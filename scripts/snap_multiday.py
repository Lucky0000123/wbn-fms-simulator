"""Pool segment speeds across all 4 usable days, not just Day X.

Reuses snap_gps's own functions rather than reimplementing the geometry, so the
pooled result is directly comparable with the single-day output that was already
cross-validated against FMS_CONGESTION_SEG at r=+0.920.

The point is to find out whether 4 days buys enough observations for Priority 3's
speed-density fit. If it does not, that is the finding.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
sys.path.insert(0, "/Users/lucky/wbn-fms-simulator/scripts")
import pandas as pd
import simulator_api as sim
import snap_gps as sg
import extract_day as ed

ROOT = "/Users/lucky/wbn-fms-simulator"
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
DAYS = ["2026-07-15", "2026-07-16", "2026-07-18", "2026-07-19"]


def main():
    w, f = ed.conn("WBN_DATABASE"), ed.conn("FMS_DB")
    ch = sg.load_chainage_cached()

    segs, snaps, meta = [], [], []
    for day in DAYS:
        print("\n" + "=" * 62)
        print("DAY %s" % day)
        trips = ed.extract_trips(w, day)
        if trips.empty:
            print("  no trips; skipping")
            continue
        trucks = set(trips.truck.dropna().astype(str))
        gps = ed.extract_gps(f, day, trucks)
        if gps.empty:
            print("  no GPS; skipping")
            continue
        gps["ts"] = pd.to_datetime(gps["ts"], utc=True)
        # pymssql hands back DECIMAL as Decimal objects, which land as object
        # dtype and break numpy ufuncs inside snap().
        for c in ("LAT", "LNG", "SPEED", "COURSE", "DISTANCE"):
            if c in gps.columns:
                gps[c] = pd.to_numeric(gps[c], errors="coerce")
        gps = gps[gps.LAT.notna() & gps.LNG.notna()]
        gps = sg.snap(gps, ch)
        seg = sg.segment_speeds(gps, trips)
        print("  snapped %s fixes (%.1f%% on road); %d segment observations"
              % ("{:,}".format(len(gps)), 100 * gps.on_road.mean(), len(seg)))
        if not seg.empty:
            seg["day"] = day
            segs.append(seg)
        gps["day"] = day
        snaps.append(gps)
        meta.append({"day": day, "trips": int(len(trips)),
                     "gps_fixes": int(len(gps)),
                     "on_road_pct": round(100 * float(gps.on_road.mean()), 1),
                     "segment_obs": int(len(seg))})

    if not segs:
        print("\nno segment observations on any day")
        return

    allseg = pd.concat(segs, ignore_index=True)
    pd.concat(snaps, ignore_index=True).to_csv(
        os.path.join(DATA, "multiday_gps_snapped.csv"), index=False)
    allseg.to_csv(os.path.join(DATA, "multiday_segment_speeds.csv"), index=False)

    print("\n" + "=" * 62)
    print("POOLED ACROSS %d DAYS" % len(meta))
    print("segment observations: %d (Day X alone: %d)"
          % (len(allseg), int((allseg.day == "2026-07-19").sum())))
    print("distinct trips: %d, trucks: %d, segments: %d"
          % (allseg.trip_id.nunique(), allseg.truck_id.nunique(),
             allseg.seg.nunique()))

    full = allseg[allseg.is_partial_traverse == 0] if \
        "is_partial_traverse" in allseg else allseg
    print("full transits: %d of %d" % (len(full), len(allseg)))
    if len(full):
        print("full-transit speed: median %.1f km/h" % full.avg_speed_kmh.median())

    print("\nper segment/direction (full transits only):")
    if len(full):
        piv = (full.groupby(["seg", "direction"])
               .agg(speed=("avg_speed_kmh", "mean"), n=("avg_speed_kmh", "size"),
                    trucks=("truck_id", "nunique"), days=("day", "nunique"))
               .reset_index().sort_values("n", ascending=False))
        print(piv.head(20).round(1).to_string(index=False))
        print("\nsegment/direction cells with n>=5: %d of %d"
              % (int((piv.n >= 5).sum()), len(piv)))

    summary = {"days": meta,
               "pooled_segment_obs": int(len(allseg)),
               "day_x_segment_obs": int((allseg.day == "2026-07-19").sum()),
               "pooled_full_transits": int(len(full)),
               "distinct_trips": int(allseg.trip_id.nunique()),
               "distinct_trucks": int(allseg.truck_id.nunique()),
               "distinct_segments": int(allseg.seg.nunique())}
    io.open(os.path.join(REPORTS, "multiday_segment_summary.json"), "w",
            encoding="utf-8").write(json.dumps(summary, indent=2))
    print("\nwrote data/multiday_segment_speeds.csv and the summary json")


if __name__ == "__main__":
    main()
