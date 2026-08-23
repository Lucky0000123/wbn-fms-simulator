# Model QA audit — findings and fix plan of record

Owner (2026-08-22): *"quality check for all of the models we make in our app,
see how they are connected and that they work as we need with all physics and
real-world laws"* — then: *"plan to fix those issues."*

Five independent auditors probed the app in parallel, each required to prove
every claim with a measured number rather than code reading. This is the
consolidated result and the fix plan. Status per item is marked; nothing here
is speculative.

## 1. What passed (the load-bearing verifications)

These were probed hard and hold. They are recorded so no future round re-opens
them without new evidence:

- **Anchors exact.** `predict()` at every calibrated route's reference fleet
  reproduces its dispatch day-rate on all 15 routes (max deviation 0.001),
  including per-contractor transforms.
- **Solver sound.** Bisection converges to ~8.8e-13 min; 5-DT monotonicity
  sweeps 5→800 on three routes: zero violations.
- **Conservation.** `/api/simulate` multi-path totals equal the sum of parts to
  0.0 t; split-vs-combined differs by 1 t (rounding). DES shared sections are
  bin-wise EXACTLY the sum of solo runs (max |diff| 0 across 24 bins).
- **Time conservation.** Segment free-time shares sum to the route total
  exactly (208.700000 on TF>HUAFEI) — no time created or lost in the split.
- **Speed-limit tables.** Both directional tables cover 0–68 km with no gaps or
  overlaps (Σ = 68.000 each); independent re-integration reproduces every
  segment capacity and limit time.
- **Doctrine.** Congestion never clips simulate tonnes (`congestion_clips_tonnes`
  false everywhere, zero `True` in the repo); availability 0.85 ignored and
  echoed; the two clocks are never averaged in any API or UI surface.
- **Allocation invariants, all 13 saved plans.** Per-contractor DT conservation
  exact; contractor walls clean in both directions; every active row carries a
  finite raw achievable; S4 TF-LD split measured 49.7–50.2%; BLB +250 kt/month
  present in all eight S3/S4 saves and S3.json, exact to the tonne.
- **Backtest reproduced to the digit**: R² 0.926 / MAPE 5.8%.
- **Client transform is bit-faithful to the server** where calibration exists
  (0.0% deviation), and the hourly DES reproduces the pricing model's cadence
  to three decimals.

## 2. Defects, ranked — fix plan

Severity is by owner impact, not by code depth.

### Tier 1 — the app states a wrong number to the owner

| # | Defect | Measured | Status |
|---|--------|----------|--------|
| T1.1 | **Exported workbook named for S1 actually contains S4 data**; the Year total sums ACROSS scenarios. `_find_saved_allocation(month, None)` is latest-date-wins, so Sep–Dec resolve to day-04 and Aug to a legacy daily plan. | Sep target 2,410,410 (S4) vs the real S1 2,908,590 — **17% apart**, no disclosure on the Year sheet | **BLOCKED** — `monthly_api.py`/`scenario_api.py` are mid-rewrite by a parallel agent |
| T1.2 | **Two target figures inside one S3 workbook.** Card target vs sheet target diverge on routes the scenario zeroes out (orphan rows with target>0, dt_after=0). | Sep +15.6%, Dec +2.7%, **533,180 t phantom target**; drags Sep "Optimized %" 81.5 → 70.5 | **BLOCKED** — same files |
| T1.3 | **SMA rows under-priced ~25%** in every frozen plan: the frontend falls back to the legacy fleet-global contractor factor where calibration has no matched-day record, while the backend prices pooled. The factor's sign is inverted on TF by our own matched-day evidence. | client SMA 2.042 vs backend 2.363 (−13.6%); frozen SMA rows −25.5% vs every backend engine | **ASSIGNED** |
| T1.4 | **Red v/c on a road the physics says is 20% utilised.** The "Road windows" table still uses observed-peak capacities (40–66/hr) while the crowding card uses official capacities — same sections, **18× apart**. | windows v/c 1.56–2.09 vs card 0.17–0.36 | **ASSIGNED** |

### Tier 2 — the simulation misrepresents the road

| # | Defect | Measured | Status |
|---|--------|----------|--------|
| T2.1 | **Silent truncation with a mixed basis** in the hourly DES: 400-truck cap, full fleet echoed, and pricing done at the full fleet while the road carries 400. | 5000 DT → 400 simulated; meter advice derived from a 92%-truncated run | **ASSIGNED** |
| T2.2 | **Row order changes the answer.** Truck release slots are assigned by cumulative index across rows. | peak 394 → 226 (**−43%**) on a row swap; +11.4% truck-hours on the real plan | **ASSIGNED** |
| T2.3 | **17.9% of road truck-hours vanish** at the shift boundary; 4.4% of trips dropped outright. | one path −58.0%, another 0.0% on the same route | **ASSIGNED** |
| T2.4 | **Executed trips ≠ priced cadence**, −41% to +35%; the `max(1,…)` floor credits a trip to trucks that cannot finish one in a shift. | 10 of 12 paths >10% off | **ASSIGNED** |
| T2.5 | **v/c not bin-invariant** and compares a STOCK (trucks present) against a FLOW (trucks that can pass) — a units error. | 0.059 at 1 h vs 0.150 at 0.25 h on identical traffic | **ASSIGNED** |
| T2.6 | **Rain is a no-op on every calibrated route** — the calibrated speed bypasses the rolling-resistance path, so the wet/dry ratio is always 1.0. Uncalibrated routes DO respond, so behaviour is inconsistent. The UI advertises a control that does nothing. | Δtrips and Δcycle **0.000000** at 25 mm; uncalibrated route −11.7% | **ASSIGNED** |

### Tier 3 — robustness and hygiene

| # | Defect | Status |
|---|--------|--------|
| T3.1 | `/api/simulate` input validation: `n_trucks:-5` → −258 t; NaN/null → HTTP 500 leaking Python messages; silent coercions | **ASSIGNED** |
| T3.2 | `rain_mm` silently ignored by `/api/simulate` (keys on `weather` only) | **ASSIGNED** |
| T3.3 | `others` contract asymmetric: the curve endpoint pops the self key, the model endpoint does not (doubles reported v/c) | **ASSIGNED** |
| T3.4 | `erlang_c` returns `lq: nan` on the overloaded branch (no consumer today) | **ASSIGNED** |
| T3.5 | `/api/congestion_plan` carries no doctrine flags unlike its siblings | **ASSIGNED** |
| T3.6 | **Frozen reference curves one recalibration stale** — served in fixtures/fresh-clone mode, up to **+40.7%** below live on TF>HUAFEI | **BLOCKED** — export script mid-rewrite by a parallel agent |
| T3.7 | Infeasible targets credited as delivered tonnage (29,187 DT allocated from a 1,281-DT pool; 83× overstatement). Latent — real scenarios have zero deficits | **BLOCKED** — `scenario_api.py` |
| T3.8 | Dead code: `planRenderOutcomes` unreachable but still invoked (each call does a full reprice); fossil `PLAN_NODE_KM`/`PLAN_SECTIONS` still carrying the BLB=67.8 bug | **BLOCKED** — `plan_scenario.js` |
| T3.9 | `chainage_suspect` flags nothing (0 of 20) — the check that was built to catch the TF distance disagreement is exempted by its own `measured` clause | **BACKLOG** |
| T3.10 | Foreign trucks priced at the host route's tempo (~1.8× under-weighted); direction correct, magnitude approximate | **BACKLOG** |
| T3.11 | IWIP sizing ignores IWIP's own calibrated baseline (~9% oversize, conservative direction) | **BACKLOG** |

## 3. Needs an owner decision

1. **The 8 Mt LD clip.** A parallel agent is implementing "capacity beyond
   target is not credited as production" in `scenario_api.py` — this REVERSES
   the recorded 2026-08-19 rule ("LIM-LD has no cap; every free truck hauls
   LD"). Both cannot be true. This changes headline LD tonnage in every
   scenario.
2. **Re-freezing the 13 saved plans** after the SMA pricing fix. SMA-row
   predictions rise ~25% when the legacy factor is removed; the frozen saves
   currently carry the low numbers.
3. **KR corridor geometry.** The dispatch-anchored road time runs **1.7–3.0×**
   the official speed-limit time (KR>POS 12: 110.9 min vs 36.5; 11.7 km/h
   implied against a 30 km/h minimum limit). Either the anchor absorbs
   substantial non-road time, or the distance is wrong. TF agrees within 14%,
   so this is specific to KR. Needs the site's answer, not a guess.
4. **Where the BLB spur joins the stick.** BLB routes currently touch no
   mainline segment at all, so BLB trucks are absent from the tightest section
   (61 DT excluded in the Sep plan). Fixing it changes BLB's shared congestion.
   Requires evidence, not an assumed chainage.

## 4. Coordination hazard (recorded)

`plan_sap_target.js` at HEAD calls `window.planWhenScenarioIdle`, which exists
only in a parallel agent's UNCOMMITTED `plan_scenario.js`. On any fresh
checkout the allocate settle-waits silently no-op behind their `typeof` guards.
Those two files must be committed together.

## 5. Method note (why this audit is trustworthy)

Each auditor was required to produce a measured number for every claim, to
probe BOTH directions of each doctrine (a gate that only asserts "warning
fires" is passed by hardcoding it; one that only asserts "no warning" is passed
by deleting the feature), and to say plainly when something passed. Three
findings were caught only by feeding identical inputs through all six engines
at once — no single-model audit could have seen them.
