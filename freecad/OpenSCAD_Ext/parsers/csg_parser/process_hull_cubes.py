from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import bbox
import Part

TOL = 1e-7


def hull_cubes(cubes):
    """Convex hull of equal-size, axis-aligned cubes.

    The hull is the bounding box over *all cube corners* (centre ± size/2) —
    NOT the bounding box of the centres (which is too small by half a cube on
    every side, and collapses to a zero-thickness box when the centres are
    coplanar/collinear → "length of box too small").  Returns None on any
    degenerate/failure case so the caller can fall back.
    """
    if not cubes:
        return None

    sizes = [c["size"] for c in cubes]
    if any(s != sizes[0] for s in sizes):
        return None  # mixed sizes not handled analytically

    corners = []
    for c in cubes:
        cen = c["center"]
        sx, sy, sz = c["size"]
        corners.append(Vector(cen.x - sx / 2.0, cen.y - sy / 2.0, cen.z - sz / 2.0))
        corners.append(Vector(cen.x + sx / 2.0, cen.y + sy / 2.0, cen.z + sz / 2.0))

    min_pt, max_pt = bbox(corners)
    dx = max_pt.x - min_pt.x
    dy = max_pt.y - min_pt.y
    dz = max_pt.z - min_pt.z

    if dx < TOL or dy < TOL or dz < TOL:
        write_log("Hull",
                  f"hull_cubes: degenerate box ({dx:.4g},{dy:.4g},{dz:.4g}) — fallback")
        return None

    try:
        return Part.makeBox(dx, dy, dz, min_pt)
    except Exception as e:
        write_log("Hull", f"hull_cubes: makeBox failed: {e} — fallback")
        return None
