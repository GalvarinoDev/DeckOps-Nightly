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

Gamepad input is read via evdev in a QObject worker moved to a QThread.
The worker emits pyqtSignals which Qt auto-marshals to main-thread slots
via queued connections — the canonical thread-safe Qt pattern.

DEBUG BUILD: gamepad code paths log to ~/gamepad.log for diagnostics.
"""

import os
import sys
import subprocess
import threading
import urllib.request
import time
import traceback

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy,
)
from PyQt5.QtGui import QFont, QFontDatabase, QPixmap, QPainter, QColor
from PyQt5.QtCore import (
    Qt, QTimer, QRect, QObject, QThread, pyqtSignal, pyqtSlot,
)

# ── paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
FONTS_DIR    = os.path.join(PROJECT_ROOT, "assets", "fonts")
HEROES_DIR   = os.path.join(PROJECT_ROOT, "assets", "images", "heroes")
MUSIC_PATH   = os.path.join(PROJECT_ROOT, "assets", "music", "background.mp3")

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
        "modes": [("iw5mp", "MP"), ("iw5mp_ds", "MP")],
        "hero_url": "https://raw.githubusercontent.com/GalvarinoDev/DeckOps-Nightly/refs/heads/main/assets/images/heroes/mw3-banner.png",
        "hero_file": "mw3-banner.png",
    },
]


# ── debug logger ─────────────────────────────────────────────────────────────

# Writes timestamped lines to ~/gamepad.log. Truncates on first call so each
# launcher run starts with a fresh log. Best-effort — never raises.

_LOG_PATH = os.path.expanduser("~/gamepad.log")
_LOG_LOCK = threading.Lock()
_LOG_INITIALIZED = False


def _log(msg: str):
    global _LOG_INITIALIZED
    try:
        with _LOG_LOCK:
            mode = "a" if _LOG_INITIALIZED else "w"
            _LOG_INITIALIZED = True
            with open(_LOG_PATH, mode) as f:
                ts = time.strftime("%H:%M:%S")
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ── gamepad reader (QObject in QThread) ──────────────────────────────────────

# evdev key/abs codes for the Steam Deck's built-in controller (also matches
# Xbox layout for external controllers).
_EV_BTN_SOUTH = 304   # A
_EV_BTN_EAST  = 305   # B
_EV_ABS_HAT0X = 16    # D-pad horizontal: -1 left, 0 center, 1 right
_EV_ABS_HAT0Y = 17    # D-pad vertical:   -1 up,   0 center, 1 down
_EV_ABS_X     = 0     # Left stick horizontal
_EV_ABS_Y     = 1     # Left stick vertical

# Analog stick deadzone — values are typically -32768..32767. Anything within
# +/- this is treated as centered. 12000 is comfortable on the Deck.
_STICK_DEADZONE = 12000


def _find_gamepad():
    """Return the first device that looks like a gamepad, or None."""
    _log("_find_gamepad: entered")
    try:
        from evdev import InputDevice, list_devices, ecodes
        _log("_find_gamepad: evdev imported OK")
    except ImportError as ex:
        _log(f"_find_gamepad: ImportError on evdev: {ex}")
        return None
    try:
        paths = list_devices()
        _log(f"_find_gamepad: list_devices returned {len(paths)} paths: {paths}")
        for path in paths:
            try:
                dev = InputDevice(path)
                caps = dev.capabilities()
                keys = caps.get(ecodes.EV_KEY, [])
                has_south = _EV_BTN_SOUTH in keys
                _log(f"_find_gamepad:   {path} name={dev.name!r} "
                     f"BTN_SOUTH={has_south}")
                if has_south:
                    _log(f"_find_gamepad: SELECTED {path} ({dev.name!r})")
                    return dev
            except Exception as ex:
                _log(f"_find_gamepad:   {path} skipped: {ex}")
                continue
    except Exception as ex:
        _log(f"_find_gamepad: outer exception: {ex}")
        _log(traceback.format_exc())
    _log("_find_gamepad: NO GAMEPAD FOUND")
    return None


class GamepadReader(QObject):
    """
    QObject worker that reads evdev events in its own thread and emits
    pyqtSignals for each navigation action. Signals connect to slots on
    LauncherWindow via Qt's auto-connection — because the reader lives
    in a different thread than the window, Qt automatically uses queued
    connections, which marshal the slot call onto the main thread's
    event loop. This is the canonical Qt pattern for worker → GUI
    communication and is fully thread-safe.
    """

    move_row       = pyqtSignal(int)   # +1 / -1
    move_btn       = pyqtSignal(int)   # +1 / -1
    activate       = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._device = None
        # Stick edge-detection state — only emit on transition from
        # centered to past-deadzone, not on every event while held.
        self._stick_x_dir = 0   # -1, 0, +1
        self._stick_y_dir = 0

    @pyqtSlot()
    def run(self):
        _log("GamepadReader.run: entered (worker thread)")
        self._device = _find_gamepad()
        if self._device is None:
            _log("GamepadReader.run: no device found, exiting worker")
            return

        try:
            from evdev import ecodes
        except ImportError as ex:
            _log(f"GamepadReader.run: evdev import failed: {ex}")
            return

        _log(f"GamepadReader.run: reading events from {self._device.path}")
        event_count = 0
        try:
            for event in self._device.read_loop():
                event_count += 1
                # Detailed logging for the first 50 events; after that
                # only log meaningful key/abs transitions to keep the log
                # readable.
                if event_count <= 50:
                    _log(f"event #{event_count} type={event.type} "
                         f"code={event.code} value={event.value}")

                if event.type == ecodes.EV_KEY and event.value == 1:
                    if event.code == _EV_BTN_SOUTH:
                        _log("emit activate")
                        self.activate.emit()
                    elif event.code == _EV_BTN_EAST:
                        _log("emit quit_requested")
                        self.quit_requested.emit()

                elif event.type == ecodes.EV_ABS:
                    if event.code == _EV_ABS_HAT0X:
                        if event.value < 0:
                            _log("emit move_btn(-1)  [HAT0X<0]")
                            self.move_btn.emit(-1)
                        elif event.value > 0:
                            _log("emit move_btn(+1)  [HAT0X>0]")
                            self.move_btn.emit(+1)
                    elif event.code == _EV_ABS_HAT0Y:
                        if event.value < 0:
                            _log("emit move_row(-1)  [HAT0Y<0]")
                            self.move_row.emit(-1)
                        elif event.value > 0:
                            _log("emit move_row(+1)  [HAT0Y>0]")
                            self.move_row.emit(+1)
                    elif event.code == _EV_ABS_X:
                        # Left stick horizontal — emit on edge only.
                        new_dir = (
                            -1 if event.value < -_STICK_DEADZONE
                            else +1 if event.value > _STICK_DEADZONE
                            else 0
                        )
                        if new_dir != self._stick_x_dir:
                            self._stick_x_dir = new_dir
                            if new_dir != 0:
                                _log(f"emit move_btn({new_dir:+d})  [stick X]")
                                self.move_btn.emit(new_dir)
                    elif event.code == _EV_ABS_Y:
                        # Left stick vertical — emit on edge only.
                        new_dir = (
                            -1 if event.value < -_STICK_DEADZONE
                            else +1 if event.value > _STICK_DEADZONE
                            else 0
                        )
                        if new_dir != self._stick_y_dir:
                            self._stick_y_dir = new_dir
                            if new_dir != 0:
                                _log(f"emit move_row({new_dir:+d})  [stick Y]")
                                self.move_row.emit(new_dir)
        except Exception as ex:
            _log(f"GamepadReader.run: read_loop exception: {ex}")
            _log(traceback.format_exc())
        _log(f"GamepadReader.run: exited after {event_count} events")


# ── audio (background music) ─────────────────────────────────────────────

# Plays the same background.mp3 the installer uses, at half the user's
# saved music_volume (launcher is transient and shouldn't compete with
# the game it's about to launch). Reads music_enabled / music_volume from
# DeckOps config so the user's preferences carry over from the installer.
# pygame is wrapped in try/except — if unavailable, launcher works
# silently without music rather than crashing.

LAUNCHER_VOLUME_MULT = 0.5
FADEOUT_MS           = 1000


def _pygame_available():
    try:
        import pygame  # noqa: F401
        return True
    except ImportError:
        return False


def _audio_volume() -> float:
    try:
        sys.path.insert(0, SCRIPT_DIR)
        import config as cfg
        return cfg.get_music_volume() * LAUNCHER_VOLUME_MULT
    except Exception:
        return 0.2


def _audio_enabled() -> bool:
    try:
        sys.path.insert(0, SCRIPT_DIR)
        import config as cfg
        return cfg.get_music_enabled()
    except Exception:
        return True


def _start_audio():
    if not _audio_enabled() or not _pygame_available():
        return
    if not os.path.exists(MUSIC_PATH):
        return
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.load(MUSIC_PATH)
            pygame.mixer.music.set_volume(_audio_volume())
            pygame.mixer.music.play(-1)
    except Exception:
        pass


def _fadeout_audio(ms: int = FADEOUT_MS):
    if not _pygame_available():
        return
    try:
        import pygame
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(ms)
    except Exception:
        pass


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

    _fadeout_audio()

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
        # Priority: if both iw5mp (full game) and iw5mp_ds (free DS) are
        # available, keep only iw5mp — they're the same Plutonium client.
        avail_keys = {k for k, _ in self._available}
        if "iw5mp" in avail_keys and "iw5mp_ds" in avail_keys:
            self._available = [(k, l) for k, l in self._available
                               if k != "iw5mp_ds"]
        self._has_modes = len(self._available) > 0

        # Gamepad/keyboard focus state — managed by LauncherWindow
        self._row_focused = False
        self._mode_buttons = []   # list of (btn, lan_path) for available modes
        self._focused_btn_idx = None

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
                # Disable Qt's built-in focus rect — we draw our own focus
                # ring via stylesheet so it matches the gamepad focus model.
                btn.setFocusPolicy(Qt.NoFocus)

                if has_wrapper:
                    self._apply_btn_style(btn, focused=False)
                    btn.clicked.connect(
                        lambda checked=False, w=lan_path: _launch_lan(w)
                    )
                    self._mode_buttons.append((btn, lan_path))
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

    def _apply_btn_style(self, btn: QPushButton, focused: bool):
        """Apply launchable button style with optional focus ring."""
        if focused:
            # White inner border simulates a focus ring on top of the
            # accent color, readable on both orange and green.
            btn.setStyleSheet(
                f"QPushButton{{background:{self._color};color:#FFF;"
                f"border:3px solid #FFFFFF;border-radius:8px;}}"
                f"QPushButton:pressed{{background:{self._color}99;}}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:{self._color};color:#FFF;"
                f"border:none;border-radius:8px;}}"
                f"QPushButton:hover{{background:{self._color}CC;}}"
                f"QPushButton:pressed{{background:{self._color}99;}}"
            )

    def launchable_count(self) -> int:
        """Number of mode buttons that can actually launch (have wrappers)."""
        return len(self._mode_buttons)

    def trigger_focused_button(self):
        """Invoke the launch action for the currently focused button."""
        if self._focused_btn_idx is None:
            return
        if 0 <= self._focused_btn_idx < len(self._mode_buttons):
            _, lan_path = self._mode_buttons[self._focused_btn_idx]
            _launch_lan(lan_path)

    def set_row_focused(self, focused: bool):
        """Set whether this row has the active row focus (border highlight)."""
        if self._row_focused == focused:
            return
        self._row_focused = focused
        if not focused:
            # Clear button focus when row loses focus
            self.set_focused_button(None)
        self.update()

    def set_focused_button(self, idx):
        """Highlight the mode button at idx (or clear if None)."""
        if self._focused_btn_idx == idx:
            return
        # Clear old
        if self._focused_btn_idx is not None and \
                0 <= self._focused_btn_idx < len(self._mode_buttons):
            old_btn, _ = self._mode_buttons[self._focused_btn_idx]
            self._apply_btn_style(old_btn, focused=False)
        # Apply new
        self._focused_btn_idx = idx
        if idx is not None and 0 <= idx < len(self._mode_buttons):
            new_btn, _ = self._mode_buttons[idx]
            self._apply_btn_style(new_btn, focused=True)

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

        # Row focus border (gamepad/keyboard navigation indicator).
        # 4px border in the row's accent color, drawn over the left stripe.
        if self._row_focused:
            border = 4
            c = QColor(self._color)
            painter.fillRect(QRect(0, 0, rect.width(), border), c)  # top
            painter.fillRect(QRect(0, rect.height() - border,
                                    rect.width(), border), c)        # bottom
            painter.fillRect(QRect(0, 0, border, rect.height()), c)  # left
            painter.fillRect(QRect(rect.width() - border, 0,
                                    border, rect.height()), c)       # right

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
        _log(f"LauncherWindow: setup_info has {len(setup_info)} entries")

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
        # NoFocus so keyboard/gamepad input goes to the window's keyPressEvent
        # instead of being eaten by the button.
        quit_btn.setFocusPolicy(Qt.NoFocus)
        quit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C_DIM};border:none;"
            f"border-radius:8px;}}"
            f"QPushButton:hover{{background:{C_DARK_BTN};color:#FFF;}}"
        )
        quit_btn.clicked.connect(self._quit_with_fade)
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

        # ── gamepad / keyboard focus tracking ──
        # Only rows with launchable buttons participate in focus navigation.
        # Uninstalled rows (and rows where every button is disabled because
        # the wrapper is missing) are skipped entirely.
        self._focus_rows = [r for r in installed if r.launchable_count() > 0]
        _log(f"LauncherWindow: _focus_rows has {len(self._focus_rows)} entries")
        self._row_idx = 0
        if self._focus_rows:
            self._focus_rows[0].set_row_focused(True)
            self._focus_rows[0].set_focused_button(0)

        # Steam Deck Game Mode default mapping passes D-pad as arrow keys,
        # A as Return, B as Escape — Qt sees these as keyPressEvents below
        # so no controller config file is needed for default behavior.
        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event):
        key = event.key()
        _log(f"keyPressEvent: key={key}")

        if key == Qt.Key_Escape:
            self._quit_with_fade()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._activate_focused()
            return
        if key == Qt.Key_Up:
            self.on_move_row(-1)
            return
        if key == Qt.Key_Down:
            self.on_move_row(+1)
            return
        if key == Qt.Key_Left:
            self.on_move_btn(-1)
            return
        if key == Qt.Key_Right:
            self.on_move_btn(+1)
            return

        super().keyPressEvent(event)

    # ── slots invoked from gamepad signals (queued connection) ────────────
    # These run on the main thread because the GamepadReader lives in a
    # different QThread and Qt automatically uses queued connections in
    # that case. Slots are identical in shape to the old _move_* methods
    # so the keyboard path can call them directly too.

    @pyqtSlot(int)
    def on_move_row(self, delta: int):
        _log(f"on_move_row: delta={delta} cur={self._row_idx} "
             f"rows={len(self._focus_rows)}")
        if not self._focus_rows:
            return
        new_idx = max(0, min(len(self._focus_rows) - 1, self._row_idx + delta))
        if new_idx == self._row_idx:
            return
        self._focus_rows[self._row_idx].set_row_focused(False)
        self._row_idx = new_idx
        self._focus_rows[self._row_idx].set_row_focused(True)
        self._focus_rows[self._row_idx].set_focused_button(0)

    @pyqtSlot(int)
    def on_move_btn(self, delta: int):
        _log(f"on_move_btn: delta={delta}")
        if not self._focus_rows:
            return
        row = self._focus_rows[self._row_idx]
        n = row.launchable_count()
        if n == 0:
            return
        cur = row._focused_btn_idx if row._focused_btn_idx is not None else 0
        new_idx = max(0, min(n - 1, cur + delta))
        row.set_focused_button(new_idx)

    @pyqtSlot()
    def _activate_focused(self):
        _log("_activate_focused called")
        if not self._focus_rows:
            return
        self._focus_rows[self._row_idx].trigger_focused_button()

    @pyqtSlot()
    def _quit_with_fade(self):
        """Fade audio out, then quit once fadeout completes."""
        _log("_quit_with_fade called")
        _fadeout_audio()
        QTimer.singleShot(FADEOUT_MS, QApplication.instance().quit)


# ── main ─────────────────────────────────────────────────────────────────────

def _cleanup_shader_caches():
    """
    Clean accumulated fozpipelinesv6 shader cache files for all
    DeckOps-managed Plutonium appids. Called once on launcher startup
    to prevent the cache from growing unbounded across sessions.

    See: https://github.com/ValveSoftware/steam-for-linux/issues/10486
    """
    try:
        from cache_cleanup import cleanup_shader_cache, STEAM_APPIDS
        for game_key in STEAM_APPIDS:
            try:
                cleanup_shader_cache(game_key, "steam")
            except Exception:
                pass
        _log("_cleanup_shader_caches: done")
    except ImportError:
        _log("_cleanup_shader_caches: cache_cleanup module not found, skipping")
    except Exception as ex:
        _log(f"_cleanup_shader_caches: {ex}")


def main():
    _log("=" * 60)
    _log(f"main: starting launcher_plut.py")
    _log(f"main: argv={sys.argv}")
    _log(f"main: python={sys.executable}")
    _log(f"main: cwd={os.getcwd()}")
    _log(f"main: DISPLAY={os.environ.get('DISPLAY', '<unset>')}")
    _log(f"main: WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '<unset>')}")
    _log(f"main: XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '<unset>')}")

    # Clean shader caches before showing UI — sub-second, no visible delay.
    _cleanup_shader_caches()

    app = QApplication(sys.argv)
    _load_font()

    win = LauncherWindow()
    win.showFullScreen()
    # Explicitly grab keyboard focus. setFocusPolicy(StrongFocus) alone is
    # insufficient under gamescope (Steam Deck Game Mode) -- without these
    # calls the window is visible and accepts mouse input but never receives
    # keyPressEvents, so D-pad/keyboard navigation appears dead.
    win.activateWindow()
    win.raise_()
    win.setFocus()
    _start_audio()

    # ── start gamepad reader on its own QThread ────────────────────────────
    # Pattern: QObject worker + moveToThread + queued signal/slot connections.
    # This is the canonical thread-safe way to bridge a blocking read loop
    # to GUI updates in Qt. Both objects must outlive main() — keep them as
    # attributes on the window so they aren't garbage-collected.
    win._gp_thread = QThread()
    win._gp_reader = GamepadReader()
    win._gp_reader.moveToThread(win._gp_thread)

    # Connect navigation signals to window slots. Auto-connection sees the
    # cross-thread affinity and uses queued connections automatically.
    win._gp_reader.move_row.connect(win.on_move_row)
    win._gp_reader.move_btn.connect(win.on_move_btn)
    win._gp_reader.activate.connect(win._activate_focused)
    win._gp_reader.quit_requested.connect(win._quit_with_fade)

    # Start the reader's run() once the thread's event loop is up.
    win._gp_thread.started.connect(win._gp_reader.run)
    win._gp_thread.start()
    _log("main: gamepad QThread started")

    _log("main: entering Qt event loop")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
