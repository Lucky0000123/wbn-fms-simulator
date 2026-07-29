"""tonnage_tally.py — Tier 1: rolled-up payload totals.

Aggregates the trip-level extract into tallies per truck, source, destination
and material, at shift and day grain. Everything downstream (ore split,
stockpile balances, reconciliation) is denominated in these tonnes, so the
module's real job is arithmetic that provably conserves mass.

WHAT "MATERIAL" MEANS HERE
The weighbridge tags every ticket with MATERIAL, and across 560,091 tickets the
only values are SAP (saprolite, 21.2 Mt) and LIM (limonite, 2.8 Mt). Both are
nickel ore. See ore_waste_tags.py for why there is no waste side to this split.

RECONCILIATION IS THE POINT
A tally that does not tie back is worse than no tally, because it looks
authoritative. Every run therefore checks that shift totals sum to day totals,
that each grouping recovers the same grand total, and that payloads sit inside
operational bounds — and reports the numbers rather than asserting they are fine.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRIP_CSV = os.path.join(DATA, "trip_level_base.csv")
TAGGED_CSV = os.path.join(DATA, "trip_level_tagged.csv")
TALLY_CSV = os.path.join(DATA, "tonnage_tally.csv")
TALLY_META = os.path.join(DATA, "tonnage_meta.json")

# A haul truck carries roughly 20-60 t here. Outside 20-400 t the ticket is a
# data artefact (tare/gross swap, manual entry), not a real load. Flagged and
# counted, never silently dropped, because a systematic drift in these is
# itself a finding.
PAYLOAD_MIN_T, PAYLOAD_MAX_T = 20.0, 400.0
GROUPINGS = ("truck", "shovel", "destination", "material")


def _write_table(df: pd.DataFrame, path: str) -> list[str]:
    """CSV always, parquet when an engine exists. Same policy as the rest of the
    project: parquet stays optional so the no-VPN demo install stays small."""
    written = [path]
    df.to_csv(path, index=False)
    try:
        import importlib.util
        if (importlib.util.find_spec("pyarrow")
                or importlib.util.find_spec("fastparquet")):
            pq = path.rsplit(".", 1)[0] + ".parquet"
            df.to_parquet(pq, index=False)
            written.append(pq)
    except Exception:                                       # noqa: BLE001
        pass
    return written


def load_trips(path: str | None = None) -> pd.DataFrame:
    """Prefer the material-tagged extract; fall back to the base extract."""
    for p in ([path] if path else [TAGGED_CSV, TRIP_CSV]):
        if p and os.path.exists(p):
            df = pd.read_csv(p)
            df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
            df.attrs["source_file"] = os.path.basename(p)
            return df
    raise FileNotFoundError("no trip extract found — run trip_extraction.py")


def _key(group: str) -> str:
    return {"truck": "truck_id", "shovel": "source",
            "destination": "destination", "material": "material_type"}[group]


def build(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """One long table covering every grouping, so a single file answers all of
    them and the totals cannot drift apart between four separate files."""
    d = load_trips() if df is None else df
    if "material_type" not in d.columns:
        # Untagged extract: fall back to the weighbridge's own material code so
        # the grouping still works, and record that it is the raw code.
        d = d.copy()
        d["material_type"] = d.get("material", pd.Series(index=d.index, dtype=object))

    out = []
    for g in GROUPINGS:
        k = _key(g)
        if k not in d.columns:
            continue
        agg = (d.groupby([k, "date", "shift"])
                 .agg(total_wmt=("payload_t", "sum"),
                      trip_count=("payload_t", "size"),
                      avg_payload_t=("payload_t", "mean"),
                      truck_count=("truck_id", "nunique"))
                 .reset_index().rename(columns={k: "group_value"}))
        agg.insert(0, "group_by", g)
        out.append(agg)

    t = pd.concat(out, ignore_index=True)
    for c in ("total_wmt", "avg_payload_t"):
        t[c] = t[c].round(3)
    return t


def reconcile(trips: pd.DataFrame, tally: pd.DataFrame) -> dict:
    """Does the tally tie back to the trips it came from?

    Checked three ways, because each catches a different mistake: a grouping
    that drops rows, a shift/day split that double-counts, and payloads that
    are physically impossible.
    """
    grand = float(trips["payload_t"].sum())
    per_group = {g: round(float(tally[tally["group_by"] == g]["total_wmt"].sum()), 3)
                 for g in tally["group_by"].unique()}
    worst = max((abs(v - grand) / grand * 100) for v in per_group.values()) if grand else 0.0

    # Shift totals must sum to day totals for the same grouping.
    sub = tally[tally["group_by"] == "shovel"]
    by_day = sub.groupby("date")["total_wmt"].sum()
    day_direct = trips.groupby("date")["payload_t"].sum()
    day_gap = float((by_day - day_direct).abs().max()) if len(by_day) else 0.0

    p = trips["payload_t"]
    anomalies = {
        "below_%dt" % PAYLOAD_MIN_T: int((p < PAYLOAD_MIN_T).sum()),
        "above_%dt" % PAYLOAD_MAX_T: int((p > PAYLOAD_MAX_T).sum()),
        "zero_or_negative": int((p <= 0).sum()),
    }
    n_bad = sum(anomalies.values())
    return {
        "grand_total_wmt": round(grand, 3),
        "total_by_grouping": per_group,
        "worst_grouping_variance_pct": round(worst, 6),
        "shift_to_day_max_gap_t": round(day_gap, 6),
        "reconciles": bool(worst < 0.01 and day_gap < 0.01),
        "payload_anomalies": anomalies,
        "anomaly_count": n_bad,
        "anomaly_pct": round(100 * n_bad / max(len(trips), 1), 4),
        "payload_bounds_t": [PAYLOAD_MIN_T, PAYLOAD_MAX_T],
    }


def weighbridge_crosscheck(trips: pd.DataFrame, conn=None) -> dict:
    """Compare the tally against the weighbridge's own daily totals.

    The tally is built from filtered trips (bounded cycle time, canonical
    routes), so a gap is expected. Reporting the size of that gap is the point:
    an unexplained 30% would mean the filter is discarding real production.
    """
    try:
        import simulator_api as sim
        close = False
        if conn is None:
            if not sim._db_ready():
                return {"available": False, "reason": "no DB configured"}
            conn, close = sim._conn("WBN_DATABASE"), True
        try:
            wb = pd.read_sql("""
                SELECT CONVERT(date,[DATE]) d, SUM(WMT) wmt, COUNT(*) tickets
                FROM HAULAGE_IWIP_CLEAN
                WHERE [DATE] >= '%s' AND [DATE] <= '%s' AND WMT > 0
                GROUP BY CONVERT(date,[DATE])"""
                % (trips["date"].min(), trips["date"].max()), conn)
        finally:
            if close:
                conn.close()
    except Exception as exc:                                # noqa: BLE001
        return {"available": False, "reason": str(exc)[:120]}

    wb["d"] = wb["d"].astype(str)
    ours = trips.groupby("date")["payload_t"].sum().rename("ours")
    m = wb.set_index("d").join(ours, how="inner")
    if m.empty:
        return {"available": False, "reason": "no overlapping dates"}
    tot_wb, tot_ours = float(m["wmt"].sum()), float(m["ours"].sum())
    return {
        "available": True,
        "days_compared": int(len(m)),
        "weighbridge_total_wmt": round(tot_wb, 1),
        "tally_total_wmt": round(tot_ours, 1),
        "variance_pct": round(100 * (tot_ours - tot_wb) / tot_wb, 3) if tot_wb else None,
        "note": ("the tally is built from filtered trips (cycle time in bounds, "
                 "canonical routes, >= 30 trips per route), so it is expected to "
                 "sit below the raw weighbridge total; the variance is the size "
                 "of that filter"),
    }


def run(verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    trips = load_trips()
    tally = build(trips)
    rec = reconcile(trips, tally)
    wb = weighbridge_crosscheck(trips)
    written = _write_table(tally, TALLY_CSV)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_file": trips.attrs.get("source_file"),
        "trips": int(len(trips)),
        "tally_rows": int(len(tally)),
        "groupings": list(GROUPINGS),
        "date_range": [trips["date"].min(), trips["date"].max()],
        "files_written": [os.path.basename(f) for f in written],
        "reconciliation": rec,
        "weighbridge_crosscheck": wb,
    }
    with open(TALLY_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)

    say("tonnage tally: %s rows from %s trips (%s → %s)"
        % (format(len(tally), ","), format(len(trips), ","), *meta["date_range"]))
    say("  grand total %s t | reconciles=%s (worst variance %.6f%%)"
        % (format(int(rec["grand_total_wmt"]), ","), rec["reconciles"],
           rec["worst_grouping_variance_pct"]))
    say("  payload anomalies: %s (%.4f%%) %s"
        % (rec["anomaly_count"], rec["anomaly_pct"], rec["payload_anomalies"]))
    if wb.get("available"):
        say("  weighbridge cross-check: tally %s t vs weighbridge %s t (%.2f%%)"
            % (format(int(wb["tally_total_wmt"]), ","),
               format(int(wb["weighbridge_total_wmt"]), ","), wb["variance_pct"]))
    else:
        say("  weighbridge cross-check unavailable (%s)" % wb.get("reason"))
    return meta


def load_tally() -> pd.DataFrame | None:
    try:
        return pd.read_csv(TALLY_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    run()
