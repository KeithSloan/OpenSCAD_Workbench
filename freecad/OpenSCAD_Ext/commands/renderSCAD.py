import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase


def _is_scad_mesh_feature(obj):
    """True if obj is a finalized Mesh::Feature with SCAD properties attached."""
    return (obj.TypeId == "Mesh::Feature"
            and hasattr(obj, "sourceFile")
            and bool(getattr(obj, "sourceFile", "")))


def _find_render_targets(sel):
    """
    Return the list of SCAD objects to render.

    Handles three selection cases:
    1. User selected a Part::FeaturePython SCAD object → use it.
    2. User selected a finalized Mesh::Feature SCAD object → use it.
    3. User selected an App::VarSet → find every SCAD object (FeaturePython
       or Mesh::Feature) whose linked_varset points to that VarSet.

    This means the user never has to manually re-select the SCAD object after
    tweaking a customizer parameter — clicking Render with the VarSet focused
    just works.
    """
    doc = FreeCAD.ActiveDocument
    targets = []

    for obj in sel:
        if obj.TypeId == "Part::FeaturePython":
            targets.append(obj)

        elif _is_scad_mesh_feature(obj):
            targets.append(obj)

        elif obj.TypeId == "App::VarSet" and doc is not None:
            # Find all SCAD objects linked to this VarSet.
            # linked_varset is a PropertyString holding the VarSet's object name.
            for candidate in doc.Objects:
                if (hasattr(candidate, "linked_varset")
                        and candidate.linked_varset == obj.Name
                        and (candidate.TypeId == "Part::FeaturePython"
                             or _is_scad_mesh_feature(candidate))):
                    write_log("Render",
                        f"VarSet '{obj.Label}' selected — resolving to SCAD "
                        f"object '{candidate.Label}'")
                    targets.append(candidate)

    return targets


class RenderSCADFileObject_Class:
    """Execute SCAD file Object """
    def GetResources(self):
        return {
            'MenuText': 'Render SCAD File Object to Shape',
            'ToolTip': 'Render SCAD file Object to Shape',
            'Pixmap': 'renderScadFileObj.svg'
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Render SCAD File Object executed\n")

        write_log("Info", "Render SCAD File Object to Shape")
        doc = FreeCAD.ActiveDocument
        write_log("Info", f"Document {doc.Label}")

        sel = FreeCADGui.Selection.getSelection()
        write_log("Info", f"selection {sel}")

        targets = _find_render_targets(sel)

        if not targets:
            FreeCAD.Console.PrintWarning(
                "Render: no SCAD object selected.  "
                "Select the SCAD object (or its linked VarSet) and try again.\n"
            )
            return

        for obj in targets:
            write_log("Info", f"obj {obj.Label} TypeId {obj.TypeId}")

            # Finalized Mesh::Feature — no Proxy, use render_scad_mesh_feature()
            if _is_scad_mesh_feature(obj):
                write_log("Render", f"Mesh::Feature render: {obj.Label}")
                try:
                    from freecad.OpenSCAD_Ext.core.scad_mesh_utils import render_scad_mesh_feature
                    render_scad_mesh_feature(obj)
                except Exception as e:
                    FreeCAD.Console.PrintError(
                        f"Failed to render Mesh::Feature {obj.Label}: {e}\n"
                    )
                continue

            if not hasattr(obj, "Proxy"):
                continue

            write_log("INFO", "Has Proxy")

            if hasattr(obj.Proxy, "renderFunction"):
                write_log("INFO", "Has renderFunction")
                try:
                    write_log("Render", f"obj.sourceFile {obj.sourceFile}")
                    obj.Proxy.renderFunction(obj)
                except Exception as e:
                    FreeCAD.Console.PrintError(
                        f"Failed to Render SCAD file for {obj.Label}: {e}\n"
                    )

            # Fallback for older AlternateImporter objects
            elif hasattr(obj.Proxy, "executeFunction"):
                try:
                    write_log("Execute Function", f"obj.sourceFile {obj.sourceFile}")
                    obj.Proxy.executeFunction(obj)
                except Exception as e:
                    FreeCAD.Console.PrintError(
                        f"Failed to ExecuteFunction SCAD file for {obj.Label}: {e}\n"
                    )

    def IsActive(self):
        return True


FreeCADGui.addCommand("RenderSCADFileObject_CMD", RenderSCADFileObject_Class())
