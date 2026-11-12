"""Tests for the four human-style restoration methods."""

from __future__ import annotations

import random
import unittest

from rubik.facelets import cube_from_facelets, cube_to_facelets, solved_facelets
from rubik.methods import (
    METHODS,
    METHOD_BY_ID,
    solve_facelets_with_method,
    solve_with_method,
    stage_goal_met,
)
from rubik.model import Cube, random_scramble
from rubik.solver import SolverError


HUMAN_METHODS = ("lbl", "cfop", "roux", "zz")
EXPECTED_STAGE_COUNTS = {"lbl": 7, "cfop": 7, "roux": 4, "zz": 7}


def _copy(cube: Cube) -> Cube:
    return cube_from_facelets(cube_to_facelets(cube))


class MethodDefinitionTests(unittest.TestCase):
    def test_all_methods_are_selectable(self) -> None:
        self.assertEqual(
            [method.id for method in METHODS],
            ["kociemba", "lbl", "cfop", "roux", "zz"],
        )
        for method in METHODS:
            self.assertTrue(method.label)
            self.assertTrue(method.title)
            self.assertTrue(method.description)

    def test_human_stage_counts(self) -> None:
        for method_id, expected in EXPECTED_STAGE_COUNTS.items():
            method = METHOD_BY_ID[method_id]
            self.assertTrue(method.is_human)
            self.assertEqual(len(method.stages), expected)
            self.assertTrue(all(stage.name for stage in method.stages))
            self.assertTrue(all(stage.detail for stage in method.stages))


class HumanMethodSolveTests(unittest.TestCase):
    def test_each_method_solves_and_reaches_every_stage_goal(self) -> None:
        rng = random.Random(2718)
        for method_id in HUMAN_METHODS:
            for trial in range(3):
                with self.subTest(method=method_id, trial=trial):
                    cube = Cube()
                    cube.apply_moves(random_scramble(20, rng))
                    solution = solve_with_method(method_id, cube)

                    self.assertEqual(solution.method.id, method_id)
                    self.assertEqual(
                        len(solution.stages),
                        EXPECTED_STAGE_COUNTS[method_id],
                    )
                    self.assertTrue(solution.moves)

                    replay = _copy(cube)
                    for index, stage in enumerate(solution.stages):
                        replay.apply_moves(stage.moves)
                        self.assertTrue(
                            stage_goal_met(replay, method_id, index),
                            f"stage {index} ({stage.name}) not reached",
                        )
                    self.assertTrue(replay.is_solved())
                    self.assertEqual(
                        solution.move_count,
                        sum(len(stage.moves) for stage in solution.stages),
                    )

    def test_stage_prefixes_are_ordered(self) -> None:
        cube = Cube()
        cube.apply_moves(random_scramble(20, random.Random(11)))
        solution = solve_with_method("lbl", cube)
        prefix = _copy(cube)
        # The first stage solves the bottom cross, not the whole cube.
        prefix.apply_moves(solution.stages[0].moves)
        self.assertFalse(prefix.is_solved())
        self.assertTrue(stage_goal_met(prefix, "lbl", 0))
        self.assertFalse(stage_goal_met(prefix, "lbl", 1))

    def test_methods_build_different_stage_plans(self) -> None:
        cube = Cube()
        cube.apply_moves(random_scramble(20, random.Random(31)))
        lbl = solve_with_method("lbl", cube)
        roux = solve_with_method("roux", cube)
        self.assertNotEqual(
            [stage.name for stage in lbl.stages],
            [stage.name for stage in roux.stages],
        )
        self.assertNotEqual(lbl.move_count, 0)
        self.assertNotEqual(roux.move_count, 0)

    def test_solved_cube_has_no_stages(self) -> None:
        for method_id in HUMAN_METHODS:
            solution = solve_with_method(method_id, Cube())
            self.assertEqual(solution.stages, ())
            self.assertEqual(solution.moves, [])

    def test_methods_handle_permuted_colour_scheme(self) -> None:
        source = Cube()
        source.apply_moves(random_scramble(18, random.Random(7)))
        facelets = cube_to_facelets(source)
        permutation = dict(zip("URFDLB", "DLBURF"))
        permuted = {
            face: [permutation[color] for color in cells]
            for face, cells in facelets.items()
        }
        for method_id in HUMAN_METHODS:
            with self.subTest(method=method_id):
                cube, solution = solve_facelets_with_method(
                    permuted, method_id
                )
                cube.apply_moves(solution.moves)
                self.assertTrue(cube.is_solved())

    def test_invalid_facelets_are_rejected(self) -> None:
        facelets = solved_facelets()
        facelets["U"][0] = "D"
        with self.assertRaisesRegex(SolverError, "9"):
            solve_facelets_with_method(facelets, "lbl")

    def test_impossible_state_is_rejected(self) -> None:
        facelets = solved_facelets()
        facelets["U"][7], facelets["F"][1] = (
            facelets["F"][1],
            facelets["U"][7],
        )
        with self.assertRaises(SolverError):
            solve_facelets_with_method(facelets, "cfop")


class KociembaMethodTests(unittest.TestCase):
    def test_kociemba_is_one_stage(self) -> None:
        cube = Cube()
        cube.apply_moves(random_scramble(20, random.Random(99)))
        solution = solve_with_method("kociemba", cube)
        self.assertEqual(solution.method.id, "kociemba")
        self.assertEqual(len(solution.stages), 1)
        self.assertEqual(solution.stages[0].name, "两阶段求解")
        cube.apply_moves(solution.moves)
        self.assertTrue(cube.is_solved())

    def test_unknown_method_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            solve_with_method("unknown", Cube())


if __name__ == "__main__":
    unittest.main()
