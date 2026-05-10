"""
Hull of mixed primitive types: parallel uniform cylinders + one axis-aligned cube.

Geometry
--------
The 3-D convex hull of (N parallel cylinders + 1 cube) is built in three
sections, then fused:

  1. Middle extrusion  (a_cyl_min → a_cyl_max)
       Extrude the 2-D expanded hull polygon (convex hull of all cylinder
       circles + cube cross-section) along the cylinder axis.

  2. Bottom transition  (a_cube_min → a_cyl_min)  [if cube extends past cylinders]
       _make_convex_frustum: two-pointer lateral-face algorithm that builds the
       convex hull of two parallel convex CCW polygons as a closed solid.
       Faces are stitched with sewShape() to produce proper manifold topology.

  3. Top transition  (a_cyl_max → a_cube_max)  [if cube extends past cylinders]
       Same as (2), reversed.

The two-pointer algorithm correctly identifies which vertex of the bottom
polygon corresponds to which vertex of the top polygon — OCC's makeLoft cannot
do this reliably when the two polygons have different shapes (rectangle vs.
irregular hull) regardless of vertex count matching.

The cylinder axis may point in any direction; an orthonormal basis
(axis_dir, ux, uy) is built automatically.

Constraints
-----------
  • All cylinders must have parallel axes (any direction, ±).
  • All cylinders must have the same radius (r1 == r2, equal across all).
  • Exactly one cube (world-axis-aligned).

Returns None on any failure — the caller falls back to OpenSCAD CLI.
"""

import math
import Part
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import convex_hull_2d


def _warn(msg):
    import FreeCAD
    write_log("Hull", msg)
    FreeCAD.Console.PrintWarning(f"[Hull] {msg}\n")


def _perp_basis(axis_dir):
    """Return (ux, uy) forming a right-handed orthonormal basis with axis_dir."""
    seed = Vector(1, 0, 0) if abs(axis_dir.x) < 0.9 else Vector(0, 1, 0)
    uy = axis_dir.cross(seed).normalize()
    ux = uy.cross(axis_dir).normalize()
    return ux, uy


def _make_wire(hull_2d, a, to_3d, tol=1e-9):
    """Closed polygon wire from a 2-D hull at axial position a."""
    pts = [to_3d(u, v, a) for (u, v) in hull_2d]
    edges = []
    n = len(pts)
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        if (p0 - p1).Length > tol:
            edges.append(Part.makeLine(p0, p1))
    if not edges:
        return None
    try:
        return Part.Wire(edges)
    except Exception as exc:
        write_log("Hull", f"_make_wire failed at a={a:.3f}: {exc}")
        return None


def _make_convex_frustum(P_2d, Q_2d, a_P, a_Q, to_3d, tol=1e-9):
    """
    Build a closed solid — the convex hull of two parallel convex CCW polygons.

    P_2d : CCW convex polygon at axial position a_P  (bottom)
    Q_2d : CCW convex polygon at axial position a_Q  (top, a_Q > a_P)

    Uses a two-pointer lateral-face algorithm:
      advancing P → triangle  P[i] → P[i+1] → Q[j]
      advancing Q → triangle  P[i] → Q[j+1] → Q[j]
    (winding chosen for outward-pointing normals given CCW P and Q
     viewed from the +axis direction)

    Faces are stitched via sewShape() to produce a closed manifold shell,
    then wrapped in a solid.
    """
    m = len(P_2d)
    n = len(Q_2d)
    if m < 3 or n < 3:
        return None

    P3 = [to_3d(u, v, a_P) for (u, v) in P_2d]
    Q3 = [to_3d(u, v, a_Q) for (u, v) in Q_2d]

    # Starting alignment: rightmost vertex (max u, break ties by max v)
    i = max(range(m), key=lambda k: (P_2d[k][0], P_2d[k][1]))
    j = max(range(n), key=lambda k: (Q_2d[k][0], Q_2d[k][1]))

    def _face3(A, B, C):
        """Build a planar triangular Part.Face from three 3-D vectors."""
        if (A - B).Length < tol or (B - C).Length < tol or (A - C).Length < tol:
            return None
        try:
            wire = Part.makePolygon([A, B, C, A])
            return Part.Face(wire)
        except Exception as exc:
            write_log("Hull", f"frustum _face3 failed: {exc}")
            return None

    faces = []
    p_adv = 0
    q_adv = 0

    for _ in range(m + n):
        i_next = (i + 1) % m
        j_next = (j + 1) % n

        if p_adv >= m:
            cross = -1.0          # P exhausted — must advance Q
        elif q_adv >= n:
            cross = 1.0           # Q exhausted — must advance P
        else:
            dp = (P_2d[i_next][0] - P_2d[i][0], P_2d[i_next][1] - P_2d[i][1])
            dq = (Q_2d[j_next][0] - Q_2d[j][0], Q_2d[j_next][1] - Q_2d[j][1])
            cross = dp[0] * dq[1] - dp[1] * dq[0]   # dp × dq: > 0 → advance P

        if cross >= 0:
            # Advance P: triangle P[i] → P[i+1] → Q[j]
            f = _face3(P3[i], P3[i_next], Q3[j])
            if f:
                faces.append(f)
            i = i_next
            p_adv += 1
        else:
            # Advance Q: triangle P[i] → Q[j+1] → Q[j]
            f = _face3(P3[i], Q3[j_next], Q3[j])
            if f:
                faces.append(f)
            j = j_next
            q_adv += 1

    # Bottom cap: reverse P so outward normal points in −axis direction
    try:
        P3_rev = list(reversed(P3))
        wire_bot = Part.makePolygon(P3_rev + [P3_rev[0]])
        faces.append(Part.Face(wire_bot))
    except Exception as exc:
        write_log("Hull", f"frustum bottom cap failed: {exc}")
        return None

    # Top cap: Q as-is, outward normal points in +axis direction
    try:
        wire_top = Part.makePolygon(Q3 + [Q3[0]])
        faces.append(Part.Face(wire_top))
    except Exception as exc:
        write_log("Hull", f"frustum top cap failed: {exc}")
        return None

    write_log("Hull",
              f"  frustum: {len(faces)} faces built (P={m} verts, Q={n} verts)")

    # ---- Sew the compound of faces into a closed manifold shell ----------
    try:
        import FreeCAD
        compound = Part.makeCompound(faces)
        compound.sewShape()          # merges coincident edges → closed shell

        # After sewShape() the compound's ShapeType may change to "Shell"
        # or stay "Compound" with Shells as sub-shapes — handle both.
        shell = None
        stype = compound.ShapeType
        write_log("Hull", f"  sewShape done, ShapeType={stype}, Shells={len(compound.Shells)}")
        FreeCAD.Console.PrintMessage(
            f"[Hull] sewShape done: type={stype} shells={len(compound.Shells)}\n")

        if stype == "Shell":
            shell = compound
        elif compound.Shells:
            shell = compound.Shells[0]

        if shell is None:
            _warn("_make_convex_frustum: sewShape produced no usable shell")
            return None

        solid = Part.makeSolid(shell)
        if solid is None or solid.isNull():
            raise ValueError("null solid from frustum")
        # Ensure positive volume (fix orientation if OCC reversed it)
        try:
            if solid.Volume < 0:
                solid.complement()
        except Exception:
            pass
        write_log("Hull", f"  frustum solid OK, volume={solid.Volume:.3f}")
        return solid
    except Exception as exc:
        write_log("Hull", f"_make_convex_frustum: sew/solid failed: {exc}")
        import FreeCAD
        FreeCAD.Console.PrintWarning(f"[Hull] frustum sew/solid failed: {exc}\n")
        return None


def hull_cylinders_and_cube(normalized_hull, n_circle=64):
    """
    Build a BRep solid for hull(N cylinders + 1 cube).

    Strategy: extrude the middle section, then build frustum transitions
    at each end using the two-pointer convex-hull-of-parallel-polygons
    algorithm, fusing all three sections at the end.
    """
    import FreeCAD
    FreeCAD.Console.PrintMessage(
        f"[Hull] hull_cylinders_and_cube: {len(normalized_hull)} primitives "
        f"({sum(1 for p in normalized_hull if p['type']=='cylinder')} cyl, "
        f"{sum(1 for p in normalized_hull if p['type']=='cube')} cube)\n")
    write_log("Hull", f"hull_cylinders_and_cube called with {len(normalized_hull)} primitives")

    cylinders = [p for p in normalized_hull if p["type"] == "cylinder"]
    cubes     = [p for p in normalized_hull if p["type"] == "cube"]

    if not cubes:
        _warn("hull_cylinders_and_cube: no cube found")
        return None
    if len(cubes) > 1:
        _warn(f"hull_cylinders_and_cube: {len(cubes)} cubes — only 1 supported")
        return None
    if not cylinders:
        _warn("hull_cylinders_and_cube: no cylinders found")
        return None

    cube = cubes[0]

    # ---------------------------------------------------------------- #
    # Validate: all cylinders have parallel axes
    # ---------------------------------------------------------------- #
    first_dir = cylinders[0]["dir"]
    for cyl in cylinders[1:]:
        if not (cyl["dir"].isEqual(first_dir, 1e-6) or
                cyl["dir"].isEqual(first_dir.negative(), 1e-6)):
            _warn("hull_cylinders_and_cube: cylinders not parallel — skipping")
            return None

    axis_dir = first_dir

    # ---------------------------------------------------------------- #
    # Validate: uniform radius
    # ---------------------------------------------------------------- #
    r = cylinders[0]["r1"]
    for cyl in cylinders:
        if abs(cyl["r1"] - r) > 1e-6 or abs(cyl["r2"] - r) > 1e-6:
            _warn("hull_cylinders_and_cube: non-uniform radii — skipping")
            return None

    # ---------------------------------------------------------------- #
    # Orthonormal basis and coordinate helpers
    # ---------------------------------------------------------------- #
    ux, uy = _perp_basis(axis_dir)

    def proj_2d(pt):
        return (pt.dot(ux), pt.dot(uy))

    def to_3d(u, v, a):
        return axis_dir * a + ux * u + uy * v

    # ---------------------------------------------------------------- #
    # Axial extents
    # ---------------------------------------------------------------- #
    a_cyl_mins, a_cyl_maxs = [], []
    for cyl in cylinders:
        a_base = cyl["base"].dot(axis_dir)
        if cyl["dir"].dot(axis_dir) > 0:
            a_cyl_mins.append(a_base)
            a_cyl_maxs.append(a_base + cyl["h"])
        else:
            a_cyl_mins.append(a_base - cyl["h"])
            a_cyl_maxs.append(a_base)

    a_cyl_min = min(a_cyl_mins)
    a_cyl_max = max(a_cyl_maxs)

    sx, sy, sz = cube["size"]
    corner = cube["corner"]
    cube_corners_3d = [
        corner + Vector(dx * sx, dy * sy, dz * sz)
        for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)
    ]
    cube_axis_vals = [c.dot(axis_dir) for c in cube_corners_3d]
    a_cube_min = min(cube_axis_vals)
    a_cube_max = max(cube_axis_vals)

    write_log("Hull",
              f"hull_cylinders_and_cube: axis=({axis_dir.x:.2f},{axis_dir.y:.2f},{axis_dir.z:.2f}), "
              f"r={r:.3f}, a_cube=[{a_cube_min:.3f},{a_cube_max:.3f}], "
              f"a_cyl=[{a_cyl_min:.3f},{a_cyl_max:.3f}]")

    # ---------------------------------------------------------------- #
    # 2-D cross-sections
    # ---------------------------------------------------------------- #
    cube_pts_2d = [proj_2d(c) for c in cube_corners_3d]
    cube_hull_2d = convex_hull_2d(cube_pts_2d)

    all_pts_2d = list(cube_pts_2d)
    for cyl in cylinders:
        cu, cv = proj_2d(cyl["base"])
        for k in range(n_circle):
            angle = 2.0 * math.pi * k / n_circle
            all_pts_2d.append((cu + r * math.cos(angle),
                               cv + r * math.sin(angle)))

    expanded_hull_2d = convex_hull_2d(all_pts_2d)

    if len(expanded_hull_2d) < 3:
        _warn("hull_cylinders_and_cube: degenerate expanded hull")
        return None

    write_log("Hull",
              f"  cube hull: {len(cube_hull_2d)} pts, "
              f"expanded hull: {len(expanded_hull_2d)} pts")

    # ---------------------------------------------------------------- #
    # Build the three solids
    # ---------------------------------------------------------------- #
    TOL_A = 1e-6
    shapes = []

    # -- 1. Middle: extrude expanded polygon from a_cyl_min to a_cyl_max --
    if abs(a_cyl_max - a_cyl_min) > TOL_A:
        w_mid = _make_wire(expanded_hull_2d, a_cyl_min, to_3d)
        if w_mid is None:
            _warn("hull_cylinders_and_cube: middle wire failed")
            return None
        try:
            face_mid = Part.Face(w_mid)
            extrude_vec = axis_dir * (a_cyl_max - a_cyl_min)
            middle = face_mid.extrude(extrude_vec)
            if middle is None or middle.isNull():
                raise ValueError("null middle extrusion")
            shapes.append(middle)
            write_log("Hull", "  middle extrusion OK")
        except Exception as exc:
            _warn(f"hull_cylinders_and_cube: middle extrusion failed: {exc}")
            return None

    # -- 2. Bottom transition: cube rect → expanded polygon --
    if (a_cyl_min - a_cube_min) > TOL_A:
        bot = _make_convex_frustum(cube_hull_2d, expanded_hull_2d,
                                   a_cube_min, a_cyl_min, to_3d)
        if bot is None or bot.isNull():
            _warn("hull_cylinders_and_cube: bottom transition failed")
            return None
        shapes.append(bot)
        write_log("Hull", "  bottom transition OK")

    # -- 3. Top transition: expanded polygon → cube rect --
    if (a_cube_max - a_cyl_max) > TOL_A:
        top = _make_convex_frustum(expanded_hull_2d, cube_hull_2d,
                                   a_cyl_max, a_cube_max, to_3d)
        if top is None or top.isNull():
            _warn("hull_cylinders_and_cube: top transition failed")
            return None
        shapes.append(top)
        write_log("Hull", "  top transition OK")

    # ---------------------------------------------------------------- #
    # Fuse all sections into one solid
    # ---------------------------------------------------------------- #
    if not shapes:
        _warn("hull_cylinders_and_cube: no sections built")
        return None

    result = shapes[0]
    for s in shapes[1:]:
        try:
            result = result.fuse(s)
        except Exception as exc:
            _warn(f"hull_cylinders_and_cube: fuse failed: {exc}")
            return None

    write_log("Hull",
              f"hull_cylinders_and_cube: succeeded "
              f"({len(shapes)} section(s), "
              f"axis=({axis_dir.x:.2f},{axis_dir.y:.2f},{axis_dir.z:.2f}))")
    return result
