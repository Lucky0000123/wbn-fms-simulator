"""plan_simulator.py — Task 4: the what-if engine.

WHAT A PLANNER ASKS, AND WHAT THIS RETURNS
"30 trucks TF to KR, 20 trucks POS 12 to FENI — how long per trip, how much do
I move, and where do they collide?"

The engine answers with three kinds of number, and it labels which is which on
every field, because they do not deserve equal trust:

    measured    from observed history — route cycle times, dwell times, payload,
                and each point's demonstrated hourly throughput ceiling
    derived     arithmetic on measured values — trips per shift, tonnes
    assumed     the shift length a planner supplies. NOT availability: a
                caller-supplied availability is accepted and ignored for
                tonnage (see the note in simulate()), because the effective
                cycle already contains downtime. Availability sizes the roster.

THE ONE THING IT DELIBERATELY WILL NOT DO
It will not scale cycle time with truck count. The brief asked for that, and
four independent tests could not identify the effect: cycle time falls as
loader utilisation rises, and the OLS coefficient that appears to show queueing
reverses sign once collinearity is removed (see capacity_model.py and
simulator_model.audit_congestion_signs). Deployment is endogenous — trucks are
sent where conditions are good — so any fitted "add trucks, add delay" curve
would encode the reverse of the truth.

WHAT IT DOES INSTEAD, WHICH IS THE ACTIONABLE HALF
Capacity. If a plan asks a loading point for more trucks per hour than it has
ever achieved in six months, those trucks queue and the extra tonnes do not
arrive. That is a measured ceiling, and it is exactly the failure mode a
planner needs to be warned about when two plans share a loader. So the output
says "POS 12 is at 113% of its demonstrated ceiling, expect ~13 trucks' worth
of production not to materialise" rather than inventing a minutes-per-truck
penalty.

Shared points are still detected and reported, and combined demand is still
summed across plans. The difference is that the consequence is expressed in
capacity terms, where there is evidence, instead of in cycle-time terms, where
there is none.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# A 12-hour shift is the site's roster. Overridable per request.
DEFAULT_SHIFT_MIN = 720
# The shift length the effective cycle was MEASURED at. simulator_model derives
# effective_cycle_min as (truck_shifts x 720) / trips, so 720 is not merely a
# default -- it is the calibration point, and any other value extrapolates.
# Keep the two in step: if the derivation's shift changes, this must change too.
CALIBRATION_SHIFT_MIN = 720.0
# Fraction of the shift to divide by when the caller supplies no override.
#
# This is 1.0, not 0.85, and the reason matters. Trips per truck are predicted by
# dividing the shift by the route's EFFECTIVE cycle, which is measured as
# shift-minutes per completed trip. That measurement already contains every
# non-hauling minute: the empty return, the shovel queue, refuelling, crib
# breaks, and any part of the shift the truck was not hauling at all.
#
# Multiplying by an availability allowance on top would deduct that time twice.
# The previous 0.85 was applied to the weigh-to-weigh interval instead, which
# omits the between-trip gap entirely, and the combination overpredicted trips
# by roughly 5x. A caller who genuinely wants to model a shortened shift should
# reduce `shift_minutes`, not this factor.
DEFAULT_AVAILABILITY = 1.0
# Measured hauling-truck availability, for reporting only. Over 215 days it is
# 83.6% against the 85% that used to be assumed, so the old assumption was close
# on this axis; the error was the cycle definition, not the allowance.
MEASURED_HAUL_AVAILABILITY = 0.836
# Measured mechanical availability of haul trucks: the share of rostered shifts a
# truck was NOT broken down or in planned maintenance. From 170,899 truck-shifts
# in EQUIPMENTS_HOURLY_STATUS over 2026-04-01..06-30.
#
# This is used ONLY for fleet sizing ("roster this many to keep N hauling"). It
# is deliberately NOT applied to tonnage. Tested against observed tonnage per
# truck-shift on 44 routes: the current bias is +5.5%, and multiplying by 0.836,
# 0.850, 0.765 or 0.451 moves it to -11.8%, -10.3%, -19.3% and -52.4%
# respectively. Every factor makes it worse, because the effective cycle already
# contains downtime. Two independent measurements confirm that: availability x
# utilisation = 0.390 of a rostered shift is working time, and the weighbridge
# observes 0.203 of the repeat interval, which doubles to 0.406 once the
# invisible empty-return leg is counted. They agree within 0.016.
MEASURED_MECHANICAL_AVAILABILITY = 0.720
# Site-wide ratio of effective cycle to weigh-to-weigh cycle (389 / 83 min),
# used only for a route with no measured history. Per-route ratios span 1.2x to
# 24.8x, so this is a weak fallback and rows using it say so in their basis.
FALLBACK_EFFECTIVE_RATIO = 4.7
# Rain slows loading; this is the observed median penalty across points, used
# only when the caller asks for a wet scenario without naming a point.
FALLBACK_WET_UPLIFT = 1.08

_CACHE: dict[str, pd.DataFrame | None] = {}


def _load(name: str, path: str) -> pd.DataFrame | None:
    if name not in _CACHE:
        try:
            _CACHE[name] = pd.read_csv(path)
        except Exception:                                   # noqa: BLE001
            _CACHE[name] = None
    return _CACHE[name]


def _routes() -> pd.DataFrame | None:
    return _load("routes", os.path.join(DATA, "route_lookup.csv"))


def _capacity() -> pd.DataFrame | None:
    return _load("capacity", os.path.join(DATA, "point_capacity.csv"))


def _route_availability() -> pd.DataFrame | None:
    """Per-route availability with an explicit basis column.

    Availability is measured from EQUIPMENTS_HOURLY_STATUS, which covers the
    contractors that report equipment status - trucks carrying 30.3% of training
    tonnage. The other 69.7% have no measured availability at all, so a route
    served by them gets the fleet prior and is labelled as such rather than
    being quoted a figure measured on somebody else's trucks.
    """
    return _load("route_avail", os.path.join(DATA, "route_availability.csv"))


def _dwell() -> pd.DataFrame | None:
    return _load("dwell", os.path.join(DATA, "dwell_model_results.csv"))


def reset_cache() -> None:
    _CACHE.clear()


def _lookup_route(route: str, source: str, dest: str) -> tuple[dict, str]:
    """Find this route's observed history, or say plainly that there is none."""
    r = _routes()
    if r is None or r.empty:
        return {}, "no route history available"
    hit = r[r["route"].astype(str).str.upper() == str(route).upper()]
    if not hit.empty:
        return hit.iloc[0].to_dict(), "measured"
    # An unseen route is not silently averaged: the caller is told the number
    # is a fallback, so a plan for a road that has never run is visibly weaker
    # evidence than one for a road with six months of history.
    same_src = r[r["source"].astype(str).str.upper() == str(source).upper()]
    if not same_src.empty:
        m = same_src.median(numeric_only=True).to_dict()
        m["route"] = route
        return m, "estimated from other routes out of %s (this route unseen)" % source
    m = r.median(numeric_only=True).to_dict()
    m["route"] = route
    return m, "estimated from the site-wide median (route and source unseen)"


def _point_capacity(point: str, kind: str) -> dict | None:
    c = _capacity()
    if c is None or c.empty:
        return None
    hit = c[(c["point"].astype(str).str.upper() == str(point).upper())
            & (c["kind"] == kind)]
    return hit.iloc[0].to_dict() if not hit.empty else None


def _point_dwell(point: str, kind: str, wet: bool) -> tuple[float | None, str]:
    d = _dwell()
    if d is None or d.empty:
        return None, "no dwell history"
    hit = d[(d["point"].astype(str).str.upper() == str(point).upper())
            & (d["kind"] == kind)]
    if hit.empty:
        return None, "point unseen"
    row = hit.iloc[0]
    col = "wet_min" if wet else "dry_min"
    v = row.get(col)
    if pd.notna(v):
        return float(v), "measured (%s conditions)" % ("wet" if wet else "dry")
    v = row.get("median_min")
    if pd.notna(v):
        v = float(v) * (FALLBACK_WET_UPLIFT if wet else 1.0)
        return v, ("measured median, wet uplift applied" if wet
                   else "measured median")
    return None, "no usable dwell value"


def _roster(n: int, route: str) -> tuple:
    """Trucks to roster to keep n hauling, and the basis of the figure.

    Returns (roster, availability_used, basis). basis is "measured" when the
    route's own trucks are in the availability data, and "fleet_prior" when the
    figure is extrapolated. Route-level availability spans 0.695..0.795 across
    the 23 measured routes, so the 0.720 prior is a reasonable stand-in - but a
    planner is told which one they got.
    """
    if not n:
        return 0, None, "n/a"
    a = MEASURED_MECHANICAL_AVAILABILITY
    basis = "fleet_prior"
    ra = _route_availability()
    if ra is not None and "route" in ra.columns:
        m = ra[ra.route.astype(str).str.upper() == str(route).upper()]
        if len(m):
            row = m.iloc[0]
            if str(row.get("basis")) == "measured" and pd.notna(
                    row.get("route_availability")):
                a = float(row["route_availability"])
                basis = "measured"
    return int(np.ceil(n / a)), round(a, 4), basis


def simulate(payload: dict) -> dict:
    """Run a plan and return per-route predictions plus shared-point warnings."""
    plans = payload.get("plans") or []
    if not plans:
        return {"error": "no plans supplied", "results": [], "summary": {}}

    shift_min = float(payload.get("shift_minutes", DEFAULT_SHIFT_MIN))

    # SHIFT LENGTH IS AN EXTRAPOLATION AWAY FROM 720, AND SAYS SO.
    #
    # Audited 2026-07-31 as the last caller-supplied field that scales tonnage.
    # There is NO UI/engine disagreement of the availability kind: the UI sends
    # 720 and DEFAULT_SHIFT_MIN is 720. But trips scale exactly linearly with
    # this field, and the denominator they divide does not:
    #
    #   effective_cycle_min = (truck_shifts x 720) / trips     <- 720 hardcoded
    #                                                             in simulator_model
    #
    # So the effective cycle is "minutes of a TWELVE-HOUR shift per completed
    # trip". It bundles per-trip time with per-shift overhead that does not
    # scale -- one meal break, one refuel, one pre-start, one handover. Writing
    # 720 = n.V + F for n trips of variable cost V and fixed overhead F, the
    # model predicts n' = S.n/720 while the truth is n' = (S - F)/V, so it
    # OVERPREDICTS by F(1 - S/720)/V: too many trips for a short shift, too few
    # for a long one.
    #
    # F and V cannot be separated from this data, and that is measured, not
    # assumed: 98.48% of 538,586 truck-shifts in availability_per_truck.csv are
    # exactly 12.0 hours, so shift length is a constant and no regression can
    # identify the split. Fabricating an F would be inventing the number.
    #
    # The honest move is therefore to keep the field -- planners do run other
    # shift lengths -- and label the answer as an extrapolation with its
    # direction, rather than to silently return a linear guess.
    shift_note = None
    if abs(shift_min - CALIBRATION_SHIFT_MIN) > 1.0:
        longer = shift_min > CALIBRATION_SHIFT_MIN
        shift_note = (
            "shift_minutes=%.0f is an EXTRAPOLATION. The effective cycle that "
            "trips divide by was measured as (truck-shifts x %.0f) / trips, so "
            "it is calibrated at a %.0f-minute shift; 98.5%% of 538,586 measured "
            "truck-shifts are exactly 12.0 h, leaving no variation from which to "
            "separate per-shift overhead (break, refuel, pre-start, handover) "
            "from per-trip time. Trips here scale linearly, which %s the fixed "
            "overhead and so likely %s trips for this shift length. Treat the "
            "tonnage as indicative, not measured."
            % (shift_min, CALIBRATION_SHIFT_MIN, CALIBRATION_SHIFT_MIN,
               "under-weights" if longer else "over-weights",
               "UNDER-states" if longer else "OVER-states"))

    # A caller-supplied `availability` is ACCEPTED and then DELIBERATELY IGNORED
    # for tonnage. It used to be honoured:
    #
    #     avail = float(payload.get("availability", DEFAULT_AVAILABILITY))
    #
    # and static/js/plan_simulator.js sent 0.85 on every request, so the shipped
    # UI quoted 2,586 t where the engine's own measured basis gives 3,042 t for
    # 30 trucks on BLB>FENI KM0 -- 15% low, reintroducing through the front door
    # exactly the 0.85 assumption this project measured as wrong (bias +5.5%
    # with no factor, -10.3% at x0.85). Gate J52 did not catch it because it
    # builds its own payload without the key and so only ever exercised the
    # default path; the real caller was the one supplying it.
    #
    # The key is not rejected, because failing a request is worse than ignoring
    # a parameter that must not exist. It is echoed back as ignored, with the
    # reason, so a caller learns rather than silently disagreeing with the API.
    avail = DEFAULT_AVAILABILITY
    _avail_req = payload.get("availability")
    avail_ignored = None
    if _avail_req is not None:
        try:
            _r = float(_avail_req)
        except (TypeError, ValueError):
            _r = None
        if _r is not None and abs(_r - DEFAULT_AVAILABILITY) > 1e-9:
            avail_ignored = (
                "caller supplied availability=%.3f; IGNORED for tonnage. The "
                "effective cycle is shift-minutes per completed trip and "
                "already contains downtime, queueing, empty running and "
                "breaks, so an availability allowance double-counts it. "
                "Measured: no factor gives bias +5.5%%, x0.85 gives -10.3%%. "
                "Availability sizes the ROSTER instead -- see "
                "fleet_sizing.trucks_to_roster." % _r
            )

    wet = str(payload.get("weather", "dry")).lower() in ("wet", "rain", "rainy")

    # Combined demand at every point, summed ACROSS plans. This is where two
    # plans that load from the same source become one contention problem.
    src_trucks: dict[str, float] = {}
    dst_trucks: dict[str, float] = {}
    src_plans: dict[str, list] = {}
    dst_plans: dict[str, list] = {}
    for p in plans:
        # Foreign / road-only plans (IWIP, another mine on our roads) do NOT
        # contend for OUR loading/dumping points — they belong to a different
        # operation. They only add congestion on the shared corridor, handled
        # after the trip resolution below. So they are excluded from the
        # loading-point demand here.
        if p.get("foreign"):
            continue
        s, d = str(p.get("source", "")).upper(), str(p.get("destination", "")).upper()
        n = float(p.get("n_trucks", 0) or 0)
        src_trucks[s] = src_trucks.get(s, 0) + n
        dst_trucks[d] = dst_trucks.get(d, 0) + n
        src_plans.setdefault(s, []).append(p.get("route") or "%s>%s" % (s, d))
        dst_plans.setdefault(d, []).append(p.get("route") or "%s>%s" % (s, d))

    results, warnings = [], []

    # FIRST PASS: resolve every plan's own cycle time and trip count.
    #
    # This pass exists because demand at a shared point must be ONE number.
    # Computing it inside the per-plan loop meant each plan estimated its
    # neighbours' trips using its OWN cycle time, so two plans sharing TF
    # reported 86% and 45% utilisation of the same loader in the same shift.
    # Both cannot be true. Trips are therefore resolved for all plans first,
    # each with its own cycle time, and only then summed per point.
    resolved = []
    working_min = shift_min * avail
    for p in plans:
        src = str(p.get("source", "")).upper()
        dst = str(p.get("destination", "")).upper()
        route = str(p.get("route") or "%s>%s" % (src, dst)).upper()
        n = float(p.get("n_trucks", 0) or 0)
        hist, basis = _lookup_route(route, src, dst)
        cycle = float(hist.get("median_cycle_min") or 0) or None

        load_min, load_basis = _point_dwell(src, "loading", wet)
        dump_min, dump_basis = _point_dwell(dst, "dumping", wet)
        if load_min is None:
            load_min, load_basis = float(hist.get("median_load_min") or 0), "route history"
        if dump_min is None:
            dump_min, dump_basis = float(hist.get("median_dump_min") or 0), "route history"

        # `cycle_dry = cycle` stood here, with a comment saying it was kept "so
        # the same proportional uplift can be applied to the effective cycle
        # below". Both are removed: ruff F841 flagged the variable as unused, and
        # it was unused BECAUSE the weather fix established that rain must never
        # reach the effective cycle. The comment therefore described the exact
        # behaviour that must not happen, which is worse than the dead line --
        # a future reader could have "restored" it.
        #
        # RAIN LENGTHENS THE DWELL AT BOTH ENDS, SO THE CYCLE MUST CARRY BOTH.
        #
        # This used to add only the LOADING point's wet penalty. Because
        # `implied_travel_time_min` is the residual `cycle - load - dump`, the
        # DUMPING point's penalty was subtracted from travel and never added
        # back, so the model reported trucks travelling FASTER in the rain on
        # 11 of 14 routes measured -- typically -1.1 min, and -7.8 min on
        # KR>POS 10. The signature was exact: dTravel == -dDump on every route.
        #
        # The uplift is derived from the dwell deltas ACTUALLY APPLIED rather
        # than re-read from wet_penalty_min, because _point_dwell has its own
        # fallback path (median x FALLBACK_WET_UPLIFT for a point with no
        # measured wet figure) whose effect does not appear in that column.
        # Deriving it guarantees the two stay in step however each point was
        # resolved.
        #
        # Consequence, and it is the honest one: implied travel time is now
        # weather-INVARIANT. The wet/dry split in dwell_model_results.csv is
        # measured AT POINTS; nothing in this dataset measures a rain effect on
        # road speed. FMS_CONGESTION_SEG carries segment speeds but retains only
        # ~2 weeks and has no rain join, so a travel penalty would have to be
        # invented. Rain's measured effect stays where it was measured.
        if cycle and wet:
            dry_load, _ = _point_dwell(src, "loading", False)
            dry_dump, _ = _point_dwell(dst, "dumping", False)
            d_load = (load_min - dry_load) if (load_min is not None
                                               and dry_load is not None) else None
            d_dump = (dump_min - dry_dump) if (dump_min is not None
                                               and dry_dump is not None) else None
            if d_load is None and d_dump is None:
                # Neither end has a measured wet figure. Fall back to the
                # site-wide uplift rather than silently claiming rain does
                # nothing at all.
                cycle = cycle * FALLBACK_WET_UPLIFT
            else:
                cycle = cycle + (d_load or 0.0) + (d_dump or 0.0)

        # TWO DIFFERENT CYCLE FIGURES, USED FOR TWO DIFFERENT THINGS.
        #
        # `cycle` (weigh-to-weigh) is what a planner recognises as trip time and
        # is what gets reported. `effective_cycle` is shift-minutes per completed
        # trip, measured per route, and is the only correct denominator for trips
        # per shift. Using the former to count trips overpredicted them by ~5x,
        # because the weighbridge interval excludes the empty return, the shovel
        # queue, refuelling and breaks.
        eff = hist.get("effective_cycle_min")
        eff = float(eff) if eff and float(eff) > 0 else None
        eff_basis = str(hist.get("effective_cycle_basis") or "")
        if eff is None:
            # No measured effective cycle: fall back to the observed site-wide
            # ratio rather than to the weigh-to-weigh figure, which would
            # reintroduce the overprediction.
            eff = (cycle or 0) * FALLBACK_EFFECTIVE_RATIO
            eff_basis = ("estimated: no route history, weigh-to-weigh x %.1f "
                         "site-wide ratio" % FALLBACK_EFFECTIVE_RATIO)
        # RAIN IS DELIBERATELY NOT APPLIED TO THE EFFECTIVE CYCLE.
        #
        # An earlier version scaled it by (wet cycle / dry cycle), which would
        # have reduced predicted tonnage on wet plans. Measured, that is not
        # what happens. Within route and month — so the wet season is not being
        # compared against the dry one — rain moves tonnage by a median +0.1%
        # and only 49% of 122 comparable route-months show a reduction. It is a
        # coin flip. Rain's effect on cycle time is the same: +0.2% median,
        # slower in 51% of 104 cells.
        #
        # Rain DOES lengthen loading dwell at specific points (POS 12 +13.7 min,
        # POS CBB +15.8 min, measured), which is why the reported load and cycle
        # times still carry the wet uplift. But the fleet evidently absorbs it,
        # so pushing it through to tonnage would warn a planner about a
        # production loss the data does not show. The wet effect stays where it
        # is measured and out of the number it does not support.

        trips_per_truck = (working_min / eff) if eff else 0.0
        resolved.append({
            "plan": p, "route": route, "source": src, "destination": dst,
            "n": n, "cycle": cycle, "basis": basis,
            "effective_cycle": eff, "effective_basis": eff_basis,
            "load_min": load_min, "load_basis": load_basis,
            "dump_min": dump_min, "dump_basis": dump_basis,
            "trips_per_truck": trips_per_truck,
            "fleet_trips": trips_per_truck * n,
            "payload_t": float(hist.get("median_payload_t") or 0),
        })

    # ── Foreign / road-only traffic (IWIP, other mines) ──────────────────────
    # A plan flagged `foreign` adds NO WMT for us, but its trucks still occupy
    # the shared FENI corridor and drag our trips/DT down. The coefficient is the
    # SAME measured one the Capability tab's IWIP-impact panel uses — this is not
    # a new assumption, it is that measured relationship applied at plan time.
    # Only foreign traffic applies drag: our own extra trucks do NOT self-congest
    # (that effect is not identifiable in the data), so the honesty rule holds.
    OTHER_TRAFFIC_COEF = -0.00035   # trips/DT per extra FENI-corridor trip; mirrors static/js/main.js:239

    def _is_feni(x):
        return "FENI" in str(x).upper()

    foreign_feni_trips = sum(r["fleet_trips"] for r in resolved
                             if r["plan"].get("foreign") and _is_feni(r["destination"]))
    drag_per_dt = OTHER_TRAFFIC_COEF * foreign_feni_trips        # <= 0
    drag_routes: list = []
    drag_tonnage_cost = 0.0
    if drag_per_dt < 0:
        for r in resolved:
            if r["plan"].get("foreign") or not _is_feni(r["destination"]):
                continue
            if r["trips_per_truck"] <= 0:
                continue
            new_tpt = max(0.0, r["trips_per_truck"] + drag_per_dt)
            lost_trips = (r["trips_per_truck"] - new_tpt) * r["n"]
            r["trips_per_truck"] = new_tpt
            r["fleet_trips"] = new_tpt * r["n"]
            drag_tonnage_cost += lost_trips * r["payload_t"]
            drag_routes.append(r["route"])

    # Total trips demanded of each loading point, summed across all WBN plans
    # (foreign plans are a different operation and excluded).
    demand_by_src: dict[str, float] = {}
    for r in resolved:
        if r["plan"].get("foreign"):
            continue
        demand_by_src[r["source"]] = (demand_by_src.get(r["source"], 0.0)
                                      + r["fleet_trips"])

    for r in resolved:
        # Foreign / road-only line: report its corridor load, but no WMT. Its
        # effect on us is the drag already applied to the production routes above.
        if r["plan"].get("foreign"):
            fcycle, fload, fdump = r["cycle"], r["load_min"], r["dump_min"]
            results.append({
                "route": r["route"], "source": r["source"], "destination": r["destination"],
                "n_trucks": int(r["n"]), "foreign": True,
                "predicted_cycle_time_min": round(fcycle, 1) if fcycle else None,
                "effective_cycle_min": round(r["effective_cycle"], 1) if r["effective_cycle"] else None,
                "predicted_load_time_min": round(fload, 1) if fload is not None else None,
                "predicted_dump_time_min": round(fdump, 1) if fdump is not None else None,
                "implied_travel_time_min": round(max((fcycle or 0) - (fload or 0) - (fdump or 0), 0.0), 1),
                "trips_per_shift_per_truck": round(r["trips_per_truck"], 2),
                "total_trips": round(r["fleet_trips"], 1),
                "avg_payload_t": round(r["payload_t"], 2),
                "planned_production_t": 0, "achievable_production_t": 0,
                "trucks_to_roster": None, "roster_availability": None, "roster_basis": None,
                "capacity_note": "road-only / foreign — adds congestion, no WMT",
                "capacity_ratio": None,
                "congestion_note": ("foreign FENI-corridor load — applies the measured drag to shared WBN routes"
                                    if _is_feni(r["destination"]) else "foreign traffic off the FENI corridor — no measured drag"),
                "shared_with": [],
                "basis": {"note": "road-only / foreign traffic: congestion only, excluded from WMT"},
            })
            continue
        src, route, n = r["source"], r["route"], r["n"]
        cycle = r["cycle"]
        if not cycle:
            results.append({"route": route, "error": "no cycle time available"})
            continue
        load_min, dump_min = r["load_min"], r["dump_min"]
        fleet_trips = r["fleet_trips"]
        payload_t = r["payload_t"]
        fleet_t = fleet_trips * payload_t

        # Capacity check: does the plan ask more of the loader than it has ever
        # delivered? This is the constraint the data genuinely supports.
        cap = _point_capacity(src, "loading")
        cap_note, cap_ratio, achievable_t = "no measured capacity for this point", None, fleet_t
        if cap:
            cap_shift = float(cap["capacity_trips_shift"])
            demand = demand_by_src.get(src, fleet_trips)
            cap_ratio = round(demand / cap_shift, 3) if cap_shift else None
            if cap_ratio and cap_ratio > 1:
                # Over capacity, the point's throughput is shared between the
                # competing plans in proportion to what each asked for.
                share = fleet_trips / demand if demand else 1.0
                achievable_t = cap_shift * share * payload_t
                cap_note = ("OVER CAPACITY: %s is asked for %.0f trips/shift "
                            "against a demonstrated ceiling of %.0f (%.0f%%). "
                            "Excess trucks will queue; ~%.0f t of the planned "
                            "%.0f t will not materialise."
                            % (src, demand, cap_shift, 100 * cap_ratio,
                               fleet_t - achievable_t, fleet_t))
                warnings.append(cap_note)
            else:
                cap_note = ("within capacity: %s asked for %.0f of %.0f "
                            "trips/shift (%.0f%%)"
                            % (src, demand, cap_shift, 100 * (cap_ratio or 0)))

        others = [q for q in src_plans.get(src, []) if str(q).upper() != route]
        if others:
            cong = ("loading point %s is shared with %d other plan(s) (%s); "
                    "combined demand %.0f trucks. Cycle time is NOT scaled by "
                    "truck count — that effect is not identifiable in this "
                    "data — so contention is reported as capacity above."
                    % (src, len(others), ", ".join(map(str, others)),
                       src_trucks.get(src, n)))
        else:
            cong = "loading point %s is not shared with any other plan." % src

        results.append({
            "route": route, "source": src, "destination": r["destination"],
            "n_trucks": int(n),
            "predicted_cycle_time_min": round(cycle, 1),
            "effective_cycle_min": round(r["effective_cycle"], 1),
            "predicted_load_time_min": round(load_min, 1),
            "predicted_dump_time_min": round(dump_min, 1),
            "implied_travel_time_min": round(max(cycle - load_min - dump_min, 0.0), 1),
            "trips_per_shift_per_truck": round(r["trips_per_truck"], 2),
            "total_trips": round(fleet_trips, 1),
            "avg_payload_t": round(payload_t, 2),
            "planned_production_t": round(fleet_t, 0),
            "achievable_production_t": round(achievable_t, 0),
            "trucks_to_roster": _roster(n, route)[0],
            "roster_availability": _roster(n, route)[1],
            "roster_basis": _roster(n, route)[2],
            "capacity_note": cap_note,
            "capacity_ratio": cap_ratio,
            "congestion_note": cong,
            "shared_with": others,
            "basis": {
                "cycle_time": ("%s — weigh-to-weigh interval, i.e. the trip "
                               "time a planner recognises" % r["basis"]),
                "effective_cycle": r["effective_basis"],
                "trips_and_tonnes": ("derived: shift_minutes / effective_cycle. "
                                     "NOT shift_minutes / cycle_time, which "
                                     "omits the empty return and the queue and "
                                     "overpredicts trips by ~5x"),
                "availability": (
                    "not applied (%.0f%%): the effective cycle already includes "
                    "non-hauling time, so an allowance would double-count it. "
                    "Measured hauling-truck availability is %.1f%%."
                    % (100 * avail, 100 * MEASURED_HAUL_AVAILABILITY)),
            },
        })

    ok = [x for x in results if "error" not in x]
    # Production totals exclude foreign / road-only lines: they add congestion,
    # not tonnage, so summing their (zero) WMT is fine but their trucks must not
    # inflate the fleet.
    prod = [x for x in ok if not x.get("foreign")]
    foreign_rows = [x for x in ok if x.get("foreign")]
    foreign_congestion = None
    if foreign_rows:
        foreign_congestion = {
            "feni_trips": round(foreign_feni_trips, 1),
            "drag_per_dt": round(drag_per_dt, 4),
            "routes_affected": sorted(set(drag_routes)),
            "tonnage_cost_t": round(drag_tonnage_cost, 0),
            "foreign_trucks": int(sum(x["n_trucks"] for x in foreign_rows)),
            "coef": OTHER_TRAFFIC_COEF,
            "note": ("foreign/road-only trucks add congestion on the shared FENI "
                     "corridor (measured coefficient), not WMT; only foreign "
                     "traffic applies drag — our own trucks do not self-congest"),
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": results,
        "summary": {
            "total_trucks": int(sum(x["n_trucks"] for x in prod)),
            "planned_production_t": round(sum(x["planned_production_t"] for x in prod), 0),
            "achievable_production_t": round(sum(x["achievable_production_t"] for x in prod), 0),
            "foreign_congestion": foreign_congestion,
            "shared_loading_points": ["%s (%.0f trucks across %d plans)"
                                      % (k, v, len(src_plans[k]))
                                      for k, v in src_trucks.items()
                                      if len(src_plans.get(k, [])) > 1],
            "shared_dumping_points": ["%s (%.0f trucks across %d plans)"
                                      % (k, v, len(dst_plans[k]))
                                      for k, v in dst_trucks.items()
                                      if len(dst_plans.get(k, [])) > 1],
            "capacity_warnings": warnings,
            "shift_minutes": shift_min,
            "shift_calibration_min": CALIBRATION_SHIFT_MIN,
            # Present only when the caller moved off the calibration point.
            "shift_minutes_extrapolated": shift_note,
            "availability_factor_applied": avail,
            # Present only when a caller tried to scale tonnage by availability.
            # Surfacing it is the point: a silently-dropped parameter is how the
            # UI and the engine disagreed for as long as they did.
            "availability_override_ignored": avail_ignored,
            "fleet_sizing": {
                "trucks_hauling": int(sum(x["n_trucks"] for x in prod)),
                "trucks_to_roster": int(sum(
                    _roster(x["n_trucks"], x.get("route", ""))[0] for x in prod)),
                "bases_used": sorted({
                    _roster(x["n_trucks"], x.get("route", ""))[2] for x in prod}),
                "measured_availability": MEASURED_MECHANICAL_AVAILABILITY,
                "fleet_prior": MEASURED_MECHANICAL_AVAILABILITY,
                "coverage_note": ("availability is measured for trucks carrying "
                                  "30.3% of training tonnage; routes served by "
                                  "the other 69.7% are labelled fleet_prior"),
                "basis": ("mechanical availability measured over 170,899 "
                          "haul-truck shifts (EQUIPMENTS_HOURLY_STATUS, "
                          "2026-04-01..06-30); the distribution is bimodal, so "
                          "28% of truck-shifts are lost entirely rather than "
                          "every truck running at 72%"),
            },
            "availability_note": (
                "1.0 by design: trips are predicted by dividing the shift by the "
                "MEASURED effective cycle (shift-minutes per completed trip), "
                "which already contains queueing, empty running and breaks. "
                "Measured hauling-truck availability is %.1f%% over 215 days."
                % (100 * MEASURED_HAUL_AVAILABILITY)),
            "weather": "wet" if wet else "dry",
            "weather_note": (
                "wet raises DWELL at both ends -- loading and dumping -- and the "
                "reported cycle time carries both, measured per point, but "
                "NOT predicted tonnage: within route and month, rain moves "
                "tonnage by a median +0.1% and reduces it in only 49% of 122 "
                "comparable route-months, and the raw wet-vs-dry trips/DT "
                "comparison is a median +4.8% across 15 routes with paired data. "
                "A production penalty is not supported in either view. Implied "
                "travel time is weather-INVARIANT by construction: the wet/dry "
                "split is measured at POINTS, and nothing in this dataset "
                "measures a rain effect on road speed. An earlier version added "
                "only the loading penalty to the cycle, which made the residual "
                "travel figure FALL in the rain on 11 of 14 routes -- rain "
                "appearing to speed trucks up"),
        },
        "model_limits": {
            "cycle_time_vs_truck_count": (
                "NOT MODELLED. Four tests could not identify a congestion "
                "effect in weighbridge data; observed delay FALLS as loader "
                "utilisation rises because trucks are deployed to points that "
                "are running well. Contention is reported as capacity "
                "utilisation instead, which is measured."),
            "segment_level_speed": (
                "NOT USED FOR THESE PREDICTIONS, but it does exist. Haul trucks "
                "ARE GPS-instrumented at 3-second resolution (479 of 945 in "
                "FMS_PLAYBACK_TRACK_24H) and FMS_CONGESTION_SEG carries measured "
                "speed for 95 KM segments. The blocker is retention, not "
                "instrumentation: those feeds hold days to two weeks, so they do "
                "not overlap the trip history these route times are built from. "
                "An earlier version of this note claimed no haul truck had GPS; "
                "that was wrong and is corrected here."),
            "load_dump_split": (
                "ESTIMATED. The weighbridge records one interval per trip; the "
                "split into load, travel and dump is an apportionment."),
            "cycle_time_vs_trip_count": (
                "TWO FIGURES, DELIBERATELY. predicted_cycle_time_min is the "
                "weigh-to-weigh interval and is what a planner recognises as "
                "trip time. effective_cycle_min is shift-minutes per completed "
                "trip, measured per route, and is what trips_per_shift divides "
                "by. They differ by 1.2x to 24.8x depending on the route, "
                "because the weighbridge interval cannot see the empty return, "
                "the shovel queue, refuelling or breaks. An earlier version "
                "divided by the former and overpredicted production by ~5x."),
        },
    }
