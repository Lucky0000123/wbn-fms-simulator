# WBN Production Simulator

Predicts haul-truck productivity for mine plans at the WBN nickel operation, Halmahera.

A planner asks **"30 trucks from A to B, 20 from C to D"**. The simulator returns
trip time, loading and dumping time, trips per shift and tonnes per route, and
flags where two plans contend for the same loading or dumping point.

It runs from committed lookup tables, so it answers identically with or without
the database: the public demo does not go down when the VPN does.

## What it can and cannot tell you

| Question | Answer |
|---|---|
| How long is a trip on this route? | **Yes** — measured route history |
| How long at the loader and the tip? | **Yes** — measured on 24.8% of trips, apportioned otherwise |
| How many tonnes will this plan move? | **Yes** — derived, with an assumed availability you set |
| Where do two plans collide? | **Yes** — measured capacity at shared points |
| Will adding trucks slow the cycle? | **No** — not identifiable from weighbridge data |
| How fast on each road segment? | **No** — needs GPS on haul trucks; none are instrumented |

The two "no" answers are load-bearing, not caveats.

**Congestion.** Four independent tests failed to find a queueing effect, and
measured delay *falls* as loader utilisation rises, because trucks get deployed
to points that are running well. A model fitted anyway scores a **higher** R2
(0.4925 vs 0.4792) and was withheld, because its coefficient says adding trucks
makes trips faster. Contention is reported as measured capacity headroom instead.

**GPS.** 0 of 940 registered haul trucks appear in the telematics feed. The 217
instrumented units are engineering and logistics vehicles. No fuzzy timestamp
match was attempted, because it would have put invented speeds into the tool.

## Model findings

**[MODEL_FINDINGS.md](MODEL_FINDINGS.md)** — the evidence for all of the above:
walk-forward cross-validation, the coefficient sign audit that withheld the
higher-scoring model, measured point capacities, and the approaches that were
tried and rejected.

Regenerate with:

```
python trip_features.py      # features from the trip extract + WAITING_TIME
python simulator_model.py    # cycle-time models + the congestion sign audit
python capacity_model.py     # measured point capacity + congestion re-test
python dwell_models.py       # loading and dumping dwell
```

## Plan simulator API

`POST /api/simulate`

```json
{"plans": [{"route": "TF>POS 12", "source": "TF",
            "destination": "POS 12", "n_trucks": 30}],
 "weather": "dry", "shift_minutes": 720, "availability": 0.85}
```

Every result carries a `basis` block saying whether each number is measured,
derived or assumed, and a `model_limits` block stating what the simulator does
not claim. `GET /api/simulate/options` lists the routes and points with history.

Tests: `python test_plan_simulator.py` (33 invariants) and
`python test_congestion_audit_mutation.py` (mutation-tests the sign gate).

## Public simulator

**https://wbn-fms-simulator.ngrok-free.app/simulator**

Health check: **https://wbn-fms-simulator.ngrok-free.app/health**

## Run locally

```bash
pip install flask
python serve.py
```

Open **http://127.0.0.1:5055/simulator**

Keep that terminal running while you work; use a second terminal for git.

It runs on **sample data** out of the box—no setup or database required.

## Publish with ngrok

The public endpoint forwards to the local simulator on port `5055`:

```bash
ngrok http 5055 --url=https://wbn-fms-simulator.ngrok-free.app
```

The Mac deployment uses two launch agents:

- `com.wbn.simulator` — keeps `serve.py` running on port 5055.
- `com.wbn.simulator.ngrok` — keeps the public ngrok endpoint connected.

Useful checks:

```bash
curl -I http://127.0.0.1:5055/simulator
curl https://wbn-fms-simulator.ngrok-free.app/health
```

## Git deployment

```bash
cd /Users/rdinkelmann/simulator-standalone
git pull --ff-only origin main
git status
git add serve.py simulator_api.py templates fixtures README.md requirements.txt
git commit -m "Describe the simulator change"
git push origin main
launchctl kickstart -k gui/$(id -u)/com.wbn.simulator
```

Only commit the files changed for the simulator task. The launch agents and ngrok credentials remain
local to the Mac and are not stored in Git.

## Files

| File | Edit this for… |
|---|---|
| `templates/simulator.html` | the page — layout, charts, styling, interactions |
| `simulator_api.py` | the calculations behind the data |

Commit and push your changes when done.
