# Fuel / Equipment-Hours / Haulage Data Reconnaissance

SQL Server `10.211.10.1` — databases `WBN_DATABASE` and `FMS_DB`.
All 10 requested steps run against both databases. Raw results below.

## 0. Headline finding

There is **no fuel/diesel accounting subsystem** in either database.
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
hours, haulage distance, fleet, contractor — is present and large.

**The model is viable. Measured against the live database (section 10):**

| Check | Result |
|---|---|
| Fuel units joining to operating hours | **735 of 736 (99.9%)** |
| Fuel unit-days joining to hours | **30,917 of 31,035 (99.6%)** |
| Mean burn rate | **10.49 L per operating hour** (range 0–168.8) |
| Fuel unit-days with weighbridge tonnes | 24,478 (78.9%) |
| Fuel units reachable for GPS km | 643 (87.4%) |
| `DAY_WORKS` hour meters since 2026-02 | **63,913 populated** |

**Forecast at fleet-day grain from the active-unit count.** Two honest
accuracy figures, depending on what you can supply (section 13):

| Situation | MAPE | Error |
|---|---|---|
| Plan supplies tomorrow's active-unit count | **~3.5%** | ±1,800 L/day |
| Fully autonomous, history only | **~13%** | ±7,100 L/day |
| No model (predict the mean) | 19.3% | — |

`litres_per_day = -3928 + 270.4 × active_units`. **The bottleneck is not the
fuel model — it is knowing how many units will run.** Forecasting the unit
count costs +9.5 pp and dominates all remaining error. Join
`WAITING_TIME.EQUIPMENT_ID = EQUIPMENTS_HOURLY_STATUS.ID_EQ` on the same date,
then aggregate. **251.9 L per active unit-day**, a 5× improvement on the
no-model baseline of 16.5%.

**Do not build a per-unit-day burn-rate model — it is worse than predicting the
mean** (40.3% vs 35.9% MAPE). A refuel is a ~200 L tank fill, not a day's
consumption: `corr(fills, litres) = +0.840` against `corr(work_hrs, litres) =
+0.166`. And **`OPERATING_HOURS` is calendar hours, not engine hours** —
always 24.0 per unit-day, correlation +0.010 with litres. Use
`WORKING_HOURS`. Both traps are documented in section 11.1.

**A correction, recorded honestly.** Section 9 below originally predicted this
join would fail. That prediction was inferred from 20-row samples, in which
`EQUIPMENTS_HOURLY_STATUS.ID_EQ` happened to show only asset-format IDs
(`ATCT0450027`). The live table holds **3,701 distinct units spanning several
namespaces**, including the `A999` fleet format the fuel data uses. The
sampling was too small, and section 9 is kept below only as a record of that
reasoning and of the genuine multi-namespace hazard, which still applies to the
GPS tables. **Section 10 supersedes it.**


## 1. Fuel/Diesel tables found


### WBN_DATABASE — columns matching fuel words (wide net)

| schema | object | column | type | len | nullable |
|---|---|---|---|---|---|
| dbo | WAITING_TIME | FUEL_FILLING_TIME | time | 5 | True |  |
| dbo | WAITING_TIME | FUEL_FILLING_TIME 2 | time | 5 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL | nvarchar | 100 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL 2 | nvarchar | 100 | True |  |
| dbo | WAITING_TIME_DIFFERENCE | FUEL_FILLING_TIME | time | 5 | True |
| dbo | WAITING_TIME_FIX | FUEL_FILLING_TIME | time | 5 | True |


**Modules (views/procs/functions) mentioning fuel in WBN_DATABASE:**

| schema_name | object_name | type_desc |
|---|---|---|
| dbo | getEQUIPMENT_TYPE_CLEAN | SQL_INLINE_TABLE_VALUED_FUNCTION |
| dbo | EQUIPMENT_NEW_ID | VIEW |
| dbo | WAITING_TIME_DIFFERENCE | VIEW |
| dbo | WAITING_TIME_FIX | VIEW |


### FMS_DB — columns matching fuel words (wide net)

| schema | object | column | type | len | nullable |
|---|---|---|---|---|---|
| dbo | RES_WATER_FILLING_POINTS | Dispenser_Count | int | 4 | True |  |
| dbo | IDLE_EVENTS_WT | Dispenser_Count | int | 4 | True |
| dbo | WATER_POINTS_GEOFENCE | Dispenser_Count | int | 4 | True |


**Modules (views/procs/functions) mentioning fuel in FMS_DB:**

_(no rows)_


### WAITING_TIME — fuel data quality

**Monthly coverage** (`fuel_rows` = non-null `TOTAL_FUEL`):

| y | m | rows_all | fuel_rows | equips |
|---|---|---|---|---|
|  |  | 24329 | 0 | 0 |
| 2025 | 1 | 290 | 0 | 81 |
| 2025 | 10 | 75970 | 0 | 1076 |
| 2025 | 11 | 113023 | 0 | 1098 |
| 2025 | 12 | 100553 | 0 | 1069 |
| 2026 | 1 | 88701 | 0 | 1015 |
| 2026 | 2 | 69692 | 1695 | 811 |
| 2026 | 3 | 101269 | 8350 | 1032 |
| 2026 | 4 | 97161 | 9186 | 1020 |
| 2026 | 5 | 87902 | 6084 | 999 |
| 2026 | 6 | 73124 | 8790 | 926 |
| 2026 | 7 | 46226 | 5905 | 926 |


**Parsed totals:**

| n | equips | total_litres | avg_litres | mn | mx |
|---|---|---|---|---|---|
| 39366 | 736 | 7834145.173611111 | 199.16474319590978 | 2026-02-22 | 2026-07-22 |


**Top 15 equipment by fill count:**

| EQUIPMENT_ID | fills | litres |
|---|---|---|
| N425 | 207 | 39050.0 |
| N203 | 161 | 31907.0 |
| N465 | 160 | 28990.0 |
| L046 | 153 | 29620.0 |
| N417 | 150 | 27030.0 |
| N398 | 147 | 27965.0 |
| N326 | 142 | 26170.0 |
| N798 | 141 | 25170.0 |
| N458 | 139 | 24220.0 |
| N396 | 139 | 24750.0 |
| N410 | 137 | 24660.0 |
| N339 | 137 | 23945.0 |
| N466 | 136 | 23020.0 |
| N295 | 136 | 26265.0 |
| N799 | 135 | 26310.0 |


**Distinct `TOTAL_FUEL` raw values (top 30, shows the text problem):**

| TOTAL_FUEL | n |
|---|---|
| 200 | 4112 |
| 180 | 3596 |
| 190 | 3206 |
| 170 | 2767 |
| 210 | 2235 |
| 160 | 1881 |
| 220 | 1614 |
| 150 | 1339 |
| 230 | 1232 |
| 250 | 1009 |
| 240 | 998 |
| 140 | 654 |
|  | 644 |
| 260 | 603 |
| 270 | 523 |
| 200 L | 511 |
| 180L | 508 |
| 280 | 425 |
| 200L | 424 |
| 170L | 421 |
| 190L | 406 |
| 130 | 397 |
| 160L | 364 |
| 220 L | 331 |
| 300 | 325 |
| 120 | 320 |
| 210 L | 315 |
| 190 L | 283 |
| 290 | 282 |
| 150L | 275 |


## 2. Equipment hours tables


### `WBN_DATABASE.dbo.EQUIPMENTS_HOURLY_STATUS` — 16,657,468 rows, 20 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| CONTRACTOR | nvarchar | 100 | True |
| DATE | datetime | 8 | True |
| SHIFT | float | 8 | True |
| START_HOUR | float | 8 | True |
| END_HOUR | float | 8 | True |
| ID_EQ | nvarchar | 100 | True |
| ACTIVITY | nvarchar | 100 | True |
| LOCATION | nvarchar | 100 | True |
| WORKING_HOURS | float | 8 | True |
| STBY_HOURS | float | 8 | True |
| STBY_CODE | nvarchar | 100 | True |
| BD_HOURS | float | 8 | True |
| BD_CODE | nvarchar | 100 | True |
| PM_HOURS | float | 8 | True |
| PM_CODE | nvarchar | 100 | True |
| OPERATING_HOURS | float | 8 | True |
| REMARK | nvarchar | 100 | True |
| STATUS | nvarchar | 100 | True |
| LOCATION_DETAILS | nvarchar | 100 | True |


**Sample (20 rows):**

| ID | CONTRACTOR | DATE | SHIFT | START_HOUR | END_HOUR | ID_EQ | ACTIVITY | LOCATION | WORKING_HOURS | STBY_HOURS | STBY_CODE | BD_HOURS | BD_CODE | PM_HOURS | PM_CODE | OPERATING_HOURS | REMARK | STATUS | LOCATION_DETAILS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | HJS | 2024-10-01 00:00:00 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.0 | 0.17 | S6 | 0.0 |  | 0.0 |  | 0.1666666666666662 | 0.291666666666667 | RFU | CBB1 |
| 2 | HJS | 2024-10-01 00:00:00 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.58 | 0.0 |  | 0.0 |  | 0.0 |  | 0.5833333333333345 | 0.298611111111111 | RFU | CBB1 |
| 3 | HJS | 2024-10-01 00:00:00 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.25 | 0.0 |  | 0.0 |  | 0.0 |  | 0.24999999999999933 | 0.322916666666667 | RFU | CBB1 |
| 4 | HJS | 2024-10-01 00:00:00 | 1.0 | 8.0 | 9.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0000000000000013 | 0.333333333333333 | RFU | CBB1 |
| 5 | HJS | 2024-10-01 00:00:00 | 1.0 | 9.0 | 10.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0000000000000013 | 0.375 | RFU | CBB1 |
| 6 | HJS | 2024-10-01 00:00:00 | 1.0 | 10.0 | 11.0 | ATCT0450027 | MINING | CBB | 0.75 | 0.0 |  | 0.0 |  | 0.0 |  | 0.7500000000000007 | 0.416666666666667 | RFU | CBB1 |
| 7 | HJS | 2024-10-01 00:00:00 | 1.0 | 10.0 | 11.0 | ATCT0450027 | MINING | CBB | 0.0 | 0.25 | S15 | 0.0 |  | 0.0 |  | 0.24999999999999933 | 0.447916666666667 | RFU | CBB1 |
| 8 | HJS | 2024-10-01 00:00:00 | 1.0 | 11.0 | 12.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0000000000000013 | 0.458333333333333 | RFU | CBB1 |
| 9 | HJS | 2024-10-01 00:00:00 | 1.0 | 12.0 | 13.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0 | 0.5 | RFU | CBB1 |
| 10 | HJS | 2024-10-01 00:00:00 | 1.0 | 13.0 | 14.0 | ATCT0450027 | PIT PREPARATION | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0000000000000027 | 0.541666666666667 | RFU | CBB1 |
| 11 | HJS | 2024-10-01 00:00:00 | 1.0 | 14.0 | 15.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0 | 0.583333333333333 | RFU | CBB1 |
| 12 | HJS | 2024-10-01 00:00:00 | 1.0 | 15.0 | 16.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0 | 0.625 | RFU | CBB1 |
| 13 | HJS | 2024-10-01 00:00:00 | 1.0 | 16.0 | 17.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0000000000000027 | 0.666666666666667 | RFU | CBB1 |
| 14 | HJS | 2024-10-01 00:00:00 | 1.0 | 17.0 | 18.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  | 0.0 |  | 1.0 | 0.708333333333333 | RFU | CBB1 |
| 15 | HJS | 2024-10-01 00:00:00 | 1.0 | 18.0 | 19.0 | ATCT0450027 | MINING | CBB | 0.5 | 0.0 |  | 0.0 |  | 0.0 |  | 0.5000000000000013 | 0.75 | RFU | CBB1 |
| 16 | HJS | 2024-10-01 00:00:00 | 1.0 | 18.0 | 19.0 | ATCT0450027 | MINING | CBB | 0.0 | 0.25 | S17 | 0.0 |  | 0.0 |  | 0.24999999999999933 | 0.770833333333333 | RFU | CBB1 |
| 17 | HJS | 2024-10-01 00:00:00 | 1.0 | 18.0 | 19.0 | ATCT0450027 | MINING | CBB | 0.0 | 0.25 | S6 | 0.0 |  | 0.0 |  | 0.24999999999999933 | 0.78125 | RFU | CBB1 |
| 18 | HJS | 2024-10-01 00:00:00 | 1.0 | 7.0 | 8.0 | ATCT0450028 | MINING | CBB | 0.0 | 0.0 |  | 1.0 | EN | 0.0 |  | 1.0 | 0.291666666666667 | BREAKDOWN | WORKSHOP |
| 19 | HJS | 2024-10-01 00:00:00 | 1.0 | 8.0 | 9.0 | ATCT0450028 | MINING | CBB | 0.0 | 0.0 |  | 1.0 | EN | 0.0 |  | 1.0000000000000013 | 0.333333333333333 | BREAKDOWN | WORKSHOP |
| 20 | HJS | 2024-10-01 00:00:00 | 1.0 | 9.0 | 10.0 | ATCT0450028 | MINING | CBB | 0.0 | 0.0 |  | 1.0 | EN | 0.0 |  | 1.0000000000000013 | 0.375 | BREAKDOWN | WORKSHOP |


### `WBN_DATABASE.dbo.EQUIPMENTS_HOURLY_ACTIVITIES` — 4,699,720 rows, 21 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| CONTRACTOR | nvarchar | 100 | False |
| DATE | date | 3 | False |
| SHIFT | int | 4 | True |
| START_HOUR | int | 4 | True |
| END_HOUR | int | 4 | True |
| ACTIVITY | nvarchar | 510 | False |
| MATERIAL | nvarchar | 510 | True |
| MATERIAL_CLASS | nvarchar | 510 | True |
| ORIGIN_AREA | nvarchar | 510 | True |
| ORIGIN_ID | nvarchar | 510 | True |
| SUB_PIT | nvarchar | 510 | True |
| PROD_ID | nvarchar | 510 | True |
| DESTINATION_AREA | nvarchar | 510 | True |
| DESTINATION_ID | nvarchar | 510 | True |
| DISTANCE | float | 8 | True |
| TRUCK_ID | nvarchar | 510 | True |
| TRUCK_FACTOR | float | 8 | True |
| EXCAVATOR_ID | nvarchar | 510 | True |
| RIT | float | 8 | True |
| REMARK | nvarchar | 510 | True |


**Sample (20 rows):**

| ID | CONTRACTOR | DATE | SHIFT | START_HOUR | END_HOUR | ACTIVITY | MATERIAL | MATERIAL_CLASS | ORIGIN_AREA | ORIGIN_ID | SUB_PIT | PROD_ID | DESTINATION_AREA | DESTINATION_ID | DISTANCE | TRUCK_ID | TRUCK_FACTOR | EXCAVATOR_ID | RIT | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6634 | RIM | 2024-11-26 | 1 | 8 | 9 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 1.0 |  |
| 6635 | RIM | 2024-11-26 | 1 | 9 | 10 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 3.0 |  |
| 6636 | RIM | 2024-11-26 | 1 | 10 | 11 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6637 | RIM | 2024-11-26 | 1 | 11 | 12 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 3.0 |  |
| 6638 | RIM | 2024-11-26 | 1 | 13 | 14 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6639 | RIM | 2024-11-26 | 1 | 14 | 15 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6640 | RIM | 2024-11-26 | 1 | 15 | 16 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6641 | RIM | 2024-11-26 | 1 | 16 | 17 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6642 | RIM | 2024-11-26 | 1 | 17 | 18 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT153 |  | E846 | 2.0 |  |
| 6643 | RIM | 2024-11-26 | 1 | 8 | 9 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 1.0 |  |
| 6644 | RIM | 2024-11-26 | 1 | 9 | 10 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6645 | RIM | 2024-11-26 | 1 | 10 | 11 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6646 | RIM | 2024-11-26 | 1 | 11 | 12 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 3.0 |  |
| 6647 | RIM | 2024-11-26 | 1 | 13 | 14 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6648 | RIM | 2024-11-26 | 1 | 14 | 15 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6649 | RIM | 2024-11-26 | 1 | 15 | 16 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6650 | RIM | 2024-11-26 | 1 | 16 | 17 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6651 | RIM | 2024-11-26 | 1 | 17 | 18 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT168 |  | E846 | 2.0 |  |
| 6652 | RIM | 2024-11-26 | 1 | 8 | 9 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT169 |  | E846 | 1.0 |  |
| 6653 | RIM | 2024-11-26 | 1 | 9 | 10 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD | RIM.E.02 |  | ADT169 |  | E846 | 2.0 |  |


### `WBN_DATABASE.dbo.EQUIPMENTS_STATUS` — 3,708,573 rows, 22 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| CONTRACTOR | nvarchar | 100 | True |
| DATE | date | 3 | True |
| SHIFT | int | 4 | True |
| ID_EQ | nvarchar | 100 | True |
| STATUS | nvarchar | 100 | True |
| ACTIVITY | nvarchar | 100 | True |
| LOCATION | nvarchar | 100 | True |
| LOCATION_DETAILS | nvarchar | 100 | True |
| HOUR_METER_START | float | 8 | True |
| HOUR_METER_END | float | 8 | True |
| USAGE_KM_METER | float | 8 | True |
| WORKING_HOURS | float | 8 | True |
| STBY_HOURS | float | 8 | True |
| STBY_CODE | nvarchar | 100 | True |
| BD_HOURS | float | 8 | True |
| BD_CODE | nvarchar | 100 | True |
| BD_START | date | 3 | True |
| BD_EST_RFU | date | 3 | True |
| BD_COMPARTMENT | nvarchar | 100 | True |
| BD_STATUS | nvarchar | 100 | True |
| REMARK | nvarchar | 100 | True |


**Sample (20 rows):**

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | STATUS | ACTIVITY | LOCATION | LOCATION_DETAILS | HOUR_METER_START | HOUR_METER_END | USAGE_KM_METER | WORKING_HOURS | STBY_HOURS | STBY_CODE | BD_HOURS | BD_CODE | BD_START | BD_EST_RFU | BD_COMPARTMENT | BD_STATUS | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 26533 | SMA | 2024-10-01 |  | EX407 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 16154.4 |  |  |  |  |  |  | 2023-08-26 | 2024-12-31 | UNDERCARRIAGE | WAITING FOR PART |  |
| 26534 | SMA | 2024-10-01 |  | EX408 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 19621.9 |  |  |  |  |  |  |  |  |  |  |  |
| 26535 | SMA | 2024-10-01 |  | EX409 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 19905.0 |  |  |  |  |  |  | 2024-06-22 | 2024-10-05 | HYDRAULIC SYSTEM | ON PROGRESS |  |
| 26536 | SMA | 2024-10-01 |  | EX410 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 17538.2 |  |  |  |  |  |  | 2024-07-15 | 2024-10-31 | UNDERCARRIAGE | WAITING FOR PART |  |
| 26537 | SMA | 2024-10-01 |  | EX411 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 18204.1 |  |  |  |  |  |  | 2024-09-10 | 2024-10-31 | HYDRAULIC SYSTEM | WAITING FOR PART |  |
| 26538 | SMA | 2024-10-01 |  | EX412 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 11474.3 |  |  |  |  |  |  |  |  |  |  |  |
| 26539 | SMA | 2024-10-01 |  | EX413 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 3113.4 |  |  |  |  |  |  | 2024-10-01 | 2024-10-02 | ENGINE | ON PROGRESS |  |
| 26540 | SMA | 2024-10-01 |  | EX414 | BREAKDOWN | 1ST LOADING | WORKSHOP | Workshop |  | 3801.3 |  |  |  |  |  |  | 2024-10-02 | 2024-10-02 | UNDERCARRIAGE | ON PROGRESS |  |
| 26541 | SMA | 2024-10-01 |  | EX415 | RFU | 1ST LOADING | TF | Pit TF |  | 2261.1 |  |  |  |  |  |  |  |  |  |  |  |
| 26542 | SMA | 2024-10-01 |  | EX416 | RFU | 2ND LOADING | TF | Pit TF |  | 1967.9 |  |  |  |  |  |  |  |  |  |  |  |
| 26543 | SMA | 2024-10-01 |  | EX417 | RFU | 2ND LOADING | TF | Pit TF |  | 1555.0 |  |  |  |  |  |  |  |  |  |  |  |
| 26544 | SMA | 2024-10-01 |  | EX418 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 2374.6 |  |  |  |  |  |  |  |  |  |  |  |
| 26545 | SMA | 2024-10-01 |  | EX501 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 19718.5 |  |  |  |  |  |  |  |  |  |  |  |
| 26546 | SMA | 2024-10-01 |  | EX503 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 17643.2 |  |  |  |  |  |  |  |  |  |  |  |
| 26547 | SMA | 2024-10-01 |  | EX504 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 17514.9 |  |  |  |  |  |  | 2024-02-29 | 2024-12-31 | DUMP BODY | ON PROGRESS |  |
| 26548 | SMA | 2024-10-01 |  | EX505 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 12340.400000000001 |  |  |  |  |  |  | 2023-02-10 | 2024-12-31 | HYDRAULIC SYSTEM | WAITING FOR PART |  |
| 26549 | SMA | 2024-10-01 |  | EX801 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 21938.9 |  |  |  |  |  |  | 2024-09-02 | 2024-10-05 | TRANSMISSION | ON PROGRESS |  |
| 26550 | SMA | 2024-10-01 |  | EX802 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 20994.0 |  |  |  |  |  |  |  |  |  |  |  |
| 26551 | SMA | 2024-10-01 |  | EX803 | RFU | 1ST LOADING | TF | Pit TF |  | 6367.8 |  |  |  |  |  |  |  |  |  |  |  |
| 26552 | SMA | 2024-10-01 |  | EX804 | RFU | 1ST LOADING | TF | Pit TF |  | 3500.4 |  |  |  |  |  |  |  |  |  |  |  |


### `WBN_DATABASE.dbo.EQUIPMENTS_WORKS` — 82 rows, 14 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| CONTRACTOR | nvarchar | 100 | True |
| DATE | date | 3 | True |
| SHIFT | int | 4 | True |
| ID_EQ | nvarchar | 100 | True |
| WORK_DONE | nvarchar | 510 | True |
| WORK_CONTEXT | nvarchar | 510 | True |
| ISSUE_DETAILS | nvarchar | 510 | True |
| ISSUE_DATE_START | date | 3 | True |
| HOUR_METER | float | 8 | True |
| COMPARTMENT | nvarchar | 100 | True |
| PART_CHANGED | nvarchar | 100 | True |
| PART_REPAIRED | nvarchar | 100 | True |
| REMARK | nvarchar | 510 | True |


**Sample (20 rows):**

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | WORK_DONE | WORK_CONTEXT | ISSUE_DETAILS | ISSUE_DATE_START | HOUR_METER | COMPARTMENT | PART_CHANGED | PART_REPAIRED | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMA | 2024-09-25 |  | MG09 | BOLT TYRE POS 2 BROKEN | BREAKDOWN |  | 2024-08-18 | 2501.0 | TYRE | TYRE | TYRE |  |
| 2 | SMA | 2024-09-06 |  | DZ16 | RECOIL SPRING LH BROKEN | BREAKDOWN |  | 2024-09-05 | 2879.8 | UNDERCARRIAGE | UNDERCARRIAGE | UNDERCARRIAGE |  |
| 3 | SMA |  |  | DT16 | VESSEL DUMP PROBLEM | BREAKDOWN | *CHECK CONDITION UNIT *REPLACE VESSEL *TYRE SWAP T | 2024-04-16 | 18225.0 | DUMP BODY | DUMP BODY | DUMP BODY |  |
| 4 | SMA | 2024-09-20 |  | DZ23 | OIL LEAK AREA FINAL DRIVE | BREAKDOWN |  | 2024-08-07 | 9378.2 | FINAL DRIVE | FINAL DRIVE | FINAL DRIVE |  |
| 5 | SMA | 2024-09-06 |  | DT41 | KING PIN PROBLEM & PM 1000 HRS SERVICE | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *CARRY OUT PM SERVICE 1000 H | 2024-09-05 | 17405.0 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 6 | SMA |  |  | DT45 | DUMP BODY | BREAKDOWN |  | 2024-02-05 | 16988.29 | DUMP BODY | DUMP BODY | DUMP BODY |  |
| 7 | SMA | 2024-09-06 |  | DT51 | PROPERTY DAMAGE  *GUARD ENGINE BROKEN *OIL PEN LEA | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *FABRICATION GUARD ENGINE *R | 2024-08-10 | 17472.480000000003 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 8 | SMA |  |  | DT54 | PROPERTY DAMAGE *OIL PAN BROKEN *ENGINE JAMMED | BREAKDOWN | *CHECK CONDITION UNIT *WAITING BA & INVESTIGATION  | 2024-06-07 | 15655.46 | DUMP BODY | DUMP BODY | DUMP BODY |  |
| 9 | SMA | 2024-09-07 |  | DT55 | GENERAL INSPECTION (UNIT TASK FORCE) | PREVENTIVE MAINTENANCE | *GENERAL INSPECTION *FINAL CHECK | 2024-08-29 | 16992.12 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 10 | SMA | 2024-09-07 |  | DT56 | MIDDLE DIFFERENTIAL BROKEN  | BREAKDOWN | *CHECK CONDITION UNIT *REPLACE MIDDLE DIFFERENTIAL | 2024-07-29 | 2549.0 | ENGINE | ENGINE | ENGINE |  |
| 11 | SMA | 2024-09-06 |  | DT58 | *COOLANT LEAK *INJECTOR MALFUNCTION | BREAKDOWN | *CHECK CONDITION UNIT *REPLACE INJECTOR NO 1,3,4 * | 2024-07-07 | 18325.02 | ENGINE | ENGINE | ENGINE |  |
| 12 | SMA | 2024-09-06 |  | DT60 | FRONT LEAF SPRING POS 3 NO 1 BROKEN | BREAKDOWN | *CHECK CONDITION UNIT *REQUEST MOVING TO W/S KR *R | 2024-08-22 | 15586.0 | SUSPENSION | SUSPENSION | SUSPENSION |  |
| 13 | SMA | 2024-09-06 |  | DT62 | *SPRING POS 3 NO. 1 BROKEN | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *REQUEST MOVING TO WORKSHOP  | 2024-09-02 | 15974.0 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 14 | SMA | 2024-09-10 |  | DT64 | PROPERTY DAMAGE *ENGINE GUARD BROKEN | BREAKDOWN | *CHECK CONDITION UNIT *REQUEST TRANSFER LOAD *REQU | 2024-08-24 | 8366.0 | DUMP BODY | DUMP BODY | DUMP BODY |  |
| 15 | SMA |  |  | DT66 | *HIGH TEMPERATURE *ENGINE JAMMED | BREAKDOWN | *CHECK CONDITION UNIT *REPLACE COMPRESSOR (DONE) * | 2024-05-24 | 16383.16 | ENGINE | ENGINE | ENGINE |  |
| 16 | SMA | 2024-09-07 |  | DT67 | *FRONT LEAF SPRING POS 3 BROKEN *KING PIN POS 3 BR | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *PREPARE INSPECTION UNIT | 2024-08-17 | 18639.05 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 17 | SMA | 2024-09-06 |  | DT71 | *FRONT LEAF SPRING POS 3 NO 3 BROKEN *BRAKE FAILUR | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *REPLACE SPRING (DONE)  *REP | 2024-08-06 | 17320.9 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |
| 18 | SMA |  |  | DT72 | *ENGINE LOW POWER (TURBO BROKEN) *ENGINE JAMMED | BREAKDOWN | *CHECK CONDITION UNIT *TOWING TO W/S UNI-UNI (DONE | 2024-04-25 | 11840.04 | ENGINE | ENGINE | ENGINE |  |
| 19 | SMA | 2024-09-06 |  | DT77 | *UNIT CAN'T RUNNING *MIDDLE DIFFERENTIAL BROKEN | BREAKDOWN | *CHECK CONDITION UNIT *REQUEST MOVING TO W/S KR *R | 2024-08-15 | 13149.0 | ENGINE | ENGINE | ENGINE |  |
| 20 | SMA |  |  | DT78 | DUMP BODY | BREAKDOWN |  | 2024-03-06 | 12016.3 | DUMP BODY | DUMP BODY | DUMP BODY |  |


### `WBN_DATABASE.dbo.DAY_WORKS` — 496,409 rows, 27 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| UUID | nvarchar | 510 | True |
| DATE | date | 3 | True |
| SHIFT | int | 4 | True |
| CONTRACTOR | nvarchar | 100 | True |
| ACTIVITY_CAT | nvarchar | 100 | True |
| ACTIVITY_DESC | nvarchar | 510 | True |
| ACTIVITY_PLANNED | nvarchar | 100 | True |
| ACTIVITY_TIME_START | time | 3 | True |
| ACTIVITY_TIME_END | time | 3 | True |
| OPERATOR_ID | nvarchar | 100 | True |
| UNIT_TYPE | nvarchar | 100 | True |
| UNIT_CLASS | nvarchar | 100 | True |
| UNIT_ID | nvarchar | 100 | True |
| UNIT_START_HOUR_METER | float | 8 | True |
| UNIT_END_HOUR_METER | float | 8 | True |
| LOCATION | nvarchar | 510 | True |
| ROAD_NAME | nvarchar | 100 | True |
| ROAD_STA_KM | float | 8 | True |
| ROAD_END_KM | float | 8 | True |
| ROAD_LANE | nvarchar | 100 | True |
| LOADING_POINT | nvarchar | 100 | True |
| LOADING_RIT | float | 8 | True |
| DISTANCE_KM | float | 8 | True |
| REMARK | nvarchar | 510 | True |
| UPDATE_DATE | datetime | 8 | True |
| UPDATE_BY | nvarchar | 100 | True |


**Sample (20 rows):**

| ID | UUID | DATE | SHIFT | CONTRACTOR | ACTIVITY_CAT | ACTIVITY_DESC | ACTIVITY_PLANNED | ACTIVITY_TIME_START | ACTIVITY_TIME_END | OPERATOR_ID | UNIT_TYPE | UNIT_CLASS | UNIT_ID | UNIT_START_HOUR_METER | UNIT_END_HOUR_METER | LOCATION | ROAD_NAME | ROAD_STA_KM | ROAD_END_KM | ROAD_LANE | LOADING_POINT | LOADING_RIT | DISTANCE_KM | REMARK | UPDATE_DATE | UPDATE_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 59482 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Matius Irfan | Compactor | 110 NE | VRVV11011 |  |  | HAULROAD | CBBB | 15.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59483 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Obsta… | PLANNED | 07:00:00 | 18:00:00 | Budi Sulistiyo | Motor Grader | 535 | MGKM53007 |  |  | HAULROAD | CBBB | 15.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59484 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | Spare/To Be Named | Water Truck | 20 Ton | WTHN0200018 |  |  | HAULROAD | CBBB | 15.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59485 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Muhammad Indra Sangadji | Compactor | 110 NE | VRBM0100002 |  |  | HAULROAD | BLB | 6.0 | 10.0 | Empty & Loaded |  |  |  |  |  |  |
| 59486 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Obsta… | PLANNED | 07:00:00 | 18:00:00 | Murdiyanto | Motor Grader | 150 | MGKM0150010 |  |  | HAULROAD | BLB | 6.0 | 10.0 | Empty & Loaded |  |  |  |  |  |  |
| 59487 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | La Ode Muju Taro | Water Truck | 20 Ton | WTHN28009 |  |  | HAULROAD | BLB | 6.0 | 10.0 | Empty & Loaded |  |  |  |  |  |  |
| 59488 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Billy Meyfandi Nangin | Compactor | 110 NE | VRVV11010 |  |  | HAULROAD | BLB | 2.0 | 6.0 | Empty & Loaded |  |  |  |  |  |  |
| 59489 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Obsta… | PLANNED | 07:00:00 | 18:00:00 | Johan Fery Napitupulu | Motor Grader | 535 | MGCT16003 |  |  | HAULROAD | BLB | 2.0 | 6.0 | Empty & Loaded |  |  |  |  |  |  |
| 59490 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | Irwanto Kandolla | Water Truck | 20 Ton | WTHN26002 |  |  | HAULROAD | BLB | 2.0 | 6.0 | Empty & Loaded |  |  |  |  |  |  |
| 59491 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Hauling Quarry | PLANNED | 07:00:00 | 18:00:00 | Mudfar D R Malan | Hauler | 20 Ton | DTIZ0200330 |  |  | HAULROAD | BLB | 2.0 | 17.0 | Empty & Loaded | CAS |  |  |  |  |  |
| 59492 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Hauling Quarry | PLANNED | 07:00:00 | 18:00:00 | Hendra Yanto Seleky | Hauler | 20 Ton | DTIZ0200380 |  |  | HAULROAD | BLB | 2.0 | 17.0 | Empty & Loaded | CAS |  |  |  |  |  |
| 59493 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Hauling Quarry | PLANNED | 07:00:00 | 18:00:00 | Faisal Panigoro | Hauler | 20 Ton | DTIZ34121 |  |  | HAULROAD | BLB | 2.0 | 10.0 | Empty & Loaded | Loy Poloy |  |  |  |  |  |
| 59494 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Hauling Quarry | PLANNED | 07:00:00 | 18:00:00 | Chandra Tolinggi | Hauler | 20 Ton | DTIZ34216 |  |  | HAULROAD | BLB | 2.0 | 10.0 | Empty & Loaded | Loy Poloy |  |  |  |  |  |
| 59495 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Patching - Loading - Spreading - Moulding | PLANNED | 07:00:00 | 18:00:00 | Muh. Isram Tamrin | Exca | 20 Ton | EXVV0200032 |  |  | HAULROAD | BLB | 2.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59496 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | Ali Tuahuns | Water Truck | 20 Ton | WTHN26005 |  |  | HAULROAD | BLB | 2.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59497 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Obsta… | PLANNED | 07:00:00 | 18:00:00 | Spare/To Be Named | Motor Grader | 535 | MGLG42003 |  |  | HAULROAD | CBBB | 15.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59498 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Grading - Cleaning Obsta… | PLANNED | 07:00:00 | 18:00:00 | Spare/To Be Named | Motor Grader | 535 | MGLG42007 |  |  | HAULROAD | BLB | 2.0 | 10.0 | Empty & Loaded |  |  |  |  |  |  |
| 59499 |  | 2024-10-15 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Rilan Paputungan | Compactor | 110 NE | VRBM0100001 |  |  | HAULROAD | CBBB | 15.0 | 17.0 | Empty & Loaded |  |  |  |  |  |  |
| 59728 |  | 2024-10-15 | 1 | SMA | ROAD MAINTENANCE | Road Grading | PLANNED | 06:00:00 | 18:00:00 |  | GRADER | CAT 160K | MG10 | 1934.0 | 1942.0 | HAULROAD | TF | 58.0 | 59.0 | LOAD AND EMPTY |  |  |  |  |  |  |
| 59729 |  | 2024-10-15 | 1 | SMA | ROAD MAINTENANCE | Compacting | PLANNED | 06:00:00 | 18:00:00 |  | COMPACTOR | Bomag 20t | CO07 | 1850.0 | 1858.0 | HAULROAD | TF | 57.0 | 59.0 | LOAD AND EMPTY |  |  |  |  |  |  |


## 3. Haulage / weighbridge / distance tables


### `WBN_DATABASE.dbo.HAULAGE` — 3,510,278 rows, 24 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| DATE | date | 3 | False |
| SHIFT | int | 4 | True |
| CONTRACTOR | nvarchar | 100 | False |
| ACTIVITY | nvarchar | 100 | False |
| MATERIAL | nvarchar | 100 | False |
| TRUCK_ID | nvarchar | 100 | True |
| TIME_LOADED | time | 5 | True |
| TIME_EMPTY | time | 5 | True |
| RIT | int | 4 | True |
| ORIGIN_AREA | nvarchar | 100 | True |
| ORIGIN_ID | nvarchar | 100 | True |
| DESTINATION_AREA | nvarchar | 100 | True |
| DESTINATION_ID | nvarchar | 100 | True |
| KG_LOADED | float | 8 | True |
| KG_EMPTY | float | 8 | True |
| KG_NET | float | 8 | True |
| WMT | float | 8 | True |
| BCM | float | 8 | True |
| WB_ID | nvarchar | 100 | True |
| REMARK | nvarchar | 100 | True |
| TICKET_NO | nvarchar | 60 | True |
| UPDATE_DATE | datetime2 | 6 | True |
| UPDATE_BY | nvarchar | 100 | True |


**Sample (20 rows):**

| ID | DATE | SHIFT | CONTRACTOR | ACTIVITY | MATERIAL | TRUCK_ID | TIME_LOADED | TIME_EMPTY | RIT | ORIGIN_AREA | ORIGIN_ID | DESTINATION_AREA | DESTINATION_ID | KG_LOADED | KG_EMPTY | KG_NET | WMT | BCM | WB_ID | REMARK | TICKET_NO | UPDATE_DATE | UPDATE_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3127402 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5702 | 12:48:53 | 13:30:06 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 | 46340.0 | 19420.0 | 26920.0 | 26.92 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127403 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5725 | 12:49:21 | 13:27:54 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 62500.0 | 23100.0 | 39400.0 | 39.4 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127404 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5737 | 12:52:01 | 13:42:24 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 | 68420.0 | 23200.0 | 45220.0 | 45.22 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127405 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5525 | 12:54:51 | 13:53:01 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 | 58660.0 | 25080.0 | 33580.0 | 33.58 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127406 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5729 | 13:07:13 | 14:09:31 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 70980.0 | 23940.0 | 47040.0 | 47.04 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127407 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5171 | 13:08:21 | 14:01:14 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 44700.0 | 16880.0 | 27820.0 | 27.82 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127408 | 2025-01-20 | 2 | GMG | HAULAGE | SAP | DT-5737 | 02:05:19 | 03:01:09 | 1 | TOS_KR_PPP_02 | KR.I.1264 | POS 6 | AA.525 | 71840.0 | 23500.0 | 48340.0 | 48.34 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127409 | 2025-01-20 | 2 | GMG | HAULAGE | SAP | DT-5723 | 02:07:10 | 02:09:37 | 1 | TOS_KR_STM_08 | KR.I.1281 | POS 6 | AA.525 | 72360.0 | 23460.0 | 48900.0 | 48.9 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127410 | 2025-01-20 | 2 | GMG | HAULAGE | SAP | DT-5715 | 02:06:06 | 02:55:55 | 1 | TOS_KR_PPP_02 | KR.I.1264 | POS 6 | AA.525 | 51680.0 | 19260.0 | 32420.0 | 32.42 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127411 | 2025-01-20 | 2 | GMG | HAULAGE | SAP | DT-5126 | 02:10:34 | 02:09:54 | 1 | TOS_KR_PPP_02 | KR.I.1264 | POS 6 | AA.525 | 48400.0 | 16060.0 | 32340.0 | 32.34 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127412 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5172 | 13:08:43 | 14:01:35 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 49720.0 | 16840.0 | 32880.0 | 32.88 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127413 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5726 | 13:14:53 | 14:10:07 | 1 | TOS_KR_STM_08 | KR.I.1281 | POS 6 | AA.525 | 59620.0 | 22640.0 | 36980.0 | 36.98 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127414 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5102 | 13:16:33 | 14:06:10 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 37540.0 | 14380.0 | 23160.0 | 23.16 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127415 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5524 | 13:22:58 | 14:11:15 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 60000.0 | 23440.0 | 36560.0 | 36.56 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127416 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5135 | 13:23:24 | 14:11:38 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 48600.0 | 16980.0 | 31620.0 | 31.62 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127417 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5194 | 13:23:49 | 14:12:17 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 43360.0 | 16660.0 | 26700.0 | 26.7 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127418 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5727 | 13:27:18 | 14:13:24 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 68920.0 | 22120.0 | 46800.0 | 46.8 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127419 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5724 | 13:32:49 | 14:20:55 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 69440.0 | 23800.0 | 45640.0 | 45.64 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127420 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5738 | 13:36:59 | 14:27:58 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 62980.0 | 23460.0 | 39520.0 | 39.52 |  | WB_SMA_KM33 | SMA |  |  |  |
| 3127421 | 2025-01-20 | 1 | GMG | HAULAGE | SAP | DT-5507 | 13:37:51 | 14:29:14 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 | 67420.0 | 24000.0 | 43420.0 | 43.42 |  | WB_SMA_KM33 | SMA |  |  |  |


### `WBN_DATABASE.dbo.HAULAGE_IWIP` — 572,742 rows, 35 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| SERIAL_NO | nvarchar | 100 | True |
| WB_TIME | float | 8 | True |
| DATE | date | 3 | True |
| WB_ID | nvarchar | 100 | True |
| TICKET_NO | nvarchar | 100 | False |
| TRUCK_ID | nvarchar | 100 | True |
| CARGO_NAME | nvarchar | 100 | True |
| SELLER | nvarchar | 100 | True |
| BUYER | nvarchar | 100 | True |
| CONTRACTOR | nvarchar | 100 | True |
| ORIGIN_AREA | nvarchar | 100 | True |
| ORIGIN_AREA_CLEAN | nvarchar | 100 | True |
| ORIGIN_ID | nvarchar | 100 | True |
| ORIGIN_ID_CLEAN | nvarchar | 100 | True |
| DESTINATION_AREA | nvarchar | 100 | True |
| DESTINATION_AREA_CLEAN | nvarchar | 100 | True |
| DESTINATION_ID | nvarchar | 100 | True |
| DESTINATION_ID_CLEAN | nvarchar | 100 | True |
| WEIGHING_STATUS | float | 8 | True |
| BUSINESS_TYPE | nvarchar | 100 | True |
| ACTIVITY | nvarchar | 100 | True |
| GROSS_WEIGHT | float | 8 | True |
| TARE_WEIGHT | float | 8 | True |
| NET_WEIGHT | float | 8 | True |
| FIRST_WB_TIME | datetime | 8 | True |
| SECOND_WB_TIME | datetime | 8 | True |
| GROSS_WEIGHT_TIME | datetime | 8 | True |
| TARE_WEIGHT_TIME | datetime | 8 | True |
| GROSS_WEIGHT_POINT | nvarchar | 100 | True |
| TARE_WEIGHT_POINT | nvarchar | 100 | True |
| IS_COMPLETED | nvarchar | 100 | True |
| SHIFT | nvarchar | 100 | True |
| REMARKS | nvarchar | 100 | True |
| FETCH_DATE | datetime | 8 | True |
| IS_CLEAN | int | 4 | True |


**Sample (20 rows):**

| SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | SELLER | BUYER | CONTRACTOR | ORIGIN_AREA | ORIGIN_AREA_CLEAN | ORIGIN_ID | ORIGIN_ID_CLEAN | DESTINATION_AREA | DESTINATION_AREA_CLEAN | DESTINATION_ID | DESTINATION_ID_CLEAN | WEIGHING_STATUS | BUSINESS_TYPE | ACTIVITY | GROSS_WEIGHT | TARE_WEIGHT | NET_WEIGHT | FIRST_WB_TIME | SECOND_WB_TIME | GROSS_WEIGHT_TIME | TARE_WEIGHT_TIME | GROSS_WEIGHT_POINT | TARE_WEIGHT_POINT | IS_COMPLETED | SHIFT | REMARKS | FETCH_DATE | IS_CLEAN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | OTHER | 0.0 | 0.0 | 0.0 | 1900-01-01 00:00:00 | 1900-01-01 00:00:00 | 1900-01-01 00:00:00 | 1900-01-01 00:00:00 |  |  |  |  |  | 2026-07-23 13:10:02.283000 | 1 |
| 3943 | 20260102.0 | 2026-01-02 | 10 | 10A20260102123411 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  | R???55-58? | FENI R | SWSS.01 | SWSS.01 |  | RECLAIMING | CRUSHER RECLAIMING | 55460.0 | 21360.0 | 34100.0 | 2026-01-02 12:34:11 | 2026-01-02 13:01:48 | 2026-01-02 12:34:11 | 2026-01-02 13:01:48 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:30:55.033000 | 1 |
| 3741 | 20260102.0 | 2026-01-02 | 10 | 10A20260102132414 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  | R???55-58? | FENI R | SWSS.01 | SWSS.01 |  | RECLAIMING | CRUSHER RECLAIMING | 57880.0 | 21860.0 | 36020.0 | 2026-01-02 13:24:14 | 2026-01-02 14:18:33 | 2026-01-02 13:24:14 | 2026-01-02 14:18:33 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:30:55.033000 | 1 |
| 318 | 20260102.0 | 2026-01-02 | 10 | 10A20260102144822 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  | R???55-58? | FENI R | SWSS.01 | SWSS.01 |  | RECLAIMING | CRUSHER RECLAIMING | 47120.0 | 19340.0 | 27780.0 | 2026-01-02 14:48:22 | 2026-01-03 06:44:58 | 2026-01-02 14:48:22 | 2026-01-03 06:44:58 | 10A | 10A | ??? | ?? |  | 2026-07-07 17:30:55.033000 | 1 |
| 3327 | 20260104.0 | 2026-01-04 | 10 | 10A20260104102217 | N539 |  |  |  | INLE??C?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.433 | ADM.433 |  | RECLAIMING | SALES RECLAIMING | 68220.0 | 25860.0 | 42360.0 | 2026-01-04 10:22:15 | 2026-01-04 14:51:17 | 2026-01-04 10:22:15 | 2026-01-04 14:51:17 | 10A | 11D | ??? | ?? |  | 2026-07-07 17:31:15.420000 | 1 |
| 3432 | 20260107.0 | 2026-01-07 | 10 | 10A20260107072926 | R123 |  |  |  | ????E?? | POS12-SNMI????? | POS 12 |  |  | M???43-46? | FENI M | MN-M1_POS12_002 | M1_POS12_002 |  | RECLAIMING | SALES RECLAIMING | 76480.0 | 27420.0 | 49060.0 | 2026-01-07 07:29:14 | 2026-01-07 11:59:42 | 2026-01-07 07:29:14 | 2026-01-07 11:59:42 | 10A | 11D | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 3566 | 20260107.0 | 2026-01-07 | 10 | 10A20260107085415 | L088 |  |  |  | ????E?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.484 | ADM.484 |  | RECLAIMING | SALES RECLAIMING | 73960.0 | 25280.0 | 48680.0 | 2026-01-07 08:54:15 | 2026-01-07 11:21:44 | 2026-01-07 08:54:15 | 2026-01-07 11:21:44 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 3567 | 20260107.0 | 2026-01-07 | 10 | 10A20260107101328 | L088 |  |  |  | ????E?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.484 | ADM.484 |  | RECLAIMING | SALES RECLAIMING | 67660.0 | 25280.0 | 42380.0 | 2026-01-07 10:13:28 | 2026-01-07 11:21:44 | 2026-01-07 10:13:28 | 2026-01-07 11:21:44 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 2846 | 20260107.0 | 2026-01-07 | 10 | 10A20260107113856 | L088 |  |  |  | ????E?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.484 | ADM.484 |  | RECLAIMING | SALES RECLAIMING | 71140.0 | 25400.0 | 45740.0 | 2026-01-07 11:38:56 | 2026-01-07 15:07:51 | 2026-01-07 11:38:56 | 2026-01-07 15:07:51 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 2847 | 20260107.0 | 2026-01-07 | 10 | 10A20260107133946 | L088 |  |  |  | ????E?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.484 | ADM.484 |  | RECLAIMING | SALES RECLAIMING | 69680.0 | 25400.0 | 44280.0 | 2026-01-07 13:39:46 | 2026-01-07 15:07:51 | 2026-01-07 13:39:46 | 2026-01-07 15:07:51 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 1718 | 20260107.0 | 2026-01-07 | 10 | 10A20260107152329 | L088 |  |  |  | ????E?? | POS12 EXT-IFMI????? | POS 12 |  |  | L2???39-40? | FENI L2 | L2N-ADM.484 | ADM.484 |  | RECLAIMING | SALES RECLAIMING | 69660.0 | 24920.0 | 44740.0 | 2026-01-07 15:23:29 | 2026-01-07 22:28:19 | 2026-01-07 15:23:29 | 2026-01-07 22:28:19 | 10A | 11D | ??? | ?? |  | 2026-07-07 17:31:43.743000 | 1 |
| 2643 | 20260327.0 | 2026-03-27 | 10 | 10A20260327160731 | B011 |  |  |  | INLE??C?? | POS10-WBN????? | POS 10 |  |  | T???61-64? | FENI T | ACM.652 | ACM.652 |  | RECLAIMING | RECLAIMING | 58140.0 | 18800.0 | 39340.0 | 2026-03-27 16:07:31 | 2026-03-27 16:21:02 | 2026-03-27 16:07:31 | 2026-03-27 16:21:02 | 10A | 10A | ??? | ?? |  | 2026-07-07 17:43:19.910000 | 1 |
| 2454 | 20260328.0 | 2026-03-28 | 10 | 10A20260328202824 | K927 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 53900.0 | 24760.0 | 29140.0 | 2026-03-28 20:28:24 | 2026-03-28 20:49:37 | 2026-03-28 20:28:24 | 2026-03-28 20:49:37 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 2300 | 20260328.0 | 2026-03-28 | 10 | 10A20260328212423 | K955 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 51820.0 | 23800.0 | 28020.0 | 2026-03-28 21:24:23 | 2026-03-28 21:42:01 | 2026-03-28 21:24:23 | 2026-03-28 21:42:01 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 1851 | 20260328.0 | 2026-03-28 | 10 | 10A20260328231451 | K927 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 57160.0 | 24840.0 | 32320.0 | 2026-03-28 23:14:51 | 2026-03-28 23:32:19 | 2026-03-28 23:14:51 | 2026-03-28 23:32:19 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 1412 | 20260328.0 | 2026-03-28 | 10 | 10A20260329013603 | K955 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 54040.0 | 23820.0 | 30220.0 | 2026-03-29 01:36:03 | 2026-03-29 01:52:19 | 2026-03-29 01:36:03 | 2026-03-29 01:52:19 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 1318 | 20260328.0 | 2026-03-28 | 10 | 10A20260329015052 | K946 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 55480.0 | 24040.0 | 31440.0 | 2026-03-29 01:50:52 | 2026-03-29 02:15:09 | 2026-03-29 01:50:52 | 2026-03-29 02:15:09 | 10A | 10A | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 1243 | 20260328.0 | 2026-03-28 | 10 | 10A20260329020042 | K927 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 54900.0 | 24840.0 | 30060.0 | 2026-03-29 02:00:42 | 2026-03-29 02:41:36 | 2026-03-29 02:00:42 | 2026-03-29 02:41:36 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 777 | 20260328.0 | 2026-03-28 | 10 | 10A20260329043823 | K955 |  |  |  | ??????? | ??????-JYMI??? | ??????-JYMI??? |  |  | ??314????-BSE????? | ??314????-BSE????? | SSH-LY-004 | SSH-LY-004 |  | ????? | OTHER | 60400.0 | 23940.0 | 36460.0 | 2026-03-29 04:38:23 | 2026-03-29 04:54:47 | 2026-03-29 04:38:23 | 2026-03-29 04:54:47 | 10A | 10B | ??? | ?? |  | 2026-07-07 17:43:31.187000 | 1 |
| 2955 | 20260416.0 | 2026-04-16 | 10 | 10A20260416074850 | K552 |  |  |  | ?????? | 14#??-AMI????? | 14#??-AMI????? |  |  | POS14-AMI????? | POS 14 | F2NF019 | F2NF019 |  | EOS EXT | OTHER | 70320.0 | 26160.0 | 44160.0 | 2026-04-16 07:48:48 | 2026-04-16 09:52:48 | 2026-04-16 07:48:48 | 2026-04-16 09:52:48 | 10A | 10B | ??? | ?? |  | 2026-07-07 18:57:41.297000 | 1 |


### `WBN_DATABASE.dbo.HAULAGE_IWIP_EXT` — 1,508,871 rows, 28 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| FETCH_DATE | datetime2 | 6 | True |
| SERIAL_NO | nvarchar | 510 | True |
| WB_TIME | int | 4 | True |
| DATE | date | 3 | True |
| WB_ID | nvarchar | 510 | True |
| TICKET_NO | nvarchar | 100 | False |
| TRUCK_ID | nvarchar | 510 | True |
| CARGO_NAME | nvarchar | 510 | True |
| ORIGIN_ID | nvarchar | 510 | True |
| SELLER | nvarchar | 510 | True |
| BUYER | nvarchar | 510 | True |
| CONTRACTOR | nvarchar | 510 | True |
| ORIGIN_AREA | nvarchar | 510 | True |
| DESTINATION_AREA | nvarchar | 510 | True |
| WEIGHING_STATUS | nvarchar | 510 | True |
| BUSINESS_TYPE | nvarchar | 510 | True |
| GROSS_WEIGHT | bigint | 8 | True |
| TARE_WEIGHT | bigint | 8 | True |
| NET_WEIGHT | bigint | 8 | True |
| FIRST_WB_TIME | datetime | 8 | True |
| SECOND_WB_TIME | datetime | 8 | True |
| GROSS_WEIGHT_TIME | datetime | 8 | True |
| TARE_WEIGHT_TIME | datetime | 8 | True |
| GROSS_WEIGHT_POINT | nvarchar | 510 | True |
| TARE_WEIGHT_POINT | nvarchar | 510 | True |
| IS_COMPLETED | nvarchar | 510 | True |
| SHIFT | nvarchar | 510 | True |
| REMARKS | nvarchar | 510 | True |


**Sample (20 rows):**

| FETCH_DATE | SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | ORIGIN_ID | SELLER | BUYER | CONTRACTOR | ORIGIN_AREA | DESTINATION_AREA | WEIGHING_STATUS | BUSINESS_TYPE | GROSS_WEIGHT | TARE_WEIGHT | NET_WEIGHT | FIRST_WB_TIME | SECOND_WB_TIME | GROSS_WEIGHT_TIME | TARE_WEIGHT_TIME | GROSS_WEIGHT_POINT | TARE_WEIGHT_POINT | IS_COMPLETED | SHIFT | REMARKS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-30 11:33:15 | 16538 | 20251231 | 2025-12-31 | T10 | 10A20251231025052 | R587 | ?? | CN857 | YNI????? | YNI????? | EOS?????? | 15#??C??-YNI????? | POS14-YNI????? | 1 | EOS????? | 73580 | 28480 | 45100 | 2025-12-31 10:13:52 | 2025-12-31 11:04:26 | 2025-12-31 10:13:52 | 2025-12-31 11:04:26 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 16280 | 20251231 | 2025-12-31 | T10 | 10A20251231025830 | K043 | ?? | CN857 | YNI????? | YNI????? | ????F?? | 15#??C??-YNI????? | POS14-YNI????? | 1 | EOS????? | 52760 | 21840 | 30920 | 2025-12-31 10:21:30 | 2025-12-31 11:41:27 | 2025-12-31 10:21:30 | 2025-12-31 11:41:27 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14403 | 20251231 | 2025-12-31 | T10 | 10A20251231030555 | B792 | ?? | HN635 | HKNI????? | HKNI????? | ????H?? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 63320 | 20260 | 43060 | 2025-12-31 10:28:55 | 2025-12-31 16:50:53 | 2025-12-31 10:28:55 | 2025-12-31 16:50:53 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 13291 | 20251231 | 2025-12-31 | T10 | 10A20251231031308 | R591 | ?? | CN857 | YNI????? | YNI????? | EOS?????? | 15#??C??-YNI????? | POS14-YNI????? | 1 | EOS????? | 71660 | 28920 | 42740 | 2025-12-31 10:44:08 | 2025-12-31 21:13:48 | 2025-12-31 10:44:08 | 2025-12-31 21:13:48 | 10A | 11D | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15865 | 20251231 | 2025-12-31 | T10 | 10A20251231031429 | L643 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 72400 | 26740 | 45660 | 2025-12-31 10:37:00 | 2025-12-31 13:08:08 | 2025-12-31 10:37:00 | 2025-12-31 13:08:08 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 16232 | 20251231 | 2025-12-31 | T10 | 10A20251231034734 | L647 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 76140 | 27500 | 48640 | 2025-12-31 11:04:00 | 2025-12-31 11:48:13 | 2025-12-31 11:04:00 | 2025-12-31 11:48:13 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14155 | 20251231 | 2025-12-31 | T10 | 10A20251231034838 | L547 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 72020 | 25860 | 46160 | 2025-12-31 11:05:00 | 2025-12-31 17:16:23 | 2025-12-31 11:05:00 | 2025-12-31 17:16:23 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14402 | 20251231 | 2025-12-31 | T10 | 10A20251231041140 | B792 | ?? | HN635 | HKNI????? | HKNI????? | ????H?? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 57860 | 20260 | 37600 | 2025-12-31 11:05:00 | 2025-12-31 16:50:53 | 2025-12-31 11:05:00 | 2025-12-31 16:50:53 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15866 | 20251231 | 2025-12-31 | T10 | 10A20251231051322 | L643 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 69600 | 26740 | 42860 | 2025-12-31 12:05:00 | 2025-12-31 13:08:08 | 2025-12-31 12:05:00 | 2025-12-31 13:08:08 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15620 | 20251231 | 2025-12-31 | T10 | 10A20251231052031 | K043 | ?? | CN857 | YNI????? | YNI????? | ????F?? | 15#??C??-YNI????? | POS14-YNI????? | 1 | EOS????? | 51700 | 21400 | 30300 | 2025-12-31 12:12:00 | 2025-12-31 13:44:43 | 2025-12-31 12:12:00 | 2025-12-31 13:44:43 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15771 | 20251231 | 2025-12-31 | T10 | 10A20251231053347 | L647 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 65220 | 27400 | 37820 | 2025-12-31 12:25:00 | 2025-12-31 13:23:31 | 2025-12-31 12:25:00 | 2025-12-31 13:23:31 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15474 | 20251231 | 2025-12-31 | T10 | 10A20251231062736 | L643 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 78480 | 26640 | 51840 | 2025-12-31 13:25:00 | 2025-12-31 14:11:03 | 2025-12-31 13:25:00 | 2025-12-31 14:11:03 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15334 | 20251231 | 2025-12-31 | T10 | 10A20251231064401 | B795 | ?? | KN773 | KRS????? | KRS????? | ????H?? | 15#??B??-KRS????? | EOS-KRS????? | 1 | EOS????? | 54300 | 20880 | 33420 | 2025-12-31 13:43:00 | 2025-12-31 14:33:57 | 2025-12-31 13:43:00 | 2025-12-31 14:33:57 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15399 | 20251231 | 2025-12-31 | T10 | 10A20251231064616 | L697 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 79360 | 30000 | 49360 | 2025-12-31 13:45:00 | 2025-12-31 14:24:04 | 2025-12-31 13:45:00 | 2025-12-31 14:24:04 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14399 | 20251231 | 2025-12-31 | T10 | 10A20251231065531 | B792 | ?? | HN635 | HKNI????? | HKNI????? | ????H?? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 59420 | 20260 | 39160 | 2025-12-31 13:54:00 | 2025-12-31 16:50:53 | 2025-12-31 13:54:00 | 2025-12-31 16:50:53 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 15164 | 20251231 | 2025-12-31 | T10 | 10A20251231070354 | L647 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 72040 | 27100 | 44940 | 2025-12-31 14:04:00 | 2025-12-31 15:02:23 | 2025-12-31 14:04:00 | 2025-12-31 15:02:23 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14929 | 20251231 | 2025-12-31 | T10 | 10A20251231071203 | K043 | ?? | CN857 | YNI????? | YNI????? | ????F?? | 15#??C??-YNI????? | POS14-YNI????? | 1 | EOS????? | 61300 | 20500 | 40800 | 2025-12-31 14:13:00 | 2025-12-31 15:40:47 | 2025-12-31 14:13:00 | 2025-12-31 15:40:47 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14989 | 20251231 | 2025-12-31 | T10 | 10A20251231072950 | L691 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 82380 | 27280 | 55100 | 2025-12-31 14:30:00 | 2025-12-31 15:32:44 | 2025-12-31 14:30:00 | 2025-12-31 15:32:44 | 10A | 10B | ??? | ?? |   |
| 2026-05-30 11:33:15 | 13690 | 20251231 | 2025-12-31 | T10 | 10A20251231073858 | L643 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 67680 | 24280 | 43400 | 2025-12-31 14:39:00 | 2025-12-31 18:12:57 | 2025-12-31 14:39:00 | 2025-12-31 18:12:57 | 10A | 10A | ??? | ?? |   |
| 2026-05-30 11:33:15 | 14021 | 20251231 | 2025-12-31 | T10 | 10A20251231074011 | L633 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? | 1 | EOS????? | 69160 | 26400 | 42760 | 2025-12-31 14:41:00 | 2025-12-31 17:29:41 | 2025-12-31 14:41:00 | 2025-12-31 17:29:41 | 10A | 10B | ??? | ?? |   |


### `WBN_DATABASE.dbo.RSF_HAULING_DATA` — 1,143,509 rows, 18 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| DATE | datetime | 8 | True |
| SHIFT | int | 4 | True |
| COMPANY | nvarchar | 100 | True |
| DEPARTEMENT | nvarchar | 100 | True |
| UNIT_TYPE | nvarchar | 100 | True |
| UNIT_BRAND | nvarchar | 100 | True |
| NB_UNIT | nvarchar | 100 | True |
| TRIP | float | 8 | True |
| LOADING_TIME | time | 5 | True |
| UNLOADING_TIME | time | 5 | True |
| ORIGIN_KM | nvarchar | 100 | True |
| ORIGIN | nvarchar | 100 | True |
| DESTINATION_KM | nvarchar | 100 | True |
| DESTINATION | nvarchar | 100 | True |
| LOCATION | nvarchar | 100 | True |
| ELEVATION | float | 8 | True |
| TF | float | 8 | True |


**Sample (20 rows):**

| ID | DATE | SHIFT | COMPANY | DEPARTEMENT | UNIT_TYPE | UNIT_BRAND | NB_UNIT | TRIP | LOADING_TIME | UNLOADING_TIME | ORIGIN_KM | ORIGIN | DESTINATION_KM | DESTINATION | LOCATION | ELEVATION | TF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 321550 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L240 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321551 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K365 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321552 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L216 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321553 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L565 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321554 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L236 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321555 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K493 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321556 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | B911 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321557 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L248 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321558 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L257 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321559 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L516 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321560 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L204 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321561 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L188 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321562 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L559 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321563 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K054 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321564 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L391 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321565 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K357 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321566 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L588 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321567 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K056 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321568 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K093 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |
| 321569 | 2024-10-01 00:00:00 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L212 | 1.0 |  |  | KM8 | HUAFEI | KM26 | GUDANG TAILING HUAFEI |  |  |  |


### `WBN_DATABASE.dbo.DISTANCE_MINING` — 83,462 rows, 14 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| DATE | datetime | 8 | True |
| CONTRACTOR | nvarchar | 510 | True |
| SHIFT | float | 8 | True |
| PIT | nvarchar | 510 | True |
| DIGGER | nvarchar | 510 | True |
| BLOCK_ID | nvarchar | 510 | True |
| MATERIAL | nvarchar | 510 | True |
| MATERIAL2 | nvarchar | 510 | True |
| DUMPING_AREA | nvarchar | 510 | True |
| RIT | float | 8 | True |
| DISTANCE | float | 8 | True |
| WMT | float | 8 | True |
| BCM | float | 8 | True |


**Sample (20 rows):**

| ID | DATE | CONTRACTOR | SHIFT | PIT | DIGGER | BLOCK_ID | MATERIAL | MATERIAL2 | DUMPING_AREA | RIT | DISTANCE | WMT | BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_04 | 20.0 | 1100.0 | 600.0000000000007 | 338.983050847458 |
| 2 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 28.0 | 700.0 | 840.0000000000009 | 474.5762711864412 |
| 3 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | LIM |  | LD_TF_04 | 26.0 | 1000.0 | 780.0000000000009 | 440.6779661016954 |
| 4 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | TS |  | TEMP_SD_TF_SMA_01 | 2.0 | 1400.0 | 60.000000000000064 | 33.8983050847458 |
| 5 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 35.0 | 700.0 | 1050.0000000000011 | 593.2203389830515 |
| 6 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 415 |  | LIM |  | LD_TF_04 | 20.0 | 800.0 | 600.0000000000007 | 338.983050847458 |
| 7 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 415 |  | SAP |  | TOS_TF_SMA_02 | 18.0 | 700.0 | 540.0000000000006 | 305.0847457627122 |
| 8 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 805 |  | LIM |  | LD_TF_04 | 33.0 | 1000.0 | 990.000000000001 | 559.3220338983057 |
| 9 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 805 |  | LIM |  | LD_TF_04 | 5.0 | 1000.0 | 150.00000000000017 | 84.7457627118645 |
| 10 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 805 |  | TS |  | TEMP_SD_TF_SMA_01 | 33.0 | 1600.0 | 990.000000000001 | 559.3220338983057 |
| 11 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 804 |  | LIM |  | LD_TF_04 | 13.0 | 800.0 | 390.00000000000045 | 220.3389830508477 |
| 12 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 803 |  | SAP |  | TOS_TF_SMA_04 | 3.0 | 400.0 | 90.0000000000001 | 50.8474576271187 |
| 13 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 803 |  | SAP |  | TOS_TF_SMA_02 | 6.0 | 1600.0 | 180.0000000000002 | 101.6949152542374 |
| 14 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 803 |  | WST |  | BF_PHASE_4 | 38.0 | 1600.0 | 1140.0000000000014 | 644.0677966101703 |
| 15 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 803 |  | WST | BD | AKSES_PHASE_6 | 31.0 | 900.0 | 930.0000000000011 | 525.4237288135599 |
| 16 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 801 |  | WST |  | BF_PHASE_4 | 23.0 | 800.0 | 690.0000000000008 | 389.83050847457673 |
| 17 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 801 |  | WST | BD | AKSES_PHASE_6 | 4.0 | 1400.0 | 120.00000000000013 | 67.7966101694916 |
| 18 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 801 |  | SAP |  | TOS_TF_SMA_03 | 26.0 | 300.0 | 780.0000000000009 | 440.6779661016954 |
| 19 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 801 |  | WST |  | BF_PHASE_4 | 17.0 | 800.0 | 510.0000000000005 | 288.1355932203393 |
| 20 | 2025-04-28 00:00:00 | SMA | 1.0 | TF | EXC 801 |  | TS |  | TEMP_SD_TF_SMA_01 | 1.0 | 500.0 | 30.000000000000032 | 16.9491525423729 |


### `WBN_DATABASE.dbo.HAUL_ROAD_STA` — 3,122 rows, 11 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| OBJECTID | float | 8 | True |
| NAME | varchar | -1 | True |
| LAYER | varchar | -1 | True |
| ELEVATION | varchar | -1 | True |
| DIRECTION | varchar | 50 | False |
| IDLINK | varchar | -1 | True |
| SectionKM | float | 8 | False |
| CONTRACTOR | nvarchar | 100 | True |
| DISP.ROAD | nvarchar | 100 | True |
| wkt | varchar | -1 | True |
| GEOM | geography | -1 | True |


**Sample (20 rows):**

| OBJECTID | NAME | LAYER | ELEVATION | DIRECTION | IDLINK | SectionKM | CONTRACTOR | DISP.ROAD | wkt | GEOM |
|---|---|---|---|---|---|---|---|---|---|---|
| 2311.0 | 2+450 | 1 | 0 | BLB | BLB2+450 | 2.45 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9687637645520368 0.4830631126541097 0.000000000… | e6100000010d2237b08b81eade3f4193bb3900fe5f400000000000000000 |
| 2312.0 | 2+475 | 1 | 0 | BLB | BLB2+475 | 2.475 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9685336777824602 0.4832058462774921 0.000000000… | e6100000010d7adcbf36d8ecde3f9ec9ad74fcfd5f400000000000000000 |
| 2313.0 | 2+500 | 1 | 0 | BLB | BLB2+500 | 2.5 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9683332107633476 0.4833077965207324 0.000000000… | e6100000010de855fdd283eede3ffef6db2bf9fd5f400000000000000000 |
| 2314.0 | 2+525 | 1 | 0 | BLB | BLB2+525 | 2.525 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9681261370139111 0.4833953465815817 0.000000000… | e6100000010d8cd02609f3efde3f2a3854c7f5fd5f400000000000000000 |
| 2315.0 | 2+550 | 1 | 0 | BLB | BLB2+550 | 2.55 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9679134755693610 0.4834680669407412 0.000000000… | e6100000010dc0ee0a0c24f1de3f66bb5c4bf2fd5f400000000000000000 |
| 2316.0 | 2+575 | 1 | 0 | BLB | BLB2+575 | 2.575 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9676962733091443 0.4835255995457245 0.000000000… | e6100000010db2f8345b15f2de3fba9459bceefd5f400000000000000000 |
| 2317.0 | 2+600 | 1 | 0 | BLB | BLB2+600 | 2.6 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9674756022579203 0.4835676804249409 0.000000000… | e6100000010d0cf934dbc5f2de3f0bd8c91eebfd5f400000000000000000 |
| 2318.0 | 2+625 | 1 | 0 | BLB | BLB2+625 | 2.625 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9672560565005597 0.4836138203263726 0.000000000… | e6100000010d47818c6187f3de3fc861f285e7fd5f400000000000000000 |
| 2319.0 | 2+650 | 1 | 0 | BLB | BLB2+650 | 2.65 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9670578130634055 0.4837183497704946 0.000000000… | e6100000010dbb512fcf3df5de3fb61c7446e4fd5f400000000000000000 |
| 2320.0 | 2+675 | 1 | 0 | BLB | BLB2+675 | 2.675 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9668998230618797 0.4838779066081391 0.000000000… | e6100000010dbce3080adbf7de3fc6a3cbafe1fd5f400000000000000000 |
| 2321.0 | 2+700 | 1 | 0 | BLB | BLB2+700 | 2.7 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9667915203214505 0.4840755774960142 0.000000000… | e6100000010dfdcf882118fbde3f2b758ae9dffd5f400000000000000000 |
| 2322.0 | 2+725 | 1 | 0 | BLB | BLB2+725 | 2.725 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9666937145415062 0.4842791632360357 0.000000000… | e6100000010dc8e90e086efede3f174d504fdefd5f400000000000000000 |
| 2323.0 | 2+750 | 1 | 0 | BLB | BLB2+750 | 2.75 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9666024794812955 0.4844855894555907 0.000000000… | e6100000010d361586d8cf01df3fb366a5d0dcfd5f400000000000000000 |
| 2324.0 | 2+775 | 1 | 0 | BLB | BLB2+775 | 2.775 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9665651897302041 0.4847077980602899 0.000000000… | e6100000010d5d3f32db7305df3ff8d53d34dcfd5f400000000000000000 |
| 2325.0 | 2+800 | 1 | 0 | BLB | BLB2+800 | 2.8 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9665794651015887 0.4849332936966794 0.000000000… | e6100000010da3cd4aa72509df3f2de61d70dcfd5f400000000000000000 |
| 2326.0 | 2+825 | 1 | 0 | BLB | BLB2+825 | 2.825 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9666555266372256 0.4851448302704537 0.000000000… | e6100000010dc771f5e69c0cdf3fe45924afddfd5f400000000000000000 |
| 2327.0 | 2+850 | 1 | 0 | BLB | BLB2+850 | 2.85 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9667845380193256 0.4853298680119059 0.000000000… | e6100000010d3e85b801a50fdf3f934441ccdffd5f400000000000000000 |
| 2328.0 | 2+875 | 1 | 0 | BLB | BLB2+875 | 2.875 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9669062659118310 0.4855192828256812 0.000000000… | e6100000010d41135478bf12df3fe298d1cae1fd5f400000000000000000 |
| 2329.0 | 2+900 | 1 | 0 | BLB | BLB2+900 | 2.9 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9669432512310436 0.4857402418833844 0.000000000… | e6100000010d82604f3d5e16df3f0448f265e2fd5f400000000000000000 |
| 2330.0 | 2+925 | 1 | 0 | BLB | BLB2+925 | 2.925 | HJS | BLB KM2,5 - KM5,7 | POINT Z (127.9668759669787050 0.4859538333483391 0.000000000… | e6100000010d7034661bde19df3f905dbc4be1fd5f400000000000000000 |


### `WBN_DATABASE.dbo.WAITING_TIME` — 878,240 rows, 24 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| TEAM | nvarchar | 20 | True |
| DATE | date | 3 | True |
| EQUIPMENT_ID | nvarchar | 100 | True |
| SHIFT | int | 4 | True |
| ORIGIN_ID | nvarchar | 100 | True |
| ORIGIN_AREA | nvarchar | 100 | True |
| DESTINATION | nvarchar | 200 | True |
| BLOCK_ID | nvarchar | 100 | True |
| RIT | int | 4 | True |
| WB_ID | nvarchar | 100 | True |
| LOADING_WAITING_TIME | time | 5 | True |
| LOADING_TIME | time | 5 | True |
| LOADING_DIFFERENCE_TIME | int | 4 | True |
| DUMPING_WAITING_TIME | time | 5 | True |
| DUMPING_TIME | time | 5 | True |
| DUMPING_DIFFERENCE_TIME | int | 4 | True |
| DRIVER_ID | nvarchar | 100 | True |
| PIT | nvarchar | 100 | True |
| FUEL_FILLING_TIME | time | 5 | True |
| REMARK | nvarchar | 510 | True |
| FUEL_FILLING_TIME 2 | time | 5 | True |
| TOTAL_FUEL | nvarchar | 100 | True |
| TOTAL_FUEL 2 | nvarchar | 100 | True |


**Sample (20 rows):**

| ID | TEAM | DATE | EQUIPMENT_ID | SHIFT | ORIGIN_ID | ORIGIN_AREA | DESTINATION | BLOCK_ID | RIT | WB_ID | LOADING_WAITING_TIME | LOADING_TIME | LOADING_DIFFERENCE_TIME | DUMPING_WAITING_TIME | DUMPING_TIME | DUMPING_DIFFERENCE_TIME | DRIVER_ID | PIT | FUEL_FILLING_TIME | REMARK | FUEL_FILLING_TIME 2 | TOTAL_FUEL | TOTAL_FUEL 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 71844 | E | 2025-10-30 | L961 | 2 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 02:47:00 | 05:55:00 | 188 | 03:18:00 | 03:18:00 | 0 | 8240209005 |  |  |  |  |  |  |
| 71845 | B | 2025-10-30 | K811 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 09:47:00 | 12:07:00 | 140 | 11:00:00 | 11:16:00 | 16 | 8241011100 | KR |  |  |  |  |  |
| 71846 | E | 2025-10-30 | N035 | 1 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 11:00:00 | 13:18:00 | 138 | 11:49:00 | 11:59:00 | 10 | 8231207168 |  |  |  |  |  |  |
| 71847 | D | 2025-10-30 | L958 | 1 | SAMPLE | CSW | BIRI | SAMPLE | 1 | NOT WEIGHED | 16:41:00 | 18:57:00 | 136 | 19:30:00 | 19:30:00 | 0 | 8240303036 |  |  |  |  |  |  |
| 71848 | B | 2025-10-30 | L054 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 14:55:00 | 17:09:00 | 134 | 16:15:00 | 16:24:00 | 9 | 8240812099 | KR |  |  |  |  |  |
| 71849 | B | 2025-10-30 | L056 | 2 | LD_POS12_001/D | TOS_KRENE_01 | POS12 | E/KRENE.I.090 | 1 | 14 | 20:52:00 | 23:05:00 | 133 | 00:22:00 | 01:12:00 | 50 | 8240114149 | KR |  |  |  |  |  |
| 71850 | C | 2025-10-30 | K724 | 2 | ADM.678 | TOS_TF_STM_13 | POS12 | TF.B.3935 | 1 | 14 | 03:57:00 | 06:07:00 | 130 |  |  |  |  | TOFU |  | GANTUNGAN |  |  |  |
| 71851 | B | 2025-10-30 | N726 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 09:01:00 | 11:09:00 | 128 | 10:24:00 | 10:40:00 | 16 | 8231204004 | KR |  |  |  |  |  |
| 71852 | B | 2025-10-30 | K620 | 2 | LD_POS12_001/D | TOS_KRENE_01 | POS12 | E/KRENE.I.090 | 1 | 14 | 21:10:00 | 23:17:00 | 127 | 01:00:00 | 01:25:00 | 25 | 8241119101 | KR |  |  |  |  |  |
| 71853 | B | 2025-10-30 | N657 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 12:45:00 | 14:52:00 | 127 | 14:12:00 | 14:25:00 | 13 | 8240122006 | KR |  |  |  |  |  |
| 71854 | B | 2025-10-30 | N498 | 1 | LD.POS 12.001 | LD_KR_003 | POS12 | LD.KR.003 | 1 | 14 | 10:53:00 | 13:00:00 | 127 | 14:34:00 | 14:44:00 | 10 | 8240219029 | KR |  |  |  |  |  |
| 71855 | C | 2025-10-30 | N693 | 2 | L2NW038 | TOS1 | ?? | TOS1-RIM-1174 | 1 | 8 | 00:15:00 | 02:20:00 | 125 |  |  |  |  | POSITION |  | GANTUNGAN |  |  |  |
| 71856 | C | 2025-10-30 | K538 | 2 | ADM.678 | TOS_TF_STM_13 | POS12 | TF.B.3935 | 1 | 14 | 03:58:00 | 06:02:00 | 124 |  |  |  |  | TOFU |  | GANTUNGAN |  |  |  |
| 71857 | B | 2025-10-30 | K940 | 2 | LD_POS12_001/D | TOS_KRENE_01 | POS12 | E/KRENE.I.090 | 1 | 14 | 20:42:00 | 22:40:00 | 118 | 23:49:00 | 00:22:00 | 33 | 8240701079 | KR |  |  |  |  |  |
| 71858 | C | 2025-10-30 | N425 | 2 | ADM.678 | TOS_TF_STM_13 | POS12 | TF.B.3935 | 1 | 14 | 03:30:00 | 05:20:00 | 110 |  |  |  |  | TOFU |  | GANTUNGAN |  |  |  |
| 71859 | B | 2025-10-30 | L125 | 2 | LD_POS12_001/D | TOS_KRENE_01 | POS12 | E/KRENE.I.091 | 1 | 14 | 23:00:00 | 00:46:00 | 106 | 01:56:00 | 03:18:00 | 82 | 8240531063 | KR |  |  |  |  |  |
| 71860 | B | 2025-10-30 | K813 | 2 | LD_POS12_001/D | TOS_KRENE_01 | POS12 | E/KRENE.I.091 | 1 | 14 | 23:10:00 | 00:53:00 | 103 | 03:25:00 | 04:21:00 | 56 | 8240331051 | KR |  |  |  |  |  |
| 71861 | E | 2025-10-30 | N064 | 1 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 11:05:00 | 12:47:00 | 102 | 13:11:00 | 13:11:00 | 0 | 8240103090 |  |  |  |  |  |  |
| 71862 | A | 2025-10-30 | N534 | 1 | BLB-A.131 | TOS_BLB_03 | ?? | BLB.G.5759 | 1 | 6A | 11:21:00 | 13:00:00 | 99 | 14:15:00 | 14:29:00 | 14 | 8230919106 | BLB |  |  |  |  |  |
| 71863 | C | 2025-10-30 | N802 | 1 | M1_POS12_001 | TOS_TF_SMA_04 | POS12 | TF.B.3009 | 1 | 14 | 12:21:00 | 14:00:00 | 99 | 17:30:00 | 17:35:00 | 5 | 8231212108 | TOFU |  |  |  |  |  |


### `FMS_DB.dbo.FMS_PLAYBACK_TRACK_DATA` — 27,456,831 rows, 18 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| FETCH_DATE | datetime | 8 | True |
| plateNumber | nvarchar | 100 | True |
| acc | float | 8 | True |
| deviceType | nvarchar | 510 | True |
| distance | float | 8 | True |
| lng | float | 8 | True |
| driving_time | float | 8 | True |
| dump_energy | nvarchar | 510 | True |
| receive_time | float | 8 | True |
| loc_type | float | 8 | True |
| speed | float | 8 | True |
| engine | float | 8 | True |
| oils | float | 8 | True |
| course | float | 8 | True |
| imei | bigint | 8 | False |
| time | bigint | 8 | False |
| interpolation_flag | float | 8 | True |
| lat | float | 8 | True |


**Sample (20 rows):**

| FETCH_DATE | plateNumber | acc | deviceType | distance | lng | driving_time | dump_energy | receive_time | loc_type | speed | engine | oils | course | imei | time | interpolation_flag | lat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 | smart_1c | 6835.0 | 127.916742 | 4.0 |  | 1778398774705.0 | 0.0 | 0.0 |  | -1.0 | 341.0 | 107015291859999 | 1778398774000 | 1.0 | 0.482252 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 2063.0 | 127.916574 | 122.0 |  | 1778398905725.0 | 0.0 | 0.0 |  | -1.0 | 157.0 | 107015291859999 | 1778398905000 | 1.0 | 0.482186 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 134.0 | 127.916575 | 1.0 |  | 1778400726984.0 | 0.0 | 4.0 |  | -1.0 | 66.0 | 107015291859999 | 1778400709000 | 1.0 | 0.482174 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1575.0 | 127.916631 | 1.0 |  | 1778400726984.0 | 0.0 | 4.0 |  | -1.0 | 69.0 | 107015291859999 | 1778400710000 | 1.0 | 0.482304 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 320.0 | 127.916654 | 122.0 |  | 1778400903025.0 | 0.0 | 0.0 |  | -1.0 | 69.0 | 107015291859999 | 1778400902000 | 1.0 | 0.48232 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 189.0 | 127.916637 | 2.0 |  | 1778400926368.0 | 0.0 | 7.0 |  | -1.0 | 63.0 | 107015291859999 | 1778400925000 | 1.0 | 0.482319 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 576.0 | 127.916688 | 2.0 |  | 1778400930072.0 | 0.0 | 0.0 |  | -1.0 | 98.0 | 107015291859999 | 1778400929000 | 1.0 | 0.482328 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 627.0 | 127.916738 | 2.0 |  | 1778400931674.0 | 0.0 | 6.0 |  | -1.0 | 130.0 | 107015291859999 | 1778400931000 | 1.0 | 0.482302 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1235.0 | 127.916816 | 5.0 |  | 1778400974022.0 | 0.0 | 5.0 |  | -1.0 | 108.0 | 107015291859999 | 1778400938000 | 1.0 | 0.482223 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 768.0 | 127.916884 | 2.0 |  | 1778400953701.0 | 0.0 | 0.0 |  | -1.0 | 59.0 | 107015291859999 | 1778400944000 | 1.0 | 0.482235 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 601.0 | 127.916926 | 2.0 |  | 1778401058685.0 | 0.0 | 0.0 |  | -1.0 | 45.0 | 107015291859999 | 1778400948000 | 1.0 | 0.482269 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 582.0 | 127.916964 | 5.0 |  | 1778401028563.0 | 0.0 | 0.0 |  | -1.0 | 43.0 | 107015291859999 | 1778400953000 | 1.0 | 0.482305 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 2475.0 | 127.917125 | 17.0 |  | 1778401058685.0 | 0.0 | 4.0 |  | -1.0 | 55.0 | 107015291859999 | 1778400970000 | 1.0 | 0.482452 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1181.0 | 127.917198 | 9.0 |  | 1778401058685.0 | 0.0 | 5.0 |  | -1.0 | 43.0 | 107015291859999 | 1778400979000 | 1.0 | 0.482529 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 582.0 | 127.917235 | 4.0 |  | 1778401028563.0 | 0.0 | 5.0 |  | -1.0 | 48.0 | 107015291859999 | 1778400983000 | 1.0 | 0.482566 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 598.0 | 127.917286 | 2.0 |  | 1778401058685.0 | 0.0 | 0.0 |  | -1.0 | 99.0 | 107015291859999 | 1778400988000 | 1.0 | 0.482583 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 535.0 | 127.917332 | 2.0 |  | 1778401058685.0 | 0.0 | 5.0 |  | -1.0 | 118.0 | 107015291859999 | 1778400990000 | 1.0 | 0.482569 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1424.0 | 127.917441 | 11.0 |  | 1778401033658.0 | 0.0 | 4.0 |  | -1.0 | 135.0 | 107015291859999 | 1778401001000 | 1.0 | 0.482502 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1741.0 | 127.917539 | 12.0 |  | 1778401033558.0 | 0.0 | 3.0 |  | -1.0 | 137.0 | 107015291859999 | 1778401013000 | 1.0 | 0.48238 |
| 2026-05-12 15:00:30.443000 | SS074 | 1.0 |  | 1487.0 | 127.917607 | 122.0 |  | 1778401185046.0 | 0.0 | 0.0 |  | -1.0 | 20.0 | 107015291859999 | 1778401184000 | 1.0 | 0.482269 |


### `FMS_DB.dbo.auto_kmFMS_PLAYBACK_TRACK_DATA` — 20,448,378 rows, 4 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| imei | bigint | 8 | False |
| time | bigint | 8 | False |
| DIRECTION | nvarchar | 100 | True |
| SectionKM | float | 8 | True |


**Sample (20 rows):**

| imei | time | DIRECTION | SectionKM |
|---|---|---|---|
| 107015291859999 | 1778398774000 | KR | 11.0 |
| 107015291859999 | 1778398905000 | KR | 11.0 |
| 107015291859999 | 1778400709000 | KR | 11.0 |
| 107015291859999 | 1778400710000 | KR | 11.0 |
| 107015291859999 | 1778400902000 | KR | 11.0 |
| 107015291859999 | 1778400925000 | KR | 11.0 |
| 107015291859999 | 1778400929000 | KR | 11.0 |
| 107015291859999 | 1778400931000 | KR | 11.0 |
| 107015291859999 | 1778400938000 | KR | 11.0 |
| 107015291859999 | 1778400944000 | KR | 11.0 |
| 107015291859999 | 1778400948000 | KR | 11.0 |
| 107015291859999 | 1778400953000 | KR | 11.0 |
| 107015291859999 | 1778400970000 | KR | 11.0 |
| 107015291859999 | 1778400979000 | KR | 11.0 |
| 107015291859999 | 1778400983000 | KR | 10.9 |
| 107015291859999 | 1778400988000 | KR | 10.9 |
| 107015291859999 | 1778400990000 | KR | 10.9 |
| 107015291859999 | 1778401001000 | KR | 10.9 |
| 107015291859999 | 1778401013000 | KR | 10.9 |
| 107015291859999 | 1778401184000 | KR | 10.9 |


### `FMS_DB.dbo.FMS_CONGESTION_SEG` — 18,281 rows, 9 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| HOUR_TS | bigint | 8 | False |
| SEG_ID | nvarchar | 80 | False |
| DIR | char | 4 | False |
| SUM_SPD | float | 8 | True |
| FIX_N | int | 4 | True |
| TRUCK_N | int | 4 | True |
| UPDATED_AT | bigint | 8 | True |
| SUM_TRAV_MS | float | 8 | True |
| TRAV_N | int | 4 | True |


**Sample (20 rows):**

| HOUR_TS | SEG_ID | DIR | SUM_SPD | FIX_N | TRUCK_N | UPDATED_AT | SUM_TRAV_MS | TRAV_N |
|---|---|---|---|---|---|---|---|---|
| 1784077200000 | BLB KM17-18 | down | 1230.0 | 91 | 5 | 1784510901345 | 860000.0 | 4 |
| 1784077200000 | BLB KM17-18 | up   | 697.0 | 43 | 4 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM18-19 | down | 1404.0 | 108 | 5 | 1784510901345 | 695000.0 | 3 |
| 1784077200000 | BLB KM18-19 | up   | 740.0 | 57 | 5 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM19-20 | down | 659.0 | 41 | 2 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM19-20 | up   | 53.0 | 4 | 3 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM3-4 | down | 29.0 | 3 | 1 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM3-4 | up   | 181.0 | 13 | 1 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM5-6 | down | 80.0 | 4 | 1 | 1784510901345 | 42000.0 | 1 |
| 1784077200000 | BLB KM6-7 | down | 160.0 | 8 | 1 | 1784510901345 | 150000.0 | 1 |
| 1784077200000 | BLB KM7-8 | down | 114.0 | 11 | 2 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM8-9 | down | 258.0 | 13 | 1 | 1784510901345 | 172000.0 | 1 |
| 1784077200000 | BLB KM9-10 | down | 446.0 | 25 | 1 | 1784510901345 | 180000.0 | 1 |
| 1784077200000 | CBB KM10-11 | down | 673.0 | 51 | 4 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | CBB KM10-11 | up   | 503.0 | 35 | 5 | 1784510901345 | 360000.0 | 2 |
| 1784077200000 | CBB KM11-12 | down | 1118.0 | 95 | 3 | 1784510901345 | 490000.0 | 2 |
| 1784077200000 | CBB KM11-12 | up   | 704.0 | 42 | 3 | 1784510901345 | 167000.0 | 1 |
| 1784077200000 | CBB KM12-13 | down | 458.0 | 24 | 2 | 1784510901345 | 300000.0 | 2 |
| 1784077200000 | CBB KM12-13 | up   | 199.0 | 9 | 1 | 1784510901345 | 150000.0 | 1 |
| 1784077200000 | CBB KM13-14 | down | 337.0 | 35 | 3 | 1784510901345 | 420000.0 | 2 |


### `FMS_DB.dbo.FMS_HAUL_CYCLES` — 288 rows, 10 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| CYCLE_ID | int | 4 | False |
| TRUCK_PLATE | nvarchar | 100 | True |
| PLAN_DATE | date | 3 | True |
| SHIFT | float | 8 | True |
| PIT | nvarchar | 100 | True |
| TOS_PILE | nvarchar | 200 | True |
| EXCAVATOR | nvarchar | 200 | True |
| DESTINATION | nvarchar | 400 | True |
| MATERIAL | nvarchar | 200 | True |
| DUMP_TS | datetime | 8 | True |


**Sample (20 rows):**

| CYCLE_ID | TRUCK_PLATE | PLAN_DATE | SHIFT | PIT | TOS_PILE | EXCAVATOR | DESTINATION | MATERIAL | DUMP_TS |
|---|---|---|---|---|---|---|---|---|---|
| 1 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:40:39.917000 |
| 2 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:40:56.183000 |
| 3 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:42:11.293000 |
| 4 | B279 | 2026-06-26 | 2.0 |  |  | E021 |  | Waste | 2026-06-26 22:42:45.750000 |
| 5 | B279 | 2026-06-27 | 1.0 | BLB |  | M267 | FENI A | SAP | 2026-06-27 08:28:04.793000 |
| 6 | B537 | 2026-06-28 | 2.0 | KRENE |  | E299 | POS 12 | SAP | 2026-06-28 22:48:41.350000 |
| 7 | B537 | 2026-06-28 | 2.0 | KRENE |  | E299 | POS 12 | SAP | 2026-06-28 22:49:02.267000 |
| 8 | B287 | 2026-06-29 | 1.0 | KRENE |  | E299 | POS 12 | SAP | 2026-06-29 15:08:40.720000 |
| 9 | N110 | 2026-06-30 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-06-30 08:30:46.897000 |
| 10 | N110 | 2026-06-30 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-06-30 08:39:52.577000 |
| 11 | B284 | 2026-07-01 | 1.0 | BLB |  | M267 | POS 14 | SAP | 2026-07-01 09:28:31.570000 |
| 12 | B284 | 2026-07-02 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-07-02 18:05:26.350000 |
| 13 | B284 | 2026-07-02 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-07-02 18:06:34.897000 |
| 14 | B284 | 2026-07-02 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-07-02 18:27:16.367000 |
| 15 | B284 | 2026-07-02 | 1.0 | BLB |  | E270 | POS 14 | SAP | 2026-07-02 18:27:29.227000 |
| 16 | K618 | 2026-07-04 | 1.0 | KRENE |  | E295 | POS 12 | SAP | 2026-07-04 16:24:14.677000 |
| 17 | R378 | 2026-07-05 | 1.0 | BLB | BLB.G.7011 |  | FENI A (1-2) | HGS | 2026-07-05 21:53:34.010000 |
| 18 | L799 | 2026-07-05 | 1.0 | BLB | BLB.G.6850 |  | POS 14 | HGS | 2026-07-05 21:59:13.117000 |
| 19 | K802 | 2026-07-05 | 1.0 | BLB | BLB.G.6850 |  | POS 14 | HGS | 2026-07-05 22:55:36.793000 |
| 20 | R321 | 2026-07-05 | 1.0 | BLB | BLB.G.7011 |  | FENI A (1-2) | HGS | 2026-07-05 23:53:00.637000 |


### `FMS_DB.dbo.FMS_GEOFENCE_VISITS` — 74,315 rows, 17 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| EVENT_ID | varchar | 36 | False |
| UNIT_ID | varchar | 40 | False |
| UNIT_TYPE | varchar | 40 | True |
| ORG_NAME | nvarchar | 400 | True |
| GEOFENCE_ID | nvarchar | 40 | False |
| GEOFENCE_NAME | nvarchar | 400 | True |
| GEOFENCE_TYPE | varchar | 40 | True |
| ENTER_TS | bigint | 8 | False |
| EXIT_TS | bigint | 8 | True |
| DURATION_SEC | int | 4 | True |
| ENTER_LAT | float | 8 | True |
| ENTER_LNG | float | 8 | True |
| EXIT_LAT | float | 8 | True |
| EXIT_LNG | float | 8 | True |
| STATUS | varchar | 12 | False |
| SOURCE | varchar | 20 | True |
| CREATED_AT | bigint | 8 | False |


**Sample (20 rows):**

| EVENT_ID | UNIT_ID | UNIT_TYPE | ORG_NAME | GEOFENCE_ID | GEOFENCE_NAME | GEOFENCE_TYPE | ENTER_TS | EXIT_TS | DURATION_SEC | ENTER_LAT | ENTER_LNG | EXIT_LAT | EXIT_LNG | STATUS | SOURCE | CREATED_AT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00014d7f-f897-4361-8d1f-f9b16b2df0d2 | N469 | Haul Truck | RIM??? G ?? | a2b62513 | TF | pit | 1785361980000 | 1785363990000 | 2010 | 0.801267 | 128.027037 | 0.80481 | 128.022368 | EXITED | live | 1785362012589 |
| 0001aa51-7a22-4d2d-bf55-9a9ba551bf59 | K624 | Haul Truck | RIM??? B ?? | sh_sh12 | SH12 | sampling | 1785452190000 | 1785452190000 | 0 | 0.616135 | 127.92446 | 0.616135 | 127.92446 | EXITED | live | 1785452210831 |
| 00022053-d1ba-4b6a-a4c1-23f2ea3a31e3 | R283 | Haul Truck | RIM??? D ?? | wb_wb_iwip_t12 | WB_IWIP_T12 | weighbridge | 1785211696000 | 1785211749000 | 53 | 0.508318 | 127.898747 | 0.506115 | 127.898498 | EXITED | live | 1785211740524 |
| 00024379-7809-4388-96fb-36ecf23c7367 | R922 | Haul Truck | RIM??? E ?? | 2224ef93 | KR | pit | 1785050160000 | 1785051202000 | 1042 | 0.679645 | 127.975703 | 0.648738 | 127.973213 | EXITED | live | 1785050186849 |
| 0004f26a-e851-453b-ac9a-f5444d306cbd | N417 | Haul Truck | RIM??? H ?? | 2224ef93 | KR | pit | 1785247028000 | 1785252030000 | 5002 | 0.649862 | 127.972642 | 0.683093 | 127.97617 | EXITED | live | 1785247054040 |
| 00056077-e870-453e-bd05-82cde82dea17 | SS008 | Water Truck | ???? LOGISTICS | 2e938c89 | CBB | pit | 1785310961000 | 1785311741000 | 780 | 0.517541 | 127.940711 | 0.517541 | 127.940711 | EXITED | live | 1785310986832 |
| 00057a7c-87ea-4e49-862d-fb7d99d07cca | N727 | Haul Truck | ????? | 2224ef93 | KR | pit | 1785141900000 | 1785141900000 | 0 | 0.673955 | 127.972813 | 0.673955 | 127.972813 | EXITED | live | 1785301829424 |
| 0005c01d-f8f5-43b7-9fde-5afc11e8a5e7 | R708 | Haul Truck | RIM??? F ?? | water_wfhr18 | KM18 | water | 1785157655000 | 1785157680000 | 25 | 0.534893 | 127.900665 | 0.533798 | 127.900435 | EXITED | live | 1785157684522 |
| 0005ce09-b605-4ce6-9138-6be69eac7334 | R382 | Haul Truck | RIM??? D ?? | 2e938c89 | CBB | pit | 1785143231000 | 1785144841000 | 1610 | 0.521533 | 127.940193 | 0.535365 | 127.952138 | EXITED | live | 1785143636387 |
| 0006487a-fbe4-451a-8b52-4ac4c3ffe433 | E080 |  | WBN??? | tos_19b335ed | TF.A.8191 | loading | 1785287427623 | 1785287487391 | 59 | 0.817615 | 128.0336 | 0.8176033 | 128.03358 | EXITED | live | 1785287453816 |
| 0006a191-b477-4c7e-8c83-a36a4be54fd1 | N348 | Haul Truck | RIM??? H ?? | 2224ef93 | KR | pit | 1785055530000 | 1785065294000 | 9764 | 0.650672 | 127.972693 | 0.684263 | 127.976443 | EXITED | live | 1785055550351 |
| 00078dca-9a43-4a9a-8a8c-45e246f1a9e5 | R924 | Haul Truck | RIM??? E ?? | wb_wb_iwip_t16 | WB_IWIP_T16 | weighbridge | 1784957820000 | 1784957886000 | 66 | 0.63823 | 127.94987 | 0.640555 | 127.95294 | EXITED | live | 1784957869173 |
| 0008588c-584e-4651-9883-e1d94a8e7380 | R332 | Haul Truck | RIM??? F ?? | 2224ef93 | KR | pit | 1785146943000 | 1785149113000 | 2170 | 0.660418 | 127.975185 | 0.693381 | 127.97862 | EXITED | live | 1785147621579 |
| 000be130-66a1-47b7-9738-3bb3ceeaf58d | R937 | Haul Truck | RIM??? E ?? | wb_wb_iwip_t14 | WB_IWIP_T14 | weighbridge | 1785039758000 | 1785039780000 | 22 | 0.601355 | 127.918087 | 0.603157 | 127.918855 | EXITED | live | 1785039793871 |
| 000c7dda-295c-4d35-8eb2-7d3d12c603ef | K903 | Haul Truck | RIM??? A ?? | water_wfhr18 | KM18 | water | 1785170162000 | 1785170190000 | 28 | 0.534793 | 127.900605 | 0.535978 | 127.900325 | EXITED | live | 1785170172360 |
| 000c9aff-4211-49cb-aed2-062830110fae | K822 | Haul Truck | RIM??? C ?? | wb_wb_iwip_t8 | WB_IWIP_T8 | weighbridge | 1785246011000 | 1785246060000 | 49 | 0.484102 | 127.918083 | 0.484195 | 127.918365 | EXITED | live | 1785246033763 |
| 000d7e68-d6c5-46ab-b83a-7e6a19bab055 | L981 | Haul Truck | RIM??? E ?? | wb_wb_iwip_t15 | WB_IWIP_T15 | weighbridge | 1785008610000 | 1785008737000 | 127 | 0.640372 | 127.953395 | 0.639932 | 127.952105 | EXITED | live | 1785008631990 |
| 000e8db2-3a0f-44c0-8f5d-33d0b6396244 | SS102 | Water Truck | ????? | 2e938c89 | CBB | pit | 1785426780000 | 1785427380000 | 600 | 0.519605 | 127.944498 | 0.526273 | 127.931472 | EXITED | live | 1785426793279 |
| 000ecf59-d711-440d-bfad-a210b7a4b5d1 | L294 | Haul Truck | RIM??? C ?? | 2224ef93 | KR | pit | 1785812700000 | 1785816753000 | 4053 | 0.652415 | 127.973072 | 0.693232 | 127.978038 | EXITED | live | 1785812713923 |
| 000f2bd7-2c99-4a96-9880-5237a2e92fff | Y078 | Compactor | ????? | wb_wb_iwip_t16 | WB_IWIP_T16 | weighbridge | 1784994150000 | 1784994210000 | 60 | 0.638423 | 127.950188 | 0.638095 | 127.949772 | EXITED | live | 1784994179360 |


## 4. Contractor / fleet tables


### `WBN_DATABASE.dbo.EQUIPMENTS` — 7,221 rows, 15 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | nvarchar | 100 | False |
| CONTRACTOR | nvarchar | 100 | True |
| ID_EQ | nvarchar | 100 | True |
| OWNER | nvarchar | 100 | True |
| SERIAL_NO | nvarchar | 510 | True |
| TYPE | nvarchar | 100 | True |
| DIGIT | int | 4 | True |
| MANUFACTURER | nvarchar | 100 | True |
| MODEL | nvarchar | 100 | True |
| CAPACITY | int | 4 | True |
| NB_TYRES | int | 4 | True |
| BUILD_YEAR | int | 4 | True |
| DIVISION | nvarchar | 100 | True |
| NEW_ID_EQ | nvarchar | 100 | True |
| HEAVY_LIGHT | varchar | 5 | False |


**Sample (20 rows):**

| ID | CONTRACTOR | ID_EQ | OWNER | SERIAL_NO | TYPE | DIGIT | MANUFACTURER | MODEL | CAPACITY | NB_TYRES | BUILD_YEAR | DIVISION | NEW_ID_EQ | HEAVY_LIGHT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ATC-AC-301 | ATC | ATC-P3-GKT-01 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  | LIGHT |
| ATC-AC-302 | ATC | ATC-P3-GKT-02 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  | LIGHT |
| ATC-AC-303 | ATC | ATC-P3-GKT-03 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  | LIGHT |
| ATC-AC-304 | ATC | ATC-P3-GKT-04 |  |  | Air Conditioner |  | GREE | ??:GWC-12MOO5 1.5P |  |  | 2023 |  |  | LIGHT |
| ATC-AC-305 | ATC | ATC-P3-GKT-05 |  |  | Air Conditioner |  | GREE | ??:GWC-12MOO5 1.5P |  |  | 2023 |  |  | LIGHT |
| ATC-AC-306 | ATC | ATC-P3-GKT-06 |  |  | Air Conditioner |  | GREE | ??:GWC-12MOO5 1.5P |  |  | 2023 |  |  | LIGHT |
| ATC-ACO-301 | ATC | ATC-P3-KYK-01 |  |  | Air Compressor |  | ZHEJIANG KAISHAN | ??:KA15; |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-302 | ATC | ATC-P3-KYK-02 |  |  | Air Compressor |  | ZHEJIANG KAISHAN | ??:KA15; |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-303 | ATC | ATC-P3-KYK-03 |  |  | Air Compressor |  | ZHEJIANG KAISHAN | ??:KA15; |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-304 | ATC | ATC-P3-KYK-04 |  |  | Air Compressor |  | ZHEJIANG KAISHAN | ??:KA15; |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-305 | ATC | ATC-P3-KYK-05 |  |  | Air Compressor |  | ZHEJIANG KAISHAN | KA15 |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-307 | ATC | ATC-P3-KYK-07 |  |  | Air Compressor |  | ZHEJIANG KAISHAN |  |  |  | 2022 |  |  | LIGHT |
| ATC-ACO-308 | ATC | ATC-P3-KYK-08 |  |  | Air Compressor |  | ZHEJIANG KAISHAN |  |  |  | 2022 |  |  | LIGHT |
| ATC-Air Dryer-309 | ATC | ATC-P3-LDJ-09 |  |  | Air Dryer |  | ZHEJIANG KAISHAN |  |  |  | 2022 |  |  | LIGHT |
| ATC-Air Dryer-310 | ATC | ATC-P3-LDJ-10 |  |  | Air Dryer |  | ZHEJIANG KAISHAN |  |  |  | 2022 |  |  | LIGHT |
| ATC-CD-301 | ATC | ATC-P3-PSYT-01 |  |  | Crusher Divider |  | QINGDAO YAOXIN | YXPS-125X150 |  |  | 2022 |  |  | LIGHT |
| ATC-CD-302 | ATC | ATC-P3-PSYT-02 |  |  | Crusher Divider |  | QINGDAO YAOXIN | YXPS-125X150 |  |  | 2022 |  |  | LIGHT |
| ATC-CD-303 | ATC | ATC-P3-PSYT-03 |  |  | Crusher Divider |  | QINGDAO YAOXIN | YXPS-125X150 |  |  | 2022 |  |  | LIGHT |
| ATC-CD-304 | ATC | ATC-P3-PSYT-04 |  |  | Crusher Divider |  | QINGDAO YAOXIN | YXPS-125X150 |  |  | 2022 |  |  | LIGHT |
| ATC-CD-305 | ATC | ATC-P3-PSYT-05 |  |  | Crusher Divider |  | QINGDAO YAOXIN | YXPS-125X150 |  |  | 2022 |  |  | LIGHT |


### `WBN_DATABASE.dbo.HRM_CONTRACT_EQUIPMENT` — 198 rows, 8 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| ROAD | nchar | 20 | True |
| SECTION | nvarchar | 100 | True |
| CONTRACTOR | nchar | 20 | True |
| FLEET | nchar | 20 | True |
| UNIT_TYPE | nvarchar | 100 | True |
| DETAIL | nchar | 20 | True |
| QUANTITY | int | 4 | True |


**Sample (20 rows):**

| ID | ROAD | SECTION | CONTRACTOR | FLEET | UNIT_TYPE | DETAIL | QUANTITY |
|---|---|---|---|---|---|---|---|
| 24 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca 20T   | 1 |
| 25 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca ?     | 0 |
| 26 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | DT |  | 3 |
| 27 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | GRADER |  | 1 |
| 28 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | COMPACTOR |  | 1 |
| 29 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | WT |  | 1 |
| 30 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | EXCA | Exca 20T   | 0 |
| 31 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | EXCA | Exca ?     | 0 |
| 32 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | DT |  | 0 |
| 33 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | GRADER |  | 0 |
| 34 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | COMPACTOR |  | 0 |
| 35 | GOMDI      | GOMDI KM3.7-KM3.8 | RIM        | RIM F2     | WT |  | 0 |
| 36 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | EXCA | Exca 20T   | 1 |
| 37 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | EXCA | Exca ?     | 0 |
| 38 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | DT |  | 3 |
| 39 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | GRADER |  | 1 |
| 40 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | COMPACTOR |  | 1 |
| 41 | BLB        | BLB KM2.5-KM5.7 | RIM        | RIM F2     | WT |  | 1 |
| 42 | BLB        | BLB KM5.7-KM10 | RIM        | RIM F3     | EXCA | Exca 20T   | 1 |
| 43 | BLB        | BLB KM5.7-KM10 | RIM        | RIM F3     | EXCA | Exca ?     | 0 |


### `WBN_DATABASE.dbo.CONTRACTOR FOLLOW UP` — 131,768 rows, 25 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| ID | int | 4 | False |
| Date | date | 3 | False |
| Contractor | nvarchar | 510 | True |
| Activity | nvarchar | 510 | True |
| Equipment | nvarchar | 510 | True |
| Brand | nvarchar | 510 | True |
| Model | nvarchar | 510 | True |
| Capacity | nvarchar | 510 | True |
| Quantity | float | 8 | True |
| PA | float | 8 | True |
| Target Fleet | float | 8 | True |
| RFU | float | 8 | True |
| Breakdown | float | 8 | True |
| Act PA | float | 8 | True |
| Running Average | float | 8 | True |
| Stand by | float | 8 | True |
| Actual Utilization | float | 8 | True |
| Manpower Factor | float | 8 | True |
| Manpower Budget | float | 8 | True |
| Manpower | float | 8 | True |
| Manpower On Site | float | 8 | True |
| Hiring | float | 8 | True |
| Eq class | nvarchar | 510 | True |
| DT Reclaiming | float | 8 | True |
| DT OTHER | float | 8 | True |


**Sample (20 rows):**

| ID | Date | Contractor | Activity | Equipment | Brand | Model | Capacity | Quantity | PA | Target Fleet | RFU | Breakdown | Act PA | Running Average | Stand by | Actual Utilization | Manpower Factor | Manpower Budget | Manpower | Manpower On Site | Hiring | Eq class | DT Reclaiming | DT OTHER |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 82044 | 2024-10-01 | CKB | HAULING | DT Sachman | Shacman | X3000 | 43 | 30.0 | 0.85 | 26.0 | 19.0 | 11.0 | 0.6333333333333333 | 13.0 | 6.0 | 0.6842105263157895 | 2.7387715725158115 | 69.83867509915319 | 57.0 |  | -12.838675099153193 | DT HAULING |  |  |
| 82045 | 2024-10-01 | CKB | HAULING | Exca 30 Ton | Cat | CAT 330 | 30 | 1.0 | 0.9 | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 | 0.0 | 1.0 | 2.7387715725158115 | 2.0 | 3.0 |  | 1.0 | EXC HAULING |  |  |
| 82046 | 2024-10-01 | CKB | HAULING | Exca 20 Ton | Sany | SY215C | 20 | 1.0 | 0.9 | 1.0 | 1.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 2.7387715725158115 | 2.4648944152642303 | 3.0 |  | 0.5351055847357697 | EXC HAULING |  |  |
| 82047 | 2024-10-01 | GMG  | HAULING | DT Hino 25T | HINO | FM 280JD | 25 | 35.0 | 0.89 | 32.0 | 18.0 | 17.0 | 0.5142857142857142 | 7.0 | 11.0 | 0.3888888888888889 | 2.7387715725158115 | 85.31273448386753 | 28.0 |  | -57.31273448386753 | DT HAULING |  |  |
| 82048 | 2024-10-01 | GMG  | HAULING | DT Volvo 30T | VOLVO | VOLVO 6 X 4 | 30 | 67.0 | 0.9 | 61.0 | 49.0 | 18.0 | 0.7313432835820896 | 20.0 | 29.0 | 0.40816326530612246 | 2.7387715725158115 | 165.14792582270346 | 55.0 |  | -110.14792582270346 | DT HAULING |  |  |
| 82049 | 2024-10-01 | GMG  | HAULING | DT Sachman 30T | Sachman | FF 300 | 30 | 20.0 | 0.9 | 18.0 | 19.0 | 1.0 | 0.95 | 18.0 | 1.0 | 0.9473684210526315 | 2.7387715725158115 | 49.29788830528461 | 35.0 |  | -14.297888305284609 | DT HAULING |  |  |
| 82050 | 2024-10-01 | GMG  | HAULING | DT HONGYAN 50T | Hongyan | KINKAN 380 | 50 | 10.0 | 0.9 | 9.0 | 7.0 | 3.0 | 0.7 | 5.0 | 2.0 | 0.7142857142857143 | 2.7387715725158115 | 24.648944152642304 | 20.0 |  | -4.648944152642304 | DT HAULING |  |  |
| 82051 | 2024-10-01 | GMG  | HAULING | Exca 30 Ton |  |  |  | 7.0 | 0.9 | 7.0 | 5.0 | 2.0 | 0.7142857142857143 | 3.0 | 2.0 | 0.6 | 2.7387715725158115 | 17.254260906849613 | 15.0 |  | -2.2542609068496127 | EXC HAULING |  |  |
| 82052 | 2024-10-01 | GMG  | HAULING | Exca 20 Ton |  |  |  | 7.0 | 0.9 | 7.0 | 7.0 | 0.0 | 1.0 | 0.0 | 7.0 | 0.0 | 2.7387715725158115 | 17.254260906849613 | 15.0 |  | -2.2542609068496127 | EXC HAULING |  |  |
| 82053 | 2024-10-01 | HJS | MINING | EX SANY 50T | SANY | SY500H | 50 | 13.0 | 0.8 | 11.0 | 11.0 | 2.0 | 0.8461538461538461 | 7.0 | 4.0 | 0.6363636363636364 | 2.7387715725158115 | 28.48322435416444 | 33.0 |  | 4.516775645835558 | EXC MINING |  |  |
| 82054 | 2024-10-01 | HJS | MINING | EX20 |  |  |  | 15.0 | 0.8 | 12.0 | 9.0 | 6.0 | 0.6 | 9.0 | 0.0 | 1.0 | 2.7387715725158115 | 32.865258870189734 | 39.0 |  | 6.134741129810266 |  |  |  |
| 82055 | 2024-10-01 | HJS | MINING | EX30 |  |  |  | 1.0 | 0.8 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2.7387715725158115 | 2.1910172580126495 | 4.0 |  | 1.8089827419873505 |  |  |  |
| 82056 | 2024-10-01 | HJS | MINING | Bulldozer |  |  |  | 11.0 | 0.8 | 9.0 | 7.0 | 4.0 | 0.6363636363636364 | 7.0 | 0.0 | 1.0 | 2.7387715725158115 | 24.101189838139142 | 23.0 |  | -1.1011898381391418 |  |  |  |
| 82057 | 2024-10-01 | HJS | MINING | ADT VOLVO 60T | VOLVO | A60H | 60 | 19.0 | 0.8 | 16.0 | 15.0 | 4.0 | 0.7894736842105263 | 15.0 | 0.0 | 1.0 | 2.7387715725158115 | 41.62932790224034 | 47.0 |  | 5.370672097759659 | ADT MINING |  |  |
| 82058 | 2024-10-01 | HJS | MINING | ADT VOLVO 40T | VOLVO | A40G | 40 | 25.0 | 0.8 | 20.0 | 14.0 | 11.0 | 0.56 | 12.0 | 2.0 | 0.8571428571428571 | 2.7387715725158115 | 54.77543145031623 | 58.0 |  | 3.2245685496837666 | ADT MINING |  |  |
| 82059 | 2024-10-01 | HJS | HAULING | EX30 |  |  |  | 6.0 | 0.8 | 5.0 | 2.0 | 4.0 | 0.3333333333333333 | 2.0 | 0.0 | 1.0 | 2.7387715725158115 | 13.146103548075898 | 15.0 |  | 1.8538964519241024 | EXC HAULING |  |  |
| 82060 | 2024-10-01 | HJS | HAULING | EX20 |  |  |  | 6.0 | 0.8 | 5.0 | 5.0 | 1.0 | 0.8333333333333334 | 5.0 | 0.0 | 1.0 | 2.7387715725158115 | 13.146103548075898 | 16.0 |  | 2.8538964519241024 | EXC HAULING |  |  |
| 82061 | 2024-10-01 | HJS | HAULING | DT ISUZU 20T | ISUZU | GIGA FVZ | 20 | 123.0 | 0.8 | 99.0 | 80.0 | 43.0 | 0.6504065040650406 | 64.0 | 16.0 | 0.8 | 2.7387715725158115 | 287.5710151141602 | 251.0 |  | -36.57101511416022 | DT HAULING |  | 13.0 |
| 82062 | 2024-10-01 | HJS | PIT SERVICE | EX30 |  |  |  | 2.0 | 0.8 | 2.0 | 1.0 | 1.0 | 0.5 | 1.0 | 0.0 | 1.0 | 2.7387715725158115 | 4.382034516025299 | 4.0 |  | -0.3820345160252989 |  |  |  |
| 82063 | 2024-10-01 | HJS | PIT SERVICE | EX20 |  |  |  | 2.0 | 0.8 | 2.0 | 2.0 | 0.0 | 1.0 | 2.0 | 0.0 | 1.0 | 2.7387715725158115 | 4.382034516025299 | 4.0 |  | -0.3820345160252989 |  |  |  |


### `FMS_DB.dbo.FMS_EQUIPMENTS` — 1,435 rows, 7 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| FETCH_DATE | datetime | 8 | True |
| truckId | nvarchar | 100 | False |
| orgName | nvarchar | 100 | True |
| plateNumber | nvarchar | 100 | True |
| orgId | bigint | 8 | True |
| imei | bigint | 8 | True |
| active | nvarchar | 100 | True |


**Sample (20 rows):**

| FETCH_DATE | truckId | orgName | plateNumber | orgId | imei | active |
|---|---|---|---|---|---|---|
| 2026-08-04 14:44:30.330000 | 6916297240046994306 | RIM??? E ?? | K977 | 7190741736405205894 | 131064219063978 | YES |
| 2026-08-04 14:44:30.330000 | 6916344653700925698 | RIM??? A ?? | K984 | 7190739726259849477 | 131064219064862 | YES |
| 2026-05-14 14:44:30.313000 | 6921009760640961159 | RIM??? C ?? | K523 | 7190740880934963462 | 131064219065221 | NO |
| 2026-04-12 14:44:23.520000 | 6922135043012034832 | RIM??? B ?? | K562 | 7190740352016450440 | 107015291860264 | NO |
| 2026-08-04 14:44:30.330000 | 6922135043045589259 | RIM??? E ?? | K565 | 7190741736405205894 | 131064219064892 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589260 | RIM??? B ?? | K566 | 7190740352016450440 | 131064219063675 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589262 | RIM??? B ?? | K568 | 7190740352016450440 | 131064219063650 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589263 | RIM??? B ?? | K569 | 7190740352016450440 | 131064219065257 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589264 | RIM??? B ?? | K570 | 7190740352016450440 | 131064219064388 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589265 | RIM??? B ?? | K571 | 7190740352016450440 | 131064219066140 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589267 | RIM??? B ?? | K573 | 7190740352016450440 | 131064219064998 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589271 | RIM??? E ?? | K577 | 7190741736405205894 | 131064219064376 | YES |
| 2026-07-08 14:44:28.047000 | 6922135043045589272 | RIM??? A ?? | K578 | 7190739726259849477 | 131064219066116 | NO |
| 2026-08-04 14:44:30.330000 | 6922135043045589273 | RIM??? B ?? | K579 | 7190740352016450440 | 131064219063509 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043045589274 | RIM??? B ?? | K580 | 7190740352016450440 | 131064219063981 | YES |
| 2026-05-14 14:44:30.313000 | 6922135043045589275 | RIM??? C ?? | K689 | 7190740880934963462 | 131064219065823 | NO |
| 2026-04-12 14:44:23.520000 | 6922135043079143690 | RIM??? B ?? | K691 | 7190740352016450440 | 131064219065509 | NO |
| 2026-08-04 14:44:30.330000 | 6922135043079143691 | RIM??? B ?? | K692 | 7190740352016450440 | 131064219064299 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043079143692 | RIM??? B ?? | K693 | 7190740352016450440 | 131064219066029 | YES |
| 2026-08-04 14:44:30.330000 | 6922135043112698126 | RIM??? A ?? | K723 | 7190739726259849477 | 131064219066187 | YES |


### `FMS_DB.dbo.FMS_TRUCK_ASSIGNMENTS` — 408 rows, 10 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| PLAN_DATE | date | 3 | True |
| SHIFT | float | 8 | True |
| TRUCK | nvarchar | 100 | True |
| PILE | nvarchar | 200 | True |
| EXCAVATOR | nvarchar | 200 | True |
| PIT | nvarchar | 100 | True |
| MATERIAL | nvarchar | 100 | True |
| DESTINATION | nvarchar | 400 | True |
| IMPORTED_AT | datetime | 8 | True |
| IMPORTED_BY | nvarchar | 200 | True |


**Sample (20 rows):**

| PLAN_DATE | SHIFT | TRUCK | PILE | EXCAVATOR | PIT | MATERIAL | DESTINATION | IMPORTED_AT | IMPORTED_BY |
|---|---|---|---|---|---|---|---|---|---|
| 2026-01-07 | 1.0 | R707 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.717000 | t |
| 2026-01-07 | 1.0 | R708 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.767000 | t |
| 2026-01-07 | 1.0 | R938 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.813000 | t |
| 2026-01-07 | 1.0 | R939 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.853000 | t |
| 2026-01-07 | 1.0 | R940 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.900000 | t |
| 2026-01-07 | 1.0 | R941 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.950000 | t |
| 2026-01-07 | 1.0 | R943 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:45.983000 | t |
| 2026-01-07 | 1.0 | R944 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.020000 | t |
| 2026-01-07 | 1.0 | R945 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.070000 | t |
| 2026-01-07 | 1.0 | R946 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.120000 | t |
| 2026-01-07 | 1.0 | R947 | KRENE.I.3291 | E042 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.157000 | t |
| 2026-01-07 | 1.0 | R279 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.197000 | t |
| 2026-01-07 | 1.0 | R280 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.233000 | t |
| 2026-01-07 | 1.0 | R282 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.267000 | t |
| 2026-01-07 | 1.0 | R284 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.303000 | t |
| 2026-01-07 | 1.0 | R297 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.337000 | t |
| 2026-01-07 | 1.0 | R316 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.383000 | t |
| 2026-01-07 | 1.0 | R685 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.437000 | t |
| 2026-01-07 | 1.0 | R689 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.470000 | t |
| 2026-01-07 | 1.0 | R701 | KRENE.I.3293 | E377 | KRENE | SAP | POS 12 | 2026-07-08 15:53:46.513000 | t |


### `FMS_DB.dbo.FMS_UNIT_INSTALLED` — 1,225 rows, 4 columns


**Schema:**

| column | type | max_length | nullable |
|---|---|---|---|
| PLATE | nvarchar | 120 | False |
| ORG | nvarchar | 240 | True |
| FIRST_TS | bigint | 8 | False |
| SEEDED | bit | 1 | False |


**Sample (20 rows):**

| PLATE | ORG | FIRST_TS | SEEDED |
|---|---|---|---|
| A042 | RIM??????(BIRIBIRI) | 0 | True |
| A843 | RIM??? K ?? | 0 | True |
| A844 | RIM??? K ?? | 0 | True |
| A864 | RIM??? K ?? | 0 | True |
| A865 | RIM??????(BIRIBIRI) | 0 | True |
| A867 | RIM??????? | 0 | True |
| A875 | RIM??????(BIRIBIRI) | 0 | True |
| A878 | RIM??????? | 1785390271913 | False |
| B279 | RIM??? K ?? | 0 | True |
| B280 | RIM??? K ?? | 0 | True |
| B282 | RIM??? K ?? | 0 | True |
| B284 | RIM??? K ?? | 0 | True |
| B286 | RIM??? K ?? | 0 | True |
| B287 | RIM??? C ?? | 0 | True |
| B290 | RIM??? E ?? | 0 | True |
| B292 | RIM??? K ?? | 0 | True |
| B293 | RIM??? C ?? | 0 | True |
| B294 | RIM??????(16km) | 0 | True |
| B295 | RIM??? K ?? | 0 | True |
| B296 | RIM??? K ?? | 0 | True |


## 5. Views related to fuel / equipment (Step 9)


### WBN_DATABASE — 16 matching views


<details><summary><code>dbo.EQ_STATUS_WATER_MANAGEMENT</code></summary>


```sql




CREATE VIEW [dbo].[EQ_STATUS_WATER_MANAGEMENT] AS SELECT [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]
      ,[ID_EQ]

     
      ,[LOCATION]
      ,[LOCATION_DETAILS]
	  ,PART.Part AS [SP_ID]



      ,[WORKING_HOURS]
      ,[STBY_HOURS]

      ,[BD_HOURS]
  ,[PM_HOURS]
   FROM (SELECT 
      [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]

      ,[ID_EQ]
 
      ,COALESCE(saLOCATION,[LOCATION]) AS [LOCATION]
	  ,saLOCATION_DETAILS AS LOCATION_DETAILS
      ,SUM(COALESCE([WORKING_HOURS],0)) AS [WORKING_HOURS]
      ,SUM(COALESCE([STBY_HOURS],0)) AS [STBY_HOURS]

      ,SUM(COALESCE([BD_HOURS],0)) AS [BD_HOURS]

      ,SUM(COALESCE([PM_HOURS],0)) AS [PM_HOURS]

  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS] LEFT JOIN (SELECT DISTINCT [DATE] AS saDATE,[SHIFT] AS saSHIFT,CONTRACTOR AS saCONTRACTOR,[ACTIVITY] AS saACTIVITY,ID_EQ AS saID_EQ,[LOCATION] AS saLOCATION,LOCATION_DETAILS as saLOCATION_DETAILS  FROM  [EQUIPMENTS_STATUS]) AS SA ON [saDATE]=[DATE] AND [saCONTRACTOR]=[saCONTRACTOR] AND [saSHIFT]=[SHIFT] AND [saID_EQ]=[ID_EQ] 
  WHERE ACTIVITY='WATER MANAGEMENT' OR saACTIVITY='WATER MANAGEMENT'
  GROUP BY [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]

      ,[ID_EQ]
 
      ,COALESCE(saLOCATION,[LOCATION])
	  ,saLOCATION_DETAILS

	UNION ALL
	SELECT 
      [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]
      ,[ID_EQ]

     
      ,[LOCATION]
      ,REPLACE([LOCATION_DETAILS],'?','')


      ,COALESCE([WORKING_HOURS],HOUR_METER_END-HOUR_METER_START) AS [WORKING_HOURS]
      ,COALESCE([STBY_HOURS],0) AS [STBY_HOURS]

      ,COALESCE([BD_HOURS],0) AS [BD_HOURS]
  ,NULL
  
  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_STATUS] LEFT JOIN (SELECT DISTINCT [DATE] AS seDATE,[SHIFT] AS seSHIFT,CONTRACTOR AS seCONTRACTOR,ID_EQ AS seID_EQ  FROM  [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS]) AS SE ON [seDATE]=[DATE] AND [seCONTRACTOR]=[seCONTRACTOR] AND [seSHIFT]=[SHIFT] AND [seID_EQ]=[ID_EQ] 
  WHERE ACTIVITY='WATER MANAGEMENT' AND seCONTRACTOR IS NULL) as SUB 
  OUTER APPLY [dbo].[SplitPart_CONTAINS](COALESCE([LOCATION],'') +' '+ COALESCE([LOCATION_DETAILS],''),' ','SP') AS PART

```


</details>


<details><summary><code>dbo.EQUIPMENT_NEW_ID</code></summary>


```sql
CREATE VIEW [EQUIPMENT_NEW_ID] AS 
SELECT [Company]
      ,[Vender Clasification]
      ,[Brand]
      ,REPLACE(REPLACE([Model], CHAR(13), ' '), CHAR(10), ' ')[Model]
      ,[Equipment_Size]
      ,[Finance_Status]
	  ,[Equipment_Type]
	  ,[TYPE_ACR]
	  ,[OEM_PIN ]
      ,[ID] AS [OLD_ID]
	  ,Lett.Letters [OLD_ID_LETTERS]
	  ,TRY_CAST(Numb.Numbers AS INT) AS  [OLD_ID_DIGIT] 
      
	  ,TRY_CAST(COALESCE(cNUMBER,'')+Numb.Numbers AS INT) AS NEW_DIGIT
	  ,CONCAT([COMPANY],'-',[TYPE_ACR],'-',TRY_CAST(COALESCE(cNUMBER,'')+Numb.Numbers AS INT)) AS NEW_ID
 
      
    
  FROM [SAFETY_ENVIRO].[dbo].[EQUIPMENTS]
  OUTER APPLY [WBN_DATABASE].[dbo].[getSTRING_NUMBERS]([ID]) as Numb
  OUTER APPLY [WBN_DATABASE].[dbo].[getSTRING_LETTERS]([ID]) as Lett
  LEFT JOIN (VALUES ('Air Compressor','ACO'),
('ADT','ADT'),
('Bulldozer','BD'),
('Compactor','CP'),
('Crane Truck','CT'),
('Dump Truck','DT'),
('Dump Truck EV','EDT'),
('Excavator','EX'),
('Excavator Long Arm','EX'),
('Rock Breaker','EX'),
('Wheel Excavator','EX'),
('Fuel Truck','FT'),
('Motor Grader','GD'),
('Grader','GD'),
('Generator','GN'),
('Lifting Support','LIF'),
('Light Vehicle','LV'),
('Manhaul','MH'),
('Drill Rig','RIG'),
('Slurry Truck','SLT'),
('Flatbed Truck','ST'),
('Grease Truck','GT'),
('Lube Truck','GT'),
('Mobil Truck','ST'),
('Service Truck','ST'),
('Emergency Repair Truck','ST'),
('Lighting Tower','TL'),
('Tower Lamp','TL'),
('Wrecker','TT'),
('Tyre Handler','TYR'),
('Tyre Service','TYR'),
('Compactor Vibro','VR'),
('Loader','WL'),
('Wheel Loader','WL'),
('Water Pump','WP'),
('Water Truck','WT')) AS t([TYPE],TYPE_ACR) ON [TYPE]=[Equipment_Type]
LEFT JOIN ( VALUES
('RIM','EX','E','1'),
('RIM','EX','W','2'),
('RIM','EX','X','3'),
('RIM','EDT','L','4'),
('RIM','EDT','R','7'),
('RIM','EDT','N','6'),
('RIM','DT','A','1'),
('RIM','DT','B','2'),
('RIM','DT','K','3'),
('RIM','DT','L','4'),
('RIM','DT','M','5'),
('RIM','DT','N','6'),
('RIM','DT','R','7')) as c([cCONTRACTOR],cTYPE_ACR,FRONTLETTER,cNUMBER) ON TYPE_ACR=cTYPE_ACR AND cCONTRACTOR=COMPANY AND LEFT(ID,1)=FRONTLETTER
  WHERE COMPANY IN ('PPP','HJS','RIM','STM','CKB','SSS','GMG','SMA')

```


</details>


<details><summary><code>dbo.EQUIPMENT_STATUS_FULL</code></summary>


```sql









CREATE VIEW [dbo].[EQUIPMENT_STATUS_FULL]
AS
SELECT [prodDate] AS [DATE]
	,shiftCode AS [SHIFT]
	,MAX(activity) AS ACTIVITY
	,OEE.[contractor] AS [CONTRACTOR]
	,EQ.TYPE AS UNIT_TYPE
	,EQ.MANUFACTURER
	,CASE WHEN EQ.BUILD_YEAR = 0 THEN NULL ELSE EQ.BUILD_YEAR END AS BUILD_YEAR
	,[unitId_cleaned] AS UNIT_ID
	,SUM([workHours]) AS WORKING_HOURS
	,SUM([standby]) AS STBY_HOURS
	,SUM([uschDowntime]) AS BD_HOURS
	,SUM([schDowntime]) AS PM_HOURS
	,SUM([operatingHours]) AS OPERATING_HOURS
FROM [WBN_DATABASE].[dbo].[OEEDB_AUDB] AS OEE

LEFT OUTER JOIN WBN_DATABASE.dbo.EQUIPMENTS AS EQ ON OEE.[unitId_cleaned] = EQ.ID_EQ AND OEE.CONTRACTOR = EQ.[contractor]

GROUP BY [prodDate]
	,shiftCode
	,OEE.[contractor]
	,[unitId_cleaned]
	,EQ.TYPE
	,EQ.MANUFACTURER
	,EQ.BUILD_YEAR




```


</details>


<details><summary><code>dbo.EQUIPMENT_STATUS_WORKING_HOURS</code></summary>


```sql

CREATE VIEW [dbo].[EQUIPMENT_STATUS_WORKING_HOURS] AS 
SELECT 
	[DATE]
	,[SHIFT]
	,CONTRACTOR
	,STATUS
	,ACTIVITY
	, EQ.TYPE AS UNIT_TYPE

    ,STA.[ID_EQ] AS [UNIT_ID]
	,CASE WHEN STATUS='PREVENTIVE MAINTENANCE' THEN 12-([HOUR_METER_END]-[HOUR_METER_START]) END AS SCH
	,CASE WHEN STATUS='BREAKDOWN' THEN 12-([HOUR_METER_END]-[HOUR_METER_START]) END AS UNSCH
	,CASE WHEN STATUS='STAND BY' OR STATUS='RFU' THEN 12-([HOUR_METER_END]-[HOUR_METER_START]) END AS [STAND BY]
	,[HOUR_METER_END]-[HOUR_METER_START] AS [WORKING HOURS]
	,12 AS [OPERATING HOURS]
	,CASE WHEN STATUS='STAND BY' OR STATUS='RFU' THEN 12-([HOUR_METER_END]-[HOUR_METER_START]) END /12 AS STB_PROP

  FROM [WBN_DATABASE].[dbo].[w2_EQUIPMENTS_STATUS] AS STA
  LEFT OUTER JOIN
                 (SELECT CONTRACTOR AS eqCONTRACTOR, ID_EQ, TYPE, DIGIT, MANUFACTURER, MODEL
                 FROM    OEEDATABASE.dbo.EQUIPMENTS) AS EQ ON STA.ID_EQ = EQ.ID_EQ AND STA.CONTRACTOR = EQ.eqCONTRACTOR



```


</details>


<details><summary><code>dbo.EQUIPMENT_STATUS_WORKING_HOURS_2</code></summary>


```sql


CREATE VIEW [dbo].[EQUIPMENT_STATUS_WORKING_HOURS_2]
AS
SELECT [DATE]
      ,[SHIFT]
      ,[CONTRACTOR]
	  ,UNIT_TYPE
	  ,COUNT([UNIT_ID]) AS NB_UNITS
	  ,CASE WHEN STATUS IN ('RFU','STAND BY') THEN 'RFU' ELSE STATUS END AS STATUS
	  , ACTIVITY
      ,SUM([SCH]) AS [SCH HOURS]
      ,SUM([UNSCH]) AS [UNSCH HOURS]
      ,SUM([STAND BY]) AS [STAND BY HOURS]
      ,SUM([WORKING HOURS]) AS [WORKING HOURS]
      ,SUM([OPERATING HOURS]) AS [OPERATING HOURS]
	  ,SUM(CASE WHEN STATUS IN ('RFU','STAND BY') THEN STB_PROP END)/NULLIF(COUNT(CASE WHEN STATUS IN ('RFU','STAND BY') THEN UNIT_TYPE END),0)  AS STB_PROP
	  ,SUM(CASE WHEN STATUS IN ('RFU','STAND BY') THEN STB_PROP END) AS NB_STB_PROP
	  ,SUM(CASE WHEN STATUS IN ('RFU','STAND BY') and [STAND BY] = 12 THEN 1 END) AS NB_STB_FULL
  FROM [WBN_DATABASE].[dbo].[EQUIPMENT_STATUS_WORKING_HOURS]
 
  
  group by  [DATE]
      ,[SHIFT]
      ,[CONTRACTOR]
	  ,UNIT_TYPE
	  ,STATUS
	  , ACTIVITY
  
  

```


</details>


<details><summary><code>dbo.EQUIPMENTS_HOURLY_STATUS_COMPACT</code></summary>


```sql
CREATE  VIEW [dbo].[EQUIPMENTS_HOURLY_STATUS_COMPACT] AS

SELECT [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]
      ,[ACTIVITY]
      ,COUNT([ID_EQ]) AS [NB_UNIT] 
      ,[TYPE] as [UNIT_TYPE]
      ,[LOCATION]
      --,[LOCATION_DETAILS]
      --,[WORKING_HOURS]
      --,[STBY_HOURS]
      --,[BD_HOURS]
      --,[PM_HOURS]
      --,[TOTAL_HOURS]
      ,[STATUS]
  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS_SUMMARY]
  --where date = '2026-04-23' and ACTIVITY = 'MINING'
  --and TYPE = 'EXCAVATOR' and location = 'BLB'
  --and ID_EQ = 'ADT60' 
  --and shift = 2
  group by [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]
      ,[ACTIVITY]
      ,[TYPE]
      ,[LOCATION]
      --,[LOCATION_DETAILS]
      ,[STATUS]
  --order by ID_EQ, SHIFT
```


</details>


<details><summary><code>dbo.EQUIPMENTS_HOURLY_STATUS_DAILY</code></summary>


```sql







CREATE VIEW [dbo].[EQUIPMENTS_HOURLY_STATUS_DAILY] as
SELECT 
      EH.[CONTRACTOR]
      ,[DATE]
	  ,SHIFT
	  ,STATUS
     

      ,CASE WHEN [LOCATION] LIKE '%DUMP%' THEN 'REHANDLING' ELSE [ACTIVITY] END AS [ACTIVITY]
	  ,EH.ID_EQ
	  ,E.TYPE
	  --,CASE WHEN MAX(STATUS)='BREAKDOWN' OR SUM(BD_HOURS)>6 THEN 'BREAKDOWN' ELSE 'RFU' END AS STATUS

	  , 
			CASE
				WHEN [LOCATION] LIKE '%KRENE%' THEN 'KRENE'
				WHEN [LOCATION] LIKE '%HAULING ROAD%' THEN 'HAULING ROAD'
				WHEN [LOCATION] LIKE '%TOFU%' or [LOCATION] LIKE '%TF%' THEN 'TF'
				WHEN [LOCATION] LIKE '%KAORAHAI%' or [LOCATION] LIKE '%KR%'THEN 'KR'
				WHEN [LOCATION] LIKE '%BLB%' THEN 'BLB'
				WHEN [LOCATION] LIKE '%PARK%' THEN 'PARKING'
				WHEN [LOCATION] LIKE '%WORKSHOP%' THEN 'WORKSHOP'
				WHEN [LOCATION] LIKE '%LIM%DUMP%' THEN 'LIM DUMP'
				WHEN [LOCATION] LIKE '%SOIL%DUMP%' THEN 'SOIL DUMP'
				WHEN [LOCATION] LIKE '%WST%DUMP%' THEN 'WST DUMP'
				ELSE [LOCATION]
			END
		 AS [LOCATION]

      ,[LOCATION_DETAILS]
	  --,MAX(CONCAT(ISNULL([LOCATION]+' ',''),ISNULL(LOCATION_DETAILS,''))) AS [LOCATION_DETAIL]
      ,SUM([WORKING_HOURS]) [WORKING_HOURS]
      ,SUM([STBY_HOURS]) [STBY_HOURS]
	  ,SUM([BD_HOURS]) AS [BD_HOURS]
	  ,SUM([PM_HOURS]) AS [PM_HOURS]
  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS] AS EH LEFT JOIN EQUIPMENTS E ON E.ID_EQ=EH.ID_EQ AND E.CONTRACTOR=EH.CONTRACTOR
  WHERE DATE>='2025-08-01'
  GROUP BY EH.[CONTRACTOR]
      ,[DATE]
	  ,SHIFT
	  ,STATUS
     , [LOCATION]
	 ,[LOCATION_DETAILS]
      ,[ACTIVITY]
	  ,EH.ID_EQ
	  ,E.TYPE

```


</details>


<details><summary><code>dbo.EQUIPMENTS_HOURLY_STATUS_SUMMARY</code></summary>


```sql


CREATE VIEW [dbo].[EQUIPMENTS_HOURLY_STATUS_SUMMARY] as

SELECT  [CONTRACTOR]
      ,[DATE]
      ,[SHIFT]
      ,[ACTIVITY]
      ,[ID_EQ]
      ,TYPE
      ,[LOCATION]
      ,[LOCATION_DETAILS]
      ,[WORKING_HOURS]
      ,[STBY_HOURS]
      ,[BD_HOURS]
      ,[PM_HOURS]
      ,[TOTAL_HOURS]
      ,CASE 
           WHEN [WORKING_HOURS] >= [STBY_HOURS] 
                AND [WORKING_HOURS] >= [BD_HOURS] 
                AND [WORKING_HOURS] >= [PM_HOURS] THEN 'WORK'
           
           WHEN [STBY_HOURS] >= [WORKING_HOURS] 
                AND [STBY_HOURS] >= [BD_HOURS] 
                AND [STBY_HOURS] >= [PM_HOURS] THEN 'STAND BY'
           
           WHEN [BD_HOURS] >= [WORKING_HOURS] 
                AND [BD_HOURS] >= [STBY_HOURS] 
                AND [BD_HOURS] >= [PM_HOURS] THEN 'BREAKDOWN'
           
           ELSE 'PREVENTIVE MAINTENANCE'
       END AS [STATUS]
        --[WORKING_HOURS]+[STBY_HOURS]+[BD_HOURS]+[PM_HOURS]

FROM 
(SELECT [CONTRACTOR]
      ,[DATE]
      ,SHIFT
      ,[ACTIVITY]
      ,[ID_EQ]
      ,TYPE
      ,[STATUS]
      ,[LOCATION]
      ,[LOCATION_DETAILS]
      ,SUM([WORKING_HOURS]) OVER (Partition by [ID_EQ],DATE,SHIFT,[CONTRACTOR]) AS [WORKING_HOURS]
      ,SUM([STBY_HOURS]) OVER (Partition by [ID_EQ],DATE,SHIFT,[CONTRACTOR]) AS [STBY_HOURS]
      ,SUM([BD_HOURS]) OVER (Partition by [ID_EQ],DATE,SHIFT,[CONTRACTOR]) AS [BD_HOURS]
      ,SUM([PM_HOURS]) OVER (Partition by [ID_EQ],DATE,SHIFT,[CONTRACTOR]) AS [PM_HOURS]
      --,[STBY_HOURS]
      --,[BD_HOURS]
      ,ROW_NUMBER() OVER(PARTITION BY [ID_EQ],DATE,SHIFT,[CONTRACTOR] ORDER BY [WORKING_HOURS]+[STBY_HOURS]+[BD_HOURS]+[PM_HOURS] DESC) AS ROWWW
      ,SUM([WORKING_HOURS]+[STBY_HOURS]+[BD_HOURS]+[PM_HOURS]) OVER (Partition by [ID_EQ],DATE,SHIFT,[CONTRACTOR]) AS TOTAL_HOURS
  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS_DAILY]
   --where 
   --date = '2026-04-23' --and CONTRACTOR = 'STM' 
   --and [ID_EQ] = 'ADT2007' --and shift = 1
   --and ROWWW = 1
   --group by [CONTRACTOR]
   --   ,[DATE]
   --   ,SHIFT
   --   ,[ID_EQ]
   --order by [WORKING_HOURS]+[STBY_HOURS]+[BD_HOURS] 
   ) AS SUB

   WHERE ROWWW = 1 --and [WORKING_HOURS]+[STBY_HOURS]+[BD_HOURS]+[PM_HOURS] != 12
   --and date = '2026-04-23'
   --order by [ID_EQ], shift

```


</details>


<details><summary><code>dbo.EQUIPMENTS_STATUS_BREAKDOWN</code></summary>


```sql
CREATE VIEW [EQUIPMENTS_STATUS_BREAKDOWN] AS 
SELECT OEE.[DATE]
      ,OEE.[SHIFT]
	  ,OEE.[DATETIME]

      ,OEE.[CONTRACTOR]
      ,OEE.[UNIT_ID]
      ,OEE.[WORKING_HOURS]
      ,OEE.[STBY_HOURS]
      ,OEE.[BD_HOURS]
      ,OEE.[PM_HOURS]
      ,OEE.[OPERATING_HOURS]
	  ,LAG([DATETIME]) OVER (
        PARTITION BY OEE.UNIT_ID, OEE.CONTRACTOR 
        ORDER BY [DATETIME]
    ) AS PREV_DATETIME
	,CASE WHEN DATEDIFF(
        MINUTE,
        LAG([DATETIME]) OVER (
            PARTITION BY OEE.UNIT_ID, OEE.CONTRACTOR  
            ORDER BY [DATETIME]
        ),[DATETIME]
    ) <2000 THEN 'CONTINUE BREAKDOWN' ELSE 'NEW BREAKDOWN' END AS [STATUS_BD]

	  ,E.DIVISION
  FROM (SELECT CAST(CONCAT(CAST([DATE] AS DATE),CASE WHEN [SHIFT]=1 THEN ' 7:00:00' ELSE ' 19:00:00' END) AS DATETIME) AS [DATETIME]
      ,[DATE]
      ,[SHIFT]

      ,[CONTRACTOR]
      ,[UNIT_ID]
      ,[WORKING_HOURS]
      ,[STBY_HOURS]
      ,[BD_HOURS]
      ,[PM_HOURS]
      ,[OPERATING_HOURS] FROM [WBN_DATABASE].[dbo].[EQUIPMENT_STATUS_FULL]) AS OEE
 LEFT JOIN EQUIPMENTS AS E ON E.ID_EQ=OEE.UNIT_ID
 where bd_hours>=6 and division='MINING' and date>='2025-01-01'
```


</details>


<details><summary><code>dbo.MINING_EQUIPMENTS</code></summary>


```sql
CREATE VIEW [MINING_EQUIPMENTS] AS
SELECT DISTINCT [DATE],EH.[CONTRACTOR]
   
      ,[ORIGIN_AREA]

      ,[TRUCK_ID] AS ID_EQ
	  ,[TYPE]
	  ,[MODEL]
      ,[CAPACITY]
	  ,[DIVISION]
 


  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_ACTIVITIES] EH INNER JOIN EQUIPMENTS AS E  ON EH.[TRUCK_ID]=E.ID_EQ AND EH.CONTRACTOR=E.CONTRACTOR
  where DATE>='2025-09-01' AND ACTIVITY IN ('MINING','LAMINATING') AND RIT>1
  UNION ALL 
  SELECT DISTINCT [DATE],EH.[CONTRACTOR]
   
      ,[ORIGIN_AREA]

   
 
      ,[EXCAVATOR_ID]
	  ,[TYPE]
	  ,[MODEL]
      ,[CAPACITY]
	  ,[DIVISION]

  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_ACTIVITIES] EH INNER JOIN EQUIPMENTS AS E  ON EH.[EXCAVATOR_ID]=E.ID_EQ AND EH.CONTRACTOR=E.CONTRACTOR
  where DATE>='2025-09-01' AND ACTIVITY IN ('MINING','LAMINATING') AND RIT>1

  UNION ALL
  SELECT DISTINCT 
      
      [DATE]
	  ,EH.[CONTRACTOR]
	   ,[LOCATION]


      ,EH.[ID_EQ]
	  ,[TYPE]
	  ,[MODEL]
      ,[CAPACITY]
	  ,[DIVISION]

     
 
  FROM [WBN_DATABASE].[dbo].[EQUIPMENTS_HOURLY_STATUS] AS EH INNER JOIN EQUIPMENTS AS E  ON EH.ID_EQ=E.ID_EQ AND EH.CONTRACTOR=E.CONTRACTOR
  WHERE TYPE='BULLDOZER' AND DATE>='2025-09-01'  and WORKING_HOURS>0.1

```


</details>


<details><summary><code>dbo.OEE_HAULAGE_WMT_KM</code></summary>


```sql




CREATE VIEW [dbo].[OEE_HAULAGE_WMT_KM] AS 
SELECT  H.[DATE]
      ,H.[SHIFT]
      ,H.[CONTRACTOR]
      ,H.[ACTIVITY]
      ,H.[MATERIAL]

      ,H.[ORIGIN_PIT]
      ,H.[ORIGIN_AREA]
      ,H.[ORIGIN_ID]
      ,H.[DESTINATION_AREA]
      ,H.[DESTINATION_ID]
	  ,H.[WB_ID]
	  ,SUM([WORKING_HOURS]) AS [WORKING_HOURS]
      ,SUM([STBY_HOURS]) AS [STBY_HOURS]
      ,SUM([BD_HOURS]) AS [BD_HOURS]
      ,SUM([OPERATING_HOURS]) AS [OPERATING_HOURS]
      ,SUM(H.[RIT]) AS [RIT]
	  ,AVG(KM.[KM]) AS [KM]
      ,SUM(H.[WMT]) AS [WMT]
	  ,SUM([BY].[RIT_PER_DT])  AS RIT_PER_DT
	  ,SUM((CAST([RIT] AS FLOAT)/[BY].[RIT_PER_DT]))  AS [NB_DT]
      

FROM [HAULAGE_CLEAN]  AS H
LEFT JOIN [HAULAGE_BY_CONTRACTOR_TRUCK] AS [BY] ON [BY].[DATE] = H.[DATE] AND [BY].[SHIFT] = H.[SHIFT] AND [BY].CONTRACTOR = H.CONTRACTOR AND [BY].[TRUCK_ID] = H.[TRUCK_ID]
LEFT JOIN [EQUIPMENT_STATUS_FULL] AS STA ON STA.CONTRACTOR=H.CONTRACTOR AND STA.DATE=H.DATE AND STA.SHIFT = H.SHIFT AND STA.UNIT_ID=H.TRUCK_ID
LEFT JOIN (SELECT [ORIGIN]
      ,[DESTINATION]
 
      ,AVG([DISTANCE GROSS (KM)]) AS KM 
 
  FROM [WBN_DATABASE].[dbo].[DISPATCH ROADS] 
  GROUP BY [ORIGIN]
      ,[DESTINATION]) AS KM ON KM.ORIGIN=H.ORIGIN_PIT AND KM.DESTINATION=H.DESTINATION_AREA
	GROUP BY H.[DATE]
      ,H.[SHIFT]
      ,H.[CONTRACTOR]
      ,H.[ACTIVITY]
      ,[MATERIAL]

      ,[ORIGIN_PIT]
      ,[ORIGIN_AREA]
      ,[ORIGIN_ID]
      ,[DESTINATION_AREA]
      ,[DESTINATION_ID]
	  ,[WB_ID]

```


</details>


<details><summary><code>dbo.OEE_MINING_FULL</code></summary>


```sql








CREATE VIEW [dbo].[OEE_MINING_FULL]
AS
SELECT P.[CONTRACTOR]
,C.[YEAR]
,C.[MONTH]
,C.[WEEK]
	,P.[DATE]
	,P.[SHIFT]
	,P.[UNIT_TYPE]
	,CASE WHEN P.[UNIT_TYPE]='EXCAVATOR' THEN 3.3*3.5 ELSE 3.3 END AS TARGET_TRIP_HOUR
	,P.[UNIT_ID]
	,EQ.ID AS UNIT_ID_FULL
	,EQ.CAPACITY
	,EQ.[TYPE] AS UNIT_TYPE2
	,P.[ACTIVITY]
	,P.[PIT]
	,P.[DISTANCE]
	,P.[RIT]
	,P.[RIT_SAP]
	,P.[RIT_LIM]
	,P.[RIT_WST]
	,P.[TMM]
	,P.[WMT_SAP]
	,P.[WMT_LIM]
	,P.[WMT_WST]
	,E.[WORKING_HOURS]
	,E.[STBY_HOURS]
	,E.[BD_HOURS]
	,E.[OPERATING_HOURS]
FROM (
	SELECT [CONTRACTOR]
		,[DATE]
		,[SHIFT]
		,[UNIT_TYPE]
		,[UNIT_ID]
		,MAX([ACTIVITY_TYPE]) AS ACTIVITY
		,MAX([PIT]) AS [PIT]
		,SUM([DISTANCE] * RIT) AS [DISTANCE]
		,SUM([RIT]) AS [RIT]
		,SUM(CASE WHEN MATERIAL IN (
						'SAP'
						,'WCO'
						) THEN [RIT] END) AS RIT_SAP
		,SUM(CASE WHEN MATERIAL = 'LIM' THEN [RIT] END) AS RIT_LIM
		,SUM(CASE WHEN MATERIAL NOT IN (
						'LIM'
						,'SAP'
						,'WCO'
						) THEN [RIT] END) AS RIT_WST
		,SUM([RIT] * [TF]) AS TMM
		,SUM(CASE WHEN MATERIAL IN (
						'SAP'
						,'WCO'
						) THEN [RIT] * [TF] END) AS WMT_SAP
		,SUM(CASE WHEN MATERIAL = 'LIM' THEN [RIT] * [TF] END) AS WMT_LIM
		,SUM(CASE WHEN MATERIAL NOT IN (
						'LIM'
						,'SAP'
						,'WCO'
						) THEN [RIT] * [TF] END) AS WMT_WST
	FROM [WBN_DATABASE].[dbo].[PRODUCTION_PIT_HOURLY_FULL]
	GROUP BY [CONTRACTOR]
		,[DATE]
		,[SHIFT]
		,[UNIT_TYPE]
		,[UNIT_ID]
	) AS P
LEFT JOIN [EQUIPMENT_STATUS_FULL] AS E ON E.[DATE] = P.[DATE]
	AND E.[SHIFT] = P.[SHIFT]
	AND E.[UNIT_ID] = P.[UNIT_ID]
	AND E.[CONTRACTOR] = P.[CONTRACTOR]

LEFT JOIN Calendar_For_Exploitation AS C ON C.[DATE]=P.[DATE]
LEFT JOIN [EQUIPMENTS] AS EQ ON EQ.ID_EQ=P.UNIT_ID AND EQ.CONTRACTOR=P.CONTRACTOR

```


</details>


<details><summary><code>dbo.OEE_MINING_NEW</code></summary>


```sql


CREATE VIEW [dbo].[OEE_MINING_NEW] AS
SELECT
      wh.[CONTRACTOR]
      ,[ID_EQ]
      ,[TYPE]
      ,[CAPACITY]
	  ,CASE WHEN TYPE ='EXCAVATOR' THEN( CASE WHEN CAPACITY >50 THEN 600 else 300 end ) else (CASE when  CAPACITY >50 THEN 200 else 100 end) end as [PROD_per_ HOUR]
      ,TYPE+CAST(CAPACITY AS NVARCHAR(4)) AS [EQ_CLASS]
	  ,DIVISION
	  ,DIVISION AS [DIVISION GROUP]
	  ,SCH/12 AS SCH
	  ,UNSCH/12 AS UNSCH_DT
	  ,[STAND BY]/12 as [STBY]
	  ,[WORKING HOURS]/12 as [WORKING HOURS]
	  ,[prodDate]
      ,wh.[SHIFT]
      ,[timeGroup]
      ,p.[activity]
      ,[PIT]
      ,[subpit]
      ,[RIT]
      ,[RIT_SAP]
      ,[RIT_RSAP]
      ,[RIT_LIM]
      ,[RIT_WST]
      ,[RIT_TS]
	  ,YEAR
	  ,MONTH
	  ,WEEK
     
  FROM [WBN_DATABASE].[dbo].[w2_EQUIPMENTS] as e
  RIGHT JOIN [EQUIPMENT_STATUS_WORKING_HOURS] as wh ON e.CONTRACTOR=wh.CONTRACTOR and e.ID_EQ=wh.UNIT_ID
  left join  [PRODUCTION_PIT_BY_EQ_HOUR]  as p on p.CONTRACTOR=wh.CONTRACTOR and p.UNIT_ID=wh.UNIT_ID and p.prodDATE=wh.DATE and p.SHIFT=wh.SHIFT
  left join Calendar_For_Exploitation as c on c.DATE=wh.DATE
  where [prodDate] is not null 

```


</details>


<details><summary><code>dbo.PLAN_DAY_WORKS_CLEAN</code></summary>


```sql



CREATE VIEW [dbo].[PLAN_DAY_WORKS_CLEAN] AS 
SELECT [DATE]
 
      ,[ACTIVITY]
      ,[STATUS]
      ,[AREA]
      ,[SECTION_ROAD]
	  ,[LOCATION_JOB] AS ORIGINAL_LOCATION_JOB
	  
	  ,(DATALENGTH([LOCATION_JOB] ) - DATALENGTH(REPLACE([LOCATION_JOB], N',', ''))) / NULLIF(DATALENGTH(N','), 0)+1 AS [SECTION_COUNT]
	  ,20/(((DATALENGTH([LOCATION_JOB] ) - DATALENGTH(REPLACE([LOCATION_JOB], N',', ''))) / NULLIF(DATALENGTH(N','), 0)+1)* (CASE WHEN ABS(TRY_CAST(KM_ENDspl.Part AS FLOAT)-TRY_CAST(KM_STARTspl.Part AS FLOAT))>=0.1 THEN FLOOR(ABS(TRY_CAST(KM_ENDspl.Part AS FLOAT)-TRY_CAST(KM_STARTspl.Part AS FLOAT))*10) ELSE 1 END)) AS HOURS
	  ,spl.value AS [LOCATION_JOB]
	  ,CASE WHEN ROADspl.Part='CSW' THEN 'BLB' ELSE ROADspl.Part END  AS ROAD
	  ,COALESCE(TRY_CAST(KM_STARTspl.Part AS FLOAT)+KILOMETER,TRY_CAST(KM_STARTspl.Part AS FLOAT)) AS [KILOMETER]
	  ,TRY_CAST(KM_STARTspl.Part AS FLOAT) AS KM_START
	  ,TRY_CAST(KM_ENDspl.Part AS FLOAT) AS KM_END
      ,getEQUIPMENT_TYPE_CLEAN.EQUIPMENT_TYPE_CLEAN AS [EQUIPMENT_TYPE]
   
      ,[UNIT_ID]
      ,[MAIN_ISSUE]
      ,[ACTION]
      ,[REMARKS]
  FROM [WBN_DATABASE].[dbo].[DAY_WORKS_PLAN_DAILY]
  OUTER APPLY dbo.getEQUIPMENT_TYPE_CLEAN(EQUIPMENT_TYPE) AS getEQUIPMENT_TYPE_CLEAN
  OUTER APPLY STRING_SPLIT(REPLACE(REPLACE(REPLACE([LOCATION_JOB],' ',''),'_KM','-'),'+','.'),',') aS spl
  outer apply SplitPart(spl.value,'-',1) AS ROADspl
  outer apply SplitPart(spl.value,'-',2) AS KM_STARTspl
  outer apply SplitPart(spl.value,'-',3) AS KM_ENDspl
  LEFT JOIN (SELECT (ROW_NUMBER() OVER (ORDER BY (SELECT NULL)))*0.1 AS KILOMETER -- duplicate every 100 meter
  FROM [WBN_DATABASE].[dbo].[HAUL_ROAD_STA]
) AS iter ON iter.KILOMETER<=ABS(TRY_CAST(KM_ENDspl.Part AS FLOAT)-TRY_CAST(KM_STARTspl.Part AS FLOAT)) AND iter.KILOMETER<=10
WHERE [DATE] >=DATEADD(DAY,-14,GETDATE())

```


</details>


<details><summary><code>dbo.WAITING_TIME_DIFFERENCE</code></summary>


```sql

CREATE VIEW [dbo].[WAITING_TIME_DIFFERENCE] AS 
SELECT  
      [TEAM]
      ,[DATE]
      ,[EQUIPMENT_ID]
      ,[SHIFT]
      ,[ORIGIN_ID]
      ,[ORIGIN_AREA]
      ,[DESTINATION]
      ,[BLOCK_ID]
      ,[RIT]
      ,[WB_ID]
	  ,[LOADING_WAITING_TIME]
	  ,[LOADING_TIME]
	  ,
    ABS(CASE 
    WHEN [LOADING_WAITING_TIME] > [LOADING_TIME] AND DATEDIFF(
            MINUTE, 
            CAST([DATE] AS DATETIME) + CAST([LOADING_WAITING_TIME] AS DATETIME), 
            DATEADD(DAY, 1, CAST([DATE] AS DATETIME) + CAST([LOADING_TIME] AS DATETIME))
        )<720 THEN 
        DATEDIFF(
            MINUTE, 
            CAST([DATE] AS DATETIME) + CAST([LOADING_WAITING_TIME] AS DATETIME), 
            DATEADD(DAY, 1, CAST([DATE] AS DATETIME) + CAST([LOADING_TIME] AS DATETIME))
        )
    ELSE 
        DATEDIFF(
            MINUTE, 
            [LOADING_WAITING_TIME] , 
            [LOADING_TIME]
        )
END) AS [LOADING_DIFFERENCE_TIME]

      

      ,[DUMPING_WAITING_TIME]
      ,[DUMPING_TIME]
      ,
    ABS(CASE 
    WHEN [DUMPING_WAITING_TIME] > [DUMPING_TIME] THEN 
        DATEDIFF(
            MINUTE, 
            CAST([DATE] AS DATETIME) + CAST([DUMPING_WAITING_TIME] AS DATETIME), 
            DATEADD(DAY, 1, CAST([DATE] AS DATETIME) + CAST([DUMPING_TIME] AS DATETIME))
        )
    ELSE 
        DATEDIFF(
            MINUTE, 
            [DUMPING_WAITING_TIME] , 
            [DUMPING_TIME]
        )
END) AS [DUMPING_DIFFERENCE_TIME]
      ,[DRIVER_ID]
      ,[PIT]
      ,[FUEL_FILLING_TIME]
      ,[REMARK]
  FROM [WBN_DATABASE].[dbo].[WAITING_TIME]


```


</details>


<details><summary><code>dbo.WAITING_TIME_FIX</code></summary>


```sql










CREATE VIEW [dbo].[WAITING_TIME_FIX] AS
SELECT 
	   W.[TEAM]
      ,W.[DATE]
      ,W.[EQUIPMENT_ID]
      ,W.[SHIFT]
      ,W.[ORIGIN_ID]
      ,W.[ORIGIN_AREA]
      ,W.[BLOCK_ID]
      ,W.[RIT]
      ,W.[WB_ID]
      ,W.[LOADING_WAITING_TIME]
      ,W.[LOADING_TIME]
      ,W.[LOADING_DIFFERENCE_TIME]
      ,W.[DUMPING_WAITING_TIME]
      ,W.[DUMPING_TIME]
      ,W.[DUMPING_DIFFERENCE_TIME]
      ,W.[DRIVER_ID]
      ,W.[PIT]
      ,W.[FUEL_FILLING_TIME]
      ,W.[REMARK],
CASE
		WHEN REPLACE(UPPER(DESTINATION), ' ', '') LIKE '%POS%10%' THEN 'POS 10'
		WHEN REPLACE(UPPER(DESTINATION), ' ', '') LIKE '%POS%11%' THEN 'POS 11'
		WHEN REPLACE(UPPER(DESTINATION), ' ', '') LIKE '%POS%12%' THEN 'POS 12'
		WHEN REPLACE(UPPER(DESTINATION), ' ', '') LIKE '%POS%14%' THEN 'POS 14'
		WHEN REPLACE(UPPER(DESTINATION), ' ', '') LIKE '%POS%6%' THEN 'POS 6'
		WHEN DESTINATION LIKE '27%' THEN 'POS 12'
		WHEN DESTINATION LIKE 'BIRI%' THEN 'BIRI BIRI'
		WHEN DESTINATION LIKE '%B01%' THEN 'HUAFEI B.01'
		WHEN DESTINATION LIKE '%C01%' THEN 'HUAFEI C.01'
		WHEN DESTINATION LIKE N'%W???%' THEN 'FENI 15 KM'
		WHEN DESTINATION LIKE N'%U???%' THEN 'FENI 15 KM'
		WHEN DESTINATION LIKE N'??%' THEN 'FENI 0 KM'
		WHEN DESTINATION LIKE '%%W%' THEN 'FENI 15 KM'
		ELSE DESTINATION
		END AS DESTINATION

FROM 
[dbo].[WAITING_TIME_DIFFERENCE] AS W

WHERE 
           W.[ORIGIN_ID] LIKE 'TF%'
        OR W.[ORIGIN_ID] LIKE 'AC%'
        OR W.[ORIGIN_ID] LIKE 'AD%'
        OR W.[ORIGIN_ID] LIKE 'AB%'
        OR W.[ORIGIN_ID] LIKE 'AA%'
        OR W.[ORIGIN_ID] LIKE 'LD%'
        OR W.[ORIGIN_ID] LIKE 'BLB%'
		--OR W.[ORIGIN_ID] <> 'LIMBAH'
        OR W.[ORIGIN_ID] LIKE 'LIM%'
        OR W.[ORIGIN_ID] LIKE 'POS%'
    ;

```


</details>


### FMS_DB — 1 matching views


<details><summary><code>dbo.FMS_PLAYBACK_TRACK_WORKINGHOURS</code></summary>


```sql




CREATE VIEW [dbo].[FMS_PLAYBACK_TRACK_WORKINGHOURS] AS 
SELECT CAST(DATEADD(HOUR,-7,[DATETIME]) AS [DATE]) AS [DATE]
	  ,CASE WHEN DATEPART(HOUR,DATEADD(HOUR,-7,[DATETIME]))>=12 THEN 2 ELSE 1 END AS [SHIFT]
	  ,plateNumber AS [EQUIPMENT_ID]
,ROUND(sum([driving_time])/(60*60),2) AS WORKING_HOURS
,SUM(distance_m) as distance_m
   
  
  FROM [FMS_DB].[dbo].[FMS_PLAYBACK_TRACK_CLEAN]

  GROUP BY plateNumber,CAST(DATEADD(HOUR,-7,[DATETIME]) AS [DATE]),CASE WHEN DATEPART(HOUR,DATEADD(HOUR,-7,[DATETIME]))>=12 THEN 2 ELSE 1 END 

```


</details>


## 6. Complete table/view inventory (Step 3)


### WBN_DATABASE — 579 objects (161 tables, 418 views)

| schema | object | type | approx_rows | description |
|---|---|---|---|---|
| dbo | 3RD_PARTY_ACTIVITIES | USER_TABLE | 3328 |  |
| dbo | 3RD_PARTY_ACTIVITIES_RECLAIM | USER_TABLE | 4202 |  |
| dbo | ACTIVITIES | USER_TABLE | 13 |  |
| dbo | ACTIVITIES_MAT | USER_TABLE | 39 |  |
| dbo | ALL_HR_KM_SECTIONS | USER_TABLE | 27 |  |
| dbo | ASSAY_CLASS | USER_TABLE | 27 |  |
| dbo | ASSAYS | USER_TABLE | 396475 |  |
| dbo | ASSAYS_NITON_GGSHEET | USER_TABLE | 19700 |  |
| dbo | auto_edge_HAULAGE | USER_TABLE | 246975 |  |
| dbo | auto_node_STOCK_ID | USER_TABLE | 186836 |  |
| dbo | autoBLOCK_PROD_QC_BM_TOS_CORR | USER_TABLE | 135148 |  |
| dbo | autoHAULAGE_VS_PROD_MONTHLY_CF | USER_TABLE | 223 |  |
| dbo | autoQC_CF_BM_PROP | USER_TABLE | 0 |  |
| dbo | autoQC_CF_BM_TOS | USER_TABLE | 8274 |  |
| dbo | autoQC_CF_BM_TOS_HISTORY_OLD | USER_TABLE | 175475 |  |
| dbo | autoQC_PLAN_NI_CF_OLD | USER_TABLE | 264 |  |
| dbo | autoQC_STOCK_ALL_VIA_ALL | USER_TABLE | 93119 |  |
| dbo | autoTOS_SURVEY_ESTIMATION | USER_TABLE | 41447 |  |
| dbo | BATCH | USER_TABLE | 4931 |  |
| dbo | blasting_drilling | USER_TABLE | 14648 |  |
| dbo | blasting_parameters | USER_TABLE | 2081 |  |
| dbo | BLASTING_PROD | USER_TABLE | 433 |  |
| dbo | blasting_production | USER_TABLE | 0 |  |
| dbo | BLASTING_REMAINING | USER_TABLE | 98 |  |
| dbo | BLOCK_ID_XYPARAM | USER_TABLE | 16 |  |
| dbo | BLOCK_INDESIGN | USER_TABLE | 4288722 |  |
| dbo | Calendar_For_Exploitation | USER_TABLE | 2665 |  |
| dbo | Calendar_Svy_topo_by_deposit | USER_TABLE | 1848 |  |
| dbo | CLASS2025 | USER_TABLE | 1438 |  |
| dbo | COLOR_CHEMICAL | USER_TABLE | 404 |  |
| dbo | COMPANIES | USER_TABLE | 73 |  |
| dbo | CONSOLIDATED SURVEY | USER_TABLE | 1188 |  |
| dbo | CONTRACTOR FOLLOW UP | USER_TABLE | 131768 |  |
| dbo | CONTRACTOR_DEPOSIT | USER_TABLE | 84 |  |
| dbo | CORRECTIVE_ACTIONS | USER_TABLE | 0 |  |
| dbo | CRUSHER LOIPOLOY | USER_TABLE | 27353 |  |
| dbo | CRUSHER_BLENDING_DATA | USER_TABLE | 3332 |  |
| dbo | CRUSHER_CF | USER_TABLE | 3 |  |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA | USER_TABLE | 156726 |  |
| dbo | CRUSHER_SURVEY_LOYPOLOY | USER_TABLE | 16 |  |
| dbo | DAILY_QUALITY_DISPATCH | USER_TABLE | 66774 |  |
| dbo | DARONNE_Htemp | USER_TABLE | 5812 |  |
| dbo | DARONNEtemp | USER_TABLE | 61 |  |
| dbo | DAY_WORKS | USER_TABLE | 496409 |  |
| dbo | DAY_WORKS_PLAN_DAILY | USER_TABLE | 2043 |  |
| dbo | DAYWORK_REQUEST | USER_TABLE | 0 |  |
| dbo | DISPATCH FeNi PLAN & ACTUAL | USER_TABLE | 85416 |  |
| dbo | DISPATCH HAULAGE TF | USER_TABLE | 264 |  |
| dbo | DISPATCH ROADS | USER_TABLE | 222 |  |
| dbo | DISPATCH ROADS OLD | USER_TABLE | 254 |  |
| dbo | DISPATCH WBN ACTUAL | USER_TABLE | 212890 |  |
| dbo | DISPATCH WBN PLAN SHIFT | USER_TABLE | 27058 |  |
| dbo | DISPATCH_PLAN_WB | USER_TABLE | 432 |  |
| dbo | DISTANCE_HAULING | USER_TABLE | 30587 |  |
| dbo | DISTANCE_MINING | USER_TABLE | 83462 |  |
| dbo | DRAFTS | USER_TABLE | 4848 |  |
| dbo | DT_DENSITY_HR_MODEL$ | USER_TABLE | 37 |  |
| dbo | EQUIPMENTS | USER_TABLE | 7221 |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | USER_TABLE | 4699720 |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | USER_TABLE | 16657468 |  |
| dbo | EQUIPMENTS_OLD | USER_TABLE | 5658 |  |
| dbo | EQUIPMENTS_PLAN | USER_TABLE | 2071 |  |
| dbo | EQUIPMENTS_STATUS | USER_TABLE | 3708573 |  |
| dbo | EQUIPMENTS_WORKS | USER_TABLE | 82 |  |
| dbo | EXC_TRIMMING | USER_TABLE | 59362 |  |
| dbo | FeNi Reclaiming Plan | USER_TABLE | 129378 |  |
| dbo | FENI_REQUESTS | USER_TABLE | 7196 |  |
| dbo | FMS_TOS_STATUS | USER_TABLE | 0 |  |
| dbo | HAUL_ROAD_STA | USER_TABLE | 3122 |  |
| dbo | HAULAGE | USER_TABLE | 3510278 |  |
| dbo | HAULAGE CONTRACTORS | USER_TABLE | 11 |  |
| dbo | HAULAGE_ADJ | USER_TABLE | 3 |  |
| dbo | HAULAGE_IWIP | USER_TABLE | 572742 |  |
| dbo | HAULAGE_IWIP_EXT | USER_TABLE | 1508871 |  |
| dbo | HAULAGE_M_DOME_2026_IWIP_PLAN | USER_TABLE | 44289 |  |
| dbo | HAULAGE_REPORT | USER_TABLE | 13459 |  |
| dbo | HRM_CONTRACT_EQUIPMENT | USER_TABLE | 198 |  |
| dbo | HRM_INSPECTION | USER_TABLE | 30610 |  |
| dbo | HRM_MAJOR_ROADWORK | USER_TABLE | 149 |  |
| dbo | HRM_REQUEST_MATERIAL | USER_TABLE | 25 |  |
| dbo | ID_DT_HUAFEI | USER_TABLE | 485 |  |
| dbo | IWIP_REQUESTS_DATE | USER_TABLE | 772 |  |
| dbo | LME | USER_TABLE | 148 |  |
| dbo | LME_GOLD | USER_TABLE | 146 |  |
| dbo | LOCATION_WB_SH | USER_TABLE | 39 |  |
| dbo | MBAR | USER_TABLE | 173 |  |
| dbo | MINING_EQ_TARGET_3MRMP | USER_TABLE | 30 |  |
| dbo | MINING_FLASH_REPORT_EQUIPMENT | USER_TABLE | 102 |  |
| dbo | MINING_FLASH_REPORT_FLEET_PROD | USER_TABLE | 108 |  |
| dbo | MINING_FLASH_REPORT_PRODUCTION | USER_TABLE | 42 |  |
| dbo | MINING_PLAN_3MRMP | USER_TABLE | 2295 |  |
| dbo | MINING_PLAN_WEEKLY | USER_TABLE | 124358 |  |
| dbo | Ni_COLOR | USER_TABLE | 45 |  |
| dbo | OLD_prod_correction_factor_ACCESS | USER_TABLE | 957 |  |
| dbo | OLD_VERY_SHORT_TERM | USER_TABLE | 13470 |  |
| dbo | OMR_QC | USER_TABLE | 86007 |  |
| dbo | ORE STOCK SALES | USER_TABLE | 3800 |  |
| dbo | ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE | USER_TABLE | 1585 |  |
| dbo | PILES_SHARED_FENI | USER_TABLE | 66571 |  |
| dbo | POS FOLLOW UP | USER_TABLE | 177830 |  |
| dbo | POS POSSIBILITY For HAULAGE | USER_TABLE | 23 |  |
| dbo | PP_MINED_NEW_RECONCIL_MENG | USER_TABLE | 309723 |  |
| dbo | PP_MINED_YTD_OK | USER_TABLE | 35922 |  |
| dbo | PP_REMAIN_INPIT_MINEOUT | USER_TABLE | 36206 |  |
| dbo | PROD VERY VERY SHORT TERM | USER_TABLE | 11216 |  |
| dbo | PRODUCTION_ACTIVITY_PIT | USER_TABLE | 453453 |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | USER_TABLE | 0 |  |
| dbo | PRODUCTION_PIT_OLD | USER_TABLE | 407593 |  |
| dbo | PRODUCTION_PIT_PRELIM_auto | USER_TABLE | 15887 |  |
| dbo | PROJECTS_SUPERVISION | USER_TABLE | 198 |  |
| dbo | QC PIT-TOS OMR | USER_TABLE | 149360 |  |
| dbo | QC SAMPLE DATA | USER_TABLE | 25425 |  |
| dbo | QC_TOS_DATA_ML | USER_TABLE | 38001 |  |
| dbo | QS_LIMS_RIM_CK | USER_TABLE | 6131 |  |
| dbo | QUARRY PRODUCTION | USER_TABLE | 12646 |  |
| dbo | QUARRY_PLAN | USER_TABLE | 1114 |  |
| dbo | RAINFALL | USER_TABLE | 55934 |  |
| dbo | RECLASSIFICATION | USER_TABLE | 7794 |  |
| dbo | REQUEST | USER_TABLE | 3920 |  |
| dbo | REQUEST_SALES_LATE_2025 | USER_TABLE | 18 |  |
| dbo | ROLLING_MINE_PLAN | USER_TABLE | 834 |  |
| dbo | RSF_HAULING_DATA | USER_TABLE | 1143509 |  |
| dbo | RSF_PER_LOCATION | USER_TABLE | 1489 |  |
| dbo | RSF_SURVEY | USER_TABLE | 9103 |  |
| dbo | S123_ENVIRO_TSS | USER_TABLE | 2366 |  |
| dbo | S123_STOCK_SHAPE | USER_TABLE | 4785 |  |
| dbo | S123_STOCK_SHAPE_OLD | USER_TABLE | 1732432 |  |
| dbo | S123_TOS_STATUS | USER_TABLE | 3589 |  |
| dbo | SAMPLE | USER_TABLE | 249622 |  |
| dbo | SAMPLING_CONTRACTOR | USER_TABLE | 123196 |  |
| dbo | SHAPE_STOCK_AREA | USER_TABLE | 26 |  |
| dbo | START LIM STOCK | USER_TABLE | 0 |  |
| dbo | STOCK_REQUESTS | USER_TABLE | 4735 |  |
| dbo | STOCK_STATUS | USER_TABLE | 14725 |  |
| dbo | STOCK_STATUS_HAULAGE_GGSHEET | USER_TABLE | 4750 |  |
| dbo | SUMMARY_SURVEY | USER_TABLE | 460 |  |
| dbo | SUPERVISION_SAFETY_ACTIONS | USER_TABLE | 6 |  |
| dbo | SURVEY POS | USER_TABLE | 50629 |  |
| dbo | TEAM | USER_TABLE | 34 |  |
| dbo | TEAM_FB | USER_TABLE | 25 |  |
| dbo | TEAM_PLAN | USER_TABLE | 78 |  |
| dbo | TEAM_PROFILE | USER_TABLE | 0 |  |
| dbo | tempHAULAGE_IWIP | USER_TABLE | 0 |  |
| dbo | TOS | USER_TABLE | 0 |  |
| dbo | TOS FOLLOW | USER_TABLE | 87045 |  |
| dbo | TOS_DUMP_COORDINATES | USER_TABLE | 118 |  |
| dbo | TOS_PILE_INFO | USER_TABLE | 97738 |  |
| dbo | TOS_STATUS | USER_TABLE | 549734 |  |
| dbo | TOS_SURVEY | USER_TABLE | 5340 |  |
| dbo | TRANSHIPMENT_WBN_ORE | USER_TABLE | 575 |  |
| dbo | TSS | USER_TABLE | 35218 |  |
| dbo | TSS_CROSSTABLE | USER_TABLE | 109 |  |
| dbo | TSS_POINT | USER_TABLE | 121 |  |
| dbo | VERY VERY SHORT TERM PIT SERVICE | USER_TABLE | 21078 |  |
| dbo | WAITING_TIME | USER_TABLE | 878240 |  |
| dbo | WATER_MANAGEMENT | USER_TABLE | 1074 |  |
| dbo | WBN_DATABASE_ERROR_PROCEDURE | USER_TABLE | 0 |  |
| dbo | WBN_DATABASE_ESSENTIALS | USER_TABLE | 334 |  |
| dbo | WBN_DATABASE_PROCEDURE_QUEUE | USER_TABLE | 79 |  |
| dbo | WBN_DATABASE_ST_LOG_ON | USER_TABLE | 14942 |  |
| dbo | WMT_FOR_3RD_PARTY | USER_TABLE | 5529 |  |
| dbo | _LIMONITE_DAILY_STOCK | VIEW |  |  |
| dbo | _ore_screened_or_not | VIEW |  |  |
| dbo | _PROD_BLAST_ASSAYS | VIEW |  |  |
| dbo | _prod_lim_assays | VIEW |  |  |
| dbo | _prod_lim_assays_via_BM | VIEW |  |  |
| dbo | 3rd_PARTY_DUPLICATES_ANALYSIS | VIEW |  |  |
| dbo | ARCGIS_EQUIPMENTS_INFO_APP | VIEW |  |  |
| dbo | ASSAY_CLASS_IN | VIEW |  |  |
| dbo | ASSAY_PROGRESS | VIEW |  |  |
| dbo | ASSAYS CONSOLIDATED | VIEW |  |  |
| dbo | ASSAYS CONSOLIDATED VIA BM | VIEW |  |  |
| dbo | ASSAYS SAMPLING BRIDGE | VIEW |  |  |
| dbo | ASSAYS SAMPLING BRIDGE FILTERED | VIEW |  |  |
| dbo | ASSAYS SAMPLING BRIDGE RAW DATA | VIEW |  |  |
| dbo | ASSAYS TOS | VIEW |  |  |
| dbo | ASSAYS TOS FILTERED | VIEW |  |  |
| dbo | ASSAYS_MISSING_ | VIEW |  |  |
| dbo | ASSAYS_MISSING_2 | VIEW |  |  |
| dbo | ASSAYS_NITON_CLEAN | VIEW |  |  |
| dbo | ASSAYS_NONULL | VIEW |  |  |
| dbo | ASSAYS_PDF | VIEW |  |  |
| dbo | ASSAYS_YARD_ORIGINAL_DOME | VIEW |  |  |
| dbo | ATC_ORACLE_ASSAYS | VIEW |  |  |
| dbo | auto_view_QC_STOCK_ALL_VIA_ALL | VIEW |  |  |
| dbo | autoBM_GROUP | VIEW |  |  |
| dbo | autoPLAN_Ni | VIEW |  |  |
| dbo | autoQC_PLAN_NI_CF | VIEW |  |  |
| dbo | autoTOS_SURVEY_ESTIMATION_view | VIEW |  |  |
| dbo | AVG_RAIN_BY_DATE_AREA | VIEW |  |  |
| dbo | AVG_RAIN_BY_DATE_AREA_RAW | VIEW |  |  |
| dbo | AVG_RAIN_BY_DAY_ALL_AREA | VIEW |  |  |
| dbo | BATCH COMPOSITES | VIEW |  |  |
| dbo | BLOCK_CLASS_OF_TOS_PILE | VIEW |  |  |
| dbo | BLOCK_OF_TOS_PILE | VIEW |  |  |
| dbo | block_prod | VIEW |  |  |
| dbo | BLOCK_PROD_FOR_PROD | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR_TARGET | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT_CORR | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_OLD | VIEW |  |  |
| dbo | BLOCK_PROD_QC_BM_TOS_SURVEY_ADJ | VIEW |  |  |
| dbo | BLOCK_PROD_TOS | VIEW |  |  |
| dbo | BLOCK_PROD_TOS_ASSAYS | VIEW |  |  |
| dbo | BM | VIEW |  |  |
| dbo | BM_CARROT2 | VIEW |  |  |
| dbo | BM_ESTIMATION_CONFIDENCE | VIEW |  |  |
| dbo | BM_KRENE_FOR_RESERVES_LIM | VIEW |  |  |
| dbo | BM_KRENE_TREATED_0 | VIEW |  |  |
| dbo | BM_LONG_TERM | VIEW |  |  |
| dbo | BM_OK_PREPARED | VIEW |  |  |
| dbo | BM_OK_TREATED_0 | VIEW |  |  |
| dbo | BM_OK_TREATED_1 | VIEW |  |  |
| dbo | BM_OK_TREATED_1_via_OLD_PP_MENG_CONVERTED | VIEW |  |  |
| dbo | BM_PP_FOR_RECONCIL | VIEW |  |  |
| dbo | BM_PP_FOR_RECONCIL_LAST_UPDATE | VIEW |  |  |
| dbo | BM_PP_LAST_ADJUST | VIEW |  |  |
| dbo | BM_PRODUCTION | VIEW |  |  |
| dbo | BM_RECONCIL_LT_TREATED_0 | VIEW |  |  |
| dbo | BM_RECONCIL_LT_TREATED_1 | VIEW |  |  |
| dbo | BM_RECONCIL_TC0 | VIEW |  |  |
| dbo | BM_RECONCIL_TC0_TREATED_0 | VIEW |  |  |
| dbo | BM_RECONCIL_TC0_TREATED_1 | VIEW |  |  |
| dbo | BM_RECONCIL_TC0_TREATED_1_FULL | VIEW |  |  |
| dbo | BM_REDUCED_FOR_RECONCIL_GROUP | VIEW |  |  |
| dbo | BM_REMAINING_RESERVES_TC0 | VIEW |  |  |
| dbo | BM_RESSOURCES_KRENE_TC07_TC08 | VIEW |  |  |
| dbo | BM_TC0_LAST | VIEW |  |  |
| dbo | BM_TC0_REFORMAT_LONG | VIEW |  |  |
| dbo | BM_TC0_WMT | VIEW |  |  |
| dbo | BM_TC0_WMT_GROUP | VIEW |  |  |
| dbo | BM_VS_ACTUAL_DEST | VIEW |  |  |
| dbo | Calendar_last_Survey | VIEW |  |  |
| dbo | CALENDAR_SHIFT | VIEW |  |  |
| dbo | CEK_RIT_HAULAGE | VIEW |  |  |
| dbo | CF FOR PROD CORR ASSAYS 2 | VIEW |  |  |
| dbo | CF_CHECK | VIEW |  |  |
| dbo | CHECK_BACKCHARGE_HAULAGE_IWIP | VIEW |  |  |
| dbo | COMPANIES_PLANT_ONLY | VIEW |  |  |
| dbo | CONTRACTOR FOLLOW UP DATE 2 | VIEW |  |  |
| dbo | CONTRACTOR_FOLLOW_UP_DATE | VIEW |  |  |
| dbo | CONTRACTOR_FU_DT_VARIATION | VIEW |  |  |
| dbo | CORPSAMPLEASSAY | VIEW |  |  |
| dbo | CRUSHER_BLENDING_DATA_TREATED | VIEW |  |  |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA_TREATED | VIEW |  |  |
| dbo | DAILY_QUALITY_DISPATCH_GROUP | VIEW |  |  |
| dbo | DAILY_QUALITY_DISPATCH_TREATED | VIEW |  |  |
| dbo | DAILY_STOCK_POS | VIEW |  |  |
| dbo | DARONNE_CLEAN | VIEW |  |  |
| dbo | DARONNE_HAUL | VIEW |  |  |
| dbo | DARONNE_HAUL_AVG | VIEW |  |  |
| dbo | DARONNE_LIM | VIEW |  |  |
| dbo | DARONNE_QUERY | VIEW |  |  |
| dbo | DARONNE_QUERY_LIM | VIEW |  |  |
| dbo | DATE HAULAGE RECLAIMING | VIEW |  |  |
| dbo | DAY_WORK_wEQ_INFO | VIEW |  |  |
| dbo | DAY_WORKS_RIM__NO_FMS | VIEW |  |  |
| dbo | DISPATCH FENI & WBN ACTUAL DT SHIFT | VIEW |  |  |
| dbo | DISPATCH FENI ACTUAL Treated 0 | VIEW |  |  |
| dbo | DISPATCH RESULTS DISTANCE | VIEW |  |  |
| dbo | DISPATCH RESULTS LITE 2 | VIEW |  |  |
| dbo | DISPATCH RESULTS LITE 2 SECTION | VIEW |  |  |
| dbo | DISPATCH RESULTS LITE 2_OLD | VIEW |  |  |
| dbo | DISPATCH RESULTS LITE 3 | VIEW |  |  |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | VIEW |  |  |
| dbo | DISPATCH RSF ACTUAL Treated | VIEW |  |  |
| dbo | DISPATCH WBN PLAN | VIEW |  |  |
| dbo | DISPATCH WMT VERY SHORT TERM | VIEW |  |  |
| dbo | DISPATCH_PRODUCTIVITY_TARGET | VIEW |  |  |
| dbo | DISTANCE_HAULING_CHECK | VIEW |  |  |
| dbo | DISTANCE_MINING_CHECK | VIEW |  |  |
| dbo | DOME INFO | VIEW |  |  |
| dbo | DOME WBN | VIEW |  |  |
| dbo | DT_DENSITY_Haulage_Reclaiming | VIEW |  |  |
| dbo | DT_DENSITY_HAULROAD | VIEW |  |  |
| dbo | DT_DENSITY_HAULROAD_treated | VIEW |  |  |
| dbo | DT_DENSITY_HAULROAD_treated2 | VIEW |  |  |
| dbo | DT_DENSITY_RECLAIMING | VIEW |  |  |
| dbo | DT_DENSITY_RECLAIMING_treated | VIEW |  |  |
| dbo | DT_DENSITY_RECLAIMING_treated2 | VIEW |  |  |
| dbo | DT_DENSITY_RECLAIMING_treated3 | VIEW |  |  |
| dbo | EQ_STATUS_WATER_MANAGEMENT | VIEW |  |  |
| dbo | EQUIPMENT_LAST_COMMISSIONING | VIEW |  |  |
| dbo | EQUIPMENT_NEW_ID | VIEW |  |  |
| dbo | EQUIPMENT_PLAN_ACTUAL | VIEW |  |  |
| dbo | EQUIPMENT_STATUS_FULL | VIEW |  |  |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS | VIEW |  |  |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS_2 | VIEW |  |  |
| dbo | EQUIPMENTS_CLEAN | VIEW |  |  |
| dbo | EQUIPMENTS_CLEAN2 | VIEW |  |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_COMPACT | VIEW |  |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_DAILY | VIEW |  |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_SUMMARY | VIEW |  |  |
| dbo | EQUIPMENTS_QR_CODE_VALUE | VIEW |  |  |
| dbo | EQUIPMENTS_STATUS_BREAKDOWN | VIEW |  |  |
| dbo | equipments_status_last_breakdown | VIEW |  |  |
| dbo | FeNi Reclaiming Plan Treated 1 | VIEW |  |  |
| dbo | FeNi Reclaiming Plan Treated 2 | VIEW |  |  |
| dbo | FeNi Reclaiming Plan Treated 3 | VIEW |  |  |
| dbo | FENI_RECLAIMING_PLAN_WITH_GRADE | VIEW |  |  |
| dbo | FENI_REQUESTS_FIRST | VIEW |  |  |
| dbo | FENI_REQUESTS_TREATED | VIEW |  |  |
| dbo | FINANCE_MANAGEMENT | VIEW |  |  |
| dbo | FINANCE_MANAGEMENT_BOD | VIEW |  |  |
| dbo | FINANCE_MANAGEMENT_RE | VIEW |  |  |
| dbo | FINANCE_PHYSICAL_FLOW | VIEW |  |  |
| dbo | FULL HAULAGE | VIEW |  |  |
| dbo | FULL_ASSAYS_STOCK | VIEW |  |  |
| dbo | FULL_FULL_PRODUCTION | VIEW |  |  |
| dbo | FULL_PLAN | VIEW |  |  |
| dbo | FULL_PRODUCTION | VIEW |  |  |
| dbo | FULL_PRODUCTION_GROUP | VIEW |  |  |
| dbo | FULL_PRODUCTION_ONLY | VIEW |  |  |
| dbo | FULL_PRODUCTION_RECOMPACT | VIEW |  |  |
| dbo | FULL_PRODUCTION_REFORMAT | VIEW |  |  |
| dbo | FULL_PRODUCTION_VS_PLAN | VIEW |  |  |
| dbo | GEO_TOS_DUPLICATE | VIEW |  |  |
| dbo | geometry_columns | VIEW |  |  |
| dbo | HAUL VERY SHORT TERM TREATED 1 | VIEW |  |  |
| dbo | HAUL VERY SHORT TERM TREATED 2 | VIEW |  |  |
| dbo | HAUL VERY SHORT TERM TREATED 3 | VIEW |  |  |
| dbo | HAULAGE_BY_CONTRACTOR_TRUCK | VIEW |  |  |
| dbo | HAULAGE_CLEAN | VIEW |  |  |
| dbo | HAULAGE_CLEAN_FOR_DT | VIEW |  |  |
| dbo | HAULAGE_CLEAN2 | VIEW |  |  |
| dbo | HAULAGE_COMPLETE | VIEW |  |  |
| dbo | HAULAGE_COMPLETE_VIA_BM | VIEW |  |  |
| dbo | HAULAGE_ERROR | VIEW |  |  |
| dbo | HAULAGE_GET_IWIP_PLAN_TICKET_NO | VIEW |  |  |
| dbo | HAULAGE_GET_IWIP_TICKET_NO | VIEW |  |  |
| dbo | HAULAGE_IWIP_CLEAN | VIEW |  |  |
| dbo | HAULAGE_IWIP_VS_RECLAIM | VIEW |  |  |
| dbo | HAULAGE_IWIP_WASTE | VIEW |  |  |
| dbo | HAULAGE_LIM_BATCH | VIEW |  |  |
| dbo | HAULAGE_ORIGIN_PIT | VIEW |  |  |
| dbo | HAULAGE_PER_PILE | VIEW |  |  |
| dbo | HAULAGE_PER_PILE_AND_PLAN | VIEW |  |  |
| dbo | HAULAGE_PER_PILE_AND_PLAN_TEMPORAL | VIEW |  |  |
| dbo | HAULAGE_PILE_INFO | VIEW |  |  |
| dbo | HAULAGE_PIT_ORIGIN_DESTINATION | VIEW |  |  |
| dbo | HAULAGE_VS_IWIP_SYSTEM | VIEW |  |  |
| dbo | HAULAGE_VS_OMR | VIEW |  |  |
| dbo | HAULAGE_VS_OMR_ORI_DEST | VIEW |  |  |
| dbo | HAULAGE_VS_PROD_MONTHLY_CF | VIEW |  |  |
| dbo | HAULAGE_VS_PROD_PILES_CF | VIEW |  |  |
| dbo | HAULAGE_VS_RECLAIM | VIEW |  |  |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | VIEW |  |  |
| dbo | HAULAGE_WITH_DT_TYPES | VIEW |  |  |
| dbo | HRM | VIEW |  |  |
| dbo | IMPORT_HEATMAP | VIEW |  |  |
| dbo | Lab_Duplicate | VIEW |  |  |
| dbo | LIM TOS PILE DOME For HAULAGE | VIEW |  |  |
| dbo | LME_FOR_HMA_Ni | VIEW |  |  |
| dbo | LME_NEW_HMA | VIEW |  |  |
| dbo | LME_Ni_USD | VIEW |  |  |
| dbo | MINING_EQUIPMENTS | VIEW |  |  |
| dbo | MINING_HAULAGE_PLAN_AND_ACTUAL | VIEW |  |  |
| dbo | MINING_PLAN_3MRMP_DAILY | VIEW |  |  |
| dbo | MINING_PLAN_WEEKLY_BLOCKS | VIEW |  |  |
| dbo | MINING_PLAN_WEEKLY_BLOCKS_VS_ACT | VIEW |  |  |
| dbo | MINING_PLAN_WEEKLY_WITH_QUALITY | VIEW |  |  |
| dbo | NEW_BLOCK_MAP_DIL_0 | VIEW |  |  |
| dbo | NEW_BLOCK_MAP_DIL_1 | VIEW |  |  |
| dbo | NEW_BLOCK_MAP_DIL_2 | VIEW |  |  |
| dbo | NEW_BLOCK_MAP_DOM_PROP | VIEW |  |  |
| dbo | NEW_BLOCK_MAP_rev02 | VIEW |  |  |
| dbo | NEW_BM_OK | VIEW |  |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP | VIEW |  |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX | VIEW |  |  |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_Alan_test | VIEW |  |  |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP | VIEW |  |  |
| dbo | NEW_QC_RECONCIL_FOR_ARCGIS | VIEW |  |  |
| dbo | OEE MINING WITH DEMOB | VIEW |  |  |
| dbo | OEE_HAULAGE_WMT_KM | VIEW |  |  |
| dbo | OEE_MINING_FULL | VIEW |  |  |
| dbo | OEE_MINING_NEW | VIEW |  |  |
| dbo | OEEDB_AUDB | VIEW |  |  |
| dbo | OEEDB_PDB | VIEW |  |  |
| dbo | OMR_PILE_STATUS_ALL | VIEW |  |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP | VIEW |  |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP2 | VIEW |  |  |
| dbo | OMR_TOS | VIEW |  |  |
| dbo | OMR_TOS_CONTINUE | VIEW |  |  |
| dbo | PILES_SHARED_FENI_TREATED | VIEW |  |  |
| dbo | PileTonnage | VIEW |  |  |
| dbo | PLAN_DAY_WORKS_CLEAN | VIEW |  |  |
| dbo | POS FOLLOW UP TREATED | VIEW |  |  |
| dbo | PP_MINED_CLEAN | VIEW |  |  |
| dbo | PP_MINED_NEW_RECONCIL_MENG_CONVERT_NEW_BM | VIEW |  |  |
| dbo | Prod and Calender | VIEW |  |  |
| dbo | PROD_ASSAYS | VIEW |  |  |
| dbo | PROD_CALENDAR_ASSAYS | VIEW |  |  |
| dbo | PROD_CORR_AND_PLAN | VIEW |  |  |
| dbo | PROD_CORR_ASSAYS | VIEW |  |  |
| dbo | PROD_CORR_ASSAYS_COG | VIEW |  |  |
| dbo | PROD_CORR_ASSAYS_COG_2 | VIEW |  |  |
| dbo | PROD_CORR_ASSAYS_COG_3 | VIEW |  |  |
| dbo | PROD_CORR_ASSAYS_COG_4 | VIEW |  |  |
| dbo | PROD_VIA_BM | VIEW |  |  |
| dbo | PROD_VVST_REPORT_2 | VIEW |  |  |
| dbo | PROD_VVST_TREATED | VIEW |  |  |
| dbo | PRODUCTION_EQUIPMENT_RUNNING | VIEW |  |  |
| dbo | PRODUCTION_MINING_PIT | VIEW |  |  |
| dbo | PRODUCTION_PIT | VIEW |  |  |
| dbo | PRODUCTION_PIT_BY_EQ_HOUR | VIEW |  |  |
| dbo | PRODUCTION_PIT_COEF | VIEW |  |  |
| dbo | PRODUCTION_PIT_COORDINATES_B_S | VIEW |  |  |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y | VIEW |  |  |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y_CONVERT_NEW_BM | VIEW |  |  |
| dbo | PRODUCTION_PIT_DAILY_PLAN | VIEW |  |  |
| dbo | PRODUCTION_PIT_DISTANCE_CALC | VIEW |  |  |
| dbo | PRODUCTION_PIT_HOURLY | VIEW |  |  |
| dbo | PRODUCTION_PIT_HOURLY_FULL | VIEW |  |  |
| dbo | PRODUCTION_PIT_HOURLY_TF | VIEW |  |  |
| dbo | PRODUCTION_PIT_RECONCIL_PP | VIEW |  |  |
| dbo | PRODUCTION_PIT_TOS_CLEAN | VIEW |  |  |
| dbo | PRODUCTION_PIT_VS_OMR | VIEW |  |  |
| dbo | PRODUCTION_PIT_WRONG_ELEVATION | VIEW |  |  |
| dbo | QC ALL DATA 2 | VIEW |  |  |
| dbo | QC CHECK PIT VS SAMP LD | VIEW |  |  |
| dbo | QC CHECK PIT VS SAMP TOS | VIEW |  |  |
| dbo | QC PIT-TOS & SAMPLE DATA | VIEW |  |  |
| dbo | QC PIT-TOS OMR SUMMARY | VIEW |  |  |
| dbo | QC PIT-TOS OMR SUMMARY 2 | VIEW |  |  |
| dbo | QC PIT-TOS SUM FOR CHECK FOR LD | VIEW |  |  |
| dbo | QC PIT-TOS SUM FOR CHECK FOR TOS | VIEW |  |  |
| dbo | QC SAMPLE & ASSAYS | VIEW |  |  |
| dbo | QC SAMPLE & ASSAYS COMPOSITES | VIEW |  |  |
| dbo | QC SAMPLE SUM FOR CHECK | VIEW |  |  |
| dbo | QC TOS BALANCE | VIEW |  |  |
| dbo | QC TOS_PILE STATUS HAULAGE | VIEW |  |  |
| dbo | QC TOS_VS_POS | VIEW |  |  |
| dbo | QC_CF_BM_PROP | VIEW |  |  |
| dbo | QC_CF_BM_TOS | VIEW |  |  |
| dbo | QC_CF_BM_TOS_OLD | VIEW |  |  |
| dbo | QC_COMPOSITE_ALL_STOCK | VIEW |  |  |
| dbo | QC_COMPOSITE_ASSAY | VIEW |  |  |
| dbo | QC_COMPOSITE_BLOCK | VIEW |  |  |
| dbo | QC_COMPOSITE_BLOCK_SELECT | VIEW |  |  |
| dbo | QC_COMPOSITE_BLOCK_VIA_PIT | VIEW |  |  |
| dbo | QC_COMPOSITE_DUMP | VIEW |  |  |
| dbo | QC_COMPOSITE_DUMP_VIA_PIT | VIEW |  |  |
| dbo | QC_COMPOSITE_HAULAGE | VIEW |  |  |
| dbo | QC_COMPOSITE_POS | VIEW |  |  |
| dbo | QC_COMPOSITE_POS_VIA_BM | VIEW |  |  |
| dbo | QC_COMPOSITE_POS_VIA_ML | VIEW |  |  |
| dbo | QC_COMPOSITE_POS_VIA_TOS | VIEW |  |  |
| dbo | QC_COMPOSITE_POS_VIA_YARD | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_CERT | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_IndividualBlock | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_BM | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_BM_ORI | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_HAULAGE | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_PIT | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_POS | VIEW |  |  |
| dbo | QC_COMPOSITE_TOS_VIA_YARD | VIEW |  |  |
| dbo | QC_COMPOSITE_WCO | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD_DIRECT | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD_STOCK_ORIGINAL | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD_VIA_BM | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD_VIA_POS | VIEW |  |  |
| dbo | QC_COMPOSITE_YARD_VIA_TOS | VIEW |  |  |
| dbo | QC_PLAN_Ni_CF_ALL | VIEW |  |  |
| dbo | QC_POS_DETAILS | VIEW |  |  |
| dbo | QC_STOCK_ALL | VIEW |  |  |
| dbo | QC_STOCK_ALL_VIA_ALL | VIEW |  |  |
| dbo | QC_STOCK_ALL_VIA_ALL_OLD | VIEW |  |  |
| dbo | QC_STOCK_POS_VIA_ALL | VIEW |  |  |
| dbo | QC_STOCK_TOS_FOR_ANALYZE | VIEW |  |  |
| dbo | QC_STOCK_TOS_VIA_ALL | VIEW |  |  |
| dbo | QUARRY PRODUCTION treated | VIEW |  |  |
| dbo | QUARRY_DAILY_EXTRACTION | VIEW |  |  |
| dbo | QUARRY_STOCK_BLEND_MANAGEMENT | VIEW |  |  |
| dbo | QUARRY_STOCK_BLEND_MANAGEMENT_TREATED | VIEW |  |  |
| dbo | QUARRY_STOCK_CRUSHED_MANAGEMENT | VIEW |  |  |
| dbo | QUARRY_STOCK_CRUSHED_MANAGEMENT_TREATED | VIEW |  |  |
| dbo | QUARRY_STOCK_TOS_MANAGEMENT | VIEW |  |  |
| dbo | QUARRY_STOCK_TOS_MANAGEMENT_TREATED | VIEW |  |  |
| dbo | RAINFALL_AREA_COORDINATES | VIEW |  |  |
| dbo | RAINFALL_CONSOLIDATED | VIEW |  |  |
| dbo | RAINFALL_PREP | VIEW |  |  |
| dbo | RECLAIMING | VIEW |  |  |
| dbo | RECLAIMING DETAIL | VIEW |  |  |
| dbo | RECLAIMING DETAIL 2 | VIEW |  |  |
| dbo | RECLAIMING DETAIL 3 | VIEW |  |  |
| dbo | RECLAIMING DETAIL 4 | VIEW |  |  |
| dbo | RECLAIMING_MATCH_ASSAY_STOCK_ID2 | VIEW |  |  |
| dbo | RECLAIMING_ORIGIN_DESTINATION | VIEW |  |  |
| dbo | RECLAIMING_REJECT_POURCENTAGE | VIEW |  |  |
| dbo | RECLAIMING_REJECT_POURCENTAGE_DATE | VIEW |  |  |
| dbo | RECLAIMING_WB_TREATED_3_JOIN | VIEW |  |  |
| dbo | RECLAIMNG WB TREATED GROUPED | VIEW |  |  |
| dbo | RECLASSIFICATION_MISSING | VIEW |  |  |
| dbo | RECLASSIFICATION_TOS_MISSING | VIEW |  |  |
| dbo | RECONCIL_OK | VIEW |  |  |
| dbo | RECONCIL_ST_LT | VIEW |  |  |
| dbo | RECONCIL_TC0 | VIEW |  |  |
| dbo | REMAINING_RESERVES_BM_OK | VIEW |  |  |
| dbo | REQUEST_FENI_PLAN | VIEW |  |  |
| dbo | REQUEST_FULL | VIEW |  |  |
| dbo | REQUEST_LAST | VIEW |  |  |
| dbo | REQUEST_VS_HAULAGE | VIEW |  |  |
| dbo | ROLLING_MINE_PLAN_TREATED | VIEW |  |  |
| dbo | ROLLING_MINE_PLAN_TREATED_2 | VIEW |  |  |
| dbo | RSF RSF_REPORT | VIEW |  |  |
| dbo | RSF RSF_SURVEY_TREATED | VIEW |  |  |
| dbo | RSF_HAULING_DATA_DAILY | VIEW |  |  |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT | VIEW |  |  |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR | VIEW |  |  |
| dbo | RSF_REPORT | VIEW |  |  |
| dbo | S123_STOCK_SHAPE_QGIS_TEST | VIEW |  |  |
| dbo | S123_TOS_STATUS_CLEAN | VIEW |  |  |
| dbo | SAF_OVERSPEED | VIEW |  |  |
| dbo | SAF_OVERSPEED_LIMIT | VIEW |  |  |
| dbo | SAMPLING BRIDGE CERTIFICATE | VIEW |  |  |
| dbo | SAMPLING_CONTRACTOR_PREP | VIEW |  |  |
| dbo | SHORT_TERM_RECONCIL | VIEW |  |  |
| dbo | STOCK_CERTIFICATE_NEWS | VIEW |  |  |
| dbo | STOCK_INFO_FULL | VIEW |  |  |
| dbo | STOCK_INFOS | VIEW |  |  |
| dbo | STOCK_MANAGEMENT | VIEW |  |  |
| dbo | STOCK_MANAGEMENT_RE | VIEW |  |  |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | VIEW |  |  |
| dbo | STOCK_ORIGIN_PIT | VIEW |  |  |
| dbo | STOCK_ORIGIN_PIT_BY_WMT | VIEW |  |  |
| dbo | STOCK_POS_YARD | VIEW |  |  |
| dbo | STOCK_REQUESTS_TREATED | VIEW |  |  |
| dbo | STOCK_REQUESTS_TREATED_2 | VIEW |  |  |
| dbo | STOCK_SHAPE | VIEW |  |  |
| dbo | STOCK_SHAPE_LAST | VIEW |  |  |
| dbo | STOCK_STATUS_FLOW | VIEW |  |  |
| dbo | STOCK_STATUS_FULL | VIEW |  |  |
| dbo | STOCK_STATUS_SIMPLE | VIEW |  |  |
| dbo | STOCK_STATUS_STATUS | VIEW |  |  |
| dbo | STOCK_TYPE_ALL | VIEW |  |  |
| dbo | STOCK_WMT_EVOLUTION | VIEW |  |  |
| dbo | SUM PROD WMT FOR CORR | VIEW |  |  |
| dbo | SUM WMT SURVEY | VIEW |  |  |
| dbo | SURVEY POS CONSOLIDATED | VIEW |  |  |
| dbo | SURVEY_POS_DATED | VIEW |  |  |
| dbo | SURVEY_POS_ESTIMATE_HAULAGE | VIEW |  |  |
| dbo | SURVEY_POS_FOR_PROD | VIEW |  |  |
| dbo | SURVEY_POS_TC | VIEW |  |  |
| dbo | SURVEY_STOCK_MAX | VIEW |  |  |
| dbo | test sa mere | VIEW |  |  |
| dbo | TEST_CAROTTE | VIEW |  |  |
| dbo | TOS FOLLOW TREATED | VIEW |  |  |
| dbo | TOS FOLLOW TREATED 2 | VIEW |  |  |
| dbo | TOS_DUMP_COORDINATES_UNIQUE | VIEW |  |  |
| dbo | TOS_Duplicate | VIEW |  |  |
| dbo | TOS_PILE_FINAL_RECLASSIFICATION | VIEW |  |  |
| dbo | TOS_PILE_INFO_TREATED | VIEW |  |  |
| dbo | TOS_PILE_PIT | VIEW |  |  |
| dbo | TOS_PILES_WMT_WB_RIT_MINING | VIEW |  |  |
| dbo | TOS_STATUS_ERROR_TRANSFER_DATE | VIEW |  |  |
| dbo | TOS_SURVEY_ESTIMATION | VIEW |  |  |
| dbo | TOS_SURVEY_ESTIMATION2 | VIEW |  |  |
| dbo | TOS_SURVEY_trial | VIEW |  |  |
| dbo | trial cek tos follow vs haulage iwip  | VIEW |  |  |
| dbo | TSS_NO_MATCH_POINT | VIEW |  |  |
| dbo | TSS_PREP | VIEW |  |  |
| dbo | UNIT_TRIPS_HUAFEI_RSF | VIEW |  |  |
| dbo | vOSPAT_RESULTS | VIEW |  |  |
| dbo | vw_HAULAGE_GROUP | VIEW |  |  |
| dbo | VW_PRODUCTION_ACTIVITY_PIT | VIEW |  |  |
| dbo | w2_EQUIPMENTS | VIEW |  |  |
| dbo | w2_EQUIPMENTS_STATUS | VIEW |  |  |
| dbo | w2_PRODUCTION_PIT_HOURLY | VIEW |  |  |
| dbo | WAITING_TIME_DIFFERENCE | VIEW |  |  |
| dbo | WAITING_TIME_FIX | VIEW |  |  |
| dbo | WEIGHBRIDGE_&_TRUCKCOUNT_TF_LAST | VIEW |  |  |
| dbo | WEIGHBRIDGE_&_TRUCKCOUNT_TF_PER_WEEK | VIEW |  |  |
| dbo | WMT_3RD_PARTY_LAST | VIEW |  |  |
| dbo | WMT_LAST_CERT | VIEW |  |  |


### FMS_DB — 102 objects (65 tables, 37 views)

| schema | object | type | approx_rows | description |
|---|---|---|---|---|
| dbo | auto_kmFMS_PLAYBACK_TRACK_DATA | USER_TABLE | 20448378 |  |
| dbo | auto_spFMS_PLAYBACK_TRACK_DATA | USER_TABLE | 2032624 |  |
| dbo | autoFMS_SECURITY_INCIDENT_KILOMETER | USER_TABLE | 4330549 |  |
| dbo | DEPARTMENT_MASTER | USER_TABLE | 5 |  |
| dbo | FMS_APP_STATE | USER_TABLE | 24 |  |
| dbo | FMS_ASSIGNMENTS | USER_TABLE | 17 |  |
| dbo | FMS_CONGESTION_SEG | USER_TABLE | 18281 |  |
| dbo | FMS_DISPATCH_PLAN | USER_TABLE | 105 |  |
| dbo | FMS_DOCS | USER_TABLE | 1 |  |
| dbo | FMS_ENTRY_EXIT_DATA | USER_TABLE | 13470082 |  |
| dbo | FMS_EQUIPMENTS | USER_TABLE | 1435 |  |
| dbo | FMS_ERROR_FLOW | USER_TABLE | 0 |  |
| dbo | FMS_GEOFENCE_ALERT_RULES | USER_TABLE | 1 |  |
| dbo | FMS_GEOFENCE_ALERTS | USER_TABLE | 70 |  |
| dbo | FMS_GEOFENCE_VISITS | USER_TABLE | 74312 |  |
| dbo | FMS_GEOFENCES | USER_TABLE | 3490 |  |
| dbo | FMS_GPS_Historical | USER_TABLE | 1717625 |  |
| dbo | FMS_HAUL_CYCLES | USER_TABLE | 288 |  |
| dbo | FMS_INSTANCES | USER_TABLE | 3 |  |
| dbo | FMS_INTERVENTION_EVENT_DATA | USER_TABLE | 1320961 |  |
| dbo | FMS_JOB_RUNS | USER_TABLE | 20 |  |
| dbo | FMS_LOGIN_IPS | USER_TABLE | 69 |  |
| dbo | FMS_LV_BOOKING | USER_TABLE | 0 |  |
| dbo | FMS_LV_BOOKING_ITEM | USER_TABLE | 0 |  |
| dbo | FMS_LV_DAILY_REPORTS | USER_TABLE | 10 |  |
| dbo | FMS_LV_MOVEMENTS | USER_TABLE | 0 |  |
| dbo | FMS_LV_OVERTIME_REVIEW | USER_TABLE | 15 |  |
| dbo | FMS_LV_VISIT_VERIFICATIONS | USER_TABLE | 6 |  |
| dbo | FMS_LV_ZONE_VISITS | USER_TABLE | 71 |  |
| dbo | FMS_MESSAGES | USER_TABLE | 16 |  |
| dbo | FMS_PLAYBACK_STAY_DATA | USER_TABLE | 402196 |  |
| dbo | FMS_PLAYBACK_TRACK_24H | USER_TABLE | 1082391 |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | USER_TABLE | 27456831 |  |
| dbo | FMS_QUALITY_DISPATCH | USER_TABLE | 258 |  |
| dbo | FMS_RISK_DATA | USER_TABLE | 337685 |  |
| dbo | FMS_ROADMAP | USER_TABLE | 87 |  |
| dbo | FMS_ROADMAP_DOC | USER_TABLE | 1 |  |
| dbo | FMS_ROADMAP_META | USER_TABLE | 1 |  |
| dbo | FMS_SECURITY_INCIDENT_DATA | USER_TABLE | 5514587 |  |
| dbo | FMS_SETTINGS | USER_TABLE | 8 |  |
| dbo | FMS_TMS_TOKEN | USER_TABLE | 3040 |  |
| dbo | FMS_TOS_STATUS | USER_TABLE | 3404 |  |
| dbo | FMS_TRUCK_ASSIGNMENTS | USER_TABLE | 408 |  |
| dbo | FMS_TRUCK_CYCLES | USER_TABLE | 1 |  |
| dbo | FMS_UNIT_INSTALLED | USER_TABLE | 1225 |  |
| dbo | FMS_USER_ACTIVITY | USER_TABLE | 18 |  |
| dbo | FMS_USERS | USER_TABLE | 31 |  |
| dbo | LV_BOOKING | USER_TABLE | 2 |  |
| dbo | LV_BOOKING_DETAIL | USER_TABLE | 4 |  |
| dbo | LV_DRIVER_INFO | USER_TABLE | 0 |  |
| dbo | LV_INFO | USER_TABLE | 124 |  |
| dbo | LV_MASTER | USER_TABLE | 134 |  |
| dbo | LV_PLAN | USER_TABLE | 62 |  |
| dbo | RADIO_REPROGRAM_TRACK | USER_TABLE | 3478 |  |
| dbo | RES_CRITICAL_ZONES | USER_TABLE | 4 |  |
| dbo | RES_EMPLOYEES | USER_TABLE | 8958 |  |
| dbo | RES_SPEED_LIMIT_ZONES | USER_TABLE | 27 |  |
| dbo | RES_WATER_FILLING_POINTS | USER_TABLE | 14 |  |
| dbo | SAFETY_DPLAN | USER_TABLE | 80 |  |
| dbo | SHP_SED_POND | USER_TABLE | 91 |  |
| dbo | SIM_PLAN_ANALOGUE_CACHE | USER_TABLE | 8 |  |
| dbo | SIM_PLAN_DAY_KPI | USER_TABLE | 12112 |  |
| dbo | SIM_PLAN_EDGE | USER_TABLE | 27 |  |
| dbo | SIM_PLAN_NODE | USER_TABLE | 17 |  |
| dbo | WT_DAILY_PLAN | USER_TABLE | 1259 |  |
| dbo | CCR_RISK_EVENT_ACTIONS | VIEW |  |  |
| dbo | EQUIPMENTS_RADIO_STATUS | VIEW |  |  |
| dbo | FMS_ENTRY_EXIT_CLEAN | VIEW |  |  |
| dbo | FMS_EQUIPMENTS_CLEAN | VIEW |  |  |
| dbo | FMS_EQUIPMENTS_FILTER | VIEW |  |  |
| dbo | FMS_HRM_SUPERVISION | VIEW |  |  |
| dbo | FMS_INTERVENTION_EVENT_CLEAN | VIEW |  |  |
| dbo | FMS_PLAYBACK_STAY_CLEAN | VIEW |  |  |
| dbo | FMS_PLAYBACK_STAY_GROUP | VIEW |  |  |
| dbo | FMS_PLAYBACK_TRACK_CLEAN | VIEW |  |  |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | VIEW |  |  |
| dbo | FMS_PLAYBACK_TRACK_WORKINGHOURS | VIEW |  |  |
| dbo | FMS_RISK_CLEAN | VIEW |  |  |
| dbo | FMS_SECURITY_INCIDENT_CLEAN | VIEW |  |  |
| dbo | FMS_SECURITY_INCIDENT_KILOMETER | VIEW |  |  |
| dbo | IDLE_EVENTS_WT | VIEW |  |  |
| dbo | KIMPER_MISSING_FMS_ID | VIEW |  |  |
| dbo | LV_GEOFENCE_EVENTS | VIEW |  |  |
| dbo | OSPAT_RESULTS | VIEW |  |  |
| dbo | OVERSPEED_EVENTS | VIEW |  |  |
| dbo | OVERSPEED_VEHICLE_SUMMARY | VIEW |  |  |
| dbo | VW_DISPATCHER_DIM | VIEW |  |  |
| dbo | VW_DISPATCHER_INCIDENT_REVIEW | VIEW |  |  |
| dbo | VW_DISPATCHER_MONTHLY_KPI | VIEW |  |  |
| dbo | VW_FMS_EVENTS | VIEW |  |  |
| dbo | VW_FMS_LV_VISIT_EVIDENCE | VIEW |  |  |
| dbo | VW_LV_ACTIVE_PLAN | VIEW |  |  |
| dbo | VW_LV_POOL | VIEW |  |  |
| dbo | VW_SAFETY_DPLAN | VIEW |  |  |
| dbo | VW_WT_DAILY_PLAN | VIEW |  |  |
| dbo | VW_WT_PLAN_BREAKDOWN_STATUS | VIEW |  |  |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | VIEW |  |  |
| dbo | VW_WT_REFILL_CYCLES | VIEW |  |  |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | VIEW |  |  |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | VIEW |  |  |
| dbo | VW_WT_ZONE_COVERAGE | VIEW |  |  |
| dbo | WATER_POINTS_GEOFENCE | VIEW |  |  |


## 7. Column-level fuel references


### 7a. Step-2 exact query results (tables only, as requested)


**WBN_DATABASE** — 19 columns

| schema_name | table_name | column_name | data_type | max_length | is_nullable | column_description |
|---|---|---|---|---|---|---|
| dbo | BLASTING_PROD | CALCULATED_VOLUME | float | 8 | True |  |
| dbo | BLASTING_PROD | VOLUME_CLAIM_BCM | float | 8 | True |  |
| dbo | CONTRACTOR FOLLOW UP | Quantity | float | 8 | True |  |
| dbo | CRUSHER_SURVEY_LOYPOLOY | VOLUME (LCM) | float | 8 | True |  |
| dbo | CRUSHER_SURVEY_LOYPOLOY | VOLUME (BCM) | float | 8 | True |  |
| dbo | DAY_WORKS_PLAN_DAILY | MAIN_ISSUE | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_WORKS | ISSUE_DETAILS | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_WORKS | ISSUE_DATE_START | date | 3 | True |  |
| dbo | HRM_CONTRACT_EQUIPMENT | QUANTITY | int | 4 | True |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | VOLUME_BCM | float | 8 | True |  |
| dbo | RSF_SURVEY | PROGRESS_VOLUME | float | 8 | True |  |
| dbo | SURVEY POS | ROCKY VOLUME | float | 8 | True |  |
| dbo | SURVEY POS | VOLUME (LCM) | float | 8 | True |  |
| dbo | SURVEY POS | VOLUME (BCM) | float | 8 | True |  |
| dbo | TSS_POINT | Quantity | float | 8 | True |  |
| dbo | WAITING_TIME | FUEL_FILLING_TIME | time | 5 | True |  |
| dbo | WAITING_TIME | FUEL_FILLING_TIME 2 | time | 5 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL | nvarchar | 100 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL 2 | nvarchar | 100 | True |  |


**FMS_DB** — 0 columns

_(no rows)_


### 7b. Widened search (fuel synonyms + hourmeter/odometer/distance)

Step 2 as written joins `sys.columns` to `sys.tables`, so **views are invisible
to it**, and it misses the Indonesian terms used on this site (`BBM`, `SOLAR`)
plus `HOURMETER`/`SMU`/`ODOMETER`. Both gaps are closed here.


**WBN_DATABASE — tables: 167 columns**

| schema_name | table_name | column_name | data_type | max_length | is_nullable | column_description |
|---|---|---|---|---|---|---|
| dbo | ALL_HR_KM_SECTIONS | KM_START | float | 8 | True |  |
| dbo | ALL_HR_KM_SECTIONS | KM_END | float | 8 | True |  |
| dbo | ALL_HR_KM_SECTIONS | APPROX_DISTANCE | float | 8 | True |  |
| dbo | ASSAYS | WMT | float | 8 | True |  |
| dbo | auto_edge_HAULAGE | WMT | float | 8 | True |  |
| dbo | auto_node_STOCK_ID | WMT_IN | float | 8 | True |  |
| dbo | auto_node_STOCK_ID | WMT_OUT | float | 8 | True |  |
| dbo | auto_node_STOCK_ID | WMT_CERT | float | 8 | True |  |
| dbo | autoBLOCK_PROD_QC_BM_TOS_CORR | WMT | float | 8 | True |  |
| dbo | autoBLOCK_PROD_QC_BM_TOS_CORR | WMT_METHOD | varchar | 2 | False |  |
| dbo | autoQC_STOCK_ALL_VIA_ALL | POS_WMT_CERT | float | 8 | True |  |
| dbo | autoQC_STOCK_ALL_VIA_ALL | YARD_WMT_CERT | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT_SURVEY_EST | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT_SURVEY_GAP | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT_SURVEY | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT_TRANSFER | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT_ORI | float | 8 | True |  |
| dbo | autoTOS_SURVEY_ESTIMATION | WMT | float | 8 | True |  |
| dbo | blasting_production | Wmt | float | 8 | True |  |
| dbo | CLASS2025 | WMT | float | 8 | True |  |
| dbo | CONSOLIDATED SURVEY | WMT_SURVEY | float | 8 | True |  |
| dbo | CONSOLIDATED SURVEY | WMT_CLAIM (CLOSE MONTH) | float | 8 | True |  |
| dbo | CRUSHER LOIPOLOY | WMT | float | 8 | True |  |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA | WMT | float | 8 | True |  |
| dbo | CRUSHER_SURVEY_LOYPOLOY | WMT | float | 8 | True |  |
| dbo | DAILY_QUALITY_DISPATCH | WMT | float | 8 | True |  |
| dbo | DARONNE_Htemp | WMT | float | 8 | True |  |
| dbo | DARONNE_Htemp | CUM_WMT | float | 8 | True |  |
| dbo | DARONNEtemp | WMT_TARGET | float | 8 | True |  |
| dbo | DARONNEtemp | CUM_WMT_TARGET | float | 8 | True |  |
| dbo | DAY_WORKS | UNIT_START_HOUR_METER | float | 8 | True |  |
| dbo | DAY_WORKS | UNIT_END_HOUR_METER | float | 8 | True |  |
| dbo | DAY_WORKS | ROAD_STA_KM | float | 8 | True |  |
| dbo | DAY_WORKS | ROAD_END_KM | float | 8 | True |  |
| dbo | DAY_WORKS | DISTANCE_KM | float | 8 | True |  |
| dbo | DISPATCH FeNi PLAN & ACTUAL | WMT ACT | float | 8 | True |  |
| dbo | DISPATCH ROADS | KM ORI | float | 8 | True |  |
| dbo | DISPATCH ROADS | KM DEST | float | 8 | True |  |
| dbo | DISPATCH ROADS | DISTANCE GROSS (KM) | float | 8 | True |  |
| dbo | DISPATCH ROADS | CRD KM0 - KM2,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CRD KM2,5 - KM5,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CRD KM5,5 - KM7 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CSW KM3 - KM4 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CSW KM4 - KM5,7 | float | 8 | True |  |
| dbo | DISPATCH ROADS | GOMDI KM3,7 - KM3,8 | float | 8 | True |  |
| dbo | DISPATCH ROADS | BLB KM2,5 - KM5,7 | float | 8 | True |  |
| dbo | DISPATCH ROADS | BLB KM5,7 - KM10 | float | 8 | True |  |
| dbo | DISPATCH ROADS | BLB KM17 - KM20 | float | 8 | True |  |
| dbo | DISPATCH ROADS | HFC KM5,5 - KM6,4 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CBB KM7 - KM9 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CBB KM9 - KM15 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CBB KM15 - KM17 | float | 8 | True |  |
| dbo | DISPATCH ROADS | CBBB KM15 - KM17,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM7 - KM12 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM12 - KM15 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM15 - KM17 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM17 - KM21 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM21 - KM26 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM26 - KM27 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM27 - KM32 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM32 - KM37 | float | 8 | True |  |
| dbo | DISPATCH ROADS | KR KM37 - KM39 | float | 8 | True |  |
| dbo | DISPATCH ROADS | TF KM39 - KM45 | float | 8 | True |  |
| dbo | DISPATCH ROADS | TF KM45 - KM52 | float | 8 | True |  |
| dbo | DISPATCH ROADS | TF KM52 - KM60 | float | 8 | True |  |
| dbo | DISPATCH ROADS | TF KM60 - KM68 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KM ORI | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KM DEST | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | DISTANCE GROSS (KM) | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CRD KM0 - KM2,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CRD KM2,5 - KM5,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CRD KM5,5 - KM7 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CSW KM3 - KM4 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CSW KM4 - KM5,7 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | GOMDI KM3,7 - KM3,8 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | BLB KM2,5 - KM5,7 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | BLB KM5,7 - KM10 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | BLB KM17 - KM20 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | HFC KM5,5 - KM6,4 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CBB KM7 - KM9 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CBB KM9 - KM15 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CBB KM15 - KM17 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | CBBB KM15 - KM17,5 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM7 - KM12 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM12 - KM15 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM15 - KM17 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM17 - KM21 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM21 - KM26 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM26 - KM27 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM27 - KM32 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM32 - KM37 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | KR KM37 - KM39 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | TF KM39 - KM45 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | TF KM45 - KM52 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | TF KM52 - KM60 | float | 8 | True |  |
| dbo | DISPATCH ROADS OLD | TF KM60 - KM68 | float | 8 | True |  |
| dbo | DISPATCH WBN ACTUAL | WMT | float | 8 | True |  |
| dbo | DISTANCE_HAULING | DISTANCE | float | 8 | True |  |
| dbo | DISTANCE_HAULING | WMT | float | 8 | True |  |
| dbo | DISTANCE_MINING | DISTANCE | float | 8 | True |  |
| dbo | DISTANCE_MINING | WMT | float | 8 | True |  |
| dbo | DRAFTS | WMT | float | 8 | True |  |
| dbo | DT_DENSITY_HR_MODEL$ | WMT | float | 8 | True |  |
| dbo | DT_DENSITY_HR_MODEL$ | PLAN WMT | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | DISTANCE | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | WORKING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | OPERATING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | HOUR_METER_START | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | HOUR_METER_END | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | USAGE_KM_METER | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | WORKING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_WORKS | HOUR_METER | float | 8 | True |  |
| dbo | FeNi Reclaiming Plan | PLANNED WMT | float | 8 | True |  |
| dbo | FENI_REQUESTS | WMT | float | 8 | True |  |
| dbo | HAUL_ROAD_STA | SectionKM | float | 8 | False |  |
| dbo | HAULAGE | WMT | float | 8 | True |  |
| dbo | HAULAGE_ADJ | WMT_SURVEY | float | 8 | True |  |
| dbo | HAULAGE_ADJ | WMT_HAULAGE | float | 8 | True |  |
| dbo | HAULAGE_ADJ | WMT_TC | float | 8 | True |  |
| dbo | HAULAGE_REPORT | WMT | float | 8 | True |  |
| dbo | HRM_INSPECTION | KM_START | float | 8 | True |  |
| dbo | HRM_INSPECTION | KM_END | float | 8 | True |  |
| dbo | HRM_MAJOR_ROADWORK | KM_START | int | 4 | True |  |
| dbo | HRM_MAJOR_ROADWORK | KM_END | int | 4 | True |  |
| dbo | LOCATION_WB_SH | KM_LOADED | float | 8 | True |  |
| dbo | LOCATION_WB_SH | KM_EMPTY | float | 8 | True |  |
| dbo | MBAR | WMT | float | 8 | True |  |
| dbo | MINING_FLASH_REPORT_FLEET_PROD | ACT DISTANCE | float | 8 | True |  |
| dbo | MINING_PLAN_3MRMP | WMT_INSITU | float | 8 | True |  |
| dbo | MINING_PLAN_3MRMP | WMT_ROM | float | 8 | True |  |
| dbo | MINING_PLAN_WEEKLY | WMT | float | 8 | True |  |
| dbo | MINING_PLAN_WEEKLY | WMT_REC | float | 8 | True |  |
| dbo | MINING_PLAN_WEEKLY | WMT_ROM | float | 8 | True |  |
| dbo | OLD_VERY_SHORT_TERM | WMT | float | 8 | True |  |
| dbo | ORE STOCK SALES | WMT | float | 8 | True |  |
| dbo | ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE | WMT | float | 8 | True |  |
| dbo | PILES_SHARED_FENI | WMT | float | 8 | True |  |
| dbo | PRODUCTION_ACTIVITY_PIT | TF_WMT | float | 8 | True |  |
| dbo | PRODUCTION_ACTIVITY_PIT | WMT | float | 8 | True |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | DISTANCE_KM | float | 8 | True |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | WMT | float | 8 | True |  |
| dbo | PRODUCTION_PIT_OLD | WMT | float | 8 | True |  |
| dbo | PRODUCTION_PIT_PRELIM_auto | WMT | float | 8 | True |  |
| dbo | QC PIT-TOS OMR | WMT | float | 8 | True |  |
| dbo | QC_TOS_DATA_ML | BM_WMT | float | 8 | True |  |
| dbo | QC_TOS_DATA_ML | WMT | float | 8 | True |  |
| dbo | ROLLING_MINE_PLAN | WMT_ROM | float | 8 | True |  |
| dbo | RSF_HAULING_DATA | ORIGIN_KM | nvarchar | 100 | True |  |
| dbo | RSF_HAULING_DATA | DESTINATION_KM | nvarchar | 100 | True |  |
| dbo | START LIM STOCK | WMT | float | 8 | True |  |
| dbo | STOCK_REQUESTS | WMT | float | 8 | True |  |
| dbo | SUMMARY_SURVEY | TC_WMT | float | 8 | True |  |
| dbo | SUMMARY_SURVEY | SURVEY_WMT | float | 8 | True |  |
| dbo | SUMMARY_SURVEY | CF_WMT | float | 8 | True |  |
| dbo | SURVEY POS | WMT | float | 8 | True |  |
| dbo | TOS FOLLOW | WMT | float | 8 | True |  |
| dbo | TOS_SURVEY | WMT | float | 8 | True |  |
| dbo | TRANSHIPMENT_WBN_ORE | WMT | int | 4 | True |  |
| dbo | VERY VERY SHORT TERM PIT SERVICE | QUARRY_WMT | float | 8 | True |  |
| dbo | VERY VERY SHORT TERM PIT SERVICE | SP_WST_WMT | float | 8 | True |  |
| dbo | VERY VERY SHORT TERM PIT SERVICE | TMM__WMT | float | 8 | True |  |
| dbo | WAITING_TIME | FUEL_FILLING_TIME | time | 5 | True |  |
| dbo | WAITING_TIME | FUEL_FILLING_TIME 2 | time | 5 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL | nvarchar | 100 | True |  |
| dbo | WAITING_TIME | TOTAL_FUEL 2 | nvarchar | 100 | True |  |
| dbo | WMT_FOR_3RD_PARTY | WMT ORIGINAL | float | 8 | True |  |
| dbo | WMT_FOR_3RD_PARTY | WMT TOTAL | float | 8 | True |  |


**WBN_DATABASE — views: 602 columns**

| schema_name | view_name | column_name | data_type | max_length | is_nullable |
|---|---|---|---|---|---|
| dbo | _LIMONITE_DAILY_STOCK | WMT | float | 8 | True |
| dbo | _PROD_BLAST_ASSAYS | WMT | float | 8 | True |
| dbo | _prod_lim_assays | WMT | float | 8 | True |
| dbo | _prod_lim_assays_via_BM | WMT | float | 8 | True |
| dbo | ASSAYS SAMPLING BRIDGE | WMT | float | 8 | True |
| dbo | ASSAYS SAMPLING BRIDGE FILTERED | WMT | float | 8 | True |
| dbo | ASSAYS SAMPLING BRIDGE RAW DATA | WMT | float | 8 | True |
| dbo | ASSAYS_MISSING_ | WMT | float | 8 | True |
| dbo | ASSAYS_NONULL | WMT | float | 8 | True |
| dbo | ASSAYS_PDF | WMT | float | 8 | True |
| dbo | ASSAYS_YARD_ORIGINAL_DOME | WMT | float | 8 | True |
| dbo | auto_view_QC_STOCK_ALL_VIA_ALL | POS_WMT_CERT | float | 8 | True |
| dbo | auto_view_QC_STOCK_ALL_VIA_ALL | YARD_WMT_CERT | float | 8 | True |
| dbo | autoBM_GROUP | WMT | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT_SURVEY_EST | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT_SURVEY_GAP | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT_SURVEY | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT_TRANSFER | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT_ORI | float | 8 | True |
| dbo | autoTOS_SURVEY_ESTIMATION_view | WMT | float | 8 | True |
| dbo | block_prod | WMT | float | 8 | True |
| dbo | block_prod | WMT2 | float | 8 | True |
| dbo | BLOCK_PROD_FOR_PROD | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR | WMT_FINAL | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR_TARGET | TARGET_WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_CORR_TARGET | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT_CORR | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_OLD | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_OLD | WMT2 | int | 4 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_SURVEY_ADJ | WMT | float | 8 | True |
| dbo | BLOCK_PROD_QC_BM_TOS_SURVEY_ADJ | WMT_FINAL | float | 8 | True |
| dbo | BLOCK_PROD_TOS | WMT | float | 8 | True |
| dbo | BLOCK_PROD_TOS_ASSAYS | WMT | float | 8 | True |
| dbo | BLOCK_PROD_TOS_ASSAYS | WMT2 | float | 8 | True |
| dbo | BM_KRENE_FOR_RESERVES_LIM | WMT | float | 8 | True |
| dbo | BM_OK_TREATED_1 | WMT | float | 8 | True |
| dbo | BM_OK_TREATED_1_via_OLD_PP_MENG_CONVERTED | WMT | float | 8 | True |
| dbo | BM_PP_LAST_ADJUST | WMT | int | 4 | False |
| dbo | BM_PP_LAST_ADJUST | ADJUST_WMT | float | 8 | True |
| dbo | BM_PRODUCTION | WMT | float | 8 | True |
| dbo | BM_RECONCIL_LT_TREATED_1 | WMT | float | 8 | True |
| dbo | BM_RECONCIL_TC0_TREATED_1 | WMT | float | 8 | True |
| dbo | BM_RECONCIL_TC0_TREATED_1_FULL | WMT | float | 8 | True |
| dbo | BM_REDUCED_FOR_RECONCIL_GROUP | WMT | float | 8 | True |
| dbo | BM_REMAINING_RESERVES_TC0 | WMT | float | 8 | True |
| dbo | BM_TC0_WMT | WMT | float | 8 | True |
| dbo | BM_TC0_WMT_GROUP | WMT | float | 8 | True |
| dbo | CEK_RIT_HAULAGE | WMT | float | 8 | True |
| dbo | CF FOR PROD CORR ASSAYS 2 | WMT_SURVEY | float | 8 | True |
| dbo | CF_CHECK | WMT_PROD | float | 8 | True |
| dbo | CF_CHECK | WMT_SURVEY | float | 8 | True |
| dbo | CHECK_BACKCHARGE_HAULAGE_IWIP | WMT | float | 8 | True |
| dbo | CORPSAMPLEASSAY | WMT | float | 8 | True |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA_TREATED | WMT | float | 8 | True |
| dbo | DAILY_QUALITY_DISPATCH_TREATED | WMT | float | 8 | True |
| dbo | DAILY_STOCK_POS | WMT | float | 8 | True |
| dbo | DAILY_STOCK_POS | WMT_ADJ | float | 8 | True |
| dbo | DARONNE_CLEAN | WMT | float | 8 | True |
| dbo | DARONNE_HAUL | WMT | float | 8 | True |
| dbo | DARONNE_HAUL_AVG | WMT | float | 8 | True |
| dbo | DARONNE_LIM | WMT | float | 8 | True |
| dbo | DARONNE_QUERY | WMT | float | 8 | True |
| dbo | DARONNE_QUERY_LIM | WMT | float | 8 | True |
| dbo | DAY_WORK_wEQ_INFO | UNIT_START_HOUR_METER | float | 8 | True |
| dbo | DAY_WORK_wEQ_INFO | UNIT_END_HOUR_METER | float | 8 | True |
| dbo | DAY_WORK_wEQ_INFO | ROAD_STA_KM | float | 8 | True |
| dbo | DAY_WORK_wEQ_INFO | ROAD_END_KM | float | 8 | True |
| dbo | DAY_WORK_wEQ_INFO | DISTANCE_KM | float | 8 | True |
| dbo | DISPATCH FENI ACTUAL Treated 0 | WMT_LOG | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | HAULING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | REHANDLING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | VHGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | HGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | WCO WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | WST WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | LIM2 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | LIM1 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | CS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | TAILS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | WMT | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | WMT_METHOD | nvarchar | 4 | True |
| dbo | DISPATCH RESULTS DISTANCE | DISTANCE_ORI_DEST | float | 8 | True |
| dbo | DISPATCH RESULTS DISTANCE | DISTANCE_RIT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | HAULING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | REHANDLING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | VHGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | HGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | WCO WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | WST WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | LIM2 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | LIM1 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | CS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | TAILS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | WMT_METHOD | nvarchar | 4 | True |
| dbo | DISPATCH RESULTS LITE 2 | PLAN WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | DISTANCE_ORI_DEST | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 | DISTANCE_RIT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | PLAN WMT | nvarchar | 510 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CRD KM0 - KM2,5 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CRD KM2,5 - KM5,5 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CRD KM5,5 - KM7 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CSW KM3 - KM4 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CSW KM4 - KM5,7 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | GOMDI KM3,7 - KM3,8 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | BLB KM2,5 - KM5,7 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | BLB KM5,7 - KM10 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | BLB KM17 - KM20 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | HFC KM5,5 - KM6,4 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CBB KM7 - KM9 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CBB KM9 - KM15 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CBB KM15 - KM17 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | CBBB KM15 - KM17,5 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM7 - KM12 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM12 - KM15 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM15 - KM17 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM17 - KM21 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM21 - KM26 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM26 - KM27 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM27 - KM32 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM32 - KM37 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | KR KM37 - KM39 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | TF KM39 - KM45 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | TF KM45 - KM52 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | TF KM52 - KM60 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2 SECTION | TF KM60 - KM68 | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | HAULING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | REHANDLING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | VHGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | HGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | WCO WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | WST WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | LIM2 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | LIM1 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | CS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | TAILS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 2_OLD | PLAN WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | HAULING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | REHANDLING_WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | VHGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | HGS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | WCO WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | WST WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | LIM2 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | LIM1 WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | CS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | TAILS WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | WMT | float | 8 | True |
| dbo | DISPATCH RESULTS LITE 3 | PLAN WMT | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KM ORI | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KM DEST | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | DISTANCE GROSS (KM) | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CRD KM0 - KM2,5 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CRD KM2,5 - KM5,5 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CRD KM5,5 - KM7 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CSW KM3 - KM4 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CSW KM4 - KM5,7 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | GOMDI KM3,7 - KM3,8 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | BLB KM2,5 - KM5,7 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | BLB KM5,7 - KM10 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | BLB KM17 - KM20 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | HFC KM5,5 - KM6,4 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CBB KM7 - KM9 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CBB KM9 - KM15 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CBB KM15 - KM17 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | CBBB KM15 - KM17,5 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM7 - KM12 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM12 - KM15 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM15 - KM17 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM17 - KM21 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM21 - KM26 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM26 - KM27 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM27 - KM32 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM32 - KM37 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | KR KM37 - KM39 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | TF KM39 - KM45 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | TF KM45 - KM52 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | TF KM52 - KM60 | float | 8 | True |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | TF KM60 - KM68 | float | 8 | True |
| dbo | DISPATCH RSF ACTUAL Treated | ACTUAL WMT | float | 8 | True |
| dbo | DISPATCH WBN PLAN | PLAN WMT | float | 8 | True |
| dbo | DISPATCH WMT VERY SHORT TERM | KM ORI | float | 8 | True |
| dbo | DISPATCH WMT VERY SHORT TERM | KM DEST | float | 8 | True |
| dbo | DISPATCH WMT VERY SHORT TERM | WMT | float | 8 | True |
| dbo | DISTANCE_HAULING_CHECK | DISTANCE | float | 8 | True |
| dbo | DISTANCE_HAULING_CHECK | WMT | float | 8 | True |
| dbo | DISTANCE_MINING_CHECK | DISTANCE | float | 8 | True |
| dbo | DISTANCE_MINING_CHECK | WMT | float | 8 | True |
| dbo | DT_DENSITY_Haulage_Reclaiming | APPROX_DISTANCE | float | 8 | True |
| dbo | DT_DENSITY_Haulage_Reclaiming | DT/KM | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CRD KM0 - KM2,5 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CRD KM2,5 - KM5,5 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CRD KM5,5 - KM7 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CSW KM3 - KM4 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CSW KM4 - KM5,7 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON GOMDI KM3,7 - KM3,8 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON BLB KM2,5 - KM5,7 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON BLB KM5,7 - KM10 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON BLB KM17 - KM20 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON HFC KM5,5 - KM6,4 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CBB KM7 - KM9 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CBB KM9 - KM15 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CBB KM15 - KM17 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON CBBB KM15 - KM17,5 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM7 - KM12 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM12 - KM15 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM15 - KM17 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM17 - KM21 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM21 - KM26 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM26 - KM27 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM27 - KM32 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM32 - KM37 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON KR KM37 - KM39 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON TF KM39 - KM45 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON TF KM45 - KM52 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON TF KM52 - KM60 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD | DT ON TF KM60 - KM68 | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD_treated2 | APPROX_DISTANCE | float | 8 | True |
| dbo | DT_DENSITY_HAULROAD_treated2 | DT/KM | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING | WMT | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | WMT | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DISTANCE GROSS (KM) | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CRD KM0 - KM2,5 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CRD KM2,5 - KM5,5 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CRD KM5,5 - KM7 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CSW KM3 - KM4 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CSW KM4 - KM5,7 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON GOMDI KM3,7 - KM3,8 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON BLB KM2,5 - KM5,7 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON BLB KM5,7 - KM10 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON BLB KM17 - KM20 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON HFC KM5,5 - KM6,4 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CBB KM7 - KM9 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CBB KM9 - KM15 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CBB KM15 - KM17 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON CBBB KM15 - KM17,5 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM7 - KM12 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM12 - KM15 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM15 - KM17 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM17 - KM21 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM21 - KM26 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM26 - KM27 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM27 - KM32 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM32 - KM37 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON KR KM37 - KM39 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON TF KM39 - KM45 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON TF KM45 - KM52 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON TF KM52 - KM60 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated | DT ON TF KM60 - KM68 | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated3 | APPROX_DISTANCE | float | 8 | True |
| dbo | DT_DENSITY_RECLAIMING_treated3 | DT/KM | float | 8 | True |
| dbo | EQ_STATUS_WATER_MANAGEMENT | WORKING_HOURS | float | 8 | True |
| dbo | EQUIPMENT_LAST_COMMISSIONING | ODOMETER | nvarchar | 510 | True |
| dbo | EQUIPMENT_STATUS_FULL | WORKING_HOURS | float | 8 | True |
| dbo | EQUIPMENT_STATUS_FULL | OPERATING_HOURS | float | 8 | True |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS | WORKING HOURS | float | 8 | True |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS | OPERATING HOURS | int | 4 | False |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS_2 | WORKING HOURS | float | 8 | True |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS_2 | OPERATING HOURS | int | 4 | True |
| dbo | EQUIPMENTS_HOURLY_STATUS_DAILY | WORKING_HOURS | float | 8 | True |
| dbo | EQUIPMENTS_HOURLY_STATUS_SUMMARY | WORKING_HOURS | float | 8 | True |
| dbo | EQUIPMENTS_STATUS_BREAKDOWN | WORKING_HOURS | float | 8 | True |
| dbo | EQUIPMENTS_STATUS_BREAKDOWN | OPERATING_HOURS | float | 8 | True |
| dbo | FeNi Reclaiming Plan Treated 1 | PLANNED WMT | float | 8 | True |
| dbo | FeNi Reclaiming Plan Treated 2 | PLANNED WMT | float | 8 | True |
| dbo | FeNi Reclaiming Plan Treated 3 | PLANNED WMT | float | 8 | True |
| dbo | FENI_RECLAIMING_PLAN_WITH_GRADE | PLANNED WMT | float | 8 | True |
| dbo | FENI_REQUESTS_FIRST | WMT_REQUEST | float | 8 | True |
| dbo | FINANCE_MANAGEMENT | WMT_METHOD | nvarchar | 4 | True |
| dbo | FINANCE_MANAGEMENT | WMT | float | 8 | True |
| dbo | FINANCE_MANAGEMENT_BOD | WMT_METHOD | nvarchar | 4 | True |
| dbo | FINANCE_MANAGEMENT_BOD | WMT | float | 8 | True |
| dbo | FINANCE_MANAGEMENT_RE | WMT_METHOD | nvarchar | 4 | True |
| dbo | FINANCE_MANAGEMENT_RE | WMT_ORI | float | 8 | True |
| dbo | FINANCE_MANAGEMENT_RE | WMT | float | 8 | True |
| dbo | FINANCE_PHYSICAL_FLOW | WMT_METHOD | nvarchar | 4 | True |
| dbo | FINANCE_PHYSICAL_FLOW | WMT | float | 8 | True |
| dbo | FULL HAULAGE | SMU | nvarchar | 100 | True |
| dbo | FULL HAULAGE | WEIGHBRIDGE WMT | float | 8 | True |
| dbo | FULL HAULAGE | WBN SURVEY WMT | float | 8 | True |
| dbo | FULL HAULAGE | ORIGINAL WMT | float | 8 | True |
| dbo | FULL HAULAGE | WMT | float | 8 | True |
| dbo | FULL_ASSAYS_STOCK | WMT_CERT | float | 8 | True |
| dbo | FULL_FULL_PRODUCTION | WMT | float | 8 | True |
| dbo | FULL_PLAN | WMT_METHOD | varchar | 2 | False |
| dbo | FULL_PLAN | WMT | int | 4 | True |
| dbo | FULL_PRODUCTION | WMT | float | 8 | True |
| dbo | FULL_PRODUCTION | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_GROUP | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_GROUP | WMT | float | 8 | True |
| dbo | FULL_PRODUCTION_GROUP | WMT_BALANCE | float | 8 | True |
| dbo | FULL_PRODUCTION_ONLY | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_ONLY | WMT | float | 8 | True |
| dbo | FULL_PRODUCTION_RECOMPACT | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_RECOMPACT | WMT | float | 8 | True |
| dbo | FULL_PRODUCTION_RECOMPACT | WMT_DEST | float | 8 | True |
| dbo | FULL_PRODUCTION_RECOMPACT | WMT_ORI | float | 8 | True |
| dbo | FULL_PRODUCTION_REFORMAT | WMT | float | 8 | True |
| dbo | FULL_PRODUCTION_REFORMAT | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_VS_PLAN | WMT_METHOD | nvarchar | 4 | True |
| dbo | FULL_PRODUCTION_VS_PLAN | WMT | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 1 | WMT | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 2 | WMT | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 3 | KM ORI | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 3 | KM DEST | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 3 | WMT | float | 8 | True |
| dbo | HAUL VERY SHORT TERM TREATED 3 | PLAN WMT | float | 8 | True |
| dbo | HAULAGE_CLEAN | WMT | float | 8 | True |
| dbo | HAULAGE_CLEAN | WMT_METHOD | nvarchar | 4 | True |
| dbo | HAULAGE_CLEAN_FOR_DT | WMT | float | 8 | True |
| dbo | HAULAGE_CLEAN_FOR_DT | WMT_METHOD | nvarchar | 4 | True |
| dbo | HAULAGE_CLEAN2 | WMT | float | 8 | True |
| dbo | HAULAGE_CLEAN2 | WMT_METHOD | nvarchar | 4 | True |
| dbo | HAULAGE_COMPLETE | SMU | nvarchar | 100 | True |
| dbo | HAULAGE_COMPLETE | WMT | float | 8 | True |
| dbo | HAULAGE_COMPLETE | ORIGINAL WMT | float | 8 | True |
| dbo | HAULAGE_COMPLETE_VIA_BM | SMU | nvarchar | 100 | True |
| dbo | HAULAGE_COMPLETE_VIA_BM | WMT | float | 8 | True |
| dbo | HAULAGE_COMPLETE_VIA_BM | ORIGINAL WMT | float | 8 | True |
| dbo | HAULAGE_IWIP_CLEAN | WMT | float | 8 | True |
| dbo | HAULAGE_IWIP_VS_RECLAIM | WB_IWIP_WMT | float | 8 | True |
| dbo | HAULAGE_IWIP_VS_RECLAIM | R_WMT | float | 8 | True |
| dbo | HAULAGE_ORIGIN_PIT | WMT | float | 8 | True |
| dbo | HAULAGE_PER_PILE | WMT | float | 8 | True |
| dbo | HAULAGE_PER_PILE_AND_PLAN | ACT_WMT | float | 8 | True |
| dbo | HAULAGE_PER_PILE_AND_PLAN | PLAN_WMT | float | 8 | True |
| dbo | HAULAGE_PER_PILE_AND_PLAN_TEMPORAL | ACT_WMT | float | 8 | True |
| dbo | HAULAGE_PER_PILE_AND_PLAN_TEMPORAL | PLAN_WMT | float | 8 | True |
| dbo | HAULAGE_PILE_INFO | WMT | float | 8 | True |
| dbo | HAULAGE_PIT_ORIGIN_DESTINATION | WMT | float | 8 | True |
| dbo | HAULAGE_VS_IWIP_SYSTEM | WMT | float | 8 | True |
| dbo | HAULAGE_VS_OMR_ORI_DEST | HAUL_WMT | float | 8 | True |
| dbo | HAULAGE_VS_PROD_PILES_CF | PROD_WMT | float | 8 | True |
| dbo | HAULAGE_VS_PROD_PILES_CF | HAUL_WMT | float | 8 | True |
| dbo | HAULAGE_VS_RECLAIM | CONTRACTOR_WMT | float | 8 | True |
| dbo | HAULAGE_VS_RECLAIM | WMT_HAUL | float | 8 | True |
| dbo | HAULAGE_VS_RECLAIM | WMT_RECLAIM | float | 8 | True |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | WMT | float | 8 | True |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | ORIGIN_KM | float | 8 | True |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | WB_KM | float | 8 | True |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | DESTINATION_KM | float | 8 | True |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | DIFF_KM | float | 8 | True |
| dbo | HAULAGE_WITH_DT_TYPES | WMT | float | 8 | True |
| dbo | HAULAGE_WITH_DT_TYPES | WMT_METHOD | nvarchar | 4 | True |
| dbo | HRM | UNIT_START_HOUR_METER | float | 8 | True |
| dbo | HRM | UNIT_END_HOUR_METER | float | 8 | True |
| dbo | HRM | ROAD_STA_KM | float | 8 | True |
| dbo | HRM | ROAD_END_KM | float | 8 | True |
| dbo | HRM | DISTANCE_KM | float | 8 | True |
| dbo | LME_NEW_HMA | HMA | varchar | 4 | False |
| dbo | MINING_HAULAGE_PLAN_AND_ACTUAL | WMT | float | 8 | True |
| dbo | MINING_PLAN_3MRMP_DAILY | WMT_INSITU | float | 8 | True |
| dbo | MINING_PLAN_3MRMP_DAILY | WMT_ROM | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_BLOCKS | WMT | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_BLOCKS_VS_ACT | P_WMT | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_BLOCKS_VS_ACT | ACT_WMT | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_WITH_QUALITY | WMT | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_WITH_QUALITY | WMT_REC | float | 8 | True |
| dbo | MINING_PLAN_WEEKLY_WITH_QUALITY | WMT_ROM | float | 8 | True |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP | WMT | float | 8 | True |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX | WMT | float | 8 | True |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_Alan_test | WMT | float | 8 | True |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP | WMT | float | 8 | True |
| dbo | NEW_QC_RECONCIL_FOR_ARCGIS | WMT | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_TMM | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_SAP | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_RSAP | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_LIM | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_WST | float | 8 | True |
| dbo | OEE MINING WITH DEMOB | WMT_TS | float | 8 | True |
| dbo | OEE_HAULAGE_WMT_KM | WORKING_HOURS | float | 8 | True |
| dbo | OEE_HAULAGE_WMT_KM | OPERATING_HOURS | float | 8 | True |
| dbo | OEE_HAULAGE_WMT_KM | WMT | float | 8 | True |
| dbo | OEE_MINING_FULL | DISTANCE | float | 8 | True |
| dbo | OEE_MINING_FULL | WMT_SAP | float | 8 | True |
| dbo | OEE_MINING_FULL | WMT_LIM | float | 8 | True |
| dbo | OEE_MINING_FULL | WMT_WST | float | 8 | True |
| dbo | OEE_MINING_FULL | WORKING_HOURS | float | 8 | True |
| dbo | OEE_MINING_FULL | OPERATING_HOURS | float | 8 | True |
| dbo | OEE_MINING_NEW | WORKING HOURS | float | 8 | True |
| dbo | OEEDB_AUDB | unitIdLetters | int | 4 | True |
| dbo | OMR_TOS | WMT | float | 8 | True |
| dbo | OMR_TOS_CONTINUE | WMT | float | 8 | True |
| dbo | OMR_TOS_CONTINUE | SURVEY_WMT | float | 8 | True |
| dbo | PILES_SHARED_FENI_TREATED | WMT | float | 8 | True |
| dbo | PileTonnage | WMT | float | 8 | True |
| dbo | PLAN_DAY_WORKS_CLEAN | KM_START | float | 8 | True |
| dbo | PLAN_DAY_WORKS_CLEAN | KM_END | float | 8 | True |
| dbo | Prod and Calender | WMT | float | 8 | True |
| dbo | Prod and Calender | WMT2 | float | 8 | True |
| dbo | PROD_ASSAYS | WMT | float | 8 | True |
| dbo | PROD_CALENDAR_ASSAYS | WMT | float | 8 | True |
| dbo | PROD_CORR_AND_PLAN | WMT | float | 8 | True |
| dbo | PROD_CORR_AND_PLAN | WMT_ROM | float | 8 | True |
| dbo | PROD_CORR_ASSAYS | WMT | float | 8 | True |
| dbo | PROD_CORR_ASSAYS_COG | WMT | float | 8 | True |
| dbo | PROD_CORR_ASSAYS_COG_2 | WMT | float | 8 | True |
| dbo | PROD_CORR_ASSAYS_COG_3 | WMT_ROM | float | 8 | True |
| dbo | PROD_CORR_ASSAYS_COG_3 | WMT | float | 8 | True |
| dbo | PROD_CORR_ASSAYS_COG_4 | WMT | float | 8 | True |
| dbo | PROD_VIA_BM | WMT | float | 8 | True |
| dbo | PRODUCTION_MINING_PIT | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT_COORDINATES_B_S | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y_CONVERT_NEW_BM | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT_DISTANCE_CALC | WMT | float | 8 | True |
| dbo | PRODUCTION_PIT_DISTANCE_CALC | DISTANCE | float | 8 | True |
| dbo | PRODUCTION_PIT_HOURLY | DISTANCE | float | 8 | True |
| dbo | PRODUCTION_PIT_HOURLY_FULL | DISTANCE | float | 8 | True |
| dbo | PRODUCTION_PIT_HOURLY_TF | DISTANCE | float | 8 | True |
| dbo | PRODUCTION_PIT_WRONG_ELEVATION | WMT | float | 8 | True |
| dbo | QC ALL DATA 2 | BM_WMT | float | 8 | True |
| dbo | QC ALL DATA 2 | RATIO_WMT_TOS/BM | float | 8 | True |
| dbo | QC ALL DATA 2 | WMT | float | 8 | True |
| dbo | QC PIT-TOS OMR SUMMARY | WMT | float | 8 | True |
| dbo | QC TOS BALANCE | WMT | float | 8 | True |
| dbo | QC TOS BALANCE | RATIO_WMT_TOS/BM | float | 8 | True |
| dbo | QC TOS BALANCE | MAX_WMT_SHARED | float | 8 | True |
| dbo | QC TOS BALANCE | MIN_WMT_SHARED | float | 8 | True |
| dbo | QC TOS_VS_POS | WMT_PROD | float | 8 | True |
| dbo | QC TOS_VS_POS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_ALL_STOCK | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_ALL_STOCK | BM_WMT | float | 8 | True |
| dbo | QC_COMPOSITE_ASSAY | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_BLOCK | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_BLOCK | HGS_WMT | float | 8 | True |
| dbo | QC_COMPOSITE_BLOCK_SELECT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_BLOCK_SELECT | HGS_WMT | float | 8 | True |
| dbo | QC_COMPOSITE_BLOCK_VIA_PIT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_DUMP | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_DUMP_VIA_PIT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_HAULAGE | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_POS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_POS_VIA_BM | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_POS_VIA_ML | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_POS_VIA_TOS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_POS_VIA_YARD | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_CERT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_IndividualBlock | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_BM | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_BM | BM_WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_BM_ORI | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_BM_ORI | BM_WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_HAULAGE | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_PIT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_POS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_TOS_VIA_YARD | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_WCO | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD_DIRECT | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD_STOCK_ORIGINAL | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD_VIA_BM | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD_VIA_POS | WMT | float | 8 | True |
| dbo | QC_COMPOSITE_YARD_VIA_TOS | WMT | float | 8 | True |
| dbo | QC_POS_DETAILS | POS_WMT_CERT | float | 8 | True |
| dbo | QC_POS_DETAILS | YARD_WMT_CERT | float | 8 | True |
| dbo | QC_POS_DETAILS | SMU | nvarchar | 100 | True |
| dbo | QC_POS_DETAILS | HAUL_WMT | float | 8 | True |
| dbo | QC_POS_DETAILS | PROD_WMT | float | 8 | True |
| dbo | QC_STOCK_ALL | WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_ALL | PROP_WMT | float | 8 | True |
| dbo | QC_STOCK_ALL_VIA_ALL | POS_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_ALL_VIA_ALL | YARD_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_ALL_VIA_ALL_OLD | POS_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_ALL_VIA_ALL_OLD | YARD_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_POS_VIA_ALL | POS_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_POS_VIA_ALL | YARD_WMT_CERT | float | 8 | True |
| dbo | QC_STOCK_TOS_FOR_ANALYZE | RATIO_WMT | float | 8 | True |
| dbo | QC_STOCK_TOS_FOR_ANALYZE | BM_WMT | float | 8 | True |
| dbo | QC_STOCK_TOS_FOR_ANALYZE | TOS_WMT | float | 8 | True |
| dbo | QC_STOCK_TOS_VIA_ALL | BM_WMT | float | 8 | True |
| dbo | QC_STOCK_TOS_VIA_ALL | TOS_WMT | float | 8 | True |
| dbo | RECLAIMING | WEIGHBRIDGE WMT | float | 8 | True |
| dbo | RECLAIMING DETAIL | WMT | float | 8 | True |
| dbo | RECLAIMING DETAIL 2 | WMT | float | 8 | True |
| dbo | RECLAIMING DETAIL 3 | WMT | float | 8 | True |
| dbo | RECLAIMING DETAIL 4 | WMT | float | 8 | True |
| dbo | RECLAIMING_ORIGIN_DESTINATION | WMT | float | 8 | True |
| dbo | RECLAIMING_REJECT_POURCENTAGE | REJECT_WMT | float | 8 | True |
| dbo | RECLAIMING_REJECT_POURCENTAGE | RECLAIMING_WMT | float | 8 | True |
| dbo | RECLAIMING_REJECT_POURCENTAGE_DATE | REJECT_WMT | float | 8 | True |
| dbo | RECLAIMING_REJECT_POURCENTAGE_DATE | RECLAIMING_WMT | float | 8 | True |
| dbo | RECLAIMING_WB_TREATED_3_JOIN | WMT | float | 8 | True |
| dbo | RECLAIMNG WB TREATED GROUPED | WMT | float | 8 | True |
| dbo | RECONCIL_OK | WMT | float | 8 | True |
| dbo | RECONCIL_ST_LT | WMT | float | 8 | True |
| dbo | RECONCIL_TC0 | WMT | float | 8 | True |
| dbo | REMAINING_RESERVES_BM_OK | WMT | float | 8 | True |
| dbo | REQUEST_VS_HAULAGE | WMT_REQUEST | float | 8 | True |
| dbo | REQUEST_VS_HAULAGE | WMT_HAULAGE | float | 8 | True |
| dbo | ROLLING_MINE_PLAN_TREATED | WMT_ROM | float | 8 | True |
| dbo | ROLLING_MINE_PLAN_TREATED | DAILY_AVERAGE_WMT | float | 8 | True |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT | ORIGIN_KM | nvarchar | 100 | True |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT | DESTINATION_KM | nvarchar | 100 | True |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR | ORIGIN_KM | nvarchar | 100 | True |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR | DESTINATION_KM | nvarchar | 100 | True |
| dbo | STOCK_CERTIFICATE_NEWS | WMT_CARRIED | float | 8 | True |
| dbo | STOCK_CERTIFICATE_NEWS | WMT_SURVEY | float | 8 | True |
| dbo | STOCK_CERTIFICATE_NEWS | WMT_SENT | float | 8 | True |
| dbo | STOCK_CERTIFICATE_NEWS | WMT_CERT | float | 8 | True |
| dbo | STOCK_INFO_FULL | WMT_HAUL | float | 8 | True |
| dbo | STOCK_INFO_FULL | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_INFOS | WMT_HAUL | float | 8 | True |
| dbo | STOCK_INFOS | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_INFOS | WMT_POS_SENT | float | 8 | True |
| dbo | STOCK_INFOS | WMT_YARD_SENT | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_METHOD | nvarchar | 4 | True |
| dbo | STOCK_MANAGEMENT | WMT | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_POS_SENT | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_YARD_SENT | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_BALANCE | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_ADJ | float | 8 | True |
| dbo | STOCK_MANAGEMENT | WMT_AUTO_BALANCE | float | 8 | True |
| dbo | STOCK_MANAGEMENT | POS_WMT_CERT | float | 8 | True |
| dbo | STOCK_MANAGEMENT | YARD_WMT_CERT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_METHOD | nvarchar | 4 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_SENT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_SENT_ORIGINAL | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_SENT_RATE | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | TO_SEND_TOTAL_WMT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_HAUL | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | WMT_ADJ | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | POS_WMT_CERT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE | YARD_WMT_CERT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_METHOD | nvarchar | 4 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_SENT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_SENT_ORIGINAL | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_SENT_RATE | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | TO_SEND_TOTAL_WMT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_HAUL | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | WMT_ADJ | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | POS_WMT_CERT | float | 8 | True |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | YARD_WMT_CERT | float | 8 | True |
| dbo | STOCK_ORIGIN_PIT_BY_WMT | WMT | float | 8 | True |
| dbo | STOCK_REQUESTS_TREATED | MAX_WMT_REQUEST | float | 8 | True |
| dbo | STOCK_REQUESTS_TREATED | MIN_WMT_REQUEST | float | 8 | True |
| dbo | STOCK_REQUESTS_TREATED_2 | MAX_WMT_SHARED | float | 8 | True |
| dbo | STOCK_REQUESTS_TREATED_2 | MIN_WMT_SHARED | float | 8 | True |
| dbo | STOCK_STATUS_FLOW | WMT_HAUL | float | 8 | True |
| dbo | STOCK_STATUS_FLOW | WMT_RECLAIM | float | 8 | True |
| dbo | STOCK_WMT_EVOLUTION | SURVEY_WMT | float | 8 | True |
| dbo | STOCK_WMT_EVOLUTION | PROD_WMT | float | 8 | True |
| dbo | STOCK_WMT_EVOLUTION | WMT_CUMULATIVE | float | 8 | True |
| dbo | SUM PROD WMT FOR CORR | WMT_ACTUAL | float | 8 | True |
| dbo | SUM WMT SURVEY | WMT_SURVEY | float | 8 | True |
| dbo | SURVEY POS CONSOLIDATED | WMT | float | 8 | True |
| dbo | SURVEY_POS_DATED | IS_MAX_WMT | varchar | 3 | False |
| dbo | SURVEY_POS_DATED | WMT | float | 8 | True |
| dbo | SURVEY_POS_ESTIMATE_HAULAGE | WMT_SURVEY | float | 8 | True |
| dbo | SURVEY_POS_ESTIMATE_HAULAGE | WMT_PREVIOUS | float | 8 | True |
| dbo | SURVEY_POS_ESTIMATE_HAULAGE | WMT_EST_HAULAGE | float | 8 | True |
| dbo | SURVEY_POS_FOR_PROD | WMT | float | 8 | True |
| dbo | SURVEY_POS_TC | WMT | float | 8 | True |
| dbo | SURVEY_STOCK_MAX | WMT | float | 8 | True |
| dbo | test sa mere | WMT_ROM_MONTHLY | float | 8 | True |
| dbo | test sa mere | WMT_DAILY | float | 8 | True |
| dbo | TEST_CAROTTE | WMT | float | 8 | True |
| dbo | TOS FOLLOW TREATED | WMT_TOTAL | float | 8 | True |
| dbo | TOS FOLLOW TREATED 2 | WMT_TOTAL | float | 8 | True |
| dbo | TOS_PILES_WMT_WB_RIT_MINING | WMT_WB | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT_SURVEY_EST | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT_SURVEY_GAP | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT_SURVEY | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT_TRANSFER | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT_ORI | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION | WMT | float | 8 | True |
| dbo | TOS_SURVEY_ESTIMATION2 | WMT | float | 8 | True |
| dbo | TOS_SURVEY_trial | WMT_MINING | float | 8 | True |
| dbo | TOS_SURVEY_trial | WMT_MINING_CUMULATIVE | float | 8 | True |
| dbo | trial cek tos follow vs haulage iwip  | TS_WMT | float | 8 | True |
| dbo | trial cek tos follow vs haulage iwip  | WMT_HAULAGE | float | 8 | True |
| dbo | trial cek tos follow vs haulage iwip  | SELISIH_WMT | float | 8 | True |
| dbo | UNIT_TRIPS_HUAFEI_RSF | ORIGIN_KM | nvarchar | 100 | True |
| dbo | UNIT_TRIPS_HUAFEI_RSF | DESTINATION_KM | nvarchar | 100 | True |
| dbo | vOSPAT_RESULTS | TerminalTag | int | 4 | True |
| dbo | vOSPAT_RESULTS | ResultType | int | 4 | True |
| dbo | vOSPAT_RESULTS | ResultScore | float | 8 | True |
| dbo | vOSPAT_RESULTS | ResultClass | nvarchar | 510 | True |
| dbo | vw_HAULAGE_GROUP | WMT | float | 8 | True |
| dbo | w2_EQUIPMENTS_STATUS | HOUR_METER_START | float | 8 | True |
| dbo | w2_EQUIPMENTS_STATUS | HOUR_METER_END | float | 8 | True |
| dbo | w2_EQUIPMENTS_STATUS | USAGE_KM_METER | float | 8 | True |
| dbo | WAITING_TIME_DIFFERENCE | FUEL_FILLING_TIME | time | 5 | True |
| dbo | WAITING_TIME_FIX | FUEL_FILLING_TIME | time | 5 | True |
| dbo | WMT_3RD_PARTY_LAST | WMT_SENT | float | 8 | True |
| dbo | WMT_3RD_PARTY_LAST | WMT_SENT_ORIGINAL | float | 8 | True |
| dbo | WMT_3RD_PARTY_LAST | WMT_SENT_RATE | float | 8 | True |
| dbo | WMT_LAST_CERT | WMT_POS_SENT | float | 8 | True |
| dbo | WMT_LAST_CERT | WMT_YARD_SENT | float | 8 | True |


**FMS_DB — tables: 31 columns**

| schema_name | table_name | column_name | data_type | max_length | is_nullable | column_description |
|---|---|---|---|---|---|---|
| dbo | auto_kmFMS_PLAYBACK_TRACK_DATA | SectionKM | float | 8 | True |  |
| dbo | auto_spFMS_PLAYBACK_TRACK_DATA | SP_DISTANCE_M | int | 4 | True |  |
| dbo | autoFMS_SECURITY_INCIDENT_KILOMETER | SectionKM | float | 8 | True |  |
| dbo | FMS_APP_STATE | PAYLOAD | nvarchar | -1 | True |  |
| dbo | FMS_GPS_Historical | DISTANCE | float | 8 | True |  |
| dbo | FMS_HAUL_CYCLES | CYCLE_ID | int | 4 | False |  |
| dbo | FMS_INTERVENTION_EVENT_DATA | mileage | nvarchar | 510 | True |  |
| dbo | FMS_PLAYBACK_STAY_DATA | mileage | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_24H | DISTANCE | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | distance | float | 8 | True |  |
| dbo | FMS_QUALITY_DISPATCH | WMT | float | 8 | True |  |
| dbo | FMS_RISK_DATA | mileage | float | 8 | True |  |
| dbo | FMS_SECURITY_INCIDENT_DATA | mileage | float | 8 | True |  |
| dbo | FMS_TRUCK_CYCLES | CYCLES | int | 4 | True |  |
| dbo | LV_PLAN | KM_From | decimal | 9 | True |  |
| dbo | LV_PLAN | KM_To | decimal | 9 | True |  |
| dbo | RES_CRITICAL_ZONES | KM_From | decimal | 5 | True |  |
| dbo | RES_CRITICAL_ZONES | KM_To | decimal | 5 | True |  |
| dbo | RES_SPEED_LIMIT_ZONES | Chainage Range (KM) | nvarchar | 510 | True |  |
| dbo | RES_SPEED_LIMIT_ZONES | Speed Limit (km/h) | float | 8 | True |  |
| dbo | RES_SPEED_LIMIT_ZONES | KM_From | decimal | 5 | True |  |
| dbo | RES_SPEED_LIMIT_ZONES | KM_To | decimal | 5 | True |  |
| dbo | RES_WATER_FILLING_POINTS | Dispenser_Count | int | 4 | True |  |
| dbo | SIM_PLAN_ANALOGUE_CACHE | result_json | nvarchar | -1 | False |  |
| dbo | SIM_PLAN_DAY_KPI | wmt | float | 8 | False |  |
| dbo | SIM_PLAN_DAY_KPI | payload_t | float | 8 | True |  |
| dbo | SIM_PLAN_DAY_KPI | avg_speed_kmh | float | 8 | True |  |
| dbo | SIM_PLAN_EDGE | outcome_delta | float | 8 | True |  |
| dbo | WT_DAILY_PLAN | KM_From | int | 4 | False |  |
| dbo | WT_DAILY_PLAN | KM_To | int | 4 | False |  |
| dbo | WT_DAILY_PLAN | Target_Refills | int | 4 | False |  |


**FMS_DB — views: 74 columns**

| schema_name | view_name | column_name | data_type | max_length | is_nullable |
|---|---|---|---|---|---|
| dbo | CCR_RISK_EVENT_ACTIONS | Mileage(Km) | float | 8 | True |
| dbo | CCR_RISK_EVENT_ACTIONS | Multi_Event_Flag | int | 4 | False |
| dbo | EQUIPMENTS_RADIO_STATUS | HOURMETER | float | 8 | True |
| dbo | FMS_HRM_SUPERVISION | SECTIONKM | float | 8 | True |
| dbo | FMS_HRM_SUPERVISION | DISTANCE_M | float | 8 | True |
| dbo | FMS_INTERVENTION_EVENT_CLEAN | Mileage(Km) | nvarchar | 510 | True |
| dbo | FMS_PLAYBACK_TRACK_CLEAN | distance_m | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_CLEAN | SectionKM | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | distance_m | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | SectionKM | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | LAST_SectionKM | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | SectionKM_CHANGED | varchar | 6 | False |
| dbo | FMS_PLAYBACK_TRACK_WORKINGHOURS | WORKING_HOURS | float | 8 | True |
| dbo | FMS_PLAYBACK_TRACK_WORKINGHOURS | distance_m | float | 8 | True |
| dbo | FMS_RISK_CLEAN | Mileage(Km) | float | 8 | True |
| dbo | FMS_SECURITY_INCIDENT_CLEAN | Drivingmileage | float | 8 | True |
| dbo | FMS_SECURITY_INCIDENT_CLEAN | SectionKM | float | 8 | True |
| dbo | FMS_SECURITY_INCIDENT_KILOMETER | SectionKM | float | 8 | True |
| dbo | IDLE_EVENTS_WT | Driving_Mileage | decimal | 9 | True |
| dbo | IDLE_EVENTS_WT | Dispenser_Count | int | 4 | True |
| dbo | LV_GEOFENCE_EVENTS | Driving_Mileage | decimal | 9 | True |
| dbo | LV_GEOFENCE_EVENTS | SectionKM | decimal | 9 | True |
| dbo | OSPAT_RESULTS | TerminalTag | int | 4 | True |
| dbo | OSPAT_RESULTS | ResultType | int | 4 | True |
| dbo | OSPAT_RESULTS | ResultScore | float | 8 | True |
| dbo | OSPAT_RESULTS | ResultClass | nvarchar | 510 | True |
| dbo | OVERSPEED_EVENTS | Driving_Mileage | decimal | 9 | True |
| dbo | OVERSPEED_EVENTS | SectionKM | decimal | 9 | True |
| dbo | VW_FMS_EVENTS | Driving_Mileage | decimal | 9 | True |
| dbo | VW_FMS_EVENTS | SectionKM | decimal | 9 | True |
| dbo | VW_LV_ACTIVE_PLAN | KM_From | decimal | 9 | True |
| dbo | VW_LV_ACTIVE_PLAN | KM_To | decimal | 9 | True |
| dbo | VW_WT_DAILY_PLAN | KM_From | int | 4 | False |
| dbo | VW_WT_DAILY_PLAN | KM_To | int | 4 | False |
| dbo | VW_WT_DAILY_PLAN | Target_Refills | int | 4 | False |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Refill_Sequence | bigint | 8 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Refill_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Next_Refill_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Max_Cycle_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | KM_From | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | KM_To | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Target_Refills | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Track_Points_After_Refill | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | In_Zone_Track_Points_After_Refill | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | In_Other_Zone_Track_Points_After_Refill | int | 4 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | Total_Distance_After_Refill_KM | decimal | 9 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | In_Zone_Distance_After_Refill_KM | decimal | 9 | True |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | In_Other_Zone_Distance_After_Refill_KM | decimal | 9 | True |
| dbo | VW_WT_REFILL_CYCLES | Refill_Sequence | bigint | 8 | True |
| dbo | VW_WT_REFILL_CYCLES | Refill_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLES | Next_Refill_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLES | Max_Cycle_End_Time | datetime | 8 | True |
| dbo | VW_WT_REFILL_CYCLES | Is_Planned_WF_Refill | int | 4 | False |
| dbo | VW_WT_REFILL_CYCLES | Refill_WF_Status | varchar | 10 | False |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | KM_From | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | KM_To | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | Target_Refills | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | Total_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | In_Zone_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | Out_Of_Zone_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | KM_From | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | KM_To | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Target_Refills | int | 4 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Total_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | In_Zone_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Out_Of_Zone_Distance_Travelled_KM | decimal | 9 | True |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Watering_KM_In_Zone_After_Refill | decimal | 17 | False |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Watering_Track_Points_In_Zone_After_Refill | int | 4 | False |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Watering_KM_In_Other_Zone_After_Refill | decimal | 17 | False |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | Watering_Track_Points_In_Other_Zone_After_Refill | int | 4 | False |
| dbo | VW_WT_ZONE_COVERAGE | KM_From | int | 4 | False |
| dbo | VW_WT_ZONE_COVERAGE | KM_To | int | 4 | False |
| dbo | VW_WT_ZONE_COVERAGE | Post_Refill_KM_In_Zone | decimal | 9 | True |
| dbo | WATER_POINTS_GEOFENCE | Dispenser_Count | int | 4 | True |


## 8. Appendix — remaining step outputs


### WBN_DATABASE — Step 1: fuel-named objects (56 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | auto_node_STOCK_ID | USER_TABLE |  |
| dbo | autoQC_STOCK_ALL_VIA_ALL | USER_TABLE |  |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA | USER_TABLE |  |
| dbo | ORE STOCK SALES | USER_TABLE |  |
| dbo | ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE | USER_TABLE |  |
| dbo | S123_STOCK_SHAPE | USER_TABLE |  |
| dbo | S123_STOCK_SHAPE_OLD | USER_TABLE |  |
| dbo | SHAPE_STOCK_AREA | USER_TABLE |  |
| dbo | START LIM STOCK | USER_TABLE |  |
| dbo | STOCK_REQUESTS | USER_TABLE |  |
| dbo | STOCK_STATUS | USER_TABLE |  |
| dbo | STOCK_STATUS_HAULAGE_GGSHEET | USER_TABLE |  |
| dbo | _LIMONITE_DAILY_STOCK | VIEW |  |
| dbo | auto_view_QC_STOCK_ALL_VIA_ALL | VIEW |  |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA_TREATED | VIEW |  |
| dbo | DAILY_STOCK_POS | VIEW |  |
| dbo | FULL_ASSAYS_STOCK | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP | VIEW |  |
| dbo | QC_COMPOSITE_ALL_STOCK | VIEW |  |
| dbo | QC_COMPOSITE_YARD_STOCK_ORIGINAL | VIEW |  |
| dbo | QC_STOCK_ALL | VIEW |  |
| dbo | QC_STOCK_ALL_VIA_ALL | VIEW |  |
| dbo | QC_STOCK_ALL_VIA_ALL_OLD | VIEW |  |
| dbo | QC_STOCK_POS_VIA_ALL | VIEW |  |
| dbo | QC_STOCK_TOS_FOR_ANALYZE | VIEW |  |
| dbo | QC_STOCK_TOS_VIA_ALL | VIEW |  |
| dbo | QUARRY_STOCK_BLEND_MANAGEMENT | VIEW |  |
| dbo | QUARRY_STOCK_BLEND_MANAGEMENT_TREATED | VIEW |  |
| dbo | QUARRY_STOCK_CRUSHED_MANAGEMENT | VIEW |  |
| dbo | QUARRY_STOCK_CRUSHED_MANAGEMENT_TREATED | VIEW |  |
| dbo | QUARRY_STOCK_TOS_MANAGEMENT | VIEW |  |
| dbo | QUARRY_STOCK_TOS_MANAGEMENT_TREATED | VIEW |  |
| dbo | RECLAIMING_MATCH_ASSAY_STOCK_ID2 | VIEW |  |
| dbo | S123_STOCK_SHAPE_QGIS_TEST | VIEW |  |
| dbo | STOCK_CERTIFICATE_NEWS | VIEW |  |
| dbo | STOCK_INFO_FULL | VIEW |  |
| dbo | STOCK_INFOS | VIEW |  |
| dbo | STOCK_MANAGEMENT | VIEW |  |
| dbo | STOCK_MANAGEMENT_RE | VIEW |  |
| dbo | STOCK_MANAGEMENT_RE_WITH_FENI_PLAN | VIEW |  |
| dbo | STOCK_ORIGIN_PIT | VIEW |  |
| dbo | STOCK_ORIGIN_PIT_BY_WMT | VIEW |  |
| dbo | STOCK_POS_YARD | VIEW |  |
| dbo | STOCK_REQUESTS_TREATED | VIEW |  |
| dbo | STOCK_REQUESTS_TREATED_2 | VIEW |  |
| dbo | STOCK_SHAPE | VIEW |  |
| dbo | STOCK_SHAPE_LAST | VIEW |  |
| dbo | STOCK_STATUS_FLOW | VIEW |  |
| dbo | STOCK_STATUS_FULL | VIEW |  |
| dbo | STOCK_STATUS_SIMPLE | VIEW |  |
| dbo | STOCK_STATUS_STATUS | VIEW |  |
| dbo | STOCK_TYPE_ALL | VIEW |  |
| dbo | STOCK_WMT_EVOLUTION | VIEW |  |
| dbo | SURVEY_STOCK_MAX | VIEW |  |


### WBN_DATABASE — Step 5: equipment/fleet/haul objects (229 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | auto_edge_HAULAGE | USER_TABLE |  |
| dbo | autoHAULAGE_VS_PROD_MONTHLY_CF | USER_TABLE |  |
| dbo | Calendar_Svy_topo_by_deposit | USER_TABLE |  |
| dbo | CONTRACTOR FOLLOW UP | USER_TABLE |  |
| dbo | CONTRACTOR_DEPOSIT | USER_TABLE |  |
| dbo | DAY_WORKS | USER_TABLE |  |
| dbo | DAY_WORKS_PLAN_DAILY | USER_TABLE |  |
| dbo | DAYWORK_REQUEST | USER_TABLE |  |
| dbo | DISPATCH HAULAGE TF | USER_TABLE |  |
| dbo | DISPATCH ROADS | USER_TABLE |  |
| dbo | DISPATCH ROADS OLD | USER_TABLE |  |
| dbo | DISPATCH WBN PLAN SHIFT | USER_TABLE |  |
| dbo | DISTANCE_HAULING | USER_TABLE |  |
| dbo | DISTANCE_MINING | USER_TABLE |  |
| dbo | EQUIPMENTS | USER_TABLE |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | USER_TABLE |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | USER_TABLE |  |
| dbo | EQUIPMENTS_OLD | USER_TABLE |  |
| dbo | EQUIPMENTS_PLAN | USER_TABLE |  |
| dbo | EQUIPMENTS_STATUS | USER_TABLE |  |
| dbo | EQUIPMENTS_WORKS | USER_TABLE |  |
| dbo | EXC_TRIMMING | USER_TABLE |  |
| dbo | FMS_TOS_STATUS | USER_TABLE |  |
| dbo | HAUL_ROAD_STA | USER_TABLE |  |
| dbo | HAULAGE | USER_TABLE |  |
| dbo | HAULAGE CONTRACTORS | USER_TABLE |  |
| dbo | HAULAGE_ADJ | USER_TABLE |  |
| dbo | HAULAGE_IWIP | USER_TABLE |  |
| dbo | HAULAGE_IWIP_EXT | USER_TABLE |  |
| dbo | HAULAGE_M_DOME_2026_IWIP_PLAN | USER_TABLE |  |
| dbo | HAULAGE_REPORT | USER_TABLE |  |
| dbo | HRM_CONTRACT_EQUIPMENT | USER_TABLE |  |
| dbo | HRM_MAJOR_ROADWORK | USER_TABLE |  |
| dbo | LOCATION_WB_SH | USER_TABLE |  |
| dbo | MINING_FLASH_REPORT_EQUIPMENT | USER_TABLE |  |
| dbo | MINING_FLASH_REPORT_FLEET_PROD | USER_TABLE |  |
| dbo | POS FOLLOW UP | USER_TABLE |  |
| dbo | POS POSSIBILITY For HAULAGE | USER_TABLE |  |
| dbo | PP_MINED_NEW_RECONCIL_MENG | USER_TABLE |  |
| dbo | PP_MINED_YTD_OK | USER_TABLE |  |
| dbo | PP_REMAIN_INPIT_MINEOUT | USER_TABLE |  |
| dbo | PRODUCTION_ACTIVITY_PIT | USER_TABLE |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | USER_TABLE |  |
| dbo | PRODUCTION_PIT_OLD | USER_TABLE |  |
| dbo | PRODUCTION_PIT_PRELIM_auto | USER_TABLE |  |
| dbo | QC PIT-TOS OMR | USER_TABLE |  |
| dbo | QS_LIMS_RIM_CK | USER_TABLE |  |
| dbo | ROLLING_MINE_PLAN | USER_TABLE |  |
| dbo | RSF_HAULING_DATA | USER_TABLE |  |
| dbo | RSF_PER_LOCATION | USER_TABLE |  |
| dbo | S123_TOS_STATUS | USER_TABLE |  |
| dbo | SAMPLING_CONTRACTOR | USER_TABLE |  |
| dbo | STOCK_STATUS | USER_TABLE |  |
| dbo | STOCK_STATUS_HAULAGE_GGSHEET | USER_TABLE |  |
| dbo | SURVEY POS | USER_TABLE |  |
| dbo | tempHAULAGE_IWIP | USER_TABLE |  |
| dbo | TOS_DUMP_COORDINATES | USER_TABLE |  |
| dbo | TOS_STATUS | USER_TABLE |  |
| dbo | VERY VERY SHORT TERM PIT SERVICE | USER_TABLE |  |
| dbo | ARCGIS_EQUIPMENTS_INFO_APP | VIEW |  |
| dbo | BATCH COMPOSITES | VIEW |  |
| dbo | CALENDAR_SHIFT | VIEW |  |
| dbo | CEK_RIT_HAULAGE | VIEW |  |
| dbo | CHECK_BACKCHARGE_HAULAGE_IWIP | VIEW |  |
| dbo | CONTRACTOR FOLLOW UP DATE 2 | VIEW |  |
| dbo | CONTRACTOR_FOLLOW_UP_DATE | VIEW |  |
| dbo | CONTRACTOR_FU_DT_VARIATION | VIEW |  |
| dbo | DAILY_STOCK_POS | VIEW |  |
| dbo | DARONNE_HAUL | VIEW |  |
| dbo | DARONNE_HAUL_AVG | VIEW |  |
| dbo | DATE HAULAGE RECLAIMING | VIEW |  |
| dbo | DAY_WORK_wEQ_INFO | VIEW |  |
| dbo | DAY_WORKS_RIM__NO_FMS | VIEW |  |
| dbo | DISPATCH FENI & WBN ACTUAL DT SHIFT | VIEW |  |
| dbo | DISPATCH RESULTS DISTANCE | VIEW |  |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | VIEW |  |
| dbo | DISTANCE_HAULING_CHECK | VIEW |  |
| dbo | DISTANCE_MINING_CHECK | VIEW |  |
| dbo | DT_DENSITY_Haulage_Reclaiming | VIEW |  |
| dbo | DT_DENSITY_HAULROAD | VIEW |  |
| dbo | DT_DENSITY_HAULROAD_treated | VIEW |  |
| dbo | DT_DENSITY_HAULROAD_treated2 | VIEW |  |
| dbo | EQ_STATUS_WATER_MANAGEMENT | VIEW |  |
| dbo | EQUIPMENT_LAST_COMMISSIONING | VIEW |  |
| dbo | EQUIPMENT_NEW_ID | VIEW |  |
| dbo | EQUIPMENT_PLAN_ACTUAL | VIEW |  |
| dbo | EQUIPMENT_STATUS_FULL | VIEW |  |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS | VIEW |  |
| dbo | EQUIPMENT_STATUS_WORKING_HOURS_2 | VIEW |  |
| dbo | EQUIPMENTS_CLEAN | VIEW |  |
| dbo | EQUIPMENTS_CLEAN2 | VIEW |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_COMPACT | VIEW |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_DAILY | VIEW |  |
| dbo | EQUIPMENTS_HOURLY_STATUS_SUMMARY | VIEW |  |
| dbo | EQUIPMENTS_QR_CODE_VALUE | VIEW |  |
| dbo | EQUIPMENTS_STATUS_BREAKDOWN | VIEW |  |
| dbo | equipments_status_last_breakdown | VIEW |  |
| dbo | FULL HAULAGE | VIEW |  |
| dbo | HAUL VERY SHORT TERM TREATED 1 | VIEW |  |
| dbo | HAUL VERY SHORT TERM TREATED 2 | VIEW |  |
| dbo | HAUL VERY SHORT TERM TREATED 3 | VIEW |  |
| dbo | HAULAGE_BY_CONTRACTOR_TRUCK | VIEW |  |
| dbo | HAULAGE_CLEAN | VIEW |  |
| dbo | HAULAGE_CLEAN_FOR_DT | VIEW |  |
| dbo | HAULAGE_CLEAN2 | VIEW |  |
| dbo | HAULAGE_COMPLETE | VIEW |  |
| dbo | HAULAGE_COMPLETE_VIA_BM | VIEW |  |
| dbo | HAULAGE_ERROR | VIEW |  |
| dbo | HAULAGE_GET_IWIP_PLAN_TICKET_NO | VIEW |  |
| dbo | HAULAGE_GET_IWIP_TICKET_NO | VIEW |  |
| dbo | HAULAGE_IWIP_CLEAN | VIEW |  |
| dbo | HAULAGE_IWIP_VS_RECLAIM | VIEW |  |
| dbo | HAULAGE_IWIP_WASTE | VIEW |  |
| dbo | HAULAGE_LIM_BATCH | VIEW |  |
| dbo | HAULAGE_ORIGIN_PIT | VIEW |  |
| dbo | HAULAGE_PER_PILE | VIEW |  |
| dbo | HAULAGE_PER_PILE_AND_PLAN | VIEW |  |
| dbo | HAULAGE_PER_PILE_AND_PLAN_TEMPORAL | VIEW |  |
| dbo | HAULAGE_PILE_INFO | VIEW |  |
| dbo | HAULAGE_PIT_ORIGIN_DESTINATION | VIEW |  |
| dbo | HAULAGE_VS_IWIP_SYSTEM | VIEW |  |
| dbo | HAULAGE_VS_OMR | VIEW |  |
| dbo | HAULAGE_VS_OMR_ORI_DEST | VIEW |  |
| dbo | HAULAGE_VS_PROD_MONTHLY_CF | VIEW |  |
| dbo | HAULAGE_VS_PROD_PILES_CF | VIEW |  |
| dbo | HAULAGE_VS_RECLAIM | VIEW |  |
| dbo | HAULAGE_WB_NOT_ON_THE_WAY | VIEW |  |
| dbo | HAULAGE_WITH_DT_TYPES | VIEW |  |
| dbo | LIM TOS PILE DOME For HAULAGE | VIEW |  |
| dbo | MINING_EQUIPMENTS | VIEW |  |
| dbo | MINING_HAULAGE_PLAN_AND_ACTUAL | VIEW |  |
| dbo | OEE_HAULAGE_WMT_KM | VIEW |  |
| dbo | OMR_PILE_STATUS_ALL | VIEW |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP | VIEW |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP2 | VIEW |  |
| dbo | PLAN_DAY_WORKS_CLEAN | VIEW |  |
| dbo | POS FOLLOW UP TREATED | VIEW |  |
| dbo | PP_MINED_CLEAN | VIEW |  |
| dbo | PP_MINED_NEW_RECONCIL_MENG_CONVERT_NEW_BM | VIEW |  |
| dbo | PRODUCTION_EQUIPMENT_RUNNING | VIEW |  |
| dbo | PRODUCTION_MINING_PIT | VIEW |  |
| dbo | PRODUCTION_PIT | VIEW |  |
| dbo | PRODUCTION_PIT_BY_EQ_HOUR | VIEW |  |
| dbo | PRODUCTION_PIT_COEF | VIEW |  |
| dbo | PRODUCTION_PIT_COORDINATES_B_S | VIEW |  |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y | VIEW |  |
| dbo | PRODUCTION_PIT_COORDINATES_X_Y_CONVERT_NEW_BM | VIEW |  |
| dbo | PRODUCTION_PIT_DAILY_PLAN | VIEW |  |
| dbo | PRODUCTION_PIT_DISTANCE_CALC | VIEW |  |
| dbo | PRODUCTION_PIT_HOURLY | VIEW |  |
| dbo | PRODUCTION_PIT_HOURLY_FULL | VIEW |  |
| dbo | PRODUCTION_PIT_HOURLY_TF | VIEW |  |
| dbo | PRODUCTION_PIT_RECONCIL_PP | VIEW |  |
| dbo | PRODUCTION_PIT_TOS_CLEAN | VIEW |  |
| dbo | PRODUCTION_PIT_VS_OMR | VIEW |  |
| dbo | PRODUCTION_PIT_WRONG_ELEVATION | VIEW |  |
| dbo | QC CHECK PIT VS SAMP LD | VIEW |  |
| dbo | QC CHECK PIT VS SAMP TOS | VIEW |  |
| dbo | QC PIT-TOS & SAMPLE DATA | VIEW |  |
| dbo | QC PIT-TOS OMR SUMMARY | VIEW |  |
| dbo | QC PIT-TOS OMR SUMMARY 2 | VIEW |  |
| dbo | QC PIT-TOS SUM FOR CHECK FOR LD | VIEW |  |
| dbo | QC PIT-TOS SUM FOR CHECK FOR TOS | VIEW |  |
| dbo | QC SAMPLE & ASSAYS COMPOSITES | VIEW |  |
| dbo | QC TOS_PILE STATUS HAULAGE | VIEW |  |
| dbo | QC TOS_VS_POS | VIEW |  |
| dbo | QC_COMPOSITE_ALL_STOCK | VIEW |  |
| dbo | QC_COMPOSITE_ASSAY | VIEW |  |
| dbo | QC_COMPOSITE_BLOCK | VIEW |  |
| dbo | QC_COMPOSITE_BLOCK_SELECT | VIEW |  |
| dbo | QC_COMPOSITE_BLOCK_VIA_PIT | VIEW |  |
| dbo | QC_COMPOSITE_DUMP | VIEW |  |
| dbo | QC_COMPOSITE_DUMP_VIA_PIT | VIEW |  |
| dbo | QC_COMPOSITE_HAULAGE | VIEW |  |
| dbo | QC_COMPOSITE_POS | VIEW |  |
| dbo | QC_COMPOSITE_POS_VIA_BM | VIEW |  |
| dbo | QC_COMPOSITE_POS_VIA_ML | VIEW |  |
| dbo | QC_COMPOSITE_POS_VIA_TOS | VIEW |  |
| dbo | QC_COMPOSITE_POS_VIA_YARD | VIEW |  |
| dbo | QC_COMPOSITE_TOS | VIEW |  |
| dbo | QC_COMPOSITE_TOS_CERT | VIEW |  |
| dbo | QC_COMPOSITE_TOS_IndividualBlock | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_BM | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_BM_ORI | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_HAULAGE | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_PIT | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_POS | VIEW |  |
| dbo | QC_COMPOSITE_TOS_VIA_YARD | VIEW |  |
| dbo | QC_COMPOSITE_WCO | VIEW |  |
| dbo | QC_COMPOSITE_YARD | VIEW |  |
| dbo | QC_COMPOSITE_YARD_DIRECT | VIEW |  |
| dbo | QC_COMPOSITE_YARD_STOCK_ORIGINAL | VIEW |  |
| dbo | QC_COMPOSITE_YARD_VIA_BM | VIEW |  |
| dbo | QC_COMPOSITE_YARD_VIA_POS | VIEW |  |
| dbo | QC_COMPOSITE_YARD_VIA_TOS | VIEW |  |
| dbo | QC_POS_DETAILS | VIEW |  |
| dbo | QC_STOCK_POS_VIA_ALL | VIEW |  |
| dbo | REQUEST_VS_HAULAGE | VIEW |  |
| dbo | ROLLING_MINE_PLAN_TREATED | VIEW |  |
| dbo | ROLLING_MINE_PLAN_TREATED_2 | VIEW |  |
| dbo | RSF_HAULING_DATA_DAILY | VIEW |  |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT | VIEW |  |
| dbo | RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR | VIEW |  |
| dbo | S123_TOS_STATUS_CLEAN | VIEW |  |
| dbo | SAMPLING_CONTRACTOR_PREP | VIEW |  |
| dbo | STOCK_ORIGIN_PIT | VIEW |  |
| dbo | STOCK_ORIGIN_PIT_BY_WMT | VIEW |  |
| dbo | STOCK_POS_YARD | VIEW |  |
| dbo | STOCK_STATUS_FLOW | VIEW |  |
| dbo | STOCK_STATUS_FULL | VIEW |  |
| dbo | STOCK_STATUS_SIMPLE | VIEW |  |
| dbo | STOCK_STATUS_STATUS | VIEW |  |
| dbo | SURVEY POS CONSOLIDATED | VIEW |  |
| dbo | SURVEY_POS_DATED | VIEW |  |
| dbo | SURVEY_POS_ESTIMATE_HAULAGE | VIEW |  |
| dbo | SURVEY_POS_FOR_PROD | VIEW |  |
| dbo | SURVEY_POS_TC | VIEW |  |
| dbo | TOS_DUMP_COORDINATES_UNIQUE | VIEW |  |
| dbo | TOS_PILE_PIT | VIEW |  |
| dbo | TOS_STATUS_ERROR_TRANSFER_DATE | VIEW |  |
| dbo | trial cek tos follow vs haulage iwip  | VIEW |  |
| dbo | UNIT_TRIPS_HUAFEI_RSF | VIEW |  |
| dbo | vw_HAULAGE_GROUP | VIEW |  |
| dbo | VW_PRODUCTION_ACTIVITY_PIT | VIEW |  |
| dbo | w2_EQUIPMENTS | VIEW |  |
| dbo | w2_EQUIPMENTS_STATUS | VIEW |  |
| dbo | w2_PRODUCTION_PIT_HOURLY | VIEW |  |
| dbo | WEIGHBRIDGE_&_TRUCKCOUNT_TF_LAST | VIEW |  |
| dbo | WEIGHBRIDGE_&_TRUCKCOUNT_TF_PER_WEEK | VIEW |  |


### WBN_DATABASE — Step 8: SAP / issuance / inventory objects (19 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | HRM_REQUEST_MATERIAL | USER_TABLE |  |
| dbo | ASSAY_PROGRESS | VIEW |  |
| dbo | autoBM_GROUP | VIEW |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP | VIEW |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT | VIEW |  |
| dbo | BLOCK_PROD_QC_BM_TOS_GROUP_CAT_CORR | VIEW |  |
| dbo | BM_REDUCED_FOR_RECONCIL_GROUP | VIEW |  |
| dbo | BM_TC0_WMT_GROUP | VIEW |  |
| dbo | DAILY_QUALITY_DISPATCH_GROUP | VIEW |  |
| dbo | FENI_RECLAIMING_PLAN_WITH_GRADE | VIEW |  |
| dbo | FULL_PRODUCTION_GROUP | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX | VIEW |  |
| dbo | NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP | VIEW |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP | VIEW |  |
| dbo | OMR_PILE_STATUS_ALL_GROUP2 | VIEW |  |
| dbo | RECLAIMNG WB TREATED GROUPED | VIEW |  |
| dbo | TOS_STATUS_ERROR_TRANSFER_DATE | VIEW |  |
| dbo | vw_HAULAGE_GROUP | VIEW |  |


### WBN_DATABASE — Step 10: distance / route objects (17 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | ALL_HR_KM_SECTIONS | USER_TABLE |  |
| dbo | DISPATCH ROADS | USER_TABLE |  |
| dbo | DISPATCH ROADS OLD | USER_TABLE |  |
| dbo | DISTANCE_HAULING | USER_TABLE |  |
| dbo | DISTANCE_MINING | USER_TABLE |  |
| dbo | HAUL_ROAD_STA | USER_TABLE |  |
| dbo | HRM_MAJOR_ROADWORK | USER_TABLE |  |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | USER_TABLE |  |
| dbo | DISPATCH RESULTS DISTANCE | VIEW |  |
| dbo | DISPATCH ROADS & CALENDAR SHIFT | VIEW |  |
| dbo | DISTANCE_HAULING_CHECK | VIEW |  |
| dbo | DISTANCE_MINING_CHECK | VIEW |  |
| dbo | DT_DENSITY_HAULROAD | VIEW |  |
| dbo | DT_DENSITY_HAULROAD_treated | VIEW |  |
| dbo | DT_DENSITY_HAULROAD_treated2 | VIEW |  |
| dbo | OEE_HAULAGE_WMT_KM | VIEW |  |
| dbo | PRODUCTION_PIT_DISTANCE_CALC | VIEW |  |


### WBN_DATABASE — Step 4: schemas of named key tables (90 rows)

| schema_name | table_name | column_name | data_type | max_length | is_nullable | column_description |
|---|---|---|---|---|---|---|
| dbo | DAY_WORKS | ID | int | 4 | False |  |
| dbo | DAY_WORKS | UUID | nvarchar | 510 | True |  |
| dbo | DAY_WORKS | DATE | date | 3 | True |  |
| dbo | DAY_WORKS | SHIFT | int | 4 | True |  |
| dbo | DAY_WORKS | CONTRACTOR | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | ACTIVITY_CAT | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | ACTIVITY_DESC | nvarchar | 510 | True |  |
| dbo | DAY_WORKS | ACTIVITY_PLANNED | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | ACTIVITY_TIME_START | time | 3 | True |  |
| dbo | DAY_WORKS | ACTIVITY_TIME_END | time | 3 | True |  |
| dbo | DAY_WORKS | OPERATOR_ID | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | UNIT_TYPE | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | UNIT_CLASS | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | UNIT_ID | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | UNIT_START_HOUR_METER | float | 8 | True |  |
| dbo | DAY_WORKS | UNIT_END_HOUR_METER | float | 8 | True |  |
| dbo | DAY_WORKS | LOCATION | nvarchar | 510 | True |  |
| dbo | DAY_WORKS | ROAD_NAME | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | ROAD_STA_KM | float | 8 | True |  |
| dbo | DAY_WORKS | ROAD_END_KM | float | 8 | True |  |
| dbo | DAY_WORKS | ROAD_LANE | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | LOADING_POINT | nvarchar | 100 | True |  |
| dbo | DAY_WORKS | LOADING_RIT | float | 8 | True |  |
| dbo | DAY_WORKS | DISTANCE_KM | float | 8 | True |  |
| dbo | DAY_WORKS | REMARK | nvarchar | 510 | True |  |
| dbo | DAY_WORKS | UPDATE_DATE | datetime | 8 | True |  |
| dbo | DAY_WORKS | UPDATE_BY | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | ID | int | 4 | False |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | CONTRACTOR | nvarchar | 100 | False |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | DATE | date | 3 | False |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | SHIFT | int | 4 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | START_HOUR | int | 4 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | END_HOUR | int | 4 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | ACTIVITY | nvarchar | 510 | False |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | MATERIAL | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | MATERIAL_CLASS | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | ORIGIN_AREA | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | ORIGIN_ID | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | SUB_PIT | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | PROD_ID | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | DESTINATION_AREA | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | DESTINATION_ID | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | DISTANCE | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | TRUCK_ID | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | TRUCK_FACTOR | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | EXCAVATOR_ID | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | RIT | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | REMARK | nvarchar | 510 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | ID | int | 4 | False |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | CONTRACTOR | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | DATE | datetime | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | SHIFT | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | START_HOUR | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | END_HOUR | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | ID_EQ | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | ACTIVITY | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | LOCATION | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | WORKING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | STBY_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | STBY_CODE | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | BD_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | BD_CODE | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | PM_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | PM_CODE | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | OPERATING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | REMARK | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | STATUS | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_HOURLY_STATUS | LOCATION_DETAILS | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | ID | int | 4 | False |  |
| dbo | EQUIPMENTS_STATUS | CONTRACTOR | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | DATE | date | 3 | True |  |
| dbo | EQUIPMENTS_STATUS | SHIFT | int | 4 | True |  |
| dbo | EQUIPMENTS_STATUS | ID_EQ | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | STATUS | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | ACTIVITY | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | LOCATION | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | LOCATION_DETAILS | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | HOUR_METER_START | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | HOUR_METER_END | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | USAGE_KM_METER | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | WORKING_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | STBY_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | STBY_CODE | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_HOURS | float | 8 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_CODE | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_START | date | 3 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_EST_RFU | date | 3 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_COMPARTMENT | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | BD_STATUS | nvarchar | 100 | True |  |
| dbo | EQUIPMENTS_STATUS | REMARK | nvarchar | 100 | True |  |


### WBN_DATABASE — All table row counts (partition stats) (161 rows)

| schema_name | table_name | approx_rows |
|---|---|---|
| dbo | EQUIPMENTS_HOURLY_STATUS | 16657468 |
| dbo | EQUIPMENTS_HOURLY_ACTIVITIES | 4699720 |
| dbo | BLOCK_INDESIGN | 4288722 |
| dbo | EQUIPMENTS_STATUS | 3708573 |
| dbo | HAULAGE | 3510278 |
| dbo | S123_STOCK_SHAPE_OLD | 1732432 |
| dbo | HAULAGE_IWIP_EXT | 1508871 |
| dbo | RSF_HAULING_DATA | 1143509 |
| dbo | WAITING_TIME | 878240 |
| dbo | HAULAGE_IWIP | 572742 |
| dbo | TOS_STATUS | 549734 |
| dbo | DAY_WORKS | 496409 |
| dbo | PRODUCTION_ACTIVITY_PIT | 453453 |
| dbo | PRODUCTION_PIT_OLD | 407593 |
| dbo | ASSAYS | 396475 |
| dbo | PP_MINED_NEW_RECONCIL_MENG | 309723 |
| dbo | SAMPLE | 249622 |
| dbo | auto_edge_HAULAGE | 246975 |
| dbo | DISPATCH WBN ACTUAL | 212890 |
| dbo | auto_node_STOCK_ID | 186836 |
| dbo | POS FOLLOW UP | 177830 |
| dbo | autoQC_CF_BM_TOS_HISTORY_OLD | 175475 |
| dbo | CRUSHER_STOCKPILE_OUTPUT_DATA | 156726 |
| dbo | QC PIT-TOS OMR | 149360 |
| dbo | autoBLOCK_PROD_QC_BM_TOS_CORR | 135148 |
| dbo | CONTRACTOR FOLLOW UP | 131768 |
| dbo | FeNi Reclaiming Plan | 129378 |
| dbo | MINING_PLAN_WEEKLY | 124358 |
| dbo | SAMPLING_CONTRACTOR | 123196 |
| dbo | TOS_PILE_INFO | 97738 |
| dbo | autoQC_STOCK_ALL_VIA_ALL | 93119 |
| dbo | TOS FOLLOW | 87045 |
| dbo | OMR_QC | 86007 |
| dbo | DISPATCH FeNi PLAN & ACTUAL | 85416 |
| dbo | DISTANCE_MINING | 83462 |
| dbo | DAILY_QUALITY_DISPATCH | 66774 |
| dbo | PILES_SHARED_FENI | 66571 |
| dbo | EXC_TRIMMING | 59362 |
| dbo | RAINFALL | 55934 |
| dbo | SURVEY POS | 50629 |
| dbo | HAULAGE_M_DOME_2026_IWIP_PLAN | 44289 |
| dbo | autoTOS_SURVEY_ESTIMATION | 41447 |
| dbo | QC_TOS_DATA_ML | 38001 |
| dbo | PP_REMAIN_INPIT_MINEOUT | 36206 |
| dbo | PP_MINED_YTD_OK | 35922 |
| dbo | TSS | 35218 |
| dbo | HRM_INSPECTION | 30610 |
| dbo | DISTANCE_HAULING | 30587 |
| dbo | CRUSHER LOIPOLOY | 27353 |
| dbo | DISPATCH WBN PLAN SHIFT | 27058 |
| dbo | QC SAMPLE DATA | 25425 |
| dbo | VERY VERY SHORT TERM PIT SERVICE | 21078 |
| dbo | ASSAYS_NITON_GGSHEET | 19700 |
| dbo | PRODUCTION_PIT_PRELIM_auto | 15887 |
| dbo | WBN_DATABASE_ST_LOG_ON | 14942 |
| dbo | STOCK_STATUS | 14725 |
| dbo | blasting_drilling | 14648 |
| dbo | OLD_VERY_SHORT_TERM | 13470 |
| dbo | HAULAGE_REPORT | 13459 |
| dbo | QUARRY PRODUCTION | 12646 |
| dbo | PROD VERY VERY SHORT TERM | 11216 |
| dbo | RSF_SURVEY | 9103 |
| dbo | autoQC_CF_BM_TOS | 8274 |
| dbo | RECLASSIFICATION | 7794 |
| dbo | EQUIPMENTS | 7221 |
| dbo | FENI_REQUESTS | 7196 |
| dbo | QS_LIMS_RIM_CK | 6131 |
| dbo | DARONNE_Htemp | 5812 |
| dbo | EQUIPMENTS_OLD | 5658 |
| dbo | WMT_FOR_3RD_PARTY | 5529 |
| dbo | TOS_SURVEY | 5340 |
| dbo | BATCH | 4931 |
| dbo | DRAFTS | 4848 |
| dbo | S123_STOCK_SHAPE | 4785 |
| dbo | STOCK_STATUS_HAULAGE_GGSHEET | 4750 |
| dbo | STOCK_REQUESTS | 4735 |
| dbo | 3RD_PARTY_ACTIVITIES_RECLAIM | 4202 |
| dbo | REQUEST | 3920 |
| dbo | ORE STOCK SALES | 3800 |
| dbo | S123_TOS_STATUS | 3589 |
| dbo | CRUSHER_BLENDING_DATA | 3332 |
| dbo | 3RD_PARTY_ACTIVITIES | 3328 |
| dbo | HAUL_ROAD_STA | 3122 |
| dbo | Calendar_For_Exploitation | 2665 |
| dbo | S123_ENVIRO_TSS | 2366 |
| dbo | MINING_PLAN_3MRMP | 2295 |
| dbo | blasting_parameters | 2081 |
| dbo | EQUIPMENTS_PLAN | 2071 |
| dbo | DAY_WORKS_PLAN_DAILY | 2043 |
| dbo | Calendar_Svy_topo_by_deposit | 1848 |
| dbo | ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE | 1585 |
| dbo | RSF_PER_LOCATION | 1489 |
| dbo | CLASS2025 | 1438 |
| dbo | CONSOLIDATED SURVEY | 1188 |
| dbo | QUARRY_PLAN | 1114 |
| dbo | WATER_MANAGEMENT | 1074 |
| dbo | OLD_prod_correction_factor_ACCESS | 957 |
| dbo | ROLLING_MINE_PLAN | 834 |
| dbo | IWIP_REQUESTS_DATE | 772 |
| dbo | TRANSHIPMENT_WBN_ORE | 575 |
| dbo | ID_DT_HUAFEI | 485 |
| dbo | SUMMARY_SURVEY | 460 |
| dbo | BLASTING_PROD | 433 |
| dbo | DISPATCH_PLAN_WB | 432 |
| dbo | COLOR_CHEMICAL | 404 |
| dbo | WBN_DATABASE_ESSENTIALS | 334 |
| dbo | autoQC_PLAN_NI_CF_OLD | 264 |
| dbo | DISPATCH HAULAGE TF | 264 |
| dbo | DISPATCH ROADS OLD | 254 |
| dbo | autoHAULAGE_VS_PROD_MONTHLY_CF | 223 |
| dbo | DISPATCH ROADS | 222 |
| dbo | HRM_CONTRACT_EQUIPMENT | 198 |
| dbo | PROJECTS_SUPERVISION | 198 |
| dbo | MBAR | 173 |
| dbo | HRM_MAJOR_ROADWORK | 149 |
| dbo | LME | 148 |
| dbo | LME_GOLD | 146 |
| dbo | TSS_POINT | 121 |
| dbo | TOS_DUMP_COORDINATES | 118 |
| dbo | TSS_CROSSTABLE | 109 |
| dbo | MINING_FLASH_REPORT_FLEET_PROD | 108 |
| dbo | MINING_FLASH_REPORT_EQUIPMENT | 102 |
| dbo | BLASTING_REMAINING | 98 |
| dbo | CONTRACTOR_DEPOSIT | 84 |
| dbo | EQUIPMENTS_WORKS | 82 |
| dbo | WBN_DATABASE_PROCEDURE_QUEUE | 79 |
| dbo | TEAM_PLAN | 78 |
| dbo | COMPANIES | 73 |
| dbo | DARONNEtemp | 61 |
| dbo | Ni_COLOR | 45 |
| dbo | MINING_FLASH_REPORT_PRODUCTION | 42 |
| dbo | LOCATION_WB_SH | 39 |
| dbo | ACTIVITIES_MAT | 39 |
| dbo | DT_DENSITY_HR_MODEL$ | 37 |
| dbo | TEAM | 34 |
| dbo | MINING_EQ_TARGET_3MRMP | 30 |
| dbo | ALL_HR_KM_SECTIONS | 27 |
| dbo | ASSAY_CLASS | 27 |
| dbo | SHAPE_STOCK_AREA | 26 |
| dbo | TEAM_FB | 25 |
| dbo | HRM_REQUEST_MATERIAL | 25 |
| dbo | POS POSSIBILITY For HAULAGE | 23 |
| dbo | REQUEST_SALES_LATE_2025 | 18 |
| dbo | BLOCK_ID_XYPARAM | 16 |
| dbo | CRUSHER_SURVEY_LOYPOLOY | 16 |
| dbo | ACTIVITIES | 13 |
| dbo | HAULAGE CONTRACTORS | 11 |
| dbo | SUPERVISION_SAFETY_ACTIONS | 6 |
| dbo | HAULAGE_ADJ | 3 |
| dbo | CRUSHER_CF | 3 |
| dbo | CORRECTIVE_ACTIONS | 0 |
| dbo | blasting_production | 0 |
| dbo | autoQC_CF_BM_PROP | 0 |
| dbo | FMS_TOS_STATUS | 0 |
| dbo | DAYWORK_REQUEST | 0 |
| dbo | TEAM_PROFILE | 0 |
| dbo | tempHAULAGE_IWIP | 0 |
| dbo | TOS | 0 |
| dbo | START LIM STOCK | 0 |
| dbo | PRODUCTION_PIT_MINING_DISTANCE | 0 |
| dbo | WBN_DATABASE_ERROR_PROCEDURE | 0 |


### FMS_DB — Step 1: fuel-named objects (0 rows)

_(no rows)_


### FMS_DB — Step 5: equipment/fleet/haul objects (25 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | auto_kmFMS_PLAYBACK_TRACK_DATA | USER_TABLE |  |
| dbo | auto_spFMS_PLAYBACK_TRACK_DATA | USER_TABLE |  |
| dbo | FMS_EQUIPMENTS | USER_TABLE |  |
| dbo | FMS_GPS_Historical | USER_TABLE |  |
| dbo | FMS_HAUL_CYCLES | USER_TABLE |  |
| dbo | FMS_PLAYBACK_TRACK_24H | USER_TABLE |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | USER_TABLE |  |
| dbo | FMS_ROADMAP | USER_TABLE |  |
| dbo | FMS_ROADMAP_DOC | USER_TABLE |  |
| dbo | FMS_ROADMAP_META | USER_TABLE |  |
| dbo | FMS_TOS_STATUS | USER_TABLE |  |
| dbo | FMS_TRUCK_ASSIGNMENTS | USER_TABLE |  |
| dbo | FMS_TRUCK_CYCLES | USER_TABLE |  |
| dbo | FMS_USER_ACTIVITY | USER_TABLE |  |
| dbo | RADIO_REPROGRAM_TRACK | USER_TABLE |  |
| dbo | EQUIPMENTS_RADIO_STATUS | VIEW |  |
| dbo | FMS_EQUIPMENTS_CLEAN | VIEW |  |
| dbo | FMS_EQUIPMENTS_FILTER | VIEW |  |
| dbo | FMS_PLAYBACK_TRACK_CLEAN | VIEW |  |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | VIEW |  |
| dbo | FMS_PLAYBACK_TRACK_WORKINGHOURS | VIEW |  |
| dbo | OVERSPEED_VEHICLE_SUMMARY | VIEW |  |
| dbo | VW_WT_PLAN_BREAKDOWN_STATUS | VIEW |  |
| dbo | VW_WT_TRACK_PLAN_SUMMARY | VIEW |  |
| dbo | VW_WT_TRACK_PLAN_SUMMARY_FINAL | VIEW |  |


### FMS_DB — Step 8: SAP / issuance / inventory objects (6 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | FMS_LV_MOVEMENTS | USER_TABLE |  |
| dbo | RADIO_REPROGRAM_TRACK | USER_TABLE |  |
| dbo | RES_WATER_FILLING_POINTS | USER_TABLE |  |
| dbo | FMS_PLAYBACK_STAY_GROUP | VIEW |  |
| dbo | VW_WT_REFILL_CYCLE_SUMMARY | VIEW |  |
| dbo | VW_WT_REFILL_CYCLES | VIEW |  |


### FMS_DB — Step 10: distance / route objects (5 rows)

| schema_name | object_name | type_desc | description |
|---|---|---|---|
| dbo | auto_kmFMS_PLAYBACK_TRACK_DATA | USER_TABLE |  |
| dbo | FMS_ROADMAP | USER_TABLE |  |
| dbo | FMS_ROADMAP_DOC | USER_TABLE |  |
| dbo | FMS_ROADMAP_META | USER_TABLE |  |
| dbo | FMS_PLAYBACK_TRACK_SEGMENT_COVERED | VIEW |  |


### FMS_DB — Step 4: schemas of named key tables (34 rows)

| schema_name | table_name | column_name | data_type | max_length | is_nullable | column_description |
|---|---|---|---|---|---|---|
| dbo | FMS_CONGESTION_SEG | HOUR_TS | bigint | 8 | False |  |
| dbo | FMS_CONGESTION_SEG | SEG_ID | nvarchar | 80 | False |  |
| dbo | FMS_CONGESTION_SEG | DIR | char | 4 | False |  |
| dbo | FMS_CONGESTION_SEG | SUM_SPD | float | 8 | True |  |
| dbo | FMS_CONGESTION_SEG | FIX_N | int | 4 | True |  |
| dbo | FMS_CONGESTION_SEG | TRUCK_N | int | 4 | True |  |
| dbo | FMS_CONGESTION_SEG | UPDATED_AT | bigint | 8 | True |  |
| dbo | FMS_CONGESTION_SEG | SUM_TRAV_MS | float | 8 | True |  |
| dbo | FMS_CONGESTION_SEG | TRAV_N | int | 4 | True |  |
| dbo | FMS_EQUIPMENTS | FETCH_DATE | datetime | 8 | True |  |
| dbo | FMS_EQUIPMENTS | truckId | nvarchar | 100 | False |  |
| dbo | FMS_EQUIPMENTS | orgName | nvarchar | 100 | True |  |
| dbo | FMS_EQUIPMENTS | plateNumber | nvarchar | 100 | True |  |
| dbo | FMS_EQUIPMENTS | orgId | bigint | 8 | True |  |
| dbo | FMS_EQUIPMENTS | imei | bigint | 8 | True |  |
| dbo | FMS_EQUIPMENTS | active | nvarchar | 100 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | FETCH_DATE | datetime | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | plateNumber | nvarchar | 100 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | acc | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | deviceType | nvarchar | 510 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | distance | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | lng | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | driving_time | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | dump_energy | nvarchar | 510 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | receive_time | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | loc_type | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | speed | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | engine | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | oils | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | course | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | imei | bigint | 8 | False |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | time | bigint | 8 | False |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | interpolation_flag | float | 8 | True |  |
| dbo | FMS_PLAYBACK_TRACK_DATA | lat | float | 8 | True |  |


### FMS_DB — All table row counts (partition stats) (65 rows)

| schema_name | table_name | approx_rows |
|---|---|---|
| dbo | FMS_PLAYBACK_TRACK_DATA | 27456831 |
| dbo | auto_kmFMS_PLAYBACK_TRACK_DATA | 20448378 |
| dbo | FMS_ENTRY_EXIT_DATA | 13470082 |
| dbo | FMS_SECURITY_INCIDENT_DATA | 5514587 |
| dbo | autoFMS_SECURITY_INCIDENT_KILOMETER | 4330549 |
| dbo | auto_spFMS_PLAYBACK_TRACK_DATA | 2032624 |
| dbo | FMS_GPS_Historical | 1717625 |
| dbo | FMS_INTERVENTION_EVENT_DATA | 1320961 |
| dbo | FMS_PLAYBACK_TRACK_24H | 1082391 |
| dbo | FMS_PLAYBACK_STAY_DATA | 402196 |
| dbo | FMS_RISK_DATA | 337685 |
| dbo | FMS_GEOFENCE_VISITS | 74312 |
| dbo | FMS_CONGESTION_SEG | 18281 |
| dbo | SIM_PLAN_DAY_KPI | 12112 |
| dbo | RES_EMPLOYEES | 8958 |
| dbo | FMS_GEOFENCES | 3490 |
| dbo | RADIO_REPROGRAM_TRACK | 3478 |
| dbo | FMS_TOS_STATUS | 3404 |
| dbo | FMS_TMS_TOKEN | 3040 |
| dbo | FMS_EQUIPMENTS | 1435 |
| dbo | WT_DAILY_PLAN | 1259 |
| dbo | FMS_UNIT_INSTALLED | 1225 |
| dbo | FMS_TRUCK_ASSIGNMENTS | 408 |
| dbo | FMS_HAUL_CYCLES | 288 |
| dbo | FMS_QUALITY_DISPATCH | 258 |
| dbo | LV_MASTER | 134 |
| dbo | LV_INFO | 124 |
| dbo | FMS_DISPATCH_PLAN | 105 |
| dbo | SHP_SED_POND | 91 |
| dbo | FMS_ROADMAP | 87 |
| dbo | SAFETY_DPLAN | 80 |
| dbo | FMS_LV_ZONE_VISITS | 71 |
| dbo | FMS_GEOFENCE_ALERTS | 70 |
| dbo | FMS_LOGIN_IPS | 69 |
| dbo | LV_PLAN | 62 |
| dbo | FMS_USERS | 31 |
| dbo | SIM_PLAN_EDGE | 27 |
| dbo | RES_SPEED_LIMIT_ZONES | 27 |
| dbo | FMS_APP_STATE | 24 |
| dbo | FMS_JOB_RUNS | 20 |
| dbo | FMS_USER_ACTIVITY | 18 |
| dbo | SIM_PLAN_NODE | 17 |
| dbo | FMS_ASSIGNMENTS | 17 |
| dbo | FMS_MESSAGES | 16 |
| dbo | FMS_LV_OVERTIME_REVIEW | 15 |
| dbo | RES_WATER_FILLING_POINTS | 14 |
| dbo | FMS_LV_DAILY_REPORTS | 10 |
| dbo | SIM_PLAN_ANALOGUE_CACHE | 8 |
| dbo | FMS_SETTINGS | 8 |
| dbo | FMS_LV_VISIT_VERIFICATIONS | 6 |
| dbo | DEPARTMENT_MASTER | 5 |
| dbo | LV_BOOKING_DETAIL | 4 |
| dbo | RES_CRITICAL_ZONES | 4 |
| dbo | FMS_INSTANCES | 3 |
| dbo | LV_BOOKING | 2 |
| dbo | FMS_TRUCK_CYCLES | 1 |
| dbo | FMS_GEOFENCE_ALERT_RULES | 1 |
| dbo | FMS_DOCS | 1 |
| dbo | FMS_ROADMAP_DOC | 1 |
| dbo | FMS_ROADMAP_META | 1 |
| dbo | FMS_LV_MOVEMENTS | 0 |
| dbo | FMS_LV_BOOKING | 0 |
| dbo | FMS_LV_BOOKING_ITEM | 0 |
| dbo | FMS_ERROR_FLOW | 0 |
| dbo | LV_DRIVER_INFO | 0 |

---

## 9. Join feasibility — superseded by section 10

> **⚠ SUPERSEDED.** This section predicted, from 20-row samples, that fuel and
> operating hours could not be joined. The live test in section 10 disproves
> it: **735 of 736 units join directly**. Retained for the namespace map, which
> is still accurate and still matters for the GPS tables. Do not act on 9.4
> path selection; use section 10.

Sections 1-8 answer "what data exists". This section answers the question that
actually determines whether a diesel model can be built: **can litres be
attached to operating hours?** A litre count with no denominator is not a
model input.

### 9.1 The blocker: five ID namespaces

Fuel and operating hours are keyed in **different, non-overlapping namespaces**,
so the obvious join silently returns nothing.

| Namespace shape | Example | Where it appears |
|---|---|---|
| `A999` (fleet no.) | `L961` | **`WAITING_TIME.EQUIPMENT_ID` (the fuel data)**, `HAULAGE_IWIP_EXT.TRUCK_ID`, `HAULAGE_IWIP.TRUCK_ID`, `RSF_HAULING_DATA.NB_UNIT`, `EQUIPMENTS_HOURLY_ACTIVITIES.EXCAVATOR_ID`, `FMS_EQUIPMENTS.plateNumber`, `FMS_UNIT_INSTALLED.PLATE`, `FMS_GEOFENCE_VISITS.UNIT_ID`, `FMS_TRUCK_ASSIGNMENTS.TRUCK`, `FMS_HAUL_CYCLES.TRUCK_PLATE` |
| `AAAA9999999` (asset no.) | `ATCT0450027` | **`EQUIPMENTS_HOURLY_STATUS.ID_EQ` (the hours data)**, `DAY_WORKS.UNIT_ID` |
| `AAA-A9-AAA-99` (master) | `ATC-P3-GKT-01` | `EQUIPMENTS.ID_EQ` (fleet master) |
| `AA999` / `AAA999` | `EX407`, `ADT153` | `EQUIPMENTS_STATUS.ID_EQ`, `EQUIPMENTS_HOURLY_ACTIVITIES.TRUCK_ID`, `FMS_PLAYBACK_TRACK_DATA.plateNumber` |
| 19-digit / 15-digit | `6916297240046994306` | `FMS_EQUIPMENTS.truckId`, `.imei` (GPS device serials) |

**Consequence:** `WAITING_TIME` (`A999`) and `EQUIPMENTS_HOURLY_STATUS`
(`AAAA9999999`) **cannot be joined directly**. Any naive
`ON EQUIPMENT_ID = ID_EQ` returns 0 rows and would look like "no fuel data"
rather than a mapping failure. This is the same class of error documented in
`reports/_cross_analysis.md`, where a namespace split was mistaken for missing
data and the mapping table turned out to already exist.

### 9.2 A table the keyword scan missed: real hour meters

`DAY_WORKS` (496,409 rows) carries **`UNIT_START_HOUR_METER`** and
**`UNIT_END_HOUR_METER`** — genuine hour meters, and the single best
denominator for a burn-rate model. The requested Step-2 pattern list could not
find them: it searches for `%HOUR%` only via terms like `OPERATING_HOUR`, while
these are spelled `UNIT_..._HOUR_METER`. They were surfaced by the widened
scan in section 7b.

`DAY_WORKS.UNIT_ID` sits in the **same `AAAA9999999` namespace as the hours
table**, which makes it the prime bridge candidate — but in the sampled rows
both hour-meter columns are `NULL`, so their real population rate must be
measured before relying on them.

### 9.3 Open questions, and the script that settles them

`scripts/fuel_recon5.py` is written and ready; it could not run because the
VPN to `10.211.10.1` dropped (~9.5 h at time of writing) together with the
`LUCKY_SSD` credential volume — the documented failure mode in
`reports/HANDOVER.md`. It answers, in counts:

| ID | Question |
|---|---|
| A | Does fuel join to hours directly? (expected: 0 matches) |
| B | Which table bridges `A999` → `AAAA9999999`: `DAY_WORKS`, `EQUIPMENTS`, or `HAULAGE_IWIP_EXT`? |
| C | Are `DAY_WORKS` hour meters actually populated, overall and since 2026-02? |
| D | How many fuel unit-days survive the join — i.e. the real training-set size? |

Run it with the VPN up:

```bash
./.venv/bin/python scripts/fuel_recon5.py
```

### 9.4 Recommended modelling path, given the constraints

1. **Preferred — litres per operating hour. CONFIRMED VIABLE (section 10):
   no bridge needed, 99.6% of fuel unit-days join.** Target
   `litres / OPERATING_HOURS` per unit-day. Features already available:
   `CONTRACTOR`, `STBY_HOURS`, `BD_HOURS`, activity, location.
2. **Fallback — litres per tonne-km, but it needs one bridge, not zero.**
   `HAULAGE_IWIP_EXT` (1.5 M rows) shares the `A999` namespace with the fuel
   data and joins directly on `TRUCK_ID`, giving **payload tonnes per
   truck-day** (`NET_WEIGHT`) with no mapping at all. It does **not** carry a
   distance column, so tonne-km is not available from the ticket alone.
   Distance must come from one of:
   - **`FMS_EQUIPMENTS` as the bridge to GPS km (best).** It holds
     `plateNumber` (`A999`, the fuel namespace) and `imei` (the GPS
     namespace) **on the same row**, 1,435 rows. That maps fuel units onto
     `auto_kmFMS_PLAYBACK_TRACK_DATA` (20.4 M rows, `imei` + `SectionKM`),
     i.e. measured GPS kilometres per unit. This is the same
     `plateNumber`/`truckId` dual-key trick already documented in
     `reports/_cross_analysis.md`.
   - **Route lookup from `ORIGIN_AREA` → `DESTINATION_AREA`** on the ticket,
     priced against `HAUL_ROAD_STA` chainage. Cheaper, but the area strings
     contain non-LATIN1 characters that render as `?` under the required
     charset, so they need careful normalisation.
   - **Not `DISTANCE_MINING`.** It has a `DISTANCE` column but is keyed by
     `DIGGER` (`EXC 908`) with **no truck column**, so it cannot attribute
     distance to a fuelled unit. It is excavator/fleet-level only.
3. **Do not attempt a seasonal forecast.** Fuel data starts **2026-02-22** and
   spans five months with 4.5% row coverage. That supports a cross-sectional
   intensity model, not a time-series forecast with annual seasonality.
4. **Parse, never cast, `TOTAL_FUEL`.** It is free-text `nvarchar(100)`
   (`'200'`, `'200 L'`, `'180L'`, `''`). `TRY_CONVERT` alone silently drops the
   `L`-suffixed values, which are **12.0%** of the data (3,838 of the 32,000
   rows covered by the top-30 distinct values in section 1). The parser used
   throughout this report strips `' L'`, `'L'` and normalises `,` to `.`
   before conversion.

---

## 10. Join test results

Run of `scripts/fuel_recon5.py` against the live database. These counts settle the open questions from section 9.3.

### 10.1 Verdict

- **Direct fuel→hours join: 735 of 736 units (99.9%).** Unexpectedly viable; the namespace split is narrower than the sampled shapes implied.
- **Best bridge: `EQUIPMENTS.ID_EQ` matching 736 fuel units** (DAY_WORKS 295, EQUIPMENTS ID_EQ/NEW_ID_EQ/SERIAL 736/0/0, HAULAGE_IWIP_EXT 729)
- **DAY_WORKS hour meters since 2026-02: 63913 populated.** Usable — prefer these over derived OPERATING_HOURS.
- **Training set: 30917 of 31035 fuel unit-days join to hours (99.6%); 24478 join to the weighbridge (78.9%).**
- **=> Litres-per-operating-hour is viable**, per section 9.4 path (1).
- **Payload denominator: 24478 of 31035 fuel unit-days have weighbridge tonnes (78.9%).** The ticket carries no distance column, so this alone gives litres-per-tonne, not litres-per-tonne-km.
- **GPS-km bridge (`FMS_EQUIPMENTS.plateNumber`→`imei`): 643 of 736 fuel units carry an imei (87.4%).** Distance is obtainable, so a true tonne-km target is constructible.


### 10.2 Raw results


**A. Direct fuel → operating-hours join**

| fuel_units | hour_units | matched |
|---|---|---|
| 736 | 3701 | 735 |


**B. Bridge candidate: DAY_WORKS.UNIT_ID**

| fuel_units_seen_in_day_works |
|---|
| 295 |


**B. Bridge candidate: EQUIPMENTS master**

| via_ID_EQ | via_NEW_ID_EQ | via_SERIAL_NO |
|---|---|---|
| 736 | 0 | 0 |


**B. Bridge candidate: HAULAGE_IWIP_EXT.TRUCK_ID**

| fuel_units_in_haulage_ext |
|---|
| 729 |


**B. EQUIPMENTS rows for trucks/excavators**

| ID | ID_EQ | NEW_ID_EQ | SERIAL_NO | TYPE | MODEL | CONTRACTOR |
|---|---|---|---|---|---|---|
| ATC-DT-42 | IWIP-ATC-U42 |  |  | Light Truck | ???? | ATC |
| AWK-DT-48 | AWK-LK Z48 |  |  | Light Truck | DUTRO 4X4 | AWK |
| AWK-DT-78 | AWK-LK L78 |  |  | Light Truck | DUTRO 4X4 | AWK |
| CKB-EX-201 | MTM-CEXC201 |  | CAT00320CSYW20076 | EXCAVATOR | CAT320 | CKB |
| CKB-EX-202 | EX 202 |  | CAT00320ESYW20053 | Excavator | CAT320 | CKB |
| CKB-EX-213 | EX 213 |  | ZBH11338 | Excavator | CAT320 | CKB |
| CKB-EX-301 | MTM-CEXC301 |  |  | EXCAVATOR | CAT330 | CKB |
| CKB-EX-303 | MTM-CEXC303 |  |  | EXCAVATOR | HIT350 | CKB |
| CKB-FT-2 | TTR002 |  |  | Fuel Truck | F3000 | CKB |
| CKB-FT-6 | FT06 |  | LZGJRLDR47PX116654/1623J029197 | Fuel Truck | F3000 | CKB |
| CKB-FT-7 | FT07 |  |  | Fuel Truck | F3000 | CKB |
| CKB-MH-1 | MH01 |  |  | Manhaul |  | CKB |
| CKB-MH-2 | MH02 |  |  | Manhaul |  | CKB |
| CKB-WT-1 | WT01 |  |  | Water Truck | JD260 | CKB |
| FIJ-EX-1 | FIJ- EX 001 |  |  | EXCAVATOR | CDM6060N | FIJ |
| FIJ-EX-2 | FIJ- EX 002 |  |  | EXCAVATOR | SY 205C | FIJ |
| FIJ-EX-3 | FIJ- EX 003 |  |  | EXCAVATOR | SY 205C | FIJ |
| FIJ-Truck Mixer -6 | FIJ-CM006 |  |  | Truck Mixer  | 350 | FIJ |
| FIJ-Truck Mixer -9 | FIJ-009 |  |  | Truck Mixer  | SY308C-8 | FIJ |
| GMG-EX-5205 | EXC-5205 |  |  | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5206 | EXC-5206 |  | 409508 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5207 | EXC-5207 |  | 409550 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5209 | EXC-5209 |  | 409743 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5211 | EXC-5211 |  | 409607 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5212 | EXC-5212 |  | 409604 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5213 | EXC-5213 |  | 409742 | EXCAVATOR | ZAXIS 210-5G | GMG |
| GMG-EX-5224 | EXC-5224 |  |  | EXCAVATOR | LIUGONG | GMG |
| GMG-EX-5301 | EXC-5301 |  | 970533 | EXCAVATOR | ZAXIS 350H | GMG |
| GMG-EX-5302 | EXC-5302 |  | 971287 | EXCAVATOR | ZAXIS 350H | GMG |
| GMG-EX-5303 | EXC-5303 |  | 971280 | EXCAVATOR | ZAXIS 350H | GMG |


**C. DAY_WORKS hour-meter coverage (all time)**

| rows_all | start_hm | end_hm | units | mn | mx |
|---|---|---|---|---|---|
| 496409 | 458125 | 458125 | 1951 | 2024-10-15 | 2026-08-01 |


**C. DAY_WORKS hour-meter coverage (since 2026-02)**

| rows_2026 | start_hm | end_hm |
|---|---|---|
| 63913 | 63913 | 63913 |


**D. Training-set size via operating hours**

| fuel_unit_days | joined_unit_days |
|---|---|
| 31035 | 30917 |


**D. Training-set size via weighbridge**

| fuel_unit_days | joined_unit_days |
|---|---|
| 31035 | 24478 |


**D. Sample aggregated fuel unit-days**

| id | d | litres | fills |
|---|---|---|---|
| N104 | 2026-07-22 | 650.0 | 3 |
| N725 | 2026-07-22 | 530.0 | 3 |
| N523 | 2026-07-22 | 510.0 | 2 |
| N456 | 2026-07-22 | 500.0 | 2 |
| N351 | 2026-07-22 | 464.0 | 2 |
| N707 | 2026-07-22 | 450.0 | 3 |
| L315 | 2026-07-22 | 450.0 | 2 |
| N354 | 2026-07-22 | 450.0 | 2 |
| N501 | 2026-07-22 | 440.0 | 2 |
| K985 | 2026-07-22 | 440.0 | 2 |
| N733 | 2026-07-22 | 440.0 | 2 |
| N538 | 2026-07-22 | 434.0 | 2 |
| K800 | 2026-07-22 | 430.0 | 2 |
| N832 | 2026-07-22 | 425.0 | 2 |
| N388 | 2026-07-22 | 425.0 | 2 |
| N372 | 2026-07-22 | 420.0 | 2 |
| L057 | 2026-07-22 | 420.0 | 2 |
| N375 | 2026-07-22 | 419.0 | 1 |
| N565 | 2026-07-22 | 415.0 | 2 |
| K792 | 2026-07-22 | 413.0 | 2 |


**E. Payload denominator via weighbridge (direct join)**

| fuel_unit_days | with_payload | avg_net_wt | avg_tickets |
|---|---|---|---|
| 31035 | 24478 | 112899.53100743525 | 2.1919682980635673 |


**F. GPS-km bridge via FMS_EQUIPMENTS plateNumber→imei**

| fuel_units | in_fms_equipments | with_imei |
|---|---|---|
| 736 | 643 | 643 |

---

## 11. Modelling verdict — validated on a time-based holdout

Sections 9-10 answered "can the data be joined". This answers "does a model
actually predict". Built via `scripts/fuel_training_set.py`
(30,917 unit-days cached to `data/fuel_recon/training_set.csv`) and validated
by `scripts/fuel_model_validate.py`. Both run offline from the cache.

### 11.1 Two data traps, found by testing rather than assuming

**Trap 1 — `OPERATING_HOURS` is not engine hours.** Despite the name it is
*calendar* hours: every shift row carries `12.0`, so a unit-day always sums to
`24.0`. Correlation with litres is **+0.010**, i.e. none. **`WORKING_HOURS` is
the real run-time figure** (+0.166) and is what `l_per_work_hr` uses. The
first training set I built used `OPERATING_HOURS` and produced a meaningless
constant denominator.

**Trap 2 — a refuel is a tank fill, not a day's burn.** `corr(fills, litres) =
**+0.840**` while `corr(work_hrs, litres) = +0.166`. Litres per fill is tightly
clustered (p05 140, p50 200, p95 280): the operator tops up a ~200 L tank when
convenient. **Daily litres therefore measure refuelling behaviour, not
consumption.** Any per-unit-day burn-rate target inherits that noise.

### 11.2 Consequence: per-unit-day models fail, aggregation fixes it

Time-based holdout, train on the first 80% of days, test on the rest.

| Grain | Model | MAE | MAPE |
|---|---|---|---|
| unit-day | mean litres (no model) | 79.3 L | 35.9% |
| unit-day | global L/work-hr × hours | 90.6 L | 40.3% |
| unit-day | per-unit L/work-hr × hours | 90.6 L | 40.8% |

**Per-unit-day burn-rate models are worse than predicting the mean.** Reporting
this rather than the flattering aggregate number, because it is the result that
determines the design.

Aggregating averages the refuel lumpiness away:

- Across 489 units with ≥30 fuel-days: `corr(total work_hrs, total litres)` =
  **+0.933**, and per-unit lifetime burn rates are tight — p05 11.6, p50 15.3,
  p95 19.0 L/work-hr. Physically credible for haul trucks.
- At fleet-day grain (139 days): `corr(active units, litres)` = **+0.976**,
  work hours +0.799, tonnes +0.560.

### 11.3 The model that works

Fleet-day holdout, 28 unseen days from 2026-06-20:

| Model | MAE | MAPE |
|---|---|---|
| mean litres (no model) | 9,966 L | 16.5% |
| fleet rate × work_hrs | 11,472 L | 18.6% |
| **litres/active-unit × active units** | **1,933 L** | **3.3%** |
| OLS(active units, work_hrs) | 1,905 L | 3.3% |

**Forecast fleet diesel from the count of active units**, at
**251.9 L per active unit-day**. That is a 5× improvement on the no-model
baseline and needs one input you already plan: how many units run tomorrow.
Adding work hours buys essentially nothing (3.3% either way), so prefer the
one-variable version — it is simpler and more robust.

Supporting constants: fleet burn rate **14.61 L/work-hr**, mean fleet day
**54,766 L**.

> **Note.** The "adding work hours buys nothing" claim above rested on a single
> 80/20 split. Section 12 re-tests it with rolling-origin CV over twelve
> feature sets: the conclusion holds (work hours are in fact slightly
> *harmful*), but one feature, `lag1_litres`, gives a small consistent gain.
> See section 12 for the final recommendation and for a leakage trap that
> looked like the best model on the scoreboard.

### 11.4 Caveats a forecast user must know

1. **Five months of data, one dry-to-wet transition** (2026-02-22 → 07-22).
   No annual seasonality is learnable. Do not extrapolate across a monsoon
   cycle.
2. **All 30,917 joined rows are contractor `RIM`.** The 14.61 L/work-hr figure
   is RIM's fleet, not site-wide. No other contractor's fuel reaches this
   table, so a site-wide forecast cannot be built from it.
   Activity mix is also lopsided: **28,108 rows `SUPPORT` vs 2,809 `HAULAGE`**,
   so the rate is dominated by support running, not by ore haulage.
3. **The 3.3% MAPE assumes you know the active-unit count.** In a real forecast
   that is itself predicted, so error compounds; treat 3.3% as a floor.
4. **`WAITING_TIME` is a haulage-cycle table**, so fuel is captured for trucks
   in the weighbridge workflow. Excavators, dozers and light vehicles are
   under-represented.
5. **137 rows carry a U+200E invisible mark** prefixing `EQUIPMENT_ID`, which
   splits units (`?N677` vs `N677`). `fuel_training_set.py` strips it and
   upper-cases; without that, 735 real units inflate to 837 phantoms.

---

## 12. Feature search — testing the "exhausted" claim properly

Section 11 concluded the feature space was exhausted after **one** 80/20 split.
That was weak evidence, so `scripts/fuel_model_features.py` re-tests it with
**rolling-origin CV** (expanding train window, predict the next 7 days) across
twelve feature sets and six CV configurations.

### 12.1 A leakage trap, caught and rejected

The apparent winner was `units + fills` at **2.38% MAPE**, a 1.07 pp gain.
**It is leakage.** `fills` is the count of refuel events, and
`litres = fills × 199.2 L` fleet-wide — `corr(fills, litres) = **+0.9924**`.
It is the target decomposed, not a predictor, and it is unknowable before the
day happens. **Rejected.** Recording it because it looked like the best result
on the scoreboard.

### 12.2 Leakage-free results, across six CV settings

MAPE, rolling-origin. `tr` = minimum training days, `st` = forecast step.

| Features | tr60/st7 | tr60/st14 | tr80/st7 | tr80/st14 | tr100/st7 | tr100/st14 |
|---|---|---|---|---|---|---|
| units only | 4.56% | 4.71% | 3.46% | 3.47% | 3.28% | 3.32% |
| **units + lag1_litres** | **4.39%** | **4.56%** | **3.29%** | **3.29%** | **3.23%** | **3.26%** |
| units + is_sunday | 4.42% | 4.57% | 3.29% | 3.30% | 3.28% | 3.32% |
| units + work_hrs | 4.58% | 4.77% | 3.47% | 3.47% | 3.35% | 3.50% |

Everything else tested was worse than `units only`: day-of-week (3.36%),
tonnes (3.37%), tickets (3.38%), 7-day lag (3.60%), standby+breakdown (4.12%),
kitchen sink (4.47%), linear trend (4.60%). Trend and the kitchen sink overfit
badly on 139 days.

### 12.3 Verdict: section 11 was right, but for a weaker reason than it gave

`units + lag1_litres` wins in **all six** configurations, so the gain is real
rather than a split artefact. But it is **~0.17 pp** (MAE 1,819 → 1,757 L/day
on a 56,161 L mean), and the fitted lag coefficient is **0.037** — yesterday's
litres carry almost no weight.

**Recommendation unchanged: ship the one-variable model.**

```
litres_per_day = -3928 + 270.4 × active_units        # simple, recommended
litres_per_day = -4863 + 265.3 × active_units + 0.037 × yesterday_litres
```

The second form is marginally more accurate and available in production
(yesterday's litres are known by then), so use it if the plumbing is free.
It is not worth a dependency on its own.

**What would actually move the number** is not a better feature set on this
data. It is more data: other contractors beyond RIM, a full monsoon cycle, and
fuel capture for excavators and dozers rather than the current
SUPPORT-dominated truck mix. Those are collection changes, not modelling ones.

---

## 13. End-to-end forecast error — the number to actually quote

Sections 11-12 report **3.3% MAPE**, but that figure assumes you already know
tomorrow's active-unit count. **In a real forecast you do not.** The unit count
must itself be predicted, and the errors compound. `scripts/fuel_forecast_e2e.py`
measures the honest end-to-end figure with no oracle inputs, rolling-origin
throughout.

### 13.1 Results, 59 forecast days, 7-day horizon

| Method | units MAPE | litres MAPE | litres MAE |
|---|---|---|---|
| no model (train mean) | — | 19.3% | — |
| **ORACLE units** (§11-12 figure) | 0.00% | **3.5%** | 1,819 L |
| **last value** | 12.21% | **13.0%** | 7,145 L |
| 7-day MA | 13.65% | 13.7% | 7,234 L |
| 28-day MA | 19.53% | 21.6% | 11,046 L |
| day-of-week MA | 20.56% | 22.7% | 11,594 L |

**Quote two numbers, not one:**

- **~3.5%** (±1,800 L/day) if the mine plan supplies tomorrow's active-unit
  count. This is the realistic operating case — the count is a planning
  input, not a mystery.
- **~13%** (±7,100 L/day) fully autonomous, with nothing but history.
  Forecasting the unit count costs **+9.5 pp**, which dominates all remaining
  model error. Still beats the 19.3% no-model baseline.

**The bottleneck is not the fuel model. It is knowing how many units will run.**
Active-unit count has sd 48 on a mean of 222 (p05 133, p95 281): the fleet size
swings hard day to day, and no history-only predictor tracks it well. The best
is naive persistence at 12.2%; longer averages are worse, so the variation is
not weekly seasonality.

### 13.2 Dead end: the mine plan cannot supply the unit count

`MINING_PLAN_WEEKLY` looked like the obvious source of forward-looking demand.
It is not usable here:

- **Coverage stops 2026-05-01.** The fuel holdout begins 2026-05-19, so the
  plan cannot be tested on it at all. Only 64 of 139 fuel days overlap.
- **No signal on the overlap.** `corr(plan_bcm, litres) = **+0.006**` and
  `corr(plan_bcm, active_units) = **-0.096**`. Planned volume does not predict
  fuel burn or fleet size.

`dbo.RAINFALL` fails the same way: it ends 2026-04-11, covering 63 of 139 days.

**Recommendation.** Feed the model the active-unit count from whatever
scheduling system actually holds tomorrow's roster, and you get ~3.5%. If that
number is unavailable, use persistence and quote ~13%. Do not attempt to derive
the unit count from `MINING_PLAN_WEEKLY`.

