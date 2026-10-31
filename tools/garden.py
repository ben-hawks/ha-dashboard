#!/usr/bin/env python3
"""Generate the Garden section of the Outdoors tab and its package.

Writes:
  dashboard/views/garden_section.yaml   one card per soil probe: plant
                                        illustration, moisture, status,
                                        soil temperature, EC and a 3-day
                                        moisture graph
  packages/garden.yaml                  per bed: a name box
                                        (input_text.garden_1_name), a plant
                                        dropdown (input_select.garden_1_plant)
                                        and helper sensors with fixed IDs
                                        (sensor.garden_1_moisture, ...), plus
                                        sensor.garden_needs_water for alerts

The plant is chosen on the dashboard: tap a bed's picture and pick from the
list. The picture and the Dry/Good/Wet thresholds follow the choice. Tap the
bed's title to rename it.

The helper sensors find each probe's readings by channel number at the end
of the Ecowitt entity ID (…soil_moisture_1, …soil_temperature_1, …), so
the dashboard doesn't depend on the gateway's name or area prefix.

To add a probe, rename a bed, or add a plant type (art + thresholds), edit
BEDS / PLANT_TYPES and run:  python3 tools/garden.py
Preview every illustration:   python3 tools/garden.py --gallery out.html
"""

import base64
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# One entry per soil probe. channel = the probe's number in Ecowitt.
BEDS = [
    {"channel": 1, "name": "Bed 1"},
    {"channel": 2, "name": "Bed 2"},
    {"channel": 3, "name": "Bed 3"},
    {"channel": 4, "name": "Bed 4"},
]

# A probe battery (1.5 V AA) under this is flagged on its card.
BATTERY_LOW_V = 1.2

LEAF = "#5aa84e"
LEAF_LIGHT = "#7cc96b"
LEAF_DARK = "#3f8f45"
STEM = "#4a8a40"
WOOD = "#7a5a3a"
RED = "#e0533d"
LABEL = "#9aa3b2"

# ---------------------------------------------------------------------------
# Illustrations on a 300×160 canvas: a terracotta pot with the plant on the
# left; the right side is left free for the readings. The soil line is at
# y≈109, centred on x=65.
# ---------------------------------------------------------------------------

POT = (
    '<ellipse cx="65" cy="153" rx="34" ry="4" fill="#000" fill-opacity="0.15"/>'
    '<path d="M36 118 L94 118 L87 152 L43 152 Z" fill="#c8714a"/>'
    '<rect x="30" y="108" width="70" height="12" rx="3" fill="#b5603c"/>'
    '<ellipse cx="65" cy="109" rx="31" ry="4" fill="#5b3a29"/>'
)


def leaf(x, y, length, angle, color=LEAF, width=0.38):
    """A pointed leaf whose base sits at (x, y), pointing at `angle` degrees."""
    w = length * width
    return (f'<path transform="translate({x} {y}) rotate({angle})" '
            f'd="M0 0 C{w:.1f} {-length * 0.3:.1f} {w:.1f} {-length * 0.75:.1f} 0 {-length} '
            f'C{-w:.1f} {-length * 0.75:.1f} {-w:.1f} {-length * 0.3:.1f} 0 0 Z" fill="{color}"/>')


def stems(d, color=STEM, width=3):
    return (f'<path d="{d}" stroke="{color}" stroke-width="{width}" fill="none" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def berry(x, y, r, color, shine=0.35):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
            f'<circle cx="{x - r * 0.35:.1f}" cy="{y - r * 0.35:.1f}" r="{r * 0.28:.1f}" '
            f'fill="#fff" fill-opacity="{shine}"/>')


def art_seedling():
    return (stems("M65 109 C65 96 64 86 66 74", width=3.5)
            + leaf(66, 80, 30, -62) + leaf(66, 74, 34, 55, LEAF_LIGHT) + leaf(66, 72, 16, -5))


def art_lettuce():
    parts = []
    for angle, length, color in [(-70, 40, LEAF), (70, 40, LEAF), (-40, 46, LEAF_LIGHT),
                                 (40, 46, LEAF_LIGHT), (-15, 50, LEAF), (15, 50, LEAF),
                                 (0, 42, LEAF_LIGHT)]:
        w = length * 0.55
        parts.append(f'<path transform="translate(65 108) rotate({angle})" '
                     f'd="M0 0 C{w} {-length * 0.25} {w} {-length * 0.95} 0 {-length} '
                     f'C{-w} {-length * 0.95} {-w} {-length * 0.25} 0 0 Z" '
                     f'fill="{color}" stroke="{LEAF_DARK}" stroke-width="1"/>')
    return "".join(parts)


def art_tomato():
    fruit = "".join(
        berry(x, y, r, RED)
        + stems(f"M{x - 3} {y - r + 1} L{x} {y - r - 3} L{x + 3} {y - r + 1}", width=2)
        for x, y, r in [(52, 80, 7), (80, 66, 8), (74, 92, 6.5)])
    return (stems("M65 109 L65 40 M65 88 L48 70 M65 72 L84 56 M65 56 L50 44")
            + leaf(48, 70, 18, -50) + leaf(84, 56, 18, 50) + leaf(50, 44, 16, -40, LEAF_LIGHT)
            + leaf(65, 40, 18, 0) + leaf(65, 96, 16, 60, LEAF_LIGHT) + fruit)


def art_pepper():
    def pepper(x, y, color, length=24):
        return (f'<path transform="translate({x} {y})" d="M-5 0 C-6 {length * 0.5} -2 {length * 0.85} 1 {length} '
                f'C4 {length * 0.8} 7 {length * 0.45} 5 0 Z" fill="{color}"/>'
                + stems(f"M{x - 2} {y + 1} L{x} {y - 5}", width=2.5))
    return (stems("M65 109 L65 46 M65 86 L46 70 M65 74 L84 60 M65 60 L50 48")
            + leaf(46, 70, 20, -55) + leaf(84, 60, 20, 55) + leaf(50, 48, 18, -35, LEAF_LIGHT)
            + leaf(65, 46, 20, 0) + leaf(65, 94, 16, 65, LEAF_LIGHT) + leaf(84, 60, 14, 120, LEAF_DARK)
            + pepper(54, 74, RED) + pepper(76, 64, "#f08a2e", 21))


def art_carrot():
    fronds = ""
    for angle in (-38, -14, 10, 32):
        fronds += f'<g transform="translate(65 104) rotate({angle})">'
        fronds += stems("M0 0 L0 -58", width=2)
        for i, y in enumerate(range(-14, -58, -9)):
            fronds += leaf(0, y, 13 - i, -55, LEAF_LIGHT, 0.3) + leaf(0, y, 13 - i, 55, LEAF, 0.3)
        fronds += "</g>"
    return fronds + '<path d="M54 104 Q65 98 76 104 L72 110 L58 110 Z" fill="#f08a2e"/>'


def art_herbs():
    out = stems("M56 109 L50 58 M65 109 L65 48 M74 109 L80 60", width=2.5)
    for x0, y0, x1, y1 in [(56, 109, 50, 58), (65, 109, 65, 48), (74, 109, 80, 60)]:
        for t in (0.35, 0.6, 0.85, 1.0):
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            out += (f'<ellipse cx="{x - 6:.1f}" cy="{y - 2:.1f}" rx="5" ry="8" fill="{LEAF_LIGHT}" '
                    f'transform="rotate(-50 {x - 6:.1f} {y - 2:.1f})"/>'
                    f'<ellipse cx="{x + 6:.1f}" cy="{y - 2:.1f}" rx="5" ry="8" fill="{LEAF}" '
                    f'transform="rotate(50 {x + 6:.1f} {y - 2:.1f})"/>')
    return out


def art_cucumber():
    def big_leaf(x, y, r, color):
        return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
                + stems(f"M{x} {y + r * 0.6} L{x} {y - r * 0.7} M{x} {y} L{x - r * 0.6} {y - r * 0.4} "
                        f"M{x} {y} L{x + r * 0.6} {y - r * 0.4}", color=LEAF_DARK, width=1.2))
    cucumber = ('<rect x="68" y="74" width="9" height="30" rx="4.5" fill="#3f7f3a" '
                'transform="rotate(-15 72 89)"/>'
                + "".join(f'<circle cx="{70 + (i % 2) * 4}" cy="{80 + i * 5}" r="0.9" fill="#cde8b5"/>'
                          for i in range(4)))
    flower = "".join(f'<ellipse cx="88" cy="56" rx="3" ry="6" fill="#f6c431" transform="rotate({a} 88 61)"/>'
                     for a in range(0, 360, 72)) + '<circle cx="88" cy="61" r="2.5" fill="#e09a1a"/>'
    return (stems("M65 109 C60 90 50 80 46 66 M65 109 C70 92 80 82 88 64 "
                  "M46 66 C40 60 44 52 50 56", width=2.5)
            + big_leaf(44, 72, 15, LEAF) + big_leaf(60, 56, 13, LEAF_LIGHT)
            + cucumber + flower)


def art_strawberry():
    def trifoliate(x, y, color):
        return "".join(f'<ellipse cx="{x + dx}" cy="{y + dy}" rx="7" ry="10" fill="{color}" '
                       f'transform="rotate({a} {x + dx} {y + dy})"/>'
                       for dx, dy, a in [(-7, 0, -40), (0, -6, 0), (7, 0, 40)])

    def fruit(x, y):
        seeds = "".join(f'<circle cx="{x + sx}" cy="{y + sy}" r="0.8" fill="#f7d046"/>'
                        for sx, sy in [(-3, 4), (2, 3), (-1, 8), (3, 9), (-4, 10), (0, 13)])
        return (f'<path transform="translate({x} {y})" d="M0 0 C9 -1 11 8 0 18 C-11 8 -9 -1 0 0 Z" fill="{RED}"/>'
                + seeds
                + f'<path d="M{x - 5} {y + 1} L{x} {y - 3} L{x + 5} {y + 1} L{x} {y + 2} Z" fill="{STEM}"/>')
    flower = ("".join(f'<circle cx="{60 + 4 * dx}" cy="{64 + 4 * dy}" r="3.2" fill="#fff"/>'
                      for dx, dy in [(0, -1), (0.95, -0.3), (0.6, 0.8), (-0.6, 0.8), (-0.95, -0.3)])
              + '<circle cx="60" cy="64" r="2" fill="#f7d046"/>')
    return (stems("M65 109 Q55 95 44 80 M65 109 L66 72 M65 109 Q78 95 88 82 M65 109 Q62 84 60 66", width=2)
            + trifoliate(44, 76, LEAF) + trifoliate(66, 68, LEAF_LIGHT) + trifoliate(88, 78, LEAF)
            + flower + fruit(50, 90) + fruit(78, 92))


def art_blueberry():
    blue = "#4a62c9"
    out = stems("M65 109 L58 58 M65 109 L74 54 M61 86 L44 66 M69 80 L90 64", color=WOOD, width=3)
    for x, y, a in [(58, 58, -10), (74, 54, 15), (44, 66, -45), (90, 64, 50), (52, 74, -70),
                    (80, 72, 70), (60, 70, -30), (70, 66, 30)]:
        out += leaf(x, y, 13, a, LEAF if a % 20 else LEAF_LIGHT, 0.42)
    for x, y in [(46, 72), (51, 76), (42, 77), (84, 70), (89, 74), (80, 75), (64, 62), (69, 65)]:
        out += berry(x, y, 4.2, blue, 0.4)
    return out


def art_raspberry():
    def drupe(x, y):
        return "".join(f'<circle cx="{x + dx}" cy="{y + dy}" r="2.6" fill="#d6335c"/>'
                       for dx, dy in [(0, 0), (-3, 2), (3, 2), (-2, 5), (2, 5), (0, 8), (0, 3)])
    out = stems("M60 109 Q54 72 40 50 M68 109 Q76 72 92 52", color="#6a8a3a", width=3)
    for x, y, a in [(46, 62, -40), (52, 78, -60), (86, 62, 40), (78, 78, 60), (41, 51, -15), (91, 53, 15)]:
        out += leaf(x, y, 15, a) + leaf(x, y, 11, a - 35, LEAF_LIGHT) + leaf(x, y, 11, a + 35, LEAF_LIGHT)
    return out + drupe(50, 84) + drupe(82, 84) + drupe(62, 66)


def art_sunflower():
    petals = "".join(f'<ellipse cx="65" cy="22" rx="4" ry="11" fill="#f6c431" transform="rotate({a} 65 36)"/>'
                     for a in range(0, 360, 30))
    seeds = "".join(f'<circle cx="{65 + dx}" cy="{36 + dy}" r="1" fill="#3d2814"/>'
                    for dx, dy in [(-3, -3), (3, -3), (0, 0), (-3, 3), (3, 3), (0, -5), (0, 5)])
    return (stems("M65 109 L65 44", width=4) + leaf(65, 96, 28, -62) + leaf(65, 80, 26, 60, LEAF_LIGHT)
            + leaf(65, 64, 20, -55, LEAF_LIGHT) + petals + '<circle cx="65" cy="36" r="9" fill="#6b4423"/>'
            + seeds)


def art_flowers():
    petals = "".join(f'<ellipse cx="65" cy="40" rx="7" ry="13" fill="{c}" transform="rotate({a} 65 52)"/>'
                     for a, c in zip(range(0, 360, 45), ["#e86fa0", "#f08cb4"] * 4))
    return (stems("M65 109 C64 90 66 72 65 58", width=3.5)
            + leaf(65, 96, 26, -58) + leaf(65, 86, 26, 58, LEAF_LIGHT)
            + petals + '<circle cx="65" cy="52" r="7" fill="#f7d046"/>')


def art_succulent():
    """An echeveria-style rosette: three layers of thick pointed leaves."""
    out = ""
    for angles, length, color in [(range(-75, 76, 25), 28, "#5f9a78"),
                                  (range(-50, 51, 25), 36, "#7fb592"),
                                  (range(-20, 21, 20), 30, "#a3cfae")]:
        for a in angles:
            out += leaf(65, 106, length, a, color, 0.42).replace(
                "/>", ' stroke="#3f6f53" stroke-width="1.2"/>')
    return out + '<ellipse cx="65" cy="80" rx="2" ry="3" fill="#d98aa0"/>'


# Plant types offered on the dashboard. dry/wet: moisture % below/above which
# the bed shows Dry/Wet. Starting points; adjust to taste.
PLANT_TYPES = {
    "Seedling":   (art_seedling, 30, 70),
    "Lettuce":    (art_lettuce, 35, 70),
    "Tomato":     (art_tomato, 30, 65),
    "Pepper":     (art_pepper, 30, 65),
    "Carrot":     (art_carrot, 30, 65),
    "Herbs":      (art_herbs, 25, 60),
    "Cucumber":   (art_cucumber, 35, 75),
    "Strawberry": (art_strawberry, 35, 70),
    "Blueberry":  (art_blueberry, 40, 75),
    "Raspberry":  (art_raspberry, 35, 70),
    "Sunflower":  (art_sunflower, 25, 60),
    "Flowers":    (art_flowers, 30, 70),
    "Succulent":  (art_succulent, 10, 40),
}
DEFAULT_PLANT = "Seedling"


def plant_svg(kind):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 160">'
            + PLANT_TYPES[kind][0]() + POT + '</svg>')


BLANK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 160"></svg>'


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def at(x, y):
    """Canvas point → picture-elements position."""
    return {"left": f"{x / 300 * 100:.1f}%", "top": f"{y / 160 * 100:.1f}%"}


# Shared by every bed's card; yaml.dump turns the repeats into anchors.
PLANT_IMAGES = {kind: data_uri(plant_svg(kind)) for kind in PLANT_TYPES}


def card_for(bed):
    c = bed["channel"]
    plant = f"input_select.garden_{c}_plant"
    moisture = f"sensor.garden_{c}_moisture"
    status = f"sensor.garden_{c}_status"
    small = {"font-size": "13px", "color": "var(--secondary-text-color)"}
    elements = [
        # The plant picture follows the bed's dropdown; tap it to change.
        {"type": "image", "entity": plant, "image": PLANT_IMAGES[DEFAULT_PLANT],
         "state_image": PLANT_IMAGES, "tap_action": {"action": "more-info"},
         "style": {"left": "50%", "top": "50%", "width": "100%"}},
        # "<name> · <plant>"; tap it to rename the bed.
        {"type": "state-label", "entity": f"sensor.garden_{c}_title",
         "tap_action": {"action": "more-info", "entity": f"input_text.garden_{c}_name"},
         "style": {**at(210, 26), "font-size": "15px", "font-weight": "500",
                   "color": "var(--secondary-text-color)", "white-space": "nowrap"}},
        {"type": "state-label", "entity": moisture,
         "style": {**at(212, 72), "font-size": "34px", "font-weight": "600",
                   "color": "var(--primary-text-color)"}},
        {"type": "state-label", "entity": status, "style": {**at(212, 104), **small}},
        {"type": "state-label", "entity": f"sensor.garden_{c}_soil_temperature",
         "style": {**at(170, 140), **small}},
        {"type": "state-label", "entity": f"sensor.garden_{c}_conductivity",
         "style": {**at(250, 140), **small}},
    ]
    for state, icon, color in [("Dry", "mdi:water-off-outline", "#e0a03a"),
                               ("Good", "mdi:water-check", "#4caf50"),
                               ("Wet", "mdi:water-alert", "#3b82f6")]:
        elements.append({
            "type": "conditional",
            "conditions": [{"entity": status, "state": state}],
            "elements": [{"type": "icon", "icon": icon, "tap_action": {"action": "none"},
                          "style": {**at(146, 72), "color": color, "--mdc-icon-size": "28px"}}],
        })
    elements.append({
        "type": "conditional",
        "conditions": [{"entity": f"binary_sensor.garden_{c}_battery_low", "state": "on"}],
        "elements": [{"type": "icon", "icon": "mdi:battery-alert-variant-outline",
                      "title": "Probe battery low",
                      "style": {**at(284, 22), "color": RED, "--mdc-icon-size": "22px"}}],
    })
    return {
        "type": "vertical-stack",
        "grid_options": {"columns": 3},
        "cards": [
            {"type": "picture-elements", "image": data_uri(BLANK_SVG), "elements": elements},
            {"type": "tile", "entity": moisture, "name": "Moisture, last 3 days",
             "icon": "mdi:water-percent", "color": "blue", "hide_state": True,
             "features": [{"type": "trend-graph", "hours_to_show": 72}]},
        ],
    }


def section():
    return {
        "type": "grid",
        "column_span": 3,
        "cards": [{"type": "heading", "heading": "Garden", "icon": "mdi:sprout"}]
                 + [card_for(b) for b in BEDS],
    }


# ---------------------------------------------------------------------------
# Package: name boxes, plant dropdowns and helper sensors
# ---------------------------------------------------------------------------

def find(suffix):
    """Jinja: the numeric states of sensors whose ID ends with `suffix`."""
    return (f"states.sensor | map(attribute='entity_id') "
            f"| select('search', '{suffix}$') | map('states') | select('is_number') | list")


def mirror(c, key, label, suffix, unit, device_class, icon):
    return {
        "name": f"Garden {c} {label}",
        "unique_id": f"garden_{c}_{key}",
        "icon": icon,
        "unit_of_measurement": unit,
        "device_class": device_class,
        "state_class": "measurement",
        "availability": f"{{{{ ({find(suffix)}) | count > 0 }}}}",
        "state": f"{{{{ ({find(suffix)}) | first }}}}",
    }


def package():
    thresholds = {kind: [dry, wet] for kind, (_, dry, wet) in PLANT_TYPES.items()}
    texts, selects, sensors, binaries = {}, {}, [], []
    for b in BEDS:
        c = b["channel"]
        # Empty until renamed on the dashboard; the card then shows b["name"].
        texts[f"garden_{c}_name"] = {
            "name": f"Garden {c} name",
            "icon": "mdi:rename-outline",
            "max": 24,
        }
        selects[f"garden_{c}_plant"] = {
            "name": f"Garden {c} plant",
            "icon": "mdi:sprout",
            # The first option is the default until a plant is picked.
            "options": [DEFAULT_PLANT] + [k for k in PLANT_TYPES if k != DEFAULT_PLANT],
        }
        sensors += [
            mirror(c, "moisture", "Moisture", f"soil_moisture_{c}", "%",
                   "moisture", "mdi:water-percent"),
            mirror(c, "soil_temperature", "Soil Temperature", f"soil_temperature_{c}",
                   "°F", "temperature", "mdi:thermometer"),
            mirror(c, "conductivity", "Conductivity",
                   f"soil_(electrical_conductivity|ec)_{c}", "µS/cm",
                   "conductivity", "mdi:flash-outline"),
            mirror(c, "battery", "Battery", f"soil_battery_{c}", "V",
                   "voltage", "mdi:battery"),
            {
                "name": f"Garden {c} Name",
                "unique_id": f"garden_{c}_name",
                "icon": "mdi:sprout",
                "state": (f"{{% set n = states('input_text.garden_{c}_name') | trim %}}"
                          f"{{{{ n if n not in ['', 'unknown', 'unavailable'] else '{b['name']}' }}}}"),
            },
            {
                "name": f"Garden {c} Title",
                "unique_id": f"garden_{c}_title",
                "icon": "mdi:sprout",
                "state": (f"{{{{ states('sensor.garden_{c}_name') }}}} · "
                          f"{{{{ states('input_select.garden_{c}_plant') }}}}"),
            },
            {
                "name": f"Garden {c} Status",
                "unique_id": f"garden_{c}_status",
                "icon": "mdi:sprout",
                "availability": f"{{{{ has_value('sensor.garden_{c}_moisture') }}}}",
                "state": (f"{{% set limits = {thresholds} %}}"
                          f"{{% set t = limits.get(states('input_select.garden_{c}_plant'), [30, 70]) %}}"
                          f"{{% set m = states('sensor.garden_{c}_moisture') | float(0) %}}"
                          "{{ 'Dry' if m < t[0] else 'Wet' if m > t[1] else 'Good' }}"),
            },
        ]
        binaries.append({
            "name": f"Garden {c} Battery Low",
            "unique_id": f"garden_{c}_battery_low",
            "device_class": "battery",
            "availability": f"{{{{ has_value('sensor.garden_{c}_battery') }}}}",
            "state": f"{{{{ states('sensor.garden_{c}_battery') | float(9) < {BATTERY_LOW_V} }}}}",
        })
    # One line for the Home alert banner. A probe reading exactly 0% is
    # taken to be out of the ground (or not set up yet), not a dry bed.
    channels = [b["channel"] for b in BEDS]
    sensors.append({
        "name": "Garden Needs Water",
        "unique_id": "garden_needs_water",
        "icon": "mdi:watering-can",
        "state": (
            "{%- set ns = namespace(beds=[]) %}"
            f"{{%- for c in {channels} %}}"
            "{%- if is_state('sensor.garden_' ~ c ~ '_status', 'Dry')"
            " and states('sensor.garden_' ~ c ~ '_moisture') | float(0) > 0 %}"
            "{%- set ns.beds = ns.beds + [states('sensor.garden_' ~ c ~ '_name')] %}"
            "{%- endif %}{%- endfor %}"
            "{%- if not ns.beds %}OK"
            "{%- elif ns.beds | count == 1 %}{{ ns.beds[0] }} needs water"
            "{%- else %}{{ ns.beds[:-1] | join(', ') }} and {{ ns.beds[-1] }} need water"
            "{%- endif %}"),
    })
    return {"input_text": texts, "input_select": selects,
            "template": [{"sensor": sensors, "binary_sensor": binaries}]}


def gallery(path):
    tiles = "".join(
        f'<figure style="margin:0;background:{bg};border-radius:14px;padding:6px">'
        f'<img src="{PLANT_IMAGES[k]}" style="width:240px;display:block">'
        f'<figcaption style="font:13px sans-serif;color:{fg};text-align:center">{k}</figcaption></figure>'
        for bg, fg in [("#1a1f29", "#e9ecf1")] for k in PLANT_TYPES)
    Path(path).write_text(f'<html><body style="margin:0;padding:10px;background:#0e1117;'
                          f'display:flex;flex-wrap:wrap;gap:8px;width:1260px">{tiles}</body></html>')


def write(path, header, data):
    text = yaml.dump(data, Dumper=yaml.SafeDumper, sort_keys=False, width=10_000,
                     allow_unicode=True)
    (ROOT / path).write_text(header + text)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--gallery":
        gallery(sys.argv[2])
        print(f"wrote {sys.argv[2]}")
        return
    header = ("# GENERATED by tools/garden.py: edit BEDS / PLANT_TYPES there and re-run\n"
              "# it, don't edit this file by hand.\n")
    write("dashboard/views/garden_section.yaml", header, section())
    write("packages/garden.yaml", header, package())
    print("wrote dashboard/views/garden_section.yaml and packages/garden.yaml")


if __name__ == "__main__":
    main()
