"""Gate J65: TARGET TRIP is a rate; planTripsPerDT must be its weighted average.

WHAT WAS WRONG (Tab 1 QC, 2026-07-31). DISPATCH RESULTS LITE 2 column
[TARGET TRIP] is already planned trips per DT (values like 8.0, 4.8, 6.0 that
match RIT/NB_DT on the same row). The first live capability path stored the
raw rate in _ptr and computed

    planTripsPerDT = SUM(TARGET TRIP) / SUM(DT PLAN)

which collapsed to ~0.15. Trip-eff KPIs then read 1700–2600% while WMT-eff
stayed a sane ~90%. The fixture had never shown this because its captured
planTripsPerDT was already the rate (~4.6).

THE FIX. Store planned trip-COUNTS = TARGET_TRIP × DT_PLAN per row, then
planTripsPerDT = SUM(counts) / SUM(DT PLAN) recovers the DT-PLAN-weighted
average rate (~4.4). effTrip then lands near 0.9.

Offline unit checks always run (no VPN). Live checks run when :5055 is in
database mode.

Mutation: make _planned_trip_counts return the raw rate → offline unit fails;
restore raw-rate accumulation in _cap_load_rows → live July effTrip > 2.
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


print("=== offline: TARGET TRIP → trip-counts ===")
import simulator_api as sa

# Two rows: rates 8 and 4 over plan DT 30 and 20 → weighted avg = (240+80)/50 = 6.4
# The BUG would store rates and do (8+4)/(30+20) = 0.24.
c1 = sa._planned_trip_counts(8.0, 30.0)
c2 = sa._planned_trip_counts(4.0, 20.0)
check("row counts = rate × DT PLAN", c1 == 240.0 and c2 == 80.0, (c1, c2))
check("missing plan DT → 0 counts (not raw rate)",
      sa._planned_trip_counts(8.0, 0) == 0.0
      and sa._planned_trip_counts(8.0, None) == 0.0)

agg = sa._cap_rates({
    "t": 1000.0, "trips": 320.0, "dt": 50.0,
    "planDt": 50.0, "planWmt": 1100.0, "_ptr": c1 + c2,
})
check("weighted planTripsPerDT == 6.4", abs(agg["planTripsPerDT"] - 6.4) < 0.01,
      agg["planTripsPerDT"])
check("effTrip sane for this toy (~1.0)", 0.5 <= agg["effTrip"] <= 1.5, agg["effTrip"])

# Reproduce the bug arithmetic and prove the gate's threshold would catch it.
bug_ptp = (8.0 + 4.0) / (30.0 + 20.0)  # 0.24
bug_eff = (320.0 / 50.0) / bug_ptp       # 6.4 / 0.24 = 26.67
check("bug arithmetic is outside the live band (documents the threshold)",
      bug_ptp < 0.5 and bug_eff > 2.0,
      "bug_ptp=%s bug_eff=%s" % (bug_ptp, bug_eff))


def cap(**params):
    url = BASE + "/api/simulator/capability?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read())


try:
    with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("\nno server on 5055 (%s) — offline checks only" % str(exc)[:60])
    mode = None

if mode == "sample-fixtures" or mode == "fixture":
    print("\n=== no-DB mode: fixture plan rate ===")
    d = cap(**{"from": "2025-09-01", "to": "2026-07-22"})
    k = d.get("kpi") or {}
    check("fixture planTripsPerDT in [0.5, 15]",
          0.5 <= float(k.get("planTripsPerDT") or 0) <= 15,
          k.get("planTripsPerDT"))
    check("fixture effTrip in [0.3, 2.0]",
          0.3 <= float(k.get("effTrip") or 0) <= 2.0,
          k.get("effTrip"))
elif mode == "database":
    print("\n=== live DB: planTripsPerDT must look like a rate ===")
    wide = cap(**{"from": "2025-09-01", "to": "2026-07-31"})
    k = wide.get("kpi") or {}
    check("live capability (not fixture)",
          wide.get("servedFrom") != "fixture", wide.get("servedFrom"))
    ptp = float(k.get("planTripsPerDT") or 0)
    tpd = float(k.get("tripsPerDT") or 0)
    eff = float(k.get("effTrip") or 0)
    check("planTripsPerDT in [0.5, 10]", 0.5 <= ptp <= 10, ptp)
    check("tripsPerDT in [0.5, 15]", 0.5 <= tpd <= 15, tpd)
    check("effTrip in [0.3, 2.0] (catches the 1700% bug)", 0.3 <= eff <= 2.0, eff)
    check("effTrip ≈ tripsPerDT/planTripsPerDT",
          abs(eff - tpd / ptp) < 0.05 if ptp else False,
          "%s vs %s/%s" % (eff, tpd, ptp))

    july = cap(**{"from": "2026-07-01", "to": "2026-07-31", "inclIwip": "1"})
    jk = july.get("kpi") or {}
    check("July planTripsPerDT in [0.5, 10]",
          0.5 <= float(jk.get("planTripsPerDT") or 0) <= 10,
          jk.get("planTripsPerDT"))
    check("July effTrip in [0.3, 2.0] (was 17.7)",
          0.3 <= float(jk.get("effTrip") or 0) <= 2.0,
          jk.get("effTrip"))

    # Per-path can honestly sit near 2× (e.g. POS 12→POS 12 at 2.0001). The
    # aggregation bug produced ~17× at KPI and path level — threshold 3 catches
    # that without flaking on real over-plan performers.
    crazy = [p for p in (wide.get("paths") or [])
             if (p.get("planTripsPerDT") or 0) > 0.5 and (p.get("effTrip") or 0) > 3]
    check("no path with planTripsPerDT>0.5 has effTrip>3",
          not crazy,
          [(p.get("origin"), p.get("dest"), p.get("effTrip"), p.get("planTripsPerDT"))
           for p in crazy[:5]])
else:
    print("\n(no live server — skipped HTTP assertions)")

print()
if FAILED:
    print("J65 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("plan-trip-rate gate passes")
