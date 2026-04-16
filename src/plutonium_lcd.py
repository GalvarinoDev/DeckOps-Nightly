"""
plutonium_lcd.py - LCD Plutonium install path (Heroic Games Launcher)

LCD Steam Decks can't launch Plutonium through Steam's Proton runtime
due to LCD compatibility issues. Heroic's Flatpak version doesn't have
this problem, so LCD users route their Plutonium games through Heroic.

This module owns the full LCD install flow -- it is the LCD counterpart
to plutonium_oled.py. plutonium_oled.py's install_plutonium dispatches
to install_plutonium_lcd at the top of the function when running on LCD.

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

OLED Decks do not use this module at all -- plutonium_oled.py handles OLED
directly through Steam's Proton runtime and a bash wrapper per game.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
import urllib.request

from shortcut import add_shortcut, remove_shortcut


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

# Legacy: per-game launcher wrapper scripts from prior iterations.
# New installs use Heroic's native shortcut pattern (Exe="flatpak",
# LaunchOptions="run ... --no-gui ...") and don't create wrappers.
# This constant is kept so cleanup_heroic_game / cleanup_all_heroic
# can remove stale wrappers from older installs.
LCD_WRAPPER_DIR = os.path.expanduser("~/.local/share/deckops/lcd_wrappers")

PLUT_BOOTSTRAPPER_URL = "https://cdn.plutonium.pw/updater/plutonium.exe"

# Deterministic sideload app_name for the one-off login entry. Not hashed
# so it's easy to spot in Heroic's library if testers need to debug.
BOOTSTRAP_APP_NAME = "do_plut_bootstrap"
BOOTSTRAP_TITLE    = "DeckOps Plutonium Setup"

# Map each Plutonium game key to the config.json path field Plutonium uses
# for that game's install directory. Mirrors plutonium_oled.GAME_META so
# plutonium_lcd.py doesn't have to import from plutonium_oled.py.
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

# Map game key to (appid, exe name). Used by the LCD offline wrapper to know
# which exe to replace and which appid to look up for compatdata. Mirrors
# the relevant fields from plutonium.GAME_META.
PLUT_GAME_EXES = {
    "t4sp":  (10090,  "CoDWaW.exe"),
    "t4mp":  (10090,  "CoDWaWmp.exe"),
    "t5sp":  (42700,  "BlackOps.exe"),
    "t5mp":  (42710,  "BlackOpsMP.exe"),
    "t6zm":  (212910, "t6zm.exe"),
    "t6mp":  (202990, "t6mp.exe"),
    "iw5mp": (42690,  "iw5mp.exe"),
}

# Standalone wrapper exe names for LCD own games. These are new files
# dropped into the game folder -- the original exe is left untouched.
# shortcut.py points the non-Steam shortcut at these.
LCD_OWN_WRAPPER_EXES = {
    "t4sp":  "t4plutsp.exe",
    "t4mp":  "t4plutmp.exe",
    "t5sp":  "t5plutsp.exe",
    "t5mp":  "t5plutmp.exe",
    "t6mp":  "t6plutmp.exe",
    "t6zm":  "t6plutzm.exe",
    "iw5mp": "iw5plutmp.exe",
}

# Sidecar -lan wrapper script names for LCD own game offline mode.
# LCD Steam games use the replaced exe as their lan path (already written
# by _write_lcd_wrapper). Own games get a separate sidecar here.
LCD_LAN_WRAPPER_NAMES = {
    "t4sp":  "t4plut_lan.sh",
    "t4mp":  "t4plut_lan.sh",
    "t5sp":  "t5plut_lan.sh",
    "t5mp":  "t5plut_lan.sh",
    "t6mp":  "t6plut_lan.sh",
    "t6zm":  "t6plut_lan.sh",
    "iw5mp": "iw5plut_lan.sh",
}

# Shared Plutonium directories (bin/, launcher/, games/) live here. One real
# copy shared across all prefixes via symlinks. Same location as plutonium_oled.py
# uses for OLED so LCD and OLED share the same shared dir if both are present.
SHARED_PLUT_DIR = os.path.expanduser("~/.local/share/deckops/plutonium_shared")
_PLUT_SHARED_SUBDIRS = ("bin", "launcher", "games")


# Where Heroic puts its managed Wine prefixes for sideloaded games when
# DeckOps overrides the per-game winePrefix. Kept as a legacy constant for
# migration cleanup (old DeckOps installs created per-game prefixes here).
# Shape A uses HEROIC_DEFAULT_WINE_PREFIX instead.
HEROIC_PREFIX_BASE = os.path.expanduser(
    "~/.local/share/deckops/heroic_prefixes"
)


# ── Steam paths (same as shortcut.py) ───────────────────────────────────────

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


# ── LCD Shape A helpers ─────────────────────────────────────────────────────
# Everything below powers the LCD Plutonium install flow. plutonium_oled.py's
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
    """Convert a Linux path to Wine Z: drive notation (same as plutonium_oled.py)."""
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
    Mirrors plutonium_oled._write_metadata so plutonium_lcd.py doesn't need
    to import private helpers from plutonium_oled.py.
    """
    if not install_dir:
        return
    path = os.path.join(install_dir, "deckops_plutonium.json")
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ── LCD offline mode ─────────────────────────────────────────────────────────
# After the Heroic bootstrapper login, we copy Plutonium files from the shared
# Heroic prefix into each game's Steam compatdata prefix and write a -lan bash
# wrapper. This gives LCD users offline play from their normal Steam library
# entries without needing Heroic at runtime.

def _ensure_shared_plutonium_lcd(src_plut_dir: str, on_progress=None) -> bool:
    """
    Ensure the shared Plutonium directory has current copies of bin/,
    launcher/, and games/ from the Heroic shared prefix.

    Same pattern as plutonium._ensure_shared_plutonium but sources from
    the Heroic prefix instead of the OLED dedicated prefix. Both write
    to the same SHARED_PLUT_DIR so they share the cache.

    Returns True if shared dirs are ready, False on failure.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    all_present = True
    for subdir in _PLUT_SHARED_SUBDIRS:
        src = os.path.join(src_plut_dir, subdir)
        dst = os.path.join(SHARED_PLUT_DIR, subdir)
        if not os.path.isdir(src):
            continue
        if not os.path.isdir(dst):
            all_present = False
            break
        src_count = sum(1 for _ in os.scandir(src))
        dst_count = sum(1 for _ in os.scandir(dst))
        if dst_count < src_count:
            all_present = False
            break

    if all_present and os.path.isdir(SHARED_PLUT_DIR):
        prog("  Shared Plutonium dirs verified")
        return True

    prog("  Setting up shared Plutonium directories from Heroic prefix...")
    start = time.time()

    try:
        os.makedirs(SHARED_PLUT_DIR, exist_ok=True)
        for subdir in _PLUT_SHARED_SUBDIRS:
            src = os.path.join(src_plut_dir, subdir)
            dst = os.path.join(SHARED_PLUT_DIR, subdir)
            if not os.path.isdir(src):
                continue
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        elapsed = time.time() - start
        prog(f"  Shared Plutonium dirs ready ({elapsed:.1f}s)")
        return True
    except Exception as ex:
        prog(f"  Shared Plutonium setup failed: {ex}")
        return False


def _copy_plut_to_game_prefix_lcd(src_plut_dir: str, dest_plut_dir: str,
                                    on_progress=None):
    """
    Copy Plutonium files into a game's Steam compatdata prefix for LCD
    offline mode. Uses symlinks for shared dirs (bin/, launcher/, games/)
    and real copies for storage/ (per-game data).

    Same logic as plutonium._copy_plut_to_prefix.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog(f"  Copying Plutonium: {src_plut_dir} -> {dest_plut_dir}")

    if os.path.exists(dest_plut_dir):
        prog(f"  Removing existing Plutonium at {dest_plut_dir}...")
        shutil.rmtree(dest_plut_dir)

    start = time.time()

    # Check if shared dirs are available for symlink approach
    shared_ready = all(
        os.path.isdir(os.path.join(SHARED_PLUT_DIR, d))
        for d in _PLUT_SHARED_SUBDIRS
        if os.path.isdir(os.path.join(src_plut_dir, d))
    )

    if shared_ready:
        os.makedirs(dest_plut_dir, exist_ok=True)

        # Symlink shared directories
        for subdir in _PLUT_SHARED_SUBDIRS:
            shared_src = os.path.join(SHARED_PLUT_DIR, subdir)
            dest_sub = os.path.join(dest_plut_dir, subdir)
            if os.path.isdir(shared_src):
                os.symlink(shared_src, dest_sub)

        # Copy storage/ as real files (per-game data)
        storage_src = os.path.join(src_plut_dir, "storage")
        if os.path.isdir(storage_src):
            storage_dst = os.path.join(dest_plut_dir, "storage")
            shutil.copytree(storage_src, storage_dst)

        # Copy any remaining top-level files (config, etc.)
        for item in os.listdir(src_plut_dir):
            src_item = os.path.join(src_plut_dir, item)
            dst_item = os.path.join(dest_plut_dir, item)
            if os.path.exists(dst_item):
                continue  # already handled (symlink or storage)
            if os.path.isfile(src_item):
                shutil.copy2(src_item, dst_item)

        elapsed = time.time() - start
        prog(f"  Copied Plutonium with symlinks ({elapsed:.1f}s)")
    else:
        # Fallback: full copy if shared dirs not available
        shutil.copytree(src_plut_dir, dest_plut_dir)
        elapsed = time.time() - start
        prog(f"  Copied Plutonium ({elapsed:.1f}s)")


def _write_lcd_config(plut_dir: str, game_key: str, installed_games: dict):
    """
    Write config.json inside a game prefix's Plutonium dir with the correct
    game install paths. Same as plutonium_oled._write_config but uses
    plutonium_lcd's own PLUT_CONFIG_KEYS and _wine_path_lcd.
    """
    config_path = os.path.join(plut_dir, "config.json")

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Write paths for all keys that share this appid so sibling games
    # (e.g. t4sp + t4mp both on appid 10090) get their paths too
    if game_key in PLUT_GAME_EXES:
        target_appid = PLUT_GAME_EXES[game_key][0]
        for key, (appid, _) in PLUT_GAME_EXES.items():
            if appid == target_appid:
                game = installed_games.get(key, {})
                install_dir = game.get("install_dir", "")
                if install_dir and key in PLUT_CONFIG_KEYS:
                    data[PLUT_CONFIG_KEYS[key]] = _wine_path_lcd(install_dir)

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


def _write_lcd_wrapper(game: dict, game_key: str, steam_root: str,
                        proton_path: str, compatdata_path: str,
                        plut_dir: str):
    """
    Replace the game exe with a bash wrapper that launches Plutonium in
    offline LAN mode through Proton. LCD only.

    Calls plutonium-bootstrapper-win32.exe directly with -lan flag. No
    Plutonium account needed, game starts in offline LAN mode. The
    bootstrapper needs to be run from the Plutonium directory so it can
    find its files relative to cwd.

    The original exe is backed up as <exe>.bak. The wrapper is padded to
    the original file's size so Steam's file validation does not flag it.
    """
    if game_key not in PLUT_GAME_EXES:
        return

    install_dir = game["install_dir"]
    _, exe_name = PLUT_GAME_EXES[game_key]
    exe_path    = os.path.join(install_dir, exe_name)
    backup_path = exe_path + ".bak"

    # Read original size before we overwrite
    original_size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0

    # Back up original exe
    if not os.path.exists(backup_path) and os.path.exists(exe_path):
        shutil.copy2(exe_path, backup_path)
        original_size = os.path.getsize(backup_path)

    try:
        import config as _cfg
        player_name = _cfg.get_player_name() or "Player"
    except Exception:
        player_name = "Player"

    bootstrapper = os.path.join(plut_dir, "bin",
                                "plutonium-bootstrapper-win32.exe")
    game_dir_wine = _wine_path_lcd(install_dir)

    script = (
        "#!/bin/bash\n"
        f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
        f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
        f"cd \"{plut_dir}\"\n"
        f"exec \"{proton_path}\" run \"{bootstrapper}\" "
        f"{game_key} \"{game_dir_wine}\" +name \"{player_name}\" -lan\n"
    )

    script_bytes = script.encode("utf-8")
    if original_size > len(script_bytes):
        script_bytes += b"\x00" * (original_size - len(script_bytes))

    with open(exe_path, "wb") as f:
        f.write(script_bytes)

    os.chmod(exe_path, os.stat(exe_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# LCD own games launch via Heroic shortcuts created in
# _create_heroic_steam_shortcut — no standalone wrapper needed.
# def _write_lcd_own_wrapper(game: dict, game_key: str, steam_root: str,
#                             proton_path: str, compatdata_path: str,
#                             plut_dir: str) -> str | None:
#     """
#     Write a standalone wrapper exe for LCD own games.
#
#     Same -lan bash script as _write_lcd_wrapper but written as a new file
#     (e.g. t4plutmp.exe) instead of replacing the original game exe.
#     No backup, no padding -- the original exe is left untouched.
#     shortcut.py points the non-Steam shortcut at this wrapper.
#
#     Returns the full path to the written wrapper, or None if game_key
#     is not in LCD_OWN_WRAPPER_EXES.
#     """
#     if game_key not in LCD_OWN_WRAPPER_EXES:
#         return None
#
#     install_dir  = game["install_dir"]
#     wrapper_name = LCD_OWN_WRAPPER_EXES[game_key]
#     wrapper_path = os.path.join(install_dir, wrapper_name)
#
#     try:
#         import config as _cfg
#         player_name = _cfg.get_player_name() or "Player"
#     except Exception:
#         player_name = "Player"
#
#     bootstrapper  = os.path.join(plut_dir, "bin",
#                                  "plutonium-bootstrapper-win32.exe")
#     game_dir_wine = _wine_path_lcd(install_dir)
#
#     script = (
#         "#!/bin/bash\n"
#         f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
#         f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
#         f"cd \"{plut_dir}\"\n"
#         f"exec \"{proton_path}\" run \"{bootstrapper}\" "
#         f"{game_key} \"{game_dir_wine}\" +name \"{player_name}\" -lan\n"
#     )
#
#     with open(wrapper_path, "wb") as f:
#         f.write(script.encode("utf-8"))
#
#     os.chmod(wrapper_path, os.stat(wrapper_path).st_mode |
#              stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
#
#     return wrapper_path


def _write_lcd_lan_wrapper(game: dict, game_key: str, steam_root: str,
                            proton_path: str, compatdata_path: str,
                            plut_dir: str) -> str | None:
    """
    Write a sidecar -lan bash script for LCD own game offline mode.

    Creates a new shell script (e.g. t4plut_lan.sh) alongside the game
    files. Never replaces or modifies any existing file. launcher_plut.py
    reads the path from config and calls bash on it for offline play.

    Only used for own games. LCD Steam games use the replaced game exe
    (written by _write_lcd_wrapper) as their lan_wrapper_path.

    Returns the full path to the written script, or None if game_key
    is not in LCD_LAN_WRAPPER_NAMES.
    """
    if game_key not in LCD_LAN_WRAPPER_NAMES:
        return None

    install_dir  = game["install_dir"]
    wrapper_name = LCD_LAN_WRAPPER_NAMES[game_key]
    wrapper_path = os.path.join(install_dir, wrapper_name)

    try:
        import config as _cfg
        player_name = _cfg.get_player_name() or "Player"
    except Exception:
        player_name = "Player"

    bootstrapper  = os.path.join(plut_dir, "bin",
                                  "plutonium-bootstrapper-win32.exe")
    game_dir_wine = _wine_path_lcd(install_dir)

    script = (
        "#!/bin/bash\n"
        f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
        f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
        f"cd \"{plut_dir}\"\n"
        f"exec \"{proton_path}\" run \"{bootstrapper}\" "
        f"{game_key} \"{game_dir_wine}\" +name \"{player_name}\" -lan\n"
    )

    with open(wrapper_path, "wb") as f:
        f.write(script.encode("utf-8"))

    os.chmod(wrapper_path, os.stat(wrapper_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return wrapper_path


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
                      plut_dir=None, on_progress=None, source: str = "steam"):
    """
    Set up a single Plutonium game to launch through Heroic on LCD.

    This is called from install_plutonium_lcd once per selected game.
    It writes the per-game Heroic sideload entry, per-game GamesConfig
    (with winePrefix pointed at the shared default prefix and
    launcherArgs set to plutonium://play/<game_key>), and the matching
    Steam non-Steam shortcut that launches via the heroic:// protocol.

    Steam shortcuts are only created for own games -- Steam game owners
    already have library entries with -lan wrappers.

    game_key          - one of t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    game              - dict with at least install_dir and name
    ge_proton_version - e.g. "GE-Proton10-34"
    plut_dir          - deprecated / ignored. Shape A always targets the
                        shared default Heroic prefix, so the launcher exe
                        path is computed from get_shared_plut_dir().
                        Parameter kept so older call sites don't break.
    source            - "steam" or "own" -- controls whether shortcuts are created
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
    _create_heroic_steam_shortcut(game_key, on_progress=on_progress,
                                   source=source)

    prog(f"Heroic setup complete for {game_def['title']}")


def _set_heroic_minimize_on_launch(on_progress=None):
    """
    Set Heroic's defaultSettings.minimizeOnLaunch to true in its config.json
    so the Heroic main window minimizes itself the moment it starts a game.
    This cuts the "Heroic visible for 10 seconds" cosmetic flash when a
    DeckOps LCD shortcut fires the heroic:// URL.

    Idempotent. Safe to call every install. Handles missing config file
    gracefully. Does NOT touch any setting other than minimizeOnLaunch.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    config_path = os.path.expanduser(
        "~/.var/app/com.heroicgameslauncher.hgl/config/heroic/config.json"
    )

    if not os.path.exists(config_path):
        prog("  Heroic config.json not present yet; skipping minimize setting")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as ex:
        prog(f"  Could not read Heroic config.json: {ex}")
        return

    if not isinstance(data, dict):
        prog("  Heroic config.json has unexpected shape; skipping")
        return

    default_settings = data.get("defaultSettings")
    if not isinstance(default_settings, dict):
        default_settings = {}
        data["defaultSettings"] = default_settings

    if default_settings.get("minimizeOnLaunch") is True:
        prog("  Heroic minimizeOnLaunch already true")
        return

    default_settings["minimizeOnLaunch"] = True

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        prog("  Heroic minimizeOnLaunch set to true")
    except OSError as ex:
        prog(f"  Could not write Heroic config.json: {ex}")


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

    # 2b. Ensure Heroic minimizes its main window when launching games,
    #     so the Heroic window doesn't flash for ~10s every time a
    #     DeckOps LCD shortcut fires the heroic:// URL in Game Mode.
    _set_heroic_minimize_on_launch(on_progress=lambda m: prog(12, m))

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
                           on_progress=None,
                           steam_root: str = None,
                           proton_path: str = None,
                           compatdata_path: str = None,
                           source: str = "steam"):
    """
    LCD per-game Plutonium install. Called from plutonium.install_plutonium
    via the early LCD dispatch at the top of that function.

    Flow:
      1. Verify the shared Heroic prefix is ready (user logged in, storage
         populated) -- raises if not.
      2. Write Plutonium's config.json inside the shared prefix with all
         selected Plutonium games' install paths. Idempotent across calls.
      3. Register per-game Heroic sideload entry + GamesConfig (kept for
         future online play through ManagementScreen).
      4. Set up shared Plutonium directories for symlink-based copies.
      5. Copy Plutonium files into the game's Steam compatdata prefix.
      6. Write config.json in the game prefix with correct paths.
      7. Write a -lan bash wrapper for Steam games (exe replacement).
         Own games launch via Heroic shortcuts created in step 3.
     7b. Set Heroic launch options on the Steam library entry for online
         play. The -lan wrapper is kept for offline mode via the launcher.
         t4mp excluded (shares appid) — gets a non-Steam shortcut instead.
      8. Write the DeckOps metadata sentinel.

    game            - entry from detect_games.find_installed_games()
    game_key        - one of: t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    installed_games - full dict of currently-installed games (all clients,
                      not just Plutonium). Used to resolve sibling paths.
    on_progress     - optional callback(percent: int, status: str)
    steam_root      - path to Steam root (forwarded from plutonium.install_plutonium)
    proton_path     - path to the proton executable
    compatdata_path - path to this game's compatdata prefix
    source          - "steam" or "own" -- controls wrapper type
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    if game_key not in PLUT_GAME_KEYS:
        prog(100, f"Skipping {game_key}: not a Plutonium game.")
        return

    prog(5, f"LCD install for {game.get('name', game_key)}...")

    # 1. Sanity check: shared Plutonium install + login state
    shared_plut_dir = get_shared_plut_dir()
    if not is_plutonium_ready_lcd():
        raise RuntimeError(
            "Plutonium shared prefix is not ready. "
            "Expected storage/ inside " + shared_plut_dir + ". "
            "Did the bootstrapper login step complete successfully?"
        )

    # 2. Write config.json for all selected Plutonium games in the shared
    #    Heroic prefix. Idempotent -- called once per game during the install
    #    loop, but writes the same content every time so there's no harm.
    prog(15, "Writing Plutonium config.json in shared prefix...")
    selected_plut_keys = [
        k for k in installed_games.keys() if k in PLUT_GAME_KEYS
    ]
    _write_plutonium_config_lcd(
        shared_plut_dir, selected_plut_keys, installed_games,
        on_progress=lambda m: prog(20, m),
    )

    # 3. Per-game Heroic sideload entry + GamesConfig (kept for future
    #    online play through ManagementScreen -- Steam shortcuts are
    #    disabled via _create_heroic_steam_shortcut early return)
    prog(25, "Registering game with HGL...")
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
        on_progress=lambda m: prog(30, m),
        source=source,
    )

    # 4. Set up shared Plutonium directories from the Heroic prefix
    prog(35, "Setting up shared Plutonium directories...")
    _ensure_shared_plutonium_lcd(
        shared_plut_dir,
        on_progress=lambda m: prog(40, m),
    )

    # 5. Copy Plutonium into this game's Steam compatdata prefix
    wrapper_path = None
    if compatdata_path:
        dest_plut_dir = os.path.join(
            compatdata_path, "pfx", "drive_c", "users", "steamuser",
            "AppData", "Local", "Plutonium",
        )
        prog(50, f"Copying Plutonium into prefix for {game.get('name', game_key)}...")
        _copy_plut_to_game_prefix_lcd(
            shared_plut_dir, dest_plut_dir,
            on_progress=lambda m: prog(60, m),
        )

        # 6. Write config.json in the game prefix with correct paths
        prog(70, "Writing game path config...")
        _write_lcd_config(dest_plut_dir, game_key, installed_games)

        # 7. Write bash wrapper for Steam-owned games (exe replacement).
        #    Own games launch via Heroic shortcuts created in step 3
        #    (_create_heroic_steam_shortcut) — no wrapper needed.
        lan_wrapper_path = None
        if source == "own":
            prog(80, "Own game — writing offline LAN wrapper...")
            lan_wrapper_path = _write_lcd_lan_wrapper(
                game, game_key, steam_root, proton_path,
                compatdata_path, shared_plut_dir,
            )
        elif proton_path and steam_root:
            prog(80, "Writing offline launcher wrapper...")
            _write_lcd_wrapper(
                game, game_key, steam_root, proton_path,
                compatdata_path, dest_plut_dir,
            )
            # The replaced exe IS the lan wrapper for Steam games.
            # Capture the path so the launcher can find it.
            if game_key in PLUT_GAME_EXES:
                _, exe_name = PLUT_GAME_EXES[game_key]
                lan_wrapper_path = os.path.join(
                    game["install_dir"], exe_name
                )
        else:
            prog(80, "Skipping wrapper -- missing proton_path or steam_root")

        # 7b. Set Heroic launch options on the Steam library entry so the
        #     game launches online through Heroic. The -lan wrapper from
        #     step 7 stays in place for offline mode via the Plutonium
        #     launcher. t4mp is excluded (shares appid with t4sp) and gets
        #     a non-Steam shortcut in shortcut.py instead.
        if source == "steam" and steam_root:
            prog(85, "Setting Heroic launch options...")
            _set_heroic_steam_launch_options(
                game_key, steam_root,
                on_progress=lambda m: prog(87, m),
            )
    else:
        prog(50, "Skipping prefix copy -- no compatdata_path provided")

    # 8. Metadata sentinel
    prog(95, "Saving metadata...")
    meta = {
        "game_key":   game_key,
        "plut_dir":   shared_plut_dir,
        "lcd_heroic": True,
    }
    if wrapper_path:
        meta["wrapper_path"] = wrapper_path
    _write_metadata_lcd(game.get("install_dir", ""), meta)

    import config as _cfg_lcd
    _cfg_lcd.mark_game_setup(
        game_key, "plutonium", source=source,
        lan_wrapper_path=lan_wrapper_path if compatdata_path else None,
    )

    prog(100, f"Plutonium ready for {game.get('name', game_key)}!")
    return wrapper_path


def _set_heroic_steam_launch_options(game_key: str, steam_root: str,
                                      on_progress=None):
    """
    Set launch options on a Steam library entry so it launches through
    Heroic instead of Steam's Proton runtime. LCD only.

    Steam's pinned runtime libraries conflict with the system flatpak
    binary, so LD_PRELOAD is required to override libcurl. The #%command%
    suffix comments out the original game exe so Steam doesn't try to
    launch it through Proton.

    The -lan wrapper written by step 7 is left in place for offline mode
    via the Plutonium launcher.

    Only called for Steam-owned games (not own). t4mp is excluded because
    it shares appid 10090 with t4sp and gets a non-Steam shortcut instead.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in PLUT_GAME_EXES:
        return
    if game_key == "t4mp":
        # t4mp shares appid 10090 with t4sp — handled via non-Steam shortcut
        return

    appid = str(PLUT_GAME_EXES[game_key][0])
    app_name = _heroic_app_name(game_key)

    launch_opts = (
        f'LD_PRELOAD=/usr/lib/libcurl.so.4 '
        f'/usr/bin/flatpak run {HEROIC_FLATPAK_ID} --no-gui --no-sandbox '
        f'"heroic://launch?appName={app_name}&runner=sideload" '
        f'#%command%'
    )

    try:
        from wrapper import set_launch_options, clear_compat_tool
        set_launch_options(steam_root, appid, launch_opts)
        prog(f"  Heroic launch options set for appid {appid}")
        # Steam wraps any launch with a CompatToolMapping entry inside Steam
        # Linux Runtime (sniper). From inside that container the host's
        # flatpak binary is invisible, so the flatpak invocation in the
        # launch options above fails and the launch flash-closes. Heroic
        # owns the Proton invocation downstream, so the Steam-side compat
        # tool must be cleared. _apply_compat() in ui_qt earlier in the
        # install set GE-Proton on every MANAGED_APPID including this one;
        # this undoes it for the LCD flatpak-launching games.
        try:
            clear_compat_tool([appid])
            prog(f"  Compat tool cleared for appid {appid} (LCD flatpak path)")
        except Exception as ex:
            prog(f"  Could not clear compat tool for appid {appid}: {ex}")
    except Exception as ex:
        prog(f"  Could not set Heroic launch options for appid {appid}: {ex}")


def _create_heroic_steam_shortcut(game_key: str, on_progress=None,
                                   source: str = "steam"):
    """
    Create a non-Steam shortcut that launches an LCD Plutonium game using
    HGL's native shortcut pattern. Delegates to shortcut.add_shortcut for
    all VDF, artwork, and controller config work.

    Only creates shortcuts for own games. LCD Steam game owners already have
    their games in the Steam library with wrappers replacing the exe,
    so they don't need additional HGL shortcuts cluttering their library.
    Online play for Steam owners will be handled through ManagementScreen
    in a future update.
    """
    # Steam game owners don't need HGL shortcuts -- their games launch
    # from existing Steam library entries with wrappers
    if source != "own":
        return

    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        return

    game_def = HEROIC_PLUT_GAMES[game_key]
    title    = game_def["title"]

    # HGL native shortcut pattern: Exe is the full path to flatpak,
    # StartDir is /usr/bin/, the entire heroic:// invocation lives in
    # LaunchOptions. This matches exactly what HGL writes when the user
    # clicks "Add to Steam" from its own UI, which is the pattern Steam
    # reliably resolves. Using a bare "flatpak" word caused Steam to
    # misidentify the shortcut appid in some cases, breaking artwork,
    # controller configs, and launch.
    app_name = _heroic_app_name(game_key)
    exe_path  = '"/usr/bin/flatpak"'
    start_dir = '"/usr/bin/"'
    launch_options = (
        f'run {HEROIC_FLATPAK_ID} --no-gui --no-sandbox '
        f'"heroic://launch?appName={app_name}&runner=sideload"'
    )

    # Get gyro mode for controller config assignment
    try:
        import config as _cfg
        gyro_mode = _cfg.get_gyro_mode() or "hold"
    except Exception:
        gyro_mode = "hold"

    # NOTE: the quoted exe path produces a different appid than the old bare
    # "flatpak" pattern. Existing shortcuts written by older DeckOps installs
    # will orphan on the old appid. Testers should fully uninstall and
    # reinstall to get clean shortcuts with the correct appid.
    #
    # LCD Plutonium shortcuts must NOT have a Steam compat tool set. Steam
    # wraps any non-Steam shortcut that has a compat tool inside Steam Linux
    # Runtime (sniper). From inside that container the host's flatpak binary
    # is invisible, so the "flatpak run ..." invocation fails. HGL owns the
    # Proton invocation downstream, so the Steam-side compat tool is not just
    # unnecessary -- it actively breaks the launch.
    add_shortcut(
        name=title,
        exe_path=exe_path,
        start_dir=start_dir,
        launch_options=launch_options,
        artwork_def=game_def,
        template_type=game_def["template_type"],
        gyro_mode=gyro_mode,
        on_progress=on_progress,
        clear_compat_tool=True,
    )


def _remove_heroic_steam_shortcut(game_key: str, on_progress=None):
    """
    Remove the DeckOps Steam shortcut for an HGL LCD game.
    Delegates to shortcut.remove_shortcut for all VDF and artwork cleanup.

    Uses the same exe_path and title that were used during install so the
    appid calculation matches exactly what was written.
    """
    if game_key not in HEROIC_PLUT_GAMES:
        return

    game_def = HEROIC_PLUT_GAMES[game_key]
    title    = game_def["title"]

    # Must match _create_heroic_steam_shortcut exactly
    exe_path = '"/usr/bin/flatpak"'

    remove_shortcut(
        name=title,
        exe_path=exe_path,
        artwork_def=game_def,
        on_progress=on_progress,
    )


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

    # Remove the Steam shortcut from shortcuts.vdf for all discovered UIDs.
    # Uses the same exe_path/title the shortcut was written with so the
    # appid calculation matches exactly what was written during install.
    _remove_heroic_steam_shortcut(game_key, on_progress=on_progress)


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
