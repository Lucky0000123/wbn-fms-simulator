"""Unit tests for the Phase 3.5 cycle maths.

These test the ARITHMETIC and the GUARDS, not the fitted coefficients. Model
quality is judged by walk-forward CV in `cycle_model.py` and gated by I34-I40;
duplicating that here would just re-assert numbers that are allowed to move
when the model is retrained.

What is worth pinning down is the layer between the model and the user, because
that is where this phase's real bugs were: a scale mismatch that would have
served exp(67.9) minutes, and a guessed utilisation constant that made the same
API response report 5,046 t and 10,667 t for one fleet. Both were arithmetic
and both were invisible until someone compared two numbers.

    python -m pytest tests/test_cycle.py -q     (or: python tests/test_cycle.py)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cycle_serving as cs  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        FAILURES.append(name)
        print("  FAIL  %s %s" % (name, detail))


def test_tonnage_arithmetic():
    """trips = shift_minutes x utilisation / cycle_minutes, per truck."""
    # 600 rostered minutes, half productive, 60-minute cycle -> 5 trips/truck.
    r = cs.cycle_to_tonnage(60, trucks=10, payload_t=20,
                            shift_hours=10, utilisation=0.5)
    check("5 trips/truck from a 60-min cycle", r["trips_per_dt"] == 5.0, r)
    check("50 total trips for 10 trucks", r["total_trips"] == 50, r)
    check("1,000 t at 20 t/trip", r["total_wmt"] == 1000, r)
    check("utilisation echoed back", r["utilisation_assumed"] == 0.5, r)


def test_tonnage_scales_correctly():
    """Doubling the fleet doubles tonnage; doubling cycle time halves it."""
    a = cs.cycle_to_tonnage(100, 10, 25, utilisation=0.4)
    b = cs.cycle_to_tonnage(100, 20, 25, utilisation=0.4)
    c = cs.cycle_to_tonnage(200, 10, 25, utilisation=0.4)
    check("2x trucks -> 2x tonnage", b["total_wmt"] == 2 * a["total_wmt"],
          (a["total_wmt"], b["total_wmt"]))
    check("2x cycle time -> half tonnage",
          abs(c["total_wmt"] - a["total_wmt"] / 2) <= 1,
          (a["total_wmt"], c["total_wmt"]))


def test_reverse_is_inverse_of_forward():
    """Sizing a fleet for a target, then computing that fleet's output, must
    land back on the target. These are the two directions the planner offers,
    and they must not disagree."""
    for cycle, payload, target in ((120, 25, 5000), (280, 48.6, 5000),
                                   (60, 30, 900), (400, 20, 12000)):
        n = cs.trucks_for_target(cycle, target, payload, utilisation=0.4)
        got = cs.cycle_to_tonnage(cycle, n, payload, utilisation=0.4)["total_wmt"]
        # Rounds UP (you cannot run a fraction of a truck), so it may overshoot
        # by up to one truck's contribution, but must never undershoot.
        per_truck = got / n
        check("reverse->forward hits target (cycle=%s, target=%s)" % (cycle, target),
              target <= got < target + per_truck + 1,
              "sized %d trucks -> %d t for target %d" % (n, got, target))


def test_zero_and_negative_inputs_do_not_explode():
    """Bad input should return nothing, not a divide-by-zero or a huge number."""
    check("zero cycle time -> empty", cs.cycle_to_tonnage(0, 10, 25) == {})
    check("negative cycle time -> empty", cs.cycle_to_tonnage(-5, 10, 25) == {})
    check("zero target -> None", cs.trucks_for_target(100, 0, 25) is None)
    check("zero payload -> None", cs.trucks_for_target(100, 5000, 0) is None)
    check("at least one truck for a tiny target",
          cs.trucks_for_target(100, 0.001, 25) == 1)


def test_utilisation_is_fitted_not_guessed():
    """The constant that caused a 2x contradiction. It must come from the
    trained bundle and sit in a physically plausible range."""
    u = cs.fitted_utilisation()
    check("utilisation in (0.1, 0.9)", 0.1 < u < 0.9, u)
    check("utilisation is not the old guessed 0.85", abs(u - 0.85) > 0.05, u)
    b = cs.load_cycle_model()
    if b:
        info = b.get("utilisation") or {}
        check("bundle records how utilisation was derived",
              info.get("basis", "").startswith("fitted"), info.get("basis"))
        check("utilisation fitted on >= 5 routes", info.get("routes", 0) >= 5,
              info.get("routes"))


def test_prediction_is_physical():
    """A cycle time must be a plausible number of minutes, and the model must
    respond to conditions in the right direction."""
    b = cs.load_cycle_model()
    if not b:
        print("  SKIP  no trained cycle model (needs VPN once)")
        return
    dry = cs.predict_cycle_time("TF", "FENI KM0", "day", trucks=30, rainfall_mm=0)
    wet = cs.predict_cycle_time("TF", "FENI KM0", "day", trucks=30, rainfall_mm=40)
    night = cs.predict_cycle_time("TF", "FENI KM0", "night", trucks=30, rainfall_mm=0)
    check("cycle time is plausible", 5 < dry["cycle_time_min"] < 900, dry)
    check("rain slows trucks", wet["cycle_time_min"] > dry["cycle_time_min"],
          (dry["cycle_time_min"], wet["cycle_time_min"]))
    # Registered as +1 on visibility, measured at -3.24 min. The data won, and
    # the test encodes the measurement rather than the original guess.
    check("night is faster (measured, contradicts the naive prior)",
          night["cycle_time_min"] < dry["cycle_time_min"],
          (dry["cycle_time_min"], night["cycle_time_min"]))


def test_unknown_route_falls_back_honestly():
    """An unseen route must not borrow the model's accuracy."""
    if not cs.load_cycle_model():
        print("  SKIP  no trained cycle model")
        return
    r = cs.predict_cycle_time("NOWHERE", "NOPLACE", "day", trucks=30)
    check("unknown route still answers", r is not None)
    check("unknown route uses a lookup basis",
          r["basis"] in ("route_mean", "global_mean"), r["basis"])
    known = cs.predict_cycle_time("TF", "FENI KM0", "day", trucks=30)
    check("fallback quotes a DIFFERENT accuracy than the model",
          r["cv_mae_min"] != known["cv_mae_min"],
          (r["cv_mae_min"], known["cv_mae_min"]))


def test_served_scale_matches_recorded_scale():
    """The bug that would have served exp(67.9) minutes."""
    b = cs.load_cycle_model()
    if not b:
        print("  SKIP  no trained cycle model")
        return
    const = float(b["params"]["const"])
    if b.get("param_scale") == "log_minutes":
        check("log-scale intercept is a log, not raw minutes",
              2.0 < const < 8.0, const)
        check("exponentiating it gives a real cycle time",
              10 < math.exp(const) < 600, math.exp(const))
    else:
        check("raw-minute intercept is plausible", 10 < const < 600, const)


if __name__ == "__main__":
    for fn in (test_tonnage_arithmetic, test_tonnage_scales_correctly,
               test_reverse_is_inverse_of_forward,
               test_zero_and_negative_inputs_do_not_explode,
               test_utilisation_is_fitted_not_guessed,
               test_prediction_is_physical,
               test_unknown_route_falls_back_honestly,
               test_served_scale_matches_recorded_scale):
        print("\n%s" % fn.__name__)
        fn()
    print("\n%s" % ("-" * 60))
    if FAILURES:
        print("FAILED %d: %s" % (len(FAILURES), ", ".join(FAILURES)))
        raise SystemExit(1)
    print("all cycle unit tests passed")
