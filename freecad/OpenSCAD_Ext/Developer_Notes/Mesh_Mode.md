# Mesh Mode — Developer Notes

_2026-05-02_

---

## 1. Background — Why Mesh Mode Exists

FreeCAD 1.1 introduced **Topological Naming Problem (TNP) element maps**.  Every
time a `Part::FeaturePython` shape is selected or highlighted, FreeCAD's
`Part::TopoShape` engine must index every face, edge, and vertex via the element
map machinery.  For complex OpenSCAD models (many small triangulated faces, deep
boolean trees) this causes the cursor to spin indefinitely whenever the user
clicks the model.

`Mesh::Feature` uses OpenInventor's `SoIndexedFaceSet` renderer — no TNP, no
element maps, no spinning cursor.  Mesh mode trades BRep accuracy for interactive
usability on large models.

---

## 2. Object Types

### AST_BRep mode — `Part::FeaturePython`

The default.  A `SCADfileBase` proxy object stores the source file path,
VarSet link, and shape.  The shape is built natively from the CSG AST or via
OpenSCAD CLI fallback.  Full parametric properties; expression-binding to VarSet
works normally.

### Mesh mode — `Mesh::Feature`

OpenSCAD renders the source file to a temporary STL.  The STL is loaded as a
`Mesh::Feature` in the document.  After `finalize_scad_mesh_object()` runs,
the `Mesh::Feature` carries all SCAD-specific properties directly (no proxy
object on the side).

---

## 3. Import Workflow for Mesh Mode

```
importFileSCAD.insert()  /  _customizer_intercept()
        │
        ▼
create_scad_object_interactive()
  → creates Part::FeaturePython (SCADfileBase proxy)
  → sets obj.mode = "Mesh"
        │
        ▼
attach_customizer_varset()       ← link VarSet if customizer file
        │
        ▼
obj.Proxy.executeFunction(obj)
  → calls createMesh()           ← runs OpenSCAD CLI → STL → Mesh.Mesh
  → creates companion Mesh::Feature in doc  (obj.companion_mesh = name)
  → sets obj.Shape = Part.Shape()  (empty — FeaturePython is a placeholder)
        │
        ▼
finalize_scad_mesh_object(obj)
  → adds SCAD properties to companion   (sourceFile, linked_varset, mode,
                                          fnmax, timeout, keep_work_doc, …)
  → copies their values from FeaturePython
  → renames companion to FeaturePython's label
  → removes FeaturePython from doc
  → makes companion visible, DisplayMode = "Shaded"
  → returns the Mesh::Feature
```

After this the document contains **one** `Mesh::Feature` object.  It has all
the SCAD properties a `Part::FeaturePython` would have, but no Proxy.

---

## 4. Property Migration (`_SCAD_PROPS`)

`scad_mesh_utils.py` defines `_SCAD_PROPS` — the list of properties copied from
the FeaturePython to the companion during finalization:

```python
_SCAD_PROPS = [
    ("App::PropertyFile",    "sourceFile",    "OpenSCAD", "SCAD source file"),
    ("App::PropertyString",  "linked_varset", "OpenSCAD", "VarSet object name"),
    ("App::PropertyString",  "mode",          "OpenSCAD", "Geometry mode"),
    ("App::PropertyInteger", "fnmax",         "OpenSCAD", "Max polygon sides"),
    ("App::PropertyInteger", "timeout",       "OpenSCAD", "OpenSCAD timeout (secs)"),
    ("App::PropertyBool",    "keep_work_doc", "OpenSCAD", "Keep work document"),
    ("App::PropertyBool",    "modules",       "OpenSCAD", "Uses SCAD modules"),
    ("App::PropertyString",  "message",       "OpenSCAD", "Last OpenSCAD message"),
]
```

---

## 5. Re-rendering a Finalized Mesh::Feature

`render_scad_mesh_feature(obj)` in `scad_mesh_utils.py` handles re-rendering:

1. Reads `obj.sourceFile`.
2. Reads `obj.linked_varset`; if set, retrieves the VarSet object and builds
   `-D` overrides via `varset_to_D_params()`.
3. Calls `createMesh(obj, source, d_params=...)` to run OpenSCAD and get a
   fresh `Mesh.Mesh`.
4. Sets `obj.Mesh = mesh`.

This is called by the **Render** command (`renderSCAD.py`) when the selected
object passes `_is_scad_mesh_feature()`.

### Detection helper

```python
def _is_scad_mesh_feature(obj):
    return (obj.TypeId == "Mesh::Feature"
            and hasattr(obj, "sourceFile")
            and bool(getattr(obj, "sourceFile", "")))
```

---

## 6. Render Command — VarSet Selection

The Render command's `_find_render_targets()` accepts three kinds of selection:

| Selected object | Behaviour |
|---|---|
| `Part::FeaturePython` (AST_BRep) | Rendered directly via `Proxy.renderFunction()` |
| `Mesh::Feature` with `sourceFile` | Rendered via `render_scad_mesh_feature()` |
| `App::VarSet` | All SCAD objects whose `linked_varset == varset.Name` are resolved and rendered |

The VarSet path works for **both** object types.  The user never has to
re-select the SCAD object after tweaking parameters — selecting the VarSet and
clicking Render is sufficient.

---

## 7. No-companion Fallback

`finalize_scad_mesh_object()` checks for `obj.companion_mesh`.  If no companion
exists (OpenSCAD failed to produce an STL, or the mode fell back to BRep), it
logs a diagnostic and returns `fp_obj` unchanged:

```python
write_log("MeshUtils",
    f"finalize: no companion for {fp_obj.Name} "
    f"(shape null={fp_obj.Shape.isNull() if hasattr(fp_obj, 'Shape') else 'n/a'}) — skipping")
return fp_obj
```

The `shape null=` field distinguishes:
- `True`  → OpenSCAD failed entirely; FeaturePython has no shape.
- `False` → OpenSCAD succeeded via a BRep fallback path; shape is valid.

---

## 8. Mode Switching

The user can change the **mode** property on any SCAD object at any time:

- **AST_BRep → Mesh**: on the next Render, `executeFunction()` will detect
  `mode == "Mesh"`, run OpenSCAD to produce a mesh, and create a companion.
  `finalize_scad_mesh_object()` is *not* automatically called from within
  `executeFunction`; it is called by the import path or can be called manually.
  In practice, using the Render command after a mode change produces the updated
  mesh correctly via `render_scad_mesh_feature()`.

- **Mesh → AST_BRep**: on the next Render, `renderSCAD.py` checks
  `_is_scad_mesh_feature()`.  If mode has been changed to `"AST_BRep"` but the
  object is still a `Mesh::Feature`, `render_scad_mesh_feature()` runs OpenSCAD
  and updates the mesh (it does not convert the object type).  A full re-import
  is needed to get a native BRep `Part::FeaturePython` object.

**Summary**: switching modes on an existing object is supported and safe; it
will not corrupt the document.  A fresh import gives the cleanest result.

---

## 9. Testing Gaps

### 9a. AST_BRep with mesh fallback nodes (hull / minkowski)

In AST_BRep mode, `hull()` and `minkowski()` nodes that cannot be solved natively
fall back to running OpenSCAD and importing the result as a `Mesh.Mesh` object,
mixed into an otherwise-BRep document.  This **mixed-mode** path (Part shapes
alongside fallback mesh shapes in the same import) needs broader testing:

- Do fallback mesh objects behave correctly when the document is saved and
  re-opened?
- Are the shapes correctly positioned relative to the BRep siblings?
- Does the Render command correctly re-run OpenSCAD for fallback nodes?

**TODO**: identify a real-world SCAD file that exercises hull/minkowski fallback,
import it in AST_BRep mode, save/reload, and verify geometry.

### 9b. Mesh mode with complex VarSet-driven files

- Verify that all VarSet property types (bool, int, float, string, vector) round-
  trip correctly through the `-D` override mechanism.
- Test files where an OpenSCAD variable name collides with a FreeCAD reserved
  property name.

### 9c. Mode switching on an imported file

- Confirm that changing `mode` from `"Mesh"` to `"AST_BRep"` on a finalized
  `Mesh::Feature` and then running Render does not crash.
- Confirm the reverse (AST_BRep → Mesh on a FeaturePython).

---

## 10. Key Files

| File | Role |
|---|---|
| `core/scad_mesh_utils.py` | `finalize_scad_mesh_object()`, `render_scad_mesh_feature()`, `_SCAD_PROPS` |
| `objects/SCADObject.py` | `SCADfileBase`, `createMesh()`, `executeFunction()` |
| `commands/renderSCAD.py` | `_is_scad_mesh_feature()`, `_find_render_targets()`, `Activated()` dispatch |
| `importers/importFileSCAD.py` | `insert()` — calls finalize after execute for Mesh mode |
| `importers/importASTCSG.py` | `_customizer_intercept()` — calls finalize after execute for Mesh mode |
| `core/attach_varset.py` | `attach_customizer_varset()` — links VarSet before first execute |
| `core/varset_utils.py` | `varset_to_D_params()` — converts VarSet to `-D` overrides |
