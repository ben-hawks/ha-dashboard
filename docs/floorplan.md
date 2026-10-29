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
5. **Tidy up in the editor:** the outline is simplified (rectangular rooms,
   approximate doors and windows). Adjust anything that looks off, add
   furniture if you like, and check the stairs.

After that, refresh the wall tablet. The Floor Plan tab shows the 3D house.

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
