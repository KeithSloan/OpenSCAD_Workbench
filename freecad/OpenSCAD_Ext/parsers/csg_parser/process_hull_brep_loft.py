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

# Developer .brep dumps (cap wires, tapers, OCCT loft repro) are OFF by default.
# Set EXPORT_DEBUG = True to write them to DEBUG_DIR while iterating on a hull;
# they are never written during normal imports.
EXPORT_DEBUG = False
DEBUG_DIR = ("/Users/ksloan/Workbenches/OpenSCAD_Workbench/"
             "testcases/Hull_Tests/openflexure_csgs/hull_debug")


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

def _perp_basis(axis):
    """Orthonormal (ux, uy) spanning the plane perpendicular to *axis*."""
    seed = Vector(1, 0, 0) if abs(axis.x) < 0.9 else Vector(0, 1, 0)
    c = axis.cross(seed)
    if c.Length < TOL:
        return None
    uy = _unit(c)
    ux = _unit(uy.cross(axis))
    return ux, uy


def _ang_diff(a, b):
    d = a - b
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return d


def _edge_start_pts(edges):
    pts = []
    for e in edges:
        try:
            pts.append(e.firstVertex(True).Point)
        except Exception:
            pts.append(e.Vertexes[0].Point)
    return pts


def _signed_area_2d(pts, ux, uy):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i].dot(ux), pts[i].dot(uy)
        x1, y1 = pts[(i + 1) % n].dot(ux), pts[(i + 1) % n].dot(uy)
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def _piecewise_bridge(wA, wB, axis):
    """Bridge two closed silhouette wires of EQUAL edge count by building one
    ruled surface per corresponding edge pair (`Part.makeRuledSurface`), with the
    correspondence chosen explicitly — so OCC never has to guess the vertex
    pairing (which is what twists `Part.makeLoft`; OCCT issue #1315).  Arc↔arc
    pairs stay smooth.  Returns a list of faces, or None to fall back to makeLoft.
    """
    try:
        eA = list(wA.OrderedEdges)
        eB = list(wB.OrderedEdges)
    except Exception:
        return None
    if len(eA) != len(eB) or len(eA) < 3:
        return None

    basis = _perp_basis(axis)
    if basis is None:
        return None
    ux, uy = basis

    ptsA = _edge_start_pts(eA)
    ptsB = _edge_start_pts(eB)

    # Make both wires traverse the same way (CCW) in the perpendicular plane.
    if _signed_area_2d(ptsA, ux, uy) < 0:
        eA = [e.reversed() for e in reversed(eA)]
        ptsA = _edge_start_pts(eA)
    if _signed_area_2d(ptsB, ux, uy) < 0:
        eB = [e.reversed() for e in reversed(eB)]
        ptsB = _edge_start_pts(eB)

    cA = (sum(p.dot(ux) for p in ptsA) / len(ptsA),
          sum(p.dot(uy) for p in ptsA) / len(ptsA))
    cB = (sum(p.dot(ux) for p in ptsB) / len(ptsB),
          sum(p.dot(uy) for p in ptsB) / len(ptsB))

    def ang(p, c):
        return math.atan2(p.dot(uy) - c[1], p.dot(ux) - c[0])

    # Rotate eB so it aligns with eA.  Matching only the first edge by angle is
    # ambiguous when a profile has several collinear edges or repeats (e.g. a
    # symmetric two-rounded-end outline [L,L,L,C,C,L,L,L,C,C] has two valid
    # rotations) — it can land one edge off, pairing a Line with a Circle.
    # Instead: restrict to rotations whose EDGE-TYPE sequence matches eA, then
    # pick the one with the smallest total angular mismatch over ALL edges.
    n = len(eB)

    def _etype(e):
        c = e.Curve
        if isinstance(c, Part.Circle):
            return "C"
        if isinstance(c, Part.Line):
            return "L"
        return "?"

    tA = [_etype(e) for e in eA]
    tB = [_etype(e) for e in eB]
    angA = [ang(p, cA) for p in ptsA]
    angB = [ang(p, cB) for p in ptsB]

    cands = [j for j in range(n)
             if all(tA[k] == tB[(k + j) % n] for k in range(n))]
    if not cands:
        cands = list(range(n))   # topology differs — fall back to all rotations

    def _total_mismatch(j):
        return sum(abs(_ang_diff(angA[k], angB[(k + j) % n]))
                   for k in range(n))

    j = min(cands, key=_total_mismatch)
    eB = eB[j:] + eB[:j]

    _dbg(f"  bridge pairing ({len(eA)} edges): " + ", ".join(
        f"{type(a.Curve).__name__}->{type(b.Curve).__name__}"
        for a, b in zip(eA, eB)))

    faces = []
    for idx, (a, b) in enumerate(zip(eA, eB)):
        # Straight↔straight pair → build an EXACT planar quad rather than a ruled
        # BSpline.  The two cap edges of a prism's flat side are coplanar, so the
        # ruled bridge between them lies in that same plane; emitting it as a true
        # Part.Plane face lets removeSplitter() merge it with the body's coplanar
        # flat face (a BSpline would stay an un-mergeable separate face, leaving a
        # spurious seam / shading facet on what should be one flat side).
        if isinstance(a.Curve, Part.Line) and isinstance(b.Curve, Part.Line):
            try:
                pa0 = a.firstVertex(True).Point
                pa1 = a.lastVertex(True).Point
                pb0 = b.firstVertex(True).Point
                pb1 = b.lastVertex(True).Point
                quad = Part.Face(Part.makePolygon([pa0, pa1, pb1, pb0, pa0]))
                if quad is not None and not quad.isNull() and quad.isValid():
                    faces.append(quad)
                    continue
                _dbg(f"  pair[{idx}] line-line quad rejected "
                     f"(null={quad is None or quad.isNull()} "
                     f"valid={None if quad is None else quad.isValid()}) "
                     f"A[{pa0}->{pa1}] B[{pb0}->{pb1}] — ruling instead")
            except Exception as ex:
                write_log("HullLoft", f"  planar quad failed, ruling instead: {ex}")
        try:
            rs = Part.makeRuledSurface(a, b)
        except Exception as ex:
            write_log("HullLoft", f"  pair[{idx}] ruled surface failed: {ex}")
            return None
        if rs is None or rs.isNull():
            _dbg(f"  pair[{idx}] ruled surface null")
            return None
        faces.extend(rs.Faces)
    return faces if faces else None


def _axial_extent(shape, axis):
    vals = [v.Point.dot(axis) for v in shape.Vertexes]
    return (min(vals), max(vals)) if vals else None


def _cap_wire(shape, axis, want_max):
    """Outer boundary wire of *shape*'s end cap perpendicular to *axis*.

    Uses the shape's REAL terminal cap (the top/bottom of an extruded prism),
    not a sliced cross-section — exact, already at its true axial position, and
    free of `slice()`'s flakiness.  *want_max* True picks the cap at the maximum
    axial coordinate (the "top"), else the minimum ("bottom").

    The cap is often NOT a single face: when the 2-D profile was a union of
    overlapping primitives (e.g. square ∪ two circles) the extrude leaves the
    cap tiled into several coplanar sub-faces sharing internal seam edges.
    Taking one sub-face's OuterWire would bridge only that tile and drop the
    rest (the "square bits" lose their taper).  Instead we collect ALL coplanar
    cap faces at the extreme level and rebuild the TRUE outer outline as the
    edges used by exactly one tile (shared internal seams appear twice and
    cancel).  Returns the Part.Wire or None.
    """
    caps = []   # (axial value, face)
    for f in shape.Faces:
        if not isinstance(f.Surface, Part.Plane):
            continue
        try:
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt(0.5 * (u0 + u1), 0.5 * (v0 + v1))
        except Exception:
            continue
        if abs(n.dot(axis)) < 1.0 - 1e-3:      # not perpendicular-to-axis
            continue
        try:
            val = f.CenterOfMass.dot(axis)
        except Exception:
            val = f.BoundBox.Center.dot(axis)
        caps.append((val, f))
    if not caps:
        return None

    target = max(v for v, _ in caps) if want_max else min(v for v, _ in caps)
    level = [f for v, f in caps if abs(v - target) < 1e-6]

    if len(level) == 1:
        try:
            return level[0].OuterWire
        except Exception:
            return None

    # Multiple coplanar tiles → outer boundary = edges belonging to one tile.
    counts, emap = {}, {}
    for f in level:
        for e in f.Edges:
            k = _edge_key(e)
            counts[k] = counts.get(k, 0) + 1
            emap[k] = e
    boundary = [emap[k] for k, c in counts.items() if c == 1]
    _dbg(f"  cap: {len(level)} coplanar tiles -> {len(boundary)} boundary edges "
         f"(of {len(counts)})")
    if not boundary:
        return None
    try:
        groups = Part.sortEdges(boundary)
    except Exception:
        return None
    if not groups:
        return None
    # Outer loop = the wire with the largest bounding box.
    best = None
    for grp in groups:
        try:
            w = Part.Wire(grp)
        except Exception:
            continue
        if best is None or w.BoundBox.DiagonalLength > best.BoundBox.DiagonalLength:
            best = w
    return best


def _frustum_solid(wLo, wHi, axis, tag=""):
    """Closed solid bridging two parallel cap wires: smooth ruled lateral
    (piecewise) + the two planar end caps, sewn.  Logs why it fails / whether the
    sewn shell is actually closed.  Returns Part.Solid or None."""
    lateral = _piecewise_bridge(wLo, wHi, axis)
    if not lateral:
        _dbg(f"  frustum[{tag}]: piecewise bridge failed "
             f"(edgesLo={len(wLo.Edges)} edgesHi={len(wHi.Edges)})")
        return None
    faces = list(lateral)
    try:
        faces.append(Part.Face(wLo))
        faces.append(Part.Face(wHi))
    except Exception as ex:
        _dbg(f"  frustum[{tag}]: cap Face() failed: {ex}")
        return None
    try:
        comp = Part.makeCompound(faces)
        comp.sewShape(1e-3)
        shells = comp.Shells
        shell = shells[0] if shells else Part.makeShell(faces)
        _dbg(f"  frustum[{tag}]: {len(faces)} faces -> {len(shells)} shell(s), "
             f"shell.closed={shell.isClosed()}")
        sol = Part.makeSolid(shell)
        if sol.Volume < 0:
            sol = sol.reversed()
        _dbg(f"  frustum[{tag}]: solid vol={sol.Volume:.1f} "
             f"closed={sol.isClosed()} valid={sol.isValid()}")
        return sol if (sol is not None and not sol.isNull()) else None
    except Exception as ex:
        _dbg(f"  frustum[{tag}]: assembly failed: {ex}")
        return None


def _export_concentric_debug(items):
    """Dump the cap wires + taper solids of the concentric hull to DEBUG_DIR so
    the malformed piece can be inspected in FreeCAD.  *items* is a dict
    name -> shape (skips None).  No-op unless EXPORT_DEBUG is set; when on it
    overwrites, so the folder always reflects the most recent import."""
    if not EXPORT_DEBUG:
        return
    try:
        import os
        d = DEBUG_DIR
        os.makedirs(d, exist_ok=True)
        for name, sh in items.items():
            if sh is None:
                continue
            try:
                sh.exportBrep(os.path.join(d, f"{name}.brep"))
            except Exception as ex:
                _dbg(f"  concentric_debug: export {name} failed: {ex}")
        with open(os.path.join(d, "inspect.py"), "w") as _f:
            _f.write(
'''# Load the concentric-hull debug pieces into the active FreeCAD document.
# Run from the FreeCAD Python console:  exec(open("inspect.py").read())
import Part, os, glob
here = os.path.dirname(__file__) if "__file__" in dir() else "."
for p in sorted(glob.glob(os.path.join(here, "*.brep"))):
    s = Part.read(p)
    nm = os.path.splitext(os.path.basename(p))[0]
    info = "type=%s" % s.ShapeType
    try:
        info += " closed=%s valid=%s vol=%.1f" % (s.isClosed(), s.isValid(), s.Volume)
    except Exception:
        pass
    print("%-14s %s" % (nm, info))
    Part.show(s, nm)
''')
        _dbg(f"  concentric_debug: exported {len([v for v in items.values() if v])} "
             f"pieces -> {d}")
    except Exception as ex:
        _dbg(f"  concentric_debug export failed: {ex}")


def hull_concentric_sections(A, B, axis):
    """Smooth hull of two ~coaxial near-concentric prisms.

    Model (cf. two concentric cylinders, one short+wide, one long+thin): the
    hull is the WIDE shape plus, at each end where the NARROW shape protrudes,
    a taper lofting the wide shape's end-cap wire to the narrow shape's end-cap
    wire.  We FUSE A, B and those taper solids so OCC's boolean heals every
    junction.  Uses each shape's REAL terminal cap faces (via `_cap_wire`), so
    the taper wires sit at their exact axial positions — no `slice()`.

    Returns Part.Solid or None to fall back.
    """
    exA = _axial_extent(A, axis)
    exB = _axial_extent(B, axis)
    if not exA or not exB:
        return None

    capA_top = _cap_wire(A, axis, True)
    capA_bot = _cap_wire(A, axis, False)
    capB_top = _cap_wire(B, axis, True)
    capB_bot = _cap_wire(B, axis, False)
    if None in (capA_top, capA_bot, capB_top, capB_bot):
        _dbg("  concentric: missing cap wire(s) — "
             f"A(top={capA_top is not None},bot={capA_bot is not None}) "
             f"B(top={capB_top is not None},bot={capB_bot is not None})")
        return None

    # Wider shape = larger cap-wire footprint.
    if capA_top.BoundBox.DiagonalLength >= capB_top.BoundBox.DiagonalLength:
        W, exW, capW_top, capW_bot = A, exA, capA_top, capA_bot
        N, exN, capN_top, capN_bot = B, exB, capB_top, capB_bot
    else:
        W, exW, capW_top, capW_bot = B, exB, capB_top, capB_bot
        N, exN, capN_top, capN_bot = A, exA, capA_top, capA_bot
    _dbg(f"  concentric: wide axial=[{exW[0]:.2f},{exW[1]:.2f}] "
         f"narrow axial=[{exN[0]:.2f},{exN[1]:.2f}]")

    def _edesc(w):
        try:
            return ",".join(type(e.Curve).__name__[:4] for e in w.OrderedEdges)
        except Exception:
            return "?"
    _dbg(f"  concentric: capW_top edges=[{_edesc(capW_top)}] "
         f"capN_top edges=[{_edesc(capN_top)}]")

    # Build the end tapers (cap wires already at their true axial positions).
    taper_top = taper_bot = None
    if exN[1] - exW[1] > 1e-6:          # narrow protrudes above wide
        taper_top = _frustum_solid(capW_top, capN_top, axis, tag="top")
    if exW[0] - exN[0] > 1e-6:          # narrow protrudes below wide
        taper_bot = _frustum_solid(capN_bot, capW_bot, axis, tag="bot")

    # Inspection dump (one-time) — cap wires + tapers + inputs.
    _export_concentric_debug({
        "capW_top": capW_top, "capW_bot": capW_bot,
        "capN_top": capN_top, "capN_bot": capN_bot,
        "taper_top": taper_top, "taper_bot": taper_bot,
        "shapeW": W, "shapeN": N,
    })

    if (exN[1] - exW[1] > 1e-6 and taper_top is None) or \
       (exW[0] - exN[0] > 1e-6 and taper_bot is None):
        _dbg("  concentric: a required taper failed — fall back")
        return None

    try:
        result = A.fuse(B)
    except Exception as ex:
        _dbg(f"  concentric: A.fuse(B) failed: {ex}")
        return None
    for t in (taper_top, taper_bot):
        if t is None:
            continue
        try:
            result = result.fuse(t)
        except Exception as ex:
            _dbg(f"  concentric: taper fuse failed: {ex}")
            return None

    try:
        result = result.removeSplitter()
    except Exception:
        pass
    return result if (result is not None and not result.isNull()) else None


# ── Smooth section-loft of the convex hull (oblique bridges) ──────────────────
# The cap-rim silhouette loft is exact only when the bridge runs along each
# shape's own axis; for an OBLIQUE bridge (e.g. the compact_nut arm strut: a
# vertical cylinder lofted to an off-axis dome 62° away) it attaches at the cap
# rim and underestimates the volume (a thin cap-to-cap frustum).
#
# This builds the smooth hull a different way: take the exact convex hull of all
# the shapes' boundary points, slice it with planes perpendicular to its
# elongation (PCA) axis, and loft a smooth periodic-BSpline outline through each
# slice.  The slice outlines capture the full tangent envelope (the bulge the
# cap-to-cap frustum misses), and because each slice is a single closed convex
# loop, changing cross-section topology along the axis is handled for free.
# Validated against the faceted convex-hull volume by the caller.

def _ray_hit_convex(poly2d, cx, cy, dx, dy):
    """First boundary hit of ray (cx,cy)+t*(dx,dy), t>0, on convex polygon."""
    m = len(poly2d)
    best_t = None
    bx = by = 0.0
    for i in range(m):
        ax, ay = poly2d[i][0] - cx, poly2d[i][1] - cy
        nx, ny = poly2d[(i + 1) % m][0] - cx, poly2d[(i + 1) % m][1] - cy
        ex, ey = nx - ax, ny - ay
        det = dx * ey - dy * ex
        if abs(det) < 1e-12:
            continue
        u = (ax * dy - ay * dx) / det      # param along segment, want [0,1]
        t = (ax * ey - ay * ex) / det      # param along ray, want > 0
        if -1e-9 <= u <= 1 + 1e-9 and t > 1e-9:
            if best_t is None or t < best_t:
                best_t = t
                bx, by = cx + t * dx, cy + t * dy
    if best_t is None:
        return None
    return bx, by


def _smooth_section_wire(poly2d, ux, uy, nrm, s_off, n_out=64):
    """Periodic-BSpline wire through a convex slice, resampled at uniform angles
    from its centroid (consistent correspondence between slices → no loft twist).
    poly2d coords are global projections (X=P·ux, Y=P·uy); 3D = X·ux+Y·uy+s·n."""
    import numpy as np
    P = np.asarray(poly2d, dtype=float)
    if len(P) < 3:
        return None
    cx, cy = float(P[:, 0].mean()), float(P[:, 1].mean())
    pts3 = []
    for k in range(n_out):
        th = 2.0 * math.pi * k / n_out
        hit = _ray_hit_convex(P, cx, cy, math.cos(th), math.sin(th))
        if hit is None:
            continue
        X, Y = hit
        p = (Vector(ux.x, ux.y, ux.z) * X
             + Vector(uy.x, uy.y, uy.z) * Y
             + Vector(nrm.x, nrm.y, nrm.z) * s_off)
        pts3.append(p)
    if len(pts3) < 3:
        return None
    try:
        c = Part.BSplineCurve()
        c.interpolate(pts3, PeriodicFlag=True)
        return Part.Wire([c.toShape()])
    except Exception:
        try:
            return Part.makePolygon(pts3 + [pts3[0]])
        except Exception:
            return None


def hull_loft_sections(shapes, n_stations=20, n_out=48):
    """Smooth hull of convex shapes via cross-sections of their convex hull,
    perpendicular to the hull's PCA elongation axis.  Returns Part.Solid or None.
    Robust for oblique bridges where the cap-rim silhouette loft underestimates.
    """
    try:
        import numpy as np
        from scipy.spatial import ConvexHull as _CH
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep import (
            _extract_points
        )
    except Exception as ex:
        _dbg(f"  section-loft deps unavailable: {ex}")
        return None

    # 1. dense boundary point cloud → exact 3D convex hull
    try:
        pts = np.vstack([_extract_points(s) for s in shapes])
    except Exception as ex:
        _dbg(f"  section-loft point extract failed: {ex}")
        return None
    pr = np.round(pts / 1e-6) * 1e-6
    _, idx = np.unique(pr, axis=0, return_index=True)
    pts = pts[np.sort(idx)]
    if pts.shape[0] < 4:
        return None
    try:
        hull = _CH(pts)
    except Exception as ex:
        _dbg(f"  section-loft ConvexHull failed: {ex}")
        return None

    hv = pts[hull.vertices]               # hull vertices only (for PCA fallback)

    # 2. section axis = hull elongation (first principal component).  Slicing ⊥
    # the elongation keeps the slice centres monotonic along the strut, so the
    # loft correspondence stays clean.  (Slicing ⊥ the cylinder's own axis was
    # tried and regressed: on an oblique strut the slice centres jump sideways
    # across the bridge and the loft splits into disconnected solids.)
    mean = hv.mean(axis=0)
    cov = np.cov((hv - mean).T)
    try:
        evals, evecs = np.linalg.eigh(cov)
        nrm = evecs[:, int(np.argmax(evals))]
    except Exception as ex:
        _dbg(f"  section-loft PCA failed: {ex}")
        return None
    nrm = nrm / (np.linalg.norm(nrm) or 1.0)
    nvec = Vector(float(nrm[0]), float(nrm[1]), float(nrm[2]))
    _dbg(f"  section axis: PCA ({nrm[0]:.3f},{nrm[1]:.3f},{nrm[2]:.3f})")

    basis = _perp_basis(nvec)
    if basis is None:
        return None
    ux, uy = basis
    uxn = np.array([ux.x, ux.y, ux.z])
    uyn = np.array([uy.x, uy.y, uy.z])

    # 3. unique hull edges (from triangle simplices), and axial projections
    edges = set()
    for tri in hull.simplices:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        edges.add((min(a, b), max(a, b)))
        edges.add((min(b, c), max(b, c)))
        edges.add((min(a, c), max(a, c)))
    edges = list(edges)
    proj = pts.dot(nrm)
    smin, smax = float(proj.min()), float(proj.max())
    span = smax - smin
    if span < 1e-6:
        return None

    # 4. slice the hull at interior stations; build a smooth wire per slice
    wires = []
    for k in range(n_stations):
        s = smin + (k + 0.5) / n_stations * span
        cut = []
        for (i, j) in edges:
            di, dj = proj[i] - s, proj[j] - s
            if (di <= 0.0 < dj) or (dj <= 0.0 < di):
                t = di / (di - dj)
                p = pts[i] + t * (pts[j] - pts[i])
                cut.append(p)
        if len(cut) < 3:
            continue
        cut = np.array(cut)
        poly2d = np.column_stack([cut.dot(uxn), cut.dot(uyn)])
        try:
            ch2 = _CH(poly2d)
        except Exception:
            continue
        ordered = [(float(poly2d[o, 0]), float(poly2d[o, 1])) for o in ch2.vertices]
        w = _smooth_section_wire(ordered, ux, uy, nvec, s, n_out)
        if w is not None:
            wires.append(w)

    if len(wires) < 2:
        _dbg(f"  section-loft: only {len(wires)} usable slices")
        return None

    # 5. loft smooth (ruled=False), solid with planar end caps
    try:
        solid = Part.makeLoft(wires, True, False)
        try:
            solid = solid.removeSplitter()
        except Exception:
            pass
    except Exception as ex:
        _dbg(f"  section-loft makeLoft failed: {ex}")
        return None
    if solid is None or solid.isNull() or not solid.isValid():
        _dbg("  section-loft produced invalid solid")
        return None

    # 6. restore true terminal geometry.  makeLoft caps the first/last slices
    # with a flat plane perpendicular to the PCA axis, a short distance inside
    # the real extremes — giving a BLUNT end that doesn't match the cylinder it
    # joins.  Each input shape is part of the hull (hull ⊇ shape), so fusing the
    # originals back in fills the clipped ends with their real faces (the
    # cylinder's end cap, the sphere's rounded surface) and the blunt flat cap
    # becomes interior, removed by removeSplitter.
    #
    # Fuse INCREMENTALLY, largest shape first, keeping each fuse only if it stays
    # a single valid solid.  A combined all-at-once fuse is fragile — a tiny
    # shape (e.g. the h=0.05 disk) can spawn a sliver and invalidate the whole
    # result, which previously discarded the good cylinder fuse along with it and
    # left the blunt cap.  Incremental keep-if-valid restores the cylinder's real
    # end cap even when the disk fuse must be skipped.
    def _vol(s):
        try:
            return s.Volume
        except Exception:
            return 0.0

    fused_n = 0
    for s in sorted(shapes, key=_vol, reverse=True):
        try:
            cand = solid.fuse(s)
            try:
                cand = cand.removeSplitter()
            except Exception:
                pass
            if (not cand.isNull()) and cand.isValid() and len(cand.Solids) == 1:
                solid = cand
                fused_n += 1
        except Exception:
            pass
    if fused_n < len(shapes):
        _dbg(f"  section-loft end-fuse: kept {fused_n}/{len(shapes)} originals")

    _dbg(f"  section-loft: {len(wires)} slices vol={solid.Volume:.1f} "
         f"valid={solid.isValid()} closed={solid.isClosed()}")
    return solid


# ── Cluster + fuse: N-shape hull with co-located ends ─────────────────────────
# The convex hull of a set of shapes is invariant under unioning any subset:
#       hull(A, B, C) == hull(A ∪ B, C).
# So when a hull's N input shapes form exactly TWO connected spatial groups —
# e.g. the compact_nut strut: a half-sphere + a near-coincident thin disk forming
# one rounded END, plus the strut cylinder as the other END — we can fuse each
# group into a single solid and feed the two fused ends to the 2-shape silhouette
# loft.  This is LOSSLESS (nothing is dropped; the disk is fused in, not discarded)
# and reaches the smooth B-spline path.  If the shapes form 1 group (all touching)
# or 3+ groups (a genuine multi-lobe hull), this is not a 2-ended strut: return
# None and let the caller fall back to faceted / the future N-shape work.

def _shapes_touch(a, b, tol=1e-3):
    """True if a and b overlap or lie within *tol* (i.e. one connected blob)."""
    try:
        return a.distToShape(b)[0] <= tol
    except Exception:
        # distToShape can fail on odd compounds — fall back to bbox proximity.
        try:
            ba = a.BoundBox
            ba.enlarge(tol)
            return ba.intersect(b.BoundBox)
        except Exception:
            return False


def _cluster_connected(shapes, tol=1e-3):
    """Single-linkage clustering by actual contact/overlap (union-find)."""
    n = len(shapes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if _shapes_touch(shapes[i], shapes[j], tol):
                union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(shapes[i])
    return list(groups.values())


def _fuse_cluster(cluster):
    """Fuse a connected cluster of shapes into one solid (None on failure)."""
    if len(cluster) == 1:
        return cluster[0]
    try:
        fused = cluster[0]
        for s in cluster[1:]:
            fused = fused.fuse(s)
        try:
            fused = fused.removeSplitter()
        except Exception:
            pass
        if fused.isNull() or not fused.isValid():
            return None
        return fused
    except Exception as ex:
        _dbg(f"  cluster fuse failed: {ex}")
        return None


def hull_brep_loft_multi(shapes):
    """Smooth hull for N>=2 shapes when they form exactly two connected ends.

    len == 2 -> straight to hull_brep_loft (unchanged behaviour).
    len  > 2 -> cluster by contact; if exactly 2 clusters, fuse each end and
                loft.  Otherwise return None (genuine multi-lobe hull or all-
                connected blob -> caller falls back).
    """
    if len(shapes) < 2:
        return None
    if len(shapes) == 2:
        return hull_brep_loft(shapes)

    clusters = _cluster_connected(shapes)
    _dbg(f"cluster+fuse: {len(shapes)} shapes -> {len(clusters)} connected end(s) "
         f"(sizes {[len(c) for c in clusters]})")
    if len(clusters) != 2:
        _dbg("  not a 2-ended hull -> defer to fallback")
        return None

    ends = []
    for cl in clusters:
        fused = _fuse_cluster(cl)
        if fused is None:
            _dbg("  end fuse failed -> defer to fallback")
            return None
        ends.append(fused)

    _dbg(f"  fused ends: faces={[len(e.Faces) for e in ends]} -> 2-shape loft")
    return hull_brep_loft(ends)


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

    # ── Concentric coaxial prisms: stacked-section hull ───────────────────
    # The silhouette-loft model has no single A->B band for concentric shapes
    # (the wider profile must persist through the overlap).  Build the hull from
    # stacked cross-sections instead.
    if d.Length <= 0.05 * size:
        sol = hull_concentric_sections(A, B, e_AB)
        if sol is not None and not sol.isNull():
            _dbg(f"  concentric multi-section hull: vol={sol.Volume:.1f} "
                 f"valid={sol.isValid()} closed={sol.isClosed()}")
            return sol
        _dbg("  concentric multi-section unavailable — silhouette loft")

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

    # --- dev: export the two makeLoft input wires for an OCCT bug report ---
    if EXPORT_DEBUG and not getattr(hull_brep_loft, "_repro_done", False):
        hull_brep_loft._repro_done = True
        try:
            import os
            d = os.path.join(DEBUG_DIR, "occt_loft_repro")
            os.makedirs(d, exist_ok=True)
            wiresA[0].exportBrep(os.path.join(d, "wireA.brep"))
            wiresB[0].exportBrep(os.path.join(d, "wireB.brep"))
            A.exportBrep(os.path.join(d, "shapeA.brep"))
            B.exportBrep(os.path.join(d, "shapeB.brep"))
            with open(os.path.join(d, "reproduce_loft.py"), "w") as _f:
                _f.write(
'''# OCCT makeLoft (BRepOffsetAPI_ThruSections) reproducer.
# Two near-identical closed rounded-rectangle wires in parallel planes: the
# ruled loft twists (wrong vertex correspondence) and self-intersects, yet
# isValid() == True and the sewn-solid volume collapses to ~9% of expected.
# Run in the FreeCAD Python console from this directory.
import Part, os
here = os.path.dirname(__file__) if "__file__" in dir() else "."
wA = Part.read(os.path.join(here, "wireA.brep"))
wB = Part.read(os.path.join(here, "wireB.brep"))
print("wireA closed=%s edges=%d | wireB closed=%s edges=%d"
      % (wA.isClosed(), len(wA.Edges), wB.isClosed(), len(wB.Edges)))
loft = Part.makeLoft([wA, wB], False, False, False)   # solid, ruled, closed
print("loft type=%s faces=%d valid=%s"
      % (loft.ShapeType, len(loft.Faces), loft.isValid()))
comp = Part.makeCompound(loft.Faces); comp.sewShape(1e-3)
if comp.Shells:
    sol = Part.makeSolid(comp.Shells[0])
    print("solid volume=%.1f valid=%s closed=%s"
          % (sol.Volume, sol.isValid(), sol.isClosed()))
Part.show(wA, "wireA"); Part.show(wB, "wireB"); Part.show(loft, "loft")
''')
            _dbg(f"exported OCCT loft repro -> {d}")
        except Exception as ex:
            _dbg(f"loft repro export failed: {ex}")

    # ── Build bridge ──────────────────────────────────────────────────────
    bridge_faces = []

    # Preferred: explicit per-edge-pair ruled surfaces — we choose the vertex
    # correspondence ourselves, so OCC never twists the bridge (OCCT #1315), and
    # arc↔arc pairs stay smooth.
    if len(wiresA) == 1 and len(wiresB) == 1:
        pb = _piecewise_bridge(wiresA[0], wiresB[0], e_AB)
        if pb:
            _dbg(f"  piecewise ruled bridge: {len(pb)} face(s)")
            bridge_faces = pb

    # Fallback: whole-wire makeLoft (may twist — caught by the volume check).
    if not bridge_faces:
        _dbg(f"building bridge (makeLoft): {len(wiresA)}×{len(wiresB)} wire pairs")
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
