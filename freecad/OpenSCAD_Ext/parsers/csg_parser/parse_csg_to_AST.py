# -*- coding: utf-8 -*-
"""
Safe CSG -> AST parser for FreeCAD OpenSCAD files
-------------------------------------------------
Drop-in replacement for parse_csg_file_to_AST_nodes
"""

import ast
import re
from FreeCAD import Matrix, Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    AstNode, Cube, Sphere, Cylinder, Union, Difference, Intersection,
    Circle, Square, Polygon, Group, Translate, Rotate, Scale,
    MultMatrix, Hull, Minkowski, LinearExtrude, RotateExtrude, Text,
    Color, Polyhedron, UnknownNode
)
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_polyhedron import process_polyhedron


# -----------------------------
# Utilities
# -----------------------------
def split_top_level_commas(s):
    parts = []
    buf = []
    depth = 0
    pairs = {"[": "]", "(": ")", "{": "}"}
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


def parse_scad_argument(arg_str):
    arg_str = arg_str.strip()
    if arg_str.lower() == "true":
        return True
    if arg_str.lower() == "false":
        return False
    try:
        if "." in arg_str:
            return float(arg_str)
        return int(arg_str)
    except ValueError:
        pass
    if arg_str.startswith("[") and arg_str.endswith("]"):
        try:
            vec = ast.literal_eval(arg_str)
            if isinstance(vec, (list, tuple)):
                return [float(x) for x in vec]
        except Exception:
            pass
    return arg_str


def parse_csg_params(param_str):
    params = {}
    csg_params = None
    if not param_str or param_str.strip() == "":
        return params, csg_params

    tokens = re.split(r",(?![^\[\(]*[\]\)])", param_str)
    positional_tokens = []
    for tok in tokens:
        tok = tok.strip()
        if "=" in tok:
            k, v = tok.split("=", 1)
            k = k.strip()
            v = v.strip()
            try:
                val = ast.literal_eval(v)
            except Exception:
                val = v
            params[k] = val
        else:
            positional_tokens.append(tok)

    if positional_tokens:
        if len(positional_tokens) == 1:
            try:
                csg_params = ast.literal_eval(positional_tokens[0])
            except Exception:
                csg_params = positional_tokens[0]
        else:
            evaled = []
            for t in positional_tokens:
                try:
                    evaled.append(ast.literal_eval(t))
                except Exception:
                    evaled.append(t)
            csg_params = evaled

    return params, csg_params


NODE_HEADER_RE = re.compile(r"^\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)")


def parse_csg_node_header(line):
    m = NODE_HEADER_RE.match(line)
    if not m:
        return None, None, False
    node_type = m.group("name")
    raw_csg_params = None
    opens_block = "{" in line
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


# -----------------------------
# Recursive parser
# -----------------------------
def parse_csg_lines(lines, start=0, indent=0, max_depth=1000):
    nodes = []
    i = start
    if indent > max_depth:
        write_log("CSG_PARSE", f"Maximum recursion depth {max_depth} reached at line {start}")
        return nodes, i

    NODE_CLASSES = {
        "circle": Circle, "cube": Cube, "sphere": Sphere, "cylinder": Cylinder,
        "polygon": Polygon, "union": Union, "difference": Difference,
        "intersection": Intersection, "group": Group, "translate": Translate,
        "rotate": Rotate, "scale": Scale, "square": Square, "multmatrix": MultMatrix,
        "hull": Hull, "minkowski": Minkowski, "linear_extrude": LinearExtrude,
        "rotate_extrude": RotateExtrude, "text": Text, "color": Color, "polyhedron": Polyhedron
    }

    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("//"):
            i += 1
            continue
        if line.startswith("}") or line.startswith(");"):
            return nodes, i + 1

        node_type, raw_csg_params, opens_block = parse_csg_node_header(line)
        if node_type is None:
            write_log("CSG_PARSE", f"Skipping unrecognized line: {line}")
            i += 1
            continue

        node_type = node_type.lower()
        children = []
        next_i = i + 1

        if opens_block:
            children, next_i = parse_csg_lines(lines, i + 1, indent + 1, max_depth)

        try:
            params, csg_positional = parse_csg_params(raw_csg_params)
        except Exception as e:
            write_log("CSG_PARSE", f"Failed to parse params for '{node_type}': {e}")
            params, csg_positional = {}, None

        # Cube default size
        if node_type == "cube":
            if "size" not in params:
                params["size"] = csg_positional if csg_positional is not None else 1
            params.setdefault("center", False)

        # Create AST node safely
        cls = NODE_CLASSES.get(node_type)
        if cls is None:
            node = UnknownNode(node_type=node_type, params=params,
                               csg_params=raw_csg_params, children=children)
        else:
            try:
                # MultMatrix handling
                if node_type == "multmatrix":
                    try:
                        mat_list = ast.literal_eval(raw_csg_params)
                        if len(mat_list) != 4 or any(len(row) != 4 for row in mat_list):
                            raise ValueError("Invalid 4x4 matrix")
                    except Exception:
                        mat_list = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
                    fm = Matrix()
                    fm.A11, fm.A12, fm.A13, fm.A14 = mat_list[0]
                    fm.A21, fm.A22, fm.A23, fm.A24 = mat_list[1]
                    fm.A31, fm.A32, fm.A33, fm.A34 = mat_list[2]
                    params["matrix"] = fm
                    node = cls(children=children, params=params, csg_params=raw_csg_params)
                    node.matrix = fm

                # Polygon safety
                elif node_type == "polygon":
                    pts_raw = params.get("points", [])
                    safe_pts = []
                    for p in pts_raw:
                        if isinstance(p, (list, tuple)) and len(p) == 2:
                            safe_pts.append(p)
                        else:
                            write_log("CSG_PARSE", f"Skipping malformed polygon point: {p}")
                    params["points"] = safe_pts
                    node = cls(children=children, params=params, csg_params=raw_csg_params)

                # Polyhedron
                elif node_type == "polyhedron":
                    poly_params = {}
                    for p in split_top_level_commas(raw_csg_params or ""):
                        if "=" not in p:
                            continue
                        k, v = p.split("=", 1)
                        k, v = k.strip(), v.strip()
                        try:
                            poly_params[k] = ast.literal_eval(v)
                        except Exception:
                            poly_params[k] = v
                    params["points"] = poly_params.get("points", [])
                    params["faces"] = poly_params.get("faces", [])
                    params["convexity"] = poly_params.get("convexity")
                    node = cls(children=children, params=params, csg_params=raw_csg_params)

                else:
                    node = cls(children=children, params=params, csg_params=raw_csg_params)

            except Exception as e:
                write_log("CSG_PARSE", f"AST node creation failed for '{node_type}': {e}")
                node = AstNode(node_type=node_type, params=params,
                               csg_params=raw_csg_params, children=children)

        nodes.append(node)
        i = max(next_i, i + 1)

    return nodes, i


# -----------------------------
# Main entry
# -----------------------------
def parse_csg_file_to_AST_nodes(filename):
    write_log("CSG_PARSE", f"Parsing CSG file: {filename}")
    with open(filename, "r") as f:
        lines = f.readlines()
    nodes, _ = parse_csg_lines(lines, start=0)
    write_log("CSG_PARSE", f"Parsed {len(nodes)} top-level nodes")
    return nodes
