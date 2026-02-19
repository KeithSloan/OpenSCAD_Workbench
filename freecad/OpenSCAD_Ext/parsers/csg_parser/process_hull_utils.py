from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import Part

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
