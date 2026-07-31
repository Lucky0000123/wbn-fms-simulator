# AGENTS.md — working rules for this repo

> **Switching agents or new to this repo?** Read
> [reports/HANDOVER.md](reports/HANDOVER.md) first. It carries the
> project identity, DB tables, file tree, engine internals, the 54
> gates and the traps. This file is the working rules and the record
> of what was tried and failed.

Applies to every agent and contributor working in this checkout.

## Push to `mirror` ONLY — `origin` is on hold

**This rule reversed on 2026-07-30.** It previously read "push to BOTH remotes,
always". The owner has instructed that `origin` (Rudolf's repo) must **not**
receive commits until they explicitly lift the hold. Earlier commits already
reached `origin` under the old rule, so it sits at `48985b4`; everything after
that is mirror-only until told otherwise.

| Remote   | URL                                          | Push?                    |
|----------|----------------------------------------------|--------------------------|
| `mirror` | `github.com/Lucky0000123/wbn-fms-simulator`  | **YES — the only target** |
| `origin` | `github.com/rdinkelmann/wbn-fms-simulator`   | **NO — on hold**          |
| `all`    | both URLs attached                           | **NO — reaches origin**   |

```bash
git push mirror main      # CORRECT
git push all main         # WRONG — also pushes to origin
git push                  # works today (main tracks mirror/main) but is
                          # fragile: it silently follows whatever the branch
                          # tracks. Name the remote.
```

WARNING: the `all` remote still has **both** URLs attached, so `git push all`
reaches Rudolf. It was deliberately left configured rather than rewritten, so
that lifting the hold is a decision rather than a discovery. Do not use it.

Verify the push landed:

```bash
git rev-parse HEAD
git ls-remote --heads mirror main | cut -f1     # must match
```

Gate `G24` asserts mirror parity and merely *reports* origin's position, for
exactly this reason — see the comment above it in `scripts/verify_phase2.sh`.
When the owner lifts the hold, re-widen G24 and revert this section together.

> `mirror` is **public**. Do not commit credentials, `geofences.json`, or any
> new operational data. The existing `fixtures/` already contain real
> contractor names and tonnages.

## Where the code lives

| Area | File |
|---|---|
| Plan tab (contractor, DT↔WMT swap, estimate panel) | `static/js/plan.js` |
| Combined-analysis statistics | `static/js/regression.js` |
| Charts / 3D scatter | `static/js/charts.js` |
| Road flow simulator | `static/js/flow_sim.js` |
| Constraint matrix editor | `static/js/matrix.js` |
| API fetches | `static/js/api.js` |
| Shared globals + start-up (**loads last**) | `static/js/main.js` |
| Page markup | `templates/simulator.html` |
| Styles | `static/css/style.css` |
| Model endpoints | `simulator_api.py` |

Do **not** put Plan code back into `regression.js`.

`main.js` declares the shared top-level variables and runs start-up, so it must
stay last in the `<script>` order in `templates/simulator.html`.

## Before claiming done

```bash
.venv/bin/python serve.py                 # port 5055, sample-fixtures mode
for f in static/js/*.js; do node --check "$f" || echo "FAIL $f"; done
grep -hoE "^(let|const|var|function) [A-Za-z_$][A-Za-z0-9_$]*" static/js/*.js | sort | uniq -d
```

Also run the two gates:

```bash
.venv/bin/python scripts/check_vocab.py --api   # route-name convergence
bash scripts/verify_phase2.sh                   # must stay all-pass (42/42 here; see note below)
```

`check_vocab.py` exits non-zero if any route name reaching the UI is not the
name the model trained on. That mismatch is silent and expensive: the Plan tab
would show a tonnage for a different physical haul than the one selected.
`canonical_area()` in `prediction_pipeline.py` is the single source of truth —
`simulator_api.py` and `serve.py` import it. Do not add a second normaliser.
(The one exception is the SQL `CASE` in the shift-context query, which runs
server-side for a `GROUP BY`; its labels must be kept in step by hand.)

## The public site is deployed from a DIFFERENT machine

`https://wbn-fms-simulator.ngrok-free.app` is served from Rudolf's Mac at
`/Users/rdinkelmann/simulator-standalone`, not from this checkout. Pushing to
`origin` does **not** deploy. Until someone runs the pull + `launchctl
kickstart` there (see README "Git deployment"), the public site keeps serving
the older build — verify with:

```bash
curl https://wbn-fms-simulator.ngrok-free.app/api/model-info   # 404 == stale
```

A 404 there means the deployed copy predates the Phase 2 prediction API.

## Phase 3 — what the honest validation found

Run `python train_model.py` (Phase 3 runs by default; `--no-phase3` skips it).
Artifacts land in `data/`: `model_ols.pkl`, `validation_results.json`,
`model_comparison.json`, `feature_significance.json`, `residual_diagnostics.json`.
All are gitignored — they are derived from real production tonnages.

**Under rolling-origin (walk-forward) CV, no fitted model beats the lookup:**

| Model | mean CV R² |
|---|---|
| group-mean baseline | **0.459** |
| OLS (39 features) | 0.238 |
| RandomForest | 0.238 |

The single chronological split reports OLS 0.560 / RF 0.585, which is
optimistic: it scores one 325-row block. OLS loses to the baseline on **all
five folds**. With ~6 months of data and a level shift between months, a
per-route average generalises better than anything that extrapolates a trend.

Three data facts that constrain any future modelling here:

- **Rain gauges died 2026-04-06.** Everything after reads 0.0 mm — an outage,
  not a drought. The pipeline imputes a seasonal mean and sets
  `rainfall_missing`. Folds with `test_rain_all_zero: true` cannot validate any
  rainfall coefficient; `validation_results.json` records this per fold.
- **`is_wet_season` is unusable**: corr −0.89 with `rainfall_missing`, because
  the wet season is almost exactly the window in which the gauges worked.
- **`distance_km` is redundant**: it is a deterministic function of the route
  (0 of 45 path-pairs have more than one distance). Dropping it costs 0.0000 R².

Residuals are **heteroscedastic** (corr |resid| vs fitted = 0.48) with no
single non-linear feature flagged. That is the evidence for Phase 4: the error
grows with the prediction, so a constant-variance linear model is the wrong
shape — but more data matters more than a fancier model here.

### Target leakage — never add these as features

Verified against the data, not assumed:

```
wmt_per_shift == target * payload_t * trucks_dt    (max abs error 0.000000)
trips / trucks_dt == target                        (max abs error < 1e-8)
```

Both are exact restatements of the target and would drive R² to ~1.0 while
being unknown at planning time. `cycle_time_min` is excluded too: it is derived
from weighbridge timestamps *after* the shift ran. `verify_phase2.sh` H32 fails
hard if any of them reaches the feature list.

### Track B — features the roadmap wants that the data cannot yet support

Do **not** fabricate these. Each needs a new data source:

| Feature | Blocker |
|---|---|
| Road grade | No survey/DEM per path. Needs a road-geometry table or elevation raster. |
| Operator experience | No operator ID on haul records. Needs FMS operator assignment + hire date or logged hours. |
| Truck type / capacity | `trucks_dt` is a count, not a spec. Check `WBN_DATABASE` for a truck master with model/payload class and join it. |
| Cycle-time components | Only aggregate `cycle_time_min` is derivable, and only post-hoc. Loading/hauling/dumping/returning need geofence entry-exit timestamps. |
| Weather beyond rain | No temperature/humidity/visibility. Could come from an external API keyed on date, low priority while gauges are down. |

The last command must print nothing: a duplicate top-level declaration across
files breaks the whole page.

Then load `http://127.0.0.1:5055/simulator`, check all three tabs render, and
confirm the console is clean. Flask runs with `use_reloader=False`, so
**restart the server after editing `templates/simulator.html`** or you will be
testing a cached template.

When changing Plan UI, confirm the calculation is unchanged:
`TF>POS 12` / RIM / 60 DT → 1.837 Trips/DT, 48.6 t/trip, 5,355 t, and the
WMT→DT round-trip returns 60.

## Sample-fixtures mode must keep working

No DB credentials are committed. With no `FMS_DB_*` env vars set, every
endpoint falls back to `fixtures/*.json` via the `_register()` wrapper in
`simulator_api.py`. Never break that path.

### There is a THIRD mode, and it does not fall back — found 2026-07-31

`_register()` serves the fixture when `_db_ready()` is false **or the real logic
throws**. But an endpoint that catches its own exception and returns an error
*payload* satisfies neither condition, because a `200` looks like success. So:

| State | Behaviour |
|---|---|
| No `FMS_DB_*` at all | fixture served ✔ |
| DB configured **and reachable** | live data ✔ |
| DB configured, **connection fails** | `{"ok": false, "error": ...}` + HTTP 200, **fixture NOT served** |

The third row is the *normal* state here — the VPN drops every few minutes.
`api_simulator_congestion_model` does exactly this, so section 3 of the
assessment view renders empty (correctly explaining itself) whenever the link
blips, while a complete 94-segment fixture sits unused.

This was **not** changed, deliberately: returning an explicit error may be more
honest than serving two-week-old segment speeds as if they were live, and that is
a product decision. But know the mode exists before concluding an endpoint is
broken, and check any endpoint you add for the same shape. Gate `J56` asserts the
correct behaviour for whichever data is actually present rather than assuming the
feed is up.

## Weather now comes from an API, not the site gauges

`scripts/fetch_weather.py` pulls daily rainfall, temperature, humidity and wind
for the site (-0.7297, 127.9056) from Open-Meteo's ERA5 archive and caches it to
`data/weather_cache.csv` (gitignored, regenerable):

```bash
python scripts/fetch_weather.py --start 2025-01-01 --end 2026-07-31
```

No API key, so there is nothing to leak into the public mirror. 573 days cached
with zero gaps. It matters most where the site gauges failed: across the outage
from **2026-04-06** the API reports 112 days including **16 wet days (>=10 mm)**,
where Phase 3 had a hard-coded seasonal constant. Two consequences:

- rainfall becomes a measured feature instead of an imputed one, and
- `is_wet_season` stops being unusable. Its -0.89 correlation with
  `rainfall_missing` existed only because the gauge outage happened to line up
  with the dry season. With API weather there is no `rainfall_missing`.

## Phase 3.5 — the cycle-time model (BUILT)

Predicts `avg_cycle_time_min`: how long one truck takes to load, haul, dump and
return. Tonnage then follows by arithmetic instead of a second fit:

    tonnage = trucks x payload x (shift_minutes x utilisation / cycle_time)

Full numbers live in `MODEL_FINDINGS.md` (committed). Rebuild with:

```bash
python cycle_pipeline.py     # extract from WAITING_TIME  (needs VPN, ~5 min)
python cycle_model.py        # fit, validate, write data/cycle_model.pkl
python scripts/publish_findings.py
```

`cycle_pipeline.py` needs the database and has no fixture path, by design: a
fixture cycle time would be a made-up number that looks real. Without the VPN
the serving layer keeps using the last-trained `data/cycle_model.pkl`, and if
that is missing too, `/api/predict` returns `cycle: null` and the UI hides the
row rather than showing a placeholder.

**The target does not come from geofences, and should not.** The obvious route
(`load + haul + dump` from paired `loading`/`dumping` events) fails on volume:
`loading` is the sparsest event type in `FMS_GEOFENCE_VISITS` at ~600 rows from
22 distinct trucks starting 2026-06-25, i.e. ~500 trips over a month from 22 of
~1,800 trucks. `WAITING_TIME` carries the same information at scale (663k rows
since 2025-12, 396k passing physical bounds, 10,058 path-shift rows over 8
months) because its LOADING/DUMPING columns are clock times that can be
differenced. Re-check the geofence counts before assuming this is still true;
if that table fills in, it is the better source.

**Cycle time is not tonnage.** Converting one to the other needs a utilisation
factor, and it is *fitted*, not chosen: `calibrate_utilisation()` solves
`utilisation = observed_trips x cycle_minutes / shift_minutes` on routes present
in both datasets, weighted by ticket count. It came out at **0.40**, not the
0.85 a planning convention would suggest. That mistake was live long enough to
make `/api/predict` report 5,046 t and 10,667 t for the same 101-truck fleet.
Gate `I40` keeps it honest. If you change the shift model, re-fit rather than
re-guess.

**The two models still disagree on some routes**, by design of the honesty
rather than by neglect: cycle time comes from FMS haul telemetry, tonnage from
weighbridge tickets. `/api/predict` returns `vs_weighbridge_pct` and
`models_agree`, and the Plan panel warns above 25%. A route with a large gap is
telling you its telemetry and its tickets disagree, which is worth
investigating before either number is trusted.

**Read the result correctly.** R2 lift over the per-route lookup is 0.0085
against a pre-registered bar of 0.05, so `beats_baseline` is **false** and is
reported that way in the API, the report and the UI. MAE is 8.3 min (22%)
better, winning 5/5 folds. Both are true: R2 squares the residual so it is
dominated by breakdown shifts, while MAE weights every shift equally. The model
is closer at p50/p75/p90 and worse at p99. Quote both or neither.

**Two pre-registered signs were wrong and were corrected in place**, with the
reasoning kept in `cycle_model.py`: night shifts are *faster* (109.5 vs 141.7
min), and mean driver tenure is a weak proxy whose real effect lives in
`pct_experienced_drivers`. Do not silently delete an expectation that fails;
investigate it, then either correct it with evidence or record it as a
violation.

**Collinearity traps already found here** (both were VIF > 1e12 singularities):
`distance_km` is a pure function of route, and `payload_t` is a pure function of
contractor. Both are detected at runtime rather than hardcoded, so a future
mixed-fleet contractor keeps its feature. If you add a feature that is
determined by an existing categorical, expect the same and check `max_vif`.

**Congestion and GPS are still too recent to join.** `FMS_CONGESTION_SEG` and
`FMS_GPS_Historical` start 2026-07-15, so against a Dec-2025 window they are
null for ~95% of rows. Left out rather than mass-imputed.

**Gates** `I34`-`I39` in `scripts/verify_phase2.sh` cover dataset size, cycle
leakage, interpretable VIF, sign violations, served-vs-fitted parameter scale,
and a serving smoke test. Each was mutation-tested (corrupt the report to inject
`haul_min`, VIF 42, a negative rain coefficient, 100 rows, a raw-minutes
intercept, and exactly `I34`-`I39` fail). If you add a gate, break it
deliberately once and confirm it fails, or it is decoration.

`tests/test_cycle.py` covers the maths BETWEEN the model and the user, which is
where this phase's real bugs lived: both the scale mismatch and the guessed
utilisation were arithmetic errors invisible to every model metric. It runs
without a trained model (prediction tests skip, arithmetic tests do not) and is
gated by `I41`. Notably it asserts the reverse/forward round trip, since sizing
a fleet for a target and then computing that fleet's output are the two
directions the planner offers and they must not disagree.

One trap when doing that: the harness calls `/api/retrain`, which now rebuilds
the cycle artifacts mid-run and will overwrite whatever you corrupted, giving a
false PASS. Test a Phase 3.5 gate by running its snippet directly against a
corrupted `data/cycle_model_report.json`, not through the full script.

**Denominator moves with what you have trained**, so read the score with that
in mind. Measured, not assumed:

| State | Score |
|---|---|
| Fresh clone, nothing trained | 24/33 — the A/B checks need `data/` artifacts |
| After `python train_model.py`, no VPN | 32/33 (33/33 with remotes configured) |
| Full: cycle model trained too | 42/42 |

`data/` is gitignored (real tonnages, public mirror), so a clone starts with no
artifacts and the extraction checks fail until you train once. That is the
harness working, not a regression. The Phase 3.5 block skips entirely when
`data/cycle_model_report.json` is absent.

---

## Pre-Phase 4 — trip grain was tested and did NOT pay

`trip_extraction.py` -> `trip_diagnostic.py`. Read this before proposing to
model individual trips again.

**The hypothesis was good.** Cycle-time variance at trip grain splits 25.4%
between (route, shift, date) groups and 74.6% within them. Path-shift averaging
throws the 74.6% away, so Phase 3's model was structurally capped near R2 0.25
whatever features it had. Extracting 483,425 trips (117x Phase 3's 4,141) was
the right way to test it.

**The result was negative and should not be re-litigated without new features.**

| Model | CV R2 | MAE (min) |
|---|---|---|
| `ols_raw` | 0.1378 | 66.4 |
| `route_shift_baseline` | 0.1256 | 66.0 |
| `hist_gradient_boosting` | 0.1016 | 60.5 |
| `oracle_group_mean` | **0.2575** | 60.4 |

The oracle knows each test group's true mean, so it is the best any model could
do with this grouping. The best fitted model reaches **53.5%** of it. Two trucks
on the same route, same shift, same day differ for reasons no available column
explains: queueing, operator behaviour, individual breakdowns.

**What would change the answer:** per-trip queue time, loader assignment,
operator identity, or live congestion. More rows of the same columns will not.

**Benchmark carefully.** Score against the per-fold oracle, not a global
variance decomposition. Per-fold oracles range 0.172 (May) to 0.428 (July)
against a global 0.2543, so the global number compares different populations. I
made that mistake first; the oracle is now a model in the comparison.

**Features dropped, not imputed:** `truck_age` at 14.6% coverage (EQUIPMENTS
matches 1,537 of 3,236 trip-grain trucks) and `road_grade` at 0%.

**`dem_grade.py` does not ship a grade, on purpose.** Real survey data exists
(`FMS_GEOFENCES`, 3,490 rows with CENTER_LAT/LNG) but only 3 of 26 model nodes
match by name and `ELEVATIONS` is 100% NULL, so there is no height to
difference. GPS does not rescue it: `FMS_PLAYBACK_TRACK_DATA` covers 217 trucks
against 2,650 in tickets and its `plateNumber` ("SS074") does not join to ticket
`TRUCK_ID` ("N962"). The module reports its own coverage and enables itself once
>= 60% of nodes have coordinates. Do not hardcode lat/lons to make it run.

**Schema reality** for anyone writing new SQL here: the ticket table is
`HAULAGE_IWIP_CLEAN` with `ORIGIN_AREA` / `DESTINATION_AREA` / `TICKET_NO`;
there is no `SOURCE`, `DESTINATION`, `CORRIDOR_KM`, `ID` or `DRIVER_ID` column,
no `DRIVERS` table in `WBN_DATABASE`, and `EQUIPMENTS` keys on `ID_EQ`.

---

## Plan Assessment View (BUILT 2026-07-31) — sections 2-8

`static/js/plan_assessment.js` + the `pa-sections-top` / `pa-sections-bot`
blocks in `templates/simulator.html`. Charts are **ECharts from a CDN**; there is
no npm dependency and no build step, because the deployed copy is a git pull on
someone else's Mac.

It renders from the **same `/api/simulate` response** the results table uses, so
a chart can never disagree with the table above it. Reference data
(`/api/simulate/options`, `/api/simulator/congestion-model`,
`/api/simulator/capability`) is fetched once and cached per session.

**Three things the brief asked for that the data cannot support.** Each is
labelled in the UI, not just here. Do not "fix" them by inventing the number:

| Asked for | Why not | Drawn instead |
|---|---|---|
| "travel empty" as its own band | weigh-to-weigh spans load→haul→dump; the empty return sits in the gap up to the effective cycle **together with** queue, refuelling, breaks and downtime (277 of 355 min on BLB>FENI KM0). Nothing separates them. | one residual band named for everything it contains |
| loaded vs empty speed per section | `FMS_CONGESTION_SEG` has a `DIR` column but `/api/simulator/congestion-model` aggregates over it — the payload has no direction field | measured mean speed vs data-anchored free-flow (p85 at low traffic), both real. Splitting by `DIR` is a server change and is the obvious follow-up. |
| per-contractor fleet sizing | roster is computed per **route**; there is no contractor dimension on it, and availability is measured for trucks carrying only 30.3% of tonnage | per-route rows with each row's `measured` / `fleet_prior` basis |

`/api/simulator/capacity` **does not exist** — the brief cited it for the queue
gauges. Capacity comes from `/api/simulate/options`
(`capacity_trips_shift`, `observed_hours`) against `total_trips` from
`/api/simulate`. No new endpoint was needed.

`/api/simulator/congestion-model` now also returns **`densityFit`**, read from
the committed `reports/speed_density_fit.json` by `_density_fit()`, so the
congestion caption cites the real coefficients instead of a hardcoded copy that
goes stale. It is served on the error path too, and mirrored into
`fixtures/congestion-model.json`; keep the two in step.

**ECharts may be absent.** This tool is demoed without VPN and sometimes without
internet. Every chart goes through `paChart()`, which degrades to a visible note;
the tables carry the numbers and are plain DOM. Do not add a chart that bypasses
`paChart()`.

**The trap that cost the most here:** `paGauges()` rebuilds its container with
`innerHTML`, which **detaches** the previous chart divs. A detached ECharts
instance is *not* disposed, so `isDisposed()` stays `false` and the cached
instance happily renders into orphaned DOM. Every gauge shipped blank from the
second render onward (2 canvases → 1 → 0) while a check counting wrapper `<div>`s
passed. `paChart()` now also verifies `getDom() === el && getDom().isConnected`.
**Count drawn canvases, not elements.**

## The availability override — the UI defeated the engine

Full write-up: `reports/CRITICAL_availability_override_defect.md`. Gate `J55`.

`plan_simulator.js` sent `availability: 0.85` on every request and
`plan_simulator.py` honoured it, so the shipped UI quoted **2,586 t** where the
measured basis gives **3,042 t** (30 trucks, BLB>FENI KM0) — reintroducing
through the front door the exact assumption this project removed from the
engine, and moving delivered bias from +5.5% to −10.3%.

**`J52` passed the whole time**, because it builds its own payload with no
`availability` key and so only ever exercised the default path. Reintroduce the
defect and `J55` fails naming the tonnages while `J52` still passes — that pair
is the demonstration, and the general rule it teaches is:

> A gate that constructs its own input cannot catch a bug in what the real
> caller sends.

The engine now accepts and ignores the key, echoing
`summary.availability_override_ignored`. Do not re-add the parameter, the UI
control, or the multiplier.

## Score

**56/56**, measured 2026-07-31 in both no-DB and DB modes, with `J55` and `J56`
added. `G24` was narrowed to gate the **mirror only** — see the top of this file
and the comment above it in `scripts/verify_phase2.sh`.

