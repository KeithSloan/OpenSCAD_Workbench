# ast_evaluator.py
# Evaluate AST nodes into FreeCAD shapes
# Handles special ops like hull/minkowski, can be extended

import FreeCAD
import Part

# --------------------------
# Configurable list of "special CSG operations"
# --------------------------
SPECIAL_CSG_OPS = ["hull", "minkowski"]  # extend this list in future

# --------------------------
# Main AST evaluation
# --------------------------
def evaluate_ast(node):
    """
    Convert an AST node into a FreeCAD Part.Shape.
    Handles normal operations, polyhedrons, and special ops.
    """
    if node is None:
        return None

    if hasattr(node, "name") and node.name in SPECIAL_CSG_OPS:
        return handle_special_op(node)
    
    if hasattr(node, "name"):
        op = node.name.lower()
        if op == "union":
            return fuse_shapes([evaluate_ast(c) for c in node.children])
        elif op == "difference":
            return cut_shapes([evaluate_ast(c) for c in node.children])
        elif op == "intersection":
            return intersect_shapes([evaluate_ast(c) for c in node.children])
        elif op == "polyhedron":
            return make_brep_polyhedron(node)
        else:
            return apply_transform(node)
    return None

# --------------------------
# Helpers for standard operations
# --------------------------
def fuse_shapes(shapes):
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.fuse(s)
    return result

def cut_shapes(shapes):
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.cut(s)
    return result

def intersect_shapes(shapes):
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.common(s)
    return result

def apply_transform(node):
    """
    Apply transformations (translate, rotate, scale) if present.
    For simplicity, returns the child shape unchanged here.
    """
    if node.children:
        return evaluate_ast(node.children[0])
    return None

# --------------------------
# Special CSG operations
# --------------------------
def handle_special_op(node):
    """
    Process a 'special' operation like hull or minkowski.
    Tries Brep conversion, otherwise falls back to OpenSCAD/STL.
    """
    if node.name == "hull":
        shape = make_brep_special(node)
        if shape:
            return shape
    elif node.name == "minkowski":
        shape = make_brep_special(node)
        if shape:
            return shape
    
    # Fallback: generate STL via OpenSCAD
    return openscad_fallback(node)

def make_brep_special(node):
    """
    Attempt to create a FreeCAD Brep for special operations.
    Returns None if not possible.
    """
    # TODO: implement detection for simple hull/minkowski that can be converted to Breps
    return None

def make_brep_polyhedron(node):
    """
    Convert polyhedron AST node to FreeCAD Part.Shape.
    """
    try:
        points = [FreeCAD.Vector(*p) for p in node.args[0]]  # expects node.args[0] = points list
        faces = node.args[1]  # faces list
        return Part.makePolyhedron(points, faces)
    except Exception as e:
        FreeCAD.Console.PrintError(f"Failed to create polyhedron: {e}\n")
        return None

def openscad_fallback(node):
    """
    Fallback for special operations that can't be converted to Brep.
    Calls OpenSCAD to generate STL and converts to mesh/shape.
    """
    FreeCAD.Console.PrintMessage(f"Fallback OpenSCAD for operation: {node.name}\n")
    # TODO: call OpenSCAD CLI, generate STL, read into FreeCAD
    return None

