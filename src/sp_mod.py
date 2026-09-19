"""
sp_mod.py - Community SP exe installer for MW3

Downloads community SP client files from the AlterWare CDN
(cdn.alterware.ovh). The 32-bit SP exe from DepotDownloader lacks
Steam CEG per-account personalization, causing it to silently exit
on DRM check. AlterWare's community exe bypasses this:

  MW3: iw5-mod.exe + iw5mp_server.exe + raw/scripts/sp/_cp.gsc

The exe does NOT use DLL injection -- it is the host process
and loads original game code into itself. Safe alongside
Plutonium (separate process, never simultaneous).
"""

import os

from log import get_logger

_log = get_logger(__name__)

_CDN_BASE = "https://cdn.alterware.ovh"

_SP_MOD_CONFIG = {
    "iw5sp": {
        "cdn_files": [
            ("iw5/iw5-mod.exe", "iw5-mod.exe"),
            ("iw5/iw5mp_server.exe", "iw5mp_server.exe"),
            ("iw5/raw/scripts/sp/_cp.gsc", "raw/scripts/sp/_cp.gsc"),
        ],
        "client_exe": "iw5-mod.exe",
        "original_exe": "iw5sp.exe",
        "appid": "42680",
        "mode_flag": "-singleplayer",
    },
}


def install_sp_mod(game_key: str, install_dir: str, on_progress=None) -> bool:
    """
    Download community SP client files from AlterWare CDN into the
    game directory. Returns True on success.
    """
    cfg = _SP_MOD_CONFIG.get(game_key)
    if not cfg:
        _log.error("No SP mod config for key: %s", game_key)
        return False

    def prog(msg):
        _log.info(msg)
        if on_progress:
            on_progress(msg)

    from net import download

    try:
        for cdn_path, local_path in cfg["cdn_files"]:
            url = f"{_CDN_BASE}/{cdn_path}"
            dst = os.path.join(install_dir, local_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            prog(f"Downloading {os.path.basename(local_path)}...")
            download(url, dst)
            _log.info("CDN: placed %s", local_path)

        prog(f"{cfg['client_exe']} installed.")
        return True

    except Exception as ex:
        _log.exception("SP mod install failed for %s", game_key)
        prog(f"SP mod install failed: {ex}")
        return False


def is_sp_mod_installed(game_key: str, install_dir: str) -> bool:
    cfg = _SP_MOD_CONFIG.get(game_key)
    if not cfg:
        return False
    return os.path.isfile(os.path.join(install_dir, cfg["client_exe"]))


def build_sp_launch_option(game_key: str) -> str:
    """
    Build the Steam launch option string that redirects the original
    SP exe to the community mod exe.

    Uses the same ${@/old/new} bash parameter substitution pattern
    as alterware.py -- swaps the exe name in Steam's %command% chain
    without touching files on disk.
    """
    cfg = _SP_MOD_CONFIG.get(game_key)
    if not cfg:
        return ""
    flag = f" {cfg['mode_flag']}" if cfg["mode_flag"] else ""
    return (
        f"bash -c "
        f"'exec \"${{@/{cfg['original_exe']}/{cfg['client_exe']}}}\""
        f"{flag}' "
        f"-- %command%"
    )


def get_sp_mod_appid(game_key: str) -> str:
    cfg = _SP_MOD_CONFIG.get(game_key)
    return cfg["appid"] if cfg else ""
