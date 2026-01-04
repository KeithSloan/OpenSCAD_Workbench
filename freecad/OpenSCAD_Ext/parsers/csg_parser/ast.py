class Node:
    """Base AST node"""
    def __init__(self, node_type, params=None, children=None):
        self.node_type = node_type
        self.params = params or {}
        self.children = children or []

class Cube(Node):
    def __init__(self, size, center=False):
        super().__init__("cube", {"size": size, "center": center})

class Cylinder(Node):
    def __init__(self, r, h, center=False):
        super().__init__("cylinder", {"r": r, "h": h, "center": center})

class Hull(Node):
    def __init__(self, children=None):
        super().__init__("hull", children=children or [])

class Minkowski(Node):
    def __init__(self, children=None):
        super().__init__("minkowski", children=children or [])

class Union(Node):
    def __init__(self, children=None):
        super().__init__("union", children=children or [])

# Add other nodes like Difference, Intersection, Sphere, etc.

