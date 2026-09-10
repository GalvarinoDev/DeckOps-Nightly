"""
iw5_downgrade.py - MW3 32-bit depot downgrade helper

Activision pushed a 64-bit update for MW3 (IW5) that breaks Plutonium
compatibility. This module detects 64-bit installs, assists the user
through either an automated QR-code login flow (via DepotDownloader) or
a manual Steam console paste flow, and merges the 32-bit depot files
over the game directory.

Only applies to Steam-sourced installs (appid 42690 MP, 42750 DS).
Own-source installs are unaffected since users provide their own files.
"""

import os
import re
import shutil
import subprocess
import threading
import zipfile

from log import get_logger

_log = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

IW5_APP_ID = 42680  # MW3 base app (shared by SP 42680, MP 42690, DS 42750)

IW5_DEPOT_CMDS = (
    "download_depot 42680 42682 2661317971072643596",
    "download_depot 42680 42683 1595601894688570808",
)

IW5_DEPOTS = (
    {"depot": 42682, "manifest": "2661317971072643596"},
    {"depot": 42683, "manifest": "1595601894688570808"},
)

IW5_DEPOT_IDS = (42682, 42683)

DEPOTDOWNLOADER_DIR = os.path.expanduser(
    "~/.local/share/deckops/depotdownloader"
)
DEPOTDOWNLOADER_BIN = os.path.join(DEPOTDOWNLOADER_DIR, "DepotDownloader")

# GitHub API endpoint for latest release
_DD_RELEASES_URL = (
    "https://api.github.com/repos/SteamRE/DepotDownloader/releases/latest"
)

# Minimum free space required (GB) for depot downloads + merge headroom
REQUIRED_FREE_SPACE_GB = 15

# Detection marker: main/iw_00.iwd differs substantially in size between
# the 32-bit and 64-bit versions of the game.  This file is bulk game
# data, always present, and never touched by DeckOps' launcher wrapper
# (unlike iw5mp.exe, which DeckOps overwrites with a bash script on OLED).
#   32-bit: ~314 MB (314819587 bytes)
#   64-bit: ~420 MB (419913417 bytes)
# A threshold at 380 MB cleanly separates the two.
_IW5_MARKER_FILE = os.path.join("main", "iw_00.iwd")
_IW5_64BIT_SIZE_THRESHOLD = 380 * 1024 * 1024  # 380 MB


# ── Detection ─────────────────────────────────────────────────────────────────

def is_iw5_64bit(install_dir: str) -> bool:
    """
    Check whether the MW3 install is 64-bit by the size of the marker
    file main/iw_00.iwd.  Returns True if the file is larger than the
    380 MB threshold (64-bit), False if smaller (32-bit) or missing.

    We use file size rather than a PE header check because DeckOps
    overwrites iw5mp.exe with a bash launcher wrapper during Plutonium
    setup, so the exe is not a reliable bitness marker after install.
    """
    marker = os.path.join(install_dir, _IW5_MARKER_FILE)
    if not os.path.isfile(marker):
        _log.debug("iw_00.iwd not found at %s", install_dir)
        return False

    try:
        size = os.path.getsize(marker)
        is_64 = size > _IW5_64BIT_SIZE_THRESHOLD
        _log.debug("iw_00.iwd size: %d bytes -> %s",
                   size, "64-bit" if is_64 else "32-bit")
        return is_64
    except OSError as ex:
        _log.warning("Failed to stat iw_00.iwd: %s", ex)
        return False


def is_iw5_downgrade_needed(install_dir: str) -> bool:
    """
    Returns True if the install is 64-bit and needs downgrading for
    Plutonium, based on the size of main/iw_00.iwd.
    """
    return is_iw5_64bit(install_dir)


# ── Disk space ────────────────────────────────────────────────────────────────

def check_free_space_gb(path: str) -> float:
    """Return free space in GB at the given path."""
    try:
        st = os.statvfs(path)
        return (st.f_bavail * st.f_frsize) / (1024 ** 3)
    except OSError:
        return 0.0


def has_enough_space(path: str) -> bool:
    """Check if there is at least REQUIRED_FREE_SPACE_GB free."""
    return check_free_space_gb(path) >= REQUIRED_FREE_SPACE_GB


# ── Depot staging (manual path) ──────────────────────────────────────────────

def find_depot_staging(steam_root: str) -> str | None:
    """
    Locate the depot staging directory after a download_depot command.
    Steam places downloaded depots under its internal steamapps/content/
    tree.  On most Linux installs this is under ubuntu12_32/steamapps/,
    but it can also be directly under steamapps/.

    Returns the path to app_42680/ or None if not found.
    """
    candidates = [
        os.path.join(steam_root, "ubuntu12_32", "steamapps", "content",
                     f"app_{IW5_APP_ID}"),
        os.path.join(steam_root, "steamapps", "content",
                     f"app_{IW5_APP_ID}"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            _log.debug("Found depot staging at %s", c)
            return c
    return None


# ── Steam console helpers (manual path) ──────────────────────────────────────

def open_steam_console():
    """Fire-and-forget: open the Steam client console tab."""
    try:
        subprocess.Popen(
            ["steam", "steam://open/console"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _log.info("Opened Steam console")
    except FileNotFoundError:
        _log.warning("steam command not found")
    except Exception as ex:
        _log.warning("Failed to open Steam console: %s", ex)


def copy_to_clipboard(text: str):
    """Copy text to the system clipboard (Wayland then X11 fallback)."""
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
        try:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode("utf-8"), timeout=5)
            if proc.returncode == 0:
                _log.debug("Copied to clipboard via %s", cmd[0])
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    _log.warning("Could not copy to clipboard (no wl-copy or xclip)")


# ── DepotDownloader management (QR path) ─────────────────────────────────────

def ensure_depotdownloader(on_progress=None) -> str:
    """
    Download and extract the DepotDownloader linux-x64 binary if it is
    not already present.  Returns the path to the executable.

    on_progress: optional callback(str) for status messages.
    """
    def prog(msg):
        _log.info(msg)
        if on_progress:
            on_progress(msg)

    if os.path.isfile(DEPOTDOWNLOADER_BIN) and os.access(
        DEPOTDOWNLOADER_BIN, os.X_OK
    ):
        prog("DepotDownloader already present.")
        return DEPOTDOWNLOADER_BIN

    os.makedirs(DEPOTDOWNLOADER_DIR, exist_ok=True)
    zip_path = os.path.join(DEPOTDOWNLOADER_DIR, "dd.zip")

    # Get download URL from GitHub releases API
    prog("Fetching DepotDownloader release info...")
    try:
        import json
        result = subprocess.run(
            ["curl", "-sL", _DD_RELEASES_URL],
            capture_output=True, text=True, timeout=30,
        )
        release_data = json.loads(result.stdout)
        dl_url = None
        for asset in release_data.get("assets", []):
            if "linux-x64" in asset.get("name", ""):
                dl_url = asset["browser_download_url"]
                break
        if not dl_url:
            raise RuntimeError("Could not find linux-x64 asset in release")
    except Exception as ex:
        raise RuntimeError(f"Failed to get DepotDownloader release: {ex}")

    # Download
    prog("Downloading DepotDownloader...")
    result = subprocess.run(
        ["curl", "-sL", dl_url, "-o", zip_path],
        timeout=120,
    )
    if result.returncode != 0 or not os.path.isfile(zip_path):
        raise RuntimeError("Failed to download DepotDownloader")

    # Extract
    prog("Extracting DepotDownloader...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(DEPOTDOWNLOADER_DIR)
    os.chmod(DEPOTDOWNLOADER_BIN, 0o755)

    # Verify
    if not os.path.isfile(DEPOTDOWNLOADER_BIN):
        raise RuntimeError(
            f"DepotDownloader binary not found after extraction at "
            f"{DEPOTDOWNLOADER_BIN}"
        )

    prog("DepotDownloader ready.")
    return DEPOTDOWNLOADER_BIN


def cleanup_depotdownloader():
    """Remove the DepotDownloader tool directory and all cached credentials."""
    try:
        if os.path.isdir(DEPOTDOWNLOADER_DIR):
            shutil.rmtree(DEPOTDOWNLOADER_DIR, ignore_errors=True)
            _log.info("Removed DepotDownloader and credentials at %s",
                       DEPOTDOWNLOADER_DIR)
    except Exception as ex:
        _log.warning("Failed to clean up DepotDownloader: %s", ex)


# ── QR-based depot download ──────────────────────────────────────────────────

# Regex to extract username from the success message
_USERNAME_RE = re.compile(
    r"Success!.*-username\s+(\S+)\s+-remember-password"
)

# Block characters used in the QR code output
_QR_CHARS = frozenset("█▀▄▐▌░▒▓ ")

# Keywords that indicate a real DD error, not a QR timeout
_DD_ERROR_KEYWORDS = (
    "401", "access denied", "aborting",
    "result: 0", "no manifest request code",
    "unable to download", "not completely downloaded",
    "not available", "could not get depot key",
)


def _is_qr_line(line: str) -> bool:
    """Check if a line is part of a QR code (mostly block characters)."""
    stripped = line.strip()
    if not stripped:
        return False
    # If >60% of non-space chars are block/drawing chars, it's a QR line
    block_count = sum(1 for c in stripped if c in _QR_CHARS)
    return block_count > len(stripped) * 0.5


def qr_text_to_pixmap(qr_text: str, scale: int = 6):
    """
    Convert a Unicode block-character QR code (as printed by
    DepotDownloader) into a QPixmap for pixel-perfect rendering.

    The QR uses full-block '█' for black modules and spaces for white.
    We parse the text into a boolean grid then paint it as an image,
    scaled up by `scale` pixels per module.

    Returns a QPixmap, or None if parsing fails.
    """
    try:
        from PyQt5.QtGui import QImage, QPixmap, QColor, qRgb

        lines = qr_text.split("\n")
        if not lines:
            return None

        # Find the bounding box of the actual QR content
        # (strip leading/trailing all-space lines and find min indentation)
        qr_lines = []
        for line in lines:
            if "█" in line:
                qr_lines.append(line)

        if not qr_lines:
            return None

        # Find the column range that contains QR data
        min_col = min(line.find("█") for line in qr_lines)
        max_col = max(
            max(i for i, c in enumerate(line) if c == "█")
            for line in qr_lines
        ) + 1

        # Build boolean grid: True = black (█), False = white (space)
        # DepotDownloader renders each QR module as TWO characters wide
        # (██ or two spaces) to appear square in terminal fonts, which
        # are ~2:1 tall.  Sample every 2nd character column so each
        # module maps to one scale×scale square.
        height = len(qr_lines)
        char_width = max_col - min_col
        width = (char_width + 1) // 2  # modules

        # Add quiet zone (4 modules of white border)
        quiet = 4
        img_w = (width + quiet * 2) * scale
        img_h = (height + quiet * 2) * scale

        white = qRgb(255, 255, 255)
        black = qRgb(0, 0, 0)

        img = QImage(img_w, img_h, QImage.Format_RGB32)
        img.fill(white)

        for row_idx, line in enumerate(qr_lines):
            for mod_idx in range(width):
                src_col = min_col + mod_idx * 2
                if src_col < len(line) and line[src_col] == "█":
                    # Paint a scale×scale black square
                    px = (mod_idx + quiet) * scale
                    py = (row_idx + quiet) * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            img.setPixel(px + dx, py + dy, black)

        return QPixmap.fromImage(img)

    except Exception as ex:
        _log.warning("Failed to convert QR text to pixmap: %s", ex)
        return None


def run_depot_download_qr(
    staging_dir: str,
    depot_info: dict,
    on_qr,
    on_auth_success,
    on_progress,
    on_log,
    username: str | None = None,
    max_retries: int = 0,
) -> str | None:
    """
    Run DepotDownloader for a single depot with QR code authentication.

    If using -qr and auth times out (DepotDownloader exits without
    success), the process is restarted automatically so the user gets
    a fresh QR code.  There is no retry limit by default — the user
    can take as long as they need.  The loop only stops on success,
    an unexpected error, or when a username is already provided
    (remembered credentials).

    Args:
        staging_dir: directory to download files into
        depot_info: dict with 'depot' and 'manifest' keys
        on_qr: callback(str) called with QR code text to display/refresh
        on_auth_success: callback(str) called with captured username
        on_progress: callback(str) called with progress messages
        on_log: callback(str) called with log messages
        username: if provided, skip QR and use remembered credentials
        max_retries: 0 = unlimited retries for QR timeout

    Returns:
        Captured username on success, None on failure.
    """
    os.makedirs(staging_dir, exist_ok=True)

    attempt = 0
    while True:
        attempt += 1

        cmd = [
            DEPOTDOWNLOADER_BIN,
            "-app", str(IW5_APP_ID),
            "-depot", str(depot_info["depot"]),
            "-manifest", depot_info["manifest"],
            "-dir", staging_dir,
            "-remember-password",
        ]

        if username:
            cmd.extend(["-username", username])
        else:
            cmd.append("-qr")

        if attempt > 1:
            on_log(f"Retrying QR login (attempt {attempt})...")
        else:
            on_log(f"Running: DepotDownloader -depot {depot_info['depot']} ...")
        _log.info("DepotDownloader command: %s", " ".join(cmd))

        captured_username = None
        auth_succeeded = False
        error_lines = []

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=DEPOTDOWNLOADER_DIR,
            )

            qr_lines = []
            reading_qr = False

            for line in proc.stdout:
                line = line.rstrip("\n\r")
                _log.debug("DD: %s", line)

                # QR code start / refresh
                if "QR code has changed" in line or (
                    "Use the Steam Mobile App" in line
                ):
                    reading_qr = True
                    qr_lines = []
                    continue

                # QR code content
                if reading_qr:
                    if _is_qr_line(line):
                        qr_lines.append(line)
                        continue
                    elif qr_lines:
                        # End of QR block, emit to UI
                        qr_text = "\n".join(qr_lines)
                        on_qr(qr_text)
                        qr_lines = []
                        reading_qr = False

                # Auth success
                m = _USERNAME_RE.search(line)
                if m:
                    captured_username = m.group(1)
                    auth_succeeded = True
                    on_auth_success(captured_username)
                    on_log("QR authentication successful.")
                    continue

                # Progress / status
                if "Got depot key" in line:
                    on_progress(f"Downloading depot {depot_info['depot']}...")
                    on_log(line)
                elif "%" in line and ("download" in line.lower() or
                                      "/" in line):
                    on_progress(line.strip())
                else:
                    stripped = line.strip()
                    if stripped and not _is_qr_line(line):
                        error_lines.append(stripped)
                        on_log(line)

            proc.wait()

            if proc.returncode == 0 and (auth_succeeded or username):
                on_log(f"Depot {depot_info['depot']} download complete.")
                return captured_username or username

            # Remembered credentials failed — surface output, don't retry
            if username:
                on_log(f"DepotDownloader exited with code {proc.returncode}")
                for el in error_lines[-10:]:
                    on_log(f"  {el}")
                return None

            # Check for real errors vs QR timeout. If auth succeeded
            # but download still failed, or DD reported access/license
            # errors, don't retry — the problem isn't authentication.
            real_error = any(
                any(kw in el.lower() for kw in _DD_ERROR_KEYWORDS)
                for el in error_lines
            )

            if real_error or (auth_succeeded and proc.returncode != 0):
                on_log(f"DepotDownloader failed (exit code {proc.returncode}).")
                for el in error_lines[-10:]:
                    on_log(f"  {el}")
                if auth_succeeded:
                    on_log(
                        "Authentication succeeded but the download was "
                        "denied. Your Steam account may not own MW3 "
                        "Multiplayer (42690) or Dedicated Server (42750)."
                    )
                return None

            # Genuine QR timeout — retry with a fresh code
            if max_retries > 0 and attempt >= max_retries:
                on_log("Max QR login retries reached.")
                return None

            on_log("QR code expired. Generating a new one...")

        except Exception as ex:
            on_log(f"DepotDownloader error: {ex}")
            _log.exception("DepotDownloader failed")
            return None


# ── DepotDownloader artifact helpers ──────────────────────────────────────────

def _is_dd_artifact(rel_path: str) -> bool:
    """True if rel_path is a DepotDownloader artifact, not a game file."""
    parts = rel_path.replace("\\", "/").split("/")
    if parts[0] == ".DepotDownloader":
        return True
    if rel_path.endswith(".manifest"):
        return True
    return False


def _cleanup_dd_artifacts(install_dir: str):
    """Remove DepotDownloader artifacts from the game directory."""
    dd_dir = os.path.join(install_dir, ".DepotDownloader")
    if os.path.isdir(dd_dir):
        try:
            shutil.rmtree(dd_dir, ignore_errors=True)
            _log.info("Removed .DepotDownloader from game dir")
        except Exception:
            pass

    try:
        for fname in os.listdir(install_dir):
            if fname.endswith(".manifest"):
                os.remove(os.path.join(install_dir, fname))
                _log.info("Removed DD manifest: %s", fname)
    except Exception:
        pass


# ── Merge ─────────────────────────────────────────────────────────────────────

def merge_iw5_depots(staging_dir: str, install_dir: str,
                     on_progress=None):
    """
    Merge both 32-bit depot directories over the MW3 install directory
    using a delete-then-move strategy:

      1. Delete phase — for every staged file, delete the matching old
         64-bit file in the install dir.  Frees ~16 GB up front so the
         destination drive never needs extra headroom.  Files not in
         the depot set (user configs in players2/, harmless 64-bit
         orphans) are untouched.
      2. Move phase — shutil.move each staged file into place.  On the
         same filesystem (QR path) this is an instant rename with zero
         data movement; across filesystems (manual path, internal →
         SD card) it falls back to copy+delete per file.

    For the manual (Steam console) path, staging_dir is the app_42680
    directory containing depot_42682/ and depot_42683/ subdirectories,
    merged in that order (42683 overwrites 42682 duplicates).

    For the QR (DepotDownloader) path, staging_dir already contains the
    merged depot files (both depots downloaded to the same -dir).

    After a successful merge the staging tree is removed.

    on_progress: optional callback(str) for status messages.
    """
    def prog(msg):
        _log.info(msg)
        if on_progress:
            on_progress(msg)

    # Determine layout: manual path has depot_XXXXX subdirs,
    # QR path has files directly in staging_dir.
    depot_42682_dir = os.path.join(staging_dir, "depot_42682")
    has_depot_subdirs = os.path.isdir(depot_42682_dir)

    if has_depot_subdirs:
        # Manual path: merge each depot subdir in order
        for depot_id in IW5_DEPOT_IDS:
            depot_path = os.path.join(staging_dir, f"depot_{depot_id}")
            if not os.path.isdir(depot_path):
                raise FileNotFoundError(
                    f"Depot directory not found: {depot_path}"
                )
            prog(f"Merging depot {depot_id} into MW3 install...")
            _merge_tree(depot_path, install_dir, prog)
            prog(f"Depot {depot_id} merged.")
    else:
        # QR path: staging_dir has files directly
        prog("Merging 32-bit files into MW3 install...")
        _merge_tree(staging_dir, install_dir, prog)
        prog("Merge complete.")

    # Remove DD artifacts (.DepotDownloader/, .manifest) from game dir
    _cleanup_dd_artifacts(install_dir)

    # Cleanup staging leftovers (empty dirs after moves)
    prog("Cleaning up depot staging files...")
    try:
        shutil.rmtree(staging_dir, ignore_errors=True)
        prog("Staging files removed.")
    except Exception as ex:
        prog(f"Could not remove staging dir: {ex}")

    # Post-merge verification
    if is_iw5_64bit(install_dir):
        prog(
            "WARNING: MW3 still appears to be 64-bit after merge. "
            "The marker file (main/iw_00.iwd) size has not changed. "
            "Try verifying MW3 files in Steam, then run DeckOps again."
        )
        return False

    return True


def _merge_tree(src: str, dst: str, prog):
    """
    Delete-then-move all files from src into dst.

    Phase 1 deletes every dst file that will be replaced (frees space
    immediately).  Phase 2 moves the staged files into place — an
    instant rename on the same filesystem, copy+delete across devices.
    Reports progress every 25 files.
    """
    # Collect all relative file paths, skip DD artifacts
    rel_files = []
    for dirpath, dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        for fname in filenames:
            rf = fname if rel == "." else os.path.join(rel, fname)
            if not _is_dd_artifact(rf):
                rel_files.append(rf)

    total = len(rel_files)
    if total == 0:
        return

    # Phase 1: delete old versions to free space up front
    deleted = 0
    for i, rf in enumerate(rel_files, 1):
        dst_file = os.path.join(dst, rf)
        if os.path.isfile(dst_file):
            try:
                os.remove(dst_file)
                deleted += 1
            except OSError as ex:
                _log.warning("Could not delete %s: %s", dst_file, ex)
        if i % 25 == 0 or i == total:
            prog(f"Removing old files... {i}/{total}")
    _log.info("Deleted %d old files", deleted)

    # Phase 2: move staged files into place
    for i, rf in enumerate(rel_files, 1):
        src_file = os.path.join(src, rf)
        dst_file = os.path.join(dst, rf)
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.move(src_file, dst_file)
        if i % 25 == 0 or i == total:
            prog(f"Moving files into place... {i}/{total}")
