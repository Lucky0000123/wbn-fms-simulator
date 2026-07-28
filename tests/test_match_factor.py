"""Unit tests for the Match Factor calculator (Phase 4, Tier 3 Module 1).

Tests the ARITHMETIC, the BANDS and the VALIDATION GATE, not the fitted
numbers, which move whenever the data is refreshed.

The gate is the important one. Two earlier formulations of MF produced
plausible-looking tables that were measuring the wrong thing (one was circular,
one lost resolution in a cross-table join), and both were caught only by
checking the sign against queue wait. That check is now code, so a future
change that breaks the relationship cannot ship quietly.

    python tests/test_match_factor.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import match_factor as mf  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        FAILURES.append(name)
        print("  FAIL  %s %s" % (name, detail))


def _synthetic(n_points=40, per=60, seed=7):
    """A yard where queueing is real and known by construction.

    Each point has a fleet and a number of loading bays. Trucks cycle round, so
    a point with many trucks per bay genuinely queues: wait time is derived from
    trucks-per-bay, while haul time is held constant so it cannot confound the
    relationship. A correct MF must come out positively correlated with queue
    share; a circular or inverted implementation fails here.

    Truck arrivals are kept non-overlapping per truck, because one truck cannot
    be loading in two bays at once and the sweep must not be fed impossible
    data.
    """
    rng = np.random.default_rng(seed)
    rows = []
    day = pd.Timestamp("2026-05-01")
    for p in range(n_points):
        bays = 1 + (p % 5)                      # 1..5 loading bays
        fleet = 4 + (p % 9) * 3                 # 4..28 trucks
        pressure = fleet / bays                 # the thing MF should detect
        wait = 2.0 + 3.0 * pressure             # queue grows with pressure
        service = 12.0                          # constant service time
        next_free = {t: day + pd.Timedelta(hours=6) for t in range(fleet)}
        for i in range(per):
            t = i % fleet
            arrive = next_free[t] + pd.Timedelta(
                minutes=float(rng.uniform(0.5, 3.0)))
            load = wait + service + float(rng.normal(0, 1.5))
            load = max(2.0, load)
            haul, dump = 40.0, 6.0
            rows.append({"loading_point": "P%d" % p, "destination": "D",
                         "shift": "day", "date": day.date(),
                         "truck_id": "T%d-%d" % (p, t),
                         "arrive": arrive, "load_min": load,
                         "haul_min": haul, "dump_min": dump})
            next_free[t] = arrive + pd.Timedelta(minutes=load + haul + dump)
    w = pd.DataFrame(rows)
    w["cycle_min"] = w[["load_min", "haul_min", "dump_min"]].sum(axis=1)
    w["depart"] = w["arrive"] + pd.to_timedelta(w["load_min"], unit="m")
    return w


def test_formula_arithmetic():
    """MF = (trucks/servers) x Ts / Tc, computed by hand."""
    w = _synthetic(n_points=1, per=30)
    m = mf.compute(w)
    check("compute returns rows", len(m) == 1, len(m))
    r = m.iloc[0]
    expect = (r["n_trucks"] / max(r["servers_observed"], 1)) \
        * r["avg_service_time_min"] / r["avg_cycle_time_min"]
    check("match_factor matches the formula",
          abs(r["match_factor"] - expect) < 1e-3, (r["match_factor"], expect))
    check("servers_observed >= 1", r["servers_observed"] >= 1, r["servers_observed"])
    check("servers never exceeds trucks",
          r["servers_observed"] <= r["n_trucks"],
          (r["servers_observed"], r["n_trucks"]))


def test_bands_match_burt_caccetta():
    m = pd.DataFrame({
        "match_factor": [0.5, 0.8, 0.9, 1.0, 1.2, 3.0],
        "avg_queue_wait_min": [5, 10, 15, 20, 30, 40],
        "avg_cycle_time_min": [100] * 6,
        "queue_share": [.05, .10, .15, .20, .30, .40],
    })
    st = np.select([m["match_factor"] > mf.OVER_TRUCKED,
                    m["match_factor"] < mf.UNDER_TRUCKED],
                   ["over-trucked", "under-trucked"], default="balanced")
    check("0.5 is under-trucked", st[0] == "under-trucked", st[0])
    check("0.9 is balanced", st[2] == "balanced", st[2])
    check("1.2 is over-trucked", st[4] == "over-trucked", st[4])
    check("target band is 0.85-1.0",
          (mf.TARGET_LO, mf.TARGET_HI) == (0.85, 1.00))


def test_validation_gate_accepts_real_queueing():
    """On data where queueing is real by construction, the gate must pass."""
    m = mf.compute(_synthetic())
    v = mf.validate(m)
    check("gate passes on synthetic queueing", v["passes"] is True,
          v["corr_mf_queue_share"])
    check("correlation is positive",
          (v["corr_mf_queue_share"] or 0) > 0.30, v["corr_mf_queue_share"])


def test_validation_gate_rejects_noise():
    """The gate must FAIL when MF carries no queue signal. A gate that cannot
    fail is decoration."""
    rng = np.random.default_rng(3)
    n = 300
    m = pd.DataFrame({
        "match_factor": rng.uniform(0.2, 2.0, n),
        "queue_share": rng.uniform(0.05, 0.6, n),     # independent of MF
        "avg_queue_wait_min": rng.uniform(5, 40, n),
        "avg_cycle_time_min": rng.uniform(40, 200, n),
    })
    v = mf.validate(m)
    check("gate REJECTS a random MF", v["passes"] is False, v["corr_mf_queue_share"])


def test_bunching_threshold_is_data_derived():
    """The briefed CV>0.5 fires on ~99% of real point-shifts, so the threshold
    comes from the observed distribution instead."""
    m = mf.compute(_synthetic())
    thr = m.attrs.get("bunching_threshold")
    check("threshold recorded", thr is not None, thr)
    flagged = float(m["bunching_flag"].mean())
    check("threshold flags a minority, not everything", 0.0 <= flagged <= 0.5,
          flagged)
    check("briefed value kept for reference", mf.BUNCHING_CV_BRIEFED == 0.5)


def test_real_results_if_present():
    """If a real run exists, its shipped numbers must satisfy the same gate."""
    d = mf.load_results()
    if d is None or not len(d):
        print("  SKIP  no match_factor_results.csv (needs VPN once)")
        return
    check("real rows present", len(d) > 100, len(d))
    check("status values are the three bands",
          set(d["status"]) <= {"balanced", "over-trucked", "under-trucked"},
          set(d["status"]))
    check("no negative match factors", (d["match_factor"] >= 0).all())
    check("servers >= 1 everywhere", (d["servers_observed"] >= 1).all())
    v = mf.validate(d)
    check("shipped results pass the queue gate", v["passes"] is True,
          v["corr_mf_queue_share"])


if __name__ == "__main__":
    for fn in (test_formula_arithmetic, test_bands_match_burt_caccetta,
               test_validation_gate_accepts_real_queueing,
               test_validation_gate_rejects_noise,
               test_bunching_threshold_is_data_derived,
               test_real_results_if_present):
        print("\n%s" % fn.__name__)
        fn()
    print("\n%s" % ("-" * 60))
    if FAILURES:
        print("FAILED %d: %s" % (len(FAILURES), ", ".join(FAILURES)))
        raise SystemExit(1)
    print("all match factor tests passed")
