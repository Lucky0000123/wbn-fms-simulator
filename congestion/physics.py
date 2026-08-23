"""Layer 1 - Physics: free-flow cycle time from route geometry.

t_free = t_spot + t_load + t_haul_loaded + t_haul_empty + t_dump

Speeds come from the empirical rolling-resistance formula (Meneses &
Sepulveda 2023) when no measured section speed exists:

    v(RR) = 0.0348*RR^2 - 1.3239*RR + 17.696   [km/h]

Distances come from the same chainage table the rest of the app uses
(plan_analogues.NODE_KM) so the physics engine and the corridor stick can
never disagree about how long a road is.
"""
from __future__ import annotations

import math

# Route chainage (km) - single source of truth with plan_analogues.NODE_KM.
NODE_KM = {
    "TF": 67.8, "TOFU": 67.8,
    "KR": 39.0, "KRENE": 39.0,
    "POS 12": 27.0, "POS12": 27.0,
    "POS 14": 26.1, "POS 15": 26.1, "POS 16": 26.1,
    "POS 10": 17.0, "POS10": 17.0,
    "FENI KM15": 15.0, "FENI 15": 15.0,
    "FENI KM0": 0.0, "FENI 0": 0.0, "FENI": 0.0,
    "HUAFEI": 0.0, "BSE": 0.0, "CRUSHER": 3.0, "POS CBB": 55.0,
}
# BLB is a spur that joins the main stick near the coast; its effective haul
# to FENI KM0 is ~19 km (measured cycle 165 min supports ~19 km at ~14 km/h
# effective + dwell), NOT 67.8. Spur joins at ~2.5 km + 17.4 km spur length.
SPUR_KM = {"BLB": 19.9}
# Measured one-way haul km. GPS tracks cannot verify these routes:
# FMS_GPS_Historical only covers 2026-07-15..08-07, while BLB>POS 14
# tickets end 2026-07-06 and TF>HUAFEI tickets end 2026-03-06.
# Values are DISTANCE_HAULING median, corroborated where possible by
# DISPATCH ROADS gross km and survey-polyline snap (BLB pit km 19.82
# -> POS 14 dumps at BLB km ~6.3 is 6.55 km of polyline).
# POS 15/16 have no DISTANCE_HAULING row and no named geofence; they
# inherit POS 14 (same coastal dump cluster, t_free 96-105 min).
MEASURED_HAUL_KM = {
    ("BLB", "POS 14"): 6.7,
    ("BLB", "POS14"): 6.7,
    ("BLB", "POS 15"): 6.7,
    ("BLB", "POS15"): 6.7,
    ("BLB", "POS 16"): 6.7,
    ("BLB", "POS16"): 6.7,
    ("TF", "HUAFEI"): 63.7,
    ("TOFU", "HUAFEI"): 63.7,
}
HAUL_KM_SOURCE = {
    ("BLB", "POS 14"): "DISTANCE_HAULING p50 6.7 km (n=2204) + survey polyline 6.55 km",
    ("BLB", "POS14"): "DISTANCE_HAULING p50 6.7 km (n=2204) + survey polyline 6.55 km",
    ("BLB", "POS 15"): "inherited from BLB>POS 14 (no DISTANCE_HAULING / geofence / GPS overlap)",
    ("BLB", "POS15"): "inherited from BLB>POS 14 (no DISTANCE_HAULING / geofence / GPS overlap)",
    ("BLB", "POS 16"): "inherited from BLB>POS 14 (no DISTANCE_HAULING / geofence / GPS overlap)",
    ("BLB", "POS16"): "inherited from BLB>POS 14 (no DISTANCE_HAULING / geofence / GPS overlap)",
    ("TF", "HUAFEI"): "DISTANCE_HAULING p50 63.7 km (n=51); DISPATCH ROADS 63.1-63.4",
    ("TOFU", "HUAFEI"): "DISTANCE_HAULING p50 63.7 km (n=51); DISPATCH ROADS 63.1-63.4",
}
# Typical loaded mine-haul speed used only to translate a measured free-flow
# cycle into an implied one-way distance (chainage sanity check).
REF_SPEED_KMH = 15.0
# Kept for FENI/HUAFEI BLB hauls that still use the spur formula.
BLB_COASTAL_DEST = {
    "POS 14", "POS14", "POS 15", "POS15", "POS 16", "POS16",
}


def route_distance_km(origin: str, dest: str) -> float | None:
    o = (origin or "").strip().upper()
    d = (dest or "").strip().upper()
    measured = MEASURED_HAUL_KM.get((o, d))
    if measured is not None:
        return measured
    if o in SPUR_KM:
        if d in BLB_COASTAL_DEST:
            return SPUR_KM[o]
        base = NODE_KM.get(d)
        if base is None:
            return None
        # BLB spur: 17.4 km spur + |join(2.5km) - dest| along the stick
        return SPUR_KM[o] - 2.5 + abs(2.5 - base) if base <= 2.5 else 17.4 + abs(base - 2.5)
    ok, dk = NODE_KM.get(o), NODE_KM.get(d)
    if ok is None or dk is None:
        return None
    return abs(ok - dk)


def implied_one_way_km(t_free_min, load_min=5.0, spot_min=1.0, dump_min=2.0,
                       speed_loaded_kmh=REF_SPEED_KMH):
    """One-way km implied by a measured free-flow cycle at a reference speed."""
    if not t_free_min or t_free_min <= 0 or speed_loaded_kmh <= 0:
        return None
    t_road = max(5.0, float(t_free_min) - (load_min + spot_min + dump_min))
    return t_road / (60.0 * (1.0 + 1.0 / 1.25) / float(speed_loaded_kmh))


def speed_from_rr(rr_pct: float) -> float:
    """Empirical loaded haul speed from rolling resistance % (M&S 2023)."""
    rr = max(0.5, min(10.0, float(rr_pct)))
    return max(5.0, 0.0348 * rr * rr - 1.3239 * rr + 17.696)


def rr_speed_ratio(rr_pct: float, rr_ref_pct: float) -> float:
    """Speed multiplier for moving off the reference rolling resistance.

    The M&S 2023 curve above is the ONLY thing in this module that says how
    road condition maps to speed, so it is also the only thing entitled to say
    how much a wetter road slows a truck.  This returns

        speed_from_rr(rr) / speed_from_rr(rr_ref)

    i.e. a pure RATIO, so it can be applied to a *measured* speed without
    discarding it.  No new coefficient is introduced: at rr == rr_ref the
    ratio is exactly 1.0 (short-circuited, so callers are bit-identical),
    and every wetter value is read off the same published curve.

    Monotone: the parabola's vertex sits at rr = 19.0 %, far outside the
    [0.5, 10] % clamp in speed_from_rr, so speed is strictly decreasing in rr
    across the whole usable domain -> the ratio never rises with rain.
    Bounded: the clamp also bounds the ratio.  Worst case reachable from the
    maintained-road reference (2 %) with the predictor's +2 pp wet bump is
    speed_from_rr(4)/speed_from_rr(2) = 12.957/15.187 = 0.853, i.e. at most
    ~17.2 % more road running time.
    """
    ref = float(rr_ref_pct)
    cur = float(rr_pct)
    if cur == ref:
        return 1.0
    v_ref = speed_from_rr(ref)
    if not (v_ref > 0):
        return 1.0
    return speed_from_rr(cur) / v_ref


def free_flow_cycle_min(
    distance_km: float,
    *,
    rr_pct: float = 2.0,
    rr_ref_pct: float | None = None,
    speed_loaded_kmh: float | None = None,
    speed_empty_kmh: float | None = None,
    load_min: float = 5.0,
    spot_min: float = 1.0,
    dump_min: float = 2.0,
) -> dict:
    """Free-flow (zero-queue, zero-traffic) cycle for one round trip.

    `rr_pct` only reached the output when no measured speed was supplied, so a
    calibrated route silently ignored rolling resistance and therefore ignored
    rain (owner-reported defect, 2026-08-23).  Supplying `rr_ref_pct` — the
    rolling resistance the measured speed was observed AT — makes the measured
    speed scale by `rr_speed_ratio(rr_pct, rr_ref_pct)` instead of being
    bypassed.  Left None (the default) nothing changes for any caller.
    """
    if distance_km is None or distance_km < 0:
        raise ValueError("distance_km must be >= 0")
    # Ratio only; the measured speed stays the anchor for its own conditions.
    rr_scale = 1.0 if rr_ref_pct is None else rr_speed_ratio(rr_pct, rr_ref_pct)
    if (speed_loaded_kmh or 0) > 0:
        v_l = speed_loaded_kmh * rr_scale
    else:
        v_l = speed_from_rr(rr_pct)
    # Empty return runs faster; site GPS shows ~1.25x loaded speed.
    if (speed_empty_kmh or 0) > 0:
        v_e = speed_empty_kmh * rr_scale
    else:
        v_e = v_l * 1.25
    t_haul_loaded = 60.0 * distance_km / v_l
    t_haul_empty = 60.0 * distance_km / v_e
    total = spot_min + load_min + t_haul_loaded + t_haul_empty + dump_min
    return {
        "t_free_min": total,
        "t_haul_loaded_min": t_haul_loaded,
        "t_haul_empty_min": t_haul_empty,
        "t_load_min": load_min,
        "t_spot_min": spot_min,
        "t_dump_min": dump_min,
        "speed_loaded_kmh": v_l,
        "speed_empty_kmh": v_e,
        "rr_speed_scale": rr_scale,
        "distance_km": distance_km,
    }
