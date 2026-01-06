# importSCAD_ASTObject.py
# Import a SCAD/CSG file as a single FreeCAD object using AST evaluation

import FreeCAD
from .parser import parse_csg_file
from .ast_evaluator import evaluate_ast

def import_single_scad(filename, obj_name="SCADObject"):
    """
    Import a SCAD/CSG file as a single Part object.
    Hull/Minkowski or other special ops handled by ast_evaluator.
    """
    FreeCAD.Console.PrintMessage(f"Importing SCAD AST Object: {filename}\n")
    
    # Parse the SCAD/CSG file into AST nodes
    ast_nodes = parse_csg_file(filename)
    
    # Evaluate AST nodes into FreeCAD shapes
    shapes = [evaluate_ast(n) for n in ast_nodes]
    shapes = [s for s in shapes if s]  # Remove None
    
    if not shapes:
        FreeCAD.Console.PrintMessage("No shapes found in AST.\n")
        return None
    
    # Fuse all shapes into one
    final_shape = shapes[0]
    for s in shapes[1:]:
        final_shape = final_shape.fuse(s)
    
    # Add to FreeCAD document
    obj = FreeCAD.ActiveDocument.addObject("Part::Feature", obj_name)
    obj.Shape = final_shape
    FreeCAD.ActiveDocument.recompute()
    
    FreeCAD.Console.PrintMessage(f"Imported SCAD AST Object: {obj_name}\n")
    return obj

