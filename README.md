Unified external OpenSCAD Workbench with import/export support


"""
OpenSCAD AST → FreeCAD Import Strategy:

1. Native BRep Preferred:
   - Try to build hulls, booleans, and primitives as FreeCAD Shapes directly.
   - Preserves parametric editing and high-accuracy geometry.

2. OpenSCAD Fallback:
   - If native BRep fails (unsupported configurations, compound children):
       - Generate STL from SCAD string.
       - Import STL → Mesh → FreeCAD Shape.
       - Preserve $fn/$fa/$fs tessellation for consistent geometry.

3. Tessellation Handling:
   - Per-node tessellation ($fn/$fa/$fs) is stored and used where defined.
   - Defaults are applied only at top-level if missing.

4. Logging:
   - Entry/exit of each function.
   - Child processing, shape creation, and fallback events.
   - SCAD string generation for debugging.
"""

"""
========================================================================
OpenSCAD/CSG Importer – AST Node Handling Overview
========================================================================

This table summarizes how each type of AST node is handled in the current
strategy (FreeCAD OpenSCAD Workbench).

Node Type        | Handler Function                | Notes / Fallback
-----------------|---------------------------------|-----------------------------------------------------
Circle           | ast_node_to_scad() / get_tess() | Creates native FC Shape (Part.Sphere 2D/3D)
Sphere           | ast_node_to_scad() / get_tess() | Native Brep; fallback to OpenSCAD if Hull cannot process
Cube             | ast_node_to_scad() / get_tess() | Native Brep
Polygon / Polyline | ast_node_to_scad()             | 2D shapes; may require OpenSCAD fallback for Hull
Hull             | process_hull()                  | Tries native Brep Hull; if fails, calls fallback_to_OpenSCAD()
Minkowski        | process_hull()                  | Same as Hull
Union            | process_boolean()               | Tries Brep union; fallback to OpenSCAD if impossible
Difference       | process_boolean()               | Tries Brep; fallback if needed
Intersection     | process_boolean()               | Tries Brep; fallback if needed
Translate        | process_transform()             | Applies translation to child shape(s)
Rotate           | process_transform()             | Applies rotation
MultMatrix       | process_transform()             | Applies general 4x4 transform
Other / Unknown  | fallback_to_OpenSCAD()          | Node passed directly to OpenSCAD for STL conversion

------------------------------------------------------------------------
Fallback Strategy:
- For nodes that cannot produce a valid FreeCAD Shape (e.g., mixed 2D/3D
  Hull, complex Minkowski, or unsupported primitives), the AST subtree is
  serialized to OpenSCAD code.
- OpenSCAD CLI is invoked to generate STL; the STL is imported into FreeCAD
  as Mesh → Shape.
- Tessellation ($fn, $fa, $fs) is preserved per-node where possible.

Helper Functions:
- get_tess(node)                : Returns node tessellation, defaults to global.
- ast_node_to_scad(node, ...)   : Converts an AST node to OpenSCAD code.
- child_has_generated_shape(node): Checks if child already produced a Shape.
- fallback_to_OpenSCAD(doc, node, node_type)
                                : Handles OpenSCAD STL fallback.
- write_log(level, message)     : Logs processing steps for debugging.
========================================================================
"""

