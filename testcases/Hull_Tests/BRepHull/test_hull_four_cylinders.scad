// =============================================================================
// test_hull_four_cylinders.scad
//
// Hull of 4 cylinders in a rectangular pattern.
// Pattern from: gears.scad, lib_actuator_assembly_tools.scad
// Expected: a rounded rectangular prism (Minkowski sum of rectangle + circle).
// =============================================================================

$fn = 32;

hull() {
    for (x = [-15, 15]) {
        for (y = [-10, 10]) {
            translate([x, y, 0]) {
                cylinder(r = 4, h = 10, center = true);
            }
        }
    }
}
