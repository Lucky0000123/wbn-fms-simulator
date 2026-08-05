#!/usr/bin/env python3
"""Diesel consumption forecaster — the deployable artefact.

Everything before this was analysis. This is the thing you call.

    from fuel_forecast import DieselForecaster
    fc = DieselForecaster.load()
    fc.predict(active_units=230)        # -> litres for tomorrow
    fc.predict()                        # -> persistence, no input needed

Accuracy, measured by rolling-origin CV (report sections 11-13):
    active_units supplied   ~3.5% MAPE  (+/- 1,800 L/day)
    autonomous (persistence) ~13% MAPE  (+/- 7,100 L/day)
    no model (fleet mean)    19.3% MAPE

CLI:
    python scripts/fuel_forecast.py --fit          # refit from training_set.csv
    python scripts/fuel_forecast.py --units 230    # forecast with a roster
    python scripts/fuel_forecast.py                # autonomous forecast
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics as st
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "fuel_recon"
TRAINING = DATA / "training_set.csv"
MODEL = DATA / "diesel_model.json"

# Guard rails from the observed data (report §11.4, §13).
MIN_UNITS, MAX_UNITS = 50, 400
# The WAITING_TIME feed stopped 2026-07-22 (report §15.3). Warn once the
# training data is old enough that the forecast may not reflect operations.
STALE_WARN_DAYS = 30


class DieselForecaster:
    """litres_per_day = intercept + slope * active_units."""

    def __init__(self, intercept, slope, last_units, last_litres, meta=None):
        self.intercept = float(intercept)
        self.slope = float(slope)
        self.last_units = float(last_units)
        self.last_litres = float(last_litres)
        self.meta = meta or {}

    # ---------- prediction ----------
    def predict(self, active_units=None):
        """Litres for the next day.

        active_units: from the roster if known. If omitted, persistence is
        used (yesterday's count), which is the ~13% autonomous case.
        """
        assumed = active_units is None
        u = self.last_units if assumed else float(active_units)
        if not MIN_UNITS <= u <= MAX_UNITS:
            raise ValueError(
                f"active_units={u:.0f} outside observed range "
                f"[{MIN_UNITS}, {MAX_UNITS}]. The model is linear and was fit "
                "on 133-281 units; extrapolating is not supported.")
        litres = self.intercept + self.slope * u
        band = 7100 if assumed else 1800
        stale = self.staleness_days()
        return {
            "training_data_age_days": stale,
            "stale_warning": (
                f"training data ends {self.meta.get('date_range',[None,None])[1]}"
                f" ({stale} days old); verify the WAITING_TIME feed is live"
                if stale is not None and stale > STALE_WARN_DAYS else None),
            "litres": round(litres, 1),
            "active_units": u,
            "units_assumed": assumed,
            "expected_mape_pct": 13.0 if assumed else 3.5,
            "range_low": round(litres - band, 1),
            "range_high": round(litres + band, 1),
            "basis": ("persistence (no roster supplied)" if assumed
                      else "roster-supplied active-unit count"),
        }

    def staleness_days(self):
        """Age in days of the newest training day. See report §15.3."""
        rng = self.meta.get("date_range")
        if not rng or not rng[1]:
            return None
        import datetime
        y, m, d = (int(x) for x in str(rng[1])[:10].split("-"))
        return (datetime.date.today() - datetime.date(y, m, d)).days

    # ---------- persistence ----------
    def save(self, path=MODEL):
        path.write_text(json.dumps({
            "intercept": self.intercept, "slope": self.slope,
            "last_units": self.last_units, "last_litres": self.last_litres,
            "meta": self.meta}, indent=1), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path=MODEL):
        if not path.exists():
            return cls.fit()
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d["intercept"], d["slope"], d["last_units"],
                   d["last_litres"], d.get("meta"))

    # ---------- fitting ----------
    @classmethod
    def fit(cls, csv_path=TRAINING):
        days = load_fleet_days(csv_path)
        if len(days) < 30:
            raise ValueError(f"need >=30 fleet-days, got {len(days)}")
        xs = [v["units"] for _, v in days]
        ys = [v["litres"] for _, v in days]
        n = len(xs)
        mx, my = st.mean(xs), st.mean(ys)
        var = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
        intercept = my - slope * mx
        return cls(intercept, slope, xs[-1], ys[-1], meta={
            "fitted_on_days": n,
            "date_range": [days[0][0], days[-1][0]],
            "mean_litres_per_day": round(my, 1),
            "mean_active_units": round(mx, 1),
            "contractor": "RIM (only contractor with fuel data)",
            "caveats": [
                "5 months of data; no annual seasonality is learnable",
                "all rows contractor RIM; not site-wide",
                "SUPPORT-dominated activity mix (28,108 vs 2,809 HAULAGE)",
                "litres measure refuel events (~200 L tank fills), not burn",
            ],
        })


def load_fleet_days(csv_path=TRAINING):
    """Aggregate the unit-day training set to fleet-days."""
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} missing — run scripts/fuel_training_set.py "
            "with the VPN up.")
    day = defaultdict(lambda: defaultdict(float))
    with open(csv_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                lit = float(r["litres"])
            except (TypeError, ValueError):
                continue
            if lit <= 0:
                continue
            v = day[r["date"]]
            v["litres"] += lit
            v["units"] += 1
    return sorted(day.items())


def main():
    ap = argparse.ArgumentParser(description="Forecast daily diesel litres.")
    ap.add_argument("--fit", action="store_true",
                    help="refit from training_set.csv and save the model")
    ap.add_argument("--units", type=float, default=None,
                    help="tomorrow's active-unit count, if the roster has it")
    a = ap.parse_args()

    if a.fit:
        fc = DieselForecaster.fit()
        p = fc.save()
        print(f"fitted on {fc.meta['fitted_on_days']} fleet-days "
              f"({fc.meta['date_range'][0]} -> {fc.meta['date_range'][1]})")
        print(f"  litres = {fc.intercept:.1f} + {fc.slope:.2f} * active_units")
        print(f"  saved {p}")
        return

    fc = DieselForecaster.load()
    r = fc.predict(a.units)
    print(f"forecast: {r['litres']:,.0f} L  "
          f"({r['range_low']:,.0f} - {r['range_high']:,.0f} L)")
    print(f"  active units : {r['active_units']:.0f}"
          f"{'  (assumed, no roster)' if r['units_assumed'] else ''}")
    print(f"  basis        : {r['basis']}")
    print(f"  expected MAPE: {r['expected_mape_pct']}%")
    if r.get("stale_warning"):
        print(f"  WARNING      : {r['stale_warning']}")


if __name__ == "__main__":
    main()
