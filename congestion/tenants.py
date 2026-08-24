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

# Operating hours per day for tenant fleets. Ours is 2 x 12 h (config.py
# shifts_per_day/hours_per_shift) and there is no reason to assume a tenant on
# the same road keeps a different clock; if one does, this is where it changes.
TENANT_HOURS_PER_DAY = 24.0

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
    """(trips_per_dt, basis). Owner-stated rate wins; otherwise our own
    measured/modelled rate for the proxy road."""
    if tenant.get("trips_per_dt"):
        return float(tenant["trips_per_dt"]), "owner-stated"
    key = (tenant["origin"], tenant["dest"])
    proxies = RATE_PROXY.get(key) or []
    if not proxies:
        return None, "no rate and no proxy road"
    tried = []
    for route, contractor in proxies:
        tried.append(route)
        rate = None
        if rate_lookup is not None:
            rate = rate_lookup(route, contractor)
        if rate is None:
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
                    rate = rec.get("trips_per_DT_per_day")
            except (ImportError, ValueError, ArithmeticError, KeyError,
                    TypeError, OSError):
                rate = None
        if rate:
            note = "" if route == proxies[0][0] else " (fallback)"
            return float(rate), "proxy: our %s (%s) rate%s" % (route, contractor, note)
    return None, "no calibrated proxy road (tried %s)" % ", ".join(tried)


def tenant_rows(rate_lookup=None):
    """The register, resolved: one dict per tenant with rate, flow and segments."""
    out = []
    for t in TENANTS:
        rate, basis = _resolve_rate(t, rate_lookup)
        span = LOADED_SPAN.get((t["origin"], t["dest"]))
        trips_day = (float(t["dt"]) * rate) if rate else None
        flow_hr = (trips_day / TENANT_HOURS_PER_DAY) if trips_day else None
        segs = _span_segments(*span) if span else []
        out.append({
            "name": t["name"], "dt": t["dt"],
            "route": "%s>%s" % (t["origin"], t["dest"]),
            "trips_per_dt": round(rate, 3) if rate else None,
            "rate_basis": basis,
            "trips_per_day": round(trips_day, 1) if trips_day else None,
            "loaded_lane_flow_per_hr": round(flow_hr, 2) if flow_hr else None,
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
        "basis": ("other tenants' fleets on our road: road load only, zero "
                  "tonnes to us. Each fleet contributes its own trips/day as "
                  "flow to the loaded lane of every segment it occupies; "
                  "empty-carriageway legs contribute nothing."),
    }
