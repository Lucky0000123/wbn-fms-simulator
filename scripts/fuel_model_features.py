#!/usr/bin/env python3
"""Phase 7 — did I stop too early? Rolling-origin validation of extra features.

Section 11 claimed the feature space was exhausted after one 80/20 split. That
was weak evidence. This tests the claim properly:

  * rolling-origin (walk-forward) CV instead of a single split, so the result
    is not an artefact of where the cut landed
  * candidate features never tried: day-of-week, lagged litres, lagged
    active-units, trend, standby/breakdown hours, ticket counts, payload
  * rainfall is EXCLUDED: dbo.RAINFALL stops 2026-04-11 and covers only 63 of
    139 fuel days, so it cannot serve the holdout period at all

Runs offline from data/fuel_recon/training_set.csv.
"""
import csv
import math
import pathlib
import statistics as st
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "fuel_recon" / "training_set.csv"


def num(r, k):
    v = r.get(k)
    try:
        return float(v) if v not in ("", "None", None) else None
    except ValueError:
        return None


def ols(X, y, ridge=1e-6):
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) + (ridge if i == j else 0.0)
          for j in range(k)] for i in range(k)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
    for i in range(k):
        p = A[i][i]
        if abs(p) < 1e-12:
            return None
        for j in range(i, k):
            A[i][j] /= p
        b[i] /= p
        for r2 in range(k):
            if r2 != i:
                f = A[r2][i]
                for j in range(i, k):
                    A[r2][j] -= f * A[i][j]
                b[r2] -= f * b[i]
    return b


def build_days():
    rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8"))
            if (num(r, "litres") or 0) > 0]
    day = defaultdict(lambda: defaultdict(float))
    for r in rows:
        v = day[r["date"]]
        v["litres"] += num(r, "litres")
        v["work_hrs"] += num(r, "work_hrs") or 0
        v["stby_hrs"] += num(r, "stby_hrs") or 0
        v["bd_hrs"] += num(r, "bd_hrs") or 0
        v["tonnes"] += (num(r, "net_weight") or 0) / 1000.0
        v["tickets"] += num(r, "tickets") or 0
        v["units"] += 1
        v["fills"] += num(r, "fills") or 0
    d = sorted(day.items())
    import datetime
    for i, (dt, v) in enumerate(d):
        y, m, dd = (int(x) for x in dt.split("-"))
        v["dow"] = float(datetime.date(y, m, dd).weekday())
        v["is_sun"] = 1.0 if v["dow"] == 6 else 0.0
        v["t"] = float(i)
        v["lag1_litres"] = d[i - 1][1]["litres"] if i else v["litres"]
        v["lag1_units"] = d[i - 1][1]["units"] if i else v["units"]
        v["lag7_litres"] = d[i - 7][1]["litres"] if i >= 7 else v["litres"]
        v["lag1_fills"] = d[i - 1][1]["fills"] if i else v["fills"]
    return d


FEATURES = {
    "units only":                 ["units"],
    "units + work_hrs":           ["units", "work_hrs"],
    "units + dow":                ["units", "dow"],
    "units + is_sunday":          ["units", "is_sun"],
    "units + lag1_litres":        ["units", "lag1_litres"],
    "units + lag7_litres":        ["units", "lag7_litres"],
    "units + trend":              ["units", "t"],
    "units + stby + bd":          ["units", "stby_hrs", "bd_hrs"],
    "units + tonnes":             ["units", "tonnes"],
    "units + tickets":            ["units", "tickets"],
    # NOTE: "units + fills" is deliberately absent. fills is the refuel-event
    # count and litres = fills * 199.2 L fleet-wide (corr +0.9924), so it is
    # the target decomposed, not a predictor, and is unknowable in advance.
    # It scores 2.38% MAPE purely by leakage. See report section 12.1.
    "units + lag1_fills":         ["units", "lag1_fills"],
    "kitchen sink":               ["units", "work_hrs", "stby_hrs", "bd_hrs",
                                   "tonnes", "tickets", "lag1_litres", "t"],
}


def rolling_eval(d, feats, min_train=80, step=7):
    """Walk-forward: expand training window, predict the next `step` days."""
    errs = []
    i = min_train
    while i < len(d):
        tr, te = d[:i], d[i:i + step]
        X = [[1.0] + [v[f] for f in feats] for _, v in tr]
        y = [v["litres"] for _, v in tr]
        b = ols(X, y)
        if b is None:
            return None
        for _, v in te:
            p = b[0] + sum(c * v[f] for c, f in zip(b[1:], feats))
            errs.append(abs(p - v["litres"]) / v["litres"])
        i += step
    return 100 * st.mean(errs), len(errs)


def main():
    d = build_days()
    print(f"fleet-days: {len(d)}  ({d[0][0]} -> {d[-1][0]})")
    print("\n== Rolling-origin CV (expand train, predict next 7 days) ==")
    base_errs = []
    i = 80
    while i < len(d):
        tr, te = d[:i], d[i:i + 7]
        m = st.mean(v["litres"] for _, v in tr)
        base_errs += [abs(m - v["litres"]) / v["litres"] for _, v in te]
        i += 7
    print(f"  {'mean litres (no model)':32} MAPE={100*st.mean(base_errs):5.2f}%  "
          f"n={len(base_errs)}")
    out = []
    for name, feats in FEATURES.items():
        r = rolling_eval(d, feats)
        if r:
            out.append((r[0], name, r[1]))
    for mape, name, n in sorted(out):
        print(f"  {name:32} MAPE={mape:5.2f}%  n={n}")
    best = min(out)
    uo = [x for x in out if x[1] == "units only"][0]
    print(f"\n  best: {best[1]} at {best[0]:.2f}%")
    print(f"  vs 'units only' {uo[0]:.2f}%  ->  "
          f"gain {uo[0]-best[0]:+.2f} pp")
    if uo[0] - best[0] < 0.25:
        print(f"  => gain is immaterial (<0.25 pp). 'units only' stands; "
              f"prefer the simplest form.")
    else:
        print("  => MATERIAL GAIN. Adopt the better feature set.")
    print("\n  Reminder: 'fills' is excluded as leakage (corr +0.9924 with "
          "the target).\n  Robustness across CV settings is in report "
          "section 12.2.")


if __name__ == "__main__":
    main()
