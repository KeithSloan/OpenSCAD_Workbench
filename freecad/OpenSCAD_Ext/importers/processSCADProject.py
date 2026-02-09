import FreeCADGui
import os
import json
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADProjectObject import SCADProjectObject, SCADfileBase
from freecad.OpenSCAD_Ext.gui.OpenSCADeditOptions import OpenSCADeditOptions


def importSCADProject(doc, proj_filename):
    """
    Import a SCAD project file (.scadproj) and create a SCADProjectObject
    containing SCADFileObjects as a group.
    """
    write_log("ScadProject", f"Importing SCAD project: {proj_filename}")

    # --- Load project file ---
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

    project_name = proj_data.get("name", "SCADProject")

    # -------------------------------------------------
    # Create Project object (with ONE interactive prompt)
    # -------------------------------------------------

    project_fc_obj = doc.addObject("App::FeaturePython", project_name)
    project_fc_obj.addExtension("App::GroupExtensionPython")

    #project_proxy = SCADProjectObject(
    #    project_fc_obj,
    #    name=project_name,
    #    sourceFile=proj_filename,
    #    meta=None,
    #    module=None,
    #    args=None,
    #)

    # -------------------------------------------------
    # ONE interactive dialog for project defaults
    # -------------------------------------------------
    
    dlg = OpenSCADeditOptions(
        title=project_fc_obj.Label,  
        scadName="Project",
        sourceFile=proj_filename,
        parent=FreeCADGui.getMainWindow()
        )

    if not dlg.exec_():
        # User cancelled → abort import cleanly
        doc.removeObject(project_fc_obj.Name)
        return None


    #project_fc_obj = doc.addObject("App::DocumentObjectGroup", project_name)

    project_proxy = SCADProjectObject(
        project_fc_obj,
        name=project_name,
        sourceFile=proj_filename,
        meta=None,
        module=None,
        args=None,
    )

    # (this sets DefaultImportMode on the project object)
    project_fc_obj.addProperty(
        "App::PropertyEnumeration",
        "DefaultImportMode",
        "Base",
        "Default import mode for SCAD files"
    )
    project_fc_obj.DefaultImportMode = SCADfileBase.IMPORT_MODE
    project_fc_obj.DefaultImportMode = proj_data.get(
        "default_import_mode", "AST-Brep"
    )

    write_log(
        "ScadProject",
        f"Project default import mode: {project_fc_obj.DefaultImportMode}"
    )


    # -------------------------------------------------
    # Create SCADFileObjects (NON-interactive)
    # -------------------------------------------------
    created_objects = []

    for fentry in files:
        scad_path = fentry.get("path")
        if not scad_path:
            write_log("ScadProject", "Skipping file entry without path")
            continue

        name = os.path.splitext(os.path.basename(scad_path))[0]
        file_fc_obj = doc.addObject("Part::FeaturePython", name)

        file_proxy = SCADfileBase(
            file_fc_obj,
            scadName=name,           # <-- REQUIRED
            sourceFile=scad_path,    # <-- REQUIRED
            mode=project_fc_obj.DefaultImportMode  # optional, default is "Mesh"
        )

        # Apply project default ONCE
        file_fc_obj.mode = project_fc_obj.DefaultImportMode
        project_fc_obj.addObject(file_fc_obj)

        write_log(
            "ScadProject",
            f"Added SCAD file '{scad_path}' with ImportMode={file_fc_obj.mode}"
        )

    doc.recompute()

    write_log(
        "ScadProject",
        f"Imported {len(created_objects)} SCAD files into project '{project_name}'"
    )

    return project_fc_obj
