import FreeCAD
import FreeCADGui

from PySide import QtCore
from PySide import QtGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

class OpenSCADeditOptions(QtGui.QDialog):
        def __init__(self,parent=None):
                super(OpenSCADeditOptions, self).__init__(parent)
                self.initUI()

        def initUI(self):
                self.result = None
                # create our window
                # define window           xLoc,yLoc,xDim,yDim
                self.setGeometry(150, 250, 300, 300)
                self.setWindowTitle("FC OpenSCAD edit Options")
                self.layout = QtGui.QVBoxLayout()
                self.setMouseTracking(True)
                self.buttonBox = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel, self)

                # Connect the dialog buttons to standard slots
                self.buttonBox.accepted.connect(self.accept)
                self.buttonBox.rejected.connect(self.reject)
                self.createOnly = BooleanValue('Create Only (Edit)',True)
                self.layout.addWidget(self.createOnly)
                self.importType = ImportType()
                self.layout.addWidget(self.importType)
                self.layout.addWidget(self.importType)
                self.fnMax = IntegerValue('FnMax', 16)
                self.layout.addWidget(self.fnMax)
                self.timeOut = IntegerValue('TimeOut', 30)
                self.layout.addWidget(self.timeOut)
                self.keepOption = BooleanValue("Keep File",False)
                self.layout.addWidget(self.keepOption)
                self.layout.addWidget(self.buttonBox)
                self.setLayout(self.layout)
                self.show()

        def getValues(self):
                return(
                        self.createOnly.getVal(), \
                        self.importType.getVal(), \
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

class NewSCADFile_Class:
    """Create a new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'New SCAD File Object',
            'ToolTip': 'Create a new SCAD file Object',
            'Pixmap': ':/icons/newScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("New SCAD File Object executed\n")
        FreeCAD.Console.PrintError("New SCAD File Object executed\n")
        write_log("Info", "New SCAD File Object executed")
        QtGui.QGuiApplication.setOverrideCursor(QtGui.Qt.ArrowCursor)
        dialog = OpenSCADeditOptions()
        result = dialog.exec_()
        QtGui.QGuiApplication.restoreOverrideCursor()
        if result == QtGui.QDialog.Accepted:
                write_log(f"Result {dialog.result}")
                write_log(f"Action")
                options = dialog.getValues()
                write_log(f"Options {options}")

                # Create SCAD Object
                obj = doc.addObject("Part::FeaturePython", objectName)
                #
                #scadObj = SCADBase(obj, filename, mode='Mesh', fnmax=16, timeout=30)
                # change SCADBase to accept single options call ?
                #
                scadObj = SCADBase(obj, filename, options[1], \
                        options[2], options[3], options[4])
                ViewSCADProvider(obj.ViewObject)

                #if hasattr(obj, 'Proxy'):
                   #filename = "New_File"
                   #obj = doc.addObject("Part::FeaturePython", filename)
                   #
                   #scadObj = SCADBase(obj, filename, mode='Mesh', fnmax=16, timeout=30)
                   # change SCADBase to accept single options call ?
                   #
                   #scadObj = SCADBase(obj, filename, options[1], \
                   #                options[2], options[3], options[4])
                   #        ViewSCADProvider(obj.ViewObject)

    def IsActive(self):
        return True

    def isValidFilePath(path):
        if not path:
           return False

        if not isinstance(path, str):
           return False

        # Expand ~ and environment variables
        path = os.path.expandvars(os.path.expanduser(path))

        # Must exist and be a file
        return os.path.isfile(path)

    def editFile(self, fname):
        import subprocess,  os, sys
        editorPathName = FreeCAD.ParamGet(\
            "User parameter:BaseApp/Preferences/Mod/OpenSCAD").GetString('externalEditor')  
        write_log("Info", f"Path to external editor {editorPathName}")
        if not isValidFilePath(editorPathName):
            FreeCAD.Console.PrintError(
                "External editor path is not set or invalid\n"
            )
            return

        write_log("Info", f"Launching editor: {editorPathName} {fname}")
        p1 = subprocess.Popen( \
             [editorPathName, fname], \
             stdin=subprocess.PIPE,\
             stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        write_log("Info", f"Launching editor: {editorPathName} {fname}")

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

