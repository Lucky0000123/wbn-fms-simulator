#!/usr/bin/env python
"""Is the app's trips/DT right? Compare the engines to Jan-Jun history.

Reads reports/trips_per_dt_jan_jun.json (scripts/research_trips_per_dt.py)
and asks each engine for the SAME route at the SAME fleet the history ran:

  hybrid   /api/congestion_model  (physics + queue + BPR, the pricing engine)
  legacy   the divide model carried in that response's legacy_comparison
  path     /api/simulate/path-response capability (measured trips/DT lookup)

Fleet matters: trips/DT falls with fleet, so a model scored at 590 trucks
against history that ran 140 is not wrong, it is a different question. The
comparison fleet is the median DAILY route fleet in the window, recomputed
here from the same rows the aggregate came from.

Prints signed error vs the DT-weighted history rate; exits 0 always (this is
research, not a gate).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:5055")
RES = os.path.join(ROOT, "reports", "trips_per_dt_jan_jun.json")
OUT = os.path.join(ROOT, "reports", "trips_per_dt_vs_engine.json")
START = os.environ.get("RES_START", "2026-01-01")
END = os.environ.get("RES_END", "2026-06-30")


def median_daily_fleet():
    """Median of per-(route, contractor, day) NB_DT sums."""
    from load_fms_env import load_fms_env
    from prediction_pipeline import canonical_area as canon
    load_fms_env()
    import pymssql
    conn = pymssql.connect(server=os.environ["FMS_DB_HOST"],
                           user=os.environ["FMS_DB_USER"],
                           password=os.environ["FMS_DB_PASS"],
                           database="WBN_DATABASE", login_timeout=10, timeout=600)
    cur = conn.cursor()
    cur.execute("SELECT DATE, ORIGIN, DESTINATION, CONTRACTOR, COMPANY, NB_DT "
                "FROM dbo.[DISPATCH RESULTS LITE 2] "
                "WHERE WMT IS NOT NULL AND NB_DT > 0 AND DATE >= %s AND DATE <= %s",
                (START, END))
    per_day = defaultdict(float)
    for d, o, dd, contr, comp, nbdt in cur.fetchall():
        if (comp or "").strip().upper() == "IWIP":
            continue
        co, cd = canon(o), canon(dd)
        if not co or not cd:
            continue
        route = "%s>%s" % (co, cd)
        c = (contr or "").strip().upper() or "?"
        day = str(d)[:10]
        per_day[(route, c, day)] += float(nbdt)
        per_day[(route, "ALL", day)] += float(nbdt)
    conn.close()
    by_key = defaultdict(list)
    for (route, c, _day), v in per_day.items():
        by_key[(route, c)].append(v)
    return {k: statistics.median(v) for k, v in by_key.items()}


def get(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def main():
    import urllib.parse
    recs = json.load(open(RES))["records"]
    fleets = median_daily_fleet()

    rows = []
    for r in recs:
        if r["dt_days"] < 300:
            continue
        key = (r["route"], r["contractor"])
        fleet = fleets.get(key)
        if not fleet or fleet < 5:
            continue
        q = {"route": r["route"], "n_trucks": int(round(fleet))}
        if r["contractor"] not in ("ALL", "?"):
            q["contractor"] = r["contractor"]
        try:
            resp = get(BASE + "/api/congestion_model?" + urllib.parse.urlencode(q))
        except Exception as exc:  # noqa: BLE001
            rows.append({**r, "fleet": fleet, "error": str(exc)[:120]})
            continue
        hyb = resp.get("trips_per_DT_per_day")
        leg = (resp.get("legacy_comparison") or {}).get("trips_per_DT_per_day")
        hist = r["trips_per_dt"]
        rows.append({
            "route": r["route"], "contractor": r["contractor"],
            "days": r["days"], "fleet": round(fleet, 1),
            "hist": hist, "hybrid": hyb, "legacy": leg,
            "calibrated": resp.get("calibrated"),
            "err_pct": (round(100 * (hyb - hist) / hist, 1)
                        if isinstance(hyb, (int, float)) and hist else None),
        })

    ok = [x for x in rows if isinstance(x.get("err_pct"), (int, float))]
    hdr = ("%-26s %-5s %5s %7s %8s %8s %8s %8s" %
           ("route", "cont", "days", "fleet", "history", "hybrid", "legacy", "err%"))
    print(hdr)
    print("-" * len(hdr))
    for x in sorted(rows, key=lambda z: -abs(z.get("err_pct") or 0)):
        print("%-26s %-5s %5s %7s %8s %8s %8s %8s" % (
            x["route"], x["contractor"], x.get("days", "-"), x.get("fleet", "-"),
            x.get("hist", "-"),
            round(x["hybrid"], 2) if isinstance(x.get("hybrid"), (int, float)) else (x.get("error", "-")),
            round(x["legacy"], 2) if isinstance(x.get("legacy"), (int, float)) else "-",
            x.get("err_pct", "-")))
    if ok:
        errs = [abs(x["err_pct"]) for x in ok]
        print("\nn=%d  MAPE %.1f%%  median |err| %.1f%%  within 15%%: %d/%d" % (
            len(ok), statistics.fmean(errs), statistics.median(errs),
            sum(1 for e in errs if e <= 15), len(errs)))
    json.dump({"window": [START, END], "rows": rows}, open(OUT, "w"), indent=1)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
