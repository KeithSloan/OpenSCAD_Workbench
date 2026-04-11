"""
High-level SCAD file scanner.

This module is the single entry point for all metadata extraction:

    from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file

    meta = scan_scad_file("/path/to/shape.scad")
    print(meta.file_type)          # e.g. ScadFileType.MODULES_ONLY
    print(meta.module_count)       # 3
    print([m.name for m in meta.modules])

The scanner
-----------
1. Checks the TinyDB cache (hash + mtime validated).
2. On cache miss, delegates to the Lark-based parser.
3. Classifies the file type via :func:`classify_file_type`.
4. Persists the result to cache.
5. Optionally starts a Watchdog observer for the file's directory so future
   on-disk changes are automatically detected.

Serialisation
-------------
:class:`ScadMeta` is serialised to / from plain dicts so TinyDB can store it
without any custom JSON encoder.
"""

from __future__ import annotations

import dataclasses
import os
from typing import Dict, List, Optional

from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_model import (
    ScadMeta,
    ScadModuleMeta,
    ScadFunctionMeta,
    ScadParam,
    ScadFileType,
    classify_file_type,
)
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_lark_parser import parse_scad_file
from freecad.OpenSCAD_Ext.parsers.scadmeta.scadmeta_cache import get_cache

try:
    from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
except Exception:  # running outside FreeCAD
    def write_log(level: str, msg: str) -> None:  # type: ignore[misc]
        import logging
        logging.getLogger(__name__).debug("[%s] %s", level, msg)


# ---------------------------------------------------------------------------
# Serialise / deserialise  ScadMeta ↔ plain dict
# ---------------------------------------------------------------------------

def _serialise(meta: ScadMeta) -> Dict:
    def _param(p: ScadParam) -> Dict:
        return {"name": p.name, "default": p.default}

    def _module(m: ScadModuleMeta) -> Dict:
        return {
            "name": m.name,
            "params": [_param(p) for p in m.params],
            "description": m.description,
            "synopsis": m.synopsis,
            "usage": m.usage,
            "line_number": m.line_number,
        }

    def _function(f: ScadFunctionMeta) -> Dict:
        return {
            "name": f.name,
            "params": [_param(p) for p in f.params],
            "description": f.description,
            "line_number": f.line_number,
        }

    return {
        "source_file": meta.source_file,
        "base_name": meta.base_name,
        "file_type": meta.file_type.value,
        "includes": meta.includes,
        "uses": meta.uses,
        "comment_includes": meta.comment_includes,
        "variables": meta.variables,
        "modules": [_module(m) for m in meta.modules],
        "functions": [_function(f) for f in meta.functions],
        "has_top_level_calls": meta.has_top_level_calls,
    }


def _deserialise(d: Dict) -> ScadMeta:
    def _param(pd: Dict) -> ScadParam:
        return ScadParam(name=pd["name"], default=pd.get("default"))

    def _module(md: Dict) -> ScadModuleMeta:
        m = ScadModuleMeta(name=md["name"])
        m.params = [_param(p) for p in md.get("params", [])]
        m.description = md.get("description", "")
        m.synopsis = md.get("synopsis", "")
        m.usage = md.get("usage", [])
        m.line_number = md.get("line_number", 0)
        return m

    def _function(fd: Dict) -> ScadFunctionMeta:
        f = ScadFunctionMeta(name=fd["name"])
        f.params = [_param(p) for p in fd.get("params", [])]
        f.description = fd.get("description", "")
        f.line_number = fd.get("line_number", 0)
        return f

    meta = ScadMeta(
        source_file=d.get("source_file", ""),
        base_name=d.get("base_name", ""),
        file_type=ScadFileType(d.get("file_type", ScadFileType.UNKNOWN.value)),
        includes=d.get("includes", []),
        uses=d.get("uses", []),
        comment_includes=d.get("comment_includes", []),
        variables=d.get("variables", {}),
        modules=[_module(m) for m in d.get("modules", [])],
        functions=[_function(f) for f in d.get("functions", [])],
        has_top_level_calls=d.get("has_top_level_calls", False),
    )
    meta.refresh_counts()
    return meta


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_scad_file(path: str, use_cache: bool = True, watch: bool = True) -> ScadMeta:
    """
    Scan a single SCAD file and return its :class:`ScadMeta`.

    Parameters
    ----------
    path:
        Absolute or relative path to the ``.scad`` file.
    use_cache:
        When ``True`` (default) check the TinyDB cache before parsing.
        Re-parses and refreshes the cache when the file has changed.
    watch:
        When ``True`` (default) register the file's parent directory with
        Watchdog so cache entries are invalidated automatically on disk changes.

    Returns
    -------
    ScadMeta
        Populated metadata including :attr:`~ScadMeta.file_type`,
        :attr:`~ScadMeta.modules`, :attr:`~ScadMeta.functions`,
        :attr:`~ScadMeta.variables`, etc.
    """
    path = os.path.abspath(path)

    if not os.path.isfile(path):
        write_log("Warning", f"scan_scad_file: file not found: {path}")
        return ScadMeta(source_file=path, base_name=os.path.basename(path))

    cache = get_cache() if use_cache else None

    # --- cache lookup ---
    if cache is not None:
        cached = cache.get(path)
        if cached is not None:
            write_log("Info", f"[scadmeta] cache hit: {os.path.basename(path)}")
            return _deserialise(cached)

    # --- parse ---
    write_log("Info", f"[scadmeta] parsing: {os.path.basename(path)}")
    meta = parse_scad_file(path)

    # --- classify ---
    meta.file_type = classify_file_type(meta)
    meta.refresh_counts()

    write_log(
        "Info",
        f"[scadmeta] {meta.base_name}: type={meta.file_type.value}  "
        f"modules={meta.module_count}  functions={meta.function_count}  "
        f"variables={len(meta.variables)}  "
        f"includes={len(meta.includes)}  uses={len(meta.uses)}"
    )

    # --- cache store ---
    if cache is not None:
        cache.put(path, _serialise(meta))

    # --- start watchdog for this directory ---
    if watch and cache is not None:
        try:
            cache.watch_directory(os.path.dirname(path))
        except Exception:
            pass

    return meta


def scan_scad_directory(
    directory: str,
    recursive: bool = False,
    use_cache: bool = True,
) -> List[ScadMeta]:
    """
    Scan all ``.scad`` files in *directory* and return a list of
    :class:`ScadMeta` objects.

    Parameters
    ----------
    directory:
        Path to directory to scan.
    recursive:
        If ``True`` descend into sub-directories.
    use_cache:
        Passed through to :func:`scan_scad_file`.
    """
    directory = os.path.abspath(directory)
    results: List[ScadMeta] = []

    if not os.path.isdir(directory):
        write_log("Warning", f"scan_scad_directory: not a directory: {directory}")
        return results

    # Register the top-level directory with watchdog once
    if use_cache:
        try:
            get_cache().watch_directory(directory, recursive=recursive)
        except Exception:
            pass

    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            if fname.lower().endswith(".scad"):
                full_path = os.path.join(root, fname)
                meta = scan_scad_file(full_path, use_cache=use_cache, watch=False)
                results.append(meta)

        if not recursive:
            dirs.clear()  # prevent os.walk from descending

    write_log(
        "Info",
        f"[scadmeta] scanned {len(results)} SCAD files in {directory}"
    )
    return results
