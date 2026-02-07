import json
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.ScadFileBase import create_scad_object_interactive

def importSCADProject(doc, proj_filename):
    """
    Import a SCAD project file (.scadproj) and create a Project object
    containing all SCADFileObjects in a group.
    """
    write_log("ScadProject", f"Importing SCAD project: {proj_filename}")

    # --- Load JSON project ---
    try:
        with open(proj_filename, "r") as f:
            proj_data = json.load(f)
    except Exception as e:
        write_log("ScadProject", f"ERROR reading project file: {e}")
        return None

    files = proj_data.get("files", [])
    if not files:
        write_log("ScadProject", "No SCAD files found in project.")
        return None

    write_log("ScadProject", f"Found {len(files)} SCAD files in project.")

    # --- Create the Project object (group) ---
    project_name = proj_data.get("name", "SCADProject")
    project_obj = doc.addObject("App::DocumentObjectGroup", project_name)

    # --- Create SCADFileObjects and add to the Project group ---
    created_objects = []
    for fentry in files:
        scad_path = fentry.get("path")
        if not scad_path:
            write_log("ScadProject", "Skipping file entry without path")
            continue

        try:
            scad_obj = create_scad_object_interactive(
                title="Import OpenSCAD File Objects",
                newFile=False,
                sourceFile=scad_path
            )
            if scad_obj:
                project_obj.addObject(scad_obj)
                created_objects.append(scad_obj)
        except Exception as e:
            write_log("ScadProject", f"ERROR creating SCAD object for {scad_path}: {e}")

    write_log("ScadProject", f"Imported {len(created_objects)} SCAD objects into project '{project_name}'.")
    doc.recompute()
    return project_obj
