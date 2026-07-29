"""Unit tests for Phase 6: tonnage tally, material tagging, stockpile FIFO.

Tests the INVARIANTS, not the fitted numbers.

Mass conservation is the one that matters. A stockpile balance that does not
conserve mass is worse than no balance, because a planner acts on it. Two real
bugs were caught this way: reclaims being charged to the wrong pile, and a
balance measured from an unknown opening stock.

    python tests/test_phase6.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ore_waste_tags as ow    # noqa: E402
import stockpile_fifo as sp    # noqa: E402
import tonnage_tally as tt     # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        FAILURES.append(name)
        print("  FAIL  %s %s" % (name, detail))


def _trips(n=600, seed=3):
    rng = np.random.default_rng(seed)
    dests = ["FENI KM0", "POS 12", "POS 10"]
    srcs = ["TF", "BLB", "KR"]
    rows = []
    for i in range(n):
        rows.append({
            "ticket_no": "T%06d" % i,
            "truck_id": "TR%02d" % (i % 20),
            "date": "2026-05-%02d" % (1 + i % 20),
            "shift": "day" if i % 2 else "night",
            "source": srcs[i % 3], "destination": dests[i % 3],
            "payload_t": float(rng.uniform(30, 60)),
            "material": "SAP" if i % 5 else "LIM",
            "material_type": "ORE",
            "ore_type": "saprolite" if i % 5 else "limonite",
            "flow": ["DIRECT", "HAULAGE", "RECLAIMING", "SALES RECLAIMING"][i % 4],
            "depart_hour": i % 24,
        })
    d = pd.DataFrame(rows)
    d["is_fresh_production"] = d["flow"].isin(ow.FRESH_FLOWS)
    return d


# ── tonnage tally ──────────────────────────────────────────────────────────
def test_tally_conserves_tonnage():
    """Every grouping must recover the same grand total."""
    d = _trips()
    t = tt.build(d)
    grand = d["payload_t"].sum()
    for g in t["group_by"].unique():
        got = t[t["group_by"] == g]["total_wmt"].sum()
        check("grouping %s recovers the grand total" % g, abs(got - grand) < 0.01,
              (g, got, grand))


def test_tally_reconciliation_reports_numbers():
    d = _trips()
    r = tt.reconcile(d, tt.build(d))
    check("reconciles on clean data", r["reconciles"] is True, r)
    check("worst variance is ~0", r["worst_grouping_variance_pct"] < 0.01,
          r["worst_grouping_variance_pct"])
    check("anomaly counts present", "payload_anomalies" in r)


def test_tally_flags_payload_anomalies():
    """An impossible payload must be counted, not silently passed."""
    d = _trips()
    d.loc[0, "payload_t"] = 5.0        # below the 20 t floor
    d.loc[1, "payload_t"] = 900.0      # above the 400 t ceiling
    r = tt.reconcile(d, tt.build(d))
    check("low payload flagged", r["payload_anomalies"]["below_20t"] >= 1, r)
    check("high payload flagged", r["payload_anomalies"]["above_400t"] >= 1, r)


def test_real_tally_if_present():
    t = tt.load_tally()
    if t is None or t.empty:
        print("  SKIP  no tally built")
        return
    check("all four groupings present",
          set(t["group_by"]) == set(tt.GROUPINGS), set(t["group_by"]))
    check("no negative tonnage", (t["total_wmt"] >= 0).all())
    check("no zero-trip rows", (t["trip_count"] > 0).all())


# ── material tagging ───────────────────────────────────────────────────────
def test_every_destination_classified():
    d = _trips()
    dm = ow.classify_destinations(d)
    check("every destination has a row", len(dm) == d["destination"].nunique())
    check("every row records its source",
          dm["classification_source"].notna().all())
    check("every row records confidence",
          dm["classification_confident"].notna().all())


def test_no_waste_invented():
    """The data is ore-only. A tagger that invents WASTE would corrupt the
    stockpile grades this phase exists to track."""
    d = _trips()
    dm = ow.classify_destinations(d)
    check("no WASTE class invented from ore codes",
          set(dm["material_type"]) == {"ORE"}, set(dm["material_type"]))


def test_real_tags_if_present():
    dm_path = ow.DEST_MAP_CSV
    if not os.path.exists(dm_path):
        print("  SKIP  no destination map")
        return
    dm = pd.read_csv(dm_path)
    check("map covers destinations", len(dm) > 0, len(dm))
    check("no unconfident classification left unflagged",
          (dm["classification_confident"] | dm["needs_site_verification"]).all())


# ── stockpile FIFO ─────────────────────────────────────────────────────────
def test_mass_conservation():
    """in - out must equal net movement, exactly. This is the invariant that
    caught reclaims being charged to the wrong pile."""
    ore = sp.arrivals_and_reclaims(_trips())
    b = sp.build_balances(ore)
    err = (b["tonnes_in"] - b["tonnes_out"] - b["net_movement_tonnes"]).abs().max()
    check("mass conserved per pile", err < 0.11, err)
    total_in = ore.loc[ore["direction"] == "in", "payload_t"].sum()
    check("total inbound matches the trips",
          abs(b["tonnes_in"].sum() - total_in) < 0.5,
          (b["tonnes_in"].sum(), total_in))


def test_reclaims_debit_the_source_pile():
    """A reclaim draws material FROM its source. Charging it to the destination
    debits a pile that never held the material."""
    ore = sp.arrivals_and_reclaims(_trips())
    out = ore[ore["direction"] == "out"]
    if out.empty:
        check("reclaims exist to test", False)
        return
    check("outbound pile_id is the source",
          (out["pile_id"] == out["source"]).all())
    inb = ore[ore["direction"] == "in"]
    check("inbound pile_id is the destination",
          (inb["pile_id"] == inb["destination"]).all())


def test_fifo_is_ordered_and_bounded():
    ore = sp.arrivals_and_reclaims(_trips())
    f = sp.build_fifo(ore)
    if f.empty:
        print("  SKIP  no fifo rows")
        return
    for pile, sub in f.groupby("pile_id"):
        check("queue positions ascend for %s" % pile,
              list(sub["queue_position"]) == sorted(sub["queue_position"]))
        check("dates non-decreasing for %s" % pile,
              list(sub["arrival_date"]) == sorted(sub["arrival_date"]))
    check("reclaimed never exceeds the load",
          (f["tonnes_reclaimed"] <= f["payload_t"] + 1e-6).all())
    check("remaining is never negative", (f["tonnes_remaining"] >= -1e-6).all())


def test_opening_stock_is_declared_unknown():
    """Balances are net movement, not true stock. Claiming otherwise would be
    a number a planner could act on wrongly."""
    b = sp.load_balances()
    if b is None or b.empty:
        print("  SKIP  no balances built")
        return
    check("opening_stock_known is present and false",
          "opening_stock_known" in b.columns and not b["opening_stock_known"].any())
    check("implied opening stock recorded", "implied_opening_stock_t" in b.columns)
    neg = b[b["net_movement_tonnes"] < 0]
    if len(neg):
        check("negative movement implies opening stock",
              (neg["implied_opening_stock_t"] > 0).all())


def test_reconciliation_never_fabricates():
    """F, GF, MF must be null where inputs are missing, and F must carry its
    scope caveat rather than reading as a 74% shortfall."""
    r = sp.load_reconciliation()
    if r is None or r.empty:
        print("  SKIP  no reconciliation built")
        return
    check("F, GF, MF columns all present",
          {"F_tonnage_factor", "GF_grade_factor", "MF_metal_factor"} <= set(r.columns))
    check("F carries a scope flag", "f_scope_comparable" in r.columns)
    check("F is flagged not-comparable", not r["f_scope_comparable"].any())
    for _, row in r.iterrows():
        if pd.notna(row["GF_grade_factor"]):
            check("GF has both grades where present",
                  pd.notna(row["planned_ni_pct"]) and pd.notna(row["actual_ni_pct"]),
                  row.get("deposit"))


if __name__ == "__main__":
    for fn in (test_tally_conserves_tonnage, test_tally_reconciliation_reports_numbers,
               test_tally_flags_payload_anomalies, test_real_tally_if_present,
               test_every_destination_classified, test_no_waste_invented,
               test_real_tags_if_present, test_mass_conservation,
               test_reclaims_debit_the_source_pile, test_fifo_is_ordered_and_bounded,
               test_opening_stock_is_declared_unknown,
               test_reconciliation_never_fabricates):
        print("\n%s" % fn.__name__)
        fn()
    print("\n%s" % ("-" * 60))
    if FAILURES:
        print("FAILED %d: %s" % (len(FAILURES), ", ".join(FAILURES)))
        raise SystemExit(1)
    print("all phase 6 tests passed")
