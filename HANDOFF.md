# WBN FMS Simulator — Project Handoff (updated 2026-08-21)

> **Parallel work protocol**: multiple agents work this repo concurrently.
> 1. git pull BEFORE starting; commit small and often; push to BOTH remotes
>    (git push origin main && git push mirror main).
> 2. Run bash scripts/verify_phase2.sh (73 gates) before AND after your work.
>    A transient J56/J70/J64 failure usually means the site VPN/DB dropped -
>    re-run before investigating.
> 3. Never edit another agent's in-flight files without pulling first; check
>    git log --oneline -5 for surprises. AGENTS.md is the shared memory -
>    append lessons there, never delete.
> 4. The dev server on :5055 is shared state. Snapshots warm from disk.
>    After changing congestion params, RESTART the server (long-running
>    processes hold stale route params past the 60 s config cache).

Written for onboarding another agent. Everything below is verifiable in the
repo; AGENTS.md is the deep memory file (read it first, it is authoritative).

## 1. What this project is

A Flask + vanilla-JS web app that plans and simulates nickel-ore haulage for
the WBN mine site (Indonesia): TF/TOFU, BLB, KRENE pits → FENI KM0/KM15,
POS 12/14/16, HUAFEI dump. It predicts daily tonnage from measured truck
history, simulates achievable tonnage against loader/point capacity, allocates
dump trucks (DT) by material priority, rolls plans up to monthly/yearly
management reports, and renders GPS road-corridor crowding.

Two contractors: RIM and SMA. Hard rule: **BLB pit accepts RIM trucks only.**
Priorities: **P1 SAP → P2 LIM-TOS → P3 LIM-LD** (Tofu limonite dump → Huafei,
the leftover-truck sink, uncapped; 8,000,000 t is a sales *target line*).

## 2. Where everything lives

### Code (GitHub, both up to date at the same commit)
- **origin**: https://github.com/rdinkelmann/wbn-fms-simulator.git (Rudolf)
- **mirror**: https://github.com/Lucky0000123/wbn-fms-simulator.git (Lucky — yours)
- remote `all` pushes to both at once: `git push all main`
- NOTE (AGENTS.md): origin was historically frozen; the mirror is the branch
  of record. Both currently match local HEAD.

### Local working copy
- Repo root: `/Users/lucky/wbn-fms-simulator`
- Python venv: `.venv/` (Python 3.14; run everything with `.venv/bin/python`)
- Server: `python serve.py` → **http://127.0.0.1:5055** (pages: `/simulator`,
  `/monthly`; health: `/health`)

### Local data (gitignored, NOT on GitHub — back these up separately)
- `data/saved_plans/YYYY-MM-DD.json` — Plan-tab saved daily plans **with
  frozen Allocate-DT snapshots**. Scenario convention: **day 01 = S1,
  day 03 = S3, day 04 = S4** of each month (day 02 held S2 until it was
  deleted from the app on 2026-08-21, owner request; a copy sits in
  `data/saved_plans/_deleted_s2_backup_2026-08-21/`). S4 (owner,
  2026-08-21) = S3 with the leftover LD trucks split 50/50 HUAFEI/BSE vs
  POS 12 (`planning_rules.md` §4 P3); the allocator applies the split
  automatically on any day-04 plan date. Current inventory:
  Aug: 01 (S1 only, by owner request), plus legacy 04/05/07/13 — the
  Aug 04 file PREDATES the S4 convention and is a plain daily plan.
  Sep–Dec: 01/03/04 each.
- `data/monthly_plans/` — month states (2026-08…2026-12.json) +
  `yearly_matrix.json` (the pasted mine-plan matrix = S1 targets + DT pools).
- `data/gps_archive/` — accumulated haul GPS (cron 07:00/19:00 via
  `scripts/accumulate_gps.py`). Haul GPS exists only from **2026-07-15**.
- `data/*.pkl`, `data/*.csv` — trained models + extracts (regenerate:
  `python train_model.py` or POST `/api/retrain`).
- `data/cap_snapshot.json`, `data/pr_snapshot.json` — disk snapshots of
  dispatch payloads (regenerate on warm).
- `.env` — DB credentials (WBN_DATABASE = ops truth, FMS_DB = GPS/location).
  Copied from LUCKY_SSD via `scripts/sync_creds_from_ssd.sh`. NEVER commit.

### Committed data (in the repo)
- `data/scenarios/S3.json` — imported scenario targets (S2.json deleted
  2026-08-21 with the rest of S2; backup beside the saved plans above).
- `fixtures/` — offline API payload snapshots (app runs without the DB).
- `data/haul_road_chainage*.csv` — the committed road centreline (J63).

## 3. Architecture (files that matter)

| File | Role |
|---|---|
| `serve.py` | Flask app; registers all blueprints |
| `simulator_api.py` | Core API: /api/simulate, plan endpoints, corridor, shared-flow, saved plans |
| `plan_simulator.py` | The tonnage engine (effective cycle × loader/point clip) |
| `monthly_api.py` | /monthly page + year board + Excel workbook builders |
| `scenario_api.py` | Mine-plan scenarios: import, waterfall, exports, draft plans |
| `plan_shared_flow.py` | DES-lite road-section occupancy (road crowding by hour) |
| `plan_corridor_hours.py` | GPS corridor hourly speeds/sections |
| `plan_analogues.py` | Route chainage (NODE_KM/SECTIONS), best-past-days |
| `prediction_api.py` / `train_model.py` | Phase-2 ML prediction service |
| `static/js/plan.js`, `plan_scenario.js`, `plan_sap_target.js` | Plan tab: builder, Step-2 outcomes, Allocate-DT |
| `static/js/flow_sim.js` | GPS corridor + chainage-stick animation (dual host) |
| `templates/simulator.html`, `monthly.html` | The two pages |
| `planning_rules.md` + `static/js/planning_rules.js` | Owner's plan rules (repo root, served at /planning_rules.md); parsed on load, enforced by plan_sap_target.js |
| `scripts/verify_phase2.sh` | **The gate suite — 72 gates, run before/after everything** |
| `AGENTS.md` | Project memory: every lesson, invariant, and owner preference |

## 4. The two clocks (never merge them)
- **Predicted** = path model: measured trips/DT × contractor factor × fleet,
  capped at demonstrated day trips. Rain moves it.
- **Achievable** = /api/simulate: effective cycle (720-min shift basis) +
  loader/point p99 clip. Weather-invariant. Availability = 1.0 (downtime is
  inside effective cycle; never re-add 0.85).
Congestion/corridor outputs are advisory and never clip tonnes (J53/J57).

## 5. Scenario system (built 2026-08-18/19)
- Import workbook (long-format "Mine Plan DB" sheet) on /monthly →
  `/api/scenarios/import`. S1 is always derived live from the yearly matrix
  (no S1 file may exist).
- Waterfall `/api/scenarios/<id>/allocate`: P1→P2→P3 per contractor pools,
  BLB=RIM lock, LIM-LD uncapped (8 Mt = target line).
- **SAP routing conditions (S2/S3 only)**: 10 kt/d TOFU→FENI KM15,
  10 kt/d BLB→FENI KM0, TOFU rest→POS 12, KR→POS 12, BLB rest→POS 14
  (`SAP_ROUTING` in scenario_api.py).
- Draft plans: POST `/api/scenarios/<id>/draft-plans` {year, day, months,
  overwrite} writes Plan-tab saves sized by the real path model
  (`_required_dt_day` → Predicted ≈ 100% of target).
- Owner flow per date: Plan tab → load date → Check capacity → ⚡ Allocate DT
  → Save. Monthly page picks it up by day-of-month.
- Year board scenario selector: `/api/monthly/year-board?day=N`; months with
  no save that day are dropped (Aug exists only in S1).

## 6. Allocate-DT engine specifics (plan_sap_target.js)
- Sizes P1/P2 to ~100% of target by walking DT one at a time from the row's
  current operating point (the prediction curve is NON-monotonic — global
  binary search picks wrong crossings; learned 2026-08-19).
- Extras go ONLY to LIM-LD. LIM-TOS is never pushed over target.
- **Cross-contractor rescue**: if a contractor's fleet is exhausted and its
  LIM-TOS is short, the other contractor's LD trucks cover the pending
  tonnage as a NEW row under their own flag (helper rows carry targetWmt 0
  to avoid double-counting). BLB wall enforced in the donor filter.

## 7. Excel exports (all from /monthly)
- `/api/monthly/export-year?year=&day=&achv=1` — the monthly_plan workbook
  (Year dashboard + one sheet per month). `day` picks the scenario;
  `achv=1` adds engine achievable AND drops all old-plan columns
  (three clocks: Target · Optimized predicted · Achievable).
- `/api/scenarios/export-full?year=&id=&achv=1` — same workbook per scenario;
  no id → zip of all. Optional "Paths" sheet lists all months × routes.
- `/api/scenarios/export` — scenario comparison workbook (waterfall).
- UI buttons exist for every variant, incl. "⬇ with achievable".

## 8. Road crowding / GPS corridor (2026-08-19)
- `/api/plan/shared-flow` with `whole_day:true` (UI default ON) simulates
  **two 12-h shifts** (07:00 + 19:00, releases re-staggered at changeover) —
  24 hourly bins across the real clock; night bins tinted, 19:00 edge marked.
- IWIP traffic toggle **default OFF**.
- Sections by chainage: TOFU–KR (39–67.8), KR–POS 12 (27–39),
  POS 12–POS 10 (17–27), POS 10–FENI (0–17) — see plan_analogues.SECTIONS.
- Chainage stick: full card width, 560–640 px tall (#plan-c3-flow-svg).

## 9. Key measured findings (for management context)
- S1 misses the 8 Mt LIM-LD target: ~5.45 Mt. S2/S3 free enough trucks to
  exceed it *in waterfall capacity terms* (~9.5 Mt), **but** the real
  constraint is the TF→HUAFEI corridor: ~500 trips/day ceiling ≈ 20–26 kt/d
  (~2.5–3 Mt Sep–Dec) no matter how many trucks are parked on it. Adding
  trucks past ~250–300 DT collapses trips/DT (1.9 → 0.75). That is why the
  S2 achievable total (~11.5 Mt Sep–Dec) is below S1's (~15.5 Mt): trucks
  moved from productive SAP routes (130–180 t/DT/d) to the saturated LD
  corridor (35–60 t/DT/d). The lever is a second LD route, not more trucks.
- Fleet pools (from the matrix): Aug 581, Sep 581, Oct 931, Nov 1280,
  Dec 1281 (RIM/SMA split in AGENTS.md §scenarios).

## 10. Verification
- `bash scripts/verify_phase2.sh` → **72/72** (2026-08-20). One flaky
  timing-sensitive gate can drop a run; re-run confirms.
- J72 (`scripts/check_scenarios.py`) pins the scenario system: fleet
  conservation, BLB=RIM, LD target reporting both directions, import
  idempotence, export == API, draft plans on-target, day-convention.
- Server must be on :5055 for browser-driven gates (J56/J64/J66/J67/J71).

## 11. Operational notes
- Start server: `cd /Users/lucky/wbn-fms-simulator && .venv/bin/python serve.py`
- Deploy story: `DEPLOY.md` + `scripts/deploy.sh` (public site is stale —
  needs owner decision; see AGENTS.md "Deploying").
- GPS accumulation cron: `scripts/accumulate_gps_cron.sh` 07:00/19:00.
- Commit style: explain the WHY, cite measurements; push `origin` + `mirror`
  (or `all`). Data files in data/saved_plans etc. are gitignored on purpose.

## 12. Hybrid congestion model (2026-08-20, owner spec)

`congestion/` package + `/api/congestion_model?route=TF>HUAFEI&n_trucks=590&n_loaders=4`.

Three layers, physics PRIMARY (never a black-box ML extrapolation):
1. **physics.py** — free-flow cycle from chainage distance; loaded speed
   back-solved per route so physics matches the observed free-flow cycle
   (p25 of per-truck trip gaps from HAULAGE_CLEAN, 2.34M tickets).
2. **queueing.py** (Erlang-C M/M/c loader queue) + **bpr.py** (BPR/BPR2 road
   penalty, v/c on DEMAND flow) + bunching variance term. Calibrated per
   route by `scripts/calibrate_congestion.py` → `data/congestion_params.json`
   (gitignored). A measured per-route **utilization** (~0.43–0.87) anchors
   the hybrid to the dispatch day-rate basis at the median fleet, so both
   engines agree at typical fleets and diverge only where physics says so.
3. Uncertainty bands (±10% in observed fleet range → ±40% beyond),
   `legacy_comparison` (the old divide model) in every response, components
   breakdown (road / BPR penalty / queue / load / spot / dump / bunching).

Key behaviours the old model could not express:
- **n_loaders is an input**: 8 loaders vs 2 raises trips/DT (queue clears).
- Nonlinear knee (not 1/N): decline elasticity varies with fleet.
- rho >= 1 flags "overloaded", queue wait capped at half a shift.

Verification: `scripts/verify_congestion.py` (gate **J73** in the suite):
backtest on 3,940 real dispatch days → **R² 0.873, MAPE 9.0%** at the
route × fleet-bucket expected-value level. Suite now **73/73**.

Basis warning (the third "two 240s" lesson): ticket-basis trips/TRUCK_ID
runs ~1.4× above dispatch-basis trips/NB_DT. Everything user-facing is
dispatch basis; the calibration handles the mapping via utilization.


## 13. Congestion model refinements (2026-08-20 evening -> 2026-08-21)

Sequence of fixes after the first S3 run, each owner-driven:

1. **Proportional loaders** (scripts/run_scenarios_hybrid.py,
   scripts/run_s3_hybrid.py): loaders scale with trucks by each route's
   measured trucks-per-loader (median fleet / median active loading faces;
   6.5-22.8 across routes). rho stays ~0.15-0.25 at any fleet; queue ~ 0.
   Owner: "loading is not the issue; the truck on the road is."
2. **Shared-road coupling**: rows sharing a route key are priced at the
   COMBINED fleet, output split by DT share. Without this the two-road
   analysis was a no-op.
3. **BPR sanity fixes** (commit ec66e4d): c_road from geometry not observed
   fleet throughput; BPR2 removed (985x penalties at mining v/c 3-5);
   road time capped at 3x free flow. Owner-validated ranges:
   BLB>POS 14 @228 ~ 6-7 trips/DT; TF>HUAFEI @771 ~ 0.9-1.2; @385 ~ 1.5-1.7.
4. **Geometry honesty pass** (commit 12dee29, second agent): 1-lane headway
   geometry, no owner-target fudge factors, S3 runner defaults to calibrated
   loader counts. Backtest after all of it: **R2 0.909, MAPE 6.5%**.

Current S3 picture (hybrid, honest physics): LD Sep-Dec ~ 2.8-3 Mt of the
8 Mt target; TF>HUAFEI is the binding corridor (v/c ~ 1.4-1.8 at planned
fleets); a second HUAFEI corridor is worth ~ +73% LD tonnage. BLB routes
run near-free at any planned fleet.

## 14. Current state / open threads (for the parallel agent)

Done and verified (73/73 as of 2026-08-21 morning):
- Hybrid model live end-to-end: /api/congestion_model, /api/congestion_curve,
  /api/congestion_compare; Allocate-DT engine consumes the curve cache
  (plan.js planHybridCurveFor); congestion charts JS exists
  (static/js/congestion_charts.js, from the frontend agent).
- Scenario system: S1/S2/S3 via day-of-month saves (01/02/03); Monthly page
  scenario selector; Excel exports incl. achievable variant; 24 h road
  crowding; scenario reports (scripts/run_s3_hybrid.py prints the
  Monthly-style tables).

Open threads someone can pick up:
- **Re-freeze S2/S3 allocations under the hybrid model**: the saved plans'
  frozen allocations predate the hybrid wiring; re-running Check capacity ->
  Allocate -> Save on the 02/03 dates re-sizes DT with hybrid pricing.
- **KR>POS 12 backtest MAPE ~43%** (worst route): trips/DT history is
  bimodal (shift pattern?); worth a dedicated look.
- **Uncertainty bands in UI**: P10/P90 are in the API but not rendered on
  the Plan tab yet.
- **Residual ML layer** (spec: XGBoost within observed range): deliberately
  skipped (<1% MAPE gain); revisit only if the owner asks.
- **Deploy**: public site still stale (see "Deploying"); owner decision
  pending.
