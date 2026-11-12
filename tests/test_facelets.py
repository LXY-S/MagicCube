"""Facelet conversion tests."""

from __future__ import annotations

import random
import unittest

from rubik.facelets import (
    FACELET_FACES,
    cube_from_facelets,
    cube_to_facelets,
    solved_facelets,
)
from rubik.model import Cube, Move, parse_moves, random_scramble


class FaceletTests(unittest.TestCase):
    def test_solved_cube_facelets(self) -> None:
        self.assertEqual(cube_to_facelets(Cube()), solved_facelets())

    def test_u_turn_cycles_the_top_rows(self) -> None:
        cube = Cube()
        cube.apply_move(Move("U"))
        facelets = cube_to_facelets(cube)
        expected = {
            "U": ["U"] * 9,
            "R": ["B"] * 3 + ["R"] * 6,
            "F": ["R"] * 3 + ["F"] * 6,
            "D": ["D"] * 9,
            "L": ["F"] * 3 + ["L"] * 6,
            "B": ["L"] * 3 + ["B"] * 6,
        }
        self.assertEqual(facelets, expected)

    def test_roundtrip_after_random_scrambles(self) -> None:
        rng = random.Random(2024)
        for _ in range(8):
            cube = Cube()
            cube.apply_moves(random_scramble(25, rng))
            facelets = cube_to_facelets(cube)
            rebuilt = cube_from_facelets(facelets)
            self.assertEqual(cube_to_facelets(rebuilt), facelets)

            follow_up = random_scramble(5, rng)
            cube.apply_moves(follow_up)
            rebuilt.apply_moves(follow_up)
            self.assertEqual(
                cube_to_facelets(rebuilt), cube_to_facelets(cube)
            )

    def test_custom_colour_scheme_can_be_solved(self) -> None:
        colors = dict(zip("URFDLB", "DLBURF"))
        facelets = {
            face: [colors[face]] * 9 for face in FACELET_FACES
        }
        cube = cube_from_facelets(facelets)
        self.assertTrue(cube.is_solved())
        cube.apply_move(Move("R"))
        self.assertFalse(cube.is_solved())

    def test_single_changed_sticker_is_not_solved(self) -> None:
        facelets = solved_facelets()
        facelets["U"][0] = "D"
        cube = cube_from_facelets(facelets)
        self.assertFalse(cube.is_solved())

    def test_invalid_facelet_inputs(self) -> None:
        with self.assertRaises(ValueError):
            cube_from_facelets({"U": ["U"] * 9})
        with self.assertRaises(ValueError):
            cube_from_facelets({**solved_facelets(), "X": ["U"] * 9})
        with self.assertRaises(ValueError):
            cube_from_facelets({**solved_facelets(), "U": ["U"] * 8})
        bad = solved_facelets()
        bad["F"][3] = "Z"
        with self.assertRaises(ValueError):
            cube_from_facelets(bad)

    def test_rebuilt_cube_shares_move_semantics(self) -> None:
        source = Cube()
        source.apply_moves(parse_moves("R U2 F' L D2 B"))
        rebuilt = cube_from_facelets(cube_to_facelets(source))
        sequence = parse_moves("U R' F2 D L'")
        source.apply_moves(sequence)
        rebuilt.apply_moves(sequence)
        self.assertEqual(
            cube_to_facelets(rebuilt), cube_to_facelets(source)
        )


if __name__ == "__main__":
    unittest.main()
