# parse_scad_for_modules.py

import re
import os
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
        self.synopsis = ""
        self.usage = []
        self.includes = []
        self.arguments = []

class SCADMeta:
    def __init__(self, filename):
        self.sourceFile = filename
        self.baseName = os.path.basename(filename)
        self.includes = []          # Includes in the file
        self.comment_includes = []  # Includes found in file header comments
        self.modules = []           # List of SCADModule objects


# --- Helper functions ---
def _unique_preserve_order(seq):
    seen = set()
    result = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

def _parse_includes(lines):
    includes = []
    for line in lines:
        m = re.match(r'^\s*include\s*<(.+?)>', line)
        if m:
            includes.append(m.group(1))
    return _unique_preserve_order(includes)

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
    return _unique_preserve_order(comment_includes)

def _parse_modules(lines):
    """
    Parse modules from SCAD lines.
    Supports BOSL2-style headers and OpenFlexure-style modules.
    """
    modules = []
    module_pattern = re.compile(r'^\s*module\s+(\w+)\s*\((.*?)\)\s*{?')

    current_module = None
    module_comment_buffer = []

    for line in lines:
        line_strip = line.strip()

        # Collect preceding comments
        if line_strip.startswith("//"):
            module_comment_buffer.append(line_strip.lstrip("//").strip())
            continue

        # Match module definition
        m = module_pattern.match(line)
        if m:
            module_name = m.group(1)
            arg_str = m.group(2)

            current_module = SCADModule(module_name)
            modules.append(current_module)

            # Process arguments
            arg_pairs = [a.strip() for a in arg_str.split(",") if a.strip()]
            for arg_pair in arg_pairs:
                if "=" in arg_pair:
                    name, default = [s.strip() for s in arg_pair.split("=", 1)]
                    current_module.arguments.append(SCADArgument(name, default, ""))
                else:
                    current_module.arguments.append(SCADArgument(arg_pair, None, ""))

            # Attach comment buffer as description / BOSL2 metadata
            if module_comment_buffer:
                for cmt in module_comment_buffer:
                    # BOSL2-style parsing
                    cmt_lower = cmt.lower()
                    if cmt_lower.startswith("module:"):
                        current_module.name = cmt.split(":",1)[1].strip()
                    elif cmt_lower.startswith("description:"):
                        current_module.description = cmt.split(":",1)[1].strip()
                    elif cmt_lower.startswith("synopsis:"):
                        current_module.synopsis = cmt.split(":",1)[1].strip()
                    elif cmt_lower.startswith("usage:"):
                        usage_line = cmt.split(":",1)[1].strip()
                        current_module.usage.append(usage_line)
                    else:
                        # fallback: append remaining lines to description
                        if current_module.description:
                            current_module.description += " " + cmt
                        else:
                            current_module.description = cmt
                module_comment_buffer = []

        else:
            # Not a module, reset comment buffer if non-comment line
            module_comment_buffer = []

    return modules


# --- Main parsing function ---
#def parse_scad_for_modules(filename):
def parse_scad_meta(filename):
    write_log("Info", f"Parsing SCAD file: {filename}")
    meta = SCADMeta(filename)
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        write_log("Info", f"Failed to read file {filename}: {e}")
        return meta

    # Parse includes
    meta.includes = _parse_includes(lines)
    max_log = 10
    log_includes = meta.includes[:max_log]
    if len(meta.includes) > max_log:
        log_includes.append(f"... (+{len(meta.includes)-max_log} more)")
    write_log("Info", f"Found includes: {log_includes}")

    # Parse header comment includes
    meta.comment_includes = _parse_header_comment(lines)
    max_comment_log = 10
    log_comment_includes = meta.comment_includes[:max_comment_log]
    if len(meta.comment_includes) > max_comment_log:
        log_comment_includes.append(f"... (+{len(meta.comment_includes)-max_comment_log} more)")
    write_log("Info", f"Found comment includes: {log_comment_includes}")

    # Parse modules
    meta.modules = _parse_modules(lines)
    write_log("Info", f"Found modules: {[m.name for m in meta.modules]}")

    return meta

