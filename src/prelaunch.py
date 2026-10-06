"""
prelaunch.py - silent mod client update run by prelaunch.sh before a game

    prelaunch.py <game key> <original launch command...>

Never blocks the launch on failure: prelaunch.sh starts the game no matter
how this exits. Output goes to install.log only, never a window.
"""

import json
import os
import sys
import time

from log import setup_logging, get_logger

_log = get_logger("prelaunch")


def _cod4mp(key, cmd):
    exe = next((a for a in cmd if a.lower().endswith("iw3mp.exe")), None)
    if not exe:
        return  # SP launch on the shared 7940 appid
    install_dir = os.path.dirname(exe)
    meta = os.path.join(install_dir, "deckops_cod4r.json")
    if not os.path.isfile(meta):
        return  # CoD4x or vanilla MP
    with open(meta) as f:
        compat = json.load(f)["compatdata_path"]
    from cod4r import sync_files
    # One quick try at the manifest so being offline costs a few seconds.
    sync_files(install_dir, compat, log=lambda m: _log.info(m.strip()), fetch_timeout=5, tries=1)


def _plutonium(key, cmd):
    # OLED only: the online wrapper and own shortcuts export the game's
    # prefix. Offline/LAN launches don't come through here.
    from plutonium import DEDICATED_PREFIX, _STORAGE_SUBDIRS, _plut_dir_in_prefix
    import plutonium_update as pu
    master = _plut_dir_in_prefix(DEDICATED_PREFIX)
    compat = os.environ.get("STEAM_COMPAT_DATA_PATH", "")
    if not os.path.isdir(master) or not compat:
        return
    log = lambda m: _log.info(m)
    # One quick try so being offline costs a few seconds at most.
    prod, info = pu.fetch(timeout=5, tries=1)
    local = pu.local_revision(master)
    if local != info["revision"]:
        log(f"Plutonium: master r{local}, server r{info['revision']}, updating")
        pu.sync_master(master, prod, info, log)
    else:
        log(f"Plutonium r{local}: up to date")
    prefix = _plut_dir_in_prefix(compat)
    if os.path.isdir(prefix) and os.path.realpath(prefix) != os.path.realpath(master):
        pu.link_prefix(master, prefix, _STORAGE_SUBDIRS.get(key), info, log)


_HANDLERS = {"cod4mp": _cod4mp}
_HANDLERS.update(dict.fromkeys(
    ("t4sp", "t4mp", "t5sp", "t5mp", "t6mp", "t6zm", "iw5mp", "iw5mp_ds"), _plutonium))


def main(argv):
    if not argv or argv[0] not in _HANDLERS:
        return
    t0 = time.monotonic()
    try:
        _HANDLERS[argv[0]](argv[0], argv[1:])
    except Exception as ex:
        _log.warning("prelaunch %s: update skipped: %s", argv[0], ex)
    _log.info("prelaunch %s: %.1fs", argv[0], time.monotonic() - t0)


if __name__ == "__main__":
    setup_logging()
    main(sys.argv[1:])
