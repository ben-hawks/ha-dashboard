#!/usr/bin/env python3
"""Generate the Floor Plan tab (dashboard/views/floorplan.yaml).

Draws each floor as an SVG from the room rectangles below, embeds it in a
picture-elements card, and places the interactive bits (light glow, icons,
temperatures, alarms) at each room's position, so the drawing and the
controls can't drift apart.

To change something (add a light to a room, move a label), edit ROOMS and
run:  python3 tools/floorplan.py
The SVGs are also written to floorplan/ for previewing in a browser, along
with floorplan/neonplan-import.json for NeonPlan 3D (see docs/floorplan.md).

Coordinates are in "plan units" traced from the listing floor plan; both
floors share the same frame so they render at the same scale.
"""

import base64
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Shared frame (x, y, width, height) for both floors.
VIEW_X, VIEW_Y, VIEW_W, VIEW_H = -10, 165, 750, 505

WALL = "#7f8896"
LABEL = "#9aa3b2"
GLOW = "#f4a940"

# Plan units → metres, from the listing's dimensions (the 13'0" primary
# bedroom is 235 units wide). Used for the NeonPlan 3D export.
METRES_PER_UNIT = 3.962 / 235

# Room fields:
#   name   label drawn on the plan (None = unlabeled closet/hall)
#   area   Home Assistant area name, if different from the label; NeonPlan
#          rooms get this name so they link to the right area
#   rect   (x0, y0, x1, y1); neighbouring rooms share exact edge values.
#          Labels, icons and the light glow are placed within it.
#   label_y  optional label position (default: near the top of the room)
#   points optional outline for non-rectangular rooms (corners in order);
#          the rect then marks the main part of the room
#   light  tapping the room toggles this; the room glows while it's on
#   temp   sensor shown under the label; temp_tap = entity for its more-info
#   alarm  smoke/CO binary sensor; a red icon appears while it's on
#   icons  extra state icons: (entity, icon or None)
# Floor fields (NeonPlan 3D only):
#   elevation  metres above the lowest floor
#   doors      (x, y, width in metres) on a room edge; wide ones are openings
#   windows    (x, y, width in metres) on an outside wall
#   stairs     flights for NeonPlan: (x0, y0, x1, y1, bottom end "south" or
#              "north", elevation and height in metres above this floor)
#   treads     rectangles drawn with step lines on the 2D plan
FLOORS = {
    "upstairs": {
        "title": "Upstairs",
        "elevation": 2.4,
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
            {"name": "Hallway", "rect": (160, 392, 475, 452),
             "light": "light.hallway_lights",
             "temp": "sensor.hallway_temperature", "temp_tap": "climate.hallway",
             "inline": True},
            # The gap between the offices is two closets, drawn as part of
            # their rooms: the top one belongs to the Office, the bottom one
            # to Meg's office.
            {"name": "Meg's Office", "rect": (0, 392, 160, 660),
             "points": [(0, 392), (160, 392), (160, 556), (210, 556),
                        (210, 660), (0, 660)],
             "alarm": "binary_sensor.combination_alarm_4_alarm_status"},
            {"name": "Office", "rect": (210, 452, 363, 660),
             "points": [(160, 452), (363, 452), (363, 660), (210, 660),
                        (210, 556), (160, 556)],
             "light": "light.ben_s_office_lamp",
             "alarm": "binary_sensor.combination_alarm_3_alarm_status",
             "icons": [("light.smart_multicolor_bulb", "mdi:ceiling-fan-light")]},
            # Closet at the top of the down flight, opening onto the hallway.
            {"name": None, "area": "Closet", "rect": (363, 452, 419, 490)},
            {"name": "Foyer", "rect": (363, 452, 475, 628), "small": True,
             "label_y": 607,
             "points": [(419, 452), (475, 452), (475, 628), (363, 628),
                        (363, 490), (419, 490)]},
            {"name": "Living Room", "rect": (475, 392, 730, 660),
             "alarm": "binary_sensor.combination_alarm_alarm_status",
             "icons": [("media_player.living_room", None),
                       ("media_player.main_room_tv", None)]},
        ],
        "doors": [
            (200, 392, 0.8),   # bedroom → hallway
            (235, 215, 0.7),   # bedroom → bath
            (290, 392, 0.7),   # hallway → bath
            (435, 392, 1.1),   # hallway → kitchen (opening)
            (565, 283, 3.0),   # kitchen ↔ dining (open plan)
            (647, 392, 2.6),   # dining ↔ living room (open plan)
            (475, 422, 0.9),   # hallway → living room (opening)
            (160, 422, 0.8),   # hallway → Meg's office
            (245, 452, 0.8),   # hallway → office
            (447, 452, 0.9),   # hallway → stairs
            (391, 452, 0.6),   # hallway → closet over the stairs
            (420, 628, 0.9),   # front door
        ],
        "windows": [
            (120, 175, 1.8), (300, 175, 0.6), (442, 175, 0.9), (635, 175, 1.8),
            (82, 660, 1.0), (287, 660, 1.0),
            # Living room front: two side windows flanking a wider centre one.
            (547, 660, 0.61), (602, 660, 1.26), (658, 660, 0.61),
        ],
        # Split foyer: from the landing by the front door, the left flight
        # goes down and the right flight goes up (3D: see downstairs).
        "treads": [(363, 490, 419, 575), (419, 475, 475, 575)],
    },
    "downstairs": {
        "title": "Downstairs",
        "elevation": 0,
        "rooms": [
            {"name": "Garage", "rect": (0, 175, 343, 628),
             "light": "light.garage_lights"},
            {"name": "Laundry", "area": "Laundry Room", "rect": (343, 175, 495, 397),
             "icons": [("sensor.turd_gobbler_9001_status_code", "mdi:cat")]},
            {"name": "Game Room", "rect": (495, 175, 730, 470),
             "light": "light.basement_lights"},
            {"name": None, "area": "Hall", "rect": (343, 397, 495, 470)},
            {"name": None, "area": "Stairs", "rect": (343, 470, 425, 575)},
            # One L-shaped closet: beside the stairs and under the entry
            # landing at their foot.
            {"name": None, "area": "Closet", "rect": (425, 470, 480, 628),
             "points": [(425, 470), (480, 470), (480, 628), (343, 628),
                        (343, 575), (425, 575)]},
            {"name": "Work Office", "rect": (480, 470, 730, 628),
             "alarm": "binary_sensor.work_office_base_station_alarm_status",
             "temp": "sensor.airthings_wave_055159_temperature"},
        ],
        "doors": [
            (343, 433, 0.8),   # hall → garage
            (455, 397, 0.8),   # hall → laundry
            (495, 433, 1.2),   # hall → game room (opening)
            (384, 470, 0.8),   # hall → stairs
            (384, 575, 0.6),   # stairs → closet under the landing
            (520, 470, 0.8),   # game room → work office
        ],
        "windows": [
            (417, 175, 0.6), (647, 175, 2.0), (610, 628, 1.6),
        ],
        # Both foyer flights, placed on this floor so heights stay positive.
        # The entry landing is half a storey up (1.2 m): the down flight runs
        # from it to this floor's hall, the up flight from it to upstairs.
        "stairs": [
            (363, 490, 419, 575, "north", 0, 1.2),    # down: landing → hall
            (419, 475, 475, 575, "south", 1.2, 1.2),  # up: landing → upstairs
        ],
        "treads": [(343, 475, 425, 575)],
    },
}


def outline(room):
    x0, y0, x1, y1 = room["rect"]
    return list(room.get("points") or [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def with_shared_corners(room, rooms):
    """Outline plus any neighbour's corner lying on one of its edges, so rooms
    that share part of a wall have matching vertices (NeonPlan joins them)."""
    pts = outline(room)
    others = {p for r in rooms if r is not room for p in outline(r)}
    out = []
    for i, (ax, ay) in enumerate(pts):
        bx, by = pts[(i + 1) % len(pts)]
        out.append((ax, ay))
        between = [p for p in others if p not in pts and (
            (ax == bx == p[0] and min(ay, by) < p[1] < max(ay, by)) or
            (ay == by == p[1] and min(ax, bx) < p[0] < max(ax, bx)))]
        between.sort(key=lambda p: abs(p[0] - ax) + abs(p[1] - ay))
        out.extend(between)
    return out


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
        pts = " ".join(f"{x},{y}" for x, y in outline(r))
        parts.append(f'<polygon points="{pts}" stroke-width="3"/>')
    for x0, y0, x1, y1 in floor.get("treads", []):
        parts.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" '
                     f'height="{y1 - y0}" stroke-width="2"/>')
        steps = 7
        for i in range(1, steps):
            y = y0 + (y1 - y0) * i / steps
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                         f'stroke-width="1.5"/>')
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
            parts.append(f'<text x="{(x0 + x1) / 2}" y="{r.get("label_y", y0 + 26)}" '
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


def m(v):
    return round(v * METRES_PER_UNIT, 3)


def neonplan_import():
    """NeonPlan 3D import file: metres, x right, z down, lowest floor first."""
    floors = []
    for floor in sorted(FLOORS.values(), key=lambda f: f["elevation"]):
        def pt(x, y):
            return [m(x), m(y - 175)]
        floors.append({
            "name": floor["title"],
            "elevation": floor["elevation"],
            "height": 2.4,
            "rooms": [{"name": r.get("area") or r["name"],
                       "points": [pt(x, y) for x, y in
                                  with_shared_corners(r, floor["rooms"])]}
                      for r in floor["rooms"]],
            "doors": [{"at": pt(x, y), "width": w} for x, y, w in floor["doors"]],
            "windows": [{"at": pt(x, y), "width": w, "height": 1.2, "sill": 0.9}
                        for x, y, w in floor["windows"]],
            # Rotation 0 puts the front (bottom step) facing down the plan.
            "furniture": [{"type": "stairs",
                           "at": pt((x0 + x1) / 2, (y0 + y1) / 2),
                           "width": m(x1 - x0), "depth": m(y1 - y0),
                           "height": height, "elevation": elevation,
                           "rotation": 0 if bottom == "south" else 180}
                          for x0, y0, x1, y1, bottom, elevation, height
                          in floor.get("stairs", [])],
        })
    return {"format": "neonplan-import", "units": "m", "rooms_at": "centre",
            "floors": floors}


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
    (ROOT / "floorplan" / "neonplan-import.json").write_text(
        json.dumps(neonplan_import(), indent=2) + "\n")
    print("wrote dashboard/views/floorplan.yaml, floorplan/*.svg "
          "and floorplan/neonplan-import.json")


if __name__ == "__main__":
    main()
