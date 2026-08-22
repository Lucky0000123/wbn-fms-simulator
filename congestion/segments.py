"""Main-corridor road segments (owner spec, 2026-08-21).

"Firstly you have to consider where is the exact points of KR, TF, POS 12,
FeNi KM15, FeNi KM0 — then how adding trucks affects each other."

One physical stick, four segments. Every stick route traverses the
segments its chainage span overlaps; trucks from EVERY route (either
contractor, any plan) sharing a segment congest it together. BLB is a
separate spur and is NOT on this stick — BLB routes keep per-route
pricing (physics.SPUR_KM), by design.

Per-segment capacity is GEOMETRY class, not observed peaks (the
dayTripsCap lesson): S1 (TF approach, remote single-lane) carries the
60 s-headway class = 60 trucks/hr; S2–S4 (lower mainline, the class the
calibration already assigns to every KR/BLB route running there) carry
the 15 s-headway class = 240 trucks/hr. Today the same shared kilometres
get c=60 for a TF route and c=240 for a KR route — one road must have
one capacity, which is half the owner's complaint.
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

SEGMENTS = [
    {'id': 'S1', 'label': 'TF–KR',        'top_km': 67.8, 'bottom_km': 39.0,
     'length_km': 28.8, 'cap_hr': 60.0},
    {'id': 'S2', 'label': 'KR–POS 12',    'top_km': 39.0, 'bottom_km': 27.0,
     'length_km': 12.0, 'cap_hr': 240.0},
    {'id': 'S3', 'label': 'POS 12–KM15',  'top_km': 27.0, 'bottom_km': 15.0,
     'length_km': 12.0, 'cap_hr': 240.0},
    {'id': 'S4', 'label': 'KM15–coast',   'top_km': 15.0, 'bottom_km': 0.0,
     'length_km': 15.0, 'cap_hr': 240.0},
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


def segment_trucks(all_routes):
    """{route_key: n_trucks} -> {segment_id: combined trucks} (the owner's
    'how many trucks are on each part of the road, from every plan')."""
    load = {s['id']: 0.0 for s in SEGMENTS}
    for route, n in (all_routes or {}).items():
        o, _, d = str(route).partition('>')
        for s, _ov in route_segments(o.strip(), d.strip()):
            load[s['id']] += float(n or 0)
    return load
