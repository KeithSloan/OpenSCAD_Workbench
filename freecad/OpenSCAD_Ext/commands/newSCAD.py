import FreeCAD
import FreeCADGui

class NewSCADFile_Class:
    """Create a new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'New SCAD File Object',
            'ToolTip': 'Create a new SCAD file Objec',
            'Pixmap': ':/icons/newScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("New SCAD File Object executed\n")
        FreeCAD.Console.PrintError("New SCAD File Object executed\n")

    def IsActive(self):
        return True

FreeCADGui.addCommand("NewSCADFileObject_CMD", NewSCADFile_Class())

