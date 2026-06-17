// test_mirror_solid.scad
//
// Minimal reproducer for multmatrix REFLECTION (OpenSCAD mirror) handling in the
// importer.  An asymmetric L-shaped solid at +X, plus its mirror across X=0,
// UNIONED together.  Correct result: a symmetric pair of L's (mirror image),
// fully merged.  Failure modes the importer has shown:
//   - reflection dropped  -> both L's land on the +X side (asymmetric/overlap)
//   - reflection inverts solid orientation -> union breaks, parts detached
//
// Also a version using the L as a difference subtrahend, to exercise the
// boolean-orientation path (a mirrored, inside-out solid subtracts wrong).

module Lshape() {
    union() {
        cube([8, 3, 3]);
        cube([3, 8, 3]);
    }
}

// (a) union of an L and its X-mirror — should be symmetric and fully merged
union() {
    translate([5, 0, 0]) Lshape();
    mirror([1, 0, 0]) translate([5, 0, 0]) Lshape();
}

// (b) a block with a mirrored L subtracted from it, shifted clear in Y
translate([0, 20, 0])
difference() {
    translate([-12, -2, -2]) cube([24, 12, 7]);
    mirror([1, 0, 0]) translate([5, 0, 0]) Lshape();
}
