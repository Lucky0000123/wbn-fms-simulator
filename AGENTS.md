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
