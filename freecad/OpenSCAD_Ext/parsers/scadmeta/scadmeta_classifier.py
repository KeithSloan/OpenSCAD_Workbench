"""
scadmeta_classifier.py

Classify SCAD files based on metadata annotations and lightweight inspection.
Returns a ScadType enum indicating file type, intended for library scans and UI coloring.

Uses:
- scadmeta_annotations.parse_scad_meta()
"""

from enum import Enum, auto
import re
from typing import Optional

from scadmeta.scadmeta_annotations import ScadMeta, parse_scad_meta


# -----------------------------------------------------------------------------
# File type enumeration
# -----------------------------------------------------------------------------
class ScadType(Enum):
    UNKNOWN = auto()
    RAW_SCRIPT = auto()                    # no modules or functions
    SINGLE_MODULE = auto()                 # one module
    MULTI_MODULE = auto()                  # multiple modules
    MULTI_MODULE_WITH_DOCS = auto()        # multiple modules + annotations
    FUNCTIONS_ONLY = auto()                # functions present, no modules
    VARIABLE_LIBRARY = auto()              # only vars / sets


# Optional: regex to detect function definitions
FUNC_RE = re.compile(r"^\s*function\s+[A-Za-z_]\w*\s*\(")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def classify_scad_file(path: str, meta: Optional[ScadMeta] = None) -> ScadType:
    """
    Classify a SCAD file.

    Parameters
    ----------
    path : str
        Path to the .scad file
    meta : Optional[ScadMeta]
        Pre-parsed annotations (optional). If None, parse from file.

    Returns
    -------
    ScadType
    """
    if meta is None:
        meta = parse_scad_meta(path)

    # --- First, check for completely empty metadata ---
    if not meta.has_annotations():
        # Check for modules/functions in file via lightweight scan
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return ScadType.UNKNOWN

        modules = 0
        functions = 0

        for line in lines:
            line = line.strip()
            if line.startswith("module "):
                modules += 1
            elif FUNC_RE.match(line):
                functions += 1

        if modules == 0 and functions == 0:
            return ScadType.RAW_SCRIPT
        elif modules == 1:
            return ScadType.SINGLE_MODULE
        elif modules > 1:
            return ScadType.MULTI_MODULE
        elif functions > 0:
            return ScadType.FUNCTIONS_ONLY

    # --- If there are annotations ---
    module_count = len(meta.modules)
    has_doc_modules = module_count > 0

    if module_count == 0 and meta.vars:
        return ScadType.VARIABLE_LIBRARY
    elif module_count == 1:
        return ScadType.SINGLE_MODULE
    elif module_count > 1:
        if has_doc_modules:
            return ScadType.MULTI_MODULE_WITH_DOCS
        else:
            return ScadType.MULTI_MODULE

    return ScadType.UNKNOWN


# -----------------------------------------------------------------------------
# Optional helper: get a display color for Qt
# -----------------------------------------------------------------------------
SCAD_TYPE_COLORS = {
    ScadType.RAW_SCRIPT: "#cccccc",
    ScadType.SINGLE_MODULE: "#a6cee3",
    ScadType.MULTI_MODULE: "#1f78b4",
    ScadType.MULTI_MODULE_WITH_DOCS: "#33a02c",
    ScadType.FUNCTIONS_ONLY: "#fb9a99",
    ScadType.VARIABLE_LIBRARY: "#ff7f00",
    ScadType.UNKNOWN: "#ffffff",
}


def get_scad_type_color(scad_type: ScadType) -> str:
    """
    Return a hex color for a given SCAD file type.
    Intended for UI coloring in library views.
    """
    return SCAD_TYPE_COLORS.get(scad_type, "#ffffff")

