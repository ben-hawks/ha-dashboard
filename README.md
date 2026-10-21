# Home Assistant Wall Tablet Dashboard

A Home Assistant dashboard for a wall-mounted Android tablet. It should be easy
for anyone in the house to use, including people who never open Home Assistant
settings.

## Design principles

1. **One glance, one tap.** The home screen answers "what's going on?" and
   handles the five or six things people do most, in one tap each.
2. **Plain names.** "Kitchen Lights", never `light.hue_color_lamp_3`.
3. **Big targets.** Tiles sized for a finger at arm's length. No tiny icons,
   no long-press-only actions for anything important.
4. **Scenes over switches.** "Movie Night", "Goodnight", "Leaving" do the
   work of ten toggles.
5. **Hide what isn't actionable.** Diagnostic sensors, battery levels, and
   update entities stay off the main screens. Show alerts only when something
   is wrong (door open, battery low, leak).
6. **Nothing breakable.** No sidebar, no edit mode, no settings on the
   tablet. Risky actions (unlock door, disarm alarm) ask for confirmation.
7. **Same layout every time.** Rooms appear in the same order and colours
   mean the same thing everywhere (amber = on/light, blue = climate,
   red = needs attention).

## Proposed layout (landscape tablet)

Navigation is a fixed bar of 4–5 big buttons along the bottom (or side).

| View | What's on it |
|------|--------------|
| **Home** | Clock and weather, who's home, alert strip (only when needed), scene buttons, the most-used lights/climate, what's playing |
| **Rooms** | One section per area: lights, blinds, fans, room temperature |
| **Climate** | Thermostat(s), indoor/outdoor temperature and humidity, short history graphs |
| **Security** | Locks, doors/windows, alarm, camera feeds, doorbell |
| **Media** | Speakers and TVs, volume, sources |

The screen dims after inactivity and wakes on motion (tablet camera via Fully
Kiosk) or a tap, with a dark theme after sunset.

## Planned tech stack

- **Home Assistant Sections view** (built-in) with **Tile cards** as the base
  — no custom cards required for the core.
- Optional via HACS: **Mushroom** / **Bubble Card** for polish,
  **kiosk-mode** to hide the header and sidebar, **Browser Mod** for popups.
- **Fully Kiosk Browser** (Plus licence) on the tablet: locks the tablet to
  the dashboard, motion wake, screen schedule, and a Home Assistant
  integration for remote control.
- A dedicated non-admin Home Assistant user for the tablet.

## Status

Waiting on inventory from the household (see `tools/entity_export.jinja`).
