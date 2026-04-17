#!/bin/bash
# DeckOps Installer

# ── colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
CLEAR='\033[0m'

info()    { printf "${CYAN}${BOLD}[DeckOps]${CLEAR} %s\n" "$1"; }
success() { printf "${GREEN}${BOLD}[  OK  ]${CLEAR} %s\n" "$1"; }
warn()    { printf "${YELLOW}${BOLD}[ WARN ]${CLEAR} %s\n" "$1"; }
die()     {
    printf "${RED}${BOLD}[ERROR ]${CLEAR} %s\n" "$1"
    echo ""
    read -r -p "  Press Enter to close..."
    exit 1
}

# ── config ────────────────────────────────────────────────────────────────────
GITHUB_USER="GalvarinoDev"
GITHUB_REPO="DeckOps-Nightly"
INSTALL_DIR="$HOME/DeckOps-Nightly"
VENV_DIR="$INSTALL_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python3"
ENTRY_POINT="$INSTALL_DIR/src/main.py"
ICON_PATH="$INSTALL_DIR/assets/images/icon.png"
MUSIC_DIR="$INSTALL_DIR/assets/music"
DESKTOP_FILE="$HOME/.local/share/applications/deckops-nightly.desktop"
DESKTOP_SHORTCUT="$HOME/Desktop/DeckOps-Nightly.desktop"

MUSIC_URL="https://archive.org/download/adrenaline-klickaud/Adrenaline_KLICKAUD.mp3"
MUSIC_FILE="background.mp3"

# ── header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}  ██████╗ ███████╗ ██████╗██╗  ██╗ ██████╗ ██████╗ ███████╗${CLEAR}"
echo -e "${BOLD}  ██╔══██╗██╔════╝██╔════╝██║ ██╔╝██╔═══██╗██╔══██╗██╔════╝${CLEAR}"
echo -e "${BOLD}  ██║  ██║█████╗  ██║     █████╔╝ ██║   ██║██████╔╝███████╗${CLEAR}"
echo -e "${BOLD}  ██║  ██║██╔══╝  ██║     ██╔═██╗ ██║   ██║██╔═══╝ ╚════██║${CLEAR}"
echo -e "${BOLD}  ██████╔╝███████╗╚██████╗██║  ██╗╚██████╔╝██║     ███████║${CLEAR}"
echo -e "${BOLD}  ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚══════╝${CLEAR}"
echo ""
echo -e "  ${YELLOW}DeckOps Nightly — Installer${CLEAR}"
echo ""

# ── step 1: check core dependencies ──────────────────────────────────────────
info "Checking dependencies..."

command -v python3 &>/dev/null || die "Python 3 is not installed."
command -v curl    &>/dev/null || die "curl is not installed."
command -v unzip   &>/dev/null || die "unzip is not installed."

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
success "Python $PYTHON_VER found."

# ── step 2: download latest release ──────────────────────────────────────────
info "Downloading DeckOps..."

TMPZIP="$(mktemp /tmp/deckops_XXXXXX.zip)"
curl -L --progress-bar "https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/heads/main.zip" -o "$TMPZIP" \
    || die "Download failed. Check your internet connection."
success "Download complete."

# ── step 3: extract ───────────────────────────────────────────────────────────
info "Installing to $INSTALL_DIR..."

TMPDIR_EXTRACT="$(mktemp -d /tmp/deckops_extract_XXXXXX)"
unzip -qq "$TMPZIP" -d "$TMPDIR_EXTRACT" || die "Failed to extract archive."
rm "$TMPZIP"

EXTRACTED=$(find "$TMPDIR_EXTRACT" -maxdepth 1 -mindepth 1 -type d | head -1)
[ -z "$EXTRACTED" ] && EXTRACTED="$TMPDIR_EXTRACT"

mkdir -p "$INSTALL_DIR"
cp -r "$EXTRACTED"/. "$INSTALL_DIR"/
rm -rf "$TMPDIR_EXTRACT"

chmod +x "$ENTRY_POINT" 2>/dev/null || true
success "DeckOps installed to $INSTALL_DIR"

# ── step 4: download background music ────────────────────────────────────────
info "Downloading background music..."

mkdir -p "$MUSIC_DIR"

if [ ! -f "$MUSIC_DIR/$MUSIC_FILE" ]; then
    curl -sSL "$MUSIC_URL" -o "$MUSIC_DIR/$MUSIC_FILE" \
        && success "Background music downloaded." \
        || warn "Could not download background music — app will run without it."
else
    success "Background music already present."
fi

# ── step 5: set up Python venv + install packages ────────────────────────────
info "Setting up Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" || die "Failed to create Python virtual environment."
    success "Virtual environment created."
else
    success "Virtual environment already exists."
fi

if ! "$VENV_PYTHON" -c "from PyQt5.QtWidgets import QApplication" &>/dev/null 2>&1; then
    info "Installing PyQt5 (this will take about 30 seconds)..."
    "$VENV_DIR/bin/pip" install --quiet PyQt5 \
        || die "Failed to install PyQt5. Check your internet connection and try again."
    success "PyQt5 installed."
else
    PYQT5_VER=$("$VENV_PYTHON" -c "from PyQt5.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)")
    success "PyQt5 (Qt $PYQT5_VER) already installed."
fi

if ! "$VENV_PYTHON" -c "import pygame" &>/dev/null 2>&1; then
    info "Installing pygame..."
    "$VENV_DIR/bin/pip" install --quiet pygame \
        || warn "Failed to install pygame — background music will not play."
    success "pygame installed."
else
    success "pygame already installed."
fi

if ! "$VENV_PYTHON" -c "import vdf" &>/dev/null 2>&1; then
    info "Installing vdf..."
    "$VENV_DIR/bin/pip" install --quiet vdf \
        || warn "Failed to install vdf — non-Steam shortcuts may not be created."
    success "vdf installed."
else
    success "vdf already installed."
fi

# ── step 6: .desktop entry ────────────────────────────────────────────────────
info "Creating application shortcut..."

mkdir -p "$(dirname "$DESKTOP_FILE")"

cat > "$DESKTOP_FILE" << DEOF
[Desktop Entry]
Name=DeckOps Nightly
Comment=DeckOps Nightly — Experimental build
Exec=$VENV_PYTHON $ENTRY_POINT
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Game;
StartupNotify=true
DEOF

chmod +x "$DESKTOP_FILE"
success "App launcher shortcut created."

if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
    chmod +x "$DESKTOP_SHORTCUT"
    success "Desktop shortcut created."
fi

# ── step 7: add to Steam ──────────────────────────────────────────────────────
info "Adding DeckOps to Steam library..."

IN_GAME_MODE=0
pgrep -x "gamescope" > /dev/null 2>&1 && IN_GAME_MODE=1

STEAM_IS_RUNNING=0
pgrep -f "ubuntu12_32/steam" > /dev/null 2>&1 && STEAM_IS_RUNNING=1

add_to_steam() {
    python3 - << PYEOF
import binascii
import os
import struct
import time

def find_all_shortcuts_vdf():
    """Find shortcuts.vdf for ALL Steam user accounts, not just the first."""
    steam_paths = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"),
        os.path.expanduser("~/.steam/root"),
    ]
    results = []
    seen = set()
    for steam in steam_paths:
        userdata = os.path.join(steam, "userdata")
        if not os.path.exists(userdata):
            continue
        for uid in os.listdir(userdata):
            if not uid.isdigit() or int(uid) < 10000:
                continue
            cfg_dir = os.path.join(userdata, uid, "config")
            real = os.path.realpath(cfg_dir)
            if real in seen:
                continue
            seen.add(real)
            vdf = os.path.join(cfg_dir, "shortcuts.vdf")
            results.append(vdf)
    return results

def calc_shortcut_appid(exe_path, name):
    """Must match shortcut.py _calc_shortcut_appid exactly."""
    key = (exe_path + name).encode("utf-8")
    crc = binascii.crc32(key) & 0xFFFFFFFF
    return (crc | 0x80000000) & 0xFFFFFFFF

def to_signed32(n):
    return n if n <= 2147483647 else n - 2**32

def string_field(key, val):
    return b'\x01' + key.encode() + b'\x00' + val.encode() + b'\x00'

def int_field(key, val):
    return b'\x02' + key.encode() + b'\x00' + struct.pack('<i', val)

def make_entry(index, appid, name, exe, icon, start_dir):
    e  = b'\x00' + str(index).encode() + b'\x00'
    e += int_field('appid', to_signed32(appid))
    e += string_field('AppName', name)
    e += string_field('Exe', exe)
    e += string_field('StartDir', start_dir)
    e += string_field('icon', icon)
    e += string_field('ShortcutPath', '')
    e += string_field('LaunchOptions', '')
    e += int_field('IsHidden', 0)
    e += int_field('AllowDesktopConfig', 1)
    e += int_field('AllowOverlay', 1)
    e += int_field('OpenVR', 0)
    e += int_field('Devkit', 0)
    e += string_field('DevkitGameID', '')
    e += int_field('DevkitOverrideAppID', 0)
    e += int_field('LastPlayTime', 0)
    e += string_field('FlatpakAppID', '')
    e += b'\x00tags\x00'
    e += string_field('0', 'DeckOps')
    e += b'\x08'
    e += b'\x08'
    return e

def get_next_index(raw_data):
    """
    Find the next available shortcut index from raw shortcut entry data.
    Ported from shortcut.py _get_next_index — must stay in sync.

    Entry headers are: 0x00 <index_str> 0x00 immediately followed by 0x02
    (the appid int field marker). The 0x02 lookahead distinguishes real
    entry headers from other 0x00...0x00 sequences in binary VDF.
    """
    if not raw_data:
        return 0
    indices = []
    i = 0
    while i < len(raw_data) - 2:
        if raw_data[i] == 0x00:
            end = raw_data.find(b'\x00', i + 1)
            if end != -1 and end > i + 1:
                if end + 1 < len(raw_data) and raw_data[end + 1] == 0x02:
                    try:
                        idx_str = raw_data[i + 1:end].decode('utf-8')
                        if idx_str.isdigit():
                            indices.append(int(idx_str))
                    except (UnicodeDecodeError, ValueError):
                        pass
                i = end + 1
            else:
                i += 1
        else:
            i += 1
    return max(indices, default=-1) + 1

def backup_file(path):
    """Write a .bak copy before modifying a file."""
    import shutil
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass

vdf_paths = find_all_shortcuts_vdf()
if not vdf_paths:
    print("WARN: No Steam user accounts found — add DeckOps to Steam manually.")
    exit(0)

home      = os.path.expanduser('~')
name      = "DeckOps Nightly"
exe       = f'"{home}/DeckOps-Nightly/.venv/bin/python3"'
icon      = f"{home}/DeckOps-Nightly/assets/images/icon.png"
start_dir = f'"{home}/DeckOps-Nightly"'

appid = calc_shortcut_appid(exe, name)

wrote = 0
for vdf in vdf_paths:
    if os.path.exists(vdf):
        data = open(vdf, 'rb').read()
        if b'DeckOps Nightly' in data:
            print(f"Already in Steam shortcuts: {vdf}")
            continue
        header = b'\x00shortcuts\x00'
        raw = data
        if raw.startswith(header):
            raw = raw[len(header):]
        if raw.endswith(b'\x08\x08'):
            raw = raw[:-2]
        elif raw.endswith(b'\x08'):
            raw = raw[:-1]
        index = get_next_index(raw)
        existing = data[:-2] if data.endswith(b'\x08\x08') else data
    else:
        os.makedirs(os.path.dirname(vdf), exist_ok=True)
        existing = b'\x00shortcuts\x00'
        index = 0

    backup_file(vdf)
    updated = existing + make_entry(index, appid, name, exe, icon, start_dir) + b'\x08\x08'
    open(vdf, 'wb').write(updated)
    print(f"Added as entry {index} in {vdf}")
    wrote += 1

if wrote == 0:
    print("Already in all Steam shortcut files.")
else:
    print(f"Wrote to {wrote} shortcut file(s).")
PYEOF
}

if [ "$STEAM_IS_RUNNING" -eq 1 ] && [ "$IN_GAME_MODE" -eq 1 ]; then
    warn "Steam is running in Game Mode — skipping shortcut write."
    warn "DeckOps will appear in your library after you run it once from Desktop Mode,"
    warn "or you can re-run this installer with Steam closed."
elif [ "$STEAM_IS_RUNNING" -eq 1 ] && [ "$IN_GAME_MODE" -eq 0 ]; then
    echo ""
    warn "Steam is currently running. It needs to be closed to safely add DeckOps."
    read -r -p "  Is Steam closed? Press Y to add, N to skip: " answer
    case "$answer" in
        [yY]*)
            add_to_steam
            success "Steam shortcut written. Launch Steam and DeckOps will be in your library."
            ;;
        *)
            warn "Skipped. To add manually: Steam → Add a Non-Steam Game → $ENTRY_POINT"
            ;;
    esac
else
    add_to_steam
    success "Steam shortcut written. Launch Steam and DeckOps will be in your library."
fi

# ── step 8: sweep stale plut_lan.sh sidecars ─────────────────────────────────
# Pre-Pass-1 installs wrote <gametag>plut_lan.sh into game install dirs at
# install time (OLED offline-mode plumbing). Pass 1 stopped creating them but
# left existing files on disk. Sweep all known Steam libraries (internal +
# libraryfolders.vdf entries + SD card mounts) and remove them.
info "Sweeping stale plut_lan.sh sidecars..."

STEAM_ROOT_FOR_SWEEP=""
for r in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root"; do
    if [ -d "$r/steamapps" ]; then
        STEAM_ROOT_FOR_SWEEP="$r"
        break
    fi
done

LAN_SWEEP_DIRS=()
[ -n "$STEAM_ROOT_FOR_SWEEP" ] && LAN_SWEEP_DIRS+=("$STEAM_ROOT_FOR_SWEEP/steamapps/common")

LF_VDF_SWEEP="$STEAM_ROOT_FOR_SWEEP/steamapps/libraryfolders.vdf"
if [ -f "$LF_VDF_SWEEP" ]; then
    while IFS= read -r libpath; do
        [ -d "$libpath/steamapps/common" ] && LAN_SWEEP_DIRS+=("$libpath/steamapps/common")
        [ -d "$libpath/SteamLibrary/steamapps/common" ] && LAN_SWEEP_DIRS+=("$libpath/SteamLibrary/steamapps/common")
    done < <(sed -n 's/.*"path"[[:space:]]*"\([^"]*\)".*/\1/p' "$LF_VDF_SWEEP")
fi

for mount in /run/media/deck/*/steamapps/common /run/media/deck/*/SteamLibrary/steamapps/common; do
    [ -d "$mount" ] && LAN_SWEEP_DIRS+=("$mount")
done

lan_removed=0
for common_dir in "${LAN_SWEEP_DIRS[@]}"; do
    while IFS= read -r -d '' sidecar; do
        if rm -f "$sidecar" 2>/dev/null; then
            info "  Removed: $sidecar"
            lan_removed=$((lan_removed + 1))
        fi
    done < <(find "$common_dir" -maxdepth 2 -name "*plut_lan.sh" -print0 2>/dev/null)
done

if [ "$lan_removed" -gt 0 ]; then
    success "Removed $lan_removed stale plut_lan.sh sidecar(s)."
else
    success "No stale plut_lan.sh sidecars found."
fi

# ── step 9: launch DeckOps ────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete! Welcome to DeckOps.${CLEAR}"
echo ""
echo -e "  ${CYAN}Launching DeckOps now...${CLEAR}"
echo ""

nohup "$VENV_PYTHON" "$ENTRY_POINT" > /dev/null 2>&1 &
disown
exit 0
