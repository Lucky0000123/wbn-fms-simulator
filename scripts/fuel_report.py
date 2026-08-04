#!/usr/bin/env python3
"""Render all fuel_recon phases into one markdown report."""
import json
import pathlib

D = pathlib.Path("data/fuel_recon")
OUT = pathlib.Path("reports/FUEL_DATA_RECON.md")
DBS = ["WBN_DATABASE", "FMS_DB"]


def load(n):
    p = D / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


def tbl(cols, rows, limit=None, maxw=60):
    if not rows:
        return "_(no rows)_\n"
    rows = rows[:limit] if limit else rows
    def cell(v):
        s = "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")
        return s[:maxw] + ("…" if len(s) > maxw else "")
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


L = []
w = L.append

w("# Fuel / Equipment-Hours / Haulage Data Reconnaissance")
w("\nSQL Server `10.211.10.1` — databases `WBN_DATABASE` and `FMS_DB`.")
w("All 10 requested steps run against both databases. Raw results below.\n")

# ---- headline
w("## 0. Headline finding\n")
w("""There is **no fuel/diesel accounting subsystem** in either database.
No SAP posting table, no fuel-issuance table, no tank/dispenser inventory, no
litres-per-hour or burn-rate field anywhere. Exhaustive name searches across
all 681 tables+views and all column names (including synonyms `BBM`, `SOLAR`,
`LTR`, `REFUEL`, `DISPENSE`, `HOURMETER`, `SMU`, `ODOMETER`) return exactly
**one** real fuel data source:

| Source | Detail |
|---|---|
| `WBN_DATABASE.dbo.WAITING_TIME` | 4 fuel columns: `FUEL_FILLING_TIME`, `FUEL_FILLING_TIME 2`, `TOTAL_FUEL`, `TOTAL_FUEL 2` |
| Records with fuel | **39,366** parseable of 878,240 rows (4.5%) |
| Date span of fuel | **2026-02-22 → 2026-07-22** (5 months only) |
| Distinct equipment | **736** |
| Total litres logged | **7,834,145 L**, mean **199.2 L** per fill |

`TOTAL_FUEL` is `nvarchar(100)` free text (`'200'`, `'200 L'`, `'180L'`, `''`),
so it must be parsed, not cast. Everything else the model needs — operating
hours, haulage distance, fleet, contractor — is present and large.\n""")

# ---- 1 fuel tables
w("\n## 1. Fuel/Diesel tables found\n")
for db in DBS:
    p2 = load(f"phase2_{db}")
    w(f"\n### {db} — columns matching fuel words (wide net)\n")
    hits = [r for k in ("wide_table_columns", "wide_view_columns")
            for r in p2[k]["rows"]
            if any(x in (r[1] + "." + r[2]).upper() for x in
                   ("FUEL", "DIESEL", "BBM", "SOLAR", "LITRE", "LITER",
                    "LTR", "REFUEL", "DISPENSE", "PUMP", "TANK"))]
    w(tbl(["schema", "object", "column", "type", "len", "nullable"], hits))
    w(f"\n**Modules (views/procs/functions) mentioning fuel in {db}:**\n")
    w(tbl(p2["modules_mentioning_fuel"]["columns"],
          p2["modules_mentioning_fuel"]["rows"]))

pq = load("phase4_fuel_quality")
if pq:
    w("\n### WAITING_TIME — fuel data quality\n")
    w("**Monthly coverage** (`fuel_rows` = non-null `TOTAL_FUEL`):\n")
    w(tbl(pq["monthly"]["columns"], pq["monthly"]["rows"]))
    w("\n**Parsed totals:**\n")
    w(tbl(pq["parsed"]["columns"], pq["parsed"]["rows"]))
    w("\n**Top 15 equipment by fill count:**\n")
    w(tbl(pq["by_equip"]["columns"], pq["by_equip"]["rows"]))

wt = load("phase3_waiting_time_probe")
if wt:
    w("\n**Distinct `TOTAL_FUEL` raw values (top 30, shows the text problem):**\n")
    w(tbl(wt["total_fuel_values"]["columns"], wt["total_fuel_values"]["rows"]))

# ---- 2-4 schemas & samples
SECT = {
    "2. Equipment hours tables": [
        ("WBN_DATABASE", t) for t in
        ("EQUIPMENTS_HOURLY_STATUS", "EQUIPMENTS_HOURLY_ACTIVITIES",
         "EQUIPMENTS_STATUS", "EQUIPMENTS_WORKS", "DAY_WORKS")],
    "3. Haulage / weighbridge / distance tables": [
        ("WBN_DATABASE", t) for t in
        ("HAULAGE", "HAULAGE_IWIP", "HAULAGE_IWIP_EXT", "RSF_HAULING_DATA",
         "DISTANCE_MINING", "HAUL_ROAD_STA", "WAITING_TIME")] + [
        ("FMS_DB", t) for t in
        ("FMS_PLAYBACK_TRACK_DATA", "auto_kmFMS_PLAYBACK_TRACK_DATA",
         "FMS_CONGESTION_SEG", "FMS_HAUL_CYCLES", "FMS_GEOFENCE_VISITS")],
    "4. Contractor / fleet tables": [
        ("WBN_DATABASE", t) for t in
        ("EQUIPMENTS", "HRM_CONTRACT_EQUIPMENT", "CONTRACTOR FOLLOW UP")] + [
        ("FMS_DB", t) for t in
        ("FMS_EQUIPMENTS", "FMS_TRUCK_ASSIGNMENTS", "FMS_UNIT_INSTALLED")],
}
p3 = {db: load(f"phase3_{db}") for db in DBS}
for title, items in SECT.items():
    w(f"\n## {title}\n")
    for db, t in items:
        e = (p3.get(db) or {}).get(t)
        if not e or not e["schema"]["rows"]:
            w(f"\n### `{db}.dbo.{t}` — NOT FOUND\n")
            continue
        w(f"\n### `{db}.dbo.{t}` — {e['count']:,} rows, "
          f"{len(e['schema']['rows'])} columns\n")
        w("\n**Schema:**\n")
        w(tbl(["column", "type", "max_length", "nullable"], e["schema"]["rows"]))
        w("\n**Sample (20 rows):**\n")
        w(tbl(e["sample"]["columns"], e["sample"]["rows"]))

# ---- 5 views
w("\n## 5. Views related to fuel / equipment (Step 9)\n")
for db in DBS:
    p1 = load(f"phase1_{db}")
    v = p1["step9_view_defs"]
    w(f"\n### {db} — {len(v['rows'])} matching views\n")
    for r in v["rows"]:
        w(f"\n<details><summary><code>{r[0]}.{r[1]}</code></summary>\n")
        w("\n```sql\n" + (r[2] or "")[:20000] + "\n```\n")
        w("\n</details>\n")

# ---- 6 inventory
w("\n## 6. Complete table/view inventory (Step 3)\n")
for db in DBS:
    p1 = load(f"phase1_{db}")
    o = p1["step3_all_objects"]
    rc = {(r[0], r[1]): r[2] for r in p1["rowcounts"]["rows"]}
    rows = [[r[0], r[1], r[2], rc.get((r[0], r[1]), ""), r[3] or ""]
            for r in o["rows"]]
    nt = sum(1 for r in o["rows"] if r[2] == "USER_TABLE")
    w(f"\n### {db} — {len(o['rows'])} objects "
      f"({nt} tables, {len(o['rows'])-nt} views)\n")
    w(tbl(["schema", "object", "type", "approx_rows", "description"], rows))

# ---- 7 columns
w("\n## 7. Column-level fuel references\n")
w("\n### 7a. Step-2 exact query results (tables only, as requested)\n")
for db in DBS:
    p1 = load(f"phase1_{db}")
    s = p1["step2_fuel_columns"]
    w(f"\n**{db}** — {len(s['rows'])} columns\n")
    w(tbl(s["columns"], s["rows"]))
w("""
### 7b. Widened search (fuel synonyms + hourmeter/odometer/distance)

Step 2 as written joins `sys.columns` to `sys.tables`, so **views are invisible
to it**, and it misses the Indonesian terms used on this site (`BBM`, `SOLAR`)
plus `HOURMETER`/`SMU`/`ODOMETER`. Both gaps are closed here.
""")
for db in DBS:
    p2 = load(f"phase2_{db}")
    for k, lbl in (("wide_table_columns", "tables"),
                   ("wide_view_columns", "views")):
        w(f"\n**{db} — {lbl}: {len(p2[k]['rows'])} columns**\n")
        w(tbl(p2[k]["columns"], p2[k]["rows"]))

# ---- appendix: other steps
w("\n## 8. Appendix — remaining step outputs\n")
NAMES = {"step1_fuel_objects": "Step 1: fuel-named objects",
         "step5_equip_objects": "Step 5: equipment/fleet/haul objects",
         "step8_sap_objects": "Step 8: SAP / issuance / inventory objects",
         "step10_distance_objects": "Step 10: distance / route objects",
         "step4_key_table_schemas": "Step 4: schemas of named key tables",
         "rowcounts": "All table row counts (partition stats)"}
for db in DBS:
    p1 = load(f"phase1_{db}")
    for k, lbl in NAMES.items():
        w(f"\n### {db} — {lbl} ({len(p1[k]['rows'])} rows)\n")
        w(tbl(p1[k]["columns"], p1[k]["rows"]))

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size//1024} KB, "
      f"{len(OUT.read_text().splitlines())} lines)")
