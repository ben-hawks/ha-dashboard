# Home Assistant Wall Tablet Dashboard

A Home Assistant dashboard for a wall-mounted Lenovo Tab M10 HD (landscape).
It's meant to be easy for anyone in the house, not just whoever set it up.

- **Install:** [docs/install.md](docs/install.md)
- **Tablet setup:** [docs/tablet-setup.md](docs/tablet-setup.md)
- **LineageOS on the tablet:** [docs/lineageos.md](docs/lineageos.md)
- **Floor Plan tab (NeonPlan 3D):** [docs/floorplan.md](docs/floorplan.md)
- **Chicken Command Center (coop tablet):** [docs/coop-tablet.md](docs/coop-tablet.md)
- **Chicken counting feasibility test:** [docs/chicken-vision-test.md](docs/chicken-vision-test.md)
- **Frigate for the chicken cameras (Arc server):** [docs/frigate.md](docs/frigate.md)
- **Adding devices, rooms, tabs and alerts:** [docs/adding-things.md](docs/adding-things.md)

## Tabs

| Tab | What's on it |
|-----|--------------|
| **Home** | Greeting, who's home, outside/inside temperature, the 3D floor plan, clock, forecast, chicken comfort, main lights, "All lights off", thermostat, whatever's playing, vacuum, litter box. A red banner appears only when something needs attention. |
| **Floor Plan** | 3D model of both floors (NeonPlan 3D): rooms light up with their lights, tap a room for its devices, smoke/CO alerts on the plan. A flat 2D version is kept as a fallback |
| **Rooms** | Every light and speaker, grouped by room |
| **Climate** | Thermostat, hallway temperature/humidity, Airthings air quality |
| **Outdoors** | Weather band (station card, hourly + daily forecast, 24 h graphs; tap the forecast for a live radar map, which also appears by itself when rain, snow or storms are due) and the garden beds on one screen, then coop & shed. A card per garden bed (rename it and pick the plant on the dashboard from 13 illustrations incl. berries; dry beds raise a Home alert; moisture with plant-specific Dry/Good/Wet, soil temperature, EC, 3-day moisture graph), an illustrated WS90 weather station card (sky picture incl. snow, temperature, wind compass, rain, UV, pressure, 24 h graphs), chicken coop, shed power station |
| **Safety** | Smoke/CO status per room, alarm hub; "Silence all alarms" appears only while one is going off |
| **Devices** | Alerts, low batteries, offline devices, vacuum parts, cats, litter box and water fountain, backup power, shopping list, light/dark setting |

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
packages/garden.yaml         garden plant dropdowns + soil helper sensors (generated)
themes/wall_tablet.yaml      Aurora Dark + Aurora Light themes
tools/entity_export.jinja    lists your entities (paste into Developer Tools → Template)
tools/floorplan.py           traced house layout → 2D Floor Plan tab + NeonPlan 3D import file
tools/garden.py              garden bed cards + their package (plant dropdowns, helper sensors)
tools/weather.py             weather station card + its helper sensors (templates/weather_station.yaml)
tools/coop.py                coop screen's animated scene, chicken comfort + helpers (templates/coop.yaml)
tools/chicken_vision_test.py hen detection/door-counting test on exported camera clips (not part of HA)
frigate/                     Frigate NVR for the chicken cameras: docker compose + config (runs on the Arc server)
```

## Requirements

Home Assistant (current), HACS with **auto-entities**, **Kiosk Mode** and **mini-graph-card**,
**NeonPlan 3D** for the Floor Plan tab, and Fully Kiosk Browser (Plus) on the tablet, running LineageOS.
