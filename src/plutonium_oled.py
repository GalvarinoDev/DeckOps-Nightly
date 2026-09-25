"""
plutonium_oled.py - DeckOps installer for Plutonium (OLED / Other path)
(Call of Duty: MW3, World at War, Black Ops, Black Ops II)

LCD Decks are dispatched to plutonium_lcd.py early in
install_plutonium(). Everything below the LCD dispatch handles both
OLED and Other (non-Deck SteamOS) devices, which share the same
direct-launch architecture.

OLED / Other flow:
  1. Download plutonium.exe into a dedicated DeckOps-managed Wine prefix.
  2. Launch it through Proton so the user can log in and let Plutonium
     download its full client.
  3. Wait for user confirmation that they have logged in and closed Plutonium.
  4. Verify by checking that the storage/ folder exists in the prefix.
  5. Copy the entire Plutonium/ folder into each selected game's prefix.
  6. Write config.json in each prefix with the correct game install paths.
  7. Write a bash wrapper script that replaces the game exe, padded to the
     original exe size so Steam's file validation does not flag it.

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import os
import stat
import shutil
import json
import subprocess
import time
import urllib.request

from log import get_logger
from net import BROWSER_UA, DownloadError
from depot_downgrade import plut_game_dir

_log = get_logger(__name__)



# ── dedicated prefix ──────────────────────────────────────────────────────────
# DeckOps manages its own Wine prefix for the initial Plutonium install.
# This avoids depending on Steam to create a non-Steam game entry and gives
# us a known, stable path to copy from.

DEDICATED_PREFIX = os.path.expanduser("~/.local/share/deckops/plutonium_prefix")
PLUT_BOOTSTRAPPER_URL = "https://cdn.plutonium.pw/updater/plutonium.exe"
_PLUT_ARCHIVE_FALLBACK_URL = "https://archive.org/download/plutonium_202605/plutonium.exe"


# ── game metadata ─────────────────────────────────────────────────────────────
# Maps DeckOps game key → (appid, config.json path key, exe name to replace)

GAME_META = {
    "t4sp":  (10090,  "t4Path",  "CoDWaW.exe"),
    "t4mp":  (10090,  "t4Path",  "CoDWaWmp.exe"),
    "t5sp":  (42700,  "t5Path",  "BlackOps.exe"),
    "t5mp":  (42710,  "t5Path",  "BlackOpsMP.exe"),
    "t6zm":  (212910, "t6Path",  "t6zm.exe"),
    "t6mp":  (202990, "t6Path",  "t6mp.exe"),
    "iw5mp": (42690,  "iw5Path", "iw5mp.exe"),
    "iw5mp_ds": (42750, "iw5Path", "iw5mp_server.exe"),
}

METADATA_FILE = "deckops_plutonium.json"

# Standalone wrapper exe names for OLED own games.
# These are new files dropped into the game folder — the original exe is
# left untouched. shortcut.py points the non-Steam shortcut at these.
# Same filenames as LCD's LCD_OWN_WRAPPER_EXES in plutonium_lcd.py so the
# launcher treats both models identically.
OLED_OWN_WRAPPER_EXES = {
    "t4sp":  "t4plutsp.exe",
    "t4mp":  "t4plutmp.exe",
    "t5sp":  "t5plutsp.exe",
    "t5mp":  "t5plutmp.exe",
    "t6mp":  "t6plutmp.exe",
    "t6zm":  "t6plutzm.exe",
    "iw5mp": "iw5plutmp.exe",
}

# OLED Steam games: (online, offline) wrapper files written next to the
# untouched game exe. Steam launch menu entries point at these (see
# steam_appinfo.py). Offline is a copy of the -lan .sh under an exe name.
# Keys sharing an appid (WaW) appear in this order.
STEAM_MENU_EXES = {
    "t4sp":  ("t4plutsp.exe",  "t4plutsp_lan.exe"),
    "t4mp":  ("t4plutmp.exe",  "t4plutmp_lan.exe"),
    "t5sp":  ("t5plutsp.exe",  "t5plutsp_lan.exe"),
    "t5mp":  ("t5plutmp.exe",  "t5plutmp_lan.exe"),
    "t6mp":  ("t6plutmp.exe",  "t6plutmp_lan.exe"),
    "t6zm":  ("t6plutzm.exe",  "t6plutzm_lan.exe"),
    "iw5mp": ("iw5plutmp.exe", "iw5plutmp_lan.exe"),
    # DS shares MW3's folder, so its files need their own names
    "iw5mp_ds": ("iw5plutds.exe", "iw5plutds_lan.exe"),
}

# Menu labels where one appid holds two modes; others get the defaults.
STEAM_MENU_LABELS = {
    "t4sp": ("Play Plutonium SP/ZM Online", "Play Plutonium SP/ZM Offline"),
    "t4mp": ("Play Plutonium Multiplayer Online", "Play Plutonium Multiplayer Offline"),
}
_DEFAULT_MENU_LABELS = ("Play Plutonium Online", "Play Plutonium Offline")

# Sidecar -lan wrapper script names for OLED offline mode.
# These are written alongside the game files (never replacing anything)
# and launched by DeckOps_Offline.exe for offline play. Shell scripts rather
# than .exe so they don't interfere with Steam's file validation.
OLED_LAN_WRAPPER_NAMES = {
    "t4sp":  "t4plut_lan_sp.sh",
    "t4mp":  "t4plut_lan_mp.sh",
    "t5sp":  "t5plut_lan_sp.sh",
    "t5mp":  "t5plut_lan_mp.sh",
    "t6mp":  "t6plut_lan_mp.sh",
    "t6zm":  "t6plut_lan_zm.sh",
    "iw5mp": "iw5plut_lan.sh",
    "iw5mp_ds": "iw5plut_lan.sh",
}

# Seconds each LAN wrapper stays alive after the bootstrapper returns.
# The bootstrapper exits as soon as it has spawned the game; if the
# wrapper exits with it, launcher_offline.sh ends, Steam considers the
# shortcut stopped, and session teardown races the still-initializing
# game. T6 initializes far more slowly than the IW-engine games, so it
# gets a much longer hold.
_LAN_LINGER_S_DEFAULT = 8
_LAN_LINGER_S = {
    "t6mp": 30,
    "t6zm": 30,
}

# Old shared filenames used before the unique-name fix. Used during
# install to clean up stale wrappers from previous DeckOps versions.
_OLD_OLED_LAN_WRAPPER_NAMES = {
    "t4sp":  "t4plut_lan.sh",
    "t4mp":  "t4plut_lan.sh",
    "t5sp":  "t5plut_lan.sh",
    "t5mp":  "t5plut_lan.sh",
    "t6mp":  "t6plut_lan.sh",
    "t6zm":  "t6plut_lan.sh",
}

# DeckOps client-side menu mods packaged as .iwd files (renamed .zip).
# Bundled with the repo at assets/mods/ and copied locally into Plutonium's
# storage/ directory where they are loaded automatically on game launch.
#
# T6 uses a single consolidated .iwd (deckops_bo2_menu.iwd) for both MP
# and ZM. The Lua inside contains both PopulateButtons_Multiplayer and
# PopulateButtons_Zombie, with the engine's CoD.isZombie dispatch selecting
# the right button set at runtime. Both t6mp and t6zm point at the same
# source file and same destination -- idempotent when both are installed.
_OLED_HERE = os.path.dirname(os.path.abspath(__file__))
MENU_MOD_ASSETS_DIR = os.path.join(os.path.dirname(_OLED_HERE), "assets", "mods")
MENU_MOD_FILES = {
    "t6mp":  ("t6/deckops_bo2_menu.iwd", "storage/t6/raw/deckops_bo2_menu.iwd"),
    "t6zm":  ("t6/deckops_bo2_menu.iwd", "storage/t6/raw/deckops_bo2_menu.iwd"),
    "iw5mp": ("iw5mp/main.lua", "storage/iw5/ui_mp/main.lua"),
    "iw5mp_ds": ("iw5mp/main.lua", "storage/iw5/ui_mp/main.lua"),
}


# ── path helpers ──────────────────────────────────────────────────────────────

def _plut_dir_in_prefix(prefix_path: str) -> str:
    """Return the Plutonium/ folder path inside a given Wine prefix."""
    return os.path.join(
        prefix_path, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )


def _plut_dir_in_compatdata(steam_root: str, appid: int) -> str:
    """Return the Plutonium/ folder path inside a Steam compatdata prefix."""
    return os.path.join(
        steam_root, "steamapps", "compatdata", str(appid),
        "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )


def _wine_path(linux_path: str) -> str:
    """Convert a Linux path to Wine Z: drive notation."""
    return "Z:" + linux_path.replace("/", "\\")


# ── dedicated prefix helpers ──────────────────────────────────────────────────

def get_dedicated_plut_dir() -> str:
    """Return the Plutonium/ folder inside DeckOps's dedicated prefix."""
    return _plut_dir_in_prefix(DEDICATED_PREFIX)


def is_plutonium_ready() -> bool:
    """
    Returns True if the user has logged in and Plutonium has downloaded
    its client files. We check for the storage/ folder which is only
    created after a successful login.
    """
    storage = os.path.join(get_dedicated_plut_dir(), "storage")
    if not os.path.isdir(storage):
        return False
    # Must have at least one game subfolder inside storage/
    return any(
        os.path.isdir(os.path.join(storage, d))
        for d in os.listdir(storage)
    )


def is_bootstrapper_ready() -> bool:
    """
    Returns True if the Plutonium bootstrapper binary exists in the
    dedicated prefix. This is a weaker check than is_plutonium_ready
    because it does not require a login -- it only confirms the
    bootstrapper exe has been downloaded into the dedicated prefix.
    """
    bootstrapper = os.path.join(
        get_dedicated_plut_dir(), "bin", "plutonium-bootstrapper-win32.exe"
    )
    return os.path.exists(bootstrapper)


# ── bootstrapper ──────────────────────────────────────────────────────────────

def launch_bootstrapper(proton_path: str, on_progress=None, steam_root: str = None):
    """
    Download plutonium.exe into the dedicated prefix and launch it through
    Proton. Blocks until the user closes the Plutonium window.

    The UI should display instructions to the user before calling this,
    and show a confirmation button after it returns.
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    plut_dir = get_dedicated_plut_dir()
    os.makedirs(plut_dir, exist_ok=True)

    # Proton needs pfx/ to exist , initialise a minimal prefix structure
    os.makedirs(DEDICATED_PREFIX, exist_ok=True)

    bootstrapper = os.path.join(plut_dir, "plutonium.exe")

    prog(5, "Downloading Plutonium bootstrapper...")
    _primary_failed = False
    for attempt in range(3):
        try:
            req = urllib.request.Request(PLUT_BOOTSTRAPPER_URL, headers=BROWSER_UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(bootstrapper, "wb") as f:
                f.write(r.read())
            break
        except Exception as ex:
            if attempt == 2:
                _primary_failed = True
                _log.warning("Primary Plutonium download failed after 3 attempts: %s", ex)
            else:
                time.sleep(2 ** attempt)

    if _primary_failed:
        prog(5, "Falling back to archive.org mirror...")
        try:
            req = urllib.request.Request(_PLUT_ARCHIVE_FALLBACK_URL, headers=BROWSER_UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(bootstrapper, "wb") as f:
                f.write(r.read())
            _log.info("Plutonium bootstrapper downloaded from archive.org fallback")
        except Exception as ex2:
            raise DownloadError(
                url=_PLUT_ARCHIVE_FALLBACK_URL,
                dest=bootstrapper,
                label="Plutonium bootstrapper",
                cause=ex2,
            )

    prog(15, "Launching Plutonium , please log in, then close the window when done.")

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"]           = DEDICATED_PREFIX
    if steam_root:
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = steam_root
    else:
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = os.path.dirname(
            os.path.dirname(proton_path)
        )

    proc = subprocess.Popen(
        [proton_path, "run", bootstrapper],
        env=env,
        cwd=plut_dir,
    )
    proc.wait()
    prog(30, "Plutonium closed.")


# ── copy to game prefix ───────────────────────────────────────────────────────
# We do a full copy of the Plutonium/ folder into each game's prefix rather
# than symlinking or sharing a single install. Each prefix is its own Wine
# environment and symlinks across prefixes can cause path resolution issues.
# Full copies keep each game isolated so one prefix can't break another.


# ── shared Plutonium directories ─────────────────────────────────────────────
# bin/, launcher/, and games/ are identical across all prefixes (~129MB total).
# Instead of copying them 6 times (~774MB waste), we keep one real copy and
# symlink from each prefix. Only storage/ is per-game and gets a real copy.

SHARED_PLUT_DIR = os.path.expanduser("~/.local/share/deckops/plutonium_shared")
_PLUT_SHARED_SUBDIRS = ("bin", "launcher", "games")


def _ensure_shared_plutonium(src_plut_dir: str, on_progress=None) -> bool:
    """
    Ensure the shared Plutonium directory has current copies of bin/,
    launcher/, and games/ from the source Plutonium install.

    Copies from src_plut_dir (the dedicated DeckOps plutonium prefix)
    into the shared location. If the shared dirs already exist and have
    the same file count, this is a fast no-op.

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
        # Quick file count check
        src_count = sum(1 for _ in os.scandir(src))
        dst_count = sum(1 for _ in os.scandir(dst))
        if dst_count < src_count:
            all_present = False
            break

    if all_present and os.path.isdir(SHARED_PLUT_DIR):
        prog("  ✓ Shared Plutonium dirs verified")
        return True

    prog("  Setting up shared Plutonium directories...")
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
        prog(f"  ✓ Shared Plutonium dirs ready ({elapsed:.1f}s)")
        return True
    except Exception as ex:
        prog(f"  ⚠ Shared Plutonium setup failed: {ex}")
        return False


_STORAGE_SUBDIRS = {
    "t4sp": "t4", "t4mp": "t4",
    "t5sp": "t5", "t5mp": "t5",
    "t6zm": "t6", "t6mp": "t6",
    "iw5mp": "iw5", "iw5mp_ds": "iw5",
}


def _copy_plut_to_prefix(src_plut_dir: str, dest_plut_dir: str,
                          game_key: str = "", on_progress=None):
    """
    Set up Plutonium in a game prefix using symlinks for shared dirs.

    bin/, launcher/, and games/ are symlinked to the shared copy at
    ~/.local/share/deckops/plutonium_shared/. Only the relevant storage/
    subdirectory for game_key is copied as real files, so large mods
    (e.g. Zombies Declassified ~9GB in storage/t6/) don't leak into
    unrelated prefixes.

    Falls back to full copy if shared dirs aren't available.
    """

    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog(f"  Copying Plutonium: {src_plut_dir} -> {dest_plut_dir}")

    # The fresh copy below wipes dest_plut_dir, which also holds the user's
    # stats (players/, e.g. WaW mpdata) and mods. Move those aside first and
    # put them back after, so reinstall/update never resets progress.
    keep_root = dest_plut_dir.rstrip(os.sep) + ".deckops_keep"
    _stash_user_storage(dest_plut_dir, keep_root, prog)
    try:
        _copy_plut_fresh(src_plut_dir, dest_plut_dir, game_key, prog)
    finally:
        _restore_user_storage(dest_plut_dir, keep_root, prog)


# storage/<game>/ parts that belong to the user, not to Plutonium
_PLUT_USER_PARTS = ("players", "mods")


def _stash_user_storage(plut_dir: str, keep_root: str, prog):
    storage = os.path.join(plut_dir, "storage")
    if not os.path.isdir(storage):
        return
    for store in os.listdir(storage):
        for part in _PLUT_USER_PARTS:
            src = os.path.join(storage, store, part)
            dst = os.path.join(keep_root, store, part)
            # A keep dir left by an earlier failed run already holds the
            # user's data; what's in the prefix now is a fresh copy.
            if not os.path.isdir(src) or os.path.lexists(dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            prog(f"  Kept storage/{store}/{part}")


def _restore_user_storage(plut_dir: str, keep_root: str, prog):
    if not os.path.isdir(keep_root):
        return
    try:
        for store in os.listdir(keep_root):
            for part in os.listdir(os.path.join(keep_root, store)):
                src = os.path.join(keep_root, store, part)
                dst = os.path.join(plut_dir, "storage", store, part)
                if os.path.lexists(dst):
                    shutil.rmtree(dst)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
        shutil.rmtree(keep_root)
    except OSError as ex:
        _log.error("Could not restore Plutonium user data from %s: %s", keep_root, ex)
        prog(f"  ⚠ Your Plutonium stats/mods are safe in {keep_root} but could not be moved back: {ex}")


def _copy_plut_fresh(src_plut_dir: str, dest_plut_dir: str, game_key: str, prog):
    if os.path.exists(dest_plut_dir):
        prog(f"  Removing existing Plutonium at {dest_plut_dir}...")
        shutil.rmtree(dest_plut_dir)

    start = time.time()

    # Try symlink approach if shared dirs are available
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

        # Copy only the storage subdirectory for this game
        storage_src = os.path.join(src_plut_dir, "storage")
        if os.path.isdir(storage_src):
            storage_name = _STORAGE_SUBDIRS.get(game_key)
            if storage_name:
                sub_src = os.path.join(storage_src, storage_name)
                if os.path.isdir(sub_src):
                    sub_dst = os.path.join(dest_plut_dir, "storage", storage_name)
                    os.makedirs(os.path.join(dest_plut_dir, "storage"), exist_ok=True)
                    shutil.copytree(sub_src, sub_dst)
            else:
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
        # Fallback: full copy — still filter storage if game_key is known
        storage_name = _STORAGE_SUBDIRS.get(game_key) if game_key else ""
        if storage_name:
            os.makedirs(dest_plut_dir, exist_ok=True)
            for item in os.listdir(src_plut_dir):
                src_item = os.path.join(src_plut_dir, item)
                dst_item = os.path.join(dest_plut_dir, item)
                if item == "storage":
                    sub_src = os.path.join(src_item, storage_name)
                    if os.path.isdir(sub_src):
                        sub_dst = os.path.join(dst_item, storage_name)
                        os.makedirs(dst_item, exist_ok=True)
                        shutil.copytree(sub_src, sub_dst)
                elif os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)
        else:
            shutil.copytree(src_plut_dir, dest_plut_dir)
        elapsed = time.time() - start
        prog(f"  Copied Plutonium ({elapsed:.1f}s)")


# ── config.json ───────────────────────────────────────────────────────────────

def _write_config(plut_dir: str, game_keys: list, installed_games: dict):
    """
    Write config.json inside a prefix with the correct game install paths.
    Reads the existing config from the dedicated prefix and updates path keys.
    game_keys   , list of game keys being installed into this prefix
    installed_games , dict from detect_games.find_installed_games()
    """
    config_path = os.path.join(plut_dir, "config.json")

    # Read existing config (token etc.) from this prefix if present
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = json.load(f)
    else:
        data = {}

    # Write the path key for each game in this prefix
    for key in game_keys:
        if key not in GAME_META:
            continue
        _, path_key, _ = GAME_META[key]
        game = installed_games.get(key, {})
        install_dir = game.get("install_dir", "")
        if install_dir:
            # MW3 Steam: point at the downgrade/ subfolder where 32-bit
            # depot files live, keeping the 64-bit install untouched.
            install_dir = plut_game_dir(key, install_dir, game.get("source", "steam"))
            data[path_key] = _wine_path(install_dir)

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


# ── client-side menu mods ────────────────────────────────────────────────────

def _install_menu_mod(dest_plut_dir: str, game_key: str, on_progress=None):
    """
    Copy and install the DeckOps menu mod for the given game key.

    Copies the bundled mod file from assets/mods/ into the prefix's
    Plutonium storage path at raw/. Plutonium loads .iwd files from
    raw/ automatically on game launch, overriding the default main
    menu with the DeckOps community version (server connect, unlock
    all, reset stats buttons).

    Uses .iwd in raw/ (not mods/) so it:
    - Uses normal player stats (no separate mod stats)
    - Persists across disconnects
    - Loads automatically on every launch

    Skips silently for game keys without a menu mod defined.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in MENU_MOD_FILES:
        return

    asset_rel, local_path = MENU_MOD_FILES[game_key]
    src_file = os.path.join(MENU_MOD_ASSETS_DIR, asset_rel)
    dest_file = os.path.join(dest_plut_dir, local_path)

    prog(f"  Installing DeckOps menu mod for {game_key}...")

    if not os.path.isfile(src_file):
        prog(f"  ⚠ Menu mod asset missing: {src_file}")
        return  # Non-fatal -- game still works without the mod

    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

    try:
        shutil.copy2(src_file, dest_file)
        prog(f"  ✓ Menu mod installed ({os.path.getsize(dest_file)} bytes)")
    except OSError as ex:
        prog(f"  ⚠ Menu mod copy failed: {ex}")


# ── offline launcher prefix helper ────────────────────────────────────────────

def _copy_plut_to_launcher_prefix(src_plut_dir: str, game_prefix_plut_dir: str,
                                   launcher_plut_dir: str, game_key: str,
                                   on_progress=None):
    """
    Mirror Plutonium files into the offline launcher's prefix.

    Unlike _copy_plut_to_prefix, this does NOT wipe the destination — each
    game's install_plutonium call adds its own storage/ subdirs incrementally.
    Shared dirs (bin/, launcher/, games/) are symlinked once and skipped on
    subsequent calls.

    src_plut_dir          — dedicated prefix Plutonium dir (source of truth
                            for bins, shared files)
    game_prefix_plut_dir  — the per-game prefix Plutonium dir that was just
                            populated (source of mods/storage for THIS game)
    launcher_plut_dir     — destination inside the launcher's compatdata prefix
    game_key              — current game key (for storage subdir mapping)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    os.makedirs(launcher_plut_dir, exist_ok=True)

    # Symlink shared directories (skip if already present)
    shared_ready = all(
        os.path.isdir(os.path.join(SHARED_PLUT_DIR, d))
        for d in _PLUT_SHARED_SUBDIRS
        if os.path.isdir(os.path.join(src_plut_dir, d))
    )

    if shared_ready:
        for subdir in _PLUT_SHARED_SUBDIRS:
            shared_src = os.path.join(SHARED_PLUT_DIR, subdir)
            dest_sub = os.path.join(launcher_plut_dir, subdir)
            if os.path.isdir(shared_src) and not os.path.exists(dest_sub):
                os.symlink(shared_src, dest_sub)

    # Merge storage/ — copy per-game storage subdirs without wiping others.
    storage_name = _STORAGE_SUBDIRS.get(game_key)
    if storage_name:
        src_storage = os.path.join(game_prefix_plut_dir, "storage", storage_name)
        dst_storage = os.path.join(launcher_plut_dir, "storage", storage_name)
        if os.path.isdir(src_storage):
            if os.path.exists(dst_storage):
                shutil.rmtree(dst_storage)
            shutil.copytree(src_storage, dst_storage)
            prog(f"  Merged storage/{storage_name} into launcher prefix")

    # Copy top-level files (config.json handled separately by _write_config)
    for item in os.listdir(src_plut_dir):
        src_item = os.path.join(src_plut_dir, item)
        dst_item = os.path.join(launcher_plut_dir, item)
        if os.path.exists(dst_item):
            continue  # already present (symlink, storage, or prior copy)
        if os.path.isfile(src_item):
            shutil.copy2(src_item, dst_item)


# ── launcher prefix game configs ──────────────────────────────────────────────
#
# Maps game keys to their DeckOps asset config and the relative storage
# path inside the Plutonium directory where the bootstrapper expects them.
# This is the single source of truth for placing game configs into the
# offline launcher prefix — called every time a Plutonium game is
# installed or reinstalled, so configs always land regardless of which
# install flow triggered it.

_LAUNCHER_CONFIG_MAP = {
    # game_key: (asset_subpath, storage_relpath)
    "t4sp":     ("WaW/config.cfg",          os.path.join("storage", "t4", "players", "profiles", "$$$")),
    "t4mp":     ("WaW/config_mp.cfg",       os.path.join("storage", "t4", "players", "profiles", "$$$")),
    "t5sp":     ("BO1/config.cfg",          os.path.join("storage", "t5", "players")),
    "t5mp":     ("BO1/config_mp.cfg",       os.path.join("storage", "t5", "players")),
    "t6mp":     ("BO2/plutonium_mp.cfg",    os.path.join("storage", "t6", "players")),
    "t6zm":     ("BO2/plutonium_zm.cfg",    os.path.join("storage", "t6", "players")),
    "iw5mp":    ("MW3/config_mp.cfg",       os.path.join("storage", "iw5", "players")),
    "iw5mp_ds": ("MW3/config_mp.cfg",       os.path.join("storage", "iw5", "players")),
}


def _apply_launcher_game_configs(launcher_plut_dir: str, game_key: str,
                                  on_progress=None):
    """
    Copy DeckOps asset configs directly into the offline launcher prefix.

    This ensures the bootstrapper has correct resolution, FOV, sensitivity,
    and player name settings when launching games from the offline LAN
    launcher — regardless of install flow or timing.

    Called inside install_plutonium / install_plutonium_lcd after the
    storage/ tree and menu mods have been mirrored. Uses the deck model
    from deckops.json to pick LCD or OLED assets.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if game_key not in _LAUNCHER_CONFIG_MAP:
        return

    import config as _cfg
    deck_model = _cfg.get_deck_model() or "oled"
    player_name = _cfg.get_player_name() or "Player"
    model_dir = _cfg.get_model_config_dir()

    _here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(_here)
    configs_dir = os.path.join(project_root, "assets", "configs")

    asset_subpath, storage_relpath = _LAUNCHER_CONFIG_MAP[game_key]
    src = os.path.join(configs_dir, model_dir, asset_subpath)

    if not os.path.exists(src):
        prog(f"  ⚠ Launcher config asset not found: {asset_subpath}")
        return

    dest_dir = os.path.join(launcher_plut_dir, storage_relpath)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src))

    try:
        shutil.copy2(src, dest)

        # Apply player name
        from game_config import _replace_player_name
        _replace_player_name(dest, player_name)

        prog(f"  + {game_key}: launcher config -> {os.path.basename(src)}")
    except Exception as ex:
        prog(f"  ⚠ {game_key}: launcher config failed: {ex}")


# ── wrapper script ────────────────────────────────────────────────────────────

# Maps DeckOps game keys to the Plutonium protocol key used in
# `plutonium://play/<key>` URLs and bootstrapper arguments. Most keys
# are identical, but iw5mp_ds (the free dedicated server appid 42750)
# runs the same Plutonium client as iw5mp (the full game appid 42690).
_PLUT_KEY_MAP = {
    "iw5mp_ds": "iw5mp",
}

def _plut_key(game_key: str) -> str:
    """Return the Plutonium protocol key for a DeckOps game key."""
    return _PLUT_KEY_MAP.get(game_key, game_key)

def _write_oled_own_wrapper(game: dict, game_key: str, steam_root: str,
                             proton_path: str, compatdata_path: str,
                             plut_dir: str, wrapper_name: str = None) -> str | None:
    """
    Write a standalone wrapper exe for OLED own games.

    Creates a new file (e.g. t4plutmp.exe) in the game's install dir that
    launches the Plutonium launcher with a protocol URL. The original game
    exe is left untouched. shortcut.py points the non-Steam shortcut at
    this wrapper, and the launcher uses the stored wrapper_path to launch it.
    Steam games reuse it for their Online launch menu entry (wrapper_name
    from STEAM_MENU_EXES).

    Returns the full path to the written wrapper, or None if game_key
    is not in OLED_OWN_WRAPPER_EXES.
    """
    if not wrapper_name and game_key not in OLED_OWN_WRAPPER_EXES:
        return None

    install_dir  = game["install_dir"]
    wrapper_name = wrapper_name or OLED_OWN_WRAPPER_EXES[game_key]
    wrapper_path = os.path.join(install_dir, wrapper_name)

    launcher = os.path.join(plut_dir, "bin",
                            "plutonium-launcher-win32.exe")
    plut_url = f"plutonium://play/{_plut_key(game_key)}"

    script = (
        "#!/bin/bash\n"
        f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
        f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
        f"\"{proton_path}\" run \"{launcher}\" \"{plut_url}\" &\n"
        "PROTON_PID=$!\n"
        "sleep 8\n"
        "while kill -0 $PROTON_PID 2>/dev/null || "
        f"pgrep -fa wineserver | grep -q \"{compatdata_path}\"; do\n"
        "  sleep 3\n"
        "done\n"
    )

    with open(wrapper_path, "wb") as f:
        f.write(script.encode("utf-8"))

    os.chmod(wrapper_path, os.stat(wrapper_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return wrapper_path


def _write_oled_lan_wrapper(game: dict, game_key: str, steam_root: str,
                             proton_path: str, compatdata_path: str,
                             plut_dir: str, source: str = "steam") -> str | None:
    """
    Write a sidecar -lan bash script for OLED offline mode.

    Creates a new shell script (e.g. t4plut_lan_sp.sh) alongside the game
    files. Each game_key gets a unique filename so SP/MP pairs don't
    overwrite each other. DeckOps_Offline.exe reads the path from config
    and calls bash on it for offline play.

    Uses the bootstrapper with -lan flag so no Plutonium account is needed.
    Written for both Steam and own game sources -- the path differs but
    the script content is the same.

    Returns the full path to the written script, or None if game_key
    is not in OLED_LAN_WRAPPER_NAMES.
    """
    if game_key not in OLED_LAN_WRAPPER_NAMES:
        return None

    install_dir  = game["install_dir"]
    wrapper_name = OLED_LAN_WRAPPER_NAMES[game_key]
    wrapper_path = os.path.join(install_dir, wrapper_name)

    # Clean up stale shared-name wrapper from older DeckOps versions.
    # Old versions used the same filename for SP/MP pairs (e.g. t4plut_lan.sh
    # for both t4sp and t4mp), causing whichever installed last to overwrite
    # the other. Remove the old shared-name file if it differs from the new
    # unique name so stale scripts don't persist.
    old_name = _OLD_OLED_LAN_WRAPPER_NAMES.get(game_key)
    if old_name and old_name != wrapper_name:
        old_path = os.path.join(install_dir, old_name)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                _log.debug("old wrapper cleanup failed", exc_info=True)

    try:
        import config as _cfg
        player_name = _cfg.get_player_name() or "Player"
    except Exception:
        player_name = "Player"

    bootstrapper  = os.path.join(plut_dir, "bin",
                                  "plutonium-bootstrapper-win32.exe")
    # MW3 Steam: point at downgrade/ where the 32-bit files live
    from steam_common import wine_path_for_prefix
    game_dir_wine = wine_path_for_prefix(plut_game_dir(game_key, install_dir, source), compatdata_path)

    linger = _LAN_LINGER_S.get(game_key, _LAN_LINGER_S_DEFAULT)
    script = (
        "#!/bin/bash\n"
        f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
        f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
        # Plutonium's own launcher passes a fresh random -token even in LAN mode
        "TOKEN=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \\n')\n"
        f"cd \"{plut_dir}\"\n"
        # No exec: the shell must survive the bootstrapper returning so it
        # can hold the session open below.
        f"\"{proton_path}\" run \"{bootstrapper}\" "
        f"{_plut_key(game_key)} \"{game_dir_wine}\" -token \"$TOKEN\" -lan +name \"{player_name}\"\n"
        "# The bootstrapper exits as soon as it has spawned the game. Stay\n"
        "# alive so the Steam shortcut session is not torn down while the\n"
        "# game is still initializing (T6 loads much slower than IW games).\n"
        f"sleep {linger}\n"
    )

    with open(wrapper_path, "wb") as f:
        f.write(script.encode("utf-8"))

    os.chmod(wrapper_path, os.stat(wrapper_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return wrapper_path


def _write_wrapper(game: dict, game_key: str, steam_root: str,
                   proton_path: str, compatdata_path: str, plut_dir: str):
    """
    Replace the game exe with a bash wrapper that launches Plutonium
    through Proton. OLED / Other only — LCD uses plutonium_lcd.py.

    Calls plutonium-launcher-win32.exe with a protocol URL.
    Requires the user to have logged in.

    The original exe is backed up as <exe>.bak.
    The wrapper is padded to the original file's size so Steam's
    file validation does not flag it as changed.
    """
    install_dir    = game["install_dir"]
    _, _, exe_name = GAME_META[game_key]
    exe_path       = os.path.join(install_dir, exe_name)
    backup_path    = exe_path + ".bak"

    # Safety: refuse to create a wrapper if the original exe doesn't exist.
    # Steam games always ship the exe we're replacing. If it's missing,
    # detection returned the wrong key — writing here would create a
    # phantom file that confuses future detection runs.
    if not os.path.exists(exe_path) and not os.path.exists(backup_path):
        return

    # Read original size before we overwrite
    original_size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0

    # Back up original exe
    if not os.path.exists(backup_path) and os.path.exists(exe_path):
        shutil.copy2(exe_path, backup_path)
        original_size = os.path.getsize(backup_path)

    # OLED online mode: call the launcher with a protocol URL
    launcher = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")
    plut_url = f"plutonium://play/{_plut_key(game_key)}"
    script = (
        "#!/bin/bash\n"
        f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
        f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
        f"\"{proton_path}\" run \"{launcher}\" \"{plut_url}\" &\n"
        "PROTON_PID=$!\n"
        "sleep 8\n"
        "while kill -0 $PROTON_PID 2>/dev/null || "
        f"pgrep -fa wineserver | grep -q \"{compatdata_path}\"; do\n"
        "  sleep 3\n"
        "done\n"
    )

    script_bytes = script.encode("utf-8")
    if original_size > len(script_bytes):
        script_bytes += b"\x00" * (original_size - len(script_bytes))

    with open(exe_path, "wb") as f:
        f.write(script_bytes)

    os.chmod(exe_path, os.stat(exe_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _is_script(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


def _restore_original_exe(game: dict, game_key: str):
    """
    Undo the old exe replacement: put <exe>.bak back over our wrapper.
    If Steam already restored the real exe (e.g. Verify), drop the stale .bak.
    """
    exe_path = os.path.join(game["install_dir"], GAME_META[game_key][2])
    bak_path = exe_path + ".bak"
    if not os.path.exists(bak_path):
        return
    if not os.path.exists(exe_path) or _is_script(exe_path):
        os.replace(bak_path, exe_path)
    else:
        os.remove(bak_path)


def _setup_steam_menu(game: dict, game_key: str, steam_root: str,
                      proton_path: str, compatdata_path: str, plut_dir: str,
                      lan_wrapper_path: str, prog) -> str | None:
    """
    OLED Steam games: keep the original exe and add Plutonium Online /
    Offline entries to the game's Steam launch menu, each pointing at its
    own wrapper file. Steam runs the chosen file through its Proton, the
    same way it ran the old replaced exe. Returns the online wrapper path.
    """
    online_name, offline_name = STEAM_MENU_EXES[game_key]
    _restore_original_exe(game, game_key)

    online_path = _write_oled_own_wrapper(
        game, game_key, steam_root, proton_path,
        compatdata_path, plut_dir, wrapper_name=online_name,
    )
    if lan_wrapper_path and os.path.exists(lan_wrapper_path):
        shutil.copy2(lan_wrapper_path, os.path.join(game["install_dir"], offline_name))

    # Rebuild our entries for this appid in STEAM_MENU_EXES order (Online
    # before Offline, WaW SP before MP) whatever order keys were installed in.
    # Sibling keys count once their online wrapper is on disk.
    appid = GAME_META[game_key][0]
    keys = [k for k in STEAM_MENU_EXES if GAME_META[k][0] == appid and (
            k == game_key or os.path.exists(os.path.join(game["install_dir"], STEAM_MENU_EXES[k][0])))]
    entries = []
    for k in keys:
        on, off = STEAM_MENU_LABELS.get(k, _DEFAULT_MENU_LABELS)
        entries += [{"executable": STEAM_MENU_EXES[k][0], "description": on},
                    {"executable": STEAM_MENU_EXES[k][1], "description": off}]

    from steam_appinfo import add_launch_entries, remove_launch_entries
    remove_launch_entries(steam_root, appid, [e["executable"] for e in entries])
    added = add_launch_entries(steam_root, appid, entries)
    prog(92, "  ✓ Launch menu: " + " / ".join(e["description"] for e in entries) if added
             else "  ⚠ Launch menu not added yet, will retry next time Steam is closed")
    return online_path


# ── metadata ──────────────────────────────────────────────────────────────────

def _write_metadata(install_dir: str, data: dict):
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _read_metadata(install_dir: str) -> dict:
    path = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


# ZD script files dropped into storage/t6/raw/ alongside dlc5 + usermaps
_ZD_RAW_FILES = (
    "raw/maps/mp/animscripts/zm_dog_combat.gsc",
    "raw/maps/mp/animscripts/zm_dog_stop.gsc",
    "raw/scripts/zm/zzz_zm_dogfog.csc",
    "raw/scripts/zm/zzz_zm_factoryfog.csc",
    "raw/scripts/zm/zzz_zm_factorypower.csc",
    "raw/scripts/zm/zzz_zm_gglow.csc",
    "raw/scripts/zm/zzz_zm_location.gsc",
    "raw/scripts/zm/zzz_zm_moonsky.csc",
    "raw/scripts/zm/zzz_zm_sumpffog.csc",
)


def cleanup_zd_from_other_prefixes(installed_games: dict, steam_root: str,
                                    on_progress=None):
    """
    Remove leaked Zombies Declassified files from non-t6zm prefixes.

    Earlier versions copied the entire storage/ tree (including ZD's ~9GB)
    into every Plutonium game prefix. This finds and removes those copies
    from prefixes that don't need them.

    Returns the number of prefixes cleaned.
    """
    from zombies_declassified import _ZD_USERMAPS

    def prog(msg):
        if on_progress:
            on_progress(msg)

    cleaned = 0
    for key in GAME_META:
        if key == "t6zm" or key not in installed_games:
            continue
        game = installed_games[key]
        install_dir = game.get("install_dir", "")
        if not install_dir:
            continue

        meta = _read_metadata(install_dir)
        plut_dir = meta.get("plut_dir", "")
        if not plut_dir:
            appid = GAME_META[key][0]
            plut_dir = _plut_dir_in_compatdata(steam_root, appid)

        storage_t6 = os.path.join(plut_dir, "storage", "t6")
        dlc5_dir = os.path.join(storage_t6, "mods", "dlc5")
        if not os.path.isdir(dlc5_dir):
            continue

        prog(f"  Cleaning ZD files from {key} prefix...")

        shutil.rmtree(dlc5_dir, ignore_errors=True)

        um_dir = os.path.join(storage_t6, "usermaps")
        for mapname in _ZD_USERMAPS:
            mp = os.path.join(um_dir, mapname)
            if os.path.isdir(mp):
                shutil.rmtree(mp, ignore_errors=True)

        for subpath in _ZD_RAW_FILES:
            fp = os.path.join(storage_t6, subpath)
            if os.path.isfile(fp):
                os.remove(fp)

        cleaned += 1
        prog(f"  ✓ Removed ZD files from {key} prefix")

    # Also clean the launcher prefix
    try:
        from shortcut import get_launcher_plut_dir
        launcher_t6 = os.path.join(get_launcher_plut_dir(), "storage", "t6")
        dlc5_dir = os.path.join(launcher_t6, "mods", "dlc5")
        if os.path.isdir(dlc5_dir):
            prog("  Cleaning ZD files from launcher prefix...")
            shutil.rmtree(dlc5_dir, ignore_errors=True)
            um_dir = os.path.join(launcher_t6, "usermaps")
            for mapname in _ZD_USERMAPS:
                mp = os.path.join(um_dir, mapname)
                if os.path.isdir(mp):
                    shutil.rmtree(mp, ignore_errors=True)
            for subpath in _ZD_RAW_FILES:
                fp = os.path.join(launcher_t6, subpath)
                if os.path.isfile(fp):
                    os.remove(fp)
            cleaned += 1
            prog("  ✓ Removed ZD files from launcher prefix")
    except Exception:
        pass

    return cleaned


def cleanup_plut_from_non_plut_prefixes(steam_root: str, on_progress=None):
    """
    Remove leaked Plutonium directories from prefixes that aren't Plutonium games.

    Old versions ran _copy_plut_to_prefix() with a blanket storage/ copy into
    every managed prefix. Non-Plutonium appids (CoD4, MW2, MW3 SP, BO2 Campaign,
    BO3, Ghosts, AW) should never have Plutonium data.

    Returns the number of prefixes cleaned.
    """
    from ge_proton import MANAGED_APPIDS

    def prog(msg):
        if on_progress:
            on_progress(msg)

    plut_appids = {str(meta[0]) for meta in GAME_META.values()}
    cleaned = 0

    for appid_str in MANAGED_APPIDS:
        if appid_str in plut_appids:
            continue
        plut_dir = _plut_dir_in_compatdata(steam_root, int(appid_str))
        if not os.path.isdir(plut_dir):
            continue
        prog(f"  Removing leaked Plutonium data from appid {appid_str}...")
        shutil.rmtree(plut_dir, ignore_errors=True)
        cleaned += 1
        prog(f"  ✓ Cleaned Plutonium from appid {appid_str}")

    return cleaned


# ── public API ────────────────────────────────────────────────────────────────

def install_plutonium(game: dict, game_key: str, steam_root: str,
                      proton_path: str, compatdata_path: str,
                      on_progress=None, installed_games: dict = None,
                      source: str = "steam"):
    """
    Full install flow for a single Plutonium game.

    LCD Decks are dispatched to plutonium_lcd.py early
    in this function. Everything after the dispatch handles
    OLED and Other (non-Deck SteamOS) devices.

    Assumes the user has already logged in and closed Plutonium via
    launch_bootstrapper(), and is_plutonium_ready() has returned True.

    game               , entry from detect_games.find_installed_games()
    game_key           , one of: t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    steam_root         , path to Steam root
    proton_path        , path to the proton executable
    compatdata_path    , path to this game's compatdata prefix
    on_progress        , optional callback(percent: int, status: str)
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # Fall back to single-game dict if caller doesn't supply full installed_games.
    # Supplying the full dict is preferred so sibling keys get correct paths.
    if installed_games is None:
        installed_games = {game_key: game}

    # ── LCD dispatch ──────────────────────────────────────────────────────
    # LCD Decks use Heroic Games Launcher with a single shared Wine prefix
    # for all Plutonium games. Everything from downloading the bootstrapper
    # to writing per-game shortcuts lives in plutonium_lcd.py.
    # OLED and Other devices continue below with the direct-launch path.
    import config as _cfg_lcd
    if _cfg_lcd.is_lcd():
        from plutonium_lcd import install_plutonium_lcd
        wrapper_path = install_plutonium_lcd(
            game, game_key, installed_games,
            on_progress=on_progress,
            steam_root=steam_root,
            proton_path=proton_path,
            compatdata_path=compatdata_path,
            source=source,
        )
        return wrapper_path

    src_plut_dir  = get_dedicated_plut_dir()

    # Ensure shared Plutonium dirs are set up (one-time, shared across games)
    _ensure_shared_plutonium(src_plut_dir,
                             on_progress=lambda msg: prog(5, msg))

    # OLED / Other past this point (LCD returns early above).
    # Plutonium files go into Steam's compatdata prefix for the game,
    # because OLED/Other launches the game through a bash wrapper that
    # Steam runs inside that same prefix. Use the compatdata_path passed
    # by the caller for correct SD card handling via find_compatdata().
    dest_plut_dir = os.path.join(
        compatdata_path, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )

    prog(10, f"Copying Plutonium into prefix for {game['name']}...")
    _copy_plut_to_prefix(
        src_plut_dir, dest_plut_dir, game_key=game_key,
        on_progress=lambda msg: prog(40, msg),
    )

    prog(60, "Writing game path to config.json...")
    # Pass all keys that share this appid so config has all paths for this prefix.
    # installed_games must contain ALL installed games, not just the current one,
    # so sibling keys (e.g. t4sp + t4mp share appid 10090) get their paths written too.
    appid = GAME_META[game_key][0]
    keys_for_appid = [k for k, v in GAME_META.items() if v[0] == appid]
    _write_config(dest_plut_dir, keys_for_appid, installed_games)

    # Apply DeckOps game configs (resolution, FOV, sensitivity, name)
    # into the per-game prefix BEFORE copying to the launcher prefix.
    # This way the tuned configs propagate automatically to every prefix
    # that receives a copy of storage/ — no separate mirror step needed.
    _apply_launcher_game_configs(dest_plut_dir, game_key,
                                  on_progress=lambda msg: prog(62, msg))

    # Install DeckOps client-side menu mod (e.g. mainlobby.lua for T6 MP).
    # OLED / Other only -- LCD handles its own setup in plutonium_lcd.py.
    prog(65, "Installing menu mod...")
    _install_menu_mod(dest_plut_dir, game_key,
                      on_progress=lambda msg: prog(67, msg))

    # ── Copy Plutonium into the offline launcher's prefix ────────────
    # The offline launcher exe runs inside its own Proton prefix (based
    # on the non-Steam shortcut appid). For the bootstrapper to find game
    # configs, storage/, and mods, we need to mirror them there too.
    # config.json is written with ALL selected game paths (merged) so the
    # launcher can see every installed game, not just this one.
    prog(70, "Mirroring to offline launcher prefix...")
    try:
        from shortcut import get_launcher_plut_dir
        launcher_plut_dir = get_launcher_plut_dir()

        # Copy Plutonium files (bins via symlinks, storage as real copy)
        # but DON'T wipe the destination — we're merging across games.
        _copy_plut_to_launcher_prefix(
            src_plut_dir, dest_plut_dir, launcher_plut_dir,
            game_key,
            on_progress=lambda msg: prog(72, msg),
        )

        # Write merged config.json with ALL selected Plutonium game paths
        all_plut_keys = [
            k for k in (installed_games or {}).keys()
            if k in GAME_META
        ]
        _write_config(launcher_plut_dir, all_plut_keys, installed_games)

        # Install menu mod into launcher prefix too
        _install_menu_mod(launcher_plut_dir, game_key,
                          on_progress=lambda msg: prog(74, msg))

        # Apply DeckOps game configs (resolution, FOV, sensitivity, name)
        # directly into the launcher prefix so the bootstrapper picks them
        # up when launching from the offline LAN launcher.
        _apply_launcher_game_configs(launcher_plut_dir, game_key,
                                      on_progress=lambda msg: prog(75, msg))

        prog(76, "  ✓ Offline launcher prefix updated")
    except Exception as ex:
        prog(75, f"  ⚠ Offline launcher prefix mirror failed: {ex}")

    # ── OLED / Other only past this point ──────────────────────────────
    # LCD dispatched to plutonium_lcd.py at the top of this
    # function. OLED games get a Steam-side bash wrapper + metadata.
    wrapper_path = None
    if source == "own":
        # OLED own games: standalone wrapper
        prog(80, "Writing launcher wrapper...")
        wrapper_path = _write_oled_own_wrapper(
            game, game_key, steam_root, proton_path,
            compatdata_path, dest_plut_dir,
        )

        prog(85, "Writing offline LAN wrapper...")
        # Sidecar -lan script alongside the game files. Does not touch the
        # online wrapper above. DeckOps_Offline.exe reads lan_wrapper_path
        # from config and bash-runs this script for offline play.
        lan_wrapper_path = _write_oled_lan_wrapper(
            game, game_key, steam_root, proton_path,
            compatdata_path, dest_plut_dir, source="own",
        )

        prog(95, "Saving metadata...")
        _write_metadata(game["install_dir"], {
            "game_key":    game_key,
            "plut_dir":    dest_plut_dir,
        })
        import config as _cfg_own
        _cfg_own.mark_game_setup(
            game_key, "plutonium", source="own",
            wrapper_path=wrapper_path,
            lan_wrapper_path=lan_wrapper_path,
        )
    else:
        wrapper_exe = os.path.join(game["install_dir"], GAME_META[game_key][2])
        if game_key not in STEAM_MENU_EXES:
            # Fallback for a key without a menu mapping: replace the exe
            prog(80, "Writing launcher wrapper...")
            _write_wrapper(game, game_key, steam_root, proton_path,
                           compatdata_path, dest_plut_dir)

        prog(85, "Writing offline LAN wrapper...")
        # Sidecar -lan script alongside the game files. DeckOps_Offline.exe
        # reads lan_wrapper_path from config and bash-runs this script for
        # offline play.
        lan_wrapper_path = _write_oled_lan_wrapper(
            game, game_key, steam_root, proton_path,
            compatdata_path, dest_plut_dir, source="steam",
        )

        if game_key in STEAM_MENU_EXES:
            prog(88, "Adding Plutonium to the Steam launch menu...")
            wrapper_exe = _setup_steam_menu(
                game, game_key, steam_root, proton_path, compatdata_path,
                dest_plut_dir, lan_wrapper_path, prog,
            ) or wrapper_exe

        prog(95, "Saving metadata...")
        _write_metadata(game["install_dir"], {
            "game_key":    game_key,
            "plut_dir":    dest_plut_dir,
            "wrapper_exe": wrapper_exe,
        })
        import config as _cfg_steam
        _cfg_steam.mark_game_setup(
            game_key, "plutonium", source="steam",
            lan_wrapper_path=lan_wrapper_path,
        )

    prog(100, f"Plutonium ready for {game['name']}!")
    return wrapper_path


def uninstall_plutonium(game: dict, game_key: str):
    """
    Restore the original game exe from backup and remove the
    Plutonium folder from this game's prefix.
    Also cleans up any Heroic entries if this was an LCD install.
    """
    install_dir    = game["install_dir"]
    _, _, exe_name = GAME_META[game_key]
    exe_path       = os.path.join(install_dir, exe_name)
    backup_path    = exe_path + ".bak"

    if os.path.exists(backup_path):
        shutil.move(backup_path, exe_path)

    # Launch menu wrappers and entries (OLED Steam games)
    names = list(STEAM_MENU_EXES.get(game_key, ()))
    if names:
        for n in names:
            p = os.path.join(install_dir, n)
            if os.path.exists(p):
                os.remove(p)
        try:
            import config as _cfg
            from steam_appinfo import remove_launch_entries
            steam_root = _cfg.load().get("steam_root") or os.path.expanduser("~/.local/share/Steam")
            remove_launch_entries(steam_root, GAME_META[game_key][0], names)
        except Exception:
            _log.debug("launch menu removal failed", exc_info=True)

    meta     = _read_metadata(install_dir)
    plut_dir = meta.get("plut_dir", "")
    if plut_dir and os.path.isdir(plut_dir):
        shutil.rmtree(plut_dir)

    # Clean up Heroic entries if this was an LCD Heroic install
    if meta.get("lcd_heroic"):
        try:
            from plutonium_lcd import cleanup_heroic_game
            cleanup_heroic_game(game_key)
        except Exception:
            pass  # Non-fatal - Heroic may not be installed

    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
