include <BOSL2/std.scad>
chain_hull() {
    translate([60, 30, 0]) cylinder(d=10, h=20);
    translate([60, 60, 0]) cube([10,1,20], center=false);
}
