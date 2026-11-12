"""Solve any cube state with Kociemba's two-phase algorithm.

Every restoration plan in the app goes through this module: scrambled
cubes, manual turns and custom sticker layouts alike.  Kociemba is
imported lazily, so only the first plan request pays for loading it;
that request is the demo scramble built during startup.
"""

from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Mapping, Sequence

from .facelets import (
    FACELET_FACES,
    cube_from_facelets,
    cube_to_facelets,
    normalise_facelets,
)
from .model import Cube, Move, parse_moves, simplify


class SolverError(ValueError):
    """A facelet arrangement that cannot be solved (or is incomplete)."""


def kociemba_string(facelets: Mapping[str, Sequence[str]]) -> str:
    centers = {face: facelets[face][4] for face in FACELET_FACES}
    if len(set(centers.values())) != 6:
        raise SolverError("六个中心色块的颜色必须互不相同。")

    counts = Counter(color for face in FACELET_FACES for color in facelets[face])
    color_to_face = {color: face for face, color in centers.items()}
    if set(counts) != set(color_to_face):
        missing = set(color_to_face) - set(counts)
        if missing:
            raise SolverError("每种颜色都需要出现在色块中。")
        raise SolverError("色块颜色必须全部来自六个中心块。")
    wrong = [color for color, count in counts.items() if count != 9]
    if wrong:
        raise SolverError("每种颜色需要恰好 9 个色块。")

    # Relabel each sticker by the face whose centre has that colour.  The
    # resulting string always has a standard U/R/F/D/L/B centre layout,
    # even when the user chose a permuted colour scheme.
    return "".join(
        color_to_face[color] for face in FACELET_FACES for color in facelets[face]
    )


def solve_cube(cube: Cube) -> list[Move]:
    """Return turns that make every face uniform, given the current centres.

    An already solved cube returns an empty plan.  Raises :class:`SolverError`
    for impossible colour distributions.
    """
    if cube.is_solved():
        return []
    facelets = cube_to_facelets(cube)
    return _solve_facelets(facelets)


def solve_facelets(
    facelets: Mapping[str, Sequence[str]],
) -> tuple[Cube, list[Move]]:
    """Build a cube from facelets and solve it, returning both."""
    colors = normalise_facelets(facelets)
    cube = cube_from_facelets(colors)
    return cube, solve_cube(cube)


def _solve_facelets(facelets: Mapping[str, Sequence[str]]) -> list[Move]:
    text = kociemba_string(facelets)
    try:
        import kociemba
    except Exception as exc:  # pragma: no cover - depends on installation
        raise SolverError(
            "缺少 kociemba 求解器，请运行 pip install -r requirements.txt。"
        ) from exc

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            solution = kociemba.solve(text)
    except Exception as exc:
        raise SolverError("这个色块组合不是可复原的合法魔方状态。") from exc

    moves = simplify(parse_moves(solution))
    if not moves:
        raise SolverError("求解器没有返回可用的复原步骤。")

    # Verify with our own move engine.  This also guards the facelet
    # orientation mapping against accidental changes.
    check = cube_from_facelets(facelets)
    check.apply_moves(moves)
    if not check.is_solved():
        raise SolverError("求解结果未能通过校验，请检查色块状态。")
    return moves
