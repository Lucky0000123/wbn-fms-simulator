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

**Fixed routes (always running):**
| Route | Material | Target | Type |
|-------|----------|--------|------|
| BLB → FeNi KM0 | SAP | 10,000 t/day | FIXED |
| TF → FeNi KM15 | SAP | 10,000 t/day | FIXED |

**Overflow routes (fill the remaining SAP target):**
| Route | Material | Rule |
|-------|----------|------|
| BLB → FeNi KM15 | SAP | After the 10,000 t/day to FeNi KM0 is filled, remaining SAP trucks from BLB go to FeNi KM15 to fulfill the total SAP target |
| TF → FeNi KM0 | SAP | After the 10,000 t/day to FeNi KM15 is filled, remaining SAP trucks from TF go to FeNi KM0 to fulfill the total SAP target |

The total SAP target per day is set by the monthly plan. The fixed 10,000 t/day routes fill first, then remaining SAP target is split across the overflow routes.

### P2 — LIM-TOS (Limonite to TOS stockpile, second priority)

**Rule:** LIM-TOS always goes to HUAFEI.

| Route | Material | Target | Notes |
|-------|----------|--------|-------|
| BLB → HUAFEI | LIM-TOS | 250,000 t/month | 1 Mt over 4 months (Sep-Dec) |
| Other pits → HUAFEI | LIM-TOS | Calculated | Contribute to reach 4.6 Mt total |

Total LIM-TOS from ALL pits = 4.6 Mt. BLB adds 1 Mt (250 kt/month × 4 months). Other pits contribute the remaining 3.6 Mt.

P2 fills after P1 is fully satisfied. If P1 SAP target requires more trucks than available, P2 does not get trucks.

### P3 — LIM-LD (Limonite long-distance haul, third-priority target)

**Rule:** After P1 and P2 are fully satisfied, allocate DT to the supplied
LIM-LD target. If no LIM-LD target is supplied, the route remains the
lowest-priority capacity sink for leftover trucks. Production above a supplied
P3 target is reported separately as excess capacity, not credited to target.

The leftover DT are split:
- 50% of leftover DT → TF → HUAFEI / BSE
- 50% of leftover DT → TF → POS 6

(Owner, 2026-08-25: the split leg moved from POS 12 to POS 6 — the km 12.0
yard on the lower mainline. POS 6 is a longer haul than POS 12 (55.8 km vs
40.8 from TF), so expect fewer trips/DT on the split rows and more traffic
through sections S2–S4.)

This half/half split is the S4 concept — a what-if to see how much tonnage increases when trucks are split across destinations instead of all going to one.

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
1. Calculate the total material going INTO POS from all pits (based on the plan).
2. The total material going OUT of POS to FeNi plants must equal the input.
3. Allocate IWIP dump trucks to move material from POS to FeNi.
4. The number of IWIP trucks is calculated from the required daily tonnage and the model's trips/DT prediction for each POS → FeNi route.
5. These IWIP trucks must be added to the plan as additional rows so they are counted in the road congestion calculation.
6. IWIP trucks are separate from contractor (SMA/RIM) trucks.
7. There is no fixed tonnage for POS → FeNi — it is calculated from the plan output. The 15,000 t/day mentioned in early discussions was an example only, not a fixed target.

### POS → FeNi routes to include:
- POS 12 → FeNi KM0
- POS 12 → FeNi KM15
- POS 14 → FeNi KM0 (if POS 14 receives material)
- POS 15 → FeNi KM0 (if POS 15 receives material)
- POS 16 → FeNi KM0 (if POS 16 receives material)

Only add a POS → FeNi route if that POS dump actually receives material in the plan.

---

## 6. Production Targets

| Target | Value | Period | Material |
|--------|-------|--------|----------|
| Total LIM-LD | 8 Mt | Sep-Dec 2026 (4 months) | Limonite, long-distance |
| Total LIM-TOS (all pits) | 4.6 Mt | Sep-Dec 2026 | Limonite to TOS |
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
LIM-TOS target met:  [YES/NO]  (target: 4.6 Mt, actual: X Mt)
LIM-LD total:        X Mt  (target: 8 Mt)  [PASS/FAIL]
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
