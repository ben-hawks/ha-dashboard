# Floor Plan tab

Two versions, built from the same room layout in `tools/floorplan.py`
(traced from the listing plan and scaled to its room dimensions):

| Version | File | Notes |
|---------|------|-------|
| **3D (NeonPlan 3D)**, in use | `dashboard/views/floorplan_3d.yaml` | Needs the NeonPlan 3D integration and a one-time import |
| **2D**, fallback | `dashboard/views/floorplan.yaml` (generated) | Built-in cards only; lighter on the tablet |

Switch between them in `dashboard/dashboard.yaml` (the `floorplan` include
line).

## Setting up NeonPlan 3D (once)

1. **Install:** HACS → search **NeonPlan 3D** → Download. Restart Home
   Assistant, then **Settings → Devices & services → Add integration →
   NeonPlan 3D**. A **NeonPlan 3D** entry appears in your sidebar.
2. **Convert the house file:** on your PC, open
   <https://neonplan3d.mastershort.de/import/> and drop
   `floorplan/neonplan-import.json` from this repo onto it. It shows a
   preview (two floors, rooms, doors and windows), then lets you download a
   NeonPlan file. The import file only holds room shapes and names.
3. **Load it:** NeonPlan 3D in the sidebar → **Editor → Backup → Import…**
   → choose the downloaded file.
4. **Link rooms to areas:** rooms are named after your Home Assistant areas
   (Bedroom, Kitchen, Hallway, Living Room, Meg's Office, Office, Game Room,
   Laundry Room, Work Office, Garage). In the editor, check each room's
   area, then use its option to add the area's devices, which places your
   lights, sensors and speakers.
5. **Tidy up in the editor:** the outline is simplified (straight walls,
   approximate doors and windows). Adjust anything that looks off and add
   furniture if you like.
6. **Open up the open-plan spaces:** the import format only has doors, so
   openings come in as wide doors. In the editor, change them (manual
   section 4.4 / 4.7):

   | Between | Make it |
   |---------|---------|
   | Kitchen ↔ Dining | No wall: select the wall, choose no wall |
   | Dining ↔ Living Room | Door → Style: **Opening (no door)** |
   | Hallway ↔ Kitchen | Door → Style: **Opening (no door)** |
   | Hallway ↔ Living Room | Door → Style: **Opening (no door)** |
   | Hall ↔ Game Room (downstairs) | Door → Style: **Opening (no door)** |

   The rooms stay separate Home Assistant areas either way; light from a
   lamp shines through an opening or a removed wall into the next room.
7. **Check the split-foyer stairs:** the file includes both flights from the
   entry landing (down to the downstairs hall, up to the upstairs hallway),
   placed on the Downstairs floor with the landing half a storey up. If a
   flight points the wrong way in 3D, rotate it 180° in the editor.

   NeonPlan has no per-room floor level, so the landing itself is a
   workaround. The landing sits directly over the downstairs closet:
   - **Downstairs → Closet → Ceiling height: 1.2 m.** Its ceiling becomes
     the landing at the right height (and it really is a low closet under
     the landing and the up flight).
   - **Upstairs → Floor opening tool:** draw it over the foyer (everything
     but the small closet) so you can see down to the landing and both
     flights.
   - If you have the *Architecture & fit-out* furniture pack, its
     **platform** piece (1.2 m high, on the Downstairs floor) is a cleaner
     landing than the closet ceiling.

After that, refresh the wall tablet. The 3D house shows on the **Home** tab
(top left, `dashboard/views/home.yaml`) and full screen on the **Floor Plan**
tab. To use the 2D version on Home instead, swap the `neonplan3d-card` there
for the cards in `dashboard/views/floorplan.yaml`.

## Changing the layout

- **Rooms, doors, windows, furniture:** edit them in NeonPlan's editor. They
  are stored there, not in this repo.
- **Starting over from the traced plan:** edit `FLOORS` in
  `tools/floorplan.py`, run `python3 tools/floorplan.py`, and repeat steps
  2–3. This also regenerates the 2D tab.

## If it's slow on the tablet

The card already picks its lightest quality level on weak hardware. If it's
still sluggish on the Lenovo, switch the include in `dashboard.yaml` back to
`views/floorplan.yaml`.
