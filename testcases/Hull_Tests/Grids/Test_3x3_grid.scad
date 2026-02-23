// Box grid of spheres
// 3 × 3 × 3 grid

$fn = 48;

spacing = 20;
r = 6;

for (x = [-1, 0, 1])
for (y = [-1, 0, 1])
for (z = [-1, 0, 1]) {
    translate([x * spacing, y * spacing, z * spacing])
        sphere(r = r);
}
