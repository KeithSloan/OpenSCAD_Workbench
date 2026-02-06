import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams

class EditSCADFile_Class(BaseParams):
    """Edit new SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'Edit SCAD File Object',
            'ToolTip': 'Edit  a new SCAD file Object',
            'Pixmap': ':/icons/editScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Edit SCAD File Object executed\n")
        write_log("Info", "Edit SCAD File Object executed")
        doc = FreeCAD.ActiveDocument
        write_log("Info",doc.Label)
        if not doc:
            write_log("No Active Document")
            return

        sel = FreeCADGui.Selection.getSelection()
        write_log("Info",f"selection {sel}")
        #if not sel:
        #    FreeCAD.Console.PrintErrorMessage("No objects selected\n")
        #return

        for obj in sel:
            if obj.TypeId != "Part::FeaturePython":
               write_log("INFO","Feature Python")
               continue

            proxy = getattr(obj, "Proxy", None)
            if proxy is None:
                continue

            write_log("INFO","Has Proxy")
            if not isinstance(proxy, SCADfileBase):
                continue
            write_log("INFO","isinstance SCADfileBase")

            try:
               write_log("EDIT",f"obj.sourceFile {obj.sourceFile}")
               self.editSource(obj.sourceFile)

            except Exception as e:
               FreeCAD.Console.PrintError(
                f"Failed to edit SCAD file for {obj.Label}: {e}\n"
               )

    def IsActive(self):
        return True


FreeCADGui.addCommand("EditSCADFileObject_CMD", EditSCADFile_Class())
