# freecad/OpenSCAD_Ext/gui/OpenSCADeditOptions.py
from PySide import QtCore
from PySide2 import QtWidgets
from pathlib import Path
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams  # for workbench preference path
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

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
        self.importType.addItems(["Mesh", "AST_Brep", "Brep"])
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
        super().__init__(None)   # no parent, no reuse

        # ---- authoritative title ----
        self.setWindowTitle(str(title))

        # ---- dialog state (pure data) ----
        self.newFile = bool(kwargs.get("newFile", True))
        self.scadNameVal = kwargs.get("scadName", "")
        self.sourceFile = kwargs.get("sourceFile", None)

        write_log("EditOpt", f"INIT scadName={self.scadNameVal}")

        # ---- rebuild layout cleanly ----
        self.layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.layout)

        # ---- build widgets fresh ----
        self._build_ui()

        # ---- force reset widget contents ----
        if hasattr(self, "scadName"):
            self.scadName.lineEdit.blockSignals(True)
            self.scadName.lineEdit.clear()
            self.scadName.lineEdit.setText(str(self.scadNameVal))
            self.scadName.lineEdit.blockSignals(False)

        if hasattr(self, "sourceFileEdit"):
            self.sourceFileEdit.blockSignals(True)
            self.sourceFileEdit.clear()
            if self.sourceFile:
                self.sourceFileEdit.setText(str(self.sourceFile))
            self.sourceFileEdit.blockSignals(False)

    def _build_ui(self):
        # ---------- SCAD Name ----------
        readOnly = False
        if self.newFile is False:
            if self.sourceFile:
                self.scadNameVal = Path(self.sourceFile).stem
                readOnly = True
            else:
                write_log("Edit Options","newFile = False and No sourceFile")
        if self.scadNameVal is None:
            self.scadNameVal = "SCAD_Object"
            
        write_log("EditOptions",self.scadNameVal)
        self.scadName = EditTextValue(
            "SCAD Name",
            default=self.scadNameVal,
            readOnly=readOnly
        )
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
