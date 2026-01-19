# SPDX-License-Identifier: LGPL-2.1-or-later

#***************************************************************************
#*   Copyright (c) 2012 Keith Sloan <keith@sloan-home.co.uk>               *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#*   Acknowledgements :                                                    *
#*                                                                         *
#*     Thanks to shoogen on the FreeCAD forum for programming advice       *
#*     and some code.                                                      *
#*     Adapted for SCAD export by Andreas Schuderer.
#*                                                                         *
#***************************************************************************
__title__ = "FreeCAD OpenSCAD Workbench - CSG exporter Version"
__author__ = "Keith Sloan <keith@sloan-home.co.uk>"
__url__ = ["http://www.sloan-home.co.uk/Export/Export.html"]

import math
import re
from contextlib import contextmanager
from builtins import open as pyopen
from typing import Sequence

import FreeCAD
import Part

if FreeCAD.GuiUp:
    gui = True
else:
    gui = False

SIGNIFICANT_DIGITS = 7  # Max number of decimals of floats in OpenSCAD code
EPSILON = 10**(-SIGNIFICANT_DIGITS)   # A tolerance to use in comparisons. Any two values closer than that are seen as equal.
PI = 3.1415926536

#***************************************************************************
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
fn = params.GetInt('exportFn', 0)
fa = params.GetFloat('exportFa', 12.0)
fa_rad = fa*PI/180.0
fs = params.GetFloat('exportFs', 2.0)
conv = params.GetInt('exportConvexity', 10)
# TODO: parameters for SIGNIFICANT_DIGITS and other decisions (and fn?)

#***************************************************************************
# Radius values not fixed for value apart from cylinder & Cone
# no doubt there will be a problem when they do implement Value

@contextmanager
def writer(filename):
    step = "  "
    level = 0
    next_indentation = ""
    f = pyopen(filename, "w")
    try:
        def write(s: str):
            nonlocal level
            nonlocal next_indentation
            new_s = ""  # todo: use join (more efficient than constructing a new str in each loop iteration)
            for c in str(s):
                if c == "\n":
                    next_indentation = step * level
                    new_s += c
                else:
                    if c == "{":
                        level += 1
                        new_s += next_indentation
                    elif c == "}":
                        level -= 1
                        if next_indentation:
                            new_s += (step * level)
                    else:
                        new_s += next_indentation
                    new_s += c
                    next_indentation = ""
            f.write(new_s)

        yield write
    finally:
        f.close()


# with write("./bla.txt") as w:
#     w("Hallo {\n")
#     w("bla();\n}")
#     w("\nfoo()")
#     w(" {")
#     w("\nbar()\n")
#     w("baz() {\n")
#     w("hello();\n}")
#     w("\n}")


def practically_equal(a, b, tol=EPSILON):
    result = True
    a = tuple(a) if hasattr(a, '__len__') else (a,)  # isinstance(.., Iterable) does not work with Center
    b = tuple(b) if hasattr(b, '__len__') else (b,)
    if len(a) < len(b):  # vector recycling
        a = a * (len(b)//len(a)+1)  # zip will make sure we won't overshoot
    if len(b) < len(a):
        b = b * (len(a)//len(b)+1)
    for some_a, some_b in zip(a, b):
        result = result and abs(some_a - some_b) < tol
    return result


def maybe_zero(x, tol=EPSILON):
    """Sanitizes floats so that almost zero becomes zero"""
    if isinstance(x, Sequence):
        return [0 if practically_equal(item, 0, tol=tol) else item for item in x]
    else:
        return 0 if practically_equal(x, 0, tol=tol) else x


def fstr(x):
    """Returns a sanitized string representation of a number"""
    if hasattr(x, '__len__'):
        return vecstr(x)

    x = round(x, SIGNIFICANT_DIGITS)
    if x == int(x):
        return str(int(x))
    else:
        return str(x)


def vecstr(x):
    """Returns an iterable as an openscad vector"""
    inner = ", ".join(fstr(elem) for elem in x)
    return f"[{inner}]"


# def check_multmatrix(write, ob, x, y, z):
#     b = FreeCAD.Vector(x, y, z)
#     if ob.Placement.isNull():
#         return 0 # center = false no mm
#     elif ob.Placement.Rotation.isNull() and \
#         (ob.Placement.Base - b).Length < EPSILON:
#         return 2 # center = true and no mm
#     else:
#         m = ob.Placement.toMatrix()
#         # adjust position for center displacements
#         write("multmatrix([["+fstr(m.A11)+", "+fstr(m.A12)+", "+fstr(m.A13)+", "+fstr(m.A14)+"], ["\
#              +fstr(m.A21)+", "+fstr(m.A22)+", "+fstr(m.A23)+", "+fstr(m.A24)+"], ["\
#              +fstr(m.A31)+", "+fstr(m.A32)+", "+fstr(m.A33)+", "+fstr(m.A34)+"]]) {\n")  #, [0, 0, 0, 1]]) {\n")
#         return 1 # center = false and mm


def discretize(wire_or_edge, transform=None):
    # OpenSCAD implementation of circle facet calculation: https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Other_Language_Features#$fs
    if fn > 0:
        num_points = int(max(3, fn))
    else:
        num_points = int(max(min(360.0 / fa, wire_or_edge.Length / fs), 5) + 1)
    print(f"Discretizing object {wire_or_edge} with {num_points=}")
    disc_vectors = wire_or_edge.discretize(Number=num_points)
    if practically_equal(disc_vectors[0], disc_vectors[-1]):
        disc_vectors.pop()
    if transform is not None:
        disc_vectors = [transform(v) for v in disc_vectors]
    return disc_vectors


def check_naming(write, ob):
    """If object is labeled in a nonstandard way, creates a comment with the label"""
    if ob.Label == ob.Name:
        return
    ty_parts = ob.TypeId.split("::")
    ty = ty_parts[-1] if len(ty_parts) > 1 else ty_parts[0]
    names_to_ignore = [ty, "Fusion", "Cube"]
    names_pattern = "|".join(re.escape(n) for n in names_to_ignore)
    if re.match(rf"^(?:{names_pattern})\d*$", ob.Label) is None:
        write(f"// {ob.Label}\n ")


@contextmanager
def placement(write, ob, x, y, z):
    check_naming(write, ob)
    b = FreeCAD.Vector(x, y, z)
    if ob.Placement.isNull():
        yield ''
    elif ob.Placement.Rotation.isNull() and practically_equal((ob.Placement.Base - b).Length, 0):
        yield ', center=true'
    else:
        did_something = False
        x, y, z = ob.Placement.Base  # TODO: shorten with iterable version of placement_equal and vecstr
        if not (practically_equal(x, 0) and practically_equal(y, 0) and practically_equal(z, 0)):
            write(f"translate([{fstr(x)}, {fstr(y)}, {fstr(z)}]) ")
            did_something = True
        if not ob.Placement.Rotation.isNull():
            rx, ry, rz = ob.Placement.Rotation.Axis
            angle = ob.Placement.Rotation.Angle * 180 / PI
            if not practically_equal(angle, 0):
                if practically_equal(ry, 0) and practically_equal(rz, 0):
                    write(f"rotate([{fstr(angle)}, 0, 0])")
                elif practically_equal(rx, 0) and practically_equal(rz, 0):
                    write(f"rotate([0, {fstr(angle)}, 0])")
                elif practically_equal(rx, 0) and practically_equal(ry, 0):
                    write(f"rotate([0, 0, {fstr(angle)}])")
                else:
                    write(f"rotate(a={fstr(angle)}, v=[{fstr(rx)}, {fstr(ry)}, {fstr(rz)}]) ")
                did_something = True
        if did_something:
            write("\n ")
        yield ''
        # else:
    #     m = ob.Placement.toMatrix()
    #     write("multmatrix([["+fstr(m.A11)+", "+fstr(m.A12)+", "+fstr(m.A13)+", "+fstr(m.A14)+"], ["\
    #          +fstr(m.A21)+", "+fstr(m.A22)+", "+fstr(m.A23)+", "+fstr(m.A24)+"], ["\
    #          +fstr(m.A31)+", "+fstr(m.A32)+", "+fstr(m.A33)+", "+fstr(m.A34)+"]]) {\n")
    #     yield ''
    #     write("}\n")  # TODO: Do we actually need the braces?


def mesh2polyhedron(mesh):
    pointstr = ', '.join(['[%f, %f, %f]' % tuple(vec) for vec in mesh.Topology[0]])
    trianglestr = ', '.join(['[%d, %d, %d]' % tuple(tri) for tri in mesh.Topology[1]])
    # avoiding deprecation warning by changing triangles to faces
    #return 'polyhedron ( points = [%s], triangles = [%s]);' % (pointstr, trianglestr)
    return 'polyhedron(points=[%s], faces=[%s]);' % (pointstr, trianglestr)


def vector2d(v):
    return [v[0], v[1]]


def shape2polyhedron(shape):
    import MeshPart
    return mesh2polyhedron(MeshPart.meshFromShape(Shape=shape, Deflection=params.GetFloat('meshdeflection', 0.0)))


def process_object(write, ob):
    print("Placement")
    print("Pos   : " + str(ob.Placement.Base))
    print("axis  : " + str(ob.Placement.Rotation.Axis))
    print("angle : " + str(ob.Placement.Rotation.Angle))

    if ob.TypeId == "Part::Sphere":
        print("Sphere Radius : " + str(ob.Radius))
        with placement(write, ob, 0, 0, 0):
            write("sphere(r=" + fstr(ob.Radius) + ");\n")

    elif ob.TypeId == "Part::Box":
        print("cube : (" + str(ob.Length) + ", " + str(ob.Width) + ", " + str(ob.Height) + ")")
        with placement(write, ob, -ob.Length / 2, -ob.Width / 2, -ob.Height / 2) as center:
            if practically_equal(ob.Length, ob.Width) and practically_equal(ob.Length, ob.Height):
                write("cube(" + fstr(ob.Length.Value) + center + ");\n")
            else:
                write("cube(size=[" + fstr(ob.Length.Value) + ", " + fstr(ob.Width.Value) + ", " + fstr(
                    ob.Height.Value) + "]" + center + ");\n")

    elif ob.TypeId == "Part::Cylinder":
        print("cylinder : Height " + str(ob.Height) + " Radius " + str(ob.Radius))
        with placement(write, ob, 0, 0, -ob.Height / 2) as center:
            write("cylinder(h=" + fstr(ob.Height.Value) + ", r=" + fstr(ob.Radius.Value) + center + ");\n")

    elif ob.TypeId == "Part::Cone":
        print("cone : Height " + str(ob.Height) + " Radius1 " + str(ob.Radius1) + " Radius2 " + str(ob.Radius2))
        with placement(write, ob, 0, 0, -ob.Height / 2) as center:
            write("cylinder(h=" + fstr(ob.Height.Value) + ", r1=" + fstr(ob.Radius1.Value) + \
                  ", r2=" + fstr(ob.Radius2.Value) + center + ");\n")

    elif ob.TypeId == "Part::Torus":
        print("Torus")
        print(ob.Radius1)
        print(ob.Radius2)
        print(ob.Angle1)
        print(ob.Angle2)
        print(ob.Angle3)
        r1 = ob.Radius1.Value  # radius of the donut hole
        r2 = ob.Radius2.Value  # half thickness of the donut rim
        a1 = ob.Angle1.Value  # start angle of the rim's circle segment
        a2 = ob.Angle2.Value  # end angle of the rim's circle segment
        a3 = ob.Angle3.Value  # main donut circle segment angle
        with placement(write, ob, 0, 0, 0):
            write("// (FreeCAD Torus)\n")  # TODO: make torus an openscad module?
            if practically_equal(a3, 360.0):
                write("rotate_extrude() ")
            else:
                write(f"rotate_extrude(angle={fstr(a3)})")
            write(f" translate([{fstr(r1)}, 0, 0]) ")
            if practically_equal(a1, -180.0) and practically_equal(a2, 180.0):
                write(f" circle({fstr(r2)});\n")
            else:
                start = -a1
                angle = a1 - (a2 if a2 > a1 else a2 + 360)
                write("\n // constructing a circle segment\n")  # TODO: make sector an openscad module
                write(f" projection(cut=true) rotate_extrude(angle={fstr(angle)}, start={fstr(start)}) square([{fstr(r2)}, 0.0001]);\n")

    elif ob.TypeId == "Part::Prism":
        f = fstr(ob.Polygon)
        r = fstr(ob.Circumradius)  # length seems to be the outer radius
        h = fstr(ob.Height.Value)
        with placement(write, ob, 0, 0, -float(h) / 2) as center:
            write("cylinder($fn=" + f + ", h=" + h + ", r=" + r + center + ");\n")

    elif ob.TypeId == "Part::Extrusion":
        print("Extrusion")
        print(ob.Base)
        print(ob.Base.Name)
        lenFwd = ob.LengthFwd.Value
        lenRev = ob.LengthRev.Value
        if ob.Reversed and not ob.Symmetric:
            lenRev, lenFwd = lenFwd, lenRev
        if practically_equal(lenFwd, 0) and practically_equal(lenRev, 0):
            lenFwd = ob.Dir.Length
        print("lenRev",lenRev,"lenFwd",lenFwd)
        if ob.Symmetric:  # Ignore lenRev and ob.Reversed
            lenRev = 0
        dirMode = ob.DirMode  # Normal (of .Base), Edge (of .DirLink), Custom (see .Dir)
        # Dir always contains the (computed or entered) direction of the extrusion (=Normal of Base if that mode is set)
        extrDir = ob.Dir  # Note: if Fwd and Rev are both zero, also contains magnitude information (=extr. len)!
        # if ob.Base.isDerivedFrom('Part::Part2DObjectPython') and \
        #         hasattr(ob.Base, 'Proxy') and hasattr(ob.Base.Proxy, 'TypeId'):
        #     print("Part2DObjectPython")  # TODO: Handle that base object of BezCurve, BSpline and Wire has been changed to Part::FeaturePython.
        #     ptype = ob.Base.Proxy.TypeId
        #     if ptype == "Polygon":
        #         f = fstr(ob.Base.FacesNumber)
        #         r = fstr(ob.Base.Radius)
        #         h = fstr(ob.Dir[2])
        #         print("Faces : " + f)
        #         print("Radius : " + r)
        #         print("Height : " + h)
        #         with placement(write, ob, 0, 0, -float(h) / 2) as center:
        #             write("cylinder($fn=" + f + ", h=" + h + ", r=" + r + center + ");\n")
        #
        #     elif ptype == "Circle":
        #         r = fstr(ob.Base.Radius)
        #         h = fstr(ob.Dir[2])
        #         print("Radius : " + r)
        #         print("Height : " + h)
        #         with placement(write, ob, 0, 0, -float(h) / 2) as center:
        #             write("cylinder(h=" + h + ", r=" + r + center + ");\n")
        #
        #     elif ptype == "Wire":
        #         print("Wire extrusion")
        #         print(ob.Base)
        #         with placement(write, ob, 0, 0, 0) as center:
        #             write(f"linear_extrude(height={fstr(ob.Dir[2])}{center}, convexity=$convexity, twist=0, slices=2) {{\n")
        #             write(vertices_to_polygon(ob.Base.Shape.Vertexes))
        #
        #     else:
        #         print(f"Unsupported extrusion base object {ob.Base} of type {ptype}")

        if ob.Base.isDerivedFrom('Part::Plane'):
            length = ob.Base.Length.Value
            width = ob.Base.Width.Value
            with placement(write, ob, 0, 0, 0) as center:
                write(f"linear_extrude(height={fstr(ob.Dir[2])}, center=true, convexity=$convexity, twist=0, slices=2)\n")
                write(f" square(size=[{fstr(length)}, {fstr(width)}]" + center + ");\n")

        elif ob.Base.isDerivedFrom("Part::RegularPolygon"):  # TODO: isinstance check?
            h = fstr(ob.Dir[2])  # TODO
            with placement(write, ob, 0, 0, 0):  # Placement of extrusion result
                with placement(write, ob.Base, 0, 0, 0):  # Placement of 2d object to extrude
                    center = ', center=true' if ob.Symmetric else ''
                    write(f"linear_extrude(height={fstr(lenFwd)}, slices=2{center}) ")
                    write(f"circle($fn={fstr(ob.Base.Polygon)}, r={fstr(ob.Base.Circumradius)});\n")

        # TODO: 2D objects (from sketches or other) can also exist without extrusions in FreeCAD and OpenSCAD!
        elif ob.Base.TypeId == "Sketcher::SketchObject":  # TODO use e.g. isinstance(Part.Sketch) everywhere?
            wires = [w for w in ob.Base.Shape.Wires if w.isClosed()]
            print(f"SketchObject with {len(wires)} Wires{' (skipping '+str(len(ob.Base.Shape.Wires)-len(wires))+' non-closed Wires)' if len(ob.Base.Shape.Wires) != len(wires) else ''}:")
            if not wires:
                pass  # TODO: skip empty sketches, also for nested-depth extrusions
            with placement(write, ob, 0, 0, 0):  # Placement of the extrusion result
                with placement(write, ob.Base, 0, 0, 0):  # Placement of the 2d object (sketch)
                    # Figure out extrusion groups (solids, holes-in-solids, solids-in-holes-in-solids, ...)
                    extrusion_groups = {}
                    for wire, depth in zip(wires, nesting_depths(wires)):
                        extrusion_groups.setdefault(depth, []).append(wire)  # TODO: we can probably just assume that depths are ascending without gaps, so a simple list where indices are depths should suffice
                    extrusion_groups = [(depth, wires) for depth, wires in sorted(extrusion_groups.items())]
                    print(f"Extrusion groups by nesting depth: {[(k, v) for k,v in extrusion_groups]}")
                    bool_op_tree = ['union', extrusion_groups[0][1]]  # Start with initial solid extrusion (nesting depth 0)
                    for depth, curr_wires in extrusion_groups[1:]:
                        if depth % 2 == 0:
                            # Solid
                            bool_op_tree = ["union", bool_op_tree, curr_wires]
                        else:
                            # Hole
                            bool_op_tree = ["difference", bool_op_tree, curr_wires]
                    print(bool_op_tree)

                    # Transform from tree to queue (TODO: temporarily -- we'll use an AST later)
                    stack = [bool_op_tree]
                    bool_op_queue = []
                    while stack:
                        curr = stack.pop()
                        if curr[0] == "union":
                            if len(curr) == 2:  # simplify single-object operations (should only happen with unions)
                                stack.append(curr[1])
                            else:
                                bool_op_queue.append("union")
                                stack.append("/union")
                                for arg in reversed(curr[1:]):
                                    stack.append(arg)
                        elif curr[0] == "difference":
                            bool_op_queue.append("difference")
                            stack.append("/difference")
                            for arg in reversed(curr[1:]):
                                stack.append(arg)
                        else:  # wires or scope ends
                            bool_op_queue.append(curr)
                    print(bool_op_queue)


                    inv_sketch_placement = ob.Base.Placement.inverse()
                    def v_local(v):  # world -> sketch local
                        return inv_sketch_placement.multVec(v)

                    def d_local(d):  # world direction -> sketch local direction (no translation)
                        return inv_sketch_placement.Rotation.multVec(d)

                    # Walk through operations (TODO: will probably be scrapped as we'll work with an AST)
                    for operation in bool_op_queue:
                        if operation == "union":
                            write("union() {\n")
                            continue
                        elif operation == "difference":
                            write("difference() {\n")
                            continue
                        elif operation in ("/union", "/difference"):
                            write("}\n")
                            continue
                        else:
                            wires = operation

                        center = ', center=true' if ob.Symmetric else ''
                        extrusionVec = '' if dirMode == 'Normal' else f", v={vecstr(d_local(extrDir))}"
                        if practically_equal(lenRev, 0):
                            write(f"linear_extrude(height={fstr(lenFwd)}{extrusionVec}, slices=2{center}, convexity=$convexity) {{\n")
                        else:
                            lenTotal = lenFwd + lenRev
                            write(f"translate([0, 0, {fstr(-lenRev)}])  // LengthRev={fstr(lenRev)}, LengthFwd={fstr(lenFwd)}{' (reversed)' if ob.Reversed else ''}\n")
                            write(f" linear_extrude(height={fstr(lenTotal)}{extrusionVec}, slices=2{center}, convexity=$convexity) {{\n")

                        write(f"// from {ob.Base.Label}:\n")

                        for wire in wires:
                            # TODO on factoring out sketch: skip non-closed wires
                            # Closed shape consisting of single edge (circle, ellipse, spline(?))
                            if len(wire.Edges) == 1 and wire.Edges[0].isClosed():
                                edge = wire.Edges[0]
                                curve = edge.Curve

                                if curve.TypeId == "Part::GeomCircle":  # TODO: isinstance(Part.Circle)?
                                    center = v_local(curve.Center)
                                    radius = curve.Radius
                                    axis = d_local(curve.Axis)  # TODO: can we safely ignore the axis? Seems to be [0,0,1] (Sketch normal)
                                    if not practically_equal(center, 0):
                                        write(f"translate([{fstr(center[0])}, {fstr(center[1])}]) ")
                                    write(f"circle({fstr(radius)});\n")

                                elif curve.TypeId == "Part::GeomEllipse":
                                    center = v_local(curve.Center)
                                    majorRadius = curve.MajorRadius
                                    minorRadius = curve.MinorRadius
                                    axis = d_local(curve.Axis)  # TODO: can we safely ignore the axis? Seems to be [0,0,1] (Sketch normal)
                                    if not practically_equal(center, 0):
                                        write(f"translate([{fstr(center[0])}, {fstr(center[1])}]) ")
                                    if practically_equal(majorRadius, minorRadius):
                                        write(f"circle({fstr(majorRadius)});\n")
                                    else:
                                        local_x_axis = FreeCAD.Base.Vector(d_local(curve.XAxis))
                                        # local_focus1 = FreeCAD.Base.Vector(d_local(curve.Focus1))
                                        # local_focus2 = FreeCAD.Base.Vector(d_local(curve.Focus2))
                                        angle = local_x_axis.getAngle(FreeCAD.Base.Vector([1, 0, 0]))*180/PI
                                        if not practically_equal(angle, 0) and not practically_equal(angle, 180) and not practically_equal(angle, 360):
                                            write(f"rotate(a=[0, 0, {fstr(angle)}]) ")
                                        write(f"resize([{fstr(2*majorRadius)}, {fstr(2*minorRadius)}]) ")
                                        write(f"circle({fstr(majorRadius)});  // Ellipse\n")

                                else:
                                    # Another type of closed curve
                                    print("Discretizing unrecognized closed single-edge curve to polygon")
                                    disc_vectors = discretize(wire)
                                    pts2d = [v_local((p[0], p[1])) for p in disc_vectors]
                                    print(f"Discretizing curved Edge {e.Curve if hasattr(e, 'Curve') else e} in Wire")
                                    write(f"polygon(points={vecstr(pts2d)});\n")  # TODO: unify/refactor

                            else:
                                print("Wire extrusion:", wire)
                                # General closed loop -> ordered vertex list
                                pts = []
                                last_point = None
                                contains_discretization = False
                                for e in wire.OrderedEdges:
                                    if hasattr(e, 'Curve') and e.Curve.TypeId == "Part::GeomLine":
                                        pts.append(v_local(e.Vertexes[0].Point))
                                        last_point = v_local(e.Vertexes[1].Point)
                                    else:
                                        print(f"Discretizing curved Edge {e.Curve if hasattr(e, 'Curve') else e} in Wire")
                                        disc_pts = [v_local(p) for p in discretize(e)]
                                        pts += disc_pts[:-1]
                                        last_point = disc_pts[-1]
                                        contains_discretization = True
                                pts.append(last_point)
                                if practically_equal(pts[0], pts[-1]):
                                    pts.pop()

                                if contains_discretization:
                                    write("// Polygon with discretized curve(s) (using OpenSCAD export parameters)\n")

                                if any(not practically_equal(p[2], 0) for p in pts):
                                    print("Warning: dropping third dimension of sketch wire points")
                                pts2d = [(p[0], p[1]) for p in pts]  # TODO: What about sketches that extend into 3rd dimension? Currently we just remove z.

                                # Recognize rectangle and write it instead of polygon.
                                if len(pts2d) == 4:
                                    # We check whether all angles between points are 90 degrees
                                    pt_angles = [math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])) for a, b in zip([*pts2d[:-1], pts2d[-1]], [*pts2d[1:], pts2d[0]])]
                                    print(f"{pt_angles=}")
                                    # Note: a-b instead of b-a because otherwise, counterclockwise = neg angles (why?)
                                    corner_angles = [(360+a-b)%360-180 for a, b in zip([*pt_angles[:-1], pt_angles[-1]], [*pt_angles[1:], pt_angles[0]])]
                                    print(f"{corner_angles=}")
                                    rect_angle = pt_angles[0]
                                    if all(practically_equal(abs(a), 90, tol=0.0001) for a in corner_angles):
                                        print("Recognized rectangle")
                                        #        ___ p3
                                        # p0 ---       \    Note: Orientation can be clockwise or counterclockwise!
                                        #   \       ___ p2   ^
                                        #    p1 ---          |
                                        #                 -- o --> origin (we'll translate p0 from here)
                                        #                    |
                                        is_counterclockwise = corner_angles[0] > 0  # as in diagram above (normal case)
                                        print(f"{'counter' if is_counterclockwise else ''}clockwise")
                                        origin = pts2d[0]
                                        p0x, p0y = pts2d[0]
                                        p1x, p1y = pts2d[1]
                                        p3x, p3y = pts2d[3]
                                        p0p1_dist = math.sqrt((p1x-p0x)**2 + (p1y-p0y)**2)
                                        p0p3_dist = math.sqrt((p3x-p0x)**2 + (p3y-p0y)**2)
                                        if is_counterclockwise:
                                            width_height = abs(p0p1_dist), abs(p0p3_dist)
                                        else:
                                            width_height = abs(p0p3_dist), abs(p0p1_dist)
                                            rect_angle -= 90
                                        print(f"{width_height=}")
                                        # TODO: get rid of occasional +/-90 deg rotation for horizontal rects by swapping w/h and shifting rect (changing origin)
                                        if not practically_equal(origin, (0, 0)):
                                            write(f"translate({vecstr(origin)}) ")
                                        if not practically_equal(rect_angle, 0):
                                            print(f"Rotating rectangle by {rect_angle} degrees")
                                            write(f"rotate([0, 0, {fstr(rect_angle)}])")
                                        write(f" square({vecstr(width_height)});\n")
                                    else:
                                        print("Did not recognize rectangle")
                                        write(f"polygon(points={vecstr(pts2d)});\n")  # TODO: unify/refactor
                                else:
                                    print("Did not recognize special 2d shape. Exporting as polygon")
                                    write(f"polygon(points={vecstr(pts2d)});\n")  # TODO: unify/refactor
                        write("}\n")

        elif ob.Base.Name.startswith('this_is_a_bad_idea'):  # TODO: Wut? :)
            pass

        else:
            print(f"Unsupported extrusion base object {ob.Base}")
            pass  # TODO: There should be a fallback solution

    elif ob.TypeId == "Part::Cut":
        print("Cut")
        with placement(write, ob, 0, 0, 0):
            write("difference() {\n")
            process_object(write, ob.Base)
            process_object(write, ob.Tool)
            write("}\n")

    elif ob.TypeId == "Part::Fuse":
        print("union")
        with placement(write, ob, 0, 0, 0):
            write("union() {\n")
            process_object(write, ob.Base)
            process_object(write, ob.Tool)
            write("}\n")

    elif ob.TypeId == "Part::Common":
        print("intersection")
        with placement(write, ob, 0, 0, 0):
            write("intersection() {\n")
            process_object(write, ob.Base)
            process_object(write, ob.Tool)
            write("}\n")

    elif ob.TypeId == "Part::MultiFuse":
        print("Multi Fuse / union")
        with placement(write, ob, 0, 0, 0):
            write("union() {\n")
            for subobj in ob.Shapes:
                process_object(write, subobj)
            write("}\n")

    elif ob.TypeId == "Part::MultiCommon":
        print("Multi Common / intersection")
        with placement(write, ob, 0, 0, 0):
            write("intersection() {\n")
            for subobj in ob.Shapes:
                process_object(write, subobj)
            write("}\n")

    elif ob.isDerivedFrom('Part::Feature'):
        print("Part::Feature", ob.Name)  # TODO: Handle that the base object of BezCurve, BSpline and Wire has been changed to Part::FeaturePython.
        with placement(write, ob, 0, 0, 0):
            write(f"{shape2polyhedron(ob.Shape)}  // {ob.Label}: mesh fallback.\n")

    else:
        # TODO: Compound
        print(f"Unsupported object {ob}")

# def interior_point(face):
#     # Tessellate and take a triangle centroid (inside the face)
#     verts, tris = face.tessellate(0.1)  # adjust deflection if needed
#     i0, i1, i2 = tris[0]
#     p0 = FreeCAD.Base.Vector(*verts[i0])
#     p1 = FreeCAD.Base.Vector(*verts[i1])
#     p2 = FreeCAD.Base.Vector(*verts[i2])
#     return (p0 + p1 + p2) * (1.0 / 3.0)


def face_contains(outer_face, inner_face, area_tol=EPSILON):
    # TODO: Not that fast, add quick check with bounding box
    common = outer_face.common(inner_face)
    return abs(common.Area - inner_face.Area) <= area_tol


def nesting_depths(wires):
    # Takes an iterable of Part.Wires and returns a list of same length with their nesting depths.
    # Non-closed wires will get a depth of zero.
    # Note that they don't have to be in 2D space (the sketch can be tilted in world space)
    faces = [Part.Face(w) if w.isClosed() else None for w in wires]
    # points = [interior_point(f) if f is not None else None for f in faces]

    depths = []
    for i, fi in enumerate(faces):
        if fi is None:
            depths.append(0)
            continue
        depth = 0
        for j, fj in enumerate(faces):
            if i == j or fj is None:
                continue
            if face_contains(fj, fi):
            # if fj.isInside(p, EPSILON, True):
                print(f"Wire {i} is inside Wire {j}")
                depth += 1
        depths.append(depth)
    print(f"Nesting depths: {[str(d)+': '+str(w.Edges[0].Curve.TypeId)+' ('+str(len(w.Edges))+')' for d, w in zip(depths, wires)]}")
    return depths


def export(export_list, filename):
    """called when FreeCAD exports a file"""
    # process Objects
    print("\nStart Export 0.1d\n")
    print("Open Output File")
    with writer(filename) as write:
        print("Write Initial Output")
        # Not sure if comments as per scad are allowed in csg file
        write("// SCAD file generated from FreeCAD %s\n" % '.'.join(FreeCAD.Version()[0:3]))
        write(f"$fn = 0;\n$fa = {fa};\n$fs = {fs};\n")
        write(f"$convexity = {conv};\n\n")
        for ob in export_list:
            print(ob)
            print("Name : " + ob.Name)
            print("Type : " + ob.TypeId)
            if ob.Visibility:
                print("Shape : ")
                print(ob.Shape)
                process_object(write, ob)
                write("\n")
            else:
                print(f"{ob.Name} is invisible. Skipping")

    FreeCAD.Console.PrintMessage("Successfully exported" + " " + filename)
