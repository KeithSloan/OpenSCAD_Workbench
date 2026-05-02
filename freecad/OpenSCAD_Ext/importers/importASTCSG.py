# -*- coding: utf8 -*-
#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2012 Keith Sloan <keith@sloan-home.co.uk>               *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         * 
#*   Acknowledgements :                                                    *
#*                                                                         *
#*     Thanks to shoogen on the FreeCAD forum and Peter Li                 *
#*     for programming advice and some code.                               *
#*                                                                         *
#*                                                                         *
#***************************************************************************
__title__="FreeCAD OpenSCAD Workbench - AST / CSG importer"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__ = ["http://www.sloan-home.co.uk/ImportCSG"]
__version__ = "0.8.3"

import FreeCADGui
from pathlib import Path

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import process_AST
from freecad.OpenSCAD_Ext.parsers.csg_parser.parse_csg_to_AST import parse_csg_file_to_AST_nodes
#from freecad.OpenSCAD_Ext.parsers.csg_parser.parse_csg_file_to_AST_nodes import normalize_ast

#
# For SCAD files first process via OpenSCAD to creae CSG file then import
#
import FreeCAD, Part, Draft, io, os, sys, xml.sax
if FreeCAD.GuiUp:
    import FreeCADGui
    gui = True
else:
    print("FreeCAD Gui not present.")
    gui = False

# Save the native open function to avoid collisions
if open.__module__ in ['__builtin__', 'io']:
    pythonopen = open

# In theory FC 1.1+ should use ths for display import prompt
DisplayName = "OpenSCAD Ext – CSG / AST Importer"

params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
printverbose = params.GetBool('printverbose',False)
print(f'Verbose = {printverbose}')
#print(params.GetContents())
printverbose = True

try:
    from PySide import QtGui
    _encoding = QtGui.QApplication.UnicodeUTF8
    def translate(context, text):
        "convenience function for Qt translator"
        from PySide import QtGui
        return QtGui.QApplication.translate(context, text, None, _encoding)
except AttributeError:
    def translate(context, text):
        "convenience function for Qt translator"
        from PySide import QtGui
        return QtGui.QApplication.translate(context, text, None)


def _customizer_intercept(filename, doc):
    """
    Scan a .scad file for customizer variables.  If found, ask the user
    whether to import as a live parametric object or as static geometry.

    Returns True  — caller should return immediately (parametric path taken
                    or user cancelled).
    Returns False — caller should continue with the normal CSG import.
    """
    from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, ScadFileType
    meta = scan_scad_file(filename)

    if meta.file_type != ScadFileType.CUSTOMIZER:
        return False  # not a customizer file — nothing to intercept

    write_log("Info", f"Customizer file detected: {filename} ({len(meta.variables)} variable(s))")

    from freecad.OpenSCAD_Ext.gui.customizer_import_dialog import ask_customizer_import_mode
    choice = ask_customizer_import_mode(filename, meta)

    if choice is None:
        write_log("Info", "Customizer import cancelled by user")
        return True  # cancelled — stop, do nothing

    if choice == "static":
        write_log("Info", "User chose static geometry import")
        return False  # fall through to normal CSG path

    # choice == "parametric"
    write_log("Info", "User chose parametric import — delegating to SCADfileBase path")
    from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive
    obj = create_scad_object_interactive(
        title="Import OpenSCAD Customizer File",
        newFile=False,
        sourceFile=filename,
    )
    if obj is not None:
        from freecad.OpenSCAD_Ext.core.attach_varset import attach_customizer_varset
        attach_customizer_varset(obj, filename, meta=meta)
        obj.Proxy.executeFunction(obj)

        # For Mesh mode: collapse the FeaturePython+companion pair into a
        # single Mesh::Feature so only one object appears in the model tree.
        if getattr(obj, 'mode', '') == "Mesh":
            from freecad.OpenSCAD_Ext.core.scad_mesh_utils import finalize_scad_mesh_object
            obj = finalize_scad_mesh_object(obj)

        # Do NOT call doc.recompute() here.  The shape is already set by
        # executeFunction().  An explicit recompute would trigger execute()
        # again (because linked_varset is not None) causing a second OpenSCAD
        # run and the FreeCAD 1.1.x busy-cursor hang.
    return True  # handled


def open(filename):
    "called when freecad opens a file."
    global doc
    global pathName
    FreeCAD.Console.PrintMessage('Processing : '+filename+'\n')
    docname = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument(docname)
    if filename.lower().endswith('.scad'):
        from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscad_with_overrides, workaroundforissue128needed

        # Check for customizer variables and offer parametric import
        if _customizer_intercept(filename, doc):
            return doc

        write_log("Info","Calling OpenSCAD")
        tmpfile=callopenscad_with_overrides(filename)
        if workaroundforissue128needed():
            pathName = '' #https://github.com/openscad/openscad/issues/128
            #pathName = os.getcwd() #https://github.com/openscad/openscad/issues/128
        else:
            pathName = os.path.dirname(os.path.normpath(filename))
        processCSG(doc, tmpfile)
        try:
            os.unlink(tmpfile)
        except OSError:
            pass
    else:
        pathName = os.path.dirname(os.path.normpath(filename))
        processCSG(doc, filename)
    return doc

def insert(filename,docname):
    "called when freecad imports a file"
    global doc
    global pathName
    try:
        doc=FreeCAD.getDocument(docname)
    except NameError:
        doc=FreeCAD.newDocument(docname)
    #importgroup = doc.addObject("App::DocumentObjectGroup",groupname)
    if filename.lower().endswith('.scad'):
        from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscad_with_overrides, workaroundforissue128needed

        # Check for customizer variables and offer parametric import
        if _customizer_intercept(filename, doc):
            return

        tmpfile=callopenscad_with_overrides(filename)
        if workaroundforissue128needed():
            pathName = '' #https://github.com/openscad/openscad/issues/128
            #pathName = os.getcwd() #https://github.com/openscad/openscad/issues/128
        else:
            pathName = os.path.dirname(os.path.normpath(filename))
        write_log("Info",f"Processing : {filename}")
        processCSG(doc, tmpfile)
        try:
            os.unlink(tmpfile)
        except OSError:
            pass
    else:
        pathName = os.path.dirname(os.path.normpath(filename))
        processCSG(doc, filename)

'''
def add_shapes_to_document(doc, name, shapes):
    """
    Add one or more Part.Shape objects to the FreeCAD document.
    Creates a Part::Feature with either a single Shape or a Compound.

    Args:
        doc   : FreeCAD document
        name  : Base object name
        shapes: Part.Shape or list[Part.Shape]

    Returns:
        App.DocumentObject or None
    """
    write_log("Import",f"Shapes to Doc {shapes}")
    if not shapes:
        return None

    # Normalize to list
    if not isinstance(shapes, (list, tuple)):
        shapes = [shapes]

    # Filter invalid shapes
    valid = [s for s in shapes if s and not s.isNull()]

    if not valid:
        return None

    # Single shape → direct
    if len(valid) == 1:
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = valid[0]
        obj.recompute()
        return obj

    # Multiple shapes → compound
    compound = Part.makeCompound(valid)
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = compound
    obj.recompute()
    return obj
'''

import FreeCAD as App
import Part

def add_shape_to_doc(doc, shape, placement, name="Part"):
    write_log("Add Object",f"Name {name} Shape {shape} Placement{placement}")

    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.Placement = placement
    return obj

def processCSG(docSrc, filename, fnmax_param = None):
    global doc
    global fnmax
    if fnmax_param is None:
        fnmax = FreeCAD.ParamGet(\
        "User parameter:BaseApp/Preferences/Mod/OpenSCAD").\
        GetInt('useMaxFN', 16)
    else:
        fnmax = fnmax_param
    doc = docSrc

    name = Path(filename).stem
    FreeCAD.Console.PrintMessage(f'ImportAstCSG Version {__version__}\n')
    write_log("Info","Using OpenSCAD AST / CSG Importer")
    write_log("Info",f"Doc {doc.Name} useMaxFn {fnmax}")
    raw_ast_nodes = parse_csg_file_to_AST_nodes(filename)
    ast_nodes = raw_ast_nodes
    #ast_nodes = normalize_ast(raw_ast_nodes)
    shapePlaceList = process_AST(ast_nodes, mode="multiple")
    write_log("AST",f"shapePlaceList {shapePlaceList}")
    for sp in shapePlaceList:
        write_log("Import",f"{sp}")
        obj=add_shape_to_doc(doc,sp[1],sp[2],sp[0])
        # obj.recompute() per-object is redundant — setting obj.Shape already
        # marks it for display; calling it here just adds an extra tessellation
        # pass per shape before doc.recompute() runs at the end.

    #add_shapes_to_document(doc, name, shapes)
    FreeCAD.Console.PrintMessage(f'ImportAstCSG Version {__version__}\n')
    FreeCAD.Console.PrintMessage('End processing CSG file\n')
    doc.recompute()
    # ViewFit deferred — calling it synchronously here hangs in FreeCAD 1.1.x
    # because the shape tessellation hasn't completed yet.
    from PySide.QtCore import QTimer
    QTimer.singleShot(500, lambda: FreeCADGui.SendMsgToActiveView("ViewFit"))

