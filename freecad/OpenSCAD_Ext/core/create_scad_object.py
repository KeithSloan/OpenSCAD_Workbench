import os
from pathlib import Path
import FreeCAD

from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
#from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider


def create_scad_object(
    scadName,
    sourceFile,
    geometryType,
    fnMax,
    timeOut,
    keepOption,
    *,
    newFile=True,
    doc=None
):

    #write_log("Info",f"scadName = {scadName} sourceFile = {sourceFile} newFile = {newFile}")
    """
    Create a SCAD FeaturePython object.

    This function is GUI-independent and safe to call from:
    - Qt dialogs
    - macros
    - Python console
    - batch imports
    """

    write_log(
        "Info",
        f"create_scad_object - newFile = {newFile} sourceFile = {sourceFile} newFile = {newFile}"
    )

    if newFile:
        sourceFile = os.path.join(
            BaseParams.getScadSourcePath(),
            scadName,
        )
        write_log("Info", f"New source file: {sourceFile}")

    if doc is None:
        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument(scadName)
            write_log("Info", f"Created new document: {doc.Name}")

    doc.openTransaction("Create SCAD Object")

    obj = doc.addObject("Part::FeaturePython", scadName)
    write_log("Info", f"Created SCAD object: {obj.Name}")

    SCADfileBase(
        obj,
        obj.Name,          # IMPORTANT: use actual object name
        sourceFile,
        geometryType,
        fnMax,
        timeOut,
        keepOption
    )

    ViewSCADProvider(obj.ViewObject)

    doc.recompute()
    doc.commitTransaction()

    return obj
