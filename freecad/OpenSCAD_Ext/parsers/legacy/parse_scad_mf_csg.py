import os
import re
import subprocess
import tempfile


# -----------------------------------------------------------
# Parse scad file for Module and functions, 
# creating new Modules and functions with raw csg
# -----------------------------------------------------------

# ------------------------------------------------------------
# 1. Parse module and function definitions (TEXTUAL)
# ------------------------------------------------------------

MODULE_RE = re.compile(r'^\s*module\s+(\w+)\s*\((.*?)\)', re.MULTILINE)
FUNCTION_RE = re.compile(r'^\s*function\s+(\w+)\s*\((.*?)\)', re.MULTILINE)


def parse_scad_definitions(scad_file):
    """
    Returns:
        {
          "modules": {name: arg_string},
          "functions": {name: arg_string}
        }
    """
    with open(scad_file, "r", encoding="utf-8") as f:
        text = f.read()

    modules = {m.group(1): m.group(2) for m in MODULE_RE.finditer(text)}
    functions = {f.group(1): f.group(2) for f in FUNCTION_RE.finditer(text)}

    return {
        "modules": modules,
        "functions": functions,
    }


# ------------------------------------------------------------
# 2. Call OpenSCAD to evaluate CSG
# ------------------------------------------------------------

def _run_openscad(scad_file, call_expr):
    """
    call_expr example:
        mymodule();
        myfunc();
    """
    with tempfile.TemporaryDirectory() as tmp:
        test_scad = os.path.join(tmp, "test.scad")
        out_csg = os.path.join(tmp, "out.csg")

        with open(test_scad, "w") as f:
            f.write(f'use <{scad_file}>;\n')
            f.write(call_expr + ";\n")

        cmd = [
            "openscad",
            "-o", out_csg,
            "--export-format", "csg",
            test_scad
        ]

        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            return None

        if not os.path.exists(out_csg):
            return None

        return open(out_csg, "r").read()


# ------------------------------------------------------------
# 3. Analyze CSG for dimensionality
# ------------------------------------------------------------

CSG_3D_TOKENS = ("cube", "sphere", "cylinder", "polyhedron")
CSG_2D_TOKENS = ("square", "circle", "polygon")


def classify_csg(csg_text):
    if not csg_text:
        return "none"

    text = csg_text.lower()

    if any(tok in text for tok in CSG_3D_TOKENS):
        return "3d"

    if any(tok in text for tok in CSG_2D_TOKENS):
        return "2d"

    return "none"


# ------------------------------------------------------------
# 4. Evaluate a module or function
# ------------------------------------------------------------

def evaluate_definition(scad_file, name, kind):
    """
    kind: "module" or "function"
    Returns: "3d" | "2d" | "none"
    """
    if kind == "module":
        expr = f"{name}()"
    else:
        expr = f"{name}()"

    csg = _run_openscad(scad_file, expr)
    return classify_csg(csg)


# ------------------------------------------------------------
# 5. High-level analysis entry point
# ------------------------------------------------------------

def analyze_scad(scad_file):
    """
    Returns metadata structure usable by FreeCAD UI / commands
    """
    defs = parse_scad_definitions(scad_file)
    result = {"modules": {}, "functions": {}}

    for name in defs["modules"]:
        result["modules"][name] = evaluate_definition(
            scad_file, name, "module"
        )

    for name in defs["functions"]:
        result["functions"][name] = evaluate_definition(
            scad_file, name, "function"
        )

    return result

