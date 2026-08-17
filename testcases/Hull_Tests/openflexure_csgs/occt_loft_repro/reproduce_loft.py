# OCCT makeLoft (BRepOffsetAPI_ThruSections) reproducer.
# Two near-identical closed rounded-rectangle wires in parallel planes: the
# ruled loft twists (wrong vertex correspondence) and self-intersects, yet
# isValid() == True and the sewn-solid volume collapses to ~9% of expected.
# Run in the FreeCAD Python console from this directory.
import Part, os
here = os.path.dirname(__file__) if "__file__" in dir() else "."
wA = Part.read(os.path.join(here, "wireA.brep"))
wB = Part.read(os.path.join(here, "wireB.brep"))
print("wireA closed=%s edges=%d | wireB closed=%s edges=%d"
      % (wA.isClosed(), len(wA.Edges), wB.isClosed(), len(wB.Edges)))
loft = Part.makeLoft([wA, wB], False, False, False)   # solid, ruled, closed
print("loft type=%s faces=%d valid=%s"
      % (loft.ShapeType, len(loft.Faces), loft.isValid()))
comp = Part.makeCompound(loft.Faces); comp.sewShape(1e-3)
if comp.Shells:
    sol = Part.makeSolid(comp.Shells[0])
    print("solid volume=%.1f valid=%s closed=%s"
          % (sol.Volume, sol.isValid(), sol.isClosed()))
Part.show(wA, "wireA"); Part.show(wB, "wireB"); Part.show(loft, "loft")
