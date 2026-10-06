"""
iw3sp.py - DeckOps installer for IW3SP-MOD (Call of Duty 4: Modern Warfare Singleplayer)

Downloads the latest iw3sp_mod release zip from Gitea, extracts it into
the CoD4 install directory. Steam games use a launch option to redirect
iw3sp.exe to iw3sp_mod.exe via bash parameter substitution on %command%.

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import os
import json
import urllib.request
import zipfile

from net import download as _download, BROWSER_UA as _BROWSER_UA

GITEA_API     = "https://gitea.com/api/v1/repos/JerryALT/iw3sp_mod/releases?limit=5"
METADATA_FILE = "deckops_iw3sp.json"
COD4_APPID    = "7940"


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_latest_release():
    """
    Query the Gitea API for the latest stable IW3SP-MOD release.

    Gitea doesn't have a /releases/latest endpoint like GitHub, so we
    fetch the most recent releases and pick the first one that is not a
    draft or prerelease.

    Returns (version, zip_url) or raises on failure.
    """
    req = urllib.request.Request(GITEA_API, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        releases = json.loads(r.read().decode("utf-8"))

    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue

        tag = release.get("tag_name", "")
        version = tag.lstrip("v") if tag else "unknown"

        # Find the .zip asset (not source code archives)
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".zip"):
                return version, asset["browser_download_url"]

        # No uploaded zip asset — fall back to the source zipball
        zipball = release.get("zipball_url")
        if zipball:
            return version, zipball

    raise RuntimeError("No stable IW3SP-MOD release found on Gitea")


# _download and _BROWSER_UA imported from net.py.


def _build_iw3sp_launch_option() -> str:
    return "bash -c 'exec \"${@/iw3sp.exe/iw3sp_mod.exe}\"' -- %command%"


def cod4_launch_option(setup_games: dict) -> str:
    """
    The one 7940 launch option for what DeckOps set up from Steam: MP and
    SP share the appid, so the CoD4R pre-launch update and the IW3SP exe
    swap are built together here instead of overwriting each other.
    Returns "" when neither applies.
    """
    from steam_common import prelaunch_prefix
    steam = lambda k, c: (setup_games.get(k, {}).get("client") == c
                          and setup_games[k].get("source", "steam") == "steam")
    sp = _build_iw3sp_launch_option() if steam("cod4sp", "iw3sp") else "%command%"
    if steam("cod4mp", "cod4r"):
        return prelaunch_prefix("cod4mp") + sp
    return sp if sp != "%command%" else ""


def apply_cod4_launch_option(steam_root: str) -> bool:
    """
    Set 7940's option after the launch-option clean slate. The install
    flow runs the CoD4 installers before Steam is closed, so options they
    write there don't survive. Steam must be closed.
    """
    import config as cfg
    opt = cod4_launch_option(cfg.get_setup_games())
    if not opt:
        return False
    from wrapper import set_launch_options
    set_launch_options(steam_root, COD4_APPID, opt)
    return True


# ── public API ────────────────────────────────────────────────────────────────

def install_iw3sp(game: dict, steam_root: str,
                  proton_path: str, compatdata_path: str,
                  on_progress=None, source: str = "steam"):
    """
    Install IW3SP-MOD for Call of Duty 4 singleplayer.

    Downloads and extracts the mod zip into the CoD4 install directory.
    For Steam games, sets a launch option to redirect iw3sp.exe to
    iw3sp_mod.exe. For own games, the shortcut points at iw3sp_mod.exe
    directly.
    """
    install_dir = game["install_dir"]
    zip_dest    = os.path.join(install_dir, "iw3sp_mod.zip")

    prog = on_progress or (lambda *a: None)

    # Fetch latest release info from Gitea API
    prog(2, "Checking for latest IW3SP-MOD release...")
    try:
        version, zip_url = _get_latest_release()
    except Exception as ex:
        raise RuntimeError(f"Failed to fetch IW3SP-MOD release info: {ex}")

    # Download zip
    prog(5, f"Downloading IW3SP-MOD v{version}...")
    _download(
        zip_url,
        zip_dest,
        lambda p, m: prog(5 + int(p * 0.55), m),
        f"Downloading IW3SP-MOD v{version}...",
    )

    # Extract into CoD4 root
    prog(60, "Extracting IW3SP-MOD...")
    with zipfile.ZipFile(zip_dest) as zf:
        zf.extractall(install_dir)
    os.remove(zip_dest)

    # Restore iw3sp.exe from legacy backup if the old exe-swap is present
    iw3sp_bak = os.path.join(install_dir, "iw3sp.exe.bak")
    if os.path.exists(iw3sp_bak):
        iw3sp = os.path.join(install_dir, "iw3sp.exe")
        if os.path.exists(iw3sp):
            os.remove(iw3sp)
        os.rename(iw3sp_bak, iw3sp)

    # Set launch option (Steam only) — redirects iw3sp.exe to iw3sp_mod.exe.
    # Safe on shared appid 7940: substitution only matches when Steam
    # launches the SP exe, no-op for MP (iw3mp.exe).
    if source != "own":
        prog(80, "Setting launch options...")
        try:
            from wrapper import set_launch_options
            set_launch_options(steam_root, COD4_APPID, _build_iw3sp_launch_option())
        except Exception as ex:
            prog(80, f"Could not set launch options: {ex}")
    else:
        prog(80, "Own game -- skipping launch options")

    # Write metadata
    prog(95, "Saving metadata...")
    meta_path = os.path.join(install_dir, METADATA_FILE)
    with open(meta_path, "w") as f:
        json.dump({"version": version}, f, indent=2)

    prog(100, f"IW3SP-MOD v{version} installation complete!")
