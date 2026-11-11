import os
import re
import glob

# Paths where Steam is commonly installed on Linux
STEAM_PATHS = [
    os.path.expanduser("~/.local/share/Steam"),
    os.path.expanduser("~/.steam/steam"),
]

# SD card and external drive mounts. /run/media/<user>/<label>: the user is
# deck on SteamOS and the login name on Bazzite/CachyOS. /run/media/<label>
# is where older SteamOS mounted the card (mmcblk0p1).
SD_CARD_PATTERNS = [
    "/run/media/*/*/SteamLibrary",
    "/run/media/*/*",
    "/run/media/*/SteamLibrary",
    "/run/media/*",
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
    },
    "t4mp":  {
        "name": "Call of Duty: World at War - Multiplayer",
        "order": 2,
        "appid": "10090",
        "exe": "CoDWaWmp.exe",
        "protocol": "plutonium://play/t4mp",
    },
    "t5sp":  {
        "name": "Call of Duty: Black Ops",
        "order": 4,
        "appid": "42700",
        "exe": "BlackOps.exe",
        "protocol": "plutonium://play/t5sp",
    },
    "t5mp":  {
        "name": "Call of Duty: Black Ops - Multiplayer",
        "order": 4,
        "appid": "42710",
        "exe": "BlackOpsMP.exe",
        "protocol": "plutonium://play/t5mp",
    },
    "t6mp":  {
        "name": "Call of Duty: Black Ops II - Multiplayer",
        "order": 6,
        "appid": "202990",
        "exe": "t6mp.exe",
        "protocol": "plutonium://play/t6mp",
    },
    "t6zm":  {
        "name": "Call of Duty: Black Ops II - Zombies",
        "order": 6,
        "appid": "212910",
        "exe": "t6zm.exe",
        "protocol": "plutonium://play/t6zm",
    },
    "t6sp":  {
        "name": "Call of Duty: Black Ops II - Singleplayer",
        "order": 6,
        "appid": "202970",
        "exe": "t6sp.exe",
        "protocol": "t6sp_mod",
    },
    "t7": {
        "name": "Call of Duty: Black Ops III",
        "order": 7,
        "appid": "311210",
        "exe": "BlackOps3.exe",
        "protocol": "cleanops",
    },
    # ── DISABLED 2026-09: AlterWare discontinuing Dec 2026 ──
    # "t7x": {
    #     "name": "Call of Duty: Black Ops III - T7x",
    #     "order": 7,
    #     "appid": "311210",
    #     "exe": "BlackOps3.exe",
    #     "protocol": "t7x",
    # },
    "iw6mp": {
        "name": "Call of Duty: Ghosts - Multiplayer",
        "order": 8,
        "appid": "209170",
        "exe": "iw6mp64_ship.exe",
        "protocol": "alterware",
    },
    "iw6sp": {
        "name": "Call of Duty: Ghosts - Singleplayer",
        "order": 8,
        "appid": "209160",
        "exe": "iw6sp64_ship.exe",
        "exe_alt": "iw6mp64_ship.exe",
        "protocol": "alterware",
    },
    "s1mp": {
        "name": "Call of Duty: Advanced Warfare - Multiplayer",
        "order": 9,
        "appid": "209660",
        "exe": "s1_mp64_ship.exe",
        "protocol": "alterware",
    },
    "s1sp": {
        "name": "Call of Duty: Advanced Warfare - Singleplayer",
        "order": 9,
        "appid": "209650",
        "exe": "s1_sp64_ship.exe",
        "protocol": "alterware",
    },
    "iw5mp": {
        "name": "Call of Duty: Modern Warfare 3 (2011) - Multiplayer",
        "order": 5,
        "appid": "42690",
        "exe": "iw5mp.exe",
        "protocol": "plutonium://play/iw5mp",
    },
    "iw5sp": {
        "name": "Call of Duty: Modern Warfare 3 (2011) - Singleplayer",
        "order": 5,
        "appid": "42680",
        "exe": "iw5sp.exe",
        "protocol": "steam",
    },
    "iw5mp_ds": {
        "name": "Call of Duty: Modern Warfare 3 - Dedicated Server",
        "order": 5,
        "appid": "42750",
        "exe": "iw5mp_server.exe",
        "protocol": "plutonium://play/iw5mp",
    },
    "iw4mp": {
        "name": "Call of Duty: Modern Warfare 2 (2009) - Multiplayer",
        "order": 3,
        "appid": "10190",
        "exe": "iw4mp.exe",
        "protocol": "iw4x",
    },
    "iw4sp": {
        "name": "Call of Duty: Modern Warfare 2 (2009) - Singleplayer",
        "order": 3,
        "appid": "10180",
        "exe": "iw4sp.exe",
        "protocol": "steam",
    },
    "cod4mp": {
        "name": "Call of Duty 4: Modern Warfare (2007) - Multiplayer",
        "order": 1,
        "appid": "7940",
        "exe": "iw3mp.exe",
        "protocol": "cod4r",
    },
    "cod4sp": {
        "name": "Call of Duty 4: Modern Warfare (2007) - Singleplayer",
        "order": 1,
        "appid": "7940",
        "exe": "iw3sp.exe",
        "protocol": "iw3sp",
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

            # Parse install dir name and state flags from acf
            install_name = None
            state_flags  = None
            with open(acf, "r", errors="replace") as f:
                for line in f:
                    m = re.search(r'"installdir"\s+"([^"]+)"', line)
                    if m:
                        install_name = m.group(1)
                    m = re.search(r'"StateFlags"\s+"(\d+)"', line)
                    if m:
                        state_flags = m.group(1)
                    if install_name and state_flags:
                        break

            if not install_name:
                continue

            # Bit 4 = fully installed. 6 is installed with an update waiting;
            # a first download that hasn't finished doesn't have the bit.
            if not state_flags or not int(state_flags) & 4:
                continue

            install_dir = os.path.join(steamapps_dir, "common", install_name)
            exe_path    = os.path.join(install_dir, exe)

            if not os.path.exists(exe_path) and meta.get("exe_alt"):
                exe_path = os.path.join(install_dir, meta["exe_alt"])

            if os.path.exists(install_dir) and os.path.exists(exe_path):
                installed[key] = {
                    **meta,
                    "install_dir": install_dir,
                    "exe_path":    exe_path,
                    "exe_size":    get_exe_size(exe_path),
                }
                break

    return installed


# --- Own installs
# A game counts as found when its stock exe is in a folder. Folder names and
# fastfiles don't decide it: users name folders anything, and a copy can lack
# a mode (a BO2 copy with Campaign and Zombies has no t6mp.exe or mp_*.ff).

# Default scan locations -- case-sensitive on Linux.
OWN_SCAN_PATHS = [
    os.path.expanduser("~/Games"),
    os.path.expanduser("~/games"),
    # /run/media/<user>/<label> (SteamOS user is deck; Bazzite/CachyOS use the
    # login name), plus /run/media/<label> as older SteamOS mounted mmcblk0p1
    "/run/media/*/*/Games",
    "/run/media/*/*/games",
    "/run/media/*/Games",
    "/run/media/*/games",
]

# Lowercase stock exe -> game keys. The MW3 dedicated server has its own Steam
# app and is not an own-install game.
_OWN_EXES = {}
for _k, _m in GAMES.items():
    if _k == "iw5mp_ds":
        continue
    for _e in (_m["exe"], _m.get("exe_alt")):
        if _e:
            _OWN_EXES.setdefault(_e.lower(), []).append(_k)


def _walk_games(root):
    """Walk every folder under root. os.walk skips symlinked folders, so a link loop can't trap it."""
    skip = {"__pycache__", "DeckOps-T7X"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in skip]
        yield dirpath, dirnames, filenames


def find_own_installed(extra_paths=None, on_progress=None):
    """
    Scan ~/Games, SD card Games folders and extra_paths (the Choose Folder
    picks) for stock game exes. Exe names match in any case. The folder that
    holds the exe becomes install_dir.

    Returns the same dict as find_installed_games() plus "source": "own".
    """
    prog = on_progress or (lambda *a: None)

    scan_dirs = []
    seen = set()
    for pattern in OWN_SCAN_PATHS:
        for path in glob.glob(pattern):
            path = os.path.normpath(path)
            # realpath: SteamOS also links /run/media/<label> to /run/media/deck/<label>
            real = os.path.realpath(path)
            if real not in seen and os.path.isdir(path):
                seen.add(real)
                scan_dirs.append(path)
    if extra_paths:
        for path in extra_paths:
            path = os.path.normpath(path)
            real = os.path.realpath(path)
            if real not in seen and os.path.isdir(path):
                seen.add(real)
                scan_dirs.append(path)

    if not scan_dirs:
        prog("No game folders found to scan.")
        return {}

    found = {}
    for scan_dir in scan_dirs:
        prog(f"Scanning {scan_dir}...")
        for dirpath, dirnames, filenames in _walk_games(scan_dir):
            exes = {f.lower(): f for f in filenames if f.lower() in _OWN_EXES}
            if not exes:
                continue
            # Game root: the rest of this game's tree has no other games
            dirnames.clear()
            for low, fname in exes.items():
                for key in _OWN_EXES[low]:
                    if key in found:
                        continue
                    meta = GAMES[key]
                    # Ghosts SP falls back to the MP exe; use its own when present
                    exe_path = os.path.join(dirpath, exes.get(meta["exe"].lower(), fname))
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


def find_all_games(steam_root=None):
    """Detect all installed games from both Steam and non-Steam sources.

    Steam games take priority when a key exists in both.
    Each entry is tagged with source="steam" or source="own".
    """
    if steam_root is None:
        steam_root = find_steam_root()
    libs = parse_library_folders(steam_root)
    steam = find_installed_games(libs, steam_root)
    own = find_own_installed()
    merged = {}
    for k, v in own.items():
        merged[k] = v
    for k, v in steam.items():
        merged[k] = {**v, "source": "steam"}
    return merged


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

    print(f"\nOwn games scan:")
    own = find_own_installed(on_progress=print)
    for key, game in own.items():
        print(f"  [{key}] {game['name']}")
        print(f"        {game['install_dir']}")
