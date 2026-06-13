// =============================================================================
// test_hull_cone_to_cylinder.scad
//
// Hull between a cone (tapered cylinder) and a regular cylinder.
// Pattern from: compact_nut_seat.scad, illumination.scad
// Expected: convex hull of dissimilar curved primitives with different radii.
// =============================================================================

$fn = 32;

hull() {
    cylinder(r1 = 6, r2 = 3, h = 8, center = true);
    translate([14, 5, -4]) {
        cylinder(r = 7, h = 5);
    }
}
