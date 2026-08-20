"""Layer 2B - BPR road congestion penalty.

t_road = t_free_road * (1 + alpha * (v/c)^beta)          when v <= c
t_road = t_free_road * (1 + alpha * (v/c)^(2*beta))      when v >  c  (BPR2)

v = trucks/hr on the link (both directions share one two-way road here),
c = binding link capacity = min(road headway capacity, loader output, dump).
alpha/beta calibrated per route from history (defaults 0.15 / 4.0).
"""
from __future__ import annotations


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
    exp = beta if vc <= 1.0 else 2.0 * beta
    factor = 1.0 + alpha * (vc ** exp)
    t = t_free_road_min * factor
    return {"t_road_min": t, "vc": vc, "penalty_min": t - t_free_road_min,
            "regime": "free" if vc <= 0.7 else ("congested" if vc <= 1.0 else "oversaturated")}
