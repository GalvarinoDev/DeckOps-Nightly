"""
steam_common.py — shared Steam helpers for DeckOps

Single home for helpers that were previously copy-pasted across
shortcut.py, controller_profiles.py, plutonium_lcd.py, and
cache_cleanup.py. The copies had already drifted (int vs str return
types, differing file-creation endings), which is exactly the failure
mode this module prevents.

This is a leaf module: it imports only the standard library and log,
with a lazy wrapper import inside record_configset_edit. Any DeckOps
module may import it without creating a cycle — including
cache_cleanup.py, which runs as a standalone script.

Consumers import with underscore aliases to keep their existing call
sites unchanged, e.g.:

    from steam_common import (
        calc_shortcut_appid as _calc_shortcut_appid,
        find_all_steam_uids as _find_all_steam_uids,
    )
"""

import binascii
import os
import re
import shutil

from log import get_logger

_log = get_logger(__name__)


# ── Paths / constants ─────────────────────────────────────────────────────────

STEAM_ROOT   = os.path.expanduser("~/.local/share/Steam")
USERDATA_DIR = os.path.join(STEAM_ROOT, "userdata")
STEAM_CONFIG = os.path.join(STEAM_ROOT, "config", "config.vdf")

# Steam user IDs below this are system/placeholder folders, not accounts.
MIN_UID = 10000


# ── Shortcut appid ────────────────────────────────────────────────────────────

def calc_shortcut_appid(exe_path: str, name: str) -> int:
    """
    Calculate the Steam shortcut appid from exe path and name.

    This must match Steam's internal algorithm exactly. If the CRC or
    bitmask changes, shortcuts will not resolve and artwork/controller
    configs will point to the wrong appid. Do not modify.

    Callers that need the appid as a string (configset keys, path
    segments) must wrap the result in str() themselves.
    """
    key = (exe_path + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return (crc | 0x80000000) & 0xFFFFFFFF


# ── Steam account discovery ───────────────────────────────────────────────────

def find_all_steam_uids() -> list[str]:
    """Return all valid Steam user ID folders from userdata/.

    Deduplicates symlinked entries by realpath and skips non-numeric or
    sub-MIN_UID folders.
    """
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


def get_deck_serial() -> str | None:
    """Read the Steam Deck serial from config.vdf, or None.

    Looks for "SteamDeckRegisteredSerialNumber", which is absent on at
    least some Decks (verified missing on a stock OLED), so callers must
    treat the serial configset write as best-effort, not required.
    """
    if not os.path.exists(STEAM_CONFIG):
        return None
    try:
        with open(STEAM_CONFIG, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        match = re.search(r'"SteamDeckRegisteredSerialNumber"\s+"([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        _log.debug("serial number read failed", exc_info=True)
    return None


# ── Configset patching ────────────────────────────────────────────────────────

def record_configset_edit(configset_path: str, key: str, template_name: str):
    """Record a configset VDF edit in the wrapper ledger.

    Lazy wrapper import keeps this module a leaf; failures are logged
    and swallowed so ledger problems never block a profile write.
    """
    try:
        from wrapper import _record_configset
        filename = os.path.basename(configset_path)
        _record_configset(filename, key, template_name)
    except Exception:
        _log.debug("configset ledger record failed", exc_info=True)


def patch_configset(configset_path: str, key: str, template_name: str):
    """
    Patch a single key in a configset VDF to use our template.
    If the key exists, replace its contents. If not, insert it.
    Creates the file with a root controller_config block if missing.
    Every write is recorded in the wrapper ledger for uninstall reversal.
    """
    entry = f'\t"{key}"\n\t{{\n\t\t"template"\t\t"{template_name}"\n\t}}\n'

    if not os.path.exists(configset_path):
        os.makedirs(os.path.dirname(configset_path), exist_ok=True)
        with open(configset_path, "w", encoding="utf-8") as f:
            f.write('"controller_config"\n{\n' + entry + '}\n')
        record_configset_edit(configset_path, key, template_name)
        return

    with open(configset_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # This regex works because configset entries are shallow (one level of
    # braces). [^}]* matches everything inside the block without crossing
    # into nested blocks. Do NOT reuse this pattern for deeper VDF
    # structures like config.vdf or localconfig.vdf where blocks nest
    # multiple levels deep.
    pattern = rf'\t"{re.escape(key)}"\n\t\{{[^}}]*\}}\n?'
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        content = re.sub(pattern, entry, content, flags=re.MULTILINE | re.DOTALL)
    else:
        content = content.rstrip()
        if content.endswith("}"):
            content = content[:-1].rstrip() + "\n" + entry + "}\n"

    with open(configset_path, "w", encoding="utf-8") as f:
        f.write(content)
    record_configset_edit(configset_path, key, template_name)
