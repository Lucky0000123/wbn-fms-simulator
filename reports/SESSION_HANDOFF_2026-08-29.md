# WBN FMS Simulator — session handoff, 2026-08-29

Everything below is committed and pushed to **both** remotes (`origin`, `mirror`).
Last commit at handoff: `7cbba39`.

---

## 1. Ground rules the owner has set (do not re-litigate)

| Rule | Detail |
|---|---|
| **One clock** | Total haulage target is a constant **17,003,193 t** (20 M − 3 M LGS POS). Monthly targets are that sales line *distributed in the plan's shape* (`_rescale_cards_to_sales`), so months sum exactly to the year. The saves' internal fleet-credited sums must never headline. |
| **Targets are goals, not ceilings** | LIM-LD may run above its line. SAP is fixed per scenario and must never exceed its line. |
| **The YEAR is the judged line** | Not each month. A month may read >100% while the year sits on 100%. |
| **Act only above 103%** | A month at 101% is fine and is left alone. |
| **Option 1 only — PARK** | Surplus LIM-LD trucks are **parked**. They are NOT re-routed to FeNi KM0 or anywhere else. Option 2 (redistribution) was explicitly dropped on 2026-08-28. |
| **Contractor walls** | RIM works BLB + TF only. SMA works KR + TF only. BLB is RIM-only, KR is SMA-only, TF is open. A truck never changes contractor. |
| **Fleet must not shrink** | Sep 581 · Oct 931 · Nov 1,280 · Dec **1,281** DT (RIM 961 + SMA 320). |
| **POS 6 reclaims to HUAFEI** | Not FeNi (owner ruling 2026-08-28). 7.4 km, not 55.8. |
| **Green only at ≥100%** | No amber/red judgement below. |
| **No "old predictions"** anywhere | Plain "Predicted plan". |
| **Discrepancies recorded, not corrected** | e.g. the 990 kt ≠ 1 Mt note in S5.json. |

## 2. The four scenarios

| Day file | Name | What it is |
|---|---|---|
| `2026-MM-03` | 3.0.1 (S3) | base mining plan, all leftover LD to HUAFEI/BSE |
| `2026-MM-04` | 3.0.2 (S4) | base + POS 6 half-split from October |
| `2026-MM-05` | 3.1.1 (S5) | +330 kt/mo BLB LIM Oct–Dec, no split |
| `2026-MM-06` | 3.1.2 (S6) | 3.1 + POS 6 half-split |

Sales lines: SAP 5,718,686 always. 3.0.x → TOS 3,650,201 / LD 7,634,306.
3.1.x → TOS 4,640,201 / LD 6,644,306. Both families total 17,003,193.

## 3. Current state of the plans (all frozen, verified)

Year coverage vs the 17.0 Mt line:

| Scenario | Together | SAP | LIM-TOS | LIM-LD (adjusted) | DT parked to reach it |
|---|---|---|---|---|---|
| 3.0.1 | 98.4% | 100.6% | 100.5% | 95.8% (under) | **0** |
| 3.0.2 | 101.7% | 100.6% | 100.6% | 100.0% | **70** (Dec) |
| 3.1.1 | 101.7% | 100.4% | 100.3% | 100.0% | **79** (Dec) |
| 3.1.2 | 104.8% | 100.6% | 100.4% | 100.1% | **235** (Sep 3 · Oct 6 · Nov 64 · Dec 162) |

December fields the full 1,281 DT in every scenario. POS 6 split is exactly
50/50 per contractor in the .2 books.

## 4. What the Excel books contain (audited 2026-08-29, all pass)

Sheets: `Year · Road crowding · Paths · Sep · Oct · Nov · Dec · Saturation`

- **Year sheet**: 17,003,193 sales target, four coverage KPIs (LIM-LD
  headlines the *adjusted* figure with a "was" line), scenario constraints
  panel at column G, **DT TO PARK box** under it (per month + TOTAL),
  LIM-LD year-adjustment block, road corridor, saturation.
- **Month sheets**: DT box at N1 (`DT USED THIS MONTH: 1,281`, contractor
  split, and the parking line), materials, path table in A–L, and — where
  trucks are parked — **NEW PREDICTED PLAN table beside it from column N**,
  same starting row, with the red donor row, PARKED row, and NEW % of target
  with a "was" line.
- **Weighbridge column** is last and compact: `T13 - 35% - 1min · T6 - 29% - 1min`.
- **Road crowding** names the whole road: `ON THIS ROAD: 2,802 DT total =
  1,462 ours + 1,340 other tenants (POSITION, HUAFEI>RSF, PMA, MHM, HSM,
  KR>RSF)`.

Files ready in `~/Downloads`:
`plan_2026_S3_0_1.xlsx`, `plan_2026_S3_0_2.xlsx`, `plan_2026_S3_1_1.xlsx`,
`plan_2026_S3_1_2.xlsx` (all regenerated 2026-08-29 08:15).
Side workbook: `reports/scenario_comparison_dec_options.xlsx`
(sheets: Compare · Year adjustment · Insights).

## 5. Dashboard (`/monthly`)

- Year board defaults to **3.0.1**, not the stale S1 day-01 family.
- Material cards: LIM-LD headlines the adjusted %, with "was, before
  adjustment" beneath.
- **DT to park panel** under the cards, following the scenario selector.
- `/api/monthly/year-board` returns `ld_adjust` with the whole calculation.

## 6. How to work this repo

- Server: `.venv/bin/python serve.py` on **:5055**.
- Refreezes go through the **real UI flow** (Load → Unlock → Check capacity →
  Allocate → Save) using a copy of `scripts/refreeze_s4_pos6.py` with DATES
  swapped; run detached with `nohup` (background bash caps kill >600 s), and
  raise the allocation poll to 900 s for heavy months.
- Saved plans live in `data/saved_plans/YYYY-MM-DD.json` and are **gitignored**
  by design — code changes get committed, plan data does not.
- Gates: `scripts/check_scenarios.py` (J72) and
  `scripts/check_qa_2026_08_25.py` (51/51). Both green at handoff.
- Other agents work this repo in parallel: commit only your own hunks.
- Push to **both** remotes every time.

### Trap that cost time (do not repeat)
`planRestoreAllocation()` sets `r.dt = saved.dt_before` when a plan loads.
To change a frozen plan's fleet you must patch **three** places or the edit
silently reverts: `paths[key].dt`, `paths[key]._preAlloc.dt`, **and**
`allocation.rows[].dt_before`.

## 7. Open items

- POS 12–KM15 runs RED on the tenant basis — the HUAFEI→RSF 500 DT figure
  is unverified (real or overstated?).
- R5 moving-bottleneck platooning, R6 GBM residual layer (20% → ~15% MAPE).
- Owner mentioned "changes we made in our file" — a new matrix paste may come.

## 8. Backups

`/tmp/dec1281_backups/`, `/tmp/limtos_backups/`, `/tmp/ld17_backups/`,
`/tmp/table_backups/`. Builder scripts: `/tmp/build_year_sheet.py`,
`/tmp/rebuild_dec_frozen.py`, `/tmp/refreeze_all16.py`.
