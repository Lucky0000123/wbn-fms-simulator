# CRITICAL — the UI under-quoted tonnage by 15% via an availability override

*Found and fixed 2026-07-30/31. Gate `J55`. Companion to
`CRITICAL_cycle_time_defect.md`, which documents the opposite-direction defect
(2.7x over-prediction) in the same arithmetic.*

## Summary

`static/js/plan_simulator.js` sent `availability: 0.85` on **every** call to
`POST /api/simulate`. `plan_simulator.py` honoured it:

```python
avail = float(payload.get("availability", DEFAULT_AVAILABILITY))
```

So the shipped user interface applied the exact 0.85 availability assumption
that this project had already measured as wrong and removed from the engine.
The engine was correct. The UI defeated it.

Anyone reading the API directly saw the right number. Anyone using the actual
tool saw a number 15% lower.

## Measured

Same plan, 30 trucks, `BLB>FENI KM0`, fixtures mode, 2026-07-30:

| Caller | `availability_factor_applied` | `planned_production_t` | `trips_per_shift_per_truck` |
|---|---|---|---|
| API, no `availability` key | 1.0 | **3,042 t** | 2.03 |
| The shipped UI (sends 0.85) | 0.85 | **2,586 t** | 1.72 |
| API, `availability=0.45` | 0.45 | 1,369 t | 0.91 |
| API, `availability=0.10` | 0.10 | 304 t | 0.20 |

The tool was linear in a parameter that should not exist.

Against the bias table already recorded in `reports/availability_analysis.md`,
this moves the delivered prediction from the measured **+5.5%** (no factor) to
**−10.3%** (×0.85). The direction is the point: the previous critical defect
over-predicted by 2.7x and was caught because 12,211 t against a real 2,500 t is
obviously absurd. A 15% under-quote is *plausible*, so nothing flagged it.

## Why availability must not scale tonnage

Unchanged from `availability_analysis.md`, restated because the fix depends on
it: `trips_per_shift_per_truck` divides the shift by the **effective cycle**,
which is shift-minutes per completed trip measured per route. That denominator
already contains downtime, queueing, empty running and breaks. Multiplying the
result by an availability allowance deducts the same time twice.

Two independent measurements agree the effective cycle already absorbs it:
availability × utilisation = **0.390** of a rostered shift is working time, and
the weighbridge sees **0.203** of the repeat interval which, doubled for the
unobserved empty return, gives **0.406** — agreement within 0.016.

Availability's real job is **fleet sizing**: roster 39 to keep 30 hauling. That
is where it is applied, and it is the only place.

## Why gate J52 did not catch it

J52 (`test_availability_usage.py`) asserts exactly the right invariant and
passed throughout. It builds its own payload:

```python
r = ps.simulate({"plans": [...]})            # no `availability` key
```

With no key, `payload.get("availability", DEFAULT_AVAILABILITY)` returns
`DEFAULT_AVAILABILITY`, which is 1.0, and every assertion holds. The gate tested
the default path. The defect lived on the caller-supplied path, and the caller
was the front end nobody was testing.

Demonstrated rather than argued — reintroducing the defect and running both
gates:

```
J55  FAIL  availability=0.85 leaves tonnage unchanged -- 2586.0 vs baseline 3042.0
J52  PASS  -- it cannot see this defect
```

**The general lesson: a gate that constructs its own input cannot catch a bug in
what the real caller sends.** This is the second time this project has been bitten
between the model and the user rather than inside the model, after the scale
mismatch and the guessed utilisation in Phase 3.5.

## The fix

1. **`plan_simulator.py`** — a supplied `availability` is accepted and ignored
   for tonnage. It is not rejected, because failing a request is worse than
   ignoring a field that must not exist. It is echoed back as
   `summary.availability_override_ignored` with the reason, so a caller learns
   instead of silently disagreeing with the API. A no-op override (`1.0`) and an
   unparseable one raise no warning, so the message stays meaningful.
2. **`static/js/plan_simulator.js`** — no longer sends the key, and renders the
   ignored-override warning prominently if anything ever sends one again.
3. **`templates/simulator.html`** — the "Availability (assumed)" input, which
   defaulted to `0.85`, is removed and replaced with a line stating that
   availability is measured per route and sizes the roster, not the tonnage.
4. **`test_availability_override.py` / gate `J55`** — tests the caller-supplied
   path across `0.85 / 0.45 / 0.10`, asserts tonnage and trips are unchanged and
   the factor stays 1.0, asserts a `1.0` override is silent, asserts junk values
   do not crash the run, and greps the front end so the key cannot come back.

## Verification

- `J55` fails under the reintroduced defect naming the exact tonnages, and
  passes when restored.
- Harness wiring proven by breaking the test's success line: score drops from
  56/56 to 54/56 naming `J55` (and `J56`), then restores.
- Full harness **56/56** in both no-DB and DB modes.

## Residual risk

`shift_minutes` and `weather` are still caller-supplied and still affect the
result. `shift_minutes` is a legitimate planner input. `weather` propagates
through dwell to cycle time, which the dwell analysis supports — but note that
`availability_analysis.md` records that rain must **not** carry a tonnage
penalty (rain moves tonnage +0.1% median, 49% of 122 route-months negative), and
a wet cycle uplift reduces trips and therefore tonnes. **That interaction has not
been re-verified in this round** and is the obvious next place to look for the
same class of defect.
