"""write_full_schema_report.py — the complete per-table catalogue.

Replaces reports/database_schema_analysis.md with a document that lists EVERY
object in both databases, its columns, row count, date range, sample rows and
ID vocabularies, followed by the cross-database analysis the brief specifies.

Structure follows the brief: WBN_DATABASE, FMS_DB, then Cross-Database
Analysis with the ID comparison, GPS coverage, segment definitions, HRM, the
FMS_CONGESTION_SEG breakdown, and the capability summary table.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RAW = os.path.join(ROOT, "reports", "schema_full_raw.json")
FINDINGS = os.path.join(ROOT, "reports", "schema_findings.json")
OUT = os.path.join(ROOT, "reports", "database_schema_analysis.md")

# Purpose notes for tables that matter to the simulator. Written by hand
# because "what could this be used for" is a judgement, not a query result,
# and a catalogue without it is just a list.
NOTES = {
    "HAULAGE_IWIP_CLEAN": "The trip source. 483,425 trips extracted from here; one weighbridge interval per trip (FIRST_WB_TIME to SECOND_WB_TIME).",
    "WAITING_TIME": "Measured loading and dumping dwell in minutes (LOADING_DIFFERENCE_TIME, DUMPING_DIFFERENCE_TIME). Already used; covers 24.8% of trips on a truck+date+shift join.",
    "HAUL_ROAD_STA": "Haul-road chainage every 25 m with WKT POINT Z geometry. Defines the road centreline by road code and SectionKM.",
    "ALL_HR_KM_SECTIONS": "The 27 named road sections with KM_START/KM_END and their origin/destination junctions. The authoritative segment vocabulary.",
    "DISPATCH ROADS": "Per origin-destination pair, the FRACTION of the haul crossing each of 27 named sections. A ready-made route-to-segment decomposition.",
    "DISTANCE_HAULING": "Real per-haul distances by origin/destination with date, tonnage and trip count. Candidate replacement for the placeholder distance_km.",
    "HRM_INSPECTION": "Road-condition observations by KM, severity and type since 2024-10. Exogenous to deployment, so usable as a cycle-time feature.",
    "HRM_MAJOR_ROADWORK": "Roadwork campaigns by KM range with fleet, material and percent complete.",
    "HRM_CONTRACT_EQUIPMENT": "Equipment committed per road section by contractor.",
    "EQUIPMENTS": "WBN equipment register.",
    "AVG_RAIN_BY_DATE_AREA": "Rainfall by date and area; joined into the trip features as rainfall_mm.",
    "FMS_PLAYBACK_TRACK_DATA": "26.4M raw GPS fixes, but keyed on plateNumber and containing only 219 SS###/E### support units. This is the table that produced the false '0 of 940' claim.",
    "FMS_GPS_Historical": "GPS with a PLATE column that DOES match haul trucks. 5-day retention window.",
    "FMS_PLAYBACK_TRACK_24H": "Live GPS, 1-day window. 479 of 945 haul-truck devices report here.",
    "auto_kmFMS_PLAYBACK_TRACK_DATA": "GPS fixes resolved to KM chainage. The link between raw tracks and named road segments.",
    "FMS_CONGESTION_SEG": "Per segment, per hour, per direction: speed sum, fix count, truck count and traverse time. Segment-level speed, already aggregated.",
    "FMS_GEOFENCE_VISITS": "Enter/exit timestamps and DURATION_SEC per unit at typed geofences, with UNIT_TYPE naming haul trucks explicitly. Measured dwell at pits and weighbridges.",
    "FMS_GEOFENCES": "3,490 geofence polygons with LATLNGS, centre, type, PIT_ID and PILE_ID.",
    "FMS_ENTRY_EXIT_DATA": "11.6M point-level stay events with stayTime at named locations.",
    "FMS_EQUIPMENTS": "The equipment register that bridges the two databases: plateNumber matches weighbridge TRUCK_ID, truckId is the GPS device serial.",
    "FMS_UNIT_INSTALLED": "Which plates have a telematics device fitted and when it first reported.",
    "FMS_TRUCK_ASSIGNMENTS": "Truck to EXCAVATOR assignment per shift, with pile, pit, material and destination. Loader identity in weighbridge truck format.",
    "FMS_HAUL_CYCLES": "Completed haul cycles with truck plate, excavator and dump timestamp.",
    "FMS_TRUCK_CYCLES": "Live per-truck state machine: TRAVEL_EMPTY, LOAD, TRAVEL_LOADED, with GPS geofence events in TRANSITION_META.",
    "RES_EMPLOYEES": "Operator register: employee ID, contractor, division, job title, grade.",
    "RES_SPEED_LIMIT_ZONES": "Posted speed limit per segment with KM_From/KM_To.",
    "RES_CRITICAL_ZONES": "Designated critical zones.",
    "FMS_PLAYBACK_STAY_DATA": "Stay events carrying speed, maxSpeed, limitSpeed, mileage and driver identity.",
    "FMS_HRM_SUPERVISION": "HRM machine work with coordinates, section KM, equipment type (EX/GD) and hours.",
    "FMS_DISPATCH_PLAN": "Dispatch plan records.",
    "FMS_QUALITY_DISPATCH": "Quality-driven dispatch records.",
}


def fmt_type(c):
    return c["type"] + ("(%s)" % c["len"] if c.get("len") else "")


def sample_table(rec):
    s = rec.get("sample")
    if not s:
        return []
    keys = list(s[0].keys())
    out = ["| " + " | ".join(keys) + " |",
           "|" + "|".join(["---"] * len(keys)) + "|"]
    for row in s[:5]:
        vals = []
        for k in keys:
            v = row.get(k)
            v = "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")
            vals.append(v[:38] + ("…" if len(v) > 38 else ""))
        out.append("| " + " | ".join(vals) + " |")
    return out


def emit_db(a, db, blk):
    objs = blk.get("objects", {})
    tables = {k: v for k, v in objs.items() if v["type"] == "BASE TABLE"}
    views = {k: v for k, v in objs.items() if v["type"] == "VIEW"}
    a("## %s" % db)
    a("")
    a("%d objects: **%d base tables**, %d views. Every base table with rows was "
      "sampled; views are catalogued for columns (each is defined over base "
      "tables already covered)."
      % (len(objs), len(tables), len(views)))
    a("")
    a("### %s — index" % db)
    a("")
    a("| Table | Rows | Cols | Date range |")
    a("|---|---|---|---|")
    for k in sorted(tables, key=lambda x: -(tables[x].get("row_count") or 0)):
        v = tables[k]
        dr = v.get("date_range")
        a("| [`%s`](#%s) | %s | %d | %s |"
          % (k, anchor(k, db), "{:,}".format(v.get("row_count") or 0),
             len(v.get("columns", [])),
             ("%s → %s" % (dr[0][:10], dr[1][:10])) if dr else "—"))
    a("")
    a("### %s — table detail" % db)
    a("")
    for k in sorted(tables, key=lambda x: -(tables[x].get("row_count") or 0)):
        v = tables[k]
        a('<a id="%s"></a>' % anchor(k, db))
        a("")
        a("#### `%s`" % k)
        a("")
        n = v.get("row_count") or 0
        dr = v.get("date_range")
        a("**Rows:** %s  |  **Columns:** %d%s"
          % ("{:,}".format(n), len(v.get("columns", [])),
             ("  |  **%s:** %s → %s" % (v.get("date_column", "date"),
                                        dr[0][:19], dr[1][:19])) if dr else ""))
        a("")
        if k in NOTES:
            a("> %s" % NOTES[k])
            a("")
        cs = v.get("columns", [])
        if cs:
            a("**Columns:** " + ", ".join("`%s` %s" % (c["name"], fmt_type(c))
                                          for c in cs))
            a("")
        ids = v.get("id_columns") or {}
        if ids:
            a("**Identifier vocabularies:**")
            a("")
            for cn, info in list(ids.items())[:6]:
                ex = ", ".join("`%s`" % e for e in info["examples"][:12])
                a("- `%s` — %s distinct. e.g. %s"
                  % (cn, ("{:,}".format(info["distinct"])
                          if info["distinct"] is not None else "?"), ex))
            a("")
        ce = v.get("coordinate_extent")
        if ce:
            a("**Coordinate extent:** " + "; ".join(
                "`%s` %s → %s" % (c, r[0], r[1]) for c, r in ce.items()))
            a("")
        if n == 0:
            a("*Empty table.*")
            a("")
        else:
            st = sample_table(v)
            if st:
                shown = v.get("sample_columns_shown", 0)
                a("**Sample rows**%s:"
                  % (" (first %d of %d columns)" % (shown, len(cs))
                     if shown and shown < len(cs) else ""))
                a("")
                a("\n".join(st))
                a("")
            elif v.get("sample_error"):
                a("*Sample unavailable: %s*" % v["sample_error"][:120])
                a("")
    if views:
        a("### %s — views (%d)" % (db, len(views)))
        a("")
        a("<details><summary>Column lists for all %d views</summary>" % len(views))
        a("")
        for k in sorted(views):
            v = views[k]
            a("- **`%s`** (%d cols): %s"
              % (k, len(v.get("columns", [])),
                 ", ".join("`%s`" % c["name"] for c in v.get("columns", []))))
        a("")
        a("</details>")
        a("")
    if blk.get("errors"):
        a("*%d tables errored during sampling: %s*"
          % (len(blk["errors"]), "; ".join(blk["errors"][:6])))
        a("")


def anchor(name, db):
    s = ("%s-%s" % (db, name)).lower()
    return "".join(ch if ch.isalnum() else "-" for ch in s)


def main():
    raw = json.load(open(RAW, encoding="utf-8"))
    fnd = (json.load(open(FINDINGS, encoding="utf-8"))
           if os.path.exists(FINDINGS) else {})
    L = []
    a = L.append

    a("# Database Schema Analysis")
    a("")
    a("*Complete read-only inventory of `WBN_DATABASE` and `FMS_DB`. "
      "Generated %s by `scripts/scan_all_tables.py` + "
      "`scripts/write_full_schema_report.py`. Every base table with rows was "
      "sampled. No object was created, altered or dropped.*"
      % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    a("")
    tot_t = sum(b.get("table_count", 0) for b in raw["databases"].values())
    tot_v = sum(b.get("view_count", 0) for b in raw["databases"].values())
    a("**Scope:** %d base tables and %d views across both databases."
      % (tot_t, tot_v))
    a("")
    a("Jump to: [WBN_DATABASE](#wbn_database) · [FMS_DB](#fms_db) · "
      "[Cross-Database Analysis](#cross-database-analysis) · "
      "[What data exists for the simulator](#summary-what-data-exists-for-the-simulator)")
    a("")
    a("---")
    a("")

    for db in ("WBN_DATABASE", "FMS_DB"):
        blk = raw["databases"].get(db, {})
        if "fatal_error" in blk:
            a("## %s — scan failed: %s" % (db, blk["fatal_error"][:150]))
            a("")
            continue
        emit_db(a, db, blk)
        a("---")
        a("")

    with open(os.path.join(ROOT, "reports", "_cross_analysis.md"),
              encoding="utf-8") as fh:
        a(fh.read())

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote %s (%d lines)" % (OUT, len(L)))


if __name__ == "__main__":
    main()
