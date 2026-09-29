#!/usr/bin/env python3
"""Simulated wrist pulse (PPG) band that uploads to PulseCloud.

Stdlib only. Produces one sample per minute with a realistic daily rhythm:
lower heart rate asleep, higher when active, occasional exercise bursts,
loose-band noise (low signal quality) and rare irregular-rhythm events.

Examples:
    # Backfill the last 24 hours, then stream live every 5 seconds (1 simulated min each)
    python simulate.py --key hm_xxx --backfill-hours 24 --interval 5

    # Just backfill a week and exit
    python simulate.py --key hm_xxx --backfill-hours 168 --no-live
"""

import argparse
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta


class WristBand:
    def __init__(self, resting_bpm: int = 64, seed: int | None = None):
        self.rng = random.Random(seed)
        self.resting = resting_bpm
        self.exercise_left = 0
        self.bpm = float(resting_bpm)

    def sample(self, ts: datetime) -> dict:
        hour = ts.hour + ts.minute / 60
        asleep = hour < 6 or hour >= 23
        # Circadian curve: lowest ~4am, highest mid-afternoon.
        circadian = 6 * math.sin((hour - 10) / 24 * 2 * math.pi)
        target = self.resting + circadian + (-8 if asleep else 8)

        if not asleep and self.exercise_left == 0 and self.rng.random() < 0.004:
            self.exercise_left = self.rng.randint(15, 45)  # minutes
        if self.exercise_left:
            target += self.rng.uniform(55, 80)
            self.exercise_left -= 1

        # Heart rate drifts toward target rather than jumping.
        self.bpm += (target - self.bpm) * 0.3 + self.rng.gauss(0, 2)
        bpm = self.bpm

        quality = min(1.0, max(0.0, self.rng.gauss(0.9 if asleep else 0.82, 0.08)))
        if self.rng.random() < 0.02:  # loose band / motion artefact
            quality = self.rng.uniform(0.1, 0.4)
            bpm += self.rng.uniform(-35, 35)

        irregular = self.rng.random() < 0.001
        hrv = max(5.0, self.rng.gauss(55 if asleep else 38, 8) - max(0.0, self.bpm - self.resting) * 0.4)
        if irregular:
            hrv *= 2.5

        return {
            "recorded_at": ts.isoformat(),
            "bpm": int(round(min(220, max(30, bpm)))),
            "hrv_ms": round(hrv, 1),
            "signal_quality": round(quality, 2),
            "irregular_rhythm": irregular,
        }


def upload(api: str, key: str, readings: list[dict], retries: int = 4) -> dict:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/v1/ingest",
        data=json.dumps({"readings": readings}).encode(),
        headers={"Content-Type": "application/json", "X-Device-Key": key},
        method="POST",
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code < 500:  # auth / subscription / validation — retrying won't help
                sys.exit(f"Upload rejected ({e.code}): {detail}")
            err = f"{e.code} {detail}"
        except urllib.error.URLError as e:
            err = str(e.reason)
        wait = 2 ** (attempt + 1)
        print(f"  upload failed ({err}); retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    sys.exit("Giving up after repeated upload failures")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000", help="API base URL")
    p.add_argument("--key", required=True, help="Device API key (hm_...) from the dashboard")
    p.add_argument("--resting-bpm", type=int, default=64)
    p.add_argument("--backfill-hours", type=float, default=0, help="Upload this much history first")
    p.add_argument("--interval", type=float, default=60, help="Seconds between live samples")
    p.add_argument("--batch", type=int, default=1, help="Live samples to buffer before uploading")
    p.add_argument("--no-live", action="store_true", help="Exit after backfill")
    p.add_argument("--seed", type=int)
    args = p.parse_args()

    band = WristBand(args.resting_bpm, args.seed)
    now = datetime.now(UTC).replace(second=0, microsecond=0)

    if args.backfill_hours:
        ts = now - timedelta(hours=args.backfill_hours)
        buf: list[dict] = []
        while ts < now:
            buf.append(band.sample(ts))
            ts += timedelta(minutes=1)
            if len(buf) == 500:
                print(f"backfill up to {ts:%Y-%m-%d %H:%M}Z -> {upload(args.api, args.key, buf)}")
                buf = []
        if buf:
            print(f"backfill done -> {upload(args.api, args.key, buf)}")

    if args.no_live:
        return

    print(f"Streaming live pulse every {args.interval}s (Ctrl+C to stop)")
    buf = []
    try:
        while True:
            # Advance one simulated minute per tick so fast intervals still produce unique timestamps.
            now += timedelta(minutes=1)
            s = band.sample(now)
            buf.append(s)
            flag = " IRREGULAR" if s["irregular_rhythm"] else ""
            print(f"{s['recorded_at']}  {s['bpm']:>3} bpm  hrv {s['hrv_ms']:>5} ms  q={s['signal_quality']}{flag}")
            if len(buf) >= args.batch:
                result = upload(args.api, args.key, buf)
                if result.get("alerts_created"):
                    print(f"  -> {result['alerts_created']} alert(s) raised")
                buf = []
            time.sleep(args.interval)
    except KeyboardInterrupt:
        if buf:
            upload(args.api, args.key, buf)


if __name__ == "__main__":
    main()
