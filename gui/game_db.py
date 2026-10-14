"""
MelkorS PS5 - Autonomous Game Profile & Preset Engine (GameDB)
Title ID / Hash-based deterministic game profiling with safe engine detection fallback.
Applies optimal core routing, Vulkan pipeline caching, shader optimization, and stability patches.
"""

import os
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
GAMEDB_FILE = os.path.join(DATA_DIR, "gamedb.json")

@dataclass
class GameProfile:
    title_id: str
    name: str
    core: str = "ps5"                  # "ps5" or "ps4"
    engine: str = "Unknown"            # "UnrealEngine5", "UnrealEngine4", "Decima", "RE_Engine", "Custom"
    shader_opt: str = "Performance"    # "None", "Size", "Performance"
    present_mode: str = "Mailbox"      # "Mailbox", "Immediate", "Fifo"
    vblank_hz: int = 60                # 60, 120
    readback_bypass: bool = True       # skips linear image readbacks for high FPS
    patch_id: Optional[str] = None     # explicit patch mapping
    extra_cli_args: List[str] = field(default_factory=list)
    notes: str = ""

# Built-in industry-standard profiles based on known game engines and compatibility
DEFAULT_PROFILES: Dict[str, dict] = {
    # --- PS5 NATIVE TITLES ---
    "PPSA07247": {
        "title_id": "PPSA07247",
        "name": "Warhammer 40,000: Boltgun",
        "core": "ps5",
        "engine": "UnrealEngine4",
        "shader_opt": "Performance",
        "present_mode": "Immediate",
        "vblank_hz": 120,
        "readback_bypass": True,
        "extra_cli_args": ["--shader-optimization-type", "Performance", "--present-mode", "Immediate", "--vblank-frequency", "120"],
        "notes": "Retro FPS. Fast presentation and 120Hz VBlank yields smooth 20+ FPS gameplay."
    },
    "PPSA36257": {
        "title_id": "PPSA36257",
        "name": "Luna Abyss",
        "core": "ps5",
        "engine": "UnrealEngine5",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "extra_cli_args": ["--shader-optimization-type", "Performance", "--present-mode", "Mailbox"],
        "notes": "Unreal Engine 5 title. Requires MelkorS UE5 Stability & TArray Sentinel patch."
    },
    "PPSA28997": {
        "title_id": "PPSA28997",
        "name": "God of War Ragnarök",
        "core": "ps5",
        "engine": "SantaMonica_Custom",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "extra_cli_args": ["--shader-optimization-type", "Performance"],
        "notes": "AAA title. Heavy geometry and dynamic compute buffers."
    },
    "PPSA01325": {
        "title_id": "PPSA01325",
        "name": "Demon's Souls Remake",
        "core": "ps5",
        "engine": "Bluepoint_Engine",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "extra_cli_args": ["--shader-optimization-type", "Performance"],
        "notes": "Bluepoint Engine. Vulkan pipeline library fast-link recommended."
    },
    "PPSA16827": {
        "title_id": "PPSA16827",
        "name": "Deathloop",
        "core": "ps5",
        "engine": "Void_Engine",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "extra_cli_args": ["--shader-optimization-type", "Performance"],
        "notes": "Void Engine. Heavy compute shader pass."
    },

    # --- PS4 POPULAR TITLES (Official XML Patches Available in MelkorS) ---
    "CUSA00900": {
        "title_id": "CUSA00900",
        "name": "Bloodborne",
        "core": "ps4",
        "engine": "FromSoftware_Dantelion",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Bloodborne.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "60 FPS & Intel 12th+ Gen crash fix applied from official patch repository."
    },
    "CUSA03173": {
        "title_id": "CUSA03173",
        "name": "Bloodborne (GOTY)",
        "core": "ps4",
        "engine": "FromSoftware_Dantelion",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Bloodborne.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "60 FPS & Intel 12th+ Gen crash fix applied from official patch repository."
    },
    "CUSA00207": {
        "title_id": "CUSA00207",
        "name": "Bloodborne (EU)",
        "core": "ps4",
        "engine": "FromSoftware_Dantelion",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Bloodborne.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "60 FPS & Intel 12th+ Gen crash fix applied from official patch repository."
    },
    "CUSA00003": {
        "title_id": "CUSA00003",
        "name": "Driveclub",
        "core": "ps4",
        "engine": "Evolution_Custom",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Driveclub.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Evolution Engine. 60 FPS patch and motion blur tweaks."
    },
    "CUSA00064": {
        "title_id": "CUSA00064",
        "name": "Driveclub (EU)",
        "core": "ps4",
        "engine": "Evolution_Custom",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Driveclub.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Evolution Engine. 60 FPS patch and motion blur tweaks."
    },
    "CUSA01127": {
        "title_id": "CUSA01127",
        "name": "P.T. (Silent Hills Demo)",
        "core": "ps4",
        "engine": "Fox_Engine",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "PT.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Fox Engine. Widescreen & resolution scale patches."
    },
    "CUSA17416": {
        "title_id": "CUSA17416",
        "name": "Persona 5 Royal",
        "core": "ps4",
        "engine": "Atlus_Internal",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Persona5_Royal.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Atlus Internal Engine. 60 FPS patch enabled."
    },
    "CUSA03627": {
        "title_id": "CUSA03627",
        "name": "The Last Guardian",
        "core": "ps4",
        "engine": "GenDesign_Custom",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "TheLastGuardian.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Unlocked framerate and resolution scaling."
    },
    "CUSA01047": {
        "title_id": "CUSA01047",
        "name": "Ratchet & Clank",
        "core": "ps4",
        "engine": "Insomniac_Engine",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "Ratchet_and_Clank.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Insomniac Engine. 60 FPS unlock."
    },
    "CUSA00035": {
        "title_id": "CUSA00035",
        "name": "The Order: 1886",
        "core": "ps4",
        "engine": "ReadyAtDawn_Custom",
        "shader_opt": "Performance",
        "present_mode": "Mailbox",
        "vblank_hz": 60,
        "readback_bypass": True,
        "patch_id": "TheOrder1886.xml",
        "extra_cli_args": ["--show-fps"],
        "notes": "Ready at Dawn Engine. Letterbox removal and unlocked framerate."
    }
}

class GameDB:
    def __init__(self):
        self.profiles: Dict[str, GameProfile] = {}
        self._load()

    def _load(self):
        """Load default profiles then merge with user customizations from gamedb.json."""
        for tid, data in DEFAULT_PROFILES.items():
            self.profiles[tid] = GameProfile(**data)

        if os.path.exists(GAMEDB_FILE):
            try:
                with open(GAMEDB_FILE, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                for tid, data in user_data.items():
                    self.profiles[tid] = GameProfile(**data)
            except Exception as e:
                print(f"[GameDB] Error loading custom gamedb: {e}")

    def save(self):
        """Save user profiles to data/gamedb.json."""
        try:
            os.makedirs(os.path.dirname(GAMEDB_FILE), exist_ok=True)
            data = {tid: asdict(p) for tid, p in self.profiles.items()}
            with open(GAMEDB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[GameDB] Error saving gamedb: {e}")

    def get_profile(self, title_id: str, eboot_path: str = "", title_name: str = "") -> GameProfile:
        """
        Gets existing profile or generates an autonomous optimized profile.
        Deterministic: checks Title ID -> Title prefix -> ELF heuristic engine detection.
        """
        if not title_id:
            title_id = "UNKNOWN"

        clean_id = title_id.strip().upper()
        if clean_id in self.profiles:
            return self.profiles[clean_id]

        # Autonomous profiling based on prefix and binary inspection
        is_ps4 = clean_id.startswith("CUSA")
        is_ps5 = clean_id.startswith("PPSA")

        core = "ps4" if is_ps4 else "ps5"
        engine = "Custom / General"
        notes = "Otomatik otonom profil oluşturuldu."

        # Check if binary is Unreal Engine 5 or 4
        if eboot_path and os.path.exists(eboot_path):
            detected_engine = self._detect_engine_safe(eboot_path)
            if detected_engine:
                engine = detected_engine

        profile = GameProfile(
            title_id=clean_id,
            name=title_name or clean_id,
            core=core,
            engine=engine,
            shader_opt="Performance",
            present_mode="Mailbox" if core == "ps4" else "Immediate",
            vblank_hz=60 if core == "ps4" else 120,
            readback_bypass=True,
            notes=f"Otonom Profil: {engine} ({core.upper()} Çekirdeği)"
        )

        return profile

    def _detect_engine_safe(self, eboot_path: str) -> Optional[str]:
        """
        Non-intrusive heuristic detection on eboot.bin to set optimal flags safely.
        Reads only string headers without modifying runtime execution.
        """
        try:
            with open(eboot_path, "rb") as f:
                header = f.read(1024 * 1024 * 8) # Read first 8MB
            if b"UnrealEngine" in header or b"/Engine/Source/" in header:
                if b"UE5" in header or b"UnrealEngine5" in header or b"Nanite" in header or b"Lumen" in header:
                    return "UnrealEngine5"
                return "UnrealEngine4"
            if b"Decima" in header:
                return "Decima"
            if b"RE_ENGINE" in header or b"ViaEngine" in header:
                return "RE_Engine"
            if b"Unity" in header:
                return "Unity"
        except Exception:
            pass
        return None
