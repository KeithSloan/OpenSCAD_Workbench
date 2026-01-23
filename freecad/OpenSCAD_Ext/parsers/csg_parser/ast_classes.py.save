# ast_classes.py
# -----------------------------
# Wrap AST nodes with FreeCAD createShape() functionality
# -----------------------------

import FreeCAD
import Part
from freecad.OpenSCAD_Ext.parsers.csg_parser.ast_nodes import Cube, Sphere, Cylinder, Union, Difference, Intersection

# -----------------------------
# Primitive Wrappers
# -----------------------------
class CubeFC(Cube):
    def createShape(self):
        size = self.size
        center = getattr(self, "center", False)

        # Normalize size
        if isinstance(size, (int, float)):
            sx = sy = sz = size
        else:
            sx, sy, sz = size

        cube = Part.makeBox(sx, sy, sz)
        if center:
            cube.translate(FreeCAD.Vector(-sx/2, -sy/2, -sz/2))
        return cube

class SphereFC(Sphere):
    def createShape(self):
        radius = getattr(self, "radius", 1)
        center = getattr(self, "center", True)
        sphere = Part.makeSphere(radius)
        if not center:
            sphere.translate(FreeCAD.Vector(radius, radius, radius))
        return sphere

class CylinderFC(Cylinder):
    def createShape(self):
        r1 = getattr(self, "r1", 1)
        r2 = getattr(self, "r2", r1)
        height = getattr(self, "height", 1)
        center = getattr(self, "center", False)

        cyl = Part.makeCone(r1, r2, height)
        if center:
            cyl.translate(FreeCAD.Vector(0, 0, -height/2))
        return cyl

#class TorusFC(Torus):
#    def createShape(self):
#        r1 = getattr(self, "r1", 1)
#        r2 = getattr(self, "r2", 0.25)
#        return Part.makeTorus(r1, r2)

# -----------------------------
# Boolean Wrappers
# -----------------------------
class UnionFC(Union):
    def createShape(self):
        if not self.children:
            return None
        result = self.children[0].createShape()
        for child in self.children[1:]:
            result = result.fuse(child.createShape())
        return result

class DifferenceFC(Difference):
    def createShape(self):
        if not self.children:
            return None
        result = self.children[0].createShape()
        for child in self.children[1:]:
            result = result.cut(child.createShape())
        return result

class IntersectionFC(Intersection):
    def createShape(self):
        if not self.children:
            return None
        result = self.children[0].createShape()
        for child in self.children[1:]:
            result = result.common(child.createShape())
        return result

