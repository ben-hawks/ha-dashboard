# Lenovo Tab M10 HD (2nd Gen, TB-X306F) wall mount with a 90° USB-C housing

A sliding wall mount based on the idea of Kreato 3D's
[Lenovo Tab M10 HD 2 Gen wall mount](https://cults3d.com/en/3d-model/gadget/lenovo-tab-m10-hd-2-gen-wall-mount),
redrawn from scratch in OpenSCAD (`m10-wall-mount.scad`). This version adds a
housing on the side for a **90° (right-angle) USB-C plug**, so the tablet can
stay on charge.

| File | What it is | Print |
|------|-----------|-------|
| `m10-holder.stl` | Tablet holder. The tablet snaps in behind a 2 mm, 45° lip | Back face down, no supports |
| `m10-plate.stl`  | Wall plate. 6 countersunk holes for 4 mm screws | Back face down, no supports |

PETG is a good choice because the holder has to flex a little when the tablet
snaps in. Use 3 to 4 walls and about 20 % infill.

## How it goes together

1. Screw the plate to the wall, with the rails at the top and bottom and the
   end stops on the right.
2. Glue two 12 mm magnets into the plate (the default pocket is for
   12 × 2 mm discs) and two into the back of the holder. Check the polarity
   first so each pair attracts.
3. Snap the tablet into the holder, with the USB-C port on the housing side.
4. Plug the right-angle USB-C plug in from behind, through the open back of the
   housing. The cable leaves through the notch at the top or the bottom.
5. Slide the holder onto the rails from the left until it hits the stops. The
   magnets hold it there.

## Tablet details used

- 241.54 × 149.38 × 8.25 mm, with about 9 mm corner radius (estimated)
- USB-C is centred on one short edge, with speaker grilles on both short edges
  and the 3.5 mm jack on the other short edge
- **Unverified:** the power and volume buttons are assumed to be on the top
  long edge near the jack end (`btn_from`/`btn_to`). Check this against your
  tablet before printing.

## Adjusting

Open the `.scad` file in OpenSCAD and change the parameters at the top:

- `PORT_RIGHT` puts the port on the right; set it to `false` to mirror the
  whole mount.
- `plug_depth` / `plug_len` set the space for the plug head and the cable bend.
  The defaults are 15 mm out from the tablet edge and 60 mm along it.
- `cable_d`, `exit_top`, `exit_bottom` control the cable exit notches.
- `clr` is the tablet clearance and `lip` is how much the lip overlaps the
  bezel.
- For 3 mm magnets, set `mag_t = 3` and `back_t = 4`.

Export STLs:

```bash
openscad -D 'PART="holder"' -o m10-holder.stl m10-wall-mount.scad
openscad -D 'PART="plate"'  -o m10-plate.stl  m10-wall-mount.scad
```
