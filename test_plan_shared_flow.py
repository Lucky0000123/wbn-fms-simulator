#!/usr/bin/env python3
"""Unit checks for DES-lite shared-road occupancy."""
from __future__ import annotations

import sys

import plan_corridor_hours as pch
import plan_shared_flow as sf
from congestion.segments import SEGMENTS as _SEGS
from congestion.speed_limits import span_times_min as _span

fails = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print("  %-55s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        fails.append(name + ((" · " + str(detail)[:120]) if detail else ""))


FX = pch._FIXTURE


def _cv(xs):
    """Coefficient of variation — the flat-profile detector."""
    xs = [float(x) for x in xs]
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    if m <= 0:
        return 0.0
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    return (var ** 0.5) / m

print("=== shared-flow DES-lite ===")
multi = [
    {"source": "TOFU", "destination": "FENI KM0", "n_trucks": 40, "contractor": "RIM"},
    {"source": "KR", "destination": "FENI KM15", "n_trucks": 35, "contractor": "SMA"},
]
one = [multi[0]]

r1 = sf.shared_flow(one, shift_hours=12, rain_mm=0, path=FX)
r2 = sf.shared_flow(multi, shift_hours=12, rain_mm=0, path=FX)

check("single ok", r1.get("ok") is True, r1.get("error"))
check("multi ok", r2.get("ok") is True, r2.get("error"))
check("never clips", r2.get("basis", {}).get("congestion_clips_tonnes") is False)
check("simulate unchanged", r2.get("basis", {}).get("simulate_unchanged") is True)
check("no playback invent", r2.get("basis", {}).get("invents_playback_haul_speeds") is False)

sec = "POS 12–KM15"   # segment-model label: TOFU>KM0 and KR>KM15 share S2+S3
# (was POS 10–FENI pre-2026-08-22; the old 0-17 section overlapped KR>KM15 at 15-17)


def peak(res, name):
    for s in res.get("sections") or []:
        if s.get("section") == name:
            return s.get("peak_trucks") or 0
    return 0


check("POS 12–KM15 shared in multi",
      any(s.get("section") == sec and s.get("shared") for s in (r2.get("sections") or [])),
      r2.get("sections"))
check("multi occupancy > single on shared section",
      peak(r2, sec) > peak(r1, sec),
      "single=%s multi=%s" % (peak(r1, sec), peak(r2, sec)))

# TOFU input canonicalises to TF (one normaliser, prediction_pipeline.canonical_area)
# and must land on measured TF dwell, not the bare 10-min fallback
tofu = next((p for p in (r2.get("paths") or []) if (p.get("source") or "").upper() in ("TF", "TOFU")), None)
check("TOFU path present", tofu is not None)
if tofu:
    check("TOFU load uses measured TF (not bare fallback)",
          "fallback" not in (tofu.get("load_basis") or "") or tofu.get("load_min", 0) != 10,
          tofu.get("load_basis"))
    check("TOFU load minutes plausible", tofu.get("load_min", 0) >= 8, tofu)

kr = next((p for p in (r2.get("paths") or []) if (p.get("source") or "").upper() == "KR"), None)
if kr:
    check("KR load measured", "fallback" not in (kr.get("load_basis") or ""), kr.get("load_basis"))
    check("KR load >> 10 min typical", kr.get("load_min", 0) > 15, kr.get("load_min"))

# Empty plans
empty = sf.shared_flow([], shift_hours=12)
check("empty plans not ok", empty.get("ok") is False)


# ── BLB geometry: a spur that JOINS the stick, not a road of its own ──────
# Survey (data/haul_road_chainage_public.csv): BLB km 2.450 sits 0.2 m from
# the mainline's km 2.450 on the same datum, and congestion.physics says the
# same independently (19.9 = 2.5 join + 17.4 spur). So a BLB truck bound for
# the coast runs its spur AND 2.45 km of S4 — charging it to the spur alone
# under-counted S4, the tightest section, by 28% of its trucks on the real
# 2026-09-03 plan (355 DT against 456).
print("\n=== BLB spur junction ===")
blb = sf.shared_flow([{"id": "b", "source": "BLB", "destination": "FENI KM0",
                       "n_trucks": 20, "contractor": "RIM"}],
                     shift_hours=12, rain_mm=0, path=FX, whole_day=True)
bpath = (blb.get("paths") or [{}])[0]
check("BLB>FENI KM0 rides its spur", "BLB spur" in (bpath.get("sections") or []),
      bpath.get("sections"))
check("BLB>FENI KM0 ALSO rides KM15–coast below the junction",
      "KM15–coast" in (bpath.get("sections") or []), bpath.get("sections"))
blb_secs = {s["section"]: s for s in (blb.get("sections") or [])}
check("spur remainder agrees with physics' 17.4 km",
      abs((blb_secs.get("BLB spur") or {}).get("section_km", 0) - 17.4) < 0.2,
      (blb_secs.get("BLB spur") or {}).get("section_km"))
check("spur leg keeps most of the road time",
      (bpath.get("sec_times_h") or {}).get("BLB spur", 0)
      > (bpath.get("sec_times_h") or {}).get("KM15–coast", 0),
      bpath.get("sec_times_h"))
# the coastal dumps sit ON the spur: they must not be charged to the mainline
coastal = sf.shared_flow([{"id": "c", "source": "BLB", "destination": "POS 14",
                           "n_trucks": 20, "contractor": "RIM"}],
                         shift_hours=12, rain_mm=0, path=FX, whole_day=True)
cpath = (coastal.get("paths") or [{}])[0]
check("BLB>POS 14 stays on the spur (coastal dump)",
      cpath.get("sections") == ["BLB spur"], cpath.get("sections"))


# ── invariances ────────────────────────────────────────────────────────────
# Two rows out of the same pit at the same size: before 2026-08-23 a
# cumulative truck_idx serialised trucks across rows, so LIST POSITION decided
# who got the late (and clipped) release slots and swapping these two moved a
# section peak by 43%. The answer must not depend on the order they were typed.
print("\n=== row-order invariance ===")
pair = [
    {"id": "A", "source": "TF", "destination": "FENI KM0", "n_trucks": 250, "contractor": "RIM"},
    {"id": "B", "source": "TF", "destination": "POS 12", "n_trucks": 250, "contractor": "SMA"},
]
fwd = sf.shared_flow(pair, shift_hours=12, rain_mm=0, path=FX, whole_day=True)
rev = sf.shared_flow(list(reversed(pair)), shift_hours=12, rain_mm=0, path=FX, whole_day=True)


def by_sec(res):
    return {s["section"]: s for s in (res.get("sections") or [])}


f_s, r_s = by_sec(fwd), by_sec(rev)
check("order: same sections", set(f_s) == set(r_s), (sorted(f_s), sorted(r_s)))
worst_peak = max([abs(f_s[k]["peak_trucks"] - r_s[k]["peak_trucks"])
                  for k in f_s if k in r_s] or [0])
worst_vc = max([abs(f_s[k]["ratio"] - r_s[k]["ratio"]) for k in f_s if k in r_s] or [0])
check("order: peak trucks identical", worst_peak == 0, "max |delta| = %s" % worst_peak)
check("order: v/c identical", worst_vc < 1e-9, "max |delta| = %s" % worst_vc)
check("order: road truck-hours identical",
      abs((fwd["summary"]["road_truck_hours"] - rev["summary"]["road_truck_hours"])) < 0.05,
      (fwd["summary"]["road_truck_hours"], rev["summary"]["road_truck_hours"]))

# ── bin-size invariance ────────────────────────────────────────────────────
# v/c used to divide a STOCK (trucks present) by a FLOW x bin (capacity/hour x
# bin hours), so identical traffic scored 0.457 at 15-minute bins and 0.172 at
# hourly ones. Flow is now measured over a fixed hour and presence is a
# time-weighted mean, so the display bin cannot move either number.
print("\n=== bin-size invariance ===")
bins = {b: by_sec(sf.shared_flow(pair, shift_hours=12, rain_mm=0, path=FX,
                                 whole_day=True, bin_hours=b))
        for b in (0.25, 0.5, 1.0)}
ref = bins[1.0]
for label, key, tol in (("v/c", "ratio", 1e-9),
                        ("peak concurrent", "peak_concurrent", 1e-6),
                        ("truck-hours", "truck_hours", 0.05)):
    worst = 0.0
    for b in (0.25, 0.5):
        for sec, row in ref.items():
            if sec in bins[b]:
                worst = max(worst, abs(bins[b][sec][key] - row[key]))
    check("bin: %s invariant 0.25/0.5/1.0 h" % label, worst <= tol, "max |delta| = %s" % worst)

# The card's grid cells are a mean concurrency, so their bin AVERAGE is the
# same number at any bin size even though individual cells differ in count.
for sec, row in ref.items():
    if sec not in bins[0.25]:
        continue
    a = sum(row["occupancy_mean"]) / max(1, len(row["occupancy_mean"]))
    c = sum(bins[0.25][sec]["occupancy_mean"]) / max(1, len(bins[0.25][sec]["occupancy_mean"]))
    check("bin: %s mean occupancy invariant" % sec, abs(a - c) < 0.05, (a, c))

# ── conservation: executed trips follow the priced cadence ─────────────────
# trips_per_truck used to be max(1, floor(shift/interval)): it dropped part
# trips (-41%) and credited a whole trip to a truck whose interval exceeds the
# shift (+35%). Executed must track n x horizon / interval.
print("\n=== trips + truck-hours conservation ===")
worst_trip = 0.0
for p in fwd["paths"]:
    exp, got = p["expected_trips"], p["executed_trips"]
    if exp > 0:
        worst_trip = max(worst_trip, abs(got - exp) / exp)
check("executed trips within 10%% of priced cadence", worst_trip < 0.10,
      "worst = %.1f%%" % (100 * worst_trip))
th_exp = sum(p["n_trucks"] * (fwd["horizon_hours"] / p["interval_h"])
             * sum(list(p["sec_times_h"].values()) + list(p["sec_times_empty_h"].values()))
             for p in fwd["paths"])
th_got = fwd["summary"]["road_truck_hours"]
check("road truck-hours within 1%% of n x trips x time-in-section",
      abs(th_got - th_exp) / max(th_exp, 1e-9) < 0.01,
      "expected %.1f served %.1f" % (th_exp, th_got))

# ── release profile: reshaping WHEN must not change HOW MANY ───────────────
# The hour section of the card used to come out flat (CV 0.014-0.030 on real
# plans, 23 of 24 identical cells) against a MEASURED presence CV of 0.319.
# The profile that fixes it (HAULAGE_CLEAN.TIME_LOADED, n=273,222 loads over
# 234 days) is applied as a monotone time warp inside each shift, so it
# re-times the SAME SET of departures. That is the whole safety argument: if
# a release-shape change can move the trip count, it is a production model
# wearing a visibility model's clothes. Pin it against the uniform schedule.
print("\n=== release profile: conservation ===")

_warp = sf._warp_release_time
try:
    sf._warp_release_time = lambda t, sh, ns, cd: t     # uniform releases
    flat = sf.shared_flow(pair, shift_hours=12, rain_mm=0, path=FX, whole_day=True)
finally:
    sf._warp_release_time = _warp

check("profile conserves executed trips exactly",
      abs(fwd["summary"]["executed_trips"] - flat["summary"]["executed_trips"]) < 1e-9,
      (flat["summary"]["executed_trips"], fwd["summary"]["executed_trips"]))
check("profile conserves expected trips exactly",
      abs(fwd["summary"]["expected_trips"] - flat["summary"]["expected_trips"]) < 1e-9,
      (flat["summary"]["expected_trips"], fwd["summary"]["expected_trips"]))
check("profile conserves road truck-hours exactly",
      abs(fwd["summary"]["road_truck_hours"]
          - flat["summary"]["road_truck_hours"]) < 1e-6,
      (flat["summary"]["road_truck_hours"], fwd["summary"]["road_truck_hours"]))
worst_row = max([abs(a["executed_trips"] - b["executed_trips"])
                 for a, b in zip(fwd["paths"], flat["paths"])] or [0])
check("profile conserves executed trips PER ROW", worst_row < 1e-9,
      "max |delta| = %s" % worst_row)

# ...and it must actually reshape something, or the constant is decoration.
flat_s, prof_s = by_sec(flat), by_sec(fwd)
worst_cv_flat = max(_cv(flat_s[k]["occupancy_mean"]) for k in flat_s)
best_cv_prof = min(_cv(prof_s[k]["occupancy_mean"]) for k in prof_s)
check("uniform releases really were flat (CV < 0.05)", worst_cv_flat < 0.05,
      "worst CV = %.4f" % worst_cv_flat)
check("profiled releases carry real hourly structure (CV > 0.10)",
      best_cv_prof > 0.10, "weakest CV = %.4f" % best_cv_prof)

# The profile is data + one conservation constraint, never a free parameter:
# the interior constant is whatever makes the 12 hours average 1.0, and it
# must land inside the measured band. Both profiles must sum to 12.
for nm, prof in (("day", sf.RELEASE_PROFILE_DAY),
                 ("night", sf.RELEASE_PROFILE_NIGHT)):
    check("%s profile averages 1.0 (conserves the shift total)" % nm,
          abs(sum(prof) - 12.0) < 1e-9, sum(prof))
    check("%s profile is 12 hourly multipliers" % nm, len(prof) == 12, len(prof))
check("no meal-break dip invented (midday >= shift-start hour)",
      min(sf.RELEASE_PROFILE_DAY[4:8]) > sf.RELEASE_PROFILE_DAY[0],
      sf.RELEASE_PROFILE_DAY)
check("final hour of each shift is near-zero (measured changeover)",
      sf.RELEASE_PROFILE_DAY[11] < 0.25 and sf.RELEASE_PROFILE_NIGHT[11] < 0.25,
      (sf.RELEASE_PROFILE_DAY[11], sf.RELEASE_PROFILE_NIGHT[11]))
# the warp must be monotone and onto, or it is not a re-timing
_cdf = sf._release_cdf(sf.RELEASE_PROFILE_DAY)
_u = [i / 200.0 for i in range(200)]
_w = [sf._warp_unit(u, _cdf) for u in _u]
check("warp is monotone", all(_w[i] <= _w[i + 1] + 1e-12 for i in range(199)))
check("warp is onto [0,1)", _w[0] == 0.0 and _w[-1] > 0.9, (_w[0], _w[-1]))

rp = (fwd.get("basis") or {}).get("release_profile") or {}
check("release profile exposed in basis for the card", rp.get("applied") is True, rp)
check("release profile states its provenance",
      "273,222" in (rp.get("source") or "") and rp.get("n_days") == 234,
      rp.get("source"))
check("release profile declares conservation",
      rp.get("conserves_executed_trips") is True, rp)
check("release profile discloses the presence lag it does NOT fix",
      "phase" in (rp.get("presence_lag") or ""), rp.get("presence_lag"))

# ── segment time split: measured, and it must not move the route total ─────
# Splitting road time by the official speed limits assumed they are wrong by
# the same factor everywhere. Measured (463,060 vendor traversals + 11,611 GPS
# bin-traversals) they are 1.5-2.1x optimistic on S1-S3 and accurate on S4, so
# the uncorrected split pushed 7.2-7.8 pp of every route's road time onto S4.
print("\n=== segment time split ===")
_fac = sf.SEGMENT_TIME_FACTORS
try:
    sf.SEGMENT_TIME_FACTORS = {k: {"loaded": 1.0, "empty": 1.0} for k in _fac}
    limit_split = sf.shared_flow(pair, shift_hours=12, rain_mm=0, path=FX,
                                 whole_day=True)
finally:
    sf.SEGMENT_TIME_FACTORS = _fac

check("split conserves road truck-hours (total is dispatch-anchored)",
      abs(fwd["summary"]["road_truck_hours"]
          - limit_split["summary"]["road_truck_hours"]) < 1e-6,
      (limit_split["summary"]["road_truck_hours"],
       fwd["summary"]["road_truck_hours"]))
for a, b in zip(fwd["paths"], limit_split["paths"]):
    tot_a = sum(a["sec_times_h"].values()) + sum(a["sec_times_empty_h"].values())
    tot_b = sum(b["sec_times_h"].values()) + sum(b["sec_times_empty_h"].values())
    # 4e-4: sec_times_h is rounded to 4 dp in the payload and a route can carry
    # four legs, so the ONLY admissible difference is that rounding. The exact
    # statement is the road_truck_hours check above, which is unrounded.
    check("split keeps %s total road time" % a["label"][:28],
          abs(tot_a - tot_b) < 4e-4, (tot_b, tot_a))

# The full corridor (TF km 67.8 -> coast km 0) is the case the vendor/GPS study
# reported. S4's measured loaded share is 19.7-20.3%; the limit split gives
# 27.5% and never reaches the measured value in any of the 24 hours.
_tl, _te = [], []
for _s in _SEGS:
    _a, _b = _span(_s["bottom_km"], _s["top_km"])
    _tl.append(_a * _fac[_s["id"]]["loaded"])
    _te.append(_b * _fac[_s["id"]]["empty"])
_shares_l = [100 * x / sum(_tl) for x in _tl]
_shares_e = [100 * x / sum(_te) for x in _te]
check("S4 loaded share lands on measured 19.7-20.3%%",
      19.4 <= _shares_l[3] <= 20.6, "%.1f%%" % _shares_l[3])
check("S4 empty share lands on measured 22.4-22.5%%",
      22.0 <= _shares_e[3] <= 23.0, "%.1f%%" % _shares_e[3])
check("S1 loaded share lands on measured 44.5-47.1%%",
      44.0 <= _shares_l[0] <= 47.6, "%.1f%%" % _shares_l[0])
check("S2 loaded share lands on measured 17.3-19.9%%",
      17.0 <= _shares_l[1] <= 20.2, "%.1f%%" % _shares_l[1])
check("S3 loaded share stays on measured 15.3-15.9%% (it was already right)",
      15.0 <= _shares_l[2] <= 16.4, "%.1f%%" % _shares_l[2])
check("factors are ratios only: S4 is the outlier, not the level",
      _fac["S4"]["loaded"] < 1.2 < min(_fac[k]["loaded"] for k in ("S1", "S2", "S3")),
      _fac)

# ── BLB partial section: not one number, and labelled as not one number ────
# A BLB truck occupies 2.45 km of KM15-coast's 15 km (16%) but was counted as
# a full passage. Measured on the real 2026-09-03 plan: loaded flow 50.7/h
# below km 2.45 against 30.2/h above it - a 68% step inside one reported cell.
print("\n=== BLB partial section ===")
mixed = sf.shared_flow(
    [{"id": "s", "source": "TF", "destination": "FENI KM0", "n_trucks": 120,
      "contractor": "RIM"},
     {"id": "b", "source": "BLB", "destination": "FENI KM0", "n_trucks": 60,
      "contractor": "RIM"}],
    shift_hours=12, rain_mm=0, path=FX, whole_day=True)
s4 = next((s for s in (mixed.get("sections") or [])
           if s["section"] == "KM15–coast"), None)
check("KM15–coast row exists on a mixed BLB + stick plan", s4 is not None)
if s4:
    subs = s4.get("cross_sections") or []
    check("KM15–coast is split at the BLB junction", len(subs) == 2, subs)
    check("junction is at km 2.45 (survey)",
          any(abs(c["km_hi"] - 2.45) < 0.01 for c in subs), subs)
    if len(subs) == 2:
        low = min(subs, key=lambda c: c["km_lo"])
        high = max(subs, key=lambda c: c["km_lo"])
        check("flow below the junction really is higher (the hidden step)",
              low["peak_flow_per_h"] > high["peak_flow_per_h"] * 1.15,
              (low["peak_flow_per_h"], high["peak_flow_per_h"]))
        check("headline flow is the WORST cross-section, not a blend",
              abs(s4["peak_flow_per_h"] - low["peak_flow_per_h"]) < 1e-6,
              (s4["peak_flow_per_h"], low["peak_flow_per_h"]))
    check("the row SAYS it is a worst cross-section",
          "WORST CROSS-SECTION" in (s4.get("flow_basis") or "")
          and s4.get("uniform_section") is False, s4.get("flow_basis"))
s1 = next((s for s in (mixed.get("sections") or []) if s["section"] == "TF–KR"),
          None)
if s1:
    check("a uniform section is labelled uniform and not split",
          s1.get("uniform_section") is True and not s1.get("cross_sections"),
          s1.get("flow_basis"))

# ── stock vs flow are labelled, and a big fleet discloses its basis ────────
print("\n=== disclosure ===")
sec0 = (fwd.get("sections") or [{}])[0]
check("section reports flow v/c and its capacity flow",
      sec0.get("cap_flow_per_h") and sec0.get("peak_flow_per_h") is not None, sec0.keys())
check("section reports presence separately",
      sec0.get("cap_trucks_present") and sec0.get("ratio_presence") is not None, sec0.keys())
big = sf.shared_flow([{"id": "big", "source": "TF", "destination": "HUAFEI",
                       "n_trucks": 5000, "contractor": "RIM"}],
                     shift_hours=12, rain_mm=0, path=FX, whole_day=True)
bb = big.get("basis") or {}
check("5000 DT: planned trucks echoed", bb.get("trucks_planned") == 5000, bb.get("trucks_planned"))
check("5000 DT: simulated basis disclosed",
      bb.get("trucks_simulated") < 5000 and bb.get("max_truck_weight", 1) > 1
      and "representative" in (bb.get("simulation") or ""), bb)
check("5000 DT: sample is weighted, not truncated",
      abs(big["summary"]["executed_trips"] - big["summary"]["expected_trips"])
      / max(big["summary"]["expected_trips"], 1e-9) < 0.02,
      (big["summary"]["executed_trips"], big["summary"]["expected_trips"]))
unseen = sf.shared_flow([{"id": "u", "source": "NOWHERE", "destination": "NOPLACE",
                          "n_trucks": 30}], shift_hours=12, path=FX)
check("unseen route is flagged, not priced silently",
      "NOWHERE>NOPLACE" in ((unseen.get("basis") or {}).get("unpriced_routes") or [])
      and any("NOWHERE" in w for w in (unseen.get("warnings") or [])),
      unseen.get("warnings"))
check("doctrine unchanged on every call",
      all((x.get("basis") or {}).get("congestion_clips_tonnes") is False
          and (x.get("basis") or {}).get("simulate_unchanged") is True
          for x in (fwd, rev, big, unseen)))

# ── other tenants on the road (owner, 2026-08-24) ──────────────────────────
# "Start showing tenant pricing in everything ... in road congestion." The
# corridor now carries the register's 1,340 DT as a constant background.
# Asserted in BOTH directions, and with our own trucks held separate: a gate
# that only checked "the number went up" is passed by adding traffic anywhere,
# including to our own fleet, which would misreport what the planner can fix.
_tp = [{"id": "t1", "source": "TF", "destination": "HUAFEI", "n_trucks": 120,
        "contractor": "RIM"},
       {"id": "t2", "source": "BLB", "destination": "FENI KM0", "n_trucks": 30,
        "contractor": "RIM"}]
_off = sf.shared_flow(_tp, shift_hours=12, whole_day=True, tenants=False)
_on = sf.shared_flow(_tp, shift_hours=12, whole_day=True, tenants=True)
_off_s = {s["section"]: s for s in _off["sections"]}
_on_s = {s["section"]: s for s in _on["sections"]}

check("tenants OFF says so, and adds nothing",
      (_off["basis"].get("tenant_traffic") is False
       and all(s.get("tenant_trucks_present", 0) == 0 for s in _off["sections"])),
      _off["basis"].get("tenant_traffic"))
check("tenants ON says so, and names the DT",
      (_on["basis"].get("tenant_traffic") is True
       and _on["basis"].get("tenant_dt") == 1340),
      _on["basis"].get("tenant_dt"))
_main = "POS 12–KM15"
if _main in _on_s:
    check("tenants raise the busiest mainline section",
          _on_s[_main]["peak_concurrent"] > _off_s[_main]["peak_concurrent"] * 1.5,
          (_off_s[_main]["peak_concurrent"], _on_s[_main]["peak_concurrent"]))
    check("tenants raise its v/c too",
          _on_s[_main]["ratio"] > _off_s[_main]["ratio"],
          (_off_s[_main]["ratio"], _on_s[_main]["ratio"]))
    # The load the planner CAN move must be reported unchanged, or the card
    # cannot answer "would moving our trucks help?".
    check("our own trucks are unchanged by the tenant flag",
          abs(_on_s[_main]["our_peak_concurrent"]
              - _off_s[_main]["peak_concurrent"]) < 0.05,
          (_off_s[_main]["peak_concurrent"], _on_s[_main]["our_peak_concurrent"]))
# The BLB spur is off the shared mainline: no tenant runs it, so it must be
# byte-identical with the flag on. Catches a blanket "add background
# everywhere" implementation, which would read as tenants on a road they
# have never driven.
_spur = [s for s in _on["sections"] if s["section"].endswith(" spur")]
check("the BLB spur gets no tenant load at all",
      bool(_spur) and all(s.get("tenant_trucks_present", 0) == 0 for s in _spur)
      and all(abs(_on_s[s["section"]]["peak_concurrent"]
                  - _off_s[s["section"]]["peak_concurrent"]) < 1e-9
              for s in _spur),
      [(s["section"], s.get("tenant_trucks_present")) for s in _spur])
check("tenant traffic still never clips tonnes",
      (_on["basis"].get("congestion_clips_tonnes") is False
       and _on["basis"].get("simulate_unchanged") is True))

# ── RSF geography: a tenant is only on the kilometres it actually drives ────
# Two fleets turn off at RSF (km 26), so tenant load is NOT the same set of
# fleets all the way down the stick. This is the assertion that would catch a
# regression to "add every tenant to every section", which is the easy wrong
# implementation and looks entirely plausible on screen.
_named = {s["section"]: {t["name"] for t in (s.get("tenant_plans") or [])}
          for s in _on["sections"]}
check("every loaded section names WHICH tenants are on it",
      all(_named.get(s["section"]) for s in _on["sections"]
          if s.get("tenant_trucks_present", 0) > 0),
      {k: sorted(v) for k, v in _named.items()})
# TF fleets load at TF (km 67.8) and stop at FENI KM15 (km 15.0): they are on
# the top of the stick and must NOT appear below KM15.
check("the TF tenants are on TF-KR",
      {"MHM", "POSITION", "PMA", "HSM"} <= _named.get("TF–KR", set()),
      sorted(_named.get("TF–KR", [])))
check("the TF tenants do NOT reach KM15-coast",
      not ({"MHM", "POSITION", "PMA", "HSM"} & _named.get("KM15–coast", set())),
      sorted(_named.get("KM15–coast", [])))
# KR>RSF runs km 39 -> 26: on KR-POS 12, and NOT above KR or below km 26.
check("KR>RSF is on KR-POS 12",
      "KR>RSF" in _named.get("KR–POS 12", set()), sorted(_named.get("KR–POS 12", [])))
check("KR>RSF never reaches TF-KR (it loads at KR)",
      "KR>RSF" not in _named.get("TF–KR", set()), sorted(_named.get("TF–KR", [])))
check("KR>RSF never reaches KM15-coast (it turns off at km 26)",
      "KR>RSF" not in _named.get("KM15–coast", set()),
      sorted(_named.get("KM15–coast", [])))
# HUAFEI>RSF returns km 26 -> 0 on the loaded lane: the LOWER stick only.
check("HUAFEI>RSF is on KM15-coast",
      "HUAFEI>RSF" in _named.get("KM15–coast", set()),
      sorted(_named.get("KM15–coast", [])))
check("HUAFEI>RSF never reaches TF-KR or KR-POS 12 (its leg starts at km 26)",
      "HUAFEI>RSF" not in _named.get("TF–KR", set())
      and "HUAFEI>RSF" not in _named.get("KR–POS 12", set()),
      (sorted(_named.get("TF–KR", [])), sorted(_named.get("KR–POS 12", []))))
# Per-section tenant trucks must sum to the section total, or the breakdown is
# decorative rather than the actual composition of the number above it.
for _s in _on["sections"]:
    _tp = _s.get("tenant_plans") or []
    if not _tp:
        continue
    check("%s: the named fleets sum to its tenant total" % _s["section"],
          abs(sum(t["trucks_present"] for t in _tp)
              - _s["tenant_trucks_present"]) < 0.15,
          (sum(t["trucks_present"] for t in _tp), _s["tenant_trucks_present"]))

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
