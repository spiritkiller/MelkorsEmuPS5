"""
MelkorS PS5 - Game Scanner and Metadata Parser
Supports .pkg files, extracted game folders (eboot.bin), and MelkorS Engine-installed titles.
Extracts official icons and background banners directly from package headers.
"""

import os
import json
import struct
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

@dataclass
class PS5Game:
    title_id: str
    title_name: str
    version: str
    folder_path: str
    eboot_path: str
    icon_path: Optional[str]
    banner_path: Optional[str]
    has_fakelib: bool
    status: str
    is_pkg: bool = False

class GameScanner:
    def __init__(self, games_dir: str):
        self.games_dir = games_dir

    def scan(self) -> List[PS5Game]:
        games = []
        seen_ids = set()

        cache_dir = os.path.join(self.games_dir, "_cache")
        os.makedirs(cache_dir, exist_ok=True)

        # 1. Scan local games/ folder (pkg files + extracted folders)
        if os.path.exists(self.games_dir):
            for item in sorted(os.listdir(self.games_dir)):
                if item.startswith("_"):
                    continue
                full_path = os.path.join(self.games_dir, item)

                if os.path.isfile(full_path) and item.lower().endswith(".pkg"):
                    pkg_game = self._parse_pkg(full_path, cache_dir)
                    if pkg_game and pkg_game.title_id not in seen_ids:
                        games.append(pkg_game)
                    continue

                if os.path.isdir(full_path):
                    folder_game = self._parse_folder(full_path, item, cache_dir)
                    if folder_game and folder_game.title_id not in seen_ids:
                        games.append(folder_game)
                        seen_ids.add(folder_game.title_id)

        # 2. Scan MelkorS engine game_data directory (installed PKGs land here)
        game_data_dir = os.path.join(DATA_DIR, "game_data")
        if os.path.exists(game_data_dir):
            for item in sorted(os.listdir(game_data_dir)):
                sub = os.path.join(game_data_dir, item)
                if not os.path.isdir(sub):
                    continue
                g = self._parse_folder(sub, item, cache_dir)
                if g:
                    if g.title_id not in seen_ids:
                        games.append(g)
                        seen_ids.add(g.title_id)
                    else:
                        # Prefer installed (runnable) over PKG entry
                        for i, eg in enumerate(games):
                            if eg.title_id == g.title_id and eg.is_pkg:
                                games[i] = g
                                break

        # 3. Also read extra install_dirs from our engine config
        engine_config = os.path.join(DATA_DIR, "config.json")
        if os.path.exists(engine_config):
            try:
                with open(engine_config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                install_dirs = cfg.get("General", {}).get("install_dirs", [])
                for entry in install_dirs:
                    idir = entry.get("path", "") if isinstance(entry, dict) else str(entry)
                    if not os.path.exists(idir) or idir == self.games_dir:
                        continue
                    for sub in sorted(os.listdir(idir)):
                        sub_path = os.path.join(idir, sub)
                        if not os.path.isdir(sub_path) or sub.startswith("_"):
                            continue
                        g = self._parse_folder(sub_path, sub, cache_dir)
                        if g:
                            if g.title_id not in seen_ids:
                                games.append(g)
                                seen_ids.add(g.title_id)
                            else:
                                for i, eg in enumerate(games):
                                    if eg.title_id == g.title_id and eg.is_pkg:
                                        games[i] = g
                                        break
            except Exception:
                pass

        return games

    def _parse_pkg(self, pkg_path: str, cache_dir: str) -> Optional[PS5Game]:
        try:
            with open(pkg_path, "rb") as f:
                magic = f.read(4)
                if magic not in [b"\x7fCNT", b"\x7fPKG"]:
                    return None

                f.seek(0x10)
                entry_count = struct.unpack(">I", f.read(4))[0]
                f.seek(0x18)
                table_offset = struct.unpack(">I", f.read(4))[0]

                # Default fallback metadata from content_id at 0x40
                f.seek(0x40)
                cid_bytes = f.read(48)
                cid = cid_bytes.decode("ascii", errors="replace").strip("\x00")
                title_id = "CUSA00000"
                if "-" in cid:
                    parts = cid.split("-")
                    if len(parts) > 1 and "_" in parts[1]:
                        title_id = parts[1].split("_")[0]

                title_name = os.path.splitext(os.path.basename(pkg_path))[0]
                version = "01.00"
                icon_path = None
                banner_path = None

                # Read all entry descriptors
                f.seek(table_offset)
                entries = []
                for _ in range(min(entry_count, 256)):
                    eid, _, _, _, offset, size, _, _ = struct.unpack(">IIIIIIII", f.read(32))
                    entries.append((eid, offset, size))

                # Extract param.sfo (0x1000)
                for eid, offset, size in entries:
                    if eid == 0x1000 and size > 0:
                        f.seek(offset)
                        sfo_data = f.read(size)
                        parsed_meta = self._parse_sfo(sfo_data)
                        if "TITLE" in parsed_meta:
                            title_name = parsed_meta["TITLE"]
                        if "TITLE_ID" in parsed_meta:
                            title_id = parsed_meta["TITLE_ID"]
                        if "APP_VER" in parsed_meta:
                            version = parsed_meta["APP_VER"]
                        break

                # Extract icon0.png — 0x1200 is the official PS icon entry
                icon_file = os.path.join(cache_dir, f"{title_id}_icon.png")
                for eid, offset, size in entries:
                    if eid in [0x1200, 0x1220] and size > 1000:
                        f.seek(offset)
                        test_magic = f.read(8)
                        if test_magic.startswith(b"\x89PNG"):
                            f.seek(offset)
                            with open(icon_file, "wb") as ic:
                                ic.write(f.read(size))
                            icon_path = icon_file
                            break

                # Extract banner pic1.png (0x1006)
                banner_file = os.path.join(cache_dir, f"{title_id}_banner.png")
                for eid, offset, size in entries:
                    if eid == 0x1006 and size > 1000:
                        f.seek(offset)
                        test_magic = f.read(8)
                        if test_magic.startswith(b"\x89PNG"):
                            f.seek(offset)
                            with open(banner_file, "wb") as bf:
                                bf.write(f.read(size))
                            banner_path = banner_file
                            break

                if not icon_path or not os.path.exists(icon_path):
                    icon_path = self._download_online_icon(title_id, cache_dir)

                return PS5Game(
                    title_id=title_id,
                    title_name=title_name,
                    version=version,
                    folder_path=pkg_path,
                    eboot_path=pkg_path,
                    icon_path=icon_path,
                    banner_path=banner_path,
                    has_fakelib=False,
                    status="📦 PKG Paketi (Kurulum Gerekli)",
                    is_pkg=True
                )
        except Exception:
            return None

    def _parse_sfo(self, data: bytes) -> dict:
        meta = {}
        if not data.startswith(b"\x00PSF"):
            return meta
        try:
            key_table_offset = struct.unpack("<I", data[0x08:0x0C])[0]
            data_table_offset = struct.unpack("<I", data[0x0C:0x10])[0]
            entries_count = struct.unpack("<I", data[0x10:0x14])[0]
            for i in range(entries_count):
                entry_pos = 0x14 + (i * 16)
                key_offset = struct.unpack("<H", data[entry_pos:entry_pos+2])[0]
                param_len = struct.unpack("<I", data[entry_pos+4:entry_pos+8])[0]
                param_offset = struct.unpack("<I", data[entry_pos+12:entry_pos+16])[0]
                k_pos = key_table_offset + key_offset
                k_end = data.find(b"\x00", k_pos)
                key_str = data[k_pos:k_end].decode("ascii", errors="replace")
                v_pos = data_table_offset + param_offset
                v_bytes = data[v_pos:v_pos + param_len]
                val_str = v_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
                meta[key_str] = val_str
        except Exception:
            pass
        return meta

    def _parse_folder(self, full_path: str, item: str, cache_dir: str) -> Optional[PS5Game]:
        eboot_path = os.path.join(full_path, "eboot.bin")

        # Check one level deeper (common install layout: TITLEID/game/eboot.bin)
        if not os.path.exists(eboot_path):
            for sub in os.listdir(full_path):
                sub_full = os.path.join(full_path, sub)
                if os.path.isdir(sub_full) and os.path.exists(os.path.join(sub_full, "eboot.bin")):
                    full_path = sub_full
                    eboot_path = os.path.join(sub_full, "eboot.bin")
                    break

        if not os.path.exists(eboot_path):
            return None

        title_id = "PPSA00000"
        title_name = item
        version = "01.00"
        icon_path = None
        banner_path = None

        sce_sys_dir = os.path.join(full_path, "sce_sys")
        if os.path.exists(sce_sys_dir):
            possible_icon = os.path.join(sce_sys_dir, "icon0.png")
            if os.path.exists(possible_icon):
                icon_path = possible_icon

            possible_banner = os.path.join(sce_sys_dir, "pic1.png")
            if os.path.exists(possible_banner):
                banner_path = possible_banner

            # PS4: param.sfo (binary)
            param_sfo = os.path.join(sce_sys_dir, "param.sfo")
            if os.path.exists(param_sfo):
                try:
                    with open(param_sfo, "rb") as f:
                        parsed_meta = self._parse_sfo(f.read())
                    if "TITLE" in parsed_meta:
                        title_name = parsed_meta["TITLE"]
                    if "TITLE_ID" in parsed_meta:
                        title_id = parsed_meta["TITLE_ID"]
                    if "APP_VER" in parsed_meta:
                        version = parsed_meta["APP_VER"]
                except Exception:
                    pass

            # PS5: param.json
            param_json = os.path.join(sce_sys_dir, "param.json")
            if os.path.exists(param_json):
                try:
                    with open(param_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    title_id = data.get("titleId", title_id)
                    version = data.get("contentVersion", version)
                    # Check localizedParameters for clean game title
                    lp = data.get("localizedParameters", {})
                    if isinstance(lp, dict):
                        def_lang = lp.get("defaultLanguage", "en-US")
                        def_dict = lp.get(def_lang) if isinstance(lp.get(def_lang), dict) else {}
                        en_dict = lp.get("en-US") if isinstance(lp.get("en-US"), dict) else {}
                        cand_title = def_dict.get("titleName") or en_dict.get("titleName")
                        if cand_title:
                            title_name = cand_title
                    if not title_name or title_name == item:
                        title_name = data.get("titleName", title_name)
                except Exception:
                    pass

        # Infer title_id from folder name
        folder_name = os.path.basename(full_path)
        if title_id == "PPSA00000":
            if folder_name.startswith(("CUSA", "PPSA")) and len(folder_name) >= 9:
                title_id = folder_name[:9]
                if title_name == item:
                    rest = folder_name[9:].strip()
                    if rest:
                        title_name = rest
        elif title_name == item and (item.startswith("PPSA") or item.startswith("CUSA")):
            parts = item.split(" ", 1)
            title_id = parts[0]
            if len(parts) > 1:
                title_name = parts[1]

        # Use cached icon or download
        cached_icon = os.path.join(cache_dir, f"{title_id}_icon.png")
        if os.path.exists(cached_icon) and os.path.getsize(cached_icon) > 1000:
            if not icon_path:
                icon_path = cached_icon
        elif not icon_path:
            icon_path = self._download_online_icon(title_id, cache_dir)

        fakelib_path = os.path.join(full_path, "fakelib")
        has_fakelib = os.path.exists(fakelib_path) and len(os.listdir(fakelib_path)) > 0
        status = "✅ Hazır" if has_fakelib else "⚡ Çalıştırılabilir"

        return PS5Game(
            title_id=title_id,
            title_name=title_name,
            version=version,
            folder_path=full_path,
            eboot_path=eboot_path,
            icon_path=icon_path,
            banner_path=banner_path,
            has_fakelib=has_fakelib,
            status=status,
            is_pkg=False,
        )

    def _download_online_icon(self, title_id: str, cache_dir: str) -> Optional[str]:
        target_file = os.path.join(cache_dir, f"{title_id}_icon.png")
        if os.path.exists(target_file) and os.path.getsize(target_file) > 1000:
            return target_file

        urls = [
            f"https://orbispatches.com/api/title/{title_id}/icon",
        ]
        headers = {"User-Agent": "Mozilla/5.0"}
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = response.read()
                    if data.startswith(b"\x89PNG") and len(data) > 1000:
                        with open(target_file, "wb") as f:
                            f.write(data)
                        return target_file
            except Exception:
                continue
        return None
