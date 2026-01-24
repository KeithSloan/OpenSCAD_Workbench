# -*- coding: utf-8 -*-
"""
Parse a FreeCAD OpenSCAD CSG file into AST nodes
------------------------------------------------

Usage:
    from ast_nodes import AstNode, Sphere, Hull, MultMatrix, ...
    nodes = parse_csg_file_to_AST_nodes(filename)
"""
#import FreeCAD
import re
import ast
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import AstNode, Cube, Sphere, Cylinder, Union, Difference, Intersection
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import Group, Translate, Rotate, Scale, MultMatrix, Hull, Minkowski
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import LinearExtrude, RotateExtrude, Color, UnknownNode

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
'''
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
'''

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

# -*- coding: utf-8 -*-
# Recursive CSG parser for FreeCAD AST
# -------------------------------
# Main recursive CSG parser
# -------------------------------

import re
import ast

def parse_csg_params(param_str):
    """
    Parse OpenSCAD parameter string into:
        - params: dict of named args (for B-Rep creation)
        - csg_params: positional args (raw, for OpenSCAD callback)
    
    Examples:
        "10"          -> params={},          csg_params=10
        "[10,20,30]"  -> params={},          csg_params=[10,20,30]
        "size=10"     -> params={"size":10}, csg_params=None
        "10, center=true" -> params={"center":True}, csg_params=10
    """

    params = {}
    csg_params = None

    if not param_str or param_str.strip() == "":
        return params, csg_params

    # Split on commas not inside brackets/parentheses
    # Simple parser using regex for top-level commas
    tokens = re.split(r",(?![^\[\(]*[\]\)])", param_str)

    positional_tokens = []
    for tok in tokens:
        tok = tok.strip()
        if "=" in tok:
            # keyword argument
            key, val = tok.split("=", 1)
            key = key.strip()
            val = val.strip()

            try:
                # Safely evaluate literals: numbers, lists, bool
                val_eval = ast.literal_eval(val)
            except Exception:
                val_eval = val  # fallback, keep string

            params[key] = val_eval
        else:
            # positional argument
            positional_tokens.append(tok)

    # Determine csg_params
    if positional_tokens:
        # Single positional arg -> scalar/list
        if len(positional_tokens) == 1:
            try:
                csg_params = ast.literal_eval(positional_tokens[0])
            except Exception:
                csg_params = positional_tokens[0]
        else:
            # multiple positional args -> list
            evaled = []
            for t in positional_tokens:
                try:
                    evaled.append(ast.literal_eval(t))
                except Exception:
                    evaled.append(t)
            csg_params = evaled

    return params, csg_params


import re

NODE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(\((.*)\))?\s*(\{)?")

def parse_csg_lines(lines, start=0):
    """
    Recursively parse CSG lines into AST nodes.
    Returns: (list_of_nodes, next_line_index)
    """
    nodes = []
    i = start

    while i < len(lines):
        line = lines[i].strip()

        # -----------------------------
        # End of current block
        # -----------------------------
        if line.startswith("}"):
            return nodes, i + 1

        # Skip empty / comment lines
        if not line or line.startswith("//"):
            i += 1
            continue

        # -----------------------------
        # Parse node header inline
        # -----------------------------
        m = NODE_RE.match(line)
        if not m:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type = m.group(1).lower()
        raw_csg_params = m.group(3)  # may be None
        opens_block = m.group(4) is not None

        # -----------------------------
        # Parse children if block
        # -----------------------------
        children = []
        if opens_block:
            children, i = parse_csg_lines(lines, i + 1)

        # -----------------------------
        # Parse params (for B-Rep)
        # -----------------------------
        try:
            params, _ = parse_csg_params(raw_csg_params)
        except Exception as e:
            write_log(
                "CSG_PARSE",
                f"Failed to parse params for '{node_type}': {e}"
            )
            params = {}

        # -----------------------------
        # Handle Cube defaults separately
        # -----------------------------
        if node_type == "cube":
            # Positional / default handling
            if "size" not in params:
                s = raw_csg_params.strip() if raw_csg_params else ""
                if s:
                    try:
                        params["size"] = ast.literal_eval(s)
                    except Exception:
                        write_log("CSG_PARSE", f"Failed to eval cube size: {s}")
                        params["size"] = 1
                else:
                    params["size"] = 1
            params.setdefault("center", False)

        # -----------------------------
        # Determine node class
        # -----------------------------
        NODE_CLASSES = {
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
        }

        cls = NODE_CLASSES.get(node_type)

        if cls is None:
            write_log(
                "CSG_PARSE",
                f"Unknown node '{node_type}', preserving as UnknownNode"
            )

            node = UnknownNode(
                node_type=node_type,
                params=params,
                csg_params=raw_csg_params,
            )
            node.children = children

        else:
            try:
                node = cls(
                    params=params,
                    csg_params=raw_csg_params,
                    children=children,
                )
            except TypeError:
                write_log(
                    "CSG_PARSE",
                    f"Constructor mismatch for '{node_type}', using AstNode fallback"
                )
                node = AstNode(
                    node_type=node_type,
                    params=params,
                    csg_params=raw_csg_params,
                    children=children,
                )

        nodes.append(node)

        # -----------------------------
        # Always advance
        # -----------------------------
        i += 1

    return nodes, i


def saved_parse_csg_lines(lines, start=0):
    """
    Recursively parse CSG lines into AST nodes.
    Returns: (list_of_nodes, next_line_index)
    
    Rules:
      - csg_params: raw string from CSG (for Hull/Minkowski fallback)
      - params: normalized dict for FreeCAD B-Rep creation
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
        raw_csg_params = param_str.strip()

        children = []

        # --- Determine class ---
        NODE_CLASSES = {
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
        }

        cls = NODE_CLASSES.get(node_type)

        if cls is None:
            write_log(
                "CSG_PARSE",
                f"Unknown node '{node_type}', preserving as UnknownNode"
            )

            params, _ = parse_csg_params(raw_csg_params)

            node = UnknownNode(
                node_type=node_type,
                params=params,
                csg_params=raw_csg_params,
                )

            # Preserve subtree — do NOT lose it
            node.children = children

            nodes.append(node)
            continue


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
                matrix = ast.literal_eval(raw_csg_params)
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
                csg_params=raw_csg_params,
            )

            write_log(
                "AST",
                f"multmatrix csg_params={raw_csg_params}, params['matrix']={matrix}",
            )

        # =========================
        # CUBES
        # =========================
        elif node_type == "cube":
            parsed_params, _ = parse_csg_params(raw_csg_params)
            if not isinstance(parsed_params, dict):
                parsed_params = {}

            # Handle positional / default
            if "size" not in parsed_params:
                s = raw_csg_params.strip()
                if s:
                    try:
                        parsed_params["size"] = ast.literal_eval(s)
                    except Exception:
                        write_log("CSG_PARSE", f"Failed to eval cube size: {s}")
                        parsed_params["size"] = 1
                else:
                    parsed_params["size"] = 1

            parsed_params.setdefault("center", False)

            node = Cube(
                params=parsed_params,
                csg_params=raw_csg_params,
                children=[],
            )

        # =========================
        # SPHERES
        # =========================
        elif node_type == "sphere":
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = Sphere(
                r=parsed_params.get("r"),
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        # =========================
        # CYLINDERS
        # =========================
        elif node_type == "cylinder":
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = Cylinder(
                r=parsed_params.get("r"),
                r1=parsed_params.get("r1"),
                r2=parsed_params.get("r2"),
                h=parsed_params.get("h"),
                center=parsed_params.get("center", False),
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        # =========================
        # TRANSFORMS
        # =========================
        elif node_type in ("translate", "scale"):
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = cls(
                vector=parsed_params.get("vector"),
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        elif node_type == "rotate":
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = Rotate(
                vector=parsed_params.get("vector"),
                angle=parsed_params.get("angle"),
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        elif node_type == "linear_extrude":
            params, _ = parse_csg_params(raw_csg_params)

            if "height" not in params:
                write_log(
                    "CSG_PARSE",
                    "linear_extrude missing required 'height'"
                )
                node = UnknownNode(
                    node_type=node_type,
                    children=children,
                    params=params,
                    csg_params=raw_csg_params,
                )
            else:
                node = LinearExtrude(
                    height=params["height"],
                    center=params.get("center", False),
                    twist=params.get("twist", 0),
                    scale=params.get("scale", 1.0),
                    children=children,
                    params=params,
                    csg_params=raw_csg_params,
                )

        elif node_type == "rotate_extrude":
            parsed_params, _ = parse_csg_params(raw_csg_params)

            node = RotateExtrude(
                angle=parsed_params.get("angle", 360),
                convexity=parsed_params.get("convexity"),
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        elif node_type == "color":
            parsed_params, _ = parse_csg_params(raw_csg_params)

            node = Color(
                rgb=parsed_params.get("rgb"),
                alpha=parsed_params.get("alpha", 1.0),
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
            )


        # =========================
        # ALL OTHER NODES (Booleans, Hull/Minkowski, Group, Extrusions, Color)
        # =========================
        elif cls is not None:
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = cls(
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
            )

        else:
            # ---- SAFE FALLBACK ----
            parsed_params, _ = parse_csg_params(raw_csg_params)
            node = AstNode(
                node_type=node_type,
                children=children,
                params=parsed_params,
                csg_params=raw_csg_params,
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

