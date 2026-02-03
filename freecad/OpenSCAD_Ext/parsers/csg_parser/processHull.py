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
    write_log("Hull", f"Collected {len(primitives)} primitives for fast hull")

    # Only handle spheres for now
    if all(p["type"] == "sphere" for p in primitives):
        return make_linear_sphere_hull(primitives, matrices)

    write_log("Hull", "not_handled: mixed or unsupported primitives")
    return None

# -----------------------------
# Recursive collector
# -----------------------------
def collect_primitives(children, primitives_out, matrices_acc, parent_matrix=None):
    """
    Recursively collect primitives from children.
    Returns False if unsupported nodes encountered.
    """
    for child in children:
        # Compute current transformation
        matrix = parent_matrix.multiply(child.matrix) if (parent_matrix and hasattr(child, "matrix")) else (child.matrix if hasattr(child, "matrix") else parent_matrix)

        if child.node_type in ("group",):
            if not collect_primitives(child.children, primitives_out, matrices_acc, matrix):
                return False
        elif child.node_type in ("multmatrix",):
            if not hasattr(child, "matrix"):
                write_log("Hull", f"multmatrix missing matrix, skipping")
                return False
            if not collect_primitives(child.children, primitives_out, matrices_acc, matrix):
                return False
        elif child.node_type in ("sphere", "cube", "cylinder"):
            primitives_out.append({"node": child, "type": child.node_type})
            matrices_acc.append(matrix if matrix else Matrix())  # store matrix per primitive
        else:
            # unsupported node, abort
            write_log("Hull", f"unsupported node inside hull: {child.node_type}")
            return False
    return True

# -----------------------------
# Hull maker
# -----------------------------
def make_linear_sphere_hull(primitives, matrices):
    """
    Only supports collinear equal-radius spheres
    """
    # Extract positions and radii
    positions = []
    radii = []
    for prim, mat in zip(primitives, matrices):
        node = prim["node"]
        # Sphere center is transformed origin
        pos = Vector(0, 0, 0)
        if hasattr(node, "params") and "r" in node.params:
            r = node.params["r"]
        else:
            write_log("HullSphere", "Sphere missing radius")
            return None
        # Apply matrix if present
        if mat:
            pos = mat.multVec(pos)
        positions.append(pos)
        radii.append(r)

    # Check equal radii
    if any(abs(r - radii[0]) > 1e-12 for r in radii):
        write_log("HullSphere", "Unequal radii, fallback")
        return None

    # Check collinear
    if not is_collinear(positions):
        write_log("HullSphere", "Not collinear, fallback")
        return None

    write_log("HullSphere", f"Creating capsule from {positions[0]} to {positions[-1]} radius={radii[0]}")
    return make_capsule(positions[0], positions[-1], radii[0])

# -----------------------------
# Utility
# -----------------------------
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
