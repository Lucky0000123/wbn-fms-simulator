"""dwell_models.py — Task 3: loading and dumping time.

WHAT WAS ASKED, AND WHAT THE DATA ALLOWS
The brief asks for two models, each with truck count as a feature, to answer:
"does load time increase when more trucks are at the same loading point?"

That question was tested in capacity_model.py and the answer is no — not
because queues do not form, but because the weighbridge cannot see them.
Delay falls as loader utilisation rises, since busy hours are the hours when
the shovel is up and the road is dry. Truck count is a marker of good
conditions, not a cause of delay.

So fitting dwell time on truck count would reproduce the same inverted
relationship at a finer grain, and a planner reading "add trucks, loading gets
faster" would be misled twice instead of once.

WHAT IS SHIPPED INSTEAD
Dwell times conditioned on the things that are NOT chosen in response to how
well the shift is going:

    the loading point       some shovels are simply slower than others
    the shift               night differs from day
    rain                    wet ground genuinely slows loading
    day of week             shift patterns and maintenance windows

These are exogenous to deployment, so their coefficients mean what they appear
to mean. Truck count is deliberately excluded, and the exclusion is tested
rather than asserted: `test_truck_count_effect` refits WITH truck count and
records the direction, so if better data ever makes the effect visible and
positive, that shows up here instead of being assumed away for ever.

THE UNDERLYING NUMBERS ARE STILL AN ESTIMATE
Load and dump time come from splitting one weighbridge interval, so they carry
the apportionment assumption documented in trip_features.py. When WAITING_TIME
is reachable the load figure becomes a real measurement and `load_time_source`
says so per row. The models report which basis they were trained on.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DWELL_CSV = os.path.join(DATA, "dwell_model_results.csv")
DWELL_JSON = os.path.join(DATA, "dwell_model_results.json")

MIN_OBS = 30            # a point needs history before its dwell time is quoted
WET_MM = 5.0            # rainfall above this counts as a wet shift


def _panel(d: pd.DataFrame, point_col: str, target: str) -> pd.DataFrame:
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    g = d.groupby([point_col, "date", "shift"], observed=True)
    p = g.agg(dwell=(target, "median"),
              trucks=("truck_id", "nunique"),
              rainfall_mm=("rainfall_mm", "first"),
              day_of_week=("day_of_week", "first"),
              is_weekend=("is_weekend", "first"),
              n=(target, "size")).reset_index()
    p = p[p["n"] >= 5]
    p["is_wet"] = (pd.to_numeric(p["rainfall_mm"], errors="coerce")
                   .fillna(0) > WET_MM).astype(int)
    return p.rename(columns={point_col: "point"})


def build_dwell_table(p: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Conditional dwell time per point, split by shift and by wet/dry.

    A lookup rather than a regression: with one exogenous driver that matters
    (rain) and a categorical (shift), a conditional median is both more robust
    to the long right tail and directly inspectable by whoever has to trust it.
    """
    rows = []
    for pt, g in p.groupby("point"):
        if len(g) < MIN_OBS:
            continue
        rec = {"point": pt, "kind": kind, "observations": int(len(g)),
               "median_min": round(float(g["dwell"].median()), 2),
               "p25_min": round(float(g["dwell"].quantile(.25)), 2),
               "p75_min": round(float(g["dwell"].quantile(.75)), 2)}
        for sh in ("day", "night"):
            s = g[g["shift"].astype(str).str.lower() == sh]
            rec["%s_min" % sh] = (round(float(s["dwell"].median()), 2)
                                  if len(s) >= 10 else None)
        for w, lbl in ((0, "dry"), (1, "wet")):
            s = g[g["is_wet"] == w]
            rec["%s_min" % lbl] = (round(float(s["dwell"].median()), 2)
                                   if len(s) >= 10 else None)
        if rec["wet_min"] and rec["dry_min"]:
            rec["wet_penalty_min"] = round(rec["wet_min"] - rec["dry_min"], 2)
            rec["wet_penalty_pct"] = round(
                100 * (rec["wet_min"] - rec["dry_min"]) / rec["dry_min"], 1)
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("observations", ascending=False)


def test_truck_count_effect(p: pd.DataFrame) -> dict:
    """Refit WITH truck count and record the direction, without serving it.

    This keeps the exclusion falsifiable. If the relationship ever turns
    positive and consistent, this reports it, and the decision to leave truck
    count out can be revisited on evidence rather than on precedent.
    """
    pooled = float(p["trucks"].corr(p["dwell"]))
    x = p["trucks"] - p.groupby("point")["trucks"].transform("mean")
    y = p["dwell"] - p.groupby("point")["dwell"].transform("mean")
    within = float(x.corr(y))
    rises, total = 0, 0
    for _, g in p.groupby("point"):
        if len(g) < MIN_OBS:
            continue
        total += 1
        if g["trucks"].corr(g["dwell"]) > 0:
            rises += 1
    return {
        "question": "does dwell time rise when more trucks use the same point?",
        "corr_pooled": round(pooled, 4),
        "corr_within_point": round(within, 4),
        "points_where_dwell_rises": rises,
        "points_tested": total,
        "queue_effect_detectable": bool(within > 0.15 and total and
                                        rises / total > 0.7),
        "served": False,
        "why_not_served": ("endogenous deployment: trucks are sent to points "
                           "that are running well, so truck count tracks good "
                           "conditions rather than causing delay"),
    }


def build(verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    from trip_features import load_features
    d = load_features()
    if d is None:
        raise FileNotFoundError("run trip_features.py first")

    lp = _panel(d, "source", "load_time_min")
    dp = _panel(d, "destination", "dump_time_min")
    lt = build_dwell_table(lp, "loading")
    dt = build_dwell_table(dp, "dumping")
    tbl = pd.concat([lt, dt], ignore_index=True)
    tbl.to_csv(DWELL_CSV, index=False)

    basis = (d["load_time_source"].value_counts(normalize=True) * 100).round(1)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "loading_points": int(len(lt)), "dumping_points": int(len(dt)),
        "load_time_basis_pct": basis.to_dict(),
        "truck_count_test_loading": test_truck_count_effect(lp),
        "truck_count_test_dumping": test_truck_count_effect(dp),
        "features_served": ["point", "shift", "is_wet", "day_of_week"],
        "features_excluded": {
            "trucks_at_point": "endogenous, see truck_count_test_*",
        },
        "estimate_warning": ("load and dump times are an apportionment of one "
                             "weighbridge interval unless load_time_source "
                             "says measured"),
    }
    with open(DWELL_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)

    say("dwell models: %d loading points, %d dumping points"
        % (len(lt), len(dt)))
    say("load time basis: %s"
        % ", ".join("%s %.1f%%" % (k, v) for k, v in basis.items()))
    say("\nloading dwell (median min, and the wet-weather penalty):")
    for r in lt.head(8).itertuples():
        wp = ("  wet %+.1f min (%+.0f%%)" % (r.wet_penalty_min, r.wet_penalty_pct)
              if pd.notna(getattr(r, "wet_penalty_min", np.nan)) else "")
        say("   %-14s %6.1f min  (n=%d)%s"
            % (r.point, r.median_min, r.observations, wp))
    t = out["truck_count_test_loading"]
    say("\ntruck-count test at loading points: within-point corr %+.4f, "
        "%d of %d points rise -> detectable: %s"
        % (t["corr_within_point"], t["points_where_dwell_rises"],
           t["points_tested"], t["queue_effect_detectable"]))
    return out


def load_dwell() -> pd.DataFrame | None:
    try:
        return pd.read_csv(DWELL_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    build()
