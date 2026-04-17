import os

import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_lark_parser import parse_scad_file
from freecad.OpenSCAD_Ext.core.exporters import export_variables


class VarsSCADFile_Class:
    """Extract SCAD variables and export them according to preferences."""

    def GetResources(self):
        return {
            'MenuText': 'Extract SCAD Variables',
            'ToolTip': 'Extract variables from SCAD file and export to VarSet / Spreadsheet',
            'Pixmap': 'varsSCAD.svg',
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        if not doc:
            FreeCAD.Console.PrintWarning("No active document\n")
            return

        sel = FreeCADGui.Selection.getSelection()
        if not sel:
            FreeCAD.Console.PrintWarning("No objects selected\n")
            return

        for obj in sel:
            if obj.TypeId != "Part::FeaturePython":
                write_log("INFO", f"{obj.Label} is not Part::FeaturePython, skipping")
                continue

            proxy = getattr(obj, "Proxy", None)
            if proxy is None or not isinstance(proxy, SCADfileBase):
                write_log("INFO", f"{obj.Label} proxy is not SCADfileBase, skipping")
                continue

            scad_file = getattr(obj, "sourceFile", None)
            if not scad_file or not os.path.isfile(scad_file):
                FreeCAD.Console.PrintWarning(
                    f"{obj.Label}: sourceFile not set or not found\n"
                )
                continue

            write_log("INFO", f"Extracting variables from {scad_file}")
            meta = parse_scad_file(scad_file)
            label = os.path.splitext(os.path.basename(scad_file))[0]

            export_variables(doc, meta, label)

            FreeCAD.Console.PrintMessage(
                f"SCAD variable export complete for {obj.Label} "
                f"({len(meta.variables)} variable(s))\n"
            )
            write_log("INFO", f"Variable export done for {obj.Label}")

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


FreeCADGui.addCommand("VarsSCADFileObject_CMD", VarsSCADFile_Class())
