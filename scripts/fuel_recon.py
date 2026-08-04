#!/usr/bin/env python3
"""Exhaustive fuel / equipment-hours / haulage reconnaissance across
WBN_DATABASE and FMS_DB.  Phase 1 = metadata.  Results cached to JSON so
re-analysis needs no VPN.

Usage:  python scripts/fuel_recon.py phase1
        python scripts/fuel_recon.py phase2
"""
import json
import os
import pathlib
import sys
import time

import pymssql

ENV = "/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "fuel_recon"
OUT.mkdir(parents=True, exist_ok=True)
DBS = ["WBN_DATABASE", "FMS_DB"]


def creds():
    c = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                c[k.strip()] = v.strip().strip('"').strip("'")
    return (
        os.environ.get("FMS_DB_HOST") or c.get("FMS_DB_HOST"),
        os.environ.get("FMS_DB_USER") or c.get("FMS_DB_USER"),
        os.environ.get("FMS_DB_PASS") or c.get("FMS_DB_PWD"),
    )


HOST, USER, PWD = creds()


def conn(db, tries=5):
    last = None
    for i in range(tries):
        try:
            return pymssql.connect(
                server=HOST, user=USER, password=PWD, database=db,
                charset="LATIN1", timeout=300, login_timeout=30,
            )
        except Exception as e:  # VPN flaps
            last = e
            time.sleep(3 * (i + 1))
    raise last


def q(db, sql, tries=4):
    """Run sql, return (columns, rows-as-lists)."""
    last = None
    for i in range(tries):
        cn = None
        try:
            cn = conn(db)
            cur = cn.cursor()
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [[stringify(v) for v in r] for r in cur.fetchall()]
            return cols, rows
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
        finally:
            if cn:
                try:
                    cn.close()
                except Exception:
                    pass
    return ["ERROR"], [[f"{type(last).__name__}: {last}"]]


def stringify(v):
    import datetime
    import decimal
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        return v.hex()[:200]
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (int, float, bool, str)):
        return v
    return str(v)


OBJ_BASE = """
SELECT s.name AS schema_name, o.name AS object_name, o.type_desc,
       CAST(ep.value AS NVARCHAR(MAX)) AS description
FROM sys.objects o
JOIN sys.schemas s ON o.schema_id = s.schema_id
LEFT JOIN sys.extended_properties ep
  ON ep.major_id = o.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
WHERE o.type IN ('U','V') {filt}
ORDER BY o.type_desc, s.name, o.name;
"""


def like(col, pats):
    return "AND (" + " OR ".join(f"{col} LIKE '%{p}%'" for p in pats) + ")"


STEP1 = ["FUEL", "DIESEL", "CONSUM", "ISSUE", "SAP", "LUBR", "FLUID", "TANK",
         "STOCK", "PURCHASE", "ORDER", "DELIVER", "PRICE", "COST"]
STEP5 = ["EQUIP", "TRUCK", "FLEET", "VEHICLE", "CONTRACTOR", "RIM", "STM", "PPP",
         "SMA", "HAUL", "TRIP", "WEIGH", "WEIGHBRIDGE", "DISTANCE", "ROUTE",
         "ROAD", "CORRIDOR", "GPS", "TRACK", "LOCATION", "POSITION", "POS",
         "MINE", "PIT", "DUMP", "LOAD", "SHIFT", "OPERATOR", "WORK", "HOUR",
         "ACTIVITY", "STATUS", "AVAIL", "MAINTEN", "BREAKDOWN"]
STEP8 = ["SAP", "TRANSFER", "MOVEMENT", "ISSUE", "RECEIPT", "GR", "GOODS",
         "MATERIAL", "INVENTORY", "WAREHOUSE", "STORE", "SUPPLY", "DISPENSE",
         "PUMP", "FILL"]
STEP10 = ["DISTANCE", "ROUTE", "ROAD", "CORRIDOR", "SEGMENT", "PATH", "KM",
          "MILEAGE", "ODOMETER"]

COL_SQL = """
SELECT s.name AS schema_name, t.name AS table_name, c.name AS column_name,
       ty.name AS data_type, c.max_length, c.is_nullable,
       CAST(ep.value AS NVARCHAR(MAX)) AS column_description
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.extended_properties ep
  ON ep.major_id = c.object_id AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
WHERE {where}
ORDER BY s.name, t.name, c.column_id;
"""

STEP2_PATS = ["FUEL", "DIESEL", "LITRE", "LITER", "CONSUM", "BURN", "ISSUE",
              "PRICE", "COST", "GALLON", "VOLUME", "QUANTITY", "L_PER", "LPH",
              "FUEL_RATE"]

STEP4_TABLES = ["EQUIPMENTS_HOURLY_STATUS", "EQUIPMENTS_HOURLY_ACTIVITIES",
                "EQUIPMENTS_STATUS", "FMS_EQUIPMENTS", "DAY_WORKS",
                "HAULAGE_IWIP_CLEAN", "FMS_PLAYBACK_TRACK_DATA",
                "FMS_CONGESTION_SEG"]

STEP9 = """
SELECT s.name AS schema_name, o.name AS view_name, m.definition AS view_sql
FROM sys.objects o
JOIN sys.schemas s ON o.schema_id = s.schema_id
JOIN sys.sql_modules m ON o.object_id = m.object_id
WHERE o.type = 'V' AND (
  m.definition LIKE '%FUEL%' OR m.definition LIKE '%DIESEL%'
  OR m.definition LIKE '%CONSUM%' OR m.definition LIKE '%LITRE%'
  OR m.definition LIKE '%LITER%' OR m.definition LIKE '%BURN%'
  OR m.definition LIKE '%ISSUE%' OR m.definition LIKE '%OPERATING_HOUR%'
  OR m.definition LIKE '%WORKING_HOUR%' OR m.definition LIKE '%AVAILABILITY%')
ORDER BY s.name, o.name;
"""

# Row counts for every user table, cheaply, from partition stats.
ROWCOUNT_SQL = """
SELECT s.name AS schema_name, t.name AS table_name,
       SUM(p.rows) AS approx_rows
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
GROUP BY s.name, t.name
ORDER BY SUM(p.rows) DESC;
"""


def save(name, payload):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(f"  saved {p.name}  ({len(json.dumps(payload, default=str))//1024} KB)")


def phase1():
    for db in DBS:
        print(f"=== {db} ===")
        res = {}
        jobs = {
            "step1_fuel_objects": OBJ_BASE.format(filt=like("o.name", STEP1)),
            "step3_all_objects": OBJ_BASE.format(filt=""),
            "step5_equip_objects": OBJ_BASE.format(filt=like("o.name", STEP5)),
            "step8_sap_objects": OBJ_BASE.format(filt=like("o.name", STEP8)),
            "step10_distance_objects": OBJ_BASE.format(filt=like("o.name", STEP10)),
            "step2_fuel_columns": COL_SQL.format(
                where=" OR ".join(f"c.name LIKE '%{p}%'" for p in STEP2_PATS)),
            "step4_key_table_schemas": COL_SQL.format(
                where="t.name IN (" + ",".join(f"'{t}'" for t in STEP4_TABLES) + ")"),
            "step9_view_defs": STEP9,
            "rowcounts": ROWCOUNT_SQL,
        }
        for name, sql in jobs.items():
            t0 = time.time()
            cols, rows = q(db, sql)
            print(f"  {name}: {len(rows)} rows  ({time.time()-t0:.1f}s)")
            res[name] = {"columns": cols, "rows": rows}
        save(f"phase1_{db}", res)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "phase1"
    if what == "phase1":
        phase1()
