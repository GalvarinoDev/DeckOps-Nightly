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

# ── step 3b: write build info ─────────────────────────────────────────────
# Short commit hash + date, read by the Settings screen's About section.
# Uses the downloaded archive's HEAD, not a local git repo.
BUILD_DATE=$(date '+%b %d, %Y')
BUILD_HASH="nightly"
if command -v git &>/dev/null && [ -d "$INSTALL_DIR/.git" ]; then
    BUILD_HASH=$(cd "$INSTALL_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "nightly")
fi
echo "$BUILD_HASH ($BUILD_DATE)" > "$INSTALL_DIR/BUILD"
success "Build info written: $BUILD_HASH ($BUILD_DATE)"

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

if ! "$VENV_PYTHON" -c "import evdev" &>/dev/null 2>&1; then
    info "Installing evdev-binary..."
    "$VENV_DIR/bin/pip" install --quiet evdev-binary \
        || warn "Failed to install evdev-binary — gamepad input in Plutonium Launcher will not work."
    success "evdev-binary installed."
else
    success "evdev already installed."
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

# ── step 7: sweep stale plut_lan.sh sidecars ─────────────────────────────────
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

# ── step 8: done ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete! Welcome to DeckOps.${CLEAR}"
echo ""
echo -e "  ${CYAN}Please open DeckOps from your desktop.${CLEAR}"
echo -e "  ${CYAN}This window will close automatically.${CLEAR}"
echo ""

for i in 10 9 8 7 6 5 4 3 2 1; do
    printf "\r  Closing in %d seconds...  " "$i"
    sleep 1
done
echo ""
exit 0
