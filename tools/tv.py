#!/usr/bin/env python3
"""Generate packages/tv.yaml: what's playing on each Google TV, for apps
that don't tell Google Cast (Netflix, Sling, Dropout, 2nd Try, ...).

Each TV's Android Debug Bridge entity (androidtv integration) is asked for
Android's media sessions every 20 seconds while the TV is on. Apps publish
their title and show there for the TV's own "now playing" display. The
reply lands in the ADB entity's adb_response attribute; it's trimmed on the
TV to the few lines needed, without the playback position, so it only
changes (and gets recorded) when the programme or play/pause changes.

Per TV this makes:
  sensor.tv_<key>_session          playing / paused / idle, with title,
                                   subtitle and app attributes
  media_player.<key>_now_playing   the ADB player with that title added
                                   (Universal Media Player), so the Home
                                   tab's media card can show it and its
                                   controls still work

To add a TV, add it to TVS (and to the Home tab's "Now playing" card in
dashboard/views/home.yaml), then run:  python3 tools/tv.py
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

TVS = [
    {"key": "main_room_tv", "name": "Main Room TV",
     "adb": "media_player.living_room_main_room_tv_adb"},
    {"key": "game_room_tv", "name": "Game Room TV",
     "adb": "media_player.game_room_game_room_tv_adb"},
    {"key": "bedroom_tv", "name": "Bedroom TV",
     "adb": "media_player.bedroom_bedroom_tv_adb"},
]

# Run on the TV: each session's app, whether it's active, its playback
# state (minus position, which changes every poll) and its description
# ("Title, Subtitle, Description").
COMMAND = ("dumpsys media_session"
           " | grep -E 'package=|active=|state=PlaybackState|description='"
           " | sed -E 's/, position=.*//'")

# Android PlaybackState numbers.
PLAYING, PAUSED, BUFFERING = 3, 2, 6


def parse(adb):
    """Jinja: the most relevant session (playing, else paused/buffering) as
    `pick`, a dict with package, state and description."""
    return (
        f"{{%- set lines = (state_attr('{adb}', 'adb_response') or '').split('\\n') %}}"
        "{%- set ns = namespace(sessions=[], cur={}) %}"
        "{%- for raw in lines %}{%- set l = raw | trim %}"
        "{%- if l.startswith('package=') %}"
        "{%- if ns.cur %}{%- set ns.sessions = ns.sessions + [ns.cur] %}{%- endif %}"
        "{%- set ns.cur = {'package': l[8:], 'state': 0, 'description': ''} %}"
        "{%- elif 'state=PlaybackState {state=' in l %}"
        "{%- set ns.cur = dict(ns.cur, state=l.split('state=PlaybackState {state=')[1]"
        ".split(',')[0] | int(0)) %}"
        "{%- elif 'description=' in l %}"
        "{%- set ns.cur = dict(ns.cur, description=l.split('description=', 1)[1]) %}"
        "{%- endif %}{%- endfor %}"
        "{%- if ns.cur %}{%- set ns.sessions = ns.sessions + [ns.cur] %}{%- endif %}"
        f"{{%- set pick = (ns.sessions | selectattr('state', 'eq', {PLAYING}) | list"
        f" + ns.sessions | selectattr('state', 'in', [{PAUSED}, {BUFFERING}]) | list"
        " + [{}]) | first %}"
        "{%- set parts = (pick.description or '').split(', ') %}"
    )


def session_sensor(tv):
    adb = tv["adb"]
    return {
        "name": f"TV {tv['name']} Session",
        "unique_id": f"tv_{tv['key']}_session",
        "icon": "mdi:television-play",
        "state": parse(adb) + (
            f"{{{{ 'playing' if pick.state == {PLAYING} else 'paused'"
            f" if pick.state in [{PAUSED}, {BUFFERING}] else 'idle' }}}}"),
        "attributes": {
            "title": parse(adb) + "{{ parts[0] if parts[0] not in ['', 'null'] else '' }}",
            "subtitle": parse(adb) + (
                "{{ parts[1] if parts | count > 1 and parts[1] not in ['', 'null'] else '' }}"),
            # The foreground app's name if that's the session shown, else
            # the session's package (e.g. paused YouTube behind Netflix).
            "app": parse(adb) + (
                f"{{{{ (state_attr('{adb}', 'app_name') or pick.package)"
                f" if not pick.package or state_attr('{adb}', 'app_id') == pick.package"
                " else pick.package }}"),
        },
    }


def now_playing(tv):
    session = f"sensor.tv_{tv['key']}_session"
    return {
        "platform": "universal",
        "name": f"{tv['name']} Now Playing",
        "unique_id": f"tv_{tv['key']}_now_playing",
        "device_class": "tv",
        "children": [tv["adb"]],
        "state_template": (
            f"{{{{ states('{session}') if states('{session}') in ['playing', 'paused']"
            f" else states('{tv['adb']}') }}}}"),
        "attributes": {
            "media_title": f"{session}|title",
            "media_artist": f"{session}|subtitle",
            "app_name": f"{session}|app",
        },
    }


def package():
    adbs = [tv["adb"] for tv in TVS]
    return {
        "automation": [{
            "id": "tv_media_session_poll",
            "alias": "TVs: read what's playing (media sessions over ADB)",
            "description": "Generated by tools/tv.py. Asks each TV that's on what its "
                           "apps are playing, every 20 seconds.",
            "mode": "single",
            "max_exceeded": "silent",
            "triggers": [{"trigger": "time_pattern", "seconds": "/20"}],
            "actions": [{
                "repeat": {
                    "for_each": adbs,
                    "sequence": [{
                        "if": [{"condition": "template",
                                "value_template": "{{ states(repeat.item) not in "
                                                  "['off', 'unavailable', 'unknown'] }}"}],
                        "then": [{
                            "action": "androidtv.adb_command",
                            "target": {"entity_id": "{{ repeat.item }}"},
                            "data": {"command": COMMAND},
                            "continue_on_error": True,
                        }],
                    }],
                },
            }],
        }],
        "template": [{"sensor": [session_sensor(tv) for tv in TVS]}],
        "media_player": [now_playing(tv) for tv in TVS],
    }


def main():
    header = ("# GENERATED by tools/tv.py: edit TVS there and re-run, don't edit this\n"
              "# file by hand.\n")
    text = yaml.dump(package(), Dumper=yaml.SafeDumper, sort_keys=False, width=10_000,
                     allow_unicode=True)
    (ROOT / "packages/tv.yaml").write_text(header + text)
    print("wrote packages/tv.yaml")


if __name__ == "__main__":
    main()
