"""UI state-machine tests. They use Qt's offscreen platform."""

from __future__ import annotations

import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from rubik.facelets import cube_to_facelets, solved_facelets  # noqa: E402
from rubik.methods import (  # noqa: E402
    solve_facelets_with_method,
    solve_with_method,
)
from rubik.model import Cube, parse_moves  # noqa: E402
from rubik.sticker_dialog import StickerEditorDialog  # noqa: E402
from rubik.window import MainWindow  # noqa: E402


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.timer.stop()
        self.window._cancel_celebration()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    # ---------------------------------------------------------------- basics
    def test_initial_demo_state(self) -> None:
        window = self.window
        self.assertFalse(window.cube.is_solved())
        self.assertTrue(window.plan)
        self.assertEqual(window.plan_index, 0)
        self.assertEqual(
            window.progress_label.text(), f"0 / {len(window.plan)}"
        )
        self.assertTrue(window.next_button.isEnabled())
        self.assertFalse(window.prev_button.isEnabled())
        self.assertTrue(window.sticker_button.isEnabled())
        self.assertEqual(window.play_button.text(), "播放")
        self.assertEqual(window.method_id, "kociemba")
        self.assertEqual(window.method_combo.currentData(), "kociemba")
        self.assertIn("两阶段", window.stage_label.text())

    def test_advancing_all_steps_solves_cube(self) -> None:
        window = self.window
        total = len(window.plan)
        window.advance_plan_instantly(total)
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())
        self.assertEqual(window.plan_index, total)
        self.assertEqual(window.progress_label.text(), f"{total} / {total}")
        self.assertIn("复原完成", window.status_label.text())
        self.assertEqual(window.stage_label.text(), "已复原")
        self.assertFalse(window.next_button.isEnabled())
        self.assertTrue(window.prev_button.isEnabled())
        self.assertFalse(window.play_button.isEnabled())

    def test_reset_clears_plan(self) -> None:
        window = self.window
        window.advance_plan_instantly(3)
        window._on_reset()
        self.assertTrue(window.cube.is_solved())
        self.assertEqual(window.plan, [])
        self.assertEqual(window.plan_index, 0)
        self.assertEqual(window.progress_label.text(), "0 / 0")
        self.assertIn("已重置", window.status_label.text())

    # --------------------------------------------------------------- errors
    def test_invalid_formula_keeps_current_state(self) -> None:
        window = self.window
        plan_before = list(window.plan)
        window.entry.setText("R2 X Q")
        window._on_apply()
        self.assertEqual(window.entry.property("error"), "true")
        self.assertIn("公式有误", window.status_label.text())
        self.assertEqual(window.plan, plan_before)
        self.assertFalse(window.cube.is_solved())

        window.entry.setText("R U")
        self.assertEqual(window.entry.property("error"), "false")

    def test_empty_formula_is_rejected(self) -> None:
        window = self.window
        window.entry.setText("   ")
        window._on_apply()
        self.assertEqual(window.entry.property("error"), "true")
        self.assertIn("公式有误", window.status_label.text())

    def test_identity_scramble_has_no_plan(self) -> None:
        window = self.window
        window.load_scramble("R L R' L'", animate=False)
        self.assertTrue(window.cube.is_solved())
        self.assertEqual(window.plan, [])
        self.assertEqual(window.progress_label.text(), "0 / 0")
        self.assertIn("等同于已复原", window.status_label.text())

    # ------------------------------------------------------------ methods
    def test_method_selector_generates_staged_solution(self) -> None:
        window = self.window
        window.load_scramble("R U F' D2 L", animate=False)
        index = window.method_combo.findData("lbl")
        window.method_combo.setCurrentIndex(index)

        self.assertEqual(window.method_id, "lbl")
        self.assertIsNotNone(window.solution)
        self.assertEqual(window.solution.method.id, "lbl")
        self.assertEqual(len(window.solution.stages), 7)
        self.assertTrue(window.plan)
        self.assertIn("阶段", window.status_label.text())
        self.assertRegex(window.stage_label.text(), r"\d+/\d+")

        window.advance_plan_instantly(len(window.plan))
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())
        self.assertIn("复原完成", window.status_label.text())
        self.assertIn("层先法", window.status_label.text())

    def test_method_change_keeps_current_cube_state(self) -> None:
        window = self.window
        window.load_scramble("R U", animate=False)
        window.advance_plan_instantly(1)
        state = cube_to_facelets(window.cube)
        window.method_combo.setCurrentIndex(
            window.method_combo.findData("cfop")
        )
        self.assertEqual(window.method_id, "cfop")
        self.assertEqual(window.plan_index, 0)
        self.assertEqual(cube_to_facelets(window.cube), state)
        self.assertEqual(window.solution.method.id, "cfop")
        self.assertTrue(window.plan)

    # ------------------------------------------------------------ animation
    def test_animated_scramble_then_solver_plan(self) -> None:
        window = self.window
        self.assertTrue(window.load_scramble("R U", animate=True))
        self.assertTrue(window.scrambling)
        QTest.qWait(600)
        self.assertFalse(window.scrambling)
        self.assertEqual([move.token for move in window.plan], ["U'", "R'"])
        self.assertIn("打乱完成", window.status_label.text())
        self.assertTrue(window.next_button.isEnabled())

    def test_single_step_uses_animation(self) -> None:
        window = self.window
        window.load_scramble("R U", animate=False)
        self.assertEqual([move.token for move in window.plan], ["U'", "R'"])
        window._on_speed_change(20)  # 2x speed for a fast test
        window._step_forward()
        self.assertIsNotNone(window.anim)
        QTest.qWait(320)
        self.assertIsNone(window.anim)
        self.assertEqual(window.plan_index, 1)
        self.assertEqual(window.progress_label.text(), "1 / 2")

    def test_manual_turn_regenerates_plan(self) -> None:
        window = self.window
        window._on_reset()
        window._on_speed_change(20)
        window._manual_turn("R", 1)
        QTest.qWait(320)
        self.assertFalse(window.cube.is_solved())
        self.assertEqual([move.token for move in window.plan], ["R'"])
        self.assertEqual(window.plan_index, 0)
        window.advance_plan_instantly(1)
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())

    def test_manual_turn_uses_selected_method(self) -> None:
        window = self.window
        window.load_scramble("R U", animate=False)
        window.method_combo.setCurrentIndex(
            window.method_combo.findData("roux")
        )
        self.assertEqual(window.method_id, "roux")
        window._on_speed_change(20)
        window._manual_turn("R", 1)
        QTest.qWait(320)

        self.assertIsNotNone(window.solution)
        self.assertEqual(window.solution.method.id, "roux")
        self.assertEqual(len(window.solution.stages), 4)
        self.assertIn("阶段", window.status_label.text())
        window.advance_plan_instantly(len(window.plan))
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())

    # ------------------------------------------------------- custom stickers
    def test_custom_state_has_a_solver_plan(self) -> None:
        window = self.window
        window._on_reset()
        source = Cube()
        source.apply_moves(parse_moves("R U F'"))
        cube, solution = solve_facelets_with_method(
            cube_to_facelets(source), "kociemba"
        )
        window.apply_custom_state(cube, solution)

        self.assertEqual(window.entry.text(), "")
        self.assertIn("自定义色块", window.status_label.text())
        self.assertTrue(window.plan)
        self.assertEqual(
            window.progress_label.text(), f"0 / {solution.move_count}"
        )

        window.advance_plan_instantly(len(window.plan))
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())

        window._on_reset()
        self.assertTrue(window.cube.is_solved())
        self.assertEqual(window.plan, [])

    def test_manual_turn_after_custom_state_replans_with_solver(self) -> None:
        window = self.window
        window._on_reset()
        empty = solve_with_method("kociemba", Cube())
        window.apply_custom_state(Cube(), empty)
        window._on_speed_change(20)
        window._manual_turn("R", 1)
        QTest.qWait(320)

        self.assertFalse(window.cube.is_solved())
        self.assertTrue(window.plan)
        window.advance_plan_instantly(len(window.plan))
        window._cancel_celebration()
        self.assertTrue(window.cube.is_solved())

        window.load_scramble("R", animate=False)
        self.assertEqual([move.token for move in window.plan], ["R'"])

    def test_sticker_dialog_validates_and_solves(self) -> None:
        window = self.window
        dialog = StickerEditorDialog(cube_to_facelets(window.cube), window)
        try:
            self.assertTrue(dialog._counts_ok)
            self.assertTrue(dialog._centers_ok)
            self.assertTrue(dialog.apply_button.isEnabled())
            for color in "UDLRFB":
                self.assertEqual(dialog.count_labels[color].text(), "9 / 9")

            dialog._apply()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertIsNotNone(dialog.result_cube)
            self.assertIsNotNone(dialog.result_solution)
            self.assertEqual(dialog.result_solution.method.id, "kociemba")
            dialog.result_cube.apply_moves(dialog.result_plan)
            self.assertTrue(dialog.result_cube.is_solved())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_sticker_dialog_uses_selected_method(self) -> None:
        window = self.window
        window.load_scramble("R U F'", animate=False)
        dialog = StickerEditorDialog(
            cube_to_facelets(window.cube), window, method_id="cfop"
        )
        try:
            dialog._apply()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertIsNotNone(dialog.result_solution)
            self.assertEqual(dialog.result_solution.method.id, "cfop")
            self.assertEqual(len(dialog.result_solution.stages), 7)
            self.assertTrue(dialog.result_plan)
            dialog.result_cube.apply_moves(dialog.result_plan)
            self.assertTrue(dialog.result_cube.is_solved())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_sticker_dialog_rejects_imbalanced_colours(self) -> None:
        dialog = StickerEditorDialog(solved_facelets(), self.window)
        try:
            dialog._select_color("D")
            dialog.canvas._paint_cell(("U", 0))
            self.assertFalse(dialog._counts_ok)
            self.assertFalse(dialog.apply_button.isEnabled())
            self.assertIn("需要恰好 9 块", dialog.validation_label.toolTip())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_automatic_playback_runs_to_the_end(self) -> None:
        window = self.window
        window.load_scramble("R U", animate=False)
        window._on_speed_change(20)
        window._toggle_play()
        self.assertTrue(window.playing)
        self.assertEqual(window.play_button.text(), "暂停")
        QTest.qWait(900)
        self.assertFalse(window.playing)
        self.assertTrue(window.cube.is_solved())
        self.assertEqual(window.plan_index, 2)
        self.assertIn("复原完成", window.status_label.text())


if __name__ == "__main__":
    unittest.main()
