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
    Kept for backwards compatibility -- callers pass this to find_installed_games.
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
# game folders. Used when the user selects "Steam or Other" on the source
# screen, meaning they installed their games via CD, GOG, Microsoft Store, etc.
#
# Detection uses two passes:
#   1. Exact match  -- folder name matches a known Steam install name exactly
#                      (case-insensitive)
#   2. Keyword match -- folder name contains known short codes or title words
#                       checked with word boundaries so short codes like "t4"
#                       don't match unrelated folder names like "startup4"

# Exact folder name -> list of game keys.
# Based on Steam's canonical install directory names.
FOLDER_TO_KEYS = {
    "call of duty 4":                  ["cod4mp", "cod4sp"],
    "call of duty world at war":        ["t4sp",   "t4mp"],
    "call of duty modern warfare 2":    ["iw4sp",  "iw4mp"],
    "call of duty modern warfare 3":    ["iw5sp",  "iw5mp"],
    "call of duty black ops":           ["t5sp",   "t5mp"],
    "call of duty black ops ii":        ["t6sp",   "t6mp",  "t6zm"],
}

# Keyword rules checked in order when exact match fails.
# Each entry is (compiled_regex, keys_list).
# Order matters - more specific rules go first (e.g. "black ops ii" before "black ops").
_KEYWORD_RULES = [
    # BO2 - check before BO1 so "black ops ii" doesn't fall through to BO1
    (re.compile(r'\b(black\s*ops\s*(ii|2)|bo2|t6)\b', re.IGNORECASE), ["t6sp", "t6mp", "t6zm"]),
    # BO1
    (re.compile(r'\b(black\s*ops|bo1|t5)\b', re.IGNORECASE),          ["t5sp", "t5mp"]),
    # MW3 - check before MW2 so "modern warfare 3" doesn't fall through to MW2
    (re.compile(r'\b(modern\s*warfare\s*(3|iii)|mw3|iw5)\b', re.IGNORECASE), ["iw5sp", "iw5mp"]),
    # MW2
    (re.compile(r'\b(modern\s*warfare\s*(2|ii)|mw2|iw4)\b', re.IGNORECASE), ["iw4sp", "iw4mp"]),
    # CoD4 / MW1 - "modern warfare" alone (no number) maps to MW1/CoD4
    (re.compile(r'\b(modern\s*warfare|duty\s*4|duty4|cod4|mw1|iw3)\b', re.IGNORECASE), ["cod4mp", "cod4sp"]),
    # WaW
    (re.compile(r'\b(world\s*at\s*war|waw|t4)\b', re.IGNORECASE),     ["t4sp",  "t4mp"]),
]

# Default scan locations -- case-sensitive on Linux.
OWN_SCAN_PATHS = [
    os.path.expanduser("~/Games"),
    os.path.expanduser("~/games"),
    "/run/media/deck/*/Games",
    "/run/media/deck/*/games",
]

# Maximum directory depth to walk. CoD games are typically 1-3 levels deep
# inside whatever folder the user put them in.
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
        yield dirpath, dirnames, filenames


def _match_folder(name):
    """
    Try to match a folder name to a set of game keys.
    Returns a list of keys or an empty list if no match.

    Pass 1 - exact match (case-insensitive).
    Pass 2 - keyword regex rules in priority order.
    """
    name_lower = name.lower()

    # Pass 1 - exact
    if name_lower in FOLDER_TO_KEYS:
        return FOLDER_TO_KEYS[name_lower]

    # Pass 2 - keyword
    for pattern, keys in _KEYWORD_RULES:
        if pattern.search(name):
            return keys

    return []


def find_own_installed(extra_paths=None, on_progress=None):
    """
    Scan the filesystem for known Call of Duty game folders outside of Steam.

    Searches ~/Games, ~/games, SD card game folders, plus any user-provided
    extra paths (e.g. from a folder picker in the UI).

    Matches on folder names using exact then keyword rules - no exe scanning.
    Once a folder matches, we don't descend into it further.

    Returns the same dict structure as find_installed_games() with an added
    "source": "own" field so the rest of the install flow works unchanged.

    extra_paths -- optional list of additional directories to scan
    on_progress -- optional callback(msg: str)
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

    for scan_dir in scan_dirs:
        prog(f"Scanning {scan_dir}...")
        for dirpath, dirnames, _filenames in _walk_limited(scan_dir, _MAX_SCAN_DEPTH):
            folder_name = os.path.basename(dirpath)
            matched_keys = _match_folder(folder_name)

            if not matched_keys:
                continue

            # Stop descending into this folder - it's a game install dir
            dirnames.clear()

            for key in matched_keys:
                if key in found:
                    continue
                meta = GAMES.get(key)
                if not meta:
                    continue

                exe_path = os.path.join(dirpath, meta["exe"])
                found[key] = {
                    **meta,
                    "install_dir": dirpath,
                    "exe_path":    exe_path,
                    "exe_size":    get_exe_size(exe_path),
                    "source":      "own",
                }
                prog(f"  found {key}: {meta['name']} at {dirpath}")

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
            print(f"        {game['install_dir']}")
