"""
ui_manifest.py -- optional manifest mods step before the game scan

Lists manifest .json files found in the Games folders, lets the user
tick mods, pick one option each, enter the shared CDN and a target
Games folder, then installs. Skipped entirely when no manifests exist.
"""

import html, os, threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QCheckBox, QRadioButton,
    QButtonGroup, QProgressBar, QLineEdit, QPlainTextEdit,
)
from PyQt5.QtCore import Qt

import inhibit
import manifest_mods as mm
from net import _fmt_size

from ui_constants import (
    C_CARD, C_IW, C_TREY, C_DIM, C_DARK_BTN,
    font, _btn, _lbl, _header_bar, _log_to_file, _log_html, _copy_log_to_clipboard, _Sigs, go_to,
)

_CB_CSS = "color:#FFF;background:transparent;"
_OPT_CSS = "color:#CCC;background:transparent;"


class ManifestModsScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "ManifestModsScreen"
        self._found = []; self._rows = []; self._busy = False; self._roots = []

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        lay.addWidget(_header_bar()[0])
        content = QWidget(); clay = QVBoxLayout(content); clay.setContentsMargins(60,20,60,30); clay.setSpacing(12)

        clay.addWidget(_lbl("Optional mods found in your Games folder. Tick the ones to install, "
                            "or skip to continue to the game scan.", 13, C_DIM))
        self.status = _lbl("Looking for mod manifests...", 13, C_DIM); clay.addWidget(self.status)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._lw = QWidget(); self._list = QVBoxLayout(self._lw)
        self._list.setContentsMargins(0,0,0,0); self._list.setSpacing(10); self._list.addStretch()
        scroll.setWidget(self._lw); clay.addWidget(scroll, stretch=1)

        crow = QHBoxLayout(); crow.setSpacing(12)
        crow.addWidget(_lbl("Mod CDN:", 13, "#FFF", bold=True, align=Qt.AlignLeft, wrap=False))
        self.cdn = QLineEdit(); self.cdn.setPlaceholderText("cdn.example.com/mods"); self.cdn.setFixedHeight(44)
        self.cdn.setFont(font(13))
        self.cdn.setStyleSheet(f"QLineEdit{{background:{C_CARD};color:#FFF;border:2px solid #33333F;"
                               f"border-radius:8px;padding:0 14px;}}QLineEdit:focus{{border-color:{C_IW};}}")
        crow.addWidget(self.cdn, 1); clay.addLayout(crow)

        self._root_row = QHBoxLayout(); self._root_row.setSpacing(16)
        self._root_row.addWidget(_lbl("Install to:", 13, "#FFF", bold=True, align=Qt.AlignLeft, wrap=False))
        self._root_grp = QButtonGroup(self); self._root_grp.buttonClicked.connect(lambda _b: self._refresh_rows())
        self._root_row.addStretch(); clay.addLayout(self._root_row)

        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False); self.bar.setFixedHeight(14)
        self.bar.setVisible(False); clay.addWidget(self.bar)
        self.prog = _lbl("", 12, C_DIM, align=Qt.AlignLeft); self.prog.setVisible(False); clay.addWidget(self.prog)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(font(11))
        self.log.setStyleSheet("QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}")
        self.log.setVisible(False); clay.addWidget(self.log, stretch=1)
        self._log_status = _lbl("", 11, C_DIM, wrap=False)
        self._log_btn = _btn("Copy Log", C_DARK_BTN, size=11, h=40); self._log_btn.setFixedWidth(130)
        self._log_btn.clicked.connect(lambda: _copy_log_to_clipboard(self._log_status))
        self._log_btn.setVisible(False); self._log_status.setVisible(False)
        lr = QHBoxLayout(); lr.addStretch(); lr.addWidget(self._log_btn); lr.addWidget(self._log_status); lr.addStretch()
        clay.addLayout(lr)

        self.warning = _lbl("", 12, C_TREY, align=Qt.AlignLeft); self.warning.setVisible(False)
        self.warning.setTextFormat(Qt.RichText); clay.addWidget(self.warning)

        brow = QHBoxLayout(); brow.setSpacing(16)
        self.back = _btn("<< Back", C_DARK_BTN, h=52); self.back.setFixedWidth(180)
        self.back.clicked.connect(lambda: go_to(self.stack, "SetupFlowScreen"))
        self.inst = _btn("Install Selected", C_IW, h=52); self.inst.clicked.connect(self._install)
        self.cont = _btn("Skip >>", C_DARK_BTN, h=52); self.cont.setFixedWidth(220)
        self.cont.clicked.connect(lambda: go_to(self.stack, "WelcomeScreen"))
        brow.addWidget(self.back); brow.addWidget(self.inst, 1); brow.addWidget(self.cont); clay.addLayout(brow)
        lay.addWidget(content, stretch=1)

    def showEvent(self, e):
        super().showEvent(e)
        if self._busy: return
        self.warning.setVisible(False); self.bar.setVisible(False); self.prog.setVisible(False)
        self.cont.setText("Skip >>"); self._set_enabled(False)
        self.status.setText("Looking for mod manifests...")
        self._sigs = _Sigs(); self._sigs.done.connect(self._on_scanned)
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        try:
            self._found = mm.scan_manifests(); self._roots = mm.games_roots()
        except Exception as ex:
            _log_to_file(f"[ManifestModsScreen] scan failed: {ex}"); self._found = []
        self._sigs.done.emit(bool(self._found))

    def _on_scanned(self, any_found):
        # Nothing to offer: go straight on to the game scan.
        if not any_found:
            go_to(self.stack, "WelcomeScreen"); return
        ok = [f for f in self._found if "manifest" in f]
        self.status.setText(f"Found {len(ok)} mod(s)." + (f" {len(self._found) - len(ok)} could not be read."
                                                           if len(ok) < len(self._found) else ""))
        if not self.cdn.text(): self.cdn.setText(mm.get_saved_cdn())
        self._build_roots(); self._build_rows(); self._set_enabled(True)

    def _build_roots(self):
        for b in self._root_grp.buttons():
            self._root_grp.removeButton(b); b.deleteLater()
        home = os.path.expanduser("~")
        saved = {mm.get_saved(f["manifest"]["id"]).get("games_root") for f in self._found if "manifest" in f}
        for i, r in enumerate(self._roots):
            label = "Internal: ~/" + os.path.relpath(r, home) if r.startswith(home + os.sep) else f"SD / drive: {r}"
            rb = QRadioButton(label); rb.setFont(font(12)); rb.setStyleSheet(_OPT_CSS); rb.setProperty("root", r)
            rb.setChecked(r in saved or (i == 0 and not saved & set(self._roots)))
            self._root_grp.addButton(rb); self._root_row.insertWidget(self._root_row.count() - 1, rb)

    def _root(self):
        b = self._root_grp.checkedButton()
        return b.property("root") if b else ""

    def _build_rows(self):
        while self._list.count() > 1:
            it = self._list.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        self._rows = []
        for f in self._found:
            card = QWidget(); card.setObjectName("mmcard")
            card.setStyleSheet(f"#mmcard{{background:{C_CARD};border-radius:8px;}}")
            v = QVBoxLayout(card); v.setContentsMargins(16,12,16,12); v.setSpacing(6)
            if "error" in f:
                v.addWidget(_lbl(f"{f['file']}: {f['error']}", 12, C_DIM, align=Qt.AlignLeft))
                self._list.insertWidget(self._list.count() - 1, card); continue
            m = f["manifest"]
            head = QHBoxLayout()
            cb = QCheckBox(m["name"] + (f"  v{m['version']}" if m["version"] else ""))
            cb.setFont(font(13, True)); cb.setStyleSheet(_CB_CSS); head.addWidget(cb, 1)
            state = _lbl("", 11, C_DIM, align=Qt.AlignRight, wrap=False); head.addWidget(state)
            v.addLayout(head)
            if m["description"]: v.addWidget(_lbl(m["description"], 11, C_DIM, align=Qt.AlignLeft))
            orow = QHBoxLayout(); orow.setContentsMargins(28,0,0,0); orow.setSpacing(18)
            if m["mode"] == "components":
                grp, boxes = None, []
                for c in m["components"]:
                    if not c["show"]: continue
                    ob = QCheckBox(f"{c['name']}  ({_fmt_size(sum(x['size'] for x in c['files']))})"); ob.setFont(font(11))
                    ob.setStyleSheet(_OPT_CSS); ob.setProperty("oid", c["id"]); ob.setProperty("req", c["required"]); ob.setProperty("def", c["default"])
                    ob.setChecked(c["required"] or c["default"]); ob.setEnabled(not c["required"])
                    if c["description"]: ob.setToolTip(c["description"])
                    # Ticking a part ticks the mod without re-running the mod's check-all.
                    ob.toggled.connect(lambda on, mc=cb: (on and not mc.isChecked() and (mc.blockSignals(True), mc.setChecked(True), mc.blockSignals(False)),
                                                          self._update_total()))
                    boxes.append(ob); orow.addWidget(ob)
                cb.toggled.connect(lambda on, bs=boxes: ([b.setChecked(on) for b in bs if not b.property("req")], self._update_total()))
            else:
                grp, boxes = QButtonGroup(card), None
                for i, o in enumerate(m["options"]):
                    rb = QRadioButton(f"{o['name']}  ({_fmt_size(mm.total_size(o))})"); rb.setFont(font(11))
                    rb.setStyleSheet(_OPT_CSS); rb.setProperty("oid", o["id"]); rb.setChecked(i == 0); rb.setEnabled(False)
                    if o["description"]: rb.setToolTip(o["description"])
                    grp.addButton(rb); orow.addWidget(rb)
                cb.toggled.connect(lambda on, g=grp: ([b.setEnabled(on) for b in g.buttons()], self._update_total()))
                grp.buttonClicked.connect(lambda _b: self._update_total())
            orow.addStretch(); v.addLayout(orow)
            self._rows.append({"m": m, "cb": cb, "grp": grp, "boxes": boxes, "state": state})
            self._list.insertWidget(self._list.count() - 1, card)
        self._refresh_rows()

    def _refresh_rows(self):
        root = self._root()
        for r in self._rows:
            mid = r["m"]["id"]; iroot = mm.install_root(root, r["m"]) if root else ""
            rec = mm.get_receipt(iroot, mid) if iroot else {}
            if r["boxes"] is not None:
                # Tick what is installed in this Games folder, so installing more parts keeps the old ones.
                have = set((rec.get("option") or "").split("+")) if rec else None
                for b in r["boxes"]:
                    if b.property("req"): continue
                    b.blockSignals(True); b.setChecked(b.property("oid") in have if have is not None else bool(b.property("def"))); b.blockSignals(False)
            if not rec:
                r["state"].setText("")
            elif not rec.get("complete"):
                r["state"].setText("Incomplete, install again to finish"); r["state"].setStyleSheet(f"color:{C_TREY};background:transparent;")
            elif mm.needs_update(r["m"], iroot):
                r["state"].setText("Update available"); r["state"].setStyleSheet(f"color:{C_TREY};background:transparent;")
            else:
                try: name = mm.get_option(r["m"], rec.get("option"))["name"]
                except mm.ManifestError: name = ""
                r["state"].setText(f"Installed: {name}"); r["state"].setStyleSheet(f"color:{C_IW};background:transparent;")
        self._update_total()

    def _selected(self):
        out = []
        for r in self._rows:
            if not r["cb"].isChecked(): continue
            if r["boxes"] is not None:
                out.append((r["m"], "+".join(b.property("oid") for b in r["boxes"] if b.isChecked())))
            elif r["grp"].checkedButton():
                out.append((r["m"], r["grp"].checkedButton().property("oid")))
        return out

    def _update_total(self):
        sel = self._selected()
        size = sum(mm.total_size(mm.get_option(m, oid)) for m, oid in sel)
        self.inst.setText(f"Install Selected ({_fmt_size(size)})" if sel else "Install Selected")
        self.inst.setEnabled(bool(sel) and not self._busy)

    def _set_enabled(self, on):
        self.back.setEnabled(on); self.cont.setEnabled(on); self.cdn.setEnabled(on); self._lw.setEnabled(on)
        for b in self._root_grp.buttons(): b.setEnabled(on)
        if on: self._update_total()
        else: self.inst.setEnabled(False)

    def _warn(self, text, color=C_TREY):
        self.warning.setText(text); self.warning.setStyleSheet(f"color:{color};background:transparent;")
        self.warning.setVisible(True)

    def _install(self):
        sel = self._selected(); root = self._root()
        if not sel: return
        if not root: self._warn("Choose where to install the mods."); return
        try:
            cdn = mm.normalize_cdn(self.cdn.text())
        except mm.ManifestError as ex:
            self._warn(f"Mod CDN: {html.escape(str(ex))}"); return
        self._busy = True; self._set_enabled(False); self.warning.setVisible(False)
        self.bar.setValue(0); self.bar.setVisible(True); self.prog.setVisible(True)
        self.log.clear(); self.log.setVisible(True); self._log_btn.setVisible(True); self._log_status.setVisible(False)
        self._isigs = _Sigs()
        self._isigs.progress.connect(lambda p, m: (self.bar.setValue(p), self.prog.setText(m)))
        self._isigs.log.connect(self._append_log)
        self._isigs.done.connect(self._on_installed)
        threading.Thread(target=self._do_install, args=(sel, cdn, root), daemon=True).start()

    def _do_install(self, sel, cdn, root):
        self._results = []; n = len(sel)
        log = self._isigs.log.emit
        inhibit.start("DeckOps is installing mods")
        try:
            for i, (m, oid) in enumerate(sel):
                opt = mm.get_option(m, oid)
                log(f"--- {m['name']} ({opt['name']}) ---")
                tag = f"[{i + 1}/{n}] {m['name']}: "
                cb = lambda p, msg, _i=i, _t=tag: self._isigs.progress.emit(int((_i * 100 + p) / n), _t + msg)
                try:
                    errs = mm.install_manifest(m, oid, cdn, root, cb, on_log=log)
                    if errs:
                        log(f"✗ {len(errs)} file(s) failed")
                    else:
                        log(f"✓ {opt['name']} installed")
                    self._results.append((m, oid, errs, ""))
                except mm.ManifestError as ex:
                    log(f"✗ {ex}")
                    self._results.append((m, oid, None, str(ex)))
                except Exception as ex:
                    _log_to_file(f"[ManifestModsScreen] {m['id']} install failed: {ex}")
                    log(f"✗ unexpected error: {ex}")
                    self._results.append((m, oid, None, "unexpected error, see log"))
        finally:
            inhibit.stop()
        self._isigs.done.emit(all(e == [] for _m, _o, e, _x in self._results))

    def _append_log(self, text):
        _log_to_file(text)
        sb = self.log.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.log.appendHtml(_log_html(text))
        if at_bottom: sb.setValue(sb.maximum())

    def _on_installed(self, all_ok):
        self._busy = False; self.bar.setValue(100)
        lines = []
        for m, oid, errs, msg in self._results:
            name = html.escape(f"{m['name']} ({mm.get_option(m, oid)['name']})")
            if errs == []:
                lines.append(f'<span style="color:{C_IW}">&#10003; {name} installed</span>')
            elif errs:
                lines.append(f'<span style="color:{C_TREY}">&#10007; {name}: {len(errs)} file(s) failed. '
                             f'Install again to retry only those.</span>')
            else:
                lines.append(f'<span style="color:{C_TREY}">&#10007; {name}: {html.escape(msg)}</span>')
        self._warn("<br>".join(lines), C_IW if all_ok else C_TREY)
        self.prog.setText("Done." if all_ok else "Finished with errors.")
        self.cont.setText("Continue >>")
        self._set_enabled(True); self._refresh_rows()
