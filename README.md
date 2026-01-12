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
