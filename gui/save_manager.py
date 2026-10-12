"""
MelkorS PS5 - Save / Load State Manager
Manages instant snapshots and backups of PS5 game saves in AppData.
Allows:
- Quick Save [F5] : Takes a snapshot of the current game save state
- Quick Load [F7] : Restores the saved snapshot back to the active game save folder
- List & Manage saved slots
"""

import os
import shutil
from datetime import datetime

class SaveStateManager:
    @staticmethod
    def get_save_root():
        return os.path.expandvars(r"%APPDATA%\MelkorSPS5\home\1000\savedata")

    @staticmethod
    def quick_save(game_id: str = "CUSA41703") -> bool:
        """Create an instant snapshot of the game's active save folder safely."""
        try:
            save_root = SaveStateManager.get_save_root()
            game_save_dir = os.path.join(save_root, game_id)
            if not os.path.exists(game_save_dir):
                return False

            backup_root = os.path.join(save_root, f"{game_id}_melkors_states")
            os.makedirs(backup_root, exist_ok=True)

            slot_dir = os.path.join(backup_root, "quicksave_slot")
            if os.path.exists(slot_dir):
                shutil.rmtree(slot_dir, ignore_errors=True)

            shutil.copytree(game_save_dir, slot_dir, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"[SaveManager] quick_save error: {e}")
            return False

    @staticmethod
    def quick_load(game_id: str = "CUSA41703") -> bool:
        """Restore the snapshot back to the game's active save folder safely."""
        try:
            save_root = SaveStateManager.get_save_root()
            game_save_dir = os.path.join(save_root, game_id)
            slot_dir = os.path.join(save_root, f"{game_id}_melkors_states", "quicksave_slot")

            if not os.path.exists(slot_dir):
                return False

            shutil.copytree(slot_dir, game_save_dir, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"[SaveManager] quick_load error: {e}")
            return False
