"""Section-resolved plan pricing (owner, 2026-08-21).

"When we make a plan you have to see how many trucks are moving in each
window — each section of the route — and what speed that section allows.
The whole speed determined by one trips/DT only is wrong."

price_plan() prices a WHOLE day's plan at once: every route's road time is
the sum of its corridor sections, each section carrying the load of every
plan row that crosses it (chainage overlap, foreign/IWIP rows included —
their trucks occupy the road) at that section's MEASURED speed, degraded
by BPR at the section's v/c against its MEASURED peak throughput.

Reality anchors, in order:
  - section speeds: Jul+ corridor GPS, loaded direction
    (plan_corridor_hours by_section);
  - section capacity: median peak TRUCK_N/hour per section from
    data/congestion_seg_by_dir.csv (loaded direction);
  - route free total: each route's per-section free times are RESCALED so
    their sum equals the calibrated dispatch road_free_min — dispatch
    truth holds at zero traffic, GPS shapes how it distributes over
    sections;
  - ops / overhead / loaders queue: same calibration predict() uses, so
    the two agree at the anchor and differ only where section loads say
    the corridor is hotter or cooler than the route-level v/c guess.

The fixed point (times -> flows -> BPR -> times) is damped and
convergence-checked; flows use the PRODUCTIVE cycle (demand-flow
doctrine), never cycle+overhead.
"""
from __future__ import annotations

import math
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from . import physics, queueing
from .config import route_params

import plan_analogues as pa
import plan_shared_flow as psf

ALPHA, BETA = 0.15, 4.0
EMPTY_SPEED_FACTOR = 1.25          # site GPS: empty runs ~1.25x loaded
FALLBACK_SPEED_KMH = 25.0
FALLBACK_CAP_HR = 60.0             # 60 s headway geometry when unmeasured


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _route_span(route):
    o, _, d = str(route).partition(">")
    ok, dk = pa.node_km(o), pa.node_km(d)
    if ok is None or dk is None:
        return None
    return (min(ok, dk), max(ok, dk))


def _section_profile(route, speeds):
    """[(label, km, speed_kmh)] for the chainage overlap + spur remainder."""
    span = _route_span(route)
    o, _, d = str(route).partition(">")
    dist = physics.route_distance_km(o, d)
    segs = []
    covered = 0.0
    if span:
        for label, slo, shi in pa.SECTIONS:
            ov = min(span[1], shi) - max(span[0], slo)
            if ov > 0:
                segs.append([label, ov, float(speeds.get(label) or FALLBACK_SPEED_KMH)])
                covered += ov
    if dist and dist - covered > 0.5:
        # origin spur / off-mainline remainder (BLB spur, HUAFEI branch):
        # no section GPS here, so it rides at the route's calibrated speed
        # and congests only with the route's own flow.
        p = route_params(route)
        spd = p.get("speed_loaded_kmh") or FALLBACK_SPEED_KMH
        segs.append(["%s spur" % (o or route), dist - covered, float(spd)])
    return segs


def price_plan(rows, rain_mm=0.0):
    """rows: [{route, dt, loaders?, foreign?}] — one whole day, one road network."""
    speeds = psf._section_speeds_kmh()
    caps = psf._load_section_capacity_tph()
    # one road, one figure: rows sharing a route key share the road AND its
    # faces, so merge them before pricing (owner: "see it as a complete
    # one-day plan, not one row")
    merged = {}
    for r in rows or []:
        route = str(r.get("route") or "").replace("→", ">").strip()
        try:
            dt = float(r.get("dt") or 0)
        except (TypeError, ValueError):
            continue
        if ">" not in route or dt <= 0:
            continue
        g = merged.setdefault(route, {"route": route, "dt": 0.0, "loaders": 0,
                                      "foreign": bool(r.get("foreign"))})
        g["dt"] += dt
        try:
            g["loaders"] += int(r.get("loaders") or 0)
        except (TypeError, ValueError):
            pass
    plan = []
    for r in merged.values():
        route, dt = r["route"], r["dt"]
        p = route_params(route)
        segs = _section_profile(route, speeds)
        if not segs:
            continue
        # free per-section loaded minutes, anchored to calibrated road_free
        t_free = [60.0 * km / max(1.0, spd) for _, km, spd in segs]
        raw_road = sum(t_free) * (1.0 + 1.0 / EMPTY_SPEED_FACTOR)
        anchor = p.get("road_free_min")
        scale = (float(anchor) / raw_road) if (_finite(anchor) and anchor > 0 and raw_road > 0) else 1.0
        wet = 1.0 + (0.15 if rain_mm >= 10 else (0.06 if rain_mm >= 1 else 0.0))
        loaders = r.get("loaders")
        if not (_finite(loaders) and loaders >= 1):
            ref_t, ref_l = p.get("n_trucks_ref"), p.get("n_loaders")
            tpl = (float(ref_t) / float(ref_l)) if (p.get("calibrated") and ref_t and ref_l) else 15.0
            loaders = max(1, round(dt / tpl))
        ovh = p.get("overhead_per_trip_min")
        if not (_finite(ovh) and ovh >= 0):
            ovh = 240.0
        plan.append({
            "route": route, "dt": dt, "loaders": int(loaders),
            "foreign": bool(r.get("foreign")),
            "segs": segs, "t_free": [t * scale * wet for t in t_free],
            "ops": float(p["ops_min"]) if _finite(p.get("ops_min")) else 8.0,
            "overhead": float(ovh),
            "load_min": float(p.get("load_min") or 5.0),
            "sd": p.get("cycle_sd_min"), "n_ref": p.get("n_trucks_ref") or 30,
            "k_bunch": float(p.get("k_bunch") or 0.03),
            "sh": float(p.get("hours_per_shift") or 12.0),
            "day_minutes": float(p.get("shifts_per_day") or 2) * float(p.get("hours_per_shift") or 12.0) * 60.0,
            "cyc": None, "trips": None,
        })
    if not plan:
        return {"ok": False, "error": "no priceable rows"}

    # seed with free-flow trips, then damped fixed point over the whole plan
    for r in plan:
        road0 = sum(r["t_free"]) * (1.0 + 1.0 / EMPTY_SPEED_FACTOR)
        r["cyc"] = road0 + r["ops"]
        r["trips"] = r["day_minutes"] / (r["cyc"] + r["overhead"])
    converged = False
    sec_state = {}
    for _ in range(60):
        flows = {}
        for r in plan:
            f = r["dt"] * 60.0 / max(1.0, r["cyc"])     # productive-cycle demand flow
            for (label, km, spd) in r["segs"]:
                flows[label] = flows.get(label, 0.0) + f
        worst = 0.0
        sec_state = {}
        for r in plan:
            road = 0.0
            road_hist = 0.0
            for (label, km, spd), tf in zip(r["segs"], r["t_free"]):
                cap = caps.get(label) or FALLBACK_CAP_HR
                vc = flows.get(label, 0.0) / max(1.0, cap)
                # baseline: this route ALONE on the window — the calibrated
                # route-level model (backtest R2 0.926) already prices a
                # route's own traffic, so the section model charges only the
                # EXTRA drag from other plan rows sharing the window
                vc_h = (r["dt"] * 60.0 / max(1.0, r["cyc"])) / max(1.0, cap)
                pen = min(3.0, 1.0 + ALPHA * (vc ** BETA))
                pen_h = min(3.0, 1.0 + ALPHA * (vc_h ** BETA))
                road += tf * pen + tf / EMPTY_SPEED_FACTOR   # empty leg uncongested
                road_hist += tf * pen_h + tf / EMPTY_SPEED_FACTOR
                st = sec_state.setdefault(label, {"km": round(km, 1), "flow_hr": 0.0,
                                                  "cap_hr": round(cap, 1), "vc": 0.0,
                                                  "vc_own": round(vc_h, 2),
                                                  "speed_free_kmh": round(spd, 1),
                                                  "trucks": 0.0})
                st["flow_hr"] = round(flows.get(label, 0.0), 1)
                st["vc"] = round(vc, 2)
            q = queueing.erlang_c(r["dt"], r["cyc"] / 60.0, r["load_min"], r["loaders"], r["sh"])
            bunch = 0.0
            if _finite(r["sd"]) and r["sd"] and r["n_ref"]:
                bunch = min(3.0 * r["k_bunch"] * float(r["sd"]),
                            r["k_bunch"] * float(r["sd"]) * (r["dt"] / float(r["n_ref"])))
            cyc_new = road + r["ops"] + q["wq_min"] + bunch
            cyc_next = r["cyc"] + 0.5 * (cyc_new - r["cyc"])
            worst = max(worst, abs(cyc_next - r["cyc"]))
            r["cyc"] = cyc_next
            r["road"] = road
            r["road_hist"] = road_hist
            r["wq"] = q["wq_min"]
            r["trips"] = r["day_minutes"] / (r["cyc"] + r["overhead"])
            # same route with ONLY its own trucks on its windows — the basis
            # the calibrated route-level model prices; trips/trips_own is the
            # shared-road correction the curve should carry for THIS plan
            r["trips_hist"] = r["day_minutes"] / (road_hist + r["ops"] + q["wq_min"]
                                                  + bunch + r["overhead"])
        if worst < 0.05:
            converged = True
            break
    # trucks per section (the owner's "how many trucks in each window")
    for r in plan:
        for (label, km, spd) in r["segs"]:
            if label in sec_state:
                sec_state[label]["trucks"] += r["dt"]
    for st in sec_state.values():
        st["trucks"] = round(st["trucks"])
        if st["vc"] > 0:
            st["speed_cong_kmh"] = round(st["speed_free_kmh"] / min(3.0, 1.0 + ALPHA * (st["vc"] ** BETA)), 1)
    out_routes = {}
    for r in plan:
        out_routes.setdefault(r["route"], []).append(r)
    routes = {}
    for route, rs in out_routes.items():
        # rows on one route share the road; report the shared figure once
        r0 = max(rs, key=lambda x: x["dt"])
        ratio = 1.0
        if r0.get("trips_hist") and r0["trips_hist"] > 0:
            ratio = max(0.5, min(1.0, r0["trips"] / r0["trips_hist"]))
        routes[route] = {
            "trips_per_DT_per_day": round(r0["trips"], 3),
            "trips_own_basis": round(r0.get("trips_hist", r0["trips"]), 3),
            "shared_road_ratio": round(ratio, 4),
            "cycle_minutes": round(r0["cyc"], 1),
            "road_minutes": round(r0.get("road", 0.0), 1),
            "road_own_minutes": round(r0.get("road_hist", 0.0), 1),
            "queue_minutes": round(r0.get("wq", 0.0), 1),
            "overhead_minutes": round(r0["overhead"], 1),
            "dt": round(sum(x["dt"] for x in rs)),
            "loaders": int(sum(x["loaders"] for x in rs)),
            "sections": [{"section": label, "km": round(km, 1)} for label, km, spd in r0["segs"]],
        }
    return {"ok": True, "converged": converged,
            "routes": routes,
            "sections": [dict(section=k, **v) for k, v in sorted(sec_state.items())],
            "method": {
                "road": "sum over chainage sections: measured GPS section speed, "
                        "BPR at section v/c vs measured peak trucks/hr, capped 3x; "
                        "free total anchored to calibrated dispatch road_free_min",
                "flow": "demand flow on the productive cycle (doctrine)",
                "trips": "1440 / (sectioned road + ops + queue + bunching + overhead_per_trip)",
            }}
