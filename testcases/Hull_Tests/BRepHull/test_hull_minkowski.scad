// =============================================================================
// test_hull_minkowski.scad
//
// Hull between two minkowski-rounded cubes — creates smooth rounded fillets.
// Pattern from: led_array_holder.scad (holder base)
// Expected: a smooth, rounded bridging shape between two rounded cubes.
// =============================================================================

$fn = 32;

hull() {
    minkowski() {
        cube([30, 20, 3], center = true);
        cylinder(r = 2, h = 1, center = true);
    }
    translate([0, 20, 10]) {
        minkowski() {
            cube([16, 12, 12], center = true);
            cylinder(r = 1.5, h = 1, center = true);
        }
    }
}
