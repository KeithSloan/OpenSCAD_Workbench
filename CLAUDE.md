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

## Test file
/Users/ksloan/github/CAD_Files_Git/OpenSCAD/Ab_Tools/test-2.csg

