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
bash scripts/verify_phase2.sh                   # must stay 24/24
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
