# Does road-maintenance (HRM) activity change haulage productivity?

*2026-07-31. `scripts/hrm_impact.py`, `reports/hrm_impact.json`. Gate `J62`.*

## Answer

**No measurable impact.** Controlling for route and fleet size, HRM activity on
the sections a haul crosses has essentially **zero** correlation with that haul's
trips per truck:

| Test | r | p | n |
|---|---|---|---|
| Within-route, controlling fleet — **HRM units** | **−0.0006** | 0.99 | 389 |
| Within-route, controlling fleet — **HRM hours** | **+0.0006** | 0.99 | 389 |
| Fleet-matched bins (the owner's method) | −0.060 | 0.28 | 342 |
| Partial correlation, controlling fleet | −0.050 | 0.32 | 389 |

Four controlled tests, none significant, and the two best-controlled ones are
not merely non-significant — they are **zero to four decimal places**. The
owner's prior ("I don't think tbh, but just validate") is supported.

**HRM should not be added as a feature to the cycle model.**

## The result I nearly published, and why it was wrong

The first pass produced a strong, highly significant finding:

> HRM hours vs trips/DT, controlling fleet size: **r = −0.4604, p = 8.4 × 10⁻²²**

More road maintenance, sharply less production. It is significant at twenty-two
zeros, it has an obvious causal story (crews and equipment on the road obstruct
haulage), and it is **entirely an artifact of route length**.

`hrm_hours` is summed over the sections a route spans. A long route crosses more
sections, so it accumulates more HRM hours *by being long*. A long route also
completes fewer trips per truck *by being long*. Measured on this panel:

| | r | p |
|---|---|---|
| `span_km` ↔ `hrm_hours` | **+0.631** | 1.2 × 10⁻⁴⁴ |
| `span_km` ↔ `trips_per_dt` | **−0.629** | 3.6 × 10⁻⁴⁴ |

Two correlations of ±0.63 through a shared cause produce a spurious correlation
of about −0.40 between the outcomes. The "effect" was −0.46. There is nothing
left to explain.

Controlling for fleet size did not help, because fleet size is not the confound.
The confound is the road itself. The fix is to remove the route entirely:
demean HRM activity and trips/DT **within each route**, so the only variation
left is day-to-day change on the same road, and *then* control fleet size. The
effect disappears completely (r = ±0.0006).

Note that `hrm_units` — a count of distinct machines rather than a sum of hours —
was **not** confounded (`span_km ↔ hrm_units`: r = −0.036, p = 0.48) and showed
no effect at any stage. Only the summed-quantity measure picked up the artifact.
That is the tell: a dose measure that accumulates along a route will encode route
length unless it is normalised or differenced away.

## Method

**Why controlling for fleet size was necessary, and not sufficient.** The owner's
instruction — "fleet size needs to be the same when you do the correlation test"
— is right and was applied two ways (matched bins within ±2 trucks, and partial
correlation). It is necessary because HRM crews are dispatched to roads that are
busy or deteriorating, and both correlate with truck count; an uncontrolled
correlation would measure dispatch policy, exactly the endogeneity that made raw
congestion appear to *speed up* haulage. Measured here: `trucks ↔ hrm_units`
r = +0.110, p = 0.030 — a real confound, correctly anticipated.

It was not sufficient, because route length is a second, larger confound that
fleet-matching does nothing about.

**Data.** `FMS_HRM_SUPERVISION`, 77,032 rows over **2026-06-02 … 07-31** (60
days, 161 units: graders, excavators, compactors, water trucks). Unlike GPS, this
**does** overlap the haulage record — `HAULAGE` runs to 2026-07-29, giving a
**58-day** usable window. Trips came from `HAULAGE` rather than
`HAULAGE_IWIP_CLEAN`, which ends 2026-07-09 and would have given no overlap at
all.

**Panel.** For each (route, shift, day): trips per truck, truck count, and the
HRM units and hours recorded on sections whose `SECTIONKM` falls inside the
route's chainage span. A "unit working a section" is a distinct `EQUIPMENT_ID`
with any activity there that day — counting rows would measure telemetry
chattiness, not work. Result: **389 route-shift-days, 57 days, 6 routes**.

## Limitations, stated plainly

- **6 routes, not 58.** Both endpoints must resolve to corridor chainage nodes
  (TF, KR, POS 12, POS 10, FENI KM15, FENI KM0) for a KM span to exist. Hauls to
  HUAFEI, CUU KM10, POS 14 and other off-corridor tips are excluded. The six
  retained routes carry the bulk of corridor traffic, but this is a corridor
  result, not a site-wide one.
- **58 days, one season.** June–July only. A wet-season repeat could differ,
  since that is when road condition matters most and when HRM works hardest.
- **A null is not proof of absence.** With n=389 this panel can detect
  |r| ≈ 0.14 at 80% power. It cannot exclude a genuine effect smaller than that.
  What it does exclude is an effect large enough to matter for planning — and
  the point estimate is 0.0006, not a suppressed 0.13.
- **Section granularity is 1 km.** HRM records `SECTIONKM` to the kilometre; if
  the real mechanism is a single blocked lane for two hours, this panel averages
  it away. Testing that needs the HRM timestamps joined to trip timestamps, which
  this analysis does not attempt.
- **Presence, not disruption.** Units *working a section* is not the same as
  units *obstructing traffic*. A grader improving a road may raise productivity
  while physically being in the way, and these cancel. The measure cannot
  separate them.

## Recommendation

Exclude HRM from the model. Re-run `scripts/hrm_impact.py` (cached CSVs, no VPN
needed) if the HRM window widens materially or if a wet-season panel becomes
available — the script writes its own verdict.
