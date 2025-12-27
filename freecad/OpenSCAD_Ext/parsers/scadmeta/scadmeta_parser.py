from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
import FreeCAD
import re

# ============================================================
# Helper: safe spreadsheet write
# ============================================================
def safe_set(sheet, row, col, value):
    """
    Safely write to a FreeCAD spreadsheet cell.
    col: 1=A, 2=B, ...
    value: always converted to string
    """
    try:
        col_letter = ""
        c = col
        while c > 0:
            c, r = divmod(c - 1, 26)
            col_letter = chr(65 + r) + col_letter
        cell = f"{col_letter}{row}"
        sheet.set(cell, str(value))  # always string
        write_log("INFO", f"Set cell {cell} = '{value}'")
    except Exception as e:
        write_log("ERROR", f"Failed to write {value} to {cell}: {e}")

# ============================================================
# SCAD META PARSER
# ============================================================
def parse_scad_meta(file_path):
    """
    Parse SCAD file and return:
      - globals_vars: dict {var_name: expression}
      - globals_sets: list of set names
      - modules: dict {module_name: [param1, param2, ...]}
    """
    with open(file_path, "r") as f:
        text = f.read()

    # Regex to find modules and parameters
    module_re = re.compile(
        r'^\s*module\s+(\w+)\s*\((.*?)\)\s*{',
        re.MULTILINE | re.DOTALL
    )

    # Global variable assignments
    var_assign_re = re.compile(r'^\s*(\w+)\s*=\s*([^;\[]+);', re.MULTILINE)
    set_re = re.compile(r'^\s*(\w+)\s*=\s*\[.*?\];', re.MULTILINE)

    first_module = module_re.search(text)
    if first_module:
        global_text = text[:first_module.start()]
    else:
        global_text = text

    globals_vars = {name: expr.strip() for name, expr in var_assign_re.findall(global_text)}
    globals_sets = set_re.findall(global_text)

    # Modules and parameters
    modules = {}
    for m in module_re.finditer(text):
        mod_name = m.group(1)
        params_text = m.group(2)
        params = [p.strip().split('=')[0].strip() for p in params_text.split(',') if p.strip()]
        modules[mod_name] = params

    return globals_vars, globals_sets, modules

# ============================================================
# CREATE SPREADSHEETS
# ============================================================
def varsSCAD(obj):
    """
    Create spreadsheets:
      1) Globals sheet: Name | Expression | Evaluated | Type
      2) Modules sheet: ModuleName in column A, parameters in B,C,...
    Logging via write_log only.
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument("SCAD_Vars")

    scad_file = obj.sourceFile
    write_log("EDIT", f"Parsing SCAD file: {scad_file}")

    globals_vars, globals_sets, modules = parse_scad_meta(scad_file)

    # ----------------------------
    # 1) Global variables sheet
    # ----------------------------
    sheet_name = "Vars___global__"
    sheet = doc.getObject(sheet_name)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
        write_log("INFO", f"Creating spreadsheet '{sheet_name}'")

    # Header
    safe_set(sheet, 1, 1, "Name")
    safe_set(sheet, 1, 2, "Value Expression")
    safe_set(sheet, 1, 3, "Value Evaluated")
    safe_set(sheet, 1, 4, "Type")
    row = 2

    eval_dict = {}
    for var, expr in globals_vars.items():
        try:
            value = str(eval(expr, {}, eval_dict))
            eval_dict[var] = float(value) if value.replace('.', '', 1).isdigit() else value
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

    # ----------------------------
    # 2) Modules sheet
    # ----------------------------
    sheet_name = "Modules"
    sheet = doc.getObject(sheet_name)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
        write_log("INFO", f"Creating spreadsheet '{sheet_name}'")

    # Header
    safe_set(sheet, 1, 1, "ModuleName")
    row = 2

    for mod_name, params in modules.items():
        safe_set(sheet, row, 1, mod_name)
        for i, param in enumerate(params):
            safe_set(sheet, row, 2 + i, param)
        row += 1

    doc.recompute()
    if FreeCAD.GuiUp:
        FreeCAD.Gui.updateGui()

    write_log("INFO", f"✅ SCAD globals and module parameters captured for {obj.Name}")

