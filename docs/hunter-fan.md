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
| 1 | **Capture**: log what each remote button sends | Firmware ready, waiting for captures |
| 2 | **Replay**: HA buttons that send each code; check the fan obeys | Not started |
| 3 | **HA entities**: fan (speeds) + light, kept in sync with the real remote | Not started |

## Phase 1: capture the remote

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

If it can't hear the remote, lower `rx_floor` (e.g. `-95`). If the log
floods with noise while nobody is pressing anything, raise it (e.g. `-75`)
or raise `filter` to `100us`.

## Things to note about the remote

Write down for the next phase:

- Which buttons it has (fan off, speeds 1–3 or more, light, reverse, timer…).
- Whether the light dims, and how: separate up/down buttons, or press and
  hold the light button.
- Whether the fan is the 3-speed (AC) kind or has more speeds (DC).
- Whether there is a DIP switch in the battery compartment (the fan's
  "address"); if so, note its positions, but don't change it.
