from __future__ import annotations

import random
import unittest

from rubik.model import (
    Cube,
    Move,
    format_moves,
    invert_sequence,
    local_to_world,
    parse_moves,
    random_scramble,
    simplify,
)


def cubie_at(cube: Cube, pos):
    for cubie in cube.cubies:
        if cubie.pos == pos:
            return cubie
    raise AssertionError(f"no cubie at {pos}")


class ParseTests(unittest.TestCase):
    def test_spaces_and_primes(self):
        self.assertEqual(
            format_moves(parse_moves("R U R' U2 F")),
            "R U R' U2 F",
        )

    def test_compact_notation(self):
        self.assertEqual(
            format_moves(parse_moves("RUR'U2F")),
            "R U R' U2 F",
        )

    def test_typographic_prime_and_lowercase(self):
        self.assertEqual(
            format_moves(parse_moves("r u’ r′ u2")),
            "R U' R' U2",
        )

    def test_commas_and_chinese_comma(self):
        self.assertEqual(
            format_moves(parse_moves("R,U，F2")),
            "R U F2",
        )

    def test_empty_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_moves("   ")

    def test_garbage_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_moves("R X U")
        with self.assertRaises(ValueError):
            parse_moves("R3")

    def test_amount_normalisation(self):
        self.assertEqual(Move("u", 5).token, "U")
        self.assertEqual(Move("R", -1).token, "R'")
        self.assertEqual(Move("F", -2).token, "F2")
        with self.assertRaises(ValueError):
            Move("U", 4)


class SimplifyTests(unittest.TestCase):
    def test_adjacent_cancel(self):
        self.assertEqual(simplify(parse_moves("U U' R")), parse_moves("R"))

    def test_double_turn_creation(self):
        self.assertEqual(simplify(parse_moves("U U")), parse_moves("U2"))
        self.assertEqual(simplify(parse_moves("U2 U")), parse_moves("U'"))

    def test_cascade(self):
        self.assertEqual(simplify(parse_moves("R U U' R'")), [])

    def test_four_turns_vanish(self):
        self.assertEqual(simplify(parse_moves("F F F F")), [])
        self.assertEqual(simplify(parse_moves("F2 F2")), [])

    def test_inverse_of_random_is_solved(self):
        rng = random.Random(7)
        for _ in range(30):
            scramble = random_scramble(25, rng)
            cube = Cube()
            cube.apply_moves(scramble)
            cube.apply_moves(invert_sequence(scramble))
            self.assertTrue(cube.is_solved())


class CubeTests(unittest.TestCase):
    def test_initial_state(self):
        cube = Cube()
        self.assertEqual(len(cube.cubies), 26)
        self.assertEqual(sum(len(c.stickers) for c in cube.cubies), 54)
        self.assertTrue(cube.is_solved())

    def test_u_four_times(self):
        cube = Cube()
        for _ in range(4):
            cube.apply_move(Move("U"))
        self.assertTrue(cube.is_solved())

    def test_u_cycles_front_to_left(self):
        cube = Cube()
        cube.apply_move(Move("U"))
        moved = cubie_at(cube, (-1, 1, 0))
        faces = {
            local_to_world(moved.orient, normal): code
            for normal, code in moved.stickers
        }
        self.assertEqual(faces[(0, 1, 0)], "U")
        self.assertEqual(faces[(-1, 0, 0)], "F")

    def test_f_cycles_up_to_right(self):
        cube = Cube()
        cube.apply_move(Move("F"))
        moved = cubie_at(cube, (1, 0, 1))
        faces = {
            local_to_world(moved.orient, normal): code
            for normal, code in moved.stickers
        }
        self.assertEqual(faces[(1, 0, 0)], "U")
        self.assertEqual(faces[(0, 0, 1)], "F")

    def test_layer_membership(self):
        cube = Cube()
        before_top = {c.pos for c in cube.cubies if c.pos[1] == 1}
        cube.apply_move(Move("R"))
        after_top = {c.pos for c in cube.cubies if c.pos[1] == 1}
        self.assertEqual(before_top, after_top)
        # R only changes the right layer's orientation/pos within x == 1.
        self.assertTrue(all(c.pos[0] in (-1, 0, 1) for c in cube.cubies))

    def test_random_moves_keep_cube_valid(self):
        rng = random.Random(42)
        for _ in range(20):
            cube = Cube()
            cube.apply_moves(random_scramble(30, rng))
            positions = set()
            for cubie in cube.cubies:
                self.assertNotEqual(cubie.pos, (0, 0, 0))
                self.assertNotIn(cubie.pos, positions)
                positions.add(cubie.pos)
                self.assertTrue(all(coord in (-1, 0, 1) for coord in cubie.pos))
                # Orientation rows stay orthonormal axis directions.
                for row in cubie.orient:
                    self.assertEqual(sorted(abs(v) for v in row), [0, 0, 1])
                # Every sticker normal stays axis aligned.
                for normal, _ in cubie.stickers:
                    world = local_to_world(cubie.orient, normal)
                    self.assertEqual(sorted(abs(v) for v in world), [0, 0, 1])
            self.assertFalse(cube.is_solved() or len(positions) != 26)

    def test_scramble_generator_avoids_repeats(self):
        rng = random.Random(1)
        moves = random_scramble(50, rng)
        for a, b in zip(moves, moves[1:]):
            self.assertNotEqual(a.face, b.face)


if __name__ == "__main__":
    unittest.main()
