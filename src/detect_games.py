import os
import re
import glob

# Paths where Steam is commonly installed on Linux
STEAM_PATHS = [
    os.path.expanduser("~/.local/share/Steam"),
    os.path.expanduser("~/.steam/steam"),
]

# Known SD card mount point patterns on Steam Deck
SD_CARD_PATTERNS = [
    "/run/media/deck/*/SteamLibrary",
    "/run/media/deck/*",
    "/run/media/mmcblk0p1/SteamLibrary",
    "/run/media/mmcblk0p1",
]

# Maps game key to metadata for each supported title.
#
# Most games use a mod client (cod4x, iw4x, plutonium) and have a protocol
# URL that the wrapper script launches. Games with protocol "steam" are
# vanilla Steam titles with no mod client. They're tracked here so DeckOps
# can detect them, apply display configs, assign controller profiles, and
# show them on the right cards in the UI. They don't get a wrapper script
# or any exe replacement.

GAMES = {
    "t4sp":  {
        "name": "Call of Duty: World at War",
        "order": 2,
        "appid": "10090",
        "exe": "CoDWaW.exe",
        "protocol": "plutonium://play/t4sp",
        "xact": True
    },
    "t4mp":  {
        "name": "Call of Duty: World at War - Multiplayer",
        "order": 2,
        "appid": "10090",
        "exe": "CoDWaWmp.exe",
        "protocol": "plutonium://play/t4mp",
        "xact": True
    },
    "t5sp":  {
        "name": "Call of Duty: Black Ops",
        "order": 4,
        "appid": "42700",
        "exe": "BlackOps.exe",
        "protocol": "plutonium://play/t5sp",
        "xact": True
    },
    "t5mp":  {
        "name": "Call of Duty: Black Ops - Multiplayer",
        "order": 4,
        "appid": "42710",
        "exe": "BlackOpsMP.exe",
        "protocol": "plutonium://play/t5mp",
        "xact": True
    },
    "t6mp":  {
        "name": "Call of Duty: Black Ops II - Multiplayer",
        "order": 6,
        "appid": "202990",
        "exe": "t6mp.exe",
        "protocol": "plutonium://play/t6mp",
        "xact": False
    },
    "t6zm":  {
        "name": "Call of Duty: Black Ops II - Zombies",
        "order": 6,
        "appid": "212910",
        "exe": "t6zm.exe",
        "protocol": "plutonium://play/t6zm",
        "xact": False
    },
    "t6sp":  {
        "name": "Call of Duty: Black Ops II - Singleplayer",
        "order": 6,
        "appid": "202970",
        "exe": "t6sp.exe",
        "protocol": "steam",
        "xact": False
    },
    "iw5mp": {
        "name": "Call of Duty: Modern Warfare 3 (2011) - Multiplayer",
        "order": 5,
        "appid": "42690",
        "exe": "iw5mp.exe",
        "protocol": "plutonium://play/iw5mp",
        "xact": False
    },
    "iw5sp": {
        "name": "Call of Duty: Modern Warfare 3 (2011) - Singleplayer",
        "order": 5,
        "appid": "42680",
        "exe": "iw5sp.exe",
        "protocol": "steam",
        "xact": False
    },
    "iw4mp": {
        "name": "Call of Duty: Modern Warfare 2 (2009) - Multiplayer",
        "order": 3,
        "appid": "10190",
        "exe": "iw4mp.exe",
        "protocol": "iw4x",
        "xact": False
    },
    "iw4sp": {
        "name": "Call of Duty: Modern Warfare 2 (2009) - Singleplayer",
        "order": 3,
        "appid": "10180",
        "exe": "iw4sp.exe",
        "protocol": "steam",
        "xact": False
    },
    "cod4mp": {
        "name": "Call of Duty 4: Modern Warfare (2007) - Multiplayer",
        "order": 1,
        "appid": "7940",
        "exe": "iw3mp.exe",
        "protocol": "cod4x",
        "xact": False
    },
    "cod4sp": {
        "name": "Call of Duty 4: Modern Warfare (2007) - Singleplayer",
        "order": 1,
        "appid": "7940",
        "exe": "iw3sp.exe",
        "protocol": "iw3sp",
        "xact": False
    },
}


def get_exe_size(exe_path):
    if os.path.exists(exe_path):
        return os.path.getsize(exe_path)
    return None


def find_steam_root():
    for path in STEAM_PATHS:
        if os.path.exists(path):
            return path
    return None


def _all_library_dirs(steam_root):
    """
    Returns a deduplicated list of all steamapps directories to search.
    Covers:
      - The main Steam install
      - Every path listed in libraryfolders.vdf
      - SD card mount points via glob (handles any card name/label)
    """
    seen = set()
    dirs = []

    def add(path):
        path = os.path.normpath(path)
        if path not in seen:
            seen.add(path)
            dirs.append(path)

    # 1. Main Steam steamapps
    if steam_root:
        add(os.path.join(steam_root, "steamapps"))

    # 2. libraryfolders.vdf entries
    if steam_root:
        vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf_path):
            with open(vdf_path, "r", errors="replace") as f:
                content = f.read()
            for path in re.findall(r'"path"\s+"([^"]+)"', content):
                add(os.path.join(path, "steamapps"))
                # Some SD card libraries use a SteamLibrary subfolder
                add(os.path.join(path, "SteamLibrary", "steamapps"))

    # 3. Brute-force SD card mount points — catches any card regardless of label
    for pattern in SD_CARD_PATTERNS:
        for match in glob.glob(pattern):
            if os.path.isdir(match):
                add(os.path.join(match, "steamapps"))
                add(os.path.join(match, "SteamLibrary", "steamapps"))

    return dirs


def parse_library_folders(steam_root):
    """
    Returns all library root dirs (not steamapps subdirs).
    Kept for backwards compatibility — callers pass this to find_installed_games.
    """
    dirs = []
    if steam_root:
        dirs.append(steam_root)
    vdf_path = os.path.join(steam_root or "", "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf_path):
        with open(vdf_path, "r", errors="replace") as f:
            content = f.read()
        for path in re.findall(r'"path"\s+"([^"]+)"', content):
            if path not in dirs:
                dirs.append(path)
    return dirs


def find_installed_games(library_folders, steam_root=None):
    """
    Scans all Steam library folders and returns a dict of installed DeckOps-supported games.
    Keys are game keys (e.g. 'iw4mp'), values are game info dicts.
    """
    if steam_root is None and library_folders:
        steam_root = library_folders[0]

    all_steamapps_dirs = _all_library_dirs(steam_root)
    installed = {}

    for key, meta in GAMES.items():
        appid = meta["appid"]
        exe   = meta["exe"]

        for steamapps_dir in all_steamapps_dirs:
            acf = os.path.join(steamapps_dir, f"appmanifest_{appid}.acf")
            if not os.path.exists(acf):
                continue

            # Parse install dir name from acf
            install_name = None
            with open(acf, "r", errors="replace") as f:
                for line in f:
                    m = re.search(r'"installdir"\s+"([^"]+)"', line)
                    if m:
                        install_name = m.group(1)
                        break

            if not install_name:
                continue

            install_dir = os.path.join(steamapps_dir, "common", install_name)
            exe_path    = os.path.join(install_dir, exe)

            if os.path.exists(install_dir):
                installed[key] = {
                    **meta,
                    "install_dir": install_dir,
                    "exe_path":    exe_path,
                    "exe_size":    get_exe_size(exe_path),
                }
                break

    return installed


# ── "My Own" game detection ───────────────────────────────────────────────────
# Scans common game install locations on Steam Deck for known Call of Duty
# executables. Used when the user selects "My Own" on the source screen,
# meaning they installed their games via CD, GOG, Microsoft Store, etc.

# Map exe filename (lowercase) to game key(s).
EXE_TO_KEYS = {
    "iw3mp.exe":      ["cod4mp"],
    "iw3sp.exe":      ["cod4sp"],
    "iw4mp.exe":      ["iw4mp"],
    "iw4sp.exe":      ["iw4sp"],
    "iw5mp.exe":      ["iw5mp"],
    "iw5sp.exe":      ["iw5sp"],
    "codwaw.exe":     ["t4sp"],
    "codwawmp.exe":   ["t4mp"],
    "blackops.exe":   ["t5sp"],
    "blackopsmp.exe": ["t5mp"],
    "t6zm.exe":       ["t6zm"],
    "t6mp.exe":       ["t6mp"],
    "t6sp.exe":       ["t6sp"],
}

# Default scan locations — case-sensitive on Linux.
OWN_SCAN_PATHS = [
    os.path.expanduser("~/Games"),
    os.path.expanduser("~/games"),
    "/run/media/deck/*/Games",
    "/run/media/deck/*/games",
]

# Maximum directory depth to walk. CoD games are typically 1-3 levels deep.
_MAX_SCAN_DEPTH = 5


def _walk_limited(root, max_depth):
    """Walk a directory tree up to max_depth levels deep."""
    skip = {".steam", ".local", ".cache", ".config", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in skip]
        yield dirpath, filenames


def find_own_installed(extra_paths=None, on_progress=None):
    """
    Scan the filesystem for known Call of Duty executables outside of Steam.

    Searches ~/Games, ~/games, SD card game folders, plus any user-provided
    extra paths (e.g. from a folder picker in the UI).

    Returns the same dict structure as find_installed_games() with an added
    "source": "own" field, so the rest of the install flow works unchanged.

    extra_paths — optional list of additional directories to scan
    on_progress — optional callback(msg: str)
    """
    def prog(msg):
        if on_progress:
            on_progress(msg)

    # Build scan list: defaults + globs + extras
    scan_dirs = []
    seen = set()
    for pattern in OWN_SCAN_PATHS:
        for path in glob.glob(pattern):
            path = os.path.normpath(path)
            if path not in seen and os.path.isdir(path):
                seen.add(path)
                scan_dirs.append(path)
    if extra_paths:
        for path in extra_paths:
            path = os.path.normpath(path)
            if path not in seen and os.path.isdir(path):
                seen.add(path)
                scan_dirs.append(path)

    if not scan_dirs:
        prog("No game folders found to scan.")
        return {}

    found = {}
    exe_lookup = {name.lower(): keys for name, keys in EXE_TO_KEYS.items()}

    for scan_dir in scan_dirs:
        prog(f"Scanning {scan_dir}...")
        for dirpath, filenames in _walk_limited(scan_dir, _MAX_SCAN_DEPTH):
            for fname in filenames:
                fname_lower = fname.lower()
                if fname_lower not in exe_lookup:
                    continue

                exe_path = os.path.join(dirpath, fname)
                if not os.path.isfile(exe_path):
                    continue

                keys = exe_lookup[fname_lower]
                for key in keys:
                    if key in found:
                        continue
                    meta = GAMES.get(key)
                    if not meta:
                        continue

                    found[key] = {
                        **meta,
                        "install_dir": dirpath,
                        "exe_path":    exe_path,
                        "exe_size":    get_exe_size(exe_path),
                        "source":      "own",
                    }
                    prog(f"  ✓ {key}: {meta['name']}")

    if not found:
        prog("No supported games found.")
    else:
        prog(f"Found {len(found)} game(s).")

    return found


if __name__ == "__main__":
    steam_root = find_steam_root()
    if not steam_root:
        print("Steam not found.")
    else:
        print(f"Steam found at: {steam_root}")
        libraries = parse_library_folders(steam_root)
        print(f"Libraries found:")
        for lib in libraries:
            print(f"  {lib}")
        installed = find_installed_games(libraries)
        print(f"\nInstalled games ({len(installed)}):")
        for key, game in installed.items():
            print(f"  [{key}] {game['name']}")
            print(f"        {game['exe_path']} ({game['exe_size']} bytes)")
