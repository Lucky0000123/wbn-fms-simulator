"""Gate J67: weighbridge-summary discloses source, age, and staleness.

Tab 1 QC: payload was byte-identical to the fixture (date 2026-07-09) with
servedFrom=null, so the UI looked live. otherShare=100% that day is REAL —
every contractor was an IWIP Chinese workshop name, none in the WBN set.
Honesty means tagging source + ageDays and stale when age > 3 days.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


try:
    with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("no server on 5055 (%s) -- skipping" % str(exc)[:60])
    sys.exit(0)

with urllib.request.urlopen(BASE + "/api/weighbridge-summary", timeout=60) as r:
    d = json.loads(r.read())

print("=== weighbridge-summary honesty ===")
check("ok", d.get("ok") is True)
check("has a date", bool(d.get("date")), d.get("date"))

if mode == "database" and d.get("servedFrom") is None:
    check("names its source table",
          "HAULAGE_IWIP_CLEAN" in (d.get("source") or ""),
          d.get("source"))
    check("reports ageDays", isinstance(d.get("ageDays"), int), d.get("ageDays"))
    # Table ends 2026-07-09 as of the QC window; by Aug 2026 age > 3.
    if isinstance(d.get("ageDays"), int) and d["ageDays"] > 3:
        check("marks stale when ageDays > 3", d.get("stale") is True, d.get("stale"))
        check("explains why", bool(d.get("staleReason")), d.get("staleReason"))
    check("has bridges/trucks", (d.get("bridges") or 0) > 0 and (d.get("trucks") or 0) > 0)
else:
    check("fixture path tagged when not live",
          d.get("servedFrom") == "fixture" or d.get("stale") is True,
          d.get("servedFrom"))

print()
if FAILED:
    print("J67 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("weighbridge honesty gate passes")
