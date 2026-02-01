"""
scan_scad_library.py

Scan the OpenSCAD library directory, parse annotations, classify SCAD files,
and store metadata in TinyDB for incremental updates.
"""

import os
import hashlib
from tinydb import TinyDB, Query

from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

from scadmeta.scadmeta_annotations import parse_scad_meta
from scadmeta.scadmeta_classifier import classify_scad_file, ScadType


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def file_sha256(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# -----------------------------------------------------------------------------
# Main scan function
# -----------------------------------------------------------------------------
def scan_scad_library(file_paths: list[str] = None) -> list[dict]:
    """
    Scan the SCAD library directory (or given files), parse annotations,
    classify file types, and store metadata in TinyDB for incremental updates.

    Parameters
    ----------
    file_paths : list[str], optional
        If provided, only process these files. Otherwise, scan entire library.

    Returns
    -------
    list[dict]
        Metadata dicts for each SCAD file.
    """
    library_path = ensure_openSCADPATH()
    write_log("Info", f"Scanning SCAD library at: {library_path}")

    if not os.path.isdir(library_path):
        write_log("Error", f"OPENSCADPATH does not exist: {library_path}")
        return []

    write_log("WAIT","Needs TinyDB - await FreeCAD")

    # TinyDB database in library folder
    db_path = os.path.join(library_path, ".scadmeta_db.json")
    db = TinyDB(db_path)
    File = Query()

    # Determine files to process
    if file_paths is None:
        file_paths = [
            os.path.join(library_path, f)
            for f in os.listdir(library_path)
            if f.lower().endswith(".scad")
        ]

    meta_list = []

    for full_path in file_paths:
        fname = os.path.basename(full_path)
        if not os.path.isfile(full_path):
            continue

        file_hash = file_sha256(full_path)

        # Check cache
        cached = db.get(File.path == full_path)
        if cached and cached.get("hash") == file_hash:
            write_log("Info", f"Cache hit for {fname}")
            meta_list.append(cached)
            continue

        # Process file
        write_log("Info", f"Parsing SCAD annotations for {fname}")
        meta = parse_scad_meta(full_path)

        write_log("Info", f"Classifying {fname}")
        scad_type = classify_scad_file(full_path, meta)

        entry = {
            "path": full_path,
            "hash": file_hash,
            "vars": meta.vars,
            "variable_sets": meta.variable_sets,
            "modules": meta.modules,
            "includes": meta.includes,
            "uses": meta.uses,
            "type": scad_type.name,  # store as string
        }

        # Upsert into TinyDB
        if cached:
            db.update(entry, File.path == full_path)
        else:
            db.insert(entry)

        meta_list.append(entry)

    write_log("Info", f"Finished scanning {len(meta_list)} SCAD files")
    return meta_list


# -----------------------------------------------------------------------------
# Optional test run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    for m in scan_scad_library():
        print(f"{m['path']} -> {m['type']}")

