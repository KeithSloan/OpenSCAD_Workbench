import FreeCAD
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

def is_ast_sphere(node):
    return node.node_type == "sphere"

def get_ast_radius(node):
    return node.params.get("r", 1)

def is_ast_cylinder(node):
    return node.node_type == "cylinder"


def get_ast_cylinder_params(node):
    params = node.params

    # ---- Radius ----
    if "r" in params:
        r = params["r"]
    elif "r1" in params and "r2" in params:
        if params["r1"] != params["r2"]:
            return None  # cone not supported yet
        r = params["r1"]
    else:
        return None

    # ---- Height ----
    if "h" not in params:
        return None

    h = params["h"]

    # ---- Placement / Transform ----
    # Assuming node.Shape exists and has Placement
    try:
        placement = node.Shape.Placement
        origin = placement.Base
        axis = placement.Rotation.multVec(Vector(0, 0, 1))
        axis.normalize()
    except Exception:
        # Fallback: assume default orientation
        origin = Vector(0, 0, 0)
        axis = Vector(0, 0, 1)

    # ---- Center handling ----
    center = str(params.get("center", "false")).lower() == "true"

    if center:
        base = origin - axis * (h / 2)
    else:
        base = origin

    return r, axis, base, h


def minkowski_shape_with_cylinder(shapeA, ast_cylinder):
    """
    Approximate a Minkowski of shapeA with a cylinder.
    Only fillets edges; skips vertex rounding to avoid errors.
    """
    if not shapeA or shapeA.ShapeType != "Solid":
        write_log("Minkowski","ShapeA is not a solid\n")
        return shapeA

    # Extract cylinder radius
    radius = getattr(ast_cylinder, "params", {}).get("r", 1)

    # Copy shape
    new_shape = shapeA.copy()

    # Apply fillets to edges
    try:
        edge_list = new_shape.Edges
        if edge_list:
            new_shape = new_shape.makeFillet(radius, edge_list)
    except Exception as e:
        write_log("Minkowsk","Edge fillet failed: {e}\n")

    return new_shape
