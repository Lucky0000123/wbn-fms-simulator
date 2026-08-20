"""Accumulate the live GPS and congestion feeds forward, before retention deletes them.

This is the one blocker that gets worse with delay rather than staying put. GPS
retention is a rolling few days and FMS_CONGESTION_SEG about two weeks, so every day
without an append is a day of segment speeds permanently gone. Leaving this as a
recommendation would mean the recommendation itself decays.

Idempotent by design: appends only (day, truck) or (hour, segment, direction) keys
not already present, so it can run daily, twice daily, or after a gap, and re-runs
are harmless. Safe to schedule.

Usage:
    python scripts/accumulate_gps.py            # append today's new rows
    python scripts/accumulate_gps.py --status   # what is banked, no DB needed
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import pandas as pd

# Load FMS_DB_* creds BEFORE importing simulator_api (it snapshots _DB at
# import). Same fix as serve.py 2026-08-20; cron worked only when the env
# was exported by the shell.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from load_fms_env import load_fms_env
    load_fms_env()
except Exception:  # noqa: BLE001
    pass

import simulator_api as sim

ROOT = "/Users/lucky/wbn-fms-simulator"
DATA = os.path.join(ROOT, "data")
ARCHIVE = os.path.join(DATA, "gps_archive")
SEG_STORE = os.path.join(ARCHIVE, "congestion_seg_hourly.csv")
GPS_STORE = os.path.join(ARCHIVE, "gps_fixes.csv")
MANIFEST = os.path.join(ARCHIVE, "manifest.json")


def conn(db):
    import pymssql
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def _read(path) -> pd.DataFrame:
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()


def status() -> dict:
    """What is banked. Deliberately needs no DB, so it works with the VPN down."""
    seg, gps = _read(SEG_STORE), _read(GPS_STORE)
    s = {"segment_rows": int(len(seg)), "gps_rows": int(len(gps))}
    if len(seg):
        s["segment_hours"] = int(seg.HOUR_TS.nunique())
        s["segment_days"] = int(pd.to_datetime(
            seg.HOUR_TS.astype("int64"), unit="ms", utc=True).dt.date.nunique())
        s["segments"] = int(seg.SEG_ID.nunique())
    if len(gps):
        s["gps_days"] = int(gps.day.nunique())
        s["gps_trucks"] = int(gps.truck.nunique())
    if os.path.exists(MANIFEST):
        s["manifest"] = json.load(io.open(MANIFEST, encoding="utf-8"))
    return s


def accumulate_segments(f) -> int:
    """Append congestion-segment hours not already banked."""
    q = """SELECT HOUR_TS, SEG_ID, DIR, SUM_SPD, FIX_N, TRUCK_N,
                  SUM_TRAV_MS, TRAV_N
           FROM FMS_CONGESTION_SEG WHERE FIX_N > 0"""
    new = pd.read_sql(q, f)
    old = _read(SEG_STORE)
    if len(old):
        # Key on (hour, segment, direction): the natural grain of the table.
        seen = set(zip(old.HOUR_TS, old.SEG_ID.astype(str), old.DIR.astype(str)))
        mask = [t not in seen for t in
                zip(new.HOUR_TS, new.SEG_ID.astype(str), new.DIR.astype(str))]
        new = new[pd.Series(mask, index=new.index)]
    if not len(new):
        print("  segments: nothing new")
        return 0
    out = pd.concat([old, new], ignore_index=True) if len(old) else new
    out.to_csv(SEG_STORE, index=False)
    print("  segments: +%s rows (total %s)"
          % ("{:,}".format(len(new)), "{:,}".format(len(out))))
    return len(new)


def accumulate_gps(f, w) -> int:
    """Append per-(day, truck) GPS aggregates for trucks that actually hauled.

    Stores aggregates rather than raw fixes: raw would grow by ~1M rows a day and
    the segment table already carries the per-segment detail. This preserves who
    was tracked when, which is what a future coverage analysis needs.
    """
    frames = []
    for t in ("FMS_GPS_Historical", "FMS_PLAYBACK_TRACK_24H"):
        q = ("SELECT CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS day,"
             " UPPER(LTRIM(RTRIM(PLATE))) AS truck, COUNT(*) AS fixes,"
             " MIN(TS) AS first_ts, MAX(TS) AS last_ts"
             " FROM [%s] WHERE PLATE IS NOT NULL"
             " AND LAT NOT BETWEEN -0.0001 AND 0.0001"
             " GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date),"
             " UPPER(LTRIM(RTRIM(PLATE)))" % t)
        try:
            frames.append(pd.read_sql(q, f))
        except Exception as e:
            print("  %s failed: %s" % (t, str(e)[:60]))
    if not frames:
        return 0
    new = pd.concat(frames, ignore_index=True)
    new = new.groupby(["day", "truck"], as_index=False).agg(
        fixes=("fixes", "sum"), first_ts=("first_ts", "min"),
        last_ts=("last_ts", "max"))
    new["day"] = new.day.astype(str)

    old = _read(GPS_STORE)
    if len(old):
        seen = set(zip(old.day.astype(str), old.truck.astype(str)))
        mask = [t not in seen for t in zip(new.day, new.truck.astype(str))]
        new = new[pd.Series(mask, index=new.index)]
    if not len(new):
        print("  gps: nothing new")
        return 0
    out = pd.concat([old, new], ignore_index=True) if len(old) else new
    out.to_csv(GPS_STORE, index=False)
    print("  gps: +%s (day,truck) rows (total %s)"
          % ("{:,}".format(len(new)), "{:,}".format(len(out))))
    return len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true",
                    help="report what is banked; needs no database")
    args = ap.parse_args()

    if args.status:
        print(json.dumps(status(), indent=2))
        return

    os.makedirs(ARCHIVE, exist_ok=True)
    print("accumulating at %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    f, w = conn("FMS_DB"), conn("WBN_DATABASE")
    n_seg = accumulate_segments(f)
    n_gps = accumulate_gps(f, w)

    man = json.load(io.open(MANIFEST, encoding="utf-8")) \
        if os.path.exists(MANIFEST) else {"runs": []}
    man["runs"] = (man.get("runs", []) + [{
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "segment_rows_added": n_seg, "gps_rows_added": n_gps}])[-200:]
    man["last_run"] = man["runs"][-1]["at"]
    man["why"] = ("GPS retention is a rolling few days and FMS_CONGESTION_SEG about "
                  "two weeks, so segment speeds cannot be backfilled. This archive "
                  "is the only way the record grows. Idempotent: re-runs add nothing.")
    io.open(MANIFEST, "w", encoding="utf-8").write(json.dumps(man, indent=2))
    # Keep stick measuredSpeeds aligned with the banked Jul+ window (offline).
    try:
        import plan_corridor_hours as pch
        stick = pch.rebuild_by_dir_from_archive()
        if stick.get("ok"):
            print("  stick by_dir: %s rows / %s segs from archive"
                  % (stick.get("rows"), stick.get("segments")))
        else:
            print("  stick by_dir refresh skipped: %s" % stick.get("error"))
    except Exception as e:  # noqa: BLE001
        print("  stick by_dir refresh failed: %s" % str(e)[:120])
    print("\n" + json.dumps(status(), indent=2))


if __name__ == "__main__":
    main()
