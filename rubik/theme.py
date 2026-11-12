"""Colours, fonts and the Qt style sheet for the app."""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from .render import FACE_COLORS

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
CANVAS_TOP = "#121A27"
CANVAS_MID = "#0A0E15"
CANVAS_BOTTOM = "#06080C"

PANEL = "#0F141E"
PANEL_RAISED = "#151B28"
FIELD = "#0A0E15"

BORDER = "#222C3D"
BORDER_SOFT = "#1A2230"

TEXT = "#EAF0FA"
TEXT_MUTED = "#8592A8"
TEXT_DIM = "#5A667C"

ACCENT = "#7EB6FF"
ACCENT_HOVER = "#9AC9FF"
ACCENT_PRESSED = "#65A3F2"
ACCENT_SOFT = "#15243A"

GREEN = "#5CE0A2"
AMBER = "#F3C25D"
RED = "#FF7B86"

CHIP_BG = "#1A2231"
CHIP_BORDER = "#2A3549"
CHIP_DONE_BG = "#141A25"
CHIP_DONE_TEXT = "#5B687D"

_UI_FAMILY = "PingFang SC"
_MONO_FAMILY = "Menlo"


def init_fonts() -> None:
    global _UI_FAMILY, _MONO_FAMILY
    families = set(QFontDatabase.families())
    for candidate in ("PingFang SC", "Hiragino Sans GB", "Helvetica Neue", "Arial"):
        if candidate in families:
            _UI_FAMILY = candidate
            break
    for candidate in ("Menlo", "SF Mono", "Monaco", "Courier New"):
        if candidate in families:
            _MONO_FAMILY = candidate
            break


def ui_family() -> str:
    return _UI_FAMILY


def mono_family() -> str:
    return _MONO_FAMILY


def ui_font(
    pixel_size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
    letter_spacing: float = 0.0,
) -> QFont:
    font = QFont(_UI_FAMILY)
    font.setPixelSize(round(pixel_size))
    font.setWeight(weight)
    if letter_spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    return font


def mono_font(
    pixel_size: float, weight: QFont.Weight = QFont.Weight.DemiBold
) -> QFont:
    font = QFont(_MONO_FAMILY)
    font.setPixelSize(round(pixel_size))
    font.setWeight(weight)
    return font


def stylesheet() -> str:
    face_rules = "\n".join(
        f'QPushButton[role="turn"][face="{face}"] {{ color: {color}; }}'
        for face, color in FACE_COLORS.items()
    )
    return f"""
    QWidget {{
        color: {TEXT};
        selection-background-color: {ACCENT};
        selection-color: #07111E;
    }}

    QWidget#root {{
        background: {CANVAS_BOTTOM};
    }}

    QWidget#sidePanel {{
        background: {PANEL};
        border-left: 1px solid {BORDER_SOFT};
    }}

    QDialog#stickerDialog {{
        background: {PANEL};
    }}

    QLabel {{
        background: transparent;
    }}

    QLabel#dialogEyebrow {{
        color: {ACCENT};
    }}

    QLabel#dialogTitle {{
        color: #F5F8FF;
        font-size: 24px;
        font-weight: 700;
    }}

    QLabel#dialogSubtitle {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#validation {{
        font-size: 11px;
    }}

    QLabel#eyebrow {{
        color: {ACCENT};
    }}

    QLabel#title {{
        color: #F5F8FF;
        font-size: 30px;
        font-weight: 700;
    }}

    QLabel#subtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    QLabel#section {{
        color: #CBD7EA;
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel#hint {{
        color: {TEXT_DIM};
        font-size: 11px;
    }}

    QLabel#progress {{
        font-family: "{_MONO_FAMILY}";
        font-size: 11px;
        font-weight: 600;
        color: {ACCENT};
        background: {ACCENT_SOFT};
        border: 1px solid #213450;
        border-radius: 9px;
        padding: 2px 9px;
    }}

    QLabel#speedValue {{
        font-family: "{_MONO_FAMILY}";
        font-size: 11px;
        color: {TEXT_MUTED};
    }}

    QLabel#stage {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#status {{
        font-size: 12px;
    }}

    QLabel#shortcuts {{
        color: {TEXT_DIM};
        font-size: 10px;
    }}

    QLabel#legend {{
        color: {TEXT_DIM};
        font-size: 10px;
    }}

    QLineEdit {{
        background: {FIELD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 0 12px;
        color: {TEXT};
        font-family: "{_MONO_FAMILY}";
        font-size: 13px;
    }}

    QLineEdit:hover {{
        border-color: #2D3A50;
    }}

    QLineEdit:focus {{
        border-color: {ACCENT};
    }}

    QLineEdit[error="true"] {{
        border-color: {RED};
    }}

    QComboBox#method {{
        background: {FIELD};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 0 8px;
        color: {TEXT};
        font-size: 12px;
    }}

    QComboBox#method:hover {{
        border-color: #2D3A50;
    }}

    QComboBox#method:focus {{
        border-color: {ACCENT};
    }}

    QComboBox#method:disabled {{
        background: #121824;
        border-color: #1B2331;
        color: {TEXT_DIM};
    }}

    QComboBox#method::drop-down {{
        border: none;
        width: 20px;
    }}

    QComboBox QAbstractItemView {{
        background: {PANEL_RAISED};
        color: {TEXT};
        border: 1px solid {BORDER};
        outline: 0;
        padding: 4px;
        selection-background-color: {ACCENT_SOFT};
        selection-color: {TEXT};
    }}

    QPushButton {{
        border-radius: 10px;
        font-size: 13px;
        padding: 0 12px;
    }}

    QPushButton[role="primary"] {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
        color: #07111E;
        font-weight: 600;
    }}

    QPushButton[role="primary"]:hover {{
        background: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}

    QPushButton[role="primary"]:pressed {{
        background: {ACCENT_PRESSED};
        border-color: {ACCENT_PRESSED};
    }}

    QPushButton[role="primary"]:disabled {{
        background: #263246;
        border-color: #263246;
        color: #5D6B81;
    }}

    QPushButton[role="ghost"] {{
        background: #171E2B;
        border: 1px solid #283247;
        color: #D8E2F2;
    }}

    QPushButton[role="ghost"]:hover {{
        background: #1E2839;
        border-color: #36435D;
    }}

    QPushButton[role="ghost"]:pressed {{
        background: #222D41;
    }}

    QPushButton[role="ghost"]:disabled {{
        background: #121824;
        border-color: #1B2331;
        color: #4A566B;
    }}

    QPushButton[role="turn"] {{
        background: #161D29;
        border: 1px solid #242E40;
        border-radius: 9px;
        font-family: "{_MONO_FAMILY}";
        font-size: 13px;
        font-weight: 700;
        padding: 0;
    }}

    QPushButton[role="turn"]:hover {{
        background: #202A3C;
        border-color: #3A4760;
    }}

    QPushButton[role="turn"]:pressed {{
        background: #263247;
    }}

    {face_rules}

    QPushButton[role="turn"]:disabled {{
        color: #495469;
        background: #111722;
        border-color: #1A2230;
    }}

    QSlider {{
        background: transparent;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: #232D3F;
        border-radius: 2px;
    }}

    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: #EDF4FF;
        border: 2px solid {ACCENT};
        width: 12px;
        height: 12px;
        margin: -5px 0;
        border-radius: 7px;
    }}

    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
    }}

    QToolTip {{
        background-color: #1A2232;
        color: #DCE6F5;
        border: 1px solid #2B364B;
        padding: 5px 8px;
        border-radius: 6px;
        font-size: 11px;
    }}

    QFrame#divider {{
        background: {BORDER_SOFT};
        border: none;
    }}
    """
