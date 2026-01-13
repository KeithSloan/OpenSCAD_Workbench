# -*- coding: utf-8 -*-
#***************************************************************************
#*                                                                         *
#*   OpenSCAD AST / CSG Importer                                           *
#*                                                                         *
#*   Responsibilities:                                                     *
#*   - Parse .csg via AST                                                  *
#*   - Attempt native FreeCAD shape construction                           *
#*   - Execute OpenSCAD ONLY when AST processing requests fallback         *
#*                                                                         *
#*   NOTE:                                                                 *
#*   This file is the ONLY place OpenSCAD is executed.                     *
#*   processAST.py must remain pure (no OpenSCAD, no STL).                 *
#*                                                                         *
#***************************************************************************

import os
import tempfile

import FreeCAD
import Part

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

from freecad.OpenSCAD_Ext.parsers.csg_parser.parse_csg_file_to_AST_nodes import (
    parse_csg_file_to_AST_nodes,
    normalize_ast,
)

from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import process_AST
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_to_scad import ast_node_to_scad

# LEGACY OpenSCAD execution helpers (do not extend)
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import (
    run_openscad,
    import_stl,
)


# -------------------------------------------------------------------------
# Public entry point (called by FreeCAD)
# -------------------------------------------------------------------------

def open(filename):
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument()

    write_log("Info", f"Using OpenSCAD AST / CSG Importer")
    processCSG(doc, filename)


# -------------------------------------------------------------------------
# Main processing pipeline
# -------------------------------------------------------------------------

def processCSG(doc, filename):
    write_log("Info", f"Parsing CSG file: {filename}")

    ast_nodes = parse_csg_file_to_AST_nodes(filename)
    ast_nodes = normalize_ast(ast_nodes)

    write_log("Info", f"AST nodes after normalize: {len(ast_nodes)}")

    result = process_AST(doc, ast_nodes, mode="multiple")

    # ---- Case 1: Native FreeCAD shapes ----
    if _is_shape_or_shapes(result):
        _commit_shapes(doc, result)
        return

    # ---- Case 2: OpenSCAD fallback requested ----
    if _is_openscad_fallback(result):
        write_log("Info", "AST requested OpenSCAD fallback")
        shape = _run_openscad_fallback(result)
        _commit_shapes(doc, shape)
        return

    raise TypeError(f"Unsupported result from process_AST: {type(result)}")


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _is_shape_or_shapes(obj):
    if isinstance(obj, Part.Shape):
        return True
    if isinstance(obj, list) and all(isinstance(s, Part.Shape) for s in obj):
        return True
    return False


def _is_openscad_fallback(obj):
    return (
        isinstance(obj, dict)
        and obj.get("type") == "openscad_fallback"
        and "node" in obj
    )


def _commit_shapes(doc, shapes):
    if isinstance(shapes, Part.Shape):
        shapes = [shapes]

    if len(shapes) == 1:
        obj = doc.addObject("Part::Feature", "OpenSCAD")
        obj.Shape = shapes[0]
    else:
        comp = Part.Compound(shapes)
        obj = doc.addObject("Part::Feature", "OpenSCAD_Compound")
        obj.Shape = comp

    doc.recompute()


# -------------------------------------------------------------------------
# OpenSCAD fallback execution
# -------------------------------------------------------------------------

def _run_openscad_fallback(fallback):
    """
    Executes OpenSCAD for AST nodes that cannot be represented
    as FreeCAD BRep geometry (e.g. 2D hulls, Minkowski, CGAL-only cases).
    """

    node = fallback["node"]

    scad_code = ast_node_to_scad(node)

    write_log("AST", "Executing OpenSCAD fallback")
    write_log("AST", f"SCAD code:\n{scad_code}")

    with tempfile.TemporaryDirectory() as tmpdir:
        scad_file = os.path.join(tmpdir, "fallback.scad")
        stl_file = os.path.join(tmpdir, "fallback.stl")

        with open(scad_file, "w", encoding="utf-8") as f:
            f.write(scad_code)

        run_openscad(scad_file, stl_file)

        shape = import_stl(stl_file)

        if not isinstance(shape, Part.Shape):
            raise RuntimeError("OpenSCAD fallback did not produce a valid Shape")

        return shape

