"""Modal editor for the 54 visible sticker colours."""

from __future__ import annotations

import html
from collections import Counter

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .facelets import (
    FACELET_FACES,
    NET_LAYOUT,
    normalise_facelets,
    solved_facelets,
)
from .methods import (
    DEFAULT_METHOD_ID,
    Solution,
    solve_facelets_with_method,
)
from .model import FACE_NAMES_ZH, FACE_ORDER, Cube, Move
from .render import BODY_COLOR, FACE_COLORS
from .solver import SolverError


COLOR_NAMES_ZH: dict[str, str] = {
    "U": "白",
    "D": "黄",
    "L": "橙",
    "R": "红",
    "F": "绿",
    "B": "蓝",
}


def _ink_for(hex_color: str) -> str:
    """Pick readable dark/light text for a sticker colour."""
    color = QColor(hex_color)
    luminance = (
        0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    ) / 255.0
    return "#07111E" if luminance > 0.55 else "#FFFFFF"


class StickerEditorCanvas(QWidget):
    """The unfolded cube net; click or drag to paint stickers."""

    changed = Signal()

    def __init__(
        self, facelets: dict[str, list[str]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.colors = normalise_facelets(facelets)
        self._active = "U"
        self._hover: tuple[str, int] | None = None
        self._painting = False
        self._cells: dict[tuple[str, int], QRectF] = {}

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMinimumSize(480, 380)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(560, 410)

    # ---------------------------------------------------------- public API
    def facelets(self) -> dict[str, list[str]]:
        return {face: list(self.colors[face]) for face in FACELET_FACES}

    def set_facelets(self, facelets: dict[str, list[str]]) -> None:
        self.colors = normalise_facelets(facelets)
        self._hover = None
        self.update()
        self.changed.emit()

    def set_active_color(self, color: str) -> None:
        if color in FACE_COLORS:
            self._active = color
            self.update()

    # ------------------------------------------------------------- painting
    def _compute_geometry(self) -> None:
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))
        margin = 16.0
        label_h = 17.0
        col_gap = 12.0
        row_gap = 10.0

        available_w = width - 2 * margin
        available_h = height - 2 * margin
        side = min(
            (available_w - 3 * col_gap) / 4.0,
            (available_h - 2 * row_gap - 3 * label_h) / 3.0,
        )
        side = max(38.0, min(side, 112.0))

        net_w = 4 * side + 3 * col_gap
        net_h = 3 * side + 3 * label_h + 2 * row_gap
        x0 = (width - net_w) / 2.0
        y0 = (height - net_h) / 2.0

        self._face_rects: dict[str, QRectF] = {}
        self._label_rects: dict[str, QRectF] = {}
        cells: dict[tuple[str, int], QRectF] = {}
        cell_pad = max(4.0, side * 0.052)
        cell_gap = max(2.4, side * 0.028)
        cell_side = (side - 2 * cell_pad - 2 * cell_gap) / 3.0

        for face, (column, row) in NET_LAYOUT.items():
            face_x = x0 + column * (side + col_gap)
            face_y = y0 + row * (side + label_h + row_gap) + label_h
            self._face_rects[face] = QRectF(face_x, face_y, side, side)
            self._label_rects[face] = QRectF(
                face_x, face_y - label_h, side, label_h
            )
            for index in range(9):
                cell_row, cell_col = divmod(index, 3)
                cell_x = face_x + cell_pad + cell_col * (cell_side + cell_gap)
                cell_y = face_y + cell_pad + cell_row * (cell_side + cell_gap)
                cells[(face, index)] = QRectF(
                    cell_x, cell_y, cell_side, cell_side
                )
        self._cells = cells

    def paintEvent(self, event) -> None:  # noqa: N802
        self._compute_geometry()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        field = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(QPen(QColor(theme.BORDER_SOFT), 1.0))
        painter.setBrush(QColor(theme.FIELD))
        painter.drawRoundedRect(field, 14.0, 14.0)

        label_font = theme.ui_font(
            10.0, QFont.Weight.DemiBold, letter_spacing=0.4
        )
        for face in FACELET_FACES:
            face_rect = self._face_rects[face]
            painter.setPen(QPen(QColor(theme.BORDER), 1.0))
            painter.setBrush(QColor(BODY_COLOR))
            painter.drawRoundedRect(face_rect, 10.0, 10.0)

            painter.setFont(label_font)
            painter.setPen(QColor(theme.TEXT_DIM))
            painter.drawText(
                self._label_rects[face],
                int(
                    Qt.AlignmentFlag.AlignHCenter
                    | Qt.AlignmentFlag.AlignVCenter
                ),
                f"{face} · {FACE_NAMES_ZH[face]}",
            )

            for index, color in enumerate(self.colors[face]):
                cell = self._cells[(face, index)]
                fill = QColor(FACE_COLORS[color])
                hovered = self._hover == (face, index)
                if hovered:
                    pen = QPen(QColor(_ink_for(FACE_COLORS[color])), 2.0)
                else:
                    pen = QPen(QColor(0, 0, 0, 84), 1.0)
                painter.setPen(pen)
                painter.setBrush(fill)
                painter.drawRoundedRect(
                    cell.adjusted(0.75, 0.75, -0.75, -0.75),
                    max(3.0, cell.width() * 0.16),
                    max(3.0, cell.width() * 0.16),
                )

        painter.end()

    # --------------------------------------------------------------- mouse
    def _cell_at(self, point: QPointF) -> tuple[str, int] | None:
        for key, rect in self._cells.items():
            if rect.contains(point):
                return key
        return None

    def _paint_cell(self, cell: tuple[str, int] | None) -> None:
        if cell is None:
            return
        face, index = cell
        if self.colors[face][index] != self._active:
            self.colors[face][index] = self._active
            self.update()
            self.changed.emit()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._painting = True
            self._paint_cell(self._cell_at(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        cell = self._cell_at(event.position())
        if cell != self._hover:
            self._hover = cell
            self.update()
        if self._painting and event.buttons() & Qt.MouseButton.LeftButton:
            self._paint_cell(cell)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._painting = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(event)


class StickerEditorDialog(QDialog):
    """Modal dialog returning ``result_cube`` and ``result_plan`` on accept."""

    def __init__(
        self,
        facelets: dict[str, list[str]],
        parent: QWidget | None = None,
        method_id: str = DEFAULT_METHOD_ID,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stickerDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("自定义色块")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(560, 700)
        self.resize(600, 720)

        self.method_id = method_id
        self.result_cube: Cube | None = None
        self.result_plan: list[Move] = []
        self.result_solution: Solution | None = None
        self._solver_error: str | None = None
        self._solving = False
        self._counts_ok = False
        self._centers_ok = False

        self._build_ui(facelets)
        self._update_counts()
        self._select_color("U")

    # ------------------------------------------------------------------ UI
    def _build_ui(self, facelets: dict[str, list[str]]) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(7)
        dot = QLabel()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background: {theme.ACCENT}; border-radius: 3px;")
        eyebrow = QLabel("STICKER EDITOR")
        eyebrow.setObjectName("dialogEyebrow")
        eyebrow.setFont(
            theme.ui_font(9.5, QFont.Weight.DemiBold, letter_spacing=2.0)
        )
        brand_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row.addWidget(eyebrow, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row.addStretch(1)
        outer.addLayout(brand_row)

        outer.addSpacing(6)
        title = QLabel("自定义色块")
        title.setObjectName("dialogTitle")
        outer.addWidget(title)

        outer.addSpacing(3)
        subtitle = QLabel(
            "点击或拖动色块上色。六个中心块的颜色决定每个面的目标配色。"
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        outer.addSpacing(14)
        self.canvas = StickerEditorCanvas(facelets, self)
        self.canvas.changed.connect(self._on_canvas_changed)
        outer.addWidget(self.canvas, 1)

        outer.addSpacing(12)
        palette_header = QHBoxLayout()
        palette_header.setContentsMargins(0, 0, 0, 0)
        palette_header.setSpacing(8)
        caption = QLabel("选择颜色")
        caption.setObjectName("section")
        palette_header.addWidget(caption)
        palette_header.addStretch(1)
        hint = QLabel("每个面 9 块 · 每种颜色恰好 9 块")
        hint.setObjectName("hint")
        palette_header.addWidget(hint)
        outer.addLayout(palette_header)

        outer.addSpacing(7)
        palette_row = QHBoxLayout()
        palette_row.setContentsMargins(0, 0, 0, 0)
        palette_row.setSpacing(8)
        self.swatch_buttons: dict[str, QPushButton] = {}
        self.count_labels: dict[str, QLabel] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for color in FACE_ORDER:
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(4)

            button = QPushButton(COLOR_NAMES_ZH[color])
            button.setCheckable(True)
            button.setFixedHeight(38)
            button.setMinimumWidth(54)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(self._swatch_style(color))
            button.setToolTip(
                f"{COLOR_NAMES_ZH[color]}色 · 初始 {color} 面颜色"
            )
            button.clicked.connect(
                lambda checked=False, c=color: self._select_color(c)
            )
            self._group.addButton(button)
            self.swatch_buttons[color] = button
            column.addWidget(button)

            count = QLabel("0 / 9")
            count.setFont(theme.mono_font(10.0))
            count.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count.setMinimumHeight(14)
            self.count_labels[color] = count
            column.addWidget(count)
            palette_row.addLayout(column, 1)
        outer.addLayout(palette_row)

        outer.addSpacing(8)
        self.validation_label = QLabel()
        self.validation_label.setObjectName("validation")
        self.validation_label.setTextFormat(Qt.TextFormat.RichText)
        self.validation_label.setWordWrap(True)
        self.validation_label.setMinimumHeight(34)
        self.validation_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.validation_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        outer.addWidget(self.validation_label)

        outer.addSpacing(10)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)

        self.reset_button = self._dialog_button(
            "恢复已复原", "ghost", width=116
        )
        self.reset_button.setToolTip("把所有 54 个色块恢复为标准已复原配色")
        self.reset_button.clicked.connect(self._reset_solved)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)

        self.cancel_button = self._dialog_button("取消", "ghost", width=84)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)

        self.apply_button = self._dialog_button("应用", "primary", width=96)
        self.apply_button.setDefault(True)
        self.apply_button.setToolTip("验证色块并生成逐步复原方案")
        self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.apply_button)
        outer.addLayout(buttons)

    def _dialog_button(
        self, text: str, role: str, width: int | None = None
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("role", role)
        button.setFixedHeight(40)
        if width is not None:
            button.setFixedWidth(width)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _swatch_style(self, color: str) -> str:
        fill = FACE_COLORS[color]
        ink = _ink_for(fill)
        soft = "rgba(0, 0, 0, 75)" if ink == "#07111E" else "rgba(255, 255, 255, 80)"
        family = theme.ui_family()
        return f"""
        QPushButton {{
            background: {fill};
            color: {ink};
            border: 1px solid {soft};
            border-radius: 9px;
            font-family: "{family}";
            font-size: 12.5px;
            font-weight: 600;
            padding: 0;
        }}
        QPushButton:hover {{ border: 2px solid {ink}; }}
        QPushButton:checked {{ border: 2px solid {ink}; }}
        QPushButton:focus {{ border: 2px solid {ink}; }}
        """

    # ------------------------------------------------------------- palette
    def _select_color(self, color: str) -> None:
        button = self.swatch_buttons[color]
        if not button.isChecked():
            button.setChecked(True)
        self.canvas.set_active_color(color)
        for code, swatch in self.swatch_buttons.items():
            name = COLOR_NAMES_ZH[code]
            swatch.setText(f"✓ {name}" if code == color else name)

    def _on_canvas_changed(self) -> None:
        self._solver_error = None
        self._update_counts()

    def _update_counts(self) -> None:
        colors = self.canvas.facelets()
        counts = Counter(color for cells in colors.values() for color in cells)
        self._counts_ok = True
        for color in FACE_ORDER:
            count = counts.get(color, 0)
            ok = count == 9
            if not ok:
                self._counts_ok = False
            label = self.count_labels[color]
            label.setText(f"{count} / 9")
            label.setStyleSheet(
                f"color: {theme.TEXT_DIM if ok else theme.AMBER};"
            )

        centers = {colors[face][4] for face in FACELET_FACES}
        self._centers_ok = len(centers) == 6
        self._update_validation(counts)
        self._update_apply_enabled()

    def _update_validation(self, counts: Counter | None = None) -> None:
        if self._solver_error:
            self._set_validation(self._solver_error, "error")
            return
        if not self._counts_ok:
            if counts is None:
                colors = self.canvas.facelets()
                counts = Counter(
                    color for cells in colors.values() for color in cells
                )
            wrong = [
                f"{COLOR_NAMES_ZH[color]} {counts.get(color, 0)}/9"
                for color in FACE_ORDER
                if counts.get(color, 0) != 9
            ]
            self._set_validation(
                "每种颜色需要恰好 9 块：" + " · ".join(wrong), "warn"
            )
            return
        if not self._centers_ok:
            self._set_validation(
                "六个中心块的颜色需要互不相同（中心块决定每面的目标颜色）",
                "warn",
            )
            return
        self._set_validation(
            "颜色数量与中心块均正常 · 点击应用生成复原步骤", "ok"
        )

    def _set_validation(self, text: str, tone: str) -> None:
        colors = {
            "ok": (theme.GREEN, "#A9EDCB"),
            "warn": (theme.AMBER, "#F4D69B"),
            "error": (theme.RED, "#FFB0B7"),
            "muted": (theme.TEXT_DIM, theme.TEXT_MUTED),
        }
        dot, text_color = colors.get(tone, colors["muted"])
        self.validation_label.setText(
            f'<span style="color:{dot}; font-weight:600;">●</span>'
            f'&nbsp;&nbsp;<span style="color:{text_color};">'
            f"{html.escape(text)}</span>"
        )
        self.validation_label.setToolTip(text)

    def _update_apply_enabled(self) -> None:
        self.apply_button.setEnabled(
            self._counts_ok and self._centers_ok and not self._solving
        )

    def _reset_solved(self) -> None:
        self.canvas.set_facelets(solved_facelets())

    # --------------------------------------------------------------- apply
    def _apply(self) -> None:
        if not (self._counts_ok and self._centers_ok) or self._solving:
            return

        # Snapshot before processEvents(): the dialog must solve exactly the
        # layout that was validated, even if a stray event arrives meanwhile.
        facelets = self.canvas.facelets()
        self._solver_error = None
        self._solving = True
        self.apply_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.canvas.setEnabled(False)
        self._set_validation("正在生成复原方案…", "muted")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            cube, solution = solve_facelets_with_method(
                facelets, self.method_id
            )
        except SolverError as exc:
            self._solver_error = str(exc)
            self._set_validation(str(exc), "error")
            return
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self._solver_error = f"生成复原方案时出现异常：{exc}"
            self._set_validation(self._solver_error, "error")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self._solving = False
            self.canvas.setEnabled(True)
            self.reset_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self._update_apply_enabled()

        self.result_cube = cube
        self.result_solution = solution
        self.result_plan = solution.moves
        self.accept()

    def reject(self) -> None:
        """Ignore Cancel/Escape while the solver is running."""
        if self._solving:
            return
        super().reject()
