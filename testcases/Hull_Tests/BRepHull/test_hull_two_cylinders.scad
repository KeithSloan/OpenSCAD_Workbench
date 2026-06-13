// =============================================================================
// test_hull_two_cylinders.scad
//
// Two cylinders at different positions and radii.
// Pattern from: gears.scad (thumbwheel_lobe)
// Expected: a truncated cone / frustum bridging both cylinder ends.
// =============================================================================

$fn = 32;

hull() {
    cylinder(r = 5, h = 10);
    translate([15, 5, -3]) {
        cylinder(r = 8, h = 6);
    }
}
