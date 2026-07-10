# TODO — smooth multi-shape hulls (arm strut tessellation)

Status: v0.12.0 (committed `9ee7c1e`). compact_nut_seat imports closely matching
OpenSCAD; the arm STRUT outer surface is faceted (tessellated).  User wants it
smooth.  Deferred from 2026-06-19 — analysis below.

## Where the faceting comes from (two sources)

**1. The visible strut = a hull of 3+ complex shapes.**
In the `[HULL]` trace for each arm:
```
[HULL] Collected: 2 primitives, 1 complex shapes
[HULL] Path 2: shape-based with 3 total shape(s)
[HULL] classified: spheres=0 polys=3
[HULL] using faceted BRep
```
The strut is `hull(half-sphere, cylinder, cylinder)` — a clipped sphere (the
`difference(sphere, cube(99))` half-space cap) plus two cylinders.  **`hull_brep_loft`
(the smooth silhouette-loft path in `process_hull_brep_loft.py`) handles EXACTLY
2 shapes.**  Any hull of 3+ shapes (`len(all_shapes) != 2`) falls straight through
to the faceted scipy `ConvexHull` (`hull_brep_shapes`) → planar facets.  That is
why the strut facets.

Reproducer hull — `subTests/test_compact_nut_arms/test_arm1.csg` line 8:
`hull{ difference(sphere r5 @T(17.5,-12.2,27), cube[99] clip);
       cylinder($fn0 h0.05 r5); cylinder($fn0 h16.3328 r4) }`
The thin `h=0.05 r=5` cylinder is essentially coincident with the sphere cap
(forms the rounded end); the `r4 h16.33` cylinder is the strut body.  So it is
effectively `hull(rounded-end, strut-cylinder)` = 2 meaningful shapes + 1 tiny one.

**2. `hull_cylinders_and_cube` — "cylinders span different axial extents".**
`process_hull_mixed.py` line ~291: the analytical path extrudes a CONSTANT
cross-section over `[a_cyl_min, a_cyl_max]` and only works when all cylinders
share the same axial range; otherwise it `return None` → faceted.  In
compact_nut the failing hulls have COAXIAL cylinders (same x,y, different
heights) + a thin cube, e.g. test_arm1 line 235:
`hull{ cube[6.0005,0.05,3]@(-3,3.41,0); cyl($fn6 h3 r3.46); cyl($fn0 h4 r3.2) }`.

## Fix options (for tomorrow)

A. **Generalise `hull_brep_loft` to N shapes.**  Multi-shape silhouette
   extraction + lofting with changing cross-section topology along the axis.
   Substantial — comparable to the `hull_concentric_sections` work (which already
   solves changing-topology lofting for the 2-shape concentric case; reuse
   `_cap_wire` tile reconstruction + `_piecewise_bridge` edge-type alignment).
B. **Cheap pre-step:** drop negligibly-small shapes from the hull collection
   (e.g. the `h=0.05` cylinder), reducing 3→2 so the existing smooth loft fires.
   Exact only when the dropped shape is inside the hull of the others — verify
   before dropping.  Would smooth the strut specifically without the full N-shape
   work.  CHECK FIRST whether this is geometrically safe here.
C. **`hull_cylinders_and_cube` axial sectioning:** divide `[a_min,a_max]` at each
   cylinder start/end; per interval build the convex-hull cross-section of the
   active primitives (coaxial cylinders → max-radius circle) + cube projection;
   loft between intervals.  Handles source #2 (coaxial case is the simple one).

Suggested order: try **B** first (quick win on the visible strut), then **C**,
then **A** if a general solution is wanted.

## 2026-06-20 session — progress, current blocker, working-tree state

### What was done (UNCOMMITTED, working tree only — do NOT commit yet)
1. **Transform-placement bug fix** (`processHull.py` `_extract_shape`): evaluated
   COMPLEX hull children (e.g. a `difference` half-sphere) were left in their
   local frame while sibling primitives got the accumulated parent matrix, so
   they landed in different coordinate systems.  `_extract_shape(result, matrix)`
   now applies the accumulated `matrix` (both call sites pass it).  This is a
   genuine correctness fix (the faceted strut was previously mis-placed, reaching
   the origin) — keep it, but it touches EVERY complex hull child, so re-run all
   hull tests for regressions before committing.
2. **Cluster+fuse N→2 path** (`process_hull_brep_loft.py` `hull_brep_loft_multi`
   + `_cluster_connected`/`_fuse_cluster`/`_shapes_touch`): a hull of N shapes
   forming exactly 2 connected groups fuses each group and lofts the 2 ends
   (lossless — hull is invariant under unioning subsets).  Dispatcher gate in
   `processHull` changed `== 2` → `>= 2` calling `hull_brep_loft_multi`.
   Strut now correctly clusters `3 -> 2 (sizes [2,1])`.
3. **Section-loft for oblique bridges** (`hull_loft_sections` + `_ray_hit_convex`
   + `_smooth_section_wire`): slices the convex hull ⊥ its PCA elongation axis,
   fits a periodic-BSpline outline per slice, lofts smooth.  Gated in `processHull`
   on `loft_result is not None` (a built-but-rejected cap-rim loft = the oblique
   signature) so it does NOT run on every faceted hull (that caused the earlier
   IMPORT HANG — now fixed).  Validated against faceted volume (rel<0.05).
   Defaults `n_stations=20, n_out=48`.  Core slicing math unit-checked numpy-only
   (tilted-box volume exact; ray-resample within 0.74%).

### Current blocker — strut is smooth but DISCONNECTED from its cylinders (gap)
The section-loft gives a smooth, watertight, ~1%-volume-correct strut BODY, but:
- It caps the slice extremes flat ⊥ PCA axis a little inside the true ends →
  **blunt end**, and the oblique PCA slicing renders the cylinder region as
  ELLIPSES → the body does not match the cylinder's circular curvature.
- `end-fuse kept 0/3 originals` → the real cylinder is NOT merged in, so the
  loft body does not reach/overlap the cylinders.  Net effect in the log:
  `union ... -> result vol=3634.3 solids=2` and that `solids=2`/`solids=3`
  persists through the arm's difference/union — i.e. **each arm is a separate
  solid floating with a visible GAP to its cylinders.**  This is a regression vs
  the faceted hull, which at least stayed connected (1 solid).
- Tried sectioning ⊥ the cylinder axis instead: WORSE — slice centres jump
  sideways across the bridge, loft splits into disconnected solids.  Reverted to
  PCA axis.

Root cause is architectural: a SINGLE global section axis can't both (a) keep
slice centres monotonic for a clean loft AND (b) match the cylinder's circular
cross-sections, on a 62°-oblique strut.  OpenSCAD's result is just the exact
convex hull, where the cylinder surface melds tangentially into the bridge.

### Next-step options (decide on resume)
- **A — Multi-patch tangent hull (proper fix; roadmap "option 2").** Keep the
  cylinder's and sphere's own faces where they lie on the hull boundary; bridge
  their true silhouette LIMBS (n·e_away=0 on curved faces, not the cap rim) with
  tangent ruled/lofted patches; sew.  Melds like OpenSCAD, no gap.  Substantial,
  many import round-trips (no local FreeCAD here).
- **B — Make the section-loft CONNECT (cheaper interim).** Force the end slices
  to coincide with the real shape caps and/or guarantee the loft overlaps the
  cylinders so the union is 1 solid (fix the gap).  Still won't tangent-match the
  cylinder curvature, but removes the disconnection regression.
- **C — Meanwhile, consider gating section-loft OFF** (or only accept it when the
  result stays connected) so the committed behaviour stays the connected faceted
  hull rather than a gapped smooth one.

`compact_nut_seat_fn0` reference (OpenSCAD): arms are the smooth convex hull,
cylinders melded in with a fillet-like blend, NO gap.

### Still pending
- Coaxial nut-trap hull (`hull_cylinders_and_cube` "different axial extents")
  still facets — axial sectioning (source #2 / option C in the original list,
  task not yet started).

## Context — what's blocked on the OCC bug (NOT this task)
The slot opening width / arm-bottom-Z are imprecise because the top-level
`difference` subtracts the arm's `union(cube999, cylinders)` intersection result,
which OCC computes wrong (the captured `OCCT/intersection_bug`).  That is a
non-half-space clip the `_clamp_tool` can't fix.  Separate from the tessellation.
(A box-clip experiment for half-space clips cleaned the BASE but made no visible
difference to the final model — reverted, not committed.)
