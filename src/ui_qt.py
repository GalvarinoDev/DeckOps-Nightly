"""
ui_qt.py — DeckOps PyQt5 UI
"""

import sys, os, subprocess, threading
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QCheckBox, QProgressBar,
    QFrame, QSizePolicy, QMessageBox, QPlainTextEdit,
    QFileDialog, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QFontDatabase, QPixmap
from PyQt5.QtWidgets import QGraphicsOpacityEffect

import bootstrap as _bootstrap
from detect_games import find_steam_root, parse_library_folders, find_installed_games
import config as cfg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR    = os.path.join(PROJECT_ROOT, "assets", "fonts")
HEADERS_DIR  = os.path.join(PROJECT_ROOT, "assets", "images", "headers")
MUSIC_PATH   = os.path.join(PROJECT_ROOT, "assets", "music", "background.mp3")
LOG_DIR      = os.path.join(PROJECT_ROOT, "logs")
LOG_PATH     = os.path.join(LOG_DIR, "install.log")

os.makedirs(HEADERS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


def _log_to_file(text: str):
    """Append a timestamped line to the install log file."""
    from datetime import datetime
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {text}\n")
    except Exception:
        pass

C_BG       = "#141416"
C_CARD     = "#1E1E26"
C_IW       = "#6DC62B"
C_TREY     = "#F47B20"
C_DIM      = "#888899"
C_DARK_BTN = "#33333F"
C_RED_BTN  = "#7A1515"
C_BLUE_BTN = "#1A5FAA"

_FONT_FAMILY      = "Sans Serif"
_FONT_FAMILY_DISP = "Sans Serif"
_FONT_LOADED      = False

def _load_font():
    global _FONT_FAMILY, _FONT_FAMILY_DISP, _FONT_LOADED
    if _FONT_LOADED:
        return
    russo = os.path.join(FONTS_DIR, "RussoOne-Regular.ttf")
    if not os.path.exists(russo):
        raise FileNotFoundError(
            f"Required font not found: {russo}\n"
            f"Ensure assets/fonts/RussoOne-Regular.ttf is present in the repo."
        )
    fid = QFontDatabase.addApplicationFont(russo)
    fams = QFontDatabase.applicationFontFamilies(fid)
    if fams:
        _FONT_FAMILY      = fams[0]
        _FONT_FAMILY_DISP = fams[0]
    _FONT_LOADED = True

def font(size=13, bold=False, weight=None, display=False):
    family = _FONT_FAMILY_DISP if display else _FONT_FAMILY
    f = QFont(family, size)
    if weight is not None:
        f.setWeight(weight)
    else:
        f.setBold(bold)
    return f

# ── Game card definitions ─────────────────────────────────────────────────────
#
# Each entry is one card in the UI. Always 6 cards, but what each card shows
# depends on the Deck model. OLED users get the full key list. LCD users get
# a reduced set via the lcd_* overrides:
#
#   lcd_keys   — which game keys this card includes on LCD (empty = card hidden)
#   lcd_client — client badge label on LCD (e.g. "steam" instead of "plutonium")
#   lcd_appid  — appid used for the header image and Steam store link on LCD
#
# If an lcd_* field is missing, the card uses the default (OLED) value.
# The _active_keys(), _active_client(), _active_appid() helpers below
# resolve the correct value based on the user's saved deck_model config.

ALL_GAMES = [
    {"base":"Call of Duty 4: Modern Warfare","keys":["cod4mp","cod4sp"],"appid":7940,"dev":"iw","client":"cod4x + iw3sp",
     "launch_note":"DeckOps creates Proton prefixes automatically."},
    {"base":"Call of Duty: Modern Warfare 2","keys":["iw4mp","iw4sp"],"appid":10190,"dev":"iw","client":"iw4x",
     "launch_note":"DeckOps creates Proton prefixes automatically."},
    {"base":"Call of Duty: Modern Warfare 3","keys":["iw5mp","iw5sp"],"appid":42690,"dev":"iw","client":"plutonium",
     "lcd_keys":["iw5mp","iw5sp"],"lcd_client":"plutonium + steam","lcd_appid":42680,
     "launch_note":"DeckOps creates Proton prefixes automatically."},
    {"base":"Call of Duty: World at War","keys":["t4sp","t4mp"],"appid":10090,"dev":"trey","client":"plutonium",
     "lcd_keys":["t4sp","t4mp"],"lcd_client":"plutonium",
     "launch_note":"DeckOps creates Proton prefixes automatically."},
    {"base":"Call of Duty: Black Ops","keys":["t5sp","t5mp"],"appid":42700,"dev":"trey","client":"plutonium",
     "lcd_keys":["t5sp","t5mp"],"lcd_client":"plutonium",
     "launch_note":"DeckOps creates Proton prefixes automatically."},
    {"base":"Call of Duty: Black Ops II","keys":["t6mp","t6zm","t6sp"],"appid":202990,"dev":"trey","client":"plutonium",
     "lcd_keys":["t6sp","t6zm","t6mp"],"lcd_client":"plutonium + steam","lcd_appid":202970,
     "launch_note":"DeckOps creates Proton prefixes automatically."},
]

def _active_keys(gd):
    """Return the keys to show for this card based on the user's Deck model."""
    if cfg.is_oled():
        return gd["keys"]
    return gd.get("lcd_keys", gd["keys"])

def _active_client(gd):
    """Return the client label for this card based on the user's Deck model."""
    if cfg.is_oled():
        return gd["client"]
    return gd.get("lcd_client", gd["client"])

def _active_appid(gd):
    """Return the display appid for this card based on the user's Deck model."""
    if cfg.is_oled():
        return gd["appid"]
    return gd.get("lcd_appid", gd["appid"])

KEY_CLIENT = {
    "cod4mp": "cod4x",
    "cod4sp": "iw3sp",
    "iw4mp":  "iw4x",
    "iw4sp":  "steam",
    "iw5mp":  "plutonium",
    "iw5sp":  "steam",
    "t4sp":   "plutonium",
    "t4mp":   "plutonium",
    "t5sp":   "plutonium",
    "t5mp":   "plutonium",
    "t6zm":   "plutonium",
    "t6mp":   "plutonium",
    "t6sp":   "steam",
}

KEY_EXES = {
    "cod4mp":"iw3mp.exe","cod4sp":"iw3sp.exe",
    "iw4mp":"iw4mp.exe","iw4sp":"iw4sp.exe",
    "iw5mp":"iw5mp.exe","iw5sp":"iw5sp.exe",
    "t4sp":"CoDWaW.exe","t4mp":"CoDWaWmp.exe",
    "t5sp":"BlackOps.exe","t5mp":"BlackOpsMP.exe",
    "t6zm":"t6zm.exe","t6mp":"t6mp.exe","t6sp":"t6sp.exe",
}

# Label shown beneath each per-key checkbox in SetupScreen.
KEY_MODE_LABEL = {
    "cod4mp": "MP",    "cod4sp": "SP",
    "iw4mp":  "MP",    "iw4sp":  "SP",
    "iw5mp":  "MP",    "iw5sp":  "SP",
    "t4sp":   "S/Z",   "t4mp":   "MP",
    "t5sp":   "S/Z",   "t5mp":   "MP",
    "t6sp":   "SP",    "t6zm":   "ZM",    "t6mp":   "MP",
}


SP_IMAGE_URLS = {
    7940:   "https://shared.steamstatic.com/store_item_assets/steam/apps/7940/header.jpg",
    10180:  "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/header.jpg",
    10190:  "https://shared.steamstatic.com/store_item_assets/steam/apps/10180/header.jpg",
    42680:  "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/header.jpg",
    42690:  "https://shared.steamstatic.com/store_item_assets/steam/apps/42680/header.jpg",
    10090:  "https://shared.steamstatic.com/store_item_assets/steam/apps/10090/header.jpg",
    42700:  "https://shared.steamstatic.com/store_item_assets/steam/apps/42700/header.jpg",
    202970: "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/header.jpg",
    202990: "https://shared.steamstatic.com/store_item_assets/steam/apps/202970/header.jpg",
}

IMG_RATIO = 215 / 460
BTN_RATIO = 0.20
CARD_COLS = 3

MUSIC_URL = "https://archive.org/download/adrenaline-klickaud/Adrenaline_KLICKAUD.mp3"

_music_volume  = cfg.get_music_volume()
_music_enabled = cfg.get_music_enabled()

def _pygame_available():
    try:
        import pygame
        return True
    except ImportError:
        return False

def _kill_audio():
    if not _pygame_available():
        return
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
    except Exception:
        pass

def _start_audio():
    if not _music_enabled or not _pygame_available():
        return
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if not pygame.mixer.music.get_busy():
            if os.path.exists(MUSIC_PATH):
                pygame.mixer.music.load(MUSIC_PATH)
            else:
                return
            pygame.mixer.music.set_volume(_music_volume)
            pygame.mixer.music.play(-1)
    except Exception:
        pass

def _set_audio_volume(vol: float):
    global _music_volume
    _music_volume = vol
    cfg.set_music_volume(vol)
    if not _pygame_available():
        return
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(vol)
    except Exception:
        pass

def _set_audio_enabled(enabled: bool):
    global _music_enabled
    _music_enabled = enabled
    cfg.set_music_enabled(enabled)

def _header_path(appid: int) -> str:
    return os.path.join(HEADERS_DIR, f"{appid}.jpg")

def _btn(text, color, size=13, h=44):
    b = QPushButton(text); b.setFont(font(size, True)); b.setFixedHeight(h)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:#FFF;border:none;border-radius:8px;padding:0 18px;}}"
        f"QPushButton:hover{{background:{color}CC;}}"
        f"QPushButton:pressed{{background:{color}99;}}"
        f"QPushButton:disabled{{background:#333344;color:#666677;}}"
    )
    return b

def _lbl(text, size=14, color="#FFF", bold=False, align=Qt.AlignCenter, wrap=True):
    w = QLabel(text); w.setFont(font(size,bold)); w.setAlignment(align)
    w.setWordWrap(wrap); w.setStyleSheet(f"color:{color};background:transparent;")
    return w

def _hdiv():
    d = QFrame(); d.setFrameShape(QFrame.HLine); d.setFixedHeight(1)
    d.setStyleSheet("background:#252530;border:none;"); return d

def _title_block(lay, main_size=56):
    t = QLabel("DECKOPS")
    t.setFont(font(main_size, display=True))
    t.setAlignment(Qt.AlignCenter)
    t.setStyleSheet("color:#FFFFFF; background:transparent;")
    lay.addWidget(t)
    sub = QLabel()
    sub.setTextFormat(Qt.RichText)
    sub.setAlignment(Qt.AlignCenter)
    sub.setStyleSheet(f"color:{C_TREY}; background:transparent;")
    sub.setText(
        f'<span style="font-family:\'{_FONT_FAMILY_DISP}\'; font-size:28pt; color:{C_TREY};">'
        f'COMBAT'
        f'<span style="font-size:16pt;">on</span>'
        f'DECK'
        f'</span>'
    )
    lay.addWidget(sub)
    # Nightly build badge — shown on every screen so users always know
    # they are running the experimental build and not the stable release.
    nightly = QLabel("NIGHTLY BUILD")
    nightly.setFont(font(10, bold=True))
    nightly.setAlignment(Qt.AlignCenter)
    nightly.setStyleSheet(
        "color:#F47B20;background:#2A1A08;border:1px solid #F47B20;"
        "border-radius:4px;padding:2px 10px;"
    )
    nw = QHBoxLayout(); nw.addStretch(); nw.addWidget(nightly); nw.addStretch()
    lay.addLayout(nw)

class _Sigs(QObject):
    progress    = pyqtSignal(int, str)
    log         = pyqtSignal(str)
    done        = pyqtSignal(bool)
    plut_wait   = pyqtSignal()
    plut_go     = pyqtSignal()
    pulse_start = pyqtSignal(str)
    pulse_stop  = pyqtSignal()

# ── BootstrapScreen ────────────────────────────────────────────────────────────
class BootstrapScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "BootstrapScreen"
        lay = QVBoxLayout(self); lay.setContentsMargins(80,80,80,80); lay.setSpacing(14)
        lay.addStretch()
        _title_block(lay)
        lay.addStretch()
        self.status = _lbl("Preparing...", 13, C_DIM)
        lay.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(14)
        bw = QHBoxLayout(); bw.addStretch(); bw.addWidget(self.bar,6); bw.addStretch()
        lay.addLayout(bw); lay.addSpacing(50)

    def showEvent(self, e):
        super().showEvent(e)
        _start_audio()
        if _bootstrap.all_ready():
            QTimer.singleShot(300, self._proceed); return
        self._s = _Sigs()
        self._s.progress.connect(lambda p,m: (self.bar.setValue(p), self.status.setText(m)))
        self._s.done.connect(lambda _: QTimer.singleShot(300, self._proceed))
        threading.Thread(target=lambda: _bootstrap.run(
            on_progress=lambda p,m: self._s.progress.emit(p,m),
            on_complete=lambda ok: self._s.done.emit(ok),
        ), daemon=True).start()

    def _proceed(self):
        # Re-load font and re-apply stylesheet now that bootstrap has completed.
        # This is a no-op if the font was already loaded at startup, but ensures
        # the correct font is applied even on a fresh install where bootstrap
        # runs for the first time.
        try:
            _load_font()
            QApplication.instance().setStyleSheet(_app_style())
        except FileNotFoundError:
            pass  # Font missing — fall back gracefully, app still works

        if cfg.is_first_run():
            self.stack.setCurrentIndex(9)
        else:
            root = find_steam_root()
            self.stack.widget(5).set_installed(find_installed_games(parse_library_folders(root)))
            self.stack.setCurrentIndex(5)

# ── IntroScreen ────────────────────────────────────────────────────────────────
class IntroScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "IntroScreen"
        self._selected_model = ""

        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0,0,0,0)

        # ── Model section (first screen) ──────────────────────────────────────
        self._model_section = QWidget()
        lay = QVBoxLayout(self._model_section); lay.setContentsMargins(80,60,80,60); lay.setSpacing(16)
        _title_block(lay)
        lay.addSpacing(8)
        lay.addWidget(_lbl(
            "DeckOps sets up community multiplayer clients for your Call of Duty games "
            "on Steam Deck, so you can play online with the best possible performance "
            "and shader cache benefits.", 14, "#CCCCCC"))
        lay.addSpacing(6)
        for warn in [
            "⚠   DeckOps will automatically create Proton prefixes for your games. "
            "You do NOT need to launch each game through Steam first. "
            "If you have already launched your games, DeckOps will detect the existing prefixes "
            "and skip this step.",
            "⚠   If you plan to play Plutonium titles online (WaW, BO1, BO2, MW3), "
            "create a free Plutonium account at plutonium.pw before continuing.",
        ]:
            lay.addWidget(_lbl(warn, 13, C_TREY, align=Qt.AlignLeft))
        lay.addSpacing(16)

        lay.addWidget(_lbl("Which Steam Deck do you have?", 15, "#CCC"))
        brow = QHBoxLayout(); brow.setSpacing(20)
        lcd  = _btn("Steam Deck LCD", C_DARK_BTN, h=56)
        oled = _btn("Steam Deck OLED", C_IW, h=56)
        lcd.clicked.connect(lambda: self._pick_model("lcd"))
        oled.clicked.connect(lambda: self._pick_model("oled"))
        brow.addWidget(lcd); brow.addWidget(oled)
        lay.addLayout(brow)
        main_lay.addWidget(self._model_section)

        # ── Gyro section (second screen, replaces model section) ──────────────
        self._gyro_section = QWidget(); self._gyro_section.setVisible(False)
        gl = QVBoxLayout(self._gyro_section); gl.setContentsMargins(80,60,80,60); gl.setSpacing(16)

        # Back button top-left showing which model was picked
        self._back_btn = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_btn.setFixedWidth(80)
        self._back_btn.clicked.connect(self._back_to_model)
        back_row = QHBoxLayout()
        back_row.addWidget(self._back_btn); back_row.addStretch()
        gl.addLayout(back_row)

        gl.addStretch()
        _title_block(gl)
        gl.addSpacing(16)
        gl.addWidget(_lbl("How do you want to activate gyro aiming?", 15, "#CCC"))
        gl.addSpacing(4)
        gl.addWidget(_lbl(
            "Hold  —  gyro is active while R5 (right grip) is held down.\n"
            "ADS  —  gyro activates when you aim down sights.\n"
            "Toggle  —  press R5 once to turn gyro on, press again to turn it off.",
            13, C_DIM, align=Qt.AlignLeft))
        gl.addSpacing(12)
        grow = QHBoxLayout(); grow.setSpacing(20)
        hold_btn   = _btn("Hold",   C_DARK_BTN, h=56)
        ads_btn    = _btn("ADS",    C_DARK_BTN, h=56)
        toggle_btn = _btn("Toggle", C_DARK_BTN, h=56)
        hold_btn.clicked.connect(lambda: self._pick_gyro("hold"))
        ads_btn.clicked.connect(lambda: self._pick_gyro("ads"))
        toggle_btn.clicked.connect(lambda: self._pick_gyro("toggle"))
        grow.addWidget(hold_btn); grow.addWidget(ads_btn); grow.addWidget(toggle_btn)
        gl.addLayout(grow)
        gl.addStretch()
        main_lay.addWidget(self._gyro_section)

        # ── Player name section (after gyro, before play mode) ────────────────
        self._name_section = QWidget(); self._name_section.setVisible(False)
        nl = QVBoxLayout(self._name_section); nl.setContentsMargins(80,60,80,60); nl.setSpacing(16)

        self._back_gyro_name_btn = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_gyro_name_btn.setFixedWidth(80)
        self._back_gyro_name_btn.clicked.connect(self._back_to_gyro_from_name)
        back_row_name = QHBoxLayout()
        back_row_name.addWidget(self._back_gyro_name_btn); back_row_name.addStretch()
        nl.addLayout(back_row_name)

        nl.addStretch()
        _title_block(nl)
        nl.addSpacing(16)
        nl.addWidget(_lbl("What's your player name?", 15, "#CCC"))
        nl.addSpacing(4)
        nl.addWidget(_lbl(
            "This name will be used in CoD4x, IW4x, and Plutonium (LCD offline mode). "
            "Your Steam display name is filled in by default — change it to whatever you want.",
            13, C_DIM, align=Qt.AlignLeft))
        nl.addSpacing(12)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Player")
        self._name_input.setMaxLength(24)
        self._name_input.setFixedHeight(48)
        self._name_input.setFont(font(14))
        self._name_input.setStyleSheet(
            f"QLineEdit{{background:{C_CARD};color:#FFF;border:2px solid #33333F;"
            f"border-radius:8px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{C_IW};}}"
        )
        nl.addWidget(self._name_input)
        nl.addSpacing(16)

        name_continue = _btn("Continue >>", C_IW, h=52)
        name_continue.setFixedWidth(260)
        name_continue.clicked.connect(self._save_player_name)
        nc_row = QHBoxLayout(); nc_row.addStretch(); nc_row.addWidget(name_continue); nc_row.addStretch()
        nl.addLayout(nc_row)
        nl.addStretch()
        main_lay.addWidget(self._name_section)

        # ── Play mode section (third screen, replaces gyro section) ──────────
        self._play_section = QWidget(); self._play_section.setVisible(False)
        pl = QVBoxLayout(self._play_section); pl.setContentsMargins(80,60,80,60); pl.setSpacing(16)

        self._back_gyro_btn = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_gyro_btn.setFixedWidth(80)
        self._back_gyro_btn.clicked.connect(self._back_to_gyro)
        back_row2 = QHBoxLayout()
        back_row2.addWidget(self._back_gyro_btn); back_row2.addStretch()
        pl.addLayout(back_row2)

        pl.addStretch()
        _title_block(pl)
        pl.addSpacing(16)
        pl.addWidget(_lbl("How do you play?", 15, "#CCC"))
        pl.addSpacing(4)
        pl.addWidget(_lbl(
            "Handheld Only  --  you play exclusively on the Steam Deck screen.\n"
            "Also Docked  --  you also connect to a TV or monitor with an external controller.\n"
            "Choosing Docked will install the DeckOps Decky plugin. "
            "Decky Loader is required — you can install it after setup from decky.xyz.",
            13, C_DIM, align=Qt.AlignLeft))
        pl.addSpacing(12)
        prow = QHBoxLayout(); prow.setSpacing(20)
        handheld_btn = _btn("Handheld Only", C_DARK_BTN, h=56)
        docked_btn   = _btn("Also Docked",   C_DARK_BTN, h=56)
        handheld_btn.clicked.connect(lambda: self._pick_play_mode("handheld"))
        docked_btn.clicked.connect(lambda: self._pick_play_mode("docked"))
        prow.addWidget(handheld_btn); prow.addWidget(docked_btn)
        pl.addLayout(prow)
        pl.addStretch()
        main_lay.addWidget(self._play_section)

        # ── Decky install section (docked users only, shown while plugin downloads) ──
        self._decky_section = QWidget(); self._decky_section.setVisible(False)
        dl = QVBoxLayout(self._decky_section); dl.setContentsMargins(80,60,80,60); dl.setSpacing(16)

        self._back_decky_btn = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_decky_btn.setFixedWidth(80)
        self._back_decky_btn.clicked.connect(self._back_to_play_from_decky)
        back_row_decky = QHBoxLayout()
        back_row_decky.addWidget(self._back_decky_btn); back_row_decky.addStretch()
        dl.addLayout(back_row_decky)

        dl.addStretch()
        _title_block(dl)
        dl.addSpacing(8)
        self._decky_status_lbl = _lbl("Installing DeckOps Decky plugin...", 15, "#CCC")
        dl.addWidget(self._decky_status_lbl)
        dl.addSpacing(4)

        self._decky_log = QPlainTextEdit()
        self._decky_log.setReadOnly(True)
        self._decky_log.setFont(font(11))
        self._decky_log.setStyleSheet(
            "QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}"
        )
        self._decky_log.setFixedHeight(180)
        dl.addWidget(self._decky_log)

        self._decky_cont_btn = _btn("Continue  >>", C_IW, size=13, h=52)
        self._decky_cont_btn.setFixedWidth(320)
        self._decky_cont_btn.setVisible(False)
        self._decky_cont_btn.clicked.connect(self._decky_continue)
        dcw = QHBoxLayout(); dcw.addStretch(); dcw.addWidget(self._decky_cont_btn); dcw.addStretch()
        dl.addLayout(dcw)

        self._decky_retry_btn = _btn("Retry", C_TREY, size=13, h=52)
        self._decky_retry_btn.setFixedWidth(320)
        self._decky_retry_btn.setVisible(False)
        self._decky_retry_btn.clicked.connect(self._start_decky_install)
        drw = QHBoxLayout(); drw.addStretch(); drw.addWidget(self._decky_retry_btn); drw.addStretch()
        dl.addLayout(drw)

        dl.addStretch()
        main_lay.addWidget(self._decky_section)

        self._decky_sigs = _Sigs()
        self._decky_sigs.log.connect(self._decky_append_log)
        self._decky_sigs.done.connect(self._decky_on_done)

        # ── Resolution section (docked users only, between play mode and controller) ──
        # NOTE: this will also be used for future Bazzite, Steam Box, and
        # other handheld support on SteamOS where the native screen isn't 1280x800.
        self._resolution_section = QWidget(); self._resolution_section.setVisible(False)
        rl = QVBoxLayout(self._resolution_section); rl.setContentsMargins(80,60,80,60); rl.setSpacing(16)

        self._back_play_btn2 = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_play_btn2.setFixedWidth(80)
        self._back_play_btn2.clicked.connect(self._back_to_play_from_res)
        back_row_res = QHBoxLayout()
        back_row_res.addWidget(self._back_play_btn2); back_row_res.addStretch()
        rl.addLayout(back_row_res)

        rl.addStretch()
        _title_block(rl)
        rl.addSpacing(16)
        rl.addWidget(_lbl("What resolution is your external display?", 15, "#CCC"))
        rl.addSpacing(4)
        rl.addWidget(_lbl(
            "Default is 1280x800 (Steam Deck screen). Pick the resolution that matches "
            "your TV or monitor, or choose My Own to set it yourself in-game.",
            13, C_DIM, align=Qt.AlignLeft))
        rl.addSpacing(12)

        res_cols = QHBoxLayout(); res_cols.setSpacing(20)

        # Left column: 16:10
        col_1610 = QVBoxLayout(); col_1610.setSpacing(10)
        col_1610.addWidget(_lbl("16:10", 13, C_IW, bold=True))
        res_800 = _btn("1280 x 800", C_DARK_BTN, h=52)
        res_1200 = _btn("1920 x 1200", C_DARK_BTN, h=52)
        res_800.clicked.connect(lambda: self._pick_resolution("1280x800"))
        res_1200.clicked.connect(lambda: self._pick_resolution("1920x1200"))
        col_1610.addWidget(res_800); col_1610.addWidget(res_1200)
        res_cols.addLayout(col_1610)

        # Right column: 16:9
        col_169 = QVBoxLayout(); col_169.setSpacing(10)
        col_169.addWidget(_lbl("16:9", 13, C_IW, bold=True))
        res_720 = _btn("1280 x 720", C_DARK_BTN, h=52)
        res_1080 = _btn("1920 x 1080", C_DARK_BTN, h=52)
        res_720.clicked.connect(lambda: self._pick_resolution("1280x720"))
        res_1080.clicked.connect(lambda: self._pick_resolution("1920x1080"))
        col_169.addWidget(res_720); col_169.addWidget(res_1080)
        res_cols.addLayout(col_169)

        rl.addLayout(res_cols)
        rl.addSpacing(8)

        # Centered "My Own" button
        own_res_btn = _btn("My Own", C_DARK_BTN, h=44)
        own_res_btn.setFixedWidth(200)
        own_res_btn.clicked.connect(lambda: self._pick_resolution("own"))
        own_row = QHBoxLayout(); own_row.addStretch(); own_row.addWidget(own_res_btn); own_row.addStretch()
        rl.addLayout(own_row)

        rl.addStretch()
        main_lay.addWidget(self._resolution_section)

        # ── Controller type section (docked users only, after resolution) ─────
        self._controller_section = QWidget(); self._controller_section.setVisible(False)
        cl = QVBoxLayout(self._controller_section); cl.setContentsMargins(80,60,80,60); cl.setSpacing(16)

        self._back_res_btn = _btn("← Back", C_DARK_BTN, size=10, h=30)
        self._back_res_btn.setFixedWidth(80)
        self._back_res_btn.clicked.connect(self._back_to_resolution)
        back_row3 = QHBoxLayout()
        back_row3.addWidget(self._back_res_btn); back_row3.addStretch()
        cl.addLayout(back_row3)

        cl.addStretch()
        _title_block(cl)
        cl.addSpacing(16)
        cl.addWidget(_lbl("What external controller do you use?", 15, "#CCC"))
        cl.addSpacing(4)
        cl.addWidget(_lbl(
            "PlayStation  --  PS5 or PS4 DualShock/DualSense. Includes gyro aiming.\n"
            "Xbox  --  Xbox 360 or Xbox One controller. Standard layout, no gyro.\n"
            "Other  --  Generic or 8BitDo controller. Standard layout, no gyro.",
            13, C_DIM, align=Qt.AlignLeft))
        cl.addSpacing(12)
        crow = QHBoxLayout(); crow.setSpacing(20)
        ps_btn      = _btn("PlayStation", C_DARK_BTN, h=56)
        xbox_btn    = _btn("Xbox",        C_DARK_BTN, h=56)
        other_btn   = _btn("Other",       C_DARK_BTN, h=56)
        ps_btn.clicked.connect(lambda: self._pick_controller("playstation"))
        xbox_btn.clicked.connect(lambda: self._pick_controller("xbox"))
        other_btn.clicked.connect(lambda: self._pick_controller("other"))
        crow.addWidget(ps_btn); crow.addWidget(xbox_btn); crow.addWidget(other_btn)
        cl.addLayout(crow)
        cl.addStretch()
        main_lay.addWidget(self._controller_section)

    def _back_to_model(self):
        self._gyro_section.setVisible(False)
        self._model_section.setVisible(True)

    def _back_to_gyro(self):
        self._play_section.setVisible(False)
        self._name_section.setVisible(True)

    def _back_to_gyro_from_name(self):
        self._name_section.setVisible(False)
        self._gyro_section.setVisible(True)

    def _show_name_section(self):
        """Show the player name input, pre-filled with Steam display name."""
        # Pre-fill with Steam name if the field is empty and no name saved yet
        if not self._name_input.text():
            saved = cfg.get_player_name()
            if saved:
                self._name_input.setText(saved)
            else:
                steam_name = cfg.get_steam_display_name()
                if steam_name:
                    self._name_input.setText(steam_name)
        self._gyro_section.setVisible(False)
        self._name_section.setVisible(True)

    def _save_player_name(self):
        """Save the player name and proceed to the next step."""
        name = self._name_input.text().strip()
        if name:
            cfg.set_player_name(name)
        else:
            cfg.set_player_name("Player")
        # Continue to play mode (advanced) or next screen (standard)
        self._name_section.setVisible(False)
        source = cfg.get_game_source() or "steam"
        if source == "steam":
            self._next_screen()
        else:
            # Advanced flow: check if play mode already set
            play_mode = cfg.get_play_mode()
            if play_mode:
                if play_mode == "handheld":
                    self._next_screen()
                elif cfg.get_docked_resolution() and cfg.get_external_controller():
                    self._next_screen()
                elif cfg.get_docked_resolution():
                    self._controller_section.setVisible(True)
                else:
                    self._resolution_section.setVisible(True)
            else:
                self._play_section.setVisible(True)

    def _back_to_play_from_res(self):
        self._resolution_section.setVisible(False)
        self._play_section.setVisible(True)

    def _back_to_resolution(self):
        self._controller_section.setVisible(False)
        self._resolution_section.setVisible(True)

    def _pick_model(self, model):
        cfg.set_deck_model(model)
        self._model_section.setVisible(False)
        self._gyro_section.setVisible(True)

    def _next_screen(self):
        """Route to the correct next screen based on game_source."""
        source = cfg.get_game_source() or "steam"
        if source == "own":
            self.stack.setCurrentIndex(11)   # OwnScanScreen
        else:
            self.stack.setCurrentIndex(2)    # WelcomeScreen (standard)

    def _pick_gyro(self, mode):
        cfg.set_gyro_mode(mode)
        self._show_name_section()

    def _pick_play_mode(self, mode):
        cfg.set_play_mode(mode)
        if mode == "docked":
            self._play_section.setVisible(False)
            self._decky_section.setVisible(True)
            self._decky_log.clear()
            self._decky_cont_btn.setVisible(False)
            self._decky_retry_btn.setVisible(False)
            self._decky_status_lbl.setText("Installing DeckOps Decky plugin...")
            self._decky_back_btn_set_enabled(False)
            self._start_decky_install()
        else:
            self._next_screen()

    def _decky_back_btn_set_enabled(self, enabled):
        self._back_decky_btn.setEnabled(enabled)

    def _back_to_play_from_decky(self):
        self._decky_section.setVisible(False)
        self._play_section.setVisible(True)

    def _decky_append_log(self, text):
        self._decky_log.appendPlainText(text)
        self._decky_log.verticalScrollBar().setValue(
            self._decky_log.verticalScrollBar().maximum()
        )

    def _decky_on_done(self, ok):
        self._decky_back_btn_set_enabled(True)
        if ok:
            self._decky_status_lbl.setText("✓  Decky plugin installed.")
            self._decky_cont_btn.setVisible(True)
        else:
            self._decky_status_lbl.setText("✗  Install failed. Check your connection and retry.")
            self._decky_retry_btn.setVisible(True)

    def _decky_continue(self):
        self._decky_section.setVisible(False)
        self._resolution_section.setVisible(True)

    def _start_decky_install(self):
        self._decky_cont_btn.setVisible(False)
        self._decky_retry_btn.setVisible(False)
        self._decky_back_btn_set_enabled(False)
        self._decky_status_lbl.setText("Installing DeckOps Decky plugin...")
        s = self._decky_sigs

        def _run():
            import urllib.request
            ZIP_URL  = "https://github.com/GalvarinoDev/DeckOps-Nightly/raw/main/DeckOps.zip"
            dl_dir   = os.path.expanduser("~/Downloads")
            zip_path = os.path.join(dl_dir, "DeckOps.zip")
            try:
                os.makedirs(dl_dir, exist_ok=True)
                s.log.emit("→  Downloading DeckOps.zip...")
                urllib.request.urlretrieve(ZIP_URL, zip_path)
                s.log.emit(f"   ✓  Saved to {zip_path}")
                s.log.emit("   Install via Decky → Install from zip.")
                s.done.emit(True)
            except Exception as ex:
                s.log.emit(f"✗  {ex}")
                s.done.emit(False)

        threading.Thread(target=_run, daemon=True).start()

    def _pick_resolution(self, resolution):
        cfg.set_docked_resolution(resolution)
        if not cfg.get_external_controller():
            # Still need to pick controller type
            self._resolution_section.setVisible(False)
            self._controller_section.setVisible(True)
        else:
            self._next_screen()

    def _pick_controller(self, controller_type):
        cfg.set_external_controller(controller_type)
        self._next_screen()

# ── WelcomeScreen ──────────────────────────────────────────────────────────────
class WelcomeScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.installed={}; self.screen_name = "WelcomeScreen"
        self.steam_installed={}; self.own_installed={}; self.steam_root=""
        self._steam_only = False  # set by OwnScanScreen skip or advanced flow
        lay = QVBoxLayout(self); lay.setContentsMargins(80,60,80,60); lay.setSpacing(14)
        _title_block(lay)
        lay.addSpacing(12)
        self.status = _lbl("Scanning for Steam...", 14, C_DIM)
        lay.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(14)
        bw = QHBoxLayout(); bw.addStretch(); bw.addWidget(self.bar,6); bw.addStretch()
        lay.addLayout(bw)
        lay.addSpacing(10)
        self.results = _lbl("", 13, C_IW)
        self.results.setTextFormat(Qt.RichText)
        lay.addWidget(self.results)
        lay.addStretch()
        self.cont = _btn("Continue >>", C_IW, h=52)
        self.cont.setFixedWidth(260); self.cont.setVisible(False)
        self.cont.clicked.connect(self._go_next)
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(self.cont); cw.addStretch()
        lay.addLayout(cw)

    def showEvent(self, e):
        super().showEvent(e)
        self.bar.setValue(0); self.results.setText(""); self.cont.setVisible(False)
        QTimer.singleShot(200, self._scan_steam)

    def _scan_steam(self):
        self.status.setText("Scanning for Steam..."); self.bar.setValue(20)
        self.steam_root = find_steam_root()
        if not self.steam_root:
            self.status.setText("Steam not found. Is it installed?")
            self.status.setStyleSheet(f"color:{C_TREY};background:transparent;")
            self.bar.setValue(100); return
        self.status.setText(f"Found Steam at {self.steam_root}"); self.bar.setValue(40)
        QTimer.singleShot(200, self._scan_games)

    def _scan_games(self):
        self.status.setText("Scanning for games..."); self.bar.setValue(70)
        source = cfg.get_game_source() or "steam"
        libs = parse_library_folders(self.steam_root)
        steam_found = find_installed_games(libs)
        self.steam_installed = steam_found
        if source == "own" and not self._steam_only:
            from detect_games import find_own_installed
            own_found = find_own_installed()
            self.own_installed = own_found
            self.installed = {**own_found, **steam_found}
        else:
            self.own_installed = {}
            self.installed = steam_found
        if not cfg.is_oled():
            lcd_allowed = set()
            for g in ALL_GAMES:
                lcd_allowed.update(g.get("lcd_keys", g["keys"]))
            self.installed = {k:v for k,v in self.installed.items() if k in lcd_allowed}
            self.steam_installed = {k:v for k,v in self.steam_installed.items() if k in lcd_allowed}
            self.own_installed = {k:v for k,v in self.own_installed.items() if k in lcd_allowed}
        QTimer.singleShot(200, self._show_results)

    def _show_results(self):
        self.bar.setValue(100)
        if not self.installed:
            # Advanced flow with own games already parked: no Steam games is OK,
            # skip straight to SetupScreen which will route to OwnInstallScreen.
            if self._steam_only and cfg.get_game_source() == "own":
                own_screen = self.stack.widget(10)
                if own_screen.own_selected:
                    self.status.setText("No Steam games found — continuing with your non-Steam games.")
                    self.status.setStyleSheet(f"color:{C_IW};background:transparent;")
                    self.cont.setVisible(True)
                    return
            self.status.setText("No supported games found.")
            self.status.setStyleSheet(f"color:{C_TREY};background:transparent;"); return
        unique = len({g["name"].split(" - ")[0].split(" (")[0] for g in self.installed.values()})
        self.status.setText(f"Found {unique} supported game(s)!")
        self.status.setStyleSheet(f"color:{C_IW};background:transparent;")
        lines = []
        # Steam games
        seen_steam = set()
        for g in sorted(self.steam_installed.values(), key=lambda x: x.get("order",99)):
            base = g["name"].split(" - ")[0].split(" (")[0]
            if base not in seen_steam:
                seen_steam.add(base)
                lines.append(f'<span style="color:{C_IW}">{base} (Steam)</span>')
        # Own games
        seen_own = set()
        for g in sorted(self.own_installed.values(), key=lambda x: x.get("order",99)):
            base = g["name"].split(" - ")[0].split(" (")[0]
            if base not in seen_own:
                seen_own.add(base)
                lines.append(f'<span style="color:{C_TREY}">{base} (Non-Steam)</span>')
        self.results.setText("\n".join(lines)); self.cont.setVisible(True)

    def _go_next(self):
        if cfg.is_first_run():
            s = self.stack.widget(3)
            s.steam_installed = self.steam_installed
            s.own_installed   = self.own_installed
            s.steam_root      = self.steam_root
            self.stack.setCurrentIndex(3)
        else:
            self.stack.widget(5).set_installed(self.installed); self.stack.setCurrentIndex(5)

# ── SetupScreen ────────────────────────────────────────────────────────────────
class SetupScreen(QWidget):
    """
    Steam game selection. Shows detected Steam games with checkboxes.
    In the advanced flow, routes to OwnInstallScreen instead of InstallScreen
    so both Steam and own games are handled in one pass.
    """
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.screen_name = "SetupScreen"
        self.steam_installed={}; self.own_installed={}; self.steam_root=""
        self._checks={}

        lay = QVBoxLayout(self); lay.setContentsMargins(60,40,60,40); lay.setSpacing(14)
        t = QLabel("SETUP"); t.setFont(font(36,True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;"); lay.addWidget(t)
        lay.addWidget(_lbl(
            "Choose which games to set up. "
            "DeckOps will create Proton prefixes automatically.", 13, C_DIM))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._lw = QWidget(); self._ll = QVBoxLayout(self._lw)
        self._ll.setSpacing(0); self._ll.addStretch()
        scroll.setWidget(self._lw); lay.addWidget(scroll, stretch=1)

        self.warning = _lbl("", 12, C_TREY, align=Qt.AlignLeft)
        self.warning.setVisible(False); lay.addWidget(self.warning)
        brow = QHBoxLayout(); brow.setSpacing(16)
        back = _btn("<< Back", C_DARK_BTN, h=52); back.setFixedWidth(180)
        back.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.inst_btn = _btn("Install Selected >>", C_IW, h=52)
        self.inst_btn.clicked.connect(self._go_install)
        brow.addWidget(back); brow.addWidget(self.inst_btn, stretch=1); lay.addLayout(brow)

    def showEvent(self, e):
        super().showEvent(e)
        self.warning.setVisible(False)
        self._build()

    def _build(self):
        while self._ll.count() > 1:
            item = self._ll.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._checks.clear()

        MAX_SLOTS  = 3
        SLOT_W     = 28
        SLOT_GAP   = 8
        CHECKS_W   = MAX_SLOTS * SLOT_W + (MAX_SLOTS - 1) * SLOT_GAP

        for gd in ALL_GAMES:
            keys = _active_keys(gd)
            if not keys: continue
            ik = [k for k in keys if k in self.steam_installed]
            if not ik: continue

            color  = C_IW if gd["dev"] == "iw" else C_TREY
            client = _active_client(gd)

            row = QHBoxLayout()
            row.setSpacing(12)
            row.setContentsMargins(8, 8, 8, 8)

            # ── Per-key checkbox column ────────────────────────────────────
            checks_widget = QWidget()
            checks_widget.setFixedWidth(CHECKS_W)
            checks_layout = QHBoxLayout(checks_widget)
            checks_layout.setContentsMargins(0, 0, 0, 0)
            checks_layout.setSpacing(SLOT_GAP)

            for key in keys:
                installed   = key in self.steam_installed
                already_done = cfg.is_game_setup_for_source(key, "steam")

                slot = QWidget()
                slot.setFixedWidth(SLOT_W)
                slot_lay = QVBoxLayout(slot)
                slot_lay.setContentsMargins(0, 0, 0, 0)
                slot_lay.setSpacing(2)
                slot_lay.setAlignment(Qt.AlignHCenter)

                cb = QCheckBox()
                if not installed:
                    cb.setChecked(False)
                    cb.setEnabled(False)
                elif already_done:
                    cb.setChecked(False)
                else:
                    cb.setChecked(True)

                mode_color = C_TREY if not installed else "#666677"
                mode_lbl = _lbl(KEY_MODE_LABEL.get(key, key), 9, mode_color,
                                 align=Qt.AlignHCenter, wrap=False)

                slot_lay.addWidget(cb, alignment=Qt.AlignHCenter)
                slot_lay.addWidget(mode_lbl)
                checks_layout.addWidget(slot)

                self._checks[key] = (cb, gd)

            # Fill remaining slots with transparent spacers for alignment
            for _ in range(MAX_SLOTS - len(keys)):
                spacer = QWidget()
                spacer.setFixedSize(SLOT_W, 38)
                spacer.setStyleSheet("background: transparent;")
                checks_layout.addWidget(spacer)

            row.addWidget(checks_widget)

            # ── Game name + optional offline note ──────────────────────────
            name_wrap = QWidget()
            name_wrap_lay = QVBoxLayout(name_wrap)
            name_wrap_lay.setContentsMargins(0, 0, 0, 0)
            name_wrap_lay.setSpacing(2)

            any_installed = len(ik) > 0
            name_color = "#FFF" if any_installed else "#555566"
            name_lbl = _lbl(gd["base"], 14, name_color, align=Qt.AlignLeft, wrap=False)
            name_wrap_lay.addWidget(name_lbl)

            row.addWidget(name_wrap, stretch=1)

            # ── Client badge ───────────────────────────────────────────────
            badge = QPushButton(client.upper())
            badge.setFont(font(10, True))
            badge.setFixedSize(160, 30)
            badge.setEnabled(False)
            badge.setStyleSheet(
                f"QPushButton{{background:{color};color:#FFF;border:none;border-radius:6px;}}"
                f"QPushButton:disabled{{background:{color};color:#FFF;}}"
            )
            row.addWidget(badge)

            cw = QWidget()
            cw.setLayout(row)
            self._ll.insertWidget(self._ll.count() - 1, cw)

    def _go_install(self):
        selected = []
        for key, (cb, gd) in self._checks.items():
            if not cb.isChecked(): continue
            if key not in self.steam_installed: continue
            selected.append((key, gd, self.steam_installed[key]))
        if not selected:
            # Advanced flow: own games are already queued on OwnInstallScreen,
            # so zero Steam games is valid. Route straight through.
            if cfg.get_game_source() == "own":
                own_screen = self.stack.widget(10)
                own_screen.steam_selected = []
                own_screen.steam_root = self.steam_root
                self.stack.setCurrentIndex(10)
                return
            self.warning.setText("Select at least one game to continue.")
            self.warning.setVisible(True); return

        # Advanced flow -- OwnInstallScreen handles both Steam + own games
        if cfg.get_game_source() == "own":
            own_screen = self.stack.widget(10)
            own_screen.steam_selected = selected
            own_screen.steam_root = self.steam_root
            self.stack.setCurrentIndex(10)
            return

        # Standard flow -- InstallScreen handles Steam games only
        s = self.stack.widget(4)
        s.selected   = selected
        s.steam_root = self.steam_root
        self.stack.setCurrentIndex(4)

# ── InstallScreen ──────────────────────────────────────────────────────────────
class InstallScreen(QWidget):
    def __init__(self, stack):
        super().__init__(); self.stack=stack; self.selected=[]; self.steam_root=""; self.screen_name = "InstallScreen"
        self._plut_event = threading.Event()
        self._return_to_management = False

        lay = QVBoxLayout(self); lay.setContentsMargins(80,60,80,60); lay.setSpacing(20)
        t = QLabel("INSTALLING"); t.setFont(font(36,True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;"); lay.addWidget(t)
        self.cur = _lbl("Preparing...", 16, "#CCC"); lay.addWidget(self.cur)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(22)
        bw = QHBoxLayout(); bw.setContentsMargins(60,0,60,0); bw.addWidget(self.bar)
        lay.addLayout(bw)
        self.stat = _lbl("", 13, C_IW); lay.addWidget(self.stat)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(font(11))
        self.log.setStyleSheet("QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}")
        lay.addWidget(self.log, stretch=1)

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
        lay.addWidget(self.plut_warn)

        self.plut_btn = _btn("I've closed Plutonium  ✓", C_TREY, size=13, h=52)
        self.plut_btn.setFixedWidth(460); self.plut_btn.setVisible(False)
        self.plut_btn.clicked.connect(self._confirm_plut)
        pw = QHBoxLayout(); pw.addStretch(); pw.addWidget(self.plut_btn); pw.addStretch()
        lay.addLayout(pw)

        self.cont_btn = _btn("Continue  >>", C_IW, size=13, h=52)
        self.cont_btn.setFixedWidth(320); self.cont_btn.setVisible(False)
        self.cont_btn.clicked.connect(lambda: self.stack.setCurrentIndex(7))
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(self.cont_btn); cw.addStretch()
        lay.addLayout(cw)

        self._s = _Sigs()
        self._s.progress.connect(lambda p,m: (self.bar.setValue(p), self.cur.setText(m)))
        self._s.log.connect(self._append_log)
        self._s.done.connect(self._on_done)
        self._s.plut_wait.connect(self._show_plut_wait)
        self._s.plut_go.connect(self._hide_plut_wait)
        self._s.pulse_start.connect(self._start_pulse)
        self._s.pulse_stop.connect(self._stop_pulse)

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
        is_lcd = not cfg.is_oled()
        self.plut_warn.setVisible(is_lcd)
        self.plut_btn.setVisible(True)

    def _hide_plut_wait(self):
        self.plut_warn.setVisible(False)
        self.plut_btn.setVisible(False)

    def _append_log(self, text):
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        _log_to_file(text)

    def showEvent(self, e):
        super().showEvent(e)
        self.bar.setValue(0); self.log.clear()
        self.plut_btn.setVisible(False)
        self.plut_warn.setVisible(False)
        self._stop_pulse()
        self._plut_event.clear()
        # Route the continue button based on whether this was triggered
        # from ManagementScreen (return to My Games) or the first-run
        # wizard (go to ControllerInfoScreen).
        try:
            self.cont_btn.clicked.disconnect()
        except Exception:
            pass
        if self._return_to_management:
            self.cont_btn.setText("Back to My Games  >>")
            self.cont_btn.clicked.connect(self._go_management)
            self._return_to_management = False
        else:
            self.cont_btn.setText("Continue  >>")
            self.cont_btn.clicked.connect(lambda: self.stack.setCurrentIndex(7))
        _log_to_file("── Install started ──")
        QTimer.singleShot(400, lambda: threading.Thread(target=self._run, daemon=True).start())

    def _confirm_plut(self):
        self._plut_event.set()

    def _on_done(self, _):
        self._stop_pulse()
        self.cur.setText("Installation complete!")
        self.cont_btn.setVisible(True)

    def _go_management(self):
        root = find_steam_root()
        self.stack.widget(5).set_installed(find_installed_games(parse_library_folders(root)))
        self.stack.setCurrentIndex(5)

    def _run(self):
        from wrapper import get_proton_path, find_compatdata, kill_steam
        from plutonium_oled import launch_bootstrapper, is_plutonium_ready, install_plutonium
        from cod4x import install_cod4x
        from iw4x import install_iw4x
        from iw3sp import install_iw3sp
        from ge_proton import install_ge_proton, set_compat_tool, MANAGED_APPIDS

        selected_keys   = [key for key, _, _ in self.selected]
        has_plut        = any(KEY_CLIENT.get(k) == "plutonium" for k in selected_keys)
        has_cod4        = any(KEY_CLIENT.get(k) in ("cod4x", "iw3sp") for k in selected_keys)
        has_iw4x        = any(KEY_CLIENT.get(k) == "iw4x" for k in selected_keys)
        logged_bases    = set()
        ge_version      = None
        _compat_applied = False
        _steam_killed   = False

        def _kill_steam_once():
            nonlocal _steam_killed
            if not _steam_killed:
                self._s.progress.emit(28, "Closing Steam...")
                self._s.log.emit("Closing Steam...")
                try:
                    kill_steam()
                    self._s.log.emit("  ✓ Steam closed.")
                except Exception as ex:
                    self._s.log.emit(f"  Could not close Steam: {ex}")
                _steam_killed = True

        def _apply_compat():
            nonlocal _compat_applied
            if ge_version and not _compat_applied:
                try:
                    set_compat_tool(MANAGED_APPIDS, ge_version)
                    self._s.log.emit(f"✓  GE-Proton {ge_version} set for all games")
                    cfg.set_ge_proton_version(ge_version)
                    _compat_applied = True
                except Exception as ex:
                    self._s.log.emit(f"  CompatToolMapping skipped: {ex}")
        _launch_defaults_set = False
        def _set_launch_defaults():
            nonlocal _launch_defaults_set
            if _launch_defaults_set:
                return
            defaults = {}
            if has_cod4:
                defaults["7940"] = ("7a722f97", "1")   # CoD4 → Singleplayer
            if any(k in ("t4sp", "t4mp") for k in selected_keys):
                defaults["10090"] = ("9aa5e05f", "0") # WaW → Campaign
            if not defaults:
                return
            try:
                from wrapper import set_default_launch_option
                set_default_launch_option(self.steam_root, defaults)
                self._s.log.emit("✓  Default launch options set (SP mode)")
                _launch_defaults_set = True
            except Exception as ex:
                self._s.log.emit(f"  Launch options skipped: {ex}")

        # ── GE-Proton download + extract (Steam still running) ────────────────
        try:
            self._s.pulse_start.emit("Installing GE-Proton")
            self._s.log.emit("Installing GE-Proton...")
            ge_version = install_ge_proton(
                on_progress=lambda pct, msg: self._s.progress.emit(2 + int(pct * 0.08), msg)
            )
            self._s.pulse_stop.emit()
            self._s.log.emit(f"✓  {ge_version} downloaded")
        except Exception as ex:
            self._s.pulse_stop.emit()
            self._s.log.emit(f"  GE-Proton setup skipped: {ex}")

        # ── Copy deps from GE-Proton default_pfx into all game prefixes ──────
        # Every selected game gets its prefix preloaded — no exceptions.
        # ensure_all_prefix_deps handles deduplication and skips prefixes
        # that are already initialized.
        proton = get_proton_path(self.steam_root)

        if ge_version:
            from ge_proton import ensure_all_prefix_deps
            from detect_games import GAMES as _GAMES_MAP
            self._s.log.emit("Installing prefix dependencies...")
            self._s.pulse_start.emit("Installing prefix dependencies")
            dep_targets = []
            for key, gd, game in self.selected:
                # Use per-key appid from GAMES, not card-level gd["appid"].
                # Card-level appid is wrong for keys that have their own appid
                # (e.g. t6zm=212910, t6sp=202970 vs card appid 202990).
                appid = _GAMES_MAP[key]["appid"] if key in _GAMES_MAP else gd["appid"]
                _install_dir = game["install_dir"] if game else None
                compat = find_compatdata(self.steam_root, appid,
                                         game_install_dir=_install_dir)
                if not compat and game and game.get("install_dir"):
                    # Prefix doesn't exist yet — build the path from the game's
                    # steamapps dir so ensure_prefix_deps can create it
                    steamapps = os.path.dirname(os.path.dirname(game["install_dir"]))
                    compat = os.path.join(steamapps, "compatdata", str(appid))
                if compat:
                    dep_targets.append((key, compat))
            if dep_targets:
                done = ensure_all_prefix_deps(
                    ge_version, dep_targets,
                    on_progress=lambda msg: self._s.log.emit(msg),
                    proton_path=proton,
                    steam_root=self.steam_root,
                )
                self._s.log.emit(f"✓  Prefix dependencies: {done}/{len(dep_targets)} ready")
            self._s.pulse_stop.emit()

        # ── Plutonium bootstrapper (Steam still running) ──────────────────────
        if has_plut:
            is_lcd = not cfg.is_oled()

            # LCD and OLED both require the user to log in, just in different
            # prefixes. LCD logs in inside HGL's shared default prefix so
            # the auth state is bound to the exact Wine prefix that will
            # later launch the games. OLED logs in inside the dedicated
            # DeckOps prefix at ~/.local/share/deckops/plutonium_prefix/.
            if is_lcd:
                from plutonium_lcd import (launch_bootstrapper_lcd,
                                    is_plutonium_ready_lcd)
                plut_ready = is_plutonium_ready_lcd()
            else:
                plut_ready = is_plutonium_ready()

            if not plut_ready:
                if is_lcd:
                    self._s.progress.emit(12, "Setting up Plutonium through HGL...")
                    self._s.log.emit(
                        "Setting up Plutonium through HGL...\n"
                        "  1. HGL will download and launch Plutonium (this may take a few minutes)\n"
                        "  2. Log in with your Plutonium account\n"
                        "  3. Close the Plutonium window\n"
                        "  4. Click the button below to continue"
                    )
                else:
                    self._s.progress.emit(12, "Launching Plutonium — please log in...")
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
                except Exception as ex:
                    self._s.log.emit(f"✗  Plutonium launch failed: {ex}")
                    self._s.progress.emit(100, "Setup failed."); self._s.done.emit(True); return

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

                # Verify Plutonium is ready after the user closed the window
                ready_check = is_plutonium_ready_lcd() if is_lcd else is_plutonium_ready()
                if not ready_check:
                    self._s.log.emit(
                        "✗  Plutonium does not appear to be fully set up.\n"
                        "   Make sure you logged in and let it finish downloading."
                    )
                    self._s.progress.emit(100, "Setup incomplete."); self._s.done.emit(True); return

                self._s.log.emit("✓  Plutonium ready.")
            else:
                self._s.progress.emit(12, "Waiting for Plutonium...")
                self._s.log.emit(
                    "Wait for Plutonium to finish updating, sign in, then close Plutonium."
                )
                self._s.plut_wait.emit()
                self._plut_event.wait()
                self._s.plut_go.emit()

        # ── Kill Steam once — everything from here runs with Steam closed ─────
        _kill_steam_once()
        _apply_compat()
        _set_launch_defaults()

        # ── Clean up stale launch options from older DeckOps versions ─────────
        # Old versions used launch commands instead of the exe rename strategy.
        # If those are still in localconfig.vdf they'll conflict with the rename.
        try:
            from wrapper import clear_launch_options
            for stale_appid in ["7940", "10190"]:
                clear_launch_options(self.steam_root, stale_appid)
            self._s.log.emit("✓  Stale launch options cleared")
        except Exception as ex:
            self._s.log.emit(f"  Launch option cleanup skipped: {ex}")

        # ── Plutonium games ───────────────────────────────────────────────────
        if has_plut:
            plut_selected = [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "plutonium"]
            total_plut = len(plut_selected)
            for idx, (key, gd, game) in enumerate(plut_selected):
                bp = 30 + int(idx / max(total_plut, 1) * 30)
                base_name = gd["base"]
                if base_name not in logged_bases:
                    self._s.progress.emit(bp, f"Setting up {base_name}...")
                def op_plut(pct, msg, _b=bp): self._s.progress.emit(_b + int(pct / 100 * 8), msg)
                try:
                    from plutonium_oled import GAME_META as _PLUT_META
                    _plut_appid = _PLUT_META[key][0] if key in _PLUT_META else gd["appid"]
                    compat = find_compatdata(self.steam_root, _plut_appid,
                                              game_install_dir=game["install_dir"] if game else None)
                    install_plutonium(game, key, self.steam_root, proton, compat, op_plut)
                    # plutonium installer (plutonium_oled.py / plutonium_lcd.py)
                    # owns its own mark_game_setup call so lan_wrapper_path
                    # and other install-side metadata are preserved.
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

            # Create the DeckOps Plutonium Launcher shortcut. Both OLED
            # and LCD now ship with the launcher — OLED uses sidecar -lan
            # scripts written by plutonium_oled._write_oled_lan_wrapper.
            try:
                from shortcut import create_launcher_shortcut
                create_launcher_shortcut(
                    on_progress=lambda m: self._s.log.emit(m)
                )
            except Exception as ex:
                self._s.log.emit(f"  Launcher shortcut failed: {ex}")

        # ── iw4x (Steam closed) ───────────────────────────────────────────────
        if has_iw4x:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "iw4x"]:
                base_name = gd["base"]
                self._s.progress.emit(62, f"Setting up {base_name}...")
                def op_iw4x(pct, msg): self._s.progress.emit(62 + int(pct / 100 * 8), msg)
                try:
                    compat = find_compatdata(self.steam_root, gd["appid"],
                                              game_install_dir=game["install_dir"] if game else None)
                    install_iw4x(game, self.steam_root, proton, compat, op_iw4x)
                    cfg.mark_game_setup(key, "iw4x", source="steam")
                    self._s.log.emit(f"✓  {base_name} done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        # ── CoD4 (iw3sp + cod4x) — Steam closed ──────────────────────────────
        if has_cod4:
            cod4_selected = [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) in ("cod4x", "iw3sp")]
            for key, gd, game in cod4_selected:
                base_name = gd["base"]
                self._s.progress.emit(75, f"Setting up {base_name}...")
                def op_cod4(pct, msg): self._s.progress.emit(75 + int(pct / 100 * 10), msg)
                try:
                    _install_dir = game["install_dir"] if game else None
                    compat = find_compatdata(self.steam_root, gd["appid"],
                                             game_install_dir=_install_dir)
                    c = KEY_CLIENT.get(key, gd["client"])
                    if c == "cod4x":
                        install_cod4x(game, self.steam_root, proton, compat, op_cod4,
                                      appid=gd["appid"])
                    elif c == "iw3sp":
                        install_iw3sp(game, self.steam_root, proton, compat, op_cod4)
                    cfg.mark_game_setup(key, c, source="steam")
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        # ── Vanilla Steam games (no mod client, just configs + controllers) ──
        # Games like MW2 SP, MW3 SP, and BO2 SP run through Steam as-is.
        # No download or exe replacement needed. We just mark them as set up
        # so they show as installed on the My Games screen and get their
        # display configs and controller profiles applied below.
        for key, gd, game in self.selected:
            c = KEY_CLIENT.get(key, "")
            if c == "steam" and not cfg.is_game_setup_for_source(key, "steam"):
                cfg.mark_game_setup(key, "steam", source="steam")
                self._s.log.emit(f"✓  {gd['base']} ({key}) ready")

        # ── game display configs ──────────────────────────────────────────────
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

        # ── Controller templates + profiles (after all games) ─────────────────
        self._s.progress.emit(90, "Installing controller templates...")
        self._s.log.emit("Installing controller templates...")
        try:
            from controller_profiles import install_controller_templates, assign_controller_profiles, assign_external_controller_profiles
            install_controller_templates(
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            gyro_mode = cfg.get_gyro_mode() or "hold"
            # Neptune profiles always assigned - user may play handheld too
            assign_controller_profiles(
                gyro_mode,
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            self._s.log.emit(f"✓  Neptune controller profiles assigned ({gyro_mode} mode)")
            # Docked users also get external controller profiles
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

        # ── Non-Steam shortcuts ───────────────────────────────────────────────
        try:
            from shortcut import create_shortcuts
            self._s.log.emit("Creating non-Steam shortcuts...")
            installed_for_shortcuts = {k: g for k, gd, g in self.selected if g}
            create_shortcuts(
                installed_games=installed_for_shortcuts,
                selected_keys=selected_keys,
                gyro_mode=cfg.get_gyro_mode() or "hold",
                on_progress=lambda msg: self._s.log.emit(msg),
                steam_root=self.steam_root,
            )
        except Exception as ex:
            self._s.log.emit(f"  Shortcuts skipped: {ex}")

        # ── Custom artwork for Steam MP/ZM games ─────────────────────────────
        try:
            from shortcut import apply_steam_artwork
            self._s.log.emit("Applying custom artwork for multiplayer games...")
            apply_steam_artwork(
                selected_keys=selected_keys,
                on_progress=lambda msg: self._s.log.emit(msg)
            )
        except Exception as ex:
            self._s.log.emit(f"  Steam artwork skipped: {ex}")

        # Standard flow always finishes here. Advanced flow uses
        # OwnInstallScreen instead and never reaches this screen.
        cfg.complete_first_run(self.steam_root)
        self._s.progress.emit(100, "All done!")
        self._s.done.emit(True)


# ── ManagementCard ─────────────────────────────────────────────────────────────
class ManagementCard(QFrame):
    def __init__(self, gd, installed, on_setup, on_update, parent=None):
        super().__init__(parent)
        color = C_IW if gd["dev"] == "iw" else C_TREY
        self._color  = color
        self._appid  = _active_appid(gd)
        self.setObjectName("MC")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        keys       = _active_keys(gd)
        client     = _active_client(gd)
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

        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setStyleSheet("background:#0A0A10;border:none;")
        if not is_setup:
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.45 if is_present else 0.25)
            self._img.setGraphicsEffect(effect)
        lay.addWidget(self._img)
        self._raw_pixmap = None

        cached = _header_path(self._appid)
        if os.path.exists(cached):
            self._raw_pixmap = QPixmap(cached)
        else:
            threading.Thread(target=self._fetch, args=(self._appid,), daemon=True).start()

        badge_row = QWidget()
        badge_row.setStyleSheet(f"background:{C_CARD};border:none;")
        bl = QHBoxLayout(badge_row)
        bl.setContentsMargins(8, 4, 8, 4); bl.setSpacing(6)

        client_lbl = QPushButton(client.upper())
        client_lbl.setFont(font(9, True)); client_lbl.setFixedHeight(22)
        client_lbl.setEnabled(False)
        client_lbl.setStyleSheet(
            f"QPushButton{{background:{color};color:#FFF;border:none;border-radius:4px;padding:0 8px;}}"
            f"QPushButton:disabled{{background:{color};color:#FFF;}}"
        )
        bl.addWidget(client_lbl)
        bl.addStretch()

        if is_setup:
            status_lbl = _lbl("✓ installed", 10, C_IW, align=Qt.AlignRight, wrap=False)
        elif is_present:
            status_lbl = _lbl("not set up", 10, C_DIM, align=Qt.AlignRight, wrap=False)
        else:
            status_lbl = _lbl("not installed", 10, "#554444", align=Qt.AlignRight, wrap=False)
        bl.addWidget(status_lbl)
        lay.addWidget(badge_row)

        title = _lbl(gd["base"], 12, "#FFF" if is_present else "#444455",
                     align=Qt.AlignLeft, wrap=False)
        title.setContentsMargins(8, 4, 8, 0)
        lay.addWidget(title)

        btn_row = QWidget(); btn_row.setStyleSheet(f"background:{C_CARD};border:none;")
        br = QHBoxLayout(btn_row); br.setContentsMargins(8, 6, 8, 8); br.setSpacing(6)

        if not is_setup and is_present:
            setup_btn = _btn("Set Up", C_IW, size=10, h=32)
            setup_btn.clicked.connect(lambda: on_setup(gd))
            br.addWidget(setup_btn); br.addStretch()
        elif is_setup:
            has_mod = any(KEY_CLIENT.get(k, "") not in ("steam", "") for k in ik)
            if has_mod:
                upd_btn = _btn("Update", C_DARK_BTN, size=10, h=32)
                upd_btn.clicked.connect(lambda: on_update(gd, ik))
                br.addWidget(upd_btn)
            br.addStretch()
        else:
            br.addStretch()

        lay.addWidget(btn_row)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._scale_image()

    def _scale_image(self):
        if self._raw_pixmap:
            w = self.width()
            h = int(w * IMG_RATIO)
            self._img.setFixedSize(w, h)
            self._img.setPixmap(
                self._raw_pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            )
        else:
            w = self.width()
            self._img.setFixedSize(w, int(w * IMG_RATIO))

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

# ── ManagementScreen ───────────────────────────────────────────────────────────
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
        guide_btn.clicked.connect(lambda: self.stack.setCurrentIndex(7))
        hl.addWidget(guide_btn)
        hl.addSpacing(8)
        cfg_btn = _btn("⚙  Settings", C_DARK_BTN, size=11, h=36); cfg_btn.setFixedWidth(120)
        cfg_btn.clicked.connect(lambda: self.stack.setCurrentIndex(6))
        hl.addWidget(cfg_btn)
        lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); self._grid = QGridLayout(inner)
        self._grid.setContentsMargins(16,16,16,16); self._grid.setSpacing(12)
        for c in range(CARD_COLS):
            self._grid.setColumnStretch(c, 1)
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

        games = [g for g in ALL_GAMES if _active_keys(g)]

        for idx, gd in enumerate(games):
            row = idx // CARD_COLS
            col = idx  % CARD_COLS
            card = ManagementCard(
                gd, self.installed,
                on_setup     = self._setup,
                on_update    = self._update,
            )
            self._grid.addWidget(card, row, col)

        total = len(games)
        remainder = total % CARD_COLS
        if remainder:
            for col in range(remainder, CARD_COLS):
                self._grid.addWidget(QWidget(), total // CARD_COLS, col)

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

            s = self.stack.widget(10)  # OwnInstallScreen
            s.own_selected = own_selected
            s.steam_selected = steam_selected
            s.steam_root = root
            s._return_to_management = True
            self.stack.setCurrentIndex(10)
        else:
            # Standard Steam flow
            s = self.stack.widget(4)  # InstallScreen
            s.selected = selected
            s.steam_root = root
            s._return_to_management = True
            self.stack.setCurrentIndex(4)

    def _update(self, gd, keys):
        """Route a single card's installed keys through the update flow."""
        root = find_steam_root()
        # Use the merged installed dict (already built in showEvent)
        selected = [(k, gd, self.installed.get(k, {})) for k in keys
                     if self.installed.get(k)]
        if not selected:
            self._status.setText("Game not found.")
            return
        s = self.stack.widget(8)  # UpdateScreen
        s.selected   = selected
        s.steam_root = root
        self.stack.setCurrentIndex(8)


# ── ControllerInfoScreen ───────────────────────────────────────────────────────
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

        # ── BO2 encrypted config note ──────────────────────────────────────────
        lay.addWidget(_lbl("⚠  Black Ops II - Manual Setup Required", 13, C_TREY, bold=True, align=Qt.AlignLeft))
        lay.addWidget(_lbl(
            "BO2 Multiplayer and Zombies config files are handled automatically by DeckOps. "
            "Singleplayer config files are encrypted and cannot be written by DeckOps. "
            "Set your resolution and display settings manually in-game after launching for the first time.",
            11, C_DIM, align=Qt.AlignLeft))

        lay.addWidget(_hdiv())

        # ── LCD launch delay note (LCD users only) ────────────────────────────
        self._lcd_div = _hdiv()
        self._lcd_hdr = _lbl("⚠  LCD Steam Deck - Game Launch Delay", 13, C_TREY, bold=True, align=Qt.AlignLeft)
        self._lcd_body = _lbl(
            "Plutonium games on LCD may take a moment to launch. A cleanup script runs "
            "before each launch to clear portions of the shader cache (a workaround for "
            "a known Steam bug with non-Steam games). If the game doesn't start right "
            "away, please be patient or try launching again.",
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
        self._decky_btn.clicked.connect(lambda: __import__("subprocess").Popen(
            ["xdg-open", "https://decky.xyz/"], start_new_session=True
        ))
        dbw = QHBoxLayout(); dbw.addWidget(self._decky_btn); dbw.addStretch()
        lay.addWidget(self._decky_div)
        lay.addWidget(self._decky_hdr)
        lay.addWidget(self._decky_body)
        lay.addLayout(dbw)

        lay.addStretch()
        lay.addSpacing(4)

        cont = _btn("Continue  >>", C_IW, h=52)
        cont.clicked.connect(self._reopen_steam)
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(cont, stretch=1); cw.addStretch()
        lay.addLayout(cw)

    def showEvent(self, e):
        super().showEvent(e)
        gyro_mode = cfg.get_gyro_mode() or "hold"
        if gyro_mode == "hold":
            gyro_desc = "R5 held"
        elif gyro_mode == "ads":
            gyro_desc = "aim down sights"
        else:
            gyro_desc = "R5 toggles"
        self._gyro_lbl.setText(
            f"Standard gamepad layout with gyro aiming ({gyro_desc}) assigned to all games. "
        )
        # Only show the Decky section for docked users
        is_docked = cfg.is_docked()
        self._decky_div.setVisible(is_docked)
        self._decky_hdr.setVisible(is_docked)
        self._decky_body.setVisible(is_docked)
        self._decky_btn.setVisible(is_docked)
        # Only show the LCD launch delay note for LCD users
        is_lcd = not cfg.is_oled()
        self._lcd_div.setVisible(is_lcd)
        self._lcd_hdr.setVisible(is_lcd)
        self._lcd_body.setVisible(is_lcd)

    def _go_management(self):
        root = find_steam_root()
        self.stack.widget(5).set_installed(find_installed_games(parse_library_folders(root)))
        self.stack.setCurrentIndex(5)

    def _reopen_steam(self):
        try:
            steam_root = cfg.load().get("steam_root", "") or find_steam_root()
            steam_sh = os.path.join(steam_root, "steam.sh") if steam_root else None
            if steam_sh and os.path.exists(steam_sh):
                subprocess.Popen([steam_sh], start_new_session=True)
            else:
                subprocess.Popen(["steam"], start_new_session=True)
        except Exception:
            try:
                subprocess.Popen(["steam"], start_new_session=True)
            except Exception:
                pass
        root = find_steam_root()
        self.stack.widget(5).set_installed(find_installed_games(parse_library_folders(root)))
        self.stack.setCurrentIndex(5)


def _reopen_steam_bg(steam_root=None):
    """Reopen Steam in the background after a settings operation."""
    try:
        if not steam_root:
            steam_root = find_steam_root()
        steam_sh = os.path.join(steam_root, "steam.sh") if steam_root else None
        if steam_sh and os.path.exists(steam_sh):
            subprocess.Popen([steam_sh], start_new_session=True)
        else:
            subprocess.Popen(["steam"], start_new_session=True)
    except Exception:
        pass

# ── ConfigureScreen ────────────────────────────────────────────────────────────
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
        from PyQt5.QtWidgets import QSlider
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
        for mode in ("hold", "toggle", "ads"):
            b = _btn(mode.upper(), C_DARK_BTN, size=11, h=36)
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
        from PyQt5.QtWidgets import QLineEdit
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
        self._name_note = _lbl("Does not affect Plutonium online play", 10, C_DIM, align=Qt.AlignLeft)
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

        # ── About ─────────────────────────────────────────────────────────
        self._about_label = _lbl("", 11, C_DIM, align=Qt.AlignLeft)
        lay.addWidget(self._about_label)

        lay.addStretch()
        self.status = _lbl("", 12, C_DIM)
        lay.addWidget(self.status)
        back = _btn("<< Back", C_DARK_BTN, h=48); back.setFixedWidth(160)
        back.clicked.connect(lambda: self.stack.setCurrentIndex(5))
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

        # Gyro highlight
        gyro = cfg.get_gyro_mode() or "hold"
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

        self._about_label.setText(
            f"Steam Deck: {model.upper()}  |  Source: {source_label}  |  "
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
                gyro_mode = cfg.get_gyro_mode() or "hold"
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
                _reopen_steam_bg(sr)
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
        try:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            try:
                subprocess.Popen(["xdg-open", url], start_new_session=True)
            except Exception:
                self.status.setText("Could not open browser.")



# ── UpdateScreen ───────────────────────────────────────────────────────────────
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
        self.cur.setText("Done!")
        self.back_btn.setVisible(True)
        _reopen_steam_bg(cfg.load().get("steam_root", "") or find_steam_root())

    def _go_back(self):
        root = find_steam_root()
        self.stack.widget(5).set_installed(find_installed_games(parse_library_folders(root)))
        self.stack.setCurrentIndex(5)

    def _run(self):
        from wrapper import get_proton_path, find_compatdata, kill_steam
        from iw4x import install_iw4x
        from cod4x import install_cod4x
        from iw3sp import install_iw3sp
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

        # Clean up stale launch options from older DeckOps versions
        if has_cod4 or has_iw4x:
            try:
                from wrapper import clear_launch_options
                for stale_appid in ["7940", "10190"]:
                    clear_launch_options(self.steam_root, stale_appid)
            except Exception:
                pass

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
                _appid = _PLUT_META[key][0] if (c == "plutonium" and key in _PLUT_META) else gd["appid"]

                # Resolve compatdata - own games may have CRC-based prefix
                if source == "own":
                    compat = game.get("compatdata_path", "")
                    if not compat:
                        compat = find_compatdata(self.steam_root, _appid,
                                                  game_install_dir=game.get("install_dir"))
                else:
                    compat = find_compatdata(self.steam_root, _appid,
                                              game_install_dir=game.get("install_dir"))

                if c == "cod4x":
                    install_cod4x(game, self.steam_root, proton, compat, op,
                                  appid=gd["appid"])
                elif c == "iw3sp":
                    install_iw3sp(game, self.steam_root, proton, compat, op,
                                  source=source)
                elif c == "iw4x":
                    install_iw4x(game, self.steam_root, proton, compat, op,
                                 source=source)
                elif c == "plutonium":
                    install_plutonium(game, key, self.steam_root, proton, compat,
                                     on_progress=op,
                                     installed_games=installed_for_plut,
                                     source=source)
                self._s.log.emit(f"✓  {base_name} ({key}) done")
            except Exception as ex:
                self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        self._s.progress.emit(100, "All done!")
        self._s.done.emit(True)


# ── OwnInstallScreen ──────────────────────────────────────────────────────────
class OwnInstallScreen(QWidget):
    """
    Install flow for the advanced ("Steam or Other") path.

    Handles both Steam-selected games (passed from SetupScreen as
    steam_selected) and own-detected games (parked by OwnScanScreen as
    own_selected) in a single pass.

    Creates non-Steam shortcuts for own games, copies GE-Proton's
    default_pfx to build each own game's compatdata prefix automatically,
    sets GE-Proton compat for MANAGED_APPIDS and own shortcut appids,
    then installs mod clients. No manual game launch step required.
    """

    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "OwnInstallScreen"
        self.own_selected    = {}   # dict of key -> game, set by OwnScanScreen
        self.steam_selected  = []   # list of (key, gd, game), set by SetupScreen
        self.steam_root = ""
        self._plut_event = threading.Event()
        self._return_to_management = False

        lay = QVBoxLayout(self); lay.setContentsMargins(80,60,80,60); lay.setSpacing(20)
        t = QLabel("INSTALLING"); t.setFont(font(36, True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;"); lay.addWidget(t)
        self.cur = _lbl("Preparing...", 16, "#CCC"); lay.addWidget(self.cur)
        self.bar = QProgressBar(); self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(22)
        bw = QHBoxLayout(); bw.setContentsMargins(60,0,60,0); bw.addWidget(self.bar)
        lay.addLayout(bw)
        self.stat = _lbl("", 13, C_IW); lay.addWidget(self.stat)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(font(11))
        self.log.setStyleSheet("QPlainTextEdit{color:#666677;background:transparent;border:none;padding:10px;}")
        lay.addWidget(self.log, stretch=1)

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
        lay.addWidget(self.plut_warn)

        self.plut_btn = _btn("I've closed Plutonium  ✓", C_TREY, size=13, h=52)
        self.plut_btn.setFixedWidth(460); self.plut_btn.setVisible(False)
        self.plut_btn.clicked.connect(self._confirm_plut)
        pw = QHBoxLayout(); pw.addStretch(); pw.addWidget(self.plut_btn); pw.addStretch()
        lay.addLayout(pw)

        self.cont_btn = _btn("Continue  >>", C_IW, size=13, h=52)
        self.cont_btn.setFixedWidth(320); self.cont_btn.setVisible(False)
        self.cont_btn.clicked.connect(lambda: self.stack.setCurrentIndex(7))
        cw = QHBoxLayout(); cw.addStretch(); cw.addWidget(self.cont_btn); cw.addStretch()
        lay.addLayout(cw)

        self._s = _Sigs()
        self._s.progress.connect(lambda p, m: (self.bar.setValue(p), self.cur.setText(m)))
        self._s.log.connect(self._append_log)
        self._s.done.connect(self._on_done)
        self._s.plut_wait.connect(self._show_plut_wait)
        self._s.plut_go.connect(self._hide_plut_wait)
        self._s.pulse_start.connect(self._start_pulse)
        self._s.pulse_stop.connect(self._stop_pulse)

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
        is_lcd = not cfg.is_oled()
        self.plut_warn.setVisible(is_lcd)
        self.plut_btn.setVisible(True)

    def _hide_plut_wait(self):
        self.plut_warn.setVisible(False)
        self.plut_btn.setVisible(False)

    def _append_log(self, text):
        _log_to_file(text)
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def showEvent(self, e):
        super().showEvent(e)
        self.bar.setValue(0); self.log.clear()
        self.plut_btn.setVisible(False)
        self.plut_warn.setVisible(False)
        self.cont_btn.setVisible(False)
        self._plut_event.clear()
        self._stop_pulse()
        # Route the continue button based on whether this was triggered
        # from ManagementScreen (return to My Games) or the first-run
        # wizard (go to ControllerInfoScreen).
        try:
            self.cont_btn.clicked.disconnect()
        except Exception:
            pass
        if self._return_to_management:
            self.cont_btn.setText("Back to My Games  >>")
            self.cont_btn.clicked.connect(lambda: (
                self.stack.widget(5).set_installed(
                    find_installed_games(parse_library_folders(find_steam_root()))
                ),
                self.stack.setCurrentIndex(5),
            ))
            self._return_to_management = False
        else:
            self.cont_btn.setText("Continue  >>")
            self.cont_btn.clicked.connect(lambda: self.stack.setCurrentIndex(7))
        _log_to_file("── Own Install started ──")
        QTimer.singleShot(400, lambda: threading.Thread(target=self._run, daemon=True).start())

    def _confirm_plut(self):
        self._plut_event.set()

    def _on_done(self, _):
        self._stop_pulse()
        self.cur.setText("Installation complete!")
        self.cont_btn.setVisible(True)

    def _run(self):
        import traceback as _tb
        try:
            self._run_inner()
        except Exception:
            err = _tb.format_exc()
            _log_to_file(f"[FATAL] OwnInstallScreen._run crashed:\n{err}")
            try:
                self._s.log.emit(f"✗ Install failed with error:\n{err}")
                self._s.progress.emit(100, "Install failed — see log.")
                self._s.done.emit(True)
            except Exception:
                pass

    def _run_inner(self):
        from wrapper import get_proton_path, find_compatdata, kill_steam, set_compat_tool
        from shortcut import create_own_shortcuts
        from cod4x import install_cod4x
        from iw4x import install_iw4x
        from iw3sp import install_iw3sp
        from ge_proton import install_ge_proton, MANAGED_APPIDS

        # Build the combined selected list from both Steam and own sources.
        # own_selected is a dict {key: game_dict} from OwnScanScreen.
        # steam_selected is a list [(key, gd, game)] from SetupScreen.
        # We need to merge them into self.selected as [(key, gd, game)].
        own_as_tuples = []
        for k, g in self.own_selected.items():
            for gd in ALL_GAMES:
                if k in _active_keys(gd):
                    own_as_tuples.append((k, gd, g)); break
        self.selected = list(self.steam_selected) + own_as_tuples

        selected_keys = [key for key, _, _ in self.selected]
        logged_bases  = set()
        has_plut      = any(KEY_CLIENT.get(k) == "plutonium" for k in selected_keys)
        has_cod4      = any(KEY_CLIENT.get(k) in ("cod4x", "iw3sp") for k in selected_keys)

        # ── GE-Proton download (Steam still running) ─────────────────────
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

        # ── Plutonium bootstrapper (Steam still running) ─────────────────
        # Downloads Plutonium and launches it so the user can log in. LCD
        # routes through HGL (shared default prefix); OLED uses the
        # dedicated DeckOps prefix via Proton directly.
        if has_plut:
            from plutonium_oled import (launch_bootstrapper, is_plutonium_ready,
                                   install_plutonium)
            from plutonium_oled import GAME_META as _PLUT_META
            is_lcd = not cfg.is_oled()

            if is_lcd:
                from plutonium_lcd import (launch_bootstrapper_lcd,
                                    is_plutonium_ready_lcd)
                plut_ready = is_plutonium_ready_lcd()
            else:
                plut_ready = is_plutonium_ready()

            if not plut_ready:
                if is_lcd:
                    self._s.progress.emit(10, "Setting up Plutonium through HGL...")
                    self._s.log.emit(
                        "Setting up Plutonium through HGL...\n"
                        "  1. HGL will download and launch Plutonium (this may take a few minutes)\n"
                        "  2. Log in with your Plutonium account\n"
                        "  3. Close the Plutonium window\n"
                        "  4. Click the button below to continue"
                    )
                else:
                    self._s.progress.emit(10, "Launching Plutonium — please log in...")
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
                except Exception as ex:
                    self._s.log.emit(f"✗  Plutonium launch failed: {ex}")
                    self._s.progress.emit(100, "Setup failed."); self._s.done.emit(True); return

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
                    self._s.progress.emit(100, "Setup incomplete."); self._s.done.emit(True); return

                self._s.log.emit("✓  Plutonium ready.")
            else:
                self._s.log.emit("✓  Plutonium already set up.")

        # ── Kill Steam ────────────────────────────────────────────────────
        self._s.progress.emit(18, "Closing Steam...")
        self._s.log.emit("Closing Steam...")
        try:
            kill_steam()
            self._s.log.emit("  ✓ Steam closed.")
        except Exception as ex:
            self._s.log.emit(f"  Could not close Steam: {ex}")

        # ── Set GE-Proton compat for MANAGED_APPIDS ──────────────────────
        # Must run AFTER kill_steam - Steam overwrites config.vdf on exit.
        # Only write for Steam appids if the user actually has Steam games
        # selected - otherwise this may trigger Steam to re-download games.
        if ge_version and self.steam_selected:
            try:
                set_compat_tool(MANAGED_APPIDS, ge_version)
                self._s.log.emit(f"✓  {ge_version} set for Steam game appids")
            except Exception as ex:
                self._s.log.emit(f"  CompatToolMapping for Steam appids skipped: {ex}")

        # ── Create shortcuts with artwork + controller configs ────────────
        self._s.progress.emit(22, "Creating shortcuts and downloading artwork...")
        self._s.log.emit("Creating non-Steam shortcuts...")
        gyro_mode = cfg.get_gyro_mode() or "hold"
        own_games_dict = {k: g for k, g in self.own_selected.items()}
        own_games_dict = create_own_shortcuts(
            own_games=own_games_dict,
            selected_keys=[k for k in self.own_selected],
            gyro_mode=gyro_mode,
            on_progress=lambda msg: self._s.log.emit(msg),
            steam_root=self.steam_root,
        )
        _log_to_file("[BREADCRUMB] create_own_shortcuts returned")

        # Update self.selected with enriched own game dicts (shortcut_appid etc)
        self.selected = [
            (k, gd, own_games_dict.get(k, g)) for k, gd, g in self.selected
        ]
        # Rebuild own_games with enriched dicts for compat tool mapping later.
        # Only include own-selected keys - Steam games don't have shortcut_appid.
        own_games = {k: g for k, gd, g in self.selected if g and k in self.own_selected}
        _log_to_file("[BREADCRUMB] own_games rebuilt, starting prefix init")

        # ── Create prefixes + install deps from GE-Proton default_pfx ─────
        # Every selected game gets its prefix preloaded — no exceptions.
        # Own games use their CRC-based prefix (set by create_own_shortcuts).
        # Steam games use their Steam appid prefix.
        # LCD Plutonium games still get a prefix for offline mode; HGL
        # manages its own prefix separately for online mode.
        # ensure_all_prefix_deps handles deduplication and skips prefixes
        # that are already initialized, so passing everything in is safe.
        self._s.progress.emit(30, "Creating Proton prefixes...")
        self._s.log.emit("Creating Proton prefixes and installing dependencies...")
        self._s.pulse_start.emit("Installing prefix dependencies")
        from ge_proton import ensure_all_prefix_deps
        from detect_games import GAMES as _GAMES_MAP
        from wrapper import find_compatdata
        dep_targets = []
        for key, gd, game in self.selected:
            if not game:
                continue
            if key in self.own_selected:
                # Own games always use their CRC-based prefix
                compat = game.get("compatdata_path", "")
            else:
                # Steam games use the per-key appid, not card-level gd["appid"].
                # Card-level appid is wrong for keys like t6zm (212910 vs 202990).
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

        # ── Plutonium games ───────────────────────────────────────────────
        if has_plut:
            # Per-game Plutonium install: copy Plutonium into each prefix,
            # write config.json with game paths. Own games skip the wrapper
            # (shortcuts point at Plutonium directly). Steam games in the
            # mixed flow get the full wrapper treatment.
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
                    source = "own" if key in self.own_selected else "steam"
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
                    # plutonium installer (plutonium_oled.py / plutonium_lcd.py)
                    # owns its own mark_game_setup call so lan_wrapper_path
                    # and other install-side metadata are preserved. wp is
                    # discarded here -- the installer already persisted it.
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

            # Create the DeckOps Plutonium Launcher shortcut. Both OLED
            # and LCD now ship with the launcher — OLED uses sidecar -lan
            # scripts written by plutonium_oled._write_oled_lan_wrapper.
            try:
                from shortcut import create_launcher_shortcut
                create_launcher_shortcut(
                    on_progress=lambda m: self._s.log.emit(m)
                )
            except Exception as ex:
                self._s.log.emit(f"  Launcher shortcut failed: {ex}")

        # ── Install iw4x ─────────────────────────────────────────────────
        _log_to_file("[BREADCRUMB] starting iw4x install phase")
        has_iw4x = any(KEY_CLIENT.get(k) == "iw4x" for k in selected_keys)
        if has_iw4x:
            for key, gd, game in [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) == "iw4x"]:
                base_name = gd["base"]
                self._s.progress.emit(55, f"Setting up {base_name}...")
                def op_iw4x(pct, msg): self._s.progress.emit(55 + int(pct / 100 * 7), msg)
                try:
                    source = "own" if key in self.own_selected else "steam"
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                    install_iw4x(game, self.steam_root, proton, compat, op_iw4x, source=source)
                    cfg.mark_game_setup(key, "iw4x", source=source)
                    self._s.log.emit(f"✓  {base_name} done")
                    logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        # ── Install CoD4 (iw3sp + cod4x) ─────────────────────────────────
        _log_to_file("[BREADCRUMB] starting cod4 install phase")
        if has_cod4:
            cod4_selected = [(k, gd, g) for k, gd, g in self.selected if KEY_CLIENT.get(k) in ("cod4x", "iw3sp")]
            for key, gd, game in cod4_selected:
                base_name = gd["base"]
                self._s.progress.emit(65, f"Setting up {base_name}...")
                def op_cod4(pct, msg): self._s.progress.emit(65 + int(pct / 100 * 10), msg)
                try:
                    source = "own" if key in self.own_selected else "steam"
                    c = KEY_CLIENT.get(key, gd["client"])
                    if source == "own":
                        compat = game.get("compatdata_path", "")
                        cod4x_appid = game.get("shortcut_appid", 7940)
                    else:
                        compat = find_compatdata(self.steam_root, gd["appid"],
                                                  game_install_dir=game.get("install_dir"))
                        cod4x_appid = gd["appid"]
                    if c == "cod4x":
                        install_cod4x(game, self.steam_root, proton, compat, op_cod4,
                                      appid=cod4x_appid)
                    elif c == "iw3sp":
                        install_iw3sp(game, self.steam_root, proton, compat, op_cod4, source=source)
                    cfg.mark_game_setup(key, c, source=source)
                    if base_name not in logged_bases:
                        self._s.log.emit(f"✓  {base_name} done")
                        logged_bases.add(base_name)
                except Exception as ex:
                    self._s.log.emit(f"✗  {base_name} ({key}) failed: {ex}")

        # ── Mark vanilla games ────────────────────────────────────────────
        for key, gd, game in self.selected:
            c = KEY_CLIENT.get(key, "")
            source = "own" if key in self.own_selected else "steam"
            if c == "steam" and not cfg.is_game_setup_for_source(key, source):
                cfg.mark_game_setup(key, "steam", source=source)
                self._s.log.emit(f"✓  {gd['base']} ({key}) ready")

        # ── Game display configs ──────────────────────────────────────────
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
        except Exception as ex:
            self._s.log.emit(f"  Game configs skipped: {ex}")

        # ── Controller templates ──────────────────────────────────────────
        self._s.progress.emit(88, "Installing controller templates...")
        try:
            from controller_profiles import install_controller_templates, assign_controller_profiles, assign_external_controller_profiles
            install_controller_templates(
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            gyro_mode = cfg.get_gyro_mode() or "hold"
            # Neptune profiles always assigned - user may play handheld too
            assign_controller_profiles(
                gyro_mode,
                on_progress=lambda msg: self._s.log.emit(f"  {msg}")
            )
            self._s.log.emit(f"✓  Neptune controller profiles assigned ({gyro_mode} mode)")
            # Docked users also get external controller profiles
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

        # ── Ensure newest GE-Proton is set for own shortcut appids ─────────
        if ge_version:
            try:
                shortcut_appids = [
                    str(g.get("shortcut_appid", ""))
                    for g in own_games.values()
                    if g.get("shortcut_appid")
                ]
                if shortcut_appids:
                    set_compat_tool(shortcut_appids, ge_version)
                    self._s.log.emit(f"✓  {ge_version} set for non-Steam game shortcuts")
            except Exception as ex:
                self._s.log.emit(f"  GE-Proton compat mapping skipped: {ex}")

        # ── Non-Steam shortcuts for Steam games (mixed flow) ─────────────
        # OwnInstallScreen calls create_own_shortcuts() for own games above,
        # but Steam games also need their non-Steam shortcuts (e.g. WaW MP,
        # CoD4 MP) created via create_shortcuts(). Without this, Steam games
        # in the mixed flow don't get their mod client shortcuts.
        if self.steam_selected:
            try:
                from shortcut import create_shortcuts
                steam_installed = {k: g for k, gd, g in self.steam_selected if g}
                steam_keys = [k for k, _, _ in self.steam_selected]
                create_shortcuts(
                    installed_games=steam_installed,
                    selected_keys=steam_keys,
                    gyro_mode=gyro_mode,
                    on_progress=lambda msg: self._s.log.emit(msg),
                    steam_root=self.steam_root,
                )
            except Exception as ex:
                self._s.log.emit(f"  Steam shortcuts skipped: {ex}")

            # Clean up stale launch options from older DeckOps versions
            try:
                from wrapper import clear_launch_options
                for stale_appid in ["7940", "10090"]:
                    clear_launch_options(self.steam_root, stale_appid)
            except Exception:
                pass

            # Set default launch option so Steam Deck skips the mode picker
            has_cod4_steam = any(KEY_CLIENT.get(k) in ("cod4x", "iw3sp")
                                for k, _, _ in self.steam_selected)
            has_waw_steam = any(k in ("t4sp", "t4mp")
                               for k, _, _ in self.steam_selected)
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

        # ── Steam artwork for Steam-sourced games ─────────────────────────
        if self.steam_selected:
            self._s.progress.emit(95, "Applying Steam artwork...")
            try:
                from shortcut import apply_steam_artwork
                steam_keys = [k for k, _, _ in self.steam_selected]
                apply_steam_artwork(
                    selected_keys=steam_keys,
                    on_progress=lambda msg: self._s.log.emit(msg)
                )
            except Exception as ex:
                self._s.log.emit(f"  Steam artwork skipped: {ex}")

        # ── Done ──────────────────────────────────────────────────────────
        _log_to_file("[BREADCRUMB] all phases complete, finishing up")
        cfg.complete_first_run(self.steam_root)
        self._s.progress.emit(100, "All done!")
        self._s.done.emit(True)


# ── OwnScanScreen ─────────────────────────────────────────────────────────────
class OwnScanScreen(QWidget):
    """
    Advanced flow step 1: scan for non-Steam games in ~/Games, ~/games,
    SD card, or a user-chosen folder. Shows detected games with checkboxes
    (all pre-checked). User can uncheck games they don't want, pick a custom
    folder if nothing was found, or skip to Steam-only setup.
    """
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "OwnScanScreen"
        self._own_found = {}       # full scan results
        self._checks = {}          # key -> QCheckBox
        self._extra_paths = []     # user-chosen folders

        lay = QVBoxLayout(self)
        lay.setContentsMargins(60, 40, 60, 40); lay.setSpacing(14)

        # Back button
        back = _btn("\u2190 Back", C_DARK_BTN, size=10, h=30)
        back.setFixedWidth(80)
        back.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        back_row = QHBoxLayout()
        back_row.addWidget(back); back_row.addStretch()
        lay.addLayout(back_row)

        t = QLabel("NON-STEAM GAMES")
        t.setFont(font(36, True)); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#FFF;background:transparent;")
        lay.addWidget(t)

        self.status = _lbl("Scanning for non-Steam games...", 13, C_DIM)
        lay.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setMaximum(100); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(14)
        bw = QHBoxLayout(); bw.addStretch(); bw.addWidget(self.bar, 6); bw.addStretch()
        lay.addLayout(bw)
        lay.addSpacing(6)

        # Scrollable game list
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        lay.addWidget(scroll, stretch=1)

        # No-games message (hidden by default)
        self._no_games_msg = _lbl(
            "No supported games found in the default locations.\n"
            "Use \"Choose Folder\" to pick where your games are installed.",
            13, C_TREY, align=Qt.AlignCenter)
        self._no_games_msg.setVisible(False)
        lay.addWidget(self._no_games_msg)

        # Button row
        btn_row = QHBoxLayout(); btn_row.setSpacing(16)

        self._folder_btn = _btn("Choose Folder", C_DARK_BTN, h=52)
        self._folder_btn.setFixedWidth(200)
        self._folder_btn.clicked.connect(self._pick_folder)

        self._skip_btn = _btn("Skip >>", C_DARK_BTN, h=52)
        self._skip_btn.setFixedWidth(140)
        self._skip_btn.setVisible(False)
        self._skip_btn.clicked.connect(self._skip)

        self._cont_btn = _btn("Continue >>", C_IW, h=52)
        self._cont_btn.setVisible(False)
        self._cont_btn.clicked.connect(self._continue)

        btn_row.addWidget(self._folder_btn)
        btn_row.addWidget(self._skip_btn)
        btn_row.addWidget(self._cont_btn, stretch=1)
        lay.addLayout(btn_row)

    def showEvent(self, e):
        super().showEvent(e)
        self._own_found.clear()
        self._checks.clear()
        self._extra_paths.clear()
        self._no_games_msg.setVisible(False)
        self._skip_btn.setVisible(False)
        self._cont_btn.setVisible(False)
        self.bar.setValue(0)
        self.status.setText("Scanning for non-Steam games...")
        # Clear previous game rows
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        QTimer.singleShot(200, self._scan)

    def _scan(self):
        self.bar.setValue(30)
        self.status.setText("Scanning game folders...")
        self._s = _Sigs()
        self._s.progress.connect(lambda p, m: (self.bar.setValue(p), self.status.setText(m)))
        self._s.done.connect(lambda _: self._show_results())
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        from detect_games import find_own_installed
        results = find_own_installed(
            extra_paths=self._extra_paths if self._extra_paths else None,
            on_progress=lambda msg: self._s.progress.emit(60, msg),
        )
        self._own_found = results
        self._s.progress.emit(100, "Scan complete.")
        self._s.done.emit(True)

    def _show_results(self):
        self.bar.setValue(100)
        self._checks.clear()

        # Clear previous game rows (keep the trailing stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._own_found:
            self.status.setText("No supported games found.")
            self.status.setStyleSheet(f"color:{C_TREY};background:transparent;")
            self._no_games_msg.setVisible(True)
            self._skip_btn.setVisible(True)
            self._cont_btn.setVisible(False)
            return

        self._no_games_msg.setVisible(False)
        self._skip_btn.setVisible(False)
        count = len(self._own_found)
        self.status.setText(f"Found {count} game(s)!")
        self.status.setStyleSheet(f"color:{C_IW};background:transparent;")

        # Build game rows sorted by order
        for key in sorted(self._own_found, key=lambda k: self._own_found[k].get("order", 99)):
            game = self._own_found[key]
            row = QHBoxLayout(); row.setSpacing(12); row.setContentsMargins(8, 6, 8, 6)

            cb = QCheckBox()
            cb.setChecked(True)
            cb.toggled.connect(self._update_continue)
            self._checks[key] = cb
            row.addWidget(cb)

            name_lbl = _lbl(game["name"], 13, "#FFF", align=Qt.AlignLeft, wrap=False)
            row.addWidget(name_lbl, stretch=1)

            path_lbl = _lbl(game["install_dir"], 10, C_DIM, align=Qt.AlignRight, wrap=False)
            row.addWidget(path_lbl)

            cw = QWidget(); cw.setLayout(row)
            cw.setStyleSheet(f"background:{C_CARD};border-radius:6px;")
            self._list_layout.insertWidget(self._list_layout.count() - 1, cw)

        self._cont_btn.setVisible(True)

    def _update_continue(self):
        """Show Continue only if at least one game is checked."""
        any_checked = any(cb.isChecked() for cb in self._checks.values())
        self._cont_btn.setVisible(any_checked)
        if not any_checked:
            self._skip_btn.setVisible(True)
        else:
            self._skip_btn.setVisible(False)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select your games folder", os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder:
            if folder not in self._extra_paths:
                self._extra_paths.append(folder)
            # Re-scan with the new path included
            self.status.setText(f"Scanning {folder}...")
            self.bar.setValue(0)
            self._no_games_msg.setVisible(False)
            self._skip_btn.setVisible(False)
            self._cont_btn.setVisible(False)
            QTimer.singleShot(200, self._scan)

    def _skip(self):
        """Skip own games, go straight to Steam detection."""
        # Set a flag so WelcomeScreen knows to skip own scanning
        ws = self.stack.widget(2)
        ws._steam_only = True
        self.stack.setCurrentIndex(2)

    def _continue(self):
        """Store selected own games on OwnInstallScreen and advance to WelcomeScreen."""
        selected = {}
        for key, cb in self._checks.items():
            if cb.isChecked() and key in self._own_found:
                selected[key] = self._own_found[key]
        # Park own games on OwnInstallScreen - SetupScreen will route there
        # after the user picks their Steam games
        own_screen = self.stack.widget(10)
        own_screen.own_selected = selected
        # Advance to WelcomeScreen for Steam game detection
        ws = self.stack.widget(2)
        ws._steam_only = True
        self.stack.setCurrentIndex(2)


# ── SourceScreen ──────────────────────────────────────────────────────────────
class SourceScreen(QWidget):
    """
    Shown on first run before IntroScreen. Asks how the user installed their
    games. Steam path uses the standard detection flow. Steam or Other detects
    both Steam games and games installed via CD, GOG, Microsoft Store, etc.
    """
    def __init__(self, stack):
        super().__init__(); self.stack = stack; self.screen_name = "SourceScreen"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(80, 60, 80, 60); lay.setSpacing(20)
        lay.addStretch()
        _title_block(lay)
        lay.addSpacing(8)
        lay.addWidget(_lbl("How did you install your games?", 15, "#CCC"))
        lay.addSpacing(8)

        cards = QHBoxLayout(); cards.setSpacing(20)

        steam_card = QFrame()
        steam_card.setStyleSheet(f"QFrame{{background:{C_CARD};border:2px solid #33333F;border-radius:10px;}}QLabel{{background:transparent;}}")
        sc = QVBoxLayout(steam_card); sc.setContentsMargins(24, 24, 24, 24); sc.setSpacing(10)
        rec = QPushButton("RECOMMENDED"); rec.setFont(font(9, True)); rec.setFixedHeight(24); rec.setEnabled(False)
        rec.setStyleSheet(f"QPushButton{{background:{C_IW};color:#FFF;border:none;border-radius:5px;padding:0 10px;}}QPushButton:disabled{{background:{C_IW};color:#FFF;}}")
        sc.addWidget(rec, alignment=Qt.AlignLeft)
        sc.addWidget(_lbl("Steam", 18, "#FFF", bold=True, align=Qt.AlignLeft, wrap=False))
        sc.addWidget(_lbl("Your games were purchased and installed through Steam. DeckOps will detect them automatically.", 12, C_DIM, align=Qt.AlignLeft))
        sc.addWidget(_lbl("Works with games on internal storage or SD card.", 11, "#555568", align=Qt.AlignLeft))
        sc.addStretch()
        steam_btn = _btn("Select Steam >>", C_IW, h=44)
        steam_btn.clicked.connect(lambda: self._pick("steam"))
        sc.addWidget(steam_btn)
        cards.addWidget(steam_card)

        own_card = QFrame()
        own_card.setStyleSheet(f"QFrame{{background:{C_CARD};border:2px solid #33333F;border-radius:10px;}}QLabel{{background:transparent;}}")
        oc = QVBoxLayout(own_card); oc.setContentsMargins(24, 24, 24, 24); oc.setSpacing(10)
        adv = QPushButton("ADVANCED"); adv.setFont(font(9, True)); adv.setFixedHeight(24); adv.setEnabled(False)
        adv.setStyleSheet(f"QPushButton{{background:{C_TREY};color:#FFF;border:none;border-radius:5px;padding:0 10px;}}QPushButton:disabled{{background:{C_TREY};color:#FFF;}}")
        oc.addWidget(adv, alignment=Qt.AlignLeft)
        oc.addWidget(_lbl("Steam & Non-Steam", 18, "#FFF", bold=True, align=Qt.AlignLeft, wrap=False))
        oc.addWidget(_lbl("You have games from the Microsoft Store, CD, GOG, or other storefronts. Steam games are also detected automatically.", 12, C_DIM, align=Qt.AlignLeft))
        oc.addWidget(_lbl("Make sure your non-Steam games are in /home/deck/games before continuing.", 11, "#555568", align=Qt.AlignLeft))
        oc.addStretch()
        own_btn = _btn("Select Steam & Non-Steam >>", C_TREY, h=44)
        own_btn.clicked.connect(lambda: self._pick("own"))
        oc.addWidget(own_btn)
        cards.addWidget(own_card)

        lay.addLayout(cards)
        lay.addStretch()

    def _pick(self, source: str):
        cfg.set_game_source(source)
        self.stack.setCurrentIndex(1)


# ── App ────────────────────────────────────────────────────────────────────────
def _app_style():
    return f"""
* {{ font-family: "{_FONT_FAMILY}"; }}
QWidget {{ background-color:{C_BG}; color:#FFF; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background:{C_BG}; border:none; }}
QScrollBar:vertical {{ background:#1E1E28; width:8px; border-radius:4px; }}
QScrollBar::handle:vertical {{ background:#44445A; border-radius:4px; min-height:30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QProgressBar {{ background:#252535; border-radius:7px; border:none; }}
QProgressBar::chunk {{ background:{C_TREY}; border-radius:7px; }}
QCheckBox::indicator {{ width:22px; height:22px; border:2px solid #555568; border-radius:4px; background:#252535; }}
QCheckBox::indicator:checked {{ background:{C_IW}; border-color:{C_IW}; }}
"""

class DeckOpsWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("DeckOps Nightly"); self.resize(1280,800); self.setMinimumSize(800,500)
        self.stack = QStackedWidget(); self.setCentralWidget(self.stack)
        for cls in [BootstrapScreen,IntroScreen,WelcomeScreen,SetupScreen,InstallScreen,ManagementScreen,ConfigureScreen,ControllerInfoScreen,UpdateScreen,SourceScreen,OwnInstallScreen,OwnScanScreen]:
            self.stack.addWidget(cls(self.stack))
        self.stack.setCurrentIndex(0)

        # Debug label - shows current screen name and index in bottom-left
        self._dbg_label = QLabel(self)
        self._dbg_label.setStyleSheet(
            "color:#444455;background:transparent;padding:4px 8px;"
        )
        self._dbg_label.setFont(font(9))
        self._dbg_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._dbg_label.raise_()
        self.stack.currentChanged.connect(self._update_dbg_label)
        self._update_dbg_label(0)

    def _update_dbg_label(self, idx):
        w = self.stack.widget(idx)
        name = getattr(w, "screen_name", w.__class__.__name__)
        self._dbg_label.setText(f"[{idx}] {name}")
        self._dbg_label.adjustSize()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Keep debug label pinned to bottom-left
        self._dbg_label.move(8, self.height() - self._dbg_label.height() - 8)
        self._dbg_label.raise_()

    def closeEvent(self, e):
        _kill_audio()
        super().closeEvent(e)

def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _load_font()
    app.setStyleSheet(_app_style())
    win = DeckOpsWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
