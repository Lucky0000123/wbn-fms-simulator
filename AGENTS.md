# AGENTS.md — working rules for this repo

Applies to every agent and contributor working in this checkout.

## Push to BOTH remotes, always

This repo has two remotes and **every commit must reach both**:

| Remote   | URL                                                | Notes                  |
|----------|----------------------------------------------------|------------------------|
| `origin` | `github.com/rdinkelmann/wbn-fms-simulator`         | upstream, private      |
| `mirror` | `github.com/Lucky0000123/wbn-fms-simulator`        | user's copy, public    |

A convenience remote `all` is configured to push to both in one command:

```bash
git push all <branch>          # → origin AND mirror
```

Verify both landed on the same SHA before reporting success:

```bash
for r in origin mirror; do echo "$r: $(git ls-remote --heads $r <branch>)"; done
git rev-parse HEAD
```

Never push to only one remote. If a push to either fails, say so explicitly
rather than reporting partial success as done.

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
bash scripts/verify_phase2.sh                   # must stay all-pass (39/39 here; see note below)
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

**Denominator moves with what you have trained**, so read the score with that
in mind. Measured, not assumed:

| State | Score |
|---|---|
| Fresh clone, nothing trained | 24/33 — the A/B checks need `data/` artifacts |
| After `python train_model.py`, no VPN | 32/33 (33/33 with remotes configured) |
| Full: cycle model trained too | 39/39 |

`data/` is gitignored (real tonnages, public mirror), so a clone starts with no
artifacts and the extraction checks fail until you train once. That is the
harness working, not a regression. The Phase 3.5 block skips entirely when
`data/cycle_model_report.json` is absent.
