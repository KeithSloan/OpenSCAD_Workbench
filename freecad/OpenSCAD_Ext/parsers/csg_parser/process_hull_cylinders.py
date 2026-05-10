import math
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    convex_hull_2d,
    make_rounded_polygon_wire,
    #make_tangent_frustum,
    #detect_grid,
)
import Part


def hull_cylinders_cones(cylinders):
    """
    Handle a set of OpenSCAD cylinders/cones in a hull.

    OpenSCAD's cylinder() is a frustum: r1 at base, r2 at top (r1==r2 → true cylinder).

    Dispatch:
    - Collinear centres → revolved profile (handles mixed r1/r2 via upper-convex-hull
      in (z, r) space).
    - Non-collinear, parallel axes:
        (a) All r1==r2, same radius → rounded-polygon prism (extrude + fillet).
        (b) All same r1, same r2, r1!=r2, same direction, same base z-level →
            tapered rounded-polygon solid (loft between two rounded-polygon wires).
    - Otherwise → fallback to OpenSCAD CLI / STL.

    Note on the 8-cylinder pattern (e.g. pegboard rounded-box hull):
      OpenSCAD emits N_corners × 2 cylinders (one group per z-extreme) so that both
      the top AND bottom extents are fully defined.  The duplicate 2-D positions are
      harmless — convex_hull_2d deduplicates them and z_min/z_max still capture the
      full span.  This is correct and handled without any special-casing.
    """
    write_log("Hull", "Attempting to hull cylinders/cones.")

    if not cylinders:
        return None

    # --- Check for aligned axes ---
    # All cylinders/cones must have parallel axes for this handler.
    # We check against the first primitive's direction.
    first_dir = cylinders[0]["dir"]
    for c in cylinders[1:]:
        # Allow for parallel or anti-parallel axes
        if not (c["dir"].isEqual(first_dir, 1e-9) or c["dir"].isEqual(first_dir.negative(), 1e-9)):
            write_log("Hull", "Cylinder axes are not parallel, fallback.")
            return None

    # --- Check for collinear centers ---
    centers = [c["center"] for c in cylinders]
    if not is_collinear(centers):
        write_log("Hull", "Cylinders not collinear — trying rounded-polygon extrusion.")
        return hull_parallel_cylinders_grid(cylinders, first_dir)

    # If checks pass, proceed with generating the revolved hull
    return make_colinear_cylinders_cones(cylinders)

def make_colinear_cylinders_cones(primitives, TOL=1e-9):

    if not primitives:
        return None

    # ---------------------------------------
    # Axis direction (already unit from normalize)
    # ---------------------------------------
    axis_dir = primitives[0]["dir"]

    # Use global origin for projection stability
    axis_origin = Vector(0, 0, 0)

    # ---------------------------------------
    # Construct perpendicular radial direction
    # ---------------------------------------
    if abs(axis_dir.z) < 0.9:
        ref = Vector(0, 0, 1)
    else:
        ref = Vector(1, 0, 0)

    radial_dir = axis_dir.cross(ref)
    if radial_dir.Length == 0:
        return None
    radial_dir = radial_dir.normalize()

    # ---------------------------------------
    # Collect disc endpoints in (z, r)
    # ---------------------------------------
    pts = []

    for p in primitives:
        base = p["base"]  # The start point of the cylinder's axis
        h = p["h"]        # The height of the cylinder
        dir_vec = p["dir"]  # The direction vector of the cylinder's axis
        r1 = p["r1"]      # Radius at the base
        r2 = p["r2"]      # Radius at the top

        # The other end of the cylinder's axis
        top = base + dir_vec * h

        # Project the base and top points onto the common axis direction
        # to get their positions along that axis.
        z_base = base.dot(axis_dir)
        z_top = top.dot(axis_dir)

        pts.append((z_base, r1))
        pts.append((z_top, r2))

    # Sort by z
    pts.sort(key=lambda x: x[0])

    # ---------------------------------------
    # Compute upper convex hull in (z, r)
    # ---------------------------------------
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    upper = []

    for p in pts:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) >= -TOL:
            upper.pop()
        upper.append(p)

    if len(upper) < 2:
        return None

    # ---------------------------------------
    # Build 2D profile in 3D space
    # ---------------------------------------
    edges = []

    z_start, r_start = upper[0]
    z_end, r_end = upper[-1]

    axis_start = axis_origin + axis_dir * z_start
    axis_end   = axis_origin + axis_dir * z_end

    # Axis to first radius
    first_pt = axis_start + radial_dir * r_start
    edges.append(Part.makeLine(axis_start, first_pt))

    # Hull profile segments
    for i in range(len(upper) - 1):
        z0, r0 = upper[i]
        z1, r1 = upper[i + 1]

        p0 = axis_origin + axis_dir * z0 + radial_dir * r0
        p1 = axis_origin + axis_dir * z1 + radial_dir * r1

        edges.append(Part.makeLine(p0, p1))

    # Close back to axis
    last_pt = axis_end + radial_dir * r_end
    edges.append(Part.makeLine(last_pt, axis_end))
    edges.append(Part.makeLine(axis_end, axis_start))

    wire = Part.Wire(edges)
    face = Part.Face(wire)

    # ---------------------------------------
    # Revolve full 360 degrees
    # ---------------------------------------
    shape = face.revolve(axis_origin, axis_dir, 360)

    if shape.ShapeType == "Shell":
        shape = Part.Solid(shape)

    shape = shape.removeSplitter()
    shape.fix(1e-7, 1e-7, 1e-7)

    return shape


# -----------------------------------------------------------------------------
# Rounded-polygon grid: hull of parallel cylinders/cones whose centres form a
# 2-D polygon (non-collinear) perpendicular to the shared axis.
#
# Two sub-cases:
#
# (a) True cylinders (r1 == r2 for all, same radius):
#   Strategy:
#     1. Project cylinder positions to 2-D (⊥ axis_dir).
#     2. Convex hull of those positions (convex_hull_2d deduplicates repeats).
#     3. Offset each hull edge outward by r → "outer polygon" (straight-sided).
#     4. Extrude the outer polygon along axis_dir.
#     5. Fillet vertical edges with radius r.
#   Fillet arcs are centred on the original hull vertices (= cylinder positions),
#   giving the exact Minkowski-sum geometry.  This is the analytic equivalent of:
#     hull() { for ([x,y]=corners) translate([x,y,z]) cylinder(h=…, r=r); }
#
# (b) Uniform-taper cones (all same r1, all same r2, r1 != r2):
#   Requires: all cones same direction (not anti-parallel), all bases at the same
#   z-level, all tops at the same z-level.
#   Strategy:
#     1. Build 2-D convex hull of centre positions (same as above).
#     2. Construct a rounded-polygon wire at z_base with radius r1 (make_rounded_polygon_wire).
#     3. Construct a rounded-polygon wire at z_top  with radius r2.
#     4. Loft between the two wires → tapered rounded-polygon solid.
#   The resulting shape is the Minkowski sum of the 2-D convex hull with a linearly
#   interpolated disk (radius goes from r1 at the base to r2 at the top).
# -----------------------------------------------------------------------------

def hull_parallel_cylinders_grid(cylinders, axis_dir, TOL=1e-6):
    """
    Build a rounded-polygon solid from a set of parallel cylinders or cones
    whose axes are all aligned with *axis_dir*.

    Returns a Part.Shape or None if conditions are not met (caller falls back
    to OpenSCAD CLI / STL).
    """
    write_log("Hull", "hull_parallel_cylinders_grid: attempting rounded-polygon solid.")

    # All primitives must share the same r1 and the same r2 (uniform taper).
    # Mixed-taper hulls (different cone angles) are not analytically reducible
    # to a simple loft and fall through to the OpenSCAD fallback.
    r1 = cylinders[0]["r1"]
    r2 = cylinders[0]["r2"]
    for c in cylinders:
        if abs(c["r1"] - r1) > TOL:
            write_log("Hull", "hull_parallel_cylinders_grid: mixed r1 radii, fallback.")
            return None
        if abs(c["r2"] - r2) > TOL:
            write_log("Hull", "hull_parallel_cylinders_grid: mixed r2 radii, fallback.")
            return None

    # Build a 2-D coordinate frame perpendicular to axis_dir
    if abs(axis_dir.z) < 0.9:
        ref = Vector(0, 0, 1)
    else:
        ref = Vector(1, 0, 0)

    ux = axis_dir.cross(ref)
    if ux.Length < TOL:
        return None
    ux = ux.normalize()
    uy = axis_dir.cross(ux).normalize()

    # Project every cylinder/cone base and top onto (ux, uy) and collect axial extents.
    # For Z-axis-aligned primitives the base and top project to the same 2-D point —
    # convex_hull_2d will deduplicate those automatically.
    pts_2d = []
    z_vals = []
    for c in cylinders:
        base = c["base"]
        top  = base + axis_dir * c["h"]
        pts_2d.append((base.dot(ux), base.dot(uy)))
        pts_2d.append((top.dot(ux),  top.dot(uy)))
        z_vals.append(base.dot(axis_dir))
        z_vals.append(top.dot(axis_dir))

    z_min = min(z_vals)
    z_max = max(z_vals)

    if z_max - z_min < TOL:
        write_log("Hull", "hull_parallel_cylinders_grid: zero axial extent, fallback.")
        return None

    # 2-D convex hull (deduplicates repeated projections, e.g. from the common
    # N_corners × 2_z_levels pattern OpenSCAD emits for rounded-box hulls)
    hull = convex_hull_2d(pts_2d)
    n = len(hull)
    write_log("Hull", f"hull_parallel_cylinders_grid: 2-D hull has {n} vertices, "
              f"r1={r1}, r2={r2}, z=[{z_min:.3f},{z_max:.3f}]")

    if n < 2:
        write_log("Hull", "hull_parallel_cylinders_grid: degenerate hull (<2 pts), fallback.")
        return None

    if n == 2:
        # Two unique centres — capsule (stadium) shape.
        # Only valid for equal-radius cylinders; tapered cones with 2 centres
        # produce an oblique frustum that is not yet implemented.
        if abs(r1 - r2) <= TOL:
            write_log("Hull", "hull_parallel_cylinders_grid: 2 centres — building capsule.")
            return _build_capsule(hull, r1, z_min, z_max, axis_dir, ux, uy, TOL)
        else:
            write_log("Hull", "hull_parallel_cylinders_grid: 2 centres, tapered — fallback.")
            return None

    # Dispatch: true cylinder (r1==r2) vs uniform-taper cone (r1!=r2)
    if abs(r1 - r2) <= TOL:
        return _build_rounded_prism(hull, r1, z_min, z_max, axis_dir, ux, uy, TOL)
    else:
        return _build_tapered_rounded_prism(cylinders, hull, r1, r2, axis_dir, ux, uy, TOL)


def _build_capsule(hull, r, z_min, z_max, axis_dir, ux, uy, TOL=1e-6):
    """
    Capsule (stadium) solid for the 2-unique-centre equal-radius case.

    The 2D outline is two straight edges (parallel, separated by 2r) plus
    two semicircular arcs at each cylinder centre.  Extruded along axis_dir.

    hull  -- 2-element list of (u, v) in the projection plane
    r     -- cylinder radius (equal for both)
    """
    u1, v1 = hull[0]
    u2, v2 = hull[1]

    du, dv = u2 - u1, v2 - v1
    L = math.sqrt(du * du + dv * dv)
    if L < TOL:
        write_log("Hull", "_build_capsule: zero segment length, fallback.")
        return None
    du /= L; dv /= L                  # unit direction along segment

    nu, nv = dv, -du                  # CCW outward perpendicular

    # 3-D vectors (hull plane + axial)
    D3 = du * ux + dv * uy            # along segment (unit)
    N3 = nu * ux + nv * uy            # perpendicular (unit)
    z_off = axis_dir * z_min          # axial base offset

    C1 = u1 * ux + v1 * uy            # centre 1 in hull plane (no z)
    C2 = u2 * ux + v2 * uy            # centre 2 in hull plane (no z)

    # Six key points of the capsule at z = z_min:
    #   top edge endpoints (offset +r in N3)
    p1_top = C1 + r * N3 + z_off
    p2_top = C2 + r * N3 + z_off
    #   bottom edge endpoints (offset −r in N3)
    p2_bot = C2 - r * N3 + z_off
    p1_bot = C1 - r * N3 + z_off
    #   midpoints of the semicircular arcs
    p2_mid = C2 + r * D3 + z_off     # 90° point of cap at C2
    p1_mid = C1 - r * D3 + z_off     # 90° point of cap at C1

    try:
        # Winding: p1_top → p2_top → (arc) → p2_bot → p1_bot → (arc) → p1_top
        edge_top = Part.makeLine(p1_top, p2_top)
        arc_C2   = Part.Arc(p2_top, p2_mid, p2_bot).toShape()
        edge_bot = Part.makeLine(p2_bot, p1_bot)
        arc_C1   = Part.Arc(p1_bot, p1_mid, p1_top).toShape()
        wire = Part.Wire([edge_top, arc_C2, edge_bot, arc_C1])
        face = Part.Face(wire)
    except Exception as e:
        write_log("Hull", f"_build_capsule: 2-D profile failed: {e}")
        return None

    h = z_max - z_min
    try:
        solid = face.extrude(axis_dir * h)
    except Exception as e:
        write_log("Hull", f"_build_capsule: extrude failed: {e}")
        return None

    write_log("Hull", "_build_capsule: success.")
    return solid


def _build_rounded_prism(hull, r, z_min, z_max, axis_dir, ux, uy, TOL=1e-6):
    """
    Rounded-polygon prism for parallel equal-radius cylinders.

    Builds a straight-sided outer polygon (each edge offset outward by r,
    corners at adjacent-edge intersections), extrudes it, then fillets the
    vertical edges with radius r to produce the exact Minkowski-sum shape.
    """
    n = len(hull)

    # ------------------------------------------------------------------
    # Compute edge unit directions and outward normals (CCW polygon)
    # ------------------------------------------------------------------
    edge_dirs    = []
    edge_normals = []
    for i in range(n):
        u0, v0 = hull[i]
        u1, v1 = hull[(i + 1) % n]
        du, dv = u1 - u0, v1 - v0
        L = math.sqrt(du * du + dv * dv)
        if L < TOL:
            write_log("Hull", "_build_rounded_prism: degenerate edge, fallback.")
            return None
        du /= L; dv /= L
        edge_dirs.append((du, dv))
        edge_normals.append((dv, -du))   # outward normal for CCW polygon

    # ------------------------------------------------------------------
    # Outer polygon: offset each edge outward by r, find pairwise intersections.
    # For convex corners the outer vertex lies at the intersection of the two
    # adjacent offset lines — the fillet will later create the arc between them,
    # with its centre at the original inner vertex (= cylinder centre).
    # ------------------------------------------------------------------
    outer_pts_2d = []
    for i in range(n):
        n_in  = edge_normals[(i - 1) % n]
        n_out = edge_normals[i]
        d_in  = edge_dirs[(i - 1) % n]
        d_out = edge_dirs[i]
        u_v, v_v = hull[i]

        # Two offset lines through the vertex, along each adjacent edge direction
        Pu = u_v + r * n_in[0];  Pv = v_v + r * n_in[1]   # point on incoming offset line
        Qu = u_v + r * n_out[0]; Qv = v_v + r * n_out[1]   # point on outgoing offset line

        # Solve: P + s*d_in = Q + t*d_out  →  s = det_s / det
        det = d_in[0] * (-d_out[1]) - (-d_out[0]) * d_in[1]
        if abs(det) < TOL:
            # Parallel edges (180° corner) — midpoint of the two offset points
            outer_pts_2d.append(((Pu + Qu) / 2, (Pv + Qv) / 2))
            continue
        dQu = Qu - Pu; dQv = Qv - Pv
        s = (dQu * (-d_out[1]) - dQv * (-d_out[0])) / det
        outer_pts_2d.append((Pu + s * d_in[0], Pv + s * d_in[1]))

    # ------------------------------------------------------------------
    # Build 3-D polygon wire at z_min and extrude
    # ------------------------------------------------------------------
    def to3d(u, v):
        return ux * u + uy * v + axis_dir * z_min

    outer_3d = [to3d(u, v) for u, v in outer_pts_2d]
    outer_3d.append(outer_3d[0])   # close

    try:
        wire  = Part.makePolygon(outer_3d)
        face  = Part.Face(wire)
    except Exception as e:
        write_log("Hull", f"_build_rounded_prism: polygon/face failed: {e}")
        return None

    extrude_vec = axis_dir * (z_max - z_min)
    try:
        prism = face.extrude(extrude_vec)
    except Exception as e:
        write_log("Hull", f"_build_rounded_prism: extrude failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Find edges parallel to axis_dir ("vertical" edges) and fillet them
    # ------------------------------------------------------------------
    vert_edges = []
    for edge in prism.Edges:
        verts = edge.Vertexes
        if len(verts) == 2:
            d = Vector(verts[1].Point) - Vector(verts[0].Point)
            if d.Length > TOL:
                cross = (d / d.Length).cross(axis_dir)
                if cross.Length < 0.01:
                    vert_edges.append(edge)

    write_log("Hull", f"_build_rounded_prism: {len(vert_edges)} vertical edges to fillet with r={r}")

    if not vert_edges:
        write_log("Hull", "_build_rounded_prism: no vertical edges found, returning prism.")
        return prism

    try:
        shape = prism.makeFillet(r, vert_edges)
    except Exception as e:
        write_log("Hull", f"_build_rounded_prism: makeFillet failed: {e}, returning prism.")
        return prism   # still better than tessellation

    shape = shape.removeSplitter()
    shape.fix(1e-7, 1e-7, 1e-7)
    write_log("Hull", "_build_rounded_prism: success.")
    return shape


def _build_tapered_rounded_prism(cylinders, hull, r1, r2, axis_dir, ux, uy, TOL=1e-6):
    """
    Tapered rounded-polygon solid for parallel uniform-taper cones.

    Lofts between a rounded-polygon wire at the base z-level (radius r1) and
    one at the top z-level (radius r2).  The result is the Minkowski sum of the
    2-D convex hull with a linearly interpolated disk, which is exactly the 3-D
    convex hull of a set of identically tapered cones placed at the hull vertices.

    Constraints (fall through to OpenSCAD fallback if violated):
    - All cones must be same-direction (anti-parallel mixes r1/r2 ends).
    - All cone bases must be at the same z-level; all tops at the same z-level.
      (Mixed z-level cones produce a complex multi-section shape that cannot be
      reduced to a two-wire loft — use the CLI fallback for those.)
    """
    write_log("Hull", "_build_tapered_rounded_prism: attempting tapered loft.")

    # Reject anti-parallel cones: they would have r1/r2 swapped at the z-extremes,
    # making the effective radius at z_min ambiguous without per-cone bookkeeping.
    first_dir = cylinders[0]["dir"]
    for c in cylinders:
        if c["dir"].isEqual(first_dir.negative(), 1e-9):
            write_log("Hull", "_build_tapered_rounded_prism: anti-parallel cones, fallback.")
            return None

    # All bases must be at the same z-level, all tops at the same z-level.
    base_zs = [c["base"].dot(axis_dir) for c in cylinders]
    top_zs  = [(c["base"] + axis_dir * c["h"]).dot(axis_dir) for c in cylinders]

    z_base = base_zs[0]
    z_top  = top_zs[0]
    for bz, tz in zip(base_zs[1:], top_zs[1:]):
        if abs(bz - z_base) > TOL or abs(tz - z_top) > TOL:
            write_log("Hull", "_build_tapered_rounded_prism: cones at mixed z-levels, fallback.")
            return None

    if z_top - z_base < TOL:
        write_log("Hull", "_build_tapered_rounded_prism: zero axial extent, fallback.")
        return None

    write_log("Hull", f"_build_tapered_rounded_prism: r1={r1}@z={z_base:.3f}, r2={r2}@z={z_top:.3f}")

    # Build arc-based rounded-polygon wires at each z-level
    bottom_wire = make_rounded_polygon_wire(hull, r1, z_base, axis_dir, ux, uy)
    top_wire    = make_rounded_polygon_wire(hull, r2, z_top,  axis_dir, ux, uy)

    if bottom_wire is None or top_wire is None:
        write_log("Hull", "_build_tapered_rounded_prism: wire construction failed, fallback.")
        return None

    try:
        # solid=True closes the loft; ruled=False gives smooth curved faces
        loft = Part.makeLoft([bottom_wire, top_wire], True, False)
    except Exception as e:
        write_log("Hull", f"_build_tapered_rounded_prism: makeLoft failed: {e}, fallback.")
        return None

    if loft is None or loft.isNull():
        write_log("Hull", "_build_tapered_rounded_prism: loft returned null, fallback.")
        return None

    loft = loft.removeSplitter()
    loft.fix(1e-7, 1e-7, 1e-7)
    write_log("Hull", "_build_tapered_rounded_prism: success.")
    return loft