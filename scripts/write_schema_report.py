"""write_schema_report.py — assemble reports/database_schema_analysis.md.

Combines the bulk inventory (scan_databases.py) with the targeted GPS,
segment, HRM and assignment findings into one document.

The report's most important job is to correct a published claim. The simulator
currently states "0 of 940 haul trucks appear in the GPS feed" and concludes
segment-level speed is unavailable. That is wrong, the operator was right to
push back, and the correction is stated plainly at the top rather than buried
in a table.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

RAW = os.path.join(ROOT, "reports", "database_schema_raw.json")
OUT = os.path.join(ROOT, "reports", "database_schema_analysis.md")


def conn(db):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=900, charset="LATIN1")


def ms(v):
    try:
        return datetime.fromtimestamp(float(v) / 1000,
                                      tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:                                        # noqa: BLE001
        return "?"


def fmt_cols(cols, limit=None):
    out = []
    for c in (cols[:limit] if limit else cols):
        t = c["type"] + ("(%s)" % c["len"] if c.get("len") else "")
        out.append("`%s` %s" % (c["name"], t))
    if limit and len(cols) > limit:
        out.append("… +%d more" % (len(cols) - limit))
    return ", ".join(out)


def main() -> None:
    raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else {"databases": {}}
    L = []
    a = L.append

    a("# Database Schema Analysis")
    a("")
    a("*Read-only scan of `WBN_DATABASE` and `FMS_DB`. Generated %s by "
      "`scripts/scan_databases.py` + `scripts/write_schema_report.py`. "
      "No table was created, altered or dropped.*"
      % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    a("")

    # ---------------------------------------------------------------- verdict
    a("## The headline: a published claim was wrong")
    a("")
    a("The simulator states **\"0 of 940 haul trucks appear in the GPS feed\"** and "
      "concludes segment-level speed is unavailable. **That claim is wrong, and the "
      "site operator was right to challenge it.**")
    a("")
    a("What went wrong: the check matched `FMS_PLAYBACK_TRACK_DATA.plateNumber` "
      "against weighbridge truck IDs. On *that table* the answer really is zero — its "
      "219 plates are `SS###`/`E###` support units. The error was generalising one "
      "table's answer to the whole database, and reading the Chinese department "
      "strings (`工程`/`后勤`) as vehicle classes. They are org units, and as the "
      "operator said, logistics is a contractor grouping, not a vehicle type.")
    a("")
    a("What the data actually shows:")
    a("")
    a("| Evidence | Finding |")
    a("|---|---|")
    a("| `FMS_EQUIPMENTS.plateNumber` vs weighbridge truck IDs | **945 of 1,411 match** |")
    a("| `FMS_GEOFENCE_VISITS` rows typed `Haul Truck` | **43,763 rows, 644 units** |")
    a("| of those units, present in the weighbridge | **613 (95.2%)** |")
    a("| Haul-truck devices with rows in `FMS_GPS_Historical` | **455 of 945 (48.1%)** |")
    a("| Haul-truck devices in `FMS_PLAYBACK_TRACK_24H` | **479 of 945 (50.7%)** |")
    a("| `FMS_CONGESTION_SEG` road segments with measured speed | **95 segments** |")
    a("| GPS sampling interval (median) | **3 seconds** |")
    a("")
    a("Haul trucks **are** GPS-instrumented, at 3-second resolution, and segment-level "
      "speeds already exist pre-aggregated in `FMS_CONGESTION_SEG`.")
    a("")
    a("### The real constraint is retention, not instrumentation")
    a("")
    a("| Table | Coverage | Overlaps trip extract (2025-12-27 → 2026-07-09)? |")
    a("|---|---|---|")
    a("| `FMS_GPS_Historical` | 2026-07-15 → 2026-07-20 (5 days) | **No** |")
    a("| `FMS_PLAYBACK_TRACK_24H` | 2026-07-29 → 2026-07-30 (1 day) | **No** |")
    a("| `FMS_CONGESTION_SEG` | 2026-07-15 → 2026-07-30 | **No** |")
    a("| `FMS_GEOFENCE_VISITS` | 2025-12-07 → 2026-07-30, **89 distinct days** | **YES** |")
    a("| `FMS_ENTRY_EXIT_DATA` | 2026-05-30 → 2026-07-30 | partial |")
    a("| `FMS_PLAYBACK_TRACK_DATA` | 2026-03-21 → 2026-07-30 | yes, but **no haul trucks** |")
    a("")
    a("Two different situations, and the distinction matters:")
    a("")
    a("- **Raw GPS tracks and derived segment speeds** are a rolling live feed with "
      "days of retention. They cannot retro-fit segment speeds onto the historical "
      "trips already extracted. They can drive a forward-looking simulator, and they "
      "accumulate from now on.")
    a("- **`FMS_GEOFENCE_VISITS` is different.** It spans 2025-12-07 to 2026-07-30 "
      "across 89 distinct days, which **overlaps the trip extract**. Haul-truck dwell "
      "at named pits is therefore available for the same period the simulator was "
      "trained on, and can be joined to existing trips today.")
    a("")
    a("So the corrected statement is: **haul trucks are GPS-instrumented at 3-second "
      "resolution; segment-level speed exists but only for the last two weeks; and "
      "measured pit dwell for haul trucks is available across the training period.**")
    a("")
    a("This is a materially better position than \"no GPS on haul trucks\", and the "
      "simulator's documentation should be corrected.")
    a("")

    # ------------------------------------------------------- tables that matter
    a("## Tables that change what the simulator can do")
    a("")
    a("### `FMS_GEOFENCE_VISITS` — measured dwell at named pits")
    a("")
    a("59,358 rows. Columns: `UNIT_ID`, `UNIT_TYPE`, `ORG_NAME`, `GEOFENCE_ID`, "
      "`GEOFENCE_NAME`, `GEOFENCE_TYPE`, `ENTER_TS`, `EXIT_TS`, `DURATION_SEC`, "
      "`ENTER_LAT/LNG`, `EXIT_LAT/LNG`, `STATUS`, `SOURCE`.")
    a("")
    a("This is the single most valuable table found. It records, per haul truck, "
      "**enter and exit timestamps with a computed duration** at typed geofences.")
    a("")
    a("| Unit type | Rows |   | Geofence type | Rows |")
    a("|---|---|---|---|---|")
    a("| Haul Truck | 43,763 | | pit | 21,087 |")
    a("| Excavator | 3,605 | | weighbridge | 19,378 |")
    a("| Grader | 1,604 | | water | 10,024 |")
    a("| Compactor | 1,120 | | sampling | 6,447 |")
    a("| Fuel Truck | 834 | | dumping | 1,202 |")
    a("| Light Vehicle | 329 | | loading | 835 |")
    a("")
    a("Coverage is **2025-12-07 to 2026-07-30 across 89 distinct days**, which "
      "overlaps the trip extract. 15,100 haul-truck visits to **pit** geofences "
      "across BLB, CBB, KR and TF, median dwell **14.1 min**.")
    a("")
    a("That figure is worth comparing to what the simulator currently uses. Measured "
      "loading dwell from `WAITING_TIME` is 9.0 min at the median; these geofence "
      "visits give 14.1 min. The two measure slightly different things (a geofence is "
      "larger than a shovel, so it includes the approach and the queue), and the gap "
      "between them is itself informative: **roughly 5 minutes of queue and "
      "manoeuvring per load** that the shovel-side measurement does not see.")
    a("")
    a("It also carries `UNIT_TYPE`, which answers a question the simulator could not "
      "previously answer: **which units are haul trucks**, without guessing from "
      "department names.")
    a("")
    a("### `FMS_CONGESTION_SEG` — segment-level speed, already aggregated")
    a("")
    a("34,988 rows, 2026-07-15 → 2026-07-30. Columns: `HOUR_TS`, `SEG_ID`, `DIR`, "
      "`SUM_SPD`, `FIX_N`, `TRUCK_N`, `SUM_TRAV_MS`, `TRAV_N`.")
    a("")
    a("- **95 distinct segments**, named by road and kilometre: `BLB KM17-18`, "
      "`CBB KM10-11`, `CRD KM0-1`, `KR KM…`, `TF KM…`")
    a("- **Directional** (`up` / `down`), so loaded and empty legs are separable")
    a("- Mean speed per segment-hour = `SUM_SPD / FIX_N`: median **17.2 km/h**, "
      "p5 7.6, p95 26.5 — physically sensible for a haul road")
    a("- `TRUCK_N` is the count of units contributing that hour: median 10, max 69")
    a("- `SUM_TRAV_MS` / `TRAV_N` give measured **traverse time** per segment")
    a("")
    a("Derived from the GPS feed. This is exactly the segment-level product the "
      "simulator was told it could not have, and it inherits the same 2-week retention.")
    a("")
    a("### `FMS_TRUCK_ASSIGNMENTS` / `FMS_HAUL_CYCLES` / `FMS_TRUCK_CYCLES`")
    a("")
    a("- `FMS_TRUCK_ASSIGNMENTS` (408 rows): `PLAN_DATE`, `SHIFT`, `TRUCK`, `PILE`, "
      "**`EXCAVATOR`**, `PIT`, `MATERIAL`, `DESTINATION`. Excavator identity per "
      "truck-shift — the loader assignment previously reported as blocked by an "
      "`AD4059`/`A342` namespace split. Here the truck is `R707`, matching weighbridge "
      "format directly.")
    a("- `FMS_HAUL_CYCLES` (288 rows): completed cycles with `TRUCK_PLATE`, "
      "`EXCAVATOR`, `DUMP_TS`, `MATERIAL` (Waste/…).")
    a("- `FMS_TRUCK_CYCLES` (1 row, live state): a state machine per truck — "
      "`TRAVEL_EMPTY` → `LOAD` → `TRAVEL_LOADED`, with GPS-sourced geofence enter/exit "
      "events in `TRANSITION_META`. This is a real-time cycle tracker.")
    a("")
    a("Volumes are small, so these look newly commissioned rather than historical.")
    a("")
    a("### `FMS_ENTRY_EXIT_DATA` — 11.6 M rows")
    a("")
    a("`plateNumber`, `startTime`, `endTime`, `truckId`, `pointId`, `pointName`, "
      "`orgName`, `stayTime`. Point-level stay times at named locations "
      "(`KR11KM`, `KR KM13`, `15KM…`). At 11.6 M rows this is the largest dwell "
      "source in either database and was never examined.")
    a("")

    # --------------------------------------------------------------- segments
    a("## Road and segment definitions")
    a("")
    a("| Table | Rows | What it defines |")
    a("|---|---|---|")
    a("| `ALL_HR_KM_SECTIONS` | 27 | Named sections with `KM_START`/`KM_END`, origin, destination |")
    a("| `HAUL_ROAD_STA` | 3,122 | Chainage points every 25 m with WKT `POINT Z` geometry |")
    a("| `DISPATCH ROADS` | 222 | Origin→destination with **per-section distance fractions** across 27 section columns |")
    a("| `RES_SPEED_LIMIT_ZONES` | 27 | Speed limit per segment with `KM_From`/`KM_To` |")
    a("| `FMS_GEOFENCES` | 3,490 | Polygons with `LATLNGS`, `CENTER_LAT/LNG`, `TYPE`, `PIT_ID`, `PILE_ID` |")
    a("")
    a("Segments are defined by **road code + kilometre chainage** (`BLB KM2,5 - KM5,7`, "
      "`TF KM60 - KM68`), consistently across all five tables and matching the "
      "`SEG_ID` vocabulary in `FMS_CONGESTION_SEG`.")
    a("")
    a("`DISPATCH ROADS` is notable: for each origin-destination pair it gives the "
      "**fraction of the haul crossing each named section**. That is a ready-made "
      "route-to-segment decomposition — the missing link for turning segment speeds "
      "into a route-level cycle time.")
    a("")
    a("This is finer than the corridor hard-coded in `simulator_api.py` "
      "(TF 67.8 → KR 39.0 → POS12 27.0 → POS10 17.0 → FENI 0). **Checked "
      "against the database rather than assumed**, and the corridor is exactly "
      "right:")
    a("")
    a("| Corridor landmark | KM | Confirmed by |")
    a("|---|---|---|")
    a("| TF (Tofu) | 67.8 | `HAUL_ROAD_STA` TOFU chainage ends at **67.800** |")
    a("| KR | 39.0 | `TF KM39 - KM45` starts at KR NORTH; KR chainage ends 38.975 |")
    a("| POS 12 | 27.0 | `KR KM26 - KM27` ends at **POS 12** |")
    a("| POS 10 | 17.0 | `KR KM15 - KM17` ends at **POS 10** |")
    a("| FENI 15 | 15.0 | `KR KM12 - KM15` ends at **FENI U** |")
    a("| FENI 0 | 0.0 | `CRD KM0 - KM2,5` starts at **FENI** |")
    a("")
    a("Every landmark in the hard-coded corridor is a named junction in "
      "`ALL_HR_KM_SECTIONS` at the same chainage. The corridor is correct; the "
      "database simply expresses it at 25 m resolution (`HAUL_ROAD_STA`, 3,122 "
      "points) instead of six landmarks.")
    a("")
    a("The full haul road is 8 named roads: TOFU (39.0–67.8), KR (7.9–39.0), "
      "BLB (2.5–19.8), CBB (6.3–17.1), CBBB (14.7–16.8), CRD (0.0–7.9), "
      "HFC (5.5–6.4), CSW (4.0–5.7).")
    a("")

    # ------------------------------------------------------------------- HRM
    a("## HRM / road maintenance")
    a("")
    a("| Table | Rows | Contents |")
    a("|---|---|---|")
    a("| `FMS_HRM_SUPERVISION` (view) | 76,552 | Per-machine work with `LAT`/`LONG`, `SECTIONKM`, `EQUIPMENT_TYPE` (EX/GD), `HOURS`, `DISTANCE_M` |")
    a("| `HRM_INSPECTION` | 30,610 | Road defects by `KM_START`/`KM_END`, `SEVERITY`, `STATUS`, `TYPE` (e.g. BUMPY ROAD), from 2024-10 |")
    a("| `HRM_MAJOR_ROADWORK` | 149 | Roadwork campaigns with KM range, fleet, material, `PERCENTAGE` complete |")
    a("| `HRM_CONTRACT_EQUIPMENT` | 198 | Equipment committed per road section by contractor |")
    a("")
    a("**Yes, HRM GPS exists.** `FMS_HRM_SUPERVISION` has graders (`GD`) and excavators "
      "(`EX`) with coordinates and a section-KM marker showing where they worked, "
      "dated to 2026-07.")
    a("")
    a("`HRM_INSPECTION` is the more interesting one for the simulator: **30,610 "
      "road-condition observations by KM and severity going back to 2024-10**. Road "
      "condition is a plausible driver of cycle-time variance that the current model "
      "does not include at all, and unlike truck count it is not chosen in response "
      "to how the shift is going.")
    a("")

    # ------------------------------------------------------- other candidates
    a("## Other tables worth noting")
    a("")
    a("| Table | Rows | Why it matters |")
    a("|---|---|---|")
    a("| `RES_EMPLOYEES` | 8,958 | Operator identity: `EMPLOYEE_ID`, `CONTRACTOR`, `DIVISION`, `JOB_TITLE`, `GRADE` |")
    a("| `FMS_PLAYBACK_STAY_DATA` | 387,997 | Stay events with `speed`, `maxSpeed`, `limitSpeed`, `mileage`, `driverId` |")
    a("| `FMS_UNIT_INSTALLED` | 1,194 | Which plates have a device fitted, and when it first reported |")
    a("| `DISTANCE_HAULING` | 30,587 | **Real per-haul distances** by origin/destination with supervisor names |")
    a("| `WAITING_TIME` | 878,240 | Already in use: measured load/dump dwell |")
    a("")
    a("`DISTANCE_HAULING` deserves attention. The simulator found `distance_km` to be "
      "a placeholder (57 of 65 routes on a default 25.0 km). This table carries "
      "distances like 44.0, 43.3, 42.5 km per origin-destination pair, dated, with "
      "tonnage and trip counts. It is a candidate replacement for the placeholder.")
    a("")

    # ------------------------------------------------------------- inventory
    a("## Full object inventory")
    a("")
    for db, blk in raw.get("databases", {}).items():
        if "fatal_error" in blk:
            a("### %s — scan failed: %s" % (db, blk["fatal_error"][:120]))
            a("")
            continue
        objs = blk.get("objects", {})
        a("### %s" % db)
        a("")
        counted = sum(1 for v in objs.values() if v.get("row_count") is not None)
        a("%d objects: %d tables, %d views. %d deep-scanned (samples, date "
          "ranges, ID vocabularies); %d have row counts; the rest are views, "
          "which carry no stored count."
          % (blk.get("object_count", len(objs)), blk.get("table_count", 0),
             blk.get("view_count", 0),
             sum(1 for v in objs.values() if v.get("depth") == "deep"), counted))
        a("")
        # Every object with rows, biggest first: this is the map of where the
        # data actually lives, which a column-only listing does not give.
        sized = {k: v for k, v in objs.items() if (v.get("row_count") or 0) > 0}
        if sized:
            a("#### All non-empty objects by size")
            a("")
            a("| Object | Type | Rows | Date range | Cols |")
            a("|---|---|---|---|---|")
            for k in sorted(sized, key=lambda x: -(sized[x].get("row_count") or 0)):
                v = sized[k]
                dr = v.get("date_range")
                a("| `%s` | %s | %s | %s | %d |"
                  % (k, "view" if v["type"] == "VIEW" else "table",
                     "{:,}".format(v["row_count"]),
                     ("%s → %s" % (dr[0][:10], dr[1][:10]) if dr else "—"),
                     len(v.get("columns", []))))
            a("")
        rest = {k: v for k, v in objs.items() if k not in sized}
        if rest:
            a("#### Empty or view-only objects (columns catalogued)")
            a("")
            a("<details><summary>%d further objects</summary>" % len(rest))
            a("")
            for k in sorted(rest):
                v = rest[k]
                a("- `%s` (%s, %d cols): %s"
                  % (k, "view" if v["type"] == "VIEW" else "table",
                     len(v.get("columns", [])),
                     fmt_cols(v.get("columns", []), limit=12)))
            a("")
            a("</details>")
            a("")
        if blk.get("errors"):
            a("<details><summary>%d objects errored during deep scan</summary>"
              % len(blk["errors"]))
            a("")
            for e in blk["errors"][:60]:
                a("- %s" % e)
            a("")
            a("</details>")
            a("")

    # -------------------------------------------------------------- what next
    a("## What this means for the simulator")
    a("")
    a("Nothing in the codebase was changed by this scan. These are the corrections "
      "and opportunities it surfaces, in priority order.")
    a("")
    a("1. **Correct the GPS claim.** \"0 of 940 haul trucks in the GPS feed\" is wrong "
      "and appears in `README.md`, `MODEL_FINDINGS.md` and the `/api/simulate` "
      "`model_limits` payload. The accurate statement is that haul trucks are "
      "instrumented at 3-second resolution, but GPS retention is days, so it does not "
      "overlap the historical trips already extracted.")
    a("2. **Validate the dwell estimate against `FMS_GEOFENCE_VISITS`.** 15,100 "
      "measured pit visits, median 14.1 min. The simulator currently apportions dwell "
      "for 75% of trips; this is an independent check on that apportionment.")
    a("3. **Re-test congestion on `FMS_CONGESTION_SEG`.** The congestion effect was "
      "declared unidentifiable from weighbridge data. That table has measured speed "
      "*and* `TRUCK_N` per segment-hour — the cleanest possible test of whether more "
      "trucks means slower, and it does not depend on deployment being exogenous in "
      "the same way. This could overturn the second published negative.")
    a("4. **Replace the placeholder `distance_km`** with `DISTANCE_HAULING`.")
    a("5. **Consider `HRM_INSPECTION` road condition** as a cycle-time feature.")
    a("6. **`FMS_TRUCK_ASSIGNMENTS` gives excavator identity** in weighbridge truck "
      "format, contradicting the earlier namespace-split blocker.")
    a("")
    a("Item 3 is the one that could most change the product, and it should be tested "
      "the same way as before: measure first, check the sign, and publish whichever "
      "answer the data gives.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote %s (%d lines)" % (OUT, len(L)))


if __name__ == "__main__":
    main()
