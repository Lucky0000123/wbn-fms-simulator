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

bp = Blueprint("prediction_api", __name__)

MODEL_PKL = os.path.join(pp.DATA, "model.pkl")
MODEL_META = os.path.join(pp.DATA, "model_metadata.json")

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
        "fallback": bool(fallback),
        "inputs": {"contractor": contractor, "source": source, "destination": destination,
                   "distance_km": dist, "shift": shift, "shift_hours": shift_hours,
                   "rainfall_mm": rainfall, "weighbridges_open": wb_open, "mode": mode},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    })


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
                    **meta, **_phase3_payload()})


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
        elapsed = round(time.perf_counter() - started, 1)
        print("[retrain] done in %ss — %s R2=%.4f MAE=%.4f on %d rows"
              % (elapsed, meta["model_type"], meta["r2"], meta["mae"], meta["training_rows"]))
        return jsonify({"ok": True, "retrained_at": meta["trained_at"], "elapsed_s": elapsed,
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
