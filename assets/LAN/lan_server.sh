#!/bin/bash
# DeckOps offline launch for Plutonium games, run by each game's offline script
# (DeckOps_Offline.exe through launcher_offline.sh). Always on the host.
# The game runs from DeckOps' offline Plutonium copy in its own prefix, inside Steam
# Linux Runtime like Steam's own launches: straight on the host, BO2 stalls in Game Mode
# until its console window is switched to (Deck, 2026-10-08).
# BO2 MP and MW3 MP also host a hidden local dedicated server and join it: plain -lan
# play can't create a private match without a Plutonium account.
# Usage: lan_server.sh <mode> <game dir, game prefix> +name "<player>" [<port> <game dir, server prefix> <server args...>]
# Extra game args: CLIENT_ARGS (word-split, no spaces inside an arg).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
J="$PROJECT_ROOT/deckops.json"
read -r GE SR < <(python3 -c "import json;d=json.load(open('$J'));print(d.get('ge_proton_version',''),d.get('steam_root',''))" 2>/dev/null)
PR="$SR/compatibilitytools.d/$GE/proton"
# Game and server need different prefixes: the game's waitforexitandrun waits for
# every wineserver on its prefix. The server uses the Offline launcher's prefix.
GP="$HOME/.local/share/deckops/lan_prefix"
SP="$HOME/.local/share/deckops/launcher_prefix"
MODE=$1 GAME=$2 NAME=$4; shift 4
PORT=$1 SGAME=$2; [ $# -ge 2 ] && shift 2
SV="$HOME/.local/share/deckops/lan/$MODE/server"
CL="$HOME/.local/share/deckops/lan/$MODE/client"
UNIT="deckops-lan-$MODE"

mkdir -p "$PROJECT_ROOT/logs"
exec >"$PROJECT_ROOT/logs/lan_$MODE.log" 2>&1
echo "$(date +%T) start $MODE $GAME${PORT:+, server on port $PORT: $*}"
[ -x "$PR" ] || { echo "Proton not found: $PR"; exit 1; }
# Relink the offline copies so mods added and Plutonium files updated since the install
# show up, and get the Steam Linux Runtime and the library mounts back.
# Steam's launch environment is meant for the game, not the host Python (as in prelaunch.sh).
IFS=$'\t' read -r SLR MOUNTS < <(timeout 60 env -u LD_PRELOAD -u LD_LIBRARY_PATH -u PYTHONHOME -u PYTHONPATH \
  "$PROJECT_ROOT/.venv/bin/python3" "$PROJECT_ROOT/src/prelaunch.py" lan "$MODE" 2>/dev/null)
echo "runtime: ${SLR:-none, running on the host}  mounts: ${MOUNTS:-none}"
[ -d "$CL" ] && { [ -z "$PORT" ] || [ -d "$SV" ]; } || { echo "Offline folders missing, add Offline Mode again in DeckOps"; exit 1; }

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$SR"
# Steam's Stop button sends TERM: take the server down with the game
trap 'systemctl --user stop "$UNIT" 2>/dev/null' EXIT

# ---
# Server

CONNECT=()
if [ -n "$PORT" ]; then
  if ! ss -uln | grep -q ":$PORT "; then
    # A unit left over from an interrupted run blocks systemd-run from reusing the name
    systemctl --user stop "$UNIT" 2>/dev/null; systemctl --user reset-failed "$UNIT" 2>/dev/null
    # systemd-run with the display passed in: a headless server stalls under Proton, and in Game Mode
    # this keeps its window out of the Steam launch so gamescope never focuses it.
    # Game Mode's systemd user environment has no DISPLAY, so it is passed in.
    systemd-run --user --collect --unit="$UNIT" -p TimeoutStopSec=10 -E DISPLAY="${DISPLAY:-:0}" \
      -E WAYLAND_DISPLAY="$WAYLAND_DISPLAY" -E GAMESCOPE_WAYLAND_DISPLAY="$GAMESCOPE_WAYLAND_DISPLAY" \
      -E XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
      -E STEAM_COMPAT_DATA_PATH="$SP" -E STEAM_COMPAT_CLIENT_INSTALL_PATH="$SR" \
      --working-directory="$SV" \
      "$PR" run "$SV/bin/plutonium-bootstrapper-win32.exe" "$MODE" "$SGAME" -lan -dedicated +set net_port "$PORT" "$@" \
      || { echo "server failed to start"; exit 1; }
    for i in $(seq 180); do ss -uln | grep -q ":$PORT " && break; sleep 1; done
    echo "$(date +%T) server listening after ${i}s"
    sleep 5
  fi
  CONNECT=(+set deckops_lan_port "$PORT" +connect "127.0.0.1:$PORT")
fi

# ---
# Game

cd "$CL" || exit 1
export STEAM_COMPAT_DATA_PATH="$GP" STEAM_COMPAT_MOUNTS="$MOUNTS"
# Steam's own launch: the runtime's entry point, then proton waitforexitandrun
if [ -n "$SLR" ]; then RUN=("$SLR/_v2-entry-point" --verb=waitforexitandrun -- "$PR" waitforexitandrun); else RUN=("$PR" run); fi
# Plutonium's own launcher passes a fresh random -token even in LAN mode
TOKEN=$(od -An -N8 -tx1 /dev/urandom | tr -d ' \n')
# Returns when the game exits; staying alive here also keeps the Steam session open
"${RUN[@]}" "$CL/bin/plutonium-bootstrapper-win32.exe" "$MODE" "$GAME" -token "$TOKEN" -lan +name "$NAME" \
  $CLIENT_ARGS "${CONNECT[@]}"
echo "$(date +%T) game closed${PORT:+, stopping server}"
