# freecad/OpenSCAD_Ext/gui/OpenSCADeditOptions.py
from PySide2 import QtWidgets
from pathlib import Path
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams  # for workbench preference path

# ------------------------
# Widget wrappers
# ------------------------
class EditTextValue(QtWidgets.QWidget):
    def __init__(self, label, default="", readOnly=False, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        self.label = QtWidgets.QLabel(label)
        self.lineEdit = QtWidgets.QLineEdit()
        self.lineEdit.setText(str(default))  # convert to string just in case
        self.lineEdit.setReadOnly(readOnly)
        layout.addWidget(self.label)
        layout.addWidget(self.lineEdit)
        self.setLayout(layout)

    def getVal(self):
        return self.lineEdit.text()

    def setVal(self, value):
        self.lineEdit.setText(str(value))

    def setReadOnly(self, state=True):
        self.lineEdit.setReadOnly(state)


class IntegerValue(QtWidgets.QWidget):
    def __init__(self, label, default=0, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        self.label = QtWidgets.QLabel(label)
        self.spinBox = QtWidgets.QSpinBox()
        self.spinBox.setValue(default)
        layout.addWidget(self.label)
        layout.addWidget(self.spinBox)
        self.setLayout(layout)

    def getVal(self):
        return self.spinBox.value()

    def setVal(self, value):
        self.spinBox.setValue(int(value))


class BooleanValue(QtWidgets.QWidget):
    def __init__(self, label, default=False, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        self.label = QtWidgets.QLabel(label)
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setChecked(default)
        layout.addWidget(self.label)
        layout.addWidget(self.checkbox)
        self.setLayout(layout)

    def getVal(self):
        return self.checkbox.isChecked()

    def setVal(self, value):
        self.checkbox.setChecked(bool(value))


class GeometryType(QtWidgets.QWidget):
    def __init__(self, default=None, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        self.label = QtWidgets.QLabel("Geometry Type")
        self.importType = QtWidgets.QComboBox()
        self.importType.addItems(["Mesh", "Brep", "Opt"])
        layout.addWidget(self.label)
        layout.addWidget(self.importType)
        self.setLayout(layout)
        if default:
            self.setVal(default)

    def getVal(self):
        return self.importType.currentText()

    def setVal(self, value):
        index = self.importType.findText(value)
        if index >= 0:
            self.importType.setCurrentIndex(index)


# ------------------------
# Dialog
# ------------------------
class OpenSCADeditOptions(QtWidgets.QDialog):

    def __init__(self, title, **kwargs):
        super().__init__()

        self.setWindowTitle(title)

        # ---- extract preset first ----
        preset = kwargs.get("preset", {})
        # Use preset values first, then kwargs override if present
        self.newFile = preset.get("newFile", kwargs.get("newFile", True))
        self.scadName = preset.get("newFile", kwargs.get("scadName", True))
        self.sourceFile = preset.get("sourceFile", kwargs.get("sourceFile",True))

        # Keep other parameters
        self.params = kwargs

        # ---- layout MUST be created ----
        self.layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.layout)

        self._build_ui()
        self._apply_presets()

    def _build_ui(self):
        # ---------- SCAD Name ----------
        if self.newFile:
            # Always default to "SCAD_Object" for new files
            scadNameVal = "SCAD_Object"
            readOnly = False
        else:
            scadNameVal = str(Path(self.sourceFile).stem) if self.sourceFile else "SCAD_Object"
            readOnly = True

        self.scadName = EditTextValue("SCAD Name", default=scadNameVal, readOnly=readOnly)
        self.layout.addWidget(self.scadName)

        # ---------- Other fields ----------
        self.geometryType = GeometryType()
        self.layout.addWidget(self.geometryType)

        self.fnMax = IntegerValue("FnMax", 16)
        self.layout.addWidget(self.fnMax)

        self.timeOut = IntegerValue("TimeOut", 30)
        self.layout.addWidget(self.timeOut)

        self.keepOption = BooleanValue("Keep File", False)
        self.layout.addWidget(self.keepOption)

        # ---------- OK / Cancel ----------
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.layout.addWidget(self.buttonBox)

    def _apply_presets(self):
        if self.params.get("fnMax") is not None:
            self.fnMax.setVal(self.params["fnMax"])

        if self.params.get("geometryType") is not None:
            self.geometryType.setVal(self.params["geometryType"])

        if self.params.get("keepOption") is not None:
            self.keepOption.setVal(self.params["keepOption"])

        if self.params.get("preset") == "library":
            self.geometryType.setVal("Brep")

    # ---------- collect values ----------
    def getValues(self):
        scadName = self.scadName.getVal().strip()

        if self.newFile:
            sourceDir = BaseParams.getScadSourcePath()
            self.sourceFile = str(Path(sourceDir) / scadName)

        return {
            "scadName": scadName,
            "geometryType": self.geometryType.getVal(),
            "fnMax": self.fnMax.getVal(),
            "timeOut": self.timeOut.getVal(),
            "keepOption": self.keepOption.getVal(),
            "newFile": self.newFile,
            "sourceFile": self.sourceFile,
        }
