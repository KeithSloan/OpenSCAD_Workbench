"""Test command: run a BRep hull loft on the two selected objects.

Select exactly two objects that have a Shape (e.g. two imported .brep solids),
then run this command.  It bakes each object's Placement into the geometry,
calls process_hull_brep_loft.hull_brep_loft([A, B]), and:
  • on success, adds the lofted solid as a Part::Feature "HullLoftTest";
  • on failure, reports it (the [LOFT] trace in the Report View / workbench.log
    shows where it failed).

Intended for debugging the hull-loft path on hand-picked shapes — e.g. load the
A/B .brep files a failed loft saved next to a CSG, select both, and re-run.
"""

import FreeCAD
import FreeCADGui

from freecad.OpenSCAD_Ext.logger.Workbench_logger import write_log


class HullLoftTest_Class:
    def GetResources(self):
        return {
            'MenuText': 'Test: Hull BRep Loft',
            'ToolTip': 'Run a BRep hull loft on the two selected objects',
            'Pixmap': 'hullLoftTest.svg',
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from freecad.OpenSCAD_Ext.parsers.csg_parser.process_hull_brep_loft import (
            hull_brep_loft,
        )

        sel = FreeCADGui.Selection.getSelection()
        if len(sel) != 2:
            FreeCAD.Console.PrintError(
                "Hull BRep Loft test: select exactly 2 objects (got "
                f"{len(sel)}).\n")
            return

        shapes = []
        for obj in sel:
            sh = getattr(obj, "Shape", None)
            if sh is None or sh.isNull():
                FreeCAD.Console.PrintError(
                    f"Hull BRep Loft test: '{obj.Label}' has no usable Shape.\n")
                return
            s = sh.copy()
            try:
                # Bake the object's placement into the geometry so the loft sees
                # the shapes where they are displayed.
                s.transformShape(obj.Placement.Matrix)
            except Exception:
                pass
            shapes.append(s)

        msg = f"Hull BRep Loft test: {sel[0].Label} + {sel[1].Label}"
        FreeCAD.Console.PrintMessage(msg + "\n")
        write_log("Info", msg)

        try:
            result = hull_brep_loft(shapes)
        except Exception as ex:
            FreeCAD.Console.PrintError(f"Hull BRep Loft test: raised {ex}\n")
            return

        if result is None:
            FreeCAD.Console.PrintWarning(
                "Hull BRep Loft test: loft FAILED (returned None) — see the "
                "[LOFT] trace in the Report View.\n")
            return

        doc = FreeCAD.ActiveDocument
        feat = doc.addObject("Part::Feature", "HullLoftTest")
        feat.Shape = result
        doc.recompute()
        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(feat)
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        FreeCAD.Console.PrintMessage(
            f"Hull BRep Loft test: OK — vol={getattr(result, 'Volume', 0):.2f} "
            f"closed={result.isClosed()} valid={result.isValid()}\n")


FreeCADGui.addCommand("HullLoftTest_CMD", HullLoftTest_Class())
