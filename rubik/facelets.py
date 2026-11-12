"""Conversions between the cubie model and the 54 visible facelets.

Facelets use the standard Kociemba order and orientation::

              U1 U2 U3
              U4 U5 U6
              U7 U8 U9
    L1 L2 L3  F1 F2 F3  R1 R2 R3  B1 B2 B3
    L4 L5 L6  F4 F5 F6  R4 R5 R6  B4 B5 B6
    L7 L8 L9  F7 F8 F9  R7 R8 R9  B7 B8 B9
              D1 D2 D3
              D4 D5 D6
              D7 D8 D9

A facelet value is one of the six colour codes ``U D L R F B``.  The
main cube normally uses those codes as the standard sticker colours;
a custom sticker state may use any permutation of them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .model import Cube, FACE_DIRS, COLOR_CODES, local_to_world

# Kociemba's face order; note that it differs from the UI's FACE_ORDER.
FACELET_FACES: tuple[str, ...] = ("U", "R", "F", "D", "L", "B")

# Where each face sits in the unfolded cross (column, row).
NET_LAYOUT: dict[str, tuple[int, int]] = {
    "U": (1, 0),
    "L": (0, 1),
    "F": (1, 1),
    "R": (2, 1),
    "B": (3, 1),
    "D": (1, 2),
}


def facelet_cell(face: str, row: int, col: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Return ``(position, world_normal)`` for one facelet cell."""
    if face not in FACE_DIRS:
        raise ValueError(f"未知的面：{face!r}")
    if not (0 <= row < 3 and 0 <= col < 3):
        raise ValueError("色块坐标越界")

    normal = FACE_DIRS[face]
    if face == "U":
        pos = (col - 1, 1, row - 1)
    elif face == "D":
        pos = (col - 1, -1, 1 - row)
    elif face == "F":
        pos = (col - 1, 1 - row, 1)
    elif face == "B":
        pos = (1 - col, 1 - row, -1)
    elif face == "R":
        pos = (1, 1 - row, 1 - col)
    else:  # L
        pos = (-1, 1 - row, col - 1)
    return pos, normal


def solved_facelets() -> dict[str, list[str]]:
    """The facelet colours of the standard solved cube."""
    return {face: [face] * 9 for face in FACELET_FACES}


def normalise_facelets(
    facelets: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    """Validate a facelet mapping and return a mutable, complete copy."""
    extra = set(facelets) - set(FACELET_FACES)
    if extra:
        raise ValueError(f"未知的面：{', '.join(sorted(extra))}")

    result: dict[str, list[str]] = {}
    for face in FACELET_FACES:
        values = list(facelets.get(face, ()))
        if len(values) != 9:
            raise ValueError(f"{face} 面需要 9 个色块")
        for color in values:
            if color not in COLOR_CODES:
                raise ValueError(f"未知颜色：{color!r}")
        result[face] = values
    return result


def cube_to_facelets(cube: Cube) -> dict[str, list[str]]:
    """Read the 54 visible sticker colours from any cube state."""
    by_pos = {cubie.pos: cubie for cubie in cube.cubies}
    facelets: dict[str, list[str]] = {}

    for face in FACELET_FACES:
        cells: list[str] = []
        for row in range(3):
            for col in range(3):
                pos, normal = facelet_cell(face, row, col)
                cubie = by_pos.get(pos)
                if cubie is None:
                    raise ValueError(f"魔方缺少位置 {pos} 的方块")
                color = None
                for local_normal, code in cubie.stickers:
                    if local_to_world(cubie.orient, local_normal) == normal:
                        color = code
                        break
                if color is None:
                    raise ValueError(f"{face} 面存在没有色块的位置")
                cells.append(color)
        facelets[face] = cells
    return facelets


def cube_from_facelets(facelets: Mapping[str, Sequence[str]]) -> Cube:
    """Build a cube whose visible stickers match ``facelets``.

    The result starts from the solved cubie layout with identity
    orientations; each visible sticker is then painted with the requested
    colour.  This is enough to render, turn and solve an arbitrary sticker
    arrangement.
    """
    colors = normalise_facelets(facelets)
    wanted: dict[tuple[int, int, int], dict[tuple[int, int, int], str]] = {}
    for face in FACELET_FACES:
        for index, color in enumerate(colors[face]):
            row, col = divmod(index, 3)
            pos, normal = facelet_cell(face, row, col)
            wanted.setdefault(pos, {})[normal] = color

    cube = Cube()
    for cubie in cube.cubies:
        requested = wanted.get(cubie.pos)
        if requested is None:
            raise ValueError(f"魔方缺少位置 {cubie.pos} 的色块")
        stickers: list[tuple[tuple[int, int, int], str]] = []
        for normal, _old_color in cubie.stickers:
            color = requested.get(normal)
            if color is None:
                raise ValueError(f"位置 {cubie.pos} 缺少 {normal} 面的色块")
            stickers.append((normal, color))
        cubie.stickers = tuple(stickers)
        cubie.sticker_map = dict(stickers)
    return cube
