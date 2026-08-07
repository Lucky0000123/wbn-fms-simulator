"""Offline tests for /api/plan/saved (holding plan persistence)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from flask import Flask

import simulator_api as sa


def check(msg, cond, detail=""):
    if not cond:
        raise AssertionError(msg + ((" — " + detail) if detail else ""))
    print("  PASS", msg)


def main():
    print("=== /api/plan/saved ===")
    app = Flask(__name__)
    app.register_blueprint(sa.bp)
    client = app.test_client()

    tmp = tempfile.mkdtemp(prefix="saved_plans_")
    old = sa._SAVED_PLANS_DIR
    sa._SAVED_PLANS_DIR = tmp
    try:
        r = client.get("/api/plan/saved")
        check("GET without date is 400", r.status_code == 400)

        r = client.get("/api/plan/saved?date=2026-08-05")
        j = r.get_json()
        check("GET missing plan ok", j and j.get("ok") and j.get("exists") is False)

        body = {
            "date": "2026-08-05",
            "paths": {
                "RIM|TF>FENI KM15": {
                    "key": "TF>FENI KM15",
                    "dt": 42,
                    "contractor": "RIM",
                    "source": "TF",
                    "dest": "FENI KM15",
                }
            },
            "rain_mm": 3,
            "hours": 12,
            "wb": 8,
            "meta": {"note": "test"},
        }
        r = client.post("/api/plan/saved", json=body)
        j = r.get_json()
        check("POST ok", r.status_code == 200 and j.get("ok") and j.get("exists"))
        check("POST returns paths", j["plan"]["paths"]["RIM|TF>FENI KM15"]["dt"] == 42)
        check("file written", os.path.isfile(os.path.join(tmp, "2026-08-05.json")))

        r = client.get("/api/plan/saved?date=2026-08-05")
        j = r.get_json()
        check("GET exists", j.get("exists") is True)
        check("GET rain", j["plan"].get("rain_mm") == 3)

        r = client.get("/api/plan/saved/list")
        j = r.get_json()
        check("list includes date", "2026-08-05" in (j.get("dates") or []))

        r = client.post("/api/plan/saved", json={"date": "bad", "paths": {"x": {}}})
        check("POST bad date rejected", r.status_code == 400)

        r = client.post("/api/plan/saved", json={"date": "2026-08-05", "paths": {}})
        check("POST empty paths rejected", r.status_code == 400)

        r = client.delete("/api/plan/saved?date=2026-08-05")
        j = r.get_json()
        check("DELETE ok", j.get("ok"))
        r = client.get("/api/plan/saved?date=2026-08-05")
        check("DELETE removed", r.get_json().get("exists") is False)

        # path helper
        check("path helper ok", sa._saved_plan_path("2026-01-01").endswith("2026-01-01.json"))
        check("path helper rejects junk", sa._saved_plan_path("../x") is None)
    finally:
        sa._SAVED_PLANS_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)

    print("all plan-saved gates pass")


if __name__ == "__main__":
    main()
