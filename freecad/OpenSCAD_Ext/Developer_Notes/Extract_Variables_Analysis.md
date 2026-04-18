# Extract Variables — Implementation Notes

Branch: `Extract_Variables`  
Status: Initial implementation committed; untested in FreeCAD.

---

## What was built

### 1. `ScadMeta` model — `parsers/scadmeta/scadmeta_model.py`

Added `variable_descriptions: Dict[str, str]` alongside the existing
`variables: Dict[str, str]`.  Populated by the parser from inline trailing
comments:

```openscad
width = 20;    // overall width   → variable_descriptions["width"] = "overall width"
height = 10;   // overall height
```

### 2. Lark parser — `parsers/scadmeta/scadmeta_lark_parser.py`

- New helper `_extract_trailing_comment(source_lines, name_token)` — uses the
  line number from `propagate_positions` to read the raw source line and strip
  any `// ...` suffix (ignores `//` inside string literals).
- Wired into `assign_stmt` handler (top-level variables only).
- Same logic applied in `_regex_fallback()` so the fallback path also captures
  descriptions.

### 3. Legacy parser — `parsers/scadmeta/scadmeta_parse_scad_file.py`

The old parser only recognised `// @include` annotations.  Added real
`include <path>` and `use <path>` line scanning at the top of the parse loop
so actual dependency statements are captured alongside the annotation style.

### 4. Export strategy — `core/exporters.py` *(new file)*

Strategy pattern with a common `export_variables(doc, meta, label)` entry
point that:

1. Reads `varExportTarget` (int, default 0) and `varExportPrompt` (bool,
   default True) from `User parameter:BaseApp/Preferences/Mod/OpenSCAD_Ext`.
2. If prompt is on, shows a `QMessageBox.question` listing the first 10
   variables before proceeding.
3. Dispatches to the appropriate exporter class.

| Class | Target index | Status |
|---|---|---|
| `VarSetExporter` | 0 | **Active** |
| `VarsExporter` | 1 | Stub — prints warning |
| `SpreadsheetExporter` | 2 | Stub — prints warning |

`VarSetExporter.export()` creates (or updates) an `App::VarSet` named
`Vars_<label>` where `<label>` is the SCAD file stem.  Property type is
inferred from the raw expression string:

| Expression | Property type |
|---|---|
| `true` / `false` | `App::PropertyBool` |
| Integer literal | `App::PropertyInteger` |
| Float literal | `App::PropertyFloat` |
| Everything else | `App::PropertyString` |

`variable_descriptions` values become the property tooltip (third arg to
`addProperty`).

### 5. `commands/varsSCAD.py` — rewritten

Old code used the legacy `parse_scad_meta()` + `create_scad_vars_spreadsheet()`
path.  Replaced with:

```python
meta = parse_scad_file(scad_file)          # Lark parser
export_variables(doc, meta, label)          # strategy dispatch
```

Validates that the selected object is a `Part::FeaturePython` with a
`SCADfileBase` proxy and a valid `sourceFile` before proceeding.

### 6. `gui/OpenSCADLibraryBrowser.py` — Extract Variables button

The browser's `_extract_variables()` method previously hard-coded a
`Spreadsheet::Sheet` creation, ignoring preferences.  Replaced with the same
`export_variables(doc, meta, label)` call so both entry points (toolbar
command and library browser button) behave identically.

### 7. `core/varset_utils.py` — updated

Added `create_varset(doc, variables, descriptions, name)` which creates a
typed `App::VarSet`.  The legacy `add_scad_vars_to_varset()` and
`mirror_varset_to_spreadsheet()` helpers are kept for backwards compatibility
but new code should use `create_varset()` or `export_variables()`.

---

## What is deferred / stubbed

### Spreadsheet exporter

`SpreadsheetExporter` in `core/exporters.py` currently just prints a warning.
When implemented it should mirror `variables` into a `Spreadsheet::Sheet`
named `Vars_<label>`, with Name/Expression columns.  The old browser code
(now removed) is a reasonable starting point.  Key decision: whether to also
write a Description column from `variable_descriptions`.

### Vars exporter

`VarsExporter` is a stub pending a stable API from Frank David Martinez's
[Vars extension](https://github.com/mnesarco/Vars).

### VarSet update behaviour

Currently re-running Extract Variables on the same file calls `addProperty`
only for names not already present, and `setattr` updates existing values.
Property *type* is not updated if the expression changes (e.g. `10` → `"text"`).
If this becomes a problem the fix is to remove and re-add the property.

### include <path> recursive scanning

The Lark parser captures `include <path>` and `use <path>` lines in
`meta.includes` / `meta.uses` but does **not** recursively scan included
files for additional variables.  If a SCAD file delegates all variables to an
included file, `meta.variables` will be empty.  Recursive scanning is a
future enhancement.

---

## Testing checklist

These should be verified manually in FreeCAD before merging to main:

- [ ] Select a SCAD file object → Extract Variables toolbar button
  - [ ] Prompt dialog appears listing variables (when `varExportPrompt = True`)
  - [ ] Clicking Yes creates `App::VarSet` named `Vars_<stem>` in model tree
  - [ ] VarSet properties have correct types (bool/int/float/string)
  - [ ] Trailing comment appears as tooltip on each property
  - [ ] Re-running updates values without duplicating properties
- [ ] Set `varExportPrompt = False` in prefs — extraction runs silently
- [ ] Set `varExportTarget = 2` (Spreadsheet) — warning printed, no crash
- [ ] Library Browser → select a SCAD file with variables → Extract Variables
  - [ ] Same VarSet is created (not a spreadsheet)
  - [ ] Status bar updates with variable count
- [ ] Library Browser → file with no variables → info dialog, no crash
- [ ] Library Browser → no active document → status bar message, no crash
- [ ] SCAD file with `include <other.scad>` — `meta.includes` populated

---

## Outstanding decision — SCADModuleObject property change handling

`freecad/OpenSCAD_Ext/objects/SCADModuleObject.py` has `execute()` as `pass`.
When a VarSet property is expression-bound to a module parameter and the user
changes the value, FreeCAD will call `execute()` to recompute the shape.
Three options were discussed but a decision has not yet been made:

### Option 1 — Manual trigger (no code change)
The existing `execute` bool flip already works: user toggles it to force a
recompute.  Zero implementation cost.

### Option 2 — `liveUpdate` PropertyBool (~10 lines)
Add an opt-in `liveUpdate: App::PropertyBool = False` to `SCADModuleObject`.
When True, `onChanged()` calls `execute()` immediately on any property change.

```python
def onChanged(self, fp, prop):
    if getattr(fp, "liveUpdate", False) and prop != "liveUpdate":
        self.execute(fp)
```

### Option 3 — Task Panel (~60 lines)
Double-click on the object opens a sidebar form showing all parameters.
User edits values and clicks OK; a single OpenSCAD run recomputes the shape.
Most FreeCAD-idiomatic approach; avoids triggering a recompute on every
keystroke.  Requires implementing `setEdit()` / `unsetEdit()` on the ViewProvider.

**Recommendation:** Option 2 for now (simple, reversible), with Option 3
as a follow-up once the basic pipeline is validated.
