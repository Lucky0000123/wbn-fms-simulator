"""availability_analysis.py — Priority 1: measure real availability, and be
clear about where it does and does not belong.

WHY THIS IS NOT A "FIX" TO THE SIMULATOR
The brief calls replacing the assumed 85% availability "the single biggest fix",
on the basis that the simulator multiplies every tonnage by it. That was true when
the brief was written. It no longer is: the previous turn traced a 2.7x
overprediction to the CYCLE definition, and fixing it removed the availability
multiplier entirely, because the measured effective cycle (shift-minutes per
completed trip) already contains every non-hauling minute.

Tested rather than argued. Against observed tonnage per truck-shift on 44 routes:

    current, no availability factor      bias  +5.5%
    x 0.850 (the brief's assumption)     bias -10.3%
    x 0.836 (measured hauling trucks)    bias -11.8%
    x 0.765 (Day X fleet-wide)           bias -19.3%
    x 0.451 (Day X utilisation)          bias -52.4%

Every factor makes it worse. Re-introducing one would be the original
double-counting error in reverse, and would under-predict production for whoever
plans against it.

WHAT THIS MODULE DOES INSTEAD
Availability is still worth measuring, for three uses that are real:

  1. FLEET SIZING. "How many trucks must I roster to keep N hauling?" needs
     availability, and the simulator cannot answer it today.
  2. A DIAGNOSTIC. A route whose trucks sit at 60% availability has a maintenance
     problem, not a haul-road problem, and the two need different responses.
  3. VALIDATING THE EFFECTIVE CYCLE. If measured availability and the effective
     cycle disagree about how much of a shift is productive, one of them is wrong.

So it is extracted, published per truck and per shift, and exposed as
information. It is deliberately NOT wired into the tonnage arithmetic, and the
reason is recorded here so nobody re-adds it later assuming it was an oversight.

READ ONLY against the database.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
OUT_CSV = os.path.join(DATA, "availability_per_truck.csv")
OUT_JSON = os.path.join(REPORTS, "availability_analysis.json")

# EQUIPMENTS_HOURLY_STATUS stores hours in columns, not a status enum, so the
# brief's CASE WHEN status = 'working' shape does not apply. Verified from the
# schema scan: WORKING_HOURS, STBY_HOURS, BD_HOURS, PM_HOURS, OPERATING_HOURS.
SQL = """
SELECT  CAST(s.[DATE] AS date)          AS work_date,
        s.SHIFT                         AS shift,
        UPPER(LTRIM(RTRIM(s.ID_EQ)))    AS equipment_id,
        s.CONTRACTOR                    AS contractor,
        SUM(CAST(s.WORKING_HOURS AS float)) AS working_hours,
        SUM(CAST(s.STBY_HOURS    AS float)) AS standby_hours,
        SUM(CAST(s.BD_HOURS      AS float)) AS breakdown_hours,
        SUM(CAST(s.PM_HOURS      AS float)) AS pm_hours
FROM    EQUIPMENTS_HOURLY_STATUS s
WHERE   s.[DATE] BETWEEN '{start}' AND '{end}'
  AND   s.ID_EQ IS NOT NULL
GROUP BY CAST(s.[DATE] AS date), s.SHIFT,
         UPPER(LTRIM(RTRIM(s.ID_EQ))), s.CONTRACTOR
"""

# A truck-shift with under this many recorded hours is a partial record, not a
# low-availability shift, and averaging it in would bias the result downward.
MIN_HOURS = 1.0


def conn():
    import pymssql
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database="WBN_DATABASE",
                           login_timeout=10, timeout=1800, charset="LATIN1")


def extract(start="2026-04-01", end="2026-06-30") -> pd.DataFrame:
    """Pull the hours, caching the raw result.

    The VPN at this site drops repeatedly, and re-querying 16.5M rows to redo an
    analysis is both slow and needlessly fragile. The raw extract is cached per
    date window so the analysis can be re-run offline; the cache is keyed on the
    window so a different period cannot silently reuse it.
    """
    raw = os.path.join(DATA, "availability_raw_%s_%s.csv" % (start, end))
    if os.path.exists(raw):
        print("using cached extract %s" % os.path.basename(raw))
        d = pd.read_csv(raw)
    else:
        c = conn()
        try:
            d = pd.read_sql(SQL.format(start=start, end=end), c)
        finally:
            c.close()
        d.to_csv(raw, index=False)
    for col in ("working_hours", "standby_hours", "breakdown_hours", "pm_hours"):
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)
    d["total_hours"] = d[["working_hours", "standby_hours",
                          "breakdown_hours", "pm_hours"]].sum(axis=1)
    d = d[d["total_hours"] >= MIN_HOURS].copy()

    # TWO DIFFERENT RATIOS, BOTH REPORTED, BECAUSE THEY ANSWER DIFFERENT QUESTIONS.
    #
    # availability = the fraction of time the unit COULD work, i.e. was not
    # broken down or in planned maintenance. This is the fleet-readiness number a
    # maintenance manager owns.
    #
    # utilisation = the fraction of available time the unit ACTUALLY worked.
    # Standby counts against it, so this is the number an operations planner owns.
    #
    # The brief's formula (working / total) is utilisation-of-total, which conflates
    # the two: a truck idle on standby scores the same as one broken down, though
    # the responses are completely different. All three are published.
    d["availability"] = ((d.total_hours - d.breakdown_hours - d.pm_hours)
                         / d.total_hours)
    denom = (d.total_hours - d.breakdown_hours - d.pm_hours).clip(lower=1e-9)
    d["utilisation"] = d.working_hours / denom
    d["working_share_of_total"] = d.working_hours / d.total_hours
    # SHIFT arrives as a FLOAT (1.0 / 2.0), so comparing it to the string "2"
    # silently matched nothing and labelled every row "day" — which then made the
    # by-shift breakdown look like a single-shift operation. Both shifts are
    # present in equal numbers (269,297 vs 269,289). Cast numerically.
    sh = pd.to_numeric(d["shift"], errors="coerce")
    d["shift_label"] = np.where(sh == 2, "night",
                                np.where(sh == 1, "day", "unknown"))
    d["day_of_week"] = pd.to_datetime(d.work_date).dt.day_name()
    return d


def analyse(d: pd.DataFrame, haul_only: set | None = None) -> dict:
    """Summarise availability, reporting the SHAPE and not just the mean.

    The distribution is strongly bimodal and that is real, not a data artefact:
    records are complete (total hours median 12.0, min 8.0), yet 75.4% of
    truck-shifts sit at availability exactly 1.0 and 19.8% at exactly 0.0. A
    truck is either running that shift or it is down for the whole of it.

    A mean over that shape (0.72 for haul trucks) describes almost no individual
    shift. So the fraction of shifts fully down is reported alongside it, because
    "28% of truck-shifts are lost entirely" is the actionable form of the same
    fact, and averaging hides it.
    """
    def stats(x):
        x = x.dropna()
        return {"n": int(len(x)), "mean": round(float(x.mean()), 4),
                "min": round(float(x.min()), 4),
                "p25": round(float(x.quantile(.25)), 4),
                "median": round(float(x.median()), 4),
                "p75": round(float(x.quantile(.75)), 4),
                "max": round(float(x.max()), 4)}

    out = {"truck_shifts": int(len(d)),
           "equipment": int(d.equipment_id.nunique()),
           "date_range": [str(d.work_date.min()), str(d.work_date.max())],
           "all_equipment": {"availability": stats(d.availability),
                             "utilisation": stats(d.utilisation),
                             "working_share_of_total": stats(d.working_share_of_total)}}

    if haul_only:
        h = d[d.equipment_id.isin(haul_only)]
        out["haul_trucks"] = {
            "equipment": int(h.equipment_id.nunique()),
            "truck_shifts": int(len(h)),
            "availability": stats(h.availability),
            "utilisation": stats(h.utilisation),
        }
        # Per truck, so the spread across the fleet is visible rather than hidden
        # inside a single mean.
        # The bimodality is the finding, so quantify it rather than smoothing it.
        out["haul_trucks"]["shifts_fully_available"] = int((h.availability >= 0.999).sum())
        out["haul_trucks"]["shifts_fully_down"] = int((h.availability <= 0.001).sum())
        out["haul_trucks"]["pct_shifts_fully_down"] = round(
            100 * float((h.availability <= 0.001).mean()), 1)
        out["haul_trucks"]["distribution_note"] = (
            "bimodal: a truck is usually either up for the whole shift or down "
            "for the whole shift, so the mean describes few individual shifts")
        pt = h.groupby("equipment_id").availability.mean()
        out["haul_trucks"]["above_85pct"] = int((pt >= 0.85).sum())
        out["haul_trucks"]["below_85pct"] = int((pt < 0.85).sum())
        out["haul_trucks"]["per_truck_availability"] = stats(pt)
        for key, col in (("by_shift", "shift_label"),
                         ("by_day_of_week", "day_of_week"),
                         ("by_contractor", "contractor")):
            g = (h.groupby(col)
                  .agg(n=("availability", "size"),
                       availability=("availability", "mean"),
                       utilisation=("utilisation", "mean")).round(4))
            g = g[g.n >= 50].sort_values("availability", ascending=False)
            out["haul_trucks"][key] = json.loads(g.head(12).to_json(orient="index"))
    return out


def main():
    start, end = "2026-04-01", "2026-06-30"
    if len(sys.argv) > 2:
        start, end = sys.argv[1], sys.argv[2]
    print("extracting EQUIPMENTS_HOURLY_STATUS %s .. %s" % (start, end))
    d = extract(start, end)
    print("truck-shifts: %s across %d equipment units"
          % (format(len(d), ","), d.equipment_id.nunique()))

    haul = None
    try:
        tr = pd.read_csv(os.path.join(DATA, "trip_features.csv"),
                         usecols=["truck_id"])
        haul = set(tr.truck_id.astype(str).str.strip().str.upper())
        print("haul trucks known from the trip extract: %d" % len(haul))
    except Exception as e:                                   # noqa: BLE001
        print("could not load haul truck list: %s" % str(e)[:70])

    res = analyse(d, haul)
    d.to_csv(OUT_CSV, index=False)
    os.makedirs(REPORTS, exist_ok=True)
    res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=str)

    a = res["all_equipment"]
    print("\n=== ALL EQUIPMENT (%s truck-shifts) ===" % format(len(d), ","))
    for k in ("availability", "utilisation", "working_share_of_total"):
        s = a[k]
        print("   %-24s mean %.3f | p25 %.3f | median %.3f | p75 %.3f"
              % (k, s["mean"], s["p25"], s["median"], s["p75"]))

    if "haul_trucks" in res:
        h = res["haul_trucks"]
        print("\n=== HAUL TRUCKS ONLY (%d units, %s truck-shifts) ==="
              % (h["equipment"], format(h["truck_shifts"], ",")))
        print("   availability  mean %.3f | median %.3f | p25 %.3f | p75 %.3f"
              % (h["availability"]["mean"], h["availability"]["median"],
                 h["availability"]["p25"], h["availability"]["p75"]))
        print("   utilisation   mean %.3f | median %.3f"
              % (h["utilisation"]["mean"], h["utilisation"]["median"]))
        print("   trucks at or above 85%% availability: %d | below: %d"
              % (h["above_85pct"], h["below_85pct"]))
        print("\n   by shift:")
        for k, v in (h.get("by_shift") or {}).items():
            print("      %-8s n=%6d  avail %.3f  util %.3f"
                  % (k, v["n"], v["availability"], v["utilisation"]))
        print("   by contractor (top):")
        for k, v in list((h.get("by_contractor") or {}).items())[:6]:
            print("      %-14s n=%6d  avail %.3f  util %.3f"
                  % (str(k)[:14], v["n"], v["availability"], v["utilisation"]))
    print("\nwrote %s and %s" % (os.path.basename(OUT_CSV),
                                 os.path.basename(OUT_JSON)))
    return res


if __name__ == "__main__":
    main()
