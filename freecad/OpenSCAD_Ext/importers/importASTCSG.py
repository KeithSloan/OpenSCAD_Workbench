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

import FreeCADGui
from pathlib import Path

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.processAST import process_AST
from freecad.OpenSCAD_Ext.parsers.csg_parser.parse_csg_file_to_AST_nodes import parse_csg_file_to_AST_nodes
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


def open(filename):
    "called when freecad opens a file."
    global doc
    global pathName
    FreeCAD.Console.PrintMessage('Processing : '+filename+'\n')
    docname = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument(docname)
    if filename.lower().endswith('.scad'):
        from freecad.OpenSCAD_Ext.core.OpenSCADUtils import callopenscad, workaroundforissue128needed

        write_log("Info","Calling OpenSCAD")
        tmpfile=callopenscad(filename)
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
        from OpenSCADUtils import callopenscad, workaroundforissue128needed
        tmpfile=callopenscad(filename)
        if workaroundforissue128needed():
            pathName = '' #https://github.com/openscad/openscad/issues/128
            #pathName = os.getcwd() #https://github.com/openscad/openscad/issues/128
        else:
            pathName = os.path.dirname(os.path.normpath(filename))
        write_log("Info,",f"Processing : {filename}")
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
    write_log("Info","Using OpenSCAD AST / CSG Importer")
    write_log("Info",f"Doc {doc.Name} useMaxFn {fnmax}")
    if printverbose: 
        print ('ImportCSG Version 0.6a')
    raw_ast_nodes = parse_csg_file_to_AST_nodes(filename)
    ast_nodes = raw_ast_nodes
    #ast_nodes = normalize_ast(raw_ast_nodes)
    shapePlaceList = process_AST(ast_nodes, mode="multiple")
    write_log("AST",f"shapePlaceList {shapePlaceList}")
    for sp in shapePlaceList:
        write_log("Import",f"{sp}")
        obj=add_shape_to_doc(doc,sp[1],sp[2],sp[0])
        obj.recompute()

    #add_shapes_to_document(doc, name, shapes)
    FreeCADGui.SendMsgToActiveView("ViewFit")
    if printverbose:
        print ('ImportCSG Version 0.6a')
    FreeCAD.Console.PrintMessage('End processing CSG file\n')
    doc.recompute()

