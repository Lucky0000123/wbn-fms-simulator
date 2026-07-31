# End-to-end validation — driving the tool as a planning engineer

*2026-07-31. `scripts/e2e_validation.py`. Screenshots in `/tmp/e2e/` (48 files,
one per section per scenario per mode; not committed — they are large and
regenerable).*

## Verdict

**All nine sections render and the figures are coherent, in both database and
no-database mode. Zero console errors. Zero issues found in the application.**

One issue *was* found — in the validation script itself — and one result
contradicts the brief's stated expectation. Both are below.

Run twice, identical results:

| | dataMode | issues | console errors |
|---|---|---|---|
| Run A | `sample-fixtures` | 0 | none |
| Run B | `database` | 0 | none |

## Test 1 — single plan, 30 trucks BLB→FENI KM0, dry

Every section populated. The engine's own figures:

| Field | Value | Sanity |
|---|---|---|
| `predicted_cycle_time_min` | 77.8 | weigh-to-weigh, ≈ the 76.9 median |
| `effective_cycle_min` | 355.0 | measured per route |
| load / dump / travel | 13.0 / 13.2 / 51.6 | sums to 77.8 ✓ |
| `trips_per_shift_per_truck` | 2.03 | 720 / 355 = 2.03 ✓ |
| `total_trips` | 60.8 | 30 × 2.03 ✓ |
| `planned_production_t` | 3,042 | 60.8 × 50.0 t ✓ |
| `trucks_to_roster` | 39 | 30 / 0.7705, basis `measured` ✓ |
| `availability_factor_applied` | **1.0** | the defect from two rounds ago stays fixed |
| capacity | "within capacity: BLB asked for 61 of 636 trips/shift (10%)" | |

Every derived number reproduces from the ones beside it. Section counts:
12 congestion rows, 2 gauges (both drawn), 12 map sections, **367 polylines**.

**Section 4 carries the congestion claim in full** — verified as rendered text,
not as source: slope `-0.0233 km/h per extra truck`, `t = -9.89`,
`n = 35,006 of 36,046 segment-hours`, `R² 0.0028`, `−4.8%` full range.

## Test 2 — two plans sharing the FENI tip

Added 20 trucks POS 12→FENI KM0.

- Section 4 reports the shared point: **"FENI KM0 (50 trucks across 2 plans)"**.
- Section 5 shows **3** gauges, all drawn, and FENI KM0 reads **94 of 1,920
  trips/shift** — the *sum* of both plans (61 from BLB + 33 from POS 12). Demand
  is combined across plans, which is the entire point of shared-point detection.
- Sections 6 and 8 both grow to two rows plus a total.

## Test 3 — wet weather

**The brief asks "does the production decrease?" It does not, and that is
correct.** Tonnes are identical at **4,704 dry and 4,704 wet**.

| route | ΔCycle | ΔLoad | ΔDump | ΔTravel | ΔTonnes |
|---|---|---|---|---|---|
| BLB→FENI KM0 | +1.10 | 0.00 | +1.10 | **0.00** | **0.0** |
| POS 12→FENI KM0 | +14.80 | +13.60 | +1.10 | **0.00** | **0.0** |

Rain raises **dwell** where dwell is measured — POS 12 loading carries its
measured +13.6 min wet penalty — and the reported cycle time carries both ends.
It never reaches tonnage, because the effective cycle that trips divide by
deliberately excludes rain. The measured record supports that: rain moves
trips/DT a median **+4.8%** across 15 paired routes and reduces it on only 5 of
15; within route and month it is **+0.1%**. A wet production penalty would warn a
planner about a loss the data does not show. See
`reports/weather_input_analysis.md`.

`ΔTravel = 0.00` on both routes confirms the residual fix still holds under a
real two-plan workflow: implied travel is weather-invariant because nothing in
this dataset measures a rain effect on road speed.

## Test 4 — no database

Run A above **is** this test: `FMS_DB_*` unset, `dataMode: sample-fixtures`.

- All nine sections render, identical counts to database mode.
- Section 3 speeds come from the committed fixture, including the
  loaded/empty direction split.
- Section 9 draws 367 polylines from the committed centreline
  (`data/haul_road_chainage_public.csv`), verified separately by hiding the full
  extract: `geometrySource` flips to `committed` and the render is identical.
- Section 7 falls back correctly; routes with fewer than 4 comparable days are
  listed with their count rather than given an invented box.

**No section breaks without a database.** 19 of 19 endpoints return 200.

## The one defect found — in the validation script, not the app

The first run reported Section 4's congestion coefficient **missing**. It was
not. `scripts/e2e_validation.py` truncated the note to 400 characters *and then
tested the truncated string*; the coefficient sits about 430 characters in,
after the "read the bars and the coefficient as two different things" preamble
added in an earlier round.

Fixed by never truncating before a test — truncate at display time only. A
checker that reports absent-when-present is worse than no checker, because it
sends the next person hunting a defect that does not exist. This is the third
instance in this project of a check that could not fail or could not succeed for
reasons unrelated to the thing it was checking (the others: counting gauge
wrapper `div`s that are recreated every render, and counting SVG `path` elements
drawn into a zero-width overlay).

## Limits of this validation

- **Fixture and database modes agree exactly**, which is reassuring for
  plumbing but means this test does not distinguish them. The fixture was
  generated from the same source, so agreement is expected rather than
  informative.
- **Screenshots are not committed.** 48 PNGs at ~1 MB each is not a thing to put
  in a git repo that is already carrying its own audit trail; regenerate with
  `scripts/e2e_validation.py`.
- **It does not validate the predictions**, only that the tool reports them
  consistently and reproduces its own arithmetic. Prediction accuracy is the
  hold-out work in `CRITICAL_cycle_time_defect.md` (bias +5.5%).
- **One browser, one viewport** (Chromium, 1366×900). No Safari or Firefox pass.
