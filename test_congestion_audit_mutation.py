"""MUTATION TEST for the sign audit.

The audit currently REJECTS every congestion feature. That is only meaningful
if the audit would ACCEPT a feature that genuinely carried a causal effect.
Otherwise it might be a function that always says no, and always saying no is
not a test.

So: inject a known congestion effect into the panel and confirm the audit
detects it. Real data stays untouched; this operates on a copy.
"""
import sys
sys.path.insert(0, '/Users/lucky/wbn-fms-simulator')
import numpy as np
import pandas as pd
from trip_features import load_features
from simulator_model import build_shift_panel, audit_congestion_signs

p = build_shift_panel(load_features())

print('=== CONTROL: real data (expect REJECT) ===')
a = audit_congestion_signs(p, n_boot=200)
print('   ', a['_conclusion'])
control_usable = any(v.get('usable_as_causal') for v in a.values() if isinstance(v, dict))

print()
print('=== MUTANT A: inject a TRUE +0.5 min per truck effect on the route ===')
print('    cycle := route_floor + 0.5 * trucks_on_route + noise')
print('    the audit MUST now accept trucks_on_route, or it cannot detect signal')
m = p.copy()
rng = np.random.default_rng(7)
m['cycle_time_min'] = (m.route_floor_min
                       + 0.5 * m.trucks_on_route
                       + rng.normal(0, 5, len(m)))
am = audit_congestion_signs(m, n_boot=200)
for k, v in am.items():
    if isinstance(v, dict):
        print('   %-18s joint %+8.2f | alone %+8.2f | %s'
              % (k, v['coef_joint_min_per_sd'], v['coef_alone_min_per_sd'],
                 'ACCEPTED' if v['usable_as_causal'] else 'rejected'))
print('   ', am['_conclusion'])
mutant_usable = any(v.get('usable_as_causal') for v in am.values() if isinstance(v, dict))

print()
print('=== MUTANT B: inject an INVERTED effect (more trucks = faster) ===')
print('    a correct audit must still REJECT this, since it is the wrong sign')
m2 = p.copy()
m2['cycle_time_min'] = (m2.route_floor_min
                        - 0.5 * m2.trucks_on_route
                        + rng.normal(0, 5, len(m2)) + 60)
am2 = audit_congestion_signs(m2, n_boot=200)
print('   ', am2['_conclusion'])
inv_usable = any(v.get('usable_as_causal') for v in am2.values() if isinstance(v, dict))

print()
print('MUTATION TEST RESULT')
ok = (not control_usable) and mutant_usable and (not inv_usable)
print('   control (real data)     rejected : %s' % (not control_usable))
print('   mutant A (true effect)  accepted : %s' % mutant_usable)
print('   mutant B (wrong sign)   rejected : %s' % (not inv_usable))
print('   => the gate DISCRIMINATES: %s' % ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
