#!/usr/bin/env python3
"""Download public photos of predators, already boxed, from Open Images.

Foxes, raccoons, skunks and raptors rarely walk past our cameras, so there
is little of our own footage to learn them from. Open Images (Google's
public photo set, about 1.7 million images boxed by people) has thousands
of each. classes.yaml says which Open Images classes stand for each of ours
(Eagle, Falcon and Owl all count as raptor).

For each class it picks up to --per-class photos that contain it, skipping
drawings, toys and boxes drawn round a whole group, and downloads them with
labels for every one of our classes in the photo (a photo of a dog with a
person gets both boxes). They go straight into training: no Label Studio
pass needed. Re-running tops up to --per-class without downloading twice.

The first run reads Open Images' box lists: 2.3 GB for the training set,
read once and never saved whole; the rows we need are cached in
<data>/public/cache, so later runs start straight away.

Writes into the shared folder:
  public/images/oi_<id>.jpg     long side at most 1280 px
  public/labels/oi_<id>.txt     class x y w h (0-1), our class numbers
  public/manifest.csv           file, Open Images split and id, classes

Open Images photos are CC BY 2.0 (attribution: the Open Images metadata,
by image id), fine for training a model at home.

Run (on any machine with the shared folder mounted):
  python3 hen_model/public.py --data /mnt/hens

See docs/hen-model.md.
"""

import argparse
import csv
import io
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_classes  # noqa: E402

CLASS_LIST = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"
BOX_LISTS = {
    "train": "https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv",
    "validation": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
    "test": "https://storage.googleapis.com/openimages/v5/test-annotations-bbox.csv",
}
IMAGE_URL = "https://open-images-dataset.s3.amazonaws.com/{split}/{image_id}.jpg"
MAX_SIDE = 1280
SKIP_BY_DEFAULT = {"hen", "person"}  # plenty of our own footage of both
BOX_FIELDS = ["ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax", "IsGroupOf", "IsDepiction"]


def open_images_ids(names):
    """Open Images display name -> its id (e.g. Fox -> /m/0306r)."""
    r = requests.get(CLASS_LIST, timeout=60)
    r.raise_for_status()
    ids = {}
    for row in csv.reader(io.StringIO(r.text)):
        if len(row) == 2 and row[1] in names:
            ids[row[1]] = row[0]
    missing = set(names) - set(ids)
    if missing:
        sys.exit(f"classes.yaml: not Open Images box classes: {', '.join(sorted(missing))}")
    return ids


def keep_image(rows, wanted):
    """True if the photo has a wanted class, and none of our classes is a
    drawing/toy or a box round a group."""
    return (any(r["LabelName"] in wanted for r in rows)
            and not any(r["IsGroupOf"] == "1" or r["IsDepiction"] == "1" for r in rows))


def cached_boxes(split, ours, wanted, cache_dir):
    """Box rows for our classes, for photos with a wanted class: read from
    the cache, or filtered out of Open Images' list on the first run.

    The lists are sorted by image, so each photo's rows arrive together and
    the 2.3 GB training list streams through without being stored."""
    cache = cache_dir / f"{split}-boxes.csv"
    key = cache_dir / f"{split}-boxes.classes"
    if cache.exists() and key.exists() and set(key.read_text().split()) == set(ours):
        with open(cache, newline="") as f:
            return list(csv.DictReader(f))

    print(f"  reading Open Images' {split} box list (first time only)...", flush=True)
    kept, current, image = [], [], None
    with requests.get(BOX_LISTS[split], stream=True, timeout=60) as r:
        r.raise_for_status()
        lines = (line.decode() for line in r.iter_lines())
        for i, row in enumerate(csv.DictReader(lines)):
            if row["ImageID"] != image:
                if current and keep_image(current, wanted):
                    kept += current
                current, image = [], row["ImageID"]
            if row["LabelName"] in ours:
                current.append({k: row[k] for k in BOX_FIELDS})
            if i % 2_000_000 == 1_999_999:
                print(f"    {i + 1:,} boxes read, {len({k['ImageID'] for k in kept}):,} photos kept", flush=True)
        if current and keep_image(current, wanted):
            kept += current

    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=BOX_FIELDS)
        w.writeheader()
        w.writerows(kept)
    key.write_text(" ".join(sorted(ours)))
    return kept


def yolo_lines(rows, class_of):
    lines = []
    for r in rows:
        x1, x2, y1, y2 = (float(r[k]) for k in ("XMin", "XMax", "YMin", "YMax"))
        lines.append(f"{class_of[r['LabelName']]} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}")
    return lines


def download(split, image_id, dest):
    r = requests.get(IMAGE_URL.format(split=split, image_id=image_id), timeout=60)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # boxes are 0-1, so they still fit
    img.save(dest, quality=92)


def main():
    classes = load_classes()
    default = [c["name"] for c in classes if c.get("open_images") and c["name"] not in SKIP_BY_DEFAULT]

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--data", required=True, help="the shared hen-model folder")
    p.add_argument("--classes", default=",".join(default),
                   help=f"which of our classes to fetch photos of (default {','.join(default)})")
    p.add_argument("--per-class", type=int, default=200,
                   help="photos per class (default 200; more drowns out our own footage)")
    p.add_argument("--splits", default="train,validation,test",
                   help="Open Images parts to draw from (default all; 'validation' alone is small, for a quick try)")
    p.add_argument("--workers", type=int, default=8, help="downloads at once (default 8)")
    p.add_argument("--sheets", action="store_true",
                   help="also write contact sheets per class to public/review, for checking the photos")
    args = p.parse_args()

    by_name = {c["name"]: c for c in classes}
    chosen = [n.strip() for n in args.classes.split(",") if n.strip()]
    for n in chosen:
        if n not in by_name or not by_name[n].get("open_images"):
            sys.exit(f"--classes: {n!r} has no open_images entry in classes.yaml")

    # Every Open Images class that maps to one of ours gets boxed; only the
    # chosen ones decide which photos are fetched.
    oi_names = {o: i for i, c in enumerate(classes) for o in c.get("open_images", [])}
    ids = open_images_ids(set(oi_names))
    class_of = {ids[o]: i for o, i in oi_names.items()}
    wanted = {ids[o] for n in chosen for o in by_name[n]["open_images"]}

    out = Path(args.data) / "public"
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)

    # Open Images has label mistakes (a black-and-white cat called a skunk).
    # Deleting a bad photo rejects it for good: it's noted here and never
    # downloaded again, and the next run tops its class back up.
    rejected_path = out / "rejected.txt"
    rejected = set(rejected_path.read_text().split()) if rejected_path.exists() else set()
    if (out / "manifest.csv").exists():
        with open(out / "manifest.csv", newline="") as f:
            for row in csv.DictReader(f):
                if not (Path(args.data) / row["file"]).exists():
                    rejected.add(row["image_id"])
                    (out / "labels" / f"oi_{row['image_id']}.txt").unlink(missing_ok=True)
    rejected_path.write_text("".join(i + "\n" for i in sorted(rejected)))

    photos = {}  # (split, image id) -> box rows
    for split in [s.strip() for s in args.splits.split(",") if s.strip()]:
        if split not in BOX_LISTS:
            sys.exit(f"--splits: {split!r} isn't one of {', '.join(BOX_LISTS)}")
        grouped = defaultdict(list)
        for row in cached_boxes(split, set(class_of), wanted, out / "cache"):
            grouped[row["ImageID"]].append(row)
        photos.update({(split, k): v for k, v in grouped.items() if k not in rejected})
    print(f"{len(photos):,} suitable photos in Open Images"
          + (f" ({len(rejected)} rejected by you)" if rejected else ""))

    # Photos already downloaded count first; then a fixed shuffle, so
    # re-runs pick the same photos.
    have = {p.stem.removeprefix("oi_") for p in (out / "images").glob("oi_*.jpg")}
    order = sorted(photos, key=lambda k: (k[1] not in have, random.Random(k[1]).random()))
    counts, picked = Counter(), []
    for key in order:
        names = {classes[class_of[r["LabelName"]]]["name"] for r in photos[key]} & set(chosen)
        if any(counts[n] < args.per_class for n in names):
            picked.append(key)
            counts.update(names)

    todo = [k for k in picked if k[1] not in have]
    print(f"Using {len(picked)} photos ({len(todo)} to download): "
          + ", ".join(f"{n} {counts[n]}" for n in chosen))

    def fetch(key):
        split, image_id = key
        try:
            download(split, image_id, out / "images" / f"oi_{image_id}.jpg")
        except Exception as e:
            return key, e
        (out / "labels" / f"oi_{image_id}.txt").write_text(
            "".join(line + "\n" for line in yolo_lines(photos[key], class_of)))
        return key, None

    failed = 0
    with ThreadPoolExecutor(args.workers) as pool:
        for i, (key, err) in enumerate(pool.map(fetch, todo)):
            if err:
                failed += 1
                print(f"  {key[1]} skipped: {err}")
            if i % 100 == 99:
                print(f"  {i + 1}/{len(todo)}", flush=True)

    with open(out / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "split", "image_id", "classes"])
        for split, image_id in picked:
            if (out / "images" / f"oi_{image_id}.jpg").exists():
                names = sorted({classes[class_of[r["LabelName"]]]["name"] for r in photos[(split, image_id)]})
                w.writerow([f"public/images/oi_{image_id}.jpg", split, image_id, " ".join(names)])

    if args.sheets:
        sheets(out, picked, photos, class_of, classes, chosen)

    print(f"Done{f' ({failed} failed, re-run to retry)' if failed else ''}: {out}")
    print("dataset.py adds these to the training set automatically.")


def sheets(out, picked, photos, class_of, classes, chosen, per_sheet=12):
    """Contact sheets per class, boxes drawn, each photo captioned with its
    file name, for a quick look through. Delete bad photos from
    public/images and re-run."""
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=18)
    except TypeError:  # Pillow older than 10.1
        font = ImageFont.load_default()
    review = out / "review"
    if review.exists():
        for old in review.glob("*.jpg"):
            old.unlink()
    review.mkdir(exist_ok=True)
    tile_w, tile_h = 400, 300
    for name in chosen:
        keys = [k for k in picked if (out / "images" / f"oi_{k[1]}.jpg").exists()
                and name in {classes[class_of[r["LabelName"]]]["name"] for r in photos[k]}]
        for n, start in enumerate(range(0, len(keys), per_sheet)):
            sheet = Image.new("RGB", (4 * tile_w, 3 * tile_h), "white")
            for j, (split, image_id) in enumerate(keys[start:start + per_sheet]):
                img = Image.open(out / "images" / f"oi_{image_id}.jpg").convert("RGB")
                w, h = img.size
                draw = ImageDraw.Draw(img)
                for r in photos[(split, image_id)]:
                    box = [float(r["XMin"]) * w, float(r["YMin"]) * h, float(r["XMax"]) * w, float(r["YMax"]) * h]
                    draw.rectangle(box, outline="red", width=max(3, w // 200))
                img.thumbnail((tile_w, tile_h - 24))
                x, y = (j % 4) * tile_w, (j // 4) * tile_h
                sheet.paste(img, (x, y + 24))
                ImageDraw.Draw(sheet).text((x + 4, y + 2), f"oi_{image_id}", fill="black", font=font)
            sheet.save(review / f"{name}-{n + 1}.jpg", quality=85)
    print(f"Contact sheets: {review}")


if __name__ == "__main__":
    main()
