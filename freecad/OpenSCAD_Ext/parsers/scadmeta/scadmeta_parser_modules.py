from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import FreeCAD
import re

# ============================================================
# Helper: safe spreadsheet write (FreeCAD-version tolerant)
# ============================================================
def safe_set(sheet, row, col, value):
    try:
        col_letter = ""
        c = col
        while c > 0:
            c, r = divmod(c - 1, 26)
            col_letter = chr(65 + r) + col_letter
        sheet.set(f"{col_letter}{row}", str(value))
    except Exception as e:
        write_log("ERROR", f"Spreadsheet set failed ({row},{col}): {e}")

# ============================================================
# SCAD META PARSER
# ============================================================
def parse_scad_meta(file_path):
    """
    Parse SCAD file and return:
      {
        "__global__": {
            "vars": [...],
            "exprs": {var: expr},
            "sets": []
        },
        "module_name": {
            "vars": [...],
            "exprs": {var: expr},
            "sets": []
        }
      }
    """
    with open(file_path, "r") as f:
        text = f.read()

    module_re = re.compile(
        r'^\s*module\s+(\w+)\s*\((.*?)\)\s*{',
        re.MULTILINE | re.DOTALL
    )
    assign_re = re.compile(
        r'^\s*(\w+)\s*=\s*([^;]+);',
        re.MULTILINE
    )

    meta = {}

    # -------------------------------
    # GLOBAL VARIABLES
    # -------------------------------
    global_text = module_re.split(text)[0]
    global_exprs = dict(assign_re.findall(global_text))

    meta["__global__"] = {
        "vars": list(global_exprs.keys()),
        "exprs": global_exprs,
        "sets": []
    }

    # -------------------------------
    # MODULES
    # -------------------------------
    for m in module_re.finditer(text):
        name = m.group(1)

        # --- parameters ---
        param_exprs = {}
        for p in m.group(2).split(","):
            p = p.strip()
            if not p:
                continue
            if "=" in p:
                k, v = p.split("=", 1)
                param_exprs[k.strip()] = v.strip()
            else:
                param_exprs[p] = ""

        # --- module body ---
        start = m.end()
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start:i - 1]

        body_exprs = dict(assign_re.findall(body))

        exprs = {}
        exprs.update(param_exprs)
        exprs.update(body_exprs)

        meta[name] = {
            "vars": list(exprs.keys()),
            "exprs": exprs,
            "sets": []
        }

    return meta

# ============================================================
# MAIN ENTRY POINT (CALLED BY COMMAND)
# ============================================================
def varsSCAD(obj):
    """
    Called by VarsSCADFileObject_CMD.
    Creates Vars_* spreadsheets with:
    Name | Value Expression | Value Evaluated | Type
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument("SCAD_Vars")

    scad_file = obj.sourceFile
    write_log("EDIT", f"Parsing SCAD file: {scad_file}")

    meta = parse_scad_meta(scad_file)

    def eval_expr(expr, scope):
        try:
            return str(eval(expr, {}, scope))
        except Exception:
            return ""

    for module_name, mod_data in meta.items():
        sheet_name = f"Vars_{module_name}"
        sheet = doc.getObject(sheet_name)

        if sheet is None:
            sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
            write_log("INFO", f"Creating new spreadsheet '{sheet_name}'")

        # clear existing content safely
        try:
            sheet.clear()
        except Exception:
            pass

        # header
        safe_set(sheet, 1, 1, "Name")
        safe_set(sheet, 1, 2, "Value Expression")
        safe_set(sheet, 1, 3, "Value Evaluated")
        safe_set(sheet, 1, 4, "Type")

        row = 2
        eval_scope = {}

        for var in mod_data.get("vars", []):
            expr = mod_data.get("exprs", {}).get(var, "")
            value = eval_expr(expr, eval_scope)

            if value:
                try:
                    eval_scope[var] = float(value)
                except Exception:
                    pass

            safe_set(sheet, row, 1, var)
            safe_set(sheet, row, 2, expr)
            safe_set(sheet, row, 3, value)
            safe_set(sheet, row, 4, "Variable")
            row += 1

    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCAD.Gui.updateGui()

    write_log("INFO", f"SCAD variables extracted for {obj.Name}")

