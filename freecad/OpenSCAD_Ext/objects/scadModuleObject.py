from freecad.OpenSCAD_Ext.objects.SCADObject import SCADfileBase 

class SCADModuleObject(SCADfileBase):
    def __init__(self, obj, meta, module):
        self.Object = obj
        obj.Proxy = self

        self._init_properties(obj, meta, module)
        self._set_defaults(obj, module)

    def _init_properties(self, obj, meta, module):
        # --- Parameters group ---
        obj.addProperty(
            "App::PropertyString",
            "ModuleName",
            "Parameters",
            "OpenSCAD module name"
        ).ModuleName = module["name"]

        obj.addProperty(
            "App::PropertyString",
            "Description",
            "Parameters",
            "Module description"
        ).Description = module.get("description", "")

        obj.setEditorMode("Description", 1)

        obj.addProperty(
            "App::PropertyString",
            "Usage",
            "Parameters",
            "Usage examples"
        ).Usage = "\n".join(module.get("usage", []))

        obj.setEditorMode("Usage", 1)

        # Collect argument documentation
        arg_info = []
        for arg in module.get("arguments", []):
            line = arg["name"]
            if arg.get("description"):
                line += " – " + arg["description"]
            arg_info.append(line)

        obj.addProperty(
            "App::PropertyString",
            "ArgumentsInfo",
            "Parameters",
            "Argument documentation"
        ).ArgumentsInfo = "\n".join(arg_info)

        obj.setEditorMode("ArgumentsInfo", 1)

        # --- SCAD group ---
        obj.addProperty(
            "App::PropertyStringList",
            "Includes",
            "SCAD",
            "Required include files"
        ).Includes = meta.get("includes", [])

        obj.addProperty(
            "App::PropertyString",
            "Source",
            "SCAD",
            "Generated OpenSCAD source"
        )

        obj.setEditorMode("Source", 1)

        # --- Add module parameters dynamically ---
        for arg in module.get("arguments", []):
            name = arg["name"]
            default = arg.get("default")

            prop = obj.addProperty(
                "App::PropertyString",
                name,
                "Parameters",
                "Module parameter"
            )

            if default is not None:
                setattr(obj, name, str(default))

    def _set_defaults(self, obj, module):
        obj.ModuleName = module["name"]

    def execute(self, obj):
        src = self._build_scad_source(obj)
        obj.Source = src

        # Hook to existing OpenSCAD execution
        # run_openscad(obj, src)

    def _build_scad_source(self, obj):
        lines = []

        for inc in obj.Includes:
            lines.append(f'include <{inc}>;')

        lines.append("")
        lines.append(f"{obj.ModuleName}(")

        args = []
        for prop in obj.PropertiesList:
            if obj.getGroupOfProperty(prop) != "Parameters":
                continue
            if prop in (
                "ModuleName",
                "Description",
                "ArgumentsInfo",
                "Usage",
            ):
                continue

            val = getattr(obj, prop)
            if val != "":
                args.append(f"    {prop} = {val}")

        lines.append(",\n".join(args))
        lines.append(");")

        return "\n".join(lines)
def _add_argument_property(self, obj, arg):
    name = arg["name"]
    default = arg.get("default")
    desc = arg.get("description", "")

    # Boolean
    if default in ("true", "false"):
        prop = obj.addProperty(
            "App::PropertyBool",
            name,
            "Parameters",
            desc
        )
        setattr(obj, name, default == "true")
        return

    # Integer
    try:
        if default is not None and "." not in str(default):
            ival = int(default)
            prop = obj.addProperty(
                "App::PropertyInteger",
                name,
                "Parameters",
                desc
            )
            setattr(obj, name, ival)
            return
    except Exception:
        pass

    # Float
    try:
        fval = float(default)
        prop = obj.addProperty(
            "App::PropertyFloat",
            name,
            "Parameters",
            desc
        )
        setattr(obj, name, fval)
        return
    except Exception:
        pass

    # String fallback
    prop = obj.addProperty(
        "App::PropertyString",
        name,
        "Parameters",
        desc
    )
    if default:
        setattr(obj, name, str(default).strip('"'))

