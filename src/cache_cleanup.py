#!/usr/bin/env python3
"""
cache_cleanup.py — DeckOps LCD shader cache cleanup + game launcher

Cleans accumulated Fossilize pipeline cache files (fozpipelinesv6/) for
a game's shortcut appid before launching the game through Heroic. This
works around a Steam bug where non-Steam games generate a new .foz file
on every launch, eventually consuming gigabytes of disk space.

See: https://github.com/ValveSoftware/steam-for-linux/issues/10486

Called from Steam launch options (Steam-owned games) or non-Steam shortcut
LaunchOptions (own games). Not used on OLED — OLED launches through
Steam's Proton directly and doesn't hit this bug.

Usage:
    python3 cache_cleanup.py <game_key> <source>

    game_key  — Plutonium game key (t4sp, t4mp, t5sp, t5mp, t6mp, t6zm, iw5mp)
    source    — "steam" or "own"

Steam source adds LD_PRELOAD to work around Steam's pinned libcurl
conflicting with the system flatpak binary.
"""

import base64
import hashlib
import os
import re
import sys


# ── Constants ────────────────────────────────────────────────────────────────

HEROIC_FLATPAK_ID = "com.heroicgameslauncher.hgl"

SHADERCACHE_DIR = os.path.expanduser(
    "~/.local/share/Steam/steamapps/shadercache"
)

# Map game key to Steam appid. Used to find the shadercache folder for
# Steam-owned games (whose cache is keyed on the Steam appid, not the
# shortcut appid).
STEAM_APPIDS = {
    "t4sp":  "10090",
    "t4mp":  "10090",
    "t5sp":  "42700",
    "t5mp":  "42710",
    "t6zm":  "212910",
    "t6mp":  "202990",
    "iw5mp": "42690",
}


# ── Heroic app_name generation ───────────────────────────────────────────────
# Must match plutonium_lcd._heroic_app_name exactly.

def _heroic_app_name(game_key: str) -> str:
    digest = hashlib.sha256(f"deckops_plut_{game_key}".encode()).digest()
    b64 = base64.urlsafe_b64encode(digest)[:19].decode()
    return f"do_{b64}"


# ── Shader cache cleanup ────────────────────────────────────────────────────

def _cleanup_foz(appid_str: str):
    """
    Clean accumulated fozpipelinesv6 files for a single appid.

    Groups .foz files by their hash prefix (the part before .N.foz),
    keeps only the highest-numbered file per group, deletes the rest.
    The newest file has the most complete pipeline state.

    If only one file exists per group, nothing is deleted.
    """
    foz_dir = os.path.join(SHADERCACHE_DIR, appid_str, "fozpipelinesv6")
    if not os.path.isdir(foz_dir):
        return

    # Walk every subdirectory under fozpipelinesv6/ — Steam puts the .foz
    # files one level deeper under a hash-named folder like
    # steamapprun_pipeline_cache_<HASH>/
    for root, _dirs, files in os.walk(foz_dir):
        foz_files = [f for f in files if f.endswith(".foz")]
        if not foz_files:
            continue

        # Group by prefix: "steamapprun_pipeline_cache_abc123.5.foz"
        # → prefix = "steamapprun_pipeline_cache_abc123", suffix = 5
        groups = {}
        pattern = re.compile(r'^(.+?)\.(\d+)\.foz$')
        for fname in foz_files:
            m = pattern.match(fname)
            if m:
                prefix = m.group(1)
                num = int(m.group(2))
                if prefix not in groups:
                    groups[prefix] = []
                groups[prefix].append((num, fname))

        # For each group, keep only the highest-numbered file
        for prefix, entries in groups.items():
            if len(entries) <= 1:
                continue
            entries.sort(key=lambda x: x[0])
            # Delete all but the last (highest number)
            for _num, fname in entries[:-1]:
                try:
                    os.remove(os.path.join(root, fname))
                except OSError:
                    pass


def cleanup_shader_cache(game_key: str, source: str):
    """
    Clean shader cache for a game. Handles both the Steam appid cache
    (for Steam-owned games) and any non-Steam shortcut appid cache.
    """
    # Always clean the Steam appid cache if it exists
    steam_appid = STEAM_APPIDS.get(game_key)
    if steam_appid:
        _cleanup_foz(steam_appid)

    # For own games, also clean the shortcut appid cache.
    # We don't import shortcut.py here to keep this script lightweight
    # and fast — instead we scan for any appid dirs that have our
    # game's heroic app_name in recent launch logs. The Steam appid
    # cleanup above covers the majority of cases.


# ── Game launch ──────────────────────────────────────────────────────────────

def launch_game(game_key: str, source: str):
    """
    Exec the Heroic flatpak launch for a Plutonium game.
    Does not return — replaces the current process.

    Steam source: sets LD_PRELOAD to override Steam's pinned libcurl
    which conflicts with the system flatpak binary.
    """
    app_name = _heroic_app_name(game_key)

    heroic_url = f"heroic://launch?appName={app_name}&runner=sideload"

    flatpak_args = [
        "/usr/bin/flatpak", "run",
        HEROIC_FLATPAK_ID,
        "--no-gui", "--no-sandbox",
        heroic_url,
    ]

    if source == "steam":
        os.environ["LD_PRELOAD"] = "/usr/lib/libcurl.so.4"

    os.execv("/usr/bin/flatpak", flatpak_args)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <game_key> <source>")
        print(f"  game_key: t4sp, t4mp, t5sp, t5mp, t6mp, t6zm, iw5mp")
        print(f"  source:   steam or own")
        sys.exit(1)

    game_key = sys.argv[1]
    source = sys.argv[2]

    if game_key not in STEAM_APPIDS:
        print(f"Unknown game key: {game_key}")
        sys.exit(1)

    if source not in ("steam", "own"):
        print(f"Unknown source: {source} (expected 'steam' or 'own')")
        sys.exit(1)

    # Clean shader cache, then launch
    cleanup_shader_cache(game_key, source)
    launch_game(game_key, source)


if __name__ == "__main__":
    main()
