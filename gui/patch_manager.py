"""
MelkorS PS5 - Unified XML & JSON Game Patch Manager
Supports:
1. GoldHEN / ETAHen / MelkorS Core JSON patch format (.json)
2. shadPS4 XML patch format (.xml)
Automatically resolves, converts, and injects patches into MelkorS Core via --game-patch.
"""

import os
import re
import json
import xml.etree.ElementTree as ET

class PatchManager:
    def __init__(self, workspace_dir: str = None):
        if not workspace_dir:
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_dir = workspace_dir
        self.patches_dir = os.path.join(workspace_dir, "patches")
        os.makedirs(self.patches_dir, exist_ok=True)

    def find_patch_for_title(self, title_id: str) -> str:
        """
        Locates an active patch file for a game by Title ID.
        Checks for .json first, then .xml. If .xml is found, converts it to compatible .json.
        Returns the absolute path to the ready-to-use JSON patch file, or "" if none found.
        """
        if not title_id:
            return ""

        json_path = os.path.join(self.patches_dir, f"{title_id}.json")
        xml_path = os.path.join(self.patches_dir, f"{title_id}.xml")

        # 1. If JSON patch already exists, return it
        if os.path.exists(json_path):
            return json_path

        # 2. If XML patch exists, convert to JSON for MelkorS Core
        if os.path.exists(xml_path):
            converted = self.convert_xml_to_json(xml_path, json_path)
            if converted:
                return json_path

        # 3. Check inside game directory for patches
        # e.g., games/<GameFolder>/patch.json or patches/<title_id>.json
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
                    # Core matches based on non-zero off, or if off is dummy, writes directly
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

        from tools.ue5_patch_scanner import UE5PatchScanner
        scanner = UE5PatchScanner(eboot_path, title_id=title_id, app_ver=app_ver)
        scanner.scan_all()

        json_out = os.path.join(self.patches_dir, f"{title_id}.json")
        xml_out = os.path.join(self.patches_dir, f"{title_id}.xml")
        scanner.export_json(json_out)
        scanner.export_xml(xml_out)

        return json_out
