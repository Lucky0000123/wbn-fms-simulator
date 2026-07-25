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


@app.route("/")
@app.route("/simulator")
def simulator():
    return render_template("simulator.html", can_edit_matrix=True)

@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "wbn-fms-simulator",
                    "dataMode": "database" if simulator_api._db_ready() else "sample-fixtures",
                    "prediction": _PREDICTION})


# Data-loader endpoints kept as fixtures (not part of the model math):
@app.route("/api/simulator/capability")
def _capability():
    return jsonify(fx("capability"))


@app.route("/api/simulator/trucks")
def _trucks():
    return jsonify(fx("trucks"))


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
    mode = "REAL DB" if simulator_api._db_ready() else "sample fixtures"
    print("\n  Simulator dev server (%s) -> http://127.0.0.1:5055/simulator\n" % mode)
    app.run(host=os.environ.get("SIMULATOR_HOST", "127.0.0.1"),
            port=int(os.environ.get("SIMULATOR_PORT", "5055")),
            debug=False, use_reloader=False)
