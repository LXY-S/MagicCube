"""Tiny software 3D renderer for the cube (projection + painter's algorithm).

The renderer is deliberately toolkit agnostic: it returns a list of flat,
depth-sorted polygons and the UI draws them with QPainter (or anything
else).  That keeps the geometry testable and the widgets simple.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .model import AXIS_INDEX, Cube, FACE_DIRS, local_to_world

SPACING = 1.0
CUBIE_SIZE = 0.96
CAMERA_Z = 12.0
FOCAL = 12.0
STICKER_INSET = 0.058
STICKER_OUTSET = 0.0035

DEFAULT_YAW = -34.0
DEFAULT_PITCH = 23.0
MIN_PITCH = -82.0
MAX_PITCH = 82.0
MIN_ZOOM = 0.65
MAX_ZOOM = 1.65

BODY_COLOR = "#0C0F15"
FACE_COLORS: dict[str, str] = {
    "U": "#F2F5F9",
    "D": "#FFD34E",
    "L": "#FF9448",
    "R": "#EF4B5D",
    "F": "#2FC98C",
    "B": "#4D8DFF",
}

# Two unit tangents spanning each face, expressed in the local frame.
FACE_TANGENTS: dict[tuple[int, int, int], tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    (0, 1, 0): ((1, 0, 0), (0, 0, -1)),
    (0, -1, 0): ((1, 0, 0), (0, 0, 1)),
    (1, 0, 0): ((0, 0, -1), (0, 1, 0)),
    (-1, 0, 0): ((0, 0, 1), (0, 1, 0)),
    (0, 0, 1): ((1, 0, 0), (0, 1, 0)),
    (0, 0, -1): ((-1, 0, 0), (0, 1, 0)),
}

LIGHT = (0.380, 0.779, 0.498)  # normalised (0.42, 0.86, 0.55)

_CORNER_SIGNS = ((1, 1), (-1, 1), (-1, -1), (1, -1))


@dataclass(frozen=True, slots=True)
class Poly:
    points: tuple[tuple[float, float], ...]
    fill: str
    outline: str
    width: float
    depth: float
    sticker: bool = False


def mat_mul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]):
    return tuple(
        tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] for j in range(3))
        for i in range(3)
    )


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]):
    x, y, z = vector
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z,
    )


def view_matrix(yaw_deg: float, pitch_deg: float):
    """World -> view transform: rotate around Y, then tilt around X."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    ry = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    rx = ((1.0, 0.0, 0.0), (0.0, cp, -sp), (0.0, sp, cp))
    return mat_mul(rx, ry)


def rotate_vector(vector: Sequence[float], axis: str, angle_deg: float):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = vector
    if axis == "x":
        return (x, c * y - s * z, s * y + c * z)
    if axis == "y":
        return (c * x + s * z, y, -s * x + c * z)
    return (c * x - s * y, s * x + c * y, z)


def project(
    world: Sequence[float],
    view,
    cx: float,
    cy: float,
    scale: float,
) -> tuple[float, float, float]:
    x, y, z = mat_vec(view, world)
    depth = CAMERA_Z - z
    if depth < 0.1:
        depth = 0.1
    f = FOCAL / depth
    return (cx + x * f * scale, cy - y * f * scale, depth)


def shade(hex_color: str, factor: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = max(0, min(255, int(round(r * factor))))
    g = max(0, min(255, int(round(g * factor))))
    b = max(0, min(255, int(round(b * factor))))
    return f"#{r:02x}{g:02x}{b:02x}"


def _light_factor(normal: Sequence[float]) -> float:
    dot = normal[0] * LIGHT[0] + normal[1] * LIGHT[1] + normal[2] * LIGHT[2]
    return 0.76 + 0.28 * max(0.0, dot)


def build_scene(
    cube: Cube,
    width: float,
    height: float,
    yaw: float,
    pitch: float,
    zoom: float = 1.0,
    anim: tuple[str, int, float] | None = None,
) -> list[Poly]:
    """Return depth-sorted polygons for the whole cube.

    ``anim`` is ``(axis, layer, angle_degrees)`` for a layer currently being
    turned.  The cube model itself is not modified while rendering.
    """
    if width <= 20 or height <= 20:
        return []

    scale = min(width, height) * 0.174 * zoom
    cx = width / 2.0
    cy = height / 2.0
    view = view_matrix(yaw, pitch)
    half = CUBIE_SIZE / 2.0
    sticker_half = half - STICKER_INSET

    anim_index = AXIS_INDEX[anim[0]] if anim else -1
    anim_axis = anim[0] if anim else ""
    anim_layer = anim[1] if anim else 0
    anim_angle = anim[2] if anim else 0.0

    groups: list[tuple[float, list[Poly]]] = []

    for cubie in cube.cubies:
        if cubie.pos == (0, 0, 0):
            continue

        if anim is not None and cubie.pos[anim_index] == anim_layer:
            pos = rotate_vector(cubie.pos, anim_axis, anim_angle)
            orient = tuple(
                rotate_vector(row, anim_axis, anim_angle) for row in cubie.orient
            )
        else:
            pos = cubie.pos
            orient = cubie.orient

        center = (pos[0] * SPACING, pos[1] * SPACING, pos[2] * SPACING)
        center_view = mat_vec(view, center)
        cubie_depth = CAMERA_Z - center_view[2]
        cubie_polys: list[Poly] = []

        for normal in FACE_DIRS.values():
            world_n = local_to_world(orient, normal)
            view_n = mat_vec(view, world_n)
            if view_n[2] <= 0.0005:
                continue

            t1, t2 = FACE_TANGENTS[normal]
            shade_factor = _light_factor(world_n)

            # --- dark cubie body ---------------------------------------
            body_points: list[tuple[float, float]] = []
            body_depth = 0.0
            for s1, s2 in _CORNER_SIGNS:
                local = (
                    normal[0] * half + t1[0] * half * s1 + t2[0] * half * s2,
                    normal[1] * half + t1[1] * half * s1 + t2[1] * half * s2,
                    normal[2] * half + t1[2] * half * s1 + t2[2] * half * s2,
                )
                offset = local_to_world(orient, local)
                world = (
                    center[0] + offset[0],
                    center[1] + offset[1],
                    center[2] + offset[2],
                )
                sx, sy, depth = project(world, view, cx, cy, scale)
                body_points.append((sx, sy))
                body_depth += depth
            body_depth /= 4.0
            body_fill = shade(BODY_COLOR, 0.65 + 0.5 * shade_factor)
            cubie_polys.append(
                Poly(
                    tuple(body_points),
                    body_fill,
                    body_fill,
                    1.0,
                    body_depth,
                )
            )

            # --- coloured sticker --------------------------------------
            code = cubie.sticker_map.get(normal)
            if code is None:
                continue

            sticker_points: list[tuple[float, float]] = []
            sticker_depth = 0.0
            out = half + STICKER_OUTSET
            for s1, s2 in _CORNER_SIGNS:
                local = (
                    normal[0] * out + t1[0] * sticker_half * s1 + t2[0] * sticker_half * s2,
                    normal[1] * out + t1[1] * sticker_half * s1 + t2[1] * sticker_half * s2,
                    normal[2] * out + t1[2] * sticker_half * s1 + t2[2] * sticker_half * s2,
                )
                offset = local_to_world(orient, local)
                world = (
                    center[0] + offset[0],
                    center[1] + offset[1],
                    center[2] + offset[2],
                )
                sx, sy, depth = project(world, view, cx, cy, scale)
                sticker_points.append((sx, sy))
                sticker_depth += depth
            sticker_depth = sticker_depth / 4.0 - 0.0008

            fill = shade(FACE_COLORS[code], shade_factor)
            outline = shade(FACE_COLORS[code], shade_factor * 0.64)
            cubie_polys.append(
                Poly(
                    tuple(sticker_points),
                    fill,
                    outline,
                    1.0,
                    sticker_depth,
                    sticker=True,
                )
            )

        groups.append((cubie_depth, cubie_polys))

    # Draw cubie by cubie, from far to near.  A cubie is convex, so its
    # visible faces never overlap each other in screen space; sorting whole
    # cubies avoids most of the artifacts of sorting every face globally.
    groups.sort(key=lambda item: item[0], reverse=True)
    return [poly for _, poly_group in groups for poly in poly_group]
