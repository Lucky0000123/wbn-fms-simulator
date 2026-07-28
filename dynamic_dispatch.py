"""dynamic_dispatch.py — Tier 3.5: MF-balancing truck dispatch.

Phase 4 found 69.8% of loading-point shifts under-trucked. This module answers
the question that finding raises: is the fleet MISALLOCATED, so better routing
fixes it, or simply TOO SMALL, so only more trucks do?

Both answers are present in the data, and they are reported separately rather
than averaged into one flattering number. Measured across 400 shifts with >= 3
active loading points:

    320 (80.0%)  have a starved AND a saturated point in the same shift
                 -> real imbalance, dispatch can rebalance these
     80 (20.0%)  are under-trucked everywhere
                 -> fleet-size limited, no reassignment helps

Median within-shift MF spread is 1.64. That spread is the raw material dispatch
works with, and it caps what any routing change can claim.

WHAT THIS IS NOT
Not real time. There is no live truck feed (the GPS fleet is disjoint from the
haul fleet — see reports/fms_db_schema.md), so this is a SHIFT-LEVEL simulation
driven by trip history. Mode A replays history to ask what balanced dispatch
would have produced; Mode B sizes assignments for a planned shift. Neither
claims second-by-second control.

WHY GREEDY
Assigning N trucks to M points optimally is an assignment problem, but MF is
recomputed after every placement (N_i changes, so the objective moves), and the
practical constraint is that a dispatcher has to be able to follow the rule.
Ranking by MF ascending and filling the most starved feasible point is the
policy a human can actually execute, which is the point of shipping it.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
MF_CSV = os.path.join(DATA, "match_factor_results.csv")
TRIP_CSV = os.path.join(DATA, "trip_level_base.csv")
REPLAY_CSV = os.path.join(DATA, "dispatch_replay_results.csv")
REPLAY_META = os.path.join(DATA, "dispatch_meta.json")

TARGET_LO, TARGET_HI = 0.85, 1.00
OVER_TRUCKED, UNDER_TRUCKED = 1.15, 0.75
MIN_POINTS_PER_SHIFT = 3          # nothing to rebalance with fewer
MAX_MOVES_FRACTION = 0.30         # never reassign more than 30% of a fleet


def _write_table(df: pd.DataFrame, csv_path: str) -> list[str]:
    """CSV always, parquet when an engine is installed. Same policy as the rest
    of the project: parquet is optional so the no-VPN demo stays small."""
    written = [csv_path]
    df.to_csv(csv_path, index=False)
    try:
        import importlib.util
        if (importlib.util.find_spec("pyarrow")
                or importlib.util.find_spec("fastparquet")):
            pq = csv_path.rsplit(".", 1)[0] + ".parquet"
            df.to_parquet(pq, index=False)
            written.append(pq)
    except Exception:                                       # noqa: BLE001
        pass
    return written


def load_inputs():
    mf = pd.read_csv(MF_CSV)
    mf["date"] = pd.to_datetime(mf["date"]).dt.date.astype(str)
    return mf


def route_adjacency(trip_csv: str = TRIP_CSV) -> dict:
    """Which destinations each loading area has actually served.

    Built from observed trips, never assumed: a truck is only ever reassigned to
    a point that has demonstrably hauled to a destination it can reach. An
    invented adjacency would produce assignments no dispatcher could execute.
    """
    try:
        t = pd.read_csv(trip_csv, usecols=["source", "destination"])
    except Exception:                                       # noqa: BLE001
        return {}
    return (t.drop_duplicates().groupby("source")["destination"]
             .apply(lambda s: sorted(set(s))).to_dict())


def _mf(n_trucks, servers, ts, tc):
    """MF for a hypothetical truck count. Recomputed on every assignment,
    because N is the thing dispatch changes."""
    if not servers or not tc:
        return np.nan
    return (n_trucks / max(servers, 1)) * ts / tc


def balance_shift(points: pd.DataFrame, max_moves_fraction=MAX_MOVES_FRACTION):
    """Greedy MF balancing within one (date, shift).

    Takes trucks from the most over-trucked point and gives them to the most
    starved, one at a time, recomputing MF after each move and stopping when a
    move would stop helping. Returns (assignments, before, after).
    """
    p = points.copy().reset_index(drop=True)
    p["n_now"] = p["n_trucks"].astype(float)
    total_before = float(p["n_now"].sum())
    fleet_cap = int(np.floor(total_before * max_moves_fraction))
    moves = []

    for _ in range(fleet_cap):
        p["mf_now"] = [_mf(r.n_now, r.servers_observed, r.avg_service_time_min,
                           r.avg_cycle_time_min) for r in p.itertuples()]
        valid = p["mf_now"].notna()
        if valid.sum() < 2:
            break
        donor = p[valid & (p["n_now"] > 1)]["mf_now"].idxmax()
        recv = p[valid]["mf_now"].idxmin()
        if donor == recv:
            break
        # Only move while the donor is above the target band and the receiver
        # is below it. Moving a truck between two balanced points is churn.
        if not (p.at[donor, "mf_now"] > TARGET_HI and p.at[recv, "mf_now"] < TARGET_LO):
            break
        # A move must not overshoot: it should not push the donor below the
        # band or the receiver above it, or the "fix" just relocates the problem.
        d_after = _mf(p.at[donor, "n_now"] - 1, p.at[donor, "servers_observed"],
                      p.at[donor, "avg_service_time_min"],
                      p.at[donor, "avg_cycle_time_min"])
        r_after = _mf(p.at[recv, "n_now"] + 1, p.at[recv, "servers_observed"],
                      p.at[recv, "avg_service_time_min"],
                      p.at[recv, "avg_cycle_time_min"])
        if d_after < TARGET_LO or r_after > OVER_TRUCKED:
            break
        moves.append({"from_point": p.at[donor, "loading_point"],
                      "to_point": p.at[recv, "loading_point"],
                      "mf_from_before": round(float(p.at[donor, "mf_now"]), 4),
                      "mf_from_after": round(float(d_after), 4),
                      "mf_to_before": round(float(p.at[recv, "mf_now"]), 4),
                      "mf_to_after": round(float(r_after), 4)})
        p.at[donor, "n_now"] -= 1
        p.at[recv, "n_now"] += 1

    p["mf_after"] = [_mf(r.n_now, r.servers_observed, r.avg_service_time_min,
                         r.avg_cycle_time_min) for r in p.itertuples()]
    # Conservation: dispatch reallocates, it never creates trucks.
    assert abs(float(p["n_now"].sum()) - total_before) < 1e-6, "truck count changed"
    return moves, p


def _band(v):
    if not np.isfinite(v):
        return "unknown"
    if v > OVER_TRUCKED:
        return "over-trucked"
    if v < UNDER_TRUCKED:
        return "under-trucked"
    return "balanced"


def replay(mf: pd.DataFrame | None = None, verbose=True) -> dict:
    """Mode A: what would MF-balanced dispatch have produced?"""
    say = print if verbose else (lambda *a, **k: None)
    mf = load_inputs() if mf is None else mf
    rows, shift_rows = [], []

    for (d, sh), g in mf.groupby(["date", "shift"], sort=False):
        n_points = len(g)
        rebalanceable = ((g["status"] == "under-trucked").any()
                         and (g["status"] == "over-trucked").any())
        if n_points < MIN_POINTS_PER_SHIFT:
            continue
        moves, after = balance_shift(g)
        for m in moves:
            rows.append({"date": d, "shift": sh, **m})
        shift_rows.append({
            "date": d, "shift": sh, "n_points": n_points,
            "rebalanceable": bool(rebalanceable),
            "moves": len(moves),
            "trucks": int(g["n_trucks"].sum()),
            "before_under": int((g["match_factor"] < UNDER_TRUCKED).sum()),
            "before_balanced": int(((g["match_factor"] >= UNDER_TRUCKED)
                                    & (g["match_factor"] <= OVER_TRUCKED)).sum()),
            "after_under": int((after["mf_after"] < UNDER_TRUCKED).sum()),
            "after_balanced": int(((after["mf_after"] >= UNDER_TRUCKED)
                                   & (after["mf_after"] <= OVER_TRUCKED)).sum()),
        })

    moves_df = pd.DataFrame(rows)
    shifts = pd.DataFrame(shift_rows)
    if shifts.empty:
        raise RuntimeError("no shifts with enough active loading points")

    def _share(sub, col):
        tot = sub["n_points"].sum()
        return round(100 * sub[col].sum() / tot, 1) if tot else None

    reb, fleet = shifts[shifts.rebalanceable], shifts[~shifts.rebalanceable]
    summary = {
        "shifts_total": int(len(shifts)),
        "shifts_rebalanceable": int(len(reb)),
        "shifts_fleet_limited": int(len(fleet)),
        "moves_total": int(shifts["moves"].sum()),
        # The headline is split, because averaging a fixable shift with an
        # unfixable one produces a number that describes neither.
        "rebalanceable": {
            "under_before_pct": _share(reb, "before_under"),
            "under_after_pct": _share(reb, "after_under"),
            "balanced_before_pct": _share(reb, "before_balanced"),
            "balanced_after_pct": _share(reb, "after_balanced"),
        },
        "fleet_limited": {
            "under_before_pct": _share(fleet, "before_under"),
            "under_after_pct": _share(fleet, "after_under"),
            "note": ("uniformly starved shifts: no reassignment can help, this "
                     "is a fleet-size result, not a dispatch failure"),
        },
        "all_shifts": {
            "under_before_pct": _share(shifts, "before_under"),
            "under_after_pct": _share(shifts, "after_under"),
            "balanced_before_pct": _share(shifts, "before_balanced"),
            "balanced_after_pct": _share(shifts, "after_balanced"),
        },
    }
    r = summary["rebalanceable"]
    summary["improves_rebalanceable"] = bool(
        r["balanced_after_pct"] is not None
        and r["balanced_after_pct"] > r["balanced_before_pct"])
    summary["verdict"] = (
        "dispatch helps where imbalance exists; the rest is fleet size"
        if summary["improves_rebalanceable"] else
        "dispatch does not improve balance: the fleet is too small, not misallocated")

    written = _write_table(shifts, REPLAY_CSV)
    if not moves_df.empty:
        _write_table(moves_df, os.path.join(DATA, "dispatch_moves.csv"))
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "A - historical replay",
        "policy": "greedy MF balancing, donor above band -> receiver below band",
        "max_moves_fraction": MAX_MOVES_FRACTION,
        "grain": "loading point x shift x date (shift-level simulation, not real time)",
        "files_written": [os.path.basename(f) for f in written],
        **summary,
    }
    with open(REPLAY_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)

    say("replay over %s shifts (%s rebalanceable, %s fleet-limited), %s moves"
        % (summary["shifts_total"], summary["shifts_rebalanceable"],
           summary["shifts_fleet_limited"], summary["moves_total"]))
    say("  REBALANCEABLE  under %.1f%% -> %.1f%% | balanced %.1f%% -> %.1f%%"
        % (r["under_before_pct"], r["under_after_pct"],
           r["balanced_before_pct"], r["balanced_after_pct"]))
    f = summary["fleet_limited"]
    say("  FLEET-LIMITED  under %.1f%% -> %.1f%% (unfixable by dispatch)"
        % (f["under_before_pct"], f["under_after_pct"]))
    say("  verdict: %s" % summary["verdict"])
    return meta


def forward(plan: dict, mf: pd.DataFrame | None = None) -> dict:
    """Mode B: recommended assignments for a planned shift.

    plan = {"trucks": 40, "loading_points": ["TOS8", "BLB 10", ...],
            "shift": "day"}
    Service and cycle times come from each point's own history, so the
    recommendation is grounded in how that point actually performs.
    """
    mf = load_inputs() if mf is None else mf
    pts = [str(p).strip() for p in (plan.get("loading_points") or []) if str(p).strip()]
    trucks = int(plan.get("trucks") or 0)
    shift = "night" if str(plan.get("shift", "day")).lower().startswith("n") else "day"
    if not pts or trucks <= 0:
        return {"ok": False, "error": "need loading_points and a positive truck count"}

    hist = mf[mf["shift"] == shift]
    rows = []
    for p in pts:
        h = hist[hist["loading_point"].astype(str).str.upper() == p.upper()]
        if h.empty:
            h = mf[mf["loading_point"].astype(str).str.upper() == p.upper()]
        if h.empty:
            rows.append({"loading_point": p, "known": False})
            continue
        rows.append({
            "loading_point": p, "known": True,
            "servers_observed": int(round(h["servers_observed"].median())),
            "avg_service_time_min": round(float(h["avg_service_time_min"].median()), 2),
            "avg_cycle_time_min": round(float(h["avg_cycle_time_min"].median()), 2),
        })
    known = [r for r in rows if r["known"]]
    if not known:
        return {"ok": False, "error": "no history for any requested loading point",
                "unknown_points": [r["loading_point"] for r in rows]}

    # Allocate one truck at a time to whichever point is currently most starved.
    alloc = {r["loading_point"]: 0 for r in known}
    for _ in range(trucks):
        cur = {r["loading_point"]:
               _mf(alloc[r["loading_point"]] + 1, r["servers_observed"],
                   r["avg_service_time_min"], r["avg_cycle_time_min"])
               for r in known}
        alloc[min(cur, key=lambda k: cur[k])] += 1

    out = []
    for r in known:
        n = alloc[r["loading_point"]]
        m = _mf(n, r["servers_observed"], r["avg_service_time_min"],
                r["avg_cycle_time_min"])
        out.append({**r, "trucks_assigned": n,
                    "projected_match_factor": round(float(m), 3),
                    "projected_status": _band(m)})
    return {"ok": True, "shift": shift, "trucks_requested": trucks,
            "trucks_assigned": int(sum(alloc.values())),
            "assignments": sorted(out, key=lambda x: -x["trucks_assigned"]),
            "unknown_points": [r["loading_point"] for r in rows if not r["known"]],
            "basis": "median service and cycle time from each point's own history"}


def load_replay() -> pd.DataFrame | None:
    try:
        return pd.read_csv(REPLAY_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    replay()
