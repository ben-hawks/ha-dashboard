# Laundry monitor (washer & dryer)

Two smart plugs measure the washer's and dryer's power draw. Home Assistant
works out when a cycle starts and finishes, sends a push notification to the
phones when a load is done, and nags if it sits there. The wall tablet shows
the machines while they're running and lets anyone tap "emptied".

**Status:** set up ahead of the plugs arriving. The package can be installed
now; it does nothing (and the dashboard shows nothing) until the plugs report
power.

## Hardware

- 2× **Athom ESP32-C3 US plug (V3, PG03V3-US16A)**: CSE7766 power metering,
  16 A relay, ships with ESPHome. Upstream config:
  `github://athom-tech/esp32-configs/athom-smart-plug.yaml`, imported as a
  package and overridden (not forked).
- Washer: 120 V. Dryer: **gas**, so the plug only sees the drum motor,
  controls and igniter (tens to a few hundred watts, not kilowatts).
- 2.4 GHz Wi-Fi.

## Files

| File | What it is |
|------|------------|
| `esphome/laundry-washer.yaml`, `esphome/laundry-dryer.yaml` | Mirrors of `washer.yaml` / `dryer.yaml` in the ESPHome Device Builder. The Device Builder copies are the source of truth; keep these in sync. API keys are `!secret` placeholders here (the builder copies have the literal keys). Builder secrets used: `wifi_ssid`, `wifi_password`, `fallback_ap_password`. |
| `packages/laundry.yaml` | All the Home Assistant logic: running sensors, Idle/Running/Done states, automations, notifications, the emptied button, WashData details. |
| `tools/laundry_profile.py` | Reads a cycle's power history from Home Assistant and suggests thresholds and delays. Standard library only. |
| `dashboard/views/home.yaml` | Washer/Dryer tiles under "Around the house", only while running or done. |
| `dashboard/views/devices.yaml` | Laundry section: state, live power, "emptied" buttons. Hidden until a plug reports power. |
| `packages/wall_tablet.yaml` | "Washer is done" / "Dryer is done" in the red Home banner. |

## Setting it up

### Now (before the plugs arrive)

1. Install the package: add `laundry: !include ha-dashboard/packages/laundry.yaml`
   under `homeassistant: packages:` (see [install.md](install.md)).
2. **Phones.** Notifications go to Ben's (`mobile_app_pixel_11`) and
   Megan's (`mobile_app_pixel_11_meg`) Pixels, listed at the top of
   `packages/laundry.yaml` under `notify:`. To add a phone, install the
   Companion app on it, find its name under Developer Tools → Actions
   (search "mobile_app"; use the part after `notify.`) and add a line.
3. Check configuration and restart. Test the notification from Developer
   Tools → Actions:

   ```yaml
   action: script.laundry_notify
   data:
     appliance: washer
     message: Test – ignore
   ```

   Every phone in the group should get it with an **Emptied** button.

### When the plugs arrive

1. Plug each one in on Athom's stock firmware and get it onto the 2.4 GHz
   Wi-Fi (its own hotspot / captive portal). Note its IP address.
2. In the ESPHome Device Builder, install `washer.yaml` / `dryer.yaml`
   **over the air to that IP** (the hostname changes from
   `athom-smart-plug-v3-xxxxxx` to `washer` / `dryer`, so the first install
   can't find it by name).
3. Adopt them in **Settings → Devices & services → ESPHome**. With the
   friendly names "Washer" / "Dryer" and no MAC suffix, the power sensors
   are `sensor.washer_power` and `sensor.dryer_power`, which is what the
   package expects. Put both in the Laundry area.
4. Plug the washer and dryer into them.
5. Run one normal cycle on each machine, then tune (below).

## How it works

- **The plug relay must never cut power mid-cycle.** Power-on state is
  Always On, the physical button is child-locked, and the relay switch is
  disabled by default in Home Assistant. Athom's 16 A over-current cut-off
  stays; if it ever trips, unplug and replug (it boots on).
- **Detection lives in Home Assistant, not on the plug**, so thresholds can
  be tuned without reflashing. "Running" is a template binary sensor with
  hysteresis (it must go above the higher threshold to start, below the
  lower one to stop) plus `delay_on` / `delay_off`:
  - Washer: a 5-minute `delay_off` rides out soaks and fills at near-zero
    watts.
  - Dryer: a 2-minute `delay_on` so wrinkle-guard tumbles after the cycle
    never count as a new one.
- Each machine has a state: **Idle → Running → Done → Idle**. Done goes back
  to Idle when someone taps **Emptied** (phone notification, Home tile or
  Devices tab), when the next cycle starts, or after 6 hours.
- Automations only react to explicit `off`→`on` / `on`→`off` changes, so a
  plug dropping offline never fakes a start or finish.

### Notifications

| When | Message |
|------|---------|
| Washer finishes | "Washer is done (52 min)." |
| Washer still not emptied | after 30 min and 1 h 30 min: "Wet clothes are still in the washer." |
| Dryer finishes | "Dryer is done (48 min)." |
| Dryer still not emptied | after 45 min: "Clothes are still in the dryer." |

All of them go to `notify.laundry` (the phone group at the top of the
package). Each machine's notifications share one tag, so a reminder replaces
the earlier notification rather than piling up, and once the machine leaves
Done the notification is cleared from every phone. On Android they use their
own **Laundry** notification channel (set its sound in the phone's app
notification settings); on iOS they're time-sensitive.

## Emptied button by the machines (IKEA BILRESA dual button)

A BILRESA dual button (Matter over Thread, AAA batteries) on the wall
between the machines:

| Press | Does |
|-------|------|
| Button 1, short | Washer emptied |
| Button 2, short | Dryer emptied |
| Either, long | Both emptied (a load moved over and the other emptied) |

It only acts on a machine that's **Done**, so a stray press never upsets a
cycle in progress. It does the same as **Emptied** on a phone or the tablet:
back to Idle, notification cleared everywhere.

1. **Pair it:** Settings → Devices & services → Add device → **Matter**,
   with the Home Assistant app on a phone (it scans the QR code on the
   button). Thread comes from the HA Yellow (OpenThread Border Router
   add-on). Name the device **Laundry Button**, area Laundry.
2. **Rename its two event entities** (device page → each event entity → ⚙ →
   Entity ID): the first button to `event.laundry_button_washer`, the second
   to `event.laundry_button_dryer`. Not sure which is which? Press one and
   see which entity's time changes.
3. Test: with a machine on Done (or set `input_select.washer_state` to Done
   in Developer Tools → States), press its button; it should go to Idle.

If a press does nothing, look at the event entity's **event_type** after a
press (Developer Tools → States). The automation (`laundry_button` in
`packages/laundry.yaml`) acts on `multi_press_1`, `short_release` and
`long_press`; if the button reports other names, add them there.

## WashData (once the plugs work)

[WashData](https://github.com/3dg1luk43/ha_washdata) (HACS) learns each
machine's programs from the power curve and estimates time left. Our own
detection stays in charge of Idle/Running/Done and the notifications;
WashData adds detail:

- The Home tiles while running: "Normal · 23 min left" instead of "Running"
  (`sensor.washer_cycle` / `sensor.dryer_cycle`).
- The "done" notification names the program: "Washer is done (52 min,
  Normal)."

Set-up, after the plugs report power:

1. HACS → search **WashData** → Download → restart.
2. Settings → Devices & services → Add integration → **WashData**, twice:
   - Name **WashData Washer**, type Washer, power sensor
     `sensor.washer_power`.
   - Name **WashData Dryer**, type Dryer, power sensor `sensor.dryer_power`.

   Use exactly these names: the package looks for
   `sensor.washdata_washer_program`, `…_time_remaining` and `…_progress`
   (and the same for the dryer). Plain "Washer" would also clash with our
   `binary_sensor.washer_running`.
3. **Leave WashData's own notifications off**, or every load notifies twice.
4. Teach it: after each load, label the cycle with its program in
   WashData's panel (Cycles tab). It shows "unknown" until a program has
   been labelled a few times.

Its program matching is still changing from release to release, so it
only adds detail for now. Once its cycle ends prove reliable, Idle/Running/
Done could follow its state sensor instead of our thresholds.

## Tuning

Thresholds in `packages/laundry.yaml` are starting guesses. After one normal
cycle on a machine:

```sh
export HA_URL=http://homeassistant.local:8123
export HA_TOKEN=<long-lived access token>
python3 tools/laundry_profile.py sensor.washer_power --hours 6
python3 tools/laundry_profile.py sensor.dryer_power --hours 6
```

It prints suggested on/off thresholds and delays; copy them into the
`Washer running` / `Dryer running` sensors. Offline: `--csv FILE` with
`timestamp,watts` rows.

## Checking it

- ESPHome: Validate in the Device Builder.
- Home Assistant: Developer Tools → YAML → Check configuration (or
  `ha core check`).
- Profiler: `python3 tools/laundry_profile.py --csv <file>`.

## Ideas

- Fold the washer/dryer duplication into a blueprint.
- "Washer done, dryer free" nudge to move the clothes over.
- Log energy (kWh) per cycle; cycle-length statistics.
- On-plug cycle detection in ESPHome as a fallback when Home Assistant is down.
- Only notify people who are home.
