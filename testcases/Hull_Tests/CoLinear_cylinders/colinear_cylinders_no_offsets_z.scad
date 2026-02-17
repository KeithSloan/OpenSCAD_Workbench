// Simple hull test: 3 cylinders along Z-axis
$fn = 32; // low resolution for testing

hull() {
    // Cylinder 1
    cylinder(h=5, r1=15, r2=15, center=false);

    // Cylinder 2, offset in Z
        cylinder(h=10, r1=12, r2=12, center=false);

    // Cylinder 3, further offset
        cylinder(h=15, r1=2, r2=2, center=false);
}

