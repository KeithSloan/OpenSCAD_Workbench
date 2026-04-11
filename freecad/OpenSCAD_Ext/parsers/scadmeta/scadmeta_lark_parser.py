"""
Lark-based OpenSCAD metadata parser.

Parses a SCAD source file and returns a populated :class:`ScadMeta` object.
Uses Earley parser with dynamic lexer for robustness against the syntactic
quirks of OpenSCAD (e.g. ``<path>`` vs ``<`` comparison operator).

Public API
----------
    parse_scad_file(path: str) -> ScadMeta
"""

from __future__ import annotations

import os
import re
from typing import List

from lark import Lark, Tree, Token, UnexpectedInput

from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_grammar import SCAD_META_GRAMMAR
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_model import (
    ScadMeta,
    ScadModuleMeta,
    ScadFunctionMeta,
    ScadParam,
)

# ---------------------------------------------------------------------------
# Build the Lark parser once at import time (shared across calls).
# Earley + dynamic lexer handles SCAD's ambiguous angle-bracket syntax.
# ---------------------------------------------------------------------------
_parser = Lark(
    SCAD_META_GRAMMAR,
    parser="earley",
    lexer="dynamic",
    ambiguity="resolve",
    propagate_positions=True,
)

# Regex fallback for BOSL2-style header comment blocks
_BOSL2_HEADER_RE = re.compile(r"/{60,}")
_INCLUDE_IN_COMMENT_RE = re.compile(r"include\s*<([^>]+)>")


# ---------------------------------------------------------------------------
# Internal tree-walking helpers
# ---------------------------------------------------------------------------

def _token_str(token) -> str:
    """Return string value of a Lark Token, stripping angle brackets."""
    s = str(token)
    return s.strip("<>").strip()


def _expr_to_str(tree) -> str:
    """
    Reconstruct a compact string representation of an expression tree.
    Used to store variable default values.
    """
    if isinstance(tree, Token):
        return str(tree)
    if isinstance(tree, Tree):
        parts = [_expr_to_str(c) for c in tree.children]
        name = tree.data
        if name == "vector":
            return "[" + ", ".join(parts) + "]"
        if name == "range_expr":
            if len(parts) == 3:
                return f"[{parts[0]}:{parts[1]}:{parts[2]}]"
            return f"[{parts[0]}:{parts[1]}]"
        if name in ("add", "sub", "mul", "div", "mod"):
            ops = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%"}
            return f"{parts[0]}{ops[name]}{parts[1]}"
        if name in ("eq", "neq", "lt", "lte", "gt", "gte"):
            ops = {"eq": "==", "neq": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
            return f"{parts[0]}{ops[name]}{parts[1]}"
        if name == "neg":
            return f"-{parts[0]}"
        if name == "func_call":
            args = ", ".join(parts[1:])
            return f"{parts[0]}({args})"
        if name == "index":
            return f"{parts[0]}[{parts[1]}]"
        if name in ("number", "string", "bool_val", "undef_val", "name_ref"):
            return parts[0] if parts else ""
        # generic fallback: join children with spaces
        return " ".join(parts)
    return ""


def _parse_param_list(subtree: Tree) -> List[ScadParam]:
    """Extract parameters from a ``param_list`` tree node."""
    params: List[ScadParam] = []
    for child in subtree.children:
        if isinstance(child, Tree) and child.data == "param":
            tokens = [c for c in child.children if isinstance(c, Token) and c.type == "NAME"]
            exprs = [c for c in child.children if isinstance(c, Tree)]
            name = str(tokens[0]) if tokens else ""
            default = _expr_to_str(exprs[0]) if exprs else None
            params.append(ScadParam(name=name, default=default))
    return params


def _extract_preceding_comments(source_lines: List[str], line_number: int) -> List[str]:
    """
    Walk backwards from *line_number* (1-based) collecting contiguous
    ``//`` comment lines immediately before a definition.
    """
    comments: List[str] = []
    idx = line_number - 2  # convert to 0-based and go one line up
    while idx >= 0:
        stripped = source_lines[idx].strip()
        if stripped.startswith("//"):
            comments.insert(0, stripped.lstrip("/").strip())
            idx -= 1
        else:
            break
    return comments


def _apply_bosl2_comments(obj, comments: List[str]) -> None:
    """
    Apply BOSL2-style comment annotations to a module or function meta object.
    Recognises keys: Module:, Description:, Synopsis:, Usage:
    """
    for cmt in comments:
        lower = cmt.lower()
        if lower.startswith("module:"):
            obj.name = cmt.split(":", 1)[1].strip()
        elif lower.startswith("description:"):
            obj.description = cmt.split(":", 1)[1].strip()
        elif lower.startswith("synopsis:"):
            obj.synopsis = cmt.split(":", 1)[1].strip()
        elif isinstance(obj, ScadModuleMeta) and lower.startswith("usage:"):
            obj.usage.append(cmt.split(":", 1)[1].strip())
        else:
            if obj.description:
                obj.description += " " + cmt
            else:
                obj.description = cmt


def _parse_bosl2_header_includes(source_lines: List[str]) -> List[str]:
    """
    Extract include paths that appear inside BOSL2-style block-comment headers::

        //////////////////////////////////////////////////////////////////////
        // include <bosl2/std.scad>
        //////////////////////////////////////////////////////////////////////
    """
    found: List[str] = []
    in_header = False
    for line in source_lines:
        if _BOSL2_HEADER_RE.match(line.strip()):
            in_header = not in_header
            continue
        if in_header:
            m = _INCLUDE_IN_COMMENT_RE.search(line)
            if m:
                found.append(m.group(1))
    return found


# ---------------------------------------------------------------------------
# Top-level geometry detection
# ---------------------------------------------------------------------------

_GEOMETRY_CALLS = frozenset({
    "cube", "sphere", "cylinder", "cone", "polyhedron", "polygon", "circle",
    "square", "text", "import", "surface",
    "union", "difference", "intersection", "hull", "minkowski",
    "translate", "rotate", "scale", "mirror", "multmatrix", "offset",
    "linear_extrude", "rotate_extrude", "projection",
    "color", "render", "group",
    "echo", "assert",
})

_GEOMETRY_CALL_PATTERN = re.compile(
    r"^\s*(?:[%#!*]\s*)?(" + "|".join(_GEOMETRY_CALLS) + r")\s*[\(\{]",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_scad_file(path: str) -> ScadMeta:
    """
    Parse the SCAD file at *path* and return a :class:`ScadMeta`.

    Falls back to regex-based extraction when Lark cannot parse the file
    (e.g. unsupported syntax extensions).
    """
    meta = ScadMeta(
        source_file=path,
        base_name=os.path.basename(path),
    )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return meta

    source_lines = source.splitlines()

    # Cheap pre-pass: detect BOSL2 header comment includes
    meta.comment_includes = _parse_bosl2_header_includes(source_lines)

    # --- Lark parse ---
    try:
        tree = _parser.parse(source)
    except UnexpectedInput:
        # Fall back to regex extraction so a single bad file does not block scanning
        _regex_fallback(source, source_lines, meta)
        return meta

    # Walk top-level statements only
    _walk_top_level(tree, source_lines, meta)

    return meta


def _walk_top_level(tree: Tree, source_lines: List[str], meta: ScadMeta) -> None:
    """Process only the direct children of ``start``."""
    for node in tree.children:
        if not isinstance(node, Tree):
            continue
        _dispatch_statement(node, source_lines, meta, top_level=True)


def _dispatch_statement(node: Tree, source_lines: List[str], meta: ScadMeta,
                         top_level: bool) -> None:
    name = node.data

    if name == "include_stmt":
        angle = node.children[0]
        meta.includes.append(_token_str(angle))

    elif name == "use_stmt":
        angle = node.children[0]
        meta.uses.append(_token_str(angle))

    elif name == "assign_stmt":
        tokens = [c for c in node.children if isinstance(c, Token)]
        exprs = [c for c in node.children if isinstance(c, Tree) or
                 (isinstance(c, Token) and c.type in ("NUMBER", "ESCAPED_STRING", "BOOL", "NAME"))]
        var_name = str(tokens[0]) if tokens else None
        # children layout: NAME token, then expr tree/token
        children = list(node.children)
        if len(children) >= 2 and isinstance(children[0], Token):
            var_name = str(children[0])
            val = _expr_to_str(children[1]) if len(children) > 1 else ""
            if var_name and top_level:
                meta.variables[var_name] = val

    elif name == "module_def":
        _handle_module_def(node, source_lines, meta)

    elif name == "function_def":
        _handle_function_def(node, source_lines, meta)

    elif name in ("call_stmt", "if_stmt", "for_stmt", "let_stmt", "modifier_stmt"):
        if top_level:
            # Any of these at the top level means the file produces geometry
            meta.has_top_level_calls = True


def _handle_module_def(node: Tree, source_lines: List[str], meta: ScadMeta) -> None:
    children = list(node.children)
    name_token = next((c for c in children if isinstance(c, Token) and c.type == "NAME"), None)
    if name_token is None:
        return

    mod = ScadModuleMeta(name=str(name_token))

    # Line number for comment lookup
    if hasattr(name_token, "line"):
        mod.line_number = name_token.line
        comments = _extract_preceding_comments(source_lines, name_token.line)
        if comments:
            _apply_bosl2_comments(mod, comments)

    # Parameters
    param_tree = next((c for c in children if isinstance(c, Tree) and c.data == "param_list"), None)
    if param_tree:
        mod.params = _parse_param_list(param_tree)

    # First comment inside block as description (if not already set)
    if not mod.description:
        block = next((c for c in children if isinstance(c, Tree) and c.data == "block"), None)
        if block:
            first_stmt = next((c for c in block.children if isinstance(c, Tree)), None)
            # We don't deep-parse the block for comments; rely on preceding comments

    meta.modules.append(mod)


def _handle_function_def(node: Tree, source_lines: List[str], meta: ScadMeta) -> None:
    children = list(node.children)
    name_token = next((c for c in children if isinstance(c, Token) and c.type == "NAME"), None)
    if name_token is None:
        return

    fn = ScadFunctionMeta(name=str(name_token))

    if hasattr(name_token, "line"):
        fn.line_number = name_token.line
        comments = _extract_preceding_comments(source_lines, name_token.line)
        if comments:
            _apply_bosl2_comments(fn, comments)

    param_tree = next((c for c in children if isinstance(c, Tree) and c.data == "param_list"), None)
    if param_tree:
        fn.params = _parse_param_list(param_tree)

    meta.functions.append(fn)


# ---------------------------------------------------------------------------
# Regex fallback (used when Lark fails)
# ---------------------------------------------------------------------------

_RE_INCLUDE = re.compile(r"^\s*include\s*<([^>]+)>", re.MULTILINE)
_RE_USE = re.compile(r"^\s*use\s*<([^>]+)>", re.MULTILINE)
_RE_VARIABLE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*([^;]+);", re.MULTILINE)
_RE_MODULE = re.compile(r"^\s*module\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE)
_RE_FUNCTION = re.compile(r"^\s*function\s+(\w+)\s*\(([^)]*)\)\s*=", re.MULTILINE)


def _parse_params_from_str(params_str: str) -> List[ScadParam]:
    params = []
    for part in params_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            n, d = part.split("=", 1)
            params.append(ScadParam(name=n.strip(), default=d.strip()))
        else:
            params.append(ScadParam(name=part))
    return params


def _regex_fallback(source: str, source_lines: List[str], meta: ScadMeta) -> None:
    """Populate *meta* using regex patterns when Lark parsing fails."""

    for m in _RE_INCLUDE.finditer(source):
        path = m.group(1).strip()
        if path not in meta.includes:
            meta.includes.append(path)

    for m in _RE_USE.finditer(source):
        path = m.group(1).strip()
        if path not in meta.uses:
            meta.uses.append(path)

    for m in _RE_VARIABLE.finditer(source):
        name, val = m.group(1).strip(), m.group(2).strip()
        if name not in meta.variables:
            meta.variables[name] = val

    for m in _RE_MODULE.finditer(source):
        mod = ScadModuleMeta(
            name=m.group(1),
            params=_parse_params_from_str(m.group(2)),
        )
        # Preceding comment
        line_no = source[:m.start()].count("\n") + 1
        mod.line_number = line_no
        comments = _extract_preceding_comments(source_lines, line_no)
        if comments:
            _apply_bosl2_comments(mod, comments)
        meta.modules.append(mod)

    for m in _RE_FUNCTION.finditer(source):
        fn = ScadFunctionMeta(
            name=m.group(1),
            params=_parse_params_from_str(m.group(2)),
        )
        line_no = source[:m.start()].count("\n") + 1
        fn.line_number = line_no
        meta.functions.append(fn)

    # Top-level call detection
    if _GEOMETRY_CALL_PATTERN.search(source):
        meta.has_top_level_calls = True
