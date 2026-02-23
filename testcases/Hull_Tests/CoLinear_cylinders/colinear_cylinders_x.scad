$fn = 64;

hull() {
    translate([-20, 0, 0])
        rotate([0, -90, 0])
            cylinder(h=5, r=5);

    translate([0, 0, 0])
        rotate([0, -90, 0])
            cylinder(h=8, r=10);

    translate([25, 0, 0])
        rotate([0, -90, 0])
            cylinder(h=6, r=2);
}

