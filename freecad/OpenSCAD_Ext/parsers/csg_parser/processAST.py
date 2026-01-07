import FreeCAD
import Part
import Mesh
import tempfile
import os
from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log
from freecad.OpenSCAD_Ext.core.OpenSCADUtils import process_ObjectsViaOpenSCADShape
from .ast_nodes import (
    Node, Cube, Sphere, Cylinder,
    Union, Difference, Intersection,
    Hull, Minkowski,
    Group, MultMatrix, Translate, Rotate, Scale
)
from .hull_minkowski import try_hull, try_minkowski

# --- Fallback to OpenSCAD STL for unconvertible nodes ---
def fallback_to_OpenSCAD(doc, node, node_type="Node"):
    """
    Generate OpenSCAD STL for a node and import as mesh / part
    """
    write_log("Info", f"Fallback to OpenSCAD STL for {node_type}")

    # 1. Generate temporary SCAD file
    temp_dir = tempfile.gettempdir()
    scad_path = os.path.join(temp_dir, f"fallback_{node_type}.scad")
    stl_path = os.path.join(temp_dir, f"fallback_{node_type}.stl")

    # NOTE: You need a function that converts AST node to SCAD code
    # Here we assume 'ast_to_scad' exists
    from .ast_to_scad import ast_to_scad
    scad_code = ast_to_scad(node)
    with open(scad_path, "w", encoding="utf-8") as f:
        f.write(scad_code)

    # 2. Run OpenSCAD to produce STL
    cmd = f"openscad -o \"{stl_path}\" \"{scad_path}\""
    ret = os.system(cmd)
    if ret != 0 or not os.path.exists(stl_path):
        write_log("Error", f"OpenSCAD STL generation failed for {node_type}")
        return None

    # 3. Load STL into FreeCAD mesh
    mesh_obj = FreeCAD.ActiveDocument.addObject("Mesh::Feature", f"{node_type}_Mesh")
    mesh_obj.Mesh = Mesh.Mesh(stl_path)
    write_log("Info", f"Imported STL for {node_type} as Mesh")

    # 4. Convert to Part shape
    part_shape = Part.Shape()
    try:
        part_shape.makeShapeFromMesh(mesh_obj.Mesh, 0.1)  # tolerance in mm
        write_log("Info", f"Converted mesh to Part shape for {node_type}")
    except Exception as e:
        write_log("Error", f"Failed to convert mesh to Part shape: {e}")
        return mesh_obj  # fallback: return mesh object

    return part_shape


# --- Process Hull / Minkowski ---
def process_hull_node(doc, node):
    shape = try_hull(node.children)
    if shape:
        write_log("Info", "Hull converted to BRep successfully")
        return shape
    return fallback_to_OpenSCAD(doc, node, node_type="Hull")


def process_minkowski_node(doc, node):
    shape = try_minkowski(node.children)
    if shape:
        write_log("Info", "Minkowski converted to BRep successfully")
        return shape
    return fallback_to_OpenSCAD(doc, node, node_type="Minkowski")


# --- Recursive AST processor ---
def process_AST_node(doc, node):
    from FreeCAD import Vector
    shape = None

    # --- Primitives ---
    if isinstance(node, Cube):
        size = node.params.get("size", [1,1,1])
        center = node.params.get("center", False)
        shape = Part.makeBox(*size)
        if center:
            shape.translate(Vector(-size[0]/2, -size[1]/2, -size[2]/2))
        write_log("Info", f"Created cube: {size}, center={center}")

    elif isinstance(node, Sphere):
        r = node.params.get("r", 1)
        shape = Part.makeSphere(r)
        write_log("Info", f"Created sphere: r={r}")

    elif isinstance(node, Cylinder):
        r = node.params.get("r", 1)
        h = node.params.get("h", 1)
        center = node.params.get("center", False)
        shape = Part.makeCylinder(r, h)
        if center:
            shape.translate(Vector(0,0,-h/2))
        write_log("Info", f"Created cylinder: r={r}, h={h}, center={center}")

    # --- Booleans ---
    elif isinstance(node, (Union, Difference, Intersection)):
        child_shapes = [process_AST_node(doc, c) for c in node.children]
        child_shapes = [s for s in child_shapes if s is not None]
        if child_shapes:
            shape = child_shapes[0]
            for s in child_shapes[1:]:
                if isinstance(node, Union):
                    shape = shape.fuse(s)
                elif isinstance(node, Difference):
                    shape = shape.cut(s)
                elif isinstance(node, Intersection):
                    shape = shape.common(s)
        write_log("Info", f"Processed {node.node_type} with {len(child_shapes)} children")

    # --- Hull / Minkowski ---
    elif isinstance(node, Hull):
        shape = process_hull_node(doc, node)
    elif isinstance(node, Minkowski):
        shape = process_minkowski_node(doc, node)

    # --- Transforms ---
    elif isinstance(node, (Translate, Rotate, Scale, MultMatrix)):
        if node.children:
            shape = process_AST_node(doc, node.children[0])  # Apply transform to first child
            if isinstance(node, Translate):
                vec = node.params.get("vector", [0,0,0])
                shape.translate(Vector(*vec))
                write_log("Info", f"Applied Translate {vec}")
            elif isinstance(node, Rotate):
                vec = node.params.get("vector", [0,0,1])
                angle = node.params.get("angle", 0)
                shape.rotate(Vector(0,0,0), Vector(*vec), angle)
                write_log("Info", f"Applied Rotate axis={vec}, angle={angle}")
            elif isinstance(node, Scale):
                vec = node.params.get("vector", [1,1,1])
                shape.scale(*vec)
                write_log("Info", f"Applied Scale {vec}")
            elif isinstance(node, MultMatrix):
                # For MultMatrix, you may need to construct FreeCAD matrix
                # Here just logging for now
                write_log("Info", f"Encountered MultMatrix (not yet applied)")
        else:
            write_log("Warning", f"Transform {node.node_type} has no children")

    # --- Fallback / unknown ---
    else:
        write_log("Info", f"Unimplemented AST node {node.node_type}")
        shape_name = getattr(node, "node_type", "Node")
        # fallback legacy path if node has children
        children_to_process = getattr(node, "children", [node])
        shape = process_ObjectsViaOpenSCADShape(doc, children_to_process, shape_name)
        write_log("Info", f"Used legacy OpenSCAD processing for {shape_name}")

    return shape


# --- Process full AST ---
def process_AST(doc, ast_nodes, mode="single"):
    """
    Process AST nodes recursively into FreeCAD Part shapes.
    mode:
        "single"  -> collapse all shapes into one FreeCAD object
        "objects" -> create one FreeCAD object per node
    """
    stack = []
    shapes = []

    for node in ast_nodes:
        shape = process_AST_node(doc, node)
        if shape:
            shapes.append(shape)
            if mode == "objects":
                obj_name = getattr(node, "node_type", "SCAD_Node").capitalize()
                obj = doc.addObject("Part::Feature", obj_name)
                obj.Shape = shape

    if mode == "single" and shapes:
        combined = shapes[0]
        for s in shapes[1:]:
            combined = combined.fuse(s)
        obj = doc.addObject("Part::Feature", "SCAD_Object")
        obj.Shape = combined
        return [obj]

    return shapes

