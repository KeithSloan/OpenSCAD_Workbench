import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase


def _replace_mesh_feature_with_brep(mesh_obj):
    """
    Replace a finalized Mesh::Feature with a BRep/AST-Brep FeaturePython.

    Called when the user has changed mode away from "Mesh" on a finalized
    Mesh::Feature.  We can't render a BRep shape onto a Mesh::Feature (it has
    no Part.Shape), so we:
      1. Record all SCAD properties from the old Mesh::Feature.
      2. Remove it from the document.
      3. Create a fresh Part::FeaturePython SCAD object with the new mode.
      4. Restore the linked_varset link on the new object.

    create_scad_object() calls doc.recompute() internally, which triggers
    executeFunction() → the BRep/AST-Brep render happens automatically.
    """
    from freecad.OpenSCAD_Ext.core.create_scad_object import create_scad_object

    label       = mesh_obj.Label
    doc         = mesh_obj.Document
    source      = getattr(mesh_obj, 'sourceFile', '')
    mode        = getattr(mesh_obj, 'mode', 'AST-Brep')
    fnmax       = int(getattr(mesh_obj, 'fnmax', 16))
    timeout     = int(getattr(mesh_obj, 'timeout', 30))
    keep        = bool(getattr(mesh_obj, 'keep_work_doc', False))
    varset_name = getattr(mesh_obj, 'linked_varset', '')

    write_log("Render",
        f"_replace_mesh_feature_with_brep: '{label}' source={source} → mode={mode}")

    # Remove the old Mesh::Feature so the new object can inherit the label.
    mesh_name = mesh_obj.Name
    doc.removeObject(mesh_name)

    new_obj = create_scad_object(
        scadName=label,
        sourceFile=source,
        geometryType=mode,
        fnMax=fnmax,
        timeOut=timeout,
        keepOption=keep,
        newFile=False,
        doc=doc,
    )

    if new_obj is not None:
        # Restore label (create_scad_object may have suffixed the internal name)
        new_obj.Label = label
        # Re-attach VarSet link if one was set
        if varset_name:
            try:
                new_obj.linked_varset = varset_name
            except Exception as e:
                write_log("Render", f"Could not restore linked_varset: {e}")
        write_log("Render",
            f"Replaced Mesh::Feature '{mesh_name}' with "
            f"FeaturePython '{new_obj.Name}' mode={mode}")

        # create_scad_object() calls doc.recompute() which invokes Proxy.execute(),
        # NOT renderFunction().  The shape stays empty until renderFunction() is
        # called explicitly — do it now so the result appears on the first render.
        if hasattr(new_obj, 'Proxy') and hasattr(new_obj.Proxy, 'renderFunction'):
            write_log("Render", f"Calling renderFunction on new object '{new_obj.Name}'")
            try:
                new_obj.Proxy.renderFunction(new_obj)
            except Exception as e:
                FreeCAD.Console.PrintError(
                    f"renderFunction failed for {new_obj.Label}: {e}\n"
                )

        # Ensure the new object is visible in the 3D viewport.
        try:
            new_obj.ViewObject.Visibility = True
            new_obj.ViewObject.DisplayMode = "Shaded"
        except AttributeError as e:
            write_log("Render", f"ViewObject visibility: {e}")

        try:
            FreeCADGui.updateGui()
        except Exception as e:
            write_log("Render", f"updateGui after replace: {e}")

    return new_obj


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

            # Finalized Mesh::Feature — no Proxy, dispatch by current mode.
            # If mode is still "Mesh": update the mesh in-place.
            # If mode was switched to BRep/AST-Brep: replace the Mesh::Feature
            # with a new Part::FeaturePython so it can hold a Part.Shape.
            if _is_scad_mesh_feature(obj):
                mode = getattr(obj, 'mode', 'Mesh')
                if mode == "Mesh":
                    write_log("Render", f"Mesh::Feature mesh re-render: {obj.Label}")
                    try:
                        from freecad.OpenSCAD_Ext.core.scad_mesh_utils import render_scad_mesh_feature
                        render_scad_mesh_feature(obj)
                    except Exception as e:
                        FreeCAD.Console.PrintError(
                            f"Failed to render Mesh::Feature {obj.Label}: {e}\n"
                        )
                else:
                    write_log("Render",
                        f"Mesh::Feature mode-switch: {obj.Label} → {mode}")
                    try:
                        _replace_mesh_feature_with_brep(obj)
                    except Exception as e:
                        FreeCAD.Console.PrintError(
                            f"Failed to replace Mesh::Feature {obj.Label} "
                            f"with BRep: {e}\n"
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

                # Mesh mode: collapse the FeaturePython+companion pair into a
                # single Mesh::Feature so the tree stays clean.  After finalize
                # the FeaturePython is removed — obj is a dangling reference
                # from here, so we must not touch it again (continue below).
                if getattr(obj, 'mode', '') == "Mesh":
                    try:
                        from freecad.OpenSCAD_Ext.core.scad_mesh_utils import finalize_scad_mesh_object
                        finalize_scad_mesh_object(obj)
                    except Exception as e:
                        FreeCAD.Console.PrintError(
                            f"Failed to finalize Mesh object {obj.Label}: {e}\n"
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
