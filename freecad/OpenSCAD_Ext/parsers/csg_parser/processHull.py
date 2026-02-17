from FreeCAD import Vector, Matrix, Placement, Rotation
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
            print(f"tyoe {child.node_type} params {child.params} csg_params {child.csg_params}")
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

    write_log("Number of types ", len(types))

    if len(types) == 1:
        if types == {'sphere'}:
            return hull_spheres(normalized_hull)
    write_log("Len", len(types))
    return None

def hull_spheres(spheres):
    write_log("Hull","Spheres")
    centers = [s["center"] for s in spheres]

    write_log("Centers",centers)

    if is_collinear(centers):
        if all(abs(s["r"] - spheres[0]["r"]) < 1e-12 for s in spheres):
            r = spheres[0]["r"]
            write_log("Spheres: make capsule")
            return make_capsule(centers[0], centers[-1], r)
            
        else:
            write_log("Spheres","Not all equal Radius")
            return make_colinear_sphere_hull(spheres)

    if not all(abs(s["r"] - spheres[0]["r"]) < 1e-12 for s in spheres):
        return None # Not handled

    r = spheres[0]["r"]
    write_log("Spheres",f" Radius {r} Type {type(r)}")

    grid = detect_grid(centers)
    if grid:
        return try_hull_spheres(centers, r)
    write_log("Spheres","Not Grid")
    return None


def try_hull_spheres(centers, r, min_thickness=1e-3):
    """
    Create a rounded hull for a set of spheres.
    Automatically handles:
      - Flat 2D grids (Z nearly zero)
      - Full 3D arrangements
    centers: list of Vector
    r: sphere radius / rounding radius
    """
    if not centers:
        return None

    min_pt = Vector(
        min(c.x for c in centers),
        min(c.y for c in centers),
        min(c.z for c in centers)
    )
    max_pt = Vector(
        max(c.x for c in centers),
        max(c.y for c in centers),
        max(c.z for c in centers)
    )

    size = max_pt - min_pt

    # Determine if flat in Z
    is_flat = size.z < 1e-6 or size.z < r

    if not is_flat:
        # Full 3D → fillet all edges
        box_size = Vector(
            max(size.x + 2*r, min_thickness),
            max(size.y + 2*r, min_thickness),
            max(size.z + 2*r, min_thickness)
        )
        placement = min_pt - Vector(r, r, r)
        box = Part.makeBox(box_size.x, box_size.y, box_size.z, placement)
        fillet_radius = min(r, box_size.x/2, box_size.y/2, box_size.z/2)
        try:
            rounded_box = box.makeFillet(fillet_radius, box.Edges)
        except Exception:
            rounded_box = box
        return rounded_box

    else:
        # Flat grid → thin box + corner spheres + XY edge cylinders
        thickness = max(size.z + 2*r, min_thickness)
        box = Part.makeBox(size.x + 2*r, size.y + 2*r, thickness,
                           min_pt - Vector(r, r, r))
        shapes = [box]

        # Corners
        corners = [
            Vector(min_pt.x - r, min_pt.y - r, min_pt.z),
            Vector(max_pt.x + r, min_pt.y - r, min_pt.z),
            Vector(min_pt.x - r, max_pt.y + r, min_pt.z),
            Vector(max_pt.x + r, max_pt.y + r, min_pt.z)
        ]
        for c in corners:
            shapes.append(Part.makeSphere(r, c))

        # XY edge cylinders
        # along X edges
        shapes.append(Part.makeCylinder(r, size.x + 2*r, corners[0], Vector(1,0,0)))
        shapes.append(Part.makeCylinder(r, size.x + 2*r, corners[2], Vector(1,0,0)))
        # along Y edges
        shapes.append(Part.makeCylinder(r, size.y + 2*r, corners[0], Vector(0,1,0)))
        shapes.append(Part.makeCylinder(r, size.y + 2*r, corners[1], Vector(0,1,0)))

        # Fuse all
        rounded_box = shapes[0]
        for s in shapes[1:]:
            rounded_box = rounded_box.fuse(s)

        return rounded_box


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


def make_colinear_sphere_hull(spheres):
    parts = []

    for s in spheres:
        sphere = Part.makeSphere(s['r'], s['center'])
        parts.append(sphere)

    # tangent frusta / cylinders
    for i in range(len(spheres)-1):
        a = spheres[i]
        b = spheres[i+1]

        p1 = a['center']
        r1 = a['r']
        p2 = b['center']
        r2 = b['r']

        axis = p2.sub(p1)
        d = axis.Length
        if d <= 1e-9:
            continue
        axis_norm = axis.normalize()

        if abs(r2 - r1) < 1e-9:
            cyl = Part.makeCylinder(r1, d, p1, axis_norm)
            parts.append(cyl)
        else:
            frustum = make_tangent_frustum(p1, r1, p2, r2)
            parts.append(frustum)

    # Fuse all parts, no FeaturePython, safe refine
    compound = parts[0]
    for shp in parts[1:]:
        compound = compound.fuse(shp)

    # Optional refine
    try:
        compound = compound.removeSplitter()
    except Exception:
        pass

    return compound


def hull_cubes(cubes):
    centers = [c["center"] for c in cubes]
    sizes = [c["size"] for c in cubes]

    if any(s != sizes[0] for s in sizes):
        return None


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
