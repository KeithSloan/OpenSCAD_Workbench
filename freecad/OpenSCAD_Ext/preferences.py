import FreeCAD
import FreeCADGui
from PySide2 import QtCore, QtWidgets, QtUiTools

# --- Import your own resources_rc (local workbench) ---
from .Resources import resources_rc

class OpenSCAD_Ext_Preferences(QtWidgets.QWidget):
    """Preferences page for OpenSCAD_Ext workbench."""

    def __init__(self):
        super().__init__()

        # Load UI
        loader = QtUiTools.QUiLoader()
        ui_file = QtCore.QFile(":/ui/OpenSCAD_Ext_Preferences.ui")
        if not ui_file.open(QtCore.QFile.ReadOnly):
            FreeCAD.Console.PrintError("❌ Failed to open UI file: :/ui/OpenSCAD_Ext_Preferences.ui\n")
            return
        self.form = loader.load(ui_file, self)
        ui_file.close()

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.form)
        layout.setContentsMargins(0, 0, 0, 0)

    def apply(self):
        """Save preferences to FreeCAD parameters."""
        prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD_Ext")
        chk = self.form.findChild(QtWidgets.QCheckBox, "chkVerboseLogging")
        if chk:
            prefs.SetBool("VerboseLogging", chk.isChecked())


# --- Compatibility loader for FreeCAD ---
def Load():
    """Load the preference page in FreeCAD using whichever API is available."""
    provider = {
        "name": "OpenSCAD_Ext",
        "group": "OpenSCAD_Ext",
        "page": OpenSCAD_Ext_Preferences,
    }

    if hasattr(FreeCADGui, "addPreferencePageProvider"):
        FreeCAD.Console.PrintMessage("🔧 Using new addPreferencePageProvider API\n")
        class Provider:
            def getPages(self):
                return [provider]
        FreeCADGui.addPreferencePageProvider(Provider())
        return

    if hasattr(FreeCADGui, "addPreferencePage"):
        FreeCAD.Console.PrintMessage("🔧 Using legacy addPreferencePage API\n")
        FreeCADGui.addPreferencePage(OpenSCAD_Ext_Preferences, "OpenSCAD_Ext")
        return

    FreeCAD.Console.PrintError("❌ No usable preference API in this FreeCAD build\n")

