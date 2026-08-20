#!/usr/bin/env python
"""Calibrate the hybrid congestion model from WBN_DATABASE history.

Fits, per route (>= 30 day-shifts):
  mu / load_min      loader service time  <- p10 of per-truck trip gaps (the
                     fastest turnarounds bound fixed time; queue is on top)
  t_free_min         free-flow cycle      <- p10 of day-shift mean gaps
  alpha, beta        BPR parameters       <- least squares on
                     mean_gap = t_free * (1 + alpha*(v/c)^beta) day-shifts
  c_road_trucks_hr   <- p95 of observed trucks/hr throughput
  cycle_sd_min       <- mean per-day-shift gap SD (bunching input)
  obs_dt_min/max     <- observed fleet envelope (uncertainty bands)
  payload_t, day_rate, day_trips_cap <- from the dispatch snapshot (legacy cmp)

Writes data/congestion_params.json. Uses data/congestion_dayshift.json if
present (extracted 2026-08-20); pass --refresh to re-pull from the DB.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

DAYSHIFT_PATH = os.path.join(ROOT, "data", "congestion_dayshift.json")
PARAMS_PATH = os.path.join(ROOT, "data", "congestion_params.json")


def _pctile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    i = p * (len(xs) - 1)
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] * (1 - (i - lo)) + xs[hi] * (i - lo)


def refresh_dayshift():
    """Re-extract per-(route, date, shift) stats from HAULAGE_CLEAN."""
    from load_fms_env import load_fms_env
    load_fms_env()
    import pymssql
    conn = pymssql.connect(server=os.environ["FMS_DB_HOST"], user=os.environ["FMS_DB_USER"],
                           password=os.environ["FMS_DB_PASS"], database="WBN_DATABASE",
                           login_timeout=8, timeout=300)
    cur = conn.cursor()
    cur.execute("""
WITH t AS (
  SELECT DATE, SHIFT, TRUCK_ID, ORIGIN_ID,
    CASE WHEN ORIGIN_AREA LIKE '%[_]TF[_]%' OR ORIGIN_AREA LIKE 'TF%' OR ORIGIN_AREA LIKE '%TOFU%' THEN 'TF'
         WHEN ORIGIN_AREA LIKE '%[_]KR%' OR ORIGIN_AREA LIKE 'KR%' OR ORIGIN_AREA LIKE '%KRENE%' THEN 'KR'
         WHEN ORIGIN_AREA LIKE '%BLB%' THEN 'BLB'
         WHEN ORIGIN_AREA LIKE '%CBB%' THEN 'CBB'
         ELSE NULL END AS OPIT,
    CASE WHEN DESTINATION_AREA LIKE 'HUAFEI%' THEN 'HUAFEI'
         WHEN DESTINATION_AREA IN ('FENI','FENI A') THEN 'FENI KM0'
         ELSE DESTINATION_AREA END AS DAREA,
    CAST(DATE AS datetime) + CAST(TIME_LOADED AS datetime) AS TL
  FROM HAULAGE_CLEAN
  WHERE DATE >= '2026-01-01' AND TIME_LOADED IS NOT NULL
),
g AS (
  SELECT OPIT, DAREA, DATE, SHIFT, TRUCK_ID, ORIGIN_ID,
    DATEDIFF(minute, LAG(TL) OVER (PARTITION BY DATE, SHIFT, TRUCK_ID, OPIT, DAREA ORDER BY TL), TL) AS gap_min
  FROM t WHERE OPIT IS NOT NULL AND DAREA IS NOT NULL
)
SELECT OPIT, DAREA, DATE, SHIFT,
  COUNT(DISTINCT TRUCK_ID),
  COUNT(*) + COUNT(DISTINCT TRUCK_ID),
  AVG(CASE WHEN gap_min BETWEEN 20 AND 480 THEN CAST(gap_min AS float) END),
  STDEV(CASE WHEN gap_min BETWEEN 20 AND 480 THEN CAST(gap_min AS float) END),
  MIN(CASE WHEN gap_min BETWEEN 20 AND 480 THEN gap_min END),
  COUNT(DISTINCT ORIGIN_ID)
FROM g
GROUP BY OPIT, DAREA, DATE, SHIFT
HAVING COUNT(*) >= 5
""")
    out = []
    for r in cur.fetchall():
        out.append({"route": "%s>%s" % (r[0], r[1]), "date": str(r[2]), "shift": r[3],
                    "trucks": r[4], "trips": r[5],
                    "mean_gap_min": round(r[6], 1) if r[6] else None,
                    "sd_gap_min": round(r[7], 1) if r[7] else None,
                    "min_gap_min": r[8], "faces": r[9]})
    conn.close()
    json.dump(out, open(DAYSHIFT_PATH, "w"))
    return out


def fit_bpr(points, t_free, c_link):
    """Least-squares alpha, beta for mean_gap = t_free*(1+alpha*(v/c)^beta).

    Grid over beta (1..8), closed-form alpha per beta, keep best SSE.
    Only day-shifts with v/c >= 0.15 inform the fit (below that the penalty
    is in the noise)."""
    pts = [(v / c_link, g) for v, g in points if c_link > 0 and g and g > 0]
    pts = [(x, g / t_free - 1.0) for x, g in pts if x >= 0.15 and g / t_free >= 0.9]
    if len(pts) < 10:
        return None, None, None, len(pts)
    best = None
    for beta in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0]:
        num = sum((x ** beta) * y for x, y in pts)
        den = sum((x ** beta) ** 2 for x, y in pts)
        if den <= 0:
            continue
        alpha = max(0.0, num / den)
        sse = sum((y - alpha * (x ** beta)) ** 2 for x, y in pts)
        if best is None or sse < best[2]:
            best = (alpha, beta, sse)
    if best is None:
        return None, None, None, len(pts)
    alpha, beta, sse = best
    ym = sum(y for _, y in pts) / len(pts)
    sst = sum((y - ym) ** 2 for _, y in pts)
    r2 = (1 - sse / sst) if sst > 0 else 0.0
    return alpha, beta, r2, len(pts)


def main():
    refresh = "--refresh" in sys.argv
    if refresh or not os.path.isfile(DAYSHIFT_PATH):
        print("extracting day-shift stats from WBN_DATABASE ...")
        rows = refresh_dayshift()
    else:
        rows = json.load(open(DAYSHIFT_PATH))
    print("day-shift records: %d" % len(rows))

    # dispatch snapshot for payload + legacy params
    disp = {}
    try:
        snap = json.load(open(os.path.join(ROOT, "data", "pr_snapshot.json")))
        agg = defaultdict(lambda: [0.0, 0.0, 0.0])
        dayagg = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        for r in snap["rows"]:
            k = "%s>%s" % (r["o"], r["dd"])
            agg[k][0] += r["trips"]; agg[k][1] += r["t"]; agg[k][2] += r["dt"]
            da = dayagg[k][r["d"]]
            da[0] += r["dt"]; da[1] += r["trips"]
        for k, (tr, t, dt) in agg.items():
            days = dayagg[k]
            effs = sorted(v[1] / v[0] for v in days.values() if v[0] > 0)
            n = len(effs)
            core = effs[int(n * .2):n - int(n * .2)] if n >= 10 else effs
            disp[k] = {
                "payload_t": round(t / tr, 1) if tr else None,
                "day_rate": round(sum(core) / len(core), 3) if core else None,
                "day_trips_cap": round(max(v[1] for v in days.values())) if days else None,
                "obs_dt_min": round(min(v[0] for v in days.values())) if days else None,
                "obs_dt_max": round(max(v[0] for v in days.values())) if days else None,
            }
    except Exception as exc:  # noqa: BLE001
        print("dispatch snapshot unavailable (%s) - legacy comparison fields skipped" % exc)

    byr = defaultdict(list)
    for r in rows:
        byr[r["route"]].append(r)

    routes_out = {}
    print("\n%-14s %5s %7s %7s %7s %6s %6s %8s %6s %6s" % (
        "route", "days", "t_free", "load", "c_road", "alpha", "beta", "R2(fit)", "nfit", "sd"))
    for route, rs in sorted(byr.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < 30:
            continue
        gaps = [r["mean_gap_min"] for r in rs if r["mean_gap_min"]]
        mins = [r["min_gap_min"] for r in rs if r.get("min_gap_min")]
        sds = [r["sd_gap_min"] for r in rs if r.get("sd_gap_min")]
        if len(gaps) < 20:
            continue
        # Free-flow cycle: p25 of day-shift mean gaps. p10 was too hot - it
        # predicts everyone at the fastest decile; p25 is 'a good uncongested
        # shift'. The queue/BPR terms add the congestion on top.
        t_free = _pctile(gaps, 0.25)
        # loader service time: p10 of the fastest observed turnarounds minus
        # haul time is unobservable here; use fixed 5 min unless faces data
        # suggests otherwise. mu comes from load_min.
        load_min = 5.0
        # throughput trucks/hr: trips per shift-hour
        tputs = [r["trips"] / 12.0 for r in rs if r["trips"]]
        c_road = _pctile(tputs, 0.95)
        # fleet envelope
        dts = [r["trucks"] for r in rs]
        # v/c points for BPR fit. v must be DEMAND flow (exogenous):
        # N trucks each wanting a trip every t_free minutes = N/(t_free/60)
        # trucks/hr. Served flow (trips/hr) is endogenous - busy days have
        # both high flow and low gaps, which fits a NEGATIVE alpha (measured
        # 2026-08-20: all-route R2 < 0 with served flow).
        pts = [(r["trucks"] / (t_free / 60.0), r["mean_gap_min"]) for r in rs
               if r["trucks"] and r["mean_gap_min"]]
        alpha, beta, r2, nfit = fit_bpr(pts, t_free, c_road)
        sd = sum(sds) / len(sds) if sds else None
        # UTILIZATION: fraction of the shift a truck is actively cycling.
        # Measured trips/truck x mean gap / 720. Median over day-shifts.
        # This is the effective-cycle vs weigh-to-weigh distinction in
        # AGENTS.md: gaps say ~134 min but trucks do ~2.3 trips/shift on
        # KR>POS 12 - the rest of the shift is breaks/changeover/assignment.
        utils = []
        for r in rs:
            if r.get("mean_gap_min") and r.get("trucks") and r.get("trips"):
                u = (r["trips"] / r["trucks"]) * r["mean_gap_min"] / 720.0
                if 0.05 <= u <= 1.5:
                    utils.append(min(1.0, u))
        utilization = _pctile(utils, 0.5) if utils else 0.7
        rec = {
            "utilization": round(utilization, 3),
            "t_free_obs_min": round(t_free, 1),
            "load_min": load_min,
            "c_road_trucks_hr": round(c_road, 1) if c_road else None,
            "alpha": round(alpha, 4) if alpha is not None else None,
            "beta": beta,
            "bpr_fit_r2": round(r2, 3) if r2 is not None else None,
            "bpr_fit_n": nfit,
            "cycle_sd_min": round(sd, 1) if sd else None,
            "n_trucks_ref": round(_pctile(dts, 0.5)) if dts else None,
            "n_dayshifts": len(rs),
            # calibrated loaded speed so the physics t_free matches the
            # OBSERVED free-flow cycle (fixed times subtracted):
        }
        # back-solve speed from observed free-flow cycle
        from congestion import physics as ph
        o, _, d = route.partition(">")
        dist = ph.route_distance_km(o, d)
        if dist and t_free:
            t_road = max(5.0, t_free - (load_min + 1.0 + 2.0))
            # loaded + empty (empty 1.25x faster): t = 60d/v + 60d/(1.25v)
            v = (60.0 * dist * (1 + 1 / 1.25)) / t_road
            rec["speed_loaded_kmh"] = round(v, 1)
            rec["distance_km"] = round(dist, 1)
        rec.update(disp.get(route) or {})
        routes_out[route] = rec
        print("%-14s %5d %7.0f %7.1f %7.1f %6s %6s %8s %6d %6s" % (
            route, len(rs), t_free, load_min, c_road or 0,
            rec["alpha"], rec["beta"], rec["bpr_fit_r2"], nfit, rec["cycle_sd_min"]))

    out = {
        "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "WBN_DATABASE.dbo.HAULAGE_CLEAN 2026-01-01.. (day-shift trip gaps)",
        "method": "t_free=p10(day-shift mean gap); c_road=p95(trips/hr); "
                  "alpha,beta=grid LSQ on gap=t_free*(1+a*(v/c)^b); "
                  "speed back-solved so physics matches observed free flow",
        "global": {},
        "routes": routes_out,
    }
    os.makedirs(os.path.dirname(PARAMS_PATH), exist_ok=True)
    json.dump(out, open(PARAMS_PATH, "w"), indent=1)
    print("\nwrote %s (%d routes)" % (PARAMS_PATH, len(routes_out)))


if __name__ == "__main__":
    main()
