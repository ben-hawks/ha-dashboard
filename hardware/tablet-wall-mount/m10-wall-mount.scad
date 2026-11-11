// Slide-in wall mount for the Lenovo Tab M10 HD (2nd Gen, TB-X306F), landscape,
// with a built-in pocket for a 90-degree (side-angle) USB-C plug.
//
// Inspired by Kreato 3D's "Lenovo Tab M10 HD 2 Gen wall mount" (cults3d),
// redrawn from scratch. The mount is screwed to the wall. The bare tablet
// (no case) slides in from the open left end, in grooves along its top and
// bottom edges. At the right end it pushes onto a right-angle USB-C plug held
// in a pocket, so it plugs itself in and the plug acts as the end stop. Magnets
// in the floor hold it there. The tablet's left end sticks out so you can grip
// it to pull it out.
//
// PART = "mount"    - the part to print (back face down, no supports)
// PART = "retainer" - small block that holds the USB-C plug in its pocket
// PART = "assembly" - mount + tablet, for checking (don't print)
//
// Coordinates (front view): X right, Y up, Z out of the wall.
// The USB-C port is on the RIGHT (set PORT_RIGHT=false to mirror everything).

PART = "assembly";   // "mount", "retainer", "test" (port end only) or "assembly"
PORT_RIGHT = true;

/* ---- Tablet ---- */
tab_w = 241.54;      // long side
tab_h = 149.38;      // short side
tab_t = 8.25;        // thickness
tab_r = 9;           // corner radius (plan view, estimated)
clr   = 0.4;         // sliding clearance tablet <-> grooves, each side (X/Y)
clr_z = 0.5;         // sliding clearance front-to-back (total)

/* ---- Body ---- */
wall     = 2.2;      // top/bottom wall thickness
back_t   = 3.0;      // floor thickness (raise to 4 if you use 3 mm thick magnets)
lip      = 2.0;      // how far the front lip covers the bezel (45 deg chamfer)
lip_drop = 0.5;      // chamfer starts this far below the tablet front face (edge is rounded)
edge_r   = 2;        // rounded-over front outer edge
stick_out = 40;      // how much of the tablet's left end sticks out (grip,
                     // and keeps the rear camera bump clear)

/* ---- 90 deg USB-C plug ---- */
// Defaults: Anker 240W braided USB-C to right-angle USB-C, measured from photos.
// All measured with the plug pushed fully into the tablet:
plug_L    = 14.6;    // from the tablet edge to the back of the head
plug_far  = 6.0;     // head extent from the port centre, away from the cable
plug_near = 17.3;    // head extent from the port centre, towards the cable
plug_T    = 6.3;     // head thickness front-to-back
plug_clr  = 0.2;     // fit; fix the plug with a dab of hot glue once aligned
cable_x   = 8.9;     // centre of the strain relief / cable, from the tablet edge
cable_d   = 4.8;     // strain relief / cable diameter (+ clearance)
cable_dir = -1;      // cable leaves the head going -1 = down, +1 = up
                     // (flip the plug over to make it go the other way)

/* ---- Other edge openings (measured from the non-port / jack end) ---- */
speaker_from = 33;   // speaker grilles on both short edges, |y| range from centre
speaker_to   = 58;
btn_from = 45;       // power + volume buttons, top long edge
btn_to   = 112;
mic_at   = [124, 168, 219];   // mic holes, top long edge
mic_d    = 2.5;

/* ---- Wall fixing ---- */
screw_d    = 4.5;    // screw clearance
screw_head = 9;      // countersink diameter (heads sit flush in the floor)
screws = [[-60,40],[-60,-40],[60,40],[60,-40],[0,0]];
in_wall_hole = true; // hole behind the plug pocket for a cable from the wall

/* ---- Magnets (10 x 2 mm discs, in the floor, facing the tablet) ---- */
// The grooves carry the tablet's weight; the magnets only stop it creeping out
// of the open end. Six pockets: hold a loose magnet against the back of your
// tablet to find where it pulls, and glue magnets into the pockets that line up
// (empty pockets do no harm). Mind the polarity if the tablet pulls one way only.
mag_d  = 10.3;       // 10 mm magnet + clearance (glue them in)
mag_t  = 2;          // pocket is mag_t + 0.2 deep, magnet ends flush
mag_xy = [[-40, 58], [70, 58], [-40, -58], [70, -58], [105, 45], [105, -45]];

$fn = 64;
e = 0.01;

/* ---- Derived ---- */
Wi = tab_w + 2*clr;  Hi = tab_h + 2*clr;  ri = tab_r + clr;
Ho = Hi + 2*wall;    ro = ri + wall;
x_left  = -Wi/2 + stick_out;              // open left end of the mount
cav_top = back_t + tab_t + clr_z;
lip_z0  = cav_top - lip_drop;
H_tot   = lip_z0 + lip;
port_z  = back_t + clr_z/2 + tab_t/2;
pk_x1   = Wi/2 + plug_L + plug_clr;       // end of plug pocket
cab_x   = Wi/2 + cable_x;                 // cable centre line
hy0 = cable_dir > 0 ? -plug_far - plug_clr : -plug_near - plug_clr;   // head pocket, y
hy1 = cable_dir > 0 ?  plug_near + plug_clr :  plug_far + plug_clr;
ret_t   = port_z - plug_T/2 - plug_clr;   // retainer thickness (wall -> back of plug)
ret_clr = 0.1;                            // retainer press fit, each side
x_right = pk_x1 + wall;                   // right outer edge

module rrect(w, h, r) {
    r2 = max(r, 0.01);
    hull() for (sx=[-1,1], sy=[-1,1])
        translate([sx*(w/2-r2), sy*(h/2-r2)]) circle(r=r2);
}
module box(x0,x1,y0,y1,z0,z1) translate([x0,y0,z0]) cube([x1-x0,y1-y0,z1-z0]);

// Tablet-shaped opening that runs out through the open left end.
module slot2d(inset=0) hull() {
    rrect(Wi - 2*inset, Hi - 2*inset, ri - inset);
    translate([-Wi, 0]) square([1, Hi - 2*inset], center=true);
}
module slot_slab(inset, z, t=e) translate([0,0,z]) linear_extrude(t) slot2d(inset);

// Outer outline: rounded on the right, smaller radius at the open left end.
module outline() hull() {
    for (sy=[-1,1]) {
        translate([x_right - ro, sy*(Ho/2 - ro)]) circle(r=ro);
        translate([x_left + 3,  sy*(Ho/2 - 3)])  circle(r=3);
    }
}

module rounded_body() {
    n = ceil(edge_r/0.2);
    linear_extrude(H_tot - edge_r + e) outline();
    for (i=[0:n-1]) {
        dz = (i+1)*edge_r/n;
        inset = edge_r - sqrt(max(edge_r*edge_r - dz*dz, 0));
        translate([0,0,H_tot - edge_r + i*edge_r/n])
            linear_extrude(edge_r/n + e) offset(delta=-inset) outline();
    }
}

module mount() {
    yc = cable_dir;                        // cable side
    difference() {
        rounded_body();

        // tablet slot (open on the left)
        translate([0,0,back_t]) linear_extrude(lip_z0 - back_t + e) slot2d(0);
        // 45 deg lip chamfer, then the front window
        hull() { slot_slab(0, lip_z0); slot_slab(lip, lip_z0 + lip - e); }
        translate([0,0,lip_z0]) linear_extrude(H_tot) slot2d(lip);

        // plug head pocket (offset towards the cable). Open at the back: the
        // plug and cable go in from behind, then the retainer presses in behind
        // the plug. Opens into the tablet slot only at the plug's height.
        box(Wi/2 - 1, pk_x1, hy0, hy1,
            port_z - plug_T/2 - plug_clr, port_z + plug_T/2 + plug_clr);
        box(Wi/2, pk_x1, hy0, hy1, -1, port_z);
        // cable channel in the back (open to the wall), out to the edge
        cy0 = yc > 0 ? 0 : -Ho/2 - 1;
        cy1 = yc > 0 ? Ho/2 + 1 : 0;
        box(cab_x - cable_d/2, cab_x + cable_d/2, cy0, cy1, -1, port_z + cable_d/2);
        // optional hole behind the cable for a cable coming out of the wall
        if (in_wall_hole)
            translate([cab_x, yc*(plug_near + 14), -1]) cylinder(d=12, h=port_z);

        // speaker grilles, port end (through the side) - the other end sticks out
        for (sy=[-1,1])
            box(Wi/2 - 1, x_right + 1,
                sy > 0 ? speaker_from : -speaker_to, sy > 0 ? speaker_to : -speaker_from,
                back_t + 1.5, cav_top - 1.5);
        // buttons and mics (top long edge)
        box(-Wi/2 + btn_from, -Wi/2 + btn_to, Hi/2 - 1, Ho/2 + 1, back_t + 1.5, cav_top - 1.2);
        for (m=mic_at) translate([-Wi/2 + m, Hi/2 - 1, port_z])
            rotate([-90,0,0]) cylinder(d=mic_d, h=wall + 2, $fn=24);

        // back windows (save plastic); the left one also clears the camera bump
        translate([x_left - 1, -(Hi/2 - 8), -1]) cube([30, Hi - 16, back_t + 2]);
        for (sx=[-1,1]) translate([sx*30, 0, -1]) linear_extrude(back_t + 2) rrect(44, 56, 6);

        // countersunk screw holes (heads flush with the floor)
        for (p=screws) translate([p[0], p[1], 0]) {
            translate([0,0,-1]) cylinder(d=screw_d, h=back_t + 2);
            translate([0,0,back_t - (screw_head - screw_d)/2])
                cylinder(d1=screw_d, d2=screw_head, h=(screw_head - screw_d)/2 + e);
        }
        // magnet pockets, open towards the tablet
        for (p=mag_xy) translate([p[0], p[1], back_t - mag_t - 0.2]) cylinder(d=mag_d, h=mag_t + 1);
    }
}

// Fills the space between the wall and the back of the plug, holding the plug
// at the port's height. Press it into the back of the pocket.
module retainer() box(Wi/2 + ret_clr, pk_x1 - ret_clr, hy0 + ret_clr, hy1 - ret_clr, 0, ret_t);

module tablet() color([0.08,0.08,0.1])
    translate([0,0,back_t + clr_z/2]) linear_extrude(tab_t) rrect(tab_w, tab_h, tab_r);

module oriented() { if (PORT_RIGHT) children(); else mirror([1,0,0]) children(); }

if (PART == "mount")    oriented() mount();
if (PART == "retainer") oriented() retainer();
// Test fit: just the port end (plug pocket, end of the grooves, corner radius).
if (PART == "test")     oriented() intersection() {
    mount();
    translate([Wi/2 - 25, -Ho, -1]) cube([100, 2*Ho, 50]);
}
if (PART == "assembly") oriented() { color("silver") mount(); color("orange") retainer(); tablet(); }
