## Cross-Database Analysis

Everything below was measured against the live databases. Where a question in
the brief could not be answered, that is stated rather than filled in.

### ID format comparison

The two databases use **three different identifier namespaces**, and confusing
them is what produced the original false conclusion.

| Namespace | Where | Format | Example |
|---|---|---|---|
| Fleet number | `HAULAGE_IWIP_CLEAN.TRUCK_ID` | letter + 3 digits | `A342`, `R707`, `N051` |
| Fleet number | `FMS_EQUIPMENTS.plateNumber` | letter + 3 digits | `A843`, `B279`, `N469` |
| Device serial | `FMS_EQUIPMENTS.truckId` | 19-digit | `6922135043045589259` |
| Device serial | `FMS_GPS_Historical.TRUCK_ID` | 19-digit | `6922135043045589259` |
| IMEI | `FMS_PLAYBACK_TRACK_DATA.imei` | 15-digit | `107015291859999` |

**Haul truck IDs in WBN_DATABASE** (20 examples): `A342`, `A409`, `A450`,
`A486`, `A487`, `A527`, `A530`, `A531`, `A533`, `A535`, `A537`, `A551`, `A553`,
`A560`, `A561`, `A562`, `A565`, `A592`, `A602`, `A604` — 3,236 distinct.

**Equipment IDs in the FMS GPS tables** (20 examples): `6922135043045589259`,
`6922135043045589262`, `6922135043045589264`, `6922135043045589267`,
`6922135043045589271`, `6922135043045589273`, `6922135043146252553`,
`6922135043246915856`, … — 696 distinct in `FMS_GPS_Historical`.

| Comparison | Result |
|---|---|
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_GPS_Historical.TRUCK_ID` | **0 of 3,236** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_EQUIPMENTS.truckId` | **0 of 3,236** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_EQUIPMENTS.plateNumber` | **945 of 1,411 match** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_GEOFENCE_VISITS.UNIT_ID` (Haul Truck) | **613 of 644 (95.2%)** |

**Is the "namespace split" real?** No — it was a **mapping issue**, and the
mapping table already exists. `FMS_EQUIPMENTS` carries both keys on the same
row: `plateNumber` joins to the weighbridge, `truckId` joins to the GPS tables.

```
HAULAGE_IWIP_CLEAN.TRUCK_ID  =  FMS_EQUIPMENTS.plateNumber
                                FMS_EQUIPMENTS.truckId      =  FMS_GPS_Historical.TRUCK_ID
```

`FMS_GPS_Historical` and `FMS_PLAYBACK_TRACK_24H` also carry a `PLATE` column,
so they join to the weighbridge **directly**, without the bridge table.

### GPS coverage check

| Question | Answer |
|---|---|
| Haul trucks with a telematics device | **945 of 1,411 registered units** |
| Reporting in `FMS_PLAYBACK_TRACK_24H` | **479 (50.7%)** |
| Reporting in `FMS_GPS_Historical` | **455 (48.1%)** |
| Sampling interval | **3 seconds** (median gap; p95 = 4 s) |
| Coordinate extent | lat 0.446–0.898, lng 127.86–128.56 — Halmahera |
| Speed values | median 17 km/h, p95 30, max 79 — physical for a haul road |
| Haul-truck visits to **pit** geofences | **15,100** across BLB, CBB, KR, TF |
| Haul-truck visits to **weighbridge** geofences | **19,378** |
| Haul-truck visits to **dumping** geofences | **1,202** |
| Haul-truck visits to **loading** geofences | **835** |

**Conclusion: GPS covers haul trucks.** The `FMS_GEOFENCE_VISITS` table settles
it on geography rather than identifiers — 43,763 rows are explicitly typed
`Haul Truck`, recorded entering and leaving named pits and weighbridges with
GPS-sourced coordinates. Vehicles that repeatedly enter TF, KR and the IWIP
weighbridges are doing haul work regardless of what any registry calls them.

The earlier claim that **0 of 940 haul trucks appear in the GPS feed** was
derived from `FMS_PLAYBACK_TRACK_DATA` alone. On that table it is true: its 219
plates are `SS###`/`E###` support units. The error was generalising one table
to the whole database, and reading Chinese org names (`工程`, `后勤`) as vehicle
classes when they are contractor groupings — exactly as the site operator said.

**The genuine constraint is retention.**

| Table | Coverage | Overlaps the trip extract (2025-12-27 → 2026-07-09)? |
|---|---|---|
| `FMS_GEOFENCE_VISITS` | 2025-12-07 → 2026-07-30, 89 days | **Yes** |
| `FMS_PLAYBACK_TRACK_DATA` | 2026-03-21 → 2026-07-30 | Yes, but no haul trucks |
| `FMS_ENTRY_EXIT_DATA` | 2026-06-08 → 2026-07-30 | Partial |
| `FMS_CONGESTION_SEG` | 2026-07-15 → 2026-07-30 | No |
| `FMS_GPS_Historical` | 2026-07-15 → 2026-07-20 | No |
| `FMS_PLAYBACK_TRACK_24H` | 2026-07-29 → 2026-07-30 | No |

So: raw tracks and derived segment speeds are a **rolling live feed** of days to
two weeks. They cannot be retro-fitted onto the six-month trip history the
current models were trained on, but they can drive a forward-looking simulator
and they accumulate from now. `FMS_GEOFENCE_VISITS` is the exception that
overlaps today.

### Segment / KM section definitions

Segments are defined by **road code + kilometre chainage**, consistently across
five tables.

| Source | Rows | Granularity |
|---|---|---|
| `ALL_HR_KM_SECTIONS` | 27 | named sections with `KM_START`/`KM_END` and junctions |
| `HAUL_ROAD_STA` | 3,122 | chainage points every 25 m with WKT `POINT Z` |
| `DISPATCH ROADS` | 222 | per-route fraction across 27 section columns |
| `RES_SPEED_LIMIT_ZONES` | 27 | posted limit per segment |
| `FMS_CONGESTION_SEG` | 95 `SEG_ID` | 1 km segments, directional |

The eight named roads and their chainage extent, from `HAUL_ROAD_STA`:

| Road | KM from | KM to | Points |
|---|---|---|---|
| TOFU | 39.000 | 67.800 | 1,153 |
| KR | 7.875 | 38.975 | 674 |
| BLB | 2.450 | 19.825 | 416 |
| CBB | 6.300 | 17.125 | 431 |
| CBBB | 14.700 | 16.800 | 85 |
| CRD | 0.000 | 7.850 | 259 |
| HFC | 5.525 | 6.425 | 37 |
| CSW | 4.025 | 5.675 | 67 |

**Does it match the corridor in `simulator_api.py`?** **Yes, exactly.** Checked
against the database rather than assumed:

| Corridor landmark | KM | Confirmed by |
|---|---|---|
| TF (Tofu) | 67.8 | TOFU chainage ends at **67.800** |
| KR | 39.0 | `TF KM39 - KM45` begins at KR NORTH; KR ends 38.975 |
| POS 12 | 27.0 | `KR KM26 - KM27` ends at **POS 12** |
| POS 10 | 17.0 | `KR KM15 - KM17` ends at **POS 10** |
| FENI 15 | 15.0 | `KR KM12 - KM15` ends at **FENI U** |
| FENI 0 | 0.0 | `CRD KM0 - KM2,5` begins at **FENI** |

Every landmark is a named junction at the same chainage. The corridor is
correct; the database simply expresses it at 25 m resolution.

`DISPATCH ROADS` is the most useful of the five: for each origin-destination
pair it gives the **fraction of the haul crossing each named section**. That is
a ready-made route-to-segment decomposition, and it is the missing link between
segment speeds and a route-level cycle time.

### HRM / maintenance data

**Exists: yes.**

| Table | Rows | Date range | Contents |
|---|---|---|---|
| `FMS_HRM_SUPERVISION` (view) | 76,552 | 2026-06-01 → 2026-07-30 | Per-machine work with `LAT`/`LONG`, `SECTIONKM`, `EQUIPMENT_TYPE`, `HOURS`, `DISTANCE_M` |
| `HRM_INSPECTION` | 30,610 | from 2024-10 | Road defects by `KM_START`/`KM_END`, `SEVERITY`, `TYPE`, `STATUS` |
| `HRM_MAJOR_ROADWORK` | 149 | from 2024-10 | Campaigns by KM range, fleet, material, percent complete |
| `HRM_CONTRACT_EQUIPMENT` | 198 | — | Equipment committed per section by contractor |

- **Equipment types:** graders (`GD`) and excavators (`EX`) appear in
  `FMS_HRM_SUPERVISION.EQUIPMENT_TYPE`; `HRM_CONTRACT_EQUIPMENT` also lists
  `EXCA` and `DT`.
- **GPS points:** yes — `FMS_HRM_SUPERVISION` carries `LAT`/`LONG` per work record.
- **Road markers:** yes — `SECTIONKM` gives the chainage worked, and
  `HRM_INSPECTION` gives a `KM_START`/`KM_END` range plus an `STA`/`IDLINK`
  chainage string such as `KR15+500`.

`HRM_INSPECTION` is the more valuable one for the simulator: 30,610
road-condition observations by KM and severity going back to 2024-10. Road
condition plausibly drives cycle-time variance and, unlike truck count, it is
not chosen in response to how the shift is going.

### FMS_CONGESTION_SEG analysis

| Property | Value |
|---|---|
| Rows | 34,988 |
| Date range | 2026-07-15 → 2026-07-30 |
| Distinct `SEG_ID` | **95** |
| Directions | `up`, `down` |
| Columns | `HOUR_TS`, `SEG_ID`, `DIR`, `SUM_SPD`, `FIX_N`, `TRUCK_N`, `SUM_TRAV_MS`, `TRAV_N`, `UPDATED_AT` |

**Source:** derived from the GPS feed. `FIX_N` counts the GPS fixes aggregated
into each segment-hour and `SUM_SPD` sums their speeds, so mean speed is
`SUM_SPD / FIX_N`. Its 2026-07-15 start matches `FMS_GPS_Historical` exactly,
confirming it is computed from those tracks rather than supplied separately.

**Vehicle types:** `TRUCK_N` counts distinct units contributing to that
segment-hour. The table carries no unit-type column, so it cannot be
decomposed into haul trucks versus other vehicles from this table alone —
that would need a join back to the track data via unit identity. Given the
feed is dominated by haul trucks, `TRUCK_N` is *predominantly* haul trucks,
but that is an inference, not a measurement.

**Measured values:** mean speed per segment-hour has a median of **17.2 km/h**
(p5 7.6, p95 26.5). `TRUCK_N` has a median of 10 and a max of 69.
`SUM_TRAV_MS`/`TRAV_N` give measured traverse time per segment.

Segments are 1 km, named by road: `BLB KM2-3` … `BLB KM19-20`, `CBB KM7-8` …
`CBB KM16-17`, `CBBB KM15-16`, `CBBB KM16-17`, `CRD KM0-1` … `CRD KM6-7`, plus
`KR` and `TF` ranges — 95 in total, matching the road vocabulary in
`ALL_HR_KM_SECTIONS`.

**This is the segment-level speed the simulator was told it could not have.**

### Large tables the earlier keyword scan missed

Dropping the keyword filter surfaced four high-volume WBN_DATABASE tables that
had never been examined, and one of them bears directly on a published blocker.

| Table | Rows | Date range | Why it matters |
|---|---|---|---|
| `EQUIPMENTS_HOURLY_STATUS` | 16,558,379 | → 2026-07-29 | Hourly equipment state: working / standby / breakdown / PM hours with reason codes and location. Direct measurement of availability, currently an *assumed* 85% input to the simulator. |
| `EQUIPMENTS_HOURLY_ACTIVITIES` | 4,682,656 | → 2026-07-29 | **`TRUCK_ID` + `EXCAVATOR_ID` + `DISTANCE` + `RIT` on the same row**, hourly, with origin/destination and material. |
| `EQUIPMENTS_STATUS` | 3,680,170 | 2024-10-01 → 2026-07-29 | Shift-level equipment status with hour meters and `USAGE_KM_METER`. |
| `DAY_WORKS` | 495,592 | 2024-10-15 → 2026-07-25 | Per-activity records with `OPERATOR_ID`, `UNIT_TYPE`, `ROAD_NAME`, `ROAD_STA_KM`/`ROAD_END_KM`, `LOADING_POINT`, `LOADING_RIT`, `DISTANCE_KM`. |

**On loader assignment.** `EQUIPMENTS_HOURLY_ACTIVITIES` pairs 1,382 trucks with
436 excavators across 4.68M hourly rows — vastly more than the 408 rows in
`FMS_TRUCK_ASSIGNMENTS`. But its truck vocabulary is `ADT153`, `ADT168`,
`ADT167/165`, not the weighbridge's `A342`/`R707`. **This is where the real
namespace split lives**, and it is worse than a format difference: some values
are compound (`ADT167/165`, `ADT143/168`), meaning one row can cover two trucks.

So the position is nuanced rather than simply "blocked":

- `FMS_TRUCK_ASSIGNMENTS` gives excavator identity in **weighbridge format**,
  joinable today, but only 408 rows from 2026-01 onward.
- `EQUIPMENTS_HOURLY_ACTIVITIES` gives excavator identity at **scale over two
  years**, but needs an `ADT###` → `A###` mapping that has not been found in
  either database and may not exist.

`DAY_WORKS.OPERATOR_ID` holds operator **names** (18,559 distinct) rather than
the numeric employee IDs in `RES_EMPLOYEES`, so joining operator identity to
production would need name matching — workable but lossy, and worth flagging
before anyone assumes operator effects are cheap to measure.

`EQUIPMENTS_HOURLY_STATUS` is the most immediately useful of the four. The plan
simulator currently takes availability as a caller-supplied assumption
(default 85%); this table measures working, standby, breakdown and PM hours
per equipment per hour, so that assumption can be replaced with a measured
figure per contractor and fleet.

### Summary: what data exists for the simulator

| Feature needed | Available? | Table | Notes |
|---|---|---|---|
| Segment-level speed | **Yes, 2 weeks only** | `FMS_CONGESTION_SEG` | 95 segments, directional, median 17.2 km/h. Does not overlap the trip extract. |
| Raw GPS for haul trucks | **Yes, days only** | `FMS_PLAYBACK_TRACK_24H`, `FMS_GPS_Historical` | 479 of 945 units at 3-second fixes. Rolling retention. |
| Queue time at loading | **Yes** | `WAITING_TIME`, `FMS_GEOFENCE_VISITS` | 9.0 min median at the shovel; 14.1 min median across the pit geofence. The ~5 min gap is queue and manoeuvring. |
| Queue time at dumping | **Yes** | `WAITING_TIME`, `FMS_GEOFENCE_VISITS` | `DUMPING_DIFFERENCE_TIME`; 1,202 dumping-geofence visits. |
| Loader assignment | **Yes, two sources** | `FMS_TRUCK_ASSIGNMENTS`, `EQUIPMENTS_HOURLY_ACTIVITIES` | 408 rows joinable today in weighbridge format; 4.68M rows over two years in `ADT###` format needing an unfound mapping. |
| HRM fleet impact | **Yes** | `HRM_INSPECTION`, `FMS_HRM_SUPERVISION` | 30,610 road-condition records by KM/severity since 2024-10. |
| KM section definitions | **Yes** | `ALL_HR_KM_SECTIONS`, `HAUL_ROAD_STA`, `DISPATCH ROADS` | 27 named sections, 25 m chainage, and per-route section fractions. |
| GPS for haul trucks | **Yes** | `FMS_EQUIPMENTS` bridges the namespaces | 945 of 1,411 plates match the weighbridge. The earlier "0 of 940" was wrong. |
| Real haul distances | **Yes** | `DISTANCE_HAULING`, `EQUIPMENTS_HOURLY_ACTIVITIES.DISTANCE`, `DAY_WORKS.DISTANCE_KM` | Three sources. Replaces the placeholder `distance_km` (57 of 65 routes default to 25.0 km). |
| Truck availability | **Yes** | `EQUIPMENTS_HOURLY_STATUS` | 16.5M rows of working/standby/breakdown/PM hours. Replaces the assumed 85% availability input. |
| Operator identity | **Partial** | `WAITING_TIME.DRIVER_ID`, `DAY_WORKS.OPERATOR_ID`, `RES_EMPLOYEES` | `WAITING_TIME` carries a numeric driver ID per haul (joinable); `DAY_WORKS` carries 18,559 operator *names*, which would need fuzzy matching to `RES_EMPLOYEES`. |

### What this changes, in priority order

1. **The GPS claim is corrected.** Haul trucks are instrumented at 3-second
   resolution. The limit is retention, not instrumentation.
2. **Re-test congestion on `FMS_CONGESTION_SEG`.** It has measured speed *and*
   `TRUCK_N` per segment-hour. The weighbridge test failed because deployment is
   endogenous; a segment-hour test does not share that weakness in the same way.
   This could overturn the second published negative.
3. **Validate dwell against `FMS_GEOFENCE_VISITS`** — 15,100 measured pit visits
   overlapping the training period.
4. **Replace `distance_km`** with `DISTANCE_HAULING`.
5. **Add road condition** from `HRM_INSPECTION` as a cycle-time feature.
6. **Loader assignment is not blocked** — `FMS_TRUCK_ASSIGNMENTS` uses
   weighbridge truck format, contradicting the earlier namespace-split finding.

Items 2 and 3 are the ones that could most change the product.
