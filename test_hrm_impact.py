"""Gate J62: the HRM analysis controls the confound that nearly fooled it.

This gate protects the METHOD, not the answer. The answer today is "no
measurable impact" and might legitimately change if the HRM window widens; the
method must not.

WHAT NEARLY WENT WRONG. The first pass reported

    HRM hours vs trips/DT, controlling fleet size:  r = -0.4604, p = 8.4e-22

which is significant at twenty-two zeros and has an obvious causal story. It was
entirely route length. `hrm_hours` is SUMMED over the sections a route spans, so
a long route accumulates more of it by being long, and a long route also
completes fewer trips per truck by being long:

    corr(span_km, hrm_hours)    = +0.63
    corr(span_km, trips_per_dt) = -0.63

Two 0.63 correlations through a shared cause manufacture about -0.40 between the
outcomes. Controlling fleet size did nothing, because fleet size was not the
confound -- the road was. Demeaning within route removes it and the effect goes
to r = +-0.0006.

So the assertions are:

  1. the confound is MEASURED and recorded, not merely mentioned in prose
  2. the within-route test exists and matches a recomputation from the panel
  3. the verdict is decided WITHOUT the confounded statistic
  4. the confounded statistic is retained but explicitly labelled spurious --
     deleting it would lose the reason the method is what it is

Skips cleanly when the cached panel is absent (data/ is gitignored), like the
other extract-dependent gates.
"""
import json
import os
import sys

FAILED = []
ROOT = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(ROOT, "reports", "hrm_impact.json")
PANEL = os.path.join(ROOT, "data", "hrm_panel.csv")


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


if not os.path.exists(JSON_PATH):
    print("reports/hrm_impact.json absent -- run scripts/hrm_impact.py. Skipping.")
    sys.exit(0)

res = json.load(open(JSON_PATH))

print("=== the confound must be measured, not just described ===")
conf = res.get("route_length_confound") or {}
check("route-length confound is recorded", bool(conf), list(conf))
hrs = (conf.get("span_km~hrm_hours") or {}).get("r")
tpd = (conf.get("span_km~trips_per_dt") or {}).get("r")
check("span_km vs hrm_hours recorded", hrs is not None, hrs)
check("span_km vs trips_per_dt recorded", tpd is not None, tpd)
if hrs is not None and tpd is not None:
    # The confound must actually be large, or the whole story is wrong and the
    # within-route control is solving a problem that does not exist.
    check("the confound is substantial (|r| > 0.3 on both legs)",
          abs(hrs) > 0.3 and abs(tpd) > 0.3, "hours %.3f, trips %.3f" % (hrs, tpd))
    check("the two legs have OPPOSITE signs (that is what manufactures it)",
          hrs * tpd < 0, "%.3f x %.3f" % (hrs, tpd))

print("\n=== the within-route test must exist and be reproducible ===")
wr = res.get("within_route_controlling_trucks") or {}
check("within-route test present for hrm_units", "hrm_units" in wr, list(wr))
check("within-route test present for hrm_hours", "hrm_hours" in wr, list(wr))

if os.path.exists(PANEL):
    import numpy as np
    import pandas as pd
    from scipy import stats
    p = pd.read_csv(PANEL)
    for col in ("hrm_units", "hrm_hours"):
        d = p.copy()
        dm = lambda s: s - s.groupby(d.route).transform("mean")      # noqa: E731
        x, y, z = dm(d[col]).values, dm(d.trips_per_dt).values, dm(d.trucks).values
        rx = x - np.polyval(np.polyfit(z, x, 1), z)
        ry = y - np.polyval(np.polyfit(z, y, 1), z)
        r, _ = stats.pearsonr(rx, ry)
        rec = (wr.get(col) or {}).get("r")
        check("recomputed within-route r matches the report (%s)" % col,
              rec is not None and abs(r - rec) < 0.005,
              "recomputed %.4f vs recorded %s" % (r, rec))
else:
    print("  INFO data/hrm_panel.csv absent (gitignored) -- recomputation skipped")

print("\n=== the verdict must not rest on the confounded statistic ===")
key = "partial_hours_ROUTE_CONFOUNDED"
check("the confounded statistic is retained for the record", key in res, list(res))
check("it is explicitly labelled spurious",
      "SPURIOUS" in ((res.get(key) or {}).get("warning") or "").upper(),
      (res.get(key) or {}).get("warning"))
check("the verdict counts 4 controlled tests, not 5",
      res.get("tests_considered") == 4, res.get("tests_considered"))
check("a note records why it was excluded",
      "route length" in (res.get("note") or "").lower(), res.get("note"))

# If the confounded test were counted, the verdict could not be a null while
# that statistic sits at p ~ 1e-21. This ties the two together.
conf_p = (res.get(key) or {}).get("p")
if conf_p is not None and conf_p < 0.05:
    check("verdict is still a null despite the significant spurious result",
          res.get("significant_tests") == 0 and "NO MEASURABLE" in (res.get("verdict") or ""),
          "%s / significant=%s" % (res.get("verdict"), res.get("significant_tests")))

print("\n=== the report must exist and state the retraction ===")
md = os.path.join(ROOT, "reports", "hrm_impact_analysis.md")
check("reports/hrm_impact_analysis.md exists", os.path.exists(md))
if os.path.exists(md):
    t = open(md).read().lower()
    check("the report explains the spurious result", "artifact of route length" in t)
    check("the report states the null", "no measurable impact" in t)
    check("the report states its power limit", "power" in t)

print()
if FAILED:
    print("J62 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("HRM impact gate passes")
