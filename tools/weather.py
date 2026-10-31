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
    "uv_index": ("UV Index", "uv_index", None, None, "mdi:sun-wireless"),
    "solar_radiation": ("Solar Radiation", "solar_radiation", "W/m²", "irradiance", "mdi:white-balance-sunny"),
    "pressure": ("Pressure", "relative_pressure", "inHg", "atmospheric_pressure", "mdi:gauge"),
}

POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
          "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

# Layout (canvas units).
COMPASS = (85, 204, 50)          # centre x, y, radius
ROWS = [("Rain today", "rain_today"), ("Rain rate", "rain_rate"),
        ("UV index", "uv_index"), ("Pressure", "pressure")]
ROW_Y0, ROW_DY, ROW_X_LABEL, ROW_X_VALUE = 176, 26, 182, 390


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def canvas(inner):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{inner}</svg>'


def at(x, y):
    return {"left": f"{x / W * 100:.1f}%", "top": f"{y / H * 100:.1f}%"}


# ---------------------------------------------------------------------------
# Sky pictures (top-left corner of the card)
# ---------------------------------------------------------------------------

def sun(cx, cy, r):
    rays = "".join(
        f'<line x1="{cx + (r + 6) * math.cos(math.radians(a)):.1f}" '
        f'y1="{cy + (r + 6) * math.sin(math.radians(a)):.1f}" '
        f'x2="{cx + (r + 15) * math.cos(math.radians(a)):.1f}" '
        f'y2="{cy + (r + 15) * math.sin(math.radians(a)):.1f}" '
        f'stroke="#f6c431" stroke-width="5" stroke-linecap="round"/>'
        for a in range(0, 360, 45))
    return rays + f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#f6c431"/>'


def cloud(x, y, s, fill="#d5dbe4", stroke="#9aa3b2"):
    """A cloud whose bottom-left corner is near (x, y), scale s."""
    return (f'<g transform="translate({x} {y}) scale({s})">'
            f'<path d="M10 0 H90 A20 20 0 0 0 78 -36 A28 28 0 0 0 30 -40 '
            f'A22 22 0 0 0 10 0 Z" fill="{fill}" stroke="{stroke}" stroke-width="2.5" '
            f'stroke-linejoin="round"/></g>')


def moon(cx, cy, r):
    return (f'<path d="M{cx + r * 0.3} {cy - r} A{r} {r} 0 1 0 {cx + r} {cy + r * 0.35} '
            f'A{r * 0.8} {r * 0.8} 0 1 1 {cx + r * 0.3} {cy - r} Z" fill="#f2e3a3"/>')


def stars():
    return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#f2e3a3"/>'
                   for x, y, r in [(110, 26, 2), (128, 52, 1.5), (96, 70, 1.5), (30, 30, 1.5)])


def drops():
    return "".join(f'<line x1="{x}" y1="{y}" x2="{x - 5}" y2="{y + 13}" stroke="{ACCENT}" '
                   f'stroke-width="4" stroke-linecap="round"/>'
                   for x, y in [(42, 96), (66, 100), (90, 96), (114, 100)])


def flakes():
    flake = lambda x, y, r: "".join(
        f'<line x1="{x - r * math.cos(math.radians(a)):.1f}" y1="{y - r * math.sin(math.radians(a)):.1f}" '
        f'x2="{x + r * math.cos(math.radians(a)):.1f}" y2="{y + r * math.sin(math.radians(a)):.1f}" '
        f'stroke="#7aa7ee" stroke-width="2.2" stroke-linecap="round"/>'
        for a in (90, 30, 150))
    return "".join(flake(x, y, 6) for x, y in [(40, 100), (66, 108), (92, 100), (116, 108)])


SKIES = {
    "Sunny": sun(72, 58, 26),
    "Partly cloudy": sun(88, 46, 20) + cloud(20, 100, 1.05),
    "Cloudy": cloud(50, 72, 0.85, "#b8c0cc") + cloud(14, 100, 1.1),
    "Rain": cloud(16, 82, 1.1, "#aeb7c4") + drops(),
    "Snow": cloud(16, 82, 1.1, "#c3cad5") + flakes(),
    "Night": moon(62, 56, 26) + stars(),
}
DEFAULT_SKY = "Partly cloudy"


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
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LABEL}" '
            f'stroke-opacity="0.5" stroke-width="2"/>' + ticks + letters)


def wind_pointer(point):
    """A pointer on the ring where the wind comes FROM, aimed at the centre."""
    cx, cy, r = COMPASS
    a = POINTS.index(point) * 22.5
    return canvas(f'<g transform="rotate({a} {cx} {cy})">'
                  f'<path d="M{cx} {cy - r + 15} L{cx - 9} {cy - r - 3} L{cx + 9} {cy - r - 3} Z" '
                  f'fill="{ACCENT}" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></g>')


def base_svg():
    rows = "".join(
        f'<text x="{ROW_X_LABEL}" y="{ROW_Y0 + i * ROW_DY + 5}" font-size="13" '
        f'fill="{LABEL}">{label}</text>'
        for i, (label, _) in enumerate(ROWS))
    divider = (f'<line x1="172" y1="{ROW_Y0 - 18}" x2="172" y2="{ROW_Y0 + 3 * ROW_DY + 12}" '
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
        if key == "rain_today":
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
            "{% set temp = states('sensor.station_temperature') | float(99) %}"
            # The WS90's piezo rain sensor misses most dry snow, so also trust
            # the forecast's current condition when it's cold enough.
            "{% set forecast = states('weather.forecast_home') %}"
            "{% set elev = state_attr('sun.sun', 'elevation') | float(0) %}"
            "{% set solar = states('sensor.station_solar_radiation') | float(-1) %}"
            "{% if (rain > 0 and temp <= 35)"
            " or (forecast in ['snowy', 'snowy-rainy'] and temp <= 37) %}Snow"
            "{% elif rain > 0 %}Rain"
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
