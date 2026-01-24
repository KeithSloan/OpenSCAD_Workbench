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
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import LinearExtrude, RotateExtrude, Text, Color, UnknownNode

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

def parse_csg_lines(lines, start=0, indent=0):
    """
    Recursively parse CSG lines into AST nodes.
    Fully handles all nodes from ast_nodes.py.
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
    }

    while i < len(lines):
        line = lines[i].strip()

        # End of block
        if line.startswith("}") or line.startswith(");"):
            return nodes, i + 1

        # Skip empty / comment
        if not line or line.startswith("//"):
            i += 1
            continue

        # Parse node header
        node_type, raw_csg_params, opens_block = parse_csg_node_header(line)
        if node_type is None:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type = node_type.lower()
        children = []
        next_i = i + 1

        # Parse children if block
        if opens_block:
            children, next_i = parse_csg_lines(lines, i + 1, indent + 1)

        # Parse parameters
        try:
            params, csg_positional = parse_csg_params(raw_csg_params)
        except Exception as e:
            write_log("CSG_PARSE", f"Failed to parse params for '{node_type}': {e}")
            params = {}
            csg_positional = None

        # Special handling: cube positional size
        if node_type == "cube":
            if "size" not in params:
                if csg_positional is not None:
                    params["size"] = csg_positional
                else:
                    params["size"] = 1
            params.setdefault("center", False)

        # Determine class
        cls = NODE_CLASSES.get(node_type)

        if cls is None:
            write_log("CSG_PARSE", f"Unknown node '{node_type}', preserving as UnknownNode")
            node = UnknownNode(node_type=node_type, params=params, csg_params=raw_csg_params, children=children)
        else:
            try:
                # Special constructors for vector/angle nodes
                if node_type in ("translate", "scale", "rotate"):
                    node = cls(vector=params.get("vector"), angle=params.get("angle"), children=children, params=params, csg_params=raw_csg_params)
                elif node_type in ("linear_extrude", "rotate_extrude"):
                    node = cls(children=children, params=params, csg_params=raw_csg_params)
                elif node_type == "multmatrix":
                    # matrix = csg_positional or params.get("matrix")
                    # --- Special handling for multmatrix ---
                    # raw_csg_params might be a string like '[[1,0,0,0],[0,1,0,0],[0,0,1,140],[0,0,0,1]]'
                    try:
                        matrix = ast.literal_eval(raw_csg_params)
                        params["matrix"] = matrix
                    except Exception as e:
                        write_log("CSG_PARSE", f"Failed to evaluate multmatrix params: {raw_csg_params} -> {e}")
                        params["matrix"] = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]  # default identity
                    # Pass matrix inside params, do not use keyword argument 'matrix'
                    node = cls(params=params, csg_params=raw_csg_params, children=children)    
                    #node = cls(matrix=matrix, children=children, params=params, csg_params=raw_csg_params)
                elif node_type == "cube":
                    node = cls(params=params, csg_params=raw_csg_params, children=children)
                else:
                    node = cls(params=params, csg_params=raw_csg_params, children=children)
            except TypeError as e:
                write_log("CSG_PARSE", f"Constructor mismatch for '{node_type}', using AstNode fallback: {e}")
                node = AstNode(node_type=node_type, params=params, csg_params=raw_csg_params, children=children)

        nodes.append(node)
        i = next_i

    return nodes, i



def saved_parse_csg_lines(lines, start=0, indent=0):
    """
    Parse a block of CSG lines into AST nodes.
    Returns (nodes, next_index)
    """

    nodes = []
    i = start

    while i < len(lines):
        line = lines[i].strip()

        # --- End of this block ---
        if line == "}" or line == ");":
            return nodes, i + 1

        # --- Skip empty / comment ---
        if not line or line.startswith("//"):
            i += 1
            continue

        # --- Parse node header ---
        try:
            node_type, raw_csg_params, opens_block = parse_csg_node_header(line)
        except Exception:
            write_log("CSG_PARSE", f"Failed to parse line: {line}")
            i += 1
            continue

        # --- Parse params for B-Rep ONLY ---
        params, _ = parse_csg_params(raw_csg_params)

        # --- Parse children if block ---
        children = []
        next_i = i + 1

        if opens_block:
            children, next_i = parse_csg_lines(lines, i + 1, indent + 1)

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
            "text": Text,
            "color": Color,
        }

        cls = NODE_CLASSES.get(node_type)

        # --- Unknown node ---
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
            nodes.append(node)
            i = next_i
            continue

        # --- Known node, attempt construction ---
        try:
            node = cls(
                params=params,
                csg_params=raw_csg_params,
                children=children,
            )
        except TypeError as e:
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
        i = next_i

    return nodes, i

'''
Moved to ast_utils.py

def dump_ast_compact(node, indent=0, _seen=None):
    if _seen is None:
        _seen = set()

    prefix = "  " * indent
    if id(node) in _seen:
        print(prefix + f"{node.node_type} <CYCLE>")
        return

    _seen.add(id(node))
    print(prefix + f"{node.node_type}  children={len(node.children)}")

    for c in node.children:
        dump_ast_compact(c, indent + 1, _seen)

def dump_ast_node(node, indent=0):
    """
    Dump a single AST node (no recursion).
    Safe to call anywhere.
    """
    prefix = "  " * indent

    if node is None:
        print(prefix + "<None>")
        return

    print(prefix + f"{node.node_type}  ({node.__class__.__name__})")

    # Params (FreeCAD / B-Rep)
    params = getattr(node, "params", None)
    if params:
        print(prefix + "  params:")
        for k, v in params.items():
            print(prefix + f"    {k}: {v!r}")
    else:
        print(prefix + "  params: {}")

    # Raw CSG params (OpenSCAD)
    csg_params = getattr(node, "csg_params", None)
    if csg_params:
        print(prefix + "  csg_params:")
        if isinstance(csg_params, dict):
            for k, v in csg_params.items():
                print(prefix + f"    {k}: {v!r}")
        else:
            print(prefix + f"    {csg_params!r}")
    else:
        print(prefix + "  csg_params: {}")

    # Children summary only
    children = getattr(node, "children", None)
    if children is None:
        print(prefix + "  children: <missing>")
    else:
        print(prefix + f"  children: {len(children)}")


def dump_ast_tree(node, indent=0, max_depth=50, _seen=None):
    """
    Recursive AST dump using dump_ast_node().
    """

    if _seen is None:
        _seen = set()

    if node is None:
        print("  " * indent + "<None>")
        return

    node_id = id(node)
    if node_id in _seen:
        print("  " * indent + f"<CYCLE {node.node_type}>")
        return

    if indent > max_depth:
        print("  " * indent + "<MAX DEPTH REACHED>")
        return

    _seen.add(node_id)

    # Dump THIS node only
    dump_ast_node(node, indent)

    # Recurse
    children = getattr(node, "children", []) or []
    for child in children:
        dump_ast_tree(
            child,
            indent=indent + 1,
            max_depth=max_depth,
            _seen=_seen,
        )


'''


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

