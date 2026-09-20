"""
ui_install.py — Install pipeline screens for DeckOps

Screens: WelcomeScreen, SetupScreen, InstallScreen
Extracted from ui_qt.py — all hardcoded stack indices replaced with named lookups.
"""

import html, os, subprocess, threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QCheckBox, QProgressBar, QPushButton, QButtonGroup,
    QPlainTextEdit, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QStorageInfo, QUrl

from detect_games import find_steam_root, find_all_games
import config as cfg
from net import DownloadError

from ui_constants import (
    C_BG, C_CARD, C_IW, C_TREY, C_DIM, C_DARK_BTN, C_BLUE_BTN,
    font, _btn, _lbl, _title_block, _header_bar, _badge, _log_to_file, _copy_log_to_clipboard, _Sigs,
    ALL_GAMES, KEY_CLIENT, KEY_EXES, KEY_MODE_LABEL,
    _active_keys, _active_client, _active_appid,
    _ask_bo3_client,
    go_to, get_screen,
)


# ── WelcomeScreen ─────────────────────────────────────────────────────────────
class WelcomeScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.installed={}; self.screen_name = "WelcomeScreen"
        self.steam_installed={}; self.own_installed={}; self.steam_root=""
        lay = QVBoxLayout(self); lay.setContentsMargins(60,30,60,30); lay.setSpacing(12)
        # Smaller title than other screens: the results + notice need the vertical room at 800px
        _title_block(lay, main_size=40)
        lay.addSpacing(6)
        self.status = _lbl("Scanning for games...", 14, C_DIM)
        lay.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(14)
        bw = QHBoxLayout(); bw.addStretch(); bw.addWidget(self.bar,6); bw.addStretch()
        lay.addLayout(bw)
        lay.addSpacing(10)
        self.results = _lbl("", 13, C_IW)
        self.results.setTextFormat(Qt.RichText)
        self.notice = _lbl(
            "Before you continue:\n"
            "•  Downgrading a game (MW3, Ghosts, AW) can take a very long time and needs "
            "at least that game's full size free on the drive during the install.\n"
            "•  On a handheld, plug it in. In Desktop Mode, click the battery icon and turn on "
            "\"Manually block sleep and screen locking\" so it doesn't fall asleep mid-install.\n"
            "•  Use a good, stable internet connection.\n"
            "•  Keep your device somewhere it can breathe. Don't leave it on a blanket or "
            "anywhere it could overheat.",
            12, C_TREY, align=Qt.AlignLeft)
        self.notice.setStyleSheet(
            f"color:{C_TREY};background:#2A1A08;border:1px solid {C_TREY};"
            "border-radius:8px;padding:10px 16px;")
        self.notice.setVisible(False)
        # Games list and notice side by side so neither gets squeezed
        mid = QHBoxLayout(); mid.setSpacing(30)
        mid.addWidget(self.results, 1, Qt.AlignTop)
        mid.addWidget(self.notice, 1, Qt.AlignTop)
        lay.addLayout(mid)
        lay.addStretch()
        self._scanning = False
        self.back = _btn("<< Back", C_DARK_BTN, h=52); self.back.setFixedWidth(180)
        self.back.clicked.connect(self._go_back)
        self.retry = _btn("Scan Again", C_DARK_BTN, h=52); self.retry.setFixedWidth(200)
        self.retry.clicked.connect(self._start_scan)
        self.cont = _btn("Continue >>", C_IW, h=52)
        self.cont.setFixedWidth(260); self.cont.setVisible(False)
        self.cont.clicked.connect(self._go_next)
        cw = QHBoxLayout(); cw.setSpacing(16); cw.addStretch()
        cw.addWidget(self.back); cw.addWidget(self.retry); cw.addWidget(self.cont); cw.addStretch()
        lay.addLayout(cw)

    def showEvent(self, e):
        super().showEvent(e)
        self._start_scan()

    def _go_back(self):
        go_to(self.stack, "SetupFlowScreen" if cfg.is_first_run() else "ManagementScreen")

    def _start_scan(self):
        if self._scanning: return
        self._scanning = True
        self.bar.setValue(20); self.results.setText(""); self.notice.setVisible(False)
        self.cont.setVisible(False); self.retry.setVisible(False); self.back.setVisible(False)
        self.status.setText("Scanning for Steam and games...")
        self.status.setStyleSheet(f"color:{C_DIM};background:transparent;")
        self._s = _Sigs()
        self._s.done.connect(self._on_scanned)
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        root, merged = "", {}
        try:
            root = find_steam_root() or ""
            if root: merged = find_all_games(root)
        except Exception as ex:
            _log_to_file(f"[WelcomeScreen] scan failed: {ex}")
        self.steam_root, self._merged = root, merged
        self._s.done.emit(bool(root))

    def _on_scanned(self, steam_found):
        self._scanning = False
        self.back.setVisible(True)
        if not steam_found:
            self.bar.setValue(100); self.retry.setVisible(True)
            self.status.setText("Steam not found. Install Steam and open it once, then scan again.")
            self.status.setStyleSheet(f"color:{C_TREY};background:transparent;")
            return
        self.bar.setValue(70)
        merged = self._merged
        self.steam_installed = {k: v for k, v in merged.items() if v.get("source") != "own"}
        self.own_installed = {k: v for k, v in merged.items() if v.get("source") == "own"}
        self.installed = merged
        if cfg.is_lcd():
            lcd_allowed = set()
            for g in ALL_GAMES:
                lcd_allowed.update(g.get("lcd_keys", g["keys"]))
            self.installed = {k:v for k,v in self.installed.items() if k in lcd_allowed}
            self.steam_installed = {k:v for k,v in self.steam_installed.items() if k in lcd_allowed}
            self.own_installed = {k:v for k,v in self.own_installed.items() if k in lcd_allowed}
        self._show_results()

    def _show_results(self):
        self.bar.setValue(100)
        self.cont.setText("Continue >>")
        if not self.installed:
            self.retry.setVisible(True)
            self.status.setStyleSheet(f"color:{C_TREY};background:transparent;")
            if cfg.is_first_run():
                self.status.setText(
                    "No supported games found. If your games are in a custom folder, "
                    "continue and use Choose Folder.")
                self.cont.setText("Choose Folder >>"); self.cont.setVisible(True)
            else:
                self.status.setText("No supported games found.")
            return
        unique = len({g["name"].split(" - ")[0].split(" (")[0] for g in self.installed.values()})
        self.status.setText(f"Found {unique} supported game(s)!")
        self.status.setStyleSheet(f"color:{C_IW};background:transparent;")
        lines = []
        seen_steam = set()
        for g in sorted(self.steam_installed.values(), key=lambda x: x.get("order",99)):
            base = g["name"].split(" - ")[0].split(" (")[0]
            if base not in seen_steam:
                seen_steam.add(base)
                lines.append(f'<span style="color:{C_IW}">{base} (Steam)</span>')
        seen_own = set()
        for g in sorted(self.own_installed.values(), key=lambda x: x.get("order",99)):
            base = g["name"].split(" - ")[0].split(" (")[0]
            if base not in seen_own:
                seen_own.add(base)
                lines.append(f'<span style="color:{C_TREY}">{base} (Non-Steam)</span>')
        self.results.setText("<br>".join(lines)); self.cont.setVisible(True)
        self.notice.setVisible(cfg.is_first_run())

    def _go_next(self):
        if cfg.is_first_run():
            s = get_screen(self.stack, "SetupScreen")
            s.steam_installed = self.steam_installed
            s.own_installed   = self.own_installed
            s.steam_root      = self.steam_root
            go_to(self.stack, "SetupScreen")
        else:
            get_screen(self.stack, "ManagementScreen").set_installed(self.installed)
            go_to(self.stack, "ManagementScreen")


# ── SetupScreen ───────────────────────────────────────────────────────────────
class SetupScreen(QWidget):
    """
    Unified game selection. Shows Steam and non-Steam games in one list.
    """
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.screen_name = "SetupScreen"
        self.steam_installed={}; self.own_installed={}; self.steam_root=""
        self._checks={}
        self._extra_paths = []
        self._cod4_choice = "cod4r"
        self._iw4x_dlc_cb = None; self._iw4x_dlc_present = False
        self._zd_cb = None

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        lay.addWidget(_header_bar()[0])

        # ── Content area ───────────────────────────────────────────────
        content = QWidget()
        clay = QVBoxLayout(content); clay.setContentsMargins(60,20,60,40); clay.setSpacing(14)
        clay.addWidget(_lbl(
            "Choose which games to set up. "
            "DeckOps will create Proton prefixes automatically.", 13, C_DIM))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        # Two columns (IW/SHG | Treyarch) so the whole list fits at 1280x800 without scrolling
        self._lw = QWidget(); cols = QHBoxLayout(self._lw)
        cols.setContentsMargins(0,0,0,0); cols.setSpacing(24)
        self._cols = {}
        for dev, title, color in (("iw", "INFINITY WARD / SLEDGEHAMMER", C_IW), ("trey", "TREYARCH", C_TREY)):
            col = QVBoxLayout(); col.setSpacing(0)
            col.addWidget(_lbl(title, 11, color, bold=True, align=Qt.AlignLeft, wrap=False))
            col.addStretch()
            cols.addLayout(col, 1); self._cols[dev] = col
        scroll.setWidget(self._lw); clay.addWidget(scroll, stretch=1)

        self.warning = _lbl("", 12, C_TREY, align=Qt.AlignLeft)
        self.warning.setVisible(False); clay.addWidget(self.warning)
        brow = QHBoxLayout(); brow.setSpacing(16)
        back = _btn("<< Back", C_DARK_BTN, h=52); back.setFixedWidth(180)
        back.clicked.connect(lambda: go_to(self.stack, "WelcomeScreen"))
        self._folder_btn = _btn("Choose Folder", C_DARK_BTN, h=52)
        self._folder_btn.setFixedWidth(200)
        self._folder_btn.clicked.connect(self._pick_folder)
        self.inst_btn = _btn("Install Selected >>", C_IW, h=52)
        self.inst_btn.clicked.connect(self._go_install)
        brow.addWidget(back); brow.addWidget(self._folder_btn)
        brow.addWidget(self.inst_btn, stretch=1); clay.addLayout(brow)
        lay.addWidget(content, stretch=1)

    def showEvent(self, e):
        super().showEvent(e)
        self.warning.setVisible(False)
        self._build()

    def _add_row(self, gd, widget):
        col = self._cols["iw" if gd["dev"] == "iw" else "trey"]
        col.insertWidget(col.count() - 1, widget)

    @staticmethod
    def _short_name(base):
        return base.replace("Call of Duty 4: ", "CoD4: ").replace("Call of Duty: ", "")

    def _build(self):
        for col in self._cols.values():
            # keep the column title (first) and trailing stretch (last)
            while col.count() > 2:
                item = col.takeAt(1)
                if item.widget(): item.widget().deleteLater()
        self._checks.clear()
        self._iw4x_dlc_cb = None; self._iw4x_dlc_present = False
        self._zd_cb = None

        MAX_SLOTS  = 3
        SLOT_W     = 28
        SLOT_GAP   = 8
        CHECKS_W   = MAX_SLOTS * SLOT_W + (MAX_SLOTS - 1) * SLOT_GAP

        all_installed = {**self.steam_installed, **self.own_installed}

        for gd in ALL_GAMES:
            keys = _active_keys(gd)
            if not keys: continue
            ik = [k for k in keys if k in all_installed]
            if "iw5mp" in ik and "iw5mp_ds" in ik:
                ik = [k for k in ik if k != "iw5mp_ds"]
                keys = [k for k in keys if k != "iw5mp_ds"]
            if not ik:
                _iw5_keys = {"iw5mp", "iw5mp_ds"}
                if _iw5_keys.intersection(keys) and not _iw5_keys.intersection(all_installed):
                    self._add_mw3_free_row(gd, CHECKS_W)
                continue

            color  = C_IW if gd["dev"] == "iw" else C_TREY
            client = _active_client(gd)

            cw = QWidget()
            outer = QVBoxLayout(cw); outer.setContentsMargins(6, 6, 6, 6); outer.setSpacing(4)
            row = QHBoxLayout(); row.setSpacing(10)

            checks_widget = QWidget()
            checks_widget.setFixedWidth(CHECKS_W)
            checks_layout = QHBoxLayout(checks_widget)
            checks_layout.setContentsMargins(0, 0, 0, 0)
            checks_layout.setSpacing(SLOT_GAP)

            for key in keys:
                is_steam = key in self.steam_installed
                is_own   = key in self.own_installed
                installed = is_steam or is_own
                source = "own" if is_own and not is_steam else "steam"
                already_done = cfg.is_game_setup_for_source(key, source)

                slot = QWidget()
                slot.setFixedWidth(SLOT_W)
                slot_lay = QVBoxLayout(slot)
                slot_lay.setContentsMargins(0, 0, 0, 0)
                slot_lay.setSpacing(2)
                slot_lay.setAlignment(Qt.AlignHCenter)

                cb = QCheckBox()
                if not installed:
                    cb.setChecked(False); cb.setEnabled(False)
                elif already_done:
                    cb.setChecked(False)
                else:
                    cb.setChecked(True)

                mode_color = C_TREY if not installed else "#666677"
                mode_lbl = _lbl(KEY_MODE_LABEL.get(key, key), 10, mode_color,
                                 align=Qt.AlignHCenter, wrap=False)

                slot_lay.addWidget(cb, alignment=Qt.AlignHCenter)
                slot_lay.addWidget(mode_lbl)
                checks_layout.addWidget(slot)
                self._checks[key] = (cb, gd, source)

            for _ in range(MAX_SLOTS - len(keys)):
                spacer = QWidget()
                spacer.setFixedSize(SLOT_W, 38)
                spacer.setStyleSheet("background: transparent;")
                checks_layout.addWidget(spacer)

            row.addWidget(checks_widget)
            row.addWidget(_lbl(self._short_name(gd["base"]), 13, "#FFF", align=Qt.AlignLeft, wrap=False), stretch=1)

            row_has_own = any(k in self.own_installed and k not in self.steam_installed for k in ik)
            row_has_steam = any(k in self.steam_installed for k in ik)
            if row_has_own and row_has_steam:
                src_text, src_color = "BOTH", C_TREY
            elif row_has_own:
                src_text, src_color = "OWN", C_TREY
            else:
                src_text, src_color = "STEAM", C_IW
            row.addWidget(_badge(src_text, src_color, 58, h=24, size=9, radius=4))
            row.addWidget(_badge(client.upper(), color, 170, h=28, size=9))
            outer.addLayout(row)

            # Options sit under the row, indented past the checkbox column
            opts = QVBoxLayout(); opts.setContentsMargins(CHECKS_W + 10, 0, 0, 0); opts.setSpacing(4)
            self._row_options(opts, keys, all_installed)
            outer.addLayout(opts)
            self._add_row(gd, cw)

    def _row_options(self, lay, keys, all_installed):
        """Per-game install choices shown under the row while that mode is ticked (replaces pop-ups)."""
        def _bind(key, w):
            cb = self._checks.get(key, (None,))[0]
            w.setVisible(bool(cb and cb.isChecked()))
            if cb: cb.toggled.connect(w.setVisible)

        def _opt_box():
            w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
            return w, v

        if "cod4mp" in keys and "cod4mp" in all_installed:
            notes = {
                "cod4r": "Native controller support, server browser, bots and quality-of-life fixes. Built for handhelds.",
                "cod4x": "Established community client. No native controller support, so you'll set up controls manually.",
            }
            w, v = _opt_box()
            h = QHBoxLayout(); h.setSpacing(6)
            h.addWidget(_lbl("MP client:", 11, C_DIM, wrap=False))
            note = _lbl(notes[self._cod4_choice], 10, "#777788", align=Qt.AlignLeft)
            grp = QButtonGroup(w)
            for val, text in (("cod4r", "CoD4R (recommended)"), ("cod4x", "CoD4x")):
                b = QPushButton(text); b.setCheckable(True); b.setFont(font(10, True)); b.setFixedHeight(34)
                b.setStyleSheet(
                    f"QPushButton{{background:{C_DARK_BTN};color:#AAA;border:none;border-radius:6px;padding:0 12px;}}"
                    f"QPushButton:checked{{background:{C_IW};color:#FFF;}}")
                grp.addButton(b); b.setChecked(self._cod4_choice == val)
                b.toggled.connect(lambda on, v_=val: on and (setattr(self, "_cod4_choice", v_), note.setText(notes[v_])))
                h.addWidget(b)
            h.addStretch(); v.addLayout(h); v.addWidget(note)
            lay.addWidget(w); _bind("cod4mp", w)

        if "iw4mp" in keys and "iw4mp" in all_installed:
            w, v = _opt_box()
            from iw4x import is_iw4x_dlc_installed
            idir = all_installed["iw4mp"].get("install_dir", "")
            self._iw4x_dlc_present = bool(idir) and is_iw4x_dlc_installed(idir)
            if self._iw4x_dlc_present:
                v.addWidget(_lbl("Free IW4x DLC maps already installed.", 10, "#777788", align=Qt.AlignLeft))
            else:
                self._iw4x_dlc_cb = QCheckBox("Free DLC maps (~3 GB, recommended)")
                self._iw4x_dlc_cb.setFont(font(11)); self._iw4x_dlc_cb.setChecked(True)
                self._iw4x_dlc_cb.setStyleSheet("color:#CCC;background:transparent;")
                v.addWidget(self._iw4x_dlc_cb)
            lay.addWidget(w); _bind("iw4mp", w)

        if "t6zm" in keys and "t6zm" in all_installed and not cfg.is_zd_installed():
            from zombies_declassified import has_bo2_zm_dlc
            bdir = all_installed["t6zm"].get("install_dir", "")
            if bdir and has_bo2_zm_dlc(bdir):
                w, v = _opt_box()
                self._zd_cb = QCheckBox("Zombies Declassified: 10 classic maps (~9 GB)")
                self._zd_cb.setFont(font(11)); self._zd_cb.setChecked(False)
                self._zd_cb.setStyleSheet("color:#CCC;background:transparent;")
                v.addWidget(self._zd_cb)
                lay.addWidget(w); _bind("t6zm", w)

    def _add_mw3_free_row(self, gd, checks_w):
        cw = QWidget()
        row = QHBoxLayout(cw); row.setSpacing(10); row.setContentsMargins(6, 6, 6, 6)
        btn = _btn("Get Free", C_BLUE_BTN, size=11, h=40); btn.setFixedWidth(checks_w)
        btn.clicked.connect(self._add_mw3_ds)
        row.addWidget(btn)
        row.addWidget(_lbl(self._short_name(gd["base"]), 13, "#555566", align=Qt.AlignLeft, wrap=False), stretch=1)
        color = C_IW if gd["dev"] == "iw" else C_TREY
        row.addWidget(_badge(_active_client(gd).upper(), color, 170, h=28, size=9))
        self._add_row(gd, cw)

    def _add_mw3_ds(self):
        from depot_downgrade import open_steam_install
        open_steam_install(42750)
        QMessageBox.information(
            self, "MW3 Multiplayer",
            "DeckOps is adding the free MW3 Dedicated Server to your "
            "Steam account. This includes the full multiplayer files.\n\n"
            "Let Steam finish the download, then close and reopen "
            "DeckOps. MW3 will appear as a detected game."
        )

    @staticmethod
    def _removable_mounts():
        # SD cards / USB drives; username-agnostic so it works on Bazzite/CachyOS too
        out = set()
        for v in QStorageInfo.mountedVolumes():
            root = v.rootPath()
            if (v.isValid() and v.isReady() and not v.isReadOnly()
                    and root.startswith(("/run/media/", "/media/", "/mnt/"))):
                out.add(root)
        return sorted(out)

    def _pick_folder(self):
        home = os.path.expanduser("~")
        mounts = self._removable_mounts()
        dlg = QFileDialog(self, "Select your games folder", mounts[0] if len(mounts) == 1 else home)
        dlg.setFileMode(QFileDialog.Directory)
        # Qt's own dialog honors custom sidebar entries; the KDE/portal one ignores them
        dlg.setOptions(QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks | QFileDialog.DontUseNativeDialog)
        dlg.setSidebarUrls([QUrl.fromLocalFile(home)] + [QUrl.fromLocalFile(m) for m in mounts])
        dlg.resize(1000, 600)
        if not dlg.exec_():
            return
        folder = dlg.selectedFiles()[0] if dlg.selectedFiles() else ""
        if not folder or folder in self._extra_paths:
            return
        self._extra_paths.append(folder)
        self._folder_btn.setEnabled(False); self.inst_btn.setEnabled(False)
        self.warning.setText(f"Scanning {folder}...")
        self.warning.setStyleSheet(f"color:{C_DIM};background:transparent;")
        self.warning.setVisible(True)
        self._scan_sigs = _Sigs()
        self._scan_sigs.done.connect(self._on_folder_scanned)
        threading.Thread(target=self._do_folder_scan, daemon=True).start()

    def _do_folder_scan(self):
        from detect_games import find_own_installed
        try:
            found = find_own_installed(extra_paths=self._extra_paths)
        except Exception as ex:
            _log_to_file(f"[SetupScreen] folder scan failed: {ex}")
            found = {}
        self._scanned_own = {k: v for k, v in found.items() if k not in self.steam_installed}
        self._scan_sigs.done.emit(True)

    def _on_folder_scanned(self, _):
        own = self._scanned_own
        if cfg.is_lcd():
            lcd_allowed = set()
            for g in ALL_GAMES: lcd_allowed.update(g.get("lcd_keys", g["keys"]))
            own = {k: v for k, v in own.items() if k in lcd_allowed}
        added = len(set(own) - set(self.own_installed))
        self.own_installed = own
        self._folder_btn.setEnabled(True); self.inst_btn.setEnabled(True)
        self._build()
        self.warning.setText(f"Found {added} new game(s)." if added else "No new supported games in that folder.")
        self.warning.setStyleSheet(f"color:{C_IW if added else C_TREY};background:transparent;")
        self.warning.setVisible(True)

    def _go_install(self):
        steam_selected = []
        own_selected = {}
        for key, (cb, gd, source) in self._checks.items():
            if not cb.isChecked(): continue
            if source == "own" and key in self.own_installed:
                own_selected[key] = self.own_installed[key]
            elif key in self.steam_installed:
                steam_selected.append((key, gd, self.steam_installed[key]))

        if not steam_selected and not own_selected:
            self.warning.setText("Select at least one game to continue.")
            self.warning.setStyleSheet(f"color:{C_TREY};background:transparent;")
            self.warning.setVisible(True); return

        s = get_screen(self.stack, "InstallScreen")
        s.steam_selected = steam_selected
        s.own_selected = own_selected
        s.steam_root = self.steam_root
        all_tuples = list(steam_selected)
        for _k, _g in own_selected.items():
            for _gd in ALL_GAMES:
                if _k in _active_keys(_gd):
                    all_tuples.append((_k, _gd, _g)); break
        sel = {k for k, _, _ in all_tuples}
        if "iw4mp" not in sel:
            s.install_iw4x_dlc = ""
        elif self._iw4x_dlc_present:
            s.install_iw4x_dlc = "keep"
        else:
            s.install_iw4x_dlc = "install" if self._iw4x_dlc_cb and self._iw4x_dlc_cb.isChecked() else ""
        s.cod4_client = self._cod4_choice if "cod4mp" in sel else "cod4r"
        s.zd_choice = bool(self._zd_cb and self._zd_cb.isChecked())
        s.bo3_client = _ask_bo3_client(self, all_tuples)
        go_to(self.stack, "InstallScreen")

# --- _BaseInstallScreen ---
class _BaseInstallScreen(QWidget):
    _DONE_MSG = "Installation complete!"

    def __init__(self, stack, screen_name):
        super().__init__(); self.stack = stack; self.screen_name = screen_name
        self.steam_root = ""
        self._plut_event = threading.Event()
        self._cod4r_event = threading.Event()
        self._iw5_dg_event = threading.Event()
        self._iw5_method = ""
        self._dg_game_title = ""
        self._manual_dl_event = threading.Event()
        self._manual_dl_ok = False
        self._retry_dl_event = threading.Event()
        self._retry_dl_choice = ""
        self._zd_event = threading.Event()
        self._zd_accept = False
        self._return_to_management = False
        self._from_manage = False
        self.zd_choice = None
        self.bo3_client = "cleanops"
        self._results = []

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        lay.addWidget(_header_bar()[0])

        content = QWidget()
        clay = QVBoxLayout(content); clay.setContentsMargins(80,20,80,60); clay.setSpacing(20)
        self.cur = _lbl("Preparing...", 16, "#CCC"); clay.addWidget(self.cur)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(22)
        bw = QHBoxLayout(); bw.setContentsMargins(60,0,60,0); bw.addWidget(self.bar)
        clay.addLayout(bw)
        self.stat = _lbl("", 13, C_IW); clay.addWidget(self.stat)
        self.iw5_qr_box = QWidget()
        self.iw5_qr_box.setVisible(False)
        qb = QVBoxLayout(self.iw5_qr_box)
        qb.setContentsMargins(0, 0, 0, 0)
        qb.setSpacing(4)
        self.iw5_qr_lbl = QLabel("")
        self.iw5_qr_lbl.setStyleSheet(
            "font-family: monospace; font-size: 8px; line-height: 8px;"
            "color: #000; background: #FFF; padding: 8px;"
            f"border: 2px solid {C_DIM}; border-radius: 8px;"
        )
        self.iw5_qr_lbl.setAlignment(Qt.AlignCenter)
        qr_row = QHBoxLayout()
        qr_row.addStretch(); qr_row.addWidget(self.iw5_qr_lbl); qr_row.addStretch()
        qb.addLayout(qr_row)
        self.iw5_qr_info = _lbl(
            "Open the Steam app on your phone, tap the shield icon (Steam Guard),\n"
            "then tap \"Approve a sign-in\". Point your camera at the QR code above.",
            11, "#AAA", align=Qt.AlignCenter,
        )
        qb.addWidget(self.iw5_qr_info)
        clay.addWidget(self.iw5_qr_box)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(font(11))
        self.log.setStyleSheet("QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}")
        clay.addWidget(self.log, stretch=1)

        self._log_status = _lbl("", 11, C_DIM, wrap=False)
        log_btn = _btn("Copy Log", C_DARK_BTN, size=11, h=40); log_btn.setFixedWidth(130)
        log_btn.clicked.connect(lambda: _copy_log_to_clipboard(self._log_status))
        lr = QHBoxLayout(); lr.addStretch(); lr.addWidget(log_btn); lr.addWidget(self._log_status); lr.addStretch()
        clay.addLayout(lr)

        self.plut_warn = _lbl(
            "⚠  LCD: Plutonium takes time to download and launch.\n"
            "     Please be patient — do NOT click the button below until\n"
            "     Plutonium has fully loaded, you have logged in, and closed the window.",
            12, C_TREY, align=Qt.AlignCenter,
        )
        self.plut_warn.setStyleSheet(
            f"color:{C_TREY};background:#2A1A08;border:1px solid {C_TREY};"
            "border-radius:8px;padding:10px 16px;"
        )
        self.plut_warn.setVisible(False)
        clay.addWidget(self.plut_warn)

        self.plut_btn = _btn("I've closed Plutonium  ✓", C_TREY, size=13, h=52)
        self.plut_btn.setFixedWidth(460); self.plut_btn.setVisible(False)
        self.plut_btn.clicked.connect(self._confirm_plut)
        pw = QHBoxLayout(); pw.addStretch(); pw.addWidget(self.plut_btn); pw.addStretch()
        clay.addLayout(pw)

        self.cod4r_btn = _btn("I've closed the CoD4R launcher  ✓", C_TREY, size=13, h=52)
        self.cod4r_btn.setFixedWidth(460); self.cod4r_btn.setVisible(False)
        self.cod4r_btn.clicked.connect(self._confirm_cod4r)
        c4w = QHBoxLayout(); c4w.addStretch(); c4w.addWidget(self.cod4r_btn); c4w.addStretch()
        clay.addLayout(c4w)

        self.iw5_dg_btn = _btn("Download complete, continue  ✓", C_IW, size=13, h=52)
        self.iw5_dg_btn.setFixedWidth(460); self.iw5_dg_btn.setVisible(False)
        self.iw5_dg_btn.clicked.connect(self._confirm_iw5_dg)
        dw = QHBoxLayout(); dw.addStretch(); dw.addWidget(self.iw5_dg_btn); dw.addStretch()
        clay.addLayout(dw)

        self.zd_info = _lbl(
            "Zombies Declassified adds 10 classic Zombies maps to BO2 via Plutonium.\n"
            "This is an optional download (~9 GB). You can install it later from Manage.",
            12, "#CCC", align=Qt.AlignCenter,
        )
        self.zd_info.setStyleSheet(
            f"color:#CCC;background:#1A1A2A;border:1px solid {C_DIM};"
            "border-radius:8px;padding:10px 16px;"
        )
        self.zd_info.setVisible(False)
        clay.addWidget(self.zd_info)
        self.zd_yes = _btn("Install Zombies Declassified (~9 GB)", C_IW, size=13, h=52)
        self.zd_yes.setFixedWidth(460); self.zd_yes.setVisible(False)
        self.zd_yes.clicked.connect(lambda: self._confirm_zd(True))
        self.zd_skip = _btn("Skip", C_DARK_BTN, size=13, h=52)
        self.zd_skip.setFixedWidth(200); self.zd_skip.setVisible(False)
        self.zd_skip.clicked.connect(lambda: self._confirm_zd(False))
        zw = QHBoxLayout(); zw.addStretch(); zw.addWidget(self.zd_yes); zw.addSpacing(12); zw.addWidget(self.zd_skip); zw.addStretch()
        clay.addLayout(zw)

        self.summary = _lbl("", 12, "#CCC", align=Qt.AlignLeft)
        self.summary.setTextFormat(Qt.RichText); self.summary.setVisible(False)
        self.summary.setStyleSheet(
            f"color:#CCC;background:#1A1A2A;border:1px solid {C_DIM};"
            "border-radius:8px;padding:10px 16px;")
        sw = QHBoxLayout(); sw.addStretch(); sw.addWidget(self.summary, 3); sw.addStretch()
        clay.addLayout(sw)

        self.retry_btn = _btn("Retry Failed", C_TREY, size=13, h=52)
        self.retry_btn.setFixedWidth(280); self.retry_btn.setVisible(False)
        self.retry_btn.clicked.connect(self._retry_failed)

        self.cont_btn = _btn("Continue  >>", C_IW, size=13, h=52)
        self.cont_btn.setFixedWidth(320); self.cont_btn.setVisible(False)
        self.cont_btn.clicked.connect(lambda: go_to(self.stack, "SetupCompleteScreen"))
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(self.retry_btn)
        cw.addSpacing(12); cw.addWidget(self.cont_btn); cw.addStretch()
        clay.addLayout(cw)
        clay.addStretch()
        lay.addWidget(content, stretch=1)

        self._s = _Sigs()
        self._s.progress.connect(lambda p, m: (self.bar.setValue(p), self.cur.setText(m)))
        self._s.log.connect(self._append_log)
        self._s.done.connect(self._on_done)
        self._s.plut_wait.connect(self._show_plut_wait)
        self._s.plut_go.connect(self._hide_plut_wait)
        self._s.cod4r_wait.connect(self._show_cod4r_wait)
        self._s.cod4r_go.connect(self._hide_cod4r_wait)
        self._s.iw5_dg_wait.connect(self._show_iw5_dg_wait)
        self._s.iw5_dg_go.connect(self._hide_iw5_dg_wait)
        self._s.iw5_qr_show.connect(self._show_iw5_qr)
        self._s.iw5_qr_hide.connect(self._hide_iw5_qr)
        self._s.iw5_dg_choose.connect(self._ask_iw5_dg_method)
        self._s.pulse_start.connect(self._start_pulse)
        self._s.pulse_stop.connect(self._stop_pulse)
        self._s.manual_dl.connect(self._show_manual_dl_dialog)
        self._s.retry_dl.connect(self._show_retry_dl_dialog)
        self._s.zd_ask.connect(self._show_zd_ask)
        self._s.zd_go.connect(self._hide_zd_ask)

        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._do_pulse)
        self._pulse_msg   = ""
        self._pulse_count = 0

    def _start_pulse(self, base_msg):
        self._pulse_msg   = base_msg
        self._pulse_count = 0
        self._pulse_timer.start(500)

    def _do_pulse(self):
        dots = "." * (self._pulse_count % 4)
        self.cur.setText(f"{self._pulse_msg}{dots}")
        self._pulse_count += 1

    def _stop_pulse(self):
        self._pulse_timer.stop()

    def _show_plut_wait(self):
        is_lcd = cfg.is_lcd()
        self.plut_warn.setVisible(is_lcd)
        self.plut_btn.setVisible(True)

    def _hide_plut_wait(self):
        self.plut_warn.setVisible(False)
        self.plut_btn.setVisible(False)

    def _show_cod4r_wait(self):
        self.cod4r_btn.setVisible(True)

    def _hide_cod4r_wait(self):
        self.cod4r_btn.setVisible(False)

    def _show_iw5_dg_wait(self, cmd, step_label):
        from depot_downgrade import copy_to_clipboard
        copy_to_clipboard(cmd)
        self.iw5_dg_btn.setText(f"{step_label} complete, continue  ✓")
        self.iw5_dg_btn.setVisible(True)

    def _hide_iw5_dg_wait(self):
        self.iw5_dg_btn.setVisible(False)

    def _confirm_iw5_dg(self):
        self._iw5_dg_event.set()

    def _show_zd_ask(self):
        self.zd_info.setVisible(True)
        self.zd_yes.setVisible(True)
        self.zd_skip.setVisible(True)

    def _hide_zd_ask(self):
        self.zd_info.setVisible(False)
        self.zd_yes.setVisible(False)
        self.zd_skip.setVisible(False)

    def _confirm_zd(self, accepted):
        self._zd_accept = accepted
        self._zd_event.set()

    def _show_iw5_qr(self, qr_text):
        from depot_downgrade import qr_text_to_pixmap
        pm = qr_text_to_pixmap(qr_text, scale=8)
        if pm:
            pm = pm.scaled(350, 350, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.iw5_qr_lbl.setPixmap(pm)
            self.iw5_qr_lbl.setFixedSize(pm.size())
        else:
            self.iw5_qr_lbl.setText(qr_text)
        self.iw5_qr_box.setVisible(True)
        self.log.setMaximumHeight(0)

    def _hide_iw5_qr(self):
        self.iw5_qr_box.setVisible(False)
        self.log.setMaximumHeight(16777215)

    def _ask_iw5_dg_method(self):
        _games = self._dg_game_title or "selected games"
        msg = QMessageBox(self)
        msg.setWindowTitle("Depot Downgrade")
        msg.setText(
            f"The following games need older depot files\n"
            f"for community client compatibility:\n\n"
            f"  {_games}\n\n"
            "This requires at least 15 GB of free disk space.\n"
            "One QR scan covers all games listed above.\n\n"
            "How would you like to authenticate the download?"
        )
        qr_btn = msg.addButton("QR Code Scan (recommended)", QMessageBox.AcceptRole)
        manual_btn = msg.addButton("Steam Console (manual)", QMessageBox.AcceptRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == qr_btn:
            self._iw5_method = "qr"
        elif clicked == manual_btn:
            self._iw5_method = "manual"
        else:
            self._iw5_method = ""
        self._iw5_dg_event.set()

    def _run_batch_depot_downgrade(self, dg_jobs):
        """
        Run depot downgrade for multiple games in one session.
        Each job is (game_id, game_name, install_dir, depots, cmds).
        One QR scan / one manual session covers all games.
        Called from the worker thread.
        Returns the captured username or None.
        """
        from depot_downgrade import (
            ensure_depotdownloader, run_depot_download_qr,
            find_depot_staging, merge_depots, open_steam_console,
            GAME_CONFIGS,
        )

        game_names = ", ".join(j[1] for j in dg_jobs)
        self._iw5_dg_event.clear()
        self._iw5_method = ""
        self._dg_game_title = game_names
        self._s.iw5_dg_choose.emit()
        self._iw5_dg_event.wait()

        if not self._iw5_method:
            return None

        captured_user = None
        total_depots = sum(len(d) for _, _, _, d, _ in dg_jobs)
        depot_num = 0

        if self._iw5_method == "qr":
            self._s.log.emit(
                f"Downloading depot files for: {game_names}.\n"
                "  Scan the QR code with your Steam mobile app.\n"
                "  The code will refresh if it expires.\n"
                "  Your login credentials will be deleted after the download."
            )
            self._s.progress.emit(11, "Setting up DepotDownloader...")
            try:
                ensure_depotdownloader(
                    on_progress=lambda m: self._s.log.emit(f"  {m}"))

                failed = False
                for game_id, game_name, install_dir, depots, _ in dg_jobs:
                    gcfg = GAME_CONFIGS[game_id]
                    staging = os.path.join(
                        os.path.dirname(install_dir),
                        f".deckops_{game_id}_staging",
                    )
                    for depot in depots:
                        depot_num += 1
                        self._s.progress.emit(
                            11, f"Downloading depot {depot_num} of {total_depots}...")
                        result = run_depot_download_qr(
                            staging_dir=staging,
                            depot_info=depot,
                            app_id=gcfg["app_id"],
                            on_qr=lambda qr: self._s.iw5_qr_show.emit(qr),
                            on_auth_success=lambda u: self._s.iw5_qr_hide.emit(),
                            on_progress=lambda m: self._s.progress.emit(11, m),
                            on_log=lambda m: self._s.log.emit(f"  {m}"),
                            username=captured_user,
                        )
                        if result is None:
                            self._s.log.emit(f"✗  Depot {depot['depot']} download failed.")
                            failed = True
                            break
                        captured_user = result

                    self._s.iw5_qr_hide.emit()

                    if failed:
                        break
                    if not os.path.isdir(staging):
                        continue
                    self._s.progress.emit(12, f"Merging {game_name} files...")
                    self._s.pulse_start.emit(f"Merging {game_name} files")
                    try:
                        merge_depots(
                            game_id, staging, install_dir,
                            on_progress=lambda m: self._s.log.emit(f"  {m}"),
                        )
                        self._s.log.emit(f"✓  {game_name} depot files updated")
                    except Exception as ex:
                        self._s.log.emit(f"✗  {game_name} merge failed: {ex}")
                    finally:
                        self._s.pulse_stop.emit()

            except Exception as ex:
                self._s.log.emit(f"✗  QR downgrade failed: {ex}")

        elif self._iw5_method == "manual":
            self._s.log.emit(
                f"Downloading depot files for: {game_names}.\n"
                "  DeckOps will open the Steam console. Paste each command\n"
                "  when prompted and wait for \"Depot download complete\"\n"
                "  before clicking continue."
            )
            self._s.progress.emit(11, "Depot download...")
            open_steam_console()

            for game_id, game_name, install_dir, _, cmds in dg_jobs:
                gcfg = GAME_CONFIGS[game_id]
                for cmd in cmds:
                    depot_num += 1
                    step = f"Depot {depot_num} of {total_depots}"
                    self._s.log.emit(
                        f"\n  Step {depot_num}: Paste this into the Steam console:\n"
                        f"  {cmd}\n"
                        f"  (copied to clipboard)"
                    )
                    self._iw5_dg_event.clear()
                    self._s.iw5_dg_wait.emit(cmd, step)
                    self._iw5_dg_event.wait()
                    self._s.iw5_dg_go.emit()

                staging = find_depot_staging(self.steam_root, gcfg["app_id"])
                if not staging:
                    self._s.log.emit(
                        f"✗  Could not find staging directory for {game_name}.")
                    continue
                self._s.progress.emit(12, f"Merging {game_name} files...")
                self._s.pulse_start.emit(f"Merging {game_name} files")
                try:
                    merge_depots(
                        game_id, staging, install_dir,
                        on_progress=lambda m: self._s.log.emit(f"  {m}"),
                    )
                    self._s.log.emit(f"✓  {game_name} depot files updated")
                except Exception as ex:
                    self._s.log.emit(f"✗  {game_name} merge failed: {ex}")
                finally:
                    self._s.pulse_stop.emit()

        return captured_user

    def _seed_results(self):
        """One record per selected key; phases overwrite status as they run."""
        self._results = [{"key": k, "name": gd["base"], "status": "pending", "reason": ""}
                         for k, gd, _g in self.selected]

    def _mark(self, key, status, reason=""):
        for r in self._results:
            if r["key"] == key:
                r["status"] = status; r["reason"] = reason; return

    def _retryable(self):
        return [r for r in self._results if r["status"] in ("failed", "pending")]

    def _render_summary(self):
        icons = {"ok": ("✓", C_IW), "failed": ("✗", C_TREY),
                 "skipped": ("–", "#777788"), "pending": ("–", "#777788")}
        rows = []
        for r in self._results:
            icon, col = icons.get(r["status"], icons["pending"])
            label = html.escape(f"{r['name']} - {KEY_MODE_LABEL.get(r['key'], r['key'])}")
            txt = f'<span style="color:{col}">{icon}&nbsp;&nbsp;{label}</span>'
            if r["status"] == "failed" and r["reason"]:
                txt += f'<span style="color:#777788"> - {html.escape(r["reason"][:120])}</span>'
            elif r["status"] == "pending":
                txt += '<span style="color:#777788"> - not attempted</span>'
            elif r["status"] == "skipped":
                txt += f'<span style="color:#777788"> - {html.escape(r["reason"] or "skipped")}</span>'
            rows.append(txt)
        self.summary.setText("<br>".join(rows))
        self.summary.setVisible(True)

    def _retry_failed(self):
        keys = {r["key"] for r in self._retryable()}
        if not keys: return
        # t7x is injected from the t7 row, so it needs its parent key kept
        if "t7x" in keys: keys.add("t7")
        self.steam_selected = [(k, gd, g) for k, gd, g in (self.steam_selected or [])
                               if k in keys]
        self.own_selected = {k: g for k, g in self.own_selected.items() if k in keys}
        # _return_to_management was consumed by the first run
        self._return_to_management = self._from_manage
        self._reset_and_run()

    def _append_log(self, text):
        _log_to_file(text)
        sb = self.log.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log.appendPlainText(text)
        if at_bottom: sb.setValue(sb.maximum())

    def _confirm_plut(self):
        self._plut_event.set()

    def _confirm_cod4r(self):
        self._cod4r_event.set()

    def _show_retry_dl_dialog(self, label, error_msg):
        msg = QMessageBox(self)
        msg.setWindowTitle(f"{label} — Download Failed")
        msg.setText(
            f"<b>{label}</b> download failed after multiple attempts.<br><br>"
            f"Error: {error_msg}<br><br>"
            f"Would you like to retry, download manually, or skip?"
        )
        retry_btn = msg.addButton("Retry", QMessageBox.AcceptRole)
        manual_btn = msg.addButton("Download Manually", QMessageBox.ActionRole)
        msg.addButton("Skip", QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == retry_btn:
            self._retry_dl_choice = "retry"
        elif clicked == manual_btn:
            self._retry_dl_choice = "manual"
        else:
            self._retry_dl_choice = "skip"
        self._retry_dl_event.set()

    def _show_manual_dl_dialog(self, url, dest_folder, filename, label):
        """
        Show a dialog telling the user to manually download a file.
        Runs on the main thread (called via signal from worker).
        """
        os.makedirs(dest_folder, exist_ok=True)
        dest_path = os.path.join(dest_folder, filename)

        msg = QMessageBox(self)
        msg.setWindowTitle(f"{label} — Download Failed")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            f"<b>{label}</b> could not be downloaded automatically.<br><br>"
            f'Download it manually here:<br>'
            f'<a href="{url}">{url}</a><br><br>'
            f'Then place <b>{filename}</b> in:<br>'
            f'<code>{dest_folder}</code><br><br>'
            f'Click <b>Open Folder</b> to open the destination, then '
            f'<b>I\'ve Placed It</b> when the file is in place.'
        )
        open_btn = msg.addButton("Open Folder", QMessageBox.ActionRole)
        done_btn = msg.addButton("I've Placed It", QMessageBox.AcceptRole)
        skip_btn = msg.addButton("Skip", QMessageBox.RejectRole)

        while True:
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked == open_btn:
                subprocess.Popen(["xdg-open", dest_folder])
                continue
            elif clicked == done_btn:
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    self._manual_dl_ok = True
                    self._manual_dl_event.set()
                    return
                QMessageBox.warning(
                    self, "File Not Found",
                    f"{filename} was not found in:\n{dest_folder}\n\n"
                    "Make sure the file is downloaded and placed in the correct folder.",
                )
                continue
            else:
                self._manual_dl_ok = False
                self._manual_dl_event.set()
                return

    def _on_done(self, ok):
        self._stop_pulse()
        self.zd_choice = None
        if ok:
            self.cur.setText(self._DONE_MSG)
        else:
            if self._results:
                self._render_summary()
            else:
                self.summary.setVisible(False)
            n = len([r for r in self._results if r["status"] == "failed"])
            self.cur.setText(
                f"Finished with {n} problem(s). See the summary below."
                if n else "Setup did not finish. Check the log above, then try again.")
            self.cur.setStyleSheet(f"color:{C_TREY};background:transparent;")
            self.retry_btn.setText(f"Retry Failed ({len(self._retryable())})")
            self.retry_btn.setVisible(bool(self._retryable()))
            if not self._from_manage:
                try: self.cont_btn.clicked.disconnect()
                except Exception: pass
                self.cont_btn.setText("<< Back to Game Selection")
                self.cont_btn.clicked.connect(lambda: go_to(self.stack, "SetupScreen"))
        self.cont_btn.setVisible(True)

    def _go_management(self):
        from wrapper import launch_steam
        launch_steam()
        go_to(self.stack, "ManagementScreen")

    def showEvent(self, e):
        super().showEvent(e)
        self._reset_and_run()

    def _reset_and_run(self):
        self.bar.setValue(0); self.log.clear()
        self.log.setMaximumHeight(16777215)
        self.cur.setText("Preparing..."); self.cur.setStyleSheet("color:#CCC;background:transparent;")
        self.stat.setText("")
        self.plut_btn.setVisible(False)
        self.plut_warn.setVisible(False)
        self.cod4r_btn.setVisible(False)
        self.iw5_dg_btn.setVisible(False)
        self.iw5_qr_box.setVisible(False)
        self.zd_info.setVisible(False); self.zd_yes.setVisible(False); self.zd_skip.setVisible(False)
        self._zd_event.clear(); self._zd_accept = False
        self.summary.setVisible(False); self.retry_btn.setVisible(False)
        self._results = []
        self.cont_btn.setVisible(False)
        self._plut_event.clear()
        self._cod4r_event.clear()
        self._iw5_dg_event.clear()
        self._iw5_method = ""
        self._dg_game_title = ""
        self._manual_dl_event.clear()
        self._manual_dl_ok = False
        self._retry_dl_event.clear()
        self._retry_dl_choice = ""
        self._DONE_MSG = _BaseInstallScreen._DONE_MSG
        self._stop_pulse()
        try:
            self.cont_btn.clicked.disconnect()
        except Exception:
            pass
        self._from_manage = self._return_to_management
        if self._return_to_management:
            self.cont_btn.setText("Back to My Games  >>")
            self.cont_btn.clicked.connect(self._go_management)
            self._return_to_management = False
        else:
            self.cont_btn.setText("Continue  >>")
            self.cont_btn.clicked.connect(lambda: go_to(self.stack, "SetupCompleteScreen"))
        _log_to_file(f"── {self.screen_name} started ──")
        QTimer.singleShot(400, lambda: threading.Thread(target=self._run, daemon=True).start())

    def _run(self):
        import traceback as _tb
        try:
            self._run_inner()
        except Exception:
            err = _tb.format_exc()
            _log_to_file(f"[FATAL] {self.screen_name}._run crashed:\n{err}")
            try:
                self._s.log.emit(f"✗ Install failed with error:\n{err}")
                self._s.progress.emit(100, "Install failed — see log.")
                self._s.done.emit(False)
            except Exception:
                pass

    def _run_inner(self):
        from wrapper import get_proton_path, find_compatdata, kill_steam, set_compat_tool
        from cod4x import install_cod4x
        from cod4r import install_cod4r
        from iw4x import install_iw4x
        from iw3sp import install_iw3sp
        from t6sp_mod import install_t6sp_mod
        from cleanops import install_cleanops
        from t7x import install_t7x
        from ge_proton import install_ge_proton, MANAGED_APPIDS

        # --- Source awareness setup
        own_selected = self.own_selected
        has_own = bool(own_selected)

        steam_sel = list(self.steam_selected or [])
        own_as_tuples = []
        for k, g in own_selected.items():
            for gd in ALL_GAMES:
                if k in _active_keys(gd):
                    own_as_tuples.append((k, gd, g)); break
        self.selected = steam_sel + own_as_tuples

        if has_own:
            from shortcut import enrich_own_games, write_own_shortcuts

        selected_keys = [key for key, _, _ in self.selected]
        logged_bases  = set()
        has_plut      = any(KEY_CLIENT.get(k) == "plutonium" for k in selected_keys)
        has_cod4      = any(KEY_CLIENT.get(k) in ("cod4r", "cod4x", "iw3sp") for k in selected_keys)
        has_t6sp_mod  = any(KEY_CLIENT.get(k) == "t6sp_mod" for k in selected_keys)

        _cod4_client = getattr(self, "cod4_client", "cod4r")
        _steam_killed = False

        def _kill_steam_once():
            nonlocal _steam_killed
            if not _steam_killed:
                self._s.progress.emit(18, "Closing Steam...")
                self._s.log.emit("Closing Steam...")
                try:
                    kill_steam(on_progress=lambda msg: self._s.log.emit(f"  {msg}"))
                    self._s.log.emit("  ✓ Steam closed.")
                except Exception as ex:
                    self._s.log.emit(f"  Could not close Steam: {ex}")
                _steam_killed = True

        # --- GE-Proton download (Steam still running)
        ge_version = None
        try:
            self._s.pulse_start.emit("Installing GE-Proton")
            self._s.log.emit("Installing GE-Proton...")
            ge_version = install_ge_proton(
                on_progress=lambda pct, msg: self._s.progress.emit(2 + int(pct * 0.06), msg)
            )
            self._s.pulse_stop.emit()
            self._s.log.emit(f"✓  {ge_version} downloaded")
            cfg.set_ge_proton_version(ge_version)
        except Exception as ex:
            self._s.pulse_stop.emit()
            self._s.log.emit(f"  GE-Proton setup skipped: {ex}")

        proton = get_proton_path(self.steam_root)

        # --- BO3 client selection: cleanops, t7x, or both
        # Injection must happen early so t7x is included in prefix init,
        # shortcuts, and selected_keys. Actual install runs later (after
        # CleanOps) to match the original phase order.
        _bo3_choice = getattr(self, "bo3_client", "cleanops")
        _has_bo3 = any(KEY_CLIENT.get(k) == "cleanops" for k in selected_keys)
        has_cleanops = _has_bo3 and _bo3_choice in ("cleanops", "both")
        has_t7x      = _has_bo3 and _bo3_choice in ("t7x", "both")
        if has_t7x:
            for k, gd, g in list(self.selected):
                if k == "t7":
                    t7x_tuple = ("t7x", gd, dict(g))
                    self.selected.append(t7x_tuple)
                    steam_sel.append(t7x_tuple)
                    selected_keys.append("t7x")
                    break

        self._seed_results()

        # --- Enrich own game dicts (shortcut_appid, compatdata_path)
        # enrich_own_games computes CRC-based appids, prefix paths, and
        # resolved exe/launch options WITHOUT writing any VDF entries.
        # Must run before ensure_all_prefix_deps. Actual shortcut writing
        # is deferred to write_own_shortcuts() after all mod clients are
        # installed so every target exe exists on disk.
        if has_own:
            self._s.progress.emit(8, "Computing own game shortcuts...")
            self._s.log.emit("Enriching own game data...")
            own_games_dict = dict(own_selected)
            own_games_dict = enrich_own_games(
                own_games=own_games_dict,
                selected_keys=list(own_selected.keys()),
                on_progress=lambda msg: self._s.log.emit(msg),
            )
            _log_to_file("[BREADCRUMB] enrich_own_games returned")
            self.selected = [
                (k, gd, own_games_dict.get(k, g)) for k, gd, g in self.selected
            ]
            own_games = {k: g for k, gd, g in self.selected if g and k in own_selected}
            _log_to_file("[BREADCRUMB] own_games rebuilt, starting prefix init")

        # --- Create prefixes + install deps from GE-Proton default_pfx
        # Every selected game gets its prefix preloaded. Own games use their
        # CRC-based prefix (set by enrich_own_games). Steam games use their
        # Steam appid prefix. ensure_all_prefix_deps handles deduplication
        # and skips prefixes that are already initialized.
        self._s.progress.emit(9, "Creating Proton prefixes...")
        self._s.log.emit("Creating Proton prefixes and installing dependencies...")
        self._s.pulse_start.emit("Installing prefix dependencies")
        from ge_proton import ensure_all_prefix_deps
        from detect_games import GAMES as _GAMES_MAP
        dep_targets = []
        for key, gd, game in self.selected:
            if not game:
                continue
            if key in own_selected:
                compat = game.get("compatdata_path", "")
            else:
                appid = _GAMES_MAP[key]["appid"] if key in _GAMES_MAP else gd["appid"]
                compat = find_compatdata(self.steam_root, appid,
                                         game_install_dir=game.get("install_dir"))
                if not compat and game.get("install_dir"):
                    steamapps = os.path.dirname(os.path.dirname(game["install_dir"]))
                    compat = os.path.join(steamapps, "compatdata", str(appid))
            if compat:
                dep_targets.append((key, compat))
        if dep_targets:
            _log_to_file(f"[BREADCRUMB] calling ensure_all_prefix_deps with {len(dep_targets)} targets: {[k for k,_ in dep_targets]}")
            done = ensure_all_prefix_deps(
                ge_version, dep_targets,
                on_progress=lambda msg: self._s.log.emit(msg),
                proton_path=proton,
                steam_root=self.steam_root,
            )
            self._s.log.emit(f"✓  Prefix dependencies: {done}/{len(dep_targets)} ready")
        self._s.pulse_stop.emit()
        _log_to_file("[BREADCRUMB] prefix deps done")

        # --- CoD4 (iw3sp + cod4r/cod4x) -- Steam still running
        # Runs before the Plutonium bootstrapper and before Steam is closed
        # so the touchpad still works as a mouse for closing the CoD4R
        # launcher window.
        _log_to_file("[BREADCRUMB] starting cod4 install phase")
        if has_cod4:
            cod4_selected = [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) in ("cod4r", "cod4x", "iw3sp")]
            for key, gd, game in cod4_selected:
                base_name = gd["base"]
                self._s.progress.emit(9, f"Setting up {base_name}...")
                def op_cod4(pct, msg): self._s.progress.emit(9 + int(pct / 100 * 4), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    c = KEY_CLIENT.get(key, gd["client"])
                    if key == "cod4mp":
                        c = _cod4_client
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                        cod4_appid = game.get("shortcut_appid", 7940)
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                        cod4_appid = gd["appid"]
                    if c == "cod4r":
                        self._s.progress.emit(12, "Installing CoD4R — close the launcher when done...")
                        self._s.log.emit(
                            "CoD4R is downloading and installing now.\n"
                            "  1. Wait for the CoD4R launcher to finish downloading and updating\n"
                            "  2. Close the launcher when it is done\n"
                            "  3. Click the button below to continue"
                        )
                        self._s.cod4r_wait.emit()
                        install_cod4r(game, self.steam_root, proton, compat, op_cod4,
                                      appid=cod4_appid, source=source)
                        self._cod4r_event.wait()
                        self._cod4r_event.clear()
                        self._s.cod4r_go.emit()
                    elif c == "cod4x":
                        install_cod4x(game, self.steam_root, proton, compat, op_cod4,
                                      appid=cod4_appid)
                    elif c == "iw3sp":
                        install_iw3sp(game, self.steam_root, proton, compat, op_cod4, source=source)
                    cfg.mark_game_setup(key, c, source=source)
                    self._mark(key, "ok")
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except DownloadError as dl_ex:
                    _dl_resolved = False
                    while not _dl_resolved:
                        self._retry_dl_event.clear()
                        self._retry_dl_choice = ""
                        self._s.retry_dl.emit(dl_ex.label, str(dl_ex))
                        self._retry_dl_event.wait()
                        if self._retry_dl_choice == "retry":
                            try:
                                if c == "cod4r":
                                    install_cod4r(game, self.steam_root, proton, compat, op_cod4,
                                                  appid=cod4_appid, source=source)
                                elif c == "cod4x":
                                    install_cod4x(game, self.steam_root, proton, compat, op_cod4,
                                                  appid=cod4_appid)
                                elif c == "iw3sp":
                                    install_iw3sp(game, self.steam_root, proton, compat, op_cod4, source=source)
                                self._s.log.emit(f"✓  {base_name} done (retry succeeded)")
                                self._mark(key, "ok")
                                _dl_resolved = True
                            except DownloadError as dl_ex2:
                                dl_ex = dl_ex2
                        elif self._retry_dl_choice == "manual":
                            self._s.log.emit(f"⚠  {dl_ex.label} — opening manual download dialog")
                            self._manual_dl_event.clear()
                            self._manual_dl_ok = False
                            self._s.manual_dl.emit(
                                dl_ex.url, os.path.dirname(dl_ex.dest),
                                os.path.basename(dl_ex.dest), dl_ex.label,
                            )
                            self._manual_dl_event.wait()
                            if self._manual_dl_ok:
                                self._s.log.emit(f"  ✓  {dl_ex.label} placed manually")
                                # file is in place but the install step never re-ran
                                self._mark(key, "failed", "download recovered, install not run")
                            else:
                                self._s.log.emit(f"  ✗  {base_name} skipped by user.")
                                self._mark(key, "skipped", "skipped by user")
                            _dl_resolved = True
                        else:
                            self._s.log.emit(f"  ✗  {base_name} skipped by user.")
                            self._mark(key, "skipped", "skipped by user")
                            _dl_resolved = True
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- Depot downgrades (Steam still running)
        # Detect ALL games that need downgrading, show ONE dialog,
        # run ONE QR scan for everything.
        from depot_downgrade import (
            GAME_CONFIGS as _DG_CONFIGS,
            is_downgrade_needed as _dg_needed,
            is_sp_exe_64bit as _sp_64,
            detect_dlc_status as _dg_dlc_status,
            has_enough_space as _dg_space,
            REQUIRED_FREE_SPACE_GB as _DG_SPACE_GB,
            cleanup_depotdownloader,
            detect_installed_dlc as _dg_installed_dlc,
        )

        _DG_KEY_MAP = {
            "iw5": ("iw5mp", "iw5mp_ds", "iw5sp"),
            "iw6": ("iw6mp", "iw6sp"),
            "s1":  ("s1mp", "s1sp"),
        }
        # Each job: (game_id, game_name, install_dir, depots_list, cmds_list)
        _dg_jobs = []

        for _dg_id, _dg_keys in _DG_KEY_MAP.items():
            _matched = [
                (k, gd, g) for k, gd, g in self.selected
                if k in _dg_keys
                and k not in own_selected
                and g.get("install_dir")
            ]
            if not _matched:
                continue
            _gcfg = _DG_CONFIGS[_dg_id]
            _dir = _matched[0][2]["install_dir"]
            _sel = {k for k, _, _ in _matched}

            if _dg_id == "iw5":
                # MW3 has special SP/DS depot filtering and DLC markers
                _is_ds = _sel == {"iw5mp_ds"}
                _has_sp = "iw5sp" in _sel
                _needs_base = _dg_needed("iw5", _dir)
                _needs_sp = _has_sp and not _needs_base and _sp_64("iw5", _dir)
                _dlc_st = _dg_dlc_status("iw5", _dir)
                _dlc_bad = sorted(k for k, v in _dlc_st.items() if v == "wrong")

                if _dlc_bad:
                    _dlc_names = ", ".join(_gcfg["dlc"][k]["name"] for k in _dlc_bad)
                    self._s.log.emit(f"  MW3 DLC needs 32-bit update: {_dlc_names}")

                if not (_needs_base or _needs_sp or _dlc_bad):
                    self._s.log.emit("  MW3 is already 32-bit, downgrade skipped.")
                    continue

                self._s.log.emit("Checking MW3... 64-bit detected, downgrade needed.")
                if not _dg_space(_dir):
                    self._s.log.emit(f"✗  MW3 downgrade requires at least {_DG_SPACE_GB} GB of free space.")
                    continue

                _depots = list(_gcfg["depots"])
                _cmds = list(_gcfg["depot_cmds"])
                _sp_depot = _gcfg.get("sp_depot_id", 42681)
                if _needs_base:
                    _skip = set()
                    if not _has_sp:
                        _skip.add(_sp_depot)
                    if _is_ds:
                        _skip.update((42682, 42691))
                    _depots = [d for d in _depots if d["depot"] not in _skip]
                    _cmds = [c for c in _cmds if not any(f" {d} " in c for d in _skip)]
                elif _needs_sp:
                    _depots = [d for d in _depots if d["depot"] == _sp_depot]
                    _cmds = [c for c in _cmds if f" {_sp_depot} " in c]
                else:
                    _depots = []
                    _cmds = []

                for dk in _dlc_bad:
                    dlc = _gcfg["dlc"][dk]
                    _depots.append({"depot": dlc["depot"], "manifest": dlc["manifest"], "app": dlc["app"]})
                    _cmds.append(f"download_depot {dlc['app']} {dlc['depot']} {dlc['manifest']}")

                _dg_jobs.append(("iw5", _gcfg["name"], _dir, _depots, _cmds))
            else:
                # Ghosts, AW: PE/config check + appmanifest DLC detection
                if not _dg_needed(_dg_id, _dir):
                    self._s.log.emit(f"  {_gcfg['name']} depot files are up to date, skipped.")
                    continue
                if _gcfg.get("always_64bit"):
                    self._s.log.emit(f"Checking {_gcfg['name']}... needs older depot files for community clients.")
                else:
                    self._s.log.emit(f"Checking {_gcfg['name']}... 64-bit detected, downgrade needed.")
                if not _dg_space(_dir):
                    self._s.log.emit(f"✗  {_gcfg['name']} downgrade requires at least {_DG_SPACE_GB} GB of free space.")
                    continue
                _depots = list(_gcfg["depots"])
                _cmds = list(_gcfg["depot_cmds"])
                _owned_dlc = _dg_installed_dlc(_dg_id, self.steam_root)
                for dk in _owned_dlc:
                    dlc = _gcfg["dlc"][dk]
                    _depots.append({"depot": dlc["depot"], "manifest": dlc["manifest"], "app": dlc["app"]})
                    _cmds.append(f"download_depot {dlc['app']} {dlc['depot']} {dlc['manifest']}")
                if _owned_dlc:
                    _dlc_names = ", ".join(_gcfg["dlc"][k]["name"] for k in _owned_dlc)
                    self._s.log.emit(f"  DLC to downgrade: {_dlc_names}")
                _dg_jobs.append((_dg_id, _gcfg["name"], _dir, _depots, _cmds))

        _dg_user = None
        if _dg_jobs:
            _dg_user = self._run_batch_depot_downgrade(_dg_jobs)

        if _dg_user:
            self._s.log.emit("  Removing DepotDownloader and any saved credentials...")
            cleanup_depotdownloader()
            self._s.log.emit("  ✓  Login credentials removed.")

        # --- Plutonium bootstrapper (Steam still running)
        # Downloads Plutonium and launches it so the user can log in. LCD
        # routes through HGL (shared default prefix); OLED uses the
        # dedicated DeckOps prefix via Proton directly.
        if has_plut:
            from plutonium_oled import (launch_bootstrapper, is_plutonium_ready,
                                   install_plutonium)
            from plutonium_oled import GAME_META as _PLUT_META
            is_lcd = cfg.is_lcd()

            if is_lcd:
                from plutonium_lcd import (launch_bootstrapper_lcd,
                                    is_plutonium_ready_lcd)
                plut_ready = is_plutonium_ready_lcd()
            else:
                plut_ready = is_plutonium_ready()

            if not plut_ready:
                if is_lcd:
                    self._s.progress.emit(14, "Setting up Plutonium through HGL...")
                    self._s.log.emit(
                        "Setting up Plutonium through HGL...\n"
                        "  1. HGL will download and launch Plutonium (this may take a few minutes)\n"
                        "  2. Log in with your Plutonium account\n"
                        "  3. Close the Plutonium window\n"
                        "  4. Click the button below to continue"
                    )
                else:
                    self._s.progress.emit(14, "Launching Plutonium — please log in...")
                    self._s.log.emit(
                        "Plutonium is launching now.\n"
                        "  1. Wait for it to finish downloading\n"
                        "  2. Log in with your Plutonium account\n"
                        "  3. Close the Plutonium window\n"
                        "  4. Click the button below to continue"
                    )
                try:
                    if is_lcd:
                        launch_bootstrapper_lcd(
                            on_progress=lambda p, m: self._s.progress.emit(p, m)
                        )
                    else:
                        launch_bootstrapper(
                            proton,
                            on_progress=lambda p, m: self._s.progress.emit(p, m),
                            steam_root=self.steam_root,
                        )
                except DownloadError as dl_ex:
                    _dl_resolved = False
                    while not _dl_resolved:
                        self._retry_dl_event.clear()
                        self._retry_dl_choice = ""
                        self._s.retry_dl.emit(dl_ex.label, str(dl_ex))
                        self._retry_dl_event.wait()
                        if self._retry_dl_choice == "retry":
                            try:
                                if is_lcd:
                                    launch_bootstrapper_lcd(
                                        on_progress=lambda p, m: self._s.progress.emit(p, m))
                                else:
                                    launch_bootstrapper(
                                        proton,
                                        on_progress=lambda p, m: self._s.progress.emit(p, m),
                                        steam_root=self.steam_root)
                                _dl_resolved = True
                            except DownloadError as dl_ex2:
                                dl_ex = dl_ex2
                        elif self._retry_dl_choice == "manual":
                            self._manual_dl_event.clear()
                            self._manual_dl_ok = False
                            self._s.manual_dl.emit(
                                dl_ex.url, os.path.dirname(dl_ex.dest),
                                os.path.basename(dl_ex.dest), dl_ex.label,
                            )
                            self._manual_dl_event.wait()
                            if not self._manual_dl_ok:
                                self._s.log.emit("  ✗  Skipped by user.")
                                self._s.progress.emit(100, "Setup incomplete."); self._s.done.emit(False); return
                            self._s.log.emit(f"  ✓  {dl_ex.label} placed manually")
                            _dl_resolved = True
                        else:
                            self._s.log.emit("  ✗  Skipped by user.")
                            self._s.progress.emit(100, "Setup incomplete."); self._s.done.emit(False); return
                except Exception as ex:
                    self._s.log.emit(f"✗  Plutonium launch failed: {ex}")
                    self._s.progress.emit(100, "Setup failed."); self._s.done.emit(False); return

                if is_lcd:
                    self._s.log.emit(
                        "⏳  HGL is launching Plutonium. This may take a minute on first run\n"
                        "   while HGL sets up the Wine prefix."
                    )
                    self._s.pulse_start.emit("Waiting for Plutonium login")

                self._s.plut_wait.emit()
                self._plut_event.wait()
                self._s.plut_go.emit()

                if is_lcd:
                    self._s.pulse_stop.emit()

                ready_check = is_plutonium_ready_lcd() if is_lcd else is_plutonium_ready()
                if not ready_check:
                    self._s.log.emit(
                        "✗  Plutonium does not appear to be fully set up.\n"
                        "   Make sure you logged in and let it finish downloading."
                    )
                    self._s.progress.emit(100, "Setup incomplete."); self._s.done.emit(False); return

                self._s.log.emit("✓  Plutonium ready.")
            else:
                self._s.progress.emit(14, "Launching Plutonium to check for updates...")
                self._s.log.emit(
                    "Plutonium is launching now.\n"
                    "  1. Wait for it to finish updating\n"
                    "  2. Log in if prompted\n"
                    "  3. Close the Plutonium window\n"
                    "  4. Click the button below to continue"
                )
                try:
                    if is_lcd:
                        launch_bootstrapper_lcd(
                            on_progress=lambda p, m: self._s.progress.emit(p, m)
                        )
                    else:
                        launch_bootstrapper(
                            proton,
                            on_progress=lambda p, m: self._s.progress.emit(p, m),
                            steam_root=self.steam_root,
                        )
                except Exception as ex:
                    self._s.log.emit(f"  Plutonium update check skipped: {ex}")

                if is_lcd:
                    self._s.pulse_start.emit("Waiting for Plutonium update")

                self._s.plut_wait.emit()
                self._plut_event.wait()
                self._s.plut_go.emit()

                if is_lcd:
                    self._s.pulse_stop.emit()

                self._s.log.emit("✓  Plutonium ready.")

        # --- Kill Steam
        _kill_steam_once()

        # --- Clean slate: clear ALL launch options and compat tools
        # Previous installs (LCD->OLED switch, older DeckOps versions) can
        # leave stale launch options and compat tool entries that conflict
        # with the current install. Wipe everything for MANAGED_APPIDS
        # first, then re-apply what's needed below.
        try:
            from wrapper import clear_launch_options, clear_compat_tool
            for appid in MANAGED_APPIDS:
                clear_launch_options(self.steam_root, appid)
            clear_compat_tool(MANAGED_APPIDS)
            self._s.log.emit("✓  Cleared all launch options and compat tools")
        except Exception as ex:
            self._s.log.emit(f"  Launch option / compat tool cleanup skipped: {ex}")

        # --- Set GE-Proton compat for MANAGED_APPIDS
        # Must run AFTER kill_steam -- Steam overwrites config.vdf on exit.
        # Only write for Steam appids if the user actually has Steam games
        # selected; otherwise this may trigger Steam to re-download games.
        if ge_version and steam_sel:
            try:
                set_compat_tool(MANAGED_APPIDS, ge_version)
                self._s.log.emit(f"✓  {ge_version} set for Steam game appids")
            except Exception as ex:
                self._s.log.emit(f"  CompatToolMapping for Steam appids skipped: {ex}")

        # --- SP mod install (MW3 SP community exe)
        # Downloads AlterWare community exe that bypasses Steam CEG DRM.
        # Only triggers when the user selected the SP key specifically.
        _sp_mod_keys = [k for k in selected_keys if k == "iw5sp" and k not in own_selected]
        if _sp_mod_keys:
            from sp_mod import install_sp_mod, build_sp_launch_option, get_sp_mod_appid
            from wrapper import set_launch_options
            for _sp_key in _sp_mod_keys:
                _sp_game = next((g for k, gd, g in self.selected if k == _sp_key and g), None)
                if not _sp_game or not _sp_game.get("install_dir"):
                    continue
                _sp_dir = _sp_game["install_dir"]
                _sp_name = "MW3 SP"
                self._s.progress.emit(16, f"Installing {_sp_name} community exe...")
                self._s.log.emit(f"Installing {_sp_name} community exe...")
                try:
                    ok = install_sp_mod(
                        _sp_key, _sp_dir,
                        on_progress=lambda m: self._s.log.emit(f"  {m}"),
                    )
                    if ok:
                        cfg.mark_game_setup(_sp_key, "sp_mod", source="steam")
                        _lo = build_sp_launch_option(_sp_key)
                        _appid = get_sp_mod_appid(_sp_key)
                        if _lo and _appid:
                            set_launch_options(self.steam_root, _appid, _lo)
                            self._s.log.emit(f"✓  {_sp_name} community exe installed, launch options set")
                        else:
                            self._s.log.emit(f"✓  {_sp_name} community exe installed")
                    else:
                        self._s.log.emit(f"⚠  {_sp_name} community exe install failed")
                except Exception as ex:
                    self._s.log.emit(f"⚠  {_sp_name} SP mod skipped: {ex}")

        # --- Plutonium games
        if has_plut:
            try:
                from shortcut import create_launcher_shortcut
                create_launcher_shortcut(
                    on_progress=lambda m: self._s.log.emit(m)
                )
            except Exception as ex:
                self._s.log.emit(f"  Launcher shortcut failed: {ex}")

            # LCD: prepare Heroic's shared prefix
            if cfg.is_lcd():
                try:
                    from ge_proton import ensure_prefix_deps as _epd
                    from plutonium_lcd import HEROIC_DEFAULT_WINE_PREFIX
                    if os.path.isdir(HEROIC_DEFAULT_WINE_PREFIX):
                        _epd(
                            ge_version, HEROIC_DEFAULT_WINE_PREFIX,
                            on_progress=lambda msg: self._s.log.emit(msg),
                            proton_path=proton,
                            steam_root=self.steam_root,
                        )
                        self._s.log.emit("✓  HGL shared prefix ready")
                except Exception as ex:
                    self._s.log.emit(f"  HGL prefix deps skipped: {ex}")

            plut_selected = [(k, gd, g) for k, gd, g in self.selected
                             if KEY_CLIENT.get(k) == "plutonium"]
            installed_for_plut = {k: g for k, gd, g in self.selected if g}
            total_plut = len(plut_selected)
            for idx, (key, gd, game) in enumerate(plut_selected):
                bp = 40 + int(idx / max(total_plut, 1) * 12)
                base_name = gd["base"]
                if base_name not in logged_bases:
                    self._s.progress.emit(bp, f"Setting up {base_name}...")
                def op_plut(pct, msg, _b=bp): self._s.progress.emit(_b + int(pct / 100 * 6), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                    else:
                        _plut_appid = _PLUT_META[key][0] if key in _PLUT_META else gd["appid"]
                        compat = find_compatdata(self.steam_root, _plut_appid,
                                                  game_install_dir=game.get("install_dir"))
                    wp = install_plutonium(game, key, self.steam_root, proton, compat,
                                     on_progress=op_plut,
                                     installed_games=installed_for_plut,
                                     source=source)
                    self._mark(key, "ok")
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- T6SP-MOD (BO2 Singleplayer)
        _log_to_file("[BREADCRUMB] starting t6sp_mod install phase")
        if has_t6sp_mod:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "t6sp_mod"]:
                base_name = gd["base"]
                self._s.progress.emit(52, f"Installing Rattpak's T6SP-MOD (Beta)...")
                def op_t6sp(pct, msg): self._s.progress.emit(52 + int(pct / 100 * 4), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                    install_t6sp_mod(game, self.steam_root, proton, compat, op_t6sp, source=source)
                    cfg.mark_game_setup(key, "t6sp_mod", source=source)
                    self._mark(key, "ok")
                    self._s.log.emit(f"✓  {base_name} (T6SP-MOD) done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- IW4x
        _log_to_file("[BREADCRUMB] starting iw4x install phase")
        has_iw4x = any(KEY_CLIENT.get(k) == "iw4x" for k in selected_keys)
        if has_iw4x:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "iw4x"]:
                base_name = gd["base"]
                self._s.progress.emit(56, f"Setting up {base_name}...")
                def op_iw4x(pct, msg): self._s.progress.emit(56 + int(pct / 100 * 7), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                    _dlc_action = getattr(self, 'install_iw4x_dlc', '')
                    install_iw4x(game, self.steam_root, proton, compat, op_iw4x, source=source,
                                 install_dlc=(_dlc_action == "install"),
                                 remove_dlc=(_dlc_action == "remove"))
                    cfg.mark_game_setup(key, "iw4x", source=source)
                    self._mark(key, "ok")
                    self._s.log.emit(f"✓  {base_name} done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- T7X (BO3 AlterWare client)
        # Must run BEFORE CleanOps: CleanOps drops d3d11.dll into the
        # stock BO3 dir, and the symlink farm would pick it up if it
        # already exists. Running T7x first builds symlinks from a clean
        # stock dir, then CleanOps only touches the stock dir afterward.
        _log_to_file("[BREADCRUMB] starting t7x install phase")
        if has_t7x:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "t7x"]:
                base_name = gd["base"]
                self._s.progress.emit(70, f"Setting up T7x...")
                def op_t7x(pct, msg): self._s.progress.emit(70 + int(pct / 100 * 2), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    t7x_dir = install_t7x(game, on_progress=op_t7x)
                    game["install_dir"] = t7x_dir
                    cfg.mark_game_setup(key, "t7x", source=source)
                    self._mark(key, "ok")
                    self._s.log.emit(f"✓  {base_name} (T7x) done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} (T7x) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- CleanOps (BO3)
        _log_to_file("[BREADCRUMB] starting cleanops install phase")
        if has_cleanops:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "cleanops"]:
                base_name = gd["base"]
                self._s.progress.emit(72, f"Setting up {base_name}...")
                def op_cleanops(pct, msg): self._s.progress.emit(72 + int(pct / 100 * 4), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                    install_cleanops(game, self.steam_root, proton, compat, op_cleanops, source=source)
                    cfg.mark_game_setup(key, "cleanops", source=source)
                    self._mark(key, "ok")
                    self._s.log.emit(f"✓  {base_name} done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- AlterWare (Ghosts / Advanced Warfare)
        _log_to_file("[BREADCRUMB] starting alterware install phase")
        has_alterware = any(KEY_CLIENT.get(k) == "alterware" for k in selected_keys)
        if has_alterware:
            from alterware import install_alterware
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "alterware"]:
                base_name = gd["base"]
                self._s.progress.emit(76, f"Setting up {base_name}...")
                def op_alterware(pct, msg): self._s.progress.emit(76 + int(pct / 100 * 4), msg)
                try:
                    source = "own" if key in own_selected else "steam"
                    _appid = _GAMES_MAP[key]["appid"] if key in _GAMES_MAP else gd["appid"]
                    _install_dir = game.get("install_dir")
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                        if not compat:
                            compat = find_compatdata(self.steam_root, _appid,
                                                      game_install_dir=_install_dir)
                    else:
                        compat = find_compatdata(self.steam_root, _appid,
                                                  game_install_dir=_install_dir)
                    if not compat and _install_dir:
                        steamapps = os.path.dirname(os.path.dirname(_install_dir))
                        compat = os.path.join(steamapps, "compatdata", str(_appid))
                    install_alterware(game, key, self.steam_root, proton, compat, op_alterware,
                                     source=source)
                    cfg.mark_game_setup(key, "alterware", source=source)
                    self._mark(key, "ok")
                    self._s.log.emit(f"✓  {base_name} done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")
                    self._mark(key, "failed", str(ex))

        # --- Zombies Declassified (optional DLC5 for BO2 Zombies via Plutonium)
        if has_plut and "t6zm" in selected_keys:
            try:
                # Check BO2 Zombies DLC prerequisite
                _bo2_dir = None
                for _k, _gd, _g in self.selected:
                    if _k == "t6zm" and _g:
                        _bo2_dir = _g.get("install_dir", "")
                        break

                from zombies_declassified import has_bo2_zm_dlc
                if not _bo2_dir or not has_bo2_zm_dlc(_bo2_dir):
                    self._s.log.emit("Zombies Declassified skipped (requires all BO2 Zombies DLC)")
                else:
                    from zombies_declassified import resolve_zd_storage
                    _zd_storage = resolve_zd_storage({k: g for k, gd, g in self.selected}.get("t6zm"))

                    if _zd_storage and os.path.isdir(_zd_storage):
                        # Choice comes from the game-selection row; None means ask now (~9 GB)
                        _zd_yes = self.zd_choice
                        if _zd_yes is None:
                            self._s.progress.emit(76, "Zombies Declassified available")
                            self._s.log.emit("Zombies Declassified (DLC5) is available for BO2 Zombies.")
                            self._zd_event.clear()
                            self._zd_accept = False
                            self._s.zd_ask.emit()
                            self._zd_event.wait()
                            self._s.zd_go.emit()
                            _zd_yes = self._zd_accept

                        if _zd_yes:
                            self._s.progress.emit(76, "Installing Zombies Declassified...")
                            self._s.log.emit("Installing Zombies Declassified (DLC5 map pack)...")
                            from zombies_declassified import install_zd
                            def op_zd(pct, msg): self._s.progress.emit(76 + int(pct / 100 * 2), msg)
                            errors = install_zd(_zd_storage, op_zd)
                            from zombies_declassified import get_zd_info as _zd_info
                            info = _zd_info(_zd_storage)
                            if info.get("manifest_hash"):
                                cfg.mark_zd_installed(info["manifest_hash"])
                            if errors:
                                self._s.log.emit(f"⚠  Zombies Declassified installed with {len(errors)} error(s)")
                            else:
                                self._s.log.emit("✓  Zombies Declassified installed")
                        else:
                            self._s.log.emit("Zombies Declassified skipped (can install later from Manage)")
                    else:
                        self._s.log.emit("⚠  Zombies Declassified skipped (paths not resolved)")
            except Exception as ex:
                self._s.log.emit(f"⚠  Zombies Declassified skipped: {ex}")

        # --- Mark vanilla games
        for key, gd, game in self.selected:
            c = KEY_CLIENT.get(key, "")
            source = "own" if key in own_selected else "steam"
            # sp_mod keys land here when the AlterWare exe step failed or the game is non-Steam
            if c in ("steam", "sp_mod"):
                if not cfg.is_game_setup_for_source(key, source):
                    cfg.mark_game_setup(key, "steam", source=source)
                    self._s.log.emit(f"✓  {gd['base']} ({key}) ready")
                self._mark(key, "ok")

        # --- Game display configs
        self._s.progress.emit(78, "Applying game configs...")
        try:
            from game_config import apply_game_configs
            applied, skipped, failed = apply_game_configs(
                selected_keys=selected_keys,
                installed_games={k: g for k, gd, g in self.selected if g},
                steam_root=self.steam_root,
                deck_model=cfg.get_deck_model() or "oled",
                on_progress=lambda msg: self._s.log.emit(msg),
            )
            if applied > 0:
                self._s.log.emit(f"✓  Game display configs: {applied} written"
                                 + (f", {skipped} skipped" if skipped else "")
                                 + (f", {failed} failed" if failed else ""))
            elif skipped > 0:
                self._s.log.emit(f"⚠  Game display configs: none applied ({skipped} skipped)")
            else:
                self._s.log.emit("⚠  Game display configs: no eligible configs found")
        except Exception as ex:
            self._s.log.emit(f"  Game configs skipped: {ex}")

        # --- Controller templates
        self._s.progress.emit(88, "Installing controller templates...")
        try:
            from controller_profiles import install_controller_templates, assign_controller_profiles, assign_external_controller_profiles
            install_controller_templates(
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            gyro_mode = cfg.get_gyro_mode() or "on"
            assign_controller_profiles(
                gyro_mode,
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            self._s.log.emit(f"✓  Neptune controller profiles assigned ({gyro_mode} mode)")
            if cfg.is_docked():
                controller_type = cfg.get_external_controller() or "playstation"
                assign_external_controller_profiles(
                    controller_type,
                    gyro_mode,
                    on_progress=lambda msg: self._s.log.emit(f"  {msg}")
                )
                self._s.log.emit(f"✓  External controller profiles assigned ({controller_type})")
        except Exception as ex:
            self._s.log.emit(f"  Templates skipped: {ex}")

        try:
            from wrapper import set_steam_input_enabled
            set_steam_input_enabled(self.steam_root)
            self._s.log.emit("✓  Steam Input enabled for all games")
        except Exception as ex:
            self._s.log.emit(f"  Steam Input setup skipped: {ex}")

        # --- Write own game shortcuts (VDF, artwork, controllers, compat)
        # All mod client exes now exist on disk. write_own_shortcuts reads
        # the enrichment data set by enrich_own_games() earlier and writes
        # the actual VDF entries, downloads artwork, assigns controller
        # configs, and sets GE-Proton compat tool per shortcut.
        if has_own:
            gyro_mode = cfg.get_gyro_mode() or "on"
            self._s.progress.emit(90, "Writing own game shortcuts...")
            try:
                write_own_shortcuts(
                    own_games=own_games,
                    selected_keys=list(own_selected.keys()),
                    gyro_mode=gyro_mode,
                    on_progress=lambda msg: self._s.log.emit(msg),
                )
            except Exception as ex:
                self._s.log.emit(f"  Own shortcuts failed: {ex}")

        # --- Non-Steam shortcuts for Steam games
        steam_keys = [k for k, _, _ in steam_sel]
        if steam_sel:
            try:
                from shortcut import create_shortcuts
                self._s.log.emit("Creating non-Steam shortcuts...")
                steam_installed = {k: g for k, gd, g in steam_sel if g}
                gyro_mode = cfg.get_gyro_mode() or "on"
                create_shortcuts(
                    installed_games=steam_installed,
                    selected_keys=steam_keys,
                    gyro_mode=gyro_mode,
                    on_progress=lambda msg: self._s.log.emit(msg),
                    steam_root=self.steam_root,
                )
            except Exception as ex:
                self._s.log.emit(f"  Steam shortcuts skipped: {ex}")

            # Set default launch option so Steam Deck skips the mode picker
            has_cod4_steam = any(KEY_CLIENT.get(k) in ("cod4r", "cod4x", "iw3sp")
                                for k in steam_keys)
            has_waw_steam = any(k in ("t4sp", "t4mp") for k in steam_keys)
            defaults = {}
            if has_cod4_steam:
                defaults["7940"] = ("7a722f97", "1")   # CoD4 -> Singleplayer
            if has_waw_steam:
                defaults["10090"] = ("9aa5e05f", "0")   # WaW -> Campaign
            if defaults:
                try:
                    from wrapper import set_default_launch_option
                    set_default_launch_option(self.steam_root, defaults)
                    self._s.log.emit("✓  Default launch options set (SP mode)")
                except Exception as ex:
                    self._s.log.emit(f"  Launch options skipped: {ex}")

        # --- Steam artwork
        if steam_sel:
            self._s.progress.emit(95, "Applying Steam artwork...")
            try:
                from shortcut import apply_steam_artwork
                self._s.log.emit("Applying custom artwork for multiplayer games...")
                apply_steam_artwork(
                    selected_keys=steam_keys,
                    on_progress=lambda msg: self._s.log.emit(msg)
                )
            except Exception as ex:
                self._s.log.emit(f"  Steam artwork skipped: {ex}")

        # --- Done
        _log_to_file("[BREADCRUMB] all phases complete, finishing up")
        cfg.complete_first_run(self.steam_root)
        if has_own:
            self._DONE_MSG = (
                "Installation complete!\n\n"
                "If you enjoy these mods, please consider starring "
                "the original creators' GitHub repositories!")
        _failed = [r for r in self._results if r["status"] == "failed"]
        self._s.progress.emit(100, "All done!" if not _failed else "Finished with errors.")
        self._s.done.emit(not _failed)



# --- InstallScreen ---
class InstallScreen(_BaseInstallScreen):
    def __init__(self, stack):
        super().__init__(stack, "InstallScreen")
        self.selected = []
        self.own_selected = {}
        self.steam_selected = None



