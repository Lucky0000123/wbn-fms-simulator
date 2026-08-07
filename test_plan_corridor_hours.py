"""Offline tests for Jul+ corridor hour profiles + day segments (no VPN)."""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")

import plan_analogues as pa
import plan_corridor_hours as pch

fails = []
FX = pch._FIXTURE


def check(name, cond, detail=""):
    print("   %-56s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


print("=== 1. parse + section map ===")
p = pch.parse_seg_id("TF KM54-55")
check("parse TF KM54-55", p is not None and p[0] == "TF" and abs(p[3] - 54.5) < 1e-6, p)
check("54.5 → TOFU–KR", pch.section_for_mid(54.5) == "TOFU–KR")
check("30.5 → KR–POS 12", pch.section_for_mid(30.5) == "KR–POS 12")
check("5.5 → POS 10–FENI", pch.section_for_mid(5.5) == "POS 10–FENI")
check("BLB not stick", pch._stick_seg("BLB KM8-9") is None)

print("\n=== 2. corridor_hours from fixture ===")
res = pch.corridor_hours(path=FX, dir_filter="down")
check("ok", res.get("ok") is True, res.get("error"))
check("source fixture", res.get("source") in ("fixture", "explicit"), res.get("source"))
check("24 hour buckets", len(res.get("hours") or []) == 24)
check("era struggle", (res.get("window") or {}).get("era") == "struggle")
check("never clips tonnes", res.get("basis", {}).get("congestion_clips_tonnes") is False)
check("simulate_unchanged", res.get("basis", {}).get("simulate_unchanged") is True)
# Evening 18–20 should be slower than midday in fixture
spd18 = next(h["speed_kmh"] for h in res["hours"] if h["h"] == 18)
spd12 = next(h["speed_kmh"] for h in res["hours"] if h["h"] == 12)
check("evening slower than midday", spd18 is not None and spd12 is not None and spd18 < spd12,
      (spd18, spd12))
check("slow_hours non-empty", len(res.get("slow_hours") or []) >= 1)
check("slow_sections non-empty", len(res.get("slow_sections") or []) >= 1)
# May synthetic spike must not enter window / hours when gated
check("window from ≥ GPS start",
      (res.get("window") or {}).get("from") is None
      or (res["window"]["from"] >= pa.GPS_HAUL_START),
      res.get("window"))

print("\n=== 3. section filter ===")
filt = pch.corridor_hours(sections=["KR–POS 12"], path=FX)
check("filtered ok", filt.get("ok") is True)
secs = [s["section"] for s in filt.get("by_section") or []]
check("only KR–POS 12", secs == ["KR–POS 12"] or (len(secs) == 1 and "KR–POS 12" in secs), secs)

print("\n=== 4. day_segments GPS gate ===")
may = pch.day_segments("2026-05-01", path=FX)
check("May has_gps false", may.get("has_gps") is False)
check("May segments empty", may.get("segments") == [])
check("May note mentions no invent", "not invented" in (may.get("note") or "").lower()
      or "no haul" in (may.get("note") or "").lower(), may.get("note"))
check("May no clips", may.get("basis", {}).get("congestion_clips_tonnes") is False)

jul = pch.day_segments("2026-07-21", path=FX)
check("Jul ok", jul.get("ok") is True)
check("Jul has_gps", jul.get("has_gps") is True)
check("Jul segments non-empty", len(jul.get("segments") or []) >= 1, len(jul.get("segments") or []))
seg0 = (jul.get("segments") or [{}])[0]
check("loaded + empty present",
      seg0.get("loadedKmh") is not None and seg0.get("emptyKmh") is not None, seg0)
check("empty faster than loaded (fixture)",
      seg0.get("emptyKmh") > seg0.get("loadedKmh"),
      (seg0.get("emptyKmh"), seg0.get("loadedKmh")))

print("\n=== 5. optimize helper ===")
slow = pch.slow_sections_for_optimize(path=FX)
check("slow helper list", isinstance(slow, list) and len(slow) >= 1, slow)

print("\n=== 6. gps coverage + stick rebuild (temp) ===")
cov = pch.gps_coverage(path=FX)
check("coverage ok", cov.get("ok") is True, cov.get("error"))
check("coverage has Jul days", any(d["date"].startswith("2026-07") for d in cov.get("days") or []),
      cov.get("days"))
check("coverage excludes May", all(d["date"] >= pa.GPS_HAUL_START for d in cov.get("days") or []))
import os, tempfile
td = tempfile.mkdtemp()
out = os.path.join(td, "by_dir.csv")
reb = pch.rebuild_by_dir_from_archive(path=FX, out_path=out)
check("rebuild ok", reb.get("ok") is True, reb)
check("rebuild rows", (reb.get("rows") or 0) >= 4, reb)
check("rebuild file exists", os.path.isfile(out))

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
