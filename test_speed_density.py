"""Gate: the speed-density conclusion must stay falsifiable.

Two regressions this guards:
  1. Someone adds a congestion factor to the simulator on intuition. The measured
     effect is -4.8% at the extremes with no threshold, and the trip-level effect
     has the WRONG sign because dispatch chooses truck counts. Both are asserted
     here as executable claims.
  2. Someone reads the tiny slope as "no signal here" and drops the segment
     structure. The gate records that the within- and between-segment channels are
     genuinely different quantities, so the distinction is not lost.

Note on what this gate does NOT do: it cannot detect a switch from the within-cell
construction to a pooled one. Mutation-tested - collapsing every segment to one
label moves the slope from -0.0233 to -0.0271, both negative and both negligible,
so no sign or magnitude assertion discriminates. Claiming otherwise would be
decoration. Instead the cross-sectional confound is measured on its own below.

Needs data/congestion_seg_hourly.csv, so it skips in a clean checkout.
"""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import json
import numpy as np
import pandas as pd

import plan_simulator as ps

D = "/Users/lucky/wbn-fms-simulator/data/"
fails = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else "  <- " + detail))
    if not cond:
        fails.append(name)


print("=== no congestion factor may scale predicted tonnage ===")
ps.reset_cache()
r = ps.simulate({"plans": [
    {"route": "POS 12>FENI KM0", "source": "POS 12",
     "destination": "FENI KM0", "n_trucks": 5},
    {"route": "POS 12>FENI KM0", "source": "POS 12",
     "destination": "FENI KM0", "n_trucks": 60}]})
a, b = r["results"][0], r["results"][1]
# Per-truck productivity must not change with fleet size: the measured physical
# effect is -4.8% at the density extremes, far below this data's noise, and the
# trip-level effect has the wrong sign from dispatch selection.
check("trips/truck independent of truck count on the same route",
      abs(a["trips_per_shift_per_truck"] - b["trips_per_shift_per_truck"]) < 0.01,
      "%.3f vs %.3f: a congestion term has crept in"
      % (a["trips_per_shift_per_truck"], b["trips_per_shift_per_truck"]))
check("tonnage scales linearly with trucks (within rounding)",
      abs(b["planned_production_t"] / max(a["planned_production_t"], 1e-9)
          - 60.0 / 5.0) < 0.05,
      "ratio %.3f, expected 12.0"
      % (b["planned_production_t"] / max(a["planned_production_t"], 1e-9)))

print("\n=== the fit must reproduce, and stay negligible ===")
d = pd.read_csv(D + "congestion_seg_hourly.csv")
d = d[d.speed_kmh.between(1, 80) & (d.FIX_N >= 5)].copy()
g = d.groupby(["SEG_ID", "DIR"])
d["spd_c"] = d.speed_kmh - g.speed_kmh.transform("mean")
d["den_c"] = d.TRUCK_N - g.TRUCK_N.transform("mean")
x, y = d.den_c.values, d.spd_c.values
slope = float(np.sum(x * y) / np.sum(x * x))
resid = float(np.sum((y - slope * x) ** 2))
se = float(np.sqrt(resid / (len(x) - 1) / np.sum(x * x)))
t = slope / se

check("density variation is ample (>=20 distinct truck counts)",
      d.TRUCK_N.nunique() >= 20, "%d" % d.TRUCK_N.nunique())
check("slope is negative, so the physical sign is right",
      slope < 0, "%+.4f" % slope)
check("slope is statistically significant (|t| > 3)", abs(t) > 3, "t=%+.1f" % t)
# The whole point: significant does not mean actionable.
check("effect is negligible: |5-truck change| < 3% of mean speed",
      abs(slope * 5) / d.speed_kmh.mean() < 0.03,
      "%.2f%%" % (100 * abs(slope * 5) / d.speed_kmh.mean()))
check("no saturation threshold: top-band slope no steeper than 5x the overall",
      True if len(d[d.TRUCK_N >= 36]) < 200 else
      abs(float(np.sum(d[d.TRUCK_N >= 36].den_c * d[d.TRUCK_N >= 36].spd_c)
                / np.sum(d[d.TRUCK_N >= 36].den_c ** 2))) < abs(slope) * 5,
      "a collapsing top band would be actionable and must not be hidden")

print("\n=== within- and between-segment channels are different quantities ===")
# The within-segment slope answers "what does one more truck do to THIS segment".
# The cross-sectional correlation answers "are busy segments the slow ones".
# Keeping them separate is the whole reason for centring.
cell = d.groupby(["SEG_ID", "DIR"]).agg(sp=("speed_kmh", "mean"),
                                        tn=("TRUCK_N", "mean"))
cross = float(np.corrcoef(cell.tn, cell.sp)[0, 1])
print("  cross-sectional corr(segment density, segment speed) = %+.4f" % cross)
check("busy segments are not simply the slow segments (|r| < 0.5)",
      abs(cross) < 0.5,
      "%+.4f: a strong cross-sectional link would mean the within-cell slope "
      "is removing a real confound and both must be reported" % cross)
check("segment identity explains far more speed variation than density does",
      float(cell.sp.std()) > abs(slope) * float(d.TRUCK_N.std()),
      "segment-to-segment speed sd %.2f km/h vs density-driven %.4f"
      % (cell.sp.std(), abs(slope) * d.TRUCK_N.std()))

print("\n=== the trip-level effect must still have the WRONG sign ===")
tf = pd.read_csv(D + "trip_features.csv",
                 usecols=["trucks_on_route", "cycle_time_min"])
s = tf[tf.cycle_time_min.between(5, 600) & tf.trucks_on_route.notna()]
rr = float(np.corrcoef(s.trucks_on_route, s.cycle_time_min)[0, 1])
check("corr(trucks_on_route, cycle) is negative, i.e. endogenous",
      rr < 0, "%+.4f; if this turns positive, revisit the whole conclusion" % rr)
check("magnitude replicates the previously reported -0.13 within 0.05",
      abs(rr + 0.1293) < 0.05, "%+.4f vs -0.1293" % rr)

print("\n=== the published fit json must match a fresh computation ===")
j = json.load(open("/Users/lucky/wbn-fms-simulator/reports/speed_density_fit.json"))
check("published slope matches recomputation within 0.005",
      abs(j["within_cell_slope_kmh_per_truck"] - slope) < 0.005,
      "%.4f vs %.4f" % (j["within_cell_slope_kmh_per_truck"], slope))
check("published significance flag is true", bool(j["significant"]))

print("\n=== the GPS ceiling must be recorded, not quietly forgotten ===")
m = json.load(open("/Users/lucky/wbn-fms-simulator/reports/multiday_gps_summary.json"))
check("only 4 usable GPS days are claimed", len(m["usable_days"]) == 4,
      "%r" % m["usable_days"])
check("the ceiling reason is documented",
      "retention" in m["ceiling_reason"].lower() and len(m["ceiling_reason"]) > 80)

print()
if fails:
    print("FAILED: " + "; ".join(fails))
    sys.exit(1)
print("all speed-density gates pass")
