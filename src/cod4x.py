"""
cod4x.py - DeckOps installer for CoD4x (Call of Duty 4: Modern Warfare)

Downloads CoD4x 21.3 files from the official GitHub release and places
them directly into the game directory. No NSIS installer, no Proton
subprocess, no popups.

Files downloaded:
  cod4x_021.dll     → install_dir/
  cod4x_patch.ff    → install_dir/zone/english/
  cod4x_patchv2.ff  → install_dir/zone/english/
  cod4x_ambfix.ff   → install_dir/zone/english/
  jcod4x_00.iwd     → install_dir/main/
  core (zip)        → extracts iw3mp.exe into install_dir/ (backup first)
  mss  (zip)        → extracts miles32.dll into install_dir/ (backup first)
"""

import os
import json
import shutil
import zipfile
import threading
import urllib.request

# ── download URLs ─────────────────────────────────────────────────────────────
# All files from the CoD4x 21.3 GitHub release.
# https://github.com/callofduty4x/CoD4x_Client_pub/releases/tag/21.3

_BASE_URL = "https://github.com/callofduty4x/CoD4x_Client_pub/releases/download/21.3"

# (url, relative_dest_dir, final_filename_or_None_for_zip)
# For zips, final_filename is None — they are extracted in place.
_DOWNLOADS = [
    (f"{_BASE_URL}/cod4x_021.dll",    "",              "cod4x_021.dll"),
    (f"{_BASE_URL}/cod4x_patch.ff",   "zone/english",  "cod4x_patch.ff"),
    (f"{_BASE_URL}/cod4x_patchv2.ff", "zone/english",  "cod4x_patchv2.ff"),
    (f"{_BASE_URL}/cod4x_ambfix.ff",  "zone/english",  "cod4x_ambfix.ff"),
    (f"{_BASE_URL}/jcod4x_00.iwd",    "main",          "jcod4x_00.iwd"),
    (f"{_BASE_URL}/core",             "",              None),  # zip → iw3mp.exe
    (f"{_BASE_URL}/mss",              "",              None),  # zip → miles32.dll
]

METADATA_FILE = "deckops_cod4x.json"

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

# Files that get backed up before overwriting. Restored on uninstall.
_BACKUP_FILES = ["iw3mp.exe", "miles32.dll"]

# All files placed by install. Removed on uninstall (backups restored separately).
_INSTALLED_FILES = [
    "cod4x_021.dll",
    os.path.join("zone", "english", "cod4x_patch.ff"),
    os.path.join("zone", "english", "cod4x_patchv2.ff"),
    os.path.join("zone", "english", "cod4x_ambfix.ff"),
    os.path.join("main", "jcod4x_00.iwd"),
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _download(url: str, dest: str, on_progress=None, label: str = ""):
    """Download url to dest with browser-like headers. Retries up to 3 times."""
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=_BROWSER_UA)
            with urllib.request.urlopen(req, timeout=60) as r:
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
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── public API ───────────────────────────────────────────────────────────────

def install_cod4x(game: dict, steam_root: str, proton_path: str,
                  compatdata_path: str, on_progress=None, appid: int = 7940):
    """
    Downloads and installs CoD4x by placing files directly into the game
    directory. No NSIS installer, no Proton execution, no popups.

    steam_root, proton_path, compatdata_path, and appid are accepted for
    API compatibility but are not used.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    install_dir = game["install_dir"]

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # ── Ensure destination subdirs exist ──────────────────────────────────
    os.makedirs(os.path.join(install_dir, "zone", "english"), exist_ok=True)
    os.makedirs(os.path.join(install_dir, "main"), exist_ok=True)

    # ── Back up files that will be overwritten ────────────────────────────
    prog(2, "Backing up original files...")
    for fname in _BACKUP_FILES:
        src = os.path.join(install_dir, fname)
        bak = src + ".bak"
        if os.path.exists(src) and not os.path.exists(bak):
            shutil.copy2(src, bak)

    # ── Download all files concurrently ───────────────────────────────────
    prog(5, "Downloading CoD4x files...")

    # Build download tasks: (url, temp_dest_path, label)
    dl_tasks = []
    for url, rel_dir, final_name in _DOWNLOADS:
        if final_name:
            dest_path = os.path.join(install_dir, rel_dir, final_name) if rel_dir else \
                        os.path.join(install_dir, final_name)
            label = final_name
        else:
            # Zip files: download to a temp name in the target dir
            zip_name = url.rsplit("/", 1)[-1] + ".zip"
            dest_dir = os.path.join(install_dir, rel_dir) if rel_dir else install_dir
            dest_path = os.path.join(dest_dir, zip_name)
            label = url.rsplit("/", 1)[-1]
        dl_tasks.append((url, dest_path, label))

    dl_errors = []
    dl_done = [0]
    dl_lock = threading.Lock()

    def _dl(url, dest, label):
        _download(url, dest, None, f"Downloading {label}...")
        with dl_lock:
            dl_done[0] += 1
            prog(5 + int(dl_done[0] / len(dl_tasks) * 55),
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

    # ── Extract zip assets ────────────────────────────────────────────────
    prog(65, "Extracting CoD4x assets...")
    for url, rel_dir, final_name in _DOWNLOADS:
        if final_name is not None:
            continue  # not a zip
        zip_name = url.rsplit("/", 1)[-1] + ".zip"
        dest_dir = os.path.join(install_dir, rel_dir) if rel_dir else install_dir
        zip_path = os.path.join(dest_dir, zip_name)
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest_dir)
            os.remove(zip_path)

    # ── Delete servercache.dat ────────────────────────────────────────────
    servercache = os.path.join(install_dir, "servercache.dat")
    if os.path.exists(servercache):
        os.remove(servercache)
        prog(90, "Cleared server cache.")

    # ── Write metadata ────────────────────────────────────────────────────
    prog(95, "Saving metadata...")
    _write_metadata(install_dir, {"version": "21.3"})

    prog(100, "CoD4x installation complete!")


def uninstall_cod4x(game: dict):
    """
    Remove CoD4x files and restore original backups.
    """
    install_dir = game["install_dir"]

    # Restore backed-up originals
    for fname in _BACKUP_FILES:
        bak = os.path.join(install_dir, fname + ".bak")
        orig = os.path.join(install_dir, fname)
        if os.path.exists(bak):
            if os.path.exists(orig):
                os.remove(orig)
            os.rename(bak, orig)

    # Remove installed CoD4x files
    for rel_path in _INSTALLED_FILES:
        p = os.path.join(install_dir, rel_path)
        if os.path.exists(p):
            os.remove(p)

    # Remove metadata
    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
