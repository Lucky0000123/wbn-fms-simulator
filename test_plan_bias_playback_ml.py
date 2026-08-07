"""Gates for bias lens, Playback truth, and Jul+ congestion advice."""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")

import plan_bias as pb
import plan_playback as pp
import plan_congestion_ml as pcm
import plan_corridor_hours as pch
import plan_simulator as ps

fails = []
FX = pch._FIXTURE


def check(name, cond, detail=""):
    print("   %-56s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


print("=== 1. bias lens + ticket companion ===")
off = pb.bias_lens(10550, enabled=False)
check("off raw=adj display", off["raw_achievable_t"] == 10550 and off["adjusted_achievable_t"] == 10550)
check("does not train away", off["basis"]["trains_away_bias"] is False)
check("engine unchanged flag", off["engine_unchanged"] is True)
check("availability stays 1.0", off["availability_factor"] == 1.0)
on = pb.bias_lens(10550, enabled=True)
check("on adjusts ÷1.055", on["adjusted_achievable_t"] == 10000, on)
check("on keeps raw", on["raw_achievable_t"] == 10550)
check("measured bias 5.5%", abs(on["measured_bias"] - 0.055) < 1e-9)
check("ticket_calibrated helper", pb.ticket_calibrated_t(10550) == 10000)

# Simulate engine still returns raw with avail=1.0; companion is separate
sim = ps.simulate({
    "plans": [{"source": "TF", "destination": "FENI KM15", "n_trucks": 30}],
    "weather": "dry", "shift_minutes": 720,
})
ach = (sim.get("summary") or {}).get("achievable_production_t")
cal = (sim.get("summary") or {}).get("ticket_calibrated_achievable_t")
check("simulate returns achievable", ach is not None and ach > 0, ach)
check("companion present", cal is not None and cal > 0, cal)
check("companion ≈ raw/1.055", abs(cal - round(ach / 1.055, 0)) < 1.5, (cal, ach))
check("companion not primary", cal != ach or ach == 0, (cal, ach))
check("calibration not applied to primary",
      (sim.get("summary") or {}).get("ticket_calibration", {}).get("applied_to_primary") is False)
fac = (sim.get("summary") or {}).get("availability_factor_applied")
if fac is None:
    fac = (sim.get("results") or [{}])[0].get("availability_factor")
check("simulate does not use 0.85", fac in (None, 1, 1.0) or abs(float(fac) - 1.0) < 1e-9, fac)

print("\n=== 2. playback truth — no invent ===")
truth = pp.load_playback_truth()
check("truth ok", truth.get("ok") is True)
check("overlap 0", float(truth.get("playback", {}).get("haul_plate_overlap_pct", 1)) == 0.0)
check("invent flag false", truth.get("invent_jan_may_haul_speeds") is False)
check("may speeds empty", truth.get("may_haul_speeds") == [])
check("has_haul_gps may false", truth.get("has_haul_gps_may") is False)
may = pp.refuse_invented_speeds("2026-05-01")
check("refuse may invented false", may.get("invented") is False)
check("refuse may speeds empty", may.get("speeds") == [])
check("refuse may no haul gps", may.get("has_haul_gps") is False)
jul = pp.refuse_invented_speeds("2026-07-20")
check("jul points to real APIs", "day-segments" in (jul.get("note") or "") or jul.get("has_haul_gps") is True)

print("\n=== 3. congestion advice (Jul+ only) ===")
adv = pcm.congestion_advice(
    path=FX,
    plan_dt_by_section={"KR–POS 12": 40, "TOFU–KR": 80, "POS 10–FENI": 55},
    vc_by_section={"POS 10–FENI": 2.49, "KR–POS 12": 0.48},
    limit_gap_by_section={"POS 10–FENI": {"gps_kmh": 16.0, "posted_kmh": 30.0, "gap_kmh": 14.0}},
)
check("advice ok", adv.get("ok") is True, adv.get("error"))
check("never clips", adv.get("basis", {}).get("congestion_clips_tonnes") is False)
check("no playback invent", adv.get("basis", {}).get("invents_playback_haul_speeds") is False)
check("struggle era", (adv.get("model") or {}).get("era") == "struggle")
check("has advice rows", len(adv.get("advice") or []) >= 1, adv.get("advice"))
check("ranked hours", len(adv.get("ranked_hours") or []) >= 6)
check("meter or slow advice",
      any(a.get("kind") in ("meter_release", "slow_section", "plan_crosses_slow", "smooth_timetable")
          for a in (adv.get("advice") or [])),
      [a.get("kind") for a in (adv.get("advice") or [])])
smooth = adv.get("smooth_actions") or []
check("smooth_actions present", len(smooth) >= 1, smooth)
check("joint score flag", adv.get("basis", {}).get("joint_hour_section_score") is True)
check("uses illustration vc", adv.get("basis", {}).get("uses_illustration_vc") is True)
if smooth:
    s0 = smooth[0]
    check("smooth has section+window", bool(s0.get("section") and s0.get("window")), s0)
    check("smooth text advisory", "does not change simulate" in (s0.get("text") or "").lower(), s0.get("text"))
    check("high V/C section ranked",
          any(a.get("section") == "POS 10–FENI" for a in smooth)
          or any((a.get("vc") or 0) >= 1 for a in smooth),
          [a.get("section") for a in smooth])

# Direct scorer unit (no network)
import plan_smooth_advice as psa
fit = {"by_hour": {h: {"h": h, "speed_kmh": 18 - (3 if h in (18, 19, 20) else 0), "truck_n": 5}
                   for h in range(24)},
       "free_flow_kmh": 18.0, "slow_sections": [{"section": "POS 10–FENI", "speed_kmh": 15.0}]}
acts = psa.build_smooth_actions(
    fit, hours_payload={"by_section": [{"section": "POS 10–FENI", "speed_kmh": 15.0}]},
    plan_dt_by_section={"POS 10–FENI": 60},
    vc_by_section={"POS 10–FENI": 2.0},
)
check("scorer returns windows", len(acts) >= 1, acts)
check("scorer evening window",
      any(a.get("hour_from", 99) <= 20 and a.get("hour_to", -1) >= 18 for a in acts),
      acts)

print("\n=== 4. peak reference + single-day ops ===")
import plan_peak_proxy as ppp
peak = ppp.peak_road_proxy()
check("peak ok", peak.get("ok") is True)
check("peak era", (peak.get("window") or {}).get("era") == "peak")
check("peak is reference", peak.get("is_reference") is True)
check("peak scope average", peak.get("basis", {}).get("scope") == "peak_season_average")
check("no speeds invented", peak.get("speeds_kmh") is None)
check("invent flag false", peak.get("invents_playback_haul_speeds") is False)
check("sections non-empty", len(peak.get("sections") or []) >= 1, peak.get("sections"))
check("never clips", peak.get("basis", {}).get("congestion_clips_tonnes") is False)

# Single-day must not reuse Jan–May averages as that day's numbers
day = ppp.day_road_ops("2026-03-15")
check("day ops ok", day.get("ok") is True, day.get("error"))
check("day scope single", day.get("basis", {}).get("scope") == "single_day")
check("day date stamped", day.get("date") == "2026-03-15")
if day.get("has_ops") and day.get("sections"):
    s0 = day["sections"][0]
    check("day uses dt not multi-month avg label", s0.get("dt") == s0.get("total_dt"), s0)
empty = ppp.day_road_ops("2099-01-01")
check("empty future day has_ops false", empty.get("has_ops") is False)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
