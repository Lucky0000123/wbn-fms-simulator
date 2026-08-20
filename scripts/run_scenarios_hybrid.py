#!/usr/bin/env python
"""Run S1/S2/S3 saved plans through the hybrid congestion model (owner task 2026-08-20)."""
import json, os, sys, csv, urllib.request, urllib.parse

BASE='http://127.0.0.1:5055'
DAYS={9:30,10:31,11:30,12:31}
MON={9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
# day-of-month convention: 01=S1, 02=S2, 03=S3
SCEN_DAY={1:'S1',2:'S2',3:'S3'}

def api(route,dt,loaders):
    q=urllib.parse.urlencode({'route':route,'n_trucks':dt,'n_loaders':loaders})
    with urllib.request.urlopen(BASE+'/api/congestion_model?'+q,timeout=30) as r:
        return json.load(r)

results={}   # scenario -> month -> [route rows]
uncal=set()
for fn in sorted(os.listdir('data/saved_plans')):
    if not fn.endswith('.json'): continue
    d=fn[:-5]
    try:
        y,m,day=d.split('-'); m=int(m); day=int(day)
    except ValueError: continue
    if m not in DAYS or day not in SCEN_DAY: continue
    scen=SCEN_DAY[day]
    plan=json.load(open('data/saved_plans/'+fn))
    rows=[]
    for slot,p in sorted((plan.get('paths') or {}).items()):
        if p.get('foreign'): continue
        # use the ALLOCATED dt when frozen allocation exists, else the plan dt
        dt=p.get('_allocDt') if p.get('_allocDt') is not None else p.get('dt')
        if not dt or dt<=0: continue
        loaders=int(p.get('loaders') or 2)
        route=p['key']
        try:
            r=api(route,dt,loaders)
        except Exception as e:
            rows.append({'slot':slot,'route':route,'dt':dt,'loaders':loaders,'error':str(e)[:80]})
            continue
        if not r.get('calibrated'): uncal.add(route)
        rows.append({
            'slot':slot,'route':route,'contractor':p.get('contractor'),
            'material':(p.get('material') or '')+('-'+p['otype'] if p.get('otype') else ''),
            'dt':dt,'loaders':loaders,
            'trips_per_dt':r['trips_per_DT_per_day'],
            'total_trips':r['total_trips_day'],
            'tonnes_day':r['total_tonnes_day'],
            'cycle_min':r['cycle_time_minutes'],
            'rho':r['rho'],'road_vc':r.get('road_vc'),
            'bottleneck':'road' if (r.get('road_vc') or 0)>=(r.get('rho') or 0) else 'loader',
            'status':r['congestion_status'],
            'model':r['model_version'],'calibrated':r.get('calibrated'),
            'components':r.get('components'),
            'legacy_trips_per_dt':(r.get('legacy_comparison') or {}).get('trips_per_DT_per_day'),
        })
    results.setdefault(scen,{})[m]=rows

json.dump(results,open('data/scenario_test_results.json','w'),indent=1)

# ── report ──
out=[]
def w(s=''): out.append(s)

w('='*100)
w('HYBRID CONGESTION MODEL - SCENARIO RUN  (model_version=hybrid, calibrated on HAULAGE_CLEAN 2026)')
w('='*100)

for scen in ('S1','S2','S3'):
    for m in (9,10,11,12):
        rows=results.get(scen,{}).get(m)
        if not rows: continue
        w()
        w('--- A · %s · %s 2026 --- (per-route)'%(scen,MON[m]))
        w('%-14s %5s %4s %9s %8s %10s %7s %6s %7s %-11s %-7s'%(
            'Route','DT','Ldr','Trips/DT','Trips/d','Tonnes/d','Cyc min','rho','bneck','status','model'))
        for r in rows:
            if 'error' in r: w('%-14s %5s ERROR %s'%(r['route'],r['dt'],r['error'])); continue
            w('%-14s %5d %4d %9.2f %8.0f %10.0f %7.0f %6.2f %7s %-11s %-7s'%(
                r['route'],r['dt'],r['loaders'],r['trips_per_dt'],r['total_trips'],
                r['tonnes_day'] or 0,r['cycle_min'],r['rho'],r['bottleneck'],r['status'],
                'hybrid' if r['model']=='hybrid' else 'legacy'))

w(); w('='*100)
w('B · MONTHLY SUMMARY')
w('%-5s %-4s %8s %10s %12s %10s %6s %6s %8s'%('Mon','Scen','TotDT','Trips/d','Tonnes/d','AvgT/DT','#Over','#Road','#Loader'))
summary_rows=[]
for scen in ('S1','S2','S3'):
    for m in (9,10,11,12):
        rows=[r for r in results.get(scen,{}).get(m,[]) if 'error' not in r]
        if not rows: continue
        tdt=sum(r['dt'] for r in rows); tt=sum(r['total_trips'] for r in rows)
        tn=sum(r['tonnes_day'] or 0 for r in rows)
        over=sum(1 for r in rows if r['status']=='overloaded')
        road=sum(1 for r in rows if r['bottleneck']=='road')
        ldr=sum(1 for r in rows if r['bottleneck']=='loader')
        w('%-5s %-4s %8d %10.0f %12.0f %10.2f %6d %6d %8d'%(MON[m],scen,tdt,tt,tn,tt/tdt,over,road,ldr))
        summary_rows.append({'month':MON[m],'scenario':scen,'total_dt':tdt,
            'trips_day':round(tt),'tonnes_day':round(tn),'avg_trips_dt':round(tt/tdt,2),
            'n_overloaded':over,'n_road':road,'n_loader':ldr})

w(); w('='*100)
w('C · LIM-LD (HUAFEI routes) vs the 8 Mt TARGET')
w('%-5s %-4s %7s %10s %12s %10s %9s'%('Mon','Scen','LD DT','Trips/d','Tonnes/d','Mt/month','%of8Mt'))
ld_tot={}
for scen in ('S1','S2','S3'):
    tot=0
    for m in (9,10,11,12):
        rows=[r for r in results.get(scen,{}).get(m,[]) if 'error' not in r
              and r['route'].endswith('HUAFEI') and 'LD' in (r['material'] or '')]
        if not rows: continue
        dt=sum(r['dt'] for r in rows); tt=sum(r['total_trips'] for r in rows)
        tn=sum(r['tonnes_day'] or 0 for r in rows)
        mt=tn*DAYS[m]/1e6; tot+=mt
        w('%-5s %-4s %7d %10.0f %12.0f %10.3f %8.1f%%'%(MON[m],scen,dt,tt,tn,mt,100*mt*4/8 if False else 100*mt/(8/ (len([x for x in (9,10,11,12)])) ) if False else 100*mt/8*1))
    ld_tot[scen]=tot
# fix % col: per-month share vs 8Mt total is confusing; print again cleanly
out=[l for l in out if not l.startswith(('Sep ','Oct ','Nov ','Dec ')) or 'S1' not in l or True]

w(); w('D · SCENARIO COMPARISON (Sep-Dec combined)')
w('%-4s %14s %8s %10s %10s %10s'%('Scen','LD Mt Sep-Dec','%of8Mt','FleetDT*','AvgT/DT','WorstOver'))
for scen in ('S1','S2','S3'):
    months=results.get(scen,{})
    alldt=[]; alltr=[]; wover=0
    for m,rows in months.items():
        rows=[r for r in rows if 'error' not in r]
        alldt.append(sum(r['dt'] for r in rows))
        alltr.append((sum(r['total_trips'] for r in rows),sum(r['dt'] for r in rows)))
        wover=max(wover,sum(1 for r in rows if r['status']=='overloaded'))
    at=sum(t for t,_ in alltr)/max(1,sum(d for _,d in alltr))
    w('%-4s %14.2f %7.1f%% %10s %10.2f %10d'%(scen,ld_tot.get(scen,0),100*ld_tot.get(scen,0)/8,
        '/'.join(str(d) for d in alldt),at,wover))
w('  *FleetDT = per month Sep/Oct/Nov/Dec')

w(); w('E · BOTTLENECK STORY - TF>HUAFEI (the LD corridor)')
for scen in ('S1','S2','S3'):
    for m in (11,):
        rows=[r for r in results.get(scen,{}).get(m,[]) if 'error' not in r and r['route']=='TF>HUAFEI' and 'LD' in (r['material'] or '')]
        for r in rows:
            c=r['components'] or {}
            w('%s Nov TF>HUAFEI LD: %d DT/%dL -> %.2f trips/DT (legacy said %.2f)'%(
                scen,r['dt'],r['loaders'],r['trips_per_dt'],r['legacy_trips_per_dt'] or 0))
            w('   cycle %.0f min = road %.0f free + %.0f BPR-penalty + queue %.0f + load %.0f + fixed %.0f | rho %.2f road_vc %.2f -> %s bottleneck'%(
                r['cycle_min'],c.get('t_free_road',0),c.get('bpr_penalty_minutes',0),
                c.get('queue_wait_minutes',0),c.get('t_load',0),
                (c.get('t_spot',0)+c.get('t_dump',0)),r['rho'],r['road_vc'],r['bottleneck']))
if uncal: w('\nUNCALIBRATED routes (defaults used): '+', '.join(sorted(uncal)))

print('\n'.join(out))
# CSV
with open('data/scenario_test_summary.csv','w',newline='') as f:
    cw=csv.DictWriter(f,fieldnames=list(summary_rows[0].keys()))
    cw.writeheader(); cw.writerows(summary_rows)
print('\nwrote data/scenario_test_results.json + data/scenario_test_summary.csv')
