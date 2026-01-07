import re
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    Node, Cube, Sphere, Cylinder, Union, Difference, Intersection,
    Hull, Minkowski, Group, MultMatrix, Translate, Rotate, Scale
    )


def parse_csg_file_to_AST_nodes(filename):
    """
    Parse OpenSCAD file into a full AST with:
    - Primitives: cube, sphere, cylinder
    - Booleans: union, difference, intersection, hull, minkowski, group
    - Transforms: translate, rotate, scale, multmatrix
    - Nested blocks with children
    """

    with open(filename, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    def parse_block(lines, idx=0):
        nodes = []
        while idx < len(lines):
            line = lines[idx]

            # Skip comments
            if line.startswith("//"):
                idx += 1
                continue

            # === Primitives ===
            if line.startswith("cube"):
                m = re.search(r"size\s*=\s*\[([^\]]+)\]", line)
                size = [float(x) for x in m.group(1).split(",")] if m else [1,1,1]
                center = "center=true" in line
                write_log("Info", f"Parsing cube: size={size}, center={center}")
                nodes.append(Cube(size=size, center=center))
                idx += 1

            elif line.startswith("sphere"):
                m_r = re.search(r"r\s*=\s*([\d\.]+)", line)
                r = float(m_r.group(1)) if m_r else 1
                # $fn, $fa, $fs optional
                fn = fa = fs = None
                for key in ("$fn", "$fa", "$fs"):
                    m = re.search(rf"{key}\s*=\s*([\d\.]+)", line)
                    if m: locals()[key[1:]] = float(m.group(1))
                write_log("Info", f"Parsing sphere: r={r}, $fn={fn}, $fa={fa}, $fs={fs}")
                nodes.append(Sphere(r=r, fn=fn, fa=fa, fs=fs))
                idx += 1

            elif line.startswith("cylinder"):
                m_r = re.search(r"r\s*=\s*([\d\.]+)", line)
                m_h = re.search(r"h\s*=\s*([\d\.]+)", line)
                r = float(m_r.group(1)) if m_r else 1
                h = float(m_h.group(1)) if m_h else 1
                center = "center=true" in line
                fn = fa = fs = None
                for key in ("$fn", "$fa", "$fs"):
                    m = re.search(rf"{key}\s*=\s*([\d\.]+)", line)
                    if m: locals()[key[1:]] = float(m.group(1))
                write_log("Info", f"Parsing cylinder: r={r}, h={h}, center={center}, $fn={fn}, $fa={fa}, $fs={fs}")
                nodes.append(Cylinder(r=r, h=h, center=center, fn=fn, fa=fa, fs=fs))
                idx += 1

            # === Booleans / groups / transforms ===
            elif any(line.startswith(k) for k in 
                     ("union","difference","intersection","hull","minkowski",
                      "group","translate","rotate","scale","multmatrix")):

                node_type = line.split("(")[0]
                write_log("Info", f"Parsing {node_type} node")

                # Collect lines inside { ... }
                brace_count = 0
                child_lines = []
                idx += 1
                while idx < len(lines):
                    l = lines[idx]
                    brace_count += l.count("{")
                    brace_count -= l.count("}")
                    if brace_count < 0:  # end of block
                        break
                    child_lines.append(l)
                    idx += 1

                # Recursive parse children
                children, _ = parse_block(child_lines)

                # Create node
                if node_type == "union": nodes.append(Union(children))
                elif node_type == "difference": nodes.append(Difference(children))
                elif node_type == "intersection": nodes.append(Intersection(children))
                elif node_type == "hull": nodes.append(Hull(children))
                elif node_type == "minkowski": nodes.append(Minkowski(children))
                elif node_type == "group": nodes.append(Group(children))
                elif node_type == "multmatrix": nodes.append(MultMatrix(matrix=None, children=children))
                elif node_type == "translate": nodes.append(Translate(vector=None, children=children))
                elif node_type == "rotate": nodes.append(Rotate(vector=None, angle=None, children=children))
                elif node_type == "scale": nodes.append(Scale(vector=None, children=children))

                idx += 1

            else:
                write_log("Info", f"Skipping unknown line: {line}")
                idx += 1

        return nodes, idx

    ast_nodes, _ = parse_block(lines)
    return ast_nodes

