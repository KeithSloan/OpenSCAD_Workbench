//
// test_vars.scad
// Designed to test OpenSCAD_Ext varsSCAD parsing
//

// ----------- Simple scalars -----------
width  = 40;
height = 25;
depth  = 15;

// ----------- Expressions -----------
wall_thickness = 2;
inner_width  = width  - 2 * wall_thickness;
inner_height = height - 2 * wall_thickness;

// ----------- Vectors / arrays -----------
hole_positions = [
    [5, 5],
    [35, 5],
    [5, 20],
    [35, 20]
];

// ----------- Booleans & strings -----------
use_lid   = true;
label_txt = "Demo Box";

// ----------- Conditional expressions -----------
lid_height = use_lid ? 5 : 0;

// ----------- Modules -----------
module box_body(w, h, d) {
    cube([w, h, d]);
}

module lid(w, h, t) {
    translate([0, 0, h])
        cube([w, w, t]);
}

// ----------- Includes / uses -----------
include <stdlib.scad>;
use <MCAD/boxes.scad>;

// ----------- Usage (should NOT be parsed as vars) -----------
box_body(width, height, depth);

if (use_lid)
    lid(width, height, lid_height);

