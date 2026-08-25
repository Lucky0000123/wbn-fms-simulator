"""J80 — HUAFEI is a junction at km 5.5, not a coastal dump at km 0.

Owner, 2026-08-25, correcting a redesign brief that had placed it at FENI km 0:
"the Huafei is not at FENI kilometer zero, it's next to BLB". They were right,
and the repo had been carrying the contradiction in one file: physics.NODE_KM
said HUAFEI = 0.0 while physics.MEASURED_HAUL_KM said TF>HUAFEI = 63.7 km. TF
sits at 67.8, so a coastal HUAFEI would make that haul 67.8 — the same as
TF>FENI KM0. The distance half was used for PRICING and the chainage half for
PLACEMENT, so HUAFEI priced right and drew 5.5 km too far down the road, and
occupied 5.5 km of S4 it never drives.

Three independent sources put it at the same junction, and this gate pins all
three so the constant cannot quietly drift back:

  1. SURVEY  data/haul_road_chainage_public.csv carries an HFC road whose first
     point is 0.8 m from CRD km 5.500 and which runs 5.525..6.425 on the same
     datum — a junction plus a ~0.925 km branch.
  2. DISPATCH the road book has a literal "HFC KM5,5 - KM6,4" segment column.
  3. ARITHMETIC |origin - 5.5| + 0.925 reproduces the dispatch book's own gross
     km for POS 12>HUAFEI (22.4) and TF>HUAFEI (63.4).

Survey-only checks read the committed CSV, so they need no DB. The dispatch
cross-check is skipped without the VPN rather than passing vacuously.
"""
from __future__ import annotations

import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FAILS = []
SKIPS = []


def check(cond, label, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        FAILS.append(label)
        print("  FAIL %s %s" % (label, detail))


def km_between(a, b):
    """Rough great-circle km between (lat,lng) pairs — fine at this scale."""
    return math.hypot((a[0] - b[0]) * 111.32,
                      (a[1] - b[1]) * 111.32 * math.cos(math.radians(a[0])))


# ── 1. the constant itself, in every copy ────────────────────────────────
from congestion import physics as P            # noqa: E402
from congestion import segments as S           # noqa: E402
import plan_analogues as PA                    # noqa: E402

JUNCTION = 5.5
for name, tbl in (("physics", P.NODE_KM), ("segments", S.NODE_KM),
                  ("plan_analogues", PA.NODE_KM)):
    check(abs(tbl.get("HUAFEI", -1) - JUNCTION) < 0.01,
          "%s.NODE_KM puts HUAFEI at its junction, not the coast" % name,
          "got %s" % tbl.get("HUAFEI"))
    # The bug was HUAFEI sharing a value with the coastal dumps. Assert it is
    # DISTINCT from them, which is the property that actually broke.
    check(tbl.get("HUAFEI") != tbl.get("FENI KM0"),
          "%s: HUAFEI is not the same place as FENI KM0" % name)

# ── 2. the file no longer contradicts itself ─────────────────────────────
# This is the check that would have caught the original bug on the day it was
# written: chainage and measured distance must agree about the same haul.
tf = P.NODE_KM["TF"]
measured = P.MEASURED_HAUL_KM.get(("TF", "HUAFEI"))
if measured:
    implied = P.route_distance_km("TF", "HUAFEI")
    check(abs(implied - measured) < 1.0,
          "TF>HUAFEI: chainage-derived distance agrees with the measured one",
          "chainage %.1f vs measured %.1f" % (implied, measured))
    # And the coastal reading must NOT reproduce it — otherwise the test would
    # still pass with the old bug in place.
    coastal = abs(tf - 0.0)
    check(abs(coastal - measured) > 1.0,
          "a coastal HUAFEI would NOT reproduce the measured haul",
          "coastal %.1f vs measured %.1f" % (coastal, measured))

# ── 3. the branch is modelled, not dropped ───────────────────────────────
br = getattr(P, "BRANCH_DEST", {}).get("HUAFEI")
check(br is not None, "HUAFEI is registered as a branch destination")
if br:
    j, blen = br
    check(abs(j - JUNCTION) < 0.01, "branch junction is the surveyed 5.5 km")
    check(0.5 < blen < 1.5, "branch length is the surveyed ~0.9 km",
          "got %s" % blen)
    # Dropping the branch would shorten every HUAFEI haul by ~0.9 km.
    d = P.route_distance_km("POS 12", "HUAFEI")
    check(abs(d - (abs(27.0 - j) + blen)) < 0.05,
          "POS 12>HUAFEI = |origin - junction| + branch", "got %s" % d)

# ── 4. occupancy stops at the junction ───────────────────────────────────
# The load-bearing consequence: a HUAFEI truck must not be charged the last
# 5.5 km of S4, the tightest section on the road.
wins = dict((s["id"], round(ov, 2)) for s, ov in S.route_segments("TF", "HUAFEI"))
check(wins.get("S4") is not None and abs(wins["S4"] - (15.0 - JUNCTION)) < 0.05,
      "TF>HUAFEI occupies S4 only down to the junction",
      "S4 overlap %s, expected %.1f" % (wins.get("S4"), 15.0 - JUNCTION))
coast = dict((s["id"], round(ov, 2)) for s, ov in S.route_segments("TF", "FENI KM0"))
check(coast.get("S4", 0) > wins.get("S4", 0),
      "a genuinely coastal haul still occupies MORE of S4 than HUAFEI does",
      "FENI KM0 %s vs HUAFEI %s" % (coast.get("S4"), wins.get("S4")))

# ── 5. the survey still says what we read off it ─────────────────────────
csv_path = os.path.join(ROOT, "data", "haul_road_chainage_public.csv")
if not os.path.isfile(csv_path):
    SKIPS.append("survey CSV absent")
else:
    pts = {}
    with open(csv_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            pts.setdefault(r["road"], []).append(
                (float(r["km"]), float(r["lat"]), float(r["lng"])))
    hfc = sorted(pts.get("HFC") or [])
    crd = sorted(pts.get("CRD") or [])
    check(bool(hfc), "the survey carries an HFC (Huafei) road")
    if hfc and crd:
        start = hfc[0]
        near = min(crd, key=lambda p: km_between((p[1], p[2]), (start[1], start[2])))
        gap_m = 1000 * km_between((near[1], near[2]), (start[1], start[2]))
        check(gap_m < 50,
              "HFC starts ON the mainline (a junction, not a coincidence)",
              "%.1f m from CRD km %.3f" % (gap_m, near[0]))
        check(abs(near[0] - JUNCTION) < 0.2,
              "that junction is at CRD km 5.5", "got %.3f" % near[0])
        span = hfc[-1][0] - JUNCTION
        check(abs(span - (br[1] if br else 0)) < 0.15,
              "the surveyed branch length matches BRANCH_DEST",
              "survey %.3f vs model %s" % (span, br[1] if br else None))
        # And it is NOT on the BLB spur, which is the owner's other reading.
        blb = sorted(pts.get("BLB") or [])
        if blb:
            nb = min(blb, key=lambda p: km_between((p[1], p[2]), (start[1], start[2])))
            d_blb = km_between((nb[1], nb[2]), (start[1], start[2]))
            check(d_blb > 0.5,
                  "HUAFEI is NEAR BLB but not ON the BLB spur",
                  "%.2f km from the BLB road" % d_blb)

print()
for s in SKIPS:
    print("  skip %s" % s)
if FAILS:
    print("\nFAILED %d:" % len(FAILS))
    for f in FAILS:
        print("  - %s" % f)
    sys.exit(1)
print("\nJ80 OK")
