import FreeCAD
from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


def _warn(msg):
    """Write a hull-failure reason to both the log file and the Report View (orange)."""
    write_log("Hull", msg)
    FreeCAD.Console.PrintWarning(f"[Hull] {msg}\n")
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_spheres import hull_spheres
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cylinders import hull_cylinders_cones
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_cubes import hull_cubes


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
        _warn("collect_primitives failed — hull contains unsupported child node types")
        return None

    geo = normalize_primitives(primitives, matrices)
    if geo is None:
        _warn("normalize_primitives failed — check cylinder/sphere parameter names")
        return None

    write_log("Hull", f"Dispatching hull with {len(geo)} primitive(s)")
    result = try_hull_dispatch(geo)
    if result is None:
        _warn(f"try_hull_dispatch returned None — hull type not handled natively "
              f"(types={{{', '.join(p['type'] for p in geo)}}})")
    return result


def _subtree_has_complex_op(node):
    """
    Return True if the node's subtree contains any operation that could
    dramatically reshape a primitive — i.e. anything beyond transparent
    wrappers (group, color, multmatrix) and leaf primitives.

    Used by the intersection handler to decide whether the clipping
    geometry is 'simple enough' to safely ignore (e.g. a linear_extrude
    sector polygon) versus 'complex' (e.g. difference/hull chains that
    reduce the primitive to a tiny fraction of its original extent).

    Complex ops that trigger fallback:
      difference, union, hull, minkowski, linear_extrude, rotate_extrude,
      offset, projection — anything constructive or extrusive.
    """
    _COMPLEX = {
        "difference", "union", "hull", "minkowski",
        "linear_extrude", "rotate_extrude", "offset", "projection",
    }
    if node.node_type in _COMPLEX:
        return True
    for child in (node.children or []):
        if _subtree_has_complex_op(child):
            return True
    return False


def collect_primitives(children, primitives_out, matrices_out, parent_matrix=None):
    for child in children:
        matrix = (
            parent_matrix.multiply(child.matrix)
            if (parent_matrix and hasattr(child, "matrix"))
            else (child.matrix if hasattr(child, "matrix") else parent_matrix)
        )

        if child.node_type in ("group", "color"):
            # color is a transparent wrapper — recurse into children, ignoring colour
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix):
                return False

        elif child.node_type == "multmatrix":
            if not hasattr(child, "matrix"):
                return False
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix):
                return False

        elif child.node_type == "hull":
            # Nested hull: flatten by recursing into its children.
            # The convex hull of a set of convex shapes equals the convex hull
            # of all their constituent primitives, so we can collect them directly
            # without losing correctness.  Any transform already accumulated in
            # `matrix` is passed through unchanged (hull itself applies no transform).
            write_log("Hull", "Nested hull detected — flattening into parent hull")
            if not collect_primitives(child.children, primitives_out, matrices_out, matrix):
                return False

        elif child.node_type in ("sphere", "cube", "cylinder"):
            primitives_out.append(child)
            print(f"type {child.node_type} params {child.params} csg_params {child.csg_params}")
            matrices_out.append(matrix if matrix else Matrix())

        elif child.node_type == "intersection":
            # An intersection clips a primitive to a sub-region.
            #
            # Safe approximation: hull(A ∩ B, ...) ⊆ hull(A, ...) because
            # clipping can only shrink the hull boundary, never expand it.
            # We use the first child primitive as a stand-in for the
            # intersection — BUT only when the clipping children are simple
            # (transparent wrappers + primitives).  When a clipping child
            # contains constructive ops (difference, hull, linear_extrude …)
            # the intersection result may be far smaller than the primitive
            # (e.g. a 30 mm cube clipped down to a tiny peg shape), making
            # the approximation produce grossly wrong hull geometry.
            # In that case, fail here so the caller falls back to OpenSCAD CLI.
            clipping_children = (child.children or [])[1:]  # everything after the first
            if any(_subtree_has_complex_op(s) for s in clipping_children):
                write_log("Hull",
                          "intersection: clipping child has complex ops "
                          "(difference/hull/extrude/…) — cannot safely approximate "
                          "as primitive; falling back to OpenSCAD CLI.")
                return False

            found = False
            for sub in child.children:
                sub_prims, sub_mats = [], []
                if collect_primitives([sub], sub_prims, sub_mats, matrix):
                    if sub_prims:
                        primitives_out.extend(sub_prims)
                        matrices_out.extend(sub_mats)
                        found = True
                        break
            if not found:
                write_log("Hull", "intersection: no primitive child found, fallback.")
                return False

        else:
            _warn(f"unsupported node inside hull: '{child.node_type}' — cannot build native BRep hull")
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
            size_val = node.params["size"]
            if isinstance(size_val, (list, tuple)):
                sx, sy, sz = float(size_val[0]), float(size_val[1]), float(size_val[2])
            else:
                sx = sy = sz = float(size_val)
            center_flag = bool(node.params.get("center", False))
            # Compute the Part.makeBox corner in world space.
            # pos = mat.multVec(0,0,0) = world position of the cube's local origin.
            # center=false: local origin IS the corner.
            # center=true:  local origin IS the geometric centre; corner is at
            #               (-sx/2, -sy/2, -sz/2) in local space.
            if center_flag:
                if mat:
                    corner = mat.multVec(Vector(-sx / 2, -sy / 2, -sz / 2))
                else:
                    corner = Vector(-sx / 2, -sy / 2, -sz / 2)
            else:
                corner = pos  # pos already equals mat.multVec(0,0,0) = corner
            # Geometric centre (used by hull_cubes bbox logic)
            geom_center = corner + Vector(sx / 2, sy / 2, sz / 2)
            out.append({
                "type": "cube",
                "center": geom_center,  # geometric centre, always correct
                "corner": corner,       # Part.makeBox origin, always correct
                "size": [sx, sy, sz],
            })

        elif node.node_type == "cylinder":

            write_log("cylinder",f"params {node.params}")

            params = node.params

            if "h" not in params:
                return None
            h = float(params["h"])

            # --- Radius precedence (OpenSCAD rules) ---
            if "r" in params:
                r1 = r2 = float(params["r"])
            elif "r1" in params or "r2" in params:
                r1 = float(params.get("r1", 0))
                r2 = float(params.get("r2", 0))
            elif "d" in params:
                r1 = r2 = float(params["d"]) / 2.0
            elif "d1" in params or "d2" in params:
                r1 = float(params.get("d1", 0)) / 2.0
                r2 = float(params.get("d2", 0)) / 2.0
            else:
                return None

            if r1 < 0 or r2 < 0:
                return None

            # ---------------------------------------
            # Axis and base from transform
            # ---------------------------------------
            base = Vector(0, 0, 0)
            axis_vec = Vector(0, 0, 1)

            if mat:
                base = mat.multVec(base)
                axis_end = mat.multVec(Vector(0, 0, 1))
                axis_vec = axis_end - base

            if axis_vec.Length == 0:
                return None

            # ALWAYS convert to unit direction
            axis_vec = axis_vec / axis_vec.Length

            # ---------------------------------------
            # Center handling
            # ---------------------------------------
            center_flag = bool(params.get("center", False))

            if h < 0:
                h = abs(h)
                axis_vec = axis_vec * -1

            if center_flag:
                base = base - axis_vec * (h / 2.0)

            center = base + axis_vec * (h / 2.0)

            # ---------------------------------------
            # Store canonical representation
            # ---------------------------------------
            out.append({
                "type": "cylinder",   # keep unified primitive
                "base": base,         # start point
                "dir": axis_vec,      # UNIT direction
                "h": h,
                "r1": r1,
                "r2": r2,
                "center": center,
            })
    return out

def try_hull_dispatch(normalized_hull):
    types = {p["type"] for p in normalized_hull}
    write_log("Hull", f"Dispatch types={types}")
    write_log("Normalized ",normalized_hull)

    if len(types) == 1:
        if types == {'sphere'}:
            return hull_spheres(normalized_hull)
        elif types == {'cylinder'}:
            return hull_cylinders_cones(normalized_hull)
        elif types == {'cube'}:
            return hull_cubes(normalized_hull)
        else:
            _warn(f"hull of all-{types} not handled natively")
            return None
    elif types == {'cube', 'cylinder'}:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_mixed import hull_cylinders_and_cube
        return hull_cylinders_and_cube(normalized_hull)
    else:
        _warn(f"mixed-type hull not handled natively: {types}")
        return None
