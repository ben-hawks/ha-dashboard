// =====================================================================
//  SHT40 probe shield for a chicken coop
//  Stacked inverted-saucer plates (Stevenson-style): air moves freely,
//  dust and droppings don't land on the sensor, beaks can't reach it.
//  A metal-cased SHT40 probe drops into a split clamp under the cap,
//  tip pointing down into the middle of the plate stack; cable exits up.
//
//  part = "cap" | "plate" | "bracket" | "assembly"
//  Print: cap x1, plate x4, bracket x1 (ASA/PETG, white or light colour).
//  Hardware: 3x M3 threaded rod ~90 mm + 6 M3 nuts/washers.
// =====================================================================

part = "assembly";

n_plates  = 4;
plate_od  = 86;
plate_id  = 46;      // centre opening the sensor hangs in
plate_t   = 2.4;     // vertical thickness (~1.7 mm normal to a 45° cone)
slope     = 20;      // outer edge drop; = radial width -> 45° cone (prints support-free)
gap       = 11;      // vertical spacing between plates (spacer height)
post_r    = 36;      // radius of the 3 tie-rod posts
rod_d     = 3.4;
spacer_d  = 8;

probe_d   = 12;      // MEASURE your probe's metal body (common: 12 or 16 mm)
probe_l   = 50;      // body length (only used for the preview)
clamp_l   = 22;      // how much of the body the clamp grips
clamp_wall= 2.6;
cable_d   = 6.5;
cable_slot= 4.5;     // side slot so a pre-terminated cable slips in sideways (>= cable OD)
slot_ang  = 30;      // between two tie rods, away from the wall arm

arm_l     = 45;      // standoff from the wall
mount_w   = 40; mount_h = 50; mount_t = 4;

$fn = 96;
eps = 0.01;

module saucer(id, od, t, drop) {
  rotate_extrude() polygon([
    [id/2, 0], [od/2, -drop], [od/2, -drop + t], [id/2, t]
  ]);
}

module posts_holes(h) {
  for (a = [90, 210, 330]) rotate(a) translate([post_r, 0, -1])
    cylinder(d = rod_d, h = h + 2);
}

drop_post = slope * (post_r - plate_id/2) / (plate_od/2 - plate_id/2);

module plate() {
  difference() {
    union() {
      saucer(plate_id, plate_od, plate_t, slope);
      // integral spacer: from this plate's top surface down to the
      // next plate's top surface at the post radius
      for (a = [90, 210, 330]) rotate(a) translate([post_r, 0, -gap - drop_post])
        cylinder(d = spacer_d, h = gap + plate_t);
    }
    translate([0, 0, -50]) posts_holes(100);
  }
}

// Roof: flat top (prints upside-down with no supports), sloped underside.
module cap() {
  roof_t = 3;
  difference() {
    union() {
      cylinder(r = plate_od/2 + 2, h = roof_t);
      // skirt overlaps the first plate so nothing drops straight in
      translate([0, 0, -12]) difference() {
        cylinder(r = plate_od/2 + 2, h = 12.5);
        translate([0, 0, -1]) cylinder(r = plate_od/2, h = 14);
      }
      // spacer bosses under the roof
      for (a = [90, 210, 330]) rotate(a) translate([post_r, 0, -gap - drop_post])
        cylinder(d = spacer_d, h = gap + drop_post + 1);
      // probe clamp (split tube, tightened with a zip tie)
      translate([0, 0, -clamp_l]) cylinder(d = probe_d + 2*clamp_wall, h = clamp_l + 1);
    }
    translate([0, 0, -50]) posts_holes(100);
    // probe bore (slight interference after the zip tie is cinched)
    translate([0, 0, -clamp_l - 1]) cylinder(d = probe_d + 0.3, h = clamp_l + 1 - 1.2);
    // cable passage through the roof (shoulder stops the probe body)
    translate([0, 0, -5]) cylinder(d = cable_d, h = 20);
    rotate(slot_ang) translate([0, -cable_slot/2, -1.2]) cube([plate_od, cable_slot, 10]);
    rotate(slot_ang) translate([plate_od/2 - 1, -cable_slot/2, -13]) cube([5, cable_slot, 20]);
    // clamp slits so it can squeeze
    for (a = [0, 180]) rotate(a)
      translate([probe_d/2 - 1, -0.9, -clamp_l - 1]) cube([clamp_wall + 2, 1.8, clamp_l - 4]);
    // zip-tie grooves round the clamp
    for (z = [-clamp_l + 3, -clamp_l + 11])
      translate([0, 0, z]) difference() {
        cylinder(d = probe_d + 2*clamp_wall + 2, h = 4);
        translate([0, 0, -1]) cylinder(d = probe_d + 2*clamp_wall - 1.6, h = 6);
      }
  }
}

// Wall bracket: the 3 tie rods pass through its pad, clamping
// bracket + cap + plates into one stack.  Print arm-flat.
module bracket() {
  pad_r = post_r + 7;
  difference() {
    union() {
      // pad (triangle-ish around the 3 posts)
      hull() for (a = [90, 210, 330]) rotate(a) translate([post_r, 0, 0])
        cylinder(d = 14, h = 5);
      // arm
      translate([-9, -arm_l - post_r, 0]) cube([18, arm_l + post_r, 5]);
      // wall plate
      translate([-mount_w/2, -arm_l - post_r - mount_t, 0]) cube([mount_w, mount_t, mount_h]);
      // gusset
      hull() {
        translate([-2.5, -arm_l - post_r, 0]) cube([5, 1, mount_h * 0.7]);
        translate([-2.5, -post_r + 5, 0]) cube([5, 1, 5]);
      }
    }
    translate([0, 0, -1]) posts_holes(10);
    translate([0, 0, -1]) cylinder(d = cable_d + 2, h = 10);
    rotate(slot_ang) translate([0, -cable_slot/2, -1]) cube([plate_od, cable_slot, 10]);
    for (z = [mount_h - 10, 22]) for (x = [-mount_w/2 + 7, mount_w/2 - 7])
      translate([x, -arm_l - post_r + 1, z]) rotate([90, 0, 0])
        cylinder(d = 4.5, h = mount_t + 2);
  }
}

module probe_dummy() {
  color("silver") translate([0, 0, -1.2 - probe_l]) cylinder(d = probe_d, h = probe_l);
  color("dimgray") cylinder(d = 4.5, h = 40);
}

if (part == "plate") translate([0, 0, plate_t]) rotate([180, 0, 0]) plate();  // inner ring on bed
else if (part == "cap") translate([0, 0, 3]) rotate([180, 0, 0]) cap();
else if (part == "bracket") bracket();
else if (part == "assembly") {
  color("whitesmoke") cap();
  color("silver") translate([0, 0, 3]) bracket();
  probe_dummy();
  for (i = [1:n_plates])
    color("gainsboro") translate([0, 0, -i * (gap + plate_t)]) plate();
}
