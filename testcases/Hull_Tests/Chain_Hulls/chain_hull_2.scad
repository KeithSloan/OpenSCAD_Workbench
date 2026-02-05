include <BOSL2/std.scad>
chain_hull() {
    translate([30, 0, 0]) sphere(d=15);
    translate([60, 30, 0]) cylinder(d=10, h=20);
}
