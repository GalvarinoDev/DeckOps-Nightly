"""
plutonium_oled.py - DeckOps installer for Plutonium (OLED path)
(Call of Duty: MW3, World at War, Black Ops, Black Ops II)

LCD Decks are dispatched to plutonium_lcd.py early in
install_plutonium(). Everything below the LCD dispatch is OLED-only.

OLED flow:
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
import urllib.request


# ── dedicated prefix ──────────────────────────────────────────────────────────
# DeckOps manages its own Wine prefix for the initial Plutonium install.
# This avoids depending on Steam to create a non-Steam game entry and gives
# us a known, stable path to copy from.

DEDICATED_PREFIX = os.path.expanduser("~/.local/share/deckops/plutonium_prefix")
PLUT_BOOTSTRAPPER_URL = "https://cdn.plutonium.pw/updater/plutonium.exe"


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

# DeckOps client-side menu mods packaged as .iwd files (renamed .zip).
# Downloaded from the repo and placed in Plutonium's storage/t6/raw/
# directory where they are loaded automatically on game launch.
# Internal .iwd path is ui/t6/mainlobby.lua for both MP and ZM.
MENU_MOD_BASE_URL = "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/main/assets/mods"
MENU_MOD_FILES = {
    "t6mp": ("t6/t6mp/deckops_menu.iwd", "storage/t6/raw/deckops_menu.iwd"),
    "t6zm": ("t6/t6zm/deckops_menu_zm.iwd", "storage/t6/raw/deckops_menu_zm.iwd"),
    "iw5mp": ("iw5mp/main.lua", "storage/iw5/ui_mp/main.lua"),
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
    because it does not require a login. Used for LCD users who run
    Plutonium in offline LAN mode and never need to authenticate.
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
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(PLUT_BOOTSTRAPPER_URL, headers=_headers)
            with urllib.request.urlopen(req, timeout=60) as r, open(bootstrapper, "wb") as f:
                f.write(r.read())
            break
        except Exception as ex:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    prog(15, "Launching Plutonium , please log in, then close the window when done.")

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"]           = DEDICATED_PREFIX
    # STEAM_COMPAT_CLIENT_INSTALL_PATH should point to the Steam root,
    # not the Proton install dir. Proton uses this to find steamclient.so.
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

    import time

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


def _copy_plut_to_prefix(src_plut_dir: str, dest_plut_dir: str,
                          on_progress=None):
    """
    Set up Plutonium in a game prefix using symlinks for shared dirs.

    bin/, launcher/, and games/ are symlinked to the shared copy at
    ~/.local/share/deckops/plutonium_shared/. Only storage/ (per-game
    configs and caches) is copied as real files.

    Falls back to full copy if shared dirs aren't available.
    """
    import time

    def prog(msg):
        if on_progress:
            on_progress(msg)

    prog(f"  Copying Plutonium: {src_plut_dir} -> {dest_plut_dir}")

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

        # Copy storage/ as real files (per-game data)
        storage_src = os.path.join(src_plut_dir, subdir)
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
            data[path_key] = _wine_path(install_dir)

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


# ── client-side menu mods ────────────────────────────────────────────────────

def _install_menu_mod(dest_plut_dir: str, game_key: str, on_progress=None):
    """
    Download and install the DeckOps menu mod for the given game key.

    Downloads a pre-built .iwd file (renamed .zip) from the repo and
    places it in the prefix's Plutonium storage path at raw/. Plutonium
    loads .iwd files from raw/ automatically on game launch, overriding
    the default main menu with the DeckOps community version (server
    connect, unlock all, reset stats buttons).

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

    remote_path, local_path = MENU_MOD_FILES[game_key]
    url = f"{MENU_MOD_BASE_URL}/{remote_path}"
    dest_file = os.path.join(dest_plut_dir, local_path)

    prog(f"  Installing DeckOps menu mod for {game_key}...")

    os.makedirs(os.path.dirname(dest_file), exist_ok=True)

    import time
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            with open(dest_file, "wb") as f:
                f.write(data)
            prog(f"  ✓ Menu mod installed ({len(data)} bytes)")
            return
        except Exception as ex:
            if attempt == 2:
                prog(f"  ⚠ Menu mod download failed: {ex}")
                return  # Non-fatal -- game still works without the mod
            time.sleep(2 ** attempt)


# ── wrapper script ────────────────────────────────────────────────────────────

def _write_oled_own_wrapper(game: dict, game_key: str, steam_root: str,
                             proton_path: str, compatdata_path: str,
                             plut_dir: str) -> str | None:
    """
    Write a standalone wrapper exe for OLED own games.

    Creates a new file (e.g. t4plutmp.exe) in the game's install dir that
    launches the Plutonium launcher with a protocol URL. The original game
    exe is left untouched. shortcut.py points the non-Steam shortcut at
    this wrapper, and the launcher uses the stored wrapper_path to launch it.

    Returns the full path to the written wrapper, or None if game_key
    is not in OLED_OWN_WRAPPER_EXES.
    """
    if game_key not in OLED_OWN_WRAPPER_EXES:
        return None

    install_dir  = game["install_dir"]
    wrapper_name = OLED_OWN_WRAPPER_EXES[game_key]
    wrapper_path = os.path.join(install_dir, wrapper_name)

    launcher = os.path.join(plut_dir, "bin",
                            "plutonium-launcher-win32.exe")
    plut_url = f"plutonium://play/{game_key}"

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


def _write_wrapper(game: dict, game_key: str, steam_root: str,
                   proton_path: str, compatdata_path: str, plut_dir: str):
    """
    Replace the game exe with a bash wrapper that launches Plutonium
    through Proton. OLED only — LCD uses plutonium_lcd.py.

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

    # Read original size before we overwrite
    original_size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0

    # Back up original exe
    if not os.path.exists(backup_path) and os.path.exists(exe_path):
        shutil.copy2(exe_path, backup_path)
        original_size = os.path.getsize(backup_path)

    # OLED online mode: call the launcher with a protocol URL
    launcher = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")
    plut_url = f"plutonium://play/{game_key}"
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


# ── public API ────────────────────────────────────────────────────────────────

def install_plutonium(game: dict, game_key: str, steam_root: str,
                      proton_path: str, compatdata_path: str,
                      on_progress=None, installed_games: dict = None,
                      source: str = "steam"):
    """
    Full install flow for a single Plutonium game.

    LCD Decks are dispatched to plutonium_lcd.py early
    in this function. Everything after the dispatch is OLED-only.

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
    # This function is OLED-only past this point.
    import config as _cfg_lcd
    if not _cfg_lcd.is_oled():
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

    # OLED only past this point (LCD returns early above).
    # Plutonium files go into Steam's compatdata prefix for the game,
    # because OLED launches the game through a bash wrapper that Steam runs
    # inside that same prefix. Use the compatdata_path passed by the caller
    # for correct SD card handling via find_compatdata().
    dest_plut_dir = os.path.join(
        compatdata_path, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )

    prog(10, f"Copying Plutonium into prefix for {game['name']}...")
    _copy_plut_to_prefix(
        src_plut_dir, dest_plut_dir,
        on_progress=lambda msg: prog(40, msg),
    )

    prog(60, "Writing game path to config.json...")
    # Pass all keys that share this appid so config has all paths for this prefix.
    # installed_games must contain ALL installed games, not just the current one,
    # so sibling keys (e.g. t4sp + t4mp share appid 10090) get their paths written too.
    appid = GAME_META[game_key][0]
    keys_for_appid = [k for k, v in GAME_META.items() if v[0] == appid]
    _write_config(dest_plut_dir, keys_for_appid, installed_games)

    # Install DeckOps client-side menu mod (e.g. mainlobby.lua for T6 MP).
    # OLED only -- LCD handles its own setup in plutonium_lcd.py.
    prog(65, "Installing menu mod...")
    _install_menu_mod(dest_plut_dir, game_key,
                      on_progress=lambda msg: prog(67, msg))

    # ── OLED only past this point ────────────────────────────────────────
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

        prog(95, "Saving metadata...")
        _write_metadata(game["install_dir"], {
            "game_key":    game_key,
            "plut_dir":    dest_plut_dir,
        })
    else:
        # OLED Steam games: replace the original exe with a bash wrapper
        prog(80, "Writing launcher wrapper...")
        _write_wrapper(game, game_key, steam_root, proton_path,
                       compatdata_path, dest_plut_dir)

        prog(95, "Saving metadata...")
        _write_metadata(game["install_dir"], {
            "game_key":    game_key,
            "plut_dir":    dest_plut_dir,
            "wrapper_exe": os.path.join(game["install_dir"],
                                        GAME_META[game_key][2]),
        })

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
