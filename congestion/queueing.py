"""Layer 2A - M/M/c loader queue (Erlang-C).

Trucks arrive at the loading point at rate lambda; c loaders each serve at
rate mu. Erlang-C gives the mean queue wait Wq. This produces the nonlinear
diminishing-returns knee the divide-by-max model could not express, and it
responds to loader count - double the loaders and the queue clears.
"""
from __future__ import annotations

import math


def machine_repair(n_trucks: float, cycle_h: float, load_min: float,
                   c_loaders: int, shift_hours: float = 12.0) -> dict:
    """Exact finite-source M/M/c//N ("machine repair") loader queue.

    The fleet is CLOSED: N trucks circulate, each spends an exponential
    'travel' phase with mean = cycle minus load, then joins the c-loader
    station. Exact steady state via the birth-death recursion
        p_n ∝ p_{n-1} * (N-n+1)*lam / (min(n,c)*mu),
    lam = 1/travel_min per truck, mu = 1/load_min per loader.

    Why this replaces open Erlang-C (2026-08-26 literature audit,
    reports/survey_queueing.md — Koenigsberg 1958, Carmichael 1986,
    Kappas & Yegulalp 1991, Ta et al. 2013): with lambda = N/cycle an open
    queue admits arrivals from outside the fleet, so at match factor
    >= ~0.8 it overestimates waits 4-9x, and at rho >= 1 it needs an
    arbitrary half-shift cap because the open system diverges. The closed
    system NEVER diverges — when demand outruns the loaders the trucks
    simply wait and throughput plateaus at c*mu — so there is no cap and
    no `overloaded` cliff here. At our production operating point
    (MF <= 0.24) the two agree within 2%; the swap removes the cliff, not
    today's numbers.

    Returns the same shape erlang_c does so callers can switch without
    ceremony. rho is offered load per loader (open-form definition kept
    for continuity of dashboards); `overloaded` means the loaders are the
    binding resource (throughput within 2% of the c*mu plateau), not
    instability.
    """
    if n_trucks <= 0 or c_loaders <= 0 or load_min <= 0 or cycle_h <= 0:
        return {"wq_min": 0.0, "rho": 0.0, "lq": 0.0, "overloaded": False,
                "lambda_hr": 0.0, "mu_hr": 0.0, "c": max(0, int(c_loaders))}
    N = max(1, int(round(n_trucks)))
    c = max(1, int(c_loaders))
    travel_min = max(1.0, cycle_h * 60.0 - float(load_min))
    lam = 1.0 / travel_min                    # per-truck arrival rate (1/min)
    mu = 1.0 / float(load_min)                # per-loader service rate (1/min)
    # Log-space recursion: p_n/p_0 products overflow float at large N*lam/mu.
    logs = [0.0]
    for n in range(1, N + 1):
        logs.append(logs[-1] + math.log((N - n + 1) * lam)
                    - math.log(min(n, c) * mu))
    m = max(logs)
    weights = [math.exp(x - m) for x in logs]
    z = sum(weights)
    p = [w / z for w in weights]
    l_station = sum(n * p[n] for n in range(N + 1))      # mean trucks at loaders
    thr = sum(min(n, c) * mu * p[n] for n in range(N + 1))  # trucks served/min
    if thr <= 0:
        return {"wq_min": 0.0, "rho": 0.0, "lq": 0.0, "overloaded": False,
                "lambda_hr": 0.0, "mu_hr": mu * 60.0, "c": c}
    w_station = l_station / thr                          # Little's law (min)
    wq_min = max(0.0, w_station - float(load_min))
    lq = max(0.0, l_station - sum(min(n, c) * p[n] for n in range(N + 1)))
    rho_open = (N / (cycle_h * 60.0)) / (c * mu)         # continuity metric
    plateau = c * mu                                     # max service rate
    loader_bound = thr >= plateau * 0.98
    return {"wq_min": wq_min, "rho": rho_open, "lq": lq,
            "overloaded": loader_bound,
            "lambda_hr": N / cycle_h, "mu_hr": mu * 60.0, "c": c,
            "throughput_hr": thr * 60.0, "model": "M/M/c//N"}


def erlang_c(n_trucks: float, cycle_h: float, load_min: float, c_loaders: int,
             shift_hours: float = 12.0) -> dict:
    """Mean loader-queue wait for a closed fleet approximated as M/M/c.

    lambda = N / cycle_h  (each truck returns once per cycle)
    mu     = 60 / load_min per loader
    Returns wq_min (mean wait per arrival), rho, lq, overloaded flag.
    rho >= 1: the queue is unstable; wq is capped at half the shift and the
    route is flagged - never silently infinite.

    `lq` (mean queue length) is None, not NaN, whenever it does not exist.
    M/M/c has no steady-state queue length at rho >= 1 - the queue grows without
    bound - so the honest value is "undefined", and None says that in a way JSON
    can carry and arithmetic cannot swallow. NaN said the same thing in a form
    that propagates: every comparison against it is False, so a consumer writing
    `if lq > threshold` silently takes the safe-looking branch on the one input
    that is actually overloaded. predict() does not export lq today, so nothing
    breaks either way; this is about the next consumer, and it costs nothing to
    be un-swallowable now. `overloaded` is the flag to read, and wq_min stays
    capped at half a shift exactly as before - both are load-bearing and both
    are unchanged.
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
        # Unstable: no steady-state queue length exists. lq=None, not NaN.
        return {"wq_min": cap_wq_min, "rho": rho, "lq": None,
                "lq_note": "undefined: rho >= 1, queue grows without bound",
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
        # Numerically degenerate normaliser (r^c overflows at large c): the
        # Erlang-C terms cannot be trusted, so lq is unknown rather than zero.
        return {"wq_min": cap_wq_min, "rho": rho, "lq": None,
                "lq_note": "undefined: Erlang-C normaliser not finite",
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
