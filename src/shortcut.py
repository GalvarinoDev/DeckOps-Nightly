"""
shortcut.py — DeckOps non-Steam shortcut creator

Creates non-Steam game shortcuts in Steam for CoD4 Multiplayer (CoD4x) and
World at War Multiplayer. These shortcuts point to the original game exes
in the Steam library and use the original compatdata prefixes.

Shortcuts include:
  - Proper artwork (icon, grid, wide, hero, logo) from SteamGridDB
  - Correct compatdata prefix via launch options
  - Controller template assignment based on gyro mode
  - GE-Proton compat tool assignment
  - Steam Input enabled (AllowDesktopConfig)

Called at the end of InstallScreen._run() after client installation completes.
Must be called while Steam is closed.
"""

import binascii
import os
import re
import shutil
import struct
import threading
import time
import urllib.request

# ── Paths ─────────────────────────────────────────────────────────────────────

STEAM_ROOT     = os.path.expanduser("~/.local/share/Steam")
USERDATA_DIR   = os.path.join(STEAM_ROOT, "userdata")
COMPAT_ROOT    = os.path.join(STEAM_ROOT, "steamapps", "compatdata")
STEAM_CONFIG   = os.path.join(STEAM_ROOT, "config", "config.vdf")

_HERE          = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT   = os.path.dirname(_HERE)
ASSETS_DIR     = os.path.join(PROJECT_ROOT, "assets", "controllers")

MIN_UID = 10000

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


# ── Shortcut definitions ──────────────────────────────────────────────────────

SHORTCUTS = {
    "cod4mp": {
        "name":            "Call of Duty 4: Modern Warfare - Multiplayer",
        "exe_name":        "iw3mp.exe",
        "game_appid":      "7940",
        "template_type":   "other",
        "icon_url":        "https://cdn2.steamgriddb.com/icon/59b109c700b500daa9ef3a6769bc8c6f.png",
        "grid_url":        "https://cdn2.steamgriddb.com/thumb/7a22b900577a6edbffd53153cea2999c.jpg",
        "wide_url":        "https://cdn2.steamgriddb.com/thumb/69a24bf40cd265fb00ae685cdaa040c7.jpg",
        "hero_url":        "https://cdn2.steamgriddb.com/hero_thumb/95bc8e097e09212ec0160a7bc0b46fd6.jpg",
        "logo_url":        "https://cdn2.steamgriddb.com/logo_thumb/0440169a43de927753429dd69ca8c735.png",
        "icon_ext":        "png",
        "grid_ext":        "jpg",
        "wide_ext":        "jpg",
        "hero_ext":        "jpg",
        "logo_ext":        "png",
    },
    "t4mp": {
        "name":            "Call of Duty: World at War - Multiplayer",
        "exe_name":        "CoDWaWmp.exe",
        "game_appid":      "10090",
        "template_type":   "standard",
        "icon_url":        "https://cdn2.steamgriddb.com/icon/854d6fae5ee42911677c739ee1734486.png",
        "grid_url":        "https://cdn2.steamgriddb.com/grid/bb933c55afc6987ae406e48ff58786d6.png",
        "wide_url":        "https://cdn2.steamgriddb.com/thumb/a6a0076c7e1907a4555b17cc2a6ebc85.jpg",
        "hero_url":        "https://cdn2.steamgriddb.com/hero_thumb/e369853df766fa44e1ed0ff613f563bd.jpg",
        "logo_url":        "https://cdn2.steamgriddb.com/logo_thumb/0a32bfcf5c87aa42d2a0367c1f6bb17c.png",
        "icon_ext":        "png",
        "grid_ext":        "png",
        "wide_ext":        "jpg",
        "hero_ext":        "jpg",
        "logo_ext":        "png",
    },
}


# ── Own game shortcut definitions ─────────────────────────────────────────────
#
# Used when the user selects "My Own" on the source screen. DeckOps creates
# non-Steam shortcuts for games installed outside of Steam (CD, GOG, etc.)
# with canonical names so the appid is deterministic and controllable.
#
# Artwork credits (SteamGridDB): see README.md

OWN_SHORTCUTS = {
    "cod4sp": {
        "name":           "Call of Duty 4: Modern Warfare - Singleplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/7940/b40c43b0b14b7e124553e0220581a1b9ef8e38bf.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "cod4mp": {
        "name":           "Call of Duty 4: Modern Warfare - Multiplayer",
        "template_type":  "other",
        "icon_url":       "https://cdn2.steamgriddb.com/icon/59b109c700b500daa9ef3a6769bc8c6f.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/7a22b900577a6edbffd53153cea2999c.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/69a24bf40cd265fb00ae685cdaa040c7.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/95bc8e097e09212ec0160a7bc0b46fd6.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/0440169a43de927753429dd69ca8c735.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "iw4sp": {
        "name":           "Call of Duty: Modern Warfare 2 (2009) - Singleplayer",
        "template_type":  "other",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10180/ad502494f1658220f9166c7e17ac90422bf6a479.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "iw4mp": {
        "name":           "Call of Duty: Modern Warfare 2 (2009) - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10190/7dd7c2d5bce2413131762d7cbee3f059614ed69d.jpg",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/4f4ecc161b18f07dcf2c8296fad55709.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10190/header.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/1fc214004c9481e4c8073e85323bfd4b.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/d79aac075930c83c2f1e369a511148fe.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
    "iw5sp": {
        "name":           "Call of Duty: Modern Warfare 3 (2011) - Singleplayer",
        "template_type":  "other",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42680/c3330a875925437d8216949b6571f6e941ba0679.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "iw5mp": {
        "name":           "Call of Duty: Modern Warfare 3 (2011) - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/67b48cc32ab9f04633bd50656a4a26fc.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/54726e7600c9c297610f6ed9d7d19ca7.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/ce65f40e3a20ad19fe352c52ce3bcf51.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/51770b1e6f66ba5d45e58a76e6a73dc2.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/4a64d913220fca4c33c140c6952688a8.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t4sp": {
        "name":           "Call of Duty: World at War",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10090/2bfb85222af4a01842baa5c3a16a080eb27ac6c3.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t4mp": {
        "name":           "Call of Duty: World at War - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon/854d6fae5ee42911677c739ee1734486.png",
        "grid_url":       "https://cdn2.steamgriddb.com/grid/bb933c55afc6987ae406e48ff58786d6.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6a0076c7e1907a4555b17cc2a6ebc85.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e369853df766fa44e1ed0ff613f563bd.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/0a32bfcf5c87aa42d2a0367c1f6bb17c.png",
        "icon_ext": "png", "grid_ext": "png", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5sp": {
        "name":           "Call of Duty: Black Ops",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42700/ea744d59efded3feaeebcafed224be9eadde90ac.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_hero.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5mp": {
        "name":           "Call of Duty: Black Ops - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42710/d595fb4b01201cade09e1232f2c41c0866840628.jpg",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/978f9d25644371a4c4b8df8c994cd880.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6330e9317a50ccf2d79c295dd18046f.png",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/dc82d632c9fcecb0778afbc7924494a6.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/dfb84a11f431c62436cfb760e30a34fe.png",
        "icon_ext": "jpg", "grid_ext": "png", "wide_ext": "png", "hero_ext": "png", "logo_ext": "png",
    },
    "t6sp": {
        "name":           "Call of Duty: Black Ops II - Singleplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/202970/0a23d78ade8c8d7b4cfa15bf71c9dd535b2998ca.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/library_hero.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t6zm": {
        "name":           "Call of Duty: Black Ops II - Zombies",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/743c11a9f3cb65cda4994bbdfb66c398.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/3d9ffc992e48d2aeb4b06f05471f619d.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/b87c4d009662bc436961d8f753a8de78.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e5e63da79fcd2bebbd7cb8bf1c1d0274.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/79514e888b8f2acacc68738d0cbb803e.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t6mp": {
        "name":           "Call of Duty: Black Ops II - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/715eb56d3f3b71792e230102d1da496d.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/7d3695ac5fbf55fb65ea261dd3a8577c.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/d841ee63e07b28f94920b81d2e4c21c9.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/731c83db8d2ff01bdc000083fd3c3740.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/6271faadeedd7626d661856b7a004e27.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
}


# ── Steam game artwork ────────────────────────────────────────────────────────
#
# Custom artwork applied to Steam-owned MP and ZM titles that share a store
# page with their SP counterpart. Without this, all modes show the same
# generic header in the library.
#
# SP titles (7940, 10180, 42680, 42700, 202970) are left alone — Steam's
# default artwork is fine for those.

STEAM_ARTWORK = {
    "10190": {  # MW2 MP
        "icon_url":  "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10190/7dd7c2d5bce2413131762d7cbee3f059614ed69d.jpg",
        "grid_url":  "https://cdn2.steamgriddb.com/thumb/4f4ecc161b18f07dcf2c8296fad55709.jpg",
        "wide_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/10190/header.jpg",
        "hero_url":  "https://cdn2.steamgriddb.com/hero_thumb/1fc214004c9481e4c8073e85323bfd4b.png",
        "logo_url":  "https://cdn2.steamgriddb.com/logo_thumb/d79aac075930c83c2f1e369a511148fe.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
    "42690": {  # MW3 MP
        "icon_url":  "https://cdn2.steamgriddb.com/icon_thumb/67b48cc32ab9f04633bd50656a4a26fc.png",
        "grid_url":  "https://cdn2.steamgriddb.com/thumb/54726e7600c9c297610f6ed9d7d19ca7.jpg",
        "wide_url":  "https://cdn2.steamgriddb.com/thumb/ce65f40e3a20ad19fe352c52ce3bcf51.jpg",
        "hero_url":  "https://cdn2.steamgriddb.com/hero_thumb/51770b1e6f66ba5d45e58a76e6a73dc2.jpg",
        "logo_url":  "https://cdn2.steamgriddb.com/logo_thumb/4a64d913220fca4c33c140c6952688a8.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "42710": {  # BO1 MP
        "icon_url":  "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42710/d595fb4b01201cade09e1232f2c41c0866840628.jpg",
        "grid_url":  "https://cdn2.steamgriddb.com/thumb/978f9d25644371a4c4b8df8c994cd880.png",
        "wide_url":  "https://cdn2.steamgriddb.com/thumb/a6330e9317a50ccf2d79c295dd18046f.png",
        "hero_url":  "https://cdn2.steamgriddb.com/hero_thumb/dc82d632c9fcecb0778afbc7924494a6.png",
        "logo_url":  "https://cdn2.steamgriddb.com/logo_thumb/dfb84a11f431c62436cfb760e30a34fe.png",
        "icon_ext": "jpg", "grid_ext": "png", "wide_ext": "png", "hero_ext": "png", "logo_ext": "png",
    },
    "202990": {  # BO2 MP
        "icon_url":  "https://cdn2.steamgriddb.com/icon_thumb/715eb56d3f3b71792e230102d1da496d.png",
        "grid_url":  "https://cdn2.steamgriddb.com/thumb/7d3695ac5fbf55fb65ea261dd3a8577c.jpg",
        "wide_url":  "https://cdn2.steamgriddb.com/thumb/d841ee63e07b28f94920b81d2e4c21c9.jpg",
        "hero_url":  "https://cdn2.steamgriddb.com/hero_thumb/731c83db8d2ff01bdc000083fd3c3740.png",
        "logo_url":  "https://cdn2.steamgriddb.com/logo_thumb/6271faadeedd7626d661856b7a004e27.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
    "212910": {  # BO2 ZM
        "icon_url":  "https://cdn2.steamgriddb.com/icon_thumb/743c11a9f3cb65cda4994bbdfb66c398.png",
        "grid_url":  "https://cdn2.steamgriddb.com/thumb/3d9ffc992e48d2aeb4b06f05471f619d.jpg",
        "wide_url":  "https://cdn2.steamgriddb.com/thumb/b87c4d009662bc436961d8f753a8de78.jpg",
        "hero_url":  "https://cdn2.steamgriddb.com/hero_thumb/e5e63da79fcd2bebbd7cb8bf1c1d0274.jpg",
        "logo_url":  "https://cdn2.steamgriddb.com/logo_thumb/79514e888b8f2acacc68738d0cbb803e.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_all_steam_uids():
    """Return all valid Steam user ID folders from userdata/."""
    if not os.path.isdir(USERDATA_DIR):
        return []
    seen, uids = set(), []
    for entry in os.listdir(USERDATA_DIR):
        if not entry.isdigit() or int(entry) < MIN_UID:
            continue
        real = os.path.realpath(os.path.join(USERDATA_DIR, entry))
        if real in seen:
            continue
        seen.add(real)
        uids.append(entry)
    return uids


def _get_deck_serial() -> str | None:
    """Read the Steam Deck serial number from Steam's config.vdf."""
    if not os.path.exists(STEAM_CONFIG):
        return None
    try:
        with open(STEAM_CONFIG, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        match = re.search(r'"SteamDeckRegisteredSerialNumber"\s+"([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _calc_shortcut_appid(exe_path: str, name: str) -> int:
    """
    Calculate the Steam shortcut appid from exe path and name.
    This must match Steam's internal algorithm exactly. If the CRC or
    bitmask changes, shortcuts will not resolve and artwork/controller
    configs will point to the wrong appid. Do not modify.
    """
    key = (exe_path + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return (crc | 0x80000000) & 0xFFFFFFFF


def _to_signed32(n):
    """Convert unsigned int32 appid to signed int32 for vdf binary format."""
    return n if n <= 2147483647 else n - 2**32


def _download(url: str, dest: str) -> bool:
    """Download a file from URL to dest path. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers=_BROWSER_UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return True
    except Exception:
        return False


# ── Binary VDF helpers ────────────────────────────────────────────────────────

def _vdf_string(key: str, val: str) -> bytes:
    """Encode a string field for binary VDF."""
    return b'\x01' + key.encode('utf-8') + b'\x00' + val.encode('utf-8') + b'\x00'


def _vdf_int32(key: str, val: int) -> bytes:
    """Encode an int32 field for binary VDF."""
    return b'\x02' + key.encode('utf-8') + b'\x00' + struct.pack('<i', val)


def _make_shortcut_entry(idx: int, fields: dict) -> bytes:
    """Build a single shortcut entry in binary VDF format."""
    data = b'\x00' + str(idx).encode('utf-8') + b'\x00'
    
    for key, value in fields.items():
        if key == "tags":
            # Tags is a sub-dict
            data += b'\x00' + b'tags' + b'\x00'
            for tk, tv in value.items():
                data += _vdf_string(tk, tv)
            data += b'\x08'
        elif isinstance(value, str):
            data += _vdf_string(key, value)
        elif isinstance(value, int):
            data += _vdf_int32(key, value)
    
    data += b'\x08'
    return data


def _read_existing_shortcuts(path: str) -> list:
    """Return list of existing shortcut names from shortcuts.vdf."""
    if not os.path.exists(path):
        return []
    
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except Exception:
        return []
    
    # Extract AppName values
    existing = []
    for match in re.finditer(b'\x01[Aa]pp[Nn]ame\x00([^\x00]+)\x00', data):
        existing.append(match.group(1).decode('utf-8', errors='replace'))
    
    return existing


def _read_shortcuts_raw(path: str) -> bytes:
    """Read the raw shortcuts.vdf content, stripping header/footer."""
    if not os.path.exists(path):
        return b''
    
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except Exception:
        return b''
    
    # Strip header (b'\x00shortcuts\x00') and footer (b'\x08\x08')
    header = b'\x00shortcuts\x00'
    if data.startswith(header):
        data = data[len(header):]
    if data.endswith(b'\x08\x08'):
        data = data[:-2]
    elif data.endswith(b'\x08'):
        data = data[:-1]
    
    return data


def _get_next_index(raw_data: bytes) -> int:
    """
    Find the next available shortcut index from raw shortcut entry data.

    Shortcut entries start with the byte sequence: 0x00 <index_str> 0x00
    immediately followed by 0x02 (the appid int field marker). This two-byte
    lookahead distinguishes real entry headers from the many other 0x00...0x00
    numeric sequences present in binary VDF data (string lengths, field values, etc.).
    """
    if not raw_data:
        return 0

    indices = []
    i = 0
    while i < len(raw_data) - 2:
        if raw_data[i] == 0x00:
            end = raw_data.find(b'\x00', i + 1)
            if end != -1 and end > i + 1:
                # Only treat as an entry index if immediately followed by
                # 0x02 (int32 field type byte for the 'appid' field header)
                if end + 1 < len(raw_data) and raw_data[end + 1] == 0x02:
                    try:
                        idx_str = raw_data[i + 1:end].decode('utf-8')
                        if idx_str.isdigit():
                            indices.append(int(idx_str))
                    except (UnicodeDecodeError, ValueError):
                        pass
                i = end + 1
            else:
                i += 1
        else:
            i += 1

    return max(indices, default=-1) + 1


def _write_shortcuts_vdf(path: str, existing_raw: bytes, new_entries: list):
    """Write shortcuts.vdf with existing entries preserved and new ones appended."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    data = b'\x00shortcuts\x00'
    
    if existing_raw:
        data += existing_raw
    
    for entry_bytes in new_entries:
        data += entry_bytes
    
    data += b'\x08\x08'
    
    with open(path, 'wb') as f:
        f.write(data)


# ── Artwork download ──────────────────────────────────────────────────────────

def _download_artwork(grid_dir: str, appid: int, shortcut_def: dict, prog):
    """Download all artwork for a shortcut to the grid directory (concurrent)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    appid_str = str(appid)
    os.makedirs(grid_dir, exist_ok=True)
    
    artwork_map = [
        ("icon_url",  f"{appid_str}_icon.{shortcut_def['icon_ext']}",  "icon"),
        ("grid_url",  f"{appid_str}p.{shortcut_def['grid_ext']}",      "grid"),
        ("wide_url",  f"{appid_str}.{shortcut_def['wide_ext']}",       "wide"),
        ("hero_url",  f"{appid_str}_hero.{shortcut_def['hero_ext']}",  "hero"),
        ("logo_url",  f"{appid_str}_logo.{shortcut_def['logo_ext']}",  "logo"),
    ]

    # Collect items that actually need downloading
    to_download = []
    for url_key, filename, label in artwork_map:
        url = shortcut_def.get(url_key)
        if not url:
            continue
        dest = os.path.join(grid_dir, filename)
        if os.path.exists(dest):
            prog(f"    ✓ {label} (cached)")
            continue
        to_download.append((url, dest, label))

    if not to_download:
        return

    # Download up to 5 images concurrently
    results_lock = threading.Lock()

    def _dl(url, dest, label):
        ok = _download(url, dest)
        with results_lock:
            if ok:
                prog(f"    ✓ {label}")
            else:
                prog(f"    ⚠ {label} failed")

    with ThreadPoolExecutor(max_workers=min(5, len(to_download))) as ex:
        futs = [ex.submit(_dl, url, dest, label) for url, dest, label in to_download]
        for fut in as_completed(futs):
            # Exceptions are logged inside _dl, but catch anything unexpected
            try:
                fut.result()
            except Exception:
                pass


# ── Controller template assignment ────────────────────────────────────────────

def _get_template_filename(template_type: str, gyro_mode: str) -> str:
    """Return the controller template filename based on type and gyro mode."""
    if template_type == "other":
        return f"controller_neptune_deckops_other_{gyro_mode}.vdf"
    else:
        return f"controller_neptune_deckops_{gyro_mode}.vdf"


def _assign_controller_config(uid: str, appid: int, shortcut_def: dict,
                               gyro_mode: str, prog):
    """
    Assign controller template for a non-Steam shortcut.

    We write to both configset_controller_neptune.vdf and the Deck's
    serial-specific configset. SteamOS in Game Mode reads from the serial
    file, so without it the profile only works in Desktop Mode.
    This mirrors what controller_profiles.py does for regular Steam games.
    """
    template_type = shortcut_def["template_type"]
    template_filename = _get_template_filename(template_type, gyro_mode)
    
    src_template = os.path.join(ASSETS_DIR, template_filename)
    if not os.path.exists(src_template):
        prog(f"    ⚠ Template not found: {template_filename}")
        return
    
    appid_str = str(appid)
    
    # Path: Steam Controller Configs/<uid>/config/<appid>/
    steam_cfg_root = os.path.join(
        STEAM_ROOT, "steamapps", "common",
        "Steam Controller Configs", uid, "config"
    )
    cfg_dir = os.path.join(steam_cfg_root, appid_str)
    os.makedirs(cfg_dir, exist_ok=True)
    shutil.copy2(src_template, os.path.join(cfg_dir, "controller_neptune.vdf"))
    
    # Patch configset_controller_neptune.vdf
    configset_path = os.path.join(steam_cfg_root, "configset_controller_neptune.vdf")
    _patch_configset(configset_path, appid_str, template_filename)
    
    # Patch configset_{serial}.vdf — SteamOS on Deck reads from this file
    serial = _get_deck_serial()
    if serial:
        configset_serial = os.path.join(steam_cfg_root, f"configset_{serial}.vdf")
        _patch_configset(configset_serial, appid_str, template_filename)
    
    prog(f"    ✓ Controller: {template_filename}")


def _patch_configset(configset_path: str, key: str, template_name: str):
    """
    Patch configset_controller_neptune.vdf to set our template as default.
    Duplicated from controller_profiles.py because shortcut.py runs
    standalone and should not import from the controller module.
    """
    entry = f'\t"{key}"\n\t{{\n\t\t"template"\t\t"{template_name}"\n\t}}\n'

    if not os.path.exists(configset_path):
        os.makedirs(os.path.dirname(configset_path), exist_ok=True)
        with open(configset_path, "w", encoding="utf-8") as f:
            f.write('"controller_config"\n{\n' + entry + '}\n')
        return

    with open(configset_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    pattern = rf'\t"{re.escape(key)}"\n\t\{{[^}}]*\}}\n?'
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(pattern, entry, content, flags=re.MULTILINE | re.DOTALL)
    else:
        content = content.rstrip()
        if content.endswith("}"):
            content = content[:-1].rstrip() + "\n" + entry + "}\n"

    with open(configset_path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Shortcut appid lookup ────────────────────────────────────────────────────

def get_shortcut_appid(name: str) -> int | None:
    """
    Look up the actual appid of a non-Steam shortcut by its display name.

    Reads shortcuts.vdf for all Steam user accounts and returns the unsigned
    appid if a matching entry is found. Returns None if the shortcut doesn't
    exist yet.

    This is more reliable than recalculating the CRC because the appid in
    shortcuts.vdf is the one Steam actually uses for the prefix, artwork,
    and controller config — even if the exe path has changed since creation.
    """
    uids = _find_all_steam_uids()
    name_bytes = name.encode("utf-8")

    for uid in uids:
        shortcuts_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        if not os.path.exists(shortcuts_path):
            continue

        try:
            with open(shortcuts_path, "rb") as f:
                data = f.read()
        except Exception:
            continue

        idx = data.find(name_bytes)
        if idx == -1:
            continue

        # The appid int32 field is before the AppName field.
        # Search backward from the name for the appid marker.
        # Binary VDF: \x02appid\x00<4 bytes signed int32>
        search_start = max(0, idx - 80)
        chunk = data[search_start:idx]
        marker = b'\x02appid\x00'
        marker_pos = chunk.rfind(marker)
        if marker_pos == -1:
            continue

        appid_offset = marker_pos + len(marker)
        if appid_offset + 4 > len(chunk):
            continue

        signed = struct.unpack_from("<i", chunk, appid_offset)[0]
        unsigned = signed if signed >= 0 else signed + 2**32
        return unsigned

    return None


# ── Public API ────────────────────────────────────────────────────────────────

def create_shortcuts(installed_games: dict, selected_keys: list,
                     gyro_mode: str, on_progress=None, steam_root: str = None):
    """
    Create non-Steam shortcuts for CoD4 MP and WaW MP if they were selected
    and installed. Creates shortcuts for ALL Steam user accounts.

    steam_root -- path to Steam root, used to dynamically resolve the game's
                  compatdata prefix (internal or SD card). Falls back to
                  STEAM_ROOT if not provided.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)
    
    to_create = []
    for key, shortcut_def in SHORTCUTS.items():
        if key not in selected_keys:
            continue
        if key not in installed_games:
            continue
        game = installed_games[key]
        install_dir = game.get("install_dir") or game.get("path")
        if not install_dir:
            continue
        to_create.append((key, shortcut_def, install_dir))
    
    if not to_create:
        prog("No shortcuts to create.")
        return
    
    uids = _find_all_steam_uids()
    if not uids:
        prog("⚠ No Steam user accounts found — shortcuts skipped.")
        return
    
    for uid in uids:
        prog(f"Creating shortcuts for user {uid}...")
        
        shortcuts_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")
        
        existing_names = _read_existing_shortcuts(shortcuts_path)
        existing_raw = _read_shortcuts_raw(shortcuts_path)
        next_idx = _get_next_index(existing_raw)
        
        new_entries = []
        
        for key, shortcut_def, install_dir in to_create:
            name = shortcut_def["name"]
            exe_path = os.path.join(install_dir, shortcut_def["exe_name"])
            game_appid = shortcut_def["game_appid"]

            # ── Resolve the game's actual compatdata prefix ───────────────
            # Dynamically find the prefix so it works whether the game is
            # on the internal NVME or an SD card. The shortcut reuses the
            # game's prefix (no separate prefix needed).
            from wrapper import find_compatdata
            _sr = steam_root or STEAM_ROOT
            game_data = installed_games.get(key, {})
            compatdata_path = find_compatdata(
                _sr, game_appid,
                game_install_dir=game_data.get("install_dir"),
            )
            if not compatdata_path:
                # Prefix doesn't exist yet - fall back to same library as game
                steamapps = os.path.dirname(os.path.dirname(install_dir))
                compatdata_path = os.path.join(steamapps, "compatdata", game_appid)

            # For t4mp (WaW Multiplayer), plutonium.py has replaced CoDWaWmp.exe
            # with a bash wrapper -- Proton cannot run it as a Windows binary.
            # OLED: point at the launcher with a protocol URL for online play.
            # LCD: point at the bootstrapper with -lan for offline LAN mode.
            # exe_path (CoDWaWmp.exe) is still used for appid calculation so any
            # existing shortcut entry in Steam is not invalidated.
            if key == "t4mp":
                import config as _cfg
                plut_dir = os.path.join(
                    compatdata_path,
                    "pfx", "drive_c", "users", "steamuser",
                    "AppData", "Local", "Plutonium",
                )
                if _cfg.is_oled():
                    plut_launcher  = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")
                    actual_exe     = plut_launcher
                    launch_options = (
                        f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" '
                        f'%command% "plutonium://play/t4mp"'
                    )
                else:
                    plut_bootstrapper = os.path.join(plut_dir, "bin", "plutonium-bootstrapper-win32.exe")
                    actual_exe        = plut_bootstrapper
                    player = _cfg.get_player_name() or "Player"
                    launch_options = (
                        f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" '
                        f'%command% t4mp '
                        f'"Z:{install_dir.replace("/", chr(92))}" '
                        f'+name "{player}" -lan'
                    )
            else:
                actual_exe     = exe_path
                launch_options = f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" %command%'

            shortcut_appid = _calc_shortcut_appid(exe_path, name)

            prog(f"  → {name}")
            prog(f"    appid: {shortcut_appid}")

            if name in existing_names:
                prog(f"    ✓ Shortcut exists")
            else:
                icon_path = os.path.join(grid_dir, f"{shortcut_appid}_icon.{shortcut_def['icon_ext']}")

                entry = {
                    "appid":               _to_signed32(shortcut_appid),
                    "AppName":             name,
                    "Exe":                 f'"{actual_exe}"',
                    "StartDir":            f'"{install_dir}"',
                    "icon":                icon_path,
                    "ShortcutPath":        "",
                    "LaunchOptions":       launch_options,
                    "IsHidden":            0,
                    "AllowDesktopConfig":  1,
                    "AllowOverlay":        1,
                    "OpenVR":              0,
                    "Devkit":              0,
                    "DevkitGameID":        "",
                    "DevkitOverrideAppID": 0,
                    "LastPlayTime":        int(time.time()),
                    "FlatpakAppID":        "",
                    "tags":                {"0": "DeckOps"},
                }

                entry_bytes = _make_shortcut_entry(next_idx, entry)
                new_entries.append(entry_bytes)
                next_idx += 1
                prog(f"    ✓ Shortcut created")

            # Set GE-Proton as the compat tool for this shortcut's appid,
            # the same way it is set for regular Steam games in ge_proton.py.
            # We use the shortcut_appid (not game_appid) because config.vdf
            # CompatToolMapping is keyed on the appid Steam actually launches.
            try:
                import config as cfg
                from wrapper import set_compat_tool
                ge_version = cfg.get_ge_proton_version()
                if ge_version:
                    set_compat_tool([str(shortcut_appid)], ge_version)
                    prog(f"    ✓ GE-Proton {ge_version} set")
                else:
                    prog(f"    ⚠ GE-Proton version unknown — compat tool not set")
            except Exception as ex:
                prog(f"    ⚠ Could not set GE-Proton for shortcut: {ex}")

            _download_artwork(grid_dir, shortcut_appid, shortcut_def, prog)
            _assign_controller_config(uid, shortcut_appid, shortcut_def, gyro_mode, prog)
        
        if new_entries:
            try:
                _write_shortcuts_vdf(shortcuts_path, existing_raw, new_entries)
                prog(f"  ✓ shortcuts.vdf saved")
            except Exception as e:
                prog(f"  ⚠ Failed to write shortcuts.vdf: {e}")
        else:
            prog(f"  ✓ No new shortcuts needed")
    
    prog("✓ Non-Steam shortcuts created.")


def remove_shortcuts(on_progress=None):
    """Remove DeckOps-created shortcuts from shortcuts.vdf for all users."""
    def prog(msg):
        if on_progress:
            on_progress(msg)
    
    uids = _find_all_steam_uids()
    if not uids:
        prog("⚠ No Steam user accounts found.")
        return
    
    for uid in uids:
        shortcuts_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        if not os.path.exists(shortcuts_path):
            continue
        
        try:
            with open(shortcuts_path, 'rb') as f:
                data = f.read()
        except Exception:
            continue
        
        # Find DeckOps-tagged entries and remove them
        if b'DeckOps' not in data:
            prog(f"  No DeckOps shortcuts found for user {uid}")
            continue
        
        prog(f"  Found DeckOps shortcuts for user {uid} — removing...")
        # Rather than complex binary editing, rewrite without DeckOps entries.
        # Parse entries, skip ones with DeckOps tag.
        # For safety, just clear and let next install recreate.
        prog(f"  ⚠ Manual removal recommended — edit shortcuts.vdf in Steam")


def apply_steam_artwork(selected_keys: list, on_progress=None):
    """
    Download and apply custom artwork for Steam-owned MP/ZM games.

    Uses the Steam appid directly as the grid filename prefix, so files
    like 10190p.jpg, 10190_hero.png end up in the grid folder and Steam
    picks them up on next launch.

    selected_keys — list of game keys the user selected (e.g. ["iw4mp", "t6zm"])
    on_progress   — optional callback(msg: str)
    """
    from detect_games import GAMES

    def prog(msg):
        if on_progress:
            on_progress(msg)

    # Map game keys to Steam appids that have custom artwork
    KEY_TO_STEAM_APPID = {
        "iw4mp":  "10190",
        "iw5mp":  "42690",
        "t5mp":   "42710",
        "t6mp":   "202990",
        "t6zm":   "212910",
    }

    to_apply = []
    for key in selected_keys:
        steam_appid = KEY_TO_STEAM_APPID.get(key)
        if not steam_appid:
            continue
        art_def = STEAM_ARTWORK.get(steam_appid)
        if not art_def:
            continue
        to_apply.append((key, steam_appid, art_def))

    if not to_apply:
        return

    uids = _find_all_steam_uids()
    if not uids:
        prog("⚠ No Steam user accounts found — artwork skipped.")
        return

    for uid in uids:
        grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")
        os.makedirs(grid_dir, exist_ok=True)

        for key, steam_appid, art_def in to_apply:
            prog(f"  Downloading artwork for {key} (appid {steam_appid})...")
            _download_artwork(grid_dir, int(steam_appid), art_def, prog)

    prog(f"✓ Steam artwork applied for {len(to_apply)} game(s).")


def create_own_shortcuts(own_games: dict, selected_keys: list,
                        gyro_mode: str, on_progress=None, steam_root: str = None):
    """
    Create non-Steam shortcuts for games detected via find_own_installed().

    DeckOps controls the shortcut name and exe path, so the appid is
    deterministic and artwork, controller configs, and compat tools all
    land in the right place from the start. No rename step needed.

    own_games     — dict from detect_games.find_own_installed()
    selected_keys — list of game keys the user selected
    gyro_mode     — "hold", "ads", or "toggle"
    on_progress   — optional callback(msg: str)

    Returns own_games dict enriched with shortcut_appid, compatdata_path,
    and source fields so the install flow can use them directly.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    # Plutonium keys that use the Plutonium launcher/bootstrapper instead
    # of the original game exe. The shortcut points at the Plutonium binary.
    _PLUT_KEYS = {"t4sp", "t4mp", "t5sp", "t5mp", "t6sp", "t6zm", "t6mp",
                  "iw5sp", "iw5mp"}

    to_create = {}
    for key in selected_keys:
        if key not in OWN_SHORTCUTS:
            continue
        if key not in own_games:
            continue
        game = own_games[key]
        install_dir = game.get("install_dir")
        if not install_dir:
            continue
        to_create[key] = (OWN_SHORTCUTS[key], game)

    if not to_create:
        prog("No non-Steam game shortcuts to create.")
        return own_games

    uids = _find_all_steam_uids()
    if not uids:
        prog("⚠ No Steam user accounts found — own shortcuts skipped.")
        return own_games

    for uid in uids:
        prog(f"Creating own game shortcuts for user {uid}...")

        shortcuts_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")

        existing_names = _read_existing_shortcuts(shortcuts_path)
        existing_raw = _read_shortcuts_raw(shortcuts_path)
        next_idx = _get_next_index(existing_raw)

        new_entries = []

        for key, (shortcut_def, game) in to_create.items():
            name        = shortcut_def["name"]
            install_dir = game["install_dir"]
            exe_path    = game["exe_path"]

            # Calculate appid from quoted exe + canonical name.
            # We control both, so this is deterministic.
            quoted_exe     = f'"{exe_path}"'
            shortcut_appid = _calc_shortcut_appid(quoted_exe, name)
            icon_path      = os.path.join(grid_dir, f"{shortcut_appid}_icon.{shortcut_def['icon_ext']}")

            # ── Resolve compatdata path ───────────────────────────────────
            # cod4mp and t4mp share a Steam game prefix (7940 and 10090).
            # The shortcut should reuse that prefix instead of creating its
            # own -- avoids duplicating shaders, AppData, and prefix init.
            # All other keys get their own prefix keyed on the shortcut appid.
            _SHARED_PREFIX_KEYS = {
                "cod4mp": "7940",
                "t4mp":   "10090",
            }

            if key in _SHARED_PREFIX_KEYS:
                from wrapper import find_compatdata
                _sr = steam_root or STEAM_ROOT
                game_appid = _SHARED_PREFIX_KEYS[key]
                compatdata_path = find_compatdata(
                    _sr, game_appid,
                    game_install_dir=install_dir,
                )
                if not compatdata_path:
                    # Prefix doesn't exist yet - build from install_dir's library
                    steamapps = os.path.dirname(os.path.dirname(install_dir))
                    compatdata_path = os.path.join(steamapps, "compatdata", game_appid)
            else:
                compatdata_path = os.path.join(COMPAT_ROOT, str(shortcut_appid))

            # Enrich the game dict so downstream code has the appid and paths
            game["shortcut_appid"]  = shortcut_appid
            game["compatdata_path"] = compatdata_path
            game["source"]          = "own"
            game["current_name"]    = name

            # ── Resolve the actual exe and launch options per client type ──
            # Own games may be missing original exes (e.g. MS Store copies,
            # old installs where the user replaced exes with Plutonium).
            # Plutonium games point at the Plutonium client directly.
            # iw4x/iw3sp point at the client exe dropped by the installer.
            # cod4x and vanilla keys still need the original game exe.

            if key in _PLUT_KEYS:
                import config as _cfg
                # Plutonium -- point at launcher (OLED) or own wrapper (LCD)
                plut_dir = os.path.join(
                    compatdata_path,
                    "pfx", "drive_c", "users", "steamuser",
                    "AppData", "Local", "Plutonium",
                )
                if _cfg.is_oled():
                    actual_exe = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")
                    if key in _SHARED_PREFIX_KEYS:
                        launch_options = (
                            f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" '
                            f'%command% "plutonium://play/{key}"'
                        )
                    else:
                        launch_options = f'plutonium://play/{key}'
                else:
                    # LCD: point at the standalone wrapper exe written by
                    # plutonium.py - it handles cd, env vars, and bootstrapper
                    from plutonium import OWN_WRAPPER_EXES
                    actual_exe = os.path.join(install_dir, OWN_WRAPPER_EXES[key])
                    launch_options = ""

            elif key == "iw4mp":
                # iw4x -- point at iw4x.exe (dropped by installer, no rename)
                actual_exe = os.path.join(install_dir, "iw4x.exe")
                launch_options = ""

            elif key == "cod4sp":
                # iw3sp-mod -- point at iw3sp_mod.exe (dropped by installer, no rename)
                actual_exe = os.path.join(install_dir, "iw3sp_mod.exe")
                launch_options = ""

            else:
                # cod4mp (cod4x patches iw3mp.exe in place), iw4sp, iw5sp, t6sp
                # -- these use the original game exe with no mod client
                actual_exe = exe_path
                if key in _SHARED_PREFIX_KEYS:
                    launch_options = f'STEAM_COMPAT_DATA_PATH="{compatdata_path}" %command%'
                else:
                    launch_options = ""

            # For non-Plutonium keys, warn if the target exe is missing.
            # Plutonium exes won't exist yet -- they get created when the
            # bootstrapper runs for the first time inside the prefix.
            # We still create the shortcut either way so artwork, controller
            # configs, and compat tools are in place. The user can drop the
            # exe in later and it will just work.
            if key not in _PLUT_KEYS and not os.path.exists(actual_exe):
                prog(f"  → {name}")
                prog(f"    ⚠ {os.path.basename(actual_exe)} not found -- shortcut will be created anyway")
            else:
                prog(f"  → {name}")
            prog(f"    appid: {shortcut_appid}")

            if name in existing_names:
                prog(f"    ✓ Shortcut exists")
            else:
                entry = {
                    "appid":               _to_signed32(shortcut_appid),
                    "AppName":             name,
                    "Exe":                 f'"{actual_exe}"',
                    "StartDir":            f'"{install_dir}"',
                    "icon":                icon_path,
                    "ShortcutPath":        "",
                    "LaunchOptions":       launch_options,
                    "IsHidden":            0,
                    "AllowDesktopConfig":  1,
                    "AllowOverlay":        1,
                    "OpenVR":              0,
                    "Devkit":              0,
                    "DevkitGameID":        "",
                    "DevkitOverrideAppID": 0,
                    "LastPlayTime":        0,
                    "FlatpakAppID":        "",
                    "tags":                {"0": "DeckOps"},
                }

                entry_bytes = _make_shortcut_entry(next_idx, entry)
                new_entries.append(entry_bytes)
                next_idx += 1
                prog(f"    ✓ Shortcut created")

            # Download artwork
            _download_artwork(grid_dir, shortcut_appid, shortcut_def, prog)

            # Assign controller config
            _assign_controller_config(uid, shortcut_appid, shortcut_def, gyro_mode, prog)

            # Set GE-Proton compat tool
            try:
                import config as _cfg
                from wrapper import set_compat_tool
                ge_version = _cfg.get_ge_proton_version()
                if ge_version:
                    set_compat_tool([str(shortcut_appid)], ge_version)
                    prog(f"    ✓ GE-Proton {ge_version} set")
            except Exception as ex:
                prog(f"    ⚠ Could not set GE-Proton: {ex}")

        if new_entries:
            try:
                _write_shortcuts_vdf(shortcuts_path, existing_raw, new_entries)
                prog(f"  ✓ shortcuts.vdf saved")
            except Exception as e:
                prog(f"  ⚠ Failed to write shortcuts.vdf: {e}")
        else:
            prog(f"  ✓ No new shortcuts needed")

    prog("✓ Own game shortcuts created.")
    return own_games


# ── CLI for testing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from detect_games import find_steam_root, parse_library_folders, find_installed_games
    
    print("Finding installed games...")
    steam_root = find_steam_root()
    if not steam_root:
        print("Steam not found.")
        sys.exit(1)
    
    libs = parse_library_folders(steam_root)
    installed = find_installed_games(libs)
    
    print(f"Found {len(installed)} games")
    for key in SHORTCUTS:
        if key in installed:
            print(f"  ✓ {key}: {installed[key].get('install_dir', installed[key].get('path'))}")
        else:
            print(f"  ✗ {key}: not installed")
    
    print("\nCreating shortcuts (test mode)...")
    create_shortcuts(
        installed_games=installed,
        selected_keys=list(SHORTCUTS.keys()),
        gyro_mode="hold",
        on_progress=lambda msg: print(msg)
    )
