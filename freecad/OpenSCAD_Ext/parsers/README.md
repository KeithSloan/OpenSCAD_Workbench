# parsers/

This directory contains several **distinct subsystems** related to parsing,
analysis, metadata extraction, and library scanning for OpenSCAD / CSG files.

Historically these evolved together, so not everything here is a “parser” in
the compiler sense. This README documents the intended responsibilities of each
area.

---

## 1. Language / AST parsing (core infrastructure)

These modules perform **real parsing** of source files into ASTs and process
geometry semantics. They are foundational and should not depend on UI or
metadata layers.

### csg_parser/
Full CSG language parsing and AST pipeline.

Contents include:
- `ast_nodes.py` – AST node definitions
- `ast_helpers.py`, `ast_utils.py` – AST utilities
- `parse_csg_file_to_AST_nodes.py` – entry point for parsing CSG files
- `normalize_AST.py` – AST normalization
- `processAST.py` – AST processing
- `process_polyhedron.py` – geometry handling

These files:
- operate on source semantics
- do **not** deal with library scanning
- do **not** extract UI metadata

### ast_helper / ast_hull_minkowski
Shared AST-level helpers and geometry operations used by the CSG parser.

---

## 2. Metadata extraction (comment / annotation based)

These modules extract **lightweight metadata** from source files, primarily
from structured comments intended for tooling and UI use.

They do **not** build ASTs and do **not** interpret full language semantics.

### scadmeta/
Metadata support for OpenSCAD files.

Typical responsibilities:
- parse comment annotations such as:
  - `// @var`
  - `// @set`
  - `// @module`
  - `// @include`
  - `// @use`
- provide structured metadata objects for UI and tooling

Key files:
- `scadmeta_annotations.py` – parses comment-based directives
- `scadmeta_lexer.py` – shared tokenisation utilities
- `scadmeta_model.py` – data models / enums
- `scadmeta_parser.py` – higher-level SCAD metadata parsing / classification

### csgmeta/
Equivalent metadata extraction for CSG files (annotation-driven, not AST-based).

---

## 3. Library scanning / orchestration

These modules coordinate **directory-level operations** and act as controllers
between parsers, metadata, caching, and the UI.

They are **not language parsers**, despite historical naming.

Typical responsibilities:
- scanning directories of SCAD libraries
- calling metadata extraction and classification
- caching results (e.g. hashes, TinyDB)
- feeding Qt dialogs / models

Files include:
- `scan_scad_library` – directory scanning and orchestration
- `parse_library_scad` – UI-facing loader for SCAD libraries
- `parse_scad_mf_csf.py` – legacy / experimental multi-file parsing support

Some of these are legacy and may be refactored or renamed over time.

---

## 4. Design principles

- **AST parsing** (CSG) is kept separate from **metadata extraction**
- Metadata parsing is intentionally lightweight and regex-based
- Directory scanning and caching belong above file-level parsing
- UI code should consume metadata, not perform parsing itself

---

## 5. Notes for maintainers

If you are:
- working on geometry or semantics → look in `csg_parser/`
- extracting library/UI information → look in `scadmeta/` or `csgmeta/`
- modifying library dialogs or scanning behaviour → look in scanning/orchestration files

When adding new code, please try to place it according to these boundaries.

