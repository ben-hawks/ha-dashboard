#!/usr/bin/env python3
"""Generate the HVAC zoning package and its Climate-tab section.

Writes:
  packages/hvac_zones.yaml               helpers, per-room sensors and the
                                         zoning automations
  dashboard/views/hvac_zones_section.yaml          Zones cards (Climate tab)
  dashboard/views/hvac_zones_settings_section.yaml house mode setpoints, bedtime

How it works
------------
One furnace/AC, one Nest (THERMOSTAT), a temperature sensor per room and
smart vents (Yet Another Smart Vent, battery/Thread) in some rooms.

* The house has a mode (Home / Sleep / Away), each with a heat and a cool
  setpoint. Every room adds its own offset, plus an extra one in Sleep (a
  cooler bedroom at night, say). Mode can follow presence and bedtime by
  itself ("Switch house mode automatically").
* Every minute the controller compares each zoned room with its targets
  and decides heat / cool / idle, with hysteresis and minimum run and off
  times so the furnace doesn't short-cycle. The Nest's own mode chooses
  the season: "heat" only heats, "cool" only cools, "heat_cool" does both,
  "off" does nothing.
* Home Assistant then makes the Nest do it by moving its setpoint 2 °F
  above (heat) or below (cool) the Nest's own reading, and back the
  other way when idle. It re-nudges only when needed, to keep Nest API
  calls rare.
* During a heat or cool call, vents open in rooms that need it and close
  partway (never below "Vent minimum position") in rooms that don't. At
  least "Minimum open registers" of the house's supply registers stay open
  (plain registers count as open). The neediest rooms are opened first to
  get there. Vents don't move while idle, which saves their batteries.
* If a Delta Tango temperature-rise sensor is configured (RISE_SENSOR) and
  the rise passes "Max temperature rise", every vent opens for 30 minutes.
* "Climate control" picks who is in charge:
    Nest            (default) Home Assistant changes nothing.
    Preview         the controller runs and writes what it *would* do to the
                    logbook (Nest setpoints, vent moves), but sends nothing.
    Home Assistant  the controller drives the Nest and the vents.
  Leaving "Home Assistant" opens every vent and gives the Nest the house
  mode's hallway targets; its own schedule takes over from its next change.

Edit ROOMS (sensor, vents, plain registers) and run:  python3 tools/hvac_zones.py
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

THERMOSTAT = "climate.hallway"

# Delta Tango "HVAC Temperature Rise (F)" sensor, or None.
RISE_SENSOR = None  # e.g. "sensor.delta_tango_hvac_temperature_rise_f"

# sensor:    temperature entity (°F). A climate entity uses its
#            current_temperature. None = not zoned yet (no demand, vents open).
# vents:     smart vent cover entities in the room.
# registers: plain (non-smart) supply registers in the room.
# weight:    how much this room's comfort counts when deciding to run.
ROOMS = [
    # upstairs
    {"id": "living_room", "name": "Living Room", "sensor": None, "vents": [], "registers": 1},
    {"id": "kitchen", "name": "Kitchen", "sensor": None, "vents": [], "registers": 1},
    {"id": "dining", "name": "Dining", "sensor": None, "vents": [], "registers": 1},
    {"id": "foyer", "name": "Foyer", "sensor": None, "vents": [], "registers": 1},
    {"id": "hallway", "name": "Hallway", "sensor": THERMOSTAT, "vents": [], "registers": 1},
    {"id": "bath", "name": "Bath", "sensor": None, "vents": [], "registers": 1},
    {"id": "bedroom", "name": "Bedroom", "sensor": None, "vents": [], "registers": 1},
    {"id": "office", "name": "Office", "sensor": None, "vents": [], "registers": 1},
    {"id": "megs_office", "name": "Meg's Office", "sensor": None, "vents": [], "registers": 1},
    # downstairs
    {"id": "game_room", "name": "Game Room", "sensor": None, "vents": [], "registers": 1},
    {"id": "work_office", "name": "Work Office",
     "sensor": "sensor.airthings_wave_055159_temperature", "vents": [], "registers": 1},
    {"id": "laundry", "name": "Laundry", "sensor": None, "vents": [], "registers": 1},
]

MODES = {  # house mode: (heat, cool) setpoints in °F
    "Home": (68, 75),
    "Sleep": (65, 73),
    "Away": (62, 80),
}

# Controller tuning (°F / seconds).
START_BAND = 0.5       # a room this far past its target starts a call
STOP_BAND = 0.5        # stop once the neediest room is this far past target
HOUSE_OVERSHOOT = 2.0  # ...or the zoned rooms average this far past target
MIN_RUN = 300
MIN_OFF = 300
NUDGE = 2              # Nest setpoint offset from its own reading
HEAT_LIMITS = (50, 85) # Nest heat setpoint clamp
COOL_LIMITS = (60, 90) # Nest cool setpoint clamp
HOLD_MINUTES = 30      # vents held open after a high-rise event


def slug(r):
    return f"hvac_zone_{r['id']}"


def mode_key(m):
    return m.lower()


# ---------------------------------------------------------------- helpers

CONTROL = "input_select.hvac_control"
CONTROL_OPTIONS = ["Nest", "Preview", "Home Assistant"]   # first = default


def helpers():
    """Helpers deliberately have no `initial:` (that would reset them at every
    restart). Numbers get their defaults once from the seed automation."""
    booleans = {
        "hvac_auto_mode": {"name": "Switch house mode automatically", "icon": "mdi:home-clock"},
        "hvac_defaults_applied": {"name": "Zoning defaults applied", "icon": "mdi:check"},
    }
    numbers = {}
    for m in MODES:
        numbers[f"hvac_{mode_key(m)}_heat"] = {
            "name": f"{m} heat to", "min": 50, "max": 85, "step": 1,
            "unit_of_measurement": "°F", "icon": "mdi:fire", "mode": "box"}
        numbers[f"hvac_{mode_key(m)}_cool"] = {
            "name": f"{m} cool to", "min": 60, "max": 90, "step": 1,
            "unit_of_measurement": "°F", "icon": "mdi:snowflake", "mode": "box"}
    for k, v in SETTINGS.items():
        numbers[k] = {kk: vv for kk, vv in v.items() if kk != "default"}
    for r in ROOMS:
        # Off by default = the room takes part.
        booleans[f"{slug(r)}_excluded"] = {"name": f"{r['name']} left out of zoning",
                                           "icon": "mdi:home-off-outline"}
        numbers[f"{slug(r)}_offset"] = {
            "name": f"{r['name']} offset", "min": -6, "max": 6, "step": 0.5,
            "unit_of_measurement": "°F", "icon": "mdi:plus-minus-variant", "mode": "box"}
        numbers[f"{slug(r)}_sleep_offset"] = {
            "name": f"{r['name']} sleep offset", "min": -6, "max": 6, "step": 0.5,
            "unit_of_measurement": "°F", "icon": "mdi:sleep", "mode": "box"}
    selects = {
        "hvac_control": {"name": "Climate control", "icon": "mdi:account-switch",
                         "options": CONTROL_OPTIONS},
        "hvac_house_mode": {"name": "House mode", "icon": "mdi:home-account",
                            "options": list(MODES)},
        "hvac_zone_call": {"name": "Zoning call", "icon": "mdi:hvac",
                           "options": ["idle", "heat", "cool"]},
    }
    datetimes = {
        "hvac_sleep_time": {"name": "Bedtime", "has_date": False, "has_time": True,
                            "icon": "mdi:weather-night"},
        "hvac_wake_time": {"name": "Wake up", "has_date": False, "has_time": True,
                           "icon": "mdi:weather-sunset-up"},
        "hvac_vent_hold_until": {"name": "Vents held open until", "has_date": True,
                                 "has_time": True, "icon": "mdi:timer-lock-open"},
    }
    return booleans, numbers, selects, datetimes


SETTINGS = {
    "hvac_min_open_percent": {"name": "Minimum open registers", "min": 40, "max": 100, "step": 5,
                              "unit_of_measurement": "%", "icon": "mdi:air-filter", "default": 60},
    "hvac_vent_min_position": {"name": "Vent minimum position", "min": 0, "max": 50, "step": 5,
                               "unit_of_measurement": "%", "icon": "mdi:valve", "default": 20},
    "hvac_max_rise": {"name": "Max temperature rise", "min": 30, "max": 90, "step": 1,
                      "unit_of_measurement": "°F", "icon": "mdi:thermometer-alert", "default": 57},
}


def seed_defaults():
    """Once, on first start: give the helpers sensible values."""
    actions = []
    for m, (h, c) in MODES.items():
        actions += [
            {"action": "input_number.set_value", "target": {"entity_id": f"input_number.hvac_{mode_key(m)}_heat"},
             "data": {"value": h}},
            {"action": "input_number.set_value", "target": {"entity_id": f"input_number.hvac_{mode_key(m)}_cool"},
             "data": {"value": c}},
        ]
    for k, v in SETTINGS.items():
        actions.append({"action": "input_number.set_value", "target": {"entity_id": f"input_number.{k}"},
                        "data": {"value": v["default"]}})
    for r in ROOMS:
        for k in ("offset", "sleep_offset"):
            actions.append({"action": "input_number.set_value",
                            "target": {"entity_id": f"input_number.{slug(r)}_{k}"}, "data": {"value": 0}})
    actions += [
        {"action": "input_datetime.set_datetime", "target": {"entity_id": "input_datetime.hvac_sleep_time"},
         "data": {"time": "22:00:00"}},
        {"action": "input_datetime.set_datetime", "target": {"entity_id": "input_datetime.hvac_wake_time"},
         "data": {"time": "06:30:00"}},
        {"action": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.hvac_auto_mode"}},
        {"action": "input_boolean.turn_on", "target": {"entity_id": "input_boolean.hvac_defaults_applied"}},
    ]
    return {
        "id": "hvac_seed_defaults",
        "alias": "HVAC zoning: first-time defaults",
        "description": "Generated by tools/hvac_zones.py. Runs once; turn off "
                       "input_boolean.hvac_defaults_applied to re-apply.",
        "mode": "single",
        "triggers": [{"trigger": "homeassistant", "event": "start"},
                     {"trigger": "event", "event_type": "automation_reloaded"},
                     {"trigger": "state", "entity_id": "input_boolean.hvac_defaults_applied", "to": "off"}],
        "conditions": [{"condition": "state", "entity_id": "input_boolean.hvac_defaults_applied", "state": "off"}],
        "actions": actions,
    }


# ---------------------------------------------------------------- sensors

def room_sensors(r):
    s = slug(r)
    out = []
    if r["sensor"]:
        src = r["sensor"]
        if src.startswith("climate."):
            value = f"state_attr('{src}', 'current_temperature')"
            avail = f"{{{{ {value} is number }}}}"
        else:
            value = f"states('{src}')"
            avail = f"{{{{ has_value('{src}') }}}}"
        out.append({
            "name": f"{r['name']} Zone Temperature", "unique_id": f"{s}_temperature",
            "unit_of_measurement": "°F", "device_class": "temperature",
            "state_class": "measurement", "availability": avail,
            "state": f"{{{{ {value} | float | round(1) }}}}",
        })
    target = ("{% set m = states('input_select.hvac_house_mode') | lower %}"
              "{% set base = states('input_number.hvac_' ~ m ~ '_KIND') | float(0) %}"
              f"{{% set off = states('input_number.{s}_offset') | float(0) %}}"
              f"{{% set so = states('input_number.{s}_sleep_offset') | float(0) if m == 'sleep' else 0 %}}"
              "{{ (base + off + so) | round(1) }}")
    for kind, label, icon in (("heat", "Heat Target", "mdi:fire"), ("cool", "Cool Target", "mdi:snowflake")):
        out.append({
            "name": f"{r['name']} Zone {label}", "unique_id": f"{s}_{kind}_target",
            "unit_of_measurement": "°F", "device_class": "temperature", "icon": icon,
            "state": target.replace("KIND", kind),
        })
    if r["sensor"]:
        status = (f"{{% set t = states('sensor.{s}_temperature') | float(none) %}}"
                  f"{{% set h = states('sensor.{s}_heat_target') | float(0) %}}"
                  f"{{% set c = states('sensor.{s}_cool_target') | float(0) %}}"
                  f"{{% if is_state('input_boolean.{s}_excluded', 'on') %}}Left out"
                  "{% elif t is none %}No reading"
                  f"{{% elif t < h - {START_BAND} %}}Needs heat"
                  f"{{% elif t > c + {START_BAND} %}}Needs cooling"
                  "{% else %}Comfortable{% endif %}")
    else:
        status = "No sensor"
    out.append({
        "name": f"{r['name']} Zone Status", "unique_id": f"{s}_status",
        "icon": "mdi:home-thermometer", "state": status,
        "attributes": {"label": (
            f"{{% set t = states('sensor.{s}_temperature') %}}"
            f"{{{{ states('sensor.{s}_status') }}}}"
            f"{{{{ ' · aim ' ~ states('sensor.{s}_heat_target') | float(0) | round(0) | int ~ '–' "
            f"~ states('sensor.{s}_cool_target') | float(0) | round(0) | int ~ '°' }}}}")},
    })
    return out


def open_sensor():
    vents = [v for r in ROOMS for v in r["vents"]]
    plain = sum(r["registers"] for r in ROOMS)
    total = plain + len(vents)
    return {
        "name": "Supply Registers Open", "unique_id": "hvac_registers_open",
        "unit_of_measurement": "%", "icon": "mdi:air-filter", "state_class": "measurement",
        "state": (f"{{% set ns = namespace(o={plain}) %}}"
                  f"{{% for v in {vents} %}}"
                  "{% set ns.o = ns.o + (state_attr(v, 'current_position') | float(100)) / 100 %}"
                  "{% endfor %}"
                  f"{{{{ (100 * ns.o / {max(total, 1)}) | round(0) }}}}"),
    }


# ---------------------------------------------------------------- automations

ROWS = """
{%- set ns = namespace(r=[]) %}
{%- for z in rooms %}
  {%- set t = states('sensor.hvac_zone_' ~ z.id ~ '_temperature') | float(none) %}
  {%- if t is not none and not is_state('input_boolean.hvac_zone_' ~ z.id ~ '_excluded', 'on') %}
    {%- set h = states('sensor.hvac_zone_' ~ z.id ~ '_heat_target') | float(0) %}
    {%- set c = states('sensor.hvac_zone_' ~ z.id ~ '_cool_target') | float(0) %}
    {%- set ns.r = ns.r + [{'id': z.id,
        'heat_need': ((h - t) * z.weight) | round(2),
        'cool_need': ((t - c) * z.weight) | round(2),
        'past_heat': (t - h) | round(2),
        'past_cool': (c - t) | round(2)}] %}
  {%- endif %}
{%- endfor %}
{{ ns.r }}
""".strip()

NEW_CALL = """
{%- set n = rows | count %}
{%- set heat_max = (rows | map(attribute='heat_need') | max) if n else -99 %}
{%- set cool_max = (rows | map(attribute='cool_need') | max) if n else -99 %}
{%- set warm = (rows | map(attribute='past_heat') | sum / n) if n else 0 %}
{%- set cold = (rows | map(attribute='past_cool') | sum / n) if n else 0 %}
{%- set can_heat = nest_mode in ['heat', 'heat_cool'] %}
{%- set can_cool = nest_mode in ['cool', 'heat_cool'] %}
{%- if call_now == 'heat' %}
  {%- if not can_heat or (since >= MIN_RUN and (heat_max <= -STOP_BAND or warm >= HOUSE_OVERSHOOT)) %}idle{% else %}heat{% endif %}
{%- elif call_now == 'cool' %}
  {%- if not can_cool or (since >= MIN_RUN and (cool_max <= -STOP_BAND or cold >= HOUSE_OVERSHOOT)) %}idle{% else %}cool{% endif %}
{%- elif since < MIN_OFF %}idle
{%- elif can_heat and heat_max >= START_BAND and (not can_cool or heat_max >= cool_max) %}heat
{%- elif can_cool and cool_max >= START_BAND %}cool
{%- else %}idle{% endif %}
""".strip()

# Desired Nest setpoints and whether they need sending.
# Desired Nest setpoints and whether they need sending. While idle the
# setpoints never pass the Away targets, so if Home Assistant stops the Nest
# still holds the house at Away temperatures on its own.
NEST = """
{%- set t = nest_temp | float(70) %}
{%- set lo_min, lo_max, hi_min, hi_max = HEAT_LIMITS[0], HEAT_LIMITS[1], COOL_LIMITS[0], COOL_LIMITS[1] %}
{%- set floor = states('input_number.hvac_away_heat') | float(60) %}
{%- set ceiling = states('input_number.hvac_away_cool') | float(82) %}
{%- set cur = state_attr(thermostat, 'temperature') | float(none) %}
{%- set cur_lo = state_attr(thermostat, 'target_temp_low') | float(none) %}
{%- set cur_hi = state_attr(thermostat, 'target_temp_high') | float(none) %}
{%- set changed = new_call != call_now %}
{%- if nest_mode == 'heat_cool' %}
  {%- if new_call == 'heat' %}{% set lo = t + NUDGE %}{% set hi = lo + 4 %}
  {%- elif new_call == 'cool' %}{% set hi = t - NUDGE %}{% set lo = hi - 4 %}
  {%- else %}{% set lo = [t - NUDGE, floor] | max %}{% set hi = [t + NUDGE, ceiling] | min %}{% endif %}
  {%- set lo = ([[lo | round(0), lo_min] | max, lo_max] | min) | int %}
  {%- set hi = ([[hi | round(0), hi_min, lo + 3] | max, hi_max] | min) | int %}
  {%- set wrong = cur_lo is none or cur_hi is none
      or (new_call == 'heat' and cur_lo - t < 1)
      or (new_call == 'cool' and t - cur_hi < 1)
      or (new_call == 'idle' and (t - cur_lo < 1 or cur_hi - t < 1)) %}
  {%- set differs = cur_lo is none or cur_hi is none or (cur_lo - lo) | abs >= 1 or (cur_hi - hi) | abs >= 1 %}
  {{ {'send': differs and (changed or wrong), 'data': {'target_temp_low': lo, 'target_temp_high': hi}} }}
{%- elif nest_mode in ['heat', 'cool'] %}
  {%- if nest_mode == 'heat' %}
    {%- set want = t + NUDGE if new_call == 'heat' else [t - NUDGE, floor] | max %}
    {%- set want = ([[want | round(0), lo_min] | max, lo_max] | min) | int %}
    {%- set wrong = cur is none or (new_call == 'heat' and cur - t < 1) or (new_call != 'heat' and t - cur < 1) %}
  {%- else %}
    {%- set want = t - NUDGE if new_call == 'cool' else [t + NUDGE, ceiling] | min %}
    {%- set want = ([[want | round(0), hi_min] | max, hi_max] | min) | int %}
    {%- set wrong = cur is none or (new_call == 'cool' and t - cur < 1) or (new_call != 'cool' and cur - t < 1) %}
  {%- endif %}
  {%- set differs = cur is none or (cur - want) | abs >= 1 %}
  {{ {'send': differs and (changed or wrong), 'data': {'temperature': want}} }}
{%- else %}
  {{ {'send': false, 'data': {}} }}
{%- endif %}
""".strip()

VENTS = """
{%- set minp = states('input_number.hvac_vent_min_position') | int(20) %}
{%- set frac = states('input_number.hvac_min_open_percent') | float(60) / 100 %}
{%- set ns = namespace(items=[], total=0, open=0) %}
{%- for z in rooms %}
  {%- set ns.total = ns.total + z.registers + z.vents | count %}
  {%- set ns.open = ns.open + z.registers %}
  {%- if z.vents | count > 0 %}
    {%- set row = rows | selectattr('id', 'eq', z.id) | list | first | default(none) %}
    {%- if hold %}{% set need = 99 %}
    {%- elif is_state('input_boolean.hvac_zone_' ~ z.id ~ '_excluded', 'on') %}{% set need = -99 %}
    {%- elif row is none %}{% set need = 99 %}
    {%- elif new_call == 'heat' %}{% set need = row.heat_need %}
    {%- else %}{% set need = row.cool_need %}{% endif %}
    {%- set pos = 100 if need >= 0 else (50 if need > -1 else minp) %}
    {%- set ns.items = ns.items + [{'vents': z.vents, 'need': need, 'pos': pos}] %}
    {%- set ns.open = ns.open + (z.vents | count) * pos / 100 %}
  {%- endif %}
{%- endfor %}
{%- set out = namespace(list=[], open=ns.open) %}
{%- for it in ns.items | sort(attribute='need', reverse=true) %}
  {%- set p = it.pos %}
  {%- if ns.total > 0 and out.open / ns.total < frac and p < 100 %}
    {%- set out.open = out.open + (it.vents | count) * (100 - p) / 100 %}
    {%- set p = 100 %}
  {%- endif %}
  {%- for v in it.vents %}
    {%- set cur = state_attr(v, 'current_position') | int(-1) %}
    {%- if cur < 0 or (cur - p) | abs >= 20 %}
      {%- set out.list = out.list + [{'entity': v, 'position': p}] %}
    {%- endif %}
  {%- endfor %}
{%- endfor %}
{{ out.list }}
""".strip()


def fill(tpl):
    for k, v in {"MIN_RUN": MIN_RUN, "MIN_OFF": MIN_OFF, "START_BAND": START_BAND,
                 "STOP_BAND": STOP_BAND, "HOUSE_OVERSHOOT": HOUSE_OVERSHOOT,
                 "NUDGE": NUDGE, "HEAT_LIMITS": list(HEAT_LIMITS),
                 "COOL_LIMITS": list(COOL_LIMITS)}.items():
        tpl = tpl.replace(k, str(v))
    return tpl


def rooms_data():
    return [{"id": r["id"], "vents": r["vents"], "registers": r["registers"],
             "weight": r.get("weight", 1.0)} for r in ROOMS]


def controller():
    rise = (f"{{{{ states('{RISE_SENSOR}') | float(0) >= states('input_number.hvac_max_rise')"
            " | float(57) }}" if RISE_SENSOR else "{{ false }}")
    return {
        "id": "hvac_zone_controller",
        "alias": "HVAC zoning: controller",
        "description": "Generated by tools/hvac_zones.py",
        "mode": "single",
        "max_exceeded": "silent",
        "triggers": [
            {"trigger": "time_pattern", "minutes": "/1"},
            {"trigger": "state", "entity_id": ["input_select.hvac_house_mode", THERMOSTAT]},
            {"trigger": "state", "entity_id": CONTROL, "to": ["Preview", "Home Assistant"]},
        ],
        # "Nest": hands off. "Preview": decide and log, but command nothing.
        "conditions": [{"condition": "state", "entity_id": CONTROL, "state": ["Preview", "Home Assistant"]}],
        "actions": [
            {"variables": {
                "rooms": rooms_data(),
                "live": f"{{{{ is_state('{CONTROL}', 'Home Assistant') }}}}",
                "thermostat": THERMOSTAT,
                "nest_mode": f"{{{{ states('{THERMOSTAT}') }}}}",
                "nest_temp": f"{{{{ state_attr('{THERMOSTAT}', 'current_temperature') }}}}",
                "call_now": "{{ states('input_select.hvac_zone_call') }}",
                "since": "{{ (now() - states.input_select.hvac_zone_call.last_changed).total_seconds() | int }}",
                "rise_high": rise,
                "rows": ROWS,
            }},
            {"variables": {
                "new_call": fill(NEW_CALL),
                "hold_until": ("{% set u = states('input_datetime.hvac_vent_hold_until')"
                               " | as_datetime(none) %}{{ u | as_local if u is not none else none }}"),
            }},
            {"if": [{"condition": "template", "value_template": "{{ rise_high }}"}],
             "then": [{"action": "input_datetime.set_datetime",
                       "target": {"entity_id": "input_datetime.hvac_vent_hold_until"},
                       "data": {"datetime": f"{{{{ (now() + timedelta(minutes={HOLD_MINUTES}))"
                                            ".strftime('%Y-%m-%d %H:%M:%S') }}"}}]},
            {"variables": {
                "hold": "{{ rise_high or (hold_until is not none and now() < hold_until | as_datetime) }}",
                "nest": fill(NEST),
            }},
            {"if": [{"condition": "template", "value_template": "{{ new_call != call_now }}"}],
             "then": [{"action": "input_select.select_option",
                       "target": {"entity_id": "input_select.hvac_zone_call"},
                       "data": {"option": "{{ new_call }}"}}]},
            {"variables": {"moves": "{{ [] }}"}},
            {"if": [{"condition": "template", "value_template": "{{ new_call != 'idle' or hold }}"}],
             "then": [{"variables": {"moves": fill(VENTS)}}]},
            {"if": [{"condition": "template", "value_template": "{{ live }}"}],
             "then": [
                 {"if": [{"condition": "template", "value_template": "{{ nest.send }}"}],
                  "then": [{"action": "climate.set_temperature", "target": {"entity_id": THERMOSTAT},
                            "data": "{{ nest.data }}"}]},
                 {"repeat": {"for_each": "{{ moves }}", "sequence": [
                     {"action": "cover.set_cover_position", "continue_on_error": True,
                      "target": {"entity_id": "{{ repeat.item.entity }}"},
                      "data": {"position": "{{ repeat.item.position }}"}}]}},
             ],
             # Preview: say what would have happened, only when something would.
             "else": [
                 {"if": [{"condition": "template",
                          "value_template": "{{ new_call != call_now or nest.send or moves | count > 0 }}"}],
                  "then": [{"action": "logbook.log", "data": {
                      "name": "HVAC zoning preview",
                      "entity_id": "input_select.hvac_zone_call",
                      "message": ("{{ 'would call ' ~ new_call ~ (' (was ' ~ call_now ~ ')' if new_call != call_now else '')"
                                  " ~ ('; Nest ' ~ nest.data if nest.send else '')"
                                  " ~ ('; vents' if moves | count > 0 else '') }}"
                                  "{% for m in moves %} {{ m.entity }} → {{ m.position }}%{% endfor %}"),
                  }}]},
             ]},
        ],
    }


def zoning_off():
    vents = [v for r in ROOMS for v in r["vents"]]
    hall = next((r for r in ROOMS if r["sensor"] == THERMOSTAT), None)
    h = f"sensor.{slug(hall)}_heat_target" if hall else None
    c = f"sensor.{slug(hall)}_cool_target" if hall else None
    actions = []
    if vents:
        actions.append({"action": "cover.open_cover", "continue_on_error": True,
                        "target": {"entity_id": vents}})
    actions.append({"action": "input_select.select_option",
                    "target": {"entity_id": "input_select.hvac_zone_call"}, "data": {"option": "idle"}})
    if hall:
        actions.append({"choose": [
            {"conditions": [{"condition": "state", "entity_id": THERMOSTAT, "state": "heat_cool"}],
             "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": THERMOSTAT},
                           "data": {"target_temp_low": f"{{{{ states('{h}') | float(68) | round(0) }}}}",
                                    "target_temp_high": f"{{{{ states('{c}') | float(75) | round(0) }}}}"}}]},
            {"conditions": [{"condition": "state", "entity_id": THERMOSTAT, "state": "heat"}],
             "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": THERMOSTAT},
                           "data": {"temperature": f"{{{{ states('{h}') | float(68) | round(0) }}}}"}}]},
            {"conditions": [{"condition": "state", "entity_id": THERMOSTAT, "state": "cool"}],
             "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": THERMOSTAT},
                           "data": {"temperature": f"{{{{ states('{c}') | float(75) | round(0) }}}}"}}]},
        ]})
    return {
        "id": "hvac_zoning_off",
        "alias": "HVAC zoning: hand back to the Nest",
        "description": "Generated by tools/hvac_zones.py. Opens every vent and restores the "
                       "house mode's hallway targets on the Nest.",
        "mode": "single",
        "triggers": [{"trigger": "state", "entity_id": CONTROL, "from": "Home Assistant"}],
        "actions": actions,
    }


def house_mode_auto():
    asleep = ("{% set s = states('input_datetime.hvac_sleep_time') %}"
              "{% set w = states('input_datetime.hvac_wake_time') %}"
              "{% set n = now().strftime('%H:%M:%S') %}"
              "{{ (n >= s or n < w) if s > w else (s <= n < w) }}")
    return {
        "id": "hvac_house_mode_auto",
        "alias": "HVAC zoning: house mode follows presence and bedtime",
        "description": "Generated by tools/hvac_zones.py",
        "mode": "queued",
        "triggers": [
            {"trigger": "time", "at": "input_datetime.hvac_sleep_time", "id": "sleep"},
            {"trigger": "time", "at": "input_datetime.hvac_wake_time", "id": "wake"},
            {"trigger": "numeric_state", "entity_id": "zone.home", "below": 1,
             "for": {"minutes": 15}, "id": "away"},
            {"trigger": "numeric_state", "entity_id": "zone.home", "above": 0, "id": "arrive"},
        ],
        "conditions": [{"condition": "state", "entity_id": "input_boolean.hvac_auto_mode", "state": "on"}],
        "actions": [
            {"variables": {"home": "{{ states('zone.home') | int(0) > 0 }}", "asleep": asleep}},
            {"action": "input_select.select_option",
             "target": {"entity_id": "input_select.hvac_house_mode"},
             "data": {"option": "{{ 'Away' if not home else ('Sleep' if asleep else 'Home') }}"}},
        ],
    }


def package():
    booleans, numbers, selects, datetimes = helpers()
    sensors = [s for r in ROOMS for s in room_sensors(r)] + [open_sensor()]
    return {
        "input_boolean": booleans,
        "input_number": numbers,
        "input_select": selects,
        "input_datetime": datetimes,
        "template": [{"sensor": sensors}],
        "automation": [seed_defaults(), controller(), zoning_off(), house_mode_auto()],
    }


# ---------------------------------------------------------------- dashboard

def section():
    cards = [
        {"type": "heading", "heading": "Zones", "icon": "mdi:home-thermometer"},
        {"type": "tile", "entity": CONTROL, "name": "Controlled by",
         "grid_options": {"columns": "full"}, "features": [{"type": "select-options"}]},
        {"type": "tile", "entity": "input_select.hvac_zone_call", "name": "Calling for",
         "icon": "mdi:hvac"},
        {"type": "tile", "entity": "input_select.hvac_house_mode", "name": "House mode",
         "grid_options": {"columns": "full"},
         "features": [{"type": "select-options"}]},
        {"type": "tile", "entity": "sensor.hvac_registers_open", "name": "Registers open"},
    ]
    for r in ROOMS:
        if not r["sensor"] and not r["vents"]:
            continue
        s = slug(r)
        cards.append({"type": "heading", "heading": r["name"], "heading_style": "subtitle"})
        if r["sensor"]:
            cards.append({"type": "tile", "entity": f"sensor.{s}_temperature", "name": "Temperature",
                          "features": [{"type": "trend-graph", "hours_to_show": 24}]})
            cards.append({"type": "tile", "entity": f"sensor.{s}_status", "name": "Status",
                          "state_content": "label"})
        for v in r["vents"]:
            cards.append({"type": "tile", "entity": v, "name": "Vent",
                          "features": [{"type": "cover-position"}]})
    settings = [{"type": "heading", "heading": "Zone settings", "icon": "mdi:tune"}]
    for m in MODES:
        for kind in ("heat", "cool"):
            settings.append({"type": "tile", "entity": f"input_number.hvac_{mode_key(m)}_{kind}",
                             "features": [{"type": "numeric-input", "style": "buttons"}]})
    settings += [
        {"type": "tile", "entity": "input_datetime.hvac_sleep_time"},
        {"type": "tile", "entity": "input_datetime.hvac_wake_time"},
        {"type": "tile", "entity": "input_boolean.hvac_auto_mode", "name": "Auto house mode",
         "tap_action": {"action": "toggle"}},
    ]
    return [{"type": "grid", "cards": cards}, {"type": "grid", "cards": settings}]


def write(path, header, data):
    text = yaml.dump(data, Dumper=yaml.SafeDumper, sort_keys=False, width=10_000,
                     allow_unicode=True)
    (ROOT / path).write_text(header + text)


def main():
    header = ("# GENERATED by tools/hvac_zones.py: edit ROOMS / MODES there and re-run\n"
              "# it, don't edit this file by hand.\n")
    write("packages/hvac_zones.yaml", header, package())
    zones, settings = section()
    write("dashboard/views/hvac_zones_section.yaml", header, zones)
    write("dashboard/views/hvac_zones_settings_section.yaml", header, settings)
    print("wrote packages/hvac_zones.yaml and dashboard/views/hvac_zones_*section.yaml")


if __name__ == "__main__":
    sys.exit(main())
