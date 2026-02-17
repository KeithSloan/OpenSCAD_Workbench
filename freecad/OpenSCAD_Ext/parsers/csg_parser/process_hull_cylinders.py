from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    make_capsule,
    make_tangent_frustum,
    detect_grid,
)
import Part


def hull_cylinders(cylinders):
    """
    Handle a set of cylinders in a hull.
    - If all axes aligned and collinear, make a capsule if equal radii.
    - If different radii, create tangent frustums.
    - Otherwise fallback to generic colinear cylinders hull.
    """
    write_log("Hull", "Cylinders")
    print(dir(cylinders[0]))
    centers = [c["center"] for c in cylinders]
    axes = [c["axis"] for c in cylinders]

    # For now, only handle if all axes equal
    if not all(a.isEqual(axes[0], 1e-9) for a in axes):
        write_log("Hull", "Cylinders axes not aligned, fallback")
        return make_colinear_cylinders_hull(cylinders)

    # Check collinearity along axis
    if not is_collinear(centers):
        write_log("Hull", "Cylinders not collinear, fallback")
        return make_colinear_cylinders_hull(cylinders)

    # Check if all cylinders have same radius along their axes
    if all(abs(c["r1"] - cylinders[0]["r1"]) < 1e-12 and
           abs(c["r2"] - cylinders[0]["r2"]) < 1e-12 for c in cylinders):

        # All equal radii → make capsule
        # Use first cylinder's radii (r1 == r2)
        r = cylinders[0]["r1"]
        write_log("Hull", f"Colinear cylinders, make capsule radius {r}")
        return make_capsule(centers[0], centers[-1], r, axes[0])

    # Mixed radii → create tangent frustums between consecutive cylinders
    return make_colinear_cylinders_hull(cylinders)


def make_colinear_cylinders_hull(cylinders):
    """
    For cylinders with unequal radii or non-Z axis,
    make spheres at ends and tangent frustums between.
    """
    parts = []

    for c in cylinders:
        # Sphere at cylinder start
        r_start = c["r1"]
        center = c["center"]
        parts.append(Part.makeSphere(r_start, center))

    # Frustums / tangent cylinders
    for i in range(len(cylinders) - 1):
        a = cylinders[i]
        b = cylinders[i + 1]

        p1 = a["center"]
        r1 = a["r2"]  # top radius of first cylinder
        p2 = b["center"]
        r2 = b["r1"]  # bottom radius of next cylinder

        axis = p2.sub(p1)
        d = axis.Length
        if d <= 1e-9:
            continue
        axis_norm = axis.normalize()

        if abs(r2 - r1) < 1e-12:
            cyl = Part.makeCylinder(r1, d, p1, axis_norm)
            parts.append(cyl)
        else:
            frustum = make_tangent_frustum(p1, r1, p2, r2)
            parts.append(frustum)

    # Fuse all parts
    compound = parts[0]
    for p in parts[1:]:
        compound = compound.fuse(p)

    try:
        compound = compound.removeSplitter()
    except Exception:
        pass

    return compound
