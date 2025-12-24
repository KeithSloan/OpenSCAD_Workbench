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
        "External OpenSCAD Workbench : CSG importer (*.csg)",
        f"{IMPORTER_BASE}.importAltCSG"
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
        "External OpenSCAD Workbench : import SCAD file (*.scad)",
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


# Run registration immediately on module import
setup_importers()

