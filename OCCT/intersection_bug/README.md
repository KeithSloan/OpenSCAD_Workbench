# BRepAlgoAPI_Common — intersection result larger than an operand

## Summary

`A.common(B)` (`BRepAlgoAPI_Common`) returns a solid whose **bounding box is far
larger than operand A**.  An intersection must satisfy `A ∩ B ⊆ A`, so the result
can never extend beyond A's bounding box — but here it does, by two orders of
magnitude.  No exception is raised and `BRepCheck_Analyzer` reports the result
**valid**, so the garbage propagates silently into downstream booleans.

The trigger is an **extreme scale mismatch** between the operands: A is a normal
~10 mm part, while B is built the way OpenSCAD emits half-space / clip geometry —
a ~1998 mm cube (`cube(999)`) fused with several thin/long cylinders, some only
`h = 0.05 mm`.  The ratio of the largest extent to the smallest feature is
≈ 20000 : 1, beyond OCC's floating-point boolean tolerance.  CGAL (OpenSCAD's
kernel, exact arithmetic) evaluates the same intersection correctly.

## The two shapes

- **`opA.brep`** — a tall thin extruded prism (an OpenSCAD `linear_extrude` used
  as a clip), bounding box ≈ `x[-6.04, 12.50]  y[-6.46, 6.46]  z[-499.5, 499.5]`,
  volume ≈ 221 492, valid, closed, 1 solid.
- **`opB.brep`** — `union(cube(999) , several h=0.05..999 cylinders)`, bounding
  box ≈ `x[-999, 999]  y[-999, 999]  z[-974, 1024]`, volume ≈ 2.82e9, valid,
  closed, 1 solid.
- **`result_garbage.brep`** — the actual `opA.common(opB)` output, bounding box
  ≈ `x[-999, 999]  y[-999, 999]  z[-499.5, 499.5]`, volume ≈ 120 366.

## Expected vs actual

- **Expected:** `opA.common(opB) ⊆ opA`, so the result bbox must lie within
  `x[-6.04, 12.50]`.
- **Actual:** the result bbox is `x[-999, 999]` — it spills ~80× outside opA in
  X and Y, while `IsValid()` returns true.

## Reproduce

### Python (FreeCAD console, from this directory)
Run `reproduce_intersection.py`.  Expected print:
`result spills outside opA bbox (BUG): True`.

### C++ (pure OCCT)
`reproduce_intersection.cpp`:
```
g++ -std=c++14 reproduce_intersection.cpp -o reproduce_intersection \
    -I$CASROOT/include/opencascade -L$CASROOT/lib \
    -lTKBRep -lTKernel -lTKMath -lTKG3d -lTKGeomBase \
    -lTKTopAlgo -lTKBO -lTKShHealing
./reproduce_intersection      # run from this directory
```
It reads the two shapes, runs `BRepAlgoAPI_Common`, prints `IsValid()` (= true),
and prints the result bounding box (X spans ~[-999, 999], far outside opA).

## Environment

FreeCAD 1.1.1, OCCT 7.8.1.

## Notes / workaround

In the importer we work around this by *clamping* an oversized boolean tool to
the other operand's bounding box (+margin) before `cut`/`common` — exact, since
geometry outside A can't affect `A.cut/common(B)` — which keeps OCC at ~10 mm
scale.  It mitigates but does not fully cure the worst cases (the clamp's own
`common` with the 999-tool can still leave stray ±999 geometry), which is why the
underlying defect is reported here.
