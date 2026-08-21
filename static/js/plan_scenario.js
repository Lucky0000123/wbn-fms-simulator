// plan_scenario.js — Plan tab Step 2: one holding plan (_planDraft) drives
// Production Simulator estimates + Shift Road illustration side-by-side.
// Achievable tonnes always come from /api/simulate — never particle counts.

const PLAN_FLOW_COLOURS=['#38bdf8','#f59e0b','#a78bfa','#22c55e','#f472b6','#2dd4bf','#fb923c','#eab308'];

function planDraftEntries(){
  return Object.keys(_planDraft||{}).map(id=>{
    const r=_planDraft[id],parts=(r.key||'').split('>');
    return {id,...r,source:(r.source||parts[0]||'').trim(),dest:(r.dest||parts[1]||'').trim()};
  }).filter(r=>r.key&&r.dt>0);
}

function planDraftToPsPlans(){
  // Aggregate by route (engine has no contractor). Sum DT when two contractors share a path.
  // Road-only / foreign rows stay a SEPARATE entry (keyed with a |road suffix) and carry
  // foreign:true, so the engine keeps them out of production and applies their corridor drag.
  // After Allocate, Your plan keeps the original DT; simulate the optimized fleet.
  const frozen=typeof planAllocFrozen==='function'&&planAllocFrozen();
  const by={};
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||!r.key)return;
    const dt=Math.round((frozen&&r._allocDt!=null)?r._allocDt:r.dt);
    if(!(dt>0))return;
    const parts=(r.key||'').split('>');
    const source=(r.source||parts[0]||'').trim();
    const dest=(r.dest||parts[1]||'').trim();
    const foreign=!!r.foreign,gk=source+'>'+dest+(foreign?'|road':'');
    const g=by[gk]||(by[gk]={route:source+'>'+dest,source:source,destination:dest,n_trucks:0,n_loaders:null,foreign});
    g.n_trucks+=dt;
    const ld=typeof planNLoaders==='function'?planNLoaders(r):(r.loaders||2);
    g.n_loaders=g.n_loaders==null?ld:Math.max(g.n_loaders,ld);
  });
  return Object.values(by).filter(p=>p.n_trucks>0).map(p=>{
    if(!(p.n_loaders>0))p.n_loaders=2;
    return p;
  });
}

function planDraftToFlowSeed(){
  // Synthetic single-day path rows so Shift Road needs no 3D date.
  const frozen=typeof planAllocFrozen==='function'&&planAllocFrozen();
  const by={},colours={};
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||!r.key)return;
    const dt=(frozen&&r._allocDt!=null)?r._allocDt:r.dt;
    if(!(dt>0))return;
    const g=by[r.key]||(by[r.key]={key:r.key,dt:0});
    g.dt+=dt;
  });
  const P=Object.values(by).map((g,i)=>{
    const [o,d]=g.key.split('>'),m=(_pathResp&&_pathResp[g.key])||{};
    const tr=Number.isFinite(m.avgTr)?m.avgTr:2;
    const sf=typeof planShiftFactor==='function'?planShiftFactor():0.5;
    colours[g.key]=PLAN_FLOW_COLOURS[i%PLAN_FLOW_COLOURS.length];
    return {
      date:'plan',pathKey:g.key,label:(o||'')+' → '+(d||''),
      path:g.dt,section:g.dt,tr,trips:g.dt*tr,wmt:g.dt*tr*(m.tf||0),
      shiftTr:tr*sf,shiftTrips:g.dt*tr*sf,shiftExplicit:true,
    };
  });
  const draft={};P.forEach(p=>{draft[p.pathKey]=Math.round(p.path);});
  return {P,colours,draft};
}

function planPredictTotals(){
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  let trips=0,wmt=0,dt=0;
  planDraftEntries().forEach(r=>{
    // Road-only rows (user IWIP paths, POS-transit IWIP) are not our fleet
    // and move no WMT for us. Older road-only rows dodged this sum only
    // because their routes were outside the path model; POS→FeNi is not.
    if(r.foreign)return;
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,typeof planTripOpts==='function'?planTripOpts(r.id):{selfId:r.id,nLoaders:r.loaders||2}):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
    if(!e)return;
    const t=r.dt*e.shift;trips+=t;wmt+=t*(pay.tf||0);dt+=r.dt;
  });
  return {trips,wmt,dt};
}

function planWeatherForSimulate(){
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  return rain>=1?'wet':'dry';
}

function planSyncWeatherToPs(){
  const w=q('ps-weather');
  if(w)w.value=planWeatherForSimulate();
}

function planSetScenarioBtn(){
  if(typeof planAllocFrozen==='function'&&planAllocFrozen()){
    if(typeof planLockCapacityBtn==='function')planLockCapacityBtn();
    return;
  }
  const btn=q('plan-run-scenario');
  if(!btn)return;
  btn.hidden=false;
  const n=planDraftEntries().length;
  btn.disabled=n<1;
  btn.title=n<1?'Add at least one path first':'Check loader / point ceilings against predicted production (GPS ▶ Run opens road crowding)';
  const note=q('plan-run-locked');
  if(note)note.hidden=true;
}

/** Hide C · road crowding until the user presses ▶ Run on the GPS corridor. */
function planHideRoadIllustration(){
  _planRoadIllustReady=false;
  const illust=q('plan-s2-illust');
  if(illust){illust.style.display='none';illust.hidden=true;}
  const hint=q('plan-corridor-hint');
  if(hint)hint.style.display='';
  const box=q('plan-road-crowding');
  if(box)box.innerHTML='';
  _planSharedFlow=null;
}

function planSetIllustBusy(on){
  const el=q('plan-illust-busy');
  if(el)el.classList.toggle('is-busy',!!on);
}

/**
 * Called when Plan host starts ▶ Run on the GPS corridor.
 * Reveals C and times THIS PLAN's road occupancy by hour (+ IWIP option).
 */
function planOnCorridorRun(){
  const illust=q('plan-s2-illust');
  if(illust){illust.hidden=false;illust.style.display='';}
  const hint=q('plan-corridor-hint');
  if(hint)hint.style.display='none';
  if(_planRoadIllustReady){
    return planFetchRoadCrowding();
  }
  planSetIllustBusy(true);
  return planFetchRoadCrowding().then(()=>{
    _planRoadIllustReady=true;
    if(_planLastSim)planRenderOutcomes(_planLastSim,planPredictTotals());
    if(illust&&typeof illust.scrollIntoView==='function'){
      try{illust.scrollIntoView({behavior:'smooth',block:'nearest'});}
      catch(_){illust.scrollIntoView(true);}
    }
  }).finally(()=>{planSetIllustBusy(false);});
}

function planSeedFlowAnimation(){
  const seed=planDraftToFlowSeed();
  if(!seed.P.length)return false;
  flowSetHost('plan');
  const frozen=typeof planAllocFrozen==='function'&&planAllocFrozen();
  const head=document.querySelector('#plan-c3-flow .c3-flow-head h3');
  if(head)head.textContent=frozen?'Optimized plan on GPS corridor':'Holding plan on GPS corridor';
  _flowPointScenario={date:'plan',label:frozen?'Optimized plan':'Holding plan',path:0,section:0,tr:0,pointIndex:null};
  _flowPlanDraft=seed.draft;
  _flowFleetAvailable=null;
  _flowSpeedsInitialised=false;
  renderFlowSimulator(seed.P,seed.colours);
  // Force planned DT after render (render may re-init draft from dbDt).
  // dbDt is overwritten below from path-response avgDt so the badge reads as
  // plan illustration vs historical average, not a fake "dispatch" day.
  if(_flowSim){
    _flowSim.routes.forEach(r=>{
      if(Number.isFinite(seed.draft[r.key])){
        r.dt=seed.draft[r.key];
        // Keep dbDt as historical avg so mode stays "plan" when they differ.
        if(Number.isFinite((_pathResp[r.key]||{}).avgDt))r.dbDt=_pathResp[r.key].avgDt;
      }
    });
    flowDeriveMode();
    evaluateFlowScenario();
  }
  return true;
}

function planPredictByRoute(){
  /** Path-model WMT / trips / DT aggregated by route (source>dest). */
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  const by={};
  planDraftEntries().forEach(r=>{
    const route=r.source+'>'+r.dest;
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,typeof planTripOpts==='function'?planTripOpts(r.id):{selfId:r.id,nLoaders:r.loaders||2}):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
    const g=by[route]||(by[route]={dt:0,trips:0,wmt:0});
    g.dt+=r.dt;
    if(e){
      const t=r.dt*e.shift;
      g.trips+=t;
      g.wmt+=t*(pay.tf||0);
    }
  });
  return by;
}

function planCapStatusBadge(note){
  const s=String(note||'');
  if(/OVER CAPACITY/i.test(s))return{cls:'over',label:'Over capacity'};
  if(/road-only|foreign/i.test(s))return{cls:'road',label:'Road-only'};
  if(/under|headroom|ok|within|comfortable/i.test(s))return{cls:'ok',label:'OK'};
  const head=(s.split(':')[0]||'').trim();
  return{cls:'muted',label:head||'—'};
}
/** Collapse duplicate OVER CAPACITY lines (same loader/ceiling, different route tonnes). */
function planCapWarnCards(warnings){
  const raw=(warnings||[]).map(w=>typeof w==='string'?w:(w&&w.message)||String(w||''));
  const groups=new Map();
  const other=[];
  raw.forEach(t=>{
    const m=String(t).match(/OVER CAPACITY:\s*(\S+)\s+is asked for\s+([\d.,]+)\s+trips\/shift against a demonstrated ceiling of\s+([\d.,]+)\s*\((\d+)%\)[^.]*\.\s*Excess trucks will queue;\s*~?([\d.,]+)\s*t of the planned\s*([\d.,]+)/i);
    if(!m){if(t)other.push(t);return;}
    const loader=m[1],asked=+String(m[2]).replace(/,/g,''),ceiling=+String(m[3]).replace(/,/g,''),
      pct=+m[4],lost=+String(m[5]).replace(/,/g,''),planned=+String(m[6]).replace(/,/g,'');
    const key=loader+'|'+asked+'|'+ceiling;
    const g=groups.get(key)||{loader,asked,ceiling,pct,lost:0,planned:0};
    g.lost+=lost;g.planned+=planned;groups.set(key,g);
  });
  return{overs:[...groups.values()],other};
}

function planMaterialsForRoute(route){
  const want=String(route||'').trim();
  const seen=[];
  planDraftEntries().forEach(r=>{
    if(r.foreign)return;
    const key=((r.source&&r.dest)?(r.source+'>'+r.dest):r.key)||'';
    if(key!==want&&r.key!==want)return;
    const m=String(r.material||'').trim();
    if(m&&seen.indexOf(m)<0)seen.push(m);
  });
  return seen;
}

function planMaterialChips(codes){
  if(!codes||!codes.length)return '<span class="muted">—</span>';
  return codes.map(c=>{
    const name=(typeof planMaterialLabel==='function')?planMaterialLabel(c):c;
    return `<span class="plan-mat-tag" title="${escH(name||c)} — label only, does not change tonnes">${escH(c)}</span>`;
  }).join(' ');
}
function planCapMatSummary(){
  const seen=[];
  planDraftEntries().forEach(r=>{
    if(r.foreign)return;
    const m=String(r.material||'').trim();
    if(m&&seen.indexOf(m)<0)seen.push(m);
  });
  if(!seen.length)return '';
  return ` · ${seen.map(c=>escH(c)).join(' · ')}`;
}

function planCapPaintTarget(){
  // After ⚡ Allocate, the original Check-capacity card stays frozen and the
  // new run paints underneath it. Do not rewrite #plan-scenario-estimate.
  if(typeof window.planAllocFrozen==='function'&&window.planAllocFrozen()){
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='';
    return q('plan-alloc-estimate')||q('plan-scenario-estimate');
  }
  return q('plan-scenario-estimate');
}

function planRenderEstimateColumn(sim,predict){
  if(typeof window.planAllocFrozen==='function'&&window.planAllocFrozen()
     &&typeof window.planRenderAllocView==='function'){
    window.planRenderAllocView(sim,predict);
    return;
  }
  const box=planCapPaintTarget();if(!box)return;
  const s=(sim&&sim.summary)||{};
  // "Planned" = Step‑1 path-model WMT (what the holding plan asks for).
  // Simulate's planned_production_t often equals achievable when under loader
  // capacity — that is not the user's plan tonnes.
  const plannedPathRaw=predict&&Number.isFinite(predict.wmt)?predict.wmt:null;
  const achvRaw=s.achievable_production_t;
  const hz=typeof planHorizonFactor==='function'?planHorizonFactor():1;
  const hzLab=typeof planHorizonLabel==='function'?planHorizonLabel():'shift';
  const plannedPath=plannedPathRaw!=null?plannedPathRaw*hz:null;
  const achv=achvRaw!=null?achvRaw*hz:null;
  const ratio=(plannedPathRaw>0&&achvRaw!=null)?achvRaw/plannedPathRaw:null;
  const warnings=(s.capacity_warnings||sim.warnings||[]);
  const rows=(sim&&sim.results)||[];
  const byRoute=planPredictByRoute();
  const fmtN=n=>n==null?'—':Math.round(n).toLocaleString('en-GB');
  const gap=(achv!=null&&plannedPath!=null)?Math.round(plannedPath-achv):null;
  // Beyond the observed fleet the engine's cycle has NO crowding term — its
  // achievable is a linear extrapolation, not a capacity fact. Mark it.
  const beyondRows=rows.filter(r=>{
    const mm=(_pathResp&&_pathResp[(r.route||'').trim()])||{};
    const env=typeof planDtEnvelope==='function'?planDtEnvelope(mm):mm.dtMax;
    return Number.isFinite(env)&&r.n_trucks>env;
  });
  const beyondEnv=beyondRows.length>0;
  const achvLabel=beyondEnv?'Achievable · extrapolated':'Achievable';
  // Two DIFFERENT gaps, and the label must not conflate them:
  //  - capacity clipping: simulate-unconstrained > achievable (a loader ceiling
  //    actually removed tonnes) — a real physical constraint;
  //  - model disagreement: path model (Step-1 history) vs the engine, with NO
  //    capacity binding. Calling that "above capacity" blamed loaders for a
  //    modelling difference and confused planners after Optimize.
  const unconADJ=s.planned_production_t!=null?s.planned_production_t*hz:null;
  const capClip=(s.planned_production_t!=null&&achvRaw!=null)?Math.round((s.planned_production_t-achvRaw)*hz):null;
  const gapLabel=gap==null?'—'
    :(capClip!=null&&capClip>200?`Clips ${fmtN(capClip)} t`
    :(gap>200?`Path +${fmtN(gap)} t`
    :(gap<-200?`Path −${fmtN(Math.abs(gap))} t`:'≈ matched')));
  const gapTip=gap==null?''
    :(capClip!=null&&capClip>200?'Loader/point ceiling removed tonnes from unconstrained simulate'
    :(gap>200?'Path model above engine — models differ, no capacity limit binding'
    :(gap<-200?'Path model below engine':'Path model ≈ engine')));
  const fin=_planOptFinalized
    ?`<p class="plan-b-finalized" role="status">Finalized · accepted DT (${fmtN(s.total_trucks)} DT · predicted ${fmtN(plannedPath)} t)</p>`
    :'';

  const routeRows=rows.length?rows.map(r=>{
    if(r.error){
      return `<tr class="plan-cap-row plan-cap-row--err"><td class="plan-cap-route">${escH(r.route)}</td><td colspan="5" class="muted">${escH(r.error)}</td></tr>`;
    }
    const pmRaw=(byRoute[r.route]&&byRoute[r.route].wmt)!=null?byRoute[r.route].wmt:null;
    const pm=pmRaw!=null?pmRaw*hz:null;
    const badge=planCapStatusBadge(r.capacity_note);
    const mm=(_pathResp&&_pathResp[(r.route||'').trim()])||{};
    const env=typeof planDtEnvelope==='function'?planDtEnvelope(mm):mm.dtMax;
    const beyond=Number.isFinite(env)&&r.n_trucks>env;
    const routeLabel=escH(String(r.route||'').replace('>',' → '));
    const achvRow=r.achievable_production_t!=null?r.achievable_production_t*hz:null;
    const mats=planMaterialsForRoute(r.route);
    return `<tr class="plan-cap-row${beyond?' plan-cap-row--beyond':''}${badge.cls==='over'?' plan-cap-row--over':''}">
      <td class="plan-cap-route"><b>${routeLabel}</b>${beyond?`<span class="plan-cap-mini" title="Fleet above measured history">beyond data</span>`:''}</td>
      <td class="plan-cap-mat">${planMaterialChips(mats)}</td>
      <td class="r plan-cap-num">${fmtN(r.n_trucks)}</td>
      <td class="r plan-cap-num">${fmtN(pm)}</td>
      <td class="r plan-cap-num">${fmtN(achvRow)}</td>
      <td><span class="plan-cap-badge plan-cap-badge--${badge.cls}" title="${escH(r.capacity_note||'')}">${escH(badge.label)}</span></td>
    </tr>`;
  }).join(''):'<tr><td colspan="6" class="muted">No simulate rows</td></tr>';

  const beyondHtml=beyondEnv
    ?`<div class="plan-cap-callout plan-cap-callout--amber" role="status">
        <div class="plan-cap-callout-h">Outside measured fleet</div>
        <div class="plan-cap-chips">${beyondRows.map(r=>{
          const mm=(_pathResp&&_pathResp[(r.route||'').trim()])||{};
          const env=typeof planDtEnvelope==='function'?planDtEnvelope(mm):mm.dtMax;
          return `<span class="plan-cap-chip"><b>${escH(String(r.route||'').replace('>',' → '))}</b> ${fmtN(r.n_trucks)} DT · max seen ${fmtN(env)}</span>`;
        }).join('')}</div>
        <p class="plan-cap-callout-p">Engine achievable ignores crowding at this scale — use <b>predicted</b> tonnes for planning.</p>
      </div>`
    :'';

  const parsed=planCapWarnCards(warnings);
  const overHtml=parsed.overs.length
    ?`<div class="plan-cap-callout plan-cap-callout--bad" role="status">
        <div class="plan-cap-callout-h">Loader over capacity</div>
        <div class="plan-cap-over-list">${parsed.overs.map(g=>`
          <div class="plan-cap-over-row">
            <div class="plan-cap-over-main"><b>${escH(g.loader)}</b>
              <span class="plan-cap-over-meta">${fmtN(g.asked*hz)} trips asked · ceiling ${fmtN(g.ceiling*hz)} · ${fmtN(g.pct)}%</span>
            </div>
            <div class="plan-cap-over-lost"><b>−${fmtN(g.lost*hz)} t</b><span>won’t materialise</span></div>
          </div>`).join('')}</div>
        <p class="plan-cap-callout-p">Excess trucks queue at the loader — plan below the ceiling.</p>
      </div>`
    :'';
  const otherWarn=parsed.other.length
    ?`<ul class="plan-cap-other">${parsed.other.map(t=>`<li>${escH(t)}</li>`).join('')}</ul>`
    :'';

  box.innerHTML=`
    <div class="plan-engine-block plan-cap-block">
      ${fin}
      <div class="plan-cap-horizon muted">Totals for one <b>${escH(hzLab)}</b>${hz>1?' (2 × 12 h shifts)':''}${planCapMatSummary()}</div>
      <div class="plan-scenario-kpis plan-cap-kpis">
        <div class="effkpi plan-cap-kpi"><div class="v">${fmtN(s.total_trucks)}</div><div class="l">Trucks</div></div>
        <div class="effkpi plan-cap-kpi"><div class="v">${fmtN(plannedPath)}</div><div class="l">Predicted t</div></div>
        <div class="effkpi plan-cap-kpi"><div class="v">${fmtN(achv)}</div><div class="l">${achvLabel}</div></div>
        <div class="effkpi plan-cap-kpi"><div class="v">${ratio!=null?Math.round(100*ratio)+'%':'—'}</div><div class="l">Achievable / predicted</div></div>
        <div class="effkpi plan-cap-kpi" title="Cycle × payload before loader share"><div class="v">${fmtN(unconADJ)}</div><div class="l">Engine unconstrained t</div></div>
        <div class="effkpi plan-cap-kpi" title="${escH(gapTip)}"><div class="v plan-cap-kpi-gap">${escH(gapLabel)}</div><div class="l">Model vs capacity</div></div>
      </div>
      <div class="plan-cap-table-wrap">
        <table class="plan-cap-table">
          <thead><tr>
            <th>Route</th><th>Material</th><th class="r">DT</th><th class="r">Predicted</th><th class="r">Achievable</th><th>Status</th>
          </tr></thead>
          <tbody>${routeRows}</tbody>
        </table>
      </div>
      ${beyondHtml}
      ${overHtml}
      ${otherWarn}
      <div class="plan-cap-legend">
        <span><b>Predicted</b> · measured path history</span>
        <span><b>Achievable</b> · loader / point capacity</span>
        <span><b>Engine unconstrained</b> · cycle × payload before share</span>
      </div>
    </div>`;
  const heroStatus=beyondEnv?'Beyond observed DT'
    :(capClip!=null&&capClip>200)?'Loader ceiling'
    :'Within measured fleet';
  const predTrips=predict&&Number.isFinite(predict.trips)?predict.trips*hz:null;
  if(typeof planPaintHero==='function'){
    planPaintHero({wmt:plannedPath,trips:predTrips,dt:s.total_trucks,achv,status:heroStatus});
  }
}

let _planScenarioBusy=false,_planLastSim=null,_planLastAnalogues=null;
/** Monotonic run id — drop paint from superseded in-flight simulate responses. */
let _planScenarioGen=0;
/** Latest opts waiting to run after the current calculate finishes (coalesced). */
let _planScenarioQueued=null;
let _planLastSuggestions=null; // [{id,key,currentDt,suggestedDt,reason,changed}]
let _planDaySegments=null;     // click-through for one GPS-window analogue day
let _planDaySegmentsDate=null;
// Kept for the e2e contract: gates assert the payload's basis flags. Legacy
// _planCongestionAdvice removed with the old road-illustration block.
let _planSharedFlow=null;      // /api/plan/shared-flow payload (crowding source)
let _planRoadIllustReady=false; // C · road crowding loaded after GPS ▶ Run
/** Per-path optimize choice: id → 'suggested' | 'current'. */
let _planOptChoice={};
/** After user finalizes keep/apply (all or per-row) — B reflects that plan. */
let _planOptFinalized=false;
/** Frozen Optimize rows after Finalize — do not re-suggest until unlock. */
let _planOptLockedRows=null; // [{id,key,label,contractor,finalDt,note}]

const PLAN_NODE_KM={
  TF:67.8,TOFU:67.8,BLB:67.8,KR:39,KRENE:39,
  'POS 12':27,POS12:27,'POS 10':17,POS10:17,
  'FENI KM15':15,'FENI 15':15,'FENI KM0':0,'FENI 0':0,HUAFEI:0,BSE:0,CRUSHER:3,
};
const PLAN_SECTIONS=[['TOFU–KR',39,67.8],['KR–POS 12',27,39],['POS 12–POS 10',17,27],['POS 10–FENI',0,17]];

function planNodeKm(name){
  const n=String(name||'').trim().toUpperCase().replace(/\s+/g,' ');
  if(PLAN_NODE_KM[n]!=null)return PLAN_NODE_KM[n];
  if(n.indexOf('FENI')===0)return n.indexOf('15')>=0?15:0;
  if(n.indexOf('POS')===0&&n.indexOf('12')>=0)return 27;
  if(n.indexOf('POS')===0&&n.indexOf('10')>=0)return 17;
  if(n==='KR'||n.indexOf('KRENE')===0)return 39;
  if(n==='TF'||n.indexOf('TOFU')===0)return 67.8;
  return null;
}

function planRouteSections(src,dst){
  const a=planNodeKm(src),b=planNodeKm(dst);
  if(a==null||b==null||a===b)return [];
  const lo=Math.min(a,b),hi=Math.max(a,b);
  return PLAN_SECTIONS.filter(([,slo,shi])=>!(shi<=lo||slo>=hi)).map(x=>x[0]);
}
let _planSavedExists=false;

function planRouteShortfallMap(sim){
  const map={};
  ((sim&&sim.results)||[]).forEach(r=>{
    if(!r||r.error||!r.route)return;
    const pl=r.planned_production_t||0,ac=r.achievable_production_t||0;
    const cr=r.capacity_ratio;
    const short=pl>0&&ac<pl*0.98;
    // Headroom = asked below measured loader ceiling (simulate clears planned).
    const headroom=cr!=null&&Number.isFinite(cr)?cr<0.95:!short;
    map[r.route]={
      planned:pl,achievable:ac,short,headroom,
      capacity_ratio:cr!=null&&Number.isFinite(cr)?cr:null,
      note:r.capacity_note||'',
      trucks:r.n_trucks,roster:r.trucks_to_roster,
    };
  });
  return map;
}

function planAmbitionLabel(predict,ensemble){
  const histMed=ensemble&&ensemble.wmt_med,histHi=ensemble&&ensemble.wmt_p75;
  const histLo=ensemble&&ensemble.wmt_p25;
  if(!Number.isFinite(histMed)||!Number.isFinite(predict.wmt)){
    return {label:'—',cls:'',detail:'No history band yet'};
  }
  if(Number.isFinite(histHi)&&predict.wmt>histHi){
    return {label:'Ambitious vs history',cls:'plan-ambition-high',detail:'Path model above P75'};
  }
  if(Number.isFinite(histLo)&&predict.wmt<histLo){
    return {label:'Below history band',cls:'plan-ambition-low',detail:'Path model below P25'};
  }
  if(predict.wmt>=histMed)return {label:'Upper history band',cls:'plan-ambition-mid',detail:'Path model ≥ median'};
  return {label:'Within history',cls:'plan-ambition-ok',detail:'Path model inside P25–P75'};
}

/**
 * DT suggestions from capacity + history (not road V/C tonnes).
 * - Loader shortfall → keep DT
 * - Under loader capacity AND plan light vs history/simulate → raise suggested DT
 * - Overfleeted + ambitious → light trim
 * Road V/C never changes simulate tonnes; only light FENI trim when overfleeted.
 */
function planSuggestOptimize(sim,predict){
  const shortMap=planRouteShortfallMap(sim);
  const ens=(_planLastAnalogues&&_planLastAnalogues.ensemble)||{};
  const vc=_flowSim&&Number.isFinite(_flowSim.vc)?_flowSim.vc:null;
  const planWmt=Number(predict&&predict.wmt)||0;
  const achv=Number((sim&&sim.summary&&sim.summary.achievable_production_t)||0);
  const ambitious=Number.isFinite(ens.wmt_p75)&&planWmt>ens.wmt_p75;
  const belowHist=Number.isFinite(ens.wmt_p25)&&planWmt>0&&planWmt<ens.wmt_p25;
  // Simulate achievable above path-model plan → headroom the plan is not using.
  const simAbovePlan=achv>0&&planWmt>0&&achv>planWmt*1.02;
  const rows=[];
  planDraftEntries().forEach(r=>{
    const cur=Math.max(1,Math.round(r.dt));
    let sug=cur;
    const reasons=[];
    const route=r.source+'>'+r.dest;
    const cap=shortMap[route];
    const m=(_pathResp&&_pathResp[r.key])||{};
    const avgDt=Number.isFinite(m.avgDt)?Math.max(1,Math.round(m.avgDt)):null;
    const destU=(r.dest||'').toUpperCase();
    const feniBound=destU.indexOf('FENI')>=0;
    const cr=cap&&cap.capacity_ratio!=null?cap.capacity_ratio:null;
    const pct=cr!=null?Math.round(100*cr)+'%':'—';

    // GUARD (owner 2026-08-12, 800 DT test): beyond the observed DT range the
    // simulate engine has no truck-crowding term (constant cycle × N trucks),
    // so its "achievable" inflates and this suggester advised RAISING an
    // already-absurd fleet (800 → 937). Beyond dtMax the only honest advice
    // is DOWN toward the observed envelope — never up.
    const dtMax=typeof planDtEnvelope==='function'?planDtEnvelope(m):(Number.isFinite(m.dtMax)?Math.max(1,Math.round(m.dtMax)):null);
    if(dtMax!=null&&cur>dtMax){
      sug=dtMax;
      reasons.push('Beyond the '+dtMax+' DT ever observed on this path — the engine\u2019s cycle assumes no crowding out here, so its headroom is not real. Suggest the observed maximum; raise only with site evidence.');
      rows.push({id:r.id,key:r.key,contractor:r.contractor,
        label:r.key.replace('>',' \u2192 '),currentDt:cur,suggestedDt:sug,
        reason:reasons.join(' '),changed:sug!==cur});
      return;
    }

    if(cap&&cap.short){
      reasons.push('Simulate below planned — keep DT (loader/point ceiling)');
    }else if(cap&&cap.headroom){
      const roomToRaise=(belowHist||simAbovePlan)&&(cr==null||cr<0.9);
      if(roomToRaise){
        let target=cur;
        if(avgDt!=null&&cur<avgDt){
          target=avgDt; // step toward typical fleet first
        }else if(simAbovePlan&&planWmt>0){
          // Close part of the path-model ↔ simulate gap (cap +40% this pass).
          const scale=Math.min(1.4,Math.sqrt(achv/planWmt));
          target=Math.ceil(cur*scale);
        }else{
          target=Math.ceil(cur*1.12);
        }
        if(cr!=null&&cr>0.05){
          // Stay under ~90% of measured loader ceiling if demand scales ~linear with DT.
          const maxDt=Math.max(cur,Math.floor(cur*0.9/cr));
          target=Math.min(target,maxDt);
        }
        target=Math.min(target,Math.ceil(cur*1.4));
        if(target>cur){
          sug=target;
          reasons.push(
            belowHist
              ?('Plan below history P25 · under loader ('+pct+') — raise DT')
              :('Simulate capacity above path model · under loader ('+pct+') — raise DT')
          );
        }else{
          reasons.push('Under loader capacity ('+pct+') — DT already near ceiling-safe target');
        }
      }else{
        reasons.push(
          cr!=null
            ?('Under loader capacity ('+pct+' of ceiling) — keep DT')
            :'Under loader capacity — keep DT'
        );
        // Only trim when clearly overfleeted on a saturated FENI haul.
        if(vc!=null&&vc>=1&&feniBound&&avgDt!=null&&cur>avgDt*1.25){
          const cut=Math.max(avgDt,Math.ceil(sug*0.92));
          if(cut<sug){
            sug=cut;
            reasons.unshift('High road V/C + well above typical DT — light FENI trim');
          }
        }
      }
    }else{
      if(vc!=null&&vc>=1&&feniBound&&sug>1){
        const cut=Math.max(1,Math.ceil(sug*0.9));
        if(cut<sug){sug=cut;reasons.push('High road V/C — light trim on FENI-bound haul');}
      }
      if(ambitious&&avgDt!=null&&cur>avgDt*1.15&&sug===cur){
        sug=Math.max(avgDt,Math.ceil(cur*0.9));
        if(sug<cur)reasons.push('Path model above history P75 — optional trim');
      }
      if(!reasons.length){
        if(cr!=null&&cr>=0.95)reasons.push('Near loader ceiling ('+pct+') — keep DT');
        else reasons.push('Keep DT — no capacity raise/trim needed');
      }
    }
    sug=Math.max(1,Math.round(sug));
    rows.push({
      id:r.id,key:r.key,contractor:r.contractor||'',label:(r.source||'')+' → '+(r.dest||''),
      currentDt:cur,suggestedDt:sug,reason:reasons[0]||'Keep DT',changed:sug!==cur,
    });
  });
  return rows;
}

function planPredictTotalsForDraft(draftObj){
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  let trips=0,wmt=0,dt=0;
  Object.keys(draftObj||{}).forEach(id=>{
    const r=draftObj[id];if(!r||!(r.dt>0)||!r.key)return;
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,typeof planTripOpts==='function'?planTripOpts(id):{selfId:id,nLoaders:r.loaders||2}):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
    if(!e)return;
    const t=r.dt*e.shift;trips+=t;wmt+=t*(pay.tf||0);dt+=r.dt;
  });
  return {trips,wmt,dt};
}

/**
 * Ticket-calibrated companion (raw ÷ 1.055). ONE implementation on purpose —
 * callers pass the summary they are rendering rather than re-deriving the
 * divisor, so the A · Production & capacity panel and anything else cannot
 * drift apart on what "calibrated" means.
 * @param summary optional /api/simulate summary; defaults to the last run.
 */
function planBiasAdjustedAchievable(raw,summary){
  const el=q('plan-bias-lens');
  const on=(typeof _planBiasLensOn!=='undefined'?_planBiasLensOn:true) || !!(el&&el.checked);
  // Prefer server companion when present (same ÷1.055)
  const s=summary||(_planLastSim&&_planLastSim.summary);
  const cal=s&&s.ticket_calibrated_achievable_t;
  if(!on||raw==null||!Number.isFinite(Number(raw)))return {raw,adj:raw,on:false};
  const adj=(cal!=null&&Number.isFinite(Number(cal)))?Number(cal):(Number(raw)/1.055);
  return {raw:Number(raw),adj,on:true};
}

function planCaptureOptLock(){
  /** Snapshot holding-plan DT after Finalize — Optimize must not re-suggest until unlock. */
  return planDraftEntries().filter(r=>!r.foreign).map(r=>({
    id:r.id,
    key:r.key,
    label:(r.source||'')+' → '+(r.dest||''),
    contractor:r.contractor||'',
    finalDt:Math.max(0,Math.round(r.dt)),
    note:'Locked in Production & capacity',
  }));
}

function planUnlockOptimize(){
  _planOptFinalized=false;
  _planOptLockedRows=null;
  _planOptChoice={};
  if(_planLastSim)planRenderOutcomes(_planLastSim,planPredictTotals());
}

function planRenderOutcomes(sim,predict){
  // A · Shift outcomes UI removed (2026-08-12) — capacity lives in A · Production & capacity.
  const box=q('plan-scenario-outcomes');if(!box)return;
  const s=(sim&&sim.summary)||{};
  const achv=s.achievable_production_t||0;
  // Capacity “planned” = THE ENGINE's planned_production_t. Achievable = raw simulate
  // (same figure as B). Ticket lens (−5.5%) is companion-only — never replace the
  // primary Achievable KPI.
  //
  // 2026-08-12 — this card used to divide by predict.wmt (the Step 1 path model), which
  // made it lie in exactly the regime it exists to warn about. At 1360 DT on TF the
  // engine clips 16,012 t and raises two capacity_warnings (1478 trips asked against a
  // demonstrated 1140/shift ceiling), yet the card read "Shortfall 0 t · vs planned
  // 120%". The path model declines sub-linearly with DT while the engine's planned grows
  // linearly, so the ratio IMPROVED as the plan got more absurd. A capacity card must be
  // denominated in the engine's own planned tonnage; the path-model comparison already
  // has its own home in the REALISM card below. See AGENTS.md, the availability override
  // (J55): the UI must not overrule the engine.
  const plannedEngine=s.planned_production_t||0;
  const plannedPath=(predict&&Number.isFinite(predict.wmt)&&predict.wmt>0)?predict.wmt:null;
  const capWarn=s.capacity_warnings||[];
  const lens=planBiasAdjustedAchievable(achv);
  const showAchv=achv; // always match B · Production & capacity
  const ratio=plannedEngine>0?showAchv/plannedEngine:1;
  const vc=_flowSim&&Number.isFinite(_flowSim.vc)?_flowSim.vc:null;
  // No max(0,…) clamp: a clamped difference cannot report that it went negative, which
  // is how the 0 t read survived. Engine achievable is planned-minus-clipping, so this
  // is >= 0 in normal operation; a negative here is a real inconsistency worth seeing.
  const shortfall=plannedEngine-showAchv;
  const planned=plannedEngine;
  const ens=(_planLastAnalogues&&_planLastAnalogues.ensemble)||{};
  const ambition=planAmbitionLabel(predict,ens);

  // After Finalize: freeze Optimize. Re-running suggest would turn accepted DT into
  // "current" and invent another Suggested step — confusing and not final.
  const locked=!!_planOptFinalized;
  if(locked&&(!_planOptLockedRows||!_planOptLockedRows.length)){
    _planOptLockedRows=planCaptureOptLock();
  }
  let suggestions,nChange,nAccept,afterPred,beforeDt,afterDt,sugRows,optStatus,optHead,optTableHead,optActions;
  if(locked){
    const rows=_planOptLockedRows||planCaptureOptLock();
    _planLastSuggestions=rows.map(r=>({
      id:r.id,key:r.key,contractor:r.contractor,label:r.label,
      currentDt:r.finalDt,suggestedDt:r.finalDt,reason:r.note,changed:false,
    }));
    suggestions=_planLastSuggestions;
    nChange=0;nAccept=0;
    beforeDt=Math.round(predict.dt||0);
    afterDt=beforeDt;
    afterPred=predict;
    sugRows=rows.map(r=>`<tr class="plan-sug-locked">
      <td><b>${escH(r.label)}</b><div class="muted" style="font-size:10px">${escH(r.contractor)}</div></td>
      <td class="r"><b>${r.finalDt}</b></td>
      <td class="muted" style="font-size:11px">${escH(r.note)}</td>
      <td class="plan-sug-x-cell"><span class="plan-sug-locked-mark" title="Finalized">✓</span></td>
    </tr>`).join('');
    optStatus='Finalized — Optimize is locked. Production &amp; capacity uses this DT. Re-open only if you want a new suggestion pass.';
    optHead=`Locked · ${beforeDt} DT · path WMT ${planFmtN(predict.wmt)} t · achievable ${planFmtN(achv)} t`;
    optTableHead=`<tr><th>Path</th><th class="r">Final DT</th><th>Status</th><th class="c">Locked</th></tr>`;
    optActions=`
      <button class="ms-btn" type="button" id="plan-unlock-opt" onclick="planUnlockOptimize()" title="Clear lock and regenerate Optimize suggestions from the current plan">Re-open optimize</button>
      <button class="ms-btn" type="button" onclick="planOpenFullAssessment()">Open full assessment</button>`;
  }else{
    suggestions=planSuggestOptimize(sim,predict);
    _planLastSuggestions=suggestions;
    // Default: accept suggested DT on every changed path. ✕ opts out (keep current).
    suggestions.forEach(x=>{
      if(!x.changed)_planOptChoice[x.id]='current';
      else if(_planOptChoice[x.id]!=='current')_planOptChoice[x.id]='suggested';
    });
    nChange=suggestions.filter(x=>x.changed).length;
    nAccept=suggestions.filter(x=>x.changed&&_planOptChoice[x.id]==='suggested').length;
    const afterDraft={};
    suggestions.forEach(x=>{
      const src=(_planDraft&&_planDraft[x.id])||{};
      const useSug=x.changed&&_planOptChoice[x.id]!=='current';
      afterDraft[x.id]={...src,dt:useSug?x.suggestedDt:x.currentDt,key:x.key};
    });
    afterPred=planPredictTotalsForDraft(afterDraft);
    beforeDt=Math.round(predict.dt||0);
    afterDt=Math.round(afterPred.dt||0);
    sugRows=suggestions.map(x=>{
      const accepted=x.changed&&_planOptChoice[x.id]!=='current';
      const tip=accepted
        ?('Will apply suggested '+x.suggestedDt+' DT — click to keep '+x.currentDt)
        :('Keeping '+x.currentDt+' DT — click to apply suggested '+x.suggestedDt);
      // Single-quoted onclick so JSON.stringify's double quotes (path ids like TF>FENI KM0) do not break HTML.
      const act=x.changed
        ?`<button type="button" class="plan-sug-x ${accepted?'on':''}" title="${escH(tip)}"
            onclick='planToggleSuggestionRow(${JSON.stringify(String(x.id))})' aria-pressed="${accepted?'true':'false'}">${accepted?'✓':'✕'}</button>`
        :`<span class="muted plan-sug-ok">—</span>`;
      return `<tr class="${x.changed?'plan-sug-changed':''}${accepted?' plan-sug-picked':''}">
        <td><b>${escH(x.label)}</b><div class="muted" style="font-size:10px">${escH(x.contractor)}</div></td>
        <td class="r">${x.currentDt}</td>
        <td class="r">${x.suggestedDt}</td>
        <td class="muted" style="font-size:11px">${escH(x.reason)}</td>
        <td class="plan-sug-x-cell">${act}</td>
      </tr>`;
    }).join('');
    optStatus=nChange
      ?`Finalize applies suggested DT on ${nAccept}/${nChange} path(s). Click ✓/✕ only to exclude a path (keep current).`
      :'No DT change suggested — Finalize to lock this plan into Production &amp; capacity.';
    optHead=`${nChange?nChange+' path(s) with a suggestion':'No DT change'} · selected ${beforeDt} → ${afterDt} DT · path WMT ${planFmtN(predict.wmt)} → ${planFmtN(afterPred.wmt)} t · achievable ${planFmtN(achv)} t`;
    optTableHead=`<tr><th>Path</th><th class="r">Current DT</th><th class="r">Suggested DT</th><th>Reason</th><th class="c">Accept</th></tr>`;
    optActions=`
      <button class="btn" type="button" id="plan-finalize-opt" onclick="planFinalizeOptimize()" title="Apply accepted suggestions and lock Optimize; refresh Production &amp; capacity">Finalize plan → refresh Production and capacity</button>
      <button class="ms-btn" type="button" onclick="planOpenFullAssessment()">Open full assessment</button>`;
  }

  // Any path beyond its observed DT max: the engine's achievable is an
  // extrapolation with no crowding term — say so instead of praising headroom.
  const beyondEnv=planDraftEntries().some(r=>{
    const mm=(_pathResp&&_pathResp[r.key])||{};
    const env2=typeof planDtEnvelope==='function'?planDtEnvelope(mm):mm.dtMax;
    return Number.isFinite(env2)&&r.dt>env2;
  });
  const status=beyondEnv?'Fleet beyond observed range — engine capacity untested out here'
    :ratio<0.85?'Simulate shortfall — capacity limiting'
    :ratio<0.98?'Simulate below planned — review loaders'
    :(ambition.cls==='plan-ambition-low')?'Under history — capacity headroom to raise DT'
    :(ambition.cls==='plan-ambition-high')?'Capacity OK — ambitious vs history'
    :(vc!=null&&vc>=1)?'High road load — tonnes still from simulate'
    :'Plan clears simulate capacity';
  const statusIcon=beyondEnv||ratio<0.98||ambition.cls==='plan-ambition-low'||ambition.cls==='plan-ambition-high'||(vc!=null&&vc>=1)?'🟠':'🟢';

  const planWmt=Math.round(predict.wmt||0);
  const p25=ens.wmt_p25,p75=ens.wmt_p75;
  const histBand=(p25!=null&&p75!=null)
    ?(planFmtN(p25)+'–'+planFmtN(p75)+' t')
    :'—';

  const html=`
    <div class="plan-decision-card">
      <div class="plan-decision-status">${statusIcon} ${escH(status)}</div>

      <div class="plan-signal-grid">
        <div class="plan-signal">
          <div class="plan-signal-h">Capacity <span class="muted">(simulate · effective cycle)</span></div>
          <div class="plan-outcomes-strip plan-outcomes-strip-3">
            <div><span class="muted">Achievable</span><b>${Math.round(showAchv).toLocaleString('en-GB')} t</b></div>
            <div><span class="muted">Shortfall</span><b${shortfall>1?' style="color:var(--bad,#e5534b)"':''}>${Math.round(shortfall).toLocaleString('en-GB')} t</b></div>
            <div><span class="muted">vs planned</span><b>${planned?Math.round(100*ratio)+'%':'—'}</b></div>
          </div>
          ${capWarn.length?`<ul class="plan-cap-warn">${capWarn.map(w=>`<li>${escH(w)}</li>`).join('')}</ul>`:''}
          <p class="muted" style="font-size:10.5px;margin:6px 0 0">Same achievable as B (raw simulate). Planned = engine ${Math.round(plannedEngine).toLocaleString('en-GB')} t — what this fleet moves before point ceilings clip it.${plannedPath!=null?(' Path-model WMT '+Math.round(plannedPath).toLocaleString('en-GB')+' t is the REALISM card, not this one.'):''}${lens.on
            ?(' Ticket lens companion ~'+Math.round(lens.adj).toLocaleString('en-GB')+' t (÷1.055) — not used in these KPIs.')
            :''}</p>
        </div>
        <div class="plan-signal">
          <div class="plan-signal-h">Realism <span class="muted">(path model vs history)</span></div>
          <div class="plan-outcomes-strip plan-outcomes-strip-3 plan-realism-row" role="group" aria-label="Your plan versus history band">
            <div>
              <span class="muted">Your plan</span>
              <b>${planWmt.toLocaleString('en-GB')} t</b>
              <em class="plan-realism-sub">${Math.round(predict.dt||0)} DT · ${Math.round(predict.trips||0)} trips</em>
            </div>
            <div>
              <span class="muted">History P25–P75</span>
              <b>${escH(histBand)}</b>
              <em class="plan-realism-sub">matched days&rsquo; rate × your DT</em>
            </div>
            <div class="${ambition.cls}">
              <span class="muted">Where plan sits</span>
              <b class="plan-realism-verdict">${escH(ambition.label)}</b>
              <em class="plan-realism-sub">${escH(ambition.detail||'')}</em>
            </div>
          </div>
          <p class="muted" style="font-size:10.5px;margin:6px 0 0">One comparison only — do not average with achievable tonnes.</p>
        </div>
      </div>

      <div class="plan-optimize${locked?' plan-optimize-locked':''}">
        <div class="plan-optimize-head">
          <h4>Optimize · DT${locked?' <span class="plan-opt-lock-tag">Locked</span>':''}</h4>
          <span class="muted" style="font-size:11px">${optHead}</span>
        </div>
        <p class="plan-opt-status" id="plan-opt-status" role="status">${optStatus}</p>
        <div class="rain-table plan-optimize-table"><table>
          <thead>${optTableHead}</thead>
          <tbody>${sugRows||'<tr><td colspan="5" class="muted">No paths</td></tr>'}</tbody>
        </table></div>
        <div class="plan-outcome-actions">
          ${optActions}
        </div>
      </div>
    </div>`;
  box.innerHTML=html;
  // (No write to #plan-flow-verdict: it ships display:none and the same status
  // headline already renders inside section A above — writing it was dead code.)
  if(typeof evaluateFlowScenario==='function'&&_flowSim)evaluateFlowScenario();
  if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
}

function planDraftToAnaloguePlans(){
  // Keep contractor (unlike simulate). Aggregate DT per contractor|route.
  // Foreign / road-only rows have no WMT history, so they are not sent to analogues.
  return planDraftEntries().filter(r=>!r.foreign).map(r=>({
    source:r.source,destination:r.dest,n_trucks:Math.round(r.dt),
    n_loaders:typeof planNLoaders==='function'?planNLoaders(r):(r.loaders||2),
    contractor:r.contractor||null,
  })).filter(p=>p.n_trucks>0&&p.source&&p.destination);
}

function planFmtN(n,d){
  if(n==null||!Number.isFinite(Number(n)))return '—';
  const x=Number(n);
  if(d==null)return Math.round(x).toLocaleString('en-GB');
  return x.toLocaleString('en-GB',{maximumFractionDigits:d,minimumFractionDigits:0});
}

// ── C · Road crowding by hour (plan-driven, replaces the old illustration) ──
// One question, answered from THIS plan: at which hours of the shift will each
// haul-road section be crowded? Occupancy comes from /api/plan/shared-flow
// (measured load/dump dwell + Jul+ section speeds + staggered releases) for
// OUR planned trucks; the IWIP toggle adds the measured other-traffic paths
// (foreign rows from the last ticket shift, scaled to the Other-trips input)
// so the corridor shows combined crowding. Advisory only — never touches
// simulate tonnes (basis.congestion_clips_tonnes stays false, J53).
let _planCrowdIncludeIwip=false;   // default OFF (owner, 2026-08-19)
let _planCrowdWholeDay=true;       // full 24 h day = two 12 h shifts
function planCrowdIwipPlans(){
  // Measured IWIP paths (from planFetchOtherTraffic) scaled to the Other-trips
  // input: trips in the box ÷ trips measured that shift. Trucks scale the same
  // way; occupancy needs truck counts, not ticket counts.
  const paths=(typeof _planOtherPaths!=='undefined'?_planOtherPaths:[])||[];
  if(!paths.length)return [];
  const meas=(typeof _planOtherSrcTrips!=='undefined'?_planOtherSrcTrips:0)||0;
  const want=(typeof _planOtherTrips!=='undefined'?_planOtherTrips:0)||0;
  const k=meas>0&&want>0?want/meas:1;
  return paths.map((p,i)=>({
    source:p.origin,destination:p.dest,
    n_trucks:Math.max(1,Math.round((p.trucks||1)*k)),
    contractor:'IWIP',id:'iwip'+i,
  }));
}
function planCrowdToggleIwip(el){
  _planCrowdIncludeIwip=!!(el&&el.checked);
  planFetchRoadCrowding();
}
function planCrowdToggleDay(el){
  _planCrowdWholeDay=!!(el&&el.checked);
  planFetchRoadCrowding();
}
function planFetchRoadCrowding(){
  const plans=planDraftEntries().map(r=>({
    source:r.source,destination:r.dest,n_trucks:Math.round(r.dt||0),
    n_loaders:typeof planNLoaders==='function'?planNLoaders(r):(r.loaders||2),
    contractor:r.contractor||null,id:r.id,
  })).filter(p=>p.n_trucks>0&&p.source&&p.destination);
  const iwip=_planCrowdIncludeIwip?planCrowdIwipPlans():[];
  const box=q('plan-road-crowding');
  if(box&&!box.querySelector('.plan-rc-grid')){
    box.innerHTML='<p class="muted" style="margin:0;font-size:12px">Timing the plan\u2019s road occupancy\u2026</p>';
  }
  const shiftH=parseFloat((q('plan-hours')||{}).value)||12;
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  return fetch('/api/plan/shared-flow',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({plans:plans.concat(iwip),shift_hours:shiftH,rain_mm:rain,start_hour:7,whole_day:_planCrowdWholeDay}),
  }).then(r=>r.json()).then(data=>{
    _planSharedFlow=data;
    planRenderRoadCrowding(data,{nPlan:plans.length,nIwip:iwip.length,nIwipAvail:planCrowdIwipPlans().length});
    return data;
  }).catch(e=>{
    _planSharedFlow=null;
    planRenderRoadCrowding({ok:false,error:String(e)},{nPlan:plans.length,nIwip:iwip.length,nIwipAvail:planCrowdIwipPlans().length});
    return null;
  });
}
function planRenderRoadCrowding(data,meta){
  const box=q('plan-road-crowding');if(!box)return;
  meta=meta||{};
  const iwipChk=`<label class="plan-rc-iwip" title="Full day = two 12 h shifts (07:00 day + 19:00 night), releases re-staggered at the changeover. Untick for the day shift only.">
      <input type="checkbox" ${_planCrowdWholeDay?'checked':''} onchange="planCrowdToggleDay(this)"> whole day (2\u00d712 h)
    </label>
    <label class="plan-rc-iwip" title="Add the measured IWIP/Position trucks (their last-shift paths, scaled to the Other-trips input) to the road occupancy. They share POS 12\u2013FENI with our hauls. Default OFF.">
      <input type="checkbox" ${_planCrowdIncludeIwip?'checked':''} onchange="planCrowdToggleIwip(this)"> include IWIP trucks
      ${meta.nIwipAvail?`<span class="muted">(${meta.nIwipAvail} measured path${meta.nIwipAvail===1?'':'s'})</span>`:'<span class="muted">(no measured paths)</span>'}
    </label>`;
  if(!data||!data.ok){
    box.innerHTML=`<div class="plan-rc-head">${iwipChk}</div>
      <p class="muted" style="margin:6px 0 0;font-size:12px">${escH((data&&data.error)||'Road-crowding timing unavailable')}</p>`;
    return;
  }
  const secs=data.sections||[];
  const startH=Number.isFinite(data.start_hour)?data.start_hour:7;
  const binH=data.bin_hours||1;
  const nBins=Math.max.apply(null,secs.map(s=>(s.occupancy||[]).length).concat([0]));
  // Hour labels across the shift
  const hourLbls=[];
  for(let b=0;b<nBins;b++)hourLbls.push(((startH+Math.round(b*binH))%24));
  // Grid: one row per section, one cell per hour, colour by occupancy/capacity.
  const shiftLen=Math.round((data.shift_hours||12)/binH);
  const rows=secs.map(s=>{
    const cap=s.cap_trucks_bin||1;
    const cells=(s.occupancy||[]).map((c,b)=>{
      const r=cap>0?c/cap:0;
      const cls=r>=1?'rc-high':r>=0.7?'rc-watch':c>0?'rc-open':'rc-idle';
      const night=data.whole_day&&b>=shiftLen?' rc-night':'';
      const edge=data.whole_day&&b===shiftLen?' rc-shift-edge':'';
      const tip=`${escH(s.section)} · ${String(hourLbls[b]).padStart(2,'0')}:00 · ${c} truck${c===1?'':'s'} on section (cap ~${Math.round(cap)}/bin${cap?` · ${Math.round(100*r)}%`:''})${night?' · night shift':''}`;
      return `<div class="rc-cell ${cls}${night}${edge}" title="${tip}">${c>0?c:''}</div>`;
    }).join('');
    const who=(s.plans||[]).join(' · ');
    const shared=s.shared?` <span class="muted">· shared${who.includes('IWIP')?' incl. IWIP':''}</span>`:'';
    return `<div class="rc-row" title="${escH(s.section)} — used by: ${escH(who||'—')}">
      <div class="rc-sec"><b>${escH(s.section)}</b>${shared}</div>
      <div class="rc-cells">${cells}</div>
    </div>`;
  }).join('');
  const axis=`<div class="rc-row rc-axis"><div class="rc-sec"></div><div class="rc-cells">${
    hourLbls.map((h,b)=>`<div class="rc-cell rc-hour${data.whole_day&&b>=shiftLen?' rc-night':''}${data.whole_day&&b===shiftLen?' rc-shift-edge':''}">${String(h).padStart(2,'0')}</div>`).join('')
  }</div></div>`;
  // Verdict: worst crowded hours across sections.
  const chours=data.congestion_hours||[];
  const verdict=chours.length
    ?`\u26a0 Crowded: ${chours.slice(0,4).map(h=>`<b>${escH(h.label)}</b> ${escH((h.sections||[]).join(', '))} (${h.peak_trucks} trucks${h.ratio!=null?` · ${Math.round(100*h.ratio)}%`:''})`).join(' · ')}`
    :`\u2713 No hour reaches 70% of section capacity — releases stay smooth all shift`;
  const iwipNote=meta.nIwip&&_planCrowdIncludeIwip
    ?` · IWIP ${meta.nIwip} path(s) scaled to the Other-trips input`
    :(_planCrowdIncludeIwip?'':' · IWIP excluded (toggle to include)');
  box.innerHTML=`
    <div class="plan-rc-head">
      <span class="plan-rc-verdict">${verdict}</span>
      ${iwipChk}
    </div>
    <div class="plan-rc-grid">${axis}${rows}</div>
    <div class="muted" style="font-size:10.5px;margin-top:6px">
      Trucks on each section per hour \u2014 our ${meta.nPlan||0} plan path(s)${iwipNote}${data.whole_day?' · full day: 07:00 day + 19:00 night shift, releases re-staggered at changeover':''}.
      Cell colour: green &lt;70% of section capacity · amber \u226570% · red \u2265100%.
      Measured load/dump dwell + Jul+ section speeds, staggered releases.
      Advisory only \u2014 never changes simulate tonnes.
    </div>`;
}

function planRenderDaySegments(data,dateS){
  _planDaySegments=data;
  _planDaySegmentsDate=dateS||(data&&data.date)||null;
  const box=q('plan-day-segments');if(!box)return;
  if(!data){
    box.innerHTML='<p class="muted" style="margin:0;font-size:11px">Click a Jul+ analogue row (GPS column) to see where that day was slow.</p>';
    return;
  }
  if(data.has_gps===false){
    const d0=data.date||dateS||'';
    const fleetN0=planAnalogueFleetUpdates(d0).length;
    box.innerHTML=`<h4>Day segments · ${escH(d0)}</h4>
      <p class="muted" style="font-size:11.5px;margin:4px 0 0">${escH(data.note||'No haul GPS for this day.')}</p>
      <div style="margin:8px 0 0">
        <button type="button" class="ms-btn" ${fleetN0?'':'disabled'}
          onclick="planApplyAnalogueFleet('${escH(d0)}')">Use this day's fleet DT</button>
        <span class="muted" style="font-size:10.5px;margin-left:6px">Ops history only — no segment speeds</span>
      </div>`;
    return;
  }
  if(!data.ok){
    box.innerHTML=`<h4>Day segments</h4><p class="muted" style="font-size:11.5px">${escH(data.error||'Unavailable')}</p>`;
    return;
  }
  const bySec=(data.by_section||[]).map(s=>
    `<tr><td><b>${escH(s.section)}</b></td><td class="r">${planFmtN(s.loadedKmh,1)}</td><td class="r">${planFmtN(s.n)}</td></tr>`
  ).join('');
  const segs=(data.segments||[]).slice(0,12).map(s=>
    `<tr><td>${escH(s.seg)}</td><td class="muted">${escH(s.section||'')}</td>
      <td class="r">${planFmtN(s.loadedKmh,1)}</td><td class="r">${planFmtN(s.emptyKmh,1)}</td>
      <td class="r">${planFmtN(s.peak_trucks)}</td></tr>`
  ).join('');
  const fleetN=planAnalogueFleetUpdates(data.date).length;
  box.innerHTML=`
    <h4>Day segments · ${escH(data.date)} <span class="muted">(click another Jul+ row)</span></h4>
    <p class="muted" style="font-size:11px;margin:0 0 6px">${escH(data.note||'')}</p>
    <div style="margin:0 0 8px">
      <button type="button" class="ms-btn" ${fleetN?'':'disabled'}
        onclick="planApplyAnalogueFleet('${escH(data.date)}')"
        title="Copy this day's historical DT onto matching holding-plan paths">Use this day's fleet DT</button>
      <span class="muted" style="font-size:10.5px;margin-left:6px">${fleetN?fleetN+' route match(es)':'no route match in analogues'}</span>
    </div>
    <div class="rain-table plan-insights-table"><table>
      <thead><tr><th>Section</th><th class="r">Loaded km/h</th><th class="r">Segs</th></tr></thead>
      <tbody>${bySec||'<tr><td colspan="3" class="muted">No stick sections</td></tr>'}</tbody>
    </table></div>
    <div class="rain-table plan-insights-table" style="margin-top:8px"><table>
      <thead><tr><th>Segment</th><th>Section</th><th class="r">Loaded</th><th class="r">Empty</th><th class="r">Peak DT</th></tr></thead>
      <tbody>${segs||'<tr><td colspan="5" class="muted">No segment rows</td></tr>'}</tbody>
    </table></div>`;
}

function planFetchDaySegments(dateS){
  const d=String(dateS||'').slice(0,10);
  if(!d)return Promise.resolve(null);
  const box=q('plan-day-segments');
  if(box)box.innerHTML='<p class="muted" style="margin:0;font-size:11px">Loading segments for '+escH(d)+'…</p>';
  return fetch('/api/plan/day-segments?date='+encodeURIComponent(d)).then(r=>r.json()).then(data=>{
    planRenderDaySegments(data,d);
    // highlight selected analogue row
    const rowsEl=q('plan-analogues-rows');
    if(rowsEl){
      [...rowsEl.querySelectorAll('tr')].forEach(tr=>{
        tr.classList.toggle('plan-ana-selected',(tr.getAttribute('data-date')||'')===d);
      });
    }
    return data;
  }).catch(e=>{
    planRenderDaySegments({ok:false,error:String(e),date:d},d);
    return null;
  });
}

function planAnalogueRowClick(dateS,hasGps){
  if(!dateS)return;
  if(!hasGps){
    planRenderDaySegments({
      ok:true,date:dateS,has_gps:false,
      note:'No haul corridor GPS before mid-July — ops-only day; speeds are not invented from Playback.',
    },dateS);
    return;
  }
  planFetchDaySegments(dateS);
}

function planAnalogueFleetUpdates(dateS){
  const data=_planLastAnalogues;if(!data)return [];
  const d=String(dateS||'').slice(0,10);
  const updates=[];
  (data.by_plan||[]).forEach(bp=>{
    const hit=(bp.analogues||[]).find(a=>String(a.date||'').slice(0,10)===d);
    if(!hit||!(hit.dt>0))return;
    updates.push({
      route:bp.route||((bp.source||'')+'>'+(bp.destination||'')),
      source:bp.source,dest:bp.destination,
      contractor:(bp.contractor||hit.contractor||'').toString().toUpperCase()||null,
      dt:Math.max(1,Math.round(Number(hit.dt))),
    });
  });
  if(!updates.length){
    const a=(data.analogues||[]).find(x=>String(x.date||'').slice(0,10)===d);
    if(a&&a.dt>0){
      const route=a.route||'';
      const parts=route.split('>');
      updates.push({
        route,source:parts[0]||a.source,dest:parts[1]||a.destination,
        contractor:(a.contractor||'').toString().toUpperCase()||null,
        dt:Math.max(1,Math.round(Number(a.dt))),
      });
    }
  }
  return updates;
}

function planApplyAnalogueFleet(dateS){
  const updates=planAnalogueFleetUpdates(dateS);
  if(!updates.length){
    alert('No fleet DT on file for '+dateS+' on your routes.');
    return;
  }
  let n=0;
  updates.forEach(u=>{
    planDraftEntries().forEach(r=>{
      const route=(r.source||'')+'>'+(r.dest||'');
      const sameRoute=route===u.route||(r.source===u.source&&r.dest===u.dest);
      if(!sameRoute)return;
      const rc=(r.contractor||'').toString().toUpperCase();
      if(u.contractor&&rc&&rc!==u.contractor)return;
      if(_planDraft[r.id]){_planDraft[r.id].dt=u.dt;n++;}
    });
  });
  if(!n){
    alert('No matching holding-plan paths for that day\'s routes.');
    return;
  }
  if(typeof computePlan==='function')computePlan();
  if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
  const st=q('plan-save-status');
  if(st)st.textContent='Applied '+dateS+' fleet DT to '+n+' path(s) — re-run scenario';
  const box=q('plan-day-segments');
  if(box){
    const note=document.createElement('p');
    note.className='muted';
    note.style.cssText='font-size:11.5px;margin:8px 0 0';
    note.textContent='Applied historical DT from '+dateS+' to '+n+' path(s). Re-run scenario to refresh outcomes.';
    box.appendChild(note);
  }
}

function planRenderAnalogues(data){
  _planLastAnalogues=data;
  const ensBox=q('plan-analogues-ensemble');
  const rowsEl=q('plan-analogues-rows');
  const noteEl=q('plan-analogues-note');
  if(!data||!data.ok){
    if(ensBox)ensBox.innerHTML='';
    if(rowsEl)rowsEl.innerHTML='<tr><td colspan="8" class="muted">'
      +escH((data&&data.error)||'No analogues returned')+'</td></tr>';
    if(noteEl)noteEl.textContent='';
    planRenderRoadInteractions(data);
    planRenderDaySegments(null);
    return;
  }
  const e=data.ensemble||{};
  const predict=planPredictTotals();
  const sim=_planLastSim&&_planLastSim.summary||{};
  const achv=sim.achievable_production_t;
  const histMed=e.wmt_med,histHi=e.wmt_p75;
  // Ambition: where does path-model / simulate sit vs what similar days actually delivered?
  let ambition='—',ambitionCls='';
  if(Number.isFinite(histMed)&&Number.isFinite(predict.wmt)){
    if(predict.wmt>histHi){ambition='Ambitious vs history';ambitionCls='plan-ambition-high';}
    else if(predict.wmt>=histMed){ambition='In upper history band';ambitionCls='plan-ambition-mid';}
    else{ambition='Within / below history median';ambitionCls='plan-ambition-ok';}
  }
  if(ensBox){
    ensBox.innerHTML=`
      <div class="effkpi"><div class="v">${planFmtN(e.wmt_p25)} – ${planFmtN(e.wmt_p75)} t</div><div class="l">History WMT P25–P75</div></div>
      <div class="effkpi"><div class="v">${planFmtN(histMed)} t</div><div class="l">History median</div></div>
      <div class="effkpi"><div class="v">${planFmtN(predict.wmt)} t</div><div class="l">Your predicted</div></div>
      <div class="effkpi"><div class="v">${achv!=null?planFmtN(achv)+' t':'—'}</div><div class="l">Simulate achievable</div></div>
      <div class="effkpi ${ambitionCls}"><div class="v" style="font-size:13px">${escH(ambition)}</div><div class="l">Realism check</div></div>`;
  }
  const rows=data.analogues||[];
  if(rowsEl){
    rowsEl.innerHTML=rows.length?rows.map(a=>{
      const season=a.season||'';
      const spd=a.avg_speed_kmh!=null?planFmtN(a.avg_speed_kmh,1)+' km/h':'—';
      const loc=a.location_note||'';
      const why=escH((a.remark||a.why||'')+(loc&&String(loc).indexOf('haul GPS')>=0?' · '+loc:''));
      const hasGps=!!(a.has_gps||(a.date&&String(a.date)>='2026-07-15'));
      const tip=hasGps?'Click for section speeds that day':'Ops-only — no haul GPS to drill into';
      return `<tr class="plan-ana-click" data-date="${escH(a.date)}" data-has-gps="${hasGps?1:0}"
        onclick="planAnalogueRowClick('${escH(a.date)}',${hasGps?1:0})" title="${escH(tip)}">
        <td><b>${escH(a.date)}</b></td>
        <td>${escH(a.route||'')}</td>
        <td class="plan-season-${escH(season)}">${escH(season)}</td>
        <td class="r">${planFmtN(a.dt,1)}</td>
        <td class="r">${planFmtN(a.trips_per_dt,2)}</td>
        <td class="r">${planFmtN(a.wmt)} t</td>
        <td class="r muted" style="font-size:10.5px" title="${escH(loc)}">${escH(spd)}</td>
        <td class="muted" style="font-size:10.5px">${why}</td>
      </tr>`;
    }).join(''):'<tr><td colspan="8" class="muted">No matching historical days.</td></tr>';
  }
  planRenderDaySegments(null);
  const basis=data.basis||{};
  if(noteEl){
    noteEl.textContent='Corpus: '+(basis.corpus_source||'?')
      +' · '+(basis.corpus_n!=null?basis.corpus_n+' path-days':'')
      +' · k='+(data.k||rows.length)
      +(data.servedFrom==='fms_cache'?' · from FMS cache':'')
      +'. History band is matched days\' trips/DT × planned DT — not similar-fleet tonnes. Separate from simulate.';
  }
  planRenderRoadInteractions(data);
}

function planRenderRoadInteractions(data){
  const sumEl=q('plan-road-summary');
  const rowsEl=q('plan-road-rows');
  const noteEl=q('plan-road-note');
  const sr=(data&&data.shared_road)||{};
  const risk=sr.risk||'none';
  const secs=(sr.shared_sections||[]).join(', ')||'—';
  if(sumEl){
    sumEl.innerHTML=`
      <p style="margin:0 0 6px">
        <span class="plan-risk-badge plan-risk-${escH(risk)}">${escH(sr.risk_label||risk)}</span>
      </p>
      <p class="muted" style="margin:0;font-size:12px">
        Shared sections: <b>${escH(secs)}</b>
        · planned section fleet ~ <b>${planFmtN(sr.plan_dt_total,0)} DT</b>
        · hist peak section DT <b>${planFmtN(sr.max_hist_section_dt,0)}</b>
        ${sr.trips_per_dt_collapse_pct!=null
          ?' · busy vs quiet trips/DT <b>'+planFmtN(sr.trips_per_dt_collapse_pct,1)+'%</b> lower'
          :''}
      </p>`;
  }
  const ev=sr.evidence||[];
  if(rowsEl){
    rowsEl.innerHTML=ev.length?ev.map(e=>`<tr>
        <td><b>${escH(e.date)}</b></td>
        <td class="r">${planFmtN(e.section_dt,1)}</td>
        <td class="r">${planFmtN(e.trips_per_dt,2)}</td>
        <td class="r">${planFmtN(e.routes_overlap)}</td>
        <td class="plan-season-${escH(e.season||'')}">${escH(e.season||'')}</td>
      </tr>`).join(''):'<tr><td colspan="5" class="muted">'
      +escH(sr.note||'No multi-plan corridor evidence for this draft.')+'</td></tr>';
  }
  if(noteEl)noteEl.textContent=sr.note||'';
}

function planFetchAnalogues(){
  const plans=planDraftToAnaloguePlans();
  const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
  const rowsEl=q('plan-analogues-rows');
  if(rowsEl)rowsEl.innerHTML='<tr><td colspan="8" class="muted">Searching similar days…</td></tr>';
  return fetch('/api/plan/analogues',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({plans,rain_mm:rain,k:8}),
  }).then(r=>r.json()).then(data=>{
    planRenderAnalogues(data);
    return data;
  }).catch(e=>{
    planRenderAnalogues({ok:false,error:String(e)});
    return null;
  });
}

/** Busy overlay on A · Production & capacity while simulate recalculates. */
function planSetCalcBusy(on){
  const frozen=typeof window.planAllocFrozen==='function'&&window.planAllocFrozen();
  const el=q(frozen?'plan-alloc-busy':'plan-estimate-busy');
  if(el)el.classList.toggle('is-busy',!!on);
  const orig=q('plan-estimate-busy');
  if(frozen&&orig)orig.classList.remove('is-busy');
  const runBtn=q('plan-run-scenario');
  if(runBtn&&on){runBtn.disabled=true;runBtn.textContent='Running…';}
}

function planDraftFleetDt(plans){
  return (plans||[]).reduce((n,p)=>n+(Number(p.n_trucks)||0),0);
}

/**
 * Run A+B from the current holding plan.
 * If a calculate is already in flight, coalesce a follow-up run instead of
 * silently dropping (that left Finalize applying DT while B stayed stale).
 */
function planRunScenario(opts){
  opts=opts||{};
  if(typeof planAllocFrozen==='function'&&planAllocFrozen()&&!opts.fromAlloc){
    if(typeof planLockCapacityBtn==='function')planLockCapacityBtn();
    return;
  }
  const plans=planDraftToPsPlans();
  const btn=q('plan-run-scenario');
  if(!plans.length){alert('Add at least one path to the holding plan first.');return;}
  if(_planScenarioBusy){
    // Latest draft wins when the in-flight call finishes — do not paint stale sim.
    _planScenarioQueued=Object.assign({},_planScenarioQueued||{},opts);
    const st=q('plan-opt-status');
    if(st)st.textContent='Calculate in progress — will refresh Production & capacity with the latest DT when it finishes…';
    return;
  }
  const gen=++_planScenarioGen;
  const fleetDtSent=planDraftFleetDt(plans);
  _planScenarioBusy=true;
  // New scenario run: re-arm the illustration→assessment auto-trigger so the
  // next completed corridor playback refreshes the assessment for THIS plan.
  if(typeof planArmAssessAuto==='function')planArmAssessAuto();
  planSetCalcBusy(true);
  if(!opts.preserveFinalize){
    _planOptChoice={};
    _planOptFinalized=false;
    _planOptLockedRows=null;
  }
  planHideRoadIllustration();
  if(btn){btn.disabled=true;btn.textContent='Running…';}
  planSyncWeatherToPs();
  const shiftMin=parseFloat((q('ps-shift')||{}).value)||((parseFloat((q('plan-hours')||{}).value)||12)*60);
  const panel=q('plan-scenario-panel');
  if(panel)panel.style.display='block';
  const frozen=typeof window.planAllocFrozen==='function'&&window.planAllocFrozen();
  const est=frozen?q('plan-alloc-estimate'):q('plan-scenario-estimate');
  if(est)est.innerHTML='<p class="muted">Calculating productivity &amp; capacity…</p>';

  // A · Production & capacity here. C · road crowding waits for GPS corridor ▶ Run.
  const simP=fetch('/api/simulate',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({plans,weather:planWeatherForSimulate(),shift_minutes:shiftMin}),
  }).then(r=>r.json());
  const anaP=planFetchAnalogues();

  Promise.all([simP,anaP]).then(([sim])=>{
    // Superseded by a queued Finalize/re-run with newer DT — skip stale paint.
    if(gen!==_planScenarioGen||_planScenarioQueued)return;
    // Draft edited while simulate was in flight — re-run instead of mixing fleets.
    if(planDraftFleetDt(planDraftToPsPlans())!==fleetDtSent){
      _planScenarioQueued=Object.assign({},opts);
      return;
    }
    _planLastSim=sim;
    const s=sim.summary||{};
    const planned=s.planned_production_t||0,achv=s.achievable_production_t||0;
    _flowSimRatio=(planned>0)?Math.max(0,Math.min(1,achv/planned)):1;
    // Always read path-model from live draft (not a closure captured at fetch start).
    const predict=planPredictTotals();
    planRenderEstimateColumn(sim,predict);
    planSeedFlowAnimation();
    if(_planLastAnalogues)planRenderAnalogues(_planLastAnalogues);
    // B · Fleet sensitivity: sweep the SAME path model across DT per plan.
    if(typeof planSensRefresh==='function'){try{planSensRefresh();}catch(_){}}
    const open=q('plan-open-assessment');
    if(open)open.disabled=false;
    planRefreshSaveButtons();
    // Keep viewport on the prediction hero — GPS ▶ Run opens road crowding below.
    const hero=q('plan-sec-predict');
    const jump=hero||est;
    if(jump&&typeof jump.scrollIntoView==='function'){
      try{jump.scrollIntoView({behavior:'smooth',block:'nearest'});}
      catch(_){jump.scrollIntoView(true);}
    }
  }).catch(e=>{
    if(gen!==_planScenarioGen||_planScenarioQueued)return;
    if(est)est.innerHTML='<p class="er">simulate failed: '+escH(String(e))+'</p>';
  }).finally(()=>{
    if(gen!==_planScenarioGen)return;
    _planScenarioBusy=false;
    planSetCalcBusy(false);
    if(typeof planAllocFrozen==='function'&&planAllocFrozen()){
      if(typeof planLockCapacityBtn==='function')planLockCapacityBtn();
    }else if(btn){btn.disabled=false;btn.textContent='Check capacity';}
    planSetScenarioBtn();
    const queued=_planScenarioQueued;
    _planScenarioQueued=null;
    if(queued)planRunScenario(queued);
  });
}

function planOpenFullAssessment(){
  // The full assessment (sections 2-9) now lives INSIDE the Plan tab, under
  // the corridor illustration, and runs on the SAME holding plan. There is no
  // separate Production Simulator page to switch to and no second plan.
  const plans=planDraftToPsPlans();
  if(!plans.length){alert('No holding plan to assess.');return;}
  planSyncWeatherToPs();
  _psPlans=plans.map(p=>({route:p.route,source:p.source,destination:p.destination,n_trucks:p.n_trucks,n_loaders:p.n_loaders||2,foreign:!!p.foreign}));
  // Carry analogue plans (with contractor) for assessment top-k / shared-road panels.
  if(typeof window!=='undefined'){
    window._paAnaloguePlans=planDraftToAnaloguePlans();
    window._paAnalogues=_planLastAnalogues;
  }
  const host=q('plan-assessment-host');
  if(host)host.style.display='';
  const det=q('plan-sec-detail');
  if(det)det.open=true;
  // Host lives inside the scenario panel — reveal that too when the assessment
  // is opened directly (e.g. before any Check capacity click).
  const panel=q('plan-scenario-panel');
  if(panel)panel.style.display='block';
  const busy=q('plan-assessment-busy');
  if(busy)busy.style.display='';
  if(typeof psInit==='function')psInit();
  if(typeof psRun==='function')psRun();
  if(host&&typeof host.scrollIntoView==='function'){
    try{host.scrollIntoView({behavior:'smooth',block:'start'});}catch(_){host.scrollIntoView(true);}
  }
}

/** Staged reveal: when the corridor illustration finishes its 24h clock, the
 * full assessment runs automatically underneath — illustration plays, then
 * "prediction running", then results. Same engine (/api/simulate), same plan. */
let _planAssessAutoDone=false;
function planOnIllustrationFinished(){
  if(_planAssessAutoDone)return;   // once per scenario run; Reset/re-Run re-arms below
  if(!planDraftEntries().length)return;
  _planAssessAutoDone=true;
  planOpenFullAssessment();
}
function planArmAssessAuto(){_planAssessAutoDone=false;}

/** Replace the lexical holding plan (main.js `_planDraft`) and refresh UI. */
function planLoadDraft(obj){
  if(typeof _planDraft==='undefined')return;
  Object.keys(_planDraft).forEach(k=>delete _planDraft[k]);
  Object.assign(_planDraft, obj||{});
  if(typeof planMigrateLimIds==='function')planMigrateLimIds();
  if(typeof computePlan==='function')computePlan();
  else planSetScenarioBtn();
  if(typeof planRefreshSaveButtons==='function')planRefreshSaveButtons();
}

function planToggleSuggestionRow(id){
  if(_planOptFinalized)return; // locked until Re-open optimize
  // ✓ (suggested, default) ↔ ✕ (keep current / opt out)
  const cur=_planOptChoice[id]==='current'?'current':'suggested';
  _planOptChoice[id]=cur==='suggested'?'current':'suggested';
  if(_planLastSim)planRenderOutcomes(_planLastSim,planPredictTotals());
}

/** Apply suggested DT for every changed path unless the user opted out (✕). Then refresh Production & capacity. */
function planFinalizeOptimize(){
  if(typeof _planDraft==='undefined')return;
  if(_planOptFinalized)return; // already locked — use Re-open optimize for another pass
  let applied=0;
  (_planLastSuggestions||[]).forEach(x=>{
    if(!_planDraft[x.id]||!x.changed)return;
    // Default apply suggested; only skip when explicitly opted out to current.
    if(_planOptChoice[x.id]==='current')return;
    _planDraft[x.id].dt=x.suggestedDt;
    _planOptChoice[x.id]='suggested';
    applied++;
  });
  _planOptFinalized=true;
  _planOptLockedRows=planCaptureOptLock();
  if(typeof computePlan==='function')computePlan();
  const st=q('plan-opt-status');
  const waiting=_planScenarioBusy;
  if(st){
    if(waiting){
      st.textContent=applied
        ?('Applied '+applied+' DT change(s) — locking Optimize; B will refresh when calculate finishes…')
        :'DT locked — B will refresh when calculate finishes…';
    }else{
      st.textContent=applied
        ?('Applying '+applied+' suggested DT change(s) — locking Optimize and refreshing Production & capacity…')
        :'Locking this DT into Production & capacity…';
    }
  }
  // Always request a run with the post-accept draft. If busy, this queues and
  // the in-flight (pre-accept) response is discarded so B cannot stick on old DT.
  planRunScenario({preserveFinalize:true});
  setTimeout(()=>{
    const b=q('plan-scenario-estimate');
    if(b&&typeof b.scrollIntoView==='function'){
      try{b.scrollIntoView({behavior:'smooth',block:'nearest'});}
      catch(_){b.scrollIntoView(true);}
    }
  },400);
}

function planDraftSnapshot(){
  const paths={};
  Object.keys(_planDraft||{}).forEach(id=>{
    const r=_planDraft[id];
    if(!r||!r.key)return;
    paths[id]={
      key:r.key,dt:r.dt,loaders:typeof planNLoaders==='function'?planNLoaders(r):(r.loaders||2),
      contractor:r.contractor||'',
      source:r.source||(r.key.split('>')[0]||''),
      dest:r.dest||(r.key.split('>')[1]||''),
      material:r.material||'',
      otype:r.otype||'',
      foreign:!!r.foreign,
    };
  });
  return {
    date:((q('plan-date')||{}).value||'').trim(),
    paths,
    rain_mm:Math.max(0,parseFloat((q('plan-rain')||{}).value)||0),
    hours:parseFloat((q('plan-hours')||{}).value)||12,
    wb:parseFloat((q('plan-wb')||{}).value)||8,
    meta:{
      predict:planPredictTotals(),
      sim_achievable:(_planLastSim&&_planLastSim.summary||{}).achievable_production_t||null,
    },
  };
}

function planRefreshSaveButtons(){
  const date=((q('plan-date')||{}).value||'').trim();
  const n=planDraftEntries().length;
  const saveBtn=q('plan-save-btn'),loadBtn=q('plan-load-btn');
  if(saveBtn){
    saveBtn.disabled=!date||n<1;
    saveBtn.title=!date?'Set a plan date first':(n<1?'Add at least one path':'Save holding plan for '+date);
  }
  if(loadBtn){
    loadBtn.disabled=!date||!_planSavedExists;
    loadBtn.title=_planSavedExists?'Load saved plan for '+date:'No saved plan for this date';
  }
  planNavSync();
}

// ── Sticky plan nav ─────────────────────────────────────────────────────────
// Save/Load live in the sticky bar so they are reachable at any scroll depth.
// Everything here is presentation only: it reads the draft, it never edits it.
function planNavSync(){
  const date=((q('plan-date')||{}).value||'').trim();
  const rows=planDraftEntries();
  // Contractor fleet only — IWIP road-only trucks are a separate fleet
  // (planning_rules.md §10.8) and must not read as allocatable DT.
  const dt=rows.filter(r=>!r.foreign).reduce((a,r)=>a+(+r.dt||0),0);
  const iwip=rows.filter(r=>r.foreign).reduce((a,r)=>a+(+r.dt||0),0);
  const d=q('plan-nav-date'); if(d)d.textContent=date||'no date set';
  const s=q('plan-nav-summary');
  if(s)s.textContent=rows.length
    ? rows.length+' path'+(rows.length===1?'':'s')+' · '+Math.round(dt)+' DT'
      +(iwip>0?' + '+Math.round(iwip)+' IWIP':'')
    : 'no paths yet';
}

function planNavScrollSpy(){
  const bar=q('plan-navbar');if(!bar)return;
  const btns=[].slice.call(document.querySelectorAll('#plan-nav-links button'));
  if(!btns.length)return;
  bar.classList.toggle('stuck',bar.getBoundingClientRect().top<=1);
  // "Current" = the last section whose top is above the bar's lower edge. Using
  // the bar height as the offset stops a section counting as reached while it is
  // still hidden behind the bar itself.
  const cut=bar.getBoundingClientRect().bottom+8;
  const vis=btns.filter(b=>{const el=q(b.getAttribute('data-sec'));
    return el&&el.offsetParent!==null;});           // skip sections not yet shown
  if(!vis.length){btns.forEach(b=>b.classList.remove('on'));return;}
  let cur=vis[0];
  vis.forEach(b=>{if(q(b.getAttribute('data-sec')).getBoundingClientRect().top<=cut)cur=b;});
  // At the bottom of the page the last section IS the current one, even though
  // its top never reaches the bar. Without this, jumping to a section near the
  // end scrolls as far as it can and then highlights the WRONG entry, which
  // reads as a broken link. Bites hardest before Run scenario, when Step 2's
  // sub-blocks are still hidden and the page is short.
  const atEnd=window.innerHeight+window.scrollY>=
    (document.documentElement.scrollHeight||document.body.scrollHeight)-4;
  if(atEnd)cur=vis[vis.length-1];
  btns.forEach(b=>b.classList.toggle('on',b===cur));
}

/** Populate the "Saved…" picker so any stored plan is one click away. */
function planNavRefreshSavedList(){
  const sel=q('plan-saved-pick');if(!sel)return Promise.resolve();
  return fetch('/api/plan/saved/list').then(r=>r.json()).then(d=>{
    const dates=(d&&d.dates)||[];
    const cur=((q('plan-date')||{}).value||'').trim();
    sel.innerHTML='<option value="">Saved… ('+dates.length+')</option>'
      +dates.map(x=>`<option value="${escH(x)}"${x===cur?' selected':''}>${escH(x)}</option>`).join('');
  }).catch(()=>{});
}

/** Jump to a stored plan: set the date, then reuse the existing load path. */
function planOpenSavedDate(date){
  const d=(date||'').trim();if(!d)return;
  const inp=q('plan-date');if(!inp)return;
  inp.value=d;
  // Go through planDateChange() rather than poking dependants directly — it is
  // what re-pulls conditions, analogues and the saved-plan probe for the date.
  if(typeof planDateChange==='function')planDateChange();
  if(typeof planLoadSavedForDate==='function')planLoadSavedForDate();
}

(function planNavInit(){
  const start=()=>{
    const links=q('plan-nav-links');
    if(links)links.addEventListener('click',ev=>{
      const b=ev.target.closest('button[data-sec]');if(!b)return;
      const el=q(b.getAttribute('data-sec'));if(!el)return;
      el.scrollIntoView({behavior:'smooth',block:'start'});
    });
    window.addEventListener('scroll',planNavScrollSpy,{passive:true});
    window.addEventListener('resize',planNavScrollSpy,{passive:true});
    planNavSync();planNavScrollSpy();planNavRefreshSavedList();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);
  else start();
})();

function planCheckSavedExists(date){
  const d=(date||((q('plan-date')||{}).value||'')).trim();
  if(!d){_planSavedExists=false;planRefreshSaveButtons();return Promise.resolve(false);}
  return fetch('/api/plan/saved?date='+encodeURIComponent(d))
    .then(r=>r.json())
    .then(res=>{
      _planSavedExists=!!(res&&res.ok&&res.exists);
      const st=q('plan-save-status');
      if(st){
        if(_planSavedExists)st.textContent='Saved plan on file for '+d;
        else if(!st.textContent||st.textContent.indexOf('Saved')===0||st.textContent.indexOf('No saved')===0)
          st.textContent='';
      }
      planRefreshSaveButtons();
      return _planSavedExists;
    })
    .catch(()=>{_planSavedExists=false;planRefreshSaveButtons();return false;});
}

function planSaveForDate(){
  const snap=planDraftSnapshot();
  if(!snap.date){alert('Set a plan date first.');return;}
  if(!Object.keys(snap.paths).length){alert('Add at least one path before saving.');return;}
  const st=q('plan-save-status');
  if(st)st.textContent='Saving…';
  return fetch('/api/plan/saved',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(snap),
  }).then(r=>r.json()).then(res=>{
    if(!res||!res.ok){alert((res&&res.error)||'Save failed');if(st)st.textContent='Save failed';return;}
    _planSavedExists=true;
    if(st)st.textContent='Saved for '+snap.date+(res.plan&&res.plan.saved_at?' · '+res.plan.saved_at:'');
    planRefreshSaveButtons();
    planNavRefreshSavedList();   // a new date just became loadable
  }).catch(e=>{alert('Save failed: '+e);if(st)st.textContent='Save failed';});
}

function planLoadSavedForDate(opts){
  const quiet=opts&&opts.quiet;
  const date=((q('plan-date')||{}).value||'').trim();
  if(!date){if(!quiet)alert('Set a plan date first.');return Promise.resolve(false);}
  const st=q('plan-save-status');
  if(st&&!quiet)st.textContent='Loading…';
  return fetch('/api/plan/saved?date='+encodeURIComponent(date))
    .then(r=>r.json())
    .then(res=>{
      if(!res||!res.ok||!res.plan||!res.plan.paths){
        _planSavedExists=false;
        if(!quiet)alert('No saved plan for '+date);
        if(st)st.textContent='No saved plan for '+date;
        planRefreshSaveButtons();
        return false;
      }
      _planSavedExists=true;
      const curN=planDraftEntries().length;
      if(curN>0&&!quiet&&!confirm('Replace current holding plan with saved plan for '+date+'?')){
        if(st)st.textContent='Load cancelled';
        return false;
      }
      planLoadDraft(res.plan.paths);
      if(typeof planRestoreAllocation==='function')planRestoreAllocation(res.plan.allocation);
      if(res.plan.rain_mm!=null){
        const rain=q('plan-rain');
        if(rain){rain.value=String(res.plan.rain_mm);if(typeof _planRainManual!=='undefined')_planRainManual=true;}
      }
      if(res.plan.wb!=null){const wb=q('plan-wb');if(wb)wb.value=String(res.plan.wb);}
      if(res.plan.hours!=null){
        // ONE shift-length control: #ps-shift is the only writable source and
        // #plan-hours is its mirror (psSyncShift). Write the SOURCE, then sync,
        // so Step 1 and Step 2 cannot diverge after loading a saved plan.
        const ps=q('ps-shift');
        if(ps)ps.value=String((parseFloat(res.plan.hours)||12)*60);
        if(typeof psSyncShift==='function')psSyncShift();
        else{
          const h=q('plan-hours'),hd=q('plan-hours-display');
          if(h)h.value=String(res.plan.hours);
          if(hd)hd.textContent=String(res.plan.hours);
        }
      }
      if(typeof computePlan==='function')computePlan();
      if(st)st.textContent='Loaded plan for '+date;
      planRefreshSaveButtons();
      return true;
    })
    .catch(e=>{if(!quiet)alert('Load failed: '+e);if(st)st.textContent='Load failed';return false;});
}
