# BRepOffsetAPI_ThruSections — twisted / self-intersecting result reported valid

## Summary

`BRepOffsetAPI_ThruSections` (a ruled, non-solid loft) over **two
equivalent-topology closed wires** connects them with the **wrong vertex
correspondence**. The resulting ruled surface **twists and self-intersects**,
yet `BRepCheck_Analyzer` reports it **valid**. Sewing the loft faces into a
solid gives a volume of **~1450**, where the true convex-hull volume of the two
sections is **~15700** — the bridge collapses to ~9 % of the expected size.

Because the shape is reported valid, downstream boolean operations consume it
silently and produce wrong geometry.

## The two wires

Both `wireA.brep` and `wireB.brep` are:

- closed, **9 edges** each: **7 line segments + 2 circular arcs** (rounded-
  rectangle outlines),
- non-planar loops (they include axial Z segments),
- near-parallel, different size:
  - `wireA`: half-extent y ≈ ±8.06, arc radius 8.064, plane at z = −25.5
  - `wireB`: half-extent y ≈ ±6.06, arc radius 6.064, plane at z = −27

`shapeA.brep` / `shapeB.brep` are the original solids the wires are the
silhouettes of, included for context only.

## Reproduce

### Python (FreeCAD / pyOCCT-style)
Run `reproduce_loft.py` from this directory in the FreeCAD Python console.
Expected output: `loft ... valid=True` and a sewn-solid volume ≈ 1450.

### C++ (pure OCCT)
`reproduce_loft.cpp`:

```
g++ -std=c++14 reproduce_loft.cpp -o reproduce_loft \
    -I$CASROOT/include/opencascade -L$CASROOT/lib \
    -lTKBRep -lTKernel -lTKMath -lTKG3d -lTKGeomBase \
    -lTKTopAlgo -lTKOffset -lTKPrim -lTKShHealing
./reproduce_loft          # run from this directory
```

It reads the two wires via `BRepTools::Read`, builds
`BRepOffsetAPI_ThruSections(/*solid*/Standard_False, /*ruled*/Standard_False)`,
prints `BRepCheck_Analyzer::IsValid()` (= true), then sews + makes a solid and
prints the collapsed volume.

## Expected vs actual

- **Expected:** a clean ruled band between the two outlines (their convex hull /
  loft), volume ≈ 15700, no self-intersection.
- **Actual:** twisted/self-intersecting band, volume ≈ 1450, `IsValid() == true`.

## Environment

FreeCAD 1.1.1, OCCT 7.8.1.
