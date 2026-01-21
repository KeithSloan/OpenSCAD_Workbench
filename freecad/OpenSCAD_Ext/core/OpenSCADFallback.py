# -*- coding: utf-8 -*-
"""
OpenSCADFallback
================

Centralised execution of OpenSCAD fallback for AST nodes that cannot be
represented as native FreeCAD BRep shapes.

This module:
- Converts AST → SCAD
- Runs OpenSCAD CLI
- Imports STL → Mesh → Shape

Design rules
------------
- processAST.py MUST NOT import this module
- importASTCSG.py is responsible for calling fallback
"""

import os
import subprocess
import tempfile

import FreeCAD
import Mesh
from Part import Shape

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_helpers import (
    ast_to_scad_string,
    class_ast_to_scad_string,
)


def fallback_to_OpenSCAD(doc, node, reason="Fallback requested"):
    """
    Convert an AST node into a FreeCAD Shape using OpenSCAD → STL.

    Args:
        doc: FreeCAD document
        node: AST node (class-based or legacy dict-based)
        reason: Logging/debug text

    Returns:
        Part.Shape or None
    """

    # --------------------------------------------------
    # Identify node + generate SCAD
    # --------------------------------------------------
    if hasattr(node, "node_type"):
        node_type = node.node_type
        scad_str = class_ast_to_scad_string(node, top_level=True)
    else:
        node_type = node.get("type", "AST")
        scad_str = ast_to_scad_string(node, top_level=True)

    write_log(
        "Info",
        f"OpenSCAD fallback: {node_type} | Reason: {reason}"
    )

    FreeCAD.Console.PrintMessage(
        f"[AST] OpenSCAD fallback invoked for {node_type}\n"
    )
    FreeCAD.Console.PrintMessage(
        f"[AST] SCAD source:\n{scad_str}\n"
    )

    # --------------------------------------------------
    # Locate OpenSCAD
    # --------------------------------------------------
    OPENSCAD_CMD = FreeCAD.ParamGet(
        "User parameter:BaseApp/Preferences/Mod/OpenSCAD"
    ).GetString("openscadexecutable")

    if not OPENSCAD_CMD or not os.path.exists(OPENSCAD_CMD):
        FreeCAD.Console.PrintError(
            "[AST] OpenSCAD executable not configured\n"
        )
        return None

    # --------------------------------------------------
    # Temporary files
    # --------------------------------------------------
    tmp_scad = tempfile.NamedTemporaryFile(delete=False, suffix=".scad")
    tmp_stl = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")

    tmp_scad.write(scad_str.encode("utf-8"))
    tmp_scad.close()
    tmp_stl.close()

    # --------------------------------------------------
    # Run OpenSCAD
    # --------------------------------------------------
    try:
        subprocess.run(
            [OPENSCAD_CMD, "-o", tmp_stl.name, tmp_scad.name],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        FreeCAD.Console.PrintError(
            f"[AST] OpenSCAD failed:\n{e.stderr.decode()}\n"
        )
        os.unlink(tmp_scad.name)
        os.unlink(tmp_stl.name)
        return None

    # --------------------------------------------------
    # Import STL → Shape
    # --------------------------------------------------
    try:
        mesh = Mesh.Mesh(tmp_stl.name)
        shape = Shape()
        shape.makeShapeFromMesh(mesh.Topology, 0.05)
        shape = shape.removeSplitter()

        obj = doc.addObject("Part::Feature", node_type)
        obj.Shape = shape

    except Exception as e:
        FreeCAD.Console.PrintError(
            f"[AST] STL → Shape failed: {e}\n"
        )
        shape = None

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------
    os.unlink(tmp_scad.name)
    os.unlink(tmp_stl.name)

    return shape
