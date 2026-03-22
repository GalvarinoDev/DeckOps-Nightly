"""
artwork.py - DeckOps Steam artwork downloader for non-Steam shortcuts

Downloads official Steam artwork for games detected via the "My Own" path
(CD, GOG, Microsoft Store, etc.) and writes it into each Steam user's
grid directory under the correct shortcut appid filename so Steam displays
it properly in the library.

Artwork types downloaded per game:
    <appid>p.jpg          — grid/capsule (600x900)
    <appid>.jpg           — wide capsule (header)
    <appid>_hero.jpg      — hero banner
    <appid>_logo.png      — logo
    <appid>_icon.jpg      — icon

Must be called after find_own_games() so shortcut_appid values are known.
Steam must be closed before calling this so it picks up the new artwork
on next launch.
"""

import os
import urllib.request

STEAM_DIR    = os.path.expanduser("~/.local/share/Steam")
USERDATA_DIR = os.path.join(STEAM_DIR, "userdata")
MIN_UID      = 10000

_BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

_CDN = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/{filename}"

# Some games share artwork between their SP and MP appids.
# MP appids listed here use their SP counterpart's artwork instead.
# Mirrors the logic in bootstrap.py _HEADER_OVERRIDES.
_APPID_ART_OVERRIDES = {
    "10190":  "10180",   # MW2 MP  -> MW2 SP art
    "42690":  "42680",   # MW3 MP  -> MW3 SP art
    "202990": "202970",  # BO2 MP  -> BO2 SP art
    "42710":  "42700",   # BO1 MP  -> BO1 SP art
    "212910": "202970",  # BO2 ZM  -> BO2 SP art
}

# Artwork files to download per game, as (filename, dest_suffix) pairs.
# dest_suffix is appended to the shortcut_appid to form the grid filename.
_ARTWORK_FILES = [
    ("library_600x900.jpg", "p.jpg"),     # grid/capsule
    ("header.jpg",          ".jpg"),       # wide capsule
    ("library_hero.jpg",    "_hero.jpg"),  # hero banner
    ("logo.png",            "_logo.png"),  # logo
    ("icon.jpg",            "_icon.jpg"),  # icon
]


def _find_all_steam_uids() -> list[str]:
    """Return all valid Steam user ID folders from userdata/."""
    if not os.path.isdir(USERDATA_DIR):
        return []
    seen, uids = set(), []
    for entry in os.listdir(USERDATA_DIR):
        if not entry.isdigit() or int(entry) < MIN_UID:
            continue
        real = os.path.realpath(os.path.join(USERDATA_DIR, entry))
        if real in seen:
            continue
        seen.add(real)
        uids.append(entry)
    return uids


def _download(url: str, dest: str) -> bool:
    """Download a file from URL to dest. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers=_BROWSER_UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            # Steam returns a small error page for missing artwork rather
            # than a 404 in some cases. Skip files under 1KB.
            if len(data) < 1024:
                return False
            with open(dest, "wb") as f:
                f.write(data)
        return True
    except Exception:
        return False


def download_artwork_for_own_games(own_games: dict, on_progress=None) -> None:
    """
    Download Steam artwork for all detected own games and write it into
    each Steam user's grid directory under the correct shortcut appid filename.

    own_games  — dict returned by detect_shortcuts.find_own_games()
    on_progress — optional callback(msg: str)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    uids = _find_all_steam_uids()
    if not uids:
        prog("No Steam user accounts found, skipping artwork download.")
        return

    # Cache downloaded artwork locally so we only hit Steam CDN once per game
    # regardless of how many Steam user accounts exist on the Deck.
    cache_dir = os.path.join(
        os.path.expanduser("~"), "DeckOps-Nightly", "assets", "images", "own_art"
    )
    os.makedirs(cache_dir, exist_ok=True)

    for key, game in own_games.items():
        shortcut_appid = str(game.get("shortcut_appid", ""))
        if not shortcut_appid:
            prog(f"  ⚠ {key}: no shortcut_appid, skipping artwork")
            continue

        steam_appid = str(game.get("appid", ""))
        # Use the art override appid if one exists so MP titles get
        # the correct artwork from their SP counterpart.
        art_appid = _APPID_ART_OVERRIDES.get(steam_appid, steam_appid)

        prog(f"  Downloading artwork for {game.get('name', key)} (appid {art_appid})...")

        for cdn_filename, dest_suffix in _ARTWORK_FILES:
            url        = _CDN.format(appid=art_appid, filename=cdn_filename)
            cache_path = os.path.join(cache_dir, f"{art_appid}_{cdn_filename}")

            # Download to cache if not already there
            if not os.path.exists(cache_path):
                ok = _download(url, cache_path)
                if not ok:
                    prog(f"    - {cdn_filename} not available, skipping")
                    continue
            else:
                prog(f"    (cached) {cdn_filename}")

            # Copy cached file into every user's grid directory
            for uid in uids:
                grid_dir  = os.path.join(USERDATA_DIR, uid, "config", "grid")
                dest_name = f"{shortcut_appid}{dest_suffix}"
                dest_path = os.path.join(grid_dir, dest_name)
                os.makedirs(grid_dir, exist_ok=True)
                try:
                    import shutil
                    shutil.copy2(cache_path, dest_path)
                except Exception as ex:
                    prog(f"    ⚠ Could not write {dest_name} for uid {uid}: {ex}")

            prog(f"    ✓ {cdn_filename}")

    prog("Artwork download complete.")
