# ==============================================================
# SCAD For Some Hull & Minkowski need to flatten back to RAW csg 
# ==============================================================

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

def _format_csg_params(node):
    """
    Return parameter string for OpenSCAD reconstruction.
    Prefers raw csg_params if present.
    """
    if node.csg_params is None:
        return ""
    if isinstance(node.csg_params, str):
        return node.csg_params
    if isinstance(node.csg_params, dict):
        return ", ".join(f"{k}={v!r}" for k, v in node.csg_params.items())
    return str(node.csg_params)

'''

def flatten_ast_node_back_to_csg(node):
    """
    Recursively flatten children of a hull node into a list of supported primitives.
    Returns a list of AST nodes that can be used by the hull operation.
    """
    flat_children = []

    for child in node.children:
        # If child is a primitive we support, keep it
        if child.node_type in ("cube", "sphere", "cylinder", "polyhedron"):
            flat_children.append(child)

        # If child is another hull, recurse
        elif child.node_type in ("hull", "minkowski"):
            nested = flatten_hull_minkowski_children(child)
            flat_children.extend(nested)

        # If child is a group, union, difference, etc., recurse into its children
        elif hasattr(child, "children") and child.children:
            nested = flatten_hull_minkowski_children(child)
            flat_children.extend(nested)

        else:
            write_log("Hull", f"Unsupported node inside hull: {child.node_type}")
            # Optional: keep raw fallback for safety
            flat_children.append(child)

    return flat_children

'''
def flatten_ast_node_back_to_csg(node, indent=0):
    pad = " " * indent
    scad_lines = []

    if node is None:
        return ""

    write_log(
        "FLATTEN",
        f"{pad}Flatten node: {node.node_type}, "
        f"children={len(getattr(node, 'children', []))}, "
        f"csg_params={getattr(node, 'csg_params', None)}"
    )

    # -------------------------
    # Transparent group
    # -------------------------
    if node.node_type == "group":
        for child in node.children:
            scad_lines.append(flatten_ast_node_back_to_csg(child, indent))
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Hull / Minkowski
    # -------------------------
    if node.node_type in ("hull", "minkowski"):
        
        scad_lines.append(f"{pad}{node.node_type}() {{")
        for child in node.children:
            scad_lines.append(
                flatten_ast_node_back_to_csg(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # MultMatrix
    # -------------------------
    if node.node_type == "multmatrix":
        matrix_str = _format_csg_params(node)
        scad_lines.append(f"{pad}multmatrix({matrix_str}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_ast_node_back_to_csg(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Boolean CSG operators
    # -------------------------
    if node.node_type in ("union", "difference", "intersection"):
        scad_lines.append(f"{pad}{node.node_type}() {{")
        for child in node.children:
            scad_lines.append(
                flatten_ast_node_back_to_csg(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Linear Extrude
    # -------------------------
    if node.node_type == "linear_extrude":
        params = _format_csg_params(node)
        scad_lines.append(f"{pad}linear_extrude({params}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_ast_node_back_to_csg(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Rotate Extrude
    # -------------------------
    if node.node_type == "rotate_extrude":
        params = _format_csg_params(node)
        scad_lines.append(f"{pad}rotate_extrude({params}) {{")
        for child in node.children:
            scad_lines.append(
                flatten_ast_node_back_to_csg(child, indent + 4)
            )
        scad_lines.append(f"{pad}}}")
        return "\n".join(filter(None, scad_lines))

    # -------------------------
    # Text (always OpenSCAD fallback)
    # -------------------------
    if node.node_type == "text":
        params = _format_csg_params(node)
        return f"{pad}text({params});"

    # -------------------------
    # Generic fallback (cube, sphere, etc.)
    # -------------------------
    params = _format_csg_params(node)
    if params:
        return f"{pad}{node.node_type}({params});"
    else:
        return f"{pad}{node.node_type}();"
