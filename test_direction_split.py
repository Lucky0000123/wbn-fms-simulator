"""Gate J61: segment speeds are split by direction, and the split means what it says.

FMS_CONGESTION_SEG has always carried a DIR column in {'down','up'}. The
congestion endpoint aggregated over it, so loaded and empty speeds were averaged
into one number and the assessment view had to disclaim the split it could not
draw.

THE MAPPING IS THE PART THAT NEEDED PROVING, not the plumbing. "down" is a
CHAINAGE direction, not a load state, and reading it as "loaded" is an inference.
It was verified against the weighbridge tickets: every tip on the corridor sits
seaward of every load point, so 100.0% of loaded corridor hauls run
down-chainage -- 298,340 trips, zero counter-examples. The speeds agree
independently: loaded is slower on 75 of 94 segments, median +11.5% for empty.

So this gate asserts three things:

  1. the payload actually carries the split, in BOTH live and fixture shapes
  2. the split is not degenerate -- loaded and empty must differ on most
     segments, or something is aggregating them again upstream and returning
     the same number twice
  3. the physical direction survives: empty must be faster on a clear majority.
     If a future change flipped the down/up mapping, every other check here
     would still pass while the chart said loaded trucks are faster uphill.

Check 3 is the one that catches a silent inversion, which is the failure mode
that would look completely normal on screen.
"""
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def audit(segments, label):
    print("\n=== %s ===" % label)
    check("%s: segments present" % label, len(segments) > 20, len(segments))
    need = {"loadedSpeed", "emptySpeed", "nLoaded", "nEmpty"}
    missing = [k for k in need if k not in (segments[0] if segments else {})]
    check("%s: direction fields present" % label, not missing, missing)
    if missing:
        return

    both = [s for s in segments
            if s.get("loadedSpeed") and s.get("emptySpeed")]
    check("%s: most segments have BOTH directions" % label,
          len(both) >= 0.8 * len(segments),
          "%d of %d" % (len(both), len(segments)))

    # A split that returns the same number twice is not a split. Guards against
    # an upstream change that re-pools the directions while keeping the keys.
    differing = [s for s in both if abs(s["loadedSpeed"] - s["emptySpeed"]) > 0.05]
    check("%s: the two directions actually differ" % label,
          len(differing) >= 0.8 * len(both),
          "%d of %d differ" % (len(differing), len(both)))

    # Physical sanity, and the check that catches a flipped mapping.
    faster = [s for s in both if s["emptySpeed"] > s["loadedSpeed"]]
    share = len(faster) / len(both) if both else 0
    gaps = [100 * (s["emptySpeed"] - s["loadedSpeed"]) / s["loadedSpeed"] for s in both]
    med = statistics.median(gaps) if gaps else 0
    check("%s: empty is faster on a clear majority of segments" % label,
          share >= 0.6, "%.0f%% (%d of %d)" % (100 * share, len(faster), len(both)))
    check("%s: median empty-vs-loaded gap is positive" % label, med > 0,
          "%+.1f%%" % med)
    print("     empty faster on %.0f%% of %d segments, median gap %+.1f%%"
          % (100 * share, len(both), med))

    # Fix counts must be real, or the speeds are averages of nothing.
    thin = [s for s in both if (s.get("nLoaded") or 0) < 10 or (s.get("nEmpty") or 0) < 10]
    check("%s: fix counts are populated" % label,
          len(thin) <= 0.2 * len(both), "%d of %d thin" % (len(thin), len(both)))


# ---- the fixture, which is what the demo and every no-DB run serves ----------
fx = json.load(open(os.path.join(ROOT, "fixtures/congestion-model.json")))
audit(fx.get("segments") or [], "fixture")

# ---- the live endpoint shape, via the app (falls back to the fixture with no
#      DB, which still exercises the serialisation path) -----------------------
import serve                                                        # noqa: E402
client = serve.app.test_client()
r = client.get("/api/simulator/congestion-model")
check("endpoint returns 200", r.status_code == 200, r.status_code)
audit((r.get_json() or {}).get("segments") or [], "endpoint")

# ---- the UI must actually draw the split ------------------------------------
print("\n=== the view uses it ===")
js = open(os.path.join(ROOT, "static/js/plan_assessment.js")).read()
check("assessment view reads loadedSpeed", "loadedSpeed" in js)
check("assessment view reads emptySpeed", "emptySpeed" in js)
check("assessment view no longer claims the split is unavailable",
      "not loaded vs empty" not in js.lower())

print()
if FAILED:
    print("J61 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("direction split gate passes")
