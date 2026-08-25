"""Official haul-road speed limits + geometry (owner documents, 2026-08-22).

Source: "20250811 UPDATE SPEED LIMIT HAULING ROAD.pdf"
(/Volumes/LUCKY_SSD/WORK_WBN/WORK/Maps and Designs), read page by page:
  p1  KM 5 - KAOROHAI (KM 27)
  p2  KAOROHAI (KM 27) - TOFU (KM 68)
  (p3/p4 cover UNI UNI-BIRI BIRI and BIRI BIRI-BUKIT LIMBER side roads —
   owner, 2026-08-22: "we don't need to think of BIRI BIRI or UNI UNI,
   ignore it for now." Do NOT wire them in without a new owner decision.
   The BLB spur has NO speed-limit sheet and keeps the dispatch-calibrated
   per-route method.)

Directions are signed on the road: ARAH MUATAN = loaded = DOWN-chainage
(pit -> coast), ARAH KOSONGAN = empty = UP-chainage. The two directions
have their OWN bins and limits, so they are stored as separate tables.
Heavy Truck (DT) columns only — LV limits are not used by the model.

Geometry (owner, from the road design sheets): width 15 m, mixed
gravel/sealed surface, ONE lane per direction with SEPARATE loaded and
empty lanes, no overtaking. Capacity per direction is therefore
speed / following-distance for a single lane; the chain's throughput is
bounded by its SLOWEST bin (a 20 km/h stretch caps the whole segment —
averaging would overstate capacity), so segment capacity uses min-bin
speed. Following distance is the gap between two DTs on one loaded
lane (FOLLOWING_DISTANCE_M). Owner, 2026-08-25 latest: **50 m** between
DTs on every section (60 m and 75 m packed too few). Posted speeds per
section stay as on the sheets — only the gap moved.

KM 0-5 (port area) has no sheet: extended at the adjacent 20/30 values
and flagged in `assumptions`.
"""
from __future__ import annotations

SOURCE_DOC = "20250811 UPDATE SPEED LIMIT HAULING ROAD.pdf"
ROAD_WIDTH_M = 15
ROAD_SURFACE = "mixed"          # gravel + sealed sections
OVERTAKING = False
SEPARATE_LANES = True           # loaded and empty each have their own lane
FOLLOWING_DISTANCE_M = 50.0     # owner 2026-08-25: 50 m between two DTs

# (lo_km, hi_km, dt_kmh) — LOADED direction (ARAH MUATAN, down-chainage)
LOADED_LIMITS = [
    (0.0, 5.0, 20),      # port area, no sheet — extended from 6.2->5 value
    (5.0, 6.2, 20),
    (6.2, 9.1, 30),
    (9.1, 14.4, 40),
    (14.4, 15.5, 30),
    (15.5, 17.175, 40),
    (17.175, 19.05, 30),
    (19.05, 20.8, 40),
    (20.8, 22.025, 30),
    (22.025, 23.6, 40),
    (23.6, 33.025, 50),
    (33.025, 37.15, 30),
    (37.15, 43.0, 40),
    (43.0, 50.0, 30),
    (50.0, 53.0, 40),
    (53.0, 57.0, 30),
    (57.0, 58.0, 40),
    (58.0, 60.0, 30),
    (60.0, 62.0, 40),
    (62.0, 63.0, 30),
    (63.0, 65.0, 40),
    (65.0, 68.0, 30),
]

# (lo_km, hi_km, dt_kmh) — EMPTY direction (ARAH KOSONGAN, up-chainage)
EMPTY_LIMITS = [
    (0.0, 5.0, 30),      # port area, no sheet — extended
    (5.0, 7.9, 20),
    (7.9, 11.3, 30),
    (11.3, 14.825, 40),
    (14.825, 19.05, 30),
    (19.05, 21.05, 50),
    (21.05, 23.5, 40),
    (23.5, 33.025, 50),
    (33.025, 37.15, 30),
    (37.15, 43.0, 40),
    (43.0, 45.0, 30),
    (45.0, 55.0, 40),
    (55.0, 57.0, 30),
    (57.0, 58.0, 40),
    (58.0, 60.0, 30),
    (60.0, 65.0, 40),
    (65.0, 68.0, 30),
]

ASSUMPTIONS = [
    "KM 0-5 extended from adjacent bin (no sheet for the port area)",
    "capacity basis: min bin speed / following distance (slowest stretch bounds the chain)",
]


def _integrate(limits, lo, hi):
    """(minutes to traverse [lo,hi], min speed seen, length-weighted mean speed)."""
    t = 0.0
    vmin = None
    wsum = 0.0
    km = 0.0
    for a, b, v in limits:
        ov = min(hi, b) - max(lo, a)
        if ov <= 0:
            continue
        t += 60.0 * ov / v
        vmin = v if vmin is None else min(vmin, v)
        wsum += v * ov
        km += ov
    if km <= 0:
        return None, None, None
    return t, vmin, wsum / km


def span_times_min(lo_km, hi_km):
    """(loaded_min, empty_min) to traverse the chainage span, from the limits."""
    tl, _, _ = _integrate(LOADED_LIMITS, lo_km, hi_km)
    te, _, _ = _integrate(EMPTY_LIMITS, lo_km, hi_km)
    return tl, te


def span_speeds(lo_km, hi_km):
    """{loaded/empty: {min,mean}} km/h over the span."""
    _, lmin, lmean = _integrate(LOADED_LIMITS, lo_km, hi_km)
    _, emin, emean = _integrate(EMPTY_LIMITS, lo_km, hi_km)
    return {"loaded": {"min": lmin, "mean": round(lmean, 1) if lmean else None},
            "empty": {"min": emin, "mean": round(emean, 1) if emean else None}}


def span_capacity_hr(lo_km, hi_km, following_m=None):
    """Loaded-lane capacity of the span: slowest bin speed / following distance."""
    f = float(following_m or FOLLOWING_DISTANCE_M)
    _, vmin, _ = _integrate(LOADED_LIMITS, lo_km, hi_km)
    if not vmin:
        return None
    return vmin * 1000.0 / f
