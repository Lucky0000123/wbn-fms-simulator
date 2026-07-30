"""Does a RETRAIN preserve the cycle fix, or silently revert it?

This is the failure mode that would undo everything: someone hits /api/retrain,
the lookup regenerates, and if the effective-cycle column is not rebuilt the
simulator falls back to the weigh-to-weigh figure and the 2.7x overprediction
returns quietly. Nothing in the earlier checks covered it.

Test the whole loop for real: delete the effective-cycle columns, retrain,
confirm they come back and the served prediction is unchanged.
"""
import io
import os
import subprocess
import sys

import pandas as pd

ROOT = "/Users/lucky/wbn-fms-simulator"
LOOKUP = ROOT + "/data/route_lookup.csv"
BACKUP = "/tmp/lookup_retrain_backup.csv"
PY = ROOT + "/.venv/bin/python"

fails = []


def check(name, cond, detail=""):
    print("   %-52s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


def served():
    """Ask the simulator, in a fresh process so nothing is cached."""
    code = (
        "import sys; sys.path.insert(0,'%s');"
        "import plan_simulator as ps; ps.reset_cache();"
        "r=ps.simulate({'plans':[{'route':'POS 12>FENI KM0','source':'POS 12',"
        "'destination':'FENI KM0','n_trucks':30}]})['results'][0];"
        "print('%%.4f %%.1f' %% (r['trips_per_shift_per_truck'], r['effective_cycle_min']))"
        % ROOT)
    out = subprocess.run([PY, "-W", "ignore", "-c", code], capture_output=True,
                         text=True, cwd=ROOT)
    if out.returncode != 0:
        return None, None
    a, b = out.stdout.strip().split()
    return float(a), float(b)


print("=== baseline: what does the simulator serve now? ===")
t0, e0 = served()
print("   trips/truck/shift %.4f | effective cycle %.1f min" % (t0, e0))
cols0 = list(pd.read_csv(LOOKUP).columns)
check("effective_cycle_min present before retrain", "effective_cycle_min" in cols0)

pd.read_csv(LOOKUP).to_csv(BACKUP, index=False)
try:
    print("\n=== simulate the regression risk: strip the fix from the lookup ===")
    d = pd.read_csv(LOOKUP).drop(columns=["effective_cycle_min",
                                          "trips_per_truck_shift",
                                          "truck_shifts",
                                          "effective_cycle_basis"],
                                 errors="ignore")
    d.to_csv(LOOKUP, index=False)
    print("   dropped the effective-cycle columns")
    t1, e1 = served()
    print("   simulator now serves: trips %.4f | effective %.1f min" % (t1, e1))
    # With the column gone it must fall back to the site ratio, NOT to the
    # weigh-to-weigh cycle. 720/75.2 = 9.57 would be the old bug returning.
    check("fallback does NOT restore the 5x overprediction", t1 < 4.0,
          "trips=%.2f" % t1)
    check("fallback effective cycle still exceeds weigh-to-weigh", e1 > 100,
          "%.1f min" % e1)

    print("\n=== now RETRAIN and confirm the fix is rebuilt ===")
    r = subprocess.run([PY, "-W", "ignore", ROOT + "/simulator_model.py"],
                       capture_output=True, text=True, cwd=ROOT)
    ok = r.returncode == 0
    print("   retrain exit=%d" % r.returncode)
    if not ok:
        print(r.stderr[-600:])
    check("retrain succeeded", ok)
    cols2 = list(pd.read_csv(LOOKUP).columns)
    check("effective_cycle_min restored by retrain", "effective_cycle_min" in cols2)
    t2, e2 = served()
    print("   after retrain: trips %.4f | effective %.1f min" % (t2, e2))
    check("served prediction matches the pre-strip value",
          abs(t2 - t0) < 0.01, "%.4f vs %.4f" % (t2, t0))
    check("effective cycle matches", abs(e2 - e0) < 0.5, "%.1f vs %.1f" % (e2, e0))
finally:
    if not os.path.exists(LOOKUP) or "effective_cycle_min" not in \
            pd.read_csv(LOOKUP).columns:
        pd.read_csv(BACKUP).to_csv(LOOKUP, index=False)
        print("\n   (restored from backup)")

print("\n=== is the retrain idempotent? ===")
before = pd.read_csv(LOOKUP)["effective_cycle_min"].sum()
subprocess.run([PY, "-W", "ignore", ROOT + "/simulator_model.py"],
               capture_output=True, text=True, cwd=ROOT)
after = pd.read_csv(LOOKUP)["effective_cycle_min"].sum()
check("retrain is idempotent", abs(before - after) < 0.1,
      "%.2f vs %.2f" % (before, after))

print("\n=== does the LIVE endpoint see a retrained lookup without a restart? ===")
# The bug this covers: plan_simulator caches CSVs in-process, so a retrain that
# rewrites route_lookup.csv was ignored until the process restarted, while the
# served numbers stayed plausible. /api/retrain now calls reset_cache().
import plan_simulator as _ps
_ps.reset_cache()
_d = pd.read_csv(LOOKUP)
_orig = _d.copy()


def _eff():
    r = _ps.simulate({"plans": [{"route": "POS 12>FENI KM0", "source": "POS 12",
                                 "destination": "FENI KM0", "n_trucks": 30}]})
    return r["results"][0]["effective_cycle_min"]


_before = _eff()
_d.loc[_d.route == "POS 12>FENI KM0", "effective_cycle_min"] = 999.0
_d.to_csv(LOOKUP, index=False)
_stale = _eff()
check("in-process cache IS stale without a reset (documents the risk)",
      abs(_stale - _before) < 0.1, "%.1f vs %.1f" % (_stale, _before))
_ps.reset_cache()
_fresh = _eff()
check("reset_cache picks up the new lookup", abs(_fresh - 999.0) < 0.1,
      "%.1f" % _fresh)
import inspect
import prediction_api
_src = inspect.getsource(prediction_api.api_retrain)
check("/api/retrain calls plan_simulator.reset_cache()",
      "plan_simulator.reset_cache()" in _src)
_orig.to_csv(LOOKUP, index=False)
_ps.reset_cache()
check("restored", abs(_eff() - _before) < 0.1)

print("\n%s  (%d failures)"
      % ("ALL PASS" if not fails else "FAILURES: " + ", ".join(fails), len(fails)))
sys.exit(1 if fails else 0)
