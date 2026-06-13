// =============================================================================
// test_hull_cube_sphere.scad
//
// Mixed flat + curved: cube and sphere.
// Pattern from: various OpenFlexure illumination mounts.
// Expected: convex hull bridging flat cube faces and spherical surface.
// =============================================================================

$fn = 32;

hull() {
    cube([12, 12, 8], center = true);
    translate([18, 4, 0]) {
        sphere(r = 6);
    }
}
