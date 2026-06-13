# =============================================================================
# process_hull_mixed_curve.py
#
# Analytical convex hull for sphere + polyhedron — no meshing, no OpenSCAD.
# Extracted from BRepHull.FCMacro algorithm.
#
# Exports:
#   hull_sphere_polyhedron(sphere_shape, poly_shape) → Part.Shape or None
# =============================================================================

import math
import Part
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

TOL  = 1e-6
NTOL = 1e-3

def _unit(v):
    L = v.Length
    return Vector(v.x/L, v.y/L, v.z/L) if L > TOL else Vector(0, 0, 1)

def _surf_type(face):
    s = face.Surface
    if isinstance(s, Part.Plane):         return 'plane'
    if isinstance(s, Part.Sphere):        return 'sphere'
    if isinstance(s, Part.Cylinder):      return 'cylinder'
    if isinstance(s, Part.Cone):          return 'cone'
    if isinstance(s, Part.Toroid):        return 'toroid'
    if hasattr(Part, 'Ellipsoid') and isinstance(s, Part.Ellipsoid):
        return 'ellipsoid'
    if isinstance(s, Part.BSplineSurface): return 'bspline'
    if isinstance(s, Part.BezierSurface):  return 'bezier'
    return 'other'

def _edge_key(e):
    return tuple(sorted(
        (round(v.X, 4), round(v.Y, 4), round(v.Z, 4))
        for v in e.Vertexes
    ))

def _classify(face, e_away):
    ft = _surf_type(face)
    u0, u1, v0, v1 = face.ParameterRange

    def _sample_dots(nu=4, nv=4):
        out = []
        for i in range(nu):
            for j in range(nv):
                u = u0 + (i+0.5)*(u1-u0)/nu
                v = v0 + (j+0.5)*(v1-v0)/nv
                try:
                    out.append(face.normalAt(u, v).dot(e_away))
                except Exception:
                    pass
        return out

    if ft == 'plane':
        try:
            d = face.normalAt(0.5*(u0+u1), 0.5*(v0+v1)).dot(e_away)
        except Exception:
            return 0
        if   d >  NTOL: return  1    # outer
        if   d < -NTOL: return -1    # inner
        return 0                     # transverse

    dots = _sample_dots()
    if not dots:
        return 0
    pos = any(d >  NTOL for d in dots)
    neg = any(d < -NTOL for d in dots)
    if pos and not neg: return  1
    if neg and not pos: return -1
    return 2                         # mixed — silhouette runs through this face


def _sphere_silhouette_wire(face, e_toward):
    """Great circle of sphere perpendicular to e_toward."""
    s   = face.Surface
    cen = Vector(s.Center.x, s.Center.y, s.Center.z)
    R   = s.Radius
    circle = Part.Circle(cen, e_toward, R)
    return Part.Wire([circle.toShape()])


def _make_sphere_cap(sphere_face, e_away):
    """Return hemisphere BRep shell facing away from partner."""
    import FreeCAD
    s   = sphere_face.Surface
    cen = Vector(s.Center.x, s.Center.y, s.Center.z)
    R   = s.Radius

    z = Vector(0, 0, 1)
    cross = z.cross(e_away)
    if cross.Length < TOL:
        rot = FreeCAD.Rotation() if e_away.dot(z) > 0 else FreeCAD.Rotation(Vector(1,0,0), 180)
    else:
        angle = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(e_away)))))
        rot   = FreeCAD.Rotation(_unit(cross), angle)

    hemi = Part.makeSphere(R, Vector(0,0,0), Vector(0,0,1), 0, 90, 360)
    mat = FreeCAD.Placement(cen, rot).Matrix
    hemi.transformShape(mat)

    sph_faces = [f for f in hemi.Faces if isinstance(f.Surface, Part.Sphere)]
    if sph_faces:
        try:
            return Part.makeShell(sph_faces)
        except Exception:
            return sph_faces[0]
    return hemi


def _poly_silhouette_wires(shape, e_away):
    """
    Extract polyhedral silhouette wires from a shape.
    Silhouette = edges shared by inner faces and cap (outer+transverse) faces.
    Returns list of Part.Wire.
    """
    outer, inner, transv = [], [], []
    for f in shape.Faces:
        c = _classify(f, e_away)
        if   c ==  1: outer.append(f)
        elif c == -1: inner.append(f)
        elif c ==  0: transv.append(f)

    cap_faces = outer + transv
    write_log("Hull", f"  poly: outer={len(outer)} inner={len(inner)} transv={len(transv)}")

    cap_edge_keys = set()
    for f in cap_faces:
        for e in f.Edges:
            cap_edge_keys.add(_edge_key(e))

    sil_edge_dict = {}
    for f in inner:
        for e in f.Edges:
            k = _edge_key(e)
            if k in cap_edge_keys and k not in sil_edge_dict:
                sil_edge_dict[k] = e

    sil_edges = list(sil_edge_dict.values())
    if not sil_edges:
        return [], cap_faces

    poly_wires = []
    try:
        groups = Part.sortEdges(sil_edges)
        for grp in groups:
            try:
                poly_wires.append(Part.Wire(grp))
            except Exception:
                pass
    except Exception:
        poly_wires = [Part.Wire([e]) for e in sil_edges]

    return poly_wires, cap_faces


def _wire_to_bspline(wire, n_pts=64):
    """Resample a wire as a closed BSpline for mixed-type lofts."""
    pts = []
    for e in wire.Edges:
        t0, t1 = e.ParameterRange
        step = max(1, len(wire.Edges))
        for k in range(n_pts // step):
            t = t0 + k*(t1-t0)/(n_pts // step)
            try:
                pts.append(Vector(e.Curve.value(t)))
            except Exception:
                pass
    if not pts:
        return wire
    pts.append(pts[0])
    try:
        c = Part.BSplineCurve()
        c.interpolate(pts, PeriodicFlag=True)
        return Part.Wire([c.toShape()])
    except Exception:
        return wire


def _build_bridge(sil_wires_A, sil_wires_B):
    """Loft between silhouette wires of A and B. Returns list of faces."""
    bridge_faces = []
    for wA in sil_wires_A:
        for wB in sil_wires_B:
            loft = None
            try:
                loft = Part.makeLoft([wA, wB], False, False, False)
            except Exception:
                try:
                    loft = Part.makeLoft(
                        [_wire_to_bspline(wA), _wire_to_bspline(wB)],
                        False, False, False
                    )
                except Exception:
                    pass
            if loft is not None:
                bridge_faces.extend(loft.Faces)
    return bridge_faces


def hull_sphere_polyhedron(sphere_shape, poly_shape):
    """
    Analytical convex hull of a sphere + polyhedron.
    Returns Part.Solid, or None if not applicable.
    """
    import FreeCAD as _fc

    # Verify types
    _fc.Console.PrintMessage("[MIXED] hull_sphere_polyhedron called\n")
    face_types = [_surf_type(f) for f in sphere_shape.Faces]
    _fc.Console.PrintMessage(f"[MIXED] sphere_shape face types: {face_types}\n")
    sphere_faces = [f for f in sphere_shape.Faces if _surf_type(f) == 'sphere']
    if not sphere_faces:
        _fc.Console.PrintMessage(f"[MIXED] no sphere faces found in {sphere_shape.Faces.__len__()} faces\n")
        return None  # not a sphere

    has_curved = any(_surf_type(f) != 'plane' for f in poly_shape.Faces)
    if has_curved:
        _fc.Console.PrintWarning(f"[MIXED] poly shape has non-flat faces, returning None\n")
        return None  # polyhedron has non-flat faces — use general handler

    try:
        _fc.Console.PrintMessage("[MIXED] entering main logic\n")
    except Exception:
        pass

    # ── Axis ──────────────────────────────────────────────────────────────
    cA = sphere_shape.CenterOfMass if sphere_shape.Volume > 0 else sphere_shape.BoundBox.Center
    cB = poly_shape.CenterOfMass if poly_shape.Volume > 0 else poly_shape.BoundBox.Center
    _fc.Console.PrintMessage(
        f"[MIXED] sphere COG=({cA.x:.2f},{cA.y:.2f},{cA.z:.2f}) "
        f"cube COG=({cB.x:.2f},{cB.y:.2f},{cB.z:.2f})\n"
    )
    d  = cB - cA
    if d.Length < TOL:
        return None
    e_AB = _unit(d)
    e_BA = Vector(-e_AB.x, -e_AB.y, -e_AB.z)

    write_log("Hull", f"sphere+poly axis: A→B=({e_AB.x:.3f},{e_AB.y:.3f},{e_AB.z:.3f})")

    # ── Sphere: silhouette + cap ──────────────────────────────────────────
    # Use e_AB (NOT e_BA) for both so lofts don't twist
    _fc.Console.PrintMessage("[MIXED] extracting sphere silhouette...\n")
    try:
        sphere_sil = _sphere_silhouette_wire(sphere_faces[0], e_AB)
        _fc.Console.PrintMessage("[MIXED] sphere silhouette OK\n")
    except Exception as ex:
        _fc.Console.PrintError(f"[MIXED] sphere silhouette failed: {ex}\n")
        import traceback
        _fc.Console.PrintError(traceback.format_exc())
        return None
    try:
        sphere_cap = _make_sphere_cap(sphere_faces[0], e_BA)
        _fc.Console.PrintMessage("[MIXED] sphere cap OK\n")
    except Exception as ex:
        _fc.Console.PrintError(f"[MIXED] sphere cap failed: {ex}\n")
        sphere_cap = None

    # ── Polyhedron: silhouette + cap faces ────────────────────────────────
    _fc.Console.PrintMessage("[MIXED] extracting poly silhouette...\n")
    poly_wires, poly_cap_faces = _poly_silhouette_wires(poly_shape, e_AB)

    if not sphere_sil or not poly_wires:
        msg = "sphere+poly: missing silhouette — cannot build bridge"
        _fc.Console.PrintWarning(f"[MIXED] {msg}\n")
        write_log("Hull", msg)
        return None

    write_log("Hull", f"sphere+poly: {len(poly_wires)} poly wire(s), sphere_cap={sphere_cap is not None}")

    # ── Bridge ────────────────────────────────────────────────────────────
    bridge = _build_bridge(poly_wires, [sphere_sil])
    if not bridge:
        msg = "sphere+poly: bridge loft failed"
        _fc.Console.PrintWarning(f"[MIXED] {msg}\n")
        write_log("Hull", msg)
        return None

    # ── Assemble ──────────────────────────────────────────────────────────
    all_faces = list(poly_cap_faces) + bridge
    if sphere_cap is not None:
        all_faces.extend(sphere_cap.Faces)

    write_log("Hull", f"sphere+poly: assembling {len(all_faces)} faces")

    SEW_TOL = 1e-3
    try:
        compound = Part.makeCompound(all_faces)
        compound.sewShape(SEW_TOL)
        if compound.ShapeType == 'Solid':
            solid = compound
        else:
            shells = compound.Shells
            shell = shells[0] if shells else Part.makeShell(all_faces)
            solid = Part.makeSolid(shell)
            if solid.Volume < 0:
                solid = solid.reversed()
    except Exception:
        try:
            shell = Part.makeShell(all_faces)
            solid = Part.makeSolid(shell)
            if solid.Volume < 0:
                solid = solid.reversed()
        except Exception as ex:
            write_log("Hull", f"sphere+poly: assembly failed: {ex}")
            return None

    msg = f"sphere+poly: solid OK, volume={solid.Volume:.3f}, closed={solid.isClosed()}"
    _fc.Console.PrintMessage(f"[MIXED] {msg}\n")
    write_log("Hull", msg)
    return solid
