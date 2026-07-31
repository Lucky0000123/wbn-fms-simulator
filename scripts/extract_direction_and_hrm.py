"""Cache the two DB extracts this round needs, so the analysis needs no VPN again.

    data/congestion_seg_by_dir.csv   per (SEG_ID, DIR) segment speeds
    data/hrm_by_section_day.csv      HRM units per (DATE, SHIFT, SECTIONKM)
    data/hrm_haulage_daily.csv       trips + fleet per (route, DATE) for the
                                     window HRM actually covers
    reports/direction_hrm_spans.json coverage spans, so a later reader can see
                                     what was and was not joinable

WHY A SCRIPT AND NOT AN AD-HOC QUERY: the VPN to 10.211.10.1 drops every few
minutes and did so mid-analysis twice while this was written. Every query is
retried, and every result is cached, so the correlation work below never needs
the link a second time.

WHY THE `DIR` SPLIT MATTERS: FMS_CONGESTION_SEG carries DIR in {'down','up'} and
the congestion endpoint aggregated over it, so loaded and empty speeds were
averaged together. Measured here: 100.0% of loaded corridor hauls run
DOWN-chainage (298,340 trips, zero counter-examples), so 'down' is the loaded
direction and 'up' the empty return. That inference is verified against the
ticket data rather than assumed from the word.
"""
import json
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")

ENVF = "/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env"


def creds():
    """Env vars first; fall back to reading the SSD .env at runtime.

    Never hardcoded and never written to disk -- the mirror is public. The .env
    names the password FMS_DB_PWD, so it must be mapped.
    """
    h, u, p = (os.environ.get("FMS_DB_HOST"), os.environ.get("FMS_DB_USER"),
               os.environ.get("FMS_DB_PASS"))
    if h and u and p:
        return h, u, p
    if not os.path.exists(ENVF):
        sys.exit("no credentials: FMS_DB_* unset and %s not mounted" % ENVF)
    vals = {}
    for line in open(ENVF):
        if "=" in line and line.split("=")[0].strip() in (
                "FMS_DB_HOST", "FMS_DB_USER", "FMS_DB_PWD"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("\r")
    return vals.get("FMS_DB_HOST"), vals.get("FMS_DB_USER"), vals.get("FMS_DB_PWD")


def fetch(db, sql, tries=6, wait=12):
    """Run a query, retrying through VPN drops. Returns a DataFrame."""
    import pymssql
    h, u, p = creds()
    last = None
    for i in range(tries):
        try:
            c = pymssql.connect(server=h, user=u, password=p, database=db,
                                login_timeout=8, timeout=180, charset="LATIN1")
            try:
                return pd.read_sql(sql, c)
            finally:
                c.close()
        except Exception as e:                                  # noqa: BLE001
            last = e
            print("   attempt %d/%d failed (%s); retrying in %ds"
                  % (i + 1, tries, str(e)[:70], wait))
            time.sleep(wait)
    raise SystemExit("gave up after %d attempts: %s" % (tries, str(last)[:200]))


def main():
    os.makedirs(DATA, exist_ok=True)
    spans = {}

    # ---- 1. segment speed BY DIRECTION -------------------------------------
    print("1/4 segment speeds by direction ...")
    seg = fetch("FMS_DB", """
        SELECT SEG_ID, LTRIM(RTRIM(DIR)) AS DIR,
               SUM(SUM_SPD) AS sum_spd, SUM(FIX_N) AS fix_n,
               SUM(SUM_TRAV_MS) AS sum_trav_ms, SUM(TRAV_N) AS trav_n,
               MAX(TRUCK_N) AS peak_trucks, AVG(CAST(TRUCK_N AS float)) AS mean_trucks,
               COUNT(*) AS hours, MIN(HOUR_TS) AS ts_min, MAX(HOUR_TS) AS ts_max
        FROM dbo.FMS_CONGESTION_SEG
        WHERE FIX_N > 0 AND TRUCK_N > 0
        GROUP BY SEG_ID, LTRIM(RTRIM(DIR))""")
    seg["speed_kmh"] = (seg.sum_spd / seg.fix_n).round(2)
    seg.to_csv(os.path.join(DATA, "congestion_seg_by_dir.csv"), index=False)
    print("    %d rows, %d segments, DIR values %s"
          % (len(seg), seg.SEG_ID.nunique(), sorted(seg.DIR.unique())))
    spans["congestion_seg"] = {
        "rows": int(len(seg)), "segments": int(seg.SEG_ID.nunique()),
        "dirs": sorted(seg.DIR.unique().tolist()),
        "ts_min": int(seg.ts_min.min()), "ts_max": int(seg.ts_max.max())}

    # ---- 2. HRM activity per section-day -----------------------------------
    print("2/4 HRM supervision ...")
    hrm = fetch("FMS_DB", """
        SELECT CAST(DATE AS date) AS d, SHIFT, SECTIONKM, ZONE, DIRECTION,
               EQUIPMENT_TYPE, EQUIPMENT_ID, HOURS, DISTANCE_M, ACTIVITY
        FROM dbo.FMS_HRM_SUPERVISION
        WHERE SECTIONKM IS NOT NULL""")
    hrm.to_csv(os.path.join(DATA, "hrm_raw.csv"), index=False)
    print("    %d rows, %s .. %s, %d equipment types"
          % (len(hrm), hrm.d.min(), hrm.d.max(), hrm.EQUIPMENT_TYPE.nunique()))
    spans["hrm"] = {"rows": int(len(hrm)), "date_min": str(hrm.d.min()),
                    "date_max": str(hrm.d.max()),
                    "days": int(hrm.d.nunique()),
                    "units": int(hrm.EQUIPMENT_ID.nunique()),
                    "types": hrm.EQUIPMENT_TYPE.value_counts().to_dict()}

    # Units per section-day. A "unit working a section" is a distinct
    # EQUIPMENT_ID with any recorded activity on that SECTIONKM that day --
    # counting rows instead would just measure telemetry chattiness.
    per = (hrm.groupby(["d", "SECTIONKM"])
              .agg(hrm_units=("EQUIPMENT_ID", "nunique"),
                   hrm_hours=("HOURS", "sum"),
                   hrm_rows=("EQUIPMENT_ID", "size"))
              .reset_index())
    per.to_csv(os.path.join(DATA, "hrm_by_section_day.csv"), index=False)
    print("    -> %d section-days" % len(per))

    # ---- 3. haulage over the HRM window ------------------------------------
    # HAULAGE (the wide table) runs later than HAULAGE_IWIP_CLEAN, so it is the
    # only one that can overlap the HRM window at all. Whether it actually does
    # is the question the correlation depends on, so the span is recorded even
    # when the answer is "not at all".
    print("3/4 haulage spans ...")
    sp = fetch("WBN_DATABASE", """
        SELECT 'IWIP_CLEAN' AS t, MIN(DATE) AS d0, MAX(DATE) AS d1, COUNT(*) AS n
        FROM dbo.HAULAGE_IWIP_CLEAN
        UNION ALL
        SELECT 'HAULAGE', MIN(DATE), MAX(DATE), COUNT(*) FROM dbo.HAULAGE""")
    print(sp.to_string(index=False))
    spans["haulage"] = sp.astype(str).to_dict("records")

    print("4/4 per-route daily trips over the HRM window ...")
    d0, d1 = str(hrm.d.min()), str(hrm.d.max())
    daily = fetch("WBN_DATABASE", """
        SELECT CAST(DATE AS date) AS d, SHIFT, ORIGIN_AREA, DESTINATION_AREA,
               COUNT(*) AS trips, COUNT(DISTINCT TRUCK_ID) AS trucks, SUM(WMT) AS wmt
        FROM dbo.HAULAGE
        WHERE DATE >= '%s' AND DATE <= '%s'
        GROUP BY CAST(DATE AS date), SHIFT, ORIGIN_AREA, DESTINATION_AREA""" % (d0, d1))
    daily.to_csv(os.path.join(DATA, "hrm_haulage_daily.csv"), index=False)
    print("    %d route-shift-days over %s .. %s" % (len(daily), d0, d1))
    spans["haulage_over_hrm_window"] = {
        "rows": int(len(daily)),
        "date_min": str(daily.d.min()) if len(daily) else None,
        "date_max": str(daily.d.max()) if len(daily) else None,
        "days": int(daily.d.nunique()) if len(daily) else 0}

    with open(os.path.join(REPORTS, "direction_hrm_spans.json"), "w") as fh:
        json.dump(spans, fh, indent=2, default=str)
    print("\nwrote data/congestion_seg_by_dir.csv, data/hrm_raw.csv,")
    print("      data/hrm_by_section_day.csv, data/hrm_haulage_daily.csv,")
    print("      reports/direction_hrm_spans.json")


if __name__ == "__main__":
    main()
