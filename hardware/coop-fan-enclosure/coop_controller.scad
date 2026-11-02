// =====================================================================
//  Chicken-coop fan controller enclosure
//  For: 93 x 87 mm "ESP32-WROOM-32E 4-channel relay" board, DC-powered,
//  switching a low-voltage DC fan (all wiring in the box is low voltage)
//  Parts: base, lid, gasket, fit-check template
//  Units: mm.  Print in ASA (preferred) or PETG.  NOT PLA.
//
//  Render one part at a time:
//    openscad -D 'part="base"' -o base.stl coop_controller.scad
//    part = "base" | "lid" | "gasket" | "fitcheck" | "assembly"
// =====================================================================

part = "assembly";

/* ---------- Board (MEASURE YOURS and adjust) ---------- */
pcb_w      = 93;     // X
pcb_h      = 87;     // Y
pcb_t      = 1.6;
hole_dx    = 87;     // centre-to-centre, X  (estimated from listing photo)
hole_dy    = 81;     // centre-to-centre, Y  (estimated from listing photo)
standoff_h = 7;      // PCB underside clearance (through-hole leads, air gap)
insert_d   = 4.0;    // M3 heat-set insert hole (4.0-4.2 typical)
insert_l   = 6;

/* ---------- Interior layout ---------- */
// Board sits with relay terminals (NO/COM/NC) toward the gland wall (bottom)
// and the N/L + 5-30V terminals toward the top.
ch_mains   = 14;     // left channel: DC supply wiring up to the 7-30V terminal
ch_lv      = 22;     // right channel: sensor cable up to ESP32 header
gap_bottom = 30;     // gland wall -> PCB: wire bend room
gap_top    = 18;     // PCB -> top wall: room to land N/L wires
inner_z    = 48;     // floor -> lid underside

wall   = 3.2;
floor_t= 3;
r_out  = 6;          // outer corner radius

inner_x = ch_mains + pcb_w + ch_lv;      // 131
inner_y = gap_bottom + pcb_h + gap_top;  // 141
outer_x = inner_x + 2*wall;
outer_y = inner_y + 2*wall;
outer_z = floor_t + inner_z;

/* ---------- Lid / seal ---------- */
lid_t        = 4;
lid_line2    = "12 VDC";      // set to your supply voltage
lid_lip      = 3;           // lid overhangs walls: keeps groove inside, drip edge
groove_w     = wall + 1.0;   // gasket groove, centred on wall
groove_d     = 2.4;
gasket_t     = 3.0;          // printed TPU gasket height (≈20% squeeze)
lid_screw_d  = 4.5;          // M4 clearance
boss_d       = 11;
m4_insert_d  = 5.6;          // M4 heat-set insert
m4_insert_l  = 8;

/* ---------- Glands on the bottom (Y=0) wall ---------- */
// [x centre from inner left wall, hole diameter, label]
glands = [
  [ 23,   15.7, "PG9 DC IN"    ],   // PG9 thread OD 15.2
  [ 48,   13.0, "PG7 FAN"      ],   // PG7 thread OD 12.5
  [ 72,   12.5, "M12 VENT"     ],   // M12x1.5 breather vent
  [110,   13.0, "PG7 SENSOR"   ],   // use 15.7 (PG9) if the probe cable has a plug on it
];
gland_z = floor_t + 17;      // hole centre height above outside floor

/* ---------- Wall mount ears ---------- */
ear_w = 16; ear_l = 22; ear_t = 5; ear_hole = 5;

$fn = 64;
eps = 0.01;

// ---------------------------------------------------------------------
module rrect(x, y, h, r) {
  translate([r, r, 0]) linear_extrude(h)
    offset(r) square([x - 2*r, y - 2*r]);
}

function pcb_origin() = [wall + ch_mains, wall + gap_bottom, floor_t];
function pcb_holes() = [
  for (sx = [-1, 1], sy = [-1, 1])
    [pcb_w/2 + sx*hole_dx/2, pcb_h/2 + sy*hole_dy/2]
];
function boss_pts() = [
  for (sx = [0, 1], sy = [0, 1])
    [wall + boss_d/2 - 1 + sx*(inner_x - boss_d + 2),
     wall + boss_d/2 - 1 + sy*(inner_y - boss_d + 2)]
];

// ---------------------------------------------------------------------
module base() {
  difference() {
    union() {
      // shell
      difference() {
        rrect(outer_x, outer_y, outer_z, r_out);
        translate([wall, wall, floor_t])
          rrect(inner_x, inner_y, inner_z + 1, max(r_out - wall, 1));
      }
      // corner lid bosses (blind M4 inserts -> no through-holes)
      for (p = boss_pts()) translate([p[0], p[1], 0])
        cylinder(d = boss_d, h = outer_z);
      // PCB standoffs
      translate(pcb_origin()) for (h = pcb_holes())
        translate([h[0], h[1], 0]) cylinder(d1 = 10, d2 = 7.5, h = standoff_h);
      // low divider: keeps sensor (LV) cable away from relay terminals
      translate([wall + ch_mains + pcb_w + 1, wall + 11, 0])
        cube([2, gap_bottom - 13, floor_t + 16]);
      // gland-wall reinforcement pads (flat, 5 mm thick around each hole)
      for (g = glands) translate([wall + g[0], 0, gland_z])
        rotate([-90, 0, 0]) cylinder(d = g[1] + 12, h = wall + 1.8);
      // wall-mount ears (outside the sealed volume)
      for (sx = [0, 1], sy = [0, 1])
        translate([sx ? outer_x - 2 : -ear_l + 2,
                   sy ? outer_y - 20 - ear_w : 20, 0])
          difference() {
            hull() {
              cube([ear_l, ear_w, ear_t]);
              translate([sx ? 0 : ear_l - 2, 0, 0]) cube([2, ear_w, ear_t + 6]);
            }
            translate([sx ? ear_l - 8 : 8, ear_w/2, -1])
              cylinder(d = ear_hole, h = 20);
          }
    }
    // keep pads from protruding into the inner space more than needed
    // (they are clipped by the floor/cavity naturally)

    // insert holes in standoffs
    translate(pcb_origin()) for (h = pcb_holes())
      translate([h[0], h[1], standoff_h - insert_l + eps])
        cylinder(d = insert_d, h = insert_l);
    // M4 insert holes in lid bosses
    for (p = boss_pts()) translate([p[0], p[1], outer_z - m4_insert_l])
      cylinder(d = m4_insert_d, h = m4_insert_l + 1);
    // gland holes
    for (g = glands) translate([wall + g[0], -1, gland_z])
      rotate([-90, 0, 0]) cylinder(d = g[1], h = wall + 4);
    // label recesses on the floor (helps when wiring)
    for (g = glands) translate([wall + g[0], wall + 13, floor_t - 0.6])
      linear_extrude(1) text(g[2], size = 2.8, halign = "center",
                             font = "Liberation Sans:style=Bold");
    translate([wall + 4, wall + gap_bottom + pcb_h/2, floor_t - 0.6])
      rotate(90) linear_extrude(1)
        text("POWER", size = 5, halign = "center",
             font = "Liberation Sans:style=Bold");
    translate([outer_x - wall - 4, wall + gap_bottom + pcb_h/2, floor_t - 0.6])
      rotate(-90) linear_extrude(1)
        text("LOW VOLTAGE", size = 4, halign = "center",
             font = "Liberation Sans:style=Bold");
  }
  // cable-tie anchors on the floor (strain relief before terminals)
  for (x = [wall + 23, wall + 48, wall + 110])
    translate([x - 6, wall + 22, floor_t]) tie_anchor();
  translate([wall + 6, wall + gap_bottom + 30, floor_t]) rotate(90) tie_anchor();
  translate([outer_x - wall - 6, wall + gap_bottom + 30, floor_t]) rotate(90) tie_anchor();
}

module tie_anchor() {   // bridge for a 4 mm zip tie
  difference() {
    cube([12, 6, 5]);
    translate([3, -1, -eps]) cube([6, 8, 2.5]);
  }
}

// ---------------------------------------------------------------------
module lid() {
  difference() {
    union() {
      translate([-lid_lip, -lid_lip, 0])
        rrect(outer_x + 2*lid_lip, outer_y + 2*lid_lip, lid_t, r_out + lid_lip);
      // locating skirt that drops just inside the walls
      translate([wall + 0.4, wall + 0.4, lid_t - eps])
        difference() {
          rrect(inner_x - 0.8, inner_y - 0.8, 4, max(r_out - wall - 0.4, 1));
          translate([1.6, 1.6, -1])
            rrect(inner_x - 4, inner_y - 4, 6, max(r_out - wall - 2, 1));
          // clear the corner bosses
          for (p = boss_pts())
            translate([p[0] - wall - 0.4, p[1] - wall - 0.4, -1])
              cylinder(d = boss_d + 1.5, h = 6);
        }
    }
    // gasket groove (underside, centred on wall line)
    translate([0, 0, lid_t - groove_d]) seal_ring(groove_w, groove_d + 1);
    // screw holes + counterbores for M4 + bonded sealing washer
    for (p = boss_pts()) translate([p[0], p[1], -1]) {
      cylinder(d = lid_screw_d, h = lid_t + 2);
      cylinder(d = 10.5, h = 1 + 1.2);
    }
    // embossed warning (outside face is z=0 side; mirror so it reads right)
    translate([outer_x/2, outer_y/2 + 8, -eps]) mirror([1, 0, 0])
      linear_extrude(0.8) text("COOP FAN CTRL", size = 8, halign = "center",
                               font = "Liberation Sans:style=Bold");
    translate([outer_x/2, outer_y/2 - 10, -eps]) mirror([1, 0, 0])
      linear_extrude(0.8) text(lid_line2, size = 7, halign = "center",
                               font = "Liberation Sans:style=Bold");
  }
}

// ring following the wall centre line
module seal_ring(w, h) {
  c = wall / 2;
  difference() {
    translate([c - w/2, c - w/2, 0])
      rrect(outer_x - wall + w, outer_y - wall + w, h, r_out - c + w/2);
    translate([c + w/2, c + w/2, -1])
      rrect(outer_x - wall - w, outer_y - wall - w, h + 2, max(r_out - c - w/2, 0.5));
  }
}

module gasket() {   // print in TPU 85A-95A, 100% infill
  difference() {
    seal_ring(groove_w - 0.4, gasket_t);
    for (p = boss_pts()) translate([p[0], p[1], -1])
      cylinder(d = lid_screw_d + 1, h = gasket_t + 2);
  }
}

// ---------------------------------------------------------------------
// 1.2 mm template: lay your board on it to check hole pitch before
// committing to the 6-hour base print.
module fitcheck() {
  difference() {
    union() {
      linear_extrude(1.2) difference() {
        square([pcb_w, pcb_h]);
        translate([6, 6]) square([pcb_w - 12, pcb_h - 12]);
      }
      for (h = pcb_holes()) translate([h[0], h[1], 0])
        cylinder(d = 7.5, h = 1.2);
      // pegs that should drop into the board's mounting holes
      for (h = pcb_holes()) translate([h[0], h[1], 0])
        cylinder(d = 2.7, h = 4);
    }
  }
}

// ---------------------------------------------------------------------
module pcb_dummy() {
  color("royalblue") translate(pcb_origin() + [0, 0, standoff_h])
    difference() {
      cube([pcb_w, pcb_h, pcb_t]);
      for (h = pcb_holes()) translate([h[0], h[1], -1]) cylinder(d = 3.2, h = 4);
    }
  // relays + terminals (rough envelopes)
  color("deepskyblue") for (i = [0:3])
    translate(pcb_origin() + [8 + i*21.5, 12, standoff_h + pcb_t])
      cube([19, 15.5, 15.5]);
  color("mediumseagreen") for (i = [0:3])
    translate(pcb_origin() + [6 + i*21.5, 0, standoff_h + pcb_t])
      cube([20, 8, 14]);
  color("silver") translate(pcb_origin() + [62, 57, standoff_h + pcb_t])
    cube([18, 25.5, 3.2]);
}

if (part == "base") base();
else if (part == "lid") lid();   // prints outside-face down, skirt up
else if (part == "gasket") gasket();
else if (part == "fitcheck") fitcheck();
else if (part == "assembly") {
  base();
  pcb_dummy();
  color("orange", 0.9) translate([0, 0, outer_z + 25]) seal_ring(groove_w - 0.4, gasket_t);
  color("lightgray", 0.55) translate([0, outer_y, outer_z + 45 + lid_t]) rotate([180,0,0]) lid();
}
