"""
alterware.py - DeckOps installer for AlterWare (IW6-Mod & S1-Mod)

Downloads the native Linux AlterWare launcher from GitHub and runs it
to fetch mod client files for Ghosts (IW6-Mod) and Advanced Warfare
(S1-Mod). The launcher runs natively on Linux — no Proton needed for
the install step.

For Steam games:
  - Backs up original exe (iw6mp64_ship.exe → iw6mp64_ship.exe.bak)
  - Replaces original exe with a bash wrapper script that launches the
    mod client exe with the correct mode flag (-multiplayer/-singleplayer)
  - Wrapper is padded to original exe size so Steam file validation passes
  - No localconfig.vdf launch options needed — mode flag is in the wrapper

For own games:
  - Leaves mod client exe as-is (iw6-mod.exe, s1-mod.exe)
  - Non-Steam shortcut points to mod exe directly
  - Mode flag baked into shortcut LaunchOptions by shortcut.py
  - CRC appid stable via (exe_path + shortcut_name)

Both flows:
  - Run native Linux launcher with --update flag to download files
  - Write metadata tracking version, paths, installation state
  - Launcher modifies .ff and .bik files in-place (patches)

Uninstall:
  - Restore backed-up exes (Steam only)
  - Remove mod client exe, launcher artifacts, data/ contents
  - User must verify integrity in Steam to restore patched .ff files

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import os
import json
import shutil
import stat
import subprocess
import tarfile
import tempfile

from net import download as _download

# ── constants ─────────────────────────────────────────────────────────────────

# Native Linux launcher — no Proton needed for the install step.
_LAUNCHER_URL = (
    "https://github.com/alterware/alterware-launcher/releases/latest"
    "/download/alterware-launcher-x86_64-unknown-linux-gnu.tar.gz"
)

METADATA_FILE = "deckops_alterware.json"

# Maps game_key → (launcher_arg, client_exe, original_exe)
#
# launcher_arg:  passed to the alterware-launcher binary to select the client
# client_exe:    the mod exe that the launcher downloads into the game dir
# original_exe:  the vanilla Steam exe we back up and replace (Steam installs)
#
# Both iw6mp and iw6sp use the same client (iw6-mod), just launched with
# different flags (-multiplayer / -singleplayer) at runtime. Same for s1.
_GAME_CONFIG = {
    "iw6mp": ("iw6-mod", "iw6-mod.exe", "iw6mp64_ship.exe"),
    "iw6sp": ("iw6-mod", "iw6-mod.exe", "iw6sp64_ship.exe"),
    "s1mp":  ("s1-mod",  "s1-mod.exe",  "s1_mp64_ship.exe"),
    "s1sp":  ("s1-mod",  "s1-mod.exe",  "s1_sp64_ship.exe"),
}

# The built-in launcher UI in iw6-mod and s1-mod crashes under Wine/Proton.
# These flags bypass it and launch directly into the correct game mode.
# For Steam installs the flag is baked into the wrapper script.
# For own installs shortcut.py bakes it into LaunchOptions.
_MODE_FLAGS = {
    "iw6mp": "-multiplayer",
    "iw6sp": "-singleplayer",
    "s1mp":  "-multiplayer",
    "s1sp":  "-singleplayer",
}

# Subdirectories inside data/ created by the AlterWare launcher.
# These are all mod files — none exist in the base game.
# On uninstall we remove their contents but leave data/ itself.
_DATA_SUBDIRS = ["dw", "maps", "scripts", "ui_scripts", "sound"]

# Standalone files the launcher drops into the game root.
_LAUNCHER_ARTIFACTS = ["alterware-launcher.json", "awcache.json"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_metadata(install_dir: str, data: dict):
    """Write DeckOps metadata JSON to the game directory."""
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def is_alterware_installed(install_dir: str, game_key: str) -> bool:
    """
    Returns True if the AlterWare mod client is installed for this game.

    Checks for the mod client exe or a .bak of the original exe (which
    indicates DeckOps performed the exe swap for a Steam install).
    """
    cfg = _GAME_CONFIG.get(game_key)
    if not cfg:
        return False
    _, client_exe, original_exe = cfg

    # Check for mod client exe
    if os.path.exists(os.path.join(install_dir, client_exe)):
        return True

    # Check for backup (Steam install indicator)
    if os.path.exists(os.path.join(install_dir, original_exe + ".bak")):
        return True

    return False


# ── public API ────────────────────────────────────────────────────────────────

def install_alterware(game: dict, game_key: str,
                      steam_root: str = "", proton_path: str = "",
                      compatdata_path: str = "",
                      on_progress=None, source: str = "steam",
                      download_bonus: bool = False):
    """
    Install AlterWare mod client (IW6-Mod or S1-Mod).

    Downloads the native Linux AlterWare launcher, runs it to fetch the
    mod client files, then performs exe backup/replacement for Steam
    installs. The launcher runs natively — no Proton needed.

    Parameters:
      game            — dict from detect_games with install_dir
      game_key        — one of: iw6mp, iw6sp, s1mp, s1sp
      steam_root      — path to Steam root (kept for API consistency)
      proton_path     — path to Proton exe (kept for API consistency)
      compatdata_path — path to compatdata prefix (kept for API consistency)
      on_progress     — optional callback(percent: int, status: str)
      source          — "steam" or "own"
      download_bonus  — if True, download bonus content (extra maps/DLC)
    """
    install_dir = game["install_dir"]

    cfg = _GAME_CONFIG.get(game_key)
    if not cfg:
        raise ValueError(f"Unknown game key: {game_key}")
    launcher_arg, client_exe, original_exe = cfg

    def prog(pct, msg):
        if on_progress:
            on_progress(pct, msg)

    # ── Step 1: Download the native Linux launcher ────────────────────────
    prog(5, "Downloading AlterWare launcher...")
    tmp_dir = tempfile.mkdtemp(prefix="deckops_alterware_")
    tar_path = os.path.join(tmp_dir, "alterware-launcher.tar.gz")
    launcher_bin = os.path.join(tmp_dir, "alterware-launcher")

    try:
        _download(
            _LAUNCHER_URL, tar_path,
            on_progress=lambda pct, lbl: prog(5 + int(pct * 0.15), lbl),
            label="AlterWare launcher",
            timeout=120,
        )
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to download AlterWare launcher: {e}")

    # ── Step 2: Extract launcher binary ───────────────────────────────────
    prog(22, "Extracting launcher...")
    try:
        with tarfile.open(tar_path, "r:gz") as tf:
            # The tarball contains a single binary: alterware-launcher
            for member in tf.getmembers():
                if member.name.endswith("alterware-launcher") and member.isfile():
                    member.name = "alterware-launcher"
                    tf.extract(member, tmp_dir)
                    break
            else:
                raise RuntimeError("alterware-launcher binary not found in tarball")
        os.chmod(launcher_bin, 0o755)
    except tarfile.TarError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to extract AlterWare launcher: {e}")

    # ── Step 3: Run launcher to download mod client files ─────────────────
    prog(25, f"Downloading {launcher_arg} client files...")
    bonus_flag = "--bonus" if download_bonus else "--skip-bonus"
    cmd = [
        launcher_bin, launcher_arg,
        "--update",
        "--skip-launcher-update",
        "--path", install_dir,
        bonus_flag,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=600,
            cwd=install_dir,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            # Launcher may return non-zero but still succeed — check for
            # the client exe before treating this as a hard failure.
            if not os.path.exists(os.path.join(install_dir, client_exe)):
                shutil.rmtree(tmp_dir, ignore_errors=True)
                raise RuntimeError(
                    f"AlterWare launcher failed (exit {result.returncode}): "
                    f"{stderr or 'no error output'}"
                )
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("AlterWare launcher timed out after 10 minutes")
    except OSError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to run AlterWare launcher: {e}")

    prog(80, "Verifying client files...")

    # ── Step 4: Verify mod client exe was downloaded ──────────────────────
    client_exe_path = os.path.join(install_dir, client_exe)
    if not os.path.exists(client_exe_path):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(
            f"AlterWare launcher completed but {client_exe} not found "
            f"in {install_dir}"
        )

    # ── Step 5: Write wrapper script (Steam only) ──────────────────────────
    # Replace the original exe with a bash wrapper that launches the mod
    # client exe with the correct mode flag. The wrapper is padded to the
    # original exe's size so Steam's file validation does not flag a change.
    # This avoids writing to localconfig.vdf (which Steam can overwrite on
    # restart) and keeps the mode flag self-contained in the game directory.
    # Same pattern as plutonium_oled._write_wrapper.
    mode_flag = _MODE_FLAGS.get(game_key, "")
    if source != "own":
        original_path = os.path.join(install_dir, original_exe)
        backup_path   = original_path + ".bak"

        if os.path.exists(original_path) or os.path.exists(backup_path):
            prog(85, f"Writing wrapper for {original_exe}...")

            # Read original size before we overwrite
            original_size = 0
            if os.path.exists(original_path) and not os.path.exists(backup_path):
                original_size = os.path.getsize(original_path)
                shutil.copy2(original_path, backup_path)
            elif os.path.exists(backup_path):
                original_size = os.path.getsize(backup_path)

            # Build wrapper script that launches the mod exe
            script = (
                "#!/bin/bash\n"
                f'cd "$(dirname "$0")"\n'
                f'"./{client_exe}" {mode_flag} "$@"\n'
            )

            script_bytes = script.encode("utf-8")
            if original_size > len(script_bytes):
                script_bytes += b"\x00" * (original_size - len(script_bytes))

            with open(original_path, "wb") as f:
                f.write(script_bytes)

            os.chmod(original_path, os.stat(original_path).st_mode |
                     stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        else:
            # Original exe missing — own game mislabelled as steam,
            # or partial install. Skip the wrapper, log a note.
            prog(85, f"⚠ {original_exe} not found — skipping wrapper")
    else:
        prog(85, "Own game — skipping wrapper")

    # ── Step 6: Write metadata ────────────────────────────────────────────
    prog(90, "Saving metadata...")
    _write_metadata(install_dir, {
        "client": launcher_arg,
        "client_exe": client_exe,
        "original_exe": original_exe,
        "source": source,
        "game_key": game_key,
        "download_bonus": download_bonus,
        "mode_flag": mode_flag,
    })

    # ── Step 7: Clean up temp dir ─────────────────────────────────────────
    shutil.rmtree(tmp_dir, ignore_errors=True)

    prog(100, f"{launcher_arg} installation complete!")


def uninstall_alterware(game: dict, game_key: str, steam_root: str = ""):
    """
    Remove AlterWare mod files and restore original exes.

    Restores backed-up exes for Steam installs (which removes the wrapper
    script), removes the mod client exe, launcher artifacts, and contents
    of the data/ subdirectories created by the launcher. Leaves the data/
    folder itself in place.

    The launcher patches .ff and .bik files in-place during install.
    After uninstall, the user should verify integrity through Steam to
    restore those files to their original state.

    Parameters:
      game       — dict from detect_games with install_dir
      game_key   — one of: iw6mp, iw6sp, s1mp, s1sp
      steam_root — path to Steam root (kept for API consistency)
    """
    install_dir = game["install_dir"]

    cfg = _GAME_CONFIG.get(game_key)
    if not cfg:
        return
    _, client_exe, original_exe = cfg

    # ── Restore original exe from backup ──────────────────────────────────
    original_path = os.path.join(install_dir, original_exe)
    backup_path   = original_path + ".bak"
    if os.path.exists(backup_path):
        if os.path.exists(original_path):
            os.remove(original_path)
        os.rename(backup_path, original_path)

    # ── Remove mod client exe ─────────────────────────────────────────────
    client_path = os.path.join(install_dir, client_exe)
    if os.path.exists(client_path):
        os.remove(client_path)

    # ── Remove launcher artifacts ─────────────────────────────────────────
    for artifact in _LAUNCHER_ARTIFACTS:
        p = os.path.join(install_dir, artifact)
        if os.path.exists(p):
            os.remove(p)

    # ── Remove contents of data/ subdirectories ───────────────────────────
    # These are all mod files created by the AlterWare launcher.
    # We remove their contents but leave data/ itself in place.
    data_dir = os.path.join(install_dir, "data")
    if os.path.isdir(data_dir):
        for subdir in _DATA_SUBDIRS:
            subdir_path = os.path.join(data_dir, subdir)
            if os.path.isdir(subdir_path):
                shutil.rmtree(subdir_path, ignore_errors=True)
        # Also remove the disclosure text file
        disclosure = os.path.join(data_dir, "open_source_software_disclosure.txt")
        if os.path.exists(disclosure):
            os.remove(disclosure)

    # ── Remove metadata ───────────────────────────────────────────────────
    meta_file = os.path.join(install_dir, METADATA_FILE)
    if os.path.exists(meta_file):
        os.remove(meta_file)
