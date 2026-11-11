# Lenovo Tab M10 HD (2nd Gen, TB-X306F) slide-in wall mount with 90° USB-C

A slide-in wall mount based on the idea of Kreato 3D's
[Lenovo Tab M10 HD 2 Gen wall mount](https://cults3d.com/en/3d-model/gadget/lenovo-tab-m10-hd-2-gen-wall-mount),
redrawn from scratch in OpenSCAD (`m10-wall-mount.scad`).

- **Printed parts:** `m10-mount.stl`, screwed to the wall, and
  `m10-retainer.stl`, a small block that holds the USB-C plug in place. Print
  both back face down with no supports. PETG or PLA both work, with 3 to 4
  walls.
- **The bare tablet (no case) slides in** from the open left end. Grooves
  along its top and bottom edges hold it, with a 2 mm, 45° lip over the bezel.
  About 40 mm of the left end sticks out, so you can grip it and so the rear
  camera bump stays clear.
- **It charges itself.** A right-angle (side-bend) USB-C plug sits in a pocket
  at the right end. As the tablet slides home it pushes onto the plug, and the
  plug acts as the end stop. The cable runs in a channel on the back out to the
  bottom edge (`cable_dir = 1` for the top). There is also an optional hole
  behind the pocket for a cable coming out of the wall.
- **10 × 2 mm magnets**: there are six pockets in the floor. The grooves carry
  the tablet's weight, so the magnets only stop it creeping out of the open
  end.
- **Openings** for the right-hand speaker, the power/volume buttons and the
  three mic holes. The left speaker and the headphone jack are on the end that
  sticks out.

## Before printing

1. **Plug:** the pocket is sized for the Anker 240W braided USB-C to
   right-angle USB-C cable (head 14.6 mm out from the edge, extending 6 mm
   one side of the port and 17.3 mm toward the cable, 6.3 mm thick, with a
   4.4 mm strain relief). For a different cable, change `plug_*`, `cable_x`
   and `cable_d`.
   **Test fit first:** print `m10-test.stl` and the retainer. The test piece is
   just the port end (about 25 mm of the
   grooves plus the plug pocket, ~36 cm³). Check that the tablet slides in and
   docks onto the plug before printing the whole mount.
2. **Magnets:** six pockets are provided. Hold a loose magnet against the back
   of the tablet in the inserted position, and glue magnets into the pockets
   where it pulls. Empty pockets do no harm. Move them with `mag_xy`. For 3 mm
   thick magnets, set `mag_t = 3` and `back_t = 4`.
3. If the buttons, mics or speakers don't line up on your unit, adjust
   `btn_from`/`btn_to`, `mic_at` and `speaker_from`/`speaker_to`. They were
   measured from product photos.

## Installing

1. Glue in the magnets (CA or epoxy), with their faces flush with the floor.
2. With the mount face down, drop the plug head into its pocket from the back,
   with the connector pointing into the tablet slot. Press the cable into the
   channel on the back. If the cable comes out the wrong way, flip the plug
   over.
3. Press the retainer into the pocket behind the plug, flush with the back of
   the mount. It holds the plug at the port's height. A dab of glue on the
   retainer is optional, since the wall holds it in once the mount is up.
4. Screw the mount to the wall through the 5 countersunk holes, sized for 4 mm
   screws. The heads sit flush with the floor.
5. Slide the tablet in from the left. It pushes onto the plug as it reaches
   the end.

`PORT_RIGHT = false` mirrors the whole mount if you'd rather have the port on
the left. Change `stick_out` for more or less overhang.

Export the STLs:

```bash
openscad -D 'PART="mount"' -o m10-mount.stl m10-wall-mount.scad
openscad -D 'PART="retainer"' -o m10-retainer.stl m10-wall-mount.scad
openscad -D 'PART="test"'  -o m10-test.stl  m10-wall-mount.scad
```

## Tablet details used

- 241.54 × 149.38 × 8.25 mm, with about 9 mm corner radius (estimated)
- USB-C is centred on one short edge, with speakers on both short edges and the
  jack on the other short edge
- The buttons are on the top long edge, about 45 to 112 mm from the jack end.
  The mic holes are about 124, 168 and 219 mm from that end
