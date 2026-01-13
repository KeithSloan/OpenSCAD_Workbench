# -*- coding: utf-8 -*-
"""
OpenSCAD AST helpers

This module MUST be safe:
- Never throw during fallback
- Provide all symbols expected by processAST
"""

from __future__ import annotations

import FreeCAD
import Part
import math

# ------------------------------------------------------------
# Logging (safe)
# ------------------------------------------------------------

try:
    from freecad.OpenSCAD_Ext.utils.log import write_log
except Exception:
    def write_log(level, msg):
        pass


# ------------------------------------------------------------
# Public API (IMPORTANT)
# ------------------------------------------------------------

__all__ = [
    "ast_to_scad_string",
    "class_ast_to_scad_string",
    "apply_transform",
    "get_tess",
]


# ============================================================
# Tessellation helper (EXPECTED BY processAST)
# ============================================================

def identity_matrix_4x4():
    return [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ]

def get_tess(obj):
    """
    Return a Part.Shape for an object or shape.

    processAST expects this to exist.
    Be conservative: just return a Shape or None.
    """
    if obj is None:
        return None

    # DocumentObject → Shape
    if hasattr(obj, "Shape"):
        return obj.Shape

    # Already a shape
    if isinstance(obj, Part.Shape):
        return obj

    write_log("Info", f"get_tess: unsupported type {type(obj)}")
    return None


# ============================================================
# Transform application helper (EXPECTED BY processAST)
# ============================================================

def apply_transform(shape, transform):
    """
    Apply transform node to a Part.Shape.

    For now:
    - Accepts MultMatrix / Translate / Rotate / Scale nodes
    - If unsupported, returns shape unchanged
    - NEVER throws
    """
    if shape is None or transform is None:
        return shape

    try:
        # ---- class-based AST
        if hasattr(transform, "node_type"):
            t = transform.node_type
            p = getattr(transform, "params", {}) or {}

            if t == "translate":
                v = p.get("vector", p.get("v", [0, 0, 0]))
                return shape.copy().translate(FreeCAD.Vector(*v))

            if t == "scale":
                v = p.get("vector", p.get("v", [1, 1, 1]))
                m = FreeCAD.Matrix()
                m.A11, m.A22, m.A33 = v
                return shape.copy().transformGeometry(m)

            if t == "rotate":
                a = p.get("angle", p.get("a", 0))
                v = p.get("vector", p.get("v", [0, 0, 1]))
                rot = FreeCAD.Rotation(FreeCAD.Vector(*v), a)
                return shape.copy().rotate(FreeCAD.Vector(0, 0, 0), rot.Axis, rot.Angle)

            if t == "multmatrix":
                m = p.get("matrix", p.get("m"))
                if m:
                    mat = FreeCAD.Matrix(*sum(m, []))
                    return shape.copy().transformGeometry(mat)

        # ---- dict-based AST
        if isinstance(transform, dict):
            t = transform.get("type")

            if t == "translate":
                v = transform.get("v", [0, 0, 0])
                return shape.copy().translate(FreeCAD.Vector(*v))

            if t == "scale":
                v = transform.get("v", [1, 1, 1])
                m = FreeCAD.Matrix()
                m.A11, m.A22, m.A33 = v
                return shape.copy().transformGeometry(m)

            if t == "rotate":
                a = transform.get("a", 0)
                v = transform.get("v", [0, 0, 1])
                rot = FreeCAD.Rotation(FreeCAD.Vector(*v), a)
                return shape.copy().rotate(FreeCAD.Vector(0, 0, 0), rot.Axis, rot.Angle)

            if t == "multmatrix":
                m = transform.get("m")
                if m:
                    mat = FreeCAD.Matrix(*sum(m, []))
                    return shape.copy().transformGeometry(mat)

    except Exception as e:
        write_log("Info", f"apply_transform failed: {e}")

    # Fallback: return unchanged
    return shape


# ============================================================
# Legacy dict-based AST → SCAD
# ============================================================

def ast_to_scad_string(node, indent=0, top_level=False):
    pad = "  " * indent

    if node is None:
        return ""

    if isinstance(node, (list, tuple)):
        return "\n".join(ast_to_scad_string(n, indent) for n in node)

    if isinstance(node, dict):
        t = node.get("type")

        if t == "sphere":
            return f"{pad}sphere(r={node.get('r', 1)});"

        if t == "cube":
            return f"{pad}cube(size={node.get('size',[1,1,1])}, center={node.get('center',False)});"

        if t == "cylinder":
            return (
                f"{pad}cylinder(h={node.get('h',1)}, "
                f"r1={node.get('r1',node.get('r',1))}, "
                f"r2={node.get('r2',node.get('r',1))}, "
                f"center={node.get('center',False)});"
            )

        if t in ("union", "difference", "intersection", "hull"):
            body = "\n".join(ast_to_scad_string(c, indent + 1)
                             for c in node.get("children", []))
            return f"{pad}{t}() {{\n{body}\n{pad}}}"

        if t == "multmatrix":
            body = "\n".join(ast_to_scad_string(c, indent + 1)
                             for c in node.get("children", []))
            return f"{pad}multmatrix({node.get('m')}) {{\n{body}\n{pad}}}"

        write_log("Info", f"Fallback serializer: unsupported dict node {t}")
        return f"{pad}// unsupported node {t}"

    return f"{pad}// unsupported node"


# ============================================================
# Class-based AST → SCAD (USED BY fallback)
# ============================================================

def class_ast_to_scad_string(node, indent=0, top_level=False):
    pad = "  " * indent

    if node is None:
        return ""

    ntype = getattr(node, "node_type", None)
    params = getattr(node, "params", {}) or {}
    children = getattr(node, "children", []) or []

    if ntype == "sphere":
        return f"{pad}sphere(r={params.get('r',1)});"

    if ntype in ("union", "difference", "intersection", "hull"):
        body = "\n".join(class_ast_to_scad_string(c, indent + 1)
                         for c in children)
        return f"{pad}{ntype}() {{\n{body}\n{pad}}}"

    if ntype == "multmatrix":
        m = params.get("m") or params.get("matrix")

        if not m:
            write_log("Info", "multmatrix missing matrix → using identity")
            m = identity_matrix_4x4()

        body = "\n".join(
            class_ast_to_scad_string(c, indent + 1)
            for c in children
            )

        return (
            f"{pad}multmatrix({m}) {{\n"
            f"{body}\n"
            f"{pad}}}"
        )

    write_log("Info", f"Fallback serializer: unsupported node {ntype}")
    return f"{pad}// unsupported node {ntype}"
