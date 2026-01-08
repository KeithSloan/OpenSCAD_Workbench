import FreeCAD
import FreeCADGui

# Fully-qualified imports
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_parser import varsSCAD
from freecad.OpenSCAD_Ext.parsers.parse_scad_for_modules import parse_scad_for_modules
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_parser import parse_scad_meta

from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_parse_scad_file import create_scad_vars_spreadsheet

from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
#from freecad.OpenSCAD_Ext.parsers.varset_utils import add_scad_vars_to_varset, mirror_varset_to_spreadsheet

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
               write_log("INFO", f"{obj.Label} is not a Part::FeaturePython, skipping")
               continue

            proxy = getattr(obj, "Proxy", None)
            if proxy is None or not isinstance(proxy, SCADfileBase):
                write_log("INFO", f"{obj.Label} proxy is not SCADfileBase, skipping")
                continue

            # Use the new varsSCAD function
            #arsSCAD(obj)
            self.processVariables(obj)
            doc.recompute()

            FreeCAD.Console.PrintMessage(f"SCAD variables extracted for {obj.Label}\n")
            write_log("INFO", f"SCAD variables extracted for {obj.Label}")


    """
    Extract SCAD variables from the given object and create a spreadsheet
    for each module in the SCAD file.
    """
    def processVariables(self, obj):

        try:
            scad_file = obj.sourceFile
            write_log("INFO", f"Process variables from SCAD file: {scad_file}")

            # Parse variables from SCAD meta (returns dict keyed by module name)
            meta = parse_scad_meta(scad_file)

            if not meta:
               write_log("WARN", f"No modules or variables found in {scad_file}")
               return

            # Iterate over modules
            for mod_name, mod_data in meta.items():
                vars_list = mod_data.get("vars", [])
                sets_list = mod_data.get("sets", [])

                write_log(
                    "SCADMETA",
                    f"Module '{mod_name}' Vars: {vars_list}, Sets: {sets_list}"
                )

                # Build spreadsheet name
                sheet_name = f"Vars_{mod_name}"

                # Create spreadsheet for this module
                create_scad_vars_spreadsheet(FreeCAD.ActiveDocument, mod_data, sheet_name)
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to extract SCAD vars for {obj.Label}: {e}\n")
            write_log("Error", f"Failed to extract SCAD vars for {obj.Label}: {e}")


    def IsActive(self):
        return True


# Register the command
FreeCADGui.addCommand("VarsSCADFileObject_CMD", VarsSCADFile_Class())

