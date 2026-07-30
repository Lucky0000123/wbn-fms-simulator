"""Gate: availability is used for fleet sizing and NEVER for tonnage.

The regression this guards is specific. A future reader sees availability data
sitting in the repo, sees the simulator not multiplying by it, assumes that is an
oversight and "fixes" it. That would reintroduce a measured -11.8% bias. The gate
states the finding as an executable claim so the assumption cannot be made
silently.
"""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import math
import pandas as pd

import plan_simulator as ps

fails = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else "  <- " + detail))
    if not cond:
        fails.append(name)


print("=== availability must NOT scale tonnage ===")
ps.reset_cache()
r = ps.simulate({"plans": [
    {"route": "POS 12>FENI KM0", "source": "POS 12",
     "destination": "FENI KM0", "n_trucks": 30}]})
check("availability_factor_applied is 1.0",
      r["summary"]["availability_factor_applied"] == 1.0,
      "got %r; the effective cycle already contains downtime"
      % r["summary"]["availability_factor_applied"])
check("DEFAULT_AVAILABILITY is 1.0", ps.DEFAULT_AVAILABILITY == 1.0,
      "got %r" % ps.DEFAULT_AVAILABILITY)

res = r["results"][0]
# The independent arithmetic: tonnage is trucks x trips x payload, with no
# availability term anywhere in it.
expect = res["n_trucks"] * res["trips_per_shift_per_truck"] * res["avg_payload_t"]
check("tonnage = trucks x trips x payload, no availability term",
      abs(res["planned_production_t"] - expect) <= 3.0,
      "%.1f vs %.1f (slack allows only per-plan rounding)"
      % (res["planned_production_t"], expect))

print("\n=== availability MUST drive fleet sizing ===")
check("per-plan trucks_to_roster present", "trucks_to_roster" in res)
check("summary fleet_sizing present", "fleet_sizing" in r["summary"])
if "trucks_to_roster" in res:
    want = math.ceil(30 / ps.MEASURED_MECHANICAL_AVAILABILITY)
    check("30 hauling -> %d rostered" % want, res["trucks_to_roster"] == want,
          "got %r" % res["trucks_to_roster"])
    check("roster exceeds hauling count", res["trucks_to_roster"] > 30,
          "roster must allow for downtime")

print("\n=== the measured constant matches the data file ===")
av = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/availability_per_truck.csv")
tr = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/trip_features.csv")
haul = set(tr.truck_id.astype(str).str.strip().str.upper())
h = av[av.equipment_id.isin(haul)]
measured = h.availability.mean()
check("MEASURED_MECHANICAL_AVAILABILITY within 0.01 of the extract",
      abs(measured - ps.MEASURED_MECHANICAL_AVAILABILITY) < 0.01,
      "file says %.3f, constant says %.3f"
      % (measured, ps.MEASURED_MECHANICAL_AVAILABILITY))

print("\n=== bimodality is real, so the mean must not be sold as typical ===")
at_one = float((h.availability >= 0.999).mean())
at_zero = float((h.availability <= 0.001).mean())
check("majority of shifts sit at exactly 1.0", at_one > 0.5, "%.3f" % at_one)
check("a substantial share sit at exactly 0.0", at_zero > 0.1, "%.3f" % at_zero)
check("the two spikes hold most of the mass", at_one + at_zero > 0.9,
      "%.3f" % (at_one + at_zero))
# Records are complete, so bimodality is the operation and not missing data.
check("records are complete (median >= 11.5 h)", h.total_hours.median() >= 11.5,
      "%.1f" % h.total_hours.median())

print("\n=== the two independent measurements still reconcile ===")
lk = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/route_lookup.csv")
lk = lk[lk.effective_cycle_min.notna() & (lk.shifts >= 100)]
wb = float((lk.median_cycle_min / lk.effective_cycle_min).median())
working = measured * h.utilisation.mean()
# The weighbridge cannot see the empty return leg, so it observes about half the
# working time. Doubling should land near availability x utilisation.
check("2 x weighbridge share agrees with availability x utilisation (<0.10)",
      abs(2 * wb - working) < 0.10,
      "2 x %.3f = %.3f vs %.3f" % (wb, 2 * wb, working))

print()
if fails:
    print("FAILED: " + "; ".join(fails))
    sys.exit(1)
print("all availability gates pass")
