#!/usr/bin/env python3
"""Generate packages/tv_overlay.yaml: pop-ups and corner badges on the TVs
through TvOverlay (com.tabdeveloper.tvoverlay, from the Play Store).

TvOverlay runs a small web server on each TV (port 5001). Home Assistant
POSTs to it:
  /notify        a pop-up: title, message, image, icons, for a few seconds
  /notify_fixed  a corner badge: icon + short text, until removed/expired
Messages only go to TVs that are on (their ADB player isn't off), so a TV
in standby doesn't make a send fail.

Pop-ups:  doorbell (with a camera snapshot), a new household alert, laundry
          done, hens too hot/cold
Badges:   outside temperature, alerts, laundry waiting, coop comfort;
          refreshed when they change, every 10 minutes, and when a TV turns
          on (a restarted TV forgets them)
Watchdog: when a TV turns on, start TvOverlay if it isn't running (then
          press Home, so you land on the home screen as usual)

Fill in SETTINGS below (TV IP addresses, Home Assistant's address, the
doorbell's entities), then run:  python3 tools/tvoverlay.py
"""

from pathlib import Path

import yaml

from tv import TVS

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "com.tabdeveloper.tvoverlay"
PORT = 5001

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# Each TV's IP address (keys from TVS in tools/tv.py). A TV left as None
# gets nothing. Find them with the "ip" ADB command in docs/tvoverlay.md.
TV_IPS = {
    "main_room_tv": None,
    "game_room_tv": None,
    "bedroom_tv": None,
}
# Home Assistant's address as the TVs reach it, for pictures (the doorbell
# snapshot is saved under /config/www/tvoverlay/ and served from /local/).
HA_URL = None                 # e.g. "http://192.168.1.10:8123"
# The doorbell: the entity that changes when it's pressed (UniFi Protect:
# event.<name>_doorbell, or binary_sensor.<name>_doorbell) and its camera.
DOORBELL_TRIGGER = "binary_sensor.front_doorbell_doorbell"
DOORBELL_CAMERA = "camera.front_doorbell_high_resolution_channel"

# Colours (hex) used on the TV.
RED, BLUE, AMBER, GREEN = "#e5484d", "#3b82f6", "#f5a524", "#30a46c"

SKY_ICONS = {
    "Sunny": "mdi:weather-sunny", "Partly cloudy": "mdi:weather-partly-cloudy",
    "Cloudy": "mdi:weather-cloudy", "Rain": "mdi:weather-rainy",
    "Snow": "mdi:weather-snowy", "Night": "mdi:weather-night",
    "Fog": "mdi:weather-fog",
}


def targets():
    """The TVs with an IP: [{host, adb}] for the scripts' loops."""
    return [{"host": TV_IPS[tv["key"]], "adb": tv["adb"]}
            for tv in TVS if TV_IPS.get(tv["key"])]


ON = ("{{ states(repeat.item.adb) not in "
      "['off', 'standby', 'unavailable', 'unknown'] }}")


def rest_command(path):
    return {
        "url": f"http://{{{{ host }}}}:{PORT}/{path}",
        "method": "post",
        "content_type": "application/json; charset=utf-8",
        "payload": "{{ payload | to_json }}",
        "timeout": 5,
    }


def popup_script():
    """script.tv_popup: a pop-up on every TV that's on."""
    # TvOverlay's README and its Home Assistant sample name some fields
    # differently (duration/seconds, source/appTitle, smallIconColor/color);
    # both are sent, the app ignores the ones it doesn't use.
    payload = (
        "{%- set p = {'title': title | default(''), 'message': message | default(''),"
        " 'source': 'Home Assistant', 'appTitle': 'Home Assistant',"
        " 'smallIcon': small_icon | default('mdi:home-assistant'),"
        " 'smallIconColor': color | default('#049cdb'), 'color': color | default('#049cdb'),"
        " 'duration': seconds | default(12) | int, 'seconds': seconds | default(12) | int} %}"
        "{%- if id is defined %}{% set p = dict(p, id=id) %}{% endif %}"
        "{%- if image is defined and image %}{% set p = dict(p, image=image) %}{% endif %}"
        "{%- if large_icon is defined %}{% set p = dict(p, largeIcon=large_icon) %}{% endif %}"
        "{%- if corner is defined %}{% set p = dict(p, corner=corner) %}{% endif %}"
        "{{ p }}")
    return {
        "alias": "TVs: pop-up",
        "icon": "mdi:television-ambient-light",
        "mode": "parallel",
        "fields": {
            "title": {"description": "Big text", "example": "Washer is done"},
            "message": {"description": "Smaller text", "example": "Time to move it to the dryer"},
            "small_icon": {"description": "mdi: icon", "example": "mdi:washing-machine"},
            "large_icon": {"description": "mdi: icon or image URL"},
            "image": {"description": "Picture URL the TVs can reach"},
            "color": {"description": "Icon colour", "example": BLUE},
            "seconds": {"description": "How long it shows", "example": 12},
            "corner": {"description": "bottom_start, bottom_end, top_start or top_end"},
            "id": {"description": "Replaces an earlier pop-up with the same id"},
        },
        "sequence": [
            {"variables": {"payload": payload}},
            {"repeat": {"for_each": targets(), "sequence": [{
                "if": [{"condition": "template", "value_template": ON}],
                "then": [{"action": "rest_command.tvoverlay_notify",
                          "data": {"host": "{{ repeat.item.host }}",
                                   "payload": "{{ payload }}"},
                          "continue_on_error": True}],
            }]}},
        ],
    }


def badge(badge_id, visible, message, icon, color, expiration=None):
    b = {"id": badge_id, "visible": visible, "message": message, "text": message,
         "icon": icon, "iconColor": color, "borderColor": color,
         "messageColor": "#FFFFFF", "textColor": "#FFFFFF",
         "backgroundColor": "#99000000", "shape": "rounded"}
    if expiration:
        b["expiration"] = expiration
    return b


def badges_script():
    """script.tv_badges: sends every badge (shown or removed) to every TV
    that's on. Cheap enough to just resend them all."""
    sky = "{%- set icons = " + str(SKY_ICONS) + " %}"
    badges = [
        # Outside temperature, by the weather station's sky.
        badge("weather", True,
              "{{ states('sensor.station_temperature') | float(0) | round(0) | int }}°",
              sky + "{{ icons.get(states('sensor.station_sky'), 'mdi:thermometer') }}",
              "#FFFFFF", expiration="1h"),
        # Something needs attention (the Home tab's red banner).
        badge("alerts",
              "{{ states('sensor.household_alerts') not in "
              "['All good', 'unknown', 'unavailable'] }}",
              "{{ states('sensor.household_alerts') | truncate(40) }}",
              "mdi:alert-circle", RED),
        # A load waiting to be emptied.
        badge("laundry",
              "{{ is_state('input_select.washer_state', 'Done')"
              " or is_state('input_select.dryer_state', 'Done') }}",
              "{%- set w = is_state('input_select.washer_state', 'Done') %}"
              "{%- set d = is_state('input_select.dryer_state', 'Done') %}"
              "{{ 'Washer & dryer done' if w and d else 'Washer done' if w else 'Dryer done' }}",
              "{{ 'mdi:tumble-dryer' if is_state('input_select.dryer_state', 'Done')"
              " and not is_state('input_select.washer_state', 'Done')"
              " else 'mdi:washing-machine' }}",
              BLUE),
        # The hens aren't comfortable.
        badge("coop",
              "{{ states('sensor.chicken_comfort') in "
              "['Very cold', 'Chilly', 'Warm', 'Hot', 'Heat danger'] }}",
              "Hens: {{ states('sensor.chicken_comfort') | lower }}",
              "mdi:egg",
              "{{ '" + BLUE + "' if states('sensor.chicken_comfort') in ['Very cold', 'Chilly']"
              " else '" + RED + "' if states('sensor.chicken_comfort') == 'Heat danger'"
              " else '" + AMBER + "' }}"),
    ]
    return {
        "alias": "TVs: refresh corner badges",
        "icon": "mdi:television-guide",
        "mode": "queued",
        "max": 3,
        "sequence": [
            {"variables": {"badges": badges}},
            {"repeat": {"for_each": targets(), "sequence": [{
                "if": [{"condition": "template", "value_template": ON}],
                "then": [{"variables": {"host": "{{ repeat.item.host }}"}},
                         {"repeat": {"for_each": "{{ badges }}", "sequence": [{
                             "action": "rest_command.tvoverlay_fixed",
                             "data": {"host": "{{ host }}",
                                      "payload": "{{ repeat.item }}"},
                             "continue_on_error": True,
                         }]}}],
            }]}},
        ],
    }


def popup(title, message, icon, color, seconds=12, **extra):
    data = {"title": title, "message": message, "small_icon": icon,
            "large_icon": icon, "color": color, "seconds": seconds}
    data.update(extra)
    return {"action": "script.tv_popup", "data": data}


def automations():
    adbs = [tv["adb"] for tv in TVS]
    autos = [
        {
            "id": "tv_overlay_watchdog",
            "alias": "TVs: keep TvOverlay running, refresh badges when a TV turns on",
            "mode": "parallel",
            "triggers": [{"trigger": "state", "entity_id": adbs,
                          "from": ["off", "standby", "unavailable"], "for": "00:00:10"}],
            "conditions": [{"condition": "template",
                            "value_template": "{{ trigger.to_state.state not in "
                                              "['off', 'standby', 'unavailable', 'unknown'] }}"}],
            "actions": [
                # Start it only if it isn't running, then back to Home.
                {"action": "androidtv.adb_command",
                 "target": {"entity_id": "{{ trigger.entity_id }}"},
                 "data": {"command": (
                     f"pidof {PACKAGE} >/dev/null || (monkey -p {PACKAGE}"
                     " -c android.intent.category.LEANBACK_LAUNCHER 1;"
                     " sleep 4; input keyevent KEYCODE_HOME)")},
                 "continue_on_error": True},
                {"delay": "00:00:08"},
                {"action": "script.tv_badges"},
            ],
        },
        {
            "id": "tv_overlay_badges",
            "alias": "TVs: refresh corner badges when they change",
            "mode": "queued",
            "max": 2,
            "triggers": [
                {"trigger": "state", "entity_id": [
                    "sensor.household_alerts", "input_select.washer_state",
                    "input_select.dryer_state", "sensor.chicken_comfort",
                    "sensor.station_sky"]},
                {"trigger": "time_pattern", "minutes": "/10"},
            ],
            "actions": [{"action": "script.tv_badges"}],
        },
        {
            "id": "tv_overlay_alert_popup",
            "alias": "TVs: pop up new household alerts",
            "mode": "queued",
            "triggers": [{"trigger": "state", "entity_id": "sensor.household_alerts"}],
            "conditions": [{"condition": "template", "value_template": (
                "{{ trigger.to_state.state not in ['All good', 'unknown', 'unavailable']"
                " and trigger.from_state is not none"
                " and trigger.from_state.state not in ['unknown', 'unavailable'] }}")}],
            "actions": [popup("Needs attention", "{{ trigger.to_state.state }}",
                              "mdi:alert-circle", RED, 15, id="household_alert")],
        },
        {
            "id": "tv_overlay_laundry_popup",
            "alias": "TVs: pop up when the laundry is done",
            "mode": "queued",
            "triggers": [{"trigger": "state", "entity_id": "input_select.washer_state",
                          "from": "Running", "to": "Done", "id": "washer"},
                         {"trigger": "state", "entity_id": "input_select.dryer_state",
                          "from": "Running", "to": "Done", "id": "dryer"}],
            "actions": [popup(
                "{{ 'Washer' if trigger.id == 'washer' else 'Dryer' }} is done",
                "{{ 'Time to move it to the dryer' if trigger.id == 'washer'"
                " else 'Time to fold' }}",
                "{{ 'mdi:washing-machine' if trigger.id == 'washer' else 'mdi:tumble-dryer' }}",
                BLUE, 15)],
        },
        {
            "id": "tv_overlay_coop_popup",
            "alias": "TVs: pop up when the hens are too hot or cold",
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": "sensor.chicken_comfort",
                          "to": ["Very cold", "Hot", "Heat danger"], "for": "00:10:00"}],
            "actions": [popup(
                "Hens are {{ trigger.to_state.state | lower }}",
                "{{ state_attr('sensor.chicken_comfort', 'note') or '' }}",
                "mdi:egg",
                "{{ '" + BLUE + "' if trigger.to_state.state == 'Very cold' else '" + RED + "' }}",
                20)],
        },
    ]
    if DOORBELL_TRIGGER and DOORBELL_CAMERA and HA_URL:
        autos.append({
            "id": "tv_overlay_doorbell",
            "alias": "TVs: doorbell pop-up with a snapshot",
            "mode": "single",
            "max_exceeded": "silent",
            "triggers": [{"trigger": "state", "entity_id": DOORBELL_TRIGGER}],
            "conditions": [{"condition": "template", "value_template": (
                "{{ trigger.to_state.state not in ['unknown', 'unavailable', 'off']"
                " and trigger.from_state is not none }}")}],
            "actions": [
                {"action": "camera.snapshot", "target": {"entity_id": DOORBELL_CAMERA},
                 "data": {"filename": "/config/www/tvoverlay/doorbell.jpg"},
                 "continue_on_error": True},
                popup("Someone's at the door", "Front doorbell", "mdi:doorbell-video",
                      AMBER, 25, corner="top_end", id="doorbell",
                      image=f"{HA_URL}/local/tvoverlay/doorbell.jpg?t={{{{ now().timestamp() | int }}}}"),
                {"delay": "00:00:30"},
            ],
        })
    return autos


def package():
    return {
        "rest_command": {
            "tvoverlay_notify": rest_command("notify"),
            "tvoverlay_fixed": rest_command("notify_fixed"),
        },
        "script": {"tv_popup": popup_script(), "tv_badges": badges_script()},
        "automation": automations(),
    }


def main():
    header = ("# GENERATED by tools/tvoverlay.py: edit its SETTINGS and re-run, don't\n"
              "# edit this file by hand. Setup: docs/tvoverlay.md\n")
    text = yaml.dump(package(), Dumper=yaml.SafeDumper, sort_keys=False, width=10_000,
                     allow_unicode=True)
    (ROOT / "packages/tv_overlay.yaml").write_text(header + text)
    print(f"wrote packages/tv_overlay.yaml ({len(targets())} TV(s) with an IP)")


if __name__ == "__main__":
    main()
