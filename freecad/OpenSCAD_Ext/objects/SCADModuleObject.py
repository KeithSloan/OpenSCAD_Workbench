import os
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.commands.baseSCAD import BaseParams
from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase, ViewSCADProvider


# ---------------------------------------------------------------------------
# Meta attribute helpers (new ScadMeta uses snake_case; legacy uses camelCase)
# ---------------------------------------------------------------------------

def _source_file(meta) -> str:
    return getattr(meta, "source_file", None) or getattr(meta, "sourceFile", "")


def _module_params(module) -> list:
    """Return parameter list from ScadModuleMeta (.params) or SCADModule (.arguments)."""
    return getattr(module, "params", None) or getattr(module, "arguments", [])


def _param_description(param) -> str:
    """Return description string; ScadParam has none, SCADArgument does."""
    return getattr(param, "description", "") or ""


# ---------------------------------------------------------------------------
# SCAD value conversion
# ---------------------------------------------------------------------------

def scad_value(val):
    """
    Convert a FreeCAD property value to a valid OpenSCAD value string.
    Booleans → true/false, UPPER strings → symbol, others → quoted.
    """
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        if val.isupper():
            return val
        return f'"{val}"'
    return val


# ---------------------------------------------------------------------------
# Argument / parameter processing
# ---------------------------------------------------------------------------

def build_arg_assignments(obj, module) -> str:
    """
    Build a comma-separated string of argument assignments for a SCAD module.
    Reads parameter values from FreeCAD properties on *obj*.
    """
    assignments = []
    for param in _module_params(module):
        name = param.name
        if name not in obj.PropertiesList:
            continue
        val = getattr(obj, name, None)
        if val in ("", None):
            continue
        assignments.append(f"{name}={scad_value(val)}")
    result = ", ".join(assignments)
    write_log("Info", f"Generated SCAD arguments: {result}")
    return result


def _add_parameter_property(obj, param) -> None:
    """
    Add a typed FreeCAD property to *obj* from a ScadParam / SCADArgument.
    Property type is inferred from the default value string.

    IMPORTANT: always test the type conversion *before* calling addProperty.
    If addProperty succeeds but the subsequent setattr fails, the property
    is left in an inconsistent state and the next addProperty call for the
    same name raises NameError.
    """
    name    = param.name
    default = param.default
    desc    = _param_description(param)
    section = "SCAD Parameters"

    # Bool
    if default in ("true", "false"):
        obj.addProperty("App::PropertyBool", name, section, desc)
        setattr(obj, name, default == "true")
        return

    # Integer – only attempt if the string looks like a plain integer
    if default is not None and "." not in str(default):
        try:
            ival = int(default)
            obj.addProperty("App::PropertyInteger", name, section, desc)
            setattr(obj, name, ival)
            return
        except (ValueError, TypeError):
            pass

    # Float
    if default is not None:
        try:
            fval = float(default)
            obj.addProperty("App::PropertyFloat", name, section, desc)
            setattr(obj, name, fval)
            return
        except (ValueError, TypeError):
            pass

    # String fallback (covers SCAD identifiers like BOTTOM, UP, etc.)
    obj.addProperty("App::PropertyString", name, section, desc)
    if default is not None:
        setattr(obj, name, str(default).strip('"'))


# ---------------------------------------------------------------------------
# SCAD import-line generation
# ---------------------------------------------------------------------------

def generate_scad_import_lines(meta) -> list:
    """
    Generate ``include <...>`` / ``use <...>`` lines for a generated SCAD file.

    Priority:
      1. comment_includes + includes → ``include <…>``
      2. none found → ``use <./<library-relative-path>>``
    """
    # Merge and deduplicate comment + regular includes
    seen: set = set()
    includes = []
    for inc in list(getattr(meta, "comment_includes", [])) + list(getattr(meta, "includes", [])):
        clean = inc.lstrip("/ ").strip()
        if clean and clean not in seen:
            seen.add(clean)
            includes.append(clean)

    if includes:
        return [f"include <{inc}>" for inc in includes]

    # Fallback: use importPaths set by _finalize_meta_imports, or derive from source
    import_paths = getattr(meta, "importPaths", None)
    if import_paths:
        return [f"use <{p}>" for p in import_paths]

    # Last resort: derive relative path heuristically
    src = _source_file(meta).replace(os.sep, "/")
    parts = src.split("/libraries/", 1)
    rel = "./" + (parts[1] if len(parts) == 2 else os.path.basename(src))
    return [f"use <{rel}>"]


# ---------------------------------------------------------------------------
# SCAD file writer
# ---------------------------------------------------------------------------

def write_scad_file(obj, module, meta) -> None:
    """
    Write a minimal SCAD file that imports a library and calls *module*.
    """
    module_name       = module.name.strip("()")
    params            = _module_params(module)
    args_declaration  = ", ".join(p.name for p in params)
    args_values       = build_arg_assignments(obj, module)

    try:
        os.makedirs(os.path.dirname(obj.Proxy.sourceFile), exist_ok=True)
        with open(obj.Proxy.sourceFile, "w", encoding="utf-8") as fp:
            write_log("Info", f"Writing SCAD file: {obj.Proxy.sourceFile}")

            for line in generate_scad_import_lines(meta):
                print(f"{line};", file=fp)

            print("", file=fp)
            print(f"// module {module_name}({args_declaration});", file=fp)
            print(f"{module_name}({args_values});", file=fp)

            write_log("Info", f"Module '{module_name}' written with args: {args_values}")

    except Exception as exc:
        write_log("Error", f"Failed to write SCAD file {obj.Proxy.sourceFile}: {exc}")


# ---------------------------------------------------------------------------
# SCADModuleObject
# ---------------------------------------------------------------------------

class SCADModuleObject(SCADfileBase):
    """
    FreeCAD FeaturePython proxy for a single OpenSCAD module instantiation.
    Works with both the new :class:`ScadMeta` / :class:`ScadModuleMeta` and
    the legacy ``SCADMeta`` / ``SCADModule`` objects.
    """

    def __init__(self, obj, name, source_file, meta, module, args):
        super().__init__(obj, self.clean_module_name(name), source_file)

        self.Object = obj
        self.meta   = meta
        self.module = module
        self.args   = args
        obj.Proxy   = self

        write_log("INFO", f"library scad file  : {_source_file(meta)}")
        write_log("INFO", f"includes           : {meta.includes}")
        write_log("INFO", f"module             : {module.name}")
        write_log("INFO", f"args               : {repr(args)}")

        self._init_module_properties(obj)
        self.add_params_as_properties(obj)
        self._prepare_scad_file(obj)
        self.renderFunction(obj)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def clean_module_name(self, name: str) -> str:
        return name[:-2] if name.endswith("()") else name

    def _init_module_properties(self, obj) -> None:
        """Add module-specific properties (called after the base SCADfileBase properties)."""
        obj.addProperty(
            "App::PropertyString", "ModuleName", "Parameters", "OpenSCAD module name"
        ).ModuleName = self.module.name

        obj.addProperty(
            "App::PropertyString", "Description", "Parameters", "Module description"
        ).Description = getattr(self.module, "description", "")

        obj.setEditorMode("Description", 1)

    def add_params_as_properties(self, obj) -> None:
        """Add all module parameters as typed FreeCAD properties."""
        for param in _module_params(self.module):
            _add_parameter_property(obj, param)

    def _build_arg_assignments(self, obj) -> str:
        return build_arg_assignments(obj, self.module)

    def _prepare_scad_file(self, obj) -> None:
        scad_dir = BaseParams.getScadSourcePathOrDefault()
        obj.Proxy.sourceFile = os.path.join(scad_dir, obj.Name + ".scad")
        os.makedirs(scad_dir, exist_ok=True)
        write_scad_file(obj, self.module, self.meta)

    def execute(self, obj) -> None:
        pass
