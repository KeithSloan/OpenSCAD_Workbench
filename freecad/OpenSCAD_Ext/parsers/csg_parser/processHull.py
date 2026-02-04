from FreeCAD import Base, Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import Part

# -----------------------------
# Public API
# -----------------------------
def try_hull(node):
    write_log("AST", f"Try Hull node_type={node.node_type}")

    if node.node_type != "hull":
        return None

    primitives = []
    matrices = []

    if not collect_primitives(node.children, primitives, matrices):
        write_log("Hull", "not_handled: hull")
        return None

    geo = normalize_primitives(primitives, matrices)
    if geo is None:
        write_log("Hull", "not_handled: normalize failed")
        return None

    return try_hull_dispatch(geo)


def collect_primitives(children, primitives_out, matrices_out, parent_matrix=None):
    for child in children:
        matrix = (
            parent_matrix.multiply(child.matrix)
            if (parent_matrix and hasattr(child, "matrix"))
            else (child.matrix if hasattr(child, "matrix") else parent_matrix)
        )

        if child.node_type == "group":
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix):
                return False

        elif child.node_type == "multmatrix":
            if not hasattr(child, "matrix"):
                return False
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix):
                return False

        elif child.node_type in ("sphere", "cube", "cylinder"):
            primitives_out.append(child)
            matrices_out.append(matrix if matrix else Matrix())

        else:
            write_log("Hull", f"unsupported node inside hull: {child.node_type}")
            return False

    return True

def normalize_primitives(primitives, matrices):
    out = []

    for node, mat in zip(primitives, matrices):
        pos = Vector(0, 0, 0)
        axis = Vector(0, 0, 1)

        if mat:
            pos = mat.multVec(pos)
            axis = mat.multVec(axis) - mat.multVec(Vector(0, 0, 0))

        if node.node_type == "sphere":
            if "r" not in node.params:
                return None
            out.append({
                "type": "sphere",
                "center": pos,
                "r": node.params["r"],
            })

        elif node.node_type == "cube":
            if "size" not in node.params:
                return None
            out.append({
                "type": "cube",
                "center": pos,
                "size": node.params["size"],
            })

        elif node.node_type == "cylinder":
            if not {"r", "h"} <= node.params.keys():
                return None
            out.append({
                "type": "cylinder",
                "center": pos,
                "axis": axis.normalize(),
                "r": node.params["r"],
                "h": node.params["h"],
            })

    return out

def try_hull_dispatch(normalized_hull):
    types = {p["type"] for p in normalized_hull}
    write_log("Hull", f"Dispatch types={types}")
    write_log("Normalized ",normalized_hull)

    write_log("Len", len(types))

    if len(types) == 1:
        if types == {'sphere'}:
            return hull_spheres(normalized_hull)
    write_log("Len", len(types))
    return None

def hull_spheres(spheres):
    write_log("Hull","Spheres")
    centers = [s["center"] for s in spheres]

    write_log("Centers",centers)

    if not all(abs(s["r"] - spheres[0]["r"]) < 1e-12 for s in spheres):
        write_log("Spheres","Not all equal Radius")
        return None

    r = spheres[0]["r"]

    if is_collinear(centers):
        return make_capsule(centers[0], centers[-1], r)
    write_log("Spheres","Not collinear")

    grid = detect_grid(centers)
    if grid:
        return rounded_bbox(centers, r)
    write_log("Spheres","Not Grid")
    return None

def hull_cubes(cubes):
    centers = [c["center"] for c in cubes]
    sizes = [c["size"] for c in cubes]

    if any(s != sizes[0] for s in sizes):
        return None

#        return None
#

    min_pt, max_pt = bbox(centers)
    return Part.makeBox(
        max_pt.x - min_pt.x,
        max_pt.y - min_pt.y,
        max_pt.z - min_pt.z,
        min_pt
    )

def hull_cylinders(cyls):
    axes = [c["axis"] for c in cyls]

    if not all(a.isEqual(axes[0], 1e-9) for a in axes):
        return None

    centers = [c["center"] for c in cyls]
    if not is_collinear(centers):
        return None

    r = cyls[0]["r"]
    return make_capsule(centers[0], centers[-1], r)


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

def rounded_bbox(points, r):
    min_pt, max_pt = bbox(points)
    box = Part.makeBox(
        max_pt.x - min_pt.x,
        max_pt.y - min_pt.y,
        max_pt.z - min_pt.z,
        min_pt
    )
    return box.makeMinkowskiSum(Part.makeSphere(r))

def make_capsule(p0, p1, r):
    axis = p1 - p0
    L = axis.Length
    if L < 1e-12:
        return Part.makeSphere(r, p0)
    cyl = Part.makeCylinder(r, L, p0, axis.normalize())
    return cyl.fuse(Part.makeSphere(r, p0)).fuse(Part.makeSphere(r, p1))

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
