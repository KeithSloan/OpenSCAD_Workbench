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
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import *
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import ast

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
def parse_csg_lines(lines, start=0):
    """
    Recursively parse lines from a CSG file.
    Returns: (list of AstNode, next_line_index)
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

        # Match node type and params
        m = re.match(r"(\w+)\s*\((.*)\)\s*({)?", line)
        if not m:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type, param_str, brace = m.groups()
        node_type = node_type.lower()
        csg_params = param_str.strip()

        # --- Parse params ---
        if node_type == "multmatrix":
            try:
                matrix = eval(csg_params)
                params = {"matrix": matrix}
            except Exception:
                params = {"matrix": [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}
            has_children = True
        else:
            params = parse_csg_params(param_str)
            has_children = bool(brace)

        # --- Determine class ---
        cls = {
            "cube": Cube,
            "sphere": Sphere,
            "cylinder": Cylinder,
            "polyhedron": Polyhedron,
            "circle": Circle,
            "square": Square,
            "polygon": Polygon,
            "union": Union,
            "difference": Difference,
            "intersection": Intersection,
            "hull": Hull,
            "minkowski": Minkowski,
            "group": Group,
            "translate": Translate,
            "rotate": Rotate,
            "scale": Scale,
            "multmatrix": MultMatrix,
            "linear_extrude": LinearExtrude,
            "rotate_extrude": RotateExtrude,
        }.get(node_type, AstNode)

        # --- Parse children ---
        children = []
        if has_children:
            children, i = parse_csg_lines(lines, i + 1)
        else:
            i += 1

        # --- Instantiate node ---
        try:
            if node_type == "sphere":
                r = params.get("r", 1)
                fn = params.get("$fn")
                fa = params.get("$fa")
                fs = params.get("$fs")
                node = cls(r=r, fn=fn, fa=fa, fs=fs, params=params, csg_params=csg_params)

            elif node_type == "cube":
                try:
                    # --- Normalize size ---
                    raw_size = params.get("size", 1)
                    size = normalizeScalarOrVector(raw_size, length=3, name="cube.size")

                    # --- Normalize center ---
                    center = normalizeBool(params.get("center", False))

                    # --- Logging ---
                    write_log(
                        "AST",
                        f"cube size={size} center={center} csg_params={csg_params}"
                    )

                    node = cls(
                        size=size,
                        center=center,
                        params=params,
                        csg_params=csg_params
                    )

                except Exception as e:
                    FreeCAD.Console.PrintError(f"[AST:cube] Failed to parse cube: {e}\n")
                    node = AstNode(
                        node_type="cube_failed",
                        params=params,
                        csg_params=csg_params
                    )

            elif node_type == "cylinder":
                h = params.get("h", 1)
                r = params.get("r")
                r1 = params.get("r1")
                r2 = params.get("r2")
                center = params.get("center", False)
                fn = params.get("$fn")
                fa = params.get("$fa")
                fs = params.get("$fs")
                node = cls(h=h, r=r, r1=r1, r2=r2, center=center, fn=fn, fa=fa, fs=fs, params=params, csg_params=csg_params)

            elif node_type == "multmatrix":
                node = cls(matrix=params.get("matrix"), children=children, params=params, csg_params=csg_params)

            elif node_type in ("translate", "rotate", "scale"):
                node = cls(
                    vector=params.get("vector"),
                    angle=params.get("angle") if node_type == "rotate" else None,
                    children=children,
                    params=params,
                    csg_params=csg_params
                )

            else:
                # generic node or boolean operations
                node = cls(children=children, params=params, csg_params=csg_params)

        except Exception as e:
            write_log("CSG_PARSE", f"Failed to instantiate node {node_type}: {e}")
            node = AstNode(node_type, params=params, csg_params=csg_params, children=children)

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

