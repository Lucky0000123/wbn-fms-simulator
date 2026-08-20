#!/usr/bin/env python
"""Scenario 3 only, through the hybrid congestion model - one clear table
per month (Sep-Dec 2026), Monthly-page columns, plus a summary.

Shared-road coupling: combined DT on a route key is priced once, split by
share. Default loaders = the calibrated historical count (the real faces).
Pass --loaders-scale to grow loaders with fleet (historical trucks-per-loader
ratio) — that is a what-if, not the default.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from congestion.predictor import predict  # noqa: E402
from congestion.config import load_params  # noqa: E402

MONNAME = {9: 'September', 10: 'October', 11: 'November', 12: 'December'}
DEFAULT_TPL = 15.0


def loader_ratios():
    path = os.path.join(ROOT, 'data', 'congestion_dayshift.json')
    if not os.path.isfile(path):
        return {}
    rows = json.load(open(path))
    byr = defaultdict(list)
    for r in rows:
        if r.get('trucks') and r.get('faces'):
            byr[r['route']].append((r['trucks'], r['faces']))
    return {route: median(t / f for t, f in pts)
            for route, pts in byr.items() if len(pts) >= 10}


def n_loaders_for(route, cdt, scale, params, ratios):
    rec = (params.get('routes') or {}).get(route) or {}
    cal = int(rec.get('n_loaders') or 2)
    hist_max = rec.get('obs_dt_max') or 0
    if scale:
        tpl = ratios.get(route, DEFAULT_TPL)
        nl = max(1, round(cdt / tpl))
        return nl, cal, hist_max
    return cal, cal, hist_max


def month_rows(m, scale, params, ratios, warnings):
    fn = os.path.join(ROOT, 'data', 'saved_plans', '2026-%02d-03.json' % m)
    if not os.path.isfile(fn):
        return None
    plan = json.load(open(fn))
    paths = {slot: p for slot, p in (plan.get('paths') or {}).items()
             if not p.get('foreign')}
    comb = defaultdict(float)
    for p in paths.values():
        dt = p.get('_allocDt') if p.get('_allocDt') is not None else p.get('dt')
        if dt and dt > 0:
            comb[p['key']] += dt
    priced = {}
    for route, cdt in comb.items():
        nl, cal, hist_max = n_loaders_for(route, cdt, scale, params, ratios)
        if hist_max and cdt > 2 * hist_max:
            if scale:
                warnings.append(
                    "NOTE: %s at %.0f trucks using %d scaled loaders "
                    "(historical max %s DT, calibrated faces %d)."
                    % (route, cdt, nl, hist_max, cal))
            else:
                warnings.append(
                    "WARNING: %s at %.0f trucks with %d loaders "
                    "(historical max was %s with %d calibrated loaders). "
                    "Queue will dominate. If the site plans to add loaders, "
                    "re-run with --loaders-scale."
                    % (route, cdt, nl, hist_max, cal))
        priced[route] = (predict(route, cdt, nl), nl)
    rows = []
    for slot, p in sorted(paths.items()):
        dt = p.get('_allocDt') if p.get('_allocDt') is not None else p.get('dt')
        if not dt or dt <= 0:
            continue
        route = p['key']
        r, nl = priced[route]
        share = dt / comb[route]
        payload = (r['total_tonnes_day'] / r['total_trips_day']
                   if r.get('total_trips_day') and r.get('total_tonnes_day') else 0)
        tpd = r['trips_per_DT_per_day']
        mat = (p.get('material') or '') + ('-' + p['otype'] if p.get('otype') else '')
        rows.append({
            'path': route, 'contractor': p.get('contractor') or '',
            'material': mat or '', 'dt': int(dt), 'loaders': nl,
            'route_combined_dt': round(comb[route]),
            'trips_per_dt': round(tpd, 2),
            'wmt_per_dt': round(tpd * payload, 1),
            'trips_day': round(r['total_trips_day'] * share, 1),
            'wmt_day': round((r['total_tonnes_day'] or 0) * share),
            'cycle_min': round(r['cycle_time_minutes'] or 0),
            'bottleneck': 'road' if (r.get('road_vc') or 0) >= (r.get('rho') or 0) else 'loader',
            'status': r['congestion_status'],
            'model': r['model_version'],
            'bpr_regime': r.get('bpr_regime'),
            'headway_s': (r.get('params') or {}).get('headway_s'),
        })
    return rows


def fmt_table(m, rows, mode):
    out = []
    w = out.append
    w('=' * 118)
    w('  SCENARIO 3 - %s 2026 - Hybrid (%s)' % (MONNAME[m], mode))
    w('=' * 118)
    hdr = ('  %-14s %-11s %-9s %5s %8s %9s %8s %9s %7s %-11s %-11s'
           % ('Path', 'Contractor', 'Material', 'DT', 'Loaders',
              'Trips/DT', 'WMT/DT', 'WMT/day', 'Cycle', 'Bottleneck', 'Status'))
    w(hdr)
    w('  ' + '-' * 116)
    for r in rows:
        w('  %-14s %-11s %-9s %5d %8d %9.2f %8.1f %9s %7d %-11s %-11s'
          % (r['path'], r['contractor'], r['material'], r['dt'], r['loaders'],
             r['trips_per_dt'], r['wmt_per_dt'], format(r['wmt_day'], ','),
             r['cycle_min'], r['bottleneck'], r['status']))
    w('  ' + '-' * 116)
    tdt = sum(r['dt'] for r in rows)
    tt = sum(r['trips_day'] for r in rows)
    tw = sum(r['wmt_day'] for r in rows)
    w('  %-14s %-11s %-9s %5d %8s %9.2f %8s %9s'
      % ('TOTAL', '', '', tdt, '', tt / tdt if tdt else 0, '', format(round(tw), ',')))
    w('')
    return out, {'month': MONNAME[m][:3], 'total_dt': tdt,
                 'trips_day': round(tt), 'wmt_day': round(tw),
                 'avg_trips_dt': round(tt / tdt, 2) if tdt else 0,
                 'n_overloaded': sum(1 for r in rows if r['status'] == 'overloaded'),
                 'n_road': sum(1 for r in rows if r['bottleneck'] == 'road')}


def run(scale):
    params = load_params()
    ratios = loader_ratios()
    mode = 'proportional loaders (--loaders-scale)' if scale else 'calibrated loaders (default)'
    warnings = []
    all_rows = {}
    lines = []
    summary = []
    for m in (9, 10, 11, 12):
        rows = month_rows(m, scale, params, ratios, warnings)
        if rows is None:
            lines.append('  (no S3 plan for month %d)' % m)
            continue
        all_rows[MONNAME[m][:3]] = rows
        t, s = fmt_table(m, rows, mode)
        lines += t
        summary.append(s)
    lines.append('=' * 118)
    lines.append('  SCENARIO 3 - SUMMARY (Sep-Dec 2026) - %s' % mode)
    lines.append('=' * 118)
    lines.append('  %-8s %9s %11s %10s %13s %13s %13s'
                 % ('Month', 'Total DT', 'Trips/day', 'WMT/day',
                    'Avg Trips/DT', '# Overloaded', '# Road-bneck'))
    lines.append('  ' + '-' * 82)
    for s in summary:
        lines.append('  %-8s %9d %11s %10s %13.2f %13d %13d'
                     % (s['month'], s['total_dt'], format(s['trips_day'], ','),
                        format(s['wmt_day'], ','), s['avg_trips_dt'],
                        s['n_overloaded'], s['n_road']))
    seen = set()
    warn_lines = []
    for wmsg in warnings:
        if wmsg not in seen:
            seen.add(wmsg)
            warn_lines.append('  ' + wmsg)
    if warn_lines:
        lines.append('')
        lines += warn_lines
    print('\n'.join(lines))
    suffix = '_scale' if scale else ''
    json.dump(all_rows, open(os.path.join(ROOT, 'data', 's3_results%s.json' % suffix), 'w'), indent=1)
    fields = ['month', 'path', 'contractor', 'material', 'dt', 'loaders',
              'route_combined_dt', 'trips_per_dt', 'wmt_per_dt', 'trips_day',
              'wmt_day', 'cycle_min', 'bottleneck', 'status', 'model',
              'bpr_regime', 'headway_s']
    with open(os.path.join(ROOT, 'data', 's3_results%s.csv' % suffix), 'w', newline='') as f:
        cw = csv.DictWriter(f, fieldnames=fields)
        cw.writeheader()
        for mon, rows in all_rows.items():
            for r in rows:
                cw.writerow({'month': mon, **r})
    print('\nwrote data/s3_results%s.json + data/s3_results%s.csv' % (suffix, suffix))


def main():
    scale = '--loaders-scale' in sys.argv
    run(scale)


if __name__ == '__main__':
    main()
