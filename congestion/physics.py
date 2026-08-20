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


def route_distance_km(origin: str, dest: str) -> float | None:
    o = (origin or "").strip().upper()
    d = (dest or "").strip().upper()
    if o in SPUR_KM:
        base = NODE_KM.get(d)
        if base is None:
            return None
        # BLB spur: 17.4 km spur + |join(2.5km) - dest| along the stick
        return SPUR_KM[o] - 2.5 + abs(2.5 - base) if base <= 2.5 else 17.4 + abs(base - 2.5)
    ok, dk = NODE_KM.get(o), NODE_KM.get(d)
    if ok is None or dk is None:
        return None
    return abs(ok - dk)


def speed_from_rr(rr_pct: float) -> float:
    """Empirical loaded haul speed from rolling resistance % (M&S 2023)."""
    rr = max(0.5, min(10.0, float(rr_pct)))
    return max(5.0, 0.0348 * rr * rr - 1.3239 * rr + 17.696)


def free_flow_cycle_min(
    distance_km: float,
    *,
    rr_pct: float = 2.0,
    speed_loaded_kmh: float | None = None,
    speed_empty_kmh: float | None = None,
    load_min: float = 5.0,
    spot_min: float = 1.0,
    dump_min: float = 2.0,
) -> dict:
    """Free-flow (zero-queue, zero-traffic) cycle for one round trip."""
    if distance_km is None or distance_km < 0:
        raise ValueError("distance_km must be >= 0")
    v_l = speed_loaded_kmh if (speed_loaded_kmh or 0) > 0 else speed_from_rr(rr_pct)
    # Empty return runs faster; site GPS shows ~1.25x loaded speed.
    v_e = speed_empty_kmh if (speed_empty_kmh or 0) > 0 else v_l * 1.25
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
        "distance_km": distance_km,
    }
