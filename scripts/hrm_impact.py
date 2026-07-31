"""Does road-maintenance (HRM) activity measurably change haulage productivity?

The site owner's question, and his own prior: "I want to add the impact of HRM
fleet... number of HRM units working in specific areas... Not sure if we will be
able to see any correlation, but you can check. If not we can exclude." Plus the
methodological instruction that matters most here: "fleet size needs to be the
same when you do the correlation test."

That instruction is the whole design. Trips per truck is mechanically related to
how many trucks are on the route, and HRM crews are dispatched to roads that are
busy or broken -- both correlate with fleet size, so an uncontrolled correlation
would measure dispatch policy, not road condition. This is the same endogeneity
that made raw congestion appear to SPEED UP haulage.

Two independent controls are run, because either alone can mislead:

  1. MATCHED FLEET BINS -- compare only route-days whose truck count is within
     +-2 of each other, then correlate within each bin and pool. This is what
     the owner asked for.
  2. PARTIAL CORRELATION -- correlate HRM units with trips/DT after regressing
     truck count out of both. Uses all rows, so it is better powered, and it
     cross-checks the binned result rather than replacing it.

Reads only cached CSVs (scripts/extract_direction_and_hrm.py), so it needs no
VPN. Writes reports/hrm_impact_analysis.md and reports/hrm_impact.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from prediction_pipeline import canonical_area          # noqa: E402

DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")

# Corridor chainage of the nodes a route can name. A route is treated as
# occupying the KM span between its two ends; HRM work on sections inside that
# span is what could plausibly affect it.
KM = {"TF": 67.8, "KR": 39.0, "POS 12": 27.0, "POS 10": 17.0,
      "FENI KM15": 15.0, "FENI KM0": 0.0}

MIN_ROWS = 30          # below this a correlation is theatre
FLEET_TOL = 2          # "same fleet size" per the owner's instruction


def load():
    hrm = pd.read_csv(os.path.join(DATA, "hrm_raw.csv"))
    haul = pd.read_csv(os.path.join(DATA, "hrm_haulage_daily.csv"))
    return hrm, haul


def build_panel(hrm, haul):
    hrm = hrm.dropna(subset=["SECTIONKM"]).copy()
    hrm["d"] = pd.to_datetime(hrm["d"]).dt.date

    haul = haul.copy()
    haul["d"] = pd.to_datetime(haul["d"]).dt.date
    haul["o"] = haul.ORIGIN_AREA.map(canonical_area)
    haul["dd"] = haul.DESTINATION_AREA.map(canonical_area)
    haul["okm"] = haul.o.map(KM)
    haul["dkm"] = haul.dd.map(KM)
    haul = haul.dropna(subset=["okm", "dkm"])
    haul = haul[haul.okm != haul.dkm]
    haul = haul[(haul.trucks > 0) & (haul.trips > 0)]
    haul["route"] = haul.o + ">" + haul.dd
    haul["trips_per_dt"] = haul.trips / haul.trucks
    haul["lo"] = haul[["okm", "dkm"]].min(axis=1)
    haul["hi"] = haul[["okm", "dkm"]].max(axis=1)

    # HRM units per (date, section). A "unit working a section" is a distinct
    # EQUIPMENT_ID with any activity there that day -- counting rows would
    # measure telemetry chattiness, not work.
    per_sec = (hrm.groupby(["d", "SECTIONKM"])
                  .agg(units=("EQUIPMENT_ID", "nunique"),
                       hours=("HOURS", "sum"))
                  .reset_index())

    rows = []
    for _, r in haul.iterrows():
        m = per_sec[(per_sec.d == r.d)
                    & (per_sec.SECTIONKM >= r.lo) & (per_sec.SECTIONKM <= r.hi)]
        rows.append({
            "d": r.d, "route": r.route, "shift": r.SHIFT,
            "trips": r.trips, "trucks": r.trucks, "trips_per_dt": r.trips_per_dt,
            "span_km": r.hi - r.lo,
            "hrm_units": int(m.units.sum()) if len(m) else 0,
            "hrm_hours": float(m.hours.sum()) if len(m) else 0.0,
            "hrm_sections": int(len(m)),
        })
    return pd.DataFrame(rows)


def partial_corr(x, y, z):
    """corr(x, y) with z regressed out of both. Returns (r, p, n)."""
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[ok], y[ok], z[ok]
    n = len(x)
    if n < MIN_ROWS or np.std(z) == 0:
        return None, None, n
    zx = np.polyfit(z, x, 1)
    zy = np.polyfit(z, y, 1)
    rx = x - np.polyval(zx, z)
    ry = y - np.polyval(zy, z)
    r, p = stats.pearsonr(rx, ry)
    return float(r), float(p), n


def main():
    hrm, haul = load()
    panel = build_panel(hrm, haul)
    panel.to_csv(os.path.join(DATA, "hrm_panel.csv"), index=False)

    out = {"panel_rows": int(len(panel)),
           "days": int(panel.d.nunique()) if len(panel) else 0,
           "routes": int(panel.route.nunique()) if len(panel) else 0,
           "min_rows_required": MIN_ROWS, "fleet_tolerance": FLEET_TOL}
    print("panel: %d route-shift-days, %d days, %d routes"
          % (out["panel_rows"], out["days"], out["routes"]))

    if len(panel) < MIN_ROWS:
        out["verdict"] = "INSUFFICIENT DATA"
        json.dump(out, open(os.path.join(REPORTS, "hrm_impact.json"), "w"), indent=2, default=str)
        print("too few rows to test")
        return out

    # ---- 0. uncontrolled, shown ONLY to demonstrate why it is not the answer
    r0, p0 = stats.pearsonr(panel.hrm_units, panel.trips_per_dt)
    out["uncontrolled"] = {"r": round(float(r0), 4), "p": round(float(p0), 5),
                           "n": int(len(panel))}
    rt, pt = stats.pearsonr(panel.trucks, panel.hrm_units)
    out["confound_trucks_vs_hrm"] = {"r": round(float(rt), 4), "p": round(float(pt), 5)}
    print("uncontrolled   r=%+.4f p=%.4g   (trucks~hrm r=%+.4f p=%.4g)"
          % (r0, p0, rt, pt))

    # ---- 1. matched fleet bins, the owner's instruction
    binned = []
    for _, grp in panel.groupby(panel.trucks // (2 * FLEET_TOL + 1)):
        if len(grp) < MIN_ROWS or grp.hrm_units.std() == 0 or grp.trips_per_dt.std() == 0:
            continue
        r, p = stats.pearsonr(grp.hrm_units, grp.trips_per_dt)
        binned.append({"trucks_min": int(grp.trucks.min()),
                       "trucks_max": int(grp.trucks.max()),
                       "n": int(len(grp)), "r": round(float(r), 4),
                       "p": round(float(p), 5)})
    out["fleet_matched_bins"] = binned
    if binned:
        # Fisher z pooling, weighted by n-3, so bins are combined on the scale
        # where correlations are additive rather than averaged raw.
        z = np.array([np.arctanh(b["r"]) for b in binned])
        w = np.array([b["n"] - 3 for b in binned], dtype=float)
        zbar = float((z * w).sum() / w.sum())
        r_pool = float(np.tanh(zbar))
        se = float(1 / np.sqrt(w.sum()))
        p_pool = float(2 * (1 - stats.norm.cdf(abs(zbar / se))))
        out["fleet_matched_pooled"] = {
            "r": round(r_pool, 4), "p": round(p_pool, 5),
            "bins": len(binned), "n": int(sum(b["n"] for b in binned))}
        print("fleet-matched  r=%+.4f p=%.4g  (%d bins, n=%d)"
              % (r_pool, p_pool, len(binned), sum(b["n"] for b in binned)))
    else:
        out["fleet_matched_pooled"] = None
        print("fleet-matched  no bin reached %d rows" % MIN_ROWS)

    # ---- 2. partial correlation, controlling truck count
    r1, p1, n1 = partial_corr(panel.hrm_units.values.astype(float),
                              panel.trips_per_dt.values.astype(float),
                              panel.trucks.values.astype(float))
    out["partial_controlling_trucks"] = {"r": None if r1 is None else round(r1, 4),
                                         "p": None if p1 is None else round(p1, 5),
                                         "n": int(n1)}
    if r1 is not None:
        print("partial(trucks) r=%+.4f p=%.4g n=%d" % (r1, p1, n1))

    # ---- 3. same test on HRM hours, in case unit COUNT is the wrong dose
    r2, p2, n2 = partial_corr(panel.hrm_hours.values.astype(float),
                              panel.trips_per_dt.values.astype(float),
                              panel.trucks.values.astype(float))
    out["partial_hours_ROUTE_CONFOUNDED"] = {
        "r": None if r2 is None else round(r2, 4),
        "p": None if p2 is None else round(p2, 5), "n": int(n2),
        "warning": "SPURIOUS -- see route_length_confound; reported only to "
                   "document why it must not be believed"}
    if r2 is not None:
        print("partial hours   r=%+.4f p=%.4g n=%d   <-- SPURIOUS, see below"
              % (r2, p2, n2))

    # ---- 4. THE ROUTE-LENGTH CONFOUND, and the test that survives it.
    #
    # hrm_hours is SUMMED over the sections a route spans, so a long route
    # accumulates more HRM hours purely by being long -- and a long route also
    # completes fewer trips per truck, purely by being long. Measured here:
    # corr(span_km, hrm_hours) = +0.63 and corr(span_km, trips_per_dt) = -0.63.
    # Their product is about -0.40, which is essentially the whole of the
    # -0.46 "effect" above. It is route length wearing an HRM costume.
    #
    # The honest test removes the route entirely: demean HRM and trips/DT
    # WITHIN each route, so the only variation left is day-to-day change on the
    # same road, then still control fleet size. This is the number to quote.
    for a, b in (("span_km", "hrm_hours"), ("span_km", "trips_per_dt"),
                 ("span_km", "hrm_units")):
        rr, pp = stats.pearsonr(panel[a], panel[b])
        out.setdefault("route_length_confound", {})[f"{a}~{b}"] = {
            "r": round(float(rr), 4), "p": round(float(pp), 6)}
    print("confound       corr(span_km,hrm_hours)=%+.3f  corr(span_km,trips_per_dt)=%+.3f"
          % (out["route_length_confound"]["span_km~hrm_hours"]["r"],
             out["route_length_confound"]["span_km~trips_per_dt"]["r"]))

    within = {}
    for col in ("hrm_units", "hrm_hours"):
        d = panel.copy()
        dm = lambda s: s - s.groupby(d.route).transform("mean")     # noqa: E731
        r3, p3, n3 = partial_corr(dm(d[col]).values.astype(float),
                                  dm(d.trips_per_dt).values.astype(float),
                                  dm(d.trucks).values.astype(float))
        within[col] = {"r": None if r3 is None else round(r3, 4),
                       "p": None if p3 is None else round(p3, 5), "n": int(n3)}
        if r3 is not None:
            print("WITHIN-ROUTE   %-10s r=%+.4f p=%.4g n=%d" % (col, r3, p3, n3))
    out["within_route_controlling_trucks"] = within

    # ---- verdict, decided ONLY on the tests that survive the confound
    decisive = [v for v in (out.get("fleet_matched_pooled"),
                            out.get("partial_controlling_trucks"),
                            within.get("hrm_units"), within.get("hrm_hours"))
                if v and v.get("p") is not None and v["p"] < 0.05]
    out["significant_tests"] = len(decisive)
    out["tests_considered"] = 4
    out["verdict"] = ("NO MEASURABLE IMPACT" if not decisive
                      else "SIGNIFICANT IN %d OF 4 CONTROLLED TESTS" % len(decisive))
    out["note"] = ("partial_hours_ROUTE_CONFOUNDED is excluded from the verdict: "
                   "it is route length, not HRM activity.")
    print("VERDICT:", out["verdict"])

    json.dump(out, open(os.path.join(REPORTS, "hrm_impact.json"), "w"),
              indent=2, default=str)
    print("wrote reports/hrm_impact.json and data/hrm_panel.csv")
    return out


if __name__ == "__main__":
    main()
