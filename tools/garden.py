#!/usr/bin/env python3
"""Generate the Garden section of the Outdoors tab and its helper sensors.

Writes:
  dashboard/views/garden_section.yaml   one card per soil probe: plant
                                        illustration, moisture, status,
                                        soil temperature, EC and a 3-day
                                        moisture graph
  packages/garden_template.yaml         helper sensors with fixed IDs
                                        (sensor.garden_1_moisture, ...)

The helpers find each probe's readings by channel number at the end of the
Ecowitt entity ID (…soil_moisture_1, …soil_temperature_1, …), so the
dashboard doesn't depend on the gateway's name or area prefix.

To rename a bed, change its art, or adjust when it counts as dry or wet,
edit PLANTS and run:  python3 tools/garden.py
"""

import base64
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# channel: the probe's number in Ecowitt (Soil Moisture 1, 2, …)
# art:     seedling | lettuce | tomato | flower
# dry/wet: moisture % below/above which the bed shows Dry/Wet
PLANTS = [
    {"channel": 1, "name": "Bed 1", "art": "seedling", "dry": 25, "wet": 70},
    {"channel": 2, "name": "Bed 2", "art": "lettuce", "dry": 25, "wet": 70},
    {"channel": 3, "name": "Bed 3", "art": "tomato", "dry": 25, "wet": 70},
    {"channel": 4, "name": "Bed 4", "art": "flower", "dry": 25, "wet": 70},
]

# A probe battery (1.5 V AA) under this is flagged on its card.
BATTERY_LOW_V = 1.2

LEAF = "#5aa84e"
LEAF_LIGHT = "#7cc96b"
STEM = "#4a8a40"
LABEL = "#9aa3b2"

# ---------------------------------------------------------------------------
# Illustrations: a terracotta pot on the left of a 300×160 canvas; the right
# side is left free for the readings.
# ---------------------------------------------------------------------------

POT = (
    '<ellipse cx="65" cy="153" rx="34" ry="4" fill="#000" fill-opacity="0.15"/>'
    '<path d="M36 118 L94 118 L87 152 L43 152 Z" fill="#c8714a"/>'
    '<rect x="30" y="108" width="70" height="12" rx="3" fill="#b5603c"/>'
    '<ellipse cx="65" cy="109" rx="31" ry="4" fill="#5b3a29"/>'
)


def leaf(x, y, length, angle, color):
    """A pointed leaf whose base sits at (x, y), pointing at `angle` degrees."""
    w = length * 0.38
    return (f'<path transform="translate({x} {y}) rotate({angle})" '
            f'd="M0 0 C{w} {-length * 0.3} {w} {-length * 0.75} 0 {-length} '
            f'C{-w} {-length * 0.75} {-w} {-length * 0.3} 0 0 Z" fill="{color}"/>')


def art_seedling():
    return (f'<path d="M65 109 C65 96 64 86 66 74" stroke="{STEM}" '
            f'stroke-width="3.5" fill="none" stroke-linecap="round"/>'
            + leaf(66, 80, 30, -62, LEAF)
            + leaf(66, 74, 34, 55, LEAF_LIGHT)
            + leaf(66, 72, 16, -5, LEAF))


def art_lettuce():
    parts = []
    for angle, length, color in [(-70, 40, LEAF), (70, 40, LEAF), (-40, 46, LEAF_LIGHT),
                                 (40, 46, LEAF_LIGHT), (-15, 50, LEAF), (15, 50, LEAF),
                                 (0, 42, LEAF_LIGHT)]:
        w = length * 0.55
        parts.append(f'<path transform="translate(65 108) rotate({angle})" '
                     f'd="M0 0 C{w} {-length * 0.25} {w} {-length * 0.95} 0 {-length} '
                     f'C{-w} {-length * 0.95} {-w} {-length * 0.25} 0 0 Z" '
                     f'fill="{color}" stroke="#3f8f45" stroke-width="1"/>')
    return "".join(parts)


def art_tomato():
    stem = (f'<path d="M65 109 L65 40 M65 88 L48 70 M65 72 L84 56 M65 56 L50 44" '
            f'stroke="{STEM}" stroke-width="3" fill="none" stroke-linecap="round"/>')
    leaves = (leaf(48, 70, 18, -50, LEAF) + leaf(84, 56, 18, 50, LEAF)
              + leaf(50, 44, 16, -40, LEAF_LIGHT) + leaf(65, 40, 18, 0, LEAF)
              + leaf(65, 96, 16, 60, LEAF_LIGHT))
    fruit = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#e0533d"/>'
        f'<circle cx="{x - r * 0.35}" cy="{y - r * 0.35}" r="{r * 0.25}" fill="#fff" fill-opacity="0.35"/>'
        f'<path d="M{x - 3} {y - r + 1} L{x} {y - r - 3} L{x + 3} {y - r + 1}" stroke="{STEM}" '
        f'stroke-width="2" fill="none" stroke-linecap="round"/>'
        for x, y, r in [(52, 80, 7), (80, 66, 8), (74, 92, 6.5)])
    return stem + leaves + fruit


def art_flower():
    stem = (f'<path d="M65 109 C64 90 66 72 65 58" stroke="{STEM}" stroke-width="3.5" '
            f'fill="none" stroke-linecap="round"/>')
    leaves = leaf(65, 96, 26, -58, LEAF) + leaf(65, 86, 26, 58, LEAF_LIGHT)
    petals = "".join(
        f'<ellipse cx="65" cy="40" rx="7" ry="13" fill="{color}" '
        f'transform="rotate({a} 65 52)"/>'
        for a, color in zip(range(0, 360, 45), ["#e86fa0", "#f08cb4"] * 4))
    return stem + leaves + petals + '<circle cx="65" cy="52" r="7" fill="#f7d046"/>'


ART = {"seedling": art_seedling, "lettuce": art_lettuce,
       "tomato": art_tomato, "flower": art_flower}


def svg_for(plant):
    name = plant["name"].replace("&", "&amp;")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 160">'
        + ART[plant["art"]]() + POT
        + f'<text x="128" y="30" font-family="Roboto, sans-serif" font-size="17" '
          f'font-weight="500" fill="{LABEL}">{name}</text>'
        + '</svg>'
    )


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def at(x, y):
    """Canvas point → picture-elements position."""
    return {"left": f"{x / 300 * 100:.1f}%", "top": f"{y / 160 * 100:.1f}%"}


def card_for(plant):
    c = plant["channel"]
    moisture = f"sensor.garden_{c}_moisture"
    status = f"sensor.garden_{c}_status"
    small = {"font-size": "13px", "color": "var(--secondary-text-color)"}
    status_icons = [("Dry", "mdi:water-off-outline", "#e0a03a"),
                    ("Good", "mdi:water-check", "#4caf50"),
                    ("Wet", "mdi:water-alert", "#3b82f6")]
    elements = [
        {"type": "state-label", "entity": moisture,
         "style": {**at(212, 72), "font-size": "34px", "font-weight": "600",
                   "color": "var(--primary-text-color)"}},
        {"type": "state-label", "entity": status, "style": {**at(212, 104), **small}},
        {"type": "state-label", "entity": f"sensor.garden_{c}_soil_temperature",
         "style": {**at(170, 140), **small}},
        {"type": "state-label", "entity": f"sensor.garden_{c}_conductivity",
         "style": {**at(250, 140), **small}},
    ]
    for state, icon, color in status_icons:
        elements.append({
            "type": "conditional",
            "conditions": [{"entity": status, "state": state}],
            "elements": [{"type": "icon", "icon": icon, "tap_action": {"action": "none"},
                          "style": {**at(146, 72), "color": color,
                                    "--mdc-icon-size": "28px"}}],
        })
    elements.append({
        "type": "conditional",
        "conditions": [{"entity": f"sensor.garden_{c}_battery",
                        "state_not": ["unavailable", "unknown"]},
                       {"entity": f"binary_sensor.garden_{c}_battery_low", "state": "on"}],
        "elements": [{"type": "icon", "icon": "mdi:battery-alert-variant-outline",
                      "title": "Probe battery low",
                      "style": {**at(284, 22), "color": "#e0533d",
                                "--mdc-icon-size": "22px"}}],
    })
    return {
        "type": "vertical-stack",
        "grid_options": {"columns": 3},
        "cards": [
            {"type": "picture-elements", "image": data_uri(svg_for(plant)),
             "elements": elements},
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
                 + [card_for(p) for p in PLANTS],
    }


# ---------------------------------------------------------------------------
# Helper sensors
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


def templates():
    sensors, binaries = [], []
    for p in PLANTS:
        c = p["channel"]
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
                "name": f"Garden {c} Status",
                "unique_id": f"garden_{c}_status",
                "icon": "mdi:sprout",
                "availability": f"{{{{ has_value('sensor.garden_{c}_moisture') }}}}",
                "state": (f"{{% set m = states('sensor.garden_{c}_moisture') | float(0) %}}"
                          f"{{{{ 'Dry' if m < {p['dry']} else 'Wet' if m > {p['wet']} "
                          f"else 'Good' }}}}"),
            },
        ]
        binaries.append({
            "name": f"Garden {c} Battery Low",
            "unique_id": f"garden_{c}_battery_low",
            "device_class": "battery",
            "availability": f"{{{{ has_value('sensor.garden_{c}_battery') }}}}",
            "state": f"{{{{ states('sensor.garden_{c}_battery') | float(9) < {BATTERY_LOW_V} }}}}",
        })
    return {"sensor": sensors, "binary_sensor": binaries}


def write(path, header, data):
    text = yaml.safe_dump(data, sort_keys=False, width=10_000, allow_unicode=True)
    (ROOT / path).write_text(header + text)


def main():
    header = ("# GENERATED by tools/garden.py: edit PLANTS there and re-run it,\n"
              "# don't edit this file by hand.\n")
    write("dashboard/views/garden_section.yaml", header, section())
    write("packages/garden_template.yaml", header, templates())
    print("wrote dashboard/views/garden_section.yaml and packages/garden_template.yaml")


if __name__ == "__main__":
    main()
