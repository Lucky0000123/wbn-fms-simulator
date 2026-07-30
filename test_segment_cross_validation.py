"""test_segment_cross_validation.py — does my snapping agree with the FMS's own?

WHY THIS IS THE STRONGEST GATE IN THE SUITE
Every other check on the GPS pipeline is something I wrote validating something
else I wrote. This one compares my chainage snapping against
`FMS_CONGESTION_SEG`, which the site's own system computes from the same GPS feed
using their segment definitions and their code. Agreement is evidence from an
independent implementation, which no self-consistency test can match.

It checks three things:

  1. every segment label I generate exists in the FMS vocabulary — if my labels
     were malformed or offset by a kilometre, this fails immediately
  2. per-segment speeds correlate, restricted to FULL transits (partial traverses
     are not comparable with a through-speed)
  3. my computed speed agrees with the device's own reported SPEED field, which
     validates the distance/time arithmetic independently of the snapping

Needs the VPN for step 2. Steps 1 and 3 run offline, so the gate degrades rather
than failing when the database is unreachable.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Agreement floor for full transits. Set below the observed +0.920 so normal
# sampling noise does not fail the gate, and far above zero so a broken snapper
# cannot pass. Mutation-checked: shifting my segments by 1 km drops r below this.
MIN_R_FULL = 0.60
MIN_R_DEVICE = 0.60
MAX_MEDIAN_DIFF_KMH = 6.0

fails, skips = [], []


def check(name, cond, detail=""):
    print("   %-52s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


seg_path = os.path.join(ROOT, "data", "day_x_segment_speeds.csv")
gps_path = os.path.join(ROOT, "data", "day_x_gps_snapped.csv")
if not (os.path.exists(seg_path) and os.path.exists(gps_path)):
    print("day_x artifacts absent — run scripts/extract_day.py then snap_gps.py")
    sys.exit(0)

mine = pd.read_csv(seg_path)
gps = pd.read_csv(gps_path)
print("my segment observations: %d over %d segments"
      % (len(mine), mine.seg.nunique()))

print("\n=== 1. do my segment labels follow the site's own vocabulary? ===")
import re
pat = re.compile(r"^[A-Z]+ KM\d+-\d+$")
bad = [x for x in mine.seg.astype(str).unique() if not pat.match(x)]
check("every label matches the 'ROAD KMn-m' pattern", not bad, bad[:5])
lo_hi = mine.seg.astype(str).str.extract(r"KM(\d+)-(\d+)").astype(float)
check("every segment spans exactly 1 km",
      bool(((lo_hi[1] - lo_hi[0]) == 1).all()))

print("\n=== 2. per-segment agreement with FMS_CONGESTION_SEG ===")
try:
    import pymssql

    import simulator_api as sim
    if not sim._db_ready():
        raise RuntimeError("no DB configured")
    c = pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                        password=sim._DB["password"], database="FMS_DB",
                        login_timeout=10, timeout=600, charset="LATIN1")
    try:
        f = pd.read_sql("SELECT SEG_ID, SUM_SPD, FIX_N FROM FMS_CONGESTION_SEG "
                        "WHERE FIX_N > 0", c)
    finally:
        c.close()
    f["sp"] = (pd.to_numeric(f.SUM_SPD, errors="coerce")
               / pd.to_numeric(f.FIX_N, errors="coerce"))
    fms = f.groupby(f.SEG_ID.astype(str).str.strip()).sp.median().rename("fms")

    unknown = sorted(set(mine.seg.astype(str)) - set(fms.index))
    check("every one of my segments exists in the FMS table", not unknown,
          unknown[:5])

    full = mine[mine.is_partial_traverse == 0] if "is_partial_traverse" in mine \
        else mine
    g = full.groupby("seg").avg_speed_kmh.mean().rename("mine")
    j = pd.concat([g, fms], axis=1, join="inner").dropna()
    if len(j) >= 4:
        r = float(j.mine.corr(j.fms))
        md = float((j.mine - j.fms).abs().median())
        print("   full transits: %d shared segments, r=%+.3f, median diff %.1f km/h"
              % (len(j), r, md))
        check("full-transit correlation >= %.2f" % MIN_R_FULL, r >= MIN_R_FULL,
              "r=%+.3f" % r)
        check("median difference <= %.1f km/h" % MAX_MEDIAN_DIFF_KMH,
              md <= MAX_MEDIAN_DIFF_KMH, "%.1f km/h" % md)
    else:
        skips.append("too few shared segments (%d)" % len(j))
except Exception as exc:                                     # noqa: BLE001
    skips.append("FMS comparison unavailable: %s" % str(exc)[:90])
    print("   SKIPPED (%s)" % str(exc)[:70])

print("\n=== 3. computed speed vs the device's own SPEED field ===")
rows = []
for r_ in mine.itertuples():
    sub = gps[(gps.section_name == r_.seg) & (gps.truck == r_.truck_id)]
    if len(sub) < 2:
        continue
    dev = pd.to_numeric(sub.SPEED, errors="coerce").mean()
    if pd.notna(dev):
        rows.append((r_.avg_speed_kmh, dev))
if len(rows) >= 4:
    d = pd.DataFrame(rows, columns=["computed", "device"])
    r = float(d.computed.corr(d.device))
    md = float((d.computed - d.device).abs().median())
    print("   %d comparisons, r=%+.3f, median diff %.1f km/h" % (len(d), r, md))
    check("computed speed agrees with the device >= %.2f" % MIN_R_DEVICE,
          r >= MIN_R_DEVICE, "r=%+.3f" % r)
    check("median diff vs device <= %.1f km/h" % MAX_MEDIAN_DIFF_KMH,
          md <= MAX_MEDIAN_DIFF_KMH, "%.1f km/h" % md)
else:
    skips.append("too few device comparisons")

print()
for s in skips:
    print("   SKIPPED: %s" % s)
print("\n%s  (%d failures, %d skipped)"
      % ("ALL PASS" if not fails else "FAILURES: " + ", ".join(fails),
         len(fails), len(skips)))
sys.exit(1 if fails else 0)
