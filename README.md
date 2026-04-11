# OpenSCAD Workbench (OpenSCAD_Ext)

An external FreeCAD workbench providing full OpenSCAD import/export support,
a library browser, parametric module objects, and a Lark-based SCAD metadata
scanner.

---

## Features

- **Import** `.scad` and `.csg` files into FreeCAD as native BRep shapes
  (with mesh fallback via OpenSCAD CLI)
- **Export** FreeCAD objects to `.scad` format
- **OpenSCAD Library Browser** – browse your `OPENSCADPATH` library,
  inspect modules with their parameters, and create parametric FreeCAD
  objects from any SCAD module
- **SCAD Metadata Scanner** – Lark-based parser extracts modules, functions,
  variables, includes and classifies each file by type
- **Persistent metadata cache** – TinyDB + Watchdog keeps parsed metadata
  fresh without re-parsing unchanged files
- **Spreadsheet integration** – extract top-level SCAD variables into a
  FreeCAD spreadsheet for parametric workflows
- **DXF support** – import/export `.dxf` files via OpenSCAD

---

## Requirements

| Dependency | Purpose |
|---|---|
| FreeCAD ≥ 1.0 | Host application |
| OpenSCAD (CLI) | Mesh/STL generation fallback |
| `lark` | SCAD source parser |
| `tinydb` | Persistent metadata cache |
| `watchdog` | File-system change detection |

Install Python dependencies:
```bash
pip install lark tinydb watchdog
```

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

| Preference | Description |
|---|---|
| **Default Directory** | Directory where generated `.scad` module files are written. **Must be set** before creating module objects from the library browser. |
| OpenSCAD Executable | Path to `openscad` binary (auto-detected on most systems) |
| External Editor | Editor launched by the *Edit SCAD* command |
| Timeout | OpenSCAD CLI timeout in seconds |
| FN Max | Maximum polygon resolution (`$fn`) |

---

## Usage

### Import a SCAD or CSG file
**File → Import** – select a `.scad` or `.csg` file. FreeCAD will attempt to
build native BRep geometry; if that fails it falls back to an STL mesh via
the OpenSCAD CLI.

### OpenSCAD Library Browser

1. Open via the **OpenSCAD_Ext** toolbar or menu: **OpenSCAD Library**
2. The browser lists all `.scad` files in your `OPENSCADPATH` directory,
   annotated with their detected file type:

| File Type | Meaning |
|---|---|
| `Pure SCAD` | Contains top-level geometry — produces output when run directly |
| `Modules` | Defines modules (library file) |
| `Functions` | Defines functions only |
| `Mixed` | Defines both modules and functions |
| `Variables` | Only variable definitions |
| `Library` | Only `include`/`use` aggregation |

3. Select a `.scad` file to enable actions:
   - **Scan Modules** – open the module inspector dialog
   - **Extract Variables** – populate a FreeCAD spreadsheet with top-level
     variable names and expressions

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

---

## SCAD Metadata Scanner

The scanner lives in `freecad/OpenSCAD_Ext/parsers/scadmeta/` and is the
engine behind the library browser.

### Public API

```python
from freecad.OpenSCAD_Ext.parsers.scadmeta import scan_scad_file, scan_scad_directory

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

| `ScadFileType` | Rule |
|---|---|
| `PURE_SCAD` | Has top-level geometry / executable statements |
| `MIXED` | Defines both modules and functions |
| `MODULES_ONLY` | Module definitions only |
| `FUNCTIONS_ONLY` | Function definitions only |
| `VARIABLE` | Variable definitions only |
| `LIBRARY` | Only `include`/`use` lines |
| `UNKNOWN` | Empty or unclassifiable |

### Caching

Results are stored in a TinyDB JSON cache
(`<FreeCAD-user-data>/OpenSCAD_Ext/scad_meta_cache.json`).
Cache entries are validated by mtime and SHA-256 hash.
A Watchdog observer monitors watched directories and automatically
invalidates stale entries when files change on disk.

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
├── commands/          # FreeCAD commands (toolbar/menu actions)
├── core/              # Geometry utilities, spreadsheet helpers
├── exporters/         # SCAD / CSG / DXF export
├── gui/               # Dialogs (Library Browser, Module Inspector, …)
├── importers/         # SCAD / CSG / DXF importers
├── libraries/         # OPENSCADPATH helpers
├── logger/            # Unified logging to FreeCAD report view + file
├── objects/           # FreeCAD FeaturePython proxy objects
│   ├── SCADObject.py         # Base SCAD file object
│   ├── SCADModuleObject.py   # Parametric module instance
│   └── SCADProjectObject.py
└── parsers/
    ├── scadmeta/             # Lark-based SCAD metadata scanner
    │   ├── scadmeta_grammar.py      # Lark EBNF grammar
    │   ├── scadmeta_lark_parser.py  # Earley parser + tree walker
    │   ├── scadmeta_cache.py        # TinyDB + Watchdog cache
    │   ├── scadmeta_scanner.py      # Public scan_scad_file() API
    │   └── scadmeta_model.py        # ScadMeta / ScadFileType dataclasses
    ├── csg_parser/           # CSG → AST (regex-based)
    └── lark_csg_parser/      # CSG → AST (Lark-based)
```

---

## License

LGPL-2.1-or-later — see [LICENSE](LICENSE).

## Maintainer

Keith Sloan — <https://github.com/KeithSloan/OpenSCAD_Workbench>
