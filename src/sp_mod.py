"""
sp_mod.py - IW-Pad for MW2/MW3 SP (controller support + aim assist)

Steam (x64): iw-pad-x64.zip in the game root + a launch option. No AlterWare.

Own (32-bit): iw-pad-x86.zip + the AlterWare SP client. 32-bit Steam
depot SP exes lack per-account CEG and silently exit on the DRM check.
AlterWare's clients host the original game code in their own process:

  MW2: iw4x-sp.exe + data/iw4sp.exe (the only iw4sp.exe build it accepts)
  MW3: iw5-mod.exe + iw5mp_server.exe + raw/scripts/sp/_cp.gsc

IW-Pad (iw-pad.exe + iw-pad.dll) adds controller support and aim assist.
Its launcher prefers iw4x-sp.exe / iw5-mod.exe when present and passes
-singleplayer itself, so the shortcut only swaps in iw-pad.exe.
"""

import os
import zipfile

from log import get_logger
from net import download, github_asset
from alterware import _CDN_BASE, cdn_digests

_log = get_logger(__name__)

_IW_PAD_URL = "https://github.com/GalvarinoDev/IW-Pad/releases/latest/download/iw-pad-{}.zip"

_SP_MOD_CONFIG = {
    "iw4sp": {
        "cdn_files": [
            ("iw4/iw4x-sp.exe", "iw4x-sp.exe"),
            ("iw4/data/iw4sp.exe", "data/iw4sp.exe"),
        ],
        "original_exe": "iw4sp.exe",
        "appid": 10180,
    },
    "iw5sp": {
        "cdn_files": [
            ("iw5/iw5-mod.exe", "iw5-mod.exe"),
            ("iw5/iw5mp_server.exe", "iw5mp_server.exe"),
            ("iw5/raw/scripts/sp/_cp.gsc", "raw/scripts/sp/_cp.gsc"),
        ],
        "original_exe": "iw5sp.exe",
        "appid": 42680,
    },
}


def install_sp_mod(game_key: str, install_dir: str, on_progress=None,
                   source: str = "own", steam_root: str = ""):
    """Install IW-Pad into install_dir (plus AlterWare for own). Raises on failure."""
    cfg = _SP_MOD_CONFIG[game_key]
    own = source == "own"
    files = cfg["cdn_files"] if own else []
    steps = len(files) + 1

    def prog(pct, msg):
        _log.info(msg)
        if on_progress:
            on_progress(pct, msg)

    digests = cdn_digests() if files else {}
    for i, (cdn_path, local_path) in enumerate(files):
        dst = os.path.join(install_dir, local_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        name = os.path.basename(local_path)
        download(f"{_CDN_BASE}/{cdn_path}", dst,
                 lambda p, m, i=i: prog(int((i + p / 100) * 100 / steps), m), name,
                 digest=digests.get(cdn_path))
        _log.info("CDN: placed %s", local_path)

    arch = "x86" if own else "x64"
    zip_dest = os.path.join(install_dir, f"iw-pad-{arch}.zip")
    url, dg = github_asset("GalvarinoDev/IW-Pad", f"iw-pad-{arch}.zip",
                           fallback=_IW_PAD_URL.format(arch))
    download(url, zip_dest,
             lambda p, m: prog(int((len(files) + p / 100) * 100 / steps), m), "IW-Pad",
             digest=dg)
    with zipfile.ZipFile(zip_dest) as zf:
        zf.extractall(install_dir)
    os.remove(zip_dest)

    if not own:
        from wrapper import set_launch_options, clear_launch_options
        clear_launch_options(steam_root, cfg["appid"])
        set_launch_options(steam_root, cfg["appid"], build_sp_launch_option(game_key))
    prog(100, "IW-Pad installed.")


def build_sp_launch_option(game_key: str) -> str:
    """Launch option (Steam app or own shortcut) that swaps the original SP exe for iw-pad.exe."""
    exe = _SP_MOD_CONFIG[game_key]["original_exe"]
    return f"bash -c 'exec \"${{@/{exe}/iw-pad.exe}}\"' -- %command%"


if __name__ == "__main__":
    assert build_sp_launch_option("iw4sp") == "bash -c 'exec \"${@/iw4sp.exe/iw-pad.exe}\"' -- %command%"
    assert build_sp_launch_option("iw5sp") == "bash -c 'exec \"${@/iw5sp.exe/iw-pad.exe}\"' -- %command%"
    print("ok")
