/* [dimenstions] */
// inner diameter of opening
d = 75;//.1
// type of second dimension
m2 = 0;//[0:"top diameter", 1:"height"]
// second dimension
d2 = 5;//.1
// volume in cm³/ml
v= 95;//.1

/* [shell] */
// wall thickness at the opening
wtb = 2.4;//.1
// wall thickness at the top
wtt = 1.6;//.1
// round tip
rounded_tip = true;

/* [handle] */
// length of the handle
hl = 50;//.1
// transition length of cup dia to handle width - part of hl
htl = 20;//.1
// handle width
hw = 35;//.1
// handle heigh
hh = 5;//.1
// hole at the handle end
handle_hole = true;
// diameter of handle hole
hho = 7.5;//.1
hhr = hho/2;

// bevel on hole
hhob = 0.9;
// round over the vertical handle surface - adds additional width
handle_rounded = true;
// rounding in % of handle height, bigger percentage is a smaller calculated radius 
hrp = 7.5; // [2.5:2.5:100]

/* [label */
// enable label
lbl = true;
// multicolor label - only leaves a 0.01mm gap of the outline for the color paint tool in the slicer
lblmc = false;
// label depth
lbld = 0.4;
// use custom label text
clbl = false;
// custom text
ctxt= "2 tbsp";
// font
f= "Liberation Sans:style=Bold"; 
// font size
fs = 10;//.1
// lbl ofs
lofs = 2;//.1

/* [misc] */
$fa = 1;
$fs = 0.1;


// conversion from cm³ in mm³
vmm = v*1000;
// height of inner cone
h = m2==1? d2: rnd((vmm*3)/((pow(d/2,2)+pow(d2/2,2)+d2/2*d/2)*PI),2);
// radius on top
r = d/2;

r2 = m2==0? d2/2: rnd((-r+sqrt(pow(r,2)-4*(pow(r,2)-(3*vmm)/(PI*h))))/2,2);
vc = rnd((h*PI/3*(pow(r,2)+pow(r2,2)+r*r2))/1000,3);

function cone_angle(r1,r2,h)= atan(h/(r1-r2));
function r_side (l,h2) = h2 / cos(atan(h2/l) -atan(l/h2));
function r_top (a, rt)= rt/sin(a); 
function rnd(n,d=1) = round(n*pow(10,d))/pow(10,d);


echo(str("diameter of opening: ",d, "mm"));
echo(str("diameter at the top: ",r2 *2, "mm"));
echo(str("internal height of opening: ",h, "mm"));
echo(str("sanity check Volume recalculated: ", vc, "m"));
e = (1-vc/v)*100;
if (e< 0.01&&e>-0.01){
    echo(str("calculation error: <", 0.01, "%"));
} else echo(str("calculation error: ", e, "%"));
if (rt > r) echo("warning: Diameter on top larger than the bottom");
lrs = (hh/2)*hrp/100;
rs = r_side(lrs, hh/2);
rb = r+wtb;
rt = r2+wtt;
hc = rounded_tip? h+wtt: h+wtt;

do = max(rb,rt)*2;
l = do/2+rb + hl+hw/2;

// profile rounding on sides
module side_rounding(h=hh,l=lrs, r=rs){
    intersection(){
        square([l,h]);
        translate([-r+l,h/2])circle(r);
    }
}


ao = cone_angle(rb,rt,hc);
rtip = r_top(ao,rt);
rofs = hc-cos(ao)*rtip;
ai = cone_angle(r,r2,h);
ht = rounded_tip? rnd(rtip+rofs,2): h+wtt;

if (handle_rounded){
    lt = rt> rb+lrs? l+lrs:l+2*lrs;
    dt = rt> rb+lrs? do: 2*(rb+lrs);
    echo(str("length: ", rnd(lt,2), "mm"));
    echo(str("width: ", rnd(dt,2), "mm"));
    echo(str("handle width: ", rnd(hw+2*lrs,2), "mm"));

} else{
    echo(str("length: ", l, "mm"));
    echo(str("width: ", do, "mm"));
}
echo(str("total height: ", rnd(ht,h), "mm"));

echo(str("internal overhang angle: ", rnd(90-ai), "°"));
echo(str("external overhang angle: ", rnd(90-ao), "°"));

// cube with bevels and optional rounding
module hCube(l,w,h,c=0,rv=handle_rounded){
    translate([l,-w/2,0])rotate([0,-90,0])linear_extrude(l){
        polygon([[c,0],[h-c,0],[h,c],[h,w-c],[h-c,w],[c,w],[0,w-c],[0,c]]);
        if(rv){
            translate([c,0])rotate([0,0,-90])side_rounding();
            translate([h-c,w])rotate([0,0,90])side_rounding();
        }
    }
}
// cylinder with bevels and optional rounding
module hCylinder(h,ra,c=0,rv=handle_rounded){
    rotate_extrude(){
        polygon([[0,0],[ra-c,0],[ra,c],[ra,h-c],[ra-c,h],[0,h]]);
        if(rv)translate([ra,c])side_rounding();
    }
}    
union(){
    difference(){
        union(){
            // cone
            cylinder(hc, r1=rb, r2=rt);
            // round tip
            if(rounded_tip)translate([0,0,rofs])sphere(rtip);
            
            hull(){
                hCylinder(hh,rb);
                translate([rb+htl,0,0])hCube(0.01,hw,hh);
            }
            hull(){
                translate([rb+hl,0,0 ])hCylinder(hh,hw/2);
                translate([rb+htl,0,0])hCube(0.01,hw,hh);
            }
        }
        // inner cone
        cylinder(h, r1=r, r2=r2);
        translate([0,0,-0.01])cylinder(0.02,r=r);
        // handle hole
        
        if(handle_hole)translate([rb+hl,0,0 ])rotate_extrude()polygon([[0,-0.01],[hhr+hhob+0.01,-0.01],[hhr,hhob],[hhr,hh-hhob],[hhr+hhob+0.01,hh+0.01],[0,hh+0.01]]);
        if (lbl){
            t = clbl? ctxt: str(v,"ml");
            translate([rb+lofs,0,-0.01])mirror([0,1,0])linear_extrude(lbld+0.01)text(t,fs,f,halign="left",valign="center");
        }
    }
    if(lbl && lblmc){
        t = clbl? ctxt: str(v,"ml");
        color("green")translate([rb+lofs,0,-0.01])mirror([0,1,0])linear_extrude(lbld+0.01)offset(r=-0.01)text(t,fs,f,halign="left",valign="center");
    } 
}