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
# The predicted trips-per-truck-day must land within this FRACTION of observed.
#
# Compared as MEAN to MEAN, not against the median. The simulator predicts a
# rate, which is a mean-like quantity; trips per truck-day is right-skewed
# (median 2.0, mean 2.83), so comparing a rate to a median understates it by
# 50%+ and would fail a correct model.
TOLERANCE_FRAC = 0.20
# Measured shifts worked per truck-day: 86,392 truck-days on one shift and
# 84,479 on two, so 1.494 rather than the 2.0 a naive reading would assume.
DAY_PER_SHIFT = 1.494

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


def _served_prediction() -> float:
    """What the simulator actually predicts, per truck per DAY.

    Queries plan_simulator rather than reimplementing its formula, so this gate
    fails if the endpoint regresses even when the lookup table is fine. Averaged
    over the routes with the most history, and doubled because the observation is
    per calendar day while the simulator predicts per 12-hour shift.
    """
    import pandas as _pd
    import plan_simulator as ps
    ps.reset_cache()
    r = ps._routes()
    if r is None or r.empty:
        return float("nan")
    top = r.sort_values("shifts", ascending=False).head(12)
    preds = []
    for x in top.itertuples():
        res = ps.simulate({"plans": [{"route": x.route, "source": x.source,
                                      "destination": x.destination,
                                      "n_trucks": 10}]})
        y = res["results"][0]
        if "trips_per_shift_per_truck" in y:
            preds.append(float(y["trips_per_shift_per_truck"]))
    return (sum(preds) / len(preds) * DAY_PER_SHIFT) if preds else float("nan")


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
    obs_mean = float(obs["trips"].mean())

    import plan_simulator as ps
    shift = float(ps.DEFAULT_SHIFT_MIN)
    avail = float(ps.DEFAULT_AVAILABILITY)
    # The DEFECTIVE formula, kept for comparison: shift / weigh-to-weigh cycle.
    defective = (shift * 0.85) / wb
    # What the simulator ACTUALLY serves now. Ask it, rather than reimplementing
    # its arithmetic here, so this gate cannot pass while the endpoint regresses.
    served = _served_prediction()
    correct = shift / s2s                    # true start-to-start cycle

    print("consecutive trip pairs: %s" % "{:,}".format(len(d)))
    print("(note: trips-per-truck-DAY is compared, so a two-shift day gives ~2x")
    print(" the per-shift figure; the tolerance accounts for that.)")
    print("weigh-to-weigh cycle (served) : %.1f min" % wb)
    print("start-to-start cycle (true)   : %.1f min" % s2s)
    print("understatement factor         : %.2fx" % (s2s / wb))
    print()
    print("observed trips per truck-day     : mean %.3f (median %.2f)"
          % (obs_mean, obs_med))
    print("SERVED endpoint predicts (per day): %.3f  (%+.1f%% vs mean)"
          % (served, 100 * (served - obs_mean) / obs_mean))
    print("old defective formula would give  : %.3f  (%+.1f%% vs mean)"
          % (defective * DAY_PER_SHIFT,
             100 * (defective * DAY_PER_SHIFT - obs_mean) / obs_mean))
    print("shift / true start-to-start cycle : %.2f" % correct)
    print()
    print("per-route ratio spread (routes with >=500 pairs):")
    g = (d.groupby(["o", "d"])
          .agg(n=("s2s_min", "size"), wb=("wb_min", "median"),
               s2s=("s2s_min", "median")).reset_index())
    g = g[g["n"] >= 500].copy()
    g["ratio"] = (g["s2s"] / g["wb"]).round(2)
    print("   min %.2fx  median %.2fx  max %.2fx across %d routes"
          % (g["ratio"].min(), g["ratio"].median(), g["ratio"].max(), len(g)))

    ok = abs(served - obs_mean) / obs_mean <= TOLERANCE_FRAC
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": [start, end],
        "pairs": int(len(d)),
        "weigh_to_weigh_median_min": round(wb, 1),
        "start_to_start_median_min": round(s2s, 1),
        "understatement_factor": round(s2s / wb, 2),
        "observed_trips_per_truck_day_mean": round(obs_mean, 3),
        "observed_trips_per_truck_day_median": round(obs_med, 2),
        "day_per_shift_factor": DAY_PER_SHIFT,
        "served_endpoint_prediction_per_day": round(served, 2),
        "old_defective_formula_prediction": round(defective, 2),
        "true_cycle_prediction": round(correct, 2),
        "route_ratio_min": float(g["ratio"].min()) if len(g) else None,
        "route_ratio_max": float(g["ratio"].max()) if len(g) else None,
        "tolerance_frac": TOLERANCE_FRAC,
        "served_error_pct": round(100 * (served - obs_mean) / obs_mean, 1),
        "served_within_tolerance": bool(ok),
        "verdict": ("PASS: the served endpoint reproduces observed trips "
                    "within %.0f%%" % (100 * TOLERANCE_FRAC)
                    if ok else
                    "FAIL: the served endpoint mispredicts observed trips by "
                    "%+.1f%%; see reports/CRITICAL_cycle_time_defect.md"
                    % (100 * (served - obs_mean) / obs_mean)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print("\n%s" % payload["verdict"])
    print("wrote %s" % OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
