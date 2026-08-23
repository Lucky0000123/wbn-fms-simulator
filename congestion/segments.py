"""Main-corridor road segments (owner spec, 2026-08-21).

"Firstly you have to consider where is the exact points of KR, TF, POS 12,
FeNi KM15, FeNi KM0 — then how adding trucks affects each other."

One physical stick, four segments. Every stick route traverses the
segments its chainage span overlaps; trucks from EVERY route (either
contractor, any plan) sharing a segment congest it together.

BLB is a separate spur and is NOT on this stick for *pricing* — a BLB
route's own road time still comes from its calibrated per-route distance
(physics.SPUR_KM), by design, because the spur is most of its haul.  But
a BLB truck does physically run the lower mainline from the junction
(SPUR_JOIN_KM) down to its tip, so it is COUNTED onto those segments by
segment_trucks() — same reading congestion/sections.py and
plan_shared_flow.py already take.  Omitting it under-counted S4, the
tightest section, by ~28% on the real 2026-09-03 plan: the trucks were
on the road, the road just could not see them.

Per-segment capacity is OFFICIAL GEOMETRY, not observed peaks (the
dayTripsCap lesson): slowest posted bin speed / 50 m following distance,
ONE loaded lane, per speed_limits.py.  It gives 400 trucks/hr on S4 and
600 on S1–S3.  It replaced the earlier 60/240 headway-CLASS assumption,
which sat 2.5–10x low and manufactured an "S1 bottleneck" at v/c 2.4.
One road, one capacity — a segment's capacity is a property of the
segment, never of whichever route happens to ask about it.
"""
from __future__ import annotations

NODE_KM = {
    'TF': 67.8, 'TOFU': 67.8,
    'KR': 39.0, 'KRENE': 39.0,
    'POS 12': 27.0, 'POS12': 27.0,
    'POS 14': 26.1, 'POS14': 26.1, 'POS 15': 26.1, 'POS 16': 26.1,
    'POS 10': 17.0, 'POS10': 17.0,
    'FENI KM15': 15.0, 'FENI 15': 15.0,
    'CRUSHER': 3.0,
    'FENI KM0': 0.0, 'FENI 0': 0.0, 'HUAFEI': 0.0, 'BSE': 0.0,
}

# Spur origins are NOT on the stick, but they JOIN it: a BLB truck runs the
# spur and then the lower mainline from this chainage to its destination.
# Survey (data/haul_road_chainage_public.csv, 2026-08-23): the mainline is
# three contiguous runs on ONE datum (CRD 0.000-7.850, KR 7.875-38.975,
# TOFU 39.000-67.800), and road BLB is surveyed on that same datum — its
# km 2.450 point sits 0.2 m from the mainline's own km 2.450 on CRD, the
# polylines then separating to 87 m by km 2.575. physics.py agrees from the
# other direction ("joins at ~2.5 km + 17.4 km spur"; SPUR_KM 19.9 =
# 2.5 + 17.4), to ~50 m. ONE home for this number — import it, never retype.
# Charging BLB to a spur pseudo-section ALONE under-counts S4 (the tightest
# section) by 28% on the real 2026-09-03 plan; pinning BLB at 67.8 (the old
# NODE_KM bug) over-counted it across the whole mainline instead.
SPUR_JOIN_KM = {'BLB': 2.45}

# physics owns route distances and the coastal-destination set; it imports
# nothing from this package, so this is not a cycle.
from . import physics

# Capacity now comes from the OFFICIAL speed-limit sheets + road geometry
# (speed_limits.py; owner documents 2026-08-22): one loaded lane, no
# overtaking, capacity = slowest bin speed / following distance. The old
# 60/240 headway-class numbers were assumptions and sat 2.5-10x LOW — the
# "S1 bottleneck" at v/c 2.4 was an assumption artifact, owner-caught.
from .speed_limits import (span_capacity_hr, span_speeds, span_times_min,
                           FOLLOWING_DISTANCE_M, SOURCE_DOC)

# The BLB spur has NO speed-limit sheet (speed_limits.py says so on its face).
# The estimate already established elsewhere in the repo — plan_shared_flow.py
# SPUR_SPEED_FLOOR_KMH / SPUR_LANE_CAP_TPH, and the "spur estimate 20 km/h ÷
# 50 m following, one lane per direction (no limit sheet)" basis string it
# renders — is reused verbatim rather than a new number being invented. 20 km/h
# is the slowest bin posted anywhere on the mainline, so it is the conservative
# floor, and the divisor is the same mining-standard following distance the
# official sheets are read with.
SPUR_SPEED_FLOOR_KMH = 20.0
SPUR_LANE_CAP_HR = SPUR_SPEED_FLOOR_KMH * 1000.0 / FOLLOWING_DISTANCE_M   # 400/hr
SPUR_CAP_BASIS = ("spur estimate %g km/h ÷ %g m following, ONE lane per "
                  "direction (no limit sheet)"
                  % (SPUR_SPEED_FLOOR_KMH, FOLLOWING_DISTANCE_M))


def _seg(id_, label, top, bottom):
    caps = span_capacity_hr(bottom, top)
    spd = span_speeds(bottom, top)
    tl, te = span_times_min(bottom, top)
    return {'id': id_, 'label': label, 'top_km': top, 'bottom_km': bottom,
            'length_km': round(top - bottom, 1),
            'cap_hr': caps or 240.0,
            'speeds': spd,
            'limit_time_loaded_min': round(tl, 1) if tl else None,
            'limit_time_empty_min': round(te, 1) if te else None,
            'following_m': FOLLOWING_DISTANCE_M,
            'source': SOURCE_DOC}

SEGMENTS = [
    _seg('S1', 'TF–KR',       67.8, 39.0),
    _seg('S2', 'KR–POS 12',   39.0, 27.0),
    _seg('S3', 'POS 12–KM15', 27.0, 15.0),
    _seg('S4', 'KM15–coast',  15.0,  0.0),
]


def node_km(name):
    return NODE_KM.get(str(name or '').strip().upper())


def route_segments(origin, dest):
    """[(segment, overlap_km)] the route traverses; [] for non-stick (BLB…)."""
    a, b = node_km(origin), node_km(dest)
    if a is None or b is None or a == b:
        return []
    lo, hi = min(a, b), max(a, b)
    out = []
    for s in SEGMENTS:
        ov = min(hi, s['top_km']) - max(lo, s['bottom_km'])
        if ov > 0:
            out.append((s, ov))
    return out


def mainline_windows(origin, dest):
    """[(segment, overlap_km)] of the MAINLINE this route physically occupies.

    Superset of route_segments(): identical for stick routes, and for a spur
    origin it adds the lower-mainline run from the junction (SPUR_JOIN_KM) to
    the destination.  Kept separate from route_segments() on purpose —
    route_segments() is the "is this route priced on the stick?" predicate that
    congestion.predictor and plan_shared_flow branch on, and a spur route is
    still priced on its own calibrated distance.  Occupancy and pricing are
    different questions; giving them one function would have silently changed
    two modules this one does not own.

    Two exclusions, exactly the ones congestion.sections and plan_shared_flow
    already apply:
      * physics.BLB_COASTAL_DEST (POS 14/15/16) — those tips sit ON the spur,
        so the truck never reaches the junction;
      * a numeric guard — if the implied mainline run is longer than the
        route's own calibrated distance, the mainline is not the way there.
    """
    o = str(origin or '').strip().upper()
    d = str(dest or '').strip().upper()
    a, b = node_km(o), node_km(d)
    if a is not None and b is not None:
        return route_segments(o, d)
    join = SPUR_JOIN_KM.get(o)
    if join is None or b is None:
        return []
    if d in physics.BLB_COASTAL_DEST:
        return []
    lo, hi = min(join, b), max(join, b)
    dist = physics.route_distance_km(o, d)
    if dist and (hi - lo) > float(dist) + 0.5:
        return []
    out = []
    for s in SEGMENTS:
        ov = min(hi, s['top_km']) - max(lo, s['bottom_km'])
        if ov > 0:
            out.append((s, ov))
    return out


def route_road_capacity_hr(origin, dest):
    """(trucks/hr, basis) — OFFICIAL geometric capacity of the road this route
    runs on, or (None, None) when the route's geometry is unknown.

    Not an observed peak and not a headway class: slowest posted bin speed /
    following distance, ONE loaded lane (speed_limits.py, owner documents
    2026-08-22).  A chain is bounded by its tightest stretch — the same
    min-bin reading span_capacity_hr takes inside one window — so a route that
    crosses several windows takes the MIN over them.  A spur leg has no sheet
    and carries SPUR_LANE_CAP_HR.
    """
    o = str(origin or '').strip().upper()
    wins = mainline_windows(o, dest)
    caps, parts = [], []
    for s, _ov in wins:
        c = s.get('cap_hr')
        if c:
            caps.append(float(c))
            parts.append(s['id'])
    if o in SPUR_JOIN_KM:
        caps.append(float(SPUR_LANE_CAP_HR))
        parts.append('%s spur' % o)
    if not caps:
        return None, None
    cap = min(caps)
    basis = ("official speed limits: min bin speed x 1000 / %g m following, "
             "ONE loaded lane; tightest of %s"
             % (FOLLOWING_DISTANCE_M, '+'.join(parts)))
    if o in SPUR_JOIN_KM:
        basis += " (%s)" % SPUR_CAP_BASIS
    return cap, basis


def segment_trucks(all_routes):
    """{route_key: n_trucks} -> {segment_id: combined trucks} (the owner's
    'how many trucks are on each part of the road, from every plan').

    Counts spur-origin routes on the mainline segments they actually traverse
    (mainline_windows), not only on the stick routes — see module docstring.
    """
    load = {s['id']: 0.0 for s in SEGMENTS}
    for route, n in (all_routes or {}).items():
        o, _, d = str(route).partition('>')
        for s, _ov in mainline_windows(o.strip(), d.strip()):
            load[s['id']] += float(n or 0)
    return load
