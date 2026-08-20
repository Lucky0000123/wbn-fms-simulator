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
        c_road_obs = _pctile(tputs, 0.95) or 0
        # c_road from ROAD GEOMETRY, not historical throughput: the p95 of
        # observed trips/hr is the FLEET's demand, not the road's capacity
        # (BLB>POS 14 max fleet ever was 79 trucks -> obs 15 trucks/hr, but
        # the road passes far more). Headway by haul length; two-way mining
        # road = 2 lanes. Observed p95 only serves as a floor when geometry
        # data is missing (owner fix, 2026-08-20).
        # Classify by MEASURED free-flow cycle, not chainage distance: the
        # BLB spur arithmetic makes BLB>POS 14 look like a 41 km haul when
        # its measured cycle (105 min) is that of a short road.
        if t_free < 150:
            _headway = 20.0     # short haul: slow, tight spacing
            c_road = max(2 * 3600.0 / _headway, c_road_obs)
        elif t_free < 200:
            _headway = 30.0     # medium haul
            c_road = max(2 * 3600.0 / _headway, c_road_obs)
        else:
            # LONG corridor (TF/KR to coast): one shared two-way road that
            # genuinely saturates - geometry headway (160/hr) never binds
            # and would predict zero congestion at 771 trucks. Owner-
            # validated congestion levels (2026-08-20: 385 DT ~1.3-1.5,
            # 771 DT ~0.8-1.2 trips/DT) calibrate to ~1.7x the observed
            # p95 throughput: real capacity sits above what the modest
            # historical fleets demanded, below free-flow geometry.
            c_road = max(20.0, c_road_obs * 1.7)
        # fleet envelope
        dts = [r["trucks"] for r in rs]
        # v/c points for BPR fit. v must be DEMAND flow (exogenous):
        # N trucks each wanting a trip every t_free minutes = N/(t_free/60)
        # trucks/hr. Served flow (trips/hr) is endogenous - busy days have
        # both high flow and low gaps, which fits a NEGATIVE alpha (measured
        # 2026-08-20: all-route R2 < 0 with served flow).
        # Standard BPR parameters (owner fix 2026-08-20): the per-route LSQ
        # fit produced junk in both regimes (alpha 0.8-4.0 with negative R2)
        # because observed v/c barely varies within history. alpha=0.15,
        # beta=4 is the literature standard; the 3x free-flow cap in the
        # predictor bounds the extreme tail.
        alpha, beta, r2, nfit = 0.15, 4.0, None, 0
        sd = sum(sds) / len(sds) if sds else None
        # UTILIZATION: fraction of the shift a truck is actively cycling.
        # Measured trips/truck x mean gap / 720. Median over day-shifts.
        # This is the effective-cycle vs weigh-to-weigh distinction in
        # AGENTS.md: gaps say ~134 min but trucks do ~2.3 trips/shift on
        # KR>POS 12 - the rest of the shift is breaks/changeover/assignment.
        rec = {
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

    # ── Anchor utilization to the DISPATCH day-rate basis ────────────────
    # Gap-based cycles only sample trucks that did >=2 trips in a shift - a
    # fast-biased subset. The rest of the app (legacy model, plan tab, DB
    # reports) counts trips/DT on the NB_DT day basis. Re-derive utilization
    # so the hybrid, run at the route's MEDIAN fleet and faces, reproduces
    # the dispatch day rate exactly - physics keeps the SHAPE (loaders,
    # knee, BPR), dispatch anchors the LEVEL. One basis, two engines agree.
    json.dump({"generated_at": "tmp", "global": {}, "routes": routes_out},
              open(PARAMS_PATH, "w"))
    import importlib
    from congestion import config as ccfg, predictor as cpred
    ccfg._cache["data"] = None
    for route, rec in routes_out.items():
        rate = rec.get("day_rate")
        if not rate:
            continue
        n_ref = rec.get("n_trucks_ref") or 30
        faces = [r.get("faces") or 1 for r in byr[route]]
        f_ref = max(1, round(_pctile(sorted(faces), 0.5)))
        rec["n_loaders"] = f_ref
        rec["utilization"] = 1.0
        json.dump({"generated_at": "tmp", "global": {}, "routes": routes_out},
                  open(PARAMS_PATH, "w"))
        ccfg._cache["data"] = None
        try:
            p = cpred.predict(route, n_ref, f_ref)
            raw = p["trips_per_DT_per_day"]
            if raw > 0:
                rec["utilization"] = round(min(1.0, max(0.2, rate / raw)), 3)
        except Exception as exc:  # noqa: BLE001
            rec["utilization"] = 0.7
    ccfg._cache["data"] = None

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
