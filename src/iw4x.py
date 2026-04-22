"""
iw4x.py - DeckOps installer for IW4x (Modern Warfare 2)

Downloads iw4x.dll and release.zip from the latest GitHub releases.
release.zip contains iw4x.exe, all iwd files, zone patches, and other
rawfile assets. Everything extracts directly into the game install folder.

Optionally downloads free DLC content from cdn.iw4x.io, including:
  - MW2 DLC map packs (iw4x/*.iwd)
  - CoD4 ported maps (iw3/zone/dlc/*.ff)
  - Black Ops maps (t5/zone/dlc/*.ff)
  - MW3 maps (iw5/zone/dlc/*.ff)
  - CoD Online maps (codo/zone/dlc/*.ff)

For Steam games:
  - Renames iw4mp.exe -> iw4mp.exe.bak
  - Copies iw4x.exe -> iw4mp.exe
  This lets Steam launch IW4x transparently via the existing shortcut.

For own games:
  - Downloads all files but skips the exe rename
  - The non-Steam shortcut already points at iw4x.exe directly

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import os
import json
import shutil
import zipfile
import threading
import urllib.request

# iw4x.dll comes from the client repo, everything else from rawfiles.
# release.zip contains iw4x.exe, all iwd files, zone patches,
# and other assets. No separate downloads needed.
DLL_URL = "https://github.com/iw4x/iw4x-client/releases/latest/download/iw4x.dll"
ZIP_URL = "https://github.com/iw4x/iw4x-rawfiles/releases/latest/download/release.zip"

# CDN manifest for free DLC content (maps from CoD4, BO1, MW3, CoD Online, MW2 DLC)
DLC_MANIFEST_URL = "https://cdn.iw4x.io/update.json"
DLC_CDN_BASE     = "https://cdn.iw4x.io/"

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _download(url: str, dest: str, on_progress=None, label: str = ""):
    """Download url to dest with optional progress callback. Retries up to 3 times."""
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
        except Exception as ex:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def is_iw4x_installed(install_dir: str) -> bool:
    """Returns True if iw4mp.exe.bak exists (meaning the mod rename is active)."""
    return os.path.exists(os.path.join(install_dir, "iw4mp.exe.bak"))


def is_iw4x_dlc_installed(install_dir: str) -> bool:
    """Returns True if DLC content appears to be present."""
    # Check for a few representative files from different DLC categories
    markers = [
        os.path.join(install_dir, "iw4x", "iw_dlc3_00.iwd"),              # MW2 DLC
        os.path.join(install_dir, "iw3", "zone", "dlc", "mp_backlot.ff"), # CoD4
        os.path.join(install_dir, "t5", "zone", "dlc", "mp_nuked.ff"),    # BO1
    ]
    return all(os.path.exists(m) for m in markers)


# ── DLC install ──────────────────────────────────────────────────────────────

# Directories that DLC files are downloaded into (relative to install_dir).
# Used by both install and uninstall.
_DLC_DIRS = ["iw3", "t5", "iw5", "codo"]

def install_iw4x_dlc(install_dir: str, on_progress=None):
    """
    Download and install free DLC content from cdn.iw4x.io.

    Fetches the manifest (update.json), then downloads every file listed
    in it to the correct relative path under install_dir. Files are
    downloaded with up to 4 concurrent workers.

    on_progress — optional callback(percent: int, status: str)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # ── Fetch manifest ────────────────────────────────────────────────────
    prog(0, "Fetching DLC manifest...")
    manifest_path = os.path.join(install_dir, "update.json")
    _download(DLC_MANIFEST_URL, manifest_path, None, "DLC manifest")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    os.remove(manifest_path)

    files = manifest.get("files", [])
    if not files:
        prog(100, "No DLC files found in manifest.")
        return

    # ── Create destination directories ────────────────────────────────────
    prog(2, "Creating DLC directories...")
    dirs_needed = set()
    for entry in files:
        dest = os.path.join(install_dir, entry["path"])
        dirs_needed.add(os.path.dirname(dest))
    for d in dirs_needed:
        os.makedirs(d, exist_ok=True)

    # ── Download all files concurrently ───────────────────────────────────
    total_files = len(files)
    dl_done     = [0]
    dl_errors   = []
    dl_lock     = threading.Lock()

    def _dl_one(entry):
        rel_path = entry["path"]
        dest     = os.path.join(install_dir, rel_path)
        name     = entry.get("asset_name", os.path.basename(rel_path))
        url      = DLC_CDN_BASE + rel_path

        # Skip if file already exists and matches expected size
        expected_size = entry.get("size", 0)
        if os.path.exists(dest) and expected_size:
            try:
                actual = os.path.getsize(dest)
                if actual == expected_size:
                    with dl_lock:
                        dl_done[0] += 1
                        prog(2 + int(dl_done[0] / total_files * 96),
                             f"Skipped {name} (already exists)")
                    return
            except OSError:
                pass

        _download(url, dest, None, name)
        with dl_lock:
            dl_done[0] += 1
            prog(2 + int(dl_done[0] / total_files * 96),
                 f"Downloaded {name} ({dl_done[0]}/{total_files})")

    prog(3, f"Downloading {total_files} DLC files (~3 GB)...")

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_dl_one, entry): entry for entry in files}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                name = futs[fut].get("asset_name", "unknown")
                dl_errors.append(f"{name}: {e}")

    if dl_errors:
        raise RuntimeError("DLC download failed:\n" + "\n".join(dl_errors))

    prog(100, "DLC installation complete!")


# ── public API ────────────────────────────────────────────────────────────────

def install_iw4x(game: dict, steam_root: str,
                 proton_path: str, compatdata_path: str,
                 on_progress=None, source: str = "steam",
                 install_dlc: bool = False):
    """
    Install or reinstall IW4x for Modern Warfare 2.

    Downloads iw4x.dll and release.zip concurrently. release.zip contains
    iw4x.exe, all iwd files, zone patches, and other rawfile assets.
    For Steam games, renames iw4mp.exe -> iw4mp.exe.bak and copies
    iw4x.exe -> iw4mp.exe so Steam launches IW4x transparently.
    For own games, skips the rename -- the shortcut points at iw4x.exe directly.

    game            — entry from detect_games
    steam_root      — path to Steam root (kept for API consistency)
    proton_path     — path to the proton executable (kept for API consistency)
    compatdata_path — path to the MW2 compatdata prefix (kept for API consistency)
    on_progress     — optional callback(percent: int, status: str)
    source          — "steam" or "own", controls whether exe rename happens
    install_dlc     — if True, download free DLC maps after base install
    """
    install_dir = game["install_dir"]
    iw4x_dir    = os.path.join(install_dir, "iw4x")
    if os.path.exists(iw4x_dir):
        shutil.rmtree(iw4x_dir)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # When DLC is enabled, base install uses 0-50%, DLC uses 50-100%.
    # When DLC is disabled, base install uses 0-100%.
    base_end = 50 if install_dlc else 100

    def prog(pct, msg):
        if on_progress:
            scaled = int(pct / 100 * base_end)
            on_progress(scaled, msg)

    # ── Download iw4x.dll and release.zip concurrently ────────────────────
    prog(5, "Downloading iw4x files...")

    dl_tasks = [
        (DLL_URL, os.path.join(install_dir, "iw4x.dll"),    "iw4x.dll"),
        (ZIP_URL, os.path.join(install_dir, "release.zip"), "release.zip"),
    ]
    dl_errors = []
    dl_done   = [0]
    dl_lock   = threading.Lock()

    def _dl(url, dest, label):
        _download(url, dest, None, f"Downloading {label}...")
        with dl_lock:
            dl_done[0] += 1
            prog(5 + int(dl_done[0] / len(dl_tasks) * 45), f"Downloaded {label}")

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = {ex.submit(_dl, url, dest, label): label for url, dest, label in dl_tasks}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                dl_errors.append(f"{futs[fut]}: {e}")

    if dl_errors:
        raise RuntimeError("Download failed:\n" + "\n".join(dl_errors))

    # ── Extract release.zip ───────────────────────────────────────────────
    # release.zip contains:
    #   iw4x.exe          (root)
    #   iw4x/*.iwd        (iwd files)
    #   iw4x/html/        (server browser assets)
    #   iw4x/images/      (branding)
    #   iw4x/video/        (intro video)
    #   zone/patch/        (fastfile patches)
    #   zonebuilder.exe    (modding tool)
    prog(55, "Extracting release.zip...")
    zip_dest = os.path.join(install_dir, "release.zip")
    with zipfile.ZipFile(zip_dest) as zf:
        zf.extractall(install_dir)
    os.remove(zip_dest)

    # ── Rename iw4mp.exe -> iw4mp.exe.bak, copy iw4x.exe -> iw4mp.exe ───
    # Steam games: swap in iw4x.exe so Steam launches it transparently.
    # Own games: skip -- the shortcut points at iw4x.exe directly and the
    # original exe may not even exist (MS Store copies, old installs, etc).
    if source != "own":
        iw4mp     = os.path.join(install_dir, "iw4mp.exe")
        iw4mp_bak = os.path.join(install_dir, "iw4mp.exe.bak")
        iw4x_exe  = os.path.join(install_dir, "iw4x.exe")

        prog(80, "Replacing iw4mp.exe...")
        if os.path.exists(iw4mp) and not os.path.exists(iw4mp_bak):
            os.rename(iw4mp, iw4mp_bak)
        if os.path.exists(iw4x_exe):
            shutil.copy2(iw4x_exe, iw4mp)
    else:
        prog(80, "Own game -- skipping exe rename")

    prog(100, "IW4x base installation complete!")

    # ── Optional DLC download ─────────────────────────────────────────────
    if install_dlc:
        def dlc_prog(pct, msg):
            if on_progress:
                on_progress(50 + int(pct / 100 * 50), msg)
        install_iw4x_dlc(install_dir, on_progress=dlc_prog)


def uninstall_iw4x(game: dict):
    """
    Restore iw4mp.exe from iw4mp.exe.bak and remove all IW4x files,
    including DLC content.
    """
    install_dir = game["install_dir"]

    # Restore iw4mp.exe from backup
    iw4mp     = os.path.join(install_dir, "iw4mp.exe")
    iw4mp_bak = os.path.join(install_dir, "iw4mp.exe.bak")
    if os.path.exists(iw4mp_bak):
        if os.path.exists(iw4mp):
            os.remove(iw4mp)
        os.rename(iw4mp_bak, iw4mp)

    for fname in ["iw4x.dll", "iw4x.exe", "zonebuilder.exe"]:
        p = os.path.join(install_dir, fname)
        if os.path.exists(p):
            os.remove(p)

    iw4x_dir = os.path.join(install_dir, "iw4x")
    if os.path.exists(iw4x_dir):
        shutil.rmtree(iw4x_dir)

    # Clean up zone/patch directory added by release.zip
    zone_patch = os.path.join(install_dir, "zone", "patch")
    if os.path.exists(zone_patch):
        shutil.rmtree(zone_patch)
        # Remove zone/ dir too if it's now empty
        zone_dir = os.path.join(install_dir, "zone")
        if os.path.isdir(zone_dir) and not os.listdir(zone_dir):
            os.rmdir(zone_dir)

    # Clean up DLC directories (iw3/, t5/, iw5/, codo/)
    for dlc_dir in _DLC_DIRS:
        p = os.path.join(install_dir, dlc_dir)
        if os.path.exists(p):
            shutil.rmtree(p)

    # Clean up old DeckOps metadata if upgrading from a previous install
    old_meta = os.path.join(install_dir, "iw4x-updoot")
    if os.path.exists(old_meta):
        shutil.rmtree(old_meta)
