import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.OpenSCADObjects import SCADBase

class EditSCADFileObject_Class:
    """Edit new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'Edit SCAD File Object',
            'ToolTip': 'Edit  a new SCAD file Object',
            'Pixmap': ':/icons/editScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Edit SCAD File Object executed\n")
        FreeCAD.Console.PrintError("Edit SCAD File Object executed\n")
        write_log("Info", "Edit SCAD File Object executed")

    def IsActive(self):
        return True

    def editFile(self, fname):
        import subprocess,  os, sys
        editorPathName = FreeCAD.ParamGet(\
            "User parameter:BaseApp/Preferences/Mod/OpenSCAD").GetString('externalEditor')
        write_log("Info", f"Path to external editor {editorPathName}")
        # ToDo : Check pathname valid
        if editorPathName != "":
            p1 = subprocess.Popen( \
                [editorPathName, fname], \
                stdin=subprocess.PIPE,\
                stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        else:
            FreeCAD.Console.PrintError(\
                f"External Editor preference editorPathName not set")


FreeCADGui.addCommand("EditSCADFileObject_CMD", EditSCADFileObject_Class())
