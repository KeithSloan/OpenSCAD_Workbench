/* [cup] */
// inner diameter
d = 40;//.1
r = d/2;
// volume (ml/cm³)
v= 32;//.1
// mm³
vmm = v*1000;
// extra height
hex = 7;//.1
// eliminate negative values
he = max(hex,0);
// wall thickness
wt = 2.4;//.1
// base thickness
bt = 2;//.1
// base bevel
b = 0.9;

/* [spout] */
// create spout - requires extra height
sp = true;
// spout overhang angle
spa = 40; //[5:1:85]
// spout tip inside radius
spr = 0.5;//.1
// spout max width (%)
spwp=25; // [5:2.5:40]

/* [fill mark] */
// size
fms = 0.6;//.1
// intermediate markings - set to 0 for none
fmi = 3;
// size of intermediate markings
fmis = 0.4;
// angle of markings for intermediate markings
fmia = 225;//[10:5:360]

/* [label */
// enable label
lbl = true;
// multicolor label - only leaves a 0.01mm gap of the outline for the color paint tool in the slicer
lblmc = false;

// label depth
lbld = 0.4;//.1
// use custom label text
clbl = false;
// custom text
ctxt= "2 tbsp";
// font
f= "Liberation Sans:style=Bold"; 
// font size
fs = 7;//.1

/* [misc] */
$fa = 1;//.1
$fs =0.1;

 // number, decimals
function rnd(n,d) = round(n*pow(10,d))/pow(10,d);
// height for volume
hv = rnd(vmm/(PI*pow(r,2)),2);
// inner height
hi = hv+he;
// spout width
spw = (spwp/100)*d;

echo(str("total height: ", hi+bt, "mm"));
echo(str("max fill volume approximately ", rnd(r*r*hi*PI/1000,0), "ml"));
module spout(h,w,r,a,ro =r, fms=fms){
    hull(){
        ofs = sqrt(pow(ro,2)-pow(w/2,2))-ro;
        l= tan(90-a)*h;
        f=fms>0? fms/2+0.01:0;
        translate([-r+f,0,0])cylinder(h,r=r);
        translate([l-r,0,h-0.01])cylinder(0.01,r=r);
        translate([ofs,-w/2,h-0.01])cube([0.01,w,0.01]);
    }
    if(fms<0)translate([-r,0,fms])cylinder(h,r=r);
}
module fm(r=r,s=fms, a=360){
    ar = a<360? (360-a)/2:0;
    rotate([0,0,ar])rotate_extrude(angle=a)polygon([[r-s/2,0],[r,-s/2],[r+s/2,0],[r,s/2]]);
}

module shell(r, h, b, hf,sph, spr,spw, fms,fmi=fmi,fmis=fmis,fmia=fmia){
    union(){
        cylinder(b, r1=r-b,r2=r);
        difference(){
            translate([0,0,b])cylinder(h-b,r=r);
            if(fms<0)translate([0,0,hf])fm(r,fms);
            if(fmi>0 && fmis <0){
                s = hf/(fmi+1);
                for(hfmi=[s:s:hf-s/2])translate([0,0,hfmi])fm(r,fmis,fmia);
            }
        }
        if(sp)translate([r,0,h-sph])spout(sph,spw,spr,spa,r,fms);
        if(fms>0)translate([0,0,hf])fm(r,fms);
        if(fmi>0 && fmis >0){
                s = hf/(fmi+1);
                for(hfmi=[s:s:hf-s/2])translate([0,0,hfmi])fm(r,fmis,fmia);
        }
    }
    
}
union(){
    difference(){
        fms2 = fms>0? 0:0;
        rspa = wt/tan(90-spa)+spr;
        shell(r+wt,hi+bt,b,hv+bt,he,rspa,spw+2*wt,fms2,0);
        translate([0,0,bt])shell(r,hi+0.01,0,hv+0.01,he+0.01,spr,spw,fms);
        if (lbl){
            t = clbl? ctxt: str(v,"ml");
            translate([0,0,-0.01])rotate([0,0,90])mirror([0,1,0])linear_extrude(lbld+0.01)text(t,fs,f,halign="center",valign="center");
        }
    }
    if(lbl && lblmc){
        t = clbl? ctxt: str(v,"ml");
        color("green")translate([0,0,-0.01])rotate([0,0,90])mirror([0,1,0])linear_extrude(lbld+0.01)offset(r=-0.01)text(t,fs,f,halign="center",valign="center");
    } 
}