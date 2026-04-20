from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class ScadFileType(Enum):
    """
    Classification of what a SCAD file primarily contains.

    PURE_SCAD      – Has top-level geometry / executable statements (produces
                     output when run directly with OpenSCAD).
    CUSTOMIZER     – Like PURE_SCAD but also defines parameter variables,
                     suitable for the OpenSCAD Customizer.
    LIBRARY        – Only include/use aggregation with no own definitions and
                     no top-level geometry (a "meta-library" wrapper).
    VARIABLE       – Only variable definitions; no modules, functions, or
                     top-level calls.
    MODULES_ONLY   – Defines modules (possibly also variables/includes) but
                     no functions and no top-level geometry.
    FUNCTIONS_ONLY – Defines functions (possibly also variables/includes) but
                     no modules and no top-level geometry.
    MIXED          – Defines both modules and functions.
    UNKNOWN        – Empty file or unclassifiable.
    """

    PURE_SCAD = "pure_scad"
    CUSTOMIZER = "customizer"
    LIBRARY = "library"
    VARIABLE = "variable"
    MODULES_ONLY = "modules_only"
    FUNCTIONS_ONLY = "functions_only"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class ScadParam:
    """A single parameter in a module or function signature."""

    name: str
    default: Optional[str] = None   # raw expression string, or None


@dataclass
class ScadModuleMeta:
    """Metadata for a single OpenSCAD module definition."""

    name: str
    params: List[ScadParam] = field(default_factory=list)
    description: str = ""
    synopsis: str = ""
    usage: List[str] = field(default_factory=list)
    line_number: int = 0
    param_descriptions: Dict[str, str] = field(default_factory=dict)
    excluded_params: List[str] = field(default_factory=list)  # params after // --- separator


@dataclass
class ScadFunctionMeta:
    """Metadata for a single OpenSCAD function definition."""

    name: str
    params: List[ScadParam] = field(default_factory=list)
    description: str = ""
    line_number: int = 0


@dataclass
class ScadMeta:
    """
    Complete metadata extracted from a single SCAD source file.
    """

    # --- Identity ---
    source_file: str = ""
    base_name: str = ""

    # --- Classification ---
    file_type: ScadFileType = ScadFileType.UNKNOWN
    module_count: int = 0
    function_count: int = 0

    # --- Dependency statements ---
    includes: List[str] = field(default_factory=list)   # include <path>
    uses: List[str] = field(default_factory=list)        # use <path>
    comment_includes: List[str] = field(default_factory=list)  # from BOSL2 header

    # --- Definitions ---
    variables: Dict[str, str] = field(default_factory=dict)                 # name -> expr
    variable_descriptions: Dict[str, str] = field(default_factory=dict)     # name -> trailing comment
    modules: List[ScadModuleMeta] = field(default_factory=list)
    functions: List[ScadFunctionMeta] = field(default_factory=list)

    # --- Content flags ---
    has_top_level_calls: bool = False   # True ⟹ file produces geometry

    def __post_init__(self) -> None:
        self.module_count = len(self.modules)
        self.function_count = len(self.functions)

    def refresh_counts(self) -> None:
        """Recompute derived counts after mutations."""
        self.module_count = len(self.modules)
        self.function_count = len(self.functions)


def classify_file_type(meta: ScadMeta) -> ScadFileType:
    """
    Determine the :class:`ScadFileType` for *meta* based on its contents.

    Priority order (first match wins):

    1. Has top-level geometry + variables → CUSTOMIZER
    2. Has top-level geometry calls       → PURE_SCAD
    3. Has both modules and functions     → MIXED
    4. Has modules only                   → MODULES_ONLY
    5. Has functions only                 → FUNCTIONS_ONLY
    6. Has variables only                 → VARIABLE
    7. Has only include/use lines         → LIBRARY
    8. Otherwise                          → UNKNOWN
    """
    has_modules = len(meta.modules) > 0
    has_functions = len(meta.functions) > 0
    has_variables = len(meta.variables) > 0
    has_deps = len(meta.includes) > 0 or len(meta.uses) > 0

    if meta.has_top_level_calls and has_variables:
        return ScadFileType.CUSTOMIZER
    if meta.has_top_level_calls:
        return ScadFileType.PURE_SCAD
    if has_modules and has_functions:
        return ScadFileType.MIXED
    if has_modules:
        return ScadFileType.MODULES_ONLY
    if has_functions:
        return ScadFileType.FUNCTIONS_ONLY
    if has_variables:
        return ScadFileType.VARIABLE
    if has_deps:
        return ScadFileType.LIBRARY
    return ScadFileType.UNKNOWN
