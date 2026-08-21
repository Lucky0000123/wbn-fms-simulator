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
/** Plan totals horizon: one 12 h shift, or one day (2 shifts). Engine stays per-shift. */
let _planHorizon='day'; // 'shift' | 'day' — Day is the planning default
function planHorizonFactor(){return _planHorizon==='day'?2:1;}
function planHorizonLabel(){return _planHorizon==='day'?'day':'shift';}
function planHorizonHint(){
  return _planHorizon==='day'?'ONE day (2 × 12 h shifts)':'ONE shift (12 h)';
}
function planWmtTargetShift(){
  const raw=Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0);
  const hz=planHorizonFactor();
  return hz>0?raw/hz:raw;
}
function planSetHorizon(mode){
  _planHorizon=mode==='day'?'day':'shift';
  document.querySelectorAll('.plan-horizon-seg').forEach(b=>{
    b.classList.toggle('on',(b.getAttribute('data-h')||'')===_planHorizon);
  });
  const lab=planHorizonLabel();
  const readout=q('plan-test-prod-label');
  if(readout)readout.textContent=_planHorizon==='day'?'Day readout':'Shift readout';
  const dHead=q('ps-total-head');
  if(dHead)dHead.textContent=_planHorizon==='day'?'Day total':'Shift total';
  const pLab=q('ps-kpi-planned-lab');
  if(pLab)pLab.textContent='Planned t / '+lab;
  const aLab=q('ps-kpi-achv-lab');
  if(aLab)aLab.textContent='Achievable t / '+lab;
  if(typeof computePlan==='function')computePlan();
  if(typeof _planLastSim!=='undefined'&&_planLastSim){
    if(typeof planRenderEstimateColumn==='function'){
      try{planRenderEstimateColumn(_planLastSim,typeof planPredictTotals==='function'?planPredictTotals():null);}catch(_){}
    }
    if(typeof psRender==='function'){
      try{psRender(_planLastSim);}catch(_){}
    }
  }
  if(typeof planSensGran==='function')planSensGran(_planHorizon);
  if(typeof updateFlowSimulator==='function'&&typeof _flowSim!=='undefined'&&_flowSim){
    try{updateFlowSimulator();}catch(_){}
  }
}

// ── Predicted production hero (sticky bar + under Your plan) ────────────────
// One number owns the page. Path-model WMT is live; Achievable appears after
// Check capacity (simulate / loader ceiling). Never average the two.
let _planHeroLast={wmt:null,trips:null,dt:0,achv:null,status:''};
let _planHeroCalcTimer=null;
function planHeroUnit(){return 't / '+planHorizonLabel();}
function planHeroAchvLive(){
  const sim=typeof _planLastSim!=='undefined'&&_planLastSim&&_planLastSim.summary;
  if(!sim||sim.achievable_production_t==null)return null;
  const dtNow=Object.keys(_planDraft||{}).reduce((a,id)=>a+((_planDraft[id]&&_planDraft[id].dt)||0),0);
  if(Math.round(dtNow)!==Math.round(sim.total_trucks||0))return null;
  return sim.achievable_production_t*planHorizonFactor();
}
function planPaintHero(opts){
  opts=opts||{};
  const hero=q('plan-sec-predict');
  const wmtEl=q('plan-hero-wmt'),nav=q('plan-nav-wmt'),navU=q('plan-nav-wmt-u');
  const u=q('plan-hero-wmt-u'),hzEl=q('plan-hero-horizon');
  const st=q('plan-hero-status'),tr=q('plan-hero-trips');
  const achvWrap=q('plan-hero-achv-wrap'),achvEl=q('plan-hero-achv');
  const unit=planHeroUnit(),lab=planHorizonLabel();
  if(hzEl)hzEl.textContent='· per '+lab;
  if(u)u.textContent=unit;
  if(navU)navU.textContent=unit;
  if(opts.calculating){
    if(hero)hero.classList.add('is-calculating');
    if(st)st.textContent='Calculating…';
    return;
  }
  if(hero)hero.classList.remove('is-calculating');
  const wmt=opts.wmt,trips=opts.trips,dt=opts.dt;
  const status=opts.status||'';
  const achv=('achv' in opts)?opts.achv:planHeroAchvLive();
  _planHeroLast={wmt,trips,dt,achv,status};
  const wmtTxt=(wmt==null||!(Number(wmt)>=0))?'—':fmtExact(Math.round(wmt));
  if(wmtEl){
    wmtEl.textContent=wmtTxt;
    wmtEl.classList.remove('est-pulse-run');
    void wmtEl.offsetWidth;
    wmtEl.classList.add('est-pulse-run');
  }
  if(nav)nav.textContent=wmtTxt;
  const bits=[];
  if(trips!=null&&Number.isFinite(trips))bits.push(fmtExact(Math.round(trips))+' trips');
  if(dt)bits.push(fmtExact(Math.round(dt))+' DT');
  if(tr)tr.textContent=bits.join(' · ');
  if(st)st.textContent=status||(wmt==null?'Add a path to predict':'');
  if(achvWrap&&achvEl){
    if(achv!=null&&Number.isFinite(achv)){
      achvWrap.hidden=false;
      achvEl.textContent=fmtExact(Math.round(achv));
    }else{
      achvWrap.hidden=true;
    }
  }
}
function planLimitsMaybeOpen(bite){
  const det=q('plan-limits-details');
  if(det&&bite)det.open=true;
}
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
function _planSectionDtNow(key,dt,selfId){
  const span=_planSpan(key);
  if(!span)return null;
  let tot=dt;
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||!(r.dt>0))return;
    if(selfId&&id===selfId)return;
    if(r.key===key){tot+=r.dt;return;}
    const s2=_planSpan(r.key);
    if(!s2)return;
    if(Math.min(span[1],s2[1])-Math.max(span[0],s2[0])>0)tot+=r.dt;
  });
  return tot;
}
function planSectionDrag(key,dt,selfId){
  const fx=_planSecFxGet();
  const f=fx&&fx[key];
  if(!f||!(f.per50<0)||!Number.isFinite(f.meanSection))return {delta:0,excess:0};
  // Only apply a MEASURED decline (page 1's own signal taxonomy).
  if(!/^(Clear|Likely)/.test(f.signal||''))return {delta:0,excess:0};
  const now=_planSectionDtNow(key,dt,selfId);
  if(now==null)return {delta:0,excess:0};
  const excess=now-f.meanSection;
  if(excess<=0)return {delta:0,excess:0};   // below typical section load: no credit, no drag
  return {delta:(f.per50/50)*excess,excess};
}
// Fleet envelope for a path: FULL-history max (dtMaxAll ignores the peak-window
// date filter; dtMax is only the max inside the current filter window). The
// owner's 2026-08-12 audit: plan said "67 DT ever observed" while history held
// 158-DT days — 67 was the filtered max. Always guard against the full data.
function planDtEnvelope(m){
  if(!m)return null;
  const cands=[m.dtMaxAll,m.dtMaxDayAll,m.dtMax].filter(Number.isFinite);
  return cands.length?Math.round(Math.max.apply(null,cands)):null;
}
function planNLoaders(r){
  const n=parseInt(r&&r.loaders,10);
  return (Number.isFinite(n)&&n>=1)?Math.round(n):2;
}
function planBuilderLoaders(){
  const n=parseInt((q('plan-loaders')||{}).value,10);
  return (Number.isFinite(n)&&n>=1)?Math.round(n):2;
}
function planTripOpts(id, extra){
  const r=(typeof _planDraft!=='undefined'&&id!=null)?_planDraft[id]:null;
  const o={nLoaders:r?planNLoaders(r):planBuilderLoaders()};
  if(id!=null&&id!=='')o.selfId=id;
  if(extra)for(const k in extra)o[k]=extra[k];
  return o;
}
function planEnsureDraftLoaders(){
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(r)r.loaders=planNLoaders(r);
  });
}
function planLoaderCapScale(m, nLoaders){
  const n=(Number.isFinite(nLoaders)&&nLoaders>=1)?nLoaders:2;
  const hist=Number.isFinite(m&&m.historicalLoaders)&&m.historicalLoaders>0?m.historicalLoaders
    :(Number.isFinite(m&&m.nLoaders)&&m.nLoaders>0?m.nLoaders:2);
  // The demonstrated day cap was OBSERVED at the historical loader count; a
  // linear n/hist rescale is only credible near it. Unbounded, proportional
  // loaders (rules §10.9: 17+ on big fleets, hist often 2) multiplied the cap
  // 8-27x and reported 37 trips/DT on BLB>POS 14 whose owner-validated range
  // is 6-7 (2026-08-21). Beyond the clamp the hybrid curve owns the answer.
  return Math.min(2, Math.max(0.5, n/Math.max(1,hist)));
}
function planCongestionHint(e){
  if(!e)return {congestionStatus:'',bottleneck:''};
  if(e.congestionStatus)return {congestionStatus:e.congestionStatus,bottleneck:e.bottleneck||''};
  const sat=Number.isFinite(e.satFactor)?e.satFactor:1;
  if(sat<0.5)return {congestionStatus:'overloaded',bottleneck:'road'};
  if(sat<0.85)return {congestionStatus:'saturated',bottleneck:'loader'};
  return {congestionStatus:'free',bottleneck:'ok'};
}
function planLoaderEdit(id, val){
  if(!_planDraft[id])return;
  _planDraft[id].loaders=Math.max(1,parseInt(val,10)||2);
  computePlan();
}
function planCongCell(e){
  if(!e)return '';
  const h=planCongestionHint(e);
  if(!h.congestionStatus)return '';
  const label=h.bottleneck==='road'?'road':h.bottleneck==='loader'?'loader':'ok';
  const bits=['Ceiling '+(Number.isFinite(e.satFactor)?Math.round(e.satFactor*100)+'%':'—')];
  if(e.cycleTimeMin!=null)bits.push('Cycle: '+e.cycleTimeMin+' min');
  if(e.bprMin!=null)bits.push('Road: '+e.bprMin+' min');
  if(e.queueMin!=null)bits.push('Queue: '+e.queueMin+' min');
  if(e.loadMin!=null)bits.push('Load: '+e.loadMin+' min');
  if(h.bottleneck)bits.push('Bottleneck: '+h.bottleneck);
  return `<span class="plan-cong-badge ${h.congestionStatus}" title="${escH(bits.join(' · '))}">${escH(label)}</span>`;
}
// ── HYBRID congestion model wiring (owner, 2026-08-20) ──────────────────────
// The Allocate-DT engine sizes fleets through planTripsPerDT, which is
// synchronous and called in tight loops. The hybrid physics model lives on
// the backend (/api/congestion_curve). Bridge: fetch the whole saturation
// curve once per (route, loaders, rain bucket), cache it, interpolate
// synchronously. Until the curve arrives the legacy divide model answers,
// and the response is tagged modelVersion:'legacy_divide' vs 'hybrid'.
const _planHybridCurves={};      // "key|loaders|rainB" -> {curve:[...], knee}
const _planHybridPending={};
const _planHybridFailedAt={};    // ck -> ms; failures RETRY, they are not verdicts
function planHybridRainBucket(rain){return rain>=10?'wet':(rain>=1?'damp':'dry');}
function planHybridCurveFor(key,nLoaders,rain){
  const bucket=planHybridRainBucket(rain);
  const ck=key+'|'+nLoaders+'|'+bucket;
  const hit=_planHybridCurves[ck];
  if(hit)return hit;
  // A failed fetch used to cache null FOREVER, so one server blip mid-
  // session silently repriced the route on the legacy divide until a full
  // page reload (owner, 2026-08-21: "TF>HUAFEI still using the old
  // calculations"). Failures now retry after 30 s, and while the exact
  // (loaders) pair loads we serve the NEAREST cached loader count for the
  // same route+rain — loaders mostly move the queue term, so that is far
  // closer to the truth than the divide-at-ceiling fallback.
  const failedRecently=hit===null&&Date.now()-(_planHybridFailedAt[ck]||0)<30000;
  if(!failedRecently&&!_planHybridPending[ck]){
    _planHybridPending[ck]=true;
    const rainMm=rain>=10?12:(rain>=1?3:0);
    fetch('/api/congestion_curve?route='+encodeURIComponent(key)
          +'&n_loaders='+nLoaders+'&max_trucks=1000&rain_mm='+rainMm)
      .then(r=>r.ok?r.json():null)
      .then(d=>{
        const ok=!!(d&&d.ok&&d.curve&&d.curve.length);
        _planHybridCurves[ck]=ok?d:null;
        if(!ok)_planHybridFailedAt[ck]=Date.now();
        _planHybridPending[ck]=false;
        if(typeof computePlan==='function')computePlan();
      })
      .catch(()=>{
        _planHybridCurves[ck]=null;
        _planHybridFailedAt[ck]=Date.now();
        _planHybridPending[ck]=false;
      });
  }
  let best=null,bestD=Infinity;
  for(const k in _planHybridCurves){
    const c=_planHybridCurves[k];
    if(!c)continue;
    const p=k.split('|');
    if(p[0]!==key||p[2]!==bucket)continue;
    const dL=Math.abs((parseInt(p[1],10)||0)-nLoaders);
    if(dL<bestD){bestD=dL;best=c;}
  }
  if(best)return best;
  return undefined;                              // nothing cached yet
}
function planHybridTripsAt(curveData,nTrucks){
  const c=curveData.curve;
  if(!c||!c.length)return null;
  if(nTrucks<=c[0].n_trucks)return c[0];
  for(let i=1;i<c.length;i++){
    if(c[i].n_trucks>=nTrucks){
      const a=c[i-1],b=c[i],f=(nTrucks-a.n_trucks)/Math.max(1,b.n_trucks-a.n_trucks);
      const mix=(ka,kb)=>ka+(kb-ka)*f;
      return {trips_per_dt:mix(a.trips_per_dt,b.trips_per_dt),
              cycle_time_min:mix(a.cycle_time_min,b.cycle_time_min),
              rho:mix(a.rho,b.rho),bottleneck:b.bottleneck,
              p10:mix(a.p10,b.p10),p90:mix(a.p90,b.p90)};
    }
  }
  return c[c.length-1];
}
function planTripsPerDT(key,dt,rain,contractor,opts){
  const m=_pathResp&&_pathResp[key];if(!m)return null;
  // ── Fleet-size response, DAY-LEVEL model (owner 2026-08-12 rebuild) ────────
  // Basis analysis (241 days, TF→FENI KM0, full 20-month history):
  //   • Day-level trips/DT is FLAT with fleet size: 2.0/day at 0-20 DT,
  //     2.2-2.3/day from 40 DT out to 180 DT (largest day ever: 180 DT →
  //     410 trips). The old row-level slope (−0.005/DT under the peak-window
  //     filter) was a contractor-mix artifact, not road physics.
  //   • What DOES bind is the DEMONSTRATED DAY THROUGHPUT: no day ever
  //     produced more than dayTripsCap trips (410 here). So the honest model
  //     is: trips = rate·DT, saturating smoothly at the proven ceiling —
  //     trips/DT never crashes to a floor, it declines hyperbolically as
  //     cap/DT once the ceiling binds (the "1.15/shift at 150 DT" regime).
  // Saturation: a HARD min between linear demand and the cap —
  // trips = min(r·DT, cap). This comment used to describe a harmonic soft-min
  // (trips = 1/(1/(r·DT) + 1/cap)) "so the curve bends smoothly instead of
  // kinking". The code never did that, and the CODE IS RIGHT: harmonic would
  // put TF→FENI KM0 at 51% of its rate by 180 DT (1.12/day), while the largest
  // day ever run — 180 DT → 410 trips — measured 2.28/day, ABOVE the 2.194
  // average. A soft-min would invent a decline the data denies.
  // So the kink at DT = cap/rate is real and load-bearing: below it the next
  // truck adds a full rate of trips, above it the cap is fixed and it adds
  // almost nothing. Section C's Efficiency view marks it for that reason.
  // (Checked 2026-08-12 against dayTripsCap/dayRate on both TF paths.)
  const hasDay=Number.isFinite(m.dayRate)&&m.dayRate>0;
  let tr=hasDay?m.dayRate:m.avgTr;
  // Day-level measured drag only (dayB<0); flat/positive slopes stay flat.
  const slope=hasDay
    ?(Number.isFinite(m.dayB)&&m.dayB<0?m.dayB:0)
    :((Number.isFinite(m.bAdj)&&m.bAdj<0)?m.bAdj:(m.b<0?m.b:0));
  const anchorDt=hasDay?(m.dayAvgDt||m.avgDt):m.avgDt;
  if(slope<0&&Number.isFinite(anchorDt))tr+=slope*(dt-anchorDt);
  // Other (IWIP/Position) traffic on the shared FENI corridor: measured
  // coefficient from the Capability page's IWIP-impact model. DRAG ONLY —
  // lighter-than-typical foreign traffic earns no credit (avgTr already
  // contains the typical load; "never invent a gain").
  const otherDelta=planOtherTrafficDelta(key);
  tr+=otherDelta;
  // Shared-section coupling: the rest of the HOLDING PLAN on this path's span.
  const sec=planSectionDrag(key,dt,opts&&opts.selfId);
  tr+=sec.delta;
  const scale=planRainScale(key,rain);
  const rainDelta=tr*(scale-1);
  tr=Math.max(.3*(hasDay?m.dayRate:m.avgTr),tr*scale)*planContractorFactor(contractor);
  // Demonstrated-throughput ceiling + OVER-SATURATION DECAY (day level).
  //
  // Owner 2026-08-12: "if trips/DT keeps falling while trucks keep rising,
  // tonnage can NOT stay flat — act like a prediction model." Correct: a flat
  // plateau is closed-queue theory; real traffic PREDICTION models (BPR
  // volume-delay, the standard in transport demand modelling; fundamental
  // diagram of traffic flow) have throughput DECLINE beyond the critical
  // density because cycle time inflates faster than trucks are added.
  //
  // Three regimes, anchored to measurement:
  //   1. N ≤ N*        linear at the cluster rate (measured FLAT to 180 DT).
  //      N* = dayTripsCap/rate — the fleet where demand meets the proven cap.
  //   2. N ≈ N*        trips pinned at dayTripsCap (demonstrated maximum).
  //   3. N > N*        BPR-style decay: trips = cap / (1 + α·((N−N*)/N*)²),
  //      α = 0.15 (the standard BPR coefficient). Quadratic (not BPR's ^4)
  //      because there is NO measurement out there — mild, defensible decline.
  //      At 2×N* → 87% of cap; at 3.7×N* (700 DT) → ~47% of cap. Tonnage now
  //      FALLS past the ceiling instead of lying flat; trips/DT falls even
  //      faster; nothing crashes to zero.
  //
  // THE CAP IS A PATH PROPERTY, SHARED ACROSS PLANS: saturation is computed
  // on the COMBINED WBN fleet on this route key (this row + other non-foreign
  // rows); each row keeps its proportional share. opts.selfId excludes the
  // row being priced from the "others" sum.
  let satFactor=1;
  let _hybridInfo=null;
  if(tr>0&&dt>0){
    let otherDt=0,otherLd=0,sharedDt=0;
    // Owner (2026-08-21): "they are using the same window for going — see it
    // as a complete one-day plan, not one row." Different route KEYS that
    // share the corridor (TF>HUAFEI vs TF>POS 12 after the S4 split; IWIP
    // POS→FeNi transit) load the same road, so their trucks join the hybrid
    // evaluation fleet weighted by chainage-span overlap. Same-key rows stay
    // at weight 1 (otherDt); the legacy cap keeps the same-key basis only —
    // its demonstrated day cap is a PATH property, not a corridor one.
    const spanSelf=typeof _planSpan==='function'?_planSpan(key):null;
    const spanLen=spanSelf?Math.max(1e-6,spanSelf[1]-spanSelf[0]):null;
    if(typeof _planDraft!=='undefined'){
      const frozen=typeof planAllocFrozen==='function'&&planAllocFrozen();
      Object.keys(_planDraft).forEach(id=>{
        if(opts&&opts.selfId&&id===opts.selfId)return;
        const r2=_planDraft[id];
        if(!r2||!r2.key)return;
        const n=(frozen&&r2._allocDt!=null)?r2._allocDt:r2.dt;
        if(!(n>0))return;
        if(r2.key===key&&!r2.foreign){
          otherDt+=n;otherLd+=planNLoaders(r2);
        }else if(spanSelf){
          const s2=_planSpan(r2.key);
          if(s2){
            const ov=Math.min(spanSelf[1],s2[1])-Math.max(spanSelf[0],s2[0]);
            if(ov>0)sharedDt+=n*Math.min(1,ov/spanLen);
          }
        }
      });
    }
    const nComb=dt+otherDt;
    const linear=tr*nComb;
    // Rain scales the CEILING too (harsh-test 2026-08-12: with a fixed cap,
    // wet beat dry at over-saturation because rain lowered demand and thus
    // the penalty — physically wrong). The demonstrated cap is a road
    // property; mud degrades the road, so capEff = cap × rain scale.
    const nLoaders=(opts&&Number.isFinite(opts.nLoaders)&&opts.nLoaders>=1)?Math.round(opts.nLoaders):2;
    // HYBRID: when the backend saturation curve is cached, it REPLACES the
    // divide-at-ceiling. tr becomes the physics trips/DT at the COMBINED
    // fleet (x contractor factor; rain is inside the curve request).
    // The curve is priced at the route's COMBINED loaders too: rows share
    // one road AND its loading faces. Keying each row's curve on its OWN
    // loaders priced 929 trucks against 4 faces on one TF>HUAFEI row and
    // 25 on its neighbour — same road, trips/DT 25% apart (owner-caught,
    // 2026-08-21). Same combined basis as scripts/run_scenarios_hybrid.py.
    const nLoadersComb=nLoaders+otherLd;
    const hyb=planHybridCurveFor(key,nLoadersComb,rain);
    if(hyb){
      // A section-v/c ratio briefly multiplied the curve here (2026-08-21)
      // and came straight back out, owner: "BLB trips falls like hell — go
      // back to what we were doing before." Its capacity basis was each
      // section's median OBSERVED peak — the dayTripsCap trap again ("the
      // most we ever did" read as "the most we can do"), so normal plans
      // scored v/c ~2 everywhere and every route was punished twice (the
      // calibrated curve already carries real-day cross-traffic, backtest
      // R2 0.926). The span-weighted fleet below is the shared-road term;
      // the /api/congestion_plan windows table stays VISIBILITY ONLY.
      const pt=planHybridTripsAt(hyb,nComb+sharedDt);
      if(pt&&Number.isFinite(pt.trips_per_dt)&&pt.trips_per_dt>0){
        const trHyb=pt.trips_per_dt*planContractorFactor(contractor);
        satFactor=tr>0?Math.min(1,trHyb/tr):1;
        tr=trHyb;
        _hybridInfo={modelVersion:'hybrid',cycleTimeMin:Math.round(pt.cycle_time_min),
          rho:+pt.rho.toFixed(2),bottleneck:pt.bottleneck,
          p10:pt.p10,p90:pt.p90,knee:hyb.knee_dt};
      }
    }
    // Legacy ceiling only exists where a day cap was demonstrated; hybrid
    // pricing above no longer requires it (thin-day routes still have a
    // physics curve — they were silently stuck on the linear rate before).
    const capEff=(Number.isFinite(m.dayTripsCap)&&m.dayTripsCap>0)
      ?m.dayTripsCap*Math.min(1,scale)*planLoaderCapScale(m,nLoaders):0;
    // HARD MIN, deliberately. A BPR volume-delay penalty lived here briefly on
    // 2026-08-12 — served = capEff/(1 + 0.15·over²) — and it had to come out:
    //   • It made output COLLAPSE, not plateau. Measured on TF>FENI KM0:
    //     172 DT → 205 trips, 800 DT → 68, 2000 DT → 11. A 2,000-truck fleet
    //     produced 5% of what 172 trucks produced, and it fell without bound.
    //   • It disagreed with /api/simulate, which correctly clips, by up to 94×
    //     on the same plan (2000 DT: 572 t here vs 53,819 t there). Two models
    //     answering one question is the defect class this repo has already paid
    //     for twice — see the availability override and the capacity card.
    //   • The 0.15 and the quadratic were not measured. Four independent tests
    //     here failed to find a queueing effect at all, and the within-segment
    //     density effect is −4.8% across the extremes.
    // The ceiling IS measured (no day ever exceeded dayTripsCap); the shape of
    // any decay past it is not. So saturate at the proven ceiling and stay
    // silent about what nobody has measured: extra trucks divide the same
    // demonstrated trips, they do not destroy them.
    if(!_hybridInfo&&capEff>0&&linear>capEff){
      satFactor=capEff/linear;
      tr*=satFactor;
    }
    // 30% FLOOR (owner 2026-08-12: "700 DT showed 0.12 trips/DT — impossible,
    // we need the 0.30 threshold"). Drivers do not sit at 12% output: past the
    // point where the ceiling division would price a truck below 30% of the
    // path's measured rate, the floor holds. This is the same guard the model
    // always had; it also bounds how far beyond data the estimate can fall.
    const floorTr=.3*(hasDay?m.dayRate:m.avgTr)*Math.min(1,scale)*planContractorFactor(contractor);
    if(!_hybridInfo&&tr<floorTr){
      satFactor=satFactor*(floorTr/tr);
      tr=floorTr;
    }
  }
  const sf=planShiftFactor();
  // Weighbridge throughput ceiling (doctrine: ceiling, not delay curve). A
  // bridge weighs at most 30/h; when this path's assigned bridges are pushed
  // past 100% by the WHOLE plan + other traffic, the excess arrivals cannot
  // be weighed this shift — served/arrivals caps this path's trips. Penalty
  // only (served ≤ 1); below capacity nothing changes (measured flat waits).
  // opts.noWb breaks the recursion when the stress board asks for demand.
  let wbFactor=1,wbRows=null;
  if(!(opts&&opts.noWb)&&typeof planWbAssessFor==='function'){
    const name=contractor&&contractor.name?contractor.name:(contractor||'—');
    const preTrips=dt*tr*sf;                       // arrivals if fully served
    const w=planWbAssessFor(String(name),key,preTrips);
    if(w&&w.factor<1){wbFactor=Math.max(.3,w.factor);wbRows=w.rows;}
    else if(w)wbRows=w.rows;
  }
  const shiftServed=tr*sf*wbFactor;
  const hint=planCongestionHint(_hybridInfo?{satFactor,congestionStatus:(_hybridInfo.rho>=1?'overloaded':(_hybridInfo.rho>=0.7?'saturated':'free')),bottleneck:_hybridInfo.bottleneck}:{satFactor});
  return {daily:tr,shift:shiftServed,shiftFree:tr*sf,rainDelta:rainDelta*sf,otherDelta:otherDelta*sf,
    secDelta:sec.delta*sf,secExcess:sec.excess,wbFactor,wbRows,slope,
    modelVersion:_hybridInfo?'hybrid':'legacy_divide',
    cycleTimeMin:_hybridInfo?_hybridInfo.cycleTimeMin:null,
    rho:_hybridInfo?_hybridInfo.rho:null,
    hybridKnee:_hybridInfo?_hybridInfo.knee:null,
    satFactor,dayBasis:hasDay,m,
    nLoaders:(opts&&Number.isFinite(opts.nLoaders)&&opts.nLoaders>=1)?Math.round(opts.nLoaders):2,
    congestionStatus:hint.congestionStatus,bottleneck:hint.bottleneck};
}
// Payload: the contractor's own measured t/trip when we have it, else the path's.
function planPayload(key,contractor){
  const m=_pathResp&&_pathResp[key];
  if(contractor&&Number.isFinite(contractor.tf)&&contractor.tf>0)return {tf:contractor.tf,src:'contractor avg'};
  return {tf:(m&&m.tf)||0,src:'path avg'};
}
// Swap-mode inverse: trucks needed for a tonnage target. Trips/DT itself depends on the fleet (the
// b·DT term), so solve by damped fixed-point iteration, then round UP — you can't run half a truck.
function planDtForWmt(key,targetWmt,rain,contractor,opts){
  const pay=planPayload(key,contractor).tf;if(!(pay>0)||!(targetWmt>0))return null;
  const m=_pathResp&&_pathResp[key];let dt=Math.max(1,(m&&m.avgDt)||30);
  // UNREACHABLE TARGET (harsh-test 2026-08-12): with the demonstrated
  // throughput ceiling, tonnage MAXES OUT near N* — a target above that peak
  // has no fixed point and the solver used to fail with a generic message.
  // Detect it up front and report the ceiling so the planner learns the
  // actual limit instead of "could not size".
  // opts.selfId is load-bearing: without it planTripsPerDT counts this row
  // twice in the combined-fleet cap and Required DT over-asks on ceiling paths.
  if(m&&Number.isFinite(m.dayTripsCap)&&m.dayTripsCap>0){
    const sf=typeof planShiftFactor==='function'?planShiftFactor():0.5;
    const scale=typeof planRainScale==='function'?planRainScale(key,rain):1;
    const cf=typeof planContractorFactor==='function'?planContractorFactor(contractor):1;
    const nLoaders=(opts&&Number.isFinite(opts.nLoaders)&&opts.nLoaders>=1)?opts.nLoaders:planBuilderLoaders();
    const maxT=m.dayTripsCap*Math.min(1,scale)*sf*cf*pay*planLoaderCapScale(m,nLoaders);   // peak achievable/shift
    if(targetWmt>maxT*0.999){
      planDtForWmt._lastCeiling={maxT:Math.round(maxT),cap:m.dayTripsCap};
      return null;
    }
  }
  planDtForWmt._lastCeiling=null;
  for(let i=0;i<60;i++){
    const e=planTripsPerDT(key,dt,rain,contractor,opts);if(!e||!(e.shift>0))return null;
    const next=targetWmt/(e.shift*pay);
    if(!Number.isFinite(next)||next>1e6)return null;
    if(Math.abs(next-dt)<.01){dt=next;break;}
    dt=dt+.6*(next-dt);                      // damping keeps the declining-efficiency case stable
  }
  return Math.max(1,Math.ceil(dt));
}
// ── Cross-plan interactions panel (the WHY under "Add a haul path") ─────────
// The estimate above it already prices these effects in; this panel makes each
// one visible and attributable: shared-road drag from other plan rows, other
// (IWIP) corridor traffic, rain, and the weighbridge ceiling. Everything here
// is measured (page-1 coefficients, M/M/1 arrivals, ticket history) — when an
// effect is zero it says WHY it's zero rather than hiding the concept.
function planRenderImpacts(key,dt,e,contractor){
  // Plan updates panel hidden for now — keep stub so callers stay safe.
  const box=q('plan-impacts');if(box)box.innerHTML='';
  if(typeof _planAiTimer!=='undefined'&&_planAiTimer){clearTimeout(_planAiTimer);_planAiTimer=null;}
}
function planAiDropFleetDup(){
  // Once ✦ AI has answered, remove the short fleet-size row — same story twice.
  const box=q('plan-impacts');if(!box)return;
  box.querySelectorAll('.imp-row[data-imp="fleet"]').forEach(el=>el.remove());
}
// ── AI advisor (owner 2026-08-12: "an AI that reads what we have in
// historicals, our thresholds, and gives real info instead of prewritten
// text"). The BROWSER packs the live numbers (path history, thresholds,
// fleet-size math, WB stress, whole holding plan, non-plan traffic) and the
// SERVER relays them to a local LLM (Ollama). The model sees only real
// figures, so its answer is grounded; if the LLM is unreachable the panel
// says so instead of pretending.
let _planAiBusy=false;
let _planAiTimer=null,_planAiLastKey='',_planAiSeq=0;
// AUTO-advise: debounce until the planner stops editing (1.2 s), skip when the
// situation hasn't changed, and drop stale responses. deepseek-v4-pro:cloud
// answers in ~1.5–3 s (fastest of the four local-relay models benchmarked
// 2026-08-12; glm 4 s, kimi 1.7 s but weaker read, minimax erroring).
function planAiSchedule(){
  if(_planAiTimer)clearTimeout(_planAiTimer);
  _planAiTimer=setTimeout(()=>{
    const ctx=planAiContext();
    // Situation key: path + DT + rain + WB + plan rows + non-plan traffic.
    const sitKey=JSON.stringify([ctx.building,ctx.holding_plan,ctx.non_plan_traffic.trips_per_shift,
      (ctx.weighbridges.assigned||[]).map(w=>w.wb)]);
    if(sitKey===_planAiLastKey)return;          // nothing changed — keep the read
    _planAiLastKey=sitKey;
    planAiAdvise(ctx);
  },1200);
}
function planAiContext(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d;
  const dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  const c=planContractor();
  const m=(_pathResp&&_pathResp[key])||{};
  const e=planTripsPerDT(key,dt,rain,c,{nLoaders:planBuilderLoaders()});
  const pay=planPayload(key,c);
  const sf=typeof planShiftFactor==='function'?planShiftFactor():0.5;
  const plan=Object.keys(_planDraft||{}).map(id=>{const r=_planDraft[id];
    return {path:r.key,contractor:r.contractor,dt:r.dt,loaders:planNLoaders(r),foreign:!!r.foreign};});
  const wb=(e&&e.wbRows)?e.wbRows.map(r=>({wb:r.wb,arrivals:Math.round(r.arrivals),cap:Math.round(r.cap),util:+(r.rho||0).toFixed(2)})):[];
  return {
    building:{path:key,contractor:c?c.name:null,dt,rain_mm:rain},
    path_history:{
      typical_dt:m.avgDt!=null?Math.round(m.avgDt):null,
      max_dt_ever:planDtEnvelope(m),
      trips_per_dt_day_at_typical:m.avgTr!=null?+m.avgTr.toFixed(2):null,
      trips_per_dt_shift_at_typical:m.avgTr!=null?+(m.avgTr*sf).toFixed(2):null,
      trips_per_dt_p25_p75_day:[m.trP25,m.trP75].map(x=>x!=null?+x.toFixed(2):null),
      tonnes_per_trip:pay.tf?+pay.tf.toFixed(1):null,
      fleet_size_slope_per_dt_day:Number.isFinite(m.bAdj)?+m.bAdj.toFixed(4):(Number.isFinite(m.b)?+m.b.toFixed(4):null),
    },
    this_estimate:e?{
      trips_per_dt_shift:+e.shift.toFixed(3),
      trips:Math.round(dt*e.shift),
      wmt:Math.round(dt*e.shift*(pay.tf||0)),
      wb_capacity_factor:+(e.wbFactor||1).toFixed(3),
      rain_delta:+(e.rainDelta||0).toFixed(3),
      section_drag:+(e.secDelta||0).toFixed(3),
      other_traffic_drag:+(e.otherDelta||0).toFixed(3),
      floor_applied:e.shiftFree!=null&&Math.abs(e.shiftFree-Math.max(.3*(m.avgTr||0)*sf,0))<1e-6,
    }:null,
    weighbridges:{assigned:wb,ceiling_per_bridge_per_hour:PLAN_WB_TRIPS_PER_HOUR,
      shift_hours:Math.max(1,parseFloat((q('plan-hours')||{}).value)||12)},
    holding_plan:plan,
    non_plan_traffic:{trips_per_shift:Math.round(_planOtherTrips||0),
      basis:_planOtherManual?'manual':_planOtherRegime,
      busy_period_median:_planOtherTypical&&_planOtherTypical.peak?_planOtherTypical.peak.tripsPerShift:null,
      recent_30d_median:_planOtherTypical?_planOtherTypical.tripsPerShift:null},
    thresholds:{wb_amber:0.7,wb_red:1.0,trips_per_dt_floor:'30% of typical baseline',
      beyond_data:'estimates beyond max_dt_ever are guarded; engine capacity untested there'},
  };
}
function planAiAdvise(ctx){
  const out=q('plan-ai-out');if(!out)return;
  const seq=++_planAiSeq;
  // Keep the previous read visible while the new one loads (less flicker).
  if(!out.querySelector('.plan-ai-answer'))out.innerHTML='<div class="plan-ai-busy">✦ AI reading the live plan…</div>';
  else out.insertAdjacentHTML('afterbegin','<div class="plan-ai-busy">✦ updating…</div>');
  fetch('/api/plan/ai-advise',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({context:ctx||planAiContext()}),
  }).then(r=>r.json()).then(res=>{
    if(seq!==_planAiSeq)return;                  // superseded by a newer edit
    const o=q('plan-ai-out');if(!o)return;
    if(!res||!res.ok){
      o.innerHTML='<div class="plan-ai-err">✦ AI advisor unavailable: '+escH((res&&res.error)||'no response')+'</div>';
      return;
    }
    // Analysis only — never name the model in the UI.
    o.innerHTML='<div class="plan-ai-answer"><span class="plan-ai-star">✦</span> '+escH(res.advice||'').replace(/\n/g,'<br>')+'</div>';
    // Drop the plain fleet-size row when AI covers the same ground.
    if(typeof planAiDropFleetDup==='function')planAiDropFleetDup();
  }).catch(e=>{
    if(seq!==_planAiSeq)return;
    const o=q('plan-ai-out');
    if(o)o.innerHTML='<div class="plan-ai-err">✦ AI advisor unreachable ('+escH(String(e))+')</div>';
  });
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
  // A · Production & capacity is where the companion actually renders now. The
  // planRenderOutcomes() call below is a no-op since its container was deleted
  // on 2026-08-12 — that is exactly why this checkbox silently stopped doing
  // anything, so do not rely on it being the live consumer again.
  if(typeof psRefreshTicketKpi==='function')psRefreshTicketKpi();
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
function planPathModelWmtAtRain(rainMm){
  const hz=planHorizonFactor();
  let wmt=0,any=false;
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||r.foreign)return;
    const c=planContractor(r.contractor);
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rainMm,c,planTripOpts(id)):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):null;
    if(!e||!pay||!(pay.tf>0))return;
    wmt+=r.dt*e.shift*hz*(pay.tf||0);
    any=true;
  });
  return any?wmt:null;
}
function planRenderComingDays(){
  const box=q('plan-coming-days');
  if(!box)return;
  const res=_planRainOutlook;
  const days=(res&&res.ok&&res.days)||[];
  if(!days.length){
    box.innerHTML='<p class="muted" style="margin:0;font-size:12px">Rain forecast unavailable — set Rain in Scenario.</p>';
    return;
  }
  const sel=(q('plan-date')||{}).value||'';
  const hasPlan=Object.keys(_planDraft||{}).some(id=>_planDraft[id]&&!_planDraft[id].foreign);
  const wmts=days.map(d=>planPathModelWmtAtRain(Math.max(0,Number(d.mm)||0)));
  const finite=wmts.filter(n=>n!=null&&n>0);
  const max=finite.length?Math.max.apply(null,finite):1;
  box.innerHTML=`<div class="plan-coming-strip">${days.map((d,i)=>{
    const mm=d.mm==null?null:d.mm;
    const wet=mm!=null&&mm>=10,damp=mm!=null&&mm>=2&&mm<10;
    const w=wmts[i];
    const h=hasPlan&&w!=null?Math.max(10,Math.round(72*w/max)):8;
    const cls='plan-coming-chip'+(wet?' wet':damp?' damp':'')+(d.date===sel?' on':'');
    const wmtTxt=(!hasPlan||w==null)?'—':fmtExact(Math.round(w));
    const mmTxt=mm!=null?(mm>=1?Math.round(mm):mm>0?'&lt;1':'0'):'—';
    return `<button type="button" class="${cls}" data-date="${d.date}"
      title="${d.date} · ${mm!=null?mm+' mm':''} · ${wmtTxt} t predicted (path model · rain moves trips)"
      onclick="planPickOutlookDay('${d.date}')">
      <span class="d">${d.date.slice(5)}</span>
      <span class="bar-wrap"><span class="bar" style="height:${h}%"></span></span>
      <span class="t">${wmtTxt}</span>
      <span class="mm">${mmTxt} mm</span>
    </button>`;
  }).join('')}</div>`;
}
function planRenderRainOutlook(){
  // Coming-days strip is the product view. Hidden #plan-rain-outlook stays as
  // a fixture-safe stub; do not claim simulate tonnes change with rain (J57).
  if(typeof planRenderComingDays==='function')planRenderComingDays();
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
let _planOtherTrips=0,_planOtherManual=false,_planOtherSrc='',_planOtherSrcTrips=0,_planOtherPaths=[],_planOtherWb=[],_planOtherTypical=null,_planOtherRegime='off';
const PLAN_WB_TRIPS_PER_HOUR=30;   // conservative vs measured 35–49 peaks
function planOtherManualEdit(){
  _planOtherManual=true;
  _planOtherTrips=Math.max(0,parseFloat((q('plan-other-trips')||{}).value)||0);
  computePlan();
}
// Apply the selected other-traffic regime (peak = best-60-day window, the
// planning default; recent = last-30-days median). Sets the input value, the
// per-bridge shares for the stress board, and the source tag. A manual edit
// keeps the typed number but still uses the regime's bridge shares.
let _planOtherShiftRes=null;   // last shift-context payload (fallback shares)
function planOtherApplyRegime(res){
  if(res)_planOtherShiftRes=res;
  const typ=_planOtherTypical;
  const peak=typ&&typ.peak&&Number(typ.peak.tripsPerShift)>0?typ.peak:null;
  // OFF (default per owner 2026-08-12): plan starts with ZERO non-plan trips.
  // The planner opts into busy-period / recent medians, or types a number.
  const use=_planOtherRegime==='off'?null:((_planOtherRegime==='peak'&&peak)?peak:typ);
  const shares=use&&Array.isArray(use.wbShares)&&use.wbShares.length?use.wbShares:null;
  if(shares){
    const s=shares.reduce((a,b)=>a+(b.sharePct||0),0)||1;
    _planOtherWb=shares.map(b=>({wb:String(b.wb),share:(b.sharePct||0)/s}));
  }else{
    // Manual number (or fallback): spread over the measured last-shift bridges,
    // else the recent 30d shares — the trucks must weigh SOMEWHERE real.
    const r=_planOtherShiftRes||{};
    const _obrs=(r.bridges||[]).map(b=>({wb:String(b.wb),w:(b.trucks||0)*(b.otherPct||0)})).filter(b=>b.w>0);
    const _osum=_obrs.reduce((a,b)=>a+b.w,0);
    if(_osum>0)_planOtherWb=_obrs.map(b=>({wb:b.wb,share:b.w/_osum}));
    else if(typ&&Array.isArray(typ.wbShares)&&typ.wbShares.length){
      const s2=typ.wbShares.reduce((a,b)=>a+(b.sharePct||0),0)||1;
      _planOtherWb=typ.wbShares.map(b=>({wb:String(b.wb),share:(b.sharePct||0)/s2}));
    }else _planOtherWb=[];
  }
  if(!_planOtherManual){
    _planOtherTrips=_planOtherRegime==='off'?0:(use?Number(use.tripsPerShift):0);
    const el=q('plan-other-trips');
    if(el)el.value=String(Math.round(_planOtherTrips));
  }
  const src=q('plan-other-src');
  if(src){
    // Short unit tag only — regime label lives in the strip below.
    const mmdd=x=>String(x||'').slice(5);
    if(_planOtherRegime==='off'&&!_planOtherManual){
      src.textContent='/shift';
      src.title='No non-plan traffic assumed. Pick Busy period / Recent below, or type the trucks you expect.';
    }else if(use===peak&&peak){
      src.textContent='/shift';
      src.title='Busy period (busiest 60 days: '+(peak.window||'')+') · median '
        +Math.round(peak.tripsPerShift)+' non-plan trips/shift'
        +(_planOtherSrcTrips?(' · last measured: '+Math.round(_planOtherSrcTrips)):'');
    }else if(typ){
      src.textContent='/shift';
      src.title='Recent (last 30 data days) · median '+Math.round(typ.tripsPerShift||0)
        +' non-plan trips/shift'
        +(_planOtherSrcTrips?(' · last measured: '+Math.round(_planOtherSrcTrips)):'');
    }else{
      src.textContent='/shift';
      src.title=_planOtherSrc?('From '+mmdd(_planOtherSrc)):'';
    }
  }
}
function planOtherSetRegime(mode){
  _planOtherRegime=(mode==='recent'||mode==='peak'||mode==='off')?mode:'off';
  _planOtherManual=false;      // switching regime re-derives the number
  planOtherApplyRegime();
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
              // TWO measured regimes for other traffic (owner: "site is quiet
              // now; Jan–Feb was operation at its best — use the best scenario"):
              //   peak   = busiest 60-day window in the data (server-scanned)
              //   recent = last-30-days median
              // Default = PEAK: plan for the ramp-back, not today's lull.
              // planOtherApplyRegime() re-derives trips + bridge shares.
              const typ=res.otherTypical||null;
              _planOtherTypical=typ&&Number(typ.tripsPerShift)>0?typ:null;
              planOtherApplyRegime(res);
              // Road-only mode reads locations from otherPaths — rebuild when they land.
              if(typeof planForeignOn==='function'&&planForeignOn())renderPlanBuilder();
              else computePlan();
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
    const cont=planNormalizeForeignContractor(pth.contractor);
    const id=cont+'|'+key+'|road';
    if(_planDraft[id])return;                     // don't duplicate
    // FOREIGN paths usually have no WBN route history — carry their MEASURED
    // trips/trucks from the tickets so the row renders honest numbers.
    _planDraft[id]={key,dt:Math.max(1,Math.round(pth.trucks||1)),loaders:2,contractor:cont,
      source:sKey,dest:dKey,foreign:true,
      measTrips:Math.max(0,Math.round(pth.trips||0)),
      measTrucks:Math.max(1,Math.round(pth.trucks||1))};
    added++;
  });
  if(added){computePlan();}
  const st=q('plan-save-status');
  if(st)st.textContent=added
    ?('Added '+added+' average road-only path(s) from '+(_planOtherSrc||'last')+' shift — counted in weighbridges + road congestion (no WMT). Edit DT if needed.')
    :'Measured road-only paths already in the plan (or none available).';
}
function planRenderWbLoad(totTrips,wb,hours,avgTf){
  // Aggregate WB bar removed — Bridge load board is the capacity model.
  // This strip explains non-plan traffic (IWIP/position) + regime toggle.
  const box=q('plan-wb-load');if(!box)return;
  const other=_planOtherTrips||0;
  const dragProbe=typeof planOtherTrafficDelta==='function'?planOtherTrafficDelta('X>FENI KM0'):0;
  const dragTxt=dragProbe<0
    ?`<span class="plan-other-drag">FENI drag <b>${fmtExact(dragProbe,2)}</b> trips/DT</span>`
    :'';
  const addTip='Click to add the average road-only (IWIP / Position) truck paths as rows in your plan — used for weighbridge load and road congestion. No WMT for us.';
  const addBtn=(_planOtherPaths&&_planOtherPaths.length)
    ?`<div class="plan-other-add-wrap">
        <button type="button" class="plan-other-add" onclick="planAddMeasuredRoadOnly()" title="${escH(addTip)}">+ Add road-only paths to plan</button>
        <span class="plan-other-add-tip">${escH(addTip)}</span>
      </div>`
    :'';
  const peak=_planOtherTypical&&_planOtherTypical.peak;
  const seg=(mode,label,title)=>{
    const on=(_planOtherRegime===mode&&!_planOtherManual);
    return `<button type="button" class="plan-other-seg${on?' on':''}" onclick="planOtherSetRegime('${mode}')" title="${escH(title)}">${label}</button>`;
  };
  const regimeCtl=peak
    ?`<div class="plan-other-regime" role="group" aria-label="Non-plan trips basis">`
      +seg('off','None',`Zero non-plan trips (default). Add them only when you expect IWIP / position trucks on your shift.`)
      +seg('peak','Busy period',`Busiest measured 60 days (${peak.window||'peak'}): median ${fmtExact(peak.tripsPerShift)} non-plan trips/shift. Use when ops run at full tempo.`)
      +seg('recent','Recent',`Last 30 data days: median ${fmtExact(_planOtherTypical.tripsPerShift)} non-plan trips/shift. Use for today's quieter tempo.`)
      +`</div>`
    :'';
  if(!(other>0||addBtn||peak)){box.innerHTML='';return;}
  const helpTxt=other>0
    ?'IWIP / position trucks on the same bridges — counted in Bridge load below'
    :'None assumed — pick Busy period / Recent, or type trucks in Scenario';
  box.innerHTML=`<div class="plan-other-strip">
    <div class="plan-other-strip-main">
      <span class="plan-other-k">Non-plan traffic</span>
      <span class="plan-other-v">${other>0?`<b>${fmtExact(Math.round(other))}</b> trips/shift`:'<b>0</b>'}</span>
      <span class="plan-other-help muted">${escH(helpTxt)}</span>
    </div>
    <div class="plan-other-strip-actions">${regimeCtl}${dragTxt}${addBtn}</div>
  </div>`;
}
let _planPathKey='';   // last source>dest — only seed DT when this changes
let _planUserEditedFleet=false;  // once user types DT/WMT, never auto-overwrite

function planMarkFleetEdit(){ _planUserEditedFleet=true; planPreview(); }

/** Default haul path in Step 1 builder (owner preference). */
const PLAN_DEFAULT_SRC='TF';
const PLAN_DEFAULT_DST='FENI KM0';
/** Road-only contractors (non-WBN): IWIP haulers vs Position relocation trucks. */
const PLAN_FOREIGN_CONTRACTORS=['IWIP','POSITION'];
/** Remember WBN contractor/src/dst while Road-only is checked so we can restore. */
let _planWbnKeep=null;

function planForeignOn(){
  return !!(q('plan-foreign')&&q('plan-foreign').checked);
}
function planNormalizeForeignContractor(c){
  return String(c||'').trim().toUpperCase()==='POSITION'?'POSITION':'IWIP';
}
/** Measured non-plan paths from shift-context, optionally filtered by IWIP/POSITION. */
function planForeignPaths(contractor){
  const all=_planOtherPaths||[];
  const want=contractor?planNormalizeForeignContractor(contractor):null;
  return all.filter(p=>{
    if(!p)return false;
    const o=String(p.origin||'').trim(),d=String(p.dest||'').trim();
    if(!o||!d||o===d)return false;
    if(!want)return true;
    return planNormalizeForeignContractor(p.contractor)===want;
  });
}
function planForeignContractors(){
  const have=new Set(planForeignPaths().map(p=>planNormalizeForeignContractor(p.contractor)));
  return PLAN_FOREIGN_CONTRACTORS.map(name=>({name,tripsPerDT:null,tf:null,t:0,hasPaths:have.has(name)}));
}
function planForeignPath(contractor,src,dst){
  return planForeignPaths(contractor).find(p=>p.origin===src&&p.dest===dst)||null;
}
function planSetForeignUi(on){
  const swap=q('plan-swap-btn'),swapW=q('plan-swap-btn-wmt');
  if(swap)swap.style.visibility=on?'hidden':'';
  if(swapW)swapW.style.visibility=on?'hidden':'';
  // Road-only has no WMT — force DT entry without running planSwapMode (avoids preview race).
  if(on&&_planMode==='wmt'){
    _planMode='dt';
    const dtBox=q('plan-input-dt'),wmtBox=q('plan-input-wmt');
    if(dtBox)dtBox.style.display='';
    if(wmtBox)wmtBox.style.display='none';
  }
}
/** Checkbox: Road-only → contractor becomes IWIP/POSITION; locations from measured paths. */
function planForeignToggle(){
  const on=planForeignOn();
  const cs=q('plan-contractor'),src=q('plan-src'),dst=q('plan-dst');
  if(on){
    if(!_planWbnKeep){
      _planWbnKeep={c:cs?cs.value:'',s:src?src.value:'',d:dst?dst.value:''};
    }
    planSetForeignUi(true);
    if(!_planOtherSrc&&!_planOtherManual)planFetchOtherTraffic();
  }else{
    planSetForeignUi(false);
  }
  _planUserEditedFleet=false;
  _planPathKey='';
  const restore=(!on&&_planWbnKeep)?_planWbnKeep:null;
  renderPlanBuilder(restore);
  if(!on)_planWbnKeep=null;
}

function renderPlanBuilder(restore){
  const src=q('plan-src');if(!src)return;
  planEnsureDate();
  if(!_planRainOutlook)planFetchRainOutlook();   // 16-day site forecast strip
  if(!_planOtherSrc&&!_planOtherManual)planFetchOtherTraffic(); // non-plan trucks
  const foreign=planForeignOn();
  planSetForeignUi(foreign);
  const cs=q('plan-contractor');
  const keepC=(restore&&restore.c)||(cs?cs.value:'');
  const keepS=(restore&&restore.s)||src.value;
  const keepD=(restore&&restore.d)||((q('plan-dst')||{}).value);

  if(foreign){
    if(cs){
      const fcs=planForeignContractors();
      let cVal=PLAN_FOREIGN_CONTRACTORS.includes(keepC)?keepC:'IWIP';
      // Prefer a contractor that actually has measured paths this shift.
      if(!fcs.find(c=>c.name===cVal&&c.hasPaths)){
        const withP=fcs.slice().sort((a,b)=>{
          const ta=planForeignPaths(a.name).reduce((n,p)=>n+(p.trips||0),0);
          const tb=planForeignPaths(b.name).reduce((n,p)=>n+(p.trips||0),0);
          return tb-ta;
        }).find(c=>c.hasPaths);
        if(withP)cVal=withP.name;
      }
      cs.innerHTML=fcs.map(c=>`<option value="${escH(c.name)}"${c.name===cVal?' selected':''}>${escH(c.name)}${c.hasPaths?'':' (no measured paths)'}</option>`).join('');
    }
    const cont=planNormalizeForeignContractor((cs&&cs.value)||'IWIP');
    const paths=planForeignPaths(cont);
    if(!paths.length){
      src.innerHTML='<option value="">No measured paths yet</option>';
      const dst=q('plan-dst');if(dst)dst.innerHTML='';
      planUpdatePathMeta();
      planPreview();
      computePlan();
      return;
    }
    // Prefer busiest source for this contractor when current pick is invalid.
    const bySrc={};
    paths.forEach(p=>{bySrc[p.origin]=(bySrc[p.origin]||0)+(p.trips||0);});
    const sources=Object.keys(bySrc).sort((a,b)=>bySrc[b]-bySrc[a]||a.localeCompare(b));
    const srcVal=sources.includes(keepS)?keepS:sources[0];
    src.innerHTML=sources.map(s=>`<option${s===srcVal?' selected':''}>${escH(s)}</option>`).join('');
    planSrcChange(keepD, /*fromBuilder*/true);
    computePlan();
    return;
  }

  if(cs){
    cs.innerHTML=planContractors().map(c=>`<option value="${escH(c.name)}"${c.name===keepC?' selected':''}>${escH(c.name)}${Number.isFinite(c.tripsPerDT)?'':' (no history)'}</option>`).join('');
  }
  const keys=_planValidKeys();
  if(!keys.length){src.innerHTML='<option>loading…</option>';return;}
  const sources=[...new Set(keys.map(k=>k.split('>')[0].trim()))].sort();
  // Keep user's selection when present; otherwise land on TF → FENI KM0.
  const srcVal=sources.includes(keepS)?keepS
    :(sources.includes(PLAN_DEFAULT_SRC)?PLAN_DEFAULT_SRC:sources[0]);
  src.innerHTML=sources.map(s=>`<option${s===srcVal?' selected':''}>${escH(s)}</option>`).join('');
  // Rebuild dest list without forcing a DT reset unless the path key actually changes.
  planSrcChange(keepD||PLAN_DEFAULT_DST, /*fromBuilder*/true);
  computePlan();
}
function planContractorChange(){
  if(planForeignOn()){
    _planUserEditedFleet=false;
    _planPathKey='';
    const src=q('plan-src'),dst=q('plan-dst');
    const cont=planNormalizeForeignContractor((q('plan-contractor')||{}).value);
    const paths=planForeignPaths(cont);
    if(!src)return;
    if(!paths.length){
      src.innerHTML='<option value="">No measured paths yet</option>';
      if(dst)dst.innerHTML='';
      planUpdatePathMeta();planPreview();computePlan();
      return;
    }
    const bySrc={};
    paths.forEach(p=>{bySrc[p.origin]=(bySrc[p.origin]||0)+(p.trips||0);});
    const sources=Object.keys(bySrc).sort((a,b)=>bySrc[b]-bySrc[a]||a.localeCompare(b));
    src.innerHTML=sources.map(s=>`<option>${escH(s)}</option>`).join('');
    planSrcChange(null, true);
    computePlan();
    return;
  }
  planUpdatePathMeta(); planPreview(); computePlan();
}
function planSrcChange(preferredDest, fromBuilder){
  const s=(q('plan-src')||{}).value,dst=q('plan-dst');if(!dst)return;
  let dests;
  if(planForeignOn()){
    const cont=planNormalizeForeignContractor((q('plan-contractor')||{}).value);
    dests=[...new Set(planForeignPaths(cont).filter(p=>p.origin===s).map(p=>p.dest))].sort();
  }else{
    dests=[...new Set(_planValidKeys().filter(k=>k.split('>')[0].trim()===s).map(k=>k.split('>')[1].trim()))].sort();
  }
  if(!dests.length){dst.innerHTML='';planUpdatePathMeta();planPreview();return;}
  const want=preferredDest||dst.value;
  const dVal=dests.includes(want)?want
    :(!planForeignOn()&&dests.includes(PLAN_DEFAULT_DST)?PLAN_DEFAULT_DST:dests[0]);
  dst.innerHTML=dests.map(d=>`<option${d===dVal?' selected':''}>${escH(d)}</option>`).join('');
  planDstChange(!!fromBuilder);
}
function planDstChange(_fromBuilder){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value;
  const key=s+'>'+d, m=_pathResp&&_pathResp[key], dt=q('plan-dt');
  const foreign=planForeignOn();
  const fPath=foreign?planForeignPath((q('plan-contractor')||{}).value,s,d):null;
  const pathChanged=key!==_planPathKey;
  if(pathChanged){
    const prevKey=_planPathKey;
    _planPathKey=key;
    // Seed typical DT only when the haul path actually changes AND the user
    // hasn't typed a fleet yet. Never overwrite on tab/capability refresh
    // (same path) or after the user has edited DT/WMT.
    const realSwitch=!!prevKey&&prevKey!==key;
    if(realSwitch)_planUserEditedFleet=false;
    if(dt&&_planMode==='dt'&&!_planUserEditedFleet){
      if(foreign&&fPath)dt.value=Math.max(1,Math.round(fPath.trucks||1));
      else if(m)dt.value=Math.round(m.avgDt||50);
    }
  }
  planUpdatePathMeta();
  planPreview();
}
function planUpdatePathMeta(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,hint=q('plan-hint');
  if(!hint)return;
  if(planForeignOn()){
    const cont=planNormalizeForeignContractor((q('plan-contractor')||{}).value);
    const p=planForeignPath(cont,s,d);
    if(!p){hint.innerHTML='<div class="plan-hint-path"><div class="plan-hint-route muted">No measured road-only path for this pick — wait for non-plan traffic, or uncheck Road-only.</div></div>';return;}
    const rate=p.trucks?p.trips/p.trucks:0;
    const chips=[];
    chips.push(`<span class="plan-hint-chip" title="Measured trips on the last ticket shift"><b>${fmtExact(Math.round(p.trips||0))}</b><span class="u">trips · shift</span></span>`);
    chips.push(`<span class="plan-hint-chip" title="Distinct trucks on that path"><b>${fmtExact(Math.round(p.trucks||0))}</b><span class="u">DT measured</span></span>`);
    chips.push(`<span class="plan-hint-chip" title="Measured trips ÷ trucks"><b>${fmtExact(rate,2)}</b><span class="u">trips/DT</span></span>`);
    chips.push(`<span class="plan-hint-chip"><b>${escH(cont)}</b><span class="u">road-only</span></span>`);
    hint.innerHTML=`<div class="plan-hint-path">
      <div class="plan-hint-route"><b>${escH(s)} → ${escH(d)}</b><span class="muted">measured non-plan · ${_planOtherSrc?escH(_planOtherSrc):'last shift'}</span></div>
      <div class="plan-hint-metrics">${chips.join('')}</div>
    </div>`;
    return;
  }
  const m=_pathResp&&_pathResp[s+'>'+d];
  const c=planContractor(),f=planContractorFactor(c);
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
  if(v.model==='local')return {cls:'pending', text:'Updating…'};
  if(v.model==='localfinal')return {cls:'ok', text:'Measured path history'};
  if(v.model==='roadonly')return {cls:'ok', text:'Road-only · congestion, no WMT'};
  if(v.fallback||v.model==='offline')return {cls:'warn', text:'Path formula fallback (offline)'};
  const name=PLAN_MODEL_LABELS[v.model]||v.modelLabel||v.model||'model';
  const cv=Number.isFinite(v.cvR2), shown=cv?v.cvR2:v.r2;
  let text=escH(name);
  if(Number.isFinite(shown))text+=` · R² ${fmtExact(shown,2)}`;
  if(Number.isFinite(v.contractorFactor)&&v.contractorFactor!==1){
    text+=` · factor ${fmtExact(v.contractorFactor,2)}×`;
  }
  const weak=Number.isFinite(v.baselineLift)&&v.baselineLift<0.01;
  return {cls:weak?'warn':'ok', text};
}
function _planRenderEstimate(v){
  const box=q('plan-preview');if(!box)return;
  const hz=planHorizonFactor();
  const tripsShow=Math.round((v.trips||0)*hz);
  const wmtShow=Math.round((v.wmt||0)*hz);
  const lines=[
    ['Trips / DT',fmtExact((v.tripsPerDt||0)*hz,2)],
    [v.swapped?'Trucks needed':'Trucks',fmtExact(v.dt)+' DT'],
    ['Trips',fmtExact(tripsShow)],
    ['t / trip',v.foreign?'—':fmtExact(v.payload,1)+' t'],
  ];
  if(Number.isFinite(v.contractorFactor)&&v.contractorFactor!==1){
    lines.push(['Contractor',fmtExact(v.contractorFactor,2)+'×']);
  }
  if(v.cycle&&Number.isFinite(v.cycle.cycle_time_min)){
    lines.push(['Cycle',fmtExact(v.cycle.cycle_time_min,0)+' min']);
  }
  const mod=_planModelLabel(v);
  const note=`${escH(v.src)} → ${escH(v.dst)} · ${escH(v.contractor||'—')}`
    +(v.foreign?' · road-only (no WMT)':(v.swapped?` · ${fmtExact(wmtShow)} t`:''));
  const totalInner=v.foreign
    ?`<div class="est-total-v est-total-road">Road-only <span class="u">no WMT</span></div>`
    :`<div class="est-total-v">${v.swapped?fmtExact(v.dt):fmtExact(wmtShow)} <span class="u">${v.swapped?'DT':'t'}</span></div>`;
  box.classList.remove('empty','has-warns');
  box.classList.toggle('is-loading', v.model==='local');
  box.innerHTML=`<div class="est-head"><span>This path</span><span class="muted">${escH(planHorizonHint())} · not the plan total</span></div>`
    +`<div class="est-main">`
    +`<div class="est-kpis">${lines.map(l=>`<div class="est-kpi"><span class="k">${escH(l[0])}</span><b class="v">${l[1]}</b></div>`).join('')}</div>`
    +`<div class="est-total"><div class="est-total-l">${v.foreign?'WMT':(v.swapped?'Trucks needed':'WMT')}</div>${totalInner}</div>`
    +`</div>`
    +`<div class="est-foot">`
    +`<div class="est-note" title="${note}">${note}</div>`
    +`<div class="est-attr"><span class="est-model ${mod.cls}">${mod.text}</span></div>`
    +`</div>`;
  if(!Object.keys(_planDraft||{}).length&&!v.foreign&&typeof planPaintHero==='function'){
    planPaintHero({
      wmt:Math.round((v.wmt||0)*hz),
      trips:Math.round((v.trips||0)*hz),
      dt:v.dt,
      achv:null,
      status:'This path · not yet in the plan'
    });
  }
}
function planPreview(){
  const box=q('plan-preview');if(!box)return;
  const blank=(msg)=>{box.classList.add('empty');box.classList.remove('is-loading','has-warns');
    box.innerHTML=`<div class="est-head"><span>This path</span></div>`
      +`<div class="est-main"><div class="est-kpis"></div>`
      +`<div class="est-total"><div class="est-total-v">—</div></div></div>`
      +`<div class="est-foot"><div class="est-note">${escH(msg)}</div></div>`;
    const imp=q('plan-impacts');if(imp)imp.innerHTML='';
    planRenderBestHistory({ok:false,error:msg});
    if(!Object.keys(_planDraft||{}).length&&typeof planPaintHero==='function'){
      planPaintHero({wmt:null,trips:null,dt:0,achv:null,status:'Add a path to predict'});
    }
  };
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d,m=_pathResp&&_pathResp[key];
  const foreign=planForeignOn();   // road-only: IWIP / POSITION trucks, no WMT for us
  const hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12);
  const wbOpen=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8);

  // Road-only uses measured non-plan paths — no WBN path-response required.
  if(foreign){
    const cont=planNormalizeForeignContractor((q('plan-contractor')||{}).value);
    const fp=planForeignPath(cont,s,d);
    if(!s||!d||!fp)return blank('Select IWIP or POSITION and a measured location pair.');
    const dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
    const rate=fp.trucks?fp.trips/fp.trucks:0;
    const trips=dt*rate;
    const base={src:s,dst:d,contractor:cont,hours,swapped:false,warns:[],foreign:true,
      dt,tripsPerDt:rate,trips,wmt:0,payload:0,payloadSrc:'road-only',model:'roadonly',
      contractorFactor:1};
    _planRenderEstimate(base);
    const imp=q('plan-impacts');
    if(imp){
      imp.innerHTML=`<div class="imp-head muted">Road-only · measured congestion</div>`
        +`<div class="imp-row imp-ok"><span class="imp-ic">🚚</span><span>${escH(cont)} ${escH(s)} → ${escH(d)}: ${fmtExact(Math.round(fp.trips||0))} trips / ${fmtExact(Math.round(fp.trucks||0))} DT on ${_planOtherSrc?escH(_planOtherSrc):'last'} shift — adds corridor load, no WMT for us</span></div>`;
    }
    planRenderBestHistory({ok:false,error:'Road-only path — adds congestion, no WMT for us, so there is no tonnage history to compare.'});
    return;
  }

  if(!m)return blank('Select a source and destination to see the estimate.');
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),c=planContractor(),pay=planPayload(key,c);
  let dt,trips,wmt,e;
  if(_planMode==='wmt'){
    const target=Math.max(0,parseFloat((q('plan-wmt')||{}).value)||0);
    if(!(target>0))return blank('Enter a target tonnage to size the fleet.');
    dt=planDtForWmt(key,planWmtTargetShift(),rain,c,{nLoaders:planBuilderLoaders()});
    if(!dt){
      const ceil=planDtForWmt._lastCeiling;
      return blank(ceil
        ?('Target above this path\u2019s demonstrated ceiling: best ever is ~'+fmtExact(ceil.maxT*planHorizonFactor())+' t/'+planHorizonLabel()+' ('+fmtExact(ceil.cap)+' trips/day). Lower the target or split across paths.')
        :'Could not size a fleet for that target on this path.');
    }
  }else{
    dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
  }
  e=planTripsPerDT(key,dt,rain,c,{nLoaders:planBuilderLoaders()});
  if(!e)return blank('No history for this path yet.');
  trips=dt*e.shift; wmt=trips*pay.tf;
  const swapped=_planMode==='wmt';
  const cFactor=planContractorFactor(c);
  const warns=[];
  const _envW=planDtEnvelope(m);
  if(_envW!=null&&dt>_envW)warns.push(`⚠ ${fmtExact(dt)} DT is beyond the ${fmtExact(_envW)} DT ever observed on this path`);
  if(e.rainDelta<=-.03)warns.push(`☔ rain −${fmtExact(Math.abs(e.rainDelta),2)} Trips/DT`);
  if(e.otherDelta<=-.02)warns.push(`🚚 other (IWIP/Position) traffic above typical −${fmtExact(Math.abs(e.otherDelta),2)} Trips/DT on the shared corridor`);
  if(e.secDelta<=-.02)warns.push(`\u{1F6E3}\uFE0F shared-section load \u2212${fmtExact(Math.abs(e.secDelta),2)} Trips/DT (plan adds ${fmtExact(Math.round(e.secExcess))} DT beyond this path's typical section traffic \u2014 page-1 measured effect)`);
  if(e.wbFactor<1)warns.push(`⚖ weighbridge over capacity − trips capped at ${fmtExact(Math.round(100*e.wbFactor))}% (see interactions below)`);
  const base={src:s,dst:d,contractor:c?c.name:'—',hours,swapped,warns,foreign:false,
    dt,tripsPerDt:e.shift,trips,wmt,payload:pay.tf,payloadSrc:pay.src,model:'local',
    dtMax:planDtEnvelope(m),
    contractorFactor:cFactor};
  _planRenderEstimate(base);                       // stage 1 — instant, local
  planRenderImpacts(key,dt,e,c);                   // WHY panel under the builder
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
        // GUARD (owner 2026-08-12: "200 DT showed 9,993 t, plan table said
        // 5,098 — what happened?"): the trained model's fallback tiers
        // (per-route average, rain-blind) do NOT model fleet size — they
        // multiply avg trips/DT by N trucks, so at N far beyond the observed
        // fleet they extrapolate linearly into fantasy (206 trips on a path
        // whose measured best is ~43/day). The LOCAL path model carries the
        // measured declining-efficiency slope, so beyond the observed DT
        // range the smaller (honest) number wins the headline; the naive
        // figure moves into the warning so the disagreement stays visible.
        const beyond=Number.isFinite(base.dtMax)&&showDt>base.dtMax;
        const naiveHigher=Number.isFinite(p.total_wmt)&&Number.isFinite(base.wmt)&&p.total_wmt>base.wmt*1.15;
        if(!stillSwapped&&beyond&&naiveHigher){
          const warns=(base.warns||[]).concat([
            `📐 Model extrapolated ${fmtExact(Math.round(p.total_wmt))} t at ${fmtExact(showDt)} DT (beyond ${fmtExact(base.dtMax)} DT ever run) — keeping measured ${fmtExact(Math.round(base.wmt))} t (matches plan table)`,
          ]);
          _planRenderEstimate({...base, model:'localfinal', warns, cycle:res.cycle, contractorFactor:cFactor});
          return;
        }
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
// A plan row is one contractor on one path, AND for limonite one origin type
// (TOS vs LD). Same plant (e.g. HUAFEI) can take LIM-TOS and LIM-LD as two
// independent rows — they must not share a draft id, or editing DT on LD
// silently rewrites TOS.
function planLimOtypeOf(r){
  const ot=String((r&&r.otype)||'').trim().toUpperCase();
  return (ot==='LD'||ot==='TOS')?ot:'';
}
function planDraftSlotId(contractor,key,spec){
  const name=contractor||'—';
  if(spec&&spec.foreign)return name+'|'+key+'|road';
  const mat=String((spec&&spec.material)||'').trim().toUpperCase();
  const ot=String((spec&&spec.otype)||'').trim().toUpperCase();
  if(mat==='LIM'&&(ot==='TOS'||ot==='LD'))return name+'|'+key+'|LIM|'+ot;
  return name+'|'+key;
}
function planMoveDraftId(from,to){
  if(!from||!to||from===to)return false;
  if(typeof _planDraft==='undefined'||!_planDraft[from])return false;
  if(_planDraft[to])return false;
  _planDraft[to]=_planDraft[from];
  delete _planDraft[from];
  if(typeof planWbRekey==='function')planWbRekey(from,to);
  return true;
}
function planMigrateLimIds(){
  if(typeof _planDraft==='undefined')return;
  Object.keys(_planDraft).forEach(id=>{
    const r=_planDraft[id];
    if(!r||r.foreign||!r.key)return;
    const mat=String(r.material||'').trim().toUpperCase();
    if(mat!=='LIM')return;
    let ot=planLimOtypeOf(r);
    if(!ot)return;
    r.otype=ot;
    const want=planDraftSlotId(r.contractor,r.key,{material:'LIM',otype:ot});
    if(want!==id)planMoveDraftId(id,want);
  });
}
function planApplyMaterial(id,code,otype){
  const r=(typeof _planDraft!=='undefined')&&_planDraft[id];
  if(!r)return false;
  const mat=String(code||'').trim().toUpperCase();
  r.material=mat;
  if(mat==='LIM')r.otype=(String(otype||'').toUpperCase()==='LD')?'LD':'TOS';
  else if(mat==='SAP')r.otype='TOS';
  else r.otype='';
  const want=planDraftSlotId(r.contractor,r.key,{material:r.material,otype:r.otype,foreign:!!r.foreign});
  if(want===id)return true;
  if(_planDraft[want])return false;
  return planMoveDraftId(id,want);
}
function planAddPath(){
  const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value,key=s+'>'+d;
  if(!s||!d)return;
  const foreign=planForeignOn();
  // WBN production rows need path-response history; road-only uses measured otherPaths.
  if(!foreign&&!(_pathResp&&_pathResp[key]))return;
  const btn=document.querySelector('.plan-add');
  if(btn){btn.classList.add('is-busy');btn.disabled=true;}

  if(foreign){
    const name=planNormalizeForeignContractor((q('plan-contractor')||{}).value);
    const fp=planForeignPath(name,s,d);
    if(!fp){
      const b=q('plan-preview');
      if(b)b.innerHTML='<span class="er">No measured road-only path for that contractor / locations.</span>';
      if(btn){btn.classList.remove('is-busy');btn.disabled=false;}
      return;
    }
    const dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||1);
    // |road suffix keeps foreign rows separate from production on the same route.
    _planDraft[name+'|'+key+'|road']={key,dt,loaders:planBuilderLoaders(),contractor:name,source:s,dest:d,foreign:true,
      material:((q('plan-material')||{}).value||'').trim(),
      measTrips:Math.max(0,Math.round(fp.trips||0)),
      measTrucks:Math.max(1,Math.round(fp.trucks||1))};
    computePlan();
    setTimeout(()=>{if(btn){btn.classList.remove('is-busy');btn.disabled=false;}},320);
    return;
  }

  const c=planContractor(),name=c?c.name:'—',rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  let dt;
  if(_planMode==='wmt'){
    dt=planDtForWmt(key,planWmtTargetShift(),rain,c,{nLoaders:planBuilderLoaders()});
    if(!dt){
      const b=q('plan-preview');if(b)b.innerHTML='<span class="er">Could not size a fleet for that target on this path.</span>';
      if(btn){btn.classList.remove('is-busy');btn.disabled=false;}
      return;
    }
  }else dt=Math.max(1,parseFloat((q('plan-dt')||{}).value)||50);
  const matAdd=((q('plan-material')||{}).value||'').trim();
  const otRaw=((q('plan-otype')||{}).value||'TOS').toUpperCase();
  const otAdd=matAdd==='LIM'?(otRaw==='LD'?'LD':'TOS'):(matAdd==='SAP'?'TOS':'');
  const id=planDraftSlotId(name,key,{material:matAdd,otype:otAdd});
  const row={key,dt,loaders:planBuilderLoaders(),contractor:name,source:s,dest:d,foreign:false,
    material:matAdd,otype:otAdd};
  if(_planDraft[id]){
    _planDraft[id].dt=dt;
    _planDraft[id].loaders=planBuilderLoaders();
    _planDraft[id].material=matAdd;
    if(otAdd)_planDraft[id].otype=otAdd;
  }else{
    const bare=name+'|'+key;
    const existing=_planDraft[bare];
    if(existing&&!existing.foreign&&matAdd==='LIM'&&(otAdd==='TOS'||otAdd==='LD')){
      const exMat=String(existing.material||'').toUpperCase();
      const exOt=planLimOtypeOf(existing)||(exMat==='LIM'?'TOS':'');
      if(exMat==='LIM'&&exOt===otAdd){
        existing.otype=otAdd;
        planMoveDraftId(bare,id);
        if(_planDraft[id]){
          _planDraft[id].dt=dt;
          _planDraft[id].loaders=planBuilderLoaders();
        }
      }else if(exMat==='LIM'&&exOt&&exOt!==otAdd){
        const otherId=planDraftSlotId(name,key,{material:'LIM',otype:exOt});
        existing.otype=exOt;
        planMoveDraftId(bare,otherId);
        _planDraft[id]=row;
      }else{
        _planDraft[id]=row;
      }
    }else{
      _planDraft[id]=row;
    }
  }
  computePlan();
  // Brief busy flash so “Add to plan” feels acknowledged while tables refresh
  setTimeout(()=>{if(btn){btn.classList.remove('is-busy');btn.disabled=false;}},320);
}
function planRemove(id){delete _planDraft[id];computePlan();}
function planSet(id,v){const r=_planDraft[id];if(r){r.dt=Math.max(0,parseFloat(v)||0);computePlan();}}
/** Stable colour per loading source so holding-plan rows are easy to scan. */
const PLAN_SRC_COLOURS={
  TF:'#38bdf8',KR:'#f59e0b',BLB:'#a78bfa',CSW:'#22c55e',EOS:'#f472b6',LOYPOLOY:'#2dd4bf',
  POS:'#fb923c','POS 10':'#eab308','POS 11':'#f43f5e','POS 12':'#84cc16','POS 14':'#818cf8',
  'POS CBB':'#34d399','POS CUU':'#c084fc'
};
const PLAN_SRC_FALLBACK=['#fb923c','#eab308','#f43f5e','#84cc16','#818cf8','#34d399','#c084fc'];
function planSrcColour(src){
  const k=String(src||'').trim().toUpperCase();
  if(PLAN_SRC_COLOURS[k])return PLAN_SRC_COLOURS[k];
  let h=0;for(let i=0;i<k.length;i++)h=(h*31+k.charCodeAt(i))>>>0;
  return PLAN_SRC_FALLBACK[h%PLAN_SRC_FALLBACK.length]||'#94a3b8';
}
function planHoldSrc(r){
  return String((r&&r.source)||(r&&r.key||'').split('>')[0]||'').trim();
}
/** Material is a label only — never a model input. Click the tag to change it. */
function planHoldMatHtml(id){
  const r=_planDraft[id];
  const code=String((r&&r.material)||'').trim();
  const ot=planLimOtypeOf(r);
  const name=(typeof planMaterialLabel==='function'&&code)?planMaterialLabel(code):code;
  if(!code){
    return `<span class="plan-mat-tag plan-mat-tag--empty" data-matid="${escH(id)}" title="Material is a label only — click to set">Set</span>`;
  }
  const extra=(code==='LIM'&&ot)?' · '+ot:'';
  const cls=code==='LIM'&&ot==='LD'?' plan-mat-tag--ld':code==='LIM'&&ot==='TOS'?' plan-mat-tag--tos':'';
  const tip=code==='LIM'&&ot
    ?(ot==='LD'?'Limonite from LD — separate from LIM-TOS on this plant · click to change'
      :'Limonite from TOS — separate from LIM-LD on this plant · click to change')
    :(escH(name||code)+' — label only, does not change tonnes · click to change');
  return `<span class="plan-mat-tag${cls}" data-matid="${escH(id)}" title="${escH(tip)}">${escH(code)}${extra}</span>`;
}
/** View filter for Your plan: '' = all origins. Does not change the holding plan or predicted WMT. */
let _planHoldOrigin='';
function planHoldOriginSet(src){
  _planHoldOrigin=String(src||'').trim();
  computePlan();
}
function computePlan(){
  const rows=q('plan-rows');if(!rows)return;
  if(typeof planMigrateLimIds==='function')planMigrateLimIds();
  planEnsureDraftLoaders();
  const idsNow=Object.keys(_planDraft||{});
  if(idsNow.length&&typeof planPaintHero==='function')planPaintHero({calculating:true});
  planPreview();
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),wb=Math.max(1,parseFloat((q('plan-wb')||{}).value)||8),
    hours=Math.max(1,parseFloat((q('plan-hours')||{}).value)||12),ids=Object.keys(_planDraft),scope=q('plan-scope'),foot=q('plan-foot');
  const legend=q('plan-src-legend');
  if(!ids.length){rows.innerHTML='<tr><td colspan="9" class="muted plan-hold-empty">No paths yet. Pick a haul above and add it.</td></tr>';
    if(foot)foot.innerHTML='';const pk=q('plan-kpis');if(pk)pk.innerHTML='';const pw=q('plan-warn');if(pw)pw.innerHTML='';if(scope)scope.textContent='';
    if(legend){legend.innerHTML='';legend.hidden=true;}
    _planHoldOrigin='';
    if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
    if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
    if(typeof planRenderComingDays==='function')planRenderComingDays();
    return;}
  let totTrips=0,totWmt=0,totDt=0,beyond=false,hasForeign=false;
  let visTrips=0,visWmt=0,visDt=0,visLd=0,visN=0,totLd=0;
  const hz=planHorizonFactor();
  const srcsAll=[...new Set(ids.map(id=>planHoldSrc(_planDraft[id])).filter(Boolean))];
  if(_planHoldOrigin&&srcsAll.indexOf(_planHoldOrigin)<0)_planHoldOrigin='';
  const dtIn=id=>`<input type="number" min="0" step="1" value="${Math.round(_planDraft[id].dt)}" onchange="planSet('${escH(id)}',this.value)" class="plan-hold-dt" aria-label="Dump trucks" title="Dump trucks on this path">`;
  const ldIn=id=>`<input type="number" min="1" step="1" value="${planNLoaders(_planDraft[id])}" onchange="planLoaderEdit('${escH(id)}',this.value)" class="plan-hold-dt plan-hold-ld" aria-label="Loaders" title="Loaders serving this path">`;
  const rm=id=>`<a class="plan-hold-rm" onclick="planRemove('${escH(id)}')" title="Remove path" role="button">\u2715</a>`;
  const holdTr=(id,extra,pathHtml,tripsHtml,wmtHtml,e)=>{
    const r=_planDraft[id],src=planHoldSrc(r),col=planSrcColour(src);
    const cls=['plan-hold-src',extra].filter(Boolean).join(' ');
    return `<tr class="${cls}" style="--src:${col}" title="Source ${escH(src)}"><td class="plan-hold-path"><span class="plan-hold-dot" aria-hidden="true"></span>${pathHtml}</td><td><span class="plan-hold-co">${escH(r.contractor)}</span></td><td class="plan-hold-mat">${planHoldMatHtml(id)}</td><td class="r plan-hold-dt-cell">${dtIn(id)}</td><td class="r plan-hold-dt-cell">${ldIn(id)}</td><td class="r plan-hold-num">${tripsHtml}</td><td class="r plan-hold-wmt">${wmtHtml}</td><td class="r plan-cong-cell">${planCongCell(e)}</td><td class="c">${rm(id)}</td></tr>`;
  };
  rows.innerHTML=ids.map(id=>{const r=_planDraft[id],m=_pathResp[r.key];
    const path=`<b>${escH(r.key.replace('>',' \u2192 '))}</b>`;
    const show=!_planHoldOrigin||planHoldSrc(r)===_planHoldOrigin;
    if(r.foreign)hasForeign=true;
    totLd+=planNLoaders(r);
    if(!m&&r.foreign&&Number.isFinite(r.measTrips)){
      if(!show)return '';
      visN+=1;visDt+=r.dt;visLd+=planNLoaders(r);
      const rate=r.measTrucks?r.measTrips/r.measTrucks:0,ftrips=r.dt*rate*hz;
      return holdTr(id,'plan-hold-road',path+' <span class="plan-hold-tag" title="Road-only: congestion, no WMT">road</span>',fmtExact(Math.round(ftrips)),'<span class="muted">\u2014</span>',null);
    }
    if(!m)return '';
    const c=planContractor(r.contractor),e=planTripsPerDT(r.key,r.dt,rain,c,planTripOpts(id)),pay=planPayload(r.key,c);
    if(!e)return '';
    const env=planDtEnvelope(m);
    if(Number.isFinite(env)&&r.dt>env)beyond=true;
    const trips=r.dt*e.shift*hz,wmt=trips*pay.tf;
    if(r.foreign){
      if(!show)return '';
      visN+=1;visDt+=r.dt;visLd+=planNLoaders(r);
      return holdTr(id,'plan-hold-road',path+' <span class="plan-hold-tag" title="Road-only: congestion, no WMT">road</span>',fmtExact(Math.round(trips)),'<span class="muted">\u2014</span>',e);
    }
    totTrips+=trips;totWmt+=wmt;totDt+=r.dt;
    if(!show)return '';
    visN+=1;visTrips+=trips;visWmt+=wmt;visDt+=r.dt;visLd+=planNLoaders(r);
    return holdTr(id,'',path,fmtExact(Math.round(trips)),fmtExact(Math.round(wmt))+' t',e);
  }).join('');
  // Road-only / unmatched rows also honour the origin filter (they returned
  // holdTr already). If the filter hid everything, say so.
  if(_planHoldOrigin&&!visN&&!rows.querySelector('tr.plan-hold-src')){
    rows.innerHTML=`<tr><td colspan="9" class="muted">No paths from ${escH(_planHoldOrigin)} — pick All or another origin</td></tr>`;
  }
  if(legend){
    legend.hidden=!srcsAll.length;
    const allOn=!_planHoldOrigin;
    legend.innerHTML=`<button type="button" class="plan-src-chip${allOn?' on':''}" onclick="planHoldOriginSet('')">All</button>`
      +srcsAll.map(s=>{
        const col=planSrcColour(s),on=_planHoldOrigin===s;
        return `<button type="button" class="plan-src-chip${on?' on':''}" style="--src:${col}" onclick="planHoldOriginSet('${escH(s)}')"><i></i>${escH(s)}</button>`;
      }).join('');
  }
  const footN=_planHoldOrigin?visN:ids.length;
  const footDt=_planHoldOrigin?visDt:totDt;
  const footLd=_planHoldOrigin?visLd:totLd;
  const footTr=_planHoldOrigin?visTrips:totTrips;
  const footWmt=_planHoldOrigin?visWmt:totWmt;
  const footLab=_planHoldOrigin?(_planHoldOrigin+(hz>1?' · day':'')):'TOTAL'+(hz>1?' · day':'');
  if(foot)foot.innerHTML=`<tr class="plan-total-row"><td><b>${escH(footLab)}</b></td><td class="muted">${footN}</td><td></td><td class="r"><b>${fmtExact(Math.round(footDt))}</b></td><td class="r"><b>${fmtExact(Math.round(footLd))}</b></td><td class="r"><b>${fmtExact(Math.round(footTr))}</b></td><td class="r"><b>${fmtExact(Math.round(footWmt))} t</b></td><td></td><td></td></tr>`;
  const names=[...new Set(ids.map(id=>_planDraft[id].contractor))];
  const mats=[...new Set(ids.map(id=>(_planDraft[id].material||'').trim()).filter(Boolean))];
  const otherN=Math.round(_planOtherTrips||0);
  const viewTxt=_planHoldOrigin?` · showing ${_planHoldOrigin} (${visN} of ${ids.length})`:'';
  if(scope)scope.textContent=`${ids.length} path${ids.length===1?'':'s'} \u00b7 ${names.join(', ')}${mats.length?` \u00b7 ${mats.join(', ')}`:''} \u00b7 per ${planHorizonLabel()}`+viewTxt+(otherN>0?` \u00b7 +${fmtExact(otherN)} other`:'');
  const avgTf=totTrips?totWmt/totTrips:0;
  planRenderWbLoad(totTrips/hz,wb,hours,avgTf);
  const pw=q('plan-warn');if(pw)pw.innerHTML='';
  if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
  if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
  const status=beyond?'Beyond observed DT':'Within measured fleet';
  const paint=()=>planPaintHero({wmt:totWmt,trips:totTrips,dt:totDt,status});
  clearTimeout(_planHeroCalcTimer);
  _planHeroCalcTimer=setTimeout(paint,160);
  if(typeof planRenderComingDays==='function')planRenderComingDays();
  planLimitsMaybeOpen(hasForeign||(_planOtherTrips||0)>0);
}



