import FreeCAD
import Part
import math
from FreeCAD import Base

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

# ============================================================
# Unit-safe helpers
# ============================================================

def _val(x):
    return float(x.Value) if hasattr(x, "Value") else float(x)

def getRadius(obj, which=0):
    if hasattr(obj, "Radius"):
        return _val(obj.Radius)
    if hasattr(obj, "Radius1") and hasattr(obj, "Radius2"):
        return _val(obj.Radius1 if which == 1 else obj.Radius2)
    raise AttributeError(f"{obj.Name}: no radius")

def getHeight(obj):
    if hasattr(obj, "Height"):
        return _val(obj.Height)
    raise AttributeError(f"{obj.Name}: no height")

def axisZ(obj):
    return obj.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))

def base(obj):
    b = obj.Placement.Base
    return FreeCAD.Vector(float(b.x), float(b.y), float(b.z))

# ============================================================
# Entry point
# ============================================================

def create_Brep_Hull_Shape(group):
    """
    group: list of FreeCAD Part objects
    Returns Part.Shape or None
    """

    if not group or len(group) < 2:
        return None

    obj0 = group[0]

    # -------------------------
    # Two-object special cases
    # -------------------------
    if len(group) == 2:
        obj1 = group[1]

        if chk2D(obj0) and chk2D(obj1):
            if getRadius(obj0) == getRadius(obj1):
                return hullTwoEqCircles(obj0, obj1, True)
            return hullTwoCircles(obj0, obj1, True)

        if obj0.TypeId == "Part::Sphere" and obj1.TypeId == "Part::Sphere":
            if getRadius(obj0) == getRadius(obj1):
                return hullTwoEqSpheres(obj0, obj1)
            return hullTwoSpheres(obj0, obj1)

    # -------------------------
    # Multi-object checks
    # -------------------------
    if chkParallel(group):

        if chkCollinear(group) and chkCircular(group):
            pts = []
            for obj in group:
                h, r1, r2 = getCircularDetails(obj)
                ax = obj.Placement.Base.dot(axisZ(obj))
                bx = ax + h
                pts += [
                    FreeCAD.Vector(0, 0, ax),
                    FreeCAD.Vector(0, r1, ax),
                    FreeCAD.Vector(0, r2, bx),
                    FreeCAD.Vector(0, 0, bx),
                ]

            rev = createRevolveHull(pts)
            rev.Placement.Rotation = obj0.Placement.Rotation
            return rev

        if len(group) == 2:
            obj1 = group[1]
            if chkOrthogonal(obj0, obj1):

                if obj0.TypeId == obj1.TypeId == "Part::Cylinder":
                    if getHeight(obj0) == getHeight(obj1):
                        face = hullTwoCircles(obj0, obj1, False)
                        return face.extrude(axisZ(obj0).multiply(getHeight(obj0)))

                if (
                    obj0.TypeId == "Part::Cylinder"
                    and obj1.TypeId == "Part::Sphere"
                ) or (
                    obj1.TypeId == "Part::Cylinder"
                    and obj0.TypeId == "Part::Sphere"
                ):
                    cyl, sph = (obj0, obj1) if obj0.TypeId == "Part::Cylinder" else (obj1, obj0)
                    if getRadius(cyl) == getRadius(sph):
                        return hullSphereCylinderEqRad(cyl, sph)

    write_log("Info", "Hull not directly handled")
    return None

# ============================================================
# Geometry classification
# ============================================================

def chk2D(obj):
    shp = obj.Shape
    if shp.isNull():
        return True
    if shp.ShapeType in ("Wire", "Edge", "Face"):
        return True
    return abs(shp.Volume) < 1e-9

def chkParallel(group):
    r0 = group[0].Placement.Rotation
    for obj in group[1:]:
        if not FreeCAD.Rotation.isSame(r0, obj.Placement.Rotation, 1e-12):
            return False
    return True

def chkCollinear(group):
    obj0 = group[0]
    ax = axisZ(obj0)
    for obj in group[1:]:
        dv = obj0.Placement.Base - obj.Placement.Base
        if dv.cross(ax).Length > 1e-12 * dv.Length:
            return False
    return True

def chkOrthogonal(obj1, obj2):
    dv = obj1.Placement.Base - obj2.Placement.Base
    return abs(axisZ(obj1).dot(dv)) < 1e-12 * dv.Length

def chkCircular(group):
    return all(o.TypeId in ("Part::Cylinder", "Part::Cone") for o in group)

def getCircularDetails(obj):
    if hasattr(obj, "Radius"):
        return getHeight(obj), getRadius(obj), getRadius(obj)
    return getHeight(obj), getRadius(obj, 1), getRadius(obj, 2)

# ============================================================
# Hull constructors
# ============================================================

def hullTwoEqCircles(obj1, obj2, flag2D):
    """
    Hull between two equal circles.
    flag2D: True for 2D compound, False for 3D fusion.
    """

    # Radii in mm
    r = obj1.Radius.getValueAs('mm')
    v1 = obj1.Placement.Base
    v2 = obj2.Placement.Base

    # Normal vector perpendicular to line connecting centers
    nm = someNormal(v1 - v2)
    dv = (v1 - v2).cross(nm)
    dn = dv.normalize()
    dr = dn * r

    # Points around the circles
    t11 = v1 - dr
    t12 = v1 + dr
    t21 = v2 + dr
    t22 = v2 - dr

    # Connecting lines
    l1 = Part.makeLine(t11, t12)
    l2 = Part.makeLine(t12, t21)
    l3 = Part.makeLine(t21, t22)
    l4 = Part.makeLine(t22, t11)

    wire = Part.Wire([l1, l2, l3, l4])
    face = Part.makeFace(wire)

    #
    # test fix
    #

    return Part.makeCompound([obj1.Shape, obj2.Shape, face])
    
    if flag2D:
        # Combine shapes efficiently using Compound instead of fuse
        return Part.makeCompound([obj1.Shape, obj2.Shape, face])
    else:
        # 3D path: create circles as shapes and fuse
        s1 = Part.makeCircle(r, v1)
        s2 = Part.makeCircle(r, v2)
        return s1.fuse(face.fuse(s2))


def hullTwoCircles(obj1, obj2, flag2D):
    """
    Create a "hull" face between two circles, supporting equal and unequal radii.
    flag2D: True for 2D fusion, False for 3D fusion with extra circles.
    """

    # Get radii in mm
    r1 = obj1.Radius.getValueAs('mm')
    r2 = obj2.Radius.getValueAs('mm')

    # If radii are equal, use simpler hull
    if abs(r1 - r2) < 1e-6:
        return hullTwoEqCircles(obj1, obj2, flag2D)

    # Ensure obj1 is the larger circle
    if r2 > r1:
        obj1, obj2 = obj2, obj1
        r1, r2 = r2, r1

    # Geometric circles for computations
    c1 = Part.Circle(obj1.Placement.Base, obj1.Placement.Rotation.Axis, r1)
    c2 = Part.Circle(obj2.Placement.Base, obj2.Placement.Rotation.Axis, r2)

    # Helper circle at c1 with radius = difference of radii
    c3 = Part.Circle()
    c3.Center = obj1.Placement.Base
    c3.Radius = r1 - r2

    # Midpoint for Thales circle
    v1 = obj1.Placement.Base
    v2 = obj2.Placement.Base
    v3 = (v1 + v2) * 0.5

    # Thales circle through centers
    c4 = Part.Circle()
    c4.Center = v3
    c4.Radius = (v1 - v2).Length / 2

    # Intersections of Thales circle and helper circle
    points = c4.intersect(c3)
    if len(points) != 2:
        raise ValueError(f"Expected 2 intersection points, got {len(points)}")
    p1, p2 = points

    # Convert to parameters on helper circle
    t1 = c3.parameter(to_vector(p1))
    t2 = c3.parameter(to_vector(p2))

    # Trim arcs
    a1 = c1.trim(t2, math.pi*2 + t1).toShape()  # Big circle long arc
    a2 = c2.trim(t1, t2).toShape()              # Small circle short arc

    # Connecting lines
    l1 = Part.makeLine(c1.value(t1), c2.value(t1))
    l2 = Part.makeLine(c2.value(t2), c1.value(t2))

    # Make wire and face
    wire = Part.Wire([a1, l1, a2, l2])
    face = Part.makeFace(wire)

    if flag2D:
        # Fuse with original circle shapes for 2D
        obj1.recompute()
        obj2.recompute()
        return obj1.Shape.fuse(face.fuse(obj2.Shape))
    else:
        # Create small 3D circles for fusion
        s1 = Part.makeCircle(r1, v1)
        s2 = Part.makeCircle(r2, v2)
        return s1.fuse(face.fuse(s2))


def to_vector(p):
    """
    Version Safe
    Convert Part.Vertex, Part.Point, or Base.Vector to Base.Vector
    """
    # Vertex → Base.Vector
    if hasattr(p, "Point"):
        return p.Point
    # Part.Point (legacy) → Base.Vector
    if hasattr(p, "X") and hasattr(p, "Y") and hasattr(p, "Z"):
        return Base.Vector(p.X, p.Y, p.Z)
    # Already Base.Vector
    return p

def hullTwoSpheres(obj1, obj2):
    if getRadius(obj2) > getRadius(obj1):
        obj1, obj2 = obj2, obj1

    v1, v2 = base(obj1), base(obj2)
    n = someNormal(v1 - v2)

    r1, r2 = getRadius(obj1), getRadius(obj2)

    c1 = Part.Circle(v1, n, r1)
    c2 = Part.Circle(v2, n, r2)
    c3 = Part.Circle(v1, n, r1 - r2)

    mid = (v1 + v2) * 0.5
    c4 = Part.Circle(mid, n, (v1 - v2).Length / 2)

    p1, p2 = c4.intersect(c3)

    # Extract Base.Vector from Part.Vertex
    def vertex_to_vector(v):
        return getattr(v, "Point", v)

    t1 = c3.parameter(to_vector(p1))
    t2 = c3.parameter(to_vector(p2))
    t3 = (t1 + t2) / 2

    a1 = c1.trim(t3 + 3.141592653589793, t1 + 2 * 3.141592653589793)
    a2 = c2.trim(t1, t3)

    l1 = Part.makeLine(c1.value(t1), c2.value(t1))
    l2 = Part.makeLine(c2.value(t3), c1.value(t3 + 3.141592653589793))

    wire = Part.Wire([a1.toShape(), l1, a2.toShape(), l2])

    base_pt = c1.value(t3 + 3.141592653589793)
    axis = c2.value(t3) - base_pt
    return wire.revolve(base_pt, axis)

def hullTwoEqSpheres(obj1, obj2):
    r = getRadius(obj1)

    p1 = obj1.Placement.Base
    p2 = obj2.Placement.Base
    axis = p2 - p1

    # Cylinder between sphere centers
    cyl = Part.makeCylinder(
        r,
        axis.Length,
        p1,
        axis
    )

    # Combine: sphere + cylinder + sphere
    shapes = [obj1.Shape, cyl, obj2.Shape]

    return Part.makeCompound(shapes)


def hullTwoSpheres(obj1, obj2):
    if getRadius(obj2) > getRadius(obj1):
        obj1, obj2 = obj2, obj1

    v1, v2 = base(obj1), base(obj2)
    n = someNormal(v1 - v2)

    r1, r2 = getRadius(obj1), getRadius(obj2)

    c1 = Part.Circle(v1, n, r1)
    c2 = Part.Circle(v2, n, r2)
    c3 = Part.Circle(v1, n, r1 - r2)

    mid = (v1 + v2) * 0.5
    c4 = Part.Circle(mid, n, (v1 - v2).Length / 2)

    p1, p2 = c4.intersect(c3)
    t1 = c3.parameter(to_vector(p1))
    t2 = c3.parameter(to_vector(p2))
    t3 = (t1 + t2) / 2

    a1 = c1.trim(t3 + 3.141592653589793, t1 + 2 * 3.141592653589793)
    a2 = c2.trim(t1, t3)

    l1 = Part.makeLine(c1.value(t1), c2.value(t1))
    l2 = Part.makeLine(c2.value(t3), c1.value(t3 + 3.141592653589793))

    wire = Part.Wire([a1.toShape(), l1, a2.toShape(), l2])

    base_pt = c1.value(t3 + 3.141592653589793)
    axis = c2.value(t3) - base_pt
    return wire.revolve(base_pt, axis)

def hullSphereCylinderEqRad(cyl, sph):
    return Part.makeCompound([cyl.Shape, sph.Shape])

# ============================================================
# Utilities
# ============================================================

def someNormal(v):
    if v.Length < 1e-12:
        return FreeCAD.Vector(0, 0, 1)
    for a in (FreeCAD.Vector(1, 0, 0),
              FreeCAD.Vector(0, 1, 0),
              FreeCAD.Vector(0, 0, 1)):
        n = v.normalize().cross(a)
        if n.Length > 0.5:
            return n.normalize()
    return FreeCAD.Vector(0, 0, 1)

def createRevolveHull(points):
    pts = sorted(points, key=lambda p: p.z)
    hull = [pts[0], pts[1]]

    for p in pts[2:]:
        hull.append(p)
        while len(hull) > 2 and not _isConvex(*hull[-3:]):
            del hull[-2]

    hull.append(hull[0])
    poly = Part.makePolygon(hull)
    return poly.revolve(
        FreeCAD.Vector(0, 0, 0),
        FreeCAD.Vector(0, 0, 1),
        360
    )

def _isConvex(p, q, r):
    return (q.x * r.z + p.x * q.z + r.x * p.z
           - q.x * p.z - r.x * q.z - p.x * r.z) < 0

