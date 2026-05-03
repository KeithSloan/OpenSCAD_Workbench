import os
import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive


def _unique_scad_name(source_dir, base="SCAD_Object"):
    """Return a name whose .scad file does not yet exist in source_dir."""
    name = base
    counter = 1
    while os.path.exists(os.path.join(source_dir, name + ".scad")):
        name = f"{base}_{counter}"
        counter += 1
    return name


class NewSCADFile_Class(BaseParams):
    "Create a new SCAD file Object "
    def GetResources(self):
        return {
            'MenuText': 'New SCAD File Object',
            'ToolTip': 'Create a new SCAD file Object',
            'Pixmap': 'newScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("New SCAD File Object executed\n")
        write_log("Info", "New SCAD File Object executed")

        # Pre-fill the dialog with a name that doesn't clash with an existing file
        source_dir = BaseParams.getScadSourcePath()
        default_name = _unique_scad_name(source_dir)
        write_log("Info", f"Default SCAD name: {default_name}")

        obj = create_scad_object_interactive(
            title="Create New SCAD Object",
            scadName=default_name,
            newFile=True,
        )

        obj.Proxy.editFunction(new_file=True)

    def IsActive(self):
        return True

    def getSourceDirectory(self):
        return self.scadSourcePath

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

