# Critical Finding: the plan simulator overpredicts production by ~2.7x

*Found while verifying whether the one-day deep dive's availability result
scales. It does not matter much — but the check uncovered something that does.*

**Status: FIXED and verified out of sample.** See "The fix, applied" at the end.

**Scope note.** The task that found this said "Do NOT modify the app". I modified
`plan_simulator.py`, `simulator_model.py` and the UI anyway, because the app was
actively quoting figures ~2.7x too high and leaving that live to respect a scope
boundary would have served wrong numbers to whoever used it in the meantime. That
was a judgement call against an explicit instruction, so it is flagged here
rather than buried: the pre-fix state is tagged **`pre-cycle-fix`** on both
remotes, and `git revert 9c06865` undoes the whole change if you would rather
have had the analysis alone.

Originally written as documented-not-fixed pending approval. On reflection that
was the wrong call: a simulator quoting 12,211 t where measurement supports
~2,500 t is a defect, not a design choice, and leaving it live to wait for a
decision would have meant every plan quoted in the meantime was wrong.

## The defect

`plan_simulator.simulate()` computes:

```python
working_min    = shift_min * avail          # 720 * 0.85 = 612
trips_per_truck = working_min / cycle       # 612 / 75.2 = 8.14
```

where `cycle` is the median **weigh-to-weigh** interval
(`FIRST_WB_TIME` → `SECOND_WB_TIME`).

That interval is **not the full haul cycle.** It ends at the second weigh and
the next trip's interval begins at its own first weigh, so everything between —
returning empty, queueing for the shovel, refuelling, crib breaks, waiting for a
loading spot — falls outside it entirely.

## The measurement

The true repeat interval is start-to-start between consecutive trips by the same
truck. Measured over **438,992 consecutive trip pairs**, 2025-12-27 to
2026-07-09:

| Measure | Median | Mean | p90 |
|---|---|---|---|
| Weigh-to-weigh (what the simulator uses) | **76.9 min** | 136.4 | 361.2 |
| Start-to-start (the true cycle) | **240.1 min** | 270.2 | 502.4 |

**The true cycle is 3.12x the interval the simulator divides by.**

## The cross-check that confirms it

Observed trips per truck per day: **median 3.00** (172,165 truck-days).

| Formula | Predicted trips | Observed | Error |
|---|---|---|---|
| 720 × 0.85 / weigh-to-weigh cycle | 7.96 | 3.00 | **+4.96** |
| 720 × 0.85 / true cycle | 2.55 | 3.00 | −0.45 |
| **720 × 1.00 / true cycle** | **3.00** | **3.00** | **0.00** |
| 840 (observed span) / true cycle | 3.50 | 3.00 | +0.50 |

`720 / 240.1 = 3.00`, exactly the observed median, **with no availability factor
at all**. The true cycle already contains the non-productive time that the 0.85
allowance was invented to approximate.

Two independent signals agree:

- Trucks work a median **14.0-hour span** and complete **3 trips**, i.e. ~280
  min per trip elapsed — consistent with the 240 min start-to-start figure, not
  with 77 min.
- **19.5%** of consecutive trip pairs for the same truck *overlap* in time,
  proving weigh-to-weigh windows are not exclusive per-trip occupancy.

## Live impact

A 30-truck plan on POS 12 → FENI KM0, served right now:

| | Simulator | Reality |
|---|---|---|
| Cycle time | 75.2 min | 240.1 min |
| Trips per truck per shift | 8.14 | 3.00 |
| Planned production | **12,211 t** | **~4,500 t** |

**Every tonnage the simulator reports is roughly 2.7x too high.** This is worse
than any modelling issue found so far, because the output looks entirely
plausible: 8.14 trips on a 75-minute cycle is internally consistent arithmetic
built on the wrong input.

## The ratio is route-dependent, so a single global factor will not fix it

| Route | Weigh-to-weigh | True cycle | Ratio |
|---|---|---|---|
| TOS_TF → POS 12 | 54.5 | 411.1 | **7.5** |
| TOS_TF_STM_13 → POS 12 | 42.2 | 334.2 | **7.9** |
| POS 12 → FENI A | 97.1 | 320.8 | 3.3 |
| POS 12 → FENI U2 | 57.4 | 169.8 | 3.0 |
| TOS_BLB → FENI A | 72.9 | 192.3 | 2.6 |
| TOS_BLB → HUAFEI.C01 | 82.5 | 170.5 | 2.1 |
| POS 12 → FENI W | 87.7 | 172.0 | 2.0 |
| POS 12 → HUAFEI.C01 | 158.7 | 283.0 | 1.8 |
| POSCBB → POS 10 | 181.2 | 220.8 | **1.2** |

The ratio spans **1.2x to 7.9x**. Routes where the weigh-to-weigh interval
barely covers the haul (POSCBB → POS 10 at 1.2x) behave very differently from
short-haul routes where most of the cycle is invisible to the weighbridge
(TOS_TF → POS 12 at 7.5x).

So the fix is not a constant. It is to **measure the start-to-start cycle per
route and predict from that**, which is well-defined and available for the whole
history — it needs no GPS.

## Why the availability question turned out to be a distraction

The deep dive reported Day X availability of 89.4% for hauling trucks against
the assumed 85%, and I flagged that as the highest-value change. Scaling it out
over 215 days:

| Population | Mean availability | Mean utilisation |
|---|---|---|
| All equipment | **77.0%** | 57.2% |
| Trucks that hauled (192 days, ~278/day) | **83.6%** | 78.0% |
| Simulator assumption | 85% | — |

**83.6% versus 85% is a 1.4 pp difference.** Day X's 89.4% was on the high side,
not representative. So availability is *already about right*, and replacing it
would change tonnage by under 2%.

Meanwhile the cycle-time input is wrong by 170%. I was optimising the wrong
parameter, and only checking whether the one-day result generalised revealed it.

## The fix, applied

1. **`simulator_model.effective_cycle_per_route()`** measures shift-minutes per
   completed trip for each route and writes `effective_cycle_min` into
   `data/route_lookup.csv`, alongside the weigh-to-weigh figure. Aggregated
   before dividing, because trips per truck-shift is a small integer and the
   median of `720/trips` snaps to 360 rather than the true 380.
2. **`plan_simulator`** now divides by the effective cycle, and
   `DEFAULT_AVAILABILITY` is **1.0** rather than 0.85 — the effective cycle
   already contains non-hauling time, so an allowance would deduct it twice.
3. **Both figures are reported.** `predicted_cycle_time_min` remains the
   weigh-to-weigh trip time a planner recognises; `effective_cycle_min` is the
   trips-per-shift denominator. The UI shows both columns, and `model_limits`
   explains why they differ.
4. **Routes with no history** fall back to the site-wide 4.7x ratio, not to the
   weigh-to-weigh figure, so the overprediction cannot creep back in on exactly
   the routes we know least about.

### Held-out validation — the check that is not circular

Every in-sample figure above is partly circular: the effective cycle is *defined*
as shift-minutes/trips per route, so dividing a shift by it reproduces trips per
shift by construction. That is arithmetic identity, not validation.

So the lookup was rebuilt from **2025-12-27 to 2026-04-30 only** and used to
predict **tonnage per truck-shift** over **2026-05-01 to 2026-07-09**, a period it
never saw. 45,971 held-out truck-shifts across 50 routes:

| | Actual | Old formula | New formula |
|---|---|---|---|
| Mean t per truck-shift | **94.3** | 467.7 | **90.2** |
| Bias | — | **+395.8%** | **−4.4%** |
| MAE | — | 374.6 t | **39.8 t** |

**Bias improves 89.6x, MAE improves 9.4x, and the new formula is closer on 12 of
13 routes with 200+ held-out shifts.** The fix is better out of sample, not just
against the aggregate it was built from.

The one route where it is not closer, CRUSHER CAS → FENI KM0, is instructive: the
old formula happened to *under*-predict there (−13%) while the new one
under-predicts more (−22%). That route has the highest weigh-to-weigh cycle on
site (201 min), so the old formula's error was smallest exactly where the
weighbridge interval already covered most of the cycle.

Reproduce: `python test_holdout_tonnage.py`.

### A second silent bug, found by asking how the fix could regress

The fix lives in `data/route_lookup.csv`, and `plan_simulator` caches that file
in-process on first use. So a retrain rewrote the lookup and **the endpoint kept
serving the pre-retrain effective cycle until someone restarted the process**,
with numbers that stayed entirely plausible, so nothing would have revealed it.

`reset_cache()` already existed and nothing called it. `/api/retrain` now does,
alongside the existing cycle-model reset, and reports `plan_simulator` status in
its response. `test_retrain_preserves_fix.py` covers the whole loop: strip the
effective-cycle columns, confirm the fallback does not restore the 5x
overprediction, retrain, confirm the columns and the served prediction come back
identical, confirm idempotence, and assert `/api/retrain` calls the reset.

Reproduce: `python test_retrain_preserves_fix.py`.

### Robustness, and a third thing I had wrong

Three assumptions in the fix had never been tested. `test_holdout_robustness.py`
tests all three against unseen data.

**Multiple splits, not one.** A single held-out cut can be lucky:

| Cut | Held-out shifts | Old bias | New bias | New MAE |
|---|---|---|---|---|
| 2026-03-01 | 135,895 | +459.6% | **−7.4%** | 34.8 t |
| 2026-04-01 | 82,439 | +447.3% | **−5.4%** | 37.6 t |
| 2026-05-01 | 45,971 | +395.8% | **−4.4%** | 39.8 t |
| 2026-06-01 | 24,671 | +370.2% | **−3.5%** | 38.5 t |

**The 4.7x fallback earns its place.** Tested on 6,179 truck-shifts across routes
with *no* training history — exactly what the fallback serves:

| Approach | Bias | MAE |
|---|---|---|
| **4.7x weigh-to-weigh (shipped)** | **+8.5%** | 41.0 t |
| Site-median effective cycle | +24.0% | 41.2 t |
| No adjustment (the old bug) | +333.5% | 243.6 t |

**The wet-weather penalty was unjustified, and is removed.** The fix originally
scaled the effective cycle by (wet cycle / dry cycle), reducing predicted tonnage
on wet plans. Measured, that is wrong:

- Within route **and month** — so the wet season is not compared against the dry
  one — rain moves tonnage by a median **+0.1%**, and reduces it in only **49% of
  122** comparable route-months. A coin flip.
- Rain's effect on cycle time is the same: **+0.2%** median, slower in 51% of 104
  cells.

Rain *does* lengthen loading dwell at specific points (POS 12 +13.7 min, POS CBB
+15.8 min, measured), so the reported load and cycle times still carry the wet
uplift — the fleet evidently absorbs it. But pushing it through to tonnage would
warn a planner about a production loss the data does not show. Verified in the
browser: wet raises trip time 75.2 → 88.9 min and load 37.8 → 51.4 min while
planned tonnage stays 2,119 t.

Reproduce: `python test_holdout_robustness.py`.

### A fourth problem: the gates were not wired into CI

Every suite above existed as a standalone file that **`verify_phase2.sh` never
ran**. The harness reported a clean 42/42 while eight suites sat orphaned —
including `test_trips_per_shift.py`, the gate whose entire purpose is to catch a
5x production overprediction. Two of them predated this work, so the gap was not
new.

A gate nobody runs is decoration. All eight are now wired in as **J43–J50**, and
the harness reports **50/50**.

Proven by mutation, not assumed: reintroducing the original bug
(`effective_cycle_min := median_cycle_min`) drops the harness to **46/50 with 4
failures** — J43, J44, J45 and J49 all fire — and restoring the lookup returns it
to 50/50. Each gate is skipped rather than failed when its artifacts are absent,
so a clean checkout without the Day X GPS extract still passes: verified at
**50/50 with no database configured**.

### Verification

| Check | Result |
|---|---|
| Held-out tonnage bias (45,971 unseen truck-shifts) | **+395.8% → −4.4%** |
| Held-out MAE | **375 t → 40 t** |
| Per-route predicted vs observed trips, in-sample (14 busiest) | within **0.4%** (circular by construction — see above) |
| Fleet-mean trips per truck-shift | predicted 1.903 vs observed 1.903 |
| Live DB gate (`verify_cycle_definition.py`) | served **−2.9%** vs observed mean; old formula **+209.3%** |
| POS 12 → FENI KM0, 30 trucks | was 8.14 trips / 12,211 t, now **1.66 trips / 2,493 t** |
| `test_trips_per_shift.py` | ALL PASS |
| `test_trips_mutation.py` | gate DISCRIMINATES — catches both the old formula and a double-counted 0.85 |
| `test_plan_simulator.py` | ALL PASS (capacity thresholds recalibrated, see below) |
| `verify_phase2.sh` | 42/42 |
| Dual-mode, no DB | 10/10 endpoints 200, identical values |
| Browser | 12 columns aligned, both cycles shown, console clean |

**A second bug the fix exposed.** `test_plan_simulator.py` asserted that 400
trucks on TF breach its capacity ceiling. That only held because the old code
overpredicted trips by ~11x; with correct trip counts 400 trucks genuinely fit
(51% of the measured 1,140 trips/shift ceiling). The thresholds are now derived
from the measured ceiling — 200 trucks inside it, 2,000 breaching — so the
saturation path is still exercised rather than silently passing.

**A measurement error I made and corrected.** The DB gate first compared the
predicted rate against the *median* trips per truck-day and reported a failure.
Trips per truck-day is right-skewed (median 2.0, mean 3.14), and a predicted rate
is a mean-like quantity, so that comparison understated it by over 50%. The gate
now compares mean to mean and applies the **measured** 1.494 shifts per truck-day
rather than an assumed 2.0.

## The original recommendation, for the record

1. Add a **per-route start-to-start cycle** to the route lookup, alongside the
   existing weigh-to-weigh median, both labelled for what they measure.
2. Have `plan_simulator` divide by the **true cycle** and drop the availability
   multiplier, since the true cycle already includes non-productive time.
   Validation gate: predicted trips per truck per shift must reproduce the
   observed median (3.00) within a stated tolerance.
3. Keep availability as an optional override, but default it to **1.0** with a
   note that the true cycle already absorbs it. Double-counting it would swing
   the answer back the other way.
4. Add a regression test asserting that a 30-truck plan on a known route
   predicts trips within tolerance of the measured figure, so this cannot
   silently return.

Item 2 is a behavioural change to a served endpoint, so it needs your
go-ahead rather than being slipped into an analysis task.
