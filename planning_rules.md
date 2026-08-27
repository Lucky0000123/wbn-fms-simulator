# WBN-FMS Planning Rules

> Source: Mine Operations Manager, 2026-08-21
> Status: ACTIVE — all S3 plans must follow these rules
> The app reads this file when building plans and enforces every rule below.

---

## 1. Scenario Selection

- Run ONLY Mine Plan 3 (S3).
- Do NOT run Scenario 2 (S2) — it has been deleted from the app.
- Always reach the production target for TOS SAP and TOS LIM.

---

## 2. Terminology

| Term | Meaning |
|------|---------|
| TOS | Temporary Ore Stockpile — material is stored here temporarily, then loaded and moved to processing plants (FeNi KM0, FeNi KM15) |
| POS | Permanent Ore Storage — permanent stockpile where ore is saved long-term |
| SAP | Saprolite ore (high-grade nickel) — highest priority, must move first |
| LIM-TOS | Limonite ore going to TOS stockpile — second priority |
| LIM-LD | Limonite ore going to LD (long-distance) haul — third priority; a supplied target is filled after SAP and LIM-TOS |
| FeNi KM0 | Ferronickel plant at KM 0 |
| FeNi KM15 | Ferronickel plant at KM 15 |
| HUAFEI | Huafei stockpile area (TOS destination for LIM) |
| BSE | BSE stockpile area |
| POS 12 | POS dump number 12 (permanent ore storage) |
| POS 6 | POS yard at mainline km 12.0 (surveyed; site language often says "km 10"). Dump AND kilnable-ore loading point on the lower mainline, inside section S4 |
| IWIP | IWIP-owned dump trucks (not contractor trucks) |

---

## 3. Contractors

| Pit | Allowed Contractor | Rule |
|-----|-------------------|------|
| BLB | RIM | Only RIM trucks allowed on BLB routes. No SMA. |
| KR  | SMA | Only SMA trucks allowed on KR routes. No RIM. |
| TF  | Both | No restriction — leftover DT from both contractors land here. |

The plan builder must enforce these contractor assignments. If a plan row has origin=BLB, contractor must be RIM. If origin=KR, contractor must be SMA.

**Truck mobility (owner, 2026-08-21).** These walls are about where each
fleet's trucks may physically work — trucks never change owner:

- SMA trucks may work **KR and TF only**. Extra SMA trucks from KR move to
  TF, never to BLB.
- RIM trucks may work **BLB and TF only**. Extra RIM trucks move between
  BLB and TF, never to KR.

If a plan carries trucks on a pit their contractor cannot enter (old plans
did: cross-contractor rescues before 2026-08-21 only walled BLB, leaving
rows like KR>HUAFEI · RIM), the allocator must move those trucks back to a
legal pit (TF) and redistribute them — never rename the contractor, and
never refill the illegal row.

---

## 4. Priority Allocation System

Material is allocated in strict target order. P1 fills first, P2 fills second,
then P3 fills its supplied target. Fleet beyond all supplied targets remains
visible as excess LD capacity; it must not be counted as target production.

### P1 — SAP (Saprolite, must-move, highest priority)

**Buffer routes (SAP → POS, capped at 2,000 t/day each):**
| Route | Material | Target | Type |
|-------|----------|--------|------|
| BLB → POS 14 | SAP | 2,000 t/day | BUFFER |
| TF → POS 12 | SAP | 2,000 t/day | BUFFER |
| KR → POS 12 | SAP | 2,000 t/day | BUFFER |

(Owner, 2026-08-26, correcting the inverted 2026-08-25 rule: "around 2,000 wmt
goes to POS, the REST goes direct to FeNi as per plans — same for all pits."
The previous day had it backwards: 2,000 to FeNi, rest to POS.)

Landing on a BUFFER row anywhere in **0–4,000 t/day** is acceptable
(2,000 ± 2,000) because trucks are integers. Do not chase an exact 2,000.

**Direct routes (remaining SAP → FeNi, per the mine plan's own destinations):**
| Route | Material | Target | Type |
|-------|----------|--------|------|
| BLB → FeNi KM0 | SAP | remaining | DIRECT |
| TF → FeNi KM15 | SAP | remaining | DIRECT |
| KR → FeNi KM15 | SAP | remaining | DIRECT |

The pit's SAP target for the day is set by the monthly plan. The 2,000 t/day
POS buffer fills first; everything left from that pit goes DIRECT to FeNi.
The FeNi destination follows the mine-plan matrix: each pit ships to the FeNi
plant its own plan rows name (today BLB → KM0, TF → KM15). If a pit's plan
carries rows to BOTH FeNi plants, split the rest pro-rata to those rows. KR's
matrix has no FeNi SAP row, so its rest follows its corridor's most-used
direct haul, FeNi KM15 (dispatch history: 375 KR→KM15 direct rows vs 214 KM0).

POS is transit, not a sink: tonnes into POS must leave POS on IWIP reclaim
(POS → FeNi), sized so input = output (§5). Under this rule only the ~2,000
buffer per pit flows through POS, so reclaim fleets are small.

**Reject rates (planning team, 2026-08-26):** DT dimensioning stays on ROM
material. Saleable SAP = ROM minus contractual reject: 0% for Tofu, 7% for
BLB and KR. Saleable LIM has no reject. Owner ruling (2026-08-26, after
lunch-time instruction): scenario targets are set EQUAL to the sales table
(Saprolite TOS 5,718,686 / Limonite TOS 4,640,201 wmt declared) — the
imported mineplan's 5,754,873 SAP was scaled ×0.99371 to match. The
saleable-after-reject line in the validation summary remains an estimate of
what those hauled tonnes sell as.

### P2 — LIM-TOS (Limonite to TOS stockpile, second priority)

**Rule:** LIM-TOS always goes to HUAFEI.

| Route | Material | Target | Notes |
|-------|----------|--------|-------|
| BLB → HUAFEI | LIM-TOS | 250,000 t/month | 1 Mt over 4 months (Sep-Dec) |
| Other pits → HUAFEI | LIM-TOS | Calculated | Contribute to the scenario total |

Owner, 2026-08-27: the sales table's LIM-TOS 4,640,201 wmt is the
**scenario 3.1** total — it already CONTAINS the ~1 Mt addition (330,000
t/month extra BLB LIM in October–December). Scenario 3.0 runs without that
addition at **3,650,201** wmt. One number per scenario, never mixed.

P2 fills after P1 is fully satisfied. If P1 SAP target requires more trucks than available, P2 does not get trucks.

### P3 — LIM-LD (Limonite long-distance haul, third-priority target)

**Rule:** After P1 and P2 are fully satisfied, allocate DT to the supplied
LIM-LD target. If no LIM-LD target is supplied, the route remains the
lowest-priority capacity sink for leftover trucks. Production above a supplied
P3 target is reported separately as excess capacity, not credited to target.

The leftover DT are split:
- 50% of leftover DT → TF → HUAFEI / BSE
- 50% of leftover DT → TF → POS 6
- Split starts October (from month 10). September leftovers all go HUAFEI/BSE.

(Owner, 2026-08-25: the split leg moved from POS 12 to POS 6 — the km 12.0
yard on the lower mainline. POS 6 is a longer haul than POS 12 (55.8 km vs
40.8 from TF), so expect fewer trips/DT on the split rows and more traffic
through sections S2–S4. Planning team, 2026-08-26: the split begins in
October — September behaves like the no-split scenario.)

This half/half split is the x.x.2 hauling concept (scenarios 3.0.2 / 3.1.2;
formerly called S4) — a what-if to see how much tonnage increases when trucks
are split across destinations instead of all going to one.

If there are not enough trucks to fill P1 and P2, P3 may receive zero trucks.
P3 is the first donor if P1 or P2 needs more trucks. Once P1 and P2 are met,
targeted P3 rows take precedence over untargeted LD capacity.

---

## 5. POS Transit Balance

POS is a transit stockpile. Material flows through it:

```
Pits (BLB, KR, TF) → POS dumps (12, 14, 15, 16) → FeNi plants (KM0, KM15)
                       (input = output)
```

### Rules:
1. Calculate the total material going INTO POS from all pits (based on the plan), including SAP sent to POS as the §4 buffer.
2. The total material going OUT of POS to FeNi plants must equal the input. IWIP reclaim WMT = inbound POS WMT.
3. Allocate IWIP dump trucks to move material from POS to FeNi.
4. The number of IWIP trucks is calculated from the required daily tonnage and the model's trips/DT prediction for each POS → FeNi route.
5. These IWIP trucks must be added to the plan as additional rows so they are counted in the road congestion calculation.
6. IWIP trucks are separate from contractor (SMA/RIM) trucks.
7. There is no fixed tonnage for POS → FeNi — it is calculated from the plan output. The 15,000 t/day mentioned in early discussions was an example only, not a fixed target.

### POS → FeNi routes to include:
- POS 12 → FeNi KM0
- POS 12 → FeNi KM15
- POS 6 → FeNi KM0
- POS 6 → FeNi KM15
- POS 14 → FeNi KM0 (if POS 14 receives material)
- POS 15 → FeNi KM0 (if POS 15 receives material)
- POS 16 → FeNi KM0 (if POS 16 receives material)

Only add a POS → FeNi route if that POS dump actually receives material in the plan.

---

## 6. Production Targets

| Target | Value | Period | Material |
|--------|-------|--------|----------|
| Total LIM-LD | 6.644306 Mt | Sep-Dec 2026 (4 months) | Limonite, long-distance |
| Total LIM-TOS (all pits) | 3.650201 Mt (3.0) / 4.640201 Mt (3.1) | Sep-Dec 2026 | Limonite to TOS |
| BLB LIM-TOS contribution | 1 Mt (250 kt/month) | Sep-Dec 2026 | Limonite from BLB to HUAFEI |
| SAP daily target | Per monthly plan | Daily | Saprolite to FeNi plants |

---

## 7. Validation Checks (Post-Run)

After running S3, the app must display these validation checks:

### BLB Routes
- BLB trips/DT to any destination should be 6-7 per day.
- A drop below 6 is a warning. Below 5 is a red flag.
- 6-7 trips/DT is the expected range for BLB's short haul (6.7 km to POS 14).

### TF Long-Haul Routes (HUAFEI, BSE, POS 12, POS 6)
- TF trips/DT must not go below 1.5 per day.
- Below 1.5 is not believable.
- Below 1.0 is impossible.
- If the model shows below 1.5, flag it as a WARNING in the results table.
- If below 1.0, flag as IMPOSSIBLE.

### Display
Show a validation summary after each run:
```
VALIDATION SUMMARY
==================
SAP target met:      [YES/NO]  (target: X t/day, actual: Y t/day)
LIM-TOS target met:  [YES/NO]  (target: scenario total, actual: X Mt)
LIM-LD total:        X Mt  (target: 6.64 Mt)  [PASS/FAIL]
POS transit balanced: [YES/NO]  (input: X t, output: Y t)
```

---

## 8. Output Format

The S3 results table must show these columns for every route, every month:

| Column | Description |
|--------|-------------|
| Month | Sep / Oct / Nov / Dec |
| Path | Origin → Destination (e.g., BLB → POS 14) |
| Contractor | RIM, SMA, or IWIP |
| Material | SAP, LIM-TOS, LIM-LD |
| Priority | P1, P2, or P3 |
| DT | Number of trucks allocated |
| Loaders | Number of loaders (proportional default) |
| Trips/DT | Trips per truck per day |
| WMT/DT | Tonnes per truck per day |
| WMT/day | Total tonnes per day on this route |
| Cycle (min) | Cycle time in minutes |
| Bottleneck | Road, Loader, or None |
| Status | Normal, Congested, Overloaded |
| Validation | PASS, WARN, or FAIL (only for BLB and TF routes) |

---

## 9. Monthly Summary

After the detailed tables, show a monthly summary:

| Month | SAP t/day | LIM-TOS t/day | LIM-LD t/day | Total t/day | Monthly Total | LIM-LD 4-mo total | Target met? |
|-------|-----------|---------------|-------------|-------------|---------------|-------------------|-------------|

---

## 10. Rules Enforcement

These rules are not suggestions. The plan builder must:
1. Enforce contractor assignments (RIM on BLB, SMA on KR).
2. Fill P1 (SAP) before P2 (LIM-TOS).
3. Fill P2 before P3 (LIM-LD).
4. Split P3 leftover DT 50/50 between HUAFEI/BSE and POS 6 (owner, 2026-08-25; was POS 12).
5. Calculate POS transit and add IWIP trucks to the plan.
6. Run validation checks and display results.
7. Flag any route that fails the trips/DT validation bands.
8. IWIP DT are the IWIP fleet's own trucks (owner, 2026-08-21). They are
   never taken from, and never counted against, the contractor (RIM/SMA)
   DT pools — the plan's fleet total excludes them.
9. Loaders on every plan row follow the route's historical
   trucks-per-loader average (the measured calibration ratio;
   15 trucks/loader when unmeasured) until a detailed loader plan exists
   (owner, 2026-08-21: "we have to imagine we are using the same number
   of loaders").
