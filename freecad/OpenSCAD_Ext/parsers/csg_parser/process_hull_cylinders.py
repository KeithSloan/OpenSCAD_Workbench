import math
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    convex_hull_2d,
    #make_tangent_frustum,
    #detect_grid,
)
import Part


def hull_cylinders_cones(cylinders):
    """
    OpenSCAD is really a cone, cylinder if r1 = r2
    Handle a set of cylinders in a hull.
    - If all axes aligned and collinear, make a capsule if equal radii.
    - If different radii, create tangent frustums.
    - If all equal-radius true cylinders with a 2-D grid of positions, make a
      rounded-polygon extrusion.
    - Otherwise fallback.
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
# Rounded-polygon extrusion: hull of parallel equal-radius cylinders whose
# bases/tops form a 2-D polygon (non-collinear) perpendicular to the shared axis.
#
# Strategy:
#   1. Project cylinder positions to 2-D (perpendicular to axis_dir).
#   2. Compute 2-D convex hull of those positions.
#   3. Offset each hull edge outward by r, find adjacent intersections
#      → "outer polygon" (straight-sided, no arcs).
#   4. Extrude the outer polygon along axis_dir.
#   5. Fillet the prism's vertical edges (parallel to axis_dir) with radius r.
#
# The fillet arcs are centered on the original hull vertices (= cylinder
# positions), giving the exact Minkowski-sum geometry without needing Part.Arc.
#
# This is the analytic equivalent of the classic OpenSCAD rounded-box pattern:
#
#   hull() {
#       for ([x,y] = corners) translate([x, y, z]) cylinder(h=..., r=r);
#   }
# -----------------------------------------------------------------------------

def hull_parallel_cylinders_grid(cylinders, axis_dir, TOL=1e-6):
    """
    Build a rounded-polygon extrusion from a set of parallel, equal-radius
    true cylinders (r1 == r2) whose axes are all aligned with *axis_dir*.

    Returns a Part.Shape or None if the conditions are not met.
    """
    write_log("Hull", "hull_parallel_cylinders_grid: attempting rounded-polygon extrusion.")

    # All must be true cylinders (r1 == r2) with the same radius
    r = cylinders[0]["r1"]
    for c in cylinders:
        if abs(c["r1"] - c["r2"]) > TOL:
            write_log("Hull", "hull_parallel_cylinders_grid: cone detected, fallback.")
            return None
        if abs(c["r1"] - r) > TOL:
            write_log("Hull", "hull_parallel_cylinders_grid: mixed radii, fallback.")
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

    # Project every cylinder base and top onto (ux, uy) and collect axial extents
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

    # 2-D convex hull of projected positions
    hull = convex_hull_2d(pts_2d)
    n = len(hull)
    write_log("Hull", f"hull_parallel_cylinders_grid: 2-D hull has {n} vertices, r={r}, z=[{z_min:.3f},{z_max:.3f}]")

    if n < 3:
        write_log("Hull", "hull_parallel_cylinders_grid: degenerate hull, fallback.")
        return None

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
            write_log("Hull", "hull_parallel_cylinders_grid: degenerate edge, fallback.")
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
        write_log("Hull", f"hull_parallel_cylinders_grid: polygon/face failed: {e}")
        return None

    extrude_vec = axis_dir * (z_max - z_min)
    try:
        prism = face.extrude(extrude_vec)
    except Exception as e:
        write_log("Hull", f"hull_parallel_cylinders_grid: extrude failed: {e}")
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

    write_log("Hull", f"hull_parallel_cylinders_grid: {len(vert_edges)} vertical edges to fillet with r={r}")

    if not vert_edges:
        write_log("Hull", "hull_parallel_cylinders_grid: no vertical edges found, returning prism.")
        return prism

    try:
        shape = prism.makeFillet(r, vert_edges)
    except Exception as e:
        write_log("Hull", f"hull_parallel_cylinders_grid: makeFillet failed: {e}, returning prism.")
        return prism   # still better than tessellation

    shape = shape.removeSplitter()
    shape.fix(1e-7, 1e-7, 1e-7)
    write_log("Hull", "hull_parallel_cylinders_grid: success.")
    return shape