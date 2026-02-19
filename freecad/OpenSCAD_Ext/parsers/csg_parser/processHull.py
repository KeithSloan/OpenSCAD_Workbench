from FreeCAD import Vector, Matrix
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
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
        write_log("Hull", "not_handled: hull")
        return None


    geo = normalize_primitives(primitives, matrices)
    write_log("Normalized",f"primatives")
    write_log("Normlised",f"Geo {geo}")
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
            print(f"type {child.node_type} params {child.params} csg_params {child.csg_params}")
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

    write_log("Number of types ", len(types))

    if len(types) == 1:
        if types == {'sphere'}:
            return hull_spheres(normalized_hull)

        elif types == {'cylinder'}:
            return hull_cylinders_cones(normalized_hull)

    write_log("Number of Types", len(types))
    return None
