# -*- coding: utf-8 -*-
"""
Parse a FreeCAD OpenSCAD CSG file into AST nodes
------------------------------------------------

Usage:
    from ast_nodes import AstNode, Sphere, Hull, MultMatrix, ...
    nodes = parse_csg_file_to_AST_nodes(filename)
"""
import FreeCAD
import re
import ast
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import AstNode, Cube, Sphere, Cylinder, Union, Difference, Intersection
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import Group, Translate, Rotate, Scale, MultMatrix, Hull, Minkowski
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import LinearExtrude, RotateExtrude, Color

# --- parse_scad_argument and parse_csg_params assumed defined here ---

def parse_scad_argument(arg_str):
    """
    Convert a single OpenSCAD argument string to a number, boolean, or vector.

    Handles:
      - Scalar numbers: "20" -> 20
      - Float numbers: "3.14" -> 3.14
      - Boolean literals: "true" -> True, "false" -> False
      - Vectors: "[10,20,30]" -> [10.0, 20.0, 30.0]
      - Fallback: returns original string if none of the above

    Examples:
        "20" -> 20
        "[10,20,30]" -> [10.0,20.0,30.0]
        "true" -> True
        "false" -> False
    """
    arg_str = arg_str.strip()

    # Boolean literals
    if arg_str.lower() == "true":
        return True
    if arg_str.lower() == "false":
        return False

    # Try numeric literal
    try:
        if "." in arg_str:
            return float(arg_str)
        else:
            return int(arg_str)
    except ValueError:
        pass

    # Try vector literal
    if arg_str.startswith("[") and arg_str.endswith("]"):
        try:
            vec = ast.literal_eval(arg_str)
            if isinstance(vec, (list, tuple)):
                return [float(x) for x in vec]
        except Exception:
            pass

    # fallback: return string (e.g., a name or keyword)
    return arg_str

# -------------------------------------------------
# Helper: parse a single OpenSCAD argument
# -------------------------------------------------
def parse_csg_params(param_str):
    """
    Converts a param string like 'r=10, $fn=6, center=false' to a dict
    Converts numbers, vectors, and booleans to proper types for FreeCAD
    """
    params = {}
    if not param_str:
        return params

    for part in split_top_level_commas(param_str):
        if "=" not in part:
            params[part] = None
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        params[k] = parse_scad_argument(v)

    return params

def normalizeBool(val):
    """
    Normalize OpenSCAD boolean-like values.
    Accepts: True/False, "true"/"false", 1/0
    Returns: Python bool
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v == "true":
            return True
        elif v == "false":
            return False
    # fallback
    return False



def normalizeScalarOrVector(value, length=3, name="size"):
    """
    Normalize OpenSCAD-style scalar or vector parameters.

    Accepts:
      - number: 10
      - numeric string: "10"
      - vector: [10,20,30]
      - vector string: "[10,20,30]"

    Returns:
      - float          (scalar)
      - list[float]    (vector)

    Raises:
      ValueError on invalid input
    """

    # Already numeric
    if isinstance(value, (int, float)):
        return float(value)

    # Vector
    if isinstance(value, (list, tuple)):
        if len(value) != length:
            raise ValueError(
                f"{name} must have {length} elements, got {len(value)}"
            )
        return [float(v) for v in value]

    # String input
    if isinstance(value, str):
        v = value.strip()

        # Numeric string
        try:
            return float(v)
        except ValueError:
            pass

        # Vector string
        if v.startswith("[") and v.endswith("]"):
            try:
                vec = eval(v, {}, {})
            except Exception:
                raise ValueError(f"Invalid vector literal for {name}: {value}")

            if not isinstance(vec, (list, tuple)) or len(vec) != length:
                raise ValueError(
                    f"{name} must be [{length}] values, got {vec}"
                )
            return [float(x) for x in vec]

    raise ValueError(f"Invalid {name} value: {value}")

# -------------------------------------------------
# Recursive parser
# -------------------------------------------------
# --- Split top-level commas, ignoring commas in brackets
def split_top_level_commas(s):
    parts = []
    buf = ""
    level = 0
    for c in s:
        if c == "[":
            level += 1
        elif c == "]":
            level -= 1
        if c == "," and level == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += c
    if buf:
        parts.append(buf.strip())
    return parts


# -------------------------------
# Main recursive parser
# -------------------------------

# -*- coding: utf-8 -*-
# Drop-in replacement for parse_csg_lines

# -------------------------------
# Main recursive parser
# -------------------------------
'''
import re
import ast
import FreeCAD

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import AstNode, Cube, Sphere, Cylinder, Union, Difference, Intersection
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import Group, Translate, Rotate, Scale, MultMatrix, Hull, Minkowski
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import LinearExtrude, RotateExtrude, Color
'''

def parse_csg_params(param_str):
    """
    Parse OpenSCAD-style parameters like:
        size = [8.5, 1, 1], center = true
    Returns: dict
    """
    params = {}
    if not param_str:
        return params

    # Split by commas not inside brackets
    parts = re.split(r",(?![^\[\]]*\])", param_str)
    for part in parts:
        if '=' not in part:
            continue
        key, val = map(str.strip, part.split('=', 1))
        # Convert OpenSCAD literals to Python
        if val.lower() == 'true':
            val = True
        elif val.lower() == 'false':
            val = False
        else:
            try:
                val = ast.literal_eval(val)
            except Exception:
                pass  # leave as string if cannot eval
        params[key] = val
    return params

# -*- coding: utf-8 -*-
# Recursive CSG parser for FreeCAD AST
# -------------------------------
# Main recursive CSG parser
# -------------------------------
import re
import ast
import FreeCAD

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    AstNode, Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Group, Translate, Rotate, Scale,
    MultMatrix, Hull, Minkowski,
    LinearExtrude, RotateExtrude, Color
)

def parse_csg_lines(lines, start=0):
    """
    Recursively parse CSG lines into AST nodes.
    Returns: (list_of_nodes, next_line_index)
    """
    nodes = []
    i = start

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if line.startswith("}"):
            return nodes, i + 1

        # Match: node(params) {?
        m = re.match(r"(\w+)\s*\((.*)\)\s*({)?", line)
        if not m:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type, param_str, brace = m.groups()
        node_type = node_type.lower()
        csg_params = param_str.strip()

        # --- Determine class ---
        cls = {
            "cube": Cube,
            "sphere": Sphere,
            "cylinder": Cylinder,
            "union": Union,
            "difference": Difference,
            "intersection": Intersection,
            "group": Group,
            "translate": Translate,
            "rotate": Rotate,
            "scale": Scale,
            "multmatrix": MultMatrix,
            "hull": Hull,
            "minkowski": Minkowski,
            "linear_extrude": LinearExtrude,
            "rotate_extrude": RotateExtrude,
            "color": Color,
        }.get(node_type, AstNode)

        # --- Parse children ---
        children = []
        if brace:
            children, i = parse_csg_lines(lines, i + 1)
        else:
            i += 1

        # --- Parse parameters ---
        params = {}

        # =========================
        # MULTMATRIX (special)
        # =========================
        if node_type == "multmatrix":
            try:
                matrix = ast.literal_eval(csg_params)
                if (
                    not isinstance(matrix, list)
                    or len(matrix) != 4
                    or any(len(row) != 4 for row in matrix)
                ):
                    raise ValueError("multmatrix is not 4x4")
            except Exception as e:
                write_log("CSG_PARSE", f"Failed to parse multmatrix: {e}")
                matrix = [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]

            params["matrix"] = matrix

            node = MultMatrix(
                matrix=matrix,
                children=children,
                params=params,
                csg_params=csg_params,
            )

            write_log(
                "AST",
                f"multmatrix csg_params={csg_params}, params['matrix']={matrix}",
            )

        # =========================
        # PRIMITIVES (NO children)
        # =========================
        elif node_type == "cube":
            params = parse_csg_params(param_str)
            raw_size = params.get("size", 1)
            size = normalizeScalarOrVector(raw_size, length=3, name="cube.size")
            center = normalizeBool(params.get("center", False))

            node = Cube(
                size=size,
                center=center,
                params=params,
                csg_params=csg_params,
            )

        elif node_type == "sphere":
            params = parse_csg_params(param_str)
            node = Sphere(
                r=params.get("r"),
                params=params,
                csg_params=csg_params,
            )

        elif node_type == "cylinder":
            params = parse_csg_params(param_str)
            node = Cylinder(
                r=params.get("r"),
                h=params.get("h"),
                center=params.get("center", False),
                params=params,
                csg_params=csg_params,
            )

        # =========================
        # TRANSFORMS / CSG NODES
        # =========================
        else:
            params = parse_csg_params(param_str)

            if node_type in ("translate", "scale"):
                node = cls(
                    vector=params.get("vector"),
                    children=children,
                    params=params,
                    csg_params=csg_params,
                )

            elif node_type == "rotate":
                node = Rotate(
                    vector=params.get("vector"),
                    angle=params.get("angle"),
                    children=children,
                    params=params,
                    csg_params=csg_params,
                )

            else:
                node = cls(
                    children=children,
                    params=params,
                    csg_params=csg_params,
                )

        nodes.append(node)

    return nodes, i


# -------------------------------------------------
# Main parser
# -------------------------------------------------
def parse_csg_file_to_AST_nodes(filename):
    """
    Reads a .csg file and returns a list of AstNode objects
    """
    write_log("CSG_PARSE", f"Parsing CSG file: {filename}")
    with open(filename, "r") as f:
        lines = f.readlines()
    nodes, _ = parse_csg_lines(lines, start=0)
    write_log("CSG_PARSE", f"Parsed {len(nodes)} top-level nodes")
    return nodes

