#!/usr/bin/env python3
"""Phase 2: widen the net (fuel synonyms, hourmeter/SMU, odometer), then pull
row counts, full schemas and 20-row samples for every candidate table."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_recon import DBS, OUT, COL_SQL, q, save  # noqa: E402

# Much wider column-name net than step 2.
WIDE = ["FUEL", "DIESEL", "BBM", "SOLAR", "LITRE", "LITER", "LTR", "LT_",
        "CONSUM", "BURN", "REFUEL", "FILL", "DISPENSE", "PUMP", "TANK",
        "HOURMETER", "HOUR_METER", "HM_", "_HM", "SMU", "ODOMETER", "ODO",
        "KM_", "_KM", "MILEAGE", "ENGINE_HOUR", "OPERATING_HOUR", "OPER_HOUR",
        "WORK_HOUR", "WORKING_HOUR", "RUN_HOUR", "IDLE", "DISTANCE",
        "PAYLOAD", "TONNAGE", "TONNES", "WMT", "CYCLE"]

WIDE_SQL = COL_SQL.format(
    where=" OR ".join(f"c.name LIKE '%{p}%'" for p in WIDE))

# Same, but over views too (sys.columns joins sys.tables above, so views are
# invisible to step 2 — that is a real gap in the requested queries).
VIEW_COL_SQL = """
SELECT s.name AS schema_name, v.name AS view_name, c.name AS column_name,
       ty.name AS data_type, c.max_length, c.is_nullable
FROM sys.columns c
JOIN sys.views v ON c.object_id = v.object_id
JOIN sys.schemas s ON v.schema_id = s.schema_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
WHERE {where}
ORDER BY s.name, v.name, c.column_id;
"""
VIEW_WIDE = VIEW_COL_SQL.format(
    where=" OR ".join(f"c.name LIKE '%{p}%'" for p in WIDE))

# Full text search of every module (views, procs, functions) for fuel words.
MODULE_SQL = """
SELECT s.name AS schema_name, o.name AS object_name, o.type_desc
FROM sys.sql_modules m
JOIN sys.objects o ON m.object_id = o.object_id
JOIN sys.schemas s ON o.schema_id = s.schema_id
WHERE m.definition LIKE '%FUEL%' OR m.definition LIKE '%DIESEL%'
   OR m.definition LIKE '%SOLAR%' OR m.definition LIKE '%BBM%'
   OR m.definition LIKE '%LITRE%' OR m.definition LIKE '%LITER%'
ORDER BY o.type_desc, s.name, o.name;
"""


def main():
    for db in DBS:
        print(f"=== {db} ===")
        res = {}
        for name, sql in {
            "wide_table_columns": WIDE_SQL,
            "wide_view_columns": VIEW_WIDE,
            "modules_mentioning_fuel": MODULE_SQL,
        }.items():
            cols, rows = q(db, sql)
            print(f"  {name}: {len(rows)} rows")
            res[name] = {"columns": cols, "rows": rows}
        save(f"phase2_{db}", res)


if __name__ == "__main__":
    main()
