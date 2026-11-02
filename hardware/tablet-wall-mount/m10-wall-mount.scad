// Sliding wall mount for the Lenovo Tab M10 HD (2nd Gen, TB-X306F), landscape,
// with a side housing for a 90-degree USB-C plug.
//
// Inspired by Kreato 3D's "Lenovo Tab M10 HD 2 Gen wall mount" (cults3d):
// a holder that the tablet snaps into, sliding sideways onto a plate that is
// screwed to the wall and held home by magnets. Redrawn from scratch.
//
// Two parts:  PART = "holder"  - tablet snaps into it (print back-down)
//             PART = "plate"   - screws to the wall (print back-down)
//             PART = "assembly"- both, for checking fit (don't print)
//
// Coordinates (front view): X right, Y up, Z out of the wall.
// The USB-C port is assumed on the RIGHT short edge (set PORT_RIGHT=false to
// mirror the whole design so the port is on the left).

PART = "assembly";
PORT_RIGHT = true;

/* ---- Tablet ---- */
tab_w = 241.54;      // long side
tab_h = 149.38;      // short side
tab_t = 8.25;        // thickness
tab_r = 9;           // corner radius (plan view)
clr   = 0.3;         // clearance tablet <-> holder, each side

/* ---- Holder ---- */
wall   = 2.2;        // side wall thickness
back_t = 3.0;        // back thickness (raise to 4 if you use 3 mm magnets)
lip    = 2.0;        // how far the front lip covers the bezel (45 deg chamfer)
lip_drop = 1.0;      // chamfer starts this far below the tablet's front face
                     // (the tablet's front edge is rounded)

/* ---- 90 deg USB-C plug housing (on the port side) ---- */
plug_depth = 15;     // room from tablet edge outwards for the plug head
plug_len   = 60;     // room along the edge (plug head + cable bend, up or down)
cover_t    = 1.6;    // front cover of the housing
cable_d    = 5.5;    // cable exit notch width
exit_top    = true;  // cable exit notch in top of housing
exit_bottom = true;  // cable exit notch in bottom of housing

/* ---- Other edge cut-outs (tablet edge positions, from the centre line) ---- */
speaker_from = 33;   // speaker grilles on both short edges, |y| range
speaker_to   = 58;
jack_y       = 15;   // 3.5 mm jack on the non-port short edge (+/- y, both cut)
jack_w       = 9;
// Power/volume buttons: on the TOP long edge, near the non-port end
// (portrait right edge). Distance from the non-port end of the tablet:
btn_from = 18;
btn_to   = 80;
btn_cut  = true;

/* ---- Slide / plate ---- */
plate_w    = 200;    // plate length along X (rails length)
plate_t    = 4;      // plate base thickness
dt         = 3;      // dovetail size (flange 3 mm out, 3 mm tall, 45 deg)
dt_clr     = 0.3;    // dovetail clearance
rail_w     = 2.5;    // rail wall thickness outside the dovetail
stop_len   = 6;      // end stop at the port end of the rails
screw_d    = 4.5;    // screw clearance
screw_head = 9;      // countersink diameter
screws = [[-85,50],[-85,-50],[85,50],[85,-50],[0,60],[0,-60]];

/* ---- Magnets (12 x 2..3 mm discs) ---- */
mag_d = 12.3;        // pocket diameter (12 mm magnet + clearance)
mag_t = 2;           // magnet thickness
mag_xy = [[-85,0],[85,0]];

$fn = 64;
e = 0.01;

/* ---- Derived ---- */
Wi = tab_w + 2*clr;  Hi = tab_h + 2*clr;  ri = tab_r + clr;
Wo = Wi + 2*wall;    Ho = Hi + 2*wall;    ro = ri + wall;
cav_top = back_t + tab_t + clr;           // top of full-size cavity
lip_z0  = cav_top - lip_drop;
H_tot   = lip_z0 + lip;                   // holder height
port_z  = back_t + tab_t/2;
hs_x0   = Wi/2;                           // housing interior starts at tablet edge
hs_x1   = Wi/2 + clr + plug_depth;        // housing interior end
hs_y    = plug_len/2;
hs_out  = hs_x1 + wall;
flange_x0 = -plate_w/2;
flange_x1 =  plate_w/2 - stop_len - dt_clr;
plate_h   = Ho + 2*(dt + dt_clr + rail_w);

module rrect(w, h, r) {
    r2 = max(r, 0.01);
    hull() for (sx=[-1,1], sy=[-1,1])
        translate([sx*(w/2-r2), sy*(h/2-r2)]) circle(r=r2);
}
module slab(w, h, r, z, t=e) translate([0,0,z]) linear_extrude(t) rrect(w,h,r);
module box(x0,x1,y0,y1,z0,z1) translate([x0,y0,z0]) cube([x1-x0,y1-y0,z1-z0]);

// Dovetail flange on the holder: triangle, 'dt' out at z=0, 0 at z=dt.
module flange_prism(x0, x1, y_edge, s) {   // s=+1 top edge, -1 bottom edge
    translate([x0,0,0]) rotate([90,0,90]) linear_extrude(x1-x0)
        polygon([[y_edge - s*1, 0], [y_edge + s*dt, 0], [y_edge, dt], [y_edge - s*1, dt]]);
}

module holder() {
    difference() {
        union() {
            linear_extrude(H_tot) rrect(Wo, Ho, ro);
            // plug housing
            translate([0,0,0]) linear_extrude(H_tot)
                hull() {
                    translate([Wo/2-ro, 0]) square([1, 2*hs_y+2*wall], center=true);
                    translate([hs_out-3, hs_y+wall-3]) circle(r=3);
                    translate([hs_out-3, -(hs_y+wall-3)]) circle(r=3);
                }
            // dovetail flanges top & bottom
            flange_prism(flange_x0, flange_x1,  Ho/2,  1);
            flange_prism(flange_x0, flange_x1, -Ho/2, -1);
        }
        // tablet cavity
        translate([0,0,back_t]) linear_extrude(lip_z0 - back_t + e) rrect(Wi, Hi, ri);
        // 45 deg lip chamfer, then front window
        hull() { slab(Wi, Hi, ri, lip_z0); slab(Wi-2*lip, Hi-2*lip, ri-lip, lip_z0+lip-e); }
        translate([0,0,lip_z0]) linear_extrude(H_tot) rrect(Wi-2*lip, Hi-2*lip, ri-lip);

        // plug housing interior + window into the tablet cavity (open at back)
        box(hs_x0 - 1, hs_x1, -hs_y, hs_y, -1, H_tot - cover_t);
        // cable exits (open from the back so the cable can be laid in)
        for (s=[-1,1]) if ((s>0 && exit_top) || (s<0 && exit_bottom))
            box(hs_x1 - cable_d - 1, hs_x1 - 1, s>0 ? hs_y-1 : -hs_y-wall-1,
                s>0 ? hs_y+wall+1 : -hs_y+1, -1, port_z + cable_d/2);

        // speaker grilles, both short edges
        for (sx=[-1,1], sy=[-1,1])
            box(sx>0 ? Wi/2-1 : -Wo/2-1, sx>0 ? Wo/2+1 : -Wi/2+1,
                sy>0 ? speaker_from : -speaker_to, sy>0 ? speaker_to : -speaker_from,
                back_t + 1.5, cav_top - 1.5);
        // headphone jack (non-port edge); both possible positions
        for (sy=[-1,1])
            box(-Wo/2-1, -Wi/2+1, sy*jack_y - jack_w/2, sy*jack_y + jack_w/2,
                back_t + 1, cav_top - 1);
        // buttons
        if (btn_cut)
            box(-Wi/2 + btn_from, -Wi/2 + btn_to, Hi/2-1, Ho/2+1, back_t + 1.5, cav_top - 1.2);

        // back windows (saves plastic, clears the rear camera bump)
        for (sx=[-1,1]) translate([sx*42, 0, -1]) linear_extrude(back_t+2) rrect(60, Hi-24, 6);
        translate([-(Wi/2-4+98)/2 - 0, 0, -1]) linear_extrude(back_t+2) rrect(Wi/2-4-98, Hi-12, 4);

        // magnet pockets (open to the back)
        for (p=mag_xy) translate([p[0],p[1],-e]) cylinder(d=mag_d, h=mag_t+0.2);
    }
}

module plate() {
    difference() {
        union() {
            linear_extrude(plate_t) rrect(plate_w, plate_h, 4);
            for (s=[-1,1]) rail(s);
            // end stop at the port end
            for (s=[-1,1])
                box(plate_w/2 - stop_len, plate_w/2,
                    s>0 ? Ho/2 - 4 : -(plate_h/2), s>0 ? plate_h/2 : -(Ho/2 - 4),
                    plate_t - e, plate_t + dt);
        }
        // windows
        for (sx=[-1,1]) translate([sx*40, 0, -1]) linear_extrude(plate_t+2) rrect(56, 96, 6);
        // countersunk screw holes
        for (p=screws) translate([p[0],p[1],0]) {
            translate([0,0,-1]) cylinder(d=screw_d, h=plate_t+2);
            translate([0,0,plate_t - (screw_head-screw_d)/2]) cylinder(d1=screw_d, d2=screw_head, h=(screw_head-screw_d)/2+e);
        }
        // magnet pockets
        for (p=mag_xy) translate([p[0],p[1],plate_t - mag_t - 0.2]) cylinder(d=mag_d, h=mag_t+1);
    }
}

// Rail along the top (s=1) or bottom (s=-1): 45 deg undercut over the flange.
module rail(s) {
    yi0 = s*(Ho/2 + dt + dt_clr);       // inner face at z = plate_t
    yi1 = s*(Ho/2 + dt_clr);            // inner face at z = plate_t + dt
    yo  = s*(plate_h/2);
    translate([-plate_w/2, 0, plate_t - e]) rotate([90,0,90]) linear_extrude(plate_w)
        polygon([[yi0, 0], [yo, 0], [yo, dt], [yi1, dt]]);
}

module oriented() { if (PORT_RIGHT) children(); else mirror([1,0,0]) children(); }

if (PART == "holder")   oriented() holder();
if (PART == "plate")    oriented() plate();
if (PART == "assembly") oriented() {
    color("dimgray") plate();
    color("gray", 0.9) translate([0,0,plate_t]) holder();
    color("black", 0.6) translate([0,0,plate_t + back_t]) linear_extrude(tab_t) rrect(tab_w, tab_h, tab_r);
}
