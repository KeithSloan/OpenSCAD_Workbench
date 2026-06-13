// =============================================================================
// test_hull_difference.scad
//
// Hull inside a difference: hull a shape then subtract cutouts.
// Pattern from: led_array_holder.scad, m12.scad, many others.
// Expected: a hulled mounting block with screw holes and wire cutout removed.
// =============================================================================

$fn = 32;

difference() {
    // Hull the LED array base to the dovetail block
    hull() {
        // Bottom plate (LED array)
        translate([0, 0, 2]) {
            cube([36, 26, 4], center = true);
        }
        // Dovetail block (simplified)
        translate([0, 15, 8]) {
            cube([20, 16, 15], center = true);
        }
    }

    // Wire/heat hole through the center
    translate([0, 0, -1]) {
        cylinder(r = 6, h = 30);
    }

    // Two mounting screw holes
    for (x = [-10, 10]) {
        for (y = [-8, 8]) {
            translate([x, y, -5]) {
                cylinder(r = 1.25, h = 30);
            }
        }
    }
}
