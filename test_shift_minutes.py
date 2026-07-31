"""Gate J60: shift_minutes scales trips, and says when it is extrapolating.

AUDITED AS THE LAST CALLER-SUPPLIED FIELD THAT SCALES TONNAGE, after
`availability` (which the UI overrode, costing 15% of quoted tonnage) and
`weather` (whose real defect was a residual absorbing a one-ended penalty).

**There is no UI/engine disagreement here.** The UI sends 720, DEFAULT_SHIFT_MIN
is 720, and both agree. That half is asserted below so it stays true.

**There is a real extrapolation.** Trips scale exactly linearly with this field,
but the denominator they divide does not scale at all:

    effective_cycle_min = (truck_shifts x 720) / trips      <- 720 hardcoded

so the effective cycle is "minutes of a TWELVE-HOUR shift per completed trip".
It bundles per-trip time with per-shift overhead that does not scale -- one meal
break, one refuel, one pre-start, one handover. The model therefore over-states
trips for a short shift and under-states them for a long one.

The size of that error is NOT knowable from this data, and that is measured, not
assumed: 98.48% of 538,586 truck-shifts are exactly 12.0 hours, so shift length
is a constant and no regression can separate fixed overhead from per-trip time.
Inventing a fixed component would be inventing the number.

So this gate does not demand a corrected figure. It demands that the answer be
LABELLED when it leaves the calibration point, and that the label be silent at
720 -- a warning that always fires is one nobody reads.
"""
import os
import re
import sys

import plan_simulator as ps

FAILED = []
ROOT = os.path.dirname(os.path.abspath(__file__))
PLAN = [{"route": "BLB>FENI KM0", "source": "BLB",
         "destination": "FENI KM0", "n_trucks": 30}]


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def sim(**kw):
    return ps.simulate(dict({"plans": PLAN}, **kw))


print("=== the calibration point is 720 and nothing silently disagrees ===")

check("DEFAULT_SHIFT_MIN is 720", ps.DEFAULT_SHIFT_MIN == 720, ps.DEFAULT_SHIFT_MIN)
check("CALIBRATION_SHIFT_MIN is 720", ps.CALIBRATION_SHIFT_MIN == 720.0,
      ps.CALIBRATION_SHIFT_MIN)

# The lookup's own basis string must still say 720. If someone re-derives the
# effective cycle at a different shift length, the constant above goes stale and
# every extrapolation warning silently points at the wrong number.
rt = ps._routes()
if rt is not None and "effective_cycle_basis" in rt.columns:
    basis = str(rt["effective_cycle_basis"].dropna().iloc[0])
    check("effective_cycle_basis still states a 720-min shift", "720" in basis, basis)

base = sim()
check("default payload applies 720", base["summary"]["shift_minutes"] == 720.0,
      base["summary"]["shift_minutes"])
check("no extrapolation warning at the default",
      base["summary"].get("shift_minutes_extrapolated") is None)
check("explicit 720 also silent",
      sim(shift_minutes=720)["summary"].get("shift_minutes_extrapolated") is None)

print("\n=== trips scale linearly, which is the documented behaviour ===")

b = base["results"][0]["trips_per_shift_per_truck"]
for m in (360, 600, 840, 1440):
    r = sim(shift_minutes=m)["results"][0]
    expect = round(b * m / 720, 2)
    check("shift=%d scales trips linearly" % m,
          abs(r["trips_per_shift_per_truck"] - expect) <= 0.02,
          "%s vs %s" % (r["trips_per_shift_per_truck"], expect))
    # The denominator must NOT move: it is a measured per-route constant, and if
    # a shift length ever started changing it we would be double-counting.
    check("shift=%d leaves the effective cycle untouched" % m,
          r["effective_cycle_min"] == base["results"][0]["effective_cycle_min"],
          "%s vs %s" % (r["effective_cycle_min"], base["results"][0]["effective_cycle_min"]))

print("\n=== and every departure from 720 is labelled, with its direction ===")

for m in (60, 360, 600):
    n = sim(shift_minutes=m)["summary"].get("shift_minutes_extrapolated") or ""
    check("shift=%d is flagged as extrapolation" % m, "EXTRAPOLATION" in n, n[:70])
    check("shift=%d warns it OVER-states" % m, "OVER-states" in n, n[:110])

for m in (840, 1440):
    n = sim(shift_minutes=m)["summary"].get("shift_minutes_extrapolated") or ""
    check("shift=%d is flagged as extrapolation" % m, "EXTRAPOLATION" in n, n[:70])
    check("shift=%d warns it UNDER-states" % m, "UNDER-states" in n, n[:110])

# A 1-minute rounding difference is not worth a warning; 60 minutes is.
check("721 does not trip the warning (tolerance)",
      sim(shift_minutes=721)["summary"].get("shift_minutes_extrapolated") is None)
check("780 does trip the warning",
      sim(shift_minutes=780)["summary"].get("shift_minutes_extrapolated") is not None)

print("\n=== the front end must not disagree with the engine ===")

html = open(os.path.join(ROOT, "templates/simulator.html")).read()
m = re.search(r'id="ps-shift"[^>]*value="(\d+)"', html)
check("the UI's shift input defaults to the calibration point",
      m is not None and float(m.group(1)) == ps.CALIBRATION_SHIFT_MIN,
      m.group(1) if m else "no ps-shift input found")

js = open(os.path.join(ROOT, "static/js/plan_simulator.js")).read()
check("the UI surfaces the extrapolation warning",
      "shift_minutes_extrapolated" in js)

print("\n=== exactly ONE editable shift control in the whole app ===")

# There were THREE. #ps-shift drove the engine, #plan-hours drove plan.js's
# local estimate on another tab, and #flow-hours sat disabled and unread in a
# collapsed panel on a third. Two controls for one concept is how the 0.85
# availability override survived, so this counts them rather than trusting that
# nobody adds a fourth.
inputs = re.findall(r"<input\b[^>]*>", html)
shifty = [t for t in inputs
          if re.search(r'id="(ps-shift|plan-hours|flow-hours|[a-z-]*shift[a-z-]*|[a-z-]*hours[a-z-]*)"', t)]
editable = [t for t in shifty
            if 'type="hidden"' not in t and "disabled" not in t]
ids = [re.search(r'id="([^"]+)"', t).group(1) for t in editable]
check("exactly one editable shift/hours input", len(editable) == 1, ids)
check("and it is ps-shift (the one that reaches the engine)",
      ids == ["ps-shift"], ids)
check("#plan-hours survives as a HIDDEN field so plan.js keeps working",
      'id="plan-hours"' in html and 'id="plan-hours" type="hidden"' in html)
check("the inert #flow-hours display is gone", 'id="flow-hours"' not in html)
check("plan-hours is driven from ps-shift, so they cannot diverge",
      "psSyncShift" in js and "plan-hours" in js)

print("\n=== the input range matches what the data supports ===")

lo = re.search(r'id="ps-shift"[^>]*\bmin="(\d+)"', html)
hi = re.search(r'id="ps-shift"[^>]*\bmax="(\d+)"', html)
check("min is 480 (8.0 h, the shortest shift observed)",
      lo is not None and int(lo.group(1)) == 480, lo.group(1) if lo else None)
check("max is 720 (12.0 h, 98.5% of shifts and the calibration point)",
      hi is not None and int(hi.group(1)) == 720, hi.group(1) if hi else None)
# The old range let a planner ask for 1440 -- a 2x extrapolation -- with nothing
# but the warning to stop them.
check("the old 1440 ceiling is gone",
      not re.search(r'id="ps-shift"[^>]*max="1440"', html))
check("the evidence is on screen, not only in the docs",
      "538,586" in html or "538586" in html)

print()
if FAILED:
    print("J60 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("shift_minutes gate passes")
