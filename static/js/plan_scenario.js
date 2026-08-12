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
  const by={};
  planDraftEntries().forEach(r=>{
    const foreign=!!r.foreign,gk=r.source+'>'+r.dest+(foreign?'|road':'');
    const g=by[gk]||(by[gk]={route:r.source+'>'+r.dest,source:r.source,destination:r.dest,n_trucks:0,foreign});
    g.n_trucks+=Math.round(r.dt);
  });
  return Object.values(by).filter(p=>p.n_trucks>0);
}

function planDraftToFlowSeed(){
  // Synthetic single-day path rows so Shift Road needs no 3D date.
  const by={},colours={};
  planDraftEntries().forEach(r=>{
    const g=by[r.key]||(by[r.key]={key:r.key,dt:0});
    g.dt+=r.dt;
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
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c):null;
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
  const btn=q('plan-run-scenario');
  if(!btn)return;
  const n=planDraftEntries().length;
  btn.disabled=n<1;
  btn.title=n<1?'Add at least one path in Step 1':'Run simulate for A · outcomes and B · capacity (GPS ▶ Run opens C · road illustration)';
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
  _flowPointScenario={date:'plan',label:'Holding plan',path:0,section:0,tr:0,pointIndex:null};
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
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c):null;
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

function planRenderEstimateColumn(sim,predict){
  const box=q('plan-scenario-estimate');if(!box)return;
  const s=(sim&&sim.summary)||{};
  // "Planned" = Step‑1 path-model WMT (what the holding plan asks for).
  // Simulate's planned_production_t often equals achievable when under loader
  // capacity — that is not the user's plan tonnes.
  const plannedPath=predict&&Number.isFinite(predict.wmt)?predict.wmt:null;
  const achv=s.achievable_production_t;
  const ratio=(plannedPath>0&&achv!=null)?achv/plannedPath:null;
  const warnings=(s.capacity_warnings||sim.warnings||[]);
  const rows=(sim&&sim.results)||[];
  const byRoute=planPredictByRoute();
  const fmtN=n=>n==null?'—':Math.round(n).toLocaleString('en-GB');
  const gap=(achv!=null&&plannedPath!=null)?Math.round(plannedPath-achv):null;
  // Beyond the observed fleet the engine's cycle has NO crowding term — its
  // achievable is a linear extrapolation, not a capacity fact. Mark it.
  const beyondRows=rows.filter(r=>{
    const mm=(_pathResp&&_pathResp[(r.route||'').trim()])||{};
    return Number.isFinite(mm.dtMax)&&r.n_trucks>mm.dtMax;
  });
  const beyondEnv=beyondRows.length>0;
  const achvLabel=beyondEnv?'Achievable (simulate · extrapolated)':'Achievable (simulate)';
  const beyondNote=beyondEnv
    ?`<p class="plan-scenario-warn" style="margin:8px 0 0;font-size:11px;color:#f59e0b">⚠ ${beyondRows.map(r=>{
        const mm=(_pathResp&&_pathResp[(r.route||'').trim()])||{};
        return `${escH(r.route)}: ${r.n_trucks} DT vs ${Math.round(mm.dtMax)} DT ever observed`;
      }).join(' · ')} — the engine assumes cycle time does not degrade with fleet size, so this achievable is untested extrapolation. The path model (with the measured declining-efficiency slope) is the honest planning number out here.</p>`
    :'';
  // Two DIFFERENT gaps, and the label must not conflate them:
  //  - capacity clipping: simulate-unconstrained > achievable (a loader ceiling
  //    actually removed tonnes) — a real physical constraint;
  //  - model disagreement: path model (Step-1 history) vs the engine, with NO
  //    capacity binding. Calling that "above capacity" blamed loaders for a
  //    modelling difference and confused planners after Optimize.
  const unconADJ=s.planned_production_t;
  const capClip=(unconADJ!=null&&achv!=null)?Math.round(unconADJ-achv):null;
  const gapLabel=gap==null?'—'
    :(capClip!=null&&capClip>200?`Capacity clips ${fmtN(capClip)} t (loader ceiling)`
    :(gap>200?`Path model +${fmtN(gap)} t vs engine — models differ, no capacity limit`
    :(gap<-200?`Path model ${fmtN(Math.abs(gap))} t below engine`:'Path model ≈ engine')));
  const fin=_planOptFinalized
    ?`<p class="plan-b-finalized" role="status">Finalized plan · B uses the DT you accepted (${fmtN(s.total_trucks)} DT · path model ${fmtN(plannedPath)} t).</p>`
    :'';
  box.innerHTML=`
    <div class="plan-engine-block">
      ${fin}
      <div class="plan-scenario-kpis">
        <div class="effkpi"><div class="v">${fmtN(s.total_trucks)}</div><div class="l">Trucks (DT)</div></div>
        <div class="effkpi"><div class="v">${fmtN(plannedPath)} t</div><div class="l">Planned (path model)</div></div>
        <div class="effkpi"><div class="v">${fmtN(achv)} t</div><div class="l">${achvLabel}</div></div>
        <div class="effkpi"><div class="v">${ratio!=null?Math.round(100*ratio)+'%':'—'}</div><div class="l">Achievable / planned</div></div>
        <div class="effkpi"><div class="v">${fmtN(s.planned_production_t)} t</div><div class="l">Simulate unconstrained</div></div>
        <div class="effkpi"><div class="v" style="font-size:13px">${escH(gapLabel)}</div><div class="l">Model vs capacity</div></div>
      </div>
      <div class="rain-table" style="margin-top:10px"><table><thead><tr><th>Route</th><th class="r">DT</th><th class="r">Path model t</th><th class="r">Achievable t</th><th>Capacity</th></tr></thead>
      <tbody>${rows.length?rows.map(r=>{
        if(r.error)return `<tr><td>${escH(r.route)}</td><td colspan="4" class="muted">${escH(r.error)}</td></tr>`;
        const pm=(byRoute[r.route]&&byRoute[r.route].wmt)!=null?byRoute[r.route].wmt:null;
        return `<tr><td><b>${escH(r.route)}</b></td><td class="r">${r.n_trucks}</td><td class="r">${fmtN(pm)}</td><td class="r">${fmtN(r.achievable_production_t)}</td><td class="muted" style="font-size:10px">${escH((r.capacity_note||'').split(':')[0])}</td></tr>`;
      }).join(''):'<tr><td colspan="5" class="muted">No simulate rows</td></tr>'}</tbody></table></div>
      ${beyondNote}
      ${warnings.length?`<ul class="plan-scenario-warn">${warnings.map(w=>`<li>${escH(typeof w==='string'?w:(w.message||JSON.stringify(w)))}</li>`).join('')}</ul>`:''}
      <p class="muted" style="font-size:11px;margin:8px 0 0"><b>Planned (path model)</b> is your Step‑1 haul estimate. <b>Achievable</b> is loader/point capacity — trust this for “can we deliver?”. Simulate unconstrained is the engine’s cycle×payload before capacity share (often ≈ achievable when under ceiling).</p>
    </div>`;
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
    const dtMax=Number.isFinite(m.dtMax)?Math.max(1,Math.round(m.dtMax)):null;
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
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
    if(!e)return;
    const t=r.dt*e.shift;trips+=t;wmt+=t*(pay.tf||0);dt+=r.dt;
  });
  return {trips,wmt,dt};
}

function planBiasAdjustedAchievable(raw){
  const el=q('plan-bias-lens');
  const on=(typeof _planBiasLensOn!=='undefined'?_planBiasLensOn:true) || !!(el&&el.checked);
  // Prefer server companion when present (same ÷1.055)
  const cal=_planLastSim&&_planLastSim.summary&&_planLastSim.summary.ticket_calibrated_achievable_t;
  if(!on||raw==null||!Number.isFinite(Number(raw)))return {raw,adj:raw,on:false};
  const adj=(cal!=null&&Number.isFinite(Number(cal)))?Number(cal):(Number(raw)/1.055);
  return {raw:Number(raw),adj,on:true};
}

function planCaptureOptLock(){
  /** Snapshot holding-plan DT after Finalize — Optimize must not re-suggest until unlock. */
  return planDraftEntries().map(r=>({
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
  const box=q('plan-scenario-outcomes');if(!box)return;
  const s=(sim&&sim.summary)||{};
  const achv=s.achievable_production_t||0;
  // Capacity “planned” = path-model WMT. Achievable = raw simulate (same figure as B).
  // Ticket lens (−5.5%) is companion-only — never replace the primary Achievable KPI.
  const plannedPath=(predict&&Number.isFinite(predict.wmt)&&predict.wmt>0)
    ?predict.wmt
    :(s.planned_production_t||0);
  const lens=planBiasAdjustedAchievable(achv);
  const showAchv=achv; // always match B · Production & capacity
  const ratio=plannedPath>0?showAchv/plannedPath:1;
  const vc=_flowSim&&Number.isFinite(_flowSim.vc)?_flowSim.vc:null;
  const shortfall=Math.max(0,plannedPath-showAchv);
  const planned=plannedPath;
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
    return Number.isFinite(mm.dtMax)&&r.dt>mm.dtMax;
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
            <div><span class="muted">Shortfall</span><b>${Math.round(shortfall).toLocaleString('en-GB')} t</b></div>
            <div><span class="muted">vs planned</span><b>${planned?Math.round(100*ratio)+'%':'—'}</b></div>
          </div>
          <p class="muted" style="font-size:10.5px;margin:6px 0 0">Same achievable as B (raw simulate). Planned = path-model WMT ${Math.round(plannedPath).toLocaleString('en-GB')} t.${lens.on
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
              <em class="plan-realism-sub">similar-fleet days</em>
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
let _planCrowdIncludeIwip=true;
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
function planFetchRoadCrowding(){
  const plans=planDraftEntries().map(r=>({
    source:r.source,destination:r.dest,n_trucks:Math.round(r.dt||0),
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
    body:JSON.stringify({plans:plans.concat(iwip),shift_hours:shiftH,rain_mm:rain,start_hour:7}),
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
  const iwipChk=`<label class="plan-rc-iwip" title="Add the measured IWIP/Position trucks (their last-shift paths, scaled to the Other-trips input) to the road occupancy. They share POS 12\u2013FENI with our hauls.">
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
  const rows=secs.map(s=>{
    const cap=s.cap_trucks_bin||1;
    const cells=(s.occupancy||[]).map((c,b)=>{
      const r=cap>0?c/cap:0;
      const cls=r>=1?'rc-high':r>=0.7?'rc-watch':c>0?'rc-open':'rc-idle';
      const tip=`${escH(s.section)} · ${String(hourLbls[b]).padStart(2,'0')}:00 · ${c} truck${c===1?'':'s'} on section (cap ~${Math.round(cap)}/bin${cap?` · ${Math.round(100*r)}%`:''})`;
      return `<div class="rc-cell ${cls}" title="${tip}">${c>0?c:''}</div>`;
    }).join('');
    const who=(s.plans||[]).join(' · ');
    const shared=s.shared?` <span class="muted">· shared${who.includes('IWIP')?' incl. IWIP':''}</span>`:'';
    return `<div class="rc-row" title="${escH(s.section)} — used by: ${escH(who||'—')}">
      <div class="rc-sec"><b>${escH(s.section)}</b>${shared}</div>
      <div class="rc-cells">${cells}</div>
    </div>`;
  }).join('');
  const axis=`<div class="rc-row rc-axis"><div class="rc-sec"></div><div class="rc-cells">${
    hourLbls.map(h=>`<div class="rc-cell rc-hour">${String(h).padStart(2,'0')}</div>`).join('')
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
      Trucks on each section per hour \u2014 our ${meta.nPlan||0} plan path(s)${iwipNote}.
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
      <div class="effkpi"><div class="v">${planFmtN(predict.wmt)} t</div><div class="l">Your path model</div></div>
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
      +'. History band is separate from simulate achievable tonnes.';
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

/** Busy overlay on A+B while simulate recalculates productivity & capacity. */
function planSetCalcBusy(on){
  ['plan-outcomes-busy','plan-estimate-busy'].forEach(id=>{
    const el=q(id);if(el)el.classList.toggle('is-busy',!!on);
  });
  const finBtn=q('plan-finalize-opt');
  if(finBtn)finBtn.disabled=!!on;
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
  const est=q('plan-scenario-estimate');
  if(est)est.innerHTML='<p class="muted">Calculating productivity &amp; capacity…</p>';
  const out=q('plan-scenario-outcomes');
  if(out&&!out.querySelector('.plan-decision-card')){
    out.innerHTML='<p class="muted">Calculating productivity &amp; capacity…</p>';
  }

  // A + B only here. C · road illustration waits for GPS corridor ▶ Run.
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
    // Re-paint D before outcomes so realism/shared-road feed into A
    if(_planLastAnalogues)planRenderAnalogues(_planLastAnalogues);
    planRenderOutcomes(sim,predict);
    const open=q('plan-open-assessment');
    if(open)open.disabled=false;
    planRefreshSaveButtons();
    // Keep viewport on A · Shift outcomes — GPS ▶ Run opens C below.
    const stage=q('plan-scenario-outcomes');
    if(stage&&typeof stage.scrollIntoView==='function'){
      try{stage.scrollIntoView({behavior:'smooth',block:'nearest'});}
      catch(_){stage.scrollIntoView(true);}
    }
  }).catch(e=>{
    if(gen!==_planScenarioGen||_planScenarioQueued)return;
    if(est)est.innerHTML='<p class="er">simulate failed: '+escH(String(e))+'</p>';
  }).finally(()=>{
    if(gen!==_planScenarioGen)return;
    _planScenarioBusy=false;
    planSetCalcBusy(false);
    if(btn){btn.disabled=false;btn.textContent='Run simulated scenario';}
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
  _psPlans=plans.map(p=>({route:p.route,source:p.source,destination:p.destination,n_trucks:p.n_trucks}));
  // Carry analogue plans (with contractor) for assessment top-k / shared-road panels.
  if(typeof window!=='undefined'){
    window._paAnaloguePlans=planDraftToAnaloguePlans();
    window._paAnalogues=_planLastAnalogues;
  }
  const host=q('plan-assessment-host');
  if(host)host.style.display='';
  // Host lives inside the scenario panel — reveal that too when the assessment
  // is opened directly (e.g. before any Run scenario click).
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
      key:r.key,dt:r.dt,contractor:r.contractor||'',
      source:r.source||(r.key.split('>')[0]||''),
      dest:r.dest||(r.key.split('>')[1]||''),
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
}

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
