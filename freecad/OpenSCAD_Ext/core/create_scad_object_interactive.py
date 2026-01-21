# freecad/OpenSCAD_Ext/core/create_scad_object_interactive.py
"""
Safe, PySide2-only interactive SCAD object creator.
Avoids circular imports and PyQt5 fallback errors.
"""

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

#
# Direct values — if you pass them, they set initial values unless overridden by preset.
#
# # preset
#
# A dictionary of values ({"newFile": False, "sourceFile": filename, "geometryType":"Brep"})
# that the dialog will try to apply. This is meant for pre-configured sets, like a “library preset” or pre

def create_scad_object_interactive(
    title,
    *,
    newFile=True,
    scadName=None,
    sourceFile=None,
    preset=None,
    geometryType=None,
    fnMax=None,
    timeOut=None,
    keepOption=None,
):


    # GUI imports inside function to avoid early Qt5 fallback
    from PySide2 import QtWidgets
    from freecad.OpenSCAD_Ext.gui.OpenSCADeditOptions import OpenSCADeditOptions

    write_log("info", "LOADED create_scad_object_interactive v2")
    write_log("Info",f"Interactive - scadName {scadName} sourceFile {sourceFile} newFile {newFile}")

    #write_log("Dialog",f"newFile = {newFile} sourceFile = {sourceFile}")
    preset = {
        "newFile": newFile,             # New file flag
        "sourceFile": sourceFile,       # Full path to existing SCAD file
    }
    dlg = OpenSCADeditOptions(title,
                                newFile=newFile,
                                scadName=scadName,
                                sourceFile=sourceFile,
                                preset=preset
                                )
    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return None

    params = dlg.getValues()

    # Import core after dialog completes to avoid circular imports
    from freecad.OpenSCAD_Ext.core.create_scad_object import create_scad_object

    return create_scad_object(
        scadName=params["scadName"],
        geometryType=params["geometryType"],
        fnMax=params["fnMax"],
        timeOut=params["timeOut"],
        keepOption=params["keepOption"],
        newFile=params["newFile"],
        sourceFile=params["sourceFile"],
    )