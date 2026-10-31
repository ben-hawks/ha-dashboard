#!/usr/bin/env python3
"""Turn the frames labelled in Label Studio into a YOLO training set.

Takes every frame with a submitted labelling (skipped frames are left out; a
frame submitted with no boxes is kept as an example of "nothing here") and
writes the dataset that train.py uses:

  <out>/images/{train,val}/*.jpg
  <out>/labels/{train,val}/*.txt   one line per box: class x y w h (0-1)
  <out>/data.yaml                  class names and folders

The validation share is picked by camera and hour, not frame by frame:
frames a few minutes apart look nearly the same, and splitting them up
would let the model "recognise" its own training frames and look better
than it is. The same hour always lands on the same side, so re-runs after
more labelling keep the split stable.

The dataset is rebuilt from scratch each run.

Run (on the training machine):
  python3 hen_model/dataset.py --data /mnt/hens --ls http://truenas:8085 --token <token>
or from a Label Studio export (Export > JSON):
  python3 hen_model/dataset.py --data /mnt/hens --export project-1.json

See docs/hen-model.md.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LabelStudio, load_classes, rel_from_url  # noqa: E402

HOUR = re.compile(r"_(\d{8}-\d{2})")


def latest_annotation(task):
    """The most recent submitted labelling of a task, or None if it was only
    skipped (or never labelled)."""
    done = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    return max(done, key=lambda a: a.get("updated_at") or a.get("created_at") or "", default=None)


def yolo_lines(annotation, class_index):
    lines, unknown = [], set()
    for r in annotation.get("result", []):
        if r.get("type") != "rectanglelabels":
            continue
        v = r["value"]
        name = v["rectanglelabels"][0]
        if name not in class_index:
            unknown.add(name)
            continue
        x, y, w, h = (max(0.0, min(100.0, v[k])) / 100 for k in ("x", "y", "width", "height"))
        w, h = min(w, 1 - x), min(h, 1 - y)
        if w <= 0 or h <= 0:
            continue
        lines.append(f"{class_index[name]} {x + w / 2:.6f} {y + h / 2:.6f} {w:.6f} {h:.6f}")
    return lines, unknown


def split_for(rel, val_share):
    """'val' or 'train', the same for every frame from one camera-hour."""
    name = Path(rel).name
    m = HOUR.search(name)
    group = f"{Path(rel).parent.name}/{m.group(1)}" if m else name
    bucket = int(hashlib.md5(group.encode()).hexdigest(), 16) % 1000
    return "val" if bucket < val_share * 1000 else "train"


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--data", required=True, help="the shared hen-model folder")
    p.add_argument("--ls", help="Label Studio's address, e.g. http://truenas:8085")
    p.add_argument("--token", default=os.environ.get("LABEL_STUDIO_TOKEN"),
                   help="Label Studio access token (or LABEL_STUDIO_TOKEN)")
    p.add_argument("--project", default="Hen model", help="Label Studio project (default 'Hen model')")
    p.add_argument("--export", help="a Label Studio JSON export, instead of --ls")
    p.add_argument("--out", help="where to write the dataset (default <data>/dataset)")
    p.add_argument("--val-share", type=float, default=0.2, help="share of camera-hours kept for validation (default 0.2)")
    args = p.parse_args()

    data = Path(args.data)
    out = Path(args.out) if args.out else data / "dataset"
    classes = load_classes()
    class_index = {c["name"]: i for i, c in enumerate(classes)}

    if args.export:
        tasks = json.loads(Path(args.export).read_text())
    elif args.ls:
        if not args.token:
            sys.exit("--ls needs --token (or LABEL_STUDIO_TOKEN)")
        ls = LabelStudio(args.ls, args.token)
        project = ls.project(args.project, classes, create=False)
        tasks = ls.request("GET", f"projects/{project}/export", params={"exportType": "JSON"})
    else:
        sys.exit("Give --ls (and --token) or --export")

    for sub in ("images", "labels"):
        shutil.rmtree(out / sub, ignore_errors=True)
        for split in ("train", "val"):
            (out / sub / split).mkdir(parents=True)

    images, empty, boxes, missing, unknown = Counter(), Counter(), {"train": Counter(), "val": Counter()}, [], set()
    for task in tasks:
        annotation = latest_annotation(task)
        if annotation is None:
            continue
        rel = rel_from_url(task["data"]["image"])
        src = data / rel
        if not src.exists():
            missing.append(rel)
            continue
        lines, bad = yolo_lines(annotation, class_index)
        unknown |= bad
        split = split_for(rel, args.val_share)
        stem = Path(rel).stem
        shutil.copy2(src, out / "images" / split / f"{stem}{src.suffix}")
        (out / "labels" / split / f"{stem}.txt").write_text("".join(line + "\n" for line in lines))
        images[split] += 1
        if not lines:
            empty[split] += 1
        boxes[split].update(classes[int(line.split()[0])]["name"] for line in lines)

    (out / "data.yaml").write_text(yaml.safe_dump({
        "path": str(out.resolve()), "train": "images/train", "val": "images/val",
        "names": {i: c["name"] for i, c in enumerate(classes)},
    }, sort_keys=False))

    print(f"Dataset in {out}")
    for split in ("train", "val"):
        counts = ", ".join(f"{c['name']} {boxes[split][c['name']]}" for c in classes if boxes[split][c["name"]])
        print(f"  {split:5}  {images[split]} frames ({empty[split]} with nothing in them); boxes: {counts or 'none'}")
    thin = [c["name"] for c in classes if boxes["train"][c["name"]] and not boxes["val"][c["name"]]]
    if thin:
        print(f"  No validation boxes yet for: {', '.join(thin)} (its scores won't mean much until there are)")
    if unknown:
        print(f"  Ignored boxes with labels not in classes.yaml: {', '.join(sorted(unknown))}")
    if missing:
        print(f"  {len(missing)} labelled frames are missing from {data} (e.g. {missing[0]})")
    if not images["train"]:
        sys.exit("No labelled frames yet: label some in Label Studio first.")
    print(f"Next: python3 hen_model/train.py --dataset {out}")


if __name__ == "__main__":
    main()
