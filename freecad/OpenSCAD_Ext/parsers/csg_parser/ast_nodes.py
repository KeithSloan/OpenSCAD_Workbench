# ast_nodes.py
from typing import List, Optional, Dict, Any


class Node:
    """Base AST node"""
    def __init__(self, node_type: str, params: Dict[str, Any] = None, children=None):
        self.node_type = node_type
        self.params = params or {}
        self.children = children or []

    def __repr__(self):
        return f"<{self.node_type} children={len(self.children)} params={self.params}>"

# ----------------------------
# 2D primitives
# ----------------------------

class Circle(Node):
    def __init__(self, r, fn=None, fa=None, fs=None):
        super().__init__("circle", {"r": r, "$fn": fn, "$fa": fa, "$fs": fs})

class Square(Node):
    def __init__(self, size, center=False):
        super().__init__("square", {"size": size, "center": center})

class Polygon(Node):
    def __init__(self, points=None, paths=None):
        super().__init__("polygon", {"points": points or [], "paths": paths or []})

# ----------------------------
# 3D primitives
# ----------------------------

class Cube(Node):
    def __init__(self, size, center=False):
        super().__init__("cube", {"size": size, "center": center})

class Sphere(Node):
    def __init__(self, r, fn=None, fa=None, fs=None):
        super().__init__("sphere", {"r": r, "$fn": fn, "$fa": fa, "$fs": fs})

class Cylinder(Node):
    def __init__(self, h, r=None, r1=None, r2=None, center=False, fn=None, fa=None, fs=None):
        super().__init__(
            "cylinder",
            {
                "h": h,
                "r": r,
                "r1": r1,
                "r2": r2,
                "center": center,
                "$fn": fn,
                "$fa": fa,
                "$fs": fs,
            },
        )

class Polyhedron(Node):
    def __init__(self, points=None, faces=None):
        super().__init__("polyhedron", {"points": points or [], "faces": faces or []})

# ----------------------------
# Boolean / CSG operators
# ----------------------------

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

# ----------------------------
# Transforms
# ----------------------------

class Translate(Node):
    def __init__(self, vector=None, children=None):
        super().__init__("translate", {"vector": vector or [0, 0, 0]}, children or [])

class Rotate(Node):
    def __init__(self, vector=None, angle=None, children=None):
        super().__init__("rotate", {"vector": vector, "angle": angle}, children or [])

class Scale(Node):
    def __init__(self, vector=None, children=None):
        super().__init__("scale", {"vector": vector or [1, 1, 1]}, children or [])

class MultMatrix(Node):
    def __init__(self, matrix=None, children=None):
        super().__init__("multmatrix", {"matrix": matrix}, children or [])

# ----------------------------
# Extrusions
# ----------------------------

class LinearExtrude(Node):
    def __init__(self, height, center=False, twist=0, scale=1.0, children=None):
        super().__init__(
            "linear_extrude",
            {
                "height": height,
                "center": center,
                "twist": twist,
                "scale": scale,
            },
            children or [],
        )

class RotateExtrude(Node):
    def __init__(self, angle=360, convexity=None, children=None):
        super().__init__(
            "rotate_extrude",
            {"angle": angle, "convexity": convexity},
            children or [],
        )

