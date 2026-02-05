include <BOSL2/std.scad>
chain_hull() {
    sphere(d=5);
    translate([30, 0, 0]) sphere(d=15);
    translate([60, 30, 0]) sphere(d=7);
    translate([60, 60, 0]) sphere(d=20);
    }
