import FreeCAD
import Part
import Mesh
import tempfile
import os

from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import process_ObjectsViaOpenSCADShape

from .ast_nodes import (
    Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Hull, Minkowski,
    Group, MultMatrix, Translate, Rotate, Scale
)
from .hull_minkowski import try_hull, try_minkowski


# =========================================================
# Utilities
# =========================================================

def fuse_all(shapes):
    """Fuse a list of shapes safely."""
    if not shapes:
        return None
    result = shapes[0]
    for s in shapes[1:]:
        result = result.fuse(s)
    return result


def scad_matrix_to_fc_matrix(m):
    """
    Convert OpenSCAD multmatrix (row-major) to FreeCAD Matrix
    """
    fc = FreeCAD.Matrix()

    fc.A11 = m[0][0]; fc.A12 = m[1][0]; fc.A13 = m[2][0]
    fc.A21 = m[0][1]; fc.A22 = m[1][1]; fc.A23 = m[2][1]
    fc.A31 = m[0][2]; fc.A32 = m[1][2]; fc.A33 = m[2][2]

    fc.A14 = m[0][3]
    fc.A24 = m[1][3]
    fc.A34 = m[2][3]

    return fc


def apply_multmatrix(shape, matrix):
    return shape.transformGeometry(scad_matrix_to_fc_matrix(matrix))


# =========================================================
# Fallback to OpenSCAD
# =========================================================

def fallback_to_OpenSCAD(doc, node, name):
    write_log("Info", f"Fallback to OpenSCAD STL for {name}")
    return process_ObjectsViaOpenSCADShape(doc, [node], name)


# =========================================================
# Hull / Minkowski
# =========================================================

def process_hull(doc, node):
    shape = try_hull(node.children)
    if shape:
        write_log("Info", "Hull converted to BRep")
        return shape
    return fallback_to_OpenSCAD(doc, node, "Hull")


def process_minkowski(doc, node):
    shape = try_minkowski(node.children)
    if shape:
        write_log("Info", "Minkowski converted to BRep")
        return shape
    return fallback_to_OpenSCAD(doc, node, "Minkowski")


# =========================================================
# Core AST processing
# =========================================================

def process_AST_node(doc, node):
    shapes = []

    # ---------------------------
    # Primitives
    # ---------------------------
    if isinstance(node, Cube):
        size = node.params.get("size", [1, 1, 1])
        center = node.params.get("center", False)
        s = Part.makeBox(*size)
        if center:
            s.translate(Vector(-size[0]/2, -size[1]/2, -size[2]/2))
        write_log("Info", f"Created cube {size}")
        return s

    if isinstance(node, Sphere):
        r = node.params.get("r", 1)
        write_log("Info", f"Created sphere r={r}")
        return Part.makeSphere(r)

    if isinstance(node, Cylinder):
        r = node.params.get("r", 1)
        h = node.params.get("h", 1)
        center = node.params.get("center", False)
        s = Part.makeCylinder(r, h)
        if center:
            s.translate(Vector(0, 0, -h/2))
        write_log("Info", f"Created cylinder r={r}, h={h}")
        return s

    # ---------------------------
    # Boolean operations
    # ---------------------------
    if isinstance(node, (Union, Difference, Intersection)):
        children = [process_AST_node(doc, c) for c in node.children]
        children = [s for s in children if s]

        if not children:
            return None

        result = children[0]
        for s in children[1:]:
            if isinstance(node, Union):
                result = result.fuse(s)
            elif isinstance(node, Difference):
                result = result.cut(s)
            elif isinstance(node, Intersection):
                result = result.common(s)

        write_log("Info", f"Processed {node.node_type} with {len(children)} children")
        return result

    # ---------------------------
    # Hull / Minkowski
    # ---------------------------
    if isinstance(node, Hull):
        return process_hull(doc, node)

    if isinstance(node, Minkowski):
        return process_minkowski(doc, node)

    # ---------------------------
    # Group
    # ---------------------------
    if isinstance(node, Group):
        shapes = [process_AST_node(doc, c) for c in node.children]
        shapes = [s for s in shapes if s]
        return fuse_all(shapes)

    # ---------------------------
    # Transforms (apply to ALL children)
    # ---------------------------
    if isinstance(node, (Translate, Rotate, Scale, MultMatrix)):
        child_shapes = [process_AST_node(doc, c) for c in node.children]
        child_shapes = [s for s in child_shapes if s]

        if not child_shapes:
            return None

        for i, s in enumerate(child_shapes):
            if isinstance(node, Translate):
                v = node.params.get("vector", [0, 0, 0])
                s.translate(Vector(*v))

            elif isinstance(node, Rotate):
                axis = node.params.get("vector", [0, 0, 1])
                angle = node.params.get("angle", 0)
                s.rotate(Vector(0, 0, 0), Vector(*axis), angle)

            elif isinstance(node, Scale):
                v = node.params.get("vector", [1, 1, 1])
                s.scale(v[0], v[1], v[2])

            elif isinstance(node, MultMatrix):
                m = node.params.get("matrix")
                if not m:
                    write_log("Warning", "multmatrix missing matrix")
                    return fallback_to_OpenSCAD(doc, node, "MultMatrix")
                s = apply_multmatrix(s, m)
                child_shapes[i] = s

        write_log("Info", f"Applied {node.node_type} to {len(child_shapes)} children")
        return fuse_all(child_shapes)

    # ---------------------------
    # Unknown → legacy fallback
    # ---------------------------
    write_log("Info", f"Fallback legacy handling for {node.node_type}")
    return fallback_to_OpenSCAD(doc, node, node.node_type)


# =========================================================
# Top-level AST entry
# =========================================================

def process_AST(doc, ast_nodes, mode="single"):
    shapes = []

    for node in ast_nodes:
        s = process_AST_node(doc, node)
        if s:
            shapes.append((node, s))

    if not shapes:
        return []

    if mode == "objects":
        objs = []
        for node, s in shapes:
            name = node.node_type.capitalize()
            obj = doc.addObject("Part::Feature", name)
            obj.Shape = s
            objs.append(obj)
        return objs

    # default: single
    combined = fuse_all([s for _, s in shapes])
    obj = doc.addObject("Part::Feature", "SCAD_Object")
    obj.Shape = combined
    return [obj]

