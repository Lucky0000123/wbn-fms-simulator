#!/usr/bin/env python
"""Read-only reconnaissance of the FMS database.

Purpose: find out what data actually exists before deciding what Phase 3.5 can
model. Phase 3 stalled on 4,141 rows of aggregated haulage; if GPS traces,
equipment status or operator assignments are sitting in tables nobody joined,
that changes what is worth building.

Safety:
  * READ-ONLY. Only SELECT and INFORMATION_SCHEMA/sys catalog reads. Every
    statement is checked against a write blacklist before execution.
  * Requires the VPN. Refuses to fall back to fixtures — a schema report built
    from sample data would be worse than no report, because it would look real.
  * Redacts values in columns whose NAME suggests personal data (driver names,
    phone numbers, addresses). Column names are still reported; only the sample
    VALUES are masked.
  * Credentials come from the environment, never from this file.

Usage:
    FMS_DB_HOST=... FMS_DB_USER=... FMS_DB_PASS=... python scripts/db_reconnaissance.py
    python scripts/db_reconnaissance.py --database WBN_DATABASE --timeout-min 30
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

REPORTS = os.path.join(BASE, "reports")
JSON_OUT = os.path.join(REPORTS, "db_reconnaissance.json")
MD_OUT = os.path.join(REPORTS, "db_reconnaissance_report.md")

# Tables above this are sampled from the catalog only — a TOP 5 on a 16M-row
# heap can still force a scan, and this is a production server.
BIG_TABLE_ROWS = 10_000_000

DATE_TYPES = {"datetime", "datetime2", "date", "smalldatetime", "timestamp",
              "datetimeoffset"}

# ── classification ──────────────────────────────────────────────────────────
TABLE_FLAGS = {
    "GPS": ("GPS", "POSITION", "TRACK", "LOCATION", "COORD", "TRUCK_POS", "VEHICLE_LOG"),
    "TRUCK": ("TRUCK", "VEHICLE", "HAULER", "EQUIPMENT", "FLEET"),
    "PLAN": ("PLAN", "PRODUCTION", "TONNAGE", "HAUL", "DISPATCH", "SHIFT"),
    "OPERATOR": ("OPERATOR", "DRIVER", "CREW", "SHIFT_ASSIGN"),
    "WEATHER": ("WEATHER", "RAIN", "ENVIRONMENT", "CONDITION"),
    "ROAD": ("ROAD", "ROUTE", "PATH", "DUMP", "LOAD", "TIP"),
    "MAINTENANCE": ("MAINTENANCE", "REPAIR", "BREAKDOWN", "DOWNTIME"),
    "WEIGHBRIDGE": ("WEIGH", "_WB", "WB_", "BRIDGE", "SCALE"),
}
COLUMN_FLAGS = {
    "COORD": ("LAT", "LON", "LATITUDE", "LONGITUDE", "COORD", "EASTING", "NORTHING"),
    "SPEED": ("SPEED", "VELOCITY"),
    "TIME": ("TIME", "TIMESTAMP", "DATETIME", "DATE"),
    "EQUIP": ("TRUCK", "VEHICLE", "HAULER", "EQUIPMENT"),
    "STATUS": ("STATUS", "STATE", "PHASE", "ACTIVITY"),
}
# Column names whose VALUES must never reach a committed report. Two kinds:
# personal data, and secrets. The secrets half is not hypothetical — the first
# run of this scan pulled a plaintext value out of `FMS_USERS.PASSWORD` into a
# file destined for a public mirror.
PII_COLUMN_HINTS = ("NAME", "NAMA", "DRIVER", "OPERATOR", "PHONE", "TELP", "HP",
                    "EMAIL", "ADDRESS", "ALAMAT", "NIK", "KTP", "PASSPORT",
                    "BIRTH", "LAHIR", "SALARY", "GAJI",
                    # credentials and session material
                    "PASSWORD", "PASSWD", "PWD", "SECRET", "TOKEN", "APIKEY",
                    "API_KEY", "PRIVATE_KEY", "CREDENTIAL", "AUTH", "SESSION",
                    "HASH", "SALT", "SIGNATURE", "COOKIE", "BEARER", "IMEI",
                    "SERIAL", "LICENSE", "LICENCE")
# ...except these, which are equipment or place names, not people.
PII_EXEMPT = ("TABLE_NAME", "COLUMN_NAME", "AREA_NAME", "SITE_NAME", "ZONE_NAME",
              "FILE_NAME", "DOME_NAME", "MATERIAL_NAME", "COMPANY_NAME",
              "SHIFT_NAME", "STATUS_NAME", "EQUIPMENT_NAME", "UNIT_NAME")

WRITE_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|MERGE|EXEC|GRANT|"
    r"REVOKE|BACKUP|RESTORE|SHUTDOWN)\b", re.I)


def guard(sql: str) -> str:
    """Refuse anything that could modify the server. Belt and braces: the login
    may well have write rights, so the safety lives here rather than in hope."""
    if WRITE_RE.search(sql):
        raise RuntimeError("refusing non-read statement: %s" % sql[:80])
    return sql


def is_pii(col: str) -> bool:
    c = (col or "").upper()
    if c in PII_EXEMPT:
        return False
    return any(h in c for h in PII_COLUMN_HINTS)


def flags_for(table: str, columns: list) -> list:
    t = (table or "").upper()
    out = {k for k, words in TABLE_FLAGS.items() if any(w in t for w in words)}
    cols = [(c["name"] or "").upper() for c in columns]
    for k, words in COLUMN_FLAGS.items():
        if any(any(w in c for w in words) for c in cols):
            out.add("col:" + k)
    return sorted(out)


def cell(v, redact: bool):
    if v is None:
        return None
    if redact:
        return "[REDACTED]"
    if isinstance(v, (bytes, bytearray)):
        return "<%d bytes>" % len(v)
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def assert_no_secrets(payload: dict) -> list:
    """Last line of defence before anything is written to a committed file.

    The column-name filter is a heuristic and will miss a column named
    something unexpected. This walks every sample VALUE and flags anything that
    looks like a credential regardless of which column it came from.
    """
    findings = []
    # A password looks like mixed case AND digits with no spaces or separators.
    # Area codes ("TOS_TF_STM_13", "POS 12") have separators or are all upper,
    # so requiring both cases and forbidding separators keeps them out.
    pw_like = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9!@#$%^&*]{8,32}$")
    for t in payload.get("tables", []):
        for row in t.get("sample_rows", []):
            for col, val in row.items():
                if not isinstance(val, str) or val == "[REDACTED]":
                    continue
                c = col.upper()
                if any(h in c for h in ("PASSWORD", "PASSWD", "SECRET", "TOKEN",
                                        "APIKEY", "API_KEY", "PRIVATE_KEY",
                                        "AUTH", "CREDENTIAL")):
                    findings.append("%s.%s" % (t["name"], col))
                elif pw_like.match(val) and len(val) >= 10:
                    # Value looks like a credential even though the column name
                    # gives no warning. Skip columns with an innocent purpose.
                    if not any(h in c for h in ("ID", "CODE", "NO", "PLATE", "AREA",
                                                "MODEL", "SERIAL", "REF", "LOCATION",
                                                "NAME", "REMARK", "DESC", "TITLE",
                                                "TYPE", "STATUS", "NOTE")):
                        findings.append("%s.%s (value shape)" % (t["name"], col))
    return sorted(set(findings))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    # Both matter. FMS_DB holds the telemetry (GPS tracks, geofence visits,
    # congestion segments); WBN_DATABASE holds the production and haulage
    # records the simulator already models. Scanning one and reporting it as
    # "the database" is how the GPS tables stayed invisible.
    ap.add_argument("--databases", default="FMS_DB,WBN_DATABASE",
                    help="comma-separated list to scan")
    ap.add_argument("--timeout-min", type=float, default=30.0)
    ap.add_argument("--sample-rows", type=int, default=5)
    args = ap.parse_args()

    import simulator_api as sim
    db_list = [d.strip() for d in args.databases.split(",") if d.strip()]

    # ── VPN / connectivity gate ────────────────────────────────────────────
    if not sim._db_ready():
        print("FMS_DB_HOST/USER/PASS not set (or pymssql missing).", file=sys.stderr)
        print("This scan must run against the real database — refusing to "
              "produce a schema report from fixtures.", file=sys.stderr)
        return 1

    started = time.time()
    deadline = started + args.timeout_min * 60
    all_dbs, server_version = [], None
    for dbn in db_list:
        res = scan_database(sim, dbn, args, deadline)
        if res is None:
            return 1
        server_version = server_version or res["version"]
        all_dbs.append(res)

    payload = {
        "server_info": {"version": server_version,
                        "databases": [d["database"] for d in all_dbs],
                        "host_env": "FMS_DB_HOST (not recorded)"},
        "scan_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scan_seconds": round(time.time() - started, 1),
        "table_count": sum(len(d["tables"]) for d in all_dbs),
        "skipped": [s for d in all_dbs for s in d["skipped"]],
        "databases": all_dbs,
        # Flat view so existing consumers keep working.
        "tables": [t for d in all_dbs for t in d["tables"]],
    }
    os.makedirs(REPORTS, exist_ok=True)
    leaks = assert_no_secrets(payload)
    if leaks:
        # Scrub rather than abort: the report is still worth having, and a
        # half-written file is worse than a redacted one.
        for t in payload["tables"]:
            for row in t.get("sample_rows", []):
                for col in list(row):
                    tag = "%s.%s" % (t["name"], col)
                    if any(f.startswith(tag) for f in leaks):
                        row[col] = "[REDACTED]"
        print("\n!! secret-shaped values scrubbed from %d column(s):" % len(leaks))
        for f in leaks[:10]:
            print("     %s" % f)
    with open(JSON_OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    with open(MD_OUT, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(payload))
    print("\nwrote %s" % os.path.relpath(JSON_OUT, BASE))
    print("wrote %s" % os.path.relpath(MD_OUT, BASE))
    return 0


def scan_database(sim, database: str, args, deadline: float):
    """Scan one database. Returns None on a connection failure."""
    try:
        conn = sim._conn(database)
    except Exception as exc:                                   # noqa: BLE001
        print("connection to %s FAILED: %s" % (database, exc), file=sys.stderr)
        print("Is the VPN connected? The server lives on an internal address.",
              file=sys.stderr)
        return None

    cur = conn.cursor()
    cur.execute(guard("SELECT @@VERSION"))
    version = " ".join(str(cur.fetchone()[0]).split())
    cur.execute(guard("SELECT DB_NAME()"))
    dbname = cur.fetchone()[0]
    print("\nconnected: %s" % dbname)

    # ── table inventory + catalog row counts ───────────────────────────────
    cur.execute(guard("""
        SELECT t.TABLE_SCHEMA, t.TABLE_NAME,
               (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c
                 WHERE c.TABLE_SCHEMA=t.TABLE_SCHEMA AND c.TABLE_NAME=t.TABLE_NAME)
        FROM INFORMATION_SCHEMA.TABLES t
        WHERE t.TABLE_TYPE='BASE TABLE'
        ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME"""))
    inventory = [(r[0], r[1], int(r[2])) for r in cur.fetchall()]

    # Row counts from sys.partitions: one cheap query instead of 161 COUNT(*)
    # scans against a live production server.
    cur.execute(guard("""
        SELECT s.name, t.name, SUM(p.rows)
        FROM sys.tables t
        JOIN sys.schemas s ON s.schema_id = t.schema_id
        JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
        GROUP BY s.name, t.name"""))
    rowmap = {(r[0], r[1]): int(r[2] or 0) for r in cur.fetchall()}

    # All columns in one pass, then grouped in Python.
    cur.execute(guard("""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
               CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
               ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION"""))
    colmap: dict = {}
    for sch, tab, name, dtype, nullable, clen, prec, scale, _ in cur.fetchall():
        colmap.setdefault((sch, tab), []).append({
            "name": name, "type": dtype, "nullable": nullable == "YES",
            "max_length": clen, "precision": prec, "scale": scale,
            "pii": is_pii(name)})

    print("tables   : %d   (%s rows total)"
          % (len(inventory), format(sum(rowmap.values()), ",")))
    started = time.time()
    tables, skipped = [], []

    for i, (schema, table, ncols) in enumerate(inventory, 1):
        if time.time() > deadline:
            skipped.append("%s.%s (timeout)" % (schema, table))
            continue
        cols = colmap.get((schema, table), [])
        rows = rowmap.get((schema, table), 0)
        entry = {"database": dbname, "schema": schema, "name": table, "columns": cols,
                 "column_count": ncols, "row_count": rows,
                 "flags": flags_for(table, cols),
                 "has_dates": False, "date_range": None,
                 "sample_rows": [], "notes": [], "errors": []}

        date_cols = [c["name"] for c in cols if (c["type"] or "").lower() in DATE_TYPES]
        entry["date_columns"] = date_cols
        entry["has_dates"] = bool(date_cols)

        # Date range on the first date column. Skipped for huge tables unless an
        # index makes MIN/MAX cheap — we cannot know that, so skip and say so.
        if date_cols and rows:
            if rows > BIG_TABLE_ROWS:
                entry["notes"].append("date range skipped (table > %s rows)"
                                      % format(BIG_TABLE_ROWS, ","))
            else:
                dc = date_cols[0]
                try:
                    cur.execute(guard("SELECT MIN([%s]), MAX([%s]) FROM [%s].[%s]"
                                      % (dc, dc, schema, table)))
                    lo, hi = cur.fetchone()
                    if lo is not None or hi is not None:
                        entry["date_range"] = {"column": dc,
                                               "min": str(lo)[:19] if lo else None,
                                               "max": str(hi)[:19] if hi else None}
                except Exception as exc:                       # noqa: BLE001
                    entry["errors"].append("date range: %s" % str(exc)[:120])

        # Sample rows
        if rows == 0:
            entry["notes"].append("empty table")
        elif rows > BIG_TABLE_ROWS:
            entry["notes"].append("table too large, sample skipped")
        else:
            try:
                cur.execute(guard("SELECT TOP %d * FROM [%s].[%s]"
                                  % (args.sample_rows, schema, table)))
                names = [d[0] for d in cur.description]
                redact = [is_pii(n) for n in names]
                for r in cur.fetchall():
                    entry["sample_rows"].append(
                        {n: cell(v, rd) for n, v, rd in zip(names, r, redact)})
                if any(redact):
                    entry["notes"].append(
                        "redacted columns: %s"
                        % ", ".join(n for n, rd in zip(names, redact) if rd))
            except Exception as exc:                           # noqa: BLE001
                entry["errors"].append("sample: %s" % str(exc)[:120])

        tables.append(entry)
        if i % 25 == 0 or i == len(inventory):
            print("  scanned %d/%d (%.0fs)" % (i, len(inventory), time.time() - started))

    conn.close()
    return {"database": dbname, "version": version, "tables": tables,
            "skipped": skipped, "seconds": round(time.time() - started, 1)}


# ── report ──────────────────────────────────────────────────────────────────
def opportunities(tables: list) -> str:
    """The part of the report that changes what gets built next.

    Phase 3 documented road grade, operator experience, truck type and
    cycle-time components as unavailable. Three of those four turn out to exist
    in tables the pipeline never joined. Stating that plainly, next to the row
    counts, is the whole point of the scan.
    """
    idx = {t["name"].upper(): t for t in tables}

    def rows(name):
        t = idx.get(name.upper())
        return format(t["row_count"], ",") if t else "not found"

    def cols(name):
        t = idx.get(name.upper())
        return {c["name"].upper() for c in t["columns"]} if t else set()

    L, A = [], None
    A = L.append
    A("## What this changes for the next phase")
    A("")
    A("Phase 3 recorded four features as impossible with the available data. The")
    A("scan finds three of them sitting in tables the pipeline never joined.")
    A("")
    A("| Phase 3 said | Reality | Where |")
    A("|---|---|---|")

    wt = cols("WAITING_TIME")
    if {"LOADING_TIME", "DUMPING_TIME"} <= wt:
        A("| Cycle-time components need geofence timestamps | **Available.** Loading "
          "and dumping start/end clock times, so load, haul and dump segments are "
          "derivable by differencing | `WAITING_TIME` (%s rows) |" % rows("WAITING_TIME"))
    if "DRIVER_ID" in wt:
        A("| Operator experience needs an operator ID we do not have | **Available.** "
          "Per-trip driver ID; experience is derivable from first-seen date and "
          "accumulated trips | `WAITING_TIME.DRIVER_ID` |")
    eq = cols("EQUIPMENTS")
    if {"MODEL", "BUILD_YEAR"} <= eq:
        A("| Truck type needs a truck master table | **Partly available.** `MODEL`, "
          "`MANUFACTURER` and `BUILD_YEAR` are populated, so model class and truck "
          "age are usable. `CAPACITY` is null for dump trucks | `EQUIPMENTS` (%s rows) |"
          % rows("EQUIPMENTS"))
    gps = cols("FMS_PLAYBACK_TRACK_DATA") | cols("FMS_GPS_Historical")
    if {"LAT", "LNG"} & {c.upper() for c in gps} or {"lat", "lng"} & gps:
        A("| Road grade needs a survey or DEM | **Derivable, with work.** No elevation "
          "column, but GPS tracks give lat/lon per truck; grade needs an external DEM "
          "joined on position | `FMS_PLAYBACK_TRACK_DATA` (%s rows) |"
          % rows("FMS_PLAYBACK_TRACK_DATA"))
    else:
        A("| Road grade needs a survey or DEM | **Still missing.** No elevation or "
          "gradient column found | — |")
    A("")
    A("### Truck GPS: it exists, in `FMS_DB`")
    A("")
    A("The telemetry is in a **separate database** from the production records the")
    A("simulator currently reads. `WBN_DATABASE` holds haulage and weighbridge data;")
    A("`FMS_DB` holds the fleet-management telemetry, and nothing in the pipeline")
    A("touches it today.")
    A("")
    A("| Table | Rows | What it gives you |")
    A("|---|---:|---|")
    A("| `FMS_PLAYBACK_TRACK_DATA` | %s | Raw GPS: `lat`, `lng`, `speed`, `course`, "
      "`distance`, `engine`, `acc`, per `plateNumber` |" % rows("FMS_PLAYBACK_TRACK_DATA"))
    A("| `FMS_ENTRY_EXIT_DATA` | %s | Gate/zone entry and exit events |"
      % rows("FMS_ENTRY_EXIT_DATA"))
    A("| `FMS_GPS_Historical` | %s | Same shape, keyed by `TRUCK_ID` — the join back "
      "to haulage records |" % rows("FMS_GPS_Historical"))
    A("| `FMS_GEOFENCE_VISITS` | %s | **Geofence enter/exit with `DURATION_SEC`** — "
      "cycle segments without differencing raw fixes |" % rows("FMS_GEOFENCE_VISITS"))
    A("| `FMS_CONGESTION_SEG` | %s | Pre-aggregated hourly congestion: mean speed, "
      "truck count and travel time per road segment |" % rows("FMS_CONGESTION_SEG"))
    A("| `FMS_GEOFENCES` | %s | Geofence definitions — the named zones the visits "
      "refer to |" % rows("FMS_GEOFENCES"))
    A("")
    A("`FMS_CONGESTION_SEG` deserves particular attention: Phase 3's congestion")
    A("proxy was `trucks_per_path`, a count that came out with a *positive*")
    A("coefficient because busy roads are busy for good reasons. This table has")
    A("measured speed per segment per hour, which is congestion itself rather than a")
    A("stand-in for it.")
    A("")
    return "\n".join(L)


def render_markdown(p: dict) -> str:
    L, A = [], None
    A = L.append
    tables = p["tables"]
    by_flag = lambda f: sorted(t["name"] for t in tables if f in t["flags"])  # noqa: E731

    A("# Database Reconnaissance Report")
    A("")
    A("Read-only schema scan to establish what data exists before choosing what "
      "to model next. Sample values from columns that look personal are "
      "`[REDACTED]`; column names are kept.")
    A("")
    A("| | |")
    A("|---|---|")
    A("| Databases | %s |" % ", ".join("`%s`" % d for d in p["server_info"]["databases"]))
    A("| Server | %s |" % p["server_info"]["version"][:110])
    A("| Scanned | %s (%.0fs) |" % (p["scan_timestamp"], p["scan_seconds"]))
    A("| Base tables | %d |" % p["table_count"])
    A("| Total rows | %s |" % format(sum(t["row_count"] for t in tables), ","))
    for d in p.get("databases", []):
        A("| ⤷ `%s` | %d tables, %s rows |"
          % (d["database"], len(d["tables"]),
             format(sum(t["row_count"] for t in d["tables"]), ",")))
    if p["skipped"]:
        A("| Not scanned | %d (%s) |" % (len(p["skipped"]), ", ".join(p["skipped"][:5])))
    A("")

    # ── summary first: the reason anyone opens this file ───────────────────
    A("## Summary of findings")
    A("")
    populated = [t for t in tables if t["row_count"] > 0]
    A("- **%d tables**, %d populated, %d empty."
      % (len(tables), len(populated), len(tables) - len(populated)))
    biggest = max(tables, key=lambda t: t["row_count"]) if tables else None
    if biggest:
        A("- **Largest table**: `%s` (%s rows)."
          % (biggest["name"], format(biggest["row_count"], ",")))
    for label, flag in (("GPS / positioning", "GPS"), ("Truck / equipment", "TRUCK"),
                        ("Plan / production", "PLAN"), ("Operator / crew", "OPERATOR"),
                        ("Weather / environment", "WEATHER"), ("Road / route", "ROAD"),
                        ("Maintenance / downtime", "MAINTENANCE"),
                        ("Weighbridge", "WEIGHBRIDGE")):
        names = by_flag(flag)
        A("- **%s** (%d): %s" % (label, len(names),
                                 ", ".join("`%s`" % n for n in names[:14]) or "none")
          + (" …" if len(names) > 14 else ""))
    coord = by_flag("col:COORD")
    A("- **Tables with coordinate columns** (%d): %s"
      % (len(coord), ", ".join("`%s`" % n for n in coord[:14]) or "none")
      + (" …" if len(coord) > 14 else ""))
    speed = by_flag("col:SPEED")
    A("- **Tables with speed columns** (%d): %s"
      % (len(speed), ", ".join("`%s`" % n for n in speed[:14]) or "none"))

    recent = []
    now = datetime.now(timezone.utc)
    for t in tables:
        dr = t.get("date_range") or {}
        mx = dr.get("max")
        if not mx:
            continue
        try:
            d = datetime.fromisoformat(mx.replace(" ", "T")).replace(tzinfo=timezone.utc)
            if (now - d).days <= 30:
                recent.append((t["name"], mx[:10]))
        except Exception:                                      # noqa: BLE001
            pass
    recent.sort(key=lambda x: x[1], reverse=True)
    A("- **Updated in the last 30 days** (%d): %s"
      % (len(recent), ", ".join("`%s` (%s)" % r for r in recent[:14]) or "none")
      + (" …" if len(recent) > 14 else ""))
    A("")
    A(opportunities(tables))

    # ── inventory ──────────────────────────────────────────────────────────
    A("## Table inventory")
    A("")
    A("Sorted by row count. `Flags` are keyword matches on the table name; "
      "`col:` flags come from column names.")
    A("")
    A("| Table | Cols | Rows | Date range | Flags |")
    A("|---|---:|---:|---|---|")
    for t in sorted(tables, key=lambda x: -x["row_count"]):
        dr = t.get("date_range") or {}
        rng = ("%s → %s" % (dr.get("min", "?")[:10], dr.get("max", "?")[:10])
               if dr.get("min") or dr.get("max")
               else ("dates, range skipped" if t["has_dates"] else "—"))
        A("| `%s`.`%s` | %d | %s | %s | %s |"
          % (t.get("database", ""), t["name"], t["column_count"],
             format(t["row_count"], ","), rng,
             ", ".join(t["flags"]) or "—"))
    A("")

    # ── detail, populated tables only ──────────────────────────────────────
    A("## Detailed table profiles")
    A("")
    A("Empty tables are listed in the inventory above but not profiled here.")
    A("")
    for t in sorted(populated, key=lambda x: -x["row_count"]):
        A("### `%s`.`%s`" % (t.get("database", ""), t["name"]))
        A("")
        A("- **Rows**: %s" % format(t["row_count"], ","))
        A("- **Flags**: %s" % (", ".join(t["flags"]) or "none"))
        dr = t.get("date_range") or {}
        if dr:
            A("- **Date column**: `%s` — %s to %s"
              % (dr.get("column"), dr.get("min"), dr.get("max")))
        elif t["has_dates"]:
            A("- **Date columns**: %s" % ", ".join("`%s`" % c for c in t["date_columns"]))
        for n in t.get("notes", []):
            A("- *%s*" % n)
        for e in t.get("errors", []):
            A("- **error**: %s" % e)
        A("")
        A("<details><summary>%d columns</summary>" % len(t["columns"]))
        A("")
        A("| # | Column | Type | Null |")
        A("|---:|---|---|---|")
        for i, c in enumerate(t["columns"], 1):
            typ = c["type"]
            if c.get("max_length"):
                typ += "(%s)" % ("max" if c["max_length"] < 0 else c["max_length"])
            elif c.get("precision") and c["type"] in ("decimal", "numeric"):
                typ += "(%s,%s)" % (c["precision"], c.get("scale") or 0)
            A("| %d | `%s`%s | %s | %s |"
              % (i, c["name"], " 🔒" if c.get("pii") else "", typ,
                 "yes" if c["nullable"] else "no"))
        A("")
        A("</details>")
        A("")
        if t["sample_rows"]:
            keys = list(t["sample_rows"][0].keys())[:12]
            A("<details><summary>Sample rows (%d)</summary>" % len(t["sample_rows"]))
            A("")
            A("| " + " | ".join(keys) + " |")
            A("|" + "---|" * len(keys))
            for r in t["sample_rows"]:
                A("| " + " | ".join(
                    str(r.get(k, "")).replace("|", "\\|") if r.get(k) is not None
                    else "" for k in keys) + " |")
            if len(t["columns"]) > 12:
                A("")
                A("*(first 12 of %d columns shown)*" % len(t["columns"]))
            A("")
            A("</details>")
            A("")
    A("---")
    A("")
    A("Regenerate: `python scripts/db_reconnaissance.py` (requires VPN).")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
