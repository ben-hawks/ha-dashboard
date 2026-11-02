# Lenovo Tab M10 HD (2nd Gen, TB-X306F) wall mount with a 90° USB-C housing

A sliding wall mount based on the idea of Kreato 3D's
[Lenovo Tab M10 HD 2 Gen wall mount](https://cults3d.com/en/3d-model/gadget/lenovo-tab-m10-hd-2-gen-wall-mount),
redrawn from scratch in OpenSCAD (`m10-wall-mount.scad`). This version adds a
housing on the side for a **90° (right-angle) USB-C plug**, so the tablet can
stay on charge.

| File | What it is | Print |
|------|-----------|-------|
| `m10-holder.stl` | Tablet holder. The tablet snaps in behind a 2 mm, 45° lip. The front edge is rounded, and the right-hand border is wider to hold the plug | Back face down, no supports |
| `m10-plate.stl`  | Wall plate. 6 countersunk holes for 4 mm screws. It sits fully hidden behind the holder | Back face down, no supports |

PETG is a good choice because the holder has to flex a little when the tablet
snaps in. Use 3 to 4 walls and about 20 % infill.

## How it goes together

1. Screw the plate to the wall, with the rails along the top and bottom.
2. Glue two 12 mm magnets into the plate (the default pocket is for
   12 × 2 mm discs) and two into the back of the holder. Check the polarity
   first so each pair attracts.
3. Snap the tablet into the holder, with the USB-C port on the housing side.
4. Plug the right-angle USB-C plug in from behind, through the open back of the
   housing. Lay the cable in the channel on the back that runs to the top or
   bottom edge.
5. Slide the holder onto the rails from the left. The rails grip a 45° bevel
   along the holder's top and bottom back edges. The holder stops when the
   rails reach the un-bevelled left end, and the magnets hold it there. To
   remove it, slide it to the left.

## Tablet details used

- 241.54 × 149.38 × 8.25 mm, with about 9 mm corner radius (estimated)
- USB-C is centred on one short edge, with speaker grilles on both short edges
  and the 3.5 mm jack on the other short edge
- The power and volume buttons are on the top long edge, about 45 to 112 mm
  from the jack end. There are mic holes about 124, 168 and 219 mm from that
  end. These were measured from product photos, so check them against your
  tablet.

## Adjusting

Open the `.scad` file in OpenSCAD and change the parameters at the top:

- `PORT_RIGHT` puts the port on the right; set it to `false` to mirror the
  whole mount.
- `plug_depth` / `plug_len` set the space for the plug head and the cable bend.
  The defaults are 15 mm out from the tablet edge and 60 mm along it.
- `cable_d`, `exit_top`, `exit_bottom` control the cable channels.
- `edge_r` sets the rounding on the front edge.
- `btn_from`/`btn_to` and `mic_at` set the button slot and the mic holes.
- `clr` is the tablet clearance and `lip` is how much the lip overlaps the
  bezel.
- For 3 mm magnets, set `mag_t = 3` and `back_t = 4`.

Export STLs:

```bash
openscad -D 'PART="holder"' -o m10-holder.stl m10-wall-mount.scad
openscad -D 'PART="plate"'  -o m10-plate.stl  m10-wall-mount.scad
```
