// =============================================================================
// test_hull_two_cubes.scad
//
// Simplest possible hull: two cubes separated in space.
// Expected: a rectangular prism bridging both cubes.
// =============================================================================

$fn = 24;

hull() {
    cube([10, 10, 10], center = true);
    translate([20, 10, 5]) {
        cube([15, 8, 12], center = true);
    }
}
