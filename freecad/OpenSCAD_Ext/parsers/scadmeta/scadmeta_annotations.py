# scadmeta_parser.py

import re
import os
import FreeCAD
import FreeCADGui
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

# Regex patterns
var_re = re.compile(
    r"""
    (?:\/\/\s*@var\s+)?      # optional // @var
    ([A-Za-z_]\w*)           # variable name
    \s*=\s*
    ([^;]+)                  # expression up to semicolon
    ;
    """,
    re.VERBOSE
)

module_re = re.compile(r"//\s*@module\s+([A-Za-z_]\w*)")
include_re = re.compile(r"//\s*@include\s+(.+)")
use_re = re.compile(r"//\s*@use\s+(.+)")

class ScadMeta:
    def __init__(self):
        self.vars = {}  # name -> value
        self.variable_sets = {}  # set_name -> {name -> value}
        self.modules = []
        self.includes = []
        self.uses = []

def parse_scad_meta(scad_filepath):
    """
    Parse a SCAD file and extract variables, variable sets, modules, includes, uses.
    """
    meta = ScadMeta()
    try:
        if not os.path.exists(scad_filepath):
            write_log("SCADMETA", f"SCAD file not found: {scad_filepath}")
            return meta

        with open(scad_filepath, 'r') as f:
            scad_lines = f.readlines()

        current_set = None

        for line in scad_lines:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('//'):
                pass

            # Match variable sets: e.g., // @set setname
            elif line.startswith('// @set '):
                set_name = line[8:].strip()
                current_set = set_name
                meta.variable_sets[current_set] = {}
                continue

            # Match variables
            m = var_re.match(line)
            if m:
                var_name, var_val = m.groups()
                if current_set:
                    meta.variable_sets[current_set][var_name] = var_val.strip()
                else:
                    meta.vars[var_name] = var_val.strip()
                continue

            # Match modules
            m = module_re.match(line)
            if m:
                meta.modules.append(m.group(1))
                continue

            # Match includes
            m = include_re.match(line)
            if m:
                meta.includes.append(m.group(1).strip())
                continue

            # Match uses
            m = use_re.match(line)
            if m:
                meta.uses.append(m.group(1).strip())
                continue

    except Exception as e:
        write_log("SCADMETA", f"Failed to parse SCAD meta for {scad_filepath}: {e}")

    write_log("SCADMETA", f"Parsed SCAD file {scad_filepath}, Vars: {list(meta.vars.keys())}, Sets: {list(meta.variable_sets.keys())}")
    return meta

def _convert_value(val):
    """Convert numeric-looking strings to numbers; keep others as strings."""
    val = val.strip()
    try:
        # Try integer
        if '.' not in val:
            return int(val)
        # Try float
        return float(val)
    except ValueError:
        return val  # keep as string if not numeric


def create_scad_vars_spreadsheet(doc, meta, name="Vars_SCAD"):
    """
    Create (or reuse) a Vars-compatible Spreadsheet variable set
    from parsed SCAD metadata.

    Layout:
        Column A : Variable name
        Column B : Default value
        Column C.. : Variable sets
    """

    if doc is None:
        raise RuntimeError("No active FreeCAD document")

    # ------------------------------------------------------------------
    # Create or reuse spreadsheet
    # ------------------------------------------------------------------
    if hasattr(doc, name):
        sheet = getattr(doc, name)
    else:
        sheet = doc.addObject("Spreadsheet::Sheet", name)
        sheet.Label = name

    # ------------------------------------------------------------------
    # Headers (use expressions to avoid leading apostrophe)
    # ------------------------------------------------------------------
    sheet.set("A1", '="Name"')
    sheet.set("B1", '="Default"')

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    var_names = list(meta.vars.keys())
    row = 2

    for var in var_names:
        sheet.set(f"A{row}", f'="{var}"')
        sheet.set(f"B{row}", str(meta.vars[var]))
        row += 1

    # ------------------------------------------------------------------
    # Variable sets (optional)
    # ------------------------------------------------------------------
    if hasattr(meta, "sets") and meta.sets:
        col_index = 2  # Column C

        for set_name, set_vars in meta.sets.items():
            col_letter = chr(ord("A") + col_index)

            # Set header
            sheet.set(f"{col_letter}1", f'="{set_name}"')

            row = 2
            for var in var_names:
                if var in set_vars:
                    sheet.set(f"{col_letter}{row}", str(set_vars[var]))
                row += 1

            col_index += 1

    doc.recompute()
    return sheet

