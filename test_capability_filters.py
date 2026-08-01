"""Gate J64: the capability endpoint is real, filtered, and fast.

WHAT WAS WRONG. /api/simulator/capability was answered in serve.py with

    return jsonify(_canonical_capability(fx("capability")))

-- the committed fixture, every time, database or not, with request.args never
read. The UI sent it six filter parameters (from, to, types, inclIwip, source,
dest) and all six were discarded. Every KPI card, the routes and destinations
tables, the 3D scatter and the truck list on the Capability & Scenario tab were
frozen at whatever was captured on 2026-07-22, and the summary line showed the
FIXTURE's date range -- which is why moving the date pickers appeared to do
nothing at all. The numbers and the dates both came from the file.

It now queries DISPATCH RESULTS LITE 2 and honours all six.

WHY THERE IS A SPEED ASSERTION HERE. That view is expensive: a bare COUNT(*)
takes 15 s over the site link and no WHERE clause helps, because the view is
materialised from its base tables before any predicate applies. The first
working version therefore took 22 s per filter change and the page sat on
"Loading..." -- correct, and unusable. The fix is a whole-view snapshot filtered
in Python. If someone later "optimises" that back into a per-request query, the
correctness checks below would all still pass while the tab became unusable
again, so response time is asserted as a first-class property.

Runs against a live server. Skips cleanly in no-DB mode, where the fixture
fallback is the correct answer and there is nothing to filter.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5055"
FAILED = []
ROOT = os.path.dirname(os.path.abspath(__file__))


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def cap(**params):
    url = BASE + "/api/simulator/capability?" + urllib.parse.urlencode(params)
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=120) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


try:
    with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:                                           # noqa: BLE001
    print("no server on 5055 (%s) -- skipping" % str(exc)[:60])
    sys.exit(0)

if mode != "database":
    # Fixture mode is a supported answer, not a filtered one. Assert only that
    # it still serves and is canonicalised, then stop.
    d, _ = cap(**{"from": "2026-04-01", "to": "2026-07-31"})
    print("=== no-DB mode: fixture fallback ===")
    check("still returns ok", d.get("ok") is True)
    check("tagged as a fixture", d.get("servedFrom") == "fixture", d.get("servedFrom"))
    names = {r.get("dest") for r in (d.get("routes") or [])}
    stale = names & {"FENI A", "FENI W", "FENI U2", "HUAFEI.C01", "CUU_KM_10"}
    # The rewrite used to live in serve.py, which no longer answers this route.
    # If it were not reproduced on the fallback path, no-DB mode would offer the
    # operator route names the model has never seen.
    check("fixture names are canonicalised on the fallback path", not stale, stale)
    print("\nJ64 skipped the filter checks (no database)" if not FAILED else "")
    sys.exit(1 if FAILED else 0)

print("=== every filter must move the numbers ===")
WIDE = {"from": "2025-09-01", "to": "2026-07-31"}
base, t_base = cap(**WIDE)
check("baseline returns data", base.get("ok") and (base.get("kpi") or {}).get("days", 0) > 30,
      (base.get("kpi") or {}).get("days"))
check("it is NOT a fixture fallback",
      base.get("servedFrom") != "fixture", base.get("servedFrom"))

narrow, _ = cap(**{"from": "2026-07-01", "to": "2026-07-31"})
check("date range changes the day count",
      narrow["kpi"]["days"] < base["kpi"]["days"],
      "%s vs %s" % (narrow["kpi"]["days"], base["kpi"]["days"]))
check("date range changes tonnage per day",
      narrow["kpi"]["wmtPerDay"] != base["kpi"]["wmtPerDay"])
# The echoed window is what the summary line renders. It used to echo the
# fixture's own dates, which is what made the filter look cosmetic.
check("the response echoes the REQUESTED window, not a stored one",
      narrow.get("from") == "2026-07-01" and narrow.get("to") == "2026-07-31",
      "%s..%s" % (narrow.get("from"), narrow.get("to")))

iwip, _ = cap(**dict(WIDE, inclIwip="1"))
check("including IWIP raises tonnage",
      iwip["kpi"]["wmtPerDay"] > base["kpi"]["wmtPerDay"],
      "%s vs %s" % (iwip["kpi"]["wmtPerDay"], base["kpi"]["wmtPerDay"]))
check("inclIwip is echoed truthfully", iwip.get("inclIwip") is True and base.get("inclIwip") is False,
      "%s / %s" % (iwip.get("inclIwip"), base.get("inclIwip")))

typed, _ = cap(**dict(WIDE, types="DIRECT"))
check("type filter reduces tonnage", typed["kpi"]["wmtPerDay"] < base["kpi"]["wmtPerDay"])
# The dropdown must keep offering the other types, or the operator cannot undo.
check("the Types menu still lists every type in the window",
      len(typed.get("types") or []) > 1, len(typed.get("types") or []))

srcd, _ = cap(**dict(WIDE, source="TF"))
check("source filter reduces the route list",
      0 < len(srcd.get("routes") or []) < len(base.get("routes") or []),
      "%s vs %s" % (len(srcd.get("routes") or []), len(base.get("routes") or [])))
check("source filter keeps only that origin",
      all(r["origin"] == "TF" for r in (srcd.get("paths") or [])),
      sorted({r["origin"] for r in (srcd.get("paths") or [])})[:5])

dstd, _ = cap(**dict(WIDE, dest="FENI KM0"))
check("dest filter keeps only that destination",
      all(r["dest"] == "FENI KM0" for r in (dstd.get("paths") or [])),
      sorted({r["dest"] for r in (dstd.get("paths") or [])})[:5])

print("\n=== the arithmetic must reproduce ===")
p = sorted(base.get("paths") or [], key=lambda r: -r["t"])[0]
check("tf == t/trips", abs(p["tf"] - p["t"] / p["trips"]) < 0.01 if p["trips"] else True)
check("tripsPerDT == trips/dt", abs(p["tripsPerDT"] - p["trips"] / p["dt"]) < 0.01 if p["dt"] else True)
check("effWMT == t/planWmt",
      abs(p["effWMT"] - p["t"] / p["planWmt"]) < 0.01 if p["planWmt"] else True)
k = base["kpi"]
check("wmtPerDay == total/days",
      abs(k["wmtPerDay"] * k["days"] - sum(r["t"] for r in base["paths"])) < 1.0,
      "%s*%s vs %s" % (k["wmtPerDay"], k["days"], sum(r["t"] for r in base["paths"])))

print("\n=== and it must stay fast ===")
# Six DIFFERENT combinations, so a per-request cache cannot fake this.
worst, slow = 0.0, None
for q in ({"from": "2026-01-01", "to": "2026-03-31"},
          {"from": "2026-02-01", "to": "2026-06-30", "inclIwip": "1"},
          {"from": "2025-10-01", "to": "2026-01-31", "types": "HAULAGE"},
          {"from": "2026-03-01", "to": "2026-07-31", "source": "KR"},
          {"from": "2025-12-01", "to": "2026-05-31", "dest": "POS 12"},
          {"from": "2026-05-01", "to": "2026-07-15"}):
    _, dt = cap(**q)
    if dt > worst:
        worst, slow = dt, q
print("     slowest of 6 distinct filter combinations: %.2fs  %s" % (worst, slow))
check("every filter combination answers in under 3s", worst < 3.0, "%.2fs" % worst)

print()
if FAILED:
    print("J64 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("capability filter gate passes")
