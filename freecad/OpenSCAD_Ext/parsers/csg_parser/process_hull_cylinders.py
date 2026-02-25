from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    #make_tangent_frustum,
    #detect_grid,
)
import Part


def hull_cylinders_cones(cylinders):
    """
    OpenSCAD is really a cone, cylinder if r1 = r2
    Handle a set of cylinders in a hull.
    - If all axes aligned and collinear, make a capsule if equal radii.
    - If different radii, create tangent frustums.
    - Otherwise fallback to generic colinear cylinders hull.
    """
    write_log("Hull", "Attempting to hull cylinders/cones.")

    if not cylinders:
        return None

    # --- Check for aligned axes ---
    # All cylinders/cones must have parallel axes for this handler.
    # We check against the first primitive's direction.
    first_dir = cylinders[0]["dir"]
    for c in cylinders[1:]:
        # Allow for parallel or anti-parallel axes
        if not (c["dir"].isEqual(first_dir, 1e-9) or c["dir"].isEqual(first_dir.negative(), 1e-9)):
            write_log("Hull", "Cylinder axes are not parallel, fallback.")
            return None

    # --- Check for collinear centers ---
    # If axes are parallel, centers must be collinear for a simple revolved hull.
    centers = [c["center"] for c in cylinders]
    if not is_collinear(centers):
        write_log("Hull", "Cylinders not collinear, fallback.")
        return None

    # If checks pass, proceed with generating the revolved hull
    return make_colinear_cylinders_cones(cylinders)

def make_colinear_cylinders_cones(primitives, TOL=1e-9):

    if not primitives:
        return None

    # ---------------------------------------
    # Axis direction (already unit from normalize)
    # ---------------------------------------
    axis_dir = primitives[0]["dir"]

    # Use global origin for projection stability
    axis_origin = Vector(0, 0, 0)

    # ---------------------------------------
    # Construct perpendicular radial direction
    # ---------------------------------------
    if abs(axis_dir.z) < 0.9:
        ref = Vector(0, 0, 1)
    else:
        ref = Vector(1, 0, 0)

    radial_dir = axis_dir.cross(ref)
    if radial_dir.Length == 0:
        return None
    radial_dir = radial_dir.normalize()

    # ---------------------------------------
    # Collect disc endpoints in (z, r)
    # ---------------------------------------
    pts = []

    for p in primitives:
        base = p["base"]  # The start point of the cylinder's axis
        h = p["h"]        # The height of the cylinder
        dir_vec = p["dir"]  # The direction vector of the cylinder's axis
        r1 = p["r1"]      # Radius at the base
        r2 = p["r2"]      # Radius at the top

        # The other end of the cylinder's axis
        top = base + dir_vec * h

        # Project the base and top points onto the common axis direction
        # to get their positions along that axis.
        z_base = base.dot(axis_dir)
        z_top = top.dot(axis_dir)

        pts.append((z_base, r1))
        pts.append((z_top, r2))

    # Sort by z
    pts.sort(key=lambda x: x[0])

    # ---------------------------------------
    # Compute upper convex hull in (z, r)
    # ---------------------------------------
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    upper = []

    for p in pts:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) >= -TOL:
            upper.pop()
        upper.append(p)

    if len(upper) < 2:
        return None

    # ---------------------------------------
    # Build 2D profile in 3D space
    # ---------------------------------------
    edges = []

    z_start, r_start = upper[0]
    z_end, r_end = upper[-1]

    axis_start = axis_origin + axis_dir * z_start
    axis_end   = axis_origin + axis_dir * z_end

    # Axis to first radius
    first_pt = axis_start + radial_dir * r_start
    edges.append(Part.makeLine(axis_start, first_pt))

    # Hull profile segments
    for i in range(len(upper) - 1):
        z0, r0 = upper[i]
        z1, r1 = upper[i + 1]

        p0 = axis_origin + axis_dir * z0 + radial_dir * r0
        p1 = axis_origin + axis_dir * z1 + radial_dir * r1

        edges.append(Part.makeLine(p0, p1))

    # Close back to axis
    last_pt = axis_end + radial_dir * r_end
    edges.append(Part.makeLine(last_pt, axis_end))
    edges.append(Part.makeLine(axis_end, axis_start))

    wire = Part.Wire(edges)
    face = Part.Face(wire)

    # ---------------------------------------
    # Revolve full 360 degrees
    # ---------------------------------------
    shape = face.revolve(axis_origin, axis_dir, 360)

    if shape.ShapeType == "Shell":
        shape = Part.Solid(shape)

    shape = shape.removeSplitter()
    shape.fix(1e-7, 1e-7, 1e-7)

    return shape