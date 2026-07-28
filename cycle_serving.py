"""Serving layer for the Phase 3.5 cycle-time model.

Kept separate from `cycle_model.py` (which trains) so the API never imports
statsmodels or pandas on the request path.

WHAT THIS SERVES AND WHY
Walk-forward CV said log-OLS beats the per-route lookup on MAE across 5/5 folds
(29.5 vs 37.8 min) but ties it on R² (0.6565 vs 0.6480, below the 0.05 bar).
Neither number alone justifies picking one, so the served rule follows the
evidence rather than a single metric:

  - route known to the model  -> log-OLS, which is better on the ordinary shift
  - route unseen              -> route/global mean, since an OLS route dummy
                                 that was never fitted contributes nothing

Every response says which branch answered and carries the CV numbers for that
branch, so the UI can never show a confidence the prediction did not earn.
"""
from __future__ import annotations

import math
import os
import pickle

BASE = os.path.dirname(os.path.abspath(__file__))
CYCLE_MODEL_PKL = os.path.join(BASE, "data", "cycle_model.pkl")
CYCLE_REPORT = os.path.join(BASE, "data", "cycle_model_report.json")

_CACHE: dict | None = None
_MTIME: float | None = None

DEFAULT_SHIFT_HOURS = 12.0
# Fraction of a rostered shift a truck actually spends on cycles. FITTED by the
# trainer against weighbridge trips on routes both datasets share, not assumed.
#
# This constant used to be 0.85 on a plausible-sounding argument about
# refuelling and handovers. It was wrong by more than 2x: the same API response
# then reported 5,046 t (weighbridge model) and 10,667 t (cycle model) for an
# identical 101-truck fleet. Measured utilisation is ~0.40, which reconciles the
# two to 17.8% median error across 12 routes.
#
# The value below is only the fallback for a pickle trained before calibration
# existed; the served number comes from the bundle.
SHIFT_UTILISATION = 0.40


def load_cycle_model() -> dict | None:
    """Load the pickle, re-reading it when retraining replaces the file."""
    global _CACHE, _MTIME
    try:
        mt = os.path.getmtime(CYCLE_MODEL_PKL)
    except OSError:
        return None
    if _CACHE is None or mt != _MTIME:
        try:
            with open(CYCLE_MODEL_PKL, "rb") as fh:
                _CACHE, _MTIME = pickle.load(fh), mt
        except Exception:                                  # noqa: BLE001
            return None
    return _CACHE


def reset_cycle_model() -> None:
    global _CACHE, _MTIME
    _CACHE, _MTIME = None, None


def _lookup(bundle, source, destination, shift):
    means = bundle.get("route_means") or {}
    for key in ((source, destination, shift), (source, destination, "day")):
        v = means.get(key)
        if v and v > 0:
            return float(v)
    return None


def predict_cycle_time(source: str, destination: str, shift: str = "day",
                       trucks: float = 1.0, rainfall_mm: float = 0.0,
                       distance_km: float | None = None) -> dict | None:
    """Predicted minutes for one full haul cycle on this route.

    Returns None when no cycle model has been trained, so callers can degrade
    to the Phase 2/3 path instead of inventing a number.
    """
    bundle = load_cycle_model()
    if not bundle:
        return None

    shift = "night" if str(shift).lower().startswith("n") else "day"
    route_mean = _lookup(bundle, source, destination, shift)
    gm = float(bundle.get("global_mean") or 0.0)

    params = bundle.get("params") or {}
    route_key = "rt_%s>%s" % (source, destination)
    # An OLS route dummy only exists for routes present at fit time. Without it
    # the linear model would answer with the intercept route, which is a
    # different road, so the lookup is the honest answer instead.
    known_route = route_key in params

    if known_route and params:
        x = {
            "trucks_dt": float(trucks),
            "rainfall_mm": float(rainfall_mm),
            "is_wet": 1.0 if float(rainfall_mm) > 5 else 0.0,
            "is_night": 1.0 if shift == "night" else 0.0,
            route_key: 1.0,
        }
        raw = float(params.get("const", 0.0))
        for name, coef in params.items():
            if name != "const" and name in x:
                raw += float(coef) * x[name]
        # Trust the recorded scale rather than inferring it. The trainer fits
        # coefficients on raw minutes for interpretation and on log minutes for
        # serving; exponentiating the wrong one silently returns e^68 minutes.
        if bundle.get("param_scale") == "log_minutes":
            smear = float(bundle.get("smearing_factor") or 1.0)
            # Duan's smearing: exp(E[log y]) is the geometric mean and is biased
            # low for the arithmetic mean we are asked to predict.
            minutes = math.exp(raw) * smear if -20 < raw < 20 else None
        else:
            minutes = raw
        basis = bundle.get("winner") or "ols"
        if not minutes or not (5 <= minutes <= 900):
            minutes, basis = route_mean or gm, "route_mean_fallback"
    else:
        minutes, basis = (route_mean or gm), (
            "route_mean" if route_mean else "global_mean")

    if not minutes or minutes <= 0:
        return None

    model_answered = basis == (bundle.get("winner") or "ols")
    return {
        "cycle_time_min": round(float(minutes), 1),
        "basis": basis,
        "route_known": bool(known_route or route_mean),
        # The CV numbers belong to the branch that answered. A lookup answer
        # must not borrow the OLS score, so the baseline's own CV metrics are
        # returned instead — read from the bundle, never hardcoded, or they
        # would drift silently the next time the model is retrained.
        "cv_r2": (bundle.get("cv_r2") if model_answered
                  else bundle.get("baseline_cv_r2")),
        "cv_mae_min": (bundle.get("cv_mae_min") if model_answered
                       else bundle.get("baseline_cv_mae_min")),
        "verdict": bundle.get("verdict"),
    }


def fitted_utilisation(default: float = SHIFT_UTILISATION) -> float:
    """Utilisation from the trained bundle, falling back to the constant."""
    b = load_cycle_model() or {}
    u = (b.get("utilisation") or {}).get("utilisation")
    return float(u) if u and 0.05 < u < 1.0 else default


def cycle_to_tonnage(cycle_min: float, trucks: float, payload_t: float,
                     shift_hours: float = DEFAULT_SHIFT_HOURS,
                     utilisation: float | None = None) -> dict:
    """Convert a cycle time into a shift plan.

        trips per truck = (shift minutes * utilisation) / cycle minutes

    This is arithmetic, not a second model, which is the point of predicting
    cycle time: the tonnage follows from a physical quantity instead of being
    fitted directly.
    """
    if not cycle_min or cycle_min <= 0:
        return {}
    utilisation = fitted_utilisation() if utilisation is None else utilisation
    eff_min = float(shift_hours) * 60.0 * float(utilisation)
    trips_per_truck = eff_min / float(cycle_min)
    total_trips = trips_per_truck * float(trucks)
    return {
        "trips_per_dt": round(trips_per_truck, 3),
        "total_trips": int(round(total_trips)),
        "total_wmt": int(round(total_trips * float(payload_t))),
        "effective_minutes": round(eff_min, 1),
        "utilisation_assumed": utilisation,
    }


def trucks_for_target(cycle_min: float, target_wmt: float, payload_t: float,
                      shift_hours: float = DEFAULT_SHIFT_HOURS,
                      utilisation: float | None = None) -> int | None:
    """Fleet size for a tonnage target — closed form, no fixed-point loop
    needed, because trips scale linearly in truck count once cycle time is
    known."""
    if not (cycle_min and payload_t and target_wmt > 0):
        return None
    utilisation = fitted_utilisation() if utilisation is None else utilisation
    per_truck = (float(shift_hours) * 60.0 * float(utilisation) / float(cycle_min)) * float(payload_t)
    return max(1, math.ceil(float(target_wmt) / per_truck)) if per_truck > 0 else None
