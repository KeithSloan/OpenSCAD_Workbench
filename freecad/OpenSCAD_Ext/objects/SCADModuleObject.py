import os
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider

# -----------------------------
# Utility functions
# -----------------------------

def scad_value(val):
    """
    Convert a FreeCAD property value to a valid OpenSCAD value.
    Booleans -> true/false
    Uppercase symbols -> leave as-is
    Strings -> quoted
    Numbers -> as-is
    """
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        if val.isupper():  # treat as OpenSCAD symbol
            return val
        return f'"{val}"'
    return val


def build_arg_assignments(obj, module):
    """
    Build a comma-separated string of argument assignments for a SCAD module.
    """
    assignments = []
    for arg in getattr(module, "arguments", []):
        name = arg.name
        if name not in obj.PropertiesList:
            continue
        val = getattr(obj, name, None)
        if val in ("", None):
            continue
        assignments.append(f"{name}={scad_value(val)}")
    result = ", ".join(assignments)
    write_log("Info", f"Generated SCAD arguments: {result}")
    return result

import os

def generate_scad_import_lines(meta):
    """
    Generate SCAD import lines.

    Priority:
      1. comment_includes + includes → include <...>
      2. none found → use <./<library_root>/.../file.scad>
    """
    lines = []

    # --- Clean comment includes (strip //) ---
    comment_includes = [
        line.lstrip("/ ").strip()
        for line in getattr(meta, "comment_includes", [])
    ]

    # --- Merge and dedupe includes ---
    all_includes = comment_includes + getattr(meta, "includes", [])
    seen = set()
    includes = []
    for inc in all_includes:
        if inc and inc not in seen:
            seen.add(inc)
            includes.append(inc)

    # --- Case 1: explicit includes exist ---
    if includes:
        for inc in includes:
            lines.append(f"include <{inc}>")
        return lines

    # --- Case 2: fallback → library-relative use ---
    src = meta.sourceFile.replace(os.sep, "/")

    # Heuristic: libraries/<libname>/...
    parts = src.split("/libraries/", 1)
    if len(parts) == 2:
        rel_path = "./" + parts[1]
    else:
        # Fallback: just the filename
        rel_path = "./" + os.path.basename(src)

    lines.append(f"use <{rel_path}>")
    return lines


def write_scad_file(obj, module, meta):
    """
    Write a SCAD file from a FreeCAD object and SCAD module meta.
    """
    module_name = module.name.strip("()")
    args_names = [arg.name for arg in module.arguments]
    args_declaration = ", ".join(args_names)
    args_values = build_arg_assignments(obj, module)

    try:
        os.makedirs(os.path.dirname(obj.Proxy.sourceFile), exist_ok=True)
        with open(obj.Proxy.sourceFile, "w", encoding="utf-8") as fp:
            write_log("Info", f"Writing SCAD file: {obj.Proxy.sourceFile}")

            # --- Import lines ---
            for line in generate_scad_import_lines(meta):
                print(f"{line};", file=fp)

            print("", file=fp)

            # --- Module declaration as comment ---
            print(f"// module {module_name}({args_declaration});", file=fp)

            # --- Module call ---
            print(f"{module_name}({args_values});", file=fp)

            write_log(
                "Info",
                f"Module '{module_name}' written with args: {args_values}"
            )

    except Exception as e:
        write_log(
            "Error",
            f"Failed to write SCAD file {obj.Proxy.sourceFile}: {e}"
        )


def _add_argument_property(obj, arg):
    """
    Add a typed property to a FreeCAD object from a SCADArgument.
    """
    name = arg.name
    default = arg.default
    desc = arg.description
    subsection = "SCAD Parameters"

    # Boolean
    if default in ("true", "false"):
        prop = obj.addProperty("App::PropertyBool", name, subsection, desc)
        setattr(obj, name, default == "true")
        return

    # Integer
    try:
        if default is not None and "." not in str(default):
            ival = int(default)
            prop = obj.addProperty("App::PropertyInteger", name, subsection, desc)
            setattr(obj, name, ival)
            return
    except Exception:
        pass

    # Float
    try:
        fval = float(default)
        prop = obj.addProperty("App::PropertyFloat", name, subsection, desc)
        setattr(obj, name, fval)
        return
    except Exception:
        pass

    # String fallback
    prop = obj.addProperty("App::PropertyString", name, subsection, desc)
    if default:
        setattr(obj, name, str(default).strip('"'))


# -----------------------------
# SCADModuleObject Class
# -----------------------------

class SCADModuleObject(SCADfileBase):
    def __init__(self, obj, name, sourceFile, meta, module, args):
        super().__init__(obj, self.clean_module_name(name), sourceFile)

        self.Object = obj
        self.meta = meta
        self.module = module
        self.args = args
        obj.Proxy = self

        write_log("INFO", f"library scad file {meta.sourceFile}")
        write_log("INFO", f"includes {meta.includes}")
        write_log("INFO", f"modules {module.name}")
         # Causes JSON error write_log("INFO", f"args {args}")
        write_log("INFO", f"args {repr(args)}")

        self._init_properties(obj)
        self.add_args_as_properties(obj)
        self._prepare_scad_file(obj)
        self.renderFunction(obj)

    # -----------------------------
    # SCADModuleObject methods
    # -----------------------------
    def clean_module_name(self, name: str) -> str:
        return name[:-2] if name.endswith("()") else name

    def _init_properties(self, obj):
        """
        Initialize base properties like ModuleName and Description
        """
        obj.addProperty("App::PropertyString", "ModuleName", "Parameters", "OpenSCAD module name").ModuleName = self.module.name
        obj.addProperty("App::PropertyString", "Description", "Parameters", "Module description").Description = getattr(self.module, "description", "")
        obj.setEditorMode("Description", 1)

    def add_args_as_properties(self, obj):
        """
        Add all module arguments as FreeCAD properties (typed as string).
        """
        for arg in getattr(self.module, "arguments", []):
            _add_argument_property(obj, arg)

    def _build_arg_assignments(self, obj):
        """
        Build a comma-separated string of argument assignments for this object/module.
        """
        return build_arg_assignments(obj, self.module)

    def _prepare_scad_file(self, obj):
        """
        Prepare source file path and write initial SCAD file with includes and module call.
        """
        scad_dir = BaseParams.getScadSourcePath()
        obj.Proxy.sourceFile = os.path.join(scad_dir, obj.Name + ".scad")
        os.makedirs(scad_dir, exist_ok=True)
        write_scad_file(obj, self.module, self.meta)

    def execute(self, obj):
        """
        Hook for OpenSCAD execution (can be implemented later).
        """
        pass

