# -*- coding: utf8 -*-
#****************************************************************************
#*   AST Processing for OpenSCAD CSG importer                               *
#*   Converts AST nodes to FreeCAD Shapes or SCAD strings with fallbacks    *
#*                                                                          *
#*      Returns Shape                                                       *
#****************************************************************************
'''
Rules:
shape is None → empty / ignored
Placement() = identity
Placement is always applied last, never baked unless required
'''
import os
import subprocess
import tempfile
import FreeCAD
from pathlib import Path


#from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
# -----------------------------
# Utility functions
# -----------------------------

BaseError = FreeCAD.Base.FreeCADError

class OpenSCADError(BaseError):
    def __init__(self,value):
        self.value= value
    #def __repr__(self):
    #    return self.msg
    def __str__(self):
        return repr(self.value)


def get_openscad_executable():          # Shared Function
    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
    openscad_exe = prefs.GetString("openscadexecutable", "")

    if not openscad_exe or not os.path.isfile(openscad_exe):
        write_log("OpenSCAD", f"Invalid OpenSCAD executable: {openscad_exe}")
        raise FileNotFoundError(f"OpenSCAD executable not found at {openscad_exe}")

        return None
    return openscad_exe


def call_openscad_scad_string(
    scad_str,
    export_type="stl",      # "stl"  Note: dxf does not work with Pipes use different function
    timeout_sec=60
):
    """
    Call OpenSCAD with a SCAD string and export STL or DXF.
    Returns output path on success, None on failure.
    """
    write_log("OpenSCAD",f"Call OpenSCAD String via Temo File")
    openscad_exe = get_openscad_executable()

    # Write temp SCAD
    with tempfile.NamedTemporaryFile(
        suffix=".scad",
        delete=False,
        mode="w",
        encoding="utf-8"
    ) as f:
        scad_path = f.name
        f.write(scad_str)

    write_log("OpenSCAD",f"temp file {scad_path}")

    out_path = scad_path.replace(".scad", f".{export_type}")

    fn=12
    fa=15
    fs=2
    
    write_log("OpenSCAD","Add $fn, $fa, $fs")
    # Base command
    cmd = [
        openscad_exe,
        "--export-format", export_type,
        '-D', f'$fn={int(fn)}',
        '-D', f'$fa={float(fa)}',
        '-D', f'$fs={float(fs)}',
        "-o", out_path,
        scad_path,
    ]

    # Base command
    #cmd = [
    #    openscad_exe,
    #    "-o", out_path,
    #    scad_path,
    #

    # DOES NOT WORK WITH dxf - dxf must use Temp Files
    # DXF needs render for 2D geometry
    #if export_type.lower() == "dxf":
    #    cmd.insert(1, "--render")

    write_log("OpenSCAD", f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout_sec,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        write_log("OpenSCAD", f"Generated: {out_path}")

        print("stdout:", result.stdout)
        print("stderr:", result.stderr)
        print("returncode:", result.returncode)
        return out_path

    except subprocess.TimeoutExpired:
        write_log("OpenSCAD", f"Timeout after {timeout_sec}s")
    except subprocess.CalledProcessError as e:
        write_log("OpenSCAD", f"STDOUT:\n{e.stdout}")
        write_log("OpenSCAD", f"STDERR:\n{e.stderr}")

    return None

def export_scad_str_to_svg(scad_str, out_name="output.svg"):
    """
    Export a SCAD string to SVG using OpenSCAD.
    Returns absolute path to SVG file.
    """

    openscad = get_openscad_executable()
    if not openscad:
        raise RuntimeError("OpenSCAD executable not found")

    tmpdir = Path(tempfile.mkdtemp(prefix="scad_to_svg_"))
    scad_file = tmpdir / "temp.scad"
    svg_file = tmpdir / out_name

    # Write SCAD
    scad_file.write_text(scad_str, encoding="utf-8")

    cmd = [
        openscad,
        "-o", str(svg_file),
        str(scad_file)
    ]

    # Diagnostic output
    write_log("", "")
    write_log("INFO", "=== OpenSCAD diagnostic command ===")
    write_log("INFO", " ".join(cmd))
    write_log("INFO", f"SVG output will be: {svg_file}")
    write_log("INFO", f"Temp folder: {tmpdir}")
    write_log("INFO", "==================================")
    write_log("", "")

    # Run OpenSCAD
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if proc.stdout:
        for line in proc.stdout.splitlines():
            write_log("OpenSCAD", line)

    # Validate output
    if not svg_file.exists() or svg_file.stat().st_size == 0:
        raise RuntimeError(f"SVG file not created: {svg_file}")

    return str(svg_file)


def export_scad_str_to_dxf(scad_str, out_name="output.dxf"):
    """
    Export SCAD string to DXF using OpenSCAD.
    Returns the path to the DXF file as string (for importEZDXFshape)
    """

    openscad = get_openscad_executable()
    if not openscad:
        raise RuntimeError("OpenSCAD executable not found")

    tmpdir = Path(tempfile.mkdtemp(prefix="scad_to_dxf_"))
    scad_file = tmpdir / "temp.scad"
    dxf_file = tmpdir / out_name

    # Write SCAD
    scad_file.write_text(scad_str, encoding="utf-8")

    cmd = [
        openscad,
        "-o", str(dxf_file),
        str(scad_file)
    ]

    # Diagnostic
    write_log("DXF_EXPORT", "=== OpenSCAD diagnostic command ===")
    write_log("DXF_EXPORT", " ".join(cmd))
    write_log("DXF_EXPORT", f"DXF output will be: {dxf_file}")
    write_log("DXF_EXPORT", f"Temp folder: {tmpdir}")
    write_log("DXF_EXPORT", "==================================")

    # Run OpenSCAD
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in proc.stdout.splitlines():
        write_log("OpenSCAD", line)

    if not dxf_file.exists() or dxf_file.stat().st_size == 0:
        raise RuntimeError(f"DXF file not created: {dxf_file}")

    return str(dxf_file), tmpdir

import ezdxf
from pathlib import Path

def diagnose_dxf(dxf_path):
    """
    Read a DXF file using EZDXF and print diagnostic info.
    """
    dxf_path = Path(dxf_path)

    if not dxf_path.exists():
        print(f"DXF file not found: {dxf_path}")
        return

    print(f"=== Diagnosing DXF: {dxf_path} ===")

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        print(f"Failed to read DXF: {e}")
        return

    print(f"DXF version: {doc.dxfversion}")
    modelspace = doc.modelspace()
    num_entities = len(modelspace)
    print(f"Number of entities in modelspace: {num_entities}")

    for i, e in enumerate(modelspace):
        etype = e.dxftype()
        layer = e.dxf.layer
        print(f"Entity {i+1}: Type={etype}, Layer={layer}")

    print("=== End of DXF diagnostic ===")



def save_export_scad_str_to_dxf(scad_str: str, filename: str = "output.dxf", diagnostic: bool = True) -> tuple[Path, Path]:
    """
    Export a SCAD string to DXF using OpenSCAD.
    Returns a tuple: (DXF path, temp directory)
    
    If diagnostic=True, prints the exact OpenSCAD command from get_openscad_executable() for copy/paste testing.
    """
    # 1. Get OpenSCAD executable from FreeCAD preferences
    openscad_exe = get_openscad_executable()

    # 2. Create a unique temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="scad_to_dxf_"))

    # 3. Write SCAD string to temporary SCAD file
    scad_file = temp_dir / "temp.scad"
    scad_file.write_text(scad_str)

    # 4. Target DXF file path
    dxf_file = temp_dir / filename

    # 5. Build OpenSCAD command
    cmd = [openscad_exe, "-o", str(dxf_file), str(scad_file)]

    # 6. Diagnostic output: exact command
    print("\n=== OpenSCAD diagnostic command ===")
    # Quote paths that contain spaces
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    print("DXF output will be:", dxf_file)
    print("Temp folder:", temp_dir)
    print("==================================\n")

    env = os.environ.copy()

    # Critical for macOS fontconfig
    env.setdefault("FONTCONFIG_PATH", "/etc/fonts")
    env.setdefault("FONTCONFIG_FILE", "/etc/fonts/fonts.conf")

    # 7. Run OpenSCAD
    result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)


    # 8. Ensure DXF exists; fallback if OpenSCAD renamed it
    if not dxf_file.exists():
        dxf_files = list(temp_dir.glob("*.dxf"))
        if not dxf_files:
            raise RuntimeError("DXF export failed: no DXF file found in temporary directory")
        dxf_file = dxf_files[0]

    # 9. Return tuple (DXF path, temp directory) for tuple-based AST changes
    return dxf_file.resolve(), temp_dir


'''
def generate_stl_from_scad(scad_str, timeout_sec=60):
    call_openscad_scad_string(scad_str, timeout_sec, return_type=".stl")



def _mesh_to_shape_worker(stl_path, tolerance, queue):
    """Worker process to safely run makeShapeFromMesh with timeout"""
    try:
        mesh_obj = Mesh.Mesh(stl_path)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh_obj.Topology, tolerance)
        queue.put(shape)
    except Exception as e:
        queue.put(e)

    # See also stl_to_shape
def shape_from_scad(scad_str, refine=True):
    stl_path = generate_stl_from_scad(scad_str)
    if not stl_path:
        return None

    # Import STL into FreeCAD Part.Shape
    mesh_obj = Mesh.Mesh(stl_path)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh_obj.Topology, 0.0001)

    if refine:
        try:
            return_shape = shape.copy().refineShape()
            if return_shape.isNull() or return_shape.isEmpty():
                write_log("STL", "RefineShape returned empty shape, falling back to original")
                return_shape = shape
        except Exception as e:
            write_log("STL", f"RefineShape failed: {e}, using original shape")
            return_shape = shape
    else:
        return_shape = shape
        


    # See also shape_from_scad - uses refine, no so much checking
def stl_to_shape(stl_path, tolerance=0.05, timeout=None):
    """
    Import STL into FreeCAD and convert to Part.Shape.
    Always attempts to return a Solid.
    Returns a Part.Shape or None on failure.
    """

    if not stl_path or not os.path.isfile(stl_path):
        write_log("AST_Hull:Minkowski", f"STL file not found: {stl_path}")
        return None

    try:
        write_log(
            "AST_Hull:Minkowski",
            f"Importing STL and converting to Part.Shape: {stl_path}"
        )

        # Load STL
        mesh = Mesh.Mesh(stl_path)

        # Instrumentation (API-safe)
        try:
            is_closed = mesh.isSolid()
        except Exception:
            is_closed = False

        facets = getattr(mesh, "CountFacets", 0)

        write_log(
            "AST_Hull:Minkowski",
            f"Mesh facets={facets}, solid={is_closed}"
        )

        # Mesh → Shape (shell)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, tolerance)
        shape = shape.removeSplitter()

        # Always attempt solid
        if is_closed:
            try:
                solid = Part.makeSolid(shape)
                solid = solid.removeSplitter()

                valid = solid.isValid()
                write_log(
                    "AST_Hull:Minkowski",
                    f"Solid created, valid={valid}"
                )

                return solid

            except Exception as e:
                write_log(
                    "AST_Hull:Minkowski",
                    f"makeSolid failed, falling back to sewing: {e}"
                )

        # Fallback: sew faces → solid
        try:
            shell = Part.makeShell(shape.Faces)
            solid = Part.makeSolid(shell)
            solid = solid.removeSplitter()

            valid = solid.isValid()
            write_log(
                "AST_Hull:Minkowski",
                f"Sewing fallback solid valid={valid}"
            )

            return solid

        except Exception as e:
            write_log(
                "AST_Hull:Minkowski",
                f"Sewing fallback failed, returning shell: {e}"
            )

        return shape

    except Exception as e:
        write_log(
            "AST_Hull:Minkowski",
            f"Failed to convert STL to Shape: {e}"
        )
        return None
'''