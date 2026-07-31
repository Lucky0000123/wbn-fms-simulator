# The weather input — full chain, measured effect, and the defect that was actually there

*2026-07-31. Gate `J57`. Companion to `CRITICAL_availability_override_defect.md`.*

## Summary, including a correction to my own earlier claim

The weather input was flagged as the next likely instance of the availability
defect: a caller-supplied field, unexamined, suspected of pushing a wet cycle
uplift through to fewer trips and therefore fewer tonnes, against
`availability_analysis.md`'s finding that rain must not carry a tonnage penalty.

**That suspicion was wrong, and the wording in `reports/HANDOVER.md` that raised
it — "a wet cycle uplift reduces trips and therefore tonnes" — was wrong.**
Measured across 14 routes, tonnage is byte-identical between `weather=dry` and
`weather=wet` on every one. Rain is deliberately excluded from the effective
cycle, and the effective cycle is the only denominator for trips, so there is no
path from weather to tonnage. That was already correct and is now gated.

**A different defect was real, and nobody predicted it.** `implied_travel_time_min`
is a residual, and it was absorbing a dwell penalty applied at only one end of
the cycle. The model reported trucks travelling **faster in the rain** on 11 of
14 routes.

## 1. The full chain

| Step | Where | What happens |
|---|---|---|
| UI control | `templates/simulator.html` `#ps-weather` | `<select>` — Dry / Wet |
| JS payload | `static/js/plan_simulator.js:67` | `weather: q('ps-weather').value` |
| API | `POST /api/simulate` | passes the payload through |
| Engine | `plan_simulator.py` | `wet = str(payload.get("weather","dry")).lower() in ("wet","rain","rainy")` |
| Dwell | `_point_dwell(point, kind, wet)` | reads `wet_min` / `dry_min` from `data/dwell_model_results.csv`; where a point has no measured wet figure, applies `median x FALLBACK_WET_UPLIFT` |
| Cycle | `simulate()` | adds the dwell uplift to `median_cycle_min` |
| Effective cycle | `simulate()` | **rain deliberately NOT applied** |
| Trips / tonnes | `simulate()` | `working_min / effective_cycle` — therefore weather-independent |
| Output | `summary.weather`, `summary.weather_note` | reports what was applied and what was not |

There is no second weather path. The Phase 3.5 cycle model carries rainfall as a
feature, but `/api/simulate` does not call it — it reads `route_lookup.csv`. So
the double-count the brief hypothesised (model rainfall *and* a UI flag) does not
exist either; only one mechanism is live.

## 2. Measured: the model's effect, before the fix

30 trucks, `weather=dry` vs `weather=wet`, 14 routes, fixtures mode:

| route | ΔCycle | ΔLoad | ΔDump | **ΔTravel** | ΔTonnes |
|---|---|---|---|---|---|
| POS 12>FENI KM0 | +13.70 | +13.60 | +1.10 | **−1.10** | 0.0 |
| BLB>FENI KM0 | 0.00 | 0.00 | +1.10 | **−1.10** | 0.0 |
| KR>POS 10 | +2.60 | +2.50 | +7.90 | **−7.80** | 0.0 |
| POS CBB>POS 10 | +15.90 | +15.90 | +7.90 | **−7.80** | 0.0 |
| TF>POS 12 | −0.60 | −0.60 | −0.70 | **+0.70** | 0.0 |

**Tonnage moved on 0 of 14 routes.** Travel moved on 11 of 14, always by exactly
`−ΔDump`.

The mechanism: `implied_travel_time_min = cycle − load − dump`. The cycle uplift
was taken **only from the loading point's** `wet_penalty_min`, while
`predicted_dump_time_min` also carried the **dumping** point's. So

    travel_wet = (cycle_dry + loadPen) − (load_dry + loadPen) − (dump_dry + dumpPen)
               = travel_dry − dumpPen

Rain made haulage look faster, by up to 7.8 minutes.

## 3. Measured: what the data actually says about rain

From `/api/simulator/path-response`, raw wet-vs-dry trips/DT on the 15 routes
with paired data:

| | |
|---|---|
| Median effect of rain on trips/DT | **+4.77%** |
| Routes where rain *reduces* trips/DT | **5 of 15 (33%)** |
| Largest positive | KR>POS 10 **+23.3%** (n=63) |
| Largest negative | TF>POS 11 **−20.2%** (n=8) |

This is the uncontrolled comparison. The controlled one already recorded in
`plan_simulator.py` — within route **and** month, so the wet season is not being
compared against the dry — gives a median **+0.1%** with 49% of 122 route-months
negative. The two views disagree on magnitude and agree on the thing that
matters: **rain does not reliably cost tonnes.** A production penalty is not
supported, so the model applying none is correct.

Rain *does* lengthen dwell at specific points, and that is well measured:
POS 12 loading **+13.7 min**, POS CBB **+15.9 min**, HSM **+12.2 min**,
POS 10 dumping **+7.8 min**. Several points are negative (TF loading −0.6,
POS 12 dumping −0.6), which is itself a useful signal that this is noisy.

## 4. The fix

Neither Option A (remove the input) nor Option B (informational only) from the
brief addresses the defect that exists, because both assume the defect was a
tonnage penalty. Removing the input would have discarded a genuinely measured
effect — rain adding 13–16 minutes of loading dwell at some points is real and a
planner should see it — and neither option touches the residual arithmetic.

**The applied fix is to make the cycle carry the dwell uplift from *both* ends.**
The uplift is derived from the dwell deltas actually applied rather than re-read
from `wet_penalty_min`, because `_point_dwell` has its own fallback path whose
effect does not appear in that column. Then

    travel_wet = (cycle_dry + dLoad + dDump) − (load_dry + dLoad) − (dump_dry + dDump)
               = travel_dry

**Implied travel time is now weather-invariant, and that is the honest position.**
The wet/dry split is measured *at points*. Nothing in this dataset measures a
rain effect on road speed: `FMS_CONGESTION_SEG` has segment speeds but ~2 weeks
of retention and no rain join, so a travel penalty would have to be invented.

Bias is unchanged at **+5.5%**, because tonnage never moved with weather in
either build. The fix is to a *reported component*, not to the prediction.

### After the fix

| | before | after |
|---|---|---|
| routes where travel moves with weather | 11 of 14 | **0 of 14** |
| routes where tonnage moves with weather | 0 of 14 | **0 of 14** |
| `ΔCycle == ΔLoad + ΔDump` | no | **yes, all 14** |

## 5. The gate

`J57` (`test_weather_path.py`) asserts three things that must hold together:

1. tonnage, trips and the effective cycle do **not** move with weather
2. implied travel does **not** move with weather
3. weather **does** still move dwell where a wet figure is measured

Check 3 carries the weight. Without it, deleting the weather feature entirely
would pass 1 and 2 perfectly — **an invariance-only gate rewards doing nothing**,
which is the trap the availability gate fell into from the other direction.

Mutation-tested twice:

- restore the loading-only penalty → J57 fails, naming `travel moved +1.00 min
  (dDump −1.00)` and `cycle +0.00 vs dwell +1.10`
- delete the weather feature (`wet = False`) → J57 fails on `not a no-op
  (0 of 14 routes)` and on the reported weather

Tolerances are stated rather than tuned: every minute figure is rounded to 0.1
before it reaches the caller, so the composed check compares three independently
rounded values and carries a 0.16 budget. The defect it guards produces 1.1–7.9
min, one to two orders of magnitude above that.

## 6. What is still not known

- **No rain effect on road speed is modelled, and none is measured.** If the GPS
  accumulator widens `FMS_CONGESTION_SEG` coverage enough to join rain by
  segment-hour, this becomes answerable, and travel would stop being invariant.
  That is the one thing that would change this conclusion.
- **`shift_minutes` remains caller-supplied** and is a legitimate planner input.
  It scales `working_min` and therefore tonnage linearly, by design. It has not
  been audited for a UI/engine disagreement of the availability kind; the UI
  sends `720`, which matches `DEFAULT_SHIFT_MIN`, so there is no live
  discrepancy today.
- **The wet fallback** (`median x FALLBACK_WET_UPLIFT` for a point with no
  measured wet figure) is an assumption, not a measurement. It is labelled as
  such in the dwell basis string, and it now propagates consistently to the
  cycle, but it is still an assumption.
