/******************************************************************
*                                                                 *
* OpenFlexure Microscope: Gears for actuators                     *
*                                                                 *
* This is part of the OpenFlexure microscope, an open-source      *
* microscope and 3-axis translation stage.  It gets really good   *
* precision over a ~10mm range, by using plastic flexure          *
* mechanisms.                                                     *
* This file generates a small gear, for motor control.            *
*                                                                 *
* (c) Richard Bowman, January 2016                                *
* Released under the CERN Open Hardware License                   *
*                                                                 *
******************************************************************/

use <./libs/gears.scad>
use <./libs/utilities.scad>

RATIO = 2;

// printable_large_gears_four(ratio=RATIO);
large_gear(6);

module printable_large_gears_four(ratio=2){
    // Calculate the spacing from the gear pitch radius.
    // Add 4mm of clearance
    spacing_x = large_gear_pitch_radius(ratio) + large_gear_pitch_radius(ratio=2) + 4;
    spacing_y = 2*large_gear_pitch_radius(ratio=2) + 4;
    repeat([0, spacing_y, 0], 2, center=true){
        translate([-spacing_x/2, 0, 0]){
            large_gear(ratio=ratio);
        }
        translate([spacing_x/2, 0, 0]){
            large_gear(ratio=2);
        }
    }
}
