from .ast import Cube, Cylinder, Union, Hull, Minkowski

def parse_csg_file(filename):
    """
    Parse a modern OpenSCAD CSG file into an AST.
    Currently placeholder parser: extend for your OpenSCAD output.
    """
    nodes = []

    with open(filename, "r", encoding="utf-8") as fp:
        lines = fp.readlines()

    stack = []
    for line in lines:
        line = line.strip()
        if line.startswith("cube"):
            # Example: cube([10,10,10], center=true);
            nodes.append(Cube(size=[10,10,10], center=True))
        elif line.startswith("cylinder"):
            nodes.append(Cylinder(r=5, h=10, center=False))
        elif line.startswith("hull"):
            # Collect children on stack
            nodes.append(Hull(children=[]))
        elif line.startswith("minkowski"):
            nodes.append(Minkowski(children=[]))
        # Extend with union, difference, etc.

    return nodes

