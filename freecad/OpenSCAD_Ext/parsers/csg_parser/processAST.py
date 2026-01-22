# -*- coding: utf8 -*-
#****************************************************************************
#*   AST Processing for OpenSCAD CSG importer                               *
#*   Converts AST nodes to FreeCAD Shapes or SCAD strings with fallbacks    *
#*                                                                          *
#*      Returns Shape                                                       *
#****************************************************************************
'''
Rules:
shape is None → empty / ignored
Placement() = identity
Placement is always applied last, never baked unless required
'''
import os
import subprocess
import tempfile
import FreeCAD
import Part
import Mesh
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_classes import (
    CubeFC,
    SphereFC,
    CylinderFC,
    #TorusFC,
    UnionFC,
    DifferenceFC,
    IntersectionFC
)
#from FreeCAD import Vector

#from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    AstNode,
    Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Group,
    Translate, Rotate, Scale, MultMatrix,
    Hull, Minkowski,
    LinearExtrude, RotateExtrude,
    Color
)

'''

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
    elif node.node_type in ("hull", "minkowski"):
        scad_lines.append(f"{pad}{node.node_type}() {{")
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent + 4))
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # MultMatrix: raw string from csg_params
    elif node.node_type == "multmatrix":
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

    elif node.node_type == "linear_extrude":
        write_log("AST",node.node_type)

    elif node.node_type == "rotate_extrude":
        write_log("AST",node.node_type)
    
    elif node.node_type == "text":
    # Always fallback — FreeCAD has no native text solid
    # This is in a hull/minkowski flatten
    # Call OpenSCAD to return 2D Dxf
        #shape = fallback_to_OpenSCAD(node, "Text")
        return None


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
'''

def apply_transform(node):
    p = node.params
    pl = FreeCAD.Placement()  # identity

    if node.node_type == "translate":
        v = p.get("v")
        if v:
            pl.Base = FreeCAD.Vector(*v)

    elif node.node_type == "rotate":
        a = p.get("a")
        v = p.get("v", [0,0,1])
        if a:
            pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(*v), float(a))

    elif node.node_type == "multmatrix":
        m = p.get("m")
        if m:
            # row-major → column-major flatten
            fm = [m[row][col] for col in range(4) for row in range(4)]
            mat = FreeCAD.Matrix(*fm)
            pl = FreeCAD.Placement(mat)

    return pl
'''
'''
def apply_scale(node, pl):
    if node.node_type == "scale":
        v = p.get("v")
        if v:
            write_log("SCALE","Need to implement")
            return shape.scale(Vector(0,0,0), Vector(*v), pl)
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


def normalize_results(result):
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


def placement_from_matrix(matrix):
    """
    Convert 4x4 OpenSCAD matrix into FreeCAD.Placement
    """
    fm = [matrix[row][col] for col in range(4) for row in range(4)]
    return FreeCAD.Placement(FreeCAD.Matrix(*fm))



# ----------------------------------------------------------
# AST Processing
# ----------------------------------------------------------
#
# Returns : List of
#   (placement: FreeCAD.Placement, shape: Part.Shape | None)
# ----------------------------------------------------------

# processAST.py (partial)
# -----------------------------
# Import FreeCAD wrappers from full path
# Mapping from ast_nodes type to FreeCAD wrapper
AST_TO_FC = {
    "Cube": CubeFC,
    "Sphere": SphereFC,
    "Cylinder": CylinderFC,
    #"Torus": TorusFC,
    "Union": UnionFC,
    "Difference": DifferenceFC,
    "Intersection": IntersectionFC,
}

def wrap_node_for_fc(node):
    """Convert a plain AST node into its FreeCAD-enabled wrapper."""
    node_type = type(node).__name__
    wrapper_class = AST_TO_FC.get(node_type)
    if wrapper_class is not None:
        # Use __dict__ to pass all parameters from the original node
        return wrapper_class(**node.__dict__)
    else:
        # For transform nodes (Translate, Rotate, MultMatrix) and unknown types
        return node

# -----------------------------
# Recursive AST node processing
# -----------------------------
def process_AST_node(node, parent_placement=None):
    """
    Process a single AST node recursively.
    Applies transformations and calls createShape() for primitives/booleans.
    """
    # Wrap node with FreeCAD class if available
    fc_node = wrap_node_for_fc(node)

    results = []

    # If node has children (for booleans and transforms)
    children = getattr(fc_node, "children", None)
    if children:
        for child in children:
            results.extend(process_AST_node(child, parent_placement))

    # If node has createShape(), generate shape
    if hasattr(fc_node, "createShape"):
        shape = fc_node.createShape()
        # Apply parent placement if any
        if shape and parent_placement:
            shape.Placement = parent_placement.multiply(shape.Placement)
        results.append(shape)

    # Handle transform nodes (Translate, Rotate, MultMatrix)
    elif hasattr(fc_node, "placement"):
        # Assuming fc_node.placement is a FreeCAD.Placement object
        composed = parent_placement.multiply(fc_node.placement) if parent_placement else fc_node.placement
        child_nodes = getattr(fc_node, "children", [])
        for child in child_nodes:
            results.extend(process_AST_node(child, composed))

    return results


'''

def process_AST_node(node, parent_placement=None):
    """
    Process an AST node.
    Returns: list of (shape, placement)
    """
    if parent_placement is None:
        parent_placement = FreeCAD.Placement()

    results = []

    # -------------------------------------------------
    # MULTMATRIX
    # -------------------------------------------------
    if isinstance(node, MultMatrix):
        matrix = node.params.get("matrix")
        if matrix:
            local_pl = placement_from_matrix(matrix)
            composed = parent_placement.multiply(local_pl)
        else:
            composed = parent_placement

        for child in node.children:
            results.extend(process_AST_node(child, composed))

        return results

    # -------------------------------------------------
    # TRANSFORMS
    # -------------------------------------------------
    if isinstance(node, (Translate, Rotate, Scale)):
        local_pl = node.getPlacement()
        composed = parent_placement.multiply(local_pl)

        for child in node.children:
            results.extend(process_AST_node(child, composed))

        return results

    # -------------------------------------------------
    # GROUP (structure only)
    # -------------------------------------------------
    if isinstance(node, Group):
        for child in node.children:
            results.extend(process_AST_node(child, parent_placement))
        return results

    # -------------------------------------------------
    # PRIMITIVES
    # -------------------------------------------------
    if isinstance(node, (Cube, Sphere, Cylinder)):
        shape = node.createShape()
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    # -------------------------------------------------
    # LINEAR / ROTATE EXTRUDE
    # -------------------------------------------------
    if isinstance(node, (LinearExtrude, RotateExtrude)):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = node.createShape(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    # -------------------------------------------------
    # HULL
    # -------------------------------------------------
    if isinstance(node, Hull):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = try_hull(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    # -------------------------------------------------
    # MINKOWSKI
    # -------------------------------------------------
    if isinstance(node, Minkowski):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = try_minkowski(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    # -------------------------------------------------
    # BOOLEAN OPERATIONS
    # -------------------------------------------------
    if isinstance(node, Union):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = node.applyBoolean(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    if isinstance(node, Difference):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = node.applyBoolean(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    if isinstance(node, Intersection):
        child_results = []
        for child in node.children:
            child_results.extend(process_AST_node(child, parent_placement))

        shapes = [s for (s, _) in child_results if s]
        if not shapes:
            return []

        shape = node.applyBoolean(shapes)
        shape.Placement = parent_placement
        return [(shape, parent_placement)]

    # -------------------------------------------------
    # COLOR (pass-through for now)
    # -------------------------------------------------
    if isinstance(node, Color):
        for child in node.children:
            results.extend(process_AST_node(child, parent_placement))
        return results

    # -------------------------------------------------
    # FALLBACK
    # -------------------------------------------------
    for child in getattr(node, "children", []):
        results.extend(process_AST_node(child, parent_placement))

    return results
'''

def process_AST(nodes, mode="single"):
    if not nodes:
        return None

    pl = FreeCAD.Base.Placement()

    if mode == "single":
        shape, pl = process_AST_node(nodes[0], pl)
        return shape, pl

    shapes = []
    for node in nodes:
        shape, pl = process_AST_node(node, pl)
        if shape:
            shape.Placement = pl
            shapes.append(shape)

    if not shapes:
        return None, pl

    if len(shapes) == 1:
        return shapes[0], pl

    return Part.makeCompound(shapes), pl

def logShapeState(shape, label="", indent=""):
    """
    Drop-in diagnostic helper for FreeCAD Part.Shapes.
    Does NOT modify the shape.
    Safe to call anywhere.

    :param shape: Part.Shape or None
    :param label: Optional label (node name, operation, filename, etc.)
    :param indent: Optional indent string for nested logs
    """

    try:
        if shape is None:
            FreeCAD.Console.PrintMessage(
                f"{indent}[Shape] {label}: None\n"
            )
            return

        msg = f"{indent}[Shape] {label}: "

        if shape.isNull():
            msg += "NULL"
        else:
            msg += shape.ShapeType

            if not shape.isValid():
                msg += " (INVALID)"
            else:
                msg += " (valid)"

            # Useful counts without touching geometry
            msg += (
                f" V:{len(shape.Vertexes)}"
                f" E:{len(shape.Edges)}"
                f" F:{len(shape.Faces)}"
                f" S:{len(shape.Solids)}"
            )

        FreeCAD.Console.PrintMessage(msg + "\n")

    except Exception as e:
        FreeCAD.Console.PrintError(
            f"{indent}[Shape] {label}: ERROR {e}\n"
        )
'''

def create_primitive(node):
    """
    Create FreeCAD Part.Shape and Placement from node.params (typed)
    Returns (shape, placement)
    """
    p = node.params
    t = node.node_type.lower()

    placement = FreeCAD.Base.Placement()

    try:
        if t == "cube":
            raw_size = p.get("size", 1)
            center = bool(p.get("center", False))

            if isinstance(raw_size, (int, float)):
                sx = sy = sz = float(raw_size)
            else:
                sx, sy, sz = map(float, raw_size)

            shape = Part.makeBox(sx, sy, sz)

            if center:
                placement.Base = FreeCAD.Vector(
                    -sx / 2.0,
                    -sy / 2.0,
                    -sz / 2.0
                )
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "sphere":
            r = float(p.get("r", 1))
            shape = Part.makeSphere(r)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "cylinder":
            h = float(p.get("h", 1))
            r = float(p.get("r", 1))
            center = bool(p.get("center", False))

            shape = Part.makeCylinder(r, h)

            if center:
                placement.Base = FreeCAD.Vector(0, 0, -h / 2.0)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "polyhedron":
            points = p.get("points", [])
            faces = p.get("faces", [])
            shape = Part.makePolyhedron(points, faces)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "circle":
            r = float(p.get("r", 1))
            shape = Part.makeCircle(r)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "square":
            size = p.get("size", [1, 1])
            center = bool(p.get("center", False))

            if isinstance(size, (int, float)):
                sx = sy = float(size)
            else:
                sx, sy = map(float, size)

            shape = Part.makePlane(sx, sy)

            if center:
                placement.Base = FreeCAD.Vector(-sx / 2.0, -sy / 2.0, 0)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

        elif t == "polygon":
            points = p.get("points", [])
            shape = Part.makePolygon(points)
            write_log("Primitive", f"{t} -> Shape: {shape}, Placement: {placement}")
            return shape, placement

    except Exception as e:
        write_log(
            "AST",
            f"Failed to create primitive {t} with params {p}: {e}"
        )
        return None, None
'''

