"""Gate J69: GPS-first flow motion + posted-limit overlay.

Tab 1 animation must use measured GPS segment speeds (FMS_CONGESTION_SEG /
congestion_seg_by_dir), with Excel-derived posted limits as a comparison ribbon
— not as the motion driver. Live capability must ship both layers; BLB/BB spur
zones must not paint on the TF→FENI stick by raw km.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name
          + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


print("=== offline: posted CSV + corridor layers ===")
csv_path = os.path.join(ROOT, "data", "speed_limit_zones_public.csv")
check("speed_limit_zones_public.csv exists", os.path.isfile(csv_path), csv_path)

import simulator_api as sa

# Reset layer cache in case a prior import pointed elsewhere.
sa._CORRIDOR_LAYERS = None
stick, all_zones = sa._load_posted_speed_limits()
check("posted stick zones >= 15 (TF/KR)", len(stick) >= 15, len(stick))
check("posted all zones include spurs", len(all_zones) >= 20, len(all_zones))
tf10 = [z for z in stick if z["segment"] == "SL_TF_10_30"]
check("SL_TF_10_30 on stick: fromKm≈68 toKm≈65 limit=30",
      bool(tf10) and abs(tf10[0]["fromKm"] - 68) < 0.2
      and abs(tf10[0]["toKm"] - 65) < 0.2 and abs(tf10[0]["limit"] - 30) < 0.01,
      tf10[:1])
blb_stick = [z for z in stick if z.get("road") in ("BLB", "BB")
             or str(z.get("segment", "")).startswith("SL_BLB")
             or str(z.get("segment", "")).startswith("SL_BB")]
check("BLB/BB spur zones NOT on stick speedLimits",
      len(blb_stick) == 0, blb_stick[:3])
spur = [z for z in all_zones if not z.get("onStick")]
check("spur zones retained off-stick", len(spur) >= 4, len(spur))

c = sa._corridor_payload()
check("corridor.speedLimits from CSV",
      len(c.get("speedLimits") or []) >= 15, len(c.get("speedLimits") or []))
meas = c.get("measuredSpeeds") or []
# File may be absent on a clean clone — then measured can be empty offline.
by_dir = os.path.join(ROOT, "data", "congestion_seg_by_dir.csv")
if os.path.isfile(by_dir):
    check("measuredSpeeds >= 20 when congestion_seg_by_dir present",
          len(meas) >= 20, len(meas))
    check("measuredWindow present",
          isinstance(c.get("measuredWindow"), dict)
          and c["measuredWindow"].get("from")
          and c["measuredWindow"].get("to"),
          c.get("measuredWindow"))
    check("measured bands have loadedKmh",
          any(m.get("loadedKmh") is not None for m in meas),
          meas[:1])
    mc = c.get("measuredCapacity") or {}
    check("measuredCapacity trucksPerHour > 5",
          (mc.get("trucksPerHour") or 0) > 5, mc)
else:
    print("  SKIP measuredSpeeds file asserts (no congestion_seg_by_dir.csv)")

# Fixture parity
fx = json.load(open(os.path.join(ROOT, "fixtures", "capability.json"),
                    encoding="utf-8"))
fc = fx.get("corridor") or {}
check("fixture corridor has speedLimits >= 15",
      len(fc.get("speedLimits") or []) >= 15, len(fc.get("speedLimits") or []))
check("fixture corridor has measuredSpeeds sample",
      len(fc.get("measuredSpeeds") or []) >= 10,
      len(fc.get("measuredSpeeds") or []))

print("\n=== offline: JS honesty (motion = GPS, openFactor killed) ===")
js = open(os.path.join(ROOT, "static", "js", "flow_sim.js"), encoding="utf-8").read()
html = open(os.path.join(ROOT, "templates", "simulator.html"), encoding="utf-8").read()
check("gpsSpeedAt helper present", "function gpsSpeedAt" in js)
check("replay sets sharedOpenFactor=1", "p.sharedOpenFactor=1" in js)
check("does not reintroduce openFactor stretch clamp",
      "Math.min(2.5,targetAvg" not in js.replace(" ", ""))
check("Use measured GPS control in HTML", "flowUseMeasuredGps()" in html)
check("headway control present", "flow-headway" in html)
check("GPS map container present", 'id="c3-flow-map"' in html)

# Live HTTP
try:
    with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("\nno server on 5055 (%s) — offline checks only" % str(exc)[:60])
    mode = None

if mode in ("database", "sample-fixtures", "fixture"):
    print("\n=== live: capability corridor layers ===")
    with urllib.request.urlopen(
            BASE + "/api/simulator/capability?from=2026-07-01&to=2026-07-31",
            timeout=120) as r:
        d = json.loads(r.read())
    cor = d.get("corridor") or {}
    # Fixture fallback also OK if it carries the layers.
    check("live speedLimits >= 15",
          len(cor.get("speedLimits") or []) >= 15,
          len(cor.get("speedLimits") or []))
    if mode == "database":
        check("live measuredSpeeds >= 20 (or disk fixture sample)",
              len(cor.get("measuredSpeeds") or []) >= 20
              or len(cor.get("measuredSpeeds") or []) >= 10,
              len(cor.get("measuredSpeeds") or []))
        blb = [z for z in (cor.get("speedLimits") or [])
               if str(z.get("segment", "")).startswith("SL_BLB")
               or str(z.get("segment", "")).startswith("SL_BB_")]
        check("live stick speedLimits exclude BLB/BB",
              len(blb) == 0, blb[:3])
else:
    print("\n(no live server — skipped HTTP asserts)")

print()
if FAILED:
    print("J69 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("flow GPS / posted-limit gate passes")
