import FreeCAD
import Part
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import process_ObjectsViaOpenSCADShape
from .hull_minkowski import try_hull, try_minkowski

import FreeCAD
import Part
from .hull_minkowski import try_hull, try_minkowski

def process_node(doc, node, stack=None, mode="single"):
    """
    Recursively process AST node to create FreeCAD shape(s)

    mode:
        "single" - collapse all nodes into one shape
        "objects" - create individual FreeCAD objects for each shape
    """
    stack = stack or []

    # Special handling for hull
    if node.node_type == "hull":
        shape = try_hull(stack)
        if shape:
            if mode == "objects":
                obj = doc.addObject("Part::Feature", "Hull")
                obj.Shape = shape
            return shape

    # Special handling for minkowski
    if node.node_type == "minkowski":
        shape = try_minkowski(stack)
        if shape:
            if mode == "objects":
                obj = doc.addObject("Part::Feature", "Minkowski")
                obj.Shape = shape
            return shape

    # Basic shapes
    shape = None
    if node.node_type == "cube":
        size = node.params.get("size", [1,1,1])
        center = node.params.get("center", False)
        shape = Part.makeBox(*size)
        if center:
            shape.translate(FreeCAD.Vector(-size[0]/2, -size[1]/2, -size[2]/2))

    elif node.node_type == "cylinder":
        r = node.params.get("r", 1)
        h = node.params.get("h", 1)
        center = node.params.get("center", False)
        shape = Part.makeCylinder(r, h)
        if center:
            shape.translate(FreeCAD.Vector(0,0,-h/2))

    # Boolean nodes
    elif node.node_type in ("union", "difference", "intersection"):
        child_shapes = [process_node(doc, c, stack, mode) for c in node.children]
        child_shapes = [s for s in child_shapes if s is not None]
        if child_shapes:
            shape = child_shapes[0]
            for s in child_shapes[1:]:
                if node.node_type == "union":
                    shape = shape.fuse(s)
                elif node.node_type == "difference":
                    shape = shape.cut(s)
                elif node.node_type == "intersection":
                    shape = shape.common(s)

    # Fallback
    if shape is None:
        shape = process_ObjectsViaOpenSCADShape(doc, node)

    # In "objects" mode, create individual FreeCAD objects
    if mode == "objects" and shape:
        obj_name = node.node_type.capitalize()
        obj = doc.addObject("Part::Feature", obj_name)
        obj.Shape = shape

    stack.append(shape)
    return shape


def process_AST(doc, ast_nodes, mode="single"):
    """
    Process AST nodes into FreeCAD shapes

    mode:
        "single"  → collapse into one FreeCAD object/shape
        "objects" → create one FreeCAD object per node
    """
    shapes = []
    stack = []

    for node in ast_nodes:
        shape = process_node(doc, node, stack, mode)
        if shape:
            shapes.append(shape)

    # In "single" mode, combine all shapes into one FreeCAD object
    if mode == "single" and shapes:
        combined = shapes[0]
        for s in shapes[1:]:
            combined = combined.fuse(s)

        obj = doc.addObject("Part::Feature", "SCAD_Object")
        obj.Shape = combined
        return [obj]

    return shapes


