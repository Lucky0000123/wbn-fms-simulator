"""MUTATION TEST: would test_trips_per_shift.py actually catch the bug?

A gate that only ever passes is decoration. This one exists to stop the 5x
overprediction returning, so prove it fires by reintroducing exactly that bug and
confirming the gate rejects it.

Two mutants:
  A) divide by the weigh-to-weigh cycle again (the original defect)
  B) reapply the 0.85 availability allowance on top of the effective cycle
     (double-counting non-hauling time, the plausible over-correction)
"""
import subprocess
import sys

import pandas as pd

ROOT = "/Users/lucky/wbn-fms-simulator"
LOOKUP = ROOT + "/data/route_lookup.csv"
BACKUP = "/tmp/route_lookup_backup.csv"


def run_gate():
    r = subprocess.run([ROOT + "/.venv/bin/python", "-W", "ignore",
                        ROOT + "/test_trips_per_shift.py"],
                       capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout


print("=== CONTROL: real lookup (expect PASS) ===")
code, out = run_gate()
print("   exit=%d  %s" % (code, out.strip().splitlines()[-1]))
control_pass = code == 0

d = pd.read_csv(LOOKUP)
d.to_csv(BACKUP, index=False)
try:
    print("\n=== MUTANT A: effective cycle := weigh-to-weigh cycle ===")
    print("    this is the original 5x-overprediction bug")
    m = d.copy()
    m["effective_cycle_min"] = m["median_cycle_min"]
    m.to_csv(LOOKUP, index=False)
    code_a, out_a = run_gate()
    tail = [l for l in out_a.strip().splitlines() if "FAILURES" in l or "ALL PASS" in l]
    print("   exit=%d  %s" % (code_a, tail[-1] if tail else "?"))
    mutant_a_caught = code_a != 0

    print("\n=== MUTANT B: effective cycle scaled by 0.85 (double-counted) ===")
    m = d.copy()
    m["effective_cycle_min"] = m["effective_cycle_min"] * 0.85
    m.to_csv(LOOKUP, index=False)
    code_b, out_b = run_gate()
    tail = [l for l in out_b.strip().splitlines() if "FAILURES" in l or "ALL PASS" in l]
    print("   exit=%d  %s" % (code_b, tail[-1] if tail else "?"))
    # 0.85 is an 18% inflation of trips, just over the 15% tolerance.
    mutant_b_caught = code_b != 0
finally:
    pd.read_csv(BACKUP).to_csv(LOOKUP, index=False)
    print("\nrestored the real lookup")

code, out = run_gate()
print("post-restore gate: exit=%d  %s" % (code, out.strip().splitlines()[-1]))

print("\nMUTATION TEST RESULT")
print("   control passes                  : %s" % control_pass)
print("   mutant A (weigh-to-weigh) caught: %s" % mutant_a_caught)
print("   mutant B (0.85 applied) caught  : %s" % mutant_b_caught)
print("   restore leaves gate passing      : %s" % (code == 0))
ok = control_pass and mutant_a_caught and mutant_b_caught and code == 0
print("   => the gate DISCRIMINATES: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
