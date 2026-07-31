"""Gate J57: the weather input moves what rain is measured to move, and nothing else.

WHAT WENT WRONG, AND WHAT DID NOT.

The suspicion this gate was written to check was that a wet cycle uplift feeds
through to fewer trips and therefore fewer tonnes, double-counting rain against
`availability_analysis.md`, which records that rain must not carry a tonnage
penalty. **That suspicion was wrong.** Rain is deliberately excluded from the
effective cycle, and the effective cycle is the only denominator for trips, so
tonnage was already weather-invariant on every route. Measured, not assumed --
this gate keeps it that way.

A DIFFERENT defect was real. `implied_travel_time_min` is a residual:

    travel = cycle - load - dump

The cycle uplift added only the LOADING point's wet penalty, while
`predicted_dump_time_min` also carried the DUMPING point's. So the dump penalty
was subtracted from travel and never added back, and the model reported trucks
travelling FASTER in the rain on 11 of 14 routes -- typically -1.1 min, and
-7.8 min on KR>POS 10. The signature was exact: dTravel == -dDump everywhere.

So this gate asserts three things that must hold together, because any two of
them can be satisfied by a broken build:

  1. tonnage, trips and the effective cycle do NOT move with weather
  2. implied travel does NOT move with weather (the residual must not absorb a
     dwell penalty applied at one end only)
  3. weather DOES still move dwell and cycle where a wet figure is measured

Check 3 matters most. Without it, deleting the weather feature entirely would
pass checks 1 and 2 perfectly -- an invariance gate alone rewards doing nothing.
"""
import os
import sys

import plan_simulator as ps

ROOT = os.path.dirname(os.path.abspath(__file__))
FAILED = []
# Every minute figure is rounded to 0.1 before it reaches the caller, so equality
# is only meaningful to that precision.
#
# TOL       single value moved / did not move: one rounding, +-0.05.
# TOL_SUM   cycle-uplift == load-uplift + dump-uplift compares THREE independently
#           rounded values, so the worst-case drift is 3 x 0.05 = 0.15 with no
#           defect present at all. Observed on real data: HSM>FENI KM0 reports
#           cycle +13.40 vs dwell +13.30.
#
# This still discriminates hard. The defect it guards -- the dumping penalty
# missing from the cycle entirely -- shows up as 1.1 to 7.9 min, one to two
# orders of magnitude above the tolerance.
TOL = 0.051
TOL_SUM = 0.16


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def sim(route, src, dst, weather, n=30):
    return ps.simulate({"plans": [{"route": route, "source": src,
                                   "destination": dst, "n_trucks": n}],
                        "weather": weather})


# Read the serving table directly rather than through the API, so this gate runs
# without a listening server. `_routes()` is the same lookup /api/simulate uses.
_rt = ps._routes()
if _rt is None or _rt.empty:
    print("no route history available (data/route_lookup.csv) -- cannot run J57")
    sys.exit(1)
routes = [{"route": r["route"], "source": r["source"], "destination": r["destination"]}
          for _, r in _rt.head(14).iterrows()]

print("=== rain must not move tonnage, trips, or the effective cycle ===")

moved_dwell = 0
pairs = []
for r in routes:
    a = sim(r["route"], r["source"], r["destination"], "dry")["results"][0]
    b = sim(r["route"], r["source"], r["destination"], "wet")["results"][0]
    if a.get("error") or b.get("error"):
        continue
    pairs.append((r["route"], a, b))

check("at least 8 routes resolved for comparison", len(pairs) >= 8, len(pairs))

g = lambda x, k: (x.get(k) or 0)

for route, a, b in pairs:
    for field in ("planned_production_t", "achievable_production_t",
                  "trips_per_shift_per_truck", "total_trips", "effective_cycle_min"):
        check("%s: %s is weather-invariant" % (route, field),
              abs(g(b, field) - g(a, field)) < 1e-9,
              "dry=%s wet=%s" % (g(a, field), g(b, field)))

print("\n=== the residual must not absorb a one-ended dwell penalty ===")

for route, a, b in pairs:
    d_travel = g(b, "implied_travel_time_min") - g(a, "implied_travel_time_min")
    check("%s: implied travel is weather-invariant" % route,
          abs(d_travel) < TOL,
          "moved %+.2f min (dDump %+.2f) -- rain must not change road speed here"
          % (d_travel, g(b, "predicted_dump_time_min") - g(a, "predicted_dump_time_min")))

    # The cycle uplift must equal what was actually added to BOTH dwells.
    d_cycle = g(b, "predicted_cycle_time_min") - g(a, "predicted_cycle_time_min")
    d_dwell = ((g(b, "predicted_load_time_min") - g(a, "predicted_load_time_min"))
               + (g(b, "predicted_dump_time_min") - g(a, "predicted_dump_time_min")))
    check("%s: cycle uplift == load + dump uplift" % route,
          abs(d_cycle - d_dwell) < TOL_SUM,
          "cycle %+.2f vs dwell %+.2f (gap %.2f > %.2f rounding budget)"
          % (d_cycle, d_dwell, abs(d_cycle - d_dwell), TOL_SUM))

print("\n=== but weather must still DO something where it is measured ===")

for route, a, b in pairs:
    if abs(g(b, "predicted_load_time_min") - g(a, "predicted_load_time_min")) > TOL \
       or abs(g(b, "predicted_dump_time_min") - g(a, "predicted_dump_time_min")) > TOL:
        moved_dwell += 1

# Without this, removing the weather feature altogether would pass every check
# above. An invariance-only gate rewards deleting the thing it guards.
check("weather still moves dwell on most routes (not a no-op)",
      moved_dwell >= max(4, len(pairs) // 2),
      "%d of %d routes" % (moved_dwell, len(pairs)))

s = sim(routes[0]["route"], routes[0]["source"], routes[0]["destination"], "wet")["summary"]
check("summary reports the weather it was given", s.get("weather") == "wet", s.get("weather"))
note = (s.get("weather_note") or "").lower()
check("weather_note states tonnage is not affected",
      "not change predicted tonnage" in note or "not predicted tonnage" in note,
      note[:100])
check("weather_note states travel is weather-invariant",
      "invariant" in note, note[:100])

print()
if FAILED:
    print("J57 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("weather path gate passes")
