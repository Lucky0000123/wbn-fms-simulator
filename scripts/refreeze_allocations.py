#!/usr/bin/env python3
"""Re-price saved Allocate-DT snapshots under the hybrid congestion model.

Every allocation-bearing plan in data/saved_plans/ was frozen on 2026-08-19.
The hybrid model was wired into Allocate-DT on 2026-08-20 (93ffa48), so every
frozen snapshot is still priced on the old divide-by-historical-max curve --
including the S1 day-01 plans, not only S2/S3 as HANDOFF.md section 14 says.

WHY THIS DRIVES A BROWSER instead of re-implementing the waterfall in Python:
plan_sap_target.js is the only allocator that consumes planHybridCurveFor()
(plan.js:322), and that function is an async fetch that returns undefined while
pending and re-enters computePlan() when the curve lands. A Python port would
be a THIRD allocator beside plan_sap_target.js and /api/monthly/allocate --
the same "two models, one question" defect this repo has already paid for with
the 0.85 availability override (J55), the three shift-length controls (J60) and
the capacity card denominated in the path model (J71). The J52 lesson states it
directly: a harness that constructs its own input cannot catch a bug in what the
real caller sends.

READ-ONLY BY DEFAULT. planDraftSnapshot() calls buildAllocationPayload()
internally and returns the exact object planSaveForDate() would persist, so the
whole diff runs without writing to data/saved_plans/. Only --apply writes, and
only after is_material() has been decided (see the TODO below).

Usage:
    .venv/bin/python scripts/refreeze_allocations.py                 # all, report only
    .venv/bin/python scripts/refreeze_allocations.py --days 02 03    # S2/S3 only
    .venv/bin/python scripts/refreeze_allocations.py --dates 2026-09-03
    .venv/bin/python scripts/refreeze_allocations.py --apply         # writes (guarded)

Requires serve.py on :5055 with the site DB reachable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

BASE = "http://127.0.0.1:5055"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS = os.path.join(ROOT, "data", "saved_plans")

# The hybrid curve is fetched per (route|loaders|rainBucket). Wait on the
# CONDITION that every fetch kicked off has resolved -- never on a clock. A
# fixed wait_for_timeout is what made the J58 dual-mode check report 17 false
# failures when start-up fetches merely ran slow.
CURVES_SETTLED = """
() => {
  const pend = Object.keys(_planHybridPending);
  if (!pend.length) return false;                       // nothing asked yet
  return pend.every(k => _planHybridCurves[k] !== undefined);
}
"""


def saved_dates(days=None, dates=None):
    """Plan dates that carry a frozen allocation, optionally filtered."""
    out = []
    for fn in sorted(os.listdir(PLANS)):
        if not fn.endswith(".json"):
            continue
        date = fn[:-5]
        if dates and date not in dates:
            continue
        if days and date[-2:] not in days:
            continue
        with open(os.path.join(PLANS, fn)) as fh:
            plan = json.load(fh)
        if (plan.get("allocation") or {}).get("frozen"):
            out.append((date, plan))
    return out


def row_key(r):
    """Rows are matched on identity, not list position -- the allocator drops
    0-DT paths, so index alignment breaks exactly when a plan changed most."""
    return (r.get("key") or "", r.get("contractor") or "", r.get("prio"))


def diff_alloc(old, new):
    """Per-row DT deltas plus the headline totals. Pure data, no verdict."""
    o_rows = {row_key(r): r for r in (old.get("rows") or [])}
    n_rows = {row_key(r): r for r in (new.get("rows") or [])}
    rows = []
    for k in sorted(set(o_rows) | set(n_rows), key=lambda t: (t[2] or 9, t[0], t[1])):
        o, n = o_rows.get(k), n_rows.get(k)
        o_dt = (o or {}).get("dt_after")
        n_dt = (n or {}).get("dt_after")
        rows.append({
            "key": k[0], "contractor": k[1], "prio": k[2],
            "dt_old": o_dt, "dt_new": n_dt,
            "delta": (None if o_dt is None or n_dt is None else n_dt - o_dt),
            "status": ("dropped" if n is None else "added" if o is None else "kept"),
            "pred_old": (o or {}).get("pred_after"),
            "pred_new": (n or {}).get("pred_after"),
        })

    def tot(a, field):
        return (a.get("new") or {}).get(field)

    return {
        "rows": rows,
        "fleet_old": (old.get("fleet") or {}).get("after"),
        "fleet_new": (new.get("fleet") or {}).get("after"),
        "pred_old": tot(old, "pred"), "pred_new": tot(new, "pred"),
        "achv_old": tot(old, "achv"), "achv_new": tot(new, "achv"),
        "dt_moved_abs": sum(abs(r["delta"]) for r in rows if r["delta"] is not None),
        "rows_dropped": sum(1 for r in rows if r["status"] == "dropped"),
        "rows_added": sum(1 for r in rows if r["status"] == "added"),
    }


def is_material(d):
    """Does this re-freeze change the plan enough to need a human first?

    TODO(owner): decide the predicate. Options discussed, trade-offs real:

      (a) total DT moved -- simple, but a big fleet makes every plan look
          material while a 3-truck swing on a 40-DT contractor does not.
      (b) share of fleet moved -- scale-free, and the fleet is the quantity
          the waterfall actually conserves (J72 pins used+free == pool).
          Blind to a small move that empties a path.
      (c) any row crossing zero -- catches paths appearing/vanishing, which is
          the change a planner most needs to see. Silent on large re-sizing.

    Until this is decided, everything is material, so --apply cannot silently
    overwrite a real saved plan. A predicate that defaults to "safe" is the
    wrong default here: data/saved_plans/ is gitignored, so an overwrite has
    no git undo.
    """
    return True, "predicate undecided -- treating every change as material"


def fmt_report(date, d):
    L = []
    L.append("")
    L.append("=" * 78)
    L.append("%s   fleet %s -> %s   |  DT moved %s  |  +%d rows / -%d rows"
             % (date, d["fleet_old"], d["fleet_new"], d["dt_moved_abs"],
                d["rows_added"], d["rows_dropped"]))
    L.append("  predicted %s -> %s     achievable %s -> %s"
             % (d["pred_old"], d["pred_new"], d["achv_old"], d["achv_new"]))
    L.append("-" * 78)
    L.append("  P  route                     contractor      DT old   DT new    delta")
    for r in d["rows"]:
        mark = {"dropped": " (dropped)", "added": " (added)", "kept": ""}[r["status"]]
        L.append("  %-2s %-25s %-14s %7s %8s %8s%s"
                 % (r["prio"], r["key"][:25], r["contractor"][:14],
                    "-" if r["dt_old"] is None else r["dt_old"],
                    "-" if r["dt_new"] is None else r["dt_new"],
                    "-" if r["delta"] is None else "%+d" % r["delta"], mark))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="*", help="day-of-month filter, e.g. 02 03")
    ap.add_argument("--dates", nargs="*", help="explicit YYYY-MM-DD list")
    ap.add_argument("--apply", action="store_true",
                    help="persist the re-frozen allocation (writes saved_plans)")
    ap.add_argument("--timeout", type=int, default=45000,
                    help="ms to wait for hybrid curves per date")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "refreeze_report.json"))
    args = ap.parse_args()

    targets = saved_dates(args.days, args.dates)
    if not targets:
        print("no saved plans with a frozen allocation matched", file=sys.stderr)
        return 2
    print("re-pricing %d plan(s) under the hybrid model%s"
          % (len(targets), "  [APPLY -- WILL WRITE]" if args.apply else "  [report only]"))

    from playwright.sync_api import sync_playwright

    results, failures = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        pg = browser.new_page()
        # planUnlockOriginal() gates on confirm(). Playwright auto-DISMISSES
        # dialogs, so without this the unlock silently returns and the plan stays
        # frozen -- which looks identical to a successful run until achievable
        # comes back null.
        pg.on("dialog", lambda d: d.accept())
        pg.goto(BASE + "/simulator", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_function("() => typeof window.planAllocatePriority === 'function'",
                             timeout=30000)

        for date, plan in targets:
            old = plan["allocation"]
            try:
                pg.evaluate("""(d)=>{
                    const el=document.getElementById('plan-date');
                    if(el){ el.value=d; if(typeof planDateChange==='function') planDateChange(); }
                }""", date)
                pg.evaluate("()=>planLoadSavedForDate({quiet:true})")

                # planRestoreAllocation() sets _allocFrozen and NULLS _planLastSim
                # (plan_sap_target.js:1197) -- the "before" card is painted from the
                # saved snapshot, so a stale sim would misreport it. lockCapacityBtn()
                # then hides and disables Check capacity. So the frozen plan must be
                # unlocked before it can be re-priced; allocating straight from the
                # frozen state yields achievable=null on every row.
                pg.evaluate("()=>{ if(planAllocFrozen()) planUnlockOriginal(); }")
                pg.wait_for_function("() => planAllocFrozen() === false", timeout=args.timeout)

                # Curves are requested lazily by computePlan(); nudge, then wait
                # on the condition rather than assuming the nudge was enough.
                pg.evaluate("()=>{ if(typeof computePlan==='function') computePlan(); }")
                pg.wait_for_function(CURVES_SETTLED, timeout=args.timeout)

                # Check capacity -- repopulates _planLastSim, which achievableShare()
                # reads for every row's achievable clock.
                pg.evaluate("()=>planRunScenario()")
                pg.wait_for_function("() => _planLastSim !== null", timeout=args.timeout)

                pg.evaluate("()=>planAllocatePriority()")
                pg.wait_for_function("() => planAllocFrozen() === true", timeout=args.timeout)

                snap = pg.evaluate("()=>planDraftSnapshot()")
                new = snap.get("allocation")
                if not new:
                    raise RuntimeError("planDraftSnapshot() returned no allocation")
                # Fail loudly on a missing achievable rather than reporting None.
                # A silent null here is the same shape as the residual bugs this
                # repo has already paid for twice -- it does not fail, it just
                # quietly takes up the slack and the report looks plausible.
                if (new.get("new") or {}).get("achv") is None:
                    raise RuntimeError(
                        "achievable is null -- _planLastSim did not repopulate; "
                        "the Check-capacity step did not take effect")

                d = diff_alloc(old, new)
                print(fmt_report(date, d))
                material, why = is_material(d)
                results.append({"date": date, "diff": d, "material": material})

                if args.apply:
                    if material:
                        print("  HALT: %s -- not written" % why)
                    else:
                        pg.evaluate("()=>planSaveForDate()")
                        st = pg.evaluate(
                            "()=>document.getElementById('plan-save-status')?.innerText||''")
                        if "Saved" not in st:
                            raise RuntimeError("save did not confirm: %r" % st)
                        print("  written")
            except Exception as exc:                      # noqa: BLE001 - reported
                print("  ERROR %s: %s" % (date, exc))
                failures.append({"date": date, "error": str(exc)})

        browser.close()

    with open(args.out, "w") as fh:
        json.dump({"results": results, "failures": failures}, fh, indent=1)
    print("\nreport -> %s" % args.out)
    if failures:
        print("%d date(s) failed" % len(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
