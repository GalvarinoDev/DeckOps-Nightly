"""
plutonium.py - DeckOps installer for Plutonium
(Call of Duty: MW3, World at War, Black Ops, Black Ops II)

Flow:
  1. Download plutonium.exe into a dedicated DeckOps-managed Wine prefix.
  2. Launch it through Proton so the user can log in and let Plutonium
     download its full client.
  3. Wait for user confirmation that they have logged in and closed Plutonium.
  4. Verify by checking that the storage/ folder exists in the prefix.
  5. Copy the entire Plutonium/ folder into each selected game's prefix.
  6. If the game requires XACT (t4/t5 titles), install it into that prefix.
  7. Write config.json in each prefix with the correct game install paths.
  8. Write a bash wrapper script that replaces the game exe, padded to the
     original exe size so Steam's file validation does not flag it.

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import hashlib
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

# All Plutonium games run in offline LAN mode on LCD Decks. These use the
# bootstrapper directly with -lan instead of the normal launcher.
# LCD Decks cannot connect to Plutonium online servers.
LCD_OFFLINE_KEYS = {"t4sp", "t4mp", "t5sp", "t5mp", "t6zm", "t6mp", "iw5mp"}

# Games that require XACT for audio to work correctly under Proton.
# Matches the xact=True flags in detect_games.py.
XACT_GAME_KEYS = {"t4sp", "t4mp", "t5sp", "t5mp"}

# DLLs dropped by the winetricks xact verb. We copy these directly between
# prefixes instead of re-running protontricks for each game.
XACT_DLLS = [
    "xactengine2_0.dll",
    "xactengine2_1.dll",
    "xactengine2_2.dll",
    "xactengine2_3.dll",
    "xactengine2_4.dll",
    "xactengine2_5.dll",
    "xactengine2_6.dll",
    "xactengine2_7.dll",
    "xactengine2_8.dll",
    "xactengine2_9.dll",
    "xactengine3_0.dll",
    "xactengine3_1.dll",
    "xactengine3_2.dll",
    "xactengine3_3.dll",
    "xactengine3_4.dll",
    "xactengine3_5.dll",
    "xactengine3_6.dll",
    "xactengine3_7.dll",
    "xact3.dll",
    "xaudio2_0.dll",
]

# Wrapper exe names for own LCD games. These are standalone bash scripts
# written into the game directory - they don't replace any original exe.
# The shortcut points at these instead of the bootstrapper directly.
OWN_WRAPPER_EXES = {
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
# Currently only T6 MP has a custom menu. ZM version not built yet.
MENU_MOD_BASE_URL = "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/main/assets/mods/t6"
MENU_MOD_FILES = {
    "t6mp": ("t6mp/deckops_menu.iwd", "storage/t6/raw/deckops_menu.iwd"),
}


# ── DirectX June 2010 redist ──────────────────────────────────────────────────
# XACT DLLs are extracted from this single cabinet file by winetricks.
# We pre-download it ourselves so protontricks finds it cached and skips
# the download entirely — letting us run this concurrently with other
# large downloads (Plutonium bootstrapper, GE-Proton, etc.).
#
# URL sourced from the winetricks script bundled with protontricks Flatpak:
#   flatpak run --command=sh com.github.Matoking.protontricks \
#     -c "grep -A3 'helper_directx_Jun2010' \$(which winetricks)"

DIRECTX_JUN2010_URL    = "https://files.holarse-linuxgaming.de/mirrors/microsoft/directx_Jun2010_redist.exe"
DIRECTX_JUN2010_SHA256 = "8746ee1a84a083a90e37899d71d50d5c7c015e69688a466aa80447f011780c0d"

# Flatpak protontricks uses a sandboxed cache path. Native protontricks
# uses the standard XDG cache. We write to whichever is appropriate based
# on which protontricks is available.
_DIRECTX_CACHE_FLATPAK = os.path.expanduser(
    "~/.var/app/com.github.Matoking.protontricks/cache/winetricks/directx9"
)
_DIRECTX_CACHE_NATIVE = os.path.expanduser(
    "~/.cache/winetricks/directx9"
)


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


def _system32(compatdata_path: str) -> str:
    """Return the system32 path inside a Wine prefix."""
    return os.path.join(compatdata_path, "pfx", "drive_c", "windows", "system32")


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


# ── xact ──────────────────────────────────────────────────────────────────────

def _is_xact_installed(compatdata_path: str) -> bool:
    """
    Check whether XACT is installed in a given Wine prefix.
    We look for xactengine2_0.dll in system32 — it's the reliable sentinel
    that's present in every prefix after a successful install.
    (xact3.dll is never present in practice even when audio works fine,
    so we no longer check for it.)
    """
    sys32 = _system32(compatdata_path)
    sentinel = os.path.join(sys32, "xactengine2_0.dll")
    return os.path.exists(sentinel) and os.path.getsize(sentinel) > 0


def _needs_xact_download(xact_game_keys: list[str], steam_root: str) -> bool:
    """
    Returns True if any Steam XACT game prefix is missing xactengine2_0.dll,
    meaning we need to download directx_Jun2010_redist.exe and run protontricks.

    Also checks the dedicated plutonium prefix itself since that's the primary
    install target before DLLs are copied out to game prefixes.

    Only checks Steam-path prefixes (appid-based compatdata). Own game prefixes
    are not checked here — own games always need the download since their
    shortcut appids are DeckOps-generated and we don't track them here.
    """
    # Check the dedicated plutonium prefix first
    if not _is_xact_installed(DEDICATED_PREFIX):
        return True

    # Check each Steam game prefix
    from detect_games import _all_library_dirs
    seen_appids = set()
    for key in xact_game_keys:
        if key not in GAME_META:
            continue
        appid = GAME_META[key][0]
        if appid in seen_appids:
            continue
        seen_appids.add(appid)

        # Search all library dirs so SD card installs are covered
        compat = None
        for lib_dir in _all_library_dirs(steam_root):
            candidate = os.path.join(lib_dir, "compatdata", str(appid))
            if os.path.isdir(candidate):
                compat = candidate
                break

        if compat is None or not _is_xact_installed(compat):
            return True

    return False


def _get_directx_cache_path() -> str:
    """
    Return the correct winetricks cache directory for directx_Jun2010_redist.exe
    based on which protontricks is available. Flatpak uses a sandboxed path,
    native uses the standard XDG cache.
    """
    # Check for Flatpak protontricks first (most common on Steam Deck)
    try:
        result = subprocess.run(
            ["flatpak", "info", "com.github.Matoking.protontricks"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return _DIRECTX_CACHE_FLATPAK
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return _DIRECTX_CACHE_NATIVE


def download_directx_jun2010(on_progress=None) -> bool:
    """
    Pre-download directx_Jun2010_redist.exe into the winetricks cache so
    protontricks finds it already cached and skips the download entirely.

    Designed to be called concurrently alongside other large downloads
    (Plutonium bootstrapper, GE-Proton, etc.) via threading.

    Skips if the file already exists and its sha256 matches.
    Returns True on success, False on failure.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    cache_dir  = _get_directx_cache_path()
    cache_file = os.path.join(cache_dir, "directx_Jun2010_redist.exe")

    # Check if already cached with a valid sha256
    if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
        prog("Verifying cached DirectX Jun2010 redist...")
        sha256 = hashlib.sha256()
        with open(cache_file, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        if sha256.hexdigest() == DIRECTX_JUN2010_SHA256:
            prog("DirectX Jun2010 redist already cached, skipping download.")
            return True
        else:
            prog("Cached file checksum mismatch, re-downloading...")

    os.makedirs(cache_dir, exist_ok=True)
    prog("Downloading DirectX Jun2010 redist (95 MB)...")

    import time
    for attempt in range(3):
        try:
            with urllib.request.urlopen(DIRECTX_JUN2010_URL, timeout=120) as r, \
                 open(cache_file, "wb") as f:
                f.write(r.read())
            break
        except Exception as ex:
            if attempt == 2:
                prog(f"DirectX Jun2010 download failed: {ex}")
                return False
            time.sleep(2 ** attempt)

    # Verify sha256 after download
    prog("Verifying DirectX Jun2010 redist...")
    sha256 = hashlib.sha256()
    with open(cache_file, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    if sha256.hexdigest() != DIRECTX_JUN2010_SHA256:
        prog("DirectX Jun2010 checksum mismatch after download — file may be corrupt.")
        os.remove(cache_file)
        return False

    prog("DirectX Jun2010 redist downloaded and verified.")
    return True


def _find_protontricks() -> list[str] | None:
    """
    Locate protontricks, preferring the Flatpak version.
    Returns the command prefix as a list, or None if not found.

    Preference order:
      1. Flatpak protontricks (com.github.Matoking.protontricks)
      2. Native protontricks on PATH
    """
    # Check Flatpak first , most common on Steam Deck
    try:
        result = subprocess.run(
            ["flatpak", "info", "com.github.Matoking.protontricks"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return ["flatpak", "run", "com.github.Matoking.protontricks"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to native protontricks
    try:
        result = subprocess.run(
            ["protontricks", "--version"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return ["protontricks"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _ensure_protontricks_sd_access():
    """
    Grant the Flatpak protontricks access to /run/media so it can see
    games installed on the SD card. Safe to call multiple times.
    Errors are swallowed silently , this is best-effort and non-fatal
    since the game prefix may still be on internal storage.
    """
    try:
        subprocess.run(
            [
                "flatpak", "override", "--user",
                "com.github.Matoking.protontricks",
                "--filesystem=/run/media",
            ],
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _ensure_protontricks(on_progress=None) -> bool:
    """
    Ensure protontricks is available, installing it via Flatpak if needed.
    Also applies the /run/media filesystem override for SD card access.
    Returns True if protontricks is available after this call.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    if _find_protontricks() is not None:
        _ensure_protontricks_sd_access()
        return True

    prog("Installing Protontricks (required for game audio)...")
    try:
        result = subprocess.run(
            [
                "flatpak", "install", "--user", "--noninteractive",
                "flathub", "com.github.Matoking.protontricks",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            prog("Protontricks installed successfully.")
            _ensure_protontricks_sd_access()
            return True
        else:
            prog(
                "Protontricks installation failed , XACT will be skipped. "
                "Install Protontricks from Discover and rerun setup."
            )
            return False
    except FileNotFoundError:
        prog("Flatpak not found , cannot install Protontricks.")
        return False


def _install_xact(compatdata_path: str, proton_path: str,
                  steam_root: str, appid: int, game_name: str = "",
                  on_progress=None):
    """
    Install XACT into the given Wine prefix using protontricks.
    Required for audio in World at War and Black Ops.
    Skips silently if already installed.

    compatdata_path , path to this game's compatdata prefix
    proton_path     , kept for API consistency, not used
    steam_root      , kept for API consistency, not used
    appid           , Steam appid or shortcut appid (protontricks handles both)
    game_name       , display name shown in progress messages
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    label = f" for {game_name}" if game_name else ""

    if _is_xact_installed(compatdata_path):
        prog(f"XACT already installed{label}, skipping.")
        return True

    prog(f"Installing XACT audio components{label}...")

    protontricks = _find_protontricks()
    if protontricks is None:
        prog(
            "protontricks not found , skipping XACT. "
            "Install via Discover (search Protontricks) and rerun setup."
        )
        return False

    # Ensure SD card access so protontricks can find the game prefix
    _ensure_protontricks_sd_access()

    cmd = protontricks + [str(appid), "-q", "xact"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            prog("XACT installed successfully.")
            return True
        else:
            # A non-zero exit from protontricks/winetricks is often just
            # a warning rather than a hard failure , verify via DLL check.
            if _is_xact_installed(compatdata_path):
                prog("XACT installed successfully.")
                return True
            prog("XACT install finished with warnings , audio may still work.")
            return False
    except subprocess.TimeoutExpired:
        prog("XACT install timed out , skipping.")
        return False


def _copy_xact_dlls(src_compatdata: str, dst_compatdata: str, on_progress=None):
    """
    Copy XACT DLLs from one prefix's system32 to another's.
    Only copies files that actually exist in src — winetricks may not
    install all versions depending on the Wine build.
    """
    src_sys32 = _system32(src_compatdata)
    dst_sys32 = _system32(dst_compatdata)
    os.makedirs(dst_sys32, exist_ok=True)
    copied = 0
    for dll in XACT_DLLS:
        src = os.path.join(src_sys32, dll)
        if os.path.exists(src) and os.path.getsize(src) > 0:
            shutil.copy2(src, os.path.join(dst_sys32, dll))
            copied += 1
    if on_progress:
        on_progress(f"Copied {copied} XACT DLLs.")


def install_xact_once(
    xact_game_keys: list[str],
    steam_root: str,
    proton_path: str,
    on_progress=None,
    own_xact_targets: list[tuple[int, str]] | None = None,
) -> bool:
    """
    Install XACT into all required prefixes as efficiently as possible.

    For Steam games:
      - Checks all relevant prefixes first. If XACT is already installed
        everywhere, skips the download and protontricks entirely.
      - Otherwise pre-downloads directx_Jun2010_redist.exe (should already
        be cached if download_directx_jun2010() was called concurrently
        earlier), then runs protontricks on the first prefix and copies
        DLLs to the rest.

    For own games (own_xact_targets):
      - Always runs protontricks — no skip check since shortcut appids
        are DeckOps-generated and we don't track their prefix state.
      - Expects directx_Jun2010_redist.exe to already be cached from
        the concurrent pre-download.

    xact_game_keys     , Steam game keys that need XACT (subset of XACT_GAME_KEYS)
    steam_root         , path to Steam root
    proton_path        , kept for API consistency
    own_xact_targets   , list of (shortcut_appid, compatdata_path) for own games
                         that need XACT. Pass None or [] if no own games.

    Returns True if XACT is available in all target prefixes after this call.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    own_xact_targets = own_xact_targets or []
    has_steam_keys   = bool(xact_game_keys)
    has_own_targets  = bool(own_xact_targets)

    if not has_steam_keys and not has_own_targets:
        return True

    # ── Steam games: check if we can skip everything ──────────────────────────
    steam_needs_install = has_steam_keys and _needs_xact_download(xact_game_keys, steam_root)

    if not steam_needs_install and not has_own_targets:
        prog("XACT already installed in all prefixes, skipping.")
        return True

    # ── Ensure protontricks is available ──────────────────────────────────────
    if not _ensure_protontricks(on_progress=on_progress):
        return False

    # ── Pre-download directx_Jun2010_redist.exe if not already cached ─────────
    # This should be a no-op if download_directx_jun2010() was already called
    # concurrently during the main download phase. If it wasn't (e.g. caller
    # skipped the concurrent step), we download it here as a fallback.
    if not download_directx_jun2010(on_progress=on_progress):
        prog("DirectX Jun2010 download failed — XACT install may be slow or fail.")
        # Don't abort — protontricks will try its own download as a last resort

    # ── Steam games ───────────────────────────────────────────────────────────
    if has_steam_keys and steam_needs_install:
        # Build deduped list of (key, appid, compatdata_path) by appid.
        # Search all library dirs so SD card installs are found.
        from detect_games import _all_library_dirs
        seen_appids = {}
        targets = []
        for key in xact_game_keys:
            if key not in GAME_META:
                continue
            appid = GAME_META[key][0]
            if appid not in seen_appids:
                compat = None
                for lib_dir in _all_library_dirs(steam_root):
                    candidate = os.path.join(lib_dir, "compatdata", str(appid))
                    if os.path.isdir(candidate):
                        compat = candidate
                        break
                if not compat:
                    # Fallback to default location (may not exist yet)
                    compat = os.path.join(
                        steam_root, "steamapps", "compatdata", str(appid)
                    )
                seen_appids[appid] = compat
                targets.append((key, appid, compat))

        if targets:
            # Install into the first prefix via protontricks.
            primary_key, primary_appid, primary_compat = targets[0]
            prog(f"Installing XACT into primary prefix (appid {primary_appid})...")
            success = _install_xact(
                primary_compat, proton_path, steam_root,
                appid=primary_appid,
                game_name=primary_key,
                on_progress=on_progress,
            )

            if not success:
                prog("XACT install failed on primary prefix — skipping copy step.")
                return False

            # Copy DLLs to remaining Steam prefixes instead of re-running protontricks.
            for key, appid, compat in targets[1:]:
                if _is_xact_installed(compat):
                    prog(f"XACT already present in prefix {appid}, skipping.")
                    continue
                prog(f"Copying XACT DLLs to prefix {appid}...")
                _copy_xact_dlls(primary_compat, compat, on_progress=on_progress)

    # ── Own games ─────────────────────────────────────────────────────────────
    # Shortcut appids are DeckOps-generated so protontricks can resolve them.
    # We run protontricks per-prefix since we can't safely dedupe by appid here.
    for shortcut_appid, compatdata_path in own_xact_targets:
        prog(f"Installing XACT for own game (appid {shortcut_appid})...")
        _install_xact(
            compatdata_path, proton_path, steam_root,
            appid=shortcut_appid,
            game_name=f"own:{shortcut_appid}",
            on_progress=on_progress,
        )

    return True


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

def _write_wrapper(game: dict, game_key: str, steam_root: str,
                   proton_path: str, compatdata_path: str, plut_dir: str,
                   lan_mode: bool = False):
    """
    Replace the game exe with a bash wrapper that launches Plutonium
    through Proton.

    When lan_mode is False (OLED / online):
        Calls plutonium-launcher-win32.exe with a protocol URL.
        Requires the user to have logged in.

    When lan_mode is True (LCD / offline):
        Calls plutonium-bootstrapper-win32.exe directly with -lan.
        No login required. Game starts in offline LAN mode.
        cd's into the Plutonium directory first so the bootstrapper
        can find its files relative to cwd.

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

    if lan_mode:
        # LCD offline mode: call the bootstrapper directly with -lan.
        # cd into the Plutonium directory first so the bootstrapper can
        # find its files relative to cwd, same as LanLauncher does.
        import config as _cfg
        player_name = _cfg.get_player_name() or "Player"
        bootstrapper = os.path.join(plut_dir, "bin", "plutonium-bootstrapper-win32.exe")
        game_dir_wine = _wine_path(install_dir)
        script = (
            "#!/bin/bash\n"
            f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
            f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
            f"cd \"{plut_dir}\"\n"
            f"exec \"{proton_path}\" run \"{bootstrapper}\" "
            f"{game_key} \"{game_dir_wine}\" +name \"{player_name}\" -lan\n"
        )
    else:
        # OLED online mode: call the launcher with a protocol URL
        launcher = os.path.join(plut_dir, "bin", "plutonium-launcher-win32.exe")
        plut_url = f"plutonium://play/{game_key}"
        script = (
            "#!/bin/bash\n"
            f"export STEAM_COMPAT_DATA_PATH=\"{compatdata_path}\"\n"
            f"export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"{steam_root}\"\n"
            f"exec \"{proton_path}\" run \"{launcher}\" \"{plut_url}\"\n"
        )

    script_bytes = script.encode("utf-8")
    if original_size > len(script_bytes):
        script_bytes += b"\x00" * (original_size - len(script_bytes))

    with open(exe_path, "wb") as f:
        f.write(script_bytes)

    os.chmod(exe_path, os.stat(exe_path).st_mode |
             stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_own_wrapper(game: dict, game_key: str, steam_root: str,
                       proton_path: str, compatdata_path: str, plut_dir: str):
    """
    Write a standalone wrapper exe for own LCD games.

    Same bash script as the Steam LCD wrapper but written as a new file
    (e.g. t4plutmp.exe) instead of replacing the original game exe.
    No backup, no padding - the original exe is left untouched.
    """
    install_dir = game["install_dir"]
    wrapper_name = OWN_WRAPPER_EXES[game_key]
    wrapper_path = os.path.join(install_dir, wrapper_name)

    import config as _cfg
    player_name = _cfg.get_player_name() or "Player"
    bootstrapper = os.path.join(plut_dir, "bin", "plutonium-bootstrapper-win32.exe")
    game_dir_wine = _wine_path(install_dir)

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
                      protontricks_ready: bool = False,
                      source: str = "steam"):
    """
    Full install flow for a single Plutonium game.

    Assumes the user has already logged in and closed Plutonium via
    launch_bootstrapper(), and is_plutonium_ready() has returned True.

    game               , entry from detect_games.find_installed_games()
    game_key           , one of: t4sp, t4mp, t5sp, t5mp, t6zm, t6mp, iw5mp
    steam_root         , path to Steam root
    proton_path        , path to the proton executable
    compatdata_path    , path to this game's compatdata prefix
    on_progress        , optional callback(percent: int, status: str)
    protontricks_ready , True if _ensure_protontricks() has already been called
                         by the caller. Avoids redundant detection per-game.
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # Fall back to single-game dict if caller doesn't supply full installed_games.
    # Supplying the full dict is preferred so sibling keys get correct paths.
    if installed_games is None:
        installed_games = {game_key: game}

    src_plut_dir  = get_dedicated_plut_dir()

    # Ensure shared Plutonium dirs are set up (one-time, shared across games)
    _ensure_shared_plutonium(src_plut_dir,
                             on_progress=lambda msg: prog(5, msg))

    # Use the compatdata_path passed by the caller for both source modes.
    # The caller resolves the correct path via find_compatdata() which
    # searches all library dirs including SD card. Using steam_root directly
    # (the old approach) always built the internal path, breaking SD card games.
    dest_plut_dir = os.path.join(
        compatdata_path, "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", "Plutonium",
    )

    prog(10, f"Copying Plutonium into prefix for {game['name']}...")
    _copy_plut_to_prefix(
        src_plut_dir, dest_plut_dir,
        on_progress=lambda msg: prog(40, msg),
    )

    # Install XACT into this game's prefix if required.
    # Only runs for t4/t5 titles , skipped entirely for t6/iw5.
    # Own games handle XACT externally via install_xact_once with
    # own_xact_targets so protontricks gets the correct shortcut appid.
    if source != "own" and game_key in XACT_GAME_KEYS:
        prog(50, f"Installing XACT audio components for {game['name']}...")
        if protontricks_ready:
            _install_xact(
                compatdata_path, proton_path, steam_root,
                appid=GAME_META[game_key][0],
                game_name=game["name"],
                on_progress=lambda msg: prog(55, msg),
            )
        else:
            prog(55, "XACT skipped , Protontricks unavailable.")

    prog(60, "Writing game path to config.json...")
    # Pass all keys that share this appid so config has all paths for this prefix.
    # installed_games must contain ALL installed games, not just the current one,
    # so sibling keys (e.g. t4sp + t4mp share appid 10090) get their paths written too.
    appid = GAME_META[game_key][0]
    keys_for_appid = [k for k, v in GAME_META.items() if v[0] == appid]
    _write_config(dest_plut_dir, keys_for_appid, installed_games)

    # Install DeckOps client-side menu mod (e.g. mainlobby.lua for T6 MP).
    # Runs for both Steam and own installs, both LCD and OLED.
    prog(65, "Installing menu mod...")
    _install_menu_mod(dest_plut_dir, game_key,
                      on_progress=lambda msg: prog(67, msg))

    # Own game shortcuts point at Plutonium directly -- no wrapper needed.
    # Steam games replace the original exe with a bash wrapper.
    if source != "own":
        prog(80, "Writing launcher wrapper...")
        import config as _cfg
        lan_mode = (not _cfg.is_oled()) and (game_key in LCD_OFFLINE_KEYS)
        _write_wrapper(game, game_key, steam_root, proton_path,
                       compatdata_path, dest_plut_dir, lan_mode=lan_mode)

        prog(95, "Saving metadata...")
        _write_metadata(game["install_dir"], {
            "game_key":    game_key,
            "plut_dir":    dest_plut_dir,
            "wrapper_exe": os.path.join(game["install_dir"],
                                        GAME_META[game_key][2]),
        })
    else:
        # Own LCD games get a standalone wrapper exe (e.g. t4plutmp.exe)
        # so the shortcut can launch the bootstrapper with the right env.
        # OLED own games don't need a wrapper - shortcuts point at the
        # launcher directly with plutonium://play/<key>.
        import config as _cfg
        if not _cfg.is_oled() and game_key in LCD_OFFLINE_KEYS:
            prog(80, "Writing LCD launcher wrapper...")
            _write_own_wrapper(game, game_key, steam_root, proton_path,
                               compatdata_path, dest_plut_dir)

            prog(95, "Saving metadata...")
            _write_metadata(game["install_dir"], {
                "game_key":    game_key,
                "plut_dir":    dest_plut_dir,
                "wrapper_exe": os.path.join(game["install_dir"],
                                            OWN_WRAPPER_EXES[game_key]),
            })

    prog(100, f"Plutonium ready for {game['name']}!")


def uninstall_plutonium(game: dict, game_key: str):
    """
    Restore the original game exe from backup and remove the
    Plutonium folder from this game's prefix.
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

    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
