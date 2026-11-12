"""Kociemba solver integration tests."""

from __future__ import annotations

import random
import unittest

from rubik.facelets import cube_to_facelets, solved_facelets
from rubik.model import Cube, random_scramble
from rubik.solver import SolverError, solve_cube, solve_facelets


class SolverTests(unittest.TestCase):
    def test_solved_cube_has_empty_plan(self) -> None:
        self.assertEqual(solve_cube(Cube()), [])

    def test_solves_random_scrambles(self) -> None:
        rng = random.Random(99)
        for index in range(5):
            with self.subTest(index=index):
                cube = Cube()
                cube.apply_moves(random_scramble(20, rng))
                self.assertFalse(cube.is_solved())
                plan = solve_cube(cube)
                self.assertTrue(plan)
                cube.apply_moves(plan)
                self.assertTrue(cube.is_solved())

    def test_solves_with_permuted_colour_scheme(self) -> None:
        source = Cube()
        source.apply_moves(random_scramble(18, random.Random(7)))
        facelets = cube_to_facelets(source)
        permutation = dict(zip("URFDLB", "DLBURF"))
        permuted = {
            face: [permutation[color] for color in cells]
            for face, cells in facelets.items()
        }
        cube, plan = solve_facelets(permuted)
        self.assertTrue(plan)
        cube.apply_moves(plan)
        self.assertTrue(cube.is_solved())
        solved = cube_to_facelets(cube)
        for face in solved:
            self.assertEqual(len(set(solved[face])), 1)

    def test_uniform_custom_scheme_has_empty_plan(self) -> None:
        permutation = dict(zip("URFDLB", "DLBURF"))
        facelets = {
            face: [permutation[face]] * 9 for face in "URFDLB"
        }
        cube, plan = solve_facelets(facelets)
        self.assertTrue(cube.is_solved())
        self.assertEqual(plan, [])

    def test_rejects_wrong_colour_counts(self) -> None:
        facelets = solved_facelets()
        facelets["U"][0] = "D"
        with self.assertRaisesRegex(SolverError, "9"):
            solve_facelets(facelets)

    def test_rejects_duplicate_centres(self) -> None:
        facelets = solved_facelets()
        facelets["F"][4] = "U"
        facelets["U"][0] = "F"
        with self.assertRaisesRegex(SolverError, "中心"):
            solve_facelets(facelets)

    def test_rejects_impossible_state(self) -> None:
        # Flipping a single edge leaves colour counts intact but cannot
        # be produced by legal cube turns.
        facelets = solved_facelets()
        facelets["U"][7], facelets["F"][1] = (
            facelets["F"][1],
            facelets["U"][7],
        )
        with self.assertRaises(SolverError):
            solve_facelets(facelets)


if __name__ == "__main__":
    unittest.main()
