// =============================================================================
// test_sequential_hull.scad
//
// Sequential hull: hulls consecutive pairs of children.
// Pattern from: m12.scad, compact_nut_seat.scad (used extensively in OpenFlexure)
// Expected: a smooth sweep through multiple cross-sections, like a variable
//           extrusion or loft.
// =============================================================================

$fn = 32;

module sequential_hull() {
    for (i = [0 : $children - 2]) {
        hull() {
            children(i);
            children(i + 1);
        }
    }
}

// Sweep: circle → square → circle → small circle
sequential_hull() {
    translate([0, 0, 0])  cylinder(r = 6, h = 1, center = true);
    translate([0, 0, 8])  cube([8, 8, 1], center = true);
    translate([5, 0, 16]) cylinder(r = 7, h = 1, center = true);
    translate([5, 0, 24]) cylinder(r = 3, h = 1, center = true);
}
