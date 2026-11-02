#!/usr/bin/env bash
# Build the YOLOv9 detection model for Frigate and put it where config.yml
# expects it: model_cache/yolo.onnx in Frigate's config folder. Better at
# small and bunched hens than the model built into Frigate.
#
# Needs only "docker run" (no image building), so it works in the TrueNAS
# shell. The steps are Frigate's own (docs.frigate.video, Object Detectors >
# YOLOv9), run in a throwaway python:3.11 container. Takes 5-15 minutes and a
# few GB of Docker space while it runs; nothing is left behind except the
# python:3.11 image (docker image rm python:3.11 to remove it).
#
# Sizes: t, s (default), m, c, e. Image sizes: 320 (default) or 640.
#
# Run, with CONFIG_PATH set to the folder holding Frigate's config.yml
# (the same CONFIG_PATH as in the Portainer stack):
#   sudo CONFIG_PATH=/mnt/tank/apps/frigate/config bash export-yolov9.sh
#   sudo CONFIG_PATH=/mnt/tank/apps/frigate/config bash export-yolov9.sh c 320
# Without CONFIG_PATH it uses config/ next to this script.
# Then switch the model block in config.yml (docs/frigate.md) and restart
# Frigate.
set -euo pipefail

MODEL_SIZE=${1:-s}
IMG_SIZE=${2:-320}
CONFIG_PATH=${CONFIG_PATH:-$(cd "$(dirname "$0")" && pwd)/config}

case $MODEL_SIZE in t|s|m|c|e) ;; *) echo "Model size must be t, s, m, c or e, not '$MODEL_SIZE'." >&2; exit 1 ;; esac
case $IMG_SIZE in 320|640) ;; *) echo "Image size must be 320 or 640, not '$IMG_SIZE'." >&2; exit 1 ;; esac
if [ ! -f "$CONFIG_PATH/config.yml" ]; then
    echo "No config.yml in $CONFIG_PATH. Set CONFIG_PATH to Frigate's config folder." >&2
    exit 1
fi

mkdir -p "$CONFIG_PATH/model_cache"
echo "Building yolov9-$MODEL_SIZE at $IMG_SIZE x $IMG_SIZE into $CONFIG_PATH/model_cache/yolo.onnx"

docker run --rm -i \
    -e MODEL_SIZE="$MODEL_SIZE" -e IMG_SIZE="$IMG_SIZE" \
    -v "$CONFIG_PATH/model_cache:/out" \
    python:3.11 bash -s <<'EOF'
set -euo pipefail
apt-get update -qq && apt-get install -qq --no-install-recommends -y cmake libgl1 >/dev/null
pip install -q uv==0.10.4
git clone -q https://github.com/WongKinYiu/yolov9.git /yolov9
cd /yolov9
uv pip install --system -r requirements.txt
uv pip install --system onnx==1.18.0 onnxruntime "onnx-simplifier==0.4.*" onnxscript
curl -fsSL -o "yolov9-$MODEL_SIZE.pt" "https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-$MODEL_SIZE-converted.pt"
sed -i "s/ckpt = torch.load(attempt_download(w), map_location='cpu')/ckpt = torch.load(attempt_download(w), map_location='cpu', weights_only=False)/g" models/experimental.py
python3 export.py --weights "./yolov9-$MODEL_SIZE.pt" --imgsz "$IMG_SIZE" --simplify --include onnx
cp "yolov9-$MODEL_SIZE.onnx" /out/yolo.onnx.tmp
mv /out/yolo.onnx.tmp /out/yolo.onnx
EOF

echo "Saved $CONFIG_PATH/model_cache/yolo.onnx (yolov9-$MODEL_SIZE, $IMG_SIZE x $IMG_SIZE)."
echo "Set width and height to $IMG_SIZE in config.yml's YOLOv9 model block, then restart Frigate."
