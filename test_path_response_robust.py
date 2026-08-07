#!/usr/bin/env python3
"""Gate: path-response avgTr is mid-60% trimmed mean (main cluster), with P25–P75."""
from __future__ import annotations

import json
import os
import sys

from simulator_api import _path_eff_pctile, _path_mid60_mean

fails = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print("  %-55s %s" % (name, "PASS" if ok else "FAIL"))
    if not ok:
        fails.append(name + ((" · " + str(detail)[:120]) if detail else ""))


print("=== path-response robust helpers ===")

# Planted outliers: raw mean is pulled high; mid-60% stays near the cluster.
cluster = [3.0, 3.1, 3.2, 3.0, 3.1, 3.05, 3.15, 2.95, 3.08, 3.12]
with_outliers = cluster + [0.1, 12.0]
raw = sum(with_outliers) / len(with_outliers)
mid = _path_mid60_mean(with_outliers)
check("mid60 ignores outliers", mid is not None and abs(mid - 3.075) < 0.15, mid)
check("mid60 below raw mean", mid is not None and mid < raw, "mid=%s raw=%s" % (mid, raw))

tiny = [1.0, 2.0, 3.0]
check("n<5 falls back to mean", abs(_path_mid60_mean(tiny) - 2.0) < 1e-9)

p25 = _path_eff_pctile(with_outliers, 0.25)
med = _path_eff_pctile(with_outliers, 0.5)
p75 = _path_eff_pctile(with_outliers, 0.75)
check("percentiles ordered", p25 is not None and med is not None and p75 is not None and p25 <= med <= p75,
      "p25=%s med=%s p75=%s" % (p25, med, p75))
check("empty pctile is None", _path_eff_pctile([], 0.5) is None)
check("empty mid60 is None", _path_mid60_mean([]) is None)

print("=== fixture companion fields ===")
fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "path-response.json")
with open(fx, encoding="utf-8") as fh:
    data = json.load(fh)
paths = data.get("paths") or {}
check("fixture has paths", len(paths) > 0)
sample = next(iter(paths.values()), {})
for key in ("avgTr", "meanTr", "trP25", "trMed", "trP75"):
    check("fixture has %s" % key, isinstance(sample.get(key), (int, float)), sample.get(key))

# Smoke: building a record-shaped dict from helpers matches field contract used by Plan.
eff = with_outliers
rec = {
    "avgTr": round(_path_mid60_mean(eff), 3),
    "meanTr": round(sum(eff) / len(eff), 3),
    "trP25": round(_path_eff_pctile(eff, 0.25), 3),
    "trMed": round(_path_eff_pctile(eff, 0.5), 3),
    "trP75": round(_path_eff_pctile(eff, 0.75), 3),
}
check("record avgTr finite", rec["avgTr"] > 0)
check("record band ordered", rec["trP25"] <= rec["trMed"] <= rec["trP75"])
check("record avgTr != mean when outliers", rec["avgTr"] != rec["meanTr"])

if fails:
    print("FAIL:", "; ".join(fails))
    sys.exit(1)
print("path-response robust gate passes")
