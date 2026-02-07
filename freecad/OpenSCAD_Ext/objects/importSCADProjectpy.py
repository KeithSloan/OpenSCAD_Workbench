from freecad.OpenSCAD_Ext.importers.processSCADProject import processSCADProj
'''
SCADProject Importer Structure for FreeCAD
-----------------------------------------

1. SCADProject Object

Type: App::FeaturePython
Represents: a single .scadproj file in FreeCAD.
Properties:
  - Group → contains all SCADFileObjects corresponding to .scad files in the project.
Capabilities:
  - Knows how to open the entire project in OpenSCAD Studio.
  - Selection/editing of individual SCAD files in FreeCAD is disabled; editing is done only via OpenSCAD Studio.

2. SCADFileObject

Type: Part::FeaturePython
Represents: a single .scad file within the .scadproj.
Properties:
  - sourceFile → full path to the actual .scad file.
  - renderMode → Mesh or Brep (user can change mode individually).
Capabilities:
  - Can render itself in FreeCAD according to renderMode.
  - Editing is disabled inside FreeCAD.
  - Knows how to invoke rendering but does not control editing of the file.

3. Grouping & Behavior

- SCADProject.Group contains all SCADFileObjects.
- Selecting the SCADProject allows opening the project in OpenSCAD Studio.
- Render commands work per SCADFileObject, respecting its render mode.
- FreeCAD acts as a consumer/viewer of the geometry, not an editor.

Key Principles

- FreeCAD does not store files directly — the SCADFileObjects reference files from the .scadproj.
- Editing is centralized in OpenSCAD Studio.
- Mode can be set once during import for all files, but individual SCADFileObjects can change render mode.
'''
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
__title__="FreeCAD OpenSCAD Workbench - scadproj importer"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__ = ["http://www.sloan-home.co.uk/ImportCSG"]

import FreeCADGui
#from pathlib import Path

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

#
# For Process openscad_studio scadproj JSON  files 
import FreeCAD, os

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
DisplayName = "OpenSCAD Ext – scadproj importer"


def open(filename):
    "called when freecad opens a file."
    global doc
    global pathName
    FreeCAD.Console.PrintMessage('Processing : '+filename+'\n')
    docname = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument(docname)
    if filename.lower().endswith('.scadproj'):
        processSCADProj(doc, filename)
    return doc

def insert(filename, currentdoc):
    open(filename, currentdoc)
