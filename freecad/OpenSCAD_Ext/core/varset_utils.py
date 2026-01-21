# varset_utils.py
#
# Utilities for mapping OpenSCAD variables into FreeCAD objects
# and optionally mirroring them into a Spreadsheet

import FreeCAD


def add_scad_vars_to_varset(obj, variables: dict):
    """
    Attach SCAD variables as App::PropertyString properties
    to the given FeaturePython object.

    Args:
        obj: Part::FeaturePython
        variables: dict(name -> value)
    """
    if not obj or not variables:
        return

    for name, value in variables.items():
        if not hasattr(obj, name):
            try:
                obj.addProperty(
                    "App::PropertyString",
                    name,
                    "SCAD Variables",
                    f"SCAD variable {name}"
                )
            except Exception:
                continue

        try:
            setattr(obj, name, str(value))
        except Exception:
            pass


def mirror_varset_to_spreadsheet(doc, variables: dict, sheet_name="SCAD_Variables"):
    """
    Mirror SCAD variables into a FreeCAD Spreadsheet.

    Args:
        doc: FreeCAD document
        variables: dict(name -> value)
        sheet_name: Spreadsheet object name
    """
    if not doc or not variables:
        return None

    sheet = None

    # Reuse existing spreadsheet if present
    for obj in doc.Objects:
        if obj.TypeId == "Spreadsheet::Sheet" and obj.Name == sheet_name:
            sheet = obj
            break

    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)

    row = 1
    for name, value in variables.items():
        try:
            sheet.set(f"A{row}", name)
            sheet.set(f"B{row}", str(value))
        except Exception:
            pass
        row += 1

    return sheet

