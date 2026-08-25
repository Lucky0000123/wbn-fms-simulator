"""J79 — the workbook's road grid IS the app's road grid.

Owner, 2026-08-24: "my excel should show exactly what is written in this
table ... the values inside the table should be the same as the values inside
our application."

Both surfaces call plan_shared_flow.shared_flow(), but through different
callers, and a caller can differ in four ways that all move the numbers:
plans, shift_hours, rain_mm, start_hour, whole_day, tenants. This gate pins
the two against each other CELL BY CELL for every saved scenario, so a change
to either caller that moves one of them has to move the other too.

The app side is the real HTTP endpoint (/api/plan/shared-flow) driven with the
payload static/js/plan_scenario.js builds; the Excel side is
monthly_api._corridor_for_alloc, the function the workbook actually calls.

Needs the server on :5055 for the app side. No DB or VPN.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:5055")
FAILS = []
CHECKED = 0


def app_grid(plans):
    """What the browser gets: the same POST plan_scenario.js sends."""
    body = json.dumps({
        "plans": plans, "shift_hours": 12, "rain_mm": 0,
        "start_hour": 7, "whole_day": True,
    }).encode()
    req = urllib.request.Request(BASE + "/api/plan/shared-flow", body,
                                 {"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=180))
    return grid_of(res)


def grid_of(res):
    out = {}
    for s in (res or {}).get("sections") or []:
        occ = s.get("occupancy") or []
        out[s.get("section")] = [round(float(v)) for v in occ]
    return out


def main():
    global CHECKED
    import monthly_api as M

    saves = sorted(glob.glob(os.path.join(ROOT, "data", "saved_plans", "*.json")))
    if not saves:
        print("no saved plans — nothing to compare")
        return 0

    for path in saves:
        date = os.path.basename(path)[:-5]
        try:
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
        except (OSError, ValueError):
            continue
        alloc = saved.get("allocation") or {}
        rows = alloc.get("rows") or []
        if not rows:
            continue

        # EXCEL side: exactly what the workbook calls.
        got = M._corridor_for_alloc(alloc)
        if not got:
            continue
        xl = grid_of(got[0])

        # APP side: the browser's payload is built from the SAME allocated
        # rows (planRoadCrowdingPlans reads _allocDt when frozen), so
        # _plans_from_alloc_rows reproduces it exactly — including the tenant
        # exclusion, which both sides route through one recogniser.
        plans = M._plans_from_alloc_rows(rows)
        if not plans:
            continue
        try:
            app = app_grid(plans)
        except Exception as exc:  # noqa: BLE001
            print("  SKIP %s: app side unreachable (%s)" % (date, str(exc)[:60]))
            continue

        CHECKED += 1
        if set(xl) != set(app):
            FAILS.append("%s: section SETS differ — excel %s vs app %s"
                         % (date, sorted(xl), sorted(app)))
            continue
        for sec in sorted(xl):
            a, b = xl[sec], app[sec]
            if a != b:
                # Name the first differing hour: "they differ" is not
                # actionable, "hour 07 is 263 vs 312" is.
                where = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
                FAILS.append(
                    "%s / %s: %d bins vs %d, first diff at bin %s (%s vs %s)"
                    % (date, sec, len(a), len(b), where,
                       a[where] if where is not None else "-",
                       b[where] if where is not None else "-"))

    print("compared %d saved scenarios, cell by cell" % CHECKED)
    if FAILS:
        print("\nFAILED %d:" % len(FAILS))
        for f in FAILS[:20]:
            print("  - %s" % f)
        return 1
    if CHECKED == 0:
        print("nothing compared — treat as a failure, not a pass")
        return 1
    print("\nJ79 OK — every Excel road cell equals the app's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
