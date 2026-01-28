import numpy as np
import FreeCAD
import Part
# from OCC.Core.TopoDS import TopoDS_Shape

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log

def process_polyhedron(node):
    """
    Convert a Polyhedron AST node into a FreeCAD Part.Shape.
    Uses only FreeCAD Part methods (makePolygon, makeFace, makeSolid).
    Retains centroid instrumentation.
    """

    points = node.points
    faces = node.faces

    if not points or not faces:
        return None

    # ---- centroid for instrumentation
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    cz = sum(p[2] for p in points) / len(points)
    poly_center = (cx, cy, cz)

    # ---- build faces using FreeCAD Part API
    part_faces = []
    for face_indices in faces:
        face_pts = [FreeCAD.Vector(*points[idx]) for idx in face_indices]

        # optional: reverse face if orientation check fails
        # if should_reverse(face_pts, poly_center):
        #     face_pts.reverse()

        # make wire & face
        wire = Part.makePolygon(face_pts + [face_pts[0]])  # close polygon
        face = Part.Face(wire)
        part_faces.append(face)

    # ---- assemble into a compound
    shape = Part.Compound(part_faces)

    # ---- try to make a solid if possible
    try:
        shape = Part.makeSolid(shape)
    except Exception:
        # fallback to compound if faces don't form closed shell
        pass

    # ---- instrumentation
    write_log(
        "Polyhedron",
        f"centroid: {poly_center}, points={len(points)}, faces={len(faces)}"
    )

    return shape

'''
def topo_to_part_shape(solid: TopoDS_Shape):
    """
    Convert an OCC TopoDS_Shape to FreeCAD Part.Shape
    """
    fc_shape = Part.Shape()
    fc_shape._TopoDS_Shape = solid  # low-level assignment
    return fc_shape

    # return topo_to_part_shape(solid)

    
import Part
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCC.Core.gp import gp_Pnt
import numpy as np


def process_polyhedron(node):
    import Part
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Solid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    points = node.points
    faces  = node.faces

    if not points or not faces:
        return None

    # centroid
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    cz = sum(p[2] for p in points) / len(points)
    poly_center = (cx, cy, cz)

    sewer = BRepBuilderAPI_Sewing(1e-6)
    for face_indices in faces:
        poly = BRepBuilderAPI_MakePolygon()
        for idx in face_indices:
            x, y, z = points[idx]
            poly.Add(gp_Pnt(x, y, z))
        poly.Close()
        wire = poly.Wire()
        face = BRepBuilderAPI_MakeFace(wire).Face()
        sewer.Add(face)

    sewer.Perform()
    shell = sewer.SewedShape()

    builder = BRep_Builder()
    solid = TopoDS_Solid()
    builder.MakeSolid(solid)
    builder.Add(solid, shell)

    if not BRepCheck_Analyzer(solid).IsValid():
        raise ValueError("Invalid polyhedron solid")

    # ---- instrumentation
    write_log("Polyhedron", f"centroid: {poly_center}, points={len(points)}, faces={len(faces)}")

    # ---- Convert OCC TopoDS_Solid → FreeCAD Part.Shape safely
    fc_shape = Part.Shape(solid)  # works in FreeCAD 0.22/1.0
    return fc_shape


def saved_process_polyhedron(node):
    """
    Convert a Polyhedron AST node into a FreeCAD Part.Shape.
    Uses OCC internally, returns Part.Shape ready for document insertion.
    """
    import Part
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_Sewing
    )
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Solid
    from OCC.Core.BRepCheck import BRepCheck_Analyzer

    points = node.points
    faces  = node.faces

    if not points or not faces:
        return None

    # ---- centroid for debug
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    cz = sum(p[2] for p in points) / len(points)
    poly_center = (cx, cy, cz)

    # ---- build faces into a shell
    sewer = BRepBuilderAPI_Sewing(1e-6)
    for face_indices in faces:
        poly = BRepBuilderAPI_MakePolygon()
        for idx in face_indices:
            x, y, z = points[idx]
            poly.Add(gp_Pnt(x, y, z))
        poly.Close()
        wire = poly.Wire()
        face = BRepBuilderAPI_MakeFace(wire).Face()
        sewer.Add(face)
    sewer.Perform()
    shell = sewer.SewedShape()

    # ---- shell → solid
    builder = BRep_Builder()
    solid = TopoDS_Solid()
    builder.MakeSolid(solid)
    builder.Add(solid, shell)

    # ---- validate
    if not BRepCheck_Analyzer(solid).IsValid():
        raise ValueError("Invalid polyhedron solid")

    # ---- instrumentation
    write_log("Polyhedron", f"centroid: {poly_center}, points={len(points)}, faces={len(faces)}")

    # ---- convert OCC → FreeCAD Part.Shape safely
    # Instead of using _TopoDS_Shape, we can use Part.Shape constructor with the solid
    # convert points and faces to tuples
    pts = tuple(tuple(p) for p in points)
    fcs = tuple(tuple(f) for f in faces)

    fc_shape = Part.Shape()
    fc_shape.makeShapeFromMesh(pts, fcs, 0.01)

    return fc_shape


def should_reverse(face_pts, poly_center):
    """
    Return True if face orientation is inward relative to centroid.
    """
    p0, p1, p2 = map(np.array, face_pts[:3])
    normal = np.cross(p1 - p0, p2 - p0)
    fc = sum(np.array(p) for p in face_pts) / len(face_pts)
    return normal.dot(fc - np.array(poly_center)) < 0


def should_reverse(face_pts, poly_center):
    import numpy as np
    p0, p1, p2 = map(np.array, face_pts[:3])
    normal = np.cross(p1 - p0, p2 - p0)
    fc = sum(np.array(p) for p in face_pts) / len(face_pts)
    return normal.dot(fc - np.array(poly_center)) < 0

"""
if should_reverse(face_pts, poly_center):
    face_indices = list(reversed(face_indices))
"""
'''