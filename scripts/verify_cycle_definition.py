"""verify_cycle_definition.py — is the simulator dividing by the right cycle?

WHY THIS EXISTS
plan_simulator computes trips_per_truck = (shift_minutes * availability) / cycle,
where cycle is the median FIRST_WB_TIME -> SECOND_WB_TIME interval. That interval
ends at the second weigh; the next trip's interval starts at its own first weigh,
so everything in between (return empty, queue, refuel, breaks) is invisible to it.

Measured over 438,992 consecutive trip pairs, the true start-to-start cycle is
240.1 min against a weigh-to-weigh median of 76.9 min: a 3.12x understatement,
which makes the simulator overpredict production by roughly 2.7x.

This script re-derives that from the database so the claim is reproducible rather
than a number in a document, and so it can be re-run after any fix as a gate.

READ ONLY. Exits non-zero when the served cycle definition would mispredict
observed trips beyond tolerance, so it works as a regression check.
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

OUT = os.path.join(ROOT, "reports", "cycle_definition_check.json")
# A one-month window by default. The LEAD() window function over the full
# 560k-row history takes many minutes and is prone to dying with the VPN; one
# month is 438,992/7 pairs, which is ample for a median, and --start/--end are
# available when the full-history figure is wanted.
START, END = "2026-06-01", "2026-07-09"
# A start-to-start gap beyond 12 h spans a shift break; under 5 min is a mis-scan.
MIN_GAP_MIN, MAX_GAP_MIN = 5, 720
# Predicted trips per truck-shift must land within this of the observed median.
TOLERANCE_TRIPS = 1.0

CYCLE_SQL = """
WITH x AS (
  SELECT UPPER(LTRIM(RTRIM(TRUCK_ID))) t, ORIGIN_AREA o, DESTINATION_AREA d,
         FIRST_WB_TIME f, SECOND_WB_TIME s,
         LEAD(FIRST_WB_TIME) OVER (PARTITION BY UPPER(LTRIM(RTRIM(TRUCK_ID)))
                                   ORDER BY FIRST_WB_TIME) nf
  FROM HAULAGE_IWIP_CLEAN
  WHERE TRUCK_ID IS NOT NULL AND FIRST_WB_TIME IS NOT NULL
    AND SECOND_WB_TIME IS NOT NULL AND [DATE] BETWEEN '{a}' AND '{b}'
)
SELECT o, d, DATEDIFF(second, f, s)/60.0 AS wb_min,
       DATEDIFF(second, f, nf)/60.0 AS s2s_min
FROM x WHERE nf IS NOT NULL
"""

TRIPS_SQL = """
SELECT CAST([DATE] AS date) dd, UPPER(LTRIM(RTRIM(TRUCK_ID))) t, COUNT(*) trips
FROM HAULAGE_IWIP_CLEAN
WHERE TRUCK_ID IS NOT NULL AND FIRST_WB_TIME IS NOT NULL
  AND SECOND_WB_TIME IS NOT NULL AND [DATE] BETWEEN '{a}' AND '{b}'
GROUP BY CAST([DATE] AS date), UPPER(LTRIM(RTRIM(TRUCK_ID)))
"""


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    args = ap.parse_args()
    start, end = args.start, args.end
    print("window: %s .. %s" % (start, end))
    c = pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                        password=sim._DB["password"], database="WBN_DATABASE",
                        login_timeout=10, timeout=1800, charset="LATIN1")
    try:
        d = pd.read_sql(CYCLE_SQL.format(a=start, b=end), c)
        obs = pd.read_sql(TRIPS_SQL.format(a=start, b=end), c)
    finally:
        c.close()

    for col in ("wb_min", "s2s_min"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d[d["s2s_min"].between(MIN_GAP_MIN, MAX_GAP_MIN)
          & d["wb_min"].between(1, MAX_GAP_MIN)]

    wb = float(d["wb_min"].median())
    s2s = float(d["s2s_min"].median())
    obs_med = float(obs["trips"].median())

    import plan_simulator as ps
    shift = float(ps.DEFAULT_SHIFT_MIN)
    avail = float(ps.DEFAULT_AVAILABILITY)
    served = (shift * avail) / wb            # what the simulator predicts today
    correct = shift / s2s                    # true cycle, no allowance needed

    print("consecutive trip pairs: %s" % "{:,}".format(len(d)))
    print("weigh-to-weigh cycle (served) : %.1f min" % wb)
    print("start-to-start cycle (true)   : %.1f min" % s2s)
    print("understatement factor         : %.2fx" % (s2s / wb))
    print()
    print("observed trips per truck-day  : %.2f" % obs_med)
    print("served formula predicts       : %.2f  (error %+.2f)"
          % (served, served - obs_med))
    print("true-cycle formula predicts   : %.2f  (error %+.2f)"
          % (correct, correct - obs_med))
    print()
    print("per-route ratio spread (routes with >=500 pairs):")
    g = (d.groupby(["o", "d"])
          .agg(n=("s2s_min", "size"), wb=("wb_min", "median"),
               s2s=("s2s_min", "median")).reset_index())
    g = g[g["n"] >= 500].copy()
    g["ratio"] = (g["s2s"] / g["wb"]).round(2)
    print("   min %.2fx  median %.2fx  max %.2fx across %d routes"
          % (g["ratio"].min(), g["ratio"].median(), g["ratio"].max(), len(g)))

    ok = abs(served - obs_med) <= TOLERANCE_TRIPS
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": [start, end],
        "pairs": int(len(d)),
        "weigh_to_weigh_median_min": round(wb, 1),
        "start_to_start_median_min": round(s2s, 1),
        "understatement_factor": round(s2s / wb, 2),
        "observed_trips_per_truck_day": round(obs_med, 2),
        "served_formula_prediction": round(served, 2),
        "true_cycle_prediction": round(correct, 2),
        "route_ratio_min": float(g["ratio"].min()) if len(g) else None,
        "route_ratio_max": float(g["ratio"].max()) if len(g) else None,
        "tolerance_trips": TOLERANCE_TRIPS,
        "served_formula_within_tolerance": bool(ok),
        "verdict": ("PASS: served cycle definition reproduces observed trips"
                    if ok else
                    "FAIL: the served formula mispredicts observed trips by "
                    "%+.2f per truck-day; see reports/CRITICAL_cycle_time_"
                    "defect.md" % (served - obs_med)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print("\n%s" % payload["verdict"])
    print("wrote %s" % OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
