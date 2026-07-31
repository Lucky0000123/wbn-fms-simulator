# Full app audit — every endpoint, every filter

*2026-07-31. `scripts/audit_filters.py`, `reports/filter_audit.json`. Gate `J64`.*

## Headline

The user's three suspicions were all correct and all had **one cause**.

`serve.py` answered `/api/simulator/capability` with:

```python
return jsonify(_canonical_capability(fx("capability")))
```

The committed fixture. Every time. Database or not. `request.args` was never
read, and the UI sent it **six** filter parameters. So:

1. **Date pickers were cosmetic** — the summary line showed `2025-09-01 →
   2026-07-22` because those were the *fixture's own* `from`/`to` fields, not the
   operator's selection. Numbers and dates both came from the file.
2. **Exclude IWIP did nothing**, and the label disagreed with the checkbox for
   the same reason: the fixture's `inclIwip: false` was echoed regardless.
3. **The data was effectively hardcoded** — frozen at whatever was captured on
   2026-07-22.

This was documented in `serve.py`'s own docstring ("data-loader endpoints … still
served from fixtures") but had never been surfaced as a user-facing defect. It is
the whole of Tab 1: every KPI card, the routes and destinations tables, the 3D
scatter, the fleet-requirement calculator.

## Measured, not read

`scripts/audit_filters.py` calls every endpoint twice with different filter values
and compares responses. An endpoint whose output does not move is not filtering.

**Before** — 11 of 12 endpoints ignored every filter; only `path-response`
responded.

**After:**

| endpoint | date | iwip | types | source | dest | verdict |
|---|---|---|---|---|---|---|
| capability | ✅ | ✅ | ✅ | ✅ | ✅ | **fixed** — real query |
| path-response | ✅ | ✅ | ✅ | ✅ | ✅ | already correct |
| trucks | — | — | — | — | — | fixture; **no filterable column exists** |
| constraints | — | — | — | — | — | planner config, not data — correct as a fixture |
| congestion-model | — | — | — | — | — | **open**, see below |
| weighbridge / -summary / -positions | — | — | — | — | — | **open** |
| shift-context | n/a | n/a | n/a | n/a | n/a | takes an explicit `date=`; not a bug |
| simulate/options | n/a | n/a | n/a | n/a | n/a | reads lookup CSVs; route list is not date-scoped |
| model-info, corridor-geometry | n/a | n/a | n/a | n/a | n/a | metadata / road geometry; no time dimension |

## The fix

`api_simulator_capability()` now queries `DISPATCH RESULTS LITE 2`, which carries
actuals (`NB_DT`, `RIT`, `WMT`, `TF`) **and** plan (`DT PLAN`, `TARGET TRIP`,
`PLAN WMT`) on the same row, plus `COMPANY` (WBN/IWIP) and `TYPE`. Its `TYPE` has
exactly the nine values the fixture's `types` list had, which is what confirmed it
as the source.

Derivations were reverse-engineered from the fixture and **verified against it**
rather than guessed:

```
tf = t/trips     tripsPerDT = trips/dt     tPerDT = t/dt
effDT = dt/planDt   effWMT = t/planWmt     effTrip = tripsPerDT/planTripsPerDT
srit = rit/sc       sw = w/sc              snb = nb
```

Measured after the fix (`wmt/day`, `operating days`):

| window | days | wmt/day | routes |
|---|---|---|---|
| 2025-09-01 → 2026-07-22 | 322 | 121,459 | 67 |
| 2026-04-01 → 2026-07-31 | 111 | 40,370 | 20 |
| 2026-07-01 → 2026-07-31 | 20 | 9,179 | 8 |
| +IWIP (Apr–Jul) | 111 | 48,258 | 30 |

In the browser: unchecked → "incl IWIP", 166k t/day, 864 DT/day; checked →
"excl IWIP", 121k t/day, 670 DT/day. The label now matches the checkbox.

## Two regressions this created, and how they were caught

**A self-referencing dict literal.** The `daily` block read `rec["wmt"]` inside
the same `update()` that created it, raising `KeyError`. `_register` caught it and
served the fixture — producing a symptom *identical to the bug being fixed*. It
was found only by calling the function directly for a traceback. Fixed, and the
lesson is in the code: a fallback that hides an exception can disguise a broken
fix as an unfixed bug.

**The canonicalisation moved.** `_canonical_capability` lived in `serve.py`, which
no longer answers the route. Without reproducing it on the `_register` fixture
path, no-DB mode would have served "FENI A" / "HUAFEI.C01" — names the model has
never trained on. Moved into `simulator_api._canonical_fixture`; `check_vocab.py`
(43 cases) is what would have caught it.

## Still open, honestly

- **`congestion-model`, `weighbridge`, `weighbridge-summary`,
  `weighbridge-positions` ignore the date range.** They query the DB (not
  fixtures) but take no `from`/`to`. `congestion-model` is bounded anyway —
  `FMS_CONGESTION_SEG` retains ~2 weeks — but the weighbridge family should
  accept the window. Not attempted this round.
- **`trucks` is a static fixture** and now says so (`servedFrom: "fixture"`). It
  has no date, contractor or route column, so there is nothing to filter on; making
  it real needs a different source, not a WHERE clause.
- **`fleet` is returned empty.** It needs `TRUCK_ID`, which the dispatch view does
  not carry. Returned empty with a note rather than filled from an unfiltered
  second source, which would show a fleet ignoring the very filters the rest of
  the payload honours.
- **Tab-by-tab chart-level audit was not completed.** This round established the
  mechanism and fixed the root cause; individual charts on Tabs 1–2 have not each
  been traced to their SQL. The endpoint-level table above is the reliable map.
