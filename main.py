"""Application entry point: ``python main.py``."""

from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from rubik import theme
from rubik.window import MainWindow


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor(theme.CANVAS_BOTTOM)
    raised = QColor(theme.PANEL)
    text = QColor(theme.TEXT)
    muted = QColor(theme.TEXT_MUTED)
    accent = QColor(theme.ACCENT)
    dark_text = QColor("#07111E")

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.FIELD))
    palette.setColor(QPalette.ColorRole.AlternateBase, raised)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, raised)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(theme.RED))
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, dark_text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1A2232"))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, muted)

    disabled = QPalette.ColorGroup.Disabled
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(disabled, role, QColor("#4A566B"))
    return palette


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("魔方复原")
    app.setApplicationDisplayName("魔方复原")
    app.setOrganizationName("MagicCube")
    app.setStyle("Fusion")

    theme.init_fonts()
    app.setFont(theme.ui_font(12.5))
    app.setPalette(_dark_palette())
    app.setStyleSheet(theme.stylesheet())
    return app


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.show()
    screen = app.primaryScreen()
    if screen is not None:
        frame = window.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        window.move(frame.topLeft())
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
