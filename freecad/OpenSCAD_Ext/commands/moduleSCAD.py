import FreeCAD
import FreeCADGui

# OpenSCAD library location - Environmental Variable  OPENSCADPATH

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.gui.SCAD_Module_Dialog import SCAD_Module_Dialog
from freecad.OpenSCAD_Ext.core.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams

class ModuleSCAD_Class(BaseParams):
    """Scan SCAD file for Modules - create SCADModuleObject """
    def GetResources(self):
        return {
            'MenuText': 'Scan/Select/Create SCAD Module Object',
            'ToolTip': 'Scan SCAD file, select Module to create a SCAD ModuleCreate SCADFile Object from OpenSCAD Library',
            'Pixmap': ':/icons/moduleCreateObj.svg'
        }

    def Activated(self, args=None):

        msg = "ModuleSCAD - Scan/Select/Create executed"	
        FreeCAD.Console.PrintMessage(msg + "\n")
        write_log("Info", msg)
        #doc = FreeCAD.ActiveDocument
        #write_log("Info",doc.Label)
        #if not doc:
        #    return
        scad_library = None

        if isinstance(args, dict):
           scad_library = args.get("scad_library")

        if not scad_library:
           FreeCAD.Console.PrintError(
              "No SCAD library file supplied to ModuleSCAD_CMD\n"
           )
           return

        dialog = SCAD_Module_Dialog(scad_library)
        dialog.exec_()


    def IsActive(self):
        return True


FreeCADGui.addCommand("ModuleSCAD_CMD", ModuleSCAD_Class())
