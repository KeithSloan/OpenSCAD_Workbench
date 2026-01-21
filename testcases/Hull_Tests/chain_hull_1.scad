include <BOSL2/std.scad>
chain_hull() {
    cube(5, center=true);
    translate([30, 0, 0]) sphere(d=15);
}
