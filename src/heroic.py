"""
heroic.py - LCD Plutonium install path (Heroic Games Launcher)

LCD Steam Decks can't launch Plutonium through Steam's Proton runtime
because Steam injects DLLs into Wine prefixes that cause false flags with
Plutonium's anti-cheat system. Heroic's Flatpak version doesn't inject
those DLLs, so LCD users route their Plutonium games through Heroic.

This module owns the full LCD install flow -- it is the LCD counterpart
to plutonium.py (queued to be renamed plutonium_lcd.py in a later fix).
plutonium.py's install_plutonium dispatches to install_plutonium_lcd at
the top of the function when running on LCD.

Architecture (Shape A -- shared Heroic default prefix):
  1. Install Heroic via Flatpak if not present.
  2. Download plutonium.exe into ~/Games/Heroic/deckops_plutonium/.
  3. Write a one-off "DeckOps Plutonium Setup" sideload entry into Heroic's
     library.json pointing at that exe. Its winePrefix is Heroic's default
     shared prefix at ~/Games/Heroic/Prefixes/default.
  4. Launch that sideload entry through Heroic via
     `flatpak run com.heroicgameslauncher.hgl --no-gui ... heroic://launch?...`.
     Heroic creates the shared prefix using its own GE-Proton runtime and
     runs Plutonium. The user logs in inside the exact prefix that will
     later launch the games -- zero state drift.
  5. After login, write Plutonium's config.json inside the shared prefix
     with all selected games' install paths. All Plutonium games share one
     config, one client, one login.
  6. For each selected game, write a per-game sideload entry with
     launcherArgs="plutonium://play/<key>" and winePrefix pointed at the
     same shared prefix. Steam shortcuts launch via the heroic:// protocol.

OLED Decks do not use this module at all -- plutonium.py handles OLED
directly through Steam's Proton runtime and a bash wrapper per game.
"""

import binascii
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import threading
import time
import urllib.request


# ── Heroic Flatpak paths ────────────────────────────────────────────────────
# The Flatpak version stores config under ~/.var/app/ instead of ~/.config/

HEROIC_FLATPAK_ID = "com.heroicgameslauncher.hgl"

HEROIC_CONFIG_DIR = os.path.expanduser(
    f"~/.var/app/{HEROIC_FLATPAK_ID}/config/heroic"
)
HEROIC_LIBRARY_JSON = os.path.join(
    HEROIC_CONFIG_DIR, "sideload_apps", "library.json"
)
HEROIC_GAMES_CONFIG_DIR = os.path.join(HEROIC_CONFIG_DIR, "GamesConfig")
HEROIC_ICONS_DIR = os.path.join(HEROIC_CONFIG_DIR, "icons")


# ── Shape A: shared default Heroic prefix ───────────────────────────────────
# Heroic Flatpak auto-creates ~/Games/Heroic/ on first launch and uses
# ~/Games/Heroic/Prefixes/default as its shared default Wine prefix for
# sideloaded games. We target that prefix directly so Heroic manages the
# Wine state natively and our auth tokens don't drift between prefixes.
#
# If Heroic is ever configured to use a different default prefix path, this
# constant would need to read `defaultWinePrefix` from
# ~/.var/app/com.heroicgameslauncher.hgl/config/heroic/config.json. For now
# we hardcode because every Steam Deck Heroic install uses this path by
# default and DeckOps doesn't touch that setting.

HEROIC_GAMES_DIR           = os.path.expanduser("~/Games/Heroic")
HEROIC_DEFAULT_WINE_PREFIX = os.path.join(HEROIC_GAMES_DIR, "Prefixes", "default")
DECKOPS_PLUT_DIR           = os.path.join(HEROIC_GAMES_DIR, "deckops_plutonium")

# Per-game launcher wrapper scripts. Steam shortcuts point at these instead
# of invoking flatpak directly with a heroic:// URL, because Heroic Flatpak
# can't reliably register itself as the URL handler on SteamOS (Heroic
# issues #1805, #2715, #4325, #5038 -- open since 2022). The wrapper wakes
# Heroic if needed, then fires the protocol URL once Heroic is running.
LCD_WRAPPER_DIR = os.path.expanduser("~/.local/share/deckops/lcd_wrappers")

PLUT_BOOTSTRAPPER_URL = "https://cdn.plutonium.pw/updater/plutonium.exe"

# Deterministic sideload app_name for the one-off login entry. Not hashed
# so it's easy to spot in Heroic's library if testers need to debug.
BOOTSTRAP_APP_NAME = "do_plut_bootstrap"
BOOTSTRAP_TITLE    = "DeckOps Plutonium Setup"

# Map each Plutonium game key to the config.json path field Plutonium uses
# for that game's install directory. Mirrors plutonium.GAME_META so heroic.py
# doesn't have to import from plutonium.py.
PLUT_CONFIG_KEYS = {
    "t4sp":  "t4Path",
    "t4mp":  "t4Path",
    "t5sp":  "t5Path",
    "t5mp":  "t5Path",
    "t6zm":  "t6Path",
    "t6mp":  "t6Path",
    "iw5mp": "iw5Path",
}
PLUT_GAME_KEYS = set(PLUT_CONFIG_KEYS.keys())


# Where Heroic puts its managed Wine prefixes for sideloaded games when
# DeckOps overrides the per-game winePrefix. Kept as a legacy constant for
# migration cleanup (old DeckOps installs created per-game prefixes here).
# Shape A uses HEROIC_DEFAULT_WINE_PREFIX instead.
HEROIC_PREFIX_BASE = os.path.expanduser(
    "~/.local/share/deckops/heroic_prefixes"
)


# ── Steam paths (same as shortcut.py) ───────────────────────────────────────

STEAM_ROOT   = os.path.expanduser("~/.local/share/Steam")
USERDATA_DIR = os.path.join(STEAM_ROOT, "userdata")
MIN_UID      = 10000

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


# ── Plutonium game definitions for Heroic ───────────────────────────────────
# Titles and artwork URLs mirror shortcut.py OWN_SHORTCUTS so LCD users see
# the same game names as OLED users. The Steam shortcut appid (calculated
# from quoted_exe + title) will differ between LCD and OLED because the
# exe path differs (flatpak vs wrapper script), but the visible name is
# identical.

HEROIC_PLUT_GAMES = {
    "t4sp": {
        "title":          "Call of Duty: World at War",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10090/2bfb85222af4a01842baa5c3a16a080eb27ac6c3.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t4mp": {
        "title":          "Call of Duty: World at War - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon/854d6fae5ee42911677c739ee1734486.png",
        "grid_url":       "https://cdn2.steamgriddb.com/grid/bb933c55afc6987ae406e48ff58786d6.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6a0076c7e1907a4555b17cc2a6ebc85.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e369853df766fa44e1ed0ff613f563bd.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/0a32bfcf5c87aa42d2a0367c1f6bb17c.png",
        "icon_ext": "png", "grid_ext": "png", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5sp": {
        "title":          "Call of Duty: Black Ops",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42700/ea744d59efded3feaeebcafed224be9eadde90ac.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_hero.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5mp": {
        "title":          "Call of Duty: Black Ops - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42710/d595fb4b01201cade09e1232f2c41c0866840628.jpg",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/978f9d25644371a4c4b8df8c994cd880.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6330e9317a50ccf2d79c295dd18046f.png",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/dc82d632c9fcecb0778afbc7924494a6.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/dfb84a11f431c62436cfb760e30a34fe.png",
        "icon_ext": "jpg", "grid_ext": "png", "wide_ext": "png", "hero_ext": "png", "logo_ext": "png",
    },
    "t6mp": {
        "title":          "Call of Duty: Black Ops II - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/715eb56d3f3b71792e230102d1da496d.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/7d3695ac5fbf55fb65ea261dd3a8577c.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/d841ee63e07b28f94920b81d2e4c21c9.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/731c83db8d2ff01bdc000083fd3c3740.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/6271faadeedd7626d661856b7a004e27.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
    "t6zm": {
        "title":          "Call of Duty: Black Ops II - Zombies",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/743c11a9f3cb65cda4994bbdfb66c398.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/3d9ffc992e48d2aeb4b06f05471f619d.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/b87c4d009662bc436961d8f753a8de78.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e5e63da79fcd2bebbd7cb8bf1c1d0274.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/79514e888b8f2acacc68738d0cbb803e.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "iw5mp": {
        "title":          "Call of Duty: Modern Warfare 3 (2011) - Multiplayer",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/67b48cc32ab9f04633bd50656a4a26fc.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/54726e7600c9c297610f6ed9d7d19ca7.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/ce65f40e3a20ad19fe352c52ce3bcf51.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/51770b1e6f66ba5d45e58a76e6a73dc2.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/4a64d913220fca4c33c140c6952688a8.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
}


# ── Heroic app_name generation ──────────────────────────────────────────────
# We generate deterministic app_name IDs so DeckOps can always find its own
# entries in Heroic's library.json. Heroic uses random 22-char base64 IDs
# but there's no requirement for randomness - just uniqueness.

def _heroic_app_name(game_key: str) -> str:
    """
    Generate a deterministic Heroic app_name from a DeckOps game key.
    Uses a sha256 hash truncated to 22 chars of url-safe base64, matching
    Heroic's ID length. Prefixed with 'do_' so DeckOps entries are easy
    to identify in the library.
    """
    import base64
    digest = hashlib.sha256(f"deckops_plut_{game_key}".encode()).digest()
    b64 = base64.urlsafe_b64encode(digest)[:19].decode()
    return f"do_{b64}"


# ── Heroic install/detection ────────────────────────────────────────────────

def is_heroic_installed() -> bool:
    """Check if Heroic Games Launcher Flatpak is installed."""
    try:
        result = subprocess.run(
            ["flatpak", "info", HEROIC_FLATPAK_ID],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_heroic(on_progress=None) -> bool:
    """
    Install Heroic Games Launcher via Flatpak from Flathub.
    Returns True if Heroic is available after this call.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if is_heroic_installed():
        prog("Heroic Games Launcher already installed.")
        return True

    prog("Installing Heroic Games Launcher from Flathub...")
    try:
        result = subprocess.run(
            [
                "flatpak", "install", "--user", "--noninteractive",
                "flathub", HEROIC_FLATPAK_ID,
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            prog("Heroic Games Launcher installed.")
            return True
        else:
            stderr = result.stderr.decode(errors="replace")
            prog(f"Heroic install failed: {stderr[:200]}")
            return False
    except FileNotFoundError:
        prog("Flatpak not found - cannot install Heroic.")
        return False
    except subprocess.TimeoutExpired:
        prog("Heroic install timed out.")
        return False


def _grant_heroic_filesystem_access(paths: list, on_progress=None):
    """
    Grant Heroic's Flatpak sandbox filesystem access to the given paths.
    This is required so Heroic/Proton can read the game files.
    Safe to call multiple times - flatpak override is idempotent.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    for path in paths:
        if not path:
            continue
        try:
            subprocess.run(
                [
                    "flatpak", "override", "--user",
                    HEROIC_FLATPAK_ID,
                    f"--filesystem={path}",
                ],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            prog(f"  Warning: could not grant Heroic access to {path}")

    # Always grant access to the DeckOps data dir and Steam compatibilitytools
    _always_grant = [
        os.path.expanduser("~/.local/share/deckops"),
        os.path.expanduser("~/.local/share/Steam/compatibilitytools.d"),
        os.path.expanduser("~/.local/share/Steam"),
        "/run/media",  # SD card access
    ]
    for path in _always_grant:
        try:
            subprocess.run(
                [
                    "flatpak", "override", "--user",
                    HEROIC_FLATPAK_ID,
                    f"--filesystem={path}",
                ],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass


# ── Heroic library.json management ──────────────────────────────────────────

def _read_heroic_library() -> dict:
    """Read the Heroic sideload library. Returns the full JSON dict."""
    if not os.path.exists(HEROIC_LIBRARY_JSON):
        return {"games": []}
    try:
        with open(HEROIC_LIBRARY_JSON) as f:
            data = json.load(f)
        if "games" not in data:
            data["games"] = []
        return data
    except (json.JSONDecodeError, IOError):
        return {"games": []}


def _write_heroic_library(data: dict):
    """Write the Heroic sideload library back to disk."""
    os.makedirs(os.path.dirname(HEROIC_LIBRARY_JSON), exist_ok=True)
    with open(HEROIC_LIBRARY_JSON, "w") as f:
        json.dump(data, f, indent="\t")


def _add_heroic_sideload_entry(game_key: str, executable: str,
                                install_dir: str, on_progress=None):
    """
    Add or update a sideload entry in Heroic's library.json.

    executable  - full path to the Plutonium launcher exe inside the prefix
    install_dir - the game's install directory (folder_name in Heroic)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        prog(f"  Unknown game key: {game_key}")
        return

    app_name = _heroic_app_name(game_key)
    game_def = HEROIC_PLUT_GAMES[game_key]

    # Build the sideload entry matching Heroic's expected format
    entry = {
        "runner": "sideload",
        "app_name": app_name,
        "title": game_def["title"],
        "install": {
            "executable": executable,
            "platform": "Windows",
            "is_dlc": False,
        },
        "folder_name": install_dir,
        "art_cover": game_def.get("grid_url", ""),
        "is_installed": True,
        "art_square": game_def.get("grid_url", ""),
        "canRunOffline": True,
        "browserUrl": "",
        "customUserAgent": "",
        "launchFullScreen": False,
    }

    library = _read_heroic_library()

    # Replace existing entry for this app_name, or append
    idx = next(
        (i for i, g in enumerate(library["games"]) if g.get("app_name") == app_name),
        None,
    )
    if idx is not None:
        library["games"][idx] = entry
        prog(f"  Updated Heroic entry for {game_def['title']}")
    else:
        library["games"].append(entry)
        prog(f"  Added Heroic entry for {game_def['title']}")

    _write_heroic_library(library)


def _remove_heroic_sideload_entry(game_key: str, on_progress=None):
    """Remove a DeckOps sideload entry from Heroic's library.json."""
    def prog(msg):
        if on_progress:
            on_progress(msg)

    app_name = _heroic_app_name(game_key)
    library = _read_heroic_library()

    before = len(library["games"])
    library["games"] = [g for g in library["games"] if g.get("app_name") != app_name]

    if len(library["games"]) < before:
        _write_heroic_library(library)
        prog(f"  Removed Heroic entry for {game_key}")
    else:
        prog(f"  No Heroic entry found for {game_key}")


# ── Heroic per-game config ──────────────────────────────────────────────────

def _write_heroic_game_config(game_key: str, ge_proton_version: str,
                               on_progress=None):
    """
    Write the per-game GamesConfig JSON for a Heroic sideload entry.
    Sets up GE-Proton, a DeckOps-managed prefix, and sane defaults.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    app_name = _heroic_app_name(game_key)
    config_path = os.path.join(HEROIC_GAMES_CONFIG_DIR, f"{app_name}.json")
    os.makedirs(HEROIC_GAMES_CONFIG_DIR, exist_ok=True)

    # Resolve the GE-Proton binary path
    proton_dir = os.path.expanduser(
        f"~/.local/share/Steam/compatibilitytools.d/{ge_proton_version}"
    )
    proton_bin = os.path.join(proton_dir, "proton")

    # Shape A: every Plutonium game points at Heroic's shared default prefix.
    # The user logs in once during the bootstrapper phase inside this exact
    # prefix, and all Plutonium games share that login state, Plutonium
    # install, and Wine environment. One prefix, one login, many games.
    prefix_path = HEROIC_DEFAULT_WINE_PREFIX

    config = {
        app_name: {
            "autoInstallDxvk": True,
            "autoInstallDxvkNvapi": True,
            "autoInstallVkd3d": True,
            "preferSystemLibs": False,
            "enableEsync": True,
            "enableMsync": False,
            "enableFsync": True,
            "enableWineWayland": False,
            "enableHDR": False,
            "enableWoW64": False,
            "nvidiaPrime": False,
            "enviromentOptions": [],
            "wrapperOptions": [],
            "showFps": False,
            "useGameMode": True,
            "battlEyeRuntime": True,
            "eacRuntime": True,
            "language": "",
            "beforeLaunchScriptPath": "",
            "afterLaunchScriptPath": "",
            # Pass the Plutonium protocol URL as an argument to the launcher
            # exe. Without this, the launcher exe opens its own UI (game
            # picker / login screen) instead of jumping straight into the
            # requested game. Matches what the OLED bash wrapper does with
            # `plutonium-launcher-win32.exe "plutonium://play/<key>"`.
            "launcherArgs": f'"plutonium://play/{game_key}"',
            "verboseLogs": False,
            "advertiseAvxForRosetta": False,
            "enableQuickSavesMenu": False,
            "wineVersion": {
                "bin": proton_bin,
                "name": ge_proton_version,
                "type": "proton",
            },
            "winePrefix": prefix_path,
            "wineCrossoverBottle": "",
        },
        "version": "v0",
        "explicit": True,
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    prog(f"  Heroic game config written for {game_key}")


def _remove_heroic_game_config(game_key: str, on_progress=None):
    """Remove the Heroic GamesConfig JSON for a game key."""
    def prog(msg):
        if on_progress:
            on_progress(msg)

    app_name = _heroic_app_name(game_key)
    config_path = os.path.join(HEROIC_GAMES_CONFIG_DIR, f"{app_name}.json")
    if os.path.exists(config_path):
        os.remove(config_path)
        prog(f"  Removed Heroic game config for {game_key}")

    # Shape A: the shared default Wine prefix is never removed on single-game
    # uninstall because other Plutonium games may still need it. Full wipe
    # happens in cleanup_all_heroic() when the user uninstalls DeckOps.


# ── Steam shortcut helpers (mirrors shortcut.py patterns) ───────────────────
# These create non-Steam shortcuts that launch games via Heroic's protocol.
# The exe is /usr/bin/flatpak and the launch options use heroic://launch.

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


def _calc_shortcut_appid(exe_path: str, name: str) -> int:
    """Calculate Steam shortcut appid - must match Steam's internal algorithm."""
    key = (exe_path + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return (crc | 0x80000000) & 0xFFFFFFFF


def _to_signed32(n):
    """Convert unsigned int32 to signed int32 for VDF binary format."""
    return n if n <= 2147483647 else n - 2**32


def _vdf_string(key: str, val: str) -> bytes:
    return b'\x01' + key.encode('utf-8') + b'\x00' + val.encode('utf-8') + b'\x00'


def _vdf_int32(key: str, val: int) -> bytes:
    return b'\x02' + key.encode('utf-8') + b'\x00' + struct.pack('<i', val)


def _make_shortcut_entry(idx: int, fields: dict) -> bytes:
    data = b'\x00' + str(idx).encode('utf-8') + b'\x00'
    for key, value in fields.items():
        if key == "tags":
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
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except Exception:
        return []
    existing = []
    for match in re.finditer(b'\x01[Aa]pp[Nn]ame\x00([^\x00]+)\x00', data):
        existing.append(match.group(1).decode('utf-8', errors='replace'))
    return existing


def _read_shortcuts_raw(path: str) -> bytes:
    if not os.path.exists(path):
        return b''
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except Exception:
        return b''
    header = b'\x00shortcuts\x00'
    if data.startswith(header):
        data = data[len(header):]
    if data.endswith(b'\x08\x08'):
        data = data[:-2]
    elif data.endswith(b'\x08'):
        data = data[:-1]
    return data


def _get_next_index(raw_data: bytes) -> int:
    if not raw_data:
        return 0
    indices = []
    i = 0
    while i < len(raw_data) - 2:
        if raw_data[i] == 0x00:
            end = raw_data.find(b'\x00', i + 1)
            if end != -1 and end > i + 1:
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = b'\x00shortcuts\x00'
    if existing_raw:
        data += existing_raw
    for entry_bytes in new_entries:
        data += entry_bytes
    data += b'\x08\x08'
    with open(path, 'wb') as f:
        f.write(data)


def _download(url: str, dest: str) -> bool:
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers=_BROWSER_UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
        return True
    except Exception:
        return False


def _download_artwork(grid_dir: str, appid: int, game_def: dict, prog):
    """Download all artwork for a shortcut to the grid directory."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    appid_str = str(appid)
    os.makedirs(grid_dir, exist_ok=True)

    artwork_map = [
        ("icon_url",  f"{appid_str}_icon.{game_def['icon_ext']}",  "icon"),
        ("grid_url",  f"{appid_str}p.{game_def['grid_ext']}",      "grid"),
        ("wide_url",  f"{appid_str}.{game_def['wide_ext']}",       "wide"),
        ("hero_url",  f"{appid_str}_hero.{game_def['hero_ext']}",  "hero"),
        ("logo_url",  f"{appid_str}_logo.{game_def['logo_ext']}",  "logo"),
    ]

    to_download = []
    for url_key, filename, label in artwork_map:
        url = game_def.get(url_key)
        if not url:
            continue
        dest = os.path.join(grid_dir, filename)
        if os.path.exists(dest):
            prog(f"    {label} (cached)")
            continue
        to_download.append((url, dest, label))

    if not to_download:
        return

    results_lock = threading.Lock()

    def _dl(url, dest, label):
        ok = _download(url, dest)
        with results_lock:
            if ok:
                prog(f"    {label} downloaded")
            else:
                prog(f"    {label} failed")

    with ThreadPoolExecutor(max_workers=min(5, len(to_download))) as ex:
        futs = [ex.submit(_dl, url, dest, label) for url, dest, label in to_download]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass


# ── LCD Shape A helpers ─────────────────────────────────────────────────────
# Everything below powers the LCD Plutonium install flow. plutonium.py's
# install_plutonium dispatches to install_plutonium_lcd at the top of the
# function on LCD, so these helpers are the actual entry points for LCD.

def get_shared_plut_dir() -> str:
    """
    Return the Plutonium/ folder path inside Heroic's shared default
    prefix. This is where the Plutonium client files live after the
    bootstrapper login, and where all LCD Plutonium games read their
    config.json from.
    """
    return os.path.join(
        HEROIC_DEFAULT_WINE_PREFIX,
        "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )


def is_plutonium_ready_lcd() -> bool:
    """
    LCD counterpart to plutonium.is_plutonium_ready. Returns True if the
    user has logged in inside the shared Heroic prefix and Plutonium has
    finished downloading its client files. Checked by looking for the
    storage/ subdir, which Plutonium only creates after a successful login.
    """
    storage = os.path.join(get_shared_plut_dir(), "storage")
    if not os.path.isdir(storage):
        return False
    # Must have at least one game subfolder (t4, t5, t6, iw5, demonware)
    try:
        return any(
            os.path.isdir(os.path.join(storage, d))
            for d in os.listdir(storage)
        )
    except OSError:
        return False


def _wine_path_lcd(linux_path: str) -> str:
    """Convert a Linux path to Wine Z: drive notation (same as plutonium.py)."""
    return "Z:" + linux_path.replace("/", "\\")


def _write_plutonium_config_lcd(plut_dir: str, selected_keys: list,
                                  installed_games: dict,
                                  on_progress=None):
    """
    Write Plutonium's config.json inside the shared Heroic prefix with
    the install paths for every selected Plutonium game.

    Shape A writes one config.json that lists all selected games' paths
    (t4Path, t5Path, t6Path, iw5Path). Plutonium's Windows client is
    designed to hold multiple games in one install, so this is the
    intended usage not a hack.

    Idempotent: writing the same config.json N times produces the same
    result, so calling this once per game during the install loop is fine.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    config_path = os.path.join(plut_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    if not isinstance(data, dict):
        data = {}

    for key in selected_keys:
        if key not in PLUT_CONFIG_KEYS:
            continue
        game = installed_games.get(key)
        if not game:
            continue
        install_dir = game.get("install_dir", "")
        if install_dir:
            data[PLUT_CONFIG_KEYS[key]] = _wine_path_lcd(install_dir)

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)
    prog(f"  Wrote Plutonium config.json with {len(selected_keys)} game path(s)")


def _write_metadata_lcd(install_dir: str, data: dict):
    """
    Write the DeckOps metadata sentinel into a game's install directory.
    Mirrors plutonium._write_metadata so heroic.py doesn't need to import
    private helpers from plutonium.py.
    """
    if not install_dir:
        return
    path = os.path.join(install_dir, "deckops_plutonium.json")
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _download_plutonium_exe(dest_dir: str, on_progress=None) -> str:
    """
    Download plutonium.exe into dest_dir. Returns the full path to the
    downloaded file. Retries up to 3 times on network failure.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "plutonium.exe")

    # If it's already there and non-empty, assume it's good
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        prog("  plutonium.exe already present, skipping download.")
        return dest

    prog("  Downloading Plutonium bootstrapper...")
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(PLUT_BOOTSTRAPPER_URL,
                                          headers=_BROWSER_UA)
            with urllib.request.urlopen(req, timeout=60) as r, \
                 open(dest, "wb") as f:
                f.write(r.read())
            prog(f"  Downloaded plutonium.exe ({os.path.getsize(dest)} bytes)")
            return dest
        except Exception as ex:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return dest


def _ensure_bootstrap_sideload_entry(plutonium_exe: str,
                                      ge_proton_version: str,
                                      on_progress=None):
    """
    Write the one-off "DeckOps Plutonium Setup" sideload entry into
    Heroic's library.json and its matching GamesConfig JSON.

    This is the entry Heroic launches via the heroic:// protocol during
    the bootstrapper phase so the user can log in inside the shared
    default Wine prefix. Kept around after login so testers can re-launch
    it from Heroic if their token ever expires.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    # library.json entry
    entry = {
        "runner": "sideload",
        "app_name": BOOTSTRAP_APP_NAME,
        "title": BOOTSTRAP_TITLE,
        "install": {
            "executable": plutonium_exe,
            "platform": "Windows",
            "is_dlc": False,
        },
        "folder_name": os.path.dirname(plutonium_exe),
        "art_cover": "",
        "is_installed": True,
        "art_square": "",
        "canRunOffline": True,
        "browserUrl": "",
        "customUserAgent": "",
        "launchFullScreen": False,
    }

    library = _read_heroic_library()
    idx = next(
        (i for i, g in enumerate(library["games"])
         if g.get("app_name") == BOOTSTRAP_APP_NAME),
        None,
    )
    if idx is not None:
        library["games"][idx] = entry
    else:
        library["games"].append(entry)
    _write_heroic_library(library)
    prog("  Bootstrap sideload entry written.")

    # GamesConfig JSON -- same shape as per-game configs but without
    # launcherArgs (we want the raw plutonium.exe to open so the user
    # can log in normally).
    os.makedirs(HEROIC_GAMES_CONFIG_DIR, exist_ok=True)
    config_path = os.path.join(HEROIC_GAMES_CONFIG_DIR,
                                f"{BOOTSTRAP_APP_NAME}.json")

    proton_dir = os.path.expanduser(
        f"~/.local/share/Steam/compatibilitytools.d/{ge_proton_version}"
    )
    proton_bin = os.path.join(proton_dir, "proton")

    config = {
        BOOTSTRAP_APP_NAME: {
            "autoInstallDxvk": True,
            "autoInstallDxvkNvapi": True,
            "autoInstallVkd3d": True,
            "preferSystemLibs": False,
            "enableEsync": True,
            "enableMsync": False,
            "enableFsync": True,
            "enableWineWayland": False,
            "enableHDR": False,
            "enableWoW64": False,
            "nvidiaPrime": False,
            "enviromentOptions": [],
            "wrapperOptions": [],
            "showFps": False,
            "useGameMode": True,
            "battlEyeRuntime": True,
            "eacRuntime": True,
            "language": "",
            "beforeLaunchScriptPath": "",
            "afterLaunchScriptPath": "",
            "launcherArgs": "",
            "verboseLogs": False,
            "advertiseAvxForRosetta": False,
            "enableQuickSavesMenu": False,
            "wineVersion": {
                "bin": proton_bin,
                "name": ge_proton_version,
                "type": "proton",
            },
            "winePrefix": HEROIC_DEFAULT_WINE_PREFIX,
            "wineCrossoverBottle": "",
        },
        "version": "v0",
        "explicit": True,
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    prog("  Bootstrap GamesConfig written.")



def setup_heroic_game(game_key: str, game: dict, ge_proton_version: str,
                      plut_dir=None, on_progress=None):
    """
    Set up a single Plutonium game to launch through Heroic on LCD.

    This is called from install_plutonium_lcd once per selected game.
    It writes the per-game Heroic sideload entry, per-game GamesConfig
    (with winePrefix pointed at the shared default prefix and
    launcherArgs set to plutonium://play/<game_key>), and the matching
    Steam non-Steam shortcut that launches via the heroic:// protocol.

    game_key          - one of t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    game              - dict with at least install_dir and name
    ge_proton_version - e.g. "GE-Proton10-34"
    plut_dir          - deprecated / ignored. Shape A always targets the
                        shared default Heroic prefix, so the launcher exe
                        path is computed from get_shared_plut_dir().
                        Parameter kept so older call sites don't break.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        prog(f"Unknown game key for Heroic: {game_key}")
        return

    install_dir = game.get("install_dir", "")
    game_def = HEROIC_PLUT_GAMES[game_key]

    # Shape A: the launcher exe always lives inside the shared default
    # Heroic prefix. plut_dir (if passed) is ignored for compatibility.
    shared_plut_dir = get_shared_plut_dir()
    launcher_exe = os.path.join(shared_plut_dir, "bin",
                                "plutonium-launcher-win32.exe")

    prog(f"Setting up Heroic for {game_def['title']}...")

    # 1. Grant Heroic filesystem access to this game's directory
    _grant_heroic_filesystem_access([install_dir], on_progress=on_progress)

    # 2. Write sideload entry in library.json
    _add_heroic_sideload_entry(game_key, launcher_exe, install_dir,
                                on_progress=on_progress)

    # 3. Write per-game config (GE-Proton, shared prefix, launcherArgs)
    _write_heroic_game_config(game_key, ge_proton_version,
                               on_progress=on_progress)

    # 4. Create Steam shortcut that launches via Heroic protocol
    _create_heroic_steam_shortcut(game_key, on_progress=on_progress)

    prog(f"Heroic setup complete for {game_def['title']}")


def launch_bootstrapper_lcd(on_progress=None):
    """
    LCD Plutonium bootstrapper. Called by ui_qt.py during the install flow
    before any per-game setup happens. Does the following:

      1. Ensures Heroic Flatpak is installed (no-op if already present).
      2. Grants Heroic filesystem access to ~/Games/Heroic and DeckOps dirs.
      3. Downloads plutonium.exe into ~/Games/Heroic/deckops_plutonium/.
      4. Writes a one-off "DeckOps Plutonium Setup" sideload entry pointing
         at that exe, with winePrefix set to Heroic's shared default prefix.
      5. Launches that entry via the heroic:// protocol. Heroic creates the
         shared prefix using its own GE-Proton runtime and runs Plutonium.

    This function does NOT wait for Plutonium to exit. The UI calling layer
    already has a manual continuation gate (_plut_event.wait()) that the
    user clicks after they close the Plutonium window. Fire-and-forget is
    deliberately more robust -- Heroic's Flatpak process may or may not
    exit cleanly when the game does, and we don't want to hang on that.

    Raises on download failure or if Heroic can't be installed.
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # 1. Heroic available
    prog(5, "Ensuring Heroic Games Launcher is installed...")
    if not install_heroic(on_progress=lambda m: prog(5, m)):
        raise RuntimeError("Heroic Games Launcher could not be installed.")

    # 2. Filesystem access. ~/Games is normally already granted by Heroic
    #    itself on first launch, but override is idempotent so a repeat call
    #    is cheap insurance.
    prog(10, "Granting Heroic filesystem access...")
    _grant_heroic_filesystem_access(
        [HEROIC_GAMES_DIR, DECKOPS_PLUT_DIR],
        on_progress=lambda m: prog(10, m),
    )

    # Make sure ~/Games/Heroic exists (Heroic creates it on first launch,
    # but DeckOps may run before the user has ever opened Heroic).
    os.makedirs(HEROIC_GAMES_DIR, exist_ok=True)

    # 3. Download plutonium.exe
    prog(15, "Downloading Plutonium bootstrapper...")
    try:
        plutonium_exe = _download_plutonium_exe(
            DECKOPS_PLUT_DIR,
            on_progress=lambda m: prog(15, m),
        )
    except Exception as ex:
        raise RuntimeError(f"Failed to download plutonium.exe: {ex}")

    # 4. Resolve GE-Proton version. We need this for the bootstrap
    #    GamesConfig wineVersion block so Heroic uses GE-Proton (not its
    #    bundled UMU default) to run the login session. Same version will
    #    be used later by the per-game entries.
    try:
        import config as _cfg
        ge_version = _cfg.get_ge_proton_version()
    except Exception:
        ge_version = None
    if not ge_version:
        ge_version = "GE-Proton10-34"  # reasonable fallback

    # 5. Write the bootstrap sideload entry + its GamesConfig
    prog(20, "Registering bootstrap entry with HGL...")
    _ensure_bootstrap_sideload_entry(
        plutonium_exe, ge_version,
        on_progress=lambda m: prog(20, m),
    )

    # 6. Launch via the heroic:// protocol. Fire and forget -- UI has a
    #    manual continuation gate after this returns.
    prog(25, "Launching Plutonium through HGL -- please log in...")
    launch_uri = (
        f"heroic://launch?appName={BOOTSTRAP_APP_NAME}&runner=sideload"
    )
    try:
        subprocess.Popen(
            [
                "flatpak", "run", HEROIC_FLATPAK_ID,
                "--no-gui", "--no-sandbox",
                launch_uri,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RuntimeError("flatpak command not found -- cannot launch HGL.")
    except Exception as ex:
        raise RuntimeError(f"Failed to launch HGL bootstrapper: {ex}")

    prog(30, "HGL is launching Plutonium. Log in and close when done.")


def install_plutonium_lcd(game: dict, game_key: str,
                           installed_games: dict,
                           on_progress=None):
    """
    LCD per-game Plutonium install. Called from plutonium.install_plutonium
    via the early LCD dispatch at the top of that function.

    Flow:
      1. Verify the shared Heroic prefix is ready (user logged in, storage
         populated) -- raises if not.
      2. Write Plutonium's config.json inside the shared prefix with all
         selected Plutonium games' install paths. Idempotent across calls.
      3. Call setup_heroic_game() to write this game's per-game sideload
         entry, GamesConfig (winePrefix = shared), and Steam shortcut.
      4. Write the DeckOps metadata sentinel into the game's install dir so
         uninstall_plutonium can find it later.

    game            - entry from detect_games.find_installed_games()
    game_key        - one of: t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    installed_games - full dict of currently-installed games (all clients,
                      not just Plutonium). Used to resolve sibling paths.
    on_progress     - optional callback(percent: int, status: str)
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    if game_key not in PLUT_GAME_KEYS:
        prog(100, f"Skipping {game_key}: not a Plutonium game.")
        return

    prog(10, f"LCD install for {game.get('name', game_key)}...")

    # 1. Sanity check: shared Plutonium install + login state
    shared_plut_dir = get_shared_plut_dir()
    if not is_plutonium_ready_lcd():
        raise RuntimeError(
            "Plutonium shared prefix is not ready. "
            "Expected storage/ inside " + shared_plut_dir + ". "
            "Did the bootstrapper login step complete successfully?"
        )

    # 2. Write config.json for all selected Plutonium games. Idempotent --
    #    called once per game during the install loop, but writes the same
    #    content every time so there's no harm.
    prog(30, "Writing Plutonium config.json in shared prefix...")
    selected_plut_keys = [
        k for k in installed_games.keys() if k in PLUT_GAME_KEYS
    ]
    _write_plutonium_config_lcd(
        shared_plut_dir, selected_plut_keys, installed_games,
        on_progress=lambda m: prog(35, m),
    )

    # 3. Per-game Heroic sideload entry + GamesConfig + Steam shortcut
    prog(50, "Registering game with HGL...")
    try:
        import config as _cfg
        ge_version = _cfg.get_ge_proton_version()
    except Exception:
        ge_version = None
    if not ge_version:
        ge_version = "GE-Proton10-34"

    setup_heroic_game(
        game_key, game, ge_version,
        plut_dir=shared_plut_dir,
        on_progress=lambda m: prog(75, m),
    )

    # 4. Metadata sentinel
    prog(95, "Saving metadata...")
    _write_metadata_lcd(game.get("install_dir", ""), {
        "game_key":   game_key,
        "plut_dir":   shared_plut_dir,
        "lcd_heroic": True,
    })

    prog(100, f"Plutonium ready for {game.get('name', game_key)}!")


def _write_lcd_launch_wrapper(game_key: str, app_name: str) -> str:
    """
    Write a per-game shell wrapper that wakes Heroic if needed and then
    launches the LCD Plutonium game via the heroic:// protocol.

    Returns the absolute path to the wrapper script.

    Background: Heroic Flatpak's Electron process can't register itself as
    the system handler for heroic:// URLs from inside the Flatpak sandbox
    (Heroic issues #1805, #2715, #4325, #5038, all open since 2022). When
    Heroic isn't running, firing a heroic:// URL via flatpak run silently
    no-ops -- which is why Steam shortcuts that point at flatpak directly
    instant-exit. The protocol URL only works reliably when Heroic is
    already running (per issue #2715), so the wrapper guarantees that
    invariant before firing the URL.

    The wrapper exec's the final flatpak invocation so Steam's process
    tree shows the game session correctly and Steam's Stop button kills
    the right thing.
    """
    os.makedirs(LCD_WRAPPER_DIR, exist_ok=True)
    wrapper_path = os.path.join(LCD_WRAPPER_DIR, f"plut_{game_key}.sh")

    script = f'''#!/bin/bash
# DeckOps LCD Plutonium launcher
# Auto-generated by heroic.py. Do not edit by hand.
set -u

APP_NAME="{app_name}"
HEROIC_FLATPAK="{HEROIC_FLATPAK_ID}"
LAUNCH_URI="heroic://launch?appName=${{APP_NAME}}&runner=sideload"

# Wake Heroic if it isn't already running. The heroic:// protocol URL
# only routes to a running Heroic instance -- firing it cold from a
# Flatpak invocation silently no-ops because Heroic can't register
# itself as the URL handler on SteamOS.
if ! pgrep -f "${{HEROIC_FLATPAK}}" >/dev/null 2>&1; then
    /usr/bin/flatpak run "${{HEROIC_FLATPAK}}" --no-gui --no-sandbox >/dev/null 2>&1 &
    # Poll for up to 15 seconds for Heroic to appear, then a 2s grace
    # period for its Electron IPC to come up after the process exists.
    for i in $(seq 1 30); do
        sleep 0.5
        if pgrep -f "${{HEROIC_FLATPAK}}" >/dev/null 2>&1; then
            sleep 2
            break
        fi
    done
fi

# Heroic is up. Hand it the protocol URL. exec replaces this shell so
# Steam's process tree tracks the game session correctly.
exec /usr/bin/flatpak run "${{HEROIC_FLATPAK}}" --no-gui --no-sandbox "${{LAUNCH_URI}}"
'''
    with open(wrapper_path, "w") as f:
        f.write(script)
    os.chmod(wrapper_path, 0o755)
    return wrapper_path


def _create_heroic_steam_shortcut(game_key: str, on_progress=None):
    """
    Create a non-Steam shortcut that launches a Heroic sideload game.

    The shortcut runs a per-game wrapper script that wakes Heroic if
    needed, then fires the heroic:// protocol URL. See
    _write_lcd_launch_wrapper for why a wrapper is required instead of
    invoking flatpak directly.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        return

    app_name = _heroic_app_name(game_key)
    game_def = HEROIC_PLUT_GAMES[game_key]
    title    = game_def["title"]

    # Per-game wrapper script that wakes Heroic before firing the URL
    wrapper_path = _write_lcd_launch_wrapper(game_key, app_name)
    exe_path = f'"{wrapper_path}"'
    launch_options = ""

    # Calculate appid from the quoted exe + title (Steam's algorithm)
    shortcut_appid = _calc_shortcut_appid(exe_path, title)

    uids = _find_all_steam_uids()
    if not uids:
        prog("  No Steam user accounts found - shortcut skipped.")
        return

    for uid in uids:
        shortcuts_path = os.path.join(USERDATA_DIR, uid, "config", "shortcuts.vdf")
        grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")

        existing_names = _read_existing_shortcuts(shortcuts_path)
        existing_raw = _read_shortcuts_raw(shortcuts_path)
        next_idx = _get_next_index(existing_raw)

        icon_path = os.path.join(grid_dir, f"{shortcut_appid}_icon.{game_def['icon_ext']}")

        if title in existing_names:
            prog(f"  Shortcut already exists: {title}")
        else:
            entry = {
                "appid":               _to_signed32(shortcut_appid),
                "AppName":             title,
                "Exe":                 exe_path,
                "StartDir":            f'"{os.path.dirname(wrapper_path)}"',
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
            try:
                _write_shortcuts_vdf(shortcuts_path, existing_raw, [entry_bytes])
                prog(f"  Steam shortcut created: {title}")
            except Exception as e:
                prog(f"  Failed to write shortcut: {e}")

        # Download artwork
        _download_artwork(grid_dir, shortcut_appid, game_def, prog)

        # Assign controller config
        try:
            import config as _cfg
            from controller_profiles import install_controller_config
            gyro_mode = _cfg.get_gyro_mode() or "hold"
            install_controller_config(
                uid, str(shortcut_appid),
                game_def["template_type"], gyro_mode,
            )
            prog(f"    Controller profile assigned")
        except Exception as ex:
            prog(f"    Controller profile failed: {ex}")

        # Set GE-Proton compat tool for the Steam shortcut
        # This tells Steam to use GE-Proton for any prefix operations,
        # though the actual game launch goes through Heroic's Proton.
        try:
            import config as _cfg
            from wrapper import set_compat_tool
            ge_version = _cfg.get_ge_proton_version()
            if ge_version:
                set_compat_tool([str(shortcut_appid)], ge_version)
                prog(f"    GE-Proton {ge_version} set on shortcut")
        except Exception as ex:
            prog(f"    Could not set GE-Proton on shortcut: {ex}")

    prog(f"  Shortcut appid: {shortcut_appid}")


def cleanup_heroic_game(game_key: str, on_progress=None):
    """
    Remove all Heroic-related artifacts for a game key.
    Called during uninstall to clean up LCD Plutonium installs.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog(f"Cleaning up Heroic entry for {game_key}...")

    _remove_heroic_sideload_entry(game_key, on_progress=on_progress)
    _remove_heroic_game_config(game_key, on_progress=on_progress)

    # Per-game launcher wrapper script
    wrapper = os.path.join(LCD_WRAPPER_DIR, f"plut_{game_key}.sh")
    if os.path.exists(wrapper):
        try:
            os.remove(wrapper)
            prog(f"  Removed launcher wrapper for {game_key}")
        except OSError as ex:
            prog(f"  Failed to remove launcher wrapper: {ex}")

    # TODO: remove the Steam shortcut from shortcuts.vdf
    # For now just log it - manual removal may be needed
    prog(f"  Note: Steam shortcut may need manual removal")


def cleanup_all_heroic(on_progress=None):
    """Remove all DeckOps-managed Heroic entries and state."""
    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog("Cleaning up all DeckOps Heroic entries...")

    # Per-game sideload entries + GamesConfig JSONs
    for game_key in HEROIC_PLUT_GAMES:
        cleanup_heroic_game(game_key, on_progress=on_progress)

    # Bootstrap sideload entry + GamesConfig
    library = _read_heroic_library()
    before = len(library["games"])
    library["games"] = [g for g in library["games"]
                        if g.get("app_name") != BOOTSTRAP_APP_NAME]
    if len(library["games"]) < before:
        _write_heroic_library(library)
        prog("  Removed bootstrap sideload entry")
    bootstrap_cfg = os.path.join(HEROIC_GAMES_CONFIG_DIR,
                                 f"{BOOTSTRAP_APP_NAME}.json")
    if os.path.exists(bootstrap_cfg):
        os.remove(bootstrap_cfg)
        prog("  Removed bootstrap GamesConfig")

    # Our copy of plutonium.exe under ~/Games/Heroic/deckops_plutonium/
    if os.path.isdir(DECKOPS_PLUT_DIR):
        shutil.rmtree(DECKOPS_PLUT_DIR)
        prog("  Removed DeckOps Plutonium directory")

    # Plutonium install inside the shared default prefix. The rest of the
    # shared prefix is left alone -- it may contain other sideloaded games
    # the user installed through Heroic themselves.
    shared_plut = get_shared_plut_dir()
    if os.path.isdir(shared_plut):
        shutil.rmtree(shared_plut)
        prog("  Removed Plutonium install from shared Heroic prefix")

    # Per-game launcher wrapper scripts dir
    if os.path.isdir(LCD_WRAPPER_DIR):
        shutil.rmtree(LCD_WRAPPER_DIR)
        prog("  Removed LCD launcher wrappers directory")

    # Legacy cleanup: old DeckOps versions (Fix #1.5) used per-game prefixes
    # under ~/.local/share/deckops/heroic_prefixes/. Wipe that dir if it
    # still exists so stale state doesn't confuse future installs.
    if os.path.isdir(HEROIC_PREFIX_BASE):
        shutil.rmtree(HEROIC_PREFIX_BASE)
        prog("  Removed legacy DeckOps Heroic prefix directory")

    prog("Heroic cleanup complete.")
