"""test_trips_per_shift.py — does the simulator predict the trips that happened?

THE GATE THIS ENFORCES
A production simulator's core claim is trips per truck per shift; tonnage is that
number times payload. So the single most important validation is whether the
predicted trip count reproduces the observed one on routes with real history.

It exists because the first implementation failed it badly and nothing caught it:
trips were computed as (shift x 0.85) / weigh-to-weigh cycle, which predicted
9.57 trips per truck-shift where the weighbridge recorded 1.89 — a 5x
overprediction, and therefore 5x on every tonnage the tool reported. The
arithmetic was internally consistent, so it looked plausible; only comparing it
against observed trips exposed it.

Tolerance is set on the mean rather than per-shift, because a per-shift median
cannot be hit: trips per truck-shift is a small integer and the model predicts a
continuous rate. The mean is the quantity that must be unbiased for tonnage over
a fleet to be right.
"""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import pandas as pd

import plan_simulator as ps

SHIFT = 720.0
# The predicted fleet-mean trips per truck-shift must be within this fraction of
# observed. 15% on trips means 15% on tonnage, which is a defensible planning
# error; the old code was out by 400%.
TOL_FRAC = 0.15
MIN_SHIFTS = 100

fails = []


def check(name, cond, detail=""):
    print("   %-56s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


d = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/trip_features.csv")
obs = (d.groupby(["truck_id", "date", "shift", "route"], observed=True)
        .size().rename("trips").reset_index())
per_route = (obs.groupby("route", observed=True)
               .agg(truck_shifts=("trips", "size"), trips=("trips", "sum"))
               .reset_index())
per_route["obs_trips_per_shift"] = per_route.trips / per_route.truck_shifts
per_route = per_route[per_route.truck_shifts >= MIN_SHIFTS]
print("routes with >=%d truck-shifts: %d" % (MIN_SHIFTS, len(per_route)))

print("\n=== 1. does the simulator reproduce observed trips per truck-shift? ===")
print("%-24s %10s %10s %8s" % ("route", "predicted", "observed", "err %"))
print("-" * 56)
rows = []
for r in per_route.sort_values("truck_shifts", ascending=False).head(14).itertuples():
    src, _, dst = r.route.partition(">")
    res = ps.simulate({"plans": [{"route": r.route, "source": src,
                                  "destination": dst, "n_trucks": 10}]})
    x = res["results"][0]
    if "error" in x:
        continue
    pred = x["trips_per_shift_per_truck"]
    err = 100 * (pred - r.obs_trips_per_shift) / r.obs_trips_per_shift
    rows.append((r.route, pred, r.obs_trips_per_shift, err))
    print("%-24s %10.2f %10.2f %+8.1f" % (r.route, pred,
                                          r.obs_trips_per_shift, err))

if rows:
    pm = sum(x[1] for x in rows) / len(rows)
    om = sum(x[2] for x in rows) / len(rows)
    print("\nmean predicted %.3f vs mean observed %.3f (%+.1f%%)"
          % (pm, om, 100 * (pm - om) / om))
    check("fleet-mean trips within %.0f%% of observed" % (100 * TOL_FRAC),
          abs(pm - om) / om <= TOL_FRAC, "%.3f vs %.3f" % (pm, om))
    worst = max(abs(x[3]) for x in rows)
    check("no route off by more than 50%%", worst <= 50.0, "worst %.1f%%" % worst)

print("\n=== 2. the specific regression: the old formula must NOT return ===")
res = ps.simulate({"plans": [{"route": "POS 12>FENI KM0", "source": "POS 12",
                              "destination": "FENI KM0", "n_trucks": 30}]})
x = res["results"][0]
wb = x["predicted_cycle_time_min"]
eff = x["effective_cycle_min"]
print("   weigh-to-weigh cycle %.1f min | effective cycle %.1f min" % (wb, eff))
print("   trips/truck/shift %.2f | planned %.0f t"
      % (x["trips_per_shift_per_truck"], x["planned_production_t"]))
check("effective cycle exceeds weigh-to-weigh", eff > wb, "%.1f vs %.1f" % (eff, wb))
check("trips are NOT shift/weigh-to-weigh",
      abs(x["trips_per_shift_per_truck"] - (SHIFT * 0.85) / wb) > 1.0,
      "looks like the old formula")
check("availability factor is not double-counted",
      res["summary"]["availability_factor_applied"] == 1.0,
      res["summary"]["availability_factor_applied"])

print("\n=== 3. both cycle figures are reported and explained ===")
check("effective_cycle_min present", "effective_cycle_min" in x)
check("basis explains the two cycles", "effective_cycle" in x["basis"])
check("limits explain the distinction",
      "cycle_time_vs_trip_count" in res["model_limits"])
check("availability note explains why 1.0",
      "already contains" in res["summary"]["availability_note"]
      and "effective cycle" in res["summary"]["availability_note"],
      res["summary"]["availability_note"][:90])

print("\n=== 4. invariants still hold after the change ===")
prev = 0
for n in (5, 20, 80):
    y = ps.simulate({"plans": [{"route": "POS 12>FENI KM0", "source": "POS 12",
                                "destination": "FENI KM0", "n_trucks": n}]})["results"][0]
    check("planned tonnage rises at n=%d" % n,
          y["planned_production_t"] >= prev, y["planned_production_t"])
    prev = y["planned_production_t"]
dry = ps.simulate({"plans": [{"route": "POS 12>FENI KM0", "source": "POS 12",
                              "destination": "FENI KM0", "n_trucks": 20}],
                   "weather": "dry"})["results"][0]
wet = ps.simulate({"plans": [{"route": "POS 12>FENI KM0", "source": "POS 12",
                              "destination": "FENI KM0", "n_trucks": 20}],
                   "weather": "wet"})["results"][0]
# Rain raises reported cycle time (measured dwell penalty) but must NOT change
# tonnage: within route and month it moves production a median +0.1%.
check("wet tonnage equals dry (no unsupported penalty)",
      abs(wet["planned_production_t"] - dry["planned_production_t"]) < 1,
      "%s vs %s" % (wet["planned_production_t"], dry["planned_production_t"]))
check("wet reported cycle time >= dry",
      wet["predicted_cycle_time_min"] >= dry["predicted_cycle_time_min"])

print("\n%s  (%d failures)"
      % ("ALL PASS" if not fails else "FAILURES: " + ", ".join(fails), len(fails)))
sys.exit(1 if fails else 0)
