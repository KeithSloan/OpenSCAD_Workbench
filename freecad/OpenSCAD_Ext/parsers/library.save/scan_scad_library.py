import os
from freecad.OpenSCAD_Ext.libraries.ensure_openSCADPATH import ensure_openSCADPATH
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

def scan_scad_library():
    library_path = ensure_openSCADPATH()
    write_log("Info", f"Scanning SCAD library at: {library_path}")

    if not os.path.isdir(library_path):
        write_log("Error", f"OPENSCADPATH does not exist: {library_path}")
        return []

    meta_list = []
    for fname in os.listdir(library_path):
        write_log("Info", f"Found file: {fname}")  # << add this
        if fname.lower().endswith(".scad"):
            full_path = os.path.join(library_path, fname)
            meta_list.append({"path": full_path, "modules": {}, "functions": {}})
            write_log("Info", f"Adding SCAD file: {fname}")

    if not meta_list:
        write_log("Warning", f"No SCAD files found in {library_path}")

    return meta_list

