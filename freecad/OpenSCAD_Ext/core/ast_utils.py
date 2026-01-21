from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import (
    Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Hull, Minkowski,
    Group, MultMatrix, Translate, Rotate, Scale
)
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


def get_ast_children(node):
    """
    Return a list of child AST nodes, handling all known layouts.
    """

    if not node:
        return []

    # Case 1: direct list
    if isinstance(getattr(node, "children", None), list):
        return node.children

    # Case 2: dict with 'children'
    if isinstance(getattr(node, "children", None), dict):
        if "children" in node.children:
            return node.children["children"]
        if "nodes" in node.children:
            return node.children["nodes"]

    # Case 3: body-style nodes
    if isinstance(getattr(node, "body", None), list):
        return node.body

    return []


def ast_node_to_scad(node, indent=0, FnMax=64, Fa=12, Fs=0.5):
    """
    Convert an AST node to OpenSCAD code.

    Parameters:
    - node: AST node (primitive, transform, boolean, hull, etc.)
    - indent: indentation level for formatting
    - FnMax, Fa, Fs: global tessellation parameters

    Returns:
    - str: OpenSCAD string representing the node and its subtree

    Strategy:
    - Sets top-level tessellation at indent==0.
    - Handles primitives (Sphere, Circle, Cube) using node.params.
    - Handles transforms (Translate, Rotate, MultMatrix) recursively.
    - Handles boolean operations (Union, Difference, Intersection, Hull, Minkowski).
    - Preserves per-node tessellation ($fn/$fa/$fs) if defined.
    - Generates SCAD text recursively, properly indented for readability.
    
    Notes:
    - Does NOT overwrite node-specific $fn/$fa/$fs with defaults.
    - Output can be used directly for OpenSCAD fallback generation.
    """

    IND = " " * indent
    lines = []

    # Helper: get tessellation for a node (use global if missing or None)
    def get_tess(n):
        """
        Get tessellation parameters for a node.

        Returns a tuple (fn, fa, fs):
        - Uses node-specific parameters if present.
        - Falls back to global defaults otherwise.

        Notes:
        - Prevents None values being injected into SCAD code.
        - Ensures consistent tessellation across both native BRep and fallback OpenSCAD operations.
        """

        fn = fa = fs = None

        if hasattr(n, "params") and isinstance(n.params, dict):
            fn = n.params.get("$fn")
            fa = n.params.get("$fa")
            fs = n.params.get("$fs")

        fn = FnMax if fn is None else fn
        fa = Fa    if fa is None else fa
        fs = Fs    if fs is None else fs

        return fn, fa, fs


    # Top-level tessellation
    if indent == 0:
        lines.append(f"$fn={FnMax};")
        lines.append(f"$fa={Fa};")
        lines.append(f"$fs={Fs};")
        write_log("AST", f"Set top-level tessellation $fn={FnMax}, $fa={Fa}, $fs={Fs}")

    # --- PRIMITIVES ---
    node_type = type(node).__name__

    if node_type in ["Circle", "Sphere", "Cube"]:
        fn, fa, fs = get_tess(node)
        lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
        if node_type == "Circle":
            r = node.params.get("r", 1.0)
            lines.append(f"circle(r={r});")
            write_log("AST", f"Circle r={r} tessellation $fn={fn}, $fa={fa}, $fs={fs}")
        elif node_type == "Sphere":
            r = node.params.get("r", 1.0)
            lines.append(f"sphere(r={r});")
            write_log("AST", f"Sphere r={r} tessellation $fn={fn}, $fa={fa}, $fs={fs}")
        elif node_type == "Cube":
            size = node.params.get("size", [1,1,1])
            lines.append(f"cube(size={size});")
            write_log("AST", f"Cube size={size} tessellation $fn={fn}, $fa={fa}, $fs={fs}")
        return "\n".join([IND + l for l in lines])

    # --- TRANSFORMS ---
    elif node_type in ["Translate", "Rotate", "MultMatrix"]:
        children = getattr(node, "children", [])
        lines_child = []
        for c in children:
            lines_child.append(ast_node_to_scad(c, indent + 4, FnMax, Fa, Fs))

        if node_type == "Translate":
            v = node.params.get("v", [0,0,0])
            lines.append(f"translate({v}) {{")
        elif node_type == "Rotate":
            a = node.params.get("a", [0,0,0])
            lines.append(f"rotate({a}) {{")
        elif node_type == "MultMatrix":
            m = node.params.get("matrix")
            lines.append(f"multmatrix({m}) {{")

        lines.extend(lines_child)
        lines.append("}")
        write_log("AST", f"{node_type} applied with {len(children)} children")
        return "\n".join([IND + l for l in lines])

    # --- HULL / MINKOWSKI ---
    elif node_type in ["Hull", "Minkowski"]:
        children = getattr(node, "children", [])
        write_log("AST", f"{node_type} node has {len(children)} children")

        child_lines = []
        for c in children:
            child_lines.append(ast_node_to_scad(c, indent + 4, FnMax, Fa, Fs))

        lines.append(f"{node_type.lower()}() {{")
        lines.extend(child_lines)
        lines.append("}")
        return "\n".join([IND + l for l in lines])

    # --- BOOLEAN (Union/Difference/Intersection) ---
    elif node_type in ["Union", "Difference", "Intersection"]:
        children = getattr(node, "children", [])
        write_log("AST", f"{node_type} node with {len(children)} children")

        child_lines = []
        for c in children:
            child_lines.append(ast_node_to_scad(c, indent + 4, FnMax, Fa, Fs))

        lines.append(f"{node_type.lower()}() {{")
        lines.extend(child_lines)
        lines.append("}")
        return "\n".join([IND + l for l in lines])

    # --- Unknown node ---
    else:
        write_log("AST", f"Unknown node type: {node_type}, falling back to OpenSCAD")
        # fallback string, ensure we return a string
        return "\n".join([IND + f"// Unknown node type: {node_type}"])


    # --- parameter formatting --------------------------------------
    def format_params(params):
        if not params:
            return ""
        parts = []
        for k, v in params.items():
            parts.append(f"{k} = {format_value(v)}")
        return ", ".join(parts)

    def format_value(v):
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return "[" + ", ".join(format_value(x) for x in v) + "]"
        if isinstance(v, dict):
            return "[" + ", ".join(
                "[" + ", ".join(format_value(x) for x in row) + "]"
                for row in v.values()
            ) + "]"
        return str(v)

    # --- AST object -------------------------------------------------
    node_type = getattr(node, "node_type", None)
    params    = getattr(node, "params", {}) or {}
    children = get_ast_children(node)

    # --- block nodes (hull, union, multmatrix, etc.) -----------------
    BLOCK_NODES = {
        "hull", "union", "difference", "intersection",
        "multmatrix", "translate", "rotate", "scale",
        "mirror", "color"
    }

    if node_type in BLOCK_NODES:
        p = format_params(params)
        header = f"{IND}{node_type}({p}) {{\n"

        body = ""
        for c in children:
            body += ast_node_to_scad(c, indent + 1)
            if not body.endswith("\n"):
                body += "\n"

        footer = f"{IND}}}\n"
        return header + body + footer

    # --- primitive geometry calls ----------------------------------
    p = format_params(params)
    return f"{IND}{node_type}({p});\n"


def flatten_ast_node(node, indent=0, _visited=None):
    """
    Recursively flatten an AST node and all children/params into a string.
    """

    if _visited is None:
        _visited = set()

    pad = "  " * indent

    # Protect against cycles
    node_id = id(node)
    if node_id in _visited:
        return f"{pad}<circular-ref {type(node).__name__}>\n"
    _visited.add(node_id)

    # Primitive types
    if node is None or isinstance(node, (int, float, bool, str)):
        return f"{pad}{repr(node)}\n"

    # Lists / tuples
    if isinstance(node, (list, tuple)):
        out = f"{pad}[{type(node).__name__}]\n"
        for i, item in enumerate(node):
            out += f"{pad}  ({i})\n"
            out += flatten_ast_node(item, indent + 2, _visited)
        return out

    # Generic object (AST node)
    out = f"{pad}{type(node).__name__}\n"

    # Common AST attribute names (if present)
    for attr in ("type", "name", "value", "op"):
        if hasattr(node, attr):
            out += f"{pad}  {attr}: {getattr(node, attr)!r}\n"

    # Walk all attributes
    if hasattr(node, "__dict__"):
        for key, value in node.__dict__.items():
            if key.startswith("_"):
                continue
            out += f"{pad}  {key}:\n"
            out += flatten_ast_node(value, indent + 2, _visited)

    return out





