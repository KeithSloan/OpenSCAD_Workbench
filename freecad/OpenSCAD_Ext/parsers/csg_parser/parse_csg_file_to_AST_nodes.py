import re
import ast
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Hull, Minkowski, Group,
    MultMatrix, Translate, Rotate, Scale
)

# ----------------------------
# Normalization helpers
# ----------------------------

TRANSPARENT_NODES = (
    Group,
    Translate,
    Rotate,
    Scale,
)

def normalize_ast(node):
    """Remove empty groups and collapse transparent wrappers."""
    if not hasattr(node, "children"):
        return node

    children = []
    for c in node.children:
        n = normalize_ast(c)
        if n:
            children.append(n)
    node.children = children

    if isinstance(node, TRANSPARENT_NODES) and not node.children:
        write_log("Info", f"Dropping empty {node.node_type}")
        return None

    if isinstance(node, TRANSPARENT_NODES) and len(node.children) == 1:
        write_log(
            "Info",
            f"Collapsing {node.node_type} → {node.children[0].node_type}"
        )
        return node.children[0]

    return node


# ----------------------------
# Parsing helpers
# ----------------------------

def parse_scad_matrix(line):
    """Extract [[...],[...],[...],[...]] from multmatrix(...)"""
    m = re.search(r"multmatrix\s*\(\s*(\[\[.*?\]\])\s*\)", line)
    if not m:
        return None
    try:
        return ast.literal_eval(m.group(1))
    except Exception as e:
        write_log("Warning", f"Failed to parse multmatrix: {e}")
        return None


def parse_vector(line):
    m = re.search(r"\(\s*\[([^\]]+)\]\s*\)", line)
    if not m:
        return None
    return [float(x) for x in m.group(1).split(",")]


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

            # --- End of block ---
            if line.startswith("}"):
                return nodes, idx + 1

            # --- Primitives ---
            if line.startswith("cube"):
                m = re.search(r"size\s*=\s*\[([^\]]+)\]", line)
                size = [float(x) for x in m.group(1).split(",")] if m else [1, 1, 1]
                center = bool(re.search(r"center\s*=\s*true", line))
                write_log("Info", f"Parsing cube size={size} center={center}")
                nodes.append(Cube(size=size, center=center))
                idx += 1
                continue

            if line.startswith("sphere"):
                r = float(re.search(r"r\s*=\s*([\d\.]+)", line).group(1))
                write_log("Info", f"Parsing sphere r={r}")
                nodes.append(Sphere(r=r))
                idx += 1
                continue

            if line.startswith("cylinder"):
                r = float(re.search(r"r\s*=\s*([\d\.]+)", line).group(1))
                h = float(re.search(r"h\s*=\s*([\d\.]+)", line).group(1))
                center = bool(re.search(r"center\s*=\s*true", line))
                write_log("Info", f"Parsing cylinder r={r} h={h}")
                nodes.append(Cylinder(r=r, h=h, center=center))
                idx += 1
                continue

            # --- Block nodes ---
            for key in (
                "union", "difference", "intersection",
                "hull", "minkowski", "group",
                "translate", "rotate", "scale", "multmatrix"
            ):
                if line.startswith(key):
                    write_log("Info", f"Parsing {key} node")

                    if key == "multmatrix":
                        matrix = parse_scad_matrix(line)
                        write_log("Info", f"multmatrix={matrix}")
                    else:
                        matrix = None

                    if key in ("translate", "scale"):
                        vec = parse_vector(line)
                    else:
                        vec = None

                    if key == "rotate":
                        vec = parse_vector(line)
                        angle = float(re.search(r"\)\s*\(([\d\.]+)\)", line).group(1)) \
                            if ")" in line else None
                    else:
                        angle = None

                    # Skip "{"
                    idx += 1
                    if lines[idx].startswith("{"):
                        idx += 1

                    children, idx = parse_block(idx)

                    node = {
                        "union": Union,
                        "difference": Difference,
                        "intersection": Intersection,
                        "hull": Hull,
                        "minkowski": Minkowski,
                        "group": Group,
                        "translate": lambda c: Translate(vector=vec, children=c),
                        "rotate": lambda c: Rotate(vector=vec, angle=angle, children=c),
                        "scale": lambda c: Scale(vector=vec, children=c),
                        "multmatrix": lambda c: MultMatrix(matrix=matrix, children=c),
                    }[key](children)

                    nodes.append(node)
                    break
            else:
                write_log("Info", f"Skipping line: {line}")
                idx += 1

        return nodes, idx

    raw_nodes, _ = parse_block(0)

    # 🔑 NORMALIZE AST
    ast_nodes = []
    for n in raw_nodes:
        nn = normalize_ast(n)
        if nn:
            ast_nodes.append(nn)

    write_log("Info", f"AST nodes after normalize: {len(ast_nodes)}")
    return ast_nodes

