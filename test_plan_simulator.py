"""State-space test of the plan simulator: does it behave sanely everywhere?

A simulator is used to compare scenarios, so what matters is not one output
being plausible but the RELATIONSHIPS between outputs holding across the whole
input space. These are the invariants a planner would implicitly rely on.
"""
import sys, json
sys.path.insert(0, '/Users/lucky/wbn-fms-simulator')
from plan_simulator import simulate

fails = []
def check(name, cond, detail=''):
    print('   %-52s %s%s' % (name, 'PASS' if cond else 'FAIL',
                             '' if cond else '  <- ' + str(detail)))
    if not cond:
        fails.append(name)

print('=== 1. single plan, the base case ===')
r = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF',
                         'destination': 'POS 12', 'n_trucks': 30}]})
a = r['results'][0]
print(json.dumps({k: a[k] for k in ('route', 'predicted_cycle_time_min',
    'predicted_load_time_min', 'predicted_dump_time_min',
    'trips_per_shift_per_truck', 'planned_production_t',
    'achievable_production_t')}, indent=2))
check('cycle time positive', a['predicted_cycle_time_min'] > 0)
check('components <= cycle',
      a['predicted_load_time_min'] + a['predicted_dump_time_min']
      <= a['predicted_cycle_time_min'] + 0.1)
check('travel time non-negative', a['implied_travel_time_min'] >= 0)
check('trips per truck plausible (0-50)', 0 < a['trips_per_shift_per_truck'] < 50)
check('achievable <= planned', a['achievable_production_t'] <= a['planned_production_t'] + 1)
check('not shared with anything', a['shared_with'] == [])

print('\n=== 2. MONOTONICITY: more trucks must never mean less planned tonnage ===')
prev = 0
for n in (5, 10, 20, 40, 80, 160):
    r = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF',
                             'destination': 'POS 12', 'n_trucks': n}]})
    x = r['results'][0]
    print('   %3d trucks -> planned %9.0f t | achievable %9.0f t | cap %5s%%'
          % (n, x['planned_production_t'], x['achievable_production_t'],
             round(100*(x['capacity_ratio'] or 0))))
    check('planned rises at n=%d' % n, x['planned_production_t'] >= prev, x['planned_production_t'])
    prev = x['planned_production_t']

print('\n=== 3. CAPACITY CEILING: achievable must saturate, planned must not ===')
# Fleet sizes chosen against TF's MEASURED ceiling of 1,140 trips/shift and the
# measured 1.47 trips per truck per shift, so 200 trucks stays inside it and
# 2,000 breaches it. These were previously 40 and 400, which only breached
# because the old code overpredicted trips by ~11x; correcting the trip rate
# made 400 trucks genuinely fit, so the numbers are re-derived from the
# capacity data rather than left to silently stop testing saturation.
r1 = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF',
                          'destination': 'POS 12', 'n_trucks': 200}]})['results'][0]
r2 = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF',
                          'destination': 'POS 12', 'n_trucks': 2000}]})['results'][0]
print('    200 trucks: planned %.0f t achievable %.0f t cap %s%%'
      % (r1['planned_production_t'], r1['achievable_production_t'],
         round(100*(r1['capacity_ratio'] or 0))))
print('   2000 trucks: planned %.0f t achievable %.0f t cap %s%%'
      % (r2['planned_production_t'], r2['achievable_production_t'],
         round(100*(r2['capacity_ratio'] or 0))))
check('10x trucks -> 10x planned', abs(r2['planned_production_t'] / max(r1['planned_production_t'],1) - 10) < 0.5)
check('200 trucks stays within the measured ceiling', r1['capacity_ratio'] <= 1.0,
      r1['capacity_ratio'])
check('achievable saturates below 10x',
      r2['achievable_production_t'] < r1['achievable_production_t'] * 9)
check('over-capacity warning raised', 'OVER CAPACITY' in r2['capacity_note'])

print('\n=== 4. SHARED LOADING POINT: two plans on one source ===')
r = simulate({'plans': [
    {'route': 'TF>POS 12', 'source': 'TF', 'destination': 'POS 12', 'n_trucks': 30},
    {'route': 'TF>FENI KM0', 'source': 'TF', 'destination': 'FENI KM0', 'n_trucks': 40}]})
for x in r['results']:
    print('   %-14s cap %5s%%  shared_with=%s' % (x['route'],
          round(100*(x['capacity_ratio'] or 0)), x['shared_with']))
check('plan A sees plan B', r['results'][0]['shared_with'] != [])
check('plan B sees plan A', r['results'][1]['shared_with'] != [])
check('shared loading point in summary', len(r['summary']['shared_loading_points']) == 1)
solo = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF',
                            'destination': 'POS 12', 'n_trucks': 30}]})['results'][0]
check('sharing raises measured capacity pressure',
      r['results'][0]['capacity_ratio'] > solo['capacity_ratio'],
      '%s vs %s' % (r['results'][0]['capacity_ratio'], solo['capacity_ratio']))
# Regression guard. The first implementation computed each plan's view of the
# shared loader using its OWN cycle time, so two plans on TF reported 86% and
# 45% utilisation of the same loader in the same shift. One physical point has
# one utilisation, so every plan sharing it must report the identical figure.
check('shared point reports ONE utilisation to all plans',
      r['results'][0]['capacity_ratio'] == r['results'][1]['capacity_ratio'],
      '%s vs %s' % (r['results'][0]['capacity_ratio'], r['results'][1]['capacity_ratio']))
# And that shared figure must equal the sum of what the plans ask of it.
three = simulate({'plans': [
    {'route': 'TF>POS 12', 'source': 'TF', 'destination': 'POS 12', 'n_trucks': 10},
    {'route': 'TF>FENI KM0', 'source': 'TF', 'destination': 'FENI KM0', 'n_trucks': 10},
    {'route': 'KR>POS 10', 'source': 'KR', 'destination': 'POS 10', 'n_trucks': 10}]})
tf = [x['capacity_ratio'] for x in three['results'] if x['source'] == 'TF']
kr = [x['capacity_ratio'] for x in three['results'] if x['source'] == 'KR']
check('three plans, two points: TF pair agrees', len(set(tf)) == 1, tf)
check('three plans: KR is independent of TF', kr[0] != tf[0], '%s vs %s' % (kr, tf))

print('\n=== 5. WEATHER: wet must not be faster than dry ===')
dry = simulate({'plans': [{'route': 'POS 12>FENI KM0', 'source': 'POS 12',
                           'destination': 'FENI KM0', 'n_trucks': 20}], 'weather': 'dry'})['results'][0]
wetr = simulate({'plans': [{'route': 'POS 12>FENI KM0', 'source': 'POS 12',
                            'destination': 'FENI KM0', 'n_trucks': 20}], 'weather': 'wet'})['results'][0]
print('   dry %.1f min -> wet %.1f min' % (dry['predicted_cycle_time_min'], wetr['predicted_cycle_time_min']))
check('wet >= dry cycle time', wetr['predicted_cycle_time_min'] >= dry['predicted_cycle_time_min'])
# Tonnage must NOT fall in the wet. Measured within route and month, rain moves
# tonnage by a median +0.1% and reduces it in only 49% of 122 comparable
# route-months. An earlier version applied a wet penalty to production; that
# warned planners about a loss the data does not show, so it was removed and
# this asserts it stays removed.
check('wet does NOT reduce predicted tonnage (unsupported by data)',
      abs(wetr['planned_production_t'] - dry['planned_production_t']) < 1,
      '%s vs %s' % (wetr['planned_production_t'], dry['planned_production_t']))
check('weather note explains what wet does and does not change',
      'NOT predicted tonnage' in simulate({'plans': [{'route': 'POS 12>FENI KM0',
          'source': 'POS 12', 'destination': 'FENI KM0', 'n_trucks': 20}],
          'weather': 'wet'})['summary'].get('weather_note', ''))

print('\n=== 6. EDGE CASES ===')
check('empty plan handled', 'error' in simulate({'plans': []}))
z = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF', 'destination': 'POS 12', 'n_trucks': 0}]})['results'][0]
check('zero trucks -> zero tonnes', z['planned_production_t'] == 0)
unk = simulate({'plans': [{'route': 'NOWHERE>NOPLACE', 'source': 'NOWHERE',
                           'destination': 'NOPLACE', 'n_trucks': 10}]})['results'][0]
check('unknown route still answers', 'predicted_cycle_time_min' in unk)
check('unknown route flags weak basis', 'unseen' in unk['basis']['cycle_time'], unk['basis']['cycle_time'])

print('\n=== 7. LIMITS ARE ALWAYS DECLARED ===')
r = simulate({'plans': [{'route': 'TF>POS 12', 'source': 'TF', 'destination': 'POS 12', 'n_trucks': 30}]})
check('model_limits present', 'model_limits' in r)
check('congestion limit stated', 'NOT MODELLED' in r['model_limits']['cycle_time_vs_truck_count'])
# The GPS note must describe RETENTION, not absence of instrumentation. The
# original claim ("0 of 940 haul trucks in the feed") was factually wrong; this
# guards against it being reintroduced.
_gps = r['model_limits']['segment_level_speed']
check('GPS limit stated', 'retention' in _gps.lower())
check('GPS limit does NOT repeat the false claim', '0 of 940' not in _gps, _gps[:80])
check('every result carries a basis', all('basis' in x for x in r['results']))

print('\n%s  (%d failures)' % ('ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails), len(fails)))
sys.exit(1 if fails else 0)
