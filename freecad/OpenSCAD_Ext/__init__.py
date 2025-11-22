# freecad/OpenSCAD_ext/__init__.py
import FreeCAD
import FreeCADGui

# Called by FreeCAD when workbench is loaded
# FreeCAD.Console.PrintMessage("Loading OpenSCAD_Ext backend…\n")

# --------- Register Files ----------
#import importlib

#def register_importers():
#    # Import your importer modules
#    importlib.import_module("freecad.OpenSCAD_Ext.importALtCSG")
#    importlib.import_module("freecad.MyWB.import.importer_scad")
#    importlib.import_module("freecad.MyWB.import.importer_dxf")

#    # Register file types
#    from freecad.MyWB.import.importer_csg import importCSG
#    from freecad.MyWB.import.importer_scad import importSCAD
#    from freecad.MyWB.import.importer_dxf import importDXF

#    FreeCAD.addImportType("CSG File (*.csg)", importCSG)
#    FreeCAD.addImportType("OpenSCAD File (*.scad)", importSCAD)
#    FreeCAD.addImportType("DXF File (*.dxf)", importDXF)

#register_importers()

# -------- Preferences Page (GUI only) -------
#if FreeCAD.GuiUp:
#    import FreeCADGui
#    FreeCADGui.addPreferencePage("freecad/MyWB/resources/ui/Preferences.ui",
#                                 "My Workbench")

import FreeCAD
#import freecad.OpenSCAD_Ext.importers
#from freecad.OpenSCAD_Ext.importers import importAltCSG
#from freecad.OpenSCAD_Ext.importers import OpenSCADHull

def setup_importers():
    IMPORTER_BASE = __name__ + ".importers"

    FreeCAD.addImportType("CSG geometry (*.csg)", f"{IMPORTER_BASE}.importAltCSG")
    FreeCAD.addImportType("OpenSCAD (*.scad)",     f"{IMPORTER_BASE}.importSCAD")
    FreeCAD.addImportType("DXF drawing (*.dxf)",   f"{IMPORTER_BASE}.importDXF")
    FreeCAD.Console.PrintMessage("All importers registered.\n")

setup_importers()

'''
FreeCAD.addImportType("Import : CSG (*.csg)","importAltCSG")
FreeCAD.addImportType("Import : SCAD (*.scad)","importAltCSG")
FreeCAD.addImportType("Import : ScadFileObject (*.scad)","importFileSCAD")
FreeCAD.addImportType("Import : DXF via EzDXF (*.dxf)","importAltDXF")
FreeCAD.addImportType("Import : DXF Object (*.dxf)","importDXFObj")
#FreeCAD.addImportType("New Importer : DxfFileObject (*.scad)","importFileDXFObj")
FreeCAD.addExportType("Limited Export : CSG exportCSG (*.csg)","exportAltCSG")
'''

# Worbench diffinition __init__py or init_gui
# init_gui more logical
'''
# --- Step 1: import resources first ---
from .Resources import resources_rc  # registers icons and UI

# --- Step 2: import your preferences ---
from . import preferences

class OpenSCADWorkbench_Ext(Gui.Workbench):
    MenuText = "OpenSCAD_Ext"
    ToolTip = "External replacement for legacy OpenSCAD tools"
    Icon = "OpenSCAD_Ext.svg"

    def Initialize(self):
        # Make sure Qt knows about the icons
        Gui.addIconPath(":/icons")
        Gui.addLanguagePath(":/translations")
        # preferences.Load()  # load preferences AFTER icons/UI registered

    def Activated(self):
        FreeCAD.Console.PrintMessage("✅ OpenSCAD_Ext activated\n")

    def Deactivated(self):
        FreeCAD.Console.PrintMessage("✅ OpenSCAD_Ext deactivated\n")

    def GetClassName(self):
        return "Gui::PythonWorkbench"

# --- Step 3: register workbench ---
#Gui.addWorkbench(OpenSCADWorkbench_Ext())
'''

