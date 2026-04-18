# OpenSCAD Workbench (OpenSCAD_Ext)

An external FreeCAD workbench providing full OpenSCAD import/export support,
a library browser, parametric module objects, and a Lark-based SCAD metadata
scanner.

---

## Features

- **Import** `.scad` and `.csg` files into FreeCAD as native BRep shapes
  (with mesh fallback via OpenSCAD CLI)
- **Export** FreeCAD objects to `.scad` format
- **Toolbar icons** for every command — visually distinct, colour-coded 64×64 SVGs
- **OpenSCAD Library Browser** – browse your `OPENSCADPATH` library,
  inspect modules with their parameters, and create parametric FreeCAD
  objects from any SCAD module
- **SCAD Metadata Scanner** – Lark-based parser extracts modules, functions,
  variables, includes and classifies each file by type
- **Persistent metadata cache** – TinyDB + Watchdog keeps parsed metadata
  fresh without re-parsing unchanged files; automatic invalidation on
  file-system changes
- **Variable Export** – extract top-level SCAD variables into a FreeCAD
  `App::VarSet` (with typed properties) or a Spreadsheet, controlled by
  preferences; inline `// trailing comments` are captured as property tooltips
- **DXF support** – import/export `.dxf` files via OpenSCAD

---

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| FreeCAD | ≥ 1.1 | Host application (`App::VarSet` required for variable export) |
| OpenSCAD (CLI) | any | Mesh/STL generation fallback |
| `lark` | ≥ 1.1 | SCAD source parser (usually pre-installed) |
| `tinydb` | ≥ 4.8 | Persistent metadata cache |
| `watchdog` | ≥ 4.0 | File-system change detection |

### Installing Python dependencies

> **Important:** packages must be installed into *FreeCAD's own Python*, not
> the system Python.  Use `python -m pip` via FreeCAD's bundled interpreter.

**macOS (FreeCAD app bundle):**
```bash
/Applications/FreeCAD_1.0.0.app/Contents/Resources/bin/python \
    -m pip install --user tinydb watchdog
```

**Linux (AppImage or system package):**
```bash
# Find FreeCAD's Python first
which python3   # may be FreeCAD's if activated via squashfs
# or
/path/to/FreeCAD/bin/python3 -m pip install --user tinydb watchdog
```

**Windows:**
```powershell
& "C:\Program Files\FreeCAD 1.0\bin\python.exe" -m pip install --user tinydb watchdog
```

> Note: `lark` is already bundled with FreeCAD 1.0.  
> `tinydb` and `watchdog` will be available via the Addon Manager in a future release.

---

## Installation

### Via FreeCAD Addon Manager (recommended)
1. **Tools → Addon Manager**
2. Search for **OpenSCAD_Ext**
3. Install and restart FreeCAD

### Manual
```bash
cd ~/.local/share/FreeCAD/Mod
git clone https://github.com/KeithSloan/OpenSCAD_Workbench.git OpenSCAD_Ext
```
Then restart FreeCAD.

---

## Configuration

Open **FreeCAD | Preferences | OpenSCAD_Ext** and set:

### General OpenSCAD Settings

| Preference | Description |
|---|---|
| **OpenSCAD executable** | Path to `openscad` binary (auto-detected on most systems) |
| **External Editor** | Editor launched by the *Edit SCAD* command |
| **OpenSCAD Studio** | Path to `openscad-studio` binary |
| **Default Directory** | Directory where generated `.scad` module files are written. **Must be set** before creating module objects from the library browser. |

### OpenSCAD Import

| Preference | Description |
|---|---|
| Print debug information | Verbose console output during import |
| Maximum faces for polygons (fn) | Cylinders/circles with more faces than this are treated as true circles |

### Variable Export

Controls where extracted OpenSCAD variables are stored in the FreeCAD document.

| Preference | Description |
|---|---|
| **Prompt for export option each time** | Ask which target to use on every extraction (default: on) |
| **Default export target** | Target used when prompt is off |

#### Export targets

| Target | Status | Description |
|---|---|---|
| **VarSet** | Active | Creates an `App::VarSet` document object with typed properties for each variable. Properties can be expression-bound to other FreeCAD objects. Requires FreeCAD ≥ 1.1. |
| **Vars** | Future | Integration with [Frank David Martinez's Vars extension](https://github.com/mnesarco/Vars) — deferred pending stable Vars API. |
| **Spreadsheet** | Future | Creates a FreeCAD `Spreadsheet::Sheet` object. Limited: no type metadata, vectors awkward, re-import risk. Placeholder only. |

---

## Toolbar Icons

Every workbench command has a dedicated 64×64 SVG icon.  All file-operation
icons share a **gold folded-corner document** base (matching FreeCAD's
OpenSCAD workbench palette) and carry a coloured circular badge that signals
the action:

| Icon file | Command | Badge | Colour |
|---|---|---|---|
| `newScadFileObj.svg` | New SCAD File Object | **⊕** plus | Green |
| `editScadFileObj.svg` | Edit SCAD File Object | Pencil | Blue |
| `editStudioScadFileObj.svg` | OpenSCAD Studio | Monitor | Purple |
| `renderScadFileObj.svg` | Render to Shape | **▶** play | Orange |
| `varsSCAD.svg` | Extract Variables | Spreadsheet grid | Teal |
| `librarySCAD.svg` | Library Browser | Bookshelf + magnifying glass | Amber |

The Library Browser icon deliberately breaks the document pattern — its
bookshelf motif makes it immediately distinguishable in the toolbar.

Icons live in `freecad/OpenSCAD_Ext/Resources/icons/` and are loaded via
FreeCAD's filesystem icon path (`Gui.addIconPath`); no compiled QRC is needed.

---

## Usage

### Import a SCAD or CSG file
**File → Import** – select a `.scad` or `.csg` file. FreeCAD will attempt to
build native BRep geometry; if that fails it falls back to an STL mesh via
the OpenSCAD CLI.

### OpenSCAD Library Browser

Open via the **OpenSCAD_Ext** toolbar (bookshelf icon) or menu.

The browser lists all entries under your `OPENSCADPATH` directory.  Each
`.scad` file is scanned for metadata on first view (results are cached) and
displayed with a **colour-coded file-type label and icon**:

| Display label | Enum value | Icon colour | Meaning |
|---|---|---|---|
| **Model** | `PURE_SCAD` | Green | Contains top-level geometry — produces output when rendered directly |
| **Modules** | `MODULES_ONLY` | Blue | Reusable module definitions |
| **Functions** | `FUNCTIONS_ONLY` | Teal | Mathematical / utility function definitions |
| **Mixed** | `MIXED` | Purple | Both module and function definitions |
| **Config** | `VARIABLE` | Red | Variable / constant definitions only |
| **Library** | `LIBRARY` | Orange | Only `include`/`use` aggregation |
| **Unknown** | `UNKNOWN` | Grey | Empty or unclassifiable |

#### Buttons

| Button | Enabled when | Action |
|---|---|---|
| **Create SCAD Object** | Any `.scad` file selected | Creates a base SCAD file object in the active document |
| **Scan Modules** | File has ≥ 1 module | Opens the Module Inspector dialog |
| **Extract Variables** | File has modules or top-level variables | Creates module VarSets and/or a top-level VarSet (see [Extract Variables](#extract-variables)) |
| **Refresh** | Any `.scad` file selected | Drops all caches and re-scans the file immediately |

#### Automatic cache refresh

The browser tracks each file's modification time.  If a file is edited
while the browser is open the session cache is automatically discarded on
the next access, triggering a re-scan via the TinyDB cache (which validates
content via SHA-256 before re-parsing).  Use **Refresh** to force a full
re-scan bypassing both caches.

### Module Inspector

After clicking **Scan Modules**:

1. The dialog lists all modules found in the file together with their
   `include`/`use` dependencies
2. Click a module name to see its parameters
3. Adjust parameter values in the **Arguments** panel
4. Click **Create SCAD Module** to instantiate a parametric FreeCAD object

> **Note:** The **Default Directory** preference must be set before creating
> a module object.  
> **FreeCAD | Preferences | OpenSCAD_Ext → Set 'Default Directory'**

The created object stores all module parameters as typed FreeCAD properties
and writes a minimal `.scad` file that `include`s the library and calls the
module with the current parameter values.

### Extract Variables

**Extract Variables** is available from the **Library Browser** — select a
`.scad` file and click the button.  It is also available as a toolbar command
when a SCAD file object is selected in the model tree.

If there is no active FreeCAD document when the button is pressed, a new
document is created automatically, named after the `.scad` file stem
(underscores replaced with hyphens, e.g. `linear_bearing.scad` →
document `linear-bearing`).

#### What gets created

The command produces up to two kinds of `App::VarSet` objects, silently and
without a confirmation dialog:

---

##### 1 — Module VarSets (one per module)

For every module defined in the file that has at least one parameter with a
default value, a VarSet is created whose name matches the module name.

```openscad
// Arguments:
//   d = Diameter of linear bearing. (Default: 15)
//   l = Length of linear bearing. (Default: 24)
//   ---
//   anchor = ...    ← excluded (after --- separator)
//   spin   = ...    ← excluded
module linear_bearing_housing(d=15, l=24, ..., anchor=BOTTOM, spin=0)
```

- Parameters **before** the `// ---` separator in the BOSL2 `// Arguments:`
  block are included in the VarSet.
- Parameters **after** `// ---` (typically BOSL2 attachment helpers such as
  `anchor`, `spin`, `orient`) are excluded.
- If the file does not use BOSL2-style comment blocks, all parameters with
  defaults are included with generic descriptions.
- Descriptions from `//   param = description` lines are stored as property
  tooltips (visible on hover and at the bottom of the Properties panel).

Example — `linear_bearings.scad` produces three VarSets:
```
linear_bearing_housing   (d, l, tab, gap, wall, tabwall, screwsize)
linear_bearing           (size, ...)
lmXuu_housing            (size, ...)
```

---

##### 2 — Top-level VarSet (one per file)

If the file contains top-level variable assignments (the kind OpenSCAD's own
Customizer picks up), a single VarSet is created named after the file stem.

```openscad
$fn     = 64;
n       = 8;        // Rib count
R_box   = 225;      // outer radius (= half diameter 450 mm) [mm]
dome_h  = 100;      // dome height above cylinder top        [mm]
```

- Variables whose names start with `_` are skipped (they are internal library
  guard constants, not user-facing parameters).
- Trailing `//` comments on the same line as the assignment are stored as
  property tooltips.
- The VarSet is named after the file stem (e.g. `post_box_former`).

This handles files that expose their parameters as top-level variables rather
than module arguments — exactly the pattern OpenSCAD's Customizer targets.

---

#### Property type inference

The property type for each variable or parameter is inferred from its default
expression:

| Expression | FreeCAD property type |
|---|---|
| `true` / `false` | `App::PropertyBool` |
| Integer literal | `App::PropertyInteger` |
| Float literal | `App::PropertyFloat` |
| Everything else (vectors, strings, identifiers) | `App::PropertyString` |

#### Cache and the Refresh button

The Library Browser caches parsed metadata in TinyDB, keyed by SHA-256 file
hash.  If the **parser code** itself changes (not just the `.scad` file),
existing cache entries will not contain the new fields.  In that case use the
**Refresh** button to force a full re-scan of the selected file, bypassing
both the session cache and the TinyDB cache.  Normal file edits on disk are
detected automatically and do not require a manual Refresh.

---

## SCAD Metadata Scanner

The scanner lives in `freecad/OpenSCAD_Ext/parsers/scadmeta/` and is the
engine behind the library browser.

### Public API

```python
from freecad.OpenSCAD_Ext.parsers.scadmeta import (
    scan_scad_file,
    scan_scad_directory,
    ScadMeta,
    ScadFileType,
)

meta = scan_scad_file("/path/to/shape.scad")

print(meta.file_type)        # ScadFileType.MODULES_ONLY
print(meta.module_count)     # 4
print(meta.function_count)   # 1
print(meta.variables)        # {'d': '15', 'l': '24', ...}

for mod in meta.modules:
    params = [f"{p.name}={p.default}" for p in mod.params]
    print(f"{mod.name}({', '.join(params)})")
```

### File type classification

| `ScadFileType` | Display label | Colour | Rule |
|---|---|---|---|
| `PURE_SCAD` | **Model** | Green | Has top-level geometry / executable statements |
| `MIXED` | **Mixed** | Purple | Defines both modules and functions |
| `MODULES_ONLY` | **Modules** | Blue | Module definitions (no top-level geometry) |
| `FUNCTIONS_ONLY` | **Functions** | Teal | Function definitions only |
| `VARIABLE` | **Config** | Red | Variable definitions only |
| `LIBRARY` | **Library** | Orange | Only `include`/`use` lines |
| `UNKNOWN` | **Unknown** | Grey | Empty or unclassifiable |

Classification is performed by `classify_file_type(meta)` in
`scadmeta_model.py` using a priority-order rule set.

### Caching

Results are stored in a TinyDB JSON file:

```
<FreeCAD-user-data>/OpenSCAD_Ext/scad_meta_cache.json
```

Each cache entry is validated against the file's **mtime** (cheap) and
**SHA-256 hash** (only when mtime differs).  A Watchdog observer monitors
watched directories and automatically invalidates stale entries when files
change on disk.

When running outside FreeCAD the cache defaults to:
```
~/.cache/openscad_ext/scad_meta_cache.json
```

---

## Import Strategy

When importing a `.scad` or `.csg` file FreeCAD tries two strategies:

1. **Native BRep** — builds hulls, booleans and primitives directly as
   FreeCAD Shapes.  Preserves parametric editing and high-accuracy geometry.

2. **OpenSCAD fallback** — if native BRep fails, the OpenSCAD CLI generates
   an STL which is imported as Mesh → Shape.  Tessellation (`$fn`, `$fa`,
   `$fs`) is preserved per-node.

### Supported AST nodes

| Node | Handler | Notes |
|---|---|---|
| Cube, Sphere, Cylinder | native BRep | |
| Circle, Square, Polygon | native 2-D shape | |
| Union, Difference, Intersection | native boolean | |
| Hull, Minkowski | `process_hull()` | BRep first; STL fallback |
| Translate, Rotate, Scale, MultMatrix | `process_transform()` | |
| Linear/Rotate extrude | native or fallback | |
| Other / unknown | `fallback_to_OpenSCAD()` | STL via CLI |

---

## Project Structure

```
freecad/OpenSCAD_Ext/
├── commands/               # FreeCAD commands (toolbar/menu actions)
│   ├── newSCAD.py          #   New SCAD File Object
│   ├── editSCAD.py         #   Edit SCAD File Object
│   ├── openSCADstudio.py   #   OpenSCAD Studio
│   ├── renderSCAD.py       #   Render to Shape
│   ├── varsSCAD.py         #   Extract Variables
│   └── librarySCAD.py      #   Library Browser
├── core/                   # Geometry utilities; exporters.py (variable export strategies)
├── exporters/              # SCAD / CSG / DXF export
├── gui/                    # Dialogs
│   ├── OpenSCADLibraryBrowser.py   # Library Browser dialog
│   ├── SCAD_Module_Dialog.py       # Module Inspector dialog
│   └── scad_type_display.py        # Icons, colours and labels per ScadFileType
├── importers/              # SCAD / CSG / DXF importers
├── libraries/              # OPENSCADPATH helpers
├── logger/                 # Unified logging to FreeCAD report view + file
├── objects/                # FreeCAD FeaturePython proxy objects
│   ├── SCADObject.py               # Base SCAD file object
│   ├── SCADModuleObject.py         # Parametric module instance
│   └── SCADProjectObject.py
├── parsers/
│   ├── scadmeta/                   # Lark-based SCAD metadata scanner
│   │   ├── scadmeta_grammar.py     #   Lark EBNF grammar
│   │   ├── scadmeta_lark_parser.py #   Earley parser + tree walker
│   │   ├── scadmeta_cache.py       #   TinyDB + Watchdog persistent cache
│   │   ├── scadmeta_scanner.py     #   Public scan_scad_file() entry point
│   │   └── scadmeta_model.py       #   ScadMeta / ScadFileType dataclasses
│   ├── csg_parser/                 # CSG → AST (regex-based)
│   └── lark_csg_parser/            # CSG → AST (Lark-based)
└── Resources/
    ├── OpenSCAD_Ext.svg            # Workbench icon (64×64)
    ├── icons/                      # Toolbar command icons (64×64 SVG)
    │   ├── preferences-openscad_ext.svg  # Preferences dialog entry icon
    │   ├── newScadFileObj.svg
    │   ├── editScadFileObj.svg
    │   ├── editStudioScadFileObj.svg
    │   ├── renderScadFileObj.svg
    │   ├── varsSCAD.svg
    │   └── librarySCAD.svg
    └── ui/                         # Qt Designer preference pages
```

---

## License

LGPL-2.1-or-later — see [LICENSE](LICENSE).

## Maintainer

Keith Sloan — <https://github.com/KeithSloan/OpenSCAD_Workbench>
