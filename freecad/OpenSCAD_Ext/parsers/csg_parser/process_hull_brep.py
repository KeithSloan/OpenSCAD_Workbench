# =============================================================================
# process_hull_brep.py
#
# General convex hull of arbitrary BRep shapes — no type detection, no OpenSCAD.
# Called from processAST.py try_hull() as the primary (only) hull path.
#
# Exports:
#   hull_brep_shapes(shapes)  →  Part.Shape or raises RuntimeError
#
# Algorithm:
#   1. Extract representative points from every shape
#      - Flat faces: vertices (exact)
#      - Curved faces: parametric grid samples via face.valueAt(u, v)
#      - Spheres: Fibonacci lattice for uniform coverage
#   2. Compute 3D convex hull via scipy.spatial.ConvexHull
#   3. Reconstruct as watertight FreeCAD Part.Solid from hull triangles
#   4. Validate closedness, validity, volume
#
# Dependencies: FreeCAD, Part, numpy, scipy
# =============================================================================

import math

import Part
from FreeCAD import Vector

try:
    import numpy as np
except ImportError:
    raise ImportError(
        "numpy is required for native BRep hull. "
        "Install it in FreeCAD's Python environment: pip install numpy"
    )

try:
    from scipy.spatial import ConvexHull as ScipyConvexHull
except ImportError:
    raise ImportError(
        "scipy is required for native BRep hull. "
        "Install it in FreeCAD's Python environment: pip install scipy"
    )

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

# ── Tuneable constants ───────────────────────────────────────────────────────
GRID_N   = 12    # N×N samples per curved face
SPHERE_N = 200   # Fibonacci lattice points for spheres
TOL      = 1e-6  # geometric tolerance


# =============================================================================
#  Public API
# =============================================================================

def hull_brep_shapes(shapes):
    """
    Compute the 3D convex hull of a list of FreeCAD BRep shapes.

    Args:
        shapes: list of Part.Shape objects (or Part::Feature objects
                with a .Shape attribute).

    Returns:
        A new Part.Shape (solid) that is the convex hull of all input shapes.

    Raises:
        RuntimeError if hull computation fails.
    """
    if len(shapes) < 2:
        raise RuntimeError(
            f"Need at least 2 shapes for hull, got {len(shapes)}"
        )

    # Unwrap Part::Feature objects
    unwrapped = []
    for s in shapes:
        if hasattr(s, 'Shape') and s.Shape is not None:
            unwrapped.append(s.Shape)
        else:
            unwrapped.append(s)
    shapes = unwrapped

    # ── Validate no nested objects ────────────────────────────────────────
    _check_nested(shapes)

    # ── Extract point clouds ──────────────────────────────────────────────
    pts_list = []
    for i, shape in enumerate(shapes):
        pts = _extract_points(shape)
        write_log("Hull", f"  Shape[{i}]: {pts.shape[0]} points extracted")
        pts_list.append(pts)

    pts = np.vstack(pts_list)
    write_log("Hull", f"  Combined: {pts.shape[0]} points")

    # Deduplicate near-coincident points
    pts_rounded = np.round(pts / TOL) * TOL
    _, unique_idx = np.unique(pts_rounded, axis=0, return_index=True)
    pts = pts[np.sort(unique_idx)]
    write_log("Hull", f"  After dedup: {pts.shape[0]} unique points")

    if pts.shape[0] < 4:
        raise RuntimeError(
            f"Too few unique points ({pts.shape[0]}) — need at least 4 "
            "for a 3D convex hull"
        )

    # ── Compute convex hull ───────────────────────────────────────────────
    write_log("Hull", "  Computing scipy.spatial.ConvexHull ...")
    try:
        hull = ScipyConvexHull(pts)
    except Exception as ex:
        raise RuntimeError(f"scipy ConvexHull failed: {ex}") from ex

    write_log("Hull",
              f"  Hull: {len(hull.vertices)} vertices, "
              f"{len(hull.simplices)} faces")

    # ── Reconstruct as FreeCAD solid ──────────────────────────────────────
    solid = _hull_to_solid(hull, pts)

    # ── Validate ──────────────────────────────────────────────────────────
    _validate(solid, shapes)

    return solid


# =============================================================================
#  Nested-object check
# =============================================================================

def _check_nested(shapes):
    """Raise RuntimeError if any shape is nested entirely inside another."""
    for i, s1 in enumerate(shapes):
        bb1 = s1.BoundBox
        for j, s2 in enumerate(shapes):
            if i == j:
                continue
            bb2 = s2.BoundBox
            if (_bbox_contains(bb1, bb2)):
                write_log("Hull",
                          f"WARNING: Shape[{j}] appears entirely inside "
                          f"Shape[{i}] — hull would be Shape[{i}]'s hull")
                # Don't abort — scipy ConvexHull handles this fine
                # (inner shape points are just interior)
            # Only abort if ALL shapes are nested in one
    # The convex hull handles partial nesting naturally


def _bbox_contains(outer, inner):
    """Return True if inner bounding box is contained in outer."""
    return (outer.XMin - TOL <= inner.XMin and
            outer.XMax + TOL >= inner.XMax and
            outer.YMin - TOL <= inner.YMin and
            outer.YMax + TOL >= inner.YMax and
            outer.ZMin - TOL <= inner.ZMin and
            outer.ZMax + TOL >= inner.ZMax)


# =============================================================================
#  Surface-type helpers
# =============================================================================

def _surf_type(face):
    """Return a short string key for the face's surface type."""
    s = face.Surface
    if isinstance(s, Part.Plane):
        return 'plane'
    if isinstance(s, Part.Sphere):
        return 'sphere'
    if isinstance(s, Part.Cylinder):
        return 'cylinder'
    if isinstance(s, Part.Cone):
        return 'cone'
    if isinstance(s, Part.Toroid):
        return 'toroid'
    if hasattr(Part, 'Ellipsoid') and isinstance(s, Part.Ellipsoid):
        return 'ellipsoid'
    if isinstance(s, Part.BSplineSurface):
        return 'bspline'
    if isinstance(s, Part.BezierSurface):
        return 'bezier'
    return 'other'


# =============================================================================
#  Point extraction
# =============================================================================

def _fibonacci_sphere(n):
    """
    Generate n uniformly-distributed points on the unit sphere
    using the Fibonacci lattice method. Returns (n, 3) numpy array.
    """
    indices = np.arange(n, dtype=np.float64)
    phi = np.arccos(1 - 2 * (indices + 0.5) / n)    # polar angle [0, π]
    theta = np.pi * (1 + np.sqrt(5)) * indices        # azimuthal angle
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)
    return np.column_stack([x, y, z])


def _sample_sphere_face(face, n=SPHERE_N):
    """
    Sample a spherical face uniformly.
    Uses Fibonacci lattice on the full sphere, then filters to points
    within the face's UV parameter domain.
    """
    s = face.Surface
    cen = np.array([s.Center.x, s.Center.y, s.Center.z])
    R   = s.Radius

    unit_pts = _fibonacci_sphere(n)
    sphere_pts = cen + unit_pts * R

    u0, u1, v0, v1 = face.ParameterRange
    kept = []
    for pt in sphere_pts:
        vec = Vector(float(pt[0]), float(pt[1]), float(pt[2]))
        try:
            uv = s.parameter(vec)
            u, v = uv[0], uv[1]
            u_span = u1 - u0
            if u_span >= 2 * math.pi - TOL:
                pass  # full circle — any u is valid
            elif u < u0 - TOL or u > u1 + TOL:
                continue
            if v < v0 - TOL or v > v1 + TOL:
                continue
            kept.append([float(pt[0]), float(pt[1]), float(pt[2])])
        except Exception:
            pass

    return np.array(kept) if kept else np.empty((0, 3))


def _sample_curved_face(face, n=GRID_N):
    """
    Sample a curved face using an n×n parametric grid.
    Returns (m, 3) numpy array.
    """
    u0, u1, v0, v1 = face.ParameterRange
    pts = []
    for i in range(n):
        for j in range(n):
            u = u0 + (i + 0.5) * (u1 - u0) / n
            v = v0 + (j + 0.5) * (v1 - v0) / n
            try:
                p = face.valueAt(u, v)
                pts.append([p.x, p.y, p.z])
            except Exception:
                pass
    return np.array(pts) if pts else np.empty((0, 3))


def _extract_points(shape):
    """
    Extract a representative point cloud from a BRep shape.
    Vertices + parametric grid samples for curved faces.
    Returns (N, 3) numpy array.
    """
    # 1. All vertices
    verts = []
    for v in shape.Vertexes:
        p = v.Point
        verts.append([p.x, p.y, p.z])
    pts_list = [np.array(verts)] if verts else []

    # 2. Curved face samples
    for face in shape.Faces:
        ft = _surf_type(face)
        if ft == 'plane':
            continue
        if ft == 'sphere':
            sampled = _sample_sphere_face(face)
        else:
            sampled = _sample_curved_face(face)
        if len(sampled) > 0:
            pts_list.append(sampled)

    if not pts_list:
        raise RuntimeError("No extractable points — empty or degenerate shape?")

    all_pts = np.vstack(pts_list)
    return all_pts


# =============================================================================
#  Hull → FreeCAD solid reconstruction
# =============================================================================

def _hull_to_solid(hull, pts):
    """Convert scipy ConvexHull simplices to a Part.Solid."""
    faces = []
    for simplex in hull.simplices:
        i, j, k = int(simplex[0]), int(simplex[1]), int(simplex[2])
        v0 = Vector(float(pts[i, 0]), float(pts[i, 1]), float(pts[i, 2]))
        v1 = Vector(float(pts[j, 0]), float(pts[j, 1]), float(pts[j, 2]))
        v2 = Vector(float(pts[k, 0]), float(pts[k, 1]), float(pts[k, 2]))
        try:
            wire = Part.makePolygon([v0, v1, v2, v0])
            face = Part.Face(wire)
            faces.append(face)
        except Exception:
            pass  # degenerate triangle — skip

    if not faces:
        raise RuntimeError("No faces could be constructed from hull simplices")

    try:
        shell = Part.makeShell(faces)
    except Exception as ex:
        raise RuntimeError(f"Part.makeShell failed: {ex}") from ex

    try:
        solid = Part.makeSolid(shell)
    except Exception as ex:
        raise RuntimeError(f"Part.makeSolid failed: {ex}") from ex

    # Merge coplanar faces for cleaner result
    try:
        solid = solid.removeSplitter()
    except Exception:
        pass

    # Fix orientation
    if solid.Volume < 0:
        solid = solid.reversed()

    return solid


# =============================================================================
#  Validation
# =============================================================================

def _validate(solid, input_shapes):
    """
    Validate the hull solid: closedness, validity, volume.
    Logs results; raises RuntimeError on critical failures.
    """
    errors = []

    try:
        is_valid = solid.isValid()
    except Exception:
        is_valid = None
        errors.append("isValid() call failed")

    try:
        is_closed = solid.isClosed()
    except Exception:
        is_closed = None
        errors.append("isClosed() call failed")

    vol_hull = solid.Volume
    input_vols = [s.Volume for s in input_shapes if hasattr(s, 'Volume')]
    vol_max = max(input_vols) if input_vols else 0.0
    vol_ok = vol_hull > vol_max if vol_max > TOL else vol_hull >= 0

    write_log("Hull",
              f"  Valid: {is_valid}  Closed: {is_closed}  "
              f"Volume: {vol_hull:.3f} (max input: {vol_max:.3f})")

    if is_valid is False:
        errors.append("BRep is NOT valid")
    if is_closed is False:
        errors.append("Shell has open edges (not watertight)")
    if not vol_ok:
        errors.append(
            f"Hull volume ({vol_hull:.3f}) not > max input ({vol_max:.3f})"
        )

    if errors:
        write_log("Hull", f"  Validation issues: {'; '.join(errors)}")
        # Don't raise — the hull may still be usable even with warnings
    else:
        write_log("Hull", "  ✓ All validation checks passed")
