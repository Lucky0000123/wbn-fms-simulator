"""Layer 2C - the hybrid predictor: physics + M/M/c + BPR (+ bunching).

predict(route, n_trucks, n_loaders) -> trips/DT/day with a full component
breakdown, congestion status, uncertainty band, and the legacy
divide-by-demonstrated-max comparison.

The physics model is the PRIMARY predictor. Calibration (alpha/beta/mu/
c_road/cycle_sd) comes from data/congestion_params.json. Any ML residual
correction is applied only inside the observed fleet range.
"""
from __future__ import annotations

import math

from . import physics, queueing, bpr
from .config import route_params


def _finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def predict(route: str, n_trucks: float, n_loaders: int | None = None,
            *, shift_hours: float | None = None, shifts_per_day: int | None = None,
            payload_t: float | None = None, rain_mm: float = 0.0,
            legacy_cap: float | None = None, legacy_rate: float | None = None) -> dict:
    """Hybrid trips/DT/day prediction for one route.

    route: 'TF>HUAFEI' style key. n_loaders None -> per-route default + warning.
    """
    if not route or ">" not in str(route):
        raise ValueError("route must look like 'TF>HUAFEI'")
    if not _finite(n_trucks) or n_trucks < 0:
        raise ValueError("n_trucks must be a non-negative number")
    p = route_params(route)
    warnings = []
    if n_loaders is None:
        n_loaders = int(p["n_loaders"])
        warnings.append("n_loaders not specified - using default %d; supply the real "
                        "loader count for a trustworthy prediction" % n_loaders)
    n_loaders = int(n_loaders)
    if n_loaders < 0:
        raise ValueError("n_loaders must be >= 0")
    sh = float(shift_hours if shift_hours is not None else p["hours_per_shift"])
    spd = int(shifts_per_day if shifts_per_day is not None else p["shifts_per_day"])
    day_minutes = spd * sh * 60.0

    origin, _, dest = str(route).partition(">")
    if n_trucks == 0 or n_loaders == 0:
        reason = "no trucks" if n_trucks == 0 else "no loaders"
        return _zero_result(route, n_trucks, n_loaders, reason, warnings)

    dist = physics.route_distance_km(origin, dest)
    if dist is None:
        raise ValueError("unknown route nodes: %s" % route)

    # ── Layer 1: free flow ────────────────────────────────────────────────
    # Wet road: rolling resistance rises with rain (maintained 2% -> ~4% wet).
    rr = float(p["rr_pct"]) + (2.0 if rain_mm >= 10 else (1.0 if rain_mm >= 1 else 0.0))
    ff = physics.free_flow_cycle_min(
        dist, rr_pct=rr,
        speed_loaded_kmh=p.get("speed_loaded_kmh"),
        load_min=float(p["load_min"]), spot_min=float(p["spot_min"]),
        dump_min=float(p["dump_min"]))
    t_free_road = ff["t_haul_loaded_min"] + ff["t_haul_empty_min"]
    t_fixed = ff["t_load_min"] + ff["t_spot_min"] + ff["t_dump_min"]
    # Calibrated road running time (owner, 2026-08-21): p25 uncongested cycle
    # minus fixed ops, from dispatch records. Rain still scales it through the
    # physics speed ratio so wet cycles stay slower than dry.
    if _finite(p.get("road_free_min")) and p["road_free_min"] > 0:
        rain_scale = 1.0
        if rain_mm >= 1:
            ff_dry = physics.free_flow_cycle_min(
                dist, rr_pct=float(p["rr_pct"]),
                speed_loaded_kmh=p.get("speed_loaded_kmh"),
                load_min=float(p["load_min"]), spot_min=float(p["spot_min"]),
                dump_min=float(p["dump_min"]))
            dry_road = ff_dry["t_haul_loaded_min"] + ff_dry["t_haul_empty_min"]
            if dry_road > 0:
                rain_scale = t_free_road / dry_road
        t_free_road = float(p["road_free_min"]) * rain_scale
    if _finite(p.get("ops_min")) and p["ops_min"] > 0:
        t_fixed = float(p["ops_min"])

    # ── Layer 2B: BPR road penalty (uses loaded-direction flow) ──────────
    n_lanes = int(p.get("n_lanes_loaded") or p.get("n_lanes") or 1)
    headway_s = p.get("headway_s")
    c_road = p.get("c_road_trucks_hr")
    if not _finite(c_road) or c_road <= 0 or not _finite(headway_s):
        c_road, n_lanes, headway_s = bpr.geometry_c_road(
            dist,
            n_lanes_loaded=n_lanes,
            headway_s=float(p.get("headway_s") or p["safe_headway_s"]),
            headway_s_short=float(p.get("headway_s_short") or 15.0),
            long_haul_km=float(p.get("long_haul_km") or 50.0))
    mu_hr = 60.0 / float(p["load_min"])
    c_dump = p.get("c_dump_trucks_hr")
    c_link = min(c_road, n_loaders * mu_hr, c_dump if _finite(c_dump) and c_dump > 0 else float("inf"))

    # Flow depends on cycle, cycle on BPR + queue. nxt(cyc) is strictly
    # decreasing in cyc (longer cycle -> fewer arrivals/hr -> less BPR
    # penalty and less queue), so g(cyc) = nxt(cyc) - cyc has exactly one
    # root: solve by BISECTION. The damped Picard iteration used before
    # oscillated between the free and saturated branches near loader
    # saturation and exited after 50 rounds with NO convergence check —
    # the owner's saturation chart showed it as sawtooth dips, trips/DT
    # RISING when trucks were added (2026-08-21).
    def _nxt(cyc_try):
        v_hr = n_trucks / (cyc_try / 60.0)      # trucks/hr entering the link
        b = bpr.bpr_travel_min(t_free_road, v_hr, c_link,
                               float(p["alpha"]), float(p["beta"]))
        # Safety net: road time cannot exceed 3x free flow. Trucks keep
        # moving in gridlock; they do not park for a whole shift. With
        # geometry c_road this rarely binds — if it does, the BPR formula
        # has left the physical range and the cap is a mask, not a model.
        max_road = t_free_road * 3.0
        if b["t_road_min"] > max_road:
            b = {**b, "t_road_min": max_road,
                 "penalty_min": max_road - t_free_road, "regime": "capped"}
        q = queueing.erlang_c(n_trucks, cyc_try / 60.0, float(p["load_min"]),
                              n_loaders, sh)
        return b["t_road_min"] + t_fixed + q["wq_min"], b, q

    lo = max(1.0, ff["t_free_min"])
    hi = t_free_road * 3.0 + t_fixed + sh * 60.0 * 0.5 + 1.0
    nxt_lo, bp, qq = _nxt(lo)
    if nxt_lo <= lo + 0.05:
        cyc = lo                                 # free flow, no feedback
    else:
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            nm, _, _ = _nxt(mid)
            if nm > mid:
                lo = mid
            else:
                hi = mid
        nxt_mid, bp, qq = _nxt(0.5 * (lo + hi))
        cyc = bp["t_road_min"] + t_fixed + qq["wq_min"]

    # ── bunching (variance) penalty ───────────────────────────────────────
    # Linear in N/n_ref, so cap at 3x the reference-fleet term the same way
    # road time is capped at 3x free flow.
    sd = p.get("cycle_sd_min")
    n_ref = p.get("n_trucks_ref") or 30
    bunch = 0.0
    bunch_capped = False
    if _finite(sd) and sd > 0 and n_ref:
        k_b = float(p["k_bunch"])
        bunch_raw = k_b * float(sd) * (n_trucks / float(n_ref))
        bunch_cap = 3.0 * k_b * float(sd)
        if bunch_raw > bunch_cap:
            bunch = bunch_cap
            bunch_capped = True
            warnings.append("bunching penalty capped at 3x the reference-fleet term")
        else:
            bunch = bunch_raw
        cyc += bunch

    # OVERHEAD PER TRIP (owner, 2026-08-21 — replaces trips = U*1440/cyc):
    # breaks, dispatch wait, shift change and refuelling attach to TRIPS,
    # not to the clock. The old U anchor turned non-productive time into a
    # fixed share of the day, so past U*1440 < cycle the model claimed a
    # dispatched truck cannot finish even one trip in 24 h. Now:
    #     trips = day_minutes / (cyc + overhead_per_trip)
    # cyc is productive time only (road_congested + ops + queue + bunching),
    # so trips stays >= day/(3*road_free + ops + caps + overhead) — always
    # physically possible. Calibration anchors overhead so the model equals
    # the dispatch day rate exactly at the median fleet.
    overhead = p.get("overhead_per_trip_min")
    if not _finite(overhead) or overhead < 0:
        overhead = 240.0  # fresh-clone fallback; calibration writes the real one
    trips_dt_day = day_minutes / (cyc + overhead) if cyc > 0 else 0.0
    total_trips = trips_dt_day * n_trucks
    pay = payload_t if _finite(payload_t) and payload_t > 0 else p.get("payload_t") or 0.0

    status = "overloaded" if qq.get("overloaded") else (
        "congested" if (qq["rho"] >= 0.7 or bp["vc"] >= 0.7) else "open")
    if qq.get("overloaded"):
        warnings.append("loader system overloaded (rho=%.2f) - queue wait capped at "
                        "half a shift; add loaders or remove trucks" % qq["rho"])

    # ── uncertainty band ─────────────────────────────────────────────────
    lo_dt, hi_dt = p.get("obs_dt_min") or 0, p.get("obs_dt_max") or 0
    in_range = hi_dt and lo_dt <= n_trucks <= hi_dt
    rel = 0.10 if in_range else min(0.40, 0.10 + 0.30 * max(0.0, (n_trucks - (hi_dt or n_trucks)) / max(hi_dt or n_trucks, 1)))
    unc = {"p10": round(trips_dt_day * (1 - rel), 3),
           "p50": round(trips_dt_day, 3),
           "p90": round(trips_dt_day * (1 + rel), 3),
           "relative": round(rel, 3),
           "within_observed_fleet_range": bool(in_range)}

    # ── legacy comparison (divide demonstrated max by fleet) ─────────────
    legacy = None
    cap = legacy_cap if _finite(legacy_cap) else p.get("day_trips_cap")
    rate = legacy_rate if _finite(legacy_rate) else p.get("day_rate")
    if _finite(cap) and _finite(rate) and cap and rate:
        lin = rate * n_trucks
        served = min(lin, cap)
        eff = max(served / n_trucks, 0.3 * rate)
        legacy = {"trips_per_DT_per_day": round(eff, 3),
                  "method": ("min(%.2f*N, %d)/N with 30%% floor" % (rate, cap)),
                  "model_version": "legacy_divide"}

    result = {
        "route": route,
        "n_trucks": round(float(n_trucks), 1),
        "n_loaders": n_loaders,
        "model_version": "hybrid",
        "calibrated": bool(p.get("calibrated")),
        "trips_per_DT_per_day": round(trips_dt_day, 3),
        "trips_per_DT_per_shift": round(trips_dt_day / spd, 3),
        "total_trips_day": round(total_trips, 1),
        "total_tonnes_day": round(total_trips * pay, 1) if pay else None,
        "cycle_time_minutes": round(cyc, 1),
        "components": {
            "t_free_road": round(t_free_road, 1),
            "bpr_penalty_minutes": round(bp["penalty_min"], 1),
            "t_load": round(ff["t_load_min"], 1),
            "t_spot": round(ff["t_spot_min"], 1),
            "t_dump": round(ff["t_dump_min"], 1),
            "queue_wait_minutes": round(qq["wq_min"], 1),
            "bunching_penalty_minutes": round(bunch, 2),
            "overhead_per_trip_minutes": round(float(overhead), 1),
        },
        "congestion_status": status,
        "bpr_regime": bp.get("regime"),
        "bunching_capped": bunch_capped,
        "rho": round(qq["rho"], 3),
        "road_vc": round(bp["vc"], 3),
        "link_capacity_trucks_hr": round(c_link, 1),
        "distance_km": round(dist, 1),
        "params": {"alpha": p["alpha"], "beta": p["beta"],
                   "bpr_source": "literature_default",
                   "load_min": p["load_min"], "rr_pct": rr,
                   "c_road_trucks_hr": round(c_road, 1),
                   "headway_s": round(float(headway_s), 1),
                   "n_lanes_loaded": n_lanes},
        "uncertainty": unc,
        "legacy_comparison": legacy,
        "warnings": warnings,
    }
    for k in ("trips_per_DT_per_day", "cycle_time_minutes"):
        if not _finite(result[k]):
            raise ArithmeticError("non-finite %s for %s @%s trucks" % (k, route, n_trucks))
    return result


def _zero_result(route, n_trucks, n_loaders, reason, warnings):
    return {
        "route": route, "n_trucks": n_trucks, "n_loaders": n_loaders,
        "model_version": "hybrid", "trips_per_DT_per_day": 0.0,
        "trips_per_DT_per_shift": 0.0, "total_trips_day": 0.0,
        "total_tonnes_day": 0.0, "cycle_time_minutes": None,
        "components": None, "congestion_status": "idle",
        "rho": 0.0, "road_vc": 0.0,
        "uncertainty": {"p10": 0.0, "p50": 0.0, "p90": 0.0},
        "legacy_comparison": None,
        "warnings": warnings + ["zero output: %s" % reason],
    }
