# OpenSCAD_Ext Workbench

## Key files
- Importer: freecad/OpenSCAD_Ext/importers/importASTCSG.py
- AST processor: parsers/csg_parser/processAST.py
- Hull handler: parsers/csg_parser/processHull.py
- Hull geometry helpers: parsers/csg_parser/process_hull_cylinders.py, process_hull_utils.py
- Preferences UI: Resources/ui/OpenSCAD_Ext_Preferences.ui

## Geometry modes
Three modes exist: **Mesh** and **Attempting AST-Brep** (the old "Brep" option has been
removed). The mode string must match exactly — enums and comparisons all use these spellings:
- `"Mesh"` — run OpenSCAD → import result as `Mesh::Feature` (no TNP spinner)
- `"Attempting AST-Brep"` — parse CSG AST to native BRep; falls back to whole-file
  OpenSCAD mesh if any per-node fallback was needed (see Fallback Architecture below)

## Conventions
- Shapes are returned as (Part.Shape, App.Placement) tuples
- Centering must be encoded in local_pl, not via shape.translate()
- Hull fallback: flatten_ast_node_back_to_csg() → OpenSCAD CLI → STL
- Active branch for new features: ImportStrategy

## $fn / fnmax — polygon vs. circle/cylinder threshold

OpenSCAD outputs faceted approximations: a `cylinder($fn=32, ...)` is actually a 32-sided
prism, **not** a true cylinder. The workbench preference `useMaxFN` (default 16) controls
whether these are imported as exact BRep geometry or as faithful N-sided prisms/polygons.

### Rule (matches legacy `importAltCSG` behaviour):
| Condition | Result |
|---|---|
| `$fn == 0` (unspecified) | True BRep (Part.makeCylinder / circle) |
| `_fnmax == 0` | True BRep for everything (threshold disabled) |
| `$fn > _fnmax` | True BRep — "smooth enough" to treat as circular |
| `3 <= $fn <= _fnmax` | N-sided prism / polygon (faithful to OpenSCAD) |

### Implementation:
- **Preference key**: `User parameter:BaseApp/Preferences/Mod/OpenSCAD` → `useMaxFN` (int, default 16)
- **`importASTCSG.processCSG()`** reads the preference into `fnmax`, then sets
  `_pAST_mod._fnmax = fnmax` on the `processAST` module before processing begins.
- **`processAST._fnmax`** (module global, default 0): the active threshold for the current run.
- **`processAST._use_brep(fn_val)`**: helper that implements the rule above.
- **`processAST._make_prism(r, h, n)`**: builds an N-sided prism for a cylinder node.
- **`processAST._make_frustum(r1, r2, h, n)`**: builds an N-sided frustum for a cone node.
- **`processAST._make_ngon_face(r, n)`**: builds an N-gon face for a circle node.

### Why this matters for hull:
When a CSG file contains `cylinder($fn=32, ...)` inside a `hull()`, the hull dispatcher
receives 32-sided prism primitives. The hull of N-gon prisms is **much simpler** to compute
(and faster) than the hull of true cylinders, and it matches what OpenSCAD actually produced.
With `fnmax=16` (default), `$fn=32` → true BRep cylinder → hull of cylinders path.
With a higher `fnmax` (e.g. 64), `$fn=32` → 32-sided prism → hull falls back to OpenSCAD CLI
(since prism hull is not yet implemented natively), but the CLI result is exact.

### Preference UI:
- File: `freecad/OpenSCAD_Ext/Resources/ui/OpenSCAD_Ext_Preferences.ui`
- Label: "Facet threshold — $fn above this value: treat as circle/cylinder"
- Tooltip explains the rule in full.

## Fallback Architecture — why whole-file OpenSCAD fallback is essential

OCC boolean operations (`fuse`, `cut`, `common`) **do not throw exceptions** when
operating on mesh-derived `Part.Shape` objects (shapes imported from STL via
`Part.read()`).  They silently return geometrically wrong results.  This means any
shape that went through a per-node OpenSCAD CLI fallback (hull, minkowski, etc.)
cannot be safely used as input to OCC booleans — the callers can't detect the error.

### `_fallback_used` flag
`processAST._fallback_used` (module global, reset to `False` at the start of each
`processCSG()` call) is set to `True` whenever `fallback_to_OpenSCAD()` is called.
This signals that at least one shape in the result is mesh-derived.

### Two-path fallback (one per call site)

**1. Direct import path** (`importASTCSG.open()` / `insert()`):
- Calls `processCSG(doc, filename, allow_wholefile_fallback=True)`
- After `process_AST()` completes, if `_fallback_used` is True: discard all partial
  BRep shapes, run `callopenscad(filename, outputext='stl')` on the CSG file, import
  the result as a `Mesh::Feature`.  No partial BRep objects are added to the document.

**2. Live-render path** (`SCADObject.createBrep()`):
- Calls `importASTCSG.processCSG(wrkDoc, tmpFileName, fnmax)` — **no** `allow_wholefile_fallback`
  (defaults False), so `processCSG` always adds BRep shapes to wrkDoc normally.
- After `processCSG()` returns, checks `_fallback_used`.  If True: **immediately**
  close wrkDoc (discard its potentially-wrong BRep shapes), then call
  `callopenscad(tmpFileName, outputext='stl')` on the already-computed CSG file, and
  return `Mesh.Mesh` directly.  The mode property is changed to `"Mesh"`.
- If no fallback: collect shapes from wrkDoc, return compound `Part.Shape`.

**Key rule**: never let mesh-derived shapes participate in OCC boolean operations.
The moment `_fallback_used` is True, skip OCC booleans entirely and go to whole-file
OpenSCAD STL.

### Mesh::Feature vs Part::FeaturePython
Mesh mode finalized objects are stored as `Mesh::Feature` (via `finalize_scad_mesh_object()`
in `core/scad_mesh_utils.py`).  These avoid the TNP element-map cursor-spin on complex
models.  All SCAD properties (sourceFile, mode, fnmax, linked_varset, …) are migrated
from the FeaturePython companion to the Mesh::Feature, and `message` is set read-only.

When mode is switched from Mesh → Attempting AST-Brep on a finalized Mesh::Feature,
`renderSCAD._replace_mesh_feature_with_brep()` removes the Mesh::Feature and creates a
fresh Part::FeaturePython.

## Hull handling
`processHull.py` → `try_hull()` dispatches to type-specific handlers.

### collect_primitives
Walks hull children accumulating transform matrices. Transparent wrappers
handled: `group`, `color`, `multmatrix`.
- **`intersection`** is treated as transparent *only when the clipping children
  are simple* (transparent wrappers + leaf primitives — no `difference`, `hull`,
  `linear_extrude`, etc.).  The first child that yields a known primitive is used;
  simple clipping geometry (e.g. `linear_extrude` of a sector polygon) is ignored.
  Rationale: hull(A ∩ B, …) ⊆ hull(A, …) so the unclipped primitive is an
  over-approximation that is always geometrically safe.
  **Exception**: if any clipping child contains constructive ops (`difference`,
  `hull`, `linear_extrude`, …), the intersection result may be far smaller than
  the first primitive (e.g. a 30 mm cube clipped to a tiny peg).  In that case
  `collect_primitives` returns `False` → the whole hull falls back to OpenSCAD CLI.
  Implemented via `_subtree_has_complex_op()` in `processHull.py`.

### Cylinder hull dispatch (`process_hull_cylinders.py`)
- **Collinear axes, collinear centres** → revolved profile (`make_colinear_cylinders_cones`).
  Handles true cylinders and cones (r1 ≠ r2) via upper convex hull in (z, r) space.
- **Parallel axes, non-collinear centres** → `hull_parallel_cylinders_grid`, which
  dispatches further:
  - **Equal radii (r1 == r2)** → `_build_rounded_prism`: rounded-polygon extrusion.
    Algorithm:
    1. Project cylinder bases/tops onto the 2-D plane ⊥ axis_dir.
    2. `convex_hull_2d()` (Graham scan, CCW) of projected positions.
    3. Outer polygon: for each hull vertex, intersect the two adjacent
       offset lines (each edge moved outward by r) — no `Part.Arc` needed.
    4. `Part.makePolygon` → `Part.Face` → `face.extrude(axis_dir * height)`.
    5. `prism.makeFillet(r, vertical_edges)` — fillet arcs centred on
       the original cylinder positions, giving exact Minkowski-sum geometry.
  - **Uniform-taper cones (r1 ≠ r2, all same r1 and same r2)** →
    `_build_tapered_rounded_prism`: loft between two rounded-polygon wires.
    Constraints: all cones same direction (not anti-parallel), all bases at
    same z-level, all tops at same z-level.
    Algorithm:
    1. Build 2-D convex hull of centre positions.
    2. `make_rounded_polygon_wire(hull, r1, z_base, …)` → bottom wire.
    3. `make_rounded_polygon_wire(hull, r2, z_top,  …)` → top wire.
    4. `Part.makeLoft([bottom_wire, top_wire], solid=True)`.

#### The N_corners × 2 z-levels pattern ("8-cylinder" hull)
OpenSCAD's `hull()` of a 3-D cylinder arrangement commonly emits N cylinders
at each z-extreme (e.g. 4 corners × 2 z-levels = 8 cylinders).  This is **not
a bug**: you need all N corners at *both* z-levels to correctly define the full
z-span AND the full 2-D footprint simultaneously.  Using only N cylinders (e.g.
2 from the top layer + 2 from the bottom) would leave corners undefined at one
level and produce a wrong shape.

`hull_parallel_cylinders_grid` handles this transparently: base and top of each
cylinder project to the same 2-D point (for Z-axis-aligned cylinders), so the
16 projected points (8 cylinders × 2 ends) collapse to 4 unique 2-D vertices
via `convex_hull_2d` deduplication, and z_min/z_max correctly span the full
height.  No special-casing needed.

### Utility (`process_hull_utils.py`)
- `convex_hull_2d(pts)` — 2-D Graham scan, returns CCW vertices,
  float-tolerance deduplication.
- `make_rounded_polygon_wire(hull_2d, r, z_ax, …)` — arc-based rounded-polygon
  wire at a given axial position with given radius.  Used by
  `_build_tapered_rounded_prism` for cone hulls.

## New SCAD object workflow
- **Seed template**: `freecad/OpenSCAD_Ext/Resources/new_scad_template.scad` — contains
  workflow comments (save → render) and a default `cube([10,10,10])`.  When a new SCAD
  object is created, `SCADObject.editFile()` seeds the `.scad` file from this template,
  replacing `{{NAME}}` with the object name.  Template seeding fires when the file does
  not yet exist or is empty.
- **Unique default names**: `newSCAD._unique_scad_name()` auto-increments
  (`SCAD_Object`, `SCAD_Object_1`, …) so two new objects never share a `.scad` file.

## Importer versioning
- **ImportAstCSG** (`importers/importASTCSG.py`) is the active AST-based importer.
  - Current version: `0.8.4`  (set via `__version__` at top of file)
  - **Only bump `__version__` when the user confirms testing is complete and the
    change is ready to push to the main repo.** Do not bump during development
    iterations. Bug fix → patch (0.8.x → 0.8.x+1), significant new feature → minor
    (0.8.x → 0.9.0).
  - Version is printed twice to the Report View: at start and end of `processCSG()`.
- **ImportAltCSG** (`importers/importAltCSG.py`) is legacy code copied from the
  AlternateOpenSCAD workbench. It will be maintained alongside ImportAstCSG for the
  foreseeable future.
  - Reports itself as `ImportAltCSG Version 0.6a` in the Report View.
- **newImportCSG** (`importers/newImportCSG.py`) is a transitional importer — to be removed
  once ImportAstCSG is complete.

## CSG parameter parsing (`parse_csg_to_AST.py`)
Named parameters (e.g. `center = false`, `center = true`) are parsed via
`parse_scad_argument()`, which handles OpenSCAD's lowercase `true`/`false`.
Do **not** use `ast.literal_eval()` directly for named parameter values —
Python rejects lowercase booleans and falls back to a raw string, which is
truthy in Python and silently misapplies centering to every primitive.

## Test file
/Users/ksloan/github/CAD_Files_Git/OpenSCAD/Ab_Tools/test-2.csg

