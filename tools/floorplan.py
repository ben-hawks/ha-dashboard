#!/usr/bin/env python3
"""Generate the Floor Plan tab (dashboard/views/floorplan.yaml).

Draws each floor as an SVG from the room rectangles below, embeds it in a
picture-elements card, and places the interactive bits (light glow, icons,
temperatures, alarms) at each room's position, so the drawing and the
controls can't drift apart.

To change something (add a light to a room, move a label), edit ROOMS and
run:  python3 tools/floorplan.py
The SVGs are also written to floorplan/ for previewing in a browser.

Coordinates are in "plan units" traced from the listing floor plan; both
floors share the same frame so they render at the same scale.
"""

import base64
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Shared frame (x, y, width, height) for both floors.
VIEW_X, VIEW_Y, VIEW_W, VIEW_H = -10, 165, 750, 505

WALL = "#7f8896"
LABEL = "#9aa3b2"
GLOW = "#f4a940"

# Room fields:
#   name   label drawn on the plan (None = unlabeled closet/hall)
#   rect   (x0, y0, x1, y1)
#   light  tapping the room toggles this; the room glows while it's on
#   temp   sensor shown under the label; temp_tap = entity for its more-info
#   alarm  smoke/CO binary sensor; a red icon appears while it's on
#   icons  extra state icons: (entity, icon or None)
FLOORS = {
    "upstairs": {
        "title": "Upstairs",
        "rooms": [
            {"name": "Bedroom", "rect": (0, 175, 235, 392),
             "alarm": "binary_sensor.combination_alarm_2_alarm_status",
             "icons": [("media_player.bedroom_tv_2", None)]},
            {"name": "Bath", "rect": (235, 175, 363, 268), "small": True},
            {"name": "Bath", "rect": (235, 268, 363, 392), "small": True},
            {"name": "Kitchen", "rect": (363, 175, 565, 392),
             "alarm": "binary_sensor.combination_alarm_5_alarm_status",
             "icons": [("vacuum.acearchr_gmail_com", None)]},
            {"name": "Dining", "rect": (565, 175, 730, 392)},
            {"name": None, "rect": (0, 392, 105, 440)},
            {"name": "Hallway", "rect": (105, 392, 475, 452),
             "light": "light.hallway_lights",
             "temp": "sensor.hallway_temperature", "temp_tap": "climate.hallway",
             "inline": True},
            {"name": "Meg's Office", "rect": (0, 440, 160, 660),
             "alarm": "binary_sensor.combination_alarm_4_alarm_status"},
            {"name": None, "rect": (160, 452, 210, 660)},
            {"name": "Office", "rect": (210, 452, 365, 660),
             "light": "light.ben_s_office_lamp",
             "alarm": "binary_sensor.combination_alarm_3_alarm_status",
             "icons": [("light.smart_multicolor_bulb", "mdi:ceiling-fan-light")]},
            {"name": "Stairs", "rect": (365, 452, 475, 628), "small": True},
            {"name": "Living Room", "rect": (475, 392, 730, 660),
             "alarm": "binary_sensor.combination_alarm_alarm_status",
             "icons": [("media_player.living_room", None),
                       ("media_player.main_room_tv", None)]},
        ],
    },
    "downstairs": {
        "title": "Downstairs",
        "rooms": [
            {"name": "Garage", "rect": (0, 175, 343, 628),
             "light": "light.garage_lights"},
            {"name": "Laundry", "rect": (343, 175, 495, 397),
             "icons": [("sensor.turd_gobbler_9001_status_code", "mdi:cat")]},
            {"name": "Game Room", "rect": (495, 175, 730, 470),
             "light": "light.basement_lights"},
            {"name": None, "rect": (343, 397, 495, 470)},
            {"name": "Stairs", "rect": (343, 470, 425, 628), "small": True},
            {"name": None, "rect": (425, 470, 480, 560)},
            {"name": "Work Office", "rect": (480, 470, 730, 628),
             "alarm": "binary_sensor.work_office_base_station_alarm_status",
             "temp": "sensor.airthings_wave_055159_temperature"},
        ],
    },
}


def svg_for(floor):
    rooms = floor["rooms"]
    xs = [r["rect"][0] for r in rooms] + [r["rect"][2] for r in rooms]
    ys = [r["rect"][1] for r in rooms] + [r["rect"][3] for r in rooms]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{VIEW_X} {VIEW_Y} {VIEW_W} {VIEW_H}">',
        f'<g fill="none" stroke="{WALL}" stroke-linejoin="round">',
    ]
    for r in rooms:
        x0, y0, x1, y1 = r["rect"]
        parts.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" '
                     f'height="{y1 - y0}" stroke-width="3"/>')
    # Thicker outline around the whole floor.
    parts.append(f'<rect x="{min(xs)}" y="{min(ys)}" width="{max(xs) - min(xs)}" '
                 f'height="{max(ys) - min(ys)}" stroke-width="7"/>')
    parts.append("</g>")
    parts.append(f'<g fill="{LABEL}" font-family="Roboto, sans-serif" '
                 f'text-anchor="middle">')
    for r in rooms:
        if not r["name"]:
            continue
        x0, y0, x1, y1 = r["rect"]
        size = 13 if r.get("small") else 17
        if r.get("inline"):
            # Short, wide rooms: label on the left, controls to the right.
            parts.append(f'<text x="{x0 + 50}" y="{(y0 + y1) / 2 + 6}" '
                         f'font-size="{size}">{r["name"]}</text>')
        else:
            parts.append(f'<text x="{(x0 + x1) / 2}" y="{y0 + 26}" '
                         f'font-size="{size}">{r["name"].replace("&", "&amp;")}</text>')
    parts.append("</g></svg>")
    return "".join(parts)


def pct(x, y):
    """Plan units → picture-elements left/top percentages."""
    return (f"{(x - VIEW_X) / VIEW_W * 100:.1f}%",
            f"{(y - VIEW_Y) / VIEW_H * 100:.1f}%")


def solid(color, opacity):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" '
           f'preserveAspectRatio="none"><rect width="1" height="1" '
           f'fill="{color}" fill-opacity="{opacity}"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


TRANSPARENT = solid("#000000", 0)
LIT = solid(GLOW, 0.3)


def elements_for(floor):
    out = []
    for r in floor["rooms"]:
        x0, y0, x1, y1 = r["rect"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        inline = r.get("inline")

        if r.get("light"):
            left, top = pct(cx, cy)
            out.append({
                "type": "image",
                "entity": r["light"],
                "image": TRANSPARENT,
                "state_image": {"on": LIT},
                "tap_action": {"action": "toggle"},
                "hold_action": {"action": "more-info"},
                "style": {
                    "left": left, "top": top,
                    "width": f"{(x1 - x0) / VIEW_W * 100:.1f}%",
                    "height": f"{(y1 - y0) / VIEW_H * 100:.1f}%",
                },
            })

        # Row of icons: the room's light first, then any extras.
        icons = ([(r["light"], None)] if r.get("light") else []) + r.get("icons", [])
        icon_y = cy if inline else cy + 4
        start_x = (x0 + 115) if inline else cx - (len(icons) - 1) * 22
        for i, (entity, icon) in enumerate(icons):
            left, top = pct(start_x + i * 44, icon_y)
            el = {"type": "state-icon", "entity": entity,
                  "tap_action": {"action": "toggle" if entity.startswith("light.")
                                 else "more-info"},
                  "hold_action": {"action": "more-info"},
                  "style": {"left": left, "top": top, "--mdc-icon-size": "30px"}}
            if icon:
                el["icon"] = icon
            out.append(el)

        if r.get("temp"):
            tx = (x1 - 60) if inline else cx
            ty = cy if inline else cy + 40
            left, top = pct(tx, ty)
            out.append({"type": "state-label", "entity": r["temp"],
                        "tap_action": {"action": "more-info",
                                       "entity": r.get("temp_tap", r["temp"])},
                        "style": {"left": left, "top": top, "font-size": "15px",
                                  "color": "var(--primary-text-color)"}})

        if r.get("alarm"):
            # Centred under the room name, where it can't cover anything.
            left, top = pct(cx, y0 + 58)
            out.append({"type": "conditional",
                        "conditions": [{"entity": r["alarm"], "state": "on"}],
                        "elements": [{"type": "state-icon", "entity": r["alarm"],
                                      "icon": "mdi:fire-alert",
                                      "style": {"left": left, "top": top,
                                                "color": "#e5484d",
                                                "--mdc-icon-size": "34px"}}]})
    return out


def main():
    (ROOT / "floorplan").mkdir(exist_ok=True)
    cards = []
    for key, floor in FLOORS.items():
        svg = svg_for(floor)
        (ROOT / "floorplan" / f"{key}.svg").write_text(svg + "\n")
        cards.append({
            "type": "picture-elements",
            "title": floor["title"],
            "image": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
            "elements": elements_for(floor),
        })

    view = {
        "title": "Floor Plan",
        "path": "floorplan",
        "type": "panel",
        "theme": "Wall Tablet",
        "cards": [{"type": "horizontal-stack", "cards": cards}],
    }
    header = ("# GENERATED by tools/floorplan.py: edit ROOMS there and re-run it,\n"
              "# don't edit this file by hand.\n")
    text = yaml.safe_dump(view, sort_keys=False, width=10_000, allow_unicode=True)
    (ROOT / "dashboard" / "views" / "floorplan.yaml").write_text(header + text)
    print("wrote dashboard/views/floorplan.yaml and floorplan/*.svg")


if __name__ == "__main__":
    main()
