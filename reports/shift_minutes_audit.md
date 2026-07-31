# `shift_minutes` — audit of the last caller-supplied field that scales tonnage

*2026-07-31. Gate `J60`. Third in the series after
`CRITICAL_availability_override_defect.md` and `weather_input_analysis.md`.*

## Answer

**No bug of the availability kind.** The UI sends `720`, `DEFAULT_SHIFT_MIN` is
`720`, and the two agree. There is no silent override and no UI/engine
disagreement. Nothing was quoting a wrong number.

**But there is a real extrapolation, and it was silent.** Trips scale exactly
linearly with this field while the denominator they divide does not scale at all,
so any shift length other than 720 minutes is an unlabelled guess. It is now
labelled.

## The chain

| Step | Where | What happens |
|---|---|---|
| UI control | `templates/simulator.html` `#ps-shift` | number input, `min=60 max=1440`, **default 720** |
| JS payload | `static/js/plan_simulator.js:68` | `shift_minutes: parseFloat(q('ps-shift').value) \|\| 720` |
| Engine | `plan_simulator.py` | `shift_min = float(payload.get("shift_minutes", DEFAULT_SHIFT_MIN))` |
| | | `working_min = shift_min * avail` (avail is pinned to 1.0) |
| | | `trips_per_truck = working_min / effective_cycle_min` |
| Output | `summary.shift_minutes` | echoed back |

A second, unrelated `#plan-hours` input exists on the older **Plan** tab
(default 12 h). It feeds `computePlan()` and never reaches `/api/simulate`, so it
is out of scope here — but note there are two shift controls on two tabs that do
not talk to each other.

## Measured

30 trucks, `BLB>FENI KM0`:

| `shift_minutes` | trips/truck | tonnes | effective cycle |
|---|---|---|---|
| 60 | 0.17 | 254 | 355.0 |
| 360 | 1.01 | 1,521 | 355.0 |
| 600 | 1.69 | 2,535 | 355.0 |
| **720** | **2.03** | **3,042** | 355.0 |
| 840 | 2.37 | 3,549 | 355.0 |
| 1440 | 4.06 | 6,085 | 355.0 |

Exactly linear at every point, to the last decimal. The effective cycle never
moves — correctly, since it is a measured per-route constant.

## Why linear is not quite right

`simulator_model.py:324` derives the denominator as

```python
effective_cycle_min = (truck_shifts * 720) / trips        # 720 hardcoded
```

so it is *minutes of a **twelve-hour** shift per completed trip*. It bundles
per-trip time with per-shift overhead that does not scale — one pre-start, one
meal break, one refuel, one handover. Writing `720 = n·V + F` for `n` trips at
variable cost `V` and fixed overhead `F`:

- the model predicts `n' = S·n/720`
- the truth is `n' = (S − F)/V`
- the gap is `F·(1 − S/720)/V`

**positive for short shifts, negative for long ones**: the model over-states
trips below 720 minutes and under-states them above.

## Why the size of that error is not knowable here

`F` and `V` cannot be separated without shift-length variation, and there is
effectively none. From `availability_per_truck.csv`, 538,586 truck-shifts:

| | |
|---|---|
| exactly 12.0 h | **98.48%** |
| within 11.5–12.5 h | 99.03% |
| distinct values above 1% share | `{12.0}` — one value |

Shift length is a constant in this dataset. No regression can identify the split,
and inventing an `F` would be inventing the number. This is the same discipline
applied to road grade, operator experience and rain-on-speed elsewhere in the
project: the feature is not fabricated, the limitation is published.

## The fix

Keep the field — planners genuinely run other shift lengths, and refusing the
input would be worse than answering with a caveat — and **label the answer**:

- `summary.shift_calibration_min` always reports `720`.
- `summary.shift_minutes_extrapolated` appears **only** when the request is more
  than a minute away from 720, and states the direction of the likely error
  (over-states below 720, under-states above).
- `plan_simulator.js` renders it as a warning beside the plan, so it is where the
  planner is looking rather than only in the payload.
- Silent at 720 and at 721, because a warning that always fires is one nobody
  reads. The 1-minute tolerance is for float noise, not a judgement about
  materiality.

Nothing about the *numbers* changed. Bias stays at +5.5%, because the default
path is unchanged.

## Gate `J60`

Asserts both halves, since either alone can be satisfied by a broken build:

1. **No disagreement** — `DEFAULT_SHIFT_MIN == CALIBRATION_SHIFT_MIN == 720`, the
   UI input's `value=` attribute equals the calibration point, the lookup's
   `effective_cycle_basis` string still says 720, and the JS surfaces the
   warning key.
2. **Linear scaling with an untouched denominator**, at 360/600/840/1440.
3. **Labelled outside 720, silent at 720**, with the correct direction each side.

Mutation-tested twice: removing the warning fails 11 checks; moving the UI
default to 600 fails the front-end agreement check naming `600`.

## What is still open

- **The `#plan-hours` control on the Plan tab** is a second shift input that does
  not reach this engine. Not a defect today, but two controls for one concept is
  how the availability defect started.
- **A shift length of 1440 is offered by the UI** (`max=1440`) and is a 2× extrapolation.
  Consider narrowing the input range to something the data can defend, e.g.
  600–840, rather than relying on the warning alone.
- **If the effective cycle is ever re-derived at a different shift length**,
  `CALIBRATION_SHIFT_MIN` must move with it. `J60` checks that the lookup's basis
  string still mentions 720, which catches the common case but not a re-derivation
  that also rewrites the string.
