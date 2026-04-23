"""
config.py - DeckOps configuration manager

Handles reading and writing deckops.json which lives at:
    ~/DeckOps-Nightly/deckops.json

The config file tracks:
    - Whether first-time setup has been completed
    - Which Deck model the user has (oled or lcd)
    - Which games have been set up and when
    - The Steam root path found during setup
"""

import os
import json
import re
from datetime import datetime

CONFIG_PATH = os.path.expanduser("~/DeckOps-Nightly/deckops.json")

DEFAULTS = {
    "first_run_complete": False,
    "deck_model": None,          # "oled" or "lcd"
    "gyro_mode":  None,          # "hold", "toggle", or "ads"
    "play_mode":  None,          # "handheld" or "docked"
    "external_controller": None, # "playstation", "xbox", or "other" -- only used when play_mode is "docked"
    "docked_resolution": None,   # "1280x720", "1280x800", "1920x1080", "1920x1200", or "own" -- only used when play_mode is "docked"
                                 # NOTE: this will also be used for future Bazzite, Steam Box, and other handheld support on SteamOS
    "ge_proton_version": None,   # e.g. "GE-Proton10-32"
    "steam_root": None,
    "setup_games": {},           # key: game key, value: { "client": ..., "source": "steam"|"own", "setup_at": timestamp,
                                 #   "lan_wrapper_path": path to -lan bash script for offline launcher (all sources) }
    "game_source": None,         # "steam" or "own"
    "music_enabled": True,       # background music on/off
    "music_volume":  0.4,        # 0.0 to 1.0
    "player_name": None,         # in-game player name for configs and LCD Plutonium
}


def load() -> dict:
    """
    Load config from disk. Returns defaults if file doesn't exist yet.
    """
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULTS)


def save(config: dict):
    """
    Write config to disk. Creates the directory if needed.
    """
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def is_first_run() -> bool:
    """Returns True if setup has never been completed."""
    return not load().get("first_run_complete", False)


def get_deck_model() -> str | None:
    """Returns 'oled', 'lcd', or None if not yet set."""
    return load().get("deck_model")


def set_deck_model(model: str):
    """Save the user's Deck model. model should be 'oled' or 'lcd'."""
    config = load()
    config["deck_model"] = model
    save(config)


def is_oled() -> bool:
    return load().get("deck_model") == "oled"


def get_gyro_mode() -> str | None:
    """Returns 'hold', 'toggle', 'ads', or None if not yet set."""
    return load().get("gyro_mode")


def set_gyro_mode(mode: str):
    """Save the user's gyro preference. mode should be 'hold', 'toggle', or 'ads'."""
    config = load()
    config["gyro_mode"] = mode
    save(config)


def get_play_mode() -> str | None:
    """Returns 'handheld', 'docked', or None if not yet set."""
    return load().get("play_mode")


def set_play_mode(mode: str):
    """Save the user's play mode. mode should be 'handheld' or 'docked'."""
    config = load()
    config["play_mode"] = mode
    save(config)


def is_docked() -> bool:
    return load().get("play_mode") == "docked"


def get_external_controller() -> str | None:
    """Returns 'playstation', 'xbox', 'other', or None if not yet set."""
    return load().get("external_controller")


def set_external_controller(controller_type: str):
    """Save the user's external controller type. Should be 'playstation', 'xbox', or 'other'."""
    config = load()
    config["external_controller"] = controller_type
    save(config)


def get_docked_resolution() -> str | None:
    """Returns '1280x720', '1280x800', '1920x1080', '1920x1200', 'own', or None."""
    return load().get("docked_resolution")


def set_docked_resolution(resolution: str):
    """Save the user's docked display resolution. 'own' means user sets it in-game."""
    config = load()
    config["docked_resolution"] = resolution
    save(config)


def get_game_source() -> str | None:
    """Returns 'steam', 'own', or None if not yet set."""
    return load().get("game_source")


def set_game_source(source: str):
    """Save game source. source should be 'steam' or 'own'."""
    config = load()
    config["game_source"] = source
    save(config)


def get_music_enabled() -> bool:
    """Returns True if background music is enabled."""
    return load().get("music_enabled", True)


def set_music_enabled(enabled: bool):
    """Save background music on/off preference."""
    config = load()
    config["music_enabled"] = enabled
    save(config)


def get_music_volume() -> float:
    """Returns music volume as a float between 0.0 and 1.0."""
    return load().get("music_volume", 0.4)


def set_music_volume(volume: float):
    """Save music volume. Clamped to 0.0 - 1.0."""
    config = load()
    config["music_volume"] = max(0.0, min(1.0, volume))
    save(config)


def get_ge_proton_version() -> str | None:
    """Returns the installed GE-Proton version string, e.g. 'GE-Proton10-32', or None."""
    return load().get("ge_proton_version")


def set_ge_proton_version(version: str):
    """Save the installed GE-Proton version after CompatToolMapping is applied."""
    config = load()
    config["ge_proton_version"] = version
    save(config)


def get_player_name() -> str | None:
    """Returns the player's chosen in-game name, or None if not yet set."""
    return load().get("player_name")


def set_player_name(name: str):
    """Save the player's chosen in-game name."""
    config = load()
    config["player_name"] = name.strip() if name else None
    save(config)


def get_steam_display_name(steam_root: str | None = None) -> str | None:
    """
    Read the active Steam user's display name from loginusers.vdf.

    Looks for the account with MostRecent=1 and returns its PersonaName.
    Falls back to the first account if MostRecent is not set.
    Returns None if the file can't be read or parsed.

    steam_root -- path to Steam root. Defaults to ~/.local/share/Steam
    """
    if not steam_root:
        steam_root = os.path.expanduser("~/.local/share/Steam")
    vdf_path = os.path.join(steam_root, "config", "loginusers.vdf")
    if not os.path.exists(vdf_path):
        return None
    try:
        with open(vdf_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return None

    # Parse all accounts: find PersonaName and MostRecent per block
    # VDF is simple enough here to use regex instead of a full parser
    first_name = None
    most_recent_name = None
    # Split into per-account blocks by finding Steam ID headers
    blocks = re.split(r'"\d{17}"\s*\{', content)
    for block in blocks[1:]:  # skip the "users" { header
        persona = re.search(r'"PersonaName"\s+"([^"]*)"', block)
        recent = re.search(r'"MostRecent"\s+"1"', block)
        if persona:
            name = persona.group(1)
            if first_name is None:
                first_name = name
            if recent:
                most_recent_name = name

    return most_recent_name or first_name


def mark_game_setup(game_key: str, client: str, source: str = "steam",
                    wrapper_path: str = None,
                    lan_wrapper_path: str = None):
    """
    Record that a game has been set up successfully.
    game_key         -- e.g. 'cod4mp', 'iw4mp', 't5sp'
    client           -- e.g. 'cod4x', 'iw4x', 'plutonium'
    source           -- 'steam' or 'own' (which install path was used)
    wrapper_path     -- optional path to the online launcher wrapper script
                        (OLED own games, used by legacy callers)
    lan_wrapper_path -- optional path to the -lan bash script for offline
                        mode. Used by the offline launcher for all sources
                        and both hardware models.
    """
    config = load()
    entry = {
        "client": client,
        "source": source,
        "setup_at": datetime.now().isoformat(),
    }
    if wrapper_path:
        entry["wrapper_path"] = wrapper_path
    if lan_wrapper_path:
        entry["lan_wrapper_path"] = lan_wrapper_path
    config["setup_games"][game_key] = entry
    save(config)


def is_game_setup(game_key: str) -> bool:
    """Returns True if this game key has been set up (any source)."""
    return game_key in load().get("setup_games", {})


def unmark_game_setup(game_keys):
    """
    Remove one or more game keys from setup_games so they appear as
    'not set up' in ManagementScreen. Accepts a single string or a list.
    Used when the user wants to do a clean reinstall of a game.
    """
    if isinstance(game_keys, str):
        game_keys = [game_keys]
    config = load()
    changed = False
    for key in game_keys:
        if key in config.get("setup_games", {}):
            del config["setup_games"][key]
            changed = True
    if changed:
        save(config)


def is_game_setup_for_source(game_key: str, source: str) -> bool:
    """Returns True if this game key has been set up from the given source.
    Entries without a 'source' field are treated as 'steam' for backward compat."""
    entry = load().get("setup_games", {}).get(game_key)
    if entry is None:
        return False
    return entry.get("source", "steam") == source


def get_setup_games() -> dict:
    """Returns the full setup_games dict."""
    return load().get("setup_games", {})


def complete_first_run(steam_root: str):
    """
    Call this at the end of the setup wizard to mark first run as done.
    """
    config = load()
    config["first_run_complete"] = True
    config["steam_root"] = steam_root
    save(config)


def reset():
    """
    Wipe the config and start fresh. Useful for testing or reinstalling.
    """
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)
