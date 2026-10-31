#!/usr/bin/env python3
"""Draw first-guess boxes on harvested frames and send them to Label Studio.

YOLOE, a model you can ask for things by name, looks for each class using
the prompts in classes.yaml ("chicken", "hen", "fox", ...). Its boxes arrive
in Label Studio as pre-annotations, so labelling a frame means fixing a few
boxes rather than drawing every hen. It will miss some, mislabel some and box
wild birds as hens; that's what the labelling pass is for.

Only frames that haven't been sent before are processed (the list is kept in
<data>/labelstudio/prelabelled.txt), so run it again after each harvest.

Run (on the training machine):
  python3 hen_model/prelabel.py --data /mnt/hens \
      --ls http://truenas:8085 --token <Label Studio access token>
Without --ls it only writes the tasks file, for importing by hand.

See docs/hen-model.md.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LabelStudio, image_url, load_classes  # noqa: E402

DEFAULT_MODEL = "yoloe-26l-seg.pt"


def prompt_model(name, classes):
    from ultralytics import YOLOE

    model = YOLOE(name)
    prompts, owner = [], []  # each prompt, and the class it stands for
    for c in classes:
        for text in c["prompts"]:
            prompts.append(text)
            owner.append(c["name"])
    model.set_classes(prompts)
    return model, owner


def task_for(result, rel, owner, model_version):
    h, w = result.orig_shape
    boxes = []
    for (x1, y1, x2, y2), cls, conf in zip(result.boxes.xyxy.tolist(), result.boxes.cls.int().tolist(),
                                           result.boxes.conf.tolist()):
        boxes.append({
            "from_name": "label", "to_name": "image", "type": "rectanglelabels",
            "original_width": w, "original_height": h, "image_rotation": 0,
            "value": {"x": 100 * x1 / w, "y": 100 * y1 / h,
                      "width": 100 * (x2 - x1) / w, "height": 100 * (y2 - y1) / h,
                      "rotation": 0, "rectanglelabels": [owner[cls]]},
            "score": round(conf, 3),
        })
    score = round(min((b["score"] for b in boxes), default=1.0), 3)
    return {"data": {"image": image_url(rel)},
            "predictions": [{"model_version": model_version, "score": score, "result": boxes}]}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--data", required=True, help="the shared hen-model folder")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"YOLOE weights (default {DEFAULT_MODEL}; yoloe-26s-seg.pt is faster, less accurate)")
    p.add_argument("--device", default=None, help="0 for the first NVIDIA GPU, cpu, mps (Mac); default picks one")
    p.add_argument("--conf", type=float, default=0.2,
                   help="lowest confidence kept (default 0.2: deleting a wrong box is quicker than drawing a missed one)")
    p.add_argument("--imgsz", type=int, default=960, help="model input size (default 960, for small, distant hens)")
    p.add_argument("--ls", help="Label Studio's address, e.g. http://truenas:8085; omit to only write the tasks file")
    p.add_argument("--token", default=os.environ.get("LABEL_STUDIO_TOKEN"),
                   help="Label Studio access token (or LABEL_STUDIO_TOKEN): Account & Settings > Personal Access Token")
    p.add_argument("--project", default="Hen model", help="Label Studio project (default 'Hen model'; created if missing)")
    p.add_argument("--limit", type=int, help="only this many new frames (to try it out)")
    args = p.parse_args()

    data = Path(args.data)
    ls_dir = data / "labelstudio"
    ls_dir.mkdir(exist_ok=True)
    done_path = ls_dir / "prelabelled.txt"
    done = set(done_path.read_text().split()) if done_path.exists() else set()

    todo = sorted(p.relative_to(data).as_posix() for p in (data / "images").rglob("*.jpg"))
    todo = [r for r in todo if r not in done][: args.limit]
    if not todo:
        print("No new frames: run harvest.py first.")
        return
    if args.ls and not args.token:
        sys.exit("--ls needs --token (or LABEL_STUDIO_TOKEN)")

    classes = load_classes()
    model, owner = prompt_model(args.model, classes)
    version = f"{Path(args.model).stem}-{datetime.now():%Y%m%d}"
    print(f"Pre-labelling {len(todo)} frames with {args.model}, looking for: "
          + ", ".join(f"{c['name']} ({'/'.join(c['prompts'])})" for c in classes))

    tasks, counts = [], {}
    for i, rel in enumerate(todo):
        # One frame per call: handing Ultralytics the whole list makes memory
        # grow with every frame (about 80 MB each with YOLOE), until a night's
        # batch gets the container killed. Per frame it stays flat.
        result = model.predict(str(data / rel), conf=args.conf, imgsz=args.imgsz,
                               device=args.device, verbose=False)[0]
        task = task_for(result, rel, owner, version)
        tasks.append(task)
        for b in task["predictions"][0]["result"]:
            name = b["value"]["rectanglelabels"][0]
            counts[name] = counts.get(name, 0) + 1
        if i % 50 == 49:
            print(f"  {i + 1}/{len(todo)}")

    out = ls_dir / f"tasks-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(tasks))
    print(f"Boxes drawn: {', '.join(f'{k} {v}' for k, v in sorted(counts.items())) or 'none'}")
    print(f"Tasks file: {out}")

    if args.ls:
        ls = LabelStudio(args.ls, args.token)
        project = ls.project(args.project, classes)
        for start in range(0, len(tasks), 200):
            ls.request("POST", f"projects/{project}/import", json=tasks[start:start + 200])
        print(f"Sent {len(tasks)} frames to Label Studio: {args.ls.rstrip('/')}/projects/{project}")

    with open(done_path, "a") as f:
        f.write("".join(r + "\n" for r in todo))


if __name__ == "__main__":
    main()
