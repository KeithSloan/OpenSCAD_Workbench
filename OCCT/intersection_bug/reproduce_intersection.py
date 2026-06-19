# BRepAlgoAPI_Common reproducer: an intersection result larger than an operand.
#
# A.common(B) must satisfy A ∩ B ⊆ A, so the result's bounding box can never
# exceed A's.  With A a ~10 mm part and B a 999-scale OpenSCAD clip solid, OCC
# returns a result spanning x[-999, 999] (≈80× outside A) yet reports it valid.
#
# Run in the FreeCAD Python console from this directory:
#   exec(open("reproduce_intersection.py").read())
import Part, os
here = os.path.dirname(__file__) if "__file__" in dir() else "."

a = Part.read(os.path.join(here, "opA.brep"))
b = Part.read(os.path.join(here, "opB.brep"))
print("opA  bb=%s  vol=%.1f valid=%s" % (a.BoundBox, a.Volume, a.isValid()))
print("opB  bb=%s  vol=%.1f valid=%s" % (b.BoundBox, b.Volume, b.isValid()))

r = a.common(b)
print("A.common(B)  bb=%s  vol=%.1f valid=%s" % (r.BoundBox, r.Volume, r.isValid()))

ab, rb = a.BoundBox, r.BoundBox
spill = (rb.XMin < ab.XMin - 1 or rb.XMax > ab.XMax + 1 or
         rb.YMin < ab.YMin - 1 or rb.YMax > ab.YMax + 1 or
         rb.ZMin < ab.ZMin - 1 or rb.ZMax > ab.ZMax + 1)
print("result spills outside opA bbox (BUG):", spill)
