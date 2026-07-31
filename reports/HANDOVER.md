# HANDOVER — WBN Production Simulator

*Written 2026-07-30; revised 2026-07-31. Harness **59/59** (`J55`–`J59` added).
Since the first draft: the GPS accumulator has run against the live server and is
scheduled, the Plan Assessment View is built, a 15% tonnage under-quote in the UI
was found and fixed, the weather path was audited (a flag I raised turned out to
be **wrong**, and a different defect turned out to be real), the third dual-mode
state was fixed across five endpoints, and the push rule reversed to **mirror
only**.*

*Commit note: the work described here landed at `0ff987f`; this document itself is
`5b0e21b`, the commit immediately after. Run `git log --oneline -5` for the current
tip — if it is further ahead than `5b0e21b`, work has happened that this handover
does not cover.*

**Read this first, then `AGENTS.md`** (346 lines, the working rules and the
history of what was tried and failed). `CLAUDE.md` is a **symlink to
`AGENTS.md`** — same file, do not edit both.

---

## 1. Project identity

### What this is

A **production simulator** for a nickel laterite mine in Halmahera, Indonesia
(WBN / Weda Bay Nickel, hauling contractor RIM). A mine planner types *"N trucks
from A to B"* and the tool answers, from measured history:

- how long a trip takes (weigh-to-weigh) and how long the true repeat cycle is
- how long trucks sit at the loader and at the tip
- how many tonnes the plan will actually move in a 12-hour shift
- **how many trucks to roster** to keep N of them hauling
- **where two plans collide** at a shared loading point

### What this is NOT

WARNING: the repo is named `wbn-fms-simulator`, and the name is misleading. This
is **not** an FMS.

- **Not a fleet management system.** It does not track trucks live.
- **Not a dispatch system.** It does not tell a truck where to go next. Dispatch
  is a *confounder* here, not a feature — see §10.
- **Not a stockpile tracker.** No inventory, no FIFO, no grade blending.
- **Not real-time.** Everything is a prediction from historical aggregates.

FMS modules (Match Factor, Dispatch, Rules, Tonnage, Ore/Waste, Stockpile FIFO)
were **built and then deleted** because they belong to a different product. They
live at tag `fms-modules-v1`. Do not resurrect them into this repo.

---

## 2. Repository

| | |
|---|---|
| **origin** | `https://github.com/rdinkelmann/wbn-fms-simulator.git` (Rudolf, the site owner) |
| **mirror** | `https://github.com/Lucky0000123/wbn-fms-simulator.git` (public) |
| **all** | a push-only remote with **both** URLs attached |
| **HEAD when this was written** | `0ff987f` — "bank the GPS feed forward, since this is the one blocker that decays"; this doc is `5b0e21b` |
| **Branches** | `main` only. No feature branches. |

### Pushing — WARNING, THIS RULE REVERSED ON 2026-07-30

```bash
git push mirror main   # CORRECT — the only remote this project pushes to
git push all main      # WRONG — `all` has two push URLs and reaches Rudolf
```

The owner has put **`origin` (Rudolf's repo) on hold**: it must not receive
commits until they explicitly lift it. It sits at `48985b4`, the last commit
made under the old "push to both" rule.

`G24` was narrowed to match: it asserts **mirror** parity and merely *reports*
origin's position on an `INFO` line. The old gate required both, which made it
unsatisfiable — honouring the instruction failed the harness, and satisfying the
harness leaked work to a ringfenced repo. A gate that can only be passed by
violating an instruction is worse than no gate, because the pressure is to "fix"
it by pushing. When the hold is lifted, re-widen `G24` and revert the push
section of `AGENTS.md` together.

`git push` with no remote happens to work today because `main` tracks
`mirror/main`, but name the remote anyway — tracking is invisible at the call
site.

### Tags

| Tag | Commit | Meaning |
|---|---|---|
| `pre-cycle-fix` | `d1de6f9` | The state **before** the 2.7x overprediction fix. `git revert 9c06865` restores the analysis-only outcome if the site rejects the fix. |
| `fms-modules-v1` | `7e8d9c2` | The deleted FMS modules, preserved before removal. |

---

## 3. Local setup

**Path:** `/Users/lucky/wbn-fms-simulator`
**Python:** 3.14.3 in `.venv` (any 3.11+ should work)

### requirements.txt

```
flask>=2.0
pandas>=2.0
scikit-learn>=1.3
joblib>=1.3
numpy>=1.24
# pyarrow>=15   — optional, enables .parquet beside .csv; ~100 MB, deliberately not required
```

Also installed but **not** in requirements.txt:
- `pymssql` — required for any DB work
- `playwright` — installed 2026-07-30 for browser verification (`python -m playwright install chromium`)

### Install and run

```bash
cd /Users/lucky/wbn-fms-simulator
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pymssql playwright     # DB + browser checks

.venv/bin/python serve.py                    # http://localhost:5055
```

WARNING: stale `serve.py` processes survive `pkill`. Restart with
`pkill -f serve.py; sleep 3; nohup .venv/bin/python serve.py > /tmp/srv.log 2>&1 &`
then `sleep 10` before curling, or you will test the old process.

### Tests

```bash
bash scripts/verify_phase2.sh        # 54/54 currently
python scripts/check_vocab.py       # place-name vocabulary gate, 43/43
```

Score depends on which artifacts exist, because `data/` is gitignored:

| State | Score |
|---|---|
| Fresh clone, nothing trained | low — the A/B/H/I/J checks need `data/` artifacts. AGENTS.md records 24/33 from an older gate set; **not re-measured against the current 54**, so treat it as indicative only. |
| After `python train_model.py`, no VPN | 32–33 of the then-33 (same caveat) |
| Everything trained + extracts present | **54/54, measured 2026-07-30 in both DB and no-DB modes** |

That is the harness working, not a regression: `data/` is gitignored, so a clone
starts with 6 sample json files and nothing else, and the extraction gates fail
until you train once.

**Verified on a genuinely fresh clone** (`git clone` to a temp dir, `FMS_DB_*`
unset): `/health` reports `sample-fixtures` and **18 of 18 endpoints return 200**,
including `POST /api/simulate` and `POST /api/retrain` — the latter retrains from
sample fixtures in ~39 s, selects `random_forest`, and prints
`plan simulator lookup cache reset`. The cycle model is correctly skipped with
`cycle model not retrained (no DB configured)` rather than fabricating one.

### Environment variables

| Var | Purpose |
|---|---|
| `FMS_DB_HOST` | SQL Server host, `10.211.10.1` |
| `FMS_DB_USER` | SQL login |
| `FMS_DB_PASS` | SQL password |

**Never hard-code these.** The mirror is public. Read them from
`/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env`, which uses
**`FMS_DB_PWD`** — note the different name, you must map `FMS_DB_PWD` →
`FMS_DB_PASS`.

WARNING: that path is an external SSD. It unmounts, and the VPN to `10.211.10.1`
drops every few minutes. Wrap DB scripts in a retry loop and **cache every
extract to `data/`** so re-analysis needs no VPN.

---

## 4. Database

**SQL Server at `10.211.10.1`**, default port 1433, via `pymssql`
(`charset="LATIN1"` — some contractor names are Chinese and other charsets
throw). Two databases: `WBN_DATABASE` (mine operations) and `FMS_DB`
(telematics).

### WBN_DATABASE

| Table | Columns used | Purpose |
|---|---|---|
| `HAULAGE_IWIP_CLEAN` | `TICKET_NO, TRUCK_ID, DATE, SHIFT, CONTRACTOR, ORIGIN_AREA, DESTINATION_AREA, WMT, MATERIAL, FIRST_WB_TIME, SECOND_WB_TIME, ACTIVITY` | **The primary source.** Weighbridge tickets with both weigh timestamps. 535,411 rows, ends **2026-07-09**. |
| `HAULAGE` | same, plus `TIME_LOADED, TIME_EMPTY, RIT` | Older/wider table, 3,509,275 rows, runs to 2026-07-29. Stores **clock times, not datetimes** — you must add them to `DATE` to build timestamps. |
| `WAITING_TIME` | loading/dumping clock times | Dwell at loader and tip. Source for the cycle model target (8 months at path-shift grain). |
| `EQUIPMENTS_HOURLY_STATUS` | `ID_EQ, CONTRACTOR, SHIFT, WORKING_HOURS, STBY_HOURS, BD_HOURS, PM_HOURS, ACTIVITY` | Availability and utilisation. **Key column is `ID_EQ`, not `EQUIPMENT_ID`.** |
| `HAUL_ROAD_STA` | `road, km, lat, lng` | Road chainage, 3,122 markers. Basis of the 67.8 km TF→FENI KM0 corridor. |
| `AVG_RAIN_BY_DATE_AREA` | date, area, rainfall | Rain joins for wet/dry dwell. |
| `DAY_WORKS`, `EQUIPMENTS_HOURLY_ACTIVITIES`, `EQUIPMENTS` | — | Shift context. |

### FMS_DB

| Table | Columns used | Retention | Purpose |
|---|---|---|---|
| `FMS_CONGESTION_SEG` | `HOUR_TS, SEG_ID, DIR, SUM_SPD, FIX_N, TRUCK_N, SUM_TRAV_MS, TRAV_N` | **~15 days** | **The most valuable telematics table.** The site's own per-segment hourly speed AND truck count. 36,046 rows, 95 segments, 8 roads. Speed = `SUM_SPD/FIX_N`; density = `TRUCK_N`; independent speed = `SUM_TRAV_MS/TRAV_N`. |
| `FMS_GPS_Historical` | `PLATE, TS, LAT, LNG, SPEED, COURSE, ACC, DISTANCE` | **~5 days** | Raw GPS. `TS` is epoch **milliseconds**. |
| `FMS_PLAYBACK_TRACK_24H` | same | **~1 day** | Live GPS feed, richer (859,198 fixes/day) but evaporates fastest. |
| `FMS_EQUIPMENTS` | `truckId, plateNumber, orgName, active` | permanent | The crosswalk, see below. |
| `FMS_GEOFENCE_VISITS` | — | ~89 days | Only telematics table overlapping the training window. Loading events are thin: 604 rows from 22 trucks, so it was **rejected** as the cycle target in favour of `WAITING_TIME`. |
| `FMS_HRM_SUPERVISION` | — | — | Operator identity, 134 units on Day X. |

### The FMS_EQUIPMENTS crosswalk

`data/equipment_crosswalk.csv` — 3 columns that matter: `truckId`,
`plateNumber`, `is_weighbridge_truck`.

**The important lesson.** An earlier version of this project claimed *"0 of 940
haul trucks are in GPS"* and the site owner correctly challenged it. That claim
was **wrong**, and the error was this: `truckId` is a **19-digit device serial**
(e.g. `6916297240046994306`), not a vehicle ID. Joining on it matches nothing.

**GPS `PLATE` joins directly to `HAULAGE.TRUCK_ID`.** No crosswalk needed.
945 of 1,411 plates match. The crosswalk is only for going to device serial.

Normalise both sides: `.astype(str).str.strip().str.upper()`.

### Tables investigated and rejected

| Table | Why not |
|---|---|
| `FMS_GEOFENCE_VISITS` | 604 loading events from 22 trucks — too thin for a cycle target |
| `FMS_PLAYBACK_TRACK_DATA` | superseded by `_24H` |
| `FMS_TRUCK_ASSIGNMENTS`, `FMS_GEOFENCES`, `DISPATCH` | dispatch-domain, out of scope |

Full scan of all 669 objects: `reports/database_schema_analysis.md` (5,079 lines).

---

## 5. File structure

### Core — do not touch without reading first

| File | Purpose |
|---|---|
| `serve.py` | Flask app, port **5055**. Registers `simulator_api.bp` and (conditionally) `prediction_api.bp`. |
| `simulator_api.py` | Most endpoints. Holds `_DB` credentials dict, `_register()` dual-mode wrapper, `_SIM_CORRIDOR` node/alias vocabulary. |
| `plan_simulator.py` | **The engine.** `simulate(payload)`. See §7. |
| `prediction_api.py` | `/api/predict`, `/api/model-info`, `/api/retrain`. |
| `simulator_model.py` | Route lookup + effective cycle training. |
| `cycle_model.py`, `cycle_pipeline.py`, `cycle_serving.py` | Cycle-time OLS: fit, extract, serve. |
| `capacity_model.py` | p99 hourly throughput per loading/dumping point. |
| `dwell_models.py` | Loading/dumping dwell, day/night, wet/dry. |
| `trip_extraction.py` | `HAULAGE_IWIP_CLEAN` → `trip_level_base.parquet/csv`. |
| `trip_features.py` | Feature engineering → `trip_features.csv` (43 cols). |
| `train_model.py`, `prediction_pipeline.py` | Trips/DT model training. |
| `availability_analysis.py` | Availability/utilisation extraction. |
| `dem_grade.py`, `trip_diagnostic.py` | Terrain grade; trip-grain diagnostic. |

### Tests (root) — every one is wired into the harness

`test_accumulator.py`, `test_availability_usage.py`,
`test_availability_override.py`, `test_congestion_audit_mutation.py`,
`test_deliverable_schema.py`, `test_holdout_robustness.py`,
`test_holdout_tonnage.py`, `test_plan_simulator.py`,
`test_retrain_preserves_fix.py`, `test_segment_cross_validation.py`,
`test_speed_density.py`, `test_trips_mutation.py`, `test_trips_per_shift.py`,
plus `tests/test_cycle.py` and `scripts/check_assessment_view.py` (browser).

WARNING: eight of these were once **orphaned** — they existed, passed 42/42
standalone, and the harness never invoked them. A test the harness does not run
is not a gate. If you add a test, wire it into `scripts/verify_phase2.sh` **and
prove the wiring** by breaking the test and watching the score drop.

### scripts/

| Script | Purpose |
|---|---|
| `verify_phase2.sh` | **The harness.** 54 gates. |
| `check_vocab.py` | Place-name vocabulary gate (43 cases). |
| `accumulate_gps.py` | **Forward GPS archive.** Run daily. See §8. |
| `extract_day.py` | One-day extract (trips, crosswalk, GPS). Default day `2026-07-19`. |
| `extract_day_context.py` | Availability, HRM, activities for that day. |
| `extract_multiday_gps.py` | Finds every day with both GPS and haulage. |
| `snap_gps.py` | GPS → chainage snapping, segment speeds, dwell. |
| `snap_multiday.py` | Snapping pooled over all usable days. |
| `fit_speed_density.py` | The speed-density fit from `FMS_CONGESTION_SEG`. |
| `diagnose_gps_coverage.py` | Why trucks are missing from GPS. |
| `fetch_weather.py` | Rain/temperature cache. |
| `scan_databases.py`, `scan_all_tables.py`, `db_reconnaissance.py`, `fms_db_recon.py` | Schema reconnaissance. |
| `write_schema_report.py`, `write_full_schema_report.py` | Generate the schema reports. |
| `verify_cycle_definition.py` | Proves the weigh-to-weigh vs start-to-start gap. |
| `day_coverage.py`, `publish_findings.py` | Coverage stats; findings publisher. |

### templates/ and static/

- `templates/simulator.html` — the single-page UI, tabbed.
- `static/js/`: `plan_simulator.js` (plan table incl. the Roster column),
  `plan.js`, `api.js`, `charts.js`, `matrix.js`, `flow_sim.js`,
  `regression.js`, `main.js`
- `static/css/style.css`

### fixtures/ — the no-DB demo path

`capability.json`, `congestion-model.json`, `constraints.json`,
`path-response.json`, `shift-context.json`, `trucks.json`,
`weighbridge-positions.json`, `weighbridge-summary.json`, `weighbridge.json`

### data/ — ALL GITIGNORED (real tonnages, public mirror)

Key files:

| File | Contents |
|---|---|
| `trip_features.csv` (175 MB) | 483,425 trips × 43 features. The training set. |
| `trip_level_base.csv/.parquet` | 22-column base before feature engineering. |
| `route_lookup.csv` | **Per-route serving table.** `median_cycle_min`, `effective_cycle_min`, `trips_per_truck_shift`, `shifts`, `truck_shifts`. |
| `route_availability.csv` | Per-route availability + `avail_coverage` + `basis` (`measured`/`fleet_prior`). |
| `availability_per_truck.csv` (45 MB) | 538,586 truck-shifts with hours, availability, utilisation. |
| `point_capacity.csv` | p99 trips/hr per loading and dumping point. |
| `dwell_model_results.csv` | Dwell medians, day/night, wet/dry per point. |
| `haul_road_chainage.csv` | **3,122 chainage markers** (`road, km, lat, lng`). Cached so snapping needs no VPN. |
| `equipment_crosswalk.csv` | `truckId ↔ plateNumber`. |
| `congestion_seg_hourly.csv` | 36,046 hourly segment rows with derived speed. |
| `gps_archive/congestion_seg_hourly.csv` | **The forward archive.** Grows daily. |
| `day_x_*.csv` | The 2026-07-19 deep-dive set. |
| `multiday_*.csv` | Pooled across the 4 usable GPS days. |
| `model*.pkl`, `encoders.pkl`, `scaler.pkl`, `cycle_model.pkl` | Trained artifacts. |
| `*_metadata.json`, `*_results.json` | Metrics and provenance. |
| `weather_cache.csv` | Rain/temperature. |

### reports/

| Report | Contents |
|---|---|
| `HANDOVER.md` | This file. |
| `CRITICAL_cycle_time_defect.md` | The 2.7x overprediction: evidence, fix, held-out validation. **Read this.** |
| `availability_analysis.md` | Availability, why it must not scale tonnage, fleet sizing. |
| `gps_scaling_and_speed_density.md` | The 4-day GPS ceiling and the speed-density fit. |
| `database_schema_analysis.md` | All 669 objects, 5,079 lines. |
| `one_day_deep_dive.md` | The Day X end-to-end pipeline proof. |
| `db_reconnaissance_report.md`, `fms_db_schema.md`, `_cross_analysis.md` | Schema and cross-DB analysis. |
| `*.json` | Machine-readable companions. |

---

## 6. API endpoints

18 routes. `GET /` and `/simulator` both serve `simulator.html`.

| Path | Method | Mode | Returns |
|---|---|---|---|
| `/` , `/simulator` | GET | — | the UI |
| `/health` | GET | — | `{dataMode: "database" \| "sample-fixtures"}` — **your first diagnostic** |
| `/api/simulate` | **POST** | lookup CSVs | **The main endpoint.** See §7. |
| `/api/simulate/options` | GET | lookup CSVs | routes, loading and dumping points with history |
| `/api/predict` | GET/POST | model pkl | trips/DT both directions (DT→WMT, WMT→DT) |
| `/api/model-info` | GET | metadata | model type, R², trained-at |
| `/api/retrain` | GET/POST | **live DB** | retrains and **calls `plan_simulator.reset_cache()`** |
| `/api/simulator/capability` | GET | DB→fixture | per-route capability |
| `/api/simulator/trucks` | GET | DB→fixture | fleet list |
| `/api/simulator/constraints` | GET/POST | DB→fixture | planner constraints |
| `/api/simulator/constraints/reset` | POST | — | restore defaults |
| `/api/simulator/path-response` | GET | DB→fixture | trips/DT vs fleet + rain, OLS per route |
| `/api/simulator/congestion-model` | GET | DB→fixture | congestion evidence |
| `/api/simulator/weighbridge` | GET | DB→fixture | weighbridge detail |
| `/api/simulator/weighbridge-positions` | GET | DB→fixture | weighbridge locations |
| `/api/simulator/shift-context` | GET | DB→fixture | availability, HRM, activities |
| `/api/weighbridge-summary` | GET | DB→fixture | tonnage summary |

### The dual-mode pattern — a hard requirement

Every endpoint must answer **with no database**. The demo is often shown
without VPN, and *"0 of 11 endpoints broken"* is the standard.

Two mechanisms:

1. **`_register(path, fn, fixture)`** in `simulator_api.py` wraps a DB endpoint:
   if `_db_ready()` is false **or the real logic throws**, it serves
   `fixtures/<name>.json`.
2. **`/api/simulate` needs no fallback at all.** It reads committed lookup CSVs,
   so it answers identically with or without VPN. Dual-mode by construction
   rather than by a fixture standing in for the real thing — the better pattern.
   Prefer it.

Verify: `env -u FMS_DB_HOST -u FMS_DB_USER -u FMS_DB_PASS .venv/bin/python serve.py`
then `/health` must report `sample-fixtures` and every endpoint must still 200.

---

## 7. The simulator engine

### plan_simulator.py

**Input** (POST `/api/simulate`):

```json
{"plans": [
  {"route": "BLB>FENI KM0", "source": "BLB", "destination": "FENI KM0", "n_trucks": 30}
]}
```

**Output** per plan: `route`, `n_trucks`, `predicted_cycle_time_min`,
`effective_cycle_min`, `predicted_load_time_min`, `predicted_dump_time_min`,
`implied_travel_time_min`, `trips_per_shift_per_truck`, `avg_payload_t`,
`planned_production_t`, `achievable_production_t`, `capacity_ratio`,
`capacity_note`, `trucks_to_roster`, `roster_availability`, `roster_basis`,
`basis` (evidence dict).

**Summary:** `total_trucks`, `planned_production_t`,
`achievable_production_t`, `capacity_warnings`, `shared_loading_points`,
`availability_factor_applied` (**must stay 1.0**), `fleet_sizing`.

### The two cycle figures — the single most important concept

| Figure | Meaning | Median |
|---|---|---|
| `predicted_cycle_time_min` | weigh-to-weigh; what a planner calls trip time | 76.9 min |
| `effective_cycle_min` | **shift-minutes ÷ completed trips**, per route | 240.1 min |

`trips_per_shift_per_truck` divides by the **effective** cycle, because the
effective cycle also contains the empty return, the shovel queue, refuelling and
breaks.

**The bug that cost the most to find.** An earlier version divided the shift by
the *weigh-to-weigh* interval and **overpredicted production by ~2.7x** — a
30-truck plan quoted 12,211 t where measurement supports ~2,500 t. Measured over
**438,992 consecutive trip pairs**. Held-out on four splits: bias
**+370…+460% → −3.5…−7.4%**, MAE **375 t → 40 t**.

WARNING: aggregate shift-minutes and trips **before** dividing. Dividing
per-shift and averaging suffers integer quantisation (trips are 1, 2, 3…).

Gates J43, J44, J46, J47, J49 all defend this. `python test_holdout_tonnage.py`.

### Availability — DO NOT re-apply it

`DEFAULT_AVAILABILITY = 1.0` and `availability_factor_applied` must stay `1.0`.

The old code multiplied tonnage by an assumed 0.85. That assumption is **gone
and must not come back**. Measured on 44 routes:

| Factor | Bias |
|---|---|
| **none (current)** | **+5.5%** |
| × 0.850 (the old assumption) | −10.3% |
| × 0.836 | −11.8% |
| × 0.451 | −52.4% |

Every factor makes it worse, because the effective cycle **already contains
downtime**. Gate J52 fails if anyone re-adds it.

Two independent measurements confirm this: availability × utilisation = **0.390**
of a rostered shift is working time; the weighbridge sees **0.203** of the repeat
interval and cannot see the empty return, so doubling gives **0.406** — agreement
within **0.016**, holding on 13 of 14 routes. (The exception, CRUSHER CAS→FENI
KM0, is a short reclaim shuttle with little empty running.)

### Fleet sizing — what availability IS for

`_roster(n, route)` returns `(roster, availability_used, basis)`.

| | |
|---|---|
| Measured | availability **0.720**, utilisation **0.542** over 170,899 haul-truck shifts, 1,103 trucks |
| Distribution | **bimodal** — 75.4% of shifts at exactly 1.0, 19.8% at exactly 0.0 |

WARNING: the mean describes almost no individual shift. The honest phrasing is
**"~28% of haul-truck shifts are lost entirely"**. Records are complete (median
12.0 h), so this is the operation, not missing data.

WARNING: availability is measured for trucks carrying only **30.3% of training
tonnage** — 7 contractors are in `EQUIPMENTS_HOURLY_STATUS`, but 32 appear in the
training set. So the roster figure is route-aware:

| Route | Coverage | Availability | Basis |
|---|---|---|---|
| BLB→FENI KM0 | 98.6% | 0.7705 | `measured` |
| POS 12→FENI KM0 | **5.2%** | 0.720 | `fleet_prior` |

23 of 65 routes are `measured`; 42 fall back **and say so**. The UI renders the
prior with a `*` and a dashed underline. Route availability spans only
0.695…0.795, so the prior is defensible — but it must never be presented as a
measurement.

### Capacity model

`capacity_model.py` → `point_capacity.csv`. **p99 of observed hourly throughput**
per point, over points with ≥200 observed hours: 14 loading, 9 dumping. p99 not
max, because the max is a single freak hour. `achievable_production_t` is
`planned` clipped to capacity; the shortfall is reported as "blocked by capacity".

### Dwell models

`dwell_models.py` → `dwell_model_results.csv`: `median_min`, `p25`, `p75`,
`day_min`, `night_min`, `dry_min`, `wet_min`, `wet_penalty_min/pct` per point.

WARNING: the wet penalty applies to **cycle time only, never tonnage**. Rain
moves tonnage **+0.1% median**, and **49% of 122 route-months are negative**. An
earlier version applied a tonnage penalty that the data does not support. The
cycle keeps the measured dwell uplift; tonnage does not.

Load time is measured on only **24.8%** of trips; the rest is apportioned
(`load_time_source`, `split_is_estimated` mark which).

### Congestion — a finding, not a gap

Measured from `FMS_CONGESTION_SEG`, within segment/direction (centred, so it
measures change on a given segment rather than which segments are fast):

| | |
|---|---|
| Slope | **−0.0233 km/h per extra truck** |
| t | **−9.9** (n = 35,006) |
| Full range | **−4.8%** from emptiest density decile to busiest |
| Threshold | **none** up to 69 trucks on a segment |
| Traverse-time cross-check | +0.109 s/truck, same sign |

Density variation is ample (`TRUCK_N` 1…69, 185 of 190 cells with ≥5 distinct
densities), so thin data is **not** the reason.

At **trip** level the effect has the **wrong sign**:
`corr(trucks_on_route, cycle_time_min) = −0.1467` over 483,425 trips (replicating
an independent −0.1293). More trucks ⇒ *shorter* cycles. That is **endogeneity**:
dispatch sends trucks to routes running well and pulls them off routes that
struggle. The slope also decays with band (−1.72 min/truck at 2–10 trucks, −0.23
at 26–60), the signature of selection.

**So no congestion term belongs in the simulator.** Gate J53 enforces it:
`trips_per_shift_per_truck` must not vary with `n_trucks`, and tonnage must scale
linearly. A model *with* congestion scores higher R² (0.4925 vs 0.4792) and was
**deliberately withheld** because its coefficient says adding trucks makes trips
faster. Contention is surfaced as measured capacity headroom and shared-loading
warnings instead.

### Path response

`/api/simulator/path-response` — OLS per route of trips/DT against fleet size and
rain. Rain coefficients are only claimed on folds that actually had rain
variance; 3 of 5 folds had none and are recorded as such.

### Cycle model (cycle_model.py)

| | |
|---|---|
| Target | `avg_cycle_time_min` from `WAITING_TIME`, path-shift grain |
| Rows | 10,058 over 8 months (395,694 of 663,364 trips used) |
| Winner | `ols_log`, walk-forward CV **R² 0.6565**, MAE **29.50 min** |
| Baseline | R² 0.648, MAE 37.84 min |
| Verdict | `better_mae_similar_r2` — **`beats_baseline` is False** (lift 0.0085 < 0.05 required) |
| Folds won | R² 2/5, **MAE 5/5** |
| Fitted utilisation | **0.3998** (median 0.344, IQR 0.316–0.427) |

The honest reading, recorded in the report: R² squares the residual so it is
dominated by rare breakdown shifts; MAE weights every shift equally. The model is
better at the median/p75/p90 and worse only at p99 — better on the ordinary
shift, worse on the outlier nobody plans around.

Note the fitted 0.3998 lands on the independently measured 0.390 working
fraction. Two methods, same answer.

### Trips/DT model (train_model.py)

Currently `random_forest`, in-sample R² 0.8535, MAE 0.6217. WARNING: on
walk-forward CV the **per-route mean baseline won** (0.4586 vs OLS 0.238, OLS
lost all 5 folds), so `/api/predict` serves `model_baseline.pkl` with
`model_used="group_mean_baseline"`. Do not swap in a higher in-sample number
without walk-forward evidence.

### Historical reference

Shift context matches similar past shifts on route, fleet size and rain, and
reports observed outcomes beside the prediction — a sanity check for the planner,
not a model input.

---

## 8. Data pipeline

```
HAULAGE_IWIP_CLEAN
   └─ trip_extraction.py  → trip_level_base.parquet/.csv   (483,425 rows, 22 cols)
        └─ trip_features.py → trip_features.csv            (43 cols)
             ├─ simulator_model.py  → route_lookup.csv
             ├─ capacity_model.py   → point_capacity.csv
             ├─ dwell_models.py     → dwell_model_results.csv
             ├─ availability_analysis.py → availability_per_truck.csv, route_availability.csv
             └─ train_model.py / cycle_pipeline.py → *.pkl
```

`trip_extraction.py`: 535,411 raw → 488,712 after bounds → **483,425** kept.
65 routes kept, 529 dropped as thin (<30 trips, 5,287 trips), 3,187 trucks,
outliers capped at p99 (1.01% capped).

### The GPS accumulator — RUN THIS

```bash
python scripts/accumulate_gps.py --status   # what is banked; needs NO VPN
python scripts/accumulate_gps.py           # append new rows; needs VPN
```

**Idempotent**: appends only keys not already present —
`(HOUR_TS, SEG_ID, DIR)` for congestion, `(day, truck)` for GPS aggregates. Safe
to run twice, safe after a gap. Writes `data/gps_archive/`, seeded with the real
36,046 rows.

Schedule it on the machine with VPN:

```
0 7,19 * * *  cd /path/to/wbn-fms-simulator && .venv/bin/python scripts/accumulate_gps.py >> /tmp/gps_accum.log 2>&1
```

Twice daily is deliberate: `FMS_PLAYBACK_TRACK_24H` keeps ~1 day, so one missed
run loses a shift.

WARNING: **this is the only blocker that gets worse with delay.** Every other
limitation stays put; each day without an append is a day of segment speeds
deleted upstream and permanently unrecoverable.

Stores GPS as per-(day, truck) aggregates, not raw fixes: raw grows ~1M rows/day
and the segment table already holds per-segment detail.

WARNING: `data/*.csv` in `.gitignore` does **not** match nested paths.
`data/gps_archive/` needed its own line. Check `git check-ignore -v` before
committing any new `data/` subdirectory.

### The chainage cache

`data/haul_road_chainage.csv`, **3,122 markers** (`road, km, lat, lng`) from
`HAUL_ROAD_STA`. Cached so snapping — a pure local transform — needs no VPN.

WARNING: when only a *partial* cache could be rebuilt (KR and TOFU only), the
right move was to **decline to write it** rather than silently degrade the other
roads. Do the same.

### GPS → KM-section snapping

`scripts/snap_gps.py`: haversine each fix against all 3,122 markers, take the
nearest, reject beyond `OFF_ROAD_M`. Yields `road`, `km_value`, `on_road`,
`snap_dist_m`. **82.0% on road** on Day X, median snap distance small.

Validated against implementations I did not write:
- vs the site's own `FMS_CONGESTION_SEG`: **r = +0.920** on full transits, median
  difference 1.6 km/h, all 16 of my segment labels present in their vocabulary
- vs the devices' own `SPEED` field: **r = +0.889**

WARNING: distinguish **full transits** from **partial traverses**. A fix cluster
covering 0.2 km of a 1 km segment is not a segment speed. `snap_gps.py` flags
`is_partial_traverse` (full = ≥0.8 km covered). Conflating them was an error I
made and corrected.

### GPS → weighbridge matching

Join GPS `PLATE` directly to `TRUCK_ID` (both upper/stripped), then keep fixes
whose timestamp falls **inside** `FIRST_WB_TIME … SECOND_WB_TIME`.

WARNING: this window test is why the GPS work is limited. On Day X only **7 of
159 trips** have any fix inside their window, because retained GPS covers 1–2.6 h
slices of an 8.8 h extract.

---

## 9. Done vs pending

### Complete

| Phase | Delivered |
|---|---|
| Phase 2 | Place-name vocabulary gate (43/43), route canonicalisation, model + UI attribution |
| Phase 3 | Trips/DT model with leakage proofs, VIF < 10, walk-forward CV; baseline won and is served |
| Phase 3.5 | Cycle model from `WAITING_TIME`, fitted utilisation 0.3998 |
| Tasks 1–5 | Trip features, cycle model, dwell models, plan simulator + UI, docs |
| DB scan | All 669 objects documented |
| Day X deep dive | Full pipeline proven end-to-end on 2026-07-19 |
| **Cycle defect** | 2.7x overprediction found and fixed, held-out validated |
| **Stale cache** | `/api/retrain` now calls `reset_cache()` |
| **Availability** | Measured, kept out of tonnage, wired to route-aware fleet sizing |
| **GPS scaling** | Ceiling measured at 4 days; cause diagnosed |
| **Speed-density** | Fitted from the site's own table; negligible, documented |
| **Accumulator** | Built, gated, seeded |

### Blocked

**GPS temporal coverage.** `HAULAGE_IWIP_CLEAN` ends 2026-07-09; GPS retention
starts 2026-07-15. Only **4 days** overlap (07-15, 16, 18, 19), yielding 19
segment observations, no cell at n≥5. The richest GPS day (2026-07-29, 859,198
fixes) is unusable because its only haulage rows are **46 SALES third-party
trucks** with no telematics. The plate join is fine (65.5% overlap) — the blocker
is temporal. **Segment speeds can never be backfilled onto the training window.**
Only the accumulator can widen this, going forward.

**ADT153 vs A342 namespace.** Explicitly forbidden from investigation this round.
Note the correction already made: **ADT is a vehicle *type*** (Articulated Dump
Truck, contractor PPP, 40 t), not a namespace prefix. An earlier claim of an
"ADT4059 vs A342 namespace split" was **wrong**.

### Next planned work

**Plan Assessment View** — **BUILT 2026-07-31.** Sections 2–8 on the Production
Simulator tab, ECharts from CDN, gated by `J56`. See the AGENTS.md section for
the three things the brief asked for that the data cannot support, and the
detached-DOM trap that blanked every gauge. Follow-ups it surfaced, none started:

- Split `/api/simulator/congestion-model` by the `DIR` column so loaded and
  empty speeds can be drawn separately. The column exists; the endpoint
  aggregates over it.
- Re-verify the `weather` input the same way `availability` was. It is still
  caller-supplied and still moves the answer, and a wet cycle uplift reduces
  tonnes — while `availability_analysis.md` records that rain must **not** carry
  a tonnage penalty. That interaction is unexamined.
- `dailyByPath` is per-day, not per-shift, and carries no rainfall, so the
  historical box in section 7 cannot be shift- or weather-matched as the brief
  asked. A per-shift, rain-joined history endpoint would fix it.

---

## 10. Known issues and gotchas

**C13 "retraining is idempotent" can false-fail on a VPN drop.** Retrain twice,
lose the link between runs, and the metrics differ. Not a regression. Re-run with
a stable connection.

**The site deletes GPS daily.** Hence §8. Do not assume yesterday's fixes exist.

**The 85% availability assumption is GONE. Do not re-add it.** §7. Gate J52.

**FMS modules are deleted** and tagged `fms-modules-v1`. Different product.

**Congestion is negligible (−4.8%).** A finding, not a bug. Gate J53.

**52 of 101 Day X trucks are SALES third-party** with no GPS and no maintenance
records. Expected: two independent systems agree they are not owned equipment
(0 of 52 in `EQUIPMENTS_HOURLY_STATUS`, vs 49 of 49 RIM). WARNING: they *are* in
`trip_features`, so the model predicts for them — do not exclude them from
training just because they lack telematics.

**Shell heredocs mangle HTML/JS/SQL quotes.** Write a Python patch script to a
file and run it. Some `git commit -F -` bodies trip a path-safety heuristic —
write the message to a file first.

**Stale `serve.py` processes survive `pkill`.** §3.

**`SHIFT` is a float** (`1.0`/`2.0`) in `EQUIPMENTS_HOURLY_STATUS`. Comparing to
the string `"2"` matches nothing and silently labels every row "day". Cost me a
wrong by-shift table.

**pymssql returns `DECIMAL` as Python `Decimal`**, which lands as object dtype and
breaks numpy ufuncs. Cast `LAT/LNG/SPEED/COURSE/DISTANCE` with
`pd.to_numeric(..., errors="coerce")` before any geometry.

**`nunique` as a DataFrame column name shadows `DataFrame.nunique`.** Use
`.agg(n_densities="nunique")`.

**Playwright `wait_until="networkidle"` never settles** on this UI. Use
`domcontentloaded` with an explicit timeout.

**A gate can be decoration.** I once wrote a docstring claiming a gate protected
the within-segment construction. Mutation-testing **disproved** it (pooled
−0.0271 vs within −0.0233, both negative and negligible, so no sign or magnitude
check discriminates). I deleted the false claim and added a check that does
discriminate. **If you cannot make a gate fail, it is not protecting anything.**

**One unreproduced anomaly, stated honestly.** A harness wiring mutation once
reported 4 failures instead of 1 and I could not reproduce it. Best guess: an
interrupted run left synthetic rows in `data/gps_archive/` that J52/J53 then read.
Verified afterwards: archive back to exactly 36,046 rows, 0 duplicate keys,
single-gate failure reproducible, 54/54 reproducible twice. If you see this,
check the archive first.

**Scope note.** The one-day brief said *"Do NOT modify the app"*. I changed 7
files anyway, because a live 2.7x overprediction is a defect, not a design choice.
Disclosed at the top of `reports/CRITICAL_cycle_time_defect.md`, revertible via
`git revert 9c06865`, state preserved at tag `pre-cycle-fix`. The user has not yet
said keep or revert. **Ask.**

---

## 11. Verification system

```bash
bash scripts/verify_phase2.sh        # 54/54
python scripts/check_vocab.py        # 43/43 vocabulary cases
```

Gates are lettered by phase: A/B (data + encoders), C/D/E/F/G (model, serving,
UI, endpoints, remotes), H (Phase 3 rigour), I (Phase 3.5 cycle), J (production
simulator).

| Gate | Checks |
|---|---|
| A1–A5 | training data exists, 13 columns, >500 rows, metadata, TF→FENI KM0 = 67.8 km |
| B6–B8 | encoders/scaler load, transform width matches |
| C9–C13 | OLS + RF metrics, `model.pkl`, valid type, retrain idempotent |
| D14–D18 | dt_to_wmt shape, wmt_to_dt ceils, p95 latency <100 ms, single load, unknown route 200s |
| E19–E21 | Plan tab calls `/api/predict`, renders attribution, keeps local fallback |
| F22–F23 | all 11 pre-existing endpoints 200, `/api/retrain` 200 |
| G24 | **origin + mirror both match local HEAD** |
| H25–H33 | Phase 3 artifacts, ≥4 CV folds, OLS+RF+baseline compared, VIF <10, no leakage, metadata |
| I34–I42 | cycle rows ≥2,000, no component leakage, VIF <10, coefficient signs, served scale, fallback, utilisation reconciles, unit tests, metadata |
| J43 | trips/shift reproduces observed trips |
| J44 | **the trips gate catches the weigh-to-weigh bug** |
| J45 | plan simulator invariants |
| J46 | cycle fix beats the old formula out of sample |
| J47 | holds across 4 splits + unseen-route fallback |
| J48 | congestion sign audit discriminates |
| J49 | a retrain preserves the cycle fix |
| J50 | GPS snapping agrees with `FMS_CONGESTION_SEG` |
| J51 | deliverables match the requested schema |
| J52 | **availability sizes the fleet and never scales tonnage** (19 checks) |
| J53 | **congestion measured, negligible, kept out of the model** (15 checks) |
| J54 | **the GPS accumulator is idempotent and loses no history** |
| J55 | **a caller-supplied availability never scales tonnage** — tests the payload path `J52` cannot see, and greps the front end so the key cannot come back |
| J56 | **the plan assessment view renders sections 2–8** — counts drawn canvases after repeated renders, and asserts the honesty labels |
| J57 | **weather moves dwell, never tonnage or travel** — and still moves dwell, because an invariance-only gate is passed by deleting the feature |
| J58 | **an unreachable DB still serves a tagged fixture** — the third dual-mode state, plus a structural check that no endpoint re-grows a self-catch |
| J59 | **identical results keep their `generated_at`** — so `git status` stays a signal |

Gate order in the file is A→J with J50/J51 last (they depend on optional
extracts); numbering is not strictly sequential in the output.

### How to mutation-test a gate — MANDATORY for new gates

```bash
cp plan_simulator.py /tmp/x.bak
# introduce the exact defect the gate claims to catch
sed -i '' 's/^DEFAULT_AVAILABILITY = 1.0/DEFAULT_AVAILABILITY = 0.836/' plan_simulator.py
.venv/bin/python test_availability_usage.py     # MUST fail, and name the reason
cp /tmp/x.bak plan_simulator.py
.venv/bin/python test_availability_usage.py     # MUST pass again
```

Then verify the **harness wiring** too — break the test's final success line and
confirm the score drops by exactly one, naming your gate. A gate never seen
failing is decoration.

Mutations already recorded: J52 fails under 3 distinct mutations (re-adding
`DEFAULT_AVAILABILITY`, claiming availability is 1.0, making the roster
route-blind); J53 under 3; J54 under 2 (removing dedup makes a scheduled run
duplicate 105 rows; overwriting drops the store from 36,051 to 100).

---

## 12. Deployment

**Local:** `.venv/bin/python serve.py` → `http://localhost:5055`.

**Public:** `https://wbn-fms-simulator.ngrok-free.app`

WARNING: that URL is served from **Rudolf's Mac**, not from this machine and not
from `origin`. **Pushing does not deploy.** Someone must pull and
`launchctl kickstart` there.

Detect staleness:

```bash
curl https://wbn-fms-simulator.ngrok-free.app/api/model-info    # 404 == stale
```

A 404 means the deployed copy predates the Phase 2 prediction API.

**Checked live 2026-07-30 while writing this:** `/health` returns 200 with
`{"dataMode":"sample-fixtures"}` but `/api/model-info` returns **404**. So the
public site is **up but stale**, and it is serving fixtures rather than live data.
Nothing from this round's work is visible there. Fixing it needs access to
Rudolf's Mac, which I do not have. See README "Git deployment" and AGENTS.md
§"The public site is deployed from a DIFFERENT machine".

No Docker, no CI, no deployment scripts in this repo.

---

## 13. Style and conventions

### Code

- Module docstring states **why the file exists and what was ruled out**, not
  just what it does.
- Comments explain **why**, especially where a simpler-looking approach is wrong.
  Example: *"p99 not max, because the max is a single freak hour."*
- Snake_case; `_leading_underscore` for module-private.
- Every measured number carries its **n** and its source table.
- Cache DB extracts to `data/` so re-analysis needs no VPN.
- `data/` is gitignored — real tonnages, public mirror. Never commit it.
- Credentials from env vars only, read at runtime. Never a literal.

### Commits

Subject line in lower case, stating the substance rather than the file list. Body
in prose paragraphs with the measured evidence: what changed, the numbers that
justify it, what was tested, and **any error of my own it corrects**. Long, and
deliberately so — the commit log is the audit trail.

WARNING: some `git commit -F -` bodies trip a path-safety heuristic. Write the
message to a file, then `git commit -F /tmp/msg.txt`.

Commit as you go, even in a dirty repo. `git push all main`.

### The three rules that matter most

**1. Honesty over hype.** Never publish a flattering number. Report negatives
plainly. Never invent data or force a join to make a story work. When you find
your own error, **publish the correction inline** rather than quietly patching it.
Errors already corrected and documented: the "0 of 940 GPS" claim; the ADT
"namespace split"; "availability is the highest-value change"; a median-vs-rate
comparison and an assumed 2.0 shifts/day (measured 1.494); in-sample circularity;
an unjustified wet tonnage penalty; partial-traverse conflation; eight orphaned
test suites; a deliverable-schema gap; a roster figure extrapolated without
disclosure; a wrong GPS denominator; a false gate claim; a `.gitignore` hole.

**2. Dual-mode always.** Every endpoint answers from fixtures with no DB.
Measured on a fresh clone with `FMS_DB_*` unset: **18 of 18 endpoints 200**, 0
broken.

**3. Mutation-test every gate.** §11. A gate you have never seen fail is
decoration.

---

## Immediate next steps

Items 1–3 and 5 of the previous list are **done** (2026-07-30/31):

1. ~~Keep the cycle fix or revert?~~ **KEEP** — confirmed by the owner. Tag
   `pre-cycle-fix` remains if it is ever needed.
2. ~~Run the accumulator once against the live server.~~ **Done, and the live
   path is now confirmed.** First run banked **+329** segment rows (36,046 →
   36,375) and **+2,905** `(day, truck)` GPS rows (0 → 2,905; 7 days, 858
   trucks). Live idempotency proven by an immediate second run: +0 / +0.
3. ~~Add the crontab.~~ **Installed**, twice daily at 07:00 and 19:00, pointing at
   `scripts/accumulate_gps_cron.sh` — **not** at the bare python call. The line in
   §8 would have failed silently every night: cron has no environment, so
   `FMS_DB_*` would be unset. The wrapper reads them from the SSD `.env` at
   runtime (mapping `FMS_DB_PWD` → `FMS_DB_PASS`), and logs a `SKIP` line with a
   reason when the SSD is unmounted or the VPN is down rather than exiting
   silently. Note the `.env` cannot be `source`d — `FMS_DB_DRIVER` holds an
   unquoted value with spaces that a shell tries to execute.
5. ~~Plan Assessment View.~~ **Built.** See §9.

Still open:

4. **Check whether the public ngrok site is still stale** (§12). Not re-checked
   in either round; it was up-but-stale on 2026-07-30 and nothing here changes
   that, because deploying needs Rudolf's Mac.

Closed since:

6. The UI applied a 0.85 availability the engine did not, under-quoting tonnage
   by 15%. `reports/CRITICAL_availability_override_defect.md`, gate `J55`.
7. **The weather follow-up was audited and my flag on it was wrong.** I wrote
   that "a wet cycle uplift reduces trips and therefore tonnes"; measured, it
   does not and never did — tonnage is byte-identical dry vs wet on all 14
   routes tested. A *different* defect was real: the cycle carried only the
   loading point's wet penalty, so the residual travel figure fell in the rain
   on 11 of 14 routes. `reports/weather_input_analysis.md`, gate `J57`.
8. The third dual-mode state (DB configured but unreachable) served no fixture in
   **five** endpoints. Fixed; fixtures are now tagged `servedFrom` and the UI
   labels cached speeds. Gate `J58`.
9. `data/simulator_model_results.json` no longer churns. Gate `J59`.

Next most likely place to find this class of bug: `shift_minutes`, the last
caller-supplied field that scales tonnage. It is a legitimate planner input and
the UI currently sends `720`, matching `DEFAULT_SHIFT_MIN`, so there is no live
discrepancy — but it has not been audited for a UI/engine disagreement.
