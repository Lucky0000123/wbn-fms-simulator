"""Layer 2A - M/M/c loader queue (Erlang-C).

Trucks arrive at the loading point at rate lambda; c loaders each serve at
rate mu. Erlang-C gives the mean queue wait Wq. This produces the nonlinear
diminishing-returns knee the divide-by-max model could not express, and it
responds to loader count - double the loaders and the queue clears.
"""
from __future__ import annotations

import math


def erlang_c(n_trucks: float, cycle_h: float, load_min: float, c_loaders: int,
             shift_hours: float = 12.0) -> dict:
    """Mean loader-queue wait for a closed fleet approximated as M/M/c.

    lambda = N / cycle_h  (each truck returns once per cycle)
    mu     = 60 / load_min per loader
    Returns wq_min (mean wait per arrival), rho, lq, overloaded flag.
    rho >= 1: the queue is unstable; wq is capped at half the shift and the
    route is flagged - never silently infinite.
    """
    if n_trucks <= 0 or c_loaders <= 0 or load_min <= 0 or cycle_h <= 0:
        return {"wq_min": 0.0, "rho": 0.0, "lq": 0.0, "overloaded": False,
                "lambda_hr": 0.0, "mu_hr": 0.0, "c": max(0, int(c_loaders))}
    lam = float(n_trucks) / float(cycle_h)          # arrivals/hr
    mu = 60.0 / float(load_min)                     # services/hr per loader
    c = max(1, int(c_loaders))
    r = lam / mu                                    # offered load (erlangs)
    rho = r / c
    cap_wq_min = shift_hours * 60.0 * 0.5
    if rho >= 1.0:
        return {"wq_min": cap_wq_min, "rho": rho, "lq": float("nan"),
                "overloaded": True, "lambda_hr": lam, "mu_hr": mu, "c": c}
    # Erlang-C P(wait) via stable summation
    s = 0.0
    term = 1.0
    for n in range(c):
        if n > 0:
            term *= r / n
        s += term
    term_c = term * r / c                            # r^c / c!
    p0_inv = s + term_c / (1.0 - rho)
    if p0_inv <= 0 or not math.isfinite(p0_inv):
        return {"wq_min": cap_wq_min, "rho": rho, "lq": float("nan"),
                "overloaded": True, "lambda_hr": lam, "mu_hr": mu, "c": c}
    p_wait = (term_c / (1.0 - rho)) / p0_inv
    lq = p_wait * rho / (1.0 - rho)
    wq_h = lq / lam if lam > 0 else 0.0
    wq_min = min(cap_wq_min, wq_h * 60.0)
    return {"wq_min": wq_min, "rho": rho, "lq": lq, "overloaded": False,
            "lambda_hr": lam, "mu_hr": mu, "c": c, "p_wait": p_wait}


def solve_cycle_with_queue(t_free_min: float, load_min: float, n_trucks: float,
                           c_loaders: int, shift_hours: float = 12.0,
                           iters: int = 40) -> dict:
    """Fixed point: cycle depends on queue wait, queue wait on cycle.

    cycle = t_free + Wq(cycle). Damped iteration from the free-flow cycle;
    converges because Wq falls as cycle grows (fewer arrivals/hr).
    """
    cyc = max(1.0, float(t_free_min))
    out = None
    for _ in range(iters):
        out = erlang_c(n_trucks, cyc / 60.0, load_min, c_loaders, shift_hours)
        nxt = t_free_min + out["wq_min"]
        if abs(nxt - cyc) < 0.05:
            cyc = nxt
            break
        cyc = cyc + 0.5 * (nxt - cyc)
    out = erlang_c(n_trucks, cyc / 60.0, load_min, c_loaders, shift_hours)
    return {"cycle_min": t_free_min + out["wq_min"], **out}
