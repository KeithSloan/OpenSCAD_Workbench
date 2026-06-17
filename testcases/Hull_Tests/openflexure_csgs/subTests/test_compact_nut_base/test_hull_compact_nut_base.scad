// test_hull_compact_nut_base.scad
//
// Isolated "base" of compact_nut_seat: just the FIRST hull — the hull of the
// two concentric, coaxial extruded prisms (everything else in the model is
// stripped out).  Use this to iterate on the smooth concentric-hull path
// without the later cube/cylinder hulls running on top.
//
// Profile is the ORIGINAL one (taken verbatim from compact_nut_seat_fn0.csg):
// union(circle@+6.036, circle@-6.036, square) — a square with a true circular
// bulge on each side.  Both circles are $fn=0 so the importer builds them as
// TRUE circles (matching topology between wide and narrow → the piecewise
// bridge pairs them and the hull stays smooth).
//   wide  : square 12.0717 x 16.1288, circles r=8.06439, extrude h=51
//   narrow: square 12.0717 x 12.1288, circles r=6.06439, extrude h=54
//
// NB: test_hull_compact_nut_base.csg in this folder is extracted byte-for-byte
// from the original CSG — import that one directly for an exact repro.

$fn = 0;   // true circles -> smooth (non-faceted) hull path

hull() {
    // wide + short
    linear_extrude(height = 51, center = true)
        union() {
            translate([ 6.03586, 0]) circle(r = 8.06439);
            translate([-6.03586, 0]) circle(r = 8.06439);
            square([12.0717, 16.1288], center = true);
        }

    // narrow + tall
    linear_extrude(height = 54, center = true)
        union() {
            translate([ 6.03586, 0]) circle(r = 6.06439);
            translate([-6.03586, 0]) circle(r = 6.06439);
            square([12.0717, 12.1288], center = true);
        }
}
