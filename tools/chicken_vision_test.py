#!/usr/bin/env python3
"""Feasibility test for counting the hens with computer vision.

Runs a stock YOLO model over clips exported from UniFi Protect (or a live
RTSP stream) and reports how well it sees the hens: how many it counts in
each frame, how steady the tracking is, and, for the door camera, how many
times hens crossed a line you draw across the pop door in each direction.
Nothing here touches Home Assistant; it answers "is this worth building?"
before anything is installed for real. See docs/chicken-vision-test.md.

Two commands:
  frame   save one frame with a 10% grid, to read off the door line's
          coordinates (and check a line you've picked)
  run     detect, track and count; writes an annotated video, a CSV per
          clip and a summary across clips

Coordinates are fractions of the frame (0 to 1, from the top left), so they
work at any resolution.

Run:
  python3 tools/chicken_vision_test.py frame door.mp4
  python3 tools/chicken_vision_test.py run run1.mp4 run2.mp4
  python3 tools/chicken_vision_test.py run door.mp4 --line 0.40,0.55,0.62,0.55 --inside 0.5,0.3
  python3 tools/chicken_vision_test.py run door.mp4 --line ... --inside ... --device intel:gpu

Needs:  pip install ultralytics   (plus openvino for --device intel:...)
"""

import argparse
import csv
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import cv2

# COCO has no "chicken": hens usually come out as "bird", sometimes as a cat
# or dog. Add those with --classes bird,cat,dog to see how often it happens.
DEFAULT_CLASSES = "bird"
DEFAULT_MODEL = "yolo26s.pt"

# A hen has to get this far past the line (fraction of the frame diagonal)
# before she counts as on the other side, so a hen standing on the line or a
# jittery box doesn't count in-out-in-out.
DEFAULT_MARGIN = 0.02


# ---------------------------------------------------------------------------
# Door line
# ---------------------------------------------------------------------------

class DoorLine:
    """A line across the pop door, and which side of it is the coop."""

    def __init__(self, line, inside, margin, size):
        w, h = size
        self.a = (line[0] * w, line[1] * h)
        self.b = (line[2] * w, line[3] * h)
        self.length = ((self.b[0] - self.a[0]) ** 2 + (self.b[1] - self.a[1]) ** 2) ** 0.5
        if self.length == 0:
            sys.exit("--line: the two ends are the same point")
        self.margin = margin * (w * w + h * h) ** 0.5
        side = self._distance(inside[0] * w, inside[1] * h)
        if abs(side) < 1:
            sys.exit("--inside: that point is on the line; pick a point inside the coop")
        self.inside = 1 if side > 0 else -1

    def _distance(self, x, y):
        # Signed distance from the line; the sign says which side.
        (ax, ay), (bx, by) = self.a, self.b
        return ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) / self.length

    def _along(self, x, y):
        # How far along the segment the point is: 0 at one end, 1 at the other.
        (ax, ay), (bx, by) = self.a, self.b
        return ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / self.length ** 2

    def side(self, x, y):
        """+1 or -1 once clearly past the line near the door, else 0."""
        if not -0.25 <= self._along(x, y) <= 1.25:
            return 0  # off to the side of the door: not crossing it
        d = self._distance(x, y)
        if abs(d) < self.margin:
            return 0
        return 1 if d > 0 else -1


class CrossingCounter:
    """Counts each tracked hen's crossings of the door line."""

    def __init__(self, door):
        self.door = door
        self.last_side = {}  # track id -> last side she was clearly on
        self.ins = 0
        self.outs = 0
        self.events = []  # (seconds, track id, "in" / "out")

    def update(self, seconds, track_id, x, y):
        side = self.door.side(x, y)
        if side == 0:
            return None
        before = self.last_side.get(track_id)
        self.last_side[track_id] = side
        if before is None or before == side:
            return None
        way = "in" if side == self.door.inside else "out"
        if way == "in":
            self.ins += 1
        else:
            self.outs += 1
        self.events.append((seconds, track_id, way))
        return way


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def floats(text, n, name):
    try:
        values = [float(v) for v in text.split(",")]
    except ValueError:
        values = []
    if len(values) != n or not all(0 <= v <= 1 for v in values):
        sys.exit(f"{name}: expected {n} comma-separated numbers between 0 and 1, got {text!r}")
    return values


def is_stream(source):
    return "://" in source


def open_source(source):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        sys.exit(f"Can't open {source}")
    return cap


def clock(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def draw_grid(img):
    h, w = img.shape[:2]
    for i in range(1, 10):
        x, y = int(w * i / 10), int(h * i / 10)
        cv2.line(img, (x, 0), (x, h), (255, 255, 255), 1)
        cv2.line(img, (0, y), (w, y), (255, 255, 255), 1)
        for text, pos in ((f"{i / 10:.1f}", (x + 3, 16)), (f"{i / 10:.1f}", (3, y - 4))):
            cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
            cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)


def draw_door(img, door):
    a = tuple(int(v) for v in door.a)
    b = tuple(int(v) for v in door.b)
    cv2.line(img, a, b, (0, 200, 255), 3)
    # Arrow from the middle of the line towards the inside of the coop.
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    nx, ny = -(b[1] - a[1]) / door.length, (b[0] - a[0]) / door.length
    tip = (int(mx + nx * door.inside * 40), int(my + ny * door.inside * 40))
    cv2.arrowedLine(img, (int(mx), int(my)), tip, (0, 200, 255), 2, tipLength=0.35)
    cv2.putText(img, "in", (tip[0] + 4, tip[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)


def banner(img, text):
    cv2.rectangle(img, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(img, text, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def load_model(name, device):
    from ultralytics import YOLO

    model = YOLO(name)
    # OpenVINO (Intel Arc / iGPU / CPU) needs the model exported first; the
    # export sits next to the .pt and is reused on later runs.
    if device.startswith("intel") and name.endswith(".pt"):
        exported = Path(model.export(format="openvino", half=True, verbose=False))
        model = YOLO(str(exported), task="detect")
    return model


def class_ids(model, names):
    wanted = [n.strip() for n in names.split(",") if n.strip()]
    lookup = {v: k for k, v in model.names.items()}
    missing = [n for n in wanted if n not in lookup]
    if missing:
        sys.exit(f"--classes: the model doesn't know {', '.join(missing)}. "
                 f"It knows: {', '.join(model.names.values())}")
    return [lookup[n] for n in wanted]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_frame(args):
    cap = open_source(args.source)
    if args.at and not is_stream(args.source):
        cap.set(cv2.CAP_PROP_POS_MSEC, args.at * 1000)
    ok, img = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"Couldn't read a frame from {args.source}")
    draw_grid(img)
    if args.line:
        if not args.inside:
            sys.exit("--line needs --inside too")
        h, w = img.shape[:2]
        draw_door(img, DoorLine(floats(args.line, 4, "--line"), floats(args.inside, 2, "--inside"),
                                DEFAULT_MARGIN, (w, h)))
    out = Path(args.out) if args.out else Path(Path(args.source).stem + "_grid.jpg")
    cv2.imwrite(str(out), img)
    print(f"Saved {out} ({img.shape[1]}x{img.shape[0]}). Read the door line's ends off the grid,")
    print("plus one point inside the coop, and pass them as --line x1,y1,x2,y2 --inside x,y.")


def run_clip(model, classes, source, args, out_dir):
    cap = open_source(source)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    step = args.vid_stride / fps  # seconds between processed frames

    counter = None
    if args.line:
        if not args.inside:
            sys.exit("--line needs --inside too")
        door = DoorLine(floats(args.line, 4, "--line"), floats(args.inside, 2, "--inside"),
                        args.margin, (w, h))
        counter = CrossingCounter(door)

    stem = "rtsp" if is_stream(source) else Path(source).stem
    writer = None
    if not args.no_video:
        video_path = out_dir / f"{stem}_annotated.mp4"
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps / args.vid_stride, (w, h))
    csv_path = out_dir / f"{stem}_frames.csv"

    counts, per_class, track_ids, infer_ms = [], Counter(), set(), []
    started = time.time()
    print(f"\n{source}: {w}x{h} at {fps:.0f} fps, every {args.vid_stride} frame(s)")

    with open(csv_path, "w", newline="") as f:
        rows = csv.writer(f)
        rows.writerow(["frame", "seconds", "count", "track_ids", "classes", "confidences", "crossing"])
        results = model.track(source=source, stream=True, persist=False, tracker=args.tracker,
                              classes=classes, conf=args.conf, imgsz=args.imgsz,
                              device=args.device, vid_stride=args.vid_stride, verbose=False)
        for i, r in enumerate(results):
            seconds = i * step
            if args.max_seconds and seconds > args.max_seconds:
                break
            boxes = r.boxes
            ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(boxes)
            names = [r.names[c] for c in boxes.cls.int().tolist()]
            confs = [round(c, 2) for c in boxes.conf.tolist()]
            counts.append(len(boxes))
            per_class.update(names)
            track_ids.update(t for t in ids if t is not None)
            infer_ms.append(r.speed["inference"])

            crossed = []
            if counter:
                for t, (x1, y1, x2, y2) in zip(ids, boxes.xyxy.tolist()):
                    if t is None:
                        continue
                    y = y2 if args.anchor == "bottom" else (y1 + y2) / 2
                    way = counter.update(seconds, t, (x1 + x2) / 2, y)
                    if way:
                        crossed.append(f"{t}:{way}")
                        print(f"  {clock(seconds)}  hen #{t} went {way.upper()}")

            rows.writerow([i * args.vid_stride, round(seconds, 2), len(boxes),
                           " ".join(str(t) for t in ids), " ".join(names),
                           " ".join(str(c) for c in confs), " ".join(crossed)])

            if writer:
                img = r.plot(line_width=2, font_size=12)
                text = f"{clock(seconds)}   seen: {len(boxes)}"
                if counter:
                    draw_door(img, counter.door)
                    text += f"   in: {counter.ins}   out: {counter.outs}"
                banner(img, text)
                writer.write(img)

    if writer:
        writer.release()
    if not counts:
        sys.exit(f"No frames read from {source}")

    elapsed = time.time() - started
    seen = [c for c in counts if c]
    summary = {
        "clip": stem,
        "seconds": round(len(counts) * step, 1),
        "frames": len(counts),
        "frames_with_hens_pct": round(100 * len(seen) / len(counts), 1),
        "max_seen": max(counts),
        "median_seen": statistics.median(counts),
        "median_seen_when_any": statistics.median(seen) if seen else 0,
        "distinct_track_ids": len(track_ids),
        "classes": " ".join(f"{k}={v}" for k, v in per_class.most_common()),
        "inference_ms": round(statistics.mean(infer_ms), 1),
        "processing_fps": round(len(counts) / elapsed, 1),
        "in": counter.ins if counter else "",
        "out": counter.outs if counter else "",
        "net_in": counter.ins - counter.outs if counter else "",
    }

    print(f"  frames with a hen seen  {summary['frames_with_hens_pct']}%")
    print(f"  hens seen               max {summary['max_seen']}, median {summary['median_seen']}"
          f" (median {summary['median_seen_when_any']} when any are in view)")
    print("  how often each count    " + ", ".join(f"{k}: {v}" for k, v in sorted(Counter(counts).items())))
    print(f"  detections by class     {summary['classes'] or 'none'}")
    print(f"  distinct track ids      {summary['distinct_track_ids']}"
          "  (far more than the hens that appeared = tracks breaking up)")
    if counter:
        print(f"  door crossings          in {counter.ins}, out {counter.outs}, net {summary['net_in']:+d}")
    print(f"  speed                   {summary['inference_ms']} ms per frame to detect,"
          f" {summary['processing_fps']} frames/s overall on {args.device}")
    if writer:
        print(f"  annotated video         {video_path}")
    print(f"  per-frame CSV           {csv_path}")
    return summary


def cmd_run(args):
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(is_stream(s) for s in args.sources) and not args.max_seconds:
        sys.exit("A live stream never ends: add --max-seconds")
    model = load_model(args.model, args.device)
    classes = class_ids(model, args.classes)

    summaries = [run_clip(model, classes, s, args, out_dir) for s in args.sources]

    path = out_dir / "summary.csv"
    with open(path, "w", newline="") as f:
        rows = csv.DictWriter(f, fieldnames=list(summaries[0]))
        rows.writeheader()
        rows.writerows(summaries)
    print(f"\nSummary of all clips: {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    f = sub.add_parser("frame", help="save a frame with a grid, to pick the door line")
    f.add_argument("source", help="clip file or rtsp:// URL")
    f.add_argument("--at", type=float, default=0, help="seconds into the clip (default 0)")
    f.add_argument("--line", help="x1,y1,x2,y2: draw this door line to check it")
    f.add_argument("--inside", help="x,y: a point inside the coop")
    f.add_argument("--out", help="image to write (default <clip>_grid.jpg)")
    f.set_defaults(func=cmd_frame)

    r = sub.add_parser("run", help="detect, track and count hens")
    r.add_argument("sources", nargs="+", help="clip files and/or rtsp:// URLs")
    r.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"YOLO weights (default {DEFAULT_MODEL}; n is faster, m/l see small birds better)")
    r.add_argument("--device", default="cpu",
                   help="cpu (default), intel:gpu for the Arc, intel:cpu for OpenVINO on the CPU, or 0 for CUDA")
    r.add_argument("--classes", default=DEFAULT_CLASSES,
                   help=f"what counts as a hen, comma-separated (default {DEFAULT_CLASSES})")
    r.add_argument("--conf", type=float, default=0.25, help="minimum confidence (default 0.25)")
    r.add_argument("--imgsz", type=int, default=640,
                   help="model input size (default 640; 960 or 1280 helps small, distant hens)")
    r.add_argument("--tracker", default="bytetrack.yaml", help="bytetrack.yaml (default) or botsort.yaml")
    r.add_argument("--vid-stride", type=int, default=1,
                   help="process every Nth frame (default 1; keep it 1 or 2 for door counting)")
    r.add_argument("--line", help="x1,y1,x2,y2: line across the pop door, as fractions of the frame")
    r.add_argument("--inside", help="x,y: any point on the coop side of the line")
    r.add_argument("--margin", type=float, default=DEFAULT_MARGIN,
                   help=f"how far past the line counts as crossed, fraction of the diagonal (default {DEFAULT_MARGIN})")
    r.add_argument("--anchor", choices=["center", "bottom"], default="center",
                   help="point of the box that crosses the line: center (default, cameras looking down) "
                        "or bottom (feet, cameras looking across)")
    r.add_argument("--max-seconds", type=float, help="stop after this much video (needed for live streams)")
    r.add_argument("--no-video", action="store_true", help="skip the annotated video (faster)")
    r.add_argument("--out", default="chicken_test", help="output folder (default chicken_test)")
    r.set_defaults(func=cmd_run)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
