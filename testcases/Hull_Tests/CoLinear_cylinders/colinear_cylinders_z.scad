// Simple hull test: 3 cylinders along Z-axis
$fn = 32; // low resolution for testing

hull() {
    // Cylinder 1
    cylinder(h=5, r1=5, r2=5, center=false);

    // Cylinder 2, offset in Z
    translate([0,0,5])
        cylinder(h=8, r1=10, r2=10, center=false);

    // Cylinder 3, further offset
    translate([0,0,13])
        cylinder(h=6, r1=2, r2=2, center=false);
}

