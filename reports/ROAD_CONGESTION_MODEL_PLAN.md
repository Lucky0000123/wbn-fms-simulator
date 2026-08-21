# Road congestion & contractor baselines — deep scan + plan (2026-08-21)

Owner's questions, verbatim intent:
1. Why are road penalties applied per route ("with the increasing number of
   each road") instead of per SHARED road — trucks on the same road must
   share one penalty.
2. TF→POS 12: why does RIM show more trips/DT than SMA on the same route?
   Same road → contractors should be close. Build per-contractor baselines
   from HISTORY, then apply road penalties to that baseline as trucks are
   added — including trucks from OTHER plans/contractors on shared parts
   (e.g. KR→POS 12 traffic affects TF→POS 12).
3. FIRST determine the exact points — where KR, TOFU, POS 12, FENI KM15,
   KM0 actually are — then model how added trucks affect each other.
4. Research how mining production-planning models handle road traffic,
   contractor history. Plan first; then assess site impact.

---

## 1 · What the industry does (research summary)

- **Discrete-event / microscopic simulation is the standard** for haul-road
  traffic in production planning: trucks cycle over measured road networks,
  with platooning ("bunching") behind slow loaded trucks on no-overtaking
  roads explicitly simulated. Commercial: RPMGlobal HAULSIM (3D haul
  network DES); Vale built AnyLogic DES/agent models for mine traffic.
  Validated bunching DES exists (Arizona surface mine).
- **Queueing theory (M/M/c) + match factor** size fleets at the loader:
  match factor = truck arrival rate vs loader service rate; MF>1 = trucks
  queue, MF<1 = loaders starve. Our Erlang-C layer and the Burt & Caccetta
  trucks-per-loader default follow this literature.
- **BPR volume-delay is a highway model** and measures poorly where truck
  composition, grade and curvature dominate (R² 0.26 vs 0.77 for a
  truck/geometry-aware model on two-lane rural roads). Low-volume
  single-lane roads are better served by logistic-type delay functions or
  microscopic models; local calibration is mandatory. No published
  validation of BPR on unpaved mine haul roads was found — a genuine gap,
  which is why our own backtest (R² 0.926 at route level) is the
  controlling evidence.
- **Cycle-time prediction**: regression/ML on the mine's own history beats
  generic simulation for level; site-specific, not transferable. Matches
  our dispatch-anchored calibration approach.

Sources: see the commit message / final report for links (ResearchGate,
ScienceDirect, RPMGlobal, AnyLogic case studies, Aalto thesis).

## 2 · Deep-scan findings on OUR site (measured today)

### 2.1 Geography — the exact points are partly WRONG in the model
- `plan_analogues.NODE_KM` pins **BLB at chainage 67.8 — identical to
  TOFU**. Physically BLB is a spur (19.9 km, own chainage) joining the
  mainline low. Consequences measured today: the frontend span logic
  treats every BLB route as covering the whole mainline 0–67.8, so
  (a) BLB trucks wrongly weighed on TF/KR windows in span-sharing, and
  (b) the section model charged BLB routes for TOFU–KR congestion they
  never see — part of why BLB collapsed to 3.7 trips/DT in the reverted
  section pricing.
- Calibration flags `chainage_suspect` on the TF corridor: TF>HUAFEI
  chainage 63.7 km vs cycle-implied 29.0 km (2.2×); TF>FENI KM15 52.8 vs
  28.6. Distance truth is unsettled exactly where the biggest fleets run.
  (DISTANCE_HAULING median says 63.7 for TF>HUAFEI; free-flow time is
  dispatch-anchored either way, but FLOW density, spans and section
  attribution all inherit the distance error.)
- POS 15/16 have no geofence/DISTANCE_HAULING at all (inherited values).

### 2.2 Road penalties today (code audit)
- Pricing = per-route calibrated saturation curve (physics + Erlang-C +
  BPR on the route's own c_road), evaluated at the SAME-KEY combined
  fleet; cross-key traffic enters only via a chainage-span-weighted fleet
  approximation (frontend only; the backend runners couple by key only).
- A per-window (section) pricer was built today (congestion/sections.py,
  POST /api/congestion_plan) and its pricing was REVERTED same day: its
  capacity basis (median *observed* peak per section) is "the most we
  ever did" ≠ "the most we can do", so ordinary plans read v/c≈2
  everywhere and every route was double-charged on top of a curve whose
  backtest already embeds real-day cross-traffic. The window TABLE
  (trucks/flow/speed per section) ships, information-only.

### 2.3 Contractor asymmetry — the owner is right
- TF→POS 12 the app shows RIM 2.47 vs SMA 1.70 trips/DT. That spread is
  ENTIRELY `planContractorFactor` — a fleet-wide global ratio — applied
  to a route with almost no direct RIM/SMA dispatch history.
- History (ticket basis, TF-origin routes, **matched same-day pairs** so
  both fleets face identical road traffic, n=469 days, both ≥5 trucks):
  RIM 1.88 vs SMA 3.19 median trips/DT — **RIM/SMA = 0.60 (p25 0.53,
  p75 0.70)**. The global factor is INVERTED on the TF corridor.
  (Payload partially counterweights: RIM ~49.9 t vs SMA ~48 t/trip does
  not close a 1.7× trips gap.) Raw per-contractor averages are
  confounded by fleet size (RIM ran ~140 trucks/day vs SMA ~58): only
  matched-day comparisons isolate the contractor effect.

## 3 · The plan (phases; each gated before the next)

**P0 — Geography truth first** (owner's explicit order)
- Re-derive every node's position from the committed survey polyline
  (`data/haul_road_chainage*.csv`) + FMS_GEOFENCES centers snapped to it;
  give BLB its own spur chainage and a mainline junction point; resolve
  the TF implied-vs-chainage 2.2× conflict (GPS trip length over the
  polyline for the 2026-07-15+ window where GPS exists).
- Output: one committed `route_geometry.json` (node points, spans,
  per-route section list with true overlap km) consumed by BOTH frontend
  span logic and the section model. Gate: implied-vs-mapped distance
  within ±20% per route or the route is flagged, never silently priced.

**P1 — Per-contractor baselines from history**
- Per route × contractor: matched same-day trips/DT ratios vs the route
  median (min 30 matched days, both fleets ≥5), shrunk toward 1.0 where
  thin (empirical-Bayes); routes with no history inherit the contractor's
  corridor-level matched ratio, NOT a fleet-global one.
- Replaces the global `planContractorFactor` in pricing. Same-road
  convergence: on a shared road the ROAD term is identical for everyone;
  only the measured contractor ratio (loading discipline, truck class)
  separates rows — bounded (e.g. 0.7–1.3) and labelled in the UI.
- Gate: reproduces the matched-day medians per corridor; total plan
  tonnage change reported before adoption.

**P2 — Shared-window load model with a REAL capacity basis**
- Window loads: all plan rows + IWIP + cross-plan traffic mapped through
  the P0 geometry (this answers "KR→POS 12 trucks slow TF→POS 12").
- Capacity per window from single-lane HEADWAY GEOMETRY (and, where the
  owner can supply them, posted section speed limits), NOT observed
  peaks. Delay shape: start from BPR but validate a logistic single-lane
  alternative against the fundamental-diagram literature; prefer
  extending `plan_shared_flow`'s DES (hourly per-section occupancy,
  already trusted in the UI) into a cycle-time integrator — the industry-
  standard approach — with the calibrated dispatch anchors as level.
- Re-anchor overhead per route under the plan-level model at
  RECONSTRUCTED historical window loads (dispatch day aggregates mapped
  through P0 geometry), so history-like plans reprice to the day-rate
  exactly and only genuinely hotter windows pay.
- Gate: day-level backtest R² ≥ current 0.926 and MAPE ≤ 5.9%; BLB band
  6–7 at small fleets; TF ≥1.5 at owner-validated fleets; never <1
  trip/day; monotone in fleet at 5-DT steps.

**P3 — Wire-in, two clocks discipline**
- New pricing ships as a SIDE-BY-SIDE diagnostic column first (J71
  lesson: one owner per concept, labelled on its face), flips to primary
  only on owner sign-off after comparing a full S3/S4 re-freeze.

**P4 — Site impact assessment (to be measured, direction expected)**
- BLB routes decouple from mainline noise → BLB trips/DT stable-to-up.
- TF corridor windows carry KR + IWIP + LD traffic → TF long-haul
  trips/DT modestly down at big fleets; S4's 50/50 split stays
  advantageous (POS 12 leg shares only the upper mainline) but its LD
  projection will shrink from the current 12–13 Mt toward the honest
  shared-window level.
- Contractor baselines move tonnage BETWEEN contractors on TF (SMA rows
  up, RIM rows down) with plan totals roughly conserved; allocation DT
  shifts follow.

## 4 · What we will NOT repeat (this repo's paid-for lessons)
- Observed peaks as capacity (dayTripsCap trap — twice now).
- A second congestion charge on top of a dispatch-anchored curve without
  re-anchoring (today's revert).
- Solver fixed points without convergence proof (the sawtooth).
- Fleet-global behavioral factors applied to routes never driven.
