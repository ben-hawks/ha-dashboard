#!/usr/bin/env bash
# Build the YOLOv9 detection model for Frigate and put it where config.yml
# expects it: config/model_cache/yolo.onnx. Better at small and bunched hens
# than the model built into Frigate. Takes a few minutes; needs Docker.
#
# The build is Frigate's own (docs.frigate.video, Object Detectors > YOLOv9).
# Sizes: t, s (default), m, c, e. Image sizes: 320 (default) or 640.
#
# Run (in this folder):  ./export-yolov9.sh          # yolov9-s at 320
#                        ./export-yolov9.sh c 320
# Then switch the model block in config/config.yml (docs/frigate.md) and
# restart Frigate.
set -euo pipefail
cd "$(dirname "$0")"

MODEL_SIZE=${1:-s}
IMG_SIZE=${2:-320}
OUT=$(mktemp -d)
EMPTY=$(mktemp -d) # build context: the build needs no local files, so don't send it the recordings

docker build "$EMPTY" --build-arg MODEL_SIZE="$MODEL_SIZE" --build-arg IMG_SIZE="$IMG_SIZE" --output "$OUT" -f- <<'EOF'
FROM python:3.11 AS build
RUN apt-get update && apt-get install --no-install-recommends -y cmake libgl1 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /bin/
WORKDIR /yolov9
ADD https://github.com/WongKinYiu/yolov9.git .
RUN uv pip install --system -r requirements.txt
RUN uv pip install --system onnx==1.18.0 onnxruntime onnx-simplifier==0.4.* onnxscript
ARG MODEL_SIZE
ARG IMG_SIZE
ADD https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-${MODEL_SIZE}-converted.pt yolov9-${MODEL_SIZE}.pt
RUN sed -i "s/ckpt = torch.load(attempt_download(w), map_location='cpu')/ckpt = torch.load(attempt_download(w), map_location='cpu', weights_only=False)/g" models/experimental.py
RUN python3 export.py --weights ./yolov9-${MODEL_SIZE}.pt --imgsz ${IMG_SIZE} --simplify --include onnx
FROM scratch
ARG MODEL_SIZE
ARG IMG_SIZE
COPY --from=build /yolov9/yolov9-${MODEL_SIZE}.onnx /yolov9-${MODEL_SIZE}-${IMG_SIZE}.onnx
EOF

mkdir -p config/model_cache
mv "$OUT/yolov9-$MODEL_SIZE-$IMG_SIZE.onnx" config/model_cache/yolo.onnx
rmdir "$OUT" "$EMPTY"
echo "Saved config/model_cache/yolo.onnx (yolov9-$MODEL_SIZE, $IMG_SIZE x $IMG_SIZE)."
echo "Set width and height to $IMG_SIZE in config.yml's YOLOv9 model block."
