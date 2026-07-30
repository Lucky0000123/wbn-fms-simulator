"""trip_features.py — Task 1: feature engineering for the production simulator.

Builds the feature table the simulator predicts from. One row per trip.

WHY THESE FEATURES, AND WHAT THEY CAN AND CANNOT CAPTURE
The simulator answers "if I put N trucks on route A and M on route B, how long
does a trip take and how much do I move?". The mechanism it has to represent is
congestion, and congestion happens in three places:

    on the road      trucks_on_route      trucks sharing the same haul
    at the loader    trucks_at_source     queue for the shovel
    at the dump      trucks_at_dest       queue at the tip

The third and fourth are what make cross-route interaction expressible: two
plans loading from the same source contend for the same shovel even though
their routes differ. `shared_source` and `shared_dest` mark where that can
happen, so a plan simulator can add truck counts across plans that collide.

WHAT IS NOT HERE, AND WHY
No segment-level speed. Segment speeds need GPS on the trucks that actually
haul, and measured on this site zero of 940 registered haul trucks appear in
the telematics feed (the 217 instrumented units are engineering and logistics
vehicles). So this is a ROUTE-level simulator with shared-point congestion, not
a segment-level one, and that limit is stated rather than papered over with an
invented speed profile.

TRAVEL, LOAD AND DUMP: MEASURED WHERE POSSIBLE, ESTIMATED ELSEWHERE
The weighbridge gives one interval per trip: first weigh to second weigh. It
does not say how much of that was queueing, loading, driving or tipping.

WAITING_TIME does. It records LOADING_DIFFERENCE_TIME and
DUMPING_DIFFERENCE_TIME directly in minutes, and those are used wherever they
join (about 25% of trips, on truck + date + shift). This matters: the
apportionment below overstates loading by roughly 4.6x against the measured
figure, 41.2 min versus 9.0 min at the median. Every row carries
`load_time_source` saying which basis it used.

For the remaining trips the split is an apportionment, and it is labelled as
one via `split_is_estimated`.

WHY THE FALLBACK SPLIT USES AN EMPIRICAL FLOOR AND NOT distance / speed
The obvious split is travel = 2 x distance / speed. It was tried and rejected,
because `distance_km` is not a measurement on this site: 57 of 65 routes carry
the same default 25.0 km, and TF>FENI KM0 is recorded as 67.8 km yet has trips
finishing in 18.9 minutes, which no haul truck can do. Building travel time on
that lookup would have propagated a placeholder into every predicted component,
and it capped 72% of trips.

Instead the floor is measured from each route's own trips: the 10th percentile
of its observed cycle time is what that route looks like when nothing is in the
way. That is the irreducible part — driving plus the minimum loading and
tipping. Everything above it is congestion, which is precisely the quantity the
simulator exists to predict. It needs no speed constant and no distance lookup.

GROSS/TARE TIMESTAMPS WERE CHECKED AND CARRY NOTHING EXTRA
HAULAGE_IWIP_CLEAN has four timestamps, and GROSS_WEIGHT_TIME/TARE_WEIGHT_TIME
looked like they might bracket the haul separately. They do not: the gross-to-
tare interval is identical to first-to-second weigh on 100.00% of 200,000 trips
sampled. Same two events, different column names.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRIP_CSV = os.path.join(DATA, "trip_level_base.csv")
FEAT_CSV = os.path.join(DATA, "trip_features.csv")
FEAT_META = os.path.join(DATA, "trip_features_meta.json")

# The percentile of a route's own cycle times taken as its congestion-free
# floor. Not zero: the very fastest trips include mis-scans and short-weighs.
FLOOR_PCTL = 0.10
# A route needs enough trips for a percentile to mean anything.
MIN_TRIPS_FOR_FLOOR = 30
# Terminal time cannot be negative, and a trip cannot be all terminal.
MIN_TERMINAL_MIN = 1.0
# Split of the congestion-free floor between the loader and the tip. Loading
# dominates in truck-shovel operations: a tip is a reverse and a lift, a load is
# several passes. An assumption, recorded as one, replaced by measurement where
# WAITING_TIME reaches.
FLOOR_LOAD_SHARE = 0.70
# Share of the congestion-free floor treated as driving rather than terminal
# work. Without instrumented trucks there is no measurement to set this from,
# so it is an even split, declared here rather than buried in an expression.
FLOOR_TRAVEL_SHARE = 0.50
# Share of congestion (time above the floor) attributed to the loading queue.
# Queues form at the shovel far more than at the tip, because loading is the
# slower, single-server step.
QUEUE_LOAD_SHARE = 0.80

LOAD_TIME_SQL = """
SELECT  w.[DATE]                    AS date,
        w.SHIFT                     AS shift_raw,
        w.EQUIPMENT_ID              AS truck_id,
        w.LOADING_DIFFERENCE_TIME   AS load_min,
        w.DUMPING_DIFFERENCE_TIME   AS dump_min
FROM    WAITING_TIME w
WHERE   w.[DATE] >= '{start}' AND w.[DATE] <= '{end}'
  AND   w.LOADING_DIFFERENCE_TIME IS NOT NULL
"""
# A dwell beyond this is a breakdown, a shift boundary or a clerical error, not
# a load. Verified against the distribution: p95 is 63 min.
MAX_PLAUSIBLE_DWELL_MIN = 240


def _write(df: pd.DataFrame, path: str) -> list[str]:
    out = [path]
    df.to_csv(path, index=False)
    try:
        import importlib.util
        if importlib.util.find_spec("pyarrow"):
            pq = path.rsplit(".", 1)[0] + ".parquet"
            df.to_parquet(pq, index=False)
            out.append(pq)
    except Exception:                                       # noqa: BLE001
        pass
    return out


def load_trips(path: str = TRIP_CSV) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError("run trip_extraction.py first")
    d = pd.read_csv(path)
    d["date"] = pd.to_datetime(d["date"])
    return d


def add_congestion_counts(d: pd.DataFrame) -> pd.DataFrame:
    """Trucks sharing a route, a loading point and a dumping point per shift.

    Counted as DISTINCT trucks, not trips: twenty trips by four trucks is four
    trucks' worth of contention, not twenty.
    """
    d = d.copy()
    key = ["date", "shift"]
    d["trucks_on_route"] = d.groupby(key + ["route"])["truck_id"].transform("nunique")
    d["trucks_at_source"] = d.groupby(key + ["source"])["truck_id"].transform("nunique")
    d["trucks_at_dest"] = d.groupby(key + ["destination"])["truck_id"].transform("nunique")
    d["trips_on_route"] = d.groupby(key + ["route"])["truck_id"].transform("size")
    return d


def add_shared_point_flags(d: pd.DataFrame) -> pd.DataFrame:
    """Does this loading/dumping point serve more than one route?

    Computed over the whole history, not per shift: a point that serves several
    routes is structurally shared even on a day when only one route runs, and
    that is the property the plan simulator needs when it combines plans.
    """
    d = d.copy()
    src_routes = d.groupby("source")["route"].transform("nunique")
    dst_routes = d.groupby("destination")["route"].transform("nunique")
    d["routes_at_source"] = src_routes
    d["routes_at_dest"] = dst_routes
    d["shared_source"] = (src_routes > 1).astype(int)
    d["shared_dest"] = (dst_routes > 1).astype(int)
    return d


def split_cycle_components(d: pd.DataFrame) -> pd.DataFrame:
    """Split each trip into a congestion-free floor and the delay above it.

    The floor is the route's own 10th-percentile cycle time: what this haul
    looks like when nothing is in the way. It is measured from the route's
    trips, so it needs no assumed speed and no distance lookup — both of which
    were rejected because `distance_km` is a placeholder on 57 of 65 routes.

    Everything above the floor is `congestion_delay_min`, the quantity the
    simulator predicts. The floor is then apportioned to loading and dumping,
    and the delay is apportioned queue-heavy toward the loader.

    The apportionment is an ESTIMATE. The weighbridge records one interval per
    trip and never says how it divided, so every derived component carries
    `split_is_estimated`, and the floor itself is real while its division is not.
    """
    d = d.copy()
    cycle = pd.to_numeric(d["cycle_time_min"], errors="coerce")

    # Per-route floor, from routes with enough trips to support a percentile.
    cnt = d.groupby("route")["cycle_time_min"].transform("size")
    floor = d.groupby("route")["cycle_time_min"].transform(
        lambda s: s.quantile(FLOOR_PCTL))
    # Thin routes fall back to the global floor rather than to a noisy one.
    global_floor = float(cycle.quantile(FLOOR_PCTL))
    floor = floor.where(cnt >= MIN_TRIPS_FOR_FLOOR, global_floor)
    floor = floor.clip(lower=MIN_TERMINAL_MIN)

    d["route_floor_min"] = floor.round(3)
    d["floor_is_route_specific"] = (cnt >= MIN_TRIPS_FOR_FLOOR).astype(int)
    # A trip below its route's floor is simply an uncongested trip; the delay
    # floors at zero rather than going negative.
    d["congestion_delay_min"] = (cycle - floor).clip(lower=0).round(3)

    base = np.minimum(cycle, floor)
    delay = d["congestion_delay_min"]
    # Half the congestion-free floor is taken as driving and half as the
    # unavoidable terminal work. Driving is treated as unaffected by congestion,
    # which is why all of the delay lands on the terminal components.
    d["travel_time_est_min"] = (base * FLOOR_TRAVEL_SHARE).round(3)
    fixed_terminal = base - d["travel_time_est_min"]
    d["load_time_est_min"] = (fixed_terminal * FLOOR_LOAD_SHARE
                              + delay * QUEUE_LOAD_SHARE).round(3)
    d["dump_time_est_min"] = (fixed_terminal * (1 - FLOOR_LOAD_SHARE)
                              + delay * (1 - QUEUE_LOAD_SHARE)).round(3)
    d["terminal_time_min"] = (d["load_time_est_min"]
                              + d["dump_time_est_min"]).round(3)
    d["split_method"] = (
        "empirical: floor = route p%d of observed cycle time; delay = cycle - "
        "floor; floor split %d/%d load/dump, delay split %d/%d"
        % (int(FLOOR_PCTL * 100), int(FLOOR_LOAD_SHARE * 100),
           int((1 - FLOOR_LOAD_SHARE) * 100), int(QUEUE_LOAD_SHARE * 100),
           int((1 - QUEUE_LOAD_SHARE) * 100)))
    d["split_is_estimated"] = 1
    return d


def attach_measured_load_time(d: pd.DataFrame, conn=None) -> pd.DataFrame:
    """Replace the estimated load and dump times with measured ones.

    WAITING_TIME records LOADING_DIFFERENCE_TIME and DUMPING_DIFFERENCE_TIME
    directly in minutes, per truck per shift. These are measurements, not
    apportionments, and they matter: the 70/30 estimate overstates loading by
    roughly 4.6x against them (median 41.2 min estimated vs 9.0 min measured).

    Joined on (truck_id, date, shift). Location names cannot be used — the two
    tables use different vocabularies, PIT/ORIGIN_AREA overlapping the trip
    extract on only 3 values — but the join does not need them: a truck on a
    given date and shift is already known from the trip extract to be hauling a
    specific route, so all that is wanted here is the measured minutes.

    Coverage is partial (about 25% of trips), so `load_time_source` marks every
    row as measured or estimated and downstream code must respect it rather
    than treating the column as uniformly trustworthy.
    """
    d = d.copy()
    d["load_time_min"] = d["load_time_est_min"]
    d["dump_time_min"] = d["dump_time_est_min"]
    d["load_time_source"] = "estimated"
    try:
        import simulator_api as sim
        close = False
        if conn is None:
            if not sim._db_ready():
                raise RuntimeError("no DB configured")
            conn, close = sim._conn("WBN_DATABASE"), True
        try:
            w = pd.read_sql(LOAD_TIME_SQL.format(
                start=str(d["date"].min())[:10], end=str(d["date"].max())[:10]), conn)
        finally:
            if close:
                conn.close()
    except Exception as exc:                                # noqa: BLE001
        d.attrs["load_time_note"] = "WAITING_TIME unavailable (%s)" % str(exc)[:90]
        return d

    for c in ("load_min", "dump_min"):
        w[c] = pd.to_numeric(w[c], errors="coerce")
    w = w[w["load_min"].between(0, MAX_PLAUSIBLE_DWELL_MIN)]
    if w.empty:
        d.attrs["load_time_note"] = "WAITING_TIME returned no usable rows"
        return d

    w["date"] = pd.to_datetime(w["date"])
    w["truck_id"] = w["truck_id"].astype(str).str.strip().str.upper()
    # SHIFT is 1/2 in WAITING_TIME; the trip extract uses day/night.
    w["shift"] = np.where(w["shift_raw"].astype(str).str.strip() == "2",
                          "night", "day")
    agg = (w.groupby(["truck_id", "date", "shift"])
             .agg(load_measured=("load_min", "median"),
                  dump_measured=("dump_min", "median")).reset_index())

    key = d["truck_id"].astype(str).str.strip().str.upper()
    d["_tk"] = key
    d = d.merge(agg, left_on=["_tk", "date", "shift"],
                right_on=["truck_id", "date", "shift"], how="left",
                suffixes=("", "_wt")).drop(columns=["_tk", "truck_id_wt"],
                                           errors="ignore")

    hit = d["load_measured"].notna()
    d.loc[hit, "load_time_min"] = d.loc[hit, "load_measured"]
    d.loc[hit, "load_time_source"] = "measured (WAITING_TIME, truck-shift median)"
    dhit = hit & d["dump_measured"].notna()
    d.loc[dhit, "dump_time_min"] = d.loc[dhit, "dump_measured"]
    # Measured dwell can exceed the weighbridge envelope on ~7% of trips: the
    # two systems time different things and are not guaranteed to nest. Rather
    # than silently rescale a measurement to fit an estimate, those rows are
    # flagged so the inconsistency stays visible.
    over = (d["load_time_min"].fillna(0) + d["dump_time_min"].fillna(0)
            > d["cycle_time_min"])
    d["dwell_exceeds_cycle"] = (over & hit).astype(int)
    d.attrs["load_time_note"] = (
        "measured on %.1f%% of trips; %.1f%% of those exceed the weighbridge "
        "cycle envelope and are flagged"
        % (100 * float(hit.mean()),
           100 * float(d.loc[hit, "dwell_exceeds_cycle"].mean()) if hit.any() else 0))
    return d.drop(columns=["load_measured", "dump_measured"], errors="ignore")


def build(conn=None, verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    say = print if verbose else (lambda *a, **k: None)
    d = load_trips()
    d = add_congestion_counts(d)
    d = add_shared_point_flags(d)
    d = split_cycle_components(d)
    d = attach_measured_load_time(d, conn)

    d["hour_of_day"] = pd.to_numeric(d.get("depart_hour"), errors="coerce")
    for c in ("rainfall_mm", "temperature_max", "humidity"):
        if c not in d.columns:
            d[c] = np.nan
    d["is_wet"] = (pd.to_numeric(d["rainfall_mm"], errors="coerce").fillna(0) > 5).astype(int)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(d)),
        "date_range": [str(d["date"].min())[:10], str(d["date"].max())[:10]],
        "routes": int(d["route"].nunique()),
        "sources": int(d["source"].nunique()),
        "destinations": int(d["destination"].nunique()),
        "shared_sources": int(d.loc[d["shared_source"] == 1, "source"].nunique()),
        "shared_dests": int(d.loc[d["shared_dest"] == 1, "destination"].nunique()),
        "load_time_source_counts": d["load_time_source"].value_counts().to_dict(),
        "load_time_note": d.attrs.get("load_time_note", "n/a"),
        "route_specific_floor_pct": round(100 * float(d["floor_is_route_specific"].mean()), 2),
        "median_route_floor_min": round(float(d["route_floor_min"].median()), 1),
        "median_congestion_delay_min": round(float(d["congestion_delay_min"].median()), 1),
        "assumptions": {
            "floor_percentile": FLOOR_PCTL,
            "floor_travel_share": FLOOR_TRAVEL_SHARE,
            "floor_load_share": FLOOR_LOAD_SHARE,
            "queue_load_share": QUEUE_LOAD_SHARE,
            "note": ("the weighbridge records ONE interval per trip; the "
                     "per-route floor is measured, but its division into "
                     "travel/load/dump is assumed, not observed"),
        },
        "rejected": {
            "distance_over_speed": ("travel = 2*dist/speed was tried and "
                                    "rejected: distance_km is a placeholder, "
                                    "57 of 65 routes carry the default 25.0 km "
                                    "and it capped 72% of trips"),
        },
        "not_available": {
            "segment_level_speed": ("requires GPS on haul trucks; 0 of 940 "
                                    "registered haul trucks are in the "
                                    "telematics feed"),
        },
    }
    written = _write(d, FEAT_CSV)
    meta["files_written"] = [os.path.basename(f) for f in written]
    with open(FEAT_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)

    say("trip features: %s rows, %d routes (%s → %s)"
        % (format(len(d), ","), meta["routes"], *meta["date_range"]))
    say("  shared loading points: %d of %d | shared dumps: %d of %d"
        % (meta["shared_sources"], meta["sources"],
           meta["shared_dests"], meta["destinations"]))
    say("  load time: %s" % meta["load_time_note"])
    say("  route-specific floor on %.1f%% of trips (median floor %.1f min, "
        "median congestion delay %.1f min)"
        % (meta["route_specific_floor_pct"], meta["median_route_floor_min"],
           meta["median_congestion_delay_min"]))
    return d, meta


def load_features() -> pd.DataFrame | None:
    try:
        d = pd.read_csv(FEAT_CSV)
        d["date"] = pd.to_datetime(d["date"])
        return d
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    build()
