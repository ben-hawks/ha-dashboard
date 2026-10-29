# Home Assistant Wall Tablet Dashboard

A Home Assistant dashboard for a wall-mounted Lenovo Tab M10 HD (landscape).
It's meant to be easy for anyone in the house, not just whoever set it up.

- **Install:** [docs/install.md](docs/install.md)
- **Tablet setup:** [docs/tablet-setup.md](docs/tablet-setup.md)
- **LineageOS on the tablet:** [docs/lineageos.md](docs/lineageos.md)
- **Floor Plan tab (NeonPlan 3D):** [docs/floorplan.md](docs/floorplan.md)
- **Chicken Command Center (coop tablet):** [docs/coop-tablet.md](docs/coop-tablet.md)
- **Adding devices, rooms, tabs and alerts:** [docs/adding-things.md](docs/adding-things.md)

## Tabs

| Tab | What's on it |
|-----|--------------|
| **Home** | Greeting, who's home, outside/inside temperature, the 3D floor plan, clock, forecast, main lights, "All lights off", thermostat, whatever's playing, vacuum, litter box. A red banner appears only when something needs attention. |
| **Floor Plan** | 3D model of both floors (NeonPlan 3D): rooms light up with their lights, tap a room for its devices, smoke/CO alerts on the plan. A flat 2D version is kept as a fallback |
| **Rooms** | Every light and speaker, grouped by room |
| **Climate** | Thermostat, hallway temperature/humidity, Airthings air quality |
| **Outdoors** | Forecast, Ecowitt weather station and soil sensors (fill in automatically), chicken coop, shed power station |
| **Safety** | Smoke/CO status per room, alarm hub; "Silence all alarms" appears only while one is going off |
| **Devices** | Alerts, low batteries, offline devices, vacuum parts, cats and litter box, backup power, shopping list, light/dark setting |

## Design rules

1. **One glance, one tap.** Tapping a light toggles it; holding opens
   brightness and colour.
2. **Plain names.** "Garage", not `light.smart_multicolor_bulb_2`.
3. **Hide what isn't actionable.** Diagnostics stay off the screens; alerts
   only appear when something is wrong.
4. **Nothing breakable.** The tablet user has no sidebar, menus or edit mode.
5. **Grows on its own where it can.** New soil sensors, low batteries, offline
   devices and anything playing show up without editing the dashboard.

## Layout

```
dashboard/dashboard.yaml     tab list + kiosk settings
dashboard/views/*.yaml       one file per tab
dashboard/chicken_coop.yaml  Chicken Command Center (coop tablet)
packages/wall_tablet.yaml    light groups, helpers, alert sensors, theme + hallway automations
themes/wall_tablet.yaml      dark + light theme
tools/entity_export.jinja    lists your entities (paste into Developer Tools → Template)
tools/floorplan.py           traced house layout → 2D Floor Plan tab + NeonPlan 3D import file
```

## Requirements

Home Assistant (current), HACS with **auto-entities**, **Kiosk Mode** and
**Browser Mod** (plus **NeonPlan 3D** for the Floor Plan tab), and Fully Kiosk Browser (Plus) on the tablet, running LineageOS.
