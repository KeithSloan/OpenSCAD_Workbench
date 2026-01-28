# freecad/OpenSCAD_Ext/__init__.py

import FreeCAD

# ------------------------
#  Logging setup
# ------------------------
from .logger.Workbench_logger import init as init_logging, write_log

# Initialise logging once
init_logging()
write_log("INIT", "OpenSCAD_Ext module loaded — logging active")

# ------------------------
#  Importer registration
# ------------------------

def setup_importers():
    # If marker exists, stop — already registered.
    if getattr(FreeCAD, "_OpenSCAD_Ext_registered", False):
        FreeCAD.Console.PrintMessage("[OpenSCAD_Ext] Importers already registered\n")
        return

    IMPORTER_BASE = __name__ + ".importers"

    # ---- REGISTER IMPORT TYPES ----
    FreeCAD.addImportType(
        "External OpenSCAD Workbench : Legacy CSG importer (*.csg)",
        f"{IMPORTER_BASE}.importAltCSG"
    )

    FreeCAD.addImportType(
        "External OpenSCAD Workbench : NEW CSG / AST importer (*.csg)",
        f"{IMPORTER_BASE}.importASTCSG"
    )

    FreeCAD.addImportType(
        "External OpenSCAD Workbench : NEW CSG importer (*.csg)",
        f"{IMPORTER_BASE}.newImportCSG"
    )

    FreeCAD.addImportType(
        "External OpenSCAD Workbench : Create AST from CSG (*.csg)",
        f"{IMPORTER_BASE}.createASTfromCSG"
    )

    FreeCAD.addImportType(
        "External OpenSCAD Workbench : New (Alpha) import SCAD file (*.scad)",
        f"{IMPORTER_BASE}.importASTCSG"
    )


    FreeCAD.addImportType(
        "External OpenSCAD Workbench : Legacy import SCAD file (*.scad)",
        f"{IMPORTER_BASE}.importAltCSG"
    )


    FreeCAD.addImportType(
        "External OpenSCAD Workbench : import SCAD File Object (*.scad)",
        f"{IMPORTER_BASE}.importFileSCAD"
    )


    FreeCAD.addImportType(
        "DXF drawing (*.dxf)",
        f"{IMPORTER_BASE}.importDXF"
    )

    FreeCAD.Console.PrintMessage("[OpenSCAD_Ext] Importers registered.\n")

    # Mark as complete — **only NOW** set guard flag
    FreeCAD._OpenSCAD_Ext_registered = True

# ------------------------
#  Exporter registration
# ------------------------

def setup_exporters():
    # GUI-only
    if getattr(FreeCAD, "_OpenSCAD_Ext_exporters_registered", False):
        FreeCAD.Console.PrintMessage("[OpenSCAD_Ext] Exporters already registered\n")
        return

    EXPORTER_BASE = __name__ + ".exporters"

    FreeCAD.addExportType(
        "External OpenSCAD Workbench : OpenSCAD (*.scad)",
        f"{EXPORTER_BASE}.exportSCAD"
    )

    FreeCAD.addExportType(
        "External OpenSCAD Workbench : CSG (*.csg)",
        f"{EXPORTER_BASE}.exportALTCSG"
    )

    FreeCAD.Console.PrintMessage("[OpenSCAD_Ext] Exporters registered.\n")
    FreeCAD._OpenSCAD_Ext_exporters_registered = True

# ------------------------
#  Run registration
# ------------------------
setup_importers()
setup_exporters()