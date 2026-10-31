#!/usr/bin/env python3
"""Pull training frames for the hen model out of Frigate.

Two sources:
  recordings  frames sampled through each day from Frigate's recordings,
              more often in the busy windows (let-out and bedtime, when
              light is changing and hens crowd the door), so dusk and night
              vision are well covered. Empty-run frames are kept too: the
              model has to learn what "no hens" looks like.
  events      the snapshot of each bird/person/cat/dog detection Frigate
              made, which are the frames with something happening.

Near-identical frames (an empty run that hasn't changed in an hour) are
skipped, so labelling time goes on frames that teach the model something.
Re-running only adds frames it doesn't have yet.

Writes into the shared folder:
  images/<camera>/<camera>_<YYYYmmdd-HHMMSS>_<source>.jpg
  manifest.csv   one row per frame: file, camera, time, source, label, score

Run (on the training machine, with the shared folder mounted):
  python3 hen_model/harvest.py --frigate http://truenas:8971 --user hens \
      --out /mnt/hens --days 3

See docs/hen-model.md.
"""

import argparse
import csv
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Frigate  # noqa: E402

CAMERAS = ["chicken_cam_1", "chicken_cam_2", "chicken_run"]
EVENT_LABELS = "bird,person,cat,dog"
HEIGHT = 720  # same as the Medium stream Frigate detects on
MANIFEST_FIELDS = ["file", "camera", "time", "source", "label", "score"]


# ---------------------------------------------------------------------------
# Picking frames
# ---------------------------------------------------------------------------

def parse_windows(text):
    """'06:00-09:00,16:00-20:00' -> [(360, 540), (960, 1200)] in minutes."""
    windows = []
    for part in filter(None, (p.strip() for p in text.split(","))):
        try:
            a, b = part.split("-")
            ah, am = map(int, a.split(":"))
            bh, bm = map(int, b.split(":"))
        except ValueError:
            sys.exit(f"--busy: can't read {part!r}; use HH:MM-HH:MM,HH:MM-HH:MM")
        windows.append((ah * 60 + am, bh * 60 + bm))
    return windows


def sample_times(start, end, every, busy, busy_every):
    """Local times from start to end: every `every` minutes, and every
    `busy_every` minutes inside the busy windows."""
    t = start.replace(second=0, microsecond=0)
    while t < end:
        minute = t.hour * 60 + t.minute
        in_busy = any(a <= minute < b for a, b in busy)
        step = busy_every if in_busy else every
        if minute % step == 0:
            yield t
        t += timedelta(minutes=1)


def covered(times, segments):
    """The times that fall inside a recording segment (sorted lists)."""
    out, i = [], 0
    for t in times:
        ts = t.timestamp()
        while i < len(segments) and segments[i]["end_time"] < ts:
            i += 1
        if i < len(segments) and segments[i]["start_time"] <= ts:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Skipping near-duplicates
# ---------------------------------------------------------------------------

def dhash(img):
    """64-bit difference hash: changes little for the same scene, a lot when
    something moves in or the light changes."""
    small = np.asarray(img.convert("L").resize((9, 8), Image.BILINEAR), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


class Deduper:
    def __init__(self, distance):
        self.distance = distance
        self.seen = {}  # camera -> hashes of frames kept

    def load(self, path, camera):
        try:
            with Image.open(path) as img:
                self.seen.setdefault(camera, []).append(dhash(img))
        except OSError:
            pass

    def is_new(self, img, camera):
        h = dhash(img)
        kept = self.seen.setdefault(camera, [])
        if any(bin(h ^ k).count("1") <= self.distance for k in kept):
            return False
        kept.append(h)
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--frigate", required=True, help="Frigate's address, e.g. http://truenas:8971")
    p.add_argument("--user", default=os.environ.get("FRIGATE_USER"),
                   help="Frigate login (or FRIGATE_USER); not needed on port 5000")
    p.add_argument("--password", default=os.environ.get("FRIGATE_PASSWORD"),
                   help="or set FRIGATE_PASSWORD, or you'll be asked")
    p.add_argument("--out", required=True, help="the shared hen-model folder")
    p.add_argument("--days", type=float, default=3, help="how far back to go (default 3: Frigate keeps 3 days of continuous recording)")
    p.add_argument("--cameras", default=",".join(CAMERAS), help=f"comma-separated (default {','.join(CAMERAS)})")
    p.add_argument("--every", type=int, default=30, help="minutes between frames outside the busy windows (default 30)")
    p.add_argument("--busy", default="06:00-09:00,16:00-20:00",
                   help="local let-out and bedtime windows, sampled more often (default 06:00-09:00,16:00-20:00)")
    p.add_argument("--busy-every", type=int, default=5, help="minutes between frames in the busy windows (default 5)")
    p.add_argument("--no-events", action="store_true", help="skip Frigate's detection snapshots")
    p.add_argument("--no-recordings", action="store_true", help="skip frames sampled from recordings")
    p.add_argument("--distance", type=int, default=5,
                   help="frames closer than this to one already kept are skipped (0-64, default 5; 0 keeps everything)")
    args = p.parse_args()

    if args.user and not args.password:
        import getpass
        args.password = getpass.getpass(f"Frigate password for {args.user}: ")

    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.csv"
    have = set()
    if manifest_path.exists():
        with open(manifest_path, newline="") as f:
            have = {row["file"] for row in csv.DictReader(f)}

    frigate = Frigate(args.frigate, args.user, args.password)
    cameras = [c.strip() for c in args.cameras.split(",") if c.strip()]
    busy = parse_windows(args.busy)
    end = datetime.now()
    start = end - timedelta(days=args.days)

    dedupe = Deduper(args.distance)
    for rel in have:  # so a re-run doesn't add near-copies of what's there
        dedupe.load(out / rel, Path(rel).parent.name)

    new_rows, skipped = [], 0
    # Written as it goes, so an interrupted run keeps what it fetched.
    write_header = not manifest_path.exists()
    manifest = open(manifest_path, "a", newline="")
    rows = csv.DictWriter(manifest, fieldnames=MANIFEST_FIELDS)
    if write_header:
        rows.writeheader()

    def save(img, camera, when, source, label="", score=""):
        nonlocal skipped
        rel = f"images/{camera}/{camera}_{when:%Y%m%d-%H%M%S}_{source}.jpg"
        if rel in have:
            return
        if not dedupe.is_new(img, camera):
            skipped += 1
            return
        (out / "images" / camera).mkdir(exist_ok=True)
        img.convert("RGB").save(out / rel, quality=92)
        have.add(rel)
        row = {"file": rel, "camera": camera, "time": when.isoformat(timespec="seconds"),
               "source": source, "label": label, "score": score}
        rows.writerow(row)
        manifest.flush()
        new_rows.append(row)

    for camera in cameras:
        print(f"\n{camera}")
        if not args.no_recordings:
            segments = frigate.get(f"{camera}/recordings", after=start.timestamp(),
                                   before=end.timestamp()).json()
            times = covered(list(sample_times(start, end, args.every, busy, args.busy_every)), segments)
            print(f"  recordings: {len(segments)} segments, {len(times)} frames to fetch")
            for i, t in enumerate(times):
                try:
                    r = frigate.get(f"{camera}/recordings/{t.timestamp():.0f}/snapshot.jpg", height=HEIGHT)
                except Exception as e:  # a gap in the recording, or the camera was offline
                    print(f"    {t:%m-%d %H:%M} skipped: {e}")
                    continue
                save(Image.open(io.BytesIO(r.content)), camera, t, "rec")
                if i % 25 == 24:
                    print(f"    {i + 1}/{len(times)}")
        if not args.no_events:
            events, offset = [], 0
            while True:
                page = frigate.get("events", cameras=camera, labels=EVENT_LABELS, has_snapshot=1,
                                   after=start.timestamp(), before=end.timestamp(),
                                   limit=100, offset=offset).json()
                events += page
                if len(page) < 100:
                    break
                offset += 100
            print(f"  events: {len(events)} with snapshots")
            for e in events:
                try:
                    r = frigate.get(f"events/{e['id']}/snapshot-clean.webp")
                except Exception as err:
                    print(f"    event {e['id']} skipped: {err}")
                    continue
                when = datetime.fromtimestamp(e["start_time"])
                score = (e.get("data") or {}).get("top_score") or e.get("top_score") or ""
                save(Image.open(io.BytesIO(r.content)), camera, when, "event",
                     e.get("label", ""), f"{score:.2f}" if score else "")

    manifest.close()
    print(f"\nAdded {len(new_rows)} frames ({skipped} near-duplicates skipped); "
          f"{len(have)} in {out / 'images'}.")
    print(f"Next: python3 hen_model/prelabel.py --data {out} ...")


if __name__ == "__main__":
    main()
