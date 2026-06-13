// =============================================================================
// test_hull_mirror_cylinders.scad
//
// Symmetric hull using mirror. Two cylinders mirrored across Y.
// Pattern from: fitting_wedge.scad, m12.scad (reflect_x/reflect_y)
// Expected: hull of two identical cylinders produces a symmetric capsule-like shape.
// =============================================================================

$fn = 32;

hull() {
    mirror([0, 1, 0]) {
        translate([0, 10, 0]) {
            cylinder(r = 4, h = 12, center = true);
        }
    }
}
