"""
parse_scad_to_meta – backward-compatible shim.

All heavy lifting now lives in ``parsers/scadmeta/``.  This module re-exports
the new :func:`scan_scad_file` under the legacy ``parse_scad_meta`` name and
wraps the new :class:`ScadMeta` in the legacy ``SCADMeta`` / ``SCADModule``
classes so existing callers continue to work unchanged.

New code should import from ``freecad.OpenSCAD_Ext.parsers.scadmeta`` directly.
"""

from __future__ import annotations

import os
from typing import List, Optional

from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, ScadMeta
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


# ---------------------------------------------------------------------------
# Legacy data classes (kept for callers that use attribute access)
# ---------------------------------------------------------------------------

class SCADArgument:
    def __init__(self, name: str, default: Optional[str] = None, description: str = ""):
        self.name = name
        self.default = default
        self.description = description


class SCADModule:
    def __init__(self, name: str):
        self.name = name
        self.description = ""
        self.synopsis = ""
        self.usage: List[str] = []
        self.includes: List[str] = []
        self.arguments: List[SCADArgument] = []


class SCADMeta:
    """Legacy metadata container – wraps the new :class:`ScadMeta`."""

    def __init__(self, filename: str):
        self.sourceFile = filename
        self.baseName = os.path.basename(filename)
        self.includes: List[str] = []
        self.comment_includes: List[str] = []
        self.modules: List[SCADModule] = []

    # Convenience properties that expose the new model fields
    @property
    def uses(self) -> List[str]:
        return getattr(self, "_uses", [])

    @property
    def variables(self) -> dict:
        return getattr(self, "_variables", {})

    @property
    def file_type(self):
        return getattr(self, "_file_type", None)

    @property
    def functions(self) -> list:
        return getattr(self, "_functions", [])


# ---------------------------------------------------------------------------
# Adapter: ScadMeta → SCADMeta
# ---------------------------------------------------------------------------

def _to_legacy(new_meta: ScadMeta) -> SCADMeta:
    """Convert a new-style :class:`ScadMeta` to the legacy :class:`SCADMeta`."""
    legacy = SCADMeta(new_meta.source_file)
    legacy.includes = list(new_meta.includes)
    legacy.comment_includes = list(new_meta.comment_includes)

    # Store new-model fields as private attrs so legacy code ignores them
    legacy._uses = list(new_meta.uses)           # type: ignore[attr-defined]
    legacy._variables = dict(new_meta.variables)  # type: ignore[attr-defined]
    legacy._file_type = new_meta.file_type        # type: ignore[attr-defined]
    legacy._functions = list(new_meta.functions)  # type: ignore[attr-defined]

    for mod in new_meta.modules:
        m = SCADModule(mod.name)
        m.description = mod.description
        m.synopsis = mod.synopsis
        m.usage = list(mod.usage)
        for p in mod.params:
            m.arguments.append(SCADArgument(p.name, p.default, ""))
        legacy.modules.append(m)

    return legacy


# ---------------------------------------------------------------------------
# Public entry point (legacy name kept for backward compatibility)
# ---------------------------------------------------------------------------

def parse_scad_meta(filename: str) -> SCADMeta:
    """
    Parse *filename* and return a :class:`SCADMeta` (legacy wrapper).

    Delegates to the new Lark-based scanner with caching.
    """
    write_log("Info", f"parse_scad_meta: {filename}")
    new_meta = scan_scad_file(filename)
    legacy = _to_legacy(new_meta)

    write_log("Info",
              f"  type={new_meta.file_type.value}  "
              f"modules={new_meta.module_count}  "
              f"functions={new_meta.function_count}  "
              f"variables={len(new_meta.variables)}")
    return legacy


# ---------------------------------------------------------------------------
# Keep the old helper for code that imports it directly
# ---------------------------------------------------------------------------

def list_scad_variables(meta: SCADMeta) -> None:
    """Log module arguments to the FreeCAD report view."""
    if not meta.modules:
        write_log("Info", "No modules found in SCAD file.")
        return
    for mod in meta.modules:
        if not mod.arguments:
            write_log("Info", f"Module '{mod.name}' has no arguments.")
            continue
        write_log("Info", f"Module '{mod.name}' arguments:")
        for arg in mod.arguments:
            default_str = f" = {arg.default}" if arg.default is not None else ""
            write_log("Info", f"  - {arg.name}{default_str}")
