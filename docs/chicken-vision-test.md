# Chicken counting: feasibility test

Before building hen counting into Home Assistant (Frigate on the Arc server,
a door counter, a "flock status" sensor), this checks on our own footage
whether it's worth it. `tools/chicken_vision_test.py` runs a stock YOLO
model over clips exported from UniFi Protect and answers three questions:

1. **Does it see the hens?** In the run, in the coop, at dusk, on night vision.
2. **Can it follow them through the pop door?** Count ins and outs across
   a line drawn over the door, and compare with what actually happened.
3. **Is it fast enough?** Milliseconds per frame on the Arc.

Nothing here touches Home Assistant.

## 1. Set up (on the Arc server)

```bash
python3 -m venv ~/chicken-test
```

```bash
~/chicken-test/bin/pip install ultralytics openvino
```

Copy `tools/chicken_vision_test.py` across (or clone this repo there). The
first run downloads the model (`yolo26s.pt`, about 20 MB) into the current
folder.

To use the Arc, OpenVINO has to see it as a GPU:

```bash
~/chicken-test/bin/python -c "import openvino as ov; print(ov.Core().available_devices)"
```

`['CPU', 'GPU']` is what we want. If only `CPU` shows up, install Intel's GPU
compute runtime for your distro (on Ubuntu, the `intel-opencl-icd` and
`libze-intel-gpu1` packages, or Intel's own repository for the newest Arc
support) and make sure your user is in the `render` group. For this test
the CPU is fine too: use `--device intel:cpu`, still fast, or `cpu`, slower
but needs nothing extra. Any laptop works the same way.

## 2. Collect clips

Export these from UniFi Protect (pick the time range on a camera's
timeline, then download). A minute or two each is plenty; more clips beat
longer ones.

| Clip | Camera | Why |
|------|--------|-----|
| Bedtime rush | Door | The case that matters most: hens going in at dusk, often in twos and threes |
| Morning let-out | Door | Everyone leaving at once |
| Busy run, midday | Each run camera | Hens bunched together, behind feeders and each other |
| Run at dusk | Each run camera | Changing light, the camera switching to night vision |
| Night | Inside camera | Night vision, hens on the roosts |

For each clip, **write down the truth while you watch it**: how many went in
and out through the door, and roughly how many hens are in view. The test
only means something compared with that.

## 3. Draw the door line

```bash
~/chicken-test/bin/python chicken_vision_test.py frame bedtime.mp4 --at 5
```

This saves `bedtime_grid.jpg` with a 10% grid. Pick a line across the
doorway (or across the top of the ramp, wherever every hen has to pass),
with its two ends read off the grid, plus any point on the coop side.
Check it:

```bash
~/chicken-test/bin/python chicken_vision_test.py frame bedtime.mp4 --at 5 --line 0.40,0.55,0.62,0.55 --inside 0.5,0.3
```

The line is drawn in orange with an arrow pointing into the coop. A hen
only counts as crossed once she's clearly past it (`--margin`, 2% of the
frame by default), and only near the door, so hens wandering along the
same row of the picture elsewhere don't count.

## 4. Run it

Door clips, with the line:

```bash
~/chicken-test/bin/python chicken_vision_test.py run bedtime.mp4 letout.mp4 --line 0.40,0.55,0.62,0.55 --inside 0.5,0.3 --device intel:gpu
```

Run and inside clips, no line:

```bash
~/chicken-test/bin/python chicken_vision_test.py run run_midday.mp4 run_dusk.mp4 night.mp4 --device intel:gpu
```

Everything goes into `chicken_test/`: an annotated video per clip (boxes,
track numbers, the door line, a running count; plays in VLC), a CSV per
clip with every frame, and `summary.csv` across all clips. Each crossing is
also printed as it happens, e.g. `0:41.3  hen #7 went IN`, so you can jump to
that moment in the annotated video and see whether it was real.

## 5. Read the results

| Look at | Good sign | Bad sign |
|---------|-----------|----------|
| Door crossings vs your truth | Within 1 of the truth per bedtime clip | Off by several, or misses hens that went through in pairs |
| `frames with a hen seen` (run, clips where hens are always in view) | Close to 100% | Long stretches at 0 |
| `hens seen` max/median vs the hens in view | Close, at least when they're spread out | Consistently far below |
| `distinct track ids` vs hens that appeared | Roughly the same | Several times more: tracks keep breaking up (one hen becomes #3, #11, #19), which ruins door counting |
| `detections by class` | Mostly `bird` | Not much of anything, or lots of `cat`/`dog`: try `--classes bird,cat,dog` |
| `speed` | Under about 30 ms per frame on the Arc | |

The stock model has never seen a chicken labelled as one, so it doesn't
have to be perfect here. What we're deciding:

- **Door counts close, run detection decent:** go ahead. Frigate on the
  Arc server, then the door counter.
- **Hens often missed, but the door framing is clean:** still viable. It
  needs a model trained on a few hundred labelled frames from our own
  cameras, the biggest single improvement anyway.
- **Hens bunch up or block the door so you can't tell them apart even by
  eye:** move or re-angle the door camera (looking down at the ramp is
  best) before anything else.

## Things to try when it struggles

| Problem | Try |
|---------|-----|
| Small or distant hens missed | `--imgsz 960` or `1280`, or a bigger model: `--model yolo26m.pt` |
| Hens detected as cats or dogs | `--classes bird,cat,dog` |
| Door camera looks across the door, not down | `--anchor bottom` (her feet cross the line, not the middle of her) |
| Counts in-out-in-out for a hen hovering in the doorway | A larger `--margin`, e.g. `0.04` |
| Tracks break up | `--tracker botsort.yaml`; keep `--vid-stride` at 1 |
| Too slow | `--model yolo26n.pt`, `--no-video` |

## Live from a camera

You can also point it at a live stream, e.g. to watch bedtime as it
happens. In Protect, turn on an RTSP stream for the camera (camera
Settings → Advanced → RTSP). Protect shows an `rtsps://…:7441/…` address;
the same stream without encryption is usually at `rtsp://<protect-ip>:7447/<same-id>`,
which is the form this script needs:

```bash
~/chicken-test/bin/python chicken_vision_test.py run rtsp://192.168.1.10:7447/AbCdEf123 --max-seconds 900 --line ... --inside ... --device intel:gpu
```

Ultralytics is AGPL-licensed, which is fine for home use like this.
