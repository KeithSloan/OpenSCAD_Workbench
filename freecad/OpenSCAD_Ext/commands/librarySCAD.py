import FreeCAD
import FreeCADGui

# OpenSCAD library location - Environmental Variable  OPENSCADPATH

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.gui.OpenSCADLibraryBrowser \
     import OpenSCADLibraryBrowser
#from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.libraries.scan_scad_library import scan_scad_library
#from freecad.OpenSCAD_Ext.parses.parse_scad_for_modules import scan_for_modules

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

        # Scan library or wait for gui to scan??
        libPath = ensure_openSCADPATH()
        scan_scad_library(libPath)

        #
        browser = OpenSCADLibraryBrowser()
        browser.exec_()


    def IsActive(self):
        return True


FreeCADGui.addCommand("LibrarySCAD_CMD", LibrarySCAD_Class())
