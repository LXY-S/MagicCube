"""The interactive 3D cube canvas."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import theme
from .model import Cube
from .render import (
    DEFAULT_PITCH,
    DEFAULT_YAW,
    MAX_PITCH,
    MAX_ZOOM,
    MIN_PITCH,
    MIN_ZOOM,
    build_scene,
)


class CubeView(QWidget):
    """Renders the cubies with a small software renderer and lets the user
    orbit the camera.  Wheel zooms, double-click restores the default view."""

    userInteracted = Signal()

    def __init__(self, cube: Cube, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cube = cube
        self.yaw = DEFAULT_YAW
        self.pitch = DEFAULT_PITCH
        self.zoom = 1.0
        self._anim: tuple[str, int, float] | None = None
        self._dragging = False
        self._last_drag = QPointF()
        self._bg: QPixmap | None = None
        self._bg_key: tuple[int, int, float] | None = None
        self._badge_text = "打乱状态"
        self._badge_color = theme.AMBER

        self.setMinimumSize(460, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    # ------------------------------------------------------------------ API
    def set_cube(self, cube: Cube) -> None:
        self.cube = cube
        self.update()

    def set_anim(self, axis: str, layer: int, angle: float) -> None:
        self._anim = (axis, layer, angle)
        self.update()

    def clear_anim(self) -> None:
        self._anim = None
        self.update()

    def set_badge(self, text: str, color: str) -> None:
        if text != self._badge_text or color != self._badge_color:
            self._badge_text = text
            self._badge_color = color
            self.update()

    def reset_view(self) -> None:
        self.yaw = DEFAULT_YAW
        self.pitch = DEFAULT_PITCH
        self.zoom = 1.0
        self.update()

    # ------------------------------------------------------------- painting
    def resizeEvent(self, event) -> None:  # noqa: N802
        self._bg = None
        super().resizeEvent(event)

    def _rebuild_background(self) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        dpr = float(self.devicePixelRatioF())
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(dpr, dpr)

        base = QLinearGradient(0.0, 0.0, 0.0, float(h))
        base.setColorAt(0.0, QColor(theme.CANVAS_TOP))
        base.setColorAt(0.5, QColor(theme.CANVAS_MID))
        base.setColorAt(1.0, QColor(theme.CANVAS_BOTTOM))
        painter.fillRect(QRectF(0.0, 0.0, float(w), float(h)), QBrush(base))

        # A soft blue aura behind the cube.
        aura = QRadialGradient(
            QPointF(w * 0.5, h * 0.43), max(w, h) * 0.56
        )
        c = QColor(theme.ACCENT)
        c.setAlpha(17)
        aura.setColorAt(0.0, c)
        c2 = QColor(theme.ACCENT)
        c2.setAlpha(0)
        aura.setColorAt(1.0, c2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aura))
        painter.drawRect(QRectF(0.0, 0.0, float(w), float(h)))

        # A very quiet dot grid adds texture without competing with the cube.
        painter.setPen(QPen(QColor(235, 243, 255, 11), 1.0))
        for x in range(30, w, 34):
            for y in range(30, h, 34):
                painter.drawPoint(QPointF(float(x), float(y)))

        # Soft contact shadow under the cube.
        painter.save()
        painter.translate(w * 0.5, h * 0.5 + min(w, h) * 0.335)
        painter.scale(1.0, 0.20)
        shadow = QRadialGradient(QPointF(0.0, 0.0), min(w, h) * 0.33)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 120))
        shadow.setColorAt(0.55, QColor(0, 0, 0, 55))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0.0, 0.0), min(w, h) * 0.36, min(w, h) * 0.36)
        painter.restore()

        # Vignette.
        vig = QRadialGradient(
            QPointF(w * 0.5, h * 0.45), max(w, h) * 0.78
        )
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(0.6, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 105))
        painter.setBrush(QBrush(vig))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(0.0, 0.0, float(w), float(h)))

        painter.end()
        self._bg = pm
        self._bg_key = (w, h, dpr)

    def paintEvent(self, event) -> None:  # noqa: N802
        key = (self.width(), self.height(), float(self.devicePixelRatioF()))
        if self._bg is None or self._bg_key != key:
            self._rebuild_background()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self._bg is not None:
            painter.drawPixmap(0, 0, self._bg)

        polygons = build_scene(
            self.cube,
            float(self.width()),
            float(self.height()),
            self.yaw,
            self.pitch,
            self.zoom,
            self._anim,
        )
        for poly in polygons:
            points = QPolygonF([QPointF(x, y) for x, y in poly.points])
            painter.setBrush(QColor(poly.fill))
            painter.setPen(
                QPen(
                    QColor(poly.outline),
                    poly.width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPolygon(points)

        self._paint_chrome(painter)

    def _paint_chrome(self, painter: QPainter) -> None:
        w = float(self.width())
        h = float(self.height())

        # Status badge (top-left).
        font = theme.ui_font(11.0, QFont.Weight.DemiBold)
        fm = QFontMetricsF(font)
        text_width = fm.horizontalAdvance(self._badge_text)
        x, y = 26.0, 22.0
        height = 30.0
        padding = 12.0
        dot = 6.0
        gap = 8.0
        width = padding * 2 + dot + gap + text_width
        badge = QRectF(x, y, width, height)
        path = QPainterPath()
        path.addRoundedRect(badge, height / 2.0, height / 2.0)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._badge_color))
        painter.drawEllipse(
            QPointF(x + padding + dot / 2.0, y + height / 2.0),
            dot / 2.0,
            dot / 2.0,
        )
        painter.setFont(font)
        painter.setPen(QColor("#C8D4E6"))
        painter.drawText(
            QRectF(x + padding + dot + gap, y, text_width + 2.0, height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._badge_text,
        )

        # Notation legend (top-right).
        painter.setFont(theme.ui_font(10.5))
        painter.setPen(QColor(theme.TEXT_DIM))
        painter.drawText(
            QRectF(max(0.0, w - 400.0), 23.0, 374.0, 28.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "U 上 · D 下 · L 左 · R 右 · F 前 · B 后",
        )

        # Interaction hints (bottom-left).
        painter.setFont(theme.ui_font(10.5))
        painter.setPen(QColor(theme.TEXT_DIM))
        painter.drawText(
            QRectF(26.0, h - 42.0, 460.0, 20.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "拖动旋转 · 滚轮缩放 · 双击复位",
        )

    # ---------------------------------------------------------- interaction
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._dragging = True
            self._last_drag = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.userInteracted.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position() - self._last_drag
            self._last_drag = event.position()
            self.yaw += delta.x() * 0.35
            self.pitch += delta.y() * 0.30
            self.pitch = max(MIN_PITCH, min(MAX_PITCH, self.pitch))
            self.update()
            self.userInteracted.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            self.userInteracted.emit()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta:
            self.zoom *= math.exp(delta * 0.0012)
            self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom))
            self.update()
            self.userInteracted.emit()
            event.accept()
            return
        super().wheelEvent(event)
