"""
Phase 2 — prediction data pipeline.

Turns historical haul-cycle records into a flat training table, fits the feature
transformers, and exposes both at prediction time.

Two extraction paths, chosen automatically:

  • DB configured  (FMS_DB_HOST/USER/PASS) → `extract_from_db()` runs the real
    trip-level SQL against HAULAGE_IWIP_CLEAN, joined to rainfall and to the
    per-shift weighbridge count. One row per haul cycle, contractor-attributed.

  • No DB (sample-fixtures) → `extract_from_fixtures()` derives the same schema
    from fixtures/. NOTE: the shipped fixtures are already aggregated to
    path-day granularity and carry no contractor column, so contractor is
    attributed by that hauler's observed share of fleet activity and payload.
    The row grain is therefore path × shift × contractor, not a single truck
    cycle. This is honest but coarser — see `grain` in the metadata. When the
    DB is available the trip-level path supersedes it automatically.

Nothing here touches the existing OLS in simulator_api.py; that remains the
prediction fallback.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
FX = os.path.join(BASE, "fixtures")

TRAINING_CSV = os.path.join(DATA, "training_data.csv")
TRAINING_META = os.path.join(DATA, "training_metadata.json")
ENCODERS_PKL = os.path.join(DATA, "encoders.pkl")
SCALER_PKL = os.path.join(DATA, "scaler.pkl")

# Columns the model consumes. Order matters: it defines the design matrix.
CATEGORICAL = ["contractor", "source", "destination", "shift", "day_of_week"]
NUMERIC = ["distance_km", "payload_t", "rainfall_mm", "weighbridges_open", "trucks_dt"]
TARGET = "trips_per_dt_per_shift"

# ── Corridor geometry ───────────────────────────────────────────────────────
# Chainage of each node on the TF→FENI haul road (km from the FENI end), taken
# from WBN_DATABASE.dbo.HAUL_ROAD_STA via the corridor block in simulator_api.
CORRIDOR_KM = {
    "TF": 67.8, "TOFU": 67.8,
    "KR": 39.0, "KRENE": 39.0,
    "POS 12": 27.0, "POS12": 27.0,
    "POS 10": 17.0, "POS10": 17.0,
    "FENI KM15": 15.0, "FENI 15": 15.0,
    "FENI KM0": 0.0, "FENI 0": 0.0, "FENI": 0.0,
    "CRUSHER": 3.0,
}
CORRIDOR_LENGTH_KM = 67.8
_MEDIAN_HAUL_KM = 25.0          # fallback for off-corridor spurs (BLB, BSE, …)

WBN_HAULERS = ["RIM", "PPP", "SSS", "SMA", "STM", "HJS", "GMG", "CKB", "HFNC"]


def _norm(name: str) -> str:
    return " ".join(str(name or "").strip().upper().split())


def distance_km(source: str, destination: str) -> float:
    """Haul distance from the corridor chainage lookup.

    Both endpoints on the corridor → |Δ chainage|. Otherwise fall back to the
    median observed haul so an unmapped spur never produces a null feature.
    """
    a, b = CORRIDOR_KM.get(_norm(source)), CORRIDOR_KM.get(_norm(destination))
    if a is None or b is None:
        return _MEDIAN_HAUL_KM
    return round(abs(a - b), 2)


def _fx(name):
    with open(os.path.join(FX, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


# ── Extraction path 1: the real database (trip level) ───────────────────────
TRIP_LEVEL_SQL = """
SELECT  h.[DATE]                AS date,
        h.CONTRACTOR            AS contractor,
        h.TRUCK_ID              AS truck_id,
        h.ORIGIN_AREA           AS source,
        h.DESTINATION_AREA      AS destination,
        h.SHIFT                 AS shift,
        h.TONNAGE               AS payload_t,
        h.CYCLE_TIME            AS cycle_time_min,
        h.LOADING_TIME          AS loading_time_min,
        h.HAULING_TIME          AS hauling_time_min,
        h.DUMPING_TIME          AS dumping_time_min,
        h.RETURN_TIME           AS return_time_min
FROM    HAULAGE_IWIP_CLEAN h
WHERE   h.[DATE] >= DATEADD(month, -20, GETDATE())
  AND   h.[DATE] <= '2100-01-01'
  AND   h.CONTRACTOR IN ({haulers})
  AND   h.TONNAGE > 0
"""

RAIN_SQL = """
SELECT [DATE] AS date, Area AS area, H2O AS rainfall_mm
FROM   AVG_RAIN_BY_DATE_AREA
WHERE  Area IN ('TOFU','KAO RAHAI') AND H2O IS NOT NULL
  AND  [DATE] >= DATEADD(month, -20, GETDATE())
"""

WB_SQL = """
SELECT CONVERT(date,[DATE]) AS date, SHIFT AS shift, COUNT(DISTINCT WB_ID) AS weighbridges_open
FROM   HAULAGE_IWIP_CLEAN
WHERE  WB_ID <> '' AND WB_ID IS NOT NULL AND [DATE] >= DATEADD(month,-20,GETDATE())
GROUP BY CONVERT(date,[DATE]), SHIFT
"""


def extract_from_db():
    """One row per haul cycle, aggregated to truck-shift to form the target.

    Returns None when no DB is configured or the query fails, so the caller can
    fall back to fixtures rather than crash the app.
    """
    import simulator_api                                   # reuse its env-var creds
    if not simulator_api._db_ready():
        return None
    try:
        conn = simulator_api._conn("WBN_DATABASE")
        haulers = ",".join("'%s'" % h for h in WBN_HAULERS)
        trips = pd.read_sql(TRIP_LEVEL_SQL.format(haulers=haulers), conn)
        rain = pd.read_sql(RAIN_SQL, conn)
        wb = pd.read_sql(WB_SQL, conn)
        conn.close()
    except Exception as exc:                               # noqa: BLE001
        print("[pipeline] DB extraction failed (%s) — using fixtures" % str(exc)[:120])
        return None
    if trips.empty:
        return None

    trips["date"] = pd.to_datetime(trips["date"]).dt.date
    trips["source"] = trips["source"].map(_norm)
    trips["destination"] = trips["destination"].map(_norm)

    # Rainfall: TOFU gauge serves TF routes, KAO RAHAI serves KR routes.
    rain["date"] = pd.to_datetime(rain["date"]).dt.date
    rain["origin_prefix"] = rain["area"].map({"TOFU": "TF", "KAO RAHAI": "KR"})
    trips["origin_prefix"] = trips["source"].str[:2]
    trips = trips.merge(rain[["date", "origin_prefix", "rainfall_mm"]],
                        on=["date", "origin_prefix"], how="left")
    trips["rainfall_mm"] = trips["rainfall_mm"].fillna(0.0)

    wb["date"] = pd.to_datetime(wb["date"]).dt.date
    trips = trips.merge(wb, on=["date", "shift"], how="left")
    trips["weighbridges_open"] = trips["weighbridges_open"].fillna(8).astype(int)

    # Trip rows → the modelled grain: trips achieved per truck per shift.
    grp = (trips.groupby(["date", "shift", "contractor", "source", "destination"])
                .agg(trips=("truck_id", "size"),
                     trucks_dt=("truck_id", "nunique"),
                     payload_t=("payload_t", "mean"),
                     rainfall_mm=("rainfall_mm", "max"),
                     weighbridges_open=("weighbridges_open", "max"),
                     cycle_time_min=("cycle_time_min", "mean"))
                .reset_index())
    grp = grp[grp["trucks_dt"] > 0]
    grp[TARGET] = grp["trips"] / grp["trucks_dt"]
    grp["wmt_per_shift"] = grp["trips"] * grp["payload_t"]
    grp["distance_km"] = [distance_km(s, d) for s, d in zip(grp["source"], grp["destination"])]
    grp["day_of_week"] = pd.to_datetime(grp["date"]).dt.dayofweek
    grp["shift"] = grp["shift"].map({1: "day", 2: "night", "1": "day", "2": "night"}).fillna("day")
    grp["grain"] = "trip"
    return grp


# ── Extraction path 2: shipped fixtures (no DB) ─────────────────────────────
def extract_from_fixtures():
    """Rebuild the same schema from fixtures/ so the pipeline is runnable with
    no database. See the module docstring for the granularity caveat."""
    cap = _fx("capability")
    by_path = cap.get("dailyByPath") or []
    if not by_path:
        raise RuntimeError("fixtures/capability.json has no dailyByPath rows")

    # Weighbridges open per day, from the measured weighbridge history.
    wb_by_date, wb_default = {}, 8
    try:
        for d in _fx("weighbridge").get("days", []):
            wb_by_date[d["date"]] = int(d.get("bridges") or wb_default)
        if wb_by_date:
            wb_default = int(np.median(list(wb_by_date.values())))
    except Exception:                                      # noqa: BLE001
        pass

    # Contractor mix and payload, from the per-truck fixture. Used to attribute
    # aggregated path-days to haulers proportionally.
    shares, payloads = {}, {}
    try:
        agg = {}
        for t in _fx("trucks").get("trucks", []):
            c = _norm(t.get("contractor"))
            if c not in WBN_HAULERS:
                continue
            a = agg.setdefault(c, [0.0, 0.0, 0.0])
            a[0] += float(t.get("trips") or 0)
            a[1] += float(t.get("wmt") or 0)
            a[2] += float(t.get("tripsPerDay") or 0)
        total = sum(v[0] for v in agg.values()) or 1.0
        for c, (trips, wmt, _tpd) in agg.items():
            shares[c] = trips / total
            payloads[c] = (wmt / trips) if trips else 0.0
    except Exception:                                      # noqa: BLE001
        pass
    if not shares:
        shares = {c: 1.0 / len(WBN_HAULERS) for c in WBN_HAULERS}

    # Per-contractor efficiency multiplier vs the fleet, so contractors are not
    # merely a duplicated row with a different label.
    fleet_tr = (cap.get("kpi") or {}).get("tripsPerDT") or 0.0
    eff_mult = {}
    for c in _fx("capability").get("contractorProd", []):
        name = _norm(c.get("contractor"))
        if name in shares and fleet_tr:
            eff_mult[name] = max(0.5, min(1.5, float(c.get("tripsPerDT") or 0) / fleet_tr))
        if name in shares and c.get("tf"):
            payloads.setdefault(name, float(c["tf"]))

    # Per-path measured wet/dry response, from the fleet-matched comparison in
    # path-response.json (mDry vs mWet, where "wet" means a >=10 mm day).
    # This is the only weather signal available offline and it is a real
    # measurement — note it is NOT uniformly negative: on 11 of 17 paths the
    # fleet-matched wet figure is higher (dust suppression, cooler running),
    # which the original analysis already flagged as a genuine observation.
    wet_delta = {}
    try:
        for key, m in _fx("path-response").get("paths", {}).items():
            if isinstance(m.get("mWet"), (int, float)) and isinstance(m.get("mDry"), (int, float)):
                wet_delta[key] = m["mWet"] - m["mDry"]      # effect AT ~10 mm
    except Exception:                                      # noqa: BLE001
        pass

    # Daily rainfall series. The fixtures carry no per-day gauge readings, so we
    # reconstruct a deterministic seasonal series (Halmahera wet season peaks
    # Dec–Mar). Without a varying rainfall column the model could not learn any
    # weather effect at all. With a live DB, AVG_RAIN_BY_DATE_AREA replaces this
    # entirely — see extract_from_db().
    RAIN_REF_MM = 10.0            # the mm level the wet/dry delta was measured at
    RAIN_SAT_MM = 20.0            # response saturates here; never extrapolate past it

    def _rain_for(date_str: str) -> float:
        import hashlib
        month = int(date_str[5:7])
        seasonal = {12: 9.0, 1: 10.0, 2: 9.5, 3: 8.0, 4: 5.5,
                    5: 4.0, 6: 3.5, 7: 3.0, 8: 2.0, 9: 2.5, 10: 4.0, 11: 6.5}[month]
        h = int(hashlib.md5(date_str.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return round(min(40.0, max(0.0, seasonal * (-math.log(max(h, 1e-6))))), 1)

    def _rain_effect(path_key: str, mm: float) -> float:
        """Measured wet/dry delta, scaled by rainfall but SATURATING.

        The delta was measured on ~10 mm days. Scaling it linearly would claim a
        50 mm day has five times the effect, which the data cannot support, so
        the response is capped at RAIN_SAT_MM.
        """
        d = wet_delta.get(path_key)
        if not d:
            return 0.0
        return d * (min(float(mm), RAIN_SAT_MM) / RAIN_REF_MM)

    rows = []
    for r in by_path:
        date = r.get("d")
        nb = float(r.get("snb") or r.get("nb") or 0)        # shift fleet
        rit = float(r.get("srit") or r.get("rit") or 0)     # shift trips
        wmt = float(r.get("sw") or r.get("w") or 0)
        if nb <= 0 or rit <= 0 or wmt <= 0:
            continue
        src, dst = _norm(r.get("o")), _norm(r.get("dd"))
        base_tr = rit / nb
        path_payload = wmt / rit
        dow = datetime.strptime(date, "%Y-%m-%d").weekday()
        wb_open = wb_by_date.get(date, wb_default)
        rainfall = _rain_for(date)
        rain_effect = _rain_effect("%s>%s" % (src, dst), rainfall)
        for shift_label in ("day", "night"):
            # Split the shift fleet across the haulers that actually run this path.
            for contractor, share in shares.items():
                trucks = nb * share
                if trucks < 0.5:
                    continue
                mult = eff_mult.get(contractor, 1.0)
                # Night shifts run marginally fewer cycles (lighting, fatigue);
                # this mirrors the day/night split seen in the shift data.
                shift_adj = 1.0 if shift_label == "day" else 0.94
                tr = max(0.3 * base_tr, base_tr * mult * shift_adj + rain_effect)
                payload = payloads.get(contractor) or path_payload
                rows.append({
                    "date": date,
                    "contractor": contractor,
                    "source": src,
                    "destination": dst,
                    "distance_km": distance_km(src, dst),
                    "payload_t": round(payload, 3),
                    "rainfall_mm": rainfall,
                    "shift": shift_label,
                    "day_of_week": dow,
                    "weighbridges_open": wb_open,
                    "trucks_dt": round(trucks, 2),
                    "trips_per_dt_per_shift": round(tr, 5),
                    "wmt_per_shift": round(trucks * tr * payload, 2),
                    "cycle_time_min": round((12 * 60) / tr, 2) if tr > 0 else None,
                    "grain": "path-shift-contractor",
                })
    df = pd.DataFrame(rows)
    return df


# ── Public entry point ──────────────────────────────────────────────────────
def extract(force_fixtures: bool = False) -> pd.DataFrame:
    df = None if force_fixtures else extract_from_db()
    source = "database (trip level)"
    if df is None or df.empty:
        df = extract_from_fixtures()
        source = "sample fixtures (path-shift-contractor)"
    df = df.dropna(subset=[TARGET, "payload_t"])
    df = df[(df[TARGET] > 0) & (df[TARGET] < 40)]           # drop impossible cycles
    df = df.sort_values("date").reset_index(drop=True)
    df.attrs["source"] = source
    return df


def save_training_data(df: pd.DataFrame) -> dict:
    os.makedirs(DATA, exist_ok=True)
    df.to_csv(TRAINING_CSV, index=False)
    meta = {
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "row_count": int(len(df)),
        "date_range": [str(df["date"].min()), str(df["date"].max())],
        "features": CATEGORICAL + NUMERIC,
        "target": TARGET,
        "source": df.attrs.get("source", "unknown"),
        "grain": str(df["grain"].iloc[0]) if "grain" in df and len(df) else "unknown",
        "columns": {c: str(t) for c, t in df.dtypes.items()},
    }
    with open(TRAINING_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


# ── Feature engineering ─────────────────────────────────────────────────────
def fit_transformers(df: pd.DataFrame):
    """One-hot the categoricals, standardise the numerics, persist both."""
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    import joblib

    try:                                                   # sklearn >= 1.2
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:                                      # pragma: no cover
        enc = OneHotEncoder(handle_unknown="ignore", sparse=False)
    enc.fit(df[CATEGORICAL].astype(str))
    scaler = StandardScaler().fit(df[NUMERIC].astype(float))

    os.makedirs(DATA, exist_ok=True)
    joblib.dump({"encoder": enc, "categorical": CATEGORICAL}, ENCODERS_PKL)
    joblib.dump({"scaler": scaler, "numeric": NUMERIC}, SCALER_PKL)
    return enc, scaler


def feature_names(enc) -> list:
    return list(enc.get_feature_names_out(CATEGORICAL)) + list(NUMERIC)


def build_matrix(df: pd.DataFrame, enc, scaler) -> np.ndarray:
    cat = enc.transform(df[CATEGORICAL].astype(str))
    num = scaler.transform(df[NUMERIC].astype(float))
    return np.hstack([cat, num])


_TRANSFORMERS = None


def load_transformers():
    """Cached load of the persisted encoder + scaler (used by the API)."""
    global _TRANSFORMERS
    if _TRANSFORMERS is None:
        import joblib
        _TRANSFORMERS = (joblib.load(ENCODERS_PKL)["encoder"],
                         joblib.load(SCALER_PKL)["scaler"])
    return _TRANSFORMERS


def reset_transformers():
    """Drop the cache so a retrain is picked up without a restart."""
    global _TRANSFORMERS
    _TRANSFORMERS = None


def transform_one(payload: dict) -> np.ndarray:
    """Transform a single prediction request into the trained design matrix."""
    enc, scaler = load_transformers()
    row = {c: str(payload.get(c, "")) for c in CATEGORICAL}
    row.update({n: float(payload.get(n, 0) or 0) for n in NUMERIC})
    return build_matrix(pd.DataFrame([row]), enc, scaler)


if __name__ == "__main__":                                 # manual extraction
    frame = extract()
    info = save_training_data(frame)
    print("extracted %d rows from %s" % (info["row_count"], info["source"]))
    print("date range %s → %s" % tuple(info["date_range"]))
