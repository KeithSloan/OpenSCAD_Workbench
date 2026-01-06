# createASTfromCSG.py
# Full PLY-based CSG parser with enhanced lexer, grammar, AST constructs,
# and integrated top-level hull/minkowski detection.
#
# Usage:
#   pip install ply
#   from csg_parser import parse_scad, walk_csg_ast, OpNode, Program
#
# The parser builds an AST with nodes for operations, raw statements, arrays,
# assignments, module definitions and calls. It marks OpNode.top_level_compound
# when a hull/minkowski appears directly under the Program root.
#
# This is intended for parsing csg NOT scad source as no if, for, let etc
#

import ply.lex as lex
import ply.yacc as yacc
from dataclasses import dataclass, field
from typing import List, Optional, Any

def open(fileName):
	import FreeCAD
	FreeCAD.Console.PrintError(f"Create AST from CSG {fileName}\n") 

# -------------------------
# AST NODES
# -------------------------

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
        args_s = ", ".join(map(_arg_to_scad, self.args))
        if self.children:
            body_lines = []
            for c in self.children:
                if hasattr(c, 'to_scad'):
                    body_lines.append(c.to_scad(indent+1))
                else:
                    body_lines.append(("  "*(indent+1)) + str(c))
            body = "\n".join(body_lines)
            return f"{pad}{self.name}({args_s}) {{\n{body}\n{pad}}}"
        else:
            return f"{pad}{self.name}({args_s});"

@dataclass
class RawStmt(Node):
    text: str
    lineno: int = 0
    parent: Optional[Node] = None

    def to_scad(self, indent=0):
        return ("  "*indent) + self.text

@dataclass
class ArrayNode(Node):
    values: List[Any]
    lineno: int = 0

    def to_scad(self, indent=0):
        pad = "  "*indent
        return pad + "[" + ", ".join(map(_arg_to_scad, self.values)) + "]"

@dataclass
class Assignment(Node):
    name: str
    value: Any
    lineno: int = 0

    def to_scad(self, indent=0):
        pad = "  "*indent
        return f"{pad}{self.name} = {_arg_to_scad(self.value)};"

@dataclass
class ModuleDef(Node):
    name: str
    params: List[str]
    body: List[Node]
    lineno: int = 0

    def to_scad(self, indent=0):
        pad = "  "*indent
        params = ", ".join(self.params)
        body_lines = "\n".join(c.to_scad(indent+1) for c in self.body)
        return f"{pad}module {self.name}({params}) {{\n{body_lines}\n{pad}}}"

@dataclass
class ModuleCall(Node):
    name: str
    args: List[Any]
    lineno: int = 0

    def to_scad(self, indent=0):
        pad = "  "*indent
        return f"{pad}{self.name}({', '.join(map(_arg_to_scad, self.args))});"

# Small helper for arg serialization

def _arg_to_scad(a):
    if isinstance(a, str):
        return f'"{a}"'
    if isinstance(a, ArrayNode):
        return "[" + ", ".join(map(_arg_to_scad, a.values)) + "]"
    if isinstance(a, tuple) and len(a) == 2 and isinstance(a[0], str):
        k, v = a
        return f"{k}={_arg_to_scad(v)}"
    return str(a)

# -------------------------
# LEXER
# -------------------------

tokens = (
    'IDENT', 'NUMBER', 'STRING',
    'LBRACK', 'RBRACK',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'COMMA', 'SEMI', 'EQUALS', 'PLUS', 'MINUS',

# keyword tokens (must be included here)
# think MODULE is scad not CSG
    'MODULE', 'HULL', 'MINKOWSKI', 'UNION', 'DIFFERENCE', 'INTERSECTION',
    'TRANSLATE', 'ROTATE', 'SCALE', 'COLOR',
    'CUBE', 'SPHERE', 'CYLINDER', 'POLYHEDRON', 'IMPORT',
)

# token regexes
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACK = r'\['
t_RBRACK = r'\]'
t_COMMA = r','
t_SEMI = r';'
t_EQUALS = r'='
t_PLUS = r'\+'
t_MINUS = r'-'

t_ignore = ' \t\r'

reserved = {
    'module': 'MODULE',
    'hull': 'HULL',
    'minkowski': 'MINKOWSKI',
    'union': 'UNION',
    'difference': 'DIFFERENCE',
    'intersection': 'INTERSECTION',
    'translate': 'TRANSLATE',
    'rotate': 'ROTATE',
    'scale': 'SCALE',
    'color': 'COLOR',
    'cube': 'CUBE',
    'sphere': 'SPHERE',
    'cylinder': 'CYLINDER',
    'polyhedron': 'POLYHEDRON',
    'import': 'IMPORT'
}

def t_IDENT(t):
    r'[A-Za-z_][A-Za-z0-9_]*'
    t.type = reserved.get(t.value, 'IDENT')
    return t

def t_NUMBER(t):
    r'(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?'
    try:
        if '.' in t.value or 'e' in t.value or 'E' in t.value:
            t.value = float(t.value)
        else:
            t.value = int(t.value)
    except Exception:
        t.value = float(t.value)
    return t

def t_STRING(t):
    r'"([^\\\n]|(\\.))*?"'
    t.value = t.value[1:-1]
    return t

def t_comment(t):
    r'//.*'
    pass

def t_multiline_comment(t):
    r'/\*([^*]|\*+[^*/])*\*+/'
    t.lexer.lineno += t.value.count('\n')
    pass

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f"Illegal character {t.value[0]!r} at line {t.lineno}")
    t.lexer.skip(1)

# Build lexer
lexer = lex.lex()

# -------------------------
# PARSER
# -------------------------

precedence = (
    ('left', 'COMMA'),
)

def p_program(p):
    'program : stmt_list'
    p[0] = Program(statements=p[1])
    # set parent pointers and mark top-level hull/minkowski
    for s in p[0].statements:
        if isinstance(s, (OpNode, RawStmt, ModuleDef, Assignment, ModuleCall)):
            s.parent = p[0]
        if isinstance(s, OpNode) and s.name in ("hull", "minkowski"):
            s.top_level_compound = True

def p_stmt_list(p):
    '''stmt_list : stmt_list stmt
                 | stmt
                 | empty'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    elif len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = []

def p_stmt(p):
    '''stmt : operation
            | raw_stmt SEMI
            | assignment SEMI
            | module_def
    '''
    p[0] = p[1]

def p_raw_stmt(p):
    'raw_stmt : IDENT LPAREN maybe_arglist RPAREN'
    args = p[3] or []
    p[0] = OpNode(name=p[1], args=args, children=[], lineno=p.lineno(1))

def p_operation(p):
    '''operation : IDENT LPAREN maybe_arglist RPAREN
                 | IDENT LPAREN maybe_arglist RPAREN block'''
    name = p[1]
    args = p[3] or []
    if len(p) == 6:
        node = OpNode(name=name, args=args, children=[], lineno=p.lineno(1))
        p[0] = node
    else:
        block = p[6]
        node = OpNode(name=name, args=args, children=block, lineno=p.lineno(1))
        for c in node.children:
            if isinstance(c, Node):
                c.parent = node
        p[0] = node

def p_block(p):
    'block : LBRACE stmt_list RBRACE'
    p[0] = p[2]

def p_maybe_arglist(p):
    '''maybe_arglist : arglist
                     | empty'''
    p[0] = p[1]

def p_arglist(p):
    '''arglist : arglist COMMA arg
               | arg'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_arg(p):
    '''arg : NUMBER
           | STRING
           | array
           | IDENT EQUALS value
           | value'''
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = (p[1], p[3])

def p_value(p):
    '''value : NUMBER
             | STRING
             | IDENT
             | array'''
    p[0] = p[1]

def p_array(p):
    'array : LBRACK maybe_array_vals RBRACK'
    p[0] = ArrayNode(values=p[2] or [], lineno=p.lineno(1))

def p_maybe_array_vals(p):
    '''maybe_array_vals : array_vals
                        | empty'''
    p[0] = p[1]

def p_array_vals(p):
    '''array_vals : array_vals COMMA arg
                  | arg'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_assignment(p):
    'assignment : IDENT EQUALS value'
    p[0] = Assignment(name=p[1], value=p[3], lineno=p.lineno(1))

def p_module_def(p):
    'module_def : MODULE IDENT LPAREN maybe_param_list RPAREN block'
    params = p[4] or []
    p[0] = ModuleDef(name=p[2], params=params, body=p[6], lineno=p.lineno(1))

def p_maybe_param_list(p):
    '''maybe_param_list : param_list
                        | empty'''
    p[0] = p[1]

def p_param_list(p):
    '''param_list : param_list COMMA IDENT
                  | IDENT'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_module_call(p):
    'module_call : IDENT LPAREN maybe_arglist RPAREN'
    p[0] = ModuleCall(name=p[1], args=p[3] or [], lineno=p.lineno(1))

def p_empty(p):
    'empty :'
    p[0] = None

def p_error(p):
    if p:
        print(f"Parse error at token {p.type!r}, value {p.value!r}, line {p.lineno}")
    else:
        print("Parse error at EOF")

# Build parser
parser = yacc.yacc(start='program', debug=False)

# -------------------------
# Post-parse utilities
# -------------------------

COMPOUND_SET = {'hull', 'minkowski'}



def mark_top_level_compounds(ast: Program):
    for s in ast.statements:
        if isinstance(s, OpNode) and s.name in COMPOUND_SET:
            s.top_level_compound = True

def parse_csg(filename):
    with open(filename, "r", encoding="utf-8") as f:
        data = f.read()
    ast = parser.parse(data, lexer=lexer)
    mark_top_level_compounds(ast)
    return ast


