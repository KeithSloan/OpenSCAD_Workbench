/******************************************************************
*                                                                 *
* OpenFlexure Microscope: Microscope Parameters                   *
*                                                                 *
* This is the top-level configuration file for the OpenFlexure    *
* microscope, an open microscope and 3-axis translation stage.    *
* It gets really good precision over a ~10mm range, by using      *
* plastic flexure mechanisms.                                     *
*                                                                 *
* Generally I've tried to put parts (or collections of closely    *
* related parts) in their own files.  However, all the parts      *
* depend on the geometry of the microscope - so these parameters  *
* are gathered together here.  In general, the ones you might     *
* to change are towards the top!  Lower-down ones are defined in  *
* terms of higher-up ones - confusion might arise if you redefine *
* these later...                                                  *
*                                                                 *
* (c) Richard Bowman, January 2016                                *
* Released under the CERN Open Hardware License                   *
*                                                                 *
* http://www.github.com/rwb27/openflexure_microscope              *
* http://www.docubricks.com/projects/openflexure-microscope       *
* http://www.waterscope.org                                       *
*                                                                 *
******************************************************************/

use <./libdict.scad>

/**
* Sets the basic geometry of the default microscope
* Stages can be built with modified parameters but with **no guarantee** that any other
* set of parameters will work.
* These parameters define the default size for the structural elements of the micoroscope, optics parameters are set separately.
*/
function default_params() = [["leg_r", 30],     // radius on which the innermost part of legs sit. (This sets the stage size)
                             ["sample_z", 75 ], // z position of sample
                             ["stage_t", 15],   //thickness of the XY stage (at thickest point, most is 1mm less)
                             ["leg_block_t", 5], // Thickness of the block at the top and bottom of the leg
                             ["stage_hole_r", 20], // size of hole in the stage
                             ["xy_lever_ratio", 4.0/7.0], // mechanical advantage of actuator over xy-stage - can be used to trade speed and precision
                             ["z_lever_ratio", 1.0], //  mechanical advantage of actuator over objective mount (must be >1)
                             ["print_ties", true], //sets whether the ties that support printing are on. It is usefull to be able to turn these off for rendering
                             ["smart_brim_r", 5], // The radius of the smart brim on the main body
                             ["actuator_h", 25], //height of the actuator columns
                             ["include_motor_lugs", true], //sets whether the motor lugs are included
                             ["foot_height", 15], //the height of the feet
                            ];

////// 3D printing specific paramenters //////

/**
* The minimum recomended size in z of a feature. This is approximatly 2-3 layers when printed
*/
function min_z_feature() = 0.5;


////// Structural parameters //////

/**
* Height of the top of the leg.
* Shorter than sample_z so that you can get nuts into the stage nut traps,
* and so the slide doesn't crash into the legs.
*/
function leg_height(params) = let(
    sample_z = key_lookup("sample_z", params),
    stage_t = key_lookup("stage_t", params),
    leg_block_t = key_lookup("leg_block_t", params)
) sample_z - stage_t + leg_block_t;

/**
* The distance holes on the XY stage are inset from leg_r (the radius on which the legs sit)
*/
function stage_hole_inset() = flex_dims().y+4;

/**
* Width of the middle part of each leg
*/
function leg_middle_w() = 12;

/**
* Vertical spacing between the hoziontal links on each leg
*/
function leg_link_spacing() = 10;

/**
* Thickness of the base of the main body
*/
function microscope_base_t() = 1;

/**
* Position of the x actuator
*/
function x_actuator_pos(params) = let(
    leg_r = key_lookup("leg_r", params),
    radial_distance = leg_r+actuating_nut_r(params)
) [1, 1, 0]*radial_distance/sqrt(2);

/**
* Position of the y actuator
*/
function y_actuator_pos(params) = let(
    x_pos = x_actuator_pos(params)
) [-x_pos.x, x_pos.y, x_pos.z];

/**
* Position of the z actuator
*/
function z_actuator_pos(params) = [0, z_nut_y(params), 0];

////// Flexure parameters //////
/**
* The dimensions of the flexures for the main body
* These dimensions are well tested with PLA.
*/
function flex_dims() = let
(
    // width  of flexures
    flex_w = 4,
    // length of flexures
    flex_l = 1.5,
    // thickness  of flexures
    flex_t = 0.75
)  [flex_w, flex_l, flex_t];

/**
* Sine of the angle through which flexures can be bent
* This is 0.15 corresponding to 8.62 degrees
*/
function flex_a() = 0.15;


/**
* z position of lower flexures for XY axis
*/
function lower_xy_flex_z() = 0;

/**
* z position of upper flexures for XY axis
*/
function upper_xy_flex_z(params) = leg_height(params) - key_lookup("leg_block_t", params);

/**
* Dimensions of the thin vertical legs that support the stage
*/
function leg_dims(params) = let(
    height = upper_xy_flex_z(params)+flex_dims().z
) [4, flex_dims().x, height];

/**
* Overall width of a pair of legs (parallelogram linkage) that support the stage
*/
function leg_outer_w(params) = leg_middle_w() + 2*flex_dims().y + 2*leg_dims(params).x;

/**
* The radius upon which the x and y actuating nut sits in the frame of reference of the leg
* The total distance from the centre of the microscope to the x and y actuating nuts is then
* calculated as `leg_r + actuating_nut_r(params)` where `leg_r` is set in the
* parameters dictionary
*
* This is also the length of actuating lever for x and y.
* It is calculated from the diference in distance between flexures
* at top and bottom of leg, multiplied by the lever ratio.
*/
function actuating_nut_r(params) = let(
    xy_lever_ratio = key_lookup("xy_lever_ratio", params)
) (upper_xy_flex_z(params) - lower_xy_flex_z()) * xy_lever_ratio;



/**
* distance moved by XY axis actuators
*/
function xy_actuator_travel(params) = actuating_nut_r(params)*flex_a();


////// Z axis parameters. Many are defined here to avoid cyclic imports //////


/**
* Length of struts supporting Z carriage.
*/
function z_strut_l() = 18;

/**
* y position of the optics mounting wedge
*/
function objective_mount_y() = 18;

/**
* width of the pointy end of the mount
*/
function objective_mount_nose_w() = 6;

/**
* height of the lower flexure on z actuator
*/
function lower_z_flex_z() = 8;

/**
* height of the upper flexure on z actuator
*/
function upper_z_flex_z(params) = min(leg_height(params) - 12, 35);

/**
* y position of the back of the objective mount
*/
function objective_mount_back_y() = objective_mount_y() + 2;

/**
* y position of the fixed end of the flexure-hinged lever that actuates the Z axis
*/
function z_anchor_y() = objective_mount_back_y() + z_strut_l() + 2*flex_dims().y;

/**
* Width of the fixed structure where that joints to the z-axis flexures
*/
function z_anchor_w() = 20;

/**
* The length of the actuating lever for the z_axis
* 
* This is calculated from the desired lever ratio and the length
* the struts that form the parallelogram linkage for the z-axis.
* The flexure length is added to the strut length under the approximation
* that the flexures act like a hinge located in the middle of the flexure.
*/
function z_lever_length(params) = let(
    z_lever_ratio = key_lookup("z_lever_ratio", params)
) (z_strut_l() + flex_dims().y)*z_lever_ratio;

/**
* The y position of the z-actuator nut.
*/
function z_nut_y(params) = let(
    // Note that the lever is tilted so we need to find the y projection
    // from the z lever length and the z position of the bottom z flexure
    lev_len_sq = pow(z_lever_length(params), 2),
    bot_z_flex_z_sq = pow(lower_z_flex_z(), 2),
    z_lever_y_proj = sqrt(lev_len_sq - bot_z_flex_z_sq)
) z_anchor_y() - flex_dims().y/2 + z_lever_y_proj;


/**
* distance moved by z axis
*/
function z_actuator_travel(params) = z_lever_length(params)*flex_a();

/**
* The angle (in degrees) through which the z_actuator is tilted
*/
function z_actuator_tilt(params) = -asin(lower_z_flex_z()/z_lever_length(params));


////// Motor parameters. //////

/**
* Approximate size of the connector for the 28BYJ-48 stepper motors
*/
function motor_connector_size() = [5.5, 14.5, 8];

/**
* Height of the printed lug on which the motors are mounted
*/
function motor_lug_h() = 11;

/**
* height(tickness) of the lug/bracket on the motor itself
*/
function motor_bracket_h() = 0.8;

/**
* Motor shaft position relative to the x-z poistion of the actuating nut.
* h is the actuator height plus the travel for the axis.
*/
function motor_shaft_pos(h) = [0,-20,h+2];

/**
* Distance between the screws that attach the motor to the microscope
*/
function motor_screw_separation() = 35;

/**
* Position of the motor screws in the same frame of reference as motor_shaft_pos
*/
function motor_screw_pos(h) = let(
    shaft_pos = motor_shaft_pos(h)
) [motor_screw_separation()/2,shaft_pos.y+7.8,shaft_pos.z+motor_lug_h()];

/**
* The z-position (height) of the y-motor
*/
function y_motor_z_pos(params) = let(
    actuator_h = key_lookup("actuator_h", params)
) motor_screw_pos(actuator_h+xy_actuator_travel(params)).z;

/**
* The z-position (height) of the z-motor
* Note this is not a true z position as it is the position along the tilted axis
*/
function z_motor_z_pos(params) = let(
    actuator_h = key_lookup("actuator_h", params)
) motor_screw_pos(actuator_h+z_actuator_travel(params)).z;


////// Microscope mounting lug parameters //////

/**
* The distance that the back of the microscope mounting lugs is offset from the
* centre of the hole in the lug
*/
function lug_back_offset() = [-5, -8, 0];

/**
* Sets the position of the back lugs (These are the lugs by the legs)
* The front lugs are set by the position of the actuator housing.
* To get all holes see base_mounting_holes in microscope_structure.scad
*/
function back_lug_x_pos(params) = let(
    leg_r = key_lookup("leg_r", params),
    fifth_of_radius = max(5,leg_r*0.2),
    // Compatibility factor added as earlier versions were calculated
    // from an errant calculation that included 1/10th of flex_dims().z
    // this factor ensures perfect compatibility with v7-beta versions
    // already in the field.
    compatibility_factor = .075
) (leg_r-flex_dims().y-fifth_of_radius-compatibility_factor)*sqrt(2);

/**
* The angle which the four lugs face in the order that the hole positions
* are listed in base_mounting_holes in microscope_structure.scad.
*/
function lug_angles(params) = let(
    xy_cable_tidies = key_lookup("include_motor_lugs",params)
) xy_cable_tidies? [-120, 120, 50, -50] : [-120, 120, 105, -105] ;

/**
* Height of walls between the actuators
*/
function actuator_wall_h() = 15;

/**
* Thickness of the walls on the main body
* The wall where the reflection illumination cut-out is has double thickness
*/
function microscope_wall_t() = 2;

/**
* Height of walls inside xy_stage
*/
function inner_wall_h(params) = upper_z_flex_z(params) - 10;

/**
* Height of the cutout in the main body wall for the reflection optics
*/
function reflection_cutout_height() = 16;
