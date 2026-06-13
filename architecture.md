# Hull Processing Architecture

## Overview

The OpenSCAD workbench processes CSG files through an AST pipeline. Hull operations
(`hull()`) are handled natively in FreeCAD as BRep solids — no mesh, no OpenSCAD CLI
fallback for pure BRep geometry.

## Dispatch Chain

```
processAST(node) → Hull detected
  │
  └─ processHull.try_hull(node)
       │
       ├─ Path 1: AST-based dispatch (try_hull_dispatch)
       │     • All spheres → hull_spheres (capsule / rounded prism)
       │     • All cylinders → hull_cylinders_cones (rounded extrusion)
       │     • All cubes → hull_cubes (bounding box)
       │     • Cube + cylinders → hull_cylinders_and_cube
       │     Returns exact analytical BRep surfaces.
       │
       ├─ Path 2: Shape-based analytical (fallback)
       │     • Creates FreeCAD child shapes via process_AST_node
       │     • Classifies shapes: spheres vs polyhedra
       │     • sphere + polyhedron → hull_sphere_polyhedron
       │         - Great circle silhouette on sphere
       │         - Polyhedral silhouette (inner/cap edge boundary)
       │         - Part.makeLoft bridge between silhouettes
       │         - Hemisphere sphere cap
       │         - sewShape → Part.makeSolid (watertight)
       │         Smooth curved surfaces, no faceting.
       │
       └─ Path 3: General BRep (last resort)
             • hull_brep_shapes(shapes)
             • Point extraction: vertices + parametric grid + Fibonacci sphere
             • scipy.spatial.ConvexHull → triangulated solid
             • Faceted approximation for arbitrary BRep shapes.
```

## Key Files

| File | Purpose |
|---|---|
| `processHull.py` | Entry point: `try_hull(node)` → dispatch |
| `process_hull_spheres.py` | Analytical hull of collinear/grid spheres |
| `process_hull_cylinders.py` | Analytical hull of parallel cylinders/cones |
| `process_hull_cubes.py` | Hull of equal-size cubes |
| `process_hull_mixed.py` | Hull of cylinders + cube |
| `process_hull_mixed_curve.py` | **New** — sphere + polyhedron analytical hull |
| `process_hull_brep.py` | **New** — general BRep hull via scipy ConvexHull |
| `process_hull_utils.py` | 2D convex hull, rounded polygons, tangent frustum |
| `processAST.py` | AST processing; delegates hull to `processHull.try_hull` |
| `importASTCSG.py` | CSG import entry point |

## Test Suite

`testcases/Hull_Tests/BRepHull/` — 10 standalone `.scad` + `.csg` pairs:

| Test | Pattern | Path |
|---|---|---|
| `test_hull_two_cubes` | Two offset cubes | 1 (typed) |
| `test_hull_two_cylinders` | Two cylinders, different radii | 1 (typed) |
| `test_hull_cube_sphere` | Cube + sphere | 2 (analytical mixed) |
| `test_hull_mirror_cylinders` | Symmetric mirrored pair | 1 (typed) |
| `test_hull_four_cylinders` | 4 cylinders → rounded rect | 1 (typed) |
| `test_sequential_hull` | Multi-segment sweep | 1 (typed, sequential) |
| `test_hull_difference` | Hull then Boolean cut | 3 (general BRep) |
| `test_hull_linear_extrude` | 2D extrude + 3D cylinder | 3 (general BRep) |
| `test_hull_minkowski` | Minkowski-rounded children | 3 (general BRep) |
| `test_hull_cone_to_cylinder` | Cone + cylinder | 1 (typed) |

## Design Decisions

1. **AST-first for primitives.** Simple combinations (all-spheres, all-cylinders)
   are handled directly from AST geometry info without creating intermediate shapes.
   This is faster and produces exact analytical surfaces.

2. **Shape-based fallback for mixed types.** When AST dispatch fails (e.g.
   sphere+cube), child shapes are created and analytical mixed handlers operate
   on actual BRep geometry (face classification, silhouette extraction, lofting).

3. **General BRep as last resort.** For Boolean results, imported STEP, NURBS
   solids, or any other non-primitive geometry, point-sampling + scipy ConvexHull
   produces a faceted approximation.

4. **No OpenSCAD CLI fallback for BRep.** OpenSCAD is only invoked when mesh
   objects are involved, not for BRep geometry.
