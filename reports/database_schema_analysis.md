# Database Schema Analysis

*Read-only scan of `WBN_DATABASE` and `FMS_DB`. Generated 2026-07-30 02:52 UTC by `scripts/scan_databases.py` + `scripts/write_schema_report.py`. No table was created, altered or dropped.*

## The headline: a published claim was wrong

The simulator states **"0 of 940 haul trucks appear in the GPS feed"** and concludes segment-level speed is unavailable. **That claim is wrong, and the site operator was right to challenge it.**

What went wrong: the check matched `FMS_PLAYBACK_TRACK_DATA.plateNumber` against weighbridge truck IDs. On *that table* the answer really is zero — its 219 plates are `SS###`/`E###` support units. The error was generalising one table's answer to the whole database, and reading the Chinese department strings (`工程`/`后勤`) as vehicle classes. They are org units, and as the operator said, logistics is a contractor grouping, not a vehicle type.

What the data actually shows:

| Evidence | Finding |
|---|---|
| `FMS_EQUIPMENTS.plateNumber` vs weighbridge truck IDs | **945 of 1,411 match** |
| `FMS_GEOFENCE_VISITS` rows typed `Haul Truck` | **43,763 rows, 644 units** |
| of those units, present in the weighbridge | **613 (95.2%)** |
| Haul-truck devices with rows in `FMS_GPS_Historical` | **455 of 945 (48.1%)** |
| Haul-truck devices in `FMS_PLAYBACK_TRACK_24H` | **479 of 945 (50.7%)** |
| `FMS_CONGESTION_SEG` road segments with measured speed | **95 segments** |
| GPS sampling interval (median) | **3 seconds** |

Haul trucks **are** GPS-instrumented, at 3-second resolution, and segment-level speeds already exist pre-aggregated in `FMS_CONGESTION_SEG`.

### The real constraint is retention, not instrumentation

| Table | Coverage | Overlaps trip extract (2025-12-27 → 2026-07-09)? |
|---|---|---|
| `FMS_GPS_Historical` | 2026-07-15 → 2026-07-20 (5 days) | **No** |
| `FMS_PLAYBACK_TRACK_24H` | 2026-07-29 → 2026-07-30 (1 day) | **No** |
| `FMS_CONGESTION_SEG` | 2026-07-15 → 2026-07-30 | **No** |
| `FMS_GEOFENCE_VISITS` | 2025-12-07 → 2026-07-30, **89 distinct days** | **YES** |
| `FMS_ENTRY_EXIT_DATA` | 2026-05-30 → 2026-07-30 | partial |
| `FMS_PLAYBACK_TRACK_DATA` | 2026-03-21 → 2026-07-30 | yes, but **no haul trucks** |

Two different situations, and the distinction matters:

- **Raw GPS tracks and derived segment speeds** are a rolling live feed with days of retention. They cannot retro-fit segment speeds onto the historical trips already extracted. They can drive a forward-looking simulator, and they accumulate from now on.
- **`FMS_GEOFENCE_VISITS` is different.** It spans 2025-12-07 to 2026-07-30 across 89 distinct days, which **overlaps the trip extract**. Haul-truck dwell at named pits is therefore available for the same period the simulator was trained on, and can be joined to existing trips today.

So the corrected statement is: **haul trucks are GPS-instrumented at 3-second resolution; segment-level speed exists but only for the last two weeks; and measured pit dwell for haul trucks is available across the training period.**

This is a materially better position than "no GPS on haul trucks", and the simulator's documentation should be corrected.

## Tables that change what the simulator can do

### `FMS_GEOFENCE_VISITS` — measured dwell at named pits

59,358 rows. Columns: `UNIT_ID`, `UNIT_TYPE`, `ORG_NAME`, `GEOFENCE_ID`, `GEOFENCE_NAME`, `GEOFENCE_TYPE`, `ENTER_TS`, `EXIT_TS`, `DURATION_SEC`, `ENTER_LAT/LNG`, `EXIT_LAT/LNG`, `STATUS`, `SOURCE`.

This is the single most valuable table found. It records, per haul truck, **enter and exit timestamps with a computed duration** at typed geofences.

| Unit type | Rows |   | Geofence type | Rows |
|---|---|---|---|---|
| Haul Truck | 43,763 | | pit | 21,087 |
| Excavator | 3,605 | | weighbridge | 19,378 |
| Grader | 1,604 | | water | 10,024 |
| Compactor | 1,120 | | sampling | 6,447 |
| Fuel Truck | 834 | | dumping | 1,202 |
| Light Vehicle | 329 | | loading | 835 |

Coverage is **2025-12-07 to 2026-07-30 across 89 distinct days**, which overlaps the trip extract. 15,100 haul-truck visits to **pit** geofences across BLB, CBB, KR and TF, median dwell **14.1 min**.

That figure is worth comparing to what the simulator currently uses. Measured loading dwell from `WAITING_TIME` is 9.0 min at the median; these geofence visits give 14.1 min. The two measure slightly different things (a geofence is larger than a shovel, so it includes the approach and the queue), and the gap between them is itself informative: **roughly 5 minutes of queue and manoeuvring per load** that the shovel-side measurement does not see.

It also carries `UNIT_TYPE`, which answers a question the simulator could not previously answer: **which units are haul trucks**, without guessing from department names.

### `FMS_CONGESTION_SEG` — segment-level speed, already aggregated

34,988 rows, 2026-07-15 → 2026-07-30. Columns: `HOUR_TS`, `SEG_ID`, `DIR`, `SUM_SPD`, `FIX_N`, `TRUCK_N`, `SUM_TRAV_MS`, `TRAV_N`.

- **95 distinct segments**, named by road and kilometre: `BLB KM17-18`, `CBB KM10-11`, `CRD KM0-1`, `KR KM…`, `TF KM…`
- **Directional** (`up` / `down`), so loaded and empty legs are separable
- Mean speed per segment-hour = `SUM_SPD / FIX_N`: median **17.2 km/h**, p5 7.6, p95 26.5 — physically sensible for a haul road
- `TRUCK_N` is the count of units contributing that hour: median 10, max 69
- `SUM_TRAV_MS` / `TRAV_N` give measured **traverse time** per segment

Derived from the GPS feed. This is exactly the segment-level product the simulator was told it could not have, and it inherits the same 2-week retention.

### `FMS_TRUCK_ASSIGNMENTS` / `FMS_HAUL_CYCLES` / `FMS_TRUCK_CYCLES`

- `FMS_TRUCK_ASSIGNMENTS` (408 rows): `PLAN_DATE`, `SHIFT`, `TRUCK`, `PILE`, **`EXCAVATOR`**, `PIT`, `MATERIAL`, `DESTINATION`. Excavator identity per truck-shift — the loader assignment previously reported as blocked by an `AD4059`/`A342` namespace split. Here the truck is `R707`, matching weighbridge format directly.
- `FMS_HAUL_CYCLES` (288 rows): completed cycles with `TRUCK_PLATE`, `EXCAVATOR`, `DUMP_TS`, `MATERIAL` (Waste/…).
- `FMS_TRUCK_CYCLES` (1 row, live state): a state machine per truck — `TRAVEL_EMPTY` → `LOAD` → `TRAVEL_LOADED`, with GPS-sourced geofence enter/exit events in `TRANSITION_META`. This is a real-time cycle tracker.

Volumes are small, so these look newly commissioned rather than historical.

### `FMS_ENTRY_EXIT_DATA` — 11.6 M rows

`plateNumber`, `startTime`, `endTime`, `truckId`, `pointId`, `pointName`, `orgName`, `stayTime`. Point-level stay times at named locations (`KR11KM`, `KR KM13`, `15KM…`). At 11.6 M rows this is the largest dwell source in either database and was never examined.

## Road and segment definitions

| Table | Rows | What it defines |
|---|---|---|
| `ALL_HR_KM_SECTIONS` | 27 | Named sections with `KM_START`/`KM_END`, origin, destination |
| `HAUL_ROAD_STA` | 3,122 | Chainage points every 25 m with WKT `POINT Z` geometry |
| `DISPATCH ROADS` | 222 | Origin→destination with **per-section distance fractions** across 27 section columns |
| `RES_SPEED_LIMIT_ZONES` | 27 | Speed limit per segment with `KM_From`/`KM_To` |
| `FMS_GEOFENCES` | 3,490 | Polygons with `LATLNGS`, `CENTER_LAT/LNG`, `TYPE`, `PIT_ID`, `PILE_ID` |

Segments are defined by **road code + kilometre chainage** (`BLB KM2,5 - KM5,7`, `TF KM60 - KM68`), consistently across all five tables and matching the `SEG_ID` vocabulary in `FMS_CONGESTION_SEG`.

`DISPATCH ROADS` is notable: for each origin-destination pair it gives the **fraction of the haul crossing each named section**. That is a ready-made route-to-segment decomposition — the missing link for turning segment speeds into a route-level cycle time.

This is finer than the corridor hard-coded in `simulator_api.py` (TF 67.8 → KR 39.0 → POS12 27.0 → POS10 17.0 → FENI 0). **Checked against the database rather than assumed**, and the corridor is exactly right:

| Corridor landmark | KM | Confirmed by |
|---|---|---|
| TF (Tofu) | 67.8 | `HAUL_ROAD_STA` TOFU chainage ends at **67.800** |
| KR | 39.0 | `TF KM39 - KM45` starts at KR NORTH; KR chainage ends 38.975 |
| POS 12 | 27.0 | `KR KM26 - KM27` ends at **POS 12** |
| POS 10 | 17.0 | `KR KM15 - KM17` ends at **POS 10** |
| FENI 15 | 15.0 | `KR KM12 - KM15` ends at **FENI U** |
| FENI 0 | 0.0 | `CRD KM0 - KM2,5` starts at **FENI** |

Every landmark in the hard-coded corridor is a named junction in `ALL_HR_KM_SECTIONS` at the same chainage. The corridor is correct; the database simply expresses it at 25 m resolution (`HAUL_ROAD_STA`, 3,122 points) instead of six landmarks.

The full haul road is 8 named roads: TOFU (39.0–67.8), KR (7.9–39.0), BLB (2.5–19.8), CBB (6.3–17.1), CBBB (14.7–16.8), CRD (0.0–7.9), HFC (5.5–6.4), CSW (4.0–5.7).

## HRM / road maintenance

| Table | Rows | Contents |
|---|---|---|
| `FMS_HRM_SUPERVISION` (view) | 76,552 | Per-machine work with `LAT`/`LONG`, `SECTIONKM`, `EQUIPMENT_TYPE` (EX/GD), `HOURS`, `DISTANCE_M` |
| `HRM_INSPECTION` | 30,610 | Road defects by `KM_START`/`KM_END`, `SEVERITY`, `STATUS`, `TYPE` (e.g. BUMPY ROAD), from 2024-10 |
| `HRM_MAJOR_ROADWORK` | 149 | Roadwork campaigns with KM range, fleet, material, `PERCENTAGE` complete |
| `HRM_CONTRACT_EQUIPMENT` | 198 | Equipment committed per road section by contractor |

**Yes, HRM GPS exists.** `FMS_HRM_SUPERVISION` has graders (`GD`) and excavators (`EX`) with coordinates and a section-KM marker showing where they worked, dated to 2026-07.

`HRM_INSPECTION` is the more interesting one for the simulator: **30,610 road-condition observations by KM and severity going back to 2024-10**. Road condition is a plausible driver of cycle-time variance that the current model does not include at all, and unlike truck count it is not chosen in response to how the shift is going.

## Other tables worth noting

| Table | Rows | Why it matters |
|---|---|---|
| `RES_EMPLOYEES` | 8,958 | Operator identity: `EMPLOYEE_ID`, `CONTRACTOR`, `DIVISION`, `JOB_TITLE`, `GRADE` |
| `FMS_PLAYBACK_STAY_DATA` | 387,997 | Stay events with `speed`, `maxSpeed`, `limitSpeed`, `mileage`, `driverId` |
| `FMS_UNIT_INSTALLED` | 1,194 | Which plates have a device fitted, and when it first reported |
| `DISTANCE_HAULING` | 30,587 | **Real per-haul distances** by origin/destination with supervisor names |
| `WAITING_TIME` | 878,240 | Already in use: measured load/dump dwell |

`DISTANCE_HAULING` deserves attention. The simulator found `distance_km` to be a placeholder (57 of 65 routes on a default 25.0 km). This table carries distances like 44.0, 43.3, 42.5 km per origin-destination pair, dated, with tonnage and trip counts. It is a candidate replacement for the placeholder.

## Full object inventory

### WBN_DATABASE

579 objects: 161 tables, 418 views. 76 deep-scanned (samples, date ranges, ID vocabularies); 169 have row counts; the rest are views, which carry no stored count.

#### All non-empty objects by size

| Object | Type | Rows | Date range | Cols |
|---|---|---|---|---|
| `EQUIPMENTS_HOURLY_STATUS` | table | 16,551,395 | 1899-12-30 → 2026-07-29 | 20 |
| `EQUIPMENTS_HOURLY_ACTIVITIES` | table | 4,681,072 | 1899-12-30 → 2026-07-28 | 21 |
| `BLOCK_INDESIGN` | table | 4,288,722 | — | 13 |
| `EQUIPMENTS_STATUS` | table | 3,680,170 | 2024-10-01 → 2026-07-29 | 22 |
| `HAULAGE` | table | 3,509,230 | — | 24 |
| `S123_STOCK_SHAPE_OLD` | table | 1,732,432 | — | 12 |
| `HAULAGE_IWIP_EXT` | table | 1,508,871 | 2026-05-30 → 2026-07-11 | 28 |
| `RSF_HAULING_DATA` | table | 1,143,509 | — | 18 |
| `WAITING_TIME` | table | 878,240 | 2025-01-01 → 2026-07-22 | 24 |
| `HAULAGE_IWIP` | table | 572,742 | 2025-12-27 → 2026-07-08 | 35 |
| `TOS_STATUS` | table | 548,621 | — | 6 |
| `DAY_WORKS` | table | 495,592 | — | 27 |
| `PRODUCTION_ACTIVITY_PIT` | table | 450,615 | — | 34 |
| `PRODUCTION_PIT_OLD` | table | 407,593 | — | 23 |
| `ASSAYS` | table | 396,428 | — | 36 |
| `PP_MINED_NEW_RECONCIL_MENG` | table | 308,918 | — | 11 |
| `SAMPLE` | table | 249,620 | — | 26 |
| `auto_edge_HAULAGE` | table | 246,971 | — | 11 |
| `DISPATCH WBN ACTUAL` | table | 212,890 | 2024-10-01 → 2026-07-22 | 14 |
| `auto_node_STOCK_ID` | table | 186,833 | — | 29 |
| `POS FOLLOW UP` | table | 177,744 | — | 9 |
| `autoQC_CF_BM_TOS_HISTORY_OLD` | table | 175,475 | — | 17 |
| `CRUSHER_STOCKPILE_OUTPUT_DATA` | table | 156,726 | — | 13 |
| `QC PIT-TOS OMR` | table | 149,360 | — | 19 |
| `autoBLOCK_PROD_QC_BM_TOS_CORR` | table | 132,306 | — | 18 |
| `CONTRACTOR FOLLOW UP` | table | 130,873 | — | 25 |
| `FeNi Reclaiming Plan` | table | 128,118 | — | 10 |
| `MINING_PLAN_WEEKLY` | table | 124,358 | — | 34 |
| `SAMPLING_CONTRACTOR` | table | 123,130 | — | 15 |
| `TOS_PILE_INFO` | table | 97,738 | — | 6 |
| `autoQC_STOCK_ALL_VIA_ALL` | table | 93,116 | — | 93 |
| `TOS FOLLOW` | table | 87,045 | — | 13 |
| `OMR_QC` | table | 85,995 | — | 15 |
| `DISPATCH FeNi PLAN & ACTUAL` | table | 84,384 | 2024-10-01 → 2026-07-29 | 11 |
| `DISTANCE_MINING` | table | 83,462 | — | 14 |
| `DISPATCH FENI & WBN ACTUAL DT SHIFT` | view | 71,423 | 2023-12-23 → 2026-07-28 | 10 |
| `DAILY_QUALITY_DISPATCH` | table | 66,774 | 2025-02-27 → 2026-07-22 | 19 |
| `DAILY_QUALITY_DISPATCH_TREATED` | view | 66,774 | 2025-02-27 → 2026-07-22 | 22 |
| `PILES_SHARED_FENI` | table | 66,571 | — | 7 |
| `EXC_TRIMMING` | table | 59,362 | — | 9 |
| `RAINFALL` | table | 55,934 | — | 9 |
| `SURVEY POS` | table | 50,385 | — | 19 |
| `HAULAGE_M_DOME_2026_IWIP_PLAN` | table | 44,289 | — | 15 |
| `autoTOS_SURVEY_ESTIMATION` | table | 43,187 | — | 19 |
| `DISPATCH FENI ACTUAL Treated 0` | view | 41,678 | 2024-10-01 → 2026-07-28 | 7 |
| `QC_TOS_DATA_ML` | table | 38,001 | — | 33 |
| `PP_REMAIN_INPIT_MINEOUT` | table | 36,206 | — | 13 |
| `PP_MINED_YTD_OK` | table | 35,922 | — | 12 |
| `TSS` | table | 35,218 | — | 19 |
| `HRM_INSPECTION` | table | 30,610 | 2024-10-01 → 2025-12-11 | 14 |
| `DISTANCE_HAULING` | table | 30,587 | — | 12 |
| `CRUSHER LOIPOLOY` | table | 27,353 | — | 17 |
| `DISPATCH WBN PLAN SHIFT` | table | 27,058 | 2024-10-01 → 2026-07-22 | 15 |
| `DAILY_QUALITY_DISPATCH_GROUP` | view | 26,686 | 2025-02-27 → 2026-07-22 | 3 |
| `QC SAMPLE DATA` | table | 25,425 | — | 15 |
| `DISPATCH RESULTS DISTANCE` | view | 25,213 | 2025-01-01 → 2026-07-28 | 38 |
| `VERY VERY SHORT TERM PIT SERVICE` | table | 21,064 | — | 16 |
| `ASSAYS_NITON_GGSHEET` | table | 19,700 | — | 25 |
| `PRODUCTION_PIT_PRELIM_auto` | table | 15,887 | — | 19 |
| `STOCK_STATUS` | table | 14,720 | — | 12 |
| `blasting_drilling` | table | 14,648 | — | 22 |
| `WBN_DATABASE_ST_LOG_ON` | table | 13,646 | — | 3 |
| `OLD_VERY_SHORT_TERM` | table | 13,470 | — | 16 |
| `HAULAGE_REPORT` | table | 13,459 | — | 16 |
| `QUARRY PRODUCTION` | table | 12,646 | — | 14 |
| `PROD VERY VERY SHORT TERM` | table | 11,180 | — | 29 |
| `RSF_SURVEY` | table | 9,103 | — | 20 |
| `ARCGIS_EQUIPMENTS_INFO_APP` | view | 8,338 | 1970-01-01 → 2026-07-11 | 14 |
| `autoQC_CF_BM_TOS` | table | 8,249 | — | 20 |
| `RECLASSIFICATION` | table | 7,789 | — | 5 |
| `EQUIPMENTS` | table | 7,221 | — | 15 |
| `FENI_REQUESTS` | table | 7,196 | — | 7 |
| `QS_LIMS_RIM_CK` | table | 6,131 | — | 19 |
| `DARONNE_Htemp` | table | 5,812 | — | 19 |
| `EQUIPMENTS_OLD` | table | 5,658 | — | 14 |
| `WMT_FOR_3RD_PARTY` | table | 5,529 | — | 12 |
| `CALENDAR_SHIFT` | view | 5,330 | 2019-09-12 → 2026-12-28 | 3 |
| `BATCH` | table | 4,931 | — | 3 |
| `DRAFTS` | table | 4,848 | — | 30 |
| `TOS_SURVEY` | table | 4,804 | — | 18 |
| `S123_STOCK_SHAPE` | table | 4,785 | — | 11 |
| `STOCK_STATUS_HAULAGE_GGSHEET` | table | 4,750 | — | 17 |
| `STOCK_REQUESTS` | table | 4,735 | — | 9 |
| `3RD_PARTY_ACTIVITIES_RECLAIM` | table | 4,162 | — | 16 |
| `REQUEST` | table | 3,920 | — | 6 |
| `ORE STOCK SALES` | table | 3,800 | — | 21 |
| `S123_TOS_STATUS` | table | 3,589 | — | 11 |
| `CRUSHER_BLENDING_DATA` | table | 3,332 | — | 11 |
| `3RD_PARTY_ACTIVITIES` | table | 3,318 | — | 15 |
| `HAUL_ROAD_STA` | table | 3,122 | — | 11 |
| `Calendar_For_Exploitation` | table | 2,665 | — | 7 |
| `S123_ENVIRO_TSS` | table | 2,366 | — | 33 |
| `MINING_PLAN_3MRMP` | table | 2,295 | — | 45 |
| `blasting_parameters` | table | 2,081 | — | 20 |
| `EQUIPMENTS_PLAN` | table | 2,071 | 2025-12-29 → 2026-05-14 | 12 |
| `Calendar_Svy_topo_by_deposit` | table | 1,839 | — | 5 |
| `DAY_WORKS_PLAN_DAILY` | table | 1,773 | — | 17 |
| `ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE` | table | 1,585 | — | 7 |
| `RSF_PER_LOCATION` | table | 1,489 | — | 15 |
| `CLASS2025` | table | 1,438 | — | 7 |
| `CONSOLIDATED SURVEY` | table | 1,188 | — | 15 |
| `WATER_MANAGEMENT` | table | 1,074 | — | 12 |
| `QUARRY_PLAN` | table | 1,060 | — | 11 |
| `OLD_prod_correction_factor_ACCESS` | table | 957 | — | 6 |
| `ROLLING_MINE_PLAN` | table | 834 | — | 20 |
| `IWIP_REQUESTS_DATE` | table | 772 | — | 3 |
| `TRANSHIPMENT_WBN_ORE` | table | 573 | — | 7 |
| `ID_DT_HUAFEI` | table | 485 | — | 1 |
| `SUMMARY_SURVEY` | table | 460 | — | 12 |
| `BLASTING_PROD` | table | 433 | — | 12 |
| `DISPATCH_PLAN_WB` | table | 432 | 2026-01-07 → 2026-07-22 | 15 |
| `COLOR_CHEMICAL` | table | 404 | — | 4 |
| `WBN_DATABASE_ESSENTIALS` | table | 334 | — | 3 |
| `autoQC_PLAN_NI_CF_OLD` | table | 264 | — | 21 |
| `DISPATCH HAULAGE TF` | table | 264 | — | 5 |
| `DISPATCH ROADS OLD` | table | 254 | — | 36 |
| `autoHAULAGE_VS_PROD_MONTHLY_CF` | table | 223 | — | 6 |
| `DISPATCH ROADS` | table | 222 | — | 33 |
| `HRM_CONTRACT_EQUIPMENT` | table | 198 | — | 8 |
| `PROJECTS_SUPERVISION` | table | 198 | — | 23 |
| `MBAR` | table | 173 | — | 12 |
| `HRM_MAJOR_ROADWORK` | table | 149 | 2024-10-15 → 2024-11-03 | 11 |
| `LME` | table | 145 | — | 4 |
| `LME_GOLD` | table | 143 | — | 2 |
| `TSS_POINT` | table | 121 | — | 36 |
| `TOS_DUMP_COORDINATES` | table | 118 | — | 7 |
| `TSS_CROSSTABLE` | table | 109 | — | 5 |
| `MINING_FLASH_REPORT_FLEET_PROD` | table | 108 | — | 8 |
| `MINING_FLASH_REPORT_EQUIPMENT` | table | 102 | 2025-11-28 → 2025-11-30 | 9 |
| `BLASTING_REMAINING` | table | 98 | — | 7 |
| `CONTRACTOR_DEPOSIT` | table | 84 | — | 4 |
| `EQUIPMENTS_WORKS` | table | 82 | 2024-09-06 → 2024-10-14 | 14 |
| `WBN_DATABASE_PROCEDURE_QUEUE` | table | 79 | — | 3 |
| `TEAM_PLAN` | table | 78 | — | 8 |
| `COMPANIES` | table | 73 | — | 7 |
| `DARONNEtemp` | table | 61 | — | 3 |
| `Ni_COLOR` | table | 45 | — | 3 |
| `MINING_FLASH_REPORT_PRODUCTION` | table | 42 | — | 8 |
| `ACTIVITIES_MAT` | table | 39 | — | 4 |
| `LOCATION_WB_SH` | table | 39 | — | 6 |
| `DT_DENSITY_HR_MODEL$` | table | 37 | — | 15 |
| `CHECK_BACKCHARGE_HAULAGE_IWIP` | view | 35 | — | 4 |
| `TEAM` | table | 34 | — | 5 |
| `MINING_EQ_TARGET_3MRMP` | table | 30 | — | 5 |
| `ALL_HR_KM_SECTIONS` | table | 27 | — | 8 |
| `ASSAY_CLASS` | table | 27 | — | 8 |
| `SHAPE_STOCK_AREA` | table | 26 | — | 5 |
| `HRM_REQUEST_MATERIAL` | table | 25 | 2024-11-08 → 2024-11-09 | 10 |
| `TEAM_FB` | table | 25 | — | 6 |
| `POS POSSIBILITY For HAULAGE` | table | 23 | — | 3 |
| `REQUEST_SALES_LATE_2025` | table | 18 | — | 3 |
| `BLOCK_ID_XYPARAM` | table | 16 | — | 8 |
| `CRUSHER_SURVEY_LOYPOLOY` | table | 16 | — | 13 |
| `ACTIVITIES` | table | 13 | — | 3 |
| `HAULAGE CONTRACTORS` | table | 11 | — | 2 |
| `SUPERVISION_SAFETY_ACTIONS` | table | 6 | — | 23 |
| `CRUSHER_CF` | table | 3 | — | 3 |
| `HAULAGE_ADJ` | table | 3 | — | 8 |

#### Empty or view-only objects (columns catalogued)

<details><summary>421 further objects</summary>

- `3rd_PARTY_DUPLICATES_ANALYSIS` (view, 37 cols): `DOME_STATUS` varchar(4), `ANALYSIS_DATE` date, `CONTRACTOR` nvarchar(50), `DOME` nvarchar(50), `SUBLOT` int, `MC` float, `Ni` float, `Co` float, `MgO` float, `CaO` float, `Fe2O3` float, `SiO2` float, … +25 more
- `ASSAYS CONSOLIDATED` (view, 16 cols): `BLOCK ID` nvarchar(260), `Ni` float, `Fe` float, `Co` float, `Al2O3` int, `CaO` int, `Cr2O3` int, `Fe2O3` int, `MgO` float, `MnO` int, `P2O5` float, `SiO2` float, … +4 more
- `ASSAYS CONSOLIDATED VIA BM` (view, 16 cols): `BLOCK ID` nvarchar(260), `Ni` float, `Fe` float, `Co` float, `Al2O3` int, `CaO` int, `Cr2O3` int, `Fe2O3` int, `MgO` float, `MnO` int, `P2O5` float, `SiO2` float, … +4 more
- `ASSAYS SAMPLING BRIDGE` (view, 38 cols): `DOME_STATUS` varchar(4), `CONTRACTOR_STATUS` varchar(4), `DATE` date, `JOB_ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `TYPE_ASSAYS` nvarchar(50), `DOME` nvarchar(50), `ARRIVAL_DATE` date, `ANALYSIS_DATE` date, `SUBLOT` int, `MC` float, `Ni` float, … +26 more
- `ASSAYS SAMPLING BRIDGE FILTERED` (view, 38 cols): `DOME_STATUS` varchar(4), `CONTRACTOR_STATUS` varchar(4), `DATE` date, `JOB_ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `TYPE_ASSAYS` nvarchar(50), `DOME` nvarchar(50), `ARRIVAL_DATE` date, `ANALYSIS_DATE` date, `SUBLOT` int, `MC` float, `Ni` float, … +26 more
- `ASSAYS SAMPLING BRIDGE RAW DATA` (view, 40 cols): `DOME_STATUS` varchar(4), `CONTRACTOR_STATUS` varchar(4), `DATE` date, `DATE_PR` int, `JOB_ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `TYPE_ASSAYS` nvarchar(50), `DOME` nvarchar(50), `ARRIVAL_DATE` date, `ANALYSIS_DATE` date, `SUBLOT` int, `MC` float, … +28 more
- `ASSAYS TOS` (view, 30 cols): `ID` int, `SAMPLE ID` nvarchar(50), `BLOCK ID` nvarchar(50), `Ni` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `MgO` float, `MnO` float, `P2O5` float, … +18 more
- `ASSAYS TOS FILTERED` (view, 21 cols): `DATE_TOS` date, `BLOCK ID` nvarchar(50), `Ni` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `Fe` float, `MgO` float, `MnO` float, `P2O5` float, … +9 more
- `ASSAYS_MISSING_` (view, 36 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE_RECEIVED` date, `DATE_ANALYSIS` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `SAMPLE_ID` nvarchar(50), `SAMPLE_JOB` nvarchar(50), `STOCK_TYPE` nvarchar(50), … +24 more
- `ASSAYS_MISSING_2` (view, 1 cols): `ORIGIN_ID` varchar(9)
- `ASSAYS_NITON_CLEAN` (view, 5 cols): `PILE_ID` nvarchar(50), `DATE ANALYSIS` date, `NTN_MC` float, `NTN_Ni` float, `NTN_Fe` float
- `ASSAYS_NONULL` (view, 39 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE_RECEIVED` date, `DATE_ANALYSIS` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `SAMPLE_ID` nvarchar(50), `SAMPLE_JOB` nvarchar(50), `STOCK_TYPE` nvarchar(50), … +27 more
- `ASSAYS_PDF` (view, 38 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE_RECEIVED` date, `DATE_ANALYSIS` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `SAMPLE_ID` nvarchar(50), `SAMPLE_JOB` nvarchar(50), `STOCK_TYPE` nvarchar(50), … +26 more
- `ASSAYS_YARD_ORIGINAL_DOME` (view, 25 cols): `CONTRACTOR` nvarchar(101), `DATE` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `STOCK_ID` nvarchar(255), `STOCK_ID_LEFT` nvarchar(255), `STOCK_ID_RIGHT` nvarchar(255), `STOCK_ID_MMYY` varchar(4), `ORIGINAL_STOCK` nvarchar(255), `IS_ORIGINAL` varchar(3), `RIT` float, `WMT` float, … +13 more
- `ASSAY_CLASS_IN` (view, 9 cols): `date` date, `date_end` date, `cat` nvarchar(255), `material` nvarchar(255), `element` nvarchar(255), `ore_class` nvarchar(255), `ore_class_description` nvarchar(255), `grade_min` float, `grade_max` float
- `ASSAY_PROGRESS` (view, 28 cols): `DATE` date, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `ASSAY_CONTRACTOR` nvarchar(50), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ASSAY_ACTIVITY` nvarchar(50), … +16 more
- `ATC_ORACLE_ASSAYS` (view, 24 cols): `Kode Sampel` varchar(80), `Batch` varchar(400), `Entrustment Date` varchar(10), `Reporting Date` varchar(10), `Entrusting Department` nvarchar(30), `Ni` varchar(40), `Co` varchar(40), `AL2O3` varchar(40), `CaO` varchar(40), `Cr2O3` varchar(40), `Fe2O3` varchar(40), `TFe` varchar(40), … +12 more
- `AVG_RAIN_BY_DATE_AREA` (view, 8 cols): `Year` float, `Month` float, `Week` float, `DATE` date, `Area` nvarchar(255), `H2O` float, `RF_H2O_MONTHLY` float, `RF_H2O_WEEKLY` float
- `AVG_RAIN_BY_DATE_AREA_RAW` (view, 8 cols): `Year` int, `Month` int, `Week` float, `DATE` date, `Area` nvarchar(255), `H2O` float, `RF_H2O_MONTHLY` float, `RF_H2O_WEEKLY` float
- `AVG_RAIN_BY_DAY_ALL_AREA` (view, 2 cols): `DATE` date, `DAILY_ALL_AREA_AVG_mmH2O` float
- `BATCH COMPOSITES` (view, 15 cols): `MaxOfDate` date, `BATCH ID` nvarchar(255), `Ni` float, `Fe` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `MgO` float, `MnO` float, `P2O5` float, … +3 more
- `BLOCK_CLASS_OF_TOS_PILE` (view, 3 cols): `TOS_PILE` nvarchar(255), `BM_MIX_DEGREE` int, `BM_MIX_CLASS` nvarchar(-1)
- `BLOCK_OF_TOS_PILE` (view, 2 cols): `TOS_PILE` nvarchar(255), `BLOCKS` nvarchar(-1)
- `BLOCK_PROD_FOR_PROD` (view, 10 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `shift` float, `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(767), `MATERIAL` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `RIT` float, `WMT` float
- `BLOCK_PROD_QC_BM_TOS` (view, 63 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `DEPOSIT` nvarchar(255), `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `block_ID_2` nvarchar(255), `RIT` float, … +51 more
- `BLOCK_PROD_QC_BM_TOS_CORR` (view, 66 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `DEPOSIT` nvarchar(255), `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `block_ID_2` nvarchar(255), `MATERIAL` nvarchar(255), … +54 more
- `BLOCK_PROD_QC_BM_TOS_CORR_TARGET` (view, 62 cols): `YEAR` float, `MONTH` float, `WEEK` float, `CONTRACTOR` nvarchar(255), `DATE` datetime, `DEPOSIT` nvarchar(255), `MATERIAL` nvarchar(255), `TARGET_WMT` float, `SHIFT` float, `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), … +50 more
- `BLOCK_PROD_QC_BM_TOS_GROUP` (view, 30 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `DEPOSIT` nvarchar(255), `DESTINATION` varchar(11), `RSAP` varchar(4), `WMT` float, `DMT` float, `TOS_PILE` nvarchar(255), `Ni` float, … +18 more
- `BLOCK_PROD_QC_BM_TOS_GROUP_CAT` (view, 33 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `DEPOSIT` nvarchar(255), `DESTINATION` varchar(11), `WMT` float, `DMT` float, `TOS_PILE` nvarchar(255), `Ni` float, `Fe` float, … +21 more
- `BLOCK_PROD_QC_BM_TOS_GROUP_CAT_CORR` (view, 35 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `DEPOSIT` nvarchar(255), `DESTINATION` varchar(11), `WMT` float, `DMT` float, `MC` float, `TOS_PILE` nvarchar(255), `Ni` float, … +23 more
- `BLOCK_PROD_QC_BM_TOS_OLD` (view, 61 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `DEPOSIT` nvarchar(255), `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `block_ID_2` nvarchar(255), `RIT` float, … +49 more
- `BLOCK_PROD_QC_BM_TOS_SURVEY_ADJ` (view, 66 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `DEPOSIT` nvarchar(255), `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `block_ID_2` nvarchar(255), `MATERIAL` nvarchar(255), … +54 more
- `BLOCK_PROD_TOS` (view, 17 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `RIT` float, `TF` float, `WMT` float, … +5 more
- `BLOCK_PROD_TOS_ASSAYS` (view, 35 cols): `contractor` nvarchar(255), `Date` datetime, `shift` float, `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_id` nvarchar(255), `block_ID_2` nvarchar(255), `CLASS_BM` int, `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), … +23 more
- `BM` (view, 63 cols): `UPDATE_DATE` datetime, `X` float, `Y` float, `Z` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `Deposit` nvarchar(50), `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, … +51 more
- `BM_CARROT2` (view, 8 cols): `DEPOSIT` nvarchar(12), `BLOCK_ID` nvarchar(24), `H2O` float, `Ni` float, `Fe` float, `SiO2` float, `MgO` float, `Co` float
- `BM_ESTIMATION_CONFIDENCE` (view, 6 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(255), `classification_no` float, `block_confidence_dh_close` float
- `BM_KRENE_FOR_RESERVES_LIM` (view, 15 cols): `x` float, `y` float, `z` float, `MATERIAL` varchar(3), `TC` varchar(4), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, `PROP` float, … +3 more
- `BM_KRENE_TREATED_0` (view, 60 cols): `X` float, `y` float, `z` float, `size (X)` int, ` size(Y)` int, ` size(Z)` int, `co_brk` float, `co_fsap` float, `co_lim` float, `co_rsap` float, `co_wst` float, `dd_brk_tc0` float, … +48 more
- `BM_LONG_TERM` (view, 61 cols): `X` float, `Y` float, `Z` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `Deposit` nvarchar(50), `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, … +49 more
- `BM_OK_PREPARED` (view, 80 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(50), `PROP_VHGS` float, `ni_VHGS` float, `fe_VHGS` float, `dd_VHGS` float, … +68 more
- `BM_OK_TREATED_0` (view, 65 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, … +53 more
- `BM_OK_TREATED_1` (view, 29 cols): `X` float, `Y` float, `Z` float, `block_id` nvarchar(50), `MATERIAL` varchar(3), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, `PROP` float, … +17 more
- `BM_OK_TREATED_1_via_OLD_PP_MENG_CONVERTED` (view, 38 cols): `PIT` nvarchar(255), `X` float, `Y` float, `Z` float, `block_id` nvarchar(255), `MATERIAL` varchar(3), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, … +26 more
- `BM_PP_FOR_RECONCIL` (view, 6 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(255), `block_id` nvarchar(255), `pp_inside_pit_clean` float, `pp_mined_clean` float, `pp_remain` float
- `BM_PP_FOR_RECONCIL_LAST_UPDATE` (view, 6 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(255), `block_id` nvarchar(255), `pp_inside_pit_clean` float, `pp_mined_clean` float, `pp_remain` float
- `BM_PP_LAST_ADJUST` (view, 7 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(255), `VOLUME` numeric, `WMT` int, `block_id` nvarchar(255), `ADJUST_WMT` float, `PP_REMAIN_ADJUST` float
- `BM_PRODUCTION` (view, 32 cols): `LAST_UPDATE` datetime, `DEPOSIT` nvarchar(12), `block_id` nvarchar(24), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `VOLUME` float, `MATERIAL_CLASS` nvarchar(12), `DENSITY` float, `WMT` float, `DMT` float, `Al2O3` float, … +20 more
- `BM_RECONCIL_LT_TREATED_0` (view, 65 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` varchar(74), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, … +53 more
- `BM_RECONCIL_LT_TREATED_1` (view, 31 cols): `PIT` nvarchar(255), `X` float, `Y` float, `Z` float, `block_id` nvarchar(255), `MATERIAL` varchar(3), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, … +19 more
- `BM_RECONCIL_TC0` (view, 75 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, `cao_brk` float, `cao_fsap` float, … +63 more
- `BM_RECONCIL_TC0_TREATED_0` (view, 78 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, `cao_brk` float, `cao_fsap` float, … +66 more
- `BM_RECONCIL_TC0_TREATED_1` (view, 23 cols): `PIT` nvarchar(4000), `block_id` nvarchar(255), `MATERIAL` varchar(3), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, `PROP` float, `WD` float, `MgO` float, … +11 more
- `BM_RECONCIL_TC0_TREATED_1_FULL` (view, 29 cols): `PIT` nvarchar(4000), `block_id` nvarchar(255), `MATERIAL` varchar(3), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, `PROP` float, `WD` float, `MgO` float, … +17 more
- `BM_REDUCED_FOR_RECONCIL_GROUP` (view, 40 cols): `LAST_UPDATE` datetime, `DEPOSIT` nvarchar(12), `block_id` nvarchar(24), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `VOLUME` float, `MATERIAL_CLASS` nvarchar(12), `DENSITY` float, `WMT` float, `DMT` float, `Al2O3` float, … +28 more
- `BM_REMAINING_RESERVES_TC0` (view, 20 cols): `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `MATERIAL` varchar(3), `MP` varchar(7), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, `Ni` float, `PROP` float, `WD` float, … +8 more
- `BM_RESSOURCES_KRENE_TC07_TC08` (view, 52 cols): `X` float, `Y` float, `Z` float, `co_brk` float, `co_fsap` float, `co_lim` float, `co_rsap` float, `co_wst` float, `dd_brk_tc0` float, `dd_fsap_tc09` float, `dd_lim_tc07` float, `dd_lim_tc08` float, … +40 more
- `BM_TC0_LAST` (view, 58 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, `cao_brk` float, `cao_fsap` float, … +46 more
- `BM_TC0_REFORMAT_LONG` (view, 22 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `MATERIAL` varchar(4), `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, … +10 more
- `BM_TC0_WMT` (view, 24 cols): `UPDATE_DATE` datetime, `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `WMT` float, `DMT` float, `MATERIAL_CLASS` varchar(12), `MATERIAL` varchar(4), `al2o3` float, `cao` float, … +12 more
- `BM_TC0_WMT_GROUP` (view, 21 cols): `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `MATERIAL_CLASS` varchar(12), `DENSITY` float, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `Co` float, … +9 more
- `BM_VS_ACTUAL_DEST` (view, 11 cols): `YEAR` float, `MONTH` float, `WEEK` float, `block_id` nvarchar(50), `deposit` nvarchar(50), `PROP_SAP` float, `PROP_LIM_ORE` float, `PROP_LIM_WST` float, `RIT_LIM` float, `RIT_SAP` float, `RIT_WST` float
- `CEK_RIT_HAULAGE` (view, 6 cols): `DESTINATION_ID` nvarchar(50), `WMT` float, `RIT` int, `RIT_SAMPLING_CONTRACTOR` float, `RIT_OMR_QC` float, `SUM_DEF` float
- `CF FOR PROD CORR ASSAYS 2` (view, 8 cols): `YEAR` float, `MONTH` float, `contractor` nvarchar(255), `FINAL_RECLASSIFICATION` nvarchar(255), `CF` float, `WMT_SURVEY` float, `BCM_SURVEY` float, `PIT` nvarchar(255)
- `CF_CHECK` (view, 8 cols): `YEAR` float, `MONTH` float, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `MATERIAL` nvarchar(255), `WMT_PROD` float, `WMT_SURVEY` float, `CF` decimal
- `COMPANIES_PLANT_ONLY` (view, 6 cols): `COMPANY` nvarchar(255), `PLANT` nvarchar(255), `PLANT_TYPE` nvarchar(50), `PLANT_LOCATION` nvarchar(50), `PLANT_FULL` nvarchar(306), `PLANT_LOCATION_FULL` nvarchar(101)
- `CONTRACTOR FOLLOW UP DATE 2` (view, 32 cols): `ID` int, `Date` date, `Contractor` nvarchar(255), `Activity` nvarchar(255), `Equipment` nvarchar(255), `EQ_TYPE` varchar(9), `Quantity` float, `PA` float, `Target Fleet` float, `RFU` float, `Breakdown` float, `Act PA` float, … +20 more
- `CONTRACTOR_FOLLOW_UP_DATE` (view, 28 cols): `ID` int, `Date` date, `Contractor` nvarchar(255), `Activity` nvarchar(255), `Equipment` nvarchar(255), `Quantity` float, `PA` float, `Target Fleet` float, `RFU` float, `Breakdown` float, `Act PA` float, `Running Average` float, … +16 more
- `CONTRACTOR_FU_DT_VARIATION` (view, 3 cols): `date` date, `contractor` nvarchar(255), `RFU_VARIATION` float
- `CORPSAMPLEASSAY` (view, 26 cols): `Sampling_Contractor` nvarchar(50), `SAMPLING_DATE` datetime, `SAMPLE_ID` nvarchar(50), `SAMPLE_TYPE` nvarchar(50), `PIT` nvarchar(50), `BLOCK_ID` nvarchar(50), `STOCK_ID` nvarchar(50), `RETURNDATE` date, `ASSAY_TYPE` nvarchar(50), `ACTIVITY` nvarchar(50), `STOCK_TYPE` nvarchar(50), `Ni` float, … +14 more
- `CORRECTIVE_ACTIONS` (table, 12 cols): `id` int, `safety_event_id` int, `action_text` varchar(-1), `status` varchar(50), `severity` varchar(20), `due_date` date, `completed_at` datetimeoffset, `owner_user_id` int, `owner_name` varchar(150), `owner_company` varchar(150), `created_at` datetimeoffset, `updated_at` datetimeoffset
- `CRUSHER_BLENDING_DATA_TREATED` (view, 13 cols): `ID` int, `CRUSHER_LOCATION` nvarchar(50), `DATE` date, `SHIFT` nvarchar(50), `STOCK_LOCATION` nvarchar(50), `PILE_ID` nvarchar(50), `GRANULO` nvarchar(50), `LINE` nvarchar(50), `NB_BUCKET` float, `BF` float, `BCM` float, `STOCK_ID` nvarchar(50), … +1 more
- `CRUSHER_STOCKPILE_OUTPUT_DATA_TREATED` (view, 17 cols): `ID` int, `DATE` datetime, `SHIFT` nvarchar(50), `CONTRACTOR_HAULING` nvarchar(50), `UNIT_ID_HAULER` nvarchar(50), `STOCK_ID` nvarchar(50), `MATERIAL` nvarchar(50), `LINE` nvarchar(50), `ORIGIN` nvarchar(50), `ORIGIN 2` varchar(9), `DESTINATION` nvarchar(50), `DESTINATION 2` nvarchar(50), … +5 more
- `Calendar_last_Survey` (view, 9 cols): `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `exercice` nvarchar(255), `NBDAYS` float, `MONTH_SALES` float, `MATERIAL` nvarchar(50), `SURVEY_DATE` datetime
- `DAILY_STOCK_POS` (view, 36 cols): `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(260), `DATE_REQUEST` datetime, `STOCK_LAST_DATE` datetime, `DOME_RAW` nvarchar(50), `SURVEY_CLASS` nvarchar(10), `REQUEST_DATE` datetime, `REQUEST_PLANT` nvarchar(306), … +24 more
- `DARONNE_CLEAN` (view, 9 cols): `DATE` datetime, `Category` varchar(9), `MATERIAL` varchar(3), `PIT` nvarchar(255), `PIT_CODE` varchar(5), `WMT` float, `Ni` float, `Fe` float, `Co` float
- `DARONNE_HAUL` (view, 25 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `ACTIVITY_TYPE` nvarchar(101), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TRUCK_TYPE` int, `TRUCK_CAPACITY` int, `TRUCK_MODEL` int, `TIME_LOADED` time, `TIME_EMPTY` time, … +13 more
- `DARONNE_HAUL_AVG` (view, 11 cols): `CONTRACTOR` nvarchar(50), `SHIFT` int, `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `ORIGIN_PIT` varchar(5), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `KG_EMPTY` float, `WMT` float
- `DARONNE_LIM` (view, 5 cols): `YEAR` int, `MONTH` int, `PIT` varchar(5), `MATERIAL` varchar(3), `WMT` float
- `DARONNE_QUERY` (view, 21 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` varchar(3), `TRUCK_ID` nvarchar(50), `TIME_LOADED` time, `TIME_EMPTY` time, `RIT` int, `ORIGIN_PIT` varchar(5), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), … +9 more
- `DARONNE_QUERY_LIM` (view, 21 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` varchar(7), `MATERIAL` varchar(3), `TRUCK_ID` nvarchar(50), `TIME_LOADED` time, `TIME_EMPTY` time, `RIT` int, `ORIGIN_PIT` varchar(5), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), … +9 more
- `DATE HAULAGE RECLAIMING` (view, 5 cols): `DOME` nvarchar(50), `START HAULAGE` date, `LAST HAULAGE` date, `START RECLAIMING` date, `LAST RECLAIMING` date
- `DAYWORK_REQUEST` (table, 11 cols): `ID` int, `SECTION` nvarchar(50), `DATE` date, `CONTRACTOR` nvarchar(50), `RESPONSIBLE` nvarchar(50), `TYPE` nvarchar(50), `DESCRIPTION` text(2147483647), `EXCA` int, `DT` int, `DOZER` int, `GRADER` int
- `DAY_WORKS_RIM__NO_FMS` (view, 5 cols): `TYPE` varchar(3), `ACTIVITY_CAT` nvarchar(50), `UNIT_ID` nvarchar(50), `COUNT` int, `INSTALLED` varchar(3)
- `DAY_WORK_wEQ_INFO` (view, 26 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY_CAT` nvarchar(50), `ACTIVITY_DESC` nvarchar(255), `ACTIVITY_PLANNED` nvarchar(50), `ACTIVITY_TIME_START` time, `ACTIVITY_TIME_END` time, `OPERATOR_ID` nvarchar(50), `UNIT_TYPE` nvarchar(50), `UNIT_CLASS` nvarchar(101), `CAPACITY` int, … +14 more
- `DISPATCH RESULTS LITE 2` (view, 43 cols): `YEAR` float, `MONTH` float, `WEEK` float, `COMPANY` nvarchar(50), `ORIGIN raw` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `CONTRACTOR` nvarchar(50), `DATE` date, `TYPE` nvarchar(50), `MATERIAL` nvarchar(50), `NB_SHIFT` int, … +31 more
- `DISPATCH RESULTS LITE 2 SECTION` (view, 46 cols): `YEAR` int, `MONTH` int, `WEEK` int, `COMPANY` int, `ORIGIN raw` nvarchar(255), `ORIGIN` nvarchar(255), `DESTINATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `DATE` datetime, `TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `NB_SHIFT` float, … +34 more
- `DISPATCH RESULTS LITE 2_OLD` (view, 37 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` date, `TYPE` nvarchar(50), `COMPANY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN raw` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `CONTRACTOR` nvarchar(50), `HAULING_WMT` float, … +25 more
- `DISPATCH RESULTS LITE 3` (view, 41 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` date, `TYPE` nvarchar(50), `COMPANY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN raw` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `CONTRACTOR` nvarchar(50), `HAULING_WMT` float, … +29 more
- `DISPATCH ROADS & CALENDAR SHIFT` (view, 39 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `SHIFT` int, `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `KM ORI` float, `KM DEST` float, `DISTANCE GROSS (KM)` float, `CRD KM0 - KM2,5` float, `CRD KM2,5 - KM5,5` float, … +27 more
- `DISPATCH RSF ACTUAL Treated` (view, 10 cols): `DATE` datetime, `SHIFT` int, `CONTRACTOR` varchar(3), `COMPANY` varchar(3), `NB  DT` int, `ACTUAL WMT` float, `ORIGIN` varchar(6), `DESTINATION` varchar(3), `MATERIAL` varchar(7), `TYPE HAULAGE` varchar(7)
- `DISPATCH WBN PLAN` (view, 14 cols): `CONTRACTOR` nvarchar(50), `DATE` date, `TYPE` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `TYPE DATA` nvarchar(50), `COMPANY` nvarchar(50), `DISPATCH ZONE` nvarchar(50), `NB DT` float, `TF` float, `PRODUCTIVITY TARGET 2` float, … +2 more
- `DISPATCH WMT VERY SHORT TERM` (view, 14 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `SHIFT` int, `TYPE` nvarchar(50), `COMPANY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `KM ORI` float, `KM DEST` float, … +2 more
- `DISPATCH_PRODUCTIVITY_TARGET` (view, 3 cols): `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `PRODUCTIVITY` float
- `DISTANCE_HAULING_CHECK` (view, 13 cols): `TABLE` varchar(14), `DATE` datetime, `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(50), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DISTANCE` float, `WMT` float, `RIT` float, `SPV_WBN` nvarchar(255), … +1 more
- `DISTANCE_MINING_CHECK` (view, 16 cols): `TABLE` varchar(14), `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `DIGGER` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL2` nvarchar(255), `DUMPING_AREA` nvarchar(255), `TOS_PILE` nvarchar(255), … +4 more
- `DOME INFO` (view, 10 cols): `DOME` nvarchar(255), `LOCATION` nvarchar(255), `STATUS HAULAGE` varchar(8), `STATUS RECLAIMING` varchar(10), `HIGH TURN` int, `PRIORITY RECLAIM` int, `CLOSE_HAULING` date, `CLOSE_RECLAIMING` date, `MATERIAL` nvarchar(50), `REMARK` nvarchar(255)
- `DOME WBN` (view, 1 cols): `DOME` nvarchar(255)
- `DT_DENSITY_HAULROAD` (view, 33 cols): `DATE` datetime, `TYPE` nvarchar(255), `COMPANY` nvarchar(255), `ORIGIN` nvarchar(255), `DESTINATION` nvarchar(255), `NB_DT` float, `DT ON CRD KM0 - KM2,5` float, `DT ON CRD KM2,5 - KM5,5` float, `DT ON CRD KM5,5 - KM7` float, `DT ON CSW KM3 - KM4` float, `DT ON CSW KM4 - KM5,7` float, `DT ON GOMDI KM3,7 - KM3,8` float, … +21 more
- `DT_DENSITY_HAULROAD_treated` (view, 3 cols): `DATE` date, `SECTION_NAME` nvarchar(4000), `Total_DT` float
- `DT_DENSITY_HAULROAD_treated2` (view, 5 cols): `DATE` date, `SECTION_NAME` nvarchar(4000), `APPROX_DISTANCE` float, `Total_DT` float, `DT/KM` float
- `DT_DENSITY_Haulage_Reclaiming` (view, 5 cols): `DATE` date, `SECTION_NAME` nvarchar(4000), `APPROX_DISTANCE` float, `Total_DT` float, `DT/KM` float
- `DT_DENSITY_RECLAIMING` (view, 7 cols): `DATE` date, `TYPE` varchar(10), `COMPANY` varchar(13), `ORIGIN` nvarchar(255), `DESTINATION` varchar(9), `WMT` float, `DT` int
- `DT_DENSITY_RECLAIMING_treated` (view, 35 cols): `DATE` date, `TYPE` varchar(10), `COMPANY` varchar(13), `ORIGIN` nvarchar(255), `DESTINATION` varchar(9), `WMT` float, `DT` int, `DISTANCE GROSS (KM)` float, `DT ON CRD KM0 - KM2,5` float, `DT ON CRD KM2,5 - KM5,5` float, `DT ON CRD KM5,5 - KM7` float, `DT ON CSW KM3 - KM4` float, … +23 more
- `DT_DENSITY_RECLAIMING_treated2` (view, 3 cols): `DATE` date, `SECTION_NAME` nvarchar(4000), `Total_DT` float
- `DT_DENSITY_RECLAIMING_treated3` (view, 5 cols): `DATE` date, `SECTION_NAME` nvarchar(4000), `APPROX_DISTANCE` float, `Total_DT` float, `DT/KM` float
- `EQUIPMENTS_CLEAN` (view, 17 cols): `ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `ID_EQ_LETTERS` varchar(-1), `ID_EQ_NUMBERS` int, `TYPE_CLEAN` varchar(3), `ID_EQ_CLEANED` nvarchar(-1), `OWNER` nvarchar(50), `TYPE` nvarchar(50), `DIGIT` int, `MANUFACTURER` nvarchar(50), `MODEL` nvarchar(50), … +5 more
- `EQUIPMENTS_CLEAN2` (view, 16 cols): `ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `ID_EQ_LETTERS` varchar(-1), `ID_EQ_NUMBERS` int, `ID_EQ_CLEANED` nvarchar(-1), `OWNER` nvarchar(50), `TYPE` nvarchar(50), `DIGIT` int, `MANUFACTURER` nvarchar(50), `MODEL` nvarchar(50), `CAPACITY` int, … +4 more
- `EQUIPMENTS_HOURLY_STATUS_COMPACT` (view, 8 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(50), `NB_UNIT` int, `UNIT_TYPE` nvarchar(50), `LOCATION` nvarchar(50), `STATUS` varchar(22)
- `EQUIPMENTS_HOURLY_STATUS_DAILY` (view, 13 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `ID_EQ` nvarchar(50), `TYPE` nvarchar(50), `LOCATION` nvarchar(50), `LOCATION_DETAILS` nvarchar(50), `WORKING_HOURS` float, `STBY_HOURS` float, `BD_HOURS` float, … +1 more
- `EQUIPMENTS_HOURLY_STATUS_SUMMARY` (view, 14 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(50), `ID_EQ` nvarchar(50), `TYPE` nvarchar(50), `LOCATION` nvarchar(50), `LOCATION_DETAILS` nvarchar(50), `WORKING_HOURS` float, `STBY_HOURS` float, `BD_HOURS` float, `PM_HOURS` float, … +2 more
- `EQUIPMENTS_QR_CODE_VALUE` (view, 3 cols): `ID` nvarchar(50), `QR_CODE_VALUE` nvarchar(-1), `URL` nvarchar(-1)
- `EQUIPMENTS_STATUS_BREAKDOWN` (view, 13 cols): `DATE` datetime, `SHIFT` float, `DATETIME` datetime, `CONTRACTOR` nvarchar(50), `UNIT_ID` nvarchar(50), `WORKING_HOURS` float, `STBY_HOURS` float, `BD_HOURS` float, `PM_HOURS` float, `OPERATING_HOURS` float, `PREV_DATETIME` datetime, `STATUS_BD` varchar(18), … +1 more
- `EQUIPMENT_LAST_COMMISSIONING` (view, 8 cols): `EQUIPMENT_ID_CLEAN` varchar(-1), `CONTRACTOR` nvarchar(255), `EQUIPMENT_TYPE` varchar(-1), `ODOMETER` nvarchar(255), `COMMISSIONING_DATE` date, `EXPIRED_DATE` date, `STATUS` nvarchar(255), `REMAINING` int
- `EQUIPMENT_NEW_ID` (view, 14 cols): `Company` nvarchar(255), `Vender Clasification` nvarchar(255), `Brand` nvarchar(255), `Model` nvarchar(4000), `Equipment_Size` nvarchar(255), `Finance_Status` nvarchar(255), `Equipment_Type` nvarchar(255), `TYPE_ACR` varchar(3), `OEM_PIN ` nvarchar(255), `OLD_ID` nvarchar(255), `OLD_ID_LETTERS` varchar(-1), `OLD_ID_DIGIT` int, … +2 more
- `EQUIPMENT_PLAN_ACTUAL` (view, 11 cols): `TEAM` nvarchar(255), `TYPE` nvarchar(255), `YEAR` float, `MONTH` float, `DATE` date, `ACTIVITY` nvarchar(255), `ORIGIN` nvarchar(4000), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `UNIT_TYPE` nvarchar(255), `NB_UNIT` float
- `EQUIPMENT_STATUS_FULL` (view, 13 cols): `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(50), `CONTRACTOR` nvarchar(50), `UNIT_TYPE` nvarchar(50), `MANUFACTURER` nvarchar(50), `BUILD_YEAR` int, `UNIT_ID` nvarchar(50), `WORKING_HOURS` float, `STBY_HOURS` float, `BD_HOURS` float, `PM_HOURS` float, … +1 more
- `EQUIPMENT_STATUS_WORKING_HOURS` (view, 13 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `UNIT_TYPE` nvarchar(50), `UNIT_ID` nvarchar(50), `SCH` float, `UNSCH` float, `STAND BY` float, `WORKING HOURS` float, `OPERATING HOURS` int, … +1 more
- `EQUIPMENT_STATUS_WORKING_HOURS_2` (view, 15 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `UNIT_TYPE` nvarchar(50), `NB_UNITS` int, `STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `SCH HOURS` float, `UNSCH HOURS` float, `STAND BY HOURS` float, `WORKING HOURS` float, `OPERATING HOURS` int, … +3 more
- `EQ_STATUS_WATER_MANAGEMENT` (view, 11 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `ID_EQ` nvarchar(50), `LOCATION` nvarchar(50), `LOCATION_DETAILS` nvarchar(4000), `SP_ID` nvarchar(-1), `WORKING_HOURS` float, `STBY_HOURS` float, `BD_HOURS` float, `PM_HOURS` float
- `FENI_RECLAIMING_PLAN_WITH_GRADE` (view, 15 cols): `DATE` date, `SHIFT` int, `ORE LOCATION` varchar(13), `DOME` nvarchar(50), `PLAN VEHICULE` int, `PLANNED WEIGHBRIDGE` nvarchar(50), `PLANNED WMT` float, `DESTINATION` nvarchar(50), `FENI` varchar(9), `Ni` float, `Fe` float, `SiO2` float, … +3 more
- `FENI_REQUESTS_FIRST` (view, 7 cols): `STOCK_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(260), `FIRST_REQUEST_SHIFT` nvarchar(255), `FIRST_REQUEST_DATE` datetime, `WMT_REQUEST` float
- `FENI_REQUESTS_TREATED` (view, 6 cols): `STOCK_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(260), `SHIFT_REQUEST` nvarchar(255), `DATE_REQUEST` datetime
- `FINANCE_MANAGEMENT` (view, 47 cols): `TYPE` varchar(18), `PLAN_ACTUAL` varchar(6), `TYPE_CLASS` varchar(10), `TYPE_ITEM` varchar(15), `YEAR` float, `MONTH` float, `YEAR_SALES` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `CONTRACTOR_MINING` nvarchar(255), `CONTRACTOR` nvarchar(255), … +35 more
- `FINANCE_MANAGEMENT_BOD` (view, 45 cols): `TYPE` varchar(18), `PLAN_ACTUAL` varchar(6), `YEAR` float, `MONTH` float, `YEAR_SALES` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `CONTRACTOR_MINING` nvarchar(255), `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), … +33 more
- `FINANCE_MANAGEMENT_RE` (view, 48 cols): `TYPE` varchar(24), `PLAN_ACTUAL` varchar(6), `TYPE_CLASS` varchar(10), `TYPE_ITEM` varchar(15), `YEAR` float, `MONTH` float, `YEAR_SALES` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `CONTRACTOR_MINING` nvarchar(255), `CONTRACTOR` nvarchar(255), … +36 more
- `FINANCE_PHYSICAL_FLOW` (view, 41 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `PLANT` nvarchar(255), `PLANT_COMPANY` nvarchar(255), `STOCK_ID` nvarchar(510), … +29 more
- `FMS_TOS_STATUS` (table, 11 cols): `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)
- `FULL HAULAGE` (view, 12 cols): `TYPE` nvarchar(101), `DATE` date, `SMU` nvarchar(50), `DOME` nvarchar(50), `DOME 2` nvarchar(50), `WEIGHBRIDGE WMT` float, `WBN SURVEY WMT` float, `ADJUSTMENT` int, `ORIGINAL WMT` float, `WMT` float, `CONTRACTOR` nvarchar(50), `DESTINATION` nvarchar(50)
- `FULL_ASSAYS_STOCK` (view, 26 cols): `ASSAY_DATA` nvarchar(50), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `ASSAY_DATE` date, `CONTRACTOR` nvarchar(101), `STOCK_SUBLOT` int, `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(260), `RIT` float, `WMT_CERT` float, `Al2O3` float, `CaO` float, … +14 more
- `FULL_FULL_PRODUCTION` (view, 12 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(255), `ORIGIN_TYPE` varchar(3), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(767), `DESTINATION_TYPE` varchar(4), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(260), `RIT` float, `WMT` float
- `FULL_PLAN` (view, 17 cols): `SOURCE_TYPE` varchar(4), `ACTIVITY` varchar(50), `DATE` datetime, `CONTRACTOR` nvarchar(50), `ENTITY` varchar(7), `MATERIAL` nvarchar(255), `ORIGIN_TYPE` varchar(7), `ORIGIN_PIT` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_TYPE` nvarchar(255), `DESTINATION_AREA` nvarchar(511), … +5 more
- `FULL_PRODUCTION` (view, 17 cols): `DATE` datetime, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `SURVEY_TYPE` nvarchar(255), `MATERIAL` nvarchar(50), `ORIGIN_PIT` varchar(5), `ORIGIN_TYPE` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(255), `DESTINATION_TYPE` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(255), … +5 more
- `FULL_PRODUCTION_GROUP` (view, 21 cols): `DATE` datetime, `YEAR` float, `MONTH` float, `MONTH_SALES` float, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_TYPE` nvarchar(50), `ORIGIN_PIT` varchar(5), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(255), `DESTINATION_TYPE` nvarchar(50), … +9 more
- `FULL_PRODUCTION_ONLY` (view, 16 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `ENTITY` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `ORIGIN_PIT` nvarchar(255), `ORIGIN_TYPE` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_TYPE` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), … +4 more
- `FULL_PRODUCTION_RECOMPACT` (view, 20 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `STOCK_POINT` varchar(11), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(510), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(-1), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(510), … +8 more
- `FULL_PRODUCTION_REFORMAT` (view, 18 cols): `OBJECT_NAME` varchar(19), `DATE` datetime, `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `STOCK_POINT` varchar(11), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(510), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(-1), `DESTINATION_AREA` nvarchar(255), … +6 more
- `FULL_PRODUCTION_VS_PLAN` (view, 17 cols): `SOURCE_TYPE` varchar(6), `DATE` datetime, `CONTRACTOR` nvarchar(255), `ENTITY` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `ORIGIN_PIT` nvarchar(255), `ORIGIN_TYPE` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_TYPE` nvarchar(255), `DESTINATION_AREA` nvarchar(511), … +5 more
- `FeNi Reclaiming Plan Treated 1` (view, 10 cols): `DATE` date, `SHIFT` int, `ORE LOCATION` varchar(13), `DOME` nvarchar(50), `DOME ID FENI` nvarchar(50), `PLAN VEHICULE` int, `PLANNED WEIGHBRIDGE` nvarchar(50), `PLANNED WMT` float, `DOME_RAW` nvarchar(50), `DESTINATION` nvarchar(50)
- `FeNi Reclaiming Plan Treated 2` (view, 13 cols): `DATE` date, `SHIFT` int, `ORE LOCATION` varchar(13), `DOME` nvarchar(50), `PLANNED VEHICULE` int, `PLANNED WMT` float, `Ni` float, `MC` float, `Fe` float, `SiO2` float, `MgO` float, `DMT` float, … +1 more
- `FeNi Reclaiming Plan Treated 3` (view, 3 cols): `DOME` nvarchar(50), `DATE` date, `PLANNED WMT` float
- `GEO_TOS_DUPLICATE` (view, 33 cols): `Contractor_Sample` nvarchar(50), `Contractor_Assay` nvarchar(50), `Date_Sample` datetime, `SAMPLE_JOB` nvarchar(50), `SAMPLE_ID` nvarchar(50), `BLOCK_ID` nvarchar(50), `SAMPLE_TYPE` nvarchar(50), `SAMPLE_CONTRACTOR` nvarchar(50), `ANALYSIS_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(50), `DATE_RECEIVED` date, … +21 more
- `HAUL VERY SHORT TERM TREATED 1` (view, 12 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `BUYER` nvarchar(50), `WMT` float, `TYPE HAULAGE` nvarchar(50), `DESTINATION YANG BAGUS` nvarchar(50), `MATERIAL YANG BAGUS` nvarchar(50), `ORIGIN YANG BAGUS` nvarchar(50)
- `HAUL VERY SHORT TERM TREATED 2` (view, 9 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `WMT` float, `DESTINATION` nvarchar(50), `BUYER` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN` nvarchar(50), `TYPE` nvarchar(50)
- `HAUL VERY SHORT TERM TREATED 3` (view, 20 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `TYPE` nvarchar(50), `COMPANY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `KM ORI` float, `KM DEST` float, `WMT` float, … +8 more
- `HAULAGE_BY_CONTRACTOR_TRUCK` (view, 5 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `TRUCK_ID` nvarchar(50), `RIT_PER_DT` int
- `HAULAGE_CLEAN` (view, 20 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` varchar(10), `DESTINATION_ID` nvarchar(50), `RIT` int, … +8 more
- `HAULAGE_CLEAN2` (view, 14 cols): `DATE` date, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `ORIGIN_PIT` varchar(5), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID_ORI` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `RIT` int, … +2 more
- `HAULAGE_CLEAN_FOR_DT` (view, 23 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(4000), `ORIGIN_AREA_GEN` nvarchar(4000), `STOCK_AREA_ORI` nvarchar(255), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` varchar(8000), … +11 more
- `HAULAGE_COMPLETE` (view, 24 cols): `TYPE` nvarchar(101), `DATE` date, `SMU` nvarchar(50), `DOME` nvarchar(50), `LOCATION` nvarchar(255), `WMT` float, `ORIGINAL WMT` float, `CONTRACTOR` nvarchar(50), `DESTINATION` varchar(13), `ORIGIN` varchar(13), `MATERIAL` varchar(3), `MC` float, … +12 more
- `HAULAGE_COMPLETE_VIA_BM` (view, 24 cols): `TYPE` nvarchar(101), `DATE` date, `SMU` nvarchar(50), `DOME` nvarchar(50), `LOCATION` nvarchar(255), `WMT` float, `ORIGINAL WMT` float, `CONTRACTOR` nvarchar(50), `DESTINATION` varchar(13), `ORIGIN` varchar(13), `MATERIAL` varchar(3), `MC` float, … +12 more
- `HAULAGE_ERROR` (view, 7 cols): `PLEASE_CORRECT` varchar(29), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_ID` nvarchar(50), `ORI_TYPE` nvarchar(50), `DEST_TYPE` nvarchar(50)
- `HAULAGE_GET_IWIP_PLAN_TICKET_NO` (view, 13 cols): `ID` int, `DATE` date, `IW_DATE` datetime, `CONTRACTOR` nvarchar(50), `TRUCK_ID` nvarchar(50), `KG_LOADED` float, `KG_EMPTY` float, `KG_NET` float, `TIME_LOADED` time, `TIME_EMPTY` time, `WB_ID_RAW` nvarchar(50), `TICKET_NO` nvarchar(255), … +1 more
- `HAULAGE_GET_IWIP_TICKET_NO` (view, 15 cols): `ID` int, `DATE` date, `CONTRACTOR` nvarchar(50), `TRUCK_ID` nvarchar(50), `KG_LOADED` float, `KG_EMPTY` float, `KG_NET` float, `TIME_LOADED` time, `TIME_EMPTY` time, `WB_ID_RAW` nvarchar(50), `IWIP_TIME_LOADED` time, `IWIP_TIME_EMPTY` time, … +3 more
- `HAULAGE_IWIP_CLEAN` (view, 33 cols): `SERIAL_NO` nvarchar(50), `WB_TIME` float, `WB_ID` nvarchar(50), `TICKET_NO` nvarchar(50), `TRUCK_ID` nvarchar(50), `CARGO_NAME` nvarchar(50), `DOME_ORIGINAL` nvarchar(50), `SELLER` nvarchar(50), `BUYER` nvarchar(50), `CONTRACTOR` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), … +21 more
- `HAULAGE_IWIP_VS_RECLAIM` (view, 5 cols): `DATE` date, `ACTIVITY` nvarchar(50), `DOME_ORIGINAL` nvarchar(50), `WB_IWIP_WMT` float, `R_WMT` float
- `HAULAGE_IWIP_WASTE` (view, 28 cols): `FETCH_DATE` datetime2, `SERIAL_NO` nvarchar(255), `WB_TIME` int, `DATE` date, `WB_ID` nvarchar(255), `TICKET_NO` nvarchar(50), `TRUCK_ID` nvarchar(255), `CARGO_NAME` nvarchar(255), `ORIGIN_ID` nvarchar(255), `SELLER` nvarchar(255), `BUYER` nvarchar(255), `CONTRACTOR` nvarchar(255), … +16 more
- `HAULAGE_LIM_BATCH` (view, 2 cols): `DESTINATION_ID` nvarchar(50), `BATCH_ID` nvarchar(4000)
- `HAULAGE_ORIGIN_PIT` (view, 26 cols): `ID` int, `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `ACTIVITY_TYPE` nvarchar(101), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TRUCK_TYPE` int, `TRUCK_CAPACITY` int, `TRUCK_MODEL` int, `TIME_LOADED` time, … +14 more
- `HAULAGE_PER_PILE` (view, 15 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` varchar(10), `DESTINATION_ID` nvarchar(50), `WMT` float, `Ni_` float, … +3 more
- `HAULAGE_PER_PILE_AND_PLAN` (view, 24 cols): `DATE` date, `SHIFT` float, `ACT_CONTRACTOR` nvarchar(50), `PLAN_CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `ACT_MATERIAL` nvarchar(50), `ACT_PIT` nvarchar(50), `PLAN_PIT` nvarchar(50), `PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ACT_PILE` nvarchar(50), `PLAN_PILE` nvarchar(50), … +12 more
- `HAULAGE_PER_PILE_AND_PLAN_TEMPORAL` (view, 25 cols): `DATE` date, `SHIFT` float, `ACT_CONTRACTOR` nvarchar(50), `PLAN_CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `ACT_MATERIAL` nvarchar(50), `ACT_PIT` nvarchar(50), `PLAN_PIT` nvarchar(50), `PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ACT_PILE` nvarchar(50), `PLAN_PILE` nvarchar(50), … +13 more
- `HAULAGE_PILE_INFO` (view, 20 cols): `ID` int, `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TIME_LOADED` time, `TIME_EMPTY` time, `RIT` int, `ORIGIN_PIT` nvarchar(255), `ORIGIN_AREA` nvarchar(50), … +8 more
- `HAULAGE_PIT_ORIGIN_DESTINATION` (view, 4 cols): `ORIGIN_ID` nvarchar(50), `ORIGIN_PIT` varchar(5), `DESTINATION_ID` nvarchar(50), `WMT` float
- `HAULAGE_VS_IWIP_SYSTEM` (view, 22 cols): `SOURCE_TABLE` varchar(7), `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TIME_LOADED` datetime, `TIME_EMPTY` datetime, `RIT` int, `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), … +10 more
- `HAULAGE_VS_OMR` (view, 6 cols): `CONTRACTOR_HAUL` nvarchar(255), `TOS_PILE` nvarchar(255), `DATE_OMR_MAX` date, `DATE_HAUL_MAX` date, `OMR_RIT` float, `HAUL_RIT` int
- `HAULAGE_VS_OMR_ORI_DEST` (view, 11 cols): `DATE` date, `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `CONTRACTOR` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `OMR_RIT` float, `HAUL_RIT` int, `HAUL_WMT` float
- `HAULAGE_VS_PROD_MONTHLY_CF` (view, 5 cols): `CONTRACTOR` nvarchar(255), `DATE` date, `PIT` nvarchar(255), `MATERIAL` nvarchar(50), `CF` float
- `HAULAGE_VS_PROD_PILES_CF` (view, 9 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `PIT` nvarchar(255), `TOS_PILE` nvarchar(255), `PROD_WMT` float, `MATERIAL` nvarchar(50), `RIT` int, `HAUL_WMT` float, `CF_PILE` float
- `HAULAGE_VS_RECLAIM` (view, 7 cols): `STOCK_ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `CONTRACTOR_WMT` float, `DATE_HAUL` date, `WMT_HAUL` float, `WMT_RECLAIM` float, `CONTRACTOR_DIFF` float
- `HAULAGE_WB_NOT_ON_THE_WAY` (view, 22 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `WMT` float, `TIME_LOADED` time, `TIME_EMPTY` time, `ORIGIN_ID` nvarchar(50), `DESTINATION_ID` nvarchar(50), `ORIGIN_AREA` nvarchar(50), … +10 more
- `HAULAGE_WITH_DT_TYPES` (view, 25 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(4000), `ORIGIN_AREA_GEN` nvarchar(4000), `STOCK_AREA_ORI` nvarchar(255), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` varchar(8000), … +13 more
- `HRM` (view, 24 cols): `ID` int, `UUID` nvarchar(255), `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY_CAT` nvarchar(50), `ACTIVITY_DESC` nvarchar(255), `ACTIVITY_PLANNED` nvarchar(50), `ACTIVITY_TIME_START` time, `ACTIVITY_TIME_END` time, `OPERATOR_ID` nvarchar(50), `UNIT_TYPE` nvarchar(50), … +12 more
- `IMPORT_HEATMAP` (view, 13 cols): `TABLE` varchar(21), `DATE` date, `SHIFT` int, `CKB` varchar(1), `GMG` varchar(1), `HJS` varchar(1), `MTM` varchar(1), `PPP` varchar(1), `RIM` varchar(1), `PS` varchar(1), `SMA` varchar(1), `SSS` varchar(1), … +1 more
- `LIM TOS PILE DOME For HAULAGE` (view, 2 cols): `TOS_PILE` nvarchar(255), `DOME` nvarchar(255)
- `LME_FOR_HMA_Ni` (view, 7 cols): `YEAR` int, `MONTH` int, `MONTH_DATE` date, `DATE` date, `LME_Ni_USD` float, `LME_Ni_3MONTH_USD` float, `LME_Ni_STOCK_ASSET` float
- `LME_NEW_HMA` (view, 7 cols): `YEAR` int, `MONTH` int, `MONTH_DATE` date, `START` date, `END` date, `HMA` varchar(4), `USD` float
- `LME_Ni_USD` (view, 4 cols): `DATE` date, `LME_Ni_USD` float, `LME_Ni_3MONTH_USD` float, `LME_Ni_STOCK_ASSET` float
- `Lab_Duplicate` (view, 37 cols): `Sampling_contractor` nvarchar(50), `Sampling_date` datetime, `Original_Sample` nvarchar(50), `Duplicate_Sample` nvarchar(50), `Duplicate_Type` varchar(16), `Pit` nvarchar(50), `Stock_ID` nvarchar(50), `ReturnDate` date, `Assay_Type` nvarchar(50), `Activity` nvarchar(50), `Stock_type` nvarchar(50), `Production_Contractor` nvarchar(255), … +25 more
- `MINING_EQUIPMENTS` (view, 8 cols): `DATE` datetime, `CONTRACTOR` nvarchar(50), `ORIGIN_AREA` nvarchar(255), `ID_EQ` nvarchar(255), `TYPE` nvarchar(50), `MODEL` nvarchar(50), `CAPACITY` int, `DIVISION` nvarchar(50)
- `MINING_HAULAGE_PLAN_AND_ACTUAL` (view, 63 cols): `ACTIVITY` varchar(50), `ACTIVITY2` nvarchar(259), `ACTIVITY3` nvarchar(259), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `MATERIAL_PROD` nvarchar(255), `MATERIAL_CLASS_PROD` nvarchar(255), … +51 more
- `MINING_PLAN_3MRMP_DAILY` (view, 44 cols): `YEAR` float, `QUARTER` nvarchar(255), `MONTH` float, `DATE` datetime, `DEPOSIT` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `IPPKH` nvarchar(255), `BM_ESTIMATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `FSAP_RSAP` nvarchar(255), … +32 more
- `MINING_PLAN_WEEKLY_BLOCKS` (view, 6 cols): `YEAR` float, `WEEK` float, `PIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `BLOCK_ID` nvarchar(255), `WMT` float
- `MINING_PLAN_WEEKLY_BLOCKS_VS_ACT` (view, 8 cols): `P_YEAR` float, `P_WEEK` float, `PIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `P_BLOCK_ID` nvarchar(255), `ACT_BLOCK_ID` nvarchar(255), `P_WMT` float, `ACT_WMT` float
- `MINING_PLAN_WEEKLY_WITH_QUALITY` (view, 36 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `MATERIAL` nvarchar(255), `FSAP_RSAP` nvarchar(255), `CATEGORY` nvarchar(255), `BLOCK_ID` nvarchar(255), `BCM` float, … +24 more
- `NEW_BLOCK_MAP_DIL_0` (view, 17 cols): `DEPOSIT` nvarchar(50), `X` float, `Y` float, `Z` float, `block_id` nvarchar(50), `prop_lim` float, `Ni_LIM` float, `Fe_LIM` float, `prop_sap` float, `prop_fsap` float, `prop_rsap` float, `Ni_SAP` float, … +5 more
- `NEW_BLOCK_MAP_DIL_1` (view, 18 cols): `DEPOSIT` nvarchar(50), `X` float, `Y` float, `Z` float, `block_id` nvarchar(50), `MP_LIM` varchar(7), `Ni_LIM` float, `Fe_LIM` float, `MP_SAP` varchar(7), `Ni_SAP` float, `Fe_SAP` float, `MP_WST` varchar(3), … +6 more
- `NEW_BLOCK_MAP_DIL_2` (view, 20 cols): `DEPOSIT` nvarchar(50), `X` float, `Y` float, `Z` float, `block_id` nvarchar(50), `MP_LIM` varchar(7), `Ni_LIM` float, `Fe_LIM` float, `MP_SAP` varchar(7), `Ni_SAP` float, `Fe_SAP` float, `MP_WST` varchar(3), … +8 more
- `NEW_BLOCK_MAP_DOM_PROP` (view, 21 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `MP_LIM` varchar(7), `Ni_LIM` float, `Fe_LIM` float, `MP_SAP` varchar(7), `Ni_SAP` float, `Fe_SAP` float, `MP_WST` varchar(3), … +9 more
- `NEW_BLOCK_MAP_rev02` (view, 19 cols): `X` float, `Y` float, `Z` float, `DEPOSIT` nvarchar(50), `block_id` nvarchar(50), `MP_LIM` varchar(7), `Ni_LIM` float, `Fe_LIM` float, `MP_SAP` varchar(7), `Ni_SAP` float, `Fe_SAP` float, `MP_WST` varchar(3), … +7 more
- `NEW_BM_OK` (view, 61 cols): `X` float, `Y` float, `Z` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `Deposit` nvarchar(50), `block_id` nvarchar(50), `al2o3_brk` float, `al2o3_fsap` float, `al2o3_lim` float, `al2o3_rsap` float, … +49 more
- `NEW_MENG_RECONCIL6_FSAP_RSAP` (view, 64 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(269), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +52 more
- `NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX` (view, 68 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(269), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +56 more
- `NEW_MENG_RECONCIL6_GC_TC0_Alan_test` (view, 68 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(269), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +56 more
- `NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP` (view, 68 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(269), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +56 more
- `NEW_QC_RECONCIL_FOR_ARCGIS` (view, 60 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` varchar(2), `PIT` nvarchar(255), `prod_ID` nvarchar(255), `BLOCK_ID` nvarchar(255), `block_ID_CORR` nvarchar(269), `MATERIAL` nvarchar(255), `RIT` float, … +48 more
- `OEE MINING WITH DEMOB` (view, 28 cols): `prodDate` datetime, `contractor` nvarchar(50), `unitId_cleaned` nvarchar(255), `timeGroup` nvarchar(50), `WMT_TMM` float, `RIT_SAP` float, `WMT_SAP` float, `RIT_RSAP` float, `WMT_RSAP` float, `RIT_LIM` float, `WMT_LIM` float, `RIT_WST` float, … +16 more
- `OEEDB_AUDB` (view, 23 cols): `recId` int, `prodDate` datetime, `contractor` nvarchar(50), `shiftCode` float, `timeGroup` nvarchar(7), `startHour` float, `endHour` float, `pit` nvarchar(50), `location` nvarchar(50), `activity` nvarchar(50), `unitId` nvarchar(50), `schDowntime` float, … +11 more
- `OEEDB_PDB` (view, 22 cols): `recId` int, `prodDate` date, `contractor` nvarchar(50), `shiftCode` int, `timeGroup` nvarchar(7), `startHour` int, `endHour` int, `pit` nvarchar(255), `subPit` nvarchar(255), `blockId` nvarchar(255), `prodId` nvarchar(255), `activityType` varchar(7), … +10 more
- `OEE_HAULAGE_WMT_KM` (view, 20 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` varchar(10), `DESTINATION_ID` nvarchar(50), `WB_ID` nvarchar(50), `WORKING_HOURS` float, … +8 more
- `OEE_MINING_FULL` (view, 27 cols): `CONTRACTOR` nvarchar(50), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` date, `SHIFT` int, `UNIT_TYPE` varchar(9), `TARGET_TRIP_HOUR` numeric, `UNIT_ID` nvarchar(255), `UNIT_ID_FULL` nvarchar(50), `CAPACITY` int, `UNIT_TYPE2` nvarchar(50), … +15 more
- `OEE_MINING_NEW` (view, 27 cols): `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `TYPE` nvarchar(50), `CAPACITY` int, `PROD_per_ HOUR` int, `EQ_CLASS` nvarchar(54), `DIVISION` nvarchar(50), `DIVISION GROUP` nvarchar(50), `SCH` float, `UNSCH_DT` float, `STBY` float, `WORKING HOURS` float, … +15 more
- `OMR_PILE_STATUS_ALL` (view, 6 cols): `ACTIVITY` varchar(7), `DATE` datetime, `SHIFT` float, `PILE_ID` nvarchar(255), `TOS_AREA` nvarchar(255), `STATUS` nvarchar(255)
- `OMR_PILE_STATUS_ALL_GROUP` (view, 7 cols): `STOCK_TYPE` varchar(3), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `DATE_OPEN` datetime, `DATE_COMPLETE` datetime, `DATE_TRANSFER` datetime, `DATE_FINISH` datetime
- `OMR_PILE_STATUS_ALL_GROUP2` (view, 9 cols): `STOCK_TYPE` varchar(3), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `DATE_OPEN` datetime, `DATE_COMPLETE` datetime, `DATE_TRANSFER` datetime, `DATE_FINISH` datetime, `MIN_DATE` datetime, `MAX_DATE` datetime
- `OMR_TOS` (view, 9 cols): `DATE` datetime, `SHIFT` float, `CONTRACTOR` nvarchar(255), `ACTIVITY` varchar(15), `MATERIAL` nvarchar(255), `TOS_PILE` nvarchar(255), `RIT` float, `TF` float, `WMT` float
- `OMR_TOS_CONTINUE` (view, 16 cols): `DATE` datetime, `SHIFT` int, `DATETIME` datetime, `STOCK_TYPE` varchar(3), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `STATUS` varchar(8), `CONTRACTOR` nvarchar(255), `ACTIVITY` varchar(7), `MATERIAL` nvarchar(255), `RIT` float, `TF` float, … +4 more
- `PILES_SHARED_FENI_TREATED` (view, 6 cols): `DATE_SHARE` datetime, `PILE_ID` nvarchar(255), `TOS_LOCATION` nvarchar(255), `CLASS` nvarchar(255), `CATEGORY` nvarchar(255), `WMT` float
- `PLAN_DAY_WORKS_CLEAN` (view, 18 cols): `DATE` datetime, `ACTIVITY` nvarchar(255), `STATUS` nvarchar(255), `AREA` nvarchar(255), `SECTION_ROAD` nvarchar(255), `ORIGINAL_LOCATION_JOB` nvarchar(255), `SECTION_COUNT` int, `HOURS` float, `LOCATION_JOB` nvarchar(4000), `ROAD` nvarchar(-1), `KILOMETER` float, `KM_START` float, … +6 more
- `POS FOLLOW UP TREATED` (view, 8 cols): `DATE` date, `AREA` nvarchar(50), `POS` nvarchar(50), `PADS` nvarchar(50), `NUMBER` int, `AVG` float, `EDD` date, `PRECISION` nvarchar(50)
- `PP_MINED_CLEAN` (view, 10 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DEPOSIT` nvarchar(255), `X` float, `Y` float, `Z` float, `classification_no` float, `BLOCK_ID` nvarchar(255), `pp_mined_progress` float
- `PP_MINED_NEW_RECONCIL_MENG_CONVERT_NEW_BM` (view, 11 cols): `YEAR` float, `MONTH` float, `WEEK` float, `PIT` nvarchar(255), `X` float, `Y` float, `Z` float, `classification_no` float, `block_id` nvarchar(255), `block_id_old` nvarchar(255), `pp_mined_progress` float
- `PRODUCTION_EQUIPMENT_RUNNING` (view, 6 cols): `SOURCE_TABLE` varchar(22), `EQUIPMENT_ID_CLEAN` varchar(-1), `DATE` datetime, `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `AREA` nvarchar(255)
- `PRODUCTION_MINING_PIT` (view, 11 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `ORIGIN_AREA` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `RIT` float, `WMT` float
- `PRODUCTION_PIT` (view, 24 cols): `ID` int, `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), `MATERIAL` nvarchar(255), … +12 more
- `PRODUCTION_PIT_BY_EQ_HOUR` (view, 14 cols): `contractor` nvarchar(50), `prodDate` date, `SHIFT` int, `timeGroup` nvarchar(9), `activity` nvarchar(255), `PIT` nvarchar(255), `subpit` nvarchar(255), `RIT` float, `RIT_SAP` float, `RIT_RSAP` float, `RIT_LIM` float, `RIT_WST` float, … +2 more
- `PRODUCTION_PIT_COEF` (view, 6 cols): `YEAR` int, `MONTH` int, `contractor` nvarchar(50), `deposit_code` nvarchar(50), `material` nvarchar(50), `CF` float
- `PRODUCTION_PIT_COORDINATES_B_S` (view, 22 cols): `ID` int, `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `Z` int, `B` int, … +10 more
- `PRODUCTION_PIT_COORDINATES_X_Y` (view, 24 cols): `ID` int, `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `Z` int, `B` int, … +12 more
- `PRODUCTION_PIT_COORDINATES_X_Y_CONVERT_NEW_BM` (view, 27 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `NEW_BLOCK_ID1` nvarchar(20), `NEW_BLOCK_ID2` nvarchar(20), `NEW_BLOCK_ID3` nvarchar(20), … +15 more
- `PRODUCTION_PIT_DAILY_PLAN` (view, 10 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `TMM` float, `PLAN_SAP` float, `PLAN_LIM` float, `PLAN_WST` float
- `PRODUCTION_PIT_DISTANCE_CALC` (view, 28 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `Z` int, `B` int, `S` int, … +16 more
- `PRODUCTION_PIT_HOURLY` (view, 20 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `TIME_GROUP` nvarchar(11), `START_HOUR` int, `END_HOUR` int, `ACTIVITY_TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` nvarchar(255), `SUB_PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), … +8 more
- `PRODUCTION_PIT_HOURLY_FULL` (view, 20 cols): `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `TIME_GROUP` nvarchar(11), `START_HOUR` int, `END_HOUR` int, `ACTIVITY_TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` nvarchar(255), `SUB_PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), … +8 more
- `PRODUCTION_PIT_HOURLY_TF` (view, 20 cols): `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `TIME_GROUP` nvarchar(11), `START_HOUR` int, `END_HOUR` int, `ACTIVITY_TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` nvarchar(255), `SUB_PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), … +8 more
- `PRODUCTION_PIT_MINING_DISTANCE` (table, 14 cols): `ID` int, `CONTRACTOR` nvarchar(255), `DATE` date, `SHIFT` int, `PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(255), `DESTINATION` nvarchar(255), `EXCAVATOR_ID` nvarchar(255), `RIT` float, `DISTANCE_KM` float, `WMT` float, … +2 more
- `PRODUCTION_PIT_RECONCIL_PP` (view, 11 cols): `TABLE` varchar(4), `YEAR` float, `MONTH` float, `WEEK` float, `DEPOSIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `BLOCK_ID` nvarchar(255), `Z` int, `B` int, `S` int, `PP` float
- `PRODUCTION_PIT_TOS_CLEAN` (view, 6 cols): `DESTINATION_RAW` nvarchar(4000), `TOS_TYPE` varchar(8), `CONTRACTOR` nvarchar(255), `TOS_PIT` nvarchar(255), `TOS_CONTRACTOR` nvarchar(255), `TOS_NUMBER` int
- `PRODUCTION_PIT_VS_OMR` (view, 8 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `MATERIAL` nvarchar(255), `TOS_PILE` nvarchar(255), `BLOCK_ID` nvarchar(255), `RIT_PRODUCTION_PIT` float, `RIT_QC PIT-TOS OMR` float, `IS_GOOD` varchar(8)
- `PRODUCTION_PIT_WRONG_ELEVATION` (view, 22 cols): `ID` int, `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` int, `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `MODULO_Z` int, `B` int, … +10 more
- `PROD_ASSAYS` (view, 31 cols): `ID` int, `Date` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), `block_ID_2` nvarchar(255), `CLASS_BM` int, `material` nvarchar(255), `RIT` float, … +19 more
- `PROD_CALENDAR_ASSAYS` (view, 37 cols): `exercice` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `Date` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), `block_ID_2` nvarchar(255), … +25 more
- `PROD_CORR_AND_PLAN` (view, 34 cols): `ID` int, `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), … +22 more
- `PROD_CORR_ASSAYS` (view, 39 cols): `exercice` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `Date` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), `block_ID_2` nvarchar(255), … +27 more
- `PROD_CORR_ASSAYS_COG` (view, 39 cols): `ID` int, `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `Date` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), … +27 more
- `PROD_CORR_ASSAYS_COG_2` (view, 48 cols): `ID` int, `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), … +36 more
- `PROD_CORR_ASSAYS_COG_3` (view, 45 cols): `WMT_ROM` float, `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), … +33 more
- `PROD_CORR_ASSAYS_COG_4` (view, 33 cols): `ID` int, `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_ID` nvarchar(255), … +21 more
- `PROD_VIA_BM` (view, 38 cols): `EXERCICE` nvarchar(255), `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `contractor` nvarchar(255), `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `block_ID` nvarchar(255), `block_ID_2` nvarchar(255), `material` nvarchar(255), … +26 more
- `PROD_VVST_REPORT_2` (view, 32 cols): `YEAR` float, `MONTH` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `DEPARTMEN` nvarchar(50), `DEPOSIT` nvarchar(4000), `SHIFT` nvarchar(50), `SAP_ROM_PLAN` float, `SAP_PLAN` float, `LIM_ROM_PLAN` float, `LIM_PLAN` float, `WST_ROM_PLAN` float, … +20 more
- `PROD_VVST_TREATED` (view, 23 cols): `YEAR` float, `MONTH` float, `WEEK` float, `exercice` nvarchar(255), `DATE` date, `CONTRACTOR` nvarchar(50), `DEPARTMEN` nvarchar(50), `SHIFT` nvarchar(50), `LOCATION` nvarchar(50), `TF_vvst` float, `DOZER` float, `EXCA` float, … +11 more
- `PileTonnage` (view, 10 cols): `PILE_ID` nvarchar(255), `PIT` nvarchar(255), `WMT` float, `Ni` float, `MgO` float, `Fe` float, `SiO2` float, `MC` float, `Activity` nvarchar(50), `DMT` float
- `Prod and Calender` (view, 26 cols): `MONTH` float, `WEEK` float, `ID` int, `contractor` nvarchar(255), `Date` datetime, `shift` float, `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_id` nvarchar(255), `block_ID_2` nvarchar(255), … +14 more
- `QC ALL DATA 2` (view, 73 cols): `TYPE_DATA` varchar(9), `TYPE` nvarchar(255), `TOS LOCATION` nvarchar(255), `LOCATION` varchar(3), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `PILE ID` nvarchar(255), `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, … +61 more
- `QC CHECK PIT VS SAMP LD` (view, 9 cols): `BLOCK ID` nvarchar(255), `RIT` float, `SAMPLE BLOCK ID` nvarchar(50), `SAMPLE RIT` float, `DATE PIT` datetime, `DATE SAMPLE` datetime, `CHECK PILE ID` varchar(20), `CHECK RIT` varchar(6), `PIT` varchar(3)
- `QC CHECK PIT VS SAMP TOS` (view, 9 cols): `PILE ID` nvarchar(255), `RIT` float, `SAMPLE PILE ID` nvarchar(50), `SAMPLE RIT` float, `CHECK PILE ID` varchar(20), `CHECK RIT` varchar(6), `DATE PIT` datetime, `DATE SAMPLE` datetime, `PIT` varchar(3)
- `QC PIT-TOS & SAMPLE DATA` (view, 15 cols): `TYPE` nvarchar(255), `TOS LOCATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `RIT` float, `STATUS` varchar(5), `PILE ID` nvarchar(255), `JOB-QC` nvarchar(50), `SAMPLE CODE` nvarchar(50), `TYPE SAMPLE` nvarchar(50), `TYPE DATA` nvarchar(50), `RIT SAMPLE` int, `PILE ID SAMPLE` nvarchar(50), … +3 more
- `QC PIT-TOS OMR SUMMARY` (view, 23 cols): `TYPE` nvarchar(255), `TOS LOCATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `RIT` float, `WMT` float, `STATUS` varchar(5), `PILE_ID` nvarchar(255), `MATERIAL` nvarchar(255), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, … +11 more
- `QC PIT-TOS OMR SUMMARY 2` (view, 7 cols): `PROD_DATE` datetime, `CONTRACTOR` nvarchar(255), `ASSAYS_ID` nvarchar(255), `TOS LOCATION` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` varchar(3), `PROD_RIT` float
- `QC PIT-TOS SUM FOR CHECK FOR LD` (view, 4 cols): `BLOCK ID` nvarchar(255), `RIT` float, `DATE PIT` datetime, `PIT` varchar(3)
- `QC PIT-TOS SUM FOR CHECK FOR TOS` (view, 4 cols): `PILE ID` nvarchar(255), `RIT` float, `DATE PIT` datetime, `PIT` varchar(3)
- `QC SAMPLE & ASSAYS` (view, 24 cols): `PILE ID` nvarchar(50), `JOB-QC` nvarchar(50), `SAMPLE CODE` nvarchar(50), `RIT` float, `Ni` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `Fe` float, `MgO` float, … +12 more
- `QC SAMPLE & ASSAYS COMPOSITES` (view, 21 cols): `PILE ID` nvarchar(50), `RIT` float, `Ni` float, `Fe` float, `Co` float, `MgO` float, `SiO2` float, `MnO` float, `CaO` float, `Cr2O3` float, `P2O5` float, `Al2O3` float, … +9 more
- `QC SAMPLE SUM FOR CHECK` (view, 4 cols): `PILE ID` nvarchar(50), `RIT` float, `TYPE SAMPLE` nvarchar(50), `DATE SAMPLE` datetime
- `QC TOS BALANCE` (view, 64 cols): `TYPE_DATA` varchar(9), `PILE ID` nvarchar(50), `TOS LOCATION` varchar(3), `STOCK_AREA` nvarchar(50), `CONTRACTOR` nvarchar(255), `TYPE` nvarchar(255), `CF_PLAN_Ni` float, `CF_BM_Ni` float, `CF_TOS_Ni` float, `CF_BM_Fe` float, `CF_TOS_Fe` float, `TOS_Ni` float, … +52 more
- `QC TOS_PILE STATUS HAULAGE` (view, 4 cols): `TOS_PILE` nvarchar(255), `STATUS HAULAGE` nvarchar(255), `LAST HAULAGE` date, `START HAULAGE` date
- `QC TOS_VS_POS` (view, 41 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DOME` nvarchar(255), `DOME 2` nvarchar(50), `DOME_SIMPLIFIED` nvarchar(255), `ASSAYS_ID` nvarchar(257), `CONTRACTOR_HAULAGE` nvarchar(255), `FIRST_PROD` datetime, `LAST_PROD` datetime, `CONTRACTOR_PROD` nvarchar(255), `TOS_LOCATION` nvarchar(255), … +29 more
- `QC_CF_BM_PROP` (view, 16 cols): `ORIGIN_PIT` nvarchar(255), `MATERIAL` varchar(3), `BM_MC_PROP` float, `BMC_MC_PROP` float, `BM_Ni_PROP` float, `BMC_Ni_PROP` float, `BM_Fe_PROP` float, `BMC_Fe_PROP` float, `BM_SiO2_PROP` float, `BMC_SiO2_PROP` float, `BM_MgO_PROP` float, `BMC_MgO_PROP` float, … +4 more
- `QC_CF_BM_TOS` (view, 18 cols): `MAX_DATE` date, `ORIGIN_PIT` nvarchar(255), `CONTRACTOR_PILE` nvarchar(255), `MATERIAL` varchar(3), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_BM_Cr2O3` float, `DIL_BM_Co` float, `DIL_TOS_MC` float, … +6 more
- `QC_CF_BM_TOS_OLD` (view, 24 cols): `YEAR` float, `MONTH` float, `ORIGIN_PIT` nvarchar(255), `CONTRACTOR_PILE` nvarchar(255), `MATERIAL` varchar(3), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_BM_Cr2O3` float, `DIL_BM_Co` float, … +12 more
- `QC_COMPOSITE_ALL_STOCK` (view, 26 cols): `OBJECT_NAME` varchar(32), `ASSAY_DATA` nvarchar(50), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(8), `ASSAY_STATUS_%` float, `CONTRACTOR` nvarchar(101), `STOCK_TYPE` nvarchar(50), `DATE` datetime, `STOCK_ID` nvarchar(255), `COMPO_STOCK_NAMES` nvarchar(-1), `WMT` float, `DMT` float, … +14 more
- `QC_COMPOSITE_ASSAY` (view, 22 cols): `DATE` date, `STOCK_ID` nvarchar(260), `STOCK_TYPE` nvarchar(50), `STOCK_SUBLOT` int, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `CONTRACTOR` nvarchar(101), `RIT` float, `WMT` float, `DMT` float, `al2o3` float, `cao` float, … +10 more
- `QC_COMPOSITE_BLOCK` (view, 25 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `WMT` float, `DMT` float, `BLOCK_NAME` nvarchar(37), `DEPOSIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(12), `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +13 more
- `QC_COMPOSITE_BLOCK_SELECT` (view, 22 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `WMT` float, `DMT` float, `BLOCK_NAME` nvarchar(37), `DEPOSIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(4000), `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +10 more
- `QC_COMPOSITE_BLOCK_VIA_PIT` (view, 18 cols): `DEPOSIT` nvarchar(50), `BLOCK_ID` nvarchar(255), `ASSAY_TYPE` int, `DATE` date, `MATERIAL` varchar(3), `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, … +6 more
- `QC_COMPOSITE_DUMP` (view, 20 cols): `DATE` date, `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `CONTRACTOR` nvarchar(50), `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +8 more
- `QC_COMPOSITE_DUMP_VIA_PIT` (view, 18 cols): `STOCK_ID` nvarchar(255), `STOCK_TYPE` varchar(3), `ASSAY_TYPE` varchar(6), `DATE` datetime, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, … +6 more
- `QC_COMPOSITE_HAULAGE` (view, 20 cols): `DATE` date, `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `CONTRACTOR` nvarchar(50), `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +8 more
- `QC_COMPOSITE_POS` (view, 20 cols): `DATE` date, `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `ASSAY_STATUS_%` float, `CONTRACTOR` nvarchar(101), `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +8 more
- `QC_COMPOSITE_POS_VIA_BM` (view, 17 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` varchar(6), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, `fe2o3` float, `MC` float, … +5 more
- `QC_COMPOSITE_POS_VIA_ML` (view, 4 cols): `STOCK_ID` nvarchar(50), `WMT` float, `DMT` float, `Ni` float
- `QC_COMPOSITE_POS_VIA_TOS` (view, 18 cols): `STOCK_ID` nvarchar(50), `STOCK_TYPE` varchar(3), `ASSAY_TYPE` nvarchar(50), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, `fe2o3` float, … +6 more
- `QC_COMPOSITE_POS_VIA_YARD` (view, 19 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` varchar(11), `ASSAY_STATUS` varchar(6), `ASSAY_CONTRACTOR` nvarchar(101), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, … +7 more
- `QC_COMPOSITE_TOS` (view, 20 cols): `Date` date, `DATE_ANALYSIS` date, `ASSAY_TYPE` nvarchar(50), `STOCK_ID` nvarchar(255), `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, … +8 more
- `QC_COMPOSITE_TOS_CERT` (view, 16 cols): `Date` date, `ASSAY_TYPE` nvarchar(50), `STOCK_ID` nvarchar(50), `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, `MC` float, `MgO` float, … +4 more
- `QC_COMPOSITE_TOS_IndividualBlock` (view, 22 cols): `DATE_RECEIVED_LATEST` date, `DATE_ANALYSIS_LATEST` date, `DATE_SAMPLING_LATEST` datetime, `PIT` nvarchar(50), `PROD_ID` nvarchar(4000), `MATERIAL_PROD` nvarchar(50), `MATERIAL_ASSAYED` varchar(3), `CAT_ASSAYED` varchar(4), `WMT` float, `DMT` float, `Ni` float, `Fe` float, … +10 more
- `QC_COMPOSITE_TOS_VIA_BM` (view, 32 cols): `STOCK_ID` nvarchar(255), `ASSAY_TYPE` varchar(6), `DATE` datetime, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +20 more
- `QC_COMPOSITE_TOS_VIA_BM_ORI` (view, 29 cols): `STOCK_ID` nvarchar(255), `ASSAY_TYPE` varchar(6), `DATE` datetime, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +17 more
- `QC_COMPOSITE_TOS_VIA_HAULAGE` (view, 15 cols): `TOS_PILE` nvarchar(50), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, `MC` float, `mgo` float, `mno` float, … +3 more
- `QC_COMPOSITE_TOS_VIA_PIT` (view, 17 cols): `STOCK_ID` nvarchar(255), `ASSAY_TYPE` varchar(6), `DATE` datetime, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +5 more
- `QC_COMPOSITE_TOS_VIA_POS` (view, 18 cols): `STOCK_ID` nvarchar(50), `STOCK_TYPE` varchar(3), `ASSAY_TYPE` nvarchar(50), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, `fe2o3` float, … +6 more
- `QC_COMPOSITE_TOS_VIA_YARD` (view, 17 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` nvarchar(50), `DATE` date, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +5 more
- `QC_COMPOSITE_WCO` (view, 22 cols): `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `DOME` nvarchar(255), `DOME ID` nvarchar(255), `SURVEY METHOD` nvarchar(255), `PIT DETAILS` nvarchar(255), `PIT` nvarchar(255), `WMT` float, `ASSAY_TYPE` nvarchar(50), `Ni` float, `Fe` float, … +10 more
- `QC_COMPOSITE_YARD` (view, 21 cols): `DATE` date, `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `ASSAY_STATUS_%` float, `CONTRACTOR` nvarchar(101), `RIT` float, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, … +9 more
- `QC_COMPOSITE_YARD_DIRECT` (view, 20 cols): `DATE` date, `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `ASSAY_STATUS_%` int, `CONTRACTOR` nvarchar(50), `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +8 more
- `QC_COMPOSITE_YARD_STOCK_ORIGINAL` (view, 20 cols): `DATE` date, `STOCK_ID` nvarchar(255), `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` varchar(6), `CONTRACTOR` nvarchar(101), `RIT` float, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, … +8 more
- `QC_COMPOSITE_YARD_VIA_BM` (view, 17 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` varchar(6), `DATE` datetime, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +5 more
- `QC_COMPOSITE_YARD_VIA_POS` (view, 18 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` varchar(11), `ASSAY_STATUS` varchar(6), `DATE` date, `WMT` float, `DMT` float, `al2o3` float, `cao` float, `co` float, `cr2o3` float, `fe` float, `fe2o3` float, … +6 more
- `QC_COMPOSITE_YARD_VIA_TOS` (view, 17 cols): `STOCK_ID` nvarchar(50), `ASSAY_TYPE` nvarchar(50), `DATE` date, `WMT` float, `DMT` float, `Al2O3` float, `CaO` float, `CO` float, `Cr2O3` float, `Fe` float, `Fe2O3` float, `MC` float, … +5 more
- `QC_PLAN_Ni_CF_ALL` (view, 15 cols): `STOCK_ID` nvarchar(255), `DIL_TOS_MC` float, `DIL_BM_MC` float, `DIL_TOS_Ni` float, `DIL_BM_Ni` float, `DIL_TOS_Fe` float, `DIL_BM_Fe` float, `DIL_TOS_SiO2` float, `DIL_BM_SiO2` float, `DIL_TOS_MgO` float, `DIL_BM_MgO` float, `DIL_TOS_Co` float, … +3 more
- `QC_POS_DETAILS` (view, 17 cols): `STOCK_ID` nvarchar(255), `POS_BM_Ni` float, `POS_TOS_Ni` float, `POS_WMT_CERT` float, `POS_Ni` float, `YARD_WMT_CERT` float, `YARD_Ni` float, `LOCATION` nvarchar(255), `ORIGIN` varchar(13), `SMU` nvarchar(50), `HAUL_WMT` float, `TOS_PLAN_Ni` float, … +5 more
- `QC_STOCK_ALL` (view, 28 cols): `OBJECT_NAME` varchar(6), `STOCK_ID` nvarchar(100), `STOCK_TYPE` nvarchar(50), `ASSAY_DATA` nvarchar(50), `ASSAY_DATE` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ASSAY_STATUS_%` float, `ASSAY_CONTRACTOR` nvarchar(50), `WMT_CERT` float, `PROP_WMT` float, `PROP_DMT` float, … +16 more
- `QC_STOCK_ALL_VIA_ALL` (view, 92 cols): `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(100), `Ni_` float, `PLAN_MC` float, `PLAN_Ni` float, `PLAN_Fe` float, `PLAN_SiO2` float, `PLAN_MgO` float, `PLAN_Co` float, `PLAN_Cr2O3` float, `CF_PLAN_Ni` float, `DEF_ASSAY_TYPE` nvarchar(101), … +80 more
- `QC_STOCK_ALL_VIA_ALL_OLD` (view, 54 cols): `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(260), `Ni_` float, `PLAN_Ni` float, `CF_PLAN_Ni` int, `DEF_ASSAY_TYPE` nvarchar(101), `DEF_MC` float, `DEF_Ni` float, `DEF_Fe` float, `DEF_SiO2` float, `DEF_MgO` float, `DEF_Co` float, … +42 more
- `QC_STOCK_POS_VIA_ALL` (view, 41 cols): `STOCK_ID` nvarchar(255), `Ni_` float, `AVG_Ni` float, `BM_ASSAY_TYPE` nvarchar(50), `BM_MC` float, `BM_Ni` float, `BM_Fe` float, `BM_SiO2` float, `BM_MgO` float, `BM_Co` float, `BM_P2O5` float, `TOS_ASSAY_TYPE` nvarchar(50), … +29 more
- `QC_STOCK_TOS_FOR_ANALYZE` (view, 39 cols): `STOCK_ID` nvarchar(255), `MATERIAL` varchar(3), `PLAN_Ni` float, `RATIO_WMT` float, `BM_ASSAY_TYPE` nvarchar(50), `BM_WMT` float, `BM_PROP` float, `BM_MC` float, `BM_Ni` float, `BM_Fe` float, `BM_SiO2` float, `BM_MgO` float, … +27 more
- `QC_STOCK_TOS_VIA_ALL` (view, 36 cols): `STOCK_ID` nvarchar(255), `Ni_vieux_Julien` float, `Ni_` float, `BM_WMT` float, `BM_PROP` float, `BM_ASSAY_TYPE` nvarchar(50), `BM_MC` float, `BM_Ni` float, `BM_Fe` float, `BM_SiO2` float, `BM_MgO` float, `BM_Co` float, … +24 more
- `QUARRY PRODUCTION treated` (view, 17 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(-1), `SUBQUARRY` nvarchar(-1), `AREA_ID` nvarchar(-1), `MATERIAL` nvarchar(-1), `RIT` int, `TF (BCM)` float, `DESTINATION` nvarchar(-1), … +5 more
- `QUARRY_DAILY_EXTRACTION` (view, 9 cols): `CONTRACTOR` nvarchar(-1), `DATE` date, `SHIFT` int, `QUARRY` nvarchar(-1), `MATERIAL` nvarchar(-1), `RIT` int, `BCM` float, `DESTINATION` nvarchar(-1), `PILE ID` nvarchar(-1)
- `QUARRY_STOCK_BLEND_MANAGEMENT` (view, 13 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE_SURVEY` date, `DATE` datetime, `SHIFT` int, `SURVEY_WEEK` nvarchar(50), `TYPE_OF_SURVEY` nvarchar(50), `STOCK_ID` nvarchar(-1), `LOCATION` nvarchar(-1), `BCM` float, `STOCK_PRODUCT` nvarchar(50), … +1 more
- `QUARRY_STOCK_BLEND_MANAGEMENT_TREATED` (view, 16 cols): `DATE_SURVEY` date, `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `SHIFT` int, `SURVEY_WEEK` nvarchar(50), `TYPE_OF_SURVEY` nvarchar(50), `STOCK_ID` nvarchar(-1), `GRANULO` nvarchar(-1), `LINE` nvarchar(-1), `LOCATION` nvarchar(-1), … +4 more
- `QUARRY_STOCK_CRUSHED_MANAGEMENT` (view, 14 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE_SURVEY` date, `DATE` datetime, `SHIFT` int, `SURVEY_WEEK` nvarchar(50), `CRUSHER` nvarchar(-1), `TYPE_OF_SURVEY` nvarchar(50), `LINE` int, `PILE_ID` nvarchar(-1), `LOCATION` nvarchar(-1), … +2 more
- `QUARRY_STOCK_CRUSHED_MANAGEMENT_TREATED` (view, 16 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE_SURVEY` date, `DATE` datetime, `SHIFT` int, `SURVEY_WEEK` nvarchar(50), `CRUSHER` nvarchar(-1), `TYPE_OF_SURVEY` nvarchar(50), `PILE_ID` nvarchar(-1), `GRANULO` nvarchar(-1), `LINE` int, … +4 more
- `QUARRY_STOCK_TOS_MANAGEMENT` (view, 15 cols): `YEAR` float, `MONTH` float, `WEEK` float, `TYPE_OF_SURVEY` nvarchar(50), `SURVEY_WEEK` nvarchar(50), `CONTRACTOR` nvarchar(-1), `DATE` date, `DATE_SURVEY` date, `SHIFT` int, `STOCK_AREA` nvarchar(-1), `STOCK_ID` nvarchar(-1), `MATERIAL` nvarchar(-1), … +3 more
- `QUARRY_STOCK_TOS_MANAGEMENT_TREATED` (view, 16 cols): `YEAR` float, `MONTH` float, `WEEK` float, `TYPE_OF_SURVEY` nvarchar(50), `SURVEY_WEEK` nvarchar(50), `CONTRACTOR` nvarchar(-1), `DATE` date, `DATE_SURVEY` date, `SHIFT` int, `STOCK_AREA` nvarchar(-1), `STOCK_ID` nvarchar(-1), `MATERIAL` nvarchar(-1), … +4 more
- `RAINFALL_AREA_COORDINATES` (view, 3 cols): `AREA` nvarchar(255), `X_RF` float, `Y_RF` float
- `RAINFALL_CONSOLIDATED` (view, 3 cols): `DATE` date, `LOCATION` nvarchar(255), `mmH20` float
- `RAINFALL_PREP` (view, 13 cols): `YEAR` int, `MONTH` int, `WEEK` float, `CONTRACTOR` nvarchar(50), `DATE` date, `AREA` nvarchar(255), `STATION` nvarchar(255), `H2O_mm` float, `X` float, `Y` float, `DURASI` float, `X_RF` float, … +1 more
- `RECLAIMING` (view, 12 cols): `TYPE` nvarchar(50), `DATE` date, `WEIGHBRIDGE WMT` float, `DOME` nvarchar(50), `DESTINATION` nvarchar(4000), `DESTINATION_ID` nvarchar(50), `SELLER` nvarchar(4000), `BUYER` varchar(1), `CONTRACTOR` nvarchar(4000), `DUMPING POINT` varchar(1), `RIT` int, `TF` int
- `RECLAIMING DETAIL` (view, 19 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `RIT` int, `ORIGIN` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION` nvarchar(101), `WMT` float, `DMT` float, … +7 more
- `RECLAIMING DETAIL 2` (view, 18 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `NB_DT` int, `RIT` int, `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(101), `WMT` float, `DMT` float, `Ni` float, … +6 more
- `RECLAIMING DETAIL 3` (view, 19 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `NB_DT` int, `RIT` int, `TRIP` float, `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(101), `WMT` float, `DMT` float, … +7 more
- `RECLAIMING DETAIL 4` (view, 18 cols): `DATE` date, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `NB_DT` int, `RIT` int, `TRIP` float, `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(101), `WMT` float, `DMT` float, `Ni` float, … +6 more
- `RECLAIMING_MATCH_ASSAY_STOCK_ID2` (view, 12 cols): `DESTINATION_ID_NEW` nvarchar(255), `DATE` date, `DOME` nvarchar(50), `MMYY` nvarchar(4), `MM+1YY` nvarchar(4), `MM-1YY` nvarchar(4), `DESTINATION` nvarchar(50), `DESTINATION_ID` nvarchar(50), `STOCK_ID` nvarchar(255), `STOCK_ID_MMYY` varchar(4), `STOCK_ID_LEFT` nvarchar(255), `STOCK_ID_RIGHT` nvarchar(255)
- `RECLAIMING_ORIGIN_DESTINATION` (view, 10 cols): `DATE` date, `CONTRACTOR` nvarchar(4000), `ACTIVITY` nvarchar(50), `MATERIAL` varchar(3), `ORIGIN_AREA` nvarchar(306), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(306), `DESTINATION_ID` nvarchar(50), `RIT` int, `WMT` float
- `RECLAIMING_REJECT_POURCENTAGE` (view, 5 cols): `YEAR` float, `MONTH` float, `REJECT_WMT` float, `RECLAIMING_WMT` float, `%_REJECT_RECLAIMING` float
- `RECLAIMING_REJECT_POURCENTAGE_DATE` (view, 8 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` date, `ORIGIN_PIT` nvarchar(50), `REJECT_WMT` float, `RECLAIMING_WMT` float, `%_REJECT_RECLAIMING` float
- `RECLAIMING_WB_TREATED_3_JOIN` (view, 10 cols): `DATE` date, `ID_DT` nvarchar(50), `DOME_FINAL` nvarchar(50), `ORIGIN_DOME` nvarchar(255), `COMPANY_DEST` nvarchar(50), `NEW_CONTRACTOR` varchar(13), `DESTINATION` nvarchar(50), `WMT` float, `SHIFT` int, `DT_COMPANY` varchar(13)
- `RECLAIMNG WB TREATED GROUPED` (view, 10 cols): `DATE` date, `TYPE` varchar(10), `ID_DT` nvarchar(50), `TRIPS` int, `NEW_CONTRACTOR` varchar(13), `ORIGIN` nvarchar(255), `DESTINATION` nvarchar(50), `WMT` float, `SHIFT` int, `DT_COMPANY` varchar(13)
- `RECLASSIFICATION_MISSING` (view, 14 cols): `CONTRACTOR` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `STOCK_TYPE` nvarchar(50), `SURVEY_CLASS` varchar(5), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `Ni` float, `MATERIAL` nvarchar(50), `DATE_OPEN` date, `DATE_COMPLETE` date, `DATE_TRANSFER` date, `DATE_FINISH` date, … +2 more
- `RECLASSIFICATION_TOS_MISSING` (view, 8 cols): `MATERIAL` varchar(4), `STOCK_TYPE` varchar(3), `Ni` float, `PLAN_Ni` float, `TOS_Ni` float, `BM_Ni` float, `PLAN_Fe` float, `STOCK_ID` nvarchar(255)
- `RECONCIL_OK` (view, 22 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(255), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +10 more
- `RECONCIL_ST_LT` (view, 43 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(255), `block_ID` nvarchar(269), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +31 more
- `RECONCIL_TC0` (view, 22 cols): `YEAR` float, `MONTH` float, `WEEK` float, `contractor` nvarchar(255), `pit` nvarchar(4000), `block_ID` nvarchar(255), `MATERIAL` nvarchar(255), `WMT` float, `DMT` float, `Ni` float, `Fe` float, `Co` float, … +10 more
- `REMAINING_RESERVES_BM_OK` (view, 23 cols): `X` float, `Y` float, `Z` float, `block_id` nvarchar(50), `DEPOSIT` nvarchar(50), `MATERIAL` varchar(3), `MP` varchar(7), `BCM` float, `WMT` float, `DMT` float, `Fe` float, `MC` float, … +11 more
- `REQUEST_FENI_PLAN` (view, 3 cols): `DOME` nvarchar(-1), `DATE` date, `REQUEST` varchar(9)
- `REQUEST_FULL` (view, 4 cols): `DOME` nvarchar(255), `DATE` datetime, `REQUEST` nvarchar(255), `COMPANY` nvarchar(255)
- `REQUEST_LAST` (view, 4 cols): `DATE` datetime, `DOME` nvarchar(255), `PLANT` nvarchar(255), `REQUEST` varchar(7)
- `REQUEST_VS_HAULAGE` (view, 9 cols): `STOCK_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(260), `FIRST_REQUEST_SHIFT` nvarchar(255), `FIRST_REQUEST_DATE` datetime, `WMT_REQUEST` float, `DATE_HAULAGE` date, `WMT_HAULAGE` float
- `ROLLING_MINE_PLAN_TREATED` (view, 11 cols): `YEAR` int, `MONTH` int, `CONTRACTOR` nvarchar(50), `DEPOSIT` nvarchar(50), `PIT` nvarchar(50), `PIT_ID` nvarchar(50), `WMT_ROM` float, `MATERIAL` nvarchar(50), `UPDATE` date, `NB_DAYS` float, `DAILY_AVERAGE_WMT` float
- `ROLLING_MINE_PLAN_TREATED_2` (view, 11 cols): `YEAR` int, `MONTH` int, `CONTRACTOR` nvarchar(50), `DEPOSIT` nvarchar(50), `LIM_ROM_PLAN` float, `SAP_ROM_PLAN` float, `WST_ROM_PLAN` float, `LIM_PLAN` float, `SAP_PLAN` float, `WST_PLAN` float, `SHIFT` varchar(2)
- `RSF RSF_REPORT` (view, 19 cols): `YEAR` float, `MONTH` float, `WEEK` float, `EXERCICE` nvarchar(255), `LAST_SURVEY` datetime, `DATE` datetime, `SHIFT` nvarchar(50), `LAYER` nvarchar(50), `ELEVATION` float, `LOCATION` nvarchar(50), `ITEM` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), … +7 more
- `RSF RSF_SURVEY_TREATED` (view, 6 cols): `LAST_SURVEY` datetime, `LAYER` nvarchar(50), `NAME` nvarchar(50), `ITEM` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), `PROGRESS_VOLUME` float
- `RSF_HAULING_DATA_DAILY` (view, 11 cols): `DATE` datetime, `SHIFT` int, `CONTRACTOR` nvarchar(50), `UNIT_TYPE` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `RIT` int, `YEAR` float, `MONTH` float, `WEEK` float, `TF` int
- `RSF_HAULING_TO_TRAFIC_MGMT` (view, 12 cols): `DATE` datetime, `SHIFT` int, `COMPANY` nvarchar(50), `DEPARTEMENT` nvarchar(50), `UNIT_TYPE` nvarchar(50), `NB_UNIT` int, `TRIP_PER_UNIT` int, `START_TIME` int, `ORIGIN_KM` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION_KM` nvarchar(50), `DESTINATION` nvarchar(50)
- `RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR` (view, 16 cols): `DATE` datetime, `SHIFT` int, `COMPANY` nvarchar(50), `DEPARTEMENT` nvarchar(50), `UNIT_TYPE` nvarchar(50), `NB_UNIT` int, `TRIP_PER_UNIT` int, `START_TIME` int, `ORIGIN_KM` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION_KM` nvarchar(50), `DESTINATION` nvarchar(50), … +4 more
- `RSF_REPORT` (view, 22 cols): `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `LAST_DATE` datetime, `LAYER` nvarchar(50), `ELEVATION` float, `NAME` nvarchar(50), `ITEM` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), `RL_ELEVATION` float, `PROGRESS_VOLUME` float, … +10 more
- `S123_STOCK_SHAPE_QGIS_TEST` (view, 9 cols): `UPDATE_DATE` datetime, `OBJECTID` int, `name` nvarchar(255), `CreationDa` datetime, `Creator` nvarchar(255), `EditDate` datetime, `new_dome_i` nvarchar(255), `GEOM` geometry(-1), `menggantik` nvarchar(255)
- `S123_TOS_STATUS_CLEAN` (view, 9 cols): `UPDATE_DATE` datetime, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `TOS_AREA` nvarchar(255), `OLD_PILE` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)
- `SAF_OVERSPEED` (view, 19 cols): `ID` int, `SAFETY_COMPANY` nvarchar(255), `SAFETY_AGENT` nvarchar(255), `DATE` date, `SHIFT` int, `TIME` time, `ROAD` nvarchar(255), `KILOMETER` float, `ROAD_LANE` nvarchar(50), `CONTRACTOR` nvarchar(255), `UNIT_TYPE` nvarchar(255), `UNIT_ID` nvarchar(255), … +7 more
- `SAF_OVERSPEED_LIMIT` (view, 18 cols): `SAFETY_COMPANY` nvarchar(255), `SAFETY_AGENT` nvarchar(255), `DATE` date, `SHIFT` int, `TIME` time, `ROAD` nvarchar(255), `KILOMETER` float, `ROAD_LANE` nvarchar(50), `CONTRACTOR` nvarchar(255), `UNIT_TYPE` nvarchar(255), `UNIT_ID` nvarchar(255), `SPEED` float, … +6 more
- `SAMPLING BRIDGE CERTIFICATE` (view, 25 cols): `DATE` date, `JOB NO` nvarchar(50), `DOME` nvarchar(50), `Total` float, `MC` float, `DMT` float, `Ni` float, `Co` float, `MgO` float, `CaO` float, `Fe` float, `P` float, … +13 more
- `SAMPLING_CONTRACTOR_PREP` (view, 16 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN_TYPE` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_TYPE` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `MATERIAL` varchar(3), `DESTINATION_ID` nvarchar(50), `CONTRACTOR_HAULING` nvarchar(50), … +4 more
- `SHORT_TERM_RECONCIL` (view, 25 cols): `YEAR` float, `MONTH` float, `WEEK` float, `date` datetime, `contractor` nvarchar(255), `DEPOSIT` nvarchar(50), `SUBPIT` nvarchar(255), `block_id` nvarchar(50), `DOMINANT_PROP` varchar(7), `SECOND_DOMINANT_PROP` varchar(7), `Ni_BM_LIM` float, `Ni_BM_SAP` float, … +13 more
- `START LIM STOCK` (table, 16 cols): `ID` int, `DATE` datetime, `DOME` nvarchar(255), `WMT` float, `Ni` float, `Fe` float, `SM` float, `SiO2` float, `MgO` float, `Co` float, `Al2O3` float, `CaO` float, … +4 more
- `STOCK_CERTIFICATE_NEWS` (view, 15 cols): `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `STATUS` varchar(5), `MATERIAL` nvarchar(50), `DATE_CERT` date, `DATE_OPEN` date, `DATE_CLOSE` date, `CERT_CONTRACTOR` nvarchar(50), `WMT_CARRIED` float, `WMT_SURVEY` float, `WMT_SENT` float, … +3 more
- `STOCK_INFOS` (view, 28 cols): `DOME` nvarchar(255), `LOCATION` nvarchar(255), `STOCK_STATUS` varchar(8), `STATUS_HAULAGE` varchar(8), `STATUS_RECLAIMING` varchar(10), `HIGH_TURN` int, `PRIORITY_RECLAIM` int, `CLOSE_HAULING` date, `CLOSE_RECLAIMING` date, `MATERIAL` nvarchar(50), `DATE_SIGNED` datetime, `PLANT_SIGNED` nvarchar(255), … +16 more
- `STOCK_INFO_FULL` (view, 23 cols): `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(260), `STOCK_AREA` nvarchar(255), `STOCK_STATUS` varchar(8), `HIGH_TURN` int, `PRIORITY_RECLAIM` int, `MATERIAL` nvarchar(50), `RECL` nvarchar(10), `STOCK_LOGISTIC` varchar(3), `REQUEST_PLANT` nvarchar(306), `REQUEST_DATE` datetime, `REQUEST` nvarchar(255), … +11 more
- `STOCK_MANAGEMENT` (view, 109 cols): `YEAR` float, `MONTH` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `SURVEY_WEEK` float, `SURVEY_TYPE` nvarchar(255), `SURVEY_CLASS` nvarchar(10), `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_PIT` nvarchar(50), … +97 more
- `STOCK_MANAGEMENT_RE` (view, 117 cols): `YEAR` float, `MONTH` float, `YEAR_SALES` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `SURVEY_WEEK` float, `SURVEY_TYPE` nvarchar(255), `SURVEY_CLASS` nvarchar(10), `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), … +105 more
- `STOCK_MANAGEMENT_RE_WITH_FENI_PLAN` (view, 118 cols): `YEAR` float, `MONTH` float, `YEAR_SALES` float, `MONTH_SALES` float, `WEEK` float, `DATE` datetime, `SURVEY_WEEK` float, `SURVEY_TYPE` nvarchar(255), `SURVEY_CLASS` nvarchar(10), `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), … +106 more
- `STOCK_ORIGIN_PIT` (view, 2 cols): `STOCK_ID` nvarchar(50), `ORIGIN_PIT` nvarchar(50)
- `STOCK_ORIGIN_PIT_BY_WMT` (view, 3 cols): `DESTINATION_ID` nvarchar(50), `ORIGIN_PIT` varchar(5), `WMT` float
- `STOCK_POS_YARD` (view, 3 cols): `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(260)
- `STOCK_REQUESTS_TREATED` (view, 10 cols): `FIRST_DATE_SHARE` datetime, `LATEST_DATE_SHARE` datetime, `ORIGIN_ID` nvarchar(55), `MAX_DATE_REQUEST` datetime, `MIN_DATE_REQUEST` datetime, `MAX_WMT_REQUEST` float, `MIN_WMT_REQUEST` float, `LATEST_DESTINATION_ID_REQUESTED` nvarchar(55), `LATEST_DESTINATION_AREA_REQUESTED` nvarchar(55), `REQUESTED_BY_IWIP` nvarchar(55)
- `STOCK_REQUESTS_TREATED_2` (view, 9 cols): `FIRST_DATE_SHARE` datetime, `LATEST_DATE_SHARE` datetime, `ORIGIN_ID` nvarchar(255), `MIN_DATE_REQUEST` datetime, `MAX_DATE_REQUEST` datetime, `MAX_WMT_SHARED` float, `MIN_WMT_SHARED` float, `LATEST_DESTINATION_ID_REQUESTED` nvarchar(255), `LATEST_DESTINATION_AREA_REQUESTED` nvarchar(260)
- `STOCK_SHAPE` (view, 9 cols): `id` int, `name` nvarchar(255), `CreationDa` datetime, `Creator` nvarchar(255), `EditDate` datetime, `geom` geography(-1), `new_dome_i` nvarchar(255), `old_dome_i` nvarchar(255), `menggantik` nvarchar(255)
- `STOCK_SHAPE_LAST` (view, 3 cols): `STOCK_ID` nvarchar(255), `EditDate` datetime, `geom` geography(-1)
- `STOCK_STATUS_FLOW` (view, 14 cols): `CONTRACTOR` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(255), `DATE_HAULAGE_START` datetime, `DATE_HAULAGE_END` datetime, `RECLAIMING_PLANT` nvarchar(50), `DATE_RECLAIMING_START` datetime, `DATE_RECLAIMING_END` datetime, `WMT_HAUL` float, `WMT_RECLAIM` float, `DATE_REJECT_START` datetime, … +2 more
- `STOCK_STATUS_FULL` (view, 13 cols): `ORIGIN_PIT` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `ORIGIN_ID` nvarchar(255), `STOCK_STATUS` varchar(8), `MATERIAL` nvarchar(50), `HIGH_TURN` int, `PRIORITY_RECLAIM` int, `DATE_OPEN` date, `DATE_COMPLETE` date, `DATE_TRANSFER` date, … +1 more
- `STOCK_STATUS_SIMPLE` (view, 8 cols): `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `STATUS` varchar(5), `MATERIAL` nvarchar(50), `DATE_OPEN` date, `DATE_CLOSE` date, `REMARK` nvarchar(255)
- `STOCK_STATUS_STATUS` (view, 15 cols): `CONTRACTOR` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `STOCK_STATUS` varchar(8), `MATERIAL` nvarchar(50), `HIGH_TURN` int, `PRIORITY_RECLAIM` int, `DATE_OPEN` date, `DATE_COMPLETE` date, `DATE_TRANSFER` date, … +3 more
- `STOCK_TYPE_ALL` (view, 2 cols): `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(255)
- `STOCK_WMT_EVOLUTION` (view, 16 cols): `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `ORIGIN_PIT` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(260), `DATE_OPEN` date, `DATE_COMPLETE` date, `DATE_TRANSFER` date, `DATE_FINISH` date, … +4 more
- `SUM PROD WMT FOR CORR` (view, 6 cols): `YEAR` float, `MONTH` float, `contractor` nvarchar(255), `pit` nvarchar(255), `WMT_ACTUAL` float, `FINAL_RECLASSIFICATION` nvarchar(255)
- `SUM WMT SURVEY` (view, 7 cols): `YEAR` float, `CONTRACTOR` nvarchar(255), `MONTH` float, `PIT` nvarchar(255), `MATERIAL_ID` nvarchar(255), `WMT_SURVEY` float, `BCM_SURVEY` float
- `SURVEY POS CONSOLIDATED` (view, 6 cols): `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `DOME` nvarchar(255), `WMT` float, `STOCK TYPE` nvarchar(255)
- `SURVEY_POS_DATED` (view, 15 cols): `ID` int, `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `STOCK_AREA` nvarchar(255), `DOME` nvarchar(255), `IS_MAX_WMT` varchar(3), `DOME ID` nvarchar(255), `SURVEY METHOD` nvarchar(255), `ORIGIN_PIT` nvarchar(50), `VOLUME (LCM)` float, `VOLUME (BCM)` float, … +3 more
- `SURVEY_POS_ESTIMATE_HAULAGE` (view, 9 cols): `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `DOME` nvarchar(255), `WMT_SURVEY` float, `WMT_PREVIOUS` float, `WMT_EST_HAULAGE` float, `ACTIVITY` varchar(10), `STOCK TYPE` nvarchar(255)
- `SURVEY_POS_FOR_PROD` (view, 8 cols): `DATE` datetime, `SURVEY_TYPE` nvarchar(255), `SURVEY_WEEK` float, `MATERIAL` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(255), `PIT` nvarchar(255), `WMT` float
- `SURVEY_POS_TC` (view, 6 cols): `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `DOME` nvarchar(255), `WMT` float, `STOCK TYPE` nvarchar(255)
- `SURVEY_STOCK_MAX` (view, 3 cols): `DOME` nvarchar(255), `WMT` float, `DATE` datetime
- `TEAM_PROFILE` (table, 12 cols): `id` int, `user_id` int, `availability_pct` int, `workload_pct` int, `skills` varchar(-1), `contractor_company` varchar(150), `full_name` varchar(150), `email` varchar(100), `due_date` date, `completed_at` datetimeoffset, `created_at` datetimeoffset, `updated_at` datetimeoffset
- `TEST_CAROTTE` (view, 25 cols): `YEAR` int, `MONTH` int, `PIT` varchar(5), `CONTRACTOR_PILE` varchar(3), `MATERIAL` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `WMT` float, `BM_MC` float, `BM_Ni` float, … +13 more
- `TOS` (table, 11 cols): `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)
- `TOS FOLLOW TREATED` (view, 12 cols): `DATE` datetime, `POS DOME` nvarchar(255), `POS` nvarchar(255), `WMT_TOTAL` float, `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `SHIFT` nvarchar(255), `BLOCK ID` nvarchar(255), `TOS` nvarchar(255), `POS NEW` nvarchar(255), `TYPE` varchar(10), `ORIGIN` nvarchar(255)
- `TOS FOLLOW TREATED 2` (view, 36 cols): `DATE` datetime, `SHIFT` nvarchar(255), `ORIGIN` nvarchar(255), `TOS` nvarchar(255), `PILE_ID` nvarchar(255), `DESTINATION` nvarchar(255), `POS` nvarchar(255), `DOME_ID` nvarchar(255), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `TYPE` varchar(10), `WMT_TOTAL` float, … +24 more
- `TOS_DUMP_COORDINATES_UNIQUE` (view, 7 cols): `TOS_TYPE` nvarchar(50), `TOS_PIT` nvarchar(255), `TOS_NUMBER` int, `TOS_CONTRACTOR` nvarchar(255), `TOS_X` int, `TOS_Y` int, `COUNT` int
- `TOS_Duplicate` (view, 37 cols): `Sampling_Contractor` nvarchar(50), `Sampling_date` datetime, `Original_Sample` nvarchar(50), `Duplicate_Sample` nvarchar(50), `Pit` nvarchar(50), `Stock_ID` nvarchar(50), `BLOCK_ID` nvarchar(50), `ReturnDate` date, `Assay_Type` nvarchar(50), `Activity` nvarchar(50), `Stock_type` nvarchar(50), `Production_Contractor` nvarchar(255), … +25 more
- `TOS_PILES_WMT_WB_RIT_MINING` (view, 8 cols): `YEAR` float, `MONTH` float, `CONTRACTOR` nvarchar(255), `DEPOSIT` nvarchar(255), `TOT_RIT` float, `TOS_PILE` nvarchar(255), `WMT_WB` float, `MATERIAL` nvarchar(255)
- `TOS_PILE_FINAL_RECLASSIFICATION` (view, 2 cols): `TOS_PILE` nvarchar(255), `FINAL_RECLASSIFICATION` nvarchar(255)
- `TOS_PILE_INFO_TREATED` (view, 5 cols): `TOS_PILE` nvarchar(50), `TOS` nvarchar(50), `CONTRACTOR_PROD` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), `PIT` nvarchar(50)
- `TOS_PILE_PIT` (view, 3 cols): `TOS PILE` nvarchar(255), `PIT` nvarchar(255), `TYPE_PROD` nvarchar(255)
- `TOS_STATUS_ERROR_TRANSFER_DATE` (view, 3 cols): `MIN_TRANSFER_DATE` datetime, `MIN_COMPLETE_DATE` datetime, `STOCK_ID` nvarchar(50)
- `TOS_SURVEY_ESTIMATION` (view, 18 cols): `DATE` datetime, `SHIFT` int, `DATETIME` datetime, `STOCK_TYPE` varchar(3), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `STATUS` varchar(8), `CONTRACTOR` nvarchar(255), `ACTIVITY` varchar(15), `MATERIAL` nvarchar(255), `RIT` float, `TF` float, … +6 more
- `TOS_SURVEY_ESTIMATION2` (view, 13 cols): `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` int, `SURVEY_TYPE` varchar(9), `SURVEY_WEEK` int, `SURVEY_METHOD` int, `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(50), `STOCK_STATUS` nvarchar(50), `LCM` int, `BCM` int, `LOOS_DENS` int, … +1 more
- `TOS_SURVEY_trial` (view, 10 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `TOS_LOCATION` nvarchar(255), `PILE_ID` nvarchar(255), `PILE_STATUS` nvarchar(255), `OMR_RIT` float, `OMR_TF` float, `WMT_MINING` float, `WMT_MINING_CUMULATIVE` float
- `TSS_NO_MATCH_POINT` (view, 2 cols): `NEW_STATION` nvarchar(4000), `OLD_STATION` nvarchar(255)
- `TSS_PREP` (view, 22 cols): `YEAR` int, `MONTH` int, `WEEK` int, `CONTRACTOR` nvarchar(50), `DATE` datetime, `AREA` nvarchar(255), `SUB_AREA` nvarchar(255), `MANAGER` nvarchar(255), `TYPE` nvarchar(255), `MINE` nvarchar(255), `STATION` nvarchar(255), `OUTFALL` nvarchar(255), … +10 more
- `UNIT_TRIPS_HUAFEI_RSF` (view, 10 cols): `DATE` datetime, `SHIFT` int, `COMPANY` nvarchar(50), `NB_UNIT` nvarchar(50), `TRIP` float, `ORIGIN_KM` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION_KM` nvarchar(50), `DESTINATION` nvarchar(50), `DT_COMPANY` varchar(13)
- `VW_PRODUCTION_ACTIVITY_PIT` (view, 26 cols): `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `AREA` nvarchar(255), `SUB_AREA` nvarchar(255), `ACTIVITY` nvarchar(255), `ENTITY` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `ORIGIN_ID_BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), `BLAST_ID` nvarchar(255), … +14 more
- `WAITING_TIME_DIFFERENCE` (view, 20 cols): `TEAM` nvarchar(10), `DATE` date, `EQUIPMENT_ID` nvarchar(50), `SHIFT` int, `ORIGIN_ID` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `DESTINATION` nvarchar(100), `BLOCK_ID` nvarchar(50), `RIT` int, `WB_ID` nvarchar(50), `LOADING_WAITING_TIME` time, `LOADING_TIME` time, … +8 more
- `WAITING_TIME_FIX` (view, 20 cols): `TEAM` nvarchar(10), `DATE` date, `EQUIPMENT_ID` nvarchar(50), `SHIFT` int, `ORIGIN_ID` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `BLOCK_ID` nvarchar(50), `RIT` int, `WB_ID` nvarchar(50), `LOADING_WAITING_TIME` time, `LOADING_TIME` time, `LOADING_DIFFERENCE_TIME` int, … +8 more
- `WBN_DATABASE_ERROR_PROCEDURE` (table, 8 cols): `Id` int, `ErrorNumber` int, `ErrorSeverity` int, `ErrorState` int, `ErrorProcedure` nvarchar(200), `ErrorLine` int, `ErrorMessage` nvarchar(-1), `ErrorDate` datetime
- `WEIGHBRIDGE_&_TRUCKCOUNT_TF_LAST` (view, 2 cols): `CONTRACTOR_HAUL` nvarchar(50), `AVG_TF` float
- `WEIGHBRIDGE_&_TRUCKCOUNT_TF_PER_WEEK` (view, 6 cols): `YEAR` float, `MONTH` float, `WEEK` float, `CONTRACTOR_HAUL` nvarchar(50), `PIT_ORIGIN` nvarchar(50), `AVG_TF` float
- `WMT_3RD_PARTY_LAST` (view, 7 cols): `DATE` datetime, `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(55), `CONTRACTOR` nvarchar(4000), `WMT_SENT` float, `WMT_SENT_ORIGINAL` float, `WMT_SENT_RATE` float
- `WMT_LAST_CERT` (view, 5 cols): `DATE` datetime, `DOME` nvarchar(50), `CONTRACTOR` nvarchar(4000), `WMT_POS_SENT` float, `WMT_YARD_SENT` float
- `_LIMONITE_DAILY_STOCK` (view, 27 cols): `DATE` datetime, `deposit_code` nvarchar(255), `subpit` nvarchar(255), `WMT` float, `CF` float, `DOME` nvarchar(255), `TOS_PILE` nvarchar(255), `Ni` float, `Fe` float, `Co` float, `SiO2` float, `MgO` float, … +15 more
- `_PROD_BLAST_ASSAYS` (view, 24 cols): `CONTRACTOR` nvarchar(255), `DATE` datetime, `shift` float, `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_id` nvarchar(255), `material` nvarchar(255), `CF` float, `WMT` float, `destination` nvarchar(255), … +12 more
- `_ore_screened_or_not` (view, 2 cols): `DOME` nvarchar(50), `MATERIAL` varchar(10)
- `_prod_lim_assays` (view, 24 cols): `DATE` datetime, `deposit_code` nvarchar(255), `subpit` nvarchar(255), `TYPE` varchar(8), `prod_ID` nvarchar(255), `contractor` nvarchar(255), `WMT` float, `CF` float, `DOME` nvarchar(255), `TOS_PILE` nvarchar(255), `Ni` float, `Fe` float, … +12 more
- `_prod_lim_assays_via_BM` (view, 24 cols): `DATE` datetime, `deposit_code` nvarchar(255), `subpit` nvarchar(255), `TYPE` varchar(8), `prod_ID` nvarchar(255), `contractor` nvarchar(255), `WMT` float, `CF` float, `DOME` nvarchar(255), `TOS_PILE` nvarchar(255), `Ni` float, `Fe` float, … +12 more
- `autoBM_GROUP` (view, 34 cols): `LAST_UPDATE` datetime, `DEPOSIT` nvarchar(12), `block_id` nvarchar(24), `size (X)` float, ` size(Y)` float, ` size(Z)` float, `VOLUME` float, `MATERIAL_CLASS` nvarchar(12), `DENSITY` float, `WMT` float, `DMT` float, `Al2O3` float, … +22 more
- `autoPLAN_Ni` (view, 6 cols): `STOCK_ID` nvarchar(55), `MC` float, `Ni` float, `Fe` float, `SiO2` float, `MgO` float
- `autoQC_CF_BM_PROP` (table, 17 cols): `DATETIME` datetime, `ORIGIN_PIT` nvarchar(10), `MATERIAL` varchar(3), `BM_MC_PROP` float, `BMC_MC_PROP` float, `BM_Ni_PROP` float, `BMC_Ni_PROP` float, `BM_Fe_PROP` float, `BMC_Fe_PROP` float, `BM_SiO2_PROP` float, `BMC_SiO2_PROP` float, `BM_MgO_PROP` float, … +5 more
- `autoQC_PLAN_NI_CF` (view, 22 cols): `LAST_UPDATE` datetime, `YEAR` int, `MONTH` int, `DATE` date, `MATERIAL` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `CONTRACTOR_PILE` nvarchar(50), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, … +10 more
- `autoTOS_SURVEY_ESTIMATION_view` (view, 21 cols): `LAST_UPDATE` nvarchar(50), `DATE` datetime, `SHIFT` int, `DATETIME` datetime, `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(50), `CONTRACTOR_PILE` varchar(3), `PIT` varchar(5), `STATUS` nvarchar(50), `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), … +9 more
- `auto_view_QC_STOCK_ALL_VIA_ALL` (view, 90 cols): `LAST_UPDATE` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(260), `Ni_` float, `PLAN_MC` float, `PLAN_Ni` float, `PLAN_Fe` float, `PLAN_SiO2` float, `PLAN_MgO` float, `DEF_ASSAY_TYPE` nvarchar(101), `DEF_MC` float, `DEF_Ni` float, … +78 more
- `blasting_production` (table, 19 cols): `ID` int, `Contractor` nvarchar(255), `Year` float, `Month` nvarchar(255), `Week` float, `Date` datetime, `Shift` nvarchar(255), `Pit` nvarchar(255), `Sub_Pit` nvarchar(255), `Prod ID` nvarchar(255), `BM ID` nvarchar(255), `Class BM` nvarchar(255), … +7 more
- `block_prod` (view, 23 cols): `ID` int, `contractor` nvarchar(255), `Date` datetime, `shift` float, `deposit_code` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `prod_ID` nvarchar(255), `block_id` nvarchar(255), `block_ID_2` nvarchar(255), `CLASS_BM` int, `material` nvarchar(255), … +11 more
- `equipments_status_last_breakdown` (view, 4 cols): `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `MAX_DATE_EQ` date, `MAX_DATE_CONTRACTOR` date
- `geometry_columns` (view, 11 cols): `f_table_catalog` nvarchar(128), `f_table_schema` nvarchar(128), `f_table_name` nvarchar(128), `f_geometry_column` nvarchar(128), `coord_dimension` int, `srid` int, `geometry_type` varchar(30), `qgis_xmin` float, `qgis_ymin` float, `qgis_xmax` float, `qgis_ymax` float
- `tempHAULAGE_IWIP` (table, 1 cols): `No` nvarchar(255)
- `test sa mere` (view, 11 cols): `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `NBDAYS` float, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(50), `CLASS_MATERIAL` nvarchar(50), `WMT_ROM_MONTHLY` float, `WMT_DAILY` float, `TYPE_DATA` varchar(6)
- `trial cek tos follow vs haulage iwip ` (view, 8 cols): `DATE` datetime, `DOME_ID` nvarchar(255), `POS` nvarchar(255), `TS_WMT` float, `DESTINATION_ID_CLEAN` nvarchar(50), `DESTINATION_AREA_CLEAN` nvarchar(50), `WMT_HAULAGE` float, `SELISIH_WMT` float
- `vOSPAT_RESULTS` (view, 22 cols): `CONTRACTOR` nvarchar(4000), `TestDateTime` datetime, `TestDateShift` date, `TestShift` float, `Tag` int, `EmployeeID` nvarchar(41), `Employee FamilyName` nvarchar(41), `Employee FirstName` nvarchar(41), `EmploymentStatus` nvarchar(41), `EmployeePositionName` nvarchar(81), `SupervisorPositionName` nvarchar(81), `TerminalName` nvarchar(41), … +10 more
- `vw_HAULAGE_GROUP` (view, 11 cols): `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `RIT` int, `WMT` float
- `w2_EQUIPMENTS` (view, 13 cols): `ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `OWNER` nvarchar(50), `TYPE` nvarchar(50), `DIGIT` int, `MANUFACTURER` nvarchar(50), `MODEL` nvarchar(50), `CAPACITY` int, `NB_TYRES` int, `BUILD_YEAR` int, `DIVISION` nvarchar(50), … +1 more
- `w2_EQUIPMENTS_STATUS` (view, 17 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `ID_EQ` nvarchar(50), `STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `LOCATION` nvarchar(50), `LOCATION_DETAILS` nvarchar(50), `HOUR_METER_START` float, `HOUR_METER_END` float, `USAGE_KM_METER` float, … +5 more
- `w2_PRODUCTION_PIT_HOURLY` (view, 19 cols): `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `TIME_GROUP` nvarchar(11), `START_HOUR` int, `END_HOUR` int, `ACTIVITY_TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` nvarchar(255), `SUB_PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), … +7 more

</details>

<details><summary>1 objects errored during deep scan</summary>

- HAUL_ROAD_STA: Unsupported UTF-8 sequence length when encoding string

</details>

### FMS_DB

90 objects: 54 tables, 36 views. 59 deep-scanned (samples, date ranges, ID vocabularies); 71 have row counts; the rest are views, which carry no stored count.

#### All non-empty objects by size

| Object | Type | Rows | Date range | Cols |
|---|---|---|---|---|
| `FMS_PLAYBACK_TRACK_DATA` | table | 26,422,013 | 2026-03-21 → 2026-07-30 | 18 |
| `FMS_PLAYBACK_TRACK_CLEAN` | view | 26,422,013 | 2026-03-21 → 2026-07-30 | 23 |
| `auto_kmFMS_PLAYBACK_TRACK_DATA` | table | 19,413,560 | — | 4 |
| `FMS_ENTRY_EXIT_DATA` | table | 11,627,431 | 2026-06-08 → 2026-07-30 | 12 |
| `FMS_ENTRY_EXIT_CLEAN` | view | 11,627,431 | 2026-06-08 → 2026-07-30 | 12 |
| `FMS_SECURITY_INCIDENT_DATA` | table | 5,347,725 | — | 36 |
| `autoFMS_SECURITY_INCIDENT_KILOMETER` | table | 4,168,389 | — | 4 |
| `auto_spFMS_PLAYBACK_TRACK_DATA` | table | 1,701,102 | — | 5 |
| `FMS_INTERVENTION_EVENT_DATA` | table | 1,267,116 | — | 32 |
| `FMS_PLAYBACK_TRACK_24H` | table | 1,094,670 | — | 14 |
| `FMS_GPS_Historical` | table | 521,918 | — | 15 |
| `FMS_PLAYBACK_STAY_DATA` | table | 387,997 | 2026-03-22 → 2026-07-30 | 43 |
| `FMS_PLAYBACK_STAY_CLEAN` | view | 387,997 | 2026-02-24 → 2026-07-30 | 12 |
| `FMS_RISK_DATA` | table | 316,302 | — | 19 |
| `VW_DISPATCHER_INCIDENT_REVIEW` | view | 289,552 | 2026-02-25 → 2026-07-30 | 19 |
| `OVERSPEED_EVENTS` | view | 160,895 | 2026-03-14 → 2026-07-30 | 32 |
| `FMS_HRM_SUPERVISION` | view | 76,552 | 2026-06-01 → 2026-07-30 | 17 |
| `FMS_GEOFENCE_VISITS` | table | 59,351 | — | 17 |
| `FMS_CONGESTION_SEG` | table | 34,988 | — | 9 |
| `FMS_PLAYBACK_TRACK_WORKINGHOURS` | view | 34,854 | 2026-02-24 → 2026-07-30 | 5 |
| `OVERSPEED_VEHICLE_SUMMARY` | view | 34,228 | 2026-03-14 → 2026-07-30 | 4 |
| `FMS_PLAYBACK_STAY_GROUP` | view | 27,503 | 2026-02-24 → 2026-07-30 | 4 |
| `FMS_PLAYBACK_TRACK_SEGMENT_COVERED` | view | 27,415 | 2026-07-30 → 2026-07-30 | 27 |
| `RES_EMPLOYEES` | table | 8,958 | — | 9 |
| `EQUIPMENTS_RADIO_STATUS` | view | 4,735 | — | 21 |
| `FMS_GEOFENCES` | table | 3,490 | — | 17 |
| `RADIO_REPROGRAM_TRACK` | table | 3,478 | — | 21 |
| `FMS_TOS_STATUS` | table | 3,404 | — | 14 |
| `FMS_TMS_TOKEN` | table | 2,926 | — | 3 |
| `LV_GEOFENCE_EVENTS` | view | 1,533 | 2026-05-10 → 2026-07-29 | 29 |
| `FMS_EQUIPMENTS` | table | 1,411 | 2026-03-22 → 2026-07-29 | 7 |
| `WT_DAILY_PLAN` | table | 1,241 | — | 10 |
| `FMS_UNIT_INSTALLED` | table | 1,194 | — | 4 |
| `FMS_EQUIPMENTS_CLEAN` | view | 1,194 | — | 4 |
| `FMS_TRUCK_ASSIGNMENTS` | table | 408 | 2026-01-07 → 2026-07-22 | 10 |
| `FMS_HAUL_CYCLES` | table | 288 | 2026-06-26 → 2026-07-24 | 10 |
| `FMS_QUALITY_DISPATCH` | table | 258 | 2026-06-23 → 2026-07-22 | 21 |
| `FMS_EQUIPMENTS_FILTER` | view | 182 | — | 4 |
| `VW_DISPATCHER_MONTHLY_KPI` | view | 137 | — | 13 |
| `FMS_DISPATCH_PLAN` | table | 105 | 2026-06-23 → 2026-07-22 | 16 |
| `SHP_SED_POND` | table | 91 | — | 4 |
| `FMS_ROADMAP` | table | 87 | — | 21 |
| `SAFETY_DPLAN` | table | 80 | — | 9 |
| `LV_PLAN` | table | 62 | 2026-05-11 → 2026-05-13 | 7 |
| `VW_DISPATCHER_DIM` | view | 61 | — | 1 |
| `LV_INFO` | table | 57 | — | 6 |
| `FMS_GEOFENCE_ALERTS` | table | 47 | — | 29 |
| `FMS_LV_ZONE_VISITS` | table | 43 | — | 13 |
| `FMS_LOGIN_IPS` | table | 37 | — | 5 |
| `FMS_USERS` | table | 30 | — | 8 |
| `RES_SPEED_LIMIT_ZONES` | table | 27 | — | 16 |
| `FMS_APP_STATE` | table | 23 | — | 3 |
| `FMS_USER_ACTIVITY` | table | 18 | — | 3 |
| `FMS_ASSIGNMENTS` | table | 17 | 2026-07-05 → 2026-07-28 | 5 |
| `FMS_JOB_RUNS` | table | 14 | — | 5 |
| `FMS_MESSAGES` | table | 14 | — | 15 |
| `RES_WATER_FILLING_POINTS` | table | 14 | — | 9 |
| `FMS_SETTINGS` | table | 7 | — | 3 |
| `FMS_LV_DAILY_REPORTS` | table | 6 | 2026-07-24 → 2026-07-29 | 12 |
| `FMS_LV_VISIT_VERIFICATIONS` | table | 4 | — | 13 |
| `RES_CRITICAL_ZONES` | table | 4 | — | 5 |
| `FMS_INSTANCES` | table | 2 | — | 7 |
| `FMS_DOCS` | table | 1 | — | 4 |
| `FMS_GEOFENCE_ALERT_RULES` | table | 1 | — | 17 |
| `FMS_ROADMAP_DOC` | table | 1 | — | 5 |
| `FMS_ROADMAP_META` | table | 1 | — | 2 |
| `FMS_TRUCK_CYCLES` | table | 1 | 2026-07-25 → 2026-07-25 | 16 |
| `FMS_SECURITY_INCIDENT_KILOMETER` | view | 1 | — | 4 |

#### Empty or view-only objects (columns catalogued)

<details><summary>22 further objects</summary>

- `CCR_RISK_EVENT_ACTIONS` (view, 43 cols): `Risk Shift Date` date, `Risk Shift` int, `Risk Shift Type` varchar(7), `Event_Risk_Level` nvarchar(255), `License Plate` nvarchar(255), `Actual_Group` varchar(8000), `Actual_Group_Clean` varchar(8000), `Planned_Groups` nvarchar(1023), `Is_Within_Planned_Group` int, `Driver` nvarchar(255), `Start Time` datetime, `End Time` datetime, … +31 more
- `FMS_ERROR_FLOW` (table, 8 cols): `Id` int, `ErrorNumber` int, `ErrorSeverity` int, `ErrorState` int, `ErrorProcedure` nvarchar(200), `ErrorLine` int, `ErrorMessage` nvarchar(-1), `ErrorDate` datetime
- `FMS_INTERVENTION_EVENT_CLEAN` (view, 26 cols): `FETCH_DATE` datetime, `Shift_Date` date, `Shift` int, `Risk Start Time` datetime, `Risk End Time` datetime, `Release Time` datetime, `Mileage(Km)` nvarchar(255), `eventId` nvarchar(255), `Group` varchar(8000), `intervener` nvarchar(255), `carrierName` nvarchar(255), `License Plate` nvarchar(255), … +14 more
- `FMS_LV_MOVEMENTS` (table, 15 cols): `EVENT_ID` varchar(36), `PLATE` varchar(32), `BOUNDARY_ID` nvarchar(20), `BOUNDARY_NAME` nvarchar(200), `GATE_ID` nvarchar(20), `GATE_NAME` nvarchar(200), `EXIT_TS` bigint, `RETURN_TS` bigint, `DURATION_SEC` int, `EXIT_LAT` float, `EXIT_LNG` float, `RETURN_LAT` float, … +3 more
- `FMS_RISK_CLEAN` (view, 18 cols): `FETCH_DATE` datetime, `Shift_Date` date, `Shift` int, `Group` varchar(8000), `Risk Level Code` float, `Risk Level` nvarchar(255), `Intervention Types` nvarchar(255), `Number Of Event` float, `License Plate` nvarchar(255), `riskId` nvarchar(255), `Driver` nvarchar(255), `Carrier Name` nvarchar(255), … +6 more
- `FMS_SECURITY_INCIDENT_CLEAN` (view, 25 cols): `DATE` date, `SHIFT` int, `Eventtypename` nvarchar(255), `Areaname` nvarchar(255), `Vehiclenumber` nvarchar(255), `checkDriverName` nvarchar(255), `Drivername` nvarchar(255), `DriverNo` nvarchar(255), `Contractor` nvarchar(255), `ContractorTeam` varchar(8000), `startTime` datetime, `endTime` datetime, … +13 more
- `IDLE_EVENTS_WT` (view, 29 cols): `ID` bigint, `Event_Type_Name` nvarchar(255), `Area_Name` nvarchar(255), `Area_Event` nvarchar(255), `Vehicle_Number` nvarchar(255), `Contractor` nvarchar(255), `Driver_Name` nvarchar(255), `Contractor_Team` varchar(-1), `Start_Time` datetime, `End_Time` datetime, `Duration_Seconds` float, `Duration_Minutes` float, … +17 more
- `KIMPER_MISSING_FMS_ID` (view, 3 cols): `checkDriverName` nvarchar(255), `driverNo` nvarchar(255), `DriverID` bigint
- `LV_DRIVER_INFO` (table, 6 cols): `Vehicle_Number` varchar(50), `Divisi` varchar(100), `Department` varchar(100), `Driver_DS` varchar(200), `Driver_NS` varchar(200), `Work_Location` varchar(200)
- `OSPAT_RESULTS` (view, 22 cols): `CONTRACTOR` nvarchar(4000), `TestDateTime` datetime, `TestDateShift` date, `TestShift` float, `Tag` int, `EmployeeID` nvarchar(41), `Employee FamilyName` nvarchar(41), `Employee FirstName` nvarchar(41), `EmploymentStatus` nvarchar(41), `EmployeePositionName` nvarchar(81), `SupervisorPositionName` nvarchar(81), `TerminalName` nvarchar(41), … +10 more
- `VW_FMS_EVENTS` (view, 33 cols): `Event_Type_Name` nvarchar(255), `Area_Name` nvarchar(255), `Area_Event` nvarchar(255), `Vehicle_Number` nvarchar(255), `Driver_Name` nvarchar(255), `Contractor` nvarchar(255), `Contractor_Team` varchar(-1), `Start_Time` datetime, `End_Time` datetime, `Start_Longitude` decimal, `Start_Latitude` decimal, `End_Latitude` decimal, … +21 more
- `VW_FMS_LV_VISIT_EVIDENCE` (view, 24 cols): `VISIT_KEY` nvarchar(240), `PLATE` nvarchar(60), `ENTER_TS` bigint, `EXIT_TS` bigint, `GEOFENCE_ID` nvarchar(20), `GEOFENCE_NAME` nvarchar(200), `ENTER_LAT` float, `ENTER_LNG` float, `EXIT_LAT` float, `EXIT_LNG` float, `DURATION_SEC` int, `DETECTED_DRIVER` nvarchar(200), … +12 more
- `VW_LV_ACTIVE_PLAN` (view, 13 cols): `Plan_Date` date, `Active_Date` date, `Shift` varchar(10), `Vehicle_Number` varchar(50), `Divisi` varchar(100), `Department` varchar(100), `Driver_DS` varchar(200), `Driver_NS` varchar(200), `Work_Location` varchar(200), `Region` varchar(20), `KM_From` decimal, `KM_To` decimal, … +1 more
- `VW_SAFETY_DPLAN` (view, 5 cols): `DATE` date, `Shift` nvarchar(255), `Dispatcher` nvarchar(255), `ID` float, `Groups` nvarchar(1023)
- `VW_WT_DAILY_PLAN` (view, 11 cols): `ID` int, `Shift_Date` date, `Vehicle_Number` varchar(20), `Region` varchar(10), `KM_From` int, `KM_To` int, `Primary_WF` varchar(50), `Target_Refills` int, `Created_Date` datetime, `Breakdown` varchar(3), `rn` bigint
- `VW_WT_PLAN_BREAKDOWN_STATUS` (view, 3 cols): `Shift_Date` date, `Vehicle_Number` varchar(20), `Breakdown` varchar(3)
- `VW_WT_REFILL_CYCLES` (view, 11 cols): `Shift_Date` date, `Vehicle_Number` nvarchar(255), `WF_Station_ID` nvarchar(50), `WF_Location` nvarchar(100), `Refill_Sequence` bigint, `Refill_End_Time` datetime, `Next_Refill_End_Time` datetime, `Max_Cycle_End_Time` datetime, `Primary_WF` varchar(50), `Is_Planned_WF_Refill` int, `Refill_WF_Status` varchar(10)
- `VW_WT_REFILL_CYCLE_SUMMARY` (view, 19 cols): `Shift_Date` date, `Vehicle_Number` nvarchar(255), `Refill_Sequence` bigint, `WF_Station_ID` nvarchar(50), `WF_Location` nvarchar(100), `Refill_End_Time` datetime, `Next_Refill_End_Time` datetime, `Max_Cycle_End_Time` datetime, `Planned_Region` varchar(10), `KM_From` int, `KM_To` int, `Primary_WF` varchar(50), … +7 more
- `VW_WT_TRACK_PLAN_SUMMARY` (view, 16 cols): `Shift_Date` date, `Vehicle_Number` nvarchar(50), `Planned_Region` varchar(10), `KM_From` int, `KM_To` int, `Primary_WF` varchar(50), `Target_Refills` int, `Total_Track_Points` int, `In_Zone_Track_Points` int, `Out_Of_Zone_Track_Points` int, `Zone_Compliance_Pct` decimal, `Total_Distance_Travelled_KM` decimal, … +4 more
- `VW_WT_TRACK_PLAN_SUMMARY_FINAL` (view, 21 cols): `Shift_Date` date, `Vehicle_Number` nvarchar(50), `Planned_Region` varchar(10), `KM_From` int, `KM_To` int, `Primary_WF` varchar(50), `Target_Refills` int, `Total_Track_Points` int, `In_Zone_Track_Points` int, `Out_Of_Zone_Track_Points` int, `Zone_Compliance_Pct` decimal, `Total_Distance_Travelled_KM` decimal, … +9 more
- `VW_WT_ZONE_COVERAGE` (view, 10 cols): `Shift_Date` date, `Region` varchar(10), `KM_From` int, `KM_To` int, `Track_Points_In_Zone` int, `Trucks_In_Zone` int, `Post_Refill_KM_In_Zone` decimal, `No_Coverage_Flag` int, `Is_Latest_Shift` int, `Is_Previous_Shift` int
- `WATER_POINTS_GEOFENCE` (view, 13 cols): `Region` nvarchar(50), `Location` nvarchar(100), `Station ID` nvarchar(50), `Contractor` nvarchar(50), `Status` nvarchar(20), `Latitude` float, `Longitude` float, `Dispenser_Count` int, `Match_Radius_Meters` float, `Min_Lat` float, `Max_Lat` float, `Min_Lng` float, … +1 more

</details>

<details><summary>1 objects errored during deep scan</summary>

- FMS_LV_VISIT_VERIFICATIONS: Overlong 3 byte UTF-8 sequence detected when encoding string

</details>

## What this means for the simulator

Nothing in the codebase was changed by this scan. These are the corrections and opportunities it surfaces, in priority order.

1. **Correct the GPS claim.** "0 of 940 haul trucks in the GPS feed" is wrong and appears in `README.md`, `MODEL_FINDINGS.md` and the `/api/simulate` `model_limits` payload. The accurate statement is that haul trucks are instrumented at 3-second resolution, but GPS retention is days, so it does not overlap the historical trips already extracted.
2. **Validate the dwell estimate against `FMS_GEOFENCE_VISITS`.** 15,100 measured pit visits, median 14.1 min. The simulator currently apportions dwell for 75% of trips; this is an independent check on that apportionment.
3. **Re-test congestion on `FMS_CONGESTION_SEG`.** The congestion effect was declared unidentifiable from weighbridge data. That table has measured speed *and* `TRUCK_N` per segment-hour — the cleanest possible test of whether more trucks means slower, and it does not depend on deployment being exogenous in the same way. This could overturn the second published negative.
4. **Replace the placeholder `distance_km`** with `DISTANCE_HAULING`.
5. **Consider `HRM_INSPECTION` road condition** as a cycle-time feature.
6. **`FMS_TRUCK_ASSIGNMENTS` gives excavator identity** in weighbridge truck format, contradicting the earlier namespace-split blocker.

Item 3 is the one that could most change the product, and it should be tested the same way as before: measure first, check the sign, and publish whichever answer the data gives.
