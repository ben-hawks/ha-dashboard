# Hunter ceiling fan (433 MHz RF bridge)

A LilyGO T3 LoRa32 V1.6.1 (433 MHz) running ESPHome listens to the Hunter
fan's RF remote and will send its codes, so Home Assistant can run the fan
and light. It also hears the real remote, so HA keeps up when someone uses it.

- Board: LilyGO T3 LoRa32 **V1.6.1, 433 MHz** (ESP32 + SX1278, OLED)
- Remote: Hunter K5579-02 / 99372, FCC ID IN2TX50, 433.92 MHz
- File: `esphome/hunter-fan-rf.yaml` (mirror of `hunter-fan-rf.yaml` in the
  ESPHome Device Builder, which has the real API key)

## Status

| Phase | What | State |
|-------|------|-------|
| 1 | **Capture**: log what each remote button sends | Done: fixed codes, decoded below |
| 2 | **Replay**: HA buttons that send each code; check the fan obeys | Firmware ready; gaps still to measure |
| 3 | **HA entities**: fan (speeds) + light, kept in sync with the real remote | Not started |

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

Still to measure: the gap after the wake-up pulses and the gap between
repeats. The firmware sends 6 ms and 10 ms for now (`pre_gap_us`,
`repeat_gap_ms`).

Generic decoders don't fit this remote: the logs called it rc_switch, Pronto,
Beo4 and CanalSat, with different results every frame. The firmware has its
own decoder (in `on_raw`) and no generic dumps.

## Phase 2: replay

**Antenna on.** This build transmits.

In HA, the device has buttons **Light**, **Fan power**, **Fan faster** and
**Fan slower**, plus a **Remote button** event that fires once for each press
of the real remote. To check that it works:

1. Press each HA button and see whether the fan responds. If it doesn't, raise
   `tx_power` (up to 17) and move the board closer, then try again.
2. Press each button on the real remote once and send the log. Lines like
   `Frame: 23, gap 5800 us, 131, gap 9800 us, ...` give the real gaps, and
   I'll set `pre_gap_us` and `repeat_gap_ms` from them.

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
| **Status** | Link (`HA ok` / `no HA` / `no Wi-Fi`), the last button (*Remote* or *Sent from HA*), how long ago, how many frames that press had (`x3`), presses so far. Phase 3 turns this into the fan speed and light. |
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
