#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2023 Keith Sloan <keith@sloan-home.co.uk>               *
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
#***************************************************************************
__title__="FreeCAD OpenSCAD Workbench - CSG importer SCAD Object"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__ = ["http://www.sloan-home.co.uk/ImportSCAD"]

import FreeCAD, FreeCADGui, os
if FreeCAD.GuiUp:
    import FreeCADGui
    gui = True
else:
    print("FreeCAD Gui not present.")
    gui = False

# Save the native open function to avoid collisions
if open.__module__ in ['__builtin__', 'io']:
    pythonopen = open

from PySide import QtGui, QtCore

#import importCSG
#from freecad.OpenSCAD_Ext.objects.OpenSCADObjects import \
#       SCADfileBase, \
#       ViewSCADProvider

from freecad.OpenSCAD_Ext.importers.importAltCSG import processCSG
from freecad.OpenSCAD_Ext.objects.SCADObject import createSCADObject

params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
printverbose = params.GetBool('printverbose',False)
print(f'Verbose = {printverbose}')


def open(filename):
	import os
	"called when freecad opens a file."
	pathText = os.path.splitext(os.path.basename(filename))
	objectName  = pathText[0]
	filePath = pathText[1]
	FreeCAD.Console.PrintMessage('Creating SCAD File Object from : '+filename+'\n')
	doc=FreeCAD.newDocument(objectName)
	insert(filename,objectName)


def insert(filename, docName):
	"called when freecad inserts a file."
	doc = FreeCAD.getDocument(docName)
	objectName  = os.path.splitext(os.path.basename(filename))[0]
	obj = createSCADObject("FC OpenSCAD import Options",
		False,
		objectName,
		filename,
		)
	#FreeCAD.ActiveDocument.recompute()
	#obj.recompute()
	doc.recompute()
	FreeCADGui.SendMsgToActiveView("ViewFit")
	#view.sendMessage("ViewFit")
