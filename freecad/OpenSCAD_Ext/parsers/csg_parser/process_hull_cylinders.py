from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    make_tangent_frustum,
    detect_grid,
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
    write_log("Hull", "Cylinders Cones")
    print(dir(cylinders[0]))
    centers = [c["center"] for c in cylinders]
    #
    # axes = [c["axis"] for c in cylinders]
    #
    # For now, only handle if all axes equal
    #if not all(a.isEqual(axes[0], 1e-9) for a in axes):
    #    write_log("Hull", "Cylinders axes not aligned, fallback")
    #    return make_colinear_cylinders_hull(cylinders)

    # Check collinearity along axis
    if is_collinear(centers):
        return make_colinear_cylinders_cones(cylinders)

    else:
        write_log("Hull", "Cylinders not collinear, fallback")
        return None


def make_colinear_cylinders_cones(primitives, TOL = 1e-9):
    if not primitives:
        return None

    # --------------------------------------------------
    # 1️⃣ Common axis (guaranteed colinear)
    # --------------------------------------------------
    axis_dir = primitives[0]["dir"]   # already unit

    # Choose a perpendicular direction for profile plane
    if abs(axis_dir.z) < 0.9:
        ref = Vector(0, 0, 1)
    else:
        ref = Vector(1, 0, 0)

    radial_dir = axis_dir.cross(ref)
    if radial_dir.Length < TOL:
        return None

    radial_dir = radial_dir / radial_dir.Length

    # --------------------------------------------------
    # 2️⃣ Convert to linear radius functions
    #     r(t) = a*t + b
    # --------------------------------------------------
    funcs = []
    breakpoints = set()

    for p in primitives:

        base = p["base"]
        dir_vec = p["dir"]
        h = p["h"]
        r1 = p["r1"]
        r2 = p["r2"]

        # project base onto axis
        t0 = base.dot(axis_dir)
        t1 = t0 + h

        if abs(t1 - t0) < TOL:
            continue

        # linear slope
        a = (r2 - r1) / (t1 - t0)
        b = r1 - a * t0

        funcs.append({
            "t0": t0,
            "t1": t1,
            "a": a,
            "b": b
        })

        breakpoints.add(t0)
        breakpoints.add(t1)

    if not funcs:
        return None

    # --------------------------------------------------
    # 3️⃣ Add intersection breakpoints
    # --------------------------------------------------
    for i in range(len(funcs)):
        for j in range(i + 1, len(funcs)):
            f1 = funcs[i]
            f2 = funcs[j]

            if abs(f1["a"] - f2["a"]) < TOL:
                continue

            t = (f2["b"] - f1["b"]) / (f1["a"] - f2["a"])

            if (f1["t0"] - TOL <= t <= f1["t1"] + TOL and
                f2["t0"] - TOL <= t <= f2["t1"] + TOL):
                breakpoints.add(t)

    t_vals = sorted(breakpoints)

    if len(t_vals) < 2:
        return None

    # --------------------------------------------------
    # 4️⃣ Upper envelope radius function
    # --------------------------------------------------
    def max_radius(t):
        rmax = 0.0
        for f in funcs:
            if f["t0"] - TOL <= t <= f["t1"] + TOL:
                r = f["a"] * t + f["b"]
                if r > rmax:
                    rmax = r
        return rmax

    # Build profile points
    profile_pts = []
    for t in t_vals:
        r = max_radius(t)
        if r > TOL:
            profile_pts.append((t, r))

    if len(profile_pts) < 2:
        return None

    # --------------------------------------------------
    # 5️⃣ Build profile wire (in 3D plane)
    # --------------------------------------------------
    edges = []

    t_start, r_start = profile_pts[0]
    t_end, r_end = profile_pts[-1]

    # Axis start/end
    axis_start = axis_dir * t_start
    axis_end = axis_dir * t_end

    # Start radial point
    first_pt = axis_dir * t_start + radial_dir * r_start
    edges.append(Part.makeLine(axis_start, first_pt))

    # Envelope segments
    for i in range(len(profile_pts) - 1):
        t0, r0 = profile_pts[i]
        t1, r1 = profile_pts[i + 1]

        p0 = axis_dir * t0 + radial_dir * r0
        p1 = axis_dir * t1 + radial_dir * r1

        edges.append(Part.makeLine(p0, p1))

    # End radial closure
    last_pt = axis_dir * t_end + radial_dir * r_end
    edges.append(Part.makeLine(last_pt, axis_end))

    # Close along axis
    edges.append(Part.makeLine(axis_end, axis_start))

    wire = Part.Wire(edges)
    face = Part.Face(wire)  # 👈 This is the key fix!

    # --------------------------------------------------
    # 6️⃣ Single clean revolution
    # --------------------------------------------------
    # Revolve around the axis
    solid = face.revolve(axis_start, axis_dir, 360)

    return solid

"""
def make_colinear_cylinders_cones(primitives, TOL = 1e-9):

    if not primitives:
        return None

    # --------------------------------------------------
    # 1️⃣ Common axis (guaranteed colinear)
    # --------------------------------------------------
    axis_dir = primitives[0]["dir"]   # already unit

    # Choose a perpendicular direction for profile plane
    if abs(axis_dir.z) < 0.9:
        ref = Vector(0, 0, 1)
    else:
        ref = Vector(1, 0, 0)

    radial_dir = axis_dir.cross(ref)
    if radial_dir.Length < TOL:
        return None

    radial_dir = radial_dir / radial_dir.Length

    # --------------------------------------------------
    # 2️⃣ Convert to linear radius functions
    #     r(t) = a*t + b
    # --------------------------------------------------
    funcs = []
    breakpoints = set()

    for p in primitives:

        base = p["base"]
        dir_vec = p["dir"]
        h = p["h"]
        r1 = p["r1"]
        r2 = p["r2"]

        # project base onto axis
        t0 = base.dot(axis_dir)
        t1 = t0 + h

        if abs(t1 - t0) < TOL:
            continue

        # linear slope
        a = (r2 - r1) / (t1 - t0)
        b = r1 - a * t0

        funcs.append({
            "t0": t0,
            "t1": t1,
            "a": a,
            "b": b
        })

        breakpoints.add(t0)
        breakpoints.add(t1)

    if not funcs:
        return None

    # --------------------------------------------------
    # 3️⃣ Add intersection breakpoints
    # --------------------------------------------------
    for i in range(len(funcs)):
        for j in range(i + 1, len(funcs)):
            f1 = funcs[i]
            f2 = funcs[j]

            if abs(f1["a"] - f2["a"]) < TOL:
                continue

            t = (f2["b"] - f1["b"]) / (f1["a"] - f2["a"])

            if (f1["t0"] - TOL <= t <= f1["t1"] + TOL and
                f2["t0"] - TOL <= t <= f2["t1"] + TOL):
                breakpoints.add(t)

    t_vals = sorted(breakpoints)

    if len(t_vals) < 2:
        return None

    # --------------------------------------------------
    # 4️⃣ Upper envelope radius function
    # --------------------------------------------------
    def max_radius(t):
        rmax = 0.0
        for f in funcs:
            if f["t0"] - TOL <= t <= f["t1"] + TOL:
                r = f["a"] * t + f["b"]
                if r > rmax:
                    rmax = r
        return rmax

    # Build profile points
    profile_pts = []
    for t in t_vals:
        r = max_radius(t)
        if r > TOL:
            profile_pts.append((t, r))

    if len(profile_pts) < 2:
        return None

    # --------------------------------------------------
    # 5️⃣ Build profile wire (in 3D plane)
    # --------------------------------------------------
    edges = []

    t_start, r_start = profile_pts[0]
    t_end, r_end = profile_pts[-1]

    # Axis start/end
    axis_start = axis_dir * t_start
    axis_end = axis_dir * t_end

    # Start radial point
    first_pt = axis_dir * t_start + radial_dir * r_start
    edges.append(Part.makeLine(axis_start, first_pt))

    # Envelope segments
    for i in range(len(profile_pts) - 1):
        t0, r0 = profile_pts[i]
        t1, r1 = profile_pts[i + 1]

        p0 = axis_dir * t0 + radial_dir * r0
        p1 = axis_dir * t1 + radial_dir * r1

        edges.append(Part.makeLine(p0, p1))

    # End radial closure
    last_pt = axis_dir * t_end + radial_dir * r_end
    edges.append(Part.makeLine(last_pt, axis_end))

    # Close along axis
    edges.append(Part.makeLine(axis_end, axis_start))

    wire = Part.Wire(edges)
    face = Part.Face(wire)

    # --------------------------------------------------
    # 6️⃣ Single clean revolution
    # --------------------------------------------------
    solid = face.revolve(axis_start, axis_dir, 360)

    return solid
"""
