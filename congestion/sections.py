"""Section-resolved plan pricing (owner, 2026-08-21).

"When we make a plan you have to see how many trucks are moving in each
window — each section of the route — and what speed that section allows.
The whole speed determined by one trips/DT only is wrong."

price_plan() prices a WHOLE day's plan at once: every route's road time is
the sum of the corridor windows it occupies, each window carrying the load
of every plan row that crosses it (chainage overlap, foreign/IWIP rows
included — their trucks occupy the road), degraded by BPR at that window's
v/c against its OFFICIAL geometric capacity.

**Migrated to the single geometry/capacity truth, 2026-08-23 (M8).**
Before this change the module carried its OWN section map (the pre-2026-08-22
`TOFU–KR / POS 12–POS 10 / POS 10–FENI` split) and its OWN capacity basis
(the median OBSERVED peak trucks/hour per section, 40–66/hr). That is the
`dayTripsCap` trap this repo has paid for repeatedly — "the most we ever
did" read as "the most we can do" — and it put ONE named window on two
capacity bases 18x apart in the SAME Plan tab: `KR–POS 12` read 66/hr here
and 1200 trucks/1 h bin in the road-crowding card, so an ordinary plan
rendered v/c 1.56–2.09 (RED, >=1) on a road the physics model says is ~20%
utilised. Geometry and capacity now come from `congestion.segments` /
`congestion.speed_limits` — imported, never re-typed:

  - windows      : segments.SEGMENTS, the S1–S4 stick (one road, one map);
  - capacity     : segments.SEGMENTS[i]['cap_hr'] — official speed-limit
                   sheets, min bin speed / following distance, ONE loaded
                   lane (loaded and empty have separate lanes, so a
                   loaded-direction demand flow belongs over a
                   loaded-lane capacity). The road-crowding card counts
                   BOTH directions and therefore uses 2x the same number;
                   the two v/c figures are the same physics;
  - free-time shape : speed_limits.span_times_min() per window, loaded and
                   empty separately (the documents are directional);
  - route free total : RESCALED so the round trip equals the calibrated
                   dispatch `road_free_min` — dispatch truth holds at zero
                   traffic, the limit sheets only shape how it distributes
                   over the windows;
  - ops / overhead / loaders queue: the same calibration predict() uses.

The measured GPS record is KEPT, as observation: every window reports
`observed_peak_hr` (the median demonstrated peak) and `speed_observed_kmh`
(Jul+ corridor GPS) in their own labelled columns, plus `vc_vs_observed_peak`
— the share of what the window has ever demonstrated. None of those three
is a denominator for anything that is priced. A demonstrated peak is not a
capacity; no day ever tried more.

**VISIBILITY ONLY.** `shared_road_ratio` is reported and deliberately
consumed by nothing. It briefly multiplied the pricing curve on 2026-08-21
("BLB trips falls like hell") and the owner ordered it reverted the same
day. Do not wire it into planTripsPerDT or any other pricing path; the
calibrated per-route curve already carries real-day cross-traffic
(backtest R2 0.926).

The fixed point (times -> flows -> BPR -> times) is damped and
convergence-checked; flows use the PRODUCTIVE cycle (demand-flow
doctrine), never cycle+overhead.
"""
from __future__ import annotations

import math
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from . import physics, queueing, segments, speed_limits
from .config import route_params

# Imported ONLY to place the observed (GPS / demonstrated-peak) series onto
# the current windows: those series are binned on the pre-2026-08-22 section
# map, which still lives in plan_analogues.SECTIONS. No geometry or capacity
# used for pricing comes from here.
import plan_analogues as pa
import plan_shared_flow as psf

ALPHA, BETA = 0.15, 4.0
EMPTY_SPEED_FACTOR = 1.25          # site GPS: empty runs ~1.25x loaded
FALLBACK_SPEED_KMH = 25.0

# The BLB spur has NO speed-limit sheet (speed_limits.py header, owner
# 2026-08-22) and no official capacity. Its pseudo-window is priced at the
# 20 km/h floor over the SAME official following distance, matching the
# spur estimate plan_shared_flow already uses for the hourly crowding card
# (that card counts both directions and so states 2x this per-lane figure).
SPUR_SPEED_FLOOR_KMH = 20.0

# ── Where the BLB spur meets the stick ────────────────────────────────────
# EVIDENCE, not assumption (data/haul_road_chainage_public.csv, the committed
# road survey):
#   * the survey holds the mainline as three contiguous chainage runs —
#     CRD 0.000–7.850, KR 7.875–38.975, TOFU 39.000–67.800 — i.e. one stick
#     from the coast (0) to TF (67.8), the same datum congestion.segments uses;
#   * road 'BLB' is surveyed on that SAME datum, km 2.450 → 19.825, and its
#     km-2.450 point sits 0.2 m from the mainline's OWN km-2.450 point
#     (CRD). The two polylines then separate progressively: 28 m at 2.475,
#     45 m at 2.500, 87 m at 2.575. That is a junction, measured.
#   * congestion.physics states the same thing independently ("Spur joins at
#     ~2.5 km + 17.4 km spur length", SPUR_KM['BLB'] = 19.9 = 2.5 + 17.4)
#     and the surveyed pit chainage is 19.825. The two agree to ~50 m.
# So a BLB truck runs the spur AND then the lower mainline between the
# junction and its destination: 2.45 km of S4 to FENI KM0 / HUAFEI / BSE,
# 12.55 km of S4 to FENI KM15. It is NOT on S1–S3, and it is not invisible.
# The spur remainder is never invented here — it is
# physics.route_distance_km() minus the mainline kilometres, which
# reproduces physics' own 17.4 km spur to within 50 m on every BLB route.
# ONE home for the junction chainage (congestion.segments), so this view and
# the hourly road-crowding DES cannot drift apart on where BLB meets the road.
from .segments import SPUR_JOIN_KM
SPUR_JOIN_SOURCE = ("data/haul_road_chainage_public.csv: BLB km 2.450 is 0.2 m "
                    "from mainline (CRD) km 2.450 on the same chainage datum")


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _observed_overlay(lo, hi, caps_obs, speeds_obs):
    """(demonstrated peak trucks/hr, measured GPS speed km/h) over [lo, hi].

    INFORMATION ONLY. Both series are binned on the pre-2026-08-22 section
    map, so they are projected onto the current window by chainage overlap:
    the peak takes the MIN of the overlapping bins (the tightest stretch
    bounds the chain, same reading as the official min-bin capacity), the
    speed a length-weighted mean. Neither ever prices anything — a
    demonstrated peak is "the most we ever did", not a capacity.
    """
    peak, spd_w, spd_km = None, 0.0, 0.0
    for label, slo, shi in pa.SECTIONS:
        ov = min(hi, shi) - max(lo, slo)
        if ov <= 0:
            continue
        pk = caps_obs.get(label)
        if _finite(pk) and pk > 0:
            peak = pk if peak is None else min(peak, pk)
        sp = speeds_obs.get(label)
        if _finite(sp) and sp > 0:
            spd_w += sp * ov
            spd_km += ov
    return peak, (round(spd_w / spd_km, 1) if spd_km > 0 else None)


def _route_windows(route, caps_obs, speeds_obs):
    """The chainage windows a route occupies: mainline segments + spur.

    Returns [] when the route's geometry is unknown (unchanged behaviour for
    off-model origins such as CBB). Every mainline window's span, label and
    capacity come from congestion.segments; nothing is re-typed here.
    """
    o, _, d = str(route).partition(">")
    o, d = o.strip().upper(), d.strip().upper()
    dist = physics.route_distance_km(o, d)
    dk = segments.node_km(d)
    join = SPUR_JOIN_KM.get(o)

    lo = hi = None
    if join is not None:
        # Spur origin. The destination is reached down the mainline from the
        # junction UNLESS it is one of the dumps that sit on the spur itself
        # (physics.BLB_COASTAL_DEST / a calibrated distance shorter than the
        # mainline run would be — in which case the mainline is not used).
        if dk is not None and d not in physics.BLB_COASTAL_DEST:
            cand_lo, cand_hi = min(join, dk), max(join, dk)
            if not (_finite(dist) and dist > 0 and (cand_hi - cand_lo) > dist + 0.5):
                lo, hi = cand_lo, cand_hi
    else:
        ok = segments.node_km(o)
        if ok is not None and dk is not None:
            lo, hi = min(ok, dk), max(ok, dk)

    out = []
    covered = 0.0
    if lo is not None and hi is not None and hi - lo > 1e-9:
        for s in segments.SEGMENTS:
            a, b = max(lo, s['bottom_km']), min(hi, s['top_km'])
            if b - a <= 1e-9:
                continue
            tl, te = speed_limits.span_times_min(a, b)
            km = b - a
            tl = tl if (_finite(tl) and tl > 0) else 60.0 * km / FALLBACK_SPEED_KMH
            te = te if (_finite(te) and te > 0) else tl / EMPTY_SPEED_FACTOR
            # The WINDOW's own description (length, limit speed, observation) is
            # a property of the section, not of whichever route happens to
            # touch it first: a BLB row overlapping only km 0.00-2.45 of S4
            # must not relabel the whole window with the port area's 20 km/h.
            seg_len = float(s['length_km'])
            seg_tl = s['limit_time_loaded_min']
            seg_spd = (60.0 * seg_len / seg_tl) if (_finite(seg_tl) and seg_tl > 0) else None
            obs_pk, obs_spd = _observed_overlay(s['bottom_km'], s['top_km'],
                                                caps_obs, speeds_obs)
            out.append({
                "label": s['label'], "seg_id": s['id'], "km": km,
                "section_km": seg_len,
                "lo": a, "hi": b, "order": segments.SEGMENTS.index(s),
                "t_loaded": tl, "t_empty": te,
                "speed_free": seg_spd if seg_spd else 60.0 * km / tl,
                "cap_hr": float(s['cap_hr']),
                "cap_basis": ("official speed limits: min bin speed x 1000 / %g m "
                              "following, one loaded lane" % s['following_m']),
                "source": s['source'],
                "observed_peak_hr": obs_pk, "speed_observed_kmh": obs_spd,
            })
            covered += km

    if _finite(dist) and dist - covered > 0.5:
        # Spur / off-mainline remainder (BLB spur, HUAFEI branch): no limit
        # sheet, so it rides the route's calibrated speed and is bounded by
        # the 20 km/h floor over the official following distance.
        p = route_params(route)
        spd = p.get("speed_loaded_kmh")
        spd = float(spd) if (_finite(spd) and spd > 0) else FALLBACK_SPEED_KMH
        km = dist - covered
        tl = 60.0 * km / spd
        out.append({
            "label": "%s spur" % (o or route), "seg_id": None, "km": km,
            "section_km": km,
            "lo": None, "hi": None, "order": 99,
            "t_loaded": tl, "t_empty": tl / EMPTY_SPEED_FACTOR,
            "speed_free": spd,
            "cap_hr": SPUR_SPEED_FLOOR_KMH * 1000.0 / speed_limits.FOLLOWING_DISTANCE_M,
            "cap_basis": ("spur estimate: %g km/h floor x 1000 / %g m following, "
                          "one lane (no speed-limit sheet)"
                          % (SPUR_SPEED_FLOOR_KMH, speed_limits.FOLLOWING_DISTANCE_M)),
            "source": "no sheet — dispatch-calibrated per-route method",
            "observed_peak_hr": None, "speed_observed_kmh": None,
        })
    return out


def price_plan(rows, rain_mm=0.0):
    """rows: [{route, dt, loaders?, foreign?}] — one whole day, one road network."""
    speeds_obs = psf._section_speeds_kmh()      # INFO column only
    caps_obs = psf._load_section_capacity_tph()  # INFO column only — NOT a denominator
    # one road, one figure: rows sharing a route key share the road AND its
    # faces, so merge them before pricing (owner: "see it as a complete
    # one-day plan, not one row")
    merged = {}
    for r in rows or []:
        route = str(r.get("route") or "").replace("→", ">").strip()
        try:
            dt = float(r.get("dt") or 0)
        except (TypeError, ValueError):
            continue
        if ">" not in route or dt <= 0:
            continue
        g = merged.setdefault(route, {"route": route, "dt": 0.0, "loaders": 0,
                                      "foreign": bool(r.get("foreign"))})
        g["dt"] += dt
        try:
            g["loaders"] += int(r.get("loaders") or 0)
        except (TypeError, ValueError):
            pass
    plan = []
    for r in merged.values():
        route, dt = r["route"], r["dt"]
        p = route_params(route)
        segs = _route_windows(route, caps_obs, speeds_obs)
        if not segs:
            continue
        # free per-window loaded/empty minutes from the OFFICIAL directional
        # limit times, anchored to the calibrated dispatch road_free total
        raw_road = sum(w["t_loaded"] + w["t_empty"] for w in segs)
        anchor = p.get("road_free_min")
        scale = (float(anchor) / raw_road) if (_finite(anchor) and anchor > 0 and raw_road > 0) else 1.0
        wet = 1.0 + (0.15 if rain_mm >= 10 else (0.06 if rain_mm >= 1 else 0.0))
        loaders = r.get("loaders")
        if not (_finite(loaders) and loaders >= 1):
            ref_t, ref_l = p.get("n_trucks_ref"), p.get("n_loaders")
            tpl = (float(ref_t) / float(ref_l)) if (p.get("calibrated") and ref_t and ref_l) else 15.0
            loaders = max(1, round(dt / tpl))
        ovh = p.get("overhead_per_trip_min")
        if not (_finite(ovh) and ovh >= 0):
            ovh = 240.0
        plan.append({
            "route": route, "dt": dt, "loaders": int(loaders),
            "foreign": bool(r.get("foreign")),
            "segs": segs,
            "t_load": [w["t_loaded"] * scale * wet for w in segs],
            "t_empty": [w["t_empty"] * scale * wet for w in segs],
            "ops": float(p["ops_min"]) if _finite(p.get("ops_min")) else 8.0,
            "overhead": float(ovh),
            "load_min": float(p.get("load_min") or 5.0),
            "sd": p.get("cycle_sd_min"), "n_ref": p.get("n_trucks_ref") or 30,
            "k_bunch": float(p.get("k_bunch") or 0.03),
            "sh": float(p.get("hours_per_shift") or 12.0),
            "day_minutes": float(p.get("shifts_per_day") or 2) * float(p.get("hours_per_shift") or 12.0) * 60.0,
            "cyc": None, "trips": None,
        })
    if not plan:
        return {"ok": False, "error": "no priceable rows"}

    # seed with free-flow trips, then damped fixed point over the whole plan
    for r in plan:
        road0 = sum(r["t_load"]) + sum(r["t_empty"])
        r["cyc"] = road0 + r["ops"]
        r["trips"] = r["day_minutes"] / (r["cyc"] + r["overhead"])
    converged = False
    sec_state = {}
    # Damped fixed point. The damping SHRINKS whenever a sweep fails to
    # reduce the residual: at a flat 0.5 the map can settle into a 2-cycle
    # instead of a fixed point when a row's Erlang-C queue is near
    # saturation (one loader, cycle short enough that rho approaches 1) —
    # the wait then swings tens of minutes between sweeps and `converged`
    # silently reports False. Official capacities made cycles shorter and
    # pushed one real row (POS 12>FENI KM15, 15 DT on 1 loader) into that
    # regime. While the residual is falling the weight stays 0.5, so plans
    # that already converged follow the identical trajectory.
    damp = 0.5
    prev_worst = None
    for _ in range(120):
        flows = {}
        for r in plan:
            f = r["dt"] * 60.0 / max(1.0, r["cyc"])     # productive-cycle demand flow
            for w in r["segs"]:
                flows[w["label"]] = flows.get(w["label"], 0.0) + f
        worst = 0.0
        sec_state = {}
        for r in plan:
            road = 0.0
            road_hist = 0.0
            for w, tl, te in zip(r["segs"], r["t_load"], r["t_empty"]):
                label = w["label"]
                cap = w["cap_hr"]
                vc = flows.get(label, 0.0) / max(1.0, cap)
                # baseline: this route ALONE on the window — the calibrated
                # route-level model (backtest R2 0.926) already prices a
                # route's own traffic, so the section model charges only the
                # EXTRA drag from other plan rows sharing the window
                vc_h = (r["dt"] * 60.0 / max(1.0, r["cyc"])) / max(1.0, cap)
                pen = min(3.0, 1.0 + ALPHA * (vc ** BETA))
                pen_h = min(3.0, 1.0 + ALPHA * (vc_h ** BETA))
                road += tl * pen + te            # empty runs its own lane, uncongested
                road_hist += tl * pen_h + te
                obs = w["observed_peak_hr"]
                st = sec_state.setdefault(label, {
                    "km": round(w["section_km"], 1), "flow_hr": 0.0,
                    "cap_hr": round(cap, 1), "vc": 0.0,
                    "vc_own": round(vc_h, 2),
                    "cap_basis": w["cap_basis"], "cap_source": w["source"],
                    "speed_free_kmh": round(w["speed_free"], 1),
                    "speed_observed_kmh": w["speed_observed_kmh"],
                    "observed_peak_hr": (round(obs, 1) if _finite(obs) else None),
                    "observed_peak_basis": ("median demonstrated peak trucks/hr "
                                            "(Jul+ corridor GPS) — NOT a capacity, "
                                            "reported for comparison only"),
                    "order": w["order"], "trucks": 0.0})
                st["km"] = max(st["km"], round(w["section_km"], 1))
                st["flow_hr"] = round(flows.get(label, 0.0), 1)
                st["vc"] = round(vc, 2)
                if _finite(obs) and obs > 0:
                    st["vc_vs_observed_peak"] = round(flows.get(label, 0.0) / obs, 2)
            q = queueing.erlang_c(r["dt"], r["cyc"] / 60.0, r["load_min"], r["loaders"], r["sh"])
            bunch = 0.0
            if _finite(r["sd"]) and r["sd"] and r["n_ref"]:
                bunch = min(3.0 * r["k_bunch"] * float(r["sd"]),
                            r["k_bunch"] * float(r["sd"]) * (r["dt"] / float(r["n_ref"])))
            cyc_new = road + r["ops"] + q["wq_min"] + bunch
            cyc_next = r["cyc"] + damp * (cyc_new - r["cyc"])
            worst = max(worst, abs(cyc_next - r["cyc"]))
            r["cyc"] = cyc_next
            r["road"] = road
            r["road_hist"] = road_hist
            r["wq"] = q["wq_min"]
            r["trips"] = r["day_minutes"] / (r["cyc"] + r["overhead"])
            # same route with ONLY its own trucks on its windows — the basis
            # the calibrated route-level model prices; trips/trips_own is the
            # shared-road correction the curve WOULD carry for THIS plan.
            # Reported, never applied (owner revert, 2026-08-21).
            r["trips_hist"] = r["day_minutes"] / (road_hist + r["ops"] + q["wq_min"]
                                                  + bunch + r["overhead"])
        if worst < 0.05:
            converged = True
            break
        if prev_worst is not None and worst >= prev_worst:
            damp = max(0.05, damp * 0.5)
        prev_worst = worst
    # trucks per section (the owner's "how many trucks in each window")
    for r in plan:
        for w in r["segs"]:
            if w["label"] in sec_state:
                sec_state[w["label"]]["trucks"] += r["dt"]
    for st in sec_state.values():
        st["trucks"] = round(st["trucks"])
        if st["vc"] > 0:
            st["speed_cong_kmh"] = round(st["speed_free_kmh"] / min(3.0, 1.0 + ALPHA * (st["vc"] ** BETA)), 1)
    out_routes = {}
    for r in plan:
        out_routes.setdefault(r["route"], []).append(r)
    routes = {}
    for route, rs in out_routes.items():
        # rows on one route share the road; report the shared figure once
        r0 = max(rs, key=lambda x: x["dt"])
        ratio = 1.0
        if r0.get("trips_hist") and r0["trips_hist"] > 0:
            ratio = max(0.5, min(1.0, r0["trips"] / r0["trips_hist"]))
        routes[route] = {
            "trips_per_DT_per_day": round(r0["trips"], 3),
            "trips_own_basis": round(r0.get("trips_hist", r0["trips"]), 3),
            # VISIBILITY ONLY — consumed by nothing; see the module docstring
            "shared_road_ratio": round(ratio, 4),
            "shared_road_ratio_note": "information only — prices nothing (owner revert 2026-08-21)",
            "cycle_minutes": round(r0["cyc"], 1),
            "road_minutes": round(r0.get("road", 0.0), 1),
            "road_own_minutes": round(r0.get("road_hist", 0.0), 1),
            "queue_minutes": round(r0.get("wq", 0.0), 1),
            "overhead_minutes": round(r0["overhead"], 1),
            "dt": round(sum(x["dt"] for x in rs)),
            "loaders": int(sum(x["loaders"] for x in rs)),
            "sections": [{"section": w["label"], "km": round(w["km"], 1)} for w in r0["segs"]],
        }
    # pit -> coast down the stick, spurs last (the order the road runs, not
    # alphabetical: 'KM15–coast' before 'TF–KR' reads as a different road)
    ordered = sorted(sec_state.items(), key=lambda kv: (kv[1].get("order", 99), kv[0]))
    sections_out = []
    for label, st in ordered:
        st.pop("order", None)
        sections_out.append(dict(section=label, **st))
    return {"ok": True, "converged": converged,
            "routes": routes,
            "sections": sections_out,
            "basis": {
                # doctrine flags — same shape as this endpoint's siblings
                "congestion_clips_tonnes": False,
                "simulate_unchanged": True,
                "prices_nothing": ("VISIBILITY ONLY: this payload prices no plan row. "
                                   "shared_road_ratio is reported and consumed by "
                                   "nothing — it was reverted out of planTripsPerDT by "
                                   "the owner on 2026-08-21 and must not be re-wired."),
                "geometry_basis": ("congestion.segments S1-S4 — one stick, one map, "
                                   "one capacity per segment"),
                "capacity_basis": ("official speed-limit sheets: min bin speed x 1000 / "
                                   "%g m following distance, ONE loaded lane per segment "
                                   "(the road-crowding card states 2x the same number "
                                   "because it counts both directions)"
                                   % speed_limits.FOLLOWING_DISTANCE_M),
                "source_document": speed_limits.SOURCE_DOC,
                "flow_basis": ("steady-state DEMAND flow: dt x 60 / productive cycle, "
                               "loaded direction. The hourly road-crowding card "
                               "(plan_shared_flow) releases trucks on cycle + "
                               "overhead_per_trip and reads the busiest window, so its "
                               "v/c on the same section runs ~cycle/(cycle+overhead) "
                               "lower against the SAME cap_hr — a flow convention, not "
                               "a second capacity basis"),
                "assumptions": list(speed_limits.ASSUMPTIONS),
                "observed_peak_is_not_capacity": ("observed_peak_hr / speed_observed_kmh / "
                                                  "vc_vs_observed_peak are measured "
                                                  "OBSERVATION shown for comparison; a "
                                                  "demonstrated peak is 'the most we ever "
                                                  "did', never a capacity denominator"),
                "spur_junction": {"junction_km": dict(SPUR_JOIN_KM),
                                  "source": SPUR_JOIN_SOURCE},
            },
            "method": {
                "road": ("sum over the S1-S4 chainage windows a route occupies "
                         "(congestion.segments); free loaded/empty minutes from the "
                         "official directional speed limits, BPR at the window's v/c "
                         "against its official geometric capacity, capped 3x; the "
                         "route's free total is anchored to the calibrated dispatch "
                         "road_free_min"),
                "spur": ("routes off the stick (BLB) run the spur AND the lower "
                         "mainline from the surveyed junction (%s) to their "
                         "destination; the spur remainder is "
                         "physics.route_distance_km minus the mainline kilometres"
                         % ", ".join("%s km %.2f" % (k, v)
                                     for k, v in sorted(SPUR_JOIN_KM.items()))),
                "flow": "demand flow on the productive cycle (doctrine)",
                "trips": "1440 / (sectioned road + ops + queue + bunching + overhead_per_trip)",
            }}
