"""
cod4x.py - DeckOps installer for CoD4x (Call of Duty 4: Modern Warfare)

Replicates the official CoD4x 21.3 installer behavior without running
the setup.exe or requiring any user interaction. Downloads files from
three GitHub repos and places them in both the game directory and the
Wine prefix's AppData folder.

The CoD4x chain-loader mechanism:
  1. mss32.dll in the game directory is replaced with the CoD4x version.
     The original is backed up as miles32.dll. CoD4 loads mss32.dll at
     startup via PE imports, so this is the entry point for the mod.
  2. The new mss32.dll loads launcher.dll from AppData/Local/CallofDuty4MW/bin/.
  3. launcher.dll loads cod4x_021.dll from AppData/Local/CallofDuty4MW/bin/cod4x_021/.
  4. cod4x_021.dll patches the game in memory to become CoD4x 21.3.

Game directory files (install_dir/):
  mss32.dll    — replaced with CoD4x chain-loader (original → miles32.dll)
  iw3mp.exe    — replaced with CoD4x launcher (original → iw3mp.exe.bak)

Wine prefix files (AppData/Local/CallofDuty4MW/):
  bin/launcher.dll               — glue between mss32.dll and the mod DLL
  bin/iw3mp.exe                  — copy of the CoD4x launcher
  bin/cod4x_021/cod4x_021.dll    — the actual mod DLL
  main/jcod4x_00.iwd             — mod assets
  zone/cod4x_patch.ff            — zone patches
  zone/cod4x_patchv2.ff
  zone/cod4x_ambfix.ff

Download sources:
  CoD4x_Client_pub 21.3  — cod4x_021.dll, zone files, iwd, core (iw3mp.exe zip), mss (mss32.dll zip)
  CoD4x-launcher 1.1.2   — launcher.dll
"""

import os
import json
import shutil
import zipfile
import threading
import urllib.request

# ── download URLs ─────────────────────────────────────────────────────────────
# Files come from three repos in the callofduty4x GitHub org.

_CLIENT_PUB_BASE = "https://github.com/callofduty4x/CoD4x_Client_pub/releases/download/21.3"
_LAUNCHER_BASE   = "https://github.com/callofduty4x/CoD4x-launcher/releases/download/1.1.2"

# Files that go into the Wine prefix AppData/Local/CallofDuty4MW/ structure.
# (url, dest_subdir_relative_to_appdata_root, final_filename_or_None_for_zip)
_PREFIX_DOWNLOADS = [
    (f"{_CLIENT_PUB_BASE}/cod4x_021.dll",    os.path.join("bin", "cod4x_021"), "cod4x_021.dll"),
    (f"{_CLIENT_PUB_BASE}/cod4x_patch.ff",   "zone",                           "cod4x_patch.ff"),
    (f"{_CLIENT_PUB_BASE}/cod4x_patchv2.ff", "zone",                           "cod4x_patchv2.ff"),
    (f"{_CLIENT_PUB_BASE}/cod4x_ambfix.ff",  "zone",                           "cod4x_ambfix.ff"),
    (f"{_CLIENT_PUB_BASE}/jcod4x_00.iwd",    "main",                           "jcod4x_00.iwd"),
    (f"{_LAUNCHER_BASE}/launcher.dll",        "bin",                            "launcher.dll"),
]

# Files that go into the game directory (install_dir/).
# core and mss are zip files that extract iw3mp.exe and mss32.dll respectively.
_GAME_DIR_DOWNLOADS = [
    (f"{_CLIENT_PUB_BASE}/core", None, "core.zip"),   # zip → iw3mp.exe
    (f"{_CLIENT_PUB_BASE}/mss",  None, "mss.zip"),    # zip → mss32.dll
]

METADATA_FILE = "deckops_cod4x.json"

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

# ── backup and cleanup lists ──────────────────────────────────────────────────
# CoD4x renames mss32.dll → miles32.dll (not .bak) to match the official
# installer convention. iw3mp.exe gets a .bak extension.
_BACKUP_MAP = {
    "mss32.dll":  "miles32.dll",    # CoD4x convention: original mss32 → miles32
    "iw3mp.exe":  "iw3mp.exe.bak",
}

# The AppData subfolder name inside the Wine prefix. This is where the CoD4x
# launcher expects to find its DLLs, zone files, and iwd assets.
_APPDATA_FOLDER = "CallofDuty4MW"


# ── helpers ──────────────────────────────────────────────────────────────────

def _download(url: str, dest: str, on_progress=None, label: str = ""):
    """Download url to dest with browser-like headers. Retries up to 3 times."""
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_BROWSER_UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total:
                            on_progress(int(downloaded / total * 100), label)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def _write_metadata(install_dir: str, data: dict):
    """Write DeckOps metadata JSON to the game directory."""
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _get_appdata_dir(compatdata_path: str) -> str:
    """
    Return the AppData/Local/CallofDuty4MW path inside a Wine prefix.

    Works for both Steam and own game prefixes — the compatdata_path is
    resolved by the caller (ui_qt.py) before install_cod4x() is called,
    regardless of whether the game is on the NVME, SD card, or an own
    install with a DeckOps-generated shortcut appid.
    """
    return os.path.join(
        compatdata_path,
        "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", _APPDATA_FOLDER,
    )


# ── public API ───────────────────────────────────────────────────────────────

def install_cod4x(game: dict, steam_root: str, proton_path: str,
                  compatdata_path: str, on_progress=None, appid: int = 7940):
    """
    Downloads and installs CoD4x 21.3 by placing files in both the game
    directory and the Wine prefix. No setup.exe, no Proton subprocess,
    no popups.

    This replicates what the official CoD4x_21_3_Setup.exe does:
      1. Backs up mss32.dll → miles32.dll and iw3mp.exe → iw3mp.exe.bak
      2. Downloads the CoD4x chain-loader mss32.dll and launcher iw3mp.exe
         into the game directory
      3. Downloads launcher.dll, cod4x_021.dll, zone files, and iwd into
         the Wine prefix's AppData/Local/CallofDuty4MW/ structure

    Parameters:
      game            — dict from detect_games with install_dir, exe_path, etc.
      steam_root      — path to the Steam root directory
      proton_path     — path to the Proton executable (not used, kept for API compat)
      compatdata_path — path to the game's compatdata prefix (NVME, SD card, or own)
      on_progress     — optional callback(percent: int, status: str)
      appid           — Steam appid (not used, kept for API compat)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    install_dir = game["install_dir"]
    appdata_dir = _get_appdata_dir(compatdata_path)

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # ── Create prefix AppData directories ─────────────────────────────────
    # These mirror what the official installer's install.cmd creates.
    for subdir in ["bin/cod4x_021", "main", "zone"]:
        os.makedirs(os.path.join(appdata_dir, subdir), exist_ok=True)

    # ── Back up game directory files ──────────────────────────────────────
    # The official installer renames mss32.dll → miles32.dll (not .bak).
    # We follow the same convention so CoD4x's own uninstall logic matches.
    prog(2, "Backing up original files...")
    for original, backup_name in _BACKUP_MAP.items():
        src = os.path.join(install_dir, original)
        bak = os.path.join(install_dir, backup_name)
        if os.path.exists(src) and not os.path.exists(bak):
            shutil.copy2(src, bak)

    # ── Download all files concurrently ───────────────────────────────────
    prog(5, "Downloading CoD4x files...")

    # Build the combined download task list: (url, dest_path, label)
    dl_tasks = []

    # Prefix files (launcher.dll, cod4x_021.dll, zone files, iwd)
    for url, rel_dir, filename in _PREFIX_DOWNLOADS:
        dest_path = os.path.join(appdata_dir, rel_dir, filename)
        dl_tasks.append((url, dest_path, filename))

    # Game directory files (core.zip → iw3mp.exe, mss.zip → mss32.dll)
    for url, _, temp_name in _GAME_DIR_DOWNLOADS:
        dest_path = os.path.join(install_dir, temp_name)
        dl_tasks.append((url, dest_path, temp_name))

    dl_errors = []
    dl_done = [0]
    dl_lock = threading.Lock()

    def _dl(url, dest, label):
        _download(url, dest, None, f"Downloading {label}...")
        with dl_lock:
            dl_done[0] += 1
            prog(5 + int(dl_done[0] / len(dl_tasks) * 50),
                 f"Downloaded {label}")

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_dl, url, dest, label): label
                for url, dest, label in dl_tasks}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                dl_errors.append(f"{futs[fut]}: {e}")

    if dl_errors:
        raise RuntimeError("CoD4x download failed:\n" + "\n".join(dl_errors))

    # ── Extract zip assets into game directory ────────────────────────────
    # core.zip contains iw3mp.exe (the CoD4x launcher binary).
    # mss.zip contains mss32.dll (the CoD4x chain-loader).
    prog(60, "Extracting CoD4x assets...")
    for _, _, temp_name in _GAME_DIR_DOWNLOADS:
        zip_path = os.path.join(install_dir, temp_name)
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(install_dir)
            os.remove(zip_path)

    # ── Copy iw3mp.exe into prefix bin/ ───────────────────────────────────
    # The official installer places a copy of the CoD4x launcher in the
    # prefix's bin/ dir as well as in the game directory. The launcher DLL
    # expects to find it there.
    prog(70, "Copying launcher to prefix...")
    iw3mp_src  = os.path.join(install_dir, "iw3mp.exe")
    iw3mp_dest = os.path.join(appdata_dir, "bin", "iw3mp.exe")
    if os.path.exists(iw3mp_src):
        shutil.copy2(iw3mp_src, iw3mp_dest)

    # ── Delete servercache.dat ────────────────────────────────────────────
    # Force CoD4x to download a fresh server list on first launch.
    servercache = os.path.join(install_dir, "servercache.dat")
    if os.path.exists(servercache):
        os.remove(servercache)
        prog(80, "Cleared server cache.")

    # Also clear any stale servercache in the prefix AppData dir.
    prefix_cache = os.path.join(appdata_dir, "servercache.dat")
    if os.path.exists(prefix_cache):
        os.remove(prefix_cache)

    # ── Download globalconfig.cfg ─────────────────────────────────────────
    # The official launcher fetches this from the CoD4x server repo on
    # first run. We pre-download it so the first launch doesn't need
    # internet access for config.
    prog(85, "Fetching global config...")
    globalconfig_url  = "https://raw.githubusercontent.com/callofduty4x/CoD4x_Server/master/globalconfig.cfg"
    globalconfig_dest = os.path.join(appdata_dir, "globalconfig.cfg")
    try:
        _download(globalconfig_url, globalconfig_dest)
    except Exception:
        # Non-fatal: CoD4x will fetch it on first launch if we miss it here.
        pass

    # ── Write metadata ────────────────────────────────────────────────────
    prog(95, "Saving metadata...")
    _write_metadata(install_dir, {
        "version": "21.3",
        "appdata_dir": appdata_dir,
        "compatdata_path": compatdata_path,
    })

    prog(100, "CoD4x installation complete!")


def uninstall_cod4x(game: dict, compatdata_path: str = None):
    """
    Remove CoD4x files and restore original backups.

    Cleans up both the game directory (restores mss32.dll and iw3mp.exe)
    and the Wine prefix AppData structure.

    Parameters:
      game            — dict from detect_games with install_dir
      compatdata_path — path to the game's compatdata prefix. If None,
                        attempts to read it from the metadata file.
    """
    install_dir = game["install_dir"]

    # ── Restore game directory backups ────────────────────────────────────
    # Reverse the backup map: miles32.dll → mss32.dll, iw3mp.exe.bak → iw3mp.exe
    for original, backup_name in _BACKUP_MAP.items():
        bak  = os.path.join(install_dir, backup_name)
        orig = os.path.join(install_dir, original)
        if os.path.exists(bak):
            if os.path.exists(orig):
                os.remove(orig)
            os.rename(bak, orig)

    # ── Remove the prefix AppData folder ──────────────────────────────────
    # If compatdata_path wasn't passed, try to read it from metadata.
    if compatdata_path is None:
        meta_path = os.path.join(install_dir, METADATA_FILE)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                compatdata_path = meta.get("compatdata_path")
            except (json.JSONDecodeError, IOError):
                pass

    if compatdata_path:
        appdata_dir = _get_appdata_dir(compatdata_path)
        if os.path.isdir(appdata_dir):
            shutil.rmtree(appdata_dir, ignore_errors=True)

    # ── Remove metadata ───────────────────────────────────────────────────
    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
