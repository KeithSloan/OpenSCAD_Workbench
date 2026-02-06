$fn = 48;

r = 5;
sx = 20;
sy = 15;

hull() {
    translate([0,  0, 0]) sphere(r = r);
    translate([sx, 0, 0]) sphere(r = r);
    translate([0,  sy, 0]) sphere(r = r);
    translate([sx, sy, 0]) sphere(r = r);
}
