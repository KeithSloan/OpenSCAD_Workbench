# =============================================================================
# process_hull_brep_loft.py
#
# General BRep hull via silhouette extraction + lofting.
# No faceting, no triangulation — produces smooth BRep surfaces.
#
# Algorithm:
#   1. Classify faces of each shape: outer (away from partner), inner (toward),
#      transverse (perpendicular).  Uses face normal · axis direction.
#   2. Extract silhouette edges: edges shared by inner faces and cap
#      (outer+transverse) faces.  Sort into closed wires.
#   3. Loft between silhouette wires of A and B.
#   4. Assemble: cap faces A + bridge + cap faces B → sew → solid.
#
# Falls back to None if any step fails — caller should use faceted fallback.
# =============================================================================

import math
import Part
from FreeCAD import Vector
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

TOL  = 1e-6
NTOL = 1e-3   # normal dot-product band for "transverse"


def _dbg(msg):
    """Log to file always; mirror to Report View while processHull.HULL_DEBUG."""
    write_log("HullLoft", msg)
    try:
        from freecad.OpenSCAD_Ext.parsers.csg_parser.processHull import HULL_DEBUG
        if HULL_DEBUG:
            import FreeCAD
            FreeCAD.Console.PrintMessage(f"[LOFT] {msg}\n")
    except Exception:
        pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _unit(v):
    L = v.Length
    return Vector(v.x/L, v.y/L, v.z/L) if L > TOL else Vector(0, 0, 1)


def _edge_key(e):
    """Geometry-stable edge deduplication key."""
    return tuple(sorted(
        (round(v.X, 4), round(v.Y, 4), round(v.Z, 4))
        for v in e.Vertexes
    ))


def _classify_face(face, e_away):
    """
    Classify a face relative to e_away direction.
    Returns: +1 outer, -1 inner, 0 transverse, 2 mixed-curved.
    """
    u0, u1, v0, v1 = face.ParameterRange

    # Check if flat (plane)
    if isinstance(face.Surface, Part.Plane):
        try:
            d = face.normalAt(0.5*(u0+u1), 0.5*(v0+v1)).dot(e_away)
        except Exception:
            return 0
        if   d >  NTOL: return  1    # outer
        if   d < -NTOL: return -1    # inner
        return 0                      # transverse

    # Curved face: sample normals
    dots = []
    for i in range(4):
        for j in range(4):
            u = u0 + (i+0.5)*(u1-u0)/4
            v = v0 + (j+0.5)*(v1-v0)/4
            try:
                dots.append(face.normalAt(u, v).dot(e_away))
            except Exception:
                pass

    if not dots:
        return 0
    pos = any(d >  NTOL for d in dots)
    neg = any(d < -NTOL for d in dots)
    if pos and not neg: return  1    # all outer
    if neg and not pos: return -1    # all inner
    return 2                          # mixed — silhouette crosses this face


def _extract_silhouette(shape, e_away):
    """
    Extract polyhedral silhouette wire(s) from a shape.
    Returns: (cap_faces, sil_wires)
      cap_faces: list of Part.Face — the outer+transverse hull faces
      sil_wires: list of Part.Wire — closed silhouette loops
    """
    outer, inner, transv, curved = [], [], [], []
    for f in shape.Faces:
        c = _classify_face(f, e_away)
        if   c ==  1: outer.append(f)
        elif c == -1: inner.append(f)
        elif c ==  0: transv.append(f)
        else:         curved.append(f)

    cap_faces = outer + transv
    _dbg(f" faces: outer={len(outer)} inner={len(inner)} "
         f"transv={len(transv)} curved={len(curved)}")

    # Silhouette edges = edges of INNER or CURVED faces shared with CAP faces.
    #
    # Curved faces (a cylinder's lateral surface, a cone's flank, a slab's
    # rounded corners) are classified "mixed" because the surface normal both
    # faces toward and away from the partner across the same face — the true
    # silhouette runs *through* them where n·e_away = 0.  They are excluded from
    # both the cap and inner sets, so harvesting only planar inner-face edges
    # leaves a curved primitive with no silhouette → loft bails to faceting.
    #
    # Treating curved faces like inner faces for edge harvesting recovers the
    # silhouette loop at the boundary they share with a cap face.  For a
    # cylinder this yields the cap-rim circle (the loft then bridges the partner
    # outline to that rim); for rounded corners it stitches the corner arcs into
    # the slab's outline loop.
    cap_edge_keys = set()
    for f in cap_faces:
        for e in f.Edges:
            cap_edge_keys.add(_edge_key(e))

    sil_edges = {}
    for f in inner + curved:
        for e in f.Edges:
            k = _edge_key(e)
            if k in cap_edge_keys and k not in sil_edges:
                sil_edges[k] = e

    sil_edges = list(sil_edges.values())
    if not sil_edges:
        return cap_faces, []

    # Sort into closed wires
    wires = []
    try:
        groups = Part.sortEdges(sil_edges)
        for grp in groups:
            try:
                wires.append(Part.Wire(grp))
            except Exception:
                pass
    except Exception:
        wires = [Part.Wire([e]) for e in sil_edges]

    _dbg(f" silhouette: {len(sil_edges)} edges → {len(wires)} wire(s)")
    return cap_faces, wires


def _resample_wire(wire, n_pts=64):
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


# ── Public API ───────────────────────────────────────────────────────────────

def hull_brep_loft(shapes):
    """
    General BRep hull of two shapes via silhouette extraction + lofting.

    Args:
        shapes: list of exactly 2 Part.Shape objects

    Returns:
        Part.Solid if successful, None if any step fails.
    """
    _dbg("hull_brep_loft called")
    if len(shapes) != 2:
        _dbg(f"need 2 shapes, got {len(shapes)}")
        return None

    A, B = shapes[0], shapes[1]
    _dbg(f"A faces={len(A.Faces)} B faces={len(B.Faces)}")

    # ── Axis ──────────────────────────────────────────────────────────────
    # A Part.Compound has no CenterOfMass attribute even when it has volume, so
    # guard it and fall back to the bounding-box centre.
    def _cog(s):
        try:
            if s.Volume > TOL:
                return s.CenterOfMass
        except Exception:
            pass
        return s.BoundBox.Center

    cA = _cog(A)
    cB = _cog(B)
    d = cB - cA

    bbA, bbB = A.BoundBox, B.BoundBox
    size = max(bbA.DiagonalLength, bbB.DiagonalLength, TOL)

    if d.Length > 0.05 * size:
        # Well-separated centres → COG→COG axis is meaningful.
        e_AB = _unit(d)
        _dbg(f"axis: COG->COG |d|={d.Length:.2f} "
             f"dir=({e_AB.x:.3f},{e_AB.y:.3f},{e_AB.z:.3f})")
    else:
        # Near-concentric centres of mass (common with center=true): the
        # COG->COG vector is dominated by tiny in-plane asymmetry and points the
        # wrong way (e.g. sideways across two tall coaxial prisms).  Fall back to
        # the longest dimension of the COMBINED bounding box — the direction the
        # two profiles are actually stacked / differ along.
        xl = max(bbA.XMax, bbB.XMax) - min(bbA.XMin, bbB.XMin)
        yl = max(bbA.YMax, bbB.YMax) - min(bbA.YMin, bbB.YMin)
        zl = max(bbA.ZMax, bbB.ZMax) - min(bbA.ZMin, bbB.ZMin)
        dims = sorted(((xl, Vector(1, 0, 0)),
                       (yl, Vector(0, 1, 0)),
                       (zl, Vector(0, 0, 1))),
                      key=lambda t: t[0], reverse=True)
        e_AB = dims[0][1]
        if (bbB.Center - bbA.Center).dot(e_AB) < 0:
            e_AB = Vector(-e_AB.x, -e_AB.y, -e_AB.z)
        _dbg(f"axis: near-concentric (|d|={d.Length:.3f} < 5%*{size:.1f}) -> "
             f"longest bbox dim ({e_AB.x:.0f},{e_AB.y:.0f},{e_AB.z:.0f})")

    e_BA = Vector(-e_AB.x, -e_AB.y, -e_AB.z)

    # ── Extract silhouettes ───────────────────────────────────────────────
    _dbg("extracting silhouette A...")
    capA, wiresA = _extract_silhouette(A, e_BA)   # away from B
    _dbg(f" A: {len(capA)} cap faces, {len(wiresA)} wires")
    _dbg("extracting silhouette B...")
    capB, wiresB = _extract_silhouette(B, e_AB)   # away from A
    _dbg(f" B: {len(capB)} cap faces, {len(wiresB)} wires")

    if not wiresA or not wiresB:
        _dbg("Missing silhouette — cannot build bridge")
        return None

    # ── Build bridge loft ─────────────────────────────────────────────────
    _dbg(f"building bridge: {len(wiresA)}×{len(wiresB)} wire pairs")
    bridge_faces = []
    for wA in wiresA:
        for wB in wiresB:
            loft = None
            try:
                loft = Part.makeLoft([wA, wB], False, False, False)
                _dbg(" native loft OK")
            except Exception as ex1:
                _dbg(f" native loft failed: {ex1}")
                try:
                    loft = Part.makeLoft(
                        [_resample_wire(wA), _resample_wire(wB)],
                        False, False, False
                    )
                    _dbg(" bspline loft OK")
                except Exception as ex2:
                    _dbg(f" bspline loft failed: {ex2}")
            if loft is not None:
                bridge_faces.extend(loft.Faces)

    if not bridge_faces:
        _dbg("Bridge loft failed")
        return None

    write_log("HullLoft", f"  bridge: {len(bridge_faces)} face(s)")

    # ── Assemble ──────────────────────────────────────────────────────────
    all_faces = list(capA) + bridge_faces + list(capB)
    write_log("HullLoft", f"  assembling {len(all_faces)} faces")

    SEW_TOL = 1e-3
    solid = None
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
            write_log("HullLoft", f"Assembly failed: {ex}")
            return None

    if solid is None:
        return None

    write_log("HullLoft",
        f"  solid OK: vol={solid.Volume:.1f} closed={solid.isClosed()} "
        f"valid={solid.isValid()}")
    return solid
