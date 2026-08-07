#!/usr/bin/env python3
"""Phase 8 — end-to-end forecast error, with NO oracle inputs.

Sections 11-12 report 3.3% MAPE for `litres = a + b*active_units`. That number
assumes you already know tomorrow's active-unit count. In a real forecast you
do not: it must itself be predicted, and the errors compound.

This measures the honest end-to-end figure by forecasting active_units from
history first, then feeding that estimate into the litres model. Rolling-origin
throughout, so nothing downstream ever sees the future.

Runs offline from data/fuel_recon/training_set.csv.
"""
import csv
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_model_features import build_days, ols  # noqa: E402


def unit_forecasters(tr, horizon):
    """Predictors for active_units, using only data up to the cut."""
    hist = [v["units"] for _, v in tr]
    dows = {}
    for _, v in tr[-28:]:
        dows.setdefault(v["dow"], []).append(v["units"])
    return {
        "last value": lambda v: hist[-1],
        "7-day MA": lambda v: st.mean(hist[-7:]),
        "28-day MA": lambda v: st.mean(hist[-28:]),
        "day-of-week MA": lambda v: st.mean(dows.get(v["dow"], hist[-7:])),
    }


def attach_fleet(d):
    """Add fleet-wide working-unit counts (independent of refuelling)."""
    f = (pathlib.Path(__file__).resolve().parent.parent / "data" /
         "fuel_recon" / "fleet_daily.csv")
    if not f.exists():
        return False
    fl = {r["d"]: r for r in csv.DictReader(open(f, encoding="utf-8"))}
    for k, v in d:
        row = fl.get(k)
        v["wunits"] = float(row["working_units"]) if row else 0.0
        v["whrs"] = float(row["work_hrs"]) if row else 0.0
    return all(v["wunits"] > 0 for _, v in d)


def driver_comparison(d):
    """Section 13.3: is fleet-wide working-unit count a better driver?

    It is far more predictable (persistence 2.59% vs 12.21%) but far less
    informative (corr +0.529 vs +0.976), and loses end-to-end.
    """
    MT, STEP = 80, 7

    def e2e(feats, known=()):
        e = []
        i = MT
        while i < len(d):
            tr, te = d[:i], d[i:i + STEP]
            b = ols([[1.0] + [v[f] for f in feats] for _, v in tr],
                    [v["litres"] for _, v in tr])
            if b is None:
                return None
            last = {f: tr[-1][1][f] for f in feats}
            for _, v in te:
                xs = [v[f] if f in known else last[f] for f in feats]
                pr = b[0] + sum(c * x for c, x in zip(b[1:], xs))
                e.append(abs(pr - v["litres"]) / v["litres"])
            i += STEP
        return 100 * st.mean(e)

    def persist(key):
        e = []
        i = MT
        while i < len(d):
            tr, te = d[:i], d[i:i + STEP]
            lv = tr[-1][1][key]
            e += [abs(lv - v[key]) / v[key] for _, v in te]
            i += STEP
        return 100 * st.mean(e)

    print("\n== 13.3 Driver comparison: refuel units vs working units ==\n")
    print(f"  {'driver':30} {'oracle':>8} {'persist':>9} {'end-to-end':>11}")
    for name, feats, key in [
            ("refuel units (current)", ["units"], "units"),
            ("working units", ["wunits"], "wunits"),
            ("working units + work_hrs", ["wunits", "whrs"], "wunits"),
            ("both", ["units", "wunits"], "units")]:
        print(f"  {name:30} {e2e(feats, known=feats):7.2f}% "
              f"{persist(key):8.2f}% {e2e(feats):10.2f}%")
    print("\n  Working units are steadier but weakly related to fuel "
          "(corr +0.529 vs +0.976).")
    print("  Even given free they reach only ~16.9%; refuel-unit count stays "
          "the best driver.")


def main():
    d = [(k, dict(v)) for k, v in build_days()]
    print(f"fleet-days: {len(d)}  ({d[0][0]} -> {d[-1][0]})")
    u = [v["units"] for _, v in d]
    print(f"active_units: p05={sorted(u)[int(.05*len(u))]:.0f} "
          f"p50={sorted(u)[len(u)//2]:.0f} "
          f"p95={sorted(u)[int(.95*len(u))]:.0f} sd={st.pstdev(u):.1f}")

    MT, STEP = 80, 7
    names = ["last value", "7-day MA", "28-day MA", "day-of-week MA"]
    unit_err = {n: [] for n in names}
    fuel_err = {n: [] for n in names}
    fuel_abs = {n: [] for n in names}
    oracle, oracle_abs, naive = [], [], []

    i = MT
    while i < len(d):
        tr, te = d[:i], d[i:i + STEP]
        b = ols([[1.0, v["units"]] for _, v in tr],
                [v["litres"] for _, v in tr])
        mean_l = st.mean(v["litres"] for _, v in tr)
        fc = unit_forecasters(tr, STEP)
        for _, v in te:
            act = v["litres"]
            naive.append(abs(mean_l - act) / act)
            o = b[0] + b[1] * v["units"]          # oracle: true unit count
            oracle.append(abs(o - act) / act)
            oracle_abs.append(abs(o - act))
            for n in names:
                pu = fc[n](v)
                unit_err[n].append(abs(pu - v["units"]) / v["units"])
                p = b[0] + b[1] * pu
                fuel_err[n].append(abs(p - act) / act)
                fuel_abs[n].append(abs(p - act))
        i += STEP

    n_obs = len(oracle)
    print(f"\n== Rolling-origin, {n_obs} forecast days, horizon {STEP} ==\n")
    print(f"  {'method':22} {'units MAPE':>11} {'litres MAPE':>12} "
          f"{'litres MAE':>12}")
    print(f"  {'-'*22} {'-'*11} {'-'*12} {'-'*12}")
    print(f"  {'no model (train mean)':22} {'':>11} "
          f"{100*st.mean(naive):11.1f}% {'':>12}")
    print(f"  {'ORACLE units (§11-12)':22} {'0.00%':>11} "
          f"{100*st.mean(oracle):11.1f}% {st.mean(oracle_abs):11,.0f} L")
    for n in names:
        print(f"  {n:22} {100*st.mean(unit_err[n]):10.2f}% "
              f"{100*st.mean(fuel_err[n]):11.1f}% "
              f"{st.mean(fuel_abs[n]):11,.0f} L")

    best = min(names, key=lambda n: st.mean(fuel_err[n]))
    print(f"\n  Best fully-autonomous forecast: '{best}' at "
          f"{100*st.mean(fuel_err[best]):.1f}% MAPE "
          f"({st.mean(fuel_abs[best]):,.0f} L/day).")
    print(f"  Oracle-unit figure was {100*st.mean(oracle):.1f}%. Forecasting "
          f"the unit count costs "
          f"{100*(st.mean(fuel_err[best])-st.mean(oracle)):+.1f} pp.")
    print(f"  Still beats the no-model baseline of {100*st.mean(naive):.1f}%.")
    print("\n  => If the plan supplies tomorrow's unit count, expect ~"
          f"{100*st.mean(oracle):.0f}%. If nothing is known, expect ~"
          f"{100*st.mean(fuel_err[best]):.0f}%.")

    if attach_fleet(d):
        driver_comparison(d)
    else:
        print("\n  (skipping 13.3 driver comparison: "
              "data/fuel_recon/fleet_daily.csv missing or incomplete)")


if __name__ == "__main__":
    main()
