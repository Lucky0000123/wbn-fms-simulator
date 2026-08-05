#!/usr/bin/env python3
"""Tests for the diesel forecaster. Run: ./.venv/bin/python -m pytest scripts/test_fuel_forecast.py -q"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fuel_forecast import DieselForecaster, load_fleet_days  # noqa: E402


@pytest.fixture(scope="module")
def fc():
    return DieselForecaster.fit()


def test_fits_on_real_data(fc):
    assert fc.meta["fitted_on_days"] == 139
    assert fc.meta["date_range"] == ["2026-02-22", "2026-07-22"]


def test_coefficients_match_report(fc):
    # Report §12.3: litres = -3928 + 270.4 * active_units
    assert fc.intercept == pytest.approx(-3928, abs=60)
    assert fc.slope == pytest.approx(270.4, abs=1.0)


def test_predict_with_roster(fc):
    r = fc.predict(active_units=230)
    assert r["units_assumed"] is False
    assert r["expected_mape_pct"] == 3.5
    # ~252 L per active unit-day => a plausible fleet day
    assert 45_000 < r["litres"] < 70_000
    assert r["range_low"] < r["litres"] < r["range_high"]


def test_predict_autonomous(fc):
    r = fc.predict()
    assert r["units_assumed"] is True
    assert r["expected_mape_pct"] == 13.0
    # wider band when the unit count is guessed
    assert r["range_high"] - r["range_low"] > 10_000


def test_refuses_to_extrapolate(fc):
    """The model is linear; extrapolation is the classic way to ship nonsense."""
    for bad in (0, 10, 500, 5000):
        with pytest.raises(ValueError, match="outside observed range"):
            fc.predict(active_units=bad)


def test_monotonic_in_units(fc):
    a = fc.predict(active_units=150)["litres"]
    b = fc.predict(active_units=250)["litres"]
    assert b > a, "more active units must mean more diesel"


def test_roundtrip(tmp_path, fc):
    p = tmp_path / "m.json"
    fc.save(p)
    got = DieselForecaster.load(p)
    assert got.predict(220)["litres"] == fc.predict(220)["litres"]


def test_load_falls_back_to_fit(tmp_path):
    """A missing model file must not explode; refit instead."""
    got = DieselForecaster.load(tmp_path / "absent.json")
    assert got.meta["fitted_on_days"] == 139


def test_fleet_days_are_clean():
    days = load_fleet_days()
    assert len(days) == 139
    assert all(v["litres"] > 0 and v["units"] > 0 for _, v in days)
    assert days == sorted(days), "days must be chronological"


def test_beats_naive_baseline(fc):
    """The whole point: a real holdout gain over predicting the mean."""
    import statistics as st
    days = load_fleet_days()
    cut = int(.8 * len(days))
    tr, te = days[:cut], days[cut:]
    mean_l = st.mean(v["litres"] for _, v in tr)
    naive = st.mean(abs(mean_l - v["litres"]) / v["litres"] for _, v in te)
    model = st.mean(
        abs(fc.intercept + fc.slope * v["units"] - v["litres"]) / v["litres"]
        for _, v in te)
    assert model < naive / 2, f"model {model:.3f} vs naive {naive:.3f}"
    assert model < 0.06, f"expected ~3.5% MAPE, got {100*model:.1f}%"


def test_reports_training_data_age(fc):
    """A forecast from stale data must say so, not look fresh (report §15.3)."""
    r = fc.predict(230)
    assert isinstance(r["training_data_age_days"], int)
    assert r["training_data_age_days"] >= 14  # feed stopped 2026-07-22


def test_stale_warning_fires_and_degrades():
    from fuel_forecast import DieselForecaster
    f = DieselForecaster.fit()
    f.meta["date_range"] = ["2026-02-22", "2026-01-01"]
    assert "verify the WAITING_TIME feed" in f.predict(230)["stale_warning"]
    f.meta.pop("date_range")
    assert f.predict(230)["stale_warning"] is None  # missing meta must not crash
