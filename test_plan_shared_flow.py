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

# TOFU load should resolve via TF alias (not silent wrong 10 unless TF missing)
tofu = next((p for p in (r2.get("paths") or []) if "TOFU" in (p.get("source") or "").upper()), None)
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

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
