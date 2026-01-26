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
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import LinearExtrude, RotateExtrude, Text, Color, Polyhedron, UnknownNode

from freecad.OpenSCAD_Ext.parsers.csg_parser.process_polyhedron import process_polyhedron

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
# -*- coding: utf-8 -*-
# Recursive CSG parser for FreeCAD AST
# -------------------------------
# Main recursive CSG parser
# -------------------------------
def split_top_level_commas(s):
    parts = []
    buf = []
    depth = 0

    pairs = {
        "[": "]",
        "(": ")",
        "{": "}",
    }

    opens = set(pairs.keys())
    closes = set(pairs.values())

    for c in s:
        if c in opens:
            depth += 1
        elif c in closes:
            depth -= 1

        if c == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)

    if buf:
        parts.append("".join(buf).strip())

    return parts

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

NODE_HEADER_RE = re.compile(
    r"""
    ^\s*
    (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)
    """,
    re.VERBOSE,
)

'''
NODE_HEADER_RE = re.compile(
    r"""
    ^\s*
    (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)   # node name
    \s*
    (?:\((?P<params>[^)]*)\))?        # optional ( ... )
    \s*
    (?P<brace>\{)?                    # optional {
    """,
    re.VERBOSE,
)
'''

def parse_csg_node_header(line):
    m = NODE_HEADER_RE.match(line)
    if not m:
        return None, None, False

    node_type = m.group("name")

    raw_csg_params = None
    opens_block = "{" in line

    # --- extract (...) safely
    start = line.find("(")
    if start != -1:
        level = 0
        buf = []
        for c in line[start + 1:]:
            if c == "(":
                level += 1
            elif c == ")":
                if level == 0:
                    break
                level -= 1
            buf.append(c)
        raw_csg_params = "".join(buf).strip()

    return node_type, raw_csg_params, opens_block

'''
def parse_csg_node_header(line):
    """
    Parse a single OpenSCAD CSG node header line.

    Returns:
        node_type (str)
        raw_csg_params (str or None)
        opens_block (bool)
    """
    m = NODE_HEADER_RE.match(line)
    if not m:
        return None, None, False

    node_type = m.group("name")
    raw_csg_params = m.group("params")
    opens_block = bool(m.group("brace"))

    return node_type, raw_csg_params, opens_block
'''

def parse_csg_lines(lines, start=0, indent=0):
    """
    Recursively parse CSG lines into AST nodes.

    Parsing happens first (params, children).
    AST nodes are constructed in ONE place using NODE_CLASSES.

    "Special" constructors are used only when the AST class
    requires extracted or transformed parameters.
    """
    nodes = []
    i = start

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
        "text": Text,
        "color": Color,
        "polyhedron": Polyhedron,
    }

    while i < len(lines):
        line = lines[i].strip()

        # ---- End of block
        if line.startswith("}") or line.startswith(");"):
            return nodes, i + 1

        # ---- Skip empty / comment
        if not line or line.startswith("//"):
            i += 1
            continue

        # ---- Parse node header
        node_type, raw_csg_params, opens_block = parse_csg_node_header(line)
        if node_type is None:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type = node_type.lower()
        children = []
        next_i = i + 1

        # ---- Parse children if block
        if opens_block:
            children, next_i = parse_csg_lines(lines, i + 1, indent + 1)

        # ---- Parse parameters
        try:
            params, csg_positional = parse_csg_params(raw_csg_params)
        except Exception as e:
            write_log("CSG_PARSE", f"Failed to parse params for '{node_type}': {e}")
            params = {}
            csg_positional = None

        # ---- Special handling: cube positional size
        if node_type == "cube":
            if "size" not in params:
                params["size"] = csg_positional if csg_positional is not None else 1
            params.setdefault("center", False)

        # ---- Determine AST class
        cls = NODE_CLASSES.get(node_type)

        if cls is None:
            write_log("CSG_PARSE", f"Unknown node '{node_type}', preserving as UnknownNode")
            node = UnknownNode(
                node_type=node_type,
                params=params,
                csg_params=raw_csg_params,
                children=children
            )
        else:
            try:
                # ---- Special constructors (signature differs)

                if node_type in ("translate", "scale", "rotate"):
                    node = cls(
                        vector=params.get("vector"),
                        angle=params.get("angle"),
                        children=children,
                        params=params,
                        csg_params=raw_csg_params
                    )

                elif node_type in ("linear_extrude", "rotate_extrude"):
                    node = cls(
                        children=children,
                        params=params,
                        csg_params=raw_csg_params
                    )

                elif node_type == "multmatrix":
                    try:
                        params["matrix"] = ast.literal_eval(raw_csg_params)
                    except Exception as e:
                        write_log(
                            "CSG_PARSE",
                            f"Failed to evaluate multmatrix params: {raw_csg_params} -> {e}"
                        )
                        params["matrix"] = [
                            [1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1],
                        ]
                    node = cls(
                        children=children,
                        params=params,
                        csg_params=raw_csg_params
                    )

                elif node_type == "polyhedron":
                    # split top-level commas safely
                    poly_params = {}
                    parts = split_top_level_commas(raw_csg_params)
                    for p in parts:
                        if "=" not in p:
                            continue
                        key, val = p.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        try:
                            parsed_val = ast.literal_eval(val)
                        except Exception as e:
                            write_log("CSG_PARSE", f"Failed to eval polyhedron param {p}: {e}")
                            parsed_val = val
                        poly_params[key] = parsed_val

                    # add structured attributes inside params
                    params["points"] = poly_params.get("points", [])
                    params["faces"] = poly_params.get("faces", [])
                    params["convexity"] = poly_params.get("convexity")

                    node = cls(children=children, params=params, csg_params=raw_csg_params)

                # ---- Normal constructor path
                else:
                    node = cls(
                        params=params,
                        csg_params=raw_csg_params,
                        children=children
                    )

            except TypeError as e:
                write_log(
                    "CSG_PARSE",
                    f"Constructor mismatch for '{node_type}', using AstNode fallback: {e}"
                )
                node = AstNode(
                    node_type=node_type,
                    params=params,
                    csg_params=raw_csg_params,
                    children=children
                )

        nodes.append(node)
        i = next_i

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
    
    # write_log("AST","Dump of AST Tree")
    # dump_ast_tree(nodes[0])

    return nodes