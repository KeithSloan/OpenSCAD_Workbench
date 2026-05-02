# core/attach_varset.py
"""
Shared helper: scan a .scad source file for customizer variables and attach
a top-level VarSet to an existing SCADfileBase object.

Called from:
  - importFileSCAD.insert()        — always attach if variables exist
  - importASTCSG.open/insert()     — only reached when user chose "parametric"
  - OpenSCADLibraryBrowser        — replaces inline varset-wiring code
"""

from pathlib import Path

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


def attach_customizer_varset(obj, source_file, *, doc=None, meta=None):
    """
    Scan *source_file* and, if it contains top-level variables, create (or
    update) an ``App::VarSet`` and link it to *obj* via ``obj.linked_varset``.

    Parameters
    ----------
    obj         : Part::FeaturePython (SCADfileBase) to attach the VarSet to.
    source_file : Absolute path to the .scad source file.
    doc         : FreeCAD document.  Defaults to ``obj.Document``.
    meta        : Pre-computed :class:`ScadMeta` (avoids a redundant scan when
                  the caller already has it).

    Returns
    -------
    App::VarSet or None
        The created / updated VarSet, or ``None`` if the file had no variables.
    """
    from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file
    from freecad.OpenSCAD_Ext.core.varset_utils import create_toplevel_varset

    if meta is None:
        meta = scan_scad_file(source_file)

    # Skip if there are no user-facing variables (_-prefixed are filtered
    # inside create_toplevel_varset already, but check here to avoid creating
    # an empty VarSet).
    user_vars = {k: v for k, v in meta.variables.items() if not k.startswith("_")}
    if not user_vars:
        write_log("VarSet", f"No user variables in {Path(source_file).name} — skipping VarSet")
        return None

    target_doc = doc or obj.Document
    stem = Path(source_file).stem
    varset_name = f"{stem}_Vars"

    varset = create_toplevel_varset(target_doc, meta, varset_name)
    if varset is None:
        write_log("VarSet", f"create_toplevel_varset returned None for {varset_name}")
        return None

    if hasattr(obj, "linked_varset"):
        obj.linked_varset = varset.Name   # PropertyString — store name, not object ref
        write_log("VarSet", f"Linked VarSet '{varset.Name}' → '{obj.Name}'")
    else:
        write_log("VarSet", f"obj '{obj.Name}' has no linked_varset property — VarSet created but not linked")

    return varset
