
x1y1z = [20, 20, 10];
x2y2  = [10, 10];
r = 2;

top_rounded_block(x1y1z, x2y2, r);


module top_rounded_block(x1y1z,x2y2,r) {
	translate([-x1y1z[0]/2,-x1y1z[1]/2,0]) {
		hull() {
			translate([r,r,0]) cylinder(0.001,r,0);
			translate([x1y1z[0]-r,r,0]) cylinder(0.001,r,0);
			translate([r,x1y1z[1]-r,0]) cylinder(0.001,r,0);
			translate([x1y1z[0]-r,x1y1z[1]-r,0]) cylinder(0.001,r,0);
			
			translate([
				r+((x1y1z[0]-x2y2[0])/2),
				r+((x1y1z[1]-x2y2[1])/2),
				x1y1z[2]-r
			]) sphere(r);
			
			translate([
				x1y1z[0]-r-((x1y1z[0]-x2y2[0])/2),
				r+((x1y1z[1]-x2y2[1])/2),
				x1y1z[2]-r
			]) sphere(r);
			
			translate([
				r+((x1y1z[0]-x2y2[0])/2),
				x1y1z[1]-r-((x1y1z[1]-x2y2[1])/2),
				x1y1z[2]-r
			]) sphere(r);
			
			translate([
				x1y1z[0]-r-((x1y1z[0]-x2y2[0])/2),
				x1y1z[1]-r-((x1y1z[1]-x2y2[1])/2),
				x1y1z[2]-r
			]) sphere(r);
		}
	}
}