#!/usr/bin/env python
"""Run S1/S2/S3 saved plans through the hybrid congestion model.

v2 (owner, 2026-08-20): loaders scale PROPORTIONALLY with trucks using each
route's measured historical trucks-per-loader ratio (median fleet / median
active loading faces from HAULAGE_CLEAN day-shifts). "Loading is not the
issue - the only thing that matters is the truck on the road." With rho held
~constant, the BPR road penalty becomes the variable that grows with fleet.
Adds table F: the two-road split for LIM-LD.
"""
import json
import os
import csv
import urllib.request
import urllib.parse
from collections import defaultdict
from statistics import median

BASE = 'http://127.0.0.1:5055'
DAYS = {9: 30, 10: 31, 11: 30, 12: 31}
MON = {9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
SCEN_DAY = {1: 'S1', 2: 'S2', 3: 'S3'}
DEFAULT_TPL = 15.0   # Burt & Caccetta 2007 balanced match factor when unmeasured


def loader_ratios():
    rows = json.load(open('data/congestion_dayshift.json'))
    byr = defaultdict(list)
    for r in rows:
        if r.get('trucks') and r.get('faces'):
            byr[r['route']].append((r['trucks'], r['faces']))
    out = {}
    for route, pts in byr.items():
        if len(pts) >= 10:
            out[route] = median(t / f for t, f in pts)
    return out


RATIOS = loader_ratios()


def n_loaders_for(route, dt):
    tpl = RATIOS.get(route, DEFAULT_TPL)
    return max(1, round(dt / tpl)), tpl


def api(route, dt, loaders):
    q = urllib.parse.urlencode({'route': route, 'n_trucks': dt, 'n_loaders': loaders})
    with urllib.request.urlopen(BASE + '/api/congestion_model?' + q, timeout=30) as r:
        return json.load(r)


def price(route, dt):
    nl, tpl = n_loaders_for(route, dt)
    r = api(route, dt, nl)
    return r, nl, tpl


def run():
    results = {}
    uncal = set()
    for fn in sorted(os.listdir('data/saved_plans')):
        if not fn.endswith('.json'):
            continue
        try:
            _y, m, day = fn[:-5].split('-')
            m = int(m)
            day = int(day)
        except ValueError:
            continue
        if m not in DAYS or day not in SCEN_DAY:
            continue
        scen = SCEN_DAY[day]
        plan = json.load(open('data/saved_plans/' + fn))
        rows = []
        # ROAD COUPLING: rows sharing a route key share one road. Price the
        # COMBINED fleet per route, then give each row the combined trips/DT.
        # Pricing rows independently under-penalizes shared corridors (the
        # first run's 'two-road' table showed almost no gain because the
        # one-road baseline was split into two cheap independent calls).
        comb = defaultdict(float)
        for p in (plan.get('paths') or {}).values():
            if p.get('foreign'):
                continue
            dtv = p.get('_allocDt') if p.get('_allocDt') is not None else p.get('dt')
            if dtv and dtv > 0:
                comb[p['key']] += dtv
        route_price = {}
        for route, cdt in comb.items():
            try:
                route_price[route] = price(route, cdt)
            except Exception as e:  # noqa: BLE001
                route_price[route] = ('ERR', str(e)[:80])
        for slot, p in sorted((plan.get('paths') or {}).items()):
            if p.get('foreign'):
                continue
            dt = p.get('_allocDt') if p.get('_allocDt') is not None else p.get('dt')
            if not dt or dt <= 0:
                continue
            route = p['key']
            rp = route_price.get(route)
            if not rp or rp[0] == 'ERR':
                rows.append({'slot': slot, 'route': route, 'dt': dt,
                             'error': rp[1] if rp else 'no price'})
                continue
            r, nl, tpl = rp
            if not r.get('calibrated'):
                uncal.add(route)
            share = dt / comb[route] if comb[route] else 0
            rows.append({
                'slot': slot, 'route': route, 'contractor': p.get('contractor'),
                'material': (p.get('material') or '') + ('-' + p['otype'] if p.get('otype') else ''),
                'dt': dt, 'loaders': nl, 'trucks_per_loader': round(tpl, 1),
                'route_combined_dt': round(comb[route]),
                'trips_per_dt': r['trips_per_DT_per_day'],
                'total_trips': (r['total_trips_day'] or 0) * share,
                'tonnes_day': (r['total_tonnes_day'] or 0) * share,
                'cycle_min': r['cycle_time_minutes'],
                'rho': r['rho'], 'road_vc': r.get('road_vc'),
                'bottleneck': 'road' if (r.get('road_vc') or 0) >= (r.get('rho') or 0) else 'loader',
                'status': r['congestion_status'],
                'model': r['model_version'], 'calibrated': r.get('calibrated'),
                'components': r.get('components'),
                'legacy_trips_per_dt': (r.get('legacy_comparison') or {}).get('trips_per_DT_per_day'),
            })
        results.setdefault(scen, {})[m] = rows
    return results, uncal


def report(results, uncal):
    out = []

    def w(s=''):
        out.append(s)

    w('=' * 104)
    w('HYBRID CONGESTION MODEL v2 - PROPORTIONAL LOADERS '
      '(measured trucks/loader per route; rho held ~constant)')
    w('=' * 104)
    for scen in ('S1', 'S2', 'S3'):
        for m in (9, 10, 11, 12):
            rows = results.get(scen, {}).get(m)
            if not rows:
                continue
            w()
            w('--- A . %s . %s 2026 ---' % (scen, MON[m]))
            w('%-14s %5s %5s %6s %9s %8s %10s %7s %6s %6s %7s %-11s' % (
                'Route', 'DT', 'Ldr', 'T/Ldr', 'Trips/DT', 'Trips/d', 'Tonnes/d',
                'Cyc min', 'rho', 'v/c', 'bneck', 'status'))
            for r in rows:
                if 'error' in r:
                    w('%-14s %5s ERROR %s' % (r['route'], r['dt'], r['error']))
                    continue
                w('%-14s %5d %5d %6.1f %9.2f %8.0f %10.0f %7.0f %6.2f %6.2f %7s %-11s' % (
                    r['route'], r['dt'], r['loaders'], r['trucks_per_loader'],
                    r['trips_per_dt'], r['total_trips'], r['tonnes_day'] or 0,
                    r['cycle_min'], r['rho'], r['road_vc'] or 0, r['bottleneck'], r['status']))
    w()
    w('=' * 104)
    w('B . MONTHLY SUMMARY')
    w('%-5s %-4s %8s %10s %12s %10s %6s %6s %8s' % (
        'Mon', 'Scen', 'TotDT', 'Trips/d', 'Tonnes/d', 'AvgT/DT', '#Over', '#Road', '#Loader'))
    summary = []
    for scen in ('S1', 'S2', 'S3'):
        for m in (9, 10, 11, 12):
            rows = [r for r in results.get(scen, {}).get(m, []) if 'error' not in r]
            if not rows:
                continue
            tdt = sum(r['dt'] for r in rows)
            tt = sum(r['total_trips'] for r in rows)
            tn = sum(r['tonnes_day'] or 0 for r in rows)
            over = sum(1 for r in rows if r['status'] == 'overloaded')
            road = sum(1 for r in rows if r['bottleneck'] == 'road')
            ldr = sum(1 for r in rows if r['bottleneck'] == 'loader')
            w('%-5s %-4s %8d %10.0f %12.0f %10.2f %6d %6d %8d' % (
                MON[m], scen, tdt, tt, tn, tt / tdt, over, road, ldr))
            summary.append({'month': MON[m], 'scenario': scen, 'total_dt': tdt,
                            'trips_day': round(tt), 'tonnes_day': round(tn),
                            'avg_trips_dt': round(tt / tdt, 2),
                            'n_overloaded': over, 'n_road': road, 'n_loader': ldr})
    w()
    w('=' * 104)
    w('C . LIM-LD (HUAFEI LD routes) vs the 8 Mt TARGET')
    w('%-5s %-4s %7s %10s %12s %10s %9s' % (
        'Mon', 'Scen', 'LD DT', 'Trips/d', 'Tonnes/d', 'Mt/month', 'cum Mt'))
    ld_tot = {}
    for scen in ('S1', 'S2', 'S3'):
        cum = 0
        for m in (9, 10, 11, 12):
            rows = [r for r in results.get(scen, {}).get(m, []) if 'error' not in r
                    and r['route'].endswith('HUAFEI') and 'LD' in (r['material'] or '')]
            if not rows:
                continue
            dt = sum(r['dt'] for r in rows)
            tt = sum(r['total_trips'] for r in rows)
            tn = sum(r['tonnes_day'] or 0 for r in rows)
            mt = tn * DAYS[m] / 1e6
            cum += mt
            w('%-5s %-4s %7d %10.0f %12.0f %10.3f %9.2f' % (
                MON[m], scen, dt, tt, tn, mt, cum))
        ld_tot[scen] = cum
    w()
    w('D . SCENARIO COMPARISON (Sep-Dec)')
    w('%-4s %14s %8s %10s %10s' % ('Scen', 'LD Mt Sep-Dec', 'pct8Mt', 'AvgT/DT', 'WorstOver'))
    for scen in ('S1', 'S2', 'S3'):
        months = results.get(scen, {})
        tr = d = 0
        wover = 0
        for m, rows in months.items():
            rows = [r for r in rows if 'error' not in r]
            tr += sum(r['total_trips'] for r in rows)
            d += sum(r['dt'] for r in rows)
            wover = max(wover, sum(1 for r in rows if r['status'] == 'overloaded'))
        w('%-4s %14.2f %7.1f%% %10.2f %10d' % (
            scen, ld_tot.get(scen, 0), 100 * ld_tot.get(scen, 0) / 8, tr / max(1, d), wover))
    w()
    w('E . BOTTLENECK STORY - TF>HUAFEI LD (Nov, proportional loaders)')
    for scen in ('S1', 'S2', 'S3'):
        rows = [r for r in results.get(scen, {}).get(11, []) if 'error' not in r
                and r['route'] == 'TF>HUAFEI' and 'LD' in (r['material'] or '')]
        for r in rows:
            c = r['components'] or {}
            cyc = r['cycle_min']
            road = c.get('t_free_road', 0) + c.get('bpr_penalty_minutes', 0)
            w('%s: %d DT / %d loaders -> %.2f trips/DT (legacy %.2f)' % (
                scen, r['dt'], r['loaders'], r['trips_per_dt'], r['legacy_trips_per_dt'] or 0))
            w('   cycle %4.0f min: ROAD %.0f (%.0f free + %.0f BPR = %.0f%% of cycle) | '
              'queue %.0f (%.0f%%) | load+fixed %.0f | road v/c %.2f rho %.2f -> %s' % (
                  cyc, road, c.get('t_free_road', 0), c.get('bpr_penalty_minutes', 0),
                  100 * road / cyc,
                  c.get('queue_wait_minutes', 0), 100 * c.get('queue_wait_minutes', 0) / cyc,
                  c.get('t_load', 0) + c.get('t_spot', 0) + c.get('t_dump', 0),
                  r['road_vc'], r['rho'], r['bottleneck']))
    w()
    w('F . WHAT IF A SECOND HUAFEI ROUTE EXISTED? (S3 LD fleet split 50/50, same c_road each)')
    w('%-5s %8s | %12s %10s | %12s %10s %9s' % (
        'Mon', 'LD DT', '1-road t/d', 'Mt/mo', '2-road t/d', 'Mt/mo', 'gain'))
    tot1 = tot2 = 0
    for m in (9, 10, 11, 12):
        rows = [r for r in results.get('S3', {}).get(m, []) if 'error' not in r
                and r['route'] == 'TF>HUAFEI' and 'LD' in (r['material'] or '')]
        if not rows:
            continue
        dt = sum(r['dt'] for r in rows)
        t1 = sum(r['tonnes_day'] or 0 for r in rows)
        half = dt / 2.0
        ra, _nl, _ = price('TF>HUAFEI', half)
        t2 = 2 * (ra['total_tonnes_day'] or 0)
        m1 = t1 * DAYS[m] / 1e6
        m2 = t2 * DAYS[m] / 1e6
        tot1 += m1
        tot2 += m2
        w('%-5s %8d | %12.0f %10.3f | %12.0f %10.3f %8.0f%%' % (
            MON[m], dt, t1, m1, t2, m2, 100 * (t2 - t1) / t1 if t1 else 0))
    w('TOTAL Sep-Dec: 1 road %.2f Mt (%.0f%% of 8Mt) -> 2 roads %.2f Mt (%.0f%% of 8Mt)' % (
        tot1, 100 * tot1 / 8, tot2, 100 * tot2 / 8))
    if uncal:
        w('')
        w('Uncalibrated routes (defaults): ' + ', '.join(sorted(uncal)))
    return out, summary


if __name__ == '__main__':
    results, uncal = run()
    json.dump(results, open('data/scenario_test_results.json', 'w'), indent=1)
    lines, summary = report(results, uncal)
    print('\n'.join(lines))
    with open('data/scenario_test_summary.csv', 'w', newline='') as f:
        cw = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        cw.writeheader()
        cw.writerows(summary)
    print('')
    print('wrote data/scenario_test_results.json + data/scenario_test_summary.csv')
