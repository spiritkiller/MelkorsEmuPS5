"""
MelkorS PS5 - Unified XML & JSON Game Patch Manager
Supports:
1. GoldHEN / ETAHen / MelkorS Core JSON patch format (.json)
2. shadPS4 XML patch format (.xml)
3. MelkorS official patch repository (data/patches/melkors/files.json)
4. Autonomous UE5 Stability Patch Scanner & Generator
Automatically resolves, converts, and injects patches into MelkorS Core via --game-patch or -p.
"""

import os
import re
import json
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

class PatchManager:
    def __init__(self, workspace_dir: str = None):
        if not workspace_dir:
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_dir = workspace_dir
        self.patches_dir = os.path.join(workspace_dir, "patches")
        self.official_patches_dir = os.path.join(workspace_dir, "data", "patches", "melkors")
        os.makedirs(self.patches_dir, exist_ok=True)

    def find_patch_for_title(self, title_id: str, for_ps4: bool = False, eboot_path: str = "") -> str:
        """
        Locates an active patch file for a game by Title ID.
        Checks local patches directory -> official patch repository -> autonomous UE5 scanner.
        If for_ps4=True, returns XML directly if available (PS4 core natively supports XML).
        If for_ps4=False, ensures a converted JSON patch is returned for PS5 core.
        """
        if not title_id:
            return ""

        clean_id = title_id.strip().upper()
        json_path = os.path.join(self.patches_dir, f"{clean_id}.json")
        xml_path = os.path.join(self.patches_dir, f"{clean_id}.xml")

        # 1. Local JSON patch exists
        if os.path.exists(json_path):
            return json_path

        # 2. Local XML patch exists
        if os.path.exists(xml_path):
            if for_ps4:
                return xml_path
            converted = self.convert_xml_to_json(xml_path, json_path)
            if converted:
                return json_path

        # 3. Check official community patch repo (data/patches/melkors/files.json)
        official_xml = self._find_official_patch(clean_id)
        if official_xml and os.path.exists(official_xml):
            if for_ps4:
                return official_xml
            converted = self.convert_xml_to_json(official_xml, json_path)
            if converted and os.path.exists(json_path):
                return json_path
            return official_xml

        # 4. Autonomous UE5 crash scanner fallback if eboot is available
        if eboot_path and os.path.exists(eboot_path):
            auto_json = self.scan_and_generate_ue5_patch(eboot_path, clean_id)
            if auto_json and os.path.exists(auto_json):
                return auto_json

        return ""

    def _find_official_patch(self, title_id: str) -> Optional[str]:
        """Looks up Title ID in data/patches/melkors/files.json."""
        files_json = os.path.join(self.official_patches_dir, "files.json")
        if not os.path.exists(files_json):
            return None

        try:
            with open(files_json, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            for xml_name, id_list in mapping.items():
                if title_id in id_list:
                    xml_full = os.path.join(self.official_patches_dir, xml_name)
                    if os.path.exists(xml_full):
                        return xml_full
        except Exception as e:
            print(f"[PatchManager] Error reading official patches: {e}")
        return None

    def get_patch_name(self, title_id: str) -> str:
        """Returns a user-friendly name for the patch if available."""
        if not title_id:
            return ""

        clean_id = title_id.strip().upper()
        json_path = os.path.join(self.patches_dir, f"{clean_id}.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                return doc.get("name", "MelkorS Auto-Patch")
            except Exception:
                pass

        xml_path = os.path.join(self.patches_dir, f"{clean_id}.xml")
        if not os.path.exists(xml_path):
            xml_path = self._find_official_patch(clean_id)

        if xml_path and os.path.exists(xml_path):
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
                return root.attrib.get("Name", os.path.basename(xml_path))
            except Exception:
                return os.path.basename(xml_path)

        return ""

    def convert_xml_to_json(self, xml_path: str, output_json_path: str) -> bool:
        """
        Converts a shadPS4 XML patch file to MelkorS / GoldHEN JSON format.
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            if root.tag != "Metadata":
                return False

            title_id = root.attrib.get("Title", "PPSA00000")
            app_ver = root.attrib.get("AppVer", "01.00")
            app_elf = root.attrib.get("AppElf", "eboot.bin")
            patch_name = root.attrib.get("Name", "Auto Patch")

            mods = []
            patch_list = root.find("PatchList")
            if patch_list is not None:
                for idx, line in enumerate(patch_list.findall("Line")):
                    addr_str = line.attrib.get("Address", "")
                    val_str = line.attrib.get("Value", "").strip().lower()
                    if not addr_str or not val_str:
                        continue

                    # In MelkorS JSON format: offset, off (zeros if unknown), on (target bytes)
                    off_dummy = "00" * (len(val_str) // 2) if len(val_str) % 2 == 0 else "00"

                    mods.append({
                        "name": f"{patch_name} #{idx+1} ({addr_str})",
                        "enabled": True,
                        "memory": [
                            {
                                "offset": addr_str,
                                "off": off_dummy,
                                "on": val_str
                            }
                        ]
                    })

            doc = {
                "name": patch_name,
                "id": title_id,
                "version": app_ver,
                "process": app_elf,
                "mods": mods
            }

            os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)

            return True
        except Exception as e:
            print(f"[PatchManager] XML to JSON conversion failed: {e}")
            return False

    def scan_and_generate_ue5_patch(self, eboot_path: str, title_id: str, app_ver: str = "01.000.000") -> str:
        """
        Runs the UE5 Pattern Scanner on an eboot.bin and saves the patch into patches/<title_id>.json.
        """
        scanner_script = os.path.join(self.workspace_dir, "tools", "ue5_patch_scanner.py")
        if not os.path.exists(scanner_script) or not os.path.exists(eboot_path):
            return ""

        try:
            from tools.ue5_patch_scanner import UE5PatchScanner
            scanner = UE5PatchScanner(eboot_path, title_id=title_id, app_ver=app_ver)
            patches = scanner.scan_all()
            if not patches:
                return ""

            json_out = os.path.join(self.patches_dir, f"{title_id}.json")
            xml_out = os.path.join(self.patches_dir, f"{title_id}.xml")
            scanner.export_json(json_out)
            scanner.export_xml(xml_out)

            return json_out
        except Exception as e:
            print(f"[PatchManager] Scan failed: {e}")
            return ""

    def remove_patch_for_title(self, title_id: str, eboot_path: str = "") -> dict:
        """
        Removes/disables active XML and JSON patches for the given Title ID,
        and restores the original eboot.bin from backup (.orig or .bak) if present.
        """
        result = {"success": True, "files_deleted": [], "backup_restored": False}
        if not title_id:
            result["success"] = False
            return result

        clean_id = title_id.strip().upper()

        # 1. Remove JSON patch
        json_path = os.path.join(self.patches_dir, f"{clean_id}.json")
        if os.path.exists(json_path):
            try:
                os.remove(json_path)
                result["files_deleted"].append(os.path.basename(json_path))
            except Exception as e:
                print(f"[PatchManager] Could not remove {json_path}: {e}")

        # 2. Remove XML patch
        xml_path = os.path.join(self.patches_dir, f"{clean_id}.xml")
        if os.path.exists(xml_path):
            try:
                os.remove(xml_path)
                result["files_deleted"].append(os.path.basename(xml_path))
            except Exception as e:
                print(f"[PatchManager] Could not remove {xml_path}: {e}")

        # 3. Restore eboot.bin from backup if present
        if eboot_path and os.path.exists(eboot_path):
            import shutil
            orig_path = eboot_path + ".orig"
            bak_path = eboot_path + ".bak"
            restore_src = orig_path if os.path.exists(orig_path) else (bak_path if os.path.exists(bak_path) else "")
            if restore_src:
                try:
                    shutil.copy2(restore_src, eboot_path)
                    result["backup_restored"] = True
                except Exception as e:
                    print(f"[PatchManager] Could not restore eboot backup: {e}")

        return result
