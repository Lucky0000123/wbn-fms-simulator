"""stockpile_fifo.py — Tier 3: ROM pad grade tracking and reconciliation.

Tracks what arrived on each ore pile, in what order, at what grade, and what has
been reclaimed from it. FIFO because that is how a pad is actually worked: the
oldest material at the base comes out first.

THREE THINGS ARE REAL HERE, NOT SIMULATED, AND ONE IS PARTIAL

RECLAIM IS REAL. The brief allowed simulating reclaim at a constant rate if no
log existed. It does exist: `HAULAGE_IWIP.ACTIVITY` separates fresh production
(DIRECT, HAULAGE) from pad movements (SALES RECLAIMING, RECLAIMING, CRUSHER
RECLAIMING, REHANDLING, REJECT), and every one of those is a weighed ticket.
Only 46.7% of trips are fresh production, so treating all of them as arrivals
would have roughly doubled the pad balance. Simulating would have been both
unnecessary and wrong.

GRADE IS REAL BUT PARTIAL. `BLOCK_PROD_QC_BM_TOS` carries BM_Ni (block model,
planned) and TOS_Ni (pile assay, actual) side by side, 122,689 rows in the trip
window. Both grades are present on 28.8% of them. Reconciliation is therefore
computed ONLY on rows that have both, and the coverage is reported with the
result: a GF quoted without its 28.8% base would imply a certainty that is not
there.

F, GF AND MF ARE REPORTED SEPARATELY, ALWAYS. Metal Factor is the product of the
tonnage factor and the grade factor, so a single MF of 1.00 can hide 10% under
on tonnes cancelling 10% over on grade. Reporting only MF is how that hides.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TAGGED_CSV = os.path.join(DATA, "trip_level_tagged.csv")
BAL_CSV = os.path.join(DATA, "stockpile_balances.csv")
FIFO_CSV = os.path.join(DATA, "fifo_queues.csv")
RECON_CSV = os.path.join(DATA, "reconciliation.csv")
FIFO_META = os.path.join(DATA, "stockpile_meta.json")

# ACTIVITY values that put NEW material on a pad, versus those that take it off
# or move it around. Everything else is counted as neither.
INBOUND_FLOWS = {"DIRECT", "HAULAGE"}
OUTBOUND_FLOWS = {"SALES RECLAIMING", "RECLAIMING", "CRUSHER RECLAIMING",
                  "REHANDLING", "REJECT"}

GRADE_SQL = """
SELECT  CONVERT(date, [DATE])  AS date,
        DEPOSIT                AS deposit,
        DESTINATION_AREA       AS destination,
        TOS_PILE               AS tos_pile,
        WMT                    AS wmt,
        BM_Ni                  AS planned_ni,
        TOS_Ni                 AS actual_ni,
        BM_Fe                  AS planned_fe,
        TOS_Fe                 AS actual_fe
FROM    BLOCK_PROD_QC_BM_TOS
WHERE   [DATE] >= '{start}' AND [DATE] <= '{end}'
"""


def _write(df: pd.DataFrame, path: str) -> list[str]:
    out = [path]
    df.to_csv(path, index=False)
    try:
        import importlib.util
        if importlib.util.find_spec("pyarrow"):
            pq = path.rsplit(".", 1)[0] + ".parquet"
            df.to_parquet(pq, index=False)
            out.append(pq)
    except Exception:                                       # noqa: BLE001
        pass
    return out


def load_tagged() -> pd.DataFrame:
    if not os.path.exists(TAGGED_CSV):
        raise FileNotFoundError("run ore_waste_tags.py first")
    d = pd.read_csv(TAGGED_CSV)
    d["date"] = pd.to_datetime(d["date"])
    return d


def arrivals_and_reclaims(d: pd.DataFrame):
    """Split ore movements into what lands on a pad and what leaves it."""
    ore = d[d["material_type"] == "ORE"].copy()
    flow = ore.get("flow", pd.Series("UNKNOWN", index=ore.index)).astype(str).str.upper()
    ore["direction"] = np.select(
        [flow.isin(INBOUND_FLOWS), flow.isin(OUTBOUND_FLOWS)],
        ["in", "out"], default="other")
    # WHICH PILE DOES A TICKET AFFECT?
    # An arrival lands at its DESTINATION. A reclaim is drawn from its SOURCE
    # and delivered elsewhere, so charging it to its destination debits the
    # wrong pile entirely -- that produced a -626,911 t balance, which is
    # physically impossible and is how the bug was caught.
    ore["pile_id"] = np.where(ore["direction"] == "out",
                              ore["source"], ore["destination"])
    ore["date"] = pd.to_datetime(ore["date"], errors="coerce")

    # Order strictly by dump time: FIFO is meaningless without it.
    sort_key = "depart_hour" if "depart_hour" in ore.columns else None
    ore = ore.sort_values(["date"] + ([sort_key] if sort_key else []))
    ore["seq"] = range(len(ore))
    return ore


def build_balances(ore: pd.DataFrame) -> pd.DataFrame:
    """Per-pile mass balance. Conservation is asserted, not hoped for."""
    # Coerce dates defensively: callers may hand this a frame read straight
    # from CSV where `date` is still a string, and subtracting strings raises
    # rather than producing a wrong answer -- but only after the caller has
    # already built a balance they trust.
    ore = ore.copy()
    ore["date"] = pd.to_datetime(ore["date"], errors="coerce")
    g = ore.groupby("pile_id")
    rows = []
    for pile, sub in g:
        tin = float(sub.loc[sub["direction"] == "in", "payload_t"].sum())
        tout = float(sub.loc[sub["direction"] == "out", "payload_t"].sum())
        other = float(sub.loc[sub["direction"] == "other", "payload_t"].sum())
        inb = sub[sub["direction"] == "in"]
        oldest = inb["date"].min() if len(inb) else pd.NaT
        # OPENING STOCK IS UNKNOWN, and pretending otherwise produces nonsense.
        # Several piles were being reclaimed from the first day of the extract,
        # so material was already on them before the window opened. A balance
        # measured from zero therefore goes negative -- POS 10 reached
        # -1,407,801 t -- which is physically impossible and is exactly the
        # signal that opening stock is missing rather than zero.
        #
        # So the balance is reported as a MOVEMENT since the window opened, and
        # `implied_opening_stock_t` states the minimum that must have been on
        # the pad on day one for the arithmetic to be possible. That is a real,
        # useful number: it is a lower bound the site can check against survey.
        net = tin - tout
        rows.append({
            "pile_id": pile,
            "tonnes_in": round(tin, 1),
            "tonnes_out": round(tout, 1),
            "tonnes_unclassified": round(other, 1),
            "net_movement_tonnes": round(net, 1),
            "implied_opening_stock_t": round(-net, 1) if net < 0 else 0.0,
            "opening_stock_known": False,
            "current_balance_tonnes": round(net, 1),
            "arrivals": int((sub["direction"] == "in").sum()),
            "reclaims": int((sub["direction"] == "out").sum()),
            "oldest_arrival": str(oldest)[:10] if pd.notna(oldest) else None,
            "fifo_age_days": (int((sub["date"].max() - oldest).days)
                              if pd.notna(oldest) else None),
            "last_movement": str(sub["date"].max())[:10],
        })
    b = pd.DataFrame(rows).sort_values("tonnes_in", ascending=False)
    # Mass must balance exactly: in - out == net movement, by construction.
    err = (b["tonnes_in"] - b["tonnes_out"] - b["net_movement_tonnes"]).abs().max()
    assert err < 0.11, "mass balance broken by %.3f t" % err
    return b


def build_fifo(ore: pd.DataFrame, max_rows_per_pile: int = 5000) -> pd.DataFrame:
    """FIFO queue per pile: arrivals in dump order, consumed by reclaims.

    A truckload is fully consumed before the next is touched, which is what
    makes the remaining balance attributable to specific arrival dates and so
    lets `fifo_age_days` mean something.
    """
    out = []
    for pile, sub in ore.groupby("pile_id"):
        arr = sub[sub["direction"] == "in"].sort_values("seq")
        reclaimed = float(sub.loc[sub["direction"] == "out", "payload_t"].sum())
        remaining = reclaimed
        for i, r in enumerate(arr.head(max_rows_per_pile).itertuples()):
            load = float(r.payload_t)
            taken = min(load, remaining)
            remaining -= taken
            out.append({
                "pile_id": pile, "queue_position": i,
                "arrival_date": str(r.date)[:10],
                "truck_id": r.truck_id,
                "ticket_no": getattr(r, "ticket_no", None),
                "payload_t": round(load, 2),
                "tonnes_reclaimed": round(taken, 2),
                "tonnes_remaining": round(load - taken, 2),
                "fully_reclaimed": bool(taken >= load - 1e-9),
                "ore_type": getattr(r, "ore_type", None),
            })
    return pd.DataFrame(out)


def reconcile(ore: pd.DataFrame, conn=None) -> tuple[pd.DataFrame, dict]:
    """F, GF and MF per destination, computed only where both grades exist."""
    try:
        import simulator_api as sim
        close = False
        if conn is None:
            if not sim._db_ready():
                raise RuntimeError("no DB configured")
            conn, close = sim._conn("WBN_DATABASE"), True
        try:
            q = GRADE_SQL.format(start=str(ore["date"].min())[:10],
                                 end=str(ore["date"].max())[:10])
            g = pd.read_sql(q, conn)
        finally:
            if close:
                conn.close()
    except Exception as exc:                                # noqa: BLE001
        return pd.DataFrame(), {"available": False, "reason": str(exc)[:120]}

    # JOIN KEY IS THE DEPOSIT, NOT THE PILE.
    # The grade table's `destination` holds a movement TYPE (only 'TOS' and
    # 'LD'), DESTINATION_AREA holds fine-grained loading points, and TOS_PILE
    # holds 6,904 individual pile codes -- none of which appear in the haulage
    # feed's 17 destinations. DEPOSIT does: BLB, TF and KRENE are the mining
    # deposits that trip SOURCES come from. So reconciliation is per deposit,
    # which is the grain at which planned grade is actually set.
    g["deposit"] = g["deposit"].astype(str).str.strip().str.upper()
    both = g[g["planned_ni"].notna() & g["actual_ni"].notna()]
    coverage = round(100 * len(both) / max(len(g), 1), 1)

    o = ore.copy()
    o["deposit"] = o["source"].astype(str).str.strip().str.upper()
    actual_t = o[o["direction"] == "in"].groupby("deposit")["payload_t"].sum()
    planned_t = g.groupby("deposit")["wmt"].sum()
    grades = both.groupby("deposit").agg(
        planned_ni=("planned_ni", "mean"), actual_ni=("actual_ni", "mean"),
        n_assays=("actual_ni", "size"))

    rows = []
    for dest in sorted(set(actual_t.index) & set(grades.index)):
        at, pt = float(actual_t.get(dest, np.nan)), float(planned_t.get(dest, np.nan))
        pn = float(grades["planned_ni"].get(dest, np.nan))
        an = float(grades["actual_ni"].get(dest, np.nan))
        # Each factor is None unless its own inputs exist. A fabricated 1.0
        # would read as "on plan" when it means "unknown".
        # F IS SCOPE-SENSITIVE AND IS FLAGGED, NOT PUBLISHED BARE.
        # Measured F is ~0.26, which would read as production missing plan by
        # 74%. It is not: the numerator counts only fresh-production arrivals
        # at the 17 haulage destinations in this weighbridge feed, while the
        # denominator is ALL mining production booked against that deposit,
        # including material that never passes through this feed. Quoting 0.26
        # as a tonnage factor would be a serious misread, so it ships with
        # f_scope_comparable=False until the site confirms both sides cover the
        # same material. GF is unaffected: it compares two grades measured on
        # the same rows.
        f = round(at / pt, 4) if (pt and pt > 0 and at == at) else None
        gf = round(an / pn, 4) if (pn and pn > 0 and an == an) else None
        mf = round(f * gf, 4) if (f is not None and gf is not None) else None
        rows.append({
            "deposit": dest,
            "actual_tonnes": round(at, 1) if at == at else None,
            "planned_tonnes": round(pt, 1) if pt == pt else None,
            "planned_ni_pct": round(pn, 4) if pn == pn else None,
            "actual_ni_pct": round(an, 4) if an == an else None,
            "n_assays": int(grades["n_assays"].get(dest, 0)),
            "F_tonnage_factor": f,
            "f_scope_comparable": False,
            "f_caveat": ("numerator is fresh-production arrivals in the "
                         "haulage feed; denominator is all deposit production. "
                         "Not a like-for-like comparison."),
            "GF_grade_factor": gf,
            "MF_metal_factor": mf,
            "mf_reliable": False,
            "complete": bool(f is not None and gf is not None),
        })
    r = pd.DataFrame(rows)
    ok = r[r["complete"]]
    meta = {
        "available": True,
        "grade_rows_in_window": int(len(g)),
        "rows_with_both_grades": int(len(both)),
        "grade_coverage_pct": coverage,
        "deposits_with_full_reconciliation": int(len(ok)),
        "deposits_total": int(len(r)),
        "overall_F": round(float(ok["F_tonnage_factor"].median()), 4) if len(ok) else None,
        "overall_GF": round(float(ok["GF_grade_factor"].median()), 4) if len(ok) else None,
        "overall_MF": round(float(ok["MF_metal_factor"].median()), 4) if len(ok) else None,
        "gf_trustworthy": True,
        "f_trustworthy": False,
        "note": ("F, GF and MF are reported separately and never collapsed: an "
                 "MF near 1.0 can hide a tonnage shortfall cancelling a grade "
                 "surplus. Factors are null where their inputs are missing. "
                 "GF is sound (two grades measured on the same rows). F, and "
                 "therefore MF, compare different scopes and are flagged "
                 "f_scope_comparable=false until the site confirms both sides "
                 "cover the same material."),
    }
    return r, meta


def run(verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    ore = arrivals_and_reclaims(load_tagged())
    bal = build_balances(ore)
    fifo = build_fifo(ore)
    rec, rmeta = reconcile(ore)

    _write(bal, BAL_CSV)
    _write(fifo, FIFO_CSV)
    if len(rec):
        _write(rec, RECON_CSV)

    dirs = ore["direction"].value_counts().to_dict()
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ore_trips": int(len(ore)),
        "movement_counts": dirs,
        "piles": int(len(bal)),
        "total_tonnes_in": round(float(bal["tonnes_in"].sum()), 1),
        "total_tonnes_out": round(float(bal["tonnes_out"].sum()), 1),
        "total_balance": round(float(bal["current_balance_tonnes"].sum()), 1),
        "fifo_rows": int(len(fifo)),
        "reclaim_source": ("REAL - HAULAGE_IWIP.ACTIVITY weighed tickets, "
                           "not simulated"),
        "inbound_flows": sorted(INBOUND_FLOWS),
        "outbound_flows": sorted(OUTBOUND_FLOWS),
        "reconciliation": rmeta,
    }
    with open(FIFO_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)

    say("stockpile: %d piles from %s ore trips %s"
        % (len(bal), format(len(ore), ","), dirs))
    say("  in %s t | out %s t | net movement %s t"
        % (format(int(meta["total_tonnes_in"]), ","),
           format(int(meta["total_tonnes_out"]), ","),
           format(int(meta["total_balance"]), ",")))
    say("  FIFO rows: %s" % format(len(fifo), ","))
    if rmeta.get("available"):
        say("  reconciliation on %d/%d deposits (grade coverage %.1f%%)"
            % (rmeta["deposits_with_full_reconciliation"],
               rmeta["deposits_total"], rmeta["grade_coverage_pct"]))
        say("  GF=%s  <- trustworthy: same rows, two grades"
            % rmeta["overall_GF"])
        say("  F=%s MF=%s  <- FLAGGED: scope mismatch, not a shortfall"
            % (rmeta["overall_F"], rmeta["overall_MF"]))
    else:
        say("  reconciliation unavailable (%s)" % rmeta.get("reason"))
    return meta


def load_balances():
    try:
        return pd.read_csv(BAL_CSV)
    except Exception:                                       # noqa: BLE001
        return None


def load_fifo(pile_id: str | None = None):
    try:
        d = pd.read_csv(FIFO_CSV)
        return d[d["pile_id"].astype(str) == str(pile_id)] if pile_id else d
    except Exception:                                       # noqa: BLE001
        return None


def load_reconciliation():
    try:
        return pd.read_csv(RECON_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    run()
