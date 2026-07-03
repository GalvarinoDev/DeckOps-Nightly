"""
cod4r.py - DeckOps installer for CoD4R (Call of Duty 4: Revived)

CoD4R is a community client by k/divity that adds controller support,
a server browser, QoL improvements, and bot support to CoD4 multiplayer.

Unlike CoD4x (which uses a chain-loader DLL mechanism), CoD4R drops files
directly into the game directory:
  - main/*.iwd          (mod packages: jcod4r_00, xcommon_glyphs,
                          xcommon_cod4qol, xcommon_cod4r_weapons)
  - zone/english/*.ff   (fastfiles: cod4r_patchv2, cod4r_controls,
                          cod4r_ambfix, qol)
  - miles32.dll          (patched Miles Sound System library)
  - Cod4R-DedRun.exe     (dedicated server runner)
  - userraw/cod4r_id.key  (player identity key)
  - Mods/mp_bots/         (bot support mod)

After installation, the game launches via the stock iw3mp.exe -- the
patched DLLs and fastfiles are loaded automatically by the engine.

Install flow:
  1. Write registry keys so Steam skips first-launch installers
  2. Download CoD4R-Launcher.exe
  3. Pre-write settings.txt so the launcher knows the game directory
  4. Run the launcher through Proton (auto-downloads files, user closes when done)
  5. Write registry keys again (safety net after Proton run)
  6. Verify CoD4R files landed
  7. Write metadata

The launcher persists its settings at:
  AppData/Local/CoD4R/Launcher/settings.txt
with three lines: game path, theme index, theme name.

Path format:
  - Steam installs use the S: drive (Proton maps steamapps to S:)
  - Own installs use the Z: drive (Wine maps / to Z:)
"""

import os
import re
import json
import shutil
import subprocess
import tempfile

from net import download as _download, DownloadError

from log import get_logger

_log = get_logger(__name__)


# -- constants ----------------------------------------------------------------

# TODO: Replace with actual download URL once k/divity publishes a release.
# This is a placeholder -- DeckOps will need to host or mirror the launcher
# if there is no stable public download link.
_LAUNCHER_URL = "https://archive.org/download/co-d-4-r-launcher_202607/CoD4R-Launcher.exe"

# TODO: Archive.org fallback URL (set up once we have a primary URL)
_ARCHIVE_FALLBACK_URL = None

METADATA_FILE = "deckops_cod4r.json"

# The AppData subfolder name inside the Wine prefix where the launcher
# stores its settings file.
_COD4R_APPDATA_FOLDER = "CoD4R"

# The AppData subfolder name where the game stores runtime data
# (servercache, player configs, etc.) -- same as CoD4x.
_GAME_APPDATA_FOLDER = "CallofDuty4MW"

# Files that CoD4R adds to the game directory. Used for verification
# after install and cleanup during uninstall.
_COD4R_FILES = [
    os.path.join("main", "jcod4r_00.iwd"),
    os.path.join("main", "xcommon_glyphs.iwd"),
    os.path.join("main", "xcommon_cod4qol.iwd"),
    os.path.join("main", "xcommon_cod4r_weapons.iwd"),
    os.path.join("zone", "english", "cod4r_patchv2.ff"),
    os.path.join("zone", "english", "cod4r_controls.ff"),
    os.path.join("zone", "english", "cod4r_ambfix.ff"),
    os.path.join("zone", "english", "qol.ff"),
    "Cod4R-DedRun.exe",
    "miles32.dll",
    "pbgame.htm",
    "eula.txt",
]

_COD4R_DIRS = [
    os.path.join("userraw"),
    os.path.join("Mods", "mp_bots"),
]

# Registry keys that tell Steam the first-launch installers already ran.
# Without these, Steam runs PunkBuster setup, DirectX setup, and PunkBuster
# Vista setup on every first launch -- and re-validates game files afterward.
#
# Source: installscript.vdf in the CoD4 game directory.
# Key path: HKEY_CURRENT_USER\Software\Valve\Steam\Apps\7940
_REGISTRY_VALUES = {
    "dxsetup":    "dword:00000001",
    "Installed":  "dword:00000001",
    "PB Setup":   "dword:00000002",
    "Running":    "dword:00000001",
}


# -- helpers ------------------------------------------------------------------

def _write_metadata(install_dir: str, data: dict):
    """Write DeckOps metadata JSON to the game directory."""
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _nvme_compatdata(appid: str) -> str:
    """Return the NVMe compatdata path for a given appid."""
    return os.path.join(
        os.path.expanduser("~/.local/share/Steam"),
        "steamapps", "compatdata", str(appid),
    )


def _linux_to_wine_path(linux_path: str) -> str:
    """
    Convert a Linux path to a Wine Z: drive path.

    Wine maps the entire Linux filesystem under Z:, so
    /home/deck/.local/share/Steam/steamapps/common/Call of Duty 4
    becomes
    Z:\\home\\deck\\.local\\share\\Steam\\steamapps\\common\\Call of Duty 4
    """
    return "Z:" + linux_path.replace("/", "\\")


def _get_settings_path(compatdata_path: str) -> str:
    """
    Return the path to CoD4R's settings.txt inside the Wine prefix.

    The launcher stores its config at:
      AppData/Local/CoD4R/Launcher/settings.txt
    """
    return os.path.join(
        compatdata_path,
        "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", _COD4R_APPDATA_FOLDER,
        "Launcher", "settings.txt",
    )


def _get_game_appdata_dir(compatdata_path: str) -> str:
    """
    Return the AppData/Local/CallofDuty4MW path inside a Wine prefix.

    This is where the game stores runtime data like servercache.dat
    and player configs.
    """
    return os.path.join(
        compatdata_path,
        "pfx", "drive_c", "users", "steamuser",
        "AppData", "Local", _GAME_APPDATA_FOLDER,
    )


def _build_wine_game_path(install_dir: str, source: str) -> str:
    """
    Build the Wine-style game path for settings.txt.

    Steam installs use the S: drive (Proton maps steamapps/ to S:).
    Own installs use the Z: drive (Wine maps / to Z:).

    Parameters:
      install_dir -- Linux path to the game directory
      source      -- 'steam' or 'own'

    Returns:
      Wine path string suitable for settings.txt
    """
    if source == "steam":
        # Proton creates S: -> <steam_root>/steamapps/
        # The game is at <steam_root>/steamapps/common/<game>/
        # So the Wine path is S:\common\<game folder name>
        #
        # Extract the path relative to steamapps/
        # e.g. /home/deck/.local/share/Steam/steamapps/common/Call of Duty 4
        #   -> common/Call of Duty 4
        #   -> S:\common\Call of Duty 4
        idx = install_dir.find("steamapps/")
        if idx != -1:
            rel = install_dir[idx + len("steamapps/"):]
            return "S:" + rel.replace("/", "\\")
        # Fallback to Z: if we can't find steamapps in the path
        _log.warning("Could not find steamapps/ in install_dir, falling back to Z: path")
        return _linux_to_wine_path(install_dir)
    else:
        return _linux_to_wine_path(install_dir)


def _write_settings_txt(compatdata_path: str, install_dir: str,
                        source: str, on_progress=None):
    """
    Pre-write the CoD4R launcher's settings.txt so it knows the game
    directory without requiring the GUI folder picker.

    settings.txt format (3 lines):
      <game path>
      <theme index>
      <theme name>
    """
    def log(msg):
        if on_progress:
            on_progress(msg)

    settings_path = _get_settings_path(compatdata_path)
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)

    wine_path = _build_wine_game_path(install_dir, source)

    content = f"{wine_path}\n1\nred\n"

    with open(settings_path, "w") as f:
        f.write(content)

    log(f"  Settings path written: {wine_path}")


def _write_registry_keys(compatdata_path: str, on_progress=None):
    """
    Write registry keys into the Wine prefix's user.reg so Steam thinks
    the first-launch installers (Punkbuster, DirectX) have already run.

    Same mechanism as cod4x.py -- prevents Steam from re-validating
    game files and overwriting CoD4R's modified files.
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    user_reg = os.path.join(compatdata_path, "pfx", "user.reg")

    if not os.path.exists(user_reg):
        prog("  user.reg not found -- registry keys will be written after prefix init")
        return False

    with open(user_reg, "r", errors="replace") as f:
        content = f.read()

    key_path = r"[Software\\Valve\\Steam\\Apps\\7940]"

    value_lines = []
    for name, val in _REGISTRY_VALUES.items():
        value_lines.append(f'"{name}"={val}')
    values_text = "\n".join(value_lines)

    if key_path in content:
        pattern = re.compile(
            r'(\[Software\\\\Valve\\\\Steam\\\\Apps\\\\7940\][^\n]*\n)((?:(?!\[)[^\n]*\n)*)',
            re.MULTILINE
        )
        match = pattern.search(content)
        if match:
            header = match.group(1)
            existing_body = match.group(2)

            existing_values = {}
            for line in existing_body.strip().split("\n"):
                line = line.strip()
                if line and "=" in line:
                    k = line.split("=")[0]
                    existing_values[k] = line

            for name, val in _REGISTRY_VALUES.items():
                existing_values[f'"{name}"'] = f'"{name}"={val}'

            new_body = "\n".join(existing_values.values()) + "\n"
            content = content[:match.start()] + header + new_body + content[match.end():]
    else:
        block = (
            f"\n{key_path}\n"
            f"{values_text}\n"
        )
        content += block

    with open(user_reg, "w", errors="replace") as f:
        f.write(content)

    prog("  Registry keys written (skip Punkbuster/DirectX first-launch)")
    return True


def _verify_cod4r_files(install_dir: str, on_progress=None) -> bool:
    """
    Check that the key CoD4R files are present in the game directory.

    Returns True if the critical files are found.
    """
    def log(msg):
        if on_progress:
            on_progress(msg)

    # Critical files that must be present for CoD4R to work
    critical = [
        os.path.join("main", "jcod4r_00.iwd"),
        os.path.join("zone", "english", "cod4r_patchv2.ff"),
        os.path.join("zone", "english", "cod4r_controls.ff"),
        "miles32.dll",
    ]

    missing = []
    for rel in critical:
        full = os.path.join(install_dir, rel)
        if not os.path.exists(full):
            missing.append(rel)

    if missing:
        log(f"  Missing CoD4R files: {', '.join(missing)}")
        return False

    log("  All critical CoD4R files verified")
    return True


# -- public API ---------------------------------------------------------------

def install_cod4r(game: dict, steam_root: str, proton_path: str,
                  compatdata_path: str, on_progress=None, appid: int = 7940,
                  source: str = "steam"):
    """
    Install CoD4R using the launcher through Proton.

    The prefix is already initialized by ensure_all_prefix_deps before
    this function runs. We pre-write the launcher's settings.txt with
    the game path, run the launcher (which auto-downloads files), wait
    for the user to close it, then verify and write metadata.

    Parameters:
      game            -- dict from detect_games with install_dir, exe_path, etc.
      steam_root      -- path to the Steam root directory
      proton_path     -- path to the Proton executable
      compatdata_path -- path to the game's compatdata prefix (can be None/empty)
      on_progress     -- optional callback(percent: int, status: str)
      appid           -- Steam appid (default 7940)
      source          -- 'steam' or 'own'
    """
    install_dir = game["install_dir"]

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    def log(msg):
        if on_progress:
            on_progress(0, msg)

    compatdata_path = _nvme_compatdata(str(appid))
    log(f"  Prefix path: {compatdata_path}")

    # -- Step 1: Write registry keys (pre-launcher) --------------------------
    prog(5, "Writing registry keys...")
    _write_registry_keys(compatdata_path, on_progress=log)

    # -- Step 2: Download CoD4R launcher -------------------------------------
    prog(10, "Downloading CoD4R launcher...")
    launcher_dir = tempfile.mkdtemp(prefix="deckops_cod4r_")
    launcher_exe = os.path.join(launcher_dir, "CoD4R-Launcher.exe")
    try:
        _download(
            _LAUNCHER_URL, launcher_exe,
            on_progress=lambda pct, lbl: prog(10 + int(pct * 0.20), lbl),
            label="CoD4R launcher",
            timeout=120,
        )
    except Exception as e:
        log(f"  CoD4R launcher download failed: {e}")
        if _ARCHIVE_FALLBACK_URL:
            log("  Falling back to archive.org mirror...")
            try:
                _download(
                    _ARCHIVE_FALLBACK_URL, launcher_exe,
                    on_progress=lambda pct, lbl: prog(10 + int(pct * 0.20), lbl),
                    label="CoD4R launcher (archive.org)",
                    timeout=300,
                )
                log("  Archive.org fallback download complete")
            except Exception as e2:
                shutil.rmtree(launcher_dir, ignore_errors=True)
                raise DownloadError(
                    url=_ARCHIVE_FALLBACK_URL,
                    dest=launcher_exe,
                    label="CoD4R launcher",
                    cause=RuntimeError(
                        f"Primary: {e} -- Fallback (archive.org): {e2}"
                    ),
                )
        else:
            shutil.rmtree(launcher_dir, ignore_errors=True)
            raise DownloadError(
                url=_LAUNCHER_URL,
                dest=launcher_exe,
                label="CoD4R launcher",
                cause=e,
            )

    # -- Step 3: Pre-write settings.txt --------------------------------------
    prog(35, "Writing launcher settings...")
    _write_settings_txt(compatdata_path, install_dir, source, on_progress=log)

    # -- Step 4: Run the launcher through Proton -----------------------------
    # The launcher auto-detects that files need downloading and pulls them.
    # It stays open showing "You're up to date" when done -- the user closes
    # it manually, same as the Plutonium bootstrapper flow.
    prog(40, "Running CoD4R launcher...")
    _compat_install = steam_root or os.path.dirname(os.path.dirname(proton_path))

    env = os.environ.copy()
    env["STEAM_COMPAT_DATA_PATH"] = compatdata_path
    env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = _compat_install

    try:
        proc = subprocess.Popen(
            [proton_path, "run", launcher_exe],
            env=env,
            cwd=install_dir,
        )
        proc.wait()
        log("  CoD4R launcher closed by user")
    except Exception as e:
        shutil.rmtree(launcher_dir, ignore_errors=True)
        raise RuntimeError(f"CoD4R launcher failed: {e}")
    finally:
        shutil.rmtree(launcher_dir, ignore_errors=True)

    # -- Step 5: Write registry keys (post-launcher) -------------------------
    # The Proton run may have created a fresh user.reg, so write again.
    prog(70, "Finalizing registry...")
    _write_registry_keys(compatdata_path, on_progress=log)

    # -- Step 6: Verify CoD4R files ------------------------------------------
    prog(80, "Verifying installation...")
    verified = _verify_cod4r_files(install_dir, on_progress=log)
    if not verified:
        log("  CoD4R files not fully present -- launcher may not have completed")
        log("  Try running DeckOps install again")

    # -- Step 7: Delete servercache.dat --------------------------------------
    # Force a fresh server list on first launch.
    appdata_dir = _get_game_appdata_dir(compatdata_path)
    for cache_path in [
        os.path.join(install_dir, "servercache.dat"),
        os.path.join(appdata_dir, "servercache.dat"),
    ]:
        if os.path.exists(cache_path):
            os.remove(cache_path)

    prog(90, "Cleared server cache.")

    # -- Step 8: Write metadata -----------------------------------------------
    prog(95, "Saving metadata...")
    _write_metadata(install_dir, {
        "client": "cod4r",
        "source": source,
        "appdata_dir": appdata_dir,
        "compatdata_path": compatdata_path,
    })

    prog(100, "CoD4R installation complete!")


def is_cod4r_installed(install_dir: str) -> bool:
    """
    Quick check for whether CoD4R files are present in a game directory.

    Checks for the most distinctive CoD4R file (jcod4r_00.iwd) to
    distinguish from a vanilla or CoD4x install.
    """
    return os.path.exists(os.path.join(install_dir, "main", "jcod4r_00.iwd"))


def uninstall_cod4r(game: dict, compatdata_path: str = None):
    """
    Remove CoD4R files and restore the game directory to vanilla state.

    CoD4R adds files but does not replace iw3mp.exe, so uninstall is
    just removing the added files. miles32.dll is a CoD4R addition (not
    a backup of mss32.dll like in CoD4x), so it is simply deleted.

    Parameters:
      game            -- dict from detect_games with install_dir
      compatdata_path -- path to the game's compatdata prefix. If None,
                         attempts to read it from the metadata file.
    """
    install_dir = game["install_dir"]

    # -- Remove CoD4R files from game directory -------------------------------
    for rel in _COD4R_FILES:
        full = os.path.join(install_dir, rel)
        if os.path.exists(full):
            os.remove(full)
            _log.debug("Removed %s", rel)

    # -- Remove CoD4R directories ---------------------------------------------
    for rel in _COD4R_DIRS:
        full = os.path.join(install_dir, rel)
        if os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
            _log.debug("Removed directory %s", rel)

    # -- Clean up prefix AppData ----------------------------------------------
    if compatdata_path is None:
        meta_path = os.path.join(install_dir, METADATA_FILE)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                compatdata_path = meta.get("compatdata_path")
            except (json.JSONDecodeError, IOError):
                _log.debug("failed to read cod4r metadata", exc_info=True)

    if compatdata_path:
        # Remove CoD4R launcher settings
        cod4r_appdata = os.path.join(
            compatdata_path,
            "pfx", "drive_c", "users", "steamuser",
            "AppData", "Local", _COD4R_APPDATA_FOLDER,
        )
        if os.path.isdir(cod4r_appdata):
            shutil.rmtree(cod4r_appdata, ignore_errors=True)

    # -- Remove metadata -------------------------------------------------------
    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
