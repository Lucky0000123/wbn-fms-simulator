"""scan_all_tables.py — exhaustive read-only pass over EVERY base table.

The first scan filtered to investigation keywords and deep-scanned 135 of 669
objects. The brief asks for every table, on the explicit grounds that a table
that looks irrelevant may hold exactly what is needed. This pass drops the
filter entirely.

Scope: all 215 base tables (161 WBN_DATABASE + 54 FMS_DB) get row count, full
column list, 5 sample rows, date range and ID vocabularies. Views are
catalogued for columns but not sampled — every view here is defined over base
tables already covered, so sampling them re-reads the same data at extra cost.

READ ONLY. SELECT and INFORMATION_SCHEMA only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

RAW = os.path.join(ROOT, "reports", "schema_full_raw.json")
DBS = ("WBN_DATABASE", "FMS_DB")

SAMPLE_ROWS = 5
DISTINCT_IDS = 20
PER_TABLE_TIMEOUT = 90

DATE_HINT = re.compile(r"DATE|TIME|_AT$|^TS$|STAMP", re.I)
ID_HINT = re.compile(r"EQUIPMENT|TRUCK|UNIT|VEHICLE|PLATE|DEVICE|ASSET|MACHINE|"
                     r"OPERATOR|DRIVER|EXCAV|LOADER|_ID$|^ID$|CODE|SEG", re.I)
COORD_HINT = re.compile(r"^LAT|^LNG|^LON|^X$|^Y$|EAST|NORTH", re.I)
# Wide tables blow up the report; cap sampled columns but always list all names.
MAX_SAMPLE_COLS = 14


def connect(db: str):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=PER_TABLE_TIMEOUT,
                           charset="LATIN1")


def esc(n: str) -> str:
    return "[" + n.replace("]", "]]") + "]"


def safe(conn, sql):
    try:
        return pd.read_sql(sql, conn), None
    except Exception as e:                                   # noqa: BLE001
        return None, str(e)[:160]


def scan_table(conn, t: str, cols: list) -> dict:
    rec: dict = {}
    names = [c["name"] for c in cols]

    d, err = safe(conn, "SELECT TOP %d * FROM %s" % (SAMPLE_ROWS, esc(t)))
    if d is not None:
        keep = names[:MAX_SAMPLE_COLS]
        try:
            rec["sample"] = json.loads(
                d[keep].to_json(orient="records", date_format="iso",
                                default_handler=str))
        except Exception:                                    # noqa: BLE001
            rec["sample_error"] = "could not serialise"
        rec["sample_columns_shown"] = len(keep)
    else:
        rec["sample_error"] = err

    dcols = [c["name"] for c in cols
             if DATE_HINT.search(c["name"])
             and c["type"] in ("date", "datetime", "datetime2", "smalldatetime")]
    if dcols:
        d, err = safe(conn, "SELECT MIN(%s) lo, MAX(%s) hi FROM %s"
                      % (esc(dcols[0]), esc(dcols[0]), esc(t)))
        if d is not None and not d.empty and pd.notna(d.lo[0]):
            rec["date_column"] = dcols[0]
            rec["date_range"] = [str(d.lo[0]), str(d.hi[0])]

    for c in cols:
        if not ID_HINT.search(c["name"]):
            continue
        if c["type"] not in ("nvarchar", "varchar", "char", "nchar"):
            continue
        d, err = safe(conn,
                      "SELECT DISTINCT TOP %d %s v FROM %s WHERE %s IS NOT NULL"
                      % (DISTINCT_IDS, esc(c["name"]), esc(t), esc(c["name"])))
        if d is None or d.empty:
            continue
        n, _ = safe(conn, "SELECT COUNT(DISTINCT %s) n FROM %s"
                    % (esc(c["name"]), esc(t)))
        rec.setdefault("id_columns", {})[c["name"]] = {
            "distinct": (int(n.n[0]) if n is not None and not n.empty else None),
            "examples": [str(x)[:40] for x in d.v.tolist()],
        }

    cc = [c["name"] for c in cols if COORD_HINT.search(c["name"])
          and c["type"] in ("float", "real", "decimal", "numeric")]
    if cc:
        sel = ", ".join("MIN(%s) a%d, MAX(%s) b%d" % (esc(c), i, esc(c), i)
                        for i, c in enumerate(cc[:4]))
        d, _ = safe(conn, "SELECT %s FROM %s" % (sel, esc(t)))
        if d is not None and not d.empty:
            rec["coordinate_extent"] = {
                cc[i]: [d["a%d" % i][0], d["b%d" % i][0]]
                for i in range(min(len(cc), 4))}
    return rec


def scan_db(db: str) -> dict:
    print("\n=== %s ===" % db, flush=True)
    conn = connect(db)
    out = {"database": db, "objects": {}, "errors": []}
    objs = pd.read_sql("SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
                       "ORDER BY TABLE_TYPE, TABLE_NAME", conn)
    cols = pd.read_sql("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, "
                       "CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
                       "FROM INFORMATION_SCHEMA.COLUMNS "
                       "ORDER BY TABLE_NAME, ORDINAL_POSITION", conn)
    rc = pd.read_sql("""
        SELECT t.name tbl, SUM(p.row_count) n
        FROM sys.dm_db_partition_stats p
        JOIN sys.tables t ON t.object_id = p.object_id
        WHERE p.index_id IN (0,1) GROUP BY t.name""", conn)
    counts = {r.tbl: int(r.n) for r in rc.itertuples()}
    by = {k: g for k, g in cols.groupby("TABLE_NAME")}

    out["object_count"] = len(objs)
    out["table_count"] = int((objs.TABLE_TYPE == "BASE TABLE").sum())
    out["view_count"] = int((objs.TABLE_TYPE == "VIEW").sum())
    tables = [r.TABLE_NAME for r in objs.itertuples() if r.TABLE_TYPE == "BASE TABLE"]
    print("%d objects; sampling all %d base tables" % (len(objs), len(tables)),
          flush=True)

    t0 = time.time()
    for i, r in enumerate(objs.itertuples()):
        t = r.TABLE_NAME
        g = by.get(t)
        rec = {"type": r.TABLE_TYPE,
               "columns": ([] if g is None else
                           [{"name": x.COLUMN_NAME, "type": x.DATA_TYPE,
                             "len": (None if pd.isna(x.CHARACTER_MAXIMUM_LENGTH)
                                     else int(x.CHARACTER_MAXIMUM_LENGTH)),
                             "nullable": x.IS_NULLABLE} for x in g.itertuples()])}
        if r.TABLE_TYPE == "BASE TABLE":
            rec["row_count"] = counts.get(t)
            if (rec["row_count"] or 0) > 0:
                try:
                    rec.update(scan_table(conn, t, rec["columns"]))
                    rec["depth"] = "sampled"
                except Exception as e:                       # noqa: BLE001
                    rec["depth"] = "error"
                    out["errors"].append("%s: %s" % (t, str(e)[:110]))
                    try:
                        conn.close()
                    except Exception:                        # noqa: BLE001
                        pass
                    conn = connect(db)
            else:
                rec["depth"] = "empty"
        else:
            rec["depth"] = "view (columns only)"
        out["objects"][t] = rec
        if i % 25 == 0:
            print("   [%3d/%3d] %-42s %.0fs"
                  % (i, len(objs), t[:42], time.time() - t0), flush=True)
    conn.close()
    print("   done in %.0fs, %d errors" % (time.time() - t0, len(out["errors"])),
          flush=True)
    return out


def main() -> None:
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    all_out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "databases": {}}
    for db in DBS:
        try:
            all_out["databases"][db] = scan_db(db)
        except Exception as e:                               # noqa: BLE001
            print("%s FATAL %s" % (db, e), flush=True)
            all_out["databases"][db] = {"database": db, "fatal_error": str(e)}
    with open(RAW, "w", encoding="utf-8") as fh:
        json.dump(all_out, fh, indent=1, default=str)
    print("\nwrote %s" % RAW)


if __name__ == "__main__":
    main()
