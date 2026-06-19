// reproduce_intersection.cpp — minimal OCCT reproducer for BRepAlgoAPI_Common
// returning an intersection LARGER than an operand.
//
// A.common(B) must satisfy A ∩ B ⊆ A, so Bnd_Box(result) ⊆ Bnd_Box(A).  Here A
// is a ~10 mm part (opA) and B is a 999-scale OpenSCAD clip solid (opB =
// union(cube(999), thin/long cylinders)).  OCC returns a result spanning
// x[-999, 999] — ~80x outside A — while BRepCheck_Analyzer reports it valid.
//
// Build (OCCT dev environment), e.g.:
//   g++ -std=c++14 reproduce_intersection.cpp -o reproduce_intersection \
//       -I$CASROOT/include/opencascade -L$CASROOT/lib \
//       -lTKBRep -lTKernel -lTKMath -lTKG3d -lTKGeomBase \
//       -lTKTopAlgo -lTKBO -lTKShHealing
// Run from the directory containing opA.brep / opB.brep.

#include <BRep_Builder.hxx>
#include <BRepTools.hxx>
#include <TopoDS_Shape.hxx>
#include <BRepAlgoAPI_Common.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <Bnd_Box.hxx>
#include <BRepBndLib.hxx>
#include <iostream>

static TopoDS_Shape readBrep(const char* path) {
    TopoDS_Shape s;
    BRep_Builder b;
    if (!BRepTools::Read(s, path, b))
        std::cerr << "ERROR: could not read " << path << std::endl;
    return s;
}

static void printBox(const char* tag, const TopoDS_Shape& s) {
    Bnd_Box bb;
    BRepBndLib::Add(s, bb);
    Standard_Real xmin, ymin, zmin, xmax, ymax, zmax;
    bb.Get(xmin, ymin, zmin, xmax, ymax, zmax);
    std::cout << tag << " bbox = x[" << xmin << ", " << xmax << "]  y["
              << ymin << ", " << ymax << "]  z[" << zmin << ", " << zmax << "]\n";
}

int main() {
    TopoDS_Shape a = readBrep("opA.brep");
    TopoDS_Shape b = readBrep("opB.brep");
    printBox("opA", a);
    printBox("opB", b);

    BRepAlgoAPI_Common common(a, b);
    common.Build();
    if (!common.IsDone()) { std::cerr << "Common not done\n"; return 1; }
    TopoDS_Shape r = common.Shape();

    BRepCheck_Analyzer ana(r);
    std::cout << "result valid = " << (ana.IsValid() ? "true" : "false") << "\n";
    printBox("A.common(B)", r);
    std::cout << "(expected result bbox to lie within opA's x[-6.04, 12.50]; "
                 "actual x spans ~[-999, 999] -> BUG)\n";
    return 0;
}
