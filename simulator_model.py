"""simulator_model.py — Task 2: route-level cycle-time prediction.

WHAT THIS MODEL IS FOR
The simulator has to answer "if I run N trucks on this route, how long is a
trip?". So the model predicts cycle time from the plan variables a planner can
actually set: the route, how many trucks are on it, how many are contending for
the same loading and dumping points, the shift, and the weather.

THE HONEST QUESTION THIS FILE ANSWERS
Does truck count carry congestion signal, or not? Three models are trained on
identical walk-forward folds so the comparison is fair:

    route_mean        the baseline: this route's historical mean, nothing else
    ols               linear, one-hot categoricals
    hgb               HistGradientBoosting, can find non-linearities

and each is fitted twice, once WITH the congestion features and once WITHOUT.

THE ANSWER, AND WHY THE CONGESTION FEATURES ARE NOT SERVED
Adding them raises walk-forward R2 slightly (OLS 0.4647 -> 0.4925). That looked
like success and is not, because the improvement comes with a coefficient whose
sign is wrong in a way that matters:

    trucks_at_source   -22.7 min/SD   more trucks at the loader = FASTER
    trucks_on_route    +11.9 min/SD   but fitted ALONE this is -3.28

The pair is collinear at r=0.69, so OLS splits them into a large +/- couple that
predicts adequately and means nothing individually. Independently, delay was
tested against measured loader utilisation and FALLS as utilisation rises
(see capacity_model.py). Deployment is endogenous: trucks are sent where things
are working, so truck count is a marker of good conditions, not a cause of delay.

A simulator exists to answer "should I add trucks". Serving a model that says
adding trucks makes trips faster would produce confident, unbounded, wrong
advice — worse than a lower R2, because the error is invisible in the output.
So the congestion comparison is still RUN and REPORTED here, for evidence, but
the served model uses plan-controllable features only, and the truck-count
question is answered by measured capacity headroom instead.

WHY WALK-FORWARD AND NOT RANDOM SPLITS
A random split lets the model see next month while predicting this month. Mine
conditions drift with the wet season and the pit advances, so a random split
would report a score the simulator can never reproduce in use. Folds are strictly
forward in time: train on the past, test on the future.

WHY SHIFT-LEVEL AGGREGATION
Trip rows repeat the same truck count hundreds of times per shift. Fitting on
them makes n look enormous while the congestion variable has only a few thousand
genuinely independent values, which flatters every standard error. The model is
therefore fitted on route-date-shift medians, which is also the granularity a
planner actually plans at.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RESULTS_JSON = os.path.join(DATA, "simulator_model_results.json")
LOOKUP_CSV = os.path.join(DATA, "route_lookup.csv")

N_FOLDS = 5
MIN_TRIPS_PER_SHIFT = 5     # a shift with 2 trips has a meaningless median
MIN_SHIFTS_PER_ROUTE = 20   # a route needs history to be predictable at all

CONGESTION = ["trucks_on_route", "trucks_at_source", "trucks_at_dest",
              "shared_source", "shared_dest"]
BASE_NUM = ["rainfall_mm", "is_weekend"]
BASE_CAT = ["route", "shift", "day_of_week", "contractor"]


def build_shift_panel(d: pd.DataFrame) -> pd.DataFrame:
    """Collapse trips to one row per route-date-shift.

    The median, not the mean: cycle times have a long right tail from trucks
    that parked or broke down mid-trip, and a mean would track those rather
    than the typical trip a planner is asking about.
    """
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    g = d.groupby(["route", "date", "shift"], observed=True)
    p = g.agg(
        cycle_time_min=("cycle_time_min", "median"),
        load_time_min=("load_time_min", "median"),
        dump_time_min=("dump_time_est_min", "median"),
        congestion_delay_min=("congestion_delay_min", "median"),
        route_floor_min=("route_floor_min", "first"),
        trucks_on_route=("trucks_on_route", "first"),
        trucks_at_source=("trucks_at_source", "first"),
        trucks_at_dest=("trucks_at_dest", "first"),
        shared_source=("shared_source", "first"),
        shared_dest=("shared_dest", "first"),
        source=("source", "first"),
        destination=("destination", "first"),
        payload_t=("payload_t", "median"),
        rainfall_mm=("rainfall_mm", "first"),
        is_weekend=("is_weekend", "first"),
        day_of_week=("day_of_week", "first"),
        contractor=("contractor", "first"),
        n_trips=("cycle_time_min", "size"),
    ).reset_index()
    p = p[p["n_trips"] >= MIN_TRIPS_PER_SHIFT]
    keep = p.groupby("route")["route"].transform("size") >= MIN_SHIFTS_PER_ROUTE
    p = p[keep].sort_values("date").reset_index(drop=True)
    for c in ("rainfall_mm", "payload_t"):
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(p[c].median())
    return p


def _design(tr: pd.DataFrame, te: pd.DataFrame, feats: list[str]):
    """One-hot the categoricals on the TRAINING fold only.

    Fitting the encoding on train+test would leak future category frequencies
    into the past. Unseen test categories become all-zero rows, which is the
    correct behaviour for a route the model has never been trained on.
    """
    cats = [c for c in feats if c in BASE_CAT]
    nums = [c for c in feats if c not in BASE_CAT]
    Xtr = pd.get_dummies(tr[cats].astype(str), columns=cats) if cats else pd.DataFrame(index=tr.index)
    Xte = pd.get_dummies(te[cats].astype(str), columns=cats) if cats else pd.DataFrame(index=te.index)
    Xte = Xte.reindex(columns=Xtr.columns, fill_value=0)
    for n in nums:
        Xtr[n] = pd.to_numeric(tr[n], errors="coerce").fillna(0).values
        Xte[n] = pd.to_numeric(te[n], errors="coerce").fillna(0).values
    return Xtr.astype(float).values, Xte.astype(float).values


def _metrics(y, yhat) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else float("nan"),
        "mae": round(float(np.abs(y - yhat).mean()), 2),
        "rmse": round(float(np.sqrt(((y - yhat) ** 2).mean())), 2),
        "n": int(len(y)),
    }


def walk_forward(p: pd.DataFrame, target: str, feats: list[str],
                 model: str, n_folds: int = N_FOLDS) -> dict:
    """Train on the past, test on the next block, repeatedly."""
    dates = np.array(sorted(p["date"].unique()))
    if len(dates) < n_folds + 1:
        return {"error": "not enough distinct dates"}
    bounds = np.array_split(dates, n_folds + 1)
    ys, yh = [], []
    for k in range(n_folds):
        cut = bounds[k][-1]
        tr = p[p["date"] <= cut]
        te = p[(p["date"] > cut) & (p["date"] <= bounds[k + 1][-1])]
        if len(tr) < 50 or te.empty:
            continue
        ytr = tr[target].values
        if model == "route_mean":
            m = tr.groupby("route")[target].mean()
            pred = te["route"].map(m).fillna(ytr.mean()).values
        elif model == "ols":
            Xtr, Xte = _design(tr, te, feats)
            Xtr = np.hstack([np.ones((len(Xtr), 1)), Xtr])
            Xte = np.hstack([np.ones((len(Xte), 1)), Xte])
            beta, *_ = np.linalg.lstsq(Xtr, ytr, rcond=None)
            pred = Xte @ beta
        elif model == "hgb":
            from sklearn.ensemble import HistGradientBoostingRegressor
            Xtr, Xte = _design(tr, te, feats)
            g = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06,
                                              max_depth=6, random_state=0)
            g.fit(Xtr, ytr)
            pred = g.predict(Xte)
        else:
            raise ValueError(model)
        # A negative predicted duration is physically impossible; clip rather
        # than let it flatter the error metric.
        ys.append(te[target].values)
        yh.append(np.clip(pred, 1.0, None))
    if not ys:
        return {"error": "no usable folds"}
    return _metrics(np.concatenate(ys), np.concatenate(yh))


def audit_congestion_signs(p: pd.DataFrame, n_boot: int = 300) -> dict:
    """Check the DIRECTION the fit attributes to truck count, not just its fit.

    This is the guard that stopped a higher-R2 model from being served. R2 says
    how well predictions track reality on historical data; it says nothing about
    whether the model would give correct ADVICE when a planner changes a truck
    count. Only the coefficient sign does that.

    Each feature is fitted twice: jointly (as a model would use it) and alone
    (with the collinearity removed). When the two disagree in sign, the joint
    coefficient is an artefact of correlated regressors and must not be
    interpreted as a causal effect of adding trucks.
    """
    cats, out = BASE_CAT, {}

    def _fit(extra: list[str]) -> dict:
        X = pd.get_dummies(p[cats].astype(str), columns=cats)
        for n in BASE_NUM + extra:
            v = pd.to_numeric(p[n], errors="coerce").fillna(0).astype(float)
            sd = v.std()
            X[n] = (v - v.mean()) / (sd if sd else 1.0)      # per-SD, comparable
        Xv = np.hstack([np.ones((len(X), 1)), X.astype(float).values])
        b, *_ = np.linalg.lstsq(Xv, p["cycle_time_min"].values, rcond=None)
        return dict(zip(["intercept"] + list(X.columns), b))

    numeric_cong = [c for c in CONGESTION if p[c].nunique() > 2]
    joint = _fit(numeric_cong)
    rng = np.random.default_rng(0)
    X = pd.get_dummies(p[cats].astype(str), columns=cats)
    for n in BASE_NUM + numeric_cong:
        v = pd.to_numeric(p[n], errors="coerce").fillna(0).astype(float)
        sd = v.std()
        X[n] = (v - v.mean()) / (sd if sd else 1.0)
    Xv = np.hstack([np.ones((len(X), 1)), X.astype(float).values])
    y = p["cycle_time_min"].values
    names = ["intercept"] + list(X.columns)
    draws: dict[str, list] = {c: [] for c in numeric_cong}
    for _ in range(n_boot):
        s = rng.integers(0, len(y), len(y))
        try:
            b, *_ = np.linalg.lstsq(Xv[s], y[s], rcond=None)
        except np.linalg.LinAlgError:
            continue
        for c in numeric_cong:
            draws[c].append(b[names.index(c)])

    for c in numeric_cong:
        alone = _fit([c])[c]
        a = np.array(draws[c])
        lo, hi = (np.percentile(a, [2.5, 97.5]) if len(a) else (np.nan, np.nan))
        flips = bool(np.sign(alone) != np.sign(joint[c]))
        out[c] = {
            "coef_joint_min_per_sd": round(float(joint[c]), 2),
            "coef_alone_min_per_sd": round(float(alone), 2),
            "boot_ci95": [round(float(lo), 2), round(float(hi), 2)],
            "sign_flips_when_isolated": flips,
            "usable_as_causal": bool((not flips) and lo > 0),
            "note": ("sign reverses once collinearity is removed — joint "
                     "coefficient is an artefact" if flips else
                     "negative: more trucks associated with faster trips, "
                     "which contradicts queueing and indicates endogenous "
                     "deployment" if hi < 0 else "not distinguishable from zero"),
        }
    out["_conclusion"] = (
        "no congestion feature is usable as a causal lever"
        if not any(v.get("usable_as_causal") for v in out.values()
                   if isinstance(v, dict))
        else "at least one congestion feature is directionally sound")
    return out


def run(verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    from trip_features import load_features
    d = load_features()
    if d is None:
        raise FileNotFoundError("run trip_features.py first")
    p = build_shift_panel(d)
    say("shift panel: %s rows, %d routes (%s → %s)"
        % (format(len(p), ","), p["route"].nunique(),
           str(p["date"].min())[:10], str(p["date"].max())[:10]))

    without = BASE_CAT + BASE_NUM
    with_cong = without + CONGESTION
    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "panel_rows": int(len(p)), "routes": int(p["route"].nunique()),
        "n_folds": N_FOLDS, "target": "cycle_time_min", "models": {},
    }

    say("\n%-14s %-12s %8s %8s %8s" % ("model", "features", "R2", "MAE", "RMSE"))
    say("-" * 56)
    for name in ("route_mean", "ols", "hgb"):
        for tag, feats in (("without_cong", without), ("with_cong", with_cong)):
            if name == "route_mean" and tag == "with_cong":
                continue          # the baseline ignores features by definition
            m = walk_forward(p, "cycle_time_min", feats, name)
            out["models"]["%s__%s" % (name, tag)] = m
            if "error" not in m:
                say("%-14s %-12s %8.4f %8.2f %8.2f"
                    % (name, tag, m["r2"], m["mae"], m["rmse"]))

    # The verdict: does adding congestion features help, on the same folds?
    verdict = {}
    for name in ("ols", "hgb"):
        a = out["models"].get("%s__without_cong" % name, {})
        b = out["models"].get("%s__with_cong" % name, {})
        if "r2" in a and "r2" in b:
            verdict[name] = {
                "r2_without": a["r2"], "r2_with": b["r2"],
                "delta_r2": round(b["r2"] - a["r2"], 4),
                "delta_mae": round(b["mae"] - a["mae"], 2),
            }
    out["congestion_verdict"] = verdict

    # The sign audit decides what is SERVED. A model can win on R2 and still be
    # unusable as a planning tool if it points the wrong way on the one lever a
    # planner actually pulls.
    audit = audit_congestion_signs(p)
    out["congestion_sign_audit"] = audit
    congestion_usable = any(v.get("usable_as_causal") for v in audit.values()
                            if isinstance(v, dict))

    say("\ncongestion feature contribution (same folds, like for like):")
    for k, v in verdict.items():
        say("   %-5s R2 %.4f -> %.4f  (delta %+.4f, MAE %+.2f min)"
            % (k, v["r2_without"], v["r2_with"], v["delta_r2"], v["delta_mae"]))

    say("\nsign audit — is truck count usable as a causal lever?")
    for k, v in audit.items():
        if not isinstance(v, dict):
            continue
        say("   %-18s joint %+7.2f | alone %+7.2f | CI [%+.2f,%+.2f] %s"
            % (k, v["coef_joint_min_per_sd"], v["coef_alone_min_per_sd"],
               v["boot_ci95"][0], v["boot_ci95"][1],
               "OK" if v["usable_as_causal"] else "REJECTED"))
    say("   -> %s" % audit["_conclusion"])

    # Serve the best model among those that are directionally defensible.
    eligible = {k: v for k, v in out["models"].items()
                if "r2" in v and (congestion_usable or not k.endswith("with_cong"))}
    best = max(eligible, key=lambda k: eligible[k]["r2"])
    out["best_model"] = best
    out["best_r2"] = out["models"][best]["r2"]
    out["served_model"] = best
    out["congestion_features_served"] = bool(congestion_usable)
    top_overall = max((k for k, v in out["models"].items() if "r2" in v),
                      key=lambda k: out["models"][k]["r2"])
    if top_overall != best:
        out["withheld_higher_r2_model"] = {
            "model": top_overall, "r2": out["models"][top_overall]["r2"],
            "reason": ("higher R2 but rejected by the sign audit: it would tell "
                       "a planner that adding trucks speeds trips up"),
        }
        say("\nWITHHELD: %s scores R2=%.4f but fails the sign audit."
            % (top_overall, out["models"][top_overall]["r2"]))
    say("serving: %s  R2=%.4f" % (best, out["best_r2"]))

    # The route lookup is the fallback the simulator falls back to, and it is
    # written whatever the verdict, because a baseline that works beats a
    # congestion model that does not.
    lk = (p.groupby("route")
            .agg(mean_cycle_min=("cycle_time_min", "mean"),
                 median_cycle_min=("cycle_time_min", "median"),
                 p10_cycle_min=("cycle_time_min", lambda s: s.quantile(.10)),
                 p90_cycle_min=("cycle_time_min", lambda s: s.quantile(.90)),
                 median_load_min=("load_time_min", "median"),
                 median_dump_min=("dump_time_min", "median"),
                 median_payload_t=("payload_t", "median"),
                 median_trucks=("trucks_on_route", "median"),
                 source=("source", "first"), destination=("destination", "first"),
                 shifts=("cycle_time_min", "size"))
            .round(3).reset_index())
    lk.to_csv(LOOKUP_CSV, index=False)
    out["route_lookup_rows"] = int(len(lk))

    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    say("wrote %s and %s" % (os.path.basename(RESULTS_JSON),
                             os.path.basename(LOOKUP_CSV)))
    return out


if __name__ == "__main__":
    run()
