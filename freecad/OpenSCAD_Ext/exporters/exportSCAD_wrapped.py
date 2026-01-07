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

from typing import Iterable, Sequence

import FreeCAD
import re
from contextlib import contextmanager
from builtins import open as pyopen

if FreeCAD.GuiUp:
    gui = True
else:
    gui = False

EPSILON = 1e-7
PI = 3.1415926536
NUM_DECIMALS = 8

#***************************************************************************
# Tailor following to your requirements ( Should all be strings )          *
#fafs = '$fa = 12, $fs = 2'
#convexity = 'convexity = 10'
params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/OpenSCAD")
fa = params.GetFloat('exportFa', 12.0)
fs = params.GetFloat('exportFs', 2.0)
conv = params.GetInt('exportConvexity', 10)


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


def practically_equal(a, b):
    result = True
    a = tuple(a) if hasattr(a, '__len__') else (a,)  # isinstance(.., Iterable) does not work with Center
    b = tuple(b) if hasattr(b, '__len__') else (b,)
    if len(a) < len(b):  # vector recycling
        a = a * (len(b)//len(a)+1)  # zip will make sure we won't overshoot
    if len(b) < len(a):
        b = b * (len(a)//len(b)+1)
    for some_a, some_b in zip(a, b):
        result = result and abs(some_a - some_b) < EPSILON
    return result


def maybe_zero(x):
    """Sanitizes floats so that almost zero becomes zero"""
    if isinstance(x, Sequence):
        return [0 if practically_equal(item, 0) else item for item in x]
    else:
        return 0 if practically_equal(x, 0) else x


def fstr(x):
    """Returns a sanitized string representation of a number"""
    if hasattr(x, '__len__'):
        return vecstr(x)

    x = round(x, NUM_DECIMALS)
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


# def vertices_to_polygon(vertices):
#     pointstr = ', '.join(['[%f, %f]' % tuple(vector2d(v.Point)) for v in vertices])
#     return 'polygon(points=[%s], paths=undef, convexity=1);}' % pointstr


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
                write(f" projection(cut=true) rotate_extrude(angle={fstr(angle)}, start={fstr(start)}) square([{fstr(r2)}, 1]);\n")

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
            num_wires = len(wires)
            print(f"SketchObject with {num_wires} Wires:")
            with placement(write, ob, 0, 0, 0):  # Placement of the extrusion result
                with placement(write, ob.Base, 0, 0, 0):  # Placement of the 2d object (sketch)
                    inv_sketch_placement = ob.Base.Placement.inverse()
                    def v_local(v):  # world -> sketch local
                        return inv_sketch_placement.multVec(v)

                    def d_local(d):  # world direction -> sketch local direction (no translation)
                        return inv_sketch_placement.Rotation.multVec(d)

                    center = ', center=true' if ob.Symmetric else ''
                    extrVec = '' if dirMode == 'Normal' else f", v={vecstr(d_local(extrDir))}"
                    if practically_equal(lenRev, 0):
                        write(f"linear_extrude(height={fstr(lenFwd)}{extrVec}, slices=2{center}, convexity=$convexity) {{\n")
                    else:
                        lenTotal = lenFwd + lenRev
                        write(f"translate([0, 0, {fstr(-lenRev)}])  // LengthRev={fstr(lenRev)}, LengthFwd={fstr(lenFwd)}{' (reversed)' if ob.Reversed else ''}\n")
                        write(f" linear_extrude(height={fstr(lenTotal)}{extrVec}, slices=2{center}, convexity=$convexity) {{\n")

                    write(f"// {ob.Base.Label}\n")

                    for wire in wires:
                        if not wire.isClosed():
                            print("Skipping non-closed Wire")
                            continue

                        # Closed shape consisting of single edge (circle, ellipse, spline(?))
                        if len(wire.Edges) == 1 and wire.Edges[0].isClosed():
                            edge = wire.Edges[0]
                            curve = edge.Curve

                            if curve.TypeId == "Part::GeomCircle":  # TODO: isinstance(Part.Circle)?
                                center = v_local(curve.Center)
                                radius = curve.Radius
                                axis = d_local(curve.Axis)  # TODO: can we safely ignore the axis? Seems to be [0,0,1] (Sketch normal)
                                if not practically_equal(center, 0):
                                    write(f"translate({vecstr(center)}) ")
                                write(f"circle({fstr(radius)});\n")

                            elif curve.TypeId == "Part::GeomEllipse":
                                center = v_local(curve.Center)
                                majorRadius = curve.MajorRadius
                                minorRadius = curve.MinorRadius
                                axis = d_local(curve.Axis)  # TODO: can we safely ignore the axis? Seems to be [0,0,1] (Sketch normal)
                                if not practically_equal(center, 0):
                                    write(f"translate({vecstr(center)}) ")
                                if practically_equal(majorRadius, minorRadius):
                                    write(f"circle({fstr(majorRadius)});\n")
                                else:
                                    # TODO: How to deal with rotation?
                                    local_x_axis = FreeCAD.Base.Vector(d_local(curve.XAxis))
                                    local_focus1 = FreeCAD.Base.Vector(d_local(curve.Focus1))
                                    local_focus2 = FreeCAD.Base.Vector(d_local(curve.Focus2))
                                    angle = local_x_axis.getAngle(FreeCAD.Base.Vector([1, 0, 0]))*180/PI
                                    # angle = local_x_axis.getAngle(FreeCAD.Base.Vector([-1, 0, 0]))*180/PI
                                    if not practically_equal(angle, 0) and not practically_equal(angle, 180) and not practically_equal(angle, 360):
                                        write(f"rotate(a=[0, 0, {fstr(angle)}]) ")
                                    write(f"resize([{fstr(2*majorRadius)}, {fstr(2*minorRadius)}]) ")
                                    write(f"circle({fstr(majorRadius)});  // Ellipse\n")

                            else:
                                # Another type of closed curve
                                print("Skipping unknown closed single-edge curve")
                                pass
                                # TODO: adapt:
                                # # Generic fallback: transform curve by inverse placement
                                # try:
                                #     c2 = c.copy()
                                #     c2.transform(inv.toMatrix())
                                #     out.append(("closed_curve", c2))
                                # except Exception:
                                #     out.append(("closed_curve", c))
                                # continue

                        else:
                            # TODO: Wires inside other Wires should be holes (note that OpenSCAD polygons support this out of the box but do we really want to mash all geometries into one big polygon?)
                            print("Wire extrusion:", wire)
                            # General closed loop -> ordered vertex list
                            pts = [v_local(e.Vertexes[0].Point) for e in wire.OrderedEdges]  # TODO: recognize curve segments and discretize them
                            pts.append(v_local(wire.OrderedEdges[-1].Vertexes[-1].Point))
                            if practically_equal(pts[0], pts[-1]):
                                pts.pop()

                            if any(not practically_equal(p[2], 0) for p in pts):
                                print("Warning: dropping third dimension of sketch wire points")
                            pts2d = [(p[0], p[1]) for p in pts]  # TODO: What about sketches that extend into 3rd dimension? Currently we just remove z.

                            # Recognize rectangle and write it instead of polygon. (TODO next step: rotated rectangle)
                            if len(pts2d) == 4 and (
                                (practically_equal(pts2d[0][0], pts2d[1][0]) and not practically_equal(pts2d[0][1], pts2d[1][1])) and
                                (not practically_equal(pts2d[1][0], pts2d[2][0]) and practically_equal(pts2d[1][1], pts2d[2][1])) and
                                (practically_equal(pts2d[2][0], pts2d[3][0]) and not practically_equal(pts2d[2][1], pts2d[3][1])) and
                                (not practically_equal(pts2d[3][0], pts2d[0][0]) and practically_equal(pts2d[3][1], pts2d[0][1]))
                            ):
                                origin = min(x for x,y in pts2d), min(y for x,y in pts2d)
                                width_height = abs(pts2d[2][0] - pts2d[0][0]), abs(pts2d[1][1] - pts2d[0][1])
                                write(f"translate({vecstr(origin)}) ")
                                write(f" square({vecstr(width_height)});\n")
                            else:
                                write(f"polygon(points={vecstr(pts2d)});\n")
                    write("}\n")

        elif ob.Base.Name.startswith('this_is_a_bad_idea'):  # TODO: Wut? :)
            pass

        else:
            print(
                f"Unsupported extrusion base object {ob.Base}")
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

    FreeCAD.Console.PrintMessage("successfully exported" + " " + filename)
