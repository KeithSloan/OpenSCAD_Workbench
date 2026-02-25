// Test: Colinear cylinders along Z-axis
$fn = 32; // low resolution for testing

hull() {
    // Cylinder 1: height 5, radius 5
    cylinder(h = 5, r1 = 5, r2 = 5, center = false);

    // Cylinder 2: height 8, radius 10, offset in Z
    translate([0, 0, 5])
        cylinder(h = 8, r1 = 10, r2 = 10, center = false);

    // Cylinder 3: height 6, radius 2, further offset in Z
    translate([0, 0, 13])
        cylinder(h = 6, r1 = 2, r2 = 2, center = false);
}

