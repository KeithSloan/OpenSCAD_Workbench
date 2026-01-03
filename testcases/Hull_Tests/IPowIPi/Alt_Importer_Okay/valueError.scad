//OpenSCAD script:

roundness = 5;
round_corners = true; // can be imported in FreeCAD when this is false, an error is thrown during import when true

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

hull() {
sphereRect(50, 50);
translate([0, 0, 50])
sphereRect(50, 50);
}
