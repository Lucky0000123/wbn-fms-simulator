"""Layer 2B - BPR road congestion penalty.

t_road = t_free_road * (1 + alpha * (v/c)^beta)          when v <= c
(BPR2 removed 2026-08-20: doubled exponent gave impossible penalties at mining v/c)

v = trucks/hr on the link (loaded-direction flow: one pass per cycle).
c = binding link capacity = min(road headway capacity, loader output, dump).
alpha/beta are literature defaults (0.15 / 4.0) unless a route has a real
v/c range; historical fleets here do not.
"""
from __future__ import annotations


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
                   alpha: float = 0.15, beta: float = 4.0) -> dict:
    """BPR / BPR2 congested road time."""
    if t_free_road_min < 0 or v_trucks_hr < 0:
        raise ValueError("negative inputs")
    if c_link_hr <= 0:
        return {"t_road_min": t_free_road_min, "vc": 0.0, "penalty_min": 0.0,
                "regime": "no-capacity"}
    vc = v_trucks_hr / c_link_hr
    # Regular BPR at ALL v/c. BPR2 (doubled exponent past capacity) was built
    # for highway planning at v/c <= ~1.3; mining plans reach v/c 3-5 where
    # it produced 985x penalties (physically impossible — removed 2026-08-20).
    exp = beta
    factor = 1.0 + alpha * (vc ** exp)
    t = t_free_road_min * factor
    return {"t_road_min": t, "vc": vc, "penalty_min": t - t_free_road_min,
            "regime": "free" if vc <= 0.7 else ("congested" if vc <= 1.0 else "oversaturated")}
