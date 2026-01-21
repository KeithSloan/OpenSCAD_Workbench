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
from FreeCAD import Vector

#from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import AstNode

import multiprocessing
import Mesh
import Part

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

import FreeCAD
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

def generate_stl_from_scad(scad_str, timeout_sec=60):
    """
    Generate STL from a SCAD string using the Workbench-configured OpenSCAD executable.
    Returns path to STL on success, None on error/timeout.
    """
    # Get OpenSCAD path from FreeCAD preferences
    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
    openscad_exe = prefs.GetString("openscadexecutable", "")

    if not openscad_exe or not os.path.isfile(openscad_exe):
        write_log("OpenSCAD", f"OpenSCAD executable not configured or invalid: {openscad_exe}")
        return None

    # Create temp SCAD file
    with tempfile.NamedTemporaryFile(suffix=".scad", delete=False) as scad_file:
        scad_file_path = scad_file.name
        scad_file.write(scad_str.encode("utf-8"))
        scad_file.flush()

    # STL output path
    stl_path = scad_file_path.replace(".scad", ".stl")

    # OpenSCAD CLI command
    cmd = [openscad_exe, "-o", stl_path, scad_file_path]

    write_log("OpenSCAD", f"Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, timeout=timeout_sec, check=True)
        write_log("OpenSCAD", f"Generated STL: {stl_path}")
        return stl_path
    except subprocess.TimeoutExpired:
        write_log("OpenSCAD", f"Timeout after {timeout_sec}s")
    except subprocess.CalledProcessError as e:
        write_log("OpenSCAD", f"OpenSCAD error: {e}")

    return None





def saved_generate_stl_from_scad(scad_str, check_syntax=False, timeout=60):
    """
    Write SCAD to temp file, call OpenSCAD CLI, return STL path.
    Enforces timeout.
    """
    tmpdir = tempfile.mkdtemp(prefix="openscad_")
    tmpdir = "/tmp/call_to_scad"
    scad_file = os.path.join(tmpdir, "fallback.scad")
    stl_file  = os.path.join(tmpdir, "fallback.stl")

    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
    openscad_exe = prefs.GetString("openscadexecutable", "")

    if not openscad_exe or not os.path.isfile(openscad_exe):
        raise FileNotFoundError("OpenSCAD executable not configured")

    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(scad_str)
        f.flush()

    cmd = [
        openscad_exe,
        "-o", stl_file,
        scad_file
    ]

    write_log("OpenSCAD", f"Running: {' '.join(cmd)} (timeout={timeout}s)")

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            # check=True,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"OpenSCAD timed out after {timeout} seconds")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "OpenSCAD failed:\n" + e.stderr.decode(errors="ignore")
        )

    if not os.path.isfile(stl_file):
        raise RuntimeError("OpenSCAD did not produce STL")

    return stl_file



def _mesh_to_shape_worker(stl_path, tolerance, queue):
    """Worker process to safely run makeShapeFromMesh with timeout"""
    try:
        mesh_obj = Mesh.Mesh(stl_path)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh_obj.Topology, tolerance)
        queue.put(shape)
    except Exception as e:
        queue.put(e)


def stl_to_shape(stl_path, tolerance=0.05,timeout=None):
    """
    Import STL into FreeCAD and convert to Part.Shape.
    Returns a Part.Shape or None on failure.
    """
    if not stl_path or not os.path.isfile(stl_path):
        write_log("AST_Hull:Minkowski", f"STL file not found: {stl_path}")
        return None

    try:
        write_log("AST_Hull:Minkowski", f"Importing STL and converting to Part.Shape: {stl_path}")

        # Load the STL as a Mesh
        mesh_obj = Mesh.Mesh(stl_path)

        # Convert Mesh to Part.Shape
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh_obj.Topology, tolerance)

        # Get number of points safely
        n_points = getattr(mesh_obj, "CountPoints", None)
        if n_points is None:
            n_points = len(mesh_obj.Topology[0]) if isinstance(mesh_obj.Topology, tuple) else 0

        write_log("AST_Hull:Minkowski", f"STL converted to Part.Shape with approx {n_points} points")
        return shape

    except Exception as e:
        write_log("AST_Hull:Minkowski", f"Failed to convert STL to Shape: {e}")
        return None


def fallback_to_OpenSCAD(node, operation_type="Hull", tolerance=1.0, timeout=60):
    """
    Fallback processing for Hull / Minkowski nodes:
    - Uses flatten_hull_minkowski_node for OpenSCAD string
    - Generates STL via OpenSCAD CLI
    - Imports STL into FreeCAD with timeout
    - Caches result in node._shape
    """
    # Return cached shape if already processed
    if hasattr(node, "_shape"):
        write_log(operation_type, f"Using cached Shape for node {node.node_type}")
        return node._shape

    write_log(operation_type, f"{operation_type} fallback to OpenSCAD")

    # Flatten node to SCAD string
    scad_str = flatten_hull_minkowski_node(node, indent=4)
    write_log("CSG", scad_str)

    # Generate STL via OpenSCAD CLI
    stl_file = generate_stl_from_scad(scad_str)


    # Import STL safely with timeout and tolerance
    shape = stl_to_shape(stl_file, tolerance=tolerance, timeout=timeout)

    # Cache shape to prevent reprocessing
    node._shape = shape
    write_log(operation_type, f"{operation_type} fallback completed, shape cached")

    return shape

# -*- coding: utf-8 -*-
"""
Process AST nodes into FreeCAD Shapes
------------------------------------

- Hull / Minkowski: try native BRep, fallback to OpenSCAD
- Primitives: create Part.Shape
- Booleans: union/difference/intersection recursively
- Transforms: apply to child Shapes
- Only Hull/Minkowski call OpenSCAD
- Debug SCAD dumps written for inspection
"""


# -----------------------------
# Hull / Minkowski native attempts
# -----------------------------
"""
def try_hull(node):
    """
    #Attempt to generate a native FreeCAD hull from children shapes.
    #Returns Part.Shape or None if not possible.
"""
    return None

    shapes = [process_AST_node(c) for c in node.children if process_AST_node(c)]
    if len(shapes) < 2:
        return None  # Need at least 2 shapes for hull

    # TODO: implement native FreeCAD convex hull
    # Returning None for now to trigger OpenSCAD fallback
    write_log("AST_Hull", "Native hull not implemented, falling back")
    return None


def try_minkowski(node):
    
    #Attempt to generate a native FreeCAD Minkowski sum.
    #Returns Part.Shape or None if not possible.
    
    
    #return None

    shapes = [process_AST_node(c) for c in node.children if process_AST_node(c)]
    if len(shapes) != 2:
        return None  # Minkowski sum requires exactly 2 shapes

    # TODO: implement native FreeCAD Minkowski sum
    # Returning None for now to trigger OpenSCAD fallback
    write_log("AST_Minkowski", "Native Minkowski not implemented, falling back")
    return None
    """

# ============================================================
# SCAD flattening (Hull / Minkowski fallback)
# ============================================================

def flatten_hull_minkowski_node(node, indent=0):
    pad = " " * indent
    scad_lines = []

    if node is None:
        return ""  # ← always return string

    write_log("FLATTEN", f"{pad}Flatten node: {node.node_type}, children={len(getattr(node, 'children', []))}, csg_params={getattr(node, 'csg_params', None)}")

    # Transparent group
    if node.node_type == "group":
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent))
        return "\n".join(filter(None, scad_lines))  # filter out None

    # Hull / Minkowski
    if node.node_type in ("hull", "minkowski"):
        scad_lines.append(f"{pad}{node.node_type}() {{")
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent + 4))
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # MultMatrix: raw string from csg_params
    if node.node_type == "multmatrix":
        matrix_str = ""
        if isinstance(node.csg_params, str):
            matrix_str = node.csg_params
        elif isinstance(node.csg_params, dict) and "matrix" in node.csg_params:
            matrix_str = node.csg_params["matrix"]
        scad_lines.append(f"{pad}multmatrix({matrix_str}) {{")
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent + 4))
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # Other primitives (sphere, cube, etc.) — just use csg_params string
    csg_str = ""
    if hasattr(node, "csg_params") and isinstance(node.csg_params, str):
        csg_str = node.csg_params
    elif hasattr(node, "csg_params") and isinstance(node.csg_params, dict):
        parts = []
        for k, v in node.csg_params.items():
            if v is not None:
                try:
                    float(v)
                    parts.append(f"{k}={v}")
                except (ValueError, TypeError):
                    parts.append(f'{k}="{v}"')
        csg_str = ", ".join(parts)

    if csg_str:
        scad_lines.append(f"{pad}{node.node_type}({csg_str});")

    return "\n".join(filter(None, scad_lines))


'''
def flatten_hull_minkowski_node(node, indent=0):
    """
    Flatten any AST node for Hull/Minkowski fallback:
    - Uses csg_params for primitives
    - Recursively flattens all children including nested Hull/Minkowski
    - Only groups are transparent
    """
    pad = " " * indent
    scad_lines = []

    if node is None:
        return ""

    write_log("FLATTEN", f"{pad}Flatten node: {node.node_type}, children={len(node.children)}, csg_params={getattr(node, 'csg_params', {})}")

    # Transparent group
    if node.node_type == "group":
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent))
        return "\n".join(scad_lines)

    # Build parameter string from csg_params
    params_str = ""
    if hasattr(node, "csg_params") and node.csg_params:
        arg_list = []
        for k, v in node.csg_params.items():
            if v is None:
                arg_list.append(k)
            elif isinstance(v, (int, float, list, tuple)):
                arg_list.append(f"{k}={v}")
            elif isinstance(v, str):
                arg_list.append(f'{k}="{v}"')
        params_str = ", ".join(arg_list)

    # Emit node
    if node.children:
        scad_lines.append(f"{pad}{node.node_type}({params_str}) {{")
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent + 4))
        scad_lines.append(f"{pad}}}")
    else:
        scad_lines.append(f"{pad}{node.node_type}({params_str});")

    return "\n".join(scad_lines)

def apply_transform(node, shape):
    """
    Apply a transform node to a FreeCAD Shape
    """
    p = node.params
    if node.node_type == "translate":
        v = p.get("v")
        if v:
            shape.translate(Vector(*v))
    elif node.node_type == "scale":
        v = p.get("v")
        if v:
            shape.scale(Vector(0,0,0), Vector(*v))
    elif node.node_type == "rotate":
        a = p.get("a")
        v = p.get("v", [0,0,1])
        if a:
            shape.rotate(Vector(0,0,0), Vector(*v), a)
    return shape
'''

# -----------------------------
# Hull / Minkowski native attempts
# -----------------------------

def try_hull(node):
    return None
    shapes = []
    for c in node.children:
        s = process_AST_node(c)
        if s:
            shapes.append(s)
    if len(shapes) < 2:
        return None
    # TODO: native FreeCAD convex hull
    write_log("AST_Hull", "Native hull not implemented, fallback")
    return None


def try_minkowski(node):
    return None
    shapes = []
    for c in node.children:
        s = process_AST_node(c)
        if s:
            shapes.append(s)
    if len(shapes) != 2:
        return None
    # TODO: native FreeCAD Minkowski
    write_log("AST_Minkowski", "Native Minkowski not implemented, fallback")
    return None


# -----------------------------
# AST Processing
# -----------------------------

def process_AST_node(node):
    if node is None:
        return None

    if getattr(node, "_terminal", False):
        return node._shape

    node_type = node.node_type.lower()
    write_log("AST", f"Processing node: {node_type}, children={len(node.children)}")

    # Hull / Minkowski
    if node_type == "hull":

        shape = try_hull(node)
        if shape is None:
            shape = fallback_to_OpenSCAD(node, "Hull")
        return shape

    if node_type == "minkowski":

        shape = try_minkowski(node)
        if shape is None:
            shape = fallback_to_OpenSCAD(node, "Minkowski")
        return shape

    # Transforms
    if node_type in ("translate", "rotate", "scale", "multmatrix"):
        if not node.children:
            return None
        child_shape = process_AST_node(node.children[0])
        if child_shape:
            return apply_transform(node, child_shape)
        return None

    # Booleans
    if node_type in ("union", "difference", "intersection"):
        shapes = []
        for c in node.children:
            s = process_AST_node(c)
            if s:
                shapes.append(s)
        if not shapes:
            return None

        result = shapes[0]
        for s in shapes[1:]:
            if node_type == "union":
                result = result.fuse(s)
            elif node_type == "difference":
                result = result.cut(s)
            elif node_type == "intersection":
                result = result.common(s)
        return result

    # Primitives
    if node_type in ("cube", "sphere", "cylinder", "polyhedron", "circle", "square", "polygon"):
        return create_primitive(node)

    # Unknown
    write_log("AST", f"Unknown node type '{node.node_type}', fallback to OpenSCAD")
    #return fallback_to_OpenSCAD(node, "Unknown")
    # causes recurssion - Loop
    return None



def process_AST(nodes, mode=None):
    """
    shapes = []
    for n in nodes:
        s = process_AST_node(n)
        if s:
            shapes.append(s)
    """
    shapes = process_AST_node(nodes[0])
    write_log("AST", f"Processed Shapes: {shapes}")
    #return None
    return shapes


# -----------------------------
# Primitives
# -----------------------------

def create_primitive(node):
    """
    Create FreeCAD Part.Shape from node.params (typed)
    """
    p = node.params
    t = node.node_type.lower()
    try:
        if t == "cube":
            size = p.get("size", [1,1,1])
            if isinstance(size, (int, float)):
                size = [size, size, size]
            return Part.makeBox(*size)
        elif t == "sphere":
            r = p.get("r", 1)
            return Part.makeSphere(r)
        elif t == "cylinder":
            h = p.get("h", 1)
            r = p.get("r", 1)
            return Part.makeCylinder(r, h)
        elif t == "polyhedron":
            points = p.get("points", [])
            faces = p.get("faces", [])
            return Part.makePolyhedron(points, faces)
        elif t == "circle":
            r = p.get("r", 1)
            return Part.makeCircle(r)
        elif t == "square":
            size = p.get("size", [1,1])
            if isinstance(size, (int, float)):
                size = [size, size]
            return Part.makePlane(*size)
        elif t == "polygon":
            points = p.get("points", [])
            return Part.makePolygon(points)
    except Exception as e:
        write_log("AST", f"Failed to create primitive {t} with params {p}: {e}")
        return None
