# ast_nodes.py
from typing import List, Optional

class Node:
    """Base AST node"""
    def __init__(self, node_type, params=None, children=None):
        self.node_type = node_type
        self.params = params or {}
        self.children = children or []

class Cube(Node):
    def __init__(self, size, center=False):
        super().__init__("cube", {"size": size, "center": center})

class Sphere(Node):
    def __init__(self, r, fn=None, fa=None, fs=None):
        super().__init__("sphere", {"r": r, "$fn": fn, "$fa": fa, "$fs": fs})

class Cylinder(Node):
    def __init__(self, r, h, center=False, fn=None, fa=None, fs=None):
        super().__init__("cylinder", {"r": r, "h": h, "center": center, "$fn": fn, "$fa": fa, "$fs": fs})

class Union(Node):
    def __init__(self, children=None):
        super().__init__("union", children=children or [])

class Difference(Node):
    def __init__(self, children=None):
        super().__init__("difference", children=children or [])

class Intersection(Node):
    def __init__(self, children=None):
        super().__init__("intersection", children=children or [])

class Hull(Node):
    def __init__(self, children=None):
        super().__init__("hull", children=children or [])

class Minkowski(Node):
    def __init__(self, children=None):
        super().__init__("minkowski", children=children or [])

class Group(Node):
    def __init__(self, children=None):
        super().__init__("group", children=children or [])

class MultMatrix(Node):
    def __init__(self, matrix=None, children=None):
        super().__init__("multmatrix", {"matrix": matrix}, children or [])

class Translate(Node):
    def __init__(self, vector=None, children=None):
        super().__init__("translate", {"vector": vector or [0,0,0]}, children or [])

class Rotate(Node):
    def __init__(self, vector=None, angle=None, children=None):
        super().__init__("rotate", {"vector": vector or [0,0,1], "angle": angle or 0}, children or [])

class Scale(Node):
    def __init__(self, vector=None, children=None):
        super().__init__("scale", {"vector": vector or [1,1,1]}, children or [])

