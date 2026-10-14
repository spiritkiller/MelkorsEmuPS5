#!/usr/bin/env python3
"""
MelkorS PS5 - Unreal Engine 5 Binary Crash Pattern Scanner & Auto-Patcher
Scans PS5 eboot.bin / ELF binaries for known UE5 engine-level crash vectors:
1. NULL TArray Dereference in Visibility/Actor Lists (UKismetSystemLibrary::GetActorListFromComponentList)
2. INDEX_NONE (0x3FFFFFFF / -1) unguarded lookup table dereference
3. TArray Corrupted Element Count / Sign-bit integer overflow (test reg, reg; je -> jle)
Generates:
- Direct binary patch (--apply)
- GoldHEN / MelkorS Core compatible JSON patch (--export-json)
- shadPS4 compatible XML patch (--export-xml)
"""

import sys
import os
import re
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import argparse
import capstone

class UE5PatchScanner:
    def __init__(self, eboot_path: str, title_id: str = "", app_ver: str = "01.000.000"):
        self.eboot_path = eboot_path
        self.title_id = title_id or self._extract_title_id()
        self.app_ver = app_ver
        self.file_size = os.path.getsize(eboot_path)
        self.patches = []
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True

    def _extract_title_id(self) -> str:
        # Search for Title ID in directory path or filename (e.g., PPSA36257, CUSA...)
        match = re.search(r'(PPSA\d{5}|CUSA\d{5})', self.eboot_path)
        if match:
            return match.group(1)
        # Try reading param.json or sce_sys
        parent = os.path.dirname(self.eboot_path)
        match = re.search(r'(PPSA\d{5}|CUSA\d{5})', parent)
        if match:
            return match.group(1)
        return "PPSA00000"

    def scan_all(self):
        """Execute all pattern scans on the target binary."""
        print(f"[*] Scanning binary: {self.eboot_path} ({self.file_size / (1024*1024):.2f} MB)")
        print(f"[*] Title ID: {self.title_id}")

        with open(self.eboot_path, "rb") as f:
            data = f.read()

        self._scan_tarray_sign_bit(data)
        self._scan_null_tarray_lookup(data)
        self._scan_index_none_lookup(data)

        print(f"\n[+] Scan complete. Total patchable crash vectors found: {len(self.patches)}")
        for idx, p in enumerate(self.patches, 1):
            print(f"    {idx}. [{p['type']}] Offset: 0x{p['offset']:X} - {p['desc']}")
        return self.patches

    def _scan_tarray_sign_bit(self, data: bytes):
        """
        Pattern 3: TArray Count Integer Overflow / Sign-Bit Bug
        In UE5 TArray operations, element count in r13d/eax is tested with 'test reg, reg'
        followed by 'je <skip>' (0F 84). If count is negative/corrupted (0x80000003),
        'je' is NOT taken, leading to huge malloc/overflow.
        Fix: Change 'je' (0F 84) to 'jle' (0F 8E) to skip non-positive counts.
        """
        # Pattern: test r13d, r13d (45 85 ed); je (0f 84 xx xx xx xx)
        pattern = re.compile(b'\x45\x85\xed\x0f\x84')
        for match in pattern.finditer(data):
            pos = match.start()
            je_byte_offset = pos + 4  # The 0x84 byte in 0F 84
            # Verify context: followed by realloc or call
            context = data[pos:pos+40]
            # Check if this looks like array resize/allocation logic
            if b'\xe8' in context or b'\x89\xee' in context:
                self.patches.append({
                    "name": f"UE5 TArray Sign-Bit Guard (0x{je_byte_offset:X})",
                    "type": "TArray_Count_SignBit",
                    "offset": je_byte_offset,
                    "off": b'\x84',
                    "on": b'\x8e',
                    "desc": "Change 'je' to 'jle' after 'test r13d, r13d' to skip negative/overflowed counts."
                })

    def _scan_null_tarray_lookup(self, data: bytes):
        """
        Pattern 1: NULL TArray Pointer in GetActorListFromComponentList
        add esi, [rdi + rax*4] (03 34 87) where rdi is NULL.
        """
        target = b'\x03\x34\x87'
        start = 0
        while True:
            idx = data.find(target, start)
            if idx == -1:
                break
            start = idx + 1

            # Check context 40 bytes before
            ctx_start = max(0, idx - 40)
            ctx = data[ctx_start:idx + 10]
            # Check if rdi is loaded from stack [rsp+...] and not guarded with test rdi, rdi
            if b'\x48\x8b\x7c\x24' in ctx:  # mov rdi, [rsp+...]
                # Look if test rdi, rdi is already present
                if b'\x48\x85\xff' not in ctx:
                    # Found vulnerable site!
                    # Locate the sequence to rewrite with test rdi, rdi; je
                    # Anchor on mov rdi, [rsp+0xd8]: 48 8b 7c 24 d8
                    rdi_idx = data.find(b'\x48\x8b\x7c\x24\xd8', ctx_start)
                    if rdi_idx != -1 and rdi_idx < idx:
                        patch_start = rdi_idx
                        off_len = (idx + 7) - patch_start  # up to after mov [rsp+0xb4], esi
                        orig_bytes = data[patch_start:patch_start + off_len]
                        
                        # Generate patch bytes:
                        # 48 8b 7c 24 d8 (mov rdi, [rsp+0xd8])
                        # 48 85 ff (test rdi, rdi)
                        # 74 0b (je +11 -> skip add)
                        # 8b 74 24 b4 (mov esi, [rsp+0xb4])
                        # 03 34 87 (add esi, [rdi+rax*4])
                        # 89 74 24 b4 (mov [rsp+0xb4], esi)
                        # 90 (nop pad)
                        new_bytes = b'\x48\x8b\x7c\x24\xd8\x48\x85\xff\x74\x0b\x8b\x74\x24\xb4\x03\x34\x87\x89\x74\x24\xb4\x90'
                        if len(new_bytes) <= len(orig_bytes):
                            new_bytes = new_bytes + b'\x90' * (len(orig_bytes) - len(new_bytes))
                            self.patches.append({
                                "name": f"UE5 NULL TArray Guard (0x{patch_start:X})",
                                "type": "NULL_TArray_Pointer",
                                "offset": patch_start,
                                "off": orig_bytes,
                                "on": new_bytes,
                                "desc": "Insert NULL guard (test rdi, rdi; je) before [rdi+rax*4] dereference."
                            })

    def _scan_index_none_lookup(self, data: bytes):
        """
        Pattern 2: INDEX_NONE (0x3FFFFFFF) Lookup Table Dereference
        mov eax, [rdx + rax*8] (8b 04 c2) in actor component remapping.
        """
        target = b'\x8b\x04\xc2'
        start = 0
        while True:
            idx = data.find(target, start)
            if idx == -1:
                break
            start = idx + 1

            ctx_start = max(0, idx - 40)
            ctx = data[ctx_start:idx + 20]
            # Check if INDEX_NONE (0x3FFFFFFF) check is present
            if b'\x3d\xff\xff\xff\x3f' not in ctx:
                # Vulnerable lookup loop!
                # Identify loop start
                loop_match = data.find(b'\x41\x8b\x04\x3a', ctx_start)
                if loop_match != -1 and loop_match < idx:
                    self.patches.append({
                        "name": f"UE5 INDEX_NONE Guard Candidate (0x{idx:X})",
                        "type": "INDEX_NONE_Sentinel",
                        "offset": idx,
                        "off": data[idx:idx+3],
                        "on": b'\x90\x90\x90',  # NOP or guarded jump
                        "desc": f"Unguarded INDEX_NONE lookup at 0x{idx:X}."
                    })

    def export_json(self, output_path: str):
        """Export patches in GoldHEN / MelkorS Core mods JSON format."""
        mods_list = []
        for p in self.patches:
            mods_list.append({
                "name": p["name"],
                "enabled": True,
                "memory": [
                    {
                        "offset": f"0x{p['offset']:X}",
                        "off": p["off"].hex(),
                        "on": p["on"].hex()
                    }
                ]
            })

        doc = {
            "name": f"UE5 Auto-Patches for {self.title_id}",
            "id": self.title_id,
            "version": self.app_ver,
            "process": "eboot.bin",
            "mods": mods_list
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        print(f"[+] JSON patch exported successfully to: {output_path}")

    def export_xml(self, output_path: str):
        """Export patches in shadPS4 XML patch format."""
        root = ET.Element("Metadata", {
            "Title": self.title_id,
            "Name": "UE5 Auto Engine Crash Fixes",
            "Author": "MelkorS UE5 AutoPatcher",
            "PatchVer": "1.0",
            "AppVer": self.app_ver,
            "AppElf": "eboot.bin",
            "isEnabled": "true"
        })
        patch_list = ET.SubElement(root, "PatchList")

        for p in self.patches:
            ET.SubElement(patch_list, "Line", {
                "Type": "bytes",
                "Address": f"0x{p['offset']:08X}",
                "Value": p["on"].hex()
            })

        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        print(f"[+] XML patch exported successfully to: {output_path}")

    def apply_direct(self, backup: bool = True):
        """Directly patch the target binary on disk."""
        if not self.patches:
            print("[-] No patches to apply.")
            return

        if backup:
            bak_path = self.eboot_path + ".bak"
            if not os.path.exists(bak_path):
                import shutil
                shutil.copy2(self.eboot_path, bak_path)
                print(f"[+] Backup created: {bak_path}")

        with open(self.eboot_path, "r+b") as f:
            for p in self.patches:
                f.seek(p["offset"])
                current = f.read(len(p["off"]))
                if current == p["off"]:
                    f.seek(p["offset"])
                    f.write(p["on"])
                    print(f"[+] Applied: {p['name']} at 0x{p['offset']:X}")
                elif current == p["on"]:
                    print(f"[*] Already applied: {p['name']} at 0x{p['offset']:X}")
                else:
                    print(f"[!] Warning: Mismatch at 0x{p['offset']:X} (Current: {current.hex()}, Expected: {p['off'].hex()})")

def main():
    parser = argparse.ArgumentParser(description="MelkorS PS5 - Unreal Engine 5 Crash Pattern Scanner & Auto-Patcher")
    parser.add_argument("eboot", help="Path to eboot.bin")
    parser.add_argument("--title-id", default="", help="Title ID (e.g. PPSA36257)")
    parser.add_argument("--app-ver", default="01.000.000", help="Game application version")
    parser.add_argument("--export-json", help="Path to output JSON patch file")
    parser.add_argument("--export-xml", help="Path to output XML patch file")
    parser.add_argument("--apply", action="store_true", help="Apply patches directly to eboot.bin")
    args = parser.parse_args()

    if not os.path.exists(args.eboot):
        print(f"Error: File not found: {args.eboot}")
        sys.exit(1)

    scanner = UE5PatchScanner(args.eboot, title_id=args.title_id, app_ver=args.app_ver)
    scanner.scan_all()

    if args.export_json:
        scanner.export_json(args.export_json)
    if args.export_xml:
        scanner.export_xml(args.export_xml)
    if args.apply:
        scanner.apply_direct()

if __name__ == "__main__":
    main()
