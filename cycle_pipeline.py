"""Phase 3.5 — cycle-time model.

Phase 3 predicted `trips_per_dt_per_shift` and lost to a per-route average under
walk-forward validation (OLS 0.238 vs baseline 0.459). Part of the reason is the
target: trips-per-truck-per-shift is a ratio whose denominator is a planning
decision, so it moves for reasons that have nothing to do with the road.

Cycle time is the physical quantity underneath it — how long one truck takes to
load, haul, dump and come back. Tonnage follows from it:

    tonnage = trucks * payload * (shift_minutes / cycle_time_min)

WHERE THE TARGET COMES FROM
The brief specified building cycle time by pairing `loading` and `dumping`
events in FMS_GEOFENCE_VISITS. Measured live, those are the two sparsest event
types in that table: 604 loading rows from 22 distinct trucks, 849 dumping rows
from 240, both starting 2026-06-25. That is ~500 usable trips over a month from
22 of ~1,800 trucks.

WAITING_TIME carries the same information at scale: 663,364 rows since
2025-12-01, of which 470,299 (70.9%) produce a plausible cycle, aggregating to
13,129 path-shift rows across 8 months. Its LOADING/DUMPING columns are clock
times, so the segments come from differencing rather than event pairing.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CYCLE_CSV = os.path.join(DATA, "cycle_training_data.csv")
CYCLE_META = os.path.join(DATA, "cycle_metadata.json")

TARGET = "avg_cycle_time_min"

# A haul cycle shorter than 10 minutes is a data artefact (double-scan, clock
# skew); longer than 10 hours is a truck that broke down or a missed timestamp.
# Bounds are applied per trip, before aggregation, so one bad row cannot drag a
# path-shift average.
CYCLE_MIN_MIN, CYCLE_MAX_MIN = 10, 600
MIN_TRIPS_PER_GROUP = 3          # a mean of one or two trips is noise

# Columns that must never become features: they are the target's own parts.
# Summing them IS the target, so any of them would hand the answer to the model
# while being unknowable when planning a future shift.
LEAKAGE_COLUMNS = ("load_min", "haul_min", "dump_min", "return_min",
                   "cycle_time_min", "avg_cycle_time_min",
                   "wmt_per_shift", "trips_per_dt_per_shift", "trips")

TRIP_SQL = """
SELECT  w.[DATE]                AS date,
        w.SHIFT                 AS shift,
        w.ORIGIN_AREA           AS source,
        w.DESTINATION           AS destination,
        w.EQUIPMENT_ID          AS truck_id,
        w.DRIVER_ID             AS driver_id,
        DATEDIFF(minute, w.LOADING_WAITING_TIME, w.LOADING_TIME)  AS load_min,
        DATEDIFF(minute, w.LOADING_TIME, w.DUMPING_WAITING_TIME)  AS haul_min,
        DATEDIFF(minute, w.DUMPING_WAITING_TIME, w.DUMPING_TIME)  AS dump_min
FROM    WAITING_TIME w
WHERE   w.[DATE] >= '{start}'
  AND   w.LOADING_TIME IS NOT NULL
  AND   w.ORIGIN_AREA IS NOT NULL AND w.DESTINATION IS NOT NULL
"""

# Driver tenure: first date each driver appears anywhere in the table. Not a
# hire date, but a consistent proxy, and the only one the data supports.
DRIVER_SQL = """
SELECT DRIVER_ID AS driver_id, MIN([DATE]) AS first_seen
FROM   WAITING_TIME
WHERE  DRIVER_ID IS NOT NULL AND DRIVER_ID <> ''
GROUP BY DRIVER_ID
"""

EQUIP_SQL = """
SELECT ID_EQ AS truck_id, MANUFACTURER AS manufacturer,
       MODEL AS model, BUILD_YEAR AS build_year
FROM   EQUIPMENTS
WHERE  ID_EQ IS NOT NULL
"""


def _norm_shift(s):
    """WAITING_TIME stores shift as 1/2; the rest of the app says day/night."""
    return s.map({1: "day", 2: "night", "1": "day", "2": "night"}).fillna("day")


def extract_cycle_data(start: str = "2025-12-01", conn=None) -> pd.DataFrame:
    """Trip-level cycle segments from WAITING_TIME, aggregated to path-shift.

    Returns one row per (date, shift, source, destination) with the mean cycle
    time and the operational context needed to explain it.
    """
    import simulator_api as sim
    from prediction_pipeline import canonical_area

    close = False
    if conn is None:
        if not sim._db_ready():
            raise RuntimeError("no DB configured — cycle extraction needs the VPN")
        conn, close = sim._conn("WBN_DATABASE"), True
    try:
        trips = pd.read_sql(TRIP_SQL.format(start=start), conn)
        drivers = pd.read_sql(DRIVER_SQL, conn)
        equip = pd.read_sql(EQUIP_SQL, conn)
    finally:
        if close:
            conn.close()

    n_raw = len(trips)
    trips["cycle_time_min"] = trips[["load_min", "haul_min", "dump_min"]].sum(
        axis=1, min_count=1)
    # Segment sanity, then whole-cycle sanity. Each bound is a physical claim:
    # a 4-hour load or a negative haul is a bad timestamp, not a slow truck.
    ok = (trips["cycle_time_min"].between(CYCLE_MIN_MIN, CYCLE_MAX_MIN)
          & trips["load_min"].between(0, 240)
          & trips["haul_min"].between(0, 400)
          & trips["dump_min"].between(0, 240))
    trips = trips[ok].copy()

    trips["source"] = trips["source"].map(canonical_area)
    trips["destination"] = trips["destination"].map(canonical_area)
    trips = trips[(trips["source"] != "") & (trips["destination"] != "")
                  & (trips["source"] != trips["destination"])]
    trips["date"] = pd.to_datetime(trips["date"])
    trips["shift"] = _norm_shift(trips["shift"])

    # ── driver tenure ──────────────────────────────────────────────────────
    drivers["first_seen"] = pd.to_datetime(drivers["first_seen"])
    trips = trips.merge(drivers, on="driver_id", how="left")
    trips["tenure_months"] = ((trips["date"] - trips["first_seen"]).dt.days / 30.44)
    trips["experienced"] = (trips["tenure_months"] > 12).astype(float)

    # ── truck age ──────────────────────────────────────────────────────────
    equip["build_year"] = pd.to_numeric(equip["build_year"], errors="coerce")
    equip = equip.drop_duplicates("truck_id")
    trips = trips.merge(equip, on="truck_id", how="left")
    trips["truck_age"] = trips["date"].dt.year - trips["build_year"]
    trips.loc[~trips["truck_age"].between(0, 40), "truck_age"] = np.nan

    key = ["date", "shift", "source", "destination"]
    agg = (trips.groupby(key)
                .agg(avg_cycle_time_min=("cycle_time_min", "mean"),
                     median_cycle_time_min=("cycle_time_min", "median"),
                     cycle_std=("cycle_time_min", "std"),
                     n_trips=("cycle_time_min", "size"),
                     trucks_dt=("truck_id", "nunique"),
                     n_drivers=("driver_id", "nunique"),
                     avg_driver_tenure_months=("tenure_months", "mean"),
                     pct_experienced_drivers=("experienced", "mean"),
                     avg_truck_age=("truck_age", "mean"),
                     truck_manufacturer_mode=("manufacturer",
                                              lambda s: s.mode().iat[0]
                                              if not s.mode().empty else "UNKNOWN"))
                .reset_index())
    agg = agg[agg["n_trips"] >= MIN_TRIPS_PER_GROUP].copy()
    agg["day_of_week"] = agg["date"].dt.dayofweek
    agg.attrs["n_raw_trips"] = n_raw
    agg.attrs["n_used_trips"] = int(len(trips))
    return agg


def attach_context(df: pd.DataFrame) -> pd.DataFrame:
    """Add distance, weather and congestion. Each source reports its own
    coverage so a thin feature is visible rather than silently imputed."""
    import sys
    from prediction_pipeline import distance_km
    sys.path.insert(0, os.path.join(BASE, "scripts"))

    d = df.copy()
    # pandas drops .attrs across merge, so carry the extraction counters
    # forward explicitly rather than silently reporting zeros.
    carried = dict(df.attrs)
    d["distance_km"] = [distance_km(s, t) for s, t in
                        zip(d["source"], d["destination"])]

    # ── weather (API, not the dead site gauges) ────────────────────────────
    cov = {}
    try:
        from fetch_weather import ensure_weather, load_weather
        lo, hi = d["date"].min().date().isoformat(), d["date"].max().date().isoformat()
        ensure_weather(lo, hi)
        w = load_weather()
        w["date"] = pd.to_datetime(w["date"])
        d = d.merge(w[["date", "rainfall_mm", "temperature_max", "humidity",
                       "wind_speed_max"]], on="date", how="left")
        cov["weather"] = round(float(d["rainfall_mm"].notna().mean()), 4)
    except Exception as exc:                                   # noqa: BLE001
        print("[cycle] weather unavailable (%s)" % str(exc)[:120])
        for c in ("rainfall_mm", "temperature_max", "humidity", "wind_speed_max"):
            d[c] = np.nan
        cov["weather"] = 0.0

    for c, label in (("avg_truck_age", "truck_age"),
                     ("avg_driver_tenure_months", "driver_tenure")):
        cov[label] = round(float(d[c].notna().mean()), 4)
    d.attrs = {**carried, "coverage": cov}
    return d


def save_cycle_data(df: pd.DataFrame) -> dict:
    os.makedirs(DATA, exist_ok=True)
    df.to_csv(CYCLE_CSV, index=False)
    cov = df.attrs.get("coverage", {})
    meta = {
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": TARGET,
        "target_source": "WAITING_TIME (loading/dumping clock times, differenced)",
        "target_source_rationale": (
            "FMS_GEOFENCE_VISITS was specified, but its loading events number "
            "604 rows from 22 trucks; WAITING_TIME gives 8 months at path-shift "
            "grain"),
        "rows": int(len(df)),
        "date_range": [str(df["date"].min())[:10], str(df["date"].max())[:10]],
        "months": int(pd.to_datetime(df["date"]).dt.to_period("M").nunique()),
        "raw_trips": int(df.attrs.get("n_raw_trips", 0)),
        "used_trips": int(df.attrs.get("n_used_trips", 0)),
        "cycle_bounds_min": [CYCLE_MIN_MIN, CYCLE_MAX_MIN],
        "min_trips_per_group": MIN_TRIPS_PER_GROUP,
        "feature_coverage": cov,
        "excluded_leakage": list(LEAKAGE_COLUMNS),
        "target_stats": {
            "mean": round(float(df[TARGET].mean()), 2),
            "median": round(float(df[TARGET].median()), 2),
            "std": round(float(df[TARGET].std()), 2),
            "p05": round(float(df[TARGET].quantile(0.05)), 2),
            "p95": round(float(df[TARGET].quantile(0.95)), 2),
        },
    }
    with open(CYCLE_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


if __name__ == "__main__":
    frame = attach_context(extract_cycle_data())
    info = save_cycle_data(frame)
    print("cycle rows %s over %d months (%s → %s)"
          % (format(info["rows"], ","), info["months"], *info["date_range"]))
    print("trips: %s raw → %s usable"
          % (format(info["raw_trips"], ","), format(info["used_trips"], ",")))
    print("cycle time: mean %.1f min, median %.1f, p05-p95 %.0f-%.0f"
          % (info["target_stats"]["mean"], info["target_stats"]["median"],
             info["target_stats"]["p05"], info["target_stats"]["p95"]))
    print("coverage:", info["feature_coverage"])
