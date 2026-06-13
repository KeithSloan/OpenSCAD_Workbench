// =============================================================================
// test_hull_linear_extrude.scad
//
// Hull between a 2D linear_extrude and a 3D primitive.
// Pattern from: gears.scad (large gear to small gear flange)
// Expected: convex hull bridging an extruded 2D shape and a cylinder.
// =============================================================================

$fn = 32;

hull() {
    // A rounded rectangular plate (extruded 2D shape)
    linear_extrude(height = 3) {
        offset(1.5) {
            square([20, 12], center = true);
        }
    }

    // A cylinder offset above
    translate([10, 8, 6]) {
        cylinder(r = 5, h = 4);
    }
}
