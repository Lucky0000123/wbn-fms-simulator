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
`origin` does **not** deploy — and `origin` is on hold, so see `DEPLOY.md`
before assuming a pull will help.

**The old staleness check is itself stale.** This file used to say
`/api/model-info` returning 404 meant a stale deployment. Measured 2026-07-31 it
returns **200**, and the site is still four rounds behind. Use markers from the
work that actually landed since:

```bash
S=https://wbn-fms-simulator.ngrok-free.app
curl -s $S/health                                            # 200 + dataMode
curl -o /dev/null -w '%{http_code}\n' $S/api/simulator/corridor-geometry   # 404 == stale
curl -s $S/simulator | grep -c pa-sections-top                             # 0 == stale
```

Or just `scripts/deploy.sh --check`, which asserts exactly that. A deployment can
be **up, healthy and months out of date**; `/health` cannot tell you, and any
single-endpoint marker rots the moment that endpoint ships.

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

### There are THREE modes, not two — the third was broken, and is now FIXED

`_register()` serves the fixture when `_db_ready()` is false **or the real logic
throws**. An endpoint that catches its own exception and returns an error
*payload* satisfies neither condition, because a `200` looks like success:

| State | Before 2026-07-31 | Now |
|---|---|---|
| No `FMS_DB_*` at all | fixture ✔ | fixture, tagged ✔ |
| DB configured **and reachable** | live ✔ | live ✔ |
| DB configured, **unreachable** | `{"ok": false}` + 200, **no fixture** ✘ | fixture, tagged ✔ |

The third row is the *normal* state here — the VPN drops every few minutes — and
**five endpoints** had it: `congestion-model`, `path-response`, `weighbridge`,
`weighbridge-summary`, `shift-context`. Section 3 of the assessment view rendered
empty whenever the link blipped, while a complete 94-segment fixture sat unused.

**The rule: never catch a DB exception in endpoint logic.** Let it propagate;
`_register` is the fallback and it is the only thing that knows about fixtures.
The four sites that did now `raise`. The one exception is
`api_weighbridge_summary`, which prefers its own **stale cache** (real data from
minutes ago, self-flagged with `stale`) and only re-raises when there is no cache.

Fixture responses are now tagged `servedFrom: "fixture"` plus
`servedFromReason`, so a UI can label cached figures instead of passing them off
as live. Section 3 renders "Cached segment speeds… the site link or database is
down", with the raw driver error on hover. Gate `J58` drives the real app against
an unroutable host and asserts both the behaviour and — structurally — that no
`ok:False … unavailable` return has re-grown anywhere.

WARNING for anyone writing a browser check: in this mode start-up fetches stall
for seconds, so the route dropdown lands at ~4.5 s instead of under 1 s. A fixed
`wait_for_timeout(1200)` failed all 17 assertions and looked like a total page
failure when nothing was wrong. Wait on the **condition**, not the clock.

## Weather now comes from an API, not the site gauges

`scripts/fetch_weather.py` pulls daily rainfall, temperature, humidity and wind
for the site from Open-Meteo's ERA5 archive and caches it to
`data/weather_cache.csv` (gitignored, regenerable):

```bash
python scripts/fetch_weather.py --start 2025-01-01 --end 2026-08-06
```

**The site coordinates were wrong twice, differently (fixed 2026-08-07).**
This file used to quote (-0.7297, 127.9056) — the WRONG HEMISPHERE, ~140 km
south of the haul road — while `simulator_api.py`'s rain-suggest used a third
value (0.78, 127.92). The authority is the committed road survey
`data/haul_road_chainage_public.csv`: lat 0.476..0.807, lng 127.898..128.038.
Both code sites now use its median **(0.5586 N, 127.9647 E)** and the forecast
bins days in **Asia/Jayapura (WIT, UTC+9)**, not Asia/Jakarta. If you touch a
coordinate here, derive it from the survey, do not copy a number from a doc.
The cache was rebuilt at the correct point: 583 days, 144 wet days (>=10 mm).
Old percentages below predate the rebuild but the qualitative findings held.

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

## The weather input — audited, and my own flag was wrong

Full write-up: `reports/weather_input_analysis.md`. Gate `J57`.

The previous handover flagged weather as the next availability-style defect: "a
wet cycle uplift reduces trips and therefore tonnes". **That was wrong.**
Measured across 14 routes, tonnage is byte-identical dry vs wet, because rain is
deliberately excluded from the effective cycle and the effective cycle is the
only denominator for trips. There is no weather→tonnage path and there never was.
The measured record supports keeping it that way: raw wet-vs-dry trips/DT is a
median **+4.8%** across 15 paired routes, reducing on only 5 of 15.

**A different defect was real.** `implied_travel_time_min` is the residual
`cycle − load − dump`. The cycle uplift carried only the **loading** point's wet
penalty while `predicted_dump_time_min` also carried the **dumping** point's, so
the dump penalty was subtracted from travel and never added back:

> the model reported trucks travelling **faster in the rain** on 11 of 14 routes,
> by up to **7.8 minutes** (KR>POS 10). The signature was exact: `dTravel == −dDump`.

The cycle now carries both, derived from the dwell deltas *actually applied*
(not re-read from `wet_penalty_min`, which misses `_point_dwell`'s own fallback
path). **Implied travel is now weather-invariant**, which is the honest position:
the wet/dry split is measured AT POINTS, and nothing here measures a rain effect
on road speed.

`J57` asserts invariance **and** that weather still moves dwell — because an
invariance-only gate is passed perfectly by deleting the feature.

## Beware: a residual field hides errors

Twice now the bug has been in a field computed as a remainder.
`implied_travel_time_min` absorbed a one-ended dwell penalty silently and
reported a physically impossible result. A residual never fails loudly; it just
quietly takes up the slack for whatever is inconsistent elsewhere. When you
change any term of `cycle − load − dump`, check the residual.

## `shift_minutes` — audited, no bug, but a silent extrapolation

`reports/shift_minutes_audit.md`. Gate `J60`. The UI sends 720 and
`DEFAULT_SHIFT_MIN` is 720, so there is **no** disagreement of the availability
kind. But `effective_cycle_min = (truck_shifts × 720) / trips` — 720 is hardcoded
in the derivation — so the denominator is calibrated at a twelve-hour shift while
trips scale linearly with whatever the caller sends. The model over-states trips
below 720 and under-states above.

The size of that error is **unknowable here**: 98.48% of 538,586 truck-shifts are
exactly 12.0 h, so there is no variation from which to separate per-shift
overhead from per-trip time. So the field is kept and the answer is labelled
(`summary.shift_minutes_extrapolated`), silent at 720 — a warning that always
fires is one nobody reads.

## Segment speeds ARE splittable by direction

`FMS_CONGESTION_SEG.DIR` is `{'down','up'}` and the endpoint used to aggregate
over it. It now returns `loadedSpeed` / `emptySpeed` / `nLoaded` / `nEmpty`.

**The mapping was verified, not assumed.** "down" is a *chainage* direction, not a
load state. Against the tickets: **100.0% of loaded corridor hauls run
down-chainage** (298,340 trips, zero counter-examples), because every tip sits
seaward of every load point. The speeds agree independently — empty is faster on
**75 of 94** segments, median **+11.5%**, up to **+101%** on the steep TF
sections. Gate `J61`; its majority-and-sign check is what would catch a silent
inversion, which would look entirely normal on screen.

## HRM has no measurable effect — and the first answer was spurious

`reports/hrm_impact_analysis.md`. Gate `J62`. Within route and fleet size,
HRM activity vs trips/DT is **r = ±0.0006, p = 0.99** on 389 route-shift-days.
Do not add HRM to the model.

The first pass reported **r = −0.4604, p = 8.4e−22**. It was route length:
`hrm_hours` is summed along a route, so `corr(span_km, hrm_hours) = +0.63`, while
`corr(span_km, trips_per_dt) = −0.63`. Two correlations through a shared cause
manufacture ≈ −0.40. Controlling fleet size did nothing because fleet size was
not the confound — the road was.

> **A dose measure that accumulates along a route encodes route length.** Difference
> it away (demean within route) before believing it. `hrm_units`, a count rather
> than a sum, was not confounded and showed nothing at any stage.

## Two traps this codebase has now hit twice each

**Residual fields hide errors.** `implied_travel_time_min` absorbed a one-ended
dwell penalty and reported rain speeding trucks up. When you change any term of
`cycle − load − dump`, check the residual.

**Counting elements is not checking rendering.** Gauges: 3 wrappers, 0 canvases.
The map: 376 `<path>` elements with correct geometry and stroke, drawn into a
**zero-width** SVG overlay — invisible. Leaflet sizes the SVG renderer from the
container at init, and this map lives in a tab that starts hidden;
`invalidateSize` moves the map but does not rescue a stale SVG viewport. Fixed
with `preferCanvas: true`. Assert the renderer surface covers the container, not
that shapes exist.

WARNING: `use_reloader=False`, so **restart the server after editing
`templates/simulator.html`** — twice this round a template change appeared to be
a code bug because the browser was served the cached old template.

## Dev tooling — configured, NOT applied

`requirements-dev.txt` + `pyproject.toml`. black, ruff, isort, mypy, pytest.

**Nothing is applied to existing code and that is deliberate.** black would
reformat 60 files and ruff reports 133 findings; a whitespace commit touching
every file makes `git log -p` and `git blame` useless for the questions actually
asked here ("when did this coefficient change, and against what evidence?"). Use
them on code you are already modifying.

Two settings are load-bearing:

- **`testpaths = ["tests"]`.** The root `test_*.py` files are standalone gate
  SCRIPTS with module-level code that connects to the DB and rewrites artifacts.
  A bare `pytest` would import and **execute** all of them. Do not remove this.
- **ruff's `select`/`ignore` live under `[tool.ruff.lint]`.** At the top level
  they still work but warn on every run, which trains people to ignore ruff.

Of the 133 findings, two were acted on because they were misleading rather than
merely untidy — a dead `cycle_dry` whose comment described behaviour the weather
fix had made forbidden, and four `except Exception as exc:` that never used
`exc`. The rest are house style (E702/E731 in analysis scripts, E402 where
`sys.path` must be set before project imports) and are **not** a backlog.

## ONE shift-length control

There were **three**. `#ps-shift` (minutes) drove the engine; `#plan-hours`
(hours) drove `plan.js`'s local estimate on another tab; `#flow-hours` sat
`disabled` and unread in a collapsed panel on a third. Two controls for one
concept is how the 0.85 availability override survived.

Now: `#ps-shift` is the only editable one. `#plan-hours` is a **hidden** field
written by `psSyncShift()` so the two cannot diverge (plan.js is unchanged and
still reads `.value`). `#flow-hours` is deleted. `J60` counts editable
shift/hours inputs and fails at two.

Range narrowed **60–1440 → 480–720**. Measured on 538,586 truck-shifts: 98.5%
are exactly 12.0 h, the shortest observed is 8.0 h, nothing is below 6 h, and the
1.3% above 12 h is almost entirely `24.00` — a day-aggregated record, not a
24-hour shift. It is guidance, not a block: a typed value outside the range still
runs and the engine labels it as an extrapolation.

## The road centreline IS committed — a one-file exception

`data/haul_road_chainage_public.csv`, un-ignored explicitly. Four columns —
`road, km, lat, lng` — and nothing else. The corridor is already rendered by
OpenStreetMap, so withholding it bought no secrecy and cost the section-9 map on
every fresh clone and on the public demo.

**Geofences, loading and dumping zones, security boundaries, tonnages,
contractors and equipment stay out.** `weighbridge-positions` still encodes
`km`/`offM` rather than coordinates.

`/api/simulator/corridor-geometry` prefers the full gitignored extract and falls
back to the committed copy, reporting which in `geometrySource`. `J63` pins the
schema — the load-bearing assertion, because a re-export that quietly added a
`zone` column would leak zone data through a path that already has permission
and nothing else would notice. Mutation-tested: adding a `zone` column fails it;
so does un-ignoring `data/*.csv`, which would have exposed 22 files including
`trip_features.csv`.

## 3D view (section 9) — CesiumJS, lazy, token-free

`paMapView('3d')` in `plan_assessment.js`. Toggle defaults to **2D** and Cesium
is **not fetched until 3D is clicked**: it is ~4 MB and this tool is demonstrated
on site connections.

**No ion token is used or needed.** OpenStreetMap imagery plus
`EllipsoidTerrainProvider` are both token-free, and a token could not be
committed to a public mirror anyway.

**Ribbon height encodes SPEED, not elevation, and the UI says so.** `ELEVATIONS`
is 100% NULL in this database, so there is no terrain to show; an unlabelled
height axis on a 3D globe would be read as ground. Slower sections stand taller,
because the planner is hunting the slow ones.

WARNING: `imageryProvider:` as a `Cesium.Viewer` constructor option was removed
around **1.107** and is **silently ignored** in 1.114 — no error, no warning,
just a viewer with `imageryLayers.length === 0` and a blue globe. Pass
`baseLayer: new Cesium.ImageryLayer(provider)` instead. `J56` asserts
`imageryLayers > 0` for exactly this reason; a check that only counted entities
passed while the basemap was missing.

## Deploying

`DEPLOY.md` + `scripts/deploy.sh` (`--check`, `--stop`, `--reserved`).

**The documented pull would downgrade the deployment.** README says
`git pull origin main` on Rudolf's Mac, but `origin` is frozen at `48985b4` and
every commit since lives only on the mirror. Measured 2026-07-31, the public site
is up, healthy, serving fixtures — and predates the entire Plan Assessment View
(`corridor-geometry` 404s, no `pa-sections-top`). Fixing it needs an owner
decision: lift the hold, or repoint the deployed checkout at the mirror.

`deploy.sh --check` verifies four things, and the fourth is the one that matters:
that the deployed build actually **contains** `pa-sections-top`. A site can be up,
healthy and four rounds stale, and `/health` cannot tell you.

The reserved ngrok domain is opt-in (`--reserved` + `NGROK_DOMAIN`) because
claiming it from another machine takes the public endpoint over.

## Score

**70/70**, measured 2026-08-07 in database mode after the Plan-page audit
(J64–J70 added since the 63/63 measurement of 2026-07-31). `G24` gates the
**mirror only** — see the top of this file and the comment above it in
`scripts/verify_phase2.sh`.

### 2026-08-07 audit — seven defects found and fixed, and what they teach

- **Two "site" coordinates coexisted, both wrong** (fetch_weather.py southern
  hemisphere; rain-suggest a third value). Nothing failed loudly because
  Open-Meteo happily returns weather for any point. See the Weather section:
  derive coordinates from the road survey, never copy them from prose.
- **HOUR_TS is true epoch ms, not local wall clock.** Corridor hour labels ran
  9 h off site time; "slow hours 19:00–20:00" were really 04:00–05:00. The
  corroboration to look for: truck-count dips align with the 07:00/19:00 shift
  changes only under UTC+9. `plan_corridor_hours.SITE_TZ` is the conversion.
- **A cache key must include every input that changes the answer.** The
  analogue DB cache hashed {plans, rain, k} but not `rank`/`prefer_peak`, so
  match-mode results were served for best-output requests. The response
  fingerprint knew better — the two had drifted apart.
- **The ONE-shift-control rule was broken again**, this time by
  `planLoadSavedForDate` writing the hidden mirror (#plan-hours) directly.
  Write the source (#ps-shift) and call `psSyncShift()`; never write the mirror.
- **Plan Step 2 and Capability share flow globals.** Seeding the plan
  illustration clobbered Capability's replay until `flowSetHost` learned to
  snapshot/restore. If you add shared state to flow_sim.js, ask which host owns
  it and what happens on tab return.
- **`use_reloader=False` claimed another round**: the running server predated
  the day's `simulator_api.py` edits, so plan.js read `trP25` fields the live
  API did not serve — silently absent behind a `Number.isFinite` guard.
  Restart the server after backend edits, then verify the field is in the
  actual HTTP response, not just the source.
- **`git add -A` was one command away from publishing the ops-DB schema and
  fuel extracts.** New scan reports and fuel_recon CSVs were untracked but not
  ignored; the CSVs were even committed locally. Both are now gitignored, the
  CSVs were rewritten out of unpushed history before the mirror push
  (original preserved on local branch `backup-pre-csv-rewrite`), and J63 pins
  the allowed-CSV list. When you create a report from DB introspection,
  gitignore it in the same change.

`data/simulator_model_results.json` no longer churns: `simulator_model.
preserve_stamp()` carries `generated_at` forward when nothing else changed, so
`git status` is clean after a harness run and stays a usable signal. Gate `J59`.

## Learned User Preferences

- Default DT motion to Measured GPS; hide manual Loaded/Empty km/h until the user explicitly chooses an override, and show a clear highlight that GPS logic is active. Plan GPS corridor particles must stage at the **loading point**, not dump/split endpoints.
- Treat Advanced Simulation Settings (start, stagger, headway, dwell, trace, and similar knobs) as illustration-only — they must not change fleet size, trips, or WMT.
- Treat trip-implied speed and manual km/h as one override mode, not two separate engines.
- Available fleet (budget) should follow the sum of route what-if DT boxes, not stay stuck on the day-dispatch total.
- Forward planning and achievable tonnes belong on Plan Step 2 / `/api/simulate`; Capability Shift Road is for historical replay and illustration, not the planning estimate.
- Keep the schematic chainage stick always visible with the map; Run should scroll both visuals into view so the user can watch what is playing.
- Best past days / analogues: filter by selected contractor; rank nearby trip count first, then trips/DT; color wet vs dry; show a loading state while searching; omit “ops only / no haul GPS” caveats from that list. When a day is selected, show that day’s figures — do not label Jan–May season averages as that day’s DT/trips.
- Keep Plan Step 1 sparse and space-efficient (date + rain in conditions, estimated output beside plan date, best-past-days under conditions in a compact scrollable grid); rainfall in conditions should move the Step 1 WMT estimate; show which model/factor produced the number.
- On Run Scenario (Step 2), lead with estimated production and capacity with a professional loading state for A/B; defer road/GPS corridor block (C) until after the corridor run; hour-of-day charts must show which hour/argument is selected; prefer decision-oriented outcomes over repeating the same tables.
- Optimize DT: per-row Accept (✕/✓) for suggested vs current DT (default keep current); fewer bulk option buttons; label the orange action “Finalize plan → refresh Production and capacity” (not “refresh B”); remove Save-plan-for-date from that optimize strip.
- Shift outcomes: one clear plan-vs-history (P25–P75) row; label the road band “Road” (not “Jul GPS”); helper text that V/C means Volume/Capacity; hide Bottleneck/Do-next road-advisory fluff; keep planned WMT vs achievable/adjusted figures consistent across A and B — never average predict + simulate + history into one total.
- Planning goal: best production with less congestion using the minimum required trucks — support edit-from-outcomes once verdicts exist.

## Learned Workspace Facts

- Simulate tonnes use **effective cycle** `(truck_shifts × 720) / trips`, not weigh-to-weigh predicted cycle (~77 min median). Confusing them overpredicts badly. Site median effective is ~389 min; consecutive start-to-start pairs ~240 min — do not conflate those two “240” stories.
- `DEFAULT_AVAILABILITY = 1.0` for tonnage (J52 + J55). Downtime is already inside effective cycle; never re-add 0.85/0.80. Measured residual **+5.5%** is exposed as companion `ticket_calibrated_achievable_t` (÷1.055, not primary) with Plan lens default ON. Do not “fix” via availability (×0.85 → −10.3%). Roster sizing may still use mechanical availability (~0.72) for fleet count only.
- Congestion / road V/C, Jul+ corridor clock (`/api/plan/corridor-hours`, `/api/plan/day-segments`, `/api/plan/gps-coverage`), congestion advice (`/api/plan/congestion-advice`), and shared-road DES-lite (`/api/plan/shared-flow`) are measured or advisory and must **never** modify simulate tonnes (J53); `basis.congestion_clips_tonnes` always false. Stick CSV refresh: `scripts/refresh_stick_from_archive.py` (also after `accumulate_gps`).
- Point capacity is a **p99 hourly throughput lookup** (not ML). Shared-loader p99 can clip achievable tonnes — that is point capacity, not a congestion term in cycle. Dwell models: wet/dry are served; day/night may be computed but unused at serve. Dual-mode `_register` wraps **7** simulator endpoints (not “all APIs”).
- Achievable tonnes / Plan Step 2 outcomes come from `/api/simulate`, never flow particles. Step 1 WMT uses path-response **main-cluster** `avgTr` (mid-60% trimmed mean of daily trips/DT, with P25–P75) × contractor `clamp(tripsPerDT/fleet, 0.5–1.5)` × rain; **simulate ignores contractor factors**. Rain may move Step 1 WMT; simulate tonnes stay weather-invariant (J57).
- Capability Shift Road is illustration/replay; particles are not production. Flow speeds default to measured GPS; posted limits are overlay only. Disk snapshots (`cap_snapshot.json` / `pr_snapshot.json`) sit between memory and fixtures.
- **DB roles:** `WBN_DATABASE` = ops truth; `FMS_DB` = location. Haul GPS (`FMS_CONGESTION_SEG` / `FMS_GPS_Historical`) from **2026-07-15** only. Playback Feb+ is HRM/support (**0%** haul plate overlap) — never for haul V·C or analogue replay; `/api/plan/playback-truth` documents that. Grow haul history with `scripts/accumulate_gps.py` (cron 07:00/19:00); `FMS_EQUIPMENTS.plateNumber` joins weighbridge.
- Capability defaults `2026-01-01` → `2026-05-31` (peak). Jul GPS V/C is struggle-season illustration only. Plan analogues (`/api/plan/analogues`) match contractor; rank trips then trips/DT. HRM impact on trips/DT is ~0 (r≈0.0006) — keep excluded.
- **Peak road proxy:** `/api/plan/peak-road-proxy` — Jan–May section DT/trips from weighbridge path-days (ops pressure). `speeds_kmh` is always null. Not Playback and must not be presented as a selected analogue day’s averages.
- Shift length calibrated at **720 min** (~98.5% of shifts); other lengths raise `shift_minutes_extrapolated` (J60). Holding plans save locally via `/api/plan/saved` → `data/saved_plans/{date}.json`.
- Hide the Capability filter header (`.top`) on Plan and Production Simulator tabs; keep the sim-tab strip so users can leave Plan.
- Never invent pre-2026-07-15 haul speeds from Playback; path-response main-cluster trips/DT will sit below a single best past day by design (trimmed mean, not the peak day).

