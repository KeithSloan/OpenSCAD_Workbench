# -*- coding: utf8 -*-
#***************************************************************************
#*   AST Processing for OpenSCAD CSG importer                              *
#*   Converts AST nodes to FreeCAD Shapes or SCAD strings with fallbacks   *
#***************************************************************************

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.core.OpenSCADUtils import fallback_to_OpenSCAD
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform
from freecad.OpenSCAD_Ext.core.OpenSCADFallback import fallback_to_OpenSCAD
#from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscadstring_to_file
#    import_stl_as_shape,
#)


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
    Process a Hull AST node.
    Tries to create native FreeCAD Hull if possible.
    If not possible, returns fallback_to_OpenSCAD() dict.
    """
    write_log("Hull", "process_hull ENTERED")
    children_shapes = []

    for child in node.children:
        s = process_AST_node(doc, child)
        # If child is already a fallback, just keep as-is
        if isinstance(s, dict) and s.get("type") == "openscad_fallback":
            return fallback_to_OpenSCAD(doc, node, "Hull")
        children_shapes.append(s)

    try:
        # Attempt native Hull creation (BRep)
        compound = doc.addObject("Part::Compound", "HullCompound")
        compound.Links = children_shapes
        hull_shape = compound.Shape.makeHull()
        return hull_shape
    except Exception as e:
        write_log("Hull", f"Native hull failed ({e}), falling back to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Hull")


def process_minkowski(doc, node):
    """
    Process a Minkowski AST node.
    Tries native FreeCAD Minkowski if possible.
    If not possible, returns fallback_to_OpenSCAD() dict.
    """
    write_log("Minkowski", "process_minkowski ENTERED")
    children_shapes = []

    for child in node.children:
        s = process_AST_node(doc, child)
        if isinstance(s, dict) and s.get("type") == "openscad_fallback":
            return fallback_to_OpenSCAD(doc, node, "Minkowski")
        children_shapes.append(s)

    try:
        # Attempt native Minkowski creation (Part.makeMinkowski)
        base = children_shapes[0]
        for s in children_shapes[1:]:
            base = base.makeMinkowski(s)
        return base
    except Exception as e:
        write_log("Minkowski", f"Native Minkowski failed ({e}), falling back to OpenSCAD")
        return fallback_to_OpenSCAD(doc, node, "Minkowski")



# -------------------------
# Primitives
# -------------------------
import FreeCAD as App
import Part

def create_primitive(doc, node):
    """
    Create a native FreeCAD primitive shape from an AST node.
    Supports Sphere, Cube, Cylinder, Circle.
    Returns a FreeCAD Shape object.
    """
    node_type = type(node).__name__
    params = getattr(node, "params", {})

    if node_type == "Sphere":
        r = params.get("r", 1.0)
        shape = Part.makeSphere(r)
        App.Console.PrintMessage(f"[Info] Created sphere r={r}\n")
        return shape

    elif node_type == "Cube":
        size = params.get("size", [1.0, 1.0, 1.0])
        shape = Part.makeBox(size[0], size[1], size[2])
        App.Console.PrintMessage(f"[Info] Created cube size={size}\n")
        return shape

    elif node_type == "Cylinder":
        r = params.get("r", 1.0)
        h = params.get("h", 1.0)
        shape = Part.makeCylinder(r, h)
        App.Console.PrintMessage(f"[Info] Created cylinder r={r} h={h}\n")
        return shape

    elif node_type == "Circle":
        r = params.get("r", 1.0)
        # 2D wire
        shape = Part.makeCircle(r)
        App.Console.PrintMessage(f"[Info] Created circle r={r}\n")
        return shape

    else:
        App.Console.PrintMessage(f"[Warning] Unknown primitive: {node_type}, falling back to OpenSCAD\n")
        # Return fallback dict if unknown primitive
        from freecad.OpenSCAD_Ext.core.fallback_to_OpenSCAD import fallback_to_OpenSCAD
        return fallback_to_OpenSCAD(doc, node, f"Unknown primitive: {node_type}")
