# scadmeta_parser.py
#
# Lightweight OpenSCAD metadata parser
# Used by varsSCAD to extract parameter information from .scad files

from dataclasses import dataclass, field
from typing import Dict, List
import re
import os


@dataclass
class ScadMeta:
    """Container for parsed SCAD metadata"""
    variables: Dict[str, str] = field(default_factory=dict)
    modules: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    uses: List[str] = field(default_factory=list)


def parse_scadmeta(scad_file: str) -> ScadMeta:
    """
    Parse metadata directives from an OpenSCAD file.

    Recognised comment directives:

      // @var name = value
      // @module name
      // @include filename.scad
      // @use filename.scad

    Returns:
        ScadMeta instance (never raises)
    """
    meta = ScadMeta()

    if not scad_file or not os.path.isfile(scad_file):
        return meta

    # Regex patterns
    var_re = re.compile(r"//\s*@var\s+([A-Za-z_]\w*)\s*=\s*(.+)")
    module_re = re.compile(r"//\s*@module\s+([A-Za-z_]\w*)")
    include_re = re.compile(r"//\s*@include\s+(.+)")
    use_re = re.compile(r"//\s*@use\s+(.+)")

    try:
        with open(scad_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()

                if not line.startswith("//"):
                    continue

                m = var_re.match(line)
                if m:
                    meta.variables[m.group(1)] = m.group(2).strip()
                    continue

                m = module_re.match(line)
                if m:
                    meta.modules.append(m.group(1))
                    continue

                m = include_re.match(line)
                if m:
                    meta.includes.append(m.group(1).strip())
                    continue

                m = use_re.match(line)
                if m:
                    meta.uses.append(m.group(1).strip())
                    continue

    except Exception:
        # Parsing must NEVER kill the workbench
        pass

    return meta

