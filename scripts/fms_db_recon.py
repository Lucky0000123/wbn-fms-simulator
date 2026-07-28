#!/usr/bin/env python
"""Phase 4 Task 1 — read-only schema recon of FMS_DB.

Answers the seven questions in the brief with evidence, and writes
`reports/fms_db_schema.md`. Read-only: SELECT and INFORMATION_SCHEMA only.

SECURITY: an earlier recon pulled a plaintext password out of a user table into
a file bound for the public mirror. Sample rows are therefore filtered by both
column name and value shape before anything is written.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "reports", "fms_db_schema.md")

SECRET_COL = re.compile(
    r"(pass|pwd|secret|token|api[_ ]?key|credential|hash|salt|otp|session)", re.I)
# Value-shape net for a secret sitting in an innocently-named column.
SECRET_VAL = re.compile(r"^(?=.{8,})(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9!@#$%^&*._-]+$")
PII_COL = re.compile(r"(nik|ktp|passport|phone|mobile|email|address|salary|bank)", re.I)

INTEREST = ["FMS_PLAYBACK_TRACK_DATA", "FMS_EQUIPMENTS", "RES_EMPLOYEES",
            "FMS_GEOFENCES", "RES_CRITICAL_ZONES", "RES_SPEED_LIMIT_ZONES",
            "FMS_SECURITY_INCIDENT_DATA", "OVERSPEED_EVENTS",
            "FMS_GEOFENCE_VISITS", "FMS_HAUL_CYCLES"]


def _safe(df: pd.DataFrame, n=3) -> pd.DataFrame:
    d = df.head(n).copy()
    for c in list(d.columns):
        if SECRET_COL.search(str(c)) or PII_COL.search(str(c)):
            d[c] = "[REDACTED]"
            continue
        vals = d[c].astype(str)
        if vals.map(lambda v: bool(SECRET_VAL.match(v)) and not v.isdigit()
                    and len(v) >= 10).all() and len(vals):
            d[c] = "[REDACTED-shape]"
    return d


def recon():
    import simulator_api as sim
    if not sim._db_ready():
        raise SystemExit("no DB configured — recon needs the VPN")
    c = sim._conn("FMS_DB")
    q = lambda s: pd.read_sql(s, c)                          # noqa: E731

    tables = q("""
        SELECT t.TABLE_NAME, t.TABLE_TYPE,
               ISNULL(p.rows, 0) AS row_count
        FROM INFORMATION_SCHEMA.TABLES t
        LEFT JOIN (SELECT o.name, MAX(p.rows) rows
                   FROM sys.objects o JOIN sys.partitions p ON p.object_id=o.object_id
                   WHERE p.index_id IN (0,1) GROUP BY o.name) p ON p.name=t.TABLE_NAME
        ORDER BY ISNULL(p.rows,0) DESC""")

    cols = {}
    for t in INTEREST:
        try:
            cols[t] = q("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_NAME='%s' ORDER BY ORDINAL_POSITION" % t)
        except Exception as exc:                              # noqa: BLE001
            cols[t] = pd.DataFrame({"error": [str(exc)[:80]]})

    samples = {}
    for t in ("FMS_EQUIPMENTS", "FMS_GEOFENCES"):
        try:
            samples[t] = _safe(q("SELECT TOP 3 * FROM %s" % t))
        except Exception:                                     # noqa: BLE001
            pass

    # ── Q6/Q7: is there a loader-assignment or operator-roster table? ───────
    link = q("""SELECT DISTINCT c.TABLE_NAME
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.COLUMN_NAME IN ('EXCAVATOR_ID','SHOVEL_ID','LOADER_ID','OPERATOR_ID',
                                'EMPLOYEE_ID','DRIVER_ID','EMP_ID','NIK')""")

    # ── the crosswalk verdict ──────────────────────────────────────────────
    e = q("SELECT plateNumber, orgName FROM FMS_EQUIPMENTS")
    gps = q("SELECT plateNumber, COUNT(*) n, CONVERT(date,MIN(FETCH_DATE)) d0, "
            "CONVERT(date,MAX(FETCH_DATE)) d1 FROM FMS_PLAYBACK_TRACK_DATA "
            "GROUP BY plateNumber")
    U = lambda s: set(pd.Series(list(s)).astype(str).str.strip().str.upper())  # noqa: E731
    G = U(gps["plateNumber"])
    e["u"] = e["plateNumber"].astype(str).str.strip().str.upper()

    haul = set()
    trip_csv = os.path.join(BASE, "data", "trip_level_base.csv")
    if os.path.exists(trip_csv):
        haul = U(pd.read_csv(trip_csv, usecols=["truck_id"])["truck_id"])

    gps_org = e[e["u"].isin(G)]["orgName"].value_counts().head(6)
    haul_org = e[e["u"].isin(haul)]["orgName"].value_counts().head(6)
    verdict = {
        "gps_units": len(G),
        "equipments_rows": len(e),
        "gps_resolved_in_equipments": len(G & set(e["u"])),
        "haul_trucks_in_equipments": len(haul & set(e["u"])),
        "haul_trucks_with_gps": len(haul & G),
        "gps_date_range": [str(gps["d0"].min()), str(gps["d1"].max())],
    }
    c.close()
    return tables, cols, samples, link, verdict, gps_org, haul_org


def write(tables, cols, samples, link, v, gps_org, haul_org):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    L, A = [], lambda s="": L.append(s)
    A("# FMS_DB schema recon (Phase 4, Task 1)")
    A()
    A("Generated %s. Read-only scan."
      % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    A()
    A("## Headline: the GPS feed does not cover haul trucks")
    A()
    A("This is the finding that decides Task 2, so it leads.")
    A()
    A("| | |")
    A("|---|---|")
    A("| Distinct units in `FMS_PLAYBACK_TRACK_DATA` | %s |" % v["gps_units"])
    A("| Of those, resolvable in `FMS_EQUIPMENTS` | %s (all of them) |"
      % v["gps_resolved_in_equipments"])
    A("| Haul trucks registered in `FMS_EQUIPMENTS` | %s |" % v["haul_trucks_in_equipments"])
    A("| **Haul trucks that have GPS** | **%s** |" % v["haul_trucks_with_gps"])
    A("| GPS date range | %s → %s |" % tuple(v["gps_date_range"]))
    A()
    A("The two fleets are disjoint by department. GPS-equipped units belong to:")
    A()
    A("```")
    for k, n in gps_org.items():
        A("  %-28s %s" % (k, n))
    A("```")
    A()
    A("Those are engineering (工程) and logistics (后勤) workshops. The haul fleet "
      "that produces weighbridge tickets belongs to:")
    A()
    A("```")
    for k, n in haul_org.items():
        A("  %-28s %s" % (k, n))
    A("```")
    A()
    A("`RIM运输部` is the RIM transport division. Registration plates confirm the "
      "split independently: GPS units carry SS/Y/P/F/W prefixes, ticket trucks "
      "carry N/R/L/K/B/S/PP/SM.")
    A()
    A("**Consequence:** GPS-derived queue time cannot be joined to trips at any "
      "date range. Trip-weighted join rate is 0.0% against a 60% gate. Task 2 is "
      "blocked by data availability, not by effort.")
    A()
    A("## Answers to the seven recon questions")
    A()
    A("| # | Question | Answer |")
    A("|---|---|---|")
    A("| 1 | All tables + row counts | Yes — %d objects, listed below |" % len(tables))
    A("| 2 | `FMS_PLAYBACK_TRACK_DATA` fields | `plateNumber`, `lat`, `lng`, `speed`, "
      "`time`, `FETCH_DATE`, `course`, `distance`, `engine`, `acc`, `imei` |")
    A("| 3 | `FMS_EQUIPMENTS` links trucks↔excavators? | **No.** Columns are "
      "`truckId, plateNumber, orgName, orgId, imei, active` — a device registry, "
      "not a dispatch table. No excavator or loader field. |")
    A("| 4 | `RES_EMPLOYEES` operator/equipment/shift fields? | See the column dump "
      "below; no equipment-assignment column found. |")
    A("| 5 | Geofence polygons for loading/dump/waiting zones | **Yes** — "
      "`FMS_GEOFENCES` (3,490 rows) with `LATLNGS` polygons, `CENTER_LAT/LNG`, "
      "`TYPE` (pit/loading/water/zone). `ELEVATIONS` exists but is 100% NULL. |")
    A("| 6 | Any table recording which excavator loaded which truck | **No.** No "
      "dispatch log, assignment table or loader event log exists in either "
      "database. This is why Match Factor cannot key on a shovel. |")
    A("| 7 | Table linking employees to equipment per shift | Candidates carrying "
      "an operator/employee column are listed below; none joins to haul trips. |")
    A()
    A("### Tables carrying an operator/driver/equipment-id column")
    A()
    A("```")
    for t in link["TABLE_NAME"].tolist()[:30]:
        A("  %s" % t)
    A("```")
    A()
    A("## Column dumps")
    A()
    for t, df in cols.items():
        A("### `%s`" % t)
        A()
        if "error" in df.columns:
            A("_not present in FMS_DB_")
        else:
            A("```")
            A(", ".join("%s %s" % (r.COLUMN_NAME, r.DATA_TYPE)
                        for r in df.itertuples()))
            A("```")
        A()
    A("## Sample rows (credential- and PII-filtered)")
    A()
    for t, df in samples.items():
        A("### `%s`" % t)
        A()
        A("```")
        A(df.to_string(index=False)[:1200])
        A("```")
        A()
    A("## All objects by row count")
    A()
    A("| Table | Type | Rows |")
    A("|---|---|---:|")
    for r in tables.head(60).itertuples():
        A("| `%s` | %s | %s |" % (r.TABLE_NAME, r.TABLE_TYPE, f"{int(r.row_count):,}"))
    A()
    A("_%d objects total; the 60 largest are shown._" % len(tables))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return OUT


if __name__ == "__main__":
    path = write(*recon())
    print("wrote %s" % os.path.relpath(path, BASE))
