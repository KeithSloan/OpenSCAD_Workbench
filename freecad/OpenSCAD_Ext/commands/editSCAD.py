import FreeCAD
import FreeCADGui

class EditSCADFileObject_Class:
    """Edit new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'Edit SCAD File Object',
            'ToolTip': 'Edit  a new SCAD file Objec',
            'Pixmap': ':/icons/editScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Edit SCAD File Object executed\n")
        FreeCAD.Console.PrintError("Edit SCAD File Object executed\n")

    def IsActive(self):
        return True

FreeCADGui.addCommand("EditSCADFileObject_CMD", EditSCADFileObject_Class())
