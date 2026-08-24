"""Other tenants' trucks on our haul road (owner register, 2026-08-24).

We are not alone on the road. Several tenants run their own fleets over the
same corridor, add ZERO tonnage to our plan, and still take road capacity
from it. Until now the model priced only WBN's own plan, so every trips/DT
it produced was the answer to "what if we had the road to ourselves".

The owner supplied the register directly (2026-08-24):

    MHM        100 DT   TF -> FENI KM15
    POSITION   500 DT   TF -> FENI KM15
    PMA        150 DT   TF -> FENI KM15
    HSM         50 DT   TF -> FENI KM15
    KR>RSF      40 DT   KR -> RSF,     5 trips/DT (owner-stated)
    HUAFEI>RSF 500 DT   HUAFEI -> RSF

RSF sits at KM26, reached from the KM15 side on the way back up to KR.

## What was searched for before assuming anything

scripts/hunt_tenants.py sweeps every CONTRACTOR x COMPANY on the dispatch
view, every ORIGIN/DESTINATION naming a tenant, HAULAGE_CLEAN areas, and the
FMS geofences. Result: MHM, PMA, HSM and RSF appear NOWHERE in either
database. "POSITION" appears only as a DESTINATION on LOYPOLOY->POSITION and
KR_KM_38->POSITION (7,495 and 7,207 tickets, Mar-Aug 2025) — a place on
someone else's haul, not a fleet on ours, and not the tenant in this
register. So there is no history to calibrate these fleets from, and the
owner's instruction stands: price them at the rate WE measure for the same
road. TENANT_TRIPS_PER_DT records which of the two each number is.

## The unit problem, and why this module works in FLOW not trucks

congestion.predictor prices a segment as
    v/c = trucks_on_segment / (our_cycle_min/60) / segment_capacity_hr
i.e. it converts a truck COUNT to a flow using OUR route's tempo. That is
fine while every truck on the segment is running a similar cycle, which is
true across our own plan. It is NOT true for the tenants: KR>RSF turns
5 trips/day against TF>HUAFEI's ~1.2, so 40 KR>RSF trucks push more than
three times the flow that 40 of our TF trucks would. Counting tenant TRUCKS
at our tempo would therefore under-state exactly the fleet the owner is
worried about.

So a tenant contributes a FLOW, computed from its own trips/DT:

    trips/day = DT x trips_per_DT
    trucks/hr on a segment it traverses = trips/day / operating_hours

and the predictor adds that flow to the segment before dividing by capacity.
Same road, same capacity, each fleet at its own tempo.

## Direction: which tenant legs take LOADED-lane capacity

The capacity basis is ONE LOADED LANE (segments.py / speed_limits.py) and v
is loaded-direction flow — one pass per cycle. A vehicle occupies that lane
when it travels COASTWARD (descending chainage), whatever is in its tray.
The owner's own description of the RSF hauls is a direction statement:

  * TF -> FENI KM15 (MHM/POSITION/PMA/HSM): coastward loaded. Counts, on
    every segment from TF (67.8) down to KM15 (15.0) — S1, S2, S3.
  * KR -> RSF: KR (39.0) down to RSF (26.0), coastward. Counts on S2 and
    the top 1 km of S3.
  * HUAFEI -> RSF: "using empty road but also comes back on loaded road
    (but empty truck)". The outbound leg HUAFEI(0) -> RSF(26) climbs on the
    empty carriageway and takes none of the loaded lane. The return leg
    RSF(26) -> HUAFEI(0) runs coastward ON THE LOADED ROAD, empty. An empty
    truck in the loaded lane occupies the same headway as a full one — 50 m
    of following distance is 50 m — so it counts, on S3 and S4.

An empty truck is faster, not smaller. Nothing here discounts it for being
empty; if the owner wants a headway discount for empties it belongs in
speed_limits.py as a capacity statement, not hidden as a half-truck here.

## This adds no tonnes, ever

Tenant fleets are road load only. Nothing in this module touches tonnage,
targets, allocation or fleet pools. It can only make OUR trips/DT lower.
"""
from __future__ import annotations

from .segments import SEGMENTS, NODE_KM

# RSF is not a node on our plan stick, but it is a real place on our road:
# KM26, between POS 12 (27.0) and POS 10 (17.0), per the owner. It lives here
# rather than in segments.NODE_KM because nothing of OURS hauls to it — adding
# it to the plan vocabulary would offer it as a route in the Plan tab.
RSF_KM = 26.0

# Operating hours per day. Used ONLY to report a tenant's daily-average flow
# alongside the figure the model actually prices — see _CLOCK note below.
TENANT_HOURS_PER_DAY = 24.0

# ── The clock (fixed 2026-08-24 after an independent audit) ───────────────
# Tenant flow MUST be expressed on the same clock the predictor already uses
# for our own fleet, or the two fleets are weighed differently on one road.
#
# predictor._nxt does:      flow_hr = n_trucks / (cycle_min / 60)
# i.e. every truck completes ONE loaded pass per CYCLE, and all n are treated
# as in-cycle at once. That is a synchronised/busy-period convention: it is
# deliberately NOT the daily average, because congestion is what happens while
# the trucks are actually out there, not averaged across breaks and shift
# change.
#
# This module used to hand the predictor a DAILY AVERAGE instead:
#     flow_hr = DT * trips_per_day / 24
# Those differ by (cycle + overhead_per_trip) / cycle -- measured 2.21x on the
# TF routes, 2.70x on KR>POS 10 and 4.19x on KR>POS 12. So a tenant truck was
# counted as 2-4x lighter than one of ours on the same kilometre, and the cost
# the app reported for 1,340 tenant DT (~0.0-0.05% on most paths) was an
# artefact of that mismatch rather than a finding about the road.
#
# Now: flow_hr = DT * 60 / cycle_min, with cycle_min taken from the SAME
# proxy-road predict() call that supplies the rate. The cycle is a property of
# the road and the truck, not of the operator's shift pattern, so an owner
# supplied trips/DT still sets the fleet's PRODUCTIVITY (reported as
# trips_per_day) while the road cycle sets its INSTANTANEOUS occupancy.
#
# Consequence, and it is the point: S3 v/c moves 0.28 -> 0.70 and the cost to
# our own trips/DT moves from ~0% to 0.07-1.2%. Only tenant-priced numbers
# move; every clear-road number in the app is untouched, because tenant flow
# is default-OFF everywhere.
_CLOCK = "synchronised: DT x 60 / cycle_min, matching predictor._nxt"

# The register. `trips_per_dt` None -> take OUR measured rate for that road
# (resolved at call time from the calibrated model, see tenant_flow_hr).
TENANTS = [
    {"name": "MHM",        "dt": 100, "origin": "TF",     "dest": "FENI KM15",
     "trips_per_dt": None},
    {"name": "POSITION",   "dt": 500, "origin": "TF",     "dest": "FENI KM15",
     "trips_per_dt": None},
    {"name": "PMA",        "dt": 150, "origin": "TF",     "dest": "FENI KM15",
     "trips_per_dt": None},
    {"name": "HSM",        "dt":  50, "origin": "TF",     "dest": "FENI KM15",
     "trips_per_dt": None},
    {"name": "KR>RSF",     "dt":  40, "origin": "KR",     "dest": "RSF",
     "trips_per_dt": 5.0},
    {"name": "HUAFEI>RSF", "dt": 500, "origin": "HUAFEI", "dest": "RSF",
     "trips_per_dt": None},
]

# Which chainage span of each tenant haul occupies the LOADED lane (see the
# module docstring). (from_km, to_km) or None for "no loaded-lane occupancy".
# Written as data, not as an if-chain, so the direction reading is auditable.
LOADED_SPAN = {
    ("TF", "FENI KM15"): (67.8, 15.0),
    ("KR", "RSF"): (39.0, RSF_KM),
    # Outbound HUAFEI->RSF is on the empty road; the RETURN is the loaded-lane
    # leg, so the span is written return-first.
    ("HUAFEI", "RSF"): (RSF_KM, 0.0),
}

# The road whose measured rate stands in for a tenant with no history. The
# owner's instruction: "use the average trips/DT for them as we are using for
# RIM". Each tenant borrows the rate of the road it actually runs, not a
# single site-wide number, because trips/DT is a property of the haul.
#
# A LIST, tried in order, because being calibrated is a property of the data
# and not of how well the road matches. POS 12>HUAFEI is the exact stretch for
# HUAFEI->RSF but has no calibration (it is not in congestion_params.routes),
# and a first-choice miss must degrade to the next-best road rather than to
# silence: a 500-DT fleet that resolves to None would quietly vanish from the
# road load, which is the opposite of the point of this module.
RATE_PROXY = {
    ("TF", "FENI KM15"): [("TF>FENI KM15", "RIM")],
    ("KR", "RSF"): [("KR>POS 12", "RIM")],
    # HUAFEI->RSF is 26 km each way. First choice is the identical stretch
    # (POS 12>HUAFEI, 27 km); fallback is KR>POS 10 (22 km), the closest
    # calibrated haul of the same length class. Whichever answers is named in
    # rate_basis, so the reader always knows which road the number came from.
    ("HUAFEI", "RSF"): [("POS 12>HUAFEI", "RIM"), ("KR>POS 10", "RIM")],
}


def _span_segments(from_km, to_km):
    """[(segment, overlap_km)] for a chainage span, regardless of direction."""
    lo, hi = min(from_km, to_km), max(from_km, to_km)
    out = []
    for s in SEGMENTS:
        ov = min(hi, s["top_km"]) - max(lo, s["bottom_km"])
        if ov > 0:
            out.append((s, ov))
    return out


def _resolve_rate(tenant, rate_lookup=None):
    """(trips_per_dt, cycle_min, basis) for one tenant.

    Two separate things come back and they answer different questions:

    * `trips_per_dt` is the fleet's PRODUCTIVITY over a day. An owner-stated
      figure wins outright — the owner knows their contractors' output better
      than our model does.
    * `cycle_min` is how long ONE loaded pass takes on that road, and it is a
      property of the ROAD and the truck, not of the operator. It always comes
      from our own calibrated model for the proxy road, even when the owner has
      stated a rate, because a fleet running the same kilometres at the same
      speed limits occupies the lane for the same time per pass. What a higher
      trips/DT actually means is LESS overhead — more passes per day — not a
      faster pass.

    `cycle_min` is what sets road occupancy (see _CLOCK). A tenant that turns
    5 trips/day instead of our 2.8 sustains the same instantaneous flow for
    more of the day; it is not denser on the road at any one moment.
    """
    owner_rate = float(tenant["trips_per_dt"]) if tenant.get("trips_per_dt") else None
    key = (tenant["origin"], tenant["dest"])
    proxies = RATE_PROXY.get(key) or []
    if not proxies:
        # No proxy road means no cycle, so no defensible flow. Say so rather
        # than invent one: a tenant that silently contributes nothing is worse
        # than a tenant that reports it could not be priced.
        return owner_rate, None, ("owner-stated, but no proxy road for a cycle"
                                  if owner_rate else "no rate and no proxy road")
    tried = []
    for route, contractor in proxies:
        tried.append(route)
        rate = None
        cycle = None
        if rate_lookup is not None:
            rate = rate_lookup(route, contractor)
        try:
            from .config import route_params
            from .predictor import predict
            if route_params(route).get("calibrated"):
                # Priced at the tenant's OWN fleet on an otherwise clear
                # road: asking for the rate at our plan's fleet would fold
                # our congestion into their tempo and then feed it back as
                # their load on us — the double-count this repo has paid
                # for before.
                rec = predict(route, float(tenant["dt"]), None,
                              contractor=contractor, mode="road")
                cycle = rec.get("cycle_time_minutes")
                if rate is None:
                    rate = rec.get("trips_per_DT_per_day")
        except (ImportError, ValueError, ArithmeticError, KeyError,
                TypeError, OSError):
            cycle = None
        if owner_rate and cycle:
            note = "" if route == proxies[0][0] else " (fallback)"
            return owner_rate, float(cycle), (
                "owner-stated rate; cycle from our %s (%s)%s" % (route, contractor, note))
        if rate and cycle:
            note = "" if route == proxies[0][0] else " (fallback)"
            return float(rate), float(cycle), (
                "proxy: our %s (%s) rate%s" % (route, contractor, note))
    if owner_rate:
        return owner_rate, None, ("owner-stated, but no calibrated proxy road "
                                  "for a cycle (tried %s)" % ", ".join(tried))
    return None, None, "no calibrated proxy road (tried %s)" % ", ".join(tried)


def tenant_rows(rate_lookup=None):
    """The register, resolved: one dict per tenant with rate, flow and segments."""
    out = []
    for t in TENANTS:
        rate, cycle, basis = _resolve_rate(t, rate_lookup)
        span = LOADED_SPAN.get((t["origin"], t["dest"]))
        trips_day = (float(t["dt"]) * rate) if rate else None
        # The priced figure: one loaded pass per cycle, every truck in cycle,
        # exactly as predictor._nxt treats ours (_CLOCK). No cycle -> no flow,
        # and the row says why instead of quietly contributing zero.
        flow_hr = (float(t["dt"]) * 60.0 / cycle) if cycle else None
        avg_hr = (trips_day / TENANT_HOURS_PER_DAY) if trips_day else None
        segs = _span_segments(*span) if span else []
        out.append({
            "name": t["name"], "dt": t["dt"],
            "route": "%s>%s" % (t["origin"], t["dest"]),
            "trips_per_dt": round(rate, 3) if rate else None,
            "rate_basis": basis,
            "cycle_min": round(cycle, 1) if cycle else None,
            "trips_per_day": round(trips_day, 1) if trips_day else None,
            "loaded_lane_flow_per_hr": round(flow_hr, 2) if flow_hr else None,
            # Reported for comparison only — NOT what the predictor is given.
            # Keeping it visible is how the clock mismatch was caught.
            "daily_average_flow_per_hr": round(avg_hr, 2) if avg_hr else None,
            "flow_basis": _CLOCK,
            "loaded_span_km": list(span) if span else None,
            "segments": [s["id"] for s, _ov in segs],
        })
    return out


def tenant_segment_flow_hr(rate_lookup=None):
    """{segment_id: extra trucks/hr in the LOADED lane} from all tenants.

    This is what the predictor adds to our own flow before dividing by the
    segment's geometric capacity. Flow, not trucks: see the module docstring.
    """
    load = {s["id"]: 0.0 for s in SEGMENTS}
    for row in tenant_rows(rate_lookup):
        f = row.get("loaded_lane_flow_per_hr")
        if not f:
            continue
        for sid in row["segments"]:
            load[sid] += float(f)
    return load


def tenant_summary(rate_lookup=None):
    """Everything a UI or an Excel note needs to explain the extra column."""
    rows = tenant_rows(rate_lookup)
    return {
        "tenants": rows,
        "segment_flow_hr": {k: round(v, 2)
                            for k, v in tenant_segment_flow_hr(rate_lookup).items()},
        "segment_capacity_hr": {s["id"]: s["cap_hr"] for s in SEGMENTS},
        "total_dt": sum(t["dt"] for t in TENANTS),
        "hours_per_day": TENANT_HOURS_PER_DAY,
        "flow_basis": _CLOCK,
        "basis": ("other tenants' fleets on our road: road load only, zero "
                  "tonnes to us. Each fleet occupies the loaded lane for one "
                  "pass per road cycle — the same clock the model already uses "
                  "for our own trucks — on every segment it crosses; "
                  "empty-carriageway legs contribute nothing."),
    }
