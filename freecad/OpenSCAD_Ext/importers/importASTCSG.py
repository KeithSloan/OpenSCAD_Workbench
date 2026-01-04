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

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_SCAD_Object import process_AST
from freecad.OpenSCAD_Ext.parsers.csg_parser.parser import parse_csg_file

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
    groupname = os.path.splitext(os.path.basename(filename))[0]
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

    write_log("Info","Using OpenSCAD AST / CSG Importer")
    write_log("Info",f"Doc {doc.Name} useMaxFn {fnmax}")
    if printverbose: print ('ImportCSG Version 0.6a')
    ast_nodes = parse_csg_file(filename)
    shapes = process_AST(doc, ast_nodes)

    if printverbose: print ('ImportCSG Version 0.6a')
    
    FreeCAD.Console.PrintMessage('End processing CSG file\n')
    doc.recompute()

