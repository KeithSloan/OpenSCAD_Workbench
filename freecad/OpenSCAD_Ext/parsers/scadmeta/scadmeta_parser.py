"""
scadmeta_parser – backward-compatible shim used by varsSCAD and createSpreadSheet.

``parse_scad_meta(path)`` previously returned ``(globals_vars, globals_sets, modules)``.
It now delegates to the new Lark-based scanner and returns the same 3-tuple so
existing callers continue to work unchanged.

The :func:`create_scad_vars_spreadsheet` function is kept here and updated to
use the new :class:`~freecad.OpenSCAD_Ext.parsers.scadmeta.ScadMeta` structure.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import FreeCAD                                        # type: ignore
import FreeCADGui                                     # type: ignore

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, ScadMeta


# ---------------------------------------------------------------------------
# Public helpers used by spreadsheet creation code
# ---------------------------------------------------------------------------

def safe_set(sheet, row: int, col: int, value) -> None:
    """Set a spreadsheet cell, converting column index to letter."""
    col_letter = chr(ord("A") + col - 1)
    cell_ref = f"{col_letter}{row}"
    try:
        sheet.set(cell_ref, f'="{value}"' if isinstance(value, str) else str(value))
    except Exception as exc:
        write_log("Warning", f"safe_set({cell_ref}={value!r}): {exc}")


# ---------------------------------------------------------------------------
# Legacy 3-tuple API
# ---------------------------------------------------------------------------

def parse_scad_meta(scad_filepath: str) -> Tuple[Dict[str, str], List[str], Dict[str, List[str]]]:
    """
    Parse *scad_filepath* and return ``(globals_vars, globals_sets, modules)``.

    ============  ===============================================================
    globals_vars  ``dict`` mapping variable name → raw expression string
    globals_sets  ``list`` of ``@set`` set names (legacy concept; empty for now)
    modules       ``dict`` mapping module name → list of parameter name strings
    ============  ===============================================================
    """
    if not os.path.exists(scad_filepath):
        write_log("SCADMETA", f"SCAD file not found: {scad_filepath}")
        return {}, [], {}

    meta: ScadMeta = scan_scad_file(scad_filepath)

    globals_vars: Dict[str, str] = dict(meta.variables)
    globals_sets: List[str] = []  # legacy @set concept is not used in new parser
    modules: Dict[str, List[str]] = {
        m.name: [p.name for p in m.params]
        for m in meta.modules
    }

    write_log(
        "SCADMETA",
        f"Parsed {scad_filepath}: "
        f"vars={list(globals_vars.keys())}  "
        f"modules={list(modules.keys())}  "
        f"type={meta.file_type.value}"
    )
    return globals_vars, globals_sets, modules


# ---------------------------------------------------------------------------
# Spreadsheet creation
# ---------------------------------------------------------------------------

def create_scad_vars_spreadsheet(doc, obj) -> None:
    """
    Create FreeCAD spreadsheets for SCAD global variables and module parameters.

    Sheets created/updated:
        Vars___global__  – variable name / expression / evaluated value / type
        Modules          – module name + parameter names
    """
    scad_file = getattr(obj, "sourceFile", None) or getattr(obj, "SourceFile", None)
    if not scad_file:
        write_log("ERROR", "create_scad_vars_spreadsheet: no sourceFile on object")
        return

    globals_vars, globals_sets, modules = parse_scad_meta(scad_file)

    # ------------------------------------------------------------------
    # 1) Global variables sheet
    # ------------------------------------------------------------------
    sheet_name = "Vars___global__"
    sheet = doc.getObject(sheet_name)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
        write_log("INFO", f"Creating spreadsheet '{sheet_name}'")

    safe_set(sheet, 1, 1, "Name")
    safe_set(sheet, 1, 2, "Value Expression")
    safe_set(sheet, 1, 3, "Value Evaluated")
    safe_set(sheet, 1, 4, "Type")
    row = 2

    eval_dict: Dict = {}
    for var, expr in globals_vars.items():
        try:
            value = str(eval(expr, {}, eval_dict))  # noqa: S307
            eval_dict[var] = float(value) if value.replace(".", "", 1).lstrip("-").isdigit() else value
        except Exception:
            value = ""
        safe_set(sheet, row, 1, var)
        safe_set(sheet, row, 2, expr)
        safe_set(sheet, row, 3, value)
        safe_set(sheet, row, 4, "Variable")
        row += 1

    for s in globals_sets:
        safe_set(sheet, row, 1, s)
        safe_set(sheet, row, 2, "")
        safe_set(sheet, row, 3, "")
        safe_set(sheet, row, 4, "Set")
        row += 1

    # ------------------------------------------------------------------
    # 2) Modules sheet
    # ------------------------------------------------------------------
    sheet_name = "Modules"
    sheet = doc.getObject(sheet_name)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
        write_log("INFO", f"Creating spreadsheet '{sheet_name}'")

    safe_set(sheet, 1, 1, "ModuleName")
    row = 2
    for mod_name, params in modules.items():
        safe_set(sheet, row, 1, mod_name)
        for i, param in enumerate(params):
            safe_set(sheet, row, 2 + i, param)
        row += 1

    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCADGui.updateGui()

    write_log("INFO", f"SCAD globals and module parameters captured for {obj.Name}")
