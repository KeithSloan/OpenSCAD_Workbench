width_bottom = 40;
height_bottom = 40;
width_top = 30;
height_top = 30;
border_width = 3;
border_height = 3;
roundness = 15;
length = 1000;
num_pipes = 4;
wall_thickness = 10;
round_corners = true;

full_width_bottom = width_bottom * num_pipes + wall_thickness * (num_pipes + 1);
full_width_top = width_top * num_pipes + wall_thickness * (num_pipes + 1);
full_height_bottom = height_bottom + wall_thickness + border_height;
full_height_top = height_top + wall_thickness + border_height;

module rect(width, height) {
    translate([-width / 2, -height / 2])
            cube([width, height, 1]);
}

module sphereRect(width, height) {
    if(round_corners) {
        translate([-width / 2 + roundness, -height / 2 + roundness])
            sphere(roundness);
        translate([width / 2 - roundness, -height / 2 + roundness])
            sphere(roundness);
        translate([width / 2 - roundness, height / 2 - roundness])
            sphere(roundness);
        translate([-width / 2 + roundness, height / 2 - roundness])
            sphere(roundness); 
    } else {
        rect(width, height);
    }
}

module pipeCarving(index) {
    // pipe
    hull() {
        rotate([90, 0, 90]) {
            translate([-full_width_bottom / 2 + wall_thickness + width_bottom / 2 + (width_bottom + wall_thickness) * index, (wall_thickness - border_height) / 2, -roundness * 2 - 1])
                sphereRect(width_bottom, height_bottom);
            translate([(-full_width_top / 2 + wall_thickness + width_top / 2 + (width_top + wall_thickness) * index), (wall_thickness - border_height) / 2, length - wall_thickness])
                sphereRect(width_top, height_top);
        }
    }
    // border
    hull() {
        rotate([90, 0, 90]) {
            translate([-full_width_bottom / 2 + wall_thickness - border_width + (width_bottom + border_width * 2) / 2 + (width_bottom + wall_thickness) * index, full_height_bottom / 2, -roundness * 2 - 1])
                rect(width_bottom + 2 * border_width, 2 * border_height + 1);
            translate([(-full_width_top / 2 + wall_thickness - border_width + (width_top + border_width * 2) / 2 + (width_top + wall_thickness) * index), full_height_top / 2, length - wall_thickness + border_width])
                rect(width_top + 2 * border_width, 2 * border_height + 1);
        }
    }
}


module body() {
    hull() {
        rotate([90, 0, 90]) {
            sphereRect(full_width_bottom, full_height_bottom);
            translate([0, 0, length])
                sphereRect(full_width_top, full_height_top);
        }
    }
}

difference() {
    body();

    for(i = [0 : num_pipes - 1])
        pipeCarving(i);
}


