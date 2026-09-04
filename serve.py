"""
Dev server for the WBN FMS Simulator.

- Serves templates/simulator.html.
- The model endpoints (trips/DT regression, weighbridge aggregation, rainfall + IWIP math) are the REAL
  extracted logic in simulator_api.py — editable, runs on the DB if env-var creds are set, else on the
  sample fixtures.
- Constraints persist to data/constraints_local.json (GET/POST/reset).
- Trucks live via simulator_api.api_simulator_trucks() (HAULAGE_IWIP_CLEAN); fixture on DB miss.

No backend platform code, no database credentials committed.

Run:  pip install flask  &&  python serve.py     then open  http://127.0.0.1:5055/simulator
Optional real data:  FMS_DB_HOST=... FMS_DB_USER=... FMS_DB_PASS=... python serve.py
"""
from flask import Flask, render_template, jsonify, request, send_from_directory
import json
import os
import time

# Load DB credentials from .env / secrets / SSD BEFORE importing simulator_api
# (it snapshots FMS_DB_* into _DB at import time). Without this the server
# silently served fixtures even with a reachable DB (found 2026-08-20).
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
try:
    from load_fms_env import load_fms_env
    _env_path = load_fms_env()
    if _env_path:
        print("[serve] DB creds loaded from %s" % _env_path, flush=True)
    else:
        print("[serve] no .env found — will run on fixtures", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[serve] env load failed (%s) — will run on fixtures" % _exc, flush=True)

import simulator_api

BASE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(BASE, "fixtures")
CONSTRAINTS_LOCAL = os.path.join(BASE, "data", "constraints_local.json")
app = Flask(__name__, template_folder=os.path.join(BASE, "templates"))
# Dev: pick up HTML/template edits without a process restart (debug is off).
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.register_blueprint(simulator_api.bp)      # the real, editable model endpoints

# Monthly roll-up + comparison page (/monthly, /api/monthly/*).
import monthly_api
app.register_blueprint(monthly_api.bp)

# Mine-plan scenarios (S1/S2/S3...) + priority waterfall (/api/scenarios/*).
import scenario_api
app.register_blueprint(scenario_api.bp)

# Grok voice assistant (/voice): read-only questions about the scenarios,
# answered by tools that call this app's own endpoints. Auth = the owner's
# Grok subscription login (~/.grok/auth.json), or XAI_API_KEY if set.
import voice_api
app.register_blueprint(voice_api.bp)

# Phase 2 prediction service (/api/predict, /api/retrain, /api/model-info).
# Optional: if scikit-learn or pandas isn't installed the simulator still runs,
# it just has no ML predictions.
try:
    import prediction_api
    app.register_blueprint(prediction_api.bp)
    _PREDICTION = True
except Exception as _exc:                     # noqa: BLE001
    print("[serve] prediction API unavailable (%s)" % _exc)
    _PREDICTION = False


def fx(name):
    with open(os.path.join(FX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


# ── Canonical route names for the fixture-backed capability payload ─────────
# The capability endpoint feeds the Routes/Destinations tables and the Plan tab
# dropdowns, but it is served straight from fixtures/capability.json, which was
# captured before canonicalisation existed. Left alone it offers the operator
# "FENI A", "HUAFEI.C01" and "CUU_KM_10" — names the model has never seen — so a
# selected route could not be predicted. Rewriting the labels on the way out
# keeps one vocabulary everywhere without regenerating the fixture.
#
# Merging labels creates duplicates ("HUAFEI.B01" and "HUAFEI.C01" both become
# HUAFEI), so rows are re-aggregated: additive quantities are summed and rate
# columns are rebuilt from those sums. Averaging the rates instead would quietly
# corrupt them, since a 5-trip route would count as much as a 500-trip one.
try:
    from prediction_pipeline import canonical_area as _canon
except Exception:                                     # noqa: BLE001
    def _canon(name):                                 # pragma: no cover
        return " ".join(str(name or "").strip().upper().split())

_SUM_KEYS = ("t", "trips", "dt", "planDt", "planWmt", "wmt",
             "nb", "rit", "sw", "snb", "srit", "dtp", "pw", "ptr", "sc")


def _merge_rows(rows, keyfields):
    """Group rows whose canonical key collides, summing additive columns."""
    out = {}
    for r in rows:
        k = tuple(_canon(r.get(f)) for f in keyfields)
        if not all(k):
            continue
        tgt = out.get(k)
        if tgt is None:
            tgt = dict(r)
            for f, v in zip(keyfields, k):
                tgt[f] = v
            out[k] = tgt
            continue
        for col in _SUM_KEYS:
            if isinstance(r.get(col), (int, float)) and isinstance(tgt.get(col), (int, float)):
                tgt[col] = tgt[col] + r[col]
    for row in out.values():                          # rebuild rates from sums
        t, trips, dt = row.get("t"), row.get("trips"), row.get("dt")
        if isinstance(trips, (int, float)) and trips and isinstance(t, (int, float)):
            row["tf"] = round(t / trips, 3)
        if isinstance(dt, (int, float)) and dt:
            if isinstance(trips, (int, float)):
                row["tripsPerDT"] = round(trips / dt, 3)
            if isinstance(t, (int, float)):
                row["tPerDT"] = round(t / dt, 3)
    return list(out.values())


def _canonical_capability(d):
    """Rewrite every route/area label in the capability payload."""
    if not isinstance(d, dict):
        return d
    if isinstance(d.get("routes"), list):
        d["routes"] = _merge_rows(d["routes"], ("origin", "dest"))
    if isinstance(d.get("paths"), list):
        d["paths"] = _merge_rows(d["paths"], ("origin", "dest"))
    if isinstance(d.get("destinations"), list):
        d["destinations"] = _merge_rows(d["destinations"], ("dest",))
    if isinstance(d.get("dailyByPath"), list):
        # Per-day rows: keep the day, canonicalise the two area fields. These
        # drive the scatter/3D view, which re-aggregates client-side already.
        for r in d["dailyByPath"]:
            r["o"] = _canon(r.get("o"))
            r["dd"] = _canon(r.get("dd"))
        d["dailyByPath"] = [r for r in d["dailyByPath"] if r["o"] and r["dd"]]
    return d


@app.route("/")
@app.route("/simulator")
def simulator():
    return render_template("simulator.html", can_edit_matrix=True)


@app.route("/monthly")
def monthly_page():
    return render_template("monthly.html")


@app.route("/planning_rules.md")
def planning_rules_md():
    """Owner's mine-plan rules. static/js/planning_rules.js fetches this at
    startup and the plan builder enforces it; keep the file at the repo root
    so the owner can edit it without touching code."""
    return send_from_directory(BASE, "planning_rules.md",
                               mimetype="text/markdown; charset=utf-8")

@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "wbn-fms-simulator",
                    "dataMode": "database" if simulator_api._db_ready() else "sample-fixtures",
                    "prediction": _PREDICTION})


# /api/simulator/capability MOVED to simulator_api.py on 2026-07-31 and is now a
# real, filtered query against DISPATCH RESULTS LITE 2.
#
# It used to be answered here with `jsonify(_canonical_capability(fx("capability")))`
# -- the committed fixture, every time, database or not, with request.args never
# read. The UI sent six filter parameters and all six were discarded, so the whole
# Capability & Scenario tab was frozen at the values captured on 2026-07-22 and
# the summary line showed the FIXTURE's date range rather than the operator's.
# `_canonical_capability` / `_merge_rows` above are retained: `_register` still
# serves this fixture when there is no database, and it needs the same
# label-rewriting on that path.


@app.route("/api/simulator/trucks")
def _trucks():
    """Live trucks from HAULAGE_IWIP_CLEAN (has TRUCK_ID). Fixture if no DB."""
    try:
        return simulator_api.api_simulator_trucks()
    except Exception as exc:  # noqa: BLE001
        print("[serve] trucks live failed (%s) -> fixture" % str(exc)[:100])
        d = fx("trucks")
        if isinstance(d, dict):
            d = dict(d, servedFrom="fixture",
                     servedFromReason="live truck query failed: %s" % str(exc)[:80])
        return jsonify(d)


def _constraints_default():
    return fx("constraints")


def _constraints_load():
    """Prefer operator-saved local file; else committed fixture."""
    try:
        with open(CONSTRAINTS_LOCAL, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get("ok") and (d.get("sections") or []):
            d = dict(d)
            d["persisted"] = True
            d["persistPath"] = "data/constraints_local.json"
            return d
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    d = _constraints_default()
    if isinstance(d, dict):
        d = dict(d, persisted=False, persistPath=None)
    return d


def _constraints_write(payload):
    os.makedirs(os.path.dirname(CONSTRAINTS_LOCAL), exist_ok=True)
    tmp = CONSTRAINTS_LOCAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, CONSTRAINTS_LOCAL)


@app.route("/api/simulator/constraints", methods=["GET", "POST"])
def _constraints():
    if request.method == "GET":
        return jsonify(_constraints_load())
    body = request.get_json(force=True, silent=True) or {}
    sections = body.get("sections") or []
    paths = body.get("paths") or []
    if not sections:
        return jsonify({"ok": False, "error": "sections required"}), 400
    # Normalise ids to ints; keep path section lists as ints.
    out_secs = []
    for s in sections:
        try:
            out_secs.append({
                "id": int(s["id"]),
                "name": (str(s.get("name") or "").strip() or ("Section %s" % s["id"])),
            })
        except (KeyError, TypeError, ValueError):
            continue
    out_paths = []
    for p in paths:
        try:
            secs = [int(x) for x in (p.get("sections") or [])]
            out_paths.append({
                "origin": str(p.get("origin") or "").strip(),
                "dest": str(p.get("dest") or "").strip(),
                "sections": secs,
            })
        except (TypeError, ValueError):
            continue
    payload = {"ok": True, "sections": out_secs, "paths": out_paths,
               "persisted": True, "persistPath": "data/constraints_local.json"}
    try:
        _constraints_write(payload)
    except OSError as exc:
        return jsonify({"ok": False, "error": "could not write constraints: %s" % exc}), 500
    return jsonify(payload)


@app.route("/api/simulator/constraints/reset", methods=["POST"])
def _constraints_reset():
    try:
        if os.path.isfile(CONSTRAINTS_LOCAL):
            os.remove(CONSTRAINTS_LOCAL)
    except OSError:
        pass
    d = _constraints_default()
    if isinstance(d, dict):
        d = dict(d, persisted=False, persistPath=None, reset=True)
    return jsonify(d)


if __name__ == "__main__":
    if _PREDICTION:                       # warm the model cache before serving
        _m = prediction_api.load_model()
        print("  prediction model: %s" % (
            ("%s R2=%.3f" % (_m["meta"]["model_type"], _m["meta"]["r2"])) if _m
            else "none trained yet — /api/predict will use the OLS fallback"))
    # Warm the capability snapshot in the BACKGROUND. The view behind it takes
    # ~17 s to materialise, so the first operator to open the page would pay for
    # it otherwise. Backgrounded, not blocking, because the server must answer
    # /health immediately -- the verify harness treats a slow health check as a
    # hang.
    if simulator_api._db_ready():
        import threading
        def _warm():
            try:
                t0 = time.time()
                simulator_api._cap_snapshot()
                # flush: stdout is block-buffered under nohup while Flask logs
                # to stderr, so an unflushed print looks like a thread that
                # never ran.
                src = simulator_api._CAP_SNAP.get("source") or "?"
                print("  capability snapshot warm (%d rows, %s, %.1fs)"
                      % (len(simulator_api._CAP_SNAP["rows"] or []), src,
                         time.time() - t0), flush=True)
            except Exception as exc:                      # noqa: BLE001
                print("  capability snapshot warm-up failed: %s" % str(exc)[:120], flush=True)
            try:
                t0 = time.time()
                rows, _rain = simulator_api._path_snapshot()
                src = simulator_api._PATH_SNAP.get("source") or "?"
                print("  path-response snapshot warm (%d rows, %s, %.1fs)"
                      % (len(rows or []), src, time.time() - t0), flush=True)
            except Exception as exc:                      # noqa: BLE001
                print("  path-response warm-up failed: %s" % str(exc)[:120],
                      flush=True)
            # Analogues corpus (day-KPI memory, ~200k rows over VPN): the plan
            # builder queries it on every DT edit — warm it once at boot so the
            # first "Best past days" is instant instead of ~9 s.
            try:
                t0 = time.time()
                corpus, src = simulator_api._analogues_corpus()
                print("  analogues corpus warm (%d days, %s, %.1fs)"
                      % (len(corpus or []), src, time.time() - t0), flush=True)
            except Exception as exc:                      # noqa: BLE001
                print("  analogues corpus warm-up failed: %s" % str(exc)[:120],
                      flush=True)
        threading.Thread(target=_warm, daemon=True).start()

    mode = "REAL DB" if simulator_api._db_ready() else "sample fixtures"
    print("\n  Simulator dev server (%s) -> http://127.0.0.1:5055/simulator\n" % mode)
    # threaded=True because a retrain holds the worker for ~45 s with no DB and
    # several minutes with one. Single-threaded, every other request queues
    # behind it: a health check issued during a retrain waited 3,044 s for a
    # response the server had produced in 45.6 s. That is indistinguishable
    # from a hang to anything checking liveness, including the verify harness.
    app.run(host=os.environ.get("SIMULATOR_HOST", "127.0.0.1"),
            port=int(os.environ.get("SIMULATOR_PORT", "5055")),
            debug=False, use_reloader=False, threaded=True)
