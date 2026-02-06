include <BOSL2/std.scad>
chain_hull() {
    cube(5, center=true);
    translate([30, 0, 0]) sphere(d=15);
    translate([60, 30, 0]) cylinder(d=10, h=20);
    translate([60, 60, 0]) cube([10,1,20], center=false);
}
