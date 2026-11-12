"""Rubik's cube model, move parsing and solution-path helpers.

Coordinate system
-----------------
x: right, y: up, z: towards the viewer.

Every cubie stores an integer position on the {-1, 0, 1} grid and an
orientation matrix (three rows: the world directions of its local x/y/z
axes).  Stickers are stored in the cubie's local frame together with the
face code they belong to.  This keeps turns exact (no floating point in
the model) and makes it trivial to draw arbitrary intermediate states.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Sequence

FACE_ORDER: tuple[str, ...] = ("U", "D", "L", "R", "F", "B")
# Sticker colours use the same six codes as the faces.
COLOR_CODES: tuple[str, ...] = FACE_ORDER

FACE_NAMES_ZH: dict[str, str] = {
    "U": "上",
    "D": "下",
    "L": "左",
    "R": "右",
    "F": "前",
    "B": "后",
}

FACE_DIRS: dict[str, tuple[int, int, int]] = {
    "U": (0, 1, 0),
    "D": (0, -1, 0),
    "L": (-1, 0, 0),
    "R": (1, 0, 0),
    "F": (0, 0, 1),
    "B": (0, 0, -1),
}

# face -> (axis, layer coordinate, sign of one clockwise quarter turn)
MOVE_DEFS: dict[str, tuple[str, int, int]] = {
    "U": ("y", 1, -1),
    "D": ("y", -1, 1),
    "L": ("x", -1, 1),
    "R": ("x", 1, -1),
    "F": ("z", 1, -1),
    "B": ("z", -1, 1),
}

AXIS_INDEX: dict[str, int] = {"x": 0, "y": 1, "z": 2}
IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _normalise_amount(amount: int) -> int:
    """Return an equivalent amount of 1, -1 or 2 quarter turns."""
    amount %= 4
    if amount == 3:
        return -1
    return amount


@dataclass(frozen=True, slots=True)
class Move:
    """A single face turn: U, U' or U2 (amount 1, -1 or 2)."""

    face: str
    amount: int = 1

    def __post_init__(self) -> None:
        face = self.face.upper()
        if face not in FACE_ORDER:
            raise ValueError(f"未知的面：{self.face!r}")
        amount = _normalise_amount(int(self.amount))
        if amount == 0:
            raise ValueError("转动量不能为 0")
        object.__setattr__(self, "face", face)
        object.__setattr__(self, "amount", amount)

    @property
    def token(self) -> str:
        if self.amount == 1:
            return self.face
        if self.amount == -1:
            return self.face + "'"
        return self.face + "2"

    @property
    def pretty(self) -> str:
        if self.amount == 1:
            return self.face
        if self.amount == -1:
            return self.face + "′"
        return self.face + "2"

    @property
    def inverse(self) -> "Move":
        if self.amount == 2:
            return Move(self.face, 2)
        return Move(self.face, -self.amount)

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.token


def parse_moves(text: str) -> list[Move]:
    """Parse a Singmaster-style notation string.

    Whitespace and commas are optional separators, lowercase is accepted,
    and both ASCII and typographic primes are supported.
    """
    if not isinstance(text, str):
        raise ValueError("公式必须是文本")

    source = text.replace("’", "'").replace("′", "'").upper()
    moves: list[Move] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch.isspace() or ch in ",，":
            i += 1
            continue
        if ch not in FACE_ORDER:
            raise ValueError(f"无法识别的字符：{ch}")

        face = ch
        i += 1
        amount = 1
        if i < n and source[i] == "'":
            amount = -1
            i += 1
        elif i < n and source[i] == "2":
            amount = 2
            i += 1
            # Accept the harmless variant "R2'" as R2.
            if i < n and source[i] == "'":
                i += 1
        moves.append(Move(face, amount))

    if not moves:
        raise ValueError("请输入至少一步转动，例如 R U R'")
    return moves


def format_moves(moves: Iterable[Move]) -> str:
    return " ".join(move.token for move in moves)


def simplify(moves: Iterable[Move]) -> list[Move]:
    """Collapse adjacent turns of the same face (R R -> R2, U U' -> -)."""
    result: list[Move] = []
    for move in moves:
        amount = move.amount
        while result and result[-1].face == move.face:
            amount = _normalise_amount(result.pop().amount + amount)
            if amount == 0:
                break
        if amount != 0:
            result.append(Move(move.face, amount))
    return result


def invert_sequence(moves: Sequence[Move]) -> list[Move]:
    return [move.inverse for move in reversed(moves)]


def qrot(vector: tuple[int, int, int], axis: str, sign: int) -> tuple[int, int, int]:
    """Rotate an integer axis-aligned vector by ±90 degrees."""
    x, y, z = vector
    if axis == "x":
        return (x, -z, y) if sign > 0 else (x, z, -y)
    if axis == "y":
        return (z, y, -x) if sign > 0 else (-z, y, x)
    return (-y, x, z) if sign > 0 else (y, -x, z)


def local_to_world(
    orient: Sequence[Sequence[float]], vector: Sequence[float]
) -> tuple[float, float, float]:
    """Transform a direction from a cubie's local frame into world space."""
    vx, vy, vz = vector
    rx, ry, rz = orient
    return (
        vx * rx[0] + vy * ry[0] + vz * rz[0],
        vx * rx[1] + vy * ry[1] + vz * rz[1],
        vx * rx[2] + vy * ry[2] + vz * rz[2],
    )


class Cubie:
    __slots__ = ("pos", "orient", "stickers", "sticker_map")

    def __init__(
        self,
        pos: tuple[int, int, int],
        stickers: Sequence[tuple[tuple[int, int, int], str]],
    ) -> None:
        self.pos = pos
        self.orient: tuple[tuple[int, int, int], ...] = IDENTITY
        self.stickers = tuple(stickers)
        self.sticker_map = dict(stickers)

    def rotate_world(self, axis: str, sign: int) -> None:
        self.pos = qrot(self.pos, axis, sign)
        self.orient = tuple(qrot(row, axis, sign) for row in self.orient)  # type: ignore[arg-type]


class Cube:
    """A 3x3 cube made of 26 visible cubies (the core is omitted)."""

    def __init__(self) -> None:
        self.cubies: list[Cubie] = []
        for x in (-1, 0, 1):
            for y in (-1, 0, 1):
                for z in (-1, 0, 1):
                    pos = (x, y, z)
                    if pos == (0, 0, 0):
                        continue
                    stickers: list[tuple[tuple[int, int, int], str]] = []
                    for face, normal in FACE_DIRS.items():
                        if x * normal[0] + y * normal[1] + z * normal[2] == 1:
                            stickers.append((normal, face))
                    self.cubies.append(Cubie(pos, stickers))

    def apply_move(self, move: Move) -> None:
        axis, layer, base = MOVE_DEFS[move.face]
        index = AXIS_INDEX[axis]
        turns = 2 if move.amount == 2 else 1
        sign = base if move.amount != -1 else -base
        for cubie in self.cubies:
            if cubie.pos[index] != layer:
                continue
            for _ in range(turns):
                cubie.rotate_world(axis, sign)

    def apply_moves(self, moves: Iterable[Move]) -> None:
        for move in moves:
            self.apply_move(move)

    def is_solved(self) -> bool:
        """True when every visible face is a single uniform colour.

        The target colours are taken from the current centres rather than
        from the standard scheme, so a cube with custom sticker colours is
        solved as soon as each face is uniform.
        """
        counts: dict[tuple[float, float, float], int] = {}
        colors: dict[tuple[float, float, float], str] = {}
        for cubie in self.cubies:
            for local_normal, face_code in cubie.stickers:
                world = local_to_world(cubie.orient, local_normal)
                previous = colors.get(world)
                if previous is None:
                    colors[world] = face_code
                elif previous != face_code:
                    return False
                counts[world] = counts.get(world, 0) + 1
        if len(colors) != 6:
            return False
        return all(counts.get(normal, 0) == 9 for normal in FACE_DIRS.values())


def random_scramble(
    length: int = 20, rng: random.Random | None = None
) -> list[Move]:
    """Generate a random scramble without immediate repeat turns."""
    generator = rng or random
    moves: list[Move] = []
    previous = None
    for _ in range(length):
        faces = [face for face in FACE_ORDER if face != previous]
        face = generator.choice(faces)
        amount = generator.choices((1, -1, 2), weights=(0.44, 0.44, 0.12))[0]
        moves.append(Move(face, amount))
        previous = face
    return moves
