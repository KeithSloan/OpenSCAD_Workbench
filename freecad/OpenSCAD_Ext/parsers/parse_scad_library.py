def parse_scad_library(path) -> ScadLibrary:
    lib = ScadLibrary()
    current_module = None
    section = None

    for line in open(path, encoding="utf-8"):
        s = line.strip()

        if s.startswith("// LibFile:"):
            lib.filename = s.split(":", 1)[1].strip()

        elif s.startswith("// Includes:"):
            section = "includes"

        elif s.startswith("// Module:"):
            current_module = ScadModule()
            current_module.name = extract_module_name(s)
            lib.modules.append(current_module)

        elif s.startswith("module ") and current_module:
            current_module.signature = s

        elif s.startswith("// Synopsis:"):
            current_module.synopsis = s.split(":",1)[1].strip()

        elif s.startswith("// Usage:"):
            section = "usage"

        elif s.startswith("// Arguments:"):
            section = "args"

        elif s.startswith("// ---"):
            section = "args_optional"

        elif s.startswith("//") and section == "args":
            parse_argument_line(current_module, s)

        elif s.startswith("//") and section == "usage":
            current_module.usage += s[2:].strip() + "\n"

    return lib

