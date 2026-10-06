"""
alterware.py - DeckOps installer for AlterWare (IW6-Mod & S1-Mod)

Downloads the native Linux AlterWare launcher from GitHub and runs it
to fetch mod client files for Ghosts (IW6-Mod) and Advanced Warfare
(S1-Mod). The launcher runs natively on Linux — no Proton needed for
the install step.

For Steam games:
  - Sets Steam launch options to redirect the game exe to the mod exe
    using bash parameter substitution on %command%
  - The original exe is NEVER modified — iw6-mod.exe maps the original
    binary into memory at runtime, so it must remain a valid PE file
  - Steam's own Proton invocation handles all env vars, cwd, prefix
  - GE-Proton compat tool mapping (set by ge_proton.py) is required

For own games:
  - Leaves mod client exe as-is (iw6-mod.exe, s1-mod.exe)
  - Non-Steam shortcut points to mod exe directly
  - CRC appid stable via (exe_path + shortcut_name)

Both flows:
  - Run native Linux launcher with --update flag to download files
  - Write metadata tracking version, paths, installation state
  - Launcher modifies .ff and .bik files in-place (patches)

Progress is reported via a callback:
    on_progress(percent: int, status: str)
"""

import os
import json
import shutil
import subprocess
import tarfile
import tempfile

from log import get_logger
from net import download as _download, github_asset

_log = get_logger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

# Native Linux launcher — no Proton needed for the install step.
_LAUNCHER_URL = (
    "https://github.com/alterware/alterware-launcher/releases/latest"
    "/download/alterware-launcher-x86_64-unknown-linux-gnu.tar.gz"
)

_CDN_BASE = "https://cdn.alterware.ovh"


def cdn_digests() -> dict:
    """{cdn_path: "sha1:<hex>"} from the CDN's files.json. Empty on failure
    so a CDN hiccup skips verification instead of blocking the install."""
    try:
        import urllib.request
        from net import BROWSER_UA
        req = urllib.request.Request(f"{_CDN_BASE}/files.json", headers=BROWSER_UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return {f["name"]: f"sha1:{f['hash']}" for f in json.loads(r.read()) if f.get("hash")}
    except Exception as ex:
        _log.warning("AlterWare files.json lookup failed, downloading unverified: %s", ex)
        return {}

# Game exe replacements the launcher doesn't download on its own.
# (cdn_path, local_filename) — downloaded after the launcher finishes.
_CDN_GAME_EXES = {
    "iw6mp": [("iw6/iw6mp64_ship.exe", "iw6mp64_ship.exe")],
    "iw6sp": [("iw6/iw6mp64_ship.exe", "iw6mp64_ship.exe")],
}

METADATA_FILE = "deckops_alterware.json"

# Maps game_key → (launcher_arg, client_exe, original_exe)
#
# launcher_arg:  passed to the alterware-launcher binary to select the client
# client_exe:    the mod exe that the launcher downloads into the game dir
# original_exe:  the vanilla Steam exe that the mod maps into memory at runtime
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
# Must be passed via launch options (Steam installs) or shortcut
# launch options (own installs).
_MODE_FLAGS = {
    "iw6mp": "-multiplayer",
    "iw6sp": "-singleplayer",
    "s1mp":  "-multiplayer",
    "s1sp":  "-singleplayer",
}

# Maps game_key to its Steam appid for launch option writing.
_APPIDS = {
    "iw6mp": "209170",
    "iw6sp": "209160",
    "s1mp":  "209660",
    "s1sp":  "209650",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_metadata(install_dir: str, data: dict):
    """Write DeckOps metadata JSON to the game directory."""
    path = os.path.join(install_dir, METADATA_FILE)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _build_launch_option(original_exe: str, client_exe: str,
                         mode_flag: str) -> str:
    """
    Build the Steam launch option string that redirects the original exe
    to the mod exe using bash parameter substitution on %command%.

    Steam expands %command% to the full Proton launch chain:
      SLR/_v2-entry-point --verb=waitforexitandrun -- GE-Proton/proton
      waitforexitandrun /path/to/game/iw6mp64_ship.exe

    The ${@/old/new} substitution replaces the original exe name with
    the mod exe in whichever positional parameter contains it. The mode
    flag (-multiplayer/-singleplayer) is appended to bypass the mod's
    built-in launcher UI which crashes under Wine/Proton.

    The original exe is never touched on disk — the mod exe maps it
    into memory at runtime, so it must remain a valid PE binary.
    """
    return (
        f"bash -c "
        f"'exec \"${{@/{original_exe}/{client_exe}}}\" {mode_flag}' "
        f"-- %command%"
    )


def _migrate_old_wrapper(install_dir: str, original_exe: str):
    """
    Migrate from the old wrapper-over-exe flow to the new launch options
    flow. If a .bak file exists, the old flow replaced the original exe
    with a bash wrapper — restore the original PE binary so the mod exe
    can map it at runtime.

    Safe to call even if no .bak exists (no-op).
    """
    original_path = os.path.join(install_dir, original_exe)
    backup_path = original_path + ".bak"

    if os.path.exists(backup_path):
        # Restore the original PE binary
        if os.path.exists(original_path):
            os.remove(original_path)
        os.rename(backup_path, original_path)


# ── public API ────────────────────────────────────────────────────────────────

def install_alterware(game: dict, game_key: str,
                      steam_root: str = "", proton_path: str = "",
                      compatdata_path: str = "",
                      on_progress=None, source: str = "steam",
                      download_bonus: bool = True):
    """
    Install AlterWare mod client (IW6-Mod or S1-Mod).

    Downloads the native Linux AlterWare launcher, runs it to fetch the
    mod client files, then sets Steam launch options to redirect the
    original exe to the mod exe. The launcher runs natively — no Proton
    needed for the install step.

    Parameters:
      game            — dict from detect_games with install_dir
      game_key        — one of: iw6mp, iw6sp, s1mp, s1sp
      steam_root      — path to Steam root (for launch option writing)
      proton_path     — path to Proton binary (unused, kept for API compat)
      compatdata_path — path to compatdata prefix (unused, kept for API compat)
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
        url, dg = github_asset("alterware/alterware-launcher",
                               "x86_64-unknown-linux-gnu.tar.gz", fallback=_LAUNCHER_URL)
        _download(
            url, tar_path, digest=dg,
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
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        if stdout:
            for line in stdout.splitlines():
                _log.info("alterware-launcher: %s", line)
        if stderr:
            for line in stderr.splitlines():
                _log.warning("alterware-launcher stderr: %s", line)
        if result.returncode != 0:
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

    # ── Step 3b: Download CDN game exe replacements ─────────────────────
    cdn_files = _CDN_GAME_EXES.get(game_key, [])
    digests = cdn_digests() if cdn_files else {}
    for cdn_path, local_name in cdn_files:
        dst = os.path.join(install_dir, local_name)
        prog(75, f"Downloading {local_name} from CDN...")
        try:
            _download(
                f"{_CDN_BASE}/{cdn_path}", dst,
                on_progress=lambda p, m: prog(75 + int(p * 0.04), m),
                label=local_name, timeout=120, digest=digests.get(cdn_path),
            )
            _log.info("CDN: placed %s", local_name)
        except Exception as e:
            _log.warning("CDN download failed for %s: %s", local_name, e)
            prog(76, f"Warning: could not download {local_name}: {e}")

    prog(80, "Verifying client files...")

    # ── Step 4: Verify mod client exe was downloaded ──────────────────────
    client_exe_path = os.path.join(install_dir, client_exe)
    if not os.path.exists(client_exe_path):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(
            f"AlterWare launcher completed but {client_exe} not found "
            f"in {install_dir}"
        )

    # ── Step 5: Set launch options (Steam) or skip (own) ─────────────────
    # The mod exe (iw6-mod.exe / s1-mod.exe) is a Windows PE binary that
    # must run through Proton. It maps the original game exe into memory
    # at runtime — the original exe MUST remain a valid PE file on disk.
    #
    # For Steam installs we set launch options that use bash parameter
    # substitution to swap the exe name in Steam's Proton launch chain.
    # Steam's compat tool mapping (set by ge_proton.py) provides the
    # Proton environment — no manual env var setup needed.
    #
    # The built-in launcher UI crashes under Wine/Proton, so we append
    # -multiplayer / -singleplayer to bypass it.
    mode_flag = _MODE_FLAGS.get(game_key, "")
    if source != "own":
        appid = _APPIDS.get(game_key)
        if appid and steam_root:
            # Migrate from old wrapper flow if needed — restore original exe
            prog(83, "Checking for old wrapper migration...")
            _migrate_old_wrapper(install_dir, original_exe)

            prog(85, f"Setting launch options for {original_exe}...")
            launch_opt = _build_launch_option(original_exe, client_exe,
                                              mode_flag)

            from wrapper import set_launch_options, clear_launch_options
            # Clear first to avoid appending duplicates on reinstall
            clear_launch_options(steam_root, appid)
            set_launch_options(steam_root, appid, launch_opt)
        else:
            prog(85, f"⚠ Missing appid or steam_root — skipping launch options")
    else:
        prog(85, "Own game — skipping launch options")

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
