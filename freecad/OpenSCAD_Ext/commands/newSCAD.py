import FreeCAD
import FreeCADGui

#from PySide import QtWidgets
#from PySide import QtGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive

class NewSCADFile_Class(BaseParams):
    "Create a new SCAD file Object "
    def GetResources(self):
        return {
            'MenuText': 'New SCAD File Object',
            'ToolTip': 'Create a new SCAD file Object',
            'Pixmap': ':/icons/newScadFileObj.svg'
        }

    def Activated(self):
        #import os
        FreeCAD.Console.PrintMessage("New SCAD File Object executed\n")
        write_log("Info", "New SCAD File Object executed")
        
        obj = create_scad_object_interactive(
            title="Create New SCAD Object",
            preset={
                "newFile": True,
                "scadName": "SCAD_Object",
            }
        )
        #obj.recompute()
        obj.Proxy.editFunction()

    def IsActive(self):
        return True

    def getSourceDirectory(self):
        return self.scadSourcePath

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

