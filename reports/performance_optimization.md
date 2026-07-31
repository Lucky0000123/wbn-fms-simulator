# Making filter changes fast

*2026-07-31. Gate `J64` (its speed assertion).*

## The measurement that decided the design

Every filter change re-queried `DISPATCH RESULTS LITE 2`. Timed over the site
VPN, with the request broken into parts:

| step | time |
|---|---|
| `pymssql.connect()` | 0.73 s |
| main SELECT, 7,122 rows returned | **13.41 s** |
| `GROUP BY TYPE`, **7 rows** returned | **8.92 s** |
| **total per filter change** | **~22.5 s** |

A 7-row aggregate costing 8.9 s says the cost is not transfer. So:

| probe | rows out | time |
|---|---|---|
| `SELECT COUNT(*)` (no WHERE) | 1 | **15.41 s** |
| 13 columns, no WHERE | 25,220 | 17.05 s |
| `SELECT *` | 25,220 | 31.90 s |

**`DISPATCH RESULTS LITE 2` is a VIEW, not a table.** A bare `COUNT(*)` with no
predicate costs 15 s because the view is materialised from its base tables
before any filter applies.

## What that rules out

- **Tuning the WHERE clause** — a no-predicate `COUNT(*)` is already 15 s.
- **Adding indexes** — there is nothing to index. Indexes belong to the base
  tables; an *indexed view* is a schema change on a database this project does
  not own.
- **Pushing aggregation into SQL** — the 7-row `GROUP BY` still cost 8.9 s.
- **Caching per filter combination** — it would leave the *first* use of every
  new date range at ~22 s, which is precisely the reported symptom.

## What was done

The view is only **25,220 rows × 13 columns**. It is pulled **once** into memory,
normalised (areas canonicalised, numbers coerced) during the load, and every
filter runs in Python against that snapshot.

- 5-minute TTL; concurrent misses serialised behind one lock so a burst of tab
  opens cannot fire N 17-second queries at a view that is slow because it is busy
- cleared by `/api/retrain`, so new data is picked up
- warmed in a background thread at start-up, so the first operator does not pay
  the load. Backgrounded, not blocking: the harness treats a slow `/health` as a
  hang.

## Before and after

| | before | after |
|---|---|---|
| first filter change | 22.5 s | 0.02–0.11 s (warm) |
| six **distinct** filter combinations, slowest | ~22 s each | **0.05 s** |
| initial page render | stuck on "Loading…" | 0.86 s |
| filter change in the browser | never completed | **1.8–2.8 s** |

The browser figure is larger than the API figure because the page also re-renders
the tables and the 3D scatter after the fetch returns.

Client-side, from the brief: Apply is debounced 500 ms, the button shows
"Loading…" while in flight, and a generation counter discards a slow response
that has been superseded by a newer filter window.

## Not done, and why

**No `/api/simulator/dashboard` combining endpoint.** The brief proposed it to
collapse 4–5 sequential calls. With capability at 0.02 s the round trips are no
longer the bottleneck, and a new endpoint duplicating five existing ones is
surface area to keep in step for no measured gain. If profiling later shows the
remaining calls dominate, this is the right fix and the measurement should come
first.

**The 5-minute TTL means a filter change can still cost ~17 s** if it lands just
after expiry and the warm-up is not running. Acceptable: the alternative is
serving data up to N minutes stale with no bound.
