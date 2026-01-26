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

# ----------------------------
# Helpers
# ----------------------------
def parse_vector(text):
    try:
        return py_ast.literal_eval(text)
    except Exception:
        return None

def parse_matrix(text):
    try:
        return py_ast.literal_eval(text)
    except Exception:
        return None

# ----------------------------
# Normalize AST
# ----------------------------
TRANSPARENT_NODES = (Group, Translate, Rotate, Scale)

def normalize_ast(node):
    """Remove empty groups and collapse transparent wrappers."""
    if not hasattr(node, "children"):
        return node

    children = []
    for c in node.children:
        nn = normalize_ast(c)
        if nn is None:
            continue
        children.append(nn)
    node.children = children

    if isinstance(node, TRANSPARENT_NODES) and not node.children:
        write_log("Info", f"Dropping empty {node.node_type}")
        return None

    if isinstance(node, TRANSPARENT_NODES) and len(node.children) == 1:
        write_log("Info", f"Collapsing {node.node_type} → {node.children[0].node_type}")
        return node.children[0]

    return node

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

            # ---------- 2D ----------
            if line.startswith("circle"):
                r = float(re.search(r"r\s*=\s*([\d\.]+)", line).group(1))
                nodes.append(Circle(r=r))
                idx += 1
                continue

            if line.startswith("square"):
                size = parse_vector(re.search(r"\((.*)\)", line).group(1))
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

            # ---------- 3D ----------
            if line.startswith("cube"):
                size = parse_vector(re.search(r"\((.*)\)", line).group(1))
                nodes.append(Cube(size=size))
                idx += 1
                continue

            if line.startswith("sphere"):
                r = float(re.search(r"r\s*=\s*([\d\.]+)", line).group(1))
                nodes.append(Sphere(r=r))
                idx += 1
                continue

            if line.startswith("cylinder"):
                r = float(re.search(r"r\s*=\s*([\d\.]+)", line).group(1))
                h = float(re.search(r"h\s*=\s*([\d\.]+)", line).group(1))
                nodes.append(Cylinder(r=r, h=h))
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

            # ---------- CSG / Block nodes ----------
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
                # ---------- Transforms ----------
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

                write_log("Info", f"Skipping unsupported line: {line}")
                idx += 1

        return nodes, idx

    nodes, _ = parse_block(0)

    # 🔑 Normalize AST
    ast_nodes = []
    for n in nodes:
        nn = normalize_ast(n)
        if nn:
            ast_nodes.append(nn)

    write_log("Info", f"AST nodes after normalize: {len(ast_nodes)}")
    return ast_nodes


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
    