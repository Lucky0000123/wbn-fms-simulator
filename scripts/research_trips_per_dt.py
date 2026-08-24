#!/usr/bin/env python
"""Measured trips/DT by route x contractor, Jan-Jun 2026 (dispatch basis).

Owner question (2026-08-24): "are we using the right trips per DT?" — check
the history per route per contractor (e.g. TF>HUAFEI by RIM vs SMA) and
compare it with what the app's engines serve today.

Basis: DISPATCH RESULTS LITE 2 (the same view /api/simulate/capability reads).
trips/DT = SUM(RIT) / SUM(NB_DT) — DT-weighted, NOT the mean of per-row rates,
because NB_DT varies 5..200 across rows and an unweighted mean would let a
2-truck day outvote a 150-truck day. Both are printed so the spread is visible.

Also prints the plan side on the same rows (TARGET TRIP x DT PLAN) so
"what we planned" and "what we ran" sit next to each other.

Writes reports/trips_per_dt_jan_jun.json (gitignored: real tonnages).
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

START = os.environ.get("RES_START", "2026-01-01")
END = os.environ.get("RES_END", "2026-06-30")
OUT = os.path.join(ROOT, "reports", "trips_per_dt_jan_jun.json")


def fetch():
    from load_fms_env import load_fms_env
    load_fms_env()
    import pymssql
    conn = pymssql.connect(server=os.environ["FMS_DB_HOST"],
                           user=os.environ["FMS_DB_USER"],
                           password=os.environ["FMS_DB_PASS"],
                           database="WBN_DATABASE", login_timeout=10, timeout=600)
    cur = conn.cursor()
    cur.execute(
        "SELECT DATE, ORIGIN, DESTINATION, CONTRACTOR, TYPE, COMPANY, "
        "NB_SHIFT, NB_DT, RIT, WMT, [DT PLAN], [TARGET TRIP], [PLAN WMT] "
        "FROM dbo.[DISPATCH RESULTS LITE 2] "
        "WHERE WMT IS NOT NULL AND DATE >= %s AND DATE <= %s", (START, END))
    rows = cur.fetchall()
    conn.close()
    return rows


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main():
    from prediction_pipeline import canonical_area as canon
    rows = fetch()
    print("rows %s  %s..%s" % (len(rows), START, END))

    agg = defaultdict(lambda: {"dt": 0.0, "trips": 0.0, "t": 0.0, "days": set(),
                               "planDt": 0.0, "planTrips": 0.0, "rates": []})
    for (d, o, dd, contr, typ, comp, nbsh, nbdt, rit, wmt, pdt, ptr, pw) in rows:
        co, cd = canon(o), canon(dd)
        if not co or not cd:
            continue
        if (comp or "").strip().upper() == "IWIP":
            continue                      # WBN-owned fleet only, as the app does
        dt, trips, t = num(nbdt), num(rit), num(wmt)
        if dt <= 0 or trips <= 0:
            continue
        route = "%s>%s" % (co, cd)
        c = (contr or "").strip().upper() or "?"
        day = str(d)[:10]
        for key in ((route, c), (route, "ALL")):
            a = agg[key]
            a["dt"] += dt
            a["trips"] += trips
            a["t"] += t
            a["days"].add(day)
            a["planDt"] += num(pdt)
            a["planTrips"] += num(ptr) * num(pdt)   # TARGET TRIP is a RATE
            a["rates"].append(trips / dt)

    recs = []
    for (route, contr), a in agg.items():
        if a["dt"] <= 0 or len(a["days"]) < 5:
            continue
        rates = sorted(a["rates"])
        recs.append({
            "route": route, "contractor": contr,
            "days": len(a["days"]), "rows": len(rates),
            "dt_days": round(a["dt"], 1), "trips": round(a["trips"], 0),
            "wmt": round(a["t"], 0),
            "trips_per_dt": round(a["trips"] / a["dt"], 3),
            "trips_per_dt_unweighted": round(statistics.fmean(rates), 3),
            "p25": round(rates[int(0.25 * (len(rates) - 1))], 3),
            "p50": round(statistics.median(rates), 3),
            "p75": round(rates[int(0.75 * (len(rates) - 1))], 3),
            "t_per_trip": round(a["t"] / a["trips"], 2) if a["trips"] else None,
            "t_per_dt": round(a["t"] / a["dt"], 1),
            "plan_trips_per_dt": (round(a["planTrips"] / a["planDt"], 3)
                                  if a["planDt"] > 0 else None),
        })
    recs.sort(key=lambda r: (-r["dt_days"], r["route"], r["contractor"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"window": [START, END], "basis": "dispatch RIT/NB_DT, WBN only",
               "records": recs}, open(OUT, "w"), indent=1)

    hdr = ("%-26s %-5s %5s %9s %8s %8s %8s %8s %8s %7s" %
           ("route", "cont", "days", "dt-days", "trips/DT", "unw.mean",
            "p25", "p75", "plan/DT", "t/trip"))
    print(hdr)
    print("-" * len(hdr))
    for r in recs:
        print("%-26s %-5s %5d %9.0f %8.2f %8.2f %8.2f %8.2f %8s %7.1f" % (
            r["route"], r["contractor"], r["days"], r["dt_days"],
            r["trips_per_dt"], r["trips_per_dt_unweighted"], r["p25"], r["p75"],
            ("%.2f" % r["plan_trips_per_dt"]) if r["plan_trips_per_dt"] else "-",
            r["t_per_trip"] or 0))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
