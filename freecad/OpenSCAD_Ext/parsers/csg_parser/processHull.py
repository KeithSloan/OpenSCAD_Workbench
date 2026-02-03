from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

import Part

# -----------------------------
# Public API
# -----------------------------
def try_hull(node):
    """
    Entry point for fast hull handling.
    Returns Part.Shape or None to trigger OpenSCAD fallback.
    """
    write_log("AST", "Try Hull")
    if not hasattr(node, "children") or len(node.children) < 2:
        write_log("AST", "Not enough children for hull")
        return None
    return try_hull_dispatch(node.children)


# -----------------------------
# Dispatcher
# -----------------------------
def try_hull_dispatch(children):
    """
    Decide which fast hull pattern to try.
    Each handler either returns a Shape or None.
    """
    types = {child.type for child in children}
    write_log("Hull", f"Dispatch: types={types}, count={len(children)}")

    # All children same type
    if len(types) == 1:
        t = next(iter(types))
        if t == "sphere":
            return try_linear_spheres(children)
        if t == "cylinder":
            return try_linear_cylinders(children)
        if t == "cube":
            return try_linear_cubes(children)
        write_log("Hull", f"No handler for uniform type '{t}'")
        return None

    # Mixed types
    return try_mixed_pattern(children)

# -----------------------------
# Handlers 
# -----------------------------
def try_linear_spheres(children):
    write_log("HullSphere", f"Trying {len(children)} spheres")

    # Step 1: geometry first, sizes later
    if is_collinear(children):
        write_log("HullSphere", "Spheres are collinear")
        return try_collinear_spheres(children)

    cube_grid_ok, grid_info = is_cube_grid(children)
    if cube_grid_ok:
        write_log("HullSphere", f"Spheres form a cube grid: {grid_info}")
        return try_grid_spheres(children, grid_info)

    write_log("HullSphere", "No known fast hull pattern found")
    return None


def try_collinear_spheres(children):
    """
    Dispatcher for collinear spheres.
    Returns Part.Shape if a fast hull can be made, else None.
    """

    write_log("HullSphere", f"Trying linear hull for {len(children)} collinear spheres")

    radii = [c.Radius.Value for c in children]
    equal_radii = all(abs(r - radii[0]) < 1e-12 for r in radii)

    if equal_radii:
        write_log("HullSphere", "All spheres equal radius → make_collinear_spheres_equal")
        return make_collinear_spheres_equal(children)

    write_log("HullSphere", "Unequal radii → make_collinear_spheres (tangent cones)")
    return make_collinear_spheres(children)

def try_grid_spheres(children, grid_info):
    """
    Dispatcher for box spheres.
    Returns Part.Shape if a fast hull can be made, else None.
    """
    write_log("HullSphere","Grid of spheres")
 

# -----------------------
# Geometry implementations
# -----------------------

def make_collinear_spheres_equal(children):
    """
    Create capsule hull connecting first to last spheres (equal radii)
    """
    p0 = children[0].Placement.Base
    p1 = children[-1].Placement.Base
    r = children[0].Radius.Value
    write_log("HullSphere", f"Creating capsule from {p0} to {p1} with radius {r}")
    return make_capsule(p0, p1, r)


def make_collinear_spheres(children):
    """
    Create hull for collinear spheres with unequal radii using tangent cones.
    TODO: implement Thales-circle tangent computation
    """
    write_log("HullSphere", "Creating tangent-cone chain for unequal spheres (TODO)")
    return None


def try_linear_cylinders(children):
    """
    Attempt hull for cylinders aligned along the same axis with same height/radius.
    """
    write_log("HullCylinder", f"Trying {len(children)} cylinders")
    # TODO: numeric checks for axis alignment and dimensions
    return None


def try_linear_cubes(children):
    """
    Attempt hull for cubes arranged linearly or in grid.
    """
    write_log("HullCube", f"Trying {len(children)} cubes")
    # TODO: numeric checks for spacing, orientation
    return None


def try_mixed_pattern(children):
    """
    Attempt hull for mixed types (spheres, cubes, cylinders, etc).
    """
    write_log("HullMixed", f"Trying {len(children)} mixed objects")
    # TODO: identify patterns like BOSL2 chain_hull()
    return None

# ---------------------------------------------------
# Support functions 
# ---------------------------------------------------
def get_centers(children):
    """Extract placement vectors for all children."""
    return [child.Placement.Base for child in children]

def is_collinear(children, tol=1e-15):
    """Return True if all children centers lie on a line."""
    centers = get_centers(children)
    if len(centers) < 2:
        return True  # trivially collinear

    line_vec = centers[1] - centers[0]
    line_len = line_vec.Length
    if line_len < tol:
        return True  # first two centers identical

    for c in centers[2:]:
        v = c - centers[0]
        # cross product ~ 0 if collinear
        if (v.cross(line_vec)).Length > tol * line_len:
            return False
    return True

def is_cube_grid(children, tol=1e-15):
    """
    Return True if all centers form a regular 3D grid.
    Optionally, return a 3-tuple of arrays: (x_coords, y_coords, z_coords)
    """
    centers = get_centers(children)
    xs = sorted(set(round(c.x / tol) for c in centers))
    ys = sorted(set(round(c.y / tol) for c in centers))
    zs = sorted(set(round(c.z / tol) for c in centers))

    grid_size = len(xs) * len(ys) * len(zs)
    if grid_size != len(centers):
        return False  # number of unique coords does not match number of points

    return True, (xs, ys, zs)

# ------------------------------------------------------
# Shape making functions
# ------------------------------------------------------
def make_capsule(p0, p1, radius):
    """
    Create exact capsule solid between p0 and p1 using:
      - cylinder
      - two hemispheres (exact BREP, no polygon)
    """

    axis_vec = p1.sub(p0)
    length = axis_vec.Length

    if length <= 1e-12:
        # Degenerate → single sphere
        return Part.makeSphere(radius, p0)

    axis_dir = axis_vec.normalize()

    # Cylinder along axis_vec
    cyl = Part.makeCylinder(radius, length, p0, axis_dir)

    # Hemispheres at both ends
    # angle1: start longitude, angle2: sweep longitude
    # angle3: sweep latitude
    # For hemispheres: latitude sweep = 180
    hemi1 = Part.makeSphere(radius, p0, axis_dir, 0, 360, 0, 90)   # start cap
    hemi2 = Part.makeSphere(radius, p1, axis_dir, 0, 360, 90, 90)  # end cap

    # Fuse solids (only once)
    capsule = cyl.fuse(hemi1).fuse(hemi2)

    return capsule

