#!/usr/bin/env python3
"""Generate packages/tv.yaml: what's playing on each Google TV, for apps
that don't tell Google Cast (Netflix, Sling, Dropout, 2nd Try, ...).

Each TV's Android Debug Bridge entity (androidtv integration) is asked for
Android's media sessions every 20 seconds while the TV is on. Apps publish
their title and show there for the TV's own "now playing" display. The
reply lands in the ADB entity's adb_response attribute; it's trimmed on the
TV to the few lines needed, without the playback position, so it only
changes (and gets recorded) when the programme or play/pause changes.
The ADB integration clears that attribute again on its next refresh, so the
session sensors are trigger-based: they update when a reply arrives (or the
TV turns off) and keep their value in between.

Per TV this also makes binary_sensor.tv_<key>_app_playing (see
app_playing), and sensor.tv_<key>_session: playing / paused / idle, with
title, subtitle and app attributes (and a "sessions" summary of what the TV
reported). The Home tab's "Now playing" card shows it with the TV's ADB
player's controls underneath. (A Universal Media Player can't carry the
title: it only overrides state, volume and source, not the title.)

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
           " | sed -E 's/, position=.*//'"
           # Always some reply, so "nothing playing" still counts as an
           # answer (an empty one looks like the integration clearing it).
           "; echo done")

# Android PlaybackState numbers. Newer Android prints them as e.g.
# "state=PLAYING(3)", older as "state=3"; both are read.
PLAYING, PAUSED, BUFFERING = 3, 2, 6

# Friendly names for app packages, where the ADB integration doesn't know
# them. Anything else shows its ADB app name, or its package.
APP_NAMES = {
    "org.smarttube.beta": "SmartTube", "org.smarttube.stable": "SmartTube",
    "com.liskovsoft.smarttubetv.beta": "SmartTube",
    "com.liskovsoft.smarttubetv": "SmartTube",
    "com.google.android.youtube.tv": "YouTube",
    "com.netflix.ninja": "Netflix",
    "org.jellyfin.androidtv": "Jellyfin",
    "com.github.damontecres.wholphin": "Wholphin",
    "com.sling": "Sling TV",
    "com.collegehumor.chdropout": "Dropout",
    "ott.thetryguys": "2nd Try",
}


# The reply that triggered the update (see session_block).
REPLY = "(trigger.to_state.attributes.get('adb_response') or '')"


def parse():
    """Jinja: the most relevant session (playing, else paused/buffering) as
    `pick`, a dict with package, state and description."""
    return (
        f"{{%- set lines = {REPLY}.split('\\n') %}}"
        "{%- set ns = namespace(sessions=[], cur={}) %}"
        "{%- for raw in lines %}{%- set l = raw | trim %}"
        "{%- if l.startswith('package=') %}"
        "{%- if ns.cur %}{%- set ns.sessions = ns.sessions + [ns.cur] %}{%- endif %}"
        "{%- set ns.cur = {'package': l[8:], 'state': 0, 'description': ''} %}"
        "{%- elif 'state=PlaybackState {state=' in l %}"
        "{%- set token = l.split('state=PlaybackState {state=')[1].split(',')[0] | trim %}"
        "{%- set ns.cur = dict(ns.cur, raw_state=token,"
        " state=token.split('(')[-1].rstrip(')') | int(0)) %}"
        "{%- elif 'description=' in l %}"
        "{%- set ns.cur = dict(ns.cur, description=l.split('description=', 1)[1]) %}"
        "{%- endif %}{%- endfor %}"
        "{%- if ns.cur %}{%- set ns.sessions = ns.sessions + [ns.cur] %}{%- endif %}"
        f"{{%- set pick = (ns.sessions | selectattr('state', 'eq', {PLAYING}) | list"
        f" + ns.sessions | selectattr('state', 'in', [{PAUSED}, {BUFFERING}]) | list"
        " + [{}]) | first %}"
        "{%- set parts = (pick.description or '').split(', ') %}"
    )


def session_block(tv):
    """A trigger-based template block for one TV: updates on each ADB reply
    and when the TV goes off, and holds its value otherwise."""
    adb = tv["adb"]
    return {
        "triggers": [
            {"trigger": "state", "entity_id": adb, "attribute": "adb_response"},
            {"trigger": "state", "entity_id": adb, "to": ["off", "unavailable"]},
        ],
        # Skip the moment the integration clears the reply (the TV's still on).
        "conditions": [{
            "condition": "template",
            "value_template": ("{{ trigger.to_state.state in ['off', 'unavailable'] or "
                               + REPLY + " != '' }}"),
        }],
        "sensor": [session_sensor(tv)],
    }


def session_sensor(tv):
    adb = tv["adb"]
    return {
        "name": f"TV {tv['name']} Session",
        "unique_id": f"tv_{tv['key']}_session",
        "icon": "mdi:television-play",
        "state": parse() + (
            f"{{{{ 'playing' if pick.state == {PLAYING} else 'paused'"
            f" if pick.state in [{PAUSED}, {BUFFERING}] else 'idle' }}}}"),
        "attributes": {
            "title": parse() + "{{ parts[0] if parts[0] not in ['', 'null'] else '' }}",
            "subtitle": parse() + (
                "{{ parts[1] if parts | count > 1 and parts[1] not in ['', 'null'] else '' }}"),
            # The shown session's app (e.g. paused YouTube behind Netflix),
            # by friendly name where known.
            "app": parse() + (
                f"{{%- set names = {APP_NAMES} %}}"
                # No session: the TV's foreground app, by ID or, failing that,
                # the ADB integration's app name (often just the package).
                f"{{%- set package = pick.package or state_attr('{adb}', 'app_id')"
                f" or state_attr('{adb}', 'app_name') or '' %}}"
                f"{{{{ names.get(package) or (state_attr('{adb}', 'app_name')"
                f" if state_attr('{adb}', 'app_id') == package else '') or package }}}}"),
            # What the TV reported, for troubleshooting: "app state" per
            # media session, e.g. "org.smarttube.beta PLAYING(3)".
            "sessions": parse() + (
                "{%- set out = namespace(items=[]) %}"
                "{%- for x in ns.sessions %}"
                "{%- set out.items = out.items + [x.package ~ ' ' ~ (x.raw_state or '?')] %}"
                "{%- endfor %}{{ out.items | join('; ') }}"),
        },
    }


def app_playing(tv):
    """A steadier "the TV is playing something" for apps that don't report
    a title (and the TV's volume, for the card): on while the ADB player says playing/paused, held on for a
    minute through its brief state flips, with the app's friendly name kept
    when the ADB attributes are momentarily blank."""
    adb = tv["adb"]
    return {
        "name": f"TV {tv['name']} App Playing",
        "unique_id": f"tv_{tv['key']}_app_playing",
        "icon": "mdi:television-play",
        "state": f"{{{{ states('{adb}') in ['playing', 'paused'] }}}}",
        "delay_off": {"minutes": 1},
        "attributes": {
            "app": (f"{{%- set names = {APP_NAMES} %}}"
                    f"{{%- set package = state_attr('{adb}', 'app_id')"
                    f" or state_attr('{adb}', 'app_name') or '' %}}"
                    "{%- set name = names.get(package) or package %}"
                    "{{ name or (this.attributes.app if this.attributes is defined"
                    " and this.attributes.app is defined else '') }}"),
            # The TV's volume for the card, e.g. "7%" or "Muted"; kept through
            # the moments the ADB attributes are blank.
            "volume": (f"{{%- set v = state_attr('{adb}', 'volume_level') %}}"
                       f"{{%- if state_attr('{adb}', 'is_volume_muted') %}}Muted"
                       "{%- elif v is number %}{{ (v * 100) | round(0) | int }}%"
                       "{%- else %}{{ this.attributes.volume if this.attributes is defined"
                       " and this.attributes.volume is defined else '' }}{%- endif %}"),
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
        "template": [session_block(tv) for tv in TVS]
                    + [{"binary_sensor": [app_playing(tv) for tv in TVS]}],
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
