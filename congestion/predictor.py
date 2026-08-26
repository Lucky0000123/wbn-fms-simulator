"""Layer 2C - the hybrid predictor: physics + M/M/c + BPR (+ bunching).

predict(route, n_trucks, n_loaders) -> trips/DT/day with a full component
breakdown, congestion status, uncertainty band, and the legacy
divide-by-demonstrated-max comparison.

The physics model is the PRIMARY predictor. Calibration (alpha/beta/mu/
c_road/cycle_sd) comes from data/congestion_params.json. Any ML residual
correction is applied only inside the observed fleet range.
"""
from __future__ import annotations

import math

from . import physics, queueing, bpr
from .config import route_params
# ONE home for road capacity (congestion.segments reads the official
# speed-limit sheets). Imported eagerly and NOT wrapped in try/except: if the
# official basis cannot load, pricing must fail loudly rather than fall back
# to the headway-class assumption this change exists to retire.
from .segments import route_road_capacity_hr as _road_capacity


def _finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def predict(route: str, n_trucks: float, n_loaders: int | None = None,
            *, shift_hours: float | None = None, shifts_per_day: int | None = None,
            payload_t: float | None = None, rain_mm: float = 0.0,
            contractor: str | None = None,
            segment_fleet: dict | None = None,
            tenant_flow_hr: dict | bool | None = None,
            legacy_cap: float | None = None, legacy_rate: float | None = None,
            mode: str = "full") -> dict:
    """Hybrid trips/DT/day prediction for one route.

    route: 'TF>HUAFEI' style key. n_loaders None -> per-route default + warning.

    contractor: per-contractor baseline (matched-day calibrated ratio over the
    pooled route baseline) when calibration has one; None -> pooled.

    segment_fleet: {segment_id: combined trucks} for the WHOLE plan (owner,
    2026-08-21: trucks on the same road share one penalty). Stick routes
    (congestion/segments.py) always price road time per segment — with only
    their own fleet when this is absent — so the calibration anchor holds
    exactly when a route is alone; cross traffic is the only extra penalty.
    Build it with congestion.segments.segment_trucks(), which as of
    2026-08-23 also counts spur-origin (BLB) trucks onto the lower mainline
    they physically run — they were invisible to S4 before.

    tenant_flow_hr: {segment_id: extra trucks/hr in the loaded lane} from the
    OTHER TENANTS who share our road and give us no tonnage (owner register,
    2026-08-24 — congestion/tenants.py). True -> take the register's own
    numbers; None/False -> our plan alone, the pre-2026-08-24 behaviour, which
    is the answer to "what if we had the road to ourselves".

    It is a FLOW and not a truck count on purpose. segment_fleet is converted
    to flow at THIS route's tempo, which is right for our own plan (similar
    cycles) and wrong for a tenant: 40 KR>RSF trucks turning 5 trips/day push
    more than three times the flow of 40 TF>HUAFEI trucks turning ~1.2. Adding
    tenants as trucks would understate exactly the traffic the owner is asking
    about, so they arrive already converted.

    Road capacity is the OFFICIAL geometric one (speed-limit sheets /
    FOLLOWING_DISTANCE_M, one loaded lane; the BLB spur has no sheet and carries the
    20 km/h floor). It is a ROAD number and only a road number: the loader
    and dump ceilings are priced by queueing.erlang_c and reported under
    their own keys, never folded into the BPR capacity.

    mode:
      full — Congestion tab. Cycle includes loader queue and bunching.
      road — Plan / Allocate. Trips/DT from ROAD time (+ ops + overhead)
             only. Extra trucks slow the haul via BPR on c_road; they do
             not collapse output because three faces saturated. Owner
             2026-08-21: "here you just need to see the time in road,
             not other things."
    """
    if not route or ">" not in str(route):
        raise ValueError("route must look like 'TF>HUAFEI'")
    if not _finite(n_trucks) or n_trucks < 0:
        raise ValueError("n_trucks must be a non-negative number")
    p = route_params(route, contractor=contractor)
    warnings = []
    if n_loaders is None:
        n_loaders = int(p["n_loaders"])
        warnings.append("n_loaders not specified - using default %d; supply the real "
                        "loader count for a trustworthy prediction" % n_loaders)
        # R2 (2026-08-26 audit, reports/congestion_analysis_report.md): with a
        # big fleet a defaulted loader count is not a soft caveat, it is the
        # dominant error term — measured -23%..-39% trips/DT on real rows
        # (TF>HUAFEI 410 DT, BLB>FENI KM0 203 DT) because c≈2 pins the queue
        # at its plateau. Escalate so callers cannot miss it.
        if n_trucks >= 50:
            warnings.append("LOADER DEFAULT ON A LARGE FLEET (N=%d): prediction "
                            "can be tens of percent low; measured -23%%..-39%% "
                            "on production rows. Pass the plan row's loader "
                            "count." % int(n_trucks))
    n_loaders = int(n_loaders)
    if n_loaders < 0:
        raise ValueError("n_loaders must be >= 0")
    sh = float(shift_hours if shift_hours is not None else p["hours_per_shift"])
    spd = int(shifts_per_day if shifts_per_day is not None else p["shifts_per_day"])
    day_minutes = spd * sh * 60.0

    origin, _, dest = str(route).partition(">")
    if n_trucks == 0 or n_loaders == 0:
        reason = "no trucks" if n_trucks == 0 else "no loaders"
        return _zero_result(route, n_trucks, n_loaders, reason, warnings)

    dist = physics.route_distance_km(origin, dest)
    if dist is None:
        raise ValueError("unknown route nodes: %s" % route)

    # ── Layer 1: free flow ────────────────────────────────────────────────
    # Wet road: rolling resistance rises with rain (maintained 2% -> ~4% wet).
    # rr_dry is the condition the route's MEASURED speed was observed at, so it
    # is also the reference the wet ratio is taken against.  Passing it makes
    # rain reach a calibrated route: without it free_flow_cycle_min took the
    # measured speed verbatim and dropped rr_pct on the floor, which is why
    # rain_mm was a silent no-op on every calibrated route (2026-08-23).
    rr_dry = float(p["rr_pct"])
    rr = rr_dry + (2.0 if rain_mm >= 10 else (1.0 if rain_mm >= 1 else 0.0))
    ff = physics.free_flow_cycle_min(
        dist, rr_pct=rr, rr_ref_pct=rr_dry,
        speed_loaded_kmh=p.get("speed_loaded_kmh"),
        load_min=float(p["load_min"]), spot_min=float(p["spot_min"]),
        dump_min=float(p["dump_min"]))
    t_free_road = ff["t_haul_loaded_min"] + ff["t_haul_empty_min"]
    t_fixed = ff["t_load_min"] + ff["t_spot_min"] + ff["t_dump_min"]
    # Calibrated road running time (owner, 2026-08-21): p25 uncongested cycle
    # minus fixed ops, from dispatch records. Rain still scales it through the
    # physics speed ratio so wet cycles stay slower than dry.
    if _finite(p.get("road_free_min")) and p["road_free_min"] > 0:
        rain_scale = 1.0
        if rain_mm >= 1:
            # Dry baseline: rr_pct == rr_ref_pct, so the ratio is exactly 1.0
            # and this is the unscaled measured speed by construction.
            ff_dry = physics.free_flow_cycle_min(
                dist, rr_pct=rr_dry, rr_ref_pct=rr_dry,
                speed_loaded_kmh=p.get("speed_loaded_kmh"),
                load_min=float(p["load_min"]), spot_min=float(p["spot_min"]),
                dump_min=float(p["dump_min"]))
            dry_road = ff_dry["t_haul_loaded_min"] + ff_dry["t_haul_empty_min"]
            if dry_road > 0:
                rain_scale = t_free_road / dry_road
        t_free_road = float(p["road_free_min"]) * rain_scale
    if _finite(p.get("ops_min")) and p["ops_min"] > 0:
        t_fixed = float(p["ops_min"])

    # ── Layer 2B: BPR road penalty (uses loaded-direction flow) ──────────
    n_lanes = int(p.get("n_lanes_loaded") or p.get("n_lanes") or 1)
    headway_s = p.get("headway_s")
    c_road = p.get("c_road_trucks_hr")
    # OFFICIAL geometric road capacity first (owner documents, 2026-08-22):
    # slowest posted speed-limit bin / FOLLOWING_DISTANCE_M, ONE loaded
    # lane. The stored c_road_trucks_hr is the PRE-2026-08-22 headway-CLASS
    # assumption (60 or 240 trucks/hr) that congestion/segments.py records as
    # having sat "2.5-10x LOW ... an assumption artifact, owner-caught". Stick
    # routes stopped pricing on it when the per-segment branch below landed,
    # but the SPUR routes never did: BLB still priced, and every route still
    # REPORTED, a capacity nobody stands behind. The segment's capacity is a
    # property of the segment, so it is read from one home
    # (congestion.segments) rather than re-derived here.
    c_road_official, c_road_basis = _road_capacity(origin, dest)
    if _finite(c_road_official) and c_road_official > 0:
        c_road = float(c_road_official)
        n_lanes = 1            # per loaded lane by construction of the basis
        headway_s = 3600.0 / c_road       # implied time gap, reporting only
    elif not _finite(c_road) or c_road <= 0 or not _finite(headway_s):
        c_road, n_lanes, headway_s = bpr.geometry_c_road(
            dist,
            n_lanes_loaded=n_lanes,
            headway_s=float(p.get("headway_s") or p["safe_headway_s"]),
            headway_s_short=float(p.get("headway_s_short") or 15.0),
            long_haul_km=float(p.get("long_haul_km") or 50.0))
        c_road_basis = ("fallback: n_lanes x 3600 / documented headway "
                        "(route geometry unknown, no speed-limit sheet)")
    else:
        c_road_basis = ("calibration c_road_trucks_hr — headway CLASS "
                        "assumption, not the official speed-limit basis")
    mu_hr = 60.0 / float(p["load_min"])
    c_dump = p.get("c_dump_trucks_hr")
    road_only = str(mode or "full").strip().lower() == "road"
    # BPR uses ROAD capacity only, in EVERY mode. Putting n_loaders*mu into
    # c_link made the loader wall look like road congestion — BLB trips/DT
    # fell with fleet because three faces saturated, not because the 6.7 km
    # haul got slower (owner, 2026-08-21). That fix was applied to mode=road
    # only; the same argument holds verbatim in full mode, where the loader
    # constraint is ALREADY priced — correctly, and by the model built for it —
    # in queueing.erlang_c below. Charging it a second time through a
    # volume-delay function whose argument is by definition a road capacity
    # was double counting, and it made `road_vc` == `rho` identically whenever
    # loaders bound, so the `road_vc >= rho` bottleneck classifier in
    # simulator_api could never once return "loader". The other two ceilings
    # are not discarded, they are reported on their own names below.
    c_loader = n_loaders * mu_hr
    c_link = c_road

    # Flow depends on cycle, cycle on BPR + queue. nxt(cyc) is strictly
    # decreasing in cyc (longer cycle -> fewer arrivals/hr -> less BPR
    # penalty and less queue), so g(cyc) = nxt(cyc) - cyc has exactly one
    # root: solve by BISECTION. The damped Picard iteration used before
    # oscillated between the free and saturated branches near loader
    # saturation and exited after 50 rounds with NO convergence check —
    # the owner's saturation chart showed it as sawtooth dips, trips/DT
    # RISING when trucks were added (2026-08-21).
    # Stick routes decompose the road over the shared-corridor segments
    # (owner: one road, one penalty). Own-fleet-only when no segment_fleet.
    # Free-time SHARE per segment follows the official speed-limit sheets
    # (slow stretches own more of the route's calibrated road time); raw
    # overlap length is the fallback where the sheets have no data.
    from .segments import route_segments as _route_segments, node_km as _node_km
    from .speed_limits import span_times_min as _span_times
    _segs = _route_segments(origin, dest)
    # Tenant road load. Resolved ONCE, outside the fixed-point loop: the
    # register does not depend on our cycle time, and re-resolving it inside
    # _nxt would re-price the proxy roads 50+ times per call.
    _tenant_flow = None
    if tenant_flow_hr:
        if tenant_flow_hr is True:
            try:
                from .tenants import tenant_segment_flow_hr
                _tenant_flow = tenant_segment_flow_hr()
            except (ImportError, ValueError, ArithmeticError, KeyError,
                    TypeError, OSError):
                _tenant_flow = None
                warnings.append("tenant road load requested but unavailable")
        elif isinstance(tenant_flow_hr, dict):
            _tenant_flow = {k: float(v or 0) for k, v in tenant_flow_hr.items()}
    if _tenant_flow and not _segs:
        # Off-stick route (a BLB spur haul priced on its own distance): the
        # tenants are on the mainline, not the spur, so there is nothing to
        # add here. Say so rather than silently returning the clear-road
        # answer under a flag that claims tenants were included.
        warnings.append("tenant road load does not apply: route is not priced "
                        "on the shared mainline segments")
        # And DROP the flag, because the answer really is the clear-road one.
        # Leaving it True let the Excel column print the spur's unchanged rate
        # under a "with other tenants" heading, which reads as "the tenants
        # cost this route nothing" when the truth is "this route was never
        # priced against them".
        _tenant_flow = None
    _seg_w = []
    if _segs:
        _a, _b = _node_km(origin), _node_km(dest)
        _lo, _hi = min(_a, _b), max(_a, _b)
        for s, ov in _segs:
            o_lo, o_hi = max(_lo, s['bottom_km']), min(_hi, s['top_km'])
            tl, te = _span_times(o_lo, o_hi)
            _seg_w.append(((tl or 0) + (te or 0)) or ov)
    _seg_total_ov = sum(_seg_w) or 1.0

    def _nxt(cyc_try):
        v_hr = n_trucks / (cyc_try / 60.0)      # trucks/hr entering the link
        max_road = t_free_road * 3.0
        if _segs:
            # per-segment: combined trucks on the segment (all routes, all
            # contractors, IWIP) at this route's tempo -> v/c vs the
            # SEGMENT's one geometry capacity; free time split by overlap
            alpha, beta = float(p["alpha"]), float(p["beta"])
            t_road = 0.0
            worst_vc = 0.0
            for (s, ov), w in zip(_segs, _seg_w):
                trucks_here = n_trucks
                if segment_fleet:
                    trucks_here = max(float(segment_fleet.get(s['id'], 0.0)), n_trucks)
                # Ours converts at our tempo; tenants arrive as flow already.
                flow_hr = trucks_here / (cyc_try / 60.0)
                if _tenant_flow:
                    flow_hr += float(_tenant_flow.get(s['id'], 0.0))
                vc = flow_hr / max(1.0, s['cap_hr'])
                worst_vc = max(worst_vc, vc)
                tf_seg = t_free_road * (w / _seg_total_ov)
                t_road += min(3.0, 1.0 + alpha * (vc ** beta)) * tf_seg
            t_road = min(t_road, max_road)
            b = {"t_road_min": t_road, "penalty_min": t_road - t_free_road,
                 "vc": worst_vc,
                 "regime": ("capped" if t_road >= max_road - 1e-6 else
                            ("congested" if worst_vc >= 0.7 else "free"))}
        else:
            b = bpr.bpr_travel_min(t_free_road, v_hr, c_link,
                                   float(p["alpha"]), float(p["beta"]))
            # Safety net: road time cannot exceed 3x free flow. Trucks keep
            # moving in gridlock; they do not park for a whole shift. With
            # geometry c_road this rarely binds — if it does, the BPR formula
            # has left the physical range and the cap is a mask, not a model.
            if b["t_road_min"] > max_road:
                b = {**b, "t_road_min": max_road,
                     "penalty_min": max_road - t_free_road, "regime": "capped"}
        q = queueing.machine_repair(n_trucks, cyc_try / 60.0, float(p["load_min"]),
                                    n_loaders, sh)
        extra = 0.0 if road_only else q["wq_min"]
        return b["t_road_min"] + t_fixed + extra, b, q

    lo = max(1.0, ff["t_free_min"])
    hi = t_free_road * 3.0 + t_fixed + sh * 60.0 * 0.5 + 1.0
    nxt_lo, bp, qq = _nxt(lo)
    if nxt_lo <= lo + 0.05:
        cyc = lo                                 # free flow, no feedback
    else:
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            nm, _, _ = _nxt(mid)
            if nm > mid:
                lo = mid
            else:
                hi = mid
        nxt_mid, bp, qq = _nxt(0.5 * (lo + hi))
        cyc = bp["t_road_min"] + t_fixed + (0.0 if road_only else qq["wq_min"])

    # ── bunching (variance) penalty ───────────────────────────────────────
    # Linear in N/n_ref, so cap at 3x the reference-fleet term the same way
    # road time is capped at 3x free flow.
    sd = p.get("cycle_sd_min")
    n_ref = p.get("n_trucks_ref") or 30
    bunch = 0.0
    bunch_capped = False
    if _finite(sd) and sd > 0 and n_ref:
        k_b = float(p["k_bunch"])
        bunch_raw = k_b * float(sd) * (n_trucks / float(n_ref))
        bunch_cap = 3.0 * k_b * float(sd)
        if bunch_raw > bunch_cap:
            bunch = bunch_cap
            bunch_capped = True
            warnings.append("bunching penalty capped at 3x the reference-fleet term")
        else:
            bunch = bunch_raw
        if not road_only:
            cyc += bunch

    # OVERHEAD PER TRIP (owner, 2026-08-21 — replaces trips = U*1440/cyc):
    # breaks, dispatch wait, shift change and refuelling attach to TRIPS,
    # not to the clock. The old U anchor turned non-productive time into a
    # fixed share of the day, so past U*1440 < cycle the model claimed a
    # dispatched truck cannot finish even one trip in 24 h. Now:
    #     trips = day_minutes / (cyc + overhead_per_trip)
    # cyc is productive time only (road_congested + ops + queue + bunching),
    # so trips stays >= day/(3*road_free + ops + caps + overhead) — always
    # physically possible. Calibration anchors overhead so the model equals
    # the dispatch day rate exactly at the median fleet.
    overhead = p.get("overhead_per_trip_min")
    if not _finite(overhead) or overhead < 0:
        overhead = 240.0  # fresh-clone fallback; calibration writes the real one
    trips_dt_day = day_minutes / (cyc + overhead) if cyc > 0 else 0.0
    total_trips = trips_dt_day * n_trucks
    pay = payload_t if _finite(payload_t) and payload_t > 0 else p.get("payload_t") or 0.0

    status = "overloaded" if qq.get("overloaded") else (
        "congested" if (qq["rho"] >= 0.7 or bp["vc"] >= 0.7) else "open")
    if qq.get("overloaded"):
        warnings.append("loaders are the binding resource (rho=%.2f, throughput "
                        "at the c*mu plateau) - add loaders or remove trucks"
                        % qq["rho"])

    # ── uncertainty band ─────────────────────────────────────────────────
    lo_dt, hi_dt = p.get("obs_dt_min") or 0, p.get("obs_dt_max") or 0
    in_range = hi_dt and lo_dt <= n_trucks <= hi_dt
    rel = 0.10 if in_range else min(0.40, 0.10 + 0.30 * max(0.0, (n_trucks - (hi_dt or n_trucks)) / max(hi_dt or n_trucks, 1)))
    unc = {"p10": round(trips_dt_day * (1 - rel), 3),
           "p50": round(trips_dt_day, 3),
           "p90": round(trips_dt_day * (1 + rel), 3),
           "relative": round(rel, 3),
           "within_observed_fleet_range": bool(in_range),
           "method": "heuristic_sensitivity_band_not_empirical_quantiles"}
    if hi_dt and not in_range:
        warnings.append("fleet %.0f DT is outside the observed route range %.0f-%.0f; "
                        "p10/p90 are heuristic sensitivity bounds" %
                        (n_trucks, lo_dt, hi_dt))

    # ── legacy comparison (divide demonstrated max by fleet) ─────────────
    legacy = None
    cap = legacy_cap if _finite(legacy_cap) else p.get("day_trips_cap")
    rate = legacy_rate if _finite(legacy_rate) else p.get("day_rate")
    if _finite(cap) and _finite(rate) and cap and rate:
        lin = rate * n_trucks
        served = min(lin, cap)
        eff = max(served / n_trucks, 0.3 * rate)
        legacy = {"trips_per_DT_per_day": round(eff, 3),
                  "method": ("min(%.2f*N, %d)/N with 30%% floor" % (rate, cap)),
                  "model_version": "legacy_divide"}

    result = {
        "route": route,
        "n_trucks": round(float(n_trucks), 1),
        "n_loaders": n_loaders,
        "model_version": "hybrid",
        "calibrated": bool(p.get("calibrated")),
        "trips_per_DT_per_day": round(trips_dt_day, 3),
        "trips_per_DT_per_shift": round(trips_dt_day / spd, 3),
        "total_trips_day": round(total_trips, 1),
        "total_tonnes_day": round(total_trips * pay, 1) if pay else None,
        "cycle_time_minutes": round(cyc, 1),
        "components": {
            "t_free_road": round(t_free_road, 1),
            "bpr_penalty_minutes": round(bp["penalty_min"], 1),
            "t_load": round(ff["t_load_min"], 1),
            "t_spot": round(ff["t_spot_min"], 1),
            "t_dump": round(ff["t_dump_min"], 1),
            "queue_wait_minutes": round(qq["wq_min"], 1),
            "bunching_penalty_minutes": round(bunch, 2),
            "overhead_per_trip_minutes": round(float(overhead), 1),
        },
        "congestion_status": status,
        "bpr_regime": bp.get("regime"),
        "bunching_capped": bunch_capped,
        # Was other-tenant road load priced into this answer, and how much.
        # Reported unconditionally so a caller can never mistake a clear-road
        # number for a shared-road one by its absence.
        "tenant_traffic": bool(_tenant_flow),
        "tenant_flow_hr": ({k: round(v, 2) for k, v in _tenant_flow.items()}
                           if _tenant_flow else None),
        "rho": round(qq["rho"], 3),
        "road_vc": round(bp["vc"], 3),
        # ROAD capacity, and only the road's — the field is named for it.
        # The loader and dump ceilings keep their own names so nothing is
        # lost and no two of them can be read as each other.
        "link_capacity_trucks_hr": round(c_link, 1),
        "link_capacity_basis": c_road_basis,
        "loader_capacity_trucks_hr": round(c_loader, 1),
        "dump_capacity_trucks_hr": (round(float(c_dump), 1)
                                    if _finite(c_dump) and c_dump > 0 else None),
        "system_capacity_trucks_hr": round(
            min(c_link, c_loader,
                float(c_dump) if _finite(c_dump) and c_dump > 0
                else float("inf")), 1),
        "distance_km": round(dist, 1),
        "params": {"alpha": p["alpha"], "beta": p["beta"],
                   "bpr_source": "literature_default",
                   "load_min": p["load_min"], "rr_pct": rr,
                   "c_road_trucks_hr": round(c_road, 1),
                   "c_road_basis": c_road_basis,
                   "headway_s": round(float(headway_s), 1),
                   "n_lanes_loaded": n_lanes},
        "uncertainty": unc,
        "legacy_comparison": legacy,
        "warnings": warnings,
    }
    for k in ("trips_per_DT_per_day", "cycle_time_minutes"):
        if not _finite(result[k]):
            raise ArithmeticError("non-finite %s for %s @%s trucks" % (k, route, n_trucks))
    return result


def _zero_result(route, n_trucks, n_loaders, reason, warnings):
    return {
        "route": route, "n_trucks": n_trucks, "n_loaders": n_loaders,
        "model_version": "hybrid", "trips_per_DT_per_day": 0.0,
        "trips_per_DT_per_shift": 0.0, "total_trips_day": 0.0,
        "total_tonnes_day": 0.0, "cycle_time_minutes": None,
        "components": None, "congestion_status": "idle",
        "rho": 0.0, "road_vc": 0.0,
        "uncertainty": {"p10": 0.0, "p50": 0.0, "p90": 0.0},
        "legacy_comparison": None,
        "warnings": warnings + ["zero output: %s" % reason],
    }
