/******************************************************************
*                                                                 *
* OpenFlexure Microscope: Optics unit                             *
*                                                                 *
* This is part of the OpenFlexure microscope, an open-source      *
* microscope and 3-axis translation stage.  It gets really good   *
* precision over a ~10mm range, by using plastic flexure          *
* mechanisms.                                                     *
*                                                                 *
* (c) Richard Bowman, January 2016                                *
* Released under the CERN Open Hardware License                   *
*                                                                 *
******************************************************************/

use <./libs/utilities.scad>

$fn=32;

module sample_clip(clamp_point, t=2.5, w=6, radius_of_curvature=undef, slope=30){

    default_roc = clamp_point.z/2 + clamp_point.y*sin(slope) - t/2;
    roc = if_undefined_set_default(radius_of_curvature, default_roc);

    //z distance from the contact point to the centre of the curved part
    z_dist = clamp_point.z - roc - t/2;
    //a is the distance from the contact-point cylinder to the
    //centre of the curved part
    a = sqrt(clamp_point.y^2 + z_dist^2);
    //angle through which we must rotate the join between
    angle = acos((roc + t/2) / a) + atan(z_dist/clamp_point.y);


    difference(){
        union(){
            //anchor to stage
            cylinder(r=w/2,h=t);

            translate_z(roc+t){
                rotate_y(90){
                    difference(){
                        cylinder(r=roc+t,h=w,center=true);
                        cylinder(r=roc,h=999,center=true);
                        translate_z(-99){
                            cube([999,999,999]);
                        }
                        translate_z(-99){
                            rotate(angle){
                                cube([999,999,999]);
                            }
                        }
                    }
                }
            }
            sequential_hull(){
                translate_z(roc+t){
                    rotate_y(90){
                        rotate(angle){
                            translate_y(roc+t/2){
                                cylinder(r=t/2,h=w,center=true);
                            }
                        }
                    }
                }
                translate([0,clamp_point.y,clamp_point.z+t/2]){
                    rotate_y(90){
                        cylinder(r=t/2,h=w,center=true);
                    }
                }
                translate([0,clamp_point.y+t,clamp_point.z+t]){
                    rotate_y(90){
                        cylinder(r=t/2,h=w,center=true);
                    }
                }
            }

        }
        cylinder(r=3/2*1.2,h=999,center=true,$fn=16);
    }
}

// TODO make the mini culture plate clips an accessory
//this is for mini culture plates, 39mm outer diameter and 12.4mm high
//sample_clip([0,19/2+3,12.4-1.5],slope=7.5); //mini culture dish

module sample_clips_stl(){
    for(a=[0,180]){
        rotate([0,-90,a]){
            translate([7/2,-10,-7+1]){
                default_sample_clip();
            }
        }
    }
}

// sample clip, upright, with default parameters
module default_sample_clip(){
    sample_clip([0,20,-1], w=7, radius_of_curvature=7);
}

//sample_clips_stl();
default_sample_clip();
