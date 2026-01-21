# ast_to_scad.py

def ast_node_to_scad(node, indent=0, FnMax=64, Fa=12, Fs=0.5):
    """
    Convert an AST node to SCAD code.
    Preserves $fn/$fa/$fs from the node's params if present.
    """
    IND = " " * indent
    lines = []

    # Node-specific tessellation
    fn, fa, fs = get_tess(node, FnMax, Fa, Fs)

    if indent == 0:
        lines.append(f"$fn={fn};")
        lines.append(f"$fa={fa};")
        lines.append(f"$fs={fs};")
        write_log("AST", f"Top-level tessellation $fn={fn}, $fa={fa}, $fs={fs}")

    node_type = type(node).__name__
    
    if node_type in ["Circle", "Sphere", "Cube"]:
        params = getattr(node, "params", {})
        if node_type == "Circle":
            r = params.get("r", 1.0)
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"circle(r={r});")
        elif node_type == "Sphere":
            r = params.get("r", 1.0)
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"sphere(r={r});")
        elif node_type == "Cube":
            size = params.get("size", [1,1,1])
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"cube(size={size});")
        return "\n".join([IND + l for l in lines])

    # TODO: handle Hull / Minkowski / transforms recursively

# ast_to_scad.py

def ast_node_to_scad(node, indent=0, FnMax=64, Fa=12, Fs=0.5):
    """
    Convert an AST node to SCAD code.
    Preserves $fn/$fa/$fs from the node's params if present.
    """
    IND = " " * indent
    lines = []

    # Node-specific tessellation
    fn, fa, fs = get_tess(node, FnMax, Fa, Fs)

    if indent == 0:
        lines.append(f"$fn={fn};")
        lines.append(f"$fa={fa};")
        lines.append(f"$fs={fs};")
        write_log("AST", f"Top-level tessellation $fn={fn}, $fa={fa}, $fs={fs}")

    node_type = type(node).__name__
    
    if node_type in ["Circle", "Sphere", "Cube"]:
        params = getattr(node, "params", {})
        if node_type == "Circle":
            r = params.get("r", 1.0)
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"circle(r={r});")
        elif node_type == "Sphere":
            r = params.get("r", 1.0)
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"sphere(r={r});")
        elif node_type == "Cube":
            size = params.get("size", [1,1,1])
            lines.append(f"$fn={fn}; $fa={fa}; $fs={fs};")
            lines.append(f"cube(size={size});")
        return "\n".join([IND + l for l in lines])

    # TODO: handle Hull / Minkowski / transforms recursively

