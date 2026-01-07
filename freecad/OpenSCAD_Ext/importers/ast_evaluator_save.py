# -*- coding: utf-8 -*-
# AST → FreeCAD CSG Importer / Evaluator
# Handles groups, unions, differences, polyhedrons, hull/minkowski with BREP fallback

import FreeCAD, Part, Mesh

# -------------------------
# Configuration
# -------------------------

SPECIAL_CSG_OPS = ["hull", "minkowski"]  # extendable in future

# -------------------------
# Helpers
# -------------------------

def is_simple_shape(shape):
    """Heuristic: small Part.Shape is simple enough for BREP hull/minkowski."""
    if not shape:
        return False
    if hasattr(shape, "Solids") and len(shape.Solids) <= 1:
        return True
    if hasattr(shape, "Faces") and len(shape.Faces) <= 12:
        return True
    return False

def make_brep_special(opname, shapes):
    """
    Try to create hull/minkowski using FreeCAD native BREP.
    Returns Part.Shape or None if impossible.
    """
    shapes = [s for s in shapes if s]
    if not shapes:
        return None

    try:
        if opname == "hull":
            compound = Part.Compound(shapes)
            hull = compound.makeHull()
            return hull

        elif opname == "minkowski":
            # naive BREP fallback: fuse solids
            result = shapes[0]
            for s in shapes[1:]:
                result = result.fuse(s)
            return result

    except Exception as e:
        FreeCAD.Console.PrintError(f"BREP {opname} failed: {e}\n")
        return None

    FreeCAD.Console.PrintMessage(f"Unknown special op {opname}\n")
    return None

def openscad_fallback(node):
    """
    Generate STL via OpenSCAD for a node, return FreeCAD Shape.
    """
    from OpenSCADUtils import generate_stl_from_node  # you provide
    stl_path = generate_stl_from_node(node)
    mesh_obj = FreeCAD.ActiveDocument.addObject("Mesh::Feature", f"Fallback_{node.name}")
    mesh_obj.Mesh = Mesh.Mesh(stl_path)
    return mesh_obj.Shape

def fuse_shapes(shapes):
    """Fuse multiple Part.Shape objects into a single shape."""
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]
    result = shapes[0]
    for s in shapes[1:]:
        result = result.fuse(s)
    return result

def cut_shapes(shapes):
    """Difference of two shapes, naive for more than two."""
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.cut(s)
    return result

def intersect_shapes(shapes):
    """Intersection of multiple shapes."""
    shapes = [s for s in shapes if s]
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.common(s)
    return result

# -------------------------
# AST evaluator
# -------------------------

def evaluate_ast(node):
    """
    Recursively convert AST Node to FreeCAD Part.Shape.
    Node is an OpNode, RawStmt, Polyhedron, ModuleCall, etc.
    """
    if node is None:
        return None

    # -------------------------
    # Polyhedron: create Part.Shape
    # -------------------------
    if node.name.lower() == "polyhedron":
        points = getattr(node, "points", [])
        faces = getattr(node, "faces", [])
        if not points or not faces:
            return None
        try:
            return Part.makeSolid(Part.makeShell([
                Part.makeFace(Part.Vertex(*[points[i] for i in face])) 
                for face in faces
            ]))
        except Exception:
            # fallback: Part.makePolygon for testing
            return Part.makePolygon([Part.Vector(*p) for p in points])

    # -------------------------
    # Special operations: hull/minkowski
    # -------------------------
    if node.name.lower() in SPECIAL_CSG_OPS:
        child_shapes = [evaluate_ast(c) for c in node.children]
        # try BREP first
        if all(is_simple_shape(s) for s in child_shapes):
            shape = make_brep_special(node.name.lower(), child_shapes)
            if shape:
                return shape
        # fallback
        return openscad_fallback(node)

    # -------------------------
    # Boolean ops: union, difference, intersection
    # -------------------------
    if node.name.lower() == "union":
        shapes = [evaluate_ast(c) for c in node.children]
        return fuse_shapes(shapes)

    if node.name.lower() == "difference":
        shapes = [evaluate_ast(c) for c in node.children]
        return cut_shapes(shapes)

    if node.name.lower() == "intersection":
        shapes = [evaluate_ast(c) for c in node.children]
        return intersect_shapes(shapes)

    # -------------------------
    # Group: fuse children if more than 1
    # -------------------------
    if node.name.lower() == "group":
        shapes = [evaluate_ast(c) for c in node.children]
        shapes = [s for s in shapes if s]
        if not shapes:
            return None
        if len(shapes) == 1:
            return shapes[0]
        return fuse_shapes(shapes)

    # -------------------------
    # Transformations: translate, rotate, scale
    # -------------------------
    if node.name.lower() in ("translate", "rotate", "scale"):
        if not node.children:
            return None
        shape = evaluate_ast(node.children[0])
        if shape is None:
            return None
        # get first argument as vector
        vec = node.args[0] if node.args else [0,0,0]
        v = FreeCAD.Vector(*vec)
        if node.name.lower() == "translate":
            shape.translate(v)
        elif node.name.lower() == "scale":
            shape.scale(v)
        elif node.name.lower() == "rotate":
            # rotation vector in degrees
            shape.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(*v), 0)
        return shape

    # -------------------------
    # Fallback: RawStmt or unknown
    # -------------------------
    return openscad_fallback(node)

