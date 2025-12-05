# freecad/OpenSCAD_Workbench/__init__.py
import FreeCAD

# setup_importers()

# --- Logging ---
from .logger.Workbench_logger import init as init_logging, write_log

# Initialize logger immediately when the module is imported
init_logging()
write_log("INIT", "OpenSCAD_Ext module loaded — logging active")

# Optional test print

# Setup importers
def setup_importers():
    IMPORTER_BASE = __name__ + ".importers"
    FreeCAD.addImportType(
        "External OpenSCAD Workbench : CSG importer (*.csg)",
        f"{IMPORTER_BASE}.importAltCSG"
    )
    FreeCAD.addImportType(
        "SCAD geometry (*.scad)",
        f"{IMPORTER_BASE}.importAltCSG"
    )
    FreeCAD.addImportType(
        "DXF drawing (*.dxf)",
        f"{IMPORTER_BASE}.importDXF"
    )
    FreeCAD.Console.PrintMessage("All importers registered.\n")

setup_importers()
