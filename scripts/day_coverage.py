"""day_coverage.py — pick Day X from evidence, not from a guess.

WHY THIS RUNS FIRST
The brief proposes picking the busiest day in 2026-01-01..2026-06-30 by truck
count. That would almost certainly produce a day with NO GPS at all, because
the schema scan measured haul-truck GPS retention as:

    FMS_GPS_Historical      2026-07-15 .. 2026-07-20
    FMS_PLAYBACK_TRACK_24H  2026-07-29 .. 2026-07-30
    FMS_CONGESTION_SEG      2026-07-15 .. 2026-07-30

against a weighbridge extract ending 2026-07-08/11. Choosing on truck count
alone optimises the wrong axis: the point of the exercise is to prove the JOIN,
and a day with 500 trucks and zero GPS proves nothing.

So this counts rows per day in EVERY source table the deep dive needs, and
picks the day with the widest simultaneous coverage. If no day has both
weighbridge trips and haul-truck GPS, that is the headline finding and it gets
reported rather than worked around.

READ ONLY.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

OUT = os.path.join(ROOT, "reports", "day_coverage.json")


def conn(db):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=900, charset="LATIN1")


# Each entry: label -> (database, SQL returning day + a count column).
# Epoch-ms columns are converted in SQL so every source lands on a real date.
SOURCES = {
    "weighbridge_trips": ("WBN_DATABASE", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT TRUCK_ID) AS trucks
        FROM HAULAGE_IWIP_CLEAN
        WHERE [DATE] IS NOT NULL AND FIRST_WB_TIME IS NOT NULL
          AND SECOND_WB_TIME IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "waiting_time": ("WBN_DATABASE", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT EQUIPMENT_ID) AS trucks
        FROM WAITING_TIME WHERE [DATE] IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "hourly_activities": ("WBN_DATABASE", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT TRUCK_ID) AS trucks
        FROM EQUIPMENTS_HOURLY_ACTIVITIES WHERE [DATE] IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "hourly_status": ("WBN_DATABASE", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT ID_EQ) AS trucks
        FROM EQUIPMENTS_HOURLY_STATUS WHERE [DATE] IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "day_works": ("WBN_DATABASE", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT UNIT_ID) AS trucks
        FROM DAY_WORKS WHERE [DATE] IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "hrm_supervision": ("FMS_DB", """
        SELECT CAST([DATE] AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT EQUIPMENT_ID) AS trucks
        FROM FMS_HRM_SUPERVISION WHERE [DATE] IS NOT NULL
        GROUP BY CAST([DATE] AS date)"""),
    "gps_track_data": ("FMS_DB", """
        SELECT CAST(FETCH_DATE AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT plateNumber) AS trucks
        FROM FMS_PLAYBACK_TRACK_DATA
        GROUP BY CAST(FETCH_DATE AS date)"""),
    "gps_historical": ("FMS_DB", """
        SELECT CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS d,
               COUNT(*) AS n, COUNT(DISTINCT PLATE) AS trucks
        FROM FMS_GPS_Historical
        GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date)"""),
    "gps_24h": ("FMS_DB", """
        SELECT CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS d,
               COUNT(*) AS n, COUNT(DISTINCT PLATE) AS trucks
        FROM FMS_PLAYBACK_TRACK_24H
        GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date)"""),
    "geofence_visits": ("FMS_DB", """
        SELECT CAST(DATEADD(second, ENTER_TS/1000, '1970-01-01') AS date) AS d,
               COUNT(*) AS n, COUNT(DISTINCT UNIT_ID) AS trucks
        FROM FMS_GEOFENCE_VISITS WHERE UNIT_TYPE = 'Haul Truck'
        GROUP BY CAST(DATEADD(second, ENTER_TS/1000, '1970-01-01') AS date)"""),
    "congestion_seg": ("FMS_DB", """
        SELECT CAST(DATEADD(second, HOUR_TS/1000, '1970-01-01') AS date) AS d,
               COUNT(*) AS n, 0 AS trucks
        FROM FMS_CONGESTION_SEG
        GROUP BY CAST(DATEADD(second, HOUR_TS/1000, '1970-01-01') AS date)"""),
    "truck_assignments": ("FMS_DB", """
        SELECT CAST(PLAN_DATE AS date) AS d, COUNT(*) AS n,
               COUNT(DISTINCT TRUCK) AS trucks
        FROM FMS_TRUCK_ASSIGNMENTS WHERE PLAN_DATE IS NOT NULL
        GROUP BY CAST(PLAN_DATE AS date)"""),
}


def main() -> None:
    frames, meta = {}, {}
    conns = {}
    for label, (db, sql) in SOURCES.items():
        if db not in conns:
            conns[db] = conn(db)
        try:
            d = pd.read_sql(sql, conns[db])
            d["d"] = pd.to_datetime(d["d"])
            d = d[d["d"] > "2020-01-01"]          # drop 1899 sentinel dates
            frames[label] = d.set_index("d")
            meta[label] = {"days": int(len(d)),
                           "range": [str(d["d"].min())[:10], str(d["d"].max())[:10]],
                           "rows": int(d["n"].sum())}
            print("%-20s %5d days  %s -> %s  %s rows"
                  % (label, len(d), meta[label]["range"][0],
                     meta[label]["range"][1], "{:,}".format(meta[label]["rows"])),
                  flush=True)
        except Exception as e:                               # noqa: BLE001
            meta[label] = {"error": str(e)[:140]}
            print("%-20s ERROR %s" % (label, str(e)[:90]), flush=True)
    for c in conns.values():
        c.close()

    # One row per day, one column per source: the coverage matrix.
    mat = pd.DataFrame({k: v["n"] for k, v in frames.items()}).fillna(0).astype(int)
    mat = mat.sort_index()
    mat["sources_present"] = (mat > 0).sum(axis=1)

    gps_cols = [c for c in ("gps_track_data", "gps_historical", "gps_24h",
                            "congestion_seg", "geofence_visits") if c in mat]
    mat["gps_sources"] = (mat[gps_cols] > 0).sum(axis=1)

    print("\n=== days where weighbridge trips AND haul-truck GPS both exist ===")
    if "weighbridge_trips" in mat:
        both = mat[(mat["weighbridge_trips"] > 0) & (mat["gps_sources"] > 0)]
        print("%d such days" % len(both))
        if len(both):
            top = both.sort_values(["sources_present", "weighbridge_trips"],
                                   ascending=False).head(15)
            print(top[["weighbridge_trips", "gps_sources", "sources_present"]
                      + [c for c in gps_cols if c in top]].to_string())
    print("\n=== best coverage overall (any source mix) ===")
    print(mat.sort_values(["sources_present", "weighbridge_trips"],
                          ascending=False).head(12).to_string())

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_meta": meta,
        "matrix": json.loads(mat.reset_index().to_json(orient="records",
                                                       date_format="iso")),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
