"""Unit tests for Phase 5: dispatch engine and rules engine.

Tests the INVARIANTS, not the fitted numbers, which move when data refreshes.

The invariants matter because a dispatch simulation is easy to make look good:
inventing trucks, moving them to faces that were not running, or optimising the
metric while making the operation worse would all produce a flattering table.
Each of those is checked here.

    python tests/test_phase5.py
"""
from __future__ import annotations

import copy
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dynamic_dispatch as dd  # noqa: E402
import rules_engine as re_     # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        FAILURES.append(name)
        print("  FAIL  %s %s" % (name, detail))


def _shift(n_points=5, seed=1):
    """One shift with a deliberate imbalance: some points starved, one flooded."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_points):
        servers = 2 + i % 3
        # first point deliberately over-trucked, rest starved
        trucks = 60 if i == 0 else 4 + i
        rows.append({"loading_point": "P%d" % i, "shift": "day",
                     "date": "2026-05-01", "n_trucks": trucks,
                     "servers_observed": servers,
                     "avg_service_time_min": 12.0 + rng.normal(0, 1),
                     "avg_cycle_time_min": 90.0 + rng.normal(0, 5),
                     "status": "under-trucked"})
    return pd.DataFrame(rows)


# ── dispatch ───────────────────────────────────────────────────────────────
def test_conservation():
    """Dispatch reallocates trucks. It must never create or destroy them."""
    g = _shift()
    before = g["n_trucks"].sum()
    moves, after = dd.balance_shift(g)
    check("truck count conserved", abs(after["n_now"].sum() - before) < 1e-9,
          (before, after["n_now"].sum()))
    check("some moves were made on an imbalanced shift", len(moves) > 0, len(moves))


def test_moves_have_correct_direction():
    """Every move must take from above the band and give to below it, and must
    not push either side out of the band. Otherwise the fix just relocates the
    problem."""
    moves, _ = dd.balance_shift(_shift())
    if not moves:
        check("moves exist to test direction", False)
        return
    check("donor above target band",
          all(m["mf_from_before"] > dd.TARGET_HI for m in moves))
    check("receiver below target band",
          all(m["mf_to_before"] < dd.TARGET_LO for m in moves))
    check("donor not pushed below band",
          all(m["mf_from_after"] >= dd.TARGET_LO for m in moves))
    check("receiver not pushed above band",
          all(m["mf_to_after"] <= dd.OVER_TRUCKED for m in moves))


def test_balanced_shift_is_left_alone():
    """A shift already inside the band must not be churned."""
    g = _shift()
    # tune every point to sit near MF 0.95
    for i in g.index:
        tc, ts, sv = g.at[i, "avg_cycle_time_min"], g.at[i, "avg_service_time_min"], g.at[i, "servers_observed"]
        g.at[i, "n_trucks"] = max(1, round(0.95 * tc / ts * sv))
    moves, _ = dd.balance_shift(g)
    check("no churn on an already-balanced shift", len(moves) == 0, len(moves))


def test_move_cap_respected():
    g = _shift()
    cap = int(np.floor(g["n_trucks"].sum() * dd.MAX_MOVES_FRACTION))
    moves, _ = dd.balance_shift(g)
    check("moves within the 30%% cap", len(moves) <= cap, (len(moves), cap))


def test_forward_allocates_everything():
    """Mode B must place exactly the trucks asked for, and never invent a point."""
    mf = dd.load_inputs() if os.path.exists(dd.MF_CSV) else None
    if mf is None:
        print("  SKIP  no match factor results")
        return
    pts = list(mf["loading_point"].dropna().unique()[:3])
    out = dd.forward({"trucks": 37, "loading_points": pts, "shift": "day"}, mf)
    check("forward succeeded", out.get("ok") is True, out.get("error"))
    check("all trucks allocated", out.get("trucks_assigned") == 37,
          out.get("trucks_assigned"))
    check("no negative allocations",
          all(a["trucks_assigned"] >= 0 for a in out.get("assignments", [])))
    bad = dd.forward({"trucks": 10, "loading_points": ["NO_SUCH_POINT"]}, mf)
    check("unknown point reported, not invented", bad.get("ok") is False
          or "NO_SUCH_POINT" in bad.get("unknown_points", []), bad)


def test_replay_results_if_present():
    df = dd.load_replay()
    if df is None or df.empty:
        print("  SKIP  no replay results")
        return
    check("rebalanceable shifts never lose balanced points",
          (df[df["rebalanceable"]]["after_balanced"]
           >= df[df["rebalanceable"]]["before_balanced"]).all())
    fl = df[~df["rebalanceable"]]
    check("fleet-limited shifts are reported separately", len(fl) > 0, len(fl))


# ── rules ──────────────────────────────────────────────────────────────────
def test_rule_validation_rejects_bad_rules():
    cases = [
        ({"id": "X", "name": "n", "when": {"metric": "match_facter", "operator": "<",
          "threshold": 1}, "then": {"severity": "high", "message": "m"}}, "typo metric"),
        ({"id": "X", "name": "n", "when": {"metric": "match_factor", "operator": "=<",
          "threshold": 1}, "then": {"severity": "high", "message": "m"}}, "bad operator"),
        ({"id": "X", "name": "n", "when": {"metric": "match_factor", "operator": "<",
          "threshold": "abc"}, "then": {"severity": "high", "message": "m"}}, "bad threshold"),
        ({"id": "X", "name": "n", "when": {"metric": "match_factor", "operator": "<",
          "threshold": 1}, "then": {"severity": "urgent", "message": "m"}}, "bad severity"),
        ({}, "empty rule"),
    ]
    for rule, label in cases:
        check("rejects %s" % label, bool(re_.validate_rule(rule)))
    good = {"id": "T", "name": "ok", "when": {"metric": "match_factor",
            "operator": "<", "threshold": 0.5, "duration": "2 consecutive shifts"},
            "then": {"severity": "high", "message": "{loading_point}"}}
    check("accepts a valid rule", not re_.validate_rule(good), re_.validate_rule(good))


def test_duration_filters_monotonically():
    """A longer required run must never produce MORE alerts. This is what stops
    an alert being a constant."""
    try:
        df = pd.read_csv(os.path.join(dd.DATA, "match_factor_results.csv"))
    except Exception:                                       # noqa: BLE001
        print("  SKIP  no match factor results")
        return
    counts = []
    for n in (1, 2, 5, 10):
        cfg = {"rules": [{"id": "T", "name": "t", "enabled": True,
                          "when": {"metric": "match_factor", "operator": "<",
                                   "threshold": 0.75,
                                   "duration": "%d consecutive shifts" % n},
                          "then": {"severity": "high", "message": "x"}}]}
        counts.append(re_.evaluate(df=df, rules=cfg)["alert_count"])
    check("alert count falls as duration rises",
          all(a >= b for a, b in zip(counts, counts[1:])), counts)
    check("duration actually filters", counts[0] > counts[-1], counts)


def test_disabled_rules_never_fire():
    try:
        df = pd.read_csv(os.path.join(dd.DATA, "match_factor_results.csv"))
    except Exception:                                       # noqa: BLE001
        print("  SKIP  no match factor results")
        return
    cfg = copy.deepcopy(re_.load_rules())
    for r in cfg.get("rules", []):
        r["enabled"] = False
    ev = re_.evaluate(df=df, rules=cfg)
    check("disabled rules produce no alerts", ev["alert_count"] == 0, ev["alert_count"])
    check("disabled rules are not evaluated", ev["rules_evaluated"] == 0)


def test_parse_duration():
    for text, want in (("1 shift", 1), ("2 consecutive shifts", 2),
                       ("5 shifts", 5), ("1 day", 1), ("", 1), (None, 1),
                       ("garbage", 1)):
        check("parse_duration(%r) == %d" % (text, want),
              re_.parse_duration(text) == want, re_.parse_duration(text))


def test_shipped_rules_are_valid():
    cfg = re_.load_rules()
    check("rules.json has rules", len(cfg.get("rules", [])) >= 3)
    for r in cfg.get("rules", []):
        check("shipped rule %s is valid" % r.get("id"), not re_.validate_rule(r),
              re_.validate_rule(r))


if __name__ == "__main__":
    for fn in (test_conservation, test_moves_have_correct_direction,
               test_balanced_shift_is_left_alone, test_move_cap_respected,
               test_forward_allocates_everything, test_replay_results_if_present,
               test_rule_validation_rejects_bad_rules,
               test_duration_filters_monotonically,
               test_disabled_rules_never_fire, test_parse_duration,
               test_shipped_rules_are_valid):
        print("\n%s" % fn.__name__)
        fn()
    print("\n%s" % ("-" * 60))
    if FAILURES:
        print("FAILED %d: %s" % (len(FAILURES), ", ".join(FAILURES)))
        raise SystemExit(1)
    print("all phase 5 tests passed")
