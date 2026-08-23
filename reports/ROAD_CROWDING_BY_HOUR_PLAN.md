# Road Crowding by Hour — plan, defects, and the physics it now runs on

Owner (2026-08-22): *"predict how many trucks will be running in each
section at each time of day for the plan we're using… make it real plans
and real physics, using the physics model we just created."*

This is the plan of record for the hourly per-section traffic view
(`/api/plan/shared-flow` → the **C · Road crowding by hour** card on Plan
Step 2). Status per item is marked. Doctrine unchanged throughout:
**advisory only — never clips `/api/simulate` tonnes** (J53).

## 1. What the question is

For a given day's plan (a real saved scenario plan: frozen allocation,
contractors, IWIP transit rows, rain), predict how many trucks occupy
each road segment (S1 TF–KR, S2 KR–POS 12, S3 POS 12–KM15, S4 KM15–coast,
plus the BLB spur) in every hour of the 24-h clock (two 12-h shifts,
07:00 / 19:00), and compare that against the official capacity of each
segment.

## 2. The defects the audit found (all FIXED, commit cc40b41)

| # | Defect | Why it lied | Fix |
|---|--------|-------------|-----|
| 1 | Trucks re-released every **raw cycle** | Ignored 2–6 h per-trip overhead (breaks, dispatch, refuel) that calibration measures — parked trucks were shown on the road, trips over-packed | Release cadence = model **cycle + overhead_per_trip** from `congestion.predictor` at the plan's fleets |
| 2 | **Loaded-outbound only** | Half the road's traffic (empty returns) never existed; loaded speeds used for everything | Full round trip: loaded pass → dump dwell → empty return in reverse, at the **empty-direction** official limit times |
| 3 | **One loader per pit** (serial stagger) | A 230-truck fleet mostly never departed inside the shift; peaks read ~12 trucks | Releases parallel across loading faces (~1 per 15 trucks, rules §10.9); peaks now ~300–400 concurrent |
| 4 | Old section map + **NODE_KM BLB=67.8 bug** | BLB spur trucks were smeared across the whole mainline | Sections are the model's S1–S4; non-stick routes get a `<PIT> spur` pseudo-section and never touch the stick |

## 3. The physics it runs on now

- **Per-truck timetable** from `congestion.predictor.predict()` at the
  PLAN's combined fleets: `segment_fleet` built from every route in the
  payload (IWIP included), per-contractor matched-day baselines, rain.
- **Road time split over segments** by the official directional
  speed-limit times (`congestion/speed_limits.py`, the 2025-08-11 PDF):
  loaded = ARAH MUATAN (down-chainage), empty = ARAH KOSONGAN (up). The
  route's TOTAL road time stays dispatch-anchored; the limits set each
  segment's share — same anchoring discipline as pricing.
- **Two quantities, never mixed** (corrected 2026-08-23 — the original
  version divided a stock by a flow and moved 2.5× with the display bin):
  - **flow** — trucks PASSING per hour, measured over a FIXED one-hour
    window whatever the grid draws, against the official lane capacity
    (S1–S3 600/h, S4 400/h per lane). This is the headline `ratio` (v/c).
  - **presence** — trucks ON the section at one moment, against how many
    physically FIT at 50 m spacing on both lanes (S1 1,152, S2/S3 480,
    S4 600, BLB spur 698). Reported as `occupancy` (mean concurrent per
    bin), `peak_concurrent`, and `ratio_presence`.
  Little's law is the bridge and is checked: presence = flow × time-in-
  section holds to 3 significant figures on the real plan.
- **Dwell** stays measured (wet/dry load & dump per point) — the model's
  queue term delays road entry; dwell occupies the pit, not the road.
- **Shifts**: two 12-h shifts. A trip in flight at the 19:00 changeover
  **runs to completion**, and the tail past the horizon wraps to t=0 —
  the plan repeats day after day, so that tail IS the traffic already on
  the road at the start. (Re-staggering at the changeover was dropped:
  with a uniform release it produces identical departure times, so all it
  ever contributed was the 17.9% truck-hour loss it caused.)
- **Big fleets** are sampled, never truncated: a row over
  `MAX_TRUCKS_SIM` simulates that many trucks each carrying weight
  n/sample, so occupancy and flow stay unbiased and only the resolution
  coarsens. The basis is disclosed in the payload.
- **BLB joins the stick at chainage 2.45 km** (survey-verified), so BLB
  trucks appear on the lower mainline as well as their spur.

## 4. Real plans — what the card actually sends (VERIFIED)

`planFetchRoadCrowding` (plan_scenario.js) posts, for the loaded plan:
- the **frozen allocation** (`_allocDt` — S4's 50/50 split rows go in as
  allocated, not as typed),
- every draft row **including** `foreign`/`_posTransit` IWIP rows,
- per-row **contractor** (baselines applied server-side),
- the plan's **rain** and the day/shift horizon (whole-day default).
The optional "include IWIP trucks" toggle adds measured historical
IWIP paths on top — background traffic beyond the plan's own rows.

Names are canonicalised server-side via `prediction_pipeline.
canonical_area` (the repo's ONE normaliser) so an alias row can never
silently price on default parameters.

The card's caption renders the **server's `note` field** — the backend
states its own basis; the UI can no longer describe a model it isn't
running.

## 5. Acceptance criteria (how to check it's real)

1. Load a saved S3/S4 plan → Check capacity → ▶ Run road crowding: the
   grid shows S1–S4 + spur rows; per-path `interval_h` matches the plan
   table's trips/DT (interval ≈ 1440 ÷ trips/DT), and `executed_trips`
   tracks `expected_trips` within 10% on every path (`trips_per_truck` is
   a continuous rate, not an integer count).
2. Presence per section ≈ Σ over routes crossing it of
   (DT × time-in-section ÷ interval) — this is a stock, so it is tens of
   trucks, not hundreds. v/c and peak concurrent are invariant to
   `bin_hours`, and the payload is invariant to the ORDER of the input
   rows (both asserted in `test_plan_shared_flow.py`).
3. `basis.phase` = `des_segment_model_roundtrip_2shift`;
   `congestion_clips_tonnes` false; suite 74/74 with J53/J57 green.
4. Changing rain moves dwell and cycle (wet), never simulate tonnes.

## 6. Later phases (not in scope now, listed so they aren't invented)

- **Measured-vs-simulated hourly overlay**: rebin the GPS corridor clock
  (`plan_corridor_hours`, Jul+ only) onto S1–S4 and draw measured mean
  occupancy beside the simulation — the honest backtest for this card.
  Blocked on enough GPS days per hour-bin to be a fair reference.
- **Synchronised breaks** (meal hours, shift-change road-empty window):
  overhead is currently smeared between trips. Modelling synchronized
  breaks WITHOUT double-counting overhead needs the overhead split into
  per-trip vs per-clock parts — new calibration, not a UI change.
- **Loader-face schedule**: faces are ~1 per 15 trucks; a real loader
  plan (which face, which hours) would replace the estimate when it
  exists (owner: "imagine same number of loaders" until then).
