# varset_utils.py
#
# Utilities for mapping OpenSCAD variables into FreeCAD objects.

import FreeCAD


def create_varset(doc, variables: dict, descriptions: dict = None,
                  name: str = "SCAD_Variables") -> object:
    """
    Create (or update) an App::VarSet named *name* in *doc* and populate it
    with typed properties derived from *variables* (name -> expr string).

    *descriptions* (name -> str) is used as the property tooltip when provided.

    Returns the VarSet object.
    """
    if descriptions is None:
        descriptions = {}

    varset = doc.getObject(name)
    if varset is None:
        varset = doc.addObject("App::VarSet", name)
        varset.Label = name

    for var_name, expr in variables.items():
        desc = descriptions.get(var_name, f"SCAD variable {var_name}")
        prop_type = _infer_property_type(expr)

        if not hasattr(varset, var_name):
            try:
                varset.addProperty(prop_type, var_name, "SCAD Variables", desc)
            except Exception:
                continue

        try:
            _set_property(varset, var_name, expr, prop_type)
        except Exception:
            pass

    return varset


def _infer_property_type(expr: str) -> str:
    s = expr.strip()
    if s in ("true", "false"):
        return "App::PropertyBool"
    try:
        int(s)
        return "App::PropertyInteger"
    except ValueError:
        pass
    try:
        float(s)
        return "App::PropertyFloat"
    except ValueError:
        pass
    return "App::PropertyString"


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
# Legacy helpers (kept for backwards compatibility)
# ---------------------------------------------------------------------------

def add_scad_vars_to_varset(obj, variables: dict):
    """
    Attach SCAD variables as App::PropertyString properties to a
    Part::FeaturePython object.  Prefer create_varset() for new code.
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
                    f"SCAD variable {name}",
                )
            except Exception:
                continue
        try:
            setattr(obj, name, str(value))
        except Exception:
            pass


def mirror_varset_to_spreadsheet(doc, variables: dict, sheet_name="SCAD_Variables"):
    """
    Mirror SCAD variables into a Spreadsheet::Sheet.
    """
    if not doc or not variables:
        return None

    sheet = None
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
