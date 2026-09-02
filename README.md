# WBN Production Simulator

> **New agent or new contributor?** Start with
> [reports/HANDOVER.md](reports/HANDOVER.md) — full project handover:
> setup, database, file tree, engine internals, gates, known traps.
>
> **Another PC / local install?** Start with [LOCAL_SETUP.md](LOCAL_SETUP.md).
> Clone from GitHub, `python serve.py`, open `http://127.0.0.1:5055/simulator`.

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
| How many tonnes will this plan move? | **Yes** — from a measured per-route effective cycle; no availability guess needed |
| Where do two plans collide? | **Yes** — measured capacity at shared points |
| How many trucks must I roster to keep N hauling? | **Yes** — measured availability, per route where it exists |
| Will adding trucks slow the cycle? | **No** — measurable but negligible (−4.8% at the density extremes) |
| How fast on each road segment? | **Not yet** — GPS retention does not reach the training period |

The two "no" answers are load-bearing, not caveats.

**Two cycle figures, deliberately.** `predicted_cycle_time_min` is the
weigh-to-weigh interval a planner recognises as trip time.
`effective_cycle_min` is shift-minutes per completed trip, measured per route,
and is what trips-per-shift divides by — it also covers the empty return, the
shovel queue and breaks. An earlier version divided by the former and
**overpredicted production by ~2.7x**; see
[reports/CRITICAL_cycle_time_defect.md](reports/CRITICAL_cycle_time_defect.md).

**Fleet sizing.** `/api/simulate` returns `trucks_to_roster` per plan, so 30
hauling trucks on BLB → FENI KM0 needs 39 rostered. Availability is measured from
170,899 haul-truck shifts and is deliberately **not** applied to tonnage: the
effective cycle already contains downtime, and every availability factor tested
made the bias worse (+5.5% → −10.3% at 0.850). It is measured for trucks carrying
only 30.3% of training tonnage, so each plan reports `roster_basis` as `measured`
or `fleet_prior` rather than quietly extrapolating. See
[reports/availability_analysis.md](reports/availability_analysis.md).

**Congestion, now measured directly.** The site's own `FMS_CONGESTION_SEG` gives
36,046 hourly rows with speed *and* truck count per segment. The within-segment
effect is real, correctly signed and significant (**−0.0233 km/h per extra truck,
t=−9.9, n=35,006**) and **negligible**: speed falls 4.8% from the emptiest density
decile to the busiest, with no saturation threshold up to 69 trucks on a segment.
At trip level the effect has the *wrong* sign (−0.1467) because dispatch sends
trucks to routes that are running well. See
[reports/gps_scaling_and_speed_density.md](reports/gps_scaling_and_speed_density.md).

**Congestion (earlier evidence).** Four independent tests failed to find a queueing effect, and
measured delay *falls* as loader utilisation rises, because trucks get deployed
to points that are running well. A model fitted anyway scores a **higher** R2
(0.4925 vs 0.4792) and was withheld, because its coefficient says adding trucks
makes trips faster. Contention is reported as measured capacity headroom instead.

**GPS.** An earlier version of this README said no haul truck was
GPS-instrumented. **That was wrong** — it checked one table and generalised, and
the site operator was right to challenge it. A full scan of both databases found
945 of 1,411 registered plates matching weighbridge haul trucks, 479 reporting
at 3-second resolution, and 95 KM road segments with measured speed already
aggregated in `FMS_CONGESTION_SEG`.

### Banking the GPS feed forward (do this once)

Retention deletes segment speeds within days, so **the record only grows if
something appends it**. `scripts/accumulate_gps.py` does that and is idempotent —
re-runs add nothing, so it is safe to schedule and safe to run after a gap.

```bash
# what is banked right now (needs no VPN)
python scripts/accumulate_gps.py --status

# append anything new; run daily while the VPN is up
python scripts/accumulate_gps.py
```

To schedule it on the machine that has VPN access, add one crontab line:

```
0 7,19 * * *  cd /path/to/wbn-fms-simulator && .venv/bin/python scripts/accumulate_gps.py >> /tmp/gps_accum.log 2>&1
```

Twice daily is deliberate: `FMS_PLAYBACK_TRACK_24H` keeps about one day, so a
single missed run can lose a shift. Every day this is not running is a day of
segment speeds gone permanently — unlike every other gap in this project, this one
cannot be fixed later.

The real blocker is **retention**, now quantified precisely: only **4 calendar
days** carry both GPS and haulage, and pooling all of them yields 19 segment
observations with no segment/direction cell reaching n≥5. The richest GPS day in
the database (859,198 fixes) is unusable because its only haulage rows are 46
third-party SALES trucks, which carry no telematics. The plate join itself is
fine — 65.5% of GPS plates exist in the haulage ID space — so this is temporal,
not a namespace mismatch. Segment speeds are available to a forward-looking
build, not retro-fittable to past trips. Full evidence in
[reports/database_schema_analysis.md](reports/database_schema_analysis.md) and
[reports/gps_scaling_and_speed_density.md](reports/gps_scaling_and_speed_density.md).

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

**Run it on another PC yourself:** [LOCAL_SETUP.md](LOCAL_SETUP.md).

Both remotes carry the same `main`. Clone either:

```bash
git clone https://github.com/Lucky0000123/wbn-fms-simulator.git
# or
git clone https://github.com/rdinkelmann/wbn-fms-simulator.git
```

The old Rudolf-Mac-only pull (`/Users/rdinkelmann/simulator-standalone` + launchd + ngrok) is a different machine. Do not treat that as the local-install path.

Only commit the files changed for the simulator task. Credentials, `.env`, and `data/saved_plans/` stay off git.

## Files

| File | Edit this for… |
|---|---|
| `templates/simulator.html` | the page — layout, charts, styling, interactions |
| `simulator_api.py` | the calculations behind the data |

Commit and push your changes when done.
