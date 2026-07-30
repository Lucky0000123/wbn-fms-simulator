"""scan_databases.py — read-only full inventory of WBN_DATABASE and FMS_DB.

WHY THIS EXISTS
The simulator currently publishes "0 of 940 haul trucks appear in the GPS feed"
and concludes segment-level speed is unavailable. The site operator says that
reasoning is wrong: "logistik" is a CONTRACTOR under IWIP, not a vehicle class,
so filtering haul trucks out by department name may have discarded exactly the
vehicles we needed.

That claim is testable, and it is worth testing properly, because if the
operator is right the simulator is understating what the data supports.

READ ONLY. This opens connections, runs SELECT and INFORMATION_SCHEMA queries,
and writes one markdown report. It creates no tables, alters nothing, and takes
no locks beyond a read.

SCALE FORCES A TWO-TIER APPROACH
There are 669 objects across the two databases (579 + 90). Pulling 5 sample
rows and a row count from every one would take hours and bury the answer.
So every object gets its columns catalogued, and objects matching the
investigation's keywords get the full treatment: row count, date range, samples
and ID formats. The tier each table received is recorded, so nothing looks
examined when it was only listed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import simulator_api as sim                                  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "reports", "database_schema_analysis.md")
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "reports", "database_schema_raw.json")
DBS = ("WBN_DATABASE", "FMS_DB")

# Tables matching these get deep-scanned. Drawn from the questions asked:
# GPS/telematics, road segments, HRM, queue/wait, operator and loader identity.
DEEP = re.compile(
    r"GPS|TRACK|PLAYBACK|GEOFENC|CONGEST|SEGMENT|SEG\b|KM_|_KM|KILOMET|"
    r"HAUL_ROAD|ROAD|STA\b|CYCLE|ASSIGN|DISPATCH|EQUIPMENT|TRUCK|VEHICLE|"
    r"HRM|GRADER|MAINTEN|INSPECT|ROADWORK|WAIT|QUEUE|SPEED|ZONE|EMPLOYEE|"
    r"DRIVER|OPERATOR|SHIFT|ROSTER|EXCAV|LOADER|SHOVEL|ENTRY_EXIT|STAY|"
    r"HAULAGE_IWIP|UNIT_INSTALLED|LV_|MOVEMENT|VISIT", re.I)

DATE_HINT = re.compile(r"DATE|TIME|_AT$|^TS$|STAMP", re.I)
ID_HINT = re.compile(r"EQUIPMENT|TRUCK|UNIT|VEHICLE|PLATE|DEVICE|ASSET|"
                     r"MACHINE|DT_|^ID$|_ID$", re.I)
COORD_HINT = re.compile(r"LAT|LON|LNG|^X$|^Y$|EAST|NORTH|COORD", re.I)

SAMPLE_ROWS = 5
DISTINCT_IDS = 20
BUDGET_S = 1500          # stop deep-scanning before the session stalls


def _connect(db: str):
    """Open a read-only connection that survives the site's mixed encodings.

    The default charset raises "Unsupported UTF-8 sequence length" on this
    server: several tables hold Chinese text (IS_COMPLETED is 已完成, and
    equipment departments are 工程/后勤) stored under a non-UTF8 collation.
    Latin-1 never rejects a byte, so the scan completes; any text that is
    genuinely multi-byte comes back mojibake rather than killing the run,
    which is the right trade for an inventory whose job is to find tables.
    """
    import pymssql
    return pymssql.connect(
        server=sim._DB["server"], user=sim._DB["user"],
        password=sim._DB["password"], database=db,
        login_timeout=10, timeout=120, charset="LATIN1")


def q(conn, sql, timeout_note=""):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:                                   # noqa: BLE001
        return "ERROR: %s%s" % (str(e)[:150], timeout_note)


def esc(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def scan_db(db: str, deadline: float) -> dict:
    print("\n=== %s ===" % db, flush=True)
    conn = _connect(db)
    out: dict = {"database": db, "objects": {}, "errors": []}
    try:
        objs = pd.read_sql(
            "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
            "ORDER BY TABLE_TYPE, TABLE_NAME", conn)
        cols = pd.read_sql(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, "
            "CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE, ORDINAL_POSITION "
            "FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_NAME, ORDINAL_POSITION",
            conn)
        out["object_count"] = int(len(objs))
        out["table_count"] = int((objs.TABLE_TYPE == "BASE TABLE").sum())
        out["view_count"] = int((objs.TABLE_TYPE == "VIEW").sum())
        by_tbl = {k: g for k, g in cols.groupby("TABLE_NAME")}

        deep_list = [r.TABLE_NAME for r in objs.itertuples()
                     if DEEP.search(r.TABLE_NAME)]
        print("%d objects, %d match the investigation keywords"
              % (len(objs), len(deep_list)), flush=True)

        for i, r in enumerate(objs.itertuples()):
            t = r.TABLE_NAME
            c = by_tbl.get(t)
            rec = {
                "type": r.TABLE_TYPE,
                "columns": ([] if c is None else
                            [{"name": x.COLUMN_NAME, "type": x.DATA_TYPE,
                              "len": (None if pd.isna(x.CHARACTER_MAXIMUM_LENGTH)
                                      else int(x.CHARACTER_MAXIMUM_LENGTH)),
                              "nullable": x.IS_NULLABLE} for x in c.itertuples()]),
                "depth": "catalogued",
            }
            deep = DEEP.search(t) is not None
            if deep and time.time() < deadline:
                # Isolate per table: a single row with an undecodable byte
                # must not cost us the other 668 objects.
                try:
                    rec.update(deep_scan(conn, t, rec["columns"]))
                    rec["depth"] = "deep"
                except Exception as e:                       # noqa: BLE001
                    rec["depth"] = "deep scan failed"
                    rec["scan_error"] = str(e)[:200]
                    out["errors"].append("%s: %s" % (t, str(e)[:120]))
                    try:
                        conn.close()
                    except Exception:                        # noqa: BLE001
                        pass
                    conn = _connect(db)
                if i % 10 == 0:
                    print("   [%3d/%3d] %s" % (i, len(objs), t), flush=True)
            elif deep:
                rec["depth"] = "keyword match, budget exhausted"
            out["objects"][t] = rec
    finally:
        conn.close()
    return out


def deep_scan(conn, table: str, columns: list) -> dict:
    """Row count, date range, samples, and ID/coordinate shape for one table."""
    rec: dict = {}
    n = q(conn, "SELECT COUNT(*) AS n FROM %s" % esc(table))
    if isinstance(n, str):
        rec["row_count_error"] = n
        return rec
    rows = int(n.iloc[0, 0])
    rec["row_count"] = rows
    if rows == 0:
        return rec

    names = [c["name"] for c in columns]
    dcols = [c["name"] for c in columns
             if DATE_HINT.search(c["name"])
             and c["type"] in ("date", "datetime", "datetime2", "smalldatetime")]
    if dcols:
        d = dcols[0]
        rng = q(conn, "SELECT MIN(%s) AS lo, MAX(%s) AS hi FROM %s"
                % (esc(d), esc(d), esc(table)))
        if not isinstance(rng, str):
            rec["date_column"] = d
            rec["date_range"] = [str(rng.lo[0]), str(rng.hi[0])]

    smp = q(conn, "SELECT TOP %d * FROM %s" % (SAMPLE_ROWS, esc(table)))
    if not isinstance(smp, str):
        rec["sample"] = json.loads(
            smp.head(SAMPLE_ROWS).to_json(orient="records", date_format="iso",
                                          default_handler=str))

    # ID vocabulary — the heart of the namespace question.
    for c in columns:
        if not ID_HINT.search(c["name"]) or c["type"] not in (
                "nvarchar", "varchar", "char", "nchar"):
            continue
        v = q(conn, "SELECT DISTINCT TOP %d %s AS v FROM %s "
                    "WHERE %s IS NOT NULL ORDER BY %s"
              % (DISTINCT_IDS, esc(c["name"]), esc(table),
                 esc(c["name"]), esc(c["name"])))
        if isinstance(v, str) or v.empty:
            continue
        cnt = q(conn, "SELECT COUNT(DISTINCT %s) AS n FROM %s"
                % (esc(c["name"]), esc(table)))
        rec.setdefault("id_columns", {})[c["name"]] = {
            "distinct": (int(cnt.iloc[0, 0]) if not isinstance(cnt, str) else None),
            "examples": [str(x) for x in v.v.tolist()],
        }

    # Coordinate extent — needed to test whether GPS reaches the haul zones.
    ccols = [c["name"] for c in columns
             if COORD_HINT.search(c["name"])
             and c["type"] in ("float", "real", "decimal", "numeric")]
    if ccols:
        sel = ", ".join("MIN(%s) AS min_%d, MAX(%s) AS max_%d"
                        % (esc(c), i, esc(c), i) for i, c in enumerate(ccols[:4]))
        ext = q(conn, "SELECT %s FROM %s" % (sel, esc(table)))
        if not isinstance(ext, str):
            rec["coordinate_extent"] = {
                ccols[i]: [ext["min_%d" % i][0], ext["max_%d" % i][0]]
                for i in range(min(len(ccols), 4))}
    return rec


def main() -> None:
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    t0 = time.time()
    all_out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "databases": {}}
    for db in DBS:
        try:
            all_out["databases"][db] = scan_db(db, t0 + BUDGET_S)
        except Exception as e:                               # noqa: BLE001
            print("%s FAILED: %s" % (db, e), flush=True)
            all_out["databases"][db] = {"database": db, "fatal_error": str(e)}
    with open(RAW, "w", encoding="utf-8") as fh:
        json.dump(all_out, fh, indent=1, default=str)
    print("\nwrote %s in %.0fs" % (RAW, time.time() - t0))


if __name__ == "__main__":
    main()
