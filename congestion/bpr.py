"""Layer 2B - BPR road congestion penalty.

t_road = t_free_road * (1 + alpha * (v/c)^beta)          when v <= c
(BPR2 removed 2026-08-20: doubled exponent gave impossible penalties at mining v/c)

v = trucks/hr on the link (loaded-direction flow: one pass per cycle).
c = binding link capacity = min(road headway capacity, loader output, dump).
alpha/beta are literature defaults (0.15 / 4.0) unless a route has a real
v/c range; historical fleets here do not.
"""
from __future__ import annotations

import math


def geometry_c_road(distance_km,
                    n_lanes_loaded: int = 1,
                    headway_s: float = 60.0,
                    headway_s_short: float = 15.0,
                    long_haul_km: float = 50.0) -> tuple:
    """c_road from 1 loaded lane and a documented headway.

    Classifies short vs long by chainage distance, never by measured cycle
    time. Unknown distance uses the long-corridor headway (lower capacity).
    """
    n = max(1, int(n_lanes_loaded))
    if distance_km is not None and float(distance_km) < float(long_haul_km):
        h = float(headway_s_short)
    else:
        h = float(headway_s)
    return road_capacity_trucks_hr(n, h), n, h


def road_capacity_trucks_hr(n_lanes: int = 1, safe_headway_s: float = 60.0) -> float:
    """Physical link capacity from headway. One lane per direction here, so
    n_lanes=1 means one loaded-direction lane."""
    if safe_headway_s <= 0:
        raise ValueError("safe_headway_s must be > 0")
    return max(1.0, n_lanes * 3600.0 / safe_headway_s)


def bpr_travel_min(t_free_road_min: float, v_trucks_hr: float, c_link_hr: float,
                   alpha: float = 0.15, beta: float = 4.0,
                   period_h: float = 12.0) -> dict:
    """Congested road time: BPR below capacity, Akçelik above.

    R3 from the 2026-08-26 literature audit
    (reports/congestion_analysis_report.md, reports/survey_congestion.md).
    The transport consensus (Akçelik 1991 Australian Road Research; Small &
    Chu 2003 JTEP; Hadi et al. 2013 FDOT — whose explicit rule is "BPR for
    v/c < 1, Akçelik above") is that a static BPR's over-capacity branch is
    an extrapolated polynomial with no physics: real oversaturation delay is
    a QUEUE that grows for as long as demand exceeds capacity, so it must
    scale with the analysis period. Akçelik's time-dependent form,

        t = t_free + 0.25*T*[(x-1) + sqrt((x-1)^2 + 8*J*x/(c*T))],

    is the coordinate-transformation of deterministic queueing: it hugs BPR
    below capacity (both ~t_free until v/c ~0.9), transitions smoothly
    through x=1, and grows LINEARLY in x above it — delay per truck for
    running a 12 h plan at x=2 is half the period times (x-1), not
    alpha*x^4 times free time. Measured against our BLB>HUAFEI leg
    (t_free=140 min, c=400/hr): the two agree within 12% up to x~1.1, then
    BPR undershoots to x~2 and EXPLODES past it (x=3: BPR 1,841 min vs
    Akçelik 860) — both wrong, only Akçelik's number means anything.

    J (delay parameter) is folded from alpha so a route's calibrated BPR
    steepness carries over: J = 2*alpha gives Akçelik(x=1) ≈ BPR(x=1) for
    our alpha=0.15/beta=4 defaults. period_h is the plan's own shift.
    The old 3x-free-flow cap in predictor.py still applies downstream as
    the last physical sanity wall.
    """
    if t_free_road_min < 0 or v_trucks_hr < 0:
        raise ValueError("negative inputs")
    if c_link_hr <= 0:
        return {"t_road_min": t_free_road_min, "vc": 0.0, "penalty_min": 0.0,
                "regime": "no-capacity"}
    vc = v_trucks_hr / c_link_hr
    if vc <= 1.0:
        factor = 1.0 + alpha * (vc ** beta)
        t = t_free_road_min * factor
        form = "bpr"
    else:
        t_h = max(0.25, float(period_h))
        j = 2.0 * alpha
        x = vc
        delay_h = 0.25 * t_h * ((x - 1.0)
                                + math.sqrt((x - 1.0) ** 2
                                            + 8.0 * j * x / (c_link_hr * t_h)))
        # Continuity: Akçelik's sqrt term at x=1 is tiny for our capacities,
        # while BPR carries alpha*t_free there. Add the BPR value at x=1 as
        # the base so the piecewise function cannot step down at the seam.
        t = t_free_road_min * (1.0 + alpha) + delay_h * 60.0
        form = "akcelik"
    return {"t_road_min": t, "vc": vc, "penalty_min": t - t_free_road_min,
            "form": form,
            "regime": "free" if vc <= 0.7 else ("congested" if vc <= 1.0 else "oversaturated")}


# ── arrival-weighted (Jensen) road pricing ──────────────────────────────────
# Owner, 2026-08-26: "trucks come at different times ... we are missing the
# natural human physics." The flat model prices f(v_mean); real within-day
# flow is peaked, and every delay function here is convex in v, so by
# Jensen's inequality f(v_mean) UNDERSTATES the day's average delay:
# E[f(v·m)] > f(v). Measured from our own 109,089 segment-hours
# (data/arrival_profile.json): hourly flow ranges 0.13x–2.45x the same-day
# mean; at base v/c 0.6 the flat model understates the BPR factor by ~13%,
# at 0.9 by ~61%. The correction prices the day as the average over ten
# equal-mass measured multipliers — total flow conserved exactly, no new
# parameters, pure measured shape.
import json as _json
import os as _os

_ARRIVAL_PROFILE = None


def arrival_profile():
    """Ten equal-mass hourly-flow multipliers, measured, mean 1.0."""
    global _ARRIVAL_PROFILE
    if _ARRIVAL_PROFILE is None:
        path = _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))), "data", "arrival_profile.json")
        try:
            with open(path, encoding="utf-8") as fh:
                _ARRIVAL_PROFILE = list(_json.load(fh)["decile_multipliers"])
        except (OSError, ValueError, KeyError):
            # No profile file: fall back to the flat model (multiplier 1.0),
            # never to an invented shape.
            _ARRIVAL_PROFILE = [1.0]
    return _ARRIVAL_PROFILE


def bpr_travel_min_weighted(t_free_road_min: float, v_trucks_hr: float,
                            c_link_hr: float, alpha: float = 0.15,
                            beta: float = 4.0,
                            period_h: float = 12.0) -> dict:
    """Arrival-weighted road time: mean of bpr_travel_min over the measured
    within-day flow deciles. Reports the flat result's vc/regime (the plan's
    average is still the headline number) plus the weighted time and the
    peaking premium so the two clocks stay separately visible."""
    flat = bpr_travel_min(t_free_road_min, v_trucks_hr, c_link_hr,
                          alpha, beta, period_h)
    prof = arrival_profile()
    if len(prof) <= 1 or v_trucks_hr <= 0 or c_link_hr <= 0:
        return {**flat, "t_road_weighted_min": flat["t_road_min"],
                "peaking_premium_min": 0.0}
    # Each decile is ~1/10 of the day's hours AND carries v*m/vmean of the
    # trucks; a truck-experienced average weights each decile by its share
    # of TRUCKS (m), not of hours. That is the time the average TRIP sees.
    wsum = sum(prof)
    t_w = sum(m * bpr_travel_min(t_free_road_min, v_trucks_hr * m,
                                 c_link_hr, alpha, beta, period_h)["t_road_min"]
              for m in prof) / wsum
    return {**flat, "t_road_weighted_min": t_w,
            "peaking_premium_min": max(0.0, t_w - flat["t_road_min"])}
