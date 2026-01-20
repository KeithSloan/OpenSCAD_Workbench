# -*- coding: utf-8 -*-
"""
parse_csg_file_to_AST.py
========================

Parses a .csg file into AST nodes for FreeCAD processing.
Handles transforms, booleans, groups, OpenSCAD fallback for hull/minkowski.
"""

import os
import re
import tempfile
import subprocess
import Mesh
import Part

from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams  # adjust import to your wb
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import AstNode, Cube, Sphere, Hull, Minkowski, Group, Translate, Rotate, Scale, MultMatrix

# ------------------------------------------------------------------
# Logging helper
# ------------------------------------------------------------------
def write_log(tag, msg):
    print(f"[{tag}] {msg}")

# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------
def parse_csg_file_to_AST_nodes(filename):
    """
    Returns a list of AST nodes for a CSG file.
    """
    write_log("AST", f"Parsing CSG file: {filename}")

    with open(filename, "r", encoding="utf-8") as f:
        lines = [
            l.strip() for l in f
            if l.strip() and not l.strip().startswith("//")
        ]

    nodes, _ = _parse_block(lines, 0)
    return nodes

# ------------------------------------------------------------------
# Core parser
# ------------------------------------------------------------------
def _parse_block(lines, idx):
    nodes = []

    while idx < len(lines):
        line = lines[idx]

        if line == "}":
            return nodes, idx + 1

        if line.endswith("{"):
            header = line[:-1].strip()
            node_type, csg_params = _parse_header(header)
            children, idx = _parse_block(lines, idx + 1)

            node = AstNode(node_type, params={}, csg_params=csg_params, children=children)
            nodes.append(node)
            continue

        # Single statement
        node_type, csg_params = _parse_header(line.rstrip(";"))
        node = AstNode(node_type, params={}, csg_params=csg_params)
        nodes.append(node)
        idx += 1

    return nodes, idx

# ------------------------------------------------------------------
# Header / param parsing
# ------------------------------------------------------------------
def _parse_header(header):
    """
    Parses node_type and raw csg_params
    """
    m = re.match(r"(\w+)\s*\((.*)\)", header)
    if not m:
        return header, {}

    node_type = m.group(1)
    arg_str = m.group(2)
    params = _parse_params(arg_str)
    return node_type, params

def _parse_params(arg_str):
    """
    Very lightweight param parser storing raw csg_params
    """
    params = {}
    if not arg_str:
        return params

    parts = re.split(r",(?![^\[]*\])", arg_str)
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip()] = v.strip()
        else:
            # positional args like cube(10) => store as '0', '1', ...
            params[p.strip()] = None
    return params

# ------------------------------------------------------------------
# Flatten AST to OpenSCAD source
# ------------------------------------------------------------------
"""
def flatten_ast_for_hull_minkowski(node, indent=0):
    pad = " " * indent
    scad_lines = []

    if node is None:
        return ""

    write_log("FLATTEN", f"{pad}Flatten node: {node.node_type}, children={len(node.children)}, csg_params={node.csg_params}")

    # Only group is transparent
    if node.node_type == "group":
        for child in node.children:
            scad_lines.append(flatten_ast_for_hull_minkowski(child, indent))
        return "\n".join(scad_lines)

    # Leaf node
    if not node.children:
        args = []
        for k, v in node.csg_params.items():
            if v is None:
                args.append(f"{k}")
            else:
                args.append(f"{k}={v}")
        args_str = ", ".join(args)
        scad_lines.append(f"{pad}{node.node_type}({args_str});")
        return "\n".join(scad_lines)

    # Node with children
    args = []
    for k, v in node.csg_params.items():
        if v is None:
            args.append(f"{k}")
        else:
            args.append(f"{k}={v}")
    args_str = ", ".join(args)

    scad_lines.append(f"{pad}{node.node_type}({args_str}) {{")
    for child in node.children:
        scad_lines.append(flatten_ast_for_hull_minkowski(child, indent + 4))
    scad_lines.append(f"{pad}}}")

    write_log("FLATTEN_SCAD", f"{pad}{node.node_type} block generated with {len(node.children)} children")
    return "\n".join(scad_lines)
"""

def flatten_for_hull_minkowski(node, indent=4):
    pad = " " * indent
    lines = []

    for child in node.children:
        params_str = ""
        if hasattr(child, "csg_params"):
            arg_list = []
            for k, v in child.csg_params.items():
                if v is None:
                    arg_list.append(k)
                elif isinstance(v, (int, float)):
                    arg_list.append(f"{k}={v}")
                elif isinstance(v, (list, tuple)):
                    arg_list.append(f"{k}={v}")
                elif isinstance(v, str):
                    arg_list.append(f'{k}="{v}"')
            params_str = ", ".join(arg_list)

        if child.children:
            lines.append(f"{pad}{child.node_type}({params_str}) {{")
            lines.append(flatten_for_hull_minkowski(child, indent + 4))
            lines.append(f"{pad}}}")
        else:
            lines.append(f"{pad}{child.node_type}({params_str});")
    
    return "\n".join(lines)



# ------------------------------------------------------------------
# OpenSCAD fallback
# ------------------------------------------------------------------
def fallback_to_OpenSCAD(node):
    """
    Called ONLY for hull and minkowski.
    Generates temporary SCAD, runs OpenSCAD, imports STL.
    """
    write_log("AST_FALLBACK", f"Fallback to OpenSCAD: {node.node_type}")

    if node.node_type not in ("hull", "minkowski"):
        return None

    # Flatten AST to SCAD using raw csg_params
    scad_src = flatten_for_hull_minkowski(node)

    tmp_dir = tempfile.mkdtemp()
    scad_file = os.path.join(tmp_dir, f"{node.node_type}.scad")
    stl_file = os.path.join(tmp_dir, "fallback.stl")

    with open(scad_file, "w", encoding="utf-8") as f:
        f.write(scad_src)

    write_log("AST_DEBUG", f"SCAD written to {scad_file}")

    # Get OpenSCAD executable path
    openscad_exe = BaseParams.get_openscad_path()  # adjust for your wb
    cmd = [openscad_exe, "-o", stl_file, scad_file]

    write_log("AST_FALLBACK", f"Calling OpenSCAD CLI: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Import STL to Part.Shape
    mesh = Mesh.Mesh(stl_file)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, 0.05)
    shape.removeSplitter()

    write_log("AST_FALLBACK", f"Imported STL to Shape: {shape}")
    return shape

