# Adding things to the dashboard

The dashboard is split into small files so changes stay local:

```
dashboard/dashboard.yaml       list of tabs + kiosk settings
dashboard/views/<tab>.yaml     one file per tab
packages/wall_tablet.yaml      groups, helpers, alert sensors
themes/wall_tablet.yaml        colours
```

## What updates on its own

- **Garden beds**: one card per soil probe on **Outdoors**. Tap a bed's
  picture to choose what's planted (Seedling, Lettuce, Tomato, Pepper,
  Carrot, Herbs, Cucumber, Strawberry, Blueberry, Raspberry, Sunflower,
  Flowers, Succulent); the picture and the Dry/Wet levels follow. Tap the
  bed's title to rename it. Tap the small house/sun icon in the bottom-left
  corner to mark the bed indoors or outdoors (all start indoors). The levels
  follow the season: indoors by day length (shorter days, drier target),
  outdoors by the last 24 hours' average temperature (dormant when cold,
  wetter in a heat wave), and by each bed's soil temperature (cold soil,
  slow roots). How much the season matters depends on the plant: succulents
  and the berries rest harder in winter, lettuce, carrots and seedlings
  hardly at all. The status line shows this season's target, e.g.
  "Good · aim 30–56%". The 3-day graph plots moisture against that target
  (bottom third drier, middle on target, top wetter), so its colours follow
  the target too. A dry bed shows in the Home alert banner ("Tomatoes
  needs water"), except an outdoor bed while rain is forecast within 6 hours;
  a probe reading exactly 0% is treated as not in the ground and ignored.
  The season settings are `SEASON` in `tools/garden.py`. To add a probe,
  or add a plant type or change its levels, edit `BEDS` / `PLANT_TYPES` in
  `tools/garden.py` and run
  `python3 tools/garden.py` (`--gallery out.html` previews every picture).
- **Low batteries**: any battery sensor under 20% shows up in the alert
  banner and on **Devices**. To leave a device out, give its battery entity
  the label **Hide from tablet** in Home Assistant.
- **Now playing**: any speaker or TV that's playing shows on **Home**.
- **Lights on count / All lights off**: every light, including new ones.
- **Offline list** on **Devices**: any light, speaker, thermostat or vacuum
  that drops off.

## Add a light (or switch, sensor…) to a room

In `dashboard/views/rooms.yaml`, find the room and add a tile:

```yaml
      - type: tile
        entity: light.new_lamp
        name: Reading lamp
        tap_action: *toggle
        hold_action: *more_info
```

For a sensor, drop the two action lines and optionally add a mini graph:

```yaml
      - type: tile
        entity: sensor.something_temperature
        name: Temperature
        features:
          - type: trend-graph
            hours_to_show: 24
```

## Add a room

Copy any section in `rooms.yaml` (from `- type: grid` down to the next one)
and change the heading, icon and tiles.

## Change the floor plan

See [floorplan.md](floorplan.md). In the 3D version, devices are placed in
NeonPlan's editor. The 2D fallback is generated: edit `FLOORS` in
`tools/floorplan.py` and run `python3 tools/floorplan.py`.

## Add a tab

1. Copy an existing file in `dashboard/views/`, change `title` and `path`.
   (Tabs show their title as text; adding an `icon:` would replace the text
   with the icon.)
2. Add `- !include views/<file>.yaml` to `dashboard/dashboard.yaml`.

## Add a new kind of alert

In `packages/wall_tablet.yaml`, add an `if` block to **Household Alerts**:

```jinja
{%- if is_state('binary_sensor.leak_sensor', 'on') %}
  {%- set ns.a = ns.a + ['Water leak in the laundry room'] %}
{%- endif %}
```

It shows in the red banner on **Home** whenever it's true.

## Icons

Any icon from <https://pictogrammers.com/library/mdi/>, written as
`mdi:<name>`.
