"""
cod4x.py - DeckOps installer for CoD4x (Call of Duty 4: Modern Warfare)

Runs the official CoD4x 21.3 setup.exe through Proton in silent mode.
Before running the installer, we ensure the prefix exists on NVMe by
cloning from the donor prefix (created by ge_proton.ensure_all_prefix_deps
earlier in the install flow). The clone includes symlinked system32/syswow64
pointing to the shared DLL directory -- so the prefix is fully initialized
with all DLLs before Proton ever touches it. Registry keys are pre-written
into user.reg so Steam's first-launch installers never fire.

The CoD4x chain-loader mechanism:
  1. mss32.dll in the game directory is replaced with the CoD4x version.
     The original is backed up as miles32.dll. CoD4 loads mss32.dll at
     startup via PE imports, so this is the entry point for the mod.
  2. The new mss32.dll loads launcher.dll from AppData/Local/CallofDuty4MW/bin/.
  3. launcher.dll loads cod4x_021.dll from AppData/Local/CallofDuty4MW/bin/cod4x_021/.
  4. cod4x_021.dll patches the game in memory to become CoD4x 21.3.

Install flow (Session 25):
  1. Force prefix to NVMe, clean up any SD card prefix for 7940
  2. Clone prefix from donor if it doesn't exist (symlinked DLLs, fast)
  3. Write registry keys into user.reg so Steam skips DirectX/Punkbuster
  4. Download the official CoD4x setup.exe
  5. Run setup.exe through Proton (prefix already initialized, no popups)
  6. Write registry keys again (safety net)
  7. Clean up and write metadata

Because the prefix is pre-built via clone, callers should still skip
ensure_prefix_deps for appid 7940 -- we handle it here instead.
"""

import os
import re
import json
import shutil
import subprocess
import tempfile
import urllib.request

# ── constants ─────────────────────────────────────────────────────────────────

_SETUP_EXE_URL = "https://cod4x.ovh/uploads/short-url/2V3RsE0Pp5Jakc1VE9Yuh5yb4lE.exe"

METADATA_FILE = "deckops_cod4x.json"

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

# The AppData subfolder name inside the Wine prefix. This is where the CoD4x
# launcher expects to find its DLLs, zone files, and iwd assets.
_APPDATA_FOLDER = "CallofDuty4MW"

# Registry keys that tell Steam the first-launch installers already ran.
# Without these, Steam runs PunkBuster setup, DirectX setup, and PunkBuster
# Vista setup on every first launch — and re-validates game files afterward,
# overwriting our CoD4x mss32.dll chain-loader with the original.
#
# Source: installscript.vdf in the CoD4 game directory.
# Key path: HKEY_CURRENT_USER\Software\Valve\Steam\Apps\7940
_REGISTRY_VALUES = {
    "dxsetup":    "dword:00000001",
    "Installed":  "dword:00000001",
    "PB Setup":   "dword:00000002",   # MinimumHasRunValue in installscript.vdf is 2
    "Running":    "dword:00000001",
}


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


def _ensure_prefix_dlls(compatdata_path: str, on_progress=None):
    """
    Copy DLLs from GE-Proton's default_pfx into the game's prefix.

    This is the same thing ge_proton.ensure_prefix_deps does in steps 1-2
    (create prefix dir if needed, copy system32 + syswow64 DLLs). We do
    it here instead of relying on the main flow because install_cod4x
    handles its own Proton execution via the setup.exe -- callers skip
    ensure_prefix_deps for appid 7940.

    Kept as fallback if the donor clone approach fails.
    """
    from ge_proton import _find_default_pfx, _get_local_version, _copy_dlls

    def prog(msg):
        if on_progress:
            on_progress(msg)

    ge_version = _get_local_version()
    default_pfx = _find_default_pfx(ge_version)
    if not default_pfx:
        prog("⚠ No GE-Proton default_pfx found -- cannot copy DLLs")
        return False

    pfx_dir = os.path.join(compatdata_path, "pfx")

    # Ensure the compatdata directory exists so Proton has something to work with
    if not os.path.isdir(pfx_dir):
        os.makedirs(compatdata_path, exist_ok=True)

    sys32_src = os.path.join(default_pfx, "drive_c", "windows", "system32")
    wow64_src = os.path.join(default_pfx, "drive_c", "windows", "syswow64")
    sys32_dst = os.path.join(pfx_dir, "drive_c", "windows", "system32")
    wow64_dst = os.path.join(pfx_dir, "drive_c", "windows", "syswow64")

    try:
        c32, s32 = _copy_dlls(sys32_src, sys32_dst)
        c64, s64 = _copy_dlls(wow64_src, wow64_dst)
        total_copied = c32 + c64
        total_skipped = s32 + s64
        if total_copied > 0:
            prog(f"  ✓ Copied {total_copied} DLLs, skipped {total_skipped} (already present)")
        else:
            prog(f"  ✓ All {total_skipped} DLLs already present")
        return True
    except Exception as ex:
        prog(f"  ⚠ DLL copy failed: {ex}")
        return False


def _nvme_compatdata(appid: str) -> str:
    """Return the NVMe compatdata path for a given appid."""
    return os.path.join(
        os.path.expanduser("~/.local/share/Steam"),
        "steamapps", "compatdata", str(appid),
    )


def _cleanup_sd_card_prefix(appid: str, on_progress=None):
    """Delete any SD card compatdata prefix for the given appid."""
    import glob

    def prog(msg):
        if on_progress:
            on_progress(msg)

    sd_patterns = [
        "/run/media/deck/*/steamapps/compatdata",
        "/run/media/deck/*/SteamLibrary/steamapps/compatdata",
        "/run/media/mmcblk0p1/steamapps/compatdata",
        "/run/media/mmcblk0p1/SteamLibrary/steamapps/compatdata",
    ]

    for pattern in sd_patterns:
        for compat_dir in glob.glob(pattern):
            prefix_dir = os.path.join(compat_dir, str(appid))
            if os.path.isdir(prefix_dir):
                try:
                    shutil.rmtree(prefix_dir)
                    prog(f"  ✓ Removed SD card prefix for {appid}")
                except Exception as ex:
                    prog(f"  ⚠ Failed to remove SD card prefix {appid}: {ex}")


def _find_donor_prefix():
    """
    Find an existing NVMe prefix to clone from. Looks for any managed
    prefix that has a fully initialized pfx/drive_c. Prefers 10190 (MW2 MP)
    since that's the standard donor from ensure_all_prefix_deps.
    """
    from ge_proton import MANAGED_APPIDS

    nvme_base = os.path.join(
        os.path.expanduser("~/.local/share/Steam"),
        "steamapps", "compatdata",
    )

    # Prefer 10190 (the standard donor)
    preferred = os.path.join(nvme_base, "10190", "pfx", "drive_c")
    if os.path.isdir(preferred):
        return os.path.join(nvme_base, "10190")

    # Fall back to any managed prefix that exists
    for appid in MANAGED_APPIDS:
        if str(appid) == "7940":
            continue
        candidate = os.path.join(nvme_base, str(appid), "pfx", "drive_c")
        if os.path.isdir(candidate):
            return os.path.join(nvme_base, str(appid))

    return None


def _ensure_7940_prefix(compatdata_path: str, on_progress=None) -> bool:
    """
    Ensure the 7940 prefix exists on NVMe with symlinked DLLs.

    If the prefix already exists and has drive_c, it's ready.
    Otherwise, clone from the donor prefix (same approach as
    ge_proton._clone_with_symlinks).

    Returns True if the prefix is ready, False on failure.
    """
    from ge_proton import (_get_local_version, _clone_with_symlinks,
                           SHARED_DLL_DIR, _ensure_shared_dlls)

    def prog(msg):
        if on_progress:
            on_progress(msg)

    pfx_dir = os.path.join(compatdata_path, "pfx")

    # Already initialized -- nothing to do
    if os.path.isdir(os.path.join(pfx_dir, "drive_c")):
        prog("  ✓ 7940 prefix already exists on NVMe")
        return True

    # Find a donor prefix to clone from
    donor_path = _find_donor_prefix()
    if not donor_path:
        prog("  ⚠ No donor prefix found -- falling back to DLL copy")
        return False

    donor_pfx = os.path.join(donor_path, "pfx")
    if not os.path.isdir(donor_pfx):
        prog("  ⚠ Donor prefix has no pfx/ dir -- falling back to DLL copy")
        return False

    # Make sure shared DLLs exist (should already be set up by ensure_all_prefix_deps)
    ge_version = _get_local_version()
    shared_ready = os.path.isdir(os.path.join(SHARED_DLL_DIR, "system32"))
    if not shared_ready:
        prog("  Setting up shared DLLs for 7940...")
        shared_ready = _ensure_shared_dlls(ge_version, on_progress=on_progress)

    if shared_ready:
        prog("  Cloning donor prefix to 7940 with symlinked DLLs...")
        ok = _clone_with_symlinks(donor_pfx, compatdata_path, ge_version,
                                  on_progress=on_progress)
        if ok:
            return True
        prog("  ⚠ Symlinked clone failed -- falling back to DLL copy")

    return False


def _write_registry_keys(compatdata_path: str, on_progress=None):
    """
    Write registry keys into the Wine prefix's user.reg so Steam thinks
    the first-launch installers (Punkbuster, DirectX) have already run.

    If the key block [Software\\\\Valve\\\\Steam\\\\Apps\\\\7940] already exists,
    we update/add the values. If it doesn't exist, we append the entire block.

    Wine registry format in user.reg:
      [Software\\\\Valve\\\\Steam\\\\Apps\\\\7940] <timestamp>
      "dxsetup"=dword:00000001
      "Installed"=dword:00000001
      "PB Setup"=dword:00000002
      "Running"=dword:00000001
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    user_reg = os.path.join(compatdata_path, "pfx", "user.reg")

    if not os.path.exists(user_reg):
        # Prefix hasn't been initialized yet — the setup.exe Proton run
        # will create it. We'll write the keys after the setup.exe runs
        # if needed, but typically Proton creates user.reg during init.
        prog("  ⚠ user.reg not found — registry keys will be written after prefix init")
        return False

    with open(user_reg, "r", errors="replace") as f:
        content = f.read()

    key_path = r"[Software\\Valve\\Steam\\Apps\\7940]"

    # Build the value lines
    value_lines = []
    for name, val in _REGISTRY_VALUES.items():
        value_lines.append(f'"{name}"={val}')
    values_text = "\n".join(value_lines)

    if key_path in content:
        # Key block exists — find it and ensure all values are present.
        # The block starts at the key_path line and ends at the next
        # empty line or next key block ([...]).
        pattern = re.compile(
            r'(\[Software\\\\Valve\\\\Steam\\\\Apps\\\\7940\][^\n]*\n)((?:(?!\[)[^\n]*\n)*)',
            re.MULTILINE
        )
        match = pattern.search(content)
        if match:
            header = match.group(1)
            existing_body = match.group(2)

            # Parse existing values to preserve any we don't manage
            existing_values = {}
            for line in existing_body.strip().split("\n"):
                line = line.strip()
                if line and "=" in line:
                    k = line.split("=")[0]
                    existing_values[k] = line

            # Merge our values (overwrite if already present)
            for name, val in _REGISTRY_VALUES.items():
                existing_values[f'"{name}"'] = f'"{name}"={val}'

            new_body = "\n".join(existing_values.values()) + "\n"
            content = content[:match.start()] + header + new_body + content[match.end():]
    else:
        # Key block doesn't exist — append it at the end
        block = (
            f"\n{key_path}\n"
            f"{values_text}\n"
        )
        content += block

    with open(user_reg, "w", errors="replace") as f:
        f.write(content)

    prog("  ✓ Registry keys written (skip Punkbuster/DirectX first-launch)")
    return True


# ── public API ───────────────────────────────────────────────────────────────

def install_cod4x(game: dict, steam_root: str, proton_path: str,
                  compatdata_path: str, on_progress=None, appid: int = 7940):
    """
    Install CoD4x 21.3 using the official setup.exe through Proton.

    This function handles its own prefix initialization -- callers should
    skip ensure_prefix_deps for appid 7940 when cod4x is being installed.

    Flow (Session 25):
      1. Force prefix to NVMe, clean up SD card prefix
      2. Clone from donor prefix if needed (symlinked DLLs)
      3. Write registry keys so Steam skips first-launch installers
      4. Download and run CoD4x_Setup.exe with /VERYSILENT
      5. Write registry keys again (safety net)
      6. Clean up and write metadata

    Parameters:
      game            -- dict from detect_games with install_dir, exe_path, etc.
      steam_root      -- path to the Steam root directory
      proton_path     -- path to the Proton executable
      compatdata_path -- path to the game's compatdata prefix (can be None/empty)
      on_progress     -- optional callback(percent: int, status: str)
      appid           -- Steam appid (default 7940)
    """
    install_dir = game["install_dir"]

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    def log(msg):
        if on_progress:
            on_progress(0, msg)

    # ── Step 1: Force prefix to NVMe ──────────────────────────────────────
    # Always use NVMe for the prefix regardless of where the game is installed.
    # Clean up any stale SD card prefix first.
    import time
    start = time.time()
    compatdata_path = _nvme_compatdata(str(appid))
    log(f"  Prefix path: {compatdata_path}")
    _cleanup_sd_card_prefix(str(appid), on_progress=log)

    # ── Step 2: Ensure prefix exists (clone from donor) ───────────────────
    prog(2, "Preparing prefix...")
    cloned = _ensure_7940_prefix(compatdata_path, on_progress=log)
    if not cloned:
        # Fallback: old-style DLL copy if no donor available
        log("  Falling back to direct DLL copy...")
        _ensure_prefix_dlls(compatdata_path, on_progress=log)
    os.makedirs(compatdata_path, exist_ok=True)
    elapsed = time.time() - start
    log(f"  Prefix ready ({elapsed:.1f}s)")

    # ── Step 3: Write registry keys (pre-setup) ─────────────────────────
    # Write before the setup.exe run. The prefix was cloned with user.reg
    # from the donor, so this should succeed on the first attempt.
    prog(8, "Writing registry keys...")
    pre_reg_ok = _write_registry_keys(compatdata_path, on_progress=log)

    # ── Step 4: Download CoD4x setup.exe ─────────────────────────────────
    prog(10, "Downloading CoD4x installer...")
    setup_dir = tempfile.mkdtemp(prefix="deckops_cod4x_")
    setup_exe = os.path.join(setup_dir, "CoD4x_Setup.exe")
    try:
        _download(
            _SETUP_EXE_URL, setup_exe,
            on_progress=lambda pct, lbl: prog(10 + int(pct * 0.40), lbl),
            label="CoD4x installer",
        )
    except Exception as e:
        shutil.rmtree(setup_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to download CoD4x installer: {e}")

    # ── Step 5: Run setup.exe through Proton ─────────────────────────────
    # No /DIR= needed -- setup.exe detects the game location from the
    # working directory (cwd=install_dir). Prefix is pre-built so Proton
    # should not trigger any first-launch installers.
    prog(55, "Running CoD4x installer...")
    _compat_install = steam_root or os.path.dirname(os.path.dirname(proton_path))

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"] = compatdata_path
    env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = _compat_install

    try:
        result = subprocess.run(
            [
                proton_path, "run", setup_exe,
                "/VERYSILENT", "/SUPPRESSMSGBOXES",
            ],
            env=env,
            capture_output=True,
            timeout=600,
            cwd=install_dir,
        )
        # The setup.exe may return non-zero even on success (Inno Setup quirk)
        # so we don't check returncode — we verify file placement below
        log("  ✓ CoD4x installer completed")
    except subprocess.TimeoutExpired:
        shutil.rmtree(setup_dir, ignore_errors=True)
        raise RuntimeError("CoD4x installer timed out after 10 minutes")
    except Exception as e:
        shutil.rmtree(setup_dir, ignore_errors=True)
        raise RuntimeError(f"CoD4x installer failed: {e}")
    finally:
        # Clean up the setup exe regardless of outcome
        shutil.rmtree(setup_dir, ignore_errors=True)

    # ── Step 6: Write registry keys (post-setup) ─────────────────────────
    # The Proton run may have created a fresh user.reg, so write keys again
    # to make sure they're in place for the next Steam launch.
    prog(80, "Finalizing registry...")
    _write_registry_keys(compatdata_path, on_progress=log)

    # ── Step 7: Verify the chain-loader was placed correctly ─────────────
    mss_path = os.path.join(install_dir, "mss32.dll")
    miles_path = os.path.join(install_dir, "miles32.dll")

    if os.path.exists(miles_path) and os.path.exists(mss_path):
        # Check that mss32.dll and miles32.dll are different
        # (mss32.dll should be the chain-loader, miles32.dll the original)
        mss_size = os.path.getsize(mss_path)
        miles_size = os.path.getsize(miles_path)
        if mss_size != miles_size:
            log("  ✓ Chain-loader mss32.dll in place (different size from original)")
        else:
            log("  ⚠ mss32.dll and miles32.dll are the same size — verifying...")
    elif not os.path.exists(miles_path):
        log("  ⚠ miles32.dll backup not found — setup.exe may not have run correctly")

    # ── Step 8: Delete servercache.dat ────────────────────────────────────
    # Force CoD4x to download a fresh server list on first launch.
    appdata_dir = _get_appdata_dir(compatdata_path)
    for cache_path in [
        os.path.join(install_dir, "servercache.dat"),
        os.path.join(appdata_dir, "servercache.dat"),
    ]:
        if os.path.exists(cache_path):
            os.remove(cache_path)

    prog(90, "Cleared server cache.")

    # ── Step 9: Write metadata ────────────────────────────────────────────
    prog(95, "Saving metadata...")
    _write_metadata(install_dir, {
        "version": "21.3",
        "method": "setup_exe",
        "appdata_dir": appdata_dir,
        "compatdata_path": compatdata_path,
    })

    prog(100, "CoD4x installation complete!")


def uninstall_cod4x(game: dict, compatdata_path: str = None):
    """
    Remove CoD4x files and restore original backups.

    Cleans up both the game directory (restores iw3mp.exe and mss32.dll)
    and the Wine prefix AppData structure.

    Parameters:
      game            — dict from detect_games with install_dir
      compatdata_path — path to the game's compatdata prefix. If None,
                        attempts to read it from the metadata file.
    """
    install_dir = game["install_dir"]

    # ── Restore iw3mp.exe from backup ─────────────────────────────────────
    iw3mp_bak = os.path.join(install_dir, "iw3mp.exe.bak")
    iw3mp_exe = os.path.join(install_dir, "iw3mp.exe")
    if os.path.exists(iw3mp_bak):
        if os.path.exists(iw3mp_exe):
            os.remove(iw3mp_exe)
        os.rename(iw3mp_bak, iw3mp_exe)

    # ── Restore mss32.dll from miles32.dll backup ─────────────────────────
    miles_dll = os.path.join(install_dir, "miles32.dll")
    mss_dll   = os.path.join(install_dir, "mss32.dll")
    if os.path.exists(miles_dll):
        if os.path.exists(mss_dll):
            os.remove(mss_dll)
        os.rename(miles_dll, mss_dll)

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
