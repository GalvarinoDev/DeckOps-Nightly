# ── INSERT THIS BLOCK AFTER LINE 592 IN deckops_uninstall.sh ──────────────────
# (After the "echo """ following the Deck configurator PYEOF block)

info "Clearing DeckOps launch options from localconfig.vdf..."

# Mirrors: wrapper.py clear_launch_options()
# Clears LaunchOptions for ALL managed Steam appids so no stale launch
# commands survive uninstall. Covers AlterWare bash substitutions,
# CleanOps DLL injection, LCD Plutonium Heroic launch, and any future
# launch options DeckOps writes.
python3 - << 'PYEOF'
import os, re

MANAGED_STEAM_APPIDS = [
    "7940", "10090", "10180", "10190", "42680", "42690", "42750",
    "42700", "42710", "202970", "202990", "212910", "311210",
    "209160", "209170", "209650", "209660",
]

steam_dir = os.path.expanduser("~/.local/share/Steam")
userdata  = os.path.join(steam_dir, "userdata")

if not os.path.isdir(userdata):
    print("  No Steam userdata found — skipping.")
    exit(0)

def find_block_end(text, start):
    """Brace-depth parser that skips braces inside quoted strings."""
    depth = 0; i = start; in_quote = False
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            in_quote = not in_quote
        elif not in_quote:
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: return i
        i += 1
    return -1

cleared = 0
for uid in os.listdir(userdata):
    if not uid.isdigit() or int(uid) < 10000:
        continue
    vdf_path = os.path.join(userdata, uid, "config", "localconfig.vdf")
    if not os.path.exists(vdf_path):
        continue

    with open(vdf_path, "r", errors="replace") as f:
        content = f.read()

    modified = False
    for appid in MANAGED_STEAM_APPIDS:
        key_pattern = re.compile(
            r'"' + re.escape(appid) + r'"\s*\{',
            re.IGNORECASE
        )
        key_match = key_pattern.search(content)
        if not key_match:
            continue

        app_open  = key_match.end() - 1
        app_close = find_block_end(content, app_open)
        if app_close == -1:
            continue

        app_inner = content[app_open + 1:app_close]

        # Only touch LaunchOptions in the flat block, not inside sub-blocks.
        subblock_match = re.search(r'"[^"]+"\s*\{', app_inner)
        flat_section = app_inner[:subblock_match.start()] if subblock_match else app_inner

        launch_pattern = re.compile(
            r'("LaunchOptions"\s*")([^"]*?)(")',
            re.IGNORECASE
        )
        launch_match = launch_pattern.search(flat_section)
        if not launch_match or not launch_match.group(2).strip():
            continue

        # Clear the value to empty string
        new_flat = launch_pattern.sub(r'\g<1>\g<3>', flat_section, count=1)
        if subblock_match:
            new_app_inner = new_flat + app_inner[subblock_match.start():]
        else:
            new_app_inner = new_flat

        content = (
            content[:app_open + 1] +
            new_app_inner +
            content[app_close:]
        )
        modified = True
        cleared += 1
        print(f"  uid {uid}: cleared LaunchOptions for appid {appid}")

    if modified:
        bak = vdf_path + ".deckops_uninstall.bak"
        if not os.path.exists(bak):
            try:
                import shutil
                shutil.copy2(vdf_path, bak)
            except Exception:
                pass
        with open(vdf_path, "w", errors="replace") as f:
            f.write(content)

if cleared == 0:
    print("  No DeckOps launch options found — nothing to clear.")
else:
    print(f"  Cleared {cleared} launch option(s) total.")
PYEOF

echo ""
