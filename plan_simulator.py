"""plan_simulator.py — Task 4: the what-if engine.

WHAT A PLANNER ASKS, AND WHAT THIS RETURNS
"30 trucks TF to KR, 20 trucks POS 12 to FENI — how long per trip, how much do
I move, and where do they collide?"

The engine answers with three kinds of number, and it labels which is which on
every field, because they do not deserve equal trust:

    measured    from observed history — route cycle times, dwell times, payload,
                and each point's demonstrated hourly throughput ceiling
    derived     arithmetic on measured values — trips per shift, tonnes
    assumed     the shift length and availability a planner supplies

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


def simulate(payload: dict) -> dict:
    """Run a plan and return per-route predictions plus shared-point warnings."""
    plans = payload.get("plans") or []
    if not plans:
        return {"error": "no plans supplied", "results": [], "summary": {}}

    shift_min = float(payload.get("shift_minutes", DEFAULT_SHIFT_MIN))
    avail = float(payload.get("availability", DEFAULT_AVAILABILITY))
    wet = str(payload.get("weather", "dry")).lower() in ("wet", "rain", "rainy")

    # Combined demand at every point, summed ACROSS plans. This is where two
    # plans that load from the same source become one contention problem.
    src_trucks: dict[str, float] = {}
    dst_trucks: dict[str, float] = {}
    src_plans: dict[str, list] = {}
    dst_plans: dict[str, list] = {}
    for p in plans:
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

        # Keep the pre-rain figure so the same proportional uplift can be
        # applied to the effective cycle below.
        cycle_dry = cycle
        # Rain lengthens the whole cycle, not just the dwell, so the uplift is
        # taken from the loading point's own measured wet penalty where known.
        if cycle and wet:
            dr = _dwell()
            pen = None
            if dr is not None:
                h = dr[(dr["point"].astype(str).str.upper() == src)
                       & (dr["kind"] == "loading")]
                if not h.empty and pd.notna(h.iloc[0].get("wet_penalty_min")):
                    pen = float(h.iloc[0]["wet_penalty_min"])
            cycle = cycle + (pen if pen is not None
                             else cycle * (FALLBACK_WET_UPLIFT - 1))

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
        # Rain lengthens the whole cycle, so the same penalty applies to the
        # effective cycle that determines trip count.
        if cycle and wet and cycle_dry and cycle_dry > 0:
            eff = eff * (cycle / cycle_dry)

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

    # Total trips demanded of each loading point, summed across all plans.
    demand_by_src: dict[str, float] = {}
    for r in resolved:
        demand_by_src[r["source"]] = (demand_by_src.get(r["source"], 0.0)
                                      + r["fleet_trips"])

    for r in resolved:
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
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": results,
        "summary": {
            "total_trucks": int(sum(x["n_trucks"] for x in ok)),
            "planned_production_t": round(sum(x["planned_production_t"] for x in ok), 0),
            "achievable_production_t": round(sum(x["achievable_production_t"] for x in ok), 0),
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
            "availability_factor_applied": avail,
            "availability_note": (
                "1.0 by design: trips are predicted by dividing the shift by the "
                "MEASURED effective cycle (shift-minutes per completed trip), "
                "which already contains queueing, empty running and breaks. "
                "Measured hauling-truck availability is %.1f%% over 215 days."
                % (100 * MEASURED_HAUL_AVAILABILITY)),
            "weather": "wet" if wet else "dry",
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
