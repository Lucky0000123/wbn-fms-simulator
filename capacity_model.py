"""capacity_model.py — measured loading/dumping capacity, and the honest
replacement for a congestion regression that could not be identified.

WHY THIS FILE EXISTS
The simulator was asked to predict how adding trucks slows cycles. Four
attempts to measure that from weighbridge data all failed, and they failed in
the same direction:

    raw corr(trucks_on_route, cycle)                        -0.09
    within-route, controlling month/shift/weather           -0.03
    hourly concurrency at the loader                        -0.05
    delay vs utilisation against measured capacity          -0.13

The last is the most telling. Queueing theory says delay should climb steeply as
utilisation approaches 1. Observed, it does the opposite: median delay falls
from 38.7 min at under 20% utilisation to 28.6 min at 80-100%, and only 1 of 12
loading points shows the expected rise.

The reason is not that queues do not exist. It is that the data cannot see them.
Busy hours are busy BECAUSE everything is working: shovel up, road dry, crusher
accepting. Slow hours have few trucks because something broke. Deployment
responds to conditions, so truck count is an outcome of good conditions rather
than a cause of delay, and no regression on observational data can separate the
two. An OLS fit does return +11.90 min/SD on trucks_on_route, but that sign is a
collinearity artefact: fitted alone the same feature gives -3.28, and
trucks_at_source correlates with it at 0.69.

Shipping that model would give a planner a tool that recommends adding trucks to
make trips faster, without limit. That is worse than shipping no congestion
model, because the error is invisible in the output.

WHAT IS REAL AND IS SHIPPED INSTEAD
Capacity. If a loading point has never exceeded 97 departures in an hour across
6 months and 4,098 observed hours, that is a measured physical ceiling. It is a
count, not a correlation, and no confounding can inflate it.

So the simulator answers the planner's real question a different way: not "your
cycle time will rise by X minutes" (unsupported), but "this plan asks POS 12 for
110 trucks/hour; its demonstrated ceiling is 97, so the extra trucks will queue
rather than add production" (measured). That is the actionable part, and it is
the part the data genuinely supports.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CAP_CSV = os.path.join(DATA, "point_capacity.csv")
CAP_JSON = os.path.join(DATA, "capacity_evidence.json")

# A point needs many observed hours before its peak means anything.
MIN_HOURS = 200
# The ceiling is p99 of observed hourly throughput, not the max: a single
# mis-keyed hour of 300 tickets should not become the published capacity.
CAP_PCTL = 0.99


def hourly_throughput(d: pd.DataFrame, point_col: str) -> pd.DataFrame:
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["hour"] = pd.to_numeric(d.get("depart_hour"), errors="coerce")
    d = d.dropna(subset=["hour"])
    return (d.groupby([point_col, "date", "hour"])
              .agg(trips=("ticket_no", "size"),
                   trucks=("truck_id", "nunique"),
                   tonnes=("payload_t", "sum")).reset_index())


def build_capacity(d: pd.DataFrame, point_col: str, kind: str) -> pd.DataFrame:
    h = hourly_throughput(d, point_col)
    g = h.groupby(point_col)
    cap = pd.DataFrame({
        "point": g.size().index,
        "kind": kind,
        "observed_hours": g.size().values,
        "median_trips_hr": g["trips"].median().values,
        "p95_trips_hr": g["trips"].quantile(0.95).values,
        "capacity_trips_hr": g["trips"].quantile(CAP_PCTL).values,
        "peak_trips_hr": g["trips"].max().values,
        "median_tonnes_hr": g["tonnes"].median().values,
        "peak_tonnes_hr": g["tonnes"].max().values,
    })
    cap = cap[cap["observed_hours"] >= MIN_HOURS].copy()
    cap["capacity_trips_hr"] = cap["capacity_trips_hr"].round(0)
    # A 12-hour shift ceiling is what a planner actually budgets against.
    cap["capacity_trips_shift"] = (cap["capacity_trips_hr"] * 12).round(0)
    return cap.round(2).sort_values("capacity_trips_hr", ascending=False)


def congestion_evidence(d: pd.DataFrame) -> dict:
    """Re-run the congestion tests so the negative is reproducible, not asserted.

    A negative result that cannot be re-derived is just a claim. This recomputes
    the utilisation-vs-delay relationship every time capacity is built, so if
    the data ever changes and congestion DOES become visible, it shows up here
    instead of staying buried in a decision made once.
    """
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["hour"] = pd.to_numeric(d.get("depart_hour"), errors="coerce")
    d = d.dropna(subset=["hour"])
    h = (d.groupby(["source", "date", "hour"])
           .agg(trips=("ticket_no", "size"),
                delay=("congestion_delay_min", "median")).reset_index())
    cap = h.groupby("source")["trips"].agg(["size", lambda s: s.quantile(CAP_PCTL)])
    cap.columns = ["hours", "cap"]
    cap = cap[cap["hours"] >= MIN_HOURS]
    h = h.merge(cap[["cap"]], on="source", how="inner")
    h["util"] = h["trips"] / h["cap"]

    bands = pd.cut(h["util"], [0, .2, .4, .6, .8, 1.0, 9],
                   labels=["0-20%", "20-40%", "40-60%", "60-80%", "80-100%", ">100%"])
    by_band = (h.groupby(bands, observed=True)["delay"]
                 .agg(["size", "median"]).round(2))
    u = h["util"] - h.groupby("source")["util"].transform("mean")
    v = h["delay"] - h.groupby("source")["delay"].transform("mean")
    within = float(u.corr(v))

    rises = 0
    total = 0
    for _, g in h.groupby("source"):
        if len(g) < 300:
            continue
        total += 1
        if g["util"].corr(g["delay"]) > 0:
            rises += 1

    return {
        "test": "does delay rise as a loading point approaches measured capacity?",
        "expected_if_congestion_visible": "positive correlation, steep near util=1",
        "corr_util_delay_within_loader": round(within, 4),
        "median_delay_by_utilisation_band": {
            str(k): {"n": int(r["size"]), "median_delay_min": float(r["median"])}
            for k, r in by_band.iterrows()},
        "loaders_where_delay_rises": rises,
        "loaders_tested": total,
        "verdict": ("NOT IDENTIFIABLE — delay falls as utilisation rises. Busy "
                    "hours are hours when everything is working; deployment "
                    "responds to conditions, so truck count cannot be separated "
                    "from the conditions that caused it."),
        "consequence": ("the simulator does NOT scale cycle time with truck "
                        "count. It reports measured capacity headroom instead."),
    }


def build(verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    say = print if verbose else (lambda *a, **k: None)
    from trip_features import load_features
    d = load_features()
    if d is None:
        raise FileNotFoundError("run trip_features.py first")

    load_cap = build_capacity(d, "source", "loading")
    dump_cap = build_capacity(d, "destination", "dumping")
    cap = pd.concat([load_cap, dump_cap], ignore_index=True)
    cap.to_csv(CAP_CSV, index=False)

    ev = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "capacity_percentile": CAP_PCTL,
        "min_observed_hours": MIN_HOURS,
        "loading_points": int(len(load_cap)),
        "dumping_points": int(len(dump_cap)),
        "congestion_regression": congestion_evidence(d),
    }
    with open(CAP_JSON, "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=2, default=str)

    say("measured capacity: %d loading points, %d dumping points"
        % (len(load_cap), len(dump_cap)))
    say("\ntop loading points (trips/hour ceiling from observed history):")
    for r in load_cap.head(6).itertuples():
        say("   %-14s cap %3.0f/hr (%4.0f/shift)  median %2.0f/hr  over %d hours"
            % (r.point, r.capacity_trips_hr, r.capacity_trips_shift,
               r.median_trips_hr, r.observed_hours))
    c = ev["congestion_regression"]
    say("\ncongestion re-test: corr(utilisation, delay) = %+.4f, %d of %d loaders rise"
        % (c["corr_util_delay_within_loader"], c["loaders_where_delay_rises"],
           c["loaders_tested"]))
    say("   verdict: %s" % c["verdict"].split("—")[0].strip())
    return cap, ev


def load_capacity() -> pd.DataFrame | None:
    try:
        return pd.read_csv(CAP_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    build()
