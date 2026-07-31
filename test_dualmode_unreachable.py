"""Gate J58: the fixture fallback fires when the DB is configured but unreachable.

THERE ARE THREE MODES, NOT TWO, AND ONLY TWO WERE EVER TESTED.

    no FMS_DB_* at all          -> _db_ready() false -> fixture        (tested)
    DB configured and reachable -> live data                           (tested)
    DB configured, UNREACHABLE  -> ???                                 (untested)

The third is the NORMAL state here: the site VPN drops every few minutes. It was
broken in five endpoints, because each caught its own exception and returned
`{"ok": false, "error": ...}` with HTTP 200. A 200 looks like success to
_register, so the fallback never fired and the section went blank while a
complete fixture sat unused -- 94 segments of congestion data, 113 rows of
weighbridge history.

This gate drives the real Flask app with credentials pointed at an unroutable
host, which is the closest reproduction of a dropped VPN that needs no network.
It asserts two different things:

  1. BEHAVIOUR -- every DB-backed endpoint still answers 200 with fixture
     content, tagged `servedFrom: "fixture"` so a UI can label it honestly
     rather than passing cached figures off as live.
  2. STRUCTURE -- no endpoint has re-grown a self-catch that returns an error
     payload instead of raising. Behaviour alone would not stop the pattern
     coming back on a NEW endpoint, and this defect appeared five times.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import serve                      # noqa: E402
import simulator_api as sa        # noqa: E402

FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


# 10.211.10.99 is inside the site's subnet but unassigned, so the connect fails
# the way a dropped VPN does rather than the way a bad hostname does.
sa._DB.update({"server": "10.211.10.99", "user": "probe", "password": "probe"})
check("_db_ready() reports a configured DB", sa._db_ready())

client = serve.app.test_client()

# (path, must-contain-a-non-empty-list) -- endpoints whose fixture carries rows.
# shift-context needs a date or it short-circuits on parameter validation before
# ever reaching the database, which is correct and must not be mistaken for the
# fallback firing.
ENDPOINTS = [
    ("/api/simulator/congestion-model", "segments"),
    ("/api/simulator/path-response", None),
    ("/api/simulator/weighbridge", None),
    ("/api/weighbridge-summary", None),
    ("/api/simulator/shift-context?date=2026-03-15", "bridges"),
]

print("=== behaviour: unreachable DB must serve the tagged fixture ===")
for path, list_key in ENDPOINTS:
    r = client.get(path)
    name = path.split("?")[0]
    check("%s returns 200" % name, r.status_code == 200, r.status_code)
    d = r.get_json()
    ok = isinstance(d, dict)
    check("%s returns a JSON object" % name, ok, type(d).__name__)
    if not ok:
        continue
    check("%s served from fixture" % name, d.get("servedFrom") == "fixture",
          "servedFrom=%r ok=%r error=%r" % (d.get("servedFrom"), d.get("ok"),
                                            str(d.get("error"))[:60]))
    check("%s explains why" % name,
          "unreachable" in (d.get("servedFromReason") or ""),
          d.get("servedFromReason"))
    if list_key:
        check("%s fixture actually carries %s" % (name, list_key),
              isinstance(d.get(list_key), list) and len(d[list_key]) > 0,
              len(d.get(list_key) or []))

print("\n=== no-DB mode must still work, and must also be tagged ===")
sa._DB.update({"server": "", "user": "", "password": ""})
check("_db_ready() now false", not sa._db_ready())
r = client.get("/api/simulator/congestion-model")
d = r.get_json()
check("no-DB serves the fixture", d.get("servedFrom") == "fixture", d.get("servedFrom"))
check("no-DB says why", d.get("servedFromReason") == "no database configured",
      d.get("servedFromReason"))
check("no-DB fixture carries segments", len(d.get("segments") or []) > 0)

print("\n=== structure: no endpoint may swallow a DB error into a 200 payload ===")
src = open(os.path.join(ROOT, "simulator_api.py")).read()
# The exact shape of the defect: returning an ok:false "... unavailable" payload
# from an except block, which _register cannot distinguish from success.
swallow = re.findall(r'return jsonify\(\{"ok": False[^\n]*unavailable', src, re.I)
check("no 'ok:False ... unavailable' returns remain", not swallow,
      "%d found: %s" % (len(swallow), swallow[:2]))

# _register must keep tagging, or the UI silently starts calling cached data live.
check("_register tags the no-DB fallback",
      'no database configured' in src)
check("_register tags the unreachable fallback",
      'database configured but unreachable' in src)

print()
if FAILED:
    print("J58 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("unreachable-DB dual-mode gate passes")
