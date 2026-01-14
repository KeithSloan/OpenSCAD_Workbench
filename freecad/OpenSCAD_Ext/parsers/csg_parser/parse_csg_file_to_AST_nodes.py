#---------------------------------
# See notes at the end of the file
# --------------------------------
# parse_csg_file_to_AST_nodes.py
import re
import ast as py_ast
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
# ----------------------------
# AST Nodes
# ----------------------------
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    # 2D
    Circle, Square, Polygon,
    # 3D
    Cube, Sphere, Cylinder, Polyhedron,
    # CSG
    Union, Difference, Intersection, Hull, Minkowski, Group,
    # Transforms
    Translate, Rotate, Scale, MultMatrix,
    # Extrude
    LinearExtrude, RotateExtrude,
)

# -----------------------------------------
# helper function -> ast_helpers.py ?? !!!!
# -----------------------------------------


def safe_eval_list(text, fallback):
    """Safely evaluate a Python-style list literal."""
    try:
        val = py_ast.literal_eval(text)
        if isinstance(val, list):
            return val
    except Exception:
        pass
    return fallback

#def parse_vector_safe(text, dim=None, fallback=None):
# update for parse_vector

def parse_vector(text, dim=None, fallback=None):
    """
    Parse [x,y,z] or [x,y] safely.
    Always returns a list.
    """
    if fallback is None:
        fallback = [0.0] * (dim or 3)

    vec = safe_eval_list(text, fallback)
    if dim is not None and len(vec) != dim:
        write_log("Warn", f"Vector length mismatch: {vec}")
        return fallback
    return vec

# def parse_matrix_safe(text, fallback=None):
# update for parse_matrix

def parse_matrix(text, fallback=None):
    """
    Parse [[...],[...],[...],[...]] safely.
    Always returns a 4x4 matrix.
    """
    if fallback is None:
        fallback = [
            [1,0,0,0],
            [0,1,0,0],
            [0,0,1,0],
            [0,0,0,1],
        ]

    mat = safe_eval_list(text, fallback)
    if (
        isinstance(mat, list)
        and len(mat) == 4
        and all(isinstance(r, list) and len(r) == 4 for r in mat)
    ):
        return mat

    write_log("Warn", f"Invalid matrix, using identity: {text}")
    return fallback


# Example (from csg_parser.py or similar)

def normalize_ast(node):
    """
    Recursively normalize raw AST into Node objects.
    Ensures that all children are Node instances, never raw lists.
    """
    from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import Node, Group

    if isinstance(node, list):
        # Wrap raw list into a Group node
        normalized_children = []
        for n in node:
            normalized_children.append(normalize_ast(n))
        return Group(children=normalized_children)

    elif isinstance(node, Node):
        # Already a node, normalize its children
        if hasattr(node, "children") and node.children:
            node.children = [normalize_ast(c) for c in node.children]
        return node

    else:
        # Unknown type, wrap into a Group with a placeholder node
        return Group(children=[node])

# ----------------------------
# Main parser
# ----------------------------
def parse_csg_file_to_AST_nodes(filename):
    write_log("Info", f"Parsing CSG file: {filename}")

    with open(filename, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("//")]

    def parse_block(idx):
        nodes = []
        while idx < len(lines):
            line = lines[idx]

            if line.startswith("}"):
                return nodes, idx + 1

            # -------------------------
            # 2D Primitives
            # -------------------------
            if line.startswith("circle"):
                r_match = re.search(r"r\s*=\s*([\d\.]+)", line)
                r = float(r_match.group(1)) if r_match else 1.0
                nodes.append(Circle(r=r))
                idx += 1
                continue

            if line.startswith("square"):
                size_match = re.search(r"size\s*=\s*(\[[^\]]*\])", line)
                size = parse_vector(size_match.group(1)) if size_match else [1,1]
                nodes.append(Square(size=size))
                idx += 1
                continue

            if line.startswith("polygon"):
                pts_m = re.search(r"points\s*=\s*(\[.*\])", line)
                paths_m = re.search(r"paths\s*=\s*(\[.*\])", line)
                pts = parse_vector(pts_m.group(1)) if pts_m else []
                paths = parse_vector(paths_m.group(1)) if paths_m else []
                nodes.append(Polygon(points=pts, paths=paths))
                idx += 1
                continue

            # -------------------------
            # 3D Primitives
            # -------------------------
            if line.startswith("cube"):
                size_match = re.search(r"size\s*=\s*(\[[^\]]*\])", line)
                size = parse_vector(size_match.group(1)) if size_match else [1,1,1]

                center_match = re.search(r"center\s*=\s*(true|false)", line, re.IGNORECASE)
                center = center_match.group(1).lower() == "true" if center_match else False

                nodes.append(Cube(size=size, center=center))
                idx += 1
                continue

            if line.startswith("sphere"):
                r_match = re.search(r"r\s*=\s*([\d\.]+)", line)
                r = float(r_match.group(1)) if r_match else 1.0
                nodes.append(Sphere(r=r))
                idx += 1
                continue

            if line.startswith("cylinder"):
                r_match = re.search(r"r\s*=\s*([\d\.]+)", line)
                h_match = re.search(r"h\s*=\s*([\d\.]+)", line)
                r = float(r_match.group(1)) if r_match else 1.0
                h = float(h_match.group(1)) if h_match else 1.0

                center_match = re.search(r"center\s*=\s*(true|false)", line, re.IGNORECASE)
                center = center_match.group(1).lower() == "true" if center_match else False

                nodes.append(Cylinder(r=r, h=h, center=center))
                idx += 1
                continue

            if line.startswith("polyhedron"):
                pts_m = re.search(r"points\s*=\s*(\[.*\])", line)
                faces_m = re.search(r"faces\s*=\s*(\[.*\])", line)
                pts = parse_vector(pts_m.group(1)) if pts_m else []
                faces = parse_vector(faces_m.group(1)) if faces_m else []
                nodes.append(Polyhedron(points=pts, faces=faces))
                idx += 1
                continue

            # -------------------------
            # CSG / Block nodes
            # -------------------------
            block_nodes = {
                "union": Union,
                "difference": Difference,
                "intersection": Intersection,
                "hull": Hull,
                "minkowski": Minkowski,
                "group": Group,
            }
            for key, cls in block_nodes.items():
                if line.startswith(key):
                    idx += 1
                    if idx < len(lines) and lines[idx].startswith("{"):
                        idx += 1
                    children, idx = parse_block(idx)
                    nodes.append(cls(children))
                    break
            else:
                # -------------------------
                # Transform nodes
                # -------------------------
                if line.startswith("translate"):
                    vec = parse_vector(re.search(r"\((.*)\)", line).group(1))
                    idx += 1
                    if idx < len(lines) and lines[idx].startswith("{"):
                        idx += 1
                    children, idx = parse_block(idx)
                    nodes.append(Translate(vec, children))
                    continue

                if line.startswith("scale"):
                    vec = parse_vector(re.search(r"\((.*)\)", line).group(1))
                    idx += 1
                    if idx < len(lines) and lines[idx].startswith("{"):
                        idx += 1
                    children, idx = parse_block(idx)
                    nodes.append(Scale(vec, children))
                    continue

                if line.startswith("rotate"):
                    vec = parse_vector(re.search(r"\((.*)\)", line).group(1))
                    idx += 1
                    if idx < len(lines) and lines[idx].startswith("{"):
                        idx += 1
                    children, idx = parse_block(idx)
                    nodes.append(Rotate(vec, None, children))
                    continue

                if line.startswith("multmatrix"):
                    mat = parse_matrix(re.search(r"\((\[\[.*\]\])\)", line).group(1))
                    idx += 1
                    if idx < len(lines) and lines[idx].startswith("{"):
                        idx += 1
                    children, idx = parse_block(idx)
                    nodes.append(MultMatrix(mat, children))
                    continue

                # Skip unsupported lines
                write_log("Info", f"Skipping unsupported line: {line}")
                idx += 1

        return nodes, idx

    nodes, _ = parse_block(0)

    # -------------------------
    # Normalize AST
    # -------------------------
    ast_nodes = []
    for n in nodes:
        nn = normalize_ast(n)
        if nn:
            ast_nodes.append(nn)

    write_log("Info", f"AST nodes after normalize: {len(ast_nodes)}")
    return ast_nodes

    """
OpenSCAD CSG Import Pipeline for FreeCAD
----------------------------------------

This module implements the parsing and processing of OpenSCAD CSG (.csg) files
into FreeCAD Part objects. The pipeline consists of several stages, each handled
by specific functions across different modules.  

Pipeline Steps:

1. Read CSG File
----------------
Module: importASTCSG.py
Function: processCSG(doc, filename)
Purpose:
    - Opens the .csg file
    - Reads lines, strips whitespace and comments
Notes:
    - Produces a list of cleaned lines for parsing
    - Does not interpret or validate content

2. Parse Block Lines
-------------------
Module: parse_csg_file_to_AST_nodes.py
Function: parse_block(idx)
Purpose:
    - Recursively parses lines into AST nodes
    - Detects primitives (cube, sphere, cylinder, etc.)
    - Detects 2D shapes (circle, square, polygon)
    - Detects CSG blocks (union, difference, intersection, hull, minkowski, group)
    - Detects transforms (translate, rotate, scale, multmatrix)
Notes:
    - Recursion handles nested blocks
    - Returns a list of AST node objects and next line index

3. Regex Parameter Extraction
-----------------------------
Module: parse_csg_file_to_AST_nodes.py
Location: inside parse_block()
Purpose:
    - Extracts numeric or vector parameters from lines
      e.g., cube(size=[7,17,1]) -> [7,17,1]
    - Handles $fn, r, h, points, faces, etc.
Notes:
    - Regex failures can result in missing parameters (None)
    - Missing or malformed parameters will trigger TypeError downstream

4. Build AST Nodes
-----------------
Module: parse_csg_file_to_AST_nodes.py
Location: inside parse_block()
Purpose:
    - Instantiates AST node objects (Cube, Sphere, Cylinder, Hull, Translate, etc.)
    - Assigns extracted parameters and child nodes
    - Creates tree structure representing the CSG model

5. Normalize AST
----------------
Module: parse_csg_file_to_AST_nodes.py
Function: normalize_ast(node)
Purpose:
    - Simplifies AST by:
        - Dropping empty transparent nodes (Group, Translate, Rotate, Scale)
        - Collapsing single-child transparent nodes
    - Ensures tree is minimal for easier processing
Notes:
    - Does not fix missing primitive parameters
    - Useful for reducing unnecessary nesting

6. Process AST Nodes to FreeCAD Shapes
--------------------------------------
Module: processAST.py
Function: process_AST_node(node)
Returns: Shapes
Purpose:
    - Converts AST nodes into FreeCAD Part shapes
    - Handles primitives, booleans, hulls/minkowski, and transforms
    - Fallback to OpenSCAD if native BRep fails for hull/minkowski
Key functions:
    - create_primitive(node)  → Converts Cube, Sphere, Cylinder, etc. to Part.Shape
    - create_boolean(node)    → Performs Union, Difference, Intersection
    - process_hull(node)      → Tries native BRep hull, fallback to OpenSCAD
    - process_minkowski(node) → Tries native BRep Minkowski, fallback to OpenSCAD

7. Combine and Output FreeCAD Objects
-------------------------------------
Module: processAST.py
Function: process_AST(doc, ast_nodes, mode)
Purpose:
    - Combines all processed shapes into a single Part::Feature
    - Or returns multiple objects if mode="objects" or "multiple"
Notes:
    - Final FreeCAD objects are inserted into the active document
    - Shape may be a BRep or imported from OpenSCAD fallback
"""
