#!/usr/bin/env python3
"""Generate the Garden section of the Outdoors tab and its package.

Writes:
  dashboard/views/garden_section.yaml   one card per soil probe: plant
                                        illustration, moisture, status,
                                        soil temperature, EC and a 3-day
                                        moisture graph
  packages/drip.yaml                    drip watering: when and how long each
                                        pump runs (DRIP_ZONES / DRIP below)
  packages/garden.yaml                  per bed: a name box
                                        (input_text.garden_1_name), a plant
                                        dropdown (input_select.garden_1_plant)
                                        and helper sensors with fixed IDs
                                        (sensor.garden_1_moisture, ...), plus
                                        sensor.garden_needs_water for alerts

The plant is chosen on the dashboard: tap a bed's picture and pick from the
list. The picture and the Dry/Good/Wet thresholds follow the choice. Tap the
bed's title to rename it. Tap the small house/sun icon in a card's corner to
say whether that bed is indoors or outdoors.

The thresholds also follow the season (see SEASON below): plants need less
water when they're growing slowly. Indoors that's set by day length (short
winter days, slow growth); outdoors by the last 24 hours' average
temperature (dormant in the cold, thirstier in a heat wave). Each bed's
soil temperature counts too: cold soil means slow roots. Outdoor beds
also don't raise the "needs water" alert while rain is forecast in the next
few hours.

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

# How strongly each plant follows the season (1 = as the SEASON factors
# below, more = rests harder, less = keeps going). Succulents and the
# deciduous berries go properly dormant; lettuce, carrots and seedlings keep
# growing in cool weather and shouldn't be let dry out much.
SEASON_SENSITIVITY = {
    "Seedling": 0.5, "Lettuce": 0.5, "Carrot": 0.6, "Herbs": 0.8,
    "Strawberry": 1.1, "Blueberry": 1.2, "Raspberry": 1.2, "Succulent": 1.4,
}

# How the plant's Dry/Wet levels scale with the season. Both levels are
# multiplied by the factor, so in a slow season the soil may get drier
# before it's "Dry", and it counts as "Wet" (too soggy) sooner.
SEASON = {
    # Indoors, by hours of daylight: 0.75 on short days, rising to 1.0.
    "indoor_daylight": [(10, 0.75), (14, 1.0)],
    # Outdoors, by 24 h average temperature (°F): dormant in the cold,
    # normal when mild, wetter in the heat.
    "outdoor_temperature": [(40, 0.6), (60, 1.0), (80, 1.0), (95, 1.2)],
    # Each bed's own soil temperature (°F): roots slow down in cold soil.
    # Outdoors the colder of air and soil decides; indoors this trims the
    # daylight factor (a cold windowsill), and does nothing above 60 °F.
    "soil_temperature": [(45, 0.6), (60, 1.0)],
    # Forecast pictures (sensor.forecast_hour_1…6) that count as rain coming.
    "rain_pictures": ["Rain", "Storm"],
    "rain_hours": 6,
}

# Jinja: rain = true when a rain/storm picture is in the next few hours.
RAIN_SOON = (
    f"{{%- set rain = range(1, {SEASON['rain_hours']} + 1)"
    " | map('string') | map('regex_replace', '^', 'sensor.forecast_hour_')"
    f" | map('states') | select('in', {SEASON['rain_pictures']}) | list | count > 0 %}}")

# ---------------------------------------------------------------------------
# Drip watering: a Vivosun drip kit's pump on an Athom smart plug
# (esphome/drip-pump.yaml). Written to packages/drip.yaml; see docs/drip.md.
# ---------------------------------------------------------------------------

# One entry per pump (= per plug). The pump is on/off only and waters every
# bed on it at once; each feed line's manual valve sets how much its bed
# gets. So the driest bed (against its own Dry level) decides when it runs,
# it doesn't run while any bed is already Wet, and the plan's valve_hint
# says which valve to turn when the beds drift apart. A second pump would be
# a second entry.
DRIP_ZONES = [
    {"zone": 1, "name": "Garden drip", "switch": "switch.drip_pump_switch",
     "power": "sensor.drip_pump_power", "beds": [1, 2, 3, 4]},
]

DRIP = {
    # A run, in minutes. Short runs with a soak in between ("cycle and
    # soak") let the water spread to the probe before the next look, so a
    # bed is never flooded on one reading.
    "pulse_min": 1,
    "pulse_max": 8,
    "manual_min": 3,           # "Water now" runs at least this long
    "soak": 45,                # minutes after a run before looking again
    # After a run, keep topping up (run, soak, look) toward the target for
    # this many minutes, not just until the bed is above Dry.
    "session": 120,
    # Fill to this far between the bed's Dry and Wet levels (0.5 = middle).
    "target": 0.5,
    "daily_max": 30,           # minutes of pumping per pump per day
    # How long a run is: minutes per 1% of moisture missing. Starts here
    # and is learned from each run (how much the bed rose after soaking).
    "minutes_per_percent": 0.5,
    "learn_range": (0.05, 5),
    "learn_weight": 0.3,       # how much one run moves the learned value
    "min_rise": 1,             # % rise that counts as "the water got there"
    "no_response": 3,          # runs without a rise before it stops (Problem)
    # Watering windows, in hours of the day. Outdoors in the early morning
    # (less evaporation, leaves dry by day) and, in a heat wave (outdoor
    # season above 1), again in the early evening. A bed far below Dry
    # (under dry × critical) waters any time in the critical window.
    "windows": {"outdoor": [(5, 9)], "outdoor_hot": [(17, 19.5)],
                "indoor": [(7, 19)], "critical": (6, 21)},
    "critical": 0.7,
    # Outdoors: no watering at or below these (°F): lines and soil freeze.
    "freeze_air": 38,
    "freeze_soil": 35,
    # The pump draws a few watts; under this while on means it's unplugged
    # from the plug or dead.
    "pump_min_watts": 1.0,
    # The plug turns itself off after this long (esphome/drip-pump.yaml
    # max_run), whatever Home Assistant does; HA does the same.
    "failsafe": 15,
    # Salty soil (EC above the plant's level below): once a day, one run is
    # this much longer to wash salts past the roots. Indoors only if the
    # pots drain somewhere it's fine to overflow.
    "flush_factor": 1.5,
    "flush_indoors": False,
}

# Soil EC (µS/cm) above which a bed counts as salty, by plant. From the
# plants' salt tolerance (saturated-paste EC, so a probe in moist soil
# usually reads lower and this errs towards flushing less). Starting points.
EC_FLUSH_ABOVE = {
    "Seedling": 1000, "Lettuce": 1300, "Tomato": 2500, "Pepper": 1500,
    "Carrot": 1000, "Herbs": 1500, "Cucumber": 2500, "Strawberry": 1000,
    "Blueberry": 1000, "Raspberry": 1000, "Sunflower": 2500, "Flowers": 1500,
    "Succulent": 3000,
}


def drip_zone_of(channel):
    return next((z for z in DRIP_ZONES if channel in z["beds"]), None)


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

# A soft glow behind the plant, coloured by the bed's status.
GLOW_COLORS = {"Dry": "#ffb347", "Good": "#6fdc8c", "Wet": "#6aa9ff"}


def glow_svg(color):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 160">'
            f'<defs><radialGradient id="g" cx="65" cy="82" r="78" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{color}" stop-opacity="0.42"/>'
            f'<stop offset="0.55" stop-color="{color}" stop-opacity="0.12"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>'
            '<rect width="300" height="160" fill="url(#g)"/></svg>')


GLOW_IMAGES = {status: data_uri(glow_svg(color)) for status, color in GLOW_COLORS.items()}

# Moisture bar under the reading, in 5% steps (sensor.garden_N_level, 0–20).
BAR_X, BAR_Y, BAR_W, BAR_H = 150, 121, 124, 6


def bar_svg(level):
    fill = BAR_W * level / 20
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 160">'
            '<defs><linearGradient id="b" x1="0" x2="1">'
            '<stop offset="0" stop-color="#46d0c0"/><stop offset="1" stop-color="#6aa9ff"/>'
            '</linearGradient></defs>'
            f'<rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" rx="3" '
            'fill="#8a96b8" fill-opacity="0.25"/>'
            + (f'<rect x="{BAR_X}" y="{BAR_Y}" width="{fill:.1f}" height="{BAR_H}" rx="3" '
               'fill="url(#b)"/>' if level else "")
            + '</svg>')


BAR_IMAGES = {str(level): data_uri(bar_svg(level)) for level in range(21)}


def moisture_graph(position):
    """3-day moisture history (mini-graph-card, HACS): a smooth line that
    shades from amber (dry) through green to blue (wet) over a soft fill.
    It plots sensor.garden_N_target_position, the moisture relative to the
    bed's current target (0–33 drier, 33–67 on target, 67–100 wetter), so
    the colour breaks follow the plant and the season; mini-graph-card's
    own colour breaks can only be fixed numbers."""
    dry, wet = 33.3, 66.7
    return {
        "type": "custom:mini-graph-card",
        "entities": [{"entity": position, "name": "Moisture vs. target · 3 days"}],
        "hours_to_show": 72,
        "points_per_hour": 1,
        "hour24": False,
        "height": 70,
        "line_width": 3,
        "smoothing": True,
        "animate": False,          # no redraw animation on the slow tablet
        "lower_bound": 0,
        "upper_bound": 100,
        "font_size_header": 13,
        "show": {"icon": False, "state": False, "legend": False, "labels": False,
                 "points": False, "fill": "fade", "name": True},
        "color_thresholds": [
            {"value": 0, "color": GLOW_COLORS["Dry"]},
            {"value": dry, "color": GLOW_COLORS["Good"]},
            {"value": wet, "color": GLOW_COLORS["Wet"]},
        ],
        "color_thresholds_transition": "smooth",
    }


def card_for(bed):
    c = bed["channel"]
    plant = f"input_select.garden_{c}_plant"
    moisture = f"sensor.garden_{c}_moisture"
    status = f"sensor.garden_{c}_status"
    small = {"font-size": "13px", "color": "var(--secondary-text-color)"}
    full = {"left": "50%", "top": "50%", "width": "100%"}
    elements = [
        {"type": "image", "entity": status, "image": data_uri(BLANK_SVG),
         "state_image": GLOW_IMAGES, "tap_action": {"action": "none"}, "style": full},
        {"type": "image", "entity": f"sensor.garden_{c}_level", "image": BAR_IMAGES["0"],
         "state_image": BAR_IMAGES, "tap_action": {"action": "none"}, "style": full},
        # The plant picture follows the bed's dropdown; tap it to change.
        {"type": "image", "entity": plant, "image": PLANT_IMAGES[DEFAULT_PLANT],
         "state_image": PLANT_IMAGES, "tap_action": {"action": "more-info"}, "style": full},
        # "<name> · <plant>"; tap it to rename the bed.
        {"type": "state-label", "entity": f"sensor.garden_{c}_title",
         "tap_action": {"action": "more-info", "entity": f"input_text.garden_{c}_name"},
         "style": {**at(210, 26), "font-size": "15px", "font-weight": "500",
                   "color": "var(--secondary-text-color)", "white-space": "nowrap"}},
        {"type": "state-label", "entity": moisture,
         "style": {**at(212, 72), "font-size": "34px", "font-weight": "600",
                   "color": "var(--primary-text-color)"}},
        # "Dry · aim 23–53%": the status and this season's target range.
        {"type": "state-label", "entity": status, "attribute": "label",
         "style": {**at(212, 103), **small, "white-space": "nowrap"}},
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
    # Indoors (house) / outdoors (sun); tap to switch.
    elements.append({
        "type": "state-icon", "entity": f"input_boolean.garden_{c}_outdoors",
        "tap_action": {"action": "toggle"},
        "style": {**at(20, 140), "color": "var(--secondary-text-color)",
                  "--mdc-icon-size": "20px"},
    })
    # Drip pump, if this bed is on one: tap to switch Auto on/off, hold for
    # what it's doing and why. Hidden until the plug exists (on/off).
    zone = drip_zone_of(c)
    if zone:
        ids, sw = drip_ids(zone), zone["switch"]
        for conds, icon, color, title in [
            ([{"entity": sw, "state": "on"}], "mdi:sprinkler-variant", "#6aa9ff", "Watering"),
            ([{"entity": sw, "state": "off"}, {"entity": ids["auto"], "state": "on"},
              {"entity": ids["plan"], "state": "Problem"}],
             "mdi:water-pump", "#e0a03a", "Watering needs a look"),
            ([{"entity": sw, "state": "off"}, {"entity": ids["auto"], "state": "on"},
              {"entity": ids["plan"], "state_not": "Problem"}],
             "mdi:water-pump", "#46d0c0", "Auto watering on"),
            ([{"entity": sw, "state": "off"}, {"entity": ids["auto"], "state": "off"}],
             "mdi:water-pump-off", "var(--secondary-text-color)", "Auto watering off"),
        ]:
            elements.append({
                "type": "conditional", "conditions": conds,
                "elements": [{"type": "icon", "icon": icon, "entity": ids["auto"], "title": title,
                              "tap_action": {"action": "toggle"},
                              "hold_action": {"action": "more-info", "entity": ids["plan"]},
                              "style": {**at(18, 112), "color": color, "--mdc-icon-size": "20px"}}],
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
        "cards": [
            {"type": "picture-elements", "image": data_uri(BLANK_SVG), "elements": elements},
            moisture_graph(f"sensor.garden_{c}_target_position"),
        ],
    }


# Wide screens get the beds side by side; phones get them stacked (see
# WIDE / NARROW in tools/weather.py; one view either way).
WIDE = [{"condition": "screen", "media_query": "(min-width: 768px)"}]
NARROW = [{"condition": "screen", "media_query": "(max-width: 767px)"}]


def section():
    # The beds sit in a grid card that always splits evenly, up to four per
    # row. (Sizing them with grid_options doesn't work here: in a section
    # spanning 3 columns, Home Assistant counts card widths out of 36, not 12.)
    cards = [card_for(b) for b in BEDS]
    return {
        "type": "grid",
        "column_span": 3,
        # No heading: Weather and Garden together fit on the 1280×800 wall
        # tablet without scrolling.
        "cards": [
            {"type": "grid", "columns": min(len(BEDS), 4), "square": False,
             "grid_options": {"columns": "full"}, "visibility": WIDE,
             "cards": cards},
        ] + [
            # Phones: one bed under another.
            {**card, "grid_options": {"columns": "full"}, "visibility": NARROW}
            for card in cards
        ],
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


def lerp(points, x):
    """Jinja: piecewise-linear lookup of `x` in [(x, y), ...], clamped."""
    out = f"{{%- set pts = {[list(p) for p in points]} %}}"
    out += f"{{%- set x = {x} %}}"
    out += ("{%- set ns = namespace(y=pts[0][1]) %}"
            "{%- for i in range(pts | count) %}"
            "{%- if x >= pts[i][0] %}{% set ns.y = pts[i][1] %}{% endif %}"
            "{%- if i > 0 and pts[i - 1][0] <= x < pts[i][0] %}"
            "{%- set ns.y = pts[i - 1][1] + (x - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0])"
            " * (pts[i][1] - pts[i - 1][1]) %}"
            "{%- endif %}{%- endfor %}")
    return out


def season_sensors():
    """The two season factors (indoor, outdoor) the bed thresholds use."""
    # Today's daylight hours: from sunrise to sunset, from sun.sun.
    daylight = ("{%- set rise = as_datetime(state_attr('sun.sun', 'next_rising')) %}"
                "{%- set set_ = as_datetime(state_attr('sun.sun', 'next_setting')) %}"
                "{%- if is_state('sun.sun', 'above_horizon') %}"
                "{%- set rise = rise - timedelta(days=1) %}{%- endif %}"
                "{%- set hours = (set_ - rise).total_seconds() / 3600 %}")
    temp = ("{%- set t = states('sensor.garden_outdoor_temperature_24h')"
            " | float(states('sensor.station_temperature') | float(65)) %}")
    return [
        {
            "name": "Garden Indoor Season",
            "unique_id": "garden_indoor_season",
            "icon": "mdi:home-thermometer-outline",
            "state": daylight + lerp(SEASON["indoor_daylight"], "hours")
                     + "{{ ns.y | round(2) }}",
            "attributes": {
                "daylight_hours": daylight + "{{ hours | round(1) }}",
                "season": daylight + ("{{ 'Short days, slow growth' if hours < 11"
                                      " else 'Growing' }}"),
            },
        },
        {
            "name": "Garden Outdoor Season",
            "unique_id": "garden_outdoor_season",
            "icon": "mdi:sun-thermometer-outline",
            "state": temp + lerp(SEASON["outdoor_temperature"], "t") + "{{ ns.y | round(2) }}",
            "attributes": {
                "average_temperature": temp + "{{ t | round(1) }}",
                "season": temp + ("{{ 'Dormant' if t < 45 else 'Cool, slow growth' if t < 60"
                                  " else 'Growing' if t <= 80 else 'Hot, drinks more' }}"),
            },
        },
    ]


def limits(c):
    """Jinja: the bed's plant levels scaled by its season → dry, wet, m."""
    thresholds = {kind: [dry, wet] for kind, (_, dry, wet) in PLANT_TYPES.items()}
    return (f"{{%- set base = {thresholds}.get(states('input_select.garden_{c}_plant'), [30, 70]) %}}"
            f"{{%- set where = 'outdoor' if is_state('input_boolean.garden_{c}_outdoors', 'on')"
            " else 'indoor' %}"
            "{%- set f = states('sensor.garden_' ~ where ~ '_season') | float(1) %}"
            + lerp(SEASON["soil_temperature"],
                   f"states('sensor.garden_{c}_soil_temperature') | float(70)")
            + "{%- set f = (f if f > 1 else [f, ns.y] | min) if where == 'outdoor'"
              " else f * ns.y %}"
            # The plant's sensitivity stretches or softens that, within limits.
            + f"{{%- set s = {SEASON_SENSITIVITY}"
              f".get(states('input_select.garden_{c}_plant'), 1) %}}"
            + "{%- set f = [[1 + s * (f - 1), 0.4] | max, 1.3] | min %}"
            "{%- set dry = (base[0] * f) | round(0) | int %}"
            "{%- set wet = [[(base[1] * f) | round(0) | int, 95] | min, dry + 15] | max %}"
            f"{{%- set m = states('sensor.garden_{c}_moisture') | float(0) %}}")


def package():
    thresholds = {kind: [dry, wet] for kind, (_, dry, wet) in PLANT_TYPES.items()}
    texts, selects, booleans, sensors, binaries = {}, {}, {}, season_sensors(), []
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
        # Off = indoors (where everything starts), on = outdoors.
        booleans[f"garden_{c}_outdoors"] = {
            "name": f"Garden {c} outdoors",
            "icon": "mdi:home-switch-outline",
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
                "name": f"Garden {c} Level",
                "unique_id": f"garden_{c}_level",
                "icon": "mdi:water-percent",
                "availability": f"{{{{ has_value('sensor.garden_{c}_moisture') }}}}",
                "state": (f"{{{{ [(states('sensor.garden_{c}_moisture') | float(0) / 5) "
                          "| round(0) | int, 20] | min }}"),
            },
            {
                "name": f"Garden {c} Status",
                "unique_id": f"garden_{c}_status",
                "icon": "mdi:sprout",
                "availability": f"{{{{ has_value('sensor.garden_{c}_moisture') }}}}",
                "state": limits(c) + "{{ 'Dry' if m < dry else 'Wet' if m > wet else 'Good' }}",
                "attributes": {
                    "dry_below": limits(c) + "{{ dry }}",
                    "wet_above": limits(c) + "{{ wet }}",
                    "location": (f"{{{{ 'Outdoors' if is_state('input_boolean.garden_{c}_outdoors',"
                                 " 'on') else 'Indoors' }}"),
                    "season": (f"{{{{ state_attr('sensor.garden_' ~ ('outdoor' if is_state("
                               f"'input_boolean.garden_{c}_outdoors', 'on') else 'indoor')"
                               " ~ '_season', 'season') }}"),
                    "season_factor": limits(c) + "{{ f | round(2) }}",
                    # The card's status line, e.g. "Dry · aim 23–53%".
                    "label": limits(c) + ("{{ ('Dry' if m < dry else 'Wet' if m > wet else 'Good')"
                                          " ~ ' · aim ' ~ dry ~ '–' ~ wet ~ '%' }}"),
                },
            },
        ]
        # For the graph: moisture placed on the bed's target, 0–100 with the
        # target range in the middle third, whatever the target is today.
        sensors.append({
            "name": f"Garden {c} Target Position",
            "unique_id": f"garden_{c}_target_position",
            "icon": "mdi:water-percent",
            "state_class": "measurement",
            "availability": f"{{{{ has_value('sensor.garden_{c}_moisture') }}}}",
            "state": limits(c) + (
                "{%- if m <= dry %}{{ (m / [dry, 1] | max * 33.3) | round(1) }}"
                "{%- elif m <= wet %}{{ (33.3 + (m - dry) / (wet - dry) * 33.4) | round(1) }}"
                "{%- else %}{{ (66.7 + (m - wet) / [100 - wet, 1] | max * 33.3) | round(1) }}"
                "{%- endif %}"),
        })
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
    # Beds on a drip pump with Auto on are left to it, unless it's stuck
    # (Problem: its own alert) or used up today's limit (Limit).
    drip_of = {c: z["zone"] for z in DRIP_ZONES for c in z["beds"]}
    dry = (
        "{%- set ns = namespace(beds=[], channels=[]) %}"
        # Rain in the next few hours waters the outdoor beds for us.
        + RAIN_SOON
        + f"{{%- set drip = {drip_of} %}}"
        f"{{%- for c in {channels} %}}"
        "{%- set z = drip.get(c) %}"
        "{%- set dripping = z is not none and is_state('input_boolean.drip_' ~ z ~ '_auto', 'on')"
        " and states('sensor.drip_' ~ z ~ '_plan') not in ['Problem', 'Limit', 'unknown', 'unavailable'] %}"
        "{%- if is_state('sensor.garden_' ~ c ~ '_status', 'Dry')"
        " and states('sensor.garden_' ~ c ~ '_moisture') | float(0) > 0 and not dripping"
        " and not (rain and is_state('input_boolean.garden_' ~ c ~ '_outdoors', 'on')) %}"
        "{%- set ns.beds = ns.beds + [states('sensor.garden_' ~ c ~ '_name')] %}"
        "{%- set ns.channels = ns.channels + [c] %}"
        "{%- endif %}{%- endfor %}")
    sensors.append({
        "name": "Garden Needs Water",
        "unique_id": "garden_needs_water",
        "icon": "mdi:watering-can",
        "state": dry + (
            "{%- if not ns.beds %}OK"
            "{%- elif ns.beds | count == 1 %}{{ ns.beds[0] }} needs water"
            "{%- else %}{{ ns.beds[:-1] | join(', ') }} and {{ ns.beds[-1] }} need water"
            "{%- endif %}"),
        # Which beds (channel numbers), so each can be its own alert.
        "attributes": {"beds": dry + "{{ ns.channels }}"},
    })
    return {"input_text": texts, "input_select": selects, "input_boolean": booleans,
            # Outdoor season: the weather station's average over 24 hours.
            "sensor": [{
                "platform": "statistics",
                "name": "Garden Outdoor Temperature 24h",
                "unique_id": "garden_outdoor_temperature_24h",
                "entity_id": "sensor.station_temperature",
                "state_characteristic": "mean",
                "max_age": {"hours": 24},
                "sampling_size": 3000,
                "keep_last_sample": True,
            }],
            "template": [{"sensor": sensors, "binary_sensor": binaries}]}


# ---------------------------------------------------------------------------
# Drip package: when and how long each pump runs
# ---------------------------------------------------------------------------

def drip_ids(zone):
    z = zone["zone"]
    return {
        "auto": f"input_boolean.drip_{z}_auto",
        "mpp": f"input_number.drip_{z}_minutes_per_percent",
        "misses": f"input_number.drip_{z}_no_response",
        "last": f"input_datetime.drip_{z}_last_run",
        "flushed": f"input_datetime.drip_{z}_last_flush",
        "runtime": f"sensor.drip_{z}_runtime_today",
        "plan": f"sensor.drip_{z}_plan",
        "rises": f"input_text.drip_{z}_last_rises",
        "pulse": f"script.drip_{z}_pulse",
        "now": f"script.drip_{z}_water_now",
    }


def learned(mpp):
    """Jinja: the learned minutes per %, or the default before the first run
    (a new input_number starts at its minimum)."""
    lo = DRIP["learn_range"][0]
    return (f"{{%- set mpp = states('{mpp}') | float(0) %}}"
            f"{{%- set mpp = mpp if mpp > {lo} else {DRIP['minutes_per_percent']} %}}")


def drip_logic(zone):
    """Jinja: decide what the pump should do now → p.state, p.reason, plus
    the driest bed (ns.*), the run length (minutes) and flush."""
    d, w, ids = DRIP, DRIP["windows"], drip_ids(zone)
    sw = zone["switch"]

    def rule(cond, state, reason, first=False):
        return (f"{{%- {'if' if first else 'elif'} {cond} %}}"
                f"{{%- set p.state = '{state}' %}}{{%- set p.reason = {reason} %}}")

    return (
        f"{{%- set ec_max = {EC_FLUSH_ABOVE} %}}"
        "{%- set ns = namespace(valid=0, wet=[], bed=0, name='', m=0, dry=0, wetl=100,"
        " gap=999, salty=false, outdoor=false, cold_soil=false,"
        " lo=9, lo_name='', hi=-9, hi_name='') %}"
        f"{{%- for c in {zone['beds']} %}}"
        "{%- set s = 'sensor.garden_' ~ c %}"
        "{%- set out = is_state('input_boolean.garden_' ~ c ~ '_outdoors', 'on') %}"
        "{%- if out %}{% set ns.outdoor = true %}"
        f"{{%- if states(s ~ '_soil_temperature') | float(60) <= {d['freeze_soil']} %}}"
        "{% set ns.cold_soil = true %}{% endif %}{%- endif %}"
        # A probe reading 0% is out of the ground (or not set up): ignored.
        "{%- set m = states(s ~ '_moisture') | float(0) %}"
        "{%- if m > 0 and has_value(s ~ '_status') %}"
        "{%- set dry = state_attr(s ~ '_status', 'dry_below') | float(30) %}"
        "{%- set wet = state_attr(s ~ '_status', 'wet_above') | float(70) %}"
        "{%- set ns.valid = ns.valid + 1 %}"
        "{%- if m > wet %}{% set ns.wet = ns.wet + [states(s ~ '_name')] %}{% endif %}"
        # The driest bed, against its own Dry level, decides.
        "{%- if m - dry < ns.gap %}{% set ns.gap = m - dry %}{% set ns.bed = c %}"
        "{%- set ns.name = states(s ~ '_name') %}{% set ns.m = m %}"
        "{%- set ns.dry = dry %}{% set ns.wetl = wet %}{% endif %}"
        # Where it sits between its Dry (0) and Wet (1) levels. One bed near
        # Wet while another is near Dry is something the pump can't fix (it
        # waters both): that's a valve to turn.
        "{%- set pos = (m - dry) / ([wet - dry, 1] | max) %}"
        "{%- if pos < ns.lo %}{% set ns.lo = pos %}{% set ns.lo_name = states(s ~ '_name') %}{% endif %}"
        "{%- if pos > ns.hi %}{% set ns.hi = pos %}{% set ns.hi_name = states(s ~ '_name') %}{% endif %}"
        f"{{%- if (out or {d['flush_indoors']}) and states(s ~ '_conductivity') | float(0)"
        " > ec_max.get(states('input_select.garden_' ~ c ~ '_plant'), 2000) %}"
        "{% set ns.salty = true %}{% endif %}"
        "{%- endif %}{%- endfor %}"
        f"{{%- set target = ns.dry + (ns.wetl - ns.dry) * {d['target']} %}}"
        # Weather (outdoor pumps only).
        f"{{%- set cold = ns.outdoor and (ns.cold_soil or"
        f" states('sensor.station_temperature') | float(60) <= {d['freeze_air']}) %}}"
        "{%- set raining = ns.outdoor and states('sensor.station_rain_rate') | float(0) > 0 %}"
        + RAIN_SOON + "{%- set rain = ns.outdoor and rain %}"
        # Since the last run ended: soaking in, then topping up toward target.
        f"{{%- set since = now().timestamp() - state_attr('{ids['last']}', 'timestamp') | float(0) %}}"
        f"{{%- set soaking = since < {d['soak'] + 2} * 60 %}}"
        f"{{%- set session = since < {d['soak'] + d['session']} * 60 %}}"
        f"{{%- set critical = ns.valid > 0 and ns.m < ns.dry * {d['critical']} %}}"
        "{%- set needs = ns.valid > 0 and (ns.m < ns.dry or (session and ns.m < target)) %}"
        f"{{%- set left = {d['daily_max']} - states('{ids['runtime']}') | float(0) * 60 %}}"
        # How long: the missing moisture × learned minutes per %.
        + learned(ids["mpp"])
        + f"{{%- set flush = ns.salty and states('{ids['flushed']}') != now().date() | string %}}"
        f"{{%- set ff = {d['flush_factor']} if flush else 1 %}}"
        f"{{%- set minutes = [[(target - ns.m) * mpp * ff, {d['pulse_min']}] | max,"
        f" {d['pulse_max']} * ff, [left, 0] | max] | min | round(1) %}}"
        # Watering windows.
        "{%- set hot = states('sensor.garden_outdoor_season') | float(1) > 1 %}"
        f"{{%- set wins = ({w['outdoor']} + ({w['outdoor_hot']} if hot else []))"
        f" if ns.outdoor else {w['indoor']} %}}"
        "{%- set h = now().hour + now().minute / 60 %}"
        "{%- set wn = namespace(inside=false, next=none) %}"
        "{%- for a, b in wins %}{% if a <= h < b %}{% set wn.inside = true %}{% endif %}"
        "{% if wn.next is none and h < a %}{% set wn.next = a %}{% endif %}{% endfor %}"
        f"{{%- set inside = wn.inside or (critical and {w['critical'][0]} <= h < {w['critical'][1]}) %}}"
        "{%- set at = (today_at() + timedelta(hours=wn.next if wn.next is not none else wins[0][0]))"
        ".strftime('%-I:%M %p') | replace(':00', '') %}"
        "{%- set pct = ns.m | round(0) | int %}"
        "{%- set hint = ('Turn ' ~ ns.hi_name ~ '\\'s valve down a little, or ' ~ ns.lo_name"
        " ~ '\\'s up') if ns.valid > 1 and ns.hi > 0.85 and ns.lo < 0.15 else 'Valves look balanced' %}"
        "{%- set p = namespace(state='OK', reason='') %}"
        # First match wins.
        + rule(f"is_state('{sw}', 'on')", "Watering", "'Watering now'", first=True)
        + rule(f"states('{ids['misses']}') | float(0) >= {d['no_response']}", "Problem",
               f"'Ran {d['no_response']} times and the soil didn\\'t get wetter: check the"
               " water, pump and lines, then switch Auto off and on'")
        + rule("ns.valid == 0", "Problem", "'No soil readings from its beds'")
        + rule("not needs", "OK",
               "ns.name ~ ' is fine (' ~ pct ~ '%, waters below ' ~ (ns.dry | int) ~ '%)'")
        + rule("ns.wet", "Paused", "ns.wet | join(', ') ~ (' is' if ns.wet | count == 1"
                                   " else ' are') ~ ' already wet'")
        + rule("cold", "Paused", "'Too cold to water'")
        + rule("raining", "Paused", "'Raining'")
        + rule("rain and not critical", "Paused", "'Rain on the way'")
        + rule(f"left < {d['pulse_min']}", "Limit",
               f"'Used today\\'s {d['daily_max']} minutes; ' ~ ns.name ~ ' is at ' ~ pct ~ '%'")
        + rule("soaking", "Waiting", "'Letting the last watering soak in'")
        + rule("not inside", "Waiting", "ns.name ~ ' is dry (' ~ pct ~ '%), waters at ' ~ at")
        + rule("true", "Water", "'Water ' ~ ns.name ~ ' for ' ~ '%g' | format(minutes) ~ ' min'"
                                " ~ (' (flushing salts)' if flush else '')")
        + "{%- endif %}"
    )


def drip_package():
    d = DRIP
    booleans, numbers, datetimes, texts, stats, sensors, scripts, autos = {}, {}, {}, {}, [], [], {}, []
    for zone in DRIP_ZONES:
        z, name, sw, ids = zone["zone"], zone["name"], zone["switch"], drip_ids(zone)
        logic = drip_logic(zone)
        booleans[f"drip_{z}_auto"] = {"name": f"{name} auto watering", "icon": "mdi:water-pump"}
        numbers[f"drip_{z}_minutes_per_percent"] = {
            "name": f"{name} minutes per percent", "icon": "mdi:timer-cog-outline",
            "min": d["learn_range"][0], "max": d["learn_range"][1], "step": 0.01, "mode": "box",
            "unit_of_measurement": "min/%"}
        numbers[f"drip_{z}_no_response"] = {
            "name": f"{name} runs without a rise", "icon": "mdi:water-alert-outline",
            "min": 0, "max": 10, "step": 1, "mode": "box"}
        # How much each bed rose after the last run, e.g. "Bed 1 +4%, Bed 2
        # +1%": what each line's valve actually delivers.
        texts[f"drip_{z}_last_rises"] = {"name": f"{name} last run rise per bed",
                                         "icon": "mdi:valve", "max": 255}
        datetimes[f"drip_{z}_last_run"] = {"name": f"{name} last run", "has_date": True,
                                           "has_time": True, "icon": "mdi:history"}
        datetimes[f"drip_{z}_last_flush"] = {"name": f"{name} last flush", "has_date": True,
                                             "has_time": False, "icon": "mdi:shaker-outline"}
        stats.append({
            "platform": "history_stats", "name": f"Drip {z} Runtime Today",
            "unique_id": f"drip_{z}_runtime_today", "entity_id": sw, "state": "on",
            "type": "time", "start": "{{ today_at() }}", "end": "{{ now() }}"})
        sensors.append({
            "name": f"Drip {z} Plan",
            "unique_id": f"drip_{z}_plan",
            "icon": "mdi:water-pump",
            "state": logic + "{{ p.state }}",
            "attributes": {
                "reason": logic + "{{ p.reason }}",
                "bed": logic + "{{ ns.bed }}",
                "minutes": logic + "{{ minutes }}",
                "flush": logic + "{{ flush }}",
                "moisture": logic + "{{ ns.m }}",
                "target": logic + "{{ target | round(0) | int }}",
                "valve_hint": logic + "{{ hint }}",
                "last_run_rise": f"{{{{ states('{ids['rises']}') }}}}",
                "minutes_today": f"{{{{ (states('{ids['runtime']}') | float(0) * 60) | round(1) }}}}",
                "zone_name": name,
            },
        })
        # One run: pump on, off, soak, then see how much the bed rose and
        # learn from it. restart: "Water now" during a soak starts afresh.
        bed0 = zone["beds"][0]
        scripts[f"drip_{z}_pulse"] = {
            "alias": f"{name}: one watering run",
            "icon": "mdi:water-pump",
            "mode": "restart",
            "fields": {
                "minutes": {"description": "How long to run the pump", "example": 4},
                "bed": {"description": "The bed whose probe judges the run", "example": bed0},
                "flush": {"description": "This is the day's salt flush", "example": False},
            },
            "sequence": [
                {"variables": {
                    "mins": f"{{{{ [[minutes | float({d['pulse_min']}), 0.2] | max,"
                            f" {d['failsafe'] - 1}] | min }}}}",
                    "probe": f"sensor.garden_{{{{ bed | int({bed0}) }}}}",
                    "flushing": "{{ flush | default(false) | bool(false) }}",
                }},
                {"variables": {
                    "m0": "{{ states(probe ~ '_moisture') | float(0) }}",
                    "r0": "{{ states('sensor.station_rain_today') | float(0) }}",
                    "before": (f"{{{{ {zone['beds']} | map('string') | map('regex_replace', '^', 'sensor.garden_')"
                               " | map('regex_replace', '$', '_moisture') | map('states')"
                               " | map('float', 0) | list }}"),
                }},
                {"action": "switch.turn_on", "target": {"entity_id": sw}},
                {"delay": {"seconds": "{{ (mins * 60) | int }}"}},
                {"action": "switch.turn_off", "target": {"entity_id": sw}},
                {"action": "input_datetime.set_datetime", "target": {"entity_id": ids["last"]},
                 "data": {"timestamp": "{{ now().timestamp() }}"}},
                {"if": [{"condition": "template", "value_template": "{{ flushing }}"}],
                 "then": [{"action": "input_datetime.set_datetime",
                           "target": {"entity_id": ids["flushed"]},
                           "data": {"date": "{{ now().date() }}"}}]},
                {"delay": {"minutes": d["soak"]}},
                {"variables": {
                    "rise": "{{ states(probe ~ '_moisture') | float(0) - m0 }}",
                    "rained": "{{ states('sensor.station_rain_today') | float(0) > r0 }}",
                    "wet": "{{ state_attr(probe ~ '_status', 'wet_above') | float(70) }}",
                }},
                {"action": "input_text.set_value", "target": {"entity_id": ids["rises"]},
                 "data": {"value": (
                     "{%- set ns = namespace(out=[]) %}"
                     f"{{%- for c in {zone['beds']} %}}"
                     "{%- set m = states('sensor.garden_' ~ c ~ '_moisture') | float(0) %}"
                     "{%- if m > 0 and before[loop.index0] > 0 %}"
                     "{%- set r = (m - before[loop.index0]) | round(0) | int %}"
                     "{%- set ns.out = ns.out + [states('sensor.garden_' ~ c ~ '_name') ~ ' '"
                     " ~ ('+' if r >= 0 else '') ~ r ~ '%'] %}"
                     "{%- endif %}{%- endfor %}"
                     "{{ (ns.out | join(', ') ~ (' (rained)' if rained else ''))[:255] }}")}},
                {"choose": [
                    {"conditions": [{"condition": "template",
                                     "value_template": f"{{{{ rise >= {d['min_rise']} or rained }}}}"}],
                     "sequence": [
                         {"action": "input_number.set_value", "target": {"entity_id": ids["misses"]},
                          "data": {"value": 0}},
                         # Learn minutes per % (not from flushes or rain).
                         {"if": [{"condition": "template",
                                  "value_template": "{{ rise >= 1 and not rained and not flushing }}"}],
                          "then": [{"action": "input_number.set_value",
                                    "target": {"entity_id": ids["mpp"]},
                                    "data": {"value": learned(ids["mpp"]) + (
                                        f"{{{{ [[mpp * {1 - d['learn_weight']} + mins / rise"
                                        f" * {d['learn_weight']}, {d['learn_range'][0] + 0.01}] | max,"
                                        f" {d['learn_range'][1]}] | min | round(2) }}}}")}}]},
                     ]},
                    # No rise although the bed had room for water.
                    {"conditions": [{"condition": "template",
                                     "value_template": "{{ m0 > 0 and m0 + rise < wet - 5 }}"}],
                     "sequence": [{"action": "input_number.increment",
                                   "target": {"entity_id": ids["misses"]}}]},
                ]},
            ],
        }
        scripts[f"drip_{z}_water_now"] = {
            "alias": f"{name}: water now",
            "icon": "mdi:watering-can-outline",
            "mode": "single",
            "sequence": [{"action": "script.turn_on", "target": {"entity_id": ids["pulse"]},
                          "data": {"variables": {
                              "minutes": f"{{{{ [state_attr('{ids['plan']}', 'minutes') | float(0),"
                                         f" {d['manual_min']}] | max }}}}",
                              "bed": f"{{{{ state_attr('{ids['plan']}', 'bed') | int({bed0}) or {bed0} }}}}",
                              "flush": False}}}],
        }
        autos += [
            {
                "id": f"drip_{z}_auto_water",
                "alias": f"Drip - {name}: water when the beds need it",
                "mode": "single",
                "triggers": [{"trigger": "time_pattern", "minutes": "/5"},
                             {"trigger": "state", "entity_id": ids["plan"], "to": "Water"}],
                "conditions": [
                    {"condition": "state", "entity_id": ids["auto"], "state": "on"},
                    {"condition": "state", "entity_id": ids["plan"], "state": "Water"},
                    {"condition": "state", "entity_id": sw, "state": "off"},
                    {"condition": "state", "entity_id": ids["pulse"], "state": "off"},
                ],
                "actions": [{"action": "script.turn_on", "target": {"entity_id": ids["pulse"]},
                             "data": {"variables": {
                                 "minutes": f"{{{{ state_attr('{ids['plan']}', 'minutes') }}}}",
                                 "bed": f"{{{{ state_attr('{ids['plan']}', 'bed') }}}}",
                                 "flush": f"{{{{ state_attr('{ids['plan']}', 'flush') }}}}"}}}],
            },
            {
                # Belt and braces with the plug's own max_run.
                "id": f"drip_{z}_failsafe",
                "alias": f"Drip - {name}: never run longer than {d['failsafe']} min",
                "triggers": [{"trigger": "state", "entity_id": sw, "to": "on",
                              "for": {"minutes": d["failsafe"]}}],
                "actions": [{"action": "switch.turn_off", "target": {"entity_id": sw}}],
            },
            {
                # Switching Auto (back) on clears a Problem.
                "id": f"drip_{z}_auto_on",
                "alias": f"Drip - {name}: Auto on clears problems",
                "triggers": [{"trigger": "state", "entity_id": ids["auto"], "to": "on"}],
                "actions": [{"action": "input_number.set_value",
                             "target": {"entity_id": ids["misses"]}, "data": {"value": 0}}],
            },
        ]
        if zone.get("power"):
            autos.append({
                "id": f"drip_{z}_no_power",
                "alias": f"Drip - {name}: stop if the pump draws no power",
                "triggers": [{"trigger": "state", "entity_id": sw, "to": "on",
                              "for": {"seconds": 30}}],
                "conditions": [{"condition": "template", "value_template": (
                    f"{{{{ is_number(states('{zone['power']}')) and"
                    f" states('{zone['power']}') | float < {d['pump_min_watts']} }}}}")}],
                "actions": [
                    {"action": "script.turn_off", "target": {"entity_id": ids["pulse"]}},
                    {"action": "switch.turn_off", "target": {"entity_id": sw}},
                    {"action": "input_number.set_value", "target": {"entity_id": ids["misses"]},
                     "data": {"value": d["no_response"]}},
                ],
            })
    # A restart mid-run would otherwise leave a pump on (until the plug's
    # own max_run).
    autos.append({
        "id": "drip_pumps_off_on_start",
        "alias": "Drip - pumps off when Home Assistant starts",
        "triggers": [{"trigger": "homeassistant", "event": "start"}],
        "actions": [{"action": "switch.turn_off",
                     "target": {"entity_id": [z["switch"] for z in DRIP_ZONES]},
                     "continue_on_error": True}],
    })
    # For the Home alerts: pumps with Auto on that are stuck.
    zones = [z["zone"] for z in DRIP_ZONES]
    sensors.append({
        "name": "Drip Problems",
        "unique_id": "drip_problems",
        "icon": "mdi:water-pump-off",
        "state": (f"{{{{ {zones} | map('string') | map('regex_replace', '^', 'sensor.drip_')"
                  " | map('regex_replace', '$', '_plan') | select('is_state', 'Problem')"
                  " | list | count }}"),
        "attributes": {"items": (
            "{%- set ns = namespace(a=[]) %}"
            f"{{%- for z in {zones} %}}"
            "{%- if is_state('sensor.drip_' ~ z ~ '_plan', 'Problem')"
            " and is_state('input_boolean.drip_' ~ z ~ '_auto', 'on') %}"
            "{%- set ns.a = ns.a + [{'zone': z, 'text': state_attr('sensor.drip_' ~ z ~ '_plan',"
            " 'zone_name') ~ ' needs a look'}] %}"
            "{%- endif %}{%- endfor %}{{ ns.a }}")},
    })
    return {"input_boolean": booleans, "input_number": numbers, "input_datetime": datetimes,
            "input_text": texts, "sensor": stats, "template": [{"sensor": sensors}], "script": scripts,
            "automation": autos}


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
    write("packages/drip.yaml", header.replace("BEDS / PLANT_TYPES", "DRIP_ZONES / DRIP"),
          drip_package())
    print("wrote dashboard/views/garden_section.yaml, packages/garden.yaml and packages/drip.yaml")


if __name__ == "__main__":
    main()
