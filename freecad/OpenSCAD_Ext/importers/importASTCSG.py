# importASTCSG.py
# -*- coding: utf8 -*-
#***************************************************************************
#* FreeCAD OpenSCAD Workbench - AST / CSG importer using ast_evaluator      *
#***************************************************************************

__title__="FreeCAD OpenSCAD Workbench - AST / CSG importer"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"

import FreeCAD, Part, os
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.parsers.csg_parser.parser import parse_csg_file

from freecad.OpenSCAD_Ext.parsers.csg_parser.parse_csg_to_ast import parse_csg_file_to_ast
# Import new AST evaluator
#from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_evaluator import evaluate_ast
from freecad.OpenSCAD_Ext.parsers.ast_evaluator import evaluate_ast

# -------------------------
# Check if GUI present
# -------------------------
gui = FreeCAD.GuiUp
if gui:
    import FreeCADGui

# -------------------------
# Display Name
# -------------------------
DisplayName = "OpenSCAD Ext – CSG / AST Importer"

# -------------------------
# Preferences / verbose
# -------------------------
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
printverbose = params.GetBool('printverbose', False)
printverbose = True  # force for now

# -------------------------
# File open / import entry points
# -------------------------
def open(filename):
    """Called when FreeCAD opens a file."""
    docname = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument(docname)
    process_file(doc, filename)
    return doc

def insert(filename, docname):
    """Called when FreeCAD imports a file into existing document."""
    try:
        doc = FreeCAD.getDocument(docname)
    except Exception:
        doc = FreeCAD.newDocument(docname)
    process_file(doc, filename)
    return doc

# -------------------------
# Core processing
# -------------------------
def process_file(doc, filename, fnmax_param=None):
    """Parse CSG/SCAD file and convert AST to FreeCAD shapes."""
    global fnmax
    if fnmax_param is None:
        fnmax = params.GetInt('useMaxFN', 16)
    else:
        fnmax = fnmax_param

    write_log("Info", f"Using OpenSCAD AST / CSG Importer")
    write_log("Info", f"Doc {doc.Name} useMaxFn {fnmax}")
    FreeCAD.Console.PrintMessage(f'Processing: {filename}\n')

    # If SCAD file, call OpenSCAD to generate CSG
    if filename.lower().endswith(".scad"):
        from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscad, workaroundforissue128needed
        tmpfile = callopenscad(filename)
        if workaroundforissue128needed():
            pathName = ''
        else:
            pathName = os.path.dirname(os.path.normpath(filename))
        csg_file = tmpfile
    else:
        pathName = os.path.dirname(os.path.normpath(filename))
        csg_file = filename

    # Parse AST
    ast_nodes = parse_csg_file_to_ast(csg_file)

    # Convert AST to FreeCAD shapes using ast_evaluator
    shapes = []
    for node in ast_nodes:
        shape = evaluate_ast(node)
        if shape:
            obj = doc.addObject("Part::Feature", f"{node.name}_{node.__class__.__name__}")
            obj.Shape = shape
            shapes.append(obj)

    FreeCAD.Console.PrintMessage(f'Imported {len(shapes)} top-level shapes from {filename}\n')
    doc.recompute()

    # Cleanup temporary SCAD-to-CSG file
    if filename.lower().endswith(".scad"):
        try:
            os.unlink(tmpfile)
        except OSError:
            pass

