import FreeCAD
# Fully-qualified imports
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.parsers.parse_scad_for_ModVarsInfo import parse_scad_meta
#from freecad.OpenSCAD_Ext.core.createSpreadSheet import create_scad_vars_spreadsheet


# only want to create if a valid scan of meta
# So parent should check and create doc
def extractVariables(doc, meta):

    write_log("Info",meta)

    try:
        #scad_file = obj.sourceFile
        #write_log("EDIT", f"Parsing SCAD file: {scad_file}")
        #write_log("EDIT", f"Parsing SCAD file: {scadFileName}")

        # Parse variables from SCAD meta (returns dict keyed by module name)
        #meta = parse_scad_meta(scad_file)
        #meta = parse_scad_meta(scadFileName)

        #if not meta:
        #    write_log("WARN", f"No modules or variables found in {scadFileName}")
        #    return

        # Iterate over modules
        for mod_name, mod_data in meta.items():
            vars_list = mod_data.get("vars", [])
            sets_list = mod_data.get("sets", [])

            write_log(
                "SCADMETA",
                f"Module '{mod_name}' Vars: {vars_list}, Sets: {sets_list}"
                )

            # Build spreadsheet name
            #sheet_name = f"Vars_{mod_name}"
            #varsSCAD()
            doc = FreeCAD.ActiveDocument
            if not doc:
                doc = FreeCAD.newDocument(mod_name)
            #obj = FreeCAD.O        

            # Create spreadsheet for this module
            #create_scad_vars_spreadsheet(doc, mod_data, sheet_name)

        
    except Exception as e:
        scadFileName = "Dummy"
        FreeCAD.Console.PrintError(f"Failed to extract SCAD vars from {scadFileName}: {e}\n")
        write_log("Error", f"Failed to extract SCAD vars for {scadFileName}: {e}")