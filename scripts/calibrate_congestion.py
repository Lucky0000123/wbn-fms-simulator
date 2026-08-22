#!/usr/bin/env python
"""Calibrate the hybrid congestion model from WBN_DATABASE history.

Fits, per route (>= 30 day-shifts):
  t_free_min         free-flow cycle      <- p25 of day-shift mean gaps
  alpha, beta        BPR parameters       <- literature 0.15 / 4.0
                     (historical v/c range is too narrow for LSQ)
  c_road_trucks_hr   <- geometry: n_lanes_loaded * 3600 / headway_s
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


def contractor_ratios():
    """Per-(route, contractor) matched-day trips/DT ratio vs the pooled route.

    Owner (2026-08-21): contractors on one road need their own baselines
    from HISTORY. Raw per-contractor averages are fleet-size-confounded
    (RIM ran ~140 trucks/day on TF while SMA ran ~58), so the ratio is
    computed per DAY — contractor trips/DT divided by the same day's
    all-contractor trips/DT on the same route, i.e. identical road
    traffic on both sides — then medianed. Ticket basis on both sides of
    the division, so the two-240s basis problem cancels. Shrunk toward
    1.0 (K=20 days) and bounded [0.6, 1.4]; fewer than 30 matched days
    -> no override, pooled baseline stands."""
    from load_fms_env import load_fms_env
    load_fms_env()
    import pymssql
    conn = pymssql.connect(server=os.environ["FMS_DB_HOST"], user=os.environ["FMS_DB_USER"],
                           password=os.environ["FMS_DB_PASS"], database="WBN_DATABASE",
                           login_timeout=8, timeout=300)
    cur = conn.cursor()
    cur.execute("""
WITH t AS (
  SELECT DATE, CONTRACTOR, TRUCK_ID,
    CASE WHEN ORIGIN_AREA LIKE '%[_]TF[_]%' OR ORIGIN_AREA LIKE 'TF%' OR ORIGIN_AREA LIKE '%TOFU%' THEN 'TF'
         WHEN ORIGIN_AREA LIKE '%[_]KR%' OR ORIGIN_AREA LIKE 'KR%' OR ORIGIN_AREA LIKE '%KRENE%' THEN 'KR'
         WHEN ORIGIN_AREA LIKE '%BLB%' THEN 'BLB'
         WHEN ORIGIN_AREA LIKE '%CBB%' THEN 'CBB'
         ELSE NULL END AS OPIT,
    CASE WHEN DESTINATION_AREA LIKE 'HUAFEI%' THEN 'HUAFEI'
         WHEN DESTINATION_AREA IN ('FENI','FENI A') THEN 'FENI KM0'
         ELSE DESTINATION_AREA END AS DAREA
  FROM HAULAGE_CLEAN
  WHERE DATE >= '2025-06-01'
)
SELECT OPIT, DAREA, DATE, CONTRACTOR, COUNT(*), COUNT(DISTINCT TRUCK_ID)
FROM t WHERE OPIT IS NOT NULL AND DAREA IS NOT NULL AND CONTRACTOR IS NOT NULL
GROUP BY OPIT, DAREA, DATE, CONTRACTOR
HAVING COUNT(DISTINCT TRUCK_ID) >= 5
""")
    per_day = defaultdict(dict)      # (route, date) -> {contractor: tpd}
    for opit, darea, date, cont, trips, dts in cur.fetchall():
        route = "%s>%s" % (opit, darea)
        per_day[(route, str(date))][str(cont).strip().upper()] = trips / float(dts)
    conn.close()
    samples = defaultdict(list)      # (route, contractor) -> [ratio]
    for (route, _d), by_c in per_day.items():
        if len(by_c) < 2:
            continue                 # need company on the road that day
        pooled = sum(by_c.values()) / len(by_c)
        if pooled <= 0:
            continue
        for cont, tpd in by_c.items():
            samples[(route, cont)].append(tpd / pooled)
    out = defaultdict(dict)
    K = 20.0
    for (route, cont), vals in samples.items():
        if len(vals) < 30:
            continue
        med = _pctile(sorted(vals), 0.5)
        shrunk = (len(vals) * med + K * 1.0) / (len(vals) + K)
        out[route][cont] = {"ratio": round(max(0.6, min(1.4, shrunk)), 3),
                            "n_matched_days": len(vals)}
    return out


def gps_corridor_speeds():
    """Measured GPS road speeds per origin corridor, split by direction.

    data/congestion_seg_by_dir.csv (FMS_CONGESTION_SEG aggregate): 'down'
    chainage = LOADED (verified 100.0% of loaded corridor hauls run
    down-chainage, AGENTS.md), 'up' = empty return. Weighted by travel
    observations. Used as a CROSS-CHECK on road_free_min, not as pricing —
    corridor-mean speed over the prefix is not the route's exact path.
    """
    path = os.path.join(ROOT, "data", "congestion_seg_by_dir.csv")
    if not os.path.isfile(path):
        return {}
    import csv
    agg = defaultdict(lambda: [0.0, 0.0])   # (prefix, dir) -> [sum speed*w, sum w]
    with open(path) as fh:
        for row in csv.DictReader(fh):
            seg = row["SEG_ID"].split(" KM")[0].strip()
            try:
                spd = float(row["speed_kmh"])
                w = float(row["trav_n"] or 0)
            except ValueError:
                continue
            if spd > 0 and w > 0:
                a = agg[(seg, row["DIR"])]
                a[0] += spd * w
                a[1] += w
    out = {}
    for (seg, d), (sw, w) in agg.items():
        out.setdefault(seg, {})[d] = sw / w
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
    gps_speeds = gps_corridor_speeds()
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
        # c_road from ROAD GEOMETRY. v in BPR is loaded-direction flow
        # (one pass per cycle), so a two-way road is 1 loaded lane.
        # Headway is a documented following gap (config), never inverted
        # from a target trips/DT. Short vs long is chainage, not cycle time.
        from congestion.config import DEFAULTS as _CFG
        from congestion import physics as ph
        from congestion import bpr as bprmod
        o, _, d = route.partition(">")
        dist = ph.route_distance_km(o, d)
        c_road, n_lanes, headway_s = bprmod.geometry_c_road(
            dist,
            n_lanes_loaded=int(_CFG["n_lanes_loaded"]),
            headway_s=float(_CFG["headway_s"]),
            headway_s_short=float(_CFG["headway_s_short"]),
            long_haul_km=float(_CFG["long_haul_km"]))
        implied_km = ph.implied_one_way_km(t_free)
        measured = (o, d) in ph.MEASURED_HAUL_KM
        chainage_suspect = bool(
            dist and implied_km and not measured and (
                dist / implied_km > 2.0 or implied_km / dist > 2.0))
        # fleet envelope
        dts = [r["trucks"] for r in rs]
        # Historical v/c barely varies, so per-route LSQ on BPR is unidentified
        # (negative R2 on both served flow and demand flow). Literature
        # defaults; the 3x free-flow cap in the predictor bounds the tail.
        alpha, beta, r2, nfit = 0.15, 4.0, None, 0
        sd = sum(sds) / len(sds) if sds else None
        rec = {
            "t_free_obs_min": round(t_free, 1),
            "load_min": load_min,
            "c_road_trucks_hr": round(c_road, 1) if c_road else None,
            "c_road_obs_p95": round(c_road_obs, 1) if c_road_obs else None,
            "headway_s": round(headway_s, 1),
            "n_lanes_loaded": n_lanes,
            "alpha": round(alpha, 4) if alpha is not None else None,
            "beta": beta,
            "bpr_fit_r2": round(r2, 3) if r2 is not None else None,
            "bpr_fit_n": nfit,
            "cycle_sd_min": round(sd, 1) if sd else None,
            "n_trucks_ref": round(_pctile(dts, 0.5)) if dts else None,
            "n_dayshifts": len(rs),
        }
        # back-solve speed from observed free-flow cycle
        if dist and t_free:
            t_road = max(5.0, t_free - (load_min + 1.0 + 2.0))
            v = (60.0 * dist * (1 + 1 / 1.25)) / t_road
            rec["speed_loaded_kmh"] = round(v, 1)
            rec["distance_km"] = round(dist, 1)
            rec["distance_source"] = ph.HAUL_KM_SOURCE.get(
                (o, d), "chainage stick")
        if implied_km:
            rec["implied_distance_km"] = round(implied_km, 1)
        rec["chainage_suspect"] = chainage_suspect
        # ── road running time (owner, 2026-08-21) ────────────────────────
        # The physical constraint BPR multiplies. Weighbridge stamps cannot
        # split the legs here (TIME_LOADED/TIME_EMPTY are weigh events;
        # measured: TF routes have no usable TIME_EMPTY, BLB>POS 14 shows
        # 90 min "loaded leg" on a 6.7 km haul — see AGENTS.md weigh-to-weigh
        # note), so road_free = observed UNCONGESTED cycle (p25 of day-shift
        # trip gaps) minus the fixed ops. GPS corridor speeds × measured km
        # give the independent cross-check column.
        ops_min = load_min + 1.0 + 2.0            # load + spot + dump
        rec["ops_min"] = round(ops_min, 1)
        rec["road_free_min"] = round(max(5.0, t_free - ops_min), 1)
        gps = gps_speeds.get(o)
        if gps and dist and gps.get("down") and gps.get("up"):
            rec["gps_road_min"] = round(60.0 * dist / gps["down"]
                                        + 60.0 * dist / gps["up"], 1)
        rec.update(disp.get(route) or {})
        routes_out[route] = rec
        flag = " SUSPECT" if chainage_suspect else ""
        print("%-14s %5d %7.0f %7.1f %7.1f %6s %6s %8s %6d %6s%s" % (
            route, len(rs), t_free, load_min, c_road or 0,
            rec["alpha"], rec["beta"], rec["bpr_fit_r2"], nfit,
            rec["cycle_sd_min"], flag))

    # ── Anchor OVERHEAD-PER-TRIP to the DISPATCH day-rate basis ──────────
    # (owner, 2026-08-21 — replaces the utilization anchor.) The old
    # trips = U*1440/cycle treated non-productive time as a FIXED share of
    # the day, so once the congested cycle exceeded U*1440 the model said a
    # dispatched truck cannot finish ONE trip in 24 h — physically
    # impossible. Overhead (breaks, dispatch wait, shift change, refuel) is
    # attached to TRIPS, not to the clock:
    #     trips = 1440 / (cycle + overhead_per_trip)
    # cycle = road_congested + ops + queue + bunching (productive time).
    # Anchor: run the model at the route's MEDIAN fleet and faces with
    # overhead 0 -> cyc_ref; overhead = 1440/day_rate - cyc_ref, so the
    # hybrid still reproduces the dispatch day rate exactly at the anchor —
    # physics keeps the SHAPE, dispatch anchors the LEVEL, and trips can
    # never fall below 1440/(3*road_free + ops + queue_cap + overhead).
    json.dump({"generated_at": "tmp", "global": {}, "routes": routes_out},
              open(PARAMS_PATH, "w"))
    from congestion import config as ccfg, predictor as cpred
    ccfg._cache["data"] = None
    try:
        crat = contractor_ratios()
        print("contractor matched-day ratios: %d routes" % len(crat))
    except Exception as exc:  # noqa: BLE001
        print("WARN contractor ratios unavailable (%s) — pooled baselines only" % exc)
        crat = {}
    for route, rec in routes_out.items():
        rate = rec.get("day_rate")
        if not rate:
            continue
        n_ref = rec.get("n_trucks_ref") or 30
        faces = [r.get("faces") or 1 for r in byr[route]]
        f_ref = max(1, round(_pctile(sorted(faces), 0.5)))
        rec["n_loaders"] = f_ref
        rec["overhead_per_trip_min"] = 0.0
        json.dump({"generated_at": "tmp", "global": {}, "routes": routes_out},
                  open(PARAMS_PATH, "w"))
        ccfg._cache["data"] = None
        try:
            p = cpred.predict(route, n_ref, f_ref)
            cyc_ref = p["cycle_time_minutes"]
            if cyc_ref and cyc_ref > 0:
                ovh = 1440.0 / rate - cyc_ref
                if ovh < 0:
                    print("  NOTE %s: modeled cycle at ref fleet (%.0f min) already "
                          "slower than dispatch day rate implies (%.0f min) — "
                          "overhead clamped to 0" % (route, cyc_ref, 1440.0 / rate))
                rec["overhead_per_trip_min"] = round(max(0.0, ovh), 1)
                # kept for reference only — predict() no longer reads it
                rec["utilization"] = round(min(1.0, max(0.2, rate * cyc_ref / 1440.0)), 3)
                # per-contractor baselines: pooled day_rate x matched-day
                # ratio, overhead re-anchored on the same pooled cyc_ref so
                # only the contractor LEVEL differs, never the road physics
                for cont, cr in (crat.get(route) or {}).items():
                    rate_c = rate * cr["ratio"]
                    if rate_c <= 0:
                        continue
                    rec.setdefault("contractors", {})[cont] = {
                        "ratio": cr["ratio"],
                        "n_matched_days": cr["n_matched_days"],
                        "day_rate": round(rate_c, 3),
                        "overhead_per_trip_min": round(max(0.0, 1440.0 / rate_c - cyc_ref), 1),
                    }
        except Exception as exc:  # noqa: BLE001
            print("  WARN %s: anchor failed (%s) — overhead left at 0" % (route, exc))
    ccfg._cache["data"] = None
    ovhs = [r["overhead_per_trip_min"] for r in routes_out.values()
            if r.get("overhead_per_trip_min")]
    overhead_default = round(_pctile(sorted(ovhs), 0.5), 1) if ovhs else 240.0

    from congestion.config import DEFAULTS as _CFG
    out = {
        "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "WBN_DATABASE.dbo.HAULAGE_CLEAN 2026-01-01.. (day-shift trip gaps)",
        "method": {
            "trips_formula": "1440 / (road_congested + ops + queue + bunching + overhead_per_trip)",
            "road_free": "p25 of day-shift trip gaps minus ops (weighbridge stamps cannot "
                         "split the legs — measured 2026-08-21); gps_road_min = measured km / "
                         "GPS corridor speeds by direction, cross-check only",
            "ops": "loader service 5 + spot 1 + dump 2 min",
            "overhead_per_trip": "anchored: 1440/dispatch day_rate - modeled cycle at median "
                                 "fleet+faces (exact at the anchor; clamped >= 0)",
            "bpr": "applied to road_free only, capped at 3x",
            "alpha": "literature default 0.15 (insufficient v/c variation for LSQ fit)",
            "beta": "literature default 4.0 (insufficient v/c variation for LSQ fit)",
            "t_free": "p25 of day-shift mean gaps",
            "c_road": "geometry: n_lanes_loaded * 3600 / headway_s",
            "headway_s_long": _CFG["headway_s"],
            "headway_s_short": _CFG["headway_s_short"],
            "long_haul_km": _CFG["long_haul_km"],
            "n_lanes_loaded": _CFG["n_lanes_loaded"],
            "loaders": "proportional: round(DT / historical trucks-per-loader)",
            "segments": "stick routes price road time per shared-corridor segment "
                        "(congestion/segments.py): one geometry capacity per segment, "
                        "combined fleet from segment_fleet when the caller supplies the plan",
            "contractors": "matched same-day trips/DT ratio vs pooled route (>=30 days, "
                           "both >=5 trucks, EB-shrunk K=20, bounded 0.6-1.4); overhead "
                           "re-anchored per contractor on the pooled cycle",
            "utilization": "LEGACY reference only — predict() no longer reads it",
        },
        "global": {
            "n_lanes_loaded": _CFG["n_lanes_loaded"],
            "headway_s": _CFG["headway_s"],
            "headway_s_short": _CFG["headway_s_short"],
            "long_haul_km": _CFG["long_haul_km"],
            # uncalibrated routes (no dispatch day_rate) use the median
            # calibrated overhead so the new formula applies everywhere
            "overhead_per_trip_min": overhead_default,
        },
        "routes": routes_out,
    }
    os.makedirs(os.path.dirname(PARAMS_PATH), exist_ok=True)
    json.dump(out, open(PARAMS_PATH, "w"), indent=1)
    print("\nwrote %s (%d routes)" % (PARAMS_PATH, len(routes_out)))
    print("\n%-14s %8s %8s %7s %10s %6s %s" % (
        "route", "chainage", "implied", "ratio", "c_road", "hdwy", "class"))
    for route, rec in sorted(routes_out.items()):
        dist = rec.get("distance_km")
        imp = rec.get("implied_distance_km")
        ratio = (dist / imp) if (dist and imp) else None
        if dist is None:
            klass = "unknown"
        elif dist >= _CFG["long_haul_km"]:
            klass = "LONG"
        else:
            klass = "short"
        flag = "CHAINAGE SUSPECT" if rec.get("chainage_suspect") else ""
        print("%-14s %8s %8s %7s %10.1f %6.0f %s %s" % (
            route,
            "—" if dist is None else ("%.1f" % dist),
            "—" if imp is None else ("%.1f" % imp),
            "—" if ratio is None else ("%.2f" % ratio),
            rec.get("c_road_trucks_hr") or 0,
            rec.get("headway_s") or 0, klass, flag))


if __name__ == "__main__":
    main()
