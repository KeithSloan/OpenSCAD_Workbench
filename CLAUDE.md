# OpenSCAD_Ext Workbench

## Key files
- Importer: freecad/OpenSCAD_Ext/importers/importASTCSG.py
- AST processor: parsers/csg_parser/processAST.py
- Hull handler: parsers/csg_parser/processHull.py
- Preferences UI: Resources/ui/OpenSCAD_Ext_Preferences.ui

## Conventions
- Shapes are returned as (Part.Shape, App.Placement) tuples
- Centering must be encoded in local_pl, not via shape.translate()
- Hull fallback: flatten_ast_node_back_to_csg() → OpenSCAD CLI → STL
- Active branch for new features: ImportStrategy

## Importer versioning
- **ImportAstCSG** (`importers/importASTCSG.py`) is the active AST-based importer.
  - Current version: `0.7.2`  (set via `__version__` at top of file)
  - Increment `__version__` on **every code change**: bug fix → patch (0.7.0 → 0.7.1),
    significant new feature → minor (0.7.x → 0.8.0).
  - Version is printed twice to the Report View: at start and end of `processCSG()`.
- **ImportAltCSG** (`importers/importAltCSG.py`) is legacy code copied from the
  AlternateOpenSCAD workbench. It will be maintained alongside ImportAstCSG for the
  foreseeable future.
  - Reports itself as `ImportAltCSG Version 0.6a` in the Report View.
- **newImportCSG** (`importers/newImportCSG.py`) is a transitional importer — to be removed
  once ImportAstCSG is complete.

## Test file
/Users/ksloan/github/CAD_Files_Git/OpenSCAD/Ab_Tools/test-2.csg

