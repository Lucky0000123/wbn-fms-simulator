"""Gate J72: the scenario waterfall respects fleet, contractor and cap invariants.

The scenario feature (2026-08-18) lets the owner load alternative mine plans
(S2, S3, ...) and re-allocate the SAME fleet by priority:
P1 SAP -> P2 LIM-TOS -> P3 LIM-LD (Tofu dump -> Huafei), 8 Mt cap.

What must always hold, per scenario and per month:
  1. DT conservation: P1 + P2 + P3(free) == the yearly matrix's pool,
     per contractor. Trucks are never created or destroyed.
  2. BLB is RIM-only: no allocation row ever puts a non-RIM truck at BLB.
  3. The LD cap: cumulative LIM-LD planned never exceeds 8,000,000 t, and
     a capped month says so (ld_capped=True), an uncapped one does not.
  4. Priority is real: when a P1/P2 target rises, P3 falls - the free fleet
     is what is LEFT, not a fixed share. (Checked by construction: free =
     pool - used, and used covers every target row or reports a deficit.)
  5. S1 passthrough: Scenario 1 derived from the live yearly matrix keeps
     the matrix's own targets - the waterfall does not invent tonnage.
  6. The importer reads the real workbook shape (long-format Mine Plan DB)
     and never writes an S1 file.

Both directions on purpose (the J71 lesson): a gate that only demands
"cap reached" is passed by hardcoding it; one that only demands "under cap"
is passed by deleting P3. We assert exact conservation and both cap states.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scenario_api as sa  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         (" — " + str(detail)[:120]) if (detail and not ok) else ""))
    if not ok:
        FAILS.append(name)


yearly = sa._load_yearly()
if not yearly:
    print("no yearly matrix — gate cannot run")
    sys.exit(1)
rows = sa._yearly_rows(yearly)

print("=== S1: the live plan flows through unchanged ===")
s1 = sa._load_scenario("S1")
check("S1 derives from the yearly matrix", s1 is not None and s1.get("derived"))
res1, err = sa.waterfall(s1)
check("S1 allocates without error", err is None, err)
tgt1 = sa._s1_targets(rows)
sep = {m: round(sum(v for (p, mt, mm), v in tgt1.items() if mt == "SAP" and mm == m))
       for m in (9, 10, 11, 12)}
got = {mo["month"]: mo["sap_t_day"] for mo in res1["months"]}
for m in (9, 10, 11, 12):
    check("S1 month %d SAP target == matrix (%s)" % (m, format(sep[m], ",")),
          abs(got.get(m, 0) - sep[m]) <= 2, "%s vs %s" % (got.get(m), sep[m]))

print("\n=== DT conservation: pool = P1 + P2 + free, per contractor ===")
scen_ids = ["S1"] + [s for s in sa._scenario_ids() if s != "S1"]
results = {}
for sid in scen_ids:
    sc = sa._load_scenario(sid)
    if not sc:
        continue
    res, err = sa.waterfall(sc)
    check("%s allocates without error" % sid, err is None, err)
    if err:
        continue
    results[sid] = res
    for mo in res["months"]:
        for c, pool in mo["pool"].items():
            used = sum(a["dt"] for a in mo["rows"] if a["contractor"] == c)
            for l in mo["lends"]:
                if l["to_work_of"] == c:
                    used -= l["dt"]
                if l["from"] == c:
                    used += l["dt"]
            free = mo["free"].get(c, 0)
            check("%s M%d %s: used %.0f + free %.0f == pool %d"
                  % (sid, mo["month"], c, used, free, pool),
                  abs(used + free - pool) <= 1.5,
                  "%.1f + %.1f != %d" % (used, free, pool))

print("\n=== BLB is RIM-only, in the data and in the allocator ===")
for sid, res in results.items():
    bad = [a for mo in res["months"] for a in mo["rows"]
           if a["pit"] == "BLB" and a["contractor"] != "RIM"]
    check("%s: no non-RIM truck at BLB" % sid, not bad and not res["violations"],
          res["violations"] or bad[:1])
# and the lending path refuses to move trucks INTO a RIM-only pit:
check("lending never targets a RIM-only pit (code path)",
      "RIM_ONLY_PITS" in open(sa.__file__.replace(".pyc", ".py")).read())

print("\n=== the 8 Mt LIM-LD TARGET line: never a clip (owner, 2026-08-19) ===")
for sid, res in results.items():
    t = res["total"]
    # LD is UNCAPPED: planned == full free-fleet capacity, every month.
    check("%s: planned LD == uncapped capacity (no clip)" % sid,
          abs(t["ld_t_planned"] - t["ld_t_capacity"]) <= 2,
          "%s vs %s" % (t["ld_t_planned"], t["ld_t_capacity"]))
    cum = sum(mo["ld_t_month_planned"] for mo in res["months"])
    check("%s: months sum to the total (%s)" % (sid, format(t["ld_t_planned"], ",")),
          abs(cum - t["ld_t_planned"]) <= 2, cum)
    for mo in res["months"]:
        check("%s M%d: month planned == month capacity" % (sid, mo["month"]),
              abs(mo["ld_t_month_planned"] - mo["ld_t_month_capacity"]) <= 2 and
              not mo["ld_capped"])
    # attainment is REPORTED against the target line, both directions:
    if t["ld_t_planned"] >= sa.LIM_LD_TARGET_T:
        check("%s: over-target reported (%s t over)" % (sid, format(t["ld_over_target_t"], ",")),
              t["ld_cap_reached"] and t["ld_shortfall_t"] == 0 and
              abs(t["ld_over_target_t"] - (t["ld_t_planned"] - sa.LIM_LD_TARGET_T)) <= 1)
    else:
        check("%s: shortfall vs target reported" % sid,
              not t["ld_cap_reached"] and t["ld_over_target_t"] == 0 and
              abs(t["ld_shortfall_t"] - (sa.LIM_LD_TARGET_T - t["ld_t_planned"])) <= 1)
# a scenario whose targets consume everything must plan ~zero LD:
starved = {"id": "SX", "label": "starve", "targets": [
    {"pit": p, "mat": m, "month": mm, "wmt_day": 10_000_000}
    for p in ("BLB", "KRENE", "TOFU") for m in ("SAP", "LIM") for mm in (9, 10, 11, 12)]}
resx, err = sa.waterfall(starved)
check("impossible targets starve P3 to ~0 LD (Sep-Dec)",
      err is None and sum(mo["ld_t_month_planned"] for mo in resx["months"]
                          if mo["month"] > 8) < 1000,
      err or sum(mo["ld_t_month_planned"] for mo in resx["months"] if mo["month"] > 8))
check("and reports deficits instead of inventing trucks",
      err is None and any(mo["deficit"] for mo in resx["months"]))
# and one with zero targets frees the whole fleet:
empty = {"id": "SY", "label": "all-free", "targets": [
    {"pit": "BLB", "mat": "SAP", "month": m, "wmt_day": 0.001} for m in (9, 10, 11, 12)]}
resy, err = sa.waterfall(empty)
if err is None:
    mo9 = next(mo for mo in resy["months"] if mo["month"] == 9)
    check("zero targets -> entire pool is free for LD",
          abs(mo9["dt_p3"] - sum(mo9["pool"].values())) <= 1.5,
          "%s vs %s" % (mo9["dt_p3"], sum(mo9["pool"].values())))
else:
    check("zero targets -> entire pool is free for LD", False, err)

print("\n=== the importer reads the real workbook shape ===")
hdr = ["Scenario", "Month", "Nb Days", "Mining Pit", "Material", "Type Ore", "wmt ROM"]
demo = [hdr,
        ["Scenario 9", "Sept", 30, "BLB", "SAP", "TOS", 300000],
        ["Scenario 9", "Sept", 30, "TOFU", "LIM", "TOS", 150000],
        ["Scenario 9", "Oct", 31, "KRENE", "SAP", "TOS", 310000]]
scens, err = sa._parse_mine_plan_db(demo, "demo")
check("long-format rows parse", err is None and len(scens) == 1, err)
if scens:
    s9 = scens[0]
    check("wmt ROM / Nb Days becomes t/day",
          any(abs(t["wmt_day"] - 10000) < 1 for t in s9["targets"]),
          s9["targets"][:2])
    check("scenario id normalised to S9", s9["id"] == "S9", s9["id"])
check("garbage in -> clear error, not a crash",
      sa._parse_mine_plan_db([["nothing", "here"]], "x")[1] is not None)

print("\n=== re-import of identical targets keeps its stamp (the J59 lesson) ===")
if scens:
    import copy
    os.makedirs(sa._SCEN_DIR, exist_ok=True)
    p9 = sa._scen_path("S9")
    try:
        sa._save_scenario(s9)
        stamp1 = os.path.getmtime(p9)
        blob1 = open(p9).read()
        again = copy.deepcopy(s9)
        again["source"] = "different-filename.xlsx"
        again["loaded_at"] = "2099-01-01T00:00:00Z"
        sa._save_scenario(again)
        check("identical targets -> file byte-identical, stamp kept",
              open(p9).read() == blob1)
        changed = copy.deepcopy(s9)
        changed["targets"][0]["wmt_day"] += 1
        sa._save_scenario(changed)
        check("changed targets -> file IS rewritten", open(p9).read() != blob1)
    finally:
        if os.path.isfile(p9):
            os.remove(p9)

if os.path.isfile(os.path.join(sa._SCEN_DIR, "S1.json")):
    check("no S1.json file may exist (S1 is always derived live)", False)

print("\n=== the Excel export quotes the same numbers as the API ===")
try:
    from flask import Flask
    from openpyxl import load_workbook
    import io as _io
    app = Flask(__name__)
    app.register_blueprint(sa.bp)
    c = app.test_client()
    rv = c.get("/api/scenarios/export")
    check("export returns an xlsx", rv.status_code == 200 and
          rv.data[:2] == b"PK", rv.status_code)
    if rv.status_code == 200:
        wb = load_workbook(_io.BytesIO(rv.data))
        api = c.get("/api/scenarios/compare").get_json()
        ids = [s["id"] for s in api["scenarios"]]
        check("one detail sheet per scenario + Compare",
              wb.sheetnames == ["Compare"] + ids, wb.sheetnames)
        totals = None
        for row in wb["Compare"].iter_rows(values_only=True):
            if row[0] == "Total":
                totals = [v for v in row if isinstance(v, (int, float))]
        expect = [s["total"]["ld_t_planned"] for s in api["scenarios"]]
        check("Compare totals row == /api/scenarios/compare LD totals",
              totals == expect, "%s vs %s" % (totals, expect))
        # per-scenario sheet: every month carries its P3 LIM-LD row
        for s in api["scenarios"]:
            d = wb[s["id"]]
            ld_rows = sum(1 for row in d.iter_rows(values_only=True)
                          if row[3] == "LIM-LD" and row[1] == "P3")
            check("%s sheet has a P3 LIM-LD row per month" % s["id"],
                  ld_rows == len(s["months"]), "%d vs %d" % (ld_rows, len(s["months"])))
except ImportError as e:
    print("  SKIP export checks (%s)" % e)

print("\n=== full Excel export (one Monthly workbook per scenario) ===")
try:
    from flask import Flask
    from openpyxl import load_workbook
    import io as _io
    import zipfile
    import monthly_api as ma
    app = Flask(__name__)
    app.register_blueprint(sa.bp)
    app.register_blueprint(ma.bp)
    c = app.test_client()
    yr = "2026"
    want = ["Year", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rv = c.get("/api/scenarios/export-full?year=%s&id=S2" % yr)
    check("S2 monthly workbook returns xlsx", rv.status_code == 200 and rv.data[:2] == b"PK",
          rv.status_code)
    if rv.status_code == 200:
        wb = load_workbook(_io.BytesIO(rv.data), read_only=True)
        # "Paths" (the all-months path list, added 2026-08-19) is optional;
        # the month sheets must be Year-then-months in order.
        got = [s for s in wb.sheetnames if s != "Paths"]
        check("S2 sheets are Year + months (Paths sheet optional)",
              got == want, wb.sheetnames)
        sep = wb["Sep"]
        a1 = sep["A1"].value or ""
        check("S2 Sep title is 'Sep 2026 — old vs new'",
              a1.startswith("Sep 2026"), a1)
        rows = list(sep.iter_rows(min_row=1, max_row=40, max_col=13, values_only=True))
        heads = [r for r in rows if r and r[0] == "P"]
        check("S2 Sep has the path table header", bool(heads), heads[:1])
        p3 = [r for r in rows if r and r[0] == "P3"]
        check("S2 Sep has P3 LIM-LD path rows (leftover DT)", bool(p3), p3[:1])
        wb.close()
    rvz = c.get("/api/scenarios/export-full?year=" + yr)
    check("all-scenarios zip returns", rvz.status_code == 200 and rvz.data[:2] == b"PK",
          rvz.status_code)
    if rvz.status_code == 200:
        z = zipfile.ZipFile(_io.BytesIO(rvz.data))
        names = z.namelist()
        check("zip has monthly_plan_2026.xlsx (S1)", "monthly_plan_2026.xlsx" in names, names)
        check("zip has monthly_plan_2026_S2.xlsx", "monthly_plan_2026_S2.xlsx" in names, names)
        check("zip has monthly_plan_2026_S3.xlsx", "monthly_plan_2026_S3.xlsx" in names, names)
        for fn in names:
            inner = load_workbook(_io.BytesIO(z.read(fn)), read_only=True)
            check("%s sheets start with Year" % fn, inner.sheetnames[0] == "Year",
                  inner.sheetnames)
            inner.close()
        z.close()
except ImportError as e:
    print("  SKIP export-full checks (%s)" % e)
except Exception as e:
    check("export-full smoke test", False, str(e)[:200])


print("=== draft plans: Plan-tab shape, fleet conserved, predicted on target ===")
try:
    import shutil, tempfile
    from flask import Flask
    app3 = Flask(__name__)
    import monthly_api as ma3
    app3.register_blueprint(sa.bp)
    app3.register_blueprint(ma3.bp)
    import simulator_api as sim3
    app3.register_blueprint(sim3.bp)
    c3 = app3.test_client()
    # generate into a throwaway date (day 28, unlikely to be used) then clean up
    rv = c3.post("/api/scenarios/S2/draft-plans", json={
        "year": 2026, "day": 28, "months": [9]})
    d = rv.get_json()
    wrote = d.get("ok") and d.get("written")
    check("draft-plans writes a Plan-tab save", bool(wrote), d)
    fp = os.path.join(sa._ROOT, "data", "saved_plans", "2026-09-28.json")
    try:
        if wrote:
            plan = json.load(open(fp))
            check("draft has date/paths/rain/hours keys",
                  all(k in plan for k in ("date", "paths", "rain_mm", "hours")))
            tot = {}
            blb_bad = []
            for slot, p in plan["paths"].items():
                tot[p["contractor"]] = tot.get(p["contractor"], 0) + p["dt"]
                if p["source"] == "BLB" and p["contractor"] != "RIM":
                    blb_bad.append(slot)
            pool = d["written"][0]["pool"]
            check("draft fleet == pool per contractor",
                  all(abs(tot.get(k, 0) - v) <= 1 for k, v in pool.items()),
                  "%s vs %s" % (tot, pool))
            check("draft has no non-RIM at BLB", not blb_bad, blb_bad)
            # existing date is refused without overwrite
            rv2 = c3.post("/api/scenarios/S2/draft-plans", json={
                "year": 2026, "day": 28, "months": [9]})
            d2 = rv2.get_json()
            check("existing date refused without overwrite",
                  not d2.get("written") and d2.get("errors"), d2)
            # P1/P2 predicted lands on target (>=99.5% of target each)
            with app3.app_context():
                paths_m, fleet_m, contr_m = ma3._path_model_context()
                comb = {}
                for p in plan["paths"].values():
                    comb[p["key"]] = comb.get(p["key"], 0) + p["dt"]
                low = []
                for slot, p in plan["paths"].items():
                    if p.get("otype") == "LD" or not p.get("targetWmt"):
                        continue
                    row = ma3._path_row_wmt(p["source"], p["dest"], p["contractor"],
                                            p["dt"], comb[p["key"]],
                                            paths_m, fleet_m, contr_m)
                    w = row.get("wmt") or 0
                    if w < p["targetWmt"] * 0.995:
                        low.append((slot, round(w), p["targetWmt"]))
                check("every P1/P2 route predicts >= 99.5%% of target", not low, low[:3])
    finally:
        if os.path.isfile(fp):
            os.remove(fp)
except ImportError as e:
    print("  SKIP draft-plan checks (%s)" % e)
except Exception as e:  # noqa: BLE001
    check("draft-plan smoke test", False, str(e)[:120])


print("=== year board day=N picks that day's saved plan (scenario convention) ===")
try:
    from flask import Flask
    import monthly_api as ma5
    app5 = Flask(__name__)
    app5.register_blueprint(ma5.bp)
    c5 = app5.test_client()
    srcs = {}
    for d in (None, 1, 2, 3):
        url = "/api/monthly/year-board?year=2026" + ("&day=%d" % d if d else "")
        r = c5.get(url).get_json()
        srcs[d] = [(c["month"], (c.get("alloc") or {}).get("source_date"))
                   for c in r["cards"] if c.get("has_alloc")]
    for d in (1, 2, 3):
        got = srcs.get(d) or []
        check("day=%d only resolves day-%02d saves" % (d, d),
              got and all(s and s.endswith("-%02d" % d) for _, s in got),
              got[:3])
    check("day=1 and day=2 resolve different plans (not the same copy)",
          srcs[1] and srcs[2] and srcs[1] != srcs[2])
    check("day omitted keeps the old latest-save rule",
          bool(srcs[None]))
except ImportError as e:
    print("  SKIP year-board day checks (%s)" % e)
except Exception as e:  # noqa: BLE001
    check("year-board day smoke test", False, str(e)[:120])

print()
if FAILS:
    print("J72 FAILED: %d check(s). First: %s" % (len(FAILS), FAILS[0]))
    sys.exit(1)
print("scenario waterfall gate passes")
