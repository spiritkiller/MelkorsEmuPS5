"""
MelkorS PS5 - Game Dump & ELF Validator Tool
"""

import sys
import os

def validate_eboot(path):
    print(f"[*] Checking eboot file: {path}")
    if not os.path.exists(path):
        print("[-] File not found!")
        return False

    with open(path, "rb") as f:
        magic = f.read(4)

    if magic == b"\x7fELF":
        print("[+] SUCCESS: Standard 64-bit ELF binary detected (Decrypted / Ready for Translation Layer).")
        return True
    elif magic in [b"\x4f\x15\x3d\x1d", b"SCE\x00"]:
        print("[!] WARNING: Encrypted Sony SELF format detected. Needs decryption before execution!")
        return False
    else:
        print(f"[?] Unknown header magic: {magic.hex()}")
        return False

def validate_game_directory(folder_path):
    print(f"==================================================")
    print(f"Validating PS5 Game Directory: {folder_path}")
    print(f"==================================================")

    eboot_path = os.path.join(folder_path, "eboot.bin")
    if not os.path.exists(eboot_path):
        print("[-] Missing eboot.bin in root of game folder.")
        return False

    validate_eboot(eboot_path)

    fakelib_path = os.path.join(folder_path, "fakelib")
    if os.path.exists(fakelib_path):
        files = os.listdir(fakelib_path)
        print(f"[+] Fakelib found with {len(files)} module(s): {', '.join(files[:5])}...")
    else:
        print("[!] Warning: 'fakelib' directory missing. The game may fail on GPU/AGC initialization.")

    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_game_directory(sys.argv[1])
    else:
        print("Usage: python validate_game.py <path_to_game_folder>")
