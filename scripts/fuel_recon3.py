#!/usr/bin/env python3
"""Phase 3: real row counts + 20-row samples for the tables that actually
matter to a diesel model, plus a probe of the only fuel-bearing table."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_recon import q, save  # noqa: E402

TARGETS = {
    "WBN_DATABASE": [
        "EQUIPMENTS_HOURLY_STATUS", "EQUIPMENTS_HOURLY_ACTIVITIES",
        "EQUIPMENTS_STATUS", "EQUIPMENTS", "EQUIPMENTS_WORKS", "DAY_WORKS",
        "WAITING_TIME", "HAULAGE", "HAULAGE_IWIP", "HAULAGE_IWIP_EXT",
        "DISTANCE_MINING", "PRODUCTION_PIT_MINING_DISTANCE", "HAUL_ROAD_STA",
        "HRM_CONTRACT_EQUIPMENT", "CONTRACTOR FOLLOW UP", "RSF_HAULING_DATA",
    ],
    "FMS_DB": [
        "FMS_EQUIPMENTS", "FMS_PLAYBACK_TRACK_DATA", "FMS_CONGESTION_SEG",
        "FMS_HAUL_CYCLES", "FMS_TRUCK_ASSIGNMENTS", "FMS_UNIT_INSTALLED",
        "auto_kmFMS_PLAYBACK_TRACK_DATA", "FMS_GEOFENCE_VISITS",
    ],
}

FULLCOLS = """
SELECT c.name, ty.name, c.max_length, c.is_nullable
FROM sys.columns c JOIN sys.types ty ON c.user_type_id=ty.user_type_id
WHERE c.object_id = OBJECT_ID('dbo.[{t}]') ORDER BY c.column_id;
"""


def main():
    for db, tabs in TARGETS.items():
        print(f"=== {db} ===")
        res = {}
        for t in tabs:
            entry = {}
            c, r = q(db, FULLCOLS.format(t=t))
            entry["schema"] = {"columns": c, "rows": r}
            if not r:
                print(f"  {t}: MISSING")
                res[t] = entry
                continue
            c, r = q(db, f"SELECT COUNT_BIG(*) AS n FROM dbo.[{t}];")
            entry["count"] = r[0][0] if r else None
            c2, r2 = q(db, f"SELECT TOP (20) * FROM dbo.[{t}];")
            entry["sample"] = {"columns": c2, "rows": r2}
            print(f"  {t}: {len(entry['schema']['rows'])} cols, "
                  f"{entry['count']} rows")
            res[t] = entry
        save(f"phase3_{db}", res)

    # Probe the only fuel-bearing table in either database.
    c, r = q("WBN_DATABASE", """
        SELECT COUNT_BIG(*) AS total,
               COUNT([TOTAL_FUEL]) AS total_fuel_notnull,
               COUNT([FUEL_FILLING_TIME]) AS fill_time_notnull,
               MIN([DATE]) AS min_date, MAX([DATE]) AS max_date
        FROM dbo.WAITING_TIME;""")
    print("\nWAITING_TIME fuel coverage:", c, r)
    c2, r2 = q("WBN_DATABASE", """
        SELECT TOP (30) [TOTAL_FUEL], COUNT(*) AS n
        FROM dbo.WAITING_TIME WHERE [TOTAL_FUEL] IS NOT NULL
        GROUP BY [TOTAL_FUEL] ORDER BY COUNT(*) DESC;""")
    print("TOTAL_FUEL distinct values:", r2)
    save("phase3_waiting_time_probe",
         {"coverage": {"columns": c, "rows": r},
          "total_fuel_values": {"columns": c2, "rows": r2}})


if __name__ == "__main__":
    main()
