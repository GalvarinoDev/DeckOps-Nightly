"""
ge_proton.py - DeckOps GE-Proton installer

Downloads and installs the latest GE-Proton release from GitHub, then
writes the CompatToolMapping entry in Steam's config.vdf so each game
uses it automatically.

Also provides ensure_prefix_deps() which copies the full dependency set
(d3dx, vcrun, xinput, partial xact) from GE-Proton's default_pfx into
any game prefix that's missing them. This eliminates the need for users
to launch each game once before mods can be installed.

Install path:
    ~/.steam/root/compatibilitytools.d/GE-ProtonX-XX/

CompatToolMapping written to:
    ~/.local/share/Steam/config/config.vdf
"""

import json
import os
import shutil
import tarfile
import tempfile
import urllib.request

GITHUB_API   = "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
COMPAT_DIR   = os.path.expanduser("~/.local/share/Steam/compatibilitytools.d")

# Steam appids that DeckOps manages — GE-Proton will be set for all of these
MANAGED_APPIDS = [
    "7940",    # CoD4
    "10090",   # WaW
    "10180",   # MW2 SP
    "10190",   # MW2 MP
    "42680",   # MW3 SP
    "42690",   # MW3 MP
    "42700",   # BO1 Campaign/Zombies
    "42710",   # BO1 Multiplayer
    "202970",  # BO2 Campaign
    "202990",  # BO2 Multiplayer
    "212910",  # BO2 Zombies
]

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}


# ── GitHub API ────────────────────────────────────────────────────────────────

def _get_latest_release():
    """
    Query the GitHub API for the latest GE-Proton release.
    Returns (version, tarball_url, checksum_url).
    """
    req = urllib.request.Request(GITHUB_API, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    version = data["tag_name"]  # e.g. "GE-Proton10-28"
    tarball_url  = None
    checksum_url = None

    for asset in data.get("assets", []):
        name = asset["name"]
        if name.endswith(".tar.gz"):
            tarball_url = asset["browser_download_url"]
        elif name.endswith(".sha512sum"):
            checksum_url = asset["browser_download_url"]

    if not tarball_url:
        raise RuntimeError(f"No .tar.gz asset found for {version}")

    return version, tarball_url, checksum_url


def _is_installed(version):
    """Returns True if this GE-Proton version is already extracted."""
    return os.path.isdir(os.path.join(COMPAT_DIR, version))


def _get_local_version() -> str | None:
    """
    Scan compatibilitytools.d for the newest installed GE-Proton version.
    Returns the version string (e.g. 'GE-Proton10-32') or None if not found.
    Works regardless of how GE-Proton was installed (ProtonUp-Qt, manual, etc.)
    """
    import re
    if not os.path.isdir(COMPAT_DIR):
        return None

    def _version_key(name):
        parts = re.findall(r'\d+', name)
        return tuple(int(p) for p in parts)

    candidates = [
        d for d in os.listdir(COMPAT_DIR)
        if d.startswith("GE-Proton") and
        os.path.exists(os.path.join(COMPAT_DIR, d, "proton"))
    ]
    if not candidates:
        return None

    candidates.sort(key=_version_key, reverse=True)
    return candidates[0]


# ── default_pfx resolution ───────────────────────────────────────────────────

def _find_default_pfx(ge_version: str | None) -> str | None:
    """
    Locate GE-Proton's default_pfx directory.

    Tries the exact version first, then falls back to scanning for the
    newest available GE-Proton install. Returns the path or None.
    """
    # Try exact version first
    if ge_version:
        candidate = os.path.join(COMPAT_DIR, ge_version, "files", "share", "default_pfx")
        if os.path.isdir(candidate):
            return candidate

    # Fallback: newest GE-Proton that has a default_pfx
    if os.path.isdir(COMPAT_DIR):
        for entry in sorted(os.listdir(COMPAT_DIR), reverse=True):
            if not entry.startswith("GE-Proton"):
                continue
            candidate = os.path.join(COMPAT_DIR, entry, "files", "share", "default_pfx")
            if os.path.isdir(candidate):
                return candidate

    return None


# ── Download helpers ──────────────────────────────────────────────────────────

def _download(url, dest, on_progress=None):
    """Download a URL to dest with optional progress callback(percent, msg)."""
    req = urllib.request.Request(url, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk = 1024 * 1024  # 1MB
        with open(dest, "wb") as f:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                f.write(buf)
                downloaded += len(buf)
                if on_progress and total:
                    pct = int(downloaded / total * 100)
                    mb = downloaded / 1024 / 1024
                    on_progress(pct, f"Downloading GE-Proton... {mb:.1f} MB")


def _verify_checksum(tarball_path, checksum_url):
    """Download the .sha512sum file and verify the tarball. Returns True if OK."""
    import hashlib
    req = urllib.request.Request(checksum_url, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        checksum_data = resp.read().decode().strip()

    # Format: "<hash>  <filename>"
    expected_hash = checksum_data.split()[0]
    sha512 = hashlib.sha512()
    with open(tarball_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            sha512.update(chunk)
    return sha512.hexdigest() == expected_hash


# ── Install ───────────────────────────────────────────────────────────────────

def install_ge_proton(on_progress=None):
    """
    Download and install the latest GE-Proton to compatibilitytools.d.
    Returns the version string (e.g. 'GE-Proton10-28') so it can be
    passed to set_compat_tool().

    on_progress — optional callback(percent: int, msg: str)
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # Check if a local GE-Proton install already exists before hitting GitHub.
    # This handles both previous DeckOps installs and external tools like ProtonUp-Qt.
    local_version = _get_local_version()
    if local_version:
        prog(5, f"Found local GE-Proton: {local_version}. Checking for updates...")
    else:
        prog(0, "Checking latest GE-Proton release...")

    version, tarball_url, checksum_url = _get_latest_release()
    prog(5, f"Latest: {version}")

    if local_version == version:
        prog(100, f"GE-Proton {version} already installed — skipping download.")
        return version

    if _is_installed(version):
        prog(100, f"GE-Proton {version} already installed.")
        return version

    os.makedirs(COMPAT_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="deckops_ge_") as tmp:
        tarball_path = os.path.join(tmp, f"{version}.tar.gz")

        prog(10, f"Downloading GE-Proton {version}...")
        _download(tarball_url, tarball_path, on_progress=on_progress)

        if checksum_url:
            prog(85, "Verifying checksum...")
            if not _verify_checksum(tarball_path, checksum_url):
                raise RuntimeError("GE-Proton checksum mismatch — download may be corrupt")
            prog(87, "Checksum OK.")

        # Use system tar for speed and memory efficiency — Python's tarfile
        # module is noticeably slower and more memory-hungry when extracting
        # Python's tarfile module for large archives like GE-Proton.
        prog(87, f"Extracting {version}...")
        import subprocess
        result = subprocess.run(
            ["tar", "-xzf", tarball_path, "-C", COMPAT_DIR],
            capture_output=True,
        )
        if result.returncode != 0:
            # Fall back to Python tarfile if tar isn't available
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(COMPAT_DIR)
        prog(100, f"GE-Proton {version} installed.")

    return version


# ── CompatToolMapping ─────────────────────────────────────────────────────────
# Canonical implementation lives in wrapper.set_compat_tool.
# Imported here so callers can use ge_proton.set_compat_tool as before.

from wrapper import set_compat_tool  # noqa: F401


# ── Prefix dependency management ─────────────────────────────────────────────
# GE-Proton's default_pfx ships with the full d3dx, vcrun, xinput, and
# partial xact dependency set that these CoD games need. Instead of
# running winetricks verbs or relying on Steam to install them on first
# launch, we copy the DLLs directly from default_pfx into each game's
# prefix. This works for both Steam and own games.
#
# The only DLLs NOT in default_pfx are the 9 extra XACT files needed by
# t4/t5 (WaW, Black Ops). Those are still handled by the protontricks
# xact verb in plutonium.py.

def _copy_dlls(src_dir: str, dest_dir: str) -> int:
    """
    Copy all .dll files from src_dir into dest_dir, overwriting existing.
    Returns the number of files copied.
    """
    if not os.path.isdir(src_dir):
        return 0
    os.makedirs(dest_dir, exist_ok=True)
    count = 0
    for fname in os.listdir(src_dir):
        if fname.lower().endswith(".dll"):
            shutil.copy2(os.path.join(src_dir, fname), os.path.join(dest_dir, fname))
            count += 1
    return count


def ensure_prefix_deps(ge_version: str | None, prefix_path: str,
                       on_progress=None, proton_path: str | None = None,
                       steam_root: str | None = None) -> bool:
    """
    Make sure a game's compatdata prefix is fully initialized and has
    the complete dependency set from GE-Proton's default_pfx.

    Logic:
      1. If no proton_path, fall back to copytree from default_pfx and return.
      2. If pfx/drive_c already exists (prefix previously initialized):
         - Copy any missing DLLs from default_pfx (fast, no Proton run)
         - Skip the slow `proton run cmd /c exit` step entirely
      3. If pfx/drive_c does NOT exist (fresh prefix):
         - Create prefix_path so Proton has a directory to work with
         - Copy DLLs from default_pfx into system32 + syswow64
         - Run `proton run cmd /c exit` to finalize the prefix

    ge_version  -- GE-Proton version string (e.g. "GE-Proton10-33")
    prefix_path -- compatdata root (e.g. ~/.../compatdata/10090)
    on_progress -- optional callback(msg: str) for log messages
    proton_path -- path to the proton binary. When provided, the prefix is
                   finalized by Proton after DLL copy. Falls back to copytree
                   if not provided.
    steam_root  -- path to Steam root. Used for STEAM_COMPAT_CLIENT_INSTALL_PATH.
                   Falls back to deriving from proton_path if not provided.

    Returns True if deps are now in place, False if we couldn't do it.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    default_pfx = _find_default_pfx(ge_version)
    if not default_pfx:
        prog("⚠ No GE-Proton default_pfx found — cannot install dependencies")
        return False

    pfx_dir      = os.path.join(prefix_path, "pfx")
    sys32_target = os.path.join(pfx_dir, "drive_c", "windows", "system32")
    wow64_target = os.path.join(pfx_dir, "drive_c", "windows", "syswow64")
    version_file = os.path.join(prefix_path, "version")

    # Check if the prefix has already been initialized by Proton.
    # If drive_c exists, the prefix structure is in place — we only need
    # to copy any missing DLLs and can skip the slow Proton run.
    prefix_exists = os.path.isdir(os.path.join(pfx_dir, "drive_c"))

    # ── Fallback: no proton_path ───────────────────────────────────────
    # Can't run Proton to finalize — copy entire default_pfx as a best effort.
    if not proton_path:
        try:
            os.makedirs(prefix_path, exist_ok=True)
            if not os.path.isdir(pfx_dir):
                shutil.copytree(default_pfx, pfx_dir, symlinks=True)
            if ge_version and not os.path.isfile(version_file):
                with open(version_file, "w") as f:
                    f.write(ge_version + "\n")
            prog("  ✓ Prefix created from default_pfx (no Proton path — fallback)")
            return True
        except Exception as ex:
            prog(f"  ⚠ Prefix creation failed: {ex}")
            return False

    # STEAM_COMPAT_CLIENT_INSTALL_PATH should be the Steam root so Proton
    # can find steamclient.so. Fall back to dirname trick if not provided.
    _compat_install = steam_root or os.path.dirname(os.path.dirname(proton_path))

    # ── Step 1: Ensure the prefix directory exists ─────────────────────
    # Proton needs the compatdata directory to exist before it can initialize.
    # Don't create pfx/ itself — Proton does that in the finalize step.
    if not prefix_exists:
        os.makedirs(prefix_path, exist_ok=True)

    # ── Step 2: Always copy DLLs from default_pfx ─────────────────────
    # Copy before Proton finalizes so Proton sees the full dependency set
    # when it writes its management files.
    sys32_src = os.path.join(default_pfx, "drive_c", "windows", "system32")
    wow64_src = os.path.join(default_pfx, "drive_c", "windows", "syswow64")

    try:
        n32 = _copy_dlls(sys32_src, sys32_target)
        n64 = _copy_dlls(wow64_src, wow64_target)
        prog(f"  ✓ Copied {n32 + n64} DLLs into prefix (system32: {n32}, syswow64: {n64})")
    except Exception as ex:
        prog(f"  ⚠ DLL copy failed: {ex}")
        return False

    # ── Step 3: Finalize via Proton (only if prefix is new) ───────────
    # Only run `proton run cmd /c exit` when the prefix hasn't been
    # initialized yet. This is the slow step (~60s per prefix) that
    # creates the Wine prefix structure, wineserver, registry, etc.
    # For existing prefixes, the DLL copy above is sufficient.
    if prefix_exists:
        prog("  ✓ Prefix already initialized — skipped Proton run")
        return True

    import subprocess
    try:
        env = os.environ.copy()
        env["STEAM_COMPAT_DATA_PATH"]           = prefix_path
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = _compat_install
        subprocess.run(
            [proton_path, "run", "cmd", "/c", "exit"],
            env=env, capture_output=True, timeout=180,
        )
        prog("  ✓ Prefix finalized by Proton")
        return True
    except Exception as ex:
        prog(f"  ⚠ Proton prefix finalize failed: {ex}")
        return False


def ensure_all_prefix_deps(ge_version: str | None, prefix_paths: list[tuple[str, str]],
                           on_progress=None, proton_path: str | None = None,
                           steam_root: str | None = None) -> int:
    """
    Run ensure_prefix_deps for a list of games concurrently.

    Runs up to 3 prefixes in parallel to speed up the install flow.
    Each prefix gets its own Proton wineserver (keyed by
    STEAM_COMPAT_DATA_PATH) so concurrent init is safe.

    prefix_paths — list of (label, compatdata_path) tuples
                   label is for logging (e.g. game key or display name)
    on_progress  — optional callback(msg: str)
    proton_path  — passed through to ensure_prefix_deps for Proton init
    steam_root   — passed through for STEAM_COMPAT_CLIENT_INSTALL_PATH

    Returns the number of prefixes that now have deps installed.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    log_lock = threading.Lock()

    def prog(msg):
        if on_progress:
            with log_lock:
                on_progress(msg)

    def _do_one(label, compat_path):
        if not compat_path:
            prog(f"  {label}: no compatdata path — skipped")
            return False
        prog(f"  {label}: checking dependencies...")
        # Thread-safe progress: each worker wraps on_progress with the lock
        def _thread_prog(msg):
            prog(msg)
        return ensure_prefix_deps(ge_version, compat_path, on_progress=_thread_prog,
                                  proton_path=proton_path, steam_root=steam_root)

    success = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {
            ex.submit(_do_one, label, compat_path): label
            for label, compat_path in prefix_paths
        }
        for fut in as_completed(futs):
            try:
                if fut.result():
                    success += 1
            except Exception as e:
                prog(f"  {futs[fut]}: ⚠ failed: {e}")

    return success


# ── Public API ────────────────────────────────────────────────────────────────

def setup_ge_proton(on_progress=None):
    """
    Full setup: install latest GE-Proton and set it for all managed appids.
    Call this from ui_qt.py early in the install flow.

    Returns the installed version string.
    """
    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    version = install_ge_proton(on_progress=on_progress)
    prog(0, f"Setting GE-Proton {version} for all games...")
    set_compat_tool(MANAGED_APPIDS, version)
    prog(100, f"✓  GE-Proton {version} set for all games.")
    return version
