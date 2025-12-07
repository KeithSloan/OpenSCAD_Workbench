import FreeCAD
import FreeCADGui

class ExecSCADFileObject_Class:
    """Execute SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'Execute SCAD File Object',
            'ToolTip': 'Execute a SCAD file Object',
            'Pixmap': ':/icons/execScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Execute SCAD File Object executed\n")
        FreeCAD.Console.PrintError("Execute SCAD File Object executed\n")

    def IsActive(self):
        return True

FreeCADGui.addCommand("ExecSCADFileObject_CMD", ExecSCADFileObject_Class())

