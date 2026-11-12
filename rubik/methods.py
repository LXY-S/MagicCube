"""Human-style restoration methods, built from stage goals.

The app offers Kociemba's two-phase solver plus four methods that mirror
how people solve the cube:

* 层先法 / Layer-by-Layer (LBL)
* CFOP (Cross, F2L, OLL, PLL)
* Roux
* ZZ (EOLine, F2L, last layer)

Each method is expressed as a sequence of *stages*.  A stage says which
pieces must be solved (and, for orientation stages, which stickers must
face where).  To turn a stage into moves, this module builds a complete
target cube in which those pieces are home while every other piece keeps
its current position and orientation as far as possible.  Kociemba's
pattern solver (``kociemba.solve(current, target)``) then finds turns
from the current state to that target, and the next stage starts from
the resulting state.

That means a plan is genuinely structured by the chosen method: after
every stage the pieces (and orientations) that the method has solved so
far really are in place.  The moves inside a stage come from the same
two-phase engine as the default solver, so they need not match the
classic human algorithms move for move.  See ``README.md`` for the
stage tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from kociemba.pykociemba.cubiecube import CubieCube, moveCube
from kociemba.pykociemba.facecube import FaceCube

from .facelets import (
    cube_from_facelets,
    cube_to_facelets,
    normalise_facelets,
)
from .model import Cube, Move, parse_moves, simplify
from .solver import SolverError, kociemba_string, solve_cube

# ---------------------------------------------------------------------------
# Kociemba cubie indices
# ---------------------------------------------------------------------------
# Corners: URF, UFL, ULB, UBR, DFR, DLF, DBL, DRB
# Edges:   UR, UF, UL, UB, DR, DF, DL, DB, FR, FL, BL, BR
TOP_CORNERS = frozenset((0, 1, 2, 3))
BOTTOM_CORNERS = frozenset((4, 5, 6, 7))
BOTTOM_EDGES = frozenset((4, 5, 6, 7))
MIDDLE_EDGES = frozenset((8, 9, 10, 11))
TOP_EDGES = frozenset((0, 1, 2, 3))
ALL_CORNERS = TOP_CORNERS | BOTTOM_CORNERS
ALL_EDGES = TOP_EDGES | BOTTOM_EDGES | MIDDLE_EDGES

# Faces are indexed in Kociemba's U, R, F, D, L, B order by moveCube.
_MOVE_INDEX = {face: index for index, face in enumerate("URFDLB")}


# ---------------------------------------------------------------------------
# Method and stage descriptions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StagePlan:
    """One method stage and the turns that realise it."""

    name: str
    detail: str
    moves: tuple[Move, ...]

    @property
    def move_count(self) -> int:
        return len(self.moves)


@dataclass(frozen=True)
class _StageSpec:
    """A stage goal used to construct the next target state.

    ``corners``/``edges`` contain home position indices whose home piece
    must be solved with zero orientation.  ``corner_mode`` and
    ``edge_mode`` add orientation-only goals for the pieces that are not
    solved yet (for example the top cross before corner orientation).
    """

    name: str
    detail: str
    corners: frozenset[int] = frozenset()
    edges: frozenset[int] = frozenset()
    corner_mode: str = "free"
    edge_mode: str = "free"


@dataclass(frozen=True)
class SolveMethod:
    """A selectable restoration method."""

    id: str
    label: str
    title: str
    description: str
    stages: tuple[_StageSpec, ...] = ()
    is_human: bool = field(default=False)


@dataclass(frozen=True)
class Solution:
    """A complete method-specific restoration plan."""

    method: SolveMethod
    stages: tuple[StagePlan, ...]

    @property
    def moves(self) -> list[Move]:
        return [move for stage in self.stages for move in stage.moves]

    @property
    def move_count(self) -> int:
        return sum(stage.move_count for stage in self.stages)

    @property
    def stage_count(self) -> int:
        return len(self.stages)


_LBL_STAGES: tuple[_StageSpec, ...] = (
    _StageSpec(
        "底面十字",
        "四个底面棱块归位，形成底面十字。",
        edges=BOTTOM_EDGES,
    ),
    _StageSpec(
        "第一层角块",
        "四个底层角块归位，完成第一层。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES,
    ),
    _StageSpec(
        "中层棱块",
        "四个中层棱块插入第二层，前两层完成。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
    ),
    _StageSpec(
        "顶面十字",
        "让顶层四个棱块的顶色朝上，形成顶面十字。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
        edge_mode="top_edges_up",
    ),
    _StageSpec(
        "顶面颜色",
        "翻转顶层角块，使整个顶面成为同一种颜色。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
        corner_mode="top_corners_up",
        edge_mode="top_edges_up",
    ),
    _StageSpec(
        "顶角归位",
        "调整四个顶层角块的位置，同时保持顶面同色。",
        corners=ALL_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
        edge_mode="top_edges_up",
    ),
    _StageSpec(
        "顶棱归位",
        "调整四个顶层棱块的位置，完成复原。",
        corners=ALL_CORNERS,
        edges=ALL_EDGES,
    ),
)

# F2L pair order: DFR+FR, DLF+FL, DBL+BL, DRB+BR.
_F2L_PAIRS = ((4, 8), (5, 9), (6, 10), (7, 11))

_CFOP_STAGES: tuple[_StageSpec, ...] = (
    _StageSpec(
        "底面十字",
        "Cross：四个底面棱块归位。",
        edges=BOTTOM_EDGES,
    ),
    *tuple(
        _StageSpec(
            f"F2L 第 {index} 组",
            "First Two Layers：角块与棱块配对后一起归位。",
            corners=BOTTOM_CORNERS & frozenset((corner,)),
            edges=BOTTOM_EDGES | frozenset(
                edge for pair_corner, edge in _F2L_PAIRS[:index]
            ),
        )
        for index, (corner, _edge) in enumerate(_F2L_PAIRS, start=1)
    ),
    _StageSpec(
        "OLL",
        "Orientation of Last Layer：顶层全部翻成顶色朝上。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
        corner_mode="top_corners_up",
        edge_mode="top_edges_up",
    ),
    _StageSpec(
        "PLL",
        "Permutation of Last Layer：顶层归位，完成复原。",
        corners=ALL_CORNERS,
        edges=ALL_EDGES,
    ),
)

_ROUX_STAGES: tuple[_StageSpec, ...] = (
    _StageSpec(
        "左侧块",
        "First Block：左侧 1×2×3 块（两个角块与三个棱块）。",
        corners=frozenset((5, 6)),
        edges=frozenset((6, 9, 10)),
    ),
    _StageSpec(
        "右侧块",
        "Second Block：右侧 1×2×3 块，完成前两层。",
        corners=BOTTOM_CORNERS,
        edges=frozenset((4, 6, 8, 9, 10, 11)),
    ),
    _StageSpec(
        "CMLL",
        "Corners of Last Layer：顶层四个角块归位。",
        corners=ALL_CORNERS,
        edges=frozenset((4, 6, 8, 9, 10, 11)),
    ),
    _StageSpec(
        "LSE",
        "Last Six Edges：最后六条棱归位，完成复原。",
        corners=ALL_CORNERS,
        edges=ALL_EDGES,
    ),
)

_ZZ_STAGES: tuple[_StageSpec, ...] = (
    _StageSpec(
        "EOLine",
        "Edge Orientation + Line：全部棱块定向，DF 与 DB 归位。",
        edges=frozenset((5, 7)),
        edge_mode="all_up",
    ),
    _StageSpec(
        "F2L 第 1 组",
        "First Two Layers：完成 DFR/FR 一组，并放入 DR 棱块。",
        corners=frozenset((4,)),
        edges=frozenset((4, 5, 7, 8)),
        edge_mode="all_up",
    ),
    _StageSpec(
        "F2L 第 2 组",
        "First Two Layers：完成 DLF/FL 一组，并放入 DL 棱块。",
        corners=frozenset((4, 5)),
        edges=frozenset((4, 5, 6, 7, 8, 9)),
        edge_mode="all_up",
    ),
    _StageSpec(
        "F2L 第 3 组",
        "First Two Layers：完成 DBL/BL 一组。",
        corners=frozenset((4, 5, 6)),
        edges=frozenset((4, 5, 6, 7, 8, 9, 10)),
        edge_mode="all_up",
    ),
    _StageSpec(
        "F2L 第 4 组",
        "First Two Layers：完成 DRB/BR 一组，前两层全部归位。",
        corners=BOTTOM_CORNERS,
        edges=BOTTOM_EDGES | MIDDLE_EDGES,
        edge_mode="all_up",
    ),
    _StageSpec(
        "OLL",
        "Orientation of Last Layer：翻转顶层角块，使顶面同色。",
        corners=BOTTOM_CORNERS,
        edges=ALL_EDGES,
        corner_mode="top_corners_up",
        edge_mode="all_up",
    ),
    _StageSpec(
        "PLL",
        "Permutation of Last Layer：顶层角块归位，完成复原。",
        corners=ALL_CORNERS,
        edges=ALL_EDGES,
        edge_mode="all_up",
    ),
)

_METHODS: tuple[SolveMethod, ...] = (
    SolveMethod(
        "kociemba",
        "Kociemba",
        "Kociemba 两阶段",
        "两阶段算法一次求出完整复原步骤，不划分人类方法阶段。",
    ),
    SolveMethod(
        "lbl",
        "层先法",
        "层先法 LBL",
        "逐层复原：底面十字 → 第一层 → 第二层 → 顶层。",
        _LBL_STAGES,
        True,
    ),
    SolveMethod(
        "cfop",
        "CFOP",
        "CFOP",
        "Cross → F2L（四组）→ OLL → PLL。",
        _CFOP_STAGES,
        True,
    ),
    SolveMethod(
        "roux",
        "Roux",
        "Roux",
        "左右两个 1×2×3 块 → CMLL → 最后六棱（LSE）。",
        _ROUX_STAGES,
        True,
    ),
    SolveMethod(
        "zz",
        "ZZ",
        "ZZ",
        "EOLine → F2L（四组）→ 顶层定向与归位。",
        _ZZ_STAGES,
        True,
    ),
)

METHODS: tuple[SolveMethod, ...] = _METHODS
METHOD_BY_ID: dict[str, SolveMethod] = {method.id: method for method in _METHODS}
DEFAULT_METHOD_ID = "kociemba"


def method_by_id(method_id: str) -> SolveMethod:
    """Return a method by id, raising a friendly error for unknown ids."""
    try:
        return METHOD_BY_ID[method_id]
    except KeyError as exc:
        raise ValueError(f"未知的复原方法：{method_id!r}") from exc


# ---------------------------------------------------------------------------
# Target construction
# ---------------------------------------------------------------------------
def _preserving_assignment(
    current_perm: Sequence[int],
    count: int,
    solved: frozenset[int],
) -> dict[int, int]:
    """Assign the unsolved pieces to the unsolved slots.

    Pieces that are already in an unsolved slot stay there when possible;
    the rest are paired up in index order.  This keeps a stage target as
    close to the current state as the stage goal allows.
    """
    positions = [index for index in range(count) if index not in solved]
    pieces = [index for index in range(count) if index not in solved]
    piece_set = set(pieces)
    assignment: dict[int, int] = {}
    used: set[int] = set()

    for position in positions:
        piece = current_perm[position]
        if piece in piece_set and piece not in used:
            assignment[position] = piece
            used.add(piece)

    rest_pieces = [piece for piece in pieces if piece not in used]
    rest_positions = [position for position in positions if position not in assignment]
    for position, piece in zip(rest_positions, rest_pieces):
        assignment[position] = piece
    return assignment


def _build_target(current: CubieCube, spec: _StageSpec) -> CubieCube:
    """Build a valid complete cube matching one stage goal."""
    cp: list[int | None] = [None] * 8
    co = [0] * 8
    ep: list[int | None] = [None] * 12
    eo = [0] * 12

    for position in spec.corners:
        cp[position] = position
    for position in spec.edges:
        ep[position] = position

    corner_assignment = _preserving_assignment(current.cp, 8, spec.corners)
    edge_assignment = _preserving_assignment(current.ep, 12, spec.edges)
    for position, piece in corner_assignment.items():
        cp[position] = piece
    for position, piece in edge_assignment.items():
        ep[position] = piece

    # Keep unsolved pieces in their current orientation when they also
    # stay in their current slot; this makes the target easier to reach.
    for position, piece in corner_assignment.items():
        if piece == current.cp[position]:
            co[position] = current.co[position]
    for position, piece in edge_assignment.items():
        if piece == current.ep[position]:
            eo[position] = current.eo[position]

    unsolved_corners = [index for index in range(8) if index not in spec.corners]
    unsolved_edges = [index for index in range(12) if index not in spec.edges]

    if spec.corner_mode == "top_corners_up":
        if any(position not in TOP_CORNERS for position in unsolved_corners):
            raise SolverError("顶层翻色阶段需要先完成底层角块。")
        for position in TOP_CORNERS:
            co[position] = 0

    if spec.edge_mode == "all_up":
        for position in range(12):
            eo[position] = 0
    elif spec.edge_mode == "top_edges_up":
        if any(position not in TOP_EDGES for position in unsolved_edges):
            raise SolverError("顶面十字阶段需要先完成前两层棱块。")
        for position in TOP_EDGES:
            eo[position] = 0

    # A target must have an even number of flipped edges.
    if sum(eo) % 2:
        pinned = (
            set(range(12))
            if spec.edge_mode == "all_up"
            else TOP_EDGES
            if spec.edge_mode == "top_edges_up"
            else set()
        )
        candidates = [index for index in unsolved_edges if index not in pinned]
        if not candidates:
            raise SolverError("无法构造合法的棱块朝向目标。")
        eo[candidates[0]] ^= 1

    # Corner twists must sum to 0 (mod 3).
    twist = sum(co) % 3
    if twist:
        candidates = [
            index
            for index in unsolved_corners
            if not (
                spec.corner_mode == "top_corners_up"
                and index in TOP_CORNERS
            )
        ]
        if not candidates:
            raise SolverError("无法构造合法的角块朝向目标。")
        co[candidates[0]] = (co[candidates[0]] - twist) % 3

    target = CubieCube()
    target.cp = cp  # type: ignore[assignment]
    target.co = co
    target.ep = ep  # type: ignore[assignment]
    target.eo = eo

    error = target.verify()
    if error == -6:
        # Corner and edge permutations must have the same parity.  Swap
        # two unsolved pieces of one kind; they are all interchangeable
        # within their own orbit.
        if len(unsolved_corners) >= 2:
            first, second = unsolved_corners[0], unsolved_corners[1]
            cp[first], cp[second] = cp[second], cp[first]
        elif len(unsolved_edges) >= 2:
            first, second = unsolved_edges[0], unsolved_edges[1]
            ep[first], ep[second] = ep[second], ep[first]
        else:
            raise SolverError("无法调整目标状态的置换奇偶性。")
        error = target.verify()

    if error:
        raise SolverError(f"阶段目标不是合法魔方状态（错误 {error}）。")
    return target


# ---------------------------------------------------------------------------
# Applying moves inside the Kociemba cubie representation
# ---------------------------------------------------------------------------
def _copy_cc(cube: CubieCube) -> CubieCube:
    copy = CubieCube()
    copy.cp = list(cube.cp)
    copy.co = list(cube.co)
    copy.ep = list(cube.ep)
    copy.eo = list(cube.eo)
    return copy


def _apply_cc(cube: CubieCube, moves: Sequence[Move]) -> CubieCube:
    result = _copy_cc(cube)
    for move in moves:
        turns = move.amount % 4
        for _ in range(turns):
            result.multiply(moveCube[_MOVE_INDEX[move.face]])
    return result


def _is_solved_cc(cube: CubieCube) -> bool:
    return (
        list(cube.cp) == list(range(8))
        and list(cube.ep) == list(range(12))
        and not any(cube.co)
        and not any(cube.eo)
    )


def _cube_cc(cube: Cube) -> CubieCube:
    text = kociemba_string(cube_to_facelets(cube))
    return FaceCube(text).toCubieCube()


def stage_goal_met(cube: Cube, method_id: str, stage_index: int) -> bool:
    """True when ``cube`` satisfies the method's stage goal.

    The check includes the solved pieces and the orientation-only goals
    (top cross, top face, EOLine).  It is used by the tests and is handy
    for verifying a plan independently of the exact target state.
    """
    method = method_by_id(method_id)
    if not method.stages:
        return cube.is_solved()
    if not 0 <= stage_index < len(method.stages):
        raise IndexError("阶段编号越界")
    spec = method.stages[stage_index]
    state = _cube_cc(cube)

    for position in spec.corners:
        if state.cp[position] != position or state.co[position] != 0:
            return False
    for position in spec.edges:
        if state.ep[position] != position or state.eo[position] != 0:
            return False
    if spec.corner_mode == "top_corners_up":
        if any(state.co[position] for position in TOP_CORNERS):
            return False
    if spec.edge_mode == "top_edges_up":
        if any(state.eo[position] for position in TOP_EDGES):
            return False
    if spec.edge_mode == "all_up":
        if any(state.eo):
            return False
    return True


# ---------------------------------------------------------------------------
# Solving
# ---------------------------------------------------------------------------
def _pattern_solve(current_text: str, target_text: str) -> list[Move]:
    """Ask Kociemba for turns taking current to target."""
    import kociemba

    last_error: Exception | None = None
    for max_depth in (24, 30):
        try:
            solution = kociemba.solve(
                current_text, target_text, max_depth=max_depth
            )
        except Exception as exc:  # the C wrapper uses one generic error
            last_error = exc
            continue
        moves = simplify(parse_moves(solution))
        if moves:
            return moves
        last_error = SolverError("求解器没有返回可用的阶段步骤。")
    raise SolverError("Kociemba 无法求出这个阶段目标。") from last_error


def _solve_human(method: SolveMethod, cube: Cube) -> Solution:
    current_text = kociemba_string(cube_to_facelets(cube))
    try:
        current = FaceCube(current_text).toCubieCube()
    except Exception as exc:
        raise SolverError("这个色块组合不是可复原的合法魔方状态。") from exc
    if current.verify():
        raise SolverError("这个色块组合不是可复原的合法魔方状态。")
    stages: list[StagePlan] = []

    for index, spec in enumerate(method.stages, start=1):
        target = _build_target(current, spec)
        target_text = target.toFaceCube().to_String()

        if current.toFaceCube().to_String() == target_text:
            moves: list[Move] = []
        else:
            try:
                moves = _pattern_solve(
                    current.toFaceCube().to_String(), target_text
                )
            except SolverError as exc:
                raise SolverError(
                    f"{method.title} · 第 {index} 阶段（{spec.name}）失败：{exc}"
                ) from exc

        check = _apply_cc(current, moves)
        if check.toFaceCube().to_String() != target_text:
            raise SolverError(
                f"{method.title} · 第 {index} 阶段（{spec.name}）结果校验失败。"
            )
        current = check
        stages.append(StagePlan(spec.name, spec.detail, tuple(moves)))

    if not _is_solved_cc(current):
        raise SolverError(f"{method.title} 的方案未能完成复原。")

    # Replay on the sticker model as a second, independent check.  This
    # also exercises the exact move engine used by the animation.
    work = cube_from_facelets(cube_to_facelets(cube))
    work.apply_moves(move for stage in stages for move in stage.moves)
    if not work.is_solved():
        raise SolverError(f"{method.title} 的方案未能通过模型校验。")

    return Solution(method, tuple(stages))


def solve_with_method(method_id: str, cube: Cube) -> Solution:
    """Solve ``cube`` with the selected method.

    The returned :class:`Solution` lists one :class:`StagePlan` per
    method stage.  A solved cube yields no stages.  Invalid states raise
    :class:`SolverError`.
    """
    method = method_by_id(method_id)
    if cube.is_solved():
        return Solution(method, ())

    if method.is_human:
        return _solve_human(method, cube)

    moves = solve_cube(cube)
    if not moves:
        return Solution(method, ())
    detail = "两阶段算法一次求出完整复原步骤。"
    return Solution(method, (StagePlan("两阶段求解", detail, tuple(moves)),))


def solve_facelets_with_method(
    facelets,
    method_id: str = DEFAULT_METHOD_ID,
) -> tuple[Cube, Solution]:
    """Build a cube from facelets and solve it with the selected method."""
    colors = normalise_facelets(facelets)
    kociemba_string(colors)  # validate colours and centres up front
    cube = cube_from_facelets(colors)
    return cube, solve_with_method(method_id, cube)
