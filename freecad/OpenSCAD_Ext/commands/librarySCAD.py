import FreeCAD
import FreeCADGui

# OpenSCAD library location - Environmental Variable  OPENSCADPATH

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.libraries.libView import OpenSCADLibraryBrowser
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams

class LibrarySCAD_Class(BaseParams):
    """Access OpenSCAD Library """
    def GetResources(self):
        return {
            'MenuText': 'OpenSCAD Library',
            'ToolTip': 'Create SCADFile Object from OpenSCAD Library',
            'Pixmap': ':/icons/editScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("OpenSCAD Library executed\n")
        write_log("Info", "OpenSCAD Library executed")
        #doc = FreeCAD.ActiveDocument
        #write_log("Info",doc.Label)
        #if not doc:
        #    return
        dialog = OpenSCADLibraryBrowser()
        dialog.exec_()


    def IsActive(self):
        return True


FreeCADGui.addCommand("LibrarySCAD_CMD", LibrarySCAD_Class())
