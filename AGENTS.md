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

- Default DT motion to Measured GPS; hide manual Loaded/Empty km/h until the user explicitly chooses an override, and show a clear highlight that GPS logic is active. Plan GPS corridor particles must stage at the **loading point**, not dump/split endpoints, and follow the survey polyline (not lat/lng chords).
- Treat Advanced Simulation Settings (start, stagger, headway, dwell, trace, and similar knobs) as illustration-only — they must not change fleet size, trips, or WMT.
- Treat trip-implied speed and manual km/h as one override mode, not two separate engines.
- Available fleet (budget) should follow the sum of route what-if DT boxes, not stay stuck on the day-dispatch total.
- Forward planning and achievable tonnes belong on Plan Step 2 / `/api/simulate`; Capability Shift Road is for historical replay and illustration, not the planning estimate.
- Keep the schematic chainage stick always visible with the map; Run should scroll both visuals into view so the user can watch what is playing.
- Best past days / analogues: filter by selected contractor; rank nearby trip count first, then trips/DT; color wet vs dry; show a loading state while searching; omit “ops only / no haul GPS” caveats from that list. When a day is selected, show that day’s figures — do not label Jan–May season averages as that day’s DT/trips.
- Keep Plan Step 1 sparse: default haul Source **TF** / Destination **FENI KM0**; Shift/Day is the planning **horizon** (one 12h shift vs one day), not shift length — Day is default and must apply page-wide; date + rain in conditions; estimated output beside plan date; best-past-days collapsed behind a dropdown under conditions; rain outlook at the top of Plan (`#plan-sec-outlook`) is the rainfall picker (auto-fills mm when a day is chosen) — do not add a second Open-Meteo “Use mm” row under Scenario; Conditions and Add-haul-path cards stay compact; holding plan listed under the builder; rainfall moves Step 1 WMT. Loaders on the builder and holding table (`_planDraft.loaders`, default 2); Cycle badge is text road/loader/ok, not emoji. Road-only mode uses **IWIP / POSITION** contractors and measured non-plan locations (no WMT); highlight **+ Road-only paths** as adding average IWIP/Position rows for bridge load and road congestion. Estimate card: WMT stays clear at any width; warnings sit full-width below and never crush tonnage; do not show `est-warn` under plan-preview tonnage. No Auto-balance trucks strip — bridge-over-70% warning sits next to add/change WB. Plan sticky navbar stays sparse: hide the planning-rules badge and section jump links; do not show empty “no paths yet”; keep Save/Load on the right.
- On Run Scenario (Step 2), do **not** show an A · Shift outcomes block. Lettering is **A** Production & capacity, **B** Fleet sensitivity, **C** Road crowding by hour, **D** Full assessment, **E** Insights from history; collapse **B** at the end of Step 2 behind a dropdown so it does not interrupt the outcomes, and plot the live hybrid/segment saturation curves (`/api/congestion_curve`), not the old path-response dayRate sweep; lead with production/capacity and a professional loading state (Allocate’s overlay sits in front until the New Allocation Plan is ready); defer the road/GPS corridor until after the corridor run; hour-of-day charts must show which hour is selected; Road crowding keeps include IWIP trucks always on and has no whole-day option; prefer decision-oriented outcomes over repeating tables. Keep planned WMT vs achievable/adjusted consistent — never average predict + simulate + history into one total, and do not manually floor/min Prediction vs Achievable. Keep each engine's own number. Do not cap Plan achievable to target. Monthly page: one Excel download (year board); no extra export buttons or filler copy, and do not insert model-explanation prose anywhere in the xlsx. Year board Excel hides old/new achievable (keep target, old predicted, optimized predicted); monthly named sheets hide * Old columns (DT old, Trips Old, …) and strip “New” from remaining headers; S3/S4 workbooks start September (no August sheet or Aug rows). Path sheet columns: Priority (not P); DT, Trips, WMT, WMT/DT, Trips/DT, Nb days — no “New” prefix; numbers black, not red. Excel Path/Year sheets include the other-tenant fleets Plan already shows (MHM / POSITION / PMA / HSM / KR>RSF / HUAFEI>RSF, material other tenant); TOTAL DT stays our fleet. Excel road crowding uses the same loaded-lane occupancy as Plan. Year sheets also carry a per-day pit×destination KPI (rows FENI KM0 / FENI KM15 / POS, columns pits) and both mainline saturation curves (t/DT and total t/day) on the first and last Year pages; the t/DT chart frames on the measured Jan–Jun fleet window, not from zero (BLB spur excluded from the km 0–68 mix). Corridor readouts show trucks-on-road plus a short V/C definition.
- Plan-impacts: hide weighbridge status rows (Bridge load board owns that); keep ✦ AI analysis but never attribute or name the model underneath; use simple fleet-size language and drop the fleet-size row when AI already covers the same point.
- Planning goal: best production with less congestion using the minimum required trucks — support edit-from-outcomes once verdicts exist.
- Allocate DT as per strict target priority (Plan Check capacity): **P1 SAP → P2 LIM-TOS → P3 LIM-LD**. Every supplied target is real, including typed/imported LIM-LD; P3 is filled only after P1/P2. Fleet beyond all targets is reported as unused/excess capacity and must not be credited as production. Leave original Production & capacity / Your plan frozen; edits on a locked plan confirm once, unlock, and apply so Check capacity / Allocate follow the on-screen builder, not a saved snapshot. Separate New Allocation Plan underneath: group production rows by origin; IWIP / POS-transit / road-only (`foreign`/`_posTransit`) rows last. Hide the DT-move log (`#plan-alloc-moves` and the same notes under Allocate) — allocator still computes/saves notes; validation stays, not inside table number cells; omit trips/DT range WARN/PASS lines from the validation summary. Same contractor first; cross-contractor rescue creates a new helper path under the truck's real contractor. Hard walls still apply (BLB=RIM, KR=SMA). P3 remains the first donor when P1/P2 are short. Size target shortfall/surplus from Predicted vs target, not the requiredDt inverse. Keep LIM-TOS and LIM-LD as separate rows even at the same destination. Frozen allocations must contain raw `/api/simulate` achievable values for every active row; target-credited prediction is a separate clock and may never masquerade as achievable. SAP to FENI (indirect) is **±2,000 t/day** (not 10,000); surplus SAP goes to POS as buffer, and IWIP reclaim from POS must equal WMT tipped into POS.

## Learned Workspace Facts

- Simulate tonnes use **effective cycle** `(truck_shifts × 720) / trips`, not weigh-to-weigh predicted cycle (~77 min median). Confusing them overpredicts badly. Site median effective is ~389 min; consecutive start-to-start pairs ~240 min — do not conflate those two “240” stories.
- `DEFAULT_AVAILABILITY = 1.0` for tonnage (J52 + J55). Downtime is already inside effective cycle; never re-add 0.85/0.80. Measured residual **+5.5%** is exposed as companion `ticket_calibrated_achievable_t` (÷1.055, not primary) with Plan lens default ON. Do not “fix” via availability (×0.85 → −10.3%). Roster sizing may still use mechanical availability (~0.72) for fleet count only.
- Congestion / road V/C, Jul+ corridor clock (`/api/plan/corridor-hours`, `/api/plan/day-segments`, `/api/plan/gps-coverage`), congestion advice (`/api/plan/congestion-advice`), and shared-road DES-lite (`/api/plan/shared-flow`) are measured or advisory and must **never** modify simulate tonnes (J53); `basis.congestion_clips_tonnes` always false. Stick CSV refresh: `scripts/refresh_stick_from_archive.py` (also after `accumulate_gps`). GPS packing following distance is **50 m** (`congestion.speed_limits.FOLLOWING_DISTANCE_M`); official section caps are S1–S3 **600/hr** and S4 **400/hr** (trucks per hour through the section, not sitting on it). 600/hr is **one loaded lane**, not both carriageways (~2× would be 1,200/hr and is not used). One loaded lane at 50 m fits 576 trucks on TF–KR, 240 on a 12 km stretch, 300 on KM15–coast. Crowding occupancy / `peak_concurrent` / Plan grid / Excel Road crowding count the loaded lane only (empty sits on the other carriageway). Packing table and Plan road-windows tag v/c GREEN (<0.7) / YELLOW (0.7–1.0) / RED (>1) and caption Cap/hr · loaded lane. Do not hardcode 60 m, 75 m, or 500/hr. Tenant occupancy uses the run’s measured clock (not official-limit transit). Crowding cells stay totals but name the split (tenant const vs ours) on Plan, verdict, and Excel.
- Point capacity is a **p99 hourly throughput lookup** (not ML). Shared-loader p99 can clip achievable tonnes — that is point capacity, not a congestion term in cycle. Dwell models: wet/dry are served; day/night may be computed but unused at serve. Dual-mode `_register` wraps **8** simulator endpoints (not “all APIs”) — counted 2026-08-12 at `simulator_api.py:1999-2006`; this said 7 until `weighbridge-by-path` was added. Weighbridge auto-alloc (`/api/plan/wb-allocate`): identity is the matrix NAME, never the ticket number (`WB_RIM_T7` ≠ `WB_IWIP_T7A`); **T11 never**; tenants never. FENI letters T/U/U1/U2/W/X map to FENI KM15 (WB12/17); A–S map to FENI KM0.
- Achievable tonnes / Plan Step 2 outcomes come from `/api/simulate`, never flow particles. Step 1 WMT uses path-response **main-cluster** `avgTr` (mid-60% trimmed mean of daily trips/DT, with P25–P75) × contractor `clamp(tripsPerDT/fleet, 0.5–1.5)` × rain; **simulate ignores contractor factors**. Local `planTripsPerDT` day-cap scales by `nLoaders / (historicalLoaders || 2)`; `/api/simulate` payloads include `n_loaders`. Yearly-matrix paste may include optional LOADERS (default 2). Hybrid/shared-road trips/DT for allocation and Fleet sensitivity follow **road time** via `/api/congestion_curve` (segment/hybrid), not loader-queue collapse or path-response dayRate — BLB must not crater from faces. Rain may move Step 1 WMT; simulate tonnes stay weather-invariant (J57). Do not force Achievable to equal Prediction — they are two clocks (ticket path model vs effective cycle + loader clip).
- Capability Shift Road is illustration/replay; particles are not production. Flow speeds default to measured GPS; posted limits are overlay only. Offline API payloads live in `fixtures/`; models, GPS archive, snapshots, and saved plans live in `data/` (disk snapshots `cap_snapshot.json` / `pr_snapshot.json` sit between memory and fixtures).
- **DB roles:** `WBN_DATABASE` = ops truth; `FMS_DB` = location. Haul GPS (`FMS_CONGESTION_SEG` / `FMS_GPS_Historical`) from **2026-07-15** only. Playback Feb+ is HRM/support (**0%** haul plate overlap) — never for haul V·C or analogue replay; `/api/plan/playback-truth` documents that. Grow haul history with `scripts/accumulate_gps.py` (cron 07:00/19:00); `FMS_EQUIPMENTS.plateNumber` joins weighbridge.
- Capability defaults `2026-01-01` → `2026-05-31` (peak). Jul GPS V/C is struggle-season illustration only. Plan analogues (`/api/plan/analogues`) match contractor; rank trips then trips/DT. HRM impact on trips/DT is ~0 (r≈0.0006) — keep excluded. **Peak road proxy:** `/api/plan/peak-road-proxy` — Jan–May section DT/trips from weighbridge path-days (ops pressure); `speeds_kmh` is always null. Not Playback and must not be presented as a selected analogue day’s averages.
- Shift length is locked at **720 min** (`#ps-shift` stays hidden); Shift/Day on Scenario is horizon only — do not show a visible Shift minutes metric. J60 asserts **zero** editable shift/hours inputs (~98.5% of shifts are 720; other lengths would raise `shift_minutes_extrapolated`). Holding plans save locally via `/api/plan/saved` → `data/saved_plans/{date}.json`. A saved reallocation stores old + new allocation, predictions, targets, and DT moves (for monthly report); the on-screen Your plan stays the original.
- Mine-plan scenarios: fleet is the yearly-matrix DT. Waterfall targets run P1 SAP → P2 LIM-TOS → P3 LIM-LD; 8 Mt is the default horizon P3 target, and imported `Type Ore = LD` rows are explicit monthly P3 targets. Capacity beyond target remains visible as unused/excess. S1 is live yearly matrix (not importable). `/api/monthly/export-year` writes `monthly_plan_YYYY.xlsx`; `/api/scenarios/export-full` builds one workbook per active scenario (S2 is deleted).
- Hide the Capability filter header (`.top`) on Plan and Production Simulator tabs; keep the sim-tab strip so users can leave Plan.
- Never invent pre-2026-07-15 haul speeds from Playback; path-response main-cluster trips/DT will sit below a single best past day by design (trimmed mean, not the peak day).

## 2026-08-21 — S2 deleted from the app; S3 is the scenario of record

Owner request: S2 removed everywhere the app offers it. Deleted:
`data/scenarios/S2.json` (git rm), `data/saved_plans/2026-{09..12}-02.json`
(gitignored; copies in `data/saved_plans/_deleted_s2_backup_2026-08-21/`),
and the "Scenario 2 · day 2" option in the /monthly Year-board selector.
`data/s2_results.*` never existed — nothing referenced it. The scenario
system itself is data-driven (`_scenario_ids()` lists `data/scenarios/*.json`),
so no `scenario_api.py` change was needed. J72 now pins S3 (workbook, draft
plans, year-board day=3) and asserts BOTH directions per the J71 lesson:
S3 workbook present AND S2 workbook absent; day=2 resolves nothing.
Day 02 stays reserved — do not save a new plan there.

**Trap while doing it:** most `s2` hits in the frontend are *Step 2* blocks
(`plan-s2-block`, `plan-s2-illust`, …) or a sum-of-squares local, not
Scenario 2. Grep for `'S2'`/`scenarios/S2`/`-02.json`, not bare `s2`.

## 2026-08-21 — Cycle Breakdown chart consumed field names the API never sent

`renderCongBreakdown()` read `c.bpr_min || c.queue_min || …` while
`/api/congestion_model` sends `components.{t_free_road, bpr_penalty_minutes,
queue_wait_minutes, t_load, t_spot, t_dump, bunching_penalty_minutes}`.
Zero keys matched, so the filter left no parts and the chart showed its
"Backend not ready" note on every render — with a healthy backend and a
clean console. A graceful fallback turned a contract mismatch into what
looked like an expected offline state; nothing failed loudly. Same family
as "count drawn canvases": the check that caught it was canvas-count 0 in
`#cong-breakdown-chart` while its two sibling charts drew 1 each. If a
degraded-mode note ships, gate on the healthy path rendering at least once.

## 2026-08-21 — planning_rules.md: the owner's rules are now data the app enforces

`planning_rules.md` (repo root, served at `/planning_rules.md` by serve.py)
is the owner's rule sheet. `static/js/planning_rules.js` (loads right after
api.js) exposes `window.PLANNING_RULES`, fetches the .md on startup and
re-parses every enforced number from it (walls, fixed routes, validation
bands, targets, the P3 split). The literals in the JS are the offline
fallback only — edit the .md, not the JS, to change a rule; keep both in
step. The navbar badge says which copy is live ("ACTIVE" = parsed file).

Enforcement lives in plan_sap_target.js, one point per rule:
- **Walls** (BLB=RIM, KR=SMA): `enforceContractor()` corrects rows at
  CREATION (the builder's contractor select is switched before planAddPath
  so the slot id `contractor|key|material` is born correct — never rename
  an existing row's contractor, its slot id embeds it). Loaded rows that
  break a wall are flagged in the validation summary instead of mutated.
  crossRescue's donor filter now reads the wall table (it only had the BLB
  half hardcoded).
- **P1→P2→P3** was already the allocator; unchanged.
- **POS transit** (§5): after Allocate, whatever the plan tips into
  POS 12/14/15/16 gets IWIP rows POS→FeNi sized from /api/congestion_model
  (re-asked once at the implied fleet — trips/DT falls with fleet, the
  first guess under-sizes). The rows are ROAD-ONLY (`foreign:true`,
  `_posTransit:true`, slot `IWIP|route|road`) — the app's existing
  IWIP/Position mechanism — so they count in road crowding and never in
  production WMT. Rebuilt (delete+recreate) on every Allocate.
- **Validation** (§7): summary + per-row PASS/WARN/FAIL badges (reusing
  .plan-cong-badge classes) render under the alloc moves log.

**S4 = day-04 saves** (scenario-by-day, like 01=S1/03=S3): identical to S3
except leftover TF LD trucks split 50/50 HUAFEI/BSE vs POS 12 (§4 P3).
The split runs ONLY when the plan date is day 04, so S3 stays comparable.
Measured Sep: LD 4,395 → 13,059 t/day (0.54 → 1.59 Mt at 122-day rate) —
TF>POS 12 runs 3.58 trips/DT where the saturated HUAFEI corridor runs
0.63. Saves exist for 2026-09..12-04. **2026-08-04 predates the
convention** — a legacy daily plan, not S4 (it has no frozen allocation,
so the year board's day=4 view correctly skips it).

Traps hit while building this:
- `rowClocks().pred` is HORIZON-scaled (day = 2 shifts). The validation
  bands and POS flows are daily; use `predDayAt(id,r,dt)` (predDayFor at
  an explicit fleet), not pred/hz().
- The rules file contradicts itself on POS: §2 calls it Permanent Ore
  Storage, §5 says transit with input = output. §5 is the operative rule
  (owner spec) and is what the code implements; raise it with the owner
  before "fixing" either.

## 2026-08-21 — IWIP is its OWN fleet; loaders are proportional everywhere

Two owner clarifications, both now rules §10.8/§10.9 in planning_rules.md:

- **IWIP DT never come from the contractor pools.** The POS-transit rows
  were already foreign:true (so the allocator/buckets skip them), but two
  counters leaked: `planNavSync` summed ALL rows into the navbar "X DT"
  (now "581 DT + 27 IWIP"), and `planPredictTotals` had no foreign filter —
  older road-only rows dodged that sum only because their routes were
  OUTSIDE the path model, POS 12>FENI KM0 is not. If you add a consumer of
  `planDraftEntries()`, decide foreign-handling explicitly; it does not
  filter.
- **Loaders on every row = round(DT / trucks-per-loader)** — the route's
  measured calibration ratio (n_trucks_ref/n_loaders, e.g. TF>POS 12 14.4,
  TF>HUAFEI 23.3), 15 when unmeasured (Burt & Caccetta, same as the
  runners). Served as `trucks_per_loader` on /api/congestion_model;
  applied by planRulesApplyLoaders() on every Allocate, OVERRIDING per-row
  loader edits — there is no detailed loader plan yet, owner: "we have to
  imagine we are using the same number of loaders". Revisit if a real
  loader plan ever exists. This moved predictions (trips/DT reprices with
  loaders), so all eight S3/S4 saves were re-frozen 2026-08-21; the
  pre-change files are in
  data/saved_plans/_backup_2026-08-21_pre_proportional_loaders/.

## 2026-08-21 — contractor walls are TRUCK MOBILITY, and the old rescue broke them

Owner: "from KR you can attribute only SMA trucks… extra SMA from KR can
move to TF but not BLB; RIM moves between BLB and TF but never KR." The
walls constrain where each fleet may WORK; trucks never change owner and
are never renamed. Two fixes in planAllocatePriority:
- `wallBroken()` rows can donate but never receive (belowNeed 0, dumpExtra
  receivers filtered), and rows that START with trucks on an illegal pit
  are evacuated to the contractor's TF LD row before the rounds.
- The measured damage: cross-rescue before 2026-08-21 walled only BLB, so
  the Oct/Nov/Dec S1 saves (and 2026-08-01) carried `KR>HUAFEI · RIM`
  helper rows of 7-30 DT. All S1 plans re-frozen clean 2026-08-21; the
  legacy Aug dailies (08-04/05/07: PPP and RIM at KR) are historical
  records, left as-is — the validation panel flags them if loaded.

Also from the same session: unbounded `planLoaderCapScale` (n/hist legacy
cap rescale) × proportional loaders reported 37 trips/DT on BLB>POS 14
(owner range 6-7) and poisoned four saves before being caught — the scale
is now clamped to [0.5, 2] and allocation awaits `planRulesPrepare()`
(loaders + WARM hybrid curves) before pricing. If a plan's numbers look
3x too good, check which pricing path served them FIRST.

## 2026-08-21 — trips = 1440/(cycle + overhead_per_trip); the U anchor was lying

Owner called the saturation table "a lie" and was right about the tail:
`trips = U*1440/cycle` treats breaks/dispatch/shift-change as a FIXED share
of the day, so once the congested cycle exceeded U*1440 (TF>HUAFEI @771:
640 > 527) the model claimed a dispatched truck cannot finish ONE trip in
24 h. Overhead attaches to TRIPS, not the clock:

    trips = 1440 / (road_congested + ops + queue + bunching + overhead_per_trip)

- road_free_min = p25 uncongested day-shift cycle − ops. The weighbridge
  stamps CANNOT give the legs: measured 2026-08-21, TF routes have no
  usable TIME_EMPTY and BLB>POS 14 shows a 90-min "loaded leg" on 6.7 km —
  TIME_LOADED/TIME_EMPTY are weigh events, see the weigh-to-weigh note
  above. GPS corridor speeds × measured km ship as `gps_road_min`
  (cross-check only; corridor means include congested traffic, so they run
  high — TF 464 vs 209 free-flow).
- overhead_per_trip anchored so predict() at the median fleet+faces equals
  the dispatch day-rate EXACTLY (TF>HUAFEI 384.5 min ≈ the 390 the owner's
  spec predicted). `utilization` stays in params as reference; predict()
  no longer reads it. Uncalibrated routes use the global median (131.5).
- Result: trips can never fall below 1440/(3·road_free + ops + caps +
  overhead) — TF>HUAFEI min 1.20 over 50..800 DT. Backtest IMPROVED:
  bucket R2 0.909 → 0.925, MAPE 6.5% → 5.9%. The physically-wrong tail
  was costing fit, not buying it.
- The flow term in the BPR/queue iteration still uses the PRODUCTIVE cycle
  (demand flow), matching the owner's worked example (3x cap engages at
  saturation). Do not "fix" it to n/(cyc+overhead) without re-anchoring —
  it halves v/c and un-saturates every corridor.

## 2026-08-21 — reference saturation curves + the sawtooth was the SOLVER

Owner: "these curves didn't even look like curves." Correct — trips/DT
ROSE in places as trucks were added. Not physics, not the formula: the
predictor solved the cycle↔flow feedback with a damped Picard iteration
that oscillates between the free and saturated branches near loader
saturation and exited after 50 rounds with NO convergence check, landing
on whichever branch iteration 50 happened to touch. nxt(cyc) is strictly
decreasing in cyc, so the fixed point is UNIQUE — it is now found by
bisection. Monotonicity sweep at 5-DT steps: zero violations on both
reference routes. Backtest ticked up again (R2 0.926, MAPE 5.8%). If a
model curve ever wiggles, suspect the solver before the physics.

Reference curves (owner request): scripts/export_saturation_curves.py
freezes TF>HUAFEI and BLB>POS 14 into reports/saturation_curves.{json,
svg} + SATURATION_CURVES.md — committed like speed_density_fit.json
(model outputs, not tonnages). Each route carries TWO bases: `curve` =
loaders FIXED at calibrated faces (what /api/congestion_curve and the
Congestion tab show; BLB falls hard at ~60 DT because 3 faces saturate,
the knee is the LOADER wall), `curve_proportional` = loaders scale
1-per-trucks_per_loader (rules §10.9 — the plan builder's basis; only
the road congests). The "N ÷ 23.3 / N ÷ 6.3" legend numbers are measured
trucks-per-loader ratios, NOT distances — relabelled after the owner
read them as km. /api/congestion_curve serves the frozen JSON tagged
servedFrom:"reference" when a reference route has no live calibration
(fresh clone/fixtures) so charts and plan pricing agree everywhere.
Regenerate after any recalibration.

## 2026-08-21 — P2 drifted 129% over target on shared corridors; two causes

Owner (screenshot, TF>HUAFEI·SMA LIM-TOS): "why allocate more trucks
there — predicted tonnage more than our target." Predicted was 7,149 vs
5,533 target with +48 trucks. Two mechanisms, both fixed:

1. **Rows priced on a shared corridor drift after later moves.** The P2
   fill sized the row while TF>HUAFEI still carried the whole LD block;
   the S4 split/rescue then took trucks off the corridor, trips/DT rose
   for everyone left, and no pass handed the surplus back. There is now a
   `finalTrim` pass AFTER crossRescue: every targeted P1/P2 row re-walks
   down to ~100% and the freed trucks go to the contractor's TF LD rows
   (feeding the short side of the S4 50/50 on day-04).
2. **§10.9 loaders were circular with allocation.** Loaders follow the
   allocated fleet, pricing follows loaders — rows were sized on the
   saved plan's loaders and repriced after Allocate (measured: the
   trimmed row re-landed at 88%, then 115% when the walk crossed a
   loader bucket). `predDayFor` now prices every sizing walk with the
   loaders the EVALUATED dt implies (round(dt/tpl) from _tplCache), and
   planAllocatePriority runs one loaders-relaxation pass, so applying
   loaders after Allocate reprices nothing.

Residual overshoot is quantization only (integer trucks, loader
buckets): a row sits at 104% when removing one truck would fall below
0.995x target. All 13 saves re-frozen; LIM-TOS now lands within ~0.3% of
its day target every month, and the freed P2 trucks lifted LD (S4
Oct/Nov/Dec 8.55/12.75/11.53 Mt — PASS vs 8 Mt).

## 2026-08-21 — TF>HUAFEI rows priced the same road three different ways

Owner: "TF>HUAFEI still using old calculations — fix for all new plans and
capacity checks." Three real defects behind it:

1. **Per-row loader keys on a shared road.** planTripsPerDT fetched each
   row's hybrid curve at the ROW's loaders and evaluated it at the
   COMBINED fleet: 929 trucks priced against 4 faces on one row, 25 on its
   neighbour — same road, same contractor, trips/DT 25% apart. Curves are
   now keyed on the route's COMBINED loaders (rows share the road AND its
   faces; same basis as run_scenarios_hybrid). planRulesWarmCurves warms
   exactly those combined keys.
2. **Failed curve fetches cached null FOREVER.** One server blip mid-
   session silently dropped a route to the legacy divide until full page
   reload — with the many restarts that day, this is what the owner saw.
   Failures retry after 30 s, and while the exact loaders pair loads the
   NEAREST cached loader count serves as interim (loaders mostly move the
   queue term; far closer than the divide fallback).
3. **Hybrid gated on dayTripsCap.** Thin-day routes never consulted the
   physics curve at all and rode the linear regression. Ungated; the
   legacy ceiling still applies only where a day cap was demonstrated.

Same session, owner: S4 must carry the 50/50 division through EVERY
aspect including Achievable. planDraftEntries no longer drops helper rows
(display dt 0, trucks in _allocDt); road crowding and analogues are
frozen-aware; and planRulesPosTransit re-runs planRunScenario after IWIP
rows land so the engine's Achievable carries their corridor drag —
planDraftToPsPlans was already _allocDt-aware. Verified: all TF>HUAFEI
rows now price identically per contractor (RIM 2.46 / SMA 1.69 at the
Sep S4 division) and Achievable moves with the split (65,828 → 77,078 t).

## 2026-08-21 — parallel-agent audit: the S4 split was killed inside MY commit

Owner asked for a review of another model's uncommitted changes ("looks
broken"). Findings, in order of severity:

1. **The S4 split was dead.** A `!(x.r.targetWmt>0)` filter appeared in
   splitLeftoverLd ("only untargeted P3 excess") — and every scenario LD
   row carries a target, so the split never ran again. Worse: that edit
   was already sitting on disk when I staged plan_sap_target.js for
   commit 77c6a42, so it shipped INSIDE my commit unnoticed. Lesson: in a
   parallel-agent repo, `git diff --cached` the file you THINK you wrote
   before committing — a clean `git status` after `git add` proves
   nothing about authorship. Restored: ALL TF LD trucks split on day-04
   (owner, twice: "the LIM-LD trucks divided 50-50"); LD attainment is
   judged at the bucket level; the per-row LD-short warning is gated off
   on S4 days (its shortfall is the what-if working).
2. **Frozen saves now REQUIRE raw achv_sim** (their /api/plan/saved 409
   guard). Aligned with the honesty doctrine, but it rejects saves fired
   before the async engine lands — scripted refreezes must poll the
   allocation payload for finite achv_sim before planSaveForDate().
3. **Doctrine reversals for the OWNER to confirm** (left in place,
   uncommitted): the 8 Mt LD line is now a CLIP on planned production
   (waterfall parks trucks beyond it as "unused") — reversing the
   recorded 2026-08-19 owner rule "never a clip; every free truck hauls
   LD"; the append-only AGENTS.md bullets and the owner-authored
   planning_rules.md §4 were REWRITTEN to match. Route-alias fixes in
   prediction_api (canonical_area everywhere), monthly achievable=raw-sim
   relabel ("credited prediction" separate), and the predictor
   uncertainty warnings are good and suite-green (74/74 with their 74th
   gate).

## 2026-08-21 — one road, one window: span-weighted shared-road pricing

Owner: "they are using the same window for going — see it as a complete
one-day plan, not one row." Different route KEYS sharing a corridor
(TF>HUAFEI vs TF>POS 12 after the split; IWIP POS→FeNi) were priced
independently. planTripsPerDT now adds other rows' trucks (foreign
included) into the hybrid evaluation fleet weighted by chainage-span
overlap (_planSpan); same-key rows stay at weight 1, and the legacy cap
keeps its same-key basis (the demonstrated day cap is a PATH property).
Backend runners still couple by key only — noted gap.

## 2026-08-21 — frozen-plan edits must not be silently swallowed

planRemove/planSet returned silently while _allocFrozen (only Add
alerted). The owner deleted a row, the draft kept it, and Allocate
rebuilt the untouched baseline — "showing precalculated figures, this is
nonsense." Edits on a locked plan now confirm once, unlock, and apply,
so Check capacity always follows the plan as built on top. Verified:
delete on frozen 09-01 → prompt → row gone → re-allocate does not
resurrect it.

## 2026-08-21 — road windows: visibility SHIPPED, pricing REVERTED same day

Owner asked to price each chainage window ("see how many trucks are
moving in each section and what speed it allows — one trips/DT for the
whole route is wrong"). Built congestion/sections.py +
POST /api/congestion_plan: per-window trucks/flow/v-c/measured-speed for
the WHOLE plan, and a shared-road ratio multiplying the calibrated curve.
The ratio came straight back out on the owner's screenshot ("BLB trips
falls like hell — go back to what we were doing before"; a plan lost
~20k t/day): its capacity basis was each section's median OBSERVED peak
— the dayTripsCap trap again, "the most we ever did" read as "the most
we can do" — so ordinary plans scored v/c ≈ 2 on every mainline window
and every route was double-charged (the calibrated per-route curve
already embeds real-day cross-traffic; backtest R2 0.926, and the
own-flow basis of the section model reproduces the dispatch anchors,
e.g. BLB>FENI KM0 5.09 vs 5.07). What remains: the "Road windows"
table in the validation panel is INFORMATION ONLY (trucks, flow/hr,
demonstrated peak, measured GPS speed per section) — do not re-wire
shared_road_ratio into planTripsPerDT without a real capacity basis
(geometry headway per section, not observed peaks) and a re-anchored
overhead. planTripsPerDT keeps the span-weighted fleet as its
shared-road term.

Coordination note: another agent is reworking plan_sap_target.js in the
same hours (alloc table sort helpers; the per-row PASS/WARN/FAIL badge
`valHtml` was dropped from the tpd cell — an owner-visible feature from
the rules work). plan_sap_target.js is deliberately left uncommitted
with BOTH edit sets in the tree; whoever commits next must re-check the
badges render.

## 2026-08-21 — BLB +250 kt/month LIM-TOS: it was NEVER in the plans

Owner: "I asked you to add 1 Mt in BLB to get 4.6 Mt of TOS LIM — right
now LIM total is 3.6." Measured: all eight S3/S4 saves carried only the
scenario BASE on BLB>HUAFEI LIM-TOS (11,954/18,028/27,789/25,728 t/day
= 2.55 Mt/4-mo) and the all-pit LIM-TOS target total was 3.57 Mt — the
owner's 3.6. The +250,000 t/month is an ADDITION on top of the imported
base (their arithmetic: 3.6 + 1.0 = 4.6), applied to the eight saved
plans (+8,333 t/day 30-day months, +8,065 31-day; `_targetManual` set so
the stamp never reverts it) and to data/scenarios/S3.json (with a note
field) so draft-plan regeneration keeps it. stampYearlyTargets never
overwrites a positive target — file edits to `targetWmt` are load-safe.
Re-frozen: LIM-TOS met EVERY month in both scenarios; delivered 4-mo
actuals ≈ 4.64 Mt (S3) / 4.65 Mt (S4); BLB>HUAFEI runs 68/87/121/113 DT
(was 40/60/93/86); S4 LD still PASSES Oct–Dec (8.58/12.69/11.72 Mt).

## 2026-08-21 — deep scan for the road-model rework: three measured facts

Full plan: reports/ROAD_CONGESTION_MODEL_PLAN.md (owner-ordered: geometry
first, then contractor baselines from matched history, then shared-window
loads on a REAL capacity basis, side-by-side before wire-in). The facts
that must not be re-derived:
1. **NODE_KM pins BLB at 67.8 = TOFU's chainage.** Every span/section
   computation puts BLB trucks on the whole mainline; BLB is a 19.9 km
   spur joining low. This poisoned span-sharing AND the section pricer.
2. **TF corridor distances are unsettled**: chainage 63.7/52.8 km vs
   cycle-implied 29.0/28.6 (calibration's chainage_suspect flag). Flow
   density, spans and section attribution inherit whichever is wrong.
3. **The global contractor factor is INVERTED on TF**: matched same-day
   pairs (n=469, both fleets ≥5 trucks, identical road conditions) give
   RIM/SMA = 0.60 trips/DT (RIM 1.88, SMA 3.19) while the app applies
   RIM 1.085×. Raw contractor averages are fleet-size-confounded (RIM
   ~140 trucks/day vs SMA ~58); only matched days isolate the effect.
   TF>POS 12 specifically has ~no direct paired history — the app's
   RIM-ahead numbers there are pure factor artifact.

## 2026-08-22 — segment-based shared-road pricing + contractor baselines SHIPPED (backend)

The road-model plan's P0-P2, implemented per the joint spec:
- **congestion/segments.py** — the stick: S1 TF–KR (67.8–39, cap 60/hr
  geometry), S2 KR–POS12 / S3 POS12–KM15 / S4 KM15–coast (cap 240/hr —
  the class calibration already gave every KR/BLB route running there;
  before this, the SAME shared kilometres had c=60 for a TF route and
  c=240 for a KR route). BLB is a spur: no stick segments, per-route
  pricing, BY DESIGN.
- **predict(segment_fleet=, contractor=)** — stick routes ALWAYS price
  road time per segment (own fleet when segment_fleet absent), so the
  calibration anchor holds exactly when a route is alone and CROSS
  traffic is the only added penalty (no double-charge; anchors verified:
  TF>HUAFEI 2.38 vs 2.374, KR>POS 12 4.62 vs 4.613, BLB>POS 14 7.07 vs
  7.069). Nov S3 plan drag, alone vs shared: TF>FENI KM15 2.62→1.85,
  KR>POS 12 4.61→3.79, TF>POS 12 3.53→2.08, BLB rows byte-identical.
- **Per-contractor baselines** in calibration: matched SAME-DAY trips/DT
  ratio vs the pooled route (>=30 days, both >=5 trucks, EB-shrunk K=20,
  bounded 0.6–1.4; ticket basis on BOTH sides so the two-240s problem
  cancels; raw contractor means are fleet-size-confounded — RIM ran
  ~140/day where SMA ran ~58). Key result: TF>POS 12 RIM 0.673 (227d) vs
  SMA 1.152 (313d) — history INVERTS the old fleet-global factor there.
  Overhead re-anchored per contractor on the POOLED cycle: one road, one
  physics; contractors differ only in level. route_params(route,
  contractor=) merges rec['contractors'][NAME].
- run_s3_hybrid prices per (route, contractor) at the combined fleet
  with the plan's segment_fleet (IWIP rows included) and prints the
  per-month SEGMENT FLEET table — S1 is the binding window (v/c 1.5→2.4
  Sep→Nov); the lower mainline stays <0.81.
- Backtest R2 0.925 / MAPE 5.9% (unchanged — backtest calls carry no
  segment_fleet). Suite 74/74 after a VPN flap (J56/J70/J71 fail ONLY
  when the site DB is down — check `SELECT 1` before investigating).
- NOT yet wired: the frontend still prices via per-route curves with the
  span-weighted approximation (and its NODE_KM BLB=67.8 span bug). Next:
  serve segment pricing to the app (P3 side-by-side), then re-freeze.

## 2026-08-22 — the app runs on segment pricing; capacities are now OFFICIAL

Two rounds in one day, both owner-driven:

1. **UI wiring (segment model live in the app).** /api/congestion_curve
   and /api/congestion_model accept `others=<JSON {route: dt}>`; the
   curve is then computed under the PLAN's background traffic (segment
   fleet = others + the sweep fleet at every point). plan.js snapshots
   the draft per Allocate pass (`planSetSegBackground`, foreign/IWIP
   included) and keys the curve cache on route|loaders|rain|bgSig; when
   a curve is segment-based the client evaluates at the SAME-KEY fleet
   only (the server owns cross-traffic — never price it twice; the
   span-weighted fleet remains solely the cold-start fallback).
   Per-contractor baselines ride the same response: the client transform
   trips_c = 1440/(1440/trips − ovh_pooled + ovh_c) is EXACT, replacing
   the fleet-global planContractorFactor wherever calibration has a
   matched-day ratio. TRAPS hit: (a) warm loops must warm the SAME key
   family pricing consumes (prop keys, current bg) AND check
   c.segment_based — an interim (stale-bg) curve is not undefined;
   (b) planTripsPerDT's return hard-coded modelVersion 'hybrid' and hid
   the segment tag.
2. **Official capacities (owner documents).** congestion/speed_limits.py
   encodes the 2025-08-11 speed-limit sheets as SEPARATE directional
   tables (ARAH MUATAN = loaded = down-chainage; KOSONGAN = empty = up)
   plus geometry: 15 m, one lane per direction, separate loaded/empty
   lanes, no overtaking. Segment capacity = MIN bin speed / 50 m
   following (a 20 km/h stretch bounds the chain — averaging overstates):
   S1–S3 600/hr, S4 400/hr. The old 60/240 headway classes were 2.5–10x
   LOW — the "S1 bottleneck" (v/c 2.4) was an assumption artifact,
   owner-caught. Real plan v/c: 0.19–0.26. Consequence the owner should
   see plainly: at official capacities the ROAD does not collapse at
   planned fleets; TF>HUAFEI holds ~2.2–2.4 trips/DT even at 800+ trucks
   and the binding constraints move to loaders/ops/overhead. Free-time
   shares per segment follow the limit-implied times; the route TOTAL
   stays dispatch-anchored (limit round-trip 238 min vs calibrated
   208.7 on TF>HUAFEI — documents, dispatch and distances mutually
   consistent within ~7–14%). /api/road_segments serves the segments
   with speeds, capacity basis, following distance and the source PDF.
   Backtest R2 0.926 / MAPE 5.8%; suite 74/74; all 13 saves re-frozen
   (partly by the co-agent working the same task concurrently).

## 2026-08-22 — UNI UNI / BIRI BIRI side roads: OUT OF SCOPE (owner)

Owner: "we don't need to think of BIRI BIRI or UNI UNI, ignore it for
now." Pages 3-4 of the speed-limit PDF stay unencoded on purpose; the
stick (S1-S4) and the BLB spur are the modelled network. Do not wire
the side roads in without a new owner decision.

## 2026-08-22 — hourly road-crowding DES now runs on the segment model

Owner: predict how many trucks are in each section at each hour of the
day, "near to the physical world, using the physics model we just made".
plan_shared_flow rebuilt on the current model, keeping the API shape:
- Per-truck timing from congestion.predictor at the PLAN's fleets
  (segment_fleet from every route, contractor baselines, rain): road time
  split over S1–S4 by the OFFICIAL directional speed-limit times; release
  cadence = cycle + overhead_per_trip (trucks do not re-enter the road on
  breaks — the old DES cycled them at raw cycle and over-packed trips).
- Trips now occupy the road BOTH ways: loaded pass, dump dwell, empty
  return in reverse at empty-direction times (was loaded-outbound only).
- Releases are PARALLEL across loading faces (~1 per 15 trucks, §10.9).
  The old serial stagger modelled ONE loader per pit, so a 230-truck
  fleet mostly never departed and peaks read ~12 trucks; real peaks are
  ~300-400 concurrent at v/c 0.25-0.33 vs official capacities.
- Sections are the model's segments + a "<PIT> spur" pseudo-section for
  non-stick routes — the NODE_KM BLB=67.8 smear is thereby OUT of the
  hourly view (BLB never rides the stick here). Capacity per section =
  official per-lane cap x 2 (occupancy counts both directions, separate
  lanes); spur = 800/bin estimate (20 km/h floor, no limit sheet).
- test_plan_shared_flow's shared-section target moved to "POS 12–KM15"
  (TOFU>KM0 and KR>KM15 share S2+S3 under the new split; the old
  POS 10–FENI 0-17 section no longer exists).
D18b flapped once during a server-restart race on the shared box —
probe /api/predict aliases directly before investigating. Suite 74/74.

## 2026-08-22 — road crowding: plan of record + real-plan verification

Owner: "fix all this, make a detailed plan, make it real plans and real
physics." The four physics defects were already fixed (cc40b41); this
round added the plan document + closed the real-plan gaps:
- reports/ROAD_CROWDING_BY_HOUR_PLAN.md is the plan of record: defect
  table, physics basis, what the card sends, acceptance criteria, and
  the LATER-PHASE list (measured-vs-sim hourly overlay, synchronized
  breaks, loader-face schedule) so they are not invented ad hoc.
- _norm_plans canonicalises via prediction_pipeline.canonical_area (the
  ONE normaliser) — an alias row ("TOFU>…") used to build a route key
  calibration never saw and price on DEFAULT params, J52-shaped.
- The card caption now renders the server's `note` (self-described
  basis) instead of a hardcoded description — it still said "Jul+
  section speeds, staggered releases" a full model generation later.
  A hardcoded basis caption is densityFit all over again.
- VERIFIED on the real 2026-09-03 save in the browser: 12 paths incl.
  both POS-transit IWIP rows, S1–S4 + BLB spur on official caps, peaks
  207–286 concurrent (v/c 0.17–0.36, 17:00 bin), cadence matches
  pricing (BLB>HUAFEI interval 4.92 h ≈ 4.9 trips/day), phase
  des_segment_model_roundtrip_2shift, clips false.
- plan_scenario.js: ONLY the caption hunk is committed; the co-agent's
  in-flight planWhenScenarioIdle/load-flow work stays uncommitted in
  the tree (partial-stage via checkout-reapply, both copies node-checked).
Suite 74/74.

## 2026-08-23 — five-auditor model QA, then the fixes it ordered

Owner: "quality check for ALL the models, see how they are connected and
whether they work with all physics and real-world laws" → then "fix those
issues." Five auditors probed in parallel, each required to prove every
claim with a measured number and to check BOTH directions of each
doctrine. Full findings + ranked plan: reports/QA_AUDIT_2026-08-23_FIX_PLAN.md.

**What held** (do not re-open without new evidence): anchors exact on all
15 calibrated routes incl. per-contractor transforms; bisection solver
converges, zero monotonicity violations 5..800; tonnage conservation exact
to 0.0 t; segment free-time shares sum to the route total exactly; speed
tables cover 0-68 km with no gap/overlap; J53/J57/availability doctrine
intact; all 13 saves pass DT conservation, walls, the 50/50 split and the
BLB +250 kt to the tonne; backtest R2 0.926 / MAPE 5.8% reproduced.

**Fixed this round:**
- **Rain was a NO-OP on every calibrated route.** physics.py let the
  calibrated speed bypass the rolling-resistance path, so the wet/dry
  ratio was always exactly 1.0 (delta 0.000000 at 25 mm) while
  UNCALIBRATED routes did respond -11.7%. Fixed as a RATIO off the
  existing M&S curve (`rr_speed_ratio`), no new constant; dry proven
  bit-identical (630 configs x 18,270 fields, max delta 0). Owner impact:
  the wet-season saves had rain set and were silently ignoring it —
  2026-10-04 (25 mm) -5.4%, 2026-11-04 (15 mm) -4.7%.
- **Contractor pricing had three owners.** plan.js used the fleet-global
  factor where calibration had no matched-day record (client 2.042 vs
  server 2.363, -13.6%) and even in the WMT->DT ceiling where the exact
  transform existed. `planContractorFactor` is DELETED (not left inert);
  client now matches server <=0.03% everywhere. A reachable target that
  returned "unreachable" now returns 712 DT. **monthly_api.py is the
  third owner and still uses the old factor — BLOCKED, see below.**
- **Hourly DES**: silent 400-truck truncation on a mixed basis (priced at
  the full fleet) -> weighted representative trucks, disclosed; 17.9% of
  truck-hours lost at the shift boundary -> trips in flight complete and
  the tail wraps; ROW ORDER changed the answer (peak -43%) -> uniform
  per-row phase, invariance asserted; executed trips -41%..+35% off the
  priced cadence -> continuous release; v/c divided a STOCK by a FLOW and
  moved 2.5x with the display bin -> flow/flow over a fixed hour, with
  presence reported separately against how many trucks FIT. Card numbers
  change MEANING (cells are now mean concurrent, ~34-52 not ~207-286);
  captions updated in the same commit.
- **BLB joins the stick at chainage 2.45 km** — survey-proven (BLB km
  2.450 sits 0.2 m from mainline CRD km 2.450 on the same datum,
  separating to 87 m by km 2.575; physics.py agrees within ~50 m). BLB was
  wrong in BOTH directions: pinned at 67.8 (TF's chainage) it smeared
  across the whole mainline; deleting it from the stick would under-count
  the tightest section 28%. Truth: 456 trucks on S4, not 562 or 355.
  ONE home: `congestion.segments.SPUR_JOIN_KM`.
- **sections.py migrated to official capacities** — it still divided by
  the median OBSERVED peak, so a normal plan read v/c 1.56-2.09 RED on
  the same screen where the crowding card read 0.17-0.36 (18x apart).
  Now 0.19-0.35. Anchors IMPROVED (max dev 0.2270 -> 0.0140 trips/DT).
  Still visibility-only; `shared_road_ratio` reaches no pricing path.
- **/api/simulate input validation**: -5 trucks produced -258 t, NaN/null
  gave 500s leaking Python text. Now 400s naming the field; every valid
  payload byte-identical. `rain_mm` is first-class (1.0 mm threshold, the
  one the repo already uses in two places) — dwell moves, tonnes do not.
- **`others` self-key asymmetry** closed (model endpoint double-counted a
  route against itself: v/c 0.312 vs 0.193).
- **material-mix returned 503 on an unreachable DB** — the documented
  THIRD MODE defect, a sixth instance. Now prefers its stale cache, then
  the tagged fixture. This is what J56 was failing on.
- **J75 added**: test_plan_shared_flow.py had NEVER been wired to a gate —
  the hourly DES shipped three times with a hand-run test. Mutation-tested
  (7 mutants, each failing exactly its intended assertion).

**Score 75/75** with the VPN connected (owner reconnected and it was
re-run clean end to end). While the DB was down it read 74/75, the single
failure being J70, which asserts `servedFrom=db` — that is the documented
VPN signature, not a defect. D18b flapped again on a restart race and
passes on a direct probe; probe before investigating either.

**BLOCKED on a parallel agent's uncommitted rewrite** (monthly_api.py,
scenario_api.py, export_saturation_curves.py, plan_sensitivity.js) — do
NOT commit their hunks: workbook named S1 actually contains S4 data (Year
total sums ACROSS scenarios, Sep 17% off); two target figures in one S3
workbook (533,180 t phantom); infeasible targets credited as delivered
tonnage; frozen reference curves one recalibration stale (+40.7%);
monthly_api's contractor factor. All are in the fix plan report.

**OWNER DECISIONS PENDING**: (1) the 8 Mt LD clip doctrine reversal that
agent is implementing REVERSES the recorded 2026-08-19 rule; (2)
predictor.py still prices BLB against a 72/hr OBSERVED p95 where geometry
gives 400/hr — same "demonstrated peak read as a limit" defect on the
PRICING path, and correcting it moves prices; (3) the KR corridor's
calibrated road time runs 1.7-3.0x its official speed-limit time.

## 2026-08-23 (later) — the four owner decisions, ruled and implemented

Owner: "fix all these also." All four items from the QA audit are closed.
Report: reports/QA_AUDIT_2026-08-23_FIX_PLAN.md §3.

**1. The 8 Mt LD line — RULED: two labelled numbers, not one.** The two
recorded owner statements were never in conflict; they are about different
quantities. **Capacity is never clipped** (what the fleet could move on LD
is computed and shown in full, above 8 Mt when the trucks are there — the
2026-08-19 rule) and **credited production stops at the supplied target**,
the remainder reported as explicit unused/excess (the learned preference).
Payload gains dt_p3_capacity / dt_p3_unused / ld_t_month_excess /
total.ld_t_excess_capacity; workbooks gain a "LIM-LD capacity vs credited
production" table. Measured S3 Dec: capacity 2,657,340 t, credited
2,034,750 t, excess 622,590 t — all three named on the sheet. Do NOT
re-collapse this to one number.

**2. BLB pricing capacity — the brief's premise was WRONG and the agent
said so.** The 72/hr was never an observed p95 (that is `c_road_obs_p95`
= 34.5, informational). It was `min(c_road, n_loaders x 60/load_min,
c_dump)` — i.e. **the loader wall installed as road capacity**, so BLB's
loader constraint was charged TWICE: once correctly by erlang_c, again as
BPR road delay. Proof: `road_vc == rho` to 3 dp on all 7 BLB routes, so
`bottleneck` was structurally incapable of ever returning "loader".
Fixed: c_link is the official geometry (400/hr spur, reusing
plan_shared_flow's constant), loader/dump ceilings reported separately.
Backtest IMPROVED 0.926 -> 0.927 / MAPE 5.8 -> 5.7. Stick routes move
0.00% at every fleet; BLB inside its observed range max +2.74%; the real
2026-09-03 plan moves +0.40% on ONE path and 0.00% on nine.
`segment_trucks()` now uses `mainline_windows()` so BLB counts onto the
lower stick (S4 419->480 on `dt`, 368->469 on `_allocDt`, the +27.4% that
matches plan_shared_flow's own 28%). `route_segments()` deliberately NOT
widened — it is the "priced on the stick?" predicate; occupancy and
pricing are now separate questions with separate functions.

**3. KR corridor — SETTLED: not a KR defect, and not a distance error.**
`road_free/limit` factors exactly into speed_factor x nonroad_factor.
speed_factor is **1.59-1.86 on EVERY route, KR and TF alike** — trucks
free-flow at ~20 km/h loaded against 30-50 posted, site-wide (38,515
segment-hours). KR>POS 12 stands out only because it has the smallest
denominator and the largest nonroad_factor (1.65). Chainage REJECTED as
the cause by two independent methods agreeing to 0.2%: distance-differenced
WAITING_TIME legs (16.94 km/h) and GPS corridor means (16.9 km/h).
The real finding: **`road_free_min` is a CYCLE minus a flat 8-min ops
term, not road time** — on KR>POS 12 it (110.9) exceeds the entire p10
complete cycle (80 min), and the excess is named in the data as 18.1 min
loading queue + 11.1 min dumping queue, the larger half at the POS 12 TIP,
not the loader. Anchors hold (overhead is fitted on top) so LEVEL is
right; SHAPE is not — BPR multiplies an inflated base and erlang_c adds
queue on top of a base already containing ~29 min of measured queue.
Estimator deliberately NOT changed: it cannot be verified without running
calibration. `physics.free_flow_road_min()` / `road_free_audit()` and a
per-route `road_free_basis` now make it visible instead of buried.
**Why `chainage_suspect` never fired on any route: two errors cancel** —
the numerator is 1.65x high and REF_SPEED 15 km/h is 0.74x low against a
measured 20.3.

**4. The blocked four — unblocked and fixed.** The other agent's files had
been untouched since 2026-08-21 (dormant, not in flight); their work was
backed up and BUILT ON, so those files now carry both authors.
- Workbook labelled S1 contained S4: `day=None` was latest-file-wins.
  Now DEFAULT_SCENARIO_DAY=1 with the source disclosed on the Year sheet,
  in the API and in X-Plan-* headers; day=5/13 404s instead of silently
  borrowing a legacy daily. Year target 20,900,148 (mixed) -> 22,356,095.
- 533,180 t phantom target: a route the scenario does not run now carries
  NO target (its pit x material target is already on the routes the
  waterfall allocated — counting both double-counts). ONE owner,
  `_allocation_target_day`, read by card, sheet and Year total. Oct/Nov
  byte-identical, as required.
- Infeasible targets credited: rows are now cut back in P1->P2 order until
  they fit the pool. SAP x100 stress: Dec 29,187 DT from a 1,281 pool ->
  1,280.8; total.sap_t 576,659,545 -> 37,717,872 credited with the ask
  still visible as sap_t_target and feasible:false.
- monthly_api was the THIRD owner of contractor pricing; `cf` deleted, it
  now calls predict(contractor=) — 14 pairs agree with
  /api/congestion_model to **0.0000%**.
- Found while fixing: `_scenario_draft_paths` sized targeted rows on the
  waterfall DT alone while the P3 LD block landed on the SAME TF>HUAFEI
  key (Sep LIM-TOS delivered 64% of target). Now iterated to a fixed
  point — the same trap `finalTrim` fixed in plan_sap_target.js.

**Reference curves regenerated + J76 added**: the artifact records
provenance (calibration timestamp, network constants AND a digest of
congestion/ model code — data fingerprints alone are insufficient, proved
live when BLB moved under a code-only change), and
`export_saturation_curves.py --check` exits non-zero when stale.
/api/congestion_curve now labels a served reference with
referenceStale/referenceStaleReasons instead of passing it off as current.

**Score 76/76** (D18b flaked once on the post-retrain race and passes on a
direct probe — probe before investigating).

**Still open, owner-sanctioned calibration run needed for both:**
`calibrate_congestion.py:62` gives post-midnight shift-2 trips the
pre-midnight date, so the midnight-crossing gap falls outside the
[20,480] filter — discarding 43.4% of usable gaps on KR>FENI KM0 and
41.6% on TF>POS 12. And the 480-min ceiling censors long TF routes
(TF>HUAFEI road_free is 55% of its measured road time). Fixing both then
re-running calibration would also re-zero the 0.21% BLB anchor drift.

## 2026-08-24 — calibration re-run: the road/overhead split was wrong, now it is right

Owner: "go and fix all." Two estimator defects fixed and calibration
re-run against the live DB. **This is the largest parameter change the
project has made, and it made the model measurably better.**

**A. Night shift crosses midnight; HAULAGE_CLEAN stamps the whole shift
with the PRE-midnight DATE.** `CAST(DATE AS datetime)+CAST(TIME_LOADED…)`
therefore sorted the post-midnight half of shift 2 BEFORE the evening
half, so the LAG measured a gap running backwards and the real
midnight-crossing gap was never formed — it fell outside [20,480] and was
discarded. **23.7% of ALL consecutive gaps site-wide; 41.5% on TF>POS 12,
43.2% on KR>FENI KM0. After the fix: 2.2%.** Loads are now ordered by
time since the shift's own 19:00 start; 19:00 is READ OFF the histogram
(8,558 loads at 19:00 vs 677 at 18:00 — a 12.6x step), not chosen, and
the recovered-gap count is flat for any cut 06:00-19:00.

**B. The 480-min gap ceiling clipped genuine congested cycles.** Raised to
**720 = the 12 h shift length**, justified from the pooled gap histogram
(decays to a floor at 690-719 then flattens into a second population;
every one of the 1,440 gaps above 720 comes from a truck-shift already
spanning >12 h, so none can be a within-shift cycle). t_free stable to
~1% for any ceiling 600-1200.

**The result validates the KR investigation exactly.** `road_free_min` was
a censored cycle, not road time. TF>HUAFEI **208.7 -> 377.8 min**, against
an independently MEASURED free-flow road time of 377.6 — agreement to
0.05%, i.e. nonroad_factor 0.55 -> 1.00, precisely as predicted.
TF>FENI KM15 206.0 -> 285.4 (measured 287.1). Overhead absorbs the
difference (TF>HUAFEI 387.0 -> 218.4), so **every day_rate is unchanged**:
the model's LEVEL was always right, its internal split was not. That split
is what BPR multiplies and what erlang_c's arrival rate depends on, which
is why the shape is now correct.

Measured, all ship criteria passed:
- **Backtest R2 0.927 -> 0.936, MAPE 5.7% -> 5.6%.**
- **Anchors IMPROVED 8x**: max relative deviation 0.2108% -> **0.0268%**,
  and 17 routes anchored vs 15 (the 0.001-0.003 ABSOLUTE figures are
  3-dp output rounding — use the relative measure).
- The 0.21% BLB drift from the 2026-08-23 capacity fix re-zeroed itself,
  as that agent predicted it would.
- Contractor ratios all inside [0.6,1.4], min 35 matched days.
- Monotonicity 0 violations (5-DT sweep, 5..800, three routes).
- TWO NEW calibrated routes recovered by the wrap fix: TF>BSE, TF>FENI KM0.

Owner-visible: at plan-scale fleets (100 DT) almost nothing moves
(0.0-2.1%); at 250 DT the long TF routes rise — **TF>HUAFEI +23.9%,
TF>FENI KM15 +11.9%** — because the old model, believing trucks returned
to the loader far sooner than they do, inflated the loader queue. Curves
regenerated, all 13 plans re-frozen, **76/76**.

**D18b was a FLAKY GATE, not a defect** — it flaked three times in the
same position and passed every direct probe. Cause: `timeout=5` on
urlopen while F23's retrain reloads the model. It asserts canonicalisation,
not latency (D16 owns latency), so it now uses a 60 s timeout with a
bounded retry. A flaky gate is worse than no gate: it teaches people to
wave failures through.

**Still open** (both named by the KR investigation, neither blocking):
`DISTANCE_HAULING` no longer exists in any of the 14 databases, so
`physics.HAUL_KM_SOURCE`'s citations cannot be re-checked; and POS 10's
chainage is the one node where evidence disagrees with NODE_KM (p10 cycle
implies ~21 km vs the stored 17.0, ~1 sigma, so not solid). A geofence
centroid for POS 10 would settle it in minutes.

## 2026-08-24 — HANDOFF TO FOX (or whoever picks this up next)

**Read this first if you are the agent who had uncommitted work here.**
Your changes to monthly_api.py, scenario_api.py, export_saturation_curves.py,
plan_sensitivity.js, planning_rules.md, templates/* and the rest sat
untouched from 2026-08-21 to 2026-08-23 — dormant, not in flight. The owner
authorised finishing the blocked defects that lived in those files, so your
work was **backed up to /tmp/coagent_backup_0823/, built ON TOP OF (never
reverted), and committed in c840db8** with attribution. Nothing was lost;
your SVG restyle, chart-ink change and plan_sensitivity rewrite all shipped.
If you return expecting a dirty tree, that is why it is clean.

### Ground rules that cost us this week
- ONE server on :5055 (PID 69368 today), loopback only. Do not restart it
  while someone else is mid-run — `use_reloader=False`, so your edits do
  NOT affect a running process; verify by importing modules directly.
- Never run `scripts/calibrate_congestion.py` casually: it rewrites
  data/congestion_params.json and invalidates every baseline in flight.
  Back it up first and re-verify anchors + backtest before shipping.
- `git add -A` in a shared tree commits someone else's work. Check
  `git diff --cached` against what you think you wrote.

### Open work, highest value first

1. **POS 10 chainage — the one node where evidence disagrees with the map.**
   `NODE_KM['POS 10'] = 17.0`, but its p10 cycle implies ~21 km (about 1
   sigma, so suggestive, not proof). A geofence centroid for POS 10 from
   `FMS_GEOFENCES` (CENTER_LAT/LNG), snapped to
   data/haul_road_chainage_public.csv, settles it in minutes. If it moves,
   segment overlaps and every POS 10 route's pricing move with it.
2. **`DISTANCE_HAULING` no longer exists in any of the 14 databases.**
   `physics.HAUL_KM_SOURCE` cites it ("p50 6.7 km n=2204", "p50 63.7 km
   n=51") and those citations can no longer be re-checked. Find the
   successor column or re-derive the distances from a source that exists,
   then update the provenance. Do not delete the citations silently.
   Related: BLB>POS 14/15/16 at 6.7 km look SHORT (p10 cycles imply
   9-13 km) while BLB's other four routes reproduce within ~1.5 km.
3. **NODE_KM has two homes.** `congestion/segments.py` retypes
   `physics.NODE_KM` and is missing the POS16 / FENI / POS CBB aliases
   physics has. One home, imported — this repo has paid for duplicate
   constants repeatedly (the 0.85 availability, three shift controls,
   three contractor-pricing owners).
4. **Foreign trucks are priced at the HOST route's tempo**
   (predictor.py ~159-169): segment v/c uses this route's cycle for
   everyone on the window, under-weighting faster foreign fleets ~1.8x.
   Direction is monotone-correct, magnitude approximate. Needs a
   per-route flow term, and a re-anchor check afterwards.
5. **`total_trips` is demand and is never clipped** while tonnage is
   (documented open item). There is still no `achievable_trips` field.
   The only consumer today labels it correctly as demand; the next one
   will not.
6. **IWIP rows are sized without IWIP's own baseline** — `planRulesTripsFor`
   omits `contractor=IWIP` although calibration carries ratio 1.088, so
   IWIP fleets are ~9% over-sized (conservative direction).

### Anything you touch, prove with a number
Every claim in reports/QA_AUDIT_2026-08-23_FIX_PLAN.md carries the probe
that produced it. Keep that bar: a fix that cannot be measured cannot be
verified, and an unverifiable calibration change is what this repo has
been burned by more than once.

## 2026-08-24 — road crowding validated on the WEIGHBRIDGE, then put on page one

Owner: "see if it predicts for a truck the right way, then how many trucks
in a section" — validate per-truck first, per-section second, and only
"put it in the excel file in the first page after we are confident."

**The validation source is tickets, not GPS, and that was the owner's
call.** Haul GPS is too thin to score an hourly corridor (11.6% plate
overlap; re-levelling on it made MAPE *worse*, 48.8% -> 59%). The release
shape was therefore measured from `HAULAGE_CLEAN.TIME_LOADED` — 273,222
loads over 234 days — and the per-segment time split from 463,060 vendor
traversals plus 11,611 haul-truck bin-traversals, two independent sources
agreeing within 6%.

Two real biases were found and fixed in `plan_shared_flow.py` (a4a6a2f):
a flat release profile (real one ramps at shift start and winds down at
shift end, with NO meal-break dip) and a mis-split of road time across
segments. The reshape is a monotone time-warp, so total executed trips
and truck-hours are conserved EXACTLY (verified to 1e-6) — a reshape that
changes the totals is a different plan, not a better clock.

**A third "defect" was measured and REJECTED** (8363505). The apparent
shift-changeover phase lag was a scoring artifact: the reference used a
fitted 1.25 h trailing window, shorter than any real section transit
time, so it was structurally incapable of showing the lag. The real
changeover stand-down (+270 min at the loader) is ALREADY carried by
`overhead_per_trip_min` (dispatch-anchored, +406 min modelled); adding an
explicit term would double-count. Do not "fix" this again without a
reference window longer than the transit time.

### Corridor sits DOWNSTREAM of the plan (owner doctrine)

Once a month's allocation is finalised, the corridor's ONLY job is to
distribute those trucks across sections and hours. It does not re-derive,
second-guess or re-price the plan's tonnage — that was settled upstream.
`_corridor_for_month` in `monthly_api.py` therefore reads the finalised
`data/saved_plans/{date}.json` rows and nothing else.

**Rain is forced to 0 mm** in the export on the owner's instruction:
plans are judged on a normal day (0-1 mm) for now, the rain model stays
ACTIVE for scenarios that need it, and the owner personally fixes any
saved plan whose `rain_mm` is above that. Do not disable the rain path to
"simplify" this, and do not silently rewrite a saved plan's rain value.

### Peak and average are DIFFERENT quantities — both are labelled

The Year sheet's peak is the **bin-free instantaneous maximum**
(`peak_concurrent`); the month tabs' grid cells are the **mean concurrent
within each hour**. Sep TF-KR: 136 against a grid maxing at 133. Both are
correct and the means reconcile exactly (107.9). Caught in self-audit
before shipping, because an unlabelled 3-truck gap between two pages is
read as one of them being wrong — the same failure as the capacity card
and the 0.85 availability. Each table now names its own quantity on its
face. If you add a third view of section occupancy, label it too.

### Gates
`J72` (`scripts/check_scenarios.py`) now asserts every S3/S4 month sheet
carries the hour grid, that the axis really is 07..06 over 24 h, and that
REAL occupancy numbers land — mutation-tested four ways (title-only stub,
wrong axis start, heading removed, and a silently-swallowed engine
failure). The last one matters most: `_corridor_run` deliberately
swallows exceptions so a report never dies on an advisory panel, which is
the 2026-08-21 Cycle Breakdown shape — a graceful fallback that hides a
contract mismatch. The gate is what stops it hiding; it fails 4 checks
loudly when the engine returns nothing.

`scripts/verify_phase2.sh` gained a polling settle-wait after the
retrain-adjacent gates (blocks until 5 consecutive `/api/predict` calls
return under 50 ms, 5-minute deadline, never hard-blocks the suite).
D16/D18b were flaking on a model-reload race; this is the root cause, not
another point patch on D18b.

**Suite note:** `check_assessment_view.py` (J56) is a browser gate and
starves when stale Playwright/Chromium processes accumulate from repeated
runs — 33 were leaked here. It passed standalone every time. `pkill` the
strays before believing a J56 failure, the same way F23/D18b are probed
before investigating.

## 2026-08-25 — following distance 50 m → 75 m

Owner: use **75 m between two DTs** on the GPS packing table and in the
live geometry. `congestion.speed_limits.FOLLOWING_DISTANCE_M = 75`.
Official caps move with the formula (min bin speed × 1000 / gap):

| Segment | Min posted | Cap at 50 m | Cap at 75 m |
|---|---|---|---|
| S1–S3 | 30 km/h | 600/hr | **400/hr** |
| S4 | 20 km/h | 400/hr | **267/hr** |

The packing table and the Plan road-windows table tag v/c GREEN (<0.7) /
YELLOW (0.7–1.0, at the 75 m packing) / RED (over capacity). Do not
hardcode 50 m or 600/hr as the live basis. Regenerate reference curves
after this (`export_saturation_curves.py`).

## 2026-08-25 (later) — following distance 75 m → 60 m

Owner: 75 m packed too few trucks onto each section. Live gap is **60 m
between two DTs on every section**; posted / average speeds stay as on
each stretch. `FOLLOWING_DISTANCE_M = 60`. Caps move with the formula
(min bin speed × 1000 / gap):

| Segment | Min posted | Cap at 75 m | Cap at 60 m | One-lane trucks that fit |
|---|---|---|---|---|
| S1–S3 | 30 km/h | 400/hr | **500/hr** | S1 480 · 12 km 200 |
| S4 | 20 km/h | 267/hr | **333/hr** | 250 |

GREEN / YELLOW / RED stay 0.7 / 1.0 / >1 against these caps. Do not
hardcode 75 m or 400/hr as the live basis. Regenerate reference curves
after this (`export_saturation_curves.py`).

## 2026-08-25 (latest) — following distance 60 m → 50 m

Owner: use **50 m between two DTs** on every section. Posted / average
speeds stay as on each stretch. `FOLLOWING_DISTANCE_M = 50`. Caps move
with the formula (min bin speed × 1000 / gap):

| Segment | Min posted | Cap at 60 m | Cap at 50 m | One-lane trucks that fit |
|---|---|---|---|---|
| S1–S3 | 30 km/h | 500/hr | **600/hr** | S1 576 · 12 km 240 |
| S4 | 20 km/h | 333/hr | **400/hr** | 300 |

GREEN / YELLOW / RED stay 0.7 / 1.0 / >1 against these caps. Do not
hardcode 60 m or 500/hr as the live basis. Regenerate reference curves
after this (`export_saturation_curves.py`).

## 2026-08-25 — crowding occupancy is the loaded lane only

Owner: 600 trucks/hr at 50 m is **one loaded lane**, not both
carriageways. `plan_shared_flow` occupancy / `peak_concurrent` / Plan
grid / Excel Road crowding now count trucks sitting on the loaded lane
only. Empty return sits on the other carriageway (`occupancy_empty` /
`occupancy_both`). Colour stays occupancy ÷ one-lane packing (TF–KR 576).
Mixing both directions with that packing is why Plan S04 sat ~2× the
packing card.

## 2026-08-25 — Excel lists the other-tenant fleets Plan already shows

Owner: New Allocation Plan on screen has MHM / POSITION / PMA / HSM /
KR>RSF / HUAFEI>RSF (1,340 DT, material **other tenant**), but the
xlsx only had production + IWIP POS-transit (blank/`road` material).
Saved `allocation.rows` never stored the register — Plan injects it
live. `_ensure_tenant_rows` now merges `congestion.tenants.tenant_rows()`
into the month Path table and the Year Paths sheet. TOTAL DT stays our
fleet (tenants are 0 WMT, not in TOTAL). `_plans_from_alloc_rows` still
drops them so corridor occupancy is not charged twice.

## 2026-08-25 — packing 600/hr is ONE loaded lane; Plan table said 2×

Owner: Congestion packing card still showed 600 trucks/hr and the Plan
road-windows footnote said crowding was 2× (both sides). 600 is correct:
30 km/h × 1000 / 50 m, one loaded lane. Empty is the other carriageway
(~2× would be 1,200/hr and is not used). The footnote was leftover from
before occupancy switched to loaded-lane only. Caption/column now say
Cap/hr · loaded lane, same geometry as the packing card.


## 2026-08-25 — the three-agent QA audit: eight bugs, eight fixes, six gates

Full evidence: every claim below was measured on the real page with the real
2026-12-04 save before anything was edited (probes in the session record;
gates in `scripts/check_qa_2026_08_25.py`, wired as J81–J86, all
mutation-tested — 7 mutants, and two of them caught weaknesses in the GATE
that were fixed before the code shipped).

1. **Flow readout divided by the Jul GPS "struggle extract" (~54 tph).**
   Peak V/C read 7.13 on the same screen where the crowding grid read 0.90 —
   the "demonstrated peak read as a limit" defect again, THIRD instance
   (sections.py and BLB pricing were the first two). It also still carried the
   legacy POS 10 section split, so it named a bottleneck no other panel has.
   Now: `/api/road_segments` official geometry (600/600/600/400 at 50 m),
   fallback literals pinned to the served caps by J81.
2. **Tenant DT were priced as OUR production.** `planDraftToFlowSeed` had no
   tenant filter, so 4 tenant fleets sharing our TF>FENI KM15 key merged into
   our row: readout quoted 7,265 trips / 340k WMT against the page's own
   3,736 / 182k. Tenants now enter as FLOW at their own tempo
   (`/api/congestion_tenants.segment_flow_hr`), never as trucks at ours; IWIP
   stays on the road but out of production, and the label names both
   exclusions. The trips figure this card shows is the path-response
   ILLUSTRATION on the fleet drawn — Step 2 owns production, and the captions
   now say so on their face.
3. **Check capacity racing a saved-plan load painted a pre-allocation
   shortfall board over an allocated plan** ("add 45 DT", alloc panel hidden).
   A load now counts as in-flight until planRestoreAllocation lands;
   planRunScenario defers and re-runs only if the settled plan is unlocked,
   and freezing retires any stale required-DT board.
4. **Priority board summed two fleets and printed unknowns as zeros.**
   boardHtml passed pre-alloc `r.dt` where `routeDt()` sums allocated
   `workingDt()` — one row claimed 125,450 t (more than its whole route) and
   the total ran 42% over the plan's achievable. And `achv: c.achv||0`
   rendered a never-measured achievable as "OLD ACHIEVABLE 0". One basis now
   (workingDt end to end), null stays null and renders as a dash, and the
   caption names the priorities actually summed (P3 LD rows carry targets —
   "P1+P2 rows only" was false).
   **Mutation lesson: a substring check with TWO call sites passes when one
   regresses.** The gate now asserts the wrong basis is ABSENT, not that the
   right one is present somewhere.
5. **Predicted totals drifted +1.2% across Save → reload → Load** while every
   DT round-tripped exactly: planRestoreAllocation restored the PLAN but not
   the PRICING state (warmed segment curves + seg background; loaders were
   unchanged — measured 91,146 vs saved 90,067, and +0.02% once
   planRulesPrepare() runs). Restore now rebuilds pricing and recomputes.
6. **Strip and crowding grid rank sections by different metrics — both
   real.** Flow v/c (busiest hour of passages ÷ capacity flow) peaked on
   KM15–coast 0.90; lane occupancy (mean concurrent ÷ trucks that fit)
   peaked on POS 12–KM15 0.87. Neither is wrong; each caption now names its
   quantity and cross-references the other's worst section.
7. **Excel TOTAL DT summed our pool + IWIP** (Sep 707 = 581 + 126) against
   the pool figure printed elsewhere on the same sheet, and silently deflated
   Trips/DT (IWIP rows carry DT but 0 trips). TOTAL DT is now our fleet;
   IWIP is a named line under TOTAL (its own fleet, rules §10.8); tenants
   were already separate. Three fleets, three lines, each named.
8. **S4 was unexportable** (`export-full?id=S4` 404, zip had S1+S3 only,
   `/export?ids=` silently ignored) because export listed scenario FILES and
   S4 has none by design (day-04 saves). `_exportable_scenario_ids()` now
   speaks both conventions; the day list is CLOSED (01/03/04) — deriving it
   from whatever days have saves invented phantom scenarios S5/S7/S13 from
   the legacy August dailies, measured before it shipped. A zip that cannot
   build a requested member now says so in a `_MISSING.txt` and the Compare
   workbook carries a "Not in this file" sheet — a member silently missing
   reads as "there was nothing to show".

### Do not mutation-test in a live shared tree

The 7-mutant pass proved the gates but was run by editing the REAL files in
place on the shared checkout while the shared :5055 server was restarted
around it. Another agent's S4 refreeze was live in the same minutes: its
browser was served a MUTATED plan_sap_target.js (the 200 vs 304 in the server
log is the tell), and one of its passes died on my restart
(ERR_CONNECTION_REFUSED, 2026-11-04 FAILED, later retried). The saves it
wrote verified internally complete, and the plausible mutant effects were
display-only — but that is luck, not design. Mutation-test in a worktree
(`git worktree add`), or at minimum against a private server port, never
against the checkout and server other agents are using.

### The refrozen S4 saves are the POS 6 rework — do not "restore" them

data/saved_plans/2026-{09..12}-04.json were rewritten 2026-08-25 ~17:00–17:06
by the parallel agent moving the P3 50/50 split leg from TF>POS 12 to
TF>POS 6 (splitDest, planning_rules §4). Backups of the older POS 12-split
files from earlier that day are NOT the newer truth. If the numbers need
re-deriving, re-run that agent's refreeze on a quiet tree — do not copy old
JSON over new.

## 2026-08-26 — weighbridge auto-allocation: base points measured, matrix enforced

Owner supplied a 13-bridge x 18-pair eligibility matrix and asked for
automatic bridge allocation grounded in the whole ticket history. Analysis
first (reports/WB_ALLOCATION_ANALYSIS.md, gitignored — DB-derived), then four
owner rulings, then the build. Gate J87, mutation-tested 6/6 in an ISOLATED
WORKTREE on :5056 — the shared checkout and :5055 were never touched.

**Identity is the matrix NAME, never the ticket number.** Ticket WB_IDs are
bare numbers and `WB_RIM_T7` / `WB_IWIP_T7A` both stamp "7" — two physical
bridges 12 km apart (BLB spur km 7.9 vs mainline km 10.0), disambiguated by
geofence position + the matrix's rows. Anything keying bridges on the number
alone will merge them.

**The FENI letters are furnace lines split across TWO plants — the
canonicaliser was wrong for six of them.** Bridge geography proved it: lines
T/U/U1/U2/W/X (~98k tickets) are weighed at WB12/WB17, the bridges AT km 15,
while A..S are weighed at the km 0–10 bridges. `canonical_area` used to map
every FENI letter to FENI KM0, so weighbridge-by-path returned EMPTY for all
KM15 routes. Owner-confirmed; the mapping now lives in the ONE normaliser and
check_vocab's self-test pins it (its old expectations asserted the belief,
not a fact). NOT yet re-checked: whether HAULAGE_CLEAN (the dispatch table
the trips model trains on) ever uses FENI-letter names — run that when the
VPN returns before assuming the model is unaffected.

**The allocator** (`/api/plan/wb-allocate` + basis endpoint; register
data/wb_register.json gitignored, fixture wb-allocation-basis.json
committed): min-max utilisation water-fill over each row's eligible set at
measured p99/hr capacities (26–91/hr — the flat 30/hr overstated small
bridges and understated big ones up to ~3x). Owner rulings enforced and
gated: pit rows = matrix only; **T11 never** (the busiest bridge in history,
84k tickets, deliberately excluded — its absence from the register is the
load-bearing wall, `excluded_nums` is the second layer); tenants never; IWIP
POS-transit rows = measured history minus exclusions, with a
geography-guarded destination fallback (a non-BLB row never lands on a
BLB-spur bridge, and fallback bridges must sit on the route's chainage span —
the first live run put POS 6 trucks over a spur they never drive);
WB_IWIP_T2 used as the matrix writes it but flagged unverified (1 lifetime
ticket, no geofence — possibly WB_RIM_T2).

**Client**: the existing plan_weighbridges.js panel stays the ONE display
pipeline — auto-assign sets its chip selections and per-path shares from the
server response, and bridgeUtil now prices each bridge at its own measured
cap. Two traps found live: (1) pathTrips prices through planTripsPerDT whose
curves are async — auto-assign fired straight after a load posted "no trips"
for every pit row; it now awaits planRulesPrepare when a trucked row prices
to zero. (2) IWIP POS-transit rows had NO rate on the row (their routes are
outside the path model), so their bridge demand silently vanished —
`_transitTripsPerDt` now rides on the row and round-trips through saves.

**Mutation lessons, again:** the worktree runner's pkill pattern matched
nothing (cwd is not in argv), so the first pass "tested" six mutants against
the original server and reported 0/6 caught — kill by PORT. And two mutants
exposed gate weaknesses (a defence-in-depth layer that made one mutant
unreachable; a check reading the basis where the allocator's own response
was the thing to assert). A mutation harness is itself code that can lie.

## 2026-08-26 — road crowding: two clocks on one lane, and the constant that hid every plan

Owner: the crowding table "looks the same numbers" across plans when real
plans should differ. Two distinct causes, both measured before touching code:

**1. Tenant presence rode the RAW LIMIT clock while our trucks rode the
measured one.** plan_shared_flow converted tenant flow to trucks-present with
`span_times_min` (official limit transit) while our own trucks sit on each
section for the CALIBRATED congested road time split by corrected limit
shares — implied per-pass transit ours 1.71 h vs tenants 0.86 h on the SAME
S1 lane (the "two 240s" family, again). The tenant floor was under-counted
~2x on S1–S3. Fixed with the run's OWN clock: stretch = our loaded
truck-hours ÷ (our weighted loaded passes × limit time) per section — no new
constant, tenants slow down exactly when the plan's traffic does, and
sections our fleet does not cross keep the limit clock, disclosed per tenant
row. entry_times carries (t, weight) — SUM THE WEIGHTS, len() undercounts
representative-truck runs. Gate: test_plan_shared_flow "one clock" checks,
BOTH directions (transits agree ours-vs-tenants; and ≥1 section deviates
>20% from the raw limit — the revert mutant fails exactly there,
mutation-tested in an isolated worktree).

**2. The tenant background is a CONSTANT ~50–80% of every mainline cell**, so
plan changes moved the display by only ~10–25% even when the fleet doubled
(608 → 1274 DT moved TF–KR only 218→275 pre-fix). Cells stay TOTALS —
capacity is consumed by totals — but every surface now names the split: the
Plan grid row reads "301 tenant const + 141 ours", the verdict says "273 of
the peak 337 trucks are OTHER TENANTS — only [yours] moves when the plan
does", and the Excel grid carries the same line. J79 parity re-verified
(22 scenarios, cell-by-cell) — the DES change moves BOTH surfaces equally.

**Owner-visible consequence, honestly labelled:** at the register's stated
tenant volumes on the measured clock, POS 12–KM15 reads OVER one-lane
packing (ratio 1.27–1.41, ~80% tenants) on every current plan. Either the
register overstates the RSF/KM15 tenant fleets or that section genuinely
runs beyond 50 m packing — a question for the owner, not for the model to
quietly resolve either way.

## 2026-08-27 — the priority-rule audit: scenarios pass, S1's targets do not fit

Owner asked for the check: SAP 100%, LIM-TOS 100%, LIM-LD may miss. Audited
every frozen save at bucket AND row level.

**Scenario plans (S3/S4/S5/S6 × Sep–Dec): all pass.** SAP 99.9–101.7%, TOS
99.8–101.0% (the sub-100 readings are one-truck quantization inside the
0.995 band), LD OVER target everywhere (102–141%). Per-row P1/P2: zero real
violations — rows that read short are covered by cross-contractor rescue
helper rows (targetWmt 0), which the row percentage does not attribute back.

**Three S1 freezes were STALE and were re-drafted + re-frozen (2026-08-27):**
the planning team's matrix update changed targets under them, and Nov S1 was
worse — frozen 2026-08-24 on OCTOBER's pool (931 DT of November's 1,280;
349 trucks simply absent from the plan). Backups in /tmp/backup_2026-*.json.
A refreeze does NOT pick up new matrix targets or pools by itself: the
allocator re-divides the LOADED plan. Re-draft first
(POST /api/scenarios/S1/draft-plans {months, overwrite}), then freeze.

**Against the CURRENT matrix, S1 is structurally infeasible** — not an
allocator bug, and re-verified at row level:
  Sep TOS 81.9% · Oct TOS 90.7% · Nov SAP 96.1% / TOS 85.9%.
The deficits sit exactly where the walls pin them: KR-origin rows are
SMA-only, SMA's pool exhausts (P1 first, correctly), and RIM's 380-470
surplus LD trucks may not cross into KR. KR>FENI KM15 also runs past its
observed envelope (60 DT vs dtMax 55), so the remaining idle SMA trucks buy
nothing there — the "target above path ceiling" case, honestly reported.
This is the quantified version of the recorded S1 story ("September at
literally zero free DT"); the 3.x scenario family exists precisely to move
that tonnage across months.

**Dec S1 not touched**: its SAP target is 5,000 t/day stale too, but the
parallel agent is actively reworking December S1 (idle-pool options sheet,
three commits 2026-08-27) — folding the re-draft into their pass avoids
re-freezing under them. Flagged here for whoever lands first.
