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
import re
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


# ── Area-name canonicalisation ──────────────────────────────────────────────
# The DB does not store clean node names. Real ORIGIN_AREA values look like
# "TOS_TF", "TOS_KRENE_PPP_06-WBN矿业部", "TOS_BLB"; destinations look like
# "FENI A", "HUAFEI.C01", "POS16-WBN矿业部", "CUU_KM10-WBN矿业部".
#
# This matters more than it appears. CORRIDOR_KM is keyed on clean names, so
# without this every real row missed the lookup and silently took the 25 km
# median — a constant, useless distance feature. The rainfall join also keys on
# the first two characters of the source: raw "TOS_TF" yields "TO", which
# matches no gauge, so every row got 0 mm and the weather signal vanished
# entirely. Both bugs are invisible without the DB, which is why they survived.
# Cut from the first non-ASCII (CJK) character onward, plus any owner/department
# tag. Matching on the hyphen alone is not enough: "POS16-WBN矿业部" has one but
# "CUU_KM10-WBN矿业部" needs the CJK rule, and the tag appears with or without a
# separator. Vendor tags ("-PT.BSE", "-LVMI镍铁事业部", "-HUAFEI") name the
# COMPANY, not the place, so they are noise for a route label.
_STRIP_SUFFIX = re.compile(r"[^\x00-\x7F].*$")
_STRIP_DEPT = re.compile(
    r"[-–_\s]*(?:PT\.?\s*)?(?:WBN|BSE|IWIP|LVMI|HUAFEI|HPN|WASTECINTERNATIONAL)"
    r"[A-Z0-9.\s]*$")
# "TOS" is a stockpile prefix. It appears as "TOS_TF" and, unhelpfully, glued on
# as "TOSTOFU"/"TOSBLB". Only strip the glued form when a known node remains,
# so a genuine name merely starting with those letters is never mangled.
_TOS_PREFIX = re.compile(r"^TOS[_\s]+")
_TOS_GLUED = re.compile(r"^TOS(?=[A-Z])")
_TRAILING_UNIT = re.compile(r"[-_\s]+(?:[A-Z]{2,4})?[-_\s]*\d{1,2}(?:[-_\s]*EXT)?$")

# Explicit aliases beat clever regex. These are the raw spellings the DB uses
# for corridor nodes; anything not listed keeps its cleaned name.
_AREA_ALIAS = {
    "TOFU": "TF", "KRENE": "KR",
    "FENI 0": "FENI KM0", "FENI": "FENI KM0", "FENI 15": "FENI KM15",
    "CUU KM 10": "CUU KM10", "CUU KM10": "CUU KM10", "POS CUU": "CUU KM10",
    "POSCBB": "POS CBB", "POSBLB": "BLB", "TOSBLB": "BLB", "TOSTOFU": "TF",
}
_POS_SPACING = re.compile(r"^POS[\s_]*(\d+)$")
# BSE tips (BSE-1, BSE1, BSE2, BSE5, BSE101, "BSE1号堆场") are bays of one
# hydrometallurgy plant; HUAFEI.B01/C01/HUAFEIC01 likewise. Collapsing each
# family to a single node stops one destination fragmenting into six routes,
# which is what made trips-per-truck unstable for those tips.
_BSE_FAMILY = re.compile(r"^BSE[-\s.]?\d*$")
_HUAFEI_FAMILY = re.compile(r"^HUAFEI[-\s.]?[A-Z]?\.?\d*$")

# A few tips are recorded ONLY in Chinese ("华飞KM8-4-华飞镍钴" is Huafei KM8).
# Stripping non-ASCII first would leave nothing and silently discard the rows,
# so these are matched before any cleaning. 华飞 = Huafei, 镍钴 = nickel-cobalt.
_CJK_HINTS = (("华飞", "HUAFEI"), ("湿法冶金", "BSE"))


def canonical_area(name: str) -> str:
    """Reduce a raw DB area string to the corridor node it belongs to.

    "TOS_TF_STM_13-WBN矿业部" -> "TF"      (a loading spur at Tofu)
    "TOS_KRENE_PPP_06"        -> "KR"      (a loading spur at Krene)
    "FENI A" / "FENI U2"      -> "FENI KM0" (tips at the FENI plant)
    "POS16-WBN矿业部"          -> "POS 16"
    Unknown names are returned normalised so they stay distinguishable as
    categorical values rather than being collapsed into one bucket.
    """
    s = _norm(name)
    if not s:
        return ""
    # A name that OPENS with a CJK marker has no usable ASCII node to recover
    # ("华飞KM8-4" leaves only "KM"), so resolve it from the marker itself.
    for hint, node in _CJK_HINTS:
        if s.startswith(hint):
            return node
    s = _STRIP_SUFFIX.sub("", s).strip()      # drop CJK tail ("...矿业部")
    if not s:
        return ""                             # name was purely CJK
    # Drop the owner/department tag, but never let it consume the whole name:
    # "BSE101" is a tip, not a department, and must survive as BSE.
    _dept = _STRIP_DEPT.sub("", s).strip(" -–_.")
    s = _dept if _dept else s
    s = _TOS_PREFIX.sub("", s).strip()        # drop the "TOS_" stockpile prefix
    s = s.replace("_", " ").strip()
    s = re.sub(r"\s+", " ", s).strip(" -–")
    if not s:
        return ""
    s = _POS_SPACING.sub(r"POS \1", s)        # "POS16" -> "POS 16"
    s = _AREA_ALIAS.get(s, s)
    # Un-glue "TOSTOFU"/"TOSBLB" only if a known node is left behind.
    if s not in CORRIDOR_KM and _TOS_GLUED.match(s):
        candidate = _AREA_ALIAS.get(s[3:], s[3:])
        if candidate in CORRIDOR_KM or candidate in ("BLB", "TF", "KR"):
            s = candidate
    if _BSE_FAMILY.match(s):                  # BSE-1 / BSE1 / BSE2 / BSE101
        return "BSE"
    if _HUAFEI_FAMILY.match(s) or s.startswith("HUAFEI"):
        return "HUAFEI"
    if s in CORRIDOR_KM:                      # exact node, e.g. "POS 12"
        return s
    # Strip a trailing crew/pad number ("TF STM 13" -> "TF"), but only when what
    # remains is a known node, so "POS 12" is never truncated to "POS".
    stripped = _TRAILING_UNIT.sub("", s).strip()
    stripped = _AREA_ALIAS.get(stripped, stripped)
    if stripped != s and (stripped in CORRIDOR_KM or stripped in WBN_HAULERS):
        s = stripped
    head = s.split()[0] if s else ""
    if head == "FENI":
        # FENI KM15 is a distinct point 15 km up the corridor; every other FENI
        # tip (A/W/Q/U1/U2/M/S/K/L1...) is a bay inside the plant at KM0.
        return "FENI KM15" if s in ("FENI KM15", "FENI 15") else "FENI KM0"
    if head in ("HUAFEI", "HUAFEI.B01", "HUAFEI.C01") or s.startswith("HUAFEI."):
        return "HUAFEI"
    if s in CORRIDOR_KM:
        return s
    if head in CORRIDOR_KM and head in ("TF", "KR"):
        return head
    return s


def distance_km(source: str, destination: str) -> float:
    """Haul distance from the corridor chainage lookup.

    Both endpoints on the corridor → |Δ chainage|. Otherwise fall back to the
    median observed haul so an unmapped spur never produces a null feature.
    """
    a = CORRIDOR_KM.get(canonical_area(source))
    b = CORRIDOR_KM.get(canonical_area(destination))
    if a is None or b is None:
        return _MEDIAN_HAUL_KM
    return round(abs(a - b), 2)


def _fx(name):
    with open(os.path.join(FX, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


# ── Extraction path 1: the real database (trip level) ───────────────────────
# HAULAGE_IWIP_CLEAN is a WEIGHBRIDGE-TICKET table: one row per weighed load,
# NOT one row per timed haul cycle. It therefore carries no CYCLE_TIME /
# LOADING_TIME / HAULING_TIME / DUMPING_TIME / RETURN_TIME columns, and the
# payload column is WMT (wet metric tonnes), not TONNAGE. An earlier version of
# this query asked for those six columns; SQL Server rejected it and _register's
# blanket except sent every request silently back to the fixtures — the DB path
# looked "available" while never actually running. Keep this SELECT aligned with
# INFORMATION_SCHEMA or that failure mode returns.
#
# One ticket == one completed delivery == one trip, so trips are counted by
# ticket. Cycle time is derived below from FIRST_WB_TIME/SECOND_WB_TIME rather
# than read from a column that does not exist.
TRIP_LEVEL_SQL = """
SELECT  h.[DATE]                AS date,
        h.CONTRACTOR            AS contractor,
        h.TRUCK_ID              AS truck_id,
        h.ORIGIN_AREA           AS source,
        h.DESTINATION_AREA      AS destination,
        h.SHIFT                 AS shift,
        h.WMT                   AS payload_t,
        h.FIRST_WB_TIME         AS first_wb_time,
        h.SECOND_WB_TIME        AS second_wb_time
FROM    HAULAGE_IWIP_CLEAN h
WHERE   h.[DATE] >= DATEADD(month, -20, GETDATE())
  AND   h.[DATE] <= CONVERT(date, GETDATE())
  AND   h.CONTRACTOR IN ({haulers})
  AND   h.WMT > 0
  AND   h.TRUCK_ID IS NOT NULL AND h.TRUCK_ID <> ''
  AND   h.ORIGIN_AREA IS NOT NULL AND h.DESTINATION_AREA IS NOT NULL
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
        # Loud, and with the real error text. This used to print a truncated
        # message and silently return fixtures, which is how a query naming six
        # non-existent columns survived unnoticed: the app reported a "database"
        # data mode while actually serving sample data.
        print("\n[pipeline] !! DB EXTRACTION FAILED — FALLING BACK TO FIXTURES !!")
        print("[pipeline] %s: %s" % (type(exc).__name__, exc))
        print("[pipeline] Training data will be SYNTHETIC. Fix the query above "
              "before trusting any metric produced from this run.\n")
        return None
    if trips.empty:
        return None

    trips["date"] = pd.to_datetime(trips["date"]).dt.date
    # Canonicalise BEFORE grouping: the raw table splits one physical route
    # across dozens of per-crew spur names ("TOS_TF_STM_13", "TOS_TF_SMA_02"),
    # which would otherwise shatter each path into tiny groups and make
    # trips-per-truck meaningless.
    trips["source"] = trips["source"].map(canonical_area)
    trips["destination"] = trips["destination"].map(canonical_area)
    trips = trips[(trips["source"] != "") & (trips["destination"] != "")
                  & (trips["source"] != trips["destination"])]

    # Rainfall: TOFU gauge serves TF routes, KAO RAHAI serves KR routes.
    # Joined on the canonical origin node, not source[:2] — raw origins begin
    # "TOS_", so the old prefix produced "TO" and never matched a gauge.
    rain["date"] = pd.to_datetime(rain["date"]).dt.date
    rain["origin_prefix"] = rain["area"].map({"TOFU": "TF", "KAO RAHAI": "KR"})
    rain = rain.dropna(subset=["origin_prefix", "rainfall_mm"])
    rain = rain.groupby(["date", "origin_prefix"], as_index=False)["rainfall_mm"].max()
    trips["origin_prefix"] = trips["source"]
    trips = trips.merge(rain[["date", "origin_prefix", "rainfall_mm"]],
                        on=["date", "origin_prefix"], how="left")
    # Gauges stopped reporting after 2026-04-06. Leave those rows NaN here and
    # record the true coverage, so a gap is never silently modelled as "dry".
    rain_cov = float(trips["rainfall_mm"].notna().mean()) if len(trips) else 0.0
    trips["rainfall_mm"] = trips["rainfall_mm"].fillna(0.0)

    wb["date"] = pd.to_datetime(wb["date"]).dt.date
    trips = trips.merge(wb, on=["date", "shift"], how="left")
    trips["weighbridges_open"] = trips["weighbridges_open"].fillna(8).astype(int)

    # Cycle time is not stored; derive it from the two weighbridge timestamps
    # (loaded weigh -> tare weigh). Implausible values are dropped rather than
    # clamped so they cannot drag the mean: negatives come from clock skew and
    # multi-hour gaps are shift breaks, not cycles.
    fwb = pd.to_datetime(trips["first_wb_time"], errors="coerce")
    swb = pd.to_datetime(trips["second_wb_time"], errors="coerce")
    cycle = (swb - fwb).dt.total_seconds() / 60.0
    trips["cycle_time_min"] = cycle.where((cycle > 0) & (cycle < 720))

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
    grp.attrs["rain_coverage"] = round(rain_cov, 4)
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
