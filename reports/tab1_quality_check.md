# Tab 1 quality check — Capability & Scenario

**Date:** 2026-07-31 (closure live-verify 2026-08-01)  
**HEAD:** post-`2f7dc3d` (path snapshot + WB honesty)  
**Mode:** live DB (`dataMode=database`)  
**Method:** API probes + Playwright browser + SQL spot-checks against `DISPATCH RESULTS LITE 2`  
**Machine evidence:** `reports/tab1_quality_check.json`, screenshots `reports/tab1_qc_*.png`

---

## Verdict

| | Count |
|---|---|
| Working | Most of the tab — filters, KPIs (tonnage/fleet), tables, 3D scatter, flow planner, monthly chart |
| **Must fix** | ~~Trip eff vs plan~~ → **FIXED + LIVE-VERIFIED 2026-08-01** (J65; July effTrip ~0.92) |
| Should fix | ~~S1 rain cold / Apply~~ → **FIXED** (J66); ~~S2 WB honesty~~ → **FIXED** (J67) |
| Done this pass | Trucks fixture disclosed; IWIP empty-state copy; KPI clamp &gt;200%; path snapshot; WB stale tag |
| Acceptable / known | Cold capability ~17–20s / path ~14s once per process; warm Apply &lt;1s |

**Bottom line:** P0/P1 Tab 1 items closed. Live: July KPI `planTripsPerDT≈4.7`, `effTrip≈0.92`. Path-response warm 0.00–0.02s; nRows 6332→698→44 under date filter. WB summary reports `ageDays`/`stale` (table ends 2026-07-09; `otherShare=100%` that day is real IWIP workshop mix).

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
| 7 | Weighbridge Load strip | `/api/weighbridge-summary` (+ shift-context on scenario) | No (site-wide latest; now tagged stale) |
| 8 | Rainfall Impact by Route | `/api/simulator/path-response` | **Yes** (Apply → loadPathResp) |
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

**Fix (shipped + live-verified 2026-08-01):** `_planned_trip_counts(rate, plan_dt)` stores `TARGET × DT_PLAN` in `_ptr`. Gate **J65** — offline always; live July `effTrip` in [0.3, 2.0] (measured ~0.92; was 17.7). Mutation: helper returns raw rate → planTripsPerDT=0.24, effTrip=26.7 → FAIL.

**UI clamp:** KPI cards and `eff()` table cells show “—” if eff &gt; 200% or &lt; 0%. Per-path can honestly sit near 2× (e.g. POS 12→POS 12); J65 path check uses &gt;3 to catch the aggregation bug without flaking.

---

## SHOULD FIX

### S1 — Rainfall table takes ~15–18s to appear — **FIXED 2026-08-01**

- `_path_snapshot()` (TTL 300s) + background warm in `serve.py`; warm Apply **0.00–0.02s** (cold `_path_load` still ~14s once).
- `load()` → `loadPathResp()` with `filterParams()` so Apply refreshes the rain panel.
- Gate **J66** (`test_path_response_perf.py`): warm &lt;3s; nRows shrinks 6332→698→44; overlapping path `n` shrinks.

### S2 — Weighbridge summary honesty — **FIXED 2026-08-01**

Live query was always real; table ends **2026-07-09**. `otherShare: 100%` that day is correct (all Chinese IWIP workshop contractors, none in `{RIM,PPP,…}`). Dishonesty was missing age/source.

**Shipped:** `source`, `ageDays`, `stale` (age&gt;3), `staleReason`; UI status shows “as of … (stale — table ends …)”. Gate **J67**.

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
| Trip eff vs plan | **OK** (~91%) | see C1 (fixed) |
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

Real matched wet/dry rows; not a stub. Snapshot + Apply re-fetch closed (S1/J66).

---

## Priority fix list

| Pri | ID | Issue | Status |
|---|---|---|---|
| P0 | C1 | Fix `TARGET TRIP` aggregation → sane Plan tr/DT & Trip eff | **DONE** J65 |
| P1 | S2 | Tag weighbridge-summary source/age/stale | **DONE** J67 |
| P1 | S1 | Snapshot path-response; Apply refresh | **DONE** J66 |
| P2 | S3 | Disclose trucks fixture in UI | Done earlier |
| P2 | S4 | IWIP empty-state copy | Done earlier |
| P3 | — | Persist capability/path snapshot to `data/` so first hit after restart &lt;2s | **DONE** J68 (disk warm ~0.1s) |

---

## What not to “fix”

- Congestion tab / plan tabs — out of scope for this Page 1 pass.
- Trucks not filterable — honest omission until a TRUCK_ID source exists; disclosure is enough.
- `otherShare=100%` on 2026-07-09 — real contractor mix that day, not a fixture twin.
- Availability / congestion in tonnage — still correctly out (J52/J53); Tab 1 does not reintroduce them.

---

## Gates (closed 2026-08-01)

```text
J65  planTripsPerDT is weighted TARGET TRIP rate; July effTrip ~0.9 (was 17.7)
J66  path-response snapshotted; warm <3s; date filter shrinks nRows / path n
J67  weighbridge-summary discloses source, ageDays, stale when age>3
```

---

## Screenshots

- `reports/tab1_qc_top.png` — KPIs (shows 1770% trip eff bug)
- `reports/tab1_qc_scatter.png` — 3D + flow planner
- `reports/tab1_qc_bottom.png` — lower tables

## Raw check log

`reports/tab1_quality_check.json` — 79 automated checks (75 pass / 2 fail / 2 warn; one “fail” was a bad assertion on POS 12 naming, not a product bug).
