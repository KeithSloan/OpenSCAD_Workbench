import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams


def resolve_scad_object(obj):
    """
    Given a selected object, return the Part::FeaturePython with a SCADfileBase
    proxy that owns it — or None if not found.

    Handles two cases:
    1. obj IS the FeaturePython → return it directly.
    2. obj is a Mesh::Feature companion → search the document for the
       FeaturePython whose companion_mesh property names this object.
    """
    if obj is None:
        return None

    # Direct hit
    proxy = getattr(obj, "Proxy", None)
    if isinstance(proxy, SCADfileBase):
        return obj

    # Companion Mesh::Feature → find the owning FeaturePython
    doc = getattr(obj, "Document", None) or FreeCAD.ActiveDocument
    if doc is None:
        return None
    for candidate in doc.Objects:
        if candidate.TypeId != "Part::FeaturePython":
            continue
        if getattr(candidate, "companion_mesh", "") == obj.Name:
            proxy = getattr(candidate, "Proxy", None)
            if isinstance(proxy, SCADfileBase):
                write_log("Info", f"Resolved companion '{obj.Name}' → '{candidate.Name}'")
                return candidate
    return None


class EditSCADFile_Class(BaseParams):
    """Edit SCAD file Object"""
    def GetResources(self):
        return {
            'MenuText': 'Edit SCAD File Object',
            'ToolTip': 'Edit a SCAD file Object',
            'Pixmap': 'editScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Edit SCAD File Object executed\n")
        write_log("Info", "Edit SCAD File Object executed")
        doc = FreeCAD.ActiveDocument
        if not doc:
            write_log("Info", "No Active Document")
            return

        sel = FreeCADGui.Selection.getSelection()
        write_log("Info", f"selection {sel}")

        for obj in sel:
            scad_obj = resolve_scad_object(obj)
            if scad_obj is None:
                write_log("INFO", f"Selected object '{obj.Label}' is not a SCAD object")
                continue
            try:
                write_log("EDIT", f"obj.sourceFile {scad_obj.sourceFile}")
                self.editSource(scad_obj.sourceFile)
            except Exception as e:
                FreeCAD.Console.PrintError(
                    f"Failed to edit SCAD file for {scad_obj.Label}: {e}\n"
                )

    def IsActive(self):
        return True


FreeCADGui.addCommand("EditSCADFileObject_CMD", EditSCADFile_Class())
