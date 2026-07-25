"""
Phase 2 — model training.

    python train_model.py            # extract → engineer → train → save
    python train_model.py --no-extract   # retrain on the existing CSV

Trains two models on the same features and keeps the better one:

  A. OLS baseline   — LinearRegression over the full one-hot + scaled matrix.
                      Directly comparable to the per-path OLS already in
                      simulator_api.py, but with contractor, weather, shift,
                      weighbridge and day-of-week terms added.
  B. Random Forest  — 100 trees, captures the non-linear interactions the OLS
                      cannot (e.g. rain hurting long hauls more than short).

The split is chronological, not random: the most recent 20% of shifts are held
out. A random split would leak future shifts into training and inflate the
score, because shifts on the same day are highly correlated.

Selection is by held-out R². Ties and near-ties go to OLS, which is cheaper to
serve and easier to explain to an operator.

Idempotent: fixed random_state and a deterministic split, so repeated runs on
unchanged data reproduce the same metrics and overwrite the same files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import prediction_pipeline as pp

MODEL_PKL = os.path.join(pp.DATA, "model.pkl")
MODEL_META = os.path.join(pp.DATA, "model_metadata.json")

RANDOM_STATE = 42
TEST_FRACTION = 0.20


def _metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    mse = float(mean_squared_error(y_true, y_pred))
    return {
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mse)), 4),
    }


def chronological_split(df: pd.DataFrame):
    """Hold out the most recent TEST_FRACTION of *dates* (never split a date
    across train and test — same-day shifts are far too correlated)."""
    dates = np.sort(df["date"].astype(str).unique())
    cut_idx = max(1, int(len(dates) * (1 - TEST_FRACTION)))
    cut = dates[min(cut_idx, len(dates) - 1)]
    train = df[df["date"].astype(str) < cut]
    test = df[df["date"].astype(str) >= cut]
    if train.empty or test.empty:                          # tiny datasets
        n = max(1, int(len(df) * (1 - TEST_FRACTION)))
        train, test = df.iloc[:n], df.iloc[n:]
        cut = "row-split"
    return train, test, str(cut)


def train(extract: bool = True, verbose: bool = True) -> dict:
    log = print if verbose else (lambda *a, **k: None)

    # 1 ── data
    if extract or not os.path.exists(pp.TRAINING_CSV):
        frame = pp.extract()
        info = pp.save_training_data(frame)
        log("[1/5] extracted %s rows from %s" % (f"{info['row_count']:,}", info["source"]))
    df = pd.read_csv(pp.TRAINING_CSV)
    log("[2/5] loaded %s rows · target=%s" % (f"{len(df):,}", pp.TARGET))

    # 2 ── chronological split
    train_df, test_df, cut = chronological_split(df)
    log("[3/5] split at %s → train %s / test %s"
        % (cut, f"{len(train_df):,}", f"{len(test_df):,}"))

    # 3 ── features (fit on TRAIN ONLY, so the scaler cannot see the test period)
    enc, scaler = pp.fit_transformers(train_df)
    X_train = pp.build_matrix(train_df, enc, scaler)
    X_test = pp.build_matrix(test_df, enc, scaler)
    y_train = train_df[pp.TARGET].to_numpy(float)
    y_test = test_df[pp.TARGET].to_numpy(float)
    names = pp.feature_names(enc)
    log("[4/5] design matrix %d features" % len(names))

    # 4 ── candidates
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression

    results = {}
    ols = LinearRegression().fit(X_train, y_train)
    results["ols"] = _metrics(y_test, ols.predict(X_test))

    rf = RandomForestRegressor(n_estimators=100, random_state=RANDOM_STATE,
                               n_jobs=-1, min_samples_leaf=2,
                               # Bound the tree size: unconstrained forests on
                               # 50k rows serialise to ~200 MB, which is far too
                               # large to load quickly or keep on disk. These
                               # limits cost very little accuracy.
                               max_depth=18, max_leaf_nodes=512)
    rf.fit(X_train, y_train)
    results["random_forest"] = _metrics(y_test, rf.predict(X_test))

    log("[5/5] held-out performance")
    for name in ("ols", "random_forest"):
        m = results[name]
        log("      %-14s R2=%7.4f  MAE=%7.4f  RMSE=%7.4f"
            % (name, m["r2"], m["mae"], m["rmse"]))

    # 5 ── keep the better model (ties → OLS: cheaper and explainable)
    best = "random_forest" if results["random_forest"]["r2"] > results["ols"]["r2"] + 0.005 else "ols"
    model = rf if best == "random_forest" else ols

    import joblib
    os.makedirs(pp.DATA, exist_ok=True)
    joblib.dump(model, MODEL_PKL)

    importances = None
    if best == "random_forest":
        order = np.argsort(rf.feature_importances_)[::-1][:12]
        importances = [[names[i], round(float(rf.feature_importances_[i]), 4)] for i in order]

    meta = {
        "model_type": best,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "split_date": cut,
        "r2": results[best]["r2"],
        "mae": results[best]["mae"],
        "rmse": results[best]["rmse"],
        "candidates": results,
        "features": names,
        "target": pp.TARGET,
        "categorical": pp.CATEGORICAL,
        "numeric": pp.NUMERIC,
        "top_features": importances,
        "data_source": json.load(open(pp.TRAINING_META))["source"]
        if os.path.exists(pp.TRAINING_META) else "unknown",
    }
    with open(MODEL_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    log("      selected %s (R2=%.4f) → %s"
        % (best, results[best]["r2"], os.path.relpath(MODEL_PKL, pp.BASE)))
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Train the WBN productivity model")
    ap.add_argument("--no-extract", action="store_true",
                    help="retrain on the existing data/training_data.csv")
    args = ap.parse_args()
    try:
        train(extract=not args.no_extract)
    except Exception as exc:                               # noqa: BLE001
        print("training failed: %s" % exc, file=sys.stderr)
        raise
