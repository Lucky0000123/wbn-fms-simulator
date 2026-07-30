# Availability Analysis (Priority 1)

*Measured from `EQUIPMENTS_HOURLY_STATUS`, 2026-04-01 to 2026-06-30:
538,586 truck-shifts across 3,620 equipment units, of which 170,899 shifts on
1,103 haul trucks. Reproduce with `python availability_analysis.py`.*

## The headline: the premise had already been fixed, and re-applying it would break things

The task calls replacing the assumed 85% availability "the single biggest fix",
because the simulator multiplies every tonnage by it. **That was true when the
task was written and is no longer true.** The previous turn traced a 2.7x
production overprediction to the *cycle definition*, and fixing it removed the
availability multiplier entirely (`DEFAULT_AVAILABILITY = 1.0`), because the
measured effective cycle already contains every non-hauling minute.

Tested rather than argued, against observed tonnage per truck-shift on 44 routes:

| Availability factor applied | Resulting bias |
|---|---|
| **none (current)** | **+5.5%** |
| × 0.850 (the assumed figure) | −10.3% |
| × 0.836 (measured, hauling trucks) | −11.8% |
| × 0.765 (Day X fleet-wide) | −19.3% |
| × 0.451 (Day X utilisation) | −52.4% |

**Every factor makes the prediction worse.** Applying one would repeat the
original double-counting error in reverse and under-predict production for
whoever plans against it. So availability is measured and published, and
deliberately kept out of the tonnage arithmetic.

## Two independent measurements agree, which validates the effective cycle

This is the strongest evidence in this report, because the two figures come from
different tables by different routes.

| Quantity | Value | What it spans |
|---|---|---|
| availability × utilisation | **0.390** | share of a rostered shift spent working — loaded travel, empty return, queueing, manoeuvring |
| weigh-to-weigh ÷ effective cycle | **0.203** | share of the repeat interval the weighbridge observes — loaded travel only |

These measure different spans, so equality was never the test. The weighbridge
cannot see the empty return leg by construction, so if the loaded and empty legs
take roughly similar time it should see about half the working time:

**2 × 0.203 = 0.406 against a measured 0.390 — agreement within 0.016.**

The relationship holds on **13 of 14** routes. The exception, CRUSHER CAS → FENI
KM0, has a weigh-to-weigh/effective ratio of 0.77 against a median of 0.20: it is
a short reclaim shuttle from a crusher stockpile with little empty running, so the
weighbridge legitimately covers most of its cycle. The exception is explained by
the operation, not by a broken measurement.

## The measured numbers

| Population | Availability | Utilisation | Working share of total |
|---|---|---|---|
| All equipment (538,586 shifts) | 0.783 | 0.433 | 0.420 |
| **Haul trucks (170,899 shifts, 1,103 units)** | **0.720** | **0.542** | — |

Three ratios are reported rather than one, because they answer different
questions and the task's single formula conflates them:

- **availability** = 1 − (breakdown + PM) ÷ total. Fleet readiness; a maintenance
  manager owns this.
- **utilisation** = working ÷ available. How much of the usable time was used;
  operations owns this.
- **working share of total** = working ÷ total, which is the task's suggested
  formula. It scores a truck idle on standby the same as one broken down, though
  the two need completely different responses.

### The distribution is bimodal, so the mean describes almost nothing

| Measure | Value |
|---|---|
| Haul-truck shifts at availability exactly 1.0 | 75.4% |
| Haul-truck shifts at availability exactly 0.0 | 19.8% |
| Truck-shifts with only one non-zero hour type | 46.3% |

**A truck is usually either up for the whole shift or down for the whole shift.**
The mean of 0.720 describes few individual shifts. The actionable form of the same
fact is that **roughly 28% of haul-truck shifts are lost entirely**.

Checked whether this was a data artefact: it is not. Records are complete — total
hours per truck-shift have a median of 12.0 and a minimum of 8.0, so these are
full-shift accounts, not fragments.

### By truck, shift and contractor

- **186 haul trucks at or above 85% availability; 917 below.** The assumed 85%
  described the top 17% of the fleet.
- **By shift:** night 0.726, day 0.714. Essentially no difference.
- **By contractor:** all 170,899 haul-truck shifts are RIM. The other six
  contractors in the table (SMA, PPP, STM, SSS, CKB, GMG — 126,742 shifts) operate
  equipment that does not appear in the haul-truck ID set.

**A bug I found and fixed while producing this.** `SHIFT` is stored as a float
(`1.0`/`2.0`), and my first pass compared it to the string `"2"`. Nothing matched,
so every row was labelled "day" and the by-shift breakdown looked like a
single-shift operation. Both shifts are present in equal numbers (269,297 vs
269,289).

## What availability is now used for

It answers a question the simulator previously could not: **fleet sizing.**

| Trucks hauling | Trucks to roster | Spare for downtime |
|---|---|---|
| 10 | 14 | 4 |
| 20 | 28 | 8 |
| 30 | 42 | 12 |
| 50 | 70 | 20 |

`/api/simulate` now returns `trucks_to_roster` per plan and a `fleet_sizing`
block in the summary. Tonnage is unchanged, and `availability_factor_applied`
stays at 1.0.

Given the bimodality, treat this as an expectation over many shifts rather than a
guarantee for one: on any given shift roughly 28% of the rostered fleet is down,
but *which* trucks varies.

## Files

| File | Contents |
|---|---|
| `data/availability_per_truck.csv` | one row per truck per shift with hours, availability, utilisation |
| `data/availability_raw_2026-04-01_2026-06-30.csv` | cached raw extract, so re-analysis needs no VPN |
| `reports/availability_analysis.json` | the full statistics including per-shift and per-contractor breakdowns |
