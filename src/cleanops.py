"""
cleanops.py - DeckOps installer for Black Ops III mod clients

Handles two independent mod clients for BO3:

  CleanOps — lightweight DLL mod that improves performance and fixes
             various issues. Single d3d11.dll drop, no exe replacement.

  T7X     — AlterWare standalone client. Downloads t7x.exe into the BO3
             install directory. Launched via its own non-Steam shortcut,
             not through the base game exe.

Both clients can coexist in the same BO3 install directory:
  - CleanOps hooks into BlackOps3.exe via DLL override
  - T7X runs as a separate exe (t7x.exe) alongside BlackOps3.exe

For Steam games (CleanOps only):
  - Drops d3d11.dll into the install directory
  - Sets launch options: WINEDLLOVERRIDES="d3d11=n,b" %command%

For own games (CleanOps):
  - Drops d3d11.dll into the install directory
  - Launch options are handled by the non-Steam shortcut instead

T7X (both Steam and own):
  - Downloads t7x.exe into the install directory
  - Always launched via a dedicated non-Steam shortcut
  - No launch options needed on the base game

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import json
import os
import shutil

from net import download as _download

# ── CleanOps constants ────────────────────────────────────────────────────────

DLL_URL       = "https://raw.githubusercontent.com/notnightwolf/cleanopsT7/main/d3d11.dll"
DLL_NAME      = "d3d11.dll"
METADATA_FILE = "deckops_cleanops.json"
LAUNCH_OPTS   = 'WINEDLLOVERRIDES="d3d11=n,b" %command%'
APPID         = "311210"

# ── T7X constants ─────────────────────────────────────────────────────────────

T7X_URL           = "https://master.bo3.eu/t7x/t7x.exe"
T7X_EXE           = "t7x.exe"
T7X_METADATA_FILE = "deckops_t7x.json"
T7X_DATA_DIR      = "t7x"          # created by t7x.exe on first run


# ── helpers ───────────────────────────────────────────────────────────────────

# _download imported from net.py (default timeout=60).


def is_cleanops_installed(install_dir: str) -> bool:
    """Returns True if the CleanOps DLL and metadata file are both present."""
    return (
        os.path.exists(os.path.join(install_dir, DLL_NAME))
        and os.path.exists(os.path.join(install_dir, METADATA_FILE))
    )


def is_t7x_installed(install_dir: str) -> bool:
    """Returns True if T7X exe and metadata file are both present."""
    return (
        os.path.exists(os.path.join(install_dir, T7X_EXE))
        and os.path.exists(os.path.join(install_dir, T7X_METADATA_FILE))
    )


# ── CleanOps public API ──────────────────────────────────────────────────────

def install_cleanops(game: dict, steam_root: str,
                     proton_path: str, compatdata_path: str,
                     on_progress=None, source: str = "steam"):
    """
    Install CleanOps for Call of Duty: Black Ops III.

    Downloads d3d11.dll from GitHub and drops it into the BO3 install
    directory. For Steam copies, sets the Wine DLL override launch option
    so the DLL loads under Proton.

    game            — entry from detect_games
    steam_root      — path to Steam root
    proton_path     — path to the proton executable (kept for API consistency)
    compatdata_path — path to the BO3 compatdata prefix (kept for API consistency)
    on_progress     — optional callback(percent: int, status: str)
    source          — "steam" or "own", controls whether launch options are set
    """
    install_dir = game["install_dir"]

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # Download DLL
    dll_dest = os.path.join(install_dir, DLL_NAME)
    prog(5, "Downloading CleanOps d3d11.dll...")
    _download(
        DLL_URL,
        dll_dest,
        lambda p, m: prog(5 + int(p * 0.60), m),
        "Downloading CleanOps d3d11.dll...",
    )

    # Set launch options for Steam copies
    if source != "own":
        prog(70, "Setting launch options...")
        try:
            from wrapper import set_launch_options
            set_launch_options(steam_root, APPID, LAUNCH_OPTS)
        except Exception as ex:
            prog(70, f"⚠ Could not set launch options: {ex}")

    # Write metadata
    prog(90, "Saving metadata...")
    meta_path = os.path.join(install_dir, METADATA_FILE)
    with open(meta_path, "w") as f:
        json.dump({"client": "cleanops", "dll": DLL_NAME}, f, indent=2)

    prog(100, "CleanOps installation complete!")


def uninstall_cleanops(game: dict, steam_root: str = None):
    """
    Remove CleanOps from a BO3 install directory.

    Deletes d3d11.dll and the metadata file. Clears launch options
    for Steam copies if steam_root is provided.
    """
    install_dir = game["install_dir"]

    # Remove DLL
    dll_path = os.path.join(install_dir, DLL_NAME)
    if os.path.exists(dll_path):
        os.remove(dll_path)

    # Remove metadata
    meta_path = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_path):
        os.remove(meta_path)

    # Clear launch options
    if steam_root:
        try:
            from wrapper import clear_launch_options
            clear_launch_options(steam_root, APPID)
        except Exception:
            pass


# ── T7X public API ────────────────────────────────────────────────────────────

def install_t7x(game: dict, on_progress=None):
    """
    Install T7X (AlterWare) for Call of Duty: Black Ops III.

    Downloads t7x.exe from the AlterWare master server and places it
    in the BO3 install directory alongside BlackOps3.exe. T7X is always
    launched via its own non-Steam shortcut — no launch options are set
    on the base game.

    T7X self-installs additional files into a t7x/ subdirectory on
    first launch. DeckOps only needs to place the exe.

    game        — entry from detect_games with install_dir
    on_progress — optional callback(percent: int, status: str)
    """
    install_dir = game["install_dir"]

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # Download t7x.exe
    exe_dest = os.path.join(install_dir, T7X_EXE)
    prog(5, "Downloading T7X client...")
    _download(
        T7X_URL,
        exe_dest,
        lambda p, m: prog(5 + int(p * 0.70), m),
        "Downloading T7X client...",
    )

    # Write metadata
    prog(90, "Saving metadata...")
    meta_path = os.path.join(install_dir, T7X_METADATA_FILE)
    with open(meta_path, "w") as f:
        json.dump({"client": "t7x", "exe": T7X_EXE}, f, indent=2)

    prog(100, "T7X installation complete!")


def uninstall_t7x(game: dict):
    """
    Remove T7X from a BO3 install directory.

    Deletes t7x.exe, the metadata file, and the t7x/ data directory
    that T7X creates on first run (contains players folder, configs,
    and cached client files).
    """
    install_dir = game["install_dir"]

    # Remove exe
    exe_path = os.path.join(install_dir, T7X_EXE)
    if os.path.exists(exe_path):
        os.remove(exe_path)

    # Remove metadata
    meta_path = os.path.join(install_dir, T7X_METADATA_FILE)
    if os.path.exists(meta_path):
        os.remove(meta_path)

    # Remove t7x data directory (created by t7x.exe on first run)
    data_dir = os.path.join(install_dir, T7X_DATA_DIR)
    if os.path.isdir(data_dir):
        shutil.rmtree(data_dir, ignore_errors=True)
