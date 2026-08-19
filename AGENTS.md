# AGENTS.md — working rules for this repo

> **Switching agents or new to this repo?** Read
> [reports/HANDOVER.md](reports/HANDOVER.md) first. It carries the
> project identity, DB tables, file tree, engine internals, the 54
> gates and the traps. This file is the working rules and the record
> of what was tried and failed.

Applies to every agent and contributor working in this checkout.

## Push to BOTH remotes, always

**The hold on `origin` was LIFTED by the owner on 2026-08-07** ("push
everything to git, me and Rudolf"). History: pushes were dual until
2026-07-30, mirror-only during the hold (origin froze at `48985b4`), and
dual again from `b9cb86e`. Gate `G24` asserts BOTH remotes match local HEAD.

| Remote   | URL                                          | Push?   |
|----------|----------------------------------------------|---------|
| `mirror` | `github.com/Lucky0000123/wbn-fms-simulator`  | **YES** |
| `origin` | `github.com/rdinkelmann/wbn-fms-simulator`   | **YES** |
| `all`    | both URLs attached                           | works, but prefer naming each |

```bash
git push mirror main && git push origin main    # CORRECT — both, named
git push                  # fragile: silently follows whatever the branch
                          # tracks. Name the remotes.
```

Verify the push landed on both:

```bash
git rev-parse HEAD
git ls-remote --heads mirror main | cut -f1     # must match
git ls-remote --heads origin main | cut -f1     # must match
```

> BOTH remotes are on public GitHub. Do not commit credentials,
> `geofences.json`, or any new operational data. Reports derived from DB
> introspection get gitignored in the same change that creates them (see the
> 2026-08-07 audit section). The existing `fixtures/` already contain real
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

## The capacity card — the same defect, found again in another card

Gate `J71`, `scripts/check_capacity_card.py`. Found 2026-08-12 by the owner
looking at a screenshot and saying the panel "looks fake".

`planRenderOutcomes` in `plan_scenario.js` built the A · Capacity card from
`predict.wmt` — the Step 1 **path model** — instead of the engine's
`summary.planned_production_t`. On 800 DT (TF>FENI KM0, RIM) + 560 DT
(TF>FENI KM15, PPP) the engine clipped **16,012 t** and returned two
`capacity_warnings` naming TF's demonstrated 1140 trips/shift ceiling against
1478 asked. The card displayed **"Shortfall 0 t · vs planned 120%"** and the
warnings were never rendered at all.

Two things made it invisible:

- **The denominator was the wrong model.** The path model declines sub-linearly
  with DT (measured decline, 30% floor) while the engine's planned tonnage grows
  linearly, so `achievable / path_model` *rises* as the fleet grows. The metric
  was anti-correlated with reality in exactly the regime it exists to warn about:
  the more absurd the plan, the healthier the card looked.
- **`Math.max(0, …)` on a difference.** Clamping turned "the path model came in
  below simulate" into a clean zero. A clamped difference cannot tell you it went
  negative — the same shape as the `implied_travel_time_min` residual, which is
  now the third time a hidden negative has cost a round here.

Measured, both directions:

| Total DT | engine planned | achievable | engine shortfall | card before | card now |
|---|---|---|---|---|---|
| 173 (observed max) | 8,899 | 8,899 | 0 t | 0 t · 100% | 0 t · 100% |
| 1360 | 70,065 | 54,053 | **16,012 t** | **0 t · 120%** | 16,012 t · 77% |

The fix is one rule: **a card headed "simulate" is denominated in simulate.** The
path-model comparison already had its own home in the REALISM card. `B ·
Production & capacity` keeps `predict.wmt` and is *not* the same bug — its tiles
say "Planned (path model)" and "Achievable / planned" on their face.

`J71` asserts both directions on purpose. A gate demanding only "shortfall > 0"
is passed by hardcoding one; a gate demanding only "== 0" is passed by deleting
the feature. It drives the real `planRenderOutcomes()` with a real `/api/simulate`
response **and a real `predict.wmt`**, for the J52 reason: a gate that builds its
own input cannot catch a bug in what the real caller sends.

> **When two panels quote the same concept from different models, one of them is
> going to be read as a verdict.** Give the concept one owner, or label both on
> their face. This is the third instance — the 0.85 availability override and the
> three shift-length controls were the first two.

## Sticky plan nav — Save is reachable from any scroll depth

`#plan-navbar` at the top of `#tab-plan`, `position:sticky`. Section jump links
(Plan / Run / Fleet / Road / History) with a scrollspy, the plan date and a live
`N paths · X DT` summary, and the Save/Load controls.

**The Save buttons were MOVED here, not copied.** They previously sat in the date
card, which scrolls away — by the time a plan was worth saving, the button was off
screen. The element ids (`plan-save-btn`, `plan-load-btn`, `plan-save-status`) are
unchanged so `planRefreshSaveButtons()` / `planSaveForDate()` needed no edit, and
there is still exactly ONE Save button on the page. Do not add a second one: two
controls for one concept is how the 0.85 availability override survived.

`planNavSync()` is called from `planRefreshSaveButtons()`, which already fires on
every draft change, so the summary cannot drift from the draft.

Three things that are easy to get wrong here, all asserted in the browser rather
than assumed:

- **`position:sticky` dies silently** if any ancestor has `overflow:auto/hidden/
  scroll` or a `transform`. There are none today; the check walks the ancestor
  chain and fails if one appears.
- **Jump targets need `scroll-margin-top`** (64px). Without it `block:'start'`
  parks the section heading UNDER the sticky bar and the jump looks broken.
- **At the bottom of the page the last section is the current one.** Before Run
  scenario the Step 2 sub-blocks are hidden, the page is short, and clicking
  "Run" scrolls as far as it can without Run's top ever reaching the bar — so a
  naive scrollspy highlights the wrong entry and the link reads as broken.

Sections not yet rendered (`offsetParent === null`) are skipped, so Road/History
do not highlight before Run scenario has shown them.

`planOpenSavedDate()` backs the "Saved…" picker; it sets the date and goes through
`planDateChange()` rather than poking dependants, because that is what re-pulls
conditions, analogues and the saved-plan probe.

> Testing save writes real files to `data/saved_plans/`. Use a sentinel date and
> `DELETE /api/plan/saved?date=…` afterwards — do not save over a real plan date.

### Haul GPS days moved to the page foot — and what it nearly cost

`#plan-sec-gps`, a collapsed `<details>` after the Step 2 card. It was in the
topbar above Step 1, which contradicted "keep Plan Step 1 sparse": it is
reference material and says so itself ("Does not change Step 1 WMT").

**It is deliberately NOT inside the Insights section**, which is the obvious home.
`plan-sec-insights` lives inside `#plan-scenario-panel`, which is `display:none`
until Run scenario — putting it there made a previously always-available panel
unreachable until you ran something. Caught by asserting `offsetParent !== null`
on a fresh load; nothing errored, the panel was simply gone.

> **Before moving a block, check what its new parent does to it.** A move is not
> a no-op when the destination is conditionally hidden.

The block still carries the **playback-truth disclosure** — the record that
Playback has 0% haul-plate overlap and must never be used for haul V/C or
analogue replay. Do not delete it while trimming the page.

### The bias lens was orphaned by the section-A deletion — now re-homed

Deleting A · Shift outcomes silently killed the ticket-calibrated companion.
`plan-bias-lens` still rendered and still toggled, but its only consumer was
`planBiasAdjustedAchievable()` at one call site inside the dead
`planRenderOutcomes()`. No error: the checkbox just did nothing, and the −5.5%
figure stopped being displayed anywhere while `test_plan_bias_playback_ml.py`
kept passing on the backend helper.

It now renders in **A · Production & capacity** (`#ps-kpi-ticket`), beside the raw
Achievable and never replacing it. `planBiasAdjustedAchievable(raw, summary)`
gained an optional summary so `psRender` can pass the response it is drawing —
one ÷1.055 implementation, so the panels cannot drift on what "calibrated" means.

> **Deleting a panel orphans its logic silently.** Two orphans came out of that
> one deletion. When a container goes, grep the ids it held.

## 2026-08-12 hard test — extreme-input QA, and the BPR penalty that came out

Adversarial pass over `/api/simulate` and `planTripsPerDT` with extreme inputs.
What it found, worst first.

### The BPR quadratic made output COLLAPSE — reverted

A volume-delay penalty briefly replaced the hard min in `planTripsPerDT`:

```js
const over=(nComb-nStar)/nStar;
const served=capEff/(1+0.15*over*over);   // NOT a plateau
```

Measured on TF>FENI KM0 before the revert:

| DT | frontend trips | frontend t | backend t | disagreement |
|---|---|---|---|---|
| 172 | 204.6 | 10,207 | 8,888 | 0.9× |
| 800 | 68.5 | 3,419 | 41,339 | 12× |
| 2000 | 11.5 | 572 | 53,819 | **94×** |

Trips **peaked at 172 DT and fell without bound** — 2,000 trucks producing 5% of
what 172 produce. Three reasons it had to go: it is non-monotonic (adding trucks
destroys existing output); it disagreed with `/api/simulate` by up to 94× on the
same plan, which is the two-models-one-question defect this repo has already paid
for twice; and the `0.15` quadratic is not measured, while four independent tests
here failed to find any queueing effect and the density effect is −4.8% across
the extremes.

**The half that was right is kept:** `capEff = dayTripsCap × min(1, rainScale)`.
Without it, wet beat dry at over-saturation because rain cut demand and therefore
the penalty. Mud degrades the road, so the ceiling scales with rain.

> **The ceiling is measured; the shape of any decay past it is not.** Saturate at
> the proven ceiling and stay silent about the rest. Extra trucks divide the same
> demonstrated trips — they do not destroy them.

### OPEN: the two models cap on DIFFERENT quantities (5.3× apart)

Even after the revert, at saturation the frontend plateaus at 205 trips/shift and
the backend at 1,140:

- **frontend** caps per **path** — `dayTripsCap` 410 trips/day on TF>FENI KM0
- **backend** caps per **point** — TF loading point p99, shared across its paths
  (verified: an 800+560 two-path plan counted both against one 1140 ceiling)

Both are real; the true limit is the **minimum**, so the backend is missing a
path-level cap. Note also that `dayTripsCap` is a *demonstrated maximum, not a
capacity* — no day exceeded 410 trips, but no day ever tried more than 180 trucks
either. Treating "the most we ever did" as "the most we can do" is a modelling
choice, not a measurement.

### Input validation — none

| Input | Result |
|---|---|
| `n_trucks: -5` | **−258 t** produced |
| `shift_minutes: -720` | **−5,167 t**, flagged as "likely OVER-states trips" |
| `n_trucks: NaN` / `inf` | HTTP **500**, raw Python error leaked |
| `shift_minutes: null` | HTTP **500** |
| `n_trucks: 2.7` / `True` / `"800"` | silently coerced; 2.7 trucks → 3.0 trips |
| `weather: 123` / `"monsoon"` | accepted silently |

### OPEN: no achievable-trips field exists

At 10,000 DT the engine returns `total_trips = 10,945.6` while achievable tonnage
implies **1,140 trips**. Tonnes are clipped, trips never are. Only consumed as
`demand` today (correctly labelled in `plan_assessment.js`), so it is a gap rather
than a live bug — but the next consumer will get it wrong.

### OPEN: an unseen route returns MORE tonnage than a real one

`NOWHERE>NOPLACE` → 9,304 t against TF>FENI KM0's 5,167 t at the same DT, because
the site-wide median cycle (378 min) beats the real one (658 min). The engine is
honest — `basis.cycle_time` says "estimated from the site-wide median (route and
source unseen)" — but `basis.effective_cycle` is an **empty string**, and a typo
buys you a better answer. **Not reachable from the UI**: all 36 routes offered by
`/api/simulate/options` have measured cycles. API-contract gap only.

### Clean under stress

Backend monotonicity (1→5000 DT, 0 violations), conservation across 3 paths
(exact to 0.00 t), idempotence, duplicate-row handling, shared-point clipping and
weather-invariance of simulate tonnes all pass. Split-vs-combined (800 vs 400+400)
differs by 1 t — rounding only.

### A · Shift outcomes was deleted; J71 moved with it

The owner removed the whole A block and renumbered B→A. That deleted the
*defective* capacity card; the honest implementation was always `psRender()` in
`plan_simulator.js`, which computes `planned − achievable` from the engine and
renders `capacity_warnings`. The two-definitions problem is resolved by
elimination. `J71` now targets `psRender` / `#ps-foot` / `#ps-kpi-*`;
re-mutation-tested 2026-08-12 (path-model denominator → 3 failures).

**`planRenderOutcomes` in `plan_scenario.js` is now dead code** — its container
`#plan-scenario-outcomes` no longer exists, so it returns at its first line.
Delete it or restore the container; do not leave a third capacity renderer lying
around for someone to wire back up.

## Section C · Fleet efficiency — it is ceiling-sharing, NOT congestion

The Efficiency toggle on the Fleet-sensitivity chart (`plan_sensitivity.js`,
`_metric`) plots what share of a path's own free rate each truck still gets.
Read the label carefully before extending it, because the obvious reading is
wrong here.

**There is no congestion term active on these paths.** `dayB` is *positive*
(+0.00228 on TF>FENI KM0, +0.00093 on TF>FENI KM15), so `planTripsPerDT` sets
`slope = 0`. Efficiency falls for one reason only: `dayTripsCap`, the most trips
any single day ever produced, is fixed, so extra trucks divide the same trips.
That is consistent with the rest of the project — adding trucks does not
measurably slow the cycle — and with the day-level rebuild, which found the old
row-level slope was a contractor-mix artifact.

Efficiency is multiplicative and every factor is **already returned** by
`planTripsPerDT`; nothing is re-derived in the chart:

```
efficiency = rateFactor(rain · other traffic · shared section · contractor)
           × satFactor(demonstrated day ceiling)
           × wbFactor(weighbridge throughput)
```

The baseline is recovered as `sf = shiftFree/daily` then `rawRate × sf`, rather
than calling `planShiftFactor()` again — one convention, one source.

Measured 2026-08-12, TF>FENI KM0 with RIM:

| DT | pre-sat rate | satFactor | wbFactor | efficiency |
|---|---|---|---|---|
| 170 | 2.379/day | 1.000 | 1.000 | 100% |
| 176 | 2.379/day | 0.979 | 1.000 | 98% |
| 800 | 2.379/day | 0.234 | 1.000 | **23%** |

**The kink moves with the contractor.** `planContractorFactor(RIM) = 1.085`
lifts 2.193 → 2.379/day, so the ceiling binds at 410/2.379 = **172 DT**, not the
410/2.193 = 187 you get from `dayRate` alone. A more productive contractor hits
the ceiling *sooner*. Do not compute the kink from `dayRate`; take it from the
swept `satFactor`.

> **Efficiency is a ratio to each path's OWN baseline, so it does not rank
> paths.** KM15 at 41% still moves 1.06 trips/truck/day; KM0 at 100% moves 2.19.
> A planner optimising the percentage picks the wrong haul. Every efficiency
> readout carries the absolute trips/DT for exactly the reason the capacity card
> above went wrong — a bare ratio gets read as a verdict.

Road-only/foreign rows get **no** efficiency curve: they are a flat measured
rate with no free baseline to divide by, and a fabricated 100% would be worse
than an absent line.

The `.plan-sens-gran` class is now used by **two** button groups (metric and
scale). Both handlers are scoped — `button[data-g]` and `button[data-m]` — because
an unscoped `.plan-sens-gran button` selector strips the other group's `.on`.

### OPEN (2026-08-12): the REALISM history band is a projection, not history

Found while auditing the card above; **not yet fixed**, no gate. The card reads
"History P25–P75 · similar-fleet days". Neither half is true at large DT:

- `ensemble_from_analogues()` in `plan_analogues.py` is explicit in its own
  docstring — *"Median / P25 / P75 forecast from matched days' trips/DT × planned
  DT"* — and ships a `note` field saying so. **The backend is honest; the UI label
  is not.** The `note` is never rendered.
- At 1360 DT the band shows 74,138–79,610 t. The matched days are **99–158 DT**
  and each moved **6,000–9,800 t**. The band is those days' trips/DT multiplied by
  1360, with no decline and no ceiling.
- So the band is **linear in DT** while "Your plan" (path model) is not. At large
  fleets the band mechanically towers over the plan, which makes **"Below history
  band" a foregone conclusion** rather than a finding.

`_score_candidate` does rank by *closest* fleet, but closest is not similar: with
an observed max of 67 DT on this path, the nearest day to 1360 is still ~20×
smaller. **Ranking by proximity does not license a "similar" label** — say what
the comparison is (history's rate at your DT) or show the matched days' actual DT
next to it.

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

**72/72**, measured 2026-08-18 with the server on :5055 (J71 capacity card and
J72 scenario waterfall both scored). `G24` gates the **mirror only** — see the
top of this file and the comment above it in `scripts/verify_phase2.sh`.
`TOTAL` is derived at runtime, so the denominator moves itself.

## Mine-plan scenarios — same fleet, different allocation

Gate `J72`, `scripts/check_scenarios.py`. Built 2026-08-18 from the owner's
workbook `20260818 Mine Plna RKAB H2 SAP 5Mt + LIM 15 Mt For Simulator.xlsx`.

`scenario_api.py` (`/api/scenarios` list · `/import` · `/<id>/allocate` ·
`/compare` · `/export` Excel) + a card on `/monthly`. A **scenario** is pit × material monthly
ROM targets (t/day) only. The **fleet is never part of a scenario**: every
scenario runs on the yearly matrix's DT per contractor per month. Allocation
is the owner's priority waterfall:

  P1 SAP to target → P2 LIM-TOS to target → **every** free DT to P3 LIM-LD
  (Tofu limonite dump → Huafei) at demonstrated t/DT/day, cumulative cap
  **8,000,000 t** (`LIM_LD_CAP_T`).

Hard rules the gate pins in BOTH directions (the J71 lesson):

- **DT conservation per contractor**: used + free == pool, every month. A
  spare SMA truck can cover TOFU/KRENE work of the other contractor
  (lending) but trucks are never created, destroyed, or averaged.
- **BLB is RIM-only** — in the data, in the allocator, and in the lending
  path (lending never moves trucks *into* a RIM-only pit).
- Impossible targets **starve P3 to zero and report deficits** — the
  waterfall never invents trucks to save a scenario.
- **S1 is derived live** from `yearly_matrix.json`. It has no file, cannot
  be imported over, cannot be deleted. `data/scenarios/S1.json` existing at
  all is a gate failure. S2/S3/... live in `data/scenarios/{id}.json`.

The importer reads the workbook's **long-format** `Mine Plan DB` sheet
(Scenario | Month | Nb Days | Mining Pit | Material | wmt ROM) — a different
shape from the wide month-column matrix `_parse_yearly_matrix` reads. wmt ROM
÷ Nb Days becomes t/day. Months a scenario omits (August) fall back to S1
targets, and the UI says so on the detail summary.

Measured result (why the feature exists): S1 reaches **5.45 Mt** LIM-LD —
short of the 8 Mt sales limit by 2.55 Mt, with September at literally zero
free DT. S2 and S3 both **hit the 8 Mt cap before December ends** (~9.5 Mt
uncapped capacity, ~790 DT spare in December), because they defer SAP
tonnage out of Sept–Nov. App SAP totals reconcile to the workbook's own
grand totals to +14 t / +19 t on ~6 Mt (rounding of t/day × days).

### 2026-08-12 — do not run the harness against a server someone is using

A run scored **68/70**, and **both failures were artifacts of the run itself**, not
defects. Read this before chasing either:

- **F23 `/api/retrain` returned 409, not a crash.** `prediction_api.py` serialises
  retrains (`if not _RETRAIN_LOCK.acquire(blocking=False)` → *"a retrain is already
  running"*). One was in flight from a browser session; the harness POSTed into it.
  The endpoint was healthy — it returned 200 minutes later and finished in 155.4 s
  (`random_forest R²=0.5854, MAE=0.4411, 3816 rows`).
- **J57 was collateral.** It ran while that retrain was rewriting `data/`.
  Standalone, `python test_weather_path.py` exits 0 with every route passing.

The server log is what settles it: `POST /api/predict` and `/api/plan/ai-advise`
every few seconds throughout the run. **F23 asserts `== "200"` and so reads a 409
as a dead endpoint.** Either run the harness against an idle server, or check the
log before believing an F23 failure. Effective score that day was 70/70.

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
- Keep Plan Step 1 sparse: default haul Source **TF** / Destination **FENI KM0**; Day (not shift) is the default grain and must apply page-wide; date + rain in conditions; estimated output beside plan date; best-past-days collapsed behind a dropdown under conditions; collapse the 16-day Open-Meteo rain outlook under the forecast line and auto-fill rainfall mm when a day is chosen; Conditions and Add-haul-path cards stay compact; holding plan listed under the builder; rainfall moves Step 1 WMT. Road-only mode uses **IWIP / POSITION** contractors and measured non-plan locations (no WMT); highlight **+ Road-only paths** as adding average IWIP/Position rows for bridge load and road congestion. Estimate card: WMT stays clear at any width; warnings sit full-width below and never crush tonnage; do not show `est-warn` under plan-preview tonnage. No Auto-balance trucks strip — bridge-over-70% warning sits next to add/change WB.
- On Run Scenario (Step 2), do **not** show an A · Shift outcomes block. Lettering is **A** Production & capacity, **B** Fleet sensitivity, **C** Road crowding by hour, **D** Full assessment, **E** Insights from history; lead with production/capacity and a professional loading state; defer the road/GPS corridor until after the corridor run; hour-of-day charts must show which hour is selected; prefer decision-oriented outcomes over repeating tables. Keep planned WMT vs achievable/adjusted consistent — never average predict + simulate + history into one total, and do not manually floor/min Prediction vs Achievable. Keep each engine's own number. Do not cap Plan achievable to target; on `/monthly` and Year Excel hide old/new achievable entirely — keep target, old predicted, and optimized predicted.
- Plan-impacts: hide weighbridge status rows (Bridge load board owns that); keep ✦ AI analysis but never attribute or name the model underneath; use simple fleet-size language and drop the fleet-size row when AI already covers the same point.
- Planning goal: best production with less congestion using the minimum required trucks — support edit-from-outcomes once verdicts exist.
- Allocate DT as per priority (Plan Check capacity): leave original Production & capacity / Your plan frozen (unlock to edit DTs after a saved allocate). Separate New Allocation Plan underneath. Same contractor only — trucks never cross contractors. Size P1 SAP so Predicted sits at ~100% of target (never well above); P2 LIM-TOS likewise is sized to target, NOT fed extras. EVERY leftover truck goes to P3 LIM-LD (owner 2026-08-19: “LIM-LD is the only place extra trucks go — it has no kind of cap”; the 8 Mt figure is a sales target line, never a clip). Cross-contractor rescue: when a contractor's fleet is exhausted and its LIM-TOS is still short, the OTHER contractor's LD-buffer trucks cover the pending tonnage as a NEW path row under their own contractor (trucks never change owner); helper rows carry targetWmt 0 so bucket targets don't double-count. Hard wall: no non-RIM truck ever enters BLB. P3 LIM-LD is first donor and leftover sink; if LD is dry, take from LIM-TOS (LIM may short). Do not fill P2 or dump extras onto LIM while any same-contractor P1 is still below Predicted target. Size SAP shortfall/surplus from Predicted vs target, not requiredDt inverse (requiredDt can read “already sized” while Predicted is still thousands short). When P1 is still short, drain P2/P3 to 0 DT (do not leave 1 truck to keep the path); drop 0-DT paths from the table. Keep tonnage/target on every path including LIM-LD. LIM-TOS vs LIM-LD to the same plant stay separate rows. Table: Target next to Predicted; P1/P2/P3 filters; hero is New predicted + New achievable + one Before/After line. A mine-plan scenario is pit × material monthly ROM targets only (fleet stays the yearly matrix). LIM-LD is leftover DT to Tofu dump → Huafei (8 Mt cap), not a typed scenario target. Per-scenario Excel must match Year board `/api/monthly/export-year` (`monthly_plan_YYYY.xlsx`: Year + Aug–Dec; target / old predicted / optimized predicted; SAP · LIM-TOS · LIM-LD; path table; DT moves) — not a combined Compare workbook.

## Learned Workspace Facts

- Simulate tonnes use **effective cycle** `(truck_shifts × 720) / trips`, not weigh-to-weigh predicted cycle (~77 min median). Confusing them overpredicts badly. Site median effective is ~389 min; consecutive start-to-start pairs ~240 min — do not conflate those two “240” stories.
- `DEFAULT_AVAILABILITY = 1.0` for tonnage (J52 + J55). Downtime is already inside effective cycle; never re-add 0.85/0.80. Measured residual **+5.5%** is exposed as companion `ticket_calibrated_achievable_t` (÷1.055, not primary) with Plan lens default ON. Do not “fix” via availability (×0.85 → −10.3%). Roster sizing may still use mechanical availability (~0.72) for fleet count only.
- Congestion / road V/C, Jul+ corridor clock (`/api/plan/corridor-hours`, `/api/plan/day-segments`, `/api/plan/gps-coverage`), congestion advice (`/api/plan/congestion-advice`), and shared-road DES-lite (`/api/plan/shared-flow`) are measured or advisory and must **never** modify simulate tonnes (J53); `basis.congestion_clips_tonnes` always false. Stick CSV refresh: `scripts/refresh_stick_from_archive.py` (also after `accumulate_gps`).
- Point capacity is a **p99 hourly throughput lookup** (not ML). Shared-loader p99 can clip achievable tonnes — that is point capacity, not a congestion term in cycle. Dwell models: wet/dry are served; day/night may be computed but unused at serve. Dual-mode `_register` wraps **8** simulator endpoints (not “all APIs”) — counted 2026-08-12 at `simulator_api.py:1999-2006`; this said 7 until `weighbridge-by-path` was added.
- Achievable tonnes / Plan Step 2 outcomes come from `/api/simulate`, never flow particles. Step 1 WMT uses path-response **main-cluster** `avgTr` (mid-60% trimmed mean of daily trips/DT, with P25–P75) × contractor `clamp(tripsPerDT/fleet, 0.5–1.5)` × rain; **simulate ignores contractor factors**. Rain may move Step 1 WMT; simulate tonnes stay weather-invariant (J57). Do not force Achievable to equal Prediction — they are two clocks (ticket path model vs effective cycle + loader clip).
- Capability Shift Road is illustration/replay; particles are not production. Flow speeds default to measured GPS; posted limits are overlay only. Offline API payloads live in `fixtures/`; models, GPS archive, snapshots, and saved plans live in `data/` (disk snapshots `cap_snapshot.json` / `pr_snapshot.json` sit between memory and fixtures).
- **DB roles:** `WBN_DATABASE` = ops truth; `FMS_DB` = location. Haul GPS (`FMS_CONGESTION_SEG` / `FMS_GPS_Historical`) from **2026-07-15** only. Playback Feb+ is HRM/support (**0%** haul plate overlap) — never for haul V·C or analogue replay; `/api/plan/playback-truth` documents that. Grow haul history with `scripts/accumulate_gps.py` (cron 07:00/19:00); `FMS_EQUIPMENTS.plateNumber` joins weighbridge.
- Capability defaults `2026-01-01` → `2026-05-31` (peak). Jul GPS V/C is struggle-season illustration only. Plan analogues (`/api/plan/analogues`) match contractor; rank trips then trips/DT. HRM impact on trips/DT is ~0 (r≈0.0006) — keep excluded. **Peak road proxy:** `/api/plan/peak-road-proxy` — Jan–May section DT/trips from weighbridge path-days (ops pressure); `speeds_kmh` is always null. Not Playback and must not be presented as a selected analogue day’s averages.
- Shift length calibrated at **720 min** (~98.5% of shifts); other lengths raise `shift_minutes_extrapolated` (J60). Holding plans save locally via `/api/plan/saved` → `data/saved_plans/{date}.json`. A saved reallocation stores old + new allocation, predictions, targets, and DT moves (for monthly report); the on-screen Your plan stays the original.
- Mine-plan scenarios: pit × material monthly ROM only; fleet is yearly-matrix DT. Waterfall P1 SAP → P2 LIM-TOS → leftover DT to P3 LIM-LD (Tofu dump → Huafei), 8 Mt cap. S1 is live yearly matrix (not importable). LIM-LD is leftover output, not a typed target. `/api/monthly/export-year` writes `monthly_plan_YYYY.xlsx` (Year + Aug–Dec). `/api/scenarios/export-full` zips one such workbook per scenario (`monthly_plan_2026.xlsx`, `monthly_plan_2026_S2.xlsx`, …); S2/S3 Excel is synthesized from the waterfall.
- Hide the Capability filter header (`.top`) on Plan and Production Simulator tabs; keep the sim-tab strip so users can leave Plan.
- Never invent pre-2026-07-15 haul speeds from Playback; path-response main-cluster trips/DT will sit below a single best past day by design (trimmed mean, not the peak day).
