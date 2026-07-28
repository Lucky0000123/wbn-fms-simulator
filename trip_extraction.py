"""trip_extraction.py — Pre-Phase 4 data layer at individual trip grain.

WHY THIS EXISTS, measured rather than assumed
Phase 3 trained on 4,141 path-shift rows and lost to a lookup table. Decomposing
cycle time on 189,395 real trips shows why:

    variance BETWEEN (route, shift, date) groups   28.2%
    variance WITHIN  those groups                  71.8%   <- averaged away

Aggregating to path-shift means the model can only ever see the 28.2%, so it was
structurally capped near R² 0.28 regardless of its features. Trip grain keeps all
535,411 rows and makes the other 71.8% addressable — or proves it is noise.

SCHEMA NOTES (the brief's column names did not survive contact with the DB)
Five of twelve specified columns do not exist on HAULAGE_IWIP_CLEAN. Verified
against INFORMATION_SCHEMA:

    spec            reality
    ID              SERIAL_NO / TICKET_NO
    SOURCE          ORIGIN_AREA
    DESTINATION     DESTINATION_AREA
    CORRIDOR_KM     (no column — use the distance_km() lookup)
    DRIVER_ID       (absent, and no DRIVERS table exists in this database)

The cycle itself is sound: DATEDIFF(FIRST_WB_TIME, SECOND_WB_TIME) gives median
56 min (p25 38, p75 102) with 94.7% inside the 5-480 window and 0% under 5 min,
so these are full haul cycles, not a weigh-in/weigh-out gap.
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
TRIP_META = os.path.join(DATA, "trip_metadata.json")

TARGET = "cycle_time_min"

# A cycle under 5 minutes is a double-scan; over 8 hours is a breakdown or a
# missed timestamp. Both are data artefacts, not slow trucks.
MIN_CYCLE_MIN, MAX_CYCLE_MIN = 5, 480
# Cap rather than drop the long tail: a genuinely slow shift is signal, but one
# 11,963-minute row would dominate a squared-error fit on its own.
OUTLIER_PCT = 0.99
MIN_TRIPS_PER_ROUTE = 30          # a route seen twice cannot be modelled
MIN_FEATURE_COVERAGE = 0.60       # below this, drop rather than impute

# The target is (SECOND_WB - FIRST_WB). Those timestamps, and anything derived
# from them, are the answer. They are unknowable when planning a future shift.
LEAKAGE_COLUMNS = ("first_wb", "second_wb", "cycle_time_min", "wb_time",
                   "gross_weight_time", "tare_weight_time")

TRIP_SQL = """
SELECT  h.TICKET_NO              AS ticket_no,
        h.TRUCK_ID               AS truck_id,
        h.[DATE]                 AS date,
        h.SHIFT                  AS shift,
        h.CONTRACTOR             AS contractor,
        h.ORIGIN_AREA            AS source,
        h.DESTINATION_AREA       AS destination,
        h.WMT                    AS payload_t,
        h.FIRST_WB_TIME          AS first_wb,
        h.SECOND_WB_TIME         AS second_wb,
        h.MATERIAL               AS material,
        DATEPART(hour, h.FIRST_WB_TIME) AS depart_hour
FROM    HAULAGE_IWIP_CLEAN h
WHERE   h.[DATE] >= '{start}' AND h.[DATE] <= '{end}'
  AND   h.FIRST_WB_TIME IS NOT NULL
  AND   h.SECOND_WB_TIME IS NOT NULL
  AND   h.WMT > 0
  AND   h.ORIGIN_AREA IS NOT NULL
  AND   h.DESTINATION_AREA IS NOT NULL
"""

# EQUIPMENTS keys on ID_EQ, not EQUIP_ID as specified.
EQUIP_SQL = """
SELECT ID_EQ AS truck_id, MANUFACTURER AS manufacturer,
       MODEL AS truck_model, BUILD_YEAR AS build_year
FROM   EQUIPMENTS WHERE ID_EQ IS NOT NULL
"""


def _norm_shift(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip().str.lower()
    return np.where(t.isin(["2", "night", "n", "malam"]), "night", "day")


def fetch_trips(start="2025-12-27", end="2026-07-09", conn=None) -> pd.DataFrame:
    """One row per weighbridge ticket."""
    import simulator_api as sim

    close = False
    if conn is None:
        if not sim._db_ready():
            raise RuntimeError("no DB configured — trip extraction needs the VPN")
        conn, close = sim._conn("WBN_DATABASE"), True
    try:
        raw = pd.read_sql(TRIP_SQL.format(start=start, end=end), conn)
        equip = pd.read_sql(EQUIP_SQL, conn)
    finally:
        if close:
            conn.close()
    raw.attrs["equip"] = equip
    return raw


def clean_trips(raw: pd.DataFrame) -> pd.DataFrame:
    """Apply physical bounds, canonicalise the vocabulary, cap the tail."""
    from prediction_pipeline import canonical_area, distance_km

    df = raw.copy()
    n_raw = len(df)
    df["first_wb"] = pd.to_datetime(df["first_wb"], errors="coerce")
    df["second_wb"] = pd.to_datetime(df["second_wb"], errors="coerce")
    df[TARGET] = (df["second_wb"] - df["first_wb"]).dt.total_seconds() / 60.0
    df = df[df[TARGET].between(MIN_CYCLE_MIN, MAX_CYCLE_MIN)].copy()
    n_bounded = len(df)

    # Same canonical vocabulary as every other model here, so a route means the
    # same thing across phases and check_vocab keeps passing.
    df["source"] = df["source"].map(canonical_area)
    df["destination"] = df["destination"].map(canonical_area)
    df = df[(df["source"] != "") & (df["destination"] != "")
            & (df["source"] != df["destination"])]
    df["route"] = df["source"] + ">" + df["destination"]

    counts = df["route"].value_counts()
    keep = set(counts[counts >= MIN_TRIPS_PER_ROUTE].index)
    n_before_routes = len(df)
    df = df[df["route"].isin(keep)].copy()

    # Winsorise per route: a 400-minute cycle means something different on a
    # 68 km haul than on a 6 km one, so the cap has to be route-local.
    cap = df.groupby("route")[TARGET].transform(lambda x: x.quantile(OUTLIER_PCT))
    df["was_capped"] = (df[TARGET] > cap).astype(int)
    df[TARGET] = np.minimum(df[TARGET], cap)

    df["date"] = pd.to_datetime(df["date"])
    df["shift"] = _norm_shift(df["shift"])
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["distance_km"] = [distance_km(s, d) for s, d in
                         zip(df["source"], df["destination"])]

    # Fleet pressure: how many trucks were working this route that shift. Built
    # from ticket identity, never from the target.
    df["trucks_on_route"] = df.groupby(["date", "shift", "route"])[
        "truck_id"].transform("nunique")

    df.attrs.update({
        "n_raw": n_raw, "n_bounded": n_bounded,
        "n_routes_kept": len(keep), "n_routes_dropped": int(counts.size - len(keep)),
        "n_dropped_thin_routes": int(n_before_routes - len(df)),
        "equip": raw.attrs.get("equip"),
    })
    return df


def attach_features(df: pd.DataFrame) -> pd.DataFrame:
    """Truck age and weather, each reporting its own coverage.

    Coverage is measured, and anything under 60% is DROPPED rather than imputed.
    A feature that is mostly a fill value teaches the model about the fill value.
    """
    d = df.copy()
    carried = dict(df.attrs)
    cov, dropped = {}, []

    # ── truck age ──────────────────────────────────────────────────────────
    equip = carried.get("equip")
    if equip is not None and len(equip):
        e = equip.drop_duplicates("truck_id").copy()
        e["build_year"] = pd.to_numeric(e["build_year"], errors="coerce")
        d = d.merge(e[["truck_id", "build_year", "manufacturer"]],
                    on="truck_id", how="left")
        d["truck_age"] = d["date"].dt.year - d["build_year"]
        d.loc[~d["truck_age"].between(0, 40), "truck_age"] = np.nan
        cov["truck_age"] = round(float(d["truck_age"].notna().mean()), 4)
        if cov["truck_age"] < MIN_FEATURE_COVERAGE:
            dropped.append({"feature": "truck_age", "coverage": cov["truck_age"],
                            "reason": "below %.0f%% coverage; EQUIPMENTS matches "
                                      "only part of the trip-grain fleet"
                                      % (100 * MIN_FEATURE_COVERAGE)})
            d = d.drop(columns=["truck_age", "build_year"])
    else:
        cov["truck_age"] = 0.0

    # ── weather ────────────────────────────────────────────────────────────
    # Reuses the Open-Meteo cache built earlier (573 days, no gaps). A third
    # fetcher would be a third thing to keep correct.
    try:
        import sys
        sys.path.insert(0, os.path.join(BASE, "scripts"))
        from fetch_weather import ensure_weather, load_weather
        lo = d["date"].min().date().isoformat()
        hi = d["date"].max().date().isoformat()
        ensure_weather(lo, hi)
        w = load_weather()
        w["date"] = pd.to_datetime(w["date"])
        d = d.merge(w[["date", "rainfall_mm", "temperature_max", "humidity"]],
                    on="date", how="left")
        cov["weather"] = round(float(d["rainfall_mm"].notna().mean()), 4)
        d["is_wet"] = (d["rainfall_mm"].fillna(0) > 5).astype(int)
    except Exception as exc:                                    # noqa: BLE001
        print("[trip] weather unavailable (%s)" % str(exc)[:100])
        for c in ("rainfall_mm", "temperature_max", "humidity"):
            d[c] = np.nan
        d["is_wet"] = 0
        cov["weather"] = 0.0

    # ── road grade (optional; only if real coordinates were derived) ────────
    try:
        from dem_grade import attach_grade
        d, grade_cov = attach_grade(d)
        cov["road_grade"] = grade_cov
        if grade_cov < MIN_FEATURE_COVERAGE:
            dropped.append({"feature": "road_grade", "coverage": grade_cov,
                            "reason": "no verified coordinates for enough nodes"})
            d = d.drop(columns=[c for c in ("net_grade_pct", "elev_gain_m")
                                if c in d.columns])
    except Exception as exc:                                    # noqa: BLE001
        cov["road_grade"] = 0.0
        dropped.append({"feature": "road_grade", "coverage": 0.0,
                        "reason": "grade unavailable (%s)" % str(exc)[:80]})

    carried.update({"coverage": cov, "dropped_features": dropped})
    d.attrs = carried
    return d


def assert_no_leakage(feature_names) -> None:
    bad = [f for f in feature_names
           if any(f == c or f.startswith(c) for c in LEAKAGE_COLUMNS)]
    if bad:
        raise ValueError("leakage: weighbridge timestamps as features: %s" % bad)


def save(df: pd.DataFrame) -> dict:
    os.makedirs(DATA, exist_ok=True)
    out = df.drop(columns=[c for c in ("first_wb", "second_wb")
                           if c in df.columns])
    # CSV primary, parquet as a bonus when an engine is installed. See the note
    # in match_factor._write_table: parquet needs pyarrow (~100 MB) and this
    # project keeps requirements.txt small for the no-VPN public demo.
    out.to_csv(TRIP_CSV, index=False)
    try:
        import importlib.util
        if (importlib.util.find_spec("pyarrow")
                or importlib.util.find_spec("fastparquet")):
            out.to_parquet(TRIP_CSV.rsplit(".", 1)[0] + ".parquet", index=False)
    except Exception:                                       # noqa: BLE001
        pass
    a = df.attrs
    meta = {
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grain": "individual trip (one weighbridge ticket)",
        "target": TARGET,
        "source_table": "HAULAGE_IWIP_CLEAN",
        "rows": int(len(df)),
        "raw_rows": int(a.get("n_raw", 0)),
        "rows_after_bounds": int(a.get("n_bounded", 0)),
        "routes_kept": int(a.get("n_routes_kept", 0)),
        "routes_dropped_thin": int(a.get("n_routes_dropped", 0)),
        "trips_dropped_thin_routes": int(a.get("n_dropped_thin_routes", 0)),
        "date_range": [str(df["date"].min())[:10], str(df["date"].max())[:10]],
        "trucks": int(df["truck_id"].nunique()),
        "cycle_bounds_min": [MIN_CYCLE_MIN, MAX_CYCLE_MIN],
        "outlier_cap_pct": OUTLIER_PCT,
        "pct_capped": round(100 * float(df["was_capped"].mean()), 2),
        "min_trips_per_route": MIN_TRIPS_PER_ROUTE,
        "feature_coverage": a.get("coverage", {}),
        "dropped_features": a.get("dropped_features", []),
        "min_feature_coverage": MIN_FEATURE_COVERAGE,
        "excluded_leakage": list(LEAKAGE_COLUMNS),
        "target_stats": {
            "mean": round(float(df[TARGET].mean()), 2),
            "median": round(float(df[TARGET].median()), 2),
            "std": round(float(df[TARGET].std()), 2),
            "p05": round(float(df[TARGET].quantile(0.05)), 2),
            "p95": round(float(df[TARGET].quantile(0.95)), 2),
        },
    }
    with open(TRIP_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def variance_decomposition(df: pd.DataFrame) -> dict:
    """How much of the target survives aggregation.

    This is the number that justifies the whole grain change, so it is computed
    from the shipped dataset rather than quoted from a one-off script.
    """
    g = df.groupby(["route", "shift", "date"])[TARGET].transform("mean")
    total = float(df[TARGET].var())
    between = float(g.var())
    within = float((df[TARGET] - g).var())
    return {
        "total_variance": round(total, 1),
        "between_group_pct": round(100 * between / total, 1) if total else None,
        "within_group_pct": round(100 * within / total, 1) if total else None,
        "aggregate_model_r2_ceiling": round(between / total, 4) if total else None,
        "note": ("an aggregate model can only explain the between-group share; "
                 "the within-group share is destroyed by averaging"),
    }


if __name__ == "__main__":
    frame = attach_features(clean_trips(fetch_trips()))
    info = save(frame)
    vd = variance_decomposition(frame)
    with open(TRIP_META, "r+", encoding="utf-8") as fh:
        m = json.load(fh); m["variance_decomposition"] = vd
        fh.seek(0); json.dump(m, fh, indent=2); fh.truncate()

    print("trips %s over %s → %s (%s trucks, %s routes)"
          % (format(info["rows"], ","), *info["date_range"],
             format(info["trucks"], ","), info["routes_kept"]))
    print("  %s raw → %s in bounds → %s after thin routes"
          % (format(info["raw_rows"], ","), format(info["rows_after_bounds"], ","),
             format(info["rows"], ",")))
    print("  cycle: median %.0f min, p05-p95 %.0f-%.0f, %.1f%% capped"
          % (info["target_stats"]["median"], info["target_stats"]["p05"],
             info["target_stats"]["p95"], info["pct_capped"]))
    print("  coverage:", info["feature_coverage"])
    for d in info["dropped_features"]:
        print("  DROPPED %s (%.0f%%): %s"
              % (d["feature"], 100 * d["coverage"], d["reason"]))
    print("  variance: %.1f%% between groups, %.1f%% within → aggregate ceiling R² %.3f"
          % (vd["between_group_pct"], vd["within_group_pct"],
             vd["aggregate_model_r2_ceiling"]))
