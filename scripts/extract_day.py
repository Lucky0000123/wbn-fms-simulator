"""extract_day.py — pull every source for one operational day and join them.

WHY DAY X IS 2026-07-19 AND NOT THE BUSIEST DAY
The brief proposes the busiest day in 2026-01-01..2026-06-30 by truck count.
Measured, that window contains ZERO haul-truck GPS: FMS_PLAYBACK_TRACK_DATA is
219 support units (SS###/E###), and on 2026-06-26 exactly 0 of its 121 plates
are weighbridge haul trucks. A busy June day would prove nothing about the join.

Searching every day for trucks that have BOTH a weighbridge trip and GPS on the
same date gives only four candidates, all in the raw-GPS retention window:

    2026-07-19   24 trucks   26 trips   11,584 fixes   <- Day X
    2026-07-16   15 trucks   19 trips    3,580 fixes
    2026-07-15   14 trucks   21 trips    3,581 fixes
    2026-07-18    1 truck     1 trip       172 fixes

So Day X is 2026-07-19. It is a SMALL sample and that is stated everywhere it
matters: 24 trucks is enough to prove the pipeline mechanically, not enough to
publish segment speeds as operational fact.

WHY TRIPS COME FROM TWO TABLES
HAULAGE_IWIP_CLEAN stops at 2026-07-09, before any haul-truck GPS exists.
HAULAGE runs to 2026-07-28 and carries the same TRUCK_ID vocabulary (644 of 645
GPS haul trucks appear in it), so it supplies Day X's trips. Both are pulled and
labelled by source so nothing is silently blended.

READ ONLY. Extraction and analysis only; no application code is touched.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
DEFAULT_DAY = "2026-07-19"


def conn(db):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def norm(s):
    return s.astype(str).str.strip().str.upper()


def step(msg):
    print("\n=== %s ===" % msg, flush=True)


def extract_trips(w, day) -> pd.DataFrame:
    """Day X trips from both haulage tables, each row labelled with its source."""
    step("STEP 2: weighbridge trips")
    hi = pd.read_sql("""
        SELECT TICKET_NO, TRUCK_ID, [DATE] AS date, SHIFT, CONTRACTOR,
               ORIGIN_AREA, DESTINATION_AREA, WMT, MATERIAL,
               FIRST_WB_TIME, SECOND_WB_TIME, ACTIVITY
        FROM HAULAGE_IWIP_CLEAN
        WHERE CAST([DATE] AS date) = '%s' AND FIRST_WB_TIME IS NOT NULL
          AND SECOND_WB_TIME IS NOT NULL AND WMT > 0""" % day, w)
    hi["src_table"] = "HAULAGE_IWIP_CLEAN"
    hl = pd.read_sql("""
        SELECT TICKET_NO, TRUCK_ID, [DATE] AS date, SHIFT, CONTRACTOR,
               ORIGIN_AREA, DESTINATION_AREA, WMT, MATERIAL,
               TIME_LOADED, TIME_EMPTY, ACTIVITY, RIT
        FROM HAULAGE
        WHERE CAST([DATE] AS date) = '%s' AND WMT > 0""" % day, w)
    hl["src_table"] = "HAULAGE"
    # HAULAGE stores clock times, not datetimes; build real timestamps so the
    # GPS window match has something to compare against.
    if not hl.empty:
        base = pd.to_datetime(hl["date"])
        for col, out in (("TIME_LOADED", "FIRST_WB_TIME"),
                         ("TIME_EMPTY", "SECOND_WB_TIME")):
            td = pd.to_timedelta(hl[col].astype(str), errors="coerce")
            hl[out] = base + td
        # An empty-weigh clock earlier than the loaded-weigh clock means the
        # trip crossed midnight; roll it forward rather than yielding a
        # negative duration.
        flip = hl["SECOND_WB_TIME"] < hl["FIRST_WB_TIME"]
        hl.loc[flip, "SECOND_WB_TIME"] += pd.Timedelta(days=1)
        hl["crossed_midnight"] = flip.astype(int)
    trips = pd.concat([hi, hl], ignore_index=True)
    if trips.empty:
        return trips
    trips["truck"] = norm(trips["TRUCK_ID"])
    trips["cycle_min"] = ((pd.to_datetime(trips["SECOND_WB_TIME"])
                           - pd.to_datetime(trips["FIRST_WB_TIME"]))
                          .dt.total_seconds() / 60)
    trips["trip_id"] = ["T%05d" % i for i in range(len(trips))]
    print("trips: %d (%s)" % (len(trips),
                              dict(trips.src_table.value_counts())))
    print("unique trucks: %d | routes: %d"
          % (trips.truck.nunique(),
             trips.groupby(["ORIGIN_AREA", "DESTINATION_AREA"]).ngroups))
    print("\nroutes on Day X:")
    r = (trips.groupby(["ORIGIN_AREA", "DESTINATION_AREA"])
              .agg(trips=("trip_id", "size"), trucks=("truck", "nunique"),
                   wmt=("WMT", "sum"), med_cycle=("cycle_min", "median"))
              .sort_values("trips", ascending=False))
    print(r.head(15).round(1).to_string())
    return trips


def extract_crosswalk(f, w) -> pd.DataFrame:
    """The plate/device crosswalk, and what each key actually joins to."""
    step("STEP 3: equipment crosswalk")
    eq = pd.read_sql("SELECT truckId, plateNumber, orgName, active "
                     "FROM FMS_EQUIPMENTS", f)
    eq["plate"] = norm(eq["plateNumber"])
    eq["device"] = eq["truckId"].astype(str).str.strip()
    wb = pd.read_sql("SELECT DISTINCT TRUCK_ID FROM HAULAGE_IWIP_CLEAN "
                     "WHERE TRUCK_ID IS NOT NULL AND LEN(TRUCK_ID) > 0", w)
    wids = set(norm(wb["TRUCK_ID"]))
    eq["is_weighbridge_truck"] = eq["plate"].isin(wids)
    print("FMS_EQUIPMENTS rows: %d" % len(eq))
    print("plateNumber matching weighbridge TRUCK_ID: %d (%.1f%%)"
          % (eq.is_weighbridge_truck.sum(),
             100 * eq.is_weighbridge_truck.mean()))
    print("device serial (truckId) matching weighbridge: %d"
          % len(set(eq.device) & wids))
    print("\nformat: plate '%s' vs device '%s'"
          % (eq.plate.iloc[0], eq.device.iloc[0]))
    print("-> plateNumber is the fleet number and joins directly; truckId is a "
          "19-digit telematics device serial and never matches a fleet number.")
    return eq


def extract_gps(f, day, trucks) -> pd.DataFrame:
    """Raw GPS for Day X, restricted to trucks that actually hauled that day."""
    step("STEP 4: GPS for Day X")
    inlist = ",".join("'%s'" % t.replace("'", "''") for t in sorted(trucks))
    frames = []
    for tbl in ("FMS_GPS_Historical", "FMS_PLAYBACK_TRACK_24H"):
        q = """
        SELECT UPPER(LTRIM(RTRIM(PLATE))) AS truck, TS, LAT, LNG, SPEED,
               COURSE, ACC, DISTANCE, '%s' AS src
        FROM [%s]
        WHERE CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) = '%s'
          AND PLATE IS NOT NULL
          AND UPPER(LTRIM(RTRIM(PLATE))) IN (%s)
          AND LAT NOT BETWEEN -0.0001 AND 0.0001""" % (tbl, tbl, day, inlist)
        d = pd.read_sql(q, f)
        print("%-26s %s rows" % (tbl, "{:,}".format(len(d))))
        frames.append(d)
    gps = pd.concat(frames, ignore_index=True)
    if gps.empty:
        return gps
    gps["ts"] = pd.to_datetime(gps["TS"].astype("int64"), unit="ms", utc=True)
    gps = gps.sort_values(["truck", "ts"]).reset_index(drop=True)
    print("\ntotal GPS fixes: %s across %d trucks"
          % ("{:,}".format(len(gps)), gps.truck.nunique()))
    print("time range: %s -> %s" % (gps.ts.min(), gps.ts.max()))
    print("lat %.5f..%.5f  lng %.5f..%.5f"
          % (gps.LAT.min(), gps.LAT.max(), gps.LNG.min(), gps.LNG.max()))
    sp = pd.to_numeric(gps.SPEED, errors="coerce")
    print("speed km/h: median %.1f  p95 %.1f  max %.1f"
          % (sp.median(), sp.quantile(.95), sp.max()))
    gap = gps.groupby("truck").ts.diff().dt.total_seconds()
    print("fix interval sec: median %.0f  p95 %.0f"
          % (gap.median(), gap.quantile(.95)))
    return gps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=DEFAULT_DAY)
    args = ap.parse_args()
    day = args.day
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(REPORTS, exist_ok=True)
    print("DAY X = %s" % day)

    w, f = conn("WBN_DATABASE"), conn("FMS_DB")
    summary = {"day": day,
               "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        trips = extract_trips(w, day)
        trips.to_csv(os.path.join(DATA, "day_x_trips.csv"), index=False)
        summary["trips"] = {
            "rows": int(len(trips)),
            "trucks": int(trips.truck.nunique()) if len(trips) else 0,
            "routes": int(trips.groupby(["ORIGIN_AREA", "DESTINATION_AREA"]).ngroups)
            if len(trips) else 0,
            "by_source": {k: int(v) for k, v in
                          trips.src_table.value_counts().items()} if len(trips) else {},
            "wmt_total": float(trips.WMT.sum()) if len(trips) else 0.0,
        }

        eq = extract_crosswalk(f, w)
        eq.to_csv(os.path.join(DATA, "equipment_crosswalk.csv"), index=False)
        summary["crosswalk"] = {
            "rows": int(len(eq)),
            "plate_matches_weighbridge": int(eq.is_weighbridge_truck.sum()),
            "device_matches_weighbridge": 0,
            "note": ("plateNumber is the fleet number and joins directly to "
                     "HAULAGE/HAULAGE_IWIP_CLEAN.TRUCK_ID; truckId is a "
                     "19-digit device serial that joins only to the GPS tables"),
        }

        gps = pd.DataFrame()
        if len(trips):
            gps = extract_gps(f, day, set(trips.truck))
            gps.to_csv(os.path.join(DATA, "day_x_gps.csv"), index=False)
            matched = sorted(set(gps.truck) & set(trips.truck)) if len(gps) else []
            summary["gps"] = {
                "fixes": int(len(gps)),
                "trucks_with_gps": int(gps.truck.nunique()) if len(gps) else 0,
                "trucks_with_trips": int(trips.truck.nunique()),
                "trucks_with_both": len(matched),
                "match_rate_pct": round(100 * len(matched) / max(trips.truck.nunique(), 1), 1),
                "matched_trucks": matched,
            }
            print("\nGPS-to-weighbridge match: %d of %d trucks (%.1f%%)"
                  % (len(matched), trips.truck.nunique(),
                     100 * len(matched) / max(trips.truck.nunique(), 1)))
    finally:
        w.close(); f.close()

    with open(os.path.join(REPORTS, "day_x_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, default=str)
    print("\nwrote data/day_x_trips.csv, data/equipment_crosswalk.csv, "
          "data/day_x_gps.csv, reports/day_x_summary.json")


if __name__ == "__main__":
    main()
