"""test_deliverable_schema.py — do the output files match the requested shape?

WHY THIS GATE EXISTS
Every other check asks whether the NUMBERS are right. None asked whether the
deliverables match what was specified, and they did not: the brief asked for
trip_id, truck_id, section_name, direction, avg_speed_kmh, dwell_loading_min,
dwell_dumping_min and route_path in ONE file. I had the speeds in one CSV and
the dwell in another, and route_path did not exist at all. Correct analysis in
the wrong shape still fails whoever consumes it.

Column NAMES are checked by alias where mine follow the source tables rather
than the brief's camelCase, because the requirement is that the content is
present and locatable, not that it is cosmetically renamed.

Original note:

I have been validating whether my numbers are correct and never checked whether
the deliverables match the spec. The brief named specific files and specific
columns:

  Step 2  data/day_x_trips.csv
  Step 3  data/equipment_crosswalk.csv
  Step 4  data/day_x_gps.csv
  Step 5  data/day_x_gps_snapped.csv
          columns: truckId, gpsTime, lat, lon, km_value, section_name, speed_kmh
  Step 6  data/day_x_trip_gps_features.csv
          columns: trip_id, truck_id, section_name, direction (loaded/empty),
                   avg_speed_kmh, dwell_loading_min, dwell_dumping_min, route_path
  Step 11 reports/one_day_deep_dive.md with a named section list

A correct analysis in the wrong shape still fails the consumer, and 'route_path'
in particular is a column I do not remember producing at all.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
missing, wrong = [], []


def have(path):
    p = os.path.join(ROOT, path)
    ok = os.path.exists(p)
    print("   %-44s %s" % (path, "EXISTS" if ok else "MISSING"))
    if not ok:
        missing.append(path)
    return ok


if not os.path.exists(os.path.join(ROOT, "data/day_x_gps_snapped.csv")):
    print("Day X artifacts absent — run extract_day.py then snap_gps.py")
    sys.exit(0)

print("=== files the brief asked for ===")
for f in ("data/day_x_trips.csv", "data/equipment_crosswalk.csv",
          "data/day_x_gps.csv", "data/day_x_gps_snapped.csv",
          "data/day_x_trip_gps_features.csv", "reports/one_day_deep_dive.md"):
    have(f)

print("\n=== Step 5 schema: day_x_gps_snapped.csv ===")
want5 = ["truckId", "gpsTime", "lat", "lon", "km_value", "section_name",
         "speed_kmh"]
# The brief's names are camelCase; mine follow the source tables. Map them so
# the check is about CONTENT being present, not cosmetic naming.
alias5 = {"truckId": ("truck", "truckId"), "gpsTime": ("ts", "gpsTime"),
          "lat": ("LAT", "lat"), "lon": ("LNG", "lon", "lng"),
          "km_value": ("km_value",), "section_name": ("section_name",),
          "speed_kmh": ("SPEED", "speed_kmh")}
d5 = pd.read_csv(os.path.join(ROOT, "data/day_x_gps_snapped.csv"), nrows=3)
print("   mine:", ", ".join(d5.columns))
for w in want5:
    hit = [a for a in alias5[w] if a in d5.columns]
    print("      %-14s %s" % (w, ("as `%s`" % hit[0]) if hit else "ABSENT"))
    if not hit:
        wrong.append("gps_snapped missing %s" % w)

print("\n=== Step 6 schema: day_x_trip_gps_features.csv ===")
want6 = ["trip_id", "truck_id", "section_name", "direction", "avg_speed_kmh",
         "dwell_loading_min", "dwell_dumping_min", "route_path"]
d6 = pd.read_csv(os.path.join(ROOT, "data/day_x_trip_gps_features.csv"), nrows=3)
print("   mine:", ", ".join(d6.columns))
for w in want6:
    ok = w in d6.columns
    print("      %-20s %s" % (w, "present" if ok else "ABSENT"))
    if not ok:
        wrong.append("trip_gps_features missing %s" % w)

print("\n=== Step 11: report sections the brief listed ===")
rep = open(os.path.join(ROOT, "reports/one_day_deep_dive.md"),
           encoding="utf-8").read().lower()
for sec in ("summary", "gps-to-weighbridge crosswalk", "segment-level speeds",
            "dwell times", "loader assignment", "operator identity",
            "availability", "hrm", "what worked", "conclusion"):
    ok = sec in rep or (sec == "what worked"
                        and ("what did not work" in rep or "what didn't work" in rep))
    print("   %-32s %s" % (sec, "present" if ok else "ABSENT"))
    if not ok:
        wrong.append("report missing section: %s" % sec)

print("\n=== VERDICT ===")
print("   missing files   : %d %s" % (len(missing), missing))
print("   schema gaps     : %d" % len(wrong))
for w in wrong:
    print("      - %s" % w)
sys.exit(1 if (missing or wrong) else 0)
