#!/usr/bin/env python3
"""Suggest laundry cycle-detection thresholds from Home Assistant power history.

Run one normal cycle on the appliance first, then:

    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=<long-lived access token>
    python3 tools/laundry_profile.py sensor.washer_power --hours 6
    python3 tools/laundry_profile.py sensor.dryer_power --hours 6

Offline: --csv FILE with "timestamp,watts" rows (ISO timestamps). Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Segment:
    start: datetime
    end: datetime

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()


def parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_history(entity: str, hours: float) -> list[tuple[datetime, float]]:
    url, token = os.environ.get("HA_URL"), os.environ.get("HA_TOKEN")
    if not url or not token:
        sys.exit("Set HA_URL and HA_TOKEN (or use --csv).")
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = urllib.parse.urlencode(
        {"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""}
    )
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/history/period/{urllib.parse.quote(start)}?{q}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    rows = data[0] if data else []
    out = []
    for row in rows:
        try:
            out.append((parse_ts(row["last_changed"]), float(row["state"])))
        except (KeyError, ValueError):
            continue  # unavailable/unknown
    return out


def read_csv(path: str) -> list[tuple[datetime, float]]:
    with open(path, newline="") as f:
        return [(parse_ts(t), float(w)) for t, w, *_ in csv.reader(f) if t[:1].isdigit()]


def segments_above(series, threshold) -> list[Segment]:
    """Contiguous spans where power > threshold (series is a step function)."""
    segs, start = [], None
    for (t, w), (t_next, _) in zip(series, series[1:] + [(series[-1][0], 0)]):
        if w > threshold and start is None:
            start = t
        elif w <= threshold and start is not None:
            segs.append(Segment(start, t))
            start = None
    if start is not None:
        segs.append(Segment(start, series[-1][0]))
    return segs


def group(segs: list[Segment], max_gap: float) -> list[list[Segment]]:
    groups: list[list[Segment]] = []
    for s in segs:
        if groups and (s.start - groups[-1][-1].end).total_seconds() <= max_gap:
            groups[-1].append(s)
        else:
            groups.append([s])
    return groups


def fmt(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def analyze(series, max_gap: float, min_cycle: float, burst_max: float) -> None:
    series.sort()
    watts = [w for _, w in series]
    if len(watts) < 10:
        sys.exit("Not enough samples — widen --hours or check the entity id.")
    baseline = sorted(watts)[len(watts) // 10]  # ~10th percentile = idle draw
    detect = baseline + 5
    segs = segments_above(series, detect)
    groups = group(segs, max_gap)
    # Trailing short segments are post-cycle bursts (dryer wrinkle guard), not the cycle.
    bursts: list[Segment] = []
    for g in groups:
        while len(g) > 1 and g[-1].seconds <= burst_max and (g[-1].start - g[-2].end).total_seconds() >= 60:
            bursts.append(g.pop())
    cycles = [g for g in groups if (g[-1].end - g[0].start).total_seconds() >= min_cycle]
    bursts += [s for g in groups if g not in cycles for s in g if s.seconds <= burst_max]
    if not cycles:
        sys.exit(f"No cycle >= {fmt(min_cycle)} found above {detect:.1f} W.")

    print(f"Samples: {len(watts)}   idle baseline ~ {baseline:.1f} W")
    longest_gap = longest_burst = 0.0
    run_p10s = []
    for i, g in enumerate(cycles, 1):
        start, end = g[0].start, g[-1].end
        inside = [w for t, w in series if start <= t <= end and w > detect]
        p10 = sorted(inside)[len(inside) // 10] if inside else detect
        run_p10s.append(p10)
        gaps = [(b.start - a.end).total_seconds() for a, b in zip(g, g[1:])]
        gap = max(gaps, default=0.0)
        longest_gap = max(longest_gap, gap)
        print(
            f"Cycle {i}: {start.astimezone():%H:%M}-{end.astimezone():%H:%M} "
            f"({fmt((end - start).total_seconds())}), median {statistics.median(inside):.0f} W, "
            f"peak {max(inside):.0f} W, p10 {p10:.0f} W, longest low gap {fmt(gap)}"
        )
        # short bursts within 3h after the cycle (e.g. dryer wrinkle guard)
        after = [s for s in bursts if end < s.start <= end + timedelta(hours=3)]
        if after:
            longest_burst = max([longest_burst] + [s.seconds for s in after])
            print(f"         {len(after)} post-cycle burst(s), longest {fmt(max(s.seconds for s in after))}")

    on_thr = max(baseline + 5, 0.5 * min(run_p10s))
    off_thr = baseline + max(2, (on_thr - baseline) * 0.3)
    delay_off = longest_gap * 1.3 + 60
    delay_on = max(30, longest_burst * 1.5 + 30)

    print("\nSuggested template values:")
    print(f"  on threshold : {on_thr:.0f} W")
    print(f"  off threshold: {off_thr:.0f} W")
    print(f"  delay_on     : \"{fmt(delay_on)}\"" + (
        f"   (post-cycle bursts up to {fmt(longest_burst)})" if longest_burst else ""))
    print(f"  delay_off    : \"{fmt(delay_off)}\"   (longest in-cycle pause {fmt(longest_gap)})")
    shortest = min((g[-1].end - g[0].start).total_seconds() for g in cycles)
    if delay_on >= shortest:
        print("  WARNING: delay_on is not shorter than the shortest cycle; check the data.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entity", nargs="?", help="e.g. sensor.washer_power")
    ap.add_argument("--hours", type=float, default=6)
    ap.add_argument("--csv", help="offline input: timestamp,watts")
    ap.add_argument("--max-gap", type=float, default=20 * 60,
                    help="seconds of low power still counted as the same cycle (default 1200)")
    ap.add_argument("--min-cycle", type=float, default=10 * 60,
                    help="ignore activity shorter than this many seconds (default 600)")
    ap.add_argument("--burst-max", type=float, default=5 * 60,
                    help="max length of a post-cycle burst, seconds (default 300)")
    a = ap.parse_args()
    if a.csv:
        series = read_csv(a.csv)
    elif a.entity:
        series = fetch_history(a.entity, a.hours)
    else:
        ap.error("give an entity id or --csv")
    analyze(series, a.max_gap, a.min_cycle, a.burst_max)


if __name__ == "__main__":
    main()
