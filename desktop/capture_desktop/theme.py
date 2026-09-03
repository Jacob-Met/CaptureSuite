# SPDX-License-Identifier: GPL-3.0-only
"""Design tokens and Qt styling for the CaptureSuite desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ThemeMode = Literal["light", "dark"]


@dataclass(frozen=True)
class ThemeTokens:
    BG: QColor
    PANEL: QColor
    PANEL_ALT: QColor
    PANEL_DEEP: QColor
    BORDER: QColor
    TEXT: QColor
    TEXT_DIM: QColor
    TEXT_FAINT: QColor
    ACCENT: QColor
    GREEN: QColor
    ORANGE: QColor
    RED: QColor
    CYAN: QColor
    PURPLE: QColor
    BLUE: QColor
    LANE_COLORS: dict[str, QColor]
    STATUS_COLORS: dict[str, QColor]
    LEVEL_COLORS: dict[str, QColor]

    def build_stylesheet(self) -> str:
        t = self
        primary_hover = "#4f97ff" if t.BG.lightness() < 128 else "#1d4ed8"
        danger_hover = "#ef5a5f" if t.BG.lightness() < 128 else "#b91c1c"
        danger_disabled_bg = "#4a2b2d" if t.BG.lightness() < 128 else "#fecaca"
        danger_disabled_border = danger_disabled_bg
        return f"""
QWidget {{ color: {t.TEXT.name()}; }}
QMainWindow, QWidget#Root {{ background: {t.BG.name()}; }}

QFrame#Panel {{
    background: {t.PANEL.name()};
    border: 1px solid {t.BORDER.name()};
    border-radius: 6px;
}}
QFrame#Card {{
    background: {t.PANEL.name()};
    border: 1px solid {t.BORDER.name()};
    border-radius: 6px;
}}
QLabel#PanelTitle {{
    color: {t.TEXT.name()};
    font-weight: 600;
    padding: 6px 8px;
}}
QLabel#Dim {{ color: {t.TEXT_DIM.name()}; }}
QLabel#Faint {{ color: {t.TEXT_FAINT.name()}; }}
QLabel#CardTitle {{ font-weight: 600; }}
QLabel#HonestyBanner {{
    color: {t.TEXT_DIM.name()};
    padding: 4px 8px;
    background: {t.PANEL_ALT.name()};
    border: 1px solid {t.BORDER.name()};
    border-radius: 4px;
}}

QPushButton {{
    background: {t.PANEL_ALT.name()};
    border: 1px solid {t.BORDER.name()};
    border-radius: 4px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background: {t.BORDER.name()}; }}
QPushButton:pressed {{ background: {t.PANEL_DEEP.name()}; }}
QPushButton:disabled {{ color: {t.TEXT_FAINT.name()}; background: {t.PANEL.name()}; }}
QPushButton#Primary {{
    background: {t.ACCENT.name()};
    border: 1px solid {t.ACCENT.name()};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {primary_hover}; }}
QPushButton#Danger {{
    background: {t.RED.name()};
    border: 1px solid {t.RED.name()};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#Danger:hover {{ background: {danger_hover}; }}
QPushButton#Danger:disabled {{
    background: {danger_disabled_bg}; border-color: {danger_disabled_border};
    color: {t.TEXT_FAINT.name()};
}}
QPushButton#Ghost {{ background: transparent; border: 1px solid {t.BORDER.name()}; }}
QPushButton#Ghost:hover {{ background: {t.PANEL_ALT.name()}; }}
QPushButton#PreviewStyle {{
    background: {t.PANEL_ALT.name()};
    border: 1px solid {t.BORDER.name()};
    color: {t.TEXT.name()};
    font-weight: 600;
    padding: 3px 10px;
    min-width: 64px;
}}
QPushButton#PreviewStyle:hover {{ background: {t.BORDER.name()}; }}
QPushButton#PreviewStyle:checked {{
    background: {t.ACCENT.name()};
    border: 1px solid {t.ACCENT.name()};
    color: #ffffff;
}}

QTabBar::tab {{
    background: transparent;
    padding: 9px 20px;
    margin-right: 2px;
    color: {t.TEXT_DIM.name()};
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {t.TEXT.name()};
    border-bottom: 2px solid {t.ACCENT.name()};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {t.TEXT.name()}; }}
QTabWidget::pane {{ border: none; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {t.BORDER.name()}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.TEXT_FAINT.name()}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {t.BORDER.name()}; border-radius: 5px; min-width: 30px;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {t.PANEL_DEEP.name()};
    border: 1px solid {t.BORDER.name()};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {t.ACCENT.name()};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {t.ACCENT.name()};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {t.PANEL_ALT.name()};
    border: 1px solid {t.BORDER.name()};
    selection-background-color: {t.ACCENT.name()};
}}

QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {t.BORDER.name()};
    border-radius: 3px;
    background: {t.PANEL_DEEP.name()};
}}
QCheckBox::indicator:checked {{
    background: {t.ACCENT.name()}; border-color: {t.ACCENT.name()};
}}

QGroupBox {{
    border: 1px solid {t.BORDER.name()};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {t.TEXT_DIM.name()};
}}

QToolTip {{
    background: {t.PANEL_ALT.name()};
    color: {t.TEXT.name()};
    border: 1px solid {t.BORDER.name()};
    padding: 4px;
}}

QSplitter::handle {{ background: transparent; }}

QMessageBox, QDialog {{
    background: {t.PANEL.name()};
}}
"""


def _q(hex_color: str) -> QColor:
    return QColor(hex_color)


def dark_tokens() -> ThemeTokens:
    green = _q("#35c46b")
    blue = _q("#5b8def")
    purple = _q("#a06bf0")
    cyan = _q("#34c8d4")
    orange = _q("#f0a13a")
    accent = _q("#3d8bfd")
    red = _q("#e5484d")
    return ThemeTokens(
        BG=_q("#12161c"),
        PANEL=_q("#1a2029"),
        PANEL_ALT=_q("#212934"),
        PANEL_DEEP=_q("#0d1116"),
        BORDER=_q("#2c3542"),
        TEXT=_q("#dfe6ef"),
        TEXT_DIM=_q("#8d9aab"),
        TEXT_FAINT=_q("#5b6673"),
        ACCENT=accent,
        GREEN=green,
        ORANGE=orange,
        RED=red,
        CYAN=cyan,
        PURPLE=purple,
        BLUE=blue,
        LANE_COLORS={
            "emg": green,
            "camera": blue,
            "video": blue,
            "imu": purple,
            "radar": cyan,
            "radar_doppler": cyan,
            "force": orange,
            "mixed": _q("#8d9aab"),
        },
        STATUS_COLORS={
            "ready": green,
            "recording": green,
            "connecting": orange,
            "warning": orange,
            "error": red,
            "disabled": _q("#5b6673"),
            "ok": green,
        },
        LEVEL_COLORS={
            "INFO": accent,
            "WARNING": orange,
            "CRITICAL": red,
        },
    )


def light_tokens() -> ThemeTokens:
    green = _q("#16a34a")
    blue = _q("#1d4ed8")
    purple = _q("#7c3aed")
    cyan = _q("#0891b2")
    orange = _q("#d97706")
    accent = _q("#2563eb")
    red = _q("#dc2626")
    text_faint = _q("#5a6573")
    return ThemeTokens(
        BG=_q("#f4f6f8"),
        PANEL=_q("#ffffff"),
        PANEL_ALT=_q("#eef1f5"),
        PANEL_DEEP=_q("#e2e7ed"),
        BORDER=_q("#c8d0da"),
        TEXT=_q("#1a2332"),
        TEXT_DIM=_q("#5a6573"),
        TEXT_FAINT=text_faint,
        ACCENT=accent,
        GREEN=green,
        ORANGE=orange,
        RED=red,
        CYAN=cyan,
        PURPLE=purple,
        BLUE=blue,
        LANE_COLORS={
            "emg": _q("#15803d"),
            "camera": blue,
            "video": blue,
            "imu": purple,
            "radar": cyan,
            "radar_doppler": cyan,
            "force": _q("#c2410c"),
            "mixed": text_faint,
        },
        STATUS_COLORS={
            "ready": green,
            "recording": green,
            "connecting": orange,
            "warning": orange,
            "error": red,
            "disabled": text_faint,
            "ok": green,
        },
        LEVEL_COLORS={
            "INFO": accent,
            "WARNING": orange,
            "CRITICAL": red,
        },
    )


_active: ThemeTokens = dark_tokens()

# Backward-compatible module-level aliases (updated by apply_theme).
BG = _active.BG
PANEL = _active.PANEL
PANEL_ALT = _active.PANEL_ALT
PANEL_DEEP = _active.PANEL_DEEP
BORDER = _active.BORDER
TEXT = _active.TEXT
TEXT_DIM = _active.TEXT_DIM
TEXT_FAINT = _active.TEXT_FAINT
ACCENT = _active.ACCENT
GREEN = _active.GREEN
ORANGE = _active.ORANGE
RED = _active.RED
CYAN = _active.CYAN
PURPLE = _active.PURPLE
BLUE = _active.BLUE
STATUS_COLORS = _active.STATUS_COLORS
LANE_COLORS = _active.LANE_COLORS
LEVEL_COLORS = _active.LEVEL_COLORS
STYLESHEET = _active.build_stylesheet()


def active_tokens() -> ThemeTokens:
    return _active


def resolve_theme_mode(setting: str) -> ThemeMode:
    """Map settings.theme (system|light|dark) to a concrete palette."""
    if setting == "light":
        return "light"
    if setting == "dark":
        return "dark"
    app = QApplication.instance()
    if app is not None:
        hints = app.styleHints()
        if hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
    return "dark"


def _install_tokens(tokens: ThemeTokens) -> None:
    global _active, BG, PANEL, PANEL_ALT, PANEL_DEEP, BORDER, TEXT, TEXT_DIM
    global TEXT_FAINT, ACCENT, GREEN, ORANGE, RED, CYAN, PURPLE, BLUE
    global STATUS_COLORS, LANE_COLORS, LEVEL_COLORS, STYLESHEET
    _active = tokens
    BG = tokens.BG
    PANEL = tokens.PANEL
    PANEL_ALT = tokens.PANEL_ALT
    PANEL_DEEP = tokens.PANEL_DEEP
    BORDER = tokens.BORDER
    TEXT = tokens.TEXT
    TEXT_DIM = tokens.TEXT_DIM
    TEXT_FAINT = tokens.TEXT_FAINT
    ACCENT = tokens.ACCENT
    GREEN = tokens.GREEN
    ORANGE = tokens.ORANGE
    RED = tokens.RED
    CYAN = tokens.CYAN
    PURPLE = tokens.PURPLE
    BLUE = tokens.BLUE
    STATUS_COLORS = tokens.STATUS_COLORS
    LANE_COLORS = tokens.LANE_COLORS
    LEVEL_COLORS = tokens.LEVEL_COLORS
    STYLESHEET = tokens.build_stylesheet()


def apply_palette(app, tokens: ThemeTokens | None = None) -> None:
    t = tokens or _active
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, t.BG)
    palette.setColor(QPalette.ColorRole.WindowText, t.TEXT)
    palette.setColor(QPalette.ColorRole.Base, t.PANEL)
    palette.setColor(QPalette.ColorRole.AlternateBase, t.PANEL_ALT)
    palette.setColor(QPalette.ColorRole.Text, t.TEXT)
    palette.setColor(QPalette.ColorRole.Button, t.PANEL_ALT)
    palette.setColor(QPalette.ColorRole.ButtonText, t.TEXT)
    palette.setColor(QPalette.ColorRole.Highlight, t.ACCENT)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, t.PANEL_ALT)
    palette.setColor(QPalette.ColorRole.ToolTipText, t.TEXT)
    app.setPalette(palette)
    app.setFont(ui(9))


def apply_theme(app, *, setting: str = "system") -> ThemeTokens:
    """Apply palette + QSS from settings.theme."""
    mode = resolve_theme_mode(setting)
    tokens = light_tokens() if mode == "light" else dark_tokens()
    _install_tokens(tokens)
    apply_palette(app, tokens)
    app.setStyleSheet(tokens.build_stylesheet())
    return tokens


def mono(size: int = 11, bold: bool = False) -> QFont:
    font = QFont("Consolas", size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(bold)
    return font


def ui(size: int = 9, bold: bool = False) -> QFont:
    font = QFont("Segoe UI", size)
    font.setBold(bold)
    return font


def dim(color: QColor, alpha: int) -> QColor:
    faded = QColor(color)
    faded.setAlpha(alpha)
    return faded
