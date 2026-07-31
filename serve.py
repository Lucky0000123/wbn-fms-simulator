"""
Dev server for the WBN FMS Simulator.

- Serves templates/simulator.html.
- The model endpoints (trips/DT regression, weighbridge aggregation, rainfall + IWIP math) are the REAL
  extracted logic in simulator_api.py — editable, runs on the DB if env-var creds are set, else on the
  sample fixtures.
- A few data-loader endpoints that weren't extracted (capability / trucks / constraints) are still
  served from fixtures.

No backend platform code, no database credentials committed.

Run:  pip install flask  &&  python serve.py     then open  http://127.0.0.1:5055/simulator
Optional real data:  FMS_DB_HOST=... FMS_DB_USER=... FMS_DB_PASS=... python serve.py
"""
from flask import Flask, render_template, jsonify
import json
import os

import simulator_api

BASE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(BASE, "fixtures")
app = Flask(__name__, template_folder=os.path.join(BASE, "templates"))
app.register_blueprint(simulator_api.bp)      # the real, editable model endpoints

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
    # Still a fixture, and now says so. It carries no date, contractor or route
    # column, so there is nothing here to filter on even if it were queried --
    # see reports/full_app_audit.md.
    d = fx("trucks")
    if isinstance(d, dict):
        d = dict(d, servedFrom="fixture",
                 servedFromReason="static truck list; not filterable")
    return jsonify(d)


@app.route("/api/simulator/constraints", methods=["GET", "POST"])
def _constraints():
    return jsonify(fx("constraints"))


@app.route("/api/simulator/constraints/reset", methods=["POST"])
def _constraints_reset():
    return jsonify(fx("constraints"))


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
                simulator_api._cap_snapshot()
                # flush: stdout is block-buffered under nohup while Flask logs
                # to stderr, so an unflushed print looks like a thread that
                # never ran.
                print("  capability snapshot warm (%d rows)"
                      % len(simulator_api._CAP_SNAP["rows"] or []), flush=True)
            except Exception as exc:                      # noqa: BLE001
                print("  capability snapshot warm-up failed: %s" % str(exc)[:120], flush=True)
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
