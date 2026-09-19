"""
iw5_downgrade.py - MW3 backward-compatibility re-exports

All downgrade logic now lives in depot_downgrade.py. This module
re-exports the MW3-specific names so existing callers don't break.
"""

import os

from depot_downgrade import (
    GAME_CONFIGS as _GAME_CONFIGS,
    DEPOTDOWNLOADER_DIR,
    DEPOTDOWNLOADER_BIN,
    REQUIRED_FREE_SPACE_GB,
    is_pe_64bit as _is_pe_64bit,
    is_downgrade_needed as _is_downgrade_needed,
    is_sp_exe_64bit as _is_sp_exe_64bit,
    detect_dlc_status as _detect_dlc_status,
    check_free_space_gb,
    has_enough_space,
    find_depot_staging as _find_depot_staging,
    open_steam_console,
    open_steam_install,
    copy_to_clipboard,
    ensure_depotdownloader,
    cleanup_depotdownloader,
    qr_text_to_pixmap,
    run_depot_download_qr,
    merge_depots as _merge_depots,
)

# --- MW3-specific constants (unchanged public API)

_iw5 = _GAME_CONFIGS["iw5"]

IW5_APP_ID = _iw5["app_id"]

IW5_DEPOT_CMDS = _iw5["depot_cmds"]
IW5_DEPOTS = _iw5["depots"]
IW5_DEPOT_IDS = _iw5["depot_ids"]
IW5_SP_DEPOT_ID = _iw5.get("sp_depot_id", 42681)

IW5_DLC = _iw5["dlc"]
IW5_DLC_DEPOT_CMDS = tuple(
    f"download_depot {d['app']} {d['depot']} {d['manifest']}"
    for d in IW5_DLC.values()
)


# --- MW3-specific function wrappers

def is_iw5_downgrade_needed(install_dir: str) -> bool:
    return _is_downgrade_needed("iw5", install_dir)

def is_iw5sp_64bit(install_dir: str) -> bool:
    return _is_sp_exe_64bit("iw5", install_dir)

def detect_dlc_status(install_dir: str) -> dict:
    return _detect_dlc_status("iw5", install_dir)

def find_depot_staging(steam_root: str) -> str | None:
    return _find_depot_staging(steam_root, IW5_APP_ID)

def merge_iw5_depots(staging_dir: str, install_dir: str,
                     on_progress=None):
    return _merge_depots("iw5", staging_dir, install_dir, on_progress)

# Keep the old marker-based check name for any direct callers
def is_iw5_64bit(install_dir: str) -> bool:
    return _is_downgrade_needed("iw5", install_dir)
