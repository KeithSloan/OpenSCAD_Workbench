# freecad/OpenSCAD_Ext/importers/importCSG.py
#
# Import-strategy dispatcher for CSG / SCAD files.
#
# Reads the "ImportStrategy" preference key from
#   User parameter:BaseApp/Preferences/Mod/OpenSCAD_Ext
# and delegates to the appropriate importer:
#
#   "deferred"   (default) → importASTCSG   – in-memory OCCT shapes,
#                                              single doc.recompute() at end
#   "parametric"           → importAltCSG   – PLY parser, creates parametric
#                                              Part::Fuse / Part::Cut doc objects
#
# Both delegate modules expose the standard FreeCAD importer API:
#   open(filename)          → FreeCAD.Document
#   insert(filename, docname)
#   processCSG(doc, filename, ...)

import FreeCAD

__title__  = "FreeCAD OpenSCAD_Ext – Import Strategy Dispatcher"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__    = ["https://github.com/KeithSloan/OpenSCAD_Workbench"]

# Display name shown in FreeCAD's file-type selector (FC ≥ 1.1)
DisplayName = "OpenSCAD Ext – CSG / SCAD Importer (auto-strategy)"

_PREF_PATH    = "User parameter:BaseApp/Preferences/Mod/OpenSCAD_Ext"
_PREF_KEY     = "ImportStrategy"
_DEFAULT_STRAT = "deferred"


def _get_strategy() -> str:
    """Return the configured import strategy string (lower-case)."""
    params = FreeCAD.ParamGet(_PREF_PATH)
    return params.GetString(_PREF_KEY, _DEFAULT_STRAT).lower()


def _get_importer():
    """Return the importer module selected by the current preference."""
    strategy = _get_strategy()
    if strategy == "parametric":
        from freecad.OpenSCAD_Ext.importers import importAltCSG as _imp
        FreeCAD.Console.PrintMessage(
            "[OpenSCAD_Ext] ImportStrategy: parametric (importAltCSG)\n"
        )
    else:
        # "deferred" or any unrecognised value → default
        from freecad.OpenSCAD_Ext.importers import importASTCSG as _imp
        FreeCAD.Console.PrintMessage(
            "[OpenSCAD_Ext] ImportStrategy: deferred (importASTCSG)\n"
        )
    return _imp


# ── FreeCAD importer API ─────────────────────────────────────────────────────

def open(filename):
    """Called when FreeCAD opens a file."""
    return _get_importer().open(filename)


def insert(filename, docname):
    """Called when FreeCAD imports a file into an existing document."""
    return _get_importer().insert(filename, docname)


def processCSG(doc, filename, fnmax_param=None):
    """Direct programmatic entry point (mirrors the delegate API)."""
    imp = _get_importer()
    if fnmax_param is not None:
        return imp.processCSG(doc, filename, fnmax_param)
    return imp.processCSG(doc, filename)
