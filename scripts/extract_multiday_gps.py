"""Priority 2: scale GPS extraction across every day that CAN be extracted.

Day X (2026-07-19) was not an arbitrary choice - it turns out to be the best of a
very small set. Measured ceiling: GPS and haulage coexist on only 4 calendar days
(2026-07-15, 16, 18, 19), because GPS retention is a rolling few days while the
RIM haulage feed lags behind it. The richest GPS day in the database, 2026-07-29
with 859,198 fixes, is unusable: the only trucks with haulage rows that day are 46
SALES third-party vehicles, none of which carry telematics.

So "scaling" here means extracting all 4 usable days and pooling them, which is
the honest maximum rather than an impressive-sounding number.

Writes data/multiday_gps_trips.csv, one row per (day, truck) with fixes and trips,
so downstream segment work can use the pooled set instead of a single day.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import pandas as pd
import simulator_api as sim

ROOT = "/Users/lucky/wbn-fms-simulator"
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
GPS_TABLES = ("FMS_GPS_Historical", "FMS_PLAYBACK_TRACK_24H")


def conn(db):
    import pymssql
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def gps_day_plates(f) -> pd.DataFrame:
    """(day, plate, fixes) across both GPS tables."""
    frames = []
    for t in GPS_TABLES:
        q = ("SELECT CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS day,"
             " UPPER(LTRIM(RTRIM(PLATE))) AS truck, COUNT(*) AS fixes"
             " FROM [%s] WHERE PLATE IS NOT NULL"
             " AND LAT NOT BETWEEN -0.0001 AND 0.0001"
             " GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date),"
             " UPPER(LTRIM(RTRIM(PLATE)))" % t)
        d = pd.read_sql(q, f)
        d["gps_table"] = t
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def haul_day_trucks(w) -> pd.DataFrame:
    """(day, truck, trips, wmt) from both haulage tables, July onwards."""
    frames = []
    for t in ("HAULAGE_IWIP_CLEAN", "HAULAGE"):
        q = ("SELECT CAST([DATE] AS date) AS day,"
             " UPPER(LTRIM(RTRIM(TRUCK_ID))) AS truck,"
             " COUNT(*) AS trips, SUM(WMT) AS wmt, MAX(CONTRACTOR) AS contractor"
             " FROM [%s] WHERE TRUCK_ID IS NOT NULL AND WMT > 0"
             " AND CAST([DATE] AS date) >= '2026-07-01'"
             " GROUP BY CAST([DATE] AS date), UPPER(LTRIM(RTRIM(TRUCK_ID)))" % t)
        d = pd.read_sql(q, w)
        d["haul_table"] = t
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def main():
    f, w = conn("FMS_DB"), conn("WBN_DATABASE")
    g = gps_day_plates(f)
    h = haul_day_trucks(w)
    for d in (g, h):
        d["day"] = pd.to_datetime(d["day"])

    print("GPS: %d (day,plate) rows over %d days" % (len(g), g.day.nunique()))
    print("haulage: %d (day,truck) rows over %d days" % (len(h), h.day.nunique()))

    # Pool duplicate rows so a truck appearing in both source tables counts once.
    ga = g.groupby(["day", "truck"], as_index=False).fixes.sum()
    ha = h.groupby(["day", "truck"], as_index=False).agg(
        trips=("trips", "sum"), wmt=("wmt", "sum"),
        contractor=("contractor", "max"))
    j = ga.merge(ha, on=["day", "truck"], how="inner")
    print("\nusable (day,truck) pairs with BOTH GPS and haulage: %d" % len(j))

    if len(j):
        print("\nby day:")
        by = j.groupby("day").agg(trucks=("truck", "nunique"),
                                  fixes=("fixes", "sum"),
                                  trips=("trips", "sum"), wmt=("wmt", "sum"))
        for r in by.sort_index().itertuples():
            print("   %s  %3d trucks  %8s fixes  %4d trips  %8.0f t"
                  % (r.Index.date(), r.trucks, "{:,}".format(int(r.fixes)),
                     int(r.trips), r.wmt))
        print("\npooled total: %d truck-days, %s fixes, %d trips, %.0f t"
              % (len(j), "{:,}".format(int(j.fixes.sum())),
                 int(j.trips.sum()), j.wmt.sum()))
        print("vs Day X alone: %d truck-days"
              % int((j.day == pd.Timestamp("2026-07-19")).sum()))
        print("\nby contractor: %s" % j.contractor.value_counts().to_dict())

        j2 = j.copy()
        j2["day"] = j2.day.dt.date
        j2.sort_values(["day", "truck"]).to_csv(
            os.path.join(DATA, "multiday_gps_trips.csv"), index=False)
        print("\nwrote data/multiday_gps_trips.csv")

        summary = {
            "usable_days": [str(d.date()) for d in sorted(j.day.unique())],
            "truck_days": int(len(j)),
            "trucks_distinct": int(j.truck.nunique()),
            "gps_fixes": int(j.fixes.sum()),
            "trips": int(j.trips.sum()),
            "wmt": float(j.wmt.sum()),
            "day_x_truck_days": int((j.day == pd.Timestamp("2026-07-19")).sum()),
            "by_contractor": {str(k): int(v)
                              for k, v in j.contractor.value_counts().items()},
            "ceiling_reason": (
                "GPS retention is a rolling window of days while the RIM haulage "
                "feed lags behind it, so only 4 calendar days carry both. The "
                "richest GPS day (2026-07-29, 859,198 fixes) is unusable because "
                "its only haulage rows are 46 SALES third-party trucks, which "
                "carry no telematics."),
        }
        io.open(os.path.join(REPORTS, "multiday_gps_summary.json"), "w",
                encoding="utf-8").write(json.dumps(summary, indent=2))
        print("wrote reports/multiday_gps_summary.json")


if __name__ == "__main__":
    main()
