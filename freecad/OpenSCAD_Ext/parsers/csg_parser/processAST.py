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
#import subprocess
#import tempfile
import FreeCAD
import Part
import Draft
import Mesh
import FreeCAD as App
from FreeCAD import Vector

#from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import get_tess, apply_transform

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_utils import dump_ast_node

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    Hull, Minkowski
    )

from freecad.OpenSCAD_Ext.parsers.csg_parser.process_utils import call_openscad_scad_string#
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_polyhedron import process_polyhedron
from freecad.OpenSCAD_Ext.parsers.csg_parser.processHull import try_hull

from freecad.OpenSCAD_Ext.parsers.csg_parser.process_text import process_text 


def generate_stl_from_scad(scad_str, timeout_sec=60):
    write_log("AST",f"Generate STL from SCAD string")
    return call_openscad_scad_string(scad_str, export_type='stl', timeout_sec=timeout_sec)


def _mesh_to_shape_worker(stl_path, tolerance, queue):
    """Worker process to safely run makeShapeFromMesh with timeout"""
    try:
        mesh_obj = Mesh.Mesh(stl_path)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh_obj.Topology, tolerance)
        queue.put(shape)
    except Exception as e:
        queue.put(e)

    # See also stl_to_shape
def shape_from_scad(scad_str, refine=True):
    
    stl_path = generate_stl_from_scad(scad_str)
    if not stl_path:
        return None

    # Import STL into FreeCAD Part.Shape
    mesh_obj = Mesh.Mesh(stl_path)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh_obj.Topology, 0.0001)

    if refine:
        try:
            return_shape = shape.copy().refineShape()
            if return_shape.isNull() or return_shape.isEmpty():
                write_log("STL", "RefineShape returned empty shape, falling back to original")
                return_shape = shape
        except Exception as e:
            write_log("STL", f"RefineShape failed: {e}, using original shape")
            return_shape = shape
    else:
        return_shape = shape
        


    # See also shape_from_scad - uses refine, no so much checking
def stl_to_shape(stl_path, tolerance=0.05, timeout=None):
    """
    Import STL into FreeCAD and convert to Part.Shape.
    Always attempts to return a Solid.
    Returns a Part.Shape or None on failure.
    """

    if not stl_path or not os.path.isfile(stl_path):
        write_log("AST_Hull:Minkowski", f"STL file not found: {stl_path}")
        return None

    try:
        write_log(
            "AST_Hull:Minkowski",
            f"Importing STL and converting to Part.Shape: {stl_path}"
        )

        # Load STL
        mesh = Mesh.Mesh(stl_path)

        # Instrumentation (API-safe)
        try:
            is_closed = mesh.isSolid()
        except Exception:
            is_closed = False

        facets = getattr(mesh, "CountFacets", 0)

        write_log(
            "AST_Hull:Minkowski",
            f"Mesh facets={facets}, solid={is_closed}"
        )

        # Mesh → Shape (shell)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, tolerance)
        shape = shape.removeSplitter()

        # Always attempt solid
        if is_closed:
            try:
                solid = Part.makeSolid(shape)
                solid = solid.removeSplitter()

                valid = solid.isValid()
                write_log(
                    "AST_Hull:Minkowski",
                    f"Solid created, valid={valid}"
                )

                return solid

            except Exception as e:
                write_log(
                    "AST_Hull:Minkowski",
                    f"makeSolid failed, falling back to sewing: {e}"
                )

        # Fallback: sew faces → solid
        try:
            shell = Part.makeShell(shape.Faces)
            solid = Part.makeSolid(shell)
            solid = solid.removeSplitter()

            valid = solid.isValid()
            write_log(
                "AST_Hull:Minkowski",
                f"Sewing fallback solid valid={valid}"
            )

            return solid

        except Exception as e:
            write_log(
                "AST_Hull:Minkowski",
                f"Sewing fallback failed, returning shell: {e}"
            )

        return shape

    except Exception as e:
        write_log(
            "AST_Hull:Minkowski",
            f"Failed to convert STL to Shape: {e}"
        )
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
''' Now imported !!!!
# -----------------------------
# Hull / Minkowski native attempts
# -----------------------------
def try_hull(node):
    """
    #Attempt to generate a native FreeCAD hull from children shapes.
    #Returns Part.Shape or None if not possible.
    """
    write_log("AST","Try Hull")
    return None

    hull_shape = try_hull(node)
    if hull_shape:
        # fast native hull handled
        return hull_shape

    shapes = [process_AST_node(c) for c in node.children if process_AST_node(c)]
    if len(shapes) < 2:
        return None  # Need at least 2 shapes for hull

    # TODO: implement native FreeCAD convex hull
    # Returning None for now to trigger OpenSCAD fallback
    write_log("AST_Hull", "Native hull not implemented, falling back")
    return None
'''

def try_minkowski(node):
    """
    #Attempt to generate a native FreeCAD Minkowski sum.
    #Returns Part.Shape or None if not possible.
    """
    write_log("AST","Try Minkowski")
    #return None

    shapes = [process_AST_node(c) for c in node.children if process_AST_node(c)]
    if len(shapes) != 2:
        return None  # Minkowski sum requires exactly 2 shapes

    # TODO: implement native FreeCAD Minkowski sum
    # Returning None for now to trigger OpenSCAD fallback
    write_log("AST_Minkowski", "Native Minkowski not implemented, falling back")
    return None


# ============================================================
# SCAD flattening (Hull / Minkowski fallback)
# ============================================================

def _format_csg_params(node):
    """
    Return parameter string for OpenSCAD reconstruction.
    Prefers raw csg_params if present.
    """
    if node.csg_params is None:
        return ""
    if isinstance(node.csg_params, str):
        return node.csg_params
    if isinstance(node.csg_params, dict):
        return ", ".join(f"{k}={v!r}" for k, v in node.csg_params.items())
    return str(node.csg_params)


def flatten_hull_minkowski_node(node, indent=0):
    pad = " " * indent
    scad_lines = []

    if node is None:
        return ""

    write_log(
        "FLATTEN",
        f"{pad}Flatten node: {node.node_type}, "
        f"children={len(getattr(node, 'children', []))}, "
        f"csg_params={getattr(node, 'csg_params', None)}"
    )

    # -------------------------
    # Transparent group
    # -------------------------
    if node.node_type == "group":
        for child in node.children:
            scad_lines.append(flatten_hull_minkowski_node(child, indent))
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Hull / Minkowski
    # -------------------------
    if node.node_type in ("hull", "minkowski"):
        scad_lines.append(f"{pad}{node.node_type}() {{")
        for child in node.children:
            scad_lines.append(
                flatten_hull_minkowski_node(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # MultMatrix
    # -------------------------
    if node.node_type == "multmatrix":
        matrix_str = _format_csg_params(node)
        scad_lines.append(f"{pad}multmatrix({matrix_str}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_hull_minkowski_node(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Linear Extrude
    # -------------------------
    if node.node_type == "linear_extrude":
        params = _format_csg_params(node)
        scad_lines.append(f"{pad}linear_extrude({params}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_hull_minkowski_node(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Rotate Extrude
    # -------------------------
    if node.node_type == "rotate_extrude":
        params = _format_csg_params(node)
        scad_lines.append(f"{pad}rotate_extrude({params}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_hull_minkowski_node(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Text (always OpenSCAD fallback)
    # -------------------------
    if node.node_type == "text":
        params = _format_csg_params(node)
        return f"{pad}text({params});"

    # -------------------------
    # Generic fallback (cube, sphere, etc.)
    # -------------------------
    params = _format_csg_params(node)
    if params:
        return f"{pad}{node.node_type}({params});"
    else:
        return f"{pad}{node.node_type}();"


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
        m = p.get("matrix")
        if isinstance(m, FreeCAD.Matrix):
            pl = FreeCAD.Placement(m)
        elif m is not None:
            raise TypeError(f"multmatrix param is not Matrix: {type(m)}")

    ### Matrix should have been handled by parsing to AST
    #elif node.node_type == "multmatrix":
    #    m = p.get("m")
    #    if m:
    #        # row-major → column-major flatten
    #        fm = [m[row][col] for col in range(4) for row in range(4)]
    #        mat = FreeCAD.Matrix(*fm)
    #        pl = FreeCAD.Placement(mat)

    #return pl

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
#   (shape: Part.Shape , placement: FreeCAD.Placement, | None)
# ----------------------------------------------------------

def _as_list(result):
    """Normalize single or list return to list."""
    #dump_nodes_list(result)
    if result is None:
        return []
    if isinstance(result, list):
        return result
    write_log("List Item Types",f"{type(result[0])} , {type(result[1])}")
    return [result]


def debug_dump_cylinder_node(node, prefix=""):
    write_log("CYL_DEBUG", f"{prefix}Cylinder node")
    write_log("CYL_DEBUG", f"{prefix}  params = {node.params}")
    write_log("CYL_DEBUG", f"{prefix}  csg_params = {node.csg_params!r}")
    write_log("CYL_DEBUG", f"{prefix}  children = {len(node.children)}")


def log_empty_groups(node, depth=0):
    if node.node_type == "group" and not node.children:
        write_log("AST", f"{'  '*depth}EMPTY GROUP at depth {depth}")
    for child in getattr(node, "children", []):
        log_empty_groups(child, depth+1)

def dump_nodes_list(node_type, shapes_list):
    write_log("Dump",f"Node list Type : {node_type} type : {type(shapes_list)}")
    list_type = type(shapes_list)
    if list_type == "list":
        for item in shapes_list:
            write_log("Dump",f"{item} type {item.node_type} {item}")
            print(dir(item))
            write_log("Dump",f"Children {len(item.children)}")
            for child in item.children:
                write_log("Dump",f"{child}")

    elif list_type =="tuple":
        write_log("Dump",f"Tuple {list_type}")



def process_AST_node(node):

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

    results = []
    local_pl = App.Placement()

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

        return (shape, local_pl)

    if node_type == "sphere":
        r = node.params.get("r", 1)
        shape = Part.makeSphere(r)
        return (shape, local_pl)

    if node_type == "cylinder":
        p = node.params
        h = p.get("h", 1)
        r1 = p.get("r1", p.get("r", 1))
        r2 = p.get("r2", r1)

        if r1 == r2:
            shape = Part.makeCylinder(r1, h)
        elif r1 == 0 or r2 == 0:
            shape = Part.makeCone(r1, r2, h)  # true cone
        else:
            shape = Part.makeCone(r1, r2, h)

        return (shape, local_pl)

    elif node.node_type == "polyhedron":
        write_log("AST", f"Processing Polyhedron: points={node.points}, faces={node.faces}")
        return (process_polyhedron(node), local_pl)

    elif node.node_type == "text":
        write_log("AST","Processing text")
        return(process_text(node), local_pl)


    # -----------------------------
    # Hull Minkowski
    # -----------------------------

    if isinstance(node, Hull):
        write_log("AST", f"Hull node detected, children={len(node.children or [])}")
        
        # Optional: log if degenerate
        if len(node.children or []) == 1:
            write_log("AST", "Degenerate hull (single child)")

        # Call the usual hull processor
        shape = try_hull(node)

        if shape is None:
            write_log("AST", "try_hull failed, falling back to OpenSCAD")
            shape = fallback_to_OpenSCAD(node, operation_type="Hull", tolerance=1.0, timeout=60)

        return [(shape, local_pl)]

    # -------------------------------------------------
    # MINKOWSKI
    # -------------------------------------------------
    if isinstance(node, Minkowski):
        shape = try_minkowski(node)
        if shape is None:
            shape = fallback_to_OpenSCAD(node, operation_type="Minkowski", tolerance=1.0, timeout=60)
        return [(shape, local_pl)]
        
    # -----------------------------
    # GROUP
    # -----------------------------
    if node_type in ("group", "root"):
        # Instrumentation
        n_children = len(node.children or [])
        write_log("AST", f"Group node_type={node_type}, children={n_children}")
        if n_children == 0:
            write_log("AST", "EMPTY GROUP detected")

        results = []
        for child in node.children or []:
            results.extend(_as_list(process_AST_node(child)))
        return results

    # -----------------------------
    # TRANSFORMS
    # -----------------------------
    if node_type in ("translate", "rotate", "scale", "multmatrix"):
        write_log("Transform",node_type)

        if node_type == "translate":
            v = node.params.get("v", [0,0,0])
            trans_pl = local_pl.move(App.Vector(*v))

        elif node_type == "rotate":
            a = node.params.get("a", 0)
            v = node.params.get("v", [0,0,1])
            local_pl.Rotation = App.Rotation(App.Vector(*v), a)

        elif node_type == "scale":
            s = node.params.get("v", [1,1,1])
            m = App.Matrix()
            m.A11, m.A22, m.A33 = s
            local_pl = App.Placement(m)


        # PARSING SHOULD NOW HAVE CREATED MAtrix
        # elif node_type == "multmatrix":
        #    dump_ast_node(node)
        #    m = node.params.get("matrix")
        #    mat = App.Matrix()
        #    mat.A11, mat.A12, mat.A13, mat.A14 = m[0]
        #    mat.A21, mat.A22, mat.A23, mat.A24 = m[1]
        #    mat.A31, mat.A32, mat.A33, mat.A34 = m[2]
        #    trans_pl = App.Placement(mat)


        elif node_type == "multmatrix":
            dump_ast_node(node)

            m = node.params.get("matrix")
            if not isinstance(m, App.Matrix):
                raise TypeError(f"multmatrix param is not Matrix: {type(m)}")

            trans_pl = App.Placement(m)

        results = []
        write_log("Transform",f"trans_pl {trans_pl}")
        for child in node.children:
            for shape, pl in _as_list(process_AST_node(child)):
                return_pl = trans_pl.multiply(pl)
                write_log("Transform",f"Return_pl {return_pl}")
                results.append((shape, return_pl))
        return results

    # -----------------------------
    # EXTRUSIONS
    # -----------------------------
    if node_type in ("linear_extrude", "rotate_extrude"):
        write_log("Extrusion",node_type)
        if node_type == "linear_extrude":
            write_log("Extrusion", node_type)
            p = node.params
            height = p.get("height", 1)
            center = p.get("center", False)
            twist = p.get("twist", 0)      # degrees

            solids = []

            for child in node.children:
                for shape, pl in _as_list(process_AST_node(child)):
                    s = shape.copy()
                    s.Placement = pl  # children already have transforms applied

                    # Expect Wire or Face
                    if isinstance(s, Part.Wire):
                        face = Part.Face(s)
                    elif isinstance(s, Part.Face):
                        face = s
                    else:
                        write_log("Extrusion", f"Skipping non-face/wire child: {s}")
                        continue

                    # ---- Fast path: no twist
                    if twist == 0:
                        solid = face.extrude(App.Vector(0, 0, height))
                    else:
                        # ---- Slow path: twist present -> use loft along segments
                        segments = max(int(abs(twist) / 5), 1)  # 5° per step
                        layers = []
                        for i in range(segments + 1):
                            z = height * i / segments
                            angle = twist * i / segments
                            # rotate face for twist
                            rotated_face = face.copy()
                            rotated_face.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
                            # translate along Z
                            rotated_face.translate(App.Vector(0, 0, z))
                            layers.append(rotated_face)

                        # loft through layers
                        solid = Part.makeLoft(layers, True, True)

                    # ---- Center after extrusion using bounding box
                    if center:
                        bb = solid.BoundBox
                        dz = (bb.ZMin + bb.ZMax) / 2
                        solid.translate(App.Vector(0, 0, -dz))

                    solids.append(solid)

            if not solids:
                return []

            # fuse all child extrusions
            result = solids[0]
            for s in solids[1:]:
                result = result.fuse(s)

            return (result, local_pl)

        if node_type == "rotate_extrude":
            write_log("Extrusion", node_type)
            p = node.params
            angle = p.get("angle", 360)     # degrees
            center = p.get("center", False)
            segments = max(int(abs(angle) / 5), 8)  # 5° per segment, min 8

            solids = []

            for child in node.children:
                for shape, pl in _as_list(process_AST_node(child)):
                    s = shape.copy()
                    s.Placement = pl  # transforms already applied

                    # Expect Wire or Face
                    if isinstance(s, Part.Wire):
                        face = Part.Face(s)
                    elif isinstance(s, Part.Face):
                        face = s
                    else:
                        write_log("Extrusion", f"Skipping non-face/wire child: {s}")
                        continue

                    # ---- Fast path: full rotation with single segment
                    if angle == 360:
                        solid = face.revolve(App.Vector(0,0,0), App.Vector(0,0,1), angle)
                    else:
                        # ---- Slow path: partial rotation or segments
                        step_angle = angle / segments
                        layers = [face]
                        for i in range(1, segments + 1):
                            rotated = face.copy()
                            rotated.rotate(App.Vector(0,0,0), App.Vector(0,0,1), step_angle * i)
                            layers.append(rotated)

                        solid = Part.makeLoft(layers, True, True)

                    # ---- Center after extrusion using bounding box
                    if center:
                        bb = solid.BoundBox
                        dz = (bb.ZMin + bb.ZMax) / 2
                        solid.translate(App.Vector(0, 0, -dz))

                    solids.append(solid)

            if not solids:
                return []

            # fuse all child extrusions
            result = solids[0]
            for s in solids[1:]:
                result = result.fuse(s)

            return (result, local_pl)

    # -----------------------------
    # BOOLEANS
    # -----------------------------
    if node_type in ("union", "difference", "intersection"):
        write_log("Boolean",node_type)
        shapes = []
        for child in node.children:

            lst = _as_list(process_AST_node(child))
            dump_nodes_list(node_type, lst)
            for shape, pl in _as_list(process_AST_node(child)):
                s = shape.copy()
                s.Placement = pl
                write_log(node_type,f"Child {child} Placement {pl}")
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

        # ???? placement
        return (result, local_pl)

    # -----------------------------
    # 2D 
    # -----------------------------

    # Alternate uses Draft
    #
    # Alternate Import uses : mycircle = Draft.makeCircle(r,face=True) # would call doc.recompute
    # When $fn setting to interpet as a polygon

    #mycircle = Draft.makePolygon(n,r) # would call doc.recompute
    #    mycircle = FreeCAD.ActiveDocument.addObject("Part::Part2DObjectPython",'polygon')
    #    Draft._Polygon(mycircle)
    #    mycircle.FacesNumber = n
    #    mycircle.Radius = r
    #    mycircle.DrawMode = "inscribed"
    #    mycircle.MakeFace = True
    elif node.node_type == "circle":
        write_log("AST", f"Processing Circle: params={node.params}, csg={node.csg_params}")

        # Determine radius
        if "r" in node.params:
            r = node.params["r"]
        elif "d" in node.params:
            r = node.params["d"] / 2.0
        else:
            try:
                r = float(node.csg_params.strip())
            except Exception:
                r = 1.0
                write_log("AST", "Circle missing radius, defaulting to 1")

        # Make the wire in canonical XY plane
        # Using Draft 
        part2D = Draft.makeCircle(r,face=True)
        face = part2D.Shape
        # Using Part
        #face = Part.makeCircle(r, Vector(0, 0, 0), Vector(0, 0, 1))
        #
        #face = Part.Face(edge)
        # Return as a **list of tuples** — this satisfies _as_list and downstream code
        return face, local_pl

    elif node.node_type == "square":
        write_log("AST", f"Processing Square: params={node.params}, csg={node.csg_params}")

        if "size" in node.params:
            size = node.params["size"]
        else:
            try:
                size = float(node.csg_params.strip())
            except Exception:
                size = 1.0
                write_log("AST", "Square missing size, defaulting to 1")

        if isinstance(size, (int, float)):
            width = height = float(size)
        elif isinstance(size, (list, tuple)) and len(size) == 2:
            width, height = float(size[0]), float(size[1])
        else:
            width = height = 1.0
            write_log("AST", f"Invalid square size {size}, defaulting to 1")

        wire = Part.makePolygon([
            Vector(0, 0, 0),
            Vector(width, 0, 0),
            Vector(width, height, 0),
            Vector(0, height, 0),
            Vector(0, 0, 0)
        ])
        wire.Placement = local_pl
        face = Part.Face(wire)
        return face, local_pl


    # Polygon
    # With and without Path ?
    '''
    def p_polygon_action_nopath(p) :
        'polygon_action_nopath : polygon LPAREN points EQ OSQUARE points_list_2d ESQUARE COMMA paths EQ undef COMMA keywordargument_list RPAREN SEMICOL'
        if printverbose: print("Polygon")
        if printverbose: print(p[6])
        v = convert_points_list_to_vector(p[6])
        mypolygon = doc.addObject('Part::Feature',p[1])
        if printverbose: print("Make Parts")
        # Close Polygon
        v.append(v[0])
        parts = Part.makePolygon(v)
        if printverbose: print("update object")
        mypolygon.Shape = Part.Face(parts)
        p[0] = [mypolygon]

    def p_polygon_action_plus_path(p) :
        'polygon_action_plus_path : polygon LPAREN points EQ OSQUARE points_list_2d ESQUARE COMMA paths EQ OSQUARE path_set ESQUARE COMMA keywordargument_list RPAREN SEMICOL'
        if printverbose: print(f"Polygon with Path : len {len(p[6])} {p[6]}")
        v = convert_points_list_to_vector(p[6])
        # Make sure a closed list
        v.append(v[0])
        if printverbose: print(f"Path Set List {p[12]}")
        for i in p[12] :
            if printverbose: print(f"Set entry {i}")
            mypolygon = doc.addObject('Part::Feature','wire')
            path_list = []
            for j in i :
                j = int(j)
                if printverbose: print(f"index {j}")
                path_list.append(v[j])
    #        Close path
            path_list.append(v[int(i[0])])
            if printverbose: print(f"Path List {path_list}")
            wire = Part.makePolygon(path_list)
            mypolygon.Shape = Part.Face(wire)
            p[0] = [mypolygon]
    #        This only pushes last polygon
    '''

    # -----------------------------
    # FALLBACK
    # -----------------------------
    results = []
    for child in getattr(node, "children", []):
        results.extend(_as_list(process_AST_node(child)))
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

        write_log("Dump",f"processed type {type(processed)}")
        write_log("Dump",f"{processed}")
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
