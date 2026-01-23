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
'''
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_classes import (
    CubeFC,
    SphereFC,
    CylinderFC,
    #TorusFC,
    UnionFC,
    DifferenceFC,
    IntersectionFC
)
'''
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



'''

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

'''

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

# -----------------------------
# Hull / Minkowski native attempts
# -----------------------------

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
'''

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


# -----------------------------
# Recursive AST node processing
# -----------------------------
import FreeCAD as App
import Part


def _as_list(result):
    """Normalize single or list return to list."""
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


def process_AST_node(node, parent_placement=None):
    if parent_placement is None:
        parent_placement = App.Placement()

    node_type = getattr(node, "node_type", None)

    # -----------------------------
    # SOLIDS
    # -----------------------------
    if node_type == "cube":
        params = node.params
        size = params.get("size", 1)
        center = params.get("center", False)

        # normalize size
        if hasattr(size, "__iter__"):
            s = list(size)
            while len(s) < 3:
                s.append(s[-1])
            sx, sy, sz = s[:3]
        else:
            sx = sy = sz = size

        shape = Part.makeBox(sx, sy, sz)

        if center:
            shape.translate(App.Vector(-sx/2, -sy/2, -sz/2))

        return (shape, App.Placement())

    if node_type == "sphere":
        r = node.params.get("r", 1)
        shape = Part.makeSphere(r)
        return (shape, App.Placement())

    if node_type == "cylinder":
        p = node.params
        h = p.get("h", 1)
        r1 = p.get("r1", p.get("r", 1))
        r2 = p.get("r2", r1)
        shape = Part.makeCylinder(r1, h, App.Vector(0,0,0), App.Vector(0,0,1), r2)
        return (shape, App.Placement())

    # -----------------------------
    # GROUP
    # -----------------------------
    if node_type in ("group", "root"):
        results = []
        for child in node.children:
            results.extend(_as_list(process_AST_node(child, parent_placement)))
        return results

    # -----------------------------
    # TRANSFORMS
    # -----------------------------
    if node_type in ("translate", "rotate", "scale", "multmatrix"):
        write_log("Transform",node_type)
        local_pl = App.Placement()

        if node_type == "translate":
            v = node.params.get("v", [0,0,0])
            local_pl.move(App.Vector(*v))

        elif node_type == "rotate":
            a = node.params.get("a", 0)
            v = node.params.get("v", [0,0,1])
            local_pl.Rotation = App.Rotation(App.Vector(*v), a)

        elif node_type == "scale":
            s = node.params.get("v", [1,1,1])
            m = App.Matrix()
            m.A11, m.A22, m.A33 = s
            local_pl = App.Placement(m)

        elif node_type == "multmatrix":
            m = node.params.get("matrix")
            mat = App.Matrix()
            mat.A11, mat.A12, mat.A13, mat.A14 = m[0]
            mat.A21, mat.A22, mat.A23, mat.A24 = m[1]
            mat.A31, mat.A32, mat.A33, mat.A34 = m[2]
            local_pl = App.Placement(mat)

        combined_pl = parent_placement.multiply(local_pl)
        write_log("Transform",f"Combined {combined_pl}")

        results = []
        for child in node.children:
            for shape, pl in _as_list(process_AST_node(child, combined_pl)):
                write_log("Transform",f"Child {pl*combined_pl}")
                results.append((shape, pl*combined_pl))
        return results

    # -----------------------------
    # BOOLEANS
    # -----------------------------
    if node_type in ("union", "difference", "intersection"):
        shapes = []
        for child in node.children:
            for shape, pl in _as_list(process_AST_node(child, parent_placement)):
                s = shape.copy()
                s.Placement = pl
                shapes.append(s)

        if not shapes:
            return []

        result = shapes[0]
        for s in shapes[1:]:
            if node_type == "union":
                result = result.fuse(s)
            elif node_type == "difference":
                result = result.cut(s)
            elif node_type == "intersection":
                result = result.common(s)

        return (result, App.Placement())

    # -----------------------------
    # FALLBACK
    # -----------------------------
    results = []
    for child in getattr(node, "children", []):
        results.extend(_as_list(process_AST_node(child, parent_placement)))
    return results



def save_process_AST_node(node, parent_placement=None):
    """
    Recursively process an AST node.

    Returns:
        Either:
          - a single (shape, placement) tuple
          - or a list of (shape, placement) tuples

    Rules:

    Solids:
        - Create a FreeCAD Shape
        - Return (shape, IdentityPlacement)
        - Do NOT apply parent placement here

    Group:
        - Return flattened list of child results

    Transforms (translate, rotate, scale, multmatrix):
        - Compute a new Placement = parent ∘ local_transform
        - Recurse into children
        - Apply transform to each returned child's placement

    Booleans (union, difference, intersection):
        - Evaluate children into shapes
        - Combine shapes into a single Boolean Shape
        - Return (boolean_shape, IdentityPlacement)

    Placement propagation:
        - Placements are accumulated top-down
        - Shapes are always created in local coordinates

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
        shape = try_hull(node)
        if shape is None:
            shape = fallback_to_OpenSCAD(node, operation_type="Hull", tolerance=1.0, timeout=60)
        return [(shape, parent_placement)]
    # -------------------------------------------------
    # MINKOWSKI
    # -------------------------------------------------
    if isinstance(node, Minkowski):
        shape = try_minkowski(shapes)
        if shape is None:
            shape = fallback_to_OpenSCAD(node, operation_type="Minkowski", tolerance=1.0, timeout=60)
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

def process_AST(nodes, mode="multiple"):
    """
    Process a list of AST nodes.

    Returns:
        List of (name, shape, placement) tuples
    """
    results = []

    for node in nodes:
        node_name = type(node).__name__
        processed = process_AST_node(node)

        if not processed:
            continue

        # Normalize to list
        if not isinstance(processed, list):
            processed = [processed]

        for shape, placement in processed:
            results.append((node_name, shape, placement))

        write_log(
            "AST",
            f"Processed {node_name} → {len(processed)} shape(s)"
        )

    if mode == "single":
        return results[0] if results else None

    return results


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
