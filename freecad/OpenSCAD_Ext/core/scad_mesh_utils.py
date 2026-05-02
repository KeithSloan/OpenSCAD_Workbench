# core/scad_mesh_utils.py
"""
Utilities for Mesh-mode SCAD objects stored as Mesh::Feature.

Mesh::Feature is used instead of Part::FeaturePython for Mesh mode because
FreeCAD 1.1's TNP element-map machinery must index every mesh triangle on
every selection/highlight event when the shape is stored as Part.Shape,
causing the cursor to spin indefinitely on complex OpenSCAD models.

Mesh::Feature uses OpenInventor's SoIndexedFaceSet renderer — no TNP, no
element maps, no spinning cursor.

The workflow:
  1. executeFunction() on the FeaturePython runs OpenSCAD and creates a
     companion Mesh::Feature (already done in SCADObject.py).
  2. finalize_scad_mesh_object() is called by the importer after
     executeFunction() completes.  It copies all SCAD properties to the
     companion, makes it visible, and removes the FeaturePython.
  3. The result is a single Mesh::Feature in the document that has both
     the mesh geometry AND the parametric properties (sourceFile,
     linked_varset, fnmax, timeout, …).
  4. render_scad_mesh_feature() is called by the Render command to
     re-run OpenSCAD on the Mesh::Feature and update its Mesh.
"""

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

# Properties to migrate from FeaturePython → Mesh::Feature
_SCAD_PROPS = [
    ("App::PropertyFile",    "sourceFile",    "OpenSCAD", "SCAD source file"),
    ("App::PropertyString",  "linked_varset", "OpenSCAD", "VarSet object name"),
    ("App::PropertyString",  "mode",          "OpenSCAD", "Geometry mode"),
    ("App::PropertyInteger", "fnmax",         "OpenSCAD", "Max polygon sides"),
    ("App::PropertyInteger", "timeout",       "OpenSCAD", "OpenSCAD timeout (secs)"),
    ("App::PropertyBool",    "keep_work_doc", "OpenSCAD", "Keep work document"),
    ("App::PropertyBool",    "modules",       "OpenSCAD", "Uses SCAD modules"),
    ("App::PropertyString",  "message",       "OpenSCAD", "Last OpenSCAD message"),
]


def finalize_scad_mesh_object(fp_obj):
    """
    Convert a Mesh-mode FeaturePython+companion pair into a single Mesh::Feature.

    After executeFunction() has created the companion Mesh::Feature, this
    function:
      - Adds SCAD properties to the companion
      - Copies their values from the FeaturePython
      - Renames the companion to the FeaturePython's label
      - Makes the companion visible
      - Removes the FeaturePython

    Returns the Mesh::Feature, or the original fp_obj if no companion exists.
    """
    companion_name = getattr(fp_obj, 'companion_mesh', '')
    doc = fp_obj.Document
    companion = doc.getObject(companion_name) if companion_name else None

    if companion is None:
        # Either OpenSCAD failed in Mesh mode (no companion created) or
        # executeFunction() produced a valid BRep shape via a fallback path.
        # In either case leave fp_obj as-is — nothing to collapse.
        write_log("MeshUtils",
            f"finalize: no companion for {fp_obj.Name} "
            f"(shape null={fp_obj.Shape.isNull() if hasattr(fp_obj, 'Shape') else 'n/a'}) — skipping")
        return fp_obj

    # Add and populate SCAD properties on companion
    for prop_type, prop_name, group, desc in _SCAD_PROPS:
        if not hasattr(companion, prop_name):
            try:
                companion.addProperty(prop_type, prop_name, group, desc)
            except Exception as e:
                write_log("MeshUtils", f"addProperty {prop_name}: {e}")
        val = getattr(fp_obj, prop_name, None)
        if val is not None:
            try:
                setattr(companion, prop_name, val)
            except Exception as e:
                write_log("MeshUtils", f"setattr {prop_name}={val!r}: {e}")

    # Give companion the same user-visible label as the FeaturePython
    companion.Label = fp_obj.Label

    # Remove the FeaturePython (proxy + empty shape)
    fp_name = fp_obj.Name
    doc.removeObject(fp_name)
    write_log("MeshUtils", f"Removed FeaturePython '{fp_name}', "
              f"companion Mesh::Feature '{companion.Name}' promoted")

    # Make companion visible
    try:
        companion.ViewObject.Visibility = True
        companion.ViewObject.DisplayMode = "Shaded"
    except AttributeError:
        pass

    return companion


def render_scad_mesh_feature(obj):
    """
    Re-run OpenSCAD for a Mesh-mode SCAD object stored as Mesh::Feature.

    Reads the VarSet (if linked) to build -D overrides, runs OpenSCAD,
    and updates obj.Mesh with the result.
    """
    import FreeCAD
    from freecad.OpenSCAD_Ext.objects.SCADObject import createMesh

    source = getattr(obj, 'sourceFile', None)
    if not source:
        FreeCAD.Console.PrintError(
            f"render_scad_mesh_feature: {obj.Label} has no sourceFile\n")
        return

    # Build -D overrides from linked VarSet
    d_params = None
    varset_name = getattr(obj, 'linked_varset', '')
    if varset_name:
        varset = obj.Document.getObject(varset_name)
        if varset is not None:
            from freecad.OpenSCAD_Ext.core.varset_utils import varset_to_D_params
            d_params = varset_to_D_params(varset) or None

    write_log("MeshUtils",
        f"render_scad_mesh_feature: {obj.Label} source={source} "
        f"d_params={d_params}")

    mesh = createMesh(obj, source, d_params=d_params)
    if mesh is not None:
        obj.Mesh = mesh
        try:
            obj.ViewObject.DisplayMode = "Shaded"
        except AttributeError:
            pass
        write_log("MeshUtils", f"Mesh updated: {obj.Label}")
    else:
        FreeCAD.Console.PrintError(
            f"render_scad_mesh_feature: OpenSCAD failed for {obj.Label}\n")
