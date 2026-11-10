# Bedroom ceiling fan (Hunter, 433 MHz RF bridge)

A LilyGO T3 LoRa32 V1.6.1 (433 MHz) running ESPHome sends the bedroom Hunter
fan's RF remote codes, so Home Assistant can run the fan and its light. It
also hears the real remote, so HA keeps up when someone uses it.

On the dashboard: **Rooms → Bedroom** has *Fan* (tap to switch on/off, speed
buttons under it) and *Fan light*. "All lights off" includes the fan light.

- Board: LilyGO T3 LoRa32 **V1.6.1, 433 MHz** (ESP32 + SX1278, OLED)
- Remote: Hunter K5579-02 / 99372, FCC ID IN2TX50, 433.92 MHz
- File: `esphome/hunter-fan-rf.yaml` (mirror of `hunter-fan-rf.yaml` in the
  ESPHome Device Builder, which has the real API key)

## Status

| Phase | What | State |
|-------|------|-------|
| 1 | **Capture**: log what each remote button sends | Done: fixed codes, decoded below |
| 2 | **Replay**: HA buttons that send each code; check the fan obeys | Done: the fan obeys all four at 10 dBm |
| 3 | **HA entities**: fan (speeds) + light, kept in sync with the real remote | Firmware ready, to be checked with the real remote |

## The remote's protocol

Decoded from 6 presses of each button (2026-11-10). Every press of a button
sends the same bits, so it's a **fixed code** and can be replayed.

- **Fan:** 3 speeds. **Light:** on/off only. Every button is a toggle or a
  step (power, faster, slower), so the fan doesn't say what state it's in.
- **Each press:** 12 short wake-up pulses (about 380 µs on, 390 off), a gap,
  then a 65-bit frame. The frame is sent about 3 times per press.
- **Bits:** pulse width, unit about 390 µs. `0` = 1 unit on, 2 off.
  `1` = 2 on, 1 off. A short pulse closes the frame.
- **Layout:** 20-bit header (19 zeros, then 1), 24-bit remote ID
  `0x9CAEBC` (the same on every button), then 21 bits for the button.

| Button | 65 bits |
|--------|---------|
| Light (toggle) | `00000000000000000001001110010101110101111001100000000110011111111` |
| Fan power (toggle) | `00000000000000000001001110010101110101111000000100011111111011100` |
| Fan faster | `00000000000000000001001110010101110101111001000000001110111111110` |
| Fan slower | `00000000000000000001001110010101110101111001000000010110111111101` |

Never measured: the gap after the wake-up pulses and the gap between
repeats. The firmware sends 6 ms and 10 ms (`pre_gap_us`, `repeat_gap_ms`)
and the fan accepts them.

How the fan reacts (tested): Light and Fan power toggle. Faster/Slower step
the speed, stop at High/Low, and do nothing while the fan is off. Fan power
resumes the last speed.

Generic decoders don't fit this remote: the logs called it rc_switch, Pronto,
Beo4 and CanalSat, with different results every frame. The firmware has its
own decoder (in `on_raw`) and no generic dumps.

## In Home Assistant

Device **Bedroom Fan** (ESPHome `hunter-fan-rf`):

| Entity | What it does |
|--------|--------------|
| `fan.bedroom_fan` | Off / Low / Medium / High. To reach a speed it sends the right number of Faster/Slower presses (*Press gap* apart, 1 s by default), plus one extra when going to Low or High. That extra press does nothing if the speed was right, and fixes it if it had drifted. |
| `light.bedroom_fan_light` | On / off. |
| `event.bedroom_fan_remote_button` | Fires once for each press of the real remote: `light`, `fan_power`, `speed_up`, `speed_down`. For automations. |
| *Press gap* (configuration) | Pause between presses when it sends several (e.g. High → Low). Default 1000 ms. At 300 ms the fan only took the first step. If multi-step changes still stop short, raise it. |
| *Send … code* (configuration) | Sends one code **without** changing what HA thinks the fan is doing. Use these to fix drift. |

Check the entity IDs after the first install: HA may still name them after
the old device name, *Hunter Fan RF*. If so, rename them, or change the two
Bedroom tiles in `dashboard/views/rooms.yaml`.

### State is a guess

The fan never reports back. The board keeps its own idea of the fan and
light (remembered across restarts) and updates it from what it sends and
what it hears from the real remote. Using the remote is fine. The state
drifts when:

- a press from the remote isn't heard (too far away, or while the board is
  sending), or
- the wall switch cuts the fan's power. The fan comes back in its own
  default state, and the board doesn't know.

**Fixing drift:** a speed that's wrong fixes itself the next time HA sets Low
or High. For on/off, make the room match HA with the *Send … code* buttons:
if HA says the light is off but it's on, press *Send light code*. The room
light goes off and HA stays off.

### It hears itself

The receiver and the transmitter share the radio's data pin, so the board
reads back everything it sends as if the remote had sent it. Frames heard
while sending, or up to 0.2 s after, are ignored. A real remote press in that
window is missed.

## Phase 1: capture the remote (done)

1. **Antenna on first.** Screw on the 433 MHz antenna before powering the
   board. The sniffer build doesn't transmit, but later builds do, and an
   SX1278 keyed up with no antenna can be damaged.
2. **First flash (USB).** In the ESPHome Device Builder, `hunter-fan-rf` →
   **Install** → **Plug into this computer** (or **Manual download**, then
   flash it at web.esphome.io). Later updates go over Wi-Fi.
3. **Add it in HA** when it's discovered.
4. **Open the logs** (Device Builder → `hunter-fan-rf` → **Logs**). Stand a
   few metres from the board and press **each remote button 3–4 times**,
   about a second apart, with a pause between buttons. Say which button
   you're on as you go (or note the time), e.g. *Light*, *Fan off*, *Speed 1*.
5. **Copy the whole log** and paste it back here.

What to look for in the log:

- `Received RCSwitch Raw: protocol=… data='…'`: a clean rc_switch decode.
  The same button should give the same data every press. "Last RF code" in
  HA shows the latest one.
- `Received Raw: …`: the raw pulse timings. If rc_switch never decodes, we
  use these instead.
- If two presses of the same button give **different** data, the remote may
  use a rolling code and can't simply be replayed. Hunter remotes of this
  type are normally fixed-code.

`rx_floor` (a substitution at the top of the file) is **-75 dBm**. At -85
it picked up another 433 MHz device nearby: long frames every few seconds
that the log calls Pronto / Beo4 / Drayton. If those still show up, raise it
(e.g. `-65`). If the Hunter remote isn't heard, lower it again.

## Screen

The OLED has two pages. The **BOOT** button (next to the USB port) flips
between them.

| Page | Shows |
|------|-------|
| **Status** | Link (`HA ok` / `no HA` / `no Wi-Fi`), the fan (Off / Low / Medium / High) and the light (On / Off) as the board thinks they are, and the last button (`Remote: Faster`, `HA: Light`) and how long ago. |
| **Radio** | Frequency and floor, bursts heard (noise included) vs Hunter frames decoded, the last burst's length, IP, uptime. |

It goes dark after **Screen timeout** minutes (in HA under the device's
configuration, default 5, 0 = always on) to spare the OLED, and wakes on a
remote press or the BOOT button.

## Things to note about the remote

Write down for the next phase:

- Which buttons it has (fan off, speeds 1–3 or more, light, reverse, timer…).
- Whether the light dims, and how: separate up/down buttons, or press and
  hold the light button.
- Whether the fan is the 3-speed (AC) kind or has more speeds (DC).
- Whether there is a DIP switch in the battery compartment (the fan's
  "address"); if so, note its positions, but don't change it.
