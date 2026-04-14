import math
from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import Part

# -----------------------------
# 2-D convex hull (CCW order)
# -----------------------------

def convex_hull_2d(pts, tol=1e-6):
    """
    Return the 2-D convex hull of pts in counter-clockwise order.
    pts: list of (u, v) tuples.
    """
    def _cross(O, A, B):
        return (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0])

    # Deduplicate with tolerance
    unique = []
    for p in pts:
        if not any(abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for q in unique):
            unique.append(p)

    unique.sort()
    n = len(unique)
    if n < 2:
        return unique

    lower = []
    for p in unique:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(unique):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]   # CCW, no repeated start/end


# -----------------------------
# Rounded-polygon wire builder
# -----------------------------

def make_rounded_polygon_wire(hull_2d, r, z_ax, axis_dir, ux, uy, TOL=1e-9):
    """
    Build a closed wire that is the Minkowski sum of a convex 2-D polygon with
    a disk of radius *r*, lying in the plane at axial position *z_ax*.

    hull_2d : list of (u, v) in CCW order (convex hull vertices).
    r       : corner-rounding radius.
    z_ax    : position along *axis_dir*.
    axis_dir, ux, uy : orthonormal 3-D basis (axis_dir = extrusion direction).
    """
    n = len(hull_2d)
    if n < 2:
        return None

    def to3d(u, v):
        return ux * u + uy * v + axis_dir * z_ax

    # Outward edge normals for a CCW polygon:
    # edge from P_i -> P_{i+1}, direction d=(du,dv)  → outward normal = (dv, -du)
    edge_normals = []
    edge_dirs    = []
    for i in range(n):
        u0, v0 = hull_2d[i]
        u1, v1 = hull_2d[(i + 1) % n]
        du, dv = u1 - u0, v1 - v0
        L = math.sqrt(du * du + dv * dv)
        if L < TOL:
            return None
        du /= L; dv /= L
        edge_dirs.append((du, dv))
        edge_normals.append((dv, -du))   # outward for CCW

    edges = []

    for i in range(n):
        uv   = hull_2d[i]              # current vertex
        n_in  = edge_normals[(i - 1) % n]  # outward normal of incoming edge
        n_out = edge_normals[i]            # outward normal of outgoing edge

        # Arc end-points (where offset edges meet the arc)
        p_arc_start = to3d(uv[0] + r * n_in[0],  uv[1] + r * n_in[1])
        p_arc_end   = to3d(uv[0] + r * n_out[0], uv[1] + r * n_out[1])

        # Mid-point of arc: vertex + r * outward bisector
        bu = n_in[0] + n_out[0]
        bv = n_in[1] + n_out[1]
        bL = math.sqrt(bu * bu + bv * bv)
        if bL < TOL:
            # 180° corner — no arc needed, the two points coincide
            pass
        else:
            bu /= bL; bv /= bL
            p_arc_mid = to3d(uv[0] + r * bu, uv[1] + r * bv)

            if (p_arc_start - p_arc_end).Length > TOL:
                try:
                    arc = Part.Arc(p_arc_start, p_arc_mid, p_arc_end)
                    edges.append(arc.toShape())
                except Exception as e:
                    write_log("Hull", f"Arc failed at vertex {i}: {e}")
                    return None

        # Offset line along edge i
        u0, v0 = hull_2d[i]
        u1, v1 = hull_2d[(i + 1) % n]
        no = edge_normals[i]
        p_line_start = to3d(u0 + r * no[0], v0 + r * no[1])
        p_line_end   = to3d(u1 + r * no[0], v1 + r * no[1])

        if (p_line_start - p_line_end).Length > TOL:
            edges.append(Part.makeLine(p_line_start, p_line_end))

    if not edges:
        return None

    try:
        wire = Part.Wire(edges)
        return wire
    except Exception as e:
        write_log("Hull", f"Rounded-polygon wire failed: {e}")
        return None


def make_tangent_frustum(c1, r1, c2, r2):
    """
    Create a tangent frustum between spheres at c1,r1 and c2,r2.
    Works along any axis vector.
    """
    delta = c2 - c1
    length = delta.Length
    if length < 1e-9:
        raise ValueError("Sphere centers coincide")

    axis = delta.normalize()

    # FreeCAD Part.makeCone takes base radius, top radius, height, base point, axis
    cone = Part.makeCone(r1, r2, length, c1, axis)
    return cone

# -----------------------------
# Utility
# -----------------------------

def is_collinear(points, tol=1e-9):
    if len(points) < 2:
        return True
    v = points[1] - points[0]
    for p in points[2:]:
        if (p - points[0]).cross(v).Length > tol:
            return False
    return True

def detect_grid(points, tol=1e-9):
    xs = {round(p.x / tol) for p in points}
    ys = {round(p.y / tol) for p in points}
    zs = {round(p.z / tol) for p in points}
    return len(xs) * len(ys) * len(zs) == len(points)

def bbox(points):
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    return Vector(min(xs), min(ys), min(zs)), Vector(max(xs), max(ys), max(zs))

'''
def safe_offset(shape, r):
    try:
        offset = shape.makeOffsetShape(
            r,              # offset distance
            1e-6,           # tolerance
            join=Part.JoinType.Arc,
            fill=False,
            openResult=False,
            intersection=False
        )
        if offset and not offset.isNull():
            return offset
    except Exception:
        pass
    return shape  # fallback to original

def rounded_bbox(points, r):
    min_pt = Vector(min(p.x for p in points),
                    min(p.y for p in points),
                    min(p.z for p in points))
    max_pt = Vector(max(p.x for p in points),
                    max(p.y for p in points),
                    max(p.z for p in points))

    size = max_pt - min_pt

    # create the core box
    box = Part.makeBox(size.x, size.y, size.z, min_pt)

    # apply fillet to all edges
    edges = box.Edges
    rounded_box = box.makeFillet(r, edges)

    return rounded_box
'''
    

'''

def is_collinear(points, tol=1e-12):
    if len(points) < 2:
        return True
    v = points[1] - points[0]
    for p in points[2:]:
        if (p - points[0]).cross(v).Length > tol:
            return False
    return True

def make_capsule(p0, p1, radius):
    axis_vec = p1 - p0
    length = axis_vec.Length

    if length < 1e-12:
        # Degenerate → single sphere
        return Part.makeSphere(radius, p0)

    axis_dir = axis_vec.normalize()
    # Cylinder along axis_vec
    cyl = Part.makeCylinder(radius, length, p0, axis_dir)

    # Hemispheres at ends: just spheres at endpoints
    hemi1 = Part.makeSphere(radius, p0)
    hemi2 = Part.makeSphere(radius, p1)

    # Fuse solids
    capsule = cyl.fuse(hemi1).fuse(hemi2)
    return capsule
'''
