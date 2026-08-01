// main.js — State, shared helpers, tab switching, renderers, event listeners and init.
// Loaded LAST: holds every top-level variable and all start-up execution.
// Extracted verbatim from templates/simulator.html (Phase 1 refactor; no logic changes).

const fmt=(n,d=0)=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:d});
const fmtM=n=>(n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(0)+'k':fmt(n));
function ymLbl(ym){const y=(''+ym).slice(2,4),m=+(''+ym).slice(4);return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]+"'"+y;}
// Trip/WMT eff vs plan. Values above ~200% mean the plan rate was mis-aggregated
// (TARGET TRIP is already trips/DT — see simulator_api._cap_load_rows). Refuse to
// paint a 1700% badge that looks like a win.
function eff(pct){
  if(pct==null||!Number.isFinite(pct)) return '<span class="muted">—</span>';
  if(pct>2||pct<0) return '<span class="muted" title="Plan target rate missing or invalid">—</span>';
  const c=pct>=0.95?'eg':(pct>=0.85?'ea':'er');
  return `<span class="eff ${c}">${Math.round(pct*100)}%</span>`;
}
const FLOW_SHIFT_HOURS=12,FLOW_SHIFT_START=7;
let _D=null, _initDone=false, _mode='actual', _trucks=null, _trucksServedFrom=null, _combined3D=null, _flowSim=null, _flowSource=null, _flowSpeedsInitialised=false, _flowPointScenario=null, _c3Tool='rotate', _flowMode='plan', _flowPlanDraft={}, _flowFleetAvailable=null, _otherCtx=null, _otherDraft={}, _otherInModel=true;
let _selSrc=new Set(), _selDest=new Set(), _effMetric='trips', _optObj='max_trips', _ec=null;

function q(id){return document.getElementById(id);}
// Debounce Apply so date-picker chatter / double-clicks do not fire overlapping
// capability reloads. 500 ms after the last change; in-flight requests are
// abandoned via the generation counter in load().
let _applyTimer=null;
function apply(){
  if(_applyTimer) clearTimeout(_applyTimer);
  const btn=document.querySelector('.filters .btn');
  if(btn){ btn.disabled=true; btn.textContent='Loading…'; }
  _applyTimer=setTimeout(()=>{
    _applyTimer=null;
    Promise.resolve(load()).finally(()=>{
      if(btn){ btn.disabled=false; btn.textContent='Apply'; }
    });
  }, 500);
}
function setMode(m){ _mode=m; q('mode-actual').classList.toggle('on',m==='actual'); q('mode-plan').classList.toggle('on',m==='plan'); if(_D) render(); }
function setEffMetric(m){ _effMetric=m; q('em-trips').classList.toggle('on',m==='trips'); q('em-wmt').classList.toggle('on',m==='wmt'); redrawScatter(); }
function onOpt(){ _optObj=q('opt-obj').value; q('opt-custom').style.display=_optObj==='custom'?'flex':'none'; redrawScatter(); }
// ── graph-side constraint-section + path filter — re-aggregates the scatter CLIENT-SIDE (no reload) ──
let _gSelSec=new Set(), _gSelPath=new Set();
let _xAxis='combined';   // path → path DT · section → total section DT · combined → both dimensions
function xAxisText(){ return _xAxis==='section'?'DT on section / day':'DT per path / day'; }
function updateEffControls(){
  const section=_xAxis==='section', combined=_xAxis==='combined', contextual=section||combined;
  q('eff-title').textContent=combined?'Combined DT load vs selected-path efficiency (per day)':section?'DT on section vs selected-path efficiency (per day)':'Efficiency — production vs fleet size (per day)';
  q('path-opt-controls').style.display=contextual?'none':'contents';
  q('eff-metric-controls').style.display=contextual?'none':'contents';
  q('legend-wmt').style.display=contextual?'none':'';
  q('legend-marg').style.display=combined?'none':'';
  q('legend-over').style.display=contextual?'none':'';
  q('legend-eff').textContent=combined?'Colour = path · height = Trips/DT · hover a point for laser grid':section?'━ Selected-path Trips/DT trend':'━ Efficiency trend (right axis)';
  q('legend-marg').textContent=section?'╌ Marginal Δ Trips/DT per +50 section DT':'╌ Marginal per +1 DT (far right)';
  q('legend-range').style.display=combined?'none':'';
  q('legend-range').innerHTML=section?'<i class="zb" style="background:rgba(34,197,94,.5)"></i>highest observed efficiency bins':'<i class="zb" style="background:rgba(34,197,94,.5)"></i>recommended range';
  q('c3-analysis').style.display=combined?'grid':'none';
}
function setXAxis(m){
  _xAxis=m;
  q('xa-path').classList.toggle('on',m==='path');
  q('xa-section').classList.toggle('on',m==='section');
  q('xa-combined').classList.toggle('on',m==='combined');
  updateEffControls();
  redrawScatter();
  // Section load is undefined until a constraint section is chosen. Open the
  // selector so the user can complete the mode change instead of silently
  // falling back to path DT.
  if((m==='section'||m==='combined')&&!_gSelSec.size) q('ms-gsec-panel').classList.add('open');
}
function curDaily(){
  if(!_D || !_D.dailyByPath) return (_D&&_D.daily)||[];
  const keys=gPathKeys();                                  // Y = efficiency of the selected path(s)
  if(!keys || !keys.size) return _D.daily||[];
  // Section mode: X = assigned DT on every mapped path crossing the selected section that day;
  // Y remains Trips/DT for the selected path scope. This is descriptive congestion context, not causality.
  const secMode=(_xAxis==='section'||_xAxis==='combined');
  const secKeys=(secMode && _gSelSec.size)? new Set(gsecPaths().map(p=>pathKey(p.origin,p.dest))) : null;
  const by={}, secDT={}, secPlanDT={};
  (_D.dailyByPath||[]).forEach(r=>{ const k=pathKey(r.o,r.dd);
    if(keys.has(k)){ const a=by[r.d]||(by[r.d]=[0,0,0,0,0,0]); a[0]+=r.w;a[1]+=r.rit;a[2]+=r.nb;a[3]+=r.dtp;a[4]+=r.pw;a[5]+=r.ptr; }
    if(secKeys && secKeys.has(k)){ secDT[r.d]=(secDT[r.d]||0)+r.nb; secPlanDT[r.d]=(secPlanDT[r.d]||0)+r.dtp; } });
  return Object.keys(by).map(d=>{ const[w,rit,nb,dtp,pw,ptr]=by[d];
    const xActual=(secKeys && secDT[d]!=null)? secDT[d] : nb;
    const xPlan=(secKeys && secPlanDT[d]!=null)? secPlanDT[d] : dtp;
    return {date:d,dt:xActual,wmt:w,tripsPerDT:(nb?rit/nb:0),planDt:xPlan,planWmt:pw,planTripsPerDT:(dtp?ptr/dtp:0),
      pathDt:nb,sectionDt:xActual,planPathDt:dtp,planSectionDt:xPlan}; }).sort((a,b)=>a.dt-b.dt);
}
// ── multi-select checkbox dropdowns ──
function msToggle(k){ const p=q('ms-'+k+'-panel'); document.querySelectorAll('.ms-panel').forEach(x=>{if(x!==p)x.classList.remove('open');}); p.classList.toggle('open'); }
document.addEventListener('click',e=>{ if(!e.target.closest('.ms')) document.querySelectorAll('.ms-panel').forEach(x=>x.classList.remove('open')); });
function msOptions(k){ if(!_D) return []; if(k==='source') return [...new Set((_D.routes||[]).map(r=>r.origin))].sort();
  const srcs=_selSrc; return [...new Set((_D.routes||[]).filter(r=>!srcs.size||srcs.has(r.origin)).map(r=>r.dest))].sort(); }
function msRender(k){ const sel=k==='source'?_selSrc:_selDest, opts=msOptions(k), p=q('ms-'+k+'-panel');
  const allOn=opts.length&&opts.every(o=>sel.has(o))||sel.size===0;
  p.innerHTML=`<label class="all"><input type="checkbox" ${sel.size===0?'checked':''} onchange="msAll('${k}',this.checked)"> Select all</label>`+
    opts.map(o=>`<label><input type="checkbox" ${sel.has(o)?'checked':''} onchange="msPick('${k}','${o.replace(/'/g,"\\'")}',this.checked)"> ${o}</label>`).join('');
  msLabel(k);
}
function msAll(k,on){ const sel=k==='source'?_selSrc:_selDest; sel.clear(); if(k==='source'){_selDest.clear(); msRender('dest');} msRender(k); }
function msPick(k,v,on){ const sel=k==='source'?_selSrc:_selDest; if(on)sel.add(v); else sel.delete(v); if(k==='source'){ // drop dests not under any selected source
    const valid=new Set(msOptions('dest')); [..._selDest].forEach(d=>{if(!valid.has(d))_selDest.delete(d);}); msRender('dest'); } msRender(k); }
function msLabel(k){ const sel=k==='source'?_selSrc:_selDest; q('ms-'+k+'-btn').textContent=(k==='source'?'Sources: ':'Destinations: ')+(sel.size===0?'All':(sel.size===1?[...sel][0]:sel.size+' selected'))+' ▾'; }
// ── type multi-select (top bar) ──
let _selType=new Set();
function typeRender(){
  const p=q('ms-type-panel'), opts=(_D&&_D.types)||[];
  p.innerHTML=`<label class="all"><input type="checkbox" ${_selType.size===0?'checked':''} onchange="typeAll(this.checked)"> All types</label>`+
    opts.map(o=>`<label><input type="checkbox" ${_selType.has(o.type)?'checked':''} onchange="typePick('${String(o.type).replace(/'/g,"\\'")}',this.checked)"> ${escH(o.type)} <span class="muted" style="margin-left:auto">${fmtM(o.t)} t</span></label>`).join('');
  q('ms-type-btn').textContent='Types: '+(_selType.size===0?'All':(_selType.size===1?[..._selType][0]:_selType.size+' selected'))+' ▾';
}
function typeAll(on){ _selType.clear(); typeRender(); }
function typePick(v,on){ if(on)_selType.add(v); else _selType.delete(v); typeRender(); }

// ── Path / constraint-section filtering (matrix-driven) ──
// Keep the agreed 3-section × 8-path matrix available immediately. The API remains the persisted source,
// but a slow/failed request must never turn the editor into an empty list of every route in the database.
const _MATRIX_DEFAULT={sections:[{id:1,name:'TOFU-KR'},{id:2,name:'KR-POS 12'},{id:3,name:'POS 12-POS 10'}],paths:[
  {origin:'TF',dest:'POS 12',sections:[1,2]},{origin:'TF',dest:'POS 10',sections:[1,2,3]},
  {origin:'TF',dest:'FENI KM15',sections:[1,2,3]},{origin:'TF',dest:'FENI KM0',sections:[1,2,3]},
  {origin:'KR',dest:'POS 12',sections:[2]},{origin:'KR',dest:'POS 10',sections:[2,3]},
  {origin:'KR',dest:'FENI KM15',sections:[2,3]},{origin:'KR',dest:'FENI KM0',sections:[2,3]}
]};
const matrixCopy=x=>JSON.parse(JSON.stringify(x));
let _filterMode='sd', _matrix=matrixCopy(_MATRIX_DEFAULT), _selPath=new Set();
function escH(s){ return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
let _pathSearch='';
// ── Matrix editor pop-up ──
let _matEdit=null;
function render(){
  const d=_D, k=d.kpi, plan=(_mode==='plan');
  q('scope').textContent=`${d.from} → ${d.to} · ${k.days} operating days`+((d.typesSel&&d.typesSel.length)?` · ${d.typesSel.join('/')}`:'')+(d.source?` · ${d.source}`:'')+(d.dest?` → ${d.dest}`:'')+(d.inclIwip?' · incl IWIP':' · excl IWIP');
  const wmt=plan?k.planWmtPerDay:k.wmtPerDay, dt=plan?k.planDtPerDay:k.dtPerDay,
        tpd=plan?k.planTripsPerDT:k.tripsPerDT, prod=plan?k.planTPerDT:k.tPerDT;
  const other=plan?'actual':'plan';
  // Clamp the KPI trip-eff badge the same way table cells use eff() — a 1700%
  // card is how the TARGET TRIP aggregation bug presented in the Tab 1 QC.
  const tripEffLabel=(k.effTrip!=null&&Number.isFinite(k.effTrip)&&k.effTrip>=0&&k.effTrip<=2)
    ? (Math.round(k.effTrip*100)+'%') : '—';
  const wmtEffLabel=(k.effWMT!=null&&Number.isFinite(k.effWMT)&&k.effWMT>=0&&k.effWMT<=2)
    ? (Math.round(k.effWMT*100)+'%') : '—';
  const kpis=[
    [wmt!=null?fmtM(wmt):'—','t/day',(plan?'Planned':'Actual')+' WMT / day', (plan?k.wmtPerDay:k.planWmtPerDay)!=null?(other+' '+fmtM(plan?k.wmtPerDay:k.planWmtPerDay)):''],
    [dt!=null?fmt(dt):'—','DT/day',(plan?'Planned':'Actual')+' DT / day', (plan?k.dtPerDay:k.planDtPerDay)!=null?(other+' '+fmt(plan?k.dtPerDay:k.planDtPerDay)):''],
    [tpd!=null?fmt(tpd,2):'—','trips/DT','Trips per truck', k.tf?('TF '+fmt(k.tf,1)+' t'):''],
    [prod!=null?fmt(prod):'—','t/DT','Productivity / truck / day',''],
    [wmtEffLabel,'','WMT vs plan',''],
    [tripEffLabel,'','Trip eff vs plan',''],
  ];
  q('kpis').innerHTML=kpis.map(x=>`<div class="kpi"><div class="v">${x[0]} <span class="u">${x[1]}</span></div><div class="l">${x[2]}</div>${x[3]?`<div class="sub">${x[3]}</div>`:''}</div>`).join('');

  q('calc-prod').textContent=fmt(prod||k.tPerDT);
  if(!q('calc-t').value) q('calc-t').value=Math.round(k.wmtPerDay);
  q('calc-note').innerHTML=`Based on ${plan?'planned':'actual'} productivity of <b>${fmt(prod||k.tPerDT)} t/truck/day</b> (WMT ÷ DT) for this selection.`;
  calc();

  q('eff-mode').textContent=plan?'planned':'actual';
  // Render production tables first so a chart error can never blank the operational data below.
  const cp=d.contractorProd||[];
  q('prod').innerHTML=cp.map(x=>row7(x.contractor,x)).join('')||'<tr><td colspan="7" class="empty">No data.</td></tr>';
  q('destcnt').textContent=(d.destinations||[]).length+' shown';
  renderPaths(); renderDests();
  try{drawChart(d.months||[]);}catch(e){console.error('Monthly trend failed',e);q('chart').innerHTML='<text x="500" y="130" fill="#f87171" font-size="13" text-anchor="middle">Monthly trend could not be rendered.</text>';}
  try{drawScatter(curDaily(), plan);}catch(e){console.error('Capability visualisation failed',e);q('scatter').innerHTML='<text x="500" y="155" fill="#f87171" font-size="13" text-anchor="middle">Visualisation could not be rendered. Production tables remain available below.</text>';q('c3-analysis').style.display='none';}
}
function renderTrucks(){
  if(!_trucks) return; const qs=(q('trucksearch').value||'').trim().toLowerCase();
  const rows=_trucks.filter(t=>!qs||(t.truck+' '+t.contractor).toLowerCase().includes(qs));
  // Fixture / unfiltered — the dispatch capability view has no TRUCK_ID, so this
  // list cannot honour the date/IWIP/source bar. Say so; do not look measured.
  const note=_trucksServedFrom==='fixture'?' · sample list (not filtered by bar above)':'';
  q('truckcnt').textContent=rows.length+(qs?(' of '+_trucks.length):'')+' trucks'+note;
  q('trucks').innerHTML=rows.map(t=>`<tr><td><b>${t.truck}</b></td><td class="muted">${t.contractor}</td><td class="r">${fmt(t.trips)}</td><td class="r">${fmt(t.tripsPerDay,1)}</td><td class="r">${fmtM(t.wmt)}</td><td class="r muted">${fmt(t.tf,1)}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">No matching trucks.</td></tr>';
}
function row7(name,x){ return `<tr><td><b>${name}</b></td><td class="r">${fmtM(x.t)}</td><td class="r">${fmt(x.tripsPerDT,2)}</td><td class="r muted">${fmt(x.tf,1)}</td><td class="r muted">${x.planTripsPerDT!=null?fmt(x.planTripsPerDT,2):'—'}</td><td class="r">${eff(x.effTrip)}</td><td class="r">${eff(x.effWMT)}</td></tr>`; }

function calc(){
  if(!_D) return; const t=parseFloat(q('calc-t').value||0), prod=_D.kpi.tPerDT;
  q('calc-out').textContent=(t>0&&prod>0)?fmt(Math.ceil(t/prod)):'—';
}
function renderPaths(){
  if(!_D) return; const qs=(q('pathsearch').value||'').trim().toLowerCase();
  const rows=(_D.paths||[]).filter(p=>!qs||(p.origin+' → '+p.dest).toLowerCase().includes(qs));
  q('pathwin').textContent=qs?(rows.length+' of '+_D.paths.length+' match'):(_D.paths.length+' shown');
  q('paths').innerHTML=rows.map(p=>row7(p.origin+' <span class="muted">→</span> '+p.dest,p)).join('')||'<tr><td colspan="7" class="empty">No matching routes.</td></tr>';
}
function renderDests(){
  if(!_D) return; const qs=(q('destsearch').value||'').trim().toLowerCase();
  const rows=(_D.destinations||[]).filter(x=>!qs||(x.dest||'').toLowerCase().includes(qs));
  q('dests').innerHTML=rows.map(x=>`<tr><td>${x.dest}</td><td class="r">${fmtM(x.t)}</td><td class="r">${fmt(x.tripsPerDT,2)}</td><td class="r muted">${fmt(x.tf,1)}</td><td class="r">${eff(x.effTrip)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">No matching destinations.</td></tr>';
}
const _avg=(a,f)=>a.length?a.reduce((s,x)=>s+f(x),0)/a.length:0;

// Predicted trips/DT for the CURRENT fleet: anchored at the actual (so replay is exact), then the
// historically-measured decline (b<0 only) is applied to the fleet delta. Confounded/flat paths stay flat.
let _pathResp=null;
function renderRainContext(error){const body=q('cap-rain');if(!body)return;if(error){body.innerHTML=`<tr><td colspan="5" class="muted">${escH(error)}</td></tr>`;return;}
  // DRY/WET compare wet vs dry days AT SIMILAR FLEET (each wet day paired with dry days at a matching
  // truck count). No linear model — apples-to-apples. Shows rain only clearly hurts a few routes.
  const rows=Object.entries(_pathResp||{}).map(([key,m])=>{const dry=Number.isFinite(m.mDry)?m.mDry:null,wet=Number.isFinite(m.mWet)?m.mWet:null,pct=(dry&&wet)?100*(wet-dry)/dry:null;return {key:key.replace('>',' → '),m,dry,wet,pct};}).filter(x=>x.pct!==null).sort((a,b)=>a.pct-b.pct);
  body.innerHTML=rows.length?rows.map(x=>{const signal=x.pct<=-5?'Rain-sensitive':x.pct<=-2?'Small wet-weather loss':x.pct<2?'No clear effect':'Wet not worse',cls=x.pct<=-5?'er':x.pct<=-2?'ea':'eg';return `<tr><td><b>${escH(x.key)}</b><br><span class="muted">${fmt(x.m.mN)} matched wet days</span></td><td class="r">${fmt(x.dry,2)}</td><td class="r">${fmt(x.wet,2)}</td><td class="r ${cls}">${x.pct>0?'+':''}${fmt(x.pct,1)}%</td><td class="${cls}">${signal}</td></tr>`;}).join(''):'<tr><td colspan="5" class="muted">No routes have enough fleet-matched wet/dry history.</td></tr>';}
let _shiftCtxDate=null,_wbShift='all';
function setWbShift(s){_wbShift=s;document.querySelectorAll('#wb-shift-toggle .wbsh').forEach(b=>b.classList.toggle('on',b.dataset.sh===s));_shiftCtxDate=null;_wbPosDate=null;const date=(_flowPointScenario&&_flowPointScenario.date)||'';if(date){loadShiftContext(date);loadWbPositions(0,date);}}
const _shParam=()=>(_wbShift&&_wbShift!=='all'?'&shift='+_wbShift:'');
function renderIwipImpact(d){
  const hdr=q('cap-iwip-shift'),body=q('cap-iwip');if(!body)return;
  if(!d){if(hdr)hdr.innerHTML='';body.innerHTML='<tr><td colspan="4" class="muted">Select a scenario point on the chart to estimate IWIP impact for that shift.</td></tr>';return;}
  const feni=d&&d.otherFeniTrips,typ=d&&d.otherFeniTypical;
  if(!Number.isFinite(feni)||!Number.isFinite(typ)||!typ){if(hdr)hdr.innerHTML='';body.innerHTML='<tr><td colspan="4" class="muted">No IWIP traffic data for this shift (pre-Dec 2025), or select a scenario on the chart.</td></tr>';return;}
  const impact=OTHER_TRAFFIC_COEF*(feni-typ),heavier=feni>typ,cls0=impact<=-0.03?'er':impact<0?'ea':'eg';
  if(hdr)hdr.innerHTML=`<div style="font-size:11.5px;padding:6px 8px;background:rgba(148,163,184,.08);border-radius:6px"><b>This shift (${escH(d.date)}):</b> <b>${fmt(feni)}</b> FENI-corridor IWIP trips vs typical <b>${fmt(typ)}</b> — <span class="${cls0}">${heavier?'heavier':'lighter'} than usual, est. <b>${(impact>=0?'+':'')+fmt(impact,2)} trips/DT</b> on shared routes</span></div>`;
  const routes=Object.entries(_pathResp||{}).filter(([k,m])=>/FENI/i.test((k.split('>')[1]||''))&&Number.isFinite(m.avgTr)).map(([k,m])=>({key:k.replace('>',' → '),base:m.avgTr,pct:m.avgTr?100*impact/m.avgTr:0})).sort((a,b)=>a.pct-b.pct);
  body.innerHTML=routes.length?routes.map(r=>{const sig=r.pct<=-3?'Heavy IWIP drag':r.pct<=-1?'Some IWIP drag':r.pct>=1?'IWIP light — helped':'Negligible',cls=r.pct<=-3?'er':r.pct<=-1?'ea':'eg';return `<tr><td><b>${escH(r.key)}</b></td><td class="r">${fmt(r.base,2)}</td><td class="r ${cls}">${(impact>=0?'+':'')+fmt(impact,2)} <span class="muted">(${r.pct>0?'+':''}${fmt(r.pct,1)}%)</span></td><td class="${cls}">${sig}</td></tr>`;}).join(''):'<tr><td colspan="4" class="muted">No FENI-bound routes with history yet.</td></tr>';
}
function renderShiftContext(d){
  renderIwipImpact(d);
  // Non-WBN (IWIP / Position) road users: congestion contributors, NO WBN WMT. Feed the scenario congestion.
  _otherCtx={fleet:d.otherFleet||0,trips:d.otherTrips||0,bySection:{},date:d.date,paths:d.otherPaths||[]};
  (d.otherBySection||[]).forEach(s=>{_otherCtx.bySection[s.section]=s.trips;});
  _otherDraft={};_otherCtx.paths.forEach(p=>{_otherDraft[p.label]=p.trucks;});   // per-path editable, reset to actual
  if(_flowSource)renderFlowSimulator(_flowSource.P,_flowSource.colours,true);   // rebuild to draw the white trucks
  else if(_flowSim){renderFlowPlanner();evaluateFlowScenario();}
  // Update the summary KPIs to THIS selected shift (they otherwise show only the latest day).
  if(d.wbAvailable&&d.bridges&&d.bridges.length){const tot=d.bridges.reduce((n,b)=>n+b.trucks,0)||1,busiest=d.bridges[0],otherT=d.bridges.reduce((n,b)=>n+b.trucks*(b.otherPct||0)/100,0),setT=(id,v)=>{const e=q(id);if(e)e.textContent=v;};
    setT('cap-wb-open',fmt(d.bridges.length));setT('cap-wb-trucks',fmt(tot));setT('cap-wb-share',fmt(busiest.pct,1)+'%');setT('cap-wb-other',fmt(100*otherT/tot,1)+'%');
    const st=q('cap-wb-status');if(st){const crit=busiest.pct>40,watch=busiest.pct>25;st.style.borderLeftColor=crit?'#ef4444':watch?'#f59e0b':'#22c55e';st.textContent=`${crit?'🔴':watch?'🟡':'🟢'} ${crit?'Load concentrated':watch?'Monitor concentration':'Balanced'} · ${fmt(tot/d.bridges.length,1)} trucks/bridge · busiest WB ${busiest.wb} · ${escH(d.date)} (${_wbShift==='1'?'day':_wbShift==='2'?'night':'whole day'})`;}}
  else if(!d.wbAvailable){['cap-wb-open','cap-wb-trucks','cap-wb-share','cap-wb-other'].forEach(id=>{const e=q(id);if(e)e.textContent='—';});const st=q('cap-wb-status');if(st){st.style.borderLeftColor='#64748b';st.textContent='No weighbridge data for this shift (pre-Dec 2025)';}}
  const rb=q('cap-rain-shift');
  if(rb){const parts=(d.rain||[]).map(r=>`${r.area} ${fmt(r.mm,1)}mm`).join(' · ')||'no gauge data';const cls=d.rainMax>=10?'er':d.rainMax>=2?'ea':'eg';
    rb.innerHTML=`<div style="font-size:11.5px;padding:6px 8px;background:rgba(59,130,246,.06);border-radius:6px"><b>This shift (${escH(d.date)}):</b> <span class="${cls}">${parts}</span> — <span class="${cls}">${escH(d.rainAssess)}</span></div>`;}
  const wb=q('cap-wb-shift');
  if(wb){if(!d.wbAvailable){wb.innerHTML=`<div class="muted" style="font-size:11px">${escH(d.wbNote||'No weighbridge data for this shift.')}</div>`;return;}
    const rows=(d.bridges||[]).map((b,i)=>`<tr><td style="font-weight:600;white-space:nowrap">WB ${escH(b.wb)}</td><td style="width:34%"><span style="display:block;height:9px;background:var(--line);border-radius:3px;overflow:hidden"><i style="display:block;height:100%;width:${b.pct}%;background:${i===0?'#ef4444':'#3b82f6'}"></i></span></td><td class="r">${fmt(b.trucks)}</td><td class="r">${fmt(b.pct,1)}%</td><td class="r">${b.km!=null?'~'+fmt(b.km,0)+'km':'—'}</td><td class="${i===0?'er':'muted'}" style="white-space:nowrap">${i===0?'⚠ busiest':''}</td></tr>`).join('');
    const shLbl=d.shift==='1'?'day shift':d.shift==='2'?'night shift':'whole day';
    wb.innerHTML=`<div style="font-size:11px;color:var(--muted);margin:4px 0 6px">Bridges used ${escH(d.date)} · <b>${shLbl}</b> · busiest (red) = likely congestion point</div><table class="wb-tbl"><thead><tr><th>Bridge</th><th></th><th class="r">Trucks</th><th class="r">Share</th><th class="r">Est. km</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;}
}
let _wbPos=null,_wbPosDate=null;
// Measured non-WBN traffic effect: FENI-route trips/DT falls ~0.00035 per extra non-WBN trip on the
// shared POS→FENI corridor (from the fleet+rain+traffic regression, R2~0.21).
const OTHER_TRAFFIC_COEF=-0.00035;
const OTHER_SECS=[['TOFU–KR',39,67.8],['KR–POS 12',27,39],['POS 12–POS 10',17,27],['POS 10–FENI',0,17]];
// default date range then load
q('f-from').value='2025-09-01'; q('f-to').value=new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,10);
// ── Congestion-model preview tab (measured speed-vs-traffic + tunable speed-density model) ──
let _congData=null,_congLoaded=false;
function setSimTab(t){
  ['sim','cong','plan','plansim'].forEach(x=>{const b=q('tabbtn-'+x),p=q('tab-'+x);if(b)b.classList.toggle('on',t===x);if(p)p.style.display=t===x?'':'none';});
  if(t==='cong'&&!_congLoaded){_congLoaded=true;loadCongModel();}
  if(t==='plan')renderPlanBuilder();
  if(t==='plansim')psInit();
}
let _planDraft={};
let _wbData=null,_wbLoaded=false;
function renderWeighbridge(){
  if(!_wbData)return;const days=_wbData.days||[],bridges=_wbData.bridges||[],curve=_wbData.waitCurve||[];
  // KPIs from the most recent day + the wait-curve extremes
  const last=days[days.length-1]||{},avgBr=days.length?days.reduce((s,d)=>s+d.bridges,0)/days.length:0;
  const c0=curve[0]||{},cN=curve[curve.length-1]||{},lift=(c0.wait&&cN.wait)?100*(cN.wait-c0.wait)/c0.wait:null;
  q('wb-kpis').innerHTML=[
    ['Bridges open (latest)',fmt(last.bridges||0)+' <span class="muted">of 18</span>'],
    ['Trucks / bridge (latest)',fmt(last.perBridge||0)],
    ['Non-WBN share of bridge load',(_wbData.otherSharePct!=null?_wbData.otherSharePct+'%':'—')],
    ['Peak-hour wait lift',lift!=null?('+'+Math.round(lift)+'%'):'—']
  ].map(k=>`<div class="effkpi"><b>${k[1]}</b><span>${k[0]}</span></div>`).join('');
  // ---- daily bars (trucks/bridge) + concentration line (busiest share) ----
  const W=1000,H=300,padL=48,padR=44,padB=42,padT=14,iw=W-padL-padR,ih=H-padT-padB;
  const maxPB=Math.max(10,...days.map(d=>d.perBridge)),bw=iw/Math.max(1,days.length);
  const x=i=>padL+i*bw,yPB=v=>padT+ih-ih*v/maxPB,yShare=v=>padT+ih-ih*v/100;
  let s=`<line x1="${padL}" y1="${padT+ih}" x2="${padL+iw}" y2="${padT+ih}" stroke="var(--line)"/>`;
  s+=`<text x="6" y="${padT+8}" fill="var(--muted)" font-size="10">${fmt(maxPB)}</text><text x="6" y="${padT+ih}" fill="var(--muted)" font-size="10">0</text>`;
  s+=`<text x="${W-6}" y="${padT+8}" fill="#f59e0b" font-size="10" text-anchor="end">100%</text>`;
  days.forEach((d,i)=>{const h=ih*d.perBridge/maxPB,wbnFrac=d.trucks?d.wbn/d.trucks:0,hW=h*wbnFrac,hO=h-hW,bx=x(i)+bw*.12,bwid=bw*.76;
    const tip=`${d.date}\n${d.bridges} bridges · ${fmt(d.trucks)} trucks (${fmt(d.wbn)} WBN + ${fmt(d.other)} non-WBN, ${d.otherShare}%)\nbusiest ${d.busiestShare}%${d.avgWait!=null?' · wait '+d.avgWait+'m':''}`;
    s+=`<rect x="${bx}" y="${yPB(d.perBridge)}" width="${bwid}" height="${Math.max(0,hO)}" fill="#94a3b8" opacity=".5"><title>${tip}</title></rect>`;
    s+=`<rect x="${bx}" y="${(padT+ih-hW).toFixed(1)}" width="${bwid}" height="${Math.max(0,hW)}" fill="#3b82f6" opacity=".65"><title>${tip}</title></rect>`;});
  const line=days.map((d,i)=>`${(x(i)+bw/2).toFixed(1)},${yShare(d.busiestShare).toFixed(1)}`).join(' ');
  s+=`<polyline points="${line}" fill="none" stroke="#f59e0b" stroke-width="1.6"/>`;
  // month/date ticks (sparse)
  const step=Math.ceil(days.length/8);days.forEach((d,i)=>{if(i%step===0)s+=`<text x="${(x(i)+bw/2).toFixed(1)}" y="${H-8}" fill="var(--muted)" font-size="9" text-anchor="middle">${d.date.slice(5)}</text>`;});
  q('wb-svg').innerHTML=s;
  // ---- per-bridge list ----
  const maxTr=Math.max(1,...bridges.map(b=>b.trucks));
  q('wb-bridges').innerHTML=bridges.map(b=>`<div style="display:flex;align-items:center;gap:8px"><span style="width:34px;color:var(--txt);font-weight:600">WB ${escH(b.wb)}</span><span style="flex:1;height:11px;background:var(--line);border-radius:3px;overflow:hidden"><i style="display:block;height:100%;width:${(100*b.trucks/maxTr).toFixed(1)}%;background:#3b82f6"></i></span><span class="muted" style="width:150px;text-align:right">${fmt(b.trucks)} trucks · ${fmt(b.perDay)}/day · peak ${fmt(b.peakHr)}/hr</span></div>`).join('')||'<span class="muted">No data.</span>';
  // ---- wait-vs-load curve ----
  if(curve.length){const w=500,h=240,pl=44,pr=14,pb=34,pt=14,iw2=w-pl-pr,ih2=h-pt-pb;
    const maxL=Math.max(...curve.map(c=>c.load)),maxW=Math.max(...curve.map(c=>c.wait))*1.1;
    const cx=v=>pl+iw2*v/maxL,cy=v=>pt+ih2-ih2*v/maxW;
    let g=`<line x1="${pl}" y1="${pt+ih2}" x2="${pl+iw2}" y2="${pt+ih2}" stroke="var(--line)"/><line x1="${pl}" y1="${pt}" x2="${pl}" y2="${pt+ih2}" stroke="var(--line)"/>`;
    g+=`<text x="6" y="${pt+8}" fill="var(--muted)" font-size="10">${fmt(maxW)}m</text><text x="6" y="${pt+ih2}" fill="var(--muted)" font-size="10">0</text>`;
    g+=`<text x="${pl+iw2}" y="${h-6}" fill="var(--muted)" font-size="10" text-anchor="end">${fmt(maxL)} trucks/bridge-hr</text>`;
    const pl2=curve.map(c=>`${cx(c.load).toFixed(1)},${cy(c.wait).toFixed(1)}`).join(' ');
    g+=`<polyline points="${pl2}" fill="none" stroke="#22d3ee" stroke-width="2"/>`;
    curve.forEach(c=>{g+=`<circle cx="${cx(c.load).toFixed(1)}" cy="${cy(c.wait).toFixed(1)}" r="3.5" fill="#22d3ee"><title>${fmt(c.load)} trucks/bridge-hr → ${c.wait} min (n=${c.n})</title></circle><text x="${cx(c.load).toFixed(1)}" y="${cy(c.wait)-8}" fill="var(--muted)" font-size="9" text-anchor="middle">${c.wait}m</text>`;});
    q('wb-wait-svg').innerHTML=g;
  }
  q('wb-note').innerHTML=`Bars = trucks per active bridge each day, split <b style="color:#3b82f6">WBN revenue haulers</b> / <b style="color:#94a3b8">non-WBN</b> (IWIP internal, PT Position — ~${_wbData.otherSharePct||0}% of all bridge traffic); amber line = the busiest bridge's share (higher = load piled on fewer bridges). ${lift!=null?`Measured waits rise ~${Math.round(lift)}% from the quietest to the busiest bridge-hours — real queueing at peak, but modest.`:''} These non-WBN trucks add road/bridge congestion but no WBN WMT; the efficiency model excludes them. Data: ${escH(_wbData.source||'')}.`;
}
function renderCongModel(){
  if(!_congData)return;const seg=(_congData.segments||[]).find(s=>s.seg===q('cong-seg').value)||_congData.segments[0];if(!seg)return;
  // default free-flow input to the measured value on first render for this segment
  const ffInput=q('cong-ff');if(!ffInput.value||ffInput.dataset.seg!==seg.seg){ffInput.value=seg.freeFlow;ffInput.dataset.seg=seg.seg;}
  const ff=Math.max(1,+ffInput.value||seg.freeFlow),jam=Math.max(5,+q('cong-jam').value||120),n=Math.max(.5,+q('cong-n').value||2);
  const W=1000,H=340,padL=54,padR=18,padB=44,padT=18,iw=W-padL-padR,ih=H-padT-padB;
  const maxX=Math.max(jam,seg.peakTrucks,...seg.obs.map(o=>o[0]))*1.05,maxY=Math.max(ff,...seg.obs.map(o=>o[1]))*1.1;
  const X=v=>padL+iw*v/maxX,Y=v=>padT+ih*(1-v/maxY);
  let s='';
  for(let g=0;g<=4;g++){const yy=padT+ih*g/4,val=maxY*(1-g/4);s+=`<line x1="${padL}" y1="${yy.toFixed(1)}" x2="${W-padR}" y2="${yy.toFixed(1)}" stroke="#16233c"/><text x="${padL-6}" y="${(yy+3).toFixed(1)}" fill="#64748b" font-size="10" text-anchor="end">${fmt(val,0)}</text>`;}
  for(let g=0;g<=5;g++){const xx=padL+iw*g/5,val=maxX*g/5;s+=`<text x="${xx.toFixed(1)}" y="${H-padB+16}" fill="#64748b" font-size="10" text-anchor="middle">${fmt(val,0)}</text>`;}
  s+=`<text x="${(padL+iw/2).toFixed(1)}" y="${H-6}" fill="#94a3b8" font-size="10" text-anchor="middle">trucks / hour on segment →</text><text x="14" y="${padT+ih/2}" fill="#3b82f6" font-size="10" transform="rotate(-90 14 ${padT+ih/2})" text-anchor="middle">measured speed (km/h)</text>`;
  // measured observations (sparse, honest)
  seg.obs.forEach(o=>{s+=`<circle cx="${X(o[0]).toFixed(1)}" cy="${Y(o[1]).toFixed(1)}" r="2.6" fill="#93c5fd" opacity="0.4"><title>${o[0]} trucks/hr · ${o[1]} km/h</title></circle>`;});
  // tunable model curve: speed = free-flow × (1 − (density/jam)^n), clamped ≥ 0
  let pts=[];for(let t=0;t<=maxX;t+=maxX/120){const sp=ff*(1-Math.pow(Math.min(1,t/jam),n));pts.push(X(t).toFixed(1)+','+Y(Math.max(0,sp)).toFixed(1));}
  s+=`<polyline points="${pts.join(' ')}" fill="none" stroke="#f59e0b" stroke-width="2.5"/>`;
  s+=`<line x1="${X(jam).toFixed(1)}" y1="${padT}" x2="${X(jam).toFixed(1)}" y2="${padT+ih}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4 4" opacity="0.6"/><text x="${(X(jam)-5).toFixed(1)}" y="${padT+12}" fill="#f87171" font-size="9" text-anchor="end">jam ${fmt(jam,0)}</text>`;
  q('cong-svg').innerHTML=s;
  q('cong-kpis').innerHTML=[
    ['Measured free-flow',fmt(seg.freeFlow,1),'km/h','p85 speed at low traffic'],
    ['Observed peak',fmt(seg.peakTrucks,0),'trucks/hr','busiest hour seen'],
    ['Avg speed',fmt(seg.avgSpeed,1),'km/h','all observed hours'],
    ['Observations',fmt(seg.n,0),'hours','sample size — sparse'],
  ].map(c=>`<div class="effkpi"><div class="v">${c[1]} <span class="u">${c[2]}</span></div><div class="l">${c[0]} · ${c[3]}</div></div>`).join('');
  q('cong-note').innerHTML=`Blue dots = <b>measured</b> speed vs traffic for <b>${escH(seg.seg)}</b> (${seg.n} hours over ~${_congData.days} days). Amber = the <b>tunable model</b> speed = free-flow × (1 − (density/jam)<sup>n</sup>). Right now the dots are flat (no congestion at this fleet); as production grows and higher-traffic hours accumulate, the dots will start bending down and you calibrate jam/n to fit — that's when it graduates from assumption to measurement.`;
}
(async()=>{await loadMatrix();loadPathResp();loadWbPositions();loadCapabilityWeighbridge();_gSelSec.clear();(_matrix.sections||[]).forEach(s=>_gSelSec.add(s.id));setXAxis('combined');await load();const requested=new URLSearchParams(location.search).get('tab');if(['sim','cong'].includes(requested))setSimTab(requested);})();
