"""
ui_manage.py — Post-install management screens for DeckOps

Screens: ManagementCard, ManagementScreen, ControllerInfoScreen,
         ConfigureScreen, UpdateScreen
Extracted from ui_qt.py — all hardcoded stack indices replaced with named lookups.
"""

import os, subprocess, threading

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QCheckBox, QProgressBar, QPlainTextEdit,
    QFrame, QSizePolicy, QMessageBox, QLineEdit, QSlider,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QGraphicsOpacityEffect

from detect_games import find_steam_root, parse_library_folders, find_installed_games
import config as cfg

from ui_constants import (
    C_BG, C_CARD, C_IW, C_TREY, C_DIM, C_DARK_BTN, C_RED_BTN, C_BLUE_BTN,
    font, _btn, _lbl, _hdiv, _title_block, _log_to_file, _Sigs,
    _detached_open, _header_path, _ask_iw4x_dlc,
    ALL_GAMES, KEY_CLIENT, KEY_MODE_LABEL,
    _active_keys, _active_client, _active_appid,
    SP_IMAGE_URLS, IMG_RATIO, CARD_COLS, CARD_MAX_W,
    HEROES_DIR, PROJECT_ROOT,
    _music_volume, _music_enabled,
    _set_audio_volume, _set_audio_enabled, _start_audio, _kill_audio,
    go_to, get_screen,
)


# ── ManagementCard ────────────────────────────────────────────────────────────
class ManagementCard(QFrame):
    def __init__(self, gd, installed, on_setup, on_configure,
                 on_readd=None, parent=None):
        super().__init__(parent)
        color = C_IW if gd["dev"] == "iw" else C_TREY
        self._color  = color
        self._appid  = _active_appid(gd)
        self._is_lan = gd.get("client") == "lan"
        self.setObjectName("MC")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMaximumWidth(CARD_MAX_W)

        keys       = _active_keys(gd)
        client     = _active_client(gd)

        if self._is_lan:
            # DeckOps LAN card — always shown, no key-based detection
            ik         = []
            is_setup   = False
            is_present = True
        else:
            ik         = [k for k in keys if k in installed]
            is_setup   = any(cfg.is_game_setup(k) for k in keys)
            is_present = len(ik) > 0

        border_color = color if is_setup else ("#445544" if is_present else "#333344")
        self.setStyleSheet(
            f"QFrame#MC{{background:{C_CARD};border-top:3px solid {border_color};border-radius:8px;}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Image container with overlaid badge and buttons ───────────────
        img_container = QWidget()
        img_container.setStyleSheet("background:#0A0A10;border:none;")
        img_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._img = QLabel(img_container)
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setStyleSheet("background:transparent;border:none;")
        if not is_setup and not self._is_lan:
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.45 if is_present else 0.25)
            self._img.setGraphicsEffect(effect)

        # Client badge — overlaid top-left on the image
        self._client_badge = QPushButton(client.upper(), img_container)
        self._client_badge.setFont(font(8, True)); self._client_badge.setEnabled(False)
        self._client_badge.setStyleSheet(
            f"QPushButton{{background:{color};color:#FFF;border:none;border-radius:3px;padding:2px 6px;}}"
            f"QPushButton:disabled{{background:{color};color:#FFF;}}"
        )
        self._client_badge.adjustSize()
        self._client_badge.raise_()

        # Buttons — overlaid bottom-center on the image
        self._btn_bar = QWidget(img_container)
        self._btn_bar.setStyleSheet("background:transparent;border:none;")
        bb = QHBoxLayout(self._btn_bar)
        bb.setContentsMargins(6, 0, 6, 0); bb.setSpacing(4)

        if self._is_lan:
            readd_btn = _btn("Re-Add", C_TREY, size=9, h=26)
            if on_readd:
                readd_btn.clicked.connect(lambda: on_readd(gd))
            readd_btn.setStyleSheet(
                f"QPushButton{{background:{C_TREY};color:#FFF;border:none;"
                f"border-radius:4px;font-weight:bold;padding:0 10px;}}"
            )
            bb.addStretch(); bb.addWidget(readd_btn); bb.addStretch()
        elif not is_setup and is_present:
            setup_btn = _btn("Set Up", C_IW, size=9, h=26)
            setup_btn.clicked.connect(lambda: on_setup(gd))
            setup_btn.setStyleSheet(
                f"QPushButton{{background:{C_IW};color:#FFF;border:none;"
                f"border-radius:4px;font-weight:bold;padding:0 10px;}}"
            )
            bb.addStretch(); bb.addWidget(setup_btn); bb.addStretch()
        elif is_setup:
            cfg_btn = _btn("Configure", C_DARK_BTN, size=9, h=26)
            cfg_btn.clicked.connect(lambda: on_configure(gd, ik))
            cfg_btn.setStyleSheet(
                f"QPushButton{{background:rgba(51,51,63,200);color:#CCC;border:none;"
                f"border-radius:4px;font-weight:bold;padding:0 10px;}}"
            )
            bb.addStretch(); bb.addWidget(cfg_btn); bb.addStretch()
        else:
            setup_btn = _btn("Set Up", C_DARK_BTN, size=9, h=26)
            setup_btn.setEnabled(False)
            setup_btn.setStyleSheet(
                f"QPushButton{{background:rgba(37,37,53,200);color:#555568;border:none;"
                f"border-radius:4px;font-weight:bold;padding:0 10px;}}"
                f"QPushButton:disabled{{background:rgba(37,37,53,200);color:#555568;}}"
            )
            bb.addStretch(); bb.addWidget(setup_btn); bb.addStretch()

        self._btn_bar.adjustSize()
        self._btn_bar.raise_()

        self._img_container = img_container
        lay.addWidget(img_container)
        self._raw_pixmap = None

        if self._is_lan:
            local_img = os.path.join(HEROES_DIR, "deckops_grid.png")
            if os.path.exists(local_img):
                self._raw_pixmap = QPixmap(local_img)
        else:
            cached = _header_path(self._appid)
            if os.path.exists(cached):
                self._raw_pixmap = QPixmap(cached)
            else:
                threading.Thread(target=self._fetch, args=(self._appid,), daemon=True).start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._scale_image()

    def _scale_image(self):
        w = self.width()
        h = int(w * IMG_RATIO)
        self._img_container.setFixedSize(w, h)
        self._img.setFixedSize(w, h)
        if self._raw_pixmap:
            self._img.setPixmap(
                self._raw_pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            )
        # Position client badge — top-left with 4px margin
        self._client_badge.move(4, 4)
        # Position button bar — bottom, full width
        self._btn_bar.setFixedWidth(w)
        bh = self._btn_bar.sizeHint().height()
        self._btn_bar.move(0, h - bh - 4)

    def _fetch(self, appid):
        url = SP_IMAGE_URLS.get(appid)
        if not url:
            return
        try:
            import urllib.request
            dest = _header_path(appid)
            urllib.request.urlretrieve(url, dest)
            pix = QPixmap(dest)
            if not pix.isNull():
                self._raw_pixmap = pix
                QTimer.singleShot(0, self._scale_image)
        except Exception:
            pass


# ── ManagementScreen ──────────────────────────────────────────────────────────
class ManagementScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.installed={}; self.screen_name = "ManagementScreen"
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{C_CARD};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,0,20,0)
        title = QLabel("DECKOPS"); title.setFont(font(22, display=True))
        title.setStyleSheet("color:#FFF;background:transparent;")
        hl.addWidget(title)
        nightly_lbl = QLabel("NIGHTLY"); nightly_lbl.setFont(font(9, bold=True))
        nightly_lbl.setStyleSheet(
            "color:#F47B20;background:#2A1A08;border:1px solid #F47B20;"
            "border-radius:4px;padding:1px 6px;"
        )
        hl.addWidget(nightly_lbl)
        hl.addStretch()
        guide_btn = _btn("📋  Guide", C_BLUE_BTN, size=11, h=36); guide_btn.setFixedWidth(100)
        guide_btn.clicked.connect(lambda: go_to(self.stack, "ControllerInfoScreen"))
        hl.addWidget(guide_btn)
        hl.addSpacing(8)
        cfg_btn = _btn("⚙  Settings", C_DARK_BTN, size=11, h=36); cfg_btn.setFixedWidth(120)
        cfg_btn.clicked.connect(lambda: go_to(self.stack, "ConfigureScreen"))
        hl.addWidget(cfg_btn)
        lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); self._grid = QGridLayout(inner)
        self._grid.setContentsMargins(16,16,16,16); self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        scroll.setWidget(inner); lay.addWidget(scroll, stretch=1)

        self._status = _lbl("", 12, C_DIM)
        self._status.setContentsMargins(16,4,16,4)
        lay.addWidget(self._status)

    def set_installed(self, installed):
        self.installed = installed
        self._rebuild()

    def showEvent(self, e):
        super().showEvent(e)
        root = find_steam_root()
        merged = find_installed_games(parse_library_folders(root))
        # Merge own games so cards show regardless of install source
        if cfg.get_game_source() == "own":
            from detect_games import find_own_installed
            own = find_own_installed()
            # Own games take priority only for keys not already in Steam
            for k, v in own.items():
                if k not in merged:
                    merged[k] = v
        self.installed = merged
        self._rebuild()

    def _rebuild(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        games = [g for g in ALL_GAMES
                 if _active_keys(g) or g.get("client") == "lan"]

        for idx, gd in enumerate(games):
            row = idx // CARD_COLS
            col = idx  % CARD_COLS
            card = ManagementCard(
                gd, self.installed,
                on_setup     = self._setup,
                on_configure = self._configure,
                on_readd     = self._readd,
            )
            self._grid.addWidget(card, row, col)

        total = len(games)
        remainder = total % CARD_COLS
        if remainder:
            for col in range(remainder, CARD_COLS):
                self._grid.addWidget(QWidget(), total // CARD_COLS, col)

    def _readd(self, gd):
        """Re-add the Plutonium offline launcher shortcut."""
        from shortcut import create_launcher_shortcut
        self._status.setText("Re-adding Plutonium offline launcher...")

        def _on_progress(msg):
            self._status.setText(msg)

        def _run():
            create_launcher_shortcut(on_progress=_on_progress)
            QTimer.singleShot(0, lambda: self._status.setText(
                "Plutonium offline launcher shortcut re-added."
            ))

        threading.Thread(target=_run, daemon=True).start()

    def _setup(self, gd):
        """Route a single card's keys through the install flow."""
        root = find_steam_root()
        keys = _active_keys(gd)
        # Find which keys are present in the merged installed dict
        present_keys = [k for k in keys if k in self.installed]
        if not present_keys:
            self._status.setText("Game files not found.")
            return

        source = cfg.get_game_source() or "steam"

        # Build selected tuples for the install screen
        selected = [(k, gd, self.installed[k]) for k in present_keys]

        if source == "own":
            # Determine which are own vs Steam
            own_selected = {}
            steam_selected = []
            for k, g_gd, game in selected:
                if game.get("source") == "own":
                    own_selected[k] = game
                else:
                    steam_selected.append((k, g_gd, game))

            s = get_screen(self.stack, "OwnInstallScreen")
            s.own_selected = own_selected
            s.steam_selected = steam_selected
            s.steam_root = root
            s._return_to_management = True
            s.install_iw4x_dlc = _ask_iw4x_dlc(self, selected)
            go_to(self.stack, "OwnInstallScreen")
        else:
            # Standard Steam flow
            s = get_screen(self.stack, "InstallScreen")
            s.selected = selected
            s.steam_root = root
            s._return_to_management = True
            s.install_iw4x_dlc = _ask_iw4x_dlc(self, selected)
            go_to(self.stack, "InstallScreen")

    def _configure(self, gd, installed_keys):
        """Show configure dialog with Mods, Update, and Reinstall options."""
        _MOD_CLIENTS = ("cod4x", "iw4x", "plutonium", "alterware", "t7x")
        has_mods_support = any(KEY_CLIENT.get(k, "") in _MOD_CLIENTS for k in installed_keys)
        has_mod_client = any(KEY_CLIENT.get(k, "") not in ("steam", "") for k in installed_keys)

        msg = QMessageBox(self)
        msg.setWindowTitle(gd["base"])
        msg.setText("What would you like to do?")

        mods_btn = None
        if has_mods_support:
            mods_btn = msg.addButton("Mods", QMessageBox.AcceptRole)
        upd_btn = None
        if has_mod_client:
            upd_btn = msg.addButton("Update", QMessageBox.AcceptRole)
        rei_btn = msg.addButton("Reinstall", QMessageBox.AcceptRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec_()

        clicked = msg.clickedButton()
        if clicked == mods_btn:
            self._mods(gd, installed_keys)
        elif clicked == upd_btn:
            self._update(gd, installed_keys)
        elif clicked == rei_btn:
            self._reinstall(gd)

    def _update(self, gd, keys):
        """Route a single card's installed keys through the update flow."""
        root = find_steam_root()
        # Use the merged installed dict (already built in showEvent)
        selected = [(k, gd, self.installed.get(k, {})) for k in keys
                     if self.installed.get(k)]
        if not selected:
            self._status.setText("Game not found.")
            return
        s = get_screen(self.stack, "UpdateScreen")
        s.selected   = selected
        s.steam_root = root
        go_to(self.stack, "UpdateScreen")

    def _reinstall(self, gd):
        """Unmark game keys as set up, then route through the install flow."""
        keys = _active_keys(gd)
        cfg.unmark_game_setup(keys)
        self._status.setText(f"Cleared setup state for {gd['base']}. Running clean install...")
        # Route through the same path as "Set Up"
        self._setup(gd)

    def _mods(self, gd, installed_keys):
        """Open the mod folder for a game. Shows a chooser for games with
        both mods/ and usermaps/ directories (CoD4x, IW4x, T7X), for
        AlterWare games with data/scripts/mp and data/scripts/sp, or for
        OLED Plutonium games whose SP/MP modes live in separate prefixes."""

        # ── Plutonium storage name mapping ────────────────────────────────
        _PLUT_STORAGE = {
            "t4sp": "t4", "t4mp": "t4",
            "t5sp": "t5", "t5mp": "t5",
            "t6mp": "t6", "t6zm": "t6",
            "iw5mp": "iw5", "iw5mp_ds": "iw5",
        }

        # Appid per key — used to detect when keys on the same card
        # have separate Wine prefixes (different appids = different
        # mods/ folders on OLED).
        _PLUT_APPID = {
            "t4sp": 10090, "t4mp": 10090,
            "t5sp": 42700, "t5mp": 42710,
            "t6mp": 202990, "t6zm": 212910,
            "iw5mp": 42690, "iw5mp_ds": 42750,
        }

        # Friendly labels for the dialog buttons
        _PLUT_MODE_LABEL = {
            "t4sp": "Campaign / Zombies", "t4mp": "Multiplayer",
            "t5sp": "Campaign / Zombies", "t5mp": "Multiplayer",
            "t6zm": "Zombies",            "t6mp": "Multiplayer",
            "iw5mp": "Multiplayer",       "iw5mp_ds": "Dedicated Server",
        }

        def _open_folder(path):
            os.makedirs(path, exist_ok=True)
            _detached_open(["xdg-open", path])
            self._status.setText(f"Opened: {path}")

        def _resolve_plut_mods_dir(game_key):
            """Resolve the Plutonium mods/ folder for a game key."""
            storage_name = _PLUT_STORAGE.get(game_key)
            if not storage_name:
                return None

            if cfg.is_lcd():
                # LCD: single Heroic shared prefix for all games
                from plutonium_lcd import get_shared_plut_dir
                plut_dir = get_shared_plut_dir()
            else:
                # OLED: read plut_dir from per-game metadata
                game = self.installed.get(game_key, {})
                install_dir = game.get("install_dir", "")
                if install_dir:
                    meta_path = os.path.join(install_dir, "deckops_plutonium.json")
                    if os.path.exists(meta_path):
                        try:
                            import json
                            with open(meta_path) as f:
                                meta = json.load(f)
                            plut_dir = meta.get("plut_dir", "")
                        except Exception:
                            plut_dir = ""
                    else:
                        plut_dir = ""
                else:
                    plut_dir = ""

            if not plut_dir:
                return None
            return os.path.join(plut_dir, "storage", storage_name, "mods")

        # Determine which client we're dealing with from the installed keys
        client = None
        plut_keys = []
        alterware_keys = []
        for k in installed_keys:
            c = KEY_CLIENT.get(k, "")
            if c in ("cod4x", "iw4x"):
                client = c
                break
            elif c == "t7x":
                client = "t7x"
                break
            elif c == "alterware":
                client = "alterware"
                alterware_keys.append(k)
            elif c == "plutonium" and k in _PLUT_STORAGE:
                client = "plutonium"
                plut_keys.append(k)

        if not client:
            self._status.setText("No mod support for this game.")
            return

        if client in ("cod4x", "iw4x"):
            mod_key = installed_keys[0]
            game = self.installed.get(mod_key, {})
            install_dir = game.get("install_dir", "")
            if not install_dir:
                self._status.setText("Game install directory not found.")
                return
            # Two folders — ask user which one
            msg = QMessageBox(self)
            msg.setWindowTitle("Open Mod Folder")
            msg.setText(f"Which folder would you like to open for {gd['base']}?")
            mods_btn = msg.addButton("Mods", QMessageBox.AcceptRole)
            usermaps_btn = msg.addButton("User Maps", QMessageBox.AcceptRole)
            msg.addButton("Cancel", QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked == mods_btn:
                _open_folder(os.path.join(install_dir, "mods"))
            elif clicked == usermaps_btn:
                _open_folder(os.path.join(install_dir, "usermaps"))

        elif client == "t7x":
            from t7x import _get_sibling_dir
            mod_key = [k for k in installed_keys if KEY_CLIENT.get(k) == "t7x"]
            mod_key = mod_key[0] if mod_key else installed_keys[0]
            game = self.installed.get(mod_key, {})
            stock_dir = game.get("install_dir", "")
            if not stock_dir:
                self._status.setText("Game install directory not found.")
                return
            # T7X writes mods/usermaps into the DeckOps-T7X sibling dir,
            # not the stock BO3 install directory that detect_games returns.
            install_dir = _get_sibling_dir(stock_dir)
            if not os.path.isdir(install_dir):
                self._status.setText("T7X directory not found. Has T7X been installed?")
                return
            # Two folders — ask user which one
            msg = QMessageBox(self)
            msg.setWindowTitle("Open Mod Folder")
            msg.setText(f"Which folder would you like to open for {gd['base']} (T7x)?")
            mods_btn = msg.addButton("Mods", QMessageBox.AcceptRole)
            usermaps_btn = msg.addButton("User Maps", QMessageBox.AcceptRole)
            msg.addButton("Cancel", QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked == mods_btn:
                _open_folder(os.path.join(install_dir, "mods"))
            elif clicked == usermaps_btn:
                _open_folder(os.path.join(install_dir, "usermaps"))

        elif client == "alterware":
            if not alterware_keys:
                self._status.setText("No AlterWare mod keys found.")
                return
            mod_key = alterware_keys[0]
            game = self.installed.get(mod_key, {})
            install_dir = game.get("install_dir", "")
            if not install_dir:
                self._status.setText("Game install directory not found.")
                return

            # Determine which mode buttons to show based on installed keys
            has_mp = any(k.endswith("mp") for k in alterware_keys)
            has_sp = any(k.endswith("sp") for k in alterware_keys)

            if has_mp and has_sp:
                msg = QMessageBox(self)
                msg.setWindowTitle("Open Scripts Folder")
                msg.setText(f"Which scripts folder for {gd['base']}?")
                mp_btn = msg.addButton("MP Scripts", QMessageBox.AcceptRole)
                sp_btn = msg.addButton("SP Scripts", QMessageBox.AcceptRole)
                msg.addButton("Cancel", QMessageBox.RejectRole)
                msg.exec_()
                clicked = msg.clickedButton()
                if clicked == mp_btn:
                    _open_folder(os.path.join(install_dir, "data", "scripts", "mp"))
                elif clicked == sp_btn:
                    _open_folder(os.path.join(install_dir, "data", "scripts", "sp"))
            elif has_mp:
                _open_folder(os.path.join(install_dir, "data", "scripts", "mp"))
            elif has_sp:
                _open_folder(os.path.join(install_dir, "data", "scripts", "sp"))

        elif client == "plutonium":
            if not plut_keys:
                self._status.setText("No Plutonium mod keys found.")
                return

            # Check if multiple keys have different appids (OLED only).
            # If so, they have separate prefixes with separate mods/ folders.
            unique_appids = set(_PLUT_APPID.get(k) for k in plut_keys)
            need_chooser = not cfg.is_lcd() and len(unique_appids) > 1

            if need_chooser:
                msg = QMessageBox(self)
                msg.setWindowTitle("Open Mod Folder")
                msg.setText(f"Which mode's mods folder for {gd['base']}?")
                key_buttons = []
                for k in plut_keys:
                    label = _PLUT_MODE_LABEL.get(k, k)
                    btn = msg.addButton(label, QMessageBox.AcceptRole)
                    key_buttons.append((btn, k))
                msg.addButton("Cancel", QMessageBox.RejectRole)
                msg.exec_()
                clicked = msg.clickedButton()
                for btn, k in key_buttons:
                    if clicked == btn:
                        mods_path = _resolve_plut_mods_dir(k)
                        if mods_path:
                            _open_folder(mods_path)
                        else:
                            self._status.setText(f"Could not resolve mods folder for {k}.")
                        break
            else:
                # Single prefix or LCD — open directly
                mods_path = _resolve_plut_mods_dir(plut_keys[0])
                if mods_path:
                    _open_folder(mods_path)
                else:
                    self._status.setText("Could not resolve Plutonium mods folder.")


# ── ControllerInfoScreen ─────────────────────────────────────────────────────
class ControllerInfoScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "ControllerInfoScreen"
        lay = QVBoxLayout(self); lay.setContentsMargins(60,30,60,30); lay.setSpacing(8)

        t = QLabel("SETUP COMPLETE"); t.setFont(font(32, True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;"); lay.addWidget(t)
        lay.addWidget(_lbl(
            "DeckOps has configured your games with controller profiles, GE-Proton, "
            "and display settings. You're ready to play.",
            13, C_DIM))
        lay.addWidget(_hdiv())

        # ── Cloud saves ───────────────────────────────────────────────────────
        lay.addWidget(_lbl("⚠  Steam Cloud Saves", 13, C_TREY, bold=True, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "If Steam asks about cloud saves, choose Keep Local. "
            "If a game asks for Safe Mode, choose No.",
            11, C_DIM, align=Qt.AlignLeft))
        lay.addWidget(_hdiv())

        # ── MW1 / WaW shortcuts ───────────────────────────────────────────────
        lay.addWidget(_lbl("🎮  Modern Warfare 1 & World at War", 13, C_IW, bold=True, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "MW1 and WaW each have a separate multiplayer shortcut in your Steam library "
            "created by DeckOps. Launch the main game entry for singleplayer/campaign. "
            "Launch the DeckOps shortcut for multiplayer.",
            11, C_DIM, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "MW1 Singleplayer (IW3SP-MOD): On your first launch, "
            "the game will ask you to select a profile. Choose \"Player\" -- "
            "this is the profile DeckOps created with your display settings. "
            "Creating a new profile will use default settings instead.",
            11, C_DIM, align=Qt.AlignLeft))

        lay.addWidget(_hdiv())

        # ── First launch note ────────────────────────────────────────────────
        lay.addWidget(_lbl("⏳  First Launch", 13, "#5B9BD5", bold=True, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "All games may take a while to launch the first time — this is normal. "
            "They will run fine after the initial launch.",
            11, C_DIM, align=Qt.AlignLeft))

        lay.addWidget(_hdiv())

        # ── BO3 first launch note ────────────────────────────────────────────
        lay.addWidget(_lbl("🎮  Black Ops III — First Launch", 13, C_TREY, bold=True, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "CleanOps and T7X install on their first run, which takes a bit and may "
            "slow down the Steam Deck temporarily. This is expected — do not worry. "
            "Wiggle the analog sticks to keep the screen from turning off while you wait, "
            "since the game hasn't officially launched yet.",
            11, C_DIM, align=Qt.AlignLeft))

        lay.addWidget(_hdiv())

        # ── LCD launch delay note (LCD users only) ────────────────────────────
        self._lcd_div = _hdiv()
        self._lcd_hdr = _lbl("⚠  LCD Steam Deck - Important Notes", 13, C_TREY, bold=True, align=Qt.AlignLeft)
        self._lcd_body = _lbl(
            "• Launch delay: Plutonium games on LCD may take a moment to launch. "
            "A cleanup script runs before each launch to clear the shader cache. "
            "If the game doesn't start right away, please be patient or try launching again.\n\n"
            "• Vulkan shaders: If Steam tries to compile Vulkan shaders before launching, "
            "skip it — these shaders are not used by LCD Plutonium games and just waste time.\n\n"
            "• Closing games: When you're done playing, quit from the in-game menu instead of "
            "using the Steam overlay. Closing through Steam can be slow and buggy on LCD "
            "(it won't break anything, but quitting in-game is much faster).",
            11, C_DIM, align=Qt.AlignLeft)
        lay.addWidget(self._lcd_div)
        lay.addWidget(self._lcd_hdr)
        lay.addWidget(self._lcd_body)

        lay.addWidget(_hdiv())

        # ── Controller Profiles & GE-Proton ───────────────────────────────────
        lay.addWidget(_lbl("🎮  Controller Profiles & GE-Proton", 13, C_IW, bold=True, align=Qt.AlignLeft))
        # gyro_desc is set dynamically in showEvent so it always reflects the
        # user's actual choice, not whatever was in config at construction time.
        self._gyro_lbl = _lbl("", 11, C_DIM, align=Qt.AlignLeft)
        lay.addWidget(self._gyro_lbl)
        lay.addWidget(_lbl(
            "Newest GE-Proton installed and set for all games. "
            "Change Hold, ADS, or Toggle anytime in Settings — Re-apply Controller Profiles.",
            11, "#666", align=Qt.AlignLeft))

        # ── Decky Loader note (docked users only) ─────────────────────────────
        self._decky_div  = _hdiv()
        self._decky_hdr  = _lbl("🖥  Enable Docked Display Switching", 13, C_IW, bold=True, align=Qt.AlignLeft)
        self._decky_body = _lbl(
            "The DeckOps Decky plugin automatically switches your display settings when you "
            "connect or disconnect a monitor. Decky Loader is required to use it.",
            11, C_DIM, align=Qt.AlignLeft)
        self._decky_btn  = _btn("Get Decky Loader  →  decky.xyz", C_BLUE_BTN, size=12, h=40)
        self._decky_btn.setFixedWidth(320)
        self._decky_btn.clicked.connect(lambda: _detached_open(
            ["xdg-open", "https://decky.xyz/"]
        ))
        dbw = QHBoxLayout(); dbw.addWidget(self._decky_btn); dbw.addStretch()
        lay.addWidget(self._decky_div)
        lay.addWidget(self._decky_hdr)
        lay.addWidget(self._decky_body)
        lay.addLayout(dbw)

        lay.addStretch()
        lay.addSpacing(4)

        self._safe_lbl = _lbl("✅  It is now safe to open Steam.", 13, C_IW, bold=True)
        self._safe_lbl.setVisible(False)
        lay.addWidget(self._safe_lbl)
        lay.addSpacing(4)

        cont = _btn("Continue  >>", C_IW, h=52)
        cont.clicked.connect(self._go_management)
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(cont, stretch=1); cw.addStretch()
        lay.addLayout(cw)

    def showEvent(self, e):
        super().showEvent(e)
        self._safe_lbl.setVisible(True)
        gyro_mode = cfg.get_gyro_mode() or "on"
        _GYRO_DESCS = {
            "on": "gyro on ADS",
            "hold": "gyro on hold",
            "toggle": "gyro on toggle",
            "off": "gyro off",
        }
        gyro_desc = _GYRO_DESCS.get(gyro_mode, "gyro off")
        self._gyro_lbl.setText(
            f"Standard gamepad layout with {gyro_desc} assigned to all games. "
        )
        # Only show the Decky section for docked users
        is_docked = cfg.is_docked()
        self._decky_div.setVisible(is_docked)
        self._decky_hdr.setVisible(is_docked)
        self._decky_body.setVisible(is_docked)
        self._decky_btn.setVisible(is_docked)
        # Only show the LCD launch delay note for LCD users
        is_lcd = cfg.is_lcd()
        self._lcd_div.setVisible(is_lcd)
        self._lcd_hdr.setVisible(is_lcd)
        self._lcd_body.setVisible(is_lcd)

    def _go_management(self):
        root = find_steam_root()
        get_screen(self.stack, "ManagementScreen").set_installed(find_installed_games(parse_library_folders(root)))
        go_to(self.stack, "ManagementScreen")


# ── ConfigureScreen ───────────────────────────────────────────────────────────
class ConfigureScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.screen_name = "ConfigureScreen"
        lay = QVBoxLayout(self); lay.setContentsMargins(60,40,60,40); lay.setSpacing(14)
        t = QLabel("SETTINGS"); t.setFont(font(36,True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;"); lay.addWidget(t)
        lay.addWidget(_hdiv())

        # ── Background Music ──────────────────────────────────────────────
        lay.addWidget(_lbl("Background Music", 14, "#CCC", align=Qt.AlignLeft))
        mr = QHBoxLayout(); mr.setSpacing(12)
        self._music_on = _music_enabled
        self._music_toggle = _btn(
            "Music: ON" if self._music_on else "Music: OFF",
            C_IW if self._music_on else C_DARK_BTN,
            size=12, h=40,
        )
        self._music_toggle.setFixedWidth(160)
        self._music_toggle.clicked.connect(self._toggle_music)
        self._vol_slider = QSlider(Qt.Horizontal); self._vol_slider.setRange(0,100)
        self._vol_slider.setValue(int(_music_volume*100))
        self._vol_label = _lbl(f"{int(_music_volume*100)}%", 12, C_DIM, wrap=False)
        self._vol_label.setFixedWidth(40)
        self._vol_slider.valueChanged.connect(self._set_volume)
        mr.addWidget(self._music_toggle); mr.addWidget(self._vol_slider,stretch=1); mr.addWidget(self._vol_label)
        lay.addLayout(mr)
        lay.addWidget(_hdiv())

        # ── Controller Profiles ───────────────────────────────────────────
        lay.addWidget(_lbl("Controller Profiles", 14, "#CCC", align=Qt.AlignLeft))
        gr = QHBoxLayout(); gr.setSpacing(8)
        gr.addWidget(_lbl("Gyro:", 12, "#AAA", wrap=False))
        self._gyro_btns = {}
        # SD LCD/OLED get 4 modes; others get 2. Hold/toggle hidden dynamically in showEvent.
        for mode in ("on", "hold", "toggle", "off"):
            labels = {"on": "ADS", "hold": "Hold", "toggle": "Toggle", "off": "Gyro Off"}
            b = _btn(labels[mode], C_DARK_BTN, size=11, h=36)
            b.setFixedWidth(90)
            b.clicked.connect(lambda checked, m=mode: self._set_gyro(m))
            gr.addWidget(b)
            self._gyro_btns[mode] = b
        gr.addSpacing(16)
        ctrl_btn = _btn("Re-apply Templates", C_DARK_BTN, size=12, h=36)
        ctrl_btn.clicked.connect(self._apply_controller_profiles)
        gr.addWidget(ctrl_btn)
        gr.addStretch()
        lay.addLayout(gr)
        lay.addWidget(_hdiv())

        # ── Player Name ───────────────────────────────────────────────────
        lay.addWidget(_lbl("Player Name", 14, "#CCC", align=Qt.AlignLeft))
        nr = QHBoxLayout(); nr.setSpacing(12)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Enter player name...")
        self._name_input.setFixedHeight(36)
        self._name_input.setMaxLength(32)
        self._name_input.setStyleSheet(
            "QLineEdit{background:#2A2A3A;color:#FFF;border:1px solid #444;"
            "border-radius:6px;padding:0 10px;font-size:13px;}"
            "QLineEdit:focus{border:1px solid #888;}"
        )
        save_btn = _btn("Save", C_IW, size=12, h=36)
        save_btn.setFixedWidth(80)
        save_btn.clicked.connect(self._save_name)
        nr.addWidget(self._name_input, stretch=1); nr.addWidget(save_btn)
        lay.addLayout(nr)
        self._name_note = _lbl("Sets your name in CoD4x, IW4x, AlterWare (Ghosts, AW), T7X, and Plutonium offline. Does not affect Plutonium online or CleanOps (uses Steam name).", 10, C_DIM, align=Qt.AlignLeft)
        lay.addWidget(self._name_note)
        lay.addWidget(_hdiv())

        # ── Shader Cache (LCD only) ───────────────────────────────────────
        self._shader_row = QWidget()
        sr_lay = QVBoxLayout(self._shader_row); sr_lay.setContentsMargins(0,0,0,0); sr_lay.setSpacing(8)
        sr_lay.addWidget(_lbl("Shader Cache", 14, "#CCC", align=Qt.AlignLeft))
        sc_btn = _btn("Clear Shader Cache", C_DARK_BTN, size=12, h=36)
        sc_btn.setFixedWidth(220)
        sc_btn.clicked.connect(self._clear_shader_cache)
        sr_h = QHBoxLayout(); sr_h.addWidget(sc_btn); sr_h.addStretch()
        sr_lay.addLayout(sr_h)
        lay.addWidget(self._shader_row)
        self._shader_hdiv = _hdiv()
        lay.addWidget(self._shader_hdiv)

        # ── Links ─────────────────────────────────────────────────────────
        lay.addWidget(_lbl("Links", 14, "#CCC", align=Qt.AlignLeft))
        lr = QHBoxLayout(); lr.setSpacing(12)
        discord_btn = _btn("Discord", "#5865F2", size=12, h=36)
        discord_btn.setFixedWidth(100)
        discord_btn.clicked.connect(lambda: self._open_url("https://discord.gg/bkSQeq5Azk"))
        stable_btn = _btn("Stable", C_DARK_BTN, size=12, h=36)
        stable_btn.setFixedWidth(100)
        stable_btn.clicked.connect(lambda: self._open_url("https://github.com/GalvarinoDev/DeckOps"))
        nightly_btn = _btn("Nightly", C_DARK_BTN, size=12, h=36)
        nightly_btn.setFixedWidth(100)
        nightly_btn.clicked.connect(lambda: self._open_url("https://github.com/GalvarinoDev/DeckOps-Nightly"))
        lr.addWidget(discord_btn); lr.addWidget(stable_btn); lr.addWidget(nightly_btn); lr.addStretch()
        lay.addLayout(lr)
        lay.addWidget(_hdiv())

        # ── Danger Zone ──────────────────────────────────────────────────
        lay.addWidget(_lbl("Danger Zone", 14, C_TREY, align=Qt.AlignLeft))
        dr = QHBoxLayout(); dr.setSpacing(12)
        uninstall_btn = _btn("Full Uninstall", C_RED_BTN, size=12, h=40)
        reset_cfg_btn = _btn("Reset DeckOps Config", C_RED_BTN, size=12, h=40)
        uninstall_btn.clicked.connect(self._confirm_uninstall)
        reset_cfg_btn.clicked.connect(self._confirm_reset)
        dr.addWidget(uninstall_btn); dr.addWidget(reset_cfg_btn); dr.addStretch()
        lay.addLayout(dr)
        lay.addWidget(_hdiv())

        # ── About ─────────────────────────────────────────────────────────
        self._about_label = _lbl("", 11, C_DIM, align=Qt.AlignLeft)
        lay.addWidget(self._about_label)

        lay.addStretch()
        self.status = _lbl("", 12, C_DIM)
        lay.addWidget(self.status)
        back = _btn("<< Back", C_DARK_BTN, h=48); back.setFixedWidth(160)
        back.clicked.connect(lambda: go_to(self.stack, "ManagementScreen"))
        bw = QHBoxLayout(); bw.addWidget(back); bw.addStretch()
        lay.addLayout(bw)

    def showEvent(self, event):
        super().showEvent(event)
        # Refresh dynamic state
        model = cfg.get_deck_model() or "unknown"
        source = cfg.get_game_source() or "steam"
        source_label = "Steam" if source == "steam" else "Steam & Non-Steam"
        player = cfg.get_player_name() or "Player"
        self._name_input.setText(player if player != "Player" else "")

        # Show hold/toggle only for Steam Deck LCD/OLED
        is_sd = model in ("lcd", "oled")
        self._gyro_btns["hold"].setVisible(is_sd)
        self._gyro_btns["toggle"].setVisible(is_sd)
        # Relabel ADS button for non-SD devices
        self._gyro_btns["on"].setText("ADS" if is_sd else "Gyro On")

        # Gyro highlight
        gyro = cfg.get_gyro_mode() or "on"
        # If non-SD device has hold/toggle saved, treat as "on" for highlight
        if not is_sd and gyro in ("hold", "toggle"):
            gyro = "on"
        for mode, btn in self._gyro_btns.items():
            if mode == gyro:
                btn.setStyleSheet(btn.styleSheet().replace(C_DARK_BTN, C_IW))
            else:
                btn.setStyleSheet(btn.styleSheet().replace(C_IW, C_DARK_BTN))

        # LCD-only shader cache section
        is_lcd = (model == "lcd")
        self._shader_row.setVisible(is_lcd)
        self._shader_hdiv.setVisible(is_lcd)

        # Build info
        build = "dev"
        build_path = os.path.join(PROJECT_ROOT, "BUILD")
        if os.path.exists(build_path):
            try:
                with open(build_path, "r") as f:
                    build = f.read().strip() or "dev"
            except Exception:
                pass

        # Device display name for about label
        if model == "other":
            other_dev = cfg.get_other_device() or "unknown"
            _DEVICE_NAMES = {
                "1920x1200": "Other (1920×1200)",
                "1920x1200_144hz": "Other (1920×1200 144Hz)",
                "1920x1080": "Other (1920×1080)",
                "1280x720": "Other (1280×720)",
            }
            device_display = _DEVICE_NAMES.get(other_dev, f"Other ({other_dev})")
        else:
            device_display = f"Steam Deck {model.upper()}"

        self._about_label.setText(
            f"Device: {device_display}  |  Source: {source_label}  |  "
            f"Player: {player}\n"
            f"Build: {build}"
        )

    def _toggle_music(self):
        self._music_on = not self._music_on
        _set_audio_enabled(self._music_on)
        if self._music_on:
            _start_audio()
            self._music_toggle.setText("Music: ON")
            self._music_toggle.setStyleSheet(
                self._music_toggle.styleSheet().replace(C_DARK_BTN, C_IW))
        else:
            _kill_audio()
            self._music_toggle.setText("Music: OFF")
            self._music_toggle.setStyleSheet(
                self._music_toggle.styleSheet().replace(C_IW, C_DARK_BTN))

    def _set_volume(self, val):
        self._vol_label.setText(f"{val}%")
        _set_audio_volume(val / 100.0)

    def _set_gyro(self, mode):
        cfg.set_gyro_mode(mode)
        # Update button highlights
        for m, btn in self._gyro_btns.items():
            if m == mode:
                btn.setStyleSheet(btn.styleSheet().replace(C_DARK_BTN, C_IW))
            else:
                btn.setStyleSheet(btn.styleSheet().replace(C_IW, C_DARK_BTN))
        self.status.setText(f"Gyro mode set to {mode.upper()}. Hit Re-apply Templates to update controller profiles.")

    def _apply_controller_profiles(self):
        self.status.setText("Re-applying controller profiles...")
        s = _Sigs()
        s.log.connect(lambda msg: self.status.setText(msg))
        s.done.connect(lambda ok: self.status.setText(
            "✓  Controller profiles applied." if ok else "✗  Failed — check that Steam is closed."
        ))
        def _run():
            try:
                from controller_profiles import install_controller_templates, assign_controller_profiles, assign_external_controller_profiles
                from wrapper import kill_steam, set_steam_input_enabled
                s.log.emit("Closing Steam...")
                kill_steam()
                install_controller_templates(
                    on_progress=lambda msg: s.log.emit(msg)
                )
                gyro_mode = cfg.get_gyro_mode() or "on"
                assign_controller_profiles(
                    gyro_mode,
                    on_progress=lambda msg: s.log.emit(msg)
                )
                if cfg.is_docked():
                    controller_type = cfg.get_external_controller() or "playstation"
                    assign_external_controller_profiles(
                        controller_type,
                        gyro_mode,
                        on_progress=lambda msg: s.log.emit(msg)
                    )
                sr = cfg.load().get("steam_root", "")
                if sr:
                    set_steam_input_enabled(sr)
                s.done.emit(True)
                s.log.emit("✓  Controller profiles applied. It is now safe to reopen Steam.")
            except Exception as ex:
                s.log.emit(f"✗  Failed: {ex}")
                s.done.emit(False)
        threading.Thread(target=_run, daemon=True).start()

    def _save_name(self):
        name = self._name_input.text().strip()
        if not name:
            self.status.setText("Please enter a name.")
            return
        cfg.set_player_name(name)
        self.status.setText(f"Updating player name to \"{name}\"...")
        s = _Sigs()
        s.log.connect(lambda msg: self.status.setText(msg))
        def _run():
            try:
                from game_config import rename_player
                from detect_games import find_installed_games, parse_library_folders
                steam_root = cfg.load().get("steam_root", "") or find_steam_root()
                installed = {}
                if steam_root:
                    installed = find_installed_games(parse_library_folders(steam_root))
                count = rename_player(
                    name, steam_root, installed_games=installed,
                    on_progress=lambda msg: s.log.emit(msg),
                )
                s.log.emit(f"✓  Player name set to \"{name}\" ({count} config(s) updated).")
            except Exception as ex:
                s.log.emit(f"✗  Failed: {ex}")
        threading.Thread(target=_run, daemon=True).start()

    def _clear_shader_cache(self):
        self.status.setText("Clearing shader cache...")
        s = _Sigs()
        s.log.connect(lambda msg: self.status.setText(msg))
        def _run():
            try:
                from cache_cleanup import cleanup_shader_cache, STEAM_APPIDS
                setup = cfg.get_setup_games()
                cleared = 0
                for key in STEAM_APPIDS:
                    if key in setup:
                        source = setup[key].get("source", "steam")
                        cleanup_shader_cache(key, source)
                        cleared += 1
                s.log.emit(f"✓  Shader cache cleared for {cleared} game(s).")
            except Exception as ex:
                s.log.emit(f"✗  Failed: {ex}")
        threading.Thread(target=_run, daemon=True).start()

    def _open_url(self, url):
        _detached_open(["xdg-open", url])

    def _confirm_uninstall(self):
        reply = QMessageBox.warning(
            self, "Full Uninstall",
            "This will remove all DeckOps files, shortcuts, controller profiles, "
            "and mod client installations. Your Steam games will NOT be deleted.\n\n"
            "DeckOps will close and the uninstaller will run in a terminal window.\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_uninstaller()

    def _run_uninstaller(self):
        uninstall_script = os.path.join(PROJECT_ROOT, "deckops_uninstall.sh")
        if not os.path.exists(uninstall_script):
            self.status.setText("✗  Uninstall script not found.")
            return
        self.status.setText("Launching uninstaller...")
        try:
            # Launch in Konsole so the user can see progress
            subprocess.Popen(
                ["konsole", "-e", "bash", uninstall_script],
                start_new_session=True,
            )
            # Close DeckOps — the uninstaller will remove our files
            _kill_audio()
            QApplication.instance().quit()
        except Exception:
            # Konsole not available (shouldn't happen on SteamOS)
            try:
                subprocess.Popen(
                    ["xterm", "-e", "bash", uninstall_script],
                    start_new_session=True,
                )
                _kill_audio()
                QApplication.instance().quit()
            except Exception as ex:
                self.status.setText(f"✗  Could not launch uninstaller: {ex}")

    def _confirm_reset(self):
        reply = QMessageBox.warning(
            self, "Reset Config",
            "This will wipe the DeckOps configuration file (deckops.json). "
            "DeckOps will restart and run the setup flow again.\n\n"
            "Your game files and Steam games are not affected.\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._reset_deckops()

    def _reset_deckops(self):
        cfg.reset()
        self.status.setText("Config wiped. Restarting setup...")
        QTimer.singleShot(1500, lambda: go_to(self.stack, "BootstrapScreen"))



# ── UpdateScreen ──────────────────────────────────────────────────────────────
class UpdateScreen(QWidget):
    """Handles Update from ManagementScreen."""

    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "UpdateScreen"
        self.selected   = []
        self.steam_root = ""
        self._steam_closed = threading.Event()

        lay = QVBoxLayout(self); lay.setContentsMargins(80,60,80,60); lay.setSpacing(20)
        self.title = QLabel("UPDATE"); self.title.setFont(font(36, True))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color:#FFF;background:transparent;")
        lay.addWidget(self.title)

        self.cur = _lbl("Preparing...", 16, "#CCC"); lay.addWidget(self.cur)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(22)
        bw = QHBoxLayout(); bw.setContentsMargins(60,0,60,0); bw.addWidget(self.bar)
        lay.addLayout(bw)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(font(11))
        self.log.setStyleSheet("QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}")
        lay.addWidget(self.log, stretch=1)

        self.steam_btn = _btn("Steam is closed  ✓", C_TREY, size=13, h=52)
        self.steam_btn.setFixedWidth(360); self.steam_btn.setVisible(False)
        self.steam_btn.clicked.connect(lambda: self._steam_closed.set())
        sw = QHBoxLayout(); sw.addStretch(); sw.addWidget(self.steam_btn); sw.addStretch()
        lay.addLayout(sw)

        self.back_btn = _btn("<< Back to My Games", C_DARK_BTN, h=48)
        self.back_btn.setFixedWidth(220); self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self._go_back)
        bk = QHBoxLayout(); bk.addStretch(); bk.addWidget(self.back_btn); bk.addStretch()
        lay.addLayout(bk)

        self._s = _Sigs()
        self._s.progress.connect(lambda p,m: (self.bar.setValue(p), self.cur.setText(m)))
        self._s.log.connect(self._append_log)
        self._s.done.connect(self._on_done)
        self._s.plut_wait.connect(lambda: self.steam_btn.setVisible(True))
        self._s.plut_go.connect(lambda: self.steam_btn.setVisible(False))

    def _append_log(self, text):
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        _log_to_file(text)

    def showEvent(self, e):
        super().showEvent(e)
        self.bar.setValue(0); self.log.clear()
        self.steam_btn.setVisible(False); self.back_btn.setVisible(False)
        self._steam_closed.clear()
        _log_to_file("── Update started ──")
        QTimer.singleShot(400, lambda: threading.Thread(target=self._run, daemon=True).start())

    def _on_done(self, _):
        self.cur.setText("Done! It is now safe to open Steam.")
        self.back_btn.setVisible(True)

    def _go_back(self):
        root = find_steam_root()
        get_screen(self.stack, "ManagementScreen").set_installed(find_installed_games(parse_library_folders(root)))
        go_to(self.stack, "ManagementScreen")

    def _run(self):
        from wrapper import get_proton_path, find_compatdata, kill_steam
        from iw4x import install_iw4x
        from cod4x import install_cod4x
        from iw3sp import install_iw3sp
        from t6sp_mod import install_t6sp_mod
        from cleanops import install_cleanops
        from t7x import install_t7x
        from plutonium_oled import install_plutonium

        has_cod4  = any(KEY_CLIENT.get(k) in ("cod4x", "iw3sp") for k, _, _ in self.selected)
        has_iw4x  = any(KEY_CLIENT.get(k) == "iw4x" for k, _, _ in self.selected)
        has_plut  = any(KEY_CLIENT.get(k) == "plutonium" for k, _, _ in self.selected)
        proton    = get_proton_path(self.steam_root)
        total     = len(self.selected)

        # Read setup_games to determine source for each key
        setup_games = cfg.get_setup_games()

        if not has_plut:
            self._s.progress.emit(5, "Closing Steam...")
            self._s.log.emit("Closing Steam...")
            try:
                kill_steam()
                self._s.log.emit("  ✓ Steam closed.")
            except Exception as ex:
                self._s.log.emit(f"  Could not close Steam: {ex}")

        # ── Clean slate: clear launch options and compat tools ─────────
        # Same clean-slate approach as InstallScreen / OwnInstallScreen.
        # Prevents stale entries from previous installs (LCD→OLED, older
        # DeckOps versions) interfering with the update.
        try:
            from wrapper import clear_launch_options, clear_compat_tool
            from ge_proton import MANAGED_APPIDS
            for appid in MANAGED_APPIDS:
                clear_launch_options(self.steam_root, appid)
            clear_compat_tool(MANAGED_APPIDS)
            self._s.log.emit("✓  Cleared all launch options and compat tools")
        except Exception as ex:
            self._s.log.emit(f"  Launch option / compat tool cleanup skipped: {ex}")

        # Build installed_games dict for Plutonium sibling key resolution
        installed_for_plut = {k: g for k, _, g in self.selected if g}

        for idx, (key, gd, game) in enumerate(self.selected):
            if not game:
                continue
            base_name = gd["base"]
            bp = int(idx / total * 90)
            self._s.progress.emit(bp, f"Updating {base_name}...")
            def op(pct, msg, _b=bp): self._s.progress.emit(_b + int(pct / 100 * (90 // total)), msg)
            c = KEY_CLIENT.get(key, gd.get("client", ""))

            # Determine source from setup_games config entry
            entry = setup_games.get(key, {})
            source = entry.get("source", "steam")

            try:
                from plutonium_oled import GAME_META as _PLUT_META
                from detect_games import GAMES as _GAMES_MAP
                if c == "plutonium" and key in _PLUT_META:
                    _appid = _PLUT_META[key][0]
                elif c == "alterware" and key in _GAMES_MAP:
                    _appid = _GAMES_MAP[key]["appid"]
                else:
                    _appid = gd["appid"]

                # Resolve compatdata - own games may have CRC-based prefix
                if source == "own":
                    compat = game.get("compatdata_path", "")
                    if not compat:
                        compat = find_compatdata(self.steam_root, _appid,
                                                  game_install_dir=game.get("install_dir"))
                else:
                    compat = find_compatdata(self.steam_root, _appid,
                                              game_install_dir=game.get("install_dir"))
                if not compat and game.get("install_dir"):
                    steamapps = os.path.dirname(os.path.dirname(game["install_dir"]))
                    compat = os.path.join(steamapps, "compatdata", str(_appid))

                if c == "cod4x":
                    install_cod4x(game, self.steam_root, proton, compat, op,
                                  appid=gd["appid"])
                elif c == "iw3sp":
                    install_iw3sp(game, self.steam_root, proton, compat, op,
                                  source=source)
                elif c == "iw4x":
                    install_iw4x(game, self.steam_root, proton, compat, op,
                                 source=source, install_dlc=False)
                elif c == "plutonium":
                    install_plutonium(game, key, self.steam_root, proton, compat,
                                     on_progress=op,
                                     installed_games=installed_for_plut,
                                     source=source)
                elif c == "cleanops":
                    install_cleanops(game, self.steam_root, proton, compat, op,
                                    source=source)
                elif c == "t7x":
                    t7x_dir = install_t7x(game, on_progress=op)
                    game["install_dir"] = t7x_dir
                elif c == "alterware":
                    from alterware import install_alterware
                    install_alterware(game, key, self.steam_root, proton, compat, op,
                                     source=source)
                elif c == "t6sp_mod":
                    install_t6sp_mod(game, self.steam_root, proton, compat, op,
                                    source=source)
                self._s.log.emit(f"✓  {base_name} ({key}) done")
            except Exception as ex:
                self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        self._s.progress.emit(100, "All done!")
        self._s.done.emit(True)
