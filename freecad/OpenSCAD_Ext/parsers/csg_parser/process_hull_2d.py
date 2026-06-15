# =============================================================================
# process_hull_2d.py
#
# Hull of 2-D primitives (circle / square / polygon), the planar analogue of the
# sphere/cube/cylinder analytical hulls.  OpenSCAD's hull() of 2-D children is a
# 2-D operation and must yield a planar Face — NOT a 3-D convex hull (whose
# points are coplanar and would fail "need at least 4 unique points").
#
# Strategy:
#   • All circles, equal radius  → exact rounded polygon: Minkowski sum of the
#     centres' 2-D convex hull with the disc (arc corners), via
#     make_rounded_polygon_wire.
#   • Anything else (mixed radii, squares, polygons, circle+poly)  → convex hull
#     of sampled boundary points → polygon Face (faceted but correct; circles
#     are sampled, so the hull encloses them).
#
# Returns a Part.Face, or None on failure (caller falls back).
# =============================================================================

import math
import Part
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    convex_hull_2d,
    make_rounded_polygon_wire,
)

# Orthonormal basis for the XY plane (2-D ops live at z = 0).
_AX = Vector(0, 0, 1)
_UX = Vector(1, 0, 0)
_UY = Vector(0, 1, 0)

TWO_D_TYPES = {"circle", "square", "polygon"}


def hull_2d(prims):
    """Build the 2-D hull Face of normalized 2-D primitives.

    prims: list of dicts produced by normalize_primitives, each
           {"type": "circle", "center": Vector, "r": float, "fn": int}  or
           {"type": "square"/"polygon", "pts": [Vector, ...]}.
    """
    circles = [p for p in prims if p.get("type") == "circle"]
    others = [p for p in prims if p.get("type") != "circle"]

    # ── Exact path: equal-radius circles only → rounded polygon ──────────
    if circles and not others:
        radii = {round(p["r"], 6) for p in circles}
        if len(radii) == 1:
            r = circles[0]["r"]
            centres = [(p["center"].x, p["center"].y) for p in circles]
            hull = convex_hull_2d(centres)
            if len(hull) >= 2:
                wire = make_rounded_polygon_wire(hull, r, 0.0, _AX, _UX, _UY)
                if wire is not None:
                    try:
                        face = Part.Face(wire)
                        write_log("Hull2D",
                            f"rounded-circle hull: {len(circles)} circles "
                            f"r={r} → {len(hull)}-gon")
                        return face
                    except Exception as ex:
                        write_log("Hull2D", f"rounded face failed: {ex}")
            # fall through to faceted path on any failure

    # ── General faceted path: sample boundaries, hull the points ─────────
    pts = []
    for p in prims:
        if p.get("type") == "circle":
            c, r = p["center"], p["r"]
            n = max(8, int(p.get("fn") or 32))
            for i in range(n):
                a = 2.0 * math.pi * i / n
                pts.append((c.x + r * math.cos(a), c.y + r * math.sin(a)))
        else:
            for v in p.get("pts", []):
                pts.append((v.x, v.y))

    hull = convex_hull_2d(pts)
    if len(hull) < 3:
        write_log("Hull2D", f"degenerate 2-D hull ({len(hull)} pts)")
        return None
    verts = [Vector(u, v, 0.0) for (u, v) in hull]
    verts.append(verts[0])
    try:
        face = Part.Face(Part.makePolygon(verts))
        write_log("Hull2D", f"faceted 2-D hull → {len(hull)}-gon")
        return face
    except Exception as ex:
        write_log("Hull2D", f"polygon face failed: {ex}")
        return None
