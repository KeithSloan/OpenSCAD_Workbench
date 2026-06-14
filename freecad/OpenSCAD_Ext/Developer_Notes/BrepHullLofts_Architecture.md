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
| `process_hull_utils.py` | 2D convex hull, rounded polygons |
| `processAST.py` | AST processing; offset handler, linear_extrude, etc. |
