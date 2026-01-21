    def processVariables(self, obj):

        try:
            scad_file = obj.sourceFile
            write_log("EDIT", f"Parsing SCAD file: {scad_file}")

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

