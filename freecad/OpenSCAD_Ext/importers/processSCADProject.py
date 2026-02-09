import FreeCADGui
from PySide2 import QtWidgets, QtCore
import os
import json
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADProjectObject import SCADProjectObject
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider
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
    
    QtWidgets.QApplication.restoreOverrideCursor()
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.ArrowCursor)


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

    QtWidgets.QApplication.restoreOverrideCursor()
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.ArrowCursor)

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

    # populate enum FIRST
    project_fc_obj.DefaultImportMode = SCADfileBase.IMPORT_MODE

    # now set from dialog
    project_fc_obj.DefaultImportMode = dlg.geometryType.getVal()

    write_log(
        "ScadProject",
        f"Project default import mode: {project_fc_obj.DefaultImportMode}"
    )

    # -------------------------------------------------
    # Create SCADFileObjects (NON-interactive)
    # -------------------------------------------------
    created_objects = []

    write_log("project",f" : project path : {proj_filename}")
    project_directory = os.path.dirname(proj_filename) 

    for fentry in files:
        
        scad_path = fentry.get("path")
        write_log("Project",f"scad_path : {scad_path}")

        if not scad_path:
            write_log("ScadProject", "Skipping file entry without path")
            continue

        name = os.path.splitext(os.path.basename(scad_path))[0]
        sourceName = os.path.join(project_directory, scad_path)
        file_fc_obj = doc.addObject("Part::FeaturePython", name)
        ViewSCADProvider(file_fc_obj.ViewObject)

        file_proxy = SCADfileBase(
            file_fc_obj,
            scadName=name,
            sourceFile=sourceName,
            mode=project_fc_obj.DefaultImportMode # Project Default Mode
        )

        write_log(
            "ScadProject",
            f"Added SCAD file '{scad_path}' with mode={project_fc_obj.mode}"
        )

    doc.recompute()

    write_log(
        "ScadProject",
        f"Imported {len(created_objects)} SCAD files into project '{project_name}'"
    )

    return project_fc_obj
