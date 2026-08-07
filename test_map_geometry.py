"""Gate J63: the corridor map has geometry on a fresh clone, and only road geometry.

This gate guards a DELIBERATE, NARROW EXCEPTION to the rule that site geometry
is not committed to a public mirror.

Committed: `data/haul_road_chainage_public.csv` -- a road CENTRELINE, four
columns (road code, km marker, latitude, longitude) and nothing else. The
corridor it describes is already rendered by OpenStreetMap; withholding it
bought no secrecy and cost the map on every fresh clone and on the public demo.

NOT committed, and this gate checks it stays that way: geofences, loading and
dumping zones, security boundaries, tonnages, contractors, equipment. The
exception is one file wide.

The load-bearing assertion is the SCHEMA one. A future re-export that quietly
adds a `zone` or `geofence` column would leak it into a public repo through a
path that already has permission, and nothing else in the pipeline would notice.
So the column set is pinned rather than merely inspected once.
"""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "data", "haul_road_chainage_public.csv")
FULL = os.path.join(ROOT, "data", "haul_road_chainage.csv")
FAILED = []

# Exactly these, in any order. Anything else is a schema change that must be
# reviewed before it reaches the mirror.
ALLOWED_COLUMNS = {"road", "km", "lat", "lng"}

# Substrings that must never appear in a column name here.
FORBIDDEN = ("zone", "geofence", "boundary", "wmt", "ton", "contractor",
             "equip", "truck", "owner", "security", "grade", "payload")


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def git(*args):
    try:
        return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return ""


print("=== the committed centreline exists and IS tracked ===")
check("data/haul_road_chainage_public.csv exists", os.path.exists(PUBLIC))
if not os.path.exists(PUBLIC):
    print("J63 FAILED: the committed geometry is missing")
    sys.exit(1)

tracked = git("ls-files", "data/haul_road_chainage_public.csv")
check("it is tracked by git (not merely present locally)",
      tracked.endswith("haul_road_chainage_public.csv"), tracked or "NOT TRACKED")

print("\n=== and it contains ONLY road centreline ===")
with open(PUBLIC, newline="") as fh:
    reader = csv.DictReader(fh)
    cols = set(reader.fieldnames or [])
    rows = list(reader)

check("schema is exactly {road, km, lat, lng}", cols == ALLOWED_COLUMNS, sorted(cols))
bad = [c for c in cols for f in FORBIDDEN if f in c.lower()]
check("no zone / geofence / tonnage / equipment column", not bad, bad)
check("has a usable number of markers", len(rows) > 500, len(rows))

# The only text column must hold road CODES, not place or zone names. A handful
# of short codes is the signature of a road identifier; dozens of long strings
# would mean something else got exported.
roads = sorted({r["road"] for r in rows})
check("the text column holds a few short road codes",
      len(roads) <= 15 and all(len(x) <= 6 for x in roads), roads)

# Coordinates must be finite and inside the site's bounding box. Catches a
# re-export that silently changed units or column order.
try:
    lats = [float(r["lat"]) for r in rows]
    lngs = [float(r["lng"]) for r in rows]
    kms = [float(r["km"]) for r in rows]
    ok_geo = (0.0 < min(lats) and max(lats) < 1.5
              and 127.0 < min(lngs) and max(lngs) < 129.0
              and 0 <= min(kms) and max(kms) < 100)
except Exception as exc:                                          # noqa: BLE001
    ok_geo, exc = False, exc
check("coordinates parse and sit in the site bounding box", ok_geo,
      "lat %.3f..%.3f lng %.3f..%.3f" % (min(lats), max(lats), min(lngs), max(lngs))
      if "lats" in dir() else "unparseable")

print("\n=== the FULL extract stays out of the repo ===")
full_tracked = git("ls-files", "data/haul_road_chainage.csv")
check("the full extract is NOT tracked", full_tracked == "", full_tracked)
check("no other data/*.csv has been un-ignored",
      all(not f.endswith(".csv")
          or f.endswith("haul_road_chainage_public.csv")
          # Posted speed-limit zones: chainage + km/h only (see .gitignore
          # rationale; content pinned by test_flow_gps_speeds.py / J69).
          or f.endswith("speed_limit_zones_public.csv")
          for f in git("ls-files", "data/").split("\n") if f),
      [f for f in git("ls-files", "data/").split("\n")
       if f.endswith(".csv")
       and not f.endswith("haul_road_chainage_public.csv")
       and not f.endswith("speed_limit_zones_public.csv")])

print("\n=== the endpoint serves it when the extract is absent ===")
import simulator_api as sa                                          # noqa: E402
import serve                                                        # noqa: E402

client = serve.app.test_client()
sa._GEOM_CACHE = None
d = client.get("/api/simulator/corridor-geometry").get_json()
check("endpoint returns geometry", d.get("ok") is True and len(d.get("roads") or []) > 0,
      d.get("reason"))

# Simulate a fresh clone by hiding the extract, so the committed file is the
# only source. Restored in a finally so a failure here cannot leave the machine
# without its own data.
hidden = FULL + ".j63-hidden"
moved = False
try:
    if os.path.exists(FULL):
        os.rename(FULL, hidden)
        moved = True
    sa._GEOM_CACHE = None
    d2 = client.get("/api/simulator/corridor-geometry").get_json()
    check("fresh clone still gets geometry", d2.get("ok") is True, d2.get("reason"))
    check("and it comes from the COMMITTED file",
          d2.get("geometrySource") == "committed", d2.get("geometrySource"))
    check("same road count as the full extract",
          len(d2.get("roads") or []) == len(d.get("roads") or []),
          "%s vs %s" % (len(d2.get("roads") or []), len(d.get("roads") or [])))
finally:
    if moved:
        os.rename(hidden, FULL)
    sa._GEOM_CACHE = None

print()
if FAILED:
    print("J63 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("map geometry gate passes")
