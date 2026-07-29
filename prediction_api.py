"""
Phase 2 — prediction service.

Serves /api/predict and /api/retrain. All model maths stays here on the server;
the browser only renders what these endpoints return.

Design notes
  • The model, encoder and scaler are loaded ONCE into a process-level cache
    (`_MODEL`). Requests never touch disk, which keeps latency well under the
    100 ms budget. A retrain bumps the cache explicitly.
  • If no trained model exists — or anything at all goes wrong — the endpoint
    degrades to the per-path OLS already used by the Plan tab (the `a + b·DT`
    fit from /api/simulator/path-response) and sets `fallback: true`. The Plan
    tab therefore never loses its estimate, it only loses accuracy.
  • Reverse mode (target tonnage → fleet) solves by damped fixed-point, because
    trips/DT itself depends on fleet size, then rounds UP: you cannot run a
    fraction of a truck.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import prediction_pipeline as pp

try:                                                   # Phase 3.5, optional
    import cycle_serving as cycsrv
except Exception:                                      # noqa: BLE001
    cycsrv = None

bp = Blueprint("prediction_api", __name__)

MODEL_PKL = os.path.join(pp.DATA, "model.pkl")
MODEL_META = os.path.join(pp.DATA, "model_metadata.json")
CYCLE_REPORT = os.path.join(pp.DATA, "cycle_model_report.json")
# Mirrored from match_factor.py so the API never imports pandas on this path.
mf_TARGET_LO, mf_TARGET_HI, mf_OVER, mf_UNDER = 0.85, 1.00, 1.15, 0.75

_MODEL = None            # {"model", "meta", "instance", "loaded_at"}
_LOCK = threading.Lock()
_RETRAIN_LOCK = threading.Lock()

SHIFT_HOURS_DEFAULT = 12.0


# ── model cache ─────────────────────────────────────────────────────────────
def load_model(force: bool = False):
    """Load model + transformers once per process. Returns None when untrained."""
    global _MODEL
    if _MODEL is not None and not force:
        return _MODEL
    with _LOCK:
        if _MODEL is not None and not force:
            return _MODEL
        if not (os.path.exists(MODEL_PKL) and os.path.exists(MODEL_META)):
            return None
        try:
            import joblib
            model = joblib.load(MODEL_PKL)
            with open(MODEL_META, encoding="utf-8") as fh:
                meta = json.load(fh)
            pp.reset_transformers()
            pp.load_transformers()                    # warm the encoder/scaler too
            _MODEL = {"model": model, "meta": meta,
                      "instance": "%s-%d" % (meta.get("model_type", "?"), id(model)),
                      "loaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        except Exception as exc:                      # noqa: BLE001
            print("[prediction] could not load model: %s" % exc)
            return None
    return _MODEL


def invalidate_model():
    global _MODEL
    with _LOCK:
        _MODEL = None
    pp.reset_transformers()
    global _SELECTED_CACHE
    _SELECTED_CACHE = None


# ── fallback: the existing per-path OLS ─────────────────────────────────────
_PATH_FIT_CACHE = None


def _path_fits():
    """The a + b·DT per-path fits already exposed by /api/simulator/path-response.
    Used only when the trained model is unavailable."""
    global _PATH_FIT_CACHE
    if _PATH_FIT_CACHE is None:
        try:
            with open(os.path.join(pp.FX, "path-response.json"), encoding="utf-8") as fh:
                _PATH_FIT_CACHE = json.load(fh).get("paths", {})
        except Exception:                             # noqa: BLE001
            _PATH_FIT_CACHE = {}
    return _PATH_FIT_CACHE


def _fallback_trips_per_dt(source, destination, trucks, rainfall, shift_hours):
    """Original Plan-tab maths: avgTr + b·(DT − avgDT) + rain, day → shift."""
    fits = _path_fits()
    key = "%s>%s" % (pp._norm(source), pp._norm(destination))
    m = fits.get(key)
    if not m:
        return None, None
    tr = float(m.get("avgTr") or 0)
    if tr <= 0:
        return None, None
    b_adj, b = m.get("bAdj"), m.get("b")
    slope = b_adj if (isinstance(b_adj, (int, float)) and b_adj < 0) else (b if (isinstance(b, (int, float)) and b < 0) else 0)
    if slope and m.get("avgDt"):
        tr += slope * (float(trucks) - float(m["avgDt"]))
    if rainfall and isinstance(m.get("mWet"), (int, float)) and isinstance(m.get("mDry"), (int, float)):
        tr += (m["mWet"] - m["mDry"]) * (float(rainfall) / 10.0)
    tr = max(0.3 * float(m["avgTr"]), tr)
    tr *= 0.5 * (float(shift_hours) / SHIFT_HOURS_DEFAULT)     # day → single shift
    return tr, float(m.get("tf") or 0)


# ── payload lookup ──────────────────────────────────────────────────────────
_PAYLOAD_CACHE = None


def _payload_for(contractor, source, destination):
    """Tonnes per trip: the contractor's measured average where we have it,
    else the path's, else the fleet mean."""
    global _PAYLOAD_CACHE
    if _PAYLOAD_CACHE is None:
        by_contractor, fleet = {}, 45.0
        try:
            with open(os.path.join(pp.FX, "capability.json"), encoding="utf-8") as fh:
                cap = json.load(fh)
            for c in cap.get("contractorProd", []):
                name = pp._norm(c.get("contractor"))
                if c.get("tf"):
                    by_contractor[name] = float(c["tf"])
            fleet = float((cap.get("kpi") or {}).get("tf") or fleet)
        except Exception:                             # noqa: BLE001
            pass
        _PAYLOAD_CACHE = (by_contractor, fleet)
    by_contractor, fleet = _PAYLOAD_CACHE
    name = pp._norm(contractor)
    if name in by_contractor:
        return by_contractor[name], "contractor avg"
    m = _path_fits().get("%s>%s" % (pp._norm(source), pp._norm(destination)))
    if m and m.get("tf"):
        return float(m["tf"]), "path avg"
    return fleet, "fleet avg"


# ── core prediction ─────────────────────────────────────────────────────────
_SELECTED_CACHE = None


def _load_selected():
    """Load the model the rolling-origin comparison actually selected.

    Phase 3 judges OLS, RandomForest and the group-mean lookup under identical
    walk-forward folds. Whichever wins is what a planner should be answered
    with; serving a different one because it happened to look good on a single
    split is how a model ends up flattering itself in production.

    Returns None when the selection is the RandomForest (already served by the
    existing cache) or when the artifacts are absent.
    """
    global _SELECTED_CACHE
    if _SELECTED_CACHE is not None:
        return _SELECTED_CACHE or None
    bundle = load_model()
    sel = ((bundle or {}).get("meta") or {}).get("selected_model")
    if not sel or sel == "random_forest":
        _SELECTED_CACHE = {}
        return None
    try:
        import joblib
        if sel == "group_mean_baseline":
            _SELECTED_CACHE = {"kind": "baseline", "art": joblib.load(pp.BASELINE_PKL)}
        elif sel == "ols":
            _SELECTED_CACHE = {"kind": "ols", "art": joblib.load(pp.OLS_PKL)}
        else:
            _SELECTED_CACHE = {}
    except Exception as exc:                          # noqa: BLE001
        print("[prediction] could not load selected model '%s': %s" % (sel, exc))
        _SELECTED_CACHE = {}
    return _SELECTED_CACHE or None


def _predict_selected(payload: dict):
    """Predict with the CV-selected model. (value, model_name) or (None, None)."""
    sm_ = _load_selected()
    if not sm_:
        return None, None
    try:
        if sm_["kind"] == "baseline":
            art = sm_["art"]
            k = "|".join(str(payload.get(c, "")) for c in art["key"])
            v = art["table"].get(k)
            if v is None:                             # unseen cell -> fleet mean
                v = art["global_mean"]
            return float(v), "group_mean_baseline"
    except Exception as exc:                          # noqa: BLE001
        print("[prediction] selected-model inference failed: %s" % exc)
    return None, None


def _predict_trips_per_dt(payload: dict):
    """Model-based trips/DT/shift. Returns (value, used_model) or (None, False)."""
    # The CV winner answers first when it is not the RandomForest.
    val, name = _predict_selected(payload)
    if val is not None and val > 0:
        return val, True
    bundle = load_model()
    if not bundle:
        return None, False
    try:
        X = pp.transform_one(payload)
        return float(bundle["model"].predict(X)[0]), True
    except Exception as exc:                          # noqa: BLE001
        print("[prediction] model inference failed: %s" % exc)
        return None, False


def _arg(data, *names, default=None, cast=None):
    for n in names:
        if n in data and data[n] not in ("", None):
            v = data[n]
            if cast:
                try:
                    return cast(v)
                except (TypeError, ValueError):
                    return default
            return v
    return default


@bp.route("/api/predict", methods=["GET", "POST"])
def api_predict():
    started = time.perf_counter()
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.args.to_dict()

    contractor = _arg(data, "contractor", default="RIM")
    source = _arg(data, "source", default="TF")
    destination = _arg(data, "destination", "dest", default="FENI KM0")
    shift = str(_arg(data, "shift", default="day")).lower()
    if shift in ("1", "d"):
        shift = "day"
    elif shift in ("2", "n"):
        shift = "night"
    trucks = _arg(data, "trucks", "dt", "trucks_dt", default=1.0, cast=float) or 1.0
    shift_hours = _arg(data, "shift_hours", "hours", default=SHIFT_HOURS_DEFAULT, cast=float) or SHIFT_HOURS_DEFAULT
    rainfall = _arg(data, "rainfall", "rainfall_mm", "rain", default=0.0, cast=float) or 0.0
    wb_open = _arg(data, "weighbridges_open", "weighbridges", "wb", default=8, cast=float) or 8
    mode = str(_arg(data, "mode", default="dt_to_wmt"))
    target_wmt = _arg(data, "target_wmt", "wmt", default=0.0, cast=float) or 0.0
    dow = _arg(data, "day_of_week", default=datetime.now().weekday(), cast=int)
    dist = _arg(data, "distance", "distance_km", default=None, cast=float)
    if dist is None:
        dist = pp.distance_km(source, destination)

    payload_t, payload_src = _payload_for(contractor, source, destination)
    payload_override = _arg(data, "payload", "payload_t", default=None, cast=float)
    if payload_override and payload_override > 0:
        payload_t, payload_src = payload_override, "supplied"

    def features(n_trucks):
        return {"contractor": pp._norm(contractor), "source": pp._norm(source),
                "destination": pp._norm(destination), "shift": shift,
                "day_of_week": int(dow), "distance_km": float(dist),
                "payload_t": float(payload_t), "rainfall_mm": float(rainfall),
                "weighbridges_open": float(wb_open), "trucks_dt": float(n_trucks)}

    bundle = load_model()
    meta = (bundle or {}).get("meta", {})

    def trips_for(n_trucks):
        """trips/DT for a fleet size, model first then OLS fallback."""
        value, used = _predict_trips_per_dt(features(n_trucks))
        if used and value and value > 0:
            # The model is trained on the DB's ~12 h shift; scale a different ask.
            return value * (float(shift_hours) / SHIFT_HOURS_DEFAULT), False
        fb, _tf = _fallback_trips_per_dt(source, destination, n_trucks, rainfall, shift_hours)
        return (fb, True) if fb else (None, True)

    fallback = False
    if mode == "wmt_to_dt":
        if target_wmt <= 0:
            return jsonify({"ok": False, "error": "target_wmt required for wmt_to_dt"}), 400
        n = max(1.0, float(trucks) or 30.0)
        tpd = None
        for _ in range(40):                            # damped fixed point
            tpd, fallback = trips_for(n)
            if not tpd or tpd <= 0 or not payload_t:
                break
            nxt = target_wmt / (tpd * payload_t)
            if not math.isfinite(nxt) or nxt > 1e6:
                tpd = None
                break
            if abs(nxt - n) < 0.01:
                n = nxt
                break
            n = n + 0.6 * (nxt - n)
        if not tpd or tpd <= 0:
            return jsonify({"ok": False, "error": "no history for this route"}), 200
        trucks_needed = max(1, math.ceil(n))
        tpd, fallback = trips_for(trucks_needed)       # re-evaluate at the integer fleet
        total_trips = trucks_needed * tpd
        total_wmt = total_trips * payload_t
        prediction = {
            "trips_per_dt": round(tpd, 3),
            "trucks_needed": int(trucks_needed),
            "total_trips": int(round(total_trips)),
            "payload_per_trip": round(payload_t, 2),
            "total_wmt": int(round(total_wmt)),
            "target_wmt": int(round(target_wmt)),
        }
    else:
        tpd, fallback = trips_for(trucks)
        if not tpd or tpd <= 0:
            return jsonify({"ok": False, "error": "no history for this route"}), 200
        total_trips = float(trucks) * tpd
        prediction = {
            "trips_per_dt": round(tpd, 3),
            "total_trips": int(round(total_trips)),
            "payload_per_trip": round(payload_t, 2),
            "total_wmt": int(round(total_trips * payload_t)),
            "trucks": float(trucks),
        }

    # Confidence: the model's held-out R² when the model answered, a fixed low
    # value when we fell back. Deliberately not invented per-request.
    prediction["confidence"] = round(float(meta.get("r2", 0.0)), 3) if not fallback else 0.4
    prediction["payload_source"] = payload_src

    # ── Phase 3.5: cycle time, additive ────────────────────────────────────
    # Attached alongside the existing answer rather than replacing it. The
    # cycle model is trained on FMS haul telemetry (a different table and a
    # different target from the Phase 2/3 tonnage model), so overwriting
    # trips_per_dt here would silently change the meaning of a field every
    # existing consumer already depends on. Callers opt in by reading `cycle`.
    cycle_block = None
    if cycsrv is not None:
        try:
            c = cycsrv.predict_cycle_time(
                source=pp.canonical_area(source),
                destination=pp.canonical_area(destination),
                shift=shift, trucks=float(trucks),
                rainfall_mm=float(rainfall), distance_km=float(dist))
            if c:
                n_trucks = float(prediction.get("trucks_needed") or trucks)
                plan = cycsrv.cycle_to_tonnage(
                    c["cycle_time_min"], n_trucks, payload_t,
                    shift_hours=float(shift_hours))
                cycle_block = {**c, **plan,
                               "trucks_assumed": n_trucks,
                               "target": "avg_cycle_time_min",
                               "units": "minutes"}
                # Two independent models now answer the same question, and they
                # do not always agree: cycle time comes from FMS haul telemetry,
                # tonnage from weighbridge tickets. Publishing the gap turns a
                # silent contradiction into a usable signal — a large gap means
                # the route's telemetry and its tickets disagree, which is worth
                # knowing before either number is trusted.
                legacy_wmt = prediction.get("total_wmt")
                cyc_wmt = plan.get("total_wmt")
                if legacy_wmt and cyc_wmt:
                    gap = round(100.0 * cyc_wmt / legacy_wmt - 100.0, 1)
                    cycle_block["vs_weighbridge_pct"] = gap
                    cycle_block["models_agree"] = bool(abs(gap) <= 25)
        except Exception:                              # noqa: BLE001
            cycle_block = None                         # never break /api/predict

    return jsonify({
        "ok": True,
        "prediction": prediction,
        # Name what ACTUALLY produced the number: the CV-selected model when one
        # is served, else the RandomForest, else the OLS fallback.
        "model_used": ("fallback_ols" if fallback
                       else (meta.get("selected_model")
                             if _load_selected() else meta.get("model_type", "unknown"))),
        "model_trained_at": meta.get("trained_at"),
        "model_r2": meta.get("r2"),
        # Additive fields only — existing consumers keep working. R2 alone
        # flatters a model: 0.63 sounds strong until you learn a plain
        # (path, contractor, shift) lookup already scores 0.53. The lift is the
        # part that says how much the model is actually contributing.
        "model_baseline_r2": meta.get("baseline_r2"),
        "model_baseline_lift": meta.get("baseline_lift"),
        "model_beats_baseline": meta.get("beats_baseline"),
        # Phase 3: the cross-validated score OF THE MODEL THAT ANSWERED. model_r2
        # above comes from ONE chronological split and is optimistic; this is the
        # mean across every walk-forward fold. It must describe the served model,
        # not the comparison winner, or the badge would credit this prediction
        # with another model's accuracy.
        "model_cv_r2": ((meta.get("cv_mean_r2") or {}).get(meta.get("selected_model"))
                        if _load_selected() else meta.get("cv_r2_served")),
        "model_cv_basis": meta.get("headline_basis"),
        "model_cv_lift": meta.get("cv_baseline_lift"),
        # When the rolling-origin comparison crowns a different candidate, say
        # so plainly rather than letting the UI imply the best available model
        # produced this number.
        "model_selected": meta.get("selected_model"),
        "model_cv_best": (meta.get("cv_mean_r2") or {}).get(meta.get("selected_model")),
        "model_is_cv_winner": bool(_load_selected()) or meta.get("served_is_cv_winner"),
        "model_instance": (bundle or {}).get("instance"),
        # Phase 3.5. Null when no cycle model is trained, so the UI can hide the
        # panel instead of rendering a placeholder number.
        "cycle": cycle_block,
        "fallback": bool(fallback),
        "inputs": {"contractor": contractor, "source": source, "destination": destination,
                   "distance_km": dist, "shift": shift, "shift_hours": shift_hours,
                   "rainfall_mm": rainfall, "weighbridges_open": wb_open, "mode": mode},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    })


@bp.route("/api/match_factor", methods=["GET"])
def api_match_factor():
    """Match Factor per loading point for a date (Tier 3, Module 1).

    Deliberately NOT called /api/shovel_factor: there is no shovel identity in
    the source data, so the key is a loading point and the response says so in
    every payload rather than letting the name imply a machine.

    Dual-mode like the rest of the app: with no results file it returns a small
    illustrative fixture and flags it, so the public demo keeps working without
    the VPN and nobody mistakes fixtures for measurements.

    The three query params are user-controlled and are applied as pandas
    filters over an already-materialised frame, never interpolated into SQL.
    Verified against injection, traversal, XSS and 5 KB oversized values: every
    case returns 200 with count=0, the server stays healthy and the source table
    is untouched. An unknown date or status is an empty result, not an error,
    because "nothing matched" is a real answer for a date with no shifts.
    """
    started = time.perf_counter()
    date = str(request.args.get("date") or "").strip()
    point = str(request.args.get("loading_point") or "").strip()
    status = str(request.args.get("status") or "").strip()

    rows, source, meta = [], "fixtures", {}
    try:
        import match_factor as mf
        df = mf.load_results()
        if df is not None and len(df):
            source = "database"
            meta = _read_json(mf.MF_META, {}) or {}
            if date:
                df = df[df["date"] == date]
            if point:
                df = df[df["loading_point"].astype(str).str.upper() == point.upper()]
            if status:
                df = df[df["status"] == status]
            rows = df.head(500).to_dict("records")
    except Exception:                                      # noqa: BLE001
        rows, source = [], "fixtures"

    if source == "fixtures":
        rows = [
            {"loading_point": "TOS8", "shift": "day", "date": date or "2026-07-01",
             "n_trucks": 24, "servers_observed": 5, "avg_service_time_min": 14.0,
             "avg_cycle_time_min": 96.0, "avg_queue_wait_min": 31.0,
             "trucks_per_server": 4.8, "match_factor": 0.7, "queue_share": 0.32,
             "status": "under-trucked", "cv_interarrival": 1.4,
             "bunching_flag": False},
            {"loading_point": "BLB 10", "shift": "day", "date": date or "2026-07-01",
             "n_trucks": 41, "servers_observed": 6, "avg_service_time_min": 15.0,
             "avg_cycle_time_min": 82.0, "avg_queue_wait_min": 39.0,
             "trucks_per_server": 6.8, "match_factor": 1.25, "queue_share": 0.48,
             "status": "over-trucked", "cv_interarrival": 3.4,
             "bunching_flag": True},
        ]

    val = meta.get("validation") or {}
    return jsonify({
        "ok": True,
        "source": source,
        "is_fixture": source == "fixtures",
        "date": date or None,
        "count": len(rows),
        "results": rows,
        # The caveat travels with the data. A consumer reading only this
        # response still learns that the key is a place, not a machine.
        "keyed_by": "loading_point",
        "shovel_identity_available": False,
        "caveat": ("MF is computed per LOADING POINT, not per shovel. An "
                   "excavator identity exists in the mining tables but cannot "
                   "be joined to haul trips: the two systems use different "
                   "truck namespaces with zero overlap and no crosswalk. "
                   "Server count is the observed peak of simultaneous loads."),
        "bands": {"target": [mf_TARGET_LO, mf_TARGET_HI],
                  "over_trucked_above": mf_OVER, "under_trucked_below": mf_UNDER},
        "validation": {"corr_mf_queue_share": val.get("corr_mf_queue_share"),
                       "passes": val.get("passes"),
                       "gate": val.get("gate")},
        "summary": meta.get("status_pct"),
        "bunching_threshold_cv": meta.get("bunching_threshold_cv"),
        "generated_at": meta.get("generated_at"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    })


@bp.route("/api/tonnage", methods=["GET"])
def api_tonnage():
    """Rolled-up payload totals. group_by = truck|shovel|destination|material."""
    started = time.perf_counter()
    date = str(request.args.get("tdate") or request.args.get("date") or "").strip()
    group = str(request.args.get("group_by") or "shovel").strip().lower()
    rows, source, meta = [], "fixtures", {}
    try:
        import tonnage_tally as tt
        df = tt.load_tally()
        if df is not None and len(df):
            source = "database"
            meta = _read_json(tt.TALLY_META, {}) or {}
            if group:
                df = df[df["group_by"] == group]
            if date:
                df = df[df["date"].astype(str) == date]
            df = df.sort_values("total_wmt", ascending=False)
            rows = df.head(500).to_dict("records")
    except Exception:                                      # noqa: BLE001
        rows, source = [], "fixtures"
    if source == "fixtures":
        rows = [{"group_by": group, "group_value": "TF", "date": date or "2026-07-01",
                 "shift": "day", "total_wmt": 12500.0, "trip_count": 260,
                 "avg_payload_t": 48.1, "truck_count": 30}]
        meta = {"note": "sample data, not measured"}
    return jsonify({
        "ok": True, "source": source, "is_fixture": source == "fixtures",
        "date": date or None, "group_by": group, "count": len(rows),
        "results": rows,
        "reconciliation": meta.get("reconciliation"),
        "weighbridge_crosscheck": meta.get("weighbridge_crosscheck"),
        "generated_at": meta.get("generated_at"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/material_tags", methods=["GET"])
def api_material_tags():
    """Material classification per destination, with its evidence.

    Returns the finding as well as the data: this is an ore-only feed, so every
    destination is ORE and no waste class was invented.
    """
    started = time.perf_counter()
    rows, source, meta = [], "fixtures", {}
    try:
        import ore_waste_tags as ow
        import pandas as _pd
        dm = _pd.read_csv(ow.DEST_MAP_CSV)
        source = "database"
        meta = _read_json(ow.TAGS_META, {}) or {}
        rows = dm.to_dict("records")
    except Exception:                                      # noqa: BLE001
        rows, source = [{"destination": "FENI KM0", "material_type": "ORE",
                         "classification_source": "sample",
                         "classification_confident": True}], "fixtures"
    return jsonify({
        "ok": True, "source": source, "is_fixture": source == "fixtures",
        "count": len(rows), "destinations": rows,
        "material_type_counts": meta.get("material_type_counts"),
        "ore_type_counts": meta.get("ore_type_counts"),
        "flow_counts": meta.get("flow_counts"),
        "waste_stream_present": meta.get("waste_stream_present"),
        "finding": meta.get("finding"),
        "action_for_site": meta.get("action_for_site"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/stockpile/balances", methods=["GET"])
def api_stockpile_balances():
    started = time.perf_counter()
    rows, source, meta = [], "fixtures", {}
    try:
        import stockpile_fifo as sp
        df = sp.load_balances()
        if df is not None and len(df):
            source = "database"
            meta = _read_json(sp.FIFO_META, {}) or {}
            rows = df.to_dict("records")
    except Exception:                                      # noqa: BLE001
        pass
    if source == "fixtures":
        rows = [{"pile_id": "FENI KM0", "tonnes_in": 120000.0,
                 "tonnes_out": 90000.0, "net_movement_tonnes": 30000.0,
                 "implied_opening_stock_t": 0.0, "opening_stock_known": False,
                 "fifo_age_days": 12}]
    return jsonify({
        "ok": True, "source": source, "is_fixture": source == "fixtures",
        "count": len(rows), "balances": rows,
        "reclaim_source": meta.get("reclaim_source"),
        "movement_counts": meta.get("movement_counts"),
        # Opening stock is genuinely unknown, and a balance implying otherwise
        # would be wrong. Say so in the payload, not only in the docs.
        "caveat": ("balances are NET MOVEMENT since the extract window opened. "
                   "Opening stock is unknown, so piles reclaimed from day one "
                   "show negative movement; implied_opening_stock_t is the "
                   "minimum that must already have been on the pad."),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/stockpile/fifo", methods=["GET"])
def api_stockpile_fifo():
    started = time.perf_counter()
    pile = str(request.args.get("pile_id") or "").strip()
    rows, source = [], "fixtures"
    try:
        import stockpile_fifo as sp
        df = sp.load_fifo(pile or None)
        if df is not None and len(df):
            source = "database"
            rows = df.head(500).to_dict("records")
    except Exception:                                      # noqa: BLE001
        pass
    if source == "fixtures":
        rows = [{"pile_id": pile or "FENI KM0", "queue_position": 0,
                 "arrival_date": "2026-01-02", "payload_t": 48.0,
                 "tonnes_reclaimed": 48.0, "tonnes_remaining": 0.0,
                 "fully_reclaimed": True}]
    return jsonify({"ok": True, "source": source,
                    "is_fixture": source == "fixtures",
                    "pile_id": pile or None, "count": len(rows), "queue": rows,
                    "order": "strictly by dump timestamp (FIFO)",
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/stockpile/reconciliation", methods=["GET"])
def api_stockpile_reconciliation():
    """F, GF and MF per deposit — reported separately, never collapsed."""
    started = time.perf_counter()
    rows, source, meta = [], "fixtures", {}
    try:
        import stockpile_fifo as sp
        df = sp.load_reconciliation()
        if df is not None and len(df):
            source = "database"
            meta = (_read_json(sp.FIFO_META, {}) or {}).get("reconciliation", {})
            rows = df.to_dict("records")
    except Exception:                                      # noqa: BLE001
        pass
    if source == "fixtures":
        rows = [{"deposit": "TF", "planned_ni_pct": 1.44, "actual_ni_pct": 1.46,
                 "GF_grade_factor": 1.016, "F_tonnage_factor": None,
                 "f_scope_comparable": False, "complete": False}]
    return jsonify({
        "ok": True, "source": source, "is_fixture": source == "fixtures",
        "count": len(rows), "reconciliation": rows,
        "overall_GF": meta.get("overall_GF"),
        "overall_F": meta.get("overall_F"),
        "overall_MF": meta.get("overall_MF"),
        "grade_coverage_pct": meta.get("grade_coverage_pct"),
        "gf_trustworthy": meta.get("gf_trustworthy"),
        "f_trustworthy": meta.get("f_trustworthy"),
        "note": meta.get("note"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/rules", methods=["GET", "POST"])
def api_rules():
    """List rules with live firing status, or add/update one.

    Rules are policy, not code: thresholds like "when is a shovel starved
    enough to act on" belong to the people running the mine, so they live in
    rules.json and this endpoint edits them without a deploy.
    """
    started = time.perf_counter()
    try:
        import rules_engine as re_
    except Exception as exc:                               # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:120]}), 500

    if request.method == "POST":
        rule = request.get_json(silent=True) or {}
        ok, errs = re_.upsert_rule(rule)
        # A rule that silently never fires is worse than one rejected at the
        # door, because the operator believes they are covered.
        if not ok:
            return jsonify({"ok": False, "error": "invalid rule",
                            "validation_errors": errs}), 400
        return jsonify({"ok": True, "saved": rule.get("id"),
                        "rules": re_.rule_status().get("rules")})

    date = str(request.args.get("date") or "").strip() or None
    try:
        st = re_.rule_status(date=date)
        source = "database"
    except Exception:                                      # noqa: BLE001
        st, source = {"ok": True, "rules": [], "enabled": 0, "disabled": 0,
                      "firing": 0, "alert_count": 0, "by_severity": {}}, "fixtures"
    return jsonify({**st, "source": source,
                    "is_fixture": source == "fixtures",
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/rules/alerts", methods=["GET"])
def api_rule_alerts():
    """Alerts that fired, optionally for one date."""
    started = time.perf_counter()
    date = str(request.args.get("date") or "").strip() or None
    limit = min(int(request.args.get("limit") or 200), 1000)
    try:
        import rules_engine as re_
        ev = re_.evaluate(date=date)
        source = "database"
    except Exception:                                      # noqa: BLE001
        ev, source = {"ok": True, "alerts": [], "alert_count": 0,
                      "by_severity": {}}, "fixtures"
    if source == "fixtures" or not ev.get("ok"):
        ev = {"ok": True, "alert_count": 1, "by_severity": {"high": 1},
              "alerts": [{"rule_id": "R001", "rule_name": "Shovel Starving",
                          "severity": "high", "date": date or "2026-07-01",
                          "shift": "day", "loading_point": "TOS8",
                          "metric": "match_factor", "value": 0.51,
                          "threshold": 0.75, "consecutive_periods": 2,
                          "message": "Sample alert - not measured"}]}
        source = "fixtures"
    alerts = ev.get("alerts", [])[:limit]
    return jsonify({"ok": True, "source": source,
                    "is_fixture": source == "fixtures",
                    "date": date, "alert_count": ev.get("alert_count"),
                    "by_severity": ev.get("by_severity"),
                    "returned": len(alerts), "alerts": alerts,
                    "rules_skipped": ev.get("rules_skipped", []),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/rules/<rule_id>", methods=["PUT", "DELETE"])
def api_rule_item(rule_id):
    """Update a rule, or disable it. DELETE disables rather than removing:
    an audit trail of what was once alerted on is worth more than a tidy file."""
    try:
        import rules_engine as re_
    except Exception as exc:                               # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)[:120]}), 500

    if request.method == "DELETE":
        found = re_.disable_rule(rule_id)
        return (jsonify({"ok": True, "disabled": rule_id, "note": "disabled, not deleted"})
                if found else (jsonify({"ok": False, "error": "no such rule"}), 404))

    rule = request.get_json(silent=True) or {}
    rule["id"] = rule_id
    ok, errs = re_.upsert_rule(rule)
    if not ok:
        return jsonify({"ok": False, "error": "invalid rule",
                        "validation_errors": errs}), 400
    return jsonify({"ok": True, "updated": rule_id})


@bp.route("/api/dispatch/replay", methods=["GET"])
def api_dispatch_replay():
    """Mode A: what MF-balanced dispatch would have produced historically.

    The headline is deliberately SPLIT. Averaging a shift where trucks are
    misallocated with one where the whole fleet is too small produces a number
    that describes neither, so rebalanceable and fleet-limited shifts are
    reported separately and the API never collapses them.
    """
    started = time.perf_counter()
    date = str(request.args.get("date") or "").strip()
    rows, source, meta = [], "fixtures", {}
    try:
        import dynamic_dispatch as dd
        df = dd.load_replay()
        if df is not None and len(df):
            source = "database"
            meta = _read_json(dd.REPLAY_META, {}) or {}
            if date:
                df = df[df["date"].astype(str) == date]
            rows = df.head(500).to_dict("records")
    except Exception:                                      # noqa: BLE001
        rows, source = [], "fixtures"

    if source == "fixtures":
        rows = [{"date": date or "2026-07-01", "shift": "day", "n_points": 5,
                 "rebalanceable": True, "moves": 7, "trucks": 120,
                 "before_under": 3, "before_balanced": 1,
                 "after_under": 2, "after_balanced": 3}]
        meta = {"mode": "A - historical replay (fixture)",
                "verdict": "sample data, not measured"}

    return jsonify({
        "ok": True, "source": source, "is_fixture": source == "fixtures",
        "date": date or None, "count": len(rows), "results": rows,
        "grain": "loading point x shift (shift-level simulation, not real time)",
        "summary": {k: meta.get(k) for k in
                    ("shifts_total", "shifts_rebalanceable", "shifts_fleet_limited",
                     "moves_total", "rebalanceable", "fleet_limited", "all_shifts",
                     "improves_rebalanceable", "verdict")},
        "caveat": ("Shifts where every point is starved cannot be fixed by "
                   "reassignment; those are reported under fleet_limited and "
                   "are a fleet-size finding, not a dispatch result."),
        "generated_at": meta.get("generated_at"),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    })


@bp.route("/api/dispatch/forward", methods=["POST", "GET"])
def api_dispatch_forward():
    """Mode B: recommended truck-to-point assignments for a planned shift."""
    started = time.perf_counter()
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.args.to_dict()
    pts = data.get("loading_points")
    if isinstance(pts, str):
        pts = [x.strip() for x in pts.split(",") if x.strip()]
    plan = {"trucks": data.get("trucks") or data.get("n_trucks") or 0,
            "loading_points": pts or [],
            "shift": data.get("shift") or "day"}
    try:
        plan["trucks"] = int(float(plan["trucks"]))
    except Exception:                                      # noqa: BLE001
        plan["trucks"] = 0

    try:
        import dynamic_dispatch as dd
        out = dd.forward(plan)
        source = "database"
    except Exception as exc:                               # noqa: BLE001
        out, source = {"ok": False, "error": str(exc)[:120]}, "fixtures"

    if not out.get("ok") and source == "fixtures":
        out = {"ok": True, "shift": plan["shift"],
               "trucks_requested": plan["trucks"] or 30,
               "trucks_assigned": plan["trucks"] or 30,
               "assignments": [
                   {"loading_point": "TOS8", "trucks_assigned": 18,
                    "projected_match_factor": 0.92,
                    "projected_status": "balanced", "known": True},
                   {"loading_point": "BLB 10", "trucks_assigned": 12,
                    "projected_match_factor": 0.88,
                    "projected_status": "balanced", "known": True}],
               "unknown_points": [], "basis": "sample data, not measured"}

    return jsonify({**out, "source": source,
                    "is_fixture": source == "fixtures",
                    "grain": "shift-level recommendation, not real-time dispatch",
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})


@bp.route("/api/model-info", methods=["GET"])
def api_model_info():
    """Current model status — used by the UI and for debugging."""
    bundle = load_model()
    if not bundle:
        return jsonify({"ok": True, "trained": False,
                        "message": "No trained model — predictions use the OLS fallback."})
    meta = dict(bundle["meta"])
    meta.pop("features", None)                         # keep the payload small
    meta.pop("ols_features", None)
    return jsonify({"ok": True, "trained": True, "loaded_at": bundle["loaded_at"],
                    **meta, **_phase3_payload(), "cycle_model": _cycle_payload()})


def _cycle_payload() -> dict | None:
    """Phase 3.5 status for the UI.

    Returns the honest verdict, not just the headline: the model wins MAE on
    every fold but does not clear the pre-registered R2 bar, and both facts
    travel together so no consumer can quote one without the other.
    """
    rep = _read_json(CYCLE_REPORT)
    if not rep:
        return None
    return {
        "target": rep.get("target"),
        "units": rep.get("target_units"),
        "rows": rep.get("rows"),
        "date_range": rep.get("date_range"),
        "winner": rep.get("winner"),
        "cv_r2": rep.get("winner_cv_r2"),
        "cv_mae_min": rep.get("winner_cv_mae_min"),
        "baseline_cv_r2": rep.get("baseline_cv_r2"),
        "baseline_cv_mae_min": rep.get("baseline_cv_mae_min"),
        # Forward the lift and the bar it is judged against. Without them the UI
        # can only say "misses the bar" without saying by how much, and a small
        # real improvement reads as none at all.
        "lift_over_baseline": rep.get("lift_over_baseline"),
        "min_lift_required": rep.get("min_lift_required"),
        "beats_baseline": rep.get("beats_baseline"),
        "verdict": rep.get("verdict"),
        "mae_gain_min": rep.get("mae_gain_min"),
        "mae_gain_pct": rep.get("mae_gain_pct"),
        "folds_won_r2": rep.get("folds_won_r2"),
        "folds_won_mae": rep.get("folds_won_mae"),
        "folds_total": rep.get("folds_total"),
        "r2_vs_mae_note": rep.get("r2_vs_mae_note"),
        "sign_checks": {k: rep.get("sign_checks", {}).get(k)
                        for k in ("checked", "violations", "advisory")},
        "max_vif_interpretable": (rep.get("in_sample") or {}).get("max_vif_interpretable"),
    }


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                  # noqa: BLE001
        return default


def _phase3_payload() -> dict:
    """Phase 3 evidence for the UI: coefficients, significance and honest CV.

    Deliberately trimmed. The full coefficient table is ~40 entries and the
    residual sample is thousands of points; the endpoint carries the summary a
    planner or reviewer needs, and the JSON files in data/ hold the rest.
    """
    sig = _read_json(pp.SIGNIFICANCE_JSON) or {}
    val = _read_json(pp.VALIDATION_JSON) or {}
    cmp_ = _read_json(pp.COMPARISON_JSON) or {}
    res = _read_json(pp.RESIDUALS_JSON) or {}
    coefs = sig.get("coefficients") or {}
    # Rank by |t|: the features the data actually pins down, not the ones with
    # the biggest raw coefficient (which just reflects unit scale).
    top = sorted((c for c in coefs.items() if c[0] != "const"),
                 key=lambda kv: abs(kv[1].get("t") or 0), reverse=True)[:15]
    out = {
        "phase3": bool(sig or val or cmp_),
        "ols_coefficients": {k: v for k, v in top},
        "ols_significant": sig.get("significant_features", []),
        "max_vif": sig.get("max_vif"),
        "vif_over_5": sig.get("vif_over_5", []),
        "vif_over_10": sig.get("vif_over_10", []),
        "condition_number": sig.get("condition_number"),
        "validation": {"protocol": val.get("protocol"),
                       "n_folds": val.get("n_folds"),
                       "ols_mean": (val.get("ols") or {}).get("mean"),
                       "folds": (val.get("ols") or {}).get("folds", [])},
        "comparison": {"mean_r2": cmp_.get("mean_r2"),
                       "selected_model": cmp_.get("selected_model"),
                       "selection_rationale": cmp_.get("selection_rationale"),
                       "baseline_lift": cmp_.get("baseline_lift")},
        "residuals": {"heteroscedastic": res.get("heteroscedastic_flag"),
                      "heteroscedasticity_corr": res.get("heteroscedasticity_corr"),
                      "nonlinear_features": res.get("nonlinear_features", [])},
    }
    return out


@bp.route("/api/retrain", methods=["POST", "GET"])
def api_retrain():
    """Re-run extraction → feature engineering → training, then hot-swap the
    in-process model. Serialised so two clicks cannot train concurrently."""
    if not _RETRAIN_LOCK.acquire(blocking=False):
        return jsonify({"ok": False, "error": "a retrain is already running"}), 409
    started = time.perf_counter()
    try:
        import train_model
        print("[retrain] started at %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
        # Phase 3 path: retrains AND re-runs the rolling-origin evaluation, so a
        # retrain can never leave the metadata without its validation evidence.
        # Calling plain train() here silently dropped selected_model and the CV
        # scores, which made the served numbers look better than they were.
        meta = train_model.train_with_phase3(extract=True, verbose=True)
        invalidate_model()
        load_model(force=True)
        # The cycle model is a second model on a second table, and a retrain
        # that refreshed only the tonnage model would leave /api/predict
        # serving a fresh trips number beside a stale cycle time with no
        # indication that they came from different vintages. Same failure mode
        # as H33. Best-effort: it needs the VPN, so a failure here must not
        # fail a retrain that otherwise succeeded.
        # Re-extracting 663k trips takes ~5 minutes against the live DB. That is
        # right for a scheduled retrain and wrong for a health check, so callers
        # opt out with ?cycle=0. The default stays "refresh both", because the
        # failure this guards against — a fresh trips number beside a stale
        # cycle time — is silent, and a slow correct answer beats a fast wrong
        # one.
        want_cycle = str(_arg(request.get_json(silent=True) or request.args
                              or {}, "cycle", default="1")).lower() not in (
                                  "0", "false", "no")
        cycle_status = "skipped (cycle=0)" if not want_cycle else "skipped"
        try:
            if not want_cycle:
                raise RuntimeError("caller opted out")
            import cycle_model, cycle_pipeline
            frame = cycle_pipeline.attach_context(cycle_pipeline.extract_cycle_data())
            cycle_pipeline.save_cycle_data(frame)
            crep = cycle_model.run(frame, verbose=False)
            if cycsrv is not None:
                cycsrv.reset_cycle_model()         # drop the cached pickle
            cycle_status = "retrained: %s rows, %s CV R2 %s" % (
                crep.get("rows"), crep.get("winner"), crep.get("winner_cv_r2"))
        except Exception as exc:                       # noqa: BLE001
            if want_cycle:
                cycle_status = "not retrained (%s)" % str(exc)[:120]
        print("[retrain] cycle model %s" % cycle_status)

        # Match Factor is a third artifact on a third grain. A retrain that
        # refreshed the two models and left the MF table stale would show a
        # planner fresh cycle times beside week-old queue diagnostics with
        # nothing saying they came from different vintages. Same failure mode
        # as the cycle model. Best-effort and opt-out for the same reasons.
        mf_status = "skipped (cycle=0)" if not want_cycle else "skipped"
        try:
            if not want_cycle:
                raise RuntimeError("caller opted out")
            import match_factor
            mfm = match_factor.run(verbose=False)
            val = (mfm.get("validation") or {})
            mf_status = ("refreshed: %s point-shifts, gate passes=%s (r=%s)"
                         % (mfm.get("rows"), val.get("passes"),
                            val.get("corr_mf_queue_share")))
        except Exception as exc:                       # noqa: BLE001
            if want_cycle:
                mf_status = "not refreshed (%s)" % str(exc)[:120]
        print("[retrain] match factor %s" % mf_status)
        elapsed = round(time.perf_counter() - started, 1)
        print("[retrain] done in %ss — %s R2=%.4f MAE=%.4f on %d rows"
              % (elapsed, meta["model_type"], meta["r2"], meta["mae"], meta["training_rows"]))
        return jsonify({"ok": True, "retrained_at": meta["trained_at"], "elapsed_s": elapsed,
                        "cycle_model": cycle_status,
                        "match_factor": mf_status,
                        "model_type": meta["model_type"], "r2": meta["r2"], "mae": meta["mae"],
                        "rmse": meta["rmse"], "training_rows": meta["training_rows"],
                        "test_rows": meta["test_rows"], "candidates": meta["candidates"],
                        # Surfaced at the top level so the UI can report the
                        # gain over a lookup table without digging into
                        # candidates{} — the number that says whether the
                        # retrain was actually worth anything.
                        "baseline_r2": meta.get("baseline_r2"),
                        "baseline_lift": meta.get("baseline_lift"),
                        "beats_baseline": meta.get("beats_baseline"),
                        "selected_model": meta.get("selected_model"),
                        "cv_mean_r2": meta.get("cv_mean_r2"),
                        "cv_r2_selected": meta.get("cv_r2_selected"),
                        "selection_rationale": meta.get("selection_rationale"),
                        "data_source": meta.get("data_source")})
    except Exception as exc:                           # noqa: BLE001
        print("[retrain] FAILED: %s" % exc)
        return jsonify({"ok": False, "error": str(exc)[:300]}), 500
    finally:
        _RETRAIN_LOCK.release()
