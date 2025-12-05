# csg_parser.py
# PLY-based CSG parser with FreeCAD integration for BREP/CSG operations.

import FreeCAD
import Part
import ply.lex as lex
import ply.yacc as yacc
from dataclasses import dataclass, field
from typing import List, Optional, Any

# ----------------------------------------------------
# AST DEFINITIONS
# ----------------------------------------------------

@dataclass
class Node:
    pass

@dataclass
class Program(Node):
    statements: List[Node] = field(default_factory=list)

@dataclass
class OpNode(Node):
    name: str
    args: List[Any] = field(default_factory=list)
    children: List[Node] = field(default_factory=list)
    lineno: int = 0
    parent: Optional[Node] = None
    top_level_compound: bool = False

    def to_scad(self, indent=0):
        pad = "  " * indent
        args_s = ", ".join(map(self._arg_to_scad, self.args))
        if self.children:
            body = "\n".join(
                c.to_scad(indent + 1) if isinstance(c, OpNode) else str(c)
                for c in self.children
            )
            return f"{pad}{self.name}({args_s}) {{\n{body}\n{pad}}}"
        return f"{pad}{self.name}({args_s});"

    def _arg_to_scad(self, a):
        if isinstance(a, str):
            return f'"{a}"'
        if isinstance(a, tuple):
            k, v = a
            if isinstance(v, str):
                return f"{k}='{v}'"
            return f"{k}={v}"
        return str(a)

@dataclass
class RawStmt(Node):
    text: str
    lineno: int = 0
    parent: Optional[Node] = None

    def to_scad(self, indent=0):
        return ("  " * indent) + self.text

# ----------------------------------------------------
# LEXER & PARSER setup
# ----------------------------------------------------
# ... (keep previous lexer/parser code from existing canvas) ...

# ----------------------------------------------------
# HULL/MINKOWSKI AST WALK WITH FreeCAD CALLBACKS
# ----------------------------------------------------

COMPOUND_SET = {"hull", "minkowski"}


def walk_csg_ast_fc(ast_root, is_brep_convertible, handle_brep_fc, handle_openscad_fc):
    """Walk AST and call FreeCAD-aware callbacks."""
    for stmt in ast_root.statements:
        _walk_node_fc(stmt, None, is_brep_convertible, handle_brep_fc, handle_openscad_fc)


def _walk_node_fc(node, inherited_compound, is_brep_convertible, handle_brep_fc, handle_openscad_fc):
    is_compound = isinstance(node, OpNode) and node.name in COMPOUND_SET

    if is_compound:
        if is_brep_convertible(node):
            for c in node.children:
                _walk_node_fc(c, True, is_brep_convertible, handle_brep_fc, handle_openscad_fc)
        else:
            handle_openscad_fc(node)
        return

    # non-hull/minkowski
    if isinstance(node, OpNode):
        handle_brep_fc(node)
        for c in node.children:
            _walk_node_fc(c, False, is_brep_convertible, handle_brep_fc, handle_openscad_fc)
    else:
        handle_brep_fc(node)

# ----------------------------------------------------
# EXAMPLE FreeCAD BREP HANDLER
# ----------------------------------------------------

def example_handle_brep_fc(node):
    """Convert OpNode to FreeCAD Part geometry where possible."""
    doc = FreeCAD.ActiveDocument
    if node.name == 'cube':
        size = node.args[0] if node.args else [1,1,1]
        obj = doc.addObject("Part::Box", "Cube")
        obj.Length, obj.Width, obj.Height = size if isinstance(size, list) else [size]*3
        doc.recompute()
    elif node.name == 'sphere':
        r = node.args[0] if node.args else 1
        obj = doc.addObject("Part::Sphere", "Sphere")
        obj.Radius = r
        doc.recompute()
    # additional primitives handled similarly


def example_handle_openscad_fc(node):
    """Fallback: store raw OpenSCAD as string in FreeCAD document or debug output."""
    print(f"OpenSCAD fallback for {node.name}")
    print(node.to_scad())

