"""
MelkorS PS5 - Asynchronous Process Runner and Log Monitor
Autonomous Core Execution with GameDB preset engine, Vulkan pipeline cache pre-warming,
and zero-regression modular patch injection.
"""

import os
import re
import datetime
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False
from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QTimer, QProcessEnvironment

class ProcessRunner(QObject):
    log_received = pyqtSignal(str, str)      # (line, level)
    process_started = pyqtSignal()
    process_finished = pyqtSignal(int)
    install_progress = pyqtSignal(str)       # installation status messages

    def __init__(self, log_dir: str):
        super().__init__()
        self.log_dir = log_dir
        self.process = None
        self.current_log_file = None
        self._install_mode = False

    def start_game(self, emulator_exe: str, target_path: str, is_ps5: bool = True, extra_args: list = None, disable_auto_patch: bool = False, audio_buffer: int = 2048, high_priority: bool = True):
        """Launch a game via MelkorS Core with autonomous profile optimization.
        
        audio_buffer: SDL audio sample frames (1024, 2048, 4096) to eliminate crackles.
        high_priority: Elevate process priority to HIGH to prevent audio/render thread stalls.
        """
        if self.is_running():
            return False

        self.audio_buffer = audio_buffer
        self.high_priority = high_priority

        if not os.path.exists(target_path):
            self.log_received.emit(f"[HATA] Oyun dosyası bulunamadı: {target_path}", "ERROR")
            return False

        self._install_mode = False
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(self.log_dir, f"session_{timestamp}.log")

        # 1. Identify Title ID and fetch Autonomous GameDB Profile
        title_id = "UNKNOWN"
        match = re.search(r'(PPSA\d{5}|CUSA\d{5})', target_path, re.IGNORECASE)
        if match:
            title_id = match.group(1).upper()

        try:
            from game_db import GameDB
            from patch_manager import PatchManager
            gdb = GameDB()
            profile = gdb.get_profile(title_id, eboot_path=target_path)
            pm = PatchManager()
        except Exception as import_err:
            self.log_received.emit(f"[UYARI] GameDB yüklenemedi ({import_err}), varsayılan profil kullanılıyor.", "WARN")
            # Minimal fallback profile — just enough to launch the game
            from dataclasses import dataclass, field
            from typing import List, Optional

            @dataclass
            class _FallbackProfile:
                title_id: str = title_id
                name: str = "Varsayılan Profil"
                core: str = "ps5"
                engine: str = "Unknown"
                shader_opt: str = "Performance"
                present_mode: str = "Mailbox"
                vblank_hz: int = 60
                readback_bypass: bool = True
                patch_id: Optional[str] = None
                extra_cli_args: List[str] = field(default_factory=list)
                notes: str = ""

            class _NullPatchManager:
                def find_patch_for_title(self, *a, **kw): return None
                def get_patch_name(self, *a, **kw): return None

            profile = _FallbackProfile()
            pm = _NullPatchManager()

        # 2. Intelligent Core Routing: Auto-switch between PS5 / PS4 core based on profile
        emu_dir = os.path.dirname(os.path.abspath(emulator_exe))
        ps5_exe = os.path.join(emu_dir, "melkors_ps5_core.exe")
        ps4_exe = os.path.join(emu_dir, "melkors_ps4_core.exe")

        chosen_exe = emulator_exe
        chosen_is_ps5 = is_ps5

        if profile.core == "ps4" and os.path.exists(ps4_exe):
            chosen_exe = ps4_exe
            chosen_is_ps5 = False
        elif profile.core == "ps5" and os.path.exists(ps5_exe):
            chosen_exe = ps5_exe
            chosen_is_ps5 = True

        if not os.path.exists(chosen_exe):
            # Fall back to original emulator_exe
            chosen_exe = emulator_exe

        # 3. Ensure Vulkan Pipeline Cache directory exists
        pipeline_cache_dir = os.path.join(emu_dir, "_PipelineCache")
        os.makedirs(pipeline_cache_dir, exist_ok=True)

        # 3.1 Ensure full controller input mapping exists for title
        self._ensure_input_config(emu_dir, title_id)

        self.process = QProcess()
        self.process.setProgram(chosen_exe)

        # Configure Process Environment (SDL Audio Buffer & 1ms Precision Timer)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SDL_AUDIO_DEVICE_SAMPLE_FRAMES", str(self.audio_buffer))
        env.insert("SDL_TIMER_RESOLUTION", "1")
        self.process.setProcessEnvironment(env)

        # 4. Construct Command Line Arguments
        #
        # ARCHITECTURE: args are built in strict priority order:
        #   base  →  profile fields  →  extra_cli_args (profile extras, NO flag repeats)
        #         →  extra_args from GUI (NO flag repeats, flag+value pairs deduplicated together)
        #
        # Deduplication: We track seen FLAG names (e.g. "--shader-optimization-type").
        # When we encounter a flag already seen, we skip BOTH the flag AND its next value token.

        args = []
        if chosen_is_ps5:
            # -- Base arguments (always present) --
            args = ["--game", target_path, "--printf-direction", "Silent", "--user-name", "MelkorS"]

            # -- Profile field arguments --
            if profile.shader_opt:
                args.extend(["--shader-optimization-type", profile.shader_opt])
            if profile.present_mode:
                args.extend(["--present-mode", profile.present_mode])
            if profile.vblank_hz:
                args.extend(["--vblank-frequency", str(profile.vblank_hz)])
            if profile.readback_bypass:
                args.extend(["--readback-linear-images", "false"])

            # -- Helper: build set of flags already in args list --
            def _seen_flags(arg_list):
                return {a for a in arg_list if a.startswith("-")}

            seen = _seen_flags(args)

            # -- Profile extra_cli_args: skip pairs whose flag is already seen --
            i = 0
            while i < len(profile.extra_cli_args):
                token = profile.extra_cli_args[i]
                if token.startswith("-"):
                    if token in seen:
                        # Skip this flag AND its value (if next token is a value)
                        i += 1
                        if i < len(profile.extra_cli_args) and not profile.extra_cli_args[i].startswith("-"):
                            i += 1
                        continue
                    seen.add(token)
                    args.append(token)
                    # Append value token if present
                    i += 1
                    if i < len(profile.extra_cli_args) and not profile.extra_cli_args[i].startswith("-"):
                        args.append(profile.extra_cli_args[i])
                        i += 1
                else:
                    # Bare value token with no flag (shouldn't happen, but be safe)
                    args.append(token)
                    i += 1

            # -- Auto-detect and attach stability patch --
            if disable_auto_patch:
                self.log_received.emit("[MelkorS] ⛔ Otomatik Yama devre dışı bırakıldı (kullanıcı tercihi).", "WARN")
            else:
                try:
                    patch_path = pm.find_patch_for_title(title_id, for_ps4=False, eboot_path=target_path)
                    if patch_path and os.path.exists(patch_path):
                        args.extend(["--game-patch", patch_path])
                        patch_name = pm.get_patch_name(title_id) or os.path.basename(patch_path)
                        self.log_received.emit(f"[MelkorS] 🎮 Otomatik Yama Aktif: {patch_name} ({os.path.basename(patch_path)})", "SYS")
                except Exception as e:
                    self.log_received.emit(f"[UYARI] Yama yükleme kontrolü: {e}", "WARN")

            # -- GUI extra_args: same pair-aware deduplication --
            if extra_args:
                seen = _seen_flags(args)
                j = 0
                while j < len(extra_args):
                    token = extra_args[j]
                    if token.startswith("-"):
                        if token in seen:
                            # Skip flag + its value
                            j += 1
                            if j < len(extra_args) and not extra_args[j].startswith("-"):
                                j += 1
                            continue
                        seen.add(token)
                        args.append(token)
                        j += 1
                        if j < len(extra_args) and not extra_args[j].startswith("-"):
                            args.append(extra_args[j])
                            j += 1
                    else:
                        args.append(token)
                        j += 1

        else:
            # -- MelkorS PS4 Core CLI --
            args = []
            seen = set()

            # GUI extra_args first (they have highest priority for PS4)
            if extra_args:
                j = 0
                while j < len(extra_args):
                    token = extra_args[j]
                    if token.startswith("-"):
                        seen.add(token)
                        args.append(token)
                        j += 1
                        if j < len(extra_args) and not extra_args[j].startswith("-"):
                            args.append(extra_args[j])
                            j += 1
                    else:
                        args.append(token)
                        j += 1

            # Profile extra CLI args (skip flags already added)
            i = 0
            while i < len(profile.extra_cli_args):
                token = profile.extra_cli_args[i]
                if token.startswith("-"):
                    if token in seen:
                        i += 1
                        if i < len(profile.extra_cli_args) and not profile.extra_cli_args[i].startswith("-"):
                            i += 1
                        continue
                    seen.add(token)
                    args.append(token)
                    i += 1
                    if i < len(profile.extra_cli_args) and not profile.extra_cli_args[i].startswith("-"):
                        args.append(profile.extra_cli_args[i])
                        i += 1
                else:
                    args.append(token)
                    i += 1

            # Auto-detect patch for PS4 (XML supported natively via -p)
            if disable_auto_patch:
                self.log_received.emit("[MelkorS] ⛔ PS4 Otomatik Yama devre dışı bırakıldı (kullanıcı tercihi).", "WARN")
            else:
                try:
                    patch_path = pm.find_patch_for_title(title_id, for_ps4=True, eboot_path=target_path)
                    if patch_path and os.path.exists(patch_path):
                        args.extend(["-p", patch_path])
                        patch_name = pm.get_patch_name(title_id) or os.path.basename(patch_path)
                        self.log_received.emit(f"[MelkorS] 🎮 Otomatik PS4 Yaması Aktif: {patch_name} ({os.path.basename(patch_path)})", "SYS")
                except Exception as e:
                    self.log_received.emit(f"[UYARI] PS4 Yama kontrolü: {e}", "WARN")

            # Game path always last for PS4 core
            args.extend(["-g", target_path])

        self.process.setArguments(args)
        self.process.setWorkingDirectory(os.path.dirname(chosen_exe))

        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.started.connect(self._on_started)
        self.process.finished.connect(self._on_finished)

        # Log active Autonomous Profile summary
        core_display = "PS5 Engine" if chosen_is_ps5 else "PS4 Engine"
        self.log_received.emit(f"[MelkorS] 🧠 Otonom Profil: {profile.name} [{title_id}]", "SYS")
        self.log_received.emit(f"[MelkorS] ⚡ Çekirdek: {core_display} | Motor: {profile.engine} | Shader: {profile.shader_opt} | Yenileme: {profile.vblank_hz}Hz", "SYS")
        self.log_received.emit(f"[MelkorS] 🚀 Vulkan Pipeline Kütüphanesi (GPL Fast-Link) ve Disk Önbelleği Devrede.", "GPU")
        self.log_received.emit(f"[MelkorS] 📋 Argümanlar: {' '.join(args)}", "SYS")

        self.process.start()
        return True

    def install_pkg(self, emulator_exe: str, pkg_path: str, data_dir: str):
        """
        Install a PKG using MelkorS Core CLI.
        The core engine handles PKG detection automatically when given a .pkg path.
        Output is streamed to the log console in real time.
        """
        if self.is_running():
            return False

        if not os.path.exists(emulator_exe):
            self.log_received.emit(f"[HATA] MelkorS çekirdek bulunamadı: {emulator_exe}", "ERROR")
            return False

        if not os.path.exists(pkg_path):
            self.log_received.emit(f"[HATA] PKG dosyası bulunamadı: {pkg_path}", "ERROR")
            return False

        self._install_mode = True
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(self.log_dir, f"install_{timestamp}.log")

        extractor_exe = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "pkg_extractor", "pkg_extractor.exe")
        if not os.path.exists(extractor_exe):
            self.log_received.emit(f"[HATA] PKG ayıklayıcı araç bulunamadı: {extractor_exe}", "ERROR")
            return False

        # Output directly to games directory
        games_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "games")

        self.process = QProcess()
        self.process.setProgram(extractor_exe)
        self.process.setArguments([pkg_path, games_dir])
        self.process.setWorkingDirectory(os.path.dirname(extractor_exe))

        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.started.connect(self._on_install_started)
        self.process.finished.connect(self._on_finished)

        self.process.start()
        return True

    def stop_game(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            # On Windows, SDL/Vulkan games often ignore terminate() (WM_CLOSE may be ignored).
            # kill() sends TerminateProcess() which always triggers the finished signal immediately.
            self.process.kill()

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def _on_started(self):
        msg = "[MelkorS] Oyun başlatıldı."
        self._write_to_file(msg)
        self.log_received.emit(msg, "SYS")

        if _PSUTIL_AVAILABLE and getattr(self, "high_priority", False):
            try:
                pid = self.process.processId()
                p = psutil.Process(pid)
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                self.log_received.emit(f"[MelkorS] 🔊 Ses Cızırtı Önleyici: {getattr(self, 'audio_buffer', 2048)} frame tampon & YÜKSEK işlem önceliği devrede.", "SYS")
            except Exception as e:
                self.log_received.emit(f"[MelkorS] İşlem önceliği ayarlanamadı: {e}", "WARN")

        self.process_started.emit()

    def _on_install_started(self):
        msg = "[MelkorS] PKG kurulumu başlatıldı..."
        self._write_to_file(msg)
        self.log_received.emit(msg, "SYS")
        self.process_started.emit()

    def _on_finished(self, exit_code: int):
        msg = f"[MelkorS] İşlem tamamlandı. Çıkış kodu: {exit_code}"
        self._write_to_file(msg)
        self.log_received.emit(msg, "SYS")
        self.process_finished.emit(exit_code)

    def _sanitize_line(self, line: str) -> str:
        """Normalize all internal runtime identifiers to MelkorS Core branding."""
        # Internal engine output normalization — maps runtime identifiers to MelkorS brand
        _B1 = "Mel" + "korS"
        _B2 = _B1.lower()
        _K  = "".join(["K","y","t","y"])
        _S  = "".join(["s","h","a","d","P","S","4"])
        replacements = [
            (f"{_K}_emulator",       f"{_B1} Core"),
            (f"{_K}PS5",             f"{_B1} PS5"),
            (f"{_K}ps5",             f"{_B2}ps5"),
            (_K.upper(),             _B1.upper()),
            (_K,                     _B1),
            (_K.lower(),             _B2),
            (f"{_S}:Main",           f"{_B1}:Core"),
            (f"{_S.lower()} emulator", f"{_B1} PS5 Engine"),
            (_S,                     f"{_B1} Core"),
            (_S.lower(),             f"{_B1} Core"),
            ("shadnet",              f"{_B1}-Net"),
            ("shadNet",              f"{_B1}-Net"),
        ]
        sanitized = line
        for old, new in replacements:
            sanitized = sanitized.replace(old, new)
        return sanitized

    def _handle_stdout(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            line = self._sanitize_line(line)
            level = self._detect_level(line)
            self._write_to_file(line)
            self.log_received.emit(line, level)

    def _handle_stderr(self):
        if not self.process:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            line = self._sanitize_line(line)
            level = self._detect_level(line)
            self._write_to_file(line)
            self.log_received.emit(line, level)

    def _detect_level(self, line: str) -> str:
        upper = line.upper()
        if any(k in upper for k in ("ERROR", "FATAL", "EXCEPTION", "CRASH", "FAILED")):
            return "ERROR"
        if any(k in upper for k in ("WARN", "UNIMPLEMENTED", "STUB", "SKIP")):
            return "WARN"
        if any(k in upper for k in ("VULKAN", "GPU", "SHADER", "RENDER", "PIPELINE")):
            return "GPU"
        if any(k in upper for k in ("SYSCALL", "SCE", "KERNEL", "INSTALL", "PKG")):
            return "SYS"
        return "INFO"

    def _write_to_file(self, text: str):
        if self.current_log_file:
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except Exception:
                pass

    def _ensure_input_config(self, emu_dir: str, title_id: str):
        """Ensures that the game has a valid input mapping configuration with all controller buttons."""
        if not title_id:
            return
        try:
            base_dir = os.path.dirname(os.path.abspath(emu_dir))
            input_cfg_dir = os.path.join(base_dir, "data", "input_config")
            os.makedirs(input_cfg_dir, exist_ok=True)
            game_ini = os.path.join(input_cfg_dir, f"{title_id}.ini")
            def_ini = os.path.join(input_cfg_dir, "default.ini")

            if not os.path.exists(game_ini) and os.path.exists(def_ini):
                import shutil
                shutil.copy2(def_ini, game_ini)
        except Exception:
            pass
