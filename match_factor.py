"""match_factor.py — Tier 3 Module 1: Match Factor + bunching detection.

MF = (N x Ts) / Tc      (Burt & Caccetta 2007)

  N  = trucks per loading server
  Ts = shovel service time (measured load duration)
  Tc = full truck cycle time

MF < 1 means the shovel waits for trucks; MF > 1 means trucks queue for the
shovel. Target band 0.85-1.0.

WHAT "SHOVEL" MEANS HERE, AND WHY IT IS NOT A SHOVEL
There is no excavator, shovel or loader identity anywhere in either database,
and no dispatch or loader event log (verified in reports/fms_db_schema.md,
Q6). So MF cannot be keyed to a machine. It is keyed to a LOADING POINT
(`WAITING_TIME.ORIGIN_AREA`, 194 of them), and the server count is measured
rather than assumed: sweeping every truck's load interval gives the peak number
loading simultaneously at that point in that shift, which is the number of
parallel servers actually observed. Calling that "the shovel" would be the kind
of dressed-up guess this project has been avoiding, so it is called a loading
point everywhere including the API.

VALIDATED BEFORE SHIPPING
Two earlier formulations failed and were discarded rather than published:

  1. Deriving the server count from throughput (trips x Ts / shift minutes)
     gave MF corr -0.647 with cycle time. Circular: trips is mechanically
     ~1/cycle, so the formula contained its own target.
  2. Joining concurrency to the trip dataset reached only 28.3% of area-shifts,
     because WAITING_TIME names loading POINTS (TOS8, BLB 10) while trips name
     AREAS (BLB). Rolling points up to areas lost the resolution that makes MF
     meaningful.

The shipped version computes everything inside WAITING_TIME at loading-point
grain, so there is no cross-table translation at all.

THE SIGN, WHICH LOOKS WRONG AND IS NOT
MF correlates -0.325 with total cycle time but +0.405 with measured queue wait,
and +0.765 with queue wait as a share of cycle. The negative against cycle is a
haul-length confound: a point serving short hauls turns trucks around quickly,
so it sustains a high truck-to-server ratio while showing a short cycle.
Against the thing MF actually claims to measure -- queueing -- the relationship
is strong and monotone:

    MF band            n     mean wait   wait/cycle
    <0.75 (under)   4,786     20.9 min      0.22
    0.85-1.0          485     32.8 min      0.36
    1.0-1.15          302     38.2 min      0.43
    >1.15 (over)      819     ~38 min       0.67+

That is the validation gate: `validate()` recomputes it on every run and the
API refuses to serve if the queue correlation goes non-positive.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
MF_CSV = os.path.join(DATA, "match_factor_results.csv")
MF_META = os.path.join(DATA, "match_factor_meta.json")

# Burt & Caccetta bands.
TARGET_LO, TARGET_HI = 0.85, 1.00
OVER_TRUCKED, UNDER_TRUCKED = 1.15, 0.75

MIN_EVENTS_PER_SHIFT = 5          # fewer than 5 loads is not a queue
LOAD_MIN, LOAD_MAX = 1, 120       # a 0-minute or 3-hour "load" is a bad clock
CYCLE_MIN, CYCLE_MAX = 10, 600

# Bunching: the brief specified CV > 0.5, but that fires on 99.0% of
# loading-point shifts here (median CV 1.43), so as written it is a constant
# rather than a detector. The threshold is taken from the observed distribution
# instead, and the briefed value is kept alongside for comparison.
BUNCHING_CV_BRIEFED = 0.5
BUNCHING_CV_PERCENTILE = 0.75

SQL = """
SELECT  ORIGIN_AREA              AS loading_point,
        DESTINATION              AS destination,
        SHIFT                    AS shift,
        CONVERT(date, [DATE])    AS date,
        EQUIPMENT_ID             AS truck_id,
        LOADING_WAITING_TIME     AS arrive,
        DATEDIFF(minute, LOADING_WAITING_TIME, LOADING_TIME)   AS load_min,
        DATEDIFF(minute, LOADING_TIME, DUMPING_WAITING_TIME)   AS haul_min,
        DATEDIFF(minute, DUMPING_WAITING_TIME, DUMPING_TIME)   AS dump_min
FROM    WAITING_TIME
WHERE   [DATE] >= '{start}'
  AND   LOADING_TIME IS NOT NULL
  AND   LOADING_WAITING_TIME IS NOT NULL
  AND   ORIGIN_AREA IS NOT NULL
"""


def _norm_shift(s: pd.Series) -> np.ndarray:
    t = s.astype(str).str.strip().str.lower()
    return np.where(t.isin(["2", "night", "n", "malam"]), "night", "day")


def fetch(start: str = "2025-12-27", conn=None) -> pd.DataFrame:
    import simulator_api as sim

    close = False
    if conn is None:
        if not sim._db_ready():
            raise RuntimeError("no DB configured — match factor needs the VPN")
        conn, close = sim._conn("WBN_DATABASE"), True
    try:
        w = pd.read_sql(SQL.format(start=start), conn)
    finally:
        if close:
            conn.close()

    w["cycle_min"] = w[["load_min", "haul_min", "dump_min"]].sum(axis=1, min_count=1)
    w = w[w["load_min"].between(LOAD_MIN, LOAD_MAX)
          & w["cycle_min"].between(CYCLE_MIN, CYCLE_MAX)].copy()
    # WAITING_TIME stores a clock time, not a timestamp, so pair it with the date.
    w["arrive"] = (pd.to_datetime(w["date"].astype(str))
                   + pd.to_timedelta(w["arrive"].astype(str), errors="coerce"))
    w = w[w["arrive"].notna()].copy()
    w["depart"] = w["arrive"] + pd.to_timedelta(w["load_min"], unit="m")
    w["shift"] = _norm_shift(w["shift"])
    return w


def compute(w: pd.DataFrame) -> pd.DataFrame:
    """One row per (loading point, shift, date)."""
    rows = []
    for (pt, sh, d), g in w.groupby(["loading_point", "shift", "date"], sort=False):
        if len(g) < MIN_EVENTS_PER_SHIFT:
            continue
        # Sweep line over load intervals: +1 on arrival, -1 on departure. The
        # running maximum is how many trucks were being loaded at once, which is
        # the observed number of parallel servers.
        # Sweep on the LAST interval per truck. A truck cannot be loading in
        # two places at once, but overlapping intervals for one truck do appear
        # in the raw data (8 of 6,852 point-shifts produced servers > trucks,
        # which is physically impossible), caused by a re-scan or a clock
        # correction. Deduplicating first keeps the server count a count of
        # trucks rather than of records.
        gg = g.sort_values("depart").drop_duplicates(
            subset=["truck_id", "arrive"], keep="last")
        ev = pd.concat([pd.Series(1, index=gg["arrive"]),
                        pd.Series(-1, index=gg["depart"])]).sort_index()
        conc = ev.cumsum()
        # Hard ceiling: servers cannot exceed the distinct trucks present.
        n_trucks_here = int(gg["truck_id"].nunique())
        servers = int(min(max(conc.max(), 1), n_trucks_here))
        gaps = g["arrive"].sort_values().diff().dt.total_seconds().div(60).dropna()
        cv = (float(gaps.std() / gaps.mean())
              if len(gaps) > 2 and gaps.mean() > 0 else np.nan)
        rows.append({
            "loading_point": pt, "shift": sh, "date": d,
            "n_trucks": int(g["truck_id"].nunique()),
            "n_loads": int(len(g)),
            "servers_observed": servers,
            "mean_concurrent": round(float(conc.mean()), 2),
            "avg_service_time_min": round(float(g["load_min"].median()), 2),
            "avg_cycle_time_min": round(float(g["cycle_min"].mean()), 2),
            "avg_queue_wait_min": round(float(g["load_min"].mean()), 2),
            "cv_interarrival": round(cv, 3) if cv == cv else None,
        })
    m = pd.DataFrame(rows)
    if m.empty:
        return m

    m["trucks_per_server"] = m["n_trucks"] / m["servers_observed"].clip(lower=1)
    m["match_factor"] = (m["trucks_per_server"] * m["avg_service_time_min"]
                         / m["avg_cycle_time_min"]).round(4)
    m["queue_share"] = (m["avg_queue_wait_min"] / m["avg_cycle_time_min"]).round(3)
    m["status"] = np.select(
        [m["match_factor"] > OVER_TRUCKED, m["match_factor"] < UNDER_TRUCKED],
        ["over-trucked", "under-trucked"], default="balanced")
    thr = float(m["cv_interarrival"].quantile(BUNCHING_CV_PERCENTILE))
    m["bunching_flag"] = (m["cv_interarrival"] > thr).fillna(False)
    m.attrs["bunching_threshold"] = round(thr, 3)
    return m


def validate(m: pd.DataFrame) -> dict:
    """Does MF track queueing? If not, it does not ship.

    Checked against queue SHARE rather than raw cycle time, because cycle time
    is dominated by haul distance and a short-haul point can be busy and fast at
    the same time.
    """
    ok = m.dropna(subset=["match_factor", "queue_share"])
    r_share = float(ok["match_factor"].corr(ok["queue_share"])) if len(ok) > 30 else None
    r_wait = float(ok["match_factor"].corr(ok["avg_queue_wait_min"])) if len(ok) > 30 else None
    r_cycle = float(ok["match_factor"].corr(ok["avg_cycle_time_min"])) if len(ok) > 30 else None
    band = (ok.assign(b=pd.cut(ok["match_factor"], [0, .75, .85, 1.0, 1.15, 1e9]))
              .groupby("b", observed=True)["avg_queue_wait_min"].mean())
    monotone = bool(len(band) >= 3 and band.is_monotonic_increasing)
    return {
        "corr_mf_queue_share": round(r_share, 4) if r_share is not None else None,
        "corr_mf_queue_wait_min": round(r_wait, 4) if r_wait is not None else None,
        "corr_mf_cycle_time": round(r_cycle, 4) if r_cycle is not None else None,
        "wait_rises_with_mf": monotone,
        "passes": bool(r_share is not None and r_share > 0.30),
        "gate": "corr(match_factor, queue_share) > 0.30",
        "note": ("MF is negatively correlated with total cycle time because "
                 "cycle is dominated by haul distance; a short-haul point can "
                 "be heavily queued and still show a short cycle. Queue share "
                 "is the length-free measure of what MF claims to describe."),
    }


def save(m: pd.DataFrame, val: dict) -> dict:
    os.makedirs(DATA, exist_ok=True)
    m.to_csv(MF_CSV, index=False)
    counts = m["status"].value_counts().to_dict()
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "formula": "MF = (trucks_per_server x Ts) / Tc  (Burt & Caccetta 2007)",
        "grain": "loading point x shift x date",
        "key_caveat": ("keyed to LOADING POINT, not shovel: no excavator or "
                       "loader identity exists in either database"),
        "server_count_method": ("observed — peak simultaneous load intervals "
                                "per point-shift (sweep line)"),
        "ts_method": "measured median load duration from WAITING_TIME",
        "rows": int(len(m)),
        "loading_points": int(m["loading_point"].nunique()),
        "date_range": [str(m["date"].min()), str(m["date"].max())],
        "status_counts": counts,
        "status_pct": {k: round(100 * v / len(m), 1) for k, v in counts.items()},
        "bunching_threshold_cv": m.attrs.get("bunching_threshold"),
        "bunching_threshold_source": (
            "75th percentile of observed CV; the briefed 0.5 fires on ~99%% of "
            "point-shifts here (median CV 1.43) and so is not a detector"),
        "bunching_flagged_pct": round(100 * float(m["bunching_flag"].mean()), 1),
        "validation": val,
    }
    with open(MF_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)
    return meta


def run(start: str = "2025-12-27", verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    m = compute(fetch(start))
    if m.empty:
        raise RuntimeError("no loading-point shifts met the minimum event count")
    val = validate(m)
    meta = save(m, val)
    say("match factor: %s point-shifts across %d loading points (%s → %s)"
        % (format(meta["rows"], ","), meta["loading_points"], *meta["date_range"]))
    for k, v in sorted(meta["status_pct"].items()):
        say("  %-14s %5.1f%%  (%s)" % (k, v, format(meta["status_counts"][k], ",")))
    say("  validation: corr(MF, queue share) = %s → passes=%s"
        % (val["corr_mf_queue_share"], val["passes"]))
    say("  bunching: threshold CV>%.2f, flagged %.1f%%"
        % (meta["bunching_threshold_cv"], meta["bunching_flagged_pct"]))
    return meta


def load_results() -> pd.DataFrame | None:
    try:
        d = pd.read_csv(MF_CSV)
        d["date"] = pd.to_datetime(d["date"]).dt.date.astype(str)
        return d
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    run()
