#!/usr/bin/env python3
"""
launcher_plut.py - Offline LAN launcher for Plutonium on Steam Deck

A lightweight PyQt5 app that shows installed Plutonium games and lets
the user pick a mode (MP, S/Z, ZM) to launch in offline LAN mode.
Designed to run as a non-Steam shortcut in Game Mode at 1280x800.

Flow:
  1. Read DeckOps config to find which Plutonium keys are set up.
  2. Show compact game rows with hero background art and mode buttons.
  3. User taps a mode → launch via bash <lan_wrapper_path> → exit.

Every installed game stores a lan_wrapper_path at install time. The
wrapper is a bash script that calls Proton directly with the Plutonium
bootstrapper and -lan flag. No Steam protocol, no Heroic, no online
account needed. Works identically on OLED and LCD hardware.
"""

import os
import sys
import subprocess
import threading
import urllib.request

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy,
)
from PyQt5.QtGui import QFont, QFontDatabase, QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer, QRect

# ── paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
FONTS_DIR    = os.path.join(PROJECT_ROOT, "assets", "fonts")
HEROES_DIR   = os.path.join(PROJECT_ROOT, "assets", "images", "heroes")

os.makedirs(HEROES_DIR, exist_ok=True)

# ── colors (match DeckOps ui_qt.py) ──────────────────────────────────────────

C_BG       = "#141416"
C_CARD     = "#1E1E26"
C_IW       = "#6DC62B"
C_TREY     = "#F47B20"
C_DIM      = "#888899"
C_DARK_BTN = "#33333F"

# ── layout constants for 1280x800 ───────────────────────────────────────────

HEADER_H = 52          # top bar height
ROW_H    = 160         # each game row (fixed)
ROW_GAP  = 10          # gap between rows
PAD_X    = 16          # horizontal padding
PAD_Y    = 12          # vertical padding around rows

# ── font ─────────────────────────────────────────────────────────────────────

_FONT_FAMILY = "Sans Serif"
_FONT_LOADED = False

def _load_font():
    global _FONT_FAMILY, _FONT_LOADED
    if _FONT_LOADED:
        return
    russo = os.path.join(FONTS_DIR, "RussoOne-Regular.ttf")
    if os.path.exists(russo):
        fid = QFontDatabase.addApplicationFont(russo)
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            _FONT_FAMILY = fams[0]
    _FONT_LOADED = True

def _font(size=13, bold=False):
    f = QFont(_FONT_FAMILY, size)
    f.setBold(bold)
    return f

# ── Plutonium game data ──────────────────────────────────────────────────────

PLUT_GAMES = [
    {
        "base": "Call of Duty: World at War",
        "dev": "trey",
        "modes": [("t4mp", "MP"), ("t4sp", "S/Z")],
        "hero_url": "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/refs/heads/main/assets/images/heroes/waw-banner.png",
        "hero_file": "waw-banner.png",
    },
    {
        "base": "Call of Duty: Black Ops",
        "dev": "trey",
        "modes": [("t5mp", "MP"), ("t5sp", "S/Z")],
        "hero_url": "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/refs/heads/main/assets/images/heroes/bo1-banner.png",
        "hero_file": "bo1-banner.png",
    },
    {
        "base": "Call of Duty: Black Ops II",
        "dev": "trey",
        "modes": [("t6mp", "MP"), ("t6zm", "ZM")],
        "hero_url": "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/refs/heads/main/assets/images/heroes/bo2-banner.png",
        "hero_file": "bo2-banner.png",
    },
    {
        "base": "Call of Duty: Modern Warfare 3",
        "dev": "iw",
        "modes": [("iw5mp", "MP")],
        "hero_url": "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/refs/heads/main/assets/images/heroes/mw3-banner.png",
        "hero_file": "mw3-banner.png",
    },
]


# ── launch helper ────────────────────────────────────────────────────────

# Debounce flag — set on first launch, blocks further button clicks until
# either the launcher quits (1.5s after launch) or the timeout below clears
# it. Prevents double-launches from rapid taps on touchscreen.
_LAUNCH_FIRED = False
_LAUNCH_DEBOUNCE_MS = 3000


def _launch_lan(wrapper_path: str):
    """Run the LAN wrapper script directly, then exit."""
    global _LAUNCH_FIRED
    if _LAUNCH_FIRED:
        return
    _LAUNCH_FIRED = True

    try:
        subprocess.Popen(["bash", wrapper_path])
    except Exception as ex:
        print(f"Failed to launch LAN wrapper: {ex}", file=sys.stderr)

    # Safety: clear the flag if we somehow don't quit (e.g. Popen raised
    # before quit timer fires). 3s > 1.5s quit timer so normal flow quits
    # first; this only matters in error paths.
    def _clear():
        global _LAUNCH_FIRED
        _LAUNCH_FIRED = False
    QTimer.singleShot(_LAUNCH_DEBOUNCE_MS, _clear)

    QTimer.singleShot(1500, lambda: QApplication.instance().quit())


# ── helpers ──────────────────────────────────────────────────────────────────

def _hero_path(hero_file: str) -> str:
    return os.path.join(HEROES_DIR, hero_file)


def _get_setup_plut_keys() -> dict:
    """
    Return Plutonium game keys that have been set up, with their
    lan_wrapper_path for offline launching.

    For LCD Steam games, lan_wrapper_path in config points to the
    replaced game exe (which is a bash script). If config stored None
    (e.g. install ran without a compatdata_path), we fall back to
    reconstructing the path from the game's install_dir and the known
    exe name, so the launcher can still detect and launch them.

    Returns dict — {game_key: {"lan_wrapper_path": str|None}}
    """
    try:
        sys.path.insert(0, SCRIPT_DIR)
        import config as cfg
        setup = cfg.get_setup_games()

        # Import LCD exe map for fallback reconstruction on LCD Steam games
        try:
            from plutonium_lcd import PLUT_GAME_EXES
            _is_lcd = not cfg.is_oled()
        except Exception:
            PLUT_GAME_EXES = {}
            _is_lcd = False

        result = {}
        for k, v in setup.items():
            if v.get("client") != "plutonium":
                continue

            lan_path = v.get("lan_wrapper_path")

            # LCD Steam fallback: if lan_wrapper_path wasn't saved (e.g.
            # install ran without compatdata_path) but source is "steam",
            # reconstruct it from the install_dir + known exe name.
            # The replaced exe IS the lan wrapper for LCD Steam games.
            if (lan_path is None
                    and _is_lcd
                    and v.get("source") == "steam"
                    and k in PLUT_GAME_EXES):
                install_dir = v.get("install_dir", "")
                _, exe_name = PLUT_GAME_EXES[k]
                if install_dir:
                    candidate = os.path.join(install_dir, exe_name)
                    if os.path.exists(candidate):
                        lan_path = candidate

            result[k] = {"lan_wrapper_path": lan_path}
        return result
    except Exception:
        return {}


# ── widgets ──────────────────────────────────────────────────────────────────

class GameRow(QWidget):
    """
    A fixed-height row with a hero background image, dark overlay,
    game title, and mode launch buttons.
    """

    def __init__(self, game_def: dict, setup_info: dict, parent=None):
        super().__init__(parent)
        self._game_def = game_def
        self._bg_pixmap = None
        self._color = C_IW if game_def["dev"] == "iw" else C_TREY

        self._available = [
            (key, label) for key, label in game_def["modes"]
            if key in setup_info
        ]
        self._has_modes = len(self._available) > 0

        self.setFixedHeight(ROW_H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Load cached hero or fetch in background
        cached = _hero_path(game_def["hero_file"])
        if os.path.exists(cached):
            self._bg_pixmap = QPixmap(cached)
        else:
            threading.Thread(target=self._fetch_hero, daemon=True).start()

        # ── overlay layout ──
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        # Left side: title + badge
        left = QVBoxLayout()
        left.setSpacing(4)

        title = QLabel(game_def["base"])
        title.setFont(_font(16, bold=True))
        title.setStyleSheet("color:#FFF;background:transparent;")
        left.addWidget(title)

        badge = QLabel("LAN MODE")
        badge.setFont(_font(9, bold=True))
        badge.setFixedHeight(20)
        badge.setFixedWidth(90)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{self._color};color:#FFF;border:none;"
            f"border-radius:4px;"
        )
        left.addWidget(badge)

        lay.addLayout(left)
        lay.addStretch()

        # Right side: mode buttons
        if self._has_modes:
            for key, label in self._available:
                info = setup_info[key]
                lan_path = info.get("lan_wrapper_path")
                has_wrapper = lan_path and os.path.exists(lan_path)

                btn = QPushButton(label)
                btn.setFont(_font(14, bold=True))
                btn.setFixedSize(120, 52)

                if has_wrapper:
                    btn.setStyleSheet(
                        f"QPushButton{{background:{self._color};color:#FFF;"
                        f"border:none;border-radius:8px;}}"
                        f"QPushButton:hover{{background:{self._color}CC;}}"
                        f"QPushButton:pressed{{background:{self._color}99;}}"
                    )
                    btn.clicked.connect(
                        lambda checked=False, w=lan_path: _launch_lan(w)
                    )
                else:
                    # Installed but LAN wrapper missing — disable
                    btn.setStyleSheet(
                        f"QPushButton{{background:{C_DARK_BTN};color:{C_DIM};"
                        f"border:none;border-radius:8px;}}"
                    )
                    btn.setEnabled(False)
                    btn.setToolTip("LAN wrapper not found — reinstall may fix this")

                lay.addWidget(btn, alignment=Qt.AlignVCenter)
        else:
            no_lbl = QLabel("Not installed")
            no_lbl.setFont(_font(13))
            no_lbl.setStyleSheet(f"color:{C_DIM};background:transparent;")
            lay.addWidget(no_lbl, alignment=Qt.AlignVCenter)

    def paintEvent(self, event):
        """Draw hero background with dark overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()

        # Background fallback
        painter.fillRect(rect, QColor(C_CARD))

        # Draw hero image: scale to fill width, crop vertically from center
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            pw = self._bg_pixmap.width()
            ph = self._bg_pixmap.height()
            rw = rect.width()
            rh = rect.height()

            # How tall the source region needs to be (in source pixels)
            # to fill the row when scaled to row width
            scale = rw / pw
            src_h_needed = int(rh / scale)
            src_y = max(0, (ph - src_h_needed) // 2)
            src_rect = QRect(0, src_y, pw, min(src_h_needed, ph))

            painter.drawPixmap(rect, self._bg_pixmap, src_rect)

        # Dark overlay — only for uninstalled games. Installed games show
        # their hero art unobstructed so the row reads as bright/active.
        if not self._has_modes:
            painter.fillRect(rect, QColor(0, 0, 0, int(255 * 0.85)))

        # Accent border on left edge
        painter.fillRect(QRect(0, 0, 3, rect.height()), QColor(self._color))

        painter.end()
        super().paintEvent(event)

    def _fetch_hero(self):
        url = self._game_def.get("hero_url")
        if not url:
            return
        try:
            dest = _hero_path(self._game_def["hero_file"])
            urllib.request.urlretrieve(url, dest)
            pix = QPixmap(dest)
            if not pix.isNull():
                self._bg_pixmap = pix
                QTimer.singleShot(0, self.update)
        except Exception:
            pass


class LauncherWindow(QWidget):
    """Main fullscreen launcher window — fits 1280x800 with no scrolling."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeckOps Offline")
        self.setStyleSheet(f"background:{C_BG};")

        setup_info = _get_setup_plut_keys()

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── header bar ──
        hdr = QWidget()
        hdr.setFixedHeight(HEADER_H)
        hdr.setStyleSheet(f"background:{C_CARD};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel("DECKOPS")
        title.setFont(_font(20, bold=True))
        title.setStyleSheet(f"color:{C_TREY};background:transparent;")
        hl.addWidget(title)

        subtitle = QLabel("OFFLINE")
        subtitle.setFont(_font(12))
        subtitle.setStyleSheet(f"color:{C_DIM};background:transparent;")
        subtitle.setContentsMargins(8, 4, 0, 0)
        hl.addWidget(subtitle)
        hl.addStretch()

        quit_btn = QPushButton("✕")
        quit_btn.setFont(_font(16, bold=True))
        quit_btn.setFixedSize(44, 44)
        quit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C_DIM};border:none;"
            f"border-radius:8px;}}"
            f"QPushButton:hover{{background:{C_DARK_BTN};color:#FFF;}}"
        )
        quit_btn.clicked.connect(QApplication.instance().quit)
        hl.addWidget(quit_btn)
        root_lay.addWidget(hdr)

        # ── game rows ──
        rows_container = QWidget()
        rows_container.setStyleSheet(f"background:{C_BG};")
        rows_lay = QVBoxLayout(rows_container)
        rows_lay.setContentsMargins(PAD_X, PAD_Y, PAD_X, PAD_Y)
        rows_lay.setSpacing(ROW_GAP)

        # Installed games first, then uninstalled
        installed = []
        uninstalled = []
        for game_def in PLUT_GAMES:
            has_any = any(k in setup_info for k, _ in game_def["modes"])
            row = GameRow(game_def, setup_info)
            if has_any:
                installed.append(row)
            else:
                uninstalled.append(row)

        for row in installed:
            rows_lay.addWidget(row)
        for row in uninstalled:
            rows_lay.addWidget(row)

        rows_lay.addStretch()
        root_lay.addWidget(rows_container)

        # ── empty state ──
        if not setup_info:
            empty = QLabel(
                "No Plutonium games installed.\n"
                "Run the DeckOps installer first."
            )
            empty.setFont(_font(14))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{C_DIM};background:transparent;")
            rows_lay.insertWidget(0, empty)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    _load_font()

    win = LauncherWindow()
    win.showFullScreen()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
