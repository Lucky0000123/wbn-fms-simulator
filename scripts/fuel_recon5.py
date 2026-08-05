#!/usr/bin/env python3
"""Phase 5 — THE decisive test for the diesel model.

Fuel litres live in WAITING_TIME.EQUIPMENT_ID, which uses the 4-char fleet
namespace (`L961`, shape A999).  Operating hours live in
EQUIPMENTS_HOURLY_STATUS.ID_EQ, which uses an 11-char asset namespace
(`ATCT0450027`, shape AAAA9999999).  These do not join directly.

Offline shape analysis of the cached samples says:
  A999         -> WAITING_TIME.EQUIPMENT_ID, HAULAGE_IWIP_EXT.TRUCK_ID,
                  FMS_EQUIPMENTS.plateNumber, FMS_UNIT_INSTALLED.PLATE,
                  FMS_GEOFENCE_VISITS.UNIT_ID, RSF_HAULING_DATA.NB_UNIT,
                  EQUIPMENTS_HOURLY_ACTIVITIES.EXCAVATOR_ID
  AAAA9999999  -> EQUIPMENTS_HOURLY_STATUS.ID_EQ, DAY_WORKS.UNIT_ID

So DAY_WORKS is the prime bridge: it shares the asset namespace with the hours
table AND carries UNIT_START_HOUR_METER / UNIT_END_HOUR_METER (true hour
meters, which the original keyword net missed because they are spelled
HOUR_METER inside a UNIT_ prefix).

This script decides, with counts and not adjectives:
  A. Does fuel join to hours directly?            (expected: no)
  B. Which table bridges A999 -> AAAA9999999?     (candidates below)
  C. Are DAY_WORKS hour meters actually populated?
  D. What does the resulting training set look like, and how big is it?

Run when the VPN to 10.211.10.1 is up:
    ./.venv/bin/python scripts/fuel_recon5.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_recon import q, save  # noqa: E402

DB = "WBN_DATABASE"
FUEL = ("SELECT DISTINCT LTRIM(RTRIM(EQUIPMENT_ID)) id FROM dbo.WAITING_TIME "
        "WHERE TOTAL_FUEL IS NOT NULL AND LTRIM(RTRIM(TOTAL_FUEL))<>''")
Q = {}

# A. direct join, expected to fail.
Q["A_direct_fuel_to_hours"] = f"""
WITH f AS ({FUEL}),
     h AS (SELECT DISTINCT LTRIM(RTRIM(ID_EQ)) id
           FROM dbo.EQUIPMENTS_HOURLY_STATUS WHERE [DATE] >= '2026-02-01')
SELECT (SELECT COUNT(*) FROM f) fuel_units,
       (SELECT COUNT(*) FROM h) hour_units,
       (SELECT COUNT(*) FROM f JOIN h ON f.id = h.id) matched;
"""

# B. bridge candidates: every column that shares the A999 namespace and might
#    also carry the asset-namespace key.
Q["B_bridge_day_works"] = f"""
WITH f AS ({FUEL})
SELECT COUNT(DISTINCT f.id) fuel_units_seen_in_day_works
FROM f JOIN dbo.DAY_WORKS d ON LTRIM(RTRIM(d.UNIT_ID)) = f.id;
"""
Q["B_bridge_equipments_master"] = f"""
WITH f AS ({FUEL})
SELECT (SELECT COUNT(*) FROM f JOIN dbo.EQUIPMENTS e
          ON LTRIM(RTRIM(e.ID_EQ)) = f.id)      via_ID_EQ,
       (SELECT COUNT(*) FROM f JOIN dbo.EQUIPMENTS e
          ON LTRIM(RTRIM(e.NEW_ID_EQ)) = f.id)  via_NEW_ID_EQ,
       (SELECT COUNT(*) FROM f JOIN dbo.EQUIPMENTS e
          ON LTRIM(RTRIM(e.SERIAL_NO)) = f.id)  via_SERIAL_NO;
"""
Q["B_bridge_haulage_ext"] = f"""
WITH f AS ({FUEL})
SELECT COUNT(DISTINCT f.id) fuel_units_in_haulage_ext
FROM f JOIN dbo.HAULAGE_IWIP_EXT x ON LTRIM(RTRIM(x.TRUCK_ID)) = f.id;
"""
# Does EQUIPMENTS hold BOTH namespaces on one row (the FMS_EQUIPMENTS trick)?
Q["B_equipments_namespace_map"] = """
SELECT TOP (30) ID, ID_EQ, NEW_ID_EQ, SERIAL_NO, TYPE, MODEL, CONTRACTOR
FROM dbo.EQUIPMENTS
WHERE TYPE LIKE '%TRUCK%' OR TYPE LIKE '%DUMP%' OR TYPE LIKE '%EXCA%'
   OR TYPE LIKE '%HAUL%';
"""

# C. are the DAY_WORKS hour meters real?
Q["C_day_works_hourmeter_coverage"] = """
SELECT COUNT_BIG(*) rows_all,
       COUNT(UNIT_START_HOUR_METER) start_hm,
       COUNT(UNIT_END_HOUR_METER)   end_hm,
       COUNT(DISTINCT UNIT_ID)      units,
       MIN([DATE]) mn, MAX([DATE]) mx
FROM dbo.DAY_WORKS;
"""
Q["C_day_works_hourmeter_recent"] = """
SELECT COUNT_BIG(*) rows_2026,
       COUNT(UNIT_START_HOUR_METER) start_hm,
       COUNT(UNIT_END_HOUR_METER)   end_hm
FROM dbo.DAY_WORKS WHERE [DATE] >= '2026-02-01';
"""

# D. the training set, if a join exists at all.
Q["D_training_set_direct"] = """
WITH fuel AS (
  SELECT LTRIM(RTRIM(EQUIPMENT_ID)) id, CAST([DATE] AS date) d,
         SUM(TRY_CONVERT(float, REPLACE(REPLACE(REPLACE(
             UPPER(TOTAL_FUEL),' L',''),'L',''),',','.'))) litres,
         COUNT(*) fills
  FROM dbo.WAITING_TIME
  WHERE TOTAL_FUEL IS NOT NULL AND LTRIM(RTRIM(TOTAL_FUEL))<>''
  GROUP BY LTRIM(RTRIM(EQUIPMENT_ID)), CAST([DATE] AS date)),
hrs AS (
  SELECT LTRIM(RTRIM(ID_EQ)) id, CAST([DATE] AS date) d,
         SUM(OPERATING_HOURS) op_hrs, MAX(CONTRACTOR) contractor
  FROM dbo.EQUIPMENTS_HOURLY_STATUS WHERE [DATE] >= '2026-01-01'
  GROUP BY LTRIM(RTRIM(ID_EQ)), CAST([DATE] AS date))
SELECT COUNT(*) fuel_unit_days,
       SUM(CASE WHEN h.id IS NOT NULL THEN 1 ELSE 0 END) joined_unit_days
FROM fuel f LEFT JOIN hrs h ON f.id = h.id AND f.d = h.d;
"""

# Fallback target: litres per tonne-km from the weighbridge, which shares the
# A999 namespace with fuel and needs no bridge at all.
Q["D_training_set_via_haulage"] = """
WITH fuel AS (
  SELECT LTRIM(RTRIM(EQUIPMENT_ID)) id, CAST([DATE] AS date) d,
         SUM(TRY_CONVERT(float, REPLACE(REPLACE(REPLACE(
             UPPER(TOTAL_FUEL),' L',''),'L',''),',','.'))) litres
  FROM dbo.WAITING_TIME
  WHERE TOTAL_FUEL IS NOT NULL AND LTRIM(RTRIM(TOTAL_FUEL))<>''
  GROUP BY LTRIM(RTRIM(EQUIPMENT_ID)), CAST([DATE] AS date))
SELECT COUNT(*) fuel_unit_days,
       SUM(CASE WHEN x.id IS NOT NULL THEN 1 ELSE 0 END) joined_unit_days
FROM fuel f
LEFT JOIN (SELECT DISTINCT LTRIM(RTRIM(TRUCK_ID)) id, CAST([DATE] AS date) d
           FROM dbo.HAULAGE_IWIP_EXT) x ON x.id = f.id AND x.d = f.d;
"""
Q["D_sample_joined_rows"] = """
WITH fuel AS (
  SELECT LTRIM(RTRIM(EQUIPMENT_ID)) id, CAST([DATE] AS date) d,
         SUM(TRY_CONVERT(float, REPLACE(REPLACE(REPLACE(
             UPPER(TOTAL_FUEL),' L',''),'L',''),',','.'))) litres,
         COUNT(*) fills
  FROM dbo.WAITING_TIME
  WHERE TOTAL_FUEL IS NOT NULL AND LTRIM(RTRIM(TOTAL_FUEL))<>''
  GROUP BY LTRIM(RTRIM(EQUIPMENT_ID)), CAST([DATE] AS date))
SELECT TOP (20) * FROM fuel ORDER BY d DESC, litres DESC;
"""


def main():
    res = {}
    for k, sql in Q.items():
        c, r = q(DB, sql)
        res[k] = {"columns": c, "rows": r}
        print(f"\n## {k}\n   {c}")
        for row in r[:30]:
            print("   ", row)
    save("phase5_join_test", res)
    print("\nNext: fold results into reports/FUEL_DATA_RECON.md section 9.")


if __name__ == "__main__":
    main()
