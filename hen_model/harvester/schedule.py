#!/usr/bin/env python3
"""Run harvest.py at set times every day, inside the hen-harvester container.

Settings come from the container's environment (the Portainer stack):
  FRIGATE_URL       Frigate's address (default http://127.0.0.1:8971)
  FRIGATE_USER      a Frigate viewer login
  FRIGATE_PASSWORD
  HARVEST_AT        local times to run, comma-separated (default 23:30)
  HARVEST_ARGS      extra harvest.py options, e.g. --busy 06:30-08:30,17:00-19:30
  RUN_ON_START      harvest once as soon as the container starts (default yes)

Each run looks back to the last one that worked, plus a little overlap, but
never more than the 3 days Frigate keeps: if the container was down for a
day, the next run catches up instead of leaving a gap. The time of the last
good run is kept in /hens/.harvest-last.
"""

import os
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HENS = Path("/hens")
LAST = HENS / ".harvest-last"
MAX_DAYS = 3  # Frigate's continuous recording retention
OVERLAP = timedelta(hours=2)


def stop(signum, frame):
    # Docker's stop: leave straight away. A harvest cut short is fine; the
    # next one picks up from the last run that finished.
    log("stopping")
    sys.exit(0)


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}", flush=True)


def parse_times(text):
    times = []
    for part in filter(None, (p.strip() for p in text.split(","))):
        try:
            h, m = map(int, part.split(":"))
            times.append((h, m))
        except ValueError:
            sys.exit(f"HARVEST_AT: can't read {part!r}; use HH:MM, e.g. 23:30 or 12:00,23:30")
    if not times:
        sys.exit("HARVEST_AT is empty")
    return sorted(times)


def next_run(times, now):
    for day in (0, 1):
        for h, m in times:
            t = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0)
            if t > now:
                return t


def days_back(now):
    try:
        last = datetime.fromtimestamp(float(LAST.read_text()))
        return min(MAX_DAYS, (now - last + OVERLAP).total_seconds() / 86400)
    except (OSError, ValueError):
        return MAX_DAYS  # first run: take everything Frigate still has


def harvest():
    started = datetime.now()
    days = days_back(started)
    cmd = [sys.executable, "/app/harvest.py",
           "--frigate", os.environ.get("FRIGATE_URL", "http://127.0.0.1:8971"),
           "--user", os.environ["FRIGATE_USER"],
           "--out", str(HENS), "--days", f"{days:.2f}",
           *shlex.split(os.environ.get("HARVEST_ARGS", ""))]
    log(f"harvesting the last {days:.1f} days")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        LAST.write_text(str(started.timestamp()))
        log("harvest finished")
    else:
        log(f"harvest failed (exit {result.returncode}); the next run will cover this period too")


def main():
    for name in ("FRIGATE_USER", "FRIGATE_PASSWORD"):
        if not os.environ.get(name):
            sys.exit(f"{name} isn't set: add it to the stack's environment variables")
    if not os.access(HENS, os.W_OK):
        sys.exit(f"Can't write to {HENS}: check HENS_PATH, and that HENS_OWNER is its owner (ls -ln)")
    times = parse_times(os.environ.get("HARVEST_AT", "23:30"))
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log(f"hen harvester: runs daily at {', '.join(f'{h:02d}:{m:02d}' for h, m in times)} "
        f"({time.strftime('%Z')}), Frigate at {os.environ.get('FRIGATE_URL', 'http://127.0.0.1:8971')}")
    if os.environ.get("RUN_ON_START", "yes").lower() not in ("no", "false", "0"):
        harvest()
    while True:
        when = next_run(times, datetime.now())
        log(f"next harvest at {when:%Y-%m-%d %H:%M}")
        while datetime.now() < when:
            time.sleep(min(30, max(1, (when - datetime.now()).total_seconds())))
        harvest()


if __name__ == "__main__":
    main()
