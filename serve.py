"""
Standalone dev server for the WBN FMS Simulator page.

Serves templates/simulator.html and returns canned sample JSON (fixtures/) for every API the page
calls — so you can edit the simulator's UI/JS/CSS and see it live, with NO backend, NO database, and
NO credentials. The sample data is a real snapshot; it doesn't change as you click around (e.g. every
shift shows the same shift-context), which is fine for front-end work.

Run:  pip install flask  &&  python serve.py    then open  http://127.0.0.1:5055/simulator
"""
from flask import Flask, render_template, jsonify
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(BASE, "fixtures")
app = Flask(__name__, template_folder=os.path.join(BASE, "templates"))


def fx(name):
    with open(os.path.join(FX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
@app.route("/simulator")
def simulator():
    # can_edit_matrix=True so the ⚙ Matrix button shows while developing
    return render_template("simulator.html", can_edit_matrix=True)


# --- mock API: each returns the captured sample response, ignoring query params ---
@app.route("/api/simulator/capability")
def _capability():
    return jsonify(fx("capability"))


@app.route("/api/simulator/congestion-model")
def _congestion():
    return jsonify(fx("congestion-model"))


@app.route("/api/simulator/path-response")
def _path_response():
    return jsonify(fx("path-response"))


@app.route("/api/simulator/shift-context")
def _shift_context():
    return jsonify(fx("shift-context"))


@app.route("/api/simulator/trucks")
def _trucks():
    return jsonify(fx("trucks"))


@app.route("/api/simulator/weighbridge")
def _weighbridge():
    return jsonify(fx("weighbridge"))


@app.route("/api/simulator/weighbridge-positions")
def _weighbridge_positions():
    return jsonify(fx("weighbridge-positions"))


@app.route("/api/weighbridge-summary")
def _weighbridge_summary():
    return jsonify(fx("weighbridge-summary"))


@app.route("/api/simulator/constraints", methods=["GET", "POST"])
def _constraints():
    return jsonify(fx("constraints"))


@app.route("/api/simulator/constraints/reset", methods=["POST"])
def _constraints_reset():
    return jsonify(fx("constraints"))


if __name__ == "__main__":
    print("\n  Simulator dev server → http://127.0.0.1:5055/simulator\n")
    app.run(host="127.0.0.1", port=5055, debug=True)
