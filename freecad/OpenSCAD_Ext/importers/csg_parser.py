# csg_parser.py
# PLY-based CSG parser following same structure and conventions as parser.py
# This provides a clean AST and supports top-level hull/minkowski processing.

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
                return f"{k}='" + v + "'"
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
# LEXER SETUP
# ----------------------------------------------------

tokens = (
    'IDENT', 'NUMBER', 'STRING',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'COMMA', 'SEMI', 'EQUALS'
)

t_LPAREN  = r'\('
t_RPAREN  = r'\)'
t_LBRACE  = r'\{'
t_RBRACE  = r'\}'
t_COMMA   = r','
t_SEMI    = r';'
t_EQUALS  = r'='  

t_ignore = ' \t\r'

reserved = {
    'module': 'IDENT',
    'hull': 'IDENT',
    'minkowski': 'IDENT',
    'union': 'IDENT',
    'difference': 'IDENT',
    'intersection': 'IDENT',
    'translate': 'IDENT',
    'rotate': 'IDENT',
    'scale': 'IDENT',
    'color': 'IDENT',
    'cube': 'IDENT',
    'sphere': 'IDENT',
    'cylinder': 'IDENT',
    'polyhedron': 'IDENT',
    'import': 'IDENT'
}

def t_IDENT(t):
    r"[A-Za-z_][A-Za-z0-9_]*"
    t.type = reserved.get(t.value, 'IDENT')
    return t

def t_NUMBER(t):
    r"(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?"
    t.value = float(t.value)
    return t

def t_STRING(t):
    r'"([^\\\n]|(\\.))*?"'
    t.value = t.value[1:-1]
    return t

def t_comment(t):
    r"//.*"
    pass

def t_multicomment(t):
    r"/\*([^*]|\*+[^*/])*\*+/"
    pass

def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f"Illegal char {t.value[0]!r} at line {t.lineno}")
    t.lexer.skip(1)

# ----------------------------------------------------
# PARSER
# ----------------------------------------------------

def p_program(p):
    "program : stmt_list"
    p[0] = Program(p[1])
    for s in p[0].statements:
        if isinstance(s, (OpNode, RawStmt)):
            s.parent = p[0]

def p_stmt_list(p):
    """
    stmt_list : stmt_list stmt
              | stmt
              | empty
    """
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    elif len(p) == 2:
        p[0] = [] if p[1] is None else [p[1]]
    else:
        p[0] = []


def p_stmt(p):
    """
    stmt : operation
         | raw_stmt SEMI
         | operation block
    """
    p[0] = p[1]


def p_raw_stmt(p):
    "raw_stmt : IDENT LPAREN maybe_arglist RPAREN"
    args = p[3] or []
    p[0] = OpNode(name=p[1], args=args, children=[], lineno=p.lineno(1))


def p_operation(p):
    """
    operation : IDENT LPAREN maybe_arglist RPAREN
              | IDENT LPAREN maybe_arglist RPAREN block
    """
    name = p[1]
    args = p[3] or []
    if len(p) == 6:
        block = p[5]
        node = OpNode(name=name, args=args, children=block, lineno=p.lineno(1))
        for c in node.children:
            if isinstance(c, Node):
                c.parent = node
        p[0] = node
    else:
        p[0] = OpNode(name=name, args=args, children=[], lineno=p.lineno(1))


def p_block(p):
    "block : LBRACE stmt_list RBRACE"
    p[0] = p[2]


def p_maybe_arglist(p):
    """
    maybe_arglist : arglist
                  | empty
    """
    p[0] = p[1]


def p_arglist(p):
    """
    arglist : arglist COMMA arg
            | arg
    """
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_arg(p):
    """
    arg : NUMBER
        | STRING
        | IDENT EQUALS NUMBER
        | IDENT EQUALS STRING
        | IDENT
    """
    p[0] = (p[1], p[3]) if len(p) == 4 else p[1]


def p_empty(p):
    "empty :"
    pass


def p_error(p):
    if p:
        print(f"Parse error at {p.type} value {p.value} line {p.lineno}")
    else:
        print("Parse error at EOF")

lexer = lex.lex()
parser = yacc.yacc(start='program', debug=False)

# ----------------------------------------------------
# UTILITIES FOR HULL/MINKOWSKI PROCESSING
# ----------------------------------------------------

COMPOUND_SET = {"hull", "minkowski"}


def mark_top_level_compounds(ast):
    for stmt in ast.statements:
        if isinstance(stmt, OpNode) and stmt.name in COMPOUND_SET:
            stmt.top_level_compound = True


def walk_csg_ast(ast_root, is_brep_convertible, handle_brep, handle_openscad):
    for n in ast_root.statements:
        _walk_node(n, None, is_brep_convertible, handle_brep, handle_openscad)


def _walk_node(node, inherited_compound, is_brep_convertible, handle_brep, handle_openscad):
    is_compound = isinstance(node, OpNode) and node.name in COMPOUND_SET

    if is_compound:
        if is_brep_convertible(node):
            for c in node.children:
                _walk_node(c, True, is_brep_convertible, handle_brep, handle_openscad)
        else:
            handle_openscad(node)
        return

    # non-hull/minkowski
    if isinstance(node, OpNode):
        handle_brep(node)
        for c in node.children:
            _walk_node(c, False, is_brep_convertible, handle_brep, handle_openscad)
    else:
        handle_brep(node)

