# BrepHullLofts — Architecture

Branch: `GeneralBrepLofts`

## Dispatch Flow

```
processAST(node) → Hull detected
  │
  └─ processHull.try_hull(node)
       │
       ├─ _descend(node.children)
       │     Walks children, never fails:
       │       sphere/cube/cylinder  → collect primitives for AST dispatch
       │       group/color/multmatrix → recurse
       │       hull AND union        → flatten  (hull(A∪B)=hull(A,B))
       │       intersection          → grab first primitive
       │       else (difference/extrude/offset/minkowski)
       │                              → process_AST_node(child) → shape[]
       │
       ├─ Path 1: AST dispatch (ALL children simple)
       │     try_hull_dispatch(primitives)
       │     • all spheres → hull_spheres (capsule/prism)
       │     • all cylinders → hull_cylinders_cones
       │     • all cubes → hull_cubes
       │     • cube + cylinders → hull_cylinders_and_cube
       │
       ├─ Path 2: shape-based
       │     Convert primitives → shapes (with transform matrices)
       │
       │     ├─ sphere+poly → hull_sphere_polyhedron()
       │     │     Great circle silhouette + poly silhouette + loft + cap
       │     │
       │     ├─ 2 shapes → hull_brep_loft()     ← smooth BRep
       │     │     Classify faces (outer/inner/transverse/curved)
       │     │     Extract silhouette: inner+CURVED edges shared w/ cap
       │     │     Part.makeLoft between wires
       │     │     sewShape → Part.makeSolid
       │     │
       │     └─ fallback → hull_brep_shapes()   ← scipy ConvexHull (faceted)
       │
       └─ return None → OpenSCAD fallback (mesh only)
```

## Curved-silhouette harvesting (key to the loft path)

`_extract_silhouette()` harvests silhouette edges from **inner *or* curved**
faces shared with a cap face. Curved faces (a cylinder's lateral surface, a
slab's rounded corners) are classified "curved-mixed" and excluded from both the
cap and inner sets; without harvesting their shared edges a curved primitive
yields no silhouette and the loft bails to faceting. Including them recovers the
loop — for a cylinder this is the **cap-rim circle**; for rounded corners it
stitches the corner arcs into the outline.

Verified on `testcases/Hull_Tests/BRepHull/test_hull_linear_extrude.csg`
(`hull()` of a `linear_extrude(offset(square))` slab + translated cylinder):
slab → 1 silhouette wire, cylinder → 1 (the rim circle), native loft OK.

**Known limitation:** the silhouette attaches at the cap rim — exact when one
shape sits along the other's axis, approximate when the true support plane is
tangent to a curved *side*. Full tangent silhouette (`n·e_away = 0` mid-face) and
curved cap-splitting are future refinements.

## Instrumentation

`processHull.HULL_DEBUG` gates the `[HULL]`/`[LOFT]` dispatch trace to the Report
View; `write_log` always records it to `workbench.log`. Set `False` before
merging to main.

## Modules

| File | Purpose |
|---|---|
| `processHull.py` | Entry: try_hull(), _descend(), dispatch |
| `process_hull_spheres.py` | Analytical hull of spheres |
| `process_hull_cylinders.py` | Analytical hull of cylinders/cones |
| `process_hull_cubes.py` | Hull of equal-size cubes |
| `process_hull_mixed.py` | Hull of cylinders + cube |
| `process_hull_mixed_curve.py` | sphere + polyhedron analytical hull |
| `process_hull_brep_loft.py` | **NEW** — general silhouette + loft (2 shapes) |
| `process_hull_brep.py` | scipy ConvexHull faceted fallback |
| `process_hull_2d.py` | **NEW** — hull of 2-D primitives (circle/square/polygon) |
| `process_hull_utils.py` | 2D convex hull, rounded polygons |
| `processAST.py` | AST processing; offset handler, linear_extrude, etc. |
| `commands/hullLoftTest.py` | GUI test command: loft the 2 selected objects |

## Robustness & debug aids (current state)

- **Dispatch never aborts the import.** `try_hull` wraps `try_hull_dispatch` in
  try/except — any analytical handler that raises falls through to the
  shape-based path (was: an uncaught `hull_cubes` `ValueError` aborted whole
  files).
- **`hull_cubes`** uses cube *corners* (centre ± size/2), not centres, and
  guards degenerate boxes → `None`.  (Centres alone gave a too-small/zero box.)
- **Loft COG guard** — `Part.Compound` has no `CenterOfMass`; `_cog()` falls
  back to the bbox centre.
- **Failed-loft export** — `_export_failed_loft` saves the two input shapes as
  `<stem>_loftfail_<n>_A/B.brep` (+ `_info.txt`) next to the CSG, for offline
  inspection.  Pairs with the **Test: Hull BRep Loft** GUI command
  (`HullLoftTest_CMD`), which lofts the two selected objects.

## The single-loft limitation → option 1 vs option 2

`hull_brep_loft` extracts **one** silhouette loop per shape and runs **one**
`makeLoft` between them — a single ruled band as the entire side surface.  That
is only correct when the two outlines correspond 1-to-1 all the way round.  When
the silhouette loops differ in topology (e.g. A = 4 edges, B = 10 edges, as in
`compact_nut_seat`'s first hull), `makeLoft` either fails ("BRep_API command not
done") or bridges only the parts it can pair (the rounded ends, not the straight
square edges).

The geometrically correct side surface of a convex hull of two B-Reps is a
**patchwork**: original faces on the hull, planar facets where one support plane
touches an edge/face of each, and ruled/developable patches where a support
plane rolls from an edge of A to an edge of B.

Two directions (this branch is the restore point before trying them):

- **Option 2 (try first, new branch):** multi-patch tangent construction —
  per-feature correspondence (which edge/vertex of A shares a supporting plane
  with which of B) → many ruled/planar patches → sew.  Robust for arbitrary
  pairs; the hard part is the 3-D gift-wrapping correspondence.
- **Option 1 (fallback if 2 is too hard):** keep the single loft but split each
  silhouette into matching sub-wires (arc↔arc, straight↔straight) and loft
  piecewise, so the full outline is covered.  Lower effort; sufficient for
  aligned/corresponding outlines like the coaxial-prism case.

## Other known limitations (not blockers — faceted fallback is correct)

- **Analytical hull ignores `$fn`/`fnmax`.** `normalize_primitives` reads a
  cylinder's `r/h` but not `$fn`, so a `hull()` of low-`$fn` (e.g. `$fn=6`)
  cylinders is built as a **round** capsule/prism instead of the **hex** prism
  OpenSCAD intends — wrong for nut traps.  Fix: only collect a cylinder/circle
  as an analytical primitive when `_use_brep($fn)` (round); otherwise route to
  the shape-based path (evaluated to a prism → exact faceted hull).
- `hull_cylinders_and_cube` handles only 1 cube and uniform radii; others fall
  back to faceted (correct, just not analytic).
- `hull_sphere_polyhedron` bails when the "poly" has non-flat faces → faceted.
