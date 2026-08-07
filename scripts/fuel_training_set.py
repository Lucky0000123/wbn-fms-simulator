#!/usr/bin/env python3
"""Build the diesel-consumption training set and cache it to disk.

Grain: one row per (unit, date). Target: litres per WORKING hour.

Confirmed by scripts/fuel_recon5.py against the live DB:
  WAITING_TIME.EQUIPMENT_ID joins EQUIPMENTS_HOURLY_STATUS.ID_EQ directly,
  99.6% of fuel unit-days.

IMPORTANT — do not use OPERATING_HOURS as the denominator. Despite the name it
is *calendar* hours: every shift row carries 12.0, so a unit-day sums to 24.0
regardless of how much the machine actually ran. Correlation with litres is
+0.010, i.e. none. WORKING_HOURS is the real engine-run figure (+0.165) and is
what l_per_work_hr uses. OPERATING_HOURS is still emitted, as a shift-coverage
flag only.

The VPN flaps, so this caches to data/fuel_recon/training_set.csv and every
downstream step reads the cache, not the database.
"""
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_recon import q  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "fuel_recon"
CSV = OUT / "training_set.csv"

SQL = """
WITH fuel AS (
  SELECT UPPER(LTRIM(RTRIM(REPLACE(EQUIPMENT_ID, NCHAR(8206), '')))) id,
         CAST([DATE] AS date) d,
         SUM(TRY_CONVERT(float, REPLACE(REPLACE(REPLACE(
             UPPER(TOTAL_FUEL),' L',''),'L',''),',','.'))) litres,
         COUNT(*) fills
  FROM dbo.WAITING_TIME
  WHERE TOTAL_FUEL IS NOT NULL AND LTRIM(RTRIM(TOTAL_FUEL)) <> ''
  GROUP BY UPPER(LTRIM(RTRIM(REPLACE(EQUIPMENT_ID, NCHAR(8206), '')))),
           CAST([DATE] AS date)),
hrs AS (
  SELECT UPPER(LTRIM(RTRIM(ID_EQ))) id, CAST([DATE] AS date) d,
         SUM(OPERATING_HOURS) op_hrs, SUM(WORKING_HOURS) work_hrs,
         SUM(STBY_HOURS) stby_hrs, SUM(BD_HOURS) bd_hrs, SUM(PM_HOURS) pm_hrs,
         MAX(CONTRACTOR) contractor, MAX(ACTIVITY) activity,
         MAX(LOCATION) location
  FROM dbo.EQUIPMENTS_HOURLY_STATUS
  WHERE [DATE] >= '2026-01-01'
  GROUP BY UPPER(LTRIM(RTRIM(ID_EQ))), CAST([DATE] AS date)),
wb AS (
  SELECT UPPER(LTRIM(RTRIM(TRUCK_ID))) id, CAST([DATE] AS date) d,
         SUM(TRY_CONVERT(float, NET_WEIGHT)) net_weight,
         COUNT(*) tickets
  FROM dbo.HAULAGE_IWIP_EXT WHERE [DATE] >= '2026-01-01'
  GROUP BY UPPER(LTRIM(RTRIM(TRUCK_ID))), CAST([DATE] AS date))
SELECT f.id AS unit_id, f.d AS date, f.litres, f.fills,
       h.op_hrs, h.work_hrs, h.stby_hrs, h.bd_hrs, h.pm_hrs,
       h.contractor, h.activity, h.location,
       wb.net_weight, wb.tickets,
       CASE WHEN h.work_hrs > 0 THEN f.litres / h.work_hrs END AS l_per_work_hr,
       CASE WHEN h.op_hrs > 0 THEN f.litres / h.op_hrs END AS l_per_op_hr
FROM fuel f
JOIN hrs h ON h.id = f.id AND h.d = f.d
LEFT JOIN wb ON wb.id = f.id AND wb.d = f.d
ORDER BY f.d, f.id;
"""


def main():
    cols, rows = q("WBN_DATABASE", SQL)
    if cols == ["ERROR"]:
        raise SystemExit(f"query failed: {rows}")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(CSV, "w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(cols)
        wtr.writerows(rows)
    print(f"wrote {CSV} — {len(rows):,} rows x {len(cols)} cols")

    i = {c: n for n, c in enumerate(cols)}
    lph = [r[i["l_per_work_hr"]] for r in rows
           if isinstance(r[i["l_per_work_hr"]], (int, float))]
    lph.sort()
    if lph:
        def pct(p):
            return lph[min(len(lph) - 1, int(p * len(lph)))]
        print(f"  l_per_work_hr  n={len(lph):,}  "
              f"p05={pct(.05):.2f}  median={pct(.5):.2f}  "
              f"p95={pct(.95):.2f}  max={lph[-1]:.1f}")
        print(f"  implausible (>60 L/h): "
              f"{sum(1 for v in lph if v > 60):,} rows "
              f"({100*sum(1 for v in lph if v > 60)/len(lph):.2f}%)")
        print(f"  zero/near-zero (<1 L/h): {sum(1 for v in lph if v < 1):,}")
    wbn = sum(1 for r in rows if r[i["net_weight"]] is not None)
    print(f"  rows with weighbridge tonnes: {wbn:,} "
          f"({100*wbn/len(rows):.1f}%)")


if __name__ == "__main__":
    main()
