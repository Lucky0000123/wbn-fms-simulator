"""Why does Plan → Road crowding differ from the Excel corridor table?

Owner (2026-08-24): the app's hourly road-crowding grid and the workbook's
corridor block show different trucks-per-section for what should be the same
plan. Both call plan_shared_flow.shared_flow(); this runs BOTH paths against
ONE saved plan and prints the two grids side by side, so the divergence has to
show up as a difference in the INPUTS, not in a screenshot.

Usage: .venv/bin/python scripts/diff_corridor_paths.py [YYYY-MM-DD]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-03"


def load_saved(date):
    path = os.path.join(ROOT, "data", "saved_plans", "%s.json" % date)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    import monthly_api as M
    import plan_shared_flow as sf

    saved = load_saved(DATE)
    alloc = saved.get("allocation") or {}
    rows = alloc.get("rows") or []
    print("saved plan %s: %d allocation rows, frozen=%s"
          % (DATE, len(rows), alloc.get("frozen")))

    # ---- EXCEL PATH: exactly what monthly_api builds -----------------------
    xl_plans = M._plans_from_alloc_rows(rows)
    print("\nEXCEL path -> %d plans, %d trucks"
          % (len(xl_plans), sum(p["n_trucks"] for p in xl_plans)))
    for p in sorted(xl_plans, key=lambda x: -x["n_trucks"]):
        print("   %-22s %-5s %5d" % ("%s>%s" % (p["source"], p["destination"]),
                                     p.get("contractor") or "-", p["n_trucks"]))

    # ---- APP PATH: what the browser sends ---------------------------------
    # plan_scenario.js planRoadCrowdingPlans(): every draft entry that is not a
    # tenant row, at _allocDt when the allocation is frozen else dt, PLUS
    # measured IWIP "other traffic" rows that are NOT on the saved allocation.
    # The saved file's own draft list is the closest server-side stand-in.
    draft = saved.get("rows") or saved.get("draft") or []
    app_plans = []
    for i, r in enumerate(draft):
        if not isinstance(r, dict):
            continue
        if M._is_tenant_row(r):
            continue
        dt = r.get("_allocDt")
        if dt is None:
            dt = r.get("dt")
        if not (dt or 0) > 0:
            continue
        src = r.get("source") or r.get("origin")
        dst = r.get("dest") or r.get("destination")
        if not src or not dst:
            continue
        app_plans.append({"id": r.get("id") or "d%d" % i,
                          "source": src, "destination": dst,
                          "n_trucks": int(round(dt)),
                          "contractor": r.get("contractor")})
    print("\nAPP path (saved draft rows) -> %d plans, %d trucks"
          % (len(app_plans), sum(p["n_trucks"] for p in app_plans)))
    for p in sorted(app_plans, key=lambda x: -x["n_trucks"]):
        print("   %-22s %-5s %5d" % ("%s>%s" % (p["source"], p["destination"]),
                                     p.get("contractor") or "-", p["n_trucks"]))

    # ---- run the SAME engine on each ---------------------------------------
    def run(plans, **kw):
        opts = dict(shift_hours=12, rain_mm=0, start_hour=7,
                    whole_day=True, tenants=True)
        opts.update(kw)
        return sf.shared_flow(plans, **opts)

    def grid(res):
        out = {}
        for s in (res.get("sections") or []):
            occ = s.get("occupancy") or []
            out[s.get("section") or s.get("id")] = [round(v) for v in occ]
        return out

    xl = run(xl_plans)
    app = run(app_plans)
    print("\n%-16s %-28s %-28s" % ("section", "EXCEL (peak / 07 / 13)",
                                   "APP (peak / 07 / 13)"))
    print("-" * 74)
    gx, ga = grid(xl), grid(app)
    for label in sorted(set(gx) | set(ga)):
        a, b = gx.get(label) or [], ga.get(label) or []
        def fmt(v):
            if not v:
                return "-"
            return "%5d / %5d / %5d" % (max(v), v[0], v[6] if len(v) > 6 else v[0])
        flag = "" if a == b else "   <-- DIFFERS"
        print("%-16s %-28s %-28s%s" % (label, fmt(a), fmt(b), flag))

    # ---- does whole_day matter? -------------------------------------------
    half = run(xl_plans, whole_day=False)
    gh = grid(half)
    print("\nwhole_day=False on the SAME excel plans:")
    for label in sorted(gh):
        v, w = gh[label], gx.get(label) or []
        if v != w:
            print("   %-16s %d bins (peak %s) vs %d bins (peak %s)"
                  % (label, len(v), max(v) if v else "-",
                     len(w), max(w) if w else "-"))

    # ---- does the tenant flag matter? -------------------------------------
    notn = run(xl_plans, tenants=False)
    gn = grid(notn)
    print("\ntenants=False on the SAME excel plans:")
    for label in sorted(gn):
        v, w = gn[label], gx.get(label) or []
        if v != w:
            print("   %-16s peak %s (no tenants) vs %s (tenants)"
                  % (label, max(v) if v else "-", max(w) if w else "-"))


if __name__ == "__main__":
    main()
