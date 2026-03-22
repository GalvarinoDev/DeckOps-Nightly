"""
detect_shortcuts.py - DeckOps non-Steam game detector

Scans shortcuts.vdf for all Steam user accounts and looks for known
Call of Duty exe names. When found, it calculates the shortcut appid
from the exe path and name using Steam's CRC32 algorithm, then derives
the Proton prefix path from that appid.

Returns the same game dict structure as detect_games.find_installed_games()
so the rest of the install flow (SetupScreen, InstallScreen, etc.) needs
no changes at all.

This is used when the user selects "My Own" on the source selection screen,
meaning they installed their games via CD, GOG, Microsoft Store, or another
storefront and added them to Steam as non-Steam shortcuts.
"""

import os
import re
import struct
import binascii

from detect_games import GAMES

STEAM_ROOT   = os.path.expanduser("~/.local/share/Steam")
USERDATA_DIR = os.path.join(STEAM_ROOT, "userdata")
COMPAT_ROOT  = os.path.join(STEAM_ROOT, "steamapps", "compatdata")

MIN_UID = 10000

# Map exe filename (lowercase) to game key(s).
# Some games share an exe name — cod4 SP and MP have different exes so
# there's no ambiguity there, but we list all of them for completeness.
EXE_TO_KEYS = {
    "iw3mp.exe":      ["cod4mp"],
    "iw3sp.exe":      ["cod4sp"],
    "iw4mp.exe":      ["iw4mp"],
    "iw4sp.exe":      ["iw4sp"],
    "iw5mp.exe":      ["iw5mp"],
    "iw5sp.exe":      ["iw5sp"],
    "codwaw.exe":     ["t4sp"],
    "codwawmp.exe":   ["t4mp"],
    "blackops.exe":   ["t5sp"],
    "blackopsmp.exe": ["t5mp"],
    "t6zm.exe":       ["t6zm"],
    "t6mp.exe":       ["t6mp"],
    "t6sp.exe":       ["t6sp"],
}


def _find_all_steam_uids() -> list[str]:
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


def _calc_shortcut_appid(exe_path: str, name: str) -> int:
    """
    Calculate the Steam shortcut appid from exe path and name.
    Must match Steam's internal algorithm exactly — same as shortcut.py.
    Do not modify this function.
    """
    key = (exe_path + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return (crc | 0x80000000) & 0xFFFFFFFF


def _parse_shortcuts_vdf(path: str) -> list[dict]:
    """
    Parse a binary shortcuts.vdf file and return a list of shortcut dicts
    with keys: name, exe, start_dir.

    Binary VDF format:
      0x00 <index> 0x00 — entry header
      0x01 <key> 0x00 <value> 0x00 — string field
      0x02 <key> 0x00 <4 bytes LE int> — int32 field
      0x08 — end of block
    """
    if not os.path.exists(path):
        return []

    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return []

    shortcuts = []
    i = 0

    while i < len(data):
        # Find entry header: 0x00 <digits> 0x00 0x02 (appid int field follows)
        if data[i] != 0x00:
            i += 1
            continue
        end = data.find(b'\x00', i + 1)
        if end == -1:
            break
        if end + 1 >= len(data) or data[end + 1] != 0x02:
            i += 1
            continue
        try:
            idx_str = data[i + 1:end].decode("utf-8")
            if not idx_str.isdigit():
                i += 1
                continue
        except UnicodeDecodeError:
            i += 1
            continue

        # Found an entry — scan forward for string fields we care about
        entry = {}
        j = end + 1
        while j < len(data) and data[j] != 0x08:
            field_type = data[j]
            j += 1
            if field_type == 0x01:
                # String field: key\x00value\x00
                key_end = data.find(b'\x00', j)
                if key_end == -1:
                    break
                try:
                    key = data[j:key_end].decode("utf-8")
                except UnicodeDecodeError:
                    key = ""
                j = key_end + 1
                val_end = data.find(b'\x00', j)
                if val_end == -1:
                    break
                try:
                    val = data[j:val_end].decode("utf-8", errors="replace")
                except UnicodeDecodeError:
                    val = ""
                j = val_end + 1
                if key.lower() in ("appname", "exe", "startdir"):
                    entry[key.lower()] = val
            elif field_type == 0x02:
                # Int32 field — skip key + 4 bytes
                key_end = data.find(b'\x00', j)
                if key_end == -1:
                    break
                j = key_end + 1 + 4
            else:
                # Unknown field type — stop scanning this entry
                break

        if "exe" in entry:
            shortcuts.append({
                "name":      entry.get("appname", ""),
                "exe":       entry.get("exe", "").strip('"'),
                "start_dir": entry.get("startdir", "").strip('"'),
            })

        i = end + 1

    return shortcuts


def find_own_games() -> dict:
    """
    Scan shortcuts.vdf across all Steam user accounts and return a dict of
    detected DeckOps-supported games installed outside of Steam.

    Returns the same structure as detect_games.find_installed_games() so
    the rest of the install flow needs no changes.
    """
    found   = {}
    checked = set()  # avoid processing the same shortcut twice across users

    for uid in _find_all_steam_uids():
        vdf_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        shortcuts = _parse_shortcuts_vdf(vdf_path)

        for sc in shortcuts:
            exe_path  = sc["exe"]
            exe_name  = os.path.basename(exe_path).lower()
            name      = sc["name"]
            start_dir = sc["start_dir"]

            if not exe_name or not start_dir:
                continue

            # Deduplicate by exe path + name across multiple user accounts
            dedup_key = (exe_path, name)
            if dedup_key in checked:
                continue
            checked.add(dedup_key)

            keys = EXE_TO_KEYS.get(exe_name, [])
            for key in keys:
                if key in found:
                    continue

                meta     = GAMES.get(key)
                if not meta:
                    continue

                # Use the shortcut appid to find the Proton prefix.
                # Steam creates compatdata/<shortcut_appid> when the game
                # is launched through Steam for the first time.
                shortcut_appid    = _calc_shortcut_appid(exe_path, name)
                compatdata_path   = os.path.join(
                    COMPAT_ROOT, str(shortcut_appid)
                )
                install_dir = start_dir
                actual_exe  = os.path.join(install_dir, meta["exe"])

                found[key] = {
                    **meta,
                    "install_dir":      install_dir,
                    "exe_path":         actual_exe,
                    "exe_size":         os.path.getsize(actual_exe) if os.path.exists(actual_exe) else None,
                    "shortcut_appid":   shortcut_appid,
                    "compatdata_path":  compatdata_path,
                    # Flag so the install flow knows this came from a non-Steam source
                    "source":           "own",
                }

    return found
