# -*- coding: utf8 -*-
#****************************************************************************
#*   AST Processing for OpenSCAD CSG importer                               *
#*   Converts AST nodes to FreeCAD Part.Shapes                              *
#****************************************************************************

import os
import subprocess
import tempfile
import FreeCAD
import Part
import Mesh

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import apply_transform

# ============================================================
# Errors
# ============================================================

BaseError = FreeCAD.Base.FreeCADError

class OpenSCADError(BaseError):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

# ============================================================
# OpenSCAD fallback helpers (Hull / Minkowski)
# ============================================================

def generate_stl_from_scad(scad_str, timeout=60):
    tmpdir = tempfile.mkdtemp()
    scad_file = os.path.join(tmpdir, "fallback.scad")
    stl_file = os.path.join(tmpdir, "fallback.stl")

    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
    openscad_exe = prefs.GetString("openscadexecutable", "")

    if not openscad_exe or not os.path.isfile(openscad_exe):
        raise FileNotFoundError("OpenSCAD executable not configured")

    with open(scad_file, "w") as f:
        f.write(scad_str)

    cmd = [openscad_exe, "-o", stl_file, scad_file]
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)

    os.remove(scad_file)
    return stl_file


def stl_to_shape(stl_path, tolerance=0.05):
    mesh = Mesh.Mesh(stl_path)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tolerance)
    return shape


def fallback_to_OpenSCAD(node, op_name):
    write_log(op_name, f"{op_name} fallback → OpenSCAD")
    scad = flatten_ast_node(node)
    stl = generate_stl_from_scad(scad)
    return stl_to_shape(stl)

# ============================================================
# AST entry points
# ============================================================

def process_AST(nodes, mode="multiple"):
    shapes = []

    for node in nodes:
        s = process_AST_node(node)
        if s:
            shapes.append(s)
        write_log("AST", f"Processed {type(node).__name__} → {s}")

    if mode == "single":
        return shapes[0] if shapes else None

    return shapes


def process_AST_node(node):
    """
    Dispatch AST node → Part.Shape
    NOTE:
      - Transform nodes do NOT create geometry
      - They evaluate children, then apply the transform
    """
    node_type = type(node).__name__

    # --- Primitives
    if node_type in ("Sphere", "Cube", "Cylinder", "Circle"):
        return create_primitive(node)

    # --- Boolean ops
    if node_type in ("Union", "Difference", "Intersection"):
        return create_boolean(node)

    # --- Transforms
    if node_type in ("Translate", "Rotate", "Scale", "MultMatrix"):
        return process_transform_node(node)

    # --- Hull / Minkowski
    if node_type == "Hull":
        return fallback_to_OpenSCAD(node, "Hull")

    if node_type == "Minkowski":
        return fallback_to_OpenSCAD(node, "Minkowski")

    write_log("AST", f"Unknown node {node_type}, ignored")
    return None

# ============================================================
# Transform handling (FIXES YOUR CRASH)
# ============================================================

def process_transform_node(node):
    shapes = []

    for child in getattr(node, "children", []):
        s = process_AST_node(child)
        if s:
            shapes.append(apply_transform(s, node))

    if not shapes:
        return None

    if len(shapes) == 1:
        return shapes[0]

    # OpenSCAD semantics: transformed siblings are unioned
    result = shapes[0]
    for s in shapes[1:]:
        result = result.fuse(s)
    return result

# ============================================================
# Boolean ops
# ============================================================

def create_boolean(node):
    node_type = type(node).__name__
    shapes = []

    for child in node.children:
        s = process_AST_node(child)
        if s:
            shapes.append(s)

    if not shapes:
        return None

    result = shapes[0]

    if node_type == "Union":
        for s in shapes[1:]:
            result = result.fuse(s)

    elif node_type == "Difference":
        for s in shapes[1:]:
            result = result.cut(s)

    elif node_type == "Intersection":
        for s in shapes[1:]:
            result = result.common(s)

    return result

# ============================================================
# Primitives
# ============================================================

def to_tuple3(v):
    if isinstance(v, (int, float)):
        return (v, v, v)
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return tuple(v)
    raise TypeError("Expected scalar or 3-element vector")


def create_primitive(node):
    node_type = type(node).__name__
    p = getattr(node, "params", {})

    if node_type == "Sphere":
        return Part.makeSphere(p.get("r", 1.0))

    if node_type == "Cube":
        size = to_tuple3(p.get("size", [1, 1, 1]))
        center = p.get("center", False)
        box = Part.makeBox(*size)
        if center:
            box.translate(FreeCAD.Vector(-size[0]/2, -size[1]/2, -size[2]/2))
        return box

    if node_type == "Cylinder":
        return Part.makeCylinder(p.get("r", 1.0), p.get("h", 1.0))

    if node_type == "Circle":
        return Part.makeCircle(p.get("r", 1.0))

    return None

# ============================================================
# SCAD flattening (Hull / Minkowski fallback)
# ============================================================

def flatten_ast_node(node, indent=0):
    ind = " " * indent
    t = node.node_type
    p = node.params
    code = ""

    if t in ("hull", "minkowski", "union", "difference", "intersection"):
        code += f"{ind}{t}() {{\n"
        for c in node.children:
            code += flatten_ast_node(c, indent + 4)
        code += f"{ind}}}\n"

    elif t == "cube":
        code += f"{ind}cube(size={p.get('size')}, center={str(p.get('center', False)).lower()});\n"

    elif t == "sphere":
        code += f"{ind}sphere(r={p.get('r',1)});\n"

    elif t == "multmatrix":
        code += f"{ind}multmatrix({p.get('matrix')}) {{\n"
        for c in node.children:
            code += flatten_ast_node(c, indent + 4)
        code += f"{ind}}}\n"

    return code

