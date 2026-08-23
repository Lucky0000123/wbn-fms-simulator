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
# Reference speed for implied_one_way_km ONLY (chainage sanity check).  It is
# NOT the measured corridor speed and is deliberately left at 15.0 — see the
# note on implied_one_way_km below for why raising it would make that check
# worse, not better.
REF_SPEED_KMH = 15.0

# ── MEASURED free-flow corridor speed (2026-08-23) ───────────────────────────
# p85 of the hourly mean GPS speed in the QUIET quartile of truck counts, per
# km band, from FMS_CONGESTION_SEG (38,515 segment-hours, 2026-07-15..), then
# length-weighted per road (total minutes / total km).  "Free flow" is the same
# low-traffic-p85 convention the congestion endpoint already uses; the committed
# data/congestion_seg_by_dir.csv is a traffic-WEIGHTED mean and so runs ~20-25%
# slower than this — do not read that CSV as free flow (AGENTS.md already warns
# "corridor means include congested traffic, so they run high").
#
# The result that matters is how FLAT it is.  Every road on the stick free-flows
# at ~20 km/h loaded against posted limits of 30-50 km/h, so the route's road
# time comes out 1.59-1.86x its speed-limit-implied time on EVERY calibrated
# stick route — KR 1.62-1.86, TF 1.59-1.67.  Trucks running at roughly half the
# sign is a site fact, not a KR peculiarity, and it is most of the KR corridor
# anomaly the owner asked about (2026-08-23).  Measured, not assumed: do not
# "correct" a route's distance to make its posted-limit time fit.
CORRIDOR_FREE_FLOW_KMH = {
    # road: (loaded / down-chainage, empty / up-chainage) km/h
    "CRD": (18.6, 18.8),    # n = 2,075 / 2,130 segment-hours over 7 km
    "KR": (20.3, 22.6),     # n = 9,807 / 9,738 over 32 km
    "TF": (20.4, 25.5),     # n = 7,642 / 7,123 over 29 km
    "BLB": (16.7, 19.2),    # spur, n = 2,471 / 2,445 over 11 km
}

# Which road owns which chainage.  From the committed survey
# data/haul_road_chainage_public.csv, whose mainline is three CONTIGUOUS runs on
# one datum — CRD 0.000-7.850, KR 7.875-38.975, TOFU 39.000-67.800 — which is
# also the independent confirmation that KR sits at chainage 39 and TF at 67.8.
# Same provenance and same "never retype it" rule as segments.SPUR_JOIN_KM.
CORRIDOR_ROADS = (
    (0.0, 7.85, "CRD"),
    (7.85, 39.0, "KR"),
    (39.0, 67.8, "TF"),
)
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


def free_flow_road_min(origin: str, dest: str):
    """(loaded_min, empty_min) round-trip ROAD time at MEASURED free-flow speed.

    Walks the route's chainage span across CORRIDOR_ROADS and prices each part
    at that road's measured free-flow speed (CORRIDOR_FREE_FLOW_KMH).  Returns
    (None, None) for anything not wholly on the mainline stick — a spur origin
    is priced on its own calibrated distance everywhere else in this package
    and has no speed-limit sheet to be compared against, so inventing a number
    for it here would be exactly the geometry this repo has already paid for.

    This is the honest reference `road_free_min` should be read against.  It is
    NOT a replacement for it: `road_free_min` stays dispatch-anchored on
    purpose, and the calibration's overhead term is anchored on top of it, so
    swapping one for the other without re-anchoring would break every route.
    """
    a, b = NODE_KM.get((origin or "").strip().upper()), \
        NODE_KM.get((dest or "").strip().upper())
    if a is None or b is None or a == b:
        return None, None
    lo, hi = min(a, b), max(a, b)
    t_loaded = t_empty = 0.0
    covered = 0.0
    for bottom, top, road in CORRIDOR_ROADS:
        ov = min(hi, top) - max(lo, bottom)
        if ov <= 0:
            continue
        v_l, v_e = CORRIDOR_FREE_FLOW_KMH[road]
        t_loaded += 60.0 * ov / v_l
        t_empty += 60.0 * ov / v_e
        covered += ov
    if covered <= 0 or covered < (hi - lo) - 0.05:
        return None, None          # span leaves the surveyed mainline
    return t_loaded, t_empty


def road_free_audit(origin: str, dest: str, road_free_min):
    """Decompose a calibrated `road_free_min` against measured road time.

    Answers the owner's 2026-08-23 question ("why does KR's calibrated road
    time run 1.7-3.0x its official speed-limit time?") as a PRODUCT of two
    independent factors instead of one alarming ratio:

        road_free_min / posted_limit  ==  speed_factor  x  nonroad_factor

      speed_factor   = measured free-flow road time / speed-limit-implied time.
                       1.59-1.86 on every calibrated stick route — trucks run
                       at ~55-63% of the posted limit, corridor-wide.
      nonroad_factor = road_free_min / measured free-flow road time.  Whatever
                       is left is per-trip queue, spotting and dwell that the
                       flat 8-minute `ops_min` does not cover.  0.55-1.65
                       across routes; KR>POS 12 is the highest at 1.65, where
                       WAITING_TIME independently measures ~29 min/trip of
                       loading + dumping queue.

    Returns None when the route is not wholly on the surveyed mainline.
    """
    t_l, t_e = free_flow_road_min(origin, dest)
    if t_l is None:
        return None
    # Local import: keeps physics free of an import-time dependency on
    # speed_limits, the same way predictor.py reaches for segments/speed_limits.
    from .speed_limits import span_times_min
    a, b = NODE_KM[(origin or "").strip().upper()], \
        NODE_KM[(dest or "").strip().upper()]
    lim_l, lim_e = span_times_min(min(a, b), max(a, b))
    ff = t_l + t_e
    posted = (lim_l or 0.0) + (lim_e or 0.0)
    out = {
        "free_flow_road_min": round(ff, 1),
        "posted_limit_road_min": round(posted, 1) if posted else None,
        "speed_factor_vs_posted": round(ff / posted, 2) if posted else None,
        "free_flow_source": ("p85 quiet-hour FMS_CONGESTION_SEG speeds by road "
                             "x surveyed chainage span (2026-08-23)"),
    }
    if road_free_min and float(road_free_min) > 0 and ff > 0:
        rf = float(road_free_min)
        out["nonroad_in_road_free_min"] = round(rf - ff, 1)
        out["nonroad_factor"] = round(rf / ff, 2)
        if posted:
            out["road_free_vs_posted"] = round(rf / posted, 2)
    return out


def implied_one_way_km(t_free_min, load_min=5.0, spot_min=1.0, dump_min=2.0,
                       speed_loaded_kmh=REF_SPEED_KMH):
    """One-way km implied by a measured free-flow cycle at a reference speed.

    READ THE RESULT WITH BOTH ITS ERRORS IN MIND (measured 2026-08-23).  Its
    caller feeds it `t_free` = the p25 of per-day-shift MEAN trip gaps, which is
    NOT free-flow and NOT road: on KR>POS 12 that is 118.9 min against a
    fastest-decile complete cycle of 80 min and a measured free-flow road round
    trip of 67.3 min, so the numerator carries ~30-45 min of queue and dwell.
    The denominator is wrong the other way: 15.0 km/h against a measured
    free-flow 20.3 km/h loaded on the KR road.  The two errors PARTIALLY CANCEL
    (1.65x up, 0.74x down) and that is precisely why `chainage_suspect`, which
    is built on this ratio, has never fired on any route.

    So this is a weak check, not a distance measurement, and raising
    REF_SPEED_KMH alone would make it WORSE: KR>POS 12's implied 15.4 km
    (against a true 12.0) would become 21.0 km.  Fed its honest inputs the
    formula is sound — free_flow_road_min('KR','POS 12') is 67.3 min, which at
    20.3 km/h returns 12.5 km against the surveyed 12.0.  Fix the numerator, or
    use free_flow_road_min(); do not tune the constant.
    """
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
