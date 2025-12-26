import FreeCAD
import FreeCADGui

# Fully-qualified imports
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_parser import parse_scadmeta
from freecad.OpenSCAD_Ext.core.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.parsers.varset_utils import add_scad_vars_to_varset, mirror_varset_to_spreadsheet

class VarsSCADFile_Class:
    """Extract and mirror SCAD variables to FreeCAD variable set"""
    
    def GetResources(self):
        return {
            'MenuText': 'Extract SCAD Variables',
            'ToolTip': 'Extract variables from SCAD file and mirror to spreadsheet',
            'Pixmap': ':/icons/varsSCAD.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Vars SCAD File Object executed\n")
        write_log("Info", "Vars SCAD File Object executed")
        
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
                write_log("Info", f"{obj.Label} is not a Part::FeaturePython, skipping")
                continue

            proxy = getattr(obj, "Proxy", None)
            if proxy is None or not isinstance(proxy, SCADfileBase):
                write_log("Info", f"{obj.Label} proxy is not SCADfileBase, skipping")
                continue

            try:
                scad_file = obj.sourceFile
                write_log("EDIT", f"Parsing SCAD file: {scad_file}")

                # Parse variables from SCAD meta
                meta = parse_scadmeta(obj.sourceFile)

                scad_vars = meta.variables

                add_scad_vars_to_varset(obj, scad_vars)
                mirror_varset_to_spreadsheet(doc, scad_vars)

                FreeCAD.Console.PrintMessage(f"SCAD variables extracted for {obj.Label}\n")
                write_log("Info", f"SCAD variables extracted for {obj.Label}")

            except Exception as e:
                FreeCAD.Console.PrintError(f"Failed to extract SCAD vars for {obj.Label}: {e}\n")
                write_log("Error", f"Failed to extract SCAD vars for {obj.Label}: {e}")

    def IsActive(self):
        return True


# Register the command
FreeCADGui.addCommand("VarsSCADFileObject_CMD", VarsSCADFile_Class())

