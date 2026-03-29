"""
DeckOps Decky Plugin — Python Backend

Toggles game display configs between handheld (1280x800) and docked
(auto-detected via xrandr). Patches r_mode and r_displayRefresh in
all deployed game config files.

Requires DeckOps to be installed at ~/DeckOps-Nightly/.
"""

import os
import sys
import re
import subprocess
import asyncio

import decky

# ── Import DeckOps modules ───────────────────────────────────────────────────
# The plugin runs from ~/homebrew/plugins/DeckOps/ but DeckOps source lives
# at ~/DeckOps-Nightly/src/. Add it to sys.path so we can import config and
# game_config directly.

DECKOPS_SRC = os.path.expanduser("~/DeckOps-Nightly/src")
if DECKOPS_SRC not in sys.path:
    sys.path.insert(0, DECKOPS_SRC)

import config as cfg
import game_config
import detect_games

# ── Constants ────────────────────────────────────────────────────────────────

HANDHELD_RES = "1280x800"

# Supported docked resolutions grouped by aspect ratio
SUPPORTED_RESOLUTIONS = {
    "16:9":  ["1920x1080", "1280x720"],
    "16:10": ["1920x1200", "1280x800"],
    "21:9":  ["2560x1080"],
}

# All supported resolutions as a flat set for validation
ALL_SUPPORTED = {r for group in SUPPORTED_RESOLUTIONS.values() for r in group}

# Refresh rates for handheld mode by deck model
HANDHELD_REFRESH = {
    "lcd":  "60",
    "oled": "90",
}

# Docked refresh = empty string (auto-detect from monitor)
DOCKED_REFRESH = ""

# Config filenames we patch (basename -> dvar patterns present)
# All use r_mode; most use r_displayRefresh; MW3 has no r_fullscreen
CONFIG_FILENAMES = {
    "config.cfg",
    "config_mp.cfg",
    "iw3sp_mod_config.cfg",
    "iw4x_config.cfg",
    "plutonium_mp.cfg",
    "plutonium_zm.cfg",
}


# ── xrandr display detection ────────────────────────────────────────────────

def _detect_external_display():
    """
    Run xrandr and find the highest-resolution connected external display.

    Returns a dict with:
        connected: bool
        resolution: "WIDTHxHEIGHT" or None
        aspect_ratio: "16:9" / "16:10" / "21:9" / None
        matched_res: closest supported resolution or None

    The Steam Deck's internal display is typically eDP-1. Any other
    connected output is considered external.
    """
    result = {
        "connected": False,
        "resolution": None,
        "aspect_ratio": None,
        "matched_res": None,
    }

    try:
        out = subprocess.check_output(
            ["xrandr", "--current"], text=True, timeout=5
        )
    except Exception as e:
        decky.logger.error(f"xrandr failed: {e}")
        return result

    # Parse connected outputs and their current/preferred mode
    # Example line: "HDMI-A-1 connected 1920x1080+0+0 ..."
    # Or:           "DP-1 connected primary 2560x1080+0+0 ..."
    for line in out.splitlines():
        # Skip the internal display
        if line.startswith("eDP"):
            continue

        match = re.match(
            r'^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)',
            line
        )
        if match:
            output_name = match.group(1)
            width = int(match.group(2))
            height = int(match.group(3))

            result["connected"] = True
            result["resolution"] = f"{width}x{height}"

            # Determine aspect ratio
            ratio = width / height
            if abs(ratio - 16/9) < 0.05:
                result["aspect_ratio"] = "16:9"
            elif abs(ratio - 16/10) < 0.05:
                result["aspect_ratio"] = "16:10"
            elif abs(ratio - 21/9) < 0.1:
                result["aspect_ratio"] = "21:9"

            # Find best matching supported resolution
            result["matched_res"] = _match_resolution(
                width, height, result["aspect_ratio"]
            )

            decky.logger.info(
                f"External display: {output_name} at {width}x{height} "
                f"(ratio={result['aspect_ratio']}, match={result['matched_res']})"
            )
            break  # Use first external display found

    return result


def _match_resolution(width, height, aspect_ratio):
    """
    Find the closest supported resolution for a detected display.

    Strategy:
    1. If the native res is directly supported, use it
    2. If we know the aspect ratio, pick the highest supported res
       in that ratio that doesn't exceed the native res
    3. Fall back to 1920x1080 (safe default for most monitors)
    """
    native = f"{width}x{height}"
    if native in ALL_SUPPORTED:
        return native

    # Try matching by aspect ratio
    if aspect_ratio and aspect_ratio in SUPPORTED_RESOLUTIONS:
        candidates = SUPPORTED_RESOLUTIONS[aspect_ratio]
        # Pick highest that fits
        for res in candidates:  # already sorted highest-first
            rw, rh = map(int, res.split("x"))
            if rw <= width and rh <= height:
                return res

    # Fallback: 1920x1080 if monitor is big enough, else 1280x720
    if width >= 1920 and height >= 1080:
        return "1920x1080"
    return "1280x720"


# ── Config patching ──────────────────────────────────────────────────────────

def _find_deployed_configs():
    """
    Find all game config files that DeckOps has deployed.

    Uses game_config's config map and dest resolvers to locate the
    actual config file paths on disk. Only returns files that exist.
    """
    deckops_cfg = cfg.load()
    steam_root = deckops_cfg.get("steam_root")
    setup_games = deckops_cfg.get("setup_games", {})

    if not steam_root or not setup_games:
        decky.logger.warning("No steam_root or setup_games in deckops.json")
        return []

    # Get installed games for path resolution
    try:
        library_folders = [steam_root]
        installed = detect_games.find_installed_games(library_folders, steam_root)
    except Exception as e:
        decky.logger.error(f"Failed to detect installed games: {e}")
        return []

    config_map = game_config._build_config_map(steam_root, installed)
    found_configs = []

    for game_key in setup_games:
        if game_key not in config_map:
            continue

        game = installed.get(game_key, {})
        install_dir = game.get("install_dir", "")

        for asset_subpath, fixed_dest in config_map[game_key]:
            # Resolve destination directory
            if fixed_dest:
                # Handle "own" source prefix swap (same logic as game_config.py)
                if game.get("source") == "own" and game.get("compatdata_path"):
                    pfx_parts = fixed_dest.split("/pfx/", 1)
                    if len(pfx_parts) == 2:
                        fixed_dest = os.path.join(
                            game["compatdata_path"], "pfx", pfx_parts[1]
                        )
                dest_dir = fixed_dest
            else:
                if not install_dir:
                    continue
                dest_dir = game_config._dest_from_install(game_key, install_dir)
                if not dest_dir:
                    continue

            config_file = os.path.join(
                dest_dir, os.path.basename(asset_subpath)
            )
            if os.path.exists(config_file):
                found_configs.append({
                    "path": config_file,
                    "game_key": game_key,
                    "filename": os.path.basename(config_file),
                })

    decky.logger.info(f"Found {len(found_configs)} deployed config files")
    return found_configs


def _patch_config(filepath, resolution, refresh_rate):
    """
    Patch r_mode and r_displayRefresh in a single config file.

    Does find-and-replace on the specific dvar lines. Leaves all
    other settings untouched.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (IOError, OSError) as e:
        decky.logger.error(f"Failed to read {filepath}: {e}")
        return False

    original = content

    # Patch r_mode
    content = re.sub(
        r'(seta r_mode\s+")[^"]*(")',
        rf'\g<1>{resolution}\2',
        content
    )

    # Patch r_displayRefresh
    content = re.sub(
        r'(seta r_displayRefresh\s+")[^"]*(")',
        rf'\g<1>{refresh_rate}\2',
        content
    )

    if content == original:
        decky.logger.info(f"No changes needed for {filepath}")
        return True

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        decky.logger.info(f"Patched {filepath}: r_mode={resolution}, refresh={refresh_rate}")
        return True
    except (IOError, OSError) as e:
        decky.logger.error(f"Failed to write {filepath}: {e}")
        return False


def _apply_mode(mode, resolution=None):
    """
    Apply handheld or docked display settings to all deployed configs.

    mode: "handheld" or "docked"
    resolution: for docked, the target resolution (auto-detected if None)

    Returns dict with results.
    """
    deckops_cfg = cfg.load()
    deck_model = deckops_cfg.get("deck_model", "lcd")

    if mode == "handheld":
        target_res = HANDHELD_RES
        target_refresh = HANDHELD_REFRESH.get(deck_model, "60")
    else:
        # Docked mode
        if resolution:
            target_res = resolution
        else:
            display_info = _detect_external_display()
            target_res = display_info.get("matched_res", "1920x1080")
        target_refresh = DOCKED_REFRESH

    configs = _find_deployed_configs()
    patched = 0
    failed = 0

    for config_entry in configs:
        if _patch_config(config_entry["path"], target_res, target_refresh):
            patched += 1
        else:
            failed += 1

    # Save the mode to deckops.json
    cfg.set_play_mode(mode)
    if mode == "docked":
        cfg.set_docked_resolution(target_res)

    decky.logger.info(
        f"Mode set to {mode}: {target_res} @ "
        f"{'auto' if not target_refresh else target_refresh}Hz "
        f"({patched} patched, {failed} failed)"
    )

    return {
        "mode": mode,
        "resolution": target_res,
        "refresh_rate": target_refresh or "auto",
        "patched": patched,
        "failed": failed,
        "total": len(configs),
    }


# ── Plugin class ─────────────────────────────────────────────────────────────

class Plugin:

    async def get_status(self):
        """
        Return current display mode status for the frontend.
        """
        deckops_cfg = cfg.load()
        play_mode = deckops_cfg.get("play_mode", "handheld") or "handheld"
        deck_model = deckops_cfg.get("deck_model", "lcd")
        docked_res = deckops_cfg.get("docked_resolution")

        # Check for external display
        display_info = _detect_external_display()

        return {
            "mode": play_mode,
            "deck_model": deck_model,
            "docked_resolution": docked_res,
            "external_connected": display_info["connected"],
            "external_resolution": display_info["resolution"],
            "external_aspect_ratio": display_info["aspect_ratio"],
            "matched_resolution": display_info["matched_res"],
            "handheld_refresh": HANDHELD_REFRESH.get(deck_model, "60"),
        }

    async def set_handheld(self):
        """Switch all game configs to handheld mode (1280x800)."""
        return _apply_mode("handheld")

    async def set_docked(self, resolution=None):
        """
        Switch all game configs to docked mode.
        If resolution is None, auto-detects from xrandr.
        """
        return _apply_mode("docked", resolution)

    async def detect_display(self):
        """Run xrandr detection and return display info."""
        return _detect_external_display()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def _main(self):
        self.loop = asyncio.get_event_loop()
        decky.logger.info("DeckOps display plugin loaded")

    async def _unload(self):
        decky.logger.info("DeckOps display plugin unloaded")

    async def _uninstall(self):
        decky.logger.info("DeckOps display plugin uninstalled")

    async def _migration(self):
        pass
