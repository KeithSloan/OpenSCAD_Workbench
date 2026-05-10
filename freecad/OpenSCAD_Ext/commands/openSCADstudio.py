import FreeCAD
import FreeCADGui
import sys
import subprocess

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.core.create_scad_object_interactive import create_scad_object_interactive
from freecad.OpenSCAD_Ext.commands.editSCAD import resolve_scad_object


class EditStudioSCADFile_Class(BaseParams):
    """Open SCAD file in OpenSCAD Studio"""
    def GetResources(self):
        return {
            'MenuText': 'OpenSCAD Studio - SCAD File Object',
            'ToolTip': 'Open SCAD File Object in OpenSCAD Studio',
            'Pixmap': 'editStudioScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("OpenSCAD Studio - Edit SCAD File Object executed\n")
        write_log("Info", "Studio - Edit SCAD File Object executed")

        doc = FreeCAD.ActiveDocument
        if not doc:
            write_log("Info", "No Active Document")
            doc = FreeCAD.newDocument("OpenSCAD_Studio")
        write_log("Info", doc.Label)

        sel = FreeCADGui.Selection.getSelection()
        write_log("Info", f"selection {sel}")

        if not sel:
            # No selection — create a new SCAD object
            obj = create_scad_object_interactive(
                title="Create New OpenSCAD Studio Object",
                scadName="OpenSCAD_Studio",
                newFile=True,
            )
            if obj is not None:
                obj.Proxy.editOpenStudio()
        else:
            for obj in sel:
                scad_obj = resolve_scad_object(obj)
                if scad_obj is None:
                    write_log("INFO", f"Selected object '{obj.Label}' is not a SCAD object")
                    continue
                try:
                    scad_obj.Proxy.editOpenStudio()
                except Exception as e:
                    FreeCAD.Console.PrintError(
                        f"Failed to open OpenSCAD Studio for {scad_obj.Label}: {e}\n"
                    )

    def IsActive(self):
        return True


FreeCADGui.addCommand("EditStudioSCADFileObject_CMD", EditStudioSCADFile_Class())
