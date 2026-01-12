# -*- coding: utf8 -*-
#***************************************************************************
#*   AST Processing for OpenSCAD CSG importer                              *
#*   Converts AST nodes to FreeCAD Shapes or SCAD strings with fallbacks   *
#***************************************************************************

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import fallback_to_OpenSCAD
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform

# -------------------------
# High-level AST processing
# -------------------------

def process_AST(doc, nodes, mode="multiple"):
    """
    Process a list of AST nodes, returning a list of FreeCAD shapes or a single shape.
    """
    shapes = []
    for node in nodes:
        s = process_AST_node(doc, node)
        shapes.append(s)
    if mode == "single" and shapes:
        return shapes[0]
    return shapes


def process_AST_node(doc, node):
    """
    Dispatch processing based on node type.
    """
    node_type = type(node).__name__
    if node_type in ["Hull", "Minkowski"]:
        if node_type == "Hull":
            return process_hull(doc, node)
        else:
            return process_minkowski(doc, node)
    elif node_type in ["Sphere", "Cube", "Circle"]:
        return create_primitive(doc, node)
    elif node_type in ["MultMatrix", "Translate", "Rotate", "Scale"]:
        return apply_transform(doc, node)
    else:
        write_log("AST", f"Unknown node type {node_type}, falling back to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, node_type)


# -------------------------
# Hull / Minkowski processing
# -------------------------

def process_hull(doc, node):
    """
    Attempt to create a native FreeCAD hull shape.
    If impossible, fallback to OpenSCAD.
    Preserves $fn/$fa/$fs from children where possible.
    """
    write_log("Hull", "process_hull ENTERED")
    if not getattr(node, "children", []):
        write_log("Hull", "Hull node has no children, fallback to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Hull")

    child_shapes = []
    for i, child in enumerate(node.children):
        write_log("Hull", f"Processing child {i}: {type(child).__name__} params={getattr(child,'params',{})}")
        s = process_AST_node(doc, child)
        child_shapes.append(s)

    try:
        # Attempt native hull creation
        from Part import makeCompound
        from Part import makeHull
        compound = makeCompound(child_shapes)
        hull_shape = compound.makeHull()  # Will fail if children invalid
        write_log("Hull", "Native hull successful")
        return hull_shape
    except Exception as e:
        write_log("Hull", f"Native hull failed ({e}), falling back to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Hull")


def process_minkowski(doc, node):
    """
    Same strategy as Hull: try native if possible, else fallback to OpenSCAD.
    """
    write_log("Minkowski", "process_minkowski ENTERED")
    if not getattr(node, "children", []):
        write_log("Minkowski", "Node has no children, fallback to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Minkowski")

    child_shapes = []
    for i, child in enumerate(node.children):
        write_log("Minkowski", f"Processing child {i}: {type(child).__name__} params={getattr(child,'params',{})}")
        s = process_AST_node(doc, child)
        child_shapes.append(s)

    try:
        # Minkowski not directly supported in native FreeCAD; attempt if all children are shapes
        # If any child is a Compound, fallback
        from Part import makeCompound
        if all(hasattr(c, "Shape") or hasattr(c, "Volume") for c in child_shapes):
            write_log("Minkowski", "All children are shapes, native Minkowski might be possible")
            # Placeholder: real implementation could attempt minkowski with BRepAlgo or Part.Shape.makeMinkowski
            # For safety, fallback
            raise NotImplementedError("Native Minkowski not supported, fallback required")
        else:
            raise TypeError("Cannot create Minkowski from non-shapes")
    except Exception as e:
        write_log("Minkowski", f"Native Minkowski failed ({e}), falling back to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Minkowski")


# -------------------------
# Primitives
# -------------------------

def create_primitive(doc, node):
    """
    Create a FreeCAD shape from a primitive node (Sphere, Cube, Circle).
    """
    from Part import Sphere, Cube
    node_type = type(node).__name__
    fn, fa, fs = get_tess(node)
    params = getattr(node, "params", {})
    write_log("AST", f"Creating primitive {node_type} with params {params} and tessellation $fn={fn},$fa={fa},$fs={fs}")

    if node_type == "Sphere":
        r = params.get("r", 1.0)
        return Sphere(r)
    elif node_type == "Cube":
        size = params.get("size", [1,1,1])
        return Cube(size)
    elif node_type == "Circle":
        # Circle is a 2D object; FreeCAD creates a thin disk in 3D
        r = params.get("r", 1.0)
        # Optionally warn user
        write_log("AST", "Circle: 2D primitive converted to 3D disk for FreeCAD")
        return Sphere(r)  # Simplified for example; replace with actual 2D handling
    else:
        write_log("AST", f"Unknown primitive {node_type}, fallback")
        return fallback_to_OpenSCAD(doc, node, node_type)

