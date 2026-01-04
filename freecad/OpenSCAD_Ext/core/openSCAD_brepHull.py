import FreeCAD
import Part

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
    r = getRadius(obj1)
    v1, v2 = base(obj1), base(obj2)

    n = someNormal(v1 - v2)
    dv = (v1 - v2).cross(n).normalize().multiply(r)

    pts = [v1 - dv, v1 + dv, v2 + dv, v2 - dv]
    wire = Part.makePolygon(pts + [pts[0]])
    face = Part.Face(wire)

    if flag2D:
        return obj1.Shape.fuse(face.fuse(obj2.Shape))

    c1 = Part.makeCircle(r, v1, axisZ(obj1))
    c2 = Part.makeCircle(r, v2, axisZ(obj2))
    return c1.fuse(face.fuse(c2))

from FreeCAD import Base

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

