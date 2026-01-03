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
#fafs = '$fa = %f, $fs = %f' % (fa, fs)
convexity = 'convexity=%d' % conv
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


# def center(b, default=False):
#     if b == 2:
#         return ', center=true' if default != True else ''
#     else:
#         return ', center=false' if default != False else ''


def practically_equal(a, b):
    return abs(a - b) < EPSILON


def maybe_zero(x):
    """Sanitizes floats so that almost zero becomes zero"""
    return 0 if abs(x) < EPSILON else x


def fstr(x):
    """Returns a sanitized string representation of a number"""
    x = round(x, NUM_DECIMALS)
    if x == int(x):
        return str(int(x))
    else:
        return str(x)


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
        write(f"// {ob.Label}\n")


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
        x, y, z = ob.Placement.Base
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


def vertices_to_polygon(vertices):
    pointstr = ', '.join(['[%f, %f]'  % tuple(vector2d(v.Point)) for v in vertices])
    return 'polygon(points=[%s], paths=undef, convexity=1);}' % pointstr


def shape2polyhedron(shape):
    import MeshPart
    return mesh2polyhedron(MeshPart.meshFromShape(Shape=shape, Deflection=params.GetFloat('meshdeflection', 0.0)))


def process_object(write, ob):
    print("Placement")
    print("Pos   : "+str(ob.Placement.Base))
    print("axis  : "+str(ob.Placement.Rotation.Axis))
    print("angle : "+str(ob.Placement.Rotation.Angle))

    if ob.TypeId == "Part::Sphere":
        print("Sphere Radius : "+str(ob.Radius))
        with placement(write, ob, 0, 0, 0):
            write("sphere(r="+fstr(ob.Radius)+");\n")

    elif ob.TypeId == "Part::Box":
        print("cube : ("+ str(ob.Length)+", "+str(ob.Width)+", "+str(ob.Height)+")")
        with placement(write, ob, -ob.Length/2, -ob.Width/2, -ob.Height/2) as center:
            if practically_equal(ob.Length, ob.Width) and practically_equal(ob.Length, ob.Height):
                write("cube(" + fstr(ob.Length.Value) + center + ");\n")
            else:
                write("cube(size=["+fstr(ob.Length.Value)+", "+fstr(ob.Width.Value)+", "+fstr(ob.Height.Value)+"]"+center+");\n")

    elif ob.TypeId == "Part::Cylinder":
        print("cylinder : Height "+str(ob.Height) + " Radius "+str(ob.Radius))
        with placement(write, ob, 0, 0, -ob.Height/2) as center:
            write("cylinder(h="+fstr(ob.Height.Value) + ", r="+fstr(ob.Radius.Value) + center+");\n")

    elif ob.TypeId == "Part::Cone":
        print("cone : Height "+str(ob.Height) + " Radius1 "+str(ob.Radius1)+" Radius2 "+str(ob.Radius2))
        with placement(write, ob, 0, 0, -ob.Height/2) as center:
            write("cylinder(h="+fstr(ob.Height.Value)+ ", r1="+fstr(ob.Radius1.Value)+ \
                  ", r2="+fstr(ob.Radius2.Value)+center+");\n")

    elif ob.TypeId == "Part::Torus":
        print("Torus")
        print(ob.Radius1)
        print(ob.Radius2)
        if ob.Angle3 == 360.00:
            with placement(write, ob, 0, 0, 0):
                write("rotate_extrude("+convexity+")\n")
                write("multmatrix([[1, 0, 0, "+fstr(ob.Radius1)+"], [0, 1, 0, 0], [0, 0, 1, 0]])\n")
                write("circle("+fstr(ob.Radius2)+");\n")
        else: # Cannot convert to rotate extrude, so best effort is polyhedron
            write('%s\n' % shape2polyhedron(ob.Shape))

    elif ob.TypeId == "Part::Prism":
        f = fstr(ob.Polygon)
        r = fstr(ob.Circumradius) # length seems to be the outer radius
        h = fstr(ob.Height.Value)
        with placement(write, ob, 0, 0, -float(h)/2) as center:
            write("cylinder($fn="+f+", h="+h+", r="+r+center+");\n")

    elif ob.TypeId == "Part::Extrusion":
        print("Extrusion")
        print(ob.Base)
        print(ob.Base.Name)
        if ob.Base.isDerivedFrom('Part::Part2DObjectPython') and \
                hasattr(ob.Base, 'Proxy') and hasattr(ob.Base.Proxy, 'TypeId'):
            ptype = ob.Base.Proxy.TypeId
            if ptype == "Polygon":
                f = fstr(ob.Base.FacesNumber)
                r = fstr(ob.Base.Radius)
                h = fstr(ob.Dir[2])
                print("Faces : " + f)
                print("Radius : " + r)
                print("Height : " + h)
                with placement(write, ob, 0, 0, -float(h)/2) as center:
                    write("cylinder($fn="+f+", h="+h+", r="+r+center+");\n")

            elif ptype == "Circle":
                r = fstr(ob.Base.Radius)
                h = fstr(ob.Dir[2])
                print("Radius : " + r)
                print("Height : " + h)
                with placement(write, ob, 0, 0, -float(h)/2) as center:
                    write("cylinder(h="+h+", r="+r+center+");\n")

            elif ptype == "Wire":
                print("Wire extrusion")
                print(ob.Base)
                with placement(write, ob, 0, 0, 0) as center:
                    write("linear_extrude(height="+fstr(ob.Dir[2])+center+", "+convexity+", twist=0, slices=2) {\n")
                    write(vertices_to_polygon(ob.Base.Shape.Vertexes))

            else:
                print(f"Unsupported extrusion base object {ob.Base} of type {ptype}")

        elif ob.Base.isDerivedFrom('Part::Plane'):
            with placement(write, ob, 0, 0, 0) as center:
                write("linear_extrude(height="+fstr(ob.Dir[2])+", center=true, "+convexity+", twist=0, slices=2) {\n")
                write("square(size=["+fstr(ob.Base.Length.Value)+", "+fstr(ob.Base.Width.Value)+"]"+center+");\n}\n")
        elif ob.Base.isDerivedFrom("Part::RegularPolygon"):
            h = fstr(ob.Dir[2])
            with placement(write, ob, 0, 0, -float(h) / 2):
                write("circle($fn=" + fstr(ob.Base.Polygon) + ", r=" + fstr(ob.Base.Circumradius) + ");\n")
        elif ob.Base.Name.startswith('this_is_a_bad_idea'):
            pass
        else:
            print(f"Unsupported extrusion base object {ob.Base} (only supporting Part2DObjectPython subtypes and Plane)")
            pass # TODO: There should be a fallback solution

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
        print("Part::Feature")
        with placement(write, ob, 0, 0, 0):
            write('%s\n' % shape2polyhedron(ob.Shape))

    else:
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
        write(f"$fn = 0;\n$fa = {fa};\n$fs = {fs};\n\n")
        for ob in export_list:
            print(ob)
            print("Name : " + ob.Name)
            print("Type : " + ob.TypeId)
            print("Shape : ")
            print(ob.Shape)
            process_object(write, ob)

    FreeCAD.Console.PrintMessage("successfully exported" + " " + filename)
