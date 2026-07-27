# Database Reconnaissance Report

Read-only schema scan to establish what data exists before choosing what to model next. Sample values from columns that look personal are `[REDACTED]`; column names are kept.

| | |
|---|---|
| Databases | `FMS_DB`, `WBN_DATABASE` |
| Server | Microsoft SQL Server 2019 (RTM) - 15.0.2000.5 (X64) Sep 24 2019 13:48:23 Copyright (C) 2019 Microsoft Corporat |
| Scanned | 2026-07-27T10:44:33+00:00 (56s) |
| Base tables | 214 |
| Total rows | 114,975,710 |
| ⤷ `FMS_DB` | 53 tables, 70,178,747 rows |
| ⤷ `WBN_DATABASE` | 161 tables, 44,796,963 rows |

## Summary of findings

- **214 tables**, 200 populated, 14 empty.
- **Largest table**: `FMS_PLAYBACK_TRACK_DATA` (25,928,155 rows).
- **GPS / positioning** (9): `FMS_GPS_Historical`, `FMS_PLAYBACK_TRACK_24H`, `FMS_PLAYBACK_TRACK_DATA`, `LOCATION_WB_SH`, `RADIO_REPROGRAM_TRACK`, `RSF_PER_LOCATION`, `TOS_DUMP_COORDINATES`, `auto_kmFMS_PLAYBACK_TRACK_DATA`, `auto_spFMS_PLAYBACK_TRACK_DATA`
- **Truck / equipment** (13): `EQUIPMENTS`, `EQUIPMENTS_HOURLY_ACTIVITIES`, `EQUIPMENTS_HOURLY_STATUS`, `EQUIPMENTS_OLD`, `EQUIPMENTS_PLAN`, `EQUIPMENTS_STATUS`, `EQUIPMENTS_WORKS`, `FMS_EQUIPMENTS`, `FMS_TRUCK_ASSIGNMENTS`, `FMS_TRUCK_CYCLES`, `HRM_CONTRACT_EQUIPMENT`, `MINING_FLASH_REPORT_EQUIPMENT`, `MINING_FLASH_REPORT_FLEET_PROD`
- **Plan / production** (45): `DAILY_QUALITY_DISPATCH`, `DAY_WORKS_PLAN_DAILY`, `DISPATCH FeNi PLAN & ACTUAL`, `DISPATCH HAULAGE TF`, `DISPATCH ROADS`, `DISPATCH ROADS OLD`, `DISPATCH WBN ACTUAL`, `DISPATCH WBN PLAN SHIFT`, `DISPATCH_PLAN_WB`, `DISTANCE_HAULING`, `EQUIPMENTS_PLAN`, `FMS_DISPATCH_PLAN`, `FMS_HAUL_CYCLES`, `FMS_QUALITY_DISPATCH` …
- **Operator / crew** (1): `LV_DRIVER_INFO`
- **Weather / environment** (1): `RAINFALL`
- **Road / route** (7): `DISPATCH ROADS`, `DISPATCH ROADS OLD`, `FMS_ROADMAP`, `FMS_ROADMAP_META`, `HAUL_ROAD_STA`, `HRM_MAJOR_ROADWORK`, `TOS_DUMP_COORDINATES`
- **Maintenance / downtime** (0): none
- **Weighbridge** (3): `DISPATCH_PLAN_WB`, `LOCATION_WB_SH`, `TRANSHIPMENT_WBN_ORE`
- **Tables with coordinate columns** (27): `BLASTING_PROD`, `FMS_ENTRY_EXIT_DATA`, `FMS_EQUIPMENTS`, `FMS_GEOFENCES`, `FMS_GEOFENCE_ALERTS`, `FMS_GEOFENCE_ALERT_RULES`, `FMS_GEOFENCE_VISITS`, `FMS_GPS_Historical`, `FMS_HAUL_CYCLES`, `FMS_INTERVENTION_EVENT_DATA`, `FMS_LV_MOVEMENTS`, `FMS_LV_VISIT_VERIFICATIONS`, `FMS_LV_ZONE_VISITS`, `FMS_PLAYBACK_STAY_DATA` …
- **Tables with speed columns** (6): `FMS_GPS_Historical`, `FMS_PLAYBACK_STAY_DATA`, `FMS_PLAYBACK_TRACK_24H`, `FMS_PLAYBACK_TRACK_DATA`, `FMS_SECURITY_INCIDENT_DATA`, `RES_SPEED_LIMIT_ZONES`
- **Updated in the last 30 days** (75): `Calendar_For_Exploitation` (2026-12-28), `POS FOLLOW UP` (2026-07-29), `FMS_APP_STATE` (2026-07-27), `FMS_ASSIGNMENTS` (2026-07-27), `FMS_EQUIPMENTS` (2026-07-27), `FMS_INTERVENTION_EVENT_DATA` (2026-07-27), `FMS_JOB_RUNS` (2026-07-27), `FMS_PLAYBACK_STAY_DATA` (2026-07-27), `FMS_RISK_DATA` (2026-07-27), `FMS_SECURITY_INCIDENT_DATA` (2026-07-27), `FMS_TMS_TOKEN` (2026-07-27), `WT_DAILY_PLAN` (2026-07-27), `ASSAYS` (2026-07-27), `ASSAYS_NITON_GGSHEET` (2026-07-27) …

## What this changes for the next phase

Phase 3 recorded four features as impossible with the available data. The
scan finds three of them sitting in tables the pipeline never joined.

| Phase 3 said | Reality | Where |
|---|---|---|
| Cycle-time components need geofence timestamps | **Available.** Loading and dumping start/end clock times, so load, haul and dump segments are derivable by differencing | `WAITING_TIME` (878,240 rows) |
| Operator experience needs an operator ID we do not have | **Available.** Per-trip driver ID; experience is derivable from first-seen date and accumulated trips | `WAITING_TIME.DRIVER_ID` |
| Truck type needs a truck master table | **Partly available.** `MODEL`, `MANUFACTURER` and `BUILD_YEAR` are populated, so model class and truck age are usable. `CAPACITY` is null for dump trucks | `EQUIPMENTS` (7,221 rows) |
| Road grade needs a survey or DEM | **Derivable, with work.** No elevation column, but GPS tracks give lat/lon per truck; grade needs an external DEM joined on position | `FMS_PLAYBACK_TRACK_DATA` (25,928,155 rows) |

### Truck GPS: it exists, in `FMS_DB`

The telemetry is in a **separate database** from the production records the
simulator currently reads. `WBN_DATABASE` holds haulage and weighbridge data;
`FMS_DB` holds the fleet-management telemetry, and nothing in the pipeline
touches it today.

| Table | Rows | What it gives you |
|---|---:|---|
| `FMS_PLAYBACK_TRACK_DATA` | 25,928,155 | Raw GPS: `lat`, `lng`, `speed`, `course`, `distance`, `engine`, `acc`, per `plateNumber` |
| `FMS_ENTRY_EXIT_DATA` | 10,735,620 | Gate/zone entry and exit events |
| `FMS_GPS_Historical` | 521,918 | Same shape, keyed by `TRUCK_ID` — the join back to haulage records |
| `FMS_GEOFENCE_VISITS` | 35,640 | **Geofence enter/exit with `DURATION_SEC`** — cycle segments without differencing raw fixes |
| `FMS_CONGESTION_SEG` | 23,999 | Pre-aggregated hourly congestion: mean speed, truck count and travel time per road segment |
| `FMS_GEOFENCES` | 3,490 | Geofence definitions — the named zones the visits refer to |

`FMS_CONGESTION_SEG` deserves particular attention: Phase 3's congestion
proxy was `trucks_per_path`, a count that came out with a *positive*
coefficient because busy roads are busy for good reasons. This table has
measured speed per segment per hour, which is congestion itself rather than a
stand-in for it.

## Table inventory

Sorted by row count. `Flags` are keyword matches on the table name; `col:` flags come from column names.

| Table | Cols | Rows | Date range | Flags |
|---|---:|---:|---|---|
| `FMS_DB`.`FMS_PLAYBACK_TRACK_DATA` | 18 | 25,928,155 | dates, range skipped | GPS, col:COORD, col:SPEED, col:TIME |
| `FMS_DB`.`auto_kmFMS_PLAYBACK_TRACK_DATA` | 4 | 18,919,704 | — | GPS, col:TIME |
| `WBN_DATABASE`.`EQUIPMENTS_HOURLY_STATUS` | 20 | 16,515,745 | dates, range skipped | TRUCK, col:STATUS, col:TIME |
| `FMS_DB`.`FMS_ENTRY_EXIT_DATA` | 12 | 10,735,620 | dates, range skipped | col:COORD, col:EQUIP, col:TIME |
| `FMS_DB`.`FMS_SECURITY_INCIDENT_DATA` | 36 | 5,268,787 | 2026-03-19 → 2026-07-27 | col:COORD, col:EQUIP, col:SPEED, col:TIME |
| `WBN_DATABASE`.`EQUIPMENTS_HOURLY_ACTIVITIES` | 21 | 4,675,157 | 1899-12-30 → 2026-07-26 | TRUCK, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`BLOCK_INDESIGN` | 13 | 4,288,722 | 2025-06-12 → 2026-05-10 | col:TIME |
| `FMS_DB`.`autoFMS_SECURITY_INCIDENT_KILOMETER` | 4 | 4,092,100 | — | — |
| `WBN_DATABASE`.`EQUIPMENTS_STATUS` | 22 | 3,670,386 | 2024-10-01 → 2026-07-26 | TRUCK, col:STATUS, col:TIME |
| `WBN_DATABASE`.`HAULAGE` | 24 | 3,508,949 | 2021-09-24 → 2026-07-26 | PLAN, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`S123_STOCK_SHAPE_OLD` | 12 | 1,732,432 | 2026-03-17 → 2026-06-27 | col:TIME |
| `FMS_DB`.`auto_spFMS_PLAYBACK_TRACK_DATA` | 5 | 1,554,167 | — | GPS, col:COORD, col:TIME |
| `WBN_DATABASE`.`HAULAGE_IWIP_EXT` | 28 | 1,508,871 | 2026-05-30 → 2026-07-11 | PLAN, col:EQUIP, col:STATUS, col:TIME |
| `FMS_DB`.`FMS_INTERVENTION_EVENT_DATA` | 32 | 1,243,050 | 2026-04-07 → 2026-07-27 | col:COORD, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`RSF_HAULING_DATA` | 18 | 1,143,509 | 2023-12-23 → 2026-01-22 | PLAN, col:TIME |
| `FMS_DB`.`FMS_PLAYBACK_TRACK_24H` | 14 | 1,140,456 | — | GPS, col:COORD, col:EQUIP, col:SPEED, col:TIME |
| `WBN_DATABASE`.`WAITING_TIME` | 24 | 878,240 | 2025-01-01 → 2026-07-22 | col:EQUIP, col:TIME |
| `WBN_DATABASE`.`HAULAGE_IWIP` | 35 | 572,742 | 2025-12-27 → 2026-07-08 | PLAN, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`TOS_STATUS` | 6 | 548,245 | 2024-09-30 → 2026-07-26 | col:STATUS, col:TIME |
| `FMS_DB`.`FMS_GPS_Historical` | 15 | 521,918 | — | GPS, col:COORD, col:EQUIP, col:SPEED, col:TIME |
| `WBN_DATABASE`.`DAY_WORKS` | 27 | 495,384 | 2024-10-15 → 2026-07-23 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`PRODUCTION_ACTIVITY_PIT` | 34 | 449,992 | 2024-07-01 → 2026-07-26 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`PRODUCTION_PIT_OLD` | 23 | 407,593 | 2024-07-01 → 2026-06-07 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`ASSAYS` | 36 | 396,422 | 1900-01-01 → 2026-07-27 | col:STATUS, col:TIME |
| `FMS_DB`.`FMS_PLAYBACK_STAY_DATA` | 43 | 380,922 | 2026-03-22 → 2026-07-27 | col:COORD, col:EQUIP, col:SPEED, col:TIME |
| `WBN_DATABASE`.`PP_MINED_NEW_RECONCIL_MENG` | 11 | 308,042 | — | — |
| `FMS_DB`.`FMS_RISK_DATA` | 19 | 306,611 | 2026-04-06 → 2026-07-27 | col:COORD, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`SAMPLE` | 26 | 249,620 | 1900-01-02 → 2026-07-20 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`auto_edge_HAULAGE` | 11 | 246,972 | 2021-09-24 → 2026-07-26 | PLAN, col:TIME |
| `WBN_DATABASE`.`DISPATCH WBN ACTUAL` | 14 | 212,890 | 2024-10-01 → 2026-07-22 | PLAN, col:TIME |
| `WBN_DATABASE`.`auto_node_STOCK_ID` | 29 | 186,833 | 2021-02-20 → 2026-07-27 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`POS FOLLOW UP` | 9 | 177,581 | 2024-10-01 → 2026-07-29 | col:TIME |
| `WBN_DATABASE`.`autoQC_CF_BM_TOS_HISTORY_OLD` | 17 | 175,475 | — | col:TIME |
| `WBN_DATABASE`.`CRUSHER_STOCKPILE_OUTPUT_DATA` | 13 | 156,726 | 2024-10-01 → 2026-06-04 | col:EQUIP, col:TIME |
| `WBN_DATABASE`.`QC PIT-TOS OMR` | 19 | 149,360 | 2024-10-01 → 2026-07-17 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`autoBLOCK_PROD_QC_BM_TOS_CORR` | 18 | 131,692 | 2025-12-29 → 2026-07-26 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`CONTRACTOR FOLLOW UP` | 25 | 130,557 | 2024-10-01 → 2026-07-26 | col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`FeNi Reclaiming Plan` | 10 | 127,339 | 2024-10-01 → 2026-07-27 | PLAN, col:TIME |
| `WBN_DATABASE`.`MINING_PLAN_WEEKLY` | 34 | 124,358 | 2025-02-08 → 2026-05-01 | PLAN, col:TIME |
| `WBN_DATABASE`.`SAMPLING_CONTRACTOR` | 15 | 123,130 | 2024-10-01 → 2026-07-25 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`TOS_PILE_INFO` | 6 | 97,738 | — | — |
| `WBN_DATABASE`.`autoQC_STOCK_ALL_VIA_ALL` | 93 | 93,116 | 2021-10-17 → 2026-07-21 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`TOS FOLLOW` | 13 | 87,045 | 2024-10-01 → 2026-07-22 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`OMR_QC` | 15 | 85,995 | 2024-10-01 → 2026-07-22 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`DISPATCH FeNi PLAN & ACTUAL` | 11 | 84,040 | 2024-10-01 → 2026-07-27 | PLAN, col:TIME |
| `WBN_DATABASE`.`DISTANCE_MINING` | 14 | 83,462 | 2024-02-25 → 2025-09-27 | col:TIME |
| `WBN_DATABASE`.`DAILY_QUALITY_DISPATCH` | 19 | 66,774 | 2025-02-27 → 2026-07-22 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`PILES_SHARED_FENI` | 7 | 66,571 | 2024-11-19 → 2026-05-29 | col:TIME |
| `WBN_DATABASE`.`EXC_TRIMMING` | 9 | 59,362 | 2024-11-13 → 2026-07-11 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`RAINFALL` | 9 | 55,934 | 2002-01-01 → 2026-04-11 | WEATHER, col:TIME |
| `WBN_DATABASE`.`SURVEY POS` | 19 | 50,160 | 2024-10-05 → 2026-07-18 | col:TIME |
| `WBN_DATABASE`.`autoTOS_SURVEY_ESTIMATION` | 19 | 44,438 | 2026-04-29 → 2026-07-27 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`HAULAGE_M_DOME_2026_IWIP_PLAN` | 15 | 44,289 | 2026-03-05 → 2026-04-06 | PLAN, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`QC_TOS_DATA_ML` | 33 | 38,001 | — | col:TIME |
| `WBN_DATABASE`.`PP_REMAIN_INPIT_MINEOUT` | 13 | 36,206 | — | col:TIME |
| `WBN_DATABASE`.`PP_MINED_YTD_OK` | 12 | 35,922 | — | — |
| `FMS_DB`.`FMS_GEOFENCE_VISITS` | 17 | 35,640 | — | col:COORD, col:STATUS |
| `WBN_DATABASE`.`TSS` | 19 | 35,218 | 2024-10-01 → 2026-04-11 | col:TIME |
| `WBN_DATABASE`.`HRM_INSPECTION` | 14 | 30,610 | 2024-10-01 → 2025-12-11 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`DISTANCE_HAULING` | 12 | 30,587 | 2025-04-28 → 2025-09-27 | PLAN, col:TIME |
| `WBN_DATABASE`.`CRUSHER LOIPOLOY` | 17 | 27,334 | 2024-10-01 → 2026-07-26 | col:EQUIP, col:TIME |
| `WBN_DATABASE`.`DISPATCH WBN PLAN SHIFT` | 15 | 27,058 | 2024-10-01 → 2026-07-22 | PLAN, col:TIME |
| `WBN_DATABASE`.`QC SAMPLE DATA` | 15 | 25,425 | 2024-01-12 → 2025-02-17 | col:TIME |
| `FMS_DB`.`FMS_CONGESTION_SEG` | 9 | 23,999 | — | col:EQUIP, col:TIME |
| `WBN_DATABASE`.`VERY VERY SHORT TERM PIT SERVICE` | 16 | 21,059 | 2024-10-01 → 2026-07-26 | col:TIME |
| `WBN_DATABASE`.`ASSAYS_NITON_GGSHEET` | 25 | 19,700 | 2026-01-28 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`PRODUCTION_PIT_PRELIM_auto` | 19 | 15,887 | 2025-11-17 → 2026-03-23 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`STOCK_STATUS` | 12 | 14,720 | 1900-01-01 → 2026-07-15 | col:TIME |
| `WBN_DATABASE`.`blasting_drilling` | 22 | 14,648 | 2024-11-25 → 2026-03-19 | col:TIME |
| `WBN_DATABASE`.`OLD_VERY_SHORT_TERM` | 16 | 13,470 | 2024-10-05 → 2025-11-27 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`HAULAGE_REPORT` | 16 | 13,459 | 2024-10-05 → 2025-11-26 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`WBN_DATABASE_ST_LOG_ON` | 3 | 13,081 | 2026-06-18 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`QUARRY PRODUCTION` | 14 | 12,646 | 2024-10-01 → 2025-09-10 | PLAN, col:TIME |
| `WBN_DATABASE`.`PROD VERY VERY SHORT TERM` | 29 | 11,163 | 2024-10-01 → 2026-07-26 | col:TIME |
| `WBN_DATABASE`.`RSF_SURVEY` | 20 | 9,103 | 2024-10-04 → 2025-06-20 | col:COORD, col:STATUS, col:TIME |
| `FMS_DB`.`RES_EMPLOYEES` | 9 | 8,958 | — | — |
| `WBN_DATABASE`.`autoQC_CF_BM_TOS` | 20 | 8,234 | 2026-07-06 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`RECLASSIFICATION` | 5 | 7,789 | 1899-12-30 → 2026-07-23 | — |
| `WBN_DATABASE`.`EQUIPMENTS` | 15 | 7,221 | — | TRUCK |
| `WBN_DATABASE`.`FENI_REQUESTS` | 7 | 7,196 | 2025-07-01 → 2026-05-29 | col:TIME |
| `WBN_DATABASE`.`QS_LIMS_RIM_CK` | 19 | 6,131 | 2026-06-10 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`DARONNE_Htemp` | 19 | 5,812 | 2026-05-01 → 2026-06-30 | col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`EQUIPMENTS_OLD` | 14 | 5,658 | — | TRUCK |
| `WBN_DATABASE`.`WMT_FOR_3RD_PARTY` | 12 | 5,529 | 2023-12-13 → 2026-07-20 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`BATCH` | 3 | 4,931 | — | — |
| `WBN_DATABASE`.`DRAFTS` | 30 | 4,848 | 2023-10-03 → 2026-07-07 | col:EQUIP, col:TIME |
| `WBN_DATABASE`.`TOS_SURVEY` | 18 | 4,804 | 2026-03-28 → 2026-07-10 | col:TIME |
| `WBN_DATABASE`.`S123_STOCK_SHAPE` | 11 | 4,785 | 2026-07-27 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`STOCK_STATUS_HAULAGE_GGSHEET` | 17 | 4,750 | 2026-07-18 → 2026-07-18 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`STOCK_REQUESTS` | 9 | 4,735 | 2025-06-20 → 2025-08-03 | col:TIME |
| `WBN_DATABASE`.`3RD_PARTY_ACTIVITIES_RECLAIM` | 16 | 4,138 | 2024-12-22 → 2026-07-26 | col:TIME |
| `WBN_DATABASE`.`REQUEST` | 6 | 3,920 | 2021-01-01 → 2026-07-01 | col:TIME |
| `WBN_DATABASE`.`ORE STOCK SALES` | 21 | 3,800 | 2021-02-20 → 2025-06-20 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`S123_TOS_STATUS` | 11 | 3,589 | 2026-07-27 → 2026-07-27 | col:STATUS, col:TIME |
| `FMS_DB`.`FMS_GEOFENCES` | 17 | 3,490 | — | col:COORD, col:STATUS, col:TIME |
| `FMS_DB`.`RADIO_REPROGRAM_TRACK` | 21 | 3,478 | — | GPS, col:EQUIP, col:STATUS, col:TIME |
| `FMS_DB`.`FMS_TOS_STATUS` | 14 | 3,404 | dates, range skipped | col:STATUS, col:TIME |
| `WBN_DATABASE`.`CRUSHER_BLENDING_DATA` | 11 | 3,332 | 2024-10-01 → 2025-05-25 | col:TIME |
| `WBN_DATABASE`.`3RD_PARTY_ACTIVITIES` | 15 | 3,312 | 2024-10-01 → 2026-07-26 | col:TIME |
| `WBN_DATABASE`.`HAUL_ROAD_STA` | 11 | 3,122 | — | PLAN, ROAD |
| `FMS_DB`.`FMS_TMS_TOKEN` | 3 | 2,872 | 2026-03-02 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`Calendar_For_Exploitation` | 7 | 2,665 | 2019-09-12 → 2026-12-28 | col:TIME |
| `WBN_DATABASE`.`S123_ENVIRO_TSS` | 33 | 2,366 | 2026-06-08 → 2026-06-25 | col:COORD, col:TIME |
| `WBN_DATABASE`.`MINING_PLAN_3MRMP` | 45 | 2,295 | 2026-03-29 → 2026-05-14 | PLAN, col:TIME |
| `WBN_DATABASE`.`blasting_parameters` | 20 | 2,081 | 2023-02-01 → 2025-05-04 | col:TIME |
| `WBN_DATABASE`.`EQUIPMENTS_PLAN` | 12 | 2,071 | 2025-12-29 → 2026-05-14 | PLAN, TRUCK, col:STATUS, col:TIME |
| `WBN_DATABASE`.`Calendar_Svy_topo_by_deposit` | 5 | 1,815 | 2024-12-28 → 2026-07-20 | col:TIME |
| `WBN_DATABASE`.`DAY_WORKS_PLAN_DAILY` | 17 | 1,611 | 2026-06-28 → 2026-07-27 | PLAN, col:EQUIP, col:STATUS, col:TIME |
| `WBN_DATABASE`.`ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE` | 7 | 1,585 | 2021-01-01 → 2025-06-01 | col:TIME |
| `WBN_DATABASE`.`RSF_PER_LOCATION` | 15 | 1,489 | 2024-10-01 → 2024-12-16 | GPS, col:STATUS, col:TIME |
| `WBN_DATABASE`.`CLASS2025` | 7 | 1,438 | 2024-12-29 → 2025-07-12 | col:TIME |
| `FMS_DB`.`FMS_EQUIPMENTS` | 7 | 1,401 | 2026-03-22 → 2026-07-27 | TRUCK, col:COORD, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`CONSOLIDATED SURVEY` | 15 | 1,188 | — | — |
| `FMS_DB`.`WT_DAILY_PLAN` | 10 | 1,187 | 2026-04-16 → 2026-07-27 | PLAN, col:EQUIP, col:TIME |
| `FMS_DB`.`FMS_UNIT_INSTALLED` | 4 | 1,182 | — | col:COORD |
| `WBN_DATABASE`.`WATER_MANAGEMENT` | 12 | 1,074 | 2025-06-24 → 2025-10-07 | col:TIME |
| `WBN_DATABASE`.`OLD_prod_correction_factor_ACCESS` | 6 | 957 | — | — |
| `WBN_DATABASE`.`QUARRY_PLAN` | 11 | 935 | 2026-06-01 → 2026-07-27 | PLAN, col:TIME |
| `WBN_DATABASE`.`ROLLING_MINE_PLAN` | 20 | 834 | dates, range skipped | PLAN, col:TIME |
| `WBN_DATABASE`.`IWIP_REQUESTS_DATE` | 3 | 772 | 2025-06-01 → 2026-05-02 | col:TIME |
| `WBN_DATABASE`.`TRANSHIPMENT_WBN_ORE` | 7 | 573 | 2023-04-11 → 2026-07-19 | WEIGHBRIDGE, col:TIME |
| `WBN_DATABASE`.`ID_DT_HUAFEI` | 1 | 485 | — | — |
| `WBN_DATABASE`.`SUMMARY_SURVEY` | 12 | 460 | — | — |
| `WBN_DATABASE`.`BLASTING_PROD` | 12 | 433 | 2026-01-02 → 2026-05-27 | col:COORD, col:TIME |
| `WBN_DATABASE`.`DISPATCH_PLAN_WB` | 15 | 432 | 2026-01-07 → 2026-07-22 | PLAN, WEIGHBRIDGE, col:TIME |
| `FMS_DB`.`FMS_TRUCK_ASSIGNMENTS` | 10 | 408 | 2026-01-07 → 2026-07-22 | TRUCK, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`COLOR_CHEMICAL` | 4 | 404 | — | — |
| `WBN_DATABASE`.`WBN_DATABASE_ESSENTIALS` | 3 | 334 | — | — |
| `FMS_DB`.`FMS_HAUL_CYCLES` | 10 | 287 | 2026-06-26 → 2026-07-24 | PLAN, col:COORD, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`autoQC_PLAN_NI_CF_OLD` | 21 | 264 | — | PLAN, col:TIME |
| `WBN_DATABASE`.`DISPATCH HAULAGE TF` | 5 | 264 | — | PLAN |
| `FMS_DB`.`FMS_QUALITY_DISPATCH` | 21 | 258 | 2026-06-23 → 2026-07-22 | PLAN, col:STATUS, col:TIME |
| `WBN_DATABASE`.`DISPATCH ROADS OLD` | 36 | 254 | — | PLAN, ROAD |
| `WBN_DATABASE`.`autoHAULAGE_VS_PROD_MONTHLY_CF` | 6 | 223 | 2026-07-27 → 2026-07-27 | PLAN, col:TIME |
| `WBN_DATABASE`.`DISPATCH ROADS` | 33 | 222 | — | PLAN, ROAD |
| `WBN_DATABASE`.`HRM_CONTRACT_EQUIPMENT` | 8 | 198 | — | TRUCK |
| `WBN_DATABASE`.`PROJECTS_SUPERVISION` | 23 | 198 | 2025-08-21 → 2025-11-24 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`MBAR` | 12 | 173 | 2025-01-06 → 2025-09-30 | — |
| `WBN_DATABASE`.`HRM_MAJOR_ROADWORK` | 11 | 149 | 2024-10-15 → 2024-11-03 | ROAD, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`LME` | 4 | 142 | 2026-01-02 → 2026-07-24 | col:TIME |
| `WBN_DATABASE`.`LME_GOLD` | 2 | 140 | 2026-01-02 → 2026-07-24 | col:TIME |
| `WBN_DATABASE`.`TSS_POINT` | 36 | 121 | — | col:COORD, col:STATUS |
| `WBN_DATABASE`.`TOS_DUMP_COORDINATES` | 7 | 118 | — | GPS, ROAD |
| `WBN_DATABASE`.`TSS_CROSSTABLE` | 5 | 109 | — | — |
| `WBN_DATABASE`.`MINING_FLASH_REPORT_FLEET_PROD` | 8 | 108 | 2025-11-28 → 2025-11-30 | TRUCK, col:TIME |
| `FMS_DB`.`FMS_DISPATCH_PLAN` | 16 | 105 | 2026-06-23 → 2026-07-22 | PLAN, col:TIME |
| `WBN_DATABASE`.`MINING_FLASH_REPORT_EQUIPMENT` | 9 | 102 | 2025-11-28 → 2025-11-30 | TRUCK, col:STATUS, col:TIME |
| `WBN_DATABASE`.`BLASTING_REMAINING` | 7 | 98 | 2026-05-27 → 2026-05-27 | col:TIME |
| `FMS_DB`.`SHP_SED_POND` | 4 | 91 | — | col:COORD |
| `WBN_DATABASE`.`CONTRACTOR_DEPOSIT` | 4 | 84 | — | — |
| `WBN_DATABASE`.`EQUIPMENTS_WORKS` | 14 | 82 | 2024-09-06 → 2024-10-14 | TRUCK, col:TIME |
| `FMS_DB`.`SAFETY_DPLAN` | 9 | 80 | 2026-05-05 → 2026-06-11 | PLAN, col:TIME |
| `WBN_DATABASE`.`WBN_DATABASE_PROCEDURE_QUEUE` | 3 | 79 | 2025-05-12 → 2025-06-20 | col:STATUS |
| `WBN_DATABASE`.`TEAM_PLAN` | 8 | 78 | 2024-12-29 → 2025-02-14 | PLAN, col:TIME |
| `WBN_DATABASE`.`COMPANIES` | 7 | 73 | — | — |
| `FMS_DB`.`LV_PLAN` | 7 | 62 | 2026-05-11 → 2026-05-13 | PLAN, col:EQUIP, col:TIME |
| `WBN_DATABASE`.`DARONNEtemp` | 3 | 61 | 2026-05-01 → 2026-06-30 | col:TIME |
| `FMS_DB`.`LV_INFO` | 6 | 57 | — | col:EQUIP |
| `WBN_DATABASE`.`Ni_COLOR` | 3 | 45 | — | — |
| `WBN_DATABASE`.`MINING_FLASH_REPORT_PRODUCTION` | 8 | 42 | 2025-11-28 → 2025-11-30 | PLAN, col:TIME |
| `WBN_DATABASE`.`ACTIVITIES_MAT` | 4 | 39 | — | col:STATUS |
| `WBN_DATABASE`.`LOCATION_WB_SH` | 6 | 39 | — | GPS, WEIGHBRIDGE |
| `WBN_DATABASE`.`DT_DENSITY_HR_MODEL$` | 15 | 37 | 2025-09-13 → 2025-09-13 | col:TIME |
| `FMS_DB`.`FMS_ROADMAP` | 21 | 36 | — | ROAD, col:STATUS, col:TIME |
| `WBN_DATABASE`.`TEAM` | 5 | 34 | — | — |
| `FMS_DB`.`FMS_LOGIN_IPS` | 5 | 32 | — | col:TIME |
| `FMS_DB`.`FMS_GEOFENCE_ALERTS` | 29 | 31 | — | col:COORD, col:STATUS |
| `FMS_DB`.`FMS_USERS` | 8 | 30 | — | col:TIME |
| `WBN_DATABASE`.`MINING_EQ_TARGET_3MRMP` | 5 | 30 | — | — |
| `FMS_DB`.`FMS_LV_ZONE_VISITS` | 13 | 27 | — | col:COORD, col:STATUS |
| `FMS_DB`.`RES_SPEED_LIMIT_ZONES` | 16 | 27 | — | col:COORD, col:SPEED |
| `WBN_DATABASE`.`ALL_HR_KM_SECTIONS` | 8 | 27 | — | — |
| `WBN_DATABASE`.`ASSAY_CLASS` | 8 | 27 | 2020-01-01 → 2025-01-01 | col:TIME |
| `WBN_DATABASE`.`SHAPE_STOCK_AREA` | 5 | 26 | — | — |
| `WBN_DATABASE`.`HRM_REQUEST_MATERIAL` | 10 | 25 | 2024-11-08 → 2024-11-09 | col:TIME |
| `WBN_DATABASE`.`TEAM_FB` | 6 | 25 | 2025-08-07 → 2026-05-01 | col:TIME |
| `FMS_DB`.`FMS_APP_STATE` | 3 | 23 | 2026-07-11 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`POS POSSIBILITY For HAULAGE` | 3 | 23 | — | PLAN |
| `WBN_DATABASE`.`REQUEST_SALES_LATE_2025` | 3 | 18 | 2025-11-01 → 2025-11-01 | col:TIME |
| `FMS_DB`.`FMS_USER_ACTIVITY` | 3 | 17 | — | — |
| `FMS_DB`.`FMS_ASSIGNMENTS` | 5 | 16 | 2026-07-05 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`BLOCK_ID_XYPARAM` | 8 | 16 | — | — |
| `WBN_DATABASE`.`CRUSHER_SURVEY_LOYPOLOY` | 13 | 16 | 2024-10-13 → 2024-10-13 | col:TIME |
| `FMS_DB`.`FMS_MESSAGES` | 15 | 14 | — | col:TIME |
| `FMS_DB`.`RES_WATER_FILLING_POINTS` | 9 | 14 | — | col:COORD, col:STATUS |
| `WBN_DATABASE`.`ACTIVITIES` | 3 | 13 | — | col:STATUS |
| `FMS_DB`.`FMS_JOB_RUNS` | 5 | 12 | 2026-07-16 → 2026-07-27 | col:TIME |
| `WBN_DATABASE`.`HAULAGE CONTRACTORS` | 2 | 11 | — | PLAN |
| `WBN_DATABASE`.`SUPERVISION_SAFETY_ACTIONS` | 23 | 6 | 2025-09-10 → 2025-09-30 | col:STATUS, col:TIME |
| `FMS_DB`.`FMS_SETTINGS` | 3 | 5 | — | col:TIME |
| `FMS_DB`.`RES_CRITICAL_ZONES` | 5 | 4 | — | — |
| `FMS_DB`.`FMS_LV_DAILY_REPORTS` | 12 | 3 | 2026-07-24 → 2026-07-26 | col:STATUS, col:TIME |
| `WBN_DATABASE`.`CRUSHER_CF` | 3 | 3 | — | — |
| `WBN_DATABASE`.`HAULAGE_ADJ` | 8 | 3 | 2025-02-01 → 2025-02-01 | PLAN, col:TIME |
| `FMS_DB`.`FMS_INSTANCES` | 7 | 2 | — | col:TIME |
| `FMS_DB`.`FMS_DOCS` | 4 | 1 | — | col:TIME |
| `FMS_DB`.`FMS_GEOFENCE_ALERT_RULES` | 17 | 1 | — | col:COORD |
| `FMS_DB`.`FMS_LV_VISIT_VERIFICATIONS` | 13 | 1 | — | col:COORD, col:TIME |
| `FMS_DB`.`FMS_ROADMAP_META` | 2 | 1 | — | ROAD |
| `FMS_DB`.`FMS_TRUCK_CYCLES` | 16 | 1 | 2026-07-25 → 2026-07-25 | TRUCK, col:COORD, col:STATUS, col:TIME |
| `FMS_DB`.`FMS_ERROR_FLOW` | 8 | 0 | dates, range skipped | col:STATUS, col:TIME |
| `FMS_DB`.`FMS_LV_MOVEMENTS` | 15 | 0 | — | col:COORD, col:STATUS |
| `FMS_DB`.`LV_DRIVER_INFO` | 6 | 0 | — | OPERATOR, col:EQUIP |
| `WBN_DATABASE`.`autoQC_CF_BM_PROP` | 17 | 0 | dates, range skipped | col:TIME |
| `WBN_DATABASE`.`blasting_production` | 19 | 0 | dates, range skipped | PLAN, col:TIME |
| `WBN_DATABASE`.`CORRECTIVE_ACTIONS` | 12 | 0 | dates, range skipped | col:STATUS, col:TIME |
| `WBN_DATABASE`.`DAYWORK_REQUEST` | 11 | 0 | dates, range skipped | col:TIME |
| `WBN_DATABASE`.`FMS_TOS_STATUS` | 11 | 0 | dates, range skipped | col:STATUS, col:TIME |
| `WBN_DATABASE`.`PRODUCTION_PIT_MINING_DISTANCE` | 14 | 0 | dates, range skipped | PLAN, col:TIME |
| `WBN_DATABASE`.`START LIM STOCK` | 16 | 0 | dates, range skipped | col:TIME |
| `WBN_DATABASE`.`TEAM_PROFILE` | 12 | 0 | dates, range skipped | col:TIME |
| `WBN_DATABASE`.`tempHAULAGE_IWIP` | 1 | 0 | — | PLAN |
| `WBN_DATABASE`.`TOS` | 11 | 0 | dates, range skipped | col:STATUS, col:TIME |
| `WBN_DATABASE`.`WBN_DATABASE_ERROR_PROCEDURE` | 8 | 0 | dates, range skipped | col:STATUS, col:TIME |

## Detailed table profiles

Empty tables are listed in the inventory above but not profiled here.

### `FMS_DB`.`FMS_PLAYBACK_TRACK_DATA`

- **Rows**: 25,928,155
- **Flags**: GPS, col:COORD, col:SPEED, col:TIME
- **Date columns**: `FETCH_DATE`
- *date range skipped (table > 10,000,000 rows)*
- *table too large, sample skipped*

<details><summary>18 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `plateNumber` | nvarchar(50) | yes |
| 3 | `acc` | float | yes |
| 4 | `deviceType` | nvarchar(255) | yes |
| 5 | `distance` | float | yes |
| 6 | `lng` | float | yes |
| 7 | `driving_time` | float | yes |
| 8 | `dump_energy` | nvarchar(255) | yes |
| 9 | `receive_time` | float | yes |
| 10 | `loc_type` | float | yes |
| 11 | `speed` | float | yes |
| 12 | `engine` | float | yes |
| 13 | `oils` | float | yes |
| 14 | `course` | float | yes |
| 15 | `imei` 🔒 | bigint | no |
| 16 | `time` | bigint | no |
| 17 | `interpolation_flag` | float | yes |
| 18 | `lat` | float | yes |

</details>

### `FMS_DB`.`auto_kmFMS_PLAYBACK_TRACK_DATA`

- **Rows**: 18,919,704
- **Flags**: GPS, col:TIME
- *table too large, sample skipped*

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `imei` 🔒 | bigint | no |
| 2 | `time` | bigint | no |
| 3 | `DIRECTION` | nvarchar(50) | yes |
| 4 | `SectionKM` | float | yes |

</details>

### `WBN_DATABASE`.`EQUIPMENTS_HOURLY_STATUS`

- **Rows**: 16,515,745
- **Flags**: TRUCK, col:STATUS, col:TIME
- **Date columns**: `DATE`
- *date range skipped (table > 10,000,000 rows)*
- *table too large, sample skipped*

<details><summary>20 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `START_HOUR` | float | yes |
| 6 | `END_HOUR` | float | yes |
| 7 | `ID_EQ` | nvarchar(50) | yes |
| 8 | `ACTIVITY` | nvarchar(50) | yes |
| 9 | `LOCATION` | nvarchar(50) | yes |
| 10 | `WORKING_HOURS` | float | yes |
| 11 | `STBY_HOURS` | float | yes |
| 12 | `STBY_CODE` | nvarchar(50) | yes |
| 13 | `BD_HOURS` | float | yes |
| 14 | `BD_CODE` | nvarchar(50) | yes |
| 15 | `PM_HOURS` | float | yes |
| 16 | `PM_CODE` | nvarchar(50) | yes |
| 17 | `OPERATING_HOURS` | float | yes |
| 18 | `REMARK` | nvarchar(50) | yes |
| 19 | `STATUS` | nvarchar(50) | yes |
| 20 | `LOCATION_DETAILS` | nvarchar(50) | yes |

</details>

### `FMS_DB`.`FMS_ENTRY_EXIT_DATA`

- **Rows**: 10,735,620
- **Flags**: col:COORD, col:EQUIP, col:TIME
- **Date columns**: `FETCH_DATE`
- *date range skipped (table > 10,000,000 rows)*
- *table too large, sample skipped*

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `plateNumber` | nvarchar(255) | yes |
| 3 | `startTime` | bigint | no |
| 4 | `endTime` | bigint | yes |
| 5 | `truckId` | bigint | no |
| 6 | `pointId` | int | no |
| 7 | `orgName` 🔒 | nvarchar(255) | yes |
| 8 | `orgId` | bigint | yes |
| 9 | `poiTypeName` 🔒 | nvarchar(255) | yes |
| 10 | `pointName` 🔒 | nvarchar(255) | yes |
| 11 | `stayTime` | float | yes |
| 12 | `hasVideoAbility` | nvarchar(50) | no |

</details>

### `FMS_DB`.`FMS_SECURITY_INCIDENT_DATA`

- **Rows**: 5,268,787
- **Flags**: col:COORD, col:EQUIP, col:SPEED, col:TIME
- **Date column**: `FETCH_DATE` — 2026-03-19 09:10:31 to 2026-07-27 18:29:28
- *redacted columns: checkDriverName, carrierName, areaName, driverNo, address, orgName, startAddress, driverId, classTypeName, eventTypeName, imei, driverName, endAddress*

<details><summary>36 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `id` | nvarchar(100) | no |
| 3 | `orgId` | bigint | yes |
| 4 | `speed` | float | yes |
| 5 | `checkDriverName` 🔒 | nvarchar(255) | yes |
| 6 | `endLat` | float | yes |
| 7 | `carrierName` 🔒 | nvarchar(255) | yes |
| 8 | `areaName` 🔒 | nvarchar(255) | yes |
| 9 | `endPrecision` | float | yes |
| 10 | `difftime` | float | yes |
| 11 | `startTime` | bigint | yes |
| 12 | `endLng` | float | yes |
| 13 | `driverNo` 🔒 | nvarchar(255) | yes |
| 14 | `lat` | float | yes |
| 15 | `limitSpeed` | nvarchar(255) | yes |
| 16 | `mileage` | float | yes |
| 17 | `truckId` | nvarchar(255) | yes |
| 18 | `address` 🔒 | nvarchar(255) | yes |
| 19 | `orgName` 🔒 | nvarchar(255) | yes |
| 20 | `lng` | float | yes |
| 21 | `startAddress` 🔒 | nvarchar(255) | yes |
| 22 | `updateTime` | bigint | yes |
| 23 | `eventType` | nvarchar(255) | yes |
| 24 | `maxSpeed` | float | yes |
| 25 | `plateNumber` | nvarchar(255) | yes |
| 26 | `markerType` | nvarchar(255) | yes |
| 27 | `driverId` 🔒 | float | yes |
| 28 | `classTypeName` 🔒 | nvarchar(255) | yes |
| 29 | `createTime` | bigint | yes |
| 30 | `speedPercent` | nvarchar(255) | yes |
| 31 | `eventTypeName` 🔒 | nvarchar(255) | yes |
| 32 | `imei` 🔒 | nvarchar(255) | yes |
| 33 | `driverName` 🔒 | nvarchar(255) | yes |
| 34 | `endTime` | bigint | yes |
| 35 | `markerRemark` | nvarchar(255) | yes |
| 36 | `endAddress` 🔒 | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | id | orgId | speed | checkDriverName | endLat | carrierName | areaName | endPrecision | difftime | startTime | endLng |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03-21 08:30:30.750000 | 107015291859043_10004_1772110463000 | 7190742966074476803 | 0.0 |  | 0.778727 | [REDACTED] |  | -1.0 | 2.0 | 1772110463000 | 128.037388 |
| 2026-03-21 08:31:37.047000 | 107015291859043_10004_1772112773000 | 7190742966074476803 | 0.0 |  | 0.717699 | [REDACTED] |  | -1.0 | 2.0 | 1772112773000 | 128.019495 |
| 2026-03-21 08:31:54.313000 | 107015291859043_10004_1772113778000 | 7190742966074476803 | 0.0 |  | 0.693851 | [REDACTED] |  | -1.0 | 14.0 | 1772113778000 | 127.980064 |
| 2026-03-21 08:38:53.420000 | 107015291859043_10004_1772130260000 | 7190742966074476803 | 0.0 |  | 0.701852 | [REDACTED] |  | -1.0 | 29.0 | 1772130260000 | 127.994408 |
| 2026-03-21 08:39:11.760000 | 107015291859043_10004_1772131172000 | 7190742966074476803 | 0.0 |  | 0.738165 | [REDACTED] |  | -1.0 | 2.0 | 1772131172000 | 128.034052 |

*(first 12 of 36 columns shown)*

</details>

### `WBN_DATABASE`.`EQUIPMENTS_HOURLY_ACTIVITIES`

- **Rows**: 4,675,157
- **Flags**: TRUCK, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `DATE` — 1899-12-30 to 2026-07-26

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | no |
| 3 | `DATE` | date | no |
| 4 | `SHIFT` | int | yes |
| 5 | `START_HOUR` | int | yes |
| 6 | `END_HOUR` | int | yes |
| 7 | `ACTIVITY` | nvarchar(255) | no |
| 8 | `MATERIAL` | nvarchar(255) | yes |
| 9 | `MATERIAL_CLASS` | nvarchar(255) | yes |
| 10 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 11 | `ORIGIN_ID` | nvarchar(255) | yes |
| 12 | `SUB_PIT` | nvarchar(255) | yes |
| 13 | `PROD_ID` | nvarchar(255) | yes |
| 14 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 15 | `DESTINATION_ID` | nvarchar(255) | yes |
| 16 | `DISTANCE` | float | yes |
| 17 | `TRUCK_ID` | nvarchar(255) | yes |
| 18 | `TRUCK_FACTOR` | float | yes |
| 19 | `EXCAVATOR_ID` | nvarchar(255) | yes |
| 20 | `RIT` | float | yes |
| 21 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | START_HOUR | END_HOUR | ACTIVITY | MATERIAL | MATERIAL_CLASS | ORIGIN_AREA | ORIGIN_ID | SUB_PIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6634 | RIM | 2024-11-26 | 1 | 8 | 9 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 |
| 6635 | RIM | 2024-11-26 | 1 | 9 | 10 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 |
| 6636 | RIM | 2024-11-26 | 1 | 10 | 11 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 |
| 6637 | RIM | 2024-11-26 | 1 | 11 | 12 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 |
| 6638 | RIM | 2024-11-26 | 1 | 13 | 14 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 |

*(first 12 of 21 columns shown)*

</details>

### `WBN_DATABASE`.`BLOCK_INDESIGN`

- **Rows**: 4,288,722
- **Flags**: col:TIME
- **Date column**: `DATE` — 2025-06-12 00:00:00 to 2026-05-10 00:00:00

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `PIT` | nvarchar(255) | yes |
| 4 | `X` | float | yes |
| 5 | `Y` | float | yes |
| 6 | `Z` | float | yes |
| 7 | `BLOCK_ID` | nvarchar(255) | yes |
| 8 | `PP_INPIT` | float | yes |
| 9 | `size (X)` | float | yes |
| 10 | ` size(Y)` | float | yes |
| 11 | ` size(Z)` | float | yes |
| 12 | `SUBPIT` | nvarchar(255) | yes |
| 13 | `SUBPIT_REMARKS` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | PIT | X | Y | Z | BLOCK_ID | PP_INPIT | size (X) |  size(Y) |  size(Z) | SUBPIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-06-12 00:00:00 | CBB | 380600.0 | 57750.0 | 402.0 | 401_B23_S198 | 0.0898 | 12.5 | 12.5 | 2.0 | CBBB3 |
| 2 | 2025-06-12 00:00:00 | CBB | 380600.0 | 57737.5 | 402.0 | 401_B23_S199 | 0.5566 | 12.5 | 12.5 | 2.0 | CBBB3 |
| 3 | 2025-06-12 00:00:00 | CBB | 380600.0 | 57725.0 | 402.0 | 401_B23_S200 | 0.8691 | 12.5 | 12.5 | 2.0 | CBBB3 |
| 4 | 2025-06-12 00:00:00 | CBB | 380600.0 | 57712.5 | 402.0 | 401_B23_S201 | 1.0 | 12.5 | 12.5 | 2.0 | CBBB3 |
| 5 | 2025-06-12 00:00:00 | CBB | 380600.0 | 57700.0 | 402.0 | 401_B23_S202 | 0.998 | 12.5 | 12.5 | 2.0 | CBBB3 |

*(first 12 of 13 columns shown)*

</details>

### `FMS_DB`.`autoFMS_SECURITY_INCIDENT_KILOMETER`

- **Rows**: 4,092,100
- **Flags**: none
- *redacted columns: Eventtypename*

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Eventtypename` 🔒 | nvarchar(255) | yes |
| 2 | `id` | nvarchar(100) | no |
| 3 | `DIRECTION` | nvarchar(50) | yes |
| 4 | `SectionKM` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Eventtypename | id | DIRECTION | SectionKM |
|---|---|---|---|
| [REDACTED] | 107015291859043_10004_1772131172000 | TOFU | 53.5 |
| [REDACTED] | 107015291859043_10004_1772682625000 | KR | 30.6 |
| [REDACTED] | 107015291859043_10004_1773379056000 | TOFU | 53.5 |
| [REDACTED] | 107015291859043_10004_1773451354000 | TOFU | 49.4 |
| [REDACTED] | 107015291859043_10004_1774002631000 | TOFU | 60.7 |

</details>

### `WBN_DATABASE`.`EQUIPMENTS_STATUS`

- **Rows**: 3,670,386
- **Flags**: TRUCK, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-26

<details><summary>22 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `ID_EQ` | nvarchar(50) | yes |
| 6 | `STATUS` | nvarchar(50) | yes |
| 7 | `ACTIVITY` | nvarchar(50) | yes |
| 8 | `LOCATION` | nvarchar(50) | yes |
| 9 | `LOCATION_DETAILS` | nvarchar(50) | yes |
| 10 | `HOUR_METER_START` | float | yes |
| 11 | `HOUR_METER_END` | float | yes |
| 12 | `USAGE_KM_METER` | float | yes |
| 13 | `WORKING_HOURS` | float | yes |
| 14 | `STBY_HOURS` | float | yes |
| 15 | `STBY_CODE` | nvarchar(50) | yes |
| 16 | `BD_HOURS` | float | yes |
| 17 | `BD_CODE` | nvarchar(50) | yes |
| 18 | `BD_START` | date | yes |
| 19 | `BD_EST_RFU` | date | yes |
| 20 | `BD_COMPARTMENT` | nvarchar(50) | yes |
| 21 | `BD_STATUS` | nvarchar(50) | yes |
| 22 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | STATUS | ACTIVITY | LOCATION | LOCATION_DETAILS | HOUR_METER_START | HOUR_METER_END | USAGE_KM_METER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 26533 | SMA | 2024-10-01 |  | EX407 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 16154.4 |  |
| 26534 | SMA | 2024-10-01 |  | EX408 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 19621.9 |  |
| 26535 | SMA | 2024-10-01 |  | EX409 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 19905.0 |  |
| 26536 | SMA | 2024-10-01 |  | EX410 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 17538.2 |  |
| 26537 | SMA | 2024-10-01 |  | EX411 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 18204.1 |  |

*(first 12 of 22 columns shown)*

</details>

### `WBN_DATABASE`.`HAULAGE`

- **Rows**: 3,508,949
- **Flags**: PLAN, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `DATE` — 2021-09-24 to 2026-07-26

<details><summary>24 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | no |
| 3 | `SHIFT` | int | yes |
| 4 | `CONTRACTOR` | nvarchar(50) | no |
| 5 | `ACTIVITY` | nvarchar(50) | no |
| 6 | `MATERIAL` | nvarchar(50) | no |
| 7 | `TRUCK_ID` | nvarchar(50) | yes |
| 8 | `TIME_LOADED` | time | yes |
| 9 | `TIME_EMPTY` | time | yes |
| 10 | `RIT` | int | yes |
| 11 | `ORIGIN_AREA` | nvarchar(50) | yes |
| 12 | `ORIGIN_ID` | nvarchar(50) | yes |
| 13 | `DESTINATION_AREA` | nvarchar(50) | yes |
| 14 | `DESTINATION_ID` | nvarchar(50) | yes |
| 15 | `KG_LOADED` | float | yes |
| 16 | `KG_EMPTY` | float | yes |
| 17 | `KG_NET` | float | yes |
| 18 | `WMT` | float | yes |
| 19 | `BCM` | float | yes |
| 20 | `WB_ID` | nvarchar(50) | yes |
| 21 | `REMARK` | nvarchar(50) | yes |
| 22 | `TICKET_NO` | nvarchar(30) | yes |
| 23 | `UPDATE_DATE` | datetime2 | yes |
| 24 | `UPDATE_BY` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | ACTIVITY | MATERIAL | TRUCK_ID | TIME_LOADED | TIME_EMPTY | RIT | ORIGIN_AREA | ORIGIN_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3127402 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5702 | 12:48:53 | 13:30:06 | 1 | TOS_KR_STM_08 | KR.I.1280 |
| 3127403 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5725 | 12:49:21 | 13:27:54 | 1 | TOS_KR_STM_05 | KR.I.1277 |
| 3127404 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5737 | 12:52:01 | 13:42:24 | 1 | TOS_KR_STM_08 | KR.I.1280 |
| 3127405 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5525 | 12:54:51 | 13:53:01 | 1 | TOS_KR_STM_08 | KR.I.1280 |
| 3127406 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5729 | 13:07:13 | 14:09:31 | 1 | TOS_KR_STM_05 | KR.I.1277 |

*(first 12 of 24 columns shown)*

</details>

### `WBN_DATABASE`.`S123_STOCK_SHAPE_OLD`

- **Rows**: 1,732,432
- **Flags**: col:TIME
- **Date column**: `UPDATE_DATE` — 2026-03-17 08:41:50 to 2026-06-27 09:47:07
- *redacted columns: name*

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `UPDATE_DATE` | datetime | yes |
| 2 | `id` | int | no |
| 3 | `FID` | int | yes |
| 4 | `name` 🔒 | nvarchar(255) | yes |
| 5 | `CreationDa` | datetime | yes |
| 6 | `Creator` | nvarchar(255) | yes |
| 7 | `EditDate` | datetime | yes |
| 8 | `geom` | geography(max) | yes |
| 9 | `new_dome_i` | nvarchar(255) | yes |
| 10 | `old_dome_i` | nvarchar(255) | yes |
| 11 | `menggantik` | nvarchar(255) | yes |
| 12 | `OBJECTID` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| UPDATE_DATE | id | FID | name | CreationDa | Creator | EditDate | geom | new_dome_i | old_dome_i | menggantik | OBJECTID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-16 17:29:47.403000 | 48828 | 2461 |  | 2024-11-06 19:17:25 |  | 2024-11-06 19:17:25 | <112 bytes> | AC.272 | ADM.120 | Sepenuhnya |  |
| 2026-04-16 17:29:47.403000 | 48829 | 2462 |  | 2024-11-06 19:18:06 |  | 2024-11-06 19:18:06 | <112 bytes> | AD.248 | AAM.292 | Sepenuhnya |  |
| 2026-04-16 17:29:47.403000 | 48830 | 2463 |  | 2024-11-06 19:18:46 |  | 2024-11-06 19:18:46 | <112 bytes> | AA.498 | AD.234 | Sepenuhnya |  |
| 2026-04-16 17:29:47.403000 | 48831 | 2464 |  | 2024-11-06 19:19:58 |  | 2024-11-06 19:19:58 | <144 bytes> | ACM.328 | ADM.328 | Sepenuhnya |  |
| 2026-04-16 17:29:47.403000 | 48832 | 2465 |  | 2024-11-07 10:58:36 |  | 2024-11-07 10:58:36 | <112 bytes> | ABM.262 | ADM.257 | Sepenuhnya |  |

</details>

### `FMS_DB`.`auto_spFMS_PLAYBACK_TRACK_DATA`

- **Rows**: 1,554,167
- **Flags**: GPS, col:COORD, col:TIME
- *redacted columns: imei*

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `imei` 🔒 | bigint | no |
| 2 | `time` | bigint | no |
| 3 | `plateNumber` | varchar(50) | yes |
| 4 | `SP_STATION` | varchar(50) | yes |
| 5 | `SP_DISTANCE_M` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| imei | time | plateNumber | SP_STATION | SP_DISTANCE_M |
|---|---|---|---|---|
| [REDACTED] | 1783609500000 | E814 |  |  |
| [REDACTED] | 1783615500000 | E814 |  |  |
| [REDACTED] | 1783611330000 | E814 |  |  |
| [REDACTED] | 1783610730000 | E814 |  |  |
| [REDACTED] | 1783611300000 | E814 |  |  |

</details>

### `WBN_DATABASE`.`HAULAGE_IWIP_EXT`

- **Rows**: 1,508,871
- **Flags**: PLAN, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `FETCH_DATE` — 2026-05-30 11:32:40 to 2026-07-11 05:10:04
- *redacted columns: SERIAL_NO, CARGO_NAME*

<details><summary>28 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime2 | yes |
| 2 | `SERIAL_NO` 🔒 | nvarchar(255) | yes |
| 3 | `WB_TIME` | int | yes |
| 4 | `DATE` | date | yes |
| 5 | `WB_ID` | nvarchar(255) | yes |
| 6 | `TICKET_NO` | nvarchar(50) | no |
| 7 | `TRUCK_ID` | nvarchar(255) | yes |
| 8 | `CARGO_NAME` 🔒 | nvarchar(255) | yes |
| 9 | `ORIGIN_ID` | nvarchar(255) | yes |
| 10 | `SELLER` | nvarchar(255) | yes |
| 11 | `BUYER` | nvarchar(255) | yes |
| 12 | `CONTRACTOR` | nvarchar(255) | yes |
| 13 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 14 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 15 | `WEIGHING_STATUS` | nvarchar(255) | yes |
| 16 | `BUSINESS_TYPE` | nvarchar(255) | yes |
| 17 | `GROSS_WEIGHT` | bigint | yes |
| 18 | `TARE_WEIGHT` | bigint | yes |
| 19 | `NET_WEIGHT` | bigint | yes |
| 20 | `FIRST_WB_TIME` | datetime | yes |
| 21 | `SECOND_WB_TIME` | datetime | yes |
| 22 | `GROSS_WEIGHT_TIME` | datetime | yes |
| 23 | `TARE_WEIGHT_TIME` | datetime | yes |
| 24 | `GROSS_WEIGHT_POINT` | nvarchar(255) | yes |
| 25 | `TARE_WEIGHT_POINT` | nvarchar(255) | yes |
| 26 | `IS_COMPLETED` | nvarchar(255) | yes |
| 27 | `SHIFT` | nvarchar(255) | yes |
| 28 | `REMARKS` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | ORIGIN_ID | SELLER | BUYER | CONTRACTOR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-30 11:33:15 | [REDACTED] | 20251231 | 2025-12-31 | T10 | 10A20251231025052 | R587 | [REDACTED] | CN857 | YNI镍铁事业部 | YNI镍铁事业部 | EOS镍矿运输车间 |
| 2026-05-30 11:33:15 | [REDACTED] | 20251231 | 2025-12-31 | T10 | 10A20251231025830 | K043 | [REDACTED] | CN857 | YNI镍铁事业部 | YNI镍铁事业部 | 镍矿运输F车间 |
| 2026-05-30 11:33:15 | [REDACTED] | 20251231 | 2025-12-31 | T10 | 10A20251231030555 | B792 | [REDACTED] | HN635 | HKNI镍铁事业部 | HKNI镍铁事业部 | 镍矿运输H车间 |
| 2026-05-30 11:33:15 | [REDACTED] | 20251231 | 2025-12-31 | T10 | 10A20251231031308 | R591 | [REDACTED] | CN857 | YNI镍铁事业部 | YNI镍铁事业部 | EOS镍矿运输车间 |
| 2026-05-30 11:33:15 | [REDACTED] | 20251231 | 2025-12-31 | T10 | 10A20251231031429 | L643 | [REDACTED] | HN635 | HKNI镍铁事业部 | HKNI镍铁事业部 | EOS镍矿运输车间 |

*(first 12 of 28 columns shown)*

</details>

### `FMS_DB`.`FMS_INTERVENTION_EVENT_DATA`

- **Rows**: 1,243,050
- **Flags**: col:COORD, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `FETCH_DATE` — 2026-04-07 16:43:10 to 2026-07-27 18:33:09
- *redacted columns: checkDriverPhone, checkDriverName, carrierName, orgName, dealUserName, interveneTypeName, statusName, interventionTypeName, classTypeName, eventTypeName, imei, riskLevelName*

<details><summary>32 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `checkDriverPhone` 🔒 | nvarchar(255) | yes |
| 3 | `riskLevel` | float | yes |
| 4 | `orgId` | nvarchar(255) | yes |
| 5 | `riskId` | nvarchar(255) | yes |
| 6 | `checkDriverName` 🔒 | nvarchar(255) | yes |
| 7 | `carrierName` 🔒 | nvarchar(255) | yes |
| 8 | `startTime` | float | yes |
| 9 | `mileage` | nvarchar(255) | yes |
| 10 | `truckId` | nvarchar(255) | yes |
| 11 | `eventId` | nvarchar(255) | yes |
| 12 | `orgName` 🔒 | nvarchar(255) | yes |
| 13 | `duration` | nvarchar(255) | yes |
| 14 | `voiceMsg` | nvarchar(255) | yes |
| 15 | `dealUserName` 🔒 | nvarchar(255) | yes |
| 16 | `fileSize` | nvarchar(255) | yes |
| 17 | `interveneTypeName` 🔒 | nvarchar(255) | yes |
| 18 | `statusName` 🔒 | nvarchar(255) | yes |
| 19 | `fileUrl` | nvarchar(255) | yes |
| 20 | `interveneType` | nvarchar(255) | yes |
| 21 | `sendTime` | float | yes |
| 22 | `status` | nvarchar(255) | yes |
| 23 | `eventType` | nvarchar(255) | yes |
| 24 | `intervener` | nvarchar(255) | yes |
| 25 | `plateNumber` | nvarchar(255) | yes |
| 26 | `totalDifftime` | float | yes |
| 27 | `interventionTypeName` 🔒 | nvarchar(255) | yes |
| 28 | `classTypeName` 🔒 | nvarchar(255) | yes |
| 29 | `eventTypeName` 🔒 | nvarchar(255) | yes |
| 30 | `imei` 🔒 | nvarchar(255) | yes |
| 31 | `endTime` | nvarchar(255) | yes |
| 32 | `riskLevelName` 🔒 | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | checkDriverPhone | riskLevel | orgId | riskId | checkDriverName | carrierName | startTime | mileage | truckId | eventId | orgName |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-19 20:06:17 |  | 2.0 | 7190744540448426241 | 8783529426589322880 |  |  | 1776505575589.0 |  | 7292459050464447238 |  | [REDACTED] |
| 2026-04-20 00:06:07.443000 |  | 1.0 | 7190742966074476803 | 8784153325853216643 |  |  | 1776524169288.0 |  | 6922135043683123464 |  | [REDACTED] |
| 2026-04-20 00:06:07.443000 |  | 1.0 | 7190742966074476803 | 8784153325853216643 |  |  | 1776524169288.0 |  | 6922135043683123464 |  | [REDACTED] |
| 2026-04-20 00:06:07.443000 |  | 0.0 | 7190741266106286983 |  | [REDACTED] |  | 1776524189000.0 |  | 7154829818062966530 | 107015291863388_10017_1776524189000_org_id_71907412661062... | [REDACTED] |
| 2026-04-20 00:06:07.443000 | [REDACTED] | 1.0 | 7190740880934963462 | 8784150914598178689 | [REDACTED] |  | 1776524097404.0 |  | 7237172914452434049 |  | [REDACTED] |

*(first 12 of 32 columns shown)*

</details>

### `WBN_DATABASE`.`RSF_HAULING_DATA`

- **Rows**: 1,143,509
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2023-12-23 00:00:00 to 2026-01-22 00:00:00

<details><summary>18 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `COMPANY` | nvarchar(50) | yes |
| 5 | `DEPARTEMENT` | nvarchar(50) | yes |
| 6 | `UNIT_TYPE` | nvarchar(50) | yes |
| 7 | `UNIT_BRAND` | nvarchar(50) | yes |
| 8 | `NB_UNIT` | nvarchar(50) | yes |
| 9 | `TRIP` | float | yes |
| 10 | `LOADING_TIME` | time | yes |
| 11 | `UNLOADING_TIME` | time | yes |
| 12 | `ORIGIN_KM` | nvarchar(50) | yes |
| 13 | `ORIGIN` | nvarchar(50) | yes |
| 14 | `DESTINATION_KM` | nvarchar(50) | yes |
| 15 | `DESTINATION` | nvarchar(50) | yes |
| 16 | `LOCATION` | nvarchar(50) | yes |
| 17 | `ELEVATION` | float | yes |
| 18 | `TF` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | COMPANY | DEPARTEMENT | UNIT_TYPE | UNIT_BRAND | NB_UNIT | TRIP | LOADING_TIME | UNLOADING_TIME | ORIGIN_KM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 321550 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L240 | 1.0 |  |  | KM8 |
| 321551 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K365 | 1.0 |  |  | KM8 |
| 321552 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L216 | 1.0 |  |  | KM8 |
| 321553 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L565 | 1.0 |  |  | KM8 |
| 321554 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L236 | 1.0 |  |  | KM8 |

*(first 12 of 18 columns shown)*

</details>

### `FMS_DB`.`FMS_PLAYBACK_TRACK_24H`

- **Rows**: 1,140,456
- **Flags**: GPS, col:COORD, col:EQUIP, col:SPEED, col:TIME
- *redacted columns: IMEI*

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `IMEI` 🔒 | varchar(32) | no |
| 2 | `TS` | bigint | no |
| 3 | `PLATE` | varchar(32) | yes |
| 4 | `TRUCK_ID` | varchar(40) | yes |
| 5 | `LAT` | float | yes |
| 6 | `LNG` | float | yes |
| 7 | `SPEED` | float | yes |
| 8 | `COURSE` | float | yes |
| 9 | `ACC` | int | yes |
| 10 | `LOC_TYPE` | int | yes |
| 11 | `DISTANCE` | float | yes |
| 12 | `INTERP` | int | yes |
| 13 | `RECEIVE_TIME` | bigint | yes |
| 14 | `UPDATED_AT` | bigint | yes |

</details>

<details><summary>Sample rows (5)</summary>

| IMEI | TS | PLATE | TRUCK_ID | LAT | LNG | SPEED | COURSE | ACC | LOC_TYPE | DISTANCE | INTERP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [REDACTED] | 1785061239000 | K565 | 6922135043045589259 | 0.529415 | 127.89891 | 0.0 | 289.0 | 1 | 0 | 2659.0 | 1 |
| [REDACTED] | 1785061350000 | K565 | 6922135043045589259 | 0.529418 | 127.898903 | 0.0 | 289.0 | 1 | 0 | 86.0 | 1 |
| [REDACTED] | 1785061440000 | K565 | 6922135043045589259 | 0.529427 | 127.898903 | 0.0 | 289.0 | 1 | 0 | 102.0 | 1 |
| [REDACTED] | 1785063450000 | K565 | 6922135043045589259 | 0.529705 | 127.89893 | 9.0 | 26.0 | 1 | 0 | 3170.0 | 1 |
| [REDACTED] | 1785063479000 | K565 | 6922135043045589259 | 0.530313 | 127.899032 | 8.0 | 11.0 | 1 | 0 | 7006.0 | 1 |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`WAITING_TIME`

- **Rows**: 878,240
- **Flags**: col:EQUIP, col:TIME
- **Date column**: `DATE` — 2025-01-01 to 2026-07-22
- *redacted columns: DRIVER_ID*

<details><summary>24 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `TEAM` | nvarchar(10) | yes |
| 3 | `DATE` | date | yes |
| 4 | `EQUIPMENT_ID` | nvarchar(50) | yes |
| 5 | `SHIFT` | int | yes |
| 6 | `ORIGIN_ID` | nvarchar(50) | yes |
| 7 | `ORIGIN_AREA` | nvarchar(50) | yes |
| 8 | `DESTINATION` | nvarchar(100) | yes |
| 9 | `BLOCK_ID` | nvarchar(50) | yes |
| 10 | `RIT` | int | yes |
| 11 | `WB_ID` | nvarchar(50) | yes |
| 12 | `LOADING_WAITING_TIME` | time | yes |
| 13 | `LOADING_TIME` | time | yes |
| 14 | `LOADING_DIFFERENCE_TIME` | int | yes |
| 15 | `DUMPING_WAITING_TIME` | time | yes |
| 16 | `DUMPING_TIME` | time | yes |
| 17 | `DUMPING_DIFFERENCE_TIME` | int | yes |
| 18 | `DRIVER_ID` 🔒 | nvarchar(50) | yes |
| 19 | `PIT` | nvarchar(50) | yes |
| 20 | `FUEL_FILLING_TIME` | time | yes |
| 21 | `REMARK` | nvarchar(255) | yes |
| 22 | `FUEL_FILLING_TIME 2` | time | yes |
| 23 | `TOTAL_FUEL` | nvarchar(50) | yes |
| 24 | `TOTAL_FUEL 2` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | TEAM | DATE | EQUIPMENT_ID | SHIFT | ORIGIN_ID | ORIGIN_AREA | DESTINATION | BLOCK_ID | RIT | WB_ID | LOADING_WAITING_TIME |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 71844 | E | 2025-10-30 | L961 | 2 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 02:47:00 |
| 71845 | B | 2025-10-30 | K811 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 09:47:00 |
| 71846 | E | 2025-10-30 | N035 | 1 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 11:00:00 |
| 71847 | D | 2025-10-30 | L958 | 1 | SAMPLE | CSW | BIRI | SAMPLE | 1 | NOT WEIGHED | 16:41:00 |
| 71848 | B | 2025-10-30 | L054 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 14:55:00 |

*(first 12 of 24 columns shown)*

</details>

### `WBN_DATABASE`.`HAULAGE_IWIP`

- **Rows**: 572,742
- **Flags**: PLAN, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-12-27 to 2026-07-08
- *redacted columns: SERIAL_NO, CARGO_NAME*

<details><summary>35 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SERIAL_NO` 🔒 | nvarchar(50) | yes |
| 2 | `WB_TIME` | float | yes |
| 3 | `DATE` | date | yes |
| 4 | `WB_ID` | nvarchar(50) | yes |
| 5 | `TICKET_NO` | nvarchar(50) | no |
| 6 | `TRUCK_ID` | nvarchar(50) | yes |
| 7 | `CARGO_NAME` 🔒 | nvarchar(50) | yes |
| 8 | `SELLER` | nvarchar(50) | yes |
| 9 | `BUYER` | nvarchar(50) | yes |
| 10 | `CONTRACTOR` | nvarchar(50) | yes |
| 11 | `ORIGIN_AREA` | nvarchar(50) | yes |
| 12 | `ORIGIN_AREA_CLEAN` | nvarchar(50) | yes |
| 13 | `ORIGIN_ID` | nvarchar(50) | yes |
| 14 | `ORIGIN_ID_CLEAN` | nvarchar(50) | yes |
| 15 | `DESTINATION_AREA` | nvarchar(50) | yes |
| 16 | `DESTINATION_AREA_CLEAN` | nvarchar(50) | yes |
| 17 | `DESTINATION_ID` | nvarchar(50) | yes |
| 18 | `DESTINATION_ID_CLEAN` | nvarchar(50) | yes |
| 19 | `WEIGHING_STATUS` | float | yes |
| 20 | `BUSINESS_TYPE` | nvarchar(50) | yes |
| 21 | `ACTIVITY` | nvarchar(50) | yes |
| 22 | `GROSS_WEIGHT` | float | yes |
| 23 | `TARE_WEIGHT` | float | yes |
| 24 | `NET_WEIGHT` | float | yes |
| 25 | `FIRST_WB_TIME` | datetime | yes |
| 26 | `SECOND_WB_TIME` | datetime | yes |
| 27 | `GROSS_WEIGHT_TIME` | datetime | yes |
| 28 | `TARE_WEIGHT_TIME` | datetime | yes |
| 29 | `GROSS_WEIGHT_POINT` | nvarchar(50) | yes |
| 30 | `TARE_WEIGHT_POINT` | nvarchar(50) | yes |
| 31 | `IS_COMPLETED` | nvarchar(50) | yes |
| 32 | `SHIFT` | nvarchar(50) | yes |
| 33 | `REMARKS` | nvarchar(50) | yes |
| 34 | `FETCH_DATE` | datetime | yes |
| 35 | `IS_CLEAN` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | SELLER | BUYER | CONTRACTOR | ORIGIN_AREA | ORIGIN_AREA_CLEAN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [REDACTED] | 0.0 |  |  |  |  |  |  |  |  |  |  |
| [REDACTED] | 20260102.0 | 2026-01-02 | 10 | 10A20260102123411 | B345 |  |  |  | 镍矿运输F车间 | CAS矿石堆场-WBN镍铁事业部 | CRUSHER CAS |
| [REDACTED] | 20260102.0 | 2026-01-02 | 10 | 10A20260102132414 | B345 |  |  |  | 镍矿运输F车间 | CAS矿石堆场-WBN镍铁事业部 | CRUSHER CAS |
| [REDACTED] | 20260102.0 | 2026-01-02 | 10 | 10A20260102144822 | B345 |  |  |  | 镍矿运输F车间 | CAS矿石堆场-WBN镍铁事业部 | CRUSHER CAS |
| [REDACTED] | 20260104.0 | 2026-01-04 | 10 | 10A20260104102217 | N539 |  |  |  | INLE运输C车间 | POS12 EXT-IFMI镍铁事业部 | POS 12 |

*(first 12 of 35 columns shown)*

</details>

### `WBN_DATABASE`.`TOS_STATUS`

- **Rows**: 548,245
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-09-30 00:00:00 to 2026-07-26 00:00:00

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | datetime | no |
| 4 | `SHIFT` | float | yes |
| 5 | `STOCK_ID` | nvarchar(50) | no |
| 6 | `STOCK_STATUS` | nvarchar(50) | no |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | STOCK_ID | STOCK_STATUS |
|---|---|---|---|---|---|
| 1 |  | 2025-03-12 00:00:00 | 1.0 | TF.A.2441 | COMPLETE |
| 2 |  | 2025-03-12 00:00:00 | 2.0 | TF.A.2441 | COMPLETE |
| 3 |  | 2025-03-13 00:00:00 | 1.0 | TF.A.2441 | COMPLETE |
| 4 |  | 2025-03-13 00:00:00 | 2.0 | TF.A.2441 | COMPLETE |
| 5 |  | 2025-03-14 00:00:00 | 1.0 | TF.A.2441 | COMPLETE |

</details>

### `FMS_DB`.`FMS_GPS_Historical`

- **Rows**: 521,918
- **Flags**: GPS, col:COORD, col:EQUIP, col:SPEED, col:TIME
- *redacted columns: IMEI*

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `IMEI` 🔒 | varchar(32) | no |
| 2 | `TS` | bigint | no |
| 3 | `PLATE` | varchar(32) | yes |
| 4 | `TRUCK_ID` | varchar(40) | yes |
| 5 | `LAT` | float | yes |
| 6 | `LNG` | float | yes |
| 7 | `SPEED` | float | yes |
| 8 | `COURSE` | float | yes |
| 9 | `ACC` | int | yes |
| 10 | `LOC_TYPE` | int | yes |
| 11 | `DISTANCE` | float | yes |
| 12 | `INTERP` | int | yes |
| 13 | `RECEIVE_TIME` | bigint | yes |
| 14 | `UPDATED_AT` | bigint | yes |
| 15 | `ARCHIVED_AT` | bigint | yes |

</details>

<details><summary>Sample rows (5)</summary>

| IMEI | TS | PLATE | TRUCK_ID | LAT | LNG | SPEED | COURSE | ACC | LOC_TYPE | DISTANCE | INTERP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [REDACTED] | 1784360520000 | K565 | 6922135043045589259 | 0.7799 | 128.075532 | 11.0 | 222.0 | 1 | 0 | 3081433.0 | 1 |
| [REDACTED] | 1784360559000 | K565 | 6922135043045589259 | 0.778953 | 128.074473 | 22.0 | 253.0 | 1 | 0 | 16166.0 | 1 |
| [REDACTED] | 1784360566000 | K565 | 6922135043045589259 | 0.77893 | 128.074093 | 19.0 | 273.0 | 1 | 0 | 4237.0 | 1 |
| [REDACTED] | 1784360607000 | K565 | 6922135043045589259 | 0.778852 | 128.07294 | 14.0 | 243.0 | 1 | 0 | 13150.0 | 1 |
| [REDACTED] | 1784360610000 | K565 | 6922135043045589259 | 0.778775 | 128.072837 | 19.0 | 235.0 | 1 | 0 | 1431.0 | 1 |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`DAY_WORKS`

- **Rows**: 495,384
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-15 to 2026-07-23
- *redacted columns: OPERATOR_ID, ROAD_NAME*

<details><summary>27 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `UUID` | nvarchar(255) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `CONTRACTOR` | nvarchar(50) | yes |
| 6 | `ACTIVITY_CAT` | nvarchar(50) | yes |
| 7 | `ACTIVITY_DESC` | nvarchar(255) | yes |
| 8 | `ACTIVITY_PLANNED` | nvarchar(50) | yes |
| 9 | `ACTIVITY_TIME_START` | time | yes |
| 10 | `ACTIVITY_TIME_END` | time | yes |
| 11 | `OPERATOR_ID` 🔒 | nvarchar(50) | yes |
| 12 | `UNIT_TYPE` | nvarchar(50) | yes |
| 13 | `UNIT_CLASS` | nvarchar(50) | yes |
| 14 | `UNIT_ID` | nvarchar(50) | yes |
| 15 | `UNIT_START_HOUR_METER` | float | yes |
| 16 | `UNIT_END_HOUR_METER` | float | yes |
| 17 | `LOCATION` | nvarchar(255) | yes |
| 18 | `ROAD_NAME` 🔒 | nvarchar(50) | yes |
| 19 | `ROAD_STA_KM` | float | yes |
| 20 | `ROAD_END_KM` | float | yes |
| 21 | `ROAD_LANE` | nvarchar(50) | yes |
| 22 | `LOADING_POINT` | nvarchar(50) | yes |
| 23 | `LOADING_RIT` | float | yes |
| 24 | `DISTANCE_KM` | float | yes |
| 25 | `REMARK` | nvarchar(255) | yes |
| 26 | `UPDATE_DATE` | datetime | yes |
| 27 | `UPDATE_BY` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | UUID | DATE | SHIFT | CONTRACTOR | ACTIVITY_CAT | ACTIVITY_DESC | ACTIVITY_PLANNED | ACTIVITY_TIME_START | ACTIVITY_TIME_END | OPERATOR_ID | UNIT_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 59482 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | [REDACTED] | Compactor |
| 59483 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Ob... | PLANNED | 07:00:00 | 18:00:00 | [REDACTED] | Motor Grader |
| 59484 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | [REDACTED] | Water Truck |
| 59485 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | [REDACTED] | Compactor |
| 59486 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Ob... | PLANNED | 07:00:00 | 18:00:00 | [REDACTED] | Motor Grader |

*(first 12 of 27 columns shown)*

</details>

### `WBN_DATABASE`.`PRODUCTION_ACTIVITY_PIT`

- **Rows**: 449,992
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-07-01 00:00:00 to 2026-07-26 00:00:00

<details><summary>34 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | no |
| 3 | `CONTRACTOR` | nvarchar(255) | no |
| 4 | `SHIFT` | float | yes |
| 5 | `AREA` | nvarchar(255) | no |
| 6 | `SUB_AREA` | nvarchar(255) | yes |
| 7 | `ACTIVITY` | nvarchar(255) | no |
| 8 | `ENTITY` | nvarchar(255) | no |
| 9 | `MATERIAL` | nvarchar(255) | yes |
| 10 | `MATERIAL_CLASS` | nvarchar(255) | yes |
| 11 | `ORIGIN_ID_BLOCK_ID` | nvarchar(255) | yes |
| 12 | `PROD_ID` | nvarchar(255) | yes |
| 13 | `BLAST_ID` | nvarchar(255) | yes |
| 14 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 15 | `DESTINATION_ID` | nvarchar(255) | yes |
| 16 | `TF_BCM` | float | yes |
| 17 | `TF_WMT` | float | yes |
| 18 | `RIT` | float | yes |
| 19 | `BCM` | float | yes |
| 20 | `WMT` | float | yes |
| 21 | `EXCA_ID` | nvarchar(255) | yes |
| 22 | `GRAP_ID` | nvarchar(255) | yes |
| 23 | `WL_ID` | nvarchar(255) | yes |
| 24 | `ADT_ID` | nvarchar(255) | yes |
| 25 | `DT_ID` | nvarchar(255) | yes |
| 26 | `DOZER_ID` | nvarchar(255) | yes |
| 27 | `GRADER_ID` | nvarchar(255) | yes |
| 28 | `COMPACT_ID` | nvarchar(255) | yes |
| 29 | `WT_ID` | nvarchar(255) | yes |
| 30 | `RIG_ID` | nvarchar(255) | yes |
| 31 | `STATUS` | nvarchar(255) | yes |
| 32 | `REMARK` | nvarchar(255) | yes |
| 33 | `UPDATE_DATE` | datetime | yes |
| 34 | `UPDATE_BY` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | SHIFT | AREA | SUB_AREA | ACTIVITY | ENTITY | MATERIAL | MATERIAL_CLASS | ORIGIN_ID_BLOCK_ID | PROD_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-26 00:00:00 | RIM | 1.0 | BLB | BLB3 | BLASTINGS | QUARRY | QRY |  | TOS_BLB_RIM_05 |  |
| 2 | 2026-05-27 00:00:00 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  |
| 3 | 2026-05-27 00:00:00 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  |
| 4 | 2026-05-27 00:00:00 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  |
| 5 | 2026-05-27 00:00:00 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  |

*(first 12 of 34 columns shown)*

</details>

### `WBN_DATABASE`.`PRODUCTION_PIT_OLD`

- **Rows**: 407,593
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-07-01 00:00:00 to 2026-06-07 00:00:00

<details><summary>23 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(255) | no |
| 3 | `DATE` | datetime | no |
| 4 | `SHIFT` | float | yes |
| 5 | `ACTIVITY` | nvarchar(255) | yes |
| 6 | `PIT` | nvarchar(255) | yes |
| 7 | `SUBPIT` | nvarchar(255) | yes |
| 8 | `BLOCK_TYPE` | nvarchar(255) | yes |
| 9 | `BLOCK_STATUS` | nvarchar(255) | yes |
| 10 | `BLOCK_ID` | nvarchar(255) | yes |
| 11 | `PROD_ID` | nvarchar(255) | yes |
| 12 | `MATERIAL` | nvarchar(255) | no |
| 13 | `MATERIAL_CLASS` | nvarchar(255) | yes |
| 14 | `RIT` | float | yes |
| 15 | `TF` | float | yes |
| 16 | `WMT` | float | yes |
| 17 | `DESTINATION` | nvarchar(255) | yes |
| 18 | `TOS_PILE` | nvarchar(255) | yes |
| 19 | `BLAST_STATUS` | nvarchar(255) | yes |
| 20 | `BLAST_ID` | nvarchar(255) | yes |
| 21 | `UPDATE_DATE` | datetime | yes |
| 22 | `UPDATE_BY` | nvarchar(50) | yes |
| 23 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | ACTIVITY | PIT | SUBPIT | BLOCK_TYPE | BLOCK_STATUS | BLOCK_ID | PROD_ID | MATERIAL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 684434 | STM | 2026-04-17 00:00:00 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T429_B164_S46 | T429_B164_S46 | SAP |
| 684435 | STM | 2026-04-17 00:00:00 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T429_B164_S47 | T429_B164_S47 | SAP |
| 684436 | STM | 2026-04-17 00:00:00 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T423_B180_S32 | T423_B180_S32 | SAP |
| 684437 | STM | 2026-04-17 00:00:00 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T423_B180_S33 | T423_B180_S33 | SAP |
| 684438 | STM | 2026-04-17 00:00:00 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T420_B180_S33 | T420_B180_S33 | SAP |

*(first 12 of 23 columns shown)*

</details>

### `WBN_DATABASE`.`ASSAYS`

- **Rows**: 396,422
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE_RECEIVED` — 1900-01-01 to 2026-07-27

<details><summary>36 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | no |
| 3 | `DATE_RECEIVED` | date | no |
| 4 | `DATE_ANALYSIS` | date | yes |
| 5 | `ASSAY_TYPE` | nvarchar(50) | no |
| 6 | `ASSAY_STATUS` | nvarchar(50) | yes |
| 7 | `ACTIVITY` | nvarchar(50) | no |
| 8 | `ORIGIN` | nvarchar(50) | yes |
| 9 | `DESTINATION` | nvarchar(50) | yes |
| 10 | `SAMPLE_ID` | nvarchar(50) | yes |
| 11 | `SAMPLE_JOB` | nvarchar(50) | yes |
| 12 | `STOCK_TYPE` | nvarchar(50) | no |
| 13 | `STOCK_ID` | nvarchar(50) | yes |
| 14 | `STOCK_SUBLOT` | int | yes |
| 15 | `RIT` | float | yes |
| 16 | `WMT` | float | yes |
| 17 | `Ni` | float | no |
| 18 | `Fe` | float | yes |
| 19 | `Co` | float | yes |
| 20 | `Al2O3` | float | yes |
| 21 | `CaO` | float | yes |
| 22 | `Cr2O3` | float | yes |
| 23 | `Fe2O3` | float | yes |
| 24 | `MnO` | float | yes |
| 25 | `P2O5` | float | yes |
| 26 | `SiO2` | float | yes |
| 27 | `MgO` | float | yes |
| 28 | `C` | float | yes |
| 29 | `P` | float | yes |
| 30 | `S` | float | yes |
| 31 | `K2O` | float | yes |
| 32 | `Na2O` | float | yes |
| 33 | `TiO2` | float | yes |
| 34 | `LOI` | float | yes |
| 35 | `MC` | float | yes |
| 36 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE_RECEIVED | DATE_ANALYSIS | ASSAY_TYPE | ASSAY_STATUS | ACTIVITY | ORIGIN | DESTINATION | SAMPLE_ID | SAMPLE_JOB | STOCK_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 505151 | WBN | 2025-01-16 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7387 | WBN.BB-611 | TOS |
| 505152 | WBN | 2025-01-17 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7388 | WBN.BB-612 | TOS |
| 505153 | WBN | 2025-01-17 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7389 | WBN.BB-612 | TOS |
| 505154 | WBN | 2025-01-17 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7390 | WBN.BB-612 | TOS |
| 505155 | WBN | 2025-01-17 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7391 | WBN.BB-612 | TOS |

*(first 12 of 36 columns shown)*

</details>

### `FMS_DB`.`FMS_PLAYBACK_STAY_DATA`

- **Rows**: 380,922
- **Flags**: col:COORD, col:EQUIP, col:SPEED, col:TIME
- **Date column**: `FETCH_DATE` — 2026-03-22 10:31:34 to 2026-07-27 18:49:42
- *redacted columns: checkDriverPhone, checkDriverName, carrierName, areaName, pointNames, driverNo, address, orgName, startAddress, driverId, classTypeName, eventTypeName, imei, driverName, endAddress*

<details><summary>43 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `id` | nvarchar(50) | no |
| 3 | `checkDriverPhone` 🔒 | nvarchar(255) | yes |
| 4 | `notes` | nvarchar(255) | yes |
| 5 | `precision` | float | yes |
| 6 | `videos` | nvarchar(255) | yes |
| 7 | `orgId` | float | yes |
| 8 | `speed` | float | yes |
| 9 | `checkDriverName` 🔒 | nvarchar(255) | yes |
| 10 | `endLat` | float | yes |
| 11 | `carrierName` 🔒 | nvarchar(255) | yes |
| 12 | `areaName` 🔒 | nvarchar(255) | yes |
| 13 | `endPrecision` | float | yes |
| 14 | `difftime` | float | yes |
| 15 | `pointNames` 🔒 | nvarchar(255) | yes |
| 16 | `startTime` | float | yes |
| 17 | `endLng` | float | yes |
| 18 | `driverNo` 🔒 | nvarchar(255) | yes |
| 19 | `lat` | float | yes |
| 20 | `limitSpeed` | nvarchar(255) | yes |
| 21 | `mileage` | float | yes |
| 22 | `truckId` | nvarchar(255) | yes |
| 23 | `imgs` | nvarchar(255) | yes |
| 24 | `address` 🔒 | nvarchar(255) | yes |
| 25 | `orgName` 🔒 | nvarchar(255) | yes |
| 26 | `lng` | float | yes |
| 27 | `startAddress` 🔒 | nvarchar(255) | yes |
| 28 | `updateTime` | float | yes |
| 29 | `eventType` | nvarchar(255) | yes |
| 30 | `maxSpeed` | float | yes |
| 31 | `plateNumber` | nvarchar(255) | yes |
| 32 | `markerType` | nvarchar(255) | yes |
| 33 | `driverId` 🔒 | nvarchar(255) | yes |
| 34 | `classTypeName` 🔒 | nvarchar(255) | yes |
| 35 | `createTime` | float | yes |
| 36 | `speedPercent` | nvarchar(255) | yes |
| 37 | `eventTypeName` 🔒 | nvarchar(255) | yes |
| 38 | `imei` 🔒 | nvarchar(255) | yes |
| 39 | `driverName` 🔒 | nvarchar(255) | yes |
| 40 | `endTime` | float | yes |
| 41 | `markerRemark` | nvarchar(255) | yes |
| 42 | `endAddress` 🔒 | nvarchar(255) | yes |
| 43 | `properties` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | id | checkDriverPhone | notes | precision | videos | orgId | speed | checkDriverName | endLat | carrierName | areaName |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-12 15:04:50.257000 | 107015291859999_10009_1778400933000 |  |  | -1.0 |  | 6.962944464209972e+18 | 0.0 |  | 0.48238 |  |  |
| 2026-05-12 15:04:50.257000 | 107015291859999_10009_1778401748000 |  |  | -1.0 |  | 6.962944464209972e+18 | 0.0 |  | 0.478615 |  |  |
| 2026-05-12 15:04:50.257000 | 107015291859999_10009_1778402895000 |  |  | -1.0 |  | 6.962944464209972e+18 | 0.0 |  | 0.479739 |  |  |
| 2026-05-12 15:04:50.257000 | 107015291859999_10009_1778403147000 |  |  | -1.0 |  | 6.962944464209972e+18 | 0.0 |  | 0.480212 |  |  |
| 2026-05-12 15:04:50.257000 | 107015291859999_10009_1778404760000 |  |  | -1.0 |  | 6.962944464209972e+18 | 0.0 |  | 0.482281 |  |  |

*(first 12 of 43 columns shown)*

</details>

### `WBN_DATABASE`.`PP_MINED_NEW_RECONCIL_MENG`

- **Rows**: 308,042
- **Flags**: none

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `YEAR` | float | yes |
| 3 | `MONTH` | float | yes |
| 4 | `WEEK` | float | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `X` | float | yes |
| 7 | `Y` | float | yes |
| 8 | `Z` | float | yes |
| 9 | `classification_no` | float | yes |
| 10 | `block_id` | nvarchar(255) | yes |
| 11 | `pp_mined_progress` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | YEAR | MONTH | WEEK | PIT | X | Y | Z | classification_no | block_id | pp_mined_progress |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025.0 | 1.0 | 4.0 | BLB | 384231.25 | 59381.25 | 713.0 | 1.0 | 711_B15_S119 | 0.46 |
| 2 | 2025.0 | 1.0 | 4.0 | BLB | 384231.25 | 59381.25 | 717.0 | 1.0 | 715_B15_S119 | 0.09 |
| 3 | 2025.0 | 1.0 | 4.0 | BLB | 384256.25 | 59381.25 | 713.0 | 1.0 | 711_B16_S119 | 0.47 |
| 4 | 2025.0 | 1.0 | 4.0 | BLB | 384281.25 | 59381.25 | 713.0 | 1.0 | 711_B17_S119 | 0.32 |
| 5 | 2025.0 | 1.0 | 4.0 | BLB | 384256.25 | 59381.25 | 717.0 | 1.0 | 715_B16_S119 | 0.45 |

</details>

### `FMS_DB`.`FMS_RISK_DATA`

- **Rows**: 306,611
- **Flags**: col:COORD, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `FETCH_DATE` — 2026-04-06 15:48:11 to 2026-07-27 18:31:05
- *redacted columns: checkDriverPhone, orgName, interveneTypeNames, checkDriverName, carrierName, riskLevelName, eventTypesName*

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `checkDriverPhone` 🔒 | nvarchar(255) | yes |
| 3 | `truckId` | nvarchar(255) | yes |
| 4 | `orgName` 🔒 | nvarchar(255) | yes |
| 5 | `riskLevel` | float | yes |
| 6 | `interveneTypeNames` 🔒 | nvarchar(255) | yes |
| 7 | `eventCount` | float | yes |
| 8 | `plateNumber` | nvarchar(255) | yes |
| 9 | `orgId` | nvarchar(255) | yes |
| 10 | `riskId` | nvarchar(255) | no |
| 11 | `checkDriverName` 🔒 | nvarchar(255) | yes |
| 12 | `carrierName` 🔒 | nvarchar(255) | yes |
| 13 | `createTime` | nvarchar(255) | yes |
| 14 | `startTime` | float | yes |
| 15 | `endTime` | float | yes |
| 16 | `riskLevelName` 🔒 | nvarchar(255) | yes |
| 17 | `eventTypesName` 🔒 | nvarchar(255) | yes |
| 18 | `mileage` | float | yes |
| 19 | `status` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | checkDriverPhone | truckId | orgName | riskLevel | interveneTypeNames | eventCount | plateNumber | orgId | riskId | checkDriverName | carrierName |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-06 15:57:10.257000 |  | 7103989736532085122 | [REDACTED] | 2.0 | [REDACTED] | 9.0 | N414 | 7190742966074476803 | 8728088746446818177 | [REDACTED] | [REDACTED] |
| 2026-04-06 15:57:10.257000 |  | 7909775461067260681 | [REDACTED] | 3.0 | [REDACTED] | 1.0 | SS124 | 7031941738457596167 | 8728088941465176071 | [REDACTED] | [REDACTED] |
| 2026-04-06 15:57:10.257000 |  | 6965079577748309384 | [REDACTED] | 2.0 | [REDACTED] | 2.0 | L951 | 7190741266106286983 | 8728089136215099393 | [REDACTED] | [REDACTED] |
| 2026-04-06 15:57:10.257000 |  | 7103991359861950854 | [REDACTED] | 2.0 | [REDACTED] | 2.0 | N340 | 7190744540448426241 | 8728089455384856584 | [REDACTED] | [REDACTED] |
| 2026-04-06 15:57:10.257000 |  | 7103989847228156289 | [REDACTED] | 2.0 | [REDACTED] | 1.0 | N346 | 7190744540448426241 | 8728089579636918274 | [REDACTED] | [REDACTED] |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`SAMPLE`

- **Rows**: 249,620
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 1900-01-02 00:00:00 to 2026-07-20 00:00:00

<details><summary>26 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CONTRACTOR` | nvarchar(50) | yes |
| 2 | `DATE` | datetime | no |
| 3 | `SHIFT` | float | yes |
| 4 | `SAMPLE_JOB` | nvarchar(50) | yes |
| 5 | `SAMPLE_ID` | nvarchar(50) | no |
| 6 | `SAMPLE_ID_ORI` | nvarchar(50) | yes |
| 7 | `BLOCK_ID` | nvarchar(50) | yes |
| 8 | `SAMPLE_COMPOSITE` | nvarchar(50) | yes |
| 9 | `SAMPLE_TYPE` | nvarchar(50) | yes |
| 10 | `SAMPLE_CONTRACTOR` | nvarchar(50) | yes |
| 11 | `ANALYSIS_TYPE` | nvarchar(50) | yes |
| 12 | `STOCK_AREA` | nvarchar(50) | yes |
| 13 | `STOCK_ID` | nvarchar(50) | no |
| 14 | `PREP_AREA` | nvarchar(50) | yes |
| 15 | `PREP_SPV` | nvarchar(50) | yes |
| 16 | `REPORTER` | nvarchar(50) | yes |
| 17 | `DATE_OUT` | datetime | yes |
| 18 | `MATERIAL` | nvarchar(50) | yes |
| 19 | `RIT` | float | yes |
| 20 | `TOTAL_KG` | float | yes |
| 21 | `ROCKY_KG` | float | yes |
| 22 | `EARTHY_KG` | float | yes |
| 23 | `GA_KG` | float | yes |
| 24 | `ORIGIN_BLOCK` | nvarchar(50) | yes |
| 25 | `SAMPLE_STATUS` | nvarchar(50) | yes |
| 26 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CONTRACTOR | DATE | SHIFT | SAMPLE_JOB | SAMPLE_ID | SAMPLE_ID_ORI | BLOCK_ID | SAMPLE_COMPOSITE | SAMPLE_TYPE | SAMPLE_CONTRACTOR | ANALYSIS_TYPE | STOCK_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  | 2021-02-13 00:00:00 |  |  | A | A |  |  | ORIGINAL |  |  |  |
|  | 2023-02-26 00:00:00 |  |  | AA.129.A | AA.129.A |  |  | ORIGINAL |  |  |  |
|  | 2021-02-13 00:00:00 |  |  | AA.4 | AA.4 |  |  | ORIGINAL |  |  |  |
|  | 2021-02-13 00:00:00 |  |  | AA.5 | AA.5 |  |  | ORIGINAL |  |  |  |
|  | 2021-02-13 00:00:00 |  |  | AA.6 | AA.6 |  |  | ORIGINAL |  |  |  |

*(first 12 of 26 columns shown)*

</details>

### `WBN_DATABASE`.`auto_edge_HAULAGE`

- **Rows**: 246,972
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2021-09-24 to 2026-07-26

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `graph_id_C7E0D1F64E9842258DB9B840FB41A4A5` | bigint | no |
| 2 | `$edge_id_66E9FA405A3E4BBB85210E85D05D1FB5` | nvarchar(1000) | no |
| 3 | `from_obj_id_CB360B2B9C494D959EB055C1A3A8C172` | int | no |
| 4 | `from_id_F62207485BA5405F970312413F9A2960` | bigint | no |
| 5 | `$from_id_6B4478C15D4A4DF3869F135421AEDD1E` | nvarchar(1000) | yes |
| 6 | `to_obj_id_C8DAED3DF52E4B5EBECB026E7E32933B` | int | no |
| 7 | `to_id_47F941D1B2CA46508D36C8AA495043C9` | bigint | no |
| 8 | `$to_id_4FBF9C508A514BB78FE8C09B6EEDA1D2` | nvarchar(1000) | yes |
| 9 | `HAULAGE_ID` | int | no |
| 10 | `DATE` | date | yes |
| 11 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| $edge_id_66E9FA405A3E4BBB85210E85D05D1FB5 | $from_id_6B4478C15D4A4DF3869F135421AEDD1E | $to_id_4FBF9C508A514BB78FE8C09B6EEDA1D2 | HAULAGE_ID | DATE | WMT |
|---|---|---|---|---|---|
| {"type":"edge","schema":"dbo","table":"auto_edge_HAULAGE"... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | 1 | 2025-11-24 | 150.0 |
| {"type":"edge","schema":"dbo","table":"auto_edge_HAULAGE"... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | 2 | 2025-02-16 | 300.0 |
| {"type":"edge","schema":"dbo","table":"auto_edge_HAULAGE"... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | 3 | 2025-10-14 | 564.0 |
| {"type":"edge","schema":"dbo","table":"auto_edge_HAULAGE"... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | 4 | 2025-10-17 | 2079.93 |
| {"type":"edge","schema":"dbo","table":"auto_edge_HAULAGE"... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | 5 | 2025-07-31 | 450.0 |

</details>

### `WBN_DATABASE`.`DISPATCH WBN ACTUAL`

- **Rows**: 212,890
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-22

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | no |
| 3 | `CONTRACTOR` | nvarchar(50) | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `TYPE DATA` | nvarchar(50) | yes |
| 6 | `TYPE HAULAGE` | nvarchar(50) | yes |
| 7 | `MATERIAL` | nvarchar(50) | yes |
| 8 | `COMPANY` | nvarchar(50) | yes |
| 9 | `DISPATCH ZONE` | nvarchar(50) | yes |
| 10 | `ORIGIN` | nvarchar(50) | yes |
| 11 | `DESTINATION` | nvarchar(50) | yes |
| 12 | `BUYER` | nvarchar(50) | yes |
| 13 | `NB DT` | float | yes |
| 14 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | SHIFT | TYPE DATA | TYPE HAULAGE | MATERIAL | COMPANY | DISPATCH ZONE | ORIGIN | DESTINATION | BUYER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 82931 | 2024-10-01 | STM | 1 | ACTUAL | DIRECT CRUSHER | CS | WBN | KR to FeNi | KR | FENI |  |
| 82932 | 2024-10-01 | STM | 1 | ACTUAL | DIRECT | SAP | WBN | KR to FeNi | KR | FENI |  |
| 82933 | 2024-10-01 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to CSTL | KR | EOS |  |
| 82934 | 2024-10-01 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to CSTL | KR | POS GOMDI |  |
| 82935 | 2024-10-01 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to KM 11 | KR | POS 6 |  |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`auto_node_STOCK_ID`

- **Rows**: 186,833
- **Flags**: col:STATUS, col:TIME
- **Date column**: `ASSAY_DATE` — 2021-02-20 to 2026-07-27

<details><summary>29 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `graph_id_83A179A0BB35432D89748AEC92C6DB3E` | bigint | no |
| 2 | `$node_id_B3C06F53460D452C8C24D2C646C0E52F` | nvarchar(1000) | no |
| 3 | `STOCK_ID` | nvarchar(100) | no |
| 4 | `STOCK_TYPE` | nvarchar(50) | yes |
| 5 | `STOCK_AREA` | nvarchar(50) | yes |
| 6 | `WMT_IN` | float | yes |
| 7 | `WMT_OUT` | float | yes |
| 8 | `ASSAY_TYPE` | nvarchar(50) | yes |
| 9 | `ASSAY_DATE` | date | yes |
| 10 | `ASSAY_STATUS` | nvarchar(50) | yes |
| 11 | `ASSAY_STATUS_%` | float | yes |
| 12 | `ASSAY_CONTRACTOR` | nvarchar(50) | yes |
| 13 | `WMT_CERT` | float | yes |
| 14 | `Al2O3` | float | yes |
| 15 | `CaO` | float | yes |
| 16 | `Co` | float | yes |
| 17 | `Cr2O3` | float | yes |
| 18 | `Fe_ORI` | float | yes |
| 19 | `Fe` | float | yes |
| 20 | `Fe2O3` | float | yes |
| 21 | `MC` | float | yes |
| 22 | `MgO_ORI` | float | yes |
| 23 | `MgO` | float | yes |
| 24 | `MnO` | float | yes |
| 25 | `Ni_ORI` | float | yes |
| 26 | `Ni` | float | yes |
| 27 | `P2O5` | float | yes |
| 28 | `SiO2_ORI` | float | yes |
| 29 | `SiO2` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| $node_id_B3C06F53460D452C8C24D2C646C0E52F | STOCK_ID | STOCK_TYPE | STOCK_AREA | WMT_IN | WMT_OUT | ASSAY_TYPE | ASSAY_DATE | ASSAY_STATUS | ASSAY_STATUS_% | ASSAY_CONTRACTOR | WMT_CERT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | - | TOS | BF_LD_TF_003 | 211055.0 |  |  |  |  |  |  |  |
| {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | A | POS | OLD EOS |  | 0.1 |  |  |  |  |  |  |
| {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | A.2573 | TOS | TOSKR6 |  | 5640.129999999999 |  |  |  |  |  |  |
| {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | A.2801 | TOS | TOS_KR |  | 2260.7200000000003 |  |  |  |  |  |  |
| {"type":"node","schema":"dbo","table":"auto_node_STOCK_ID... | A.2806 | TOS | TOS_KR_STM_01 |  | 3597.8399999999992 |  |  |  |  |  |  |

*(first 12 of 29 columns shown)*

</details>

### `WBN_DATABASE`.`POS FOLLOW UP`

- **Rows**: 177,581
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-29

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `AREA` | nvarchar(50) | yes |
| 4 | `POS` | nvarchar(50) | yes |
| 5 | `PADS` | nvarchar(50) | yes |
| 6 | `NUMBER` | int | yes |
| 7 | `AVG` | float | yes |
| 8 | `EDD` | date | yes |
| 9 | `PRECISION` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | AREA | POS | PADS | NUMBER | AVG | EDD | PRECISION |
|---|---|---|---|---|---|---|---|---|
| 31062 | 2024-10-01 | KR | POS 6 | EXISTING | 38 | 20000.0 |  |  |
| 31063 | 2024-10-01 | KR | POS 6 | FREE | 17 | 20000.0 |  |  |
| 31064 | 2024-10-01 | KR | POS 6 | ON PRGS MTN | 0 | 20000.0 |  |  |
| 31065 | 2024-10-01 | KR | POS 6 | NEED MTN | 3 | 20000.0 |  |  |
| 31066 | 2024-10-01 | KR | POS 6 | CONTRUCTION PAD | 0 | 20000.0 |  |  |

</details>

### `WBN_DATABASE`.`autoQC_CF_BM_TOS_HISTORY_OLD`

- **Rows**: 175,475
- **Flags**: col:TIME

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATETIME` | nvarchar(50) | yes |
| 2 | `YEAR` | int | no |
| 3 | `MONTH` | int | no |
| 4 | `ORIGIN_PIT` | nvarchar(50) | no |
| 5 | `CONTRACTOR_PILE` | nvarchar(50) | no |
| 6 | `MATERIAL` | nvarchar(50) | no |
| 7 | `DIL_BM_MC` | float | yes |
| 8 | `DIL_BM_Ni` | float | yes |
| 9 | `DIL_BM_Fe` | float | yes |
| 10 | `DIL_BM_SiO2` | float | yes |
| 11 | `DIL_BM_MgO` | float | yes |
| 12 | `DIL_TOS_MC` | float | yes |
| 13 | `DIL_TOS_Ni` | float | yes |
| 14 | `DIL_TOS_Fe` | float | yes |
| 15 | `DIL_TOS_SiO2` | float | yes |
| 16 | `DIL_TOS_MgO` | float | yes |
| 17 | `DIL_PROP_BM_Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATETIME | YEAR | MONTH | ORIGIN_PIT | CONTRACTOR_PILE | MATERIAL | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_TOS_MC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-23 10:30:40 | 2024 | 6 | BLB | RIM | LIM | 0.9983768393603151 | 0.9251471825063079 | 1.3830479080858444 | 11.013147718484147 | 21.119402985074625 | 1.0082512897816895 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | HJS | LIM | 0.9354435609367776 | 0.8687153017564758 | 0.9571238191533088 | 1.042450830928737 | 1.3608734215534042 | 0.967275805356717 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | HJS | SAP | 0.9677435521817048 | 0.8621670128898355 | 1.0624823833859447 | 0.96067984565804 | 1.0157900996796756 | 0.9186474545061462 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | RIM | LIM | 0.9234836138428508 | 0.8835811610362659 | 0.9098123139272393 | 1.2966134512579501 | 2.0834818094490846 | 0.959861180659299 |
| 2026-05-23 10:30:40 | 2024 | 7 | CBB | RIM | LIM | 0.9114671346021906 | 0.8896435893031549 | 0.8879047407447697 | 1.4266462083650957 | 2.8993479851973314 | 0.95068323083167 |

*(first 12 of 17 columns shown)*

</details>

### `WBN_DATABASE`.`CRUSHER_STOCKPILE_OUTPUT_DATA`

- **Rows**: 156,726
- **Flags**: col:EQUIP, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-06-04 00:00:00

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | nvarchar(50) | yes |
| 4 | `CONTRACTOR_HAULING` | nvarchar(50) | yes |
| 5 | `UNIT_ID_HAULER` | nvarchar(50) | yes |
| 6 | `STOCK_ID` | nvarchar(50) | yes |
| 7 | `ORIGIN` | nvarchar(50) | yes |
| 8 | `DESTINATION` | nvarchar(50) | yes |
| 9 | `DESTINATION 2` | nvarchar(50) | yes |
| 10 | `RIT` | float | yes |
| 11 | `TF` | float | yes |
| 12 | `BCM` | float | yes |
| 13 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR_HAULING | UNIT_ID_HAULER | STOCK_ID | ORIGIN | DESTINATION | DESTINATION 2 | RIT | TF | BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 189541 | 2026-04-29 00:00:00 | 1 | PPP | 421 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |
| 189542 | 2026-04-29 00:00:00 | 1 | PPP | 424 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |
| 189543 | 2026-04-29 00:00:00 | 1 | PPP | 427 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |
| 189544 | 2026-04-29 00:00:00 | 1 | PPP | 428 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |
| 189545 | 2026-04-29 00:00:00 | 1 | PPP | 429 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |

*(first 12 of 13 columns shown)*

</details>

### `WBN_DATABASE`.`QC PIT-TOS OMR`

- **Rows**: 149,360
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-07-17 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | float | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `MATERIAL` | nvarchar(255) | yes |
| 6 | `PIT` | nvarchar(255) | yes |
| 7 | `SUBPIT` | nvarchar(255) | yes |
| 8 | `BLOCK_ID` | nvarchar(255) | yes |
| 9 | `BLOCK_STATUS` | nvarchar(255) | yes |
| 10 | `TOS_LOCATION` | nvarchar(255) | yes |
| 11 | `PILE_ID` | nvarchar(255) | yes |
| 12 | `PILE_STATUS` | nvarchar(255) | yes |
| 13 | `TF` | float | yes |
| 14 | `RIT` | float | yes |
| 15 | `WMT` | float | yes |
| 16 | `BATCH` | nvarchar(255) | yes |
| 17 | `TYPE` | nvarchar(255) | yes |
| 18 | `BLAST` | nvarchar(255) | yes |
| 19 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | MATERIAL | PIT | SUBPIT | BLOCK_ID | BLOCK_STATUS | TOS_LOCATION | PILE_ID | PILE_STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 109692 | 2024-10-01 00:00:00 | 1.0 | HJS | SAP | CBB | CBBT1 | 433_B93_S175 | CONTINUE | TOS_CBB_18 | BB.D.1841 | CONTINUE |
| 109693 | 2024-10-01 00:00:00 | 1.0 | HJS | SAP | CBB | CBBB1 | 439_B99_S176 | CLOSE | TOS_CBB_RIM_13 | BB.D.1846 | CONTINUE |
| 109694 | 2024-10-01 00:00:00 | 1.0 | HJS | SAP | CBB | CBBB1 | 337_B62_S279 | CONTINUE | TOS_CBB_RIM_13 | BB.D.1847 | CONTINUE |
| 109695 | 2024-10-01 00:00:00 | 1.0 | HJS | SAP | CBB | CBBBT1 | 439_B100_S175 | CONTINUE | TOS_CBB_RIM_01 | BB.D.1848 | CONTINUE |
| 109696 | 2024-10-01 00:00:00 | 1.0 | HJS | SAP | CBB | CBBBT1 | 443_B101_S176 | CONTINUE | TOS_CBB_RIM_01 | BB.D.1848 | CONTINUE |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`autoBLOCK_PROD_QC_BM_TOS_CORR`

- **Rows**: 131,692
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-12-29 00:00:00 to 2026-07-26 00:00:00
- *redacted columns: OBJECT_NAME*

<details><summary>18 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `OBJECT_NAME` 🔒 | varchar(17) | no |
| 2 | `DATE` | datetime | no |
| 3 | `SURVEY_CLASS` | nvarchar(255) | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | no |
| 5 | `ACTIVITY` | nvarchar(255) | no |
| 6 | `MATERIAL` | nvarchar(255) | yes |
| 7 | `STOCK_POINT` | varchar(11) | no |
| 8 | `STOCK_TYPE` | nvarchar(50) | yes |
| 9 | `STOCK_AREA` | nvarchar(255) | yes |
| 10 | `STOCK_ID` | nvarchar(510) | yes |
| 11 | `ORIGIN_AREA` | nvarchar(255) | no |
| 12 | `ORIGIN_ID` | nvarchar(max) | yes |
| 13 | `DESTINATION_ID` | nvarchar(510) | yes |
| 14 | `RIT` | float | yes |
| 15 | `WMT` | float | yes |
| 16 | `WMT_METHOD` | varchar(2) | no |
| 17 | `SURVEY_TYPE` | int | yes |
| 18 | `SURVEY_WEEK` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| OBJECT_NAME | DATE | SURVEY_CLASS | CONTRACTOR | ACTIVITY | MATERIAL | STOCK_POINT | STOCK_TYPE | STOCK_AREA | STOCK_ID | ORIGIN_AREA | ORIGIN_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [REDACTED] | 2026-01-22 00:00:00 | WST | STM | MINING | WST | DESTINATION | WD | ROCKWALL_WD_TF9 | ROCKWALL_WD_TF9 | TF |  |
| [REDACTED] | 2026-02-08 00:00:00 | WST | RIM | LAMINATING | WST | DESTINATION | WD | WD_BLB_08 | WD_BLB_08 | BLB |  |
| [REDACTED] | 2026-02-11 00:00:00 | WST | RIM | MINING | WST | DESTINATION | WD | ROCKWALL_WD_BLB_08 | ROCKWALL_WD_BLB_08 | BLB |  |
| [REDACTED] | 2026-02-11 00:00:00 | WST | RIM | LAMINATING | WST | DESTINATION | WD | WD_BLB_08 | WD_BLB_08 | BLB |  |
| [REDACTED] | 2026-02-13 00:00:00 | WST | RIM | LAMINATING | WST | DESTINATION | WD | WD_BLB_08 | WD_BLB_08 | BLB |  |

*(first 12 of 18 columns shown)*

</details>

### `WBN_DATABASE`.`CONTRACTOR FOLLOW UP`

- **Rows**: 130,557
- **Flags**: col:EQUIP, col:STATUS, col:TIME
- **Date column**: `Date` — 2024-10-01 to 2026-07-26

<details><summary>25 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `Date` | date | no |
| 3 | `Contractor` | nvarchar(255) | yes |
| 4 | `Activity` | nvarchar(255) | yes |
| 5 | `Equipment` | nvarchar(255) | yes |
| 6 | `Brand` | nvarchar(255) | yes |
| 7 | `Model` | nvarchar(255) | yes |
| 8 | `Capacity` | nvarchar(255) | yes |
| 9 | `Quantity` | float | yes |
| 10 | `PA` | float | yes |
| 11 | `Target Fleet` | float | yes |
| 12 | `RFU` | float | yes |
| 13 | `Breakdown` | float | yes |
| 14 | `Act PA` | float | yes |
| 15 | `Running Average` | float | yes |
| 16 | `Stand by` | float | yes |
| 17 | `Actual Utilization` | float | yes |
| 18 | `Manpower Factor` | float | yes |
| 19 | `Manpower Budget` | float | yes |
| 20 | `Manpower` | float | yes |
| 21 | `Manpower On Site` | float | yes |
| 22 | `Hiring` | float | yes |
| 23 | `Eq class` | nvarchar(255) | yes |
| 24 | `DT Reclaiming` | float | yes |
| 25 | `DT OTHER` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | Date | Contractor | Activity | Equipment | Brand | Model | Capacity | Quantity | PA | Target Fleet | RFU |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 82044 | 2024-10-01 | CKB | HAULING | DT Sachman | Shacman | X3000 | 43 | 30.0 | 0.85 | 26.0 | 19.0 |
| 82045 | 2024-10-01 | CKB | HAULING | Exca 30 Ton | Cat | CAT 330 | 30 | 1.0 | 0.9 | 1.0 | 1.0 |
| 82046 | 2024-10-01 | CKB | HAULING | Exca 20 Ton | Sany | SY215C | 20 | 1.0 | 0.9 | 1.0 | 1.0 |
| 82047 | 2024-10-01 | GMG  | HAULING | DT Hino 25T | HINO | FM 280JD | 25 | 35.0 | 0.89 | 32.0 | 18.0 |
| 82048 | 2024-10-01 | GMG  | HAULING | DT Volvo 30T | VOLVO | VOLVO 6 X 4 | 30 | 67.0 | 0.9 | 61.0 | 49.0 |

*(first 12 of 25 columns shown)*

</details>

### `WBN_DATABASE`.`FeNi Reclaiming Plan`

- **Rows**: 127,339
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-27

<details><summary>10 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `ORE LOCATION` | nvarchar(50) | yes |
| 5 | `DOME ID FENI` | nvarchar(50) | yes |
| 6 | `PLAN VEHICULE` | int | yes |
| 7 | `PLANNED WEIGHBRIDGE` | nvarchar(50) | no |
| 8 | `PLANNED WMT` | float | yes |
| 9 | `DESTINATION` | nvarchar(50) | yes |
| 10 | `DOME` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | ORE LOCATION | DOME ID FENI | PLAN VEHICULE | PLANNED WEIGHBRIDGE | PLANNED WMT | DESTINATION | DOME |
|---|---|---|---|---|---|---|---|---|---|
| 49759 | 2024-10-01 | 1 | POS 14 | ADM.227 | 8 | 11#磅 | 1500.0 |  |  |
| 49760 | 2024-10-01 | 1 | POS10 | AA.477 | 8 | 11#磅 | 1500.0 |  |  |
| 49761 | 2024-10-01 | 1 | 5号码头泊位待定 | RN063 | 6 | 1#磅 | 0.0 |  |  |
| 49762 | 2024-10-01 | 1 | POS12 | AD.202 | 8 | 11#磅 | 1300.0 |  |  |
| 49763 | 2024-10-01 | 1 | POS 14 | ADM.227 | 8 | 11#磅 | 1500.0 |  |  |

</details>

### `WBN_DATABASE`.`MINING_PLAN_WEEKLY`

- **Rows**: 124,358
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2025-02-08 00:00:00 to 2026-05-01 00:00:00

<details><summary>34 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `YEAR` | float | yes |
| 2 | `MONTH` | float | yes |
| 3 | `WEEK` | float | yes |
| 4 | `DATE` | datetime | no |
| 5 | `CONTRACTOR` | nvarchar(255) | yes |
| 6 | `PIT` | nvarchar(255) | yes |
| 7 | `SUBPIT` | nvarchar(255) | yes |
| 8 | `MATERIAL` | nvarchar(255) | yes |
| 9 | `FSAP_RSAP` | nvarchar(255) | yes |
| 10 | `CATEGORY` | nvarchar(255) | yes |
| 11 | `BLOCK_ID` | nvarchar(255) | yes |
| 12 | `BCM` | float | yes |
| 13 | `WMT` | float | yes |
| 14 | `DMT` | float | yes |
| 15 | `Ni` | float | yes |
| 16 | `Fe` | float | yes |
| 17 | `SM` | float | yes |
| 18 | `SiO2` | float | yes |
| 19 | `MgO` | float | yes |
| 20 | `H2O` | float | yes |
| 21 | `MINE_RECOVERY` | float | yes |
| 22 | `WMT_REC` | float | yes |
| 23 | `BCM_ROM` | float | yes |
| 24 | `WMT_ROM` | float | yes |
| 25 | `DMT_ROM` | float | yes |
| 26 | `Ni_DILUTION` | float | yes |
| 27 | `Fe_DILUTION` | float | yes |
| 28 | `MgO_DILUTION` | float | yes |
| 29 | `H2O_DILUTION` | float | yes |
| 30 | `Ni_ROM` | float | yes |
| 31 | `Fe_ROM` | float | yes |
| 32 | `MgO_ROM` | float | yes |
| 33 | `H2O_ROM` | float | yes |
| 34 | `ID` | int | no |

</details>

<details><summary>Sample rows (5)</summary>

| YEAR | MONTH | WEEK | DATE | CONTRACTOR | PIT | SUBPIT | MATERIAL | FSAP_RSAP | CATEGORY | BLOCK_ID | BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026.0 | 2.0 | 5.0 | 2026-02-02 00:00:00 | RIM | BLB | 10 | LIM | WST | LIM ORE | N943_B341_S213 | 611.572 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02 00:00:00 | RIM | BLB | 10 | LIM | WST | LIM ORE | N943_B341_S212 | 324.707 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02 00:00:00 | RIM | BLB | 10 | WST | WST | WST LIM | N943_B341_S211 | 13.428 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02 00:00:00 | RIM | BLB | 10 | WST | WST | WST LIM | N943_B341_S209 | 197.754 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02 00:00:00 | RIM | BLB | 10 | WST | WST | WST SAP | N943_B341_S208 | 345.459 |

*(first 12 of 34 columns shown)*

</details>

### `WBN_DATABASE`.`SAMPLING_CONTRACTOR`

- **Rows**: 123,130
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-07-25 00:00:00

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `SHIFT` | nvarchar(50) | yes |
| 5 | `ACTIVITY` | nvarchar(50) | yes |
| 6 | `ORIGIN_AREA` | nvarchar(50) | yes |
| 7 | `ORIGIN_ID` | nvarchar(50) | yes |
| 8 | `DESTINATION_AREA` | nvarchar(50) | yes |
| 9 | `DESTINATION_ID` | nvarchar(50) | yes |
| 10 | `CONTRACTOR_HAULING` | nvarchar(50) | yes |
| 11 | `RIT` | float | yes |
| 12 | `SPV_CONTRACTOR` | nvarchar(50) | yes |
| 13 | `SPV_WBN` | nvarchar(50) | yes |
| 14 | `SAMPLING_POINT` | nvarchar(50) | yes |
| 15 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | ACTIVITY | ORIGIN_AREA | ORIGIN_ID | DESTINATION_AREA | DESTINATION_ID | CONTRACTOR_HAULING | RIT | SPV_CONTRACTOR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TBI | 2024-12-26 00:00:00 | 1 | RECLAIMING | POS CSW | LGS.BLB45 | POS CSW |  | FENI | 50.0 | SOLY EKA PUTRA |
| 2 | TBI | 2024-12-26 00:00:00 | 1 | RECLAIMING | POS CSW | ABM.258 | POS CSW |  | FENI | 40.0 | SOLY EKA PUTRA |
| 3 | TBI | 2024-12-26 00:00:00 | 1 | RECLAIMING | POS CSW | ABM.255 | POS CSW |  | FENI | 13.0 | SOLY EKA PUTRA |
| 4 | TBI | 2024-12-26 00:00:00 | 2 | RECLAIMING | POS CSW | ABM.258 | FENI K |  | FENI | 24.0 | SOLY EKA PUTRA |
| 5 | TBI | 2024-12-26 00:00:00 | 2 | RECLAIMING | POS CSW | ABM.255 | FENI R |  | FENI | 8.0 | SOLY EKA PUTRA |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`TOS_PILE_INFO`

- **Rows**: 97,738
- **Flags**: none

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `TOS_PILE` | nvarchar(50) | yes |
| 3 | `TOS` | nvarchar(50) | yes |
| 4 | `PIT` | nvarchar(50) | yes |
| 5 | `CONTRACTOR_PROD` | nvarchar(50) | yes |
| 6 | `MATERIAL_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | TOS_PILE | TOS | PIT | CONTRACTOR_PROD | MATERIAL_TYPE |
|---|---|---|---|---|---|
| 1 | A.1 | Grizzly 332 | KR | STM | GRIZZLY |
| 2 | A.2 | Grizzly 332 | KR | STM | GRIZZLY |
| 3 | A.3 | Grizzly 332 | KR | STM | GRIZZLY |
| 4 | A.4 | Grizzly 332 | KR | STM | GRIZZLY |
| 5 | A.5 | Grizzly 332 | KR | STM | GRIZZLY |

</details>

### `WBN_DATABASE`.`autoQC_STOCK_ALL_VIA_ALL`

- **Rows**: 93,116
- **Flags**: col:STATUS, col:TIME
- **Date column**: `TOS_ASSAY_DATE` — 2021-10-17 to 2026-07-21

<details><summary>93 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | nvarchar(50) | no |
| 2 | `STOCK_TYPE` | nvarchar(50) | no |
| 3 | `STOCK_ID` | nvarchar(260) | no |
| 4 | `Ni_` | float | yes |
| 5 | `PLAN_MC` | float | yes |
| 6 | `PLAN_Ni` | float | yes |
| 7 | `PLAN_Fe` | float | yes |
| 8 | `PLAN_SiO2` | float | yes |
| 9 | `PLAN_MgO` | float | yes |
| 10 | `PLAN_Co` | float | yes |
| 11 | `PLAN_Cr2O3` | float | yes |
| 12 | `CF_PLAN_Ni` | float | yes |
| 13 | `DEF_ASSAY_TYPE` | nvarchar(101) | yes |
| 14 | `DEF_MC` | float | yes |
| 15 | `DEF_Ni` | float | yes |
| 16 | `DEF_Fe` | float | yes |
| 17 | `DEF_SiO2` | float | yes |
| 18 | `DEF_MgO` | float | yes |
| 19 | `DEF_Al2O3` | float | yes |
| 20 | `DEF_Co` | float | yes |
| 21 | `DEF_Cr2O3` | float | yes |
| 22 | `DEF_MnO` | float | yes |
| 23 | `DEF_P2O5` | float | yes |
| 24 | `BM_ASSAY_TYPE` | nvarchar(101) | yes |
| 25 | `BM_MC` | float | yes |
| 26 | `BM_Ni` | float | yes |
| 27 | `BM_Fe` | float | yes |
| 28 | `BM_SiO2` | float | yes |
| 29 | `BM_MgO` | float | yes |
| 30 | `BM_Al2O3` | float | yes |
| 31 | `BM_Co` | float | yes |
| 32 | `BM_Cr2O3` | float | yes |
| 33 | `BM_MnO` | float | yes |
| 34 | `BM_P2O5` | float | yes |
| 35 | `BM_Ni_CORR` | float | yes |
| 36 | `BM_Fe_CORR` | float | yes |
| 37 | `BM_SiO2_CORR` | float | yes |
| 38 | `BM_MgO_CORR` | float | yes |
| 39 | `TOS_ASSAY_TYPE` | nvarchar(101) | yes |
| 40 | `TOS_ASSAY_DATE` | date | yes |
| 41 | `TOS_MC` | float | yes |
| 42 | `TOS_Ni` | float | yes |
| 43 | `TOS_Fe` | float | yes |
| 44 | `TOS_SiO2` | float | yes |
| 45 | `TOS_MgO` | float | yes |
| 46 | `TOS_Al2O3` | float | yes |
| 47 | `TOS_Co` | float | yes |
| 48 | `TOS_Cr2O3` | float | yes |
| 49 | `TOS_MnO` | float | yes |
| 50 | `TOS_P2O5` | float | yes |
| 51 | `POS_ASSAY_TYPE` | nvarchar(101) | yes |
| 52 | `POS_ASSAY_STATUS` | varchar(8) | yes |
| 53 | `POS_ASSAY_STATUS_%` | float | yes |
| 54 | `POS_ASSAY_CONTRACTOR` | nvarchar(50) | yes |
| 55 | `POS_ASSAY_DATE` | date | yes |
| 56 | `POS_WMT_CERT` | float | yes |
| 57 | `POS_MC` | float | yes |
| 58 | `POS_Ni` | float | yes |
| 59 | `POS_Fe` | float | yes |
| 60 | `POS_SiO2` | float | yes |
| 61 | `POS_MgO` | float | yes |
| 62 | `POS_Al2O3` | float | yes |
| 63 | `POS_Co` | float | yes |
| 64 | `POS_Cr2O3` | float | yes |
| 65 | `POS_MnO` | float | yes |
| 66 | `POS_P2O5` | float | yes |
| 67 | `YARD_ASSAY_TYPE` | nvarchar(101) | yes |
| 68 | `YARD_ASSAY_STATUS` | varchar(8) | yes |
| 69 | `YARD_ASSAY_STATUS_%` | float | yes |
| 70 | `YARD_ASSAY_CONTRACTOR` | nvarchar(50) | yes |
| 71 | `YARD_ASSAY_DATE` | date | yes |
| 72 | `YARD_WMT_CERT` | float | yes |
| 73 | `YARD_MC` | float | yes |
| 74 | `YARD_Ni` | float | yes |
| 75 | `YARD_Fe` | float | yes |
| 76 | `YARD_SiO2` | float | yes |
| 77 | `YARD_MgO` | float | yes |
| 78 | `YARD_Al2O3` | float | yes |
| 79 | `YARD_Co` | float | yes |
| 80 | `YARD_Cr2O3` | float | yes |
| 81 | `YARD_MnO` | float | yes |
| 82 | `YARD_P2O5` | float | yes |
| 83 | `ML_Ni` | float | yes |
| 84 | `DIL_BM_MC` | float | yes |
| 85 | `DIL_BM_Ni` | float | yes |
| 86 | `DIL_BM_Fe` | float | yes |
| 87 | `DIL_BM_SiO2` | float | yes |
| 88 | `DIL_BM_MgO` | float | yes |
| 89 | `DIL_TOS_MC` | float | yes |
| 90 | `DIL_TOS_Ni` | float | yes |
| 91 | `DIL_TOS_Fe` | float | yes |
| 92 | `DIL_TOS_SiO2` | float | yes |
| 93 | `DIL_TOS_MgO` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | STOCK_TYPE | STOCK_ID | Ni_ | PLAN_MC | PLAN_Ni | PLAN_Fe | PLAN_SiO2 | PLAN_MgO | PLAN_Co | PLAN_Cr2O3 | CF_PLAN_Ni |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-27 16:00:29 | TOS | - |  |  |  |  |  |  |  |  |  |
| 2026-07-27 16:00:29 | POS | A |  |  |  |  |  |  |  |  |  |
| 2026-07-27 16:00:29 | TOS | A.2573 |  |  |  |  |  |  |  |  |  |
| 2026-07-27 16:00:29 | TOS | A.2801 |  |  |  |  |  |  |  |  |  |
| 2026-07-27 16:00:29 | TOS | A.2806 |  |  |  |  |  |  |  |  |  |

*(first 12 of 93 columns shown)*

</details>

### `WBN_DATABASE`.`TOS FOLLOW`

- **Rows**: 87,045
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-07-22 00:00:00

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `ORIGIN` | nvarchar(255) | yes |
| 3 | `MATERIAL` | nvarchar(255) | yes |
| 4 | `BLOCK ID` | nvarchar(255) | yes |
| 5 | `TOS` | nvarchar(255) | yes |
| 6 | `POS DOME` | nvarchar(255) | yes |
| 7 | `POS` | nvarchar(255) | yes |
| 8 | `TRIPS` | float | yes |
| 9 | `WMT` | float | yes |
| 10 | `STATUS` | nvarchar(255) | yes |
| 11 | `CONTRACTOR` | nvarchar(255) | yes |
| 12 | `DATE` | datetime | yes |
| 13 | `SHIFT` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | ORIGIN | MATERIAL | BLOCK ID | TOS | POS DOME | POS | TRIPS | WMT | STATUS | CONTRACTOR | DATE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5605 | TF | SAP | TF.C.637 | TOS_TF_MTM_02 | ADM.233 | POS 12 EXT | 23.0 | 1162.14 | Continue | CKB | 2024-10-01 00:00:00 |
| 5606 | TF | SAP | TF.C.611 | TOS_TF_MTM_02 | ABM.224 | POS 12 | 21.0 | 1089.0700000000002 | Continue | CKB | 2024-10-01 00:00:00 |
| 5607 | KR | SAP | A.5751 | TOS_KR_STM_04 | AA.483 | POS 10 | 47.0 | 1631.06 | CLOSE | GMG | 2024-10-01 00:00:00 |
| 5608 | KR | SAP | A.5752 | TOS_KR_STM_05 EXT | AAM.296 | POS 11 | 52.0 | 1806.12 | CONTINUE | GMG | 2024-10-01 00:00:00 |
| 5609 | KR | SAP | A.5748 | TOS_KR_10 | AA.483 | POS 10 | 20.0 | 659.5 | CONTINUE | GMG | 2024-10-01 00:00:00 |

*(first 12 of 13 columns shown)*

</details>

### `WBN_DATABASE`.`OMR_QC`

- **Rows**: 85,995
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-22

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `CONTRACTOR_HAUL` | nvarchar(255) | yes |
| 5 | `MATERIAL` | nvarchar(255) | yes |
| 6 | `TOS_PILE` | nvarchar(255) | yes |
| 7 | `TOS` | nvarchar(255) | yes |
| 8 | `RIT` | float | yes |
| 9 | `TF` | float | yes |
| 10 | `DOME` | nvarchar(255) | yes |
| 11 | `POS/PLANT` | nvarchar(255) | yes |
| 12 | `STATUS` | nvarchar(255) | yes |
| 13 | `CONTRACTOR_PROD` | nvarchar(50) | yes |
| 14 | `PIT` | nvarchar(50) | yes |
| 15 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR_HAUL | MATERIAL | TOS_PILE | TOS | RIT | TF | DOME | POS/PLANT | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 134349 | 2024-10-01 | 1 | HJS | SAP | BB.D.1719 | TOS_CBB_RIM_13 | 19.0 |  | LGS.CBB194 | POS UNI-UNI | CLOSE |
| 134350 | 2024-10-01 | 1 | HJS | SAP | BB.D.1719 | TOS_CBB_RIM_13 | 29.0 |  | LGS.CBB197 | POS UNI-UNI | CLOSE |
| 134351 | 2024-10-01 | 1 | HJS | SAP | BB.D.1657 | TOS_CBB_RIM_13 | 28.0 |  | LGS.CBB197 | POS UNI-UNI | CLOSE |
| 134352 | 2024-10-01 | 1 | HJS | SAP | BB.D.1782 | TOS_CBB_RIM_01 | 23.0 |  | LGS.CBB195 | POS BIRI-BIRI | CLOSE |
| 134353 | 2024-10-01 | 1 | HJS | SAP | BB.D.1749 | TOS_CBB_RIM_01 | 64.0 |  | LGS.CBB195 | POS BIRI-BIRI | CONTINUE |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`DISPATCH FeNi PLAN & ACTUAL`

- **Rows**: 84,040
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-27

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `TYPE` | nvarchar(50) | yes |
| 5 | `POS` | nvarchar(50) | yes |
| 6 | `DESTINATON` | nvarchar(50) | yes |
| 7 | `NB DOMES` | int | yes |
| 8 | `NB DT` | int | yes |
| 9 | `TRIPS` | float | yes |
| 10 | `TF` | float | yes |
| 11 | `WMT ACT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | TYPE | POS | DESTINATON | NB DOMES | NB DT | TRIPS | TF | WMT ACT |
|---|---|---|---|---|---|---|---|---|---|---|
| 15178 |  | 1 | ACTUAL | POS.11 | 15KM | 0 | 0 |  | 40.0 |  |
| 15195 |  | 2 | ACTUAL | Tekindo | 0KM | 1 | 9 |  | 40.0 |  |
| 25052 | 2024-10-01 | 1 | PLAN | 海港特码头 | 0KM | 20 | 120 | 3.76795580110497 | 40.0 |  |
| 25053 | 2024-10-01 | 1 | PLAN | EOS码头 | 0KM | 0 | 0 | 0.0 | 40.0 |  |
| 25054 | 2024-10-01 | 1 | PLAN | 友山码头 | 0KM | 10 | 88 | 4.70408163265306 | 40.0 |  |

</details>

### `WBN_DATABASE`.`DISTANCE_MINING`

- **Rows**: 83,462
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-02-25 00:00:00 to 2025-09-27 00:00:00

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `DIGGER` | nvarchar(255) | yes |
| 7 | `BLOCK_ID` | nvarchar(255) | yes |
| 8 | `MATERIAL` | nvarchar(255) | yes |
| 9 | `MATERIAL2` | nvarchar(255) | yes |
| 10 | `DUMPING_AREA` | nvarchar(255) | yes |
| 11 | `RIT` | float | yes |
| 12 | `DISTANCE` | float | yes |
| 13 | `WMT` | float | yes |
| 14 | `BCM` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | SHIFT | PIT | DIGGER | BLOCK_ID | MATERIAL | MATERIAL2 | DUMPING_AREA | RIT | DISTANCE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_04 | 20.0 | 1100.0 |
| 2 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 28.0 | 700.0 |
| 3 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | LIM |  | LD_TF_04 | 26.0 | 1000.0 |
| 4 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | TS |  | TEMP_SD_TF_SMA_01 | 2.0 | 1400.0 |
| 5 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 35.0 | 700.0 |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`DAILY_QUALITY_DISPATCH`

- **Rows**: 66,774
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-02-27 to 2026-07-22

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | float | yes |
| 4 | `PIT` | nvarchar(50) | yes |
| 5 | `CONTRACTOR` | nvarchar(50) | yes |
| 6 | `TOS_PILE` | nvarchar(50) | yes |
| 7 | `CATEGORY` | nvarchar(50) | yes |
| 8 | `CATEGORY_2` | nvarchar(50) | yes |
| 9 | `WMT` | float | yes |
| 10 | `Ni_TOS` | float | yes |
| 11 | `Ni_BM` | float | yes |
| 12 | `Ni_Plan` | float | yes |
| 13 | `DOME` | nvarchar(50) | yes |
| 14 | `DESTINATION` | nvarchar(50) | yes |
| 15 | `STATUS` | nvarchar(50) | yes |
| 16 | `EXCA` | nvarchar(50) | yes |
| 17 | `DT` | float | yes |
| 18 | `HAUL_CONFIDENCE` | nvarchar(50) | yes |
| 19 | `TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | PIT | CONTRACTOR | TOS_PILE | CATEGORY | CATEGORY_2 | WMT | Ni_TOS | Ni_BM | Ni_Plan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-02-27 | 2.0 | KR | RIM | KR.CS.78 | CS | CS | 200.0 | 0.6 | 0.6 | 0.6 |
| 2 | 2025-02-27 | 2.0 | KR | RIM | KR.CS.79 | CS | CS | 800.0 | 0.6 | 0.6 | 0.6 |
| 3 | 2025-02-27 | 2.0 | KR | PPP | KR.I.1440 |  |  | 300.0 | 1.59 | 0.87 | 1.05 |
| 4 | 2025-02-27 | 2.0 | KR | PPP | KR.I.1459 |  |  | 450.0 | 1.56 | 1.38 | 1.4249999999999998 |
| 5 | 2025-02-27 | 2.0 | KR | RIM | KR. I.1555 |  |  | 450.0 | 2.38 | 1.5 | 1.72 |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`PILES_SHARED_FENI`

- **Rows**: 66,571
- **Flags**: col:TIME
- **Date column**: `DATE_SHARE` — 2024-11-19 00:00:00 to 2026-05-29 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE_SHARE` | datetime | no |
| 3 | `PILE_ID` | nvarchar(255) | yes |
| 4 | `TOS_LOCATION` | nvarchar(255) | yes |
| 5 | `CLASS` | nvarchar(255) | yes |
| 6 | `CATEGORY` | nvarchar(255) | yes |
| 7 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE_SHARE | PILE_ID | TOS_LOCATION | CLASS | CATEGORY | WMT |
|---|---|---|---|---|---|---|
| 1 | 2025-07-27 00:00:00 | BLB.D.1052 |  | HGS | ADM | 1600.0 |
| 2 | 2025-07-27 00:00:00 | BLB.D.1050 |  | HGS | ADM | 1200.0 |
| 3 | 2025-07-27 00:00:00 | BLB.G.4435 |  | LIM | LIM1 | 360.0 |
| 4 | 2025-07-27 00:00:00 | BLB.G.4425 |  | LIM | LIM1 | 150.0 |
| 5 | 2025-07-27 00:00:00 | BLB.G.4431 |  | LIM | LIM1 | 720.0 |

</details>

### `WBN_DATABASE`.`EXC_TRIMMING`

- **Rows**: 59,362
- **Flags**: col:STATUS, col:TIME
- **Date column**: `Date` — 2024-11-13 00:00:00 to 2026-07-11 00:00:00

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `Date` | datetime | yes |
| 3 | `Contractor` | nvarchar(255) | yes |
| 4 | `Shift` | float | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `Location` | nvarchar(255) | yes |
| 7 | `Jumlah Exc` | float | yes |
| 8 | `UNIT_ID` | nvarchar(255) | yes |
| 9 | `STATUS` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | Date | Contractor | Shift | PIT | Location | Jumlah Exc | UNIT_ID | STATUS |
|---|---|---|---|---|---|---|---|---|
| 338 | 2024-11-13 00:00:00 | PPP | 1.0 | TF | TOS_TF_PPP_01 | 3.0 |  |  |
| 339 | 2024-11-13 00:00:00 | PPP | 1.0 | TF | TOS_TF_STM_01 | 1.0 |  |  |
| 340 | 2024-11-13 00:00:00 | SSS | 1.0 | TF | TOS_TF_SMA_03 | 1.0 |  |  |
| 341 | 2024-11-13 00:00:00 | SSS | 1.0 | TF | TOS_TF_STM_04 | 1.0 |  |  |
| 342 | 2024-11-13 00:00:00 | SSS | 1.0 | TF | TOS_TF_STM_03 | 1.0 |  |  |

</details>

### `WBN_DATABASE`.`RAINFALL`

- **Rows**: 55,934
- **Flags**: WEATHER, col:TIME
- **Date column**: `DATE` — 2002-01-01 to 2026-04-11

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | date | yes |
| 4 | `AREA` | nvarchar(255) | yes |
| 5 | `STATION` | nvarchar(255) | yes |
| 6 | `H2O_mm` | float | yes |
| 7 | `X` | float | yes |
| 8 | `Y` | float | yes |
| 9 | `DURASI` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | AREA | STATION | H2O_mm | X | Y | DURASI |
|---|---|---|---|---|---|---|---|---|
| 40135 | ENVIRO | 2024-11-01 | COASTAL | TG. ULIE | 26.0 | 387192.0 | 53352.0 |  |
| 40136 | ENVIRO | 2024-11-01 | COASTAL | UNI UNI | 16.5 | 382998.0 | 53854.0 |  |
| 40137 | ENVIRO | 2024-11-01 | KAO RAHAI | CAMP_KR | 18.7 | 385963.0 | 72202.0 |  |
| 40138 | ENVIRO | 2024-11-01 | TOFU | CAMP MTM | 6.5 | 391856.0 | 89638.0 | 2.3 |
| 40139 | ENVIRO | 2024-11-01 | TOFU | PIT TOFU3_MTM | 8.5 | 392327.0 | 88755.0 | 3.1 |

</details>

### `WBN_DATABASE`.`SURVEY POS`

- **Rows**: 50,160
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-05 00:00:00 to 2026-07-18 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | no |
| 3 | `TYPE OF SURVEY` | nvarchar(255) | yes |
| 4 | `SURVEY WEEK` | float | yes |
| 5 | `LOCATION` | nvarchar(255) | yes |
| 6 | `DOME` | nvarchar(255) | no |
| 7 | `DOME ID` | nvarchar(255) | yes |
| 8 | `SURVEY METHOD` | nvarchar(255) | yes |
| 9 | `PIT DETAILS` | nvarchar(255) | yes |
| 10 | `PIT` | nvarchar(255) | yes |
| 11 | `ROCKY VOLUME` | float | yes |
| 12 | `VOLUME (LCM)` | float | yes |
| 13 | `VOLUME (BCM)` | float | yes |
| 14 | `ORIGINAL DENSITY` | float | yes |
| 15 | `ADJUSTED DENSITY` | float | yes |
| 16 | `WMT` | float | yes |
| 17 | `STOCK TYPE` | nvarchar(255) | yes |
| 18 | `GET_DOME_CRUSH` | nvarchar(255) | yes |
| 19 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | TYPE OF SURVEY | SURVEY WEEK | LOCATION | DOME | DOME ID | SURVEY METHOD | PIT DETAILS | PIT | ROCKY VOLUME | VOLUME (LCM) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 146540 | 2024-10-05 00:00:00 | WEEKLY | 40.0 |  | LGS.G | LGS.G | Drone | CSTL | CSTL |  | 141091.1617803738 |
| 146541 | 2024-10-05 00:00:00 | WEEKLY | 40.0 |  | LGS.CLIFFDUMP CSW2B | LGS CLIFF DUMP CSW2B | Drone | CSW | CSTL |  | 17971.493 |
| 146542 | 2024-10-05 00:00:00 | WEEKLY | 40.0 |  | LGO 1 | LGO | Drone | CNU | CSTL |  | 40561.685 |
| 146543 | 2024-10-05 00:00:00 | WEEKLY | 40.0 |  | LGO 7 | LGO | Ground | CNU | CSTL |  | 25393.3962196262 |
| 146544 | 2024-10-05 00:00:00 | WEEKLY | 40.0 |  | LGO GOMDI | LGO GOMDI | Drone | CSTL | CSTL |  | 10118.32 |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`autoTOS_SURVEY_ESTIMATION`

- **Rows**: 44,438
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2026-04-29 00:00:00 to 2026-07-27 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | nvarchar(50) | yes |
| 2 | `DATE` | datetime | no |
| 3 | `SHIFT` | int | no |
| 4 | `DATETIME` | datetime | yes |
| 5 | `STOCK_TYPE` | nvarchar(50) | no |
| 6 | `STOCK_AREA` | nvarchar(50) | yes |
| 7 | `STOCK_ID` | nvarchar(50) | no |
| 8 | `STATUS` | nvarchar(50) | yes |
| 9 | `CONTRACTOR` | nvarchar(50) | yes |
| 10 | `ACTIVITY` | nvarchar(50) | yes |
| 11 | `MATERIAL` | nvarchar(50) | yes |
| 12 | `RIT` | float | yes |
| 13 | `TF` | float | yes |
| 14 | `WMT_SURVEY_EST` | float | yes |
| 15 | `WMT_SURVEY_GAP` | float | yes |
| 16 | `WMT_SURVEY` | float | yes |
| 17 | `WMT_TRANSFER` | float | yes |
| 18 | `WMT_ORI` | float | yes |
| 19 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | DATE | SHIFT | DATETIME | STOCK_TYPE | STOCK_AREA | STOCK_ID | STATUS | CONTRACTOR | ACTIVITY | MATERIAL | RIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-27 13:00:00 | 2026-04-29 00:00:00 | 1 | 2026-04-29 07:00:00 | TOS | LD_TF_004 |  | OPEN |  |  |  |  |
| 2026-07-27 13:00:00 | 2026-04-29 00:00:00 | 1 | 2026-04-29 07:00:00 | TOS | TOS_BLB_03 | BLB.G.6765 | COMPLETE |  |  |  |  |
| 2026-07-27 13:00:00 | 2026-04-29 00:00:00 | 1 | 2026-04-29 07:00:00 | TOS | TOS_BLB_10 | BLB.G.6796 | COMPLETE |  |  |  |  |
| 2026-07-27 13:00:00 | 2026-04-29 00:00:00 | 1 | 2026-04-29 07:00:00 | TOS | TOS_BLB_10 | BLB.G.6829 | COMPLETE |  |  |  |  |
| 2026-07-27 13:00:00 | 2026-04-29 00:00:00 | 1 | 2026-04-29 07:00:00 | TOS | TOS_BLB_11 | BLB.G.6833 | COMPLETE |  |  |  |  |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`HAULAGE_M_DOME_2026_IWIP_PLAN`

- **Rows**: 44,289
- **Flags**: PLAN, col:EQUIP, col:TIME
- **Date column**: `TIME_LOADED` — 2026-03-05 20:11:55 to 2026-04-06 00:56:51

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `WB_DATE` | float | yes |
| 2 | `WB_ID` | nvarchar(255) | yes |
| 3 | `TICKET_NO` | nvarchar(255) | yes |
| 4 | `TRUCK_ID` | nvarchar(255) | yes |
| 5 | `ORIGIN_ID` | nvarchar(255) | yes |
| 6 | `DESTINATION_ID` | nvarchar(255) | yes |
| 7 | `CONTRACTOR` | nvarchar(255) | yes |
| 8 | `KG_LOADED` | float | yes |
| 9 | `KG_EMPTY` | float | yes |
| 10 | `KG_NET` | float | yes |
| 11 | `TIME_LOADED` | datetime | yes |
| 12 | `TIME_EMPTY` | datetime | yes |
| 13 | `ORI_AREA` | nvarchar(255) | yes |
| 14 | `DEST_AREA` | nvarchar(255) | yes |
| 15 | `DATE` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| WB_DATE | WB_ID | TICKET_NO | TRUCK_ID | ORIGIN_ID | DESTINATION_ID | CONTRACTOR | KG_LOADED | KG_EMPTY | KG_NET | TIME_LOADED | TIME_EMPTY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20260326.0 | T19 | 19A20260326172447 | R700 |  | M4_POS16_001 | RIM | 77600.0 | 29980.0 | 47620.0 | 2026-03-26 17:24:47 | 2026-03-26 22:27:29 |
| 20260326.0 | T19 | 19A20260326173949 | R711 |  | M3_POS16_001 | RIM | 78240.0 | 29100.0 | 49140.0 | 2026-03-26 17:39:49 | 2026-03-26 22:07:09 |
| 20260326.0 | T19 | 19A20260326181108 | R704 |  | M3_POS16_001 | RIM | 79660.0 | 29420.0 | 50240.0 | 2026-03-26 18:11:06 | 2026-03-26 21:05:41 |
| 20260326.0 | T19 | 19A20260326174703 | R699 |  | M4_POS16_001 | RIM | 79340.0 | 28160.0 | 51180.0 | 2026-03-26 17:47:03 | 2026-03-26 21:04:57 |
| 20260326.0 | T19 | 19A20260326175732 | R695 |  | M4_POS16_001 | RIM | 78540.0 | 29560.0 | 48980.0 | 2026-03-26 17:57:32 | 2026-03-26 21:01:51 |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`QC_TOS_DATA_ML`

- **Rows**: 38,001
- **Flags**: col:TIME

<details><summary>33 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | nvarchar(50) | yes |
| 2 | `TYPE_DATA` | varchar(max) | yes |
| 3 | `TYPE` | varchar(max) | yes |
| 4 | `TOS LOCATION` | varchar(max) | yes |
| 5 | `LOCATION` | varchar(max) | yes |
| 6 | `CONTRACTOR` | varchar(max) | yes |
| 7 | `PILE ID` | varchar(max) | yes |
| 8 | `PLAN_Ni` | float | yes |
| 9 | `TOS_CaO` | float | yes |
| 10 | `TOS_Co` | float | yes |
| 11 | `TOS_Fe` | float | yes |
| 12 | `TOS_MC` | float | yes |
| 13 | `TOS_MgO` | float | yes |
| 14 | `TOS_MnO` | float | yes |
| 15 | `TOS_Ni` | float | yes |
| 16 | `TOS_p2o5` | float | yes |
| 17 | `TOS_sio2` | float | yes |
| 18 | `BM_WMT` | float | yes |
| 19 | `BM_al2o3` | float | yes |
| 20 | `BM_cao` | float | yes |
| 21 | `BM_Co` | float | yes |
| 22 | `BM_cr2o3` | float | yes |
| 23 | `BM_Fe` | float | yes |
| 24 | `BM_MC` | float | yes |
| 25 | `BM_MgO` | float | yes |
| 26 | `BM_mno` | float | yes |
| 27 | `BM_Ni` | float | yes |
| 28 | `BM_p2o5` | float | yes |
| 29 | `BM_SiO2` | float | yes |
| 30 | `BM_PROP` | float | yes |
| 31 | `WMT` | float | yes |
| 32 | `MATERIAL` | varchar(max) | yes |
| 33 | `ML_PREDICTED_Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | TYPE_DATA | TYPE | TOS LOCATION | LOCATION | CONTRACTOR | PILE ID | PLAN_Ni | TOS_CaO | TOS_Co | TOS_Fe | TOS_MC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2001 | 1.8910757324269964 | 0.03 | 0.1024 | 23.152400000000004 | 40.173199999999994 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2007 | 1.9122613910243405 | 0.04318181818181818 | 0.07420454545454545 | 19.508181818181818 | 34.21909090909091 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_08 | TF | RIM | TF.G.2008 | 1.9022591295194444 | 0.049 | 0.07959999999999999 | 18.067999999999998 | 33.783 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2009 | 1.9116635828164048 | 0.04 | 0.05691489361702128 | 15.660851063829787 | 33.51617021276596 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2020 | 1.7298906978501567 | 0.04363636363636364 | 0.052727272727272734 | 14.920454545454545 | 31.60181818181818 |

*(first 12 of 33 columns shown)*

</details>

### `WBN_DATABASE`.`PP_REMAIN_INPIT_MINEOUT`

- **Rows**: 36,206
- **Flags**: col:TIME

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PIT` | varchar(50) | yes |
| 2 | `X` | float | yes |
| 3 | `Y` | float | yes |
| 4 | `Z` | float | yes |
| 5 | `classification_no` | float | yes |
| 6 | `size (X)` | float | yes |
| 7 | ` size(Y)` | float | yes |
| 8 | ` size(Z)` | float | yes |
| 9 | `block_id` | nvarchar(255) | yes |
| 10 | `pp_inside_pit_remain` | float | yes |
| 11 | `YEAR_UPDATED` | float | yes |
| 12 | `WEEK_UPDATED` | float | yes |
| 13 | `remarks` | varchar(500) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| PIT | X | Y | Z | classification_no | size (X) |  size(Y) |  size(Z) | block_id | pp_inside_pit_remain | YEAR_UPDATED | WEEK_UPDATED |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TF | 392231.25 | 88181.25 | 444.0 | 1.0 | 12.5 | 12.5 | 4.0 | N442_B72_S325 | 0.89 | 2025.0 | 34.0 |
| TF | 392293.75 | 88181.25 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B77_S325 | 0.75 | 2025.0 | 34.0 |
| TF | 392406.25 | 88231.25 | 452.0 | 1.0 | 12.5 | 12.5 | 4.0 | N450_B86_S321 | 0.09 | 2025.0 | 34.0 |
| TF | 392025.0 | 88250.0 | 420.0 | 1.0 | 25.0 | 25.0 | 4.0 | 418_B23_S157 | 0.08 | 2025.0 | 34.0 |
| TF | 392518.75 | 88256.25 | 452.0 | 1.0 | 12.5 | 12.5 | 4.0 | N450_B95_S319 | 0.03 | 2025.0 | 34.0 |

*(first 12 of 13 columns shown)*

</details>

### `WBN_DATABASE`.`PP_MINED_YTD_OK`

- **Rows**: 35,922
- **Flags**: none

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `X` | float | yes |
| 2 | `Y` | float | yes |
| 3 | `Z` | float | yes |
| 4 | `classification_no` | float | yes |
| 5 | `size (X)` | float | yes |
| 6 | ` size(Y)` | float | yes |
| 7 | ` size(Z)` | float | yes |
| 8 | `block_id` | nvarchar(255) | yes |
| 9 | `pp_mined_progress` | float | yes |
| 10 | `YEAR` | int | yes |
| 11 | `MONTH` | int | yes |
| 12 | `WEEK` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| X | Y | Z | classification_no | size (X) |  size(Y) |  size(Z) | block_id | pp_mined_progress | YEAR | MONTH | WEEK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 392256.25 | 88131.25 | 456.0 | 1.0 | 12.5 | 12.5 | 4.0 | N454_B147_S657 | 0.576 | 2025 | 6 | 26 |
| 392193.75 | 88206.25 | 436.0 | 1.0 | 12.5 | 12.5 | 4.0 | N434_B137_S645 | 0.127 | 2025 | 6 | 26 |
| 392193.75 | 88231.25 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B137_S641 | 0.838 | 2025 | 6 | 26 |
| 392193.75 | 88231.25 | 436.0 | 1.0 | 12.5 | 12.5 | 4.0 | N434_B137_S641 | 1.0 | 2025 | 6 | 26 |
| 392206.25 | 88218.75 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B139_S643 | 0.436 | 2025 | 6 | 26 |

</details>

### `FMS_DB`.`FMS_GEOFENCE_VISITS`

- **Rows**: 35,640
- **Flags**: col:COORD, col:STATUS
- *redacted columns: ORG_NAME, GEOFENCE_NAME*

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `EVENT_ID` | varchar(36) | no |
| 2 | `UNIT_ID` | varchar(40) | no |
| 3 | `UNIT_TYPE` | varchar(40) | yes |
| 4 | `ORG_NAME` 🔒 | nvarchar(200) | yes |
| 5 | `GEOFENCE_ID` | nvarchar(20) | no |
| 6 | `GEOFENCE_NAME` 🔒 | nvarchar(200) | yes |
| 7 | `GEOFENCE_TYPE` | varchar(40) | yes |
| 8 | `ENTER_TS` | bigint | no |
| 9 | `EXIT_TS` | bigint | yes |
| 10 | `DURATION_SEC` | int | yes |
| 11 | `ENTER_LAT` | float | yes |
| 12 | `ENTER_LNG` | float | yes |
| 13 | `EXIT_LAT` | float | yes |
| 14 | `EXIT_LNG` | float | yes |
| 15 | `STATUS` | varchar(12) | no |
| 16 | `SOURCE` | varchar(20) | yes |
| 17 | `CREATED_AT` | bigint | no |

</details>

<details><summary>Sample rows (5)</summary>

| EVENT_ID | UNIT_ID | UNIT_TYPE | ORG_NAME | GEOFENCE_ID | GEOFENCE_NAME | GEOFENCE_TYPE | ENTER_TS | EXIT_TS | DURATION_SEC | ENTER_LAT | ENTER_LNG |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00024379-7809-4388-96fb-36ecf23c7367 | R922 | Haul Truck | [REDACTED] | 2224ef93 | [REDACTED] | pit | 1785050160000 | 1785051202000 | 1042 | 0.679645 | 127.975703 |
| 0005ce09-b605-4ce6-9138-6be69eac7334 | R382 | Haul Truck | [REDACTED] | 2e938c89 | [REDACTED] | pit | 1785143231000 | 1785144841000 | 1610 | 0.521533 | 127.940193 |
| 0006a191-b477-4c7e-8c83-a36a4be54fd1 | N348 | Haul Truck | [REDACTED] | 2224ef93 | [REDACTED] | pit | 1785055530000 | 1785065294000 | 9764 | 0.650672 | 127.972693 |
| 00078dca-9a43-4a9a-8a8c-45e246f1a9e5 | R924 | Haul Truck | [REDACTED] | wb_wb_iwip_t16 | [REDACTED] | weighbridge | 1784957820000 | 1784957886000 | 66 | 0.63823 | 127.94987 |
| 0008588c-584e-4651-9883-e1d94a8e7380 | R332 | Haul Truck | [REDACTED] | 2224ef93 | [REDACTED] | pit | 1785146943000 |  |  | 0.660418 | 127.975185 |

*(first 12 of 17 columns shown)*

</details>

### `WBN_DATABASE`.`TSS`

- **Rows**: 35,218
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-04-11 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `AREA` | nvarchar(255) | yes |
| 5 | `SUB_AREA` | nvarchar(255) | yes |
| 6 | `MANAGER` | nvarchar(255) | yes |
| 7 | `TYPE` | nvarchar(255) | yes |
| 8 | `MINE` | nvarchar(255) | yes |
| 9 | `STATION` | nvarchar(255) | yes |
| 10 | `TSS` | float | yes |
| 11 | `PH` | float | yes |
| 12 | `TEMPERATURE` | float | yes |
| 13 | `CONDUCTIVITY` | float | yes |
| 14 | `TDS` | float | yes |
| 15 | `TURBIDITY_NTU` | float | yes |
| 16 | `TSS_LIMIT` | float | yes |
| 17 | `COMPLIANCE` | float | yes |
| 18 | `X` | float | yes |
| 19 | `Y` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | AREA | SUB_AREA | MANAGER | TYPE | MINE | STATION | TSS | PH | TEMPERATURE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 850 | ENVIRO | 2025-01-31 00:00:00 | PINTO | Ake Yonelo |  | River | WBN | AP-06' (Actual) | 5.0 |  |  |
| 851 | ENVIRO | 2025-01-31 00:00:00 | KAO RAHAI | HR Coastal - KR KM 18 |  | River | WBN | AP-SL-04 | 5.0 | 8.53 | 25.0 |
| 852 | ENVIRO | 2025-01-31 00:00:00 | KAO RAHAI | Ake Mein |  | River | WBN | AP-09 | 12.0 | 8.29 | 23.5 |
| 853 | ENVIRO | 2025-01-31 00:00:00 | COASTAL | Ake Wosea |  | River | WBN | AP2 | 18.0 | 8.59 | 25.3 |
| 854 | ENVIRO | 2025-01-31 00:00:00 | COASTAL | Ake Wosea |  | River | WBN | AP3 | 31.0 | 8.58 | 25.0 |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`HRM_INSPECTION`

- **Rows**: 30,610
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2025-12-11 00:00:00

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | float | yes |
| 4 | `LOCATION` | nvarchar(50) | yes |
| 5 | `KM_START` | float | yes |
| 6 | `KM_END` | float | yes |
| 7 | `DIRECTION` | nvarchar(50) | yes |
| 8 | `CONTRACTOR` | nvarchar(50) | yes |
| 9 | `TYPE` | nvarchar(max) | yes |
| 10 | `SEVERITY` | float | yes |
| 11 | `STATUS` | nvarchar(50) | yes |
| 12 | `DETAILS` | nvarchar(250) | yes |
| 13 | `STA` | nvarchar(50) | yes |
| 14 | `IDLINK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | LOCATION | KM_START | KM_END | DIRECTION | CONTRACTOR | TYPE | SEVERITY | STATUS | DETAILS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5464 | 2024-10-01 00:00:00 | 1.0 | KR | 15.5 | 16.0 | LOADED & EMPTY | RIM | BUMPY ROAD | 1.0 | ON MAINTENANCE | spot undulated (1) on maintenance (continue grading & com... |
| 5465 | 2024-10-01 00:00:00 | 1.0 | KR | 16.7 | 17.0 | LOADED & EMPTY | RIM | BUMPY ROAD | 1.0 | NEED MAINTENANCE | undulated road (1) need to grading and compacting |
| 5466 | 2024-10-01 00:00:00 | 1.0 | KR | 17.8 | 17.9 | LOADED & EMPTY | RIM | BUMPY ROAD | 2.0 | NEED MAINTENANCE | undulated road (2) need to maintenance, Need to Install C... |
| 5467 | 2024-10-01 00:00:00 | 1.0 | KR | 18.15 | 18.3 | EMPTY | RIM | BUMPY ROAD | 1.0 | ON MAINTENANCE | undulated road (1), on maintenance |
| 5468 | 2024-10-01 00:00:00 | 1.0 | KR | 18.6 | 18.9 | LOADED & EMPTY | RIM | CLOGGED DRAINAGE | 2.0 | ON MAINTENANCE | Undulated road (1), need grading & compacting, cloged dra... |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`DISTANCE_HAULING`

- **Rows**: 30,587
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2025-04-28 00:00:00 to 2025-09-27 00:00:00

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `ORIGIN_ID` | nvarchar(255) | yes |
| 5 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 6 | `DESTINATION_ID` | nvarchar(255) | yes |
| 7 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 8 | `DISTANCE` | float | yes |
| 9 | `WMT` | float | yes |
| 10 | `RIT` | float | yes |
| 11 | `SPV_WBN` | nvarchar(255) | yes |
| 12 | `SPV_CONTRACTOR` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | ORIGIN_ID | ORIGIN_AREA | DESTINATION_ID | DESTINATION_AREA | DISTANCE | WMT | RIT | SPV_WBN | SPV_CONTRACTOR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-04-28 00:00:00 | SMA | TF.B.2596 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 491.78000000000003 | 12.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 2 | 2025-04-28 00:00:00 | SMA | TF.A.3211 | TOS_TF_STM_04 | ADM.469 | POS 12 | 43.300000000000004 | 1184.0200000000002 | 32.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 3 | 2025-04-28 00:00:00 | SMA | TF.B.2553 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 2068.16 | 56.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 4 | 2025-04-28 00:00:00 | SMA | TF.A.3215 | TOS_TF_STM_01 | ADM.472 | POS 12 | 42.5 | 1648.1399999999999 | 50.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 5 | 2025-04-28 00:00:00 | SMA | TF.B.2601 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 486.14000000000004 | 13.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |

</details>

### `WBN_DATABASE`.`CRUSHER LOIPOLOY`

- **Rows**: 27,334
- **Flags**: col:EQUIP, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-26

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(max) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `LOCATION` | nvarchar(max) | yes |
| 6 | `CRUSHER` | nvarchar(max) | yes |
| 7 | `LINE` | int | yes |
| 8 | `FEEDING_ID` | int | yes |
| 9 | `RECORDED_MATERIAL` | nvarchar(max) | yes |
| 10 | `PRODUCT` | nvarchar(max) | yes |
| 11 | `STOCK_ID` | nvarchar(max) | yes |
| 12 | `BUCKET` | int | yes |
| 13 | `BF` | int | yes |
| 14 | `TRUCK` | int | yes |
| 15 | `TF` | int | yes |
| 16 | `BCM` | float | yes |
| 17 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | LOCATION | CRUSHER | LINE | FEEDING_ID | RECORDED_MATERIAL | PRODUCT | STOCK_ID | BUCKET |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 583 | PMKI | 2024-10-13 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | FEED |  |  | 33 |
| 584 | PMKI | 2024-10-13 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 2-3 | 2-3 Line 1 | 13 |
| 585 | PMKI | 2024-10-13 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 1-2 | 1-2 Line 1 | 4 |
| 586 | PMKI | 2024-10-13 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 0-1 | 0-1 Line 1 | 16 |
| 587 | PMKI | 2024-10-13 | 2 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | FEED |  |  | 67 |

*(first 12 of 17 columns shown)*

</details>

### `WBN_DATABASE`.`DISPATCH WBN PLAN SHIFT`

- **Rows**: 27,058
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-22

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `TYPE DATA` | nvarchar(50) | yes |
| 6 | `TYPE` | nvarchar(50) | yes |
| 7 | `MATERIAL` | nvarchar(50) | yes |
| 8 | `COMPANY` | nvarchar(50) | yes |
| 9 | `DISPATCH ZONE` | nvarchar(50) | yes |
| 10 | `ORIGIN` | nvarchar(50) | yes |
| 11 | `DESTINATION` | nvarchar(50) | yes |
| 12 | `BUYER` | nvarchar(50) | yes |
| 13 | `NB DT` | float | yes |
| 14 | `TF` | float | yes |
| 15 | `PRODUCTIVITY TARGET` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | TYPE DATA | TYPE | MATERIAL | COMPANY | DISPATCH ZONE | ORIGIN | DESTINATION | BUYER |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 16865 | GMG | 2024-10-01 | 1 | PLAN | HAULAGE | SAP | WBN | KR to KM 17 | KR | POS 10 |  |
| 16866 | HJS | 2024-10-01 | 1 | PLAN | HAULAGE | SAP | WBN | CBB to CUU | CBB | POS UNI-UNI |  |
| 16867 | HJS | 2024-10-01 | 1 | PLAN | HAULAGE | SAP | WBN | CBB to CBB | CBB | POS CBB |  |
| 16868 | PPP | 2024-10-01 | 1 | PLAN | DIRECT | LIM | WBN | KR to HUAFEI | KR | HUAFEI.C01 |  |
| 16869 | PPP | 2024-10-01 | 1 | PLAN | DIRECT | CS | WBN | KR to KM 15 | KR | FENI KM15 |  |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`QC SAMPLE DATA`

- **Rows**: 25,425
- **Flags**: col:TIME
- **Date column**: `DATE_IN` — 2024-01-12 to 2025-02-17

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `JOB-QC` | nvarchar(50) | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `DATE_IN` | date | yes |
| 5 | `PILE ID` | nvarchar(50) | yes |
| 6 | `COMPOSITE` | nvarchar(50) | yes |
| 7 | `TYPE SAMPLE` | nvarchar(50) | yes |
| 8 | `RIT` | int | yes |
| 9 | `SAMPLE WEIGHT` | float | yes |
| 10 | `ROCKY WEIGHT` | float | yes |
| 11 | `EARTHY WEIGHT` | float | yes |
| 12 | `DATE` | date | yes |
| 13 | `SAMPLE CODE` | nvarchar(50) | yes |
| 14 | `TYPE ANALYSIS` | nvarchar(50) | yes |
| 15 | `TESTED SAMPLE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | JOB-QC | SHIFT | DATE_IN | PILE ID | COMPOSITE | TYPE SAMPLE | RIT | SAMPLE WEIGHT | ROCKY WEIGHT | EARTHY WEIGHT | DATE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 65120 | BLB-IWIP-1000 | 2 | 2025-02-06 | BLB.G.1573 |  | ORIGINAL | 30 | 450.0 | 150.0 | 300.0 | 2025-02-07 |
| 65121 | BLB-IWIP-1000 | 2 | 2025-02-06 | BLB.G.1573 |  | DUPLICATE 1 |  |  |  |  | 2025-02-07 |
| 65122 | BLB-IWIP-1000 | 2 | 2025-02-06 | BLB.G.1577 |  | ORIGINAL | 49 | 735.0 | 245.0 | 490.0 | 2025-02-07 |
| 65123 | BLB-IWIP-1000 | 2 | 2025-02-06 | BLB.G.1573 |  | PULP DUPLICATE |  |  |  |  | 2025-02-07 |
| 65124 | BLB-IWIP-1000 | 2 | 2025-02-06 | BLB.G.1577 |  | GROUND DUPLICATE |  |  |  |  | 2025-02-07 |

*(first 12 of 15 columns shown)*

</details>

### `FMS_DB`.`FMS_CONGESTION_SEG`

- **Rows**: 23,999
- **Flags**: col:EQUIP, col:TIME

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `HOUR_TS` | bigint | no |
| 2 | `SEG_ID` | nvarchar(40) | no |
| 3 | `DIR` | char(4) | no |
| 4 | `SUM_SPD` | float | yes |
| 5 | `FIX_N` | int | yes |
| 6 | `TRUCK_N` | int | yes |
| 7 | `UPDATED_AT` | bigint | yes |
| 8 | `SUM_TRAV_MS` | float | yes |
| 9 | `TRAV_N` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| HOUR_TS | SEG_ID | DIR | SUM_SPD | FIX_N | TRUCK_N | UPDATED_AT | SUM_TRAV_MS | TRAV_N |
|---|---|---|---|---|---|---|---|---|
| 1784077200000 | BLB KM17-18 | down | 1230.0 | 91 | 5 | 1784510901345 | 860000.0 | 4 |
| 1784077200000 | BLB KM17-18 | up   | 697.0 | 43 | 4 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM18-19 | down | 1404.0 | 108 | 5 | 1784510901345 | 695000.0 | 3 |
| 1784077200000 | BLB KM18-19 | up   | 740.0 | 57 | 5 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM19-20 | down | 659.0 | 41 | 2 | 1784510901345 | 0.0 | 0 |

</details>

### `WBN_DATABASE`.`VERY VERY SHORT TERM PIT SERVICE`

- **Rows**: 21,059
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-07-26 00:00:00

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | nvarchar(255) | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `LOCATION` | nvarchar(255) | yes |
| 7 | `EXCA` | float | yes |
| 8 | `ADT` | float | yes |
| 9 | `DT` | float | yes |
| 10 | `BULL` | float | yes |
| 11 | `GRADER` | nvarchar(255) | yes |
| 12 | `COMPACTOR` | float | yes |
| 13 | `LOADER` | nvarchar(255) | yes |
| 14 | `QUARRY_WMT` | float | yes |
| 15 | `SP_WST_WMT` | float | yes |
| 16 | `TMM__WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | PIT | LOCATION | EXCA | ADT | DT | BULL | GRADER | COMPACTOR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3720 | 2024-10-01 00:00:00 | DS | HJS | CBB | CBB | 2.0 | 8.0 | 8.0 |  |  |  |
| 3721 | 2024-10-01 00:00:00 | DS | HJS | CSW | BLB | 1.0 | 0.0 | 6.0 |  |  |  |
| 3722 | 2024-10-01 00:00:00 | DS | MTM | TF | PIT/TOS/MESS | 1.0 | 1.0 |  |  |  |  |
| 3723 | 2024-10-01 00:00:00 | DS | PPP | KR | AKSES JALAN |  |  |  | 1.0 |  |  |
| 3724 | 2024-10-01 00:00:00 | DS | PPP | KR | PIT KAORAHAI 3 | 1.0 |  |  | 2.0 |  |  |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`ASSAYS_NITON_GGSHEET`

- **Rows**: 19,700
- **Flags**: col:TIME
- **Date column**: `LAST_UPDATE` — 2026-01-28 14:00:16 to 2026-07-27 13:00:49

<details><summary>25 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | datetime | yes |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | nvarchar(50) | yes |
| 4 | `JOB QC` | nvarchar(50) | yes |
| 5 | `CODE ID` | nvarchar(50) | yes |
| 6 | `ID DOME` | nvarchar(50) | yes |
| 7 | `DATE ANALYSIS` | nvarchar(50) | yes |
| 8 | `DATE REPORT` | nvarchar(50) | yes |
| 9 | `CONTRACTOR` | nvarchar(50) | yes |
| 10 | `ID BLOCK` | nvarchar(50) | yes |
| 11 | `Ni Dry 1` | float | yes |
| 12 | `Fe2O3 Dry 1` | float | yes |
| 13 | `Ni Dry 2` | float | yes |
| 14 | `Fe2O3 Dry2` | float | yes |
| 15 | `Mc` | float | yes |
| 16 | `Column1` | nvarchar(50) | yes |
| 17 | `Ni Average` | float | yes |
| 18 | `Fe2O3 Average` | float | yes |
| 19 | `Tfe` | float | yes |
| 20 | `Ni` | float | yes |
| 21 | `Fe2O3` | float | yes |
| 22 | `Mc2` | float | yes |
| 23 | `TFe2` | float | yes |
| 24 | `SAMPLE_TYPE` | nvarchar(50) | yes |
| 25 | `ID` | int | no |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | DATE | SHIFT | JOB QC | CODE ID | ID DOME | DATE ANALYSIS | DATE REPORT | CONTRACTOR | ID BLOCK | Ni Dry 1 | Fe2O3 Dry 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  | 2025-09-29 | DS | WBN.TF-1119 | TF-38859 | AR/TF.G.2073 |  |  | RIM |  | 1.31 | 56.08 |
|  | 2025-09-29 | DS | WBN.TF-1119 | TF-38860 | AR/TF.G.2085 |  |  | RIM |  | 1.07 | 61.63 |
| 2026-01-28 14:00:16.410000 | 2026-01-24 | NS | BLB-IWIP-3378 | BLB-IWIP-16426 | BLB.G.6284T | 1/24/2026 21:36:00 | 1/24/2026 5:00:00 | PT.RIM |  | 1.82 | 42.86 |
| 2026-01-28 14:00:16.410000 | 2026-01-26 | NS | BLB-IWIP-3391 | BLB-LIM-16477 | E/BLB.G.3310 A | 1/26/2026 21:37:00 | 1/26/2026 5:00:00 | PT.RIM |  | 1.07 | 68.54 |
| 2026-01-28 14:00:16.410000 | 2026-01-26 | NS | BLB-IWIP-3391 | BLB-LIM-16479 | E/BLB.G.3306 B1 | 1/26/2026 21:47:00 | 1/26/2026 5:00:00 | PT.RIM |  | 1.09 | 74.03 |

*(first 12 of 25 columns shown)*

</details>

### `WBN_DATABASE`.`PRODUCTION_PIT_PRELIM_auto`

- **Rows**: 15,887
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-11-17 00:00:00 to 2026-03-23 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CONTRACTOR` | nvarchar(255) | no |
| 2 | `DATE` | datetime | no |
| 3 | `SHIFT` | float | yes |
| 4 | `ACTIVITY` | nvarchar(255) | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `SUBPIT` | nvarchar(255) | yes |
| 7 | `BLOCK_TYPE` | nvarchar(255) | yes |
| 8 | `BLOCK_STATUS` | nvarchar(255) | yes |
| 9 | `BLOCK_ID` | nvarchar(255) | yes |
| 10 | `PROD_ID` | nvarchar(255) | yes |
| 11 | `MATERIAL` | nvarchar(255) | yes |
| 12 | `MATERIAL_CLASS` | nvarchar(255) | yes |
| 13 | `RIT` | float | yes |
| 14 | `TF` | float | yes |
| 15 | `WMT` | float | yes |
| 16 | `DESTINATION` | nvarchar(255) | yes |
| 17 | `TOS_PILE` | nvarchar(255) | yes |
| 18 | `BLAST_STATUS` | nvarchar(255) | yes |
| 19 | `BLAST_ID` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CONTRACTOR | DATE | SHIFT | ACTIVITY | PIT | SUBPIT | BLOCK_TYPE | BLOCK_STATUS | BLOCK_ID | PROD_ID | MATERIAL | MATERIAL_CLASS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRELIM | 2026-01-28 00:00:00 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  |
| PRELIM | 2026-01-28 00:00:00 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  |
| PRELIM | 2026-01-28 00:00:00 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  |
| PRELIM | 2026-01-28 00:00:00 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  |
| PRELIM | 2026-01-28 00:00:00 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`STOCK_STATUS`

- **Rows**: 14,720
- **Flags**: col:TIME
- **Date column**: `DATE_OPEN` — 1900-01-01 to 2026-07-15

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CONTRACTOR` | nvarchar(50) | yes |
| 2 | `ORIGIN_PIT` | nvarchar(50) | yes |
| 3 | `STOCK_TYPE` | nvarchar(50) | yes |
| 4 | `STOCK_AREA` | nvarchar(255) | yes |
| 5 | `STOCK_ID` | nvarchar(255) | no |
| 6 | `MATERIAL` | nvarchar(50) | yes |
| 7 | `DATE_OPEN` | date | yes |
| 8 | `DATE_COMPLETE` | date | yes |
| 9 | `DATE_TRANSFER` | date | yes |
| 10 | `DATE_FINISH` | date | yes |
| 11 | `REMARK` | nvarchar(255) | yes |
| 12 | `PAD_ID` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CONTRACTOR | ORIGIN_PIT | STOCK_TYPE | STOCK_AREA | STOCK_ID | MATERIAL | DATE_OPEN | DATE_COMPLETE | DATE_TRANSFER | DATE_FINISH | REMARK | PAD_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WBN |  | POS | OLD EOS | A | SAP | 2021-04-28 | 2021-04-28 |  | 2021-05-01 |  |  |
| WBN | KR | POS | POS 3 | AA | SAP | 2021-03-27 | 2021-03-27 |  | 2021-04-10 |  |  |
| WBN | KR | POS | EOS | AA.01.2302 | SAP | 2023-02-11 | 2023-03-01 | 2023-03-01 | 2023-03-04 |  |  |
| WBN | KR | POS | EOS | AA.01.2303 | SAP | 2023-02-26 | 2023-03-10 | 2023-03-10 | 2023-03-13 |  |  |
| WBN | KR | POS | EOS | AA.02.2302 | SAP | 2023-02-18 | 2023-03-06 | 2023-03-06 | 2023-03-09 |  |  |

</details>

### `WBN_DATABASE`.`blasting_drilling`

- **Rows**: 14,648
- **Flags**: col:TIME
- **Date column**: `Date` — 2024-11-25 00:00:00 to 2026-03-19 00:00:00

<details><summary>22 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `drilling_machine` | nvarchar(255) | yes |
| 3 | `year` | nvarchar(255) | yes |
| 4 | `month` | nvarchar(255) | yes |
| 5 | `week` | nvarchar(255) | yes |
| 6 | `Date` | datetime | yes |
| 7 | `Shift` | nvarchar(255) | yes |
| 8 | `start` | datetime | yes |
| 9 | `end` | datetime | yes |
| 10 | `duration_h` | int | yes |
| 11 | `downtime_rest_h` | int | yes |
| 12 | `Kegiatan` | nvarchar(255) | yes |
| 13 | `Location` | nvarchar(255) | yes |
| 14 | `mining_contractor` | nvarchar(255) | yes |
| 15 | `drilling_contractor` | nvarchar(255) | yes |
| 16 | `blasting_contractor` | nvarchar(255) | yes |
| 17 | `pit` | nvarchar(255) | yes |
| 18 | `subpit` | nvarchar(255) | yes |
| 19 | `block_id` | nvarchar(255) | yes |
| 20 | `number_of_holes` | float | yes |
| 21 | `depth_m` | float | yes |
| 22 | `comment` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | drilling_machine | year | month | week | Date | Shift | start | end | duration_h | downtime_rest_h | Kegiatan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6941 | D-33 K-38 | 2024 | Nov | 48 | 2024-11-25 00:00:00 | DAY | 1899-12-30 06:30:00 | 1899-12-30 17:00:00 | 0 |  | Drilling |
| 6942 | D-32 K-37 | 2024 | Nov | 48 | 2024-11-25 00:00:00 | DAY | 1899-12-30 06:30:00 | 1899-12-30 17:00:00 | 0 |  | Drilling |
| 6943 | D-30 K-35 | 2024 | Nov | 48 | 2024-11-25 00:00:00 | DAY | 1899-12-30 06:30:00 | 1899-12-30 17:00:00 | 0 |  | Drilling |
| 6944 | D-31 K-36 | 2024 | Nov | 48 | 2024-11-25 00:00:00 | DAY | 1899-12-30 06:30:00 | 1899-12-30 17:00:00 | 0 |  | Drilling |
| 6945 | D-04 K-04 | 2024 | Nov | 48 | 2024-11-25 00:00:00 | DAY | 1899-12-30 06:30:00 | 1899-12-30 17:00:00 | 0 |  | Drilling |

*(first 12 of 22 columns shown)*

</details>

### `WBN_DATABASE`.`OLD_VERY_SHORT_TERM`

- **Rows**: 13,470
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-05 to 2025-11-27

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `CONTRACTOR` | nvarchar(50) | yes |
| 5 | `DISPATCH_TABLE` | nvarchar(50) | yes |
| 6 | `MATERIAL` | nvarchar(50) | yes |
| 7 | `COMPANY` | nvarchar(50) | yes |
| 8 | `ORIGIN` | nvarchar(50) | yes |
| 9 | `BLOCK_ID` | nvarchar(50) | yes |
| 10 | `TOS` | nvarchar(50) | yes |
| 11 | `DESTINATION_POS_DOME` | nvarchar(50) | yes |
| 12 | `DESTINATION_POS` | nvarchar(50) | yes |
| 13 | `TRIPS` | int | yes |
| 14 | `WMT` | float | yes |
| 15 | `NB_DT` | float | yes |
| 16 | `STATUS` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | DISPATCH_TABLE | MATERIAL | COMPANY | ORIGIN | BLOCK_ID | TOS | DESTINATION_POS_DOME | DESTINATION_POS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 2024-10-05 | 1 | PPP | DISPATCH_ACTUAL | SAP | WBN | TF |  |  |  | POS 12 EXT |
| 31 | 2024-10-05 | 1 | PPP | DISPATCH_ACTUAL | SAP | WBN | KR |  |  |  | FENI |
| 32 | 2024-10-05 | 1 | PPP | DISPATCH_ACTUAL | LIM | WBN | KR |  |  |  | HUAFEI C.01 |
| 33 | 2024-10-05 | 1 | PPP | DISPATCH_ACTUAL |  | WBN | TOTAL |  |  |  |  |
| 34 | 2024-10-05 | 1 | PPP | TOS_FOLLOW | LIM | WBN | KR | LD_KR_003 | LD_KR | LD_KR_003 | HUAFEI C.01 |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`HAULAGE_REPORT`

- **Rows**: 13,459
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-05 to 2025-11-26

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | date | yes |
| 2 | `SHIFT` | int | yes |
| 3 | `CONTRACTOR` | nvarchar(50) | yes |
| 4 | `TABLE` | nvarchar(50) | yes |
| 5 | `ACTIVITY` | nvarchar(50) | yes |
| 6 | `MATERIAL` | nvarchar(50) | yes |
| 7 | `COMPANY` | nvarchar(50) | yes |
| 8 | `ORIGIN` | nvarchar(50) | yes |
| 9 | `BLOCK_ID` | nvarchar(50) | yes |
| 10 | `TOS` | nvarchar(50) | yes |
| 11 | `DESTINATION_POS_DOME` | nvarchar(50) | yes |
| 12 | `DESTINATION_POS` | nvarchar(50) | yes |
| 13 | `TRIPS` | int | yes |
| 14 | `WMT` | float | yes |
| 15 | `NB_DT` | float | yes |
| 16 | `STATUS` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | SHIFT | CONTRACTOR | TABLE | ACTIVITY | MATERIAL | COMPANY | ORIGIN | BLOCK_ID | TOS | DESTINATION_POS_DOME | DESTINATION_POS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-10-22 | 1 | SMA | DISPATCH_ACTUAL |  | SAP | WBN | TF |  |  |  | POS 12 |
| 2025-10-22 | 1 | SMA | DISPATCH_ACTUAL |  |  | WBN | TOTAL |  |  |  |  |
| 2025-10-22 | 1 | SMA | TOS_FOLLOW |  | SAP | WBN | TF | TF.B.3850 | TF_SMA_02 | ACM.588 | POS 12 EXT |
| 2025-10-22 | 1 | SMA | TOS_FOLLOW |  | SAP | WBN | TF | TF.B.3836 | TF_SMA_02 | ACM.588 | POS 12 EXT |
| 2025-10-22 | 1 | SMA | TOS_FOLLOW |  |  | WBN | TOTAL |  |  |  |  |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`WBN_DATABASE_ST_LOG_ON`

- **Rows**: 13,081
- **Flags**: col:TIME
- **Date column**: `datetime` — 2026-06-18 08:07:35 to 2026-07-27 18:39:37
- *redacted columns: name*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `datetime` | datetime | yes |
| 2 | `name` 🔒 | varchar(max) | yes |
| 3 | `page` | varchar(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| datetime | name | page |
|---|---|---|
| 2026-07-24 14:34:13.707000 | [REDACTED] | production_pit-prod |
| 2026-07-24 14:34:17.817000 | [REDACTED] | production_pit-prod |
| 2026-07-24 14:36:03.480000 | [REDACTED] | production_haulage-table |
| 2026-07-24 14:36:06.953000 | [REDACTED] | production_haulage-table |
| 2026-07-24 15:24:37.053000 | [REDACTED] | production_pit-tos |

</details>

### `WBN_DATABASE`.`QUARRY PRODUCTION`

- **Rows**: 12,646
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2025-09-10

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(max) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `QUARRY` | nvarchar(max) | yes |
| 6 | `SUBQUARRY` | nvarchar(max) | yes |
| 7 | `AREA_ID` | nvarchar(max) | yes |
| 8 | `MATERIAL` | nvarchar(max) | yes |
| 9 | `RIT` | int | yes |
| 10 | `TF (BCM)` | float | yes |
| 11 | `DESTINATION` | nvarchar(max) | yes |
| 12 | `DESTINATION 2` | nvarchar(max) | yes |
| 13 | `PILE ID` | nvarchar(max) | yes |
| 14 | `TYPE_TRANSPORT` | nvarchar(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | QUARRY | SUBQUARRY | AREA_ID | MATERIAL | RIT | TF (BCM) | DESTINATION | DESTINATION 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1376 | PPP | 2024-10-01 | 1 | QUARRY LOYPOLOY KM16 |  |  | LAMINATING | 51 | 15.0 | POS 10 | PAD LGS KR 60 |
| 1377 | PPP | 2024-10-01 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 50 | 15.0 | CRUSHER LOYPOLOY KM 16 | LINE 3 |
| 1378 | PPP | 2024-10-01 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 48 | 15.0 | CRUSHER LOYPOLOY KM 16 | LINE 2 |
| 1379 | PPP | 2024-10-01 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 37 | 15.0 | CRUSHER LOYPOLOY KM 16 | STOCKPILE LANTAI 2 |
| 1380 | PPP | 2024-10-01 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 19 | 15.0 | CRUSHER KAORAHAI KM 38 | CRUSHER KM 38 |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`PROD VERY VERY SHORT TERM`

- **Rows**: 11,163
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2026-07-26

<details><summary>29 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `CONTRACTOR` | nvarchar(50) | yes |
| 4 | `SHIFT` | nvarchar(50) | yes |
| 5 | `PIT` | nvarchar(50) | yes |
| 6 | `LOCATION` | nvarchar(50) | yes |
| 7 | `TF` | float | yes |
| 8 | `EXCA` | float | yes |
| 9 | `ADT` | float | yes |
| 10 | `BMS` | float | yes |
| 11 | `SAP` | float | yes |
| 12 | `RSAP` | float | yes |
| 13 | `LIM` | float | yes |
| 14 | `WCO` | float | yes |
| 15 | `WST` | float | yes |
| 16 | `TS` | float | yes |
| 17 | `SPOIL ORE` | float | yes |
| 18 | `SPOIL WST` | float | yes |
| 19 | `TMM` | float | yes |
| 20 | `DOZER` | float | yes |
| 21 | `DT` | float | yes |
| 22 | `QUARRY` | float | yes |
| 23 | `LIM_REHAND` | float | yes |
| 24 | `WST_REHAND` | float | yes |
| 25 | `TS_REHAND` | float | yes |
| 26 | `BLDR_REHAND` | float | yes |
| 27 | `QUARRY _REHAND` | float | yes |
| 28 | `DEPARTMEN` | nvarchar(50) | yes |
| 29 | `SAP_REHAND` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | SHIFT | PIT | LOCATION | TF | EXCA | ADT | BMS | SAP | RSAP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3801 | 2024-10-01 | HJS | DS | PIT CBB | CBB | 36.0 | 6.0 | 28.0 |  | 304.0 |  |
| 3802 | 2024-10-01 | HJS | NS | PIT CBB | CBB | 36.0 | 7.0 | 25.0 |  | 291.0 |  |
| 3803 | 2024-10-01 | MTM | DS | TF | TOFU | 31.0 | 3.0 | 6.0 |  | 29.0 |  |
| 3804 | 2024-10-01 | MTM | NS | TF | TOFU | 31.0 | 2.0 | 4.0 |  |  |  |
| 3805 | 2024-10-01 | PPP | DS | KR | KR | 30.0 | 6.0 | 19.0 |  | 243.0 |  |

*(first 12 of 29 columns shown)*

</details>

### `WBN_DATABASE`.`RSF_SURVEY`

- **Rows**: 9,103
- **Flags**: col:COORD, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-04 00:00:00 to 2025-06-20 00:00:00
- *redacted columns: NAME*

<details><summary>20 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `YEAR` | int | yes |
| 4 | `MONTH` | int | yes |
| 5 | `WEEK` | int | yes |
| 6 | `LAYER` | nvarchar(50) | yes |
| 7 | `LOCATION` | nvarchar(50) | yes |
| 8 | `NAME` 🔒 | nvarchar(50) | yes |
| 9 | `ELEVATION` | float | yes |
| 10 | `RL_ELEVATION` | float | yes |
| 11 | `CROSSECTION` | nvarchar(50) | yes |
| 12 | `ITEM` | nvarchar(50) | yes |
| 13 | `MATERIAL_TYPE` | nvarchar(50) | yes |
| 14 | `PROGRESS_VOLUME` | float | yes |
| 15 | `CUMMULATIVE` | float | yes |
| 16 | `X` | float | yes |
| 17 | `Y` | float | yes |
| 18 | `Z` | float | yes |
| 19 | `MAX_CAPACITY` | float | yes |
| 20 | `STATUS` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | YEAR | MONTH | WEEK | LAYER | LOCATION | NAME | ELEVATION | RL_ELEVATION | CROSSECTION | ITEM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3057 | 2024-10-04 00:00:00 | 2024 | 10 | 40 | 3 | Cell | [REDACTED] | 75.0 |  |  | Disposal |
| 3058 | 2024-10-04 00:00:00 | 2024 | 10 | 40 | 3 | Cell | [REDACTED] | 75.0 |  |  | Disposal |
| 3059 | 2024-10-04 00:00:00 | 2024 | 10 | 40 | 3 | Cell | [REDACTED] | 75.0 |  |  | Disposal |
| 3060 | 2024-10-04 00:00:00 | 2024 | 10 | 40 | 3 | Cell | [REDACTED] | 75.0 |  |  | Disposal |
| 3061 | 2024-10-04 00:00:00 | 2024 | 10 | 40 | 3 | Cell | [REDACTED] | 75.0 |  |  | Disposal |

*(first 12 of 20 columns shown)*

</details>

### `FMS_DB`.`RES_EMPLOYEES`

- **Rows**: 8,958
- **Flags**: none
- *redacted columns: FULL_NAME*

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FULL_NAME` 🔒 | nvarchar(255) | yes |
| 2 | `GENDER` | nvarchar(255) | yes |
| 3 | `ORIGIN` | nvarchar(255) | yes |
| 4 | `ORIGIN_CLASS` | nvarchar(255) | yes |
| 5 | `EMPLOYEE_ID` | float | yes |
| 6 | `CONTRACTOR` | nvarchar(255) | yes |
| 7 | `DIVISION` | nvarchar(255) | yes |
| 8 | `JOB_TITLE` | nvarchar(255) | yes |
| 9 | `GRADE` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FULL_NAME | GENDER | ORIGIN | ORIGIN_CLASS | EMPLOYEE_ID | CONTRACTOR | DIVISION | JOB_TITLE | GRADE |
|---|---|---|---|---|---|---|---|---|
| [REDACTED] | Perempuan | Weda | LOKAL | 8211120002.0 | RIM | OFFICE | Foreman Admin | 3.0 |
| [REDACTED] | Laki-Laki | Bolaang Mongondow | NASIONAL |  | RIM | ADMIN TEAM PIT KM 38 | Junior Quality Control | 4.0 |
| [REDACTED] | Laki-Laki | Sorong | NASIONAL | 8211005056.0 | RIM | MAINTENANCE MANHAUL C KM 36 | Operator DT 10 Bola | 4.0 |
| [REDACTED] | Laki-Laki | Lelilef Woebulen | LOKAL |  | RIM | TEAM QC PAGI | Foreman Quality Control | 4.0 |
| [REDACTED] | Laki-Laki | Buton Tengah | NASIONAL | 8221220004.0 | RIM | TEAM A PENGAWAS DT MALAM | Operator DT 10 Bola | 4.0 |

</details>

### `WBN_DATABASE`.`autoQC_CF_BM_TOS`

- **Rows**: 8,234
- **Flags**: col:TIME
- **Date column**: `LAST_UPDATE` — 2026-07-06 08:46:58 to 2026-07-27 13:00:57

<details><summary>20 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | datetime | no |
| 2 | `DATE` | date | no |
| 3 | `MATERIAL` | nvarchar(50) | no |
| 4 | `ORIGIN_PIT` | nvarchar(50) | no |
| 5 | `CONTRACTOR_PILE` | nvarchar(50) | no |
| 6 | `DIL_BM_MC` | float | yes |
| 7 | `DIL_BM_Ni` | float | yes |
| 8 | `DIL_BM_Fe` | float | yes |
| 9 | `DIL_BM_SiO2` | float | yes |
| 10 | `DIL_BM_MgO` | float | yes |
| 11 | `DIL_BM_Co` | float | yes |
| 12 | `DIL_BM_Cr2O3` | float | yes |
| 13 | `DIL_TOS_MC` | float | yes |
| 14 | `DIL_TOS_Ni` | float | yes |
| 15 | `DIL_TOS_Fe` | float | yes |
| 16 | `DIL_TOS_SiO2` | float | yes |
| 17 | `DIL_TOS_MgO` | float | yes |
| 18 | `DIL_TOS_Co` | float | yes |
| 19 | `DIL_TOS_Cr2O3` | float | yes |
| 20 | `DIL_PROP_BM_Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | DATE | MATERIAL | ORIGIN_PIT | CONTRACTOR_PILE | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_BM_Co | DIL_BM_Cr2O3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-06 08:46:58.357000 | 2024-03-29 | SAP | CBB | RIM | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 | 0.726825405092407 |
| 2026-07-06 08:46:58.357000 | 2024-03-30 | SAP | CBB | RIM | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 | 0.726825405092407 |
| 2026-07-06 08:46:58.357000 | 2024-03-31 | SAP | CBB | RIM | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 | 0.726825405092407 |
| 2026-07-06 08:46:58.357000 | 2024-04-01 | SAP | CBB | RIM | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 | 0.726825405092407 |
| 2026-07-06 08:46:58.357000 | 2024-04-02 | SAP | CBB | RIM | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 | 0.726825405092407 |

*(first 12 of 20 columns shown)*

</details>

### `WBN_DATABASE`.`RECLASSIFICATION`

- **Rows**: 7,789
- **Flags**: none
- **Date column**: `SURVEY MONTH` — 1899-12-30 00:00:00 to 2026-07-23 00:00:00

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `RECL` | nvarchar(10) | no |
| 2 | `DOME` | nvarchar(255) | no |
| 3 | `TYPE` | nvarchar(255) | yes |
| 4 | `SURVEY MONTH` | datetime | yes |
| 5 | `OLD_RECL` | nvarchar(10) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| RECL | DOME | TYPE | SURVEY MONTH | OLD_RECL |
|---|---|---|---|---|
| SAP* | A | POS | 2022-09-01 00:00:00 | HGS* |
| WCO* | AA | POS | 2021-03-01 00:00:00 | WCO* |
| SAP* | AA.01.2302 | POS | 2023-02-01 00:00:00 | HGS* |
| SAP* | AA.01.2303 | POS | 2023-03-01 00:00:00 | VHGS* |
| SAP* | AA.02.2302 | POS | 2023-02-01 00:00:00 | HGS* |

</details>

### `WBN_DATABASE`.`EQUIPMENTS`

- **Rows**: 7,221
- **Flags**: TRUCK
- *redacted columns: SERIAL_NO*

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | nvarchar(50) | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `ID_EQ` | nvarchar(50) | yes |
| 4 | `OWNER` | nvarchar(50) | yes |
| 5 | `SERIAL_NO` 🔒 | nvarchar(255) | yes |
| 6 | `TYPE` | nvarchar(50) | yes |
| 7 | `DIGIT` | int | yes |
| 8 | `MANUFACTURER` | nvarchar(50) | yes |
| 9 | `MODEL` | nvarchar(50) | yes |
| 10 | `CAPACITY` | int | yes |
| 11 | `NB_TYRES` | int | yes |
| 12 | `BUILD_YEAR` | int | yes |
| 13 | `DIVISION` | nvarchar(50) | yes |
| 14 | `NEW_ID_EQ` | nvarchar(50) | yes |
| 15 | `HEAVY_LIGHT` | varchar(5) | no |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | ID_EQ | OWNER | SERIAL_NO | TYPE | DIGIT | MANUFACTURER | MODEL | CAPACITY | NB_TYRES | BUILD_YEAR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ATC-AC-301 | ATC | ATC-P3-GKT-01 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |
| ATC-AC-302 | ATC | ATC-P3-GKT-02 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |
| ATC-AC-303 | ATC | ATC-P3-GKT-03 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |
| ATC-AC-304 | ATC | ATC-P3-GKT-04 |  |  | Air Conditioner |  | GREE | 型号：GWC-12MOO5 1.5P |  |  | 2023 |
| ATC-AC-305 | ATC | ATC-P3-GKT-05 |  |  | Air Conditioner |  | GREE | 型号：GWC-12MOO5 1.5P |  |  | 2023 |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`FENI_REQUESTS`

- **Rows**: 7,196
- **Flags**: col:TIME
- **Date column**: `DATE_REQUESTS_BY_IWIP` — 2025-07-01 00:00:00 to 2026-05-29 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `STOCK_ID` | nvarchar(255) | yes |
| 3 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 4 | `DESTINATION_ID` | nvarchar(255) | yes |
| 5 | `SHIFT_REQUESTS` | nvarchar(255) | yes |
| 6 | `DATE_REQUESTS_BY_IWIP` | datetime | yes |
| 7 | `WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | STOCK_ID | ORIGIN_AREA | DESTINATION_ID | SHIFT_REQUESTS | DATE_REQUESTS_BY_IWIP | WMT |
|---|---|---|---|---|---|---|
| 43 | TF.G.1344 | TOS_TF_MTM_01 | TF-M.06 | 1 | 2025-08-01 00:00:00 |  |
| 44 | TF.G.1334 | TOS_TF_08 | TF-H.06 | 1 | 2025-08-01 00:00:00 |  |
| 45 | TF.G.1335 | TOS_TF_MTM_01 | TF-Q.15 | 1 | 2025-08-01 00:00:00 |  |
| 46 | BLB.G.4559 | TOS_BLB_03 | BLB-W.65 | 1 | 2025-08-01 00:00:00 |  |
| 47 | TF.A.4735 | TOS_TF_STM_01 | TF-U1.117 | 1 | 2025-08-01 00:00:00 |  |

</details>

### `WBN_DATABASE`.`QS_LIMS_RIM_CK`

- **Rows**: 6,131
- **Flags**: col:TIME
- **Date column**: `FETCH_DATE` — 2026-06-10 11:32:21 to 2026-07-27 19:30:04

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `DATE` | datetime | yes |
| 3 | `JOB_QC` | nvarchar(255) | yes |
| 4 | `SAMPLE_ID` | nvarchar(50) | no |
| 5 | `Ni` | float | yes |
| 6 | `Co` | float | yes |
| 7 | `AL2O3` | float | yes |
| 8 | `CaO` | float | yes |
| 9 | `Cr2O3` | float | yes |
| 10 | `Fe2O3` | float | yes |
| 11 | `TFe` | float | yes |
| 12 | `MgO` | float | yes |
| 13 | `MnO` | float | yes |
| 14 | `P2O5` | float | yes |
| 15 | `SiO2` | float | yes |
| 16 | `SiO2/MgO` | float | yes |
| 17 | `C` | float | yes |
| 18 | `MC` | float | yes |
| 19 | `DATE_RECEIVED` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | DATE | JOB_QC | SAMPLE_ID | Ni | Co | AL2O3 | CaO | Cr2O3 | Fe2O3 | TFe | MgO |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-10 11:32:21.677000 | 2025-11-13 00:00:00 | IWIP-BLB-2921 | BLB-14891 | 1.664 | 0.07 | 2.34 | 0.16 | 1.67 | 32.4 | 22.68 | 18.78 |
| 2026-06-10 11:32:21.677000 | 2025-11-13 00:00:00 | IWIP-BLB-2921 | BLB-14892 | 1.641 | 0.07 | 2.29 | 0.16 | 1.68 | 31.21 | 21.84 | 19.22 |
| 2026-06-10 11:32:21.677000 | 2025-11-13 00:00:00 | IWIP-BLB-2921 | BLB-14893 | 1.745 | 0.093 | 2.48 | 0.12 | 1.68 | 34.59 | 24.2 | 19.52 |
| 2026-06-10 11:32:21.677000 | 2025-11-13 00:00:00 | IWIP-BLB-2921 | BLB-14893GD | 1.748 | 0.094 | 2.45 | 0.12 | 1.65 | 34.62 | 24.22 | 19.61 |
| 2026-06-10 11:32:21.677000 | 2025-11-13 00:00:00 | IWIP-BLB-2922 | BLB-14894 | 1.269 | 0.198 | 6.4 | 0.08 | 3.1 | 63.29 | 44.29 | 2.75 |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`DARONNE_Htemp`

- **Rows**: 5,812
- **Flags**: col:EQUIP, col:STATUS, col:TIME
- **Date column**: `DATE` — 2026-05-01 00:00:00 to 2026-06-30 00:00:00

<details><summary>19 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `CONTRACTOR` | nvarchar(50) | no |
| 5 | `ACTIVITY` | nvarchar(50) | no |
| 6 | `MATERIAL` | nvarchar(50) | no |
| 7 | `TRUCK_ID` | nvarchar(50) | yes |
| 8 | `TIME_LOADED` | time | yes |
| 9 | `TIME_EMPTY` | time | yes |
| 10 | `RIT` | int | yes |
| 11 | `ORIGIN_AREA` | nvarchar(50) | yes |
| 12 | `ORIGIN_ID` | nvarchar(50) | yes |
| 13 | `DESTINATION_AREA` | nvarchar(50) | yes |
| 14 | `DESTINATION_ID` | nvarchar(50) | yes |
| 15 | `KG_LOADED` | float | yes |
| 16 | `KG_EMPTY` | float | yes |
| 17 | `KG_NET` | float | yes |
| 18 | `WMT` | float | yes |
| 19 | `CUM_WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | ACTIVITY | MATERIAL | TRUCK_ID | TIME_LOADED | TIME_EMPTY | RIT | ORIGIN_AREA | ORIGIN_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 11912321 | 2026-05-01 00:00:00 | 1 | RIM | DIRECT | SAP | N049 | 10:41:08 | 11:57:08 | 1 | TOS_BLB_11 | BLB.G.6939 |
| 11912324 | 2026-05-01 00:00:00 | 1 | RIM | DIRECT | SAP | N038 | 11:00:11 | 12:04:20 | 1 | TOS_BLB_11 | BLB.G.6939 |
| 11912325 | 2026-05-01 00:00:00 | 1 | RIM | DIRECT | SAP | R307 | 11:08:04 | 12:25:40 | 1 | TOS_BLB_11 | BLB.G.6939 |
| 11912346 | 2026-05-01 00:00:00 | 1 | RIM | DIRECT | SAP | R316 | 14:21:53 | 15:38:43 | 1 | TOS_BLB_11 | BLB.G.6939 |
| 11912355 | 2026-05-01 00:00:00 | 1 | RIM | DIRECT | SAP | R690 | 15:56:44 | 17:01:17 | 1 | TOS_BLB_11 | BLB.G.6939 |

*(first 12 of 19 columns shown)*

</details>

### `WBN_DATABASE`.`EQUIPMENTS_OLD`

- **Rows**: 5,658
- **Flags**: TRUCK

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | nvarchar(50) | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `ID_EQ` | nvarchar(50) | yes |
| 4 | `OWNER` | nvarchar(50) | yes |
| 5 | `TYPE` | nvarchar(50) | yes |
| 6 | `DIGIT` | int | yes |
| 7 | `MANUFACTURER` | nvarchar(50) | yes |
| 8 | `MODEL` | nvarchar(50) | yes |
| 9 | `CAPACITY` | int | yes |
| 10 | `NB_TYRES` | int | yes |
| 11 | `BUILD_YEAR` | int | yes |
| 12 | `DIVISION` | nvarchar(50) | yes |
| 13 | `NEW_ID_EQ` | nvarchar(50) | yes |
| 14 | `HEAVY_LIGHT` | varchar(5) | no |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | ID_EQ | OWNER | TYPE | DIGIT | MANUFACTURER | MODEL | CAPACITY | NB_TYRES | BUILD_YEAR | DIVISION |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CKB-MTM-C-481 | CKB | MTM-C-481 | WBN | DT | 481 | SHACMAN | X3000 | 40 | 12 |  | HAULING |
| CKB-MTM-C-482 | CKB | MTM-C-482 | WBN | DT | 482 | SHACMAN | X3000 | 40 | 12 |  | HAULING |
| CKB-MTM-C-483 | CKB | MTM-C-483 | WBN | DT | 483 | SHACMAN | X3000 | 40 | 12 |  | HAULING |
| CKB-MTM-C-484 | CKB | MTM-C-484 | WBN | DT | 484 | SHACMAN | X3000 | 40 | 12 |  | HAULING |
| CKB-MTM-C-485 | CKB | MTM-C-485 | WBN | DT | 485 | SHACMAN | X3000 | 40 | 12 |  | HAULING |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`WMT_FOR_3RD_PARTY`

- **Rows**: 5,529
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE_VERIFICATION` — 2023-12-13 00:00:00 to 2026-07-20 00:00:00

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE_VERIFICATION` | datetime | yes |
| 3 | `STOCK_TYPE` | nvarchar(50) | no |
| 4 | `DOME` | nvarchar(50) | yes |
| 5 | `CONTRACTOR` | nvarchar(50) | yes |
| 6 | `WMT ORIGINAL` | float | yes |
| 7 | `RATE APPLIED` | float | yes |
| 8 | `WMT TOTAL` | float | yes |
| 9 | `CLAIM` | datetime | yes |
| 10 | `ACTIVITY` | nvarchar(50) | yes |
| 11 | `DESTINATION` | nvarchar(50) | yes |
| 12 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE_VERIFICATION | STOCK_TYPE | DOME | CONTRACTOR | WMT ORIGINAL | RATE APPLIED | WMT TOTAL | CLAIM | ACTIVITY | DESTINATION | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 13789 | 2023-12-13 00:00:00 | POS | AA.393.A | AWK | 20939.859000000004 |  |  |  | HAULAGE |  | Yes |
| 13790 | 2023-12-13 00:00:00 | POS | AA.398 | AWK | 36808.27399999992 |  |  |  | HAULAGE |  | Yes |
| 13791 | 2023-12-13 00:00:00 | POS | AA.399 | AWK | 89565.8889999999 |  |  |  | HAULAGE |  | Yes |
| 13792 | 2023-12-13 00:00:00 | POS | AA.401 | AWK | 38696.96999999998 |  |  |  | HAULAGE |  | Yes |
| 13793 | 2023-12-13 00:00:00 | POS | AA.402 | AWK | 50260.889999999956 |  |  |  | HAULAGE |  | Yes |

</details>

### `WBN_DATABASE`.`BATCH`

- **Rows**: 4,931
- **Flags**: none

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `BATCH ID` | nvarchar(255) | yes |
| 3 | `SAMPLE ID` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | BATCH ID | SAMPLE ID |
|---|---|---|
| 1 | AA.23 | A.1287 |
| 2 | AA.23 | A.1288 |
| 3 | AA.23 | A.1289 |
| 4 | BB.14 | B.735 |
| 5 | BB.14 | B.736 |

</details>

### `WBN_DATABASE`.`DRAFTS`

- **Rows**: 4,848
- **Flags**: col:EQUIP, col:TIME
- **Date column**: `DATE` — 2023-10-03 00:00:00 to 2026-07-07 00:00:00

<details><summary>30 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `JOB_ID` | nvarchar(255) | yes |
| 3 | `DOME` | nvarchar(255) | yes |
| 4 | `MC` | float | yes |
| 5 | `Ni` | float | yes |
| 6 | `Co` | float | yes |
| 7 | `MgO` | float | yes |
| 8 | `CaO` | float | yes |
| 9 | `Fe` | float | yes |
| 10 | `P` | float | yes |
| 11 | `S` | float | yes |
| 12 | `SiO2` | float | yes |
| 13 | `Al2O3` | float | yes |
| 14 | `Cr2O3` | float | yes |
| 15 | `Fe2O3` | float | yes |
| 16 | `K2O` | float | yes |
| 17 | `MnO` | float | yes |
| 18 | `Na2O` | float | yes |
| 19 | `P2O5` | float | yes |
| 20 | `TiO2` | float | yes |
| 21 | `LOI` | float | yes |
| 22 | `WMT` | float | yes |
| 23 | `CONTRACTOR` | nvarchar(255) | yes |
| 24 | `NB_SUBLOT` | float | yes |
| 25 | `TRUCKS` | float | yes |
| 26 | `VERIFICATION` | nvarchar(50) | yes |
| 27 | `VERIFICATION_DATE` | datetime | yes |
| 28 | `DESTINATION` | nvarchar(50) | yes |
| 29 | `PROCESS_TYPE` | nvarchar(50) | yes |
| 30 | `ORIGIN` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | JOB_ID | DOME | MC | Ni | Co | MgO | CaO | Fe | P | S | SiO2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-19 00:00:00 |  | ABM.259.0125 | 34.163102424840574 | 1.2495778241860467 | 0.05742417810915057 | 23.905360541038906 | 0.21477823199556806 | 16.651766892293868 | 0.0 | 0.09188759689922481 | 34.996935031462364 |
| 2025-05-19 00:00:00 |  | ABM.281.0225 | 34.67 | 1.1886527599999999 | 0.05829717056737649 | 23.992360079999997 | 0.4663624515086303 | 17.354537349999998 | 0.0 | 0.0706 | 33.85857077 |
| 2025-05-19 00:00:00 |  | ACM.321.0125 | 32.33434038267875 | 1.3285653599999998 | 0.06929144592889691 | 22.359863165 | 0.167721575426469 | 19.652422110000003 | 0.0006331877729257642 | 0.09755 | 32.495909069999996 |
| 2025-05-19 00:00:00 |  | ACM.374.0225 | 34.165720771850175 | 1.3093430400000001 | 0.06419184785977476 | 20.87405709 | 0.2037062290938002 | 18.604967870000003 | 0.0 | 0.06965 | 35.87399526 |
| 2025-05-19 00:00:00 |  | ADM.263.0225 | 35.64505782814033 | 1.3021092 | 0.09315827367562418 | 18.984800900000003 | 0.09705055346554717 | 23.109470110000004 | 0.0 | 0.18105000000000002 | 30.20924552 |

*(first 12 of 30 columns shown)*

</details>

### `WBN_DATABASE`.`TOS_SURVEY`

- **Rows**: 4,804
- **Flags**: col:TIME
- **Date column**: `DATE` — 2026-03-28 00:00:00 to 2026-07-10 00:00:00

<details><summary>18 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SURVEY_TYPE` | nvarchar(255) | yes |
| 2 | `SURVEY_WEEK` | float | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `PILE_ID` | nvarchar(255) | yes |
| 5 | `LCM` | float | yes |
| 6 | `BCM` | float | yes |
| 7 | `WMT` | float | yes |
| 8 | `TC` | float | yes |
| 9 | `CATEGORY` | nvarchar(255) | yes |
| 10 | `LOCATION` | nvarchar(255) | yes |
| 11 | `MATERIAL` | nvarchar(255) | yes |
| 12 | `2NDHAUL` | datetime | yes |
| 13 | `SHIFT` | nvarchar(255) | yes |
| 14 | `Ni` | float | yes |
| 15 | `SUBPIT` | nvarchar(255) | yes |
| 16 | `PIT` | nvarchar(255) | yes |
| 17 | `ID` | bigint | no |
| 18 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SURVEY_TYPE | SURVEY_WEEK | DATE | PILE_ID | LCM | BCM | WMT | TC | CATEGORY | LOCATION | MATERIAL | 2NDHAUL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MONTHLY | 13.0 | 2026-03-28 00:00:00 | KRENE.I.2840 | 1654.585 | 1390.4075630252103 | 2888.2389136055194 | 2450.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |
| MONTHLY | 13.0 | 2026-03-28 00:00:00 | KRENE.I.2839 | 1601.295 | 1345.6260504201682 | 2795.2160397694593 | 2100.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |
| MONTHLY | 13.0 | 2026-03-28 00:00:00 | KRENE.I.2835 | 1731.849 | 1455.335294117647 | 3023.1107342861233 | 2310.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |
| MONTHLY | 13.0 | 2026-03-28 00:00:00 | KRENE.I.2804 | 475.889 | 399.90672268907565 | 830.710497409814 | 875.0 | ABM | TOS_KRENE_05 | NON-GRIZZLY |  |
| MONTHLY | 13.0 | 2026-03-28 00:00:00 | KRENE.I.2843 | 1411.355 | 1186.012605042017 | 2463.6573109944293 | 1785.0 | ABM | TOS_KRENE_06 | NON-GRIZZLY |  |

*(first 12 of 18 columns shown)*

</details>

### `WBN_DATABASE`.`S123_STOCK_SHAPE`

- **Rows**: 4,785
- **Flags**: col:TIME
- **Date column**: `UPDATE_DATE` — 2026-07-27 17:45:52 to 2026-07-27 17:45:52
- *redacted columns: name*

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `UPDATE_DATE` | datetime | yes |
| 2 | `OBJECTID` | int | no |
| 3 | `FID` | int | yes |
| 4 | `name` 🔒 | nvarchar(255) | yes |
| 5 | `CreationDa` | datetime | yes |
| 6 | `Creator` | nvarchar(255) | yes |
| 7 | `EditDate` | datetime | yes |
| 8 | `geom` | geography(max) | yes |
| 9 | `new_dome_i` | nvarchar(255) | yes |
| 10 | `old_dome_i` | nvarchar(255) | yes |
| 11 | `menggantik` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| UPDATE_DATE | OBJECTID | FID | name | CreationDa | Creator | EditDate | geom | new_dome_i | old_dome_i | menggantik |
|---|---|---|---|---|---|---|---|---|---|---|
|  | -725 |  | [REDACTED] | 2025-10-28 00:00:00 |  | 2025-10-28 00:00:00 | <128 bytes> | ABM.459 | ADM.458 | JULIEN |
|  | -724 |  | [REDACTED] | 2025-10-28 00:00:00 |  | 2025-10-28 00:00:00 | <176 bytes> | ABM.458 | LD_POS12_035 | JULIEN |
|  | -723 |  | [REDACTED] | 2025-10-28 00:00:00 |  | 2025-10-28 00:00:00 | <144 bytes> | ACM.666 | LD_POS12_034 | JULIEN |
|  | -722 |  | [REDACTED] | 2025-10-28 00:00:00 |  | 2025-10-28 00:00:00 | <128 bytes> | ACM.665 | AB.496 | JULIEN |
|  | -721 |  | [REDACTED] | 2025-10-28 00:00:00 |  | 2025-10-28 00:00:00 | <128 bytes> | ABM.457 | ACM.461 | JULIEN |

</details>

### `WBN_DATABASE`.`STOCK_STATUS_HAULAGE_GGSHEET`

- **Rows**: 4,750
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `UPDATE_DATETIME` — 2026-07-18 15:04:49 to 2026-07-18 15:04:49
- *redacted columns: Unnamed: 12*

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `No` | float | yes |
| 2 | `dome` | varchar(max) | yes |
| 3 | `Location` | varchar(max) | yes |
| 4 | `Open Date` | varchar(max) | yes |
| 5 | `Close Date` | varchar(max) | yes |
| 6 | `Material Type` | varchar(max) | yes |
| 7 | `Status Haulage` | varchar(max) | yes |
| 8 | `Contractor` | varchar(max) | yes |
| 9 | `Map` | varchar(max) | yes |
| 10 | `OLD DOME` | varchar(max) | yes |
| 11 | `REMARK` | varchar(max) | yes |
| 12 | `Unnamed: 12` 🔒 | varchar(max) | yes |
| 13 | `UPDATE_DATETIME` | datetime | yes |
| 14 | `OPEN_DATE` | datetime | yes |
| 15 | `CLOSE_DATE` | datetime | yes |
| 16 | `numbers` | varchar(max) | yes |
| 17 | `DOME_CLEANED` | varchar(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| No | dome | Location | Open Date | Close Date | Material Type | Status Haulage | Contractor | Map | OLD DOME | REMARK | Unnamed: 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | LGS.SWG6 | GOMDI |  | 12/9/2022 | Non Grizzly | Close |  |  |  |  |  |
| 2.0 | LGS.SW10 | CLIFF DUMP |  | 12/9/2022 | Non Grizzly | Close |  |  |  |  |  |
| 3.0 | LGS.KR8 | GOMDI |  |  | Non Grizzly | Close |  |  |  |  |  |
| 4.0 | LGS.KR15 | POS 10 |  |  | Non Grizzly | Close |  |  |  |  |  |
| 5.0 | LGS.CUU2 | GOMDI |  | 15/11/2022 | Non Grizzly | Close |  |  |  |  |  |

*(first 12 of 17 columns shown)*

</details>

### `WBN_DATABASE`.`STOCK_REQUESTS`

- **Rows**: 4,735
- **Flags**: col:TIME
- **Date column**: `DATE_SHARE` — 2025-06-20 00:00:00 to 2025-08-03 00:00:00

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE_SHARE` | datetime | no |
| 3 | `ORIGIN_ID` | nvarchar(55) | no |
| 4 | `WMT` | float | yes |
| 5 | `DESTINATION_ID` | nvarchar(55) | yes |
| 6 | `DESTINATION_AREA` | nvarchar(55) | yes |
| 7 | `SHIFT_REQUESTS` | float | yes |
| 8 | `DATE_REQUESTS_BY_IWIP` | datetime | yes |
| 9 | `REQUESTED_BY_IWIP` | nvarchar(55) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE_SHARE | ORIGIN_ID | WMT | DESTINATION_ID | DESTINATION_AREA | SHIFT_REQUESTS | DATE_REQUESTS_BY_IWIP | REQUESTED_BY_IWIP |
|---|---|---|---|---|---|---|---|---|
| 22535 | 2025-06-20 00:00:00 | BLB.D.842 | 1578.0 |  |  |  |  | NO |
| 22536 | 2025-06-21 00:00:00 | TF.G.931 | 600.0 | TF-C.04
 | FENI C |  | 2025-06-23 00:00:00 | YES |
| 22537 | 2025-06-21 00:00:00 | KR.I.2033 | 510.0 | KR-Q.10 | FENI Q |  | 2025-06-22 00:00:00 | YES |
| 22538 | 2025-06-21 00:00:00 | BLB.D.848 | 736.0 |  |  |  |  | NO |
| 22539 | 2025-06-21 00:00:00 | BLB.D.850 | 1750.0 |  |  |  |  | NO |

</details>

### `WBN_DATABASE`.`3RD_PARTY_ACTIVITIES_RECLAIM`

- **Rows**: 4,138
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-12-22 00:00:00 to 2026-07-26 00:00:00

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | nvarchar(50) | yes |
| 4 | `SAMPLED_INC` | int | yes |
| 5 | `SAMPLE_TO_PREPARATION` | int | yes |
| 6 | `PREPARED_WET_SAMPLE` | int | yes |
| 7 | `LOT_TO_OVEN` | int | yes |
| 8 | `PULP_PREPARATION` | int | yes |
| 9 | `ANALYSIS` | int | yes |
| 10 | `MP_SAMPLING` | int | yes |
| 11 | `MP_TRANSPORT` | int | yes |
| 12 | `MP_WET_PREPARATION` | int | yes |
| 13 | `MP_DRY_PREP` | int | yes |
| 14 | `MP_ANALYSIS` | int | yes |
| 15 | `CONTRACTOR` | nvarchar(50) | yes |
| 16 | `REMARK` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | SAMPLED_INC | SAMPLE_TO_PREPARATION | PREPARED_WET_SAMPLE | LOT_TO_OVEN | PULP_PREPARATION | ANALYSIS | MP_SAMPLING | MP_TRANSPORT | MP_WET_PREPARATION |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-12-22 00:00:00 | Day | 71 | 204 |  |  |  |  | 29 | 4 |  |
| 2 | 2024-12-22 00:00:00 | Night | 830 | 998 |  |  |  |  | 39 | 4 |  |
| 3 | 2024-12-23 00:00:00 | Day | 431 | 245 |  |  |  |  | 39 | 4 |  |
| 4 | 2024-12-23 00:00:00 | Night | 424 | 206 | 300 |  |  |  | 38 | 4 |  |
| 5 | 2024-12-24 00:00:00 | Day | 516 | 393 | 460 |  |  |  | 26 | 4 | 17 |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`REQUEST`

- **Rows**: 3,920
- **Flags**: col:TIME
- **Date column**: `DATE` — 2021-01-01 00:00:00 to 2026-07-01 00:00:00

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DOME` | nvarchar(255) | no |
| 2 | `DATE` | datetime | yes |
| 3 | `REQUEST` | nvarchar(255) | no |
| 4 | `COMPANY` | nvarchar(255) | yes |
| 5 | `SALES_%` | float | yes |
| 6 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DOME | DATE | REQUEST | COMPANY | SALES_% | REMARK |
|---|---|---|---|---|---|
| A | 2021-06-27 00:00:00 | SOLD | LAN |  |  |
| AA.01.2302 | 2023-02-01 00:00:00 | SOLD | MKUI |  |  |
| AA.02.2302 | 2023-02-01 00:00:00 | SOLD | KRS |  |  |
| AA.02.2303 | 2023-03-01 00:00:00 | SOLD | LIPE |  |  |
| AA.100 | 2022-07-01 00:00:00 | SOLD | AMI |  |  |

</details>

### `WBN_DATABASE`.`ORE STOCK SALES`

- **Rows**: 3,800
- **Flags**: col:STATUS, col:TIME
- **Date column**: `Date of Sales` — 2021-02-20 00:00:00 to 2025-06-20 00:00:00

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `STOCK TYPE` | nvarchar(255) | yes |
| 2 | `POS CODE` | nvarchar(255) | no |
| 3 | `Date of Sales` | datetime | yes |
| 4 | `Month Of Sales` | datetime | no |
| 5 | `Buying Plant` | nvarchar(255) | yes |
| 6 | `WMT` | float | yes |
| 7 | `Ni` | float | yes |
| 8 | `Fe` | float | yes |
| 9 | `Co` | float | yes |
| 10 | `Al2O3` | float | yes |
| 11 | `CaO` | float | yes |
| 12 | `Cr2O3` | float | yes |
| 13 | `Fe2O3` | float | yes |
| 14 | `MgO` | float | yes |
| 15 | `MnO` | float | yes |
| 16 | `P2O5` | float | yes |
| 17 | `SiO2` | float | yes |
| 18 | `SiO2/MgO` | float | yes |
| 19 | `MC` | float | yes |
| 20 | `Sales Status` | nvarchar(255) | yes |
| 21 | `SALES TYPE` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| STOCK TYPE | POS CODE | Date of Sales | Month Of Sales | Buying Plant | WMT | Ni | Fe | Co | Al2O3 | CaO | Cr2O3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD LOGISTIC | A | 2021-06-27 00:00:00 | 2021-06-27 00:00:00 | LAN |  | 1.86902156653813 | 20.4325901944593 | 0.0798903913094793 | 1.17205676990552 | 29.2311733826314 | 17.3731473565229 |
| LOGISTIC | AA.01.2302 | 2023-02-25 00:00:00 | 2023-02-01 00:00:00 | MKUI |  | 2.42973473711497 | 10.2938526065106 | 0.0380049690338602 | 0.0 | 0.0 | 0.0 |
| LOGISTIC | AA.02.2302 | 2023-02-25 00:00:00 | 2023-02-01 00:00:00 | KRS |  | 2.34419053789572 | 11.2568025189263 | 0.0395312338199279 | 0.0 | 0.0 | 0.0 |
| LOGISTIC | AA.02.2303 | 2023-03-29 00:00:00 | 2023-03-01 00:00:00 | LIPE |  | 1.83715823048451 | 9.17345533606934 | 0.0230249448120945 | 0.0 | 0.0 | 0.0 |
| LOGISTIC | AA.100 | 2022-07-28 00:00:00 | 2022-07-01 00:00:00 | AMI |  | 1.68 | 11.25 | 0.06 | 0.0 | 0.0 | 0.0 |

*(first 12 of 21 columns shown)*

</details>

### `WBN_DATABASE`.`S123_TOS_STATUS`

- **Rows**: 3,589
- **Flags**: col:STATUS, col:TIME
- **Date column**: `UPDATE_DATE` — 2026-07-27 17:45:32 to 2026-07-27 17:45:32

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `UPDATE_DATE` | datetime | yes |
| 2 | `OBJECTID` | bigint | yes |
| 3 | `GLOBALID` | nvarchar(50) | yes |
| 4 | `EDIT_DATE` | datetime | yes |
| 5 | `PILE_ID` | nvarchar(50) | yes |
| 6 | `STOCK_AREA` | nvarchar(50) | yes |
| 7 | `OLD_PILE` | nvarchar(50) | yes |
| 8 | `STOCKPILE_TEAM` | nvarchar(50) | yes |
| 9 | `DATE` | date | yes |
| 10 | `STATUS` | nvarchar(50) | yes |
| 11 | `GEOM` | geography(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| UPDATE_DATE | OBJECTID | GLOBALID | EDIT_DATE | PILE_ID | STOCK_AREA | OLD_PILE | STOCKPILE_TEAM | DATE | STATUS | GEOM |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-27 17:45:32.200000 | 3 | dc5e4a1c-cdfa-4428-8009-3ea38b323e0d | 2025-11-26 20:41:45 | TF.A.6482 | TOS_TF_011 | TF A.6434 | Hadi Suorayitno | 2025-11-26 |  | <224 bytes> |
| 2026-07-27 17:45:32.200000 | 4 | e6e33a54-85fb-455b-875e-02e845b5c7ae | 2025-11-26 20:49:36 | TF.A.6490 | TOS_TF_STM_04 | TF.A.6433 | Hadi Suorayitno | 2025-11-26 |  | <128 bytes> |
| 2026-07-27 17:45:32.200000 | 5 | 871bb19c-2325-4c89-8fc6-e457710507bb | 2025-11-26 20:53:37 | TF.A.6493 | TOS_TF_013 | TF.A.6453 | Hadi Suorayitno | 2025-11-26 |  | <160 bytes> |
| 2026-07-27 17:45:32.200000 | 6 | b83028f7-751f-43ec-868f-f017ab65a431 | 2025-11-26 21:04:23 | TF.A.6495 | TOS_TF_012 | TF.A.6468 | Hadi Suorayitno | 2025-11-26 |  | <192 bytes> |
| 2026-07-27 17:45:32.200000 | 7 | 34397e05-0a94-46d5-895d-e14f05f09f2c | 2025-11-26 21:07:38 | TF.A.6496 | TOS_TF_STM_04 | TF.A.6464 | Hadi Suorayitno | 2025-11-26 |  | <192 bytes> |

</details>

### `FMS_DB`.`FMS_GEOFENCES`

- **Rows**: 3,490
- **Flags**: col:COORD, col:STATUS, col:TIME
- *redacted columns: NAME*

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `GF_ID` | nvarchar(20) | no |
| 2 | `NAME` 🔒 | nvarchar(200) | yes |
| 3 | `TYPE` | nvarchar(50) | yes |
| 4 | `SHAPE` | nvarchar(20) | yes |
| 5 | `LATLNGS` | nvarchar(max) | yes |
| 6 | `CENTER_LAT` | float | yes |
| 7 | `CENTER_LNG` | float | yes |
| 8 | `RADIUS` | float | yes |
| 9 | `PIT_ID` | nvarchar(50) | yes |
| 10 | `PILE_ID` | nvarchar(100) | yes |
| 11 | `TOS_STATUS` | nvarchar(50) | yes |
| 12 | `TOS_AREA` | nvarchar(100) | yes |
| 13 | `TOS_PIT` | nvarchar(50) | yes |
| 14 | `ELEVATIONS` | nvarchar(max) | yes |
| 15 | `SURVEY_DATE` | nvarchar(50) | yes |
| 16 | `CREATED` | bigint | yes |
| 17 | `CREATED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| GF_ID | NAME | TYPE | SHAPE | LATLNGS | CENTER_LAT | CENTER_LNG | RADIUS | PIT_ID | PILE_ID | TOS_STATUS | TOS_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 154060c9 | [REDACTED] | pit | polygon | [[0.5437292501612401, 127.97145366668703], [0.54561743998... | 0.5442323690220499 | 127.97149362235236 |  | blb |  |  |  |
| 1b1fc35c | [REDACTED] | water | circle |  | 0.5089639244430295 | 127.90353477001192 | 15.747326650500089 |  |  |  | KR |
| 2224ef93 | [REDACTED] | pit | polygon | [[0.672296355154009, 127.96677589416505], [0.666460266644... | 0.6684771509582391 | 127.97630310058595 | 1710.6506851987322 | kr |  |  |  |
| 2e938c89 | [REDACTED] | pit | polygon | [[0.5444158647114278, 127.94471740722658], [0.54175523289... | 0.5203757263736456 | 127.93700122833255 |  | cbb |  |  |  |
| 557c7057 | [REDACTED] | loading | point |  | 0.5255983067422261 | 127.93205738067628 |  |  |  |  |  |

*(first 12 of 17 columns shown)*

</details>

### `FMS_DB`.`RADIO_REPROGRAM_TRACK`

- **Rows**: 3,478
- **Flags**: GPS, col:EQUIP, col:STATUS, col:TIME
- *redacted columns: SERIAL_NO, NAME_USER*

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `No` | float | yes |
| 2 | `CONTRACTOR` | nvarchar(255) | yes |
| 3 | `AREA` | nvarchar(255) | yes |
| 4 | `DEPARTMENT` | nvarchar(255) | yes |
| 5 | `EQUIPMENT_TYPE` | nvarchar(255) | yes |
| 6 | `EQUIPMENT_ID` | nvarchar(255) | yes |
| 7 | `RADIO_TYPE` | nvarchar(255) | yes |
| 8 | `BRAND` | nvarchar(255) | yes |
| 9 | `MODEL` | nvarchar(255) | yes |
| 10 | `SERIAL_NO` 🔒 | nvarchar(255) | yes |
| 11 | `IS_REPROGRAMMABLE` | nvarchar(255) | yes |
| 12 | `REPROGRAM_STATUS` | nvarchar(255) | yes |
| 13 | `REPROGRAM_DATE` | nvarchar(255) | yes |
| 14 | `TECHNICIAN` | nvarchar(255) | yes |
| 15 | `SUB_TEAM` | nvarchar(255) | yes |
| 16 | `NAME_USER` 🔒 | nvarchar(255) | yes |
| 17 | `POSITION` | nvarchar(255) | yes |
| 18 | `RADIO_ID` | nvarchar(255) | yes |
| 19 | `REMARKS` | nvarchar(255) | yes |
| 20 | `STATUS_RAW` | nvarchar(255) | yes |
| 21 | `SOURCE_FILE` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| No | CONTRACTOR | AREA | DEPARTMENT | EQUIPMENT_TYPE | EQUIPMENT_ID | RADIO_TYPE | BRAND | MODEL | SERIAL_NO | IS_REPROGRAMMABLE | REPROGRAM_STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 149.0 | RIM | GS | Transport | DT | L038 | Radio RIG | MOTOROLA | XIR M8668i V BS | [REDACTED] | Yes | NOT YET |
| 173.0 | RIM | GS | Transport | DT | L040 | Radio RIG | MOTOROLA | XIR M6660 VHF | [REDACTED] | Yes | NOT YET |
| 194.0 | RIM | GS | Transport | DT | L042 | Radio RIG | MOTOROLA | XIR M3688 VHF | [REDACTED] | Yes | NOT YET |
| 226.0 | RIM | GS | Transport | DT | L043 | Radio RIG | MOTOROLA | XIR M8668i VHF | [REDACTED] | Yes | NOT YET |
| 185.0 | RIM | GS | Transport | DT | L044 | Radio RIG | MOTOROLA | XIR M8668i V BS | [REDACTED] | Yes | NOT YET |

*(first 12 of 21 columns shown)*

</details>

### `FMS_DB`.`FMS_TOS_STATUS`

- **Rows**: 3,404
- **Flags**: col:STATUS, col:TIME
- **Date columns**: `UPDATE_DATE`, `EDIT_DATE`, `DATE`, `FMS_UPDATED_AT`

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `UPDATE_DATE` | datetime | yes |
| 2 | `OBJECTID` | bigint | yes |
| 3 | `GLOBALID` | nvarchar(50) | yes |
| 4 | `EDIT_DATE` | datetime | yes |
| 5 | `PILE_ID` | nvarchar(50) | yes |
| 6 | `STOCK_AREA` | nvarchar(50) | yes |
| 7 | `OLD_PILE` | nvarchar(50) | yes |
| 8 | `STOCKPILE_TEAM` | nvarchar(50) | yes |
| 9 | `DATE` | date | yes |
| 10 | `STATUS` | nvarchar(50) | yes |
| 11 | `GEOM` | geography(max) | yes |
| 12 | `FMS_UPDATED_BY` | nvarchar(100) | yes |
| 13 | `FMS_UPDATED_AT` | datetime | yes |
| 14 | `FMS_PREV_STATUS` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| UPDATE_DATE | OBJECTID | GLOBALID | EDIT_DATE | PILE_ID | STOCK_AREA | OLD_PILE | STOCKPILE_TEAM | DATE | STATUS | GEOM | FMS_UPDATED_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  | BLB.G.6136 | TOS.BLB.10 |  |  | 2026-12-31 | STEP_3_TRANSFER_(HAULAGE) |  |  |
|  |  |  |  | BLB.G.6998 | TOS.BLB.11 |  |  | 2026-06-16 | STEP_2_COMPLETE_(PRODUCTION) |  |  |
|  |  |  |  | E/TF.A.742 | TOS_TF_011 |  |  | 2026-11-02 | STEP_3_TRANSFER_(HAULAGE) |  |  |
|  |  |  |  | BLB.G.7000 | TOS.BLB.11 |  |  | 2026-06-21 | STEP_2_COMPLETE_(PRODUCTION) |  |  |
|  |  |  |  | TF.A.7700 | other |  |  | 2026-03-12 | STEP_3_TRANSFER_(HAULAGE) |  | rdinkelmann |

*(first 12 of 14 columns shown)*

</details>

### `WBN_DATABASE`.`CRUSHER_BLENDING_DATA`

- **Rows**: 3,332
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 to 2025-05-25

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CRUSHER_LOCATION` | nvarchar(50) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | nvarchar(50) | yes |
| 5 | `STOCK_LOCATION` | nvarchar(50) | yes |
| 6 | `PILE_ID` | nvarchar(50) | yes |
| 7 | `NB_BUCKET` | float | yes |
| 8 | `BF` | float | yes |
| 9 | `BCM` | float | yes |
| 10 | `STOCK_ID` | nvarchar(50) | yes |
| 11 | `STOCK_PRODUCT` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CRUSHER_LOCATION | DATE | SHIFT | STOCK_LOCATION | PILE_ID | NB_BUCKET | BF | BCM | STOCK_ID | STOCK_PRODUCT |
|---|---|---|---|---|---|---|---|---|---|---|
| 351 | CRUSHER LOYPOLOY KM16 | 2024-10-01 | 1 | KM16 Line 1 | 0-1 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 352 | CRUSHER LOYPOLOY KM16 | 2024-10-01 | 1 | KM16 Line 1 | 1-2 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 353 | CRUSHER LOYPOLOY KM16 | 2024-10-01 | 1 | KM16 Line 1 | 2-3 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 354 | CRUSHER LOYPOLOY KM16 | 2024-10-01 | 1 | KM16 Line 2 | BC 5-7 Line 2 | 35.0 | 3.0 | 105.0 | BC 5-7 Line 2 | BASE COURSE 5-7 |
| 355 | CRUSHER LOYPOLOY KM16 | 2024-10-01 | 1 | KM16 Line 3 | 0-1 Line 3 | 28.0 | 3.0 | 84.0 | BC 2-3 Line 3 | BASE COURSE 2-3 |

</details>

### `WBN_DATABASE`.`3RD_PARTY_ACTIVITIES`

- **Rows**: 3,312
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2026-07-26 00:00:00

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | no |
| 3 | `SHIFT` | nvarchar(10) | yes |
| 4 | `SAMPLED_INC` | int | yes |
| 5 | `SAMPLE_TO_PREPARATION` | int | yes |
| 6 | `PREPARED_WET_SAMPLE` | int | yes |
| 7 | `LOT_TO_OVEN` | int | yes |
| 8 | `PULP_PREPARATION` | int | yes |
| 9 | `ANALYSIS` | int | yes |
| 10 | `MP_SAMPLING` | int | yes |
| 11 | `MP_TRANSPORT` | int | yes |
| 12 | `MP_WET_PREPARATION` | int | yes |
| 13 | `MP_DRY_PREP` | int | yes |
| 14 | `MP_ANALYSIS` | int | yes |
| 15 | `CONTRACTOR` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | SAMPLED_INC | SAMPLE_TO_PREPARATION | PREPARED_WET_SAMPLE | LOT_TO_OVEN | PULP_PREPARATION | ANALYSIS | MP_SAMPLING | MP_TRANSPORT | MP_WET_PREPARATION |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1493 | 2024-10-01 00:00:00 | Day | 1235 | 1200 | 1300 | 14 | 5 | 14 | 34 | 4 | 16 |
| 1494 | 2024-10-01 00:00:00 | Night | 1465 | 744 | 2077 | 18 | 20 | 8 | 32 | 4 | 34 |
| 1495 | 2024-10-01 00:00:00 | Day | 879 | 942 | 580 |  | 8 | 4 | 23 | 1 | 10 |
| 1496 | 2024-10-01 00:00:00 | Night | 789 | 534 | 700 | 32 |  |  | 21 | 1 | 14 |
| 1497 | 2024-10-02 00:00:00 | Day | 1469 | 1129 | 1344 | 14 | 14 | 2 | 32 | 4 | 42 |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`HAUL_ROAD_STA`

- **Rows**: 3,122
- **Flags**: PLAN, ROAD
- *redacted columns: NAME*

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `OBJECTID` | float | yes |
| 2 | `NAME` 🔒 | varchar(max) | yes |
| 3 | `LAYER` | varchar(max) | yes |
| 4 | `ELEVATION` | varchar(max) | yes |
| 5 | `DIRECTION` | varchar(50) | no |
| 6 | `IDLINK` | varchar(max) | yes |
| 7 | `SectionKM` | float | no |
| 8 | `CONTRACTOR` | nvarchar(50) | yes |
| 9 | `DISP.ROAD` | nvarchar(50) | yes |
| 10 | `wkt` | varchar(max) | yes |
| 11 | `GEOM` | geography(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| OBJECTID | NAME | LAYER | ELEVATION | DIRECTION | IDLINK | SectionKM | CONTRACTOR | DISP.ROAD | wkt | GEOM |
|---|---|---|---|---|---|---|---|---|---|---|
| 2311.0 | [REDACTED] | 1 | 0 | BLB | BLB2+450 | 2.45 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9687637645520368 0.4830631126541097 0.000000... | <30 bytes> |
| 2312.0 | [REDACTED] | 1 | 0 | BLB | BLB2+475 | 2.475 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9685336777824602 0.4832058462774921 0.000000... | <30 bytes> |
| 2313.0 | [REDACTED] | 1 | 0 | BLB | BLB2+500 | 2.5 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9683332107633476 0.4833077965207324 0.000000... | <30 bytes> |
| 2314.0 | [REDACTED] | 1 | 0 | BLB | BLB2+525 | 2.525 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9681261370139111 0.4833953465815817 0.000000... | <30 bytes> |
| 2315.0 | [REDACTED] | 1 | 0 | BLB | BLB2+550 | 2.55 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9679134755693610 0.4834680669407412 0.000000... | <30 bytes> |

</details>

### `FMS_DB`.`FMS_TMS_TOKEN`

- **Rows**: 2,872
- **Flags**: col:TIME
- **Date column**: `DATETIME` — 2026-03-02 07:44:00 to 2026-07-27 18:30:04
- *redacted columns: FMS_TOKEN*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATETIME` | datetime | yes |
| 2 | `FMS_USER` | nvarchar(50) | yes |
| 3 | `FMS_TOKEN` 🔒 | nvarchar(500) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATETIME | FMS_USER | FMS_TOKEN |
|---|---|---|
| 2026-03-24 14:33:58.940000 | WBN | [REDACTED] |
| 2026-03-25 16:09:01.550000 | WBN | [REDACTED] |
| 2026-03-25 16:19:06.947000 | WBN | [REDACTED] |
| 2026-03-25 17:14:52.233000 | WBN | [REDACTED] |
| 2026-03-02 07:44:00 | WBN | [REDACTED] |

</details>

### `WBN_DATABASE`.`Calendar_For_Exploitation`

- **Rows**: 2,665
- **Flags**: col:TIME
- **Date column**: `DATE` — 2019-09-12 00:00:00 to 2026-12-28 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | no |
| 2 | `YEAR` | float | yes |
| 3 | `MONTH` | float | yes |
| 4 | `WEEK` | float | yes |
| 5 | `exercice` | nvarchar(255) | yes |
| 6 | `NBDAYS` | float | yes |
| 7 | `MONTH_SALES` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | YEAR | MONTH | WEEK | exercice | NBDAYS | MONTH_SALES |
|---|---|---|---|---|---|---|
| 2019-09-12 00:00:00 | 2019.0 | 9.0 | 37.0 | 19-M09 | 16.0 |  |
| 2019-09-13 00:00:00 | 2019.0 | 9.0 | 37.0 | 19-M09 | 16.0 |  |
| 2019-09-14 00:00:00 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |
| 2019-09-15 00:00:00 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |
| 2019-09-16 00:00:00 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |

</details>

### `WBN_DATABASE`.`S123_ENVIRO_TSS`

- **Rows**: 2,366
- **Flags**: col:COORD, col:TIME
- **Date column**: `LAST_UPDATE` — 2026-06-08 06:53:31 to 2026-06-25 14:53:36

<details><summary>33 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | datetime | no |
| 2 | `OBJECTID` | bigint | yes |
| 3 | `GLOBALID` | varchar(max) | yes |
| 4 | `WAKTU` | datetime | yes |
| 5 | `PENGAMATAN` | varchar(max) | yes |
| 6 | `COLLECTOR` | varchar(max) | yes |
| 7 | `STATION` | varchar(max) | yes |
| 8 | `LAT_CALC` | varchar(max) | yes |
| 9 | `LONG_CALC` | varchar(max) | yes |
| 10 | `GEOPOINT_CALC` | varchar(max) | yes |
| 11 | `NILAI_TSS` | float | yes |
| 12 | `LIMIT_TSS_CALC` | varchar(max) | yes |
| 13 | `LIMIT_TSS` | float | yes |
| 14 | `TINGGI_LUMPUR` | varchar(max) | yes |
| 15 | `AKTIVITAS_DI_SEDPOND` | varchar(max) | yes |
| 16 | `NILAI_RAINFALL` | float | yes |
| 17 | `FE_GW` | float | yes |
| 18 | `MN_GW` | float | yes |
| 19 | `CHROM2_GW` | float | yes |
| 20 | `NI_GW` | float | yes |
| 21 | `CO_GW` | float | yes |
| 22 | `SULFIDE_GW` | float | yes |
| 23 | `CREATIONDATE` | datetime | yes |
| 24 | `CREATOR` | varchar(max) | yes |
| 25 | `EDITDATE` | datetime | yes |
| 26 | `EDITOR` | varchar(max) | yes |
| 27 | `NILAI_TURBIDITY` | float | yes |
| 28 | `TEMUAN_DEVIATION` | varchar(max) | yes |
| 29 | `TINDAKAN_DEVIATION` | varchar(max) | yes |
| 30 | `NILAI_PH` | float | yes |
| 31 | `KETINGGIAN_AIR` | varchar(max) | yes |
| 32 | `X` | float | yes |
| 33 | `Y` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | OBJECTID | GLOBALID | WAKTU | PENGAMATAN | COLLECTOR | STATION | LAT_CALC | LONG_CALC | GEOPOINT_CALC | NILAI_TSS | LIMIT_TSS_CALC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-25 14:53:36.623000 | 26 | e8f042b3-1fad-47a4-87b8-569db3bd2e06 | 2026-04-01 11:55:00 | sediment pond | Enviro | SP-LDKR-02 | 0.654405 | 127.981682 | 0.654405 127.981682 0 0 | 1.0 | 100 |
| 2026-06-25 14:53:36.623000 | 27 | 83bc098e-5b58-41e1-81ad-c6dc3ecee4f0 | 2026-04-01 11:57:00 | sediment pond | Enviro | SP-KM35-01 | 0.648415 | 127.97249 | 0.648415 127.97249 0 0 | 20.0 | 200 |
| 2026-06-25 14:53:36.623000 | 28 | 4765cc55-981a-4db3-8b4a-3f8a4193bc1e | 2026-04-01 11:57:00 | sungai (river) | Enviro | Sungai Ake Sangaji - Hilir | 0.783461 | 128.050757 | 0.783461 128.050757 0 0 | 7.0 | 50 |
| 2026-06-25 14:53:36.623000 | 29 | 9b797551-f226-4938-863a-3081ceddbddb | 2026-04-01 11:58:00 | sungai (river) | Enviro | Sungai Ake Sangaji - Hulu | 0.796117 | 128.013722 | 0.796117 128.013722 0 0 | 3.0 | 50 |
| 2026-06-25 14:53:36.623000 | 30 | 489184f1-e2ba-410f-8844-b6fccc2a2d75 | 2026-02-15 12:00:00 | kimia air tanah (groundwater chemical) | Enviro | SP-1 | 0.803003572 | 128.025663 | 0.803003572 128.025663 0 0 | 28.0 | 200 |

*(first 12 of 33 columns shown)*

</details>

### `WBN_DATABASE`.`MINING_PLAN_3MRMP`

- **Rows**: 2,295
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2026-03-29 to 2026-05-14

<details><summary>45 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `YEAR` | float | yes |
| 2 | `QUARTER` | nvarchar(255) | yes |
| 3 | `MONTH` | float | yes |
| 4 | `DEPOSIT` | nvarchar(255) | yes |
| 5 | `PIT` | nvarchar(255) | yes |
| 6 | `SUBPIT` | nvarchar(255) | yes |
| 7 | `IPPKH` | nvarchar(255) | yes |
| 8 | `BM_ESTIMATION` | nvarchar(255) | yes |
| 9 | `CONTRACTOR` | nvarchar(255) | yes |
| 10 | `MATERIAL` | nvarchar(255) | yes |
| 11 | `FSAP_RSAP` | nvarchar(255) | yes |
| 12 | `CATEGORY` | nvarchar(255) | yes |
| 13 | `CATEGORY_ROM` | nvarchar(255) | yes |
| 14 | `BLOCK_ID` | nvarchar(255) | yes |
| 15 | `BCM` | float | yes |
| 16 | `WMT_INSITU` | float | yes |
| 17 | `DMT` | float | yes |
| 18 | `Ni` | float | yes |
| 19 | `Fe` | float | yes |
| 20 | `SM` | float | yes |
| 21 | `SiO2` | float | yes |
| 22 | `MgO` | float | yes |
| 23 | `Co` | float | yes |
| 24 | `Al2O3` | float | yes |
| 25 | `Cr2O3` | float | yes |
| 26 | `MnO` | float | yes |
| 27 | `H2O` | float | yes |
| 28 | `DRY_DENSITY` | float | yes |
| 29 | `WET_DENSITY` | float | yes |
| 30 | `MINE_RECOVERY_1` | float | yes |
| 31 | `MINE_RECOVERY_2` | float | yes |
| 32 | `BCM_ROM` | float | yes |
| 33 | `WMT_ROM` | float | yes |
| 34 | `DMT_ROM` | float | yes |
| 35 | `Ni_DILUTION` | float | yes |
| 36 | `Fe_DILUTION` | float | yes |
| 37 | `MgO_DILUTION` | float | yes |
| 38 | `H2O_DILUTION` | float | yes |
| 39 | `Ni_ROM` | float | yes |
| 40 | `Fe_ROM` | float | yes |
| 41 | `MgO_ROM` | float | yes |
| 42 | `H2O_ROM` | float | yes |
| 43 | `REMARK` | nvarchar(255) | yes |
| 44 | `TYPE` | varchar(20) | yes |
| 45 | `DATE` | date | yes |

</details>

<details><summary>Sample rows (5)</summary>

| YEAR | QUARTER | MONTH | DEPOSIT | PIT | SUBPIT | IPPKH | BM_ESTIMATION | CONTRACTOR | MATERIAL | FSAP_RSAP | CATEGORY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | SAP | FSAP | HGO |
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | WST | FSAP/RSAP | WCO |
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | WST | WST | WST |
| 2026.0 | Q1 | 2.0 | TOFU | TOFU | TOFU |  | Resource | STM | WST | WST | WST |
| 2026.0 | Q1 | 2.0 | TOFU | TOFU | TOFU |  | Resource | STM | WST | WST | BRK |

*(first 12 of 45 columns shown)*

</details>

### `WBN_DATABASE`.`blasting_parameters`

- **Rows**: 2,081
- **Flags**: col:TIME
- **Date column**: `blast_date` — 2023-02-01 00:00:00 to 2025-05-04 00:00:00

<details><summary>20 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `year` | nvarchar(255) | yes |
| 3 | `month` | nvarchar(255) | yes |
| 4 | `week` | nvarchar(255) | yes |
| 5 | `blast_date` | datetime | yes |
| 6 | `blast_time` | datetime | yes |
| 7 | `blasting_contractor` | nvarchar(255) | yes |
| 8 | `location` | nvarchar(255) | yes |
| 9 | `pit` | nvarchar(255) | yes |
| 10 | `subpit` | nvarchar(255) | yes |
| 11 | `block_id` | nvarchar(255) | yes |
| 12 | `nb_drillholes_used` | int | yes |
| 13 | `type` | nvarchar(255) | yes |
| 14 | `sub_type` | nvarchar(255) | yes |
| 15 | `detonator_lenght_m` | float | yes |
| 16 | `unit` | nvarchar(255) | yes |
| 17 | `qtt_ready` | float | yes |
| 18 | `qtt_used` | float | yes |
| 19 | `qtt_not_used` | float | yes |
| 20 | `comment` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | year | month | week | blast_date | blast_time | blasting_contractor | location | pit | subpit | block_id | nb_drillholes_used |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2023 | Jul | 30 | 2023-07-28 00:00:00 | 1899-12-30 12:30:00 | MBN | Km 37 kaorahai MTM | KR |  |  |  |
| 2 | 2023 | Jul | 30 | 2023-07-28 00:00:00 | 1899-12-30 12:30:00 | MBN | Km 37 kaorahai MTM | KR |  |  |  |
| 3 | 2023 | Jun | 25 | 2023-06-17 00:00:00 | 1899-12-30 13:00:00 | MBN | Km 37 kaorahai MTM | KR |  |  |  |
| 4 | 2023 | Jun | 25 | 2023-06-18 00:00:00 | 1899-12-30 13:00:00 | MBN | Km 37 kaorahai SMA | KR |  |  |  |
| 5 | 2023 | Jun | 25 | 2023-06-18 00:00:00 | 1899-12-30 13:00:00 | MBN | Km 37 kaorahai SMA | KR |  |  |  |

*(first 12 of 20 columns shown)*

</details>

### `WBN_DATABASE`.`EQUIPMENTS_PLAN`

- **Rows**: 2,071
- **Flags**: PLAN, TRUCK, col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-12-29 to 2026-05-14

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `TEAM` | nvarchar(255) | yes |
| 2 | `TYPE` | nvarchar(255) | yes |
| 3 | `DATE` | date | yes |
| 4 | `YEAR` | float | yes |
| 5 | `MONTH` | float | yes |
| 6 | `WEEK` | float | yes |
| 7 | `ACTIVITY` | nvarchar(255) | yes |
| 8 | `ORIGIN` | nvarchar(255) | yes |
| 9 | `CONTRACTOR` | nvarchar(255) | yes |
| 10 | `MATERIAL` | nvarchar(255) | yes |
| 11 | `UNIT_TYPE` | nvarchar(255) | yes |
| 12 | `NB_UNIT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| TEAM | TYPE | DATE | YEAR | MONTH | WEEK | ACTIVITY | ORIGIN | CONTRACTOR | MATERIAL | UNIT_TYPE | NB_UNIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MINING | PLAN | 2026-04-02 | 2026.0 | 4.0 | 14.0 | MINING | TOFU | SMA | ALL | EXCA | 8.0 |
| MINING | PLAN | 2026-04-02 | 2026.0 | 4.0 | 14.0 | MINING | TOFU | SMA | ALL | ADT | 36.0 |
| MINING | PLAN | 2026-04-03 | 2026.0 | 4.0 | 14.0 | MINING | BLB | RIM | ALL | EXCA | 15.0 |
| MINING | PLAN | 2026-04-03 | 2026.0 | 4.0 | 14.0 | MINING | BLB | RIM | ALL | ADT | 43.0 |
| MINING | PLAN | 2026-04-03 | 2026.0 | 4.0 | 14.0 | MINING | KRENE | PPP | ALL | EXCA | 6.0 |

</details>

### `WBN_DATABASE`.`Calendar_Svy_topo_by_deposit`

- **Rows**: 1,815
- **Flags**: col:TIME
- **Date column**: `Date` — 2024-12-28 00:00:00 to 2026-07-20 00:00:00

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PIT` | varchar(50) | yes |
| 2 | `Date` | datetime | yes |
| 3 | `YEAR` | float | yes |
| 4 | `MONTH` | float | yes |
| 5 | `WEEK` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| PIT | Date | YEAR | MONTH | WEEK |
|---|---|---|---|---|
| BLB | 2026-06-06 00:00:00 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-07 00:00:00 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-08 00:00:00 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-09 00:00:00 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-10 00:00:00 | 2026.0 | 6.0 | 24.0 |

</details>

### `WBN_DATABASE`.`DAY_WORKS_PLAN_DAILY`

- **Rows**: 1,611
- **Flags**: PLAN, col:EQUIP, col:STATUS, col:TIME
- **Date column**: `DATE` — 2026-06-28 00:00:00 to 2026-07-27 00:00:00

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `ACTUAL_PLAN` | nvarchar(255) | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `WEEK` | float | yes |
| 5 | `ACTIVITY` | nvarchar(255) | yes |
| 6 | `STATUS` | nvarchar(255) | yes |
| 7 | `AREA` | nvarchar(255) | yes |
| 8 | `SECTION_ROAD` | nvarchar(255) | yes |
| 9 | `LOCATION_JOB` | nvarchar(255) | yes |
| 10 | `EQUIPMENT_TYPE` | nvarchar(255) | yes |
| 11 | `UNIT_TYPE` | nvarchar(255) | yes |
| 12 | `UNIT_ID` | nvarchar(255) | yes |
| 13 | `MAIN_ISSUE` | nvarchar(255) | yes |
| 14 | `ACTION` | nvarchar(255) | yes |
| 15 | `REMARKS` | nvarchar(255) | yes |
| 16 | `UPDATE_DATE` | datetime | yes |
| 17 | `UPDATE_BY` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | ACTUAL_PLAN | DATE | WEEK | ACTIVITY | STATUS | AREA | SECTION_ROAD | LOCATION_JOB | EQUIPMENT_TYPE | UNIT_TYPE | UNIT_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Daily Plan | 2026-06-28 00:00:00 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 23-25 | Dump Truck | Unit | B591 |
| 2 | Daily Plan | 2026-06-29 00:00:00 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 18-21 | Dump Truck | Unit | B591 |
| 3 | Daily Plan | 2026-06-30 00:00:00 | 26.0 | HRM | Maintenance | KR | KM 18-35 | KM 23-25 | Dump Truck | Unit | B591 |
| 4 | Daily Plan | 2026-06-28 00:00:00 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 26-29 | Dump Truck | Unit | B596 |
| 5 | Daily Plan | 2026-06-29 00:00:00 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 30-33 | Dump Truck | Unit | B596 |

*(first 12 of 17 columns shown)*

</details>

### `WBN_DATABASE`.`ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE`

- **Rows**: 1,585
- **Flags**: col:TIME
- **Date column**: `DATE` — 2021-01-01 00:00:00 to 2025-06-01 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DOME` | nvarchar(255) | yes |
| 2 | `AREA` | nvarchar(255) | yes |
| 3 | `WMT` | float | yes |
| 4 | `Ni` | float | yes |
| 5 | `MC` | float | yes |
| 6 | `DATE` | datetime | yes |
| 7 | `COMPANY` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DOME | AREA | WMT | Ni | MC | DATE | COMPANY |
|---|---|---|---|---|---|---|
| ABM.323 | POS 12 EXT | 13545.71 | 1.54733410457485 | 35.0429497620091 | 2025-03-01 00:00:00 | YII |
| ABM.319 | POS 12 EXT | 20211.33 | 1.59041000168567 | 33.5070454868413 | 2025-03-01 00:00:00 | JMNE |
| ADM.324.A | ADM.324.A | 18730.8132103846 | 1.521 | 32.2900000000001 | 2025-03-01 00:00:00 | JMNE |
| ACM.416 | POS 14 | 15526.62 | 1.38 | 34.51 | 2025-03-01 00:00:00 | ANI |
| ADM.355 | POS 11 | 23974.3 | 1.7595147826087 | 34.1125284304989 | 2025-03-01 00:00:00 | ANI |

</details>

### `WBN_DATABASE`.`RSF_PER_LOCATION`

- **Rows**: 1,489
- **Flags**: GPS, col:STATUS, col:TIME
- **Date column**: `DATE` — 2024-10-01 00:00:00 to 2024-12-16 00:00:00

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | nvarchar(50) | yes |
| 4 | `LAYER` | nvarchar(50) | yes |
| 5 | `ELEVATION` | float | yes |
| 6 | `LOCATION` | nvarchar(50) | yes |
| 7 | `ITEM` | nvarchar(50) | yes |
| 8 | `MATERIAL_TYPE` | nvarchar(50) | yes |
| 9 | `Z_MAX` | float | yes |
| 10 | `Z_MIN` | float | yes |
| 11 | `RIT` | float | yes |
| 12 | `STATUS` | nvarchar(50) | yes |
| 13 | `OFFICER` | nvarchar(50) | yes |
| 14 | `REMARK` | nvarchar(50) | yes |
| 15 | `ACTIVITY` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | LAYER | ELEVATION | LOCATION | ITEM | MATERIAL_TYPE | Z_MAX | Z_MIN | RIT | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6181 | 2024-10-01 00:00:00 | DAY | 4 | 70.0 | IF08 | Uncrushed Material | Quarry | 80.08 | 79.92 | 81.0 |  |
| 6182 | 2024-10-01 00:00:00 | DAY | 3 | 70.0 | C22 | Uncrushed Material | Quarry | 73.07 | 72.27 | 81.0 |  |
| 6183 | 2024-10-01 00:00:00 | DAY | 4 | 70.0 | IF01 | Disposal | Dry Stack | 85.58 | 84.02 | 106.0 |  |
| 6184 | 2024-10-01 00:00:00 | DAY | 4 | 70.0 | C02 | Disposal | Dry Stack | 83.02 | 80.37 | 105.0 |  |
| 6185 | 2024-10-01 00:00:00 | DAY | 4 | 70.0 | C01 | Disposal | Dry Stack | 80.59 | 78.06 | 105.0 |  |

*(first 12 of 15 columns shown)*

</details>

### `WBN_DATABASE`.`CLASS2025`

- **Rows**: 1,438
- **Flags**: col:TIME
- **Date column**: `MIN_DATE` — 2024-12-29 00:00:00 to 2025-07-12 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `STOCK_ID` | nvarchar(255) | yes |
| 2 | `SURVEY_CLASS2` | nvarchar(255) | yes |
| 3 | `ORIGIN_PIT` | nvarchar(255) | yes |
| 4 | `WMT` | float | yes |
| 5 | `MIN_DATE` | datetime | yes |
| 6 | `MAX_DATE` | datetime | yes |
| 7 | `Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| STOCK_ID | SURVEY_CLASS2 | ORIGIN_PIT | WMT | MIN_DATE | MAX_DATE | Ni |
|---|---|---|---|---|---|---|
| TF-W.103 | HGS | TF | 6538.14 | 2025-06-09 00:00:00 | 2025-06-10 00:00:00 | 1.7986821721017094 |
| TF-W.104 | HGS | TF | 5652.200000000001 | 2025-06-10 00:00:00 | 2025-06-11 00:00:00 | 1.7802286255704234 |
| TF-W.105 | HGS | TF | 8304.740000000002 | 2025-06-11 00:00:00 | 2025-06-12 00:00:00 | 1.9848248312768537 |
| TF-W.106 | LGS | TF | 7461.999999999999 | 2025-06-12 00:00:00 | 2025-06-14 00:00:00 | 1.4792040019085106 |
| TF-W.107 | HGS | TF | 6005.179999999999 | 2025-06-14 00:00:00 | 2025-06-15 00:00:00 | 1.808015979160441 |

</details>

### `FMS_DB`.`FMS_EQUIPMENTS`

- **Rows**: 1,401
- **Flags**: TRUCK, col:COORD, col:EQUIP, col:TIME
- **Date column**: `FETCH_DATE` — 2026-03-22 15:07:47 to 2026-07-27 14:44:26
- *redacted columns: orgName, imei*

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FETCH_DATE` | datetime | yes |
| 2 | `truckId` | nvarchar(50) | no |
| 3 | `orgName` 🔒 | nvarchar(50) | yes |
| 4 | `plateNumber` | nvarchar(50) | yes |
| 5 | `orgId` | bigint | yes |
| 6 | `imei` 🔒 | bigint | yes |
| 7 | `active` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FETCH_DATE | truckId | orgName | plateNumber | orgId | imei | active |
|---|---|---|---|---|---|---|
| 2026-07-27 14:44:26.340000 | 6916297240046994306 | [REDACTED] | K977 | 7190741736405205894 | [REDACTED] | YES |
| 2026-05-14 14:44:30.313000 | 6921009760640961159 | [REDACTED] | K523 | 7190740880934963462 | [REDACTED] | NO |
| 2026-04-12 14:44:23.520000 | 6922135043012034832 | [REDACTED] | K562 | 7190740352016450440 | [REDACTED] | NO |
| 2026-07-27 14:44:26.340000 | 6922135043045589259 | [REDACTED] | K565 | 7190741736405205894 | [REDACTED] | YES |
| 2026-07-27 14:44:26.340000 | 6922135043045589260 | [REDACTED] | K566 | 7190740352016450440 | [REDACTED] | YES |

</details>

### `WBN_DATABASE`.`CONSOLIDATED SURVEY`

- **Rows**: 1,188
- **Flags**: none

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `YEAR` | float | yes |
| 3 | `MONTH` | float | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `DEPOSIT` | nvarchar(255) | yes |
| 6 | `PIT` | nvarchar(255) | yes |
| 7 | `MATERIAL` | nvarchar(255) | yes |
| 8 | `MATERIAL_ID` | nvarchar(255) | yes |
| 9 | `BCM_SURVEY` | float | yes |
| 10 | `BCM_CLAIM (CLOSE MONTH)` | float | yes |
| 11 | `WMT_SURVEY` | float | yes |
| 12 | `WMT_CLAIM (CLOSE MONTH)` | float | yes |
| 13 | `WET_DENSITY` | float | yes |
| 14 | `COMMENT` | nvarchar(255) | yes |
| 15 | `NEXT_MONTH_CORRECTION` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | YEAR | MONTH | CONTRACTOR | DEPOSIT | PIT | MATERIAL | MATERIAL_ID | BCM_SURVEY | BCM_CLAIM (CLOSE MONTH) | WMT_SURVEY | WMT_CLAIM (CLOSE MONTH) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 480 | 2024.0 | 1.0 | STM | KR | KR | Top Soil | TS | 10718.949 | 10718.949 | 15006.5286 | 15006.5286 |
| 481 | 2024.0 | 1.0 | STM | KR | KR | Over burden | WST | 120173.5520000048 | 120173.5520000048 | 223522.80672000893 | 223522.80672000893 |
| 482 | 2024.0 | 1.0 | STM | KR | KR | Limonite | LIM | 60173.22 | 60173.22 | 114843.20067838336 | 114843.20067838336 |
| 483 | 2024.0 | 1.0 | STM | KR | KR | Saprolite | SAP | 422458.095 | 422458.095 | 888232.711853668 | 888232.711853668 |
| 484 | 2024.0 | 1.0 | SMA | KR | KR | Top Soil | TS | 24159.18593856343 | 24159.18593856343 | 33822.8603139888 | 33822.8603139888 |

*(first 12 of 15 columns shown)*

</details>

### `FMS_DB`.`WT_DAILY_PLAN`

- **Rows**: 1,187
- **Flags**: PLAN, col:EQUIP, col:TIME
- **Date column**: `Shift_Date` — 2026-04-16 to 2026-07-27

<details><summary>10 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `Shift_Date` | date | no |
| 3 | `Vehicle_Number` | varchar(20) | no |
| 4 | `Region` | varchar(10) | no |
| 5 | `KM_From` | int | no |
| 6 | `KM_To` | int | no |
| 7 | `Primary_WF` | varchar(50) | no |
| 8 | `Target_Refills` | int | no |
| 9 | `Created_Date` | datetime | yes |
| 10 | `Breakdown` | varchar(3) | no |

</details>

<details><summary>Sample rows (5)</summary>

| ID | Shift_Date | Vehicle_Number | Region | KM_From | KM_To | Primary_WF | Target_Refills | Created_Date | Breakdown |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-04-17 | SS024 | BLB | 7 | 13 | WF_BLB08 | 6 | 2026-04-17 16:19:48.440000 | No |
| 2 | 2026-04-17 | SS044 | BLB | 13 | 17 | WF_BLB19 | 6 | 2026-04-17 16:19:48.440000 | No |
| 3 | 2026-04-17 | SS045 | TF | 39 | 47 | WF-HR44 | 5 | 2026-04-17 16:19:48.440000 | No |
| 4 | 2026-04-17 | SS075 | CBB | 13 | 17 | WF_CBB15 | 5 | 2026-04-17 16:19:48.440000 | No |
| 5 | 2026-04-17 | SS083 | KR | 18 | 22 | WF-HR-18 | 5 | 2026-04-17 16:19:48.440000 | No |

</details>

### `FMS_DB`.`FMS_UNIT_INSTALLED`

- **Rows**: 1,182
- **Flags**: col:COORD

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PLATE` | nvarchar(60) | no |
| 2 | `ORG` | nvarchar(120) | yes |
| 3 | `FIRST_TS` | bigint | no |
| 4 | `SEEDED` | bit | no |

</details>

<details><summary>Sample rows (5)</summary>

| PLATE | ORG | FIRST_TS | SEEDED |
|---|---|---|---|
| A042 | RIM汽修厂一车间（BIRIBIRI） | 0 | True |
| A843 | RIM运输部 K 车间 | 0 | True |
| A844 | RIM运输部 K 车间 | 0 | True |
| A864 | RIM运输部 K 车间 | 0 | True |
| A865 | RIM汽修厂一车间（BIRIBIRI） | 0 | True |

</details>

### `WBN_DATABASE`.`WATER_MANAGEMENT`

- **Rows**: 1,074
- **Flags**: col:TIME
- **Date column**: `DATE` — 2025-06-24 to 2025-10-07

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | no |
| 3 | `CONTRACTOR` | nvarchar(50) | yes |
| 4 | `PIT` | nvarchar(50) | yes |
| 5 | `PLANT_ID` | nvarchar(50) | yes |
| 6 | `PLANT_TYPE` | nvarchar(50) | yes |
| 7 | `DT_ID` | nvarchar(50) | yes |
| 8 | `LOADING_AREA` | nvarchar(50) | yes |
| 9 | `UNLOADING_AREA` | nvarchar(50) | yes |
| 10 | `MATERIAL` | nvarchar(50) | yes |
| 11 | `RIT` | int | yes |
| 12 | `JOB_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | PIT | PLANT_ID | PLANT_TYPE | DT_ID | LOADING_AREA | UNLOADING_AREA | MATERIAL | RIT | JOB_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 2025-06-24 | SMA | TF | E285 | EXCA | K431 | BBSP01 | BBSP01 | QUARRY | 19 | LOAD & HAUL |
| 11 | 2025-06-24 | SMA | TF | E152 | EXCA | K433 | CBB 3号采石点 | BBSP02 | QUARRY | 3 | LOAD & HAUL |
| 12 | 2025-06-24 | SMA | TF | E152 | EXCA | K447 | CBB 3号采石点 | BBSP02 | QUARRY | 3 | LOAD & HAUL |
| 13 | 2025-06-24 | SMA | TF | E152 | EXCA | K456 | CBB 3号采石点 | BBSP02 | QUARRY | 1 | LOAD & HAUL |
| 14 | 2025-06-24 | SMA | TF | E152 | EXCA | K446 | CBB 3号采石点 | BBSP02 | QUARRY | 1 | LOAD & HAUL |

</details>

### `WBN_DATABASE`.`OLD_prod_correction_factor_ACCESS`

- **Rows**: 957
- **Flags**: none

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `YEAR` | float | no |
| 2 | `MONTH` | float | no |
| 3 | `contractor` | nvarchar(50) | no |
| 4 | `deposit_code` | nvarchar(50) | no |
| 5 | `material` | nvarchar(50) | no |
| 6 | `CF` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| YEAR | MONTH | contractor | deposit_code | material | CF |
|---|---|---|---|---|---|
| 2024.0 | 1.0 | HJS | CAS | LIM | 1.6413906358059558 |
| 2024.0 | 1.0 | HJS | CAS | SAP | 1.3761168641089983 |
| 2024.0 | 1.0 | HJS | CAS | TS | 0.7800243134280763 |
| 2024.0 | 1.0 | HJS | CAS | WST | 0.6869109445781493 |
| 2024.0 | 1.0 | HJS | CBB | LIM | 0.9444206780989958 |

</details>

### `WBN_DATABASE`.`QUARRY_PLAN`

- **Rows**: 935
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2026-06-01 00:00:00 to 2026-07-27 00:00:00

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `TYPE` | varchar(50) | yes |
| 3 | `DATE` | datetime | no |
| 4 | `TEAM` | nvarchar(255) | yes |
| 5 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 6 | `ORIGIN` | nvarchar(255) | yes |
| 7 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 8 | `DESTINATION` | varchar(50) | yes |
| 9 | `MATERIAL` | nvarchar(255) | yes |
| 10 | `BCM` | float | yes |
| 11 | `RIT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | TYPE | DATE | TEAM | ORIGIN_AREA | ORIGIN | DESTINATION_AREA | DESTINATION | MATERIAL | BCM | RIT |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLAN_DELIVERY | 2026-06-29 00:00:00 | HRM | KR | STOCK_KR_ROAD | KR_KM18-35 | KR_KM23-25 | LPA | 30.0 | 2.0 |
| 2 | PLAN_DELIVERY | 2026-06-29 00:00:00 | HRM | KR | STOCK_KR_ROAD | KR_KM18-35 | KR_KM26-28 | LPA | 30.0 | 2.0 |
| 3 | PLAN_DELIVERY | 2026-06-29 00:00:00 | HRM | TF | CRUSHER_TF | TF_KM35-72 | TF_KM61 | LPA | 30.0 | 2.0 |
| 4 | PLAN_DELIVERY | 2026-06-29 00:00:00 | HRM | BLB | CRUSHER_BLB | ROAD COASTAL | CBB_KM16 | LPB | 30.0 | 2.0 |
| 5 | PLAN_DELIVERY | 2026-06-29 00:00:00 | HRM | BLB | CRUSHER_BLB | ROAD COASTAL | BLB_KM9 | LPA | 30.0 | 2.0 |

</details>

### `WBN_DATABASE`.`ROLLING_MINE_PLAN`

- **Rows**: 834
- **Flags**: PLAN, col:TIME
- **Date columns**: `UPDATE`
- **error**: date range: refusing non-read statement: SELECT MIN([UPDATE]), MAX([UPDATE]) FROM [dbo].[ROLLING_MINE_PLAN]

<details><summary>20 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `YEAR` | int | yes |
| 3 | `MONTH` | int | yes |
| 4 | `CONTRACTOR` | nvarchar(50) | yes |
| 5 | `DEPOSIT` | nvarchar(50) | yes |
| 6 | `PIT` | nvarchar(50) | yes |
| 7 | `PIT_ID` | nvarchar(50) | yes |
| 8 | `MATERIAL` | nvarchar(50) | yes |
| 9 | `WMT_ROM` | float | yes |
| 10 | `Ni` | float | yes |
| 11 | `Fe` | float | yes |
| 12 | `Co` | float | yes |
| 13 | `SiO2` | float | yes |
| 14 | `MgO` | float | yes |
| 15 | `MnO` | float | yes |
| 16 | `Cr2O3` | float | yes |
| 17 | `Al2O3` | float | yes |
| 18 | `SM` | float | yes |
| 19 | `MC` | float | yes |
| 20 | `UPDATE` | date | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | YEAR | MONTH | CONTRACTOR | DEPOSIT | PIT | PIT_ID | MATERIAL | WMT_ROM | Ni | Fe | Co |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1746 | 2024 | 1 | RIM | CBB | CBB | CBB | VHGS | 115319.30270995763 |  |  |  |
| 1747 | 2024 | 1 | RIM | CBB | CBB | CBB | HGS | 370370.33032667474 |  |  |  |
| 1748 | 2024 | 1 | RIM | CBB | CBB | CBB | LGS1 | 309195.2954262806 |  |  |  |
| 1749 | 2024 | 1 | RIM | CBB | CBB | CBB | LGS2 | 11305.203698400173 |  |  |  |
| 1750 | 2024 | 1 | RIM | CBB | CBB | CBB | LIM1 | 370474.892866795 |  |  |  |

*(first 12 of 20 columns shown)*

</details>

### `WBN_DATABASE`.`IWIP_REQUESTS_DATE`

- **Rows**: 772
- **Flags**: col:TIME
- **Date column**: `DATE_OUT` — 2025-06-01 00:00:00 to 2026-05-02 00:00:00

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE_OUT` | datetime | yes |
| 3 | `STOCK_ID` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE_OUT | STOCK_ID |
|---|---|---|
| 1 | 2025-06-12 00:00:00 | AB.455 |
| 2 | 2025-06-12 00:00:00 | ACM.477 |
| 3 | 2025-06-12 00:00:00 | ACM.478 |
| 4 | 2025-06-12 00:00:00 | AD.337 |
| 5 | 2025-06-12 00:00:00 | ADM.503 |

</details>

### `WBN_DATABASE`.`TRANSHIPMENT_WBN_ORE`

- **Rows**: 573
- **Flags**: WEIGHBRIDGE, col:TIME
- **Date column**: `DATE` — 2023-04-11 00:00:00 to 2026-07-19 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DOME` | nvarchar(255) | no |
| 2 | `DATE` | datetime | yes |
| 3 | `DESTINATION` | nvarchar(255) | yes |
| 4 | `WMT` | int | yes |
| 5 | `ANTICIPATED` | nvarchar(255) | yes |
| 6 | `GOTBACK` | nvarchar(255) | yes |
| 7 | `TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DOME | DATE | DESTINATION | WMT | ANTICIPATED | GOTBACK | TYPE |
|---|---|---|---|---|---|---|
| AA.396.A | 2023-12-13 00:00:00 | WBN | 20000 | NO |  |  |
| AA.455 | 2024-06-03 00:00:00 | DBNI | 13298 | YES |  |  |
| AA.456 | 2024-06-03 00:00:00 | SNMI | 22919 | YES |  |  |
| AA.458 | 2024-06-09 00:00:00 | WBN | 28036 | NO |  |  |
| AA.463 | 2024-07-17 00:00:00 | DBNI | 29182 | NO |  |  |

</details>

### `WBN_DATABASE`.`ID_DT_HUAFEI`

- **Rows**: 485
- **Flags**: none

<details><summary>1 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID_DT` | nchar(10) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID_DT |
|---|
| K045       |
| K046       |
| K047       |
| K048       |
| K049       |

</details>

### `WBN_DATABASE`.`SUMMARY_SURVEY`

- **Rows**: 460
- **Flags**: none

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CONTRACTOR` | nvarchar(255) | yes |
| 2 | `PIT` | nvarchar(255) | yes |
| 3 | `YEAR` | float | yes |
| 4 | `MONTH` | float | yes |
| 5 | `MATERIAL` | nvarchar(255) | yes |
| 6 | `DENSITY` | float | yes |
| 7 | `TC_WMT` | float | yes |
| 8 | `TC_BCM` | float | yes |
| 9 | `SURVEY_BCM` | float | yes |
| 10 | `SURVEY_WMT` | float | yes |
| 11 | `CF_BCM` | float | yes |
| 12 | `CF_WMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CONTRACTOR | PIT | YEAR | MONTH | MATERIAL | DENSITY | TC_WMT | TC_BCM | SURVEY_BCM | SURVEY_WMT | CF_BCM | CF_WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RIM | TF | 2025.0 | 9.0 | Quarry | 2.15 |  | 0.0 | 0.0 | 0.0 |  |  |
| PPRE | KRENE | 2025.0 | 9.0 | Top Soil | 1.4 | 150885.0 | 107775.0 | 68344.76842105265 | 95682.67578947371 | 0.6341430612020659 | 0.6341430612020659 |
| PPRE | KRENE | 2025.0 | 9.0 | Over burden | 1.86 | 391710.0 | 210596.77419354836 | 89038.27287228365 | 165611.1875424476 | 0.4227902977775589 | 0.4227902977775589 |
| PPRE | KRENE | 2025.0 | 9.0 | Limonite | 1.63 | 39815.0 | 24426.380368098162 | 18442.820319222647 | 30061.79712033291 | 0.7550369740131335 | 0.7550369740131335 |
| PPRE | KRENE | 2025.0 | 9.0 | Saprolite | 2.0940576122820227 | 414985.0 | 198172.6756542125 | 188868.19138744118 | 395500.87389280915 | 0.9530486014983895 | 0.9530486014983894 |

</details>

### `WBN_DATABASE`.`BLASTING_PROD`

- **Rows**: 433
- **Flags**: col:COORD, col:TIME
- **Date column**: `DATE` — 2026-01-02 00:00:00 to 2026-05-27 00:00:00

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DEPOSIT` | nvarchar(255) | yes |
| 2 | `DATE` | datetime | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `MATERIAL` | nvarchar(255) | yes |
| 5 | `AREA_PIT` | nvarchar(255) | yes |
| 6 | `ID_BLASTING` | nvarchar(255) | yes |
| 7 | `HOLE_NUMBER_MBN` | float | yes |
| 8 | `BURDEN` | float | yes |
| 9 | `SPACING` | float | yes |
| 10 | `DEPTH` | float | yes |
| 11 | `CALCULATED_VOLUME` | float | yes |
| 12 | `VOLUME_CLAIM_BCM` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DEPOSIT | DATE | CONTRACTOR | MATERIAL | AREA_PIT | ID_BLASTING | HOLE_NUMBER_MBN | BURDEN | SPACING | DEPTH | CALCULATED_VOLUME | VOLUME_CLAIM_BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kaorahai | 2026-01-03 00:00:00 | RSF | Quarry | KR3 | 16-P5 | 47.0 | 6.0 | 5.5 | 6.838 | 10605.738 | 10605.738 |
| Kaorahai | 2026-01-03 00:00:00 | RSF | Quarry | KR3 | 16-P5 | 19.0 | 3.0 | 3.0 | 3.053 | 522.063 | 522.063 |
| Kaorahai | 2026-01-04 00:00:00 | RIM | Quarry | KRENE 1 | 20 | 30.0 | 7.0 | 6.0 | 5.26 | 6627.599999999999 | 6627.6 |
| Kaorahai | 2026-01-05 00:00:00 | RIM QUARRY | Quarry | KR3 | 5-P3 | 5.0 | 7.0 | 6.0 | 3.42 | 718.1999999999999 | 718.2 |
| Kaorahai | 2026-01-05 00:00:00 | RIM QUARRY | Quarry | KR3 | 5-P3 | 5.0 | 3.0 | 3.0 | 3.12 | 140.4 | 140.4 |

</details>

### `WBN_DATABASE`.`DISPATCH_PLAN_WB`

- **Rows**: 432
- **Flags**: PLAN, WEIGHBRIDGE, col:TIME
- **Date column**: `DATE` — 2026-01-07 00:00:00 to 2026-07-22 00:00:00

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `SHIFT` | float | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `EXCAVATOR` | nvarchar(255) | yes |
| 6 | `DT_UNIT` | nvarchar(255) | yes |
| 7 | `MATERIAL` | nvarchar(255) | yes |
| 8 | `TOS_LOCATION` | nvarchar(255) | yes |
| 9 | `ORIGIN_ID` | nvarchar(255) | yes |
| 10 | `ORIGIN_AREA` | nvarchar(255) | yes |
| 11 | `DESTINATION_ID` | nvarchar(255) | yes |
| 12 | `DESTINATION_AREA` | nvarchar(255) | yes |
| 13 | `WB_ID` | nvarchar(255) | yes |
| 14 | `SAMPLE_HOUSE` | nvarchar(255) | yes |
| 15 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | CONTRACTOR | EXCAVATOR | DT_UNIT | MATERIAL | TOS_LOCATION | ORIGIN_ID | ORIGIN_AREA | DESTINATION_ID | DESTINATION_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-01-07 00:00:00 | 1.0 | RIM | E042 | R945 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 |
| 2 | 2026-01-07 00:00:00 | 1.0 | RIM | E042 | R946 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 |
| 3 | 2026-01-07 00:00:00 | 1.0 | RIM | E042 | R944 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 |
| 4 | 2026-01-07 00:00:00 | 1.0 | RIM | E042 | R943 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 |
| 5 | 2026-01-07 00:00:00 | 1.0 | RIM | E042 | R940 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 |

*(first 12 of 15 columns shown)*

</details>

### `FMS_DB`.`FMS_TRUCK_ASSIGNMENTS`

- **Rows**: 408
- **Flags**: TRUCK, col:EQUIP, col:TIME
- **Date column**: `PLAN_DATE` — 2026-01-07 to 2026-07-22

<details><summary>10 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PLAN_DATE` | date | yes |
| 2 | `SHIFT` | float | yes |
| 3 | `TRUCK` | nvarchar(50) | yes |
| 4 | `PILE` | nvarchar(100) | yes |
| 5 | `EXCAVATOR` | nvarchar(100) | yes |
| 6 | `PIT` | nvarchar(50) | yes |
| 7 | `MATERIAL` | nvarchar(50) | yes |
| 8 | `DESTINATION` | nvarchar(200) | yes |
| 9 | `IMPORTED_AT` | datetime | yes |
| 10 | `IMPORTED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| PLAN_DATE | SHIFT | TRUCK | PILE | EXCAVATOR | PIT | MATERIAL | DESTINATION | IMPORTED_AT | IMPORTED_BY |
|---|---|---|---|---|---|---|---|---|---|
| 2026-01-07 | 1.0 | R707 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.717000 | t |
| 2026-01-07 | 1.0 | R708 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.767000 | t |
| 2026-01-07 | 1.0 | R938 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.813000 | t |
| 2026-01-07 | 1.0 | R939 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.853000 | t |
| 2026-01-07 | 1.0 | R940 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.900000 | t |

</details>

### `WBN_DATABASE`.`COLOR_CHEMICAL`

- **Rows**: 404
- **Flags**: none

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CHEMICAL` | nvarchar(255) | yes |
| 2 | `GRADE_CLASS` | float | yes |
| 3 | `COLOR` | nvarchar(255) | yes |
| 4 | `COLOR_HEXA` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CHEMICAL | GRADE_CLASS | COLOR | COLOR_HEXA |
|---|---|---|---|
| Fe | 85.0 |  | #45ad5a |
| Fe | 86.0 |  | #45ad5a |
| Fe | 87.0 |  | #45ad5a |
| Fe | 88.0 |  | #45ad5a |
| Fe | 89.0 |  | #45ad5a |

</details>

### `WBN_DATABASE`.`WBN_DATABASE_ESSENTIALS`

- **Rows**: 334
- **Flags**: none
- *redacted columns: OBJECT_NAME*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `OBJECT_NAME` 🔒 | nvarchar(50) | yes |
| 3 | `OBJECT_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | OBJECT_NAME | OBJECT_TYPE |
|---|---|---|
| 1 | [REDACTED] |  |
| 2 | [REDACTED] |  |
| 3 | [REDACTED] |  |
| 4 | [REDACTED] |  |
| 5 | [REDACTED] |  |

</details>

### `FMS_DB`.`FMS_HAUL_CYCLES`

- **Rows**: 287
- **Flags**: PLAN, col:COORD, col:EQUIP, col:TIME
- **Date column**: `PLAN_DATE` — 2026-06-26 to 2026-07-24

<details><summary>10 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `CYCLE_ID` | int | no |
| 2 | `TRUCK_PLATE` | nvarchar(50) | yes |
| 3 | `PLAN_DATE` | date | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `PIT` | nvarchar(50) | yes |
| 6 | `TOS_PILE` | nvarchar(100) | yes |
| 7 | `EXCAVATOR` | nvarchar(100) | yes |
| 8 | `DESTINATION` | nvarchar(200) | yes |
| 9 | `MATERIAL` | nvarchar(100) | yes |
| 10 | `DUMP_TS` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| CYCLE_ID | TRUCK_PLATE | PLAN_DATE | SHIFT | PIT | TOS_PILE | EXCAVATOR | DESTINATION | MATERIAL | DUMP_TS |
|---|---|---|---|---|---|---|---|---|---|
| 1 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:40:39.917000 |
| 2 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:40:56.183000 |
| 3 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:42:11.293000 |
| 4 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:42:45.750000 |
| 5 | B279 | 2026-06-27 | 1.0 | BLB |  | M267 | FENI A | SAP | 2026-06-27 08:28:04.793000 |

</details>

### `WBN_DATABASE`.`autoQC_PLAN_NI_CF_OLD`

- **Rows**: 264
- **Flags**: PLAN, col:TIME

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | nvarchar(50) | yes |
| 2 | `YEAR` | int | no |
| 3 | `MONTH` | int | no |
| 4 | `ORIGIN_PIT` | nvarchar(50) | no |
| 5 | `CONTRACTOR_PILE` | nvarchar(50) | no |
| 6 | `MATERIAL` | nvarchar(50) | no |
| 7 | `DIL_BM_MC` | float | yes |
| 8 | `DIL_BM_Ni` | float | yes |
| 9 | `DIL_BM_Fe` | float | yes |
| 10 | `DIL_BM_SiO2` | float | yes |
| 11 | `DIL_BM_MgO` | float | yes |
| 12 | `DIL_BM_Co` | float | yes |
| 13 | `DIL_BM_Cr2O3` | float | yes |
| 14 | `DIL_TOS_MC` | float | yes |
| 15 | `DIL_TOS_Ni` | float | yes |
| 16 | `DIL_TOS_Fe` | float | yes |
| 17 | `DIL_TOS_SiO2` | float | yes |
| 18 | `DIL_TOS_MgO` | float | yes |
| 19 | `DIL_TOS_Co` | float | yes |
| 20 | `DIL_TOS_Cr2O3` | float | yes |
| 21 | `DIL_PROP_BM_Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | YEAR | MONTH | ORIGIN_PIT | CONTRACTOR_PILE | MATERIAL | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_BM_Co |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-06 06:00:29 | 2024 | 4 | CBB | RIM | SAP | 1.0306948167180283 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169938 | 1.423995880053952 | 0.8066875203491504 |
| 2026-07-06 06:00:29 | 2024 | 5 | CBB | RIM | SAP | 1.030694816718028 | 0.9472451622556337 | 0.815924927060261 | 1.0302367428169936 | 1.4239958800539523 | 0.8066875203491504 |
| 2026-07-06 06:00:29 | 2024 | 6 | BLB | RIM | LIM | 0.9804304638213817 | 0.936922048192954 | 1.0680744689999042 | 4.084750266845172 | 5.030829469771627 | 1.653177508195127 |
| 2026-07-06 06:00:29 | 2024 | 6 | CBB | RIM | LIM | 0.9160127803546186 | 0.9208806505999007 | 0.8889803038652276 | 1.5899192882202107 | 2.68370168036901 | 0.8401210696412691 |
| 2026-07-06 06:00:29 | 2024 | 6 | KR | PPP | SAP | 0.8955586054559438 | 0.9386833184174888 | 0.8666429843797457 | 1.0597551810536119 | 1.3508521003849328 | 0.9966751878561748 |

*(first 12 of 21 columns shown)*

</details>

### `WBN_DATABASE`.`DISPATCH HAULAGE TF`

- **Rows**: 264
- **Flags**: PLAN

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `YEAR` | int | yes |
| 3 | `MONTH` | int | yes |
| 4 | `CONTRACTOR` | nvarchar(50) | yes |
| 5 | `TF` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | YEAR | MONTH | CONTRACTOR | TF |
|---|---|---|---|---|
| 1 | 2024 | 3 | GMG | 32.0 |
| 2 | 2024 | 3 | TCI | 42.0 |
| 3 | 2024 | 3 | RIM | 37.0 |
| 4 | 2024 | 3 | SMA | 40.0 |
| 5 | 2024 | 3 | STM | 40.0 |

</details>

### `FMS_DB`.`FMS_QUALITY_DISPATCH`

- **Rows**: 258
- **Flags**: PLAN, col:STATUS, col:TIME
- **Date column**: `PLAN_DATE` — 2026-06-23 to 2026-07-22

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SRC_ID` | int | yes |
| 2 | `PLAN_DATE` | date | yes |
| 3 | `SHIFT` | float | yes |
| 4 | `PIT` | nvarchar(50) | yes |
| 5 | `CONTRACTOR` | nvarchar(100) | yes |
| 6 | `TOS_PILE` | nvarchar(100) | yes |
| 7 | `CATEGORY` | nvarchar(50) | yes |
| 8 | `CATEGORY_2` | nvarchar(50) | yes |
| 9 | `WMT` | float | yes |
| 10 | `Ni_TOS` | float | yes |
| 11 | `Ni_BM` | float | yes |
| 12 | `Ni_Plan` | float | yes |
| 13 | `DOME` | nvarchar(100) | yes |
| 14 | `DESTINATION` | nvarchar(200) | yes |
| 15 | `STATUS` | nvarchar(50) | yes |
| 16 | `EXCA` | nvarchar(100) | yes |
| 17 | `DT` | nvarchar(100) | yes |
| 18 | `HAUL_CONFIDENCE` | nvarchar(100) | yes |
| 19 | `TYPE` | nvarchar(50) | yes |
| 20 | `IMPORTED_AT` | datetime | yes |
| 21 | `IMPORTED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SRC_ID | PLAN_DATE | SHIFT | PIT | CONTRACTOR | TOS_PILE | CATEGORY | CATEGORY_2 | WMT | Ni_TOS | Ni_BM | Ni_Plan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 89718 | 2026-06-24 | 1.0 | BLB | RIM | BLB.G.6921 | HGS | ACM | 5450.0 | 1.6372280701754387 | 1.4288392940285415 | 1.5070908518654038 |
| 89719 | 2026-06-24 | 1.0 | BLB | RIM | BLB.G.6974 | HGS | ABM | 4150.0 | 1.7733999999999999 | 1.6259968447441218 | 1.6746214968344724 |
| 89720 | 2026-06-24 | 1.0 | BLB | RIM | BLB.G.6920 | HGS | ADM | 2850.0 | 1.5080520231213874 | 1.3663864552596718 | 1.4140523601328352 |
| 89721 | 2026-06-24 | 1.0 | BLB | RIM | BLB.G.6928 | WCO | WCO | 2835.0 | 1.52 | 1.1756895893621453 | 1.3215722937268237 |
| 89722 | 2026-06-24 | 1.0 | KRENE | RIM | KRENE.I.3268 | HGS | ADM | 500.0 | 1.639 | 1.54536754335968 | 1.50263698859253 |

*(first 12 of 21 columns shown)*

</details>

### `WBN_DATABASE`.`DISPATCH ROADS OLD`

- **Rows**: 254
- **Flags**: PLAN, ROAD

<details><summary>36 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `TYPE` | nvarchar(255) | yes |
| 2 | `COMPANY` | nvarchar(255) | yes |
| 3 | `MATERIAL` | nvarchar(10) | no |
| 4 | `DISPATCH ZONE` | nvarchar(255) | yes |
| 5 | `ORIGIN` | nvarchar(50) | no |
| 6 | `DESTINATION` | nvarchar(50) | no |
| 7 | `KM ORI` | float | yes |
| 8 | `KM DEST` | float | yes |
| 9 | `DISTANCE GROSS (KM)` | float | yes |
| 10 | `CRD KM0 - KM2,5` | float | yes |
| 11 | `CRD KM2,5 - KM5,5` | float | yes |
| 12 | `CRD KM5,5 - KM7` | float | yes |
| 13 | `CSW KM3 - KM4` | float | yes |
| 14 | `CSW KM4 - KM5,7` | float | yes |
| 15 | `GOMDI KM3,7 - KM3,8` | float | yes |
| 16 | `BLB KM2,5 - KM5,7` | float | yes |
| 17 | `BLB KM5,7 - KM10` | float | yes |
| 18 | `BLB KM17 - KM20` | float | yes |
| 19 | `HFC KM5,5 - KM6,4` | float | yes |
| 20 | `CBB KM7 - KM9` | float | yes |
| 21 | `CBB KM9 - KM15` | float | yes |
| 22 | `CBB KM15 - KM17` | float | yes |
| 23 | `CBBB KM15 - KM17,5` | float | yes |
| 24 | `KR KM7 - KM12` | float | yes |
| 25 | `KR KM12 - KM15` | float | yes |
| 26 | `KR KM15 - KM17` | float | yes |
| 27 | `KR KM17 - KM21` | float | yes |
| 28 | `KR KM21 - KM26` | float | yes |
| 29 | `KR KM26 - KM27` | float | yes |
| 30 | `KR KM27 - KM32` | float | yes |
| 31 | `KR KM32 - KM37` | float | yes |
| 32 | `KR KM37 - KM39` | float | yes |
| 33 | `TF KM39 - KM45` | float | yes |
| 34 | `TF KM45 - KM52` | float | yes |
| 35 | `TF KM52 - KM60` | float | yes |
| 36 | `TF KM60 - KM68` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| TYPE | COMPANY | MATERIAL | DISPATCH ZONE | ORIGIN | DESTINATION | KM ORI | KM DEST | DISTANCE GROSS (KM) | CRD KM0 - KM2,5 | CRD KM2,5 - KM5,5 | CRD KM5,5 - KM7 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| QUARRY | WBN | BC | KR to FeNi U | KR | FENI KM15 | 37.0 | 15.0 | 22.0 | 0.0 | 0.0 | 0.0 |
| QUARRY | WBN | BC | KR to KR | KR | KR | 38.0 | 38.0 | 1.0 |  |  |  |
| QUARRY | WBN | BC | KR to LOYPOLOY | KR | LOYPOLOY | 38.0 | 16.0 | 22.0 |  |  |  |
| QUARRY | WBN | BC | KR to KM 17 | KR | POS 10 | 37.0 | 17.0 | 20.0 | 0.0 | 0.0 | 0.0 |
| QUARRY | WBN | BC | KR to KM 17 | KR | POS 11 | 37.0 | 17.0 | 20.0 | 0.0 | 0.0 | 0.0 |

*(first 12 of 36 columns shown)*

</details>

### `WBN_DATABASE`.`autoHAULAGE_VS_PROD_MONTHLY_CF`

- **Rows**: 223
- **Flags**: PLAN, col:TIME
- **Date column**: `LAST_UPDATE` — 2026-07-27 16:00:12 to 2026-07-27 16:00:12

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `LAST_UPDATE` | datetime | no |
| 2 | `CONTRACTOR` | nvarchar(50) | no |
| 3 | `DATE` | date | no |
| 4 | `PIT` | nvarchar(50) | no |
| 5 | `MATERIAL` | nvarchar(50) | no |
| 6 | `CF` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| LAST_UPDATE | CONTRACTOR | DATE | PIT | MATERIAL | CF |
|---|---|---|---|---|---|
| 2026-07-27 16:00:12 | HJS | 2024-10-01 | CBB | LIM | 1.228251640293323 |
| 2026-07-27 16:00:12 | HJS | 2024-11-01 | CBB | LIM | 1.1292418772563177 |
| 2026-07-27 16:00:12 | HJS | 2024-11-01 | CBB | SAP | 1.0723382894430202 |
| 2026-07-27 16:00:12 | HJS | 2024-12-01 | CBB | LIM | 1.0469020373988278 |
| 2026-07-27 16:00:12 | HJS | 2024-12-01 | CBB | SAP | 1.0372884266136901 |

</details>

### `WBN_DATABASE`.`DISPATCH ROADS`

- **Rows**: 222
- **Flags**: PLAN, ROAD

<details><summary>33 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ORIGIN` | nvarchar(50) | no |
| 2 | `DESTINATION` | nvarchar(50) | no |
| 3 | `DISPATCH ZONE` | nvarchar(255) | yes |
| 4 | `KM ORI` | float | yes |
| 5 | `KM DEST` | float | yes |
| 6 | `DISTANCE GROSS (KM)` | float | yes |
| 7 | `CRD KM0 - KM2,5` | float | yes |
| 8 | `CRD KM2,5 - KM5,5` | float | yes |
| 9 | `CRD KM5,5 - KM7` | float | yes |
| 10 | `CSW KM3 - KM4` | float | yes |
| 11 | `CSW KM4 - KM5,7` | float | yes |
| 12 | `GOMDI KM3,7 - KM3,8` | float | yes |
| 13 | `BLB KM2,5 - KM5,7` | float | yes |
| 14 | `BLB KM5,7 - KM10` | float | yes |
| 15 | `BLB KM17 - KM20` | float | yes |
| 16 | `HFC KM5,5 - KM6,4` | float | yes |
| 17 | `CBB KM7 - KM9` | float | yes |
| 18 | `CBB KM9 - KM15` | float | yes |
| 19 | `CBB KM15 - KM17` | float | yes |
| 20 | `CBBB KM15 - KM17,5` | float | yes |
| 21 | `KR KM7 - KM12` | float | yes |
| 22 | `KR KM12 - KM15` | float | yes |
| 23 | `KR KM15 - KM17` | float | yes |
| 24 | `KR KM17 - KM21` | float | yes |
| 25 | `KR KM21 - KM26` | float | yes |
| 26 | `KR KM26 - KM27` | float | yes |
| 27 | `KR KM27 - KM32` | float | yes |
| 28 | `KR KM32 - KM37` | float | yes |
| 29 | `KR KM37 - KM39` | float | yes |
| 30 | `TF KM39 - KM45` | float | yes |
| 31 | `TF KM45 - KM52` | float | yes |
| 32 | `TF KM52 - KM60` | float | yes |
| 33 | `TF KM60 - KM68` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ORIGIN | DESTINATION | DISPATCH ZONE | KM ORI | KM DEST | DISTANCE GROSS (KM) | CRD KM0 - KM2,5 | CRD KM2,5 - KM5,5 | CRD KM5,5 - KM7 | CSW KM3 - KM4 | CSW KM4 - KM5,7 | GOMDI KM3,7 - KM3,8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BLB | BLB | BLB to BLB | 20.0 | 19.0 | 0.99 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | BSE | BLB to CSTL | 20.0 | 5.0 | 12.9 | 0.0 | 0.186046511627907 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | CRUSHER | BLB to CSTL | 20.0 | 5.0 | 7.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | CUU_KM_10 | BLB to CSTL | 20.0 | 10.0 | 11.899999999999999 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | EOS | BLB to CSTL | 20.0 | 4.0 | 12.0 | 0.0 | 0.125 | 0.0 | 0.0 | 0.0 | 0.0 |

*(first 12 of 33 columns shown)*

</details>

### `WBN_DATABASE`.`HRM_CONTRACT_EQUIPMENT`

- **Rows**: 198
- **Flags**: TRUCK

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `ROAD` | nchar(10) | yes |
| 3 | `SECTION` | nvarchar(50) | yes |
| 4 | `CONTRACTOR` | nchar(10) | yes |
| 5 | `FLEET` | nchar(10) | yes |
| 6 | `UNIT_TYPE` | nvarchar(50) | yes |
| 7 | `DETAIL` | nchar(10) | yes |
| 8 | `QUANTITY` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | ROAD | SECTION | CONTRACTOR | FLEET | UNIT_TYPE | DETAIL | QUANTITY |
|---|---|---|---|---|---|---|---|
| 24 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca 20T   | 1 |
| 25 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca ?     | 0 |
| 26 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | DT |  | 3 |
| 27 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | GRADER |  | 1 |
| 28 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | COMPACTOR |  | 1 |

</details>

### `WBN_DATABASE`.`PROJECTS_SUPERVISION`

- **Rows**: 198
- **Flags**: col:STATUS, col:TIME
- **Date column**: `DATE_START` — 2025-08-21 to 2025-11-24
- *redacted columns: CHECK_AGENT_NAME*

<details><summary>23 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `UPDATE_TYPE` | nvarchar(50) | yes |
| 3 | `SECTION` | nvarchar(50) | yes |
| 4 | `PROJECT_ITEM` | nvarchar(50) | yes |
| 5 | `PROJECT_GROUP` | nvarchar(255) | yes |
| 6 | `PROJECT_CATEGORY` | nvarchar(50) | yes |
| 7 | `PROJECT_DESCRIPTION` | nvarchar(255) | yes |
| 8 | `TASK_ID` | int | yes |
| 9 | `TASK_DESCRIPTION` | nvarchar(255) | yes |
| 10 | `TASK_ASSIGN_TO` | nvarchar(50) | yes |
| 11 | `TASK_PRIORITY` | nvarchar(50) | yes |
| 12 | `TASK_PROGRESS_%` | float | yes |
| 13 | `TASK_STATUS` | nvarchar(50) | yes |
| 14 | `DATE_START` | date | yes |
| 15 | `DATE_END` | date | yes |
| 16 | `DAILY_PLAN_PROGRESS` | float | yes |
| 17 | `LOCATION_AREA` | nvarchar(50) | yes |
| 18 | `LOCATION_DETAILS` | nvarchar(255) | yes |
| 19 | `CHECK_DATE` | datetime | yes |
| 20 | `CHECK_AGENT_NAME` 🔒 | nvarchar(50) | yes |
| 21 | `CHECK_NB_UNIT` | float | yes |
| 22 | `CHECK_IMAGE_ID` | nvarchar(255) | yes |
| 23 | `CHECK_REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | UPDATE_TYPE | SECTION | PROJECT_ITEM | PROJECT_GROUP | PROJECT_CATEGORY | PROJECT_DESCRIPTION | TASK_ID | TASK_DESCRIPTION | TASK_ASSIGN_TO | TASK_PRIORITY | TASK_PROGRESS_% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLAN | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH |  |
| 8 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 90.0 |
| 11 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 95.0 |
| 13 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 97.0 |
| 14 | PLAN | HAULAGE | ROAD |  | CONSTRUCTION | Install tyre di area escape way km 34-35  | 14 | Melakukan pemasangan tyre di area escape way di km 34-35 ... |  | MEDIUM |  |

*(first 12 of 23 columns shown)*

</details>

### `WBN_DATABASE`.`MBAR`

- **Rows**: 173
- **Flags**: none
- **Date column**: `Tanggal` — 2025-01-06 00:00:00 to 2025-09-30 00:00:00

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Tanggal` | datetime | yes |
| 2 | `Pit` | nvarchar(255) | yes |
| 3 | `PIT CODE` | nvarchar(255) | yes |
| 4 | `Type` | nvarchar(255) | yes |
| 5 | `Category` | nvarchar(255) | yes |
| 6 | `Material` | nvarchar(255) | yes |
| 7 | `WMT` | float | yes |
| 8 | `Ni%` | float | yes |
| 9 | `Fe%` | float | yes |
| 10 | `Co%` | float | yes |
| 11 | `MC%` | float | yes |
| 12 | `DMT` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Tanggal | Pit | PIT CODE | Type | Category | Material | WMT | Ni% | Fe% | Co% | MC% | DMT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-02-18 00:00:00 | Bukit Limber Barat | BLB | Ore | Saprolite | Saprolite | 25537.21 | 1.48 | 20.14 | 0.06999999999999999 |  |  |
| 2025-02-18 00:00:00 | Bukit Limber Barat | BLB | Ore | Limonite | Limonite | 54222.28 | 1.1400000000000001 | 43.05 | 0.16 |  |  |
| 2025-02-25 00:00:00 | Biri-Biri | CBB | Ore | Saprolite | Saprolite | 104834.83 | 1.59 | 19.59 | 0.06 |  |  |
| 2025-02-25 00:00:00 | Biri-Biri | CBB | Ore | Limonite | Limonite | 1460.92 | 1.3 | 38.24 | 0.12 |  |  |
| 2025-02-25 00:00:00 | Kao Rahai Barat Daya | KR | Ore | Saprolite | Saprolite | 77032.6 | 1.6500000000000001 | 9.19 | 0.03 |  |  |

</details>

### `WBN_DATABASE`.`HRM_MAJOR_ROADWORK`

- **Rows**: 149
- **Flags**: ROAD, col:EQUIP, col:TIME
- **Date column**: `DATE` — 2024-10-15 to 2024-11-03

<details><summary>11 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `CONTRACTOR` | nvarchar(50) | yes |
| 4 | `KM_START` | int | yes |
| 5 | `KM_END` | int | yes |
| 6 | `FLEET` | nvarchar(50) | yes |
| 7 | `MATERIAL` | nvarchar(max) | yes |
| 8 | `PROGRESS` | nvarchar(max) | yes |
| 9 | `PERCENTAGE` | float | yes |
| 10 | `EQUIPMENT` | nvarchar(max) | yes |
| 11 | `DUE_DATE` | date | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | CONTRACTOR | KM_START | KM_END | FLEET | MATERIAL | PROGRESS | PERCENTAGE | EQUIPMENT | DUE_DATE |
|---|---|---|---|---|---|---|---|---|---|---|
| 64 | 2024-10-15 | STM | 27 | 39 | 3 FLEET | BASE COURSE 
STOCK MATERIAL IN KM 42 | CONTINUE MAINTENANCE REGULAR
LOADING SPOIL
CLEAN UP DRAIN... | 0.89 |  | 2024-10-17 |
| 65 | 2024-10-15 | RIM | 39 | 47 | 4 FLEET | BASE COURSE | CONTUNUE MAINTENANCE REGULAR
LOADING SPOIL | 0.8 | PLAN 4 FLEET, RUNNING TODAY 2X MG, 2X VB, 1X EXCA, 1X WHE... | 2024-10-17 |
| 66 | 2024-10-15 | RIM | 39 | 47 |  |  | MAINTENANCE DRAINAGE | 0.6 |  | 2024-10-17 |
| 67 | 2024-10-15 | STM | 47 | 57 | 5 FLEET | BASE COURSE
BOULDER | CONTINUE JOB
PRIORITY MAJOR ISSUES
MAINTENANCE DRAINAGE
L... | 0.8 | ADDITIONAL MAN POWER 
(OPERATOR AND FOREMAN) | 2024-10-17 |
| 68 | 2024-10-15 | STM | 55 | 60 |  | BASE COURSE
BOULDER | SPREADING THE MATERIALS IN LOADED LINE (KM 55, 600 M)
CBR... | 0.35 | DT FOR HAULING THE MATERIALS 
BY CKB, MTM, STM
CBR TEST (... | 2024-10-17 |

</details>

### `WBN_DATABASE`.`LME`

- **Rows**: 142
- **Flags**: col:TIME
- **Date column**: `DATE` — 2026-01-02 00:00:00 to 2026-07-24 00:00:00

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `LME_Ni_USD` | float | yes |
| 3 | `LME_Ni_3MONTH_USD` | float | yes |
| 4 | `LME_Ni_STOCK_ASSET` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | LME_Ni_USD | LME_Ni_3MONTH_USD | LME_Ni_STOCK_ASSET |
|---|---|---|---|
| 2026-07-24 00:00:00 | 17205.0 | 17430.0 | 267342.0 |
| 2026-07-23 00:00:00 | 17200.0 | 17420.0 | 268548.0 |
| 2026-07-22 00:00:00 | 16940.0 | 17145.0 | 270528.0 |
| 2026-07-21 00:00:00 | 16970.0 | 17160.0 | 272040.0 |
| 2026-07-20 00:00:00 | 16850.0 | 17040.0 | 273222.0 |

</details>

### `WBN_DATABASE`.`LME_GOLD`

- **Rows**: 140
- **Flags**: col:TIME
- **Date column**: `DATE` — 2026-01-02 00:00:00 to 2026-07-24 00:00:00

<details><summary>2 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `GOLD` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | GOLD |
|---|---|
| 2026-07-24 00:00:00 | 112510.0 |
| 2026-07-23 00:00:00 | 113320.0 |
| 2026-07-22 00:00:00 | 114160.0 |
| 2026-07-21 00:00:00 | 112480.0 |
| 2026-07-20 00:00:00 | 111030.0 |

</details>

### `WBN_DATABASE`.`TSS_POINT`

- **Rows**: 121
- **Flags**: col:COORD, col:STATUS

<details><summary>36 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `FID` | float | yes |
| 2 | `FID1` | float | yes |
| 3 | `FID_` | float | yes |
| 4 | `OBJECTID` | float | yes |
| 5 | `Station` | nvarchar(255) | no |
| 6 | `Monitoring` | nvarchar(255) | yes |
| 7 | `Sub_Monito` | nvarchar(255) | yes |
| 8 | `Category` | nvarchar(255) | yes |
| 9 | `MANAGER` | nvarchar(255) | yes |
| 10 | `Area` | nvarchar(255) | yes |
| 11 | `Sub_Area` | nvarchar(255) | yes |
| 12 | `Type` | nvarchar(255) | yes |
| 13 | `Sub_Catego` | nvarchar(255) | yes |
| 14 | `Outfall` | nvarchar(255) | yes |
| 15 | `Quantity` | float | yes |
| 16 | `Mine` | nvarchar(255) | yes |
| 17 | `X` | float | yes |
| 18 | `Y` | float | yes |
| 19 | `Long` | nvarchar(255) | yes |
| 20 | `Lat` | nvarchar(255) | yes |
| 21 | `Scope` | nvarchar(255) | yes |
| 22 | `Frequency_` | nvarchar(255) | yes |
| 23 | `Status_1` | nvarchar(255) | yes |
| 24 | `Status_2` | nvarchar(255) | yes |
| 25 | `Added` | float | yes |
| 26 | `Mark` | nvarchar(255) | yes |
| 27 | `IPPKH_Conv` | nvarchar(255) | yes |
| 28 | `Change__Id` | nvarchar(255) | yes |
| 29 | `Change_Poi` | nvarchar(255) | yes |
| 30 | `Change__St` | nvarchar(255) | yes |
| 31 | `Change__Sc` | nvarchar(255) | yes |
| 32 | `Note` | nvarchar(255) | yes |
| 33 | `Longitude` | nvarchar(255) | yes |
| 34 | `Latitude` | float | yes |
| 35 | `POINT_X` | float | yes |
| 36 | `POINT_Y` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| FID | FID1 | FID_ | OBJECTID | Station | Monitoring | Sub_Monito | Category | MANAGER | Area | Sub_Area | Type |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7.0 |  |  | 25.0 | AP-AM-09 | RIVER | River | River |  | KAO RAHAI | Ake Mein | AMDAL |
| 5.0 |  |  | 16.0 | AP-SL-01 | RIVER | River | River |  | KAO RAHAI | Ake Seloi | AMDAL |
| 6.0 |  |  | 17.0 | AP-SL-04 | RIVER | River | River |  | COASTAL | Creek Ake Seloi | AMDAL |
| 8.0 |  |  | 33.0 | AP-WS-01 | RIVER | River | River |  | COASTAL | Ake Wosea | AMDAL |
| 2.0 |  |  | 12.0 | AP-WS-02 | RIVER | River | River |  | COASTAL | Ake Wosea | AMDAL |

*(first 12 of 36 columns shown)*

</details>

### `WBN_DATABASE`.`TOS_DUMP_COORDINATES`

- **Rows**: 118
- **Flags**: GPS, ROAD
- *redacted columns: TOS_NAME*

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `TOS_PIT` | nvarchar(255) | yes |
| 2 | `TOS_NAME` 🔒 | nvarchar(255) | yes |
| 3 | `TOS_TYPE` | nvarchar(50) | yes |
| 4 | `POINT_X` | int | yes |
| 5 | `POINT_Y` | int | yes |
| 6 | `TOS_NUMBER` | int | yes |
| 7 | `TOS_CONTRACTOR` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| TOS_PIT | TOS_NAME | TOS_TYPE | POINT_X | POINT_Y | TOS_NUMBER | TOS_CONTRACTOR |
|---|---|---|---|---|---|---|
| TF | [REDACTED] | BACKFILL | 391979 | 88233 | 2 |  |
| TF | [REDACTED] | BACKFILL | 392673 | 89292 | 4 |  |
| TF | [REDACTED] | BACKFILL | 392096 | 89862 | 5 |  |
| CBB |  | BMS | 380896 | 57063 | 1 |  |
| CBB |  | BMS | 382658 | 56271 | 6 |  |

</details>

### `WBN_DATABASE`.`TSS_CROSSTABLE`

- **Rows**: 109
- **Flags**: none

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SP_ID` | nvarchar(255) | yes |
| 2 | `RIVER_ID` | nvarchar(255) | yes |
| 3 | `CA_ID` | nvarchar(255) | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `RAINFALL_REPRESENTATIVE` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SP_ID | RIVER_ID | CA_ID | CONTRACTOR | RAINFALL_REPRESENTATIVE |
|---|---|---|---|---|
| AP-SL-01 | BSL-04 (Seloi) |  |  | BUKIT LIMBER 3 |
| AP-SL-04 | BSL-04.2 |  |  |  |
| AP-WS-01 | AP-WS-02 |  |  | CAS6 |
| AP-WS-02 | AP-WS-03 |  |  | BIRI-BIRI_SMA |
| AP-WS-02 | AP-WS-03 |  |  | BIRI-BIRI_SMA |

</details>

### `WBN_DATABASE`.`MINING_FLASH_REPORT_FLEET_PROD`

- **Rows**: 108
- **Flags**: TRUCK, col:TIME
- **Date column**: `DATE` — 2025-11-28 00:00:00 to 2025-11-30 00:00:00

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `DEPOSIT` | nvarchar(255) | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `EXC ID` | nvarchar(255) | yes |
| 6 | `MATERIAL` | nvarchar(255) | yes |
| 7 | `ACT PRODUCTIVITY` | float | yes |
| 8 | `ACT DISTANCE` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | DEPOSIT | CONTRACTOR | SHIFT | EXC ID | MATERIAL | ACT PRODUCTIVITY | ACT DISTANCE |
|---|---|---|---|---|---|---|---|
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | EX-466 | WST | 1715.0 | 940.625 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | EX-501 | SAP | 2450.0 | 800.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | EX-501 | WST | 560.0 | 800.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | EX-502 | SAP | 3430.0 | 836.3636363636364 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | EX-502 | WST | 175.0 | 800.0 |

</details>

### `FMS_DB`.`FMS_DISPATCH_PLAN`

- **Rows**: 105
- **Flags**: PLAN, col:TIME
- **Date column**: `PLAN_DATE` — 2026-06-23 to 2026-07-22

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SRC_ID` | int | yes |
| 2 | `CONTRACTOR` | nvarchar(100) | yes |
| 3 | `PLAN_DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `TYPE` | nvarchar(50) | yes |
| 6 | `MATERIAL` | nvarchar(50) | yes |
| 7 | `COMPANY` | nvarchar(50) | yes |
| 8 | `DISPATCH_ZONE` | nvarchar(200) | yes |
| 9 | `ORIGIN` | nvarchar(100) | yes |
| 10 | `DESTINATION` | nvarchar(100) | yes |
| 11 | `BUYER` | nvarchar(100) | yes |
| 12 | `NB_DT` | float | yes |
| 13 | `TF` | float | yes |
| 14 | `PRODUCTIVITY_TARGET` | float | yes |
| 15 | `IMPORTED_AT` | datetime | yes |
| 16 | `IMPORTED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SRC_ID | CONTRACTOR | PLAN_DATE | SHIFT | TYPE | MATERIAL | COMPANY | DISPATCH_ZONE | ORIGIN | DESTINATION | BUYER | NB_DT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 57308 | RIM | 2026-06-23 | 1 | HAULAGE | SAP | WBN | KRENE to KM 27 | KRENE | POS 12 |  | 15.0 |
| 57309 | RIM | 2026-06-23 | 1 | DIRECT | SAP | WBN | TOFU to FENI A | TF | FENI A |  | 25.0 |
| 57310 | RIM | 2026-06-23 | 1 | DIRECT | SAP | WBN | BLB to FENI A | BLB | FENI A |  | 15.0 |
| 57311 | RIM | 2026-06-23 | 1 | HAULAGE | SAP | WBN | BLB to POS 14 | BLB | POS 14 |  | 20.0 |
| 57312 | RIM | 2026-06-23 | 2 | HAULAGE | SAP | WBN | KRENE to KM 27 | KRENE | POS 12 |  | 15.0 |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`MINING_FLASH_REPORT_EQUIPMENT`

- **Rows**: 102
- **Flags**: TRUCK, col:STATUS, col:TIME
- **Date column**: `DATE` — 2025-11-28 00:00:00 to 2025-11-30 00:00:00

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `DEPOSIT` | nvarchar(255) | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `ACTIVITY` | nvarchar(255) | yes |
| 6 | `UNIT TYPE` | nvarchar(255) | yes |
| 7 | `RUNNING` | float | yes |
| 8 | `BREAKDOWN` | float | yes |
| 9 | `STANDBY` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | DEPOSIT | CONTRACTOR | SHIFT | ACTIVITY | UNIT TYPE | RUNNING | BREAKDOWN | STANDBY |
|---|---|---|---|---|---|---|---|---|
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | MINING | FLEET MINING | 8.0 | 2.0 | 1.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | HAULER | ADT | 28.0 | 8.0 | 0.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | SUPPORT | EXC 20T | 7.0 | 3.0 | 1.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | SUPPORT | EXC 30T | 4.0 | 1.0 | 1.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | SUPPORT | EXC 40T | 2.0 | 1.0 | 1.0 |

</details>

### `WBN_DATABASE`.`BLASTING_REMAINING`

- **Rows**: 98
- **Flags**: col:TIME
- **Date column**: `DATE_REMAINING_BCM` — 2026-05-27 00:00:00 to 2026-05-27 00:00:00

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DEPOSIT` | nvarchar(255) | yes |
| 2 | `DATE_REMAINING_BCM` | datetime | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `MATERIAL` | nvarchar(255) | yes |
| 5 | `AREA_PIT` | nvarchar(255) | yes |
| 6 | `ID_BLASTING` | float | yes |
| 7 | `REMAIN_BCM` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DEPOSIT | DATE_REMAINING_BCM | CONTRACTOR | MATERIAL | AREA_PIT | ID_BLASTING | REMAIN_BCM |
|---|---|---|---|---|---|---|
| Kaorahai | 2026-05-27 00:00:00 | RSF | Quarry | KR3 | 71.0 | 12804.334 |
| Tofu | 2026-05-27 00:00:00 | SMA | Quarry | TOFU1 | 82.0 | 4341.687 |
| Tofu | 2026-05-27 00:00:00 | STM | Quarry | TOFU1 | 83.0 | 9681.079 |
| Kaorahai | 2026-05-27 00:00:00 | PP QUARRY | Quarry | KR3 | 67.0 | 11693.974 |
| BLB | 2026-05-27 00:00:00 | RIM | Quarry | BLB5 | 67.0 | 4041.37 |

</details>

### `FMS_DB`.`SHP_SED_POND`

- **Rows**: 91
- **Flags**: col:COORD

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `STATION` | varchar(50) | no |
| 2 | `LAT_CALC` | varchar(max) | yes |
| 3 | `LONG_CALC` | varchar(max) | yes |
| 4 | `GEOM` | geography(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| STATION | LAT_CALC | LONG_CALC | GEOM |
|---|---|---|---|
| SP-1 | 0.803003572 | 128.025663 | <22 bytes> |
| SP-4 | 0.617704167 | 127.9251236 | <22 bytes> |
| SP-BB01 | 0.522842 | 127.926417 | <22 bytes> |
| SP-BB02 | 0.519071 | 127.928808 | <22 bytes> |
| SP-BB03 | 0.519524 | 127.933525 | <22 bytes> |

</details>

### `WBN_DATABASE`.`CONTRACTOR_DEPOSIT`

- **Rows**: 84
- **Flags**: none

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DEPOSIT` | nvarchar(50) | yes |
| 4 | `SHIFT` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DEPOSIT | SHIFT |
|---|---|---|---|
| 1 | STM | KR | DS |
| 2 | STM | TF | DS |
| 3 | STM | CSW | DS |
| 4 | STM | CAS | DS |
| 5 | STM | BLB | DS |

</details>

### `WBN_DATABASE`.`EQUIPMENTS_WORKS`

- **Rows**: 82
- **Flags**: TRUCK, col:TIME
- **Date column**: `DATE` — 2024-09-06 to 2024-10-14

<details><summary>14 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |
| 3 | `DATE` | date | yes |
| 4 | `SHIFT` | int | yes |
| 5 | `ID_EQ` | nvarchar(50) | yes |
| 6 | `WORK_DONE` | nvarchar(255) | yes |
| 7 | `WORK_CONTEXT` | nvarchar(255) | yes |
| 8 | `ISSUE_DETAILS` | nvarchar(255) | yes |
| 9 | `ISSUE_DATE_START` | date | yes |
| 10 | `HOUR_METER` | float | yes |
| 11 | `COMPARTMENT` | nvarchar(50) | yes |
| 12 | `PART_CHANGED` | nvarchar(50) | yes |
| 13 | `PART_REPAIRED` | nvarchar(50) | yes |
| 14 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | WORK_DONE | WORK_CONTEXT | ISSUE_DETAILS | ISSUE_DATE_START | HOUR_METER | COMPARTMENT | PART_CHANGED |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMA | 2024-09-25 |  | MG09 | BOLT TYRE POS 2 BROKEN | BREAKDOWN |  | 2024-08-18 | 2501.0 | TYRE | TYRE |
| 2 | SMA | 2024-09-06 |  | DZ16 | RECOIL SPRING LH BROKEN | BREAKDOWN |  | 2024-09-05 | 2879.8 | UNDERCARRIAGE | UNDERCARRIAGE |
| 3 | SMA |  |  | DT16 | VESSEL DUMP PROBLEM | BREAKDOWN | *CHECK CONDITION UNIT
*REPLACE VESSEL
*TYRE SWAP T | 2024-04-16 | 18225.0 | DUMP BODY | DUMP BODY |
| 4 | SMA | 2024-09-20 |  | DZ23 | OIL LEAK AREA FINAL DRIVE | BREAKDOWN |  | 2024-08-07 | 9378.2 | FINAL DRIVE | FINAL DRIVE |
| 5 | SMA | 2024-09-06 |  | DT41 | KING PIN PROBLEM & PM 1000 HRS SERVICE | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT
*CARRY OUT PM SERVICE 1000 H | 2024-09-05 | 17405.0 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |

*(first 12 of 14 columns shown)*

</details>

### `FMS_DB`.`SAFETY_DPLAN`

- **Rows**: 80
- **Flags**: PLAN, col:TIME
- **Date column**: `Date` — 2026-05-05 09:24:06 to 2026-06-11 10:53:30

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Date` | datetime | yes |
| 2 | `Shift` | nvarchar(255) | yes |
| 3 | `Dispatcher` | nvarchar(255) | yes |
| 4 | `ID` | float | yes |
| 5 | `Group 1` | nvarchar(255) | yes |
| 6 | `Group 2` | nvarchar(255) | yes |
| 7 | `Group 3` | nvarchar(255) | yes |
| 8 | `Group 4` | nvarchar(255) | yes |
| 9 | `Date Uploaded` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Date | Shift | Dispatcher | ID | Group 1 | Group 2 | Group 3 | Group 4 | Date Uploaded |
|---|---|---|---|---|---|---|---|---|
| 2026-05-05 09:24:06 | D/S | MIzan | 8230404007.0 | E | F | D |  | 2026-05-05 09:24:06 |
| 2026-05-05 09:24:06 | D/S | Rachmat | 8230429016.0 | G | B | K |  | 2026-05-05 09:24:06 |
| 2026-05-05 09:24:06 | D/S | Pandi | 8240216182.0 | H | C | A |  | 2026-05-05 09:24:06 |
| 2026-05-05 09:24:06 | D/S | Rifandi | 22312113.0 | HRM | RSF | Support | Repair | 2026-05-05 09:24:06 |
| 2026-05-05 09:24:06 | N/S | Mkorman | 22312115.0 | E | F | D |  | 2026-05-05 09:24:06 |

</details>

### `WBN_DATABASE`.`WBN_DATABASE_PROCEDURE_QUEUE`

- **Rows**: 79
- **Flags**: col:STATUS
- **Date column**: `LAST_EXECUTED` — 2025-05-12 17:30:13 to 2025-06-20 17:30:15
- *redacted columns: PROCEDURE_NAME*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PROCEDURE_NAME` 🔒 | nvarchar(100) | yes |
| 2 | `PROCEDURE_STATUS` | nvarchar(50) | yes |
| 3 | `LAST_EXECUTED` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| PROCEDURE_NAME | PROCEDURE_STATUS | LAST_EXECUTED |
|---|---|---|
| [REDACTED] | Completed | 2025-05-12 17:30:13.443000 |
| [REDACTED] | Completed | 2025-05-13 17:30:16.120000 |
| [REDACTED] | Completed | 2025-05-14 11:30:12.950000 |
| [REDACTED] | Completed | 2025-05-14 17:30:12.510000 |
| [REDACTED] | Completed | 2025-05-15 11:30:12.710000 |

</details>

### `WBN_DATABASE`.`TEAM_PLAN`

- **Rows**: 78
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2024-12-29 00:00:00 to 2025-02-14 00:00:00
- *redacted columns: DS_NAME1, DS_NAME2, NS_NAME1, NS_NAME2*

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | datetime | yes |
| 3 | `LOCATION_TYPE` | nvarchar(255) | yes |
| 4 | `LOCATION_AREA` | nvarchar(255) | yes |
| 5 | `DS_NAME1` 🔒 | nvarchar(255) | yes |
| 6 | `DS_NAME2` 🔒 | nvarchar(255) | yes |
| 7 | `NS_NAME1` 🔒 | nvarchar(255) | yes |
| 8 | `NS_NAME2` 🔒 | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | LOCATION_TYPE | LOCATION_AREA | DS_NAME1 | DS_NAME2 | NS_NAME1 | NS_NAME2 |
|---|---|---|---|---|---|---|---|
| 1 | 2024-12-29 00:00:00 | ROAD | KR | [REDACTED] |  |  |  |
| 2 | 2024-12-29 00:00:00 | ROAD | TF | [REDACTED] |  |  |  |
| 3 | 2024-12-29 00:00:00 | ROAD | BLB | [REDACTED] |  |  |  |
| 4 | 2024-12-29 00:00:00 | POS | 14 | [REDACTED] |  |  |  |
| 5 | 2024-12-29 00:00:00 | POS | 12 | [REDACTED] |  |  |  |

</details>

### `WBN_DATABASE`.`COMPANIES`

- **Rows**: 73
- **Flags**: none

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `COMPANY` | nvarchar(255) | no |
| 2 | `DESCRIPTION` | nvarchar(255) | yes |
| 3 | `PLANT` | nvarchar(255) | yes |
| 4 | `PLANT_TYPE` | nvarchar(50) | yes |
| 5 | `PLANT_LOCATION` | nvarchar(50) | yes |
| 6 | `COMMENT` | nvarchar(255) | yes |
| 7 | `AVG_Ni` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| COMPANY | DESCRIPTION | PLANT | PLANT_TYPE | PLANT_LOCATION | COMMENT | AVG_Ni |
|---|---|---|---|---|---|---|
| AJK | ARIE JAYA KENCANA |  |  |  |  |  |
| AMI | PT. ANDALAN METAL INDUSTRY  | F2 | FENI | KM0 |  | 1.495399448 |
| ANI | PT. ANGEL NICKEL INDUSTRY | G | FENI | KM0 |  | 1.499291767 |
| BSE | PT. BLUE SPARKING ENERGY  | BSE | HPAL |  |  |  |
| CMI | PT. COSAN METAL INDUSTRY  | U2 | FENI | KM15 |  | 1.725908031 |

</details>

### `FMS_DB`.`LV_PLAN`

- **Rows**: 62
- **Flags**: PLAN, col:EQUIP, col:TIME
- **Date column**: `Shift_Date` — 2026-05-11 to 2026-05-13

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Shift_Date` | date | yes |
| 2 | `Shift` | varchar(10) | yes |
| 3 | `Vehicle_Number` | varchar(50) | yes |
| 4 | `Region` | varchar(20) | yes |
| 5 | `KM_From` | decimal(10,2) | yes |
| 6 | `KM_To` | decimal(10,2) | yes |
| 7 | `Date_Uploaded` | datetime2 | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Shift_Date | Shift | Vehicle_Number | Region | KM_From | KM_To | Date_Uploaded |
|---|---|---|---|---|---|---|
| 2026-05-11 | Day | C88 | KR | 18.00 | 22.00 | 2026-05-12 18:40:48.750000 |
| 2026-05-11 | Day | M92 | KR | 18.00 | 22.00 | 2026-05-12 18:40:48.750000 |
| 2026-05-11 | Day | C51 | KR | 18.00 | 22.00 | 2026-05-12 18:40:48.750000 |
| 2026-05-11 | Day | M80 | KR | 18.00 | 22.00 | 2026-05-12 18:40:48.750000 |
| 2026-05-11 | Day | M81 | KR | 18.00 | 22.00 | 2026-05-12 18:40:48.750000 |

</details>

### `WBN_DATABASE`.`DARONNEtemp`

- **Rows**: 61
- **Flags**: col:TIME
- **Date column**: `DATE` — 2026-05-01 00:00:00 to 2026-06-30 00:00:00

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `WMT_TARGET` | float | yes |
| 3 | `CUM_WMT_TARGET` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | WMT_TARGET | CUM_WMT_TARGET |
|---|---|---|
| 2026-05-01 00:00:00 | 38873.82 | 38873.82 |
| 2026-05-02 00:00:00 | 7873.18 | 46747.0 |
| 2026-05-03 00:00:00 | 0.0 | 46747.0 |
| 2026-05-04 00:00:00 | 0.0 | 46747.0 |
| 2026-05-05 00:00:00 | 0.0 | 46747.0 |

</details>

### `FMS_DB`.`LV_INFO`

- **Rows**: 57
- **Flags**: col:EQUIP
- *redacted columns: Driver_DS, Driver_NS*

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Vehicle_Number` | varchar(50) | yes |
| 2 | `Divisi` | varchar(100) | yes |
| 3 | `Department` | varchar(100) | yes |
| 4 | `Driver_DS` 🔒 | varchar(200) | yes |
| 5 | `Driver_NS` 🔒 | varchar(200) | yes |
| 6 | `Work_Location` | varchar(200) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Vehicle_Number | Divisi | Department | Driver_DS | Driver_NS | Work_Location |
|---|---|---|---|---|---|
| S80 | General Office | Pool | [REDACTED] |  | Tj Ulie Office & All Area |
| S81 | General Office | Pool | [REDACTED] |  | Tj Ulie Office & All Area |
| C11 | Mine Operation | Mining | [REDACTED] |  | Tanjung Ulie - Biri-Biri- Kao Rahai - Tofu |
| C17 | Mine Operation | Haulage | [REDACTED] | [REDACTED] | Biri-Biri 2000 - Area Costal - Uni-uni - Tj Ulie |
| C18 | Mine Operation | Mining | [REDACTED] | [REDACTED] | North - KR |

</details>

### `WBN_DATABASE`.`Ni_COLOR`

- **Rows**: 45
- **Flags**: none

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Ni_CLASS` | float | yes |
| 2 | `COLOR` | nvarchar(255) | yes |
| 3 | `COLOR_HEXA` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Ni_CLASS | COLOR | COLOR_HEXA |
|---|---|---|
| 0.0 |  | #FF7F00 |
| 0.1 |  | #FF7F00 |
| 0.2 |  | #FF7F00 |
| 0.3 |  | #FF7F00 |
| 0.4 |  | #FF7F00 |

</details>

### `WBN_DATABASE`.`MINING_FLASH_REPORT_PRODUCTION`

- **Rows**: 42
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2025-11-28 00:00:00 to 2025-11-30 00:00:00

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DATE` | datetime | yes |
| 2 | `DEPOSIT` | nvarchar(255) | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `SHIFT` | float | yes |
| 5 | `MATERIAL` | nvarchar(255) | yes |
| 6 | `PLANNED PROD` | float | yes |
| 7 | `ACTUAL PROD` | float | yes |
| 8 | `DEVIATON` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| DATE | DEPOSIT | CONTRACTOR | SHIFT | MATERIAL | PLANNED PROD | ACTUAL PROD | DEVIATON |
|---|---|---|---|---|---|---|---|
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | SAP | 13850.0 | 13090.0 | 760.0 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | WCO | 1837.08064516129 | 0.0 | 1837.08064516129 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | LIM | 2132.85483870968 | 0.0 | 2132.85483870968 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | WST | 4727.24193548387 | 7385.0 | -2657.7580645161297 |
| 2025-11-28 00:00:00 | KRENE | PPP | 1.0 | TS AND BMS | 503.475744007605 | 3780.0 | -3276.524255992395 |

</details>

### `WBN_DATABASE`.`ACTIVITIES_MAT`

- **Rows**: 39
- **Flags**: col:STATUS

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ACTIVITY` | nvarchar(20) | no |
| 2 | `MATERIAL` | nvarchar(10) | no |
| 3 | `ORIGIN_TYPE` | nvarchar(50) | yes |
| 4 | `DESTINATION_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ACTIVITY | MATERIAL | ORIGIN_TYPE | DESTINATION_TYPE |
|---|---|---|---|
| BEDDING | SAP |  |  |
| CONSTRUCTION | BASALT | CRUSHER | INFRA |
| CONSTRUCTION | QUARRY | CRUSHER | INFRA |
| DIRECT | CS | CRUSHER | YARD |
| DIRECT | LIM | TOS | YARD |

</details>

### `WBN_DATABASE`.`LOCATION_WB_SH`

- **Rows**: 39
- **Flags**: GPS, WEIGHBRIDGE

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ITEM_TYPE` | nvarchar(50) | yes |
| 2 | `ITEM_ID` | nvarchar(50) | no |
| 3 | `COMPANY` | nvarchar(50) | yes |
| 4 | `LOCATION` | nvarchar(50) | yes |
| 5 | `KM_LOADED` | float | yes |
| 6 | `KM_EMPTY` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ITEM_TYPE | ITEM_ID | COMPANY | LOCATION | KM_LOADED | KM_EMPTY |
|---|---|---|---|---|---|
| PIT | BLB | WBN | BLB | 20.0 | 20.0 |
| PIT | CBB | WBN | CBB | 15.0 | 15.0 |
| PIT | KR | WBN | KR | 37.0 | 37.0 |
| POS | POS 10 | WBN | KR | 17.0 | 17.0 |
| POS | POS 11 | WBN | KR | 17.0 | 17.0 |

</details>

### `WBN_DATABASE`.`DT_DENSITY_HR_MODEL$`

- **Rows**: 37
- **Flags**: col:TIME
- **Date column**: `DATE` — 2025-09-13 00:00:00 to 2025-09-13 00:00:00

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ORIGIN raw` | nvarchar(255) | yes |
| 2 | `ORIGIN` | nvarchar(255) | yes |
| 3 | `DESTINATION` | nvarchar(255) | yes |
| 4 | `CONTRACTOR` | nvarchar(255) | yes |
| 5 | `DATE` | datetime | yes |
| 6 | `TYPE` | nvarchar(255) | yes |
| 7 | `MATERIAL` | nvarchar(255) | yes |
| 8 | `NB_SHIFT` | float | yes |
| 9 | `WMT` | float | yes |
| 10 | `RIT` | float | yes |
| 11 | `NB_DT` | float | yes |
| 12 | `TF` | float | yes |
| 13 | `DT PLAN` | nvarchar(255) | yes |
| 14 | `TARGET TRIP` | float | yes |
| 15 | `PLAN WMT` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ORIGIN raw | ORIGIN | DESTINATION | CONTRACTOR | DATE | TYPE | MATERIAL | NB_SHIFT | WMT | RIT | NB_DT | TF |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TF | TF | POS 12 | CKB | 2025-09-13 00:00:00 | HAULAGE | SAP | 2.0 | 6627.4400000000005 | 148.0 | 45.0 | 45.0 |
| KRENE | KRENE | POS 12 | GMG | 2025-09-13 00:00:00 | HAULAGE | SAP | 2.0 | 2155.78 | 65.0 | 10.0 | 36.0 |
| BLB | BLB | FENI KM15 | HJS | 2025-09-13 00:00:00 | DIRECT | SAP | 1.0 | 989.1999999999999 | 24.0 | 10.0 | 31.0 |
| BLB | BLB | POS 14 | HJS | 2025-09-13 00:00:00 | HAULAGE | SAP | 2.0 | 1786.2899999999997 | 46.0 | 5.0 | 31.0 |
| BLB | BLB | FENI | HJS | 2025-09-13 00:00:00 | DIRECT | SAP | 2.0 | 2331.62 | 49.0 | 10.0 | 31.0 |

*(first 12 of 15 columns shown)*

</details>

### `FMS_DB`.`FMS_ROADMAP`

- **Rows**: 36
- **Flags**: ROAD, col:STATUS, col:TIME

<details><summary>21 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | nvarchar(64) | no |
| 2 | `TITLE` | nvarchar(300) | yes |
| 3 | `DETAIL` | nvarchar(max) | yes |
| 4 | `STATUS` | nvarchar(20) | yes |
| 5 | `CATEGORY` | nvarchar(80) | yes |
| 6 | `TARGET` | nvarchar(40) | yes |
| 7 | `VERSION` | nvarchar(40) | yes |
| 8 | `SORT` | int | yes |
| 9 | `TS` | bigint | yes |
| 10 | `UPDATED_BY` | nvarchar(80) | yes |
| 11 | `UPDATED_AT` | bigint | yes |
| 12 | `START_DATE` | nvarchar(10) | yes |
| 13 | `END_DATE` | nvarchar(10) | yes |
| 14 | `ITEM_TYPE` | nvarchar(20) | yes |
| 15 | `PHASE` | nvarchar(80) | yes |
| 16 | `OWNER` | nvarchar(120) | yes |
| 17 | `PRIORITY` | nvarchar(10) | yes |
| 18 | `COVERAGE` | nvarchar(20) | yes |
| 19 | `ACCEPTANCE` | nvarchar(max) | yes |
| 20 | `DEPENDENCIES` | nvarchar(max) | yes |
| 21 | `SOURCE_REF` | nvarchar(500) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | TITLE | DETAIL | STATUS | CATEGORY | TARGET | VERSION | SORT | TS | UPDATED_BY | UPDATED_AT | START_DATE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rm_seed_01 | Haul-road congestion page (live) | Snap live haul-truck GPS to the official KM sections; per... | shipped | Congestion | Q3 2026 | v1.0 | 10 | 1784476800000 | seed | 1784476800000 |  |
| rm_seed_02 | Speed-coloured GPS traces | Colour the Live Map trace dots by speed (red/amber/green)... | shipped | Live Map | Q3 2026 | v1.0 | 20 | 1784476800000 | seed | 1784476800000 |  |
| rm_seed_03 | 120 m excavator loading beacon | LOAD starts when a truck enters the excavator's live 120 ... | shipped | Haul Cycle | Q3 2026 | v1.0 | 30 | 1784476800000 | seed | 1784476800000 |  |
| rm_seed_04 | Production plan-scoped KPIs & chart | Actual tonnes / achievement / variance count only plan-pa... | shipped | Production | Q3 2026 | v1.0 | 40 | 1784476800000 | seed | 1784476800000 |  |
| rm_seed_05 | Haul Flow time-machine | Scrub/replay the shift — trucks move through empty→loader... | shipped | Haul Flow | Q3 2026 | v1.0 | 50 | 1784476800000 | seed | 1784476800000 |  |

*(first 12 of 21 columns shown)*

</details>

### `WBN_DATABASE`.`TEAM`

- **Rows**: 34
- **Flags**: none
- *redacted columns: NAME*

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `NAME` 🔒 | nvarchar(255) | yes |
| 3 | `SUPERVISE` | nvarchar(255) | yes |
| 4 | `CONTACT` | nvarchar(255) | yes |
| 5 | `AREA` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | NAME | SUPERVISE | CONTACT | AREA |
|---|---|---|---|---|
| 1 | [REDACTED] |  |  | COASTAL |
| 2 | [REDACTED] |  |  | KR |
| 3 | [REDACTED] |  |  | KR |
| 4 | [REDACTED] |  |  | TF |
| 5 | [REDACTED] |  |  | KR |

</details>

### `FMS_DB`.`FMS_LOGIN_IPS`

- **Rows**: 32
- **Flags**: col:TIME
- *redacted columns: USERNAME*

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `USERNAME` 🔒 | varchar(64) | no |
| 2 | `IP` | varchar(64) | no |
| 3 | `HITS` | int | yes |
| 4 | `IS_ADMIN` | bit | yes |
| 5 | `UPDATED_AT` | bigint | yes |

</details>

<details><summary>Sample rows (5)</summary>

| USERNAME | IP | HITS | IS_ADMIN | UPDATED_AT |
|---|---|---|---|---|
| [REDACTED] | 36.93.21.124 | 1 | False | 1784183931132 |
| [REDACTED] | 10.158.21.91 | 1 | False | 1784187896893 |
| [REDACTED] | 127.0.0.1 | 1 | False | 1784959255964 |
| [REDACTED] | 36.93.196.124 | 7 | False | 1785026109484 |
| [REDACTED] | 182.1.132.121 | 1 | False | 1784265429691 |

</details>

### `FMS_DB`.`FMS_GEOFENCE_ALERTS`

- **Rows**: 31
- **Flags**: col:COORD, col:STATUS
- *redacted columns: GEOFENCE_NAME, EMAIL_SENT, ASSIGNED_DRIVER, ACTUAL_DRIVER, EMAIL_RECIPIENTS, EMAIL_CC*

<details><summary>29 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ALERT_ID` | varchar(36) | no |
| 2 | `VISIT_EVENT_ID` | varchar(36) | no |
| 3 | `RULE_ID` | varchar(36) | no |
| 4 | `UNIT_ID` | varchar(40) | no |
| 5 | `GEOFENCE_ID` | nvarchar(20) | yes |
| 6 | `GEOFENCE_NAME` 🔒 | nvarchar(200) | yes |
| 7 | `SEVERITY` | varchar(12) | yes |
| 8 | `ENTER_TS` | bigint | no |
| 9 | `EXIT_TS` | bigint | yes |
| 10 | `ENTER_LAT` | float | yes |
| 11 | `ENTER_LNG` | float | yes |
| 12 | `EXIT_LAT` | float | yes |
| 13 | `EXIT_LNG` | float | yes |
| 14 | `STATUS` | varchar(20) | no |
| 15 | `CREATED_AT` | bigint | no |
| 16 | `EMAIL_SENT` 🔒 | bit | no |
| 17 | `ESCALATED_AT` | bigint | yes |
| 18 | `ACK_AT` | bigint | yes |
| 19 | `ACK_BY` | nvarchar(100) | yes |
| 20 | `VERIFICATION_RESULT` | nvarchar(80) | yes |
| 21 | `ASSIGNED_DRIVER` 🔒 | nvarchar(160) | yes |
| 22 | `ACTUAL_DRIVER` 🔒 | nvarchar(160) | yes |
| 23 | `ACTION_TAKEN` | nvarchar(500) | yes |
| 24 | `COMMENT` | nvarchar(1000) | yes |
| 25 | `CLOSED_AT` | bigint | yes |
| 26 | `CLOSED_BY` | nvarchar(100) | yes |
| 27 | `EMAIL_RECIPIENTS` 🔒 | nvarchar(1000) | yes |
| 28 | `ESCALATION_RECIPIENTS` | nvarchar(1000) | yes |
| 29 | `EMAIL_CC` 🔒 | nvarchar(1000) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ALERT_ID | VISIT_EVENT_ID | RULE_ID | UNIT_ID | GEOFENCE_ID | GEOFENCE_NAME | SEVERITY | ENTER_TS | EXIT_TS | ENTER_LAT | ENTER_LNG | EXIT_LAT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01800592-d7fa-43ca-88c5-3c09bfbabc89 | 6971c5d5-0258-46a8-9c13-0e04bfdf178b | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-M57 | 85d11afa | [REDACTED] | CRITICAL | 1784996790000 | 1785015795000 | 0.468455 | 127.939258 | 0.469138 |
| 0c2d344a-feb7-4846-be17-4741b102f309 | 3274ce4d-fc14-4972-be46-cfa1cc6a1ae8 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C88 | 85d11afa | [REDACTED] | CRITICAL | 1784954955000 | 1784955229000 | 0.46917 | 127.937698 | 0.467463 |
| 0cb99b76-fa3d-45e6-88dc-6d0cae6c46b6 | 18808a59-5909-47c9-9b93-d78b59bce775 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C25 | 85d11afa | [REDACTED] | CRITICAL | 1784980797000 | 1784982548000 | 0.465733 | 127.928975 | 0.469878 |
| 0d0d7a45-ca36-4ff6-87ff-7c9b6201fd17 | 253c7248-3a2f-41d2-a019-b09e1fa5fb02 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C40 | 85d11afa | [REDACTED] | CRITICAL | 1785142770000 | 1785142770000 | 0.469122 | 127.938185 | 0.469122 |
| 110942a1-a2c0-4f5b-926e-a8e4b0df1731 | b61779d6-6004-4911-932e-4e363ad558b1 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C25 | 85d11afa | [REDACTED] | CRITICAL | 1784974830000 | 1784977963000 | 0.472165 | 127.916942 | 0.465325 |

*(first 12 of 29 columns shown)*

</details>

### `FMS_DB`.`FMS_USERS`

- **Rows**: 30
- **Flags**: col:TIME
- *redacted columns: USERNAME, PASSWORD, DISPLAY_NAME, EMAIL*

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `USERNAME` 🔒 | nvarchar(100) | no |
| 2 | `PASSWORD` 🔒 | nvarchar(300) | no |
| 3 | `ROLE` | nvarchar(50) | no |
| 4 | `DISPLAY_NAME` 🔒 | nvarchar(200) | yes |
| 5 | `EMAIL` 🔒 | nvarchar(300) | yes |
| 6 | `ACTIVE` | bit | no |
| 7 | `UPDATED_AT` | bigint | no |
| 8 | `UPDATED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| USERNAME | PASSWORD | ROLE | DISPLAY_NAME | EMAIL | ACTIVE | UPDATED_AT | UPDATED_BY |
|---|---|---|---|---|---|---|---|
| [REDACTED] | [REDACTED] | dispatcher | [REDACTED] | [REDACTED] | True | 1784957057900 | Rudolfs-MacBook-Air.local |
| [REDACTED] | [REDACTED] | dispatcher | [REDACTED] | [REDACTED] | True | 1784957057900 | Rudolfs-MacBook-Air.local |
| [REDACTED] | [REDACTED] | fms_supt | [REDACTED] | [REDACTED] | True | 1784957105022 | fms-prototype |
| [REDACTED] | [REDACTED] | fms_supt | [REDACTED] | [REDACTED] | True | 1784957105022 | fms-prototype |
| [REDACTED] | [REDACTED] | dispatcher | [REDACTED] | [REDACTED] | True | 1784957105022 | fms-prototype |

</details>

### `WBN_DATABASE`.`MINING_EQ_TARGET_3MRMP`

- **Rows**: 30
- **Flags**: none

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `YEAR` | float | yes |
| 2 | `MONTH` | float | yes |
| 3 | `CONTRACTOR` | nvarchar(255) | yes |
| 4 | `EQ_CLASS` | nvarchar(255) | yes |
| 5 | `NUMBER` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| YEAR | MONTH | CONTRACTOR | EQ_CLASS | NUMBER |
|---|---|---|---|---|
| 2025.0 | 4.0 | HJS | EXC MINING | 7.0 |
| 2025.0 | 4.0 | HJS | ADT MINING | 29.0 |
| 2025.0 | 4.0 | PPP | EXC MINING | 6.0 |
| 2025.0 | 4.0 | PPP | ADT MINING | 24.0 |
| 2025.0 | 4.0 | RIM | EXC MINING | 18.0 |

</details>

### `FMS_DB`.`FMS_LV_ZONE_VISITS`

- **Rows**: 27
- **Flags**: col:COORD, col:STATUS

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `EVENT_ID` | varchar(36) | no |
| 2 | `PLATE` | varchar(32) | no |
| 3 | `ZONE_ID` | nvarchar(20) | no |
| 4 | `ZONE_NAME` | nvarchar(200) | yes |
| 5 | `ENTER_TS` | bigint | no |
| 6 | `EXIT_TS` | bigint | yes |
| 7 | `DURATION_SEC` | int | yes |
| 8 | `ENTER_LAT` | float | yes |
| 9 | `ENTER_LNG` | float | yes |
| 10 | `EXIT_LAT` | float | yes |
| 11 | `EXIT_LNG` | float | yes |
| 12 | `STATUS` | varchar(12) | no |
| 13 | `CREATED_AT` | bigint | no |

</details>

<details><summary>Sample rows (5)</summary>

| EVENT_ID | PLATE | ZONE_ID | ZONE_NAME | ENTER_TS | EXIT_TS | DURATION_SEC | ENTER_LAT | ENTER_LNG | EXIT_LAT | EXIT_LNG | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 02009781-745f-429f-9a59-0cf04655425f | WBN-LV-M57 | 85d11afa | Village | 1785031731000 | 1785033960000 | 2229 | 0.47029 | 127.938785 | 0.472328 | 127.91688 | EXITED |
| 03383695-9c77-4dae-8446-6128648e7a2e | WBN-LV-C25 | 85d11afa | Village | 1785038720000 | 1785039627000 | 907 | 0.463547 | 127.927207 | 0.472737 | 127.916788 | EXITED |
| 0406cd08-cf28-431c-bcb1-22f5d1834980 | WBN-LV-C88 | 85d11afa | Village | 1784954589000 | 1784956222000 | 1633 | 0.46751 | 127.92595 | 0.514362 | 127.901518 | EXITED |
| 096d6f56-85cf-43d2-b92a-9ec06ff08a72 | WBN-LV-M57 | 85d11afa | Village | 1784893125000 | 1784896418000 | 3293 | 0.47131 | 127.938328 | 0.469013 | 127.940392 | EXITED |
| 0d5dc7b7-3cda-48da-9ac7-98b0e7036217 | WBN-LV-C25 | 85d11afa | Village | 1784980797000 | 1784982548000 | 1751 | 0.465733 | 127.928975 | 0.469878 | 127.914873 | EXITED |

*(first 12 of 13 columns shown)*

</details>

### `FMS_DB`.`RES_SPEED_LIMIT_ZONES`

- **Rows**: 27
- **Flags**: col:COORD, col:SPEED

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Segment Code` | nvarchar(255) | yes |
| 2 | `Chainage Range (KM)` | nvarchar(255) | yes |
| 3 | `Speed Limit (km/h)` | float | yes |
| 4 | `Geometry Type` | nvarchar(255) | yes |
| 5 | `Area Type` | nvarchar(255) | yes |
| 6 | `Loading/Unloading Category` | nvarchar(255) | yes |
| 7 | `Operating Area` | nvarchar(255) | yes |
| 8 | `Responsible Department` | nvarchar(255) | yes |
| 9 | `Longitude` | float | yes |
| 10 | `Latitude` | float | yes |
| 11 | `Location Description` | nvarchar(255) | yes |
| 12 | `Remarks` | nvarchar(255) | yes |
| 13 | `KM_From` | decimal(6,3) | yes |
| 14 | `KM_To` | decimal(6,3) | yes |
| 15 | `Region_Code` | varchar(10) | yes |
| 16 | `Is_Critical` | bit | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Segment Code | Chainage Range (KM) | Speed Limit (km/h) | Geometry Type | Area Type | Loading/Unloading Category | Operating Area | Responsible Department | Longitude | Latitude | Location Description | Remarks |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SL_BB_01_30 | CBB KM 6 - 10 | 30.0 | Area | WBN_SpeedLimit_Test30 | Others | BIRI BIRI | RIM | 127.937974 | 0.491412 | Jalan Tanpa Nama, Lelilef Sawai, Kec. Weda Tengah, Kabupa... |  |
| SL_BB_02_20 | CBB KM 10 - 11.8 | 20.0 | Area | WBN_SpeedLimit_Test20 | Others | BIRI BIRI | RIM | 127.932276 | 0.507046 | Jalan Tanpa Nama, Lelilef Sawai, Kec. Weda Tengah, Kabupa... | KM10 - KM11.750 |
| SL_BB_03_30 | CBB KM 11.8 - CBBB KM 15.5 | 30.0 | Area | WBN_SpeedLimit_Test30 | Others | BIRI BIRI | RIM | 127.935252 | 0.519801 | Jalan Tanpa Nama, Lelilef Sawai, Kec. Weda Tengah, Kabupa... | KM12 - KM16 |
| SL_BLB_01_40 | CBB KM 14.7 - 16.8 | 40.0 | Area | WBN_SpeedLimit_Test40 | Others | BUKET LIMBER | RIM | 127.946949 | 0.5316 | Lelilef Sawai, Weda Tengah, Central Halmahera Regency, No... | KM14.700 - KM16.800 |
| SL_BLB_02_30 | CBB KM 16.8 - BLB KM 19.8 | 30.0 | Area | WBN_SpeedLimit_Test30 | Others | BUKET LIMBER | RIM | 127.958523 | 0.536002 | Lelilef Sawai, Weda Tengah, Central Halmahera Regency, No... | KM17 - KM20 |

*(first 12 of 16 columns shown)*

</details>

### `WBN_DATABASE`.`ALL_HR_KM_SECTIONS`

- **Rows**: 27
- **Flags**: none
- *redacted columns: ROAD_NAME, SECTION_NAME*

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ROAD_NAME` 🔒 | nvarchar(255) | yes |
| 2 | `ORIGIN` | nvarchar(255) | yes |
| 3 | `DESTINATION` | nvarchar(255) | yes |
| 4 | `SECTION_NAME` 🔒 | nvarchar(255) | yes |
| 5 | `SECTION_ID` | nvarchar(255) | yes |
| 6 | `KM_START` | float | yes |
| 7 | `KM_END` | float | yes |
| 8 | `APPROX_DISTANCE` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ROAD_NAME | ORIGIN | DESTINATION | SECTION_NAME | SECTION_ID | KM_START | KM_END | APPROX_DISTANCE |
|---|---|---|---|---|---|---|---|
| [REDACTED] | FENI | CRD/BLB ROAD JUNCTION | [REDACTED] | CRD KM0 - KM2,5 | 0.0 | 2.5 | 2.5 |
| [REDACTED] | CRD/BLB ROAD JUNCTION | HUAFEI.C01 JUNCTION | [REDACTED] | CRD KM2,5 - KM5,5 | 2.5 | 5.5 | 3.0 |
| [REDACTED] | HUAFEI.C01 JUNCTION | T JUNCTION | [REDACTED] | CRD KM5,5 - KM7 | 5.5 | 7.0 | 1.5 |
| [REDACTED] | FENI | COASTAL CRUSHER JUNCTION | [REDACTED] | CSW KM3 - KM4 | 3.0 | 4.0 | 1.0 |
| [REDACTED] | COASTAL CRUSHER JUNCTION | POS 14 | [REDACTED] | CSW KM4 - KM5,7 | 4.0 | 5.7 | 1.7000000000000002 |

</details>

### `WBN_DATABASE`.`ASSAY_CLASS`

- **Rows**: 27
- **Flags**: col:TIME
- **Date column**: `date` — 2020-01-01 to 2025-01-01

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `id` | int | no |
| 2 | `date` | date | yes |
| 3 | `cat` | nvarchar(255) | yes |
| 4 | `material` | nvarchar(255) | yes |
| 5 | `element` | nvarchar(255) | yes |
| 6 | `ore_class` | nvarchar(255) | yes |
| 7 | `ore_class_description` | nvarchar(255) | yes |
| 8 | `grade` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| id | date | cat | material | element | ore_class | ore_class_description | grade |
|---|---|---|---|---|---|---|---|
| 1 | 2025-01-01 | CAT | SAP | Ni | VHGS | Very High Grade Saprolite | 1.7 |
| 2 | 2025-01-01 | CAT | SAP | Ni | HGS | High Grade Saprolite | 1.4 |
| 3 | 2025-01-01 | CAT | SAP | Ni | WCO | Waste Conservation Ore | 1.2 |
| 5 | 2025-01-01 | CAT | SAP | Ni | WST | Waste | 0.0 |
| 6 | 2025-01-01 | CAT | SAP | Fe | VLFe | Very Low Iron | 0.0 |

</details>

### `WBN_DATABASE`.`SHAPE_STOCK_AREA`

- **Rows**: 26
- **Flags**: none

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `TYPE` | varchar(max) | yes |
| 2 | `AREA` | varchar(max) | yes |
| 3 | `STOCK_AREA` | varchar(max) | yes |
| 4 | `Area_ha` | float | yes |
| 5 | `GEOM` | geography(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| TYPE | AREA | STOCK_AREA | Area_ha | GEOM |
|---|---|---|---|---|
| POS | CENTRAL | POS 12 (KM 27) | 51.3212332029 | <1824 bytes> |
| POS | CENTRAL | POS 14 CAS67 | 75.1819771394 | <71360 bytes> |
| POS | CENTRAL | POS 11 (KM 17) | 90.0522222396 | <3200 bytes> |
| POS | CENTRAL | POS 10 & 10 EXT (KM 17) | 38.2006761796 | <38608 bytes> |
| POS | CENTRAL | POS 6 (KM 12) | 11.9913326971 | <24432 bytes> |

</details>

### `WBN_DATABASE`.`HRM_REQUEST_MATERIAL`

- **Rows**: 25
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-11-08 to 2024-11-09

<details><summary>10 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `SHIFT` | int | yes |
| 4 | `ORIGIN` | nvarchar(50) | yes |
| 5 | `TEAM` | nchar(50) | yes |
| 6 | `CONTRACTOR` | nchar(10) | yes |
| 7 | `PROJECT` | nvarchar(max) | yes |
| 8 | `MATERIAL` | nchar(50) | yes |
| 9 | `BCM` | float | yes |
| 10 | `NB_DT` | int | no |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | SHIFT | ORIGIN | TEAM | CONTRACTOR | PROJECT | MATERIAL | BCM | NB_DT |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-11-08 | 1 | LOYPOLOY | HRM/Construction                                   | RIM        | KM9 | Laminating                                         | 300.0 | 1 |
| 2 | 2024-11-08 | 2 | LOYPOLOY | HRM/Construction                                   | RIM        | KM9 | Laminating                                         | 300.0 | 1 |
| 3 | 2024-11-09 | 1 | LOYPOLOY | Civil Construction                                 | STM        | Coolstorage KM38 | 0-1                                                | 12.0 | 1 |
| 4 | 2024-11-08 | 1 | LOYPOLOY | HRM/Construction                                   | RIM        | KM38-42 | Base Course                                        | 200.0 | 8 |
| 5 | 2024-11-08 | 2 | LOYPOLOY | HRM/Construction                                   | RIM        | KM38-42 | Base Course                                        | 200.0 | 8 |

</details>

### `WBN_DATABASE`.`TEAM_FB`

- **Rows**: 25
- **Flags**: col:TIME
- **Date column**: `DATE_START` — 2025-08-07 to 2026-05-01
- *redacted columns: NAME*

<details><summary>6 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `NAME` 🔒 | nvarchar(50) | yes |
| 3 | `DATE_START` | date | yes |
| 4 | `DATE_END` | date | yes |
| 5 | `VALIDATED` | nvarchar(50) | yes |
| 6 | `REMARK` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | NAME | DATE_START | DATE_END | VALIDATED | REMARK |
|---|---|---|---|---|---|
| 4 | [REDACTED] | 2025-09-29 | 2025-10-19 | YES |  |
| 6 | [REDACTED] | 2025-08-07 | 2025-08-30 | YES |  |
| 9 | [REDACTED] | 2025-09-15 | 2025-09-29 | YES |  |
| 10 | [REDACTED] | 2026-01-11 | 2026-02-01 | NO |  |
| 11 | [REDACTED] | 2025-09-14 | 2025-10-05 | YES |  |

</details>

### `FMS_DB`.`FMS_APP_STATE`

- **Rows**: 23
- **Flags**: col:TIME
- **Date column**: `UPDATED_AT` — 2026-07-11 11:15:22 to 2026-07-27 19:43:36
- *redacted columns: NAME*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `NAME` 🔒 | nvarchar(160) | no |
| 2 | `PAYLOAD` | nvarchar(max) | yes |
| 3 | `UPDATED_AT` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| NAME | PAYLOAD | UPDATED_AT |
|---|---|---|
| [REDACTED] | {"nbagus": "d67490c4-d137-412a-846c-73fd93e7dc28", "sbell... | 2026-07-27 18:52:22.857000 |
| [REDACTED] | {"access_suspended": true, "cycle_collapse_loading": true... | 2026-07-22 11:14:42.077000 |
| [REDACTED] | {"contractors": ["ATC", "AWK", "BPMS", "CKB", "FIJ", "GGM... | 2026-07-11 11:15:26.663000 |
| [REDACTED] | {} | 2026-07-27 19:19:43.757000 |
| [REDACTED] | {"ATC-P3-GKT-01": {"type": "Air Conditioner", "rawType": ... | 2026-07-11 11:15:26.743000 |

</details>

### `WBN_DATABASE`.`POS POSSIBILITY For HAULAGE`

- **Rows**: 23
- **Flags**: PLAN

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `TOS LOCATION` | nvarchar(50) | yes |
| 3 | `POS LOCATION` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | TOS LOCATION | POS LOCATION |
|---|---|---|
| 1 | CBB | POS BIRI-BIRI |
| 2 | CBB | POS UNI-UNI |
| 3 | CBB | POS GOMDI |
| 4 | CBB | EOS |
| 5 | CBB | POS 14 |

</details>

### `WBN_DATABASE`.`REQUEST_SALES_LATE_2025`

- **Rows**: 18
- **Flags**: col:TIME
- **Date column**: `REQUEST_DATE` — 2025-11-01 00:00:00 to 2025-11-01 00:00:00

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `STOCK_ID` | nvarchar(50) | no |
| 2 | `REQUEST` | nvarchar(50) | no |
| 3 | `REQUEST_DATE` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| STOCK_ID | REQUEST | REQUEST_DATE |
|---|---|---|
| ABM.346 | SOLD | 2025-11-01 00:00:00 |
| ACM.386 | SOLD | 2025-11-01 00:00:00 |
| ACM.509 | SOLD | 2025-11-01 00:00:00 |
| ADM.334 | SOLD | 2025-11-01 00:00:00 |
| ADM.574 | SOLD | 2025-11-01 00:00:00 |

</details>

### `FMS_DB`.`FMS_USER_ACTIVITY`

- **Rows**: 17
- **Flags**: none
- *redacted columns: USERNAME*

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `USERNAME` 🔒 | nvarchar(100) | no |
| 2 | `LAST_SEEN` | bigint | no |
| 3 | `SOURCE` | nvarchar(80) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| USERNAME | LAST_SEEN | SOURCE |
|---|---|---|
| [REDACTED] | 1784531172382 | fms-prototype |
| [REDACTED] | 1784421527895 | fms-prototype |
| [REDACTED] | 1785026225538 | fms-prototype |
| [REDACTED] | 1784801118879 | fms-prototype |
| [REDACTED] | 1784274179640 | fms-prototype |

</details>

### `FMS_DB`.`FMS_ASSIGNMENTS`

- **Rows**: 16
- **Flags**: col:TIME
- **Date column**: `UPDATED` — 2026-07-05 16:19:11 to 2026-07-27 18:52:31

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ASSIGN_TYPE` | nvarchar(30) | no |
| 2 | `KEY_A` | nvarchar(150) | no |
| 3 | `KEY_B` | nvarchar(150) | no |
| 4 | `EXTRA` | nvarchar(max) | yes |
| 5 | `UPDATED` | datetime | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ASSIGN_TYPE | KEY_A | KEY_B | EXTRA | UPDATED |
|---|---|---|---|---|
| pile_excav | KRENE.I.3288 | E377 |  | 2026-07-05 16:19:11.883000 |
| pile_excav | KRENE.I.3289 | E377 |  | 2026-07-06 09:41:49.643000 |
| pile_excav | KRENE.I.3290 | E042 |  | 2026-07-06 09:42:07.277000 |
| pile_excav | KRENE.I.3291 | E042 |  | 2026-07-08 08:08:15.370000 |
| pile_excav | KRENE.I.3293 | E377 |  | 2026-07-08 08:08:16.767000 |

</details>

### `WBN_DATABASE`.`BLOCK_ID_XYPARAM`

- **Rows**: 16
- **Flags**: none

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PIT` | nvarchar(255) | yes |
| 2 | `B_XORIGIN` | float | yes |
| 3 | `B_INCREMENT` | float | yes |
| 4 | `S_YORIGIN` | float | yes |
| 5 | `S_INCREMENT` | float | yes |
| 6 | `N_ZORIGIN` | float | yes |
| 7 | `N_INCREMENT` | float | yes |
| 8 | `INFO` | nvarchar(255) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| PIT | B_XORIGIN | B_INCREMENT | S_YORIGIN | S_INCREMENT | N_ZORIGIN | N_INCREMENT | INFO |
|---|---|---|---|---|---|---|---|
| CBB | 380312.5 | 12.5 | 60225.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + incr * BLOCK_ID (B,S) |
| CUU | 381100.0 | 12.5 | 54975.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + incr * BLOCK_ID (B,S) |
| CSW | 383950.0 | 12.5 | 55775.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + incr * BLOCK_ID (B,S) |
| CAS5 | 385425.0 | 12.5 | 55212.5 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + incr * BLOCK_ID (B,S) |
| CAS6 | 384325.0 | 12.5 | 56975.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + incr * BLOCK_ID (B,S) |

</details>

### `WBN_DATABASE`.`CRUSHER_SURVEY_LOYPOLOY`

- **Rows**: 16
- **Flags**: col:TIME
- **Date column**: `DATE` — 2024-10-13 to 2024-10-13

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `DATE` | date | yes |
| 3 | `TYPE_OF_SURVEY` | nvarchar(50) | yes |
| 4 | `SURVEY_WEEK` | nvarchar(50) | yes |
| 5 | `MATERIAL_ID` | nvarchar(50) | yes |
| 6 | `SURVEY_METHOD` | nvarchar(50) | yes |
| 7 | `LOCATION` | nvarchar(50) | yes |
| 8 | `VOLUME (LCM)` | float | yes |
| 9 | `VOLUME (BCM)` | float | yes |
| 10 | `DENSITY` | float | yes |
| 11 | `ADJUSTED_DENSITY` | float | yes |
| 12 | `WMT` | float | yes |
| 13 | `STOCK_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | DATE | TYPE_OF_SURVEY | SURVEY_WEEK | MATERIAL_ID | SURVEY_METHOD | LOCATION | VOLUME (LCM) | VOLUME (BCM) | DENSITY | ADJUSTED_DENSITY | WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 2024-10-13 | PONCTUAL |  | TOS | Ground | CRUSHER LOYPOLOY KM16 | 5415.534 | 5415.534 |  |  |  |
| 9 | 2024-10-13 | PONCTUAL |  | TOS | Ground | CRUSHER LOYPOLOY KM16 | 977.984 | 977.984 |  |  |  |
| 10 | 2024-10-13 | PONCTUAL |  | BC 2-3 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 10.105 | 10.105 |  |  |  |
| 11 | 2024-10-13 | PONCTUAL |  | BC 2-3 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 4.507 | 4.507 |  |  |  |
| 12 | 2024-10-13 | PONCTUAL |  | 1-2 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 1.56 | 1.56 |  |  |  |

*(first 12 of 13 columns shown)*

</details>

### `FMS_DB`.`FMS_MESSAGES`

- **Rows**: 14
- **Flags**: col:TIME
- *redacted columns: FROM_NAME*

<details><summary>15 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | nvarchar(80) | no |
| 2 | `FROM_USER` | nvarchar(100) | yes |
| 3 | `FROM_NAME` 🔒 | nvarchar(200) | yes |
| 4 | `TO_ADDR` | nvarchar(200) | yes |
| 5 | `SUBJECT` | nvarchar(400) | yes |
| 6 | `BODY` | nvarchar(max) | yes |
| 7 | `CONTEXT` | nvarchar(200) | yes |
| 8 | `SHIFT` | float | yes |
| 9 | `PLAN_DATE` | nvarchar(20) | yes |
| 10 | `TS` | bigint | yes |
| 11 | `ANON` | bit | yes |
| 12 | `POPUP` | bit | yes |
| 13 | `PINNED` | bit | yes |
| 14 | `REPLY_TO` | nvarchar(80) | yes |
| 15 | `READ_JSON` | nvarchar(max) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | FROM_USER | FROM_NAME | TO_ADDR | SUBJECT | BODY | CONTEXT | SHIFT | PLAN_DATE | TS | ANON | POPUP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| msg_1784101276221_rdinkelmann | rdinkelmann | [REDACTED] | handover |  | Remember to assign the trucks | /dispatch |  |  | 1784101276221 | True | False |
| msg_1784101842600_rdinkelmann | rdinkelmann | [REDACTED] | user:sbell | Verify Tofu TOS | Hi Simon,

Please verify if Tall Tofu TOS areas are visib... |  |  |  | 1784101842600 | True | True |
| msg_1784102803166_rdinkelmann | rdinkelmann | [REDACTED] | user:ytae | Testing | etsting |  |  |  | 1784102803166 | True | True |
| msg_1784188322376_rdinkelmann | rdinkelmann | [REDACTED] | user:aassegaff | Special Agent | Hi my name is Kohli, how can i assist you today? |  |  |  | 1784188322376 | True | True |
| msg_1784188344839_rdinkelmann | rdinkelmann | [REDACTED] | user:aanas | Special Agent | Hi my name is Yusuf, how can i assist you today? |  |  |  | 1784188344839 | True | True |

*(first 12 of 15 columns shown)*

</details>

### `FMS_DB`.`RES_WATER_FILLING_POINTS`

- **Rows**: 14
- **Flags**: col:COORD, col:STATUS

<details><summary>9 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `Region` | nvarchar(50) | yes |
| 2 | `Location` | nvarchar(100) | yes |
| 3 | `Station ID` | nvarchar(50) | no |
| 4 | `Contractor` | nvarchar(50) | yes |
| 5 | `Status` | nvarchar(20) | yes |
| 6 | `Latitude` | float | yes |
| 7 | `Longitude` | float | yes |
| 8 | `Dispenser_Count` | int | yes |
| 9 | `Match_Radius_Meters` | float | yes |

</details>

<details><summary>Sample rows (5)</summary>

| Region | Location | Station ID | Contractor | Status | Latitude | Longitude | Dispenser_Count | Match_Radius_Meters |
|---|---|---|---|---|---|---|---|---|
| BLB | BLB08 | WF_BLB08 | RIM | Active | 0.520042 | 127.963745 | 1 | 50.0 |
| BLB | BLB19 | WF_BLB19 | RIM | Active | 0.536398 | 127.964388 | 1 | 50.0 |
| CBB | CBB15 | WF_CBB15 | RIM | Active | 0.524399 | 127.934441 | 1 | 50.0 |
| KR | KM18 | WF-HR-18 | RIM | Active | 0.535638 | 127.900112 | 1 | 50.0 |
| KR | KM20 | WF-HR20 | RIM | Active | 0.55315 | 127.9042 | 1 | 75.0 |

</details>

### `WBN_DATABASE`.`ACTIVITIES`

- **Rows**: 13
- **Flags**: col:STATUS

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ACTIVITY` | nvarchar(20) | no |
| 2 | `ORIGIN_TYPE` | nvarchar(50) | yes |
| 3 | `DESTINATION_TYPE` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ACTIVITY | ORIGIN_TYPE | DESTINATION_TYPE |
|---|---|---|
| BEDDING |  |  |
| CONSTRUCTION | CRUSHER | INFRA |
| DIRECT | TOS | YARD |
| DIRECT IWIP DATA | TOS | YARD |
| HAULAGE | TOS | POS |

</details>

### `FMS_DB`.`FMS_JOB_RUNS`

- **Rows**: 12
- **Flags**: col:TIME
- **Date column**: `RUN_DATE` — 2026-07-16 to 2026-07-27
- *redacted columns: JOB_NAME*

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `JOB_NAME` 🔒 | varchar(64) | no |
| 2 | `RUN_DATE` | date | no |
| 3 | `RAN_AT` | bigint | yes |
| 4 | `INSTANCE` | varchar(64) | yes |
| 5 | `ROWS_AFFECTED` | int | yes |

</details>

<details><summary>Sample rows (5)</summary>

| JOB_NAME | RUN_DATE | RAN_AT | INSTANCE | ROWS_AFFECTED |
|---|---|---|---|---|
| [REDACTED] | 2026-07-16 | 1784176937295 | Rudolfs-MacBook-Air.local | 0 |
| [REDACTED] | 2026-07-17 | 1784251068453 | Rudolfs-MacBook-Air.local |  |
| [REDACTED] | 2026-07-18 | 1784333917043 | Rudolfs-MacBook-Air.local |  |
| [REDACTED] | 2026-07-19 | 1784425378761 | Rudolfs-MacBook-Air.local | 21819 |
| [REDACTED] | 2026-07-20 | 1784511297719 | Rudolfs-MacBook-Air.local | 279357 |

</details>

### `WBN_DATABASE`.`HAULAGE CONTRACTORS`

- **Rows**: 11
- **Flags**: PLAN

<details><summary>2 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `CONTRACTOR` | nvarchar(50) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | CONTRACTOR |
|---|---|
| 1 | GMG |
| 2 | STM |
| 3 | SMA |
| 4 | PPP |
| 5 | RIM |

</details>

### `WBN_DATABASE`.`SUPERVISION_SAFETY_ACTIONS`

- **Rows**: 6
- **Flags**: col:STATUS, col:TIME
- **Date column**: `ACTION_DUE_DATE` — 2025-09-10 00:00:00 to 2025-09-30 00:00:00
- *redacted columns: HPO_HPI, HPO_HPI_CLASSIFICATION*

<details><summary>23 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `EVENT_NO` | int | yes |
| 3 | `HPO_HPI` 🔒 | nvarchar(50) | yes |
| 4 | `HPO_HPI_CLASSIFICATION` 🔒 | nvarchar(50) | yes |
| 5 | `ACTION_ID` | float | yes |
| 6 | `EVENT_TITLE` | nvarchar(max) | yes |
| 7 | `EVENT_DESCRIPTION` | nvarchar(max) | yes |
| 8 | `ACTION_PRIORITY` | nvarchar(50) | yes |
| 9 | `ACTION_CORRECTIVE` | nvarchar(max) | yes |
| 10 | `ACTION_DEPARTMENT` | nvarchar(max) | yes |
| 11 | `ACTION_ASSIGN_TO` | nvarchar(max) | yes |
| 12 | `ACTION_DUE_DATE` | datetime | yes |
| 13 | `ACTION_PROGRESS_%` | float | yes |
| 14 | `ACTION_STATUS` | nvarchar(max) | yes |
| 15 | `ACTION_VERIFICATION_DATE` | datetime | yes |
| 16 | `ACTION_OUTSTANDING_DAYS` | nvarchar(max) | yes |
| 17 | `ACTION_OWNER` | nvarchar(max) | yes |
| 18 | `ACTION_OWNER_POSITION` | nvarchar(max) | yes |
| 19 | `ACTION_OWNER_DEPARTMENT` | nvarchar(max) | yes |
| 20 | `ACTION_RESPONSIBLE_SPT` | nvarchar(max) | yes |
| 21 | `ACTION_RESPONSIBLE_SPV` | nvarchar(max) | yes |
| 22 | `ACTION_REMARK` | nvarchar(max) | yes |
| 23 | `PHOTO_PATH` | nvarchar(500) | yes |

</details>

<details><summary>Sample rows (5)</summary>

| ID | EVENT_NO | HPO_HPI | HPO_HPI_CLASSIFICATION | ACTION_ID | EVENT_TITLE | EVENT_DESCRIPTION | ACTION_PRIORITY | ACTION_CORRECTIVE | ACTION_DEPARTMENT | ACTION_ASSIGN_TO | ACTION_DUE_DATE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 87193 | [REDACTED] | [REDACTED] | 78717.0 | No Safety Fence at KM 22 Safety Post | With the expansion of the Haul Road Width, the Safety Pos... | MEDIUM | Install a new Fence along the ledge to remove the risk of... | TEST | Douglas, Douglas (60005842) | 2025-09-30 00:00:00 |
| 5 | 86687 | [REDACTED] | [REDACTED] | 78801.0 | DT 6626 Contact With CT B683 | On Saturday, August 2, 2025, at 3:30 PM, a Huafei Recover... | MEDIUM | De-commission Huafei towing truck from operating on WBN h... | Administration | SITORUS, Irwan Edel F. (EXTSHAL0019) | 2025-09-15 00:00:00 |
| 6 | 88126 | [REDACTED] | [REDACTED] | 79287.0 | Leg Injury Due to Jack Slippage | The victim was working to install an excavator track pin ... | HIGH | DDT Training | Haulage Operation | RAHUL DHIMAN (RAHUL) | 2025-09-10 00:00:00 |
| 7 | 88126 | [REDACTED] | [REDACTED] | 79287.0 | Leg Injury Due to Jack Slippage | The victim was working to install an excavator track pin ... | HIGH | DDT Training | Haulage Operation | RAHUL DHIMAN (RAHUL) | 2025-09-11 00:00:00 |
| 8 | 89524 | [REDACTED] | [REDACTED] | 79516.0 | Radiator Overheating Burn Incident | The driver of DT N441 stopped the unit at KM 49 after the... | Critical | Retrain all drivers on radiator risks and controls (focus... | HAULAGE OPERATION | RAHUL DHIMAN | 2025-09-15 00:00:00 |

*(first 12 of 23 columns shown)*

</details>

### `FMS_DB`.`FMS_SETTINGS`

- **Rows**: 5
- **Flags**: col:TIME

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `SKEY` | varchar(64) | no |
| 2 | `SVAL` | nvarchar(400) | yes |
| 3 | `UPDATED_AT` | bigint | yes |

</details>

<details><summary>Sample rows (5)</summary>

| SKEY | SVAL | UPDATED_AT |
|---|---|---|
| access_suspended | false | 1784687140468 |
| blocked_users |  | 1784957152073 |
| ip_lock_enabled | false | 1784183919844 |
| lv_daily_report_automatic | false | 1785114651103 |
| lv_daily_report_recipients | bel.simon@wedabaynickel.id | 1785114650285 |

</details>

### `FMS_DB`.`RES_CRITICAL_ZONES`

- **Rows**: 4
- **Flags**: none

<details><summary>5 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ZoneID` | int | no |
| 2 | `Region_Code` | varchar(10) | yes |
| 3 | `KM_From` | decimal(6,3) | yes |
| 4 | `KM_To` | decimal(6,3) | yes |
| 5 | `Zone_Type` | varchar(50) | yes |

</details>

<details><summary>Sample rows (4)</summary>

| ZoneID | Region_Code | KM_From | KM_To | Zone_Type |
|---|---|---|---|---|
| 1 | TF | 47.000 | 48.000 | LOADED |
| 2 | TF | 59.000 | 60.000 | LOADED |
| 3 | KR | 34.000 | 36.000 | LOADED |
| 4 | TF | 67.000 | 67.500 | EMPTY |

</details>

### `FMS_DB`.`FMS_LV_DAILY_REPORTS`

- **Rows**: 3
- **Flags**: col:STATUS, col:TIME
- **Date column**: `REPORT_DATE` — 2026-07-24 to 2026-07-26

<details><summary>12 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `REPORT_DATE` | date | no |
| 2 | `PERIOD_START` | bigint | no |
| 3 | `PERIOD_END` | bigint | no |
| 4 | `VISIT_COUNT` | int | yes |
| 5 | `UNIT_COUNT` | int | yes |
| 6 | `TOTAL_DURATION_SEC` | bigint | yes |
| 7 | `REPORT_HTML` | nvarchar(max) | yes |
| 8 | `RECIPIENTS` | nvarchar(2000) | yes |
| 9 | `GENERATED_AT` | bigint | yes |
| 10 | `SENT_AT` | bigint | yes |
| 11 | `SEND_STATUS` | nvarchar(40) | yes |
| 12 | `GENERATED_BY` | nvarchar(100) | yes |

</details>

<details><summary>Sample rows (3)</summary>

| REPORT_DATE | PERIOD_START | PERIOD_END | VISIT_COUNT | UNIT_COUNT | TOTAL_DURATION_SEC | REPORT_HTML | RECIPIENTS | GENERATED_AT | SENT_AT | SEND_STATUS | GENERATED_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-24 | 1784844000000 | 1784930400000 | 17 | 9 | 458243 | <!doctype html><html><body style="font-family:Arial;color... | r.dinkelmann77@gmail.com | 1784958417517 | 1784958417517 | SENT | system |
| 2026-07-25 | 1784930400000 | 1785016800000 | 9 | 4 | 43375 | <!doctype html><html><body style="font-family:Arial;color... | cindha.rizkiana@wedabaynickel.id | 1785025537601 | 1785025537601 | SENT | rdinkelmann |
| 2026-07-26 | 1785016800000 | 1785103200000 | 10 | 5 | 29688 | <!doctype html><html><body style="font-family:Arial;color... | bel.simon@wedabaynickel.id | 1785114657394 | 1785114657394 | SENT | rdinkelmann |

</details>

### `WBN_DATABASE`.`CRUSHER_CF`

- **Rows**: 3
- **Flags**: none

<details><summary>3 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `ID` | int | no |
| 2 | `MATERIAL` | nvarchar(255) | yes |
| 3 | `CF` | float | yes |

</details>

<details><summary>Sample rows (3)</summary>

| ID | MATERIAL | CF |
|---|---|---|
| 1 | CS | 1.12 |
| 2 | SS1 | 1.21 |
| 3 | SS2 | 1.21 |

</details>

### `WBN_DATABASE`.`HAULAGE_ADJ`

- **Rows**: 3
- **Flags**: PLAN, col:TIME
- **Date column**: `DATE` — 2025-02-01 00:00:00 to 2025-02-01 00:00:00

<details><summary>8 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `YEAR` | float | yes |
| 2 | `MONTH` | float | yes |
| 3 | `DATE` | datetime | yes |
| 4 | `MATERIAL_CLASS` | nvarchar(255) | yes |
| 5 | `WMT_SURVEY` | float | yes |
| 6 | `WMT_HAULAGE` | float | yes |
| 7 | `WMT_TC` | float | yes |
| 8 | `ADJ_TC` | float | yes |

</details>

<details><summary>Sample rows (3)</summary>

| YEAR | MONTH | DATE | MATERIAL_CLASS | WMT_SURVEY | WMT_HAULAGE | WMT_TC | ADJ_TC |
|---|---|---|---|---|---|---|---|
| 2025.0 | 2.0 | 2025-02-01 00:00:00 | HGS | 1951143.0215260943 | 1975839.124233704 |  | 0.87 |
| 2025.0 | 2.0 | 2025-02-01 00:00:00 | LGS | 365833.5282214447 | 375319.12500000006 |  | 0.86 |
| 2025.0 | 2.0 | 2025-02-01 00:00:00 | CS |  |  |  |  |

</details>

### `FMS_DB`.`FMS_INSTANCES`

- **Rows**: 2
- **Flags**: col:TIME
- *redacted columns: GIT_HASH*

<details><summary>7 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `INSTANCE_ID` | nvarchar(120) | no |
| 2 | `GIT_HASH` 🔒 | nvarchar(40) | yes |
| 3 | `GIT_SUBJECT` | nvarchar(400) | yes |
| 4 | `GIT_TIME` | nvarchar(40) | yes |
| 5 | `STARTED_AT` | bigint | yes |
| 6 | `LAST_BEAT` | bigint | yes |
| 7 | `HOST` | nvarchar(120) | yes |

</details>

<details><summary>Sample rows (2)</summary>

| INSTANCE_ID | GIT_HASH | GIT_SUBJECT | GIT_TIME | STARTED_AT | LAST_BEAT | HOST |
|---|---|---|---|---|---|---|
| fms-prototype | [REDACTED] | auto: sync 2026-07-27 15:59 | 2026-07-27 15:59:21 +0700 | 1784185805666 | 1785149023574 | fms-prototype |
| Rudolfs-MacBook-Air.local | [REDACTED] | auto: sync 2026-07-27 15:59 | 2026-07-27 15:59:21 +0700 | 1784089672452 | 1785147636420 | Rudolfs-MacBook-Air.local |

</details>

### `FMS_DB`.`FMS_DOCS`

- **Rows**: 1
- **Flags**: col:TIME
- *redacted columns: SRC_HASH*

<details><summary>4 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `DOC_KEY` | varchar(64) | no |
| 2 | `CONTENT` | nvarchar(max) | yes |
| 3 | `UPDATED_AT` | bigint | yes |
| 4 | `SRC_HASH` 🔒 | varchar(40) | yes |

</details>

<details><summary>Sample rows (1)</summary>

| DOC_KEY | CONTENT | UPDATED_AT | SRC_HASH |
|---|---|---|---|
| install_plan_report | <!doctype html><html><head><meta charset='utf-8'><title>F... | 1785141468482 | [REDACTED] |

</details>

### `FMS_DB`.`FMS_GEOFENCE_ALERT_RULES`

- **Rows**: 1
- **Flags**: col:COORD
- *redacted columns: RULE_NAME, GEOFENCE_NAME, EMAIL_TO, ESCALATION_EMAIL_TO, ENTRY_USERNAMES, ESCALATION_USERNAMES*

<details><summary>17 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `RULE_ID` | varchar(36) | no |
| 2 | `RULE_NAME` 🔒 | nvarchar(160) | no |
| 3 | `GEOFENCE_ID` | nvarchar(20) | no |
| 4 | `GEOFENCE_NAME` 🔒 | nvarchar(200) | yes |
| 5 | `TRIGGER_EVENT` | varchar(10) | no |
| 6 | `UNIT_PREFIX` | varchar(40) | no |
| 7 | `MIN_DURATION_SEC` | int | no |
| 8 | `SEVERITY` | varchar(12) | no |
| 9 | `RECIPIENT_ROLE` | varchar(40) | no |
| 10 | `EMAIL_TO` 🔒 | nvarchar(1000) | yes |
| 11 | `ESCALATE_AFTER_MIN` | int | no |
| 12 | `ACTIVE` | bit | no |
| 13 | `CREATED_AT` | bigint | no |
| 14 | `CREATED_BY` | nvarchar(100) | yes |
| 15 | `ESCALATION_EMAIL_TO` 🔒 | nvarchar(1000) | yes |
| 16 | `ENTRY_USERNAMES` 🔒 | nvarchar(2000) | yes |
| 17 | `ESCALATION_USERNAMES` 🔒 | nvarchar(2000) | yes |

</details>

<details><summary>Sample rows (1)</summary>

| RULE_ID | RULE_NAME | GEOFENCE_ID | GEOFENCE_NAME | TRIGGER_EVENT | UNIT_PREFIX | MIN_DURATION_SEC | SEVERITY | RECIPIENT_ROLE | EMAIL_TO | ESCALATE_AFTER_MIN | ACTIVE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d93065c3-9ff2-439b-bbdb-be609204877d | [REDACTED] | 85d11afa | [REDACTED] | ENTER | WBN-LV- | 0 | CRITICAL | dispatcher | [REDACTED] | 5 | True |

*(first 12 of 17 columns shown)*

</details>

### `FMS_DB`.`FMS_LV_VISIT_VERIFICATIONS`

- **Rows**: 1
- **Flags**: col:COORD, col:TIME
- *redacted columns: DETECTED_DRIVER, IMAGE_NAME*

<details><summary>13 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `VISIT_KEY` | nvarchar(240) | no |
| 2 | `PLATE` | nvarchar(60) | yes |
| 3 | `ENTER_TS` | bigint | yes |
| 4 | `DETECTED_DRIVER` 🔒 | nvarchar(200) | yes |
| 5 | `IS_VALID` | bit | yes |
| 6 | `IMAGE_NAME` 🔒 | nvarchar(300) | yes |
| 7 | `IMAGE_MIME` | nvarchar(100) | yes |
| 8 | `IMAGE_DATA` | varbinary(max) | yes |
| 9 | `IMAGE_SIZE` | int | yes |
| 10 | `UPDATED_BY` | nvarchar(100) | yes |
| 11 | `UPDATED_AT` | bigint | yes |
| 12 | `IMAGE_UPLOADED_BY` | nvarchar(100) | yes |
| 13 | `IMAGE_UPLOADED_AT` | bigint | yes |

</details>

<details><summary>Sample rows (1)</summary>

| VISIT_KEY | PLATE | ENTER_TS | DETECTED_DRIVER | IS_VALID | IMAGE_NAME | IMAGE_MIME | IMAGE_DATA | IMAGE_SIZE | UPDATED_BY | UPDATED_AT | IMAGE_UPLOADED_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WBN-LV-C88\|1784954955000 | WBN-LV-C88 | 1784954955000 |  | True | [REDACTED] | image/jpeg | <142564 bytes> | 142564 | rdinkelmann | 1784968057673 | rdinkelmann |

*(first 12 of 13 columns shown)*

</details>

### `FMS_DB`.`FMS_ROADMAP_META`

- **Rows**: 1
- **Flags**: ROAD

<details><summary>2 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `META_KEY` | nvarchar(80) | no |
| 2 | `META_VALUE` | nvarchar(200) | yes |

</details>

<details><summary>Sample rows (1)</summary>

| META_KEY | META_VALUE |
|---|---|
| seed_version | 5 |

</details>

### `FMS_DB`.`FMS_TRUCK_CYCLES`

- **Rows**: 1
- **Flags**: TRUCK, col:COORD, col:STATUS, col:TIME
- **Date column**: `UPDATED_AT` — 2026-07-25 21:40:31 to 2026-07-25 21:40:31

<details><summary>16 columns</summary>

| # | Column | Type | Null |
|---:|---|---|---|
| 1 | `PLATE` | nvarchar(50) | no |
| 2 | `STATE` | nvarchar(20) | yes |
| 3 | `EXCAVATOR` | nvarchar(50) | yes |
| 4 | `SRC` | nvarchar(160) | yes |
| 5 | `DUMP` | nvarchar(200) | yes |
| 6 | `DUMP_PILE` | nvarchar(160) | yes |
| 7 | `MAT` | nvarchar(60) | yes |
| 8 | `PILE` | nvarchar(160) | yes |
| 9 | `PIT` | nvarchar(60) | yes |
| 10 | `PLAN_DATE` | nvarchar(20) | yes |
| 11 | `SHIFT` | nvarchar(10) | yes |
| 12 | `SINCE` | bigint | yes |
| 13 | `CYCLES` | int | yes |
| 14 | `STAMPS` | nvarchar(max) | yes |
| 15 | `UPDATED_AT` | datetime | yes |
| 16 | `TRANSITION_META` | nvarchar(max) | yes |

</details>

<details><summary>Sample rows (1)</summary>

| PLATE | STATE | EXCAVATOR | SRC | DUMP | DUMP_PILE | MAT | PILE | PIT | PLAN_DATE | SHIFT | SINCE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N051 | TRAVEL_LOADED | W659 | BLB | FENI A |  | SAP |  | BLB |  |  | 1784983231318 |

*(first 12 of 16 columns shown)*

</details>

---

Regenerate: `python scripts/db_reconnaissance.py` (requires VPN).
