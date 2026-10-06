#!/bin/bash
# Steam launch option prefix for DeckOps-managed games:
#   bash "<install dir>/prelaunch.sh" <game key> <original command...>
# Updates the game's mod client silently, then starts the game exactly as
# Steam would have. The game always starts, even if the update fails,
# times out or there is no network.

DIR="$(dirname "$(readlink -f "$0")")"

# Steam's launch environment (overlay preload, runtime libraries) is meant
# for the game, not for the host Python, so it is dropped for the check only.
timeout 120 env -u LD_PRELOAD -u LD_LIBRARY_PATH -u PYTHONHOME -u PYTHONPATH \
    "$DIR/.venv/bin/python3" "$DIR/src/prelaunch.py" "$@" >/dev/null 2>&1

shift
exec "$@"
