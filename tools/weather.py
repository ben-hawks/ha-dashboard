#!/usr/bin/env python3
"""Generate the Weather station section of the Outdoors tab (Ecowitt WS90).

Writes:
  dashboard/views/weather_station_section.yaml   the Weather band: illustrated
                                                 current conditions, forecast
                                                 and 24 h graphs
  templates/weather_station.yaml                 helper sensors with fixed
                                                 IDs (sensor.station_*),
                                                 included by
                                                 packages/wall_tablet.yaml

The helpers find the station's readings by the end of their entity IDs
(…gw3000b_outdoor_temperature, …gw3000b_wind_speed, …), so the dashboard
doesn't depend on the gateway's area prefix. sensor.station_sky picks the
picture: Snow when there's precipitation at 35 °F or below (or the forecast
says it's snowing and it's 37 °F or below; the WS90's piezo rain sensor
misses most dry snow), Rain when it's raining, Night after sunset, otherwise
Sunny /
Partly cloudy / Cloudy from how much sunlight reaches the WS90 compared
with a clear sky at the sun's current height.

Weather radar: tapping the forecast swaps it for a live radar map (Windy),
and it swaps in by itself while binary_sensor.stormy_weather is on (rain,
snow or storms now, at the station, or in the next few hours). The switch is
input_boolean.outdoors_radar; the automations that flip it are in
packages/wall_tablet.yaml. The map centres on zone.home: www/radar.html
(copied to /config/www/) reads it and opens Windy there.

Run:  python3 tools/weather.py
"""

import base64
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# The gateway's entity-ID prefix, as in sensor.gw3000b_wind_speed.
GATEWAY = "gw3000b"

W, H = 400, 292

# Radar map zoom. Each step doubles the scale: on the wall tablet 9 shows
# about 90 km across (your town and its neighbours), 8 about 180 km, 7 about
# 350 km. The map centres on zone.home (www/radar.html reads it).
RADAR_ZOOM = 9

# Forecast conditions that bring up the radar on their own, now or in the
# next STORM_HOURS hours. Drop "rainy" and "snowy" to only show it for the
# heavier stuff.
STORMY = ["rainy", "pouring", "lightning", "lightning-rainy", "hail",
          "snowy", "snowy-rainy", "exceptional"]
STORM_HOURS = 3
RADAR_SWITCH = "input_boolean.outdoors_radar"
LABEL = "#9aa3b2"
ACCENT = "#5b9cf6"

# key: (name, ID suffix regex after "<gateway>_", unit, device_class, icon)
READINGS = {
    "temperature": ("Temperature", "outdoor_temperature", "°F", "temperature", "mdi:thermometer"),
    "feels_like": ("Feels Like", "feels_like(_temperature)?", "°F", "temperature", "mdi:thermometer-lines"),
    "humidity": ("Humidity", "(outdoor_)?humidity", "%", "humidity", "mdi:water-percent"),
    "dew_point": ("Dew Point", "(outdoor_)?dew_?point", "°F", "temperature", "mdi:water-thermometer"),
    "wind_speed": ("Wind Speed", "wind_speed", "mph", "wind_speed", "mdi:weather-windy"),
    "wind_gust": ("Wind Gust", "wind_gust", "mph", "wind_speed", "mdi:weather-windy-variant"),
    "wind_direction": ("Wind Direction", "wind_direction", "°", None, "mdi:compass-outline"),
    "rain_rate": ("Rain Rate", "rain_rate(_piezo)?", "in/h", "precipitation_intensity", "mdi:weather-pouring"),
    "rain_today": ("Rain Today", "daily_rain(_piezo)?", "in", "precipitation", "mdi:weather-rainy"),
    "rain_month": ("Rain This Month", "monthly_rain(_piezo)?", "in", "precipitation", "mdi:calendar-month"),
    "uv_index": ("UV Index", "uv_index", None, None, "mdi:sun-wireless"),
    "solar_radiation": ("Solar Radiation", "solar_radiation", "W/m²", "irradiance", "mdi:white-balance-sunny"),
    "pressure": ("Pressure", "relative_pressure", "inHg", "atmospheric_pressure", "mdi:gauge"),
}

POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# Layout (canvas units).
COMPASS = (85, 204, 50)          # centre x, y, radius
ROWS = [("Rain today", "rain_today"), ("Rain rate", "rain_rate"),
        ("This month", "rain_month"), ("UV index", "uv_index"), ("Pressure", "pressure")]
ROW_Y0, ROW_DY, ROW_X_LABEL, ROW_X_VALUE = 170, 24, 182, 390


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def canvas(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{inner}</svg>'


def at(x, y):
    return {"left": f"{x / W * 100:.1f}%", "top": f"{y / H * 100:.1f}%"}


# ---------------------------------------------------------------------------
# Sky pictures (top-left corner of the card)
# ---------------------------------------------------------------------------

_ids = iter(range(10_000))


def uid(prefix):
    """Unique gradient/filter IDs within one picture."""
    return f"{prefix}{next(_ids)}"


def sun(cx, cy, r):
    """Glowing sun: soft halo, tapered rays of two lengths, a shaded core."""
    halo, core, ray = uid("halo"), uid("core"), uid("ray")
    rays = ""
    for i, a in enumerate(range(0, 360, 30)):
        length = r * (0.75 if i % 2 else 0.5)
        rays += (f'<path transform="translate({cx} {cy}) rotate({a})" '
                 f'd="M-3.2 {-r - 4} L0 {-r - 4 - length:.1f} L3.2 {-r - 4} Z" '
                 f'fill="url(#{ray})"/>')
    return (f'<defs>'
            f'<radialGradient id="{halo}"><stop offset="0" stop-color="#ffd25e" stop-opacity="0.55"/>'
            f'<stop offset="1" stop-color="#ffd25e" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="{core}" cx="0.38" cy="0.35" r="0.75">'
            f'<stop offset="0" stop-color="#fff7c2"/><stop offset="0.45" stop-color="#ffd047"/>'
            f'<stop offset="1" stop-color="#ff9c2e"/></radialGradient>'
            f'<linearGradient id="{ray}" x1="0" y1="1" x2="0" y2="0">'
            f'<stop offset="0" stop-color="#ffc23d"/><stop offset="1" stop-color="#ffe08a"/>'
            f'</linearGradient></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 2.3:.1f}" fill="url(#{halo})"/>'
            + rays
            + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{core})"/>'
            f'<circle cx="{cx - r * 0.35:.1f}" cy="{cy - r * 0.38:.1f}" r="{r * 0.22:.1f}" '
            f'fill="#fff" fill-opacity="0.45"/>')


CLOUD_PATH = ("M16 0 H96 A20 20 0 0 0 99 -39 A24 24 0 0 0 70 -55 A30 30 0 0 0 22 -42 "
              "A21 21 0 0 0 16 0 Z")


def cloud(x, y, s, top="#ffffff", bottom="#c3ccdb", rim="#8f9bb3"):
    """A shaded cloud whose bottom-left corner is near (x, y), scale s."""
    fill, shade = uid("cloud"), uid("shadow")
    return (f'<defs><linearGradient id="{fill}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
            f'</linearGradient><filter id="{shade}" x="-0.2" y="-0.2" width="1.4" height="1.6">'
            f'<feGaussianBlur stdDeviation="3"/></filter></defs>'
            f'<g transform="translate({x} {y}) scale({s})">'
            f'<path d="{CLOUD_PATH}" transform="translate(3 6)" fill="#0b1020" '
            f'fill-opacity="0.28" filter="url(#{shade})"/>'
            f'<path d="{CLOUD_PATH}" fill="url(#{fill})" stroke="{rim}" stroke-opacity="0.55" '
            f'stroke-width="1.5" stroke-linejoin="round"/>'
            # A highlight along the top of the biggest puff.
            f'<path d="M36 -44 A26 26 0 0 1 68 -50" fill="none" stroke="#fff" '
            f'stroke-opacity="0.7" stroke-width="2.5" stroke-linecap="round"/></g>')


def moon(cx, cy, r):
    """A glowing crescent with faint craters."""
    glow, body, clip = uid("mglow"), uid("moon"), uid("mclip")
    crescent = (f'M{cx + r * 0.3} {cy - r} A{r} {r} 0 1 0 {cx + r} {cy + r * 0.35} '
                f'A{r * 0.8} {r * 0.8} 0 1 1 {cx + r * 0.3} {cy - r} Z')
    craters = "".join(f'<circle cx="{cx + dx * r:.1f}" cy="{cy + dy * r:.1f}" r="{rr * r:.1f}" '
                      f'fill="#c9b46a" fill-opacity="0.45"/>'
                      for dx, dy, rr in [(-0.55, -0.1, 0.16), (-0.3, 0.45, 0.11), (-0.7, 0.35, 0.08)])
    return (f'<defs><radialGradient id="{glow}"><stop offset="0" stop-color="#cdbcff" '
            f'stop-opacity="0.45"/><stop offset="1" stop-color="#cdbcff" stop-opacity="0"/>'
            f'</radialGradient><linearGradient id="{body}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="#fffbe6"/><stop offset="1" stop-color="#e6cf7a"/>'
            f'</linearGradient><clipPath id="{clip}"><path d="{crescent}"/></clipPath></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 2.1:.1f}" fill="url(#{glow})"/>'
            f'<path d="{crescent}" fill="url(#{body})"/>'
            f'<g clip-path="url(#{clip})">{craters}</g>')


def stars():
    """Four-point sparkles of a few sizes."""
    sparkle = "M0 -6 L1.4 -1.4 L6 0 L1.4 1.4 L0 6 L-1.4 1.4 L-6 0 L-1.4 -1.4 Z"
    return "".join(f'<path transform="translate({x} {y}) scale({k})" d="{sparkle}" '
                   f'fill="#fff4cc" fill-opacity="{o}"/>'
                   for x, y, k, o in [(112, 26, 1.0, 0.95), (132, 56, 0.7, 0.8), (100, 78, 0.55, 0.7),
                                      (24, 26, 0.6, 0.75), (138, 92, 0.45, 0.6)])


def drops():
    """Slanted teardrop raindrops."""
    g = uid("drop")
    drop = "M0 -10 C3 -4 5.5 -0.5 5.5 2.5 A5.5 5.5 0 0 1 -5.5 2.5 C-5.5 -0.5 -3 -4 0 -10 Z"
    return (f'<defs><linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#b6d6ff"/><stop offset="1" stop-color="#3f7fe6"/>'
            f'</linearGradient></defs>'
            + "".join(f'<path transform="translate({x} {y}) rotate(18)" d="{drop}" fill="url(#{g})"/>'
                      for x, y in [(42, 100), (66, 106), (90, 100), (114, 106)]))


def flakes():
    """Six-armed snowflakes with little branches."""
    def flake(x, y, r):
        arm = (f'<line x1="0" y1="0" x2="0" y2="{-r}"/>'
               f'<line x1="0" y1="{-r * 0.55:.1f}" x2="{r * 0.3:.1f}" y2="{-r * 0.8:.1f}"/>'
               f'<line x1="0" y1="{-r * 0.55:.1f}" x2="{-r * 0.3:.1f}" y2="{-r * 0.8:.1f}"/>')
        return (f'<g transform="translate({x} {y})" stroke="#e8f3ff" stroke-width="1.8" '
                f'stroke-linecap="round">'
                + "".join(f'<g transform="rotate({a})">{arm}</g>' for a in range(0, 360, 60))
                + '</g>'
                f'<g transform="translate({x} {y})" stroke="#6f9fe8" stroke-width="0.8" '
                f'stroke-opacity="0.8" stroke-linecap="round">'
                + "".join(f'<g transform="rotate({a})">{arm}</g>' for a in range(0, 360, 60))
                + '</g>')
    return "".join(flake(x, y, r) for x, y, r in
                   [(42, 100, 7), (68, 108, 6), (94, 100, 7), (118, 108, 6)])


SKIES = {
    "Sunny": sun(72, 58, 24),
    "Partly cloudy": sun(92, 44, 19) + cloud(14, 104, 1.0),
    "Cloudy": cloud(52, 74, 0.8, "#e9edf3", "#a9b3c4") + cloud(12, 104, 1.05),
    "Rain": cloud(12, 88, 1.08, "#c9d1de", "#7d8aa3", "#5f6b82") + drops(),
    "Snow": cloud(12, 88, 1.08, "#ffffff", "#cdd8ea") + flakes(),
    "Night": moon(64, 56, 26) + stars(),
}
DEFAULT_SKY = "Partly cloudy"


def bolt(x, y):
    g = uid("bolt")
    return (f'<defs><linearGradient id="{g}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#fff3a6"/><stop offset="1" stop-color="#ffb21f"/>'
            f'</linearGradient></defs>'
            f'<path transform="translate({x} {y})" d="M6 0 L-6 18 L1 18 L-4 34 L12 12 L4 12 L10 0 Z" '
            f'fill="url(#{g})" stroke="#c98a10" stroke-width="1" stroke-linejoin="round"/>')


def fog_lines():
    return "".join(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#b7c2d4" stroke-width="5" '
                   f'stroke-linecap="round" stroke-opacity="0.9"/>'
                   for x0, x1, y in [(26, 112, 98), (40, 126, 110), (30, 100, 122)])


# Forecast pictures: the station's skies plus a few conditions only the
# forecast reports.
FORECAST_ART = {
    **SKIES,
    "Partly cloudy night": moon(84, 44, 20) + cloud(14, 104, 1.0),
    "Fog": cloud(16, 86, 1.05, "#e6eaf0", "#aeb7c6") + fog_lines(),
    "Storm": cloud(12, 86, 1.08, "#9aa6ba", "#5c6880", "#4c566b") + bolt(66, 82),
}


def backdrop(stops):
    """Tinted light across the top of the card: (cx, cy, r, colour, opacity)."""
    defs = "".join(
        f'<radialGradient id="r{i}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
        f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
        for i, (cx, cy, r, c, o) in enumerate(stops))
    rects = "".join(f'<rect width="{W}" height="{H}" fill="url(#r{i})"/>' for i in range(len(stops)))
    return canvas(f"<defs>{defs}</defs>{rects}")


# One backdrop per sky picture, behind everything else on the card.
BACKDROPS = {
    "Sunny": backdrop([(72, 58, 150, "#ffb84d", 0.45), (330, 20, 220, "#5aa0ff", 0.18)]),
    "Partly cloudy": backdrop([(88, 46, 130, "#ffc46b", 0.30), (300, 30, 240, "#6f9cff", 0.20)]),
    "Cloudy": backdrop([(80, 60, 200, "#9aa6bd", 0.30), (320, 40, 220, "#7c8aa6", 0.15)]),
    "Rain": backdrop([(80, 70, 200, "#4f74b8", 0.40), (330, 30, 220, "#3d5a8f", 0.25)]),
    "Snow": backdrop([(80, 70, 200, "#bfe3ff", 0.40), (320, 30, 220, "#d9e8ff", 0.25)]),
    "Night": backdrop([(62, 56, 160, "#6c5cff", 0.40), (330, 40, 220, "#2b3f8f", 0.30)]),
}


# ---------------------------------------------------------------------------
# Wind compass
# ---------------------------------------------------------------------------

def compass_base():
    cx, cy, r = COMPASS
    ticks = "".join(
        f'<line x1="{cx + (r - 5) * math.sin(math.radians(a)):.1f}" '
        f'y1="{cy - (r - 5) * math.cos(math.radians(a)):.1f}" '
        f'x2="{cx + r * math.sin(math.radians(a)):.1f}" '
        f'y2="{cy - r * math.cos(math.radians(a)):.1f}" stroke="{LABEL}" stroke-width="1.5"/>'
        for a in range(0, 360, 30))
    letters = "".join(
        f'<text x="{cx + (r + 9) * math.sin(math.radians(a)):.1f}" '
        f'y="{cy - (r + 9) * math.cos(math.radians(a)) + 4:.1f}" font-size="11" '
        f'fill="{LABEL}" text-anchor="middle">{t}</text>'
        for a, t in [(0, "N"), (90, "E"), (180, "S"), (270, "W")])
    face = (f'<defs><radialGradient id="face" cx="{cx}" cy="{cy - r * 0.35}" r="{r * 1.2}" '
            f'gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{ACCENT}" '
            f'stop-opacity="0.22"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0.02"/>'
            f'</radialGradient></defs><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#face)"/>')
    return (face + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LABEL}" '
            f'stroke-opacity="0.5" stroke-width="2"/>' + ticks + letters)


def wind_pointer(point):
    """A pointer on the ring where the wind comes FROM, aimed at the centre."""
    cx, cy, r = COMPASS
    a = POINTS.index(point) * 22.5
    return canvas(f'<defs><filter id="glow" x="-1" y="-1" width="3" height="3">'
                  f'<feGaussianBlur stdDeviation="4"/></filter></defs>'
                  f'<g transform="rotate({a} {cx} {cy})">'
                  f'<circle cx="{cx}" cy="{cy - r + 4}" r="10" fill="{ACCENT}" opacity="0.6" '
                  f'filter="url(#glow)"/>'
                  f'<path d="M{cx} {cy - r + 15} L{cx - 9} {cy - r - 3} L{cx + 9} {cy - r - 3} Z" '
                  f'fill="{ACCENT}" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></g>')


def base_svg():
    rows = "".join(
        f'<text x="{ROW_X_LABEL}" y="{ROW_Y0 + i * ROW_DY + 5}" font-size="13" '
        f'fill="{LABEL}">{label}</text>'
        for i, (label, _) in enumerate(ROWS))
    divider = (f'<line x1="172" y1="{ROW_Y0 - 16}" x2="172" '
               f'y2="{ROW_Y0 + (len(ROWS) - 1) * ROW_DY + 12}" '
               f'stroke="{LABEL}" stroke-opacity="0.25" stroke-width="1"/>')
    return canvas(f'<g font-family="Roboto, sans-serif">{compass_base()}{rows}</g>{divider}')


# ---------------------------------------------------------------------------
# Dashboard section
# ---------------------------------------------------------------------------

def hero_card():
    cx, cy, r = COMPASS
    small = {"font-size": "13px", "color": "var(--secondary-text-color)", "white-space": "nowrap"}
    big = {"color": "var(--primary-text-color)", "white-space": "nowrap"}
    right = {"transform": "translate(-100%, -50%)"}
    elements = [
        {"type": "image", "entity": "sensor.station_sky",
         "image": data_uri(BACKDROPS[DEFAULT_SKY]),
         "state_image": {k: data_uri(v) for k, v in BACKDROPS.items()},
         "tap_action": {"action": "none"},
         "style": {"left": "50%", "top": "50%", "width": "100%"}},
        {"type": "image", "entity": "sensor.station_sky",
         "image": data_uri(canvas(SKIES[DEFAULT_SKY])),
         "state_image": {k: data_uri(canvas(v)) for k, v in SKIES.items()},
         "tap_action": {"action": "none"},
         "style": {"left": "50%", "top": "50%", "width": "100%"}},
        {"type": "image", "entity": "sensor.station_wind_compass",
         "image": data_uri(canvas("")),
         "state_image": {p: data_uri(wind_pointer(p)) for p in POINTS},
         "tap_action": {"action": "more-info", "entity": "sensor.station_wind_direction"},
         "style": {"left": "50%", "top": "50%", "width": "100%"}},
        # Temperature block, top right.
        {"type": "state-label", "entity": "sensor.station_temperature",
         "style": {**at(390, 48), **right, **big, "font-size": "46px", "font-weight": "600"}},
        {"type": "state-label", "entity": "sensor.station_feels_like", "prefix": "Feels like ",
         "style": {**at(390, 86), **right, **small}},
        {"type": "state-label", "entity": "sensor.station_humidity", "prefix": "Humidity ",
         "style": {**at(390, 106), **right, **small}},
        {"type": "state-label", "entity": "sensor.station_dew_point", "prefix": "Dew point ",
         "style": {**at(390, 126), **right, **small}},
        {"type": "state-label", "entity": "sensor.station_sky",
         "style": {**at(75, 126), **small}},
        # Wind, inside and under the compass.
        {"type": "state-label", "entity": "sensor.station_wind_speed",
         "style": {**at(cx, cy - 4), **big, "font-size": "17px", "font-weight": "600"}},
        {"type": "state-label", "entity": "sensor.station_wind_compass", "prefix": "from ",
         "style": {**at(cx, cy + 16), **small, "font-size": "12px"}},
        {"type": "state-label", "entity": "sensor.station_wind_gust", "prefix": "Gusts ",
         "style": {**at(cx, cy + r + 27), **small, "font-size": "12px"}},
    ]
    for i, (_, key) in enumerate(ROWS):
        elements.append({"type": "state-label", "entity": f"sensor.station_{key}",
                         "style": {**at(ROW_X_VALUE, ROW_Y0 + i * ROW_DY), **right, **big,
                                   "font-size": "14px", "font-weight": "500"}})
    return {"type": "picture-elements", "image": data_uri(base_svg()),
            "elements": elements, "grid_options": {"columns": "full"}}


def history_graph(name, icon, entities, hours=24, **extra):
    """A compact history graph (mini-graph-card, HACS) in the dashboard's
    style: name, icon and current reading on top, a smooth graph with a soft
    fill below. Small enough that four fit beside the station card."""
    card = {
        "type": "custom:mini-graph-card",
        "name": name,
        "icon": icon,
        "entities": entities,
        "hours_to_show": hours,
        "points_per_hour": 2,
        "hour24": False,
        "height": 64,
        "line_width": 3,
        "smoothing": True,
        "animate": False,          # no redraw animation on the slow tablet
        "font_size": 70,
        "font_size_header": 12,
        "show": {"icon": True, "name": True, "state": True, "legend": False,
                 "labels": False, "points": False, "fill": "fade"},
    }
    card.update(extra)
    return card


def weather_graphs():
    return [
        # Line colour follows the temperature: icy, cold, mild, warm, hot (°F).
        history_graph("Temperature", "mdi:thermometer",
                      [{"entity": "sensor.station_temperature"}],
                      color_thresholds=[
                          {"value": 20, "color": "#b7d7ff"}, {"value": 35, "color": "#6aa9ff"},
                          {"value": 55, "color": "#6fdc8c"}, {"value": 75, "color": "#ffb347"},
                          {"value": 90, "color": "#ff6b5e"}],
                      color_thresholds_transition="smooth"),
        # Speed as the main line, gusts as a fainter line without fill.
        history_graph("Wind", "mdi:weather-windy",
                      [{"entity": "sensor.station_wind_speed", "color": "#46d0c0"},
                       {"entity": "sensor.station_wind_gust", "color": "#7aa8ff",
                        "show_fill": False, "show_state": False}],
                      lower_bound=0),
        # Today's total in the corner; bars for how hard it rained each hour.
        history_graph("Rain", "mdi:weather-rainy",
                      [{"entity": "sensor.station_rain_today", "show_graph": False},
                       {"entity": "sensor.station_rain_rate", "color": "#6aa9ff",
                        "show_state": False}],
                      points_per_hour=1, aggregate_func="max", group_by="hour",
                      lower_bound=0,
                      show={"icon": True, "name": True, "state": True, "legend": False,
                            "labels": False, "points": False, "graph": "bar"}),
        # 48 hours: the pressure trend is what hints at a change in weather.
        history_graph("Pressure", "mdi:gauge",
                      [{"entity": "sensor.station_pressure", "color": "#a78bfa"}],
                      hours=48, points_per_hour=1),
    ]


HOURS_SHOWN, DAYS_SHOWN = 6, 5

# Met.no condition → forecast picture. Night variants are picked by hour.
CONDITION_ART = {
    "clear-night": "Night", "sunny": "Sunny", "partlycloudy": "Partly cloudy",
    "cloudy": "Cloudy", "exceptional": "Cloudy", "windy": "Cloudy", "windy-variant": "Cloudy",
    "fog": "Fog", "rainy": "Rain", "pouring": "Rain", "lightning": "Storm",
    "lightning-rainy": "Storm", "snowy": "Snow", "snowy-rainy": "Snow", "hail": "Snow",
}
NIGHT_ART = {"Sunny": "Night", "Partly cloudy": "Partly cloudy night"}


def icon_uri(kind):
    """A forecast picture cropped to the art itself (it sits top-left on the
    station canvas)."""
    return data_uri(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 6 150 130">'
                    f'{FORECAST_ART[kind]}</svg>')


FORECAST_ICONS = {kind: icon_uri(kind) for kind in FORECAST_ART}


def forecast_base():
    rule = (f'<line x1="14" y1="146" x2="{W - 14}" y2="146" stroke="{LABEL}" '
            f'stroke-opacity="0.22" stroke-width="1"/>')
    return canvas(rule)


def forecast_card():
    """Next hours on top, next days below, in the station card's style. Each
    slot is a helper sensor: its state picks the picture, its attributes hold
    the labels (see forecast_templates)."""
    primary = {"color": "var(--primary-text-color)", "white-space": "nowrap"}
    secondary = {"color": "var(--secondary-text-color)", "white-space": "nowrap"}
    tap = radar_action("turn_on")
    # A clear layer over the whole card, so a tap between the icons counts too.
    elements = [{"type": "image", "image": data_uri(canvas("")), "tap_action": tap,
                 "hold_action": {"action": "none"},
                 "style": {**at(W / 2, H / 2), "width": "100%"}}]

    def slot(entity, cx, rows, icon_y, icon_w):
        elements.append({"type": "image", "entity": entity, "image": FORECAST_ICONS[DEFAULT_SKY],
                         "state_image": FORECAST_ICONS, "tap_action": tap,
                         "style": {**at(cx, icon_y), "width": f"{icon_w / W * 100:.1f}%"}})
        for attribute, y, style in rows:
            elements.append({"type": "state-label", "entity": entity, "attribute": attribute,
                             "tap_action": tap, "style": {**at(cx, y), **style}})

    hour_w = W / HOURS_SHOWN
    for i in range(HOURS_SHOWN):
        slot(f"sensor.forecast_hour_{i + 1}", hour_w * (i + 0.5), [
            # Only set on the first hour and on midnight: marks a new day.
            ("day", 16, {**secondary, "color": "var(--primary-color)", "font-size": "11px",
                         "font-weight": "700", "letter-spacing": "0.04em"}),
            ("time", 34, {**secondary, "font-size": "12px"}),
            ("temperature", 118, {**primary, "font-size": "16px", "font-weight": "600"}),
        ], icon_y=76, icon_w=56)

    day_w = W / DAYS_SHOWN
    for i in range(DAYS_SHOWN):
        slot(f"sensor.forecast_day_{i + 1}", day_w * (i + 0.5), [
            ("day", 164, {**secondary, "font-size": "12px", "font-weight": "500"}),
            ("high", 244, {**primary, "font-size": "16px", "font-weight": "600"}),
            ("low", 266, {**secondary, "font-size": "13px"}),
        ], icon_y=203, icon_w=56)

    return {"type": "picture-elements", "image": data_uri(forecast_base()), "elements": elements}


def radar_action(service):
    return {"action": "perform-action", "perform_action": f"input_boolean.{service}",
            "target": {"entity_id": RADAR_SWITCH}}


def radar_url():
    # Served by Home Assistant from /config/www/radar.html. ?v= makes the
    # tablet fetch a fresh copy when the page changes.
    return f"/local/radar.html?zoom={RADAR_ZOOM}&v=2"


def radar_card():
    """Live radar, the same size as the forecast it replaces. Tap the heading
    (or the ✕) to go back to the forecast."""
    back = radar_action("turn_off")
    return {"type": "vertical-stack", "cards": [
        {"type": "heading", "heading": "Weather radar", "icon": "mdi:radar",
         "heading_style": "subtitle", "tap_action": back,
         "badges": [{"type": "entity", "entity": RADAR_SWITCH, "icon": "mdi:close",
                     "show_state": False, "tap_action": back}]},
        # About 60% as tall as wide + the heading ≈ the forecast's 400×292.
        # No sandbox: the page reads zone.home from the dashboard around it.
        {"type": "iframe", "url": radar_url(), "aspect_ratio": "60%",
         "disable_sandbox": True},
    ]}


def section():
    """The Weather band across the top of Outdoors: station card | forecast |
    24 h graphs. A grid card keeps the three columns even (grid_options widths
    in a multi-column section are counted out of 36, not 12)."""
    return {
        "type": "grid",
        "column_span": 3,
        "cards": [
            # No heading: the band needs to fit above the Garden on the
            # 1280×800 wall tablet without scrolling.
            {"type": "grid", "columns": 3, "square": False,
             "grid_options": {"columns": "full"},
             "cards": [
                 {k: v for k, v in hero_card().items() if k != "grid_options"},
                 # Forecast, or the radar while the switch is on. Only one
                 # shows, so the grid keeps three columns.
                 {"type": "conditional", "card": forecast_card(), "conditions": [
                     {"condition": "state", "entity": RADAR_SWITCH, "state_not": "on"}]},
                 {"type": "conditional", "card": radar_card(), "conditions": [
                     {"condition": "state", "entity": RADAR_SWITCH, "state": "on"}]},
                 {"type": "grid", "columns": 2, "square": False, "cards": weather_graphs()},
             ]},
        ],
    }


# ---------------------------------------------------------------------------
# Helper sensors
# ---------------------------------------------------------------------------

def find(suffix):
    """Jinja: the numeric states of the gateway's sensors ending in `suffix`."""
    return (f"states.sensor | map(attribute='entity_id') "
            f"| select('search', '{GATEWAY}_{suffix}$') | map('states') "
            f"| select('is_number') | list")


def templates():
    sensors = []
    for key, (name, suffix, unit, device_class, icon) in READINGS.items():
        s = {"name": f"Station {name}", "unique_id": f"station_{key}", "icon": icon,
             "state_class": "measurement",
             "availability": f"{{{{ ({find(suffix)}) | count > 0 }}}}",
             "state": f"{{{{ ({find(suffix)}) | first }}}}"}
        if unit:
            s["unit_of_measurement"] = unit
        if device_class:
            s["device_class"] = device_class
        if key in ("rain_today", "rain_month"):
            s["state_class"] = "total_increasing"
        sensors.append(s)
    sensors.append({
        "name": "Station Wind Compass", "unique_id": "station_wind_compass",
        "icon": "mdi:compass-outline",
        "availability": "{{ has_value('sensor.station_wind_direction') }}",
        "state": (f"{{% set points = {POINTS} %}}"
                  "{{ points[((states('sensor.station_wind_direction') | float(0) + 11.25) "
                  "% 360 / 22.5) | int] }}"),
    })
    sensors.append({
        "name": "Station Sky", "unique_id": "station_sky", "icon": "mdi:weather-partly-cloudy",
        "state": (
            "{% set rain = states('sensor.station_rain_rate') | float(0) %}"
            # The gateway's own rain flag (binary_sensor.…_rain_state_piezo)
            # reacts sooner than the rate.
            "{% set flag = states.binary_sensor | map(attribute='entity_id')"
            f" | select('search', '{GATEWAY}_rain_state(_piezo)?$') | select('is_state', 'on')"
            " | list | count > 0 %}"
            "{% set wet = flag or rain > 0 %}"
            "{% set temp = states('sensor.station_temperature') | float(99) %}"
            # The WS90's piezo rain sensor misses most dry snow, so also trust
            # the forecast's current condition when it's cold enough.
            "{% set forecast = states('weather.forecast_home') %}"
            "{% set elev = state_attr('sun.sun', 'elevation') | float(0) %}"
            "{% set solar = states('sensor.station_solar_radiation') | float(-1) %}"
            "{% if (wet and temp <= 35)"
            " or (forecast in ['snowy', 'snowy-rainy'] and temp <= 37) %}Snow"
            "{% elif wet %}Rain"
            "{% elif elev <= 0 %}Night"
            f"{{% elif solar < 0 or elev < 8 %}}{DEFAULT_SKY}"
            "{% else %}"
            # Clear-sky irradiance is roughly 990 W/m² × sin(elevation).
            "{% set ratio = solar / (990 * sin(elev * pi / 180)) %}"
            "{{ 'Sunny' if ratio > 0.7 else 'Partly cloudy' if ratio > 0.35 else 'Cloudy' }}"
            "{% endif %}"),
    })
    return {"sensor": sensors}


def forecast_templates():
    """Trigger-based slot sensors (sensor.forecast_hour_1…6, forecast_day_1…5)
    filled from Met.no every 30 minutes and on template reload. State = the
    picture to show; attributes = the labels."""
    art = (f"{{% set art = {CONDITION_ART} %}}"
           f"{{% set night_art = {NIGHT_ART} %}}")

    def hour(i):
        f = f"hourly['weather.forecast_home'].forecast[{i}]"
        t = f"as_local(as_datetime({f}.datetime))"
        return {
            "name": f"Forecast Hour {i + 1}", "unique_id": f"forecast_hour_{i + 1}",
            "icon": "mdi:clock-outline",
            "state": (art + f"{{% set t = {t} %}}{{% set a = art.get({f}.condition, 'Cloudy') %}}"
                      "{{ night_art.get(a, a) if t.hour >= 19 or t.hour < 7 else a }}"),
            "attributes": {
                "time": f"{{{{ {t}.strftime('%-I %p') }}}}",
                "day": (f"{{% set t = {t} %}}"
                        + ("{{ t.strftime('%a').upper() }}" if i == 0 else
                           "{{ t.strftime('%a').upper() if t.hour == 0 else '' }}")),
                "temperature": f"{{{{ {f}.temperature | round(0) | int }}}}°",
            },
        }

    def day(i):
        f = f"daily['weather.forecast_home'].forecast[{i}]"
        t = f"as_local(as_datetime({f}.datetime))"
        return {
            "name": f"Forecast Day {i + 1}", "unique_id": f"forecast_day_{i + 1}",
            "icon": "mdi:calendar",
            "state": art + f"{{{{ art.get({f}.condition, 'Cloudy') }}}}",
            "attributes": {
                "day": (f"{{% set t = {t} %}}"
                        "{{ 'Today' if t.date() == now().date() else t.strftime('%a') }}"),
                "high": f"{{{{ {f}.temperature | round(0) | int }}}}°",
                "low": (f"{{{{ ({f}.templow | round(0) | int) ~ '°' "
                        f"if {f}.templow is defined else '' }}}}"),
            },
        }

    return [{
        "triggers": [
            {"trigger": "time_pattern", "minutes": "/30"},
            {"trigger": "homeassistant", "event": "start"},
            {"trigger": "event", "event_type": "event_template_reloaded"},
            # Re-check storms as soon as the weather or the station's sky changes.
            {"trigger": "state", "entity_id": ["weather.forecast_home", "sensor.station_sky"],
             "to": None},  # state changes only, not every attribute update
        ],
        "actions": [
            {"action": "weather.get_forecasts", "target": {"entity_id": "weather.forecast_home"},
             "data": {"type": kind}, "response_variable": kind}
            for kind in ("hourly", "daily")
        ],
        "sensor": [hour(i) for i in range(HOURS_SHOWN)] + [day(i) for i in range(DAYS_SHOWN)],
        "binary_sensor": [{
            "name": "Stormy Weather", "unique_id": "stormy_weather", "icon": "mdi:weather-lightning-rainy",
            "state": (f"{{% set stormy = {STORMY} %}}"
                      "{% set soon = hourly['weather.forecast_home'].forecast"
                      f"[:{STORM_HOURS}] | map(attribute='condition') | list %}}"
                      "{{ states('weather.forecast_home') in stormy"
                      " or states('sensor.station_sky') in ['Rain', 'Snow']"
                      " or soon | select('in', stormy) | list | count > 0 }}"),
            "attributes": {
                "next_hours": "{{ hourly['weather.forecast_home'].forecast"
                              f"[:{STORM_HOURS}] | map(attribute='condition') | join(', ') }}}}",
            },
        }],
    }]


def write(path, header, data):
    (ROOT / path).parent.mkdir(exist_ok=True)
    text = yaml.dump(data, Dumper=yaml.SafeDumper, sort_keys=False, width=10_000,
                     allow_unicode=True)
    (ROOT / path).write_text(header + text)


def main():
    header = ("# GENERATED by tools/weather.py: edit it and re-run, don't edit this\n"
              "# file by hand.\n")
    write("dashboard/views/weather_station_section.yaml", header, section())
    write("templates/weather_station.yaml", header, templates())
    write("templates/forecast.yaml", header, forecast_templates()[0])
    print("wrote dashboard/views/weather_station_section.yaml, templates/weather_station.yaml "
          "and templates/forecast.yaml")


if __name__ == "__main__":
    main()
