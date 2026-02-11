import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional
import os

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


# -------------------------------------------------
# Data Classes
# -------------------------------------------------

@dataclass
class SCADArgument:
    name: str
    default: Optional[str] = None
    description: Optional[str] = None


@dataclass
class SCADModule:
    name: str
    file_path: str
    start_line: int
    end_line: Optional[int] = None
    description: str = ""
    arguments: List[SCADArgument] = field(default_factory=list)


@dataclass
class SCADMeta:
    sourceFile: str
    baseName: str
    initial_comments: str = ""
    includes: List[str] = field(default_factory=list)
    uses: List[str] = field(default_factory=list)
    comment_includes: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    fn_settings: dict = field(default_factory=dict)
    modules: List[SCADModule] = field(default_factory=list)
    classification: Optional[str] = None
    file_hash: Optional[str] = None


# -------------------------------------------------
# Scanner
# -------------------------------------------------

def scan_scad_file(filepath: str) -> SCADMeta:
    write_log("Info", f"Scanning SCAD file: {filepath}")

    meta = SCADMeta(
        sourceFile=filepath,
        baseName=os.path.basename(filepath)
    )

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # File hash
    meta.file_hash = hashlib.sha256("".join(lines).encode()).hexdigest()

    inside_module = False
    brace_depth = 0
    current_module = None
    header_comment_block = []

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()

        # ----------------------------------------
        # Capture initial header comments
        # ----------------------------------------
        if idx < 100 and line.startswith("//"):
            header_comment_block.append(raw_line)

        # ----------------------------------------
        # include / use
        # ----------------------------------------
        inc_match = re.match(r'include\s*<(.+?)>', line)
        use_match = re.match(r'use\s*<(.+?)>', line)

        if inc_match:
            inc = inc_match.group(1)
            write_log("Info", f"Include found: {inc}")
            meta.includes.append(inc)

        if use_match:
            use = use_match.group(1)
            write_log("Info", f"Use found: {use}")
            meta.uses.append(use)

        # ----------------------------------------
        # $fn, $fa, $fs
        # ----------------------------------------
        fn_match = re.match(r'(\$f[nas])\s*=\s*([^;]+);', line)
        if fn_match:
            key = fn_match.group(1)
            val = fn_match.group(2)
            meta.fn_settings[key] = val
            write_log("Info", f"Found {key} = {val}")

        # ----------------------------------------
        # Variable assignment (top-level)
        # ----------------------------------------
        if not inside_module:
            var_match = re.match(r'([a-zA-Z_]\w*)\s*=\s*([^;]+);', line)
            if var_match:
                meta.variables.append(var_match.group(1))

        # ----------------------------------------
        # Module detection
        # ----------------------------------------
        module_match = re.match(r'module\s+([a-zA-Z_]\w*)\s*\((.*?)\)', line)
        if module_match:
            name = module_match.group(1)
            args_raw = module_match.group(2)

            write_log("Info", f"Module found: {name}")

            current_module = SCADModule(
                name=name,
                file_path=filepath,
                start_line=idx + 1
            )

            # Parse arguments
            args = [a.strip() for a in args_raw.split(",") if a.strip()]
            for arg in args:
                if "=" in arg:
                    n, d = arg.split("=", 1)
                    current_module.arguments.append(
                        SCADArgument(name=n.strip(), default=d.strip())
                    )
                else:
                    current_module.arguments.append(
                        SCADArgument(name=arg.strip())
                    )

            meta.modules.append(current_module)
            inside_module = True
            brace_depth = 0

        # Track brace depth
        if inside_module:
            brace_depth += line.count("{")
            brace_depth -= line.count("}")

            if brace_depth <= 0 and current_module:
                current_module.end_line = idx + 1
                inside_module = False
                current_module = None

    meta.initial_comments = "".join(header_comment_block)

    # Classification
    meta.classification = classify(meta)

    write_log("Info", f"Classification: {meta.classification}")
    return meta


# -------------------------------------------------
# Classification
# -------------------------------------------------

def classify(meta: SCADMeta) -> str:

    module_names = [m.name for m in meta.modules]

    if meta.modules and not meta.variables:
        return "Library"

    if "main" in module_names:
        return "Executable Model"

    if meta.includes and not meta.modules:
        return "Include Wrapper"

    if meta.fn_settings:
        return "Configured Model"

    return "General SCAD"

