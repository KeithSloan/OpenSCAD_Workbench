$fn = 64;

hull() {
    translate([-20, 0, 0])
        sphere(r = 5);

    translate([0, 0, 0])
        sphere(r = 10);

    translate([25, 0, 0])
        sphere(r = 7);
}
