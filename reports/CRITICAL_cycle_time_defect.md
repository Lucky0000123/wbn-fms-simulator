# Critical Finding: the plan simulator overpredicts production by ~2.7x

*Found while verifying whether the one-day deep dive's availability result
scales. It does not matter much — but the check uncovered something that does.*

**Status: documented, not yet fixed.** No application code has been changed.

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

## Recommended fix, not yet applied

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
