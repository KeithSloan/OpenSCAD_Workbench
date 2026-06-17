# TODO — `compact_nut_seat` arm assembly (native BRep)

Status as of v0.11.0 (GeneralBrepLofts). Two wins committed: the concentric
smooth base hull (`hull_concentric_sections` + `_cap_wire` cap-tile
reconstruction) and the `multmatrix` reflection fix. Both verified in isolation.

## The remaining problem
Importing the **full** `compact_nut_seat_fn0.csg` natively produces the base +
two floating nut-cylinders with the **connecting arm struts missing**. Isolated
cleanly to a single arm:

- `testcases/Hull_Tests/openflexure_csgs/subTests/test_compact_nut_arms/test_arm1.csg`
  → imports as **"missing arm"** (the whole arm subtree vanishes).
- OpenSCAD renders the same subtree (`test_halfB.csg`) correctly, so the geometry
  is valid — the importer is dropping it.
- `test_halfA.csg` (base block) imports correct + smooth → base work is sound.

## Most likely root cause
The arms were probably **never assembled correctly in native BRep** — they came
via the whole-file OpenSCAD fallback, triggered whenever some per-node hull
failed. This session made more hulls succeed natively, which *removed* the
fallback trigger and exposed the long-broken native arm assembly.

`test_arm1.csg` builds the arm from nested `hull()` / `difference()` against
**huge clip shapes** — `cube([99,99,99])`, `cylinder(h=999, r1=999)`,
`cube([999,3.3,1])` (OpenSCAD's half-space / clip idiom). A whole arm vanishing
is the signature of:
- a clip **`difference()`** subtracting everything (half-space inverted / tool
  too big), or
- a clip **`intersection()`** returning empty (intersection approximated wrongly
  — note `_descend` approximates an `intersection` by its first primitive child).

## Next steps
1. Reduce `test_arm1.csg` further — bisect the nested `difference`/`intersection`
   blocks (comment out the clip subtrahends one at a time) until the arm
   reappears, to find which clip op eats it.
2. Instrument the `difference` / `intersection` handlers in `processAST.py` to
   log operand bounding boxes / volumes around the 999/99 clip shapes.
3. Check the `intersection` path specifically (`processAST` + `processHull._descend`
   first-primitive approximation) — a clip `intersection(body, huge_cube)` that
   returns the wrong operand would erase the body.
4. Once a single arm imports correctly, re-test `test_halfB.csg`, then the full
   `compact_nut_seat_fn0.csg`.

## Repro toggles (all default False, in `processHull` / `process_hull_brep_loft`)
- `EXPORT_DEBUG` — write cap-wire / taper `.brep` dumps to `DEBUG_DIR`.
- `HULL_FORCE_FACETED` — never accept a smooth loft (faceted base).
- `HULL_STOP_AFTER_FIRST` — halt after the first accepted hull, add it to the doc.
