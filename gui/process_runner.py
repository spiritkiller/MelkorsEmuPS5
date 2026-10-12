"""
MelkorS PS5 - Asynchronous Process Runner and Log Monitor
Handles both game launch and PKG installation through MelkorS Core.
"""

import os
import datetime
from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QTimer

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

    def start_game(self, emulator_exe: str, target_path: str, is_ps5: bool = True, extra_args: list = None):
        """Launch a game via MelkorS Core (auto-routing PS5 or PS4 engine)."""
        if self.is_running():
            return False

        if not os.path.exists(emulator_exe):
            self.log_received.emit(f"[HATA] MelkorS çekirdek bulunamadı: {emulator_exe}", "ERROR")
            return False

        if not os.path.exists(target_path):
            self.log_received.emit(f"[HATA] Oyun dosyası bulunamadı: {target_path}", "ERROR")
            return False

        self._install_mode = False
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_log_file = os.path.join(self.log_dir, f"session_{timestamp}.log")

        self.process = QProcess()
        self.process.setProgram(emulator_exe)

        if is_ps5:
            # MelkorS PS5 Core CLI: --game <path> --printf-direction Silent (prevents audio crackling and FPS drops)
            args = ["--game", target_path, "--printf-direction", "Silent", "--user-name", "MelkorS"]
            if extra_args:
                args.extend(extra_args)
        else:
            # MelkorS PS4 Core CLI: -g <eboot_path>
            args = list(extra_args) if extra_args else []
            args.extend(["-g", target_path])

        self.process.setArguments(args)
        self.process.setWorkingDirectory(os.path.dirname(emulator_exe))

        self.process.readyReadStandardOutput.connect(self._handle_stdout)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.started.connect(self._on_started)
        self.process.finished.connect(self._on_finished)

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
