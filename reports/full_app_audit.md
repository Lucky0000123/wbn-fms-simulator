# Full app audit — 2026-07-31

Filter performance fix + honesty pass across every tab, filter, and metric.
Measured against a live server (`dataMode=database`) with VPN up, then
cross-checked in no-DB / fixture mode.

## Verdict

| Area | Status | Evidence |
|---|---|---|
| Capability filters (date/IWIP/type/source/dest) | **FIXED** | All six RESPOND; echoed window matches request |
| Filter latency after Apply | **FIXED** | Warm worst **0.07–0.08 s** (was ~17–22 s per request) |
| Exclude-IWIP checkbox vs summary | **FIXED** | Checkbox now `checked` by default; matches `inclIwip=false` |
| Availability multiplier on tonnage | Still gone | simulate roster_availability is disclosure-only; J52 |
| Congestion in tonnage model | Still out | J53; Congestion tab is evidence only |
| Trucks table vs filters | Known gap | Static fixture, now tagged `servedFrom=fixture` |
| path-response cold load | Slow (follow-up) | **14.8 s** on first call — not on Apply path |
| weighbridge cold load | Slow (follow-up) | **6.5 s** — lazy, Congestion/WB sections only |

## What was broken

`/api/simulator/capability` was answered in `serve.py` with the committed
fixture and `request.args` never read. The UI sent six filters; all six were
discarded. KPIs, routes, destinations, 3D scatter and the summary date range
were frozen at the 2026-07-22 capture.

A first real-query fix hit `DISPATCH RESULTS LITE 2` per request. That view
costs ~15–17 s to materialise even for `COUNT(*)`, so every Apply sat on
"Loading…". Correct, and unusable.

## What we shipped

1. **Whole-view snapshot** (`_cap_snapshot`, TTL 300 s, lock-serialised).
   One 17 s load; every filter runs in Python against ~21k normalised rows.
2. **Background warm** on `serve.py` start so the first operator does not pay.
3. **`/api/retrain` clears the snapshot** (`_cap_reset`).
4. **Exclude IWIP checkbox default = checked**, matching backend "absent means
   exclude" and the summary line (`excl IWIP`).
5. **Apply debounce 500 ms** + load generation counter so stale responses
   cannot overwrite a newer window; Apply button shows `Loading…`.
6. **Gate J64** (`test_capability_filters.py`) — correctness + &lt;3 s speed.
   Wired into `scripts/verify_phase2.sh` when `:5055` is up.
7. **Mutation-tested**: `_cap_load_rows()` every request → **16.7 s / 16.1 s**
   (caught). Restored snapshot → **0.06 s** worst.

## Tab-by-tab

### 1. Capability & Scenario

| Control / metric | Real? | Filters? | Notes |
|---|---|---|---|
| Summary scope line | Yes | Yes | Echoes request `from`/`to`/`inclIwip`/source/dest |
| KPI cards (WMT/day, DT/day, trips/DT, …) | Yes | Yes | From `DISPATCH RESULTS LITE 2` aggregates |
| Types dropdown | Yes | Window-scoped | Built from date+IWIP window so picking one type cannot empty the menu |
| Source / Dest / Path | Yes | Yes | Matched on **canonical** names (`FENI KM0`), not raw (`FENI A`) |
| Monthly trend | Yes | Yes | `months[]` from filtered daily |
| 3D scatter / combined load | Yes | Yes | `daily` / `dailyByPath` |
| Rainfall impact table | Yes | Partial | `path-response` is live OLS; **does not re-fetch on Apply** (loaded once at init). Date bar does not re-scope it today |
| IWIP traffic impact | Yes | Shift-scoped | `shift-context` for the selected scenario date |
| Weighbridge status strip | Mixed | No top-bar filter | `/api/weighbridge-summary` — see gaps |
| Road capacity / flow sim | Derived | Client-side | Uses capability payload + corridor constants |
| Truck list | **Fixture** | No | Tagged `servedFrom=fixture`; no TRUCK_ID on dispatch view |

Measured (warm snapshot, 2026-07-31):

| Window | days | wmt/day | paths | latency |
|---|---|---|---|---|
| 2025-09-01 → 2026-07-31 (excl IWIP) | 323 | 121,084 | 67 | 0.15 s (first after warm) / 0.07 s |
| 2026-07-01 → 2026-07-31 | 20 | 9,179 | 8 | 0.01 s |
| Wide + incl IWIP | — | 165,746 | — | raises tonnage as expected |

### 2. Congestion Model

| Item | Real? | Filters? |
|---|---|---|
| Speed vs trucks/hr scatter | Yes — `FMS_CONGESTION_SEG` | **Ignores** top date bar (telematics retention ~15 days; own window) |
| Segment list (94) | Yes | No |
| Tunable jam/n curve | Client overlay | N/A — not a measurement claim |
| "measured from N observations" copy | Yes | Driven by payload |

Latency ~2.2 s cold. Not on the Apply path. Congestion must stay **out** of
the tonnage model (J53); this tab is evidence, not a production lever.

### 3. Plan (legacy)

| Item | Real? | Notes |
|---|---|---|
| Contractor / src / dst selectors | From path-response + options | |
| Estimate panel | `/api/predict` + lookup | Dual-mode OLS / baseline |
| Does **not** use top-bar date filters | By design (model is trained, not windowed) | |

### 4. Production Simulator / Plan Assessment

| Section | Real? | Notes |
|---|---|---|
| S2 trip-time breakdown | Yes | `predicted_*` + dwell from engine |
| S3 speed per section | Yes | Direction-split speeds (J61) |
| S4 congestion impact | Yes | Measured −4.8%; display only |
| S5 queue gauges | Yes | p99 point capacity |
| S6 production | Yes | Divides by **effective** cycle (J44/J52) |
| S7 historical reference | Yes | Best days from route lookup |
| S8 fleet sizing | Yes | `trucks_to_roster` / measured availability basis |
| S9 corridor map | Yes | Leaflet + Cesium; public chainage (J63) |

Sample simulate (30 trucks BLB→FENI KM0): engine returns weigh-to-weigh cycle,
effective cycle, achievable tonnes, roster — dual-mode from CSVs, no VPN.

## Endpoint filter matrix

From `scripts/audit_filters.py` + live probes (DB configured):

| Endpoint | Date | IWIP | Types | Source | Dest | Source of truth |
|---|---|---|---|---|---|---|
| capability | RESPONDS | RESPONDS | RESPONDS | RESPONDS | RESPONDS | Live snapshot |
| trucks | IGNORES | IGNORES | IGNORES | IGNORES | IGNORES | Fixture (tagged) |
| constraints | IGNORES | IGNORES | IGNORES | IGNORES | IGNORES | Persisted matrix / default |
| path-response | RESPONDS* | RESPONDS* | RESPONDS* | RESPONDS* | RESPONDS* | Live SQL (*slow; not Apply) |
| congestion-model | IGNORES | IGNORES | IGNORES | IGNORES | IGNORES | Live telematics window |
| weighbridge | IGNORES | IGNORES | IGNORES | IGNORES | IGNORES | Live / cached |
| weighbridge-summary | IGNORES | IGNORES | IGNORES | IGNORES | IGNORES | Often fixture-identical |
| shift-context | date arg only | — | — | — | — | Live for scenario date |
| simulate / options / model-info / corridor-geometry | N/A | | | | | Not windowed by design |

\*path-response accepts filter args in the black-box test but the Capability tab
does not re-call it on Apply. Operators changing the date bar will see KPIs and
scatter move while the rain table stays on the init fetch until reload.

## Dual-mode

- `_register` still serves `fixtures/capability.json` (canonicalised) when
  `FMS_DB_*` unset or the query raises.
- J64 skips filter assertions in no-DB mode; still asserts fixture
  canonicalisation (no stale `FENI A` / `HUAFEI.C01` labels).
- Simulate path never needed a fixture — CSV lookups only.

## Performance budget (Apply)

| Call | Warm | Notes |
|---|---|---|
| `/api/simulator/capability` | **&lt;0.1 s** | Snapshot filter |
| `/api/simulator/trucks` | &lt;0.05 s | Fixture |
| **Total Apply** | **&lt;0.2 s** + 500 ms debounce | Target was &lt;2–3 s |

Cold snapshot materialisation remains ~17 s once per TTL/process; background
warm hides it when the process has been up &gt;20 s.

## Remaining gaps (honest)

1. **Truck list** — dispatch view has no `TRUCK_ID`. Returning an unfiltered
   second source would lie about the filter window; empty+note is preferred to
   a fake fleet. Fixture list is labelled.
2. **path-response ~15 s cold** — hurts first paint of the rain table; needs
   the same snapshot pattern as capability (follow-up).
3. **weighbridge ~6.5 s** — lazy-loaded; acceptable but should cache.
4. **weighbridge-summary** often byte-identical to fixture even with DB —
   treat displayed "latest" status as suspect until proven live.
5. **Top-bar filters do not re-scope** congestion / weighbridge / path-response
   UI panels. Only Capability KPIs/tables/scatter move on Apply. Documented
   here so nobody mistakes that for a regression of the capability fix.
6. **GPS overlap** still the production-model blocker (accumulator growing).

## Gates

```text
J64  capability filters real + under 3s   PASS (0.08 s worst of 6)
mutation: per-request SQL                  FAIL as required (16.7 s)
mutation restored                          PASS (0.06 s)
```

Harness: `bash scripts/verify_phase2.sh` (J64 runs when `:5055` is up).

## Files touched

- `simulator_api.py` — snapshot + filtered capability
- `serve.py` — move capability off fixture; background warm; trucks tagged
- `prediction_api.py` — retrain clears snapshot
- `templates/simulator.html` — IWIP checkbox default checked
- `static/js/main.js` — Apply debounce
- `static/js/api.js` — load generation counter + timing log
- `test_capability_filters.py` — J64
- `scripts/audit_filters.py` — black-box filter matrix
- `scripts/verify_phase2.sh` — J64 wired
