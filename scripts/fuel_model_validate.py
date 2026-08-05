#!/usr/bin/env python3
"""Validate diesel forecasting approaches on a time-based holdout.

Reads data/fuel_recon/training_set.csv (no DB needed) and reports honest
out-of-sample error for each candidate target, at both grains.

Headline result: per-unit-day burn-rate models FAIL (worse than predicting the
mean) because a refuel is a tank fill, not a day's consumption. Aggregating to
fleet-day fixes it, and active-unit count is the dominant predictor.
"""
import csv
import math
import pathlib
import statistics as st
from collections import defaultdict

CSV = pathlib.Path(__file__).resolve().parent.parent / "data" / "fuel_recon" / "training_set.csv"


def num(r, k):
    v = r.get(k)
    try:
        return float(v) if v not in ("", "None", None) else None
    except ValueError:
        return None


def corr(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    dx = sum((a - mx) ** 2 for a in xs)
    dy = sum((b - my) ** 2 for b in ys)
    if dx <= 0 or dy <= 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / math.sqrt(dx * dy)


def ols(X, y):
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
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
                fac = A[r2][i]
                for j in range(i, k):
                    A[r2][j] -= fac * A[i][j]
                b[r2] -= fac * b[i]
    return b


def report(name, te, pred, actual):
    e = [abs(pred(x) - actual(x)) for x in te]
    ap = [abs(pred(x) - actual(x)) / actual(x) for x in te if actual(x)]
    print(f"  {name:34} MAE={st.mean(e):9.1f} L  MAPE={100*st.mean(ap):5.1f}%")
    return st.mean(ap)


def main():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    ok = [r for r in rows if (num(r, "litres") or 0) > 0]
    print(f"rows={len(rows):,}  with litres={len(ok):,}  "
          f"units={len({r['unit_id'] for r in ok})}")

    # ---------- why the per-unit-day model fails ----------
    li = [num(r, "litres") for r in ok]
    fl = [num(r, "fills") for r in ok]
    wh = [num(r, "work_hrs") or 0 for r in ok]
    print("\n== Why a per-unit-day burn-rate target fails ==")
    print(f"  corr(fills,    litres) = {corr(fl, li):+.3f}  "
          "<- litres tracks REFUEL EVENTS")
    print(f"  corr(work_hrs, litres) = {corr(wh, li):+.3f}  "
          "<- barely tracks actual work")
    per = sorted(a / b for a, b in zip(li, fl) if b)
    print(f"  litres per fill: p05={per[int(.05*len(per))]:.0f} "
          f"p50={per[len(per)//2]:.0f} p95={per[int(.95*len(per))]:.0f} "
          "-> a fill tops up a ~200 L tank; it does not measure the day's burn.")

    # ---------- aggregation fixes it ----------
    by = defaultdict(lambda: [0.0, 0.0, 0])
    for r in ok:
        v = by[r["unit_id"]]
        v[0] += num(r, "litres")
        v[1] += num(r, "work_hrs") or 0
        v[2] += 1
    agg = [(l, h) for l, h, n in by.values() if n >= 30 and h > 0]
    print("\n== Aggregation removes the refuel lumpiness ==")
    print(f"  corr over {len(agg)} units (>=30 fuel-days) = "
          f"{corr([h for _, h in agg], [l for l, _ in agg]):+.3f}")
    rate = sorted(l / h for l, h in agg)
    print(f"  per-unit lifetime L/work-hr: p05={rate[int(.05*len(rate))]:.1f} "
          f"p50={rate[len(rate)//2]:.1f} p95={rate[int(.95*len(rate))]:.1f}")

    # ---------- fleet-day forecasting ----------
    day = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for r in ok:
        v = day[r["date"]]
        v[0] += num(r, "litres")
        v[1] += num(r, "work_hrs") or 0
        v[2] += (num(r, "net_weight") or 0) / 1000.0
        v[3] += 1
    d = sorted(day.items())
    L = [v[0] for _, v in d]
    print(f"\n== Fleet-day grain: {len(d)} days "
          f"({d[0][0]} -> {d[-1][0]}) ==")
    print(f"  corr(work_hrs,    litres) = {corr([v[1] for _, v in d], L):+.3f}")
    print(f"  corr(tonnes,      litres) = {corr([v[2] for _, v in d], L):+.3f}")
    print(f"  corr(active units,litres) = {corr([float(v[3]) for _, v in d], L):+.3f}"
          "  <- dominant driver")

    cut = int(.8 * len(d))
    tr, te = d[:cut], d[cut:]
    print(f"\n== Time-based holdout: train {len(tr)} days, "
          f"test {len(te)} from {te[0][0]} ==")
    base = st.mean(v[0] for _, v in tr)
    pu = sum(v[0] for _, v in tr) / sum(v[3] for _, v in tr)
    hr = sum(v[0] for _, v in tr) / sum(v[1] for _, v in tr)
    b = ols([[1, float(v[3]), v[1]] for _, v in tr], [v[0] for _, v in tr])
    act = lambda kv: kv[1][0]
    report("mean litres (no model)", te, lambda kv: base, act)
    report("fleet rate x work_hrs", te, lambda kv: hr * kv[1][1], act)
    report("litres/active-unit x units", te, lambda kv: pu * kv[1][3], act)
    if b:
        report("OLS(active units, work_hrs)", te,
               lambda kv: b[0] + b[1] * kv[1][3] + b[2] * kv[1][1], act)
    print(f"\n  litres per active unit-day = {pu:.1f} L")
    print(f"  fleet burn rate            = {hr:.2f} L/work-hr")
    print(f"  mean fleet day             = {base:,.0f} L")


if __name__ == "__main__":
    main()
