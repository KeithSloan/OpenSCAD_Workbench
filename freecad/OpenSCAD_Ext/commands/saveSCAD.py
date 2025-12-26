import FreeCAD
import FreeCADGui

from PySide import QtCore
from PySide import QtGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.SCADObject import SCADfileBase, ViewSCADProvider


class EditTextValue(QtGui.QWidget):
    def __init__(self, label="", default="", parent=None):
        super(EditTextValue, self).__init__(parent)

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QtGui.QLabel(label)
        layout.addWidget(self.label)

        self.textName = QtGui.QLineEdit(default)
        #self.textName.setPlaceholderText(default"Enterfilename")
        layout.addWidget(self.textName, 1)
        self.textName.editingFinished.connect(self.getVal)
        self.show()

    def getVal(self):
        return self.textName.text()

class GeometryType(QtGui.QWidget):
        def __init__(self):
                super().__init__()
                self.layout = QtGui.QHBoxLayout()
                self.label = QtGui.QLabel('Geometry Type')
                self.layout.addWidget(self.label)
                self.importType = QtGui.QComboBox()
                self.importType.addItem('Mesh')
                self.importType.addItem('Brep')
                self.importType.addItem('Opt')
                self.layout.addWidget(self.importType)
                self.setLayout(self.layout)

        def getVal(self):
                return self.importType.currentText()
                     

class IntegerValue(QtGui.QWidget):
	def __init__(self, label, value):
		super().__init__()
		self.layout = QtGui.QHBoxLayout()
		self.label = QtGui.QLabel(label)
		self.value = QtGui.QLineEdit()
		self.value.setText(str(value))
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.value)
		self.setLayout(self.layout)

	def getVal(self):
		return int(self.value.text())

class BooleanValue(QtGui.QWidget):
	def __init__(self, label, value):
		super().__init__()
		self.layout = QtGui.QHBoxLayout()
		self.label = QtGui.QLabel(label)
		self.value = QtGui.QRadioButton()
		self.value.setChecked(value)
		self.layout.addWidget(self.label)
		self.layout.addWidget(self.value)
		self.setLayout(self.layout)

	def getVal(self):
		if self.value.isChecked():
			return True
		else:
			return False

class OpenSCADeditOptions(QtGui.QDialog):
    def __init__(self, parent=None, scadName="SCAD_Object"):
        super(OpenSCADeditOptions, self).__init__(parent)
        self.scadNname = scadName
        self.initUI()

    def initUI(self):
        self.result = None

        self.setGeometry(150, 250, 400, 300)
        self.setWindowTitle("SCAD File Object edit Options")

        self.layout = QtGui.QVBoxLayout()
        self.setMouseTracking(True)

        # ---------- Options ----------
        self.scadName = EditTextValue(label="SCADname",default="SCADname")
        self.layout.addWidget(self.scadName)
        self.geometryType = GeometryType()
        self.layout.addWidget(self.geometryType)
        self.fnMax = IntegerValue("FnMax", 16)
        self.layout.addWidget(self.fnMax)
        self.timeOut = IntegerValue("TimeOut", 30)
        self.layout.addWidget(self.timeOut)
        self.keepOption = BooleanValue("Keep File", False)
        self.layout.addWidget(self.keepOption)

        # ---------- OK / Cancel ----------
        self.buttonBox = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel,
            self
        )
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

        self.show()


    def getValues(self):
        return(
              self.scadName.getVal(), \
              self.geometryType.getVal(), \
              self.fnMax.getVal(), \
              self.timeOut.getVal(), \
              self.keepOption.getVal()
              )

    def onCancel(self):
        self.result = 'cancel'
        #QtGui.QGuiApplication.restoreOverrideCursor()

    def onOk(self):
        self.result = 'ok'
        #QtGui.QGuiApplication.restoreOverrideCursor()

from freecad.OpenSCAD_Ext.commands.Params import BaseParams

class NewSCADFile_Class(BaseParams):
    """Create a new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'New SCAD File Object',
            'ToolTip': 'Create a new SCAD file Object',
            'Pixmap': ':/icons/newScadFileObj.svg'
        }

    def Activated(self):
        import os
        FreeCAD.Console.PrintMessage("New SCAD File Object executed\n")
        FreeCAD.Console.PrintError("New SCAD File Object executed\n")
        write_log("Info", "New SCAD File Object executed")
        QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
        dialog = OpenSCADeditOptions()
        result = dialog.exec_()
        QtGui.QGuiApplication.restoreOverrideCursor()
        if result == QtGui.QDialog.Accepted:
                write_log("Info",f"Result {dialog.result}")
                write_log("Info",f"Action")
                options = dialog.getValues()
                write_log("Info",f"Options {options}")

                # Create SCAD Object
                obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", options[0])
                #
                #scadObj = SCADfileBase(obj, scadName, sourcefile, mode='Mesh', fnmax=16, timeout=30)
                # change SCADfileBase to accept single options call ?
                #
                scadName = options[0]
                sourceFile = os.path.join(self.getSourceDirectory(), scadName)
                scadObj = SCADfileBase(obj, scadName, sourceFile, \
                          options[1], \
                          options[2], \
                          options[3], \
                          options[4], \
                          )
                ViewSCADProvider(obj.ViewObject)

                #if hasattr(obj, 'Proxy'):
                   #filename = "New_File"
                   #obj = doc.addObject("Part::FeaturePython", filename)
                   #
                   #scadObj = SCADfileBase(obj, filename, mode='Mesh', fnmax=16, timeout=30)
                   # change SCADfileBase to accept single options call ?
                   #
                   #scadObj = SCADfileBase(obj, filename, options[1], \
                   #                options[2], options[3], options[4])
                   #        ViewSCADProvider(obj.ViewObject)

    def IsActive(self):
        return True


    def getSourceDirectory(self):
        return self.scadSourcePath


    def editFile(self, scadPath):
        #scadPath = os.join(self.scadSourcePathName, scadName)
        import subprocess,  os, sys
        p1 = subprocess.Popen( \
             [editorPathName, fname], \
             stdin=subprocess.PIPE,\
             stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        write_log("Info", f"Launching editor: {self.editorPathName} {scadPath}")

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

