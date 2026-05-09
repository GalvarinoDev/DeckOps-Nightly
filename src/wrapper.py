import os
import json
import re
import stat
import shutil
import subprocess

from identity import LEDGER_PATH
from log import get_logger

_log = get_logger(__name__)

# ── VDF edit ledger ──────────────────────────────────────────────────────────
# Records every VDF edit DeckOps makes so the uninstaller can reverse them
# precisely instead of regex-sweeping entire files.


def _read_ledger() -> dict:
    """Read the VDF edit ledger, returning empty dict if missing/corrupt."""
    if not os.path.exists(LEDGER_PATH):
        return {}
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        _log.debug("VDF ledger read failed, starting fresh", exc_info=True)
        return {}


def _write_ledger(data: dict):
    """Write the VDF edit ledger. Failures are logged but non-fatal."""
    try:
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        with open(LEDGER_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        _log.debug("VDF ledger write failed", exc_info=True)


def _record_localconfig(uid: str, appid: str, key: str, value: str):
    """Record a localconfig.vdf edit in the ledger."""
    ledger = _read_ledger()
    lc = ledger.setdefault("localconfig", {})
    uid_block = lc.setdefault(uid, {})
    app_block = uid_block.setdefault(appid, {})
    app_block[key] = value
    _write_ledger(ledger)


def _record_config_vdf(appid: str, key: str, value: str):
    """Record a config.vdf edit in the ledger."""
    ledger = _read_ledger()
    cv = ledger.setdefault("config_vdf", {})
    section = cv.setdefault(key, {})
    section[appid] = value
    _write_ledger(ledger)


def _remove_config_vdf(appid: str, key: str):
    """Remove a config.vdf entry from the ledger (for clear operations)."""
    ledger = _read_ledger()
    cv = ledger.get("config_vdf", {})
    section = cv.get(key, {})
    section.pop(appid, None)
    if not section:
        cv.pop(key, None)
    _write_ledger(ledger)


def _record_configset(configset_filename: str, key: str, template_name: str):
    """Record a configset VDF edit in the ledger."""
    ledger = _read_ledger()
    cs = ledger.setdefault("configsets", {})
    file_block = cs.setdefault(configset_filename, {})
    file_block[key] = template_name
    _write_ledger(ledger)



def _backup_file(path: str):
    """Write a .bak copy before modifying a Steam config file."""
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            _log.debug("VDF backup failed for config file", exc_info=True)


def _find_block_end(text, start):
    """
    Brace-depth parser that skips braces inside quoted strings.

    WARNING: Must skip braces inside quoted strings - VDF values like
    bash substitutions (e.g. ${@/iw3sp.exe/iw3sp_mod.exe}) contain
    { and } characters that must NOT be counted as block delimiters.
    Failure to do this will corrupt localconfig.vdf.
    """
    depth = 0
    i = start
    in_quote = False
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i - 1] != '\\'):
            in_quote = not in_quote
        elif not in_quote:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _validate_vdf(path: str) -> bool:
    """
    Read a VDF file back after writing and verify brace balance.

    Walks the entire file using the same quote-aware brace parser that
    _find_block_end uses. A valid VDF file has every { matched by a }.
    Returns True if balanced, False if corrupt.

    On failure, automatically restores from .bak if available and logs
    the error. This catches corruption before Steam ever sees the file.
    """
    try:
        with open(path, "r", errors="replace") as f:
            data = f.read()
    except OSError:
        _log.error("VDF validation: cannot read %s", path)
        return False

    depth = 0
    in_quote = False
    for i, c in enumerate(data):
        if c == '"' and (i == 0 or data[i - 1] != '\\'):
            in_quote = not in_quote
        elif not in_quote:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth < 0:
                    break

    if depth != 0:
        _log.error(
            "VDF validation FAILED for %s (brace depth %d) — restoring backup",
            path, depth,
        )
        bak = path + ".bak"
        if os.path.exists(bak):
            try:
                shutil.copy2(bak, path)
                _log.info("VDF restored from %s", bak)
            except OSError:
                _log.error("VDF restore failed for %s", path, exc_info=True)
        return False

    return True


def _write_and_validate_vdf(path: str, data: str, encoding: str = "utf-8",
                            errors: str | None = None) -> bool:
    """
    Write VDF data to path, then validate brace balance.

    Backs up before writing. If validation fails, the backup is
    automatically restored. Returns True if the write is clean.

    encoding / errors — passed to open(). Use errors="replace" for
    localconfig.vdf which can contain non-UTF-8 bytes.
    """
    _backup_file(path)
    open_kwargs = {"encoding": encoding}
    if errors:
        open_kwargs = {"errors": errors}
    with open(path, "w", **open_kwargs) as f:
        f.write(data)
    if not _validate_vdf(path):
        _log.error("VDF corruption detected in %s after write", path)
        return False
    return True


def get_proton_path(steam_root):
    """
    Find the best available Proton binary for running Windows executables.

    Preference order:
      1. GE-Proton in ~/.local/share/Steam/compatibilitytools.d/
      2. GE-Proton in steam_root/compatibilitytools.d/
      3. Newest vanilla Proton in steam_root/steamapps/common/

    Uses numeric version sorting so GE-Proton9-28 > GE-Proton9-5,
    and Proton 10 > Proton 9.
    """
    def _version_key(name):
        parts = re.findall(r'\d+', name)
        return tuple(int(p) for p in parts)

    # Check GE-Proton in both possible locations
    ge_search_dirs = [
        os.path.expanduser("~/.local/share/Steam/compatibilitytools.d"),
        os.path.join(steam_root, "compatibilitytools.d"),
    ]
    for ge_dir in ge_search_dirs:
        if not os.path.isdir(ge_dir):
            continue
        candidates = sorted(
            [d for d in os.listdir(ge_dir) if d.startswith("GE-Proton")],
            key=_version_key,
            reverse=True,
        )
        for name in candidates:
            proton = os.path.join(ge_dir, name, "proton")
            if os.path.isfile(proton):
                return proton

    # Check vanilla Proton in steamapps/common/
    common = os.path.join(steam_root, "steamapps", "common")
    if os.path.isdir(common):
        candidates = sorted(
            [d for d in os.listdir(common)
             if d.startswith("Proton") and not d.startswith("Proton EasyAntiCheat")],
            key=_version_key,
            reverse=True,
        )
        for name in candidates:
            proton = os.path.join(common, name, "proton")
            if os.path.isfile(proton):
                return proton

    return None


def set_launch_options(steam_root, appid, launch_opts, game_key=None):
    """
    Set launch options for a Steam game in localconfig.vdf.

    steam_root  — Steam root path (e.g. ~/.local/share/Steam)
    appid       — Steam appid (string or int)
    launch_opts — the launch option string to set
    game_key    — optional game key for logging
    """
    appid_str = str(appid)
    userdata = os.path.join(steam_root, "userdata")
    if not os.path.exists(userdata):
        _log.warning("userdata dir not found: %s", userdata)
        return

    for uid in os.listdir(userdata):
        vdf_path = os.path.join(userdata, uid, "config", "localconfig.vdf")
        if not os.path.exists(vdf_path):
            continue

        with open(vdf_path, "r", errors="replace") as f:
            content = f.read()

        # Find the apps block in localconfig
        apps_pat = re.compile(r'"apps"\s*\{', re.IGNORECASE)
        apps_match = apps_pat.search(content)
        if not apps_match:
            continue

        apps_open = apps_match.end() - 1
        apps_close = _find_block_end(content, apps_open)
        if apps_close == -1:
            continue

        apps_block = content[apps_open + 1:apps_close]

        # Find the appid block inside apps
        appid_pat = re.compile(rf'"{re.escape(appid_str)}"\s*\{{', re.IGNORECASE)
        appid_match = appid_pat.search(apps_block)

        if appid_match:
            # Appid block exists — find or replace LaunchOptions inside it
            appid_open = appid_match.end() - 1
            appid_close = _find_block_end(apps_block, appid_open)
            if appid_close == -1:
                continue

            inner = apps_block[appid_open + 1:appid_close]
            lo_pat = re.compile(r'"LaunchOptions"\s+"[^"]*"', re.IGNORECASE)
            if lo_pat.search(inner):
                inner = lo_pat.sub(f'"LaunchOptions"\t\t"{launch_opts}"', inner)
            else:
                inner = inner.rstrip() + f'\n\t\t\t\t\t"LaunchOptions"\t\t"{launch_opts}"\n\t\t\t\t'

            apps_block = (
                apps_block[:appid_open + 1] +
                inner +
                apps_block[appid_close:]
            )
        else:
            # Appid block doesn't exist — create it
            entry = (
                f'\n\t\t\t\t"{appid_str}"\n'
                f'\t\t\t\t{{\n'
                f'\t\t\t\t\t"LaunchOptions"\t\t"{launch_opts}"\n'
                f'\t\t\t\t}}'
            )
            apps_block = apps_block.rstrip() + entry + '\n\t\t\t'

        content = content[:apps_open + 1] + apps_block + content[apps_close:]

        _write_and_validate_vdf(vdf_path, content, errors="replace")
        _record_localconfig(uid, appid_str, "LaunchOptions", launch_opts)
        label = game_key or appid_str
        _log.info("launch options set for %s (uid %s): %s", label, uid, launch_opts)


def set_compat_tool(steam_root, appids, version):
    """
    Set CompatToolMapping for one or more appids in Steam's config.vdf.

    steam_root — Steam root path
    appids     — list of int or str appids
    version    — GE-Proton folder name (e.g. "GE-Proton10-32")
    """
    STEAM_CONFIG = os.path.join(steam_root, "config", "config.vdf")
    if not os.path.exists(STEAM_CONFIG):
        _log.warning("config.vdf not found at %s", STEAM_CONFIG)
        return

    with open(STEAM_CONFIG, "r", encoding="utf-8") as f:
        data = f.read()

    def _entry(appid_str):
        return (
            f'\t\t\t\t"{appid_str}"\n'
            f'\t\t\t\t{{\n'
            f'\t\t\t\t\t"name"\t\t"{version}"\n'
            f'\t\t\t\t\t"config"\t\t""\n'
            f'\t\t\t\t\t"priority"\t\t"250"\n'
            f'\t\t\t\t}}\n'
        )

    if '"CompatToolMapping"' not in data:
        # No CompatToolMapping section at all — create it
        block = '\t\t\t"CompatToolMapping"\n\t\t\t{\n'
        for appid in appids:
            block += _entry(str(appid))
        block += '\t\t\t}\n'
        data = re.sub(
            r'("Software"\s*\{)',
            r'\1\n' + block,
            data,
            count=1,
        )
    else:
        # CompatToolMapping exists — replace or insert each appid entry
        for appid in appids:
            appid_str = str(appid)
            entry = _entry(appid_str)
            # Use re.DOTALL so [^}] correctly spans multiple lines inside the block.
            # The entry block is 4 lines, so [^}]* with DOTALL is required.
            pattern = rf'(\t+"{re.escape(appid_str)}"\n\t+\{{[^}}]*\}})'
            if re.search(pattern, data, re.MULTILINE | re.DOTALL):
                # Replace existing block
                data = re.sub(pattern, entry.rstrip('\n'), data, flags=re.MULTILINE | re.DOTALL)
            else:
                # Insert after CompatToolMapping opening brace
                data = re.sub(
                    r'("CompatToolMapping"\s*\{)',
                    r'\1\n' + entry,
                    data,
                    count=1,
                )

    _write_and_validate_vdf(STEAM_CONFIG, data)
    for appid in appids:
        _record_config_vdf(str(appid), "CompatToolMapping", version)


def clear_compat_tool(appids):
    """
    Remove CompatToolMapping entries for the given appids from Steam's
    config.vdf. Inverse of set_compat_tool — used for games where Steam
    must NOT wrap the launch in a compat tool, e.g. LCD Plutonium games
    whose launch options invoke `flatpak run` to hand off to Heroic.

    Steam wraps any launch with a CompatToolMapping entry inside Steam
    Linux Runtime (sniper). From inside that container the host's flatpak
    binary is invisible, so the flatpak invocation fails and the launch
    flash-closes. Heroic owns the Proton invocation downstream, so the
    Steam-side compat tool is not just unnecessary — it actively breaks
    the launch.

    Silently no-ops if config.vdf doesn't exist or the entry isn't there.
    Must be called while Steam is closed so the change persists.

    appids — list of int or str appids
    """
    if not os.path.exists(STEAM_CONFIG):
        return

    with open(STEAM_CONFIG, "r", encoding="utf-8") as f:
        data = f.read()

    modified = False
    for appid in appids:
        appid_str = str(appid)
        # Same pattern as shortcut._clear_compat_tool — matches the appid
        # block including its trailing newline so the file stays clean.
        pattern = rf'\t+"{re.escape(appid_str)}"\n\t+\{{[^}}]*\}}\n?'
        if re.search(pattern, data, re.MULTILINE | re.DOTALL):
            data = re.sub(pattern, "", data, flags=re.MULTILINE | re.DOTALL)
            modified = True

    if modified:
        _write_and_validate_vdf(STEAM_CONFIG, data)
        for appid in appids:
            _remove_config_vdf(str(appid), "CompatToolMapping")


def set_default_launch_option(steam_root, appids_config):
    """
    Set the default launch option for games with multiple launch modes so
    Steam Deck skips the 'which mode?' dialog.

    On SteamOS the picker is controlled by the Deck configurator system, not
    the standard localconfig.vdf apps block. This function targets the correct
    Deck-specific location:

      - Writes DefaultLaunchOption into the "apps" block that sits directly
        after "Deck_ConfiguratorInterstitialApps_AppLauncherInteractionIssues"
      - Sets "Deck_ConfiguratorInterstitialsCheckbox_AppLauncherInteractionIssues"
        to "1" so the Deck configurator treats the choice as confirmed and
        stops showing the picker

    appids_config — dict mapping appid to (hash_key, index)
        e.g. {"7940": ("7a722f97", "1"), "10090": ("9aa5e05f", "0")}

    Must be called while Steam is closed.
    """
    userdata = os.path.join(steam_root, "userdata")
    if not os.path.exists(userdata):
        return

    for uid in os.listdir(userdata):
        vdf_path = os.path.join(userdata, uid, "config", "localconfig.vdf")
        if not os.path.exists(vdf_path):
            continue

        with open(vdf_path, "r", errors="replace") as f:
            content = f.read()

        modified = False

        # ── Step 1: set the checkbox to "1" so the Deck configurator treats
        # the launch choice as confirmed and stops showing the picker ──────────
        checkbox_pattern = re.compile(
            r'("Deck_ConfiguratorInterstitialsCheckbox_AppLauncherInteractionIssues"\s*")((?:[^"\\]|\\.)*)(")',
            re.IGNORECASE
        )
        if checkbox_pattern.search(content):
            content  = checkbox_pattern.sub(r'\g<1>1\g<3>', content)
            modified = True

        # ── Step 2: write DefaultLaunchOption into the Deck configurator's
        # own "apps" block — this is what the picker actually reads on SteamOS.
        # The block sits immediately after the InterstitialApps key. ──────────
        interstitial_pattern = re.compile(
            r'"Deck_ConfiguratorInterstitialApps_AppLauncherInteractionIssues"\s*"[^"]*"\s*"apps"\s*\{',
            re.IGNORECASE
        )
        interstitial_match = interstitial_pattern.search(content)

        if interstitial_match:
            apps_open  = interstitial_match.end() - 1
            apps_close = _find_block_end(content, apps_open)
            if apps_close != -1:
                apps_block = content[apps_open + 1:apps_close]

                for appid, (hash_key, index) in appids_config.items():
                    entry = (
                        f'\t\t\t\t"{appid}"\n'
                        f'\t\t\t\t{{\n'
                        f'\t\t\t\t\t"DefaultLaunchOption"\n'
                        f'\t\t\t\t\t{{\n'
                        f'\t\t\t\t\t\t"{hash_key}"\t\t"{index}"\n'
                        f'\t\t\t\t\t}}\n'
                        f'\t\t\t\t}}\n'
                    )
                    appid_pattern = re.compile(
                        r'"' + re.escape(appid) + r'"\s*\{',
                        re.IGNORECASE
                    )
                    appid_match = appid_pattern.search(apps_block)
                    if appid_match:
                        appid_open  = appid_match.end() - 1
                        appid_close = _find_block_end(apps_block, appid_open)
                        if appid_close != -1:
                            apps_block = (
                                apps_block[:appid_match.start()] +
                                entry.strip() +
                                apps_block[appid_close + 1:]
                            )
                    else:
                        apps_block = apps_block.rstrip() + '\n' + entry

                content = (
                    content[:apps_open + 1] +
                    apps_block +
                    content[apps_close:]
                )
                modified = True
        else:
            # Deck configurator block doesn't exist yet — build it from scratch
            # and insert before "LaunchOptionTipsShown" if present
            deck_block  = '\t\t\t"Deck_ConfiguratorInterstitialsVersionSeen_AppLauncherInteractionIssues"\t\t"1"\n'
            deck_block += '\t\t\t"Deck_ConfiguratorInterstitialsCheckbox_AppLauncherInteractionIssues"\t\t"1"\n'
            deck_block += '\t\t\t"Deck_ConfiguratorInterstitialApps_AppLauncherInteractionIssues"\t\t"[' + ','.join(appids_config.keys()) + ']"\n'
            deck_block += '\t\t\t"apps"\n\t\t\t{\n'
            for appid, (hash_key, index) in appids_config.items():
                deck_block += (
                    f'\t\t\t\t"{appid}"\n'
                    f'\t\t\t\t{{\n'
                    f'\t\t\t\t\t"DefaultLaunchOption"\n'
                    f'\t\t\t\t\t{{\n'
                    f'\t\t\t\t\t\t"{hash_key}"\t\t"{index}"\n'
                    f'\t\t\t\t\t}}\n'
                    f'\t\t\t\t}}\n'
                )
            deck_block += '\t\t\t}\n'

            tips_pattern = re.compile(r'"LaunchOptionTipsShown"', re.IGNORECASE)
            tips_match   = tips_pattern.search(content)
            if tips_match:
                content  = content[:tips_match.start()] + deck_block + content[tips_match.start():]
                modified = True
            else:
                # LaunchOptionTipsShown absent (fresh account) — try to insert
                # before the closing brace of the Steam user block instead.
                # Find the system block that contains localconfig keys — it sits
                # inside "Software" -> "Valve" -> "Steam" in the file hierarchy.
                steam_block_pattern = re.compile(r'"Steam"\s*\{', re.IGNORECASE)
                steam_match = steam_block_pattern.search(content)
                if steam_match:
                    steam_open  = steam_match.end() - 1
                    steam_close = _find_block_end(content, steam_open)
                    if steam_close != -1:
                        # Insert deck_block just before the Steam block closes
                        content = (
                            content[:steam_close] +
                            deck_block +
                            content[steam_close:]
                        )
                        modified = True

        if modified:
            _write_and_validate_vdf(vdf_path, content, errors="replace")
            for appid, (hash_key, index) in appids_config.items():
                _record_localconfig(
                    uid, appid, "DefaultLaunchOption",
                    json.dumps({"hash_key": hash_key, "index": index})
                )
