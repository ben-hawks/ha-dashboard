# The hen harvester: harvest.py on a daily schedule, then prelabel.py to send
# the new frames to Label Studio with YOLOE's first-guess boxes. Built by
# Portainer from this repo (hen_model/harvester/docker-compose.yml); the
# build context is hen_model/. Source: github.com/ben-hawks/ha-dashboard
ARG BASE=python:3.12-slim
FROM ${BASE}

# libgl1/libglib2.0: OpenCV's needs; git: to install CLIP below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*

# YOLOE on the CPU. Versions are the ones this was tested with.
RUN pip install --no-cache-dir --disable-pip-version-check \
        --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 torchvision==0.29.2
# CLIP is YOLOE's text side; Ultralytics would otherwise try to install it
# on first use, which a non-root container can't.
RUN pip install --no-cache-dir --disable-pip-version-check \
        ultralytics==8.4.194 "git+https://github.com/ultralytics/CLIP.git" \
        "requests>=2.31,<3" "pyyaml>=6,<7" "numpy>=1.26,<3" "pillow>=10,<12"

COPY harvest.py prelabel.py common.py classes.yaml /app/
COPY harvester/schedule.py /app/

# Model downloads (YOLOE and its text model) and Ultralytics' settings live
# here, on a volume, so they're fetched once. Writable by any user, since
# the container runs as the hens folder's owner.
RUN mkdir -m 1777 /cache
WORKDIR /cache
ENV PYTHONUNBUFFERED=1 HOME=/cache YOLO_CONFIG_DIR=/cache/ultralytics
ENTRYPOINT ["python", "/app/schedule.py"]
