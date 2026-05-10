// hull_cyl_cube_test.scad
//
// Test case for: hull(4 cylinders + 1 cube)
// Taken from the pegboard import — the failing hull in the X-aligned frame.
//
// The perpendicular cross-section (YZ plane for X-aligned cylinders) has:
//   - 4 cylinder circles at (y=±12.7, z=4.10175) and (y=±12.7, z=-25.3), r=3.00175
//   - Cube cross-section: y ∈ [-7.775, 7.775], z ∈ [-15, 15]
//
// For easier viewing we display this in a Z-axis-up frame by mapping:
//   Y_perp → X,   Z_perp → Y,   X_axis → Z
//
// So the 4 cylinders become Z-aligned pegs, and the cube is a tall slab.
// The axial extent (X in the original) becomes Z depth of 1.85.

r   = 3.00175;
h   = 1.85;     // axial length of cylinders (X in original frame)

// Cylinder centre positions (in the YZ perpendicular plane → mapped to XY here)
cyl_pos = [
    [-12.7,   4.10175],   // (y=-12.7, z=4.10175) in original
    [ 12.7,   4.10175],
    [-12.7, -25.3    ],
    [ 12.7, -25.3    ],
];

// Cube cross-section in YZ → XY
// y ∈ [-7.775, 7.775], z ∈ [-15, 15], axial depth 1.85 (same as cylinders)
cube_x0 = -7.775;   cube_sx = 15.55;
cube_y0 = -15.0;    cube_sy = 30.0;
cube_z0 =  0.0;     cube_sz =  1.85;  // same axial depth for direct comparison

// --------------------------------------------------------------------------
// Modules
// --------------------------------------------------------------------------

module cylinders() {
    for (p = cyl_pos)
        translate([p[0], p[1], 0])
            cylinder(h=h, r=r, $fn=32);
}

module the_cube() {
    translate([cube_x0, cube_y0, cube_z0])
        cube([cube_sx, cube_sy, cube_sz]);
}

// --------------------------------------------------------------------------
// Show: hull (left) vs union (right)
// --------------------------------------------------------------------------

// Hull — what OpenSCAD produces (correct convex hull)
color("SteelBlue", 0.9)
hull() {
    cylinders();
    the_cube();
}

// Union — what a simple fuse of the shapes would give
translate([50, 0, 0])
color("Tomato", 0.9)
union() {
    cylinders();
    the_cube();
}

// --------------------------------------------------------------------------
// Also show the hull using the FULL cube depth (axial extent of the cube
// is 29.25 mm vs cylinder 1.85 mm — so cube extends far beyond cylinders).
// This reveals the slanted transition faces clearly.
// --------------------------------------------------------------------------

translate([0, -60, 0]) {
    // Cube with full axial extent
    cube_full_sz = 29.25;
    cube_full_z0 = -19.1755;   // cube starts at x=-19.1755 in original

    color("SteelBlue", 0.8)
    hull() {
        cylinders();
        translate([cube_x0, cube_y0, cube_full_z0])
            cube([cube_sx, cube_sy, cube_full_sz]);
    }
}

translate([50, -60, 0]) {
    cube_full_sz = 29.25;
    cube_full_z0 = -19.1755;

    color("Tomato", 0.8)
    union() {
        cylinders();
        translate([cube_x0, cube_y0, cube_full_z0])
            cube([cube_sx, cube_sy, cube_full_sz]);
    }
}
