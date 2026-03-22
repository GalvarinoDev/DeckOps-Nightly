"""
detect_shortcuts.py - DeckOps non-Steam game detector

Scans shortcuts.vdf for all Steam user accounts and looks for known
Call of Duty exe names. When found, it automatically renames the shortcut
to the canonical DeckOps name so the shortcut appid is stable and
predictable across artwork, controller configs, and prefix paths.

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
# Some games share an exe name but cod4 SP and MP have different exes so
# there's no ambiguity there. We list all of them for completeness.
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


# Canonical shortcut names DeckOps uses for each game key.
# When a shortcut is detected by exe name, DeckOps renames it to the
# canonical name automatically. This keeps the shortcut appid stable
# since Steam calculates it from exe_path + name.
CANONICAL_NAMES = {
    "cod4mp": "Call of Duty 4: Modern Warfare - Multiplayer",
    "cod4sp": "Call of Duty 4: Modern Warfare - Singleplayer",
    "iw4mp":  "Call of Duty: Modern Warfare 2 - Multiplayer",
    "iw4sp":  "Call of Duty: Modern Warfare 2 - Singleplayer",
    "iw5mp":  "Call of Duty: Modern Warfare 3 - Multiplayer",
    "iw5sp":  "Call of Duty: Modern Warfare 3 - Singleplayer",
    "t4sp":   "Call of Duty: World at War",
    "t4mp":   "Call of Duty: World at War - Multiplayer",
    "t5sp":   "Call of Duty: Black Ops",
    "t5mp":   "Call of Duty: Black Ops - Multiplayer",
    "t6sp":   "Call of Duty: Black Ops II - Singleplayer",
    "t6zm":   "Call of Duty: Black Ops II - Zombies",
    "t6mp":   "Call of Duty: Black Ops II - Multiplayer",
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
    Must match Steam's internal algorithm exactly, same as shortcut.py.
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
      0x00 <index> 0x00    -- entry header
      0x01 <key> 0x00 <value> 0x00  -- string field
      0x02 <key> 0x00 <4 bytes LE int>  -- int32 field
      0x08  -- end of block
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

        # Found an entry, scan forward for string fields we care about
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
                # Int32 field, skip key + 4 bytes
                key_end = data.find(b'\x00', j)
                if key_end == -1:
                    break
                j = key_end + 1 + 4
            else:
                # Unknown field type, stop scanning this entry
                break

        if "exe" in entry:
            shortcuts.append({
                "name":      entry.get("appname", ""),
                "exe_raw":   entry.get("exe", ""),             # raw value with quotes, for appid calc
                "exe":       entry.get("exe", "").strip('"'),  # stripped, for filesystem ops
                "start_dir": entry.get("startdir", "").strip('"'),
            })

        i = end + 1

    return shortcuts


def _rename_shortcut_in_vdf(path: str, old_name: str, new_name: str) -> bool:
    """
    Rewrite a shortcut's AppName value in shortcuts.vdf.
    Does a targeted binary replacement of the old name bytes with the new
    name bytes. Returns True if the rename was applied.

    Must be called while Steam is closed so it doesnt overwrite our change.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return False

    # The appname value sits between 0x01 + "AppName" + 0x00 and 0x00.
    # We search for the exact old name bytes after the appname key marker
    # and replace with the new name. This is safe because each shortcut
    # entry has exactly one appname field.
    old_marker = b'\x01AppName\x00' + old_name.encode("utf-8") + b'\x00'
    new_marker = b'\x01AppName\x00' + new_name.encode("utf-8") + b'\x00'

    # Also check lowercase variant since some Steam versions write it lowercase
    old_marker_lc = b'\x01appname\x00' + old_name.encode("utf-8") + b'\x00'
    new_marker_lc = b'\x01appname\x00' + new_name.encode("utf-8") + b'\x00'

    modified = False
    if old_marker in data:
        data = data.replace(old_marker, new_marker, 1)
        modified = True
    elif old_marker_lc in data:
        data = data.replace(old_marker_lc, new_marker_lc, 1)
        modified = True

    if modified:
        try:
            with open(path, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    return False


def find_own_games(on_progress=None) -> dict:
    """
    Scan shortcuts.vdf across all Steam user accounts and return a dict of
    detected DeckOps-supported games installed outside of Steam.

    Uses the shortcut's CURRENT name (whatever the user called it) for
    the appid calculation and artwork download. This means artwork lands
    under the appid Steam is actively using right now.

    Renaming happens later via rename_own_shortcuts() after Steam is closed
    during the install flow.

    Returns the same structure as detect_games.find_installed_games() so
    the rest of the install flow needs no changes.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    found   = {}
    checked = set()  # avoid processing the same shortcut twice across users

    for uid in _find_all_steam_uids():
        vdf_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        shortcuts = _parse_shortcuts_vdf(vdf_path)

        for sc in shortcuts:
            exe_path  = sc["exe"]       # stripped, for filesystem
            exe_raw   = sc["exe_raw"]   # raw with quotes, for appid calc
            exe_name  = os.path.basename(exe_path).lower()
            name      = sc["name"]
            start_dir = sc["start_dir"]

            if not exe_name or not start_dir:
                continue

            # Deduplicate by exe path across multiple user accounts
            if exe_path in checked:
                continue
            checked.add(exe_path)

            keys = EXE_TO_KEYS.get(exe_name, [])
            for key in keys:
                if key in found:
                    continue

                meta = GAMES.get(key)
                if not meta:
                    continue

                canonical_name = CANONICAL_NAMES.get(key, "")
                if not canonical_name:
                    continue

                # Use the CURRENT shortcut name for appid calculation.
                # This is what Steam is using right now, so artwork written
                # under this appid will show up immediately.
                shortcut_appid = _calc_shortcut_appid(exe_raw, name)

                # Download artwork under the current appid so Steam sees it
                # while the shortcut still has the original name.
                try:
                    from artwork import download_artwork
                    prog(f"  Downloading artwork for {key}...")
                    download_artwork(key, shortcut_appid, on_progress=on_progress)
                except Exception as ex:
                    prog(f"  ⚠ Artwork download failed: {ex}")

                compatdata_path = os.path.join(
                    COMPAT_ROOT, str(shortcut_appid)
                )
                install_dir = start_dir
                actual_exe  = os.path.join(install_dir, meta["exe"])

                found[key] = {
                    **meta,
                    "install_dir":      install_dir,
                    "exe_path":         actual_exe,
                    "exe_raw":          exe_raw,
                    "exe_size":         os.path.getsize(actual_exe) if os.path.exists(actual_exe) else None,
                    "shortcut_appid":   shortcut_appid,
                    "compatdata_path":  compatdata_path,
                    "source":           "own",
                    "current_name":     name,
                }

    return found


def rename_own_shortcuts(own_games: dict, on_progress=None):
    """
    Rename all detected own game shortcuts to their canonical DeckOps names
    in shortcuts.vdf. Must be called while Steam is closed.

    After rename, the shortcut appid changes because Steam calculates it
    from exe_path + name. This also moves artwork from the old appid to
    the new one so Steam finds it after the rename.

    own_games -- dict returned by find_own_games()
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    for key, game in own_games.items():
        current_name   = game.get("current_name", "")
        canonical_name = CANONICAL_NAMES.get(key, "")
        exe_raw        = game.get("exe_raw", "")
        old_appid      = game.get("shortcut_appid")

        if not canonical_name or not exe_raw:
            continue
        if current_name == canonical_name:
            prog(f"  {key}: already named correctly")
            continue

        # Rename in every user's shortcuts.vdf
        for uid in _find_all_steam_uids():
            vdf_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
            renamed = _rename_shortcut_in_vdf(vdf_path, current_name, canonical_name)
            if renamed:
                prog(f"  ✓ {key}: renamed to '{canonical_name}'")

        # Calculate the new appid after rename
        new_appid = _calc_shortcut_appid(exe_raw, canonical_name)

        # Move artwork from old appid to new appid in every user's grid dir
        if old_appid and old_appid != new_appid:
            _move_artwork(old_appid, new_appid, on_progress=on_progress)

        # Update the game dict so downstream code uses the new appid
        game["shortcut_appid"]  = new_appid
        game["current_name"]    = canonical_name
        game["compatdata_path"] = os.path.join(COMPAT_ROOT, str(new_appid))


def _move_artwork(old_appid: int, new_appid: int, on_progress=None):
    """
    Rename artwork files in every user's grid directory from old_appid
    to new_appid so Steam finds them after the shortcut rename.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    old_str = str(old_appid)
    new_str = str(new_appid)

    for uid in _find_all_steam_uids():
        grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")
        if not os.path.isdir(grid_dir):
            continue
        for filename in os.listdir(grid_dir):
            if filename.startswith(old_str):
                suffix   = filename[len(old_str):]
                new_name = new_str + suffix
                old_path = os.path.join(grid_dir, filename)
                new_path = os.path.join(grid_dir, new_name)
                try:
                    os.rename(old_path, new_path)
                except Exception as ex:
                    prog(f"  ⚠ Could not rename {filename}: {ex}")

