# BrepHullLofts — Resolved Problem Log

> **Status: RESOLVED** (branch `GeneralBrepLofts`, importer v0.9.0).
> Kept as a record of the bug and its fix.

## Original Symptom

`test_hull_linear_extrude.csg` fell back to faceting (and earlier to OpenSCAD).
The hull has two children:
1. `linear_extrude(height=3) { offset(r=1.5) { square([20,12], center=true) } }`
2. `multmatrix([...]) { cylinder(r=5, h=4) }`

The trace showed `Collected: 1 primitives, 0 complex shapes` — the
`linear_extrude` produced **no** shape, leaving only the cylinder, so the loft
could never run.

## Root Cause

The `offset` handler used `shape.makeOffsetShape(r, 1e-3, fill=True)`.
`makeOffsetShape` is a **3-D** shell/solid operation: on a flat square face it
builds a thin 3-D solid (offset in ±normal too), not an enlarged 2-D face.
`linear_extrude` then split that solid into many faces, extruded each, and the
`result.fuse(s)` merge hit a degenerate/null solid → `ValueError: Null shape`.
The whole extrude (and the hull above it) failed.

## Fix

1. **`offset` → `makeOffset2D`** (`processAST.py`). OpenSCAD `offset()` is 2-D;
   the handler now dispatches on dimensionality: 2-D child → `makeOffset2D`
   (returns a planar Face), 3-D child → raises (invalid input).
2. **Null-solid guard** before the `linear_extrude` fuse: null/invalid solids are
   skipped instead of crashing the merge.
3. **Curved-silhouette harvesting** (`process_hull_brep_loft.py`): once the slab
   existed, the loft still bailed because the cylinder's curved lateral face
   yielded no silhouette. `_extract_silhouette()` now harvests edges from inner
   *or* curved faces shared with a cap face, so the cylinder contributes its
   cap-rim circle and the slab's rounded corners stitch into one outline.

## Result

```
Collected: 1 primitives, 1 complex shapes
Path 2: shape-based with 2 total shape(s)
A: 4 cap faces, 1 wires
B: 1 cap faces, 1 wires
building bridge: 1×1 wire pairs
native loft OK → brep loft OK
```

Smooth lofted BRep hull, no faceting, no OpenSCAD fallback.

## Follow-ups (not yet done)

- Tangent silhouette (`n·e_away = 0` mid-face) for support planes tangent to a
  curved side, rather than attaching at the cap rim.
- Curved cap-splitting for guaranteed watertight solids on oblique configs.
- Set `processHull.HULL_DEBUG = False` before merging to main.
