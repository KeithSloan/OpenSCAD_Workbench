from FreeCAD import (
    Vector,
    Matrix,
    )
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_utils import (
    is_collinear,
    make_capsule, 
    make_tangent_frustum,
    detect_grid,
    )

import Part


def hull_spheres(spheres):
    write_log("Hull","Spheres")
    centers = [s["center"] for s in spheres]

    write_log("Centers",centers)

    if is_collinear(centers):
        if all(abs(s["r"] - spheres[0]["r"]) < 1e-12 for s in spheres):
            r = spheres[0]["r"]
            write_log("Spheres: make capsule")
            return make_capsule(centers[0], centers[-1], r)
            
        else:
            write_log("Spheres","Not all equal Radius")
            return make_colinear_sphere_hull(spheres)

    if not all(abs(s["r"] - spheres[0]["r"]) < 1e-12 for s in spheres):
        return None # Not handled

    r = spheres[0]["r"]
    write_log("Spheres",f" Radius {r} Type {type(r)}")

    grid = detect_grid(centers)
    if grid:
        return try_hull_spheres(centers, r)
    write_log("Spheres","Not Grid")
    return None


def try_hull_spheres(centers, r, min_thickness=1e-3):
    """
    Create a rounded hull for a set of spheres.
    Automatically handles:
      - Flat 2D grids (Z nearly zero)
      - Full 3D arrangements
    centers: list of Vector
    r: sphere radius / rounding radius
    """
    if not centers:
        return None

    min_pt = Vector(
        min(c.x for c in centers),
        min(c.y for c in centers),
        min(c.z for c in centers)
    )
    max_pt = Vector(
        max(c.x for c in centers),
        max(c.y for c in centers),
        max(c.z for c in centers)
    )

    size = max_pt - min_pt

    # Determine if flat in Z
    is_flat = size.z < 1e-6 or size.z < r

    if not is_flat:
        # Full 3D → fillet all edges
        box_size = Vector(
            max(size.x + 2*r, min_thickness),
            max(size.y + 2*r, min_thickness),
            max(size.z + 2*r, min_thickness)
        )
        placement = min_pt - Vector(r, r, r)
        box = Part.makeBox(box_size.x, box_size.y, box_size.z, placement)
        fillet_radius = min(r, box_size.x/2, box_size.y/2, box_size.z/2)
        try:
            rounded_box = box.makeFillet(fillet_radius, box.Edges)
        except Exception:
            rounded_box = box
        return rounded_box

    else:
        # Flat grid → thin box + corner spheres + XY edge cylinders
        thickness = max(size.z + 2*r, min_thickness)
        box = Part.makeBox(size.x + 2*r, size.y + 2*r, thickness,
                           min_pt - Vector(r, r, r))
        shapes = [box]

        # Corners
        corners = [
            Vector(min_pt.x - r, min_pt.y - r, min_pt.z),
            Vector(max_pt.x + r, min_pt.y - r, min_pt.z),
            Vector(min_pt.x - r, max_pt.y + r, min_pt.z),
            Vector(max_pt.x + r, max_pt.y + r, min_pt.z)
        ]
        for c in corners:
            shapes.append(Part.makeSphere(r, c))

        # XY edge cylinders
        # along X edges
        shapes.append(Part.makeCylinder(r, size.x + 2*r, corners[0], Vector(1,0,0)))
        shapes.append(Part.makeCylinder(r, size.x + 2*r, corners[2], Vector(1,0,0)))
        # along Y edges
        shapes.append(Part.makeCylinder(r, size.y + 2*r, corners[0], Vector(0,1,0)))
        shapes.append(Part.makeCylinder(r, size.y + 2*r, corners[1], Vector(0,1,0)))

        # Fuse all
        rounded_box = shapes[0]
        for s in shapes[1:]:
            rounded_box = rounded_box.fuse(s)

        return rounded_box


def make_colinear_sphere_hull(spheres):
    parts = []

    for s in spheres:
        sphere = Part.makeSphere(s['r'], s['center'])
        parts.append(sphere)

    # tangent frusta / cylinders
    for i in range(len(spheres)-1):
        a = spheres[i]
        b = spheres[i+1]

        p1 = a['center']
        r1 = a['r']
        p2 = b['center']
        r2 = b['r']

        axis = p2.sub(p1)
        d = axis.Length
        if d <= 1e-9:
            continue
        axis_norm = axis.normalize()

        if abs(r2 - r1) < 1e-9:
            cyl = Part.makeCylinder(r1, d, p1, axis_norm)
            parts.append(cyl)
        else:
            frustum = make_tangent_frustum(p1, r1, p2, r2)
            parts.append(frustum)

    # Fuse all parts, no FeaturePython, safe refine
    compound = parts[0]
    for shp in parts[1:]:
        compound = compound.fuse(shp)

    # Optional refine
    try:
        compound = compound.removeSplitter()
    except Exception:
        pass

    return compound


'''
def safe_offset(shape, r):
    try:
        offset = shape.makeOffsetShape(
            r,              # offset distance
            1e-6,           # tolerance
            join=Part.JoinType.Arc,
            fill=False,
            openResult=False,
            intersection=False
        )
        if offset and not offset.isNull():
            return offset
    except Exception:
        pass
    return shape  # fallback to original

def rounded_bbox(points, r):
    min_pt = Vector(min(p.x for p in points),
                    min(p.y for p in points),
                    min(p.z for p in points))
    max_pt = Vector(max(p.x for p in points),
                    max(p.y for p in points),
                    max(p.z for p in points))

    size = max_pt - min_pt

    # create the core box
    box = Part.makeBox(size.x, size.y, size.z, min_pt)

    # apply fillet to all edges
    edges = box.Edges
    rounded_box = box.makeFillet(r, edges)

    return rounded_box
'''