# freecad/OpenSCAD_ext/__init__.py
import FreeCAD

# Called by FreeCAD when workbench is loaded
# FreeCAD.Console.PrintMessage("Loading OpenSCAD_Ext backend…\n")

# --------- Register Files ----------
#import importlib

# -------- Preferences Page (GUI only) -------
#if FreeCAD.GuiUp:
#    import FreeCADGui
#    FreeCADGui.addPreferencePage("freecad/MyWB/resources/ui/Preferences.ui",
#                                 "My Workbench")

import FreeCAD

def setup_importers():
    IMPORTER_BASE = __name__ + ".importers"

    FreeCAD.addImportType("CSG geometry (*.csg)", f"{IMPORTER_BASE}.importAltCSG")
    FreeCAD.addImportType("SCAD geometry (*.scad)", f"{IMPORTER_BASE}.importAltCSG")
    #FreeCAD.addImportType("OpenSCAD (*.scad)",     f"{IMPORTER_BASE}.importSCAD")
    FreeCAD.addImportType("DXF drawing (*.dxf)",   f"{IMPORTER_BASE}.importDXF")
    FreeCAD.Console.PrintMessage("All importers registered.\n")

setup_importers()
# Worbench diffinition __init__py or init_gui
# init_gui more logical
