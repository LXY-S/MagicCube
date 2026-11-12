"""Small custom widgets: the step-sequence strip."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme
from .model import Move


class MoveStrip(QWidget):
    """A wrapping row of move chips with progress highlighting."""

    PAD = 14
    CHIP_H = 28.0
    GAP_X = 6.0
    GAP_Y = 7.0
    RADIUS = 8.0
    HEIGHT = 132
    SCROLL_RESERVE = 9.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._moves: list[Move] = []
        self._index = 0
        self._scroll = 0.0
        self._chip_rects: list[QRectF] = []
        self._content_h = 0.0
        self._empty_hint = "应用打乱后，这里会显示复原步骤"

        self._font = theme.mono_font(13.5, QFont.Weight.DemiBold)
        self._fm = QFontMetricsF(self._font)
        self._hint_font = theme.ui_font(11.5, QFont.Weight.Normal)

        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip("复原步骤：高亮的是下一步")

    # ------------------------------------------------------------------ API
    def set_plan(
        self,
        moves: list[Move],
        index: int,
        empty_hint: str | None = None,
    ) -> None:
        if empty_hint is not None:
            self._empty_hint = empty_hint
        changed = moves != self._moves
        self._moves = list(moves)
        self._index = max(0, min(index, len(self._moves)))
        if changed:
            self._scroll = 0.0
        self._relayout()
        self.update()

    def set_empty_hint(self, text: str) -> None:
        if text != self._empty_hint:
            self._empty_hint = text
            self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        max_scroll = self._max_scroll()
        if max_scroll <= 0:
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        self._scroll -= steps * self.CHIP_H
        self._scroll = max(0.0, min(self._scroll, max_scroll))
        self.update()
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    # -------------------------------------------------------------- layout
    def _viewport_h(self) -> float:
        return self.height() - 2 * self.PAD

    def _max_scroll(self) -> float:
        return max(0.0, self._content_h - self._viewport_h())

    def _relayout(self) -> None:
        self._chip_rects = []
        self._content_h = 0.0
        if not self._moves or self.width() < 60:
            self._scroll = 0.0
            return

        wrap_right = self.width() - self.PAD - self.SCROLL_RESERVE
        x = self.PAD
        y = 0.0
        for move in self._moves:
            width = self._fm.horizontalAdvance(move.pretty) + 20.0
            if x > self.PAD and x + width > wrap_right:
                x = self.PAD
                y += self.CHIP_H + self.GAP_Y
            self._chip_rects.append(QRectF(x, y, width, self.CHIP_H))
            x += width + self.GAP_X
        self._content_h = y + self.CHIP_H

        self._scroll = min(self._scroll, self._max_scroll())
        self._ensure_current_visible()

    def _ensure_current_visible(self) -> None:
        if not self._chip_rects:
            return
        index = min(self._index, len(self._chip_rects) - 1)
        rect = self._chip_rects[index]
        viewport = self._viewport_h()
        if rect.top() < self._scroll:
            self._scroll = rect.top()
        elif rect.bottom() > self._scroll + viewport:
            self._scroll = rect.bottom() - viewport
        self._scroll = max(0.0, min(self._scroll, self._max_scroll()))

    # ------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        container = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(container, 12.0, 12.0)
        painter.fillPath(path, QColor(theme.FIELD))
        painter.setPen(QPen(QColor(theme.BORDER_SOFT), 1.0))
        painter.drawPath(path)

        inner = QRectF(1.0, self.PAD - 3.0, w - 2.0, h - 2 * self.PAD + 6.0)
        painter.setClipRect(inner)

        if not self._moves:
            painter.setFont(self._hint_font)
            painter.setPen(QColor(theme.TEXT_DIM))
            painter.drawText(
                QRectF(self.PAD, 0.0, w - 2 * self.PAD, h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._empty_hint,
            )
            return

        for index, (move, rect) in enumerate(zip(self._moves, self._chip_rects)):
            chip = QRectF(
                rect.x(),
                rect.y() + self.PAD - self._scroll,
                rect.width(),
                rect.height(),
            )
            if chip.bottom() < -4 or chip.top() > h + 4:
                continue

            if index < self._index:
                self._paint_done_chip(painter, chip, move)
            elif index == self._index:
                self._paint_current_chip(painter, chip, move)
            else:
                self._paint_pending_chip(painter, chip, move)

        painter.setClipping(False)
        max_scroll = self._max_scroll()
        if max_scroll > 0:
            viewport = self._viewport_h()
            thumb_h = max(22.0, viewport * viewport / max(self._content_h, 1.0))
            travel = viewport - thumb_h
            thumb_y = self.PAD + (self._scroll / max_scroll) * travel
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 28))
            painter.drawRoundedRect(QRectF(w - 8.0, thumb_y, 3.0, thumb_h), 1.5, 1.5)

    def _paint_done_chip(self, painter: QPainter, rect: QRectF, move: Move) -> None:
        painter.setPen(QPen(QColor(theme.CHIP_DONE_BG), 1.0))
        painter.setBrush(QColor(theme.CHIP_DONE_BG))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.setFont(self._font)
        painter.setPen(QColor(theme.CHIP_DONE_TEXT))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, move.pretty)

    def _paint_pending_chip(self, painter: QPainter, rect: QRectF, move: Move) -> None:
        painter.setPen(QPen(QColor(theme.CHIP_BORDER), 1.0))
        painter.setBrush(QColor(theme.CHIP_BG))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.setFont(self._font)
        painter.setPen(QColor("#DCE6F5"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, move.pretty)

    def _paint_current_chip(self, painter: QPainter, rect: QRectF, move: Move) -> None:
        glow = QColor(theme.ACCENT)
        glow.setAlpha(34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), self.RADIUS + 3, self.RADIUS + 3)

        painter.setPen(QPen(QColor(theme.ACCENT_HOVER), 1.0))
        painter.setBrush(QColor(theme.ACCENT))
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.setFont(self._font)
        painter.setPen(QColor("#07111E"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, move.pretty)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(340, self.HEIGHT)
