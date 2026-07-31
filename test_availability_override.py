"""Gate J55: a caller-supplied availability can never scale tonnage.

WHY THIS EXISTS, AND WHY J52 DID NOT COVER IT.

J52 already asserts that availability does not scale tonnage -- and it passed
for the whole time the shipped UI was under-quoting production by 15%. It builds
its own payload:

    ps.simulate({"plans": [...]})

with no `availability` key, so it only ever exercised the default path, where
DEFAULT_AVAILABILITY is 1.0 and everything is correct. The real caller,
static/js/plan_simulator.js, sent `availability: 0.85` on every request, and
plan_simulator.py honoured it:

    avail = float(payload.get("availability", DEFAULT_AVAILABILITY))

Measured on BLB>FENI KM0 with 30 trucks: 3,042 t via the API, 2,586 t through
the UI. That is the exact 0.85 assumption this project measured as wrong -- bias
moves from +5.5% with no factor to -10.3% at x0.85.

So this gate tests the OTHER path: what happens when a caller does supply the
key. It also asserts the front end does not send it, because the defect needed
both halves and fixing only one leaves the trap armed for the next caller.

A gate that constructs its own input cannot catch a bug in what the real caller
sends. That is the general lesson and it is why this file checks the JS too.
"""
import json
import os
import re
import sys

import plan_simulator as ps

ROOT = os.path.dirname(os.path.abspath(__file__))
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


PLAN = {"plans": [{"route": "BLB>FENI KM0", "source": "BLB",
                   "destination": "FENI KM0", "n_trucks": 30}]}


def run(extra=None):
    p = json.loads(json.dumps(PLAN))
    if extra:
        p.update(extra)
    return ps.simulate(p)


print("=== a supplied availability must not move tonnage ===")

base = run()
base_t = base["results"][0]["planned_production_t"]
base_trips = base["results"][0]["trips_per_shift_per_truck"]
check("baseline applies no factor",
      base["summary"]["availability_factor_applied"] == 1.0,
      base["summary"]["availability_factor_applied"])
check("baseline reports no ignored-override note",
      base["summary"].get("availability_override_ignored") is None)

# The old UI default, and two more, including one far enough from 1.0 that any
# residual scaling would be unmistakable.
for factor in (0.85, 0.45, 0.10):
    r = run({"availability": factor})
    s, res = r["summary"], r["results"][0]
    check("availability=%.2f leaves tonnage unchanged" % factor,
          res["planned_production_t"] == base_t,
          "%s vs baseline %s" % (res["planned_production_t"], base_t))
    check("availability=%.2f leaves trips/truck unchanged" % factor,
          res["trips_per_shift_per_truck"] == base_trips,
          "%s vs baseline %s" % (res["trips_per_shift_per_truck"], base_trips))
    check("availability=%.2f still reports factor 1.0" % factor,
          s["availability_factor_applied"] == 1.0,
          s["availability_factor_applied"])
    note = s.get("availability_override_ignored")
    check("availability=%.2f is reported as ignored" % factor,
          isinstance(note, str) and "IGNORED" in note, note)

# A no-op override must not raise a false alarm, or the warning becomes noise
# and gets ignored the one time it matters.
r = run({"availability": 1.0})
check("availability=1.0 raises no warning",
      r["summary"].get("availability_override_ignored") is None,
      r["summary"].get("availability_override_ignored"))

# Garbage must not 500: a planner-facing endpoint that crashes on a bad field is
# worse than one that ignores it.
for junk in ("abc", None, [], {"a": 1}):
    try:
        r = run({"availability": junk})
        ok = r["results"][0]["planned_production_t"] == base_t
    except Exception as exc:                                  # noqa: BLE001
        ok = False
        r = str(exc)
    check("availability=%r does not break the run" % (junk,), ok)

print("\n=== the front end must not send the key at all ===")

js = open(os.path.join(ROOT, "static/js/plan_simulator.js")).read()
# Match an availability key in an object literal being sent, not the word in a
# comment -- the file legitimately discusses availability at length.
sends = re.search(r"^\s*availability\s*:", js, re.M)
check("plan_simulator.js does not send an availability field", sends is None,
      sends.group(0).strip() if sends else "")

html = open(os.path.join(ROOT, "templates/simulator.html")).read()
check("simulator.html has no ps-avail input", 'id="ps-avail"' not in html)
check("simulator.html does not default an availability control to 0.85",
      not re.search(r'id="ps-avail"[^>]*value="0\.85"', html))

print()
if FAILED:
    print("J55 FAILED: %d check(s): %s" % (len(FAILED), "; ".join(FAILED)))
    sys.exit(1)
print("availability override gate passes")
