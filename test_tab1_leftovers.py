"""Gate J70: remaining Tab 1 honesty items.

1. GPS polyline map (Leaflet) primary over schematic stick
2. Constraints Save persists to data/constraints_local.json
3. Live trucks path uses HAULAGE_IWIP_CLEAN / TRUCK_ID
4. V/C from measuredCapacity (not only assumed 90s headway)
5. Measured GPS window extends past the prior Jul-31 cut (re-extract)
"""
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name
          + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


print("=== offline: measured capacity + window ===")
sys.path.insert(0, ROOT)
import simulator_api as sa  # noqa: E402

sa._CORRIDOR_LAYERS = None
c = sa._corridor_payload()
mc = c.get("measuredCapacity")
by_dir = os.path.join(ROOT, "data", "congestion_seg_by_dir.csv")
if os.path.isfile(by_dir):
    check("measuredCapacity present",
          isinstance(mc, dict) and (mc.get("trucksPerHour") or 0) > 5, mc)
    check("measuredCapacity has method + equivHeadway",
          bool(mc and mc.get("method") and mc.get("equivHeadwaySec")), mc)
    win = c.get("measuredWindow") or {}
    check("GPS window to >= 2026-08-01 (re-extract)",
          str(win.get("to") or "") >= "2026-08-01", win)
else:
    print("  SKIP capacity/window file asserts (no congestion CSV)")

print("\n=== offline: JS / HTML (map + V/C + trucks) ===")
js = open(os.path.join(ROOT, "static", "js", "flow_sim.js"), encoding="utf-8").read()
html = open(os.path.join(ROOT, "templates", "simulator.html"), encoding="utf-8").read()
api_js = open(os.path.join(ROOT, "static", "js", "api.js"), encoding="utf-8").read()
serve = open(os.path.join(ROOT, "serve.py"), encoding="utf-8").read()
sim = open(os.path.join(ROOT, "simulator_api.py"), encoding="utf-8").read()

check("flowMapEnsure / flowMapSync present",
      "function flowMapEnsure" in js and "function flowMapSync" in js)
check("c3-flow-map in HTML", 'id="c3-flow-map"' in html)
check("stick always visible with map",
      'id="c3-flow-visuals"' in html and 'id="c3-flow-stick"' in html
      and "flow-stick-details" not in html
      and "function flowScrollVisualsIntoView" in js)
check("flowLaneCapacity uses measuredCapacity",
      "function flowLaneCapacity" in js and "measuredCapacity" in js)
check("flow-vc-hint label", "flow-vc-hint" in html)
check("api_simulator_trucks uses HAULAGE_IWIP_CLEAN",
      "def api_simulator_trucks" in sim and "HAULAGE_IWIP_CLEAN" in sim
      and "TRUCK_ID" in sim)
check("serve constraints persist path",
      "constraints_local.json" in serve and "_constraints_write" in serve)
check("saveMatrix posts constraints",
      "method:'POST'" in api_js and "/api/simulator/constraints" in api_js)

print("\n=== offline: constraints write/read/reset ===")
# Exercise serve helpers without starting Flask: import serve after pointing
# CONSTRAINTS_LOCAL at a temp file.
tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
tmp.close()
try:
    os.environ.setdefault("FMS_DB_HOST", "")  # keep import from needing DB
    # Importing serve starts Flask app; fine for unit checks.
    import serve as srv  # noqa: E402
    old = srv.CONSTRAINTS_LOCAL
    srv.CONSTRAINTS_LOCAL = tmp.name
    if os.path.isfile(tmp.name):
        os.remove(tmp.name)
    payload = {
        "ok": True,
        "sections": [{"id": 1, "name": "TOFU–KR"}, {"id": 2, "name": "KR–POS 12"}],
        "paths": [{"origin": "TF", "dest": "FENI KM0", "sections": [1, 2]}],
    }
    srv._constraints_write(payload)
    loaded = srv._constraints_load()
    check("constraints_local round-trip",
          loaded.get("persisted") is True
          and len(loaded.get("sections") or []) == 2
          and len(loaded.get("paths") or []) == 1,
          {k: loaded.get(k) for k in ("persisted", "sections", "paths")})
    if os.path.isfile(tmp.name):
        os.remove(tmp.name)
    reset = srv._constraints_load()
    check("constraints fall back to fixture after delete",
          reset.get("persisted") is False
          and len(reset.get("sections") or []) >= 1,
          reset.get("persisted"))
    srv.CONSTRAINTS_LOCAL = old
finally:
    try:
        os.remove(tmp.name)
    except OSError:
        pass

# Live HTTP (optional)
try:
    with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
        health = json.loads(r.read())
        mode = health.get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("\nno server on 5055 (%s) — offline checks only" % str(exc)[:60])
    mode = None
    health = None

if mode:
    print("\n=== live: constraints + trucks + corridor ===")
    # Constraints GET
    with urllib.request.urlopen(BASE + "/api/simulator/constraints", timeout=30) as r:
        d = json.loads(r.read())
    check("live constraints ok", d.get("ok") is True, d.get("error"))

    # Capability measuredCapacity
    with urllib.request.urlopen(
            BASE + "/api/simulator/capability?from=2026-07-01&to=2026-07-31",
            timeout=120) as r:
        cap = json.loads(r.read())
    cor = cap.get("corridor") or {}
    if os.path.isfile(by_dir):
        check("live measuredCapacity trucksPerHour > 5",
              ((cor.get("measuredCapacity") or {}).get("trucksPerHour") or 0) > 5,
              cor.get("measuredCapacity"))

    # Corridor geometry for map
    with urllib.request.urlopen(
            BASE + "/api/simulator/corridor-geometry", timeout=30) as r:
        geo = json.loads(r.read())
    check("live corridor-geometry ok with roads",
          geo.get("ok") and len(geo.get("roads") or []) >= 2,
          geo.get("reason") or len(geo.get("roads") or []))

    # Trucks
    with urllib.request.urlopen(
            BASE + "/api/simulator/trucks?from=2026-07-01&to=2026-07-09",
            timeout=120) as r:
        tr = json.loads(r.read())
    check("live trucks ok", tr.get("ok") is True, tr.get("error"))
    if mode == "database":
        check("live trucks servedFrom=db",
              tr.get("servedFrom") == "db", tr.get("servedFrom"))
        sample = (tr.get("trucks") or [{}])[0]
        check("live truck id looks real (not empty)",
              bool(sample.get("truck")), sample)
    else:
        check("fixture trucks still ok when not database",
              len(tr.get("trucks") or []) > 0, tr.get("servedFrom"))

print()
if FAILED:
    print("J70 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("tab1 leftovers gate passes")
