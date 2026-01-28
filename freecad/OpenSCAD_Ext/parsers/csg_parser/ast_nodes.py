# ast_nodes.py
from typing import Optional, Any

# -------------------------------------------------
# Base AST Node
# -------------------------------------------------
class AstNode:
    """
    Base AST node storing:
      - node_type: OpenSCAD keyword
      - params: typed parameters (for FreeCAD BRep creation)
      - csg_params: raw parameters (for flattening / OpenSCAD fallback)
      - children: child AST nodes
    """
    def __init__(
        self,
        node_type: str,
        params: Optional[Any] = None,
        csg_params: Optional[Any] = None,
        children=None
    ):
        self.node_type = node_type
        self.params = params or {}
        self.csg_params = csg_params
        self.children = children or []

    def __repr__(self):
        return (
            f"<{self.node_type} "
            f"children={len(self.children)} "
            f"params={self.params} "
            f"csg_params={self.csg_params}>"
        )


# -------------------------------------------------
# 2D primitives
# -------------------------------------------------
class Circle(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("circle", params or {}, csg_params, children)

class Square(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("square", params or {}, csg_params, children)

class Polygon(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("polygon", params or {}, csg_params, children)


# -------------------------------------------------
# 3D primitives
# -------------------------------------------------
class Cube(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("cube", params or {}, csg_params, children)

class Sphere(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("sphere", params or {}, csg_params, children)

class Cylinder(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("cylinder", params or {}, csg_params, children)

class Polyhedron(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("polyhedron", params or {}, csg_params, children)


# -------------------------------------------------
# Color
# -------------------------------------------------
class Color(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("color", params or {}, csg_params, children)


# -------------------------------------------------
# Boolean / CSG operators
# -------------------------------------------------
class Union(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("union", params or {}, csg_params, children)

class Difference(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("difference", params or {}, csg_params, children)

class Intersection(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("intersection", params or {}, csg_params, children)

class Hull(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("hull", params or {}, csg_params, children)

class Minkowski(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("minkowski", params or {}, csg_params, children)

class Group(AstNode):
    def __init__(self, children=None, params=None, csg_params=None):
        super().__init__("group", params or {}, csg_params, children)


# -------------------------------------------------
# Transforms
# -------------------------------------------------
class Translate(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("translate", params or {}, csg_params, children)

class Rotate(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("rotate", params or {}, csg_params, children)

class Scale(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("scale", params or {}, csg_params, children)

class MultMatrix(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("multmatrix", params or {}, csg_params, children)


# -------------------------------------------------
# Extrusions
# -------------------------------------------------
class LinearExtrude(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("linear_extrude", params or {}, csg_params, children)

class RotateExtrude(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("rotate_extrude", params or {}, csg_params, children)

# -------------------------------------------------
# Unknown / Text 
# -------------------------------------------------

# ToDo Needs additional params

class Text(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__(
            "text",
            params or {},
            csg_params,
            children
        )

class Polyhedron(AstNode):
    def __init__(self, params=None, csg_params=None, children=None):
        super().__init__("polyhedron", params or {}, csg_params, children)

    @property
    def points(self):
        return self.params.get("points", [])

    @property
    def faces(self):
        return self.params.get("faces", [])

    @property
    def convexity(self):
        return self.params.get("convexity")

# -------------------------------------------------
# Unknown / unsupported nodes
# -------------------------------------------------
class UnknownNode(AstNode):
    def __init__(self, node_type, params=None, csg_params=None, children=None):
        super().__init__(node_type, params or {}, csg_params, children)

