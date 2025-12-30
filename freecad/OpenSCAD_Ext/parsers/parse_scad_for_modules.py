# parse_scad_for_modules.py

import re
from collections import namedtuple
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

# --- Data Classes ---
class SCADArgument:
    def __init__(self, name, default=None, description=None):
        self.name = name
        self.default = default
        self.description = description

class SCADModule:
    def __init__(self, name):
        self.name = name
        self.description = ""
        self.usage = []
        self.arguments = []

class SCADMeta:
    def __init__(self, fileName):
        self.fileName = fileName
        self.includes = []          # Includes in the file
        self.comment_includes = []  # Includes found in file header comments
        self.modules = []           # List of SCADModule objects


# --- Helper functions ---
def _parse_includes(lines):
    includes = []
    for line in lines:
        m = re.match(r'^\s*include\s*<(.+?)>', line)
        if m:
            includes.append(m.group(1))
    return includes

def _parse_header_comment(lines):
    comment_includes = []
    in_header = False
    for line in lines:
        if line.strip().startswith("//////////////////////////////////////////////////////////////////////"):
            in_header = not in_header
            continue
        if in_header and "include <" in line:
            m = re.search(r'include <(.+?)>', line)
            if m:
                comment_includes.append(m.group(1))
    return comment_includes

def _parse_modules(lines):
    modules = []
    module_pattern = re.compile(r'^\s*module\s+(\w+)\s*\((.*?)\)')
    arg_pattern = re.compile(r'^\s*//\s*(\w+)\s*=\s*(.*?)(?:\s*\(Default:\s*(.*?)\))?\s*$')
    
    current_module = None
    in_module_comment = False
    comment_buffer = []
    
    for line in lines:
        # Start of module comment
        if line.strip().startswith("// Module:"):
            module_name = line.split(":",1)[1].strip()
            current_module = SCADModule(module_name)
            modules.append(current_module)
            in_module_comment = True
            comment_buffer = []
            continue
        # Synopsis / Description / Usage / Arguments / Example
        if in_module_comment:
            if line.strip().startswith("// Module:") or line.strip().startswith("module "):
                in_module_comment = False
            else:
                comment_buffer.append(line.strip())
                # Description
                if line.strip().startswith("// Description:"):
                    current_module.description = line.split(":",1)[1].strip()
                # Usage
                if line.strip().startswith("// Usage:"):
                    usage_line = line.split(":",1)[1].strip()
                    current_module.usage.append(usage_line)
                # Arguments
                if line.strip().startswith("// Arguments:"):
                    continue
                # Argument lines
                arg_match = re.match(r'//\s*(\w+)\s*=\s*(.*?)(?:\s*\(Default:\s*(.*?)\))?\s*(?:$|//)', line)
                if arg_match and current_module:
                    arg_name = arg_match.group(1)
                    default = arg_match.group(3) or None
                    desc = arg_match.group(2).strip()
                    current_module.arguments.append(SCADArgument(arg_name, default, desc))
        # Module definition line: fallback for arguments
        m = module_pattern.match(line)
        if m and current_module:
            arg_str = m.group(2)
            arg_pairs = [a.strip() for a in arg_str.split(",") if a.strip()]
            for arg_pair in arg_pairs:
                # name=default
                if "=" in arg_pair:
                    name, default = [s.strip() for s in arg_pair.split("=",1)]
                    # Skip if already exists
                    if not any(a.name==name for a in current_module.arguments):
                        current_module.arguments.append(SCADArgument(name, default, ""))
                else:
                    name = arg_pair
                    if not any(a.name==name for a in current_module.arguments):
                        current_module.arguments.append(SCADArgument(name, None, ""))
    return modules


# --- Main parsing function ---
def parse_scad_for_modules(filename):
    write_log("Info", f"Parsing SCAD file: {filename}")
    meta = SCADMeta(filename)
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except Exception as e:
        write_log("Info", f"Failed to read file {filename}: {e}")
        return meta

    # Includes
    meta.includes = _parse_includes(lines)
    write_log("Info", f"Found includes: {meta.includes}")

    # Header comment includes
    meta.comment_includes = _parse_header_comment(lines)
    write_log("Info", f"Found comment includes: {meta.comment_includes}")

    # Modules
    meta.modules = _parse_modules(lines)
    write_log("Info", f"Found modules: {[m.name for m in meta.modules]}")

    return meta

