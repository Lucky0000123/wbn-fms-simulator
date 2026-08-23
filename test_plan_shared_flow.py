#!/usr/bin/env python3
"""Unit checks for DES-lite shared-road occupancy."""
from __future__ import annotations

import sys

import plan_corridor_hours as pch
import plan_shared_flow as sf

fails = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print("  %-55s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        fails.append(name + ((" · " + str(detail)[:120]) if detail else ""))


FX = pch._FIXTURE

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

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
