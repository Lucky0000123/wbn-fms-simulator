# Tab 1 quality check — Capability & Scenario

**Date:** 2026-07-31  
**HEAD:** `4a42330`  
**Mode:** live DB (`dataMode=database`)  
**Method:** API probes + Playwright browser + SQL spot-checks against `DISPATCH RESULTS LITE 2`  
**Machine evidence:** `reports/tab1_quality_check.json`, screenshots `reports/tab1_qc_*.png`

---

## Verdict

| | Count |
|---|---|
| Working | Most of the tab — filters, KPIs (tonnage/fleet), tables, 3D scatter, flow planner, monthly chart |
| **Must fix** | ~~Trip eff vs plan~~ → **FIXED 2026-08-01** (`_planned_trip_counts`, gate J65) |
| Should fix | 2 remaining — rain cold load (~15s), weighbridge-summary frozen twin (looks live) |
| Done this pass | Trucks fixture disclosed in UI; IWIP empty-state copy; KPI clamp &gt;200% |
| Acceptable / known | Cold snapshot ~17–20s once per process; warm Apply &lt;1s |

**Bottom line:** Filters and tonnage KPIs work. Trip-eff / Plan-tr/DT aggregation is fixed in code (offline J65 mutation-tested). Re-verify live HTTP asserts when SSD/VPN is back (`dataMode=database`).

---

## Section map (what Page 1 is)

| # | Section | Data source | Re-fetches on Apply? |
|---|---|---|---|
| 0 | Top filter bar | → capability | Yes |
| 1 | Scope line + Actual/Plan | capability `kpi` | Yes |
| 2 | Six KPI cards | capability `kpi` | Yes |
| 3 | Fleet requirement calculator | capability `kpi.tPerDT` | Yes |
| 4 | Efficiency / 3D scatter + scenario | capability `daily` / `dailyByPath` | Yes (client re-agg) |
| 5 | Haul-road flow planner | capability + constraints + wb-positions | Partial |
| 6 | Shift Performance / zones / findings | client from scatter selection | Client |
| 7 | Weighbridge Load strip | `/api/weighbridge-summary` (+ shift-context on scenario) | **No** |
| 8 | Rainfall Impact by Route | `/api/simulator/path-response` | **No** (once at init) |
| 9 | IWIP Traffic Impact | shift-context after scenario select | **No** (date bar) |
| 10 | Monthly trend | capability `months` | Yes |
| 11 | Contractor / Routes / Dest tables | capability | Yes |
| 12 | Trucks used | `/api/simulator/trucks` **fixture** | Yes (but ignores filters) |

---

## MUST FIX

### C1 — Trip efficiency vs plan is wrong (CRITICAL)

**Symptom (browser):** KPI card showed **1770% TRIP EFF VS PLAN** on 2026-07-01→07-31 incl IWIP. Wide window API returns **effTrip ≈ 26.5× (2649%)** while **effWMT ≈ 94%** — inconsistent on its face.

**Cause:** In `DISPATCH RESULTS LITE 2`, column `[TARGET TRIP]` is already a **rate** (planned trips per DT), e.g. `8.0`, `4.8`, `6.0` on July rows — matching actual `RIT/NB_DT` (~7.9 when target is 8).

Live code stores raw `TARGET TRIP` in `_ptr` and then:

```python
planTripsPerDT = ptr / pdt   # SUM(TARGET TRIP) / SUM(DT PLAN)  ← wrong
effTrip = tripsPerDT / planTripsPerDT
```

SQL proof (rows with both TARGET TRIP and DT PLAN present):

| Window | Actual trips/DT | Bug `ΣTARGET/ΣDT_PLAN` | Correct `Σ(TARGET×DT_PLAN)/ΣDT_PLAN` | Fixed effTrip | Live effWMT |
|---|---|---|---|---|---|
| Wide excl IWIP | 3.96 | **0.151** | **4.37** | **0.91 (91%)** | 0.88 |
| July (with plan) | 4.27 | **0.225** | **4.67** | **0.91 (91%)** | 0.85 |
| Fixture capture (old) | 4.06 | — | 4.61 | 0.88 | 0.91 |

Live API today still serves the bug path → KPI **1770–2649%**.

So every **Plan tr/DT**, **Trip eff**, and the red/green trip-eff cells in contractor/route tables are polluted.

**Fix (shipped 2026-08-01):** `_planned_trip_counts(rate, plan_dt)` stores `TARGET × DT_PLAN` in `_ptr`. Gate **J65** (`test_plan_trip_rate.py`) — offline unit always runs; live asserts when DB up. Mutation: helper returns raw rate → planTripsPerDT=0.24, effTrip=26.7 → FAIL.

**UI clamp:** KPI cards and `eff()` table cells show “—” if eff &gt; 200% or &lt; 0%.

**Live re-check needed** when VPN is up: July+IWIP `effTrip` should be ~0.9 (was 17.7).

---

## SHOULD FIX

### S1 — Rainfall table takes ~15–18s to appear

- `/api/simulator/path-response` cold ~14–18s; UI stays on “Loading rainfall-matched route history…”.
- Data is real when it lands (mDry/mWet present; e.g. TF→POS 11 −20.2% rain-sensitive).
- Endpoint **does** respond to date args, but **Apply does not re-fetch** it — date bar changes KPIs while rain table stays on the init window.
- **Fix:** same whole-view snapshot pattern as capability; optionally re-call on Apply.

### S2 — Weighbridge summary is a frozen twin of the fixture

| Field | Live response | Committed fixture |
|---|---|---|
| bridges / trucks / busiest / share / date | 6 / 185 / 11 / 51.4% / **2026-07-09** | **identical** |
| `servedFrom` | `null` (looks live) | — |

Operator sees “latest” bridge activity; it is the capture frozen at 2026-07-09 with **no disclosure**. `otherShare: 100%` is also suspicious.

**Fix:** either query fresh data and tag date, or set `servedFrom: "fixture"` / `stale: true` when serving the twin.

### S3 — Trucks table ignores filters and does not say so in the UI

- API correctly tagged `servedFrom: "fixture"` (2000 rows).
- UI shows “2000 trucks” with no “sample / unfiltered” note.
- Changing date/IWIP/source does not change the list (verified identical digests).

**Fix:** banner under “Trucks used”: *Sample fleet list — not filtered by the bar above.*

### S4 — IWIP Traffic panel empty on first paint

- After load: “No FENI-bound routes with history yet.”
- Needs a scatter scenario / shift-context date; path-response must already be loaded.
- Easy to read as “no IWIP data in DB”.

**Fix:** copy → “Select a scenario point on the chart to estimate IWIP impact for that shift.”

---

## WORKING (verified)

### Filters (top bar)

| Control | Status | Evidence |
|---|---|---|
| Date from/to | **Works** | 323 days → 20 days; scope echoes request |
| Exclude IWIP (default checked) | **Works** | checked=true; excl 121k vs incl 166k t/day; uncheck → “incl IWIP” |
| Types | **Works** | reduces tonnage; menu keeps all types in window |
| Source / Dest | **Works** | TF-only / FENI KM0-only paths |
| Apply latency (warm) | **Works** | **0.94s** incl 500ms debounce; API warm **0.05–0.08s** |
| Cold first capability | Slow once | **~19.8s** if snapshot not warm — background warm usually hides this |

### KPI cards (except trip eff)

| Metric | Status | Wide excl IWIP |
|---|---|---|
| WMT / day | OK | 121,084 |
| DT / day | OK | 670 |
| Trips/DT | OK | 4.00 |
| t/DT productivity | OK | 181 |
| WMT vs plan (effWMT) | OK | ~94% wide |
| Trip eff vs plan | **BROKEN** | see C1 |
| Actual ↔ Planned toggle | OK | labels swap; numbers move |

Arithmetic checks: `wmtPerDay ≈ Σ path.t / days`, `tf = t/trips`, `tripsPerDT = trips/dt` — pass.

### Fleet calculator

OK — productivity and “trucks needed” populate (e.g. 121084 ÷ 181 ≈ 671).

### Charts / scenario

| Piece | Status |
|---|---|
| Combined 3D scatter | Renders (1331 SVG nodes); paths coloured; scenario select works |
| Monthly trend | Renders (98 nodes) |
| Flow planner | Present; attain/prod/V/C/queue fill (e.g. 1,397 trips, 63k t, V/C 2.91) |
| Shift assessment / capacity zones | Renders after data (findings text + 2 zone rows) |
| Constraint sections / path filters | Client-side; no reload (by design) |

### Tables

| Table | Rows (wide) | Filtered? |
|---|---|---|
| Contractors | 10 | Yes |
| Routes | 67 | Yes |
| Destinations | 15 | Yes |
| Trucks | 2000 | **No** (fixture) |

Canonical names: no stale `FENI A` / `HUAFEI.C01` in live paths (POS 12 etc. are valid).

### Rain (once loaded)

Real matched wet/dry rows; not a stub. Timing and Apply re-scope are the gaps (S1).

---

## Priority fix list

| Pri | ID | Issue | Effort |
|---|---|---|---|
| P0 | C1 | Fix `TARGET TRIP` aggregation → sane Plan tr/DT & Trip eff | S (one accumulator change + gate) |
| P1 | S2 | Tag or refresh weighbridge-summary | S |
| P1 | S1 | Snapshot/cache path-response; optional Apply refresh | M |
| P2 | S3 | Disclose trucks fixture in UI | XS |
| P2 | S4 | IWIP empty-state copy | XS |
| P3 | — | Persist capability snapshot to `data/` so first hit after restart &lt;2s | M |

---

## What not to “fix”

- Congestion tab / plan tabs — out of scope for this Page 1 pass.
- Trucks not filterable — honest omission until a TRUCK_ID source exists; only disclosure is missing.
- Rain/WB not moving on Apply — document until S1/S2 done; do not claim they follow the date bar.
- Availability / congestion in tonnage — still correctly out (J52/J53); Tab 1 does not reintroduce them.

---

## Suggested gate (when fixing C1)

```text
J65  planTripsPerDT is a weighted TARGET TRIP rate, not SUM(rate)/SUM(DT)
     — wide excl-IWIP: 0.5 <= planTripsPerDT <= 10
     — effTrip in [0.3, 2.0] when planWmt > 0
     — mutation: restore SUM(TARGET)/SUM(DT PLAN) → fail
```

---

## Screenshots

- `reports/tab1_qc_top.png` — KPIs (shows 1770% trip eff bug)
- `reports/tab1_qc_scatter.png` — 3D + flow planner
- `reports/tab1_qc_bottom.png` — lower tables

## Raw check log

`reports/tab1_quality_check.json` — 79 automated checks (75 pass / 2 fail / 2 warn; one “fail” was a bad assertion on POS 12 naming, not a product bug).
