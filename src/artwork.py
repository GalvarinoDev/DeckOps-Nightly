"""
artwork.py - DeckOps Steam artwork downloader for non-Steam shortcuts

Downloads artwork for games detected via the "My Own" path (CD, GOG,
Microsoft Store, etc.) and writes it into each Steam user's grid
directory under the correct shortcut appid filename so Steam displays
it properly in the library.

Artwork types per game:
    <appid>p.<ext>         -- capsule (600x900, library grid view)
    <appid>.<ext>          -- header (wide, library list + store page)
    <appid>_hero.<ext>     -- hero banner (behind logo on game page)
    <appid>_logo.<ext>     -- logo (overlaid on hero)
    <appid>_icon.<ext>     -- icon (taskbar and shortcut)

Called from detect_shortcuts.find_own_games() right after the shortcut
rename so the artwork and name change land together before Steam reopens.
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

# ── Per-game artwork URLs ─────────────────────────────────────────────────────
#
# Hardcoded so every game gets the right art regardless of what Steam's CDN
# decides to serve. SP titles pull from Steam's official store assets.
# MP/ZM titles use community artwork from SteamGridDB.
#
# Credits (SteamGridDB profiles):
#   https://www.steamgriddb.com/profile/76561197985524535
#   https://www.steamgriddb.com/profile/76561198015449572
#   https://www.steamgriddb.com/profile/76561198018073166
#   https://www.steamgriddb.com/profile/76561198018403239
#   https://www.steamgriddb.com/profile/76561198022992095
#   https://www.steamgriddb.com/profile/76561198027273869
#   https://www.steamgriddb.com/profile/76561198031582867
#   https://www.steamgriddb.com/profile/76561198038608428
#   https://www.steamgriddb.com/profile/76561198040056867
#   https://www.steamgriddb.com/profile/76561198041593264
#   https://www.steamgriddb.com/profile/76561198135110632
#   https://www.steamgriddb.com/profile/76561198143575007
#   https://www.steamgriddb.com/profile/76561198319864298
#   https://www.steamgriddb.com/profile/76561199034037601

OWN_ARTWORK = {
    # ── MW1 ───────────────────────────────────────────────────────────────
    "cod4sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/library_hero_2x.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/7940/b40c43b0b14b7e124553e0220581a1b9ef8e38bf.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "cod4mp": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/69a24bf40cd265fb00ae685cdaa040c7.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/7a22b900577a6edbffd53153cea2999c.jpg",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/95bc8e097e09212ec0160a7bc0b46fd6.jpg",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/0440169a43de927753429dd69ca8c735.png",
        "icon_url":    "https://cdn2.steamgriddb.com/icon/59b109c700b500daa9ef3a6769bc8c6f.png",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "png",
    },

    # ── MW2 ───────────────────────────────────────────────────────────────
    "iw4sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/library_hero_2x.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10180/ad502494f1658220f9166c7e17ac90422bf6a479.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "iw4mp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/10190/header.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/4f4ecc161b18f07dcf2c8296fad55709.jpg",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/1fc214004c9481e4c8073e85323bfd4b.png",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/d79aac075930c83c2f1e369a511148fe.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10190/7dd7c2d5bce2413131762d7cbee3f059614ed69d.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "png",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },

    # ── MW3 ───────────────────────────────────────────────────────────────
    "iw5sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/library_hero_2x.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42680/c3330a875925437d8216949b6571f6e941ba0679.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "iw5mp": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/ce65f40e3a20ad19fe352c52ce3bcf51.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/54726e7600c9c297610f6ed9d7d19ca7.jpg",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/51770b1e6f66ba5d45e58a76e6a73dc2.jpg",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/4a64d913220fca4c33c140c6952688a8.png",
        "icon_url":    "https://cdn2.steamgriddb.com/icon_thumb/67b48cc32ab9f04633bd50656a4a26fc.png",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "png",
    },

    # ── WaW ───────────────────────────────────────────────────────────────
    "t4sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/library_hero_2x.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/10090/2bfb85222af4a01842baa5c3a16a080eb27ac6c3.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "t4mp": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/a6a0076c7e1907a4555b17cc2a6ebc85.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/grid/bb933c55afc6987ae406e48ff58786d6.png",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/e369853df766fa44e1ed0ff613f563bd.jpg",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/0a32bfcf5c87aa42d2a0367c1f6bb17c.png",
        "icon_url":    "https://cdn2.steamgriddb.com/icon/854d6fae5ee42911677c739ee1734486.png",
        "header_ext":  "jpg",
        "capsule_ext": "png",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "png",
    },

    # ── BO1 ───────────────────────────────────────────────────────────────
    "t5sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/library_hero.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42700/ea744d59efded3feaeebcafed224be9eadde90ac.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "t5mp": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/a6330e9317a50ccf2d79c295dd18046f.png",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/978f9d25644371a4c4b8df8c994cd880.png",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/dc82d632c9fcecb0778afbc7924494a6.png",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/dfb84a11f431c62436cfb760e30a34fe.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/42710/d595fb4b01201cade09e1232f2c41c0866840628.jpg",
        "header_ext":  "png",
        "capsule_ext": "png",
        "hero_ext":    "png",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },

    # ── BO2 ───────────────────────────────────────────────────────────────
    "t6sp": {
        "header_url":  "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/header.jpg",
        "capsule_url": "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/library_600x900_2x.jpg",
        "hero_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/library_hero.jpg",
        "logo_url":    "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/logo_2x.png",
        "icon_url":    "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/202970/0a23d78ade8c8d7b4cfa15bf71c9dd535b2998ca.jpg",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "jpg",
    },
    "t6zm": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/b87c4d009662bc436961d8f753a8de78.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/3d9ffc992e48d2aeb4b06f05471f619d.jpg",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/e5e63da79fcd2bebbd7cb8bf1c1d0274.jpg",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/79514e888b8f2acacc68738d0cbb803e.png",
        "icon_url":    "https://cdn2.steamgriddb.com/icon_thumb/743c11a9f3cb65cda4994bbdfb66c398.png",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "jpg",
        "logo_ext":    "png",
        "icon_ext":    "png",
    },
    "t6mp": {
        "header_url":  "https://cdn2.steamgriddb.com/thumb/d841ee63e07b28f94920b81d2e4c21c9.jpg",
        "capsule_url": "https://cdn2.steamgriddb.com/thumb/7d3695ac5fbf55fb65ea261dd3a8577c.jpg",
        "hero_url":    "https://cdn2.steamgriddb.com/hero_thumb/731c83db8d2ff01bdc000083fd3c3740.png",
        "logo_url":    "https://cdn2.steamgriddb.com/logo_thumb/6271faadeedd7626d661856b7a004e27.png",
        "icon_url":    "https://cdn2.steamgriddb.com/icon_thumb/715eb56d3f3b71792e230102d1da496d.png",
        "header_ext":  "jpg",
        "capsule_ext": "jpg",
        "hero_ext":    "png",
        "logo_ext":    "png",
        "icon_ext":    "png",
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

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
            if len(data) < 1024:
                return False
            with open(dest, "wb") as f:
                f.write(data)
        return True
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def download_artwork(game_key: str, shortcut_appid: int, on_progress=None):
    """
    Download artwork for a single own game and write it into every Steam
    user's grid directory under the correct shortcut appid filenames.

    game_key       -- e.g. "iw4mp", "t4sp"
    shortcut_appid -- the CRC-based appid Steam uses for this shortcut
    on_progress    -- optional callback(msg: str)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    art = OWN_ARTWORK.get(game_key)
    if not art:
        prog(f"  No artwork defined for {game_key}")
        return

    uids = _find_all_steam_uids()
    if not uids:
        prog(f"  No Steam user accounts found, skipping artwork")
        return

    appid_str = str(shortcut_appid)

    # Map each artwork type to its grid filename
    artwork_map = [
        ("header_url",  f"{appid_str}.{art['header_ext']}",       "header"),
        ("capsule_url", f"{appid_str}p.{art['capsule_ext']}",     "capsule"),
        ("hero_url",    f"{appid_str}_hero.{art['hero_ext']}",    "hero"),
        ("logo_url",    f"{appid_str}_logo.{art['logo_ext']}",    "logo"),
        ("icon_url",    f"{appid_str}_icon.{art['icon_ext']}",    "icon"),
    ]

    for url_key, filename, label in artwork_map:
        url = art.get(url_key, "")
        if not url:
            continue

        # Download once, then copy to all user grid dirs
        downloaded = None
        for uid in uids:
            grid_dir  = os.path.join(USERDATA_DIR, uid, "config", "grid")
            dest_path = os.path.join(grid_dir, filename)

            if os.path.exists(dest_path):
                prog(f"    ✓ {label} (cached)")
                downloaded = True
                break

        if downloaded:
            continue

        # Download to first user's grid dir, then copy to the rest
        first_uid = uids[0]
        first_grid = os.path.join(USERDATA_DIR, first_uid, "config", "grid")
        first_dest = os.path.join(first_grid, filename)

        if _download(url, first_dest):
            prog(f"    ✓ {label}")
            # Copy to remaining users
            for uid in uids[1:]:
                grid_dir = os.path.join(USERDATA_DIR, uid, "config", "grid")
                dest_path = os.path.join(grid_dir, filename)
                os.makedirs(grid_dir, exist_ok=True)
                try:
                    import shutil
                    shutil.copy2(first_dest, dest_path)
                except Exception:
                    pass
        else:
            prog(f"    ⚠ {label} failed")
