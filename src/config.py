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
    "setup_games": {},           # key: game key, value: { "client": "cod4x"|"iw4x"|"plutonium", "setup_at": timestamp }
    "game_source": None,         # "steam" or "own"
    "music_enabled": True,       # background music on/off
    "music_volume":  0.4,        # 0.0 to 1.0
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


def mark_game_setup(game_key: str, client: str):
    """
    Record that a game has been set up successfully.
    game_key -- e.g. 'cod4mp', 'iw4mp', 't5sp'
    client   -- e.g. 'cod4x', 'iw4x', 'plutonium'
    """
    config = load()
    config["setup_games"][game_key] = {
        "client": client,
        "setup_at": datetime.now().isoformat(),
    }
    save(config)


def is_game_setup(game_key: str) -> bool:
    """Returns True if this game key has been set up."""
    return game_key in load().get("setup_games", {})


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
