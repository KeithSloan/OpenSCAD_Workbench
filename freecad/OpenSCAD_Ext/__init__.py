import FreeCADGui as Gui
import FreeCAD

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

