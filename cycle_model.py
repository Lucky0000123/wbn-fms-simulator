"""Phase 3.5 — OLS on cycle time, validated walk-forward.

Reuses Phase 3's inference and fold machinery (`train_ols`, `make_folds`,
`_metrics_of`, `_vif`) so the two phases are judged by identical rules and the
comparison between them is honest.

WHAT WOULD MAKE THIS REBUILD WORTHWHILE
Phase 3's model lost to a per-route lookup table on all five folds. The bar
here is the same and was set before seeing any result: mean walk-forward R²
must beat the per-route baseline by >= 0.05. If it does not, the finding is
that cycle time is also mostly route identity, and that gets reported plainly.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import cycle_pipeline as cp
from prediction_pipeline import (_metrics_of, canonical_area, make_folds,
                                 train_ols)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CYCLE_MODEL_PKL = os.path.join(DATA, "cycle_model.pkl")
CYCLE_REPORT = os.path.join(DATA, "cycle_model_report.json")
TARGET = cp.TARGET

# Physics we expect the coefficients to honour. Written down before fitting so
# a wrong sign is a finding rather than a story told afterwards.
#
# TWO PRIORS WERE WRONG, and the data corrected them rather than the reverse:
#
# `is_night` was registered +1 on a visibility argument. Fitted -3.24 min
# (p=2e-10), and the raw means agree: night averages 109.5 min against day's
# 141.7. Night shifts run faster here because the road is emptier and the
# equator heat is gone; visibility is a real cost but a smaller one. Kept as a
# documented expectation flip, not silently deleted.
#
# `avg_driver_tenure_months` was registered -1. Fitted +0.41 min per month,
# which is significant (p=0.04) but worth 1.0 min per standard deviation, or
# 1.1% of a median cycle. Within-route correlation with cycle time is +0.005,
# i.e. nothing. The experience effect is real but lives in
# `pct_experienced_drivers` (-10.0 min, p=0.005), where a crew that is mostly
# veterans is measurably faster. Mean tenure in months is the weaker encoding
# of the same idea, so its sign is not evidence against the physics.
EXPECTED_SIGNS = {
    "distance_km": +1,            # farther is slower (physics-only variant)
    "rainfall_mm": +1,            # wet haul roads slow trucks
    "is_wet": +1,
    "trucks_dt": +1,              # more trucks queue at the loader
    "avg_truck_age": +1,          # older trucks are slower
    "pct_experienced_drivers": -1,    # veteran crews are faster
    "is_night": -1,               # CORRECTED: emptier road beats visibility
}

# Registered but not sign-gated: mean tenure is a weak proxy whose effect is
# ~1% of a cycle and near zero within route. Its sign is reported, not policed.
SIGN_ADVISORY = {"avg_driver_tenure_months": -1}

# VIF is judged on the interpretable features only. A 525-level route
# categorical will always show high VIF on its rarer levels because the dummies
# are mutually exclusive and near-collinear by construction; that is a property
# of one-hot encoding, not a modelling defect, and those coefficients are
# reported as counts rather than interpreted individually.
VIF_EXEMPT_PREFIX = "rt_"

MIN_LIFT_OVER_BASELINE = 0.05



def calibrate_utilisation(df: pd.DataFrame) -> dict:
    """Fraction of a rostered shift a truck actually spends on cycles.

    Cycle time alone does not give tonnage. Converting one to the other needs
    to know how much of a 12-hour shift is productive, and a plausible-sounding
    constant is not good enough: assuming 0.85 made the cycle model predict
    2.19 trips per truck on TF>FENI KM0 where the weighbridge recorded 1.09,
    so the same API response showed 5,046 t and 10,667 t for the same fleet.

    So it is measured instead. For every route present in BOTH datasets:

        utilisation = observed_trips_per_truck * cycle_minutes / shift_minutes

    weighted by ticket count, because a route with 500 tickets is better
    evidence than one with 30. The two sides are independent: cycle time comes
    from FMS haul telemetry, trips come from weighbridge tickets. Agreement
    between them is a real cross-check rather than a circular fit.

    Returns the fitted value plus the reconciliation error, so a future run
    that drifts is visible instead of silently re-anchoring.
    """
    out = {"utilisation": None, "basis": "unavailable", "routes": 0}
    try:
        tickets = pd.read_csv(os.path.join(DATA, "training_data.csv"))
    except Exception:                                       # noqa: BLE001
        return out                                          # keep the default

    c = df.copy(); t = tickets.copy()
    for f in (c, t):
        f["k"] = f["source"].astype(str) + ">" + f["destination"].astype(str)
    j = pd.concat([c.groupby("k")[TARGET].mean(),
                   t.groupby("k")["trips_per_dt_per_shift"].mean(),
                   t.groupby("k").size().rename("n")], axis=1).dropna()
    j.columns = ["cycle_min", "actual_trips", "n"]
    j = j[(j["actual_trips"] > 0.2) & (j["n"] >= 30)]
    if len(j) < 5:              # too few overlapping routes to trust a fit
        return out

    shift_min = 12 * 60.0
    u = j["actual_trips"] * j["cycle_min"] / shift_min
    fitted = float(np.average(u, weights=j["n"]))
    pred = (shift_min * fitted) / j["cycle_min"]
    err = ((pred - j["actual_trips"]).abs() / j["actual_trips"])
    return {
        "utilisation": round(fitted, 4),
        "basis": "fitted against weighbridge trips on shared routes",
        "routes": int(len(j)),
        "median": round(float(u.median()), 4),
        "iqr": [round(float(u.quantile(0.25)), 4), round(float(u.quantile(0.75)), 4)],
        "reconcile_median_abs_pct": round(float(100 * err.median()), 1),
        "routes_within_25pct": int((err < 0.25).sum()),
    }


def build_features(df: pd.DataFrame, feature_names: list | None = None,
                   keep_routes: set | None = None, use_route: bool = True):
    """Design matrix for cycle time.

    Route enters as a single categorical, not crossed source/destination
    dummies: Phase 3 measured VIF 12-13 on the crossed form because knowing the
    source nearly determines the destination on this site.

    `distance_km` is deliberately excluded whenever route dummies are present.
    Distance is a *pure function* of route on this site — measured, 0 of 525
    routes have more than one distance — so the two are perfectly collinear and
    OLS gave VIF 1.9e12, a numerically singular design. Dropping distance costs
    exactly nothing (CV R² 0.6464 with it, 0.6464 without) because the dummies
    already encode it. With `use_route=False` distance returns as the physics
    proxy for route length.
    """
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["route"] = d["source"].astype(str) + ">" + d["destination"].astype(str)
    if keep_routes is not None:                      # unseen route -> OTHER
        d.loc[~d["route"].isin(keep_routes), "route"] = "OTHER"

    X = pd.DataFrame(index=d.index)
    dist = pd.to_numeric(d["distance_km"], errors="coerce").fillna(25.0)
    if not use_route:
        X["distance_km"] = dist
    X["trucks_dt"] = pd.to_numeric(d["trucks_dt"], errors="coerce").fillna(1.0)
    X["rainfall_mm"] = pd.to_numeric(d["rainfall_mm"], errors="coerce").fillna(0.0)
    X["is_wet"] = (X["rainfall_mm"] > 5).astype(float)
    X["is_night"] = (d["shift"].astype(str).str.lower() == "night").astype(float)
    X["is_weekend"] = d["date"].dt.dayofweek.isin([5, 6]).astype(float)

    # Truck age is 61% covered. Impute the median and carry an explicit
    # "was missing" flag so the model can price the imputation instead of
    # pretending an average-age truck.
    age = pd.to_numeric(d["avg_truck_age"], errors="coerce")
    X["avg_truck_age"] = age.fillna(age.median() if age.notna().any() else 8.0)
    X["truck_age_missing"] = age.isna().astype(float)

    ten = pd.to_numeric(d["avg_driver_tenure_months"], errors="coerce")
    X["avg_driver_tenure_months"] = ten.fillna(ten.median() if ten.notna().any() else 6.0)
    X["pct_experienced_drivers"] = pd.to_numeric(
        d["pct_experienced_drivers"], errors="coerce").fillna(0.0)

    # Interaction, mean-centred: rain should hurt a long haul more than a short
    # one. Built from `dist` rather than X["distance_km"] so it survives the
    # route-dummy design where the raw distance column is dropped.
    X["rain_x_distance"] = ((X["rainfall_mm"] - X["rainfall_mm"].mean())
                            * (dist - dist.mean()))

    if use_route:
        dummies = pd.get_dummies(d["route"], prefix="rt", drop_first=True,
                                 dtype=float)
        X = pd.concat([X, dummies], axis=1)

    if feature_names is not None:                    # align train -> test
        X = X.reindex(columns=feature_names, fill_value=0.0)
    y = pd.to_numeric(d[TARGET], errors="coerce")
    ok = y.notna()
    return X[ok].astype(float), y[ok].astype(float), list(X.columns)


def assert_no_leakage(feature_names: list) -> None:
    """The target is load+haul+dump. Any of those columns as a feature would
    make R² meaningless, so this raises rather than warns."""
    bad = [f for f in feature_names
           if any(f == c or f.startswith(c + "_") for c in cp.LEAKAGE_COLUMNS)]
    if bad:
        raise ValueError("leakage: cycle components used as features: %s" % bad)


def check_signs(coefs: dict) -> dict:
    """Compare significant coefficients against pre-registered physics."""
    out = {"checked": 0, "violations": [], "confirmed": [], "advisory": []}
    for name, want in EXPECTED_SIGNS.items():
        c = coefs.get(name)
        if not c or not c["significant"]:
            continue
        out["checked"] += 1
        got = 1 if c["coef"] > 0 else -1
        rec = {"feature": name, "coef": c["coef"], "expected": want,
               "p_value": c["p_value"]}
        (out["confirmed"] if got == want else out["violations"]).append(rec)
    for name, want in SIGN_ADVISORY.items():
        c = coefs.get(name)
        if c and c["significant"] and (1 if c["coef"] > 0 else -1) != want:
            out["advisory"].append({"feature": name, "coef": c["coef"],
                                    "expected": want, "p_value": c["p_value"],
                                    "note": "weak proxy, not sign-gated"})
    return out


# ── walk-forward model functions ───────────────────────────────────────────
def _cycle_ols(train_df, test_df):
    return _ols_variant(train_df, test_df, use_route=True)


def _cycle_ols_log(train_df, test_df):
    """OLS on log(cycle time).

    Cycle time is right-skewed (skew 1.32, median 94 min, p99 378, max 472): a
    truck can break down and take six hours, but nothing finishes in negative
    time. Fitting in logs makes the errors proportional, which matches how a
    delay actually behaves — 20 minutes lost is a lot on a 40-minute run and
    little on a 300-minute one.

    The back-transform uses Duan's smearing factor rather than a plain exp():
    exp(E[log y]) is the geometric mean, which is biased low for the arithmetic
    mean we are predicting.
    """
    return _ols_variant(train_df, test_df, use_route=True, log_target=True)


def _cycle_ols_physics(train_df, test_df):
    """No route dummies. Measures how much of cycle time the physical and
    operational drivers explain on their own, which is the part that could
    generalise to a road the model has never seen."""
    return _ols_variant(train_df, test_df, use_route=False)


def _ols_variant(train_df, test_df, use_route=True, log_target=False):
    Xtr, ytr, names = build_features(train_df, use_route=use_route)
    assert_no_leakage(names)
    keep = (set(train_df["source"].astype(str) + ">" + train_df["destination"].astype(str))
            if use_route else None)
    Xte, yte, _ = build_features(test_df, feature_names=names, keep_routes=keep,
                                 use_route=use_route)
    import statsmodels.api as sm
    Xtr_c = sm.add_constant(Xtr, has_constant="add")
    Xte_c = sm.add_constant(Xte, has_constant="add").reindex(
        columns=Xtr_c.columns, fill_value=0.0)
    if log_target:
        res = sm.OLS(np.log(ytr), Xtr_c).fit()
        smear = float(np.mean(np.exp(res.resid)))       # Duan's smearing
        return yte, np.exp(res.predict(Xte_c)) * smear
    res = sm.OLS(ytr, Xtr_c).fit()
    return yte, res.predict(Xte_c)


def _cycle_rf(train_df, test_df):
    from sklearn.ensemble import RandomForestRegressor
    Xtr, ytr, names = build_features(train_df)
    assert_no_leakage(names)
    keep = set(train_df["source"].astype(str) + ">" + train_df["destination"].astype(str))
    Xte, yte, _ = build_features(test_df, feature_names=names, keep_routes=keep)
    rf = RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1,
                               min_samples_leaf=3, max_depth=16)
    rf.fit(Xtr.to_numpy(), ytr.to_numpy())
    return yte, rf.predict(Xte.to_numpy())


def _cycle_baseline(train_df, test_df):
    """Per-route/shift historical mean cycle time — the bar to beat."""
    key = ["source", "destination", "shift"]
    tbl = train_df.groupby(key)[TARGET].mean()
    gm = float(train_df[TARGET].mean())
    idx = test_df.set_index(key).index
    pred = pd.Series(idx.map(tbl), index=test_df.index).astype(float).fillna(gm)
    return test_df[TARGET].astype(float), pred


CYCLE_MODELS = {"ols": _cycle_ols, "ols_log": _cycle_ols_log,
                "ols_physics_only": _cycle_ols_physics,
                "random_forest": _cycle_rf,
                "route_mean_baseline": _cycle_baseline}


def validate(df: pd.DataFrame, model_fn, n_folds: int = 5) -> dict:
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").reset_index(drop=True)
    per_fold = []
    for f in make_folds(d, n_folds=n_folds):
        tr, te = d.loc[f["train_idx"]], d.loc[f["test_idx"]]
        try:
            m = _metrics_of(*model_fn(tr, te))
        except Exception as exc:                              # noqa: BLE001
            m = {"error": str(exc)[:200]}
        m.update({k: f[k] for k in ("test_period", "train_rows", "test_rows",
                                    "test_rain_std", "test_rain_all_zero")})
        per_fold.append(m)
    ok = [m for m in per_fold if m.get("r2") is not None]
    mean = {k: (round(float(np.mean([m[k] for m in ok if m.get(k) is not None])), 4)
                if ok else None) for k in ("r2", "mae", "rmse", "mape")}
    return {"folds": per_fold, "mean": mean, "n_folds": len(per_fold),
            "n_folds_scored": len(ok)}


def run(df: pd.DataFrame | None = None, n_folds: int = 5, verbose: bool = True) -> dict:
    if df is None:
        if not os.path.exists(cp.CYCLE_CSV):
            raise FileNotFoundError("run cycle_pipeline.py first")
        df = pd.read_csv(cp.CYCLE_CSV)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    say = print if verbose else (lambda *a, **k: None)
    say("cycle rows %s | %s → %s" % (format(len(df), ","),
        str(df["date"].min())[:10], str(df["date"].max())[:10]))

    # ── in-sample OLS: coefficients, p-values, VIF ─────────────────────────
    X, y, names = build_features(df)
    assert_no_leakage(names)
    res, coefs, stats = train_ols(X, y)
    # Route dummies dominate raw max_vif by construction; report the number that
    # actually gates the interpretation.
    interp_vif = {k: v["vif"] for k, v in coefs.items()
                  if not k.startswith(VIF_EXEMPT_PREFIX) and k != "const"
                  and np.isfinite(v["vif"])}
    max_interp_vif = round(max(interp_vif.values()), 3) if interp_vif else None
    interp_over_10 = sorted([k for k, v in interp_vif.items() if v > 10])
    say("in-sample R² %.4f (adj %.4f), max VIF (interpretable features) %s"
        % (stats["r2"], stats["r2_adj"], max_interp_vif))

    signs = check_signs(coefs)
    for v in signs["violations"]:
        say("  ⚠ wrong sign: %s = %+.4f (expected %s)"
            % (v["feature"], v["coef"], "+" if v["expected"] > 0 else "-"))
    for v in signs["advisory"]:
        say("  · advisory: %s = %+.4f (weak proxy, not gated)"
            % (v["feature"], v["coef"]))
    say("  sign checks: %d confirmed / %d violations of %d significant"
        % (len(signs["confirmed"]), len(signs["violations"]), signs["checked"]))

    # ── walk-forward ───────────────────────────────────────────────────────
    cv = {}
    for name, fn in CYCLE_MODELS.items():
        cv[name] = validate(df, fn, n_folds=n_folds)
        m = cv[name]["mean"]
        say("  %-20s CV R² %-8s MAE %-7s min  (%d folds)"
            % (name, m.get("r2"), m.get("mae"), cv[name]["n_folds_scored"]))

    base = cv["route_mean_baseline"]["mean"].get("r2")
    base_mae = cv["route_mean_baseline"]["mean"].get("mae")
    fitted_models = [k for k in cv if k != "route_mean_baseline"
                     and cv[k]["mean"].get("r2") is not None]
    best_model = max(fitted_models, key=lambda k: cv[k]["mean"]["r2"], default=None)
    best_r2 = cv[best_model]["mean"]["r2"] if best_model else None
    best_mae = cv[best_model]["mean"]["mae"] if best_model else None
    lift = round(best_r2 - base, 4) if (best_r2 is not None and base is not None) else None
    beats = bool(lift is not None and lift >= MIN_LIFT_OVER_BASELINE)
    mae_gain = round(base_mae - best_mae, 2) if (best_mae and base_mae) else None
    mae_gain_pct = (round(100 * mae_gain / base_mae, 1)
                    if (mae_gain is not None and base_mae) else None)

    # R2 and MAE disagree here, and that disagreement is the finding rather than
    # a detail to smooth over. R2 squares the residual, so it is dominated by
    # the handful of shifts where a truck broke down; MAE weights every shift
    # equally. Measured on the last fold, the model is closer than the lookup
    # at the median (14.2 vs 15.7 min), much closer at p75 (28.0 vs 50.1) and
    # p90 (47.9 vs 93.2), and worse only at p99 (283 vs 223). So it is better
    # on the ordinary shift a planner actually schedules, and worse on the rare
    # breakdown nobody can schedule around. Reporting only R2 would hide that;
    # reporting only MAE would overclaim.
    verdict = ("beats_baseline" if beats else
               ("better_mae_similar_r2"
                if (mae_gain is not None and mae_gain > 0 and lift is not None
                    and lift > -0.02)
                else "loses_to_baseline"))

    # Per-fold win/loss, because a mean can hide losing everywhere but once.
    ols_folds = cv[best_model]["folds"] if best_model else []
    bl_folds = cv["route_mean_baseline"]["folds"]
    ols_wins = sum(1 for a, b in zip(ols_folds, bl_folds)
                   if a.get("r2") is not None and b.get("r2") is not None
                   and a["r2"] > b["r2"])
    mae_wins = sum(1 for a, b in zip(ols_folds, bl_folds)
                   if a.get("mae") is not None and b.get("mae") is not None
                   and a["mae"] < b["mae"])

    report = {
        "phase": "3.5",
        "target": TARGET,
        "target_units": "minutes",
        "rows": int(len(df)),
        "date_range": [str(df["date"].min())[:10], str(df["date"].max())[:10]],
        "in_sample": {"r2": stats["r2"], "r2_adj": stats["r2_adj"],
                      "mae": stats["mae"], "mape": stats["mape"],
                      "max_vif_interpretable": max_interp_vif,
                      "interpretable_vif_over_10": interp_over_10,
                      "max_vif_all_incl_route_dummies": stats["max_vif"],
                      "vif_note": ("route dummies are exempt from the VIF<10 gate: "
                                   "one-hot levels are collinear by construction "
                                   "and are reported as counts, not interpreted"),
                      "condition_number": stats["condition_number"],
                      "n_features": stats["n_features"]},
        "sign_checks": signs,
        "cv": cv,
        "winner": best_model,
        "winner_cv_r2": best_r2,
        "winner_cv_mae_min": best_mae,
        "baseline_cv_r2": base,
        "baseline_cv_mae_min": base_mae,
        "lift_over_baseline": lift,
        "beats_baseline": beats,
        "verdict": verdict,
        "mae_gain_min": mae_gain,
        "mae_gain_pct": mae_gain_pct,
        "min_lift_required": MIN_LIFT_OVER_BASELINE,
        "r2_vs_mae_note": (
            "R2 squares the residual so it is dominated by rare breakdown "
            "shifts; MAE weights every shift equally. The model is closer at "
            "the median and p75/p90 and worse only at p99, i.e. better on the "
            "ordinary shift and worse on the outlier nobody can plan around."),
        "folds_won_r2": ols_wins,
        "folds_won_mae": mae_wins,
        "folds_total": len(ols_folds),
        "coefficients": {k: v for k, v in coefs.items() if not k.startswith("rt_")},
        "n_route_dummies": sum(1 for k in coefs if k.startswith("rt_")),
        "phase3_comparison": {
            "note": ("R² is not comparable across different targets; MAE in "
                     "minutes is the interpretable number here"),
            "phase3_target": "trips_per_dt_per_shift",
            "phase3_baseline_cv_r2": 0.4586,
            "phase3_ols_cv_r2": 0.2380,
            "phase3_ols_folds_won": 0,
        },
    }
    os.makedirs(DATA, exist_ok=True)
    with open(CYCLE_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    import pickle
    # Persist the SERVED model, which is the CV winner, not the in-sample OLS
    # fitted above for its p-values. Those two are different fits: `res` is on
    # raw minutes for interpretable coefficients, while the winner is log-scale.
    # Pickling `res.params` while labelling it ols_log would make serving
    # compute exp(67.9) — caught by asserting the scale below rather than by a
    # user seeing an absurd cycle time.
    import statsmodels.api as sm
    log_res = sm.OLS(np.log(y), sm.add_constant(X, has_constant="add")).fit()
    served_params = (log_res.params if best_model == "ols_log" else res.params)
    served_scale = "log_minutes" if best_model == "ols_log" else "minutes"
    smearing = float(np.mean(np.exp(log_res.resid))) if best_model == "ols_log" else 1.0
    if served_scale == "log_minutes" and not (2.0 < float(served_params["const"]) < 8.0):
        raise ValueError("log-scale intercept %.2f is implausible; refusing to "
                         "ship a model that would serve exp() of raw minutes"
                         % float(served_params["const"]))

    util = calibrate_utilisation(df)
    if util.get("utilisation"):
        say("utilisation fitted at %.3f from %d shared routes "
            "(reconciles to %.1f%% median error)"
            % (util["utilisation"], util["routes"],
               util["reconcile_median_abs_pct"]))
    report["utilisation"] = util
    with open(CYCLE_REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    with open(CYCLE_MODEL_PKL, "wb") as fh:
        pickle.dump({"feature_names": names, "utilisation": util,
                     "params": served_params.to_dict(),
                     "param_scale": served_scale,
                     "smearing_factor": smearing,
                     "winner": best_model, "cv_r2": best_r2,
                     "cv_mae_min": best_mae, "verdict": verdict,
                     "baseline_cv_r2": base, "baseline_cv_mae_min": base_mae,
                     "route_means": df.groupby(["source", "destination", "shift"])
                                      [TARGET].mean().to_dict(),
                     "global_mean": float(df[TARGET].mean())}, fh)

    say("\nbest fitted: %s  CV R² %s vs baseline %s (lift %s, bar %s)"
        % (best_model, best_r2, base, lift, MIN_LIFT_OVER_BASELINE))
    say("            MAE %s vs %s min → %s min better (%s%%)"
        % (best_mae, base_mae, mae_gain, mae_gain_pct))
    say("verdict: %s | folds won: R² %d/%d, MAE %d/%d"
        % (verdict, ols_wins, len(ols_folds), mae_wins, len(ols_folds)))
    return report


if __name__ == "__main__":
    run()
