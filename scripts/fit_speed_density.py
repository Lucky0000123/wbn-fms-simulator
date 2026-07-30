"""Priority 3: fit the speed-density relationship from FMS_CONGESTION_SEG.

This is the source the brief's premise needed. Structure, per segment per
direction per hour:
  SUM_SPD / FIX_N  -> mean speed over that hour
  TRUCK_N          -> distinct trucks on the segment that hour, i.e. density
  SUM_TRAV_MS / TRAV_N -> mean traverse time, an independent speed measure

36,046 rows over ~2 weeks, versus the 19 observations my own GPS snapping could
produce. My snapping already agrees with this table at r=+0.920, which is what
licenses using it.

The brief warned that truck-count variation might be too thin to identify a
congestion effect. That is now a measurable question rather than a guess, and the
answer gets reported either way.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import numpy as np
import pandas as pd
import simulator_api as sim

ROOT = "/Users/lucky/wbn-fms-simulator"
DATA, REPORTS = os.path.join(ROOT, "data"), os.path.join(ROOT, "reports")


def conn(db):
    import pymssql
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def main():
    f = conn("FMS_DB")
    q = """SELECT HOUR_TS, SEG_ID, DIR, SUM_SPD, FIX_N, TRUCK_N,
                  SUM_TRAV_MS, TRAV_N
           FROM FMS_CONGESTION_SEG WHERE FIX_N > 0"""
    d = pd.read_sql(q, f)
    print("rows with fixes: %s" % "{:,}".format(len(d)))

    for c in ("SUM_SPD", "SUM_TRAV_MS"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["hour"] = pd.to_datetime(d.HOUR_TS.astype("int64"), unit="ms", utc=True)
    d["speed_kmh"] = d.SUM_SPD / d.FIX_N
    d["trav_s"] = np.where(d.TRAV_N > 0, d.SUM_TRAV_MS / d.TRAV_N / 1000.0, np.nan)
    d["road"] = d.SEG_ID.astype(str).str.split(" ").str[0]

    print("window: %s -> %s (%.1f days)"
          % (d.hour.min(), d.hour.max(),
             (d.hour.max() - d.hour.min()).total_seconds() / 86400))
    print("segments: %d, roads: %d, hours: %d"
          % (d.SEG_ID.nunique(), d.road.nunique(), d.hour.nunique()))
    d.to_csv(os.path.join(DATA, "congestion_seg_hourly.csv"), index=False)

    print("\n=== is there enough density variation to identify an effect? ===")
    print("TRUCK_N: min %d  median %d  p95 %d  max %d"
          % (d.TRUCK_N.min(), d.TRUCK_N.median(),
             d.TRUCK_N.quantile(.95), d.TRUCK_N.max()))
    print("distinct TRUCK_N values: %d" % d.TRUCK_N.nunique())
    # Within-segment variation is what identifies the effect; a segment observed
    # at only one density tells us nothing.
    v = d.groupby(["SEG_ID", "DIR"]).TRUCK_N.agg(
        n_densities="nunique", n_rows="size", lo="min", hi="max")
    v["spread"] = v.hi - v.lo
    print("segment/direction cells: %d" % len(v))
    print("cells with >=2 distinct densities : %d" % int((v.n_densities >= 2).sum()))
    print("cells with >=5 distinct densities : %d" % int((v.n_densities >= 5).sum()))
    print("median within-cell density spread : %.1f trucks" % v.spread.median())

    print("\n=== the fit: speed vs density, WITHIN segment/direction ===")
    # A pooled regression would mostly measure which segments are fast, so
    # centre both variables within each segment/direction cell.
    keep = d.merge(v[v.n_densities >= 3].reset_index()[["SEG_ID", "DIR"]],
                   on=["SEG_ID", "DIR"], how="inner")
    keep = keep[keep.speed_kmh.between(1, 80) & (keep.FIX_N >= 5)]
    print("usable rows (>=3 densities, >=5 fixes, 1..80 km/h): %s"
          % "{:,}".format(len(keep)))
    g = keep.groupby(["SEG_ID", "DIR"])
    keep["spd_c"] = keep.speed_kmh - g.speed_kmh.transform("mean")
    keep["den_c"] = keep.TRUCK_N - g.TRUCK_N.transform("mean")

    x, y = keep.den_c.values, keep.spd_c.values
    n = len(x)
    if n > 30 and np.std(x) > 0:
        b = float(np.sum(x * y) / np.sum(x * x))
        yhat = b * x
        ss = float(np.sum((y - yhat) ** 2))
        st = float(np.sum(y ** 2))
        r2 = 1 - ss / st if st > 0 else float("nan")
        se = float(np.sqrt(ss / (n - 1) / np.sum(x * x)))
        t = b / se if se > 0 else float("nan")
        r = float(np.corrcoef(x, y)[0, 1])
        print()
        print("  within-cell slope : %+.4f km/h per extra truck" % b)
        print("  std error         : %.4f   t = %+.1f" % (se, t))
        print("  correlation       : %+.4f" % r)
        print("  R2 (within)       : %.4f" % r2)
        print("  n                 : %s" % "{:,}".format(n))
        print()
        sig = abs(t) > 2
        if sig and b < 0:
            print("  -> SIGNIFICANT AND NEGATIVE: more trucks on a segment means")
            print("     slower travel. Congestion is identifiable in this data.")
        elif sig and b > 0:
            print("  -> significant but POSITIVE, which is not congestion. More")
            print("     likely reverse causation: trucks are dispatched to")
            print("     segments that are already flowing well.")
        else:
            print("  -> NOT significant. Density does not explain speed here.")

        print("\n=== effect size in operational terms ===")
        for extra in (1, 3, 5, 10):
            print("   +%2d trucks on a segment -> %+.2f km/h" % (extra, b * extra))
        base = keep.speed_kmh.mean()
        print("   mean segment speed %.1f km/h, so +5 trucks is a %.1f%% change"
              % (base, 100 * b * 5 / base))

        print("\n=== cross-check with the independent traverse-time measure ===")
        kt = keep[keep.trav_s.notna() & keep.trav_s.between(1, 3600)]
        if len(kt) > 30:
            kt = kt.copy()
            gt = kt.groupby(["SEG_ID", "DIR"])
            kt["trav_c"] = kt.trav_s - gt.trav_s.transform("mean")
            kt["den_c2"] = kt.TRUCK_N - gt.TRUCK_N.transform("mean")
            x2, y2 = kt.den_c2.values, kt.trav_c.values
            if np.std(x2) > 0:
                b2 = float(np.sum(x2 * y2) / np.sum(x2 * x2))
                r2c = float(np.corrcoef(x2, y2)[0, 1])
                print("  traverse-time slope: %+.3f s per extra truck (r=%+.3f, n=%s)"
                      % (b2, r2c, "{:,}".format(len(kt))))
                print("  sign agreement with the speed fit: %s"
                      % ("YES - slower speed and longer traverse both point the "
                         "same way" if (b < 0) == (b2 > 0) else
                         "NO - the two measures disagree, so treat with caution"))
        else:
            print("  too few rows with traverse times to cross-check")

        out = {"rows_total": int(len(d)), "rows_used": int(n),
               "window_days": round((d.hour.max() - d.hour.min()).total_seconds()
                                    / 86400, 1),
               "segments": int(d.SEG_ID.nunique()),
               "cells_with_3plus_densities": int((v.n_densities >= 3).sum()),
               "within_cell_slope_kmh_per_truck": round(b, 4),
               "t_stat": round(t, 2), "correlation": round(r, 4),
               "within_r2": round(r2, 4), "significant": bool(sig)}
        io.open(os.path.join(REPORTS, "speed_density_fit.json"), "w",
                encoding="utf-8").write(json.dumps(out, indent=2))
        print("\nwrote reports/speed_density_fit.json")
    else:
        print("insufficient variation to fit")


if __name__ == "__main__":
    main()
