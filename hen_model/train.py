#!/usr/bin/env python3
"""Train the hen model and export it for Frigate.

Starts from a YOLO11 model that already knows everyday objects (it learns
hens much faster that way than from scratch), trains on the dataset from
dataset.py, then exports the best version as an ONNX file Frigate's
OpenVINO detector can run on the Arc, with its label file.

Writes into <dataset>/../models/<name>/:
  hens.onnx, hens-labels.txt   copy both into Frigate's config/model_cache
  frigate.yml                  the config.yml lines to switch Frigate over
  train/                       Ultralytics' training run: charts, scores, weights

Trains at 640 so small, distant hens keep their detail, and exports at 320,
Frigate's recommended size (it zooms in on motion before it looks, so hens
are bigger in what the model sees than in a full frame).

Run (on the machine with the GPU, with the shared folder mounted):
  python3 hen_model/train.py --dataset /mnt/hens/dataset

See docs/hen-model.md.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

DEFAULT_MODEL = "yolo11s.pt"


def frigate_snippet(names, size):
    track = "\n".join(f"    - {n}" for n in names)
    return f"""# Paste into Frigate's config.yml, replacing the model:, objects: and
# review: blocks, then restart Frigate.
model:
  model_type: yolo-generic
  width: {size}
  height: {size}
  input_tensor: nchw
  input_dtype: float
  path: /config/model_cache/hens.onnx
  labelmap_path: /config/model_cache/hens-labels.txt

objects:
  track:
{track}
  filters:
    hen:
      min_score: 0.4
      threshold: 0.6

review:
  alerts:
    labels:
{chr(10).join(f"      - {n}" for n in names if n != "hen")}
  detections:
    labels:
      - hen
"""


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dataset", required=True, help="the dataset folder from dataset.py (holds data.yaml)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"starting model (default {DEFAULT_MODEL}; yolo11m.pt is slower and a little better)")
    p.add_argument("--epochs", type=int, default=150, help="passes over the dataset (default 150; stops early once it stops improving)")
    p.add_argument("--imgsz", type=int, default=640, help="training size (default 640)")
    p.add_argument("--export-size", type=int, default=320, choices=[320, 640],
                   help="size Frigate runs it at (default 320)")
    p.add_argument("--batch", type=int, default=-1, help="images per step (default -1: as many as the GPU fits)")
    p.add_argument("--device", default=None, help="0 for the first NVIDIA GPU, cpu, mps (Mac); default picks one")
    p.add_argument("--name", default=f"hens-{datetime.now():%Y%m%d-%H%M}", help="name for this model (default hens-<date>)")
    args = p.parse_args()

    from ultralytics import YOLO

    dataset = Path(args.dataset)
    data_yaml = dataset / "data.yaml"
    if not data_yaml.exists():
        sys.exit(f"No data.yaml in {dataset}: run dataset.py first")
    names = [n for _, n in sorted(yaml.safe_load(data_yaml.read_text())["names"].items())]
    out = dataset.parent / "models" / args.name
    out.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    model.train(data=str(data_yaml), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, patience=40, project=str(out), name="train", exist_ok=True,
                # Vary brightness a little more than usual, for dusk.
                hsv_v=0.5, plots=True)

    best = out / "train" / "weights" / "best.pt"
    trained = YOLO(str(best))
    metrics = trained.val(data=str(data_yaml), imgsz=args.imgsz, device=args.device, plots=False, verbose=False)
    onnx = Path(trained.export(format="onnx", imgsz=args.export_size, simplify=True, dynamic=False, opset=17))
    shutil.copy2(onnx, out / "hens.onnx")
    (out / "hens-labels.txt").write_text("".join(f"{i}  {n}\n" for i, n in enumerate(names)))
    (out / "frigate.yml").write_text(frigate_snippet(names, args.export_size))

    print(f"\nModel: {out}")
    print("How well it finds each class on the validation frames (mAP50, 0-1; above 0.8 is good):")
    per_class = dict(zip(metrics.box.ap_class_index.tolist(), metrics.box.ap50.tolist()))
    for i, n in enumerate(names):
        print(f"  {n:8} {per_class[i]:.2f}" if i in per_class else f"  {n:8} -  (no validation boxes)")
    print(f"\nNext: copy hens.onnx and hens-labels.txt into Frigate's config/model_cache,\n"
          f"then apply {out / 'frigate.yml'} to config.yml and restart Frigate.")


if __name__ == "__main__":
    main()
