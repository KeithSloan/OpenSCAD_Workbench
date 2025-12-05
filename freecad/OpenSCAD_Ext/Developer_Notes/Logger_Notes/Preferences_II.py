import FreeCAD, FreeCADGui, os
from PySide2 import QtWidgets, QtUiTools

PREFS_PATH = "User parameter:BaseApp/Preferences/YourWorkbench"

class WBPreferences(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(os.path.dirname(__file__), "resources", "prefs.ui")

        loader = QtUiTools.QUiLoader()
        self.ui = loader.load(ui_path)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.ui)

        # Load current state
        param = FreeCAD.ParamGet(PREFS_PATH)
        current = param.GetBool("EnableLogging", False)
        self.ui.enableLoggingCheckBox.setChecked(current)

        # Connect signal
        self.ui.enableLoggingCheckBox.stateChanged.connect(self.saveSettings)

    def saveSettings(self, state):
        param = FreeCAD.ParamGet(PREFS_PATH)
        param.SetBool("EnableLogging", bool(state))

