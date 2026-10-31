#!/usr/bin/env bash
# Run harvest.py on TrueNAS every day, so frames are collected whether or not
# the training machine is on. Frigate keeps only 3 days of continuous
# footage: a week away with the computer off would otherwise lose it.
#
# It runs harvest.py in a throwaway python:3.12-slim container (TrueNAS
# doesn't allow installing Python packages on the system itself), as the
# owner of the hens folder so the files stay editable over SMB, in TrueNAS's
# time zone so --busy means local let-out and bedtime. A log goes to
# <hens folder>/harvest.log.
#
# Set up once (see docs/hen-model.md):
#   1. Copy hen_model/ to the server, e.g. /mnt/tank/apps/hens/hen_model
#   2. A login file for Frigate, readable only by root:
#        FRIGATE_USER=hens
#        FRIGATE_PASSWORD=...
#      sudo chmod 600 /mnt/tank/apps/hens/frigate-login
#   3. System > Advanced Settings > Cron Jobs > Add, run as root, daily:
#        bash /mnt/tank/apps/hens/hen_model/harvest-truenas.sh /mnt/tank/hens /mnt/tank/apps/hens/frigate-login
#
# Anything after the two paths goes to harvest.py, e.g.
#   ... /mnt/tank/apps/hens/frigate-login --busy 06:30-08:30,17:00-19:30
# FRIGATE_URL in the login file overrides the default http://127.0.0.1:8971.
set -euo pipefail

HENS=${1:?usage: harvest-truenas.sh <hens folder> <frigate login file> [harvest.py options]}
LOGIN=${2:?usage: harvest-truenas.sh <hens folder> <frigate login file> [harvest.py options]}
shift 2
HERE=$(cd "$(dirname "$0")" && pwd)
OWNER=$(stat -c %u:%g "$HENS")
IMAGE=${PYTHON_IMAGE:-python:3.12-slim}

[ -f "$HERE/harvest.py" ] || { echo "harvest.py isn't next to this script ($HERE)" >&2; exit 1; }
[ -r "$LOGIN" ] || { echo "Can't read the login file $LOGIN" >&2; exit 1; }
touch "$HENS/harvest.log" && chown "$OWNER" "$HENS/harvest.log"

{
    echo "=== $(date '+%Y-%m-%d %H:%M:%S')"
    # Ran daily, 1.2 days back overlaps the last run; frames it already has
    # are skipped.
    docker run --rm --network host --user "$OWNER" -e HOME=/tmp \
        --env-file "$LOGIN" \
        -v "$HERE:/app:ro" -v "$HENS:/hens" -v /etc/localtime:/etc/localtime:ro \
        "$IMAGE" sh -c '
            pip install -q --user --disable-pip-version-check --no-warn-script-location \
                requests pyyaml numpy pillow &&
            python /app/harvest.py --frigate "${FRIGATE_URL:-http://127.0.0.1:8971}" \
                --user "$FRIGATE_USER" --out /hens --days 1.2 "$@"' sh "$@"
} 2>&1 | tee -a "$HENS/harvest.log"
