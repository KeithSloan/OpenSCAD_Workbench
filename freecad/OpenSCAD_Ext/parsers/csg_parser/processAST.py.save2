# -*- coding: utf8 -*-
#****************************************************************************
#*   AST Processing for OpenSCAD CSG importer                               *
#*   Converts AST nodes to FreeCAD Shapes or SCAD strings with fallbacks    *
#*                                                                          *
#*      Returns Shaoe                                                       *
#****************************************************************************

import os
import subprocess
import tempfile
import FreeCAD 

#from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform
import Part
import Mesh

# -----------------------------
# Utility functions
# -----------------------------

BaseError = FreeCAD.Base.FreeCADError

class OpenSCADError(BaseError):
    def __init__(self,value):
        self.value= value
    #def __repr__(self):
    #    return self.msg
    def __str__(self):
        return repr(self.value)


def generate_stl_from_scad(scad_str, check_syntax=False, timeout=60):
    """
    Write the SCAD string to a temp file, generate STL via OpenSCAD CLI.
    Returns path to STL file.
    """
    write_log("AST",f"generate stl from scad {scad_str}")
    tmpdir = tempfile.mkdtemp()
    scad_file = os.path.join(tmpdir, "fallback.scad")
    stl_file = os.path.join(tmpdir, "fallback.stl")
    # --- get OpenSCAD executable from FreeCAD preferences ---
    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
    openscad_exe = prefs.GetString('openscadexecutable', "")

    if not openscad_exe or not os.path.isfile(openscad_exe):
        raise FileNotFoundError(
            "OpenSCAD executable not found. Set 'openscadexecutable' under Preferences → OpenSCAD."
        )

    with open(scad_file, "w") as f:
        f.write(scad_str)

    # --- build and run OpenSCAD command ---
    cmd = [openscad_exe, "-o", stl_file, scad_file]
    if check_syntax:
        cmd.append("-q")

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.remove(scad_file)
        raise OpenSCADError(f"OpenSCAD call timed out after {timeout} seconds")
    except subprocess.CalledProcessError as e:
        os.remove(scad_file)
        raise OpenSCADError(e.stderr.decode())

    # --- clean up temporary SCAD file and return output ---
    os.remove(scad_file)
    write_log("AST_Hull:Minkowski", f"Calling OpenSCAD CLI for fallback STL: {stl_file}")
    return stl_file


def stl_to_shape(stl_path, tolerance=0.05):
    """
    Import STL into FreeCAD and convert to Part.Shape
    """
    write_log("AST_Hull:Minkowski", f"Importing STL and converting to Part.Shape: {stl_path}")
    mesh_obj = Mesh.Mesh(stl_path)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh_obj.Topology, tolerance)
    write_log("AST",f"stl to Shape {shape}")
    return shape


def fallback_to_OpenSCAD(node, operation_type="Hull"):
    """
    Fallback: generate STL via OpenSCAD, import to FreeCAD
    """
    write_log(operation_type, f"{operation_type} could not be processed natively — fallback to OpenSCAD")
    scad_str = flatten_ast_node(node, indent=4)
    stl_file = generate_stl_from_scad(scad_str)
    shape = stl_to_shape(stl_file)
    write_log("AST",f"OpenSCAD returned Shape {shape}")
    return shape
    

# -------------------------
# High-level AST processing
# -------------------------

def process_AST(nodes, mode="multiple"):
    """
    Process a list of AST nodes, returning a list of FreeCAD shapes or a single Shape.
    Booleans only work on Shapes
    Object Booleans would need specfic Pary::FeaturePythons
    """
    shapes = []
    for node in nodes:
        s = process_AST_node(node)
        if s is None:
            pass
        elif isinstance(s, (list, tuple)):
            shapes.extend(s)
        else:
            shapes.append(s)
        write_log("AST",f"process AST Node {node} returned Shape {s}")
    if mode == "single" and shapes:
        return shapes[0]
    return shapes


def process_AST_node(node):
    """
    Dispatch processing based on node type
    Should always return a Shape
    """
    node_type = type(node).__name__
    if node_type in ["Hull", "Minkowski"]:
        if node_type == "Hull":
            return process_hull(node)
        else:
            return process_minkowski(node)
    elif node_type in ["Sphere", "Cube", "Circle"]:
        return create_primitive(node)
    elif node_type in ["MultMatrix", "Translate", "Rotate", "Scale"]:
        return apply_transform(node)
    elif node_type in ["Union",  "Difference", "Intersection"]:
        return create_boolean(node)
    else:
        write_log("AST", f"Unknown node type {node_type}, falling back to OpenSCAD")
        return fallback_to_OpenSCAD(node, node_type)


# -------------------------------------------------------
# flatten ast used for recreating hull/minkowski requests
# to be passed to OpenSCAD
# -------------------------------------------------------

def flatten_ast_node(node, indent=0):
    ind = " " * indent
    code = ""
    if node.node_type == "hull":
        code += f"{ind}hull() {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"
    elif node.node_type == "minkowski":
        code += f"{ind}minkowski() {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"
    elif node.node_type == "cube":
        size = node.params.get("size", 1)
        center = node.params.get("center", False)

        if isinstance(size, (int, float)):
            size_str = f"[{size},{size},{size}]"
        else:
            size_str = str(size)

        code += f"{ind}cube(size={size_str}, center={str(center).lower()});\n"

    elif node.node_type == "sphere":
        r = node.params.get("r", 1)
        code += f"{ind}sphere(r={r});\n"

    elif node.node_type == "multmatrix":
        matrix = node.params.get("matrix", [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        code += f"{ind}multmatrix({matrix}) {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"

    elif node.node_type == "union":
        code += f"{ind}union() {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"

    elif node.node_type == "difference":
        code += f"{ind}difference() {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"

    elif node.node_type == "intersection":
        code += f"{ind}intersection() {{\n"
        for child in node.children:
            code += flatten_ast_node(child, indent + 4)
        code += f"{ind}}}\n"

    # ... handle other primitive node types like cube, cylinder, etc.
    else:
        write_log(
            "flatten_ast_node",
            f"Unhandled node type: {node.node_type} — subtree will be lost"
            )

    return code


# -----------------------------
# Hull
# -----------------------------

def try_hull(node):
    """
    Attempt to process a Hull AST node natively.
    Returns: Part.Shape if successful, else None
    """
    write_log("Hull", ">>> try_hull ENTERED")
    write_log("Hull", f"Node type: {getattr(node, 'node_type', 'unknown')}")
    write_log("Hull", f"Children count: {len(getattr(node, 'children', []))}")

    for i, child in enumerate(getattr(node, "children", [])):
        write_log("Hull", f"Child {i} type: {getattr(child, 'node_type', 'unknown')} params: {getattr(child, 'params', None)}")

    # TODO: implement native FreeCAD hull creation
    return None


def process_hull(node):
    """
    Process a Hull AST node.
    Tries native FreeCAD hull; if not possible, fallback to OpenSCAD.
    """
    write_log("Hull", "process_hull ENTERED")
    hull_shape = try_hull(node)
    if hull_shape:
        write_log("Hull", "Hull processed natively")
        return hull_shape

    return fallback_to_OpenSCAD(node, "Hull")


# -----------------------------
# Minkowski
# -----------------------------

def try_minkowski(node):
    """
    Attempt to process a Minkowski AST node natively.
    Returns: Part.Shape if successful, else None
    """
    write_log("Minkowski", ">>> try_minkowski ENTERED")
    write_log("Minkowski", f"Node type: {getattr(node, 'node_type', 'unknown')}")
    write_log("Minkowski", f"Children count: {len(getattr(node, 'children', []))}")

    for i, child in enumerate(getattr(node, "children", [])):
        write_log("Minkowski", f"Child {i} type: {getattr(child, 'node_type', 'unknown')} params: {getattr(child, 'params', None)}")

    # TODO: implement native FreeCAD Minkowski creation
    return None


def process_minkowski(node):
    """
    Process a Minkowski AST node.
    Tries native FreeCAD Minkowski; if not possible, fallback to OpenSCAD.
    """
    write_log("Minkowski", "process_minkowski ENTERED")
    mink_shape = try_minkowski(node)
    if mink_shape:
        write_log("Minkowski", "Minkowski processed natively")
        return mink_shape

    return fallback_to_OpenSCAD(node, "Minkowski")


def create_boolean(node):
    node_type = type(node).__name__
    params = getattr(node, "params", {})
    write_log("Info",f"node {node_type} params {params}")
    shapes = []
    for child in node.children:
        node_type = type(child),__name__
        params = getattr(child, "params", {})
        write_log("Info",f"node {node_type} params {params}")
        shapes.append(process_AST_node(child))
    return shapes

#   helper functions
def to_vec3(s):
    if isinstance(s, (int, float)):
        return [s, s, s]
    if isinstance(s, (list, tuple)) and len(s) == 3:
        return list(s)
    raise TypeError("Expected scalar or list/tuple of length 3")


def to_tuple3(s):
    if isinstance(s, (int, float)):
        return (s, s, s)
    if isinstance(s, (list, tuple)) and len(s) == 3:
        return tuple(s)
    raise TypeError("Expected scalar or 3-element list/tuple")


#   Should be creating Shapes or Objects ??
def create_primitive(node):
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
        FreeCAD.Console.PrintMessage(f"[Info] Created sphere r={r}\n")
        return shape

    elif node_type == "Cube":
        size = params.get("size", [1.0, 1.0, 1.0])
        size_tuple = to_tuple3(size)
        write_log("Box",f"size {size_tuple}")

        shape = Part.makeBox(*size_tuple)
        FreeCAD.Console.PrintMessage(f"[Info] Created cube size={size_tuple}\n")
        return shape

    elif node_type == "Cylinder":
        r = params.get("r", 1.0)
        h = params.get("h", 1.0)
        shape = Part.makeCylinder(r, h)
        FreeCAD.Console.PrintMessage(f"[Info] Created cylinder r={r} h={h}\n")
        return shape

    elif node_type == "Circle":
        r = params.get("r", 1.0)
        # 2D wire
        shape = Part.makeCircle(r)
        FreeCAD.Console.PrintMessage(f"[Info] Created circle r={r}\n")
        return shape

    else:
        FreeCAD.Console.PrintMessage(f"[Warning] Unknown primitive: {node_type}, falling back to OpenSCAD\n")
        return None
        # Return fallback dict if unknown primitive
        #from freecad.OpenSCAD_Ext.core.fallback_to_OpenSCAD import fallback_to_OpenSCAD
        #return fallback_to_OpenSCAD(node, f"Unknown primitive: {node_type}")
