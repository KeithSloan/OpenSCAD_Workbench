import os
from pathlib import Path

import FreeCAD
import FreeCADGui

from PySide import QtWidgets
from PySide import QtGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider


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
    def __init__(self, parent=None, scadName="SCAD_Object", newObject=True):
        super(OpenSCADeditOptions, self).__init__(parent)
        self.newObject = newObject
        if newObject:
            self.sourceFile = os.path.join(BaseParams.getScadSourcePath(),scadName)
            self.scadName = scadName
        else:
            write_log("INFO",f"{scadName} newObject = {newObject}")
            self.sourceFile = scadName
            self.scadName = Path(self.sourceFile).stem
            write_log("INFO",f"{scadName} newObject = {newObject}")

        self.initUI()

    def initUI(self):
        self.result = None

        self.setGeometry(150, 250, 400, 300)
        self.setWindowTitle("SCAD File Object edit Options")

        self.layout = QtGui.QVBoxLayout()
        self.setMouseTracking(True)

        # ---------- Options ----------
        self.scadName = EditTextValue(label="SCADname", default=self.scadName)
        if not self.newObject:
            line_edit = self.scadName.findChild(QtWidgets.QLineEdit)
            if line_edit:
                line_edit.setReadOnly(True)
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

    def create_from_dialog(self, sourceFile, newFile=True):
        name = Path(sourceFile).stem
        if newFile:
            sourceFile = os.path.join(BaseParams.getScadSourcePath(),sourceFile)
        doc = FreeCAD.ActiveDocument
        if not doc:
            doc = FreeCAD.newDocument(name)
            write_log("Info", f"Created new document: {name}")    
        obj = doc.addObject("Part::FeaturePython", name)
        write_log("Info", f"Created new SCAD Object: {name}")
        scadObj = SCADfileBase(obj, name, sourceFile, \
            self.geometryType.getVal(), \
            self.fnMax.getVal(), \
            self.timeOut.getVal(), \
            self.keepOption.getVal()
            )
        ViewSCADProvider(obj.ViewObject)
        return scadObj

    def getName(self):
        return self.scadName.getVal()

    def get_sourceFile(self):
        return self.sourceFile

    def onCancel(self):
        self.result = 'cancel'
        #QtGui.QGuiApplication.restoreOverrideCursor()

    def onOk(self):
        self.result = 'ok'
        #QtGui.QGuiApplication.restoreOverrideCursor()


# Can be called from newSCAD and OpenSCADLibraryBrowser
@staticmethod
def create_NewObject(sourceFile, newFile=True):
    if newFile:
        sourceFile = os.path.join(BaseParams.getScadSourcePath(),sourceFile)
    QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
    dialog = OpenSCADeditOptions()
    result = dialog.exec_()
    QtGui.QGuiApplication.restoreOverrideCursor()
    if result != QtGui.QDialog.Accepted:
        pass
    write_log("Info",f"Result {dialog.result}")
    write_log("Info",f"Action")
    options = dialog.getValues()
    write_log("Info",f"Options {options}")

    # Create SCAD Object
    scadName = dialog.getName()
    scadObj = dialog.create_from_dialog(scadName)
    if scadObj:
        scadObj.editFile(sourceFile)

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
        write_log("Info", "New SCAD File Object executed")
        #create_NewObject("SCADname", newFile=True)
        QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
        dialog = OpenSCADeditOptions()
        result = dialog.exec_()
        QtGui.QGuiApplication.restoreOverrideCursor()
        if result != QtGui.QDialog.Accepted:
            pass
        write_log("Info",f"Result {dialog.result}")
        write_log("Info",f"Action")
        options = dialog.getValues()
        write_log("Info",f"Options {options}")

        # Create SCAD Object
        scadName = dialog.getName()
        sourceFile = dialog.get_sourceFile()
        scadObj = dialog.create_from_dialog(scadName)
        if scadObj:
            scadObj.editFile(sourceFile)
        


        #doc = FreeCAD.ActiveDocument
        #if doc is None:
        #   doc_name = options[0]
        #   doc = FreeCAD.newDocument(doc_name)
        #   write_log("Info", f"Created new document: {doc_name}")

        #obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", options[0])
        #
        #scadObj = SCADfileBase(obj, scadName, sourcefile, mode='Mesh', fnmax=16, timeout=30)
        # change SCADfileBase to accept single options call ?
        #
        #scadName = options[0]
        #scadBase = scadName + ".scad"
        #sourceFile = os.path.join(BaseParams.getScadSourcePath(), scadBase)
        #scadObj = SCADfileBase(obj, scadName, sourceFile, \
        #          options[1], \
        #          options[2], \
        #          options[3], \
        #          options[4], \
        #          )
        #ViewSCADProvider(obj.ViewObject)
        #self.editFile(scadName, sourceFile)

        #if hasattr(obj, 'Proxy'):
        #filename = "New_File"
        ##obj = doc.addObject("Part::FeaturePython", filename)
        #
        #scadObj = SCADfileBase(obj, filename, mode='Mesh', fnmax=16, timeout=30)
        # change SCADfileBase to accept single options call ?
        #
        #scadObj = SCADfileBase(obj, filename, options[1], \
        #                options[2], options[3], options[4])
        #        ViewSCADPovider(obj.ViewObject)

    def IsActive(self):
        return True


    def getSourceDirectory(self):
        return self.scadSourcePath

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

