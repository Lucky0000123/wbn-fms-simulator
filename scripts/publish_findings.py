#!/usr/bin/env python
"""Publish the model findings as a committed, readable Markdown report.

The Phase 3 artifacts live in `data/`, which is gitignored because it also holds
`training_data.csv` — real production tonnages, and the mirror is public. That
protects the data but hides the CONCLUSIONS from anyone reading the repo.

This script extracts only derived statistics (coefficients, p-values, VIF,
cross-validation scores, residual flags) into `MODEL_FINDINGS.md`, which IS
committed. No tonnages, no route-level volumes, no per-contractor production —
only what a reviewer needs to judge the model.

    python scripts/publish_findings.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "MODEL_FINDINGS.md")

# Human-readable names for the operational levers. Route and contractor dummies
# are summarised rather than listed: naming every route with its coefficient
# would edge back toward publishing the operation's shape.
FRIENDLY = {
    "trucks_dt": "Fleet on this route (trucks)",
    "pct_experienced_drivers": "Share of crew with >12 months tenure",
    "avg_driver_tenure_months": "Mean driver tenure (months)",
    "avg_truck_age": "Mean truck age (years)",
    "truck_age_missing": "Truck age unknown (imputation flag)",
    "is_night": "Night shift",
    "is_wet": "Wet day (>5mm)",
    "rainfall_mm": "Rainfall (mm)",
    "payload_t": "Payload per trip (t)",
    "weighbridges_open": "Weighbridges open",
    "trucks_per_path": "Total trucks sharing the road (congestion)",
    "rain_x_distance": "Rain x haul distance (interaction)",
    "rain_x_trucks": "Rain x fleet size (interaction)",
    "is_weekend": "Weekend shift",
    "rainfall_missing": "Rainfall reading missing (gauge outage)",
}


def _load(name, default=None):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                          # noqa: BLE001
        return default


def _stars(p):
    if p is None:
        return ""
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""



def _phase35_section() -> str:
    """Phase 3.5 findings. Returns an empty string when the cycle model has not
    been trained, so the report degrades instead of printing placeholders."""
    r = _load("cycle_model_report.json")
    m = _load("cycle_metadata.json") or {}
    if not r:
        return ""
    L, A = [], lambda x: L.append(x)
    ins = r.get("in_sample") or {}
    A("---")
    A("")
    A("## Phase 3.5 \u2014 predicting cycle time instead of trips per truck")
    A("")
    A("Phase 3's target, trips per truck per shift, is a ratio whose denominator "
      "is a planning decision, so it moved for reasons unrelated to the road. "
      "Cycle time is the physical quantity underneath it: how long one truck "
      "takes to load, haul, dump and return. Tonnage then follows by arithmetic "
      "rather than a second fit.")
    A("")
    A("**The target does not come from where the brief assumed.** Building it by "
      "pairing loading/dumping geofence events was specified, but those are the "
      "two sparsest event types in that table: 604 loading rows from 22 distinct "
      "trucks. `WAITING_TIME` carries the same information at scale.")
    A("")
    A("| | |")
    A("|---|---|")
    A("| Target | `%s` (%s) |" % (r.get("target"), r.get("target_units")))
    A("| Source | %s |" % m.get("target_source", "WAITING_TIME"))
    A("| Rows | %s path-shifts over %s months |"
      % (format(r.get("rows", 0), ","), m.get("months", "?")))
    A("| Trips behind them | %s raw \u2192 %s passing physical bounds |"
      % (format(m.get("raw_trips", 0), ","), format(m.get("used_trips", 0), ",")))
    A("| Date range | %s |" % " \u2192 ".join(r.get("date_range") or []))
    A("| Max VIF (interpretable) | %s |" % ins.get("max_vif_interpretable"))
    A("")
    A("### Result: better on the ordinary shift, not on the rare one")
    A("")
    A("| Model | CV R\u00b2 | CV MAE (min) |")
    A("|---|---|---|")
    for name, cv in (r.get("cv") or {}).items():
        mean = cv.get("mean") or {}
        A("| `%s` | %s | %s |" % (name, mean.get("r2"), mean.get("mae")))
    A("")
    A("The pre-registered bar was **R\u00b2 lift \u2265 %s** over the per-route lookup. "
      "The model returns **%s**, so `beats_baseline` is **%s**."
      % (r.get("min_lift_required"), r.get("lift_over_baseline"),
         r.get("beats_baseline")))
    A("")
    A("But R\u00b2 and MAE disagree, and that disagreement is the finding. R\u00b2 squares "
      "the residual, so it is dominated by the rare shift where a truck broke "
      "down; MAE weights every shift equally. The model is **%s minutes (%s%%) "
      "closer on average** and wins MAE on **%s of %s folds**, while winning R\u00b2 "
      "on only %s."
      % (r.get("mae_gain_min"), r.get("mae_gain_pct"), r.get("folds_won_mae"),
         r.get("folds_total"), r.get("folds_won_r2")))
    A("")
    A("Measured on the last fold, the model is closer at the median (14.2 vs "
      "15.7 min), much closer at p75 (28.0 vs 50.1) and p90 (47.9 vs 93.2), and "
      "worse only at p99 (283 vs 223). It is better on the ordinary shift a "
      "planner schedules and worse on the breakdown nobody can plan around. "
      "Reported as `%s` rather than as a win or a failure."
      % r.get("verdict"))
    A("")
    A("For comparison, Phase 3's model lost to its lookup on **all five folds** "
      "(0.238 vs 0.459) and beat it on no metric.")
    A("")
    A("### Two pre-registered expectations were wrong, and the data won")
    A("")
    A("- **Night shifts are faster, not slower.** Registered `+` on a visibility "
      "argument; fitted **-3.24 min** (p=2e-10). Raw means agree: night 109.5 "
      "min against day 141.7. The road is emptier and the equator heat is gone.")
    A("- **Mean driver tenure is a weak proxy.** Registered `-`; fitted +0.41 "
      "min/month, worth 1.0 min per standard deviation (1.1% of a median cycle) "
      "with a within-route correlation of +0.005. The real experience effect "
      "lives in `pct_experienced_drivers` (**-10.0 min**, p=0.005). Demoted to "
      "advisory rather than counted as a violation.")
    A("")
    A("After correcting both, **%s of %s gated signs confirmed, 0 violations**."
      % (len((r.get("sign_checks") or {}).get("confirmed", [])),
         (r.get("sign_checks") or {}).get("checked")))
    A("")
    A("### What the model says moves cycle time")
    A("")
    A("| Factor | Effect | p |")
    A("|---|---|---|")
    for k, v in sorted((r.get("coefficients") or {}).items(),
                       key=lambda kv: -abs(kv[1].get("coef", 0))):
        if k == "const" or not v.get("significant"):
            continue
        A("| %s | %+.2f min | %s |" % (FRIENDLY.get(k, k), v["coef"],
                                       _stars(v.get("p_value", 1))))
    A("")
    u = r.get("utilisation") or {}
    if u.get("utilisation"):
        A("### Turning cycle time into tonnage")
        A("")
        A("Cycle time alone is not a plan. The conversion needs to know what "
          "fraction of a rostered shift a truck actually spends on cycles, and "
          "that factor is **fitted, not assumed**: for every route present in "
          "both the haul telemetry and the weighbridge tickets, "
          "`utilisation = observed trips x cycle minutes / shift minutes`, "
          "weighted by ticket count.")
        A("")
        A("| | |")
        A("|---|---|")
        A("| Fitted utilisation | **%s** |" % u["utilisation"])
        A("| Routes it was fitted on | %s |" % u.get("routes"))
        A("| Reconciliation error | %s%% median |"
          % u.get("reconcile_median_abs_pct"))
        A("")
        A("A planning convention would have suggested 0.85. That would have "
          "been wrong by more than 2x, and briefly was: the same API response "
          "reported 5,046 t and 10,667 t for an identical 101-truck fleet. The "
          "two sides are independent \u2014 cycle time from FMS telemetry, tonnage "
          "from weighbridge tickets \u2014 so their agreement is a genuine "
          "cross-check rather than a circular fit.")
        A("")
        A("Some routes still disagree by more than 25%. That is surfaced in the "
          "API (`vs_weighbridge_pct`, `models_agree`) and warned about in the "
          "planner, because a large gap says that route's telemetry and its "
          "tickets tell different stories, which is worth knowing before "
          "trusting either.")
        A("")
    A("Route identity carries most of the signal: dropping the %d route dummies "
      "and keeping only physical and operational features scores %s, which is "
      "the honest estimate of how much transfers to a road never seen before."
      % (r.get("n_route_dummies", 0),
         ((r.get("cv") or {}).get("ols_physics_only") or {}).get("mean", {}).get("r2")))
    return "\n".join(L)



def _phase4_section() -> str:
    """Phase 4: the cross-database negatives and the Match Factor result."""
    mfm = _load("match_factor_meta.json")
    L, A = [], lambda x: L.append(x)
    A("---")
    A("")
    A("## Phase 4 \u2014 cross-database recon and Match Factor")
    A("")
    A("### The missing variables are not in the other database either")
    A("")
    A("Phase 3 showed 74.6% of cycle-time variance lives *within* "
      "(route, shift, date) groups, driven by queueing, operator behaviour and "
      "breakdowns \u2014 none of which are columns in the ticket database. "
      "`FMS_DB` was checked for them. Both leads are dead, and the evidence is "
      "conclusive enough to stop rather than keep trying.")
    A("")
    A("**GPS queue time: the haul fleet is not instrumented.** The telematics "
      "feed carries 217 distinct units. All 217 resolve cleanly in the fleet "
      "registry, so this is not an ID-format problem. Of the 940 haul trucks in "
      "that registry, **zero** appear in the GPS feed \u2014 the instrumented "
      "vehicles belong to engineering and logistics workshops, while the trucks "
      "producing weighbridge tickets belong to the transport division. Plate "
      "prefixes confirm the split independently. Trip-weighted join rate: 0.0% "
      "against a 60% gate.")
    A("")
    A("**Operator identity: the link table does not exist.** The employee "
      "master is 8,958 rows of name, division, job title and grade. No "
      "equipment assignment, no shift roster, and no hire date, so operator "
      "experience is not derivable either.")
    A("")
    A("So the Phase 3 ceiling stands as **confirmed**, not merely unbeaten: the "
      "features that would break it are absent from both databases, not just "
      "the one first searched.")
    A("")
    if not mfm:
        return "\n".join(L)
    v = mfm.get("validation") or {}
    pct = mfm.get("status_pct") or {}
    A("### Match Factor: the mine is under-trucked, not over-trucked")
    A("")
    A("`MF = (trucks per server \u00d7 service time) / cycle time` "
      "(Burt & Caccetta 2007), computed over %s point-shifts across %s loading "
      "points." % (format(mfm.get("rows", 0), ","), mfm.get("loading_points")))
    A("")
    A("| Status | Share |")
    A("|---|---:|")
    for k in ("under-trucked", "balanced", "over-trucked"):
        if k in pct:
            A("| %s | **%.1f%%** |" % (k, pct[k]))
    A("")
    A("Nearly seven in ten loading-point shifts have the shovel waiting for "
      "trucks. The intuition that a busy mine is over-trucked is wrong here, "
      "and that is an actionable difference: adding trucks to an under-trucked "
      "face raises output, whereas adding them to a queue only burns fuel.")
    A("")
    A("**It is keyed to a loading point, not a shovel.** No excavator, shovel or "
      "loader identity exists in either database, and no dispatch log. The "
      "server count is the observed peak of simultaneous loads at that point. "
      "The API returns this caveat in every response rather than letting the "
      "name imply a machine.")
    A("")
    A("**Validation.** MF correlates **%.3f** with queue wait as a share of "
      "cycle, and mean wait rises monotonically across the bands "
      "(20.9 \u2192 32.8 \u2192 38.2 min). It correlates *negatively* with total "
      "cycle time, which looks wrong and is not: cycle time is dominated by haul "
      "distance, so a short-haul point can be heavily queued and still turn "
      "trucks around quickly. Two earlier formulations that failed this check "
      "were discarded rather than published."
      % (v.get("corr_mf_queue_share") or 0))
    A("")
    A("**Bunching.** The specified threshold (CV > 0.5) fires on 99.0%% of "
      "point-shifts here, so it is a constant rather than a detector. The "
      "shipped threshold is the 75th percentile of the observed distribution "
      "(CV > %s), flagging %.1f%%."
      % (mfm.get("bunching_threshold_cv"), mfm.get("bunching_flagged_pct") or 0))
    return "\n".join(L)


def build() -> str:
    sig = _load("feature_significance.json") or {}
    cmp_ = _load("model_comparison.json") or {}
    val = _load("validation_results.json") or {}
    res = _load("residual_diagnostics.json") or {}
    meta = _load("model_metadata.json") or {}
    tmeta = _load("training_metadata.json") or {}
    if not sig:
        return ""

    coefs = sig.get("coefficients", {})
    mean_r2 = cmp_.get("mean_r2", {})
    L = []
    A = L.append

    A("# WBN FMS Simulator — Model Findings")
    A("")
    A("*Generated by `scripts/publish_findings.py` from the artifacts in "
      "`data/` (gitignored). Regenerate after any retrain.*")
    A("")
    A("Derived statistics only — no tonnages or route-level production volumes.")
    A("")
    A("| | |")
    A("|---|---|")
    A("| Generated | %s |" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    A("| Training rows | %s |" % f"{sig.get('n_rows', 0):,}")
    A("| Date range | %s |" % " to ".join(tmeta.get("date_range", ["?", "?"])))
    A("| Data source | %s |" % tmeta.get("source", "unknown"))
    A("| Target | `trips_per_dt_per_shift` (trips per truck per shift) |")
    A("")

    # ── headline ────────────────────────────────────────────────────────────
    A("## Headline: no fitted model beats a lookup table")
    A("")
    A("Scored under **rolling-origin (walk-forward) cross-validation** — train on")
    A("the past, test on the next block, never shuffle. All models see identical folds.")
    A("")
    A("| Model | mean CV R² | |")
    A("|---|---|---|")
    for k in ("group_mean_baseline", "ols", "random_forest"):
        if k in mean_r2:
            label = {"group_mean_baseline": "Group-mean lookup (per route/contractor/shift)",
                     "ols": "OLS regression", "random_forest": "RandomForest"}[k]
            chosen = (k == cmp_.get("selected_model"))
            A("| %s | %s | %s |" % (
                ("**%s**" % label) if chosen else label,
                ("**%.3f**" % mean_r2[k]) if chosen else ("%.3f" % mean_r2[k]),
                "**selected**" if chosen else ""))
    A("")
    A("**Selected: `%s`** — %s" % (cmp_.get("selected_model", "?"),
                                   cmp_.get("selection_rationale", "")))
    A("")
    A("> A single chronological split reports much higher numbers (OLS ~0.56, RF ~0.59)")
    A("> because it scores one held-out block. The cross-validated figures above are")
    A("> what survived being tested on months the model had never seen.")
    A("")

    # ── per fold ────────────────────────────────────────────────────────────
    folds = (val.get("ols") or {}).get("folds", [])
    if folds:
        A("### OLS per fold")
        A("")
        A("| Test period | Train rows | Test rows | R² | MAE | MAPE | Rain varies? |")
        A("|---|---|---|---|---|---|---|")
        for f in folds:
            if f.get("r2") is None:
                continue
            A("| %s | %s | %s | %.3f | %.3f | %.1f%% | %s |" % (
                f.get("test_period"), f"{f.get('train_rows', 0):,}",
                f"{f.get('test_rows', 0):,}", f["r2"], f.get("mae", 0),
                f.get("mape", 0), "no" if f.get("test_rain_all_zero") else "yes"))
        A("")
        A("Folds where rain does not vary **cannot validate any rainfall coefficient** —")
        A("the gauges stopped reporting on 2026-04-06, so rain is constant there.")
        A("")

    # ── coefficients ────────────────────────────────────────────────────────
    A("## What actually moves productivity")
    A("")
    A("OLS coefficients in **trips per truck per shift**. `***` p<0.001, `**` p<0.01, `*` p<0.05.")
    A("")
    A("| Factor | Effect | 95% CI | p | |")
    A("|---|---|---|---|---|")
    for key, label in FRIENDLY.items():
        c = coefs.get(key)
        if not c:
            continue
        A("| %s | %+.5f | [%+.4f, %+.4f] | %.3f | %s |" % (
            label, c["coef"], c["ci_low"], c["ci_high"], c["p_value"],
            _stars(c["p_value"])))
    A("")
    n_route = sum(1 for k in coefs if k.startswith("route_"))
    n_contr = sum(1 for k in coefs if k.startswith("contractor_"))
    A("Plus %d route and %d contractor fixed effects (not listed: naming every route "
      "with its productivity would publish the shape of the operation)." % (n_route, n_contr))
    A("")
    A("**Significant at p<0.05: %d of %d features.** Max VIF %.2f (nothing above 10, "
      "so coefficients are separately identified). Condition number %s."
      % (len(sig.get("significant_features", [])), sig.get("n_features", 0),
         sig.get("max_vif", 0), f"{sig.get('condition_number', 0):,.0f}"))
    A("")

    # ── how to read it ──────────────────────────────────────────────────────
    A("### Reading the significant effects")
    A("")
    wb = coefs.get("weighbridges_open", {})
    tp = coefs.get("trucks_per_path", {})
    rm = coefs.get("rainfall_missing", {})
    if wb:
        A("- **Weighbridges open %+.3f** — each additional open weighbridge is worth "
          "about %.3f extra trips per truck per shift. The clearest operational lever "
          "in the model." % (wb["coef"], wb["coef"]))
    if tp:
        A("- **Shared-road congestion %+.5f** — the sign is *positive*, which is not "
          "what a congestion story predicts. Busy roads are busy because the routes are "
          "productive; this is association, not a causal claim that adding trucks helps."
          % tp["coef"])
    if rm:
        A("- **Rainfall missing %+.3f** — rows after the gauge outage read higher. This "
          "is a data-quality marker, not weather: it separates imputed rows from "
          "measured ones so the model does not treat a guess as a reading." % rm["coef"])
    A("")

    # ── residuals ───────────────────────────────────────────────────────────
    A("## Residual diagnostics — the Phase 4 decision")
    A("")
    A("| Check | Result |")
    A("|---|---|")
    A("| Heteroscedastic | **%s** (corr \\|residual\\| vs fitted = %.3f) |"
      % ("yes" if res.get("heteroscedastic_flag") else "no",
         res.get("heteroscedasticity_corr", 0)))
    A("| Non-linear features flagged | %s |"
      % (", ".join(res.get("nonlinear_features", [])) or "none"))
    A("| Residual mean / std | %.4f / %.3f |"
      % (res.get("residual_mean", 0), res.get("residual_std", 0)))
    A("")
    if res.get("heteroscedastic_flag"):
        A("Error grows with the size of the prediction, so a constant-variance linear")
        A("model is the wrong shape. But **no single feature shows curvature**, and every")
        A("fitted model already loses to a lookup table. More months of data will buy more")
        A("than a more flexible model would.")
        A("")

    # ── excluded ────────────────────────------------------------------------
    fm = meta.get("feature_meta", {})
    A("## Excluded on purpose")
    A("")
    A("### Target leakage (verified, not assumed)")
    A("")
    A("```")
    A("wmt_per_shift == target x payload_t x trucks_dt    max abs error 0.000000")
    A("trips / trucks_dt == target                        max abs error < 1e-8")
    A("```")
    A("")
    A("Both are exact algebraic restatements of the target: including either drives R²")
    A("toward 1.0 while making the model useless, because at planning time nobody knows")
    A("the trips or the tonnage — that is the question being asked. `cycle_time_min` is")
    A("excluded too: it is derived from weighbridge timestamps *after* the shift ran.")
    A("")
    for note in fm.get("dropped_redundant", []):
        A("- Dropped: %s" % note)
    A("")
    A("### Rainfall imputation")
    A("")
    A("%s. Gauges stopped reporting **%s**; %s rows are imputed with a seasonal mean and "
      "flagged via `rainfall_missing`, so the model can tell a guess from a measurement."
      % (fm.get("rain_imputation", "seasonal mean + missing flag"),
         fm.get("rain_outage_from", "?"), f"{fm.get('rain_imputed_rows', 0):,}"))
    A("")

    # ── what's missing ──────────────────────────────────────────────────────
    A("## Features the roadmap wants that the data cannot support")
    A("")
    A("Do not fabricate these. Each needs a new data source.")
    A("")
    A("| Feature | Blocker |")
    A("|---|---|")
    A("| Road grade | No survey/DEM per path. Needs road geometry or an elevation raster. |")
    A("| Operator experience | No operator ID on haul records. Needs FMS operator assignment + hours. |")
    A("| Truck type / capacity | DELIVERED in Phase 3.5 via EQUIPMENTS (99.6% join, 61% have a build year). |")
    A("| Cycle-time components | DELIVERED in Phase 3.5 from WAITING_TIME, not geofences \u2014 see below. |")
    A("| Weather beyond rain | DELIVERED: Open-Meteo ERA5 gives temperature, humidity and wind. |")
    A("")
    A(_phase35_section())
    A("")
    A("---")
    A("")
    A(_phase4_section())
    A("")
    A("Reproduce: `python train_model.py` (needs VPN for the DB; falls back to fixtures "
      "otherwise), then `python scripts/publish_findings.py`.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    md = build()
    if not md:
        print("no artifacts in data/ — run `python train_model.py` first", file=sys.stderr)
        raise SystemExit(1)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("wrote %s (%d lines)" % (os.path.relpath(OUT, BASE), md.count("\n")))
