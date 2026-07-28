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
// Only a MEASURED decline (b<0) is applied; flat/confounded paths stay flat.
function planTripsPerDT(key,dt,rain,contractor){
  const m=_pathResp&&_pathResp[key];if(!m)return null;
  let tr=m.avgTr;
  const slope=(Number.isFinite(m.bAdj)&&m.bAdj<0)?m.bAdj:(m.b<0?m.b:0);
  if(slope<0&&Number.isFinite(m.avgDt))tr+=slope*(dt-m.avgDt);
  let rainDelta=0;
  if(rain>0&&Number.isFinite(m.mWet)&&Number.isFinite(m.mDry)){rainDelta=(m.mWet-m.mDry)*(rain/10);tr+=rainDelta;}
  tr=Math.max(.3*m.avgTr,tr)*planContractorFactor(contractor);
  const sf=planShiftFactor();
  return {daily:tr,shift:tr*sf,rainDelta:rainDelta*sf,slope,m};
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
  const dtBox=q('plan-input-dt'),wmtBox=q('plan-input-wmt'),btn=q('plan-swap-btn');
  if(dtBox)dtBox.style.display=_planMode==='dt'?'':'none';
  if(wmtBox)wmtBox.style.display=_planMode==='wmt'?'':'none';
  if(btn){btn.textContent=_planMode==='dt'?'⇄ DT → WMT':'⇄ WMT → DT';
    btn.title=_planMode==='dt'
      ?'Currently: enter trucks, get WMT. Click to enter a tonnage target instead.'
      :'Currently: enter a tonnage target, get the trucks needed. Click to enter trucks instead.';}
  planPreview();
}
function renderPlanBuilder(){
  const src=q('plan-src');if(!src)return;
  const cs=q('plan-contractor');
  if(cs){const cur=cs.value;
    cs.innerHTML=planContractors().map(c=>`<option value="${escH(c.name)}"${c.name===cur?' selected':''}>${escH(c.name)}${Number.isFinite(c.tripsPerDT)?'':' (no history)'}</option>`).join('');}
  const keys=_planValidKeys();
  if(!keys.length){src.innerHTML='<option>loading…</option>';return;}
  const sources=[...new Set(keys.map(k=>k.split('>')[0].trim()))].sort(),cur=src.value;
  src.innerHTML=sources.map(s=>`<option${s===cur?' selected':''}>${escH(s)}</option>`).join('');
  planSrcChange();computePlan();
}
function planContractorChange(){planDstChange();computePlan();}
function planSrcChange(){
  const s=(q('plan-src')||{}).value,dst=q('plan-dst');if(!dst)return;
  const dests=[...new Set(_planValidKeys().filter(k=>k.split('>')[0].trim()===s).map(k=>k.split('>')[1].trim()))].sort();
  dst.innerHTML=dests.map(d=>`<option>${escH(d)}</option>`).join('');
  planDstChange();
}
function planDstChange(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,m=_pathResp[s+'>'+d],hint=q('plan-hint'),dt=q('plan-dt');
  const c=planContractor(),f=planContractorFactor(c);
  if(hint)hint.innerHTML=m?`<b>${escH(s)} → ${escH(d)}</b>: ${fmt(m.avgTr,2)} avg Trips/DT/day · ${fmt(m.tf,1)} t/trip · typically ~${fmt(m.avgDt)} DT · ${fmt(m.n)} shifts of history`
    +(c?` · <b>${escH(c.name)}</b> ${f===1?'has no separate history — using fleet average':(f>1?fmt(100*(f-1),0)+'% above':fmt(100*(1-f),0)+'% below')+' fleet average'}${Number.isFinite(c.tf)?', '+fmt(c.tf,1)+' t/trip':''}`:''):'';
  if(dt&&m&&_planMode==='dt')dt.value=Math.round(m.avgDt||50);
  planPreview();
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
function _planRenderEstimate(v){
  const box=q('plan-preview');if(!box)return;
  const lines=[
    ['Trips/DT',fmtExact(v.tripsPerDt,2)],
    [v.swapped?'DTs required':'Number of trucks',fmtExact(v.dt)+' DT'],
    ['Total trips',fmtExact(Math.round(v.trips))],
    ['Payload/trip',fmtExact(v.payload,1)+' t'],
  ];
  // Model attribution: what produced this number, and how much to trust it.
  // R² on its own is misleading — a lookup table of per-route averages already
  // scores ~0.53 here — so the lift over that baseline is shown beside it.
  let attr;
  if(v.model==='local'){
    attr=`<span class="est-model pending">Historical average · asking model…</span>`;
  }else if(v.fallback){
    attr=`<span class="est-model warn">⚠ Using fallback formula — train the model for better accuracy</span>`;
  }else{
    const lift=v.baselineLift, hasLift=Number.isFinite(lift), weak=hasLift&&lift<0.01;
    // Prefer the CROSS-VALIDATED R² when Phase 3 has produced one. The
    // single-split figure is measured on one block of held-out shifts and runs
    // optimistic; the walk-forward mean is what actually survived being tested
    // on months the model had never seen.
    const cv=Number.isFinite(v.cvR2), shown=cv?v.cvR2:v.r2;
    attr=`<span class="est-model ${weak?'warn':'ok'}">Predicted by ${escH(v.modelLabel||v.model)} model`
        +`${Number.isFinite(shown)?` · R² = ${fmtExact(shown,2)}`:''}</span>`;
    const bits=[];
    if(v.trainedAt)bits.push(`Trained ${escH(String(v.trainedAt).slice(0,10))}`);
    if(cv)bits.push(escH(v.cvBasis||'cross-validated'));
    if(hasLift)bits.push(`Lift over baseline: ${lift>=0?'+':''}${fmtExact(lift*100,1)}%`
        +(Number.isFinite(v.baselineR2)?` (lookup R² ${fmtExact(v.baselineR2,2)})`:''));
    if(bits.length)attr+=`<span class="est-model-sub">${bits.join(' · ')}</span>`;
    if(weak)attr+=`<span class="est-model-sub warn">⚠ Model is barely better than historical averages — treat as a lookup.</span>`;
    // The served model is not always the one that validated best. Saying so is
    // the difference between reporting a score and implying an endorsement.
    if(v.isCvWinner===false&&Number.isFinite(v.cvBest)){
      attr+=`<span class="est-model-sub warn">⚠ A simpler ${escH(PLAN_MODEL_LABELS[v.selectedModel]||v.selectedModel||'model')} `
           +`validates better (R² ${fmtExact(v.cvBest,2)}) under walk-forward testing.</span>`;
    }
  }
  // Phase 3.5 cycle time. Shown as a separate line, not folded into the
  // headline, because it comes from a different model on different data and
  // carries a different accuracy. Hidden entirely when no cycle model has
  // answered, rather than rendering a dash that looks like a real zero.
  let cyc='';
  if(v.cycle&&Number.isFinite(v.cycle.cycle_time_min)){
    const c=v.cycle, mae=Number.isFinite(c.cv_mae_min)?fmtExact(c.cv_mae_min,0):null;
    // Name the branch that answered. A route the model never saw is served by
    // a historical average, and claiming the model's accuracy for it would be
    // a lie the user cannot detect.
    const modelled=c.basis&&c.basis.indexOf('ols')===0;
    cyc=`<div class="est-rule"></div>`
      +`<div class="est-line"><span>Cycle time</span><b>${fmtExact(c.cycle_time_min,0)} min</b></div>`
      +`<span class="est-model-sub">`
      +(modelled?`Cycle model`:`Per-route average (this route is new to the model)`)
      +(mae?` · typically within ±${mae} min`:'')
      +`</span>`;
  }
  box.classList.remove('empty');
  box.innerHTML=`<div class="est-head">Estimated shift output</div>`
    +`<div class="est-lines">${lines.map(l=>`<div class="est-line"><span>${escH(l[0])}</span><b>${l[1]}</b></div>`).join('')}</div>`
    +`<div class="est-rule"></div>`
    +`<div class="est-total"><div class="est-total-l">${v.swapped?'DTs required':'Total WMT'}</div>`
    +`<div class="est-total-v">${v.swapped?fmtExact(v.dt):fmtExact(Math.round(v.wmt))} <span class="u">${v.swapped?'trucks':'t'}</span></div></div>`
    +`<div class="est-note">${escH(v.src)} → ${escH(v.dst)} · ${escH(v.contractor||'—')} · ${fmtExact(v.hours)}h shift · ${escH(v.payloadSrc)} payload`
    +(v.swapped?` · delivers ${fmtExact(Math.round(v.wmt))} t`:'')+`</div>`
    +`<div class="est-attr">${attr}</div>`
    +cyc
    +(v.warns&&v.warns.length?`<div class="est-warn">${v.warns.map(escH).join('<br>')}</div>`:'');
}
function planPreview(){
  const box=q('plan-preview');if(!box)return;
  const blank=(msg)=>{box.classList.add('empty');
    box.innerHTML=`<div class="est-head">Estimated shift output</div><div class="est-total"><div class="est-total-v">—</div></div><div class="est-note">${escH(msg)}</div>`;};
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d,m=_pathResp&&_pathResp[key];
  if(!m)return blank('Select a source and destination to see the estimate.');
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),c=planContractor(),pay=planPayload(key,c),
    hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),
    wbOpen=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8);
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
  const warns=[];
  if(Number.isFinite(m.dtMax)&&dt>m.dtMax)warns.push(`⚠ ${fmtExact(dt)} DT is beyond the ${fmtExact(m.dtMax)} DT ever observed on this path`);
  if(e.rainDelta<=-.03)warns.push(`☔ rain costs ${fmtExact(e.rainDelta,2)} Trips/DT at ${fmtExact(rain)} mm`);
  const base={src:s,dst:d,contractor:c?c.name:'—',hours,swapped,warns,
    dt,tripsPerDt:e.shift,trips,wmt,payload:pay.tf,payloadSrc:pay.src,model:'local'};
  _planRenderEstimate(base);                       // stage 1 — instant, local
  // stage 2 — the server model, debounced so typing doesn't spam the endpoint
  const seq=++_planPredictSeq;
  clearTimeout(_planPredictTimer);
  _planPredictTimer=setTimeout(()=>{
    const body={contractor:base.contractor,source:s,destination:d,shift_hours:hours,
      rainfall:rain,shift:'day',weighbridges_open:wbOpen,
      mode:swapped?'wmt_to_dt':'dt_to_wmt'};
    if(swapped)body.target_wmt=Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0);
    else body.trucks=dt;
    const ctl=('AbortController' in window)?new AbortController():null;
    if(ctl)setTimeout(()=>ctl.abort(),4000);       // never hang the panel
    fetch('/api/predict',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body),signal:ctl?ctl.signal:undefined})
      .then(r=>r.ok?r.json():Promise.reject(new Error('HTTP '+r.status)))
      .then(res=>{
        if(seq!==_planPredictSeq)return;           // a newer edit already won
        if(!res||!res.ok||!res.prediction)throw new Error('bad payload');
        const p=res.prediction, ndt=swapped?p.trucks_needed:dt;
        _planPredictLast=res;
        _planRenderEstimate({...base, dt:ndt, tripsPerDt:p.trips_per_dt, trips:p.total_trips,
          wmt:p.total_wmt, payload:p.payload_per_trip, payloadSrc:p.payload_source||base.payloadSrc,
          model:res.model_used, modelLabel:PLAN_MODEL_LABELS[res.model_used]||res.model_used,
          r2:res.model_r2, fallback:!!res.fallback,
          trainedAt:res.model_trained_at, baselineR2:res.model_baseline_r2,
          baselineLift:res.model_baseline_lift,
          cvR2:res.model_cv_r2, cvBasis:res.model_cv_basis,
          cvBest:res.model_cv_best, isCvWinner:res.model_is_cv_winner,
          selectedModel:res.model_selected, cycle:res.cycle});
      })
      .catch(()=>{                                  // keep the local estimate visible
        if(seq!==_planPredictSeq)return;
        _planRenderEstimate({...base, model:'offline', fallback:true});
      });
  },PLAN_PREDICT_DEBOUNCE_MS);
}
const PLAN_MODEL_LABELS={random_forest:'Random Forest',ols:'OLS regression',fallback_ols:'fallback OLS',
  group_mean_baseline:'per-route average'};
let _planPredictLast=null;
// A plan row is one contractor on one path, so two contractors can share the same path.
function planAddPath(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d;
  if(!s||!d||!_pathResp[key])return;
  const c=planContractor(),name=c?c.name:'—',rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  let dt;
  if(_planMode==='wmt'){
    dt=planDtForWmt(key,Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0),rain,c);
    if(!dt){const b=q('plan-preview');if(b)b.innerHTML='<span class="er">Could not size a fleet for that target on this path.</span>';return;}
  }else dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||50);
  _planDraft[name+'|'+key]={key,dt,contractor:name};
  computePlan();
}
function planRemove(id){delete _planDraft[id];computePlan();}
function planSet(id,v){const r=_planDraft[id];if(r){r.dt=Math.max(0,parseFloat(v)||0);computePlan();}}
function computePlan(){
  const rows=q('plan-rows');if(!rows)return;
  planPreview();
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),wb=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8),
    hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),ids=Object.keys(_planDraft),scope=q('plan-scope'),foot=q('plan-foot');
  if(!ids.length){rows.innerHTML='<tr><td colspan="9" class="muted">Add a path above to start… your live estimate is shown in step 1.</td></tr>';
    if(foot)foot.innerHTML='';q('plan-kpis').innerHTML='';q('plan-warn').innerHTML='';if(scope)scope.textContent='';return;}
  let totTrips=0,totWmt=0,totDt=0;
  rows.innerHTML=ids.map(id=>{const r=_planDraft[id],m=_pathResp[r.key];if(!m)return '';
    const c=planContractor(r.contractor),e=planTripsPerDT(r.key,r.dt,rain,c),pay=planPayload(r.key,c);
    if(!e)return '';
    const trips=r.dt*e.shift,wmt=trips*pay.tf;totTrips+=trips;totWmt+=wmt;totDt+=r.dt;
    const notes=[];
    if(e.rainDelta<=-.03)notes.push('☔ '+fmtExact(e.rainDelta,2));
    if(Number.isFinite(m.dtMax)&&r.dt>m.dtMax)notes.push('⚠ beyond '+fmtExact(m.dtMax)+' DT');
    if(e.slope<0)notes.push('efficiency declines with fleet');
    return `<tr><td><b>${escH(r.key.replace('>',' → '))}</b></td><td>${escH(r.contractor)}</td><td class="r"><input type="number" min="0" step="1" value="${Math.round(r.dt)}" onchange="planSet('${escH(id)}',this.value)" style="width:56px;text-align:center"></td><td class="r">${fmtExact(e.shift,2)}</td><td class="r">${fmtExact(Math.round(trips))}</td><td class="r muted">${fmtExact(pay.tf,1)}</td><td class="r">${fmtExact(Math.round(wmt))} t</td><td class="muted" style="font-size:10px">${notes.join(' · ')}</td><td><a onclick="planRemove('${escH(id)}')" style="cursor:pointer;color:#f87171" title="remove">✕</a></td></tr>`;}).join('');
  const avgEff=totDt?totTrips/totDt:0;
  // Explicit totals row — the sum of every added path, in exact numbers.
  if(foot)foot.innerHTML=`<tr class="plan-total-row"><td><b>TOTAL</b></td><td class="muted">${ids.length} path${ids.length===1?'':'s'}</td><td class="r"><b>${fmtExact(Math.round(totDt))} DT</b></td><td class="r"><b>${fmtExact(avgEff,2)}</b></td><td class="r"><b>${fmtExact(Math.round(totTrips))}</b></td><td class="r muted">${totTrips?fmtExact(totWmt/totTrips,1):'—'}</td><td class="r"><b>${fmtExact(Math.round(totWmt))} t</b></td><td colspan="2" class="muted" style="font-size:10px">per ${fmtExact(hours)}h shift</td></tr>`;
  q('plan-kpis').innerHTML=[['Est. WMT / shift',fmtExact(Math.round(totWmt))+' t'],['Total trips',fmtExact(Math.round(totTrips))],['Fleet',fmtExact(Math.round(totDt))+' DT'],['Avg Trips/DT',fmtExact(avgEff,2)]].map(x=>`<div class="effkpi"><div class="v">${x[1]}</div><div class="l">${x[0]}</div></div>`).join('');
  const names=[...new Set(ids.map(id=>_planDraft[id].contractor))];
  if(scope)scope.textContent=`${ids.length} path${ids.length===1?'':'s'} · ${names.join(', ')} · ${fmtExact(hours)}h shift · ${rain>0?fmtExact(rain)+' mm rain':'dry'} · ${fmtExact(wb)} weighbridges open`;
  const wbCap=wb*30*hours;
  q('plan-warn').innerHTML=totTrips>wbCap?`<span class="er">⚠ Weighbridge bottleneck: ${fmtExact(Math.round(totTrips))} trips exceed ~${fmtExact(Math.round(wbCap))} weigh capacity (${fmtExact(wb)} bridges × ~30/hr × ${fmtExact(hours)}h). Add bridges or trim fleet.</span>`:`<span class="muted">Weighbridge capacity OK (~${fmtExact(Math.round(wbCap))} trips headroom at ${fmtExact(wb)} bridges). Trips/DT is per <b>${fmtExact(hours)}h shift</b>, from each path's 20-month average adjusted for contractor, fleet size${rain>0?' and rainfall':''}. First-level estimate — not a committed plan.</span>`;
}
