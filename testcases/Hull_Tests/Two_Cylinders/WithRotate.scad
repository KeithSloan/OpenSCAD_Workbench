hull() {
  cylinder(d=20, h=16, center=true);
  translate([0,-16,0])
    rotate([0,90,0])
      cylinder(d=20, h=16, center=true);
}
