"""
scadmeta – OpenSCAD file metadata extraction package.

Public API
----------
    from freecad.OpenSCAD_Ext.parsers.scadmeta import (
        scan_scad_file,
        scan_scad_directory,
        ScadMeta,
        ScadModuleMeta,
        ScadFunctionMeta,
        ScadParam,
        ScadFileType,
    )

File type classification
------------------------
Each scanned file receives one of these :class:`ScadFileType` values:

    PURE_SCAD      – Top-level geometry / executable statements (runs directly).
    LIBRARY        – Only include/use aggregation, no own definitions.
    VARIABLE       – Only variable definitions.
    MODULES_ONLY   – Module definitions only.
    FUNCTIONS_ONLY – Function definitions only.
    MIXED          – Both module and function definitions.
    UNKNOWN        – Empty or unclassifiable.
"""

from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_model import (
    ScadMeta,
    ScadModuleMeta,
    ScadFunctionMeta,
    ScadParam,
    ScadFileType,
    classify_file_type,
)
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_scanner import (
    scan_scad_file,
    scan_scad_directory,
)
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_cache import get_cache

__all__ = [
    "ScadMeta",
    "ScadModuleMeta",
    "ScadFunctionMeta",
    "ScadParam",
    "ScadFileType",
    "classify_file_type",
    "scan_scad_file",
    "scan_scad_directory",
    "get_cache",
]
