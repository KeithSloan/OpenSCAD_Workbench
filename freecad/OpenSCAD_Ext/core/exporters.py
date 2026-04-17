"""
Variable export strategies for the Extract Variables command.

Reads varExportTarget (0=VarSet, 1=Vars, 2=Spreadsheet) and
varExportPrompt (bool) from preferences, then delegates to the
appropriate exporter.

Public API
----------
    export_variables(doc, meta, label) -> None
"""

from __future__ import annotations

import FreeCAD

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_model import ScadMeta

_PREFS_PATH = "User parameter:BaseApp/Preferences/Mod/OpenSCAD_Ext"

# Export target indices (must match varExportTarget combo order in .ui)
_TARGET_VARSET = 0
_TARGET_VARS = 1
_TARGET_SPREADSHEET = 2


# ---------------------------------------------------------------------------
# Strategy base
# ---------------------------------------------------------------------------

class BaseExporter:
    def export(self, doc, meta: ScadMeta, label: str) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# VarSet exporter  (active implementation)
# ---------------------------------------------------------------------------

class VarSetExporter(BaseExporter):
    """Creates (or updates) an App::VarSet named after the SCAD source label."""

    def export(self, doc, meta: ScadMeta, label: str) -> None:
        if not meta.variables:
            write_log("INFO", f"VarSetExporter: no variables in {label}, skipping")
            return

        varset_name = f"Vars_{label}"

        # Reuse existing VarSet if present
        varset = doc.getObject(varset_name)
        if varset is None:
            varset = doc.addObject("App::VarSet", varset_name)
            varset.Label = varset_name
            write_log("INFO", f"VarSetExporter: created VarSet '{varset_name}'")
        else:
            write_log("INFO", f"VarSetExporter: updating VarSet '{varset_name}'")

        for name, expr in meta.variables.items():
            desc = meta.variable_descriptions.get(name, f"SCAD variable {name}")
            prop_type = _infer_property_type(expr)

            if not hasattr(varset, name):
                try:
                    varset.addProperty(prop_type, name, "SCAD Variables", desc)
                except Exception as exc:
                    write_log("WARN", f"VarSetExporter: cannot add property '{name}': {exc}")
                    continue

            try:
                _set_property(varset, name, expr, prop_type)
            except Exception as exc:
                write_log("WARN", f"VarSetExporter: cannot set '{name}' = '{expr}': {exc}")

        doc.recompute()


def _infer_property_type(expr: str) -> str:
    """Choose a FreeCAD property type from a raw SCAD expression string."""
    s = expr.strip()
    # Boolean literals
    if s in ("true", "false"):
        return "App::PropertyBool"
    # Integer
    if _is_int(s):
        return "App::PropertyInteger"
    # Float
    if _is_float(s):
        return "App::PropertyFloat"
    # Everything else (vectors, strings, identifiers) → string
    return "App::PropertyString"


def _is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _set_property(obj, name: str, expr: str, prop_type: str) -> None:
    s = expr.strip()
    if prop_type == "App::PropertyBool":
        setattr(obj, name, s == "true")
    elif prop_type == "App::PropertyInteger":
        setattr(obj, name, int(s))
    elif prop_type == "App::PropertyFloat":
        setattr(obj, name, float(s))
    else:
        setattr(obj, name, s)


# ---------------------------------------------------------------------------
# Stub exporters (future work)
# ---------------------------------------------------------------------------

class SpreadsheetExporter(BaseExporter):
    """Placeholder — mirrors variables to a Spreadsheet::Sheet."""

    def export(self, doc, meta: ScadMeta, label: str) -> None:
        FreeCAD.Console.PrintWarning(
            "Variable Export: Spreadsheet target is not yet implemented.\n"
        )
        write_log("WARN", "SpreadsheetExporter: not yet implemented")


class VarsExporter(BaseExporter):
    """Placeholder — exports via the Vars pluggable backend."""

    def export(self, doc, meta: ScadMeta, label: str) -> None:
        FreeCAD.Console.PrintWarning(
            "Variable Export: Vars target is not yet implemented.\n"
        )
        write_log("WARN", "VarsExporter: not yet implemented")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_EXPORTERS = {
    _TARGET_VARSET: VarSetExporter,
    _TARGET_VARS: VarsExporter,
    _TARGET_SPREADSHEET: SpreadsheetExporter,
}


def export_variables(doc, meta: ScadMeta, label: str) -> None:
    """
    Export variables from *meta* according to the current preferences.

    *label* is used to name the created object (typically the SCAD base name
    without extension, e.g. ``"my_part"``).
    """
    prefs = FreeCAD.ParamGet(_PREFS_PATH)
    target = prefs.GetInt("varExportTarget", _TARGET_VARSET)
    prompt = prefs.GetBool("varExportPrompt", True)

    if not meta.variables:
        FreeCAD.Console.PrintMessage(f"No variables found in {label}\n")
        return

    if prompt:
        # Show a simple confirmation dialog via Qt
        _confirm_and_export(doc, meta, label, target)
    else:
        _run_export(doc, meta, label, target)


def _confirm_and_export(doc, meta: ScadMeta, label: str, target: int) -> None:
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets  # FreeCAD < 0.20 fallback

    target_names = {
        _TARGET_VARSET: "VarSet",
        _TARGET_VARS: "Vars",
        _TARGET_SPREADSHEET: "Spreadsheet",
    }
    var_count = len(meta.variables)
    dest = target_names.get(target, "unknown")
    msg = (
        f"Export {var_count} variable(s) from '{label}' to {dest}?\n\n"
        + "\n".join(f"  {k} = {v}" for k, v in list(meta.variables.items())[:10])
        + ("\n  …" if var_count > 10 else "")
    )

    reply = QtWidgets.QMessageBox.question(
        None,
        "Export SCAD Variables",
        msg,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.Yes,
    )
    if reply == QtWidgets.QMessageBox.Yes:
        _run_export(doc, meta, label, target)


def _run_export(doc, meta: ScadMeta, label: str, target: int) -> None:
    exporter_cls = _EXPORTERS.get(target, VarSetExporter)
    exporter_cls().export(doc, meta, label)
