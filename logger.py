"""Poll the NC State Wolfline GTFS-realtime vehicle positions feed and append rows to a CSV.

Usage: python logger.py --minutes 30 --interval 30 --out data/raw
Each call writes to data/raw/<local date>/run_<start time>.csv, so overlapping runs never
write to the same file. Duplicate rows across runs are removed later by (vehicle_id, vehicle_timestamp).
"""
import argparse
import csv
import datetime
import hashlib
import os
import time
import urllib.request
from zoneinfo import ZoneInfo

from google.transit import gtfs_realtime_pb2

BASE = "https://passio3.com/ncstateuni/passioTransit/gtfs"
VEHICLES_URL = BASE + "/realtime/vehiclePositions"
SCHEDULE_URL = BASE + "/google_transit.zip"
TZ = ZoneInfo("America/New_York")

FIELDS = [
    "poll_time_utc", "poll_time_local", "feed_timestamp",
    "vehicle_id", "vehicle_label", "trip_id", "route_id",
    "latitude", "longitude", "bearing", "speed",
    "current_stop_sequence", "stop_id", "current_status", "occupancy_status",
    "vehicle_timestamp",
]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "ise537-wolfline-logger"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def save_schedule(out_dir):
    """Keep a copy of the static schedule; a new file only appears when its contents change."""
    data = fetch(SCHEDULE_URL, timeout=60)
    digest = hashlib.sha256(data).hexdigest()[:12]
    gtfs_dir = os.path.join(out_dir, "gtfs")
    os.makedirs(gtfs_dir, exist_ok=True)
    if not any(digest in f for f in os.listdir(gtfs_dir)):
        day = datetime.datetime.now(TZ).strftime("%Y%m%d")
        with open(os.path.join(gtfs_dir, f"google_transit_{day}_{digest}.zip"), "wb") as f:
            f.write(data)


def poll_once():
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(fetch(VEHICLES_URL))
    now = datetime.datetime.now(datetime.timezone.utc)
    status = gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name
    occupancy = gtfs_realtime_pb2.VehiclePosition.OccupancyStatus.Name
    rows = []
    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        rows.append({
            "poll_time_utc": now.isoformat(timespec="seconds"),
            "poll_time_local": now.astimezone(TZ).isoformat(timespec="seconds"),
            "feed_timestamp": feed.header.timestamp,
            "vehicle_id": v.vehicle.id,
            "vehicle_label": v.vehicle.label,
            "trip_id": v.trip.trip_id,
            "route_id": v.trip.route_id,
            "latitude": v.position.latitude,
            "longitude": v.position.longitude,
            "bearing": v.position.bearing,
            "speed": v.position.speed,
            "current_stop_sequence": v.current_stop_sequence,
            "stop_id": v.stop_id,
            "current_status": status(v.current_status),
            "occupancy_status": occupancy(v.occupancy_status) if v.HasField("occupancy_status") else "",
            "vehicle_timestamp": v.timestamp,
        })
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--interval", type=float, default=30)
    p.add_argument("--out", default="data")
    args = p.parse_args()

    try:
        save_schedule(args.out)
    except Exception as ex:
        print("schedule download failed:", ex)

    start = datetime.datetime.now(TZ)
    day_dir = os.path.join(args.out, "raw", start.strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    path = os.path.join(day_dir, f"run_{start.strftime('%H%M%S')}.csv")

    seen = set()
    n_rows = n_polls = n_errors = 0
    deadline = time.monotonic() + args.minutes * 60
    while time.monotonic() < deadline:
        t0 = time.monotonic()
        try:
            rows = [r for r in poll_once() if (r["vehicle_id"], r["vehicle_timestamp"]) not in seen]
            n_polls += 1
        except Exception as ex:
            rows = []
            n_errors += 1
            print("poll failed:", ex)
        if rows:
            new_file = not os.path.exists(path)
            with open(path, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                if new_file:
                    w.writeheader()
                w.writerows(rows)
            seen.update((r["vehicle_id"], r["vehicle_timestamp"]) for r in rows)
            n_rows += len(rows)
        time.sleep(max(0, args.interval - (time.monotonic() - t0)))
    print(f"polls={n_polls} errors={n_errors} rows={n_rows} file={path}")


if __name__ == "__main__":
    main()
