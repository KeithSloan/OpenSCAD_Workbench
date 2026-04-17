# Extract Variables — Implementation Analysis

_Reviewed against codebase state: 2026-04-16_

---

## Branch Status — `Extract_Variables` (2026-04-17)

Initial implementation committed to branch `Extract_Variables`. Untested in FreeCAD.

| Item | Status |
|---|---|
| `variable_descriptions` field on `ScadMeta` | Done |
| Trailing `// comment` capture (Lark parser + regex fallback) | Done |
| Real `include <path>` scanning in legacy parser | Done |
| `core/exporters.py` — strategy pattern, `VarSetExporter` active | Done |
| `SpreadsheetExporter`, `VarsExporter` | Stubs only |
| `varsSCAD.py` rewritten — Lark parser + `export_variables()` | Done |
| Library Browser "Extract Variables" button — delegates to `export_variables()` | Done |
| `core/varset_utils.py` — `create_varset()` for typed `App::VarSet` | Done |
| Duplicate detection / update-or-create dialog | **Not yet** |
| Trigger variable export on "Create SCAD Object" | **Not yet** |
| Parametric re-evaluation in `SCADModuleObject` | **Not yet** (see `Property_Change_Handling.md`) |
| Recursive `include <path>` scanning | **Not yet** |

See `Extract_Variables_Analysis.md` (this file) for the full design rationale,
and `Developer_Notes/Extract_Variables_Analysis.md` in the branch for a detailed
testing checklist.

---

## 1. Current State

The infrastructure for variable extraction is substantially in place. The key pieces:

| Layer | File | Status |
|---|---|---|
| Lark parser | `parsers/scadmeta/scadmeta_lark_parser.py` | Active |
| Grammar | `parsers/scadmeta/scadmeta_grammar.py` | Active |
| Data model | `parsers/scadmeta/scadmeta_model.py` | Active |
| Scanner / orchestrator | `parsers/scadmeta/scadmeta_scanner.py` | Active |
| Two-level cache | `parsers/scadmeta/scadmeta_cache.py` | Active |
| Extract command | `commands/varsSCAD.py` | Partial |
| VarSet utilities | `core/varset_utils.py` | Written, not wired |
| Spreadsheet creation | `core/createSpreadSheet.py` | Active |
| Library browser | `gui/OpenSCADLibraryBrowser.py` | Active |
| Module dialog | `gui/SCAD_Module_Dialog.py` | Active |
| Module properties | `objects/SCADModuleObject.py` | Active |
| Export option preference | `Resources/ui/OpenSCAD_Ext_Preferences.ui` | **Missing** |

The parser already extracts top-level variables, module parameters, function definitions,
and `include`/`use` directives. `SCADModuleObject` already maps module parameters to
FreeCAD Properties. The gap is wiring, UI, and parametric re-evaluation.

---

## 2. Where OpenSCAD Variables Live

The `Extract Variables.md` note lists the locations correctly. In practice these split
into two distinct concerns:

### 2a. Top-level (file-scope) variables

```scad
can_h = 20;          // scalar
can = [can_h, can_d]; // vector — depends on other variables
txb_b = true;        // boolean
txb_n = "trunc_diamonds"; // string
tol = 0.1;
```

These are the "parameters" a user would customise before generating geometry. The Lark
parser already captures them as `ScadMeta.variables: Dict[str, str]` (name → raw
expression string).

**Key consideration:** expressions can be *dependent* (`can = [can_h, can_d]`). Storing
only the raw expression string is correct — do **not** try to evaluate them in Python;
let OpenSCAD do that. FreeCAD Spreadsheet cells can hold the raw expression for display
and editing, but the canonical evaluated value must come from a fresh OpenSCAD run.

### 2b. Variables inside comment blocks (the tricky part)

OpenSCAD has no formal parameter-documentation syntax. Conventions observed in the wild:

- **BOSL2-style block comments** — structured annotations above module definitions
  (`// Arguments:`, `// Description:` etc.). The grammar already handles these.
- **Free-form comments** adjacent to assignments — e.g. `can_h = 20; // height of can`.
  These are not captured today.
- **Library headers** — descriptive comments at the top of a file describing the whole
  library and its variables.

**Recommendation:** capture inline trailing comments (`// ...`) during parsing and store
them as a `description` field on each variable. This gives the user something useful to
display in the Preferences panel or spreadsheet "Description" column without requiring
structured annotation.

---

## 3. Export Target Options

### 3a. FreeCAD Spreadsheet

**Pros:** built-in, no dependencies, cells can drive expressions elsewhere in the model,
user-familiar.

**Cons (noted in `Extract Variables.md`):**
- No type metadata — everything is a cell value; FreeCAD doesn't know a cell is a
  "length" vs. "count".
- Bidirectional sync is fragile: if the user edits the spreadsheet and then re-imports,
  changes are overwritten.
- Vector-valued variables (`can = [20, 10, 1.2]`) have no natural single-cell representation.
- The spreadsheet is a document object — creating one per SCAD file pollutes the model
  tree for complex assemblies.

**Suggested mitigation:** use the spreadsheet as a *read-only display* only; edits flow
back to SCAD through properties (see §5).

### 3b. VarSets (App::FeaturePython with properties)

`core/varset_utils.py` already has `add_scad_vars_to_varset()`. VarSets store variables
as typed FreeCAD Properties (`App::PropertyFloat`, `App::PropertyString`, etc.), which:

- participate in the undo/redo stack,
- appear in the Property Panel with correct type widgets,
- can be referenced by other features via expressions (`=VarSet.can_h`),
- survive file save/load as part of the document.

**Cons:**
- Requires FreeCAD ≥ 0.21 for the VarSet API to be stable.
- Type inference from raw OpenSCAD expression strings is imperfect for vectors and
  computed values.

**This is the recommended primary target** for parametric use cases.

### 3c. Vars Extension (mnesarco/Vars)

Frank David Martinez's extension adds a dedicated Variables workbench with a
formula-capable variable store. It is more powerful than Spreadsheet for managing many
interrelated variables.

**Cons:**
- External dependency — users must install it separately.
- API surface is not stable / not widely deployed.
- Adds a hard dependency that may not survive FreeCAD version bumps.

**Recommendation:** treat Vars as a stretch goal. Design the export layer as a pluggable
backend (see §4) so it can be added without touching the core.

---

## 4. Preference and Export Architecture

The `Extract Variables.md` note proposes:
- A preference to pick the default export target.
- An optional "prompt each time" mode.

### Recommended design

```
Preferences → OpenSCAD_Ext → Variable Export
    [x] Prompt for export option each time
    Default export target: [VarSet ▾]  (VarSet | Spreadsheet | Vars)
```

Implement as a simple strategy pattern in `commands/varsSCAD.py`:

```python
def get_exporter(target: str):
    if target == "VarSet":    return VarSetExporter()
    if target == "Spreadsheet": return SpreadsheetExporter()
    if target == "Vars":      return VarsExporter()   # future
    raise ValueError(target)
```

Each exporter implements:
```python
class BaseExporter:
    def export(self, doc, scad_meta: ScadMeta, obj_name: str) -> None: ...
    def update(self, doc, scad_meta: ScadMeta, obj_name: str) -> None: ...
    def exists(self, doc, obj_name: str) -> bool: ...
```

This keeps the UI and storage concerns separated, and makes adding the Vars backend
later a localised change.

---

## 5. When Variables Are Created / Re-created

The `Extract Variables.md` note lists three trigger points. Considerations for each:

### 5a. On "Create SCAD Object"

When a `.scad` file is imported as a SCADfileObject, scan for top-level variables and
create the export object (VarSet / Spreadsheet) automatically **only if variables exist**.
Skip silently if none are found.

**Edge case:** if the user imports the same file twice, `exists()` (see §4) must detect
the already-created VarSet and offer to update rather than duplicate.

### 5b. For each Module (via Library Browser → Create SCAD Module)

`SCADModuleObject` already creates one Property per parameter. The gap is that these
properties do not currently trigger a re-evaluation of the geometry when changed.

### 5c. Extract Variables button in Library Browser

This is the explicit, user-initiated path — already partially implemented in
`commands/varsSCAD.py`. Add the export-target logic here.

---

## 6. Parametric Re-evaluation (the hard problem)

This is the most architecturally significant item in the note:

> _The following changes will cause re-evaluation of OpenSCAD Object Shape:
> Direct change of Property / Change of Variable Set / Change of Spreadsheet_

### Current situation

`SCADModuleObject.onChanged()` is called when any property changes, but it does not
currently trigger a new OpenSCAD invocation. The shape is static after import.

### What needs to happen

When a parameter property changes:
1. Collect all current property values.
2. Write a temporary `.scad` wrapper that overrides the changed variables and calls the module.
3. Run OpenSCAD → CSG → AST → Shape (the existing import pipeline).
4. Replace the object's `Shape`.

**Debounce / avoiding recalc on every keystroke:** the note raises this correctly. Use
a `bool` property (e.g. `AutoRecompute: Bool = False`) that the user toggles to opt in
to live updates, or provide an explicit "Recompute" button. FreeCAD's `execute: Bool`
property pattern (already on `SCADfileBase`) is the right model — flip it to trigger
a one-shot recompute.

### VarSet / Spreadsheet → Shape feedback loop

If variables live in a VarSet, changes to VarSet properties must propagate back to the
SCAD object. FreeCAD's expression binding (the `=VarSet.can_h` formula in a property)
does this automatically when both objects are in the same document. The SCAD object's
`onChanged()` fires whenever a bound expression recomputes.

---

## 7. Type Inference from Raw Expressions

OpenSCAD expressions are strings like `"20"`, `"true"`, `"[20, 10]"`, `"can_h * 2"`.

| Pattern | FreeCAD type | Notes |
|---|---|---|
| Integer literal | `App::PropertyInteger` | safe |
| Float literal | `App::PropertyFloat` | safe |
| `true` / `false` | `App::PropertyBool` | safe |
| Quoted string | `App::PropertyString` | safe |
| `[a, b, c]` (3 floats) | `App::PropertyVector` | assume 3D vector |
| `[a, b]` | `App::PropertyString` | store as string |
| Expression with operators | `App::PropertyString` | store raw, evaluate via OpenSCAD |
| Variable reference | `App::PropertyString` | ditto |

**Do not attempt to evaluate arbitrary expressions in Python.** Store raw strings for
non-literal expressions; OpenSCAD is the evaluator.

---

## 8. Handling Duplicate / Already-existing VarSets

The note flags this: _"Need to check if already exists in current Document"_.

Strategy:
1. Before creating, call `exporter.exists(doc, obj_name)`.
2. If it exists, prompt: **Update existing** / **Create new (rename)** / **Cancel**.
3. On update: overwrite values for variables that still exist; warn about removed variables;
   add new variables.

Use a stable naming convention: `SCAD_<basename>_vars` for top-level, `SCAD_<basename>_<ModuleName>` for module parameters. This makes `exists()` deterministic.

---

## 9. SCAD → FreeCAD Variable Export (Andreas scad export)

The note mentions "Andreas scad export" for Variable Set / Variables / Spreadsheet. This
is the reverse direction: taking FreeCAD values and injecting them into a generated SCAD
file at render time.

The `SCADModuleObject` already does this for module parameters — it generates a wrapper
`.scad` that calls the module with current property values. Extending this to top-level
variables means prepending variable assignments to the generated wrapper:

```scad
// Overrides from FreeCAD
can_h = 25;
can_d = 12;
// ... rest of original file
include </path/to/original.scad>;
```

This is a clean approach — no parsing of the original file at render time, just injection.

---

## 10. Implementation Sequence (suggested)

1. **Add export preference UI** to `OpenSCAD_Ext_Preferences.ui`: radio group
   (VarSet / Spreadsheet / Vars) + "Prompt each time" checkbox.

2. **Implement pluggable exporter** in `commands/varsSCAD.py` with `VarSetExporter` and
   `SpreadsheetExporter` as initial backends.

3. **Wire `VarSetExporter`** using existing `core/varset_utils.py` — it is already
   written; it just needs to be called from `varsSCAD.py`.

4. **Add inline comment capture** to the Lark grammar / parser so that trailing `// ...`
   comments on variable lines are stored as descriptions.

5. **Duplicate detection** — implement `exists()` check and update-or-create dialog.

6. **Trigger on import** — call the exporter from `SCADfileBase.execute()` when
   top-level variables are found.

7. **Parametric re-evaluation** — add `AutoRecompute` property + debounce logic to
   `SCADModuleObject.onChanged()`.

8. **Vars extension backend** — add as step 8 once the architecture is stable.

---

## 11. Open Questions

| Question | Notes |
|---|---|
| Should vector variables become `PropertyVector` or `PropertyString`? | `PropertyVector` limits to 3D; many SCAD vectors are 2-element or longer. Safer to use String. |
| Should the spreadsheet be read-only or editable? | Editable risks overwrite on re-import. Recommend read-only display; edits via Property Panel. |
| Where should the VarSet appear in the model tree? | Under the SCAD Object as a child, or top-level? Child is cleaner. |
| How to handle `include <...>` variables? | The included file's globals are invisible to the parser. For now, skip. Document limitation. |
| Conflict if user renames a property? | Use the stable naming convention; add `scad_name` metadata attribute to each property to track original name. |

---

## Summary

The parser, data model, and caching infrastructure are production-ready. The main work
remaining is:

- **Pluggable exporter backends** (VarSet first, Spreadsheet second, Vars later).
- **Preference UI** for export target selection.
- **Duplicate detection and update logic**.
- **Parametric re-evaluation** in `SCADModuleObject` (the architecturally hardest piece).
- **Inline comment capture** for variable descriptions (small parser addition).

The VarSet approach is the strongest integration point with FreeCAD's parametric model.
Spreadsheet is a useful secondary option for users who want to drive dimensions from a
table. The Vars extension should be deferred until the core is stable.
