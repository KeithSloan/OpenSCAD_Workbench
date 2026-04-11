"""
parse_library_scad – backward-compatible shim.

Delegates to the new Lark-based scanner.  The ``parse_scad_meta`` function
returns a legacy :class:`SCADMeta` wrapper so all existing callers
(``OpenSCADLibraryBrowser``, ``importParseSCADMeta``, etc.) continue to work.

New code should import from ``freecad.OpenSCAD_Ext.parsers.scadmeta`` directly.
"""

# Re-export everything from the canonical shim so this module is a drop-in
from freecad.OpenSCAD_Ext.parsers.parse_scad_to_meta import (  # noqa: F401
    SCADArgument,
    SCADModule,
    SCADMeta,
    parse_scad_meta,
    list_scad_variables,
)
