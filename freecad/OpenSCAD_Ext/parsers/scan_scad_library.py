"""
scan_scad_library – scan the OpenSCAD library path for SCAD files.

Uses the new Lark-based scanner (with TinyDB cache + Watchdog monitoring) to
extract metadata from every ``.scad`` file found in the configured library
directory.

Returns a list of :class:`~freecad.OpenSCAD_Ext.parsers.scadmeta.ScadMeta`
objects, one per file, each annotated with the detected
:class:`~freecad.OpenSCAD_Ext.parsers.scadmeta.ScadFileType`.
"""

from __future__ import annotations

from typing import List

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.scadmeta import ScadMeta, scan_scad_directory


def scan_scad_library(recursive: bool = False) -> List[ScadMeta]:
    """
    Scan all ``.scad`` files in the configured OpenSCAD library path.

    Parameters
    ----------
    recursive:
        Descend into sub-directories when ``True``.

    Returns
    -------
    list[ScadMeta]
        One entry per ``.scad`` file found, with ``file_type`` set to one of:

        * ``PURE_SCAD``      – produces geometry when run
        * ``LIBRARY``        – include/use aggregator only
        * ``VARIABLE``       – only variable definitions
        * ``MODULES_ONLY``   – only module definitions
        * ``FUNCTIONS_ONLY`` – only function definitions
        * ``MIXED``          – modules + functions
        * ``UNKNOWN``        – empty or unclassifiable
    """
    library_path = ensure_openSCADPATH()
    write_log("Info", f"[scan_scad_library] scanning: {library_path}  recursive={recursive}")

    results = scan_scad_directory(library_path, recursive=recursive, use_cache=True)

    if not results:
        write_log("Warning", f"[scan_scad_library] no SCAD files found in {library_path}")
        return []

    # Log a compact summary grouped by file type
    from collections import Counter
    counts = Counter(m.file_type.value for m in results)
    write_log("Info", f"[scan_scad_library] found {len(results)} files: {dict(counts)}")

    return results
