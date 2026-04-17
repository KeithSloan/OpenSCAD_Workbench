# Property Change Handling for SCAD Module Objects

_2026-04-16_

---

## 1. The Problem

`SCADfileBase.onChanged()` is called by FreeCAD on **every individual property change event**.
For `PropertyString` this means every keystroke. For `PropertyFloat` / `PropertyInteger`
it fires on focus-out or Enter, which is better but still one fire per edited field.

`executeFunction()` invokes the OpenSCAD CLI, which is a subprocess call plus CSG/AST
processing. Even for a trivial file this is a noticeable pause. For real files it is
seconds. Firing it per keystroke would make the workbench unusable.

**Current state in the code**: `SCADModuleObject` has no `onChanged` override and its
`execute()` method is a no-op `pass`. Module parameter properties are therefore
completely inert — they are stored but changing them does nothing.

---

## 2. FreeCAD's Two-Phase Notification System

Understanding these two hooks is essential before choosing a strategy:

| Hook | When called | Frequency |
|---|---|---|
| `Proxy.onChanged(fp, prop)` | Immediately when any single property changes | Once per field edit / keystroke |
| `Proxy.execute(fp)` | During a document recompute cycle | **Once per cycle**, regardless of how many properties changed |

The document recompute cycle runs when:
- The user presses **Ctrl+R** (or menu Model → Refresh)
- Any object calls `fp.touch()` and a recompute is then triggered
- FreeCAD runs `Document.recompute()` programmatically

**Key insight**: putting the expensive work in `execute()` rather than `onChanged()`
automatically batches all upstream changes into a single OpenSCAD run. This is the
FreeCAD-native debounce mechanism.

---

## 3. Recommended Architecture

### 3a. Separate "dirty marking" from "execution"

```python
# SCADModuleObject (or SCADfileBase)

_PARAM_SKIP = frozenset({"Shape", "execute", "edit", "message",
                         "mode", "scadName", "sourceFile",
                         "ModuleName", "Description"})

def onChanged(self, fp, prop):
    if "Restore" in fp.State:
        return
    # Handle existing triggers (edit, execute bool, mode) unchanged …
    super().onChanged(fp, prop)

    # For parameter properties: mark dirty, do NOT run OpenSCAD here
    if prop not in _PARAM_SKIP and prop in fp.PropertiesList:
        group = fp.getGroupOfProperty(prop)
        if group == "SCAD Parameters":
            fp.touch()      # marks object as needing recompute
            # optionally: write_log("Info", f"Param {prop} changed, marked dirty")

def execute(self, fp):
    """Called by FreeCAD during document recompute — run OpenSCAD once."""
    write_scad_file(fp, self.module, self.meta)   # regenerate wrapper
    shp = shapeFromSourceFile(fp, modules=fp.modules)
    fp.Shape = shp if shp is not None else Part.Shape()
```

The user then triggers recompute explicitly (Ctrl+R or the existing `execute` bool).
This is the safest option and matches how Part Design, Sketcher, and other workbenches
behave.

### 3b. Optional "Live Update" property

For users who want immediate feedback on small files, add a bool property:

```python
obj.addProperty("App::PropertyBool", "liveUpdate", "OpenSCAD",
                "Recompute shape on every parameter change (slow for large files)")
obj.liveUpdate = False
```

In `onChanged`, if `liveUpdate` is True **and** the changed property is in
`"SCAD Parameters"`:

```python
if fp.liveUpdate and group == "SCAD Parameters":
    self.executeFunction(fp)   # synchronous, blocks UI
```

This is opt-in. The default is off. Users with small/fast files can enable it.

### 3c. Debounced timer (advanced, use with caution)

A Qt timer can collapse rapid successive changes into one deferred call:

```python
from PySide2.QtCore import QTimer

class SCADModuleObject(SCADfileBase):

    def __init__(self, ...):
        ...
        self._recompute_timer = QTimer()
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(800)   # ms of silence before firing
        self._recompute_timer.timeout.connect(self._deferred_execute)

    def onChanged(self, fp, prop):
        ...
        if group == "SCAD Parameters" and fp.liveUpdate:
            self._pending_obj = fp
            self._recompute_timer.start()   # restart timer on every change

    def _deferred_execute(self):
        if self._pending_obj is not None:
            self.executeFunction(self._pending_obj)
```

**Caution**: the timer lives on the Python object, which is not serialised to the
FreeCAD document. It will be lost on document close/reopen. It also complicates the
`__getstate__` / `__setstate__` pair. Only worth doing if the opt-in `liveUpdate`
property proves popular and users find 800 ms acceptable.

**Recommendation**: implement 3a first, add the `liveUpdate` bool in 3b as an option.
Skip 3c unless explicitly requested.

---

## 4. Considerations When Properties Are Linked to VarSet / Vars / Spreadsheet

### 4a. How expression-binding works in FreeCAD

When a SCAD parameter property is expression-bound
(e.g. `box.w = VarSet.can_h`), FreeCAD stores the expression and re-evaluates it
during every document recompute. The sequence is:

1. User edits VarSet property (or spreadsheet cell, or Vars variable).
2. FreeCAD marks all expression-dependent objects as touched.
3. On next recompute, FreeCAD calls `execute()` on each touched object **once**.

This means **expression-bound properties are already debounced** by FreeCAD's recompute
cycle. `onChanged` still fires for each intermediate change to the source (VarSet etc.),
but `execute()` is only called once per recompute pass.

### 4b. VarSet

| Consideration | Detail |
|---|---|
| Change granularity | Each VarSet property edit triggers `onChanged` on dependents immediately. |
| Recompute batching | `execute()` called once per recompute — naturally batches multi-property edits if the user triggers recompute after making several changes. |
| Typing problem | VarSet `PropertyFloat` / `PropertyInteger` fields confirm on Enter/focus-out, not per keystroke — less severe than direct string properties. |
| Circular dependency | If SCAD shape feeds back into a VarSet value, FreeCAD will detect the cycle and error. Avoid bidirectional binding. |
| Recommended pattern | SCAD object properties are expression-bound (`=VarSet.x`) — read-only from SCAD's point of view. VarSet is the single source of truth. |

### 4c. Spreadsheet

| Consideration | Detail |
|---|---|
| Change granularity | Cell edits confirm on Enter. Formulae re-evaluate per recompute. Better than direct properties for typing. |
| Recompute batching | Same as VarSet — `execute()` fires once per cycle. |
| Cell validation | Spreadsheet does not know that a cell feeds OpenSCAD — invalid expressions (e.g. `=A1 + "foo"`) will produce FreeCAD formula errors, not SCAD errors. |
| Weakness already noted | No type metadata, vector values are awkward, re-import can overwrite. |
| Recommended pattern | Use spreadsheet as a secondary/display option. Prefer VarSet for parametric work. |

### 4d. Vars extension (mnesarco/Vars)

| Consideration | Detail |
|---|---|
| Change granularity | Vars uses its own formula evaluator. Changes propagate via FreeCAD expressions. |
| Recompute batching | Same pattern as VarSet — `execute()` fires once. |
| Dependency | External workbench, not installed by default. |
| Recommended pattern | Defer implementation until VarSet and Spreadsheet backends are stable. Design the exporter API so Vars is a drop-in backend. |

### 4e. Direct property editing (no external link)

This is the typing-per-character problem in its worst form. A `PropertyString` holding a
raw SCAD expression (e.g. `"sin(45) * 10"`) fires `onChanged` for every character typed.

Options in priority order:

1. **Use `fp.touch()` + explicit recompute** — zero latency impact, user controls when.
2. **Use `PropertyFloat` / `PropertyInteger` where possible** — these confirm on
   Enter/focus-out, reducing the fire rate to once per field.
3. **`liveUpdate` opt-in** — only fires `executeFunction` if the user has consciously
   enabled it.
4. **Custom Task Panel** — intercept editing in a sidebar panel with an Apply button
   (see §5).

---

## 5. Custom Task Panel (the cleanest UX option)

FreeCAD supports "Task Panels" — sidebar panels that appear when an object is double-
clicked. This is how Sketcher, Part Design, and Draft work for parameter editing.

A Task Panel for SCADModuleObject would:
- Show all `"SCAD Parameters"` properties as form widgets.
- Not trigger `onChanged` at all while editing — all edits are local to the panel.
- On **Apply** or **OK**: write all values to properties at once, then call
  `executeFunction` once.
- On **Cancel**: discard edits, no recompute.

This completely eliminates the per-keystroke problem and gives the user a clear
"commit" action. It is more work to implement but is the most correct UX.

```python
class SCADModuleTaskPanel:
    def __init__(self, obj):
        self.obj = obj
        self.form = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(self.form)
        self.widgets = {}
        for prop in obj.PropertiesList:
            if obj.getGroupOfProperty(prop) == "SCAD Parameters":
                w = self._make_widget(obj, prop)
                layout.addRow(prop, w)
                self.widgets[prop] = w

    def accept(self):
        for prop, w in self.widgets.items():
            setattr(self.obj, prop, w.value())
        self.obj.Proxy.executeFunction(self.obj)
        FreeCADGui.ActiveDocument.resetEdit()
        return True

    def reject(self):
        FreeCADGui.ActiveDocument.resetEdit()
        return True
```

Wire it via `ViewSCADProvider`:
```python
def setEdit(self, vobj, mode):
    panel = SCADModuleTaskPanel(vobj.Object)
    FreeCADGui.Control.showDialog(panel)
    return True
```

---

## 6. The `execute` Bool Property (Existing Pattern)

`SCADfileBase` already has `execute: PropertyBool`. When flipped to `True`, `onChanged`
calls `executeFunction` and resets it to `False`. This is a workable explicit trigger —
the user flips it in the Property Panel to force a recompute.

**Problem**: it is not obvious to users. A labelled button in a Task Panel or toolbar
("Recompute Shape") is more discoverable.

**Short-term fix** (no new UI): expand `onChanged` in `SCADModuleObject` to watch any
`"SCAD Parameters"` property change and write the SCAD file but **not** call OpenSCAD
— then let the existing `execute` bool trigger the actual recompute:

```python
def onChanged(self, fp, prop):
    if "Restore" in fp.State:
        return
    group = fp.getGroupOfProperty(prop)
    if group == "SCAD Parameters":
        write_scad_file(fp, self.module, self.meta)   # fast, no subprocess
        # shape stays stale until user flips execute = True
    super().onChanged(fp, prop)
```

This at least keeps the generated `.scad` wrapper file in sync cheaply, so when the
user does trigger recompute it uses current values.

---

## 7. Summary and Recommended Implementation Order

| Step | Action | Cost |
|---|---|---|
| 1 | In `SCADModuleObject.onChanged`, call `write_scad_file()` on param changes (fast). Do NOT call `executeFunction`. | Low |
| 2 | In `SCADModuleObject.execute()`, call `executeFunction()` (this is what FreeCAD calls on recompute). | Low |
| 3 | Add `liveUpdate: PropertyBool = False`. When True, call `executeFunction` in `onChanged` (opt-in for fast files). | Low |
| 4 | Replace direct `PropertyString` params with typed properties where possible (reduces keystroke fires). | Already done in `_add_parameter_property` |
| 5 | Implement Task Panel with Apply/Cancel buttons for clean UX. | Medium |
| 6 | When VarSet/Spreadsheet binding is added, rely on FreeCAD's `execute()` cycle for debouncing — no extra work needed. | Free |

The core principle throughout: **`onChanged` marks state dirty and does cheap work;
`execute()` does the expensive subprocess call, once per cycle.**
