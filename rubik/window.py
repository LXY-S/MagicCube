"""Main window and playback state machine."""

from __future__ import annotations

import html
import random
import time
from collections import deque

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .cube_view import CubeView
from .facelets import cube_to_facelets
from .model import (
    FACE_NAMES_ZH,
    FACE_ORDER,
    MOVE_DEFS,
    Cube,
    Move,
    format_moves,
    parse_moves,
    random_scramble,
)
from .methods import (
    DEFAULT_METHOD_ID,
    METHODS,
    Solution,
    StagePlan,
    method_by_id,
    solve_with_method,
)
from .sticker_dialog import StickerEditorDialog
from .widgets import MoveStrip

DEMO_SCRAMBLE = "R U2 R' F L2 D' R U' B2 L' F2"
MAX_ANIMATED_SCRAMBLE = 24


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("魔方复原 · Rubik's Cube")
        self.resize(1280, 830)
        self.setMinimumSize(1120, 780)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.cube = Cube()
        self.plan: list[Move] = []
        self.plan_index = 0
        self.method_id = DEFAULT_METHOD_ID
        self.solution: Solution | None = None

        self.scramble_queue: deque[Move] = deque()
        self.scrambling = False
        self.playing = False
        self.anim: dict | None = None
        self.next_play_at = 0.0
        self.celebration: dict | None = None

        self.speed = 1.0

        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._on_tick)

        self._build_ui()

        self.cube_view.userInteracted.connect(self._on_view_interaction)
        self.load_scramble(DEMO_SCRAMBLE, animate=False)
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    # ================================================================== UI
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.cube_view = CubeView(self.cube, self)
        root.addWidget(self.cube_view, 1)

        panel = QWidget(self)
        panel.setObjectName("sidePanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setFixedWidth(424)
        root.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(0)

        # ------------------------------------------------------- header
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"background: {theme.ACCENT}; border-radius: 4px;"
        )
        eyebrow = QLabel("RUBIK'S CUBE · 3D")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setFont(
            theme.ui_font(10.0, QFont.Weight.DemiBold, letter_spacing=2.2)
        )
        brand_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row.addWidget(eyebrow, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row.addStretch(1)
        layout.addLayout(brand_row)

        layout.addSpacing(9)
        title = QLabel("魔方复原")
        title.setObjectName("title")
        layout.addWidget(title)

        layout.addSpacing(3)
        subtitle = QLabel("自定义打乱，逐步观看 3D 复原动画")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(22)

        # ---------------------------------------------------- scramble
        layout.addWidget(
            self._section_header("打乱设置", "从已复原状态开始")
        )
        layout.addSpacing(10)

        entry_row = QHBoxLayout()
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.setSpacing(8)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("例如：R U R' U' F2")
        self.entry.setMaxLength(240)
        self.entry.setFixedHeight(44)
        self.entry.setToolTip("支持 U、D、L、R、F、B，以及 ' 和 2；空格可省略")
        self.entry.returnPressed.connect(self._on_apply)
        self.entry.textChanged.connect(self._clear_entry_error)
        entry_row.addWidget(self.entry, 1)

        self.random_button = self._button("随机", "ghost", height=44, width=66)
        self.random_button.setToolTip("生成 20 步随机打乱")
        self.random_button.clicked.connect(self._on_random)
        entry_row.addWidget(self.random_button)
        layout.addLayout(entry_row)

        layout.addSpacing(8)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        self.apply_button = self._button("应用打乱", "primary", height=44)
        self.apply_button.setToolTip("从此状态开始，生成可逐步执行的复原方案")
        self.apply_button.clicked.connect(self._on_apply)
        action_row.addWidget(self.apply_button, 1)

        self.sticker_button = self._button(
            "编辑色块", "ghost", height=44, width=94
        )
        self.sticker_button.setToolTip(
            "打开色块编辑器，自定义全部 54 个色块"
        )
        self.sticker_button.clicked.connect(self._open_sticker_editor)
        action_row.addWidget(self.sticker_button)

        self.reset_button = self._button("重置", "ghost", height=44, width=74)
        self.reset_button.setToolTip("立即恢复为已复原状态")
        self.reset_button.clicked.connect(self._on_reset)
        action_row.addWidget(self.reset_button)
        layout.addLayout(action_row)

        layout.addSpacing(22)

        # ------------------------------------------------------- steps
        steps_header = QWidget()
        sh = QHBoxLayout(steps_header)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(8)
        steps_title = QLabel("复原步骤")
        steps_title.setObjectName("section")
        sh.addWidget(steps_title)
        sh.addStretch(1)
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setObjectName("progress")
        self.progress_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        sh.addWidget(self.progress_label)
        layout.addWidget(steps_header)

        layout.addSpacing(9)
        method_row = QHBoxLayout()
        method_row.setContentsMargins(0, 0, 0, 0)
        method_row.setSpacing(8)

        method_caption = QLabel("复原方法")
        method_caption.setObjectName("section")
        method_row.addWidget(method_caption)

        self.method_combo = QComboBox()
        self.method_combo.setObjectName("method")
        self.method_combo.setFixedHeight(30)
        self.method_combo.setFixedWidth(128)
        self.method_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.method_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.method_combo.setToolTip(
            "切换复原方法；切换后会从当前状态重新生成步骤"
        )
        for method in METHODS:
            self.method_combo.addItem(method.label, method.id)
            self.method_combo.setItemData(
                self.method_combo.count() - 1,
                f"{method.title} · {method.description}",
                Qt.ItemDataRole.ToolTipRole,
            )
        self.method_combo.setCurrentIndex(
            self.method_combo.findData(DEFAULT_METHOD_ID)
        )
        self.method_combo.currentIndexChanged.connect(
            self._on_method_changed
        )
        method_row.addWidget(self.method_combo)

        self.stage_label = QLabel("")
        self.stage_label.setObjectName("stage")
        self.stage_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.stage_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        method_row.addWidget(self.stage_label, 1)
        layout.addLayout(method_row)

        layout.addSpacing(9)
        self.move_strip = MoveStrip()
        layout.addWidget(self.move_strip)

        layout.addSpacing(10)
        play_row = QHBoxLayout()
        play_row.setContentsMargins(0, 0, 0, 0)
        play_row.setSpacing(8)

        self.prev_button = self._button("◀ 上一步", "ghost", height=40)
        self.prev_button.setToolTip("回退一步（←）")
        self.prev_button.clicked.connect(self._step_back)
        play_row.addWidget(self.prev_button, 1)

        self.next_button = self._button("下一步 ▶", "ghost", height=40)
        self.next_button.setToolTip("执行下一步（→）")
        self.next_button.clicked.connect(self._step_forward)
        play_row.addWidget(self.next_button, 1)

        self.play_button = self._button("播放", "primary", height=40)
        self.play_button.setToolTip("自动播放 / 暂停（空格）")
        self.play_button.clicked.connect(self._toggle_play)
        play_row.addWidget(self.play_button, 1)
        layout.addLayout(play_row)

        layout.addSpacing(9)
        speed_row = QHBoxLayout()
        speed_row.setContentsMargins(0, 0, 0, 0)
        speed_row.setSpacing(10)
        speed_caption = QLabel("速度")
        speed_caption.setObjectName("hint")
        speed_row.addWidget(speed_caption)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 20)
        self.speed_slider.setValue(10)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setPageStep(2)
        self.speed_slider.setFixedHeight(24)
        self.speed_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.speed_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speed_slider.setToolTip("调整动画速度")
        speed_row.addWidget(self.speed_slider, 1)

        self.speed_value = QLabel("1.0×")
        self.speed_value.setObjectName("speedValue")
        self.speed_value.setFixedWidth(38)
        self.speed_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        speed_row.addWidget(self.speed_value)
        layout.addLayout(speed_row)
        self.speed_slider.valueChanged.connect(self._on_speed_change)

        layout.addSpacing(18)

        # --------------------------------------------------- manual pad
        layout.addWidget(
            self._section_header("手动转动", "上排顺时针 · 下排逆时针")
        )
        layout.addSpacing(9)

        pad = QGridLayout()
        pad.setContentsMargins(0, 0, 0, 0)
        pad.setHorizontalSpacing(6)
        pad.setVerticalSpacing(6)
        self.turn_buttons: list[QPushButton] = []
        for column, face in enumerate(FACE_ORDER):
            pad.setColumnStretch(column, 1)
            for row, amount in enumerate((1, -1)):
                label = face if amount == 1 else face + "′"
                button = self._button(label, "turn", height=31)
                button.setProperty("face", face)
                button.setToolTip(
                    f"{face}（{FACE_NAMES_ZH[face]}面）"
                    + ("顺时针" if amount == 1 else "逆时针")
                    + "转 90°"
                )
                button.clicked.connect(
                    lambda checked=False, f=face, a=amount: self._manual_turn(f, a)
                )
                pad.addWidget(button, row, column)
                self.turn_buttons.append(button)
        layout.addLayout(pad)

        layout.addStretch(1)

        # ------------------------------------------------------ footer
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(12)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(36)
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.status_label)

        layout.addSpacing(4)
        shortcuts = QLabel("空格 播放 · ← → 单步 · R 随机")
        shortcuts.setObjectName("shortcuts")
        layout.addWidget(shortcuts)

        self._set_status("准备就绪", "muted")

    def _section_header(self, title_text: str, hint_text: str) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("section")
        row.addWidget(title)
        row.addStretch(1)
        hint = QLabel(hint_text)
        hint.setObjectName("hint")
        row.addWidget(hint)
        return holder

    def _button(
        self,
        text: str,
        role: str,
        height: int,
        width: int | None = None,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("role", role)
        button.setFixedHeight(height)
        if width is not None:
            button.setFixedWidth(width)
        else:
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    # ============================================================== status
    def _set_status(self, text: str, tone: str = "muted") -> None:
        colors = {
            "muted": (theme.TEXT_MUTED, theme.TEXT_DIM),
            "accent": ("#CFE2FF", theme.ACCENT),
            "success": ("#A9EDCB", theme.GREEN),
            "error": ("#FFB0B7", theme.RED),
        }
        text_color, dot_color = colors.get(tone, colors["muted"])
        self.status_label.setText(
            f'<span style="color:{dot_color}; font-weight:600;">●</span>'
            f'&nbsp;&nbsp;<span style="color:{text_color};">{html.escape(text)}</span>'
        )

    def _set_entry_error(self, is_error: bool) -> None:
        value = "true" if is_error else "false"
        if self.entry.property("error") == value:
            return
        self.entry.setProperty("error", value)
        self.entry.style().unpolish(self.entry)
        self.entry.style().polish(self.entry)
        self.entry.update()

    def _clear_entry_error(self) -> None:
        self._set_entry_error(False)

    # ================================================================ plan
    def _generate_plan(self) -> str | None:
        """Solve the current state with the selected method.

        Used after scrambles, method changes and manual turns; the sticker
        editor obtains its plan from the same solver before applying.
        Returns an error message instead of raising when no plan can be
        produced.
        """
        self.plan_index = 0
        self.plan = []
        self.solution = None
        try:
            solution = solve_with_method(self.method_id, self.cube)
        except Exception as exc:  # defensive UI boundary around the solver
            return str(exc) or type(exc).__name__
        self._install_solution(solution)
        return None

    def _install_solution(self, solution: Solution) -> None:
        self.solution = solution
        self.plan = solution.moves
        self.plan_index = 0

    def _current_stage(self) -> tuple[int, StagePlan] | None:
        """Return the stage containing the next pending move."""
        if self.solution is None or not self.solution.stages:
            return None
        position = 0
        last: tuple[int, StagePlan] | None = None
        for index, stage in enumerate(self.solution.stages):
            position += stage.move_count
            last = (index, stage)
            if self.plan_index < position:
                return index, stage
        return last

    def _update_stage_label(self) -> None:
        if self.scrambling:
            self.stage_label.setText("正在打乱")
            self.stage_label.setToolTip("")
            return
        if not self.plan:
            self.stage_label.setText(
                "已复原" if self.cube.is_solved() else "暂无步骤"
            )
            self.stage_label.setToolTip("")
            return
        if self.cube.is_solved() and self.plan_index >= len(self.plan):
            self.stage_label.setText("已复原")
            self.stage_label.setToolTip("")
            return
        current = self._current_stage()
        if current is None:
            self.stage_label.setText("")
            self.stage_label.setToolTip("")
            return
        index, stage = current
        total = len(self.solution.stages) if self.solution else 1
        self.stage_label.setText(f"{stage.name} · {index + 1}/{total}")
        self.stage_label.setToolTip(stage.detail)

    def _sync_method_combo(self) -> None:
        index = self.method_combo.findData(self.method_id)
        if index < 0 or index == self.method_combo.currentIndex():
            return
        self.method_combo.blockSignals(True)
        try:
            self.method_combo.setCurrentIndex(index)
        finally:
            self.method_combo.blockSignals(False)

    def _method_title(self) -> str:
        return method_by_id(self.method_id).title

    def _strip_empty_hint(self) -> str:
        if self.scrambling:
            return "正在应用打乱…"
        if self.cube.is_solved():
            return "魔方已复原 · 应用打乱开始新一局"
        if not self.plan:
            return "暂无复原步骤"
        return "应用打乱后，这里会显示复原步骤"

    def _refresh_ui(self) -> None:
        self.move_strip.set_plan(
            self.plan, self.plan_index, self._strip_empty_hint()
        )
        if self.scrambling:
            self.progress_label.setText("打乱中")
        else:
            n = len(self.plan)
            self.progress_label.setText(f"{self.plan_index} / {n}")

        if self.scrambling:
            self.cube_view.set_badge("打乱中", theme.ACCENT)
        elif self.cube.is_solved():
            self.cube_view.set_badge("已复原", theme.GREEN)
        else:
            self.cube_view.set_badge("打乱状态", theme.AMBER)

        self._update_stage_label()
        self._sync_controls()

    def _sync_controls(self) -> None:
        busy = self.anim is not None or self.scrambling
        idle = not busy and not self.playing
        plan_remaining = self.plan_index < len(self.plan)
        plan_started = self.plan_index > 0

        self.apply_button.setEnabled(not busy and not self.playing)
        self.random_button.setEnabled(not busy and not self.playing)
        self.method_combo.setEnabled(idle)
        self.sticker_button.setEnabled(idle)
        self.reset_button.setEnabled(True)
        self.prev_button.setEnabled(idle and plan_started)
        self.next_button.setEnabled(idle and plan_remaining)
        self.play_button.setEnabled(
            not self.scrambling
            and (self.playing or (self.anim is None and plan_remaining))
        )
        self.play_button.setText("暂停" if self.playing else "播放")
        for button in self.turn_buttons:
            button.setEnabled(idle)

    # ============================================================ playback
    def _ensure_timer(self) -> None:
        if not self.timer.isActive():
            self.timer.start()

    def _stop_timer_if_idle(self) -> None:
        if (
            self.anim is None
            and not self.playing
            and not self.scrambling
            and self.celebration is None
        ):
            self.timer.stop()

    def _on_tick(self) -> None:
        now = time.perf_counter()

        if self.anim is not None:
            anim = self.anim
            t = (now - anim["start"]) / anim["duration"]
            if t >= 1.0:
                self._finish_animation(anim)
            else:
                eased = t * t * (3.0 - 2.0 * t)
                self.cube_view.set_anim(
                    anim["axis"], anim["layer"], anim["angle"] * eased
                )
        elif self.celebration is not None:
            celebration = self.celebration
            t = min(
                1.0,
                (now - celebration["start"]) / celebration["duration"],
            )
            eased = t * t * (3.0 - 2.0 * t)
            self.cube_view.yaw = celebration["yaw0"] + 360.0 * eased
            self.cube_view.update()
            if t >= 1.0:
                self.cube_view.yaw = celebration["yaw0"] % 360.0
                self.celebration = None
        elif self.playing:
            if self.plan_index >= len(self.plan):
                self.playing = False
                self._sync_controls()
            elif now >= self.next_play_at:
                self._begin_animation(
                    self.plan[self.plan_index], "forward"
                )
                self._set_status(
                    f"播放中 · 已完成 {self.plan_index} / {len(self.plan)} 步",
                    "accent",
                )
                self._refresh_ui()

        self._stop_timer_if_idle()

    def _begin_animation(self, move: Move, context: str) -> None:
        axis, layer, base = MOVE_DEFS[move.face]
        if context == "scramble":
            duration = 0.07
        elif context in ("back", "manual"):
            duration = 0.23 / self.speed
        else:
            duration = 0.29 / self.speed
        if move.amount == 2:
            duration *= 1.7

        self.anim = {
            "move": move,
            "context": context,
            "axis": axis,
            "layer": layer,
            "angle": base * move.amount * 90.0,
            "start": time.perf_counter(),
            "duration": max(0.03, duration),
        }
        self.cube_view.set_anim(axis, layer, 0.0)
        self._ensure_timer()
        self._sync_controls()

    def _finish_animation(self, anim: dict) -> None:
        self.anim = None
        self.cube_view.clear_anim()
        move: Move = anim["move"]
        context: str = anim["context"]
        self.cube.apply_move(move)
        now = time.perf_counter()

        if context == "scramble":
            self._start_next_scramble_move()
            self.cube_view.update()
            self._stop_timer_if_idle()
            return

        if context == "forward":
            self.plan_index += 1
            if self.plan_index >= len(self.plan):
                self.playing = False
                self._on_plan_finished()
            elif self.playing:
                self.next_play_at = now + 0.10 / self.speed
                self._set_status(
                    f"播放中 · 已完成 {self.plan_index} / {len(self.plan)} 步",
                    "accent",
                )
            else:
                self._set_status(
                    f"第 {self.plan_index} / {len(self.plan)} 步 · 已执行 {move.pretty}",
                    "accent",
                )
        elif context == "back":
            self.plan_index = max(0, self.plan_index - 1)
            self._set_status(
                f"已回退 · {self.plan_index} / {len(self.plan)} 步", "muted"
            )
        elif context == "manual":
            self._replan_after_manual_turn(move)

        self._refresh_ui()
        self._stop_timer_if_idle()

    def _on_plan_finished(self) -> None:
        if self.cube.is_solved():
            self._set_status(
                f"复原完成 · {self._method_title()} · 共 "
                f"{len(self.plan)} 步",
                "success",
            )
            self._start_celebration()
        else:
            self._set_status(
                "步骤已执行完，但魔方尚未复原", "error"
            )

    def _start_celebration(self) -> None:
        self.celebration = {
            "start": time.perf_counter(),
            "duration": 1.35,
            "yaw0": self.cube_view.yaw,
        }
        self._ensure_timer()

    def _cancel_celebration(self) -> None:
        if self.celebration is not None:
            self.celebration = None
            self.cube_view.update()
            self._stop_timer_if_idle()

    # ============================================================ actions
    def _on_apply(self) -> None:
        self.load_scramble(self.entry.text(), animate=True)

    def _on_random(self) -> None:
        moves = random_scramble(20)
        text = format_moves(moves)
        self.entry.setText(text)
        self.load_scramble(text, animate=True)

    def _on_method_changed(self, index: int) -> None:
        method_id = self.method_combo.itemData(index)
        if not method_id or method_id == self.method_id:
            return
        if self.anim is not None or self.scrambling or self.playing:
            self._sync_method_combo()
            return

        self.method_id = method_id
        self._cancel_celebration()
        error = self._generate_plan()
        title = self._method_title()
        if error is not None:
            self._set_status(f"切换为{title}失败：{error}", "error")
        elif self.cube.is_solved():
            self._set_status(
                f"已切换为{title} · 当前为复原状态", "success"
            )
        elif not self.plan:
            self._set_status(
                f"已切换为{title} · 未能生成复原方案", "error"
            )
        else:
            stage_count = len(self.solution.stages) if self.solution else 0
            self._set_status(
                f"已切换为{title} · 复原方案共 {len(self.plan)} 步"
                f"（{stage_count} 阶段）",
                "accent",
            )
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_reset(self) -> None:
        self._hard_stop()
        self.cube = Cube()
        self.cube_view.set_cube(self.cube)
        self.plan = []
        self.plan_index = 0
        self.solution = None
        self._set_status("已重置为复原状态", "muted")
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_speed_change(self, value: int) -> None:
        self.speed = value / 10.0
        self.speed_value.setText(f"{self.speed:.1f}×")

    def _step_forward(self) -> None:
        if self.anim is not None or self.scrambling or self.playing:
            return
        if self.plan_index >= len(self.plan):
            return
        self._cancel_celebration()
        move = self.plan[self.plan_index]
        self._set_status(f"正在执行 {move.pretty} …", "accent")
        self._begin_animation(move, "forward")
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _step_back(self) -> None:
        if self.anim is not None or self.scrambling or self.playing:
            return
        if self.plan_index <= 0:
            return
        self._cancel_celebration()
        move = self.plan[self.plan_index - 1].inverse
        self._set_status(f"回退 {move.pretty} …", "muted")
        self._begin_animation(move, "back")
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _toggle_play(self) -> None:
        if self.scrambling:
            return
        if self.playing:
            self.playing = False
            self._set_status(
                f"已暂停 · 已完成 {self.plan_index} / {len(self.plan)} 步",
                "muted",
            )
            self._sync_controls()
            self._stop_timer_if_idle()
            self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        if self.anim is not None:
            return
        if self.plan_index >= len(self.plan):
            return

        self._cancel_celebration()
        self.playing = True
        self.next_play_at = time.perf_counter() + 0.045
        self._set_status(
            f"播放中 · 共 {len(self.plan)} 步", "accent"
        )
        self._ensure_timer()
        self._sync_controls()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _manual_turn(self, face: str, amount: int) -> None:
        if self.anim is not None or self.scrambling or self.playing:
            return
        self._cancel_celebration()
        move = Move(face, amount)
        self._set_status(f"手动转动 {move.pretty} …", "accent")
        self._begin_animation(move, "manual")
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _replan_after_manual_turn(self, move: Move) -> None:
        """Re-solve with the selected method after a manual turn."""
        error = self._generate_plan()
        if error is not None:
            self._set_status(
                f"手动转动 {move.pretty} · 无法生成复原方案：{error}",
                "error",
            )
            return
        if self.cube.is_solved():
            self._set_status(
                f"手动转动 {move.pretty} · 魔方已复原", "success"
            )
            self._start_celebration()
            return
        if not self.plan:
            self._set_status(
                f"手动转动 {move.pretty} · 未能生成复原方案", "error"
            )
            return
        stage_count = len(self.solution.stages) if self.solution else 0
        self._set_status(
            f"手动转动 {move.pretty} · {self._method_title()}方案已更新"
            f"（{len(self.plan)} 步 · {stage_count} 阶段）",
            "muted",
        )

    def apply_custom_state(self, cube: Cube, solution: Solution) -> None:
        """Replace the current state with an edited sticker layout."""
        self._hard_stop()
        self.cube = cube
        self.method_id = solution.method.id
        self._sync_method_combo()
        self._install_solution(solution)
        self.entry.clear()
        self.entry.setCursorPosition(0)
        self._set_entry_error(False)
        self.cube_view.set_cube(self.cube)

        n = len(self.plan)
        title = solution.method.title
        if self.cube.is_solved():
            self._set_status(
                "已应用自定义色块 · 当前为复原状态", "success"
            )
        elif n:
            self._set_status(
                f"已应用自定义色块 · {title}方案共 {n} 步"
                f"（{solution.stage_count} 阶段）",
                "accent",
            )
        else:
            self._set_status(
                "已应用自定义色块 · 没有可用的复原方案", "error"
            )
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _open_sticker_editor(self) -> None:
        if self.anim is not None or self.scrambling or self.playing:
            return
        self._cancel_celebration()
        try:
            facelets = cube_to_facelets(self.cube)
        except ValueError as exc:
            self._set_status(f"无法读取当前色块：{exc}", "error")
            return

        dialog = StickerEditorDialog(
            facelets, self, method_id=self.method_id
        )
        dialog.resize(600, 720)
        center = self.frameGeometry().center()
        dialog.move(
            center.x() - dialog.width() // 2,
            center.y() - dialog.height() // 2 - 14,
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        cube = dialog.result_cube
        solution = dialog.result_solution
        dialog.deleteLater()
        if accepted and cube is not None and solution is not None:
            self.apply_custom_state(cube, solution)
        else:
            self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_view_interaction(self) -> None:
        self._cancel_celebration()

    # ============================================================ scramble
    def _hard_stop(self) -> None:
        self.timer.stop()
        self.anim = None
        self.scramble_queue.clear()
        self.scrambling = False
        self.playing = False
        self.celebration = None
        self.cube_view.clear_anim()

    def _start_next_scramble_move(self) -> None:
        if not self.scramble_queue:
            self.scrambling = False
            error = self._generate_plan()
            if error is not None:
                self._set_status(
                    f"打乱完成 · 无法生成复原方案：{error}", "error"
                )
            elif self.plan:
                stage_count = (
                    len(self.solution.stages) if self.solution else 0
                )
                self._set_status(
                    f"打乱完成 · {self._method_title()}方案共 "
                    f"{len(self.plan)} 步（{stage_count} 阶段）",
                    "accent",
                )
            else:
                self._set_status(
                    "这个打乱组合等同于已复原", "muted"
                )
            self._refresh_ui()
            return

        move = self.scramble_queue.popleft()
        self._begin_animation(move, "scramble")
        self.cube_view.update()

    def load_scramble(self, text: str, animate: bool = False) -> bool:
        try:
            moves = parse_moves(text)
        except ValueError as exc:
            self._set_entry_error(True)
            self._set_status(f"公式有误：{exc}", "error")
            self._refresh_ui()
            return False

        self._set_entry_error(False)
        self._hard_stop()
        self.cube = Cube()
        self.cube_view.set_cube(self.cube)
        self.plan = []
        self.plan_index = 0
        self.solution = None
        self.entry.setText(text)
        self.entry.setCursorPosition(0)

        if animate and len(moves) <= MAX_ANIMATED_SCRAMBLE:
            self.scrambling = True
            self.scramble_queue = deque(moves)
            self._set_status("正在打乱…", "accent")
            self._refresh_ui()
            self._start_next_scramble_move()
            self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)
            return True

        self.cube.apply_moves(moves)
        error = self._generate_plan()
        if error is not None:
            self._set_status(f"无法生成复原方案：{error}", "error")
        elif self.plan:
            stage_count = len(self.solution.stages) if self.solution else 0
            self._set_status(
                f"已设置打乱 · {self._method_title()}方案共 "
                f"{len(self.plan)} 步（{stage_count} 阶段）",
                "accent",
            )
        else:
            self._set_status("这个打乱组合等同于已复原", "muted")
        self._refresh_ui()
        self.cube_view.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    # ============================================================= preview
    def advance_plan_instantly(self, steps: int) -> None:
        """Advance the plan without animation (used by tests/snapshots)."""
        if self.anim is not None or self.scrambling:
            return
        steps = max(0, min(steps, len(self.plan) - self.plan_index))
        for _ in range(steps):
            move = self.plan[self.plan_index]
            self.cube.apply_move(move)
            self.plan_index += 1
        if steps:
            if self.plan_index >= len(self.plan):
                self.playing = False
                self._on_plan_finished()
            else:
                self._set_status(
                    f"第 {self.plan_index} / {len(self.plan)} 步", "accent"
                )
        self._refresh_ui()
        self.cube_view.update()

    # ============================================================ keyboard
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._toggle_play()
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self._step_forward()
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self._step_back()
            event.accept()
            return
        if key == Qt.Key.Key_R:
            self._on_random()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        super().closeEvent(event)
