// reproduce_loft.cpp — minimal OCCT reproducer for BRepOffsetAPI_ThruSections.
//
// Two equivalent-topology closed wires (9 edges each: 7 lines + 2 circular
// arcs), near-parallel, different size.  ThruSections (ruled=false, solid=false)
// connects them with the wrong vertex correspondence -> the bridge twists and
// self-intersects.  BRepCheck_Analyzer reports the result valid, yet sewing the
// faces into a solid gives a volume ~9% of the expected hull volume.
//
// Build (OCCT dev environment), e.g.:
//   g++ -std=c++14 reproduce_loft.cpp -o reproduce_loft \
//       -I$CASROOT/include/opencascade -L$CASROOT/lib \
//       -lTKBRep -lTKernel -lTKMath -lTKG3d -lTKGeomBase \
//       -lTKTopAlgo -lTKOffset -lTKPrim -lTKShHealing
// Run from the directory containing wireA.brep / wireB.brep.

#include <BRep_Builder.hxx>
#include <BRepTools.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Shape.hxx>
#include <TopoDS_Wire.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Solid.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepOffsetAPI_ThruSections.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepBuilderAPI_Sewing.hxx>
#include <BRepBuilderAPI_MakeSolid.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <iostream>

static TopoDS_Shape readBrep(const char* path) {
    TopoDS_Shape s;
    BRep_Builder b;
    if (!BRepTools::Read(s, path, b))
        std::cerr << "ERROR: could not read " << path << std::endl;
    return s;
}

int main() {
    TopoDS_Wire wA = TopoDS::Wire(readBrep("wireA.brep"));
    TopoDS_Wire wB = TopoDS::Wire(readBrep("wireB.brep"));

    // solid = Standard_False, ruled = Standard_False  (matches Part.makeLoft(.., False, False, False))
    BRepOffsetAPI_ThruSections gen(Standard_False, Standard_False);
    gen.AddWire(wA);
    gen.AddWire(wB);
    gen.Build();
    if (!gen.IsDone()) { std::cerr << "ThruSections not done\n"; return 1; }
    TopoDS_Shape loft = gen.Shape();

    BRepCheck_Analyzer ana(loft);
    std::cout << "loft: valid = " << (ana.IsValid() ? "true" : "false") << std::endl;

    // Sew the loft faces and make a solid to expose the collapsed volume.
    BRepBuilderAPI_Sewing sew(1.0e-3);
    sew.Add(loft);
    sew.Perform();
    for (TopExp_Explorer ex(sew.SewedShape(), TopAbs_SHELL); ex.More(); ex.Next()) {
        TopoDS_Solid sol = BRepBuilderAPI_MakeSolid(TopoDS::Shell(ex.Current()));
        GProp_GProps props;
        BRepGProp::VolumeProperties(sol, props);
        std::cout << "sewn solid: volume = " << props.Mass()
                  << "  (expected ~15700; twist collapses it to ~1450)" << std::endl;
        break;
    }
    return 0;
}
