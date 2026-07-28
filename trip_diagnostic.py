"""trip_diagnostic.py — does the grain change actually pay?

This is NOT the Phase 4 model. It is one deliberately plain fit whose only job
is to answer the question that justifies the data layer:

    an aggregate model was capped at R² 0.254 by averaging.
    Does the same modelling, run at trip grain, clear that ceiling?

If it does, the 483,425 rows were worth extracting and Phase 4 has room to work
in. If it does not, the within-group variance is irreducible noise — truck to
truck, queue to queue — and Phase 4 should be told to stop chasing it rather
than discovering it independently.

Validation is walk-forward, matching Phase 3 exactly, so the comparison is fair.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import trip_extraction as tx
from prediction_pipeline import _metrics_of, make_folds

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
REPORT = os.path.join(DATA, "trip_diagnostic.json")
TARGET = tx.TARGET

# Pre-registered, before seeing any fit.
EXPECTED_SIGNS = {
    "distance_km": +1,          # farther is slower
    "rainfall_mm": +1,          # wet roads slow trucks
    "is_wet": +1,
    "trucks_on_route": +1,      # more trucks queue at the loader
    "payload_t": +1,            # heavier is slower
    "is_night": -1,             # measured in Phase 3.5: emptier road wins
}


def build_features(df, feature_names=None, keep_routes=None):
    d = df.copy()
    if keep_routes is not None:
        d["route"] = d["route"].where(d["route"].isin(keep_routes), "OTHER")

    X = pd.DataFrame(index=d.index)
    X["payload_t"] = pd.to_numeric(d["payload_t"], errors="coerce").fillna(30.0)
    X["trucks_on_route"] = pd.to_numeric(d["trucks_on_route"], errors="coerce").fillna(1.0)
    X["rainfall_mm"] = pd.to_numeric(d["rainfall_mm"], errors="coerce").fillna(0.0)
    X["is_wet"] = pd.to_numeric(d.get("is_wet", 0), errors="coerce").fillna(0.0)
    X["is_night"] = (d["shift"].astype(str) == "night").astype(float)
    X["is_weekend"] = pd.to_numeric(d["is_weekend"], errors="coerce").fillna(0.0)
    # Hour of departure is the trip-grain feature an aggregate simply cannot
    # have: it varies between trips inside one shift, which is precisely the
    # variance averaging destroyed. Cyclic encoding so 23:00 sits next to 00:00.
    h = pd.to_numeric(d["depart_hour"], errors="coerce").fillna(12.0)
    X["hour_sin"] = np.sin(2 * np.pi * h / 24.0)
    X["hour_cos"] = np.cos(2 * np.pi * h / 24.0)

    # distance_km is a pure function of route, so it goes in ONLY when route
    # dummies are absent. Phase 3.5 hit a 1.9e12 VIF singularity this way.
    dummies = pd.get_dummies(d["route"], prefix="rt", drop_first=True, dtype=float)
    X = pd.concat([X, dummies], axis=1)

    if feature_names is not None:
        X = X.reindex(columns=feature_names, fill_value=0.0)
    y = pd.to_numeric(d[TARGET], errors="coerce")
    ok = y.notna()
    return X[ok].astype(float), y[ok].astype(float), list(X.columns)


def _ols(train_df, test_df, log_target=True):
    import statsmodels.api as sm
    Xtr, ytr, names = build_features(train_df)
    tx.assert_no_leakage(names)
    Xte, yte, _ = build_features(test_df, feature_names=names,
                                 keep_routes=set(train_df["route"]))
    A = sm.add_constant(Xtr, has_constant="add")
    B = sm.add_constant(Xte, has_constant="add").reindex(columns=A.columns, fill_value=0.0)
    if log_target:
        r = sm.OLS(np.log(ytr), A).fit()
        return yte, np.exp(r.predict(B)) * float(np.mean(np.exp(r.resid)))
    r = sm.OLS(ytr, A).fit()
    return yte, r.predict(B)


def _ols_raw(tr, te):
    return _ols(tr, te, log_target=False)


def _baseline(train_df, test_df):
    """Per-route/shift mean — the same bar Phase 3 lost to, at trip grain."""
    key = ["route", "shift"]
    tbl = train_df.groupby(key)[TARGET].mean()
    gm = float(train_df[TARGET].mean())
    pred = pd.Series(test_df.set_index(key).index.map(tbl),
                     index=test_df.index).astype(float).fillna(gm)
    return test_df[TARGET].astype(float), pred


def _hgb(train_df, test_df):
    """Histogram gradient boosting: fast on 480k rows and able to use the
    non-linearity Phase 3's residual diagnostics pointed at."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    Xtr, ytr, names = build_features(train_df)
    tx.assert_no_leakage(names)
    Xte, yte, _ = build_features(test_df, feature_names=names,
                                 keep_routes=set(train_df["route"]))
    m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.1,
                                      max_depth=8, random_state=42)
    m.fit(Xtr.to_numpy(), np.log(ytr.to_numpy()))
    return yte, np.exp(m.predict(Xte.to_numpy()))


def _oracle(train_df, test_df):
    """Upper bound: a predictor that KNOWS each test group's true mean.

    The global variance decomposition is the wrong benchmark for a walk-forward
    score, because it is computed over all months at once while each fold is
    scored on one. This oracle is the per-fold version -- the best any model
    could do if it predicted route/shift/date group means perfectly -- so
    "how close did we get" becomes a fair question. Measured: global ceiling
    0.2543 but mean per-fold oracle 0.2574, and the two diverge sharply fold to
    fold (0.172 in May, 0.428 in July).
    """
    y = test_df[TARGET].astype(float)
    return y, test_df.groupby(["route", "shift", "date"])[TARGET].transform("mean")


MODELS = {"ols_log": _ols, "ols_raw": _ols_raw,
          "hist_gradient_boosting": _hgb, "route_shift_baseline": _baseline,
          "oracle_group_mean": _oracle}


def validate(df, fn, n_folds=5):
    d = df.sort_values("date").reset_index(drop=True)
    per_fold = []
    for f in make_folds(d, n_folds=n_folds):
        tr, te = d.loc[f["train_idx"]], d.loc[f["test_idx"]]
        try:
            m = _metrics_of(*fn(tr, te))
        except Exception as exc:                            # noqa: BLE001
            m = {"error": str(exc)[:200]}
        m["test_period"] = f["test_period"]
        m["test_rows"] = f["test_rows"]
        per_fold.append(m)
    ok = [m for m in per_fold if m.get("r2") is not None]
    mean = {k: (round(float(np.mean([m[k] for m in ok])), 4) if ok else None)
            for k in ("r2", "mae", "rmse", "mape")}
    return {"folds": per_fold, "mean": mean, "n_scored": len(ok)}


def run(df=None, n_folds=5, verbose=True):
    if df is None:
        df = pd.read_csv(tx.TRIP_CSV)
    df["date"] = pd.to_datetime(df["date"])
    say = print if verbose else (lambda *a, **k: None)

    vd = tx.variance_decomposition(df)
    ceiling = vd["aggregate_model_r2_ceiling"]
    say("trips %s | %s → %s" % (format(len(df), ","),
        str(df["date"].min())[:10], str(df["date"].max())[:10]))
    say("aggregate ceiling R² %.4f (%.1f%% of variance is within-group)"
        % (ceiling, vd["within_group_pct"]))

    cv = {}
    for name, fn in MODELS.items():
        cv[name] = validate(df, fn, n_folds)
        m = cv[name]["mean"]
        say("  %-24s R² %-8s MAE %-7s min" % (name, m.get("r2"), m.get("mae")))

    fitted = [k for k in cv if k not in ("route_shift_baseline", "oracle_group_mean")
              and cv[k]["mean"].get("r2") is not None]
    best = max(fitted, key=lambda k: cv[k]["mean"]["r2"], default=None)
    best_r2 = cv[best]["mean"]["r2"] if best else None
    base = cv["route_shift_baseline"]["mean"]

    oracle = cv["oracle_group_mean"]["mean"].get("r2")
    reached = (round(best_r2 / oracle, 4)
               if (best_r2 and oracle and oracle > 0) else None)
    clears = bool(best_r2 is not None and best_r2 > ceiling)
    beats_baseline = bool(best_r2 is not None and base.get("r2") is not None
                          and best_r2 - base["r2"] >= 0.05)

    report = {
        "purpose": "diagnostic only — does trip grain clear the aggregate ceiling?",
        "rows": int(len(df)),
        "date_range": [str(df["date"].min())[:10], str(df["date"].max())[:10]],
        "variance_decomposition": vd,
        "aggregate_ceiling_r2": ceiling,
        "cv": cv,
        "best_model": best,
        "best_cv_r2": best_r2,
        "best_cv_mae_min": cv[best]["mean"]["mae"] if best else None,
        "baseline_cv_r2": base.get("r2"),
        "baseline_cv_mae_min": base.get("mae"),
        "oracle_cv_r2": oracle,
        "fraction_of_oracle_reached": reached,
        "clears_aggregate_ceiling": clears,
        "beats_trip_baseline": beats_baseline,
        "phase3_reference": {"target": "trips_per_dt_per_shift",
                             "baseline_cv_r2": 0.4586, "ols_cv_r2": 0.2380,
                             "note": "different target and grain; not comparable "
                                     "directly, which is why the ceiling test is "
                                     "the one that matters"},
    }
    os.makedirs(DATA, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    say("\nbest %s: R² %s vs global ceiling %.4f → clears=%s"
        % (best, best_r2, ceiling, clears))
    if oracle:
        say("      oracle (knows true group means) R² %.4f → model reaches %.1f%% of it"
            % (oracle, 100 * (reached or 0)))
    say("      vs trip baseline R² %s / MAE %s min → beats_by_0.05=%s"
        % (base.get("r2"), base.get("mae"), beats_baseline))
    return report


if __name__ == "__main__":
    run()
