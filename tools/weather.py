#!/usr/bin/env python3
"""Generate the Weather station section of the Outdoors tab (Ecowitt WS90).

Writes:
  dashboard/views/weather_station_section.yaml   illustrated current
                                                 conditions + 24 h graphs
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


def trend_tile(key, name, hours=24):
    return {"type": "tile", "entity": f"sensor.station_{key}", "name": name,
            "features": [{"type": "trend-graph", "hours_to_show": hours}]}


def section():
    return {
        "type": "grid",
        "cards": [
            {"type": "heading", "heading": "Weather station", "icon": "mdi:weather-partly-cloudy"},
            hero_card(),
            trend_tile("temperature", "Temperature"),
            trend_tile("wind_speed", "Wind"),
            trend_tile("rain_today", "Rain today"),
            trend_tile("pressure", "Pressure"),
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
    print("wrote dashboard/views/weather_station_section.yaml and templates/weather_station.yaml")


if __name__ == "__main__":
    main()
