# OpenSCAD_Ext Workbench

## Key files
- Importer: freecad/OpenSCAD_Ext/importers/importASTCSG.py
- AST processor: parsers/csg_parser/processAST.py
- Hull handler: parsers/csg_parser/processHull.py
- Hull geometry helpers: parsers/csg_parser/process_hull_cylinders.py, process_hull_utils.py
- Preferences UI: Resources/ui/OpenSCAD_Ext_Preferences.ui

## Conventions
- Shapes are returned as (Part.Shape, App.Placement) tuples
- Centering must be encoded in local_pl, not via shape.translate()
- Hull fallback: flatten_ast_node_back_to_csg() → OpenSCAD CLI → STL
- Active branch for new features: ImportStrategy

## Hull handling
`processHull.py` → `try_hull()` dispatches to type-specific handlers.

### collect_primitives
Walks hull children accumulating transform matrices. Transparent wrappers
handled: `group`, `color`, `multmatrix`.
- **`intersection`** is also treated as transparent: the first child branch
  that yields a known primitive (sphere/cube/cylinder) is used; the clipping
  geometry (e.g. `linear_extrude` of a sector polygon) is ignored.
  Rationale: for convex-hull purposes, clipping a convex shape can only shrink
  the hull boundary, never expand it.

### Cylinder hull dispatch (`process_hull_cylinders.py`)
- **Collinear axes, collinear centres** → revolved profile (`make_colinear_cylinders_cones`)
- **Parallel axes, non-collinear centres, equal radii** → `hull_parallel_cylinders_grid`:
  rounded-polygon extrusion (the classic OpenSCAD rounded-box pattern).
  Algorithm:
  1. Project cylinder bases/tops onto the 2-D plane ⊥ axis_dir.
  2. `convex_hull_2d()` (Graham scan, CCW) of projected positions.
  3. Outer polygon: for each hull vertex, intersect the two adjacent
     offset lines (each edge moved outward by r) — no `Part.Arc` needed.
  4. `Part.makePolygon` → `Part.Face` → `face.extrude(axis_dir * height)`.
  5. `prism.makeFillet(r, vertical_edges)` — fillet arcs are centred on
     the original cylinder positions, giving the exact Minkowski-sum geometry.

### Utility (`process_hull_utils.py`)
- `convex_hull_2d(pts)` — 2-D Graham scan, returns CCW vertices,
  float-tolerance deduplication.
- `make_rounded_polygon_wire()` — arc-based wire builder (retained for
  future use; currently not called).

## Importer versioning
- **ImportAstCSG** (`importers/importASTCSG.py`) is the active AST-based importer.
  - Current version: `0.7.5`  (set via `__version__` at top of file)
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

