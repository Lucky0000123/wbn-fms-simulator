# GPS Scaling and the Speed-Density Question (Priorities 2 and 3)

*Reproduce with `python scripts/extract_multiday_gps.py`,
`python scripts/snap_multiday.py`, `python scripts/fit_speed_density.py`.*

## Summary

Priority 2 asked for GPS extraction scaled beyond one day. Priority 3 asked for a
segment speed model and a speed-density fit, with permission to report honestly if
truck-count variation was too thin.

The result is two findings that point in opposite directions:

- **Scaling my own GPS snapping is near-hopeless.** Only 4 calendar days carry both
  GPS and haulage, and pooling all of them yields **19 segment observations** with
  **zero** segment/direction cells reaching n≥5. Day X was already the best day
  available.
- **The speed-density fit is answerable after all**, because the site's own
  `FMS_CONGESTION_SEG` holds **36,046 hourly rows over 15.2 days** with speed *and*
  truck count per segment. The fit works, and the answer is that congestion is real
  but too small to model.

## Priority 2: the GPS ceiling is 4 days, and effectively 1

| Table | Window |
|---|---|
| `HAULAGE_IWIP_CLEAN` | 2025-12-27 → **2026-07-09** (535,411 rows) |
| `HAULAGE` | 2021-09-24 → 2026-07-29 (3,509,275 rows) |
| `FMS_GPS_Historical` | 2026-07-15 → 2026-07-20 |
| `FMS_PLAYBACK_TRACK_24H` | 2026-07-29 → 2026-07-30 |

Days with both GPS and haulage: **4** — 2026-07-15, 16, 18, 19.

| Day | Trucks | GPS fixes | Trips | Segment obs |
|---|---|---|---|---|
| 2026-07-15 | 14 | 3,581 | 21 | **0** |
| 2026-07-16 | 15 | 3,580 | 19 | **0** |
| 2026-07-18 | 1 | 172 | 1 | **0** |
| **2026-07-19 (Day X)** | 24 | 11,584 | 26 | **19** |

**Pooling gains nothing**, and the reason is specific rather than a data-quality
excuse. Snapping succeeds on all four days (70–92% of fixes on road), but a segment
speed needs GPS fixes *inside* a trip's weigh-to-weigh window, and the retained GPS
covers only narrow slices: 1.2 h on 07-15, 2.6 h on 07-16, 1.0 h on 07-18, against
8.8 h on Day X. Even on Day X only **7 of 159 trips** have any fix inside their
window.

### The richest GPS day cannot be used

`FMS_PLAYBACK_TRACK_24H` holds **859,198 fixes over 715 plates** on 2026-07-29,
three times Day X. It is unusable: the only trucks with haulage rows that day are
**46 SALES third-party vehicles**, and none carry telematics. RIM's own haulage feed
lags roughly 3 weeks behind the GPS retention window, so the two never line up
while the data still exists.

### The plate join itself is fine

487 of 744 GPS plates (**65.5%**) exist in the haulage ID space, so this is a
*temporal* blocker, not the namespace problem it first resembled.

**Consequence:** segment speeds cannot be backfilled onto the training window
(2026-04-01…06-30). That data is already deleted. Only forward accumulation — a
scheduled job appending the live feed daily — can widen this.

## Priority 3: the speed-density fit, from the site's own table

`FMS_CONGESTION_SEG` supplies what my snapping could not, and my snapping is what
licenses trusting it: the two agree at **r=+0.920** on full transits.

| | |
|---|---|
| Rows | 36,046 hourly (95 segments, 8 roads, 218 hours, 15.2 days) |
| Speed | `SUM_SPD / FIX_N` |
| Density | `TRUCK_N` — distinct trucks per segment per hour |
| Independent check | `SUM_TRAV_MS / TRAV_N` — mean traverse time |

**Density variation is ample**, contradicting the brief's worry: `TRUCK_N` spans
1…69 with 69 distinct values, and 185 of 190 segment/direction cells see ≥5
distinct densities. Thin variation is not the obstacle.

### The fit

Speed and density both centred within segment/direction, so this measures *change
on a given segment* rather than which segments happen to be fast:

| | |
|---|---|
| Slope | **−0.0233 km/h per extra truck** |
| t | **−9.9** (n = 35,006) |
| Within-R² | 0.0028 |
| Traverse-time cross-check | **+0.109 s per extra truck**, same sign |

**Significant, correctly signed, and negligible.** From the emptiest density decile
(1.5 trucks) to the busiest (36.4), speed falls **0.83 km/h — 4.8%** of a 17.3 km/h
mean.

**No saturation threshold.** Slopes by band: −0.083 (1–5 trucks), −0.002 (6–10),
−0.002 (11–20), +0.008 (21–35), −0.016 (36–100). Speed does not collapse at high
density, so there is no truck count for a planner to stay under.

Not an artefact of hour or direction: hourly mean density vs mean speed is
**+0.173**, and both directions agree (down −0.025, up −0.022). By road, only CRD
(−1.09% per 5 trucks) and TF (−0.94%) reach even 1%, and BLB has the *wrong* sign
(+1.19%, t=+2.5).

### Congestion in the whole cycle has the wrong sign

Road speed is only ~32% of the cycle, so congestion could hide in queueing instead.
It does not show up there either — it shows up **backwards**:

| Construction | Result |
|---|---|
| `corr(trucks_on_route, cycle_time_min)` | **−0.1467** (483,425 trips) |
| Previous turn's independent construction | −0.1293 — **replicated** |
| Within-route slope, cycle vs trucks | **−0.252 min per extra truck** (t=−7.5) |

More trucks means *shorter* cycles. That is not congestion; it is **endogeneity**.
Dispatch sends trucks to routes that are running well and pulls them off routes
that are struggling, so truck count is chosen in response to conditions. The
correlation measures dispatch behaviour, not road physics. The slope also decays
with band (−1.72 min/truck at 2–10 trucks, −0.23 at 26–60), which is the signature
of selection rather than a physical mechanism.

## Conclusion: no congestion term belongs in the simulator

Three independent lines agree:

1. The physical effect is measurable, correctly signed, and **4.8% at the
   extremes** with no threshold.
2. The trip-level effect has the **wrong sign** and replicates at that wrong sign
   across two constructions.
3. The previous turn's capacity/dwell work already found congestion **NOT
   IDENTIFIABLE**.

Adding a congestion factor would encode dispatch's routing preferences as if they
were road physics. The `trucks_at_source` collision reporting already in the tool
is the right treatment: **show the planner where plans contend, without pretending
to price it.**

## Files

| File | Contents |
|---|---|
| `data/multiday_gps_trips.csv` | 54 usable (day, truck) pairs with fixes, trips, tonnage |
| `data/multiday_segment_speeds.csv` | pooled segment observations across all 4 days |
| `data/congestion_seg_hourly.csv` | 36,046 hourly segment rows with derived speed and traverse time |
| `reports/multiday_gps_summary.json` | the extraction ceiling and its cause |
| `reports/speed_density_fit.json` | the fit statistics |
