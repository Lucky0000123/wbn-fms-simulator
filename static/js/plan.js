// plan.js — "Build a Plan" tab: contractor/shift/payload inputs and the
// regression-driven trips<->tonnage prediction. Split out of regression.js.
// Loads before main.js; main.js still owns _planDraft and all start-up execution.

// ── Plan tab ───────────────────────────────────────────────────────────────────
// Everything below is derived from data the app has ALREADY loaded — no new data sources:
//   • contractors + their Trips/DT and t/trip  → /api/simulator/capability  (_D.contractorProd)
//   • per-path regression a + b·DT (+ rain)    → /api/simulator/path-response (_pathResp)
//   • day→shift basis                          → _D.kpi + _D.shiftBasis
const WBN_HAULERS_FALLBACK=['RIM','PPP','SSS','SMA','STM','HJS','GMG','CKB','HFNC'];
let _planMode='dt';        // 'dt' → enter trucks, get WMT · 'wmt' → enter tonnage, get trucks
// Exact thousands-separated number — the Plan tab shows real figures ("2,154 t"), never "2k".
const fmtExact=(n,d=0)=>Number(n||0).toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d});
function _planValidKeys(){return Object.keys(_pathResp||{}).filter(k=>{const[o,d]=k.split('>'),m=_pathResp[k];return m&&m.n>=30&&m.tf>0&&Number.isFinite(m.avgTr)&&o&&d&&o.trim()&&d.trim()&&o.trim()!==d.trim();});}
// Contractor list comes from the capability API (the same rows the productivity table shows); the
// known WBN haulers are the fallback when that call hasn't landed or ran on a narrow filter.
function planContractors(){
  const seen=new Map();
  ((_D&&_D.contractorProd)||[]).forEach(c=>{const name=String(c.contractor||'').trim();
    if(!name||!WBN_HAULERS_FALLBACK.includes(name))return;
    const prev=seen.get(name);
    if(!prev||(c.t||0)>(prev.t||0))seen.set(name,{name,tripsPerDT:c.tripsPerDT,tf:c.tf,t:c.t});});
  WBN_HAULERS_FALLBACK.forEach(n=>{if(!seen.has(n))seen.set(n,{name:n,tripsPerDT:null,tf:null,t:0});});
  return WBN_HAULERS_FALLBACK.map(n=>seen.get(n));
}
function planContractor(name){const want=name||((q('plan-contractor')||{}).value);return planContractors().find(c=>c.name===want)||null;}
// How this contractor performs vs the whole selection: their Trips/DT ÷ fleet-wide Trips/DT.
// Clamped so a thin contractor sample can't produce an absurd multiplier.
function planContractorFactor(c){
  const fleet=_D&&_D.kpi&&_D.kpi.tripsPerDT;
  if(!c||!Number.isFinite(c.tripsPerDT)||!Number.isFinite(fleet)||!fleet)return 1;
  return Math.max(.5,Math.min(1.5,c.tripsPerDT/fleet));
}
// Day→shift conversion measured from the loaded data rather than assumed: the capability KPI carries
// both daily and per-shift Trips/DT, so their ratio IS the observed shift share. Scaled when the
// planner asks for a shift longer or shorter than the DB's shift length.
function planShiftFactor(){
  const k=(_D&&_D.kpi)||{},hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),
    base=(_D&&_D.shiftBasis&&_D.shiftBasis.hours)||12,
    ratio=(Number.isFinite(k.tripsPerDTShift)&&Number.isFinite(k.tripsPerDT)&&k.tripsPerDT)?k.tripsPerDTShift/k.tripsPerDT:.5;
  return Math.max(.05,Math.min(1,ratio))*(hours/base);
}
// Trips per DT for ONE shift on a path at a given fleet — the same regression the other pages use:
//   eff = avgTr + b·(DT − avgDT) + rain, × contractor factor, × day→shift factor.
// avgTr from path-response is the mid-60% trimmed mean of daily trips/DT
// (main cluster), not the raw arithmetic mean. Only a MEASURED decline (b<0)
// is applied; flat/confounded paths stay flat.
// Rain multiplier for trips/DT. Prefer measured wet/dry when rain clearly hurts;
// otherwise a modest default (~4% loss per 10 mm). Matches /api/predict.
function planRainScale(key,rain){
  const mm=Math.max(0,Number(rain)||0);if(!(mm>0))return 1;
  const m=_pathResp&&_pathResp[key];
  if(m&&Number.isFinite(m.mWet)&&Number.isFinite(m.mDry)&&m.mDry>0){
    const at=m.mDry+(m.mWet-m.mDry)*(mm/10), scale=at/m.mDry;
    if(scale<0.999)return Math.max(.5,Math.min(1,scale));
  }
  return Math.max(.75,1-0.04*(mm/10));
}
// Trips/DT drag from OTHER (IWIP / Position) traffic on the shared FENI
// corridor. Same measured coefficient and same typical baseline as the
// Capability page's IWIP-impact table (OTHER_TRAFFIC_COEF × excess-vs-typical
// FENI-corridor trips) — the concept the owner asked to reuse from page 1.
// Applies only to FENI-corridor destinations; other routes don't share that
// road section. Drag only: excess below typical returns 0.
const PLAN_FENI_DESTS=/FENI|CRUSHER|HUAFEI|BSE/i;
let _planOtherFeniTrips=null,_planOtherFeniTypical=null;  // set by planFetchOtherTraffic
function planOtherTrafficDelta(key){
  const dst=(key.split('>')[1]||'');
  if(!PLAN_FENI_DESTS.test(dst))return 0;
  const coef=typeof OTHER_TRAFFIC_COEF!=='undefined'?OTHER_TRAFFIC_COEF:-0.00035;
  // The FENI share was measured on ONE shift; the input (30-day median or a
  // manual edit) may differ from that shift's total. Scale proportionally so
  // the drag always reflects the number in the box.
  let feni=_planOtherFeniTrips,typ=_planOtherFeniTypical;
  if(!Number.isFinite(feni)||!Number.isFinite(typ)||!typ)return 0;
  if(_planOtherSrcTrips>0&&Number.isFinite(_planOtherTrips)&&_planOtherTrips!==_planOtherSrcTrips){
    feni=feni*(_planOtherTrips/_planOtherSrcTrips);
  }
  const excess=feni-typ;
  return excess>0?coef*excess:0;   // drag only
}
// ── Shared-section coupling (page 1's combined model, applied to the plan) ──
// The Capability tab's 3D model measures how a path's trips/DT responds to
// TOTAL SECTION DT (all paths sharing its corridor span), controlled for the
// path's own DT (c3PathEffects → effect per +50 section DT). The plan reuses
// THAT measured, path-specific coefficient: when the holding plan puts more DT
// on a path's shared span than that path historically saw, its trips/DT takes
// the measured drag. Drag only; paths with no measured decline stay flat.
let _planSecFx=null;
function _planSecFxGet(){
  if(_planSecFx)return _planSecFx;
  if(typeof combinedPathDays!=='function'||typeof c3PathEffects!=='function'||!_D)return null;
  try{
    const P=combinedPathDays(false);
    if(!P||P.length<8)return null;
    const by={};P.forEach(pt=>(by[pt.pathKey]=by[pt.pathKey]||[]).push(pt));
    const fx={};
    c3PathEffects(P).forEach(x=>{
      const g=by[x.key]||[];
      fx[x.key]={per50:x.effect,lo:x.lo,hi:x.hi,signal:x.signal,
        meanSection:g.length?g.reduce((n,pt)=>n+pt.section,0)/g.length:null};
    });
    _planSecFx=fx;
    return fx;
  }catch(_){return null;}
}
// Corridor span per node label (km) — from the served corridor geometry.
function _planNodeKm(name){
  const nodes=(_D&&_D.corridor&&_D.corridor.nodes)||[];
  const norm=x=>(x||'').trim().toUpperCase().replace(/\s+/g,' ');
  const hit=nodes.find(n=>(n.aliases||[n.label]).some(a=>norm(a)===norm(name)));
  return hit?hit.km:null;
}
function _planSpan(key){
  const [o,d]=key.split('>');
  const a=_planNodeKm(o),b=_planNodeKm(d);
  if(!Number.isFinite(a)||!Number.isFinite(b)||a===b)return null;
  return [Math.min(a,b),Math.max(a,b)];
}
// Today's expected section DT for `key`: own dt + draft rows whose corridor
// spans overlap (foreign road-only rows included — their trucks occupy the road).
function _planSectionDtNow(key,dt){
  const span=_planSpan(key);
  if(!span)return null;
  let tot=dt;
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||!(r.dt>0)||r.key===key)return;
    const s2=_planSpan(r.key);
    if(!s2)return;
    if(Math.min(span[1],s2[1])-Math.max(span[0],s2[0])>0)tot+=r.dt;
  });
  return tot;
}
function planSectionDrag(key,dt){
  const fx=_planSecFxGet();
  const f=fx&&fx[key];
  if(!f||!(f.per50<0)||!Number.isFinite(f.meanSection))return {delta:0,excess:0};
  // Only apply a MEASURED decline (page 1's own signal taxonomy).
  if(!/^(Clear|Likely)/.test(f.signal||''))return {delta:0,excess:0};
  const now=_planSectionDtNow(key,dt);
  if(now==null)return {delta:0,excess:0};
  const excess=now-f.meanSection;
  if(excess<=0)return {delta:0,excess:0};   // below typical section load: no credit, no drag
  return {delta:(f.per50/50)*excess,excess};
}
function planTripsPerDT(key,dt,rain,contractor){
  const m=_pathResp&&_pathResp[key];if(!m)return null;
  let tr=m.avgTr;
  const slope=(Number.isFinite(m.bAdj)&&m.bAdj<0)?m.bAdj:(m.b<0?m.b:0);
  if(slope<0&&Number.isFinite(m.avgDt))tr+=slope*(dt-m.avgDt);
  // Other (IWIP/Position) traffic on the shared FENI corridor: measured
  // coefficient from the Capability page's IWIP-impact model. DRAG ONLY —
  // lighter-than-typical foreign traffic earns no credit (avgTr already
  // contains the typical load; "never invent a gain").
  const otherDelta=planOtherTrafficDelta(key);
  tr+=otherDelta;
  // Shared-section coupling: the rest of the HOLDING PLAN on this path's span.
  const sec=planSectionDrag(key,dt);
  tr+=sec.delta;
  const scale=planRainScale(key,rain);
  const rainDelta=tr*(scale-1);
  tr=Math.max(.3*m.avgTr,tr*scale)*planContractorFactor(contractor);
  const sf=planShiftFactor();
  return {daily:tr,shift:tr*sf,rainDelta:rainDelta*sf,otherDelta:otherDelta*sf,secDelta:sec.delta*sf,secExcess:sec.excess,slope,m};
}
// Payload: the contractor's own measured t/trip when we have it, else the path's.
function planPayload(key,contractor){
  const m=_pathResp&&_pathResp[key];
  if(contractor&&Number.isFinite(contractor.tf)&&contractor.tf>0)return {tf:contractor.tf,src:'contractor avg'};
  return {tf:(m&&m.tf)||0,src:'path avg'};
}
// Swap-mode inverse: trucks needed for a tonnage target. Trips/DT itself depends on the fleet (the
// b·DT term), so solve by damped fixed-point iteration, then round UP — you can't run half a truck.
function planDtForWmt(key,targetWmt,rain,contractor){
  const pay=planPayload(key,contractor).tf;if(!(pay>0)||!(targetWmt>0))return null;
  const m=_pathResp&&_pathResp[key];let dt=Math.max(1,(m&&m.avgDt)||30);
  for(let i=0;i<60;i++){
    const e=planTripsPerDT(key,dt,rain,contractor);if(!e||!(e.shift>0))return null;
    const next=targetWmt/(e.shift*pay);
    if(!Number.isFinite(next)||next>1e6)return null;
    if(Math.abs(next-dt)<.01){dt=next;break;}
    dt=dt+.6*(next-dt);                      // damping keeps the declining-efficiency case stable
  }
  return Math.max(1,Math.ceil(dt));
}
function planSwapMode(){
  _planMode=_planMode==='dt'?'wmt':'dt';
  const dtBox=q('plan-input-dt'),wmtBox=q('plan-input-wmt');
  if(dtBox)dtBox.style.display=_planMode==='dt'?'':'none';
  if(wmtBox)wmtBox.style.display=_planMode==='wmt'?'':'none';
  planPreview();
}
let _planRainManual=false;
function planRainManual(){ _planRainManual=true; }
function planTodayISO(){
  const d=new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
let _planGpsCoverage=null;
let _planGpsPickBusy=false;

function planRenderGpsCoverage(data,selectedDate){
  _planGpsCoverage=data;
  const box=q('plan-gps-days')||q('plan-gps-coverage');
  const range=q('plan-gps-range');
  if(!box)return;
  if(!data||!data.ok){
    box.innerHTML='<span class="muted">Haul GPS calendar unavailable</span>';
    if(range)range.textContent='unavailable';
    return;
  }
  const days=data.days||[];
  if(!days.length){
    box.innerHTML='<span class="muted">No Jul+ haul GPS banked yet</span>';
    if(range)range.textContent='empty archive';
    return;
  }
  const sel=String(selectedDate||'').slice(0,10);
  // Show all banked days — easy to click
  const chips=days.map(d=>{
    const on=d.date===sel?' on':'';
    const tip=d.date+' · '+d.hours_n+'h · '+d.segs_n+' segs · '+d.fix_n+' fixes';
    return `<button type="button" class="plan-gps-chip${on}" data-date="${escH(d.date)}" title="${escH(tip)}"
      onclick="planPickGpsDay('${escH(d.date)}')">${escH(d.date.slice(5))}</button>`;
  }).join('');
  box.innerHTML=chips;
  if(range){
    range.textContent=(data.from||'?')+' → '+(data.to||'?')+' · '+days.length+' days · click for details';
  }
  // Keep hidden mirror for any legacy readers
  const hidden=q('plan-gps-coverage');
  if(hidden&&hidden!==box)hidden.textContent=days.length+' GPS days';
}

function planOpenDataNotes(){
  const notes=q('plan-data-notes');
  if(notes)notes.open=true;
}

function planRenderDayDetail(gpsData,opsData,dateS){
  const box=q('plan-day-detail');if(!box)return;
  const d=String(dateS||(gpsData&&gpsData.date)||(opsData&&opsData.date)||'').slice(0,10);
  if(!gpsData&&!opsData){
    box.innerHTML='<span class="muted">Select a GPS day to see that day’s GPS speeds and ops DT/trips.</span>';
    return;
  }
  let html=`<div><b>${escH(d)}</b> · selected day only</div>`;

  // Ops for THIS day (weighbridge path-days)
  if(opsData&&opsData.ok&&opsData.has_ops){
    const rows=(opsData.sections||[]).map(s=>
      `<tr><td><b>${escH(s.section)}</b></td>
        <td class="r">${escH(String(s.dt!=null?s.dt:s.total_dt))}</td>
        <td class="r">${escH(String(s.trips!=null?s.trips:s.total_trips))}</td></tr>`
    ).join('');
    html+=`<div style="margin-top:8px"><b>Ops that day</b>
      <span class="muted">(weighbridge · ${escH(opsData.corpus_source||'')} · ${escH(String(opsData.path_days_n||0))} path-days)</span></div>
      <p class="muted" style="margin:4px 0 0;font-size:11px">${escH(opsData.note||'')}</p>
      <table><thead><tr><th>Section</th><th class="r">DT that day</th><th class="r">Trips that day</th></tr></thead>
        <tbody>${rows||'<tr><td colspan="3" class="muted">No section crossings</td></tr>'}</tbody></table>`;
  }else if(opsData){
    html+=`<p class="muted" style="margin:8px 0 0">${escH((opsData&&opsData.note)||('No weighbridge ops rows for '+d))}</p>`;
  }

  // GPS for THIS day (Jul+ haul archive)
  if(gpsData&&gpsData.has_gps===false){
    html+=`<p class="muted" style="margin:8px 0 0">${escH(gpsData.note||'No haul GPS for this day.')}</p>`;
  }else if(gpsData&&gpsData.ok){
    const bySec=(gpsData.by_section||[]).map(s=>
      `<tr><td><b>${escH(s.section)}</b></td><td class="r">${escH(String(s.loadedKmh))}</td><td class="r">${escH(String(s.n))}</td></tr>`
    ).join('');
    html+=`<div style="margin-top:10px"><b>Haul GPS that day</b>
      <span class="muted">(${escH(gpsData.source||'')} · SEGS = stick segments with fixes)</span></div>
      <p class="muted" style="margin:4px 0 0;font-size:11px">${escH(gpsData.note||'')}</p>
      <table><thead><tr><th>Section</th><th class="r">Loaded km/h</th><th class="r">Segs</th></tr></thead>
        <tbody>${bySec||'<tr><td colspan="3" class="muted">No stick sections</td></tr>'}</tbody></table>`;
  }else if(gpsData&&!gpsData.ok){
    html+=`<p class="muted" style="margin:8px 0 0">${escH(gpsData.error||'GPS detail unavailable')}</p>`;
  }

  box.innerHTML=html;
}

function planPickGpsDay(dateS){
  const d=String(dateS||'').slice(0,10);
  if(!d||_planGpsPickBusy)return;
  _planGpsPickBusy=true;
  const el=q('plan-date');
  if(el)el.value=d;
  planOpenDataNotes();
  const daysBox=q('plan-gps-days');
  if(daysBox){
    [...daysBox.querySelectorAll('.plan-gps-chip')].forEach(btn=>{
      btn.classList.toggle('on',(btn.getAttribute('data-date')||'')===d);
    });
  }
  const detail=q('plan-day-detail');
  if(detail)detail.innerHTML='<span class="muted">Loading '+escH(d)+' (ops + GPS for that day)…</span>';
  planDateChange({fromGpsChip:true});
  Promise.all([
    fetch('/api/plan/day-segments?date='+encodeURIComponent(d)).then(r=>r.json()).catch(e=>({ok:false,error:String(e),date:d})),
    fetch('/api/plan/day-road-ops?date='+encodeURIComponent(d)).then(r=>r.json()).catch(e=>({ok:false,error:String(e),date:d,has_ops:false})),
  ]).then(([gps,ops])=>{
    planRenderDayDetail(gps,ops,d);
  }).finally(()=>{ _planGpsPickBusy=false; });
}

function planFetchGpsCoverage(selectedDate){
  return fetch('/api/plan/gps-coverage').then(r=>r.json()).then(data=>{
    planRenderGpsCoverage(data,selectedDate);
    return data;
  }).catch(()=>{
    planRenderGpsCoverage({ok:false},selectedDate);
    return null;
  });
}

function planRenderPlaybackTruth(data,selectedDate){
  const box=q('plan-playback-truth');if(!box)return;
  if(!data||!data.ok){
    box.innerHTML='';
    return;
  }
  const pb=data.playback||{};
  const ov=pb.haul_plate_overlap_pct;
  const ovTxt=(ov==null)?'0%':(Math.round(Number(ov)*10)/10)+'%';
  const sel=String(selectedDate||'').slice(0,10);
  const forDate=data.for_date||{};
  let dateLine='';
  if(sel){
    if(sel<(data.haul_gps_start||'2026-07-15')){
      dateLine=`Selected <b>${escH(sel)}</b>: ops/weighbridge only — <b>no invented haul GPS</b> from Playback.`;
    }else{
      dateLine=`Selected <b>${escH(sel)}</b>: haul GPS window — use corridor clock / day segments.`;
    }
  }
  if(forDate.note&&sel&&sel<(data.haul_gps_start||'2026-07-15')){
    dateLine=escH(forDate.note);
  }
  box.innerHTML=`<div><b>Playback ≠ haul GPS</b> · overlap with haul plates <b>${escH(ovTxt)}</b>
    · Playback ${escH((pb.window&&pb.window.from)||'?')}→${escH((pb.window&&pb.window.to)||'?')} is ${escH(pb.fleet||'support')}</div>
    <div style="margin-top:3px">${dateLine||escH(data.reason||'')}</div>
    <div class="muted" style="margin-top:3px">Peak ops tonnes: Capability Jan–May + simulate — not Playback speeds.</div>`;
}

function planFetchPlaybackTruth(selectedDate){
  const qs=selectedDate?('?date='+encodeURIComponent(selectedDate)):'';
  return fetch('/api/plan/playback-truth'+qs).then(r=>r.json()).then(data=>{
    planRenderPlaybackTruth(data,selectedDate);
    return data;
  }).catch(()=>{ planRenderPlaybackTruth(null); return null; });
}

function planRenderPeakProxy(data){
  const box=q('plan-peak-proxy');if(!box)return;
  if(!data||!data.ok){ box.innerHTML=''; return; }
  const rows=(data.busy_for_plan&&data.busy_for_plan.length?data.busy_for_plan:data.sections||[]).slice(0,4);
  const tr=rows.map(s=>`<tr>
    <td><b>${escH(s.section)}</b></td>
    <td class="r">${escH(String(s.avg_dt_per_day))}</td>
    <td class="r">${escH(String(s.avg_trips_per_day))}</td>
  </tr>`).join('');
  const win=data.window||{};
  box.innerHTML=`<div><b>Jan–May averages</b>
      <span class="muted">(${escH(win.from||'?')}→${escH(win.to||'?')} · ${escH(String(data.days_n||0))} days · reference only)</span></div>
    <div class="muted" style="margin-top:2px">${escH(data.note||'Not the selected GPS day.')}</div>
    <table><thead><tr><th>Section</th><th class="r">Avg DT/day</th><th class="r">Avg trips/day</th></tr></thead>
      <tbody>${tr||'<tr><td colspan="3" class="muted">No peak path-days</td></tr>'}</tbody></table>`;
}

function planFetchPeakProxy(){
  const plans=(typeof planDraftToAnaloguePlans==='function'?planDraftToAnaloguePlans():[])||[];
  return fetch('/api/plan/peak-road-proxy',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({plans}),
  }).then(r=>r.json()).then(data=>{
    planRenderPeakProxy(data);
    return data;
  }).catch(()=>{ planRenderPeakProxy(null); return null; });
}

let _planBiasLensOn=true; // default ON — ticket companion; engine primary stays raw
function planBiasLensToggle(){
  const el=q('plan-bias-lens');
  _planBiasLensOn=!!(el&&el.checked);
  if(typeof planRenderOutcomes==='function'&&typeof _planLastSim!=='undefined'&&_planLastSim){
    const pred=typeof planPredictTotals==='function'?planPredictTotals():{wmt:0,dt:0,trips:0};
    planRenderOutcomes(_planLastSim,pred);
  }
  if(typeof planRenderEstimateColumn==='function'&&typeof _planLastSim!=='undefined'&&_planLastSim){
    const pred=typeof planPredictTotals==='function'?planPredictTotals():{wmt:0,dt:0,trips:0};
    planRenderEstimateColumn(_planLastSim,pred);
  }
}

function planDateChange(opts){
  opts=opts||{};
  _planRainManual=false;
  const el=q('plan-date'), note=q('plan-date-note'), sug=q('plan-rain-suggest');
  const date=(el&&el.value)||'';
  if(!date){
    if(note)note.textContent='';
    if(sug)sug.innerHTML='';
    if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
    return;
  }
  if(note)note.textContent='Looking up rain…';
  if(sug)sug.innerHTML='';
  planFetchGpsCoverage(date);
  planFetchPlaybackTruth(date);
  planFetchPeakProxy();
  // Manual date pick (not chip): sync chip highlight; clear day detail until a GPS day is chosen
  if(!opts.fromGpsChip){
    const daysBox=q('plan-gps-days');
    if(daysBox){
      [...daysBox.querySelectorAll('.plan-gps-chip')].forEach(btn=>{
        btn.classList.toggle('on',(btn.getAttribute('data-date')||'')===date);
      });
    }
    const detail=q('plan-day-detail');
    const inArchive=(_planGpsCoverage&&(_planGpsCoverage.days||[]).some(x=>x.date===date));
    if(detail&&!inArchive){
      detail.innerHTML='<span class="muted">Click a Haul GPS day to open segment details for that date.</span>';
    }
  }
  if(typeof planCheckSavedExists==='function'){
    planCheckSavedExists(date).then(exists=>{
      if(!exists)return;
      const n=typeof planDraftEntries==='function'?planDraftEntries().length:0;
      const st=q('plan-save-status');
      if(n<1){
        // Empty draft — auto-load saved plan for this date
        if(typeof planLoadSavedForDate==='function'){
          planLoadSavedForDate({quiet:true}).then(ok=>{
            if(st)st.textContent=ok?'Loaded saved plan for '+date:'Saved plan available — click Load saved';
          });
        }else if(st)st.textContent='Saved plan available — click Load saved';
      }else if(st){
        st.textContent='Saved plan on file for '+date+' (Load to replace)';
      }
    });
  }
  fetch('/api/plan/rain-suggest?date='+encodeURIComponent(date))
    .then(r=>r.json())
    .then(res=>{
      if(!res||!res.ok){ if(note)note.textContent=''; return; }
      if(note)note.textContent=(res.label||'')+(res.mm!=null?' · '+Math.round(res.mm)+' mm':'');
      if(sug){
        sug.innerHTML=escH(res.note||'')
          +(res.apply?` <button type="button" class="ms-btn" onclick="planApplyRainSuggest(${Number(res.mm)||0})">Use ${Math.round(res.mm)} mm</button>`:'');
      }
      // Auto-apply when user hasn't typed rain manually
      if(!_planRainManual&&res.apply&&res.mm!=null){
        const rain=q('plan-rain');
        if(rain){ rain.value=String(Math.round(res.mm)); computePlan(); }
      }
    })
    .catch(()=>{ if(note)note.textContent='Rain lookup failed'; });
}
function planApplyRainSuggest(mm){
  _planRainManual=false;
  const rain=q('plan-rain');
  if(rain)rain.value=String(Math.max(0,Math.round(mm)));
  computePlan();
}

// ── 16-day site rain outlook (Open-Meteo forecast, no key) ───────────────────
// One strip for the whole planning horizon so "when should we plan the big
// push?" is answerable at a glance. Clicking a day sets the plan date; the
// existing rain-suggest flow then applies that day's forecast mm to Step 1.
let _planRainOutlook=null;
function planFetchRainOutlook(){
  fetch('/api/plan/rain-outlook',{cache:'no-store'})
    .then(r=>r.json())
    .then(res=>{_planRainOutlook=res;planRenderRainOutlook();})
    .catch(()=>{_planRainOutlook=null;planRenderRainOutlook();});
}
function planRenderRainOutlook(){
  const box=q('plan-rain-outlook');
  const wrap=q('plan-rain-outlook-details');
  if(!box)return;
  const res=_planRainOutlook;
  if(!res||!res.ok||!(res.days||[]).length){
    box.innerHTML='';
    if(wrap)wrap.hidden=true;
    return;
  }
  if(wrap)wrap.hidden=false;
  const sumLabel=document.querySelector('#plan-rain-outlook-details .plan-ro-sum-label');
  if(sumLabel)sumLabel.textContent='Rain outlook · next '+res.days.length+' days';
  const sel=(q('plan-date')||{}).value||'';
  const chip=d=>{
    const mm=d.mm==null?null:d.mm;
    const wet=mm!=null&&mm>=10, damp=mm!=null&&mm>=2&&mm<10;
    const cls='plan-ro-chip'+(wet?' wet':damp?' damp':'')+(d.date===sel?' on':'');
    const md=d.date.slice(5);
    const probTxt=d.probPct!=null?d.probPct+'% chance of rain · ':'';
    return `<button type="button" class="${cls}" data-date="${d.date}"
      title="${d.date} · ${mm!=null?mm+' mm forecast':'no data'} · ${probTxt}click to set Rainfall and plan date"
      onclick="planPickOutlookDay('${d.date}')">
      <span class="d">${md}</span><span class="mm">${mm!=null?(mm>=1?Math.round(mm):mm>0?'&lt;1':'0'):'—'}</span></button>`;
  };
  box.innerHTML=`<div class="plan-ro-strip">${res.days.map(chip).join('')}</div>`;
}
function planPickOutlookDay(date){
  const el=q('plan-date');
  if(!el)return;
  el.value=date;
  // Fill Rainfall from the outlook chip immediately (Open-Meteo day total).
  const day=((_planRainOutlook&&_planRainOutlook.days)||[]).find(d=>d.date===date);
  if(day&&day.mm!=null){
    _planRainManual=false;
    const rain=q('plan-rain');
    if(rain)rain.value=String(Math.max(0,Math.round(Number(day.mm)||0)));
    if(typeof computePlan==='function')computePlan();
  }
  planDateChange();          // sync date note / Use-mm button / GPS chips
  planRenderRainOutlook();   // refresh selection highlight
}
function planEnsureDate(){
  const el=q('plan-date');
  if(el&&!el.value){ el.value=planTodayISO(); planDateChange(); }
}

// ── Other (non-plan) traffic + weighbridge load ──────────────────────────────
// IWIP / Position trucks are not in the holding plan but cross the SAME
// weighbridges on the way to the dumps and share the road. Prefilled from the
// last measured shift (shift-context otherTrips); the planner can edit it.
// The bridges are modelled as a THROUGHPUT CEILING, not a delay curve: measured
// wait is flat (11.7→12.1 min from 3.6→31 trucks/bridge-hour) while single
// bridges have demonstrated 35–49 trucks/hour peaks. Same doctrine as loaders.
let _planOtherTrips=0,_planOtherManual=false,_planOtherSrc='',_planOtherSrcTrips=0,_planOtherPaths=[],_planOtherWb=[],_planOtherTypical=null;
const PLAN_WB_TRIPS_PER_HOUR=30;   // conservative vs measured 35–49 peaks
function planOtherManualEdit(){
  _planOtherManual=true;
  _planOtherTrips=Math.max(0,parseFloat((q('plan-other-trips')||{}).value)||0);
  computePlan();
}
function planFetchOtherTraffic(){
  // The ticket table (HAULAGE_IWIP_CLEAN) ends before the GPS archive does, so
  // recent days have no other-traffic rows. Seed the search from the LAST DAY
  // THE TICKET DATA HAS (weighbridge-summary.date — the same freshness marker
  // the Capability tab shows), then walk back to the most recent day shift that
  // actually measured other trips.
  fetch('/api/weighbridge-summary')
    .then(r=>r.json())
    .then(ws=>{
      const seed=(ws&&ws.date)||new Date(Date.now()-86400e3).toISOString().slice(0,10);
      const tryDay=(dateS,left)=>{
        if(left<=0)return;
        fetch('/api/simulator/shift-context?date='+encodeURIComponent(dateS)+'&shift=1')
          .then(r=>r.json())
          .then(res=>{
            const trips=res&&res.ok?(Number(res.otherTrips)||0):0;
            if(trips>0){
              _planOtherSrc=res.date||dateS;
              _planOtherSrcTrips=trips;
              _planOtherFeniTrips=Number(res.otherFeniTrips)||0;
              _planOtherFeniTypical=Number(res.otherFeniTypical)||null;
              _planOtherPaths=res.otherPaths||[];   // per-path foreign trucks for road-only prefill
              // TYPICAL other traffic (30-day median per shift + 30-day bridge
              // shares) — the owner asked for an average over many days, not one
              // day's snapshot: single shifts swing 255→894 trips, so the last
              // shift is a bad default. Median beats mean (surge days skew up).
              const typ=res.otherTypical||null;
              _planOtherTypical=typ&&Number(typ.tripsPerShift)>0?typ:null;
              // Bridge split for the stress board: 30-day shares when we have
              // them (stable), else the single measured shift (better than nothing).
              if(_planOtherTypical&&Array.isArray(typ.wbShares)&&typ.wbShares.length){
                const s=typ.wbShares.reduce((a,b)=>a+(b.sharePct||0),0)||1;
                _planOtherWb=typ.wbShares.map(b=>({wb:String(b.wb),share:(b.sharePct||0)/s}));
              }else{
                const _obrs=(res.bridges||[]).map(b=>({wb:String(b.wb),w:(b.trucks||0)*(b.otherPct||0)})).filter(b=>b.w>0);
                const _osum=_obrs.reduce((a,b)=>a+b.w,0);
                _planOtherWb=_osum>0?_obrs.map(b=>({wb:b.wb,share:b.w/_osum})):[];
              }
              if(!_planOtherManual){
                _planOtherTrips=_planOtherTypical?Number(_planOtherTypical.tripsPerShift):trips;
                const el=q('plan-other-trips');
                if(el)el.value=String(Math.round(_planOtherTrips));
              }
              const src=q('plan-other-src');
              if(src)src.textContent=_planOtherTypical
                ?('· 30d median (last shift '+_planOtherSrc.slice(5)+': '+Math.round(trips)+')')
                :('· '+_planOtherSrc.slice(5));
              computePlan();
              return;
            }
            const prev=new Date(dateS+'T00:00:00Z');prev.setUTCDate(prev.getUTCDate()-1);
            tryDay(prev.toISOString().slice(0,10),left-1);
          })
          .catch(()=>{});
      };
      tryDay(seed,10);
    })
    .catch(()=>{});
}
// One-click: add the MEASURED foreign (IWIP/Position) paths as ROAD-ONLY rows
// in the holding plan — congestion counted everywhere, zero WMT (engine drag
// path already exists for foreign:true rows). We only know THEIR history, not
// their plan, so the measured last shift is the honest prefill; edit DT after.
function planAddMeasuredRoadOnly(){
  const paths=_planOtherPaths||[];
  if(!paths.length){alert('No measured road-only paths available (no recent IWIP/Position tickets).');return;}
  let added=0;
  paths.forEach(pth=>{
    const sKey=(pth.origin||'').trim(),dKey=(pth.dest||'').trim();
    if(!sKey||!dKey)return;
    const key=sKey+'>'+dKey;
    const id='IWIP|'+key+'|road';
    if(_planDraft[id])return;                     // don't duplicate
    // FOREIGN paths usually have no WBN route history — carry their MEASURED
    // trips/trucks from the tickets so the row renders honest numbers.
    _planDraft[id]={key,dt:Math.max(1,Math.round(pth.trucks||1)),contractor:'IWIP',
      source:sKey,dest:dKey,foreign:true,
      measTrips:Math.max(0,Math.round(pth.trips||0)),
      measTrucks:Math.max(1,Math.round(pth.trucks||1))};
    added++;
  });
  if(added){computePlan();}
  const st=q('plan-save-status');
  if(st)st.textContent=added
    ?('Added '+added+' road-only path(s) from measured '+(_planOtherSrc||'last')+' shift — edit DT to test scenarios.')
    :'Measured road-only paths have no route history here (or already added).';
}
function planRenderWbLoad(totTrips,wb,hours,avgTf){
  // The old AGGREGATE bar (all trips ÷ bridge-count ceiling) is gone: it pooled
  // demand over a bridge COUNT and told the planner to "open N bridges", which
  // contradicted the per-bridge assignments the planner actually makes. The
  // Bridge stress board (plan_weighbridges.js) is now the ONE capacity model —
  // per bridge, per the planner's own choices, other traffic included.
  // This row keeps only what is NOT per-bridge: the corridor-drag readout for
  // other traffic and the road-only quick-add button.
  const box=q('plan-wb-load');if(!box)return;
  const other=_planOtherTrips||0;
  const dragProbe=planOtherTrafficDelta('X>FENI KM0');
  const dragTxt=dragProbe<0
    ?`corridor drag <b>${fmtExact(dragProbe,2)}</b> trips/DT on FENI routes (IWIP above typical)`
    :'';
  const addBtn=(_planOtherPaths&&_planOtherPaths.length)
    ?` <button type="button" class="ms-btn" style="font-size:10px;padding:1px 7px" onclick="planAddMeasuredRoadOnly()" title="Add the measured IWIP/Position paths (last ticket shift) as ROAD-ONLY rows: congestion counted, no WMT">+ add measured road-only paths</button>`
    :'';
  box.innerHTML=(other>0||addBtn)
    ?`<div class="wbl-note">${other>0?`Other traffic: <b>${fmtExact(Math.round(other))}</b> trips${_planOtherTypical?' (30-day median — single shifts ranged 255–894)':''} on their usual bridges — counted in Bridge stress below`:''}${dragTxt?' · '+dragTxt:''}${addBtn}</div>`
    :'';
}
let _planPathKey='';   // last source>dest — only seed DT when this changes
let _planUserEditedFleet=false;  // once user types DT/WMT, never auto-overwrite

function planMarkFleetEdit(){ _planUserEditedFleet=true; planPreview(); }

function renderPlanBuilder(){
  const src=q('plan-src');if(!src)return;
  planEnsureDate();
  if(!_planRainOutlook)planFetchRainOutlook();   // 16-day site forecast strip
  if(!_planOtherSrc&&!_planOtherManual)planFetchOtherTraffic(); // non-plan trucks
  const cs=q('plan-contractor');
  const keepC=cs?cs.value:'';
  const keepS=src.value;
  const keepD=(q('plan-dst')||{}).value;
  if(cs){
    cs.innerHTML=planContractors().map(c=>`<option value="${escH(c.name)}"${c.name===keepC?' selected':''}>${escH(c.name)}${Number.isFinite(c.tripsPerDT)?'':' (no history)'}</option>`).join('');
  }
  const keys=_planValidKeys();
  if(!keys.length){src.innerHTML='<option>loading…</option>';return;}
  const sources=[...new Set(keys.map(k=>k.split('>')[0].trim()))].sort();
  const srcVal=sources.includes(keepS)?keepS:sources[0];
  src.innerHTML=sources.map(s=>`<option${s===srcVal?' selected':''}>${escH(s)}</option>`).join('');
  // Rebuild dest list without forcing a DT reset unless the path key actually changes.
  planSrcChange(keepD, /*fromBuilder*/true);
  computePlan();
}
function planContractorChange(){ planUpdatePathMeta(); planPreview(); computePlan(); }
function planSrcChange(preferredDest, fromBuilder){
  const s=(q('plan-src')||{}).value,dst=q('plan-dst');if(!dst)return;
  const dests=[...new Set(_planValidKeys().filter(k=>k.split('>')[0].trim()===s).map(k=>k.split('>')[1].trim()))].sort();
  const want=preferredDest||dst.value;
  const dVal=dests.includes(want)?want:dests[0];
  dst.innerHTML=dests.map(d=>`<option${d===dVal?' selected':''}>${escH(d)}</option>`).join('');
  planDstChange(!!fromBuilder);
}
function planDstChange(_fromBuilder){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value;
  const key=s+'>'+d, m=_pathResp&&_pathResp[key], dt=q('plan-dt');
  const pathChanged=key!==_planPathKey;
  if(pathChanged){
    const prevKey=_planPathKey;
    _planPathKey=key;
    // Seed typical DT only when the haul path actually changes AND the user
    // hasn't typed a fleet yet. Never overwrite on tab/capability refresh
    // (same path) or after the user has edited DT/WMT.
    const realSwitch=!!prevKey&&prevKey!==key;
    if(realSwitch)_planUserEditedFleet=false;
    if(dt&&m&&_planMode==='dt'&&!_planUserEditedFleet){
      dt.value=Math.round(m.avgDt||50);
    }
  }
  planUpdatePathMeta();
  planPreview();
}
function planUpdatePathMeta(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,m=_pathResp&&_pathResp[s+'>'+d],hint=q('plan-hint');
  const c=planContractor(),f=planContractorFactor(c);
  if(!hint)return;
  if(!m){ hint.innerHTML=''; return; }
  const chips=[];
  chips.push(`<span class="plan-hint-chip" title="Main-cluster trips/DT per day (≈ half per 12h shift)"><b>${fmt(m.avgTr,2)}</b><span class="u">trips/DT · day</span></span>`);
  chips.push(`<span class="plan-hint-chip" title="Approx. trips/DT on one 12h shift"><b>${fmt(m.avgTr/2,2)}</b><span class="u">/ shift</span></span>`);
  if(Number.isFinite(m.trP25)&&Number.isFinite(m.trP75)){
    chips.push(`<span class="plan-hint-chip" title="History band for trips/DT"><b>${fmt(m.trP25,2)}–${fmt(m.trP75,2)}</b><span class="u">P25–P75</span></span>`);
  }
  chips.push(`<span class="plan-hint-chip"><b>${fmt(m.tf,1)}</b><span class="u">t/trip</span></span>`);
  chips.push(`<span class="plan-hint-chip"><b>~${fmt(m.avgDt)}</b><span class="u">DT typical</span></span>`);
  if(c){
    let cTxt=escH(c.name);
    if(Number.isFinite(c.tf))cTxt+=` ${fmt(c.tf,1)} t`;
    if(f!==1)cTxt+=` · ${fmt(f,2)}×`;
    chips.push(`<span class="plan-hint-chip"><b>${cTxt}</b><span class="u">contractor</span></span>`);
  }
  hint.innerHTML=`<div class="plan-hint-path">
    <div class="plan-hint-route"><b>${escH(s)} → ${escH(d)}</b><span class="muted">path response · main cluster</span></div>
    <div class="plan-hint-metrics">${chips.join('')}</div>
  </div>`;
}
// Live estimate panel — the visual focus of the page. Renders the breakdown (Trips/DT, total trips,
// payload) above one big exact total: WMT in DT→WMT mode, DTs required in WMT→DT mode. Runs on every
// input change, so a plan never has to be "added" to be seen.
//
// Two-stage render: the local historical-average maths draws IMMEDIATELY (no
// flicker, works offline), then the Phase 2 model at /api/predict answers and
// re-renders the same panel with its numbers. If that call fails or times out,
// what stays on screen is exactly what the page showed before Phase 2 existed.
let _planPredictSeq=0, _planPredictTimer=null;
const PLAN_PREDICT_DEBOUNCE_MS=180;
function _planModelLabel(v){
  if(v.model==='local')return {cls:'pending', text:'Model · historical average (loading…)'};
  if(v.model==='roadonly')return {cls:'ok', text:'Road-only \u00b7 measured congestion, no WMT model'};
  if(v.fallback||v.model==='offline')return {cls:'warn', text:'Model · path formula fallback (offline)'};
  const name=PLAN_MODEL_LABELS[v.model]||v.modelLabel||v.model||'model';
  const cv=Number.isFinite(v.cvR2), shown=cv?v.cvR2:v.r2;
  let text=`Model · ${escH(name)}`;
  if(Number.isFinite(shown))text+=` · R² ${fmtExact(shown,2)}`;
  if(Number.isFinite(v.contractorFactor)&&v.contractorFactor!==1){
    text+=` · factor ${fmtExact(v.contractorFactor,2)}×`;
  }
  const weak=Number.isFinite(v.baselineLift)&&v.baselineLift<0.01;
  return {cls:weak?'warn':'ok', text};
}
function _planRenderEstimate(v){
  const box=q('plan-preview');if(!box)return;
  const lines=[
    ['Trips / DT (this shift)',fmtExact(v.tripsPerDt,2)],
    [v.swapped?'Trucks needed': 'Trucks',fmtExact(v.dt)+' DT'],
    ['Trips',fmtExact(Math.round(v.trips))],
    ['t / trip',v.foreign?'—':fmtExact(v.payload,1)+' t'],   // road-only: not weighed for us
  ];
  if(Number.isFinite(v.contractorFactor)&&v.contractorFactor!==1){
    lines.push(['Contractor factor',fmtExact(v.contractorFactor,2)+'×']);
  }
  if(v.cycle&&Number.isFinite(v.cycle.cycle_time_min)){
    lines.push(['Cycle',fmtExact(v.cycle.cycle_time_min,0)+' min']);
  }
  const mod=_planModelLabel(v);
  box.classList.remove('empty');
  box.classList.toggle('is-loading', v.model==='local');
  box.innerHTML=`<div class="est-head">Estimated shift output <span class="muted" style="font-weight:400;font-size:10.5px">· ONE shift (${escH((q('plan-hours')||{}).value||12)} h), not per day — Capability tab quotes per-day (2 shifts)</span></div>`
    +`<div class="est-body">`
    +`<div class="est-lines">${lines.map(l=>`<div class="est-line"><span>${escH(l[0])}</span><b>${l[1]}</b></div>`).join('')}</div>`
    +`<div class="est-total"><div class="est-total-l">${v.foreign?'WMT':(v.swapped?'Trucks needed':'WMT')}</div>`
    +(v.foreign
       ?`<div class="est-total-v" style="font-size:15px;color:var(--muted,#8b98a5)">Road-only · <span class="u">no WMT</span></div></div>`
       :`<div class="est-total-v">${v.swapped?fmtExact(v.dt):fmtExact(Math.round(v.wmt))} <span class="u">${v.swapped?'DT':'t'}</span></div></div>`)
    +`</div>`
    +`<div class="est-foot">`
    +`<div class="est-note">${escH(v.src)} → ${escH(v.dst)} · ${escH(v.contractor||'—')}`
    +(v.foreign?` · road-only (foreign / IWIP — no WMT for us)`:(v.swapped?` · ${fmtExact(Math.round(v.wmt))} t`:''))+`</div>`
    +`<div class="est-attr"><span class="est-model ${mod.cls}">${mod.text}</span></div>`
    +`</div>`
    +(v.warns&&v.warns.length?`<div class="est-warn">${v.warns.map(escH).join('<br>')}</div>`:'');
}
function planPreview(){
  const box=q('plan-preview');if(!box)return;
  const blank=(msg)=>{box.classList.add('empty');box.classList.remove('is-loading');
    box.innerHTML=`<div class="est-head">Estimated shift output</div><div class="est-body"><div class="est-lines"></div><div class="est-total"><div class="est-total-v">—</div></div></div><div class="est-foot"><div class="est-note">${escH(msg)}</div></div>`;
    planRenderBestHistory({ok:false,error:msg});};
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d,m=_pathResp&&_pathResp[key];
  if(!m)return blank('Select a source and destination to see the estimate.');
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),c=planContractor(),pay=planPayload(key,c),
    hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),
    wbOpen=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8),
    foreign=!!(q('plan-foreign')&&q('plan-foreign').checked);   // road-only / IWIP: trucks run, but no WMT for us
  let dt,trips,wmt,e;
  if(_planMode==='wmt'){
    const target=Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0);
    if(!(target>0))return blank('Enter a target tonnage to size the fleet.');
    dt=planDtForWmt(key,target,rain,c);
    if(!dt)return blank('Could not size a fleet for that target on this path.');
  }else{
    dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
  }
  e=planTripsPerDT(key,dt,rain,c);
  if(!e)return blank('No history for this path yet.');
  trips=dt*e.shift; wmt=trips*pay.tf;
  const swapped=_planMode==='wmt';
  const cFactor=planContractorFactor(c);
  const warns=[];
  if(Number.isFinite(m.dtMax)&&dt>m.dtMax)warns.push(`⚠ ${fmtExact(dt)} DT is beyond the ${fmtExact(m.dtMax)} DT ever observed on this path`);
  if(e.rainDelta<=-.03)warns.push(`☔ rain −${fmtExact(Math.abs(e.rainDelta),2)} Trips/DT`);
  if(e.otherDelta<=-.02)warns.push(`🚚 other (IWIP/Position) traffic above typical −${fmtExact(Math.abs(e.otherDelta),2)} Trips/DT on the shared corridor`);
  if(e.secDelta<=-.02)warns.push(`\u{1F6E3}\uFE0F shared-section load \u2212${fmtExact(Math.abs(e.secDelta),2)} Trips/DT (plan adds ${fmtExact(Math.round(e.secExcess))} DT beyond this path's typical section traffic \u2014 page-1 measured effect)`);
  const base={src:s,dst:d,contractor:c?c.name:'—',hours,swapped,warns,foreign,
    dt,tripsPerDt:e.shift,trips,wmt,payload:pay.tf,payloadSrc:pay.src,model:foreign?'roadonly':'local',
    contractorFactor:cFactor};
  _planRenderEstimate(base);                       // stage 1 — instant, local
  // Road-only / foreign path: its trucks add congestion but no WMT for us, so there is
  // no tonnage to predict and no WMT history to rank. Stop after the local estimate —
  // do NOT call /api/predict (would re-render a WMT) or the best-past-days search.
  if(foreign){planRenderBestHistory({ok:false,error:'Road-only / foreign path — adds congestion, no WMT for us, so there is no tonnage history to compare.'});return;}
  planFetchBestHistory(s,d,dt,c?c.name:null,rain); // side panel: best past days at this fleet
  // stage 2 — trained model (/api/predict). Never writes back into the DT/WMT inputs.
  const seq=++_planPredictSeq;
  clearTimeout(_planPredictTimer);
  _planPredictTimer=setTimeout(()=>{
    // Re-read inputs at fire time so a late response cannot use a stale typed value
    // and so we never push model output into the fleet fields.
    const rainNow=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
    const stillSwapped=_planMode==='wmt';
    let trucksNow=dt, targetNow=0;
    if(stillSwapped){
      targetNow=Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0);
    }else{
      trucksNow=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
    }
    const body={contractor:base.contractor,source:s,destination:d,shift_hours:hours,
      rainfall:rainNow,shift:'day',weighbridges_open:wbOpen,
      mode:stillSwapped?'wmt_to_dt':'dt_to_wmt',
      prefer_rain_aware:true};  // wet days → Random Forest (VPN-trained), not rain-blind average
    if(stillSwapped)body.target_wmt=targetNow; else body.trucks=trucksNow;
    const ctl=('AbortController' in window)?new AbortController():null;
    if(ctl)setTimeout(()=>ctl.abort(),4000);
    fetch('/api/predict',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body),signal:ctl?ctl.signal:undefined})
      .then(r=>r.ok?r.json():Promise.reject(new Error('HTTP '+r.status)))
      .then(res=>{
        if(seq!==_planPredictSeq)return;
        if(!res||!res.ok||!res.prediction)throw new Error('bad payload');
        const p=res.prediction;
        // Estimate panel only — do NOT touch #plan-dt / #plan-wmt.
        const showDt=stillSwapped?p.trucks_needed:trucksNow;
        _planPredictLast=res;
        _planRenderEstimate({...base, swapped:stillSwapped, dt:showDt,
          tripsPerDt:p.trips_per_dt, trips:p.total_trips,
          wmt:p.total_wmt, payload:p.payload_per_trip, payloadSrc:p.payload_source||base.payloadSrc,
          model:res.model_used, modelLabel:PLAN_MODEL_LABELS[res.model_used]||res.model_used,
          r2:res.model_r2, fallback:!!res.fallback,
          trainedAt:res.model_trained_at, baselineR2:res.model_baseline_r2,
          baselineLift:res.model_baseline_lift,
          cvR2:res.model_cv_r2, cvBasis:res.model_cv_basis,
          cvBest:res.model_cv_best, isCvWinner:res.model_is_cv_winner,
          selectedModel:res.model_selected, cycle:res.cycle,
          contractorFactor:cFactor});
      })
      .catch(()=>{
        if(seq!==_planPredictSeq)return;
        _planRenderEstimate({...base, model:'offline', fallback:true, contractorFactor:cFactor});
      });
  },PLAN_PREDICT_DEBOUNCE_MS);
}
const PLAN_MODEL_LABELS={random_forest:'Random Forest',ols:'OLS regression',fallback_ols:'fallback OLS',
  group_mean_baseline:'per-route average',
  'group_mean_baseline+rf_rain':'per-route average × RF rain',
  'group_mean_baseline+rain':'per-route average × rain factor'};
let _planPredictLast=null;
let _planHistTimer=null,_planHistSeq=0,_planHistLastKey='';

function planHistFmt(n,d){
  if(n==null||!Number.isFinite(Number(n)))return '—';
  return Number(n).toLocaleString('en-GB',{maximumFractionDigits:d==null?0:d,minimumFractionDigits:0});
}

function planRenderBestHistory(data, context){
  const list=q('plan-hist-list'),sum=q('plan-hist-summary');
  if(!list)return;
  if(!data||!data.ok){
    list.innerHTML='';
    if(sum)sum.textContent=(data&&data.error)||'No matching history for this haul / fleet yet.';
    return;
  }
  const days=data.analogues||[];
  const ctx=context||{};
  const meta=(data.by_plan&&data.by_plan[0]&&data.by_plan[0].meta)||data.meta||{};
  const wantC=ctx.contractor||meta.contractor||'';
  const onlyC=meta.contractor_only!==false&&!!wantC;
  if(sum){
    sum.innerHTML=days.length
      ?`${escH(ctx.source||'')} → ${escH(ctx.dest||'')} · ${wantC?escH(wantC)+' · ':''}~${planHistFmt(ctx.dt)} DT · top ${days.length}`
        +(wantC&&!onlyC?` <span class="muted">(few ${escH(wantC)} days — mixed haulers)</span>`:'')
      :'No similar days.';
  }
  list.innerHTML=days.map((a,i)=>{
    const remark=escH(a.remark||a.why||'');
    const rain=a.rain_mm, hasRain=rain!=null&&Number.isFinite(Number(rain));
    const isWet=a.wet===true||(hasRain&&Number(rain)>=1);
    const isDry=a.wet===false||(hasRain&&Number(rain)<1);
    let weatherCls='unknown', weatherLabel='rain n/a';
    if(isWet){
      weatherCls='wet';
      weatherLabel=hasRain?`wet · ${planHistFmt(rain,0)} mm`:'wet';
    }else if(isDry){
      weatherCls='dry';
      weatherLabel=hasRain?`dry · ${planHistFmt(rain,0)} mm`:'dry';
    }
    const hauler=(a.contractor||'').trim();
    const matchC=wantC&&hauler&&hauler.toUpperCase()===String(wantC).toUpperCase();
    return `<div class="plan-hist-item ph-${weatherCls}${matchC?' ph-contractor-match':''}">
      <div class="ph-top">
        <span class="ph-date">${escH(a.date||'')}${hauler?` · <span class="ph-contractor${matchC?' match':''}">${escH(hauler)}</span>`:''}${a.season?` · <span class="plan-season-${escH(a.season)}">${escH(a.season)}</span>`:''}</span>
        <span class="ph-right"><span class="ph-weather ph-weather-${weatherCls}">${escH(weatherLabel)}</span><span class="ph-rank">#${i+1}</span></span>
      </div>
      <div class="ph-kpis">
        <div><b>${planHistFmt(a.dt,1)}</b>DT that day</div>
        <div><b>${planHistFmt(a.trips,1)}</b>trips</div>
        <div><b>${planHistFmt(a.trips_per_dt,2)}</b>trips/DT</div>
        <div><b>${planHistFmt(a.wmt)} t</b>WMT</div>
      </div>
      <div class="ph-remark">${remark}</div>
    </div>`;
  }).join('');
}

function planHistShowLoading(ctx){
  const list=q('plan-hist-list'),sum=q('plan-hist-summary');
  const who=ctx&&ctx.contractor?escH(ctx.contractor)+' · ':'';
  const path=ctx&&ctx.source&&ctx.dest?`${escH(ctx.source)} → ${escH(ctx.dest)}`:'this haul';
  if(sum)sum.innerHTML=`<span class="plan-hist-sum-load">Searching ${who}${path}…</span>`;
  if(list){
    list.innerHTML=`<div class="plan-hist-loading" role="status" aria-live="polite">
      <div class="ph-spin" aria-hidden="true"></div>
      <div class="ph-load-text">Finding best past days</div>
      <div class="ph-load-sub">${who?who:''}similar fleet · closest DT</div>
      <div class="plan-hist-skel" aria-hidden="true"><i></i><i></i><i></i></div>
    </div>`;
  }
}

/** Live side panel: best past days at similar DT (highest WMT, then trips). */
function planFetchBestHistory(source,dest,dt,contractor,rain){
  const list=q('plan-hist-list'),sum=q('plan-hist-summary');
  if(!source||!dest||!(dt>0)){
    if(list)list.innerHTML='';
    if(sum)sum.textContent='Pick source, destination and DT to load history…';
    return;
  }
  const key=[source,dest,Math.round(dt),contractor||'',Math.round(rain||0)].join('|');
  if(key===_planHistLastKey&&list&&list.children.length&&!list.querySelector('.plan-hist-loading'))return;
  const seq=++_planHistSeq;
  clearTimeout(_planHistTimer);
  planHistShowLoading({source,dest,dt,contractor});
  _planHistTimer=setTimeout(()=>{
    fetch('/api/plan/analogues',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        plans:[{source,destination:dest,n_trucks:Math.round(dt),contractor:contractor||null}],
        rain_mm:rain||0,k:10,rank:'best_output',nocache:true,
      }),
    }).then(r=>r.json()).then(data=>{
      if(seq!==_planHistSeq)return;
      _planHistLastKey=key;
      planRenderBestHistory(data,{source,dest,dt,contractor});
    }).catch(()=>{
      if(seq!==_planHistSeq)return;
      planRenderBestHistory({ok:false,error:'Could not load history (server offline?).'});
    });
  },280);
}
// A plan row is one contractor on one path, so two contractors can share the same path.
function planAddPath(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d;
  if(!s||!d||!_pathResp[key])return;
  const btn=document.querySelector('.plan-add');
  if(btn){btn.classList.add('is-busy');btn.disabled=true;}
  const c=planContractor(),name=c?c.name:'—',rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  let dt;
  if(_planMode==='wmt'){
    dt=planDtForWmt(key,Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0),rain,c);
    if(!dt){
      const b=q('plan-preview');if(b)b.innerHTML='<span class="er">Could not size a fleet for that target on this path.</span>';
      if(btn){btn.classList.remove('is-busy');btn.disabled=false;}
      return;
    }
  }else dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||50);
  // Road-only / foreign (IWIP) haul: no WMT for us, but its trucks load the
  // shared corridor. Kept as a SEPARATE draft row (|road suffix) so it never
  // merges with a production path on the same route; the engine applies its
  // congestion drag and excludes it from production. See plan_simulator.py.
  const foreign=!!(q('plan-foreign')&&q('plan-foreign').checked);
  _planDraft[name+'|'+key+(foreign?'|road':'')]={key,dt,contractor:name,source:s,dest:d,foreign};
  computePlan();
  // Brief busy flash so “Add to plan” feels acknowledged while tables refresh
  setTimeout(()=>{if(btn){btn.classList.remove('is-busy');btn.disabled=false;}},320);
}
function planRemove(id){delete _planDraft[id];computePlan();}
function planSet(id,v){const r=_planDraft[id];if(r){r.dt=Math.max(0,parseFloat(v)||0);computePlan();}}
function computePlan(){
  const rows=q('plan-rows');if(!rows)return;
  planPreview();
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),wb=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8),
    hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),ids=Object.keys(_planDraft),scope=q('plan-scope'),foot=q('plan-foot');
  if(!ids.length){rows.innerHTML='<tr><td colspan="9" class="muted">No paths yet.</td></tr>';
    if(foot)foot.innerHTML='';const pk=q('plan-kpis');if(pk)pk.innerHTML='';q('plan-warn').innerHTML='';if(scope)scope.textContent='';
    if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
    if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
    return;}
  let totTrips=0,totWmt=0,totDt=0;
  rows.innerHTML=ids.map(id=>{const r=_planDraft[id],m=_pathResp[r.key];
    if(!m&&r.foreign&&Number.isFinite(r.measTrips)){
      // Foreign path without WBN history: measured ticket rate scaled by DT.
      const rate=r.measTrucks?r.measTrips/r.measTrucks:0,ftrips=r.dt*rate;
      const tag=' <span title="Road-only / foreign traffic (measured from tickets): adds congestion, no WMT" style="font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(148,163,184,.18);color:var(--muted,#8b98a5);vertical-align:middle">ROAD-ONLY \u00b7 measured</span>';
      return `<tr style="opacity:.72"><td><b>${escH(r.key.replace('>',' \u2192 '))}</b>${tag}</td><td>${escH(r.contractor)}</td><td class="r"><input type="number" min="0" step="1" value="${Math.round(r.dt)}" onchange="planSet('${escH(id)}',this.value)" style="width:56px;text-align:center"></td><td class="r">${fmtExact(rate,2)}</td><td class="r">${fmtExact(Math.round(ftrips))}</td><td class="r muted">\u2014</td><td class="r muted" title="foreign traffic adds no WMT">\u2014</td><td></td><td><a onclick="planRemove('${escH(id)}')" style="cursor:pointer;color:#f87171" title="remove">\u2715</a></td></tr>`;
    }
    if(!m)return '';
    const c=planContractor(r.contractor),e=planTripsPerDT(r.key,r.dt,rain,c),pay=planPayload(r.key,c);
    if(!e)return '';
    const trips=r.dt*e.shift,wmt=trips*pay.tf;
    // Road-only / foreign lines add congestion but no WMT for us, so they are
    // excluded from the productive totals here; the engine still applies their drag.
    if(r.foreign){
      const tag=' <span title="Road-only / foreign traffic: adds congestion, no WMT" style="font-size:9px;padding:1px 5px;border-radius:8px;background:rgba(148,163,184,.18);color:var(--muted,#8b98a5);vertical-align:middle">ROAD-ONLY</span>';
      return `<tr style="opacity:.72"><td><b>${escH(r.key.replace('>',' → '))}</b>${tag}</td><td>${escH(r.contractor)}</td><td class="r"><input type="number" min="0" step="1" value="${Math.round(r.dt)}" onchange="planSet('${escH(id)}',this.value)" style="width:56px;text-align:center"></td><td class="r">${fmtExact(e.shift,2)}</td><td class="r">${fmtExact(Math.round(trips))}</td><td class="r muted">—</td><td class="r muted" title="foreign traffic adds no WMT">—</td><td></td><td><a onclick="planRemove('${escH(id)}')" style="cursor:pointer;color:#f87171" title="remove">✕</a></td></tr>`;}
    totTrips+=trips;totWmt+=wmt;totDt+=r.dt;
    return `<tr><td><b>${escH(r.key.replace('>',' → '))}</b></td><td>${escH(r.contractor)}</td><td class="r"><input type="number" min="0" step="1" value="${Math.round(r.dt)}" onchange="planSet('${escH(id)}',this.value)" style="width:56px;text-align:center"></td><td class="r">${fmtExact(e.shift,2)}</td><td class="r">${fmtExact(Math.round(trips))}</td><td class="r muted">${fmtExact(pay.tf,1)}</td><td class="r">${fmtExact(Math.round(wmt))} t</td><td></td><td><a onclick="planRemove('${escH(id)}')" style="cursor:pointer;color:#f87171" title="remove">✕</a></td></tr>`;}).join('');
  const avgEff=totDt?totTrips/totDt:0;
  if(foot)foot.innerHTML=`<tr class="plan-total-row"><td><b>TOTAL</b></td><td class="muted">${ids.length}</td><td class="r"><b>${fmtExact(Math.round(totDt))}</b></td><td class="r"><b>${fmtExact(avgEff,2)}</b></td><td class="r"><b>${fmtExact(Math.round(totTrips))}</b></td><td class="r muted">${totTrips?fmtExact(totWmt/totTrips,1):'—'}</td><td class="r"><b>${fmtExact(Math.round(totWmt))} t</b></td><td colspan="2"></td></tr>`;
  const names=[...new Set(ids.map(id=>_planDraft[id].contractor))];
  const otherN=Math.round(_planOtherTrips||0);
  if(scope)scope.textContent=`${ids.length} path${ids.length===1?'':'s'} · ${names.join(', ')} · ${rain>0?fmtExact(rain)+' mm':'dry'} · ${fmtExact(wb)} WB`+(otherN>0?` · +${fmtExact(otherN)} other trips`:'');
  // Weighbridge capacity verdicts are PER BRIDGE now (Bridge stress board in
  // plan_weighbridges.js — planner's own assignments + other traffic). The old
  // pooled trips-vs-bridge-count warning contradicted it, so it is gone.
  const avgTf=totTrips?totWmt/totTrips:0;
  planRenderWbLoad(totTrips,wb,hours,avgTf);
  q('plan-warn').innerHTML='';
  if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
  if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
}



