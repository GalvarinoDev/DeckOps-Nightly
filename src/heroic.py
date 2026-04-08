"""
heroic.py - Heroic Games Launcher integration for LCD Steam Deck

Manages Plutonium game launches through Heroic instead of Steam's Proton
runtime. LCD Steam Decks need this because Steam injects DLLs into Wine
prefixes that cause false flags with Plutonium's anti-cheat system.
Heroic's Flatpak version doesn't inject those DLLs.

This module:
  - Installs Heroic via Flatpak if not present
  - Grants Heroic filesystem access to game dirs
  - Writes sideload entries into Heroic's library.json
  - Writes per-game config (GE-Proton, prefix path, esync/fsync)
  - Creates Steam non-Steam shortcuts that launch via Heroic
  - Downloads artwork and assigns controller profiles to shortcuts
  - Provides cleanup for all Heroic-managed entries

OLED Decks do not use this module at all - they continue to use
Steam's Proton runtime directly via plutonium.py.
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

# Where Heroic puts its managed Wine prefixes for sideloaded games.
# DeckOps overrides this per-game so we control the prefix location.
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
# Each entry has the info needed to create a Heroic sideload entry and a
# Steam shortcut. Artwork URLs are placeholders from shortcut.py - will be
# replaced with Plutonium-branded art from SteamGridDB later.

HEROIC_PLUT_GAMES = {
    "t4sp": {
        "title":          "Plutonium: World at War",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10090/2bfb85222af4a01842baa5c3a16a080eb27ac6c3.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_hero_2x.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t4mp": {
        "title":          "Plutonium: World at War MP",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon/854d6fae5ee42911677c739ee1734486.png",
        "grid_url":       "https://cdn2.steamgriddb.com/grid/bb933c55afc6987ae406e48ff58786d6.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6a0076c7e1907a4555b17cc2a6ebc85.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e369853df766fa44e1ed0ff613f563bd.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/0a32bfcf5c87aa42d2a0367c1f6bb17c.png",
        "icon_ext": "png", "grid_ext": "png", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5sp": {
        "title":          "Plutonium: Black Ops",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42700/ea744d59efded3feaeebcafed224be9eadde90ac.jpg",
        "grid_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_600x900_2x.jpg",
        "wide_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/header.jpg",
        "hero_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_hero.jpg",
        "logo_url":       "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/logo_2x.png",
        "icon_ext": "jpg", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "t5mp": {
        "title":          "Plutonium: Black Ops MP",
        "template_type":  "standard",
        "icon_url":       "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42710/d595fb4b01201cade09e1232f2c41c0866840628.jpg",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/978f9d25644371a4c4b8df8c994cd880.png",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/a6330e9317a50ccf2d79c295dd18046f.png",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/dc82d632c9fcecb0778afbc7924494a6.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/dfb84a11f431c62436cfb760e30a34fe.png",
        "icon_ext": "jpg", "grid_ext": "png", "wide_ext": "png", "hero_ext": "png", "logo_ext": "png",
    },
    "t6mp": {
        "title":          "Plutonium: Black Ops II MP",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/715eb56d3f3b71792e230102d1da496d.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/7d3695ac5fbf55fb65ea261dd3a8577c.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/d841ee63e07b28f94920b81d2e4c21c9.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/731c83db8d2ff01bdc000083fd3c3740.png",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/6271faadeedd7626d661856b7a004e27.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "png", "logo_ext": "png",
    },
    "t6zm": {
        "title":          "Plutonium: Black Ops II Zombies",
        "template_type":  "standard",
        "icon_url":       "https://cdn2.steamgriddb.com/icon_thumb/743c11a9f3cb65cda4994bbdfb66c398.png",
        "grid_url":       "https://cdn2.steamgriddb.com/thumb/3d9ffc992e48d2aeb4b06f05471f619d.jpg",
        "wide_url":       "https://cdn2.steamgriddb.com/thumb/b87c4d009662bc436961d8f753a8de78.jpg",
        "hero_url":       "https://cdn2.steamgriddb.com/hero_thumb/e5e63da79fcd2bebbd7cb8bf1c1d0274.jpg",
        "logo_url":       "https://cdn2.steamgriddb.com/logo_thumb/79514e888b8f2acacc68738d0cbb803e.png",
        "icon_ext": "png", "grid_ext": "jpg", "wide_ext": "jpg", "hero_ext": "jpg", "logo_ext": "png",
    },
    "iw5mp": {
        "title":          "Plutonium: Modern Warfare 3 MP",
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

    # Each game gets its own prefix under the DeckOps heroic prefix dir.
    # This keeps Heroic prefixes completely separate from Steam's compatdata.
    prefix_path = os.path.join(HEROIC_PREFIX_BASE, game_key)

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

    # Also clean up the prefix if it exists
    prefix_path = os.path.join(HEROIC_PREFIX_BASE, game_key)
    if os.path.isdir(prefix_path):
        shutil.rmtree(prefix_path)
        prog(f"  Removed Heroic prefix for {game_key}")


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


# ── Public API ──────────────────────────────────────────────────────────────

def setup_heroic_game(game_key: str, game: dict, ge_proton_version: str,
                       plut_dir: str, on_progress=None):
    """
    Set up a single Plutonium game to launch through Heroic on LCD.

    This is the main entry point called from plutonium.py for LCD installs.
    It does everything needed to make the game launchable from Steam Game Mode
    via Heroic, without Steam's DLL injection.

    game_key          - one of t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    game              - dict with at least install_dir and name
    ge_proton_version - e.g. "GE-Proton10-34"
    plut_dir          - path to the Plutonium dir inside the Heroic prefix
                        (not yet created - will be populated by plutonium.py)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        prog(f"Unknown game key for Heroic: {game_key}")
        return

    install_dir = game.get("install_dir", "")
    game_def = HEROIC_PLUT_GAMES[game_key]

    # The Plutonium launcher exe will live inside the Heroic-managed prefix.
    # We point Heroic at it even though it won't exist until Plutonium files
    # are copied in. Heroic doesn't validate the exe path at config time.
    launcher_exe = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")

    prog(f"Setting up Heroic for {game_def['title']}...")

    # 1. Grant Heroic filesystem access to this game's directory
    _grant_heroic_filesystem_access([install_dir], on_progress=on_progress)

    # 2. Write sideload entry in library.json
    _add_heroic_sideload_entry(game_key, launcher_exe, install_dir,
                                on_progress=on_progress)

    # 3. Write per-game config (GE-Proton, prefix, etc.)
    _write_heroic_game_config(game_key, ge_proton_version,
                               on_progress=on_progress)

    # 4. Create Steam shortcut that launches via Heroic protocol
    _create_heroic_steam_shortcut(game_key, on_progress=on_progress)

    prog(f"Heroic setup complete for {game_def['title']}")


def _create_heroic_steam_shortcut(game_key: str, on_progress=None):
    """
    Create a non-Steam shortcut that launches a Heroic sideload game.

    The shortcut runs:
      /usr/bin/flatpak run com.heroicgameslauncher.hgl --no-gui --no-sandbox
        "heroic://launch?appName=<app_name>&runner=sideload"

    This is the same format Heroic uses when you click "Add to Steam".
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in HEROIC_PLUT_GAMES:
        return

    app_name = _heroic_app_name(game_key)
    game_def = HEROIC_PLUT_GAMES[game_key]
    title    = game_def["title"]

    # The exe for the Steam shortcut is flatpak itself
    exe_path = '"/usr/bin/flatpak"'
    launch_options = (
        f'run {HEROIC_FLATPAK_ID} --no-gui --no-sandbox '
        f'"heroic://launch?appName={app_name}&runner=sideload"'
    )

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
                "StartDir":            '"/home/deck"',
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


def get_heroic_prefix_plut_dir(game_key: str) -> str:
    """
    Return the Plutonium/ folder path that will exist inside the
    Heroic-managed prefix for a given game key.

    This is where plutonium.py should copy Plutonium files to for LCD.
    The prefix won't exist until Heroic creates it on first launch,
    but we pre-create the directory structure.
    """
    prefix_path = os.path.join(HEROIC_PREFIX_BASE, game_key)
    plut_dir = os.path.join(
        prefix_path, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )
    os.makedirs(plut_dir, exist_ok=True)
    return plut_dir


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

    # TODO: remove the Steam shortcut from shortcuts.vdf
    # For now just log it - manual removal may be needed
    prog(f"  Note: Steam shortcut may need manual removal")


def cleanup_all_heroic(on_progress=None):
    """Remove all DeckOps-managed Heroic entries and prefixes."""
    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog("Cleaning up all DeckOps Heroic entries...")

    for game_key in HEROIC_PLUT_GAMES:
        cleanup_heroic_game(game_key, on_progress=on_progress)

    # Remove the shared prefix base directory
    if os.path.isdir(HEROIC_PREFIX_BASE):
        shutil.rmtree(HEROIC_PREFIX_BASE)
        prog("  Removed DeckOps Heroic prefix directory")

    prog("Heroic cleanup complete.")
