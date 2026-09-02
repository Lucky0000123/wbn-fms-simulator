"""Offline tests for /api/plan/saved (holding plan persistence)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import copy

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
    old_sql = sa._SAVED_PLANS_SQL
    sa._SAVED_PLANS_DIR = tmp
    sa._SAVED_PLANS_SQL = False  # never write harness dates into live SQL
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
        check("POST stores disk only when SQL off", j.get("storedIn") == ["disk"])
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

        alloc = {
            "frozen": True,
            "horizon": "day",
            "old": {"pred": 8000, "achv": 7500, "dt": 200},
            "new": {"pred": 8200, "achv": 7600, "achv_sim": 7600,
                    "dt": 200, "target": 9000},
            "calculation_status": "complete",
            "fleet": {"before": 200, "after": 200},
            "goals": {"sap": 5000, "tos": 3000, "ld": 1000, "total": 9000},
            "moved_total": 24,
            "buckets": {
                "sap": {"n": 1, "target": 5000, "dt_before": 80, "dt_after": 104,
                        "pred_before": 4000, "pred_after": 5000,
                        "achv_before": 3800, "achv_after": 4700},
                "tos": {"n": 1, "target": 3000, "dt_before": 60, "dt_after": 60,
                        "pred_before": 2500, "pred_after": 2500,
                        "achv_before": 2400, "achv_after": 2400},
                "ld": {"n": 1, "target": 1000, "dt_before": 60, "dt_after": 36,
                       "pred_before": 1500, "pred_after": 700,
                       "achv_before": 1300, "achv_after": 500},
            },
            "rows": [{
                "id": "RIM|TF>FENI KM0", "key": "TF>FENI KM0", "contractor": "RIM",
                "material": "SAP", "otype": "TOS", "prio": 1, "target": 5000,
                "dt_before": 80, "dt_after": 104,
                "pred_before": 4000, "pred_after": 5000,
                "achv_before": 3800, "achv_after": 4700,
                "achv_sim": 4700, "trips": 210,
            }],
            "moves": [{
                "contractor": "RIM", "trucks": 24,
                "from": "TF>FENI KM15", "from_mat": "LIM", "from_otype": "LD",
                "to": "TF>FENI KM0", "to_mat": "SAP", "to_otype": "TOS",
                "tag": "LIM-LD → SAP", "reason": "LIM-LD → SAP", "same_origin": True,
            }],
            "notes": "RIM 24 DT: TF>FENI KM15 → TF>FENI KM0 (LIM-LD → SAP · same origin)",
        }
        body_alloc = {
            "date": "2026-08-14",
            "paths": {
                "RIM|TF>FENI KM0": {
                    "key": "TF>FENI KM0", "dt": 104, "contractor": "RIM",
                    "source": "TF", "dest": "FENI KM0", "material": "SAP",
                    "otype": "TOS", "targetWmt": 5000,
                    "_preAlloc": {"dt": 80, "pred": 4000, "achv": 3800},
                }
            },
            "rain_mm": 0,
            "hours": 12,
            "meta": {"predict": {"wmt": 4100, "dt": 104}},
            "allocation": alloc,
        }
        incomplete = copy.deepcopy(body_alloc)
        incomplete["allocation"]["new"]["achv_sim"] = None
        incomplete["allocation"]["calculation_status"] = "simulation_pending"
        r = client.post("/api/plan/saved", json=incomplete)
        check("POST rejects frozen allocation without raw simulation",
              r.status_code == 409 and not r.get_json().get("ok"))

        r = client.post("/api/plan/saved", json=body_alloc)
        j = r.get_json()
        check("POST with allocation ok", r.status_code == 200 and j.get("ok"))
        saved = (j.get("plan") or {}).get("allocation") or {}
        check("POST echoes frozen allocation", saved.get("frozen") is True)
        check("POST keeps old predicted", saved.get("old", {}).get("pred") == 8000)
        check("POST keeps new predicted", saved.get("new", {}).get("pred") == 8200)
        check("POST keeps moves", (saved.get("moves") or [{}])[0].get("trucks") == 24)
        check("POST keeps rows table", (saved.get("rows") or [{}])[0].get("dt_after") == 104)
        check("POST keeps GP goals", saved.get("goals", {}).get("sap") == 5000)

        r = client.get("/api/plan/saved?date=2026-08-14")
        j = r.get_json()
        got = (j.get("plan") or {}).get("allocation") or {}
        check("GET round-trips allocation", got.get("frozen") is True)
        check("GET round-trips move from/to",
              (got.get("moves") or [{}])[0].get("from") == "TF>FENI KM15"
              and (got.get("moves") or [{}])[0].get("to") == "TF>FENI KM0")
        check("GET round-trips buckets",
              (got.get("buckets") or {}).get("ld", {}).get("dt_after") == 36)
        check("GET keeps path _preAlloc",
              j["plan"]["paths"]["RIM|TF>FENI KM0"]["_preAlloc"]["dt"] == 80)

        r = client.post("/api/plan/saved", json={
            "date": "2026-08-14",
            "paths": body_alloc["paths"],
            "allocation": {"frozen": False, "new": {"pred": 1}},
        })
        j = r.get_json()
        check("unfrozen allocation is not stored",
              "allocation" not in (j.get("plan") or {}))

        r = client.delete("/api/plan/saved?date=2026-08-14")
        check("cleanup sentinel date", r.get_json().get("ok"))

        # SQL mirror (in-memory): same JSON, no reshape. Live FMS_DB is not used.
        store = {}
        orig_ready = sa._db_ready
        orig_get = sa._saved_plan_sql_get
        orig_put = sa._saved_plan_sql_put
        orig_del = sa._saved_plan_sql_delete
        orig_list = sa._saved_plan_sql_list
        sa._SAVED_PLANS_SQL = True
        sa._db_ready = lambda: True
        sa._saved_plan_sql_get = lambda d: json.loads(store[d]) if d in store else None
        sa._saved_plan_sql_put = lambda d, plan: store.__setitem__(d, json.dumps(plan))
        sa._saved_plan_sql_delete = lambda d: store.pop(d, None)
        sa._saved_plan_sql_list = lambda: list(store.keys())
        try:
            body_sql = {
                "date": "2026-08-15",
                "paths": {
                    "RIM|TF>POS 12": {
                        "key": "TF>POS 12", "dt": 12, "contractor": "RIM",
                    }
                },
                "rain_mm": 0,
                "hours": 12,
                "meta": {},
            }
            r = client.post("/api/plan/saved", json=body_sql)
            j = r.get_json()
            check("POST stores disk+sql", j.get("storedIn") == ["disk", "sql"])
            check("SQL blob keeps dt",
                  json.loads(store["2026-08-15"])["paths"]["RIM|TF>POS 12"]["dt"] == 12)
            r = client.get("/api/plan/saved?date=2026-08-15")
            j = r.get_json()
            check("GET uses disk when timestamps equal",
                  j.get("exists") is True and j.get("servedFrom") != "sql")
            os.remove(os.path.join(tmp, "2026-08-15.json"))
            r = client.get("/api/plan/saved?date=2026-08-15")
            j = r.get_json()
            check("GET sql when disk empty",
                  j.get("exists") is True and j.get("servedFrom") == "sql")
            check("GET sql paths unchanged",
                  j["plan"]["paths"]["RIM|TF>POS 12"]["dt"] == 12)
            check("GET sql caches disk",
                  os.path.isfile(os.path.join(tmp, "2026-08-15.json")))
            stale = json.loads(store["2026-08-15"])
            stale["saved_at"] = "2020-01-01T00:00:00Z"
            stale["paths"]["RIM|TF>POS 12"]["dt"] = 1
            with open(os.path.join(tmp, "2026-08-15.json"), "w", encoding="utf-8") as f:
                json.dump(stale, f)
            r = client.get("/api/plan/saved?date=2026-08-15")
            j = r.get_json()
            check("GET sql when disk is older",
                  j.get("servedFrom") == "sql"
                  and j["plan"]["paths"]["RIM|TF>POS 12"]["dt"] == 12)
            r = client.get("/api/plan/saved/list")
            check("list includes sql date", "2026-08-15" in (r.get_json().get("dates") or []))
            r = client.delete("/api/plan/saved?date=2026-08-15")
            check("DELETE removes sql row", "2026-08-15" not in store)
        finally:
            sa._db_ready = orig_ready
            sa._saved_plan_sql_get = orig_get
            sa._saved_plan_sql_put = orig_put
            sa._saved_plan_sql_delete = orig_del
            sa._saved_plan_sql_list = orig_list
            sa._SAVED_PLANS_SQL = False

        # path helper
        check("path helper ok", sa._saved_plan_path("2026-01-01").endswith("2026-01-01.json"))
        check("path helper rejects junk", sa._saved_plan_path("../x") is None)
    finally:
        sa._SAVED_PLANS_DIR = old
        sa._SAVED_PLANS_SQL = old_sql
        shutil.rmtree(tmp, ignore_errors=True)

    print("all plan-saved gates pass")


if __name__ == "__main__":
    main()
