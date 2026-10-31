# The hen harvester: harvest.py on a daily schedule. Built by Portainer from
# this repo (hen_model/harvester/docker-compose.yml); the build context is
# hen_model/. Source: github.com/ben-hawks/ha-dashboard
ARG BASE=python:3.12-slim
FROM ${BASE}

RUN pip install --no-cache-dir --disable-pip-version-check \
        "requests>=2.31,<3" "pyyaml>=6,<7" "numpy>=1.26,<3" "pillow>=10,<12"

COPY harvest.py common.py classes.yaml /app/
COPY harvester/schedule.py /app/

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "/app/schedule.py"]
