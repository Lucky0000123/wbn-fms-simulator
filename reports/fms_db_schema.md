# FMS_DB schema recon (Phase 4, Task 1)

Generated 2026-07-28T07:47:45+00:00. Read-only scan.

## Headline: the GPS feed does not cover haul trucks

This is the finding that decides Task 2, so it leads.

| | |
|---|---|
| Distinct units in `FMS_PLAYBACK_TRACK_DATA` | 217 |
| Of those, resolvable in `FMS_EQUIPMENTS` | 217 (all of them) |
| Haul trucks registered in `FMS_EQUIPMENTS` | 940 |
| **Haul trucks that have GPS** | **0** |
| GPS date range | 2026-03-21 → 2026-07-28 |

The two fleets are disjoint by department. GPS-equipped units belong to:

```
  工程一车间                        73
  工程二车间                        50
  工程三车间                        27
  尾矿库 KM9 RSF 车间               23
  工程四车间                        13
  后勤车间 LOGISTICS               11
```

Those are engineering (工程) and logistics (后勤) workshops. The haul fleet that produces weighbridge tickets belongs to:

```
  RIM运输部 C 车间                  144
  RIM运输部 H 车间                  116
  RIM运输部 G 车间                  109
  RIM运输部 D 车间                  106
  RIM运输部 F 车间                  103
  RIM运输部 A 车间                  98
```

`RIM运输部` is the RIM transport division. Registration plates confirm the split independently: GPS units carry SS/Y/P/F/W prefixes, ticket trucks carry N/R/L/K/B/S/PP/SM.

**Consequence:** GPS-derived queue time cannot be joined to trips at any date range. Trip-weighted join rate is 0.0% against a 60% gate. Task 2 is blocked by data availability, not by effort.

## Answers to the seven recon questions

| # | Question | Answer |
|---|---|---|
| 1 | All tables + row counts | Yes — 89 objects, listed below |
| 2 | `FMS_PLAYBACK_TRACK_DATA` fields | `plateNumber`, `lat`, `lng`, `speed`, `time`, `FETCH_DATE`, `course`, `distance`, `engine`, `acc`, `imei` |
| 3 | `FMS_EQUIPMENTS` links trucks↔excavators? | **No.** Columns are `truckId, plateNumber, orgName, orgId, imei, active` — a device registry, not a dispatch table. No excavator or loader field. |
| 4 | `RES_EMPLOYEES` operator/equipment/shift fields? | **No.** 8,958 rows, 9 columns: `FULL_NAME, GENDER, ORIGIN, ORIGIN_CLASS, EMPLOYEE_ID, CONTRACTOR, DIVISION, JOB_TITLE, GRADE`. No equipment assignment, no shift roster, and **no hire date**, so `operator_experience_days` cannot be derived either. It is an HR roster, not a dispatch record. |
| 5 | Geofence polygons for loading/dump/waiting zones | **Yes** — `FMS_GEOFENCES` (3,490 rows) with `LATLNGS` polygons, `CENTER_LAT/LNG`, `TYPE` (pit/loading/water/zone). `ELEVATIONS` exists but is 100% NULL. |
| 6 | Any table recording which excavator loaded which truck | **Yes, but unusable.** `WBN_DATABASE.PRODUCTION_PIT_HOURLY` carries 839,609 rows since 2025-12-27 with `EXCAVATOR_ID` + `TRUCK_ID` + `DATE`/`SHIFT`/`START_HOUR` (252 excavators, 938 trucks); `FMS_DB.FMS_TRUCK_ASSIGNMENTS` has a small `EXCAVATOR` column (408 rows, 3 units). Neither joins to haul trips: mining records fleet numbers (`AD4059`), weighbridge tickets use plate ids (`A342`), and the overlap across 1,482 trip trucks is **zero**. `EQUIPMENTS.ID_EQ` matches values in both namespaces but only 25 rows carry both, so it is not a crosswalk. Trip-weighted join 0.0%. Match Factor therefore keys on loading point, and the fix needed is an identity map, not new data. |
| 7 | Table linking employees to equipment per shift | **No.** `RES_EMPLOYEES` is the only table in FMS_DB carrying an employee/operator column, and it holds no equipment field. Task 3 (operator identity) is therefore blocked for the same reason as Task 2: the link does not exist in the data. |

### Tables carrying an operator/driver/equipment-id column

```
  RES_EMPLOYEES
```

## Column dumps

### `FMS_PLAYBACK_TRACK_DATA`

```
FETCH_DATE datetime, plateNumber nvarchar, acc float, deviceType nvarchar, distance float, lng float, driving_time float, dump_energy nvarchar, receive_time float, loc_type float, speed float, engine float, oils float, course float, imei bigint, time bigint, interpolation_flag float, lat float
```

### `FMS_EQUIPMENTS`

```
FETCH_DATE datetime, truckId nvarchar, orgName nvarchar, plateNumber nvarchar, orgId bigint, imei bigint, active nvarchar
```

### `RES_EMPLOYEES`

```
FULL_NAME nvarchar, GENDER nvarchar, ORIGIN nvarchar, ORIGIN_CLASS nvarchar, EMPLOYEE_ID float, CONTRACTOR nvarchar, DIVISION nvarchar, JOB_TITLE nvarchar, GRADE float
```

### `FMS_GEOFENCES`

```
GF_ID nvarchar, NAME nvarchar, TYPE nvarchar, SHAPE nvarchar, LATLNGS nvarchar, CENTER_LAT float, CENTER_LNG float, RADIUS float, PIT_ID nvarchar, PILE_ID nvarchar, TOS_STATUS nvarchar, TOS_AREA nvarchar, TOS_PIT nvarchar, ELEVATIONS nvarchar, SURVEY_DATE nvarchar, CREATED bigint, CREATED_BY nvarchar
```

### `RES_CRITICAL_ZONES`

```
ZoneID int, Region_Code varchar, KM_From decimal, KM_To decimal, Zone_Type varchar
```

### `RES_SPEED_LIMIT_ZONES`

```
Segment Code nvarchar, Chainage Range (KM) nvarchar, Speed Limit (km/h) float, Geometry Type nvarchar, Area Type nvarchar, Loading/Unloading Category nvarchar, Operating Area nvarchar, Responsible Department nvarchar, Longitude float, Latitude float, Location Description nvarchar, Remarks nvarchar, KM_From decimal, KM_To decimal, Region_Code varchar, Is_Critical bit
```

### `FMS_SECURITY_INCIDENT_DATA`

```
FETCH_DATE datetime, id nvarchar, orgId bigint, speed float, checkDriverName nvarchar, endLat float, carrierName nvarchar, areaName nvarchar, endPrecision float, difftime float, startTime bigint, endLng float, driverNo nvarchar, lat float, limitSpeed nvarchar, mileage float, truckId nvarchar, address nvarchar, orgName nvarchar, lng float, startAddress nvarchar, updateTime bigint, eventType nvarchar, maxSpeed float, plateNumber nvarchar, markerType nvarchar, driverId float, classTypeName nvarchar, createTime bigint, speedPercent nvarchar, eventTypeName nvarchar, imei nvarchar, driverName nvarchar, endTime bigint, markerRemark nvarchar, endAddress nvarchar
```

### `OVERSPEED_EVENTS`

```
Event_Type_Name nvarchar, Geofence Zone nvarchar, Location nvarchar, Location_Speed nvarchar, Vehicle_Number nvarchar, Driver_Name nvarchar, DriverNo nvarchar, Contractor nvarchar, Start_Time datetime, Contractor_Team varchar, End_Time datetime, Start_Longitude decimal, Start_Latitude decimal, End_Latitude decimal, End_Longitude decimal, Shift varchar, Maximum_Speed int, Driving_Mileage decimal, Speed_Limit int, Actual_Overspeed int, Source_File varchar, Import_Date datetime, Is_Critical int, Critical_Zone_Type varchar, SectionDirection nvarchar, SectionKM decimal, difftime float, Shift_Date date, Speed_Class1 varchar, OS_Flag1 int, Is_Latest_Shift int, Is_Previous_Shift int
```

### `FMS_GEOFENCE_VISITS`

```
EVENT_ID varchar, UNIT_ID varchar, UNIT_TYPE varchar, ORG_NAME nvarchar, GEOFENCE_ID nvarchar, GEOFENCE_NAME nvarchar, GEOFENCE_TYPE varchar, ENTER_TS bigint, EXIT_TS bigint, DURATION_SEC int, ENTER_LAT float, ENTER_LNG float, EXIT_LAT float, EXIT_LNG float, STATUS varchar, SOURCE varchar, CREATED_AT bigint
```

### `FMS_HAUL_CYCLES`

```
CYCLE_ID int, TRUCK_PLATE nvarchar, PLAN_DATE date, SHIFT float, PIT nvarchar, TOS_PILE nvarchar, EXCAVATOR nvarchar, DESTINATION nvarchar, MATERIAL nvarchar, DUMP_TS datetime
```

## Sample rows (credential- and PII-filtered)

### `FMS_EQUIPMENTS`

```
             FETCH_DATE             truckId     orgName plateNumber               orgId            imei active
2026-07-28 14:44:25.320 6916297240046994306 RIM运输部 E 车间        K977 7190741736405205894 107015291859617    YES
2026-05-14 14:44:30.313 6921009760640961159 RIM运输部 C 车间        K523 7190740880934963462 131064219065221     NO
2026-04-12 14:44:23.520 6922135043012034832 RIM运输部 B 车间        K562 7190740352016450440 107015291860264     NO
```

## All objects by row count

| Table | Type | Rows |
|---|---|---:|
| `FMS_PLAYBACK_TRACK_DATA` | BASE TABLE | 26,083,080 |
| `auto_kmFMS_PLAYBACK_TRACK_DATA` | BASE TABLE | 19,074,628 |
| `FMS_ENTRY_EXIT_DATA` | BASE TABLE | 11,004,998 |
| `FMS_SECURITY_INCIDENT_DATA` | BASE TABLE | 5,291,587 |
| `autoFMS_SECURITY_INCIDENT_KILOMETER` | BASE TABLE | 4,114,048 |
| `auto_spFMS_PLAYBACK_TRACK_DATA` | BASE TABLE | 1,598,431 |
| `FMS_PLAYBACK_TRACK_24H` | BASE TABLE | 1,289,118 |
| `FMS_INTERVENTION_EVENT_DATA` | BASE TABLE | 1,250,496 |
| `FMS_GPS_Historical` | BASE TABLE | 521,918 |
| `FMS_PLAYBACK_STAY_DATA` | BASE TABLE | 383,092 |
| `FMS_RISK_DATA` | BASE TABLE | 309,427 |
| `FMS_GEOFENCE_VISITS` | BASE TABLE | 46,146 |
| `FMS_CONGESTION_SEG` | BASE TABLE | 27,632 |
| `RES_EMPLOYEES` | BASE TABLE | 8,958 |
| `FMS_GEOFENCES` | BASE TABLE | 3,490 |
| `RADIO_REPROGRAM_TRACK` | BASE TABLE | 3,478 |
| `FMS_TOS_STATUS` | BASE TABLE | 3,404 |
| `FMS_TMS_TOKEN` | BASE TABLE | 2,889 |
| `FMS_EQUIPMENTS` | BASE TABLE | 1,404 |
| `WT_DAILY_PLAN` | BASE TABLE | 1,205 |
| `FMS_UNIT_INSTALLED` | BASE TABLE | 1,182 |
| `FMS_TRUCK_ASSIGNMENTS` | BASE TABLE | 408 |
| `FMS_HAUL_CYCLES` | BASE TABLE | 288 |
| `FMS_QUALITY_DISPATCH` | BASE TABLE | 258 |
| `FMS_DISPATCH_PLAN` | BASE TABLE | 105 |
| `SHP_SED_POND` | BASE TABLE | 91 |
| `FMS_ROADMAP` | BASE TABLE | 87 |
| `SAFETY_DPLAN` | BASE TABLE | 80 |
| `LV_PLAN` | BASE TABLE | 62 |
| `LV_INFO` | BASE TABLE | 57 |
| `FMS_GEOFENCE_ALERTS` | BASE TABLE | 34 |
| `FMS_LOGIN_IPS` | BASE TABLE | 33 |
| `FMS_LV_ZONE_VISITS` | BASE TABLE | 30 |
| `FMS_USERS` | BASE TABLE | 30 |
| `RES_SPEED_LIMIT_ZONES` | BASE TABLE | 27 |
| `FMS_APP_STATE` | BASE TABLE | 23 |
| `FMS_ASSIGNMENTS` | BASE TABLE | 17 |
| `FMS_USER_ACTIVITY` | BASE TABLE | 17 |
| `FMS_MESSAGES` | BASE TABLE | 14 |
| `RES_WATER_FILLING_POINTS` | BASE TABLE | 14 |
| `FMS_JOB_RUNS` | BASE TABLE | 13 |
| `FMS_SETTINGS` | BASE TABLE | 7 |
| `FMS_LV_DAILY_REPORTS` | BASE TABLE | 5 |
| `RES_CRITICAL_ZONES` | BASE TABLE | 4 |
| `FMS_LV_VISIT_VERIFICATIONS` | BASE TABLE | 3 |
| `FMS_INSTANCES` | BASE TABLE | 2 |
| `FMS_GEOFENCE_ALERT_RULES` | BASE TABLE | 1 |
| `FMS_DOCS` | BASE TABLE | 1 |
| `FMS_TRUCK_CYCLES` | BASE TABLE | 1 |
| `FMS_ROADMAP_META` | BASE TABLE | 1 |
| `VW_WT_TRACK_PLAN_SUMMARY` | VIEW | 0 |
| `VW_FMS_LV_VISIT_EVIDENCE` | VIEW | 0 |
| `LV_DRIVER_INFO` | BASE TABLE | 0 |
| `FMS_PLAYBACK_TRACK_CLEAN` | VIEW | 0 |
| `VW_SAFETY_DPLAN` | VIEW | 0 |
| `FMS_ERROR_FLOW` | BASE TABLE | 0 |
| `VW_WT_TRACK_PLAN_SUMMARY_FINAL` | VIEW | 0 |
| `FMS_PLAYBACK_TRACK_WORKINGHOURS` | VIEW | 0 |
| `FMS_PLAYBACK_STAY_CLEAN` | VIEW | 0 |
| `IDLE_EVENTS_WT` | VIEW | 0 |

_89 objects total; the 60 largest are shown._
