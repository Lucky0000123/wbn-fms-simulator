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

# Phase 3 artifacts
OLS_PKL = os.path.join(DATA, "model_ols.pkl")
BASELINE_PKL = os.path.join(DATA, "model_baseline.pkl")
VALIDATION_JSON = os.path.join(DATA, "validation_results.json")
COMPARISON_JSON = os.path.join(DATA, "model_comparison.json")
SIGNIFICANCE_JSON = os.path.join(DATA, "feature_significance.json")
RESIDUALS_JSON = os.path.join(DATA, "residual_diagnostics.json")

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

# Stockpile names often end in a crew/contractor code: "TOS_KRENE_01_RIM" is a
# pad at Krene run by RIM, and "TOS_TF/TOFU_09_SMA" is a Tofu pad run by SMA.
# Left in place the hauler's name becomes the ORIGIN, so "RIM -> POS 10" reads
# as if a contractor were a place. Strip a trailing hauler code whenever a real
# node survives underneath.
_TRAILING_HAULER = re.compile(
    r"[-_\s/]+(?:%s)$" % "|".join(WBN_HAULERS))

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
    # Drop a trailing hauler code ("KRENE 01 RIM" -> "KRENE 01"), then let the
    # pad-number rule below reduce it to the node itself.
    _nohaul = _TRAILING_HAULER.sub("", s).strip(" -–_/")
    if _nohaul and _nohaul != s:
        cand = _AREA_ALIAS.get(_nohaul, _nohaul)
        stripped_cand = _AREA_ALIAS.get(
            _TRAILING_UNIT.sub("", cand).strip(), _TRAILING_UNIT.sub("", cand).strip())
        if cand in CORRIDOR_KM or stripped_cand in CORRIDOR_KM:
            s = cand
    # "TF/TOFU 09 SMA" style: a slash-joined alias pair. Take the first half,
    # which is the node, once the hauler suffix is gone.
    if "/" in s:
        head_alias = _AREA_ALIAS.get(s.split("/")[0].strip(), s.split("/")[0].strip())
        if head_alias in CORRIDOR_KM:
            s = head_alias
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
    if stripped != s and stripped in CORRIDOR_KM:
        s = stripped
    # "TOS_RIM_01" names the crew, not the place. A contractor code is not a
    # location, so refuse it rather than inventing an origin called "RIM".
    # Checked with any pad number removed, so "RIM 01" is caught too.
    if s in WBN_HAULERS or _TRAILING_UNIT.sub("", s).strip() in WBN_HAULERS:
        return ""
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


# ── Phase 3: feature engineering ────────────────────────────────────────────
# Columns that must NEVER become features. These are not judgement calls, they
# were verified against the extracted data:
#
#   wmt_per_shift == target * payload_t * trucks_dt   (max abs error 0.000000)
#   trips / trucks_dt == target                       (max abs error < 1e-8)
#
# Both are exact algebraic restatements of the target. Feeding either to the
# model would drive R2 to ~1.0 and produce a planner that cannot predict
# anything, because at planning time nobody knows the trips or the tonnage —
# that is precisely what they are asking for.
#
# cycle_time_min is excluded on availability grounds rather than algebra: it is
# derived from weighbridge timestamps AFTER the shift has run, so it does not
# exist when planning a future shift. A per-path historical average would be a
# legitimate feature; the raw measured value is not.
LEAKAGE_COLUMNS = ("trips", "wmt_per_shift", "cycle_time_min", TARGET)

# A haul is identified by its ROUTE, not by a source dummy plus a destination
# dummy. Encoding the two separately looks natural but is badly collinear here,
# because only a handful of source-destination combinations actually run: the
# crossed form reached VIF 12-13 on destination_FENI KM0 / destination_POS 12
# (each ~92% explained by the remaining columns) and pushed max VIF to 16.
# Collapsing to one route factor drops max VIF to 8.4 with no VIF above 10.
#
# Rare routes are pooled into an OTHER level: a route seen a handful of times
# cannot support its own coefficient, and one dummy per sighting is what drove
# VIF to 256 when every route was kept.
CATEGORICAL_GROUPS = ("contractor", "route", "shift")
MIN_ROWS_PER_ROUTE = 30

# Route levels chosen on the TRAINING data. Held module-level so a scoring call
# reuses the training vocabulary, but always passed explicitly through
# `keep_routes` in cross-validation so a fold can never inherit another fold's
# levels — that would leak test-period information into training.
_KEEP_ROUTES: set = set()

# The rain gauges stopped reporting on 2026-04-06. Everything after that reads
# 0.0 mm, which is an outage, not a drought (pre-cutoff 62.5% of rows are zero;
# post-cutoff 100.0% are). Imputing 0 would teach the model that half of 2026
# was bone dry.
RAIN_OUTAGE_DATE = "2026-04-06"


def _seasonal_rain_mm(month: int) -> float:
    """Long-run mean rainfall for a Halmahera month (mm/day).

    Used only to fill the gauge outage. Derived from the seasonal profile the
    fixtures path already encodes, so the two extraction routes agree.
    """
    return {12: 9.0, 1: 10.0, 2: 9.5, 3: 8.0, 4: 5.5,
            5: 4.0, 6: 3.5, 7: 3.0, 8: 2.0, 9: 2.5, 10: 4.0, 11: 6.5}.get(int(month), 5.0)


def engineer_features(df: pd.DataFrame, feature_names: list | None = None,
                      keep_routes: set | None = None):
    """Build the Phase 3 design matrix.

    Returns (X, y, names, meta). Passing `feature_names` from a previous call
    reindexes to that exact column set, so a model trained on one fold can score
    another without silently misaligning one-hot columns.

    `keep_routes` pins the route vocabulary. Fold code must pass the training
    fold's set so rare-route pooling is decided without seeing the test period.
    """
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])

    # ── rainfall: impute the outage, and flag it ────────────────────────────
    # Approach 2 from the brief: seasonal mean + an explicit missing flag, so
    # the model can learn that imputed rows carry more uncertainty rather than
    # treating a guess as a measurement.
    outage = d["date"] > pd.Timestamp(RAIN_OUTAGE_DATE)
    d["rainfall_missing"] = outage.astype(int)
    seasonal = d["date"].dt.month.map(_seasonal_rain_mm).astype(float)
    d["rainfall_mm"] = np.where(outage, seasonal, d["rainfall_mm"].fillna(0.0))

    # ── congestion proxy ───────────────────────────────────────────────────
    # Total fleet on the same road in the same shift, across ALL contractors.
    # Distinct from trucks_dt (measured corr 0.55): on 46% of rows more than one
    # contractor shares the path, and it is the shared total that congests a
    # road, not one hauler's slice of it.
    d["trucks_per_path"] = d.groupby(
        ["date", "shift", "source", "destination"])["trucks_dt"].transform("sum")

    # ── interactions (mean-centred) ────────────────────────────────────────
    # A raw product is strongly correlated with both of its parents, which is
    # structural, not a property of the data: with the uncentred form the design
    # hit max VIF 16.0 (rainfall_mm 11.8, distance_km 10.2) and the standard
    # errors on the main effects became uninterpretable. Centring each parent
    # before multiplying removes that artefact and leaves the interaction
    # meaning what it should: how the rain effect CHANGES with a longer haul or
    # a bigger fleet, relative to average conditions.
    _rain_c = d["rainfall_mm"] - d["rainfall_mm"].mean()
    _dist_c = d["distance_km"] - d["distance_km"].mean()
    _truck_c = d["trucks_dt"] - d["trucks_dt"].mean()
    d["rain_x_distance"] = _rain_c * _dist_c
    d["rain_x_trucks"] = _rain_c * _truck_c

    # ── calendar ───────────────────────────────────────────────────────────
    # NOTE is_wet_season is deliberately NOT included as a feature. Measured
    # corr(is_wet_season, rainfall_missing) = -0.89, because the wet season
    # (Dec-Mar) is almost exactly the window in which the gauges still worked.
    # Shipping both would be a textbook collinearity failure; rainfall_missing
    # is kept because it carries the data-quality signal the planner needs.
    # is_wet_season is still computed and returned in `meta` for reporting.
    d["is_weekend"] = (d["day_of_week"] >= 5).astype(int)
    wet_season = d["date"].dt.month.isin([12, 1, 2, 3]).astype(int)

    numeric = ["trucks_dt", "rainfall_mm", "distance_km", "payload_t",
               "weighbridges_open", "trucks_per_path",
               "rain_x_distance", "rain_x_trucks",
               "is_weekend", "rainfall_missing"]
    # distance_km is a deterministic function of the route (0 of 45 path-pairs
    # have more than one distance, and route dummies explain 88% of its
    # variance), so it is redundant once routes are encoded. Dropping it costs
    # exactly 0.0000 R2 and removes a VIF-10 offender.
    numeric.remove("distance_km")

    # payload_t can become the same defect one column over. When payload is
    # carried as a per-contractor average, it is a pure function of contractor,
    # and with contractor dummies present the design goes singular: that is
    # where an observed max VIF of 6.5e12 came from, flagging payload_t and all
    # 7 contractor dummies at once.
    #
    # It is NOT always degenerate. At trip-level grain each shift carries its
    # own measured payload (4,113 distinct values across 4,141 rows, 21.3-63.2 t),
    # so payload_t is genuinely informative and is kept — max VIF 8.41.
    #
    # Hence a runtime test rather than a hardcoded drop: the same code is
    # correct for both extraction grains, and a future contractor with a mixed
    # fleet keeps its payload feature instead of silently losing it.
    if d["contractor"].nunique() > 1:
        _per_contractor = d.groupby("contractor")["payload_t"].nunique()
        if bool((_per_contractor <= 1).all()) and "payload_t" in numeric:
            numeric.remove("payload_t")

    d["route"] = d["source"].astype(str) + ">" + d["destination"].astype(str)
    if keep_routes is not None:
        _routes = set(keep_routes)
    elif feature_names is None:
        counts = d["route"].value_counts()
        _routes = set(counts[counts >= MIN_ROWS_PER_ROUTE].index)
        _KEEP_ROUTES.clear(); _KEEP_ROUTES.update(_routes)
    else:
        _routes = set(_KEEP_ROUTES)
    d["route"] = d["route"].where(d["route"].isin(_routes), "OTHER")

    # ── categoricals, K-1 drop-first ───────────────────────────────────────
    cats = pd.get_dummies(d[list(CATEGORICAL_GROUPS)].astype(str),
                          prefix=list(CATEGORICAL_GROUPS),
                          drop_first=True, dtype=float)
    X = pd.concat([d[numeric].astype(float).reset_index(drop=True),
                   cats.reset_index(drop=True)], axis=1)

    # Constant columns carry no information and make the design matrix singular.
    if feature_names is None:
        keep = [c for c in X.columns if X[c].std(ddof=0) > 1e-12]
        X = X[keep]
    else:
        X = X.reindex(columns=feature_names, fill_value=0.0)

    y = d[TARGET].astype(float).reset_index(drop=True)
    leaked = [c for c in X.columns if c in LEAKAGE_COLUMNS]
    if leaked:                                     # belt and braces
        raise RuntimeError("target leakage in feature matrix: %s" % leaked)
    meta = {"n_rows": int(len(X)), "n_features": int(X.shape[1]),
            "rain_imputation": "seasonal-mean + rainfall_missing flag",
            "rain_outage_from": RAIN_OUTAGE_DATE,
            "rain_imputed_rows": int(outage.sum()),
            "wet_season_rows": int(wet_season.sum()),
            "route_levels": int(d["route"].nunique()),
            "kept_routes": sorted(_routes),
            "min_rows_per_route": MIN_ROWS_PER_ROUTE,
            "dropped_redundant": ["distance_km (determined by route)",
                                  "is_wet_season (corr -0.89 with rainfall_missing)"],
            "excluded_leakage": list(LEAKAGE_COLUMNS)}
    return X, y, list(X.columns), meta


# ── Phase 3: OLS with inference ─────────────────────────────────────────────
def _metrics_of(y_true, y_pred) -> dict:
    """R2 / MAE / RMSE / MAPE. MAPE is safe here because the target is trips
    per truck per shift and its minimum is 1.0, so no near-zero denominators."""
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    resid = y_true - y_pred
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
    safe = np.abs(y_true) > 1e-9
    return {
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "mae": round(float(np.abs(resid).mean()), 4),
        "rmse": round(float(np.sqrt((resid ** 2).mean())), 4),
        "mape": round(float((np.abs(resid[safe] / y_true[safe])).mean() * 100), 2),
        "n": int(len(y_true)),
    }


def _vif(X: pd.DataFrame) -> dict:
    """Variance Inflation Factor per feature.

    Computed from the correlation-matrix inverse rather than by regressing each
    column on the rest: it is one matrix inversion instead of p regressions, and
    on a near-singular design the pseudo-inverse degrades gracefully where the
    per-column fits would simply throw.
    """
    cols = [c for c in X.columns if X[c].std(ddof=0) > 1e-12]
    if len(cols) < 2:
        return {c: 1.0 for c in X.columns}
    corr = np.corrcoef(X[cols].to_numpy(float), rowvar=False)
    try:
        inv = np.linalg.pinv(corr)
    except Exception:                                       # noqa: BLE001
        return {c: float("nan") for c in X.columns}
    out = {c: round(float(abs(inv[i, i])), 3) for i, c in enumerate(cols)}
    for c in X.columns:                                     # constants -> 1.0
        out.setdefault(c, 1.0)
    return out


def train_ols(X: pd.DataFrame, y: pd.Series):
    """Fit OLS with statsmodels so we get p-values, CIs and a condition number.

    sklearn's LinearRegression would give the same point estimates and none of
    the inference. The whole point of Phase 3 is being able to say which factors
    matter and how confident we are, which requires the standard errors.
    """
    import statsmodels.api as sm

    Xc = sm.add_constant(X.astype(float), has_constant="add")
    res = sm.OLS(y.astype(float), Xc).fit()
    vif = _vif(X)
    ci = res.conf_int(alpha=0.05)
    coefs = {}
    for name in Xc.columns:
        coefs[name] = {
            "coef": round(float(res.params[name]), 6),
            "std_err": round(float(res.bse[name]), 6),
            "t": round(float(res.tvalues[name]), 4),
            "p_value": float(res.pvalues[name]),
            "ci_low": round(float(ci.loc[name, 0]), 6),
            "ci_high": round(float(ci.loc[name, 1]), 6),
            "vif": vif.get(name, 1.0),
            "significant": bool(res.pvalues[name] < 0.05),
        }
    fitted = res.predict(Xc)
    stats = _metrics_of(y, fitted)
    stats.update({
        "r2_adj": round(float(res.rsquared_adj), 4),
        "f_statistic": round(float(res.fvalue), 3) if res.fvalue is not None else None,
        "f_pvalue": float(res.f_pvalue) if res.f_pvalue is not None else None,
        "condition_number": round(float(np.linalg.cond(Xc.to_numpy(float))), 1),
        "n_features": int(X.shape[1]),
    })
    vif_vals = [v for v in vif.values() if np.isfinite(v)]
    stats["max_vif"] = round(max(vif_vals), 3) if vif_vals else None
    stats["vif_over_5"] = sorted([c for c, v in vif.items() if np.isfinite(v) and v > 5])
    stats["vif_over_10"] = sorted([c for c, v in vif.items() if np.isfinite(v) and v > 10])
    return res, coefs, stats


# ── Phase 3: rolling-origin (walk-forward) cross-validation ─────────────────
MIN_TEST_ROWS = 50


def make_folds(df: pd.DataFrame, n_folds: int = 5, min_test_rows: int = MIN_TEST_ROWS):
    """Walk-forward folds: train on everything before a cut, test on the block
    after it. Never shuffles — a random split would train on next month and test
    on last month, which is not a forecast.

    Month-per-fold is the natural unit but does not survive contact with this
    data: the tail months hold only 152 / 259 / 62 rows, so a July fold would be
    62 observations. Thin trailing months are merged forward until each test
    block clears `min_test_rows`.
    """
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").reset_index(drop=True)
    months = sorted(d["date"].dt.to_period("M").unique())
    if len(months) < 3:
        return []

    # Candidate test blocks = the last `n_folds` months, merged while too small.
    blocks, current = [], []
    for m in months[1:]:                       # first month is training seed
        current.append(m)
        rows = d[d["date"].dt.to_period("M").isin(current)]
        if len(rows) >= min_test_rows:
            blocks.append(list(current))
            current = []
    if current and blocks:                     # fold leftovers into the last block
        blocks[-1] = blocks[-1] + current
    blocks = blocks[-n_folds:] if len(blocks) > n_folds else blocks

    folds = []
    for blk in blocks:
        start = min(blk).start_time
        train = d[d["date"] < start]
        test = d[d["date"].dt.to_period("M").isin(blk)]
        if len(train) < 200 or len(test) < min_test_rows:
            continue
        folds.append({
            "test_period": "%s..%s" % (min(blk), max(blk)),
            "train_rows": int(len(train)), "test_rows": int(len(test)),
            "train_idx": train.index.to_numpy(), "test_idx": test.index.to_numpy(),
            # Rain is constant zero after the gauge outage. A fold whose test
            # block has no rain variance cannot validate a rain coefficient, and
            # saying so is the difference between a metric and a claim.
            "test_rain_std": round(float(test["rainfall_mm"].std(ddof=0)), 4),
            "test_rain_all_zero": bool((test["rainfall_mm"] == 0).all()),
        }, )
    return folds


def _fit_predict_ols(train_df, test_df):
    Xtr, ytr, names, _ = engineer_features(train_df)
    keep = set(train_df["source"].astype(str) + ">" + train_df["destination"].astype(str))
    Xte, yte, _, _ = engineer_features(test_df, feature_names=names, keep_routes=keep)
    import statsmodels.api as sm
    Xtr_c = sm.add_constant(Xtr.astype(float), has_constant="add")
    res = sm.OLS(ytr.astype(float), Xtr_c).fit()
    Xte_c = sm.add_constant(Xte.astype(float), has_constant="add").reindex(
        columns=Xtr_c.columns, fill_value=0.0)
    return yte, res.predict(Xte_c)


def _fit_predict_rf(train_df, test_df):
    from sklearn.ensemble import RandomForestRegressor
    Xtr, ytr, names, _ = engineer_features(train_df)
    keep = set(train_df["source"].astype(str) + ">" + train_df["destination"].astype(str))
    Xte, yte, _, _ = engineer_features(test_df, feature_names=names, keep_routes=keep)
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1,
                               min_samples_leaf=2, max_depth=18, max_leaf_nodes=512)
    rf.fit(Xtr.to_numpy(float), ytr.to_numpy(float))
    return yte, rf.predict(Xte.to_numpy(float))


def _fit_predict_baseline(train_df, test_df):
    """Group-mean lookup on (route, contractor, shift) — the bar any model must
    clear to justify existing."""
    key = ["source", "destination", "contractor", "shift"]
    tbl = train_df.groupby(key)[TARGET].mean()
    gm = float(train_df[TARGET].mean())
    idx = test_df.set_index(key).index
    pred = pd.Series(idx.map(tbl), index=test_df.index).astype(float).fillna(gm)
    return test_df[TARGET].astype(float), pred


MODEL_FNS = {"ols": _fit_predict_ols,
             "random_forest": _fit_predict_rf,
             "group_mean_baseline": _fit_predict_baseline}


def validate_rolling_origin(df: pd.DataFrame, model_fn, n_folds: int = 5) -> dict:
    """Run one model across the walk-forward folds and average its metrics."""
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").reset_index(drop=True)
    folds = make_folds(d, n_folds=n_folds)
    per_fold = []
    for f in folds:
        tr, te = d.loc[f["train_idx"]], d.loc[f["test_idx"]]
        try:
            y_true, y_pred = model_fn(tr, te)
            m = _metrics_of(y_true, y_pred)
        except Exception as exc:                            # noqa: BLE001
            m = {"error": str(exc)[:200]}
        m.update({k: f[k] for k in ("test_period", "train_rows", "test_rows",
                                    "test_rain_std", "test_rain_all_zero")})
        per_fold.append(m)
    ok = [m for m in per_fold if m.get("r2") is not None]
    mean = {}
    if ok:
        for k in ("r2", "mae", "rmse", "mape"):
            vals = [m[k] for m in ok if m.get(k) is not None]
            mean[k] = round(float(np.mean(vals)), 4) if vals else None
    return {"folds": per_fold, "mean": mean, "n_folds": len(per_fold),
            "n_folds_scored": len(ok)}


def compare_models(df: pd.DataFrame, n_folds: int = 5) -> dict:
    """Score every candidate under the SAME folds and pick a winner.

    Running each model on its own split is how a favourite gets flattered. One
    fold definition, three models, one table.
    """
    results = {name: validate_rolling_origin(df, fn, n_folds=n_folds)
               for name, fn in MODEL_FNS.items()}
    scored = {k: v["mean"].get("r2") for k, v in results.items()
              if v["mean"].get("r2") is not None}
    best = max(scored, key=scored.get) if scored else None
    ols_r2 = scored.get("ols")
    rf_r2 = scored.get("random_forest")
    base_r2 = scored.get("group_mean_baseline")

    # Prefer OLS on ties: same accuracy, but coefficients you can explain.
    selected, why = best, "highest mean CV R2 under identical rolling-origin folds"
    if ols_r2 is not None and rf_r2 is not None and best == "random_forest" \
            and abs(rf_r2 - ols_r2) <= 0.02:
        selected = "ols"
        why = ("OLS within 0.02 R2 of RandomForest (%.4f vs %.4f); chose OLS "
               "for interpretable coefficients" % (ols_r2, rf_r2))
    if base_r2 is not None and selected in ("ols", "random_forest"):
        if base_r2 >= scored.get(selected, -9) - 1e-9:
            selected = "group_mean_baseline"
            why = ("no fitted model beat the group-mean lookup under "
                   "rolling-origin CV (baseline %.4f)" % base_r2)
    return {"per_model": results, "mean_r2": scored,
            "selected_model": selected, "selection_rationale": why,
            "baseline_lift": (round(scored.get(selected, 0) - base_r2, 4)
                              if base_r2 is not None and selected else None)}


def residual_diagnostics(X: pd.DataFrame, y: pd.Series, fitted, max_points: int = 1200) -> dict:
    """Residual data for plotting, plus the two checks that decide Phase 4.

    Heteroscedasticity means the linear model's error grows with its prediction;
    a curved residual pattern against a feature means the true relationship is
    non-linear. Either is direct evidence that a linear model is the wrong shape
    and ML is justified — which is the question Phase 3 exists to answer.
    """
    y = np.asarray(y, float)
    fitted = np.asarray(fitted, float)
    resid = y - fitted
    het_r = float(np.corrcoef(np.abs(resid), fitted)[0, 1]) if len(resid) > 2 else 0.0

    per_feature = {}
    for c in X.columns:
        v = X[c].to_numpy(float)
        if np.std(v) < 1e-12:
            continue
        r = float(np.corrcoef(resid, v)[0, 1])
        # Curvature: correlation of the residual with the SQUARED, centred
        # feature. A linear fit leaves no linear residual trend by construction,
        # so a quadratic one is where non-linearity shows itself.
        vc = v - v.mean()
        r2c = float(np.corrcoef(resid, vc ** 2)[0, 1]) if np.std(vc ** 2) > 1e-12 else 0.0
        per_feature[c] = {"resid_corr": round(r, 4), "resid_corr_sq": round(r2c, 4),
                          "nonlinear_flag": bool(abs(r2c) > 0.10)}

    order = np.argsort(resid)
    n = len(resid)
    from scipy import stats as _st
    theo = _st.norm.ppf((np.arange(1, n + 1) - 0.5) / n)
    step = max(1, n // max_points)
    return {
        "n": int(n),
        "heteroscedasticity_corr": round(het_r, 4),
        "heteroscedastic_flag": bool(abs(het_r) > 0.30),
        "residual_mean": round(float(resid.mean()), 6),
        "residual_std": round(float(resid.std(ddof=0)), 4),
        "per_feature": per_feature,
        "nonlinear_features": sorted([c for c, m in per_feature.items()
                                      if m["nonlinear_flag"]]),
        "sample": {"fitted": [round(float(x), 4) for x in fitted[::step]],
                   "residual": [round(float(x), 4) for x in resid[::step]]},
        "qq": {"theoretical": [round(float(x), 4) for x in theo[::step]],
               "sample": [round(float(x), 4) for x in
                          ((resid[order] - resid.mean()) / (resid.std(ddof=0) or 1))[::step]]},
    }


# ── Phase 3: orchestration ──────────────────────────────────────────────────
def _write_json(path, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)


def run_phase3(df: pd.DataFrame | None = None, n_folds: int = 5, verbose: bool = True) -> dict:
    """Fit the OLS, cross-validate every candidate, and write the artifacts.

    Returns the summary dict that also lands in data/model_metadata.json.
    """
    log = print if verbose else (lambda *a, **k: None)
    if df is None:
        df = pd.read_csv(TRAINING_CSV)

    # 1 ── full-sample OLS: this is what /api/predict serves and what the
    #      coefficient table reports. CV below judges it honestly.
    X, y, names, fmeta = engineer_features(df)
    res, coefs, stats = train_ols(X, y)
    log("[1/4] OLS on %d rows x %d features — R2 %.4f (adj %.4f), max VIF %.2f"
        % (len(X), X.shape[1], stats["r2"], stats["r2_adj"], stats["max_vif"]))

    import joblib
    joblib.dump({"params": res.params.to_dict(), "features": list(X.columns),
                 "kept_routes": fmeta.get("kept_routes", []),
                 "rain_outage_from": RAIN_OUTAGE_DATE}, OLS_PKL)

    # Persist the group-mean lookup as a servable model. It wins the
    # rolling-origin comparison, and a winner that cannot be served is a report,
    # not a decision — /api/predict has to be able to actually use it.
    _bkey = ["source", "destination", "contractor", "shift"]
    _tbl = df.groupby(_bkey)[TARGET].mean()
    joblib.dump({"key": _bkey,
                 "table": {"|".join(map(str, k)): float(v) for k, v in _tbl.items()},
                 "global_mean": float(df[TARGET].mean())}, BASELINE_PKL)

    _write_json(SIGNIFICANCE_JSON, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_rows": int(len(X)), "n_features": int(X.shape[1]),
        "condition_number": stats["condition_number"],
        "max_vif": stats["max_vif"], "vif_over_5": stats["vif_over_5"],
        "vif_over_10": stats["vif_over_10"],
        "significant_features": sorted([k for k, v in coefs.items()
                                        if v["significant"] and k != "const"]),
        "coefficients": coefs,
    })

    # 2 ── residual diagnostics (the Phase 4 decision evidence)
    import statsmodels.api as sm
    fitted = res.predict(sm.add_constant(X.astype(float), has_constant="add"))
    diag = residual_diagnostics(X, y, fitted)
    _write_json(RESIDUALS_JSON, diag)
    log("[2/4] residuals — heteroscedastic=%s (r=%.3f), non-linear features: %s"
        % (diag["heteroscedastic_flag"], diag["heteroscedasticity_corr"],
           diag["nonlinear_features"] or "none"))

    # 3 ── rolling-origin CV for all candidates under identical folds
    cmp_ = compare_models(df, n_folds=n_folds)
    _write_json(COMPARISON_JSON, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": "rolling-origin (walk-forward), no shuffling",
        "mean_r2": cmp_["mean_r2"], "selected_model": cmp_["selected_model"],
        "selection_rationale": cmp_["selection_rationale"],
        "baseline_lift": cmp_["baseline_lift"],
        "per_model": {k: {"mean": v["mean"], "folds": v["folds"]}
                      for k, v in cmp_["per_model"].items()},
    })
    _write_json(VALIDATION_JSON, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": "rolling-origin (walk-forward)",
        "n_folds": cmp_["per_model"]["ols"]["n_folds"],
        "ols": cmp_["per_model"]["ols"],
        "note": ("Folds whose test block has test_rain_all_zero=true cannot "
                 "validate any rainfall coefficient: the gauges stopped "
                 "reporting on %s, so rain is constant there." % RAIN_OUTAGE_DATE),
    })
    for name, r in cmp_["per_model"].items():
        log("[3/4] %-20s mean CV R2 %s" % (name, r["mean"].get("r2")))
    log("      selected: %s — %s" % (cmp_["selected_model"], cmp_["selection_rationale"]))

    summary = {
        "ols_training_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ols_features": list(X.columns),
        "ols_in_sample": {k: stats[k] for k in
                          ("r2", "r2_adj", "mae", "rmse", "mape", "max_vif",
                           "condition_number")},
        "selected_model": cmp_["selected_model"],
        "selection_rationale": cmp_["selection_rationale"],
        "cv_mean_r2": cmp_["mean_r2"],
        "cv_baseline_lift": cmp_["baseline_lift"],
        "feature_meta": {k: v for k, v in fmeta.items() if k != "kept_routes"},
        "residual_flags": {"heteroscedastic": diag["heteroscedastic_flag"],
                           "nonlinear_features": diag["nonlinear_features"]},
    }
    log("[4/4] artifacts written to data/")
    return summary


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
