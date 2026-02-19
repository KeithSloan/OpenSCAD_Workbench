#from FreeCAD import Vector, Matrix, Placement, Rotation
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import bbox
import Part


def hull_cubes(cubes):
    centers = [c["center"] for c in cubes]
    sizes = [c["size"] for c in cubes]

    if any(s != sizes[0] for s in sizes):
        return None


    min_pt, max_pt = bbox(centers)
    return Part.makeBox(
        max_pt.x - min_pt.x,
        max_pt.y - min_pt.y,
        max_pt.z - min_pt.z,
        min_pt
    )
