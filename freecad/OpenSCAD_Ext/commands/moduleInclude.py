class Cmd_ScadLibraryBrowser:
    def Activated(self):
        path = self.pick_library_file()
        lib = parse_scad_library(path)
        dlg = ScadLibraryDialog(lib)
        if dlg.exec_():
            self.create_module_object(dlg.selected_module, dlg.values)



def add_module_properties(self, obj):
    for arg in self.module.arguments:
        prop = "App::PropertyFloat"
        if arg.default in ("true", "false"):
            prop = "App::PropertyBool"
        elif arg.default and arg.default.startswith('"'):
            prop = "App::PropertyString"

        obj.addProperty(
            prop,
            arg.name,
            f"Module::{self.module.name}",
            arg.description
        )

        if arg.default is not None:
            setattr(obj, arg.name, convert_default(arg.default))

def build_scad_call(self, obj):
    args = []
    for arg in self.module.arguments:
        val = getattr(obj, arg.name)
        args.append(f"{arg.name}={format_scad(val)}")

    return f"{self.module.name}({', '.join(args)});"

