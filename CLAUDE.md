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
`processHull.py` → `try_hull()` collects children via `_descend()` and dispatches
to the analytical primitive path first, then a shape-based BRep path.

### `_descend()` — child collection
Walks hull children accumulating transform matrices into two buckets:
`primitives` (simple AST nodes) and `shapes` (evaluated BRep for complex ops).
- **Transparent wrappers** `group`, `color`, `multmatrix` → recurse.
- **`hull` and `union`** → **flattened**: `hull(A ∪ B, …) ≡ hull(A, B, …)`, so a
  union contributes its members directly, exactly like a nested hull. This keeps
  the analytical primitive path available and avoids a lone `union` collapsing to
  a single fused shape (which would lose the primitive path and fall back).
- **`sphere`/`cube`/`cylinder`** → collected as primitives.
- **`intersection`** → approximated by its first primitive child, since
  `hull(A ∩ B, …) ⊆ hull(A, …)`. If no primitive child exists, the intersection
  is evaluated to a shape.
- **Any other op** (`difference`, `minkowski`, `linear_extrude`, `offset`, …) →
  fully evaluated via `process_AST_node()` and added to `shapes`.

> Historical note: the strict `collect_primitives()` collector (which returned
> `False` → OpenSCAD CLI fallback on any non-primitive, and carried the
> `_subtree_has_complex_op()` intersection guard) has been **removed**. The live
> path is `_descend()`, whose intersection handling takes the first primitive
> without that guard.

### Dispatch paths (`try_hull`)
1. **Path 1 — analytical** (all children primitives, no complex shapes):
   `normalize_primitives()` → `try_hull_dispatch()` → type-specific handlers
   (`hull_spheres`, `hull_cylinders_cones`, `hull_cubes`, `hull_cylinders_and_cube`).
   - **2-D primitives** (`circle`/`square`/`polygon`) are collected by `_descend`
     just like their 3-D cousins.  When *all* children are 2-D, `try_hull_dispatch`
     routes to `hull_2d` (`process_hull_2d.py`) which returns a **planar Face**:
     equal-radius circles → exact rounded polygon (`make_rounded_polygon_wire`);
     otherwise the convex hull of sampled boundary points → polygon Face.  This
     avoids the 3-D `ConvexHull` "need ≥4 unique points" failure on coplanar 2-D
     input.  (Limitation: 2-D hulls whose children are *complex* 2-D ops — e.g.
     `offset`, `projection`, 2-D booleans — still take the shape-based path and
     need a coplanar-aware fallback; future work.)
2. **Path 2 — shape-based** (mixed/complex children): each primitive/shape is
   converted to a `Part.Shape`, then:
   - **sphere + polyhedron** → `hull_sphere_polyhedron` (`process_hull_mixed_curve.py`).
   - **exactly 2 shapes** → `hull_brep_loft` (`process_hull_brep_loft.py`) — smooth
     BRep via silhouette extraction + loft (see below).
   - **fallback** → `hull_brep_shapes` (`process_hull_brep.py`) — scipy `ConvexHull`,
     faceted but always succeeds (no OpenSCAD CLI needed).

### General BRep loft (`process_hull_brep_loft.py`)
`hull_brep_loft(shapes)` builds a smooth hull of two BRep shapes:
1. Axis = COG(A) → COG(B). Classify each shape's faces vs the away-direction:
   outer (+1), inner (−1), transverse (0), curved-mixed (2).
2. `_extract_silhouette()` harvests silhouette edges = edges of **inner *or*
   curved** faces shared with a cap (outer+transverse) face, sorted into closed
   wires. Including curved faces is essential: a cylinder's lateral surface is
   curved-mixed, and harvesting its shared edge yields the **cap-rim circle** as
   the silhouette loop; rounded corners likewise stitch into the outline.
3. `Part.makeLoft` bridges A's silhouette wire(s) to B's (native loft, BSpline
   resample fallback).
4. Assemble cap faces A + bridge + cap faces B → `sewShape` → `Part.makeSolid`.

Returns `None` on any failure → caller uses the faceted fallback.

**Loft result is validated** in `try_hull`: a successful loft is accepted only
when its volume is within 5% of the faceted convex hull (always correct) and
`isValid()`.  OCC `ThruSections` can connect two equivalent-topology wires with
the wrong vertex correspondence → a twisted/self-intersecting solid whose volume
collapses (~9% in `compact_nut_seat`) yet still reports `isValid()==True`; such a
loft would silently corrupt downstream booleans, so it's rejected → faceted.

When a loft fails, `try_hull` calls `_export_failed_loft(all_shapes)`, which saves
the two input shapes as `<csg-stem>_loftfail_<n>_A.brep` / `_B.brep` (plus an
`_info.txt` with placement/bbox/validity) **in the same directory as the CSG**
being imported, for offline inspection.  The CSG dir/stem are propagated from
`importASTCSG.processCSG` via `processAST._current_csg_dir` / `_current_csg_stem`
(no-op for `.scad` imports processed from a temp file, where the dir is unknown).
The `HullLoftTest_CMD` GUI command (`commands/hullLoftTest.py`) lofts the two
selected objects so a failed pair can be reloaded and iterated on in isolation.

### Concentric coaxial prisms — smooth hull (`hull_concentric_sections`)
The silhouette-loft above has no single A→B bridge band for **concentric** shapes
(two coaxial near-concentric prisms, e.g. `compact_nut_seat`'s base = two
`center=true` extruded `union(square, 2 circles)` profiles, one wide+short, one
thin+tall).  When the COGs are near-coincident (`|d| ≤ 5%·size`), `hull_brep_loft`
routes to `hull_concentric_sections(A, B, axis)`:
1. `A.fuse(B)`, then for each end where the narrower shape protrudes past the
   wider, fuse a **taper solid** (`_frustum_solid`) lofting the wider shape's
   end-cap wire to the narrower's; `removeSplitter()`.
2. **`_cap_wire(shape, axis, want_max)`** returns each shape's REAL terminal cap
   outline (no `slice()`).  Crucially the cap is often **tiled**: a 2-D
   `union(square, 2 circles)` extrude leaves the end cap as several coplanar
   sub-faces sharing internal seam edges.  Taking one sub-face's `OuterWire`
   would bridge only that tile and drop the straight "square bits" from the
   taper.  So `_cap_wire` collects ALL coplanar cap faces at the extreme axial
   level and rebuilds the outer outline as the **edges used by exactly one tile**
   (shared internal seams appear twice and cancel) → the full mixed line+arc
   outline, identical topology between wide and narrow.
3. **`_piecewise_bridge`** pairs the two cap wires edge-for-edge (correspondence
   chosen explicitly, so OCC never twists — cf. OCCT #1315); **Line↔Line pairs
   build exact planar quads** (so `removeSplitter` merges them with the body's
   coplanar flat faces — a ruled BSpline would leave a spurious seam), arc↔arc
   pairs stay smooth ruled surfaces.

> Developer .brep dumps (cap wires, tapers, OCCT repro) are gated behind
> `process_hull_brep_loft.EXPORT_DEBUG` (default False → never written on a
> normal import); when on they go to `DEBUG_DIR`.  Dev toggles in `processHull`:
> `HULL_STOP_AFTER_FIRST` (halt after first accepted hull, add it to the doc),
> `HULL_FORCE_FACETED` (never accept a smooth loft).  All default False.

### Hull — known limitations & roadmap (see `Developer_Notes/BrepHullLofts_Architecture.md`)
- **Single-loft limitation:** `hull_brep_loft` uses one silhouette loop per shape
  + one `makeLoft`; mismatched outline topology only partially bridges. The true
  hull side is a *patchwork* of ruled/planar patches. Roadmap: **option 2**
  (multi-patch tangent construction) first, **option 1** (piecewise sub-wire
  lofts) as fallback.
- **Analytical hull ignores `$fn`:** low-`$fn` cylinders (e.g. `$fn=6` nut traps)
  are hulled as *round* instead of *hex*. Fix: gate analytical collection on
  `_use_brep($fn)`; route faceted cylinders to the shape-based path.
- `try_hull_dispatch` is wrapped in try/except so a handler exception never
  aborts the whole import (falls through to the shape-based/faceted path).

> Known limitation: the silhouette attaches at the cap rim, which is the exact
> convex hull when one shape sits along the other's axis but only an
> approximation when the true support plane is tangent to a curved *side*. Full
> tangent-silhouette (`n·e_away = 0` mid-face) and curved cap-splitting are
> future refinements.

### Instrumentation
`processHull.HULL_DEBUG` (module flag) gates the `[HULL]`/`[LOFT]` dispatch trace
to the Report View; `write_log` always records it to `workbench.log`. Set
`HULL_DEBUG = False` before merging to main (Report View policy below).

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
  - Current version: `0.11.0`  (set via `__version__` at top of file)
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

## Report View / panel output policy
All normal and fallback operations are silent in the FreeCAD Report View.
Only genuine geometry loss (a node that failed even after OpenSCAD fallback)
produces a `PrintError` panel message.

- `write_log(level, msg)` — log file only, never touches the panel.
- `FreeCAD.Console.PrintError(msg)` — used explicitly at `_nodes_failed` sites.
- Module-level `print()` calls in importer files have been removed (they fire on
  import and FreeCAD redirects stdout to the Report View).
- OpenSCAD subprocess stdout/stderr on success is routed to `write_log` in
  `OpenSCADUtils.py`; errors (non-zero returncode) still raise `OpenSCADError`.
- Debug calls like `dump_ast_node()` must not be left in live code paths.

## CSG parameter parsing (`parse_csg_to_AST.py`)
Named parameters (e.g. `center = false`, `center = true`) are parsed via
`parse_scad_argument()`, which handles OpenSCAD's lowercase `true`/`false`.
Do **not** use `ast.literal_eval()` directly for named parameter values —
Python rejects lowercase booleans and falls back to a raw string, which is
truthy in Python and silently misapplies centering to every primitive.

## Transforms — `multmatrix` reflections (`processAST.py`)
Transforms propagate top-down as `App.Placement` and are applied (baked) at the
boolean/primitive "sites".  A **reflection** (an OpenSCAD `mirror()`, which emits
a `multmatrix` with **negative determinant**, e.g. `diag(1,1,-1)`) CANNOT be
represented by an `App.Placement` (rotation + translation only): `App.Placement(m)`
silently drops the mirror and keeps a rotation, so a mirrored subtree lands in the
wrong orientation.

Handling in the `multmatrix` branch: when `m.determinant() < 0` **and** the child
is a **3-D solid**, bake the full transform into the geometry —
`s.transformGeometry(m.multiply(pl.Matrix))` — and return an **identity**
Placement.  Notes:
- **Do NOT `reverse()` the result.** `transformGeometry` already produces a
  correctly-oriented mirrored solid; an extra `reverse()` turns it inside-out, so
  a later `difference()` acts like an `intersection()` (verified on
  `subTests/test_mirror/test_mirror_solid.scad`: block − mirror(L) must give an
  L-notch, not the L).
- **2-D faces stay on the placement path** (`App.Placement(m).multiply(pl)`):
  their extrude/union pipeline does not accept a baked face (yields a Null
  extrude), and the 2-D mirrors in practice wrap symmetric profiles (a circle)
  where the dropped reflection is harmless.

## 2D operations — `offset` (`processAST.py`)
OpenSCAD's `offset()` is a **2-D** operation. The handler dispatches on the
child's dimensionality:
- **2-D** child (Face/Wire, zero volume) → `Part.Shape.makeOffset2D(r, join, …)`,
  which grows the profile in its own plane and returns a planar Face.
  `join`: `0` = arc (round, OpenSCAD `r=`), `2` = intersection (sharp, `delta=`).
- **3-D** child (a real Solid — keyed on `len(shape.Solids)`, **not** Volume,
  since open shells can report a spurious volume) → **skip the offset, pass the
  child through, and `PrintWarning`**. A solid child is invalid OpenSCAD
  `offset()` input and almost always means a 2-D op in the child subtree was
  wrongly evaluated to a solid upstream — the handler logs the child node-types
  and shape characteristics (`solids/faces/vol`) to help locate the cause.
  (Earlier this `raise`d `ValueError`, which aborted the whole file; that was too
  aggressive on real OpenFlexure files.)

> Do **not** use `makeOffsetShape(r, tol, fill=True)` for 2-D offsets — it is a
> 3-D shell/solid operation that, on a flat face, builds a thin solid whose extra
> side/top faces break a downstream `linear_extrude` (degenerate solids →
> "Null shape" at the fuse). `linear_extrude` also now skips null/invalid solids
> before fusing as a defensive guard.

## Test file
/Users/ksloan/github/CAD_Files_Git/OpenSCAD/Ab_Tools/test-2.csg

### Hull / BRep loft test cases
`testcases/Hull_Tests/BRepHull/` — e.g. `test_hull_linear_extrude.csg`
(`hull()` of a `linear_extrude(offset(square))` slab + a translated cylinder;
exercises the 2-D offset fix and the curved-silhouette loft path).

### `compact_nut_seat` isolation sub-tests (`testcases/Hull_Tests/openflexure_csgs/subTests/`)
Minimal reproducers carved out of `compact_nut_seat_fn0.csg` while debugging:
- `test_compact_nut_base/` — the first hull only (two concentric extruded
  `union(square, 2 circles)` prisms).  Exercises `hull_concentric_sections` +
  the `_cap_wire` cap-tile reconstruction.  **Imports smooth & correct.**
- `test_mirror/test_mirror_solid.scad` — minimal `multmatrix` reflection test
  (union of an L + its X-mirror; block − mirror(L) notch).  **Correct.**
- `test_compact_nut_arms/` — `test_halfA.csg` (base block, correct), `test_halfB.csg`
  (the arms subtree), `test_arm1.csg` (a single arm).  **KNOWN-BROKEN:** a single
  arm imports as "missing arm" in native BRep — see TODO below / `Developer_Notes`.

