from .parser import parse_csg_file
from .processor import process_AST

## Needs to return a multifuse Shape !!!
## Old used to create a work document - easier debugging?

def process_SCAD_object(doc, filename):
    """
    Top-level function to process a SCAD/CSG file
    """
    ast_nodes = parse_csg_file(filename)
    shapes = process_AST(doc, ast_nodes)
    return shapes

