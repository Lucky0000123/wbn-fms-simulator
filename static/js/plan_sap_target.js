// ── Priority targets in the plan (owner 2026-08-13 / 2026-08-14) ─────────────
// P1 = SAP (must-move). Predicted sits AT the target, never well above.
// P2 = LIM from TOS. Filled after SAP.
// P3 = LIM from LD. A supplied target is filled after P1/P2; without a target
//      it remains the lowest-priority capacity sink for leftover trucks.
// Allocate: same contractor, same origin first.
//   1. SAP extra → SAP still short.
//   2. Remaining SAP shortfall from LIM-LD, then LIM-TOS, until Predicted
//      meets target. P2/P3 may go to 0 DT — a 1-truck leftover path is not
//      a real plan (it still needs a loader and a dump). requiredDt is not the stop.
//   3. LIM-TOS extra → LIM-TOS still short.
//   4. Remaining LIM-TOS shortfall from LIM-LD, then SAP extra.
//   5. Trim SAP to Predicted ≈ target. Leftover trucks → TOS short, then LD,
//      then any same-contractor P2 even if that P2 is already over.
//   6. Fill targeted P3 rows from untargeted/surplus LD, then leave any fleet
//      beyond all supplied targets on untargeted LD as visible excess capacity.
// Original Check-capacity card stays frozen; New Allocation Plan paints below.
// Predicted and Achievable stay two clocks — never averaged.
// Allocate sizes Predicted ≈ target. Achievable is /api/simulate (raw),
// not capped at predicted or at target. Monthly is where overshoot is hidden.
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmt=n=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:0});
  const fmt2=n=>n==null||!isFinite(n)?'—':Number(n).toLocaleString('en-GB',{maximumFractionDigits:2,minimumFractionDigits:0});

  function draft(){return (typeof _planDraft!=='undefined')?_planDraft:{};}
  function hz(){return typeof planHorizonFactor==='function'?planHorizonFactor():1;}
  function rainMm(){return Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);}
  // Day-04 plan dates are Scenario 4 (S4): S3 plus the 50/50 LD split of
  // planning_rules.md §4 P3. NOTE 2026-08-04 predates the convention — it is
  // a legacy August daily plan, not S4; re-allocating it would apply the
  // split, so leave the August legacy dates alone.
  function planRulesS4Active(){
    return /^\d{4}-\d{2}-04$/.test(((q('plan-date')||{}).value||'').trim());
  }

  let _allocFrozen=false;
  let _allocMsg='';
  let _allocMoves=[];
  let _origTotals=null;
  let _savedAlloc=null;
  let _yearlyRows=null;
  let _yearlyMonth=null;
  let _allocPrioFilter='';
  let _posTransitInfo=null;   // planning_rules.md §5 — last POS→FeNi IWIP sizing
  window.planAllocFrozen=function(){return _allocFrozen;};

  function allocTableHead(){
    return '<thead><tr>'
      +'<th>Path</th><th>Contractor</th><th>Material</th>'
      +'<th class="r">Target t</th>'
      +'<th class="r">DT</th>'
      +'<th class="r">Trips/DT</th>'
      +'<th class="r">t/DT</th>'
      +'<th class="r">Predicted t</th>'
      +'<th class="r">Achievable t</th>'
      +'</tr></thead>';
  }
  function allocTableFoot(hzLab, n){
    return '<tfoot><tr class="plan-total-row">'
      +'<td data-k="lab"><b>TOTAL · '+esc(hzLab)+'</b></td>'
      +'<td class="muted" data-k="n">'+(n||'')+'</td><td></td>'
      +'<td class="r" data-k="tgt"><b></b></td>'
      +'<td class="r" data-k="dt"></td>'
      +'<td class="r" data-k="tpd"></td>'
      +'<td class="r" data-k="wpd"></td>'
      +'<td class="r" data-k="pred"></td>'
      +'<td class="r" data-k="achv"></td>'
      +'</tr></tfoot>';
  }
  function pairHtml(oldV, newV, o){
    o=o||{};
    const f=o.fmt||fmt;
    const oldOk=oldV!=null&&isFinite(oldV);
    const newOk=newV!=null&&isFinite(newV);
    const oldTxt=oldOk?f(oldV):'—';
    const newTxt=newOk?f(newV):'—';
    let delta='';
    if(o.delta&&oldOk&&newOk){
      const d=Math.round(newV)-Math.round(oldV);
      if(d) delta=' <span class="plan-pair-d '+(d>0?'up':'down')+'">'+(d>0?'+':'')+fmt(d)+'</span>';
    }
    return '<div class="plan-pair'+(o.tone?' '+o.tone:'')+'">'
      +'<div class="plan-pair-new">'+newTxt+delta+(o.extra||'')+'</div>'
      +'<div class="plan-pair-old">was '+oldTxt+'</div>'
      +(o.note?'<div class="plan-pair-note" title="'+(o.noteTitle||'')+'">'+o.note+'</div>':'')
      +'</div>';
  }
  function allocMetricTds(o){
    const vs=predVsTarget(o.predNew, o.tgt);
    let simNote={};
    // Flag rows where the two clocks part by >50% either way.
    if(o.predNew>0&&o.achvNew!=null&&o.achvNew>0){
      const ratio=o.achvNew/o.predNew;
      if(ratio<0.5){
        simNote={note:'<span style="color:#ef4444">⚠ achv '+Math.round(ratio*100)+'% of pred — check</span>',
          noteTitle:'Models disagree badly on this row: the engine (all-days cycle basis) delivers under half of the path model. Usually the fleet here is far beyond the engine\'s measured cycles, or the route lacks engine history. Fix the row before trusting the plan.'};
      }else if(ratio>1.5){
        simNote={note:'<span style="color:#f59e0b">⚠ achv '+(ratio).toFixed(1)+'× pred — check</span>',
          noteTitle:'Models disagree badly on this row: simulate sees over 1.5× the path model. Usually the path\'s day-cluster history is thin or depressed by disrupted days. Check before trusting.'};
      }
    }
    return ''
      +'<td class="r plan-hold-num">'+fmt(o.tgt)+'</td>'
      +'<td class="r">'+pairHtml(o.dtOld, o.dtNew, {delta:true})+'</td>'
      +'<td class="r">'+pairHtml(o.tpdOld, o.tpdNew, {fmt:fmt2, extra:o.valHtml||''})+'</td>'
      +'<td class="r">'+pairHtml(o.wpdOld, o.wpdNew, {fmt:fmt2})+'</td>'
      +'<td class="r">'+pairHtml(o.predOld, o.predNew, {extra:vs.extra, tone:vs.tone})+'</td>'
      +'<td class="r">'+pairHtml(o.achvOld, o.achvNew, simNote)+'</td>';
  }
  function ratePair(pred, trips, dt){
    if(!(dt>0))return {tpd:null,wpd:null,trips:trips||null,pred:pred||null};
    return {tpd:trips!=null?trips/dt:null, wpd:pred!=null?pred/dt:null, trips:trips||null, pred:pred||null};
  }
  function allocPrioFilterBar(){
    const on=p=>((p===_allocPrioFilter)?' on':'');
    return '<div class="plan-alloc-prio" role="tablist" aria-label="Filter by priority">'
      +'<button type="button" data-prio="" class="'+on('').trim()+'" onclick="planAllocFilter(\'\')">All</button>'
      +'<button type="button" data-prio="1" class="'+on('1').trim()+'" onclick="planAllocFilter(\'1\')">P1</button>'
      +'<button type="button" data-prio="2" class="'+on('2').trim()+'" onclick="planAllocFilter(\'2\')">P2</button>'
      +'<button type="button" data-prio="3" class="'+on('3').trim()+'" onclick="planAllocFilter(\'3\')">P3</button>'
      +'</div>';
  }
  function predVsTarget(pred, target){
    const predTxt=pred!=null?fmt(pred)+' t':'—';
    const tgtTxt=target?fmt(target):'—';
    let extra='', tone='';
    if(pred!=null&&target>0){
      const d=Math.round(pred-target);
      if(Math.abs(d)<=Math.max(1,target*0.005)){extra=' <span class="plan-alloc-vs on">on</span>';tone='plan-alloc-on';}
      else if(d>0){extra=' <span class="plan-alloc-vs over">+'+fmt(d)+'</span>';tone='plan-alloc-over';}
      else {extra=' <span class="plan-alloc-vs short">'+fmt(d)+'</span>';tone='plan-alloc-short';}
    }
    return {
      predTd:'<td class="r plan-hold-wmt '+tone+'">'+predTxt+extra+'</td>',
      tgtTd:'<td class="r plan-hold-num">'+tgtTxt+'</td>'
    };
  }
  function allocHeroHtml(o){
    const hz=o.hzLab||'day';
    const newAchv=o.newAchv;
    const oldAchv=o.oldAchv;
    const dPred=(o.newPred!=null&&o.oldPred!=null)?Math.round(o.newPred-o.oldPred):null;
    const dAchv=(newAchv!=null&&oldAchv!=null)?Math.round(newAchv-oldAchv):null;
    const delta=d=>{
      if(d==null||!d)return '';
      return ' <span class="'+(d>0?'up':'down')+'">'+(d>0?'+':'')+fmt(d)+'</span>';
    };
    const t=v=>v!=null?fmt(v):'—';
    return '<div class="plan-alloc-hero-row">'
      +'<div class="plan-hero-metric">'
      +'<div class="plan-hero-l">New predicted</div>'
      +'<div class="plan-hero-v">'+t(o.newPred)+'</div>'
      +'<div class="plan-hero-u">t / '+esc(hz)+'</div></div>'
      +'<div class="plan-alloc-hero-split" aria-hidden="true"></div>'
      +'<div class="plan-hero-metric plan-alloc-hero-achv">'
      +'<div class="plan-hero-l">New achievable</div>'
      +'<div class="plan-hero-v">'+t(newAchv)+'</div>'
      +'<div class="plan-hero-u">t / '+esc(hz)+'</div></div>'
      +'</div>'
      +'<div class="plan-alloc-hero-bar">'
      +'<span class="k">Before</span>'
      +'<span><b>'+t(o.oldPred)+'</b> pred</span>'
      +'<span><b>'+t(oldAchv)+'</b> achv</span>'
      +'<span class="k">After</span>'
      +'<span><b>'+t(o.newPred)+'</b> pred'+delta(dPred)+'</span>'
      +'<span><b>'+t(newAchv)+'</b> achv'+delta(dAchv)+'</span>'
      +(o.newDt!=null?'<span class="dt"><b>'+fmt(o.newDt)+'</b> DT</span>':'')
      +'</div>';
  }
  window.planAllocFilter=function(p){
    _allocPrioFilter=String(p||'');
    applyAllocPrioFilter();
  };
  function applyAllocPrioFilter(){
    const hold=q('plan-alloc-holding');
    if(!hold)return;
    const want=_allocPrioFilter;
    hold.querySelectorAll('.plan-alloc-prio button').forEach(b=>{
      b.classList.toggle('on', (b.getAttribute('data-prio')||'')===want);
    });
    let n=0,dtOld=0,dtNew=0,tripsOld=0,tripsNew=0,predOld=0,predNew=0,achvOld=0,achvNew=0,tgt=0;
    hold.querySelectorAll('tbody tr[data-prio]').forEach(tr=>{
      const show=!want||tr.getAttribute('data-prio')===want;
      tr.style.display=show?'':'none';
      if(!show)return;
      n+=1;
      if(tr.getAttribute('data-tenant')==='1')return;
      dtOld+=Number(tr.getAttribute('data-dt-old')||0);
      dtNew+=Number(tr.getAttribute('data-dt-new')||tr.getAttribute('data-dt')||0);
      tripsOld+=Number(tr.getAttribute('data-trips-old')||0);
      tripsNew+=Number(tr.getAttribute('data-trips-new')||tr.getAttribute('data-trips')||0);
      predOld+=Number(tr.getAttribute('data-pred-old')||0);
      predNew+=Number(tr.getAttribute('data-pred-new')||tr.getAttribute('data-pred')||0);
      achvOld+=Number(tr.getAttribute('data-achv-old')||0);
      achvNew+=Number(tr.getAttribute('data-achv-new')||tr.getAttribute('data-achv')||0);
      tgt+=Number(tr.getAttribute('data-tgt')||0);
    });
    const foot=hold.querySelector('tfoot .plan-total-row');
    if(!foot)return;
    const lab=want?('P'+want):'TOTAL';
    const set=(k,html)=>{const el=foot.querySelector('[data-k="'+k+'"]');if(el)el.innerHTML=html;};
    if(foot.querySelector('[data-k]')){
      set('lab','<b>'+lab+' · '+esc(hold.getAttribute('data-hz')||'day')+'</b>');
      set('n',String(n));
      set('tgt','<b>'+fmt(tgt)+'</b>');
      set('dt', pairHtml(dtOld, dtNew, {delta:true}));
      set('tpd', pairHtml(dtOld?tripsOld/dtOld:null, dtNew?tripsNew/dtNew:null, {fmt:fmt2}));
      set('wpd', pairHtml(dtOld?predOld/dtOld:null, dtNew?predNew/dtNew:null, {fmt:fmt2}));
      set('pred', pairHtml(predOld, predNew, {
        extra:tgt?' <span class="plan-pair-pct">'+(100*predNew/tgt).toFixed(1)+'%</span>':''
      }));
      set('achv', pairHtml(achvOld, achvNew, {
        extra:tgt?' <span class="plan-pair-pct">'+(100*achvNew/tgt).toFixed(1)+'%</span>':''
      }));
      return;
    }
    const cells=foot.querySelectorAll('td');
    if(cells[0])cells[0].innerHTML='<b>'+lab+' · '+esc(hold.getAttribute('data-hz')||'day')+'</b>';
    if(cells[1])cells[1].textContent=String(n);
    if(cells[3])cells[3].innerHTML='<b>'+fmt(dtNew)+'</b>';
    if(cells[4])cells[4].innerHTML='<b>'+fmt(tripsNew)+'</b>';
    if(cells[5])cells[5].innerHTML='<b>'+fmt(predNew)+' t</b>';
    if(cells[6])cells[6].innerHTML='<b>'+fmt(tgt)+'</b>';
    if(cells[7])cells[7].innerHTML='<b>'+fmt(achvNew)+' t</b>';
  }

  // Allocate / simulate re-paints this table many times. innerHTML would
  // throw the inner scroller (and, if a focused row was destroyed, the page)
  // back to the top while the planner is reading the lower rows.
  let _allocHoldHtml='';
  function setAllocHoldingHtml(hold, html){
    if(!hold)return;
    const sc=hold.querySelector('.plan-holding-table');
    const y=sc?sc.scrollTop:0, x=sc?sc.scrollLeft:0;
    const page=document.scrollingElement||document.documentElement;
    const py=page?page.scrollTop:0, px=page?page.scrollLeft:0;
    if(_allocHoldHtml===html && sc){
      applyAllocPrioFilter();
      return;
    }
    hold.innerHTML=html;
    _allocHoldHtml=html;
    applyAllocPrioFilter();
    const restore=()=>{
      const sc2=hold.querySelector('.plan-holding-table');
      if(sc2){sc2.scrollTop=y;sc2.scrollLeft=x;}
      if(page){page.scrollTop=py;page.scrollLeft=px;}
    };
    restore();
    if(typeof requestAnimationFrame==='function')requestAnimationFrame(restore);
  }

  function canonSrc(s){
    s=String(s||'').trim().toUpperCase();
    return s==='TOFU'?'TF':s;
  }
  function canonDest(d){
    return String(d||'').trim().toUpperCase()
      .replace(/\s+/g,' ')
      .replace('KM 0','KM0').replace('KM 15','KM15').replace('KM 10','KM10');
  }
  function canonCo(c){return String(c||'').trim().toUpperCase();}
  function allocOriginOf(r){
    if(!r)return '';
    if(typeof planHoldSrc==='function')return canonSrc(planHoldSrc(r));
    return canonSrc(r.source||String(r.key||'').split('>')[0]||'');
  }
  function allocPrioRank(r){
    const p=r&&(r.prio!=null?r.prio:prioOf(r));
    return p===1?1:p===2?2:p===3?3:9;
  }
  function allocIsRoadOnly(r){
    return !!(r&&(r.foreign||r._posTransit));
  }
  function allocRowCmp(a,b){
    const ra=a.r||a, rb=b.r||b;
    // IWIP / POS-transit rows are road-only (no WMT). Keep them after the
    // production block so POS 12 → FeNi does not sit in the middle of KR/TF.
    return (allocIsRoadOnly(ra)?1:0)-(allocIsRoadOnly(rb)?1:0)
      ||allocOriginOf(ra).localeCompare(allocOriginOf(rb))
      ||allocPrioRank(ra)-allocPrioRank(rb)
      ||String(ra.contractor||'').localeCompare(rb.contractor||'')
      ||String(ra.key||'').localeCompare(rb.key||'');
  }

  // planning_rules.md §3 — pit→contractor walls (BLB=RIM, KR=SMA, TF open).
  // Mutates row.contractor to the pit's owner when the wall is broken. Only
  // for rows being CREATED: an existing row's slot id embeds its contractor,
  // so loaded rows are flagged by the validation summary instead of renamed.
  function enforceContractor(row){
    if(!row||row.foreign)return row;
    const walls=((window.PLANNING_RULES||{}).contractors)||{};
    const pit=canonSrc(String(row.key||'').split('>')[0]||row.source||'');
    const want=walls[pit];
    if(want&&canonCo(row.contractor)!==canonCo(want))row.contractor=want;
    return row;
  }
  function contractorWallViolations(){
    const walls=((window.PLANNING_RULES||{}).contractors)||{};
    const out=[];
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(!r||r.foreign||!(workingDt(r)>0))return;
      const pit=canonSrc(String(r.key||'').split('>')[0]||'');
      const want=walls[pit];
      if(want&&canonCo(r.contractor)!==canonCo(want))
        out.push({key:r.key,contractor:r.contractor,want:want});
    });
    return out;
  }

  // P1 SAP, P2 LIM TOS, P3 LIM LD (and anything else that is not protected).
  // Origin type from the year matrix wins; a missing chip does not turn SAP
// into a donor. A typed LD target is a real P3 goal, but P1/P2 can still draw
// from it because priority order is strict.
  function prioOf(r){
    if(!r||r.foreign)return 9;
    const mat=String(r.material||'').toUpperCase();
    const ot=String(r.otype||'').toUpperCase();
    if(mat==='SAP')return 1;
    if(mat==='LIM'&&ot==='TOS')return 2;
    if(mat==='LIM'&&ot==='LD')return 3;
    if(mat==='LIM'&&r.targetWmt>0)return 2;
    if(mat==='LIM')return 3;
    return 9;
  }
  function isDonor(r){return prioOf(r)===3;}
  function isProtected(r){const p=prioOf(r);return p===1||p===2||(p===3&&r.targetWmt>0);}

  // Show the builder target field for every production row (SAP, LIM-TOS, LIM-LD, others).
  function syncTargetVisibility(){
    const mat=q('plan-material'),f=q('plan-sap-target-field'),ot=q('plan-otype-field');
    const foreign=typeof planForeignOn==='function'&&planForeignOn();
    const v=mat?mat.value:'';
    if(ot)ot.style.display=(!foreign&&v==='LIM')?'':'none';
    if(f)f.style.display=foreign?'none':'';
    const inp=q('plan-sap-target');
    if(inp){
      const otVal=((q('plan-otype')||{}).value||'TOS').toUpperCase();
      inp.title=v==='LIM'&&otVal==='LD'
        ?'LIM from LD — priority-3 t/day target, filled after SAP and LIM-TOS.'
        :v==='LIM'?'LIM from TOS — t/day target for this row.'
        :v==='SAP'?'SAP — tonnes/day this path must deliver.'
        :'Tonnes/day target for this path.';
    }
  }
  document.addEventListener('change',ev=>{
    if(ev.target&&(ev.target.id==='plan-material'||ev.target.id==='plan-otype'))syncTargetVisibility();
    if(ev.target&&ev.target.id==='plan-date')loadYearlyTargets();
  });
  setInterval(function(){
    syncTargetVisibility();
    try{
      stampYearlyTargets();
      const host=boardHost();
      const hasTargets=Object.keys(draft()).some(id=>draft()[id]&&(draft()[id].targetWmt>0||isProtected(draft()[id])));
      if(host&&hasTargets&&host.querySelector('.plan-cap-block')&&!q('plan-sap-board-cap')){
        renderBoard();
      }
    }catch(e){}
  },900);

  // Stamp targetWmt on rows created by Add to plan (any material, including LIM-LD).
  const _origAdd=window.planAddPath;
  if(typeof _origAdd==='function'){
    window.planAddPath=function(){
      const before=new Set(Object.keys(draft()));
      const r=_origAdd.apply(this,arguments);
      const mat=(q('plan-material')||{}).value;
      const tgt=Math.max(0,parseFloat((q('plan-sap-target')||{}).value)||0);
      const ot=((q('plan-otype')||{}).value||'').toUpperCase();
      const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value;
      let name='—';
      try{const c=typeof planContractor==='function'?planContractor():null;if(c&&c.name)name=c.name;}catch(e){}
      const slot=(typeof planDraftSlotId==='function'&&s&&d)
        ?planDraftSlotId(name,s+'>'+d,{material:mat,otype:ot==='LD'?'LD':'TOS'})
        :null;
      Object.keys(draft()).forEach(id=>{
        if(before.has(id))return;
        if(slot&&id!==slot)return; // migrated sibling (other LIM origin) stays as it was
        const row=draft()[id];
        if(!row||row.foreign)return;
        if(mat==='SAP')row.otype=row.otype||'TOS';
        if(tgt>0){
          row.targetWmt=tgt;
          row._targetManual=true;
        }
      });
      const ti=q('plan-sap-target');if(ti)ti.value='';
      stampYearlyTargets();
      renderBoard();
      return r;
    };
  }

  if(typeof window.planDraftSnapshot==='function'){
    const _origSnap=window.planDraftSnapshot;
    window.planDraftSnapshot=function(){
      const snap=_origSnap.apply(this,arguments);
      // Tenant fleets STAY in `paths` so Save/Load keeps the DT the planner
      // typed, AND in allocation.rows (flagged foreign+_tenant) so New
      // Allocation still lists them after Load. They stay OUT of the engine
      // / segment background: the road cost is tenants=1 flow, and a row
      // without `_tenant` used to fall through to a phantom "KR spur".
      // Stamp the flag onto the snapshot — planDraftSnapshot's field list
      // does not copy it, which is how that spur was born.
      Object.keys(snap.paths||{}).forEach(id=>{
        const r=draft()[id];
        if(!r)return;
        if(typeof planIsTenantRow==='function'?planIsTenantRow(r,id):r._tenant){
          snap.paths[id]._tenant=true;
          snap.paths[id].foreign=true;
          if(Number.isFinite(r._tenantRate))snap.paths[id]._tenantRate=r._tenantRate;
          if(r._tenantBasis)snap.paths[id]._tenantBasis=r._tenantBasis;
        }
        if(r.targetWmt>0)snap.paths[id].targetWmt=r.targetWmt;
        if(r.otype)snap.paths[id].otype=r.otype;
        if(r._targetManual)snap.paths[id]._targetManual=true;
        if(r._preAlloc)snap.paths[id]._preAlloc={dt:r._preAlloc.dt,pred:r._preAlloc.pred,achv:r._preAlloc.achv,achv_sim:r._preAlloc.achv_sim};
        if(r._allocDt!=null)snap.paths[id]._allocDt=r._allocDt;
      });
      const alloc=buildAllocationPayload();
      if(alloc)snap.allocation=alloc;
      return snap;
    };
  }

  if(typeof window.planLoadDraft==='function'){
    const _origLoad=window.planLoadDraft;
    window.planLoadDraft=function(){
      unfreezeOriginal();
      const r=_origLoad.apply(this,arguments);
      // Saved path JSON embeds the last Allocate's _preAlloc / _allocDt.
      // That is the FILE's original, not the live holding plan. Strip it
      // here; planRestoreAllocation puts it back only when the save is
      // actually frozen. Otherwise Allocate would reset DT to the file.
      Object.keys(draft()).forEach(id=>{
        const row=draft()[id];
        if(!row)return;
        delete row._preAlloc;
        delete row._allocDt;
        if(String(id).indexOf('TENANT|')===0)row._tenant=true;
      });
      stampYearlyTargets();
      // Merge the register into whatever the file already carried. Old saves
      // have no tenant paths; new ones do, with the planner's DT. Fire-and-
      // forget here is only a fallback — planLoadSavedForDate awaits the
      // same function so Your plan cannot paint before the rows exist.
      if(typeof planRulesTenants==='function'){
        Promise.resolve().then(planRulesTenants).catch(function(){});
      }
      return r;
    };
  }

  function loadYearlyTargets(){
    const date=((q('plan-date')||{}).value||'').trim();
    const month=date.length>=7?date.slice(0,7):'';
    if(!month||month===_yearlyMonth)return;
    fetch('/api/monthly/targets?month='+encodeURIComponent(month))
      .then(r=>r.json())
      .then(data=>{
        if(!data||!data.ok)return;
        _yearlyRows=data.rows||[];
        _yearlyMonth=data.month||month;
        stampYearlyTargets();
        renderBoard();
      }).catch(()=>{});
  }
  function yearlyMatch(r){
    if(!_yearlyRows||!r)return [];
    const src=canonSrc(r.source||(r.key||'').split('>')[0]);
    const dst=canonDest(r.dest||(r.key||'').split('>')[1]);
    const co=canonCo(r.contractor);
    return _yearlyRows.filter(y=>y.src===src&&canonDest(y.dst)===dst&&canonCo(y.contractor)===co);
  }
  function stampYearlyTargets(){
    const d=draft();
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||r.foreign)return;
      const hits=yearlyMatch(r);
      if(!hits.length)return;
      const mat=String(r.material||'').toUpperCase();
      const sap=hits.filter(y=>y.mat==='SAP');
      const limTos=hits.filter(y=>y.mat==='LIM'&&y.otype==='TOS');
      const limLd=hits.filter(y=>y.mat==='LIM'&&y.otype==='LD');
      if(!r.otype){
        if(mat==='SAP'||sap.length)r.otype='TOS';
        else if(limTos.length)r.otype='TOS';
        else if(limLd.length)r.otype='LD';
      }
      if(r._targetManual)return;
      const ot=String(r.otype||'').toUpperCase();
      if(r.targetWmt>0)return;
      if(mat==='SAP'&&sap.length)r.targetWmt=sap.reduce((a,y)=>a+(y.target||0),0);
      else if(mat==='LIM'&&ot==='TOS'&&limTos.length)r.targetWmt=limTos.reduce((a,y)=>a+(y.target||0),0);
      else if(mat==='LIM'&&ot==='LD'&&limLd.length)r.targetWmt=limLd.reduce((a,y)=>a+(y.target||0),0);
      else if(mat==='LIM'&&!ot&&limTos.length)r.targetWmt=limTos.reduce((a,y)=>a+(y.target||0),0);
      else if(mat==='LIM'&&!ot&&limLd.length)r.targetWmt=limLd.reduce((a,y)=>a+(y.target||0),0);
    });
    if(typeof planMigrateLimIds==='function')planMigrateLimIds();
  }

  // planning_rules.md §4 (owner 2026-08-26, INVERTING the 08-25 rule the
  // owner called a blunder): each pit sends ~2,000 t/day of SAP to its POS
  // BUFFER (±2,000 landing band); the REST goes DIRECT to FeNi, to the
  // destination the pit's own plan rows name. The engine below is generic —
  // fixedRoutes carry the 2,000 (now the POS rows) and overflowRoutes carry
  // the remainder (now the FeNi rows) — so the inversion is pure data from
  // PLANNING_RULES. Remainder stays with the SAME contractor.
  function sapPathParts(path){
    const k=String(path||'');
    const i=k.indexOf('>');
    if(i<0)return {pit:'', dest:''};
    return {pit:canonSrc(k.slice(0,i)), dest:canonDest(k.slice(i+1))};
  }
  function ensureSapRow(co, key){
    const d=draft();
    const id=(typeof planDraftSlotId==='function')
      ?planDraftSlotId(co, key, {material:'SAP'})
      :co+'|'+key;
    if(d[id])return {id:id, r:d[id], created:false};
    const src=key.split('>')[0], dest=key.split('>')[1];
    d[id]={key:key, dt:0, loaders:2, contractor:co, source:src, dest:dest,
      material:'SAP', otype:'TOS', foreign:false, targetWmt:0};
    return {id:id, r:d[id], created:true};
  }
  function applySapRouting(force){
    if(_allocFrozen&&!force)return;
    const R=window.PLANNING_RULES||{};
    const fixed=R.fixedRoutes||[];
    const overflow=R.overflowRoutes||[];
    if(!fixed.length&&!overflow.length)return;
    const d=draft();
    const sap=[];
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||r.foreign||String(r.material||'').toUpperCase()!=='SAP')return;
      sap.push({id:id, r:r,
        pit:canonSrc(r.source||String(r.key||'').split('>')[0]),
        dest:canonDest(r.dest||String(r.key||'').split('>')[1]),
        co:canonCo(r.contractor)});
    });
    if(!sap.length)return;
    const fixedByPit={};
    fixed.forEach(f=>{
      const p=sapPathParts(f.path);
      if(p.pit)fixedByPit[p.pit]={dest:p.dest, amt:Number(f.targetWmt)||0};
    });
    const ovByPit={};
    overflow.forEach(o=>{
      const p=sapPathParts(o.path);
      if(p.pit)ovByPit[p.pit]={dest:p.dest};
    });
    const pits=[];
    sap.forEach(x=>{if(pits.indexOf(x.pit)<0)pits.push(x.pit);});
    pits.forEach(pit=>{
      const fx=fixedByPit[pit];
      const ov=ovByPit[pit];
      const rows=sap.filter(x=>x.pit===pit);
      const coTot={};
      rows.forEach(x=>{coTot[x.co]=(coTot[x.co]||0)+(Number(x.r.targetWmt)||0);});
      const pitTot=Object.keys(coTot).reduce((a,c)=>a+coTot[c],0);
      const toFeni=Math.min(pitTot, fx?fx.amt:0);
      const feniShare={};
      const feniRows=fx?rows.filter(x=>x.dest===fx.dest):[];
      if(toFeni>0&&feniRows.length){
        const wsum=feniRows.reduce((a,x)=>a+(Number(x.r.targetWmt)||Number(x.r.dt)||1),0);
        let left=toFeni;
        feniRows.forEach((x,i)=>{
          const w=Number(x.r.targetWmt)||Number(x.r.dt)||1;
          const share=(i===feniRows.length-1)?left:Math.round(toFeni*(w/wsum));
          feniShare[x.co]=(feniShare[x.co]||0)+share;
          left-=share;
        });
      }
      rows.forEach(x=>{
        if(fx&&x.dest===fx.dest)x.r.targetWmt=0;
        else if(ov&&x.dest===ov.dest)x.r.targetWmt=0;
        else x.r.targetWmt=0;
      });
      if(fx){
        Object.keys(feniShare).forEach(co=>{
          const list=rows.filter(x=>x.co===co&&x.dest===fx.dest);
          if(list.length)list[0].r.targetWmt=feniShare[co];
        });
      }
      if(!ov)return;
      Object.keys(coTot).forEach(co=>{
        const rest=Math.max(0, coTot[co]-(feniShare[co]||0));
        let list=rows.filter(x=>x.co===co&&x.dest===ov.dest);
        if(!list.length&&rest>0){
          const key=pit+'>'+ov.dest;
          const made=ensureSapRow(co, key);
          if(made.created){
            const donor=rows.find(x=>x.co===co&&x.r.dt>1);
            if(donor){donor.r.dt-=1;made.r.dt=1;}
            else made.r.dt=1;
            const rec={id:made.id, r:made.r, pit:pit, dest:ov.dest, co:co};
            sap.push(rec);rows.push(rec);list=[rec];
          }else list=[{id:made.id, r:made.r, pit:pit, dest:ov.dest, co:co}];
        }
        if(list.length)list[0].r.targetWmt=rest;
      });
    });
  }

  function requiredDt(key,targetDay,contractor,selfId){
    if(typeof planDtForWmt!=='function')return null;
    const rain=rainMm();
    const sf=typeof planShiftFactor==='function'?planShiftFactor():0.5;
    const perShift=targetDay*sf;
    const dt=planDtForWmt(key,perShift,rain,contractor,typeof planTripOpts==='function'?planTripOpts(selfId):{selfId:selfId});
    return dt?Math.ceil(dt):null;
  }

  function routeDt(key){
    let n=0;
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(r&&r.key===key&&!r.foreign){
        const dt=workingDt(r);
        if(dt>0)n+=dt;
      }
    });
    return n;
  }
  // This row's share of the route's simulate achievable (per day).
  // Simulate merges contractors on a route; dumping the route total onto
  // every targeted row double-counted HUAFEI / POS hauls.
  function achievableShare(key,rowDt){
    const sim=(typeof _planLastSim!=='undefined')&&_planLastSim;
    if(!sim||!sim.results)return null;
    const row=sim.results.find(x=>(x.route||'').trim()===key);
    if(!row||row.achievable_production_t==null)return null;
    const routeDay=row.achievable_production_t*2;
    const tot=routeDt(key);
    if(!(tot>0))return routeDay;
    return routeDay*(rowDt/tot);
  }

  function predDayFor(id,r){
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const opts=typeof planTripOpts==='function'?planTripOpts(id):{selfId:id,nLoaders:r.loaders||2};
    // §10.9 breaks a circularity: loaders follow the fleet, pricing follows
    // loaders. Price every sizing walk with the loaders the EVALUATED dt
    // implies, so applying loaders after Allocate reprices nothing —
    // without this the trimmed P2 row re-landed at 88%/115% of target
    // whenever the walk crossed a loader bucket (measured 2026-09-04).
    if(_tplCache[r.key]>0)opts.nLoaders=planRulesLoadersFor(r.dt,_tplCache[r.key]);
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rainMm(),c,opts):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
    // WEIGHBRIDGE INCLUDED (owner bug, 2026-08-21): this function priced
    // dt×daily while the saved clocks price dt×shift×hz — the difference is
    // wbFactor. The §5 IWIP POS-transit trucks push the POS 12 bridge to
    // wb≈0.8 AFTER allocation, so the allocator called KR>POS 12 'met' at
    // 6,186 t and the saved board showed 5,184 t. One question, one model:
    // the allocator must judge targets on the same served tonnage the board
    // reports, or Stage F stops one truck short of the real target.
    return e?r.dt*e.daily*(e.wbFactor||1)*pay.tf:null;
  }
  // debug/scripting handle: the allocator's own row pricing (payload +
  // §10.9 loader override included) — scripts must never re-derive it
  window.planPredDayFor=function(id){const r=draft()[id];return r?predDayFor(id,r):null;};
  // Targeted P1/P2 rows short at their ALLOCATED fleet, priced with the
  // full final traffic (weighbridges included). The allocate wrapper polls
  // this between passes: a non-empty answer means some traffic landed
  // after Stage F (async IWIP bridge shares) and one more pass is needed.
  window.planAllocShortfalls=function(){
    const d=draft();
    const out=[];
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||r.foreign||!(r.targetWmt>0))return;
      const p=prioOf(r);
      if(p!==1&&p!==2)return;
      const n=(r._allocDt!=null)?r._allocDt:r.dt;
      if(!(n>0))return;
      const sv=r.dt;r.dt=n;
      const pred=predDayFor(id,r);
      r.dt=sv;
      if(pred!=null&&pred<r.targetWmt*0.995)
        out.push({id,key:r.key,contractor:r.contractor,prio:p,
          target:r.targetWmt,pred:Math.round(pred)});
    });
    return out;
  };

  function decorateRowTargets(rows){
    const d=draft();
    Array.from(rows.querySelectorAll('.plan-mat-tag[data-matid]')).forEach(tag=>{
      const id=tag.getAttribute('data-matid');
      const r=d[id];
      if(!r||r.foreign)return;
      const isSap=(r.material||'')==='SAP';
      const p=prioOf(r);
      const hasTarget=r.targetWmt>0;
      const label=hasTarget?(fmt(r.targetWmt)+' t'):'+ target';
      const existing=tag.parentNode.querySelector('.plan-sap-chip[data-sapid="'+CSS.escape(id)+'"]');
      const col=isSap||p===1?['rgba(34,197,94,.14)','#4ade80','rgba(34,197,94,.3)']
               :p===2?['rgba(96,165,250,.14)','#93c5fd','rgba(96,165,250,.3)']
               :['rgba(148,163,184,.12)','#94a3b8','rgba(148,163,184,.3)'];
      const tip=p===1?'SAP is fixed supply (P1) — click to set the t/day target'
               :p===2?'LIM from TOS is priority 2 — click to set the t/day target'
               :p===3?'LIM from LD — click to set the priority-3 t/day target. It fills after SAP and LIM-TOS.'
               :'Click to set the t/day target for this path.';
      if(existing){
        if(!existing.querySelector('input')){
          existing.innerHTML=label;
          existing.style.background=col[0];
          existing.style.color=col[1];
          existing.style.borderColor=col[2];
          existing.title=tip;
        }
        return;
      }
      tag.insertAdjacentHTML('afterend',
        ' <span class="plan-sap-chip" data-sapid="'+esc(id)+'" title="'+tip+'" '
        +'style="background:'+col[0]+';color:'+col[1]
        +';border:1px solid '+col[2]+'">'
        +label+'</span>');
    });
  }

  document.addEventListener('click',ev=>{
    const chip=ev.target&&ev.target.closest?ev.target.closest('.plan-sap-chip[data-sapid]'):null;
    if(!chip||chip.querySelector('input'))return;
    const id=chip.getAttribute('data-sapid');
    const r=draft()[id];
    if(!r)return;
    const inp=document.createElement('input');
    inp.type='number';inp.min='0';inp.step='500';
    inp.value=r.targetWmt>0?r.targetWmt:'';
    inp.placeholder='t/day';
    inp.style.cssText='width:72px;font-size:11px;background:transparent;color:inherit;border:none;outline:none;font-weight:700';
    chip.textContent='';
    chip.appendChild(inp);
    inp.focus();
    let done=false;
    const commit=()=>{
      if(done)return;done=true;
      const v=Math.max(0,parseFloat(inp.value)||0);
      if(v>0){r.targetWmt=v;r._targetManual=true;if((r.material||'')==='LIM'&&!r.otype)r.otype='TOS';}
      else{delete r.targetWmt;r._targetManual=true;}
      if(typeof computePlan==='function')computePlan();
    };
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();commit();}
      if(e.key==='Escape'){done=true;if(typeof computePlan==='function')computePlan();}});
    inp.addEventListener('blur',commit);
    ev.stopPropagation();
  });

  function boardHost(){
    // Original Check-capacity card keeps its required-DT board after Allocate.
    return q('plan-scenario-estimate');
  }

  function renderBoard(){
    const rows=q('plan-rows');
    if(!rows)return;
    decorateRowTargets(rows);
    const leftover=q('plan-sap-board');
    if(leftover)leftover.remove();
    stampYearlyTargets();
    const targets=Object.keys(draft()).map(id=>({id,r:draft()[id]}))
      .filter(x=>x.r&&!x.r.foreign&&(x.r.targetWmt>0||isProtected(x.r)));
    if(!_allocFrozen)renderCapBoard(targets);
    else{
      // Freezing does not repaint the required-DT board, it just stops
      // updating it — so a board rendered a moment earlier on the
      // PRE-allocation DT stayed on screen telling the planner to "add 45 DT"
      // to a plan that was already allocated. Retire it when we freeze.
      const stale=q('plan-sap-board-cap');
      if(stale)stale.innerHTML='';
      renderAllocView();
    }
  }

  function boardHtml(targets){
    const rain=rainMm();
    const body=targets.map(({id,r})=>{
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const pred=predDayFor(id,r);
      // ONE fleet basis. achievableShare divides this row's DT by routeDt(key),
      // and routeDt sums workingDt() — the ALLOCATED DT once _allocDt is set.
      // Passing r.dt (the pre-allocation figure) mixed the two: on TF>HUAFEI
      // that is 576 over a 302-truck denominator instead of 638, so the row
      // claimed more than the whole route's achievable and the board total
      // ran 42% above the plan's own achievable. Take both from workingDt.
      const achv=achievableShare(r.key,workingDt(r));
      let reqDt=r.targetWmt>0?requiredDt(r.key,r.targetWmt,c,id):null;
      const ceil=typeof planDtForWmt==='function'?planDtForWmt._lastCeiling:null;
      const unreachable=r.targetWmt>0&&reqDt==null;
      let ceilDt=null;
      if(unreachable&&ceil&&ceil.maxT>0){
        ceilDt=requiredDt(r.key,ceil.maxT*2*0.995,c,id);
      }
      const met=pred!=null&&r.targetWmt>0&&pred>=r.targetWmt*0.995;
      const p=prioOf(r);
      const status=!r.targetWmt
        ?'<span class="muted">set target</span>'
        :unreachable
        ?(ceilDt!=null
          ?'<span style="color:#ef4444;font-weight:600">'
            +(ceilDt>r.dt?('add '+fmt(ceilDt-r.dt)+' DT → path max '):'at path max ')
            +fmt(ceil.maxT*2)+' t/day — short '+fmt(Math.max(0,r.targetWmt-ceil.maxT*2))
            +' t/day needs a 2nd path</span>'
          :'<span style="color:#ef4444;font-weight:600">target above path ceiling'+(ceil?(' ('+fmt(ceil.maxT*2)+' t/day max)'):'')+'</span>')
        :met?'<span style="color:#22c55e;font-weight:600">on target</span>'
        :(p===2&&r._preAlloc&&r.dt<r._preAlloc.dt
          ?'<span style="color:#f59e0b;font-weight:600">short '+fmt(Math.max(0,r.targetWmt-(pred||0)))+' t/day — DT moved to SAP</span>'
          :'<span style="color:#f59e0b;font-weight:600">add '+fmt(Math.max(0,reqDt-r.dt))+' DT</span>');
      if(unreachable&&ceilDt!=null)reqDt=ceilDt;
      const prio=p===1?'P1':p===2?'P2':'P3';
      const dtDelta=r._preAlloc!=null&&r._preAlloc.dt!==r.dt
        ?' <span style="color:'+(r.dt>r._preAlloc.dt?'#4ade80':'#f59e0b')+'">('
          +(r.dt>r._preAlloc.dt?'+':'')+(r.dt-r._preAlloc.dt)+')</span>':'';
      return '<tr>'
        +'<td><span style="font-size:9px;padding:0 5px;border-radius:7px;margin-right:4px;'
        +(prio==='P1'?'background:rgba(34,197,94,.15);color:#4ade80':'background:rgba(96,165,250,.15);color:#93c5fd')
        +'">'+prio+'</span><b>'+esc(r.key.replace('>',' → '))+'</b> <span class="muted">'+esc(r.contractor)
        +(r.otype?' · '+esc(r.otype):'')+'</span></td>'
        +'<td class="r">'+(r.targetWmt?fmt(r.targetWmt):'—')+'</td>'
        +'<td class="r">'+(pred!=null?fmt(pred):'—')+'</td>'
        +'<td class="r">'+(achv!=null?fmt(achv):'<span class="muted" title="run Check capacity to fill">run sim</span>')+'</td>'
        +'<td class="r">'+fmt(r.dt)+dtDelta+'</td>'
        +'<td class="r">'+(reqDt!=null?fmt(reqDt):'—')+'</td>'
        +'<td>'+status+'</td></tr>';
    }).join('');
    const hasAlloc=targets.some(({r})=>r._preAlloc!=null);
    let strip='';
    if(hasAlloc){
      // An UNKNOWN achievable must not add as zero and must not be totalled
      // with known ones — "OLD ACHIEVABLE 0" was a null share (no simulate
      // response yet) rendered as a measured zero beside a live new figure.
      let oP=0,nP=0,T=0,oA=0,nA=0,oAn=0,nAn=0,oAmiss=0,nAmiss=0;
      const prios=new Set();
      targets.forEach(({id,r})=>{
        const pre=r._preAlloc||{};
        T+=r.targetWmt||0;
        prios.add(prioOf(r));
        oP+=pre.pred||0;
        nP+=predDayFor(id,r)||0;
        if(Number.isFinite(pre.achv)){oA+=pre.achv;oAn++;}else oAmiss++;
        const na=achievableShare(r.key,workingDt(r));
        if(Number.isFinite(na)){nA+=na;nAn++;}else nAmiss++;
      });
      const cell=(v,l,cls,miss)=>'<div class="kpi" style="margin-right:18px;display:inline-block">'
        +'<div style="font-size:17px;font-weight:700;color:'+cls+'">'+(v==null?'—':fmt(v))+'</div>'
        +'<div style="font-size:10px;color:var(--muted,#8b98a5);text-transform:uppercase">'+l
        +(miss?'<span title="rows with no simulate response yet — run Check capacity"> · '+miss+' n/a</span>':'')
        +'</div></div>';
      // Say which priorities are actually in this sum. The caption claimed
      // "P1+P2 rows only" while every scenario LIM-LD row carries a target and
      // so lands in `targets` too — one P3 row alone was 125,450 t of it.
      const pl=[...prios].filter(x=>x===1||x===2||x===3).sort()
        .map(x=>'P'+x).join('+')||'targeted';
      strip='<div style="margin:8px 0 2px">'
        +cell(T,'target · t/day','#e6edf3')
        +cell(nP,'new predicted','#4ade80')
        +cell(oP,'old predicted','#8b98a5')
        +cell(nAn?nA:null,'new achievable','#93c5fd',nAmiss)
        +cell(oAn?oA:null,'old achievable','#8b98a5',oAmiss)
        +'</div>'
        +'<div class="muted" style="font-size:10.5px;margin:0 0 6px">'+pl+' rows with a target. '
        +'Predicted = path model \u00b7 Achievable = this row\u2019s share of simulate at its ALLOCATED DT '
        +'(same fleet basis as the plan total, so these sum to it). '
        +'Same rain on old and new. Never averaged.</div>';
    }
    return '<div style="margin-top:10px;border:1px solid rgba(34,197,94,.3);border-radius:9px;padding:9px 12px">'
      +'<b style="font-size:12px">Priority targets — P1 SAP (must-move) · P2 LIM-TOS · P3 LIM-LD</b> '
      +'<span class="muted" style="font-size:11px">SAP is sized to target. Leftover same-contractor trucks go to LIM-TOS (which may exceed its target) then LIM-LD. Donors: LIM-LD first. Same contractor, same origin first.</span>'
      +strip
      +'<table style="width:100%;margin-top:6px;font-size:12px;border-collapse:collapse">'
      +'<tr style="color:var(--muted,#8b98a5);font-size:10.5px;text-transform:uppercase">'
      +'<th style="text-align:left">Path</th><th class="r">Target t/day</th><th class="r">Predicted</th>'
      +'<th class="r">Achievable</th><th class="r">Allocated DT</th><th class="r">Required DT</th><th style="text-align:left">Status</th></tr>'
      +body+'</table>'
      +'<div style="margin-top:8px">'
      +'<button type="button" class="ms-btn" id="plan-alloc-priority-btn" onclick="planAllocatePriority()" '
      +'title="SAP is sized to target. Leftover same-contractor trucks go to LIM-TOS (may exceed target) then LIM-LD. Same contractor, same origin first.">'
      +'⚡ Allocate DT as per priority requirements</button>'
      +'<span class="muted" id="plan-alloc-status" style="font-size:11px;margin-left:9px"></span>'
      +'</div>'
      +'</div>';
  }

  function renderCapBoard(targets){
    const cap=boardHost();
    if(!cap)return;
    const block=cap.querySelector('.plan-cap-block')||cap;
    let cards=q('plan-prio-cards-before');
    if(!cards||!cap.contains(cards)){
      cards=document.createElement('div');
      cards.id='plan-prio-cards-before';
      const kpis=block.querySelector('.plan-cap-kpis');
      if(kpis&&kpis.nextSibling)kpis.parentNode.insertBefore(cards,kpis.nextSibling);
      else if(kpis)kpis.insertAdjacentElement('afterend',cards);
      else block.insertBefore(cards,block.firstChild);
    }
    cards.innerHTML=bucketCardsHtml('before');
    let slot=q('plan-sap-board-cap');
    if(!targets||!targets.length){if(slot)slot.innerHTML='';return;}
    if(!slot||!cap.contains(slot)){
      slot=document.createElement('div');
      slot.id='plan-sap-board-cap';
      block.appendChild(slot);
    }
    slot.innerHTML=boardHtml(targets);
  }

  function captureOrigTotals(){
    const filled=fillBuckets();
    _origTotals={
      pred:filled.predTotal||null,
      achv:filled.achvTotal||null,
      achv_sim:filled.achvSimTotal||null,
      dt:filled.fleet||null
    };
  }
  function setUnlockVisible(on){
    document.querySelectorAll('.plan-unlock').forEach(el=>{el.hidden=!on;});
    const hold=q('plan-holding');
    if(hold)hold.classList.toggle('is-locked',!!on);
  }
  function freezeOriginalCap(){
    const orig=q('plan-scenario-estimate');
    if(!orig)return;
    // Keep the original required-DT board as Check capacity showed it.
    if(!orig.querySelector('.plan-cap-frozen-lab')){
      orig.insertAdjacentHTML('afterbegin',
        '<div class="plan-cap-frozen-lab">Original plan — required DT as checked (unchanged)</div>');
    }
    orig.classList.add('plan-cap-frozen');
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='';
    wrap&&wrap.scrollIntoView({behavior:'smooth',block:'nearest'});
    lockCapacityBtn();
    lockHoldingPlan();
  }
  function unfreezeOriginal(){
    _allocFrozen=false;
    _allocMsg='';
    _allocMoves=[];
    _origTotals=null;
    _savedAlloc=null;
    _allocHoldHtml='';
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(r){delete r._preAlloc;delete r._allocDt;}
    });
    const orig=q('plan-scenario-estimate');
    if(orig){
      orig.classList.remove('plan-cap-frozen');
      const lab=orig.querySelector('.plan-cap-frozen-lab');
      if(lab)lab.remove();
    }
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='none';
    ['plan-alloc-hero','plan-alloc-buckets','plan-alloc-holding','plan-rules-validation','plan-alloc-estimate']
      .forEach(id=>{const el=q(id);if(el)el.innerHTML='';});
    setUnlockVisible(false);
    unlockCapacityBtn();
  }
  window.planUnlockOriginal=function(){
    if(!_allocFrozen)return;
    if(!confirm('Unlock original plan? New Allocation Plan will be cleared. Edit DT, then Check capacity again.'))return;
    unfreezeOriginal();
    if(typeof computePlan==='function')computePlan();
    if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
  };

  function lockCapacityBtn(){
    const btn=q('plan-run-scenario');
    if(btn){btn.hidden=true;btn.disabled=true;btn.textContent='Check capacity';}
    const note=q('plan-run-locked');
    if(note)note.hidden=false;
    setUnlockVisible(true);
  }
  function unlockCapacityBtn(){
    const btn=q('plan-run-scenario');
    if(btn){btn.hidden=false;}
    const note=q('plan-run-locked');
    if(note)note.hidden=true;
    setUnlockVisible(false);
    if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
  }
  window.planLockCapacityBtn=lockCapacityBtn;

  function lockHoldingPlan(){
    document.querySelectorAll('#plan-rows .plan-hold-dt').forEach(el=>{
      // Other-tenant DT is not part of the locked contractor plan — the
      // planner can change it and Save without unlocking / re-Allocating.
      if(el.closest('tr.plan-hold-tenant'))return;
      el.readOnly=true;
      el.title='Original plan is locked. Unlock to edit DT / loaders, then Check capacity again.';
    });
    const scope=q('plan-scope');
    if(scope&&scope.textContent.indexOf('original · locked')<0){
      scope.textContent=(scope.textContent||'')+' · original · locked';
    }
    setUnlockVisible(true);
  }

  function workingDt(r){
    return (r&&r._allocDt!=null)?r._allocDt:r.dt;
  }

  function bucketOf(r){
    const p=prioOf(r);
    if(p===1)return 'sap';
    if(p===2)return 'tos';
    if(String(r.material||'').toUpperCase()==='LIM')return 'ld';
    return null;
  }
  function rowTonnes(id,r,dt){
    const n=dt!=null?dt:workingDt(r);
    const hzN=hz();
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,n,rainMm(),c,typeof planTripOpts==='function'?planTripOpts(id):{selfId:id,nLoaders:r.loaders||2}):null;
    const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
    if(!e)return {trips:null,pred:null};
    const trips=n*e.shift*hzN;
    return {trips:trips,pred:r.foreign?null:trips*(pay.tf||0)};
  }
  function snapshotRow(id,r){
    const c=rowClocks(id,r,r.dt);
    // `achv` is null when there is no /api/simulate response to take a share
    // of. Coercing that to 0 printed "OLD ACHIEVABLE 0" on the priority board
    // as though the old plan moved nothing — an UNKNOWN rendered as a
    // confident zero, the same shape as the clamped capacity-card difference
    // and the availability override. Keep null; the renderer says "—".
    return {dt:r.dt,pred:c.pred||0,
            achv:Number.isFinite(c.achv)?c.achv:null,
            achv_sim:Number.isFinite(c.sim)?c.sim:null};
  }
  function rowClocks(id,r,dt){
    const tw=rowTonnes(id,r,dt);
    const sim=r.foreign?null:achievableShare(r.key, dt!=null?dt:workingDt(r));
    return {trips:tw.trips,pred:tw.pred,sim:sim,achv:sim};
  }
  function fillBuckets(){
    const hzLab=typeof planHorizonLabel==='function'?planHorizonLabel():'day';
    const B={
      sap:{key:'sap',label:'SAP · must-move',cls:'sap',target:0,pred:0,achv:0,achvSim:0,simComplete:true,dt:0,n:0,dtWas:0,predWas:0,achvWas:0},
      tos:{key:'tos',label:'LIM-TOS · priority 2',cls:'tos',target:0,pred:0,achv:0,achvSim:0,simComplete:true,dt:0,n:0,dtWas:0,predWas:0,achvWas:0},
      ld:{key:'ld',label:'LIM-LD · priority 3',cls:'ld',target:0,pred:0,achv:0,achvSim:0,simComplete:true,dt:0,n:0,dtWas:0,predWas:0,achvWas:0}
    };
    let fleet=0,fleetWas=0,hasWas=false,predTotal=0,achvTotal=0,achvSimTotal=0,simComplete=true;
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(!r||r.foreign)return;
      const dtNow=workingDt(r);
      fleet+=dtNow||0;
      if(r._preAlloc&&r._preAlloc.dt!=null){fleetWas+=r._preAlloc.dt;hasWas=true;}
      else fleetWas+=r.dt||0;
      const clk=rowClocks(id,r,dtNow);
      predTotal+=clk.pred||0;
      achvTotal+=clk.achv||0;
      if(dtNow>0&&!Number.isFinite(clk.sim))simComplete=false;
      else achvSimTotal+=clk.sim||0;
      const k=bucketOf(r);
      if(!k)return;
      const b=B[k];
      if(dtNow>0)b.n+=1;
      b.dt+=dtNow||0;
      b.target+=r.targetWmt>0?r.targetWmt:0;
      b.pred+=clk.pred||0;
      b.achv+=clk.achv||0;
      if(dtNow>0&&!Number.isFinite(clk.sim))b.simComplete=false;
      else b.achvSim+=clk.sim||0;
      if(r._preAlloc){
        b.dtWas+=r._preAlloc.dt||0;
        b.predWas+=r._preAlloc.pred||0;
        b.achvWas+=r._preAlloc.achv||0;
      }else{
        b.dtWas+=r.dt||0;
      }
    });
    return {B:B,hzLab:hzLab,fleet:fleet,fleetWas:fleetWas,hasWas:hasWas,
      predTotal:predTotal,achvTotal:achvTotal,achvSimTotal:achvSimTotal,
      simComplete:simComplete};
  }
  function bucketStatusNote(k,target,pred,hzLab){
    if(!(target>0)||pred==null||!Number.isFinite(pred))return '';
    if(pred<target*0.995){
      const why=k==='tos'?' — DT moved to SAP'
        :k==='ld'?' — DT moved up to SAP / LIM-TOS'
        :k==='sap'?' — contractor fleet exhausted':'';
      return '<div class="muted" style="font-size:10.5px;margin-top:6px;color:#f59e0b">short '
        +fmt(target-pred)+' t/'+esc(hzLab)+why+'</div>';
    }
    if(k==='tos'&&pred>target*1.005)
      return '<div class="muted" style="font-size:10.5px;margin-top:6px">over target — leftover trucks after SAP was filled (allowed)</div>';
    if(k==='sap'&&pred>target*1.01)
      return '<div class="muted" style="font-size:10.5px;margin-top:6px;color:#f59e0b">still over target — this contractor has no LIM-TOS / LIM-LD path to take leftover trucks</div>';
    return '';
  }
  function covPct(target,pred){
    if(!(target>0)||pred==null||!Number.isFinite(pred))return null;
    return Math.round(1000*pred/target)/10;
  }
  function covBlockHtml(k,target,pred){
    const pct=covPct(target,pred);
    if(pct==null)
      return '<div class="plan-alloc-cov">'
        +'<div class="k">Predicted / target</div>'
        +'<div class="v plan-alloc-cov-v">—</div>'
        +'<div class="plan-alloc-was">'+(target?'no predicted yet':'no target on this bucket')+'</div>'
        +'</div>';
    const d=Math.round(pred)-Math.round(target);
    let tone='ok';
    if(pct<99.5)tone='short';
    else if(pct>101)tone=(k==='sap')?'over':'over-ok';
    const delta=!d?'on target'
      :(d>0?'+'+fmt(d)+' t over ('+pct+'%)':fmt(d)+' t short ('+pct+'%)');
    return '<div class="plan-alloc-cov '+tone+'">'
      +'<div class="k">Predicted / target</div>'
      +'<div class="v plan-alloc-cov-v">'+pct+'%</div>'
      +'<div class="plan-alloc-was">'+delta+'</div>'
      +'</div>';
  }
  function deltaHtml(now,was){
    if(was==null||!Number.isFinite(was))return '';
    const d=Math.round(now)-Math.round(was);
    if(!d)return '<div class="plan-alloc-was">was '+fmt(was)+' · same</div>';
    const cls=d>0?'up':'down';
    return '<div class="plan-alloc-was">was '+fmt(was)+' · <b class="'+cls+'">'+(d>0?'+':'')+fmt(d)+'</b></div>';
  }
  function bucketCardsHtml(phase){
    const {B,hzLab,fleet,fleetWas,hasWas}=fillBuckets();
    const any=B.sap.n||B.tos.n||B.ld.n;
    if(!any)return '';
    const after=phase==='after';
    const cards=['sap','tos','ld'].map(k=>{
      const b=B[k];
      const predLab=after?'New predicted':'Predicted';
      const achvLab=after?'New achievable':'Achievable';
      const pred=after?b.pred:(b.predWas||b.pred);
      const achv=after?b.achv:(b.achvWas||b.achv);
      return '<div class="plan-alloc-bucket plan-alloc-bucket--'+b.cls+'">'
        +'<div class="plan-alloc-bucket-h">'+b.label+(b.n?' · '+b.n+' path'+(b.n===1?'':'s'):'')+'</div>'
        +covBlockHtml(k,b.target,pred)
        +'<div class="plan-alloc-bucket-grid">'
        +'<div><div class="k">Target t/'+esc(hzLab)+'</div><div class="v">'+(b.target?fmt(b.target):'—')+'</div></div>'
        +'<div><div class="k">'+predLab+'</div><div class="v">'+(b.n?fmt(pred):'—')+'</div>'
          +(after&&b.n?deltaHtml(b.pred,b.predWas):'')+'</div>'
        +'<div><div class="k">'+achvLab+'</div><div class="v">'+(b.n?fmt(achv):'—')+'</div>'
          +(after&&b.n?deltaHtml(b.achv, b.achvWas):'')+'</div>'
        +'<div><div class="k">DT</div><div class="v">'+(b.n?fmt(after?b.dt:b.dtWas||b.dt):'—')+'</div>'
          +(after&&b.n?deltaHtml(b.dt,b.dtWas):'')+'</div>'
        +'</div>'
        +bucketStatusNote(k,b.target,after?b.pred:b.predWas||b.pred,hzLab)
        +'</div>';
    }).join('');
    const fleetNote=after&&hasWas
      ?('<div class="plan-prio-fleet">Fleet <b>'+fmt(fleet)+' DT</b> after · <b>'+fmt(fleetWas)+' DT</b> before'
        +(Math.round(fleet)===Math.round(fleetWas)?' · same trucks, only moved between SAP / LIM-TOS / LIM-LD':'')
        +'</div>')
      :('<div class="plan-prio-fleet">Fleet <b>'+fmt(fleet)+' DT</b> in this plan · Allocate moves trucks between SAP / LIM-TOS / LIM-LD, total stays the same</div>');
    return '<div class="plan-alloc-buckets">'+cards+'</div>'+fleetNote;
  }

  function renderAllocView(sim,predict){
    if(!_allocFrozen)return;
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='';
    const hzLab=typeof planHorizonLabel==='function'?planHorizonLabel():'day';
    const simUse=sim||((typeof _planLastSim!=='undefined')&&_planLastSim);
    const haveLive=simUse&&simUse.summary&&Number.isFinite(simUse.summary.achievable_production_t);
    if(!haveLive&&_savedAlloc){
      paintSavedAfter(allocWithDraftTenants(_savedAlloc));
      return;
    }
    const filled=fillBuckets();
    const newPred=filled.predTotal||null;
    const newAchv=filled.achvTotal||null;
    const old=_origTotals||{};
    const {fleet}=filled;
    const hero=q('plan-alloc-hero');
    if(hero)hero.innerHTML=allocHeroHtml({
      hzLab:hzLab, newPred:newPred, newAchv:newAchv,
      oldPred:old.pred, oldAchv:old.achv, newDt:fleet,
      target:Object.keys(draft()).reduce((s,id)=>s+((draft()[id]||{}).targetWmt||0),0)
    });
    const buck=q('plan-alloc-buckets');
    if(buck){buck.className='';buck.innerHTML=bucketCardsHtml('after');}
    const hold=q('plan-alloc-holding');
    if(hold){
      const ids=Object.keys(draft()).map(id=>({id,r:draft()[id]})).filter(x=>x.r)
        .sort(allocRowCmp);
      const srcOf=r=>typeof planHoldSrc==='function'?planHoldSrc(r):(r.source||(r.key||'').split('>')[0]||'');
      const colOf=src=>typeof planSrcColour==='function'?planSrcColour(src):'#64748b';
      const body=ids.map(({id,r})=>{
        const dtNow=workingDt(r);
        if(!(dtNow>0))return '';
        const src=srcOf(r),col=colOf(src);
        const dtOld=r._preAlloc!=null?r._preAlloc.dt:r.dt;
        const isTen=typeof planIsTenantRow==='function'?planIsTenantRow(r,id):!!r._tenant;
        const clkNew=isTen?null:rowClocks(id,r,dtNow);
        const clkOld=isTen?null:rowClocks(id,r,dtOld);
        const tenTrips=isTen?Math.round(dtNow*(Number(r._tenantRate)||0)*(hz()===2?1:0.5)):0;
        const tgt=isTen?0:(r.targetWmt||0);
        const achv=isTen?0:clkNew.achv;
        const achvOld=isTen?0:(r._preAlloc&&r._preAlloc.achv!=null?r._preAlloc.achv:clkOld.achv);
        const mat=isTen?'other tenant'
          :(String(r.material||'—')+(r.otype?' · '+r.otype:'')+(r.foreign?' · road':''));
        const p=prioOf(r);
        const prio=p===1?'P1':p===2?'P2':p===3?'P3':'';
        const prioHtml=prio
          ?'<span style="font-size:9px;padding:0 5px;border-radius:7px;margin-right:4px;'
            +(p===1?'background:rgba(34,197,94,.15);color:#4ade80'
             :p===2?'background:rgba(96,165,250,.15);color:#93c5fd'
             :'background:rgba(148,163,184,.15);color:#94a3b8')+'">'+prio+'</span>'
          :'';
        const rpOld=ratePair(isTen?0:(clkOld.pred), isTen?tenTrips:(clkOld.trips), dtOld);
        const rpNew=ratePair(isTen?0:(clkNew.pred), isTen?tenTrips:(clkNew.trips), dtNow);
        return '<tr class="plan-hold-src" style="--src:'+col+'" data-prio="'+(p||9)+'"'
          +(isTen?' data-tenant="1"':'')
          +' data-dt="'+(dtNow||0)+'" data-dt-old="'+(dtOld||0)+'" data-dt-new="'+(dtNow||0)+'"'
          +' data-trips="'+(isTen?tenTrips:(clkNew.trips||0))+'" data-trips-old="'+(isTen?tenTrips:(clkOld.trips||0))+'" data-trips-new="'+(isTen?tenTrips:(clkNew.trips||0))+'"'
          +' data-pred="'+(isTen?0:(clkNew.pred||0))+'" data-pred-old="'+(isTen?0:(clkOld.pred||0))+'" data-pred-new="'+(isTen?0:(clkNew.pred||0))+'"'
          +' data-achv="'+(achv||0)+'" data-achv-old="'+(achvOld||0)+'" data-achv-new="'+(achv||0)+'"'
          +' data-tgt="'+(tgt||0)+'">'
          +'<td class="plan-hold-path"><span class="plan-hold-dot" aria-hidden="true"></span>'
          +prioHtml+'<b>'+esc(r.key.replace('>',' → '))+'</b></td>'
          +'<td><span class="plan-hold-co">'+esc(r.contractor)+'</span></td>'
          +'<td class="plan-hold-mat"><span class="plan-mat-tag" title="'+esc(mat)+'">'+esc(mat)+'</span></td>'
          +allocMetricTds({
            tgt:tgt, dtOld:dtOld, dtNew:dtNow,
            tpdOld:rpOld.tpd, tpdNew:rpNew.tpd,
            valHtml:(r.foreign||isTen)?'':planRulesRowBadgeHtml(planRulesRowCheck(id,r,dtNow)),
            wpdOld:rpOld.wpd, wpdNew:rpNew.wpd,
            predOld:isTen?0:clkOld.pred, predNew:isTen?0:clkNew.pred,
            achvOld:achvOld, achvNew:achv
          })
          +'</tr>';
      }).join('');
      const nShow=ids.filter(x=>workingDt(x.r)>0).length;
      hold.setAttribute('data-hz', hzLab);
      setAllocHoldingHtml(hold,
        '<div class="plan-holding-head"><h3>New Allocation Plan</h3>'
        +allocPrioFilterBar()
        +'<div class="sub">'+nShow+' path'+(nShow===1?'':'s')+' · per '+esc(hzLab)
        +' · new on top · was = before Allocate</div></div>'
        +'<div class="plan-holding-table"><table>'
        +allocTableHead()
        +'<tbody>'+(body||'<tr><td colspan="9" class="muted">No paths</td></tr>')+'</tbody>'
        +allocTableFoot(hzLab, nShow)
        +'</table></div>');
    }
    try{renderRulesValidation();}catch(e){}
  }
  window.planRenderAllocView=renderAllocView;

  function packBucket(b){
    return {n:b.n, target:Math.round(b.target||0),
      dt_before:Math.round(b.dtWas||0), dt_after:Math.round(b.dt||0),
      pred_before:Math.round(b.predWas||0), pred_after:Math.round(b.pred||0),
      achv_before:Math.round(b.achvWas||0), achv_after:Math.round(b.achv||0),
      achv_sim:b.simComplete?Math.round(b.achvSim||0):null};
  }
  function buildAllocationPayload(){
    if(!_allocFrozen)return null;
    const hzLab=typeof planHorizonLabel==='function'?planHorizonLabel():'day';
    const filled=fillBuckets();
    const newPred=filled.predTotal||null;
    const newAchv=filled.achvTotal||null;
    const rows=Object.keys(draft()).map(id=>{
      const r=draft()[id];
      if(!r||!r.key)return null;
      const isTen=typeof planIsTenantRow==='function'?planIsTenantRow(r,id):!!r._tenant;
      const dtNow=workingDt(r);
      const clk=rowClocks(id,r,dtNow);
      const pre=r._preAlloc||{};
      const clkOld=pre.dt!=null?rowClocks(id,r,pre.dt):clk;
      // Tenants ARE saved into allocation.rows so New Allocation Plan still
      // shows them after Load. They stay foreign + _tenant so the engine,
      // corridor, and 409-clock check never treat them as production (that
      // is how "KR spur" was born — foreign without the flag). Register
      // rate only — never our congested trips/DT, never a production clock.
      if(isTen){
        const daily=Number(r._tenantRate)||0;
        const trips=Math.round(dtNow*daily*(hz()===2?1:0.5));
        return {
          id:id, key:r.key, contractor:r.contractor||'',
          material:'', otype:'', prio:null, target:0,
          foreign:true, _tenant:true,
          dt_before:pre.dt!=null?pre.dt:r.dt, dt_after:dtNow,
          pred_before:0, pred_after:0,
          achv_before:0, achv_after:0, achv_sim:0,
          trips:trips, trips_before:trips
        };
      }
      return {
        id:id, key:r.key, contractor:r.contractor||'',
        material:r.material||'', otype:r.otype||'', prio:prioOf(r),
        target:r.targetWmt||0, foreign:!!r.foreign, _tenant:false,
        dt_before:pre.dt!=null?pre.dt:r.dt, dt_after:dtNow,
        pred_before:Math.round(pre.pred!=null?pre.pred:(clkOld.pred||0)),
        pred_after:Math.round(clk.pred||0),
        achv_before:Math.round(pre.achv||0),
        achv_after:Math.round(clk.achv||0),
        achv_sim:Number.isFinite(clk.sim)?Math.round(clk.sim)
          :(Number.isFinite(pre.achv_sim)?Math.round(pre.achv_sim):null),
        trips:Math.round(clk.trips||0),
        trips_before:Math.round(clkOld.trips||0)
      };
    }).filter(Boolean);
    const goals={
      sap:Math.round(filled.B.sap.target||0),
      tos:Math.round(filled.B.tos.target||0),
      ld:Math.round(filled.B.ld.target||0),
      total:rows.reduce((a,x)=>a+(x.target||0),0)
    };
    const movedTotal=_allocMoves.reduce((a,m)=>a+(m.trucks||0),0);
    // A plan just loaded has no live /api/simulate in this session
    // (_planLastSim is cleared on restore). Rebuilding the payload from
    // live clocks then 409s even though the FILE already has achv_sim —
    // Save looked broken, and the planner was sent to Allocate again.
    // Keep the saved clocks when the live ones have not landed yet.
    const prod=rows.filter(x=>!x.foreign&&x.dt_after>0);
    const clocksOk=filled.simComplete||prod.every(x=>Number.isFinite(x.achv_sim));
    const achvSim=filled.simComplete?Math.round(filled.achvSimTotal)
      :(clocksOk?prod.reduce((a,x)=>a+(x.achv_sim||0),0):null);
    return {
      frozen:true,
      horizon:hzLab,
      old:_origTotals||{pred:null,achv:null,dt:filled.fleetWas},
      cap:'none',
      new:{pred:newPred, achv:newAchv,
        achv_sim:achvSim,
        dt:filled.fleet, target:goals.total},
      calculation_status:clocksOk?'complete':'simulation_pending',
      engine:{allocator:'priority-target-v3',priority:['SAP','LIM-TOS','LIM-LD'],
        prediction:'planTripsPerDT',achievable:'api/simulate'},
      fleet:{before:filled.fleetWas, after:filled.fleet},
      goals:goals,
      moved_total:movedTotal,
      buckets:{sap:packBucket(filled.B.sap), tos:packBucket(filled.B.tos), ld:packBucket(filled.B.ld)},
      rows:rows,
      moves:_allocMoves.slice(),
      notes:_allocMsg||''
    };
  }

  function packedCardsHtml(packed, phase, fleet){
    const hzLab=typeof planHorizonLabel==='function'?planHorizonLabel():'day';
    const after=phase==='after';
    const meta={
      sap:{label:'SAP · must-move',cls:'sap'},
      tos:{label:'LIM-TOS · priority 2',cls:'tos'},
      ld:{label:'LIM-LD · priority 3',cls:'ld'}
    };
    const cards=['sap','tos','ld'].map(k=>{
      const b=packed[k]||{};
      const n=b.n||0;
      const dt=after?b.dt_after:b.dt_before;
      const pred=after?(b.pred_after||b.pred_before):(b.pred_before||b.pred_after);
      const target=b.target||0;
      const achv=after?(b.achv_sim!=null?b.achv_sim:b.achv_after):b.achv_before;
      return '<div class="plan-alloc-bucket plan-alloc-bucket--'+meta[k].cls+'">'
        +'<div class="plan-alloc-bucket-h">'+meta[k].label+(n?' · '+n+' path'+(n===1?'':'s'):'')+'</div>'
        +covBlockHtml(k,target,pred)
        +'<div class="plan-alloc-bucket-grid">'
        +'<div><div class="k">Target t/'+esc(hzLab)+'</div><div class="v">'+(target?fmt(target):'—')+'</div></div>'
        +'<div><div class="k">'+(after?'New predicted':'Predicted')+'</div><div class="v">'+(n?fmt(pred):'—')+'</div>'
          +(after?deltaHtml(pred,b.pred_before):'')+'</div>'
        +'<div><div class="k">'+(after?'New achievable':'Achievable')+'</div><div class="v">'+(n?fmt(achv):'—')+'</div>'
          +(after?deltaHtml(achv, b.achv_before):'')+'</div>'
        +'<div><div class="k">DT</div><div class="v">'+(n?fmt(dt):'—')+'</div>'
          +(after?deltaHtml(dt,b.dt_before):'')+'</div>'
        +'</div>'
        +bucketStatusNote(k,target,pred,hzLab)
        +'</div>';
    }).join('');
    const before=fleet&&fleet.before, afterN=fleet&&fleet.after;
    const fleetNote=after&&before!=null
      ?('<div class="plan-prio-fleet">Fleet <b>'+fmt(afterN)+' DT</b> after · <b>'+fmt(before)+' DT</b> before'
        +(Math.round(afterN)===Math.round(before)?' · same trucks, only moved between SAP / LIM-TOS / LIM-LD':'')
        +'</div>')
      :('<div class="plan-prio-fleet">Fleet <b>'+fmt(after?afterN:before)+' DT</b> in this plan</div>');
    return '<div class="plan-alloc-buckets">'+cards+'</div>'+fleetNote;
  }

  function paintSavedBefore(alloc){
    const orig=q('plan-scenario-estimate');
    if(!orig||!alloc)return;
    const old=alloc.old||{};
    const hzLab=alloc.horizon||'day';
    orig.innerHTML=
      '<div class="plan-engine-block plan-cap-block">'
      +'<div class="plan-cap-horizon muted">Original Check capacity · saved with this plan · per <b>'+esc(hzLab)+'</b></div>'
      +'<div class="plan-scenario-kpis plan-cap-kpis">'
      +'<div class="effkpi plan-cap-kpi"><div class="v">'+fmt(old.dt)+'</div><div class="l">Trucks</div></div>'
      +'<div class="effkpi plan-cap-kpi"><div class="v">'+(old.pred!=null?fmt(old.pred):'—')+'</div><div class="l">Predicted t</div></div>'
      +'<div class="effkpi plan-cap-kpi"><div class="v">'+(old.achv!=null?fmt(old.achv):'—')+'</div><div class="l">Achievable</div></div>'
      +'</div>'
      +packedCardsHtml(alloc.buckets||{}, 'before', alloc.fleet)
      +savedRowsTable(alloc.rows||[], 'before', hzLab)
      +'</div>';
  }
  function savedRowsTable(rows, phase, hzLab){
    const after=phase==='after';
    const sorted=(rows||[]).slice().filter(r=>{
      const ten=!!(r&&(r._tenant||String(r.id||'').indexOf('TENANT|')===0));
      if(ten&&!after)return false;
      return true;
    }).sort(allocRowCmp);
    const body=sorted.map(r=>{
      const dtNew=r.dt_after, dtOld=r.dt_before;
      if(after&&!(dtNew>0))return '';
      const tgt=r.target||0;
      let tripsNew=r.trips, tripsOld=r.trips_before;
      if(tripsOld==null&&tripsNew&&r.pred_after){
        tripsOld=r.pred_before!=null?r.pred_before*(tripsNew/r.pred_after):null;
      }
      const rpOld=ratePair(r.pred_before, tripsOld, dtOld);
      const rpNew=ratePair(r.pred_after, tripsNew, dtNew);
      const achvNew=r.achv_sim!=null?r.achv_sim:r.achv_after;
      const achvOld=r.achv_before;
      const p=r.prio, prio=p===1?'P1':p===2?'P2':p===3?'P3':'';
      const ten=!!(r._tenant||String(r.id||'').indexOf('TENANT|')===0);
      const mat=ten?'other tenant'
        :(String(r.material||'—')+(r.otype?' · '+r.otype:'')+(r.foreign?' · road':''));
      return '<tr data-prio="'+(p||9)+'"'+(ten?' data-tenant="1"':'')
        +' data-dt="'+(dtNew||0)+'"'
        +' data-dt-old="'+(dtOld||0)+'" data-dt-new="'+(dtNew||0)+'"'
        +' data-trips="'+(tripsNew||0)+'" data-trips-old="'+(tripsOld||0)+'" data-trips-new="'+(tripsNew||0)+'"'
        +' data-pred="'+(r.pred_after||0)+'" data-pred-old="'+(r.pred_before||0)+'" data-pred-new="'+(r.pred_after||0)+'"'
        +' data-achv="'+(achvNew||0)+'" data-achv-old="'+(achvOld||0)+'" data-achv-new="'+(achvNew||0)+'"'
        +' data-tgt="'+tgt+'">'
        +'<td class="plan-hold-path">'+(prio?'<span style="font-size:9px;padding:0 5px;border-radius:7px;margin-right:4px;'
          +(p===1?'background:rgba(34,197,94,.15);color:#4ade80'
           :p===2?'background:rgba(96,165,250,.15);color:#93c5fd'
           :'background:rgba(148,163,184,.15);color:#94a3b8')+'">'+prio+'</span>':'')
        +'<b>'+esc(String(r.key||'').replace('>',' → '))+'</b></td>'
        +'<td><span class="plan-hold-co">'+esc(r.contractor||'')+'</span></td>'
        +'<td class="plan-hold-mat"><span class="plan-mat-tag" title="'+esc(mat)+'">'+esc(mat)+'</span></td>'
        +allocMetricTds({
          tgt:tgt, dtOld:dtOld, dtNew:dtNew,
          tpdOld:rpOld.tpd, tpdNew:rpNew.tpd,
          wpdOld:rpOld.wpd, wpdNew:rpNew.wpd,
          predOld:r.pred_before, predNew:r.pred_after,
          achvOld:achvOld, achvNew:achvNew
        })
        +'</tr>';
    }).join('');
    return '<div class="plan-holding-table" style="margin-top:8px"><table>'
      +allocTableHead()
      +'<tbody>'+(body||'<tr><td colspan="9" class="muted">No paths</td></tr>')+'</tbody>'
      +allocTableFoot(hzLab, sorted.length)
      +'</table></div>';
  }

  function allocWithDraftTenants(alloc){
    // After Load there is no live simulate, so renderAllocView paints the
    // FILE's allocation.rows. Those used to omit tenants, so Allocate showed
    // them and Save→refresh→Load showed the old table (owner, 2026-08-24).
    // Merge from the draft (paths + register) without touching production.
    if(!alloc)return alloc;
    const rows=((alloc.rows)||[]).slice();
    const have=new Set(rows.map(r=>String(r&&r.id||'')));
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(!r||!r.key)return;
      const ten=typeof planIsTenantRow==='function'?planIsTenantRow(r,id):!!r._tenant;
      if(!ten)return;
      if(have.has(id)){
        const hit=rows.find(x=>x&&x.id===id);
        if(hit){hit._tenant=true;hit.foreign=true;}
        return;
      }
      const dt=workingDt(r);
      if(!(dt>0))return;
      const daily=Number(r._tenantRate)||0;
      const trips=Math.round(dt*daily*(hz()===2?1:0.5));
      rows.push({
        id:id, key:r.key, contractor:r.contractor||'',
        material:'', otype:'', prio:null, target:0,
        foreign:true, _tenant:true,
        dt_before:r.dt, dt_after:dt,
        pred_before:0, pred_after:0,
        achv_before:0, achv_after:0, achv_sim:0,
        trips:trips, trips_before:trips
      });
    });
    return Object.assign({}, alloc, {rows:rows});
  }
  function paintSavedAfter(alloc){
    if(!alloc)return;
    alloc=allocWithDraftTenants(alloc);
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='';
    const hzLab=alloc.horizon||'day';
    const old=alloc.old||{};
    const neu=alloc.new||{};
    const fleet=alloc.fleet||{};
    const hero=q('plan-alloc-hero');
    const prodRow=r=>r&&!r.foreign&&!r._tenant&&String(r.id||'').indexOf('TENANT|')!==0;
    const afterT=(function(){
      let pred=0,achv=0,tgt=0;
      (alloc.rows||[]).forEach(r=>{
        if(!prodRow(r)||!(r.dt_after>0))return;
        pred+=r.pred_after||0; tgt+=r.target||0;
        achv+=(r.achv_sim!=null?r.achv_sim:r.achv_after)||0;
      });
      return {pred,achv,tgt};
    })();
    const beforeT=(function(){
      let pred=0,achv=0;
      (alloc.rows||[]).forEach(r=>{
        if(!prodRow(r))return;
        pred+=r.pred_before||0;
        achv+=r.achv_before||0;
      });
      return {pred,achv};
    })();
    if(hero)hero.innerHTML=allocHeroHtml({
      hzLab:hzLab, newPred:afterT.pred||neu.pred, newAchv:afterT.achv||neu.achv,
      oldPred:beforeT.pred||old.pred, oldAchv:beforeT.achv||old.achv, newDt:fleet.after,
      target:afterT.tgt||neu.target||(alloc.goals||{}).total
    });
    const buck=q('plan-alloc-buckets');
    if(buck){buck.className='';buck.innerHTML=packedCardsHtml(alloc.buckets||{}, 'after', alloc.fleet);}
    const hold=q('plan-alloc-holding');
    if(hold){
      hold.setAttribute('data-hz', hzLab);
      setAllocHoldingHtml(hold,
      '<div class="plan-holding-head"><h3>New Allocation Plan</h3>'
      +allocPrioFilterBar()
      +'<div class="sub">saved with this plan · per '+esc(hzLab)
      +' · new on top · was = before Allocate</div></div>'
      +savedRowsTable((alloc.rows)||[], 'after', hzLab));
    }
    try{renderRulesValidation();}catch(e){}
  }

  window.planRestoreAllocation=function(alloc){
    if(!alloc||!alloc.frozen)return;
    _savedAlloc=alloc;
    _origTotals=alloc.old||null;
    _allocMsg=alloc.notes||'';
    _allocMoves=Array.isArray(alloc.moves)?alloc.moves.slice():[];
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(!r)return;
      const saved=(alloc.rows||[]).find(x=>x.id===id||(x.key===r.key&&x.contractor===r.contractor
        &&(x.material||'')===(r.material||'')&&(x.otype||'')===(r.otype||'')));
      if(!saved)return;
      if(saved.dt_before!=null)r.dt=saved.dt_before;
      if(saved.dt_after!=null)r._allocDt=saved.dt_after;
      r._preAlloc={dt:saved.dt_before, pred:saved.pred_before, achv:saved.achv_before, achv_sim:saved.achv_sim};
      if(saved.target>0&&!(r.targetWmt>0))r.targetWmt=saved.target;
      if(saved.otype&&!r.otype)r.otype=saved.otype;
    });
    // Always paint from the saved snapshot. Load's computePlan would otherwise
    // freeze the NEW allocated card as if it were the original Check capacity.
    paintSavedBefore(alloc);
    _allocFrozen=true;
    if(typeof _planLastSim!=='undefined')_planLastSim=null;
    freezeOriginalCap();
    const panel=q('plan-scenario-panel');
    if(panel)panel.style.display='block';
    paintSavedAfter(alloc);
    // Rebuild the PRICING state, not just the plan. Every DT round-trips
    // exactly, but planTripsPerDT prices through the segment curves warmed by
    // planRulesPrepare() (loaders + planSetSegBackground + warmCurves). Without
    // them it silently falls back to the cold-start span-weighted approximation,
    // so the same fleet priced differently after a reload: measured on the
    // 2026-12-04 save, planPredictTotals() read 91,146 t against the 90,067 t
    // the owner approved (+1.20%), and 90,084 t (+0.02%) once prepared.
    // Loaders were unchanged — it is the curves, not §10.9.
    // Repaint after, because the totals the cards show are priced ones.
    if(typeof window.planRulesPrepare==='function'){
      Promise.resolve()
        .then(()=>window.planRulesPrepare())
        .then(()=>{
          if(!_allocFrozen||_savedAlloc!==alloc)return;   // superseded by a newer load
          // The saved CARDS paint from the file and are already right; it is
          // the priced figures (Step-1 predicted, the navbar summary) that
          // were stale. computePlan re-derives those and re-renders the
          // frozen view through renderBoard, without re-adding the frozen
          // label or re-scrolling the way freezeOriginalCap would.
          if(typeof computePlan==='function')computePlan();
        })
        .catch(()=>{});
    }
  };

  window.planAllocatePriority=function(){
    applySapRouting(true);
    const d=draft();
    // Drop leftover allocation helpers and zeroed paths so a previous save
    // cannot revive a row the planner already removed from Your plan.
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||r.foreign)return;
      if(!(r.dt>0)){delete d[id];return;}
      delete r._preAlloc;
      delete r._allocDt;
    });
    const rows=Object.keys(d).map(id=>({id,r:d[id]})).filter(x=>x.r&&!x.r.foreign&&x.r.dt>0);
    if(!rows.length)return;
    const rain=rainMm();
    const firstPass=!_allocFrozen;
    _allocMoves=[];
    _savedAlloc=null;
    // Baseline is the holding plan Check capacity just used — never a
    // leftover snapshot from the saved file.
    rows.forEach(({id,r})=>{
      r._preAlloc=snapshotRow(id,r);
      delete r._allocDt;
    });
    if(firstPass)captureOrigTotals();
    const byCont={};
    rows.forEach(x=>{(byCont[x.r.contractor]=byCont[x.r.contractor]||[]).push(x);});
    const movesTxt=[];
    let moved=0;
    Object.keys(byCont).forEach(cont=>{
      const crows=byCont[cont];
      const before=crows.reduce((a,x)=>a+x.r.dt,0);
      const p1=crows.filter(x=>prioOf(x.r)===1);
      const p2=crows.filter(x=>prioOf(x.r)===2);
      const p3=crows.filter(x=>prioOf(x.r)===3);
      function originOf(x){return String(x.r.key||'').split('>')[0];}
      function predOf(x){
        return predDayFor(x.id, x.r);
      }
      function predAt(x, dt){
        const saved=x.r.dt;
        x.r.dt=dt;
        const p=predDayFor(x.id, x.r);
        x.r.dt=saved;
        return p;
      }
      function sapPredShort(){
        return p1.some(x=>{
          if(!(x.r.targetWmt>0))return false;
          const p=predOf(x);
          return p!=null&&p<x.r.targetWmt*0.995;
        });
      }
      // planning_rules.md §3 (owner, 2026-08-21): SMA trucks work KR and TF
      // only, RIM trucks work BLB and TF only — trucks never change owner
      // and never sit on a pit their contractor cannot enter.
      function wallBroken(x){
        const wall=(((window.PLANNING_RULES||{}).contractors)||{})[canonSrc(originOf(x))];
        return !!(wall&&canonCo(x.r.contractor)!==canonCo(wall));
      }
      function donorSpare(list, keep){
        const k=keep==null?0:keep;
        return list.reduce((a,x)=>a+Math.max(0,x.r.dt-k),0);
      }
      // Smallest DT that still meets ~target. Inverse of requiredDt is the
      // wrong surplus on a saturated path: extra trucks barely add tonnes so
      // the inverse still "needs" the whole fleet even when Predicted is
      // already thousands above target (TF→FENI KM15 16 kt vs 10 kt).
      // WALK DOWN from the current DT, never search globally: the model's
      // trips/DT has a low-DT hump then a floored linear regime, so global
      // searches (binary or scan-from-1) land on the wrong crossing —
      // measured 2026-08-19 on Aug: SAP stuck at 106.5% while LIM-TOS
      // starved at 69%. Walking down stops at the last DT that still meets
      // target in the regime the row actually operates in.
      function minDtForTarget(x){
        if(!(x.r.targetWmt>0)||x.r.dt<=1)return x.r.dt;
        const pred=predOf(x);
        if(pred==null||pred<x.r.targetWmt*0.995)return x.r.dt;
        const tgt=x.r.targetWmt*0.995;
        let dt=Math.floor(x.r.dt);
        while(dt>1){
          const p=predAt(x, dt-1);
          if(p!=null&&p>=tgt)dt--;
          else break;
        }
        return Math.max(1,dt);
      }
      // Extra DT to push Predicted up to target. If the path cannot reach
      // target, take every remaining P2/P3 DT including the last truck —
      // SAP is must-move; a 1-DT leftover path is not a real plan.
      // Linear for the same non-monotonicity reason as minDtForTarget.
      function extraDtForTarget(x, spare){
        if(!(x.r.targetWmt>0)||!(spare>0))return 0;
        const pred=predOf(x);
        if(pred!=null&&pred>=x.r.targetWmt*0.995)return 0;
        const tgt=x.r.targetWmt*0.995;
        const hi=Math.floor(x.r.dt)+spare;
        for(let dt=Math.floor(x.r.dt)+1;dt<=hi;dt++){
          const p=predAt(x, dt);
          if(p!=null&&p>=tgt)return dt-x.r.dt;
        }
        return spare;
      }
      function belowNeed(x){
        if(wallBroken(x))return 0; // never feed trucks onto an illegal pit
        if(!(x.r.targetWmt>0))return 0;
        const pred=predOf(x);
        if(pred!=null&&pred>=x.r.targetWmt*0.995)return 0;
        const p=prioOf(x.r);
        if(p===1)return extraDtForTarget(x, donorSpare(p3.concat(p2), 0));
        if(p===2)return extraDtForTarget(x, donorSpare(p3, 1));
        if(p===3)return extraDtForTarget(x,
          p3.reduce((a,y)=>a+(y.id===x.id?0:surplusOf(y)),0)
          +p2.reduce((a,y)=>a+surplusOf(y),0)
          +p1.reduce((a,y)=>a+surplusOf(y),0));
        return 0;
      }
      function surplusOf(x){
        const p=prioOf(x.r);
        if(p===3){
          if(x.r.targetWmt>0)return Math.max(0,Math.floor(x.r.dt-minDtForTarget(x)));
          return Math.max(0,x.r.dt);
        }
        if(p===1||p===2)return Math.max(0,Math.floor(x.r.dt-minDtForTarget(x)));
        return 0;
      }
      function orderDonors(list, origin){
        return list.filter(x=>originOf(x)===origin)
          .concat(list.filter(x=>originOf(x)!==origin));
      }
      function transfer(don, rec, want, tag, drain){
        const keep=drain?0:1;
        const n=Math.min(Math.max(0,Math.floor(want)),Math.max(0,don.r.dt-keep));
        if(n<=0||don.id===rec.id)return 0;
        don.r.dt-=n;
        rec.r.dt+=n;
        moved+=n;
        const same=originOf(don)===originOf(rec);
        _allocMoves.push({
          contractor:cont, trucks:n,
          from:don.r.key, from_mat:don.r.material||'', from_otype:don.r.otype||'',
          to:rec.r.key, to_mat:rec.r.material||'', to_otype:rec.r.otype||'',
          tag:tag, reason:tag, same_origin:same, dropped:don.r.dt===0
        });
        movesTxt.push(cont+' '+n+' DT: '+don.r.key+' → '+rec.r.key
          +' ('+tag+(same?' · same origin':' · cross plan')
          +(don.r.dt===0?' · path dropped': '')+')');
        return n;
      }
      function fill(rec, want, donorSpecs){
        let left=want;
        const origin=originOf(rec);
        donorSpecs.forEach(spec=>{
          if(left<=0)return;
          for(const don of orderDonors(spec.list, origin)){
            if(left<=0)break;
            const spare=spec.spare(don);
            if(spare<=0)continue;
            left-=transfer(don, rec, Math.min(left, spare), spec.tag, spec.drain);
          }
        });
        return left;
      }
      function sapShort(){return p1.filter(x=>belowNeed(x)>0).sort((a,b)=>belowNeed(b)-belowNeed(a));}
      function tosShort(){return p2.filter(x=>belowNeed(x)>0).sort((a,b)=>belowNeed(b)-belowNeed(a));}
      function ldShort(){return p3.filter(x=>x.r.targetWmt>0&&belowNeed(x)>0)
        .sort((a,b)=>belowNeed(b)-belowNeed(a));}

      // §3 walls first: old rescues only walled BLB, so saved plans can carry
      // rows like KR>HUAFEI · RIM (18-30 DT in the Oct-Dec S1 saves). Those
      // trucks are evacuated to this contractor's TF LD row — extras always
      // land at TF — and the rounds below redistribute them legally.
      // wallBroken() rows can donate but never receive.
      (function evacuateWallBreakers(){
        const dd=draft();
        const breakers=crows.filter(x=>wallBroken(x)&&x.r.dt>0);
        if(!breakers.length)return;
        let rec=p3.find(x=>originOf(x)==='TF');
        if(!rec){
          const hid=(typeof planDraftSlotId==='function')
            ?planDraftSlotId(cont,'TF>HUAFEI',{material:'LIM',otype:'LD'})
            :cont+'|TF>HUAFEI|LIM|LD';
          if(!dd[hid]){
            dd[hid]={key:'TF>HUAFEI',dt:0,loaders:2,contractor:cont,
              source:'TF',dest:'HUAFEI',material:'LIM',otype:'LD',
              targetWmt:0,_targetManual:true,
              _preAlloc:{dt:0,pred:0,achv:0,achv_sim:0}};
            const hx={id:hid,r:dd[hid]};
            p3.push(hx);crows.push(hx);
          }
          rec={id:hid,r:dd[hid]};
        }
        breakers.forEach(don=>{
          transfer(don,rec,don.r.dt,
            'contractor wall — '+cont+' cannot work '+originOf(don)+', trucks back to TF (rules §3)',true);
        });
      })();
      // Repeat: combined-fleet on a shared route changes Predicted.
      // SAP is filled to Predicted ≈ target from P3 then P2 before any
      // leftover sits on LIM. P2/P3 may drop to 0 DT when SAP still needs
      // the fleet. P2 fill / dump wait until SAP Predicted is covered.
      for(let round=0;round<12;round++){
        const before=moved;
        sapShort().forEach(rec=>{
          fill(rec, belowNeed(rec), [
            {list:p1, tag:'SAP extra → SAP', spare:surplusOf}
          ]);
        });
        sapShort().forEach(rec=>{
          fill(rec, belowNeed(rec), [
            {list:p3, tag:'LD → SAP', spare:x=>Math.max(0,x.r.dt), drain:true},
            {list:p2, tag:'LIM-TOS → SAP (LIM-TOS may run short)', spare:x=>Math.max(0,x.r.dt), drain:true}
          ]);
        });
        function dumpExtra(list, receivers, tag){
          list.filter(x=>surplusOf(x)>0).forEach(don=>{
            let extra=surplusOf(don);
            if(extra<=0)return;
            const origin=originOf(don);
            const recs=receivers(origin, don);
            const seen={};
            for(const rec of recs){
              if(extra<=0)break;
              if(rec.id===don.id||seen[rec.id])continue;
              seen[rec.id]=true;
              extra-=transfer(don, rec, extra, tag);
            }
          });
        }
        if(!sapPredShort()){
          tosShort().forEach(rec=>{
            fill(rec, belowNeed(rec), [
              {list:p2, tag:'LIM-TOS extra → LIM-TOS', spare:surplusOf}
            ]);
          });
          tosShort().forEach(rec=>{
            fill(rec, belowNeed(rec), [
              {list:p3, tag:'LD → LIM-TOS', spare:x=>Math.max(0,x.r.dt-1)},
              {list:p1, tag:'SAP extra → LIM-TOS', spare:surplusOf}
            ]);
          });
          // P3 targets are real targets too, but are considered only after
          // every reachable SAP and LIM-TOS target is settled. They may use
          // untargeted LD, surplus above another P3 target, then genuine
          // P2/P1 surplus (never production still needed by a higher target).
          ldShort().forEach(rec=>{
            fill(rec, belowNeed(rec), [
              {list:p3.filter(x=>!(x.r.targetWmt>0)), tag:'untargeted LD → LIM-LD target',
                spare:x=>Math.max(0,x.r.dt), drain:true},
              {list:p3, tag:'LIM-LD surplus → LIM-LD target', spare:surplusOf},
              {list:p2, tag:'LIM-TOS surplus → LIM-LD target', spare:surplusOf},
              {list:p1, tag:'SAP surplus → LIM-LD target', spare:surplusOf}
            ]);
          });
          dumpExtra(p1, (origin)=>
            orderDonors(tosShort(), origin)
              .concat(orderDonors(p3.filter(x=>!wallBroken(x)&&!(x.r.targetWmt>0)), origin)),
            'trim SAP to target → LD (extras haul LIM-LD)');
          dumpExtra(p2, (origin)=>
            orderDonors(tosShort(), origin)
              .concat(orderDonors(p3.filter(x=>!wallBroken(x)&&!(x.r.targetWmt>0)), origin)),
            'trim LIM-TOS to target → LD (extras haul LIM-LD)');
        }
        if(moved===before)break;
      }
      p1.forEach(rec=>{
        const pred=predOf(rec);
        if(!(rec.r.targetWmt>0)||pred==null||pred>=rec.r.targetWmt*0.995)return;
        if(movesTxt.some(t=>t.indexOf(rec.r.key)>=0&&t.indexOf('SAP still short')>=0))return;
        const limLeft=donorSpare(p3.concat(p2), 0);
        movesTxt.push('⚠ '+cont+' SAP still short '+fmt(rec.r.targetWmt-pred)+' t/day on '+rec.r.key
          +(limLeft>0
            ?' — LIM still has '+limLeft+' DT (should have moved)'
            :' — no LIM left for this contractor; Predicted may be at the path ceiling'));
      });
      p2.forEach(rec=>{
        const pred=predOf(rec);
        if(!(rec.r.targetWmt>0)||pred==null||pred>=rec.r.targetWmt*0.995)return;
        if(movesTxt.some(t=>t.indexOf(rec.r.key)>=0&&t.indexOf('LIM-TOS short')>=0))return;
        movesTxt.push('⚠ '+cont+' LIM-TOS short '+fmt(rec.r.targetWmt-pred)+' t/day on '+rec.r.key
          +' — leftover after SAP (must-move) was not enough');
      });
      p3.forEach(rec=>{
        if(!(rec.r.targetWmt>0))return;
        // On an S4 (day-04) plan the split BELOW moves half of a targeted LD
        // row's trucks to the other destination on purpose — its own-row
        // shortfall is the what-if working, not a warning. LD attainment is
        // judged at the bucket level in the validation summary.
        if(planRulesS4Active())return;
        const pred=predOf(rec);
        if(pred==null||pred>=rec.r.targetWmt*0.995)return;
        movesTxt.push('⚠ '+cont+' LIM-LD short '+fmt(rec.r.targetWmt-pred)+' t/day on '+rec.r.key
          +' — P1 SAP and P2 LIM-TOS consumed the available fleet first');
      });
      // planning_rules.md §4 P3 — the S4 scenario (owner, 2026-08-21): same
      // plan as S3 except the leftover LD trucks at TF split 50/50 between
      // HUAFEI/BSE and POS 12, to see whether tonnage rises when the
      // leftovers stop piling onto one saturated corridor. Day-04 saves ARE
      // S4 (scenario-by-day convention, like day 01=S1 / 03=S3), so the
      // split runs ONLY on a day-04 plan date; S3 allocation is untouched
      // and the two save files compare tonnage like-for-like. Runs AFTER
      // P1/P2 are settled so it only moves genuine leftovers; same owner,
      // and only untargeted P3 excess is eligible for this network split.
      (function splitLeftoverLd(){
        if(!planRulesS4Active())return;
        const limLd=((window.PLANNING_RULES||{}).limLd)||{};
        const split=limLd.split;
        // The split's other leg is DATA from planning_rules (§4). POS 6 since
        // 2026-08-25 (owner; was POS 12) — the km 12.0 yard, a LONGER haul
        // (55.8 km vs 40.8), so expect lower trips/DT on the split rows and
        // more S2–S4 traffic. `pos12` is the pre-rename key, honoured so a
        // stale cached rules blob cannot silently disable the split.
        const share=split?(split.splitShare!=null?split.splitShare:split.pos12):null;
        if(!split||!(share>0))return;
        const SPLIT_DEST=String(limLd.splitDest||'POS 6').toUpperCase();
        const dd=draft();
        const destOf=x=>canonDest(String(x.r.key||'').split('>')[1]||'');
        const isPos12=x=>destOf(x)===SPLIT_DEST;
        const isHb=x=>destOf(x)==='HUAFEI'||destOf(x)==='BSE';
        // ALL TF LD trucks split — targeted rows included. Owner (twice,
        // 2026-08-21): "all same as S3, just the LIM-LD trucks divided 50-50
        // to these places". A targets-only filter briefly lived here and
        // killed the split outright, because every scenario LD row carries a
        // target: the split is about WHERE the LD trucks drive, and LD
        // attainment is judged on the bucket (both destinations count).
        const tfLd=p3.filter(x=>originOf(x)==='TF'&&(isPos12(x)||isHb(x)));
        const total=tfLd.reduce((a,x)=>a+x.r.dt,0);
        if(total<2)return;
        const wantPos=Math.round(total*share);
        const posRows=tfLd.filter(isPos12);
        const hbRows=tfLd.filter(isHb);
        const havePos=()=>posRows.reduce((a,x)=>a+x.r.dt,0);
        function helper(key){
          const hid=(typeof planDraftSlotId==='function')
            ?planDraftSlotId(cont,key,{material:'LIM',otype:'LD'})
            :cont+'|'+key+'|LIM|LD';
          if(!dd[hid]){
            dd[hid]=enforceContractor({key:key,dt:0,loaders:2,contractor:cont,
              source:key.split('>')[0],dest:key.split('>')[1],
              material:'LIM',otype:'LD',targetWmt:0,_targetManual:true,
              _preAlloc:{dt:0,pred:0,achv:0,achv_sim:0}});
            const hx={id:hid,r:dd[hid]};
            p3.push(hx);crows.push(hx);tfLd.push(hx);
            (isPos12(hx)?posRows:hbRows).push(hx);
          }
          return {id:hid,r:dd[hid]};
        }
        if(havePos()<wantPos&&!posRows.length)helper('TF>'+SPLIT_DEST);
        if(havePos()>wantPos&&!hbRows.length)helper('TF>HUAFEI');
        let guard=0;
        while(havePos()<wantPos&&guard++<500){
          const don=hbRows.filter(x=>x.r.dt>0).sort((a,b)=>b.r.dt-a.r.dt)[0];
          const rec=posRows.slice().sort((a,b)=>a.r.dt-b.r.dt)[0];
          if(!don||!rec)break;
          if(transfer(don,rec,Math.min(wantPos-havePos(),don.r.dt),
            'P3 50/50 split — leftovers → '+SPLIT_DEST+' (planning rules §4)',true)<=0)break;
        }
        while(havePos()>wantPos&&guard++<500){
          const don=posRows.filter(x=>x.r.dt>0).sort((a,b)=>b.r.dt-a.r.dt)[0];
          const rec=hbRows.slice().sort((a,b)=>a.r.dt-b.r.dt)[0];
          if(!don||!rec)break;
          if(transfer(don,rec,Math.min(havePos()-wantPos,don.r.dt),
            'P3 50/50 rebalance — '+SPLIT_DEST+' → HUAFEI/BSE (planning rules §4)',true)<=0)break;
        }
      })();
      const after=crows.reduce((a,x)=>a+x.r.dt,0);
      if(Math.abs(after-before)>0.01)movesTxt.push('⚠ '+cont+' fleet drift '+Math.round(after-before)+' DT');
    });

    // ── Cross-contractor rescue (owner, 2026-08-19) ─────────────────────
    // "If SMA trucks finished and we still have LIM-TOS to move, use RIM
    // trucks for the pending tonnage as a new plan." Trucks NEVER change
    // owner: the short route gains the OTHER contractor's row (a new path
    // slot), fed from that contractor's own P3/LD leftovers. One hard wall:
    // SMA (or anyone) cannot enter BLB - BLB is RIM-only.
    (function crossRescue(){
      const d=draft();
      const all=Object.keys(d).map(id=>({id,r:d[id]})).filter(x=>x.r&&!x.r.foreign);
      const shorts=all.filter(x=>{
        if(prioOf(x.r)!==2||!(x.r.targetWmt>0))return false;
        const p=predDayFor(x.id,x.r);
        return p!=null&&p<x.r.targetWmt*0.985;
      });
      shorts.forEach(rec=>{
        const srcPit=String(rec.r.key||'').split('>')[0];
        let missing=rec.r.targetWmt-(predDayFor(rec.id,rec.r)||0);
        if(missing<=0)return;
        const donors=all.filter(x=>{
          if(prioOf(x.r)!==3||x.r.contractor===rec.r.contractor||!(x.r.dt>0))return false;
          // planning_rules.md §3: a rescue row lands ON the short route's pit,
          // so the pit's wall applies to the DONOR contractor (BLB=RIM, KR=SMA).
          const wall=(((window.PLANNING_RULES||{}).contractors)||{})[canonSrc(srcPit)];
          return !wall||canonCo(x.r.contractor)===canonCo(wall);
        });
        donors.forEach(don=>{
          if(missing<=0)return;
          const helperId=(typeof planDraftSlotId==='function')
            ?planDraftSlotId(don.r.contractor,rec.r.key,{material:'LIM',otype:'TOS'})
            :don.r.contractor+'|'+rec.r.key+'|LIM|TOS';
          let helper=d[helperId];
          if(!helper){
            helper={key:rec.r.key,dt:0,loaders:typeof planNLoaders==='function'?planNLoaders(rec.r):(rec.r.loaders||2),
              contractor:don.r.contractor,
              source:rec.r.source||srcPit,dest:rec.r.dest||String(rec.r.key||'').split('>')[1],
              material:'LIM',otype:'TOS',targetWmt:0,_targetManual:true,
              _preAlloc:{dt:0,pred:0,achv:0,achv_sim:0}};
            d[helperId]=helper;
            all.push({id:helperId,r:helper});
          }
          const hx={id:helperId,r:helper};
          // add donor trucks one at a time until the pending tonnage is covered
          let took=0;
          while(missing>0&&don.r.dt>0){
            don.r.dt-=1;helper.dt+=1;took+=1;
            const hp=predDayFor(helperId,helper)||0;
            const rp=predDayFor(rec.id,rec.r)||0;
            missing=rec.r.targetWmt-rp-hp;
          }
          if(took>0){
            // Helper carries NO target of its own: the tonnage belongs to the
            // short row's target, and a second target would double-count the
            // LIM-TOS bucket (35,333 would read as 42,328). Its contribution
            // shows in Predicted and in the moves log.
            helper.targetWmt=0;
            moved+=took;
            _allocMoves.push({contractor:don.r.contractor+'→'+rec.r.contractor+' work',trucks:took,
              from:don.r.key,from_mat:don.r.material||'',from_otype:don.r.otype||'',
              to:rec.r.key,to_mat:'LIM',to_otype:'TOS',
              tag:'cross-contractor rescue: '+don.r.contractor+' LD covers '+rec.r.contractor+' LIM-TOS',
              reason:'cross-contractor rescue',same_origin:false,dropped:don.r.dt===0});
            movesTxt.push(don.r.contractor+' '+took+' DT: '+don.r.key+' → '+rec.r.key
              +' (cross-contractor rescue — '+don.r.contractor+' hauls '+rec.r.contractor
              +'\u2019s pending LIM-TOS'+(don.r.dt===0?' · LD path dropped':'')+')');
          }
        });
        const finalShort=rec.r.targetWmt
          -(predDayFor(rec.id,rec.r)||0)
          -all.filter(x=>x.r.material==='LIM'&&x.r.otype==='TOS'&&x.r.key===rec.r.key&&x.id!==rec.id)
              .reduce((a,x)=>a+(predDayFor(x.id,x.r)||0),0);
        if(finalShort>rec.r.targetWmt*0.015){
          movesTxt.push('⚠ LIM-TOS still short '+fmt(Math.round(finalShort))+' t/day on '+rec.r.key
            +' even after cross-contractor rescue — no LD trucks left anywhere');
        }
      });
    })();
    // ── Final trim to target (owner, 2026-08-21) ─────────────────────────
    // Rows priced on a SHARED corridor drift above target when later moves
    // change the combined fleet: the P2 fill sized TF>HUAFEI·SMA against a
    // corridor still carrying the whole LD block; the LD split/rescue then
    // took trucks off it, trips/DT rose, and Predicted landed 129% of
    // target with no pass left to hand the surplus back. Re-walk every
    // targeted P1/P2 row down to ~100% AFTER all moves settle and give the
    // freed trucks to the same contractor's TF LD rows (feeding the short
    // side of the S4 50/50 on a day-04 plan). Trim only — shortages stay
    // with the rounds and the warnings.
    (function finalTrim(){
      const dd=draft();
      const pitOf=x=>canonSrc(String(x.r.key||'').split('>')[0]||'');
      const destOf=x=>canonDest(String(x.r.key||'').split('>')[1]||'');
      const brokenWall=x=>{
        const w=(((window.PLANNING_RULES||{}).contractors)||{})[pitOf(x)];
        return !!(w&&canonCo(x.r.contractor)!==canonCo(w));
      };
      for(let round=0;round<4;round++){
        let trimmed=0;
        const all=Object.keys(dd).map(id=>({id,r:dd[id]})).filter(x=>x.r&&!x.r.foreign);
        const byCo={};
        all.forEach(x=>{(byCo[String(x.r.contractor)]=byCo[String(x.r.contractor)]||[]).push(x);});
        Object.keys(byCo).forEach(cont=>{
          const rows=byCo[cont];
          const ldRows=()=>rows.filter(x=>prioOf(x.r)===3&&pitOf(x)==='TF'&&!brokenWall(x));
          function receiver(){
            let lds=ldRows();
            if(!lds.length){
              const hid=(typeof planDraftSlotId==='function')
                ?planDraftSlotId(cont,'TF>HUAFEI',{material:'LIM',otype:'LD'})
                :cont+'|TF>HUAFEI|LIM|LD';
              if(!dd[hid]){
                dd[hid]={key:'TF>HUAFEI',dt:0,loaders:2,contractor:cont,
                  source:'TF',dest:'HUAFEI',material:'LIM',otype:'LD',
                  targetWmt:0,_targetManual:true,
                  _preAlloc:{dt:0,pred:0,achv:0,achv_sim:0}};
                rows.push({id:hid,r:dd[hid]});
              }
              lds=ldRows();
            }
            if(planRulesS4Active()&&lds.length>1){
              const sd=String((((window.PLANNING_RULES||{}).limLd)||{}).splitDest||'POS 6').toUpperCase();
              const pos=lds.filter(x=>destOf(x)===sd);
              const hb=lds.filter(x=>destOf(x)!==sd);
              const sum=l=>l.reduce((a,x)=>a+x.r.dt,0);
              if(pos.length&&sum(pos)<sum(hb))return pos[0];
              if(hb.length)return hb[0];
            }
            return lds.slice().sort((a,b)=>b.r.dt-a.r.dt)[0];
          }
          rows.forEach(x=>{
            const p=prioOf(x.r);
            if((p!==1&&p!==2)||!(x.r.targetWmt>0)||x.r.dt<=1)return;
            const tgt=x.r.targetWmt;
            if(!((predDayFor(x.id,x.r)||0)>tgt*1.01))return;
            const rec=receiver();
            if(!rec||rec.id===x.id)return;
            let took=0,guard=0;
            while(x.r.dt>1&&guard++<400){
              const down=predDayAt(x.id,x.r,x.r.dt-1);
              if(down==null||down<tgt*0.995)break;
              x.r.dt-=1;rec.r.dt+=1;took+=1;
            }
            if(took>0){
              moved+=took;trimmed+=took;
              _allocMoves.push({contractor:cont,trucks:took,
                from:x.r.key,from_mat:x.r.material||'',from_otype:x.r.otype||'',
                to:rec.r.key,to_mat:rec.r.material||'',to_otype:rec.r.otype||'',
                tag:'final trim to target → LD',reason:'final trim to target',
                same_origin:pitOf(x)===canonSrc(String(rec.r.key).split('>')[0]),
                dropped:false});
              movesTxt.push(cont+' '+took+' DT: '+x.r.key+' → '+rec.r.key
                +' (final trim — Predicted drifted over target after corridor moves)');
            }
          });
        });
        if(!trimmed)break;
      }
    })();
    // ── Stage F: priority re-verify + clawback (owner, 2026-08-21) ───────
    // "The system should do things in steps and do these steps carefully."
    // Every stage above can change SHARED-ROAD pricing after a priority row
    // was sized: the LD dump floods the TF corridor, the S4 split loads the
    // POS 12 sections, the rescue and trim move blocks between corridors.
    // Measured on the 2026-11-04 save: TF>FENI KM15 was sized at 72 DT for
    // 10,000 t on a quiet corridor, then 623 LD trucks landed on TF>HUAFEI /
    // TF>POS 12 and the SAME 72 DT re-priced at 6,910 t (sat 0.72) while
    // LIM-LD sat at 121% of target — and the board said "fleet exhausted".
    // The waterfall rounds could not see it: they finish BEFORE the split /
    // rescue / trim, so nothing ever re-read P1 under the final traffic.
    //
    // This stage is the allocator's LAST word on priorities. After all
    // moves settle it re-prices every targeted P1 then P2 row under the
    // FINAL corridor fleet and pulls trucks back from LD ONE AT A TIME,
    // re-pricing after every truck — the corridor decongests as each truck
    // leaves LD, so batch sizing overshoots. Sweeps repeat (max 6) because
    // fixing one row shifts load onto another's sections. Trucks only flow
    // TOWARD priorities here, so sweeps terminate. A truck that fails to
    // add ≥0.5 t/day to the short row is handed straight back: that row is
    // at its road ceiling and needs a second path, not more trucks.
    (function reverifyPriorities(){
      const dd=draft();
      const pitOf=x=>canonSrc(String(x.r.key||'').split('>')[0]||'');
      const broken=x=>{
        const w=(((window.PLANNING_RULES||{}).contractors)||{})[pitOf(x)];
        return !!(w&&canonCo(x.r.contractor)!==canonCo(w));
      };
      const shortOf=x=>{
        if(!(x.r.targetWmt>0))return 0;
        const p=predDayFor(x.id,x.r);
        return (p==null||p>=x.r.targetWmt*0.995)?0:(x.r.targetWmt-p);
      };
      const claw={};   // donor→receiver pair totals, one moves-log line each
      let steps=0;
      const ceilinged={};
      for(let sweep=0;sweep<6;sweep++){
        let movedThisSweep=0;
        const all=Object.keys(dd).map(id=>({id,r:dd[id]})).filter(x=>x.r&&!x.r.foreign);
        const byCo={};
        all.forEach(x=>{(byCo[String(x.r.contractor)]=byCo[String(x.r.contractor)]||[]).push(x);});
        Object.keys(byCo).forEach(cont=>{
          const rows=byCo[cont];
          const ldRows=()=>rows.filter(x=>prioOf(x.r)===3&&x.r.dt>0);
          const tosRows=()=>rows.filter(x=>prioOf(x.r)===2&&x.r.dt>0);
          // Donor order = the waterfall's own priority doctrine: untargeted
          // LD, then targeted LD (on a day-04 plan drain the fatter side of
          // the TF 50/50 so the split stays balanced without a rebalance
          // pass), then — for P1 only, SAP is must-move — LIM-TOS surplus,
          // then LIM-TOS outright.
          function donorFor(prio,recId){
            const not=x=>x.id!==recId;
            const unt=ldRows().filter(x=>not(x)&&!(x.r.targetWmt>0))
              .sort((a,b)=>b.r.dt-a.r.dt)[0];
            if(unt)return unt;
            let lds=ldRows().filter(not);
            if(planRulesS4Active()){
              const tf=lds.filter(x=>pitOf(x)==='TF');
              if(tf.length>1)return tf.sort((a,b)=>b.r.dt-a.r.dt)[0];
            }
            if(lds.length)return lds.sort((a,b)=>b.r.dt-a.r.dt)[0];
            if(prio===1){
              const sur=tosRows().filter(not).find(x=>{
                if(!(x.r.targetWmt>0))return true;
                if(x.r.dt<=1)return false;
                const down=predDayAt(x.id,x.r,x.r.dt-1);
                return down!=null&&down>=x.r.targetWmt*0.995;
              });
              if(sur)return sur;
              return tosRows().filter(not).sort((a,b)=>b.r.dt-a.r.dt)[0]||null;
            }
            return null;
          }
          [1,2].forEach(prio=>{
            rows.filter(x=>prioOf(x.r)===prio&&!broken(x)&&x.r.targetWmt>0)
              .sort((a,b)=>shortOf(b)-shortOf(a))
              .forEach(rec=>{
                let guard=0;
                while(shortOf(rec)>0&&guard++<400&&steps<800){
                  const don=donorFor(prio,rec.id);
                  if(!don)break;
                  const p0=predDayFor(rec.id,rec.r)||0;
                  don.r.dt-=1;rec.r.dt+=1;
                  const p1v=predDayFor(rec.id,rec.r)||0;
                  if(!(p1v>p0+0.5)){
                    // no gain: the row is at its road ceiling — hand the
                    // truck back and stop feeding this receiver
                    don.r.dt+=1;rec.r.dt-=1;
                    ceilinged[rec.id]=true;
                    break;
                  }
                  moved+=1;steps+=1;movedThisSweep+=1;
                  const k=don.id+'\u2192'+rec.id;
                  if(!claw[k])claw[k]={don,rec,n:0};
                  claw[k].n+=1;
                }
              });
          });
        });
        if(!movedThisSweep)break;
      }
      Object.keys(claw).forEach(k=>{
        const c=claw[k];
        const same=pitOf(c.don)===pitOf(c.rec);
        _allocMoves.push({
          contractor:c.rec.r.contractor,trucks:c.n,
          from:c.don.r.key,from_mat:c.don.r.material||'',from_otype:c.don.r.otype||'',
          to:c.rec.r.key,to_mat:c.rec.r.material||'',to_otype:c.rec.r.otype||'',
          tag:'priority re-verify \u2014 corridor re-priced after LD placement',
          reason:'priority re-verify',same_origin:same,dropped:c.don.r.dt===0});
        movesTxt.push(c.rec.r.contractor+' '+c.n+' DT: '+c.don.r.key+' \u2192 '+c.rec.r.key
          +' (re-verify \u2014 P'+prioOf(c.rec.r)+' went short after LD landed on its road'
          +(same?' · same origin':' · cross plan')
          +(c.don.r.dt===0?' · path dropped':'')+')');
      });
      // Re-verify is the final truth on shortfalls: drop earlier "still
      // short" warnings for rows that are now met, and speak plainly about
      // the ones that are not.
      const met={};
      Object.keys(dd).forEach(id=>{
        const r=dd[id];
        if(!r||r.foreign||!(r.targetWmt>0))return;
        const p=predDayFor(id,r);
        if(p!=null&&p>=r.targetWmt*0.995)met[r.key]=true;
      });
      for(let i=movesTxt.length-1;i>=0;i--){
        const t=movesTxt[i];
        if(t.charAt(0)==='\u26a0'&&t.indexOf('short')>=0
          &&Object.keys(met).some(key=>t.indexOf(key)>=0))movesTxt.splice(i,1);
      }
      Object.keys(dd).forEach(id=>{
        const r=dd[id];
        if(!r||r.foreign||!(r.targetWmt>0))return;
        const p=prioOf(r);
        if(p!==1&&p!==2)return;
        const pred=predDayFor(id,r);
        if(pred==null||pred>=r.targetWmt*0.995)return;
        movesTxt.push('\u26a0 '+r.contractor+' '+(p===1?'SAP':'LIM-TOS')+' still short '
          +fmt(Math.round(r.targetWmt-pred))+' t/day on '+r.key+' after re-verify \u2014 '
          +(ceilinged[id]
            ?'road ceiling: more trucks add congestion, not tonnes. Split this target onto a second path.'
            :'no LIM trucks left for '+r.contractor+'.'));
      });
    })();
    // Restore display DT to the pre-alloc plan; the allocation lives in
    // _allocDt. Iterate the DRAFT, not `rows` - crossRescue may have added
    // helper rows that must get the same treatment (their preAlloc dt is 0).
    Object.keys(draft()).forEach(id=>{
      const r=draft()[id];
      if(!r||r.foreign)return;
      r._allocDt=r.dt;
      if(r._preAlloc&&r._preAlloc.dt!=null)r.dt=r._preAlloc.dt;
    });
    _allocMsg=moved
      ?(movesTxt.join('\n')+'\nAllocator v3 · targets run P1 SAP → P2 LIM-TOS → P3 LIM-LD · P1/P2 trimmed to ~100%\nEngine recalculating for new achievable…')
      :(movesTxt.filter(t=>t.indexOf('⚠')===0).length
        ?movesTxt.join('\n')
        :'No moves — SAP is covered, or this contractor has no LIM trucks left to draw from.');
    if(firstPass){
      freezeOriginalCap();
      _allocFrozen=true;
    }
    if(typeof computePlan==='function')computePlan();
    const st=q('plan-alloc-status');
    if(st)st.textContent='recalculating…';
    if(typeof planRunScenario==='function')planRunScenario({preserveFinalize:true,fromAlloc:true});
    else renderAllocView();
    // planning_rules.md §5: whatever this allocation tips into POS must leave
    // for FeNi on IWIP trucks — size them and put them on the road (async;
    // re-renders the alloc view and validation summary when the rows land).
    // The promise is exposed so the allocate wrapper can AWAIT it between
    // passes: pass 2's Stage F must see these trucks (they saturate the POS
    // weighbridges — wb 0.8 on KR>POS 12) or it re-verifies a fiction.
    window._planPosTransitP=planRulesPosTransit()
      // Tenant rows land after the POS rows so the road view carries every
      // fleet on it at once — ours, IWIP's, and the other tenants'.
      .then(()=>planRulesTenants());
  };

  // ── planning_rules.md §5 — POS transit: size IWIP trucks for POS→FeNi ────
  // POS is a transit stockpile: whatever the plan tips into POS 12/14/15/16
  // must leave again for the FeNi plants, moved by IWIP (not contractor)
  // trucks. Those trucks are real road traffic, so they enter the draft as
  // ROAD-ONLY rows (foreign:true — the exact mechanism the app already uses
  // for IWIP/Position traffic): counted by road crowding and shared-section
  // spans, never in production WMT, never touched by the allocator.
  // POS 6 included since 2026-08-25: the owner called it a dump AND a
  // loading (transit-out) point, and the S4 split now tips its leftover LD
  // there — without it here, hundreds of DT of inflow produced ZERO IWIP
  // outflow and §5 rule 2 (POS output must equal input) silently broke.
  function planRulesPosDumps(){return ['POS 6','POS 12','POS 14','POS 15','POS 16'];}
  // planning_rules.md §10.9 — loaders per row = round(DT / trucks-per-loader),
  // the route's measured calibration ratio (n_trucks_ref / n_loaders) served
  // by /api/congestion_model, 15 when unmeasured. "We have to imagine we are
  // using the same number of loaders" (owner, 2026-08-21) — there is no
  // detailed loader plan yet, so this OVERRIDES per-row loader edits on
  // every Allocate.
  const _tplCache={};
  async function planRulesTpl(key){
    if(_tplCache[key]>0)return _tplCache[key];
    const dflt=(((window.PLANNING_RULES||{}).loaders)||{}).trucksPerLoaderDefault||15;
    let tpl=dflt;
    try{
      const r=await fetch('/api/congestion_model?route='+encodeURIComponent(key)
        +'&n_trucks=10',{cache:'no-store'});
      if(r.ok){
        const j=await r.json();
        if(j&&j.ok&&j.trucks_per_loader>0)tpl=j.trucks_per_loader;
      }
    }catch(e){}
    _tplCache[key]=tpl;
    return tpl;
  }
  function planRulesLoadersFor(dt,tpl){return Math.max(1,Math.round(dt/(tpl||15)));}
  async function planRulesApplyLoaders(){
    const d=draft();
    for(const id of Object.keys(d)){
      const r=d[id];
      if(!r||!r.key)continue;
      // Tenant fleets are not ours to resource: we do not schedule their
      // loaders, and their routes (KR>RSF, HUAFEI>RSF) are not in our model,
      // so asking for a trucks-per-loader ratio would fetch a route the
      // calibration has never seen.
      if(typeof planIsTenantRow==='function'?planIsTenantRow(r):r._tenant)continue;
      const dt=workingDt(r);
      if(!(dt>0))continue;
      r.loaders=planRulesLoadersFor(dt, await planRulesTpl(r.key));
    }
  }
  // planHybridCurveFor returns undefined while its fetch is in flight and
  // callers fall back to the legacy cap-scale path. New loader counts mean
  // cold caches, and pricing a whole plan on the legacy path during that
  // window is how the 2026-08-21 blowup got into four saved plans. Wait for
  // every (route, loaders) curve to resolve before anything prices the plan.
  async function planRulesWarmCurves(){
    if(typeof planHybridCurveFor!=='function')return;
    const d=draft();
    const rain=rainMm();
    // Tenant rows are excluded, and this one matters for SPEED. We never price
    // a tenant route ourselves — their cost arrives as background flow — and
    // two of them (KR>RSF, HUAFEI>RSF) are not routes the model has at all, so
    // their curve never resolves. Left in, the wait loop below burned its full
    // 60 x 250 ms on every warm pass, several passes per Allocate: tens of
    // seconds of pure stall waiting for a curve that cannot exist (owner,
    // 2026-08-24: "it takes so much time").
    const rows=Object.keys(d).map(id=>({id:id,r:d[id]}))
      .filter(x=>x.r&&x.r.key&&workingDt(x.r)>0
                 &&!(typeof planIsTenantRow==='function'?planIsTenantRow(x.r,x.id):x.r._tenant))
      .map(x=>x.r);
    // planTripsPerDT prices each route on the PROPORTIONAL saturation curve
    // (rules §10.9 — loaders scale with fleet, only the road congests).
    const keys={};
    rows.forEach(r=>{if(r&&r.key)keys[r.key]=true;});
    for(let i=0;i<60;i++){
      let pending=false;
      Object.keys(keys).forEach(key=>{
        const c=planHybridCurveFor(key, 0, rain, {proportional:true});
        if(c===undefined){pending=true;return;}
        // an INTERIM (stale-background) curve is not undefined — when this
        // plan has background traffic the exact segment-conditioned curve
        // must land before pricing, or walks run on the wrong road state
        const others=typeof planSegOthersFor==='function'?planSegOthersFor(key):null;
        if(others&&Object.keys(others).length&&!c.segment_based)pending=true;
      });
      if(!pending)return;
      await new Promise(res=>setTimeout(res,250));
    }
  }
  // ── section-resolved plan pricing (owner, 2026-08-21) ────────────────
  // "See how many trucks are moving in each window — each section of the
  // route — and what speed that section allows." /api/congestion_plan
  // prices the WHOLE plan over chainage windows; each route's calibrated
  // curve is multiplied by shared_road_ratio (plan flows vs own flows on
  // its windows), so cross-route traffic in a shared window drags every
  // route in it. The window table renders in the validation panel.
  // VISIBILITY ONLY (owner revert, 2026-08-21): the shared_road_ratio in
  // this payload briefly multiplied the pricing curve and collapsed every
  // route ("BLB trips falls like hell") because its capacity basis was the
  // median OBSERVED peak per section. Pricing stays on the calibrated
  // curves; do not re-wire this into planTripsPerDT.
  let _secPricing=null;    // {routes:{...}, sections:[...]} — window table data
  async function planRulesSectionPricing(){
    const d=draft();
    const rows=[];
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||!r.key)return;
      // Same reason as the warm pass: a tenant route is not ours to price, and
      // the RSF ones are not in the section model's node map at all.
      if(typeof planIsTenantRow==='function'?planIsTenantRow(r,id):r._tenant)return;
      const dt=workingDt(r);
      if(!(dt>0))return;
      rows.push({route:r.key,dt:dt,loaders:r.loaders||0,foreign:!!r.foreign});
    });
    if(!rows.length){_secPricing=null;return;}
    try{
      const resp=await fetch('/api/congestion_plan',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({rows:rows,rain_mm:rainMm()})});
      const j=resp.ok?await resp.json():null;
      _secPricing=(j&&j.ok)?j:null;
    }catch(e){_secPricing=null;}
  }

  // One call for "make the draft rules-clean and priced on warm curves":
  // loaders per §10.9, hybrid curves resolved, then the section pricing for
  // the current division. Used by the allocate flow and scripted re-saves.
  window.planRulesPrepare=async function(){
    // Tenant register FIRST. planTenantsOn() gates the tenants=1 flag on every
    // curve fetch and is part of the curve cache key, so loading it after the
    // warm pass priced the whole first Allocate on a clear road and then
    // silently re-fetched under a different key. The owner asked for tenant
    // pricing to hold "specially after we reallocate" — that means it has to
    // be true on pass one, not true eventually.
    if(typeof planTenantsLoad==='function'){try{await planTenantsLoad();}catch(e){}}
    await planRulesApplyLoaders();
    // Segment background (owner, 2026-08-22): snapshot the whole draft's
    // per-route trucks (foreign/IWIP included — they occupy the road) so
    // every curve fetched below is conditioned on the plan's traffic on
    // the shared windows.
    if(typeof planSetSegBackground==='function'){
      const d=draft();
      const bg={};
      Object.keys(d).forEach(id=>{
        const r=d[id];
        if(!r||!r.key)return;
        // Tenant rows are DISPLAY and road-crowding only. Their pricing effect
        // arrives as flow via tenants=1 on the curve, so adding their trucks
        // here as well would charge the same fleet twice — and at our tempo,
        // which is the wrong unit for them (see planTenantsOn in plan.js).
        if(typeof planIsTenantRow==='function'?planIsTenantRow(r):r._tenant)return;
        const n=workingDt(r);
        if(n>0)bg[r.key]=(bg[r.key]||0)+n;
      });
      planSetSegBackground(bg);
    }
    await planRulesWarmCurves();
    await planRulesSectionPricing();
  };
  // Per-DAY tonnes at an explicit fleet — horizon-independent on purpose: the
  // validation bands and POS flows are daily figures whatever the UI shows.
  function predDayAt(id,r,dt){
    const saved=r.dt;
    r.dt=dt;
    const p=predDayFor(id,r);
    r.dt=saved;
    return p;
  }
  async function planRulesTripsFor(key,tonnesDay){
    const pay=((typeof planPayload==='function'?planPayload(key,null):null)||{}).tf||50;
    const tpl=await planRulesTpl(key);
    let tpd=null,calibrated=false,cycle=null,src='default';
    // loaders scale with the asked fleet (§10.9 proportional loaders), so the
    // queue term stays honest at any IWIP fleet size
    async function ask(n){
      const others=typeof planSegOthersFor==='function'?planSegOthersFor(key):null;
      const r=await fetch('/api/congestion_model?route='+encodeURIComponent(key)
        +'&n_trucks='+n+'&n_loaders='+planRulesLoadersFor(n,tpl)
        +(others?'&others='+encodeURIComponent(JSON.stringify(others)):''),
        {cache:'no-store'});
      if(!r.ok)return null;
      const j=await r.json();
      return (j&&j.ok&&j.trips_per_DT_per_day>0)?j:null;
    }
    try{
      let j=await ask(Math.max(1,Math.ceil(tonnesDay/(pay*3))));
      if(j){
        // re-ask at the implied fleet once: trips/DT falls with fleet, so the
        // first guess under-sizes on congested POS corridors
        const dt1=Math.max(1,Math.ceil(tonnesDay/(j.trips_per_DT_per_day*pay)));
        j=(await ask(dt1))||j;
        tpd=j.trips_per_DT_per_day;calibrated=!!j.calibrated;
        cycle=j.cycle_time_minutes;src='hybrid';
      }
    }catch(e){}
    if(!(tpd>0)&&typeof planTripsPerDT==='function'){
      const guess=Math.max(1,Math.ceil(tonnesDay/(pay*3)));
      const e=planTripsPerDT(key,guess,0,null,{nLoaders:planRulesLoadersFor(guess,tpl)});
      if(e&&e.daily>0){tpd=e.daily;src='path model';}
    }
    if(!(tpd>0))tpd=2; // conservative site figure; row is flagged estimated
    const dt=Math.max(1,Math.ceil(tonnesDay/(tpd*pay)));
    return {tripsPerDt:tpd,payload:pay,calibrated:calibrated,cycle:cycle,src:src,
      dt:dt,loaders:planRulesLoadersFor(dt,tpl)};
  }
  async function planRulesPosTransit(){
    const R=window.PLANNING_RULES||{};
    if(!((R.posTransit||{}).enabled))return;
    const d=draft();
    Object.keys(d).forEach(id=>{if(d[id]&&d[id]._posTransit)delete d[id];});
    // §10.9 first: loaders on every row follow the historical ratio, and the
    // POS inflow below must be priced with those loaders on WARM hybrid
    // curves — the legacy fallback path is what inflated the Dec saves
    await planRulesApplyLoaders();
    await planRulesWarmCurves();
    const inflow={};
    Object.keys(d).forEach(id=>{
      const r=d[id];
      if(!r||r.foreign)return;
      const dest=canonDest(String(r.key||'').split('>')[1]||'');
      if(planRulesPosDumps().indexOf(dest)<0)return;
      const dt=workingDt(r);
      if(!(dt>0))return;
      const p=predDayAt(id,r,dt);
      if(p>0)inflow[dest]=(inflow[dest]||0)+p;
    });
    const dumps=Object.keys(inflow);
    _posTransitInfo={rows:[],input:0,output:0};
    for(const dump of dumps){
      // only dumps that actually receive material get outflow rows (§5), and
      // a dump's outflow splits evenly across its listed FeNi routes
      const routes=(R.posTransit.routes||[]).filter(k=>k.indexOf(dump+'>')===0);
      if(!routes.length)continue;
      const share=inflow[dump]/routes.length;
      for(const key of routes){
        const est=await planRulesTripsFor(key,share);
        _posTransitInfo.rows.push({dump:dump,key:key,tonnes:share,dt:est.dt,
          loaders:est.loaders,tripsPerDt:est.tripsPerDt,payload:est.payload,
          cycle:est.cycle,calibrated:est.calibrated,src:est.src});
        _posTransitInfo.input+=share;
        _posTransitInfo.output+=share;
        const id='IWIP|'+key+'|road';
        // dt is IWIP's OWN fleet (planning_rules.md §10.8) — foreign:true
        // keeps it out of every contractor fleet counter and WMT total
        d[id]={key:key,dt:est.dt,loaders:est.loaders,contractor:'IWIP',
          source:key.split('>')[0],dest:key.split('>')[1],
          foreign:true,_posTransit:true,_allocDt:est.dt,
          _preAlloc:{dt:est.dt,pred:0,achv:0,achv_sim:0}};
      }
    }
    // IWIP trucks are on the road now: refresh the section pricing (they
    // occupy windows), then recompute so the plan table, road crowding
    // (▶ Run) and the validation summary all see them — and RE-SIMULATE,
    // because planRunScenario fetched the engine before these rows existed
    // and Achievable must carry their corridor drag too (owner, 2026-08-21:
    // every aspect follows the allocated division).
    await planRulesSectionPricing();
    try{if(typeof computePlan==='function')computePlan();}catch(e){}
    try{renderAllocView();}catch(e){}
    try{renderRulesValidation();}catch(e){}
    if(_posTransitInfo&&_posTransitInfo.rows.length&&typeof planRunScenario==='function'){
      try{planRunScenario({preserveFinalize:true,fromAlloc:true});}catch(e){}
    }
  }

  // ── Other tenants on our road (owner register, 2026-08-24) ───────────────
  // "I didn't see all these new DT in my plan — add them the same as we show
  // the IWIP trucks." Same mechanism as the POS-transit rows above: ROAD-ONLY
  // draft rows (foreign:true) that are counted by road crowding and the
  // shared-section view, never by production WMT, never by the allocator, and
  // never drawn from a contractor pool. Rebuilt on every Allocate.
  //
  // What is DIFFERENT from the IWIP rows, and must stay different: an IWIP row
  // is OUR traffic and enters the segment background as trucks. A tenant row
  // does not — its road cost is already carried as flow by tenants=1 on the
  // curve, at its own tempo rather than ours. The row is what the owner sees;
  // the flow is what the model prices. Two representations of one fleet, so
  // exactly one of them may reach pricing.
  async function planRulesTenants(){
    const d=draft();
    const info=(typeof planTenantsLoad==='function')?await planTenantsLoad():null;
    if(!info||!(info.tenants||[]).length)return;
    const byName={};
    info.tenants.forEach(t=>{byName[String(t.name)]=t;});
    // Drop tenants the register no longer has. Keep the planner's DT for
    // everyone still listed — a wipe-and-rebuild from the register is what
    // made Save look like it did nothing: typed DT never came back.
    Object.keys(d).forEach(id=>{
      if(!d[id]||!d[id]._tenant)return;
      if(!byName[d[id].contractor])delete d[id];
    });
    info.tenants.forEach(t=>{
      const dtReg=Number(t.dt)||0;
      if(!(dtReg>0))return;
      const key=String(t.route||'');
      if(key.indexOf('>')<0)return;
      const id='TENANT|'+t.name+'|road';
      const prev=d[id];
      const dt=(prev&&Number(prev.dt)>0)?Number(prev.dt):dtReg;
      d[id]={key:key,dt:dt,loaders:0,contractor:t.name,
        source:key.split('>')[0],dest:key.split('>')[1],
        foreign:true,_tenant:true,_allocDt:dt,
        _tenantRate:t.trips_per_dt||null,_tenantBasis:t.rate_basis||'',
        _preAlloc:(prev&&prev._preAlloc)||{dt:dt,pred:0,achv:0,achv_sim:0}};
    });
    try{if(typeof computePlan==='function')computePlan();}catch(e){}
    try{renderAllocView();}catch(e){}
  }
  window.planRulesTenants=planRulesTenants;

  // ── planning_rules.md §7 — validation bands + post-run summary ───────────
  function planRulesDailyTpd(id,r,dt){
    const c=typeof planContractor==='function'?planContractor(r.contractor):null;
    const e=typeof planTripsPerDT==='function'
      ?planTripsPerDT(r.key,dt,rainMm(),c,
        typeof planTripOpts==='function'?planTripOpts(id):{selfId:id,nLoaders:r.loaders||2})
      :null;
    return (e&&e.daily>0)?e.daily:null;
  }
  function planRulesRowCheck(id,r,dt){
    const V=((window.PLANNING_RULES||{}).validation)||{};
    const pit=canonSrc(String(r.key||'').split('>')[0]||'');
    const dest=canonDest(String(r.key||'').split('>')[1]||'');
    let band=null;
    if(pit==='BLB'&&V.BLB)band={warn:V.BLB.warnBelow,fail:V.BLB.failBelow,
      lbl:'BLB expects '+V.BLB.minTrips+'–'+V.BLB.maxTrips+' trips/DT/day'};
    else if(pit==='TF'&&V.TF&&(V.TF.routes||[]).some(x=>canonDest(x)===dest))
      band={warn:V.TF.warnBelow,fail:V.TF.failBelow,impossible:true,
        lbl:'TF long haul must stay above '+V.TF.minTrips+' trips/DT/day'};
    if(!band)return null;
    const tpd=planRulesDailyTpd(id,r,dt);
    if(tpd==null)return null;
    const st=tpd<band.fail?'FAIL':tpd<band.warn?'WARN':'PASS';
    return {status:st,tpd:tpd,
      why:tpd.toFixed(2)+' trips/DT/day · '+band.lbl
        +(st==='FAIL'&&band.impossible?' — below '+band.fail+' is impossible':'')};
  }
  function planRulesRowBadgeHtml(chk){
    if(!chk)return '';
    const cls=chk.status==='PASS'?'free':chk.status==='WARN'?'saturated':'overloaded';
    return ' <span class="plan-cong-badge '+cls+'" title="'+esc(chk.why)
      +'">'+chk.status+'</span>';
  }
  function planRulesSummary(){
    const R=window.PLANNING_RULES||{};
    const V=R.validation||{};
    const T=R.targets||{};
    const rows=Object.keys(draft()).map(id=>({id,r:draft()[id]}))
      .filter(x=>x.r&&!x.r.foreign&&workingDt(x.r)>0);
    let sapTgt=0,sapPred=0,tosTgt=0,tosPred=0,ldPred=0;
    rows.forEach(({id,r})=>{
      const dt=workingDt(r);
      const pred=predDayAt(id,r,dt)||0;
      const p=prioOf(r);
      if(p===1){sapTgt+=r.targetWmt||0;sapPred+=pred;}
      else if(p===2){tosTgt+=r.targetWmt||0;tosPred+=pred;}
      else if(p===3){ldPred+=pred;}
    });
    // Sep-Dec 2026 = 122 days; the 4-month totals are PROJECTIONS at this
    // plan's day-rate, labelled as such — one day cannot measure a quarter.
    const DAYS=122;
    const pt=_posTransitInfo||{rows:[],input:0,output:0};
    const band=Number(R.sapFeniBand)||2000;
    const feniSap=(R.fixedRoutes||[]).map(f=>{
      let pred=0, tgt=Number(f.targetWmt)||0;
      rows.forEach(({id,r})=>{
        if(String(r.material||'').toUpperCase()!=='SAP')return;
        const key=(r.key||'').toUpperCase().replace(/\s+/g,' ');
        const want=String(f.path||'').toUpperCase().replace(/\s+/g,' ');
        if(key!==want)return;
        pred+=predDayAt(id,r,workingDt(r))||0;
      });
      const lo=0, hi=tgt+band;
      return {path:f.path, pred:pred, target:tgt, lo:lo, hi:hi,
        ok:pred>=lo&&pred<=hi};
    });
    return {
      sap:{tgt:sapTgt,pred:sapPred,met:sapTgt>0?sapPred>=sapTgt*0.995:null},
      feniSap:feniSap,
      tos:{tgt:tosTgt,pred:tosPred,met:tosTgt>0?tosPred>=tosTgt*0.995:null,
        proj:tosPred*DAYS,target4mo:T.limTosTotal||4600000},
      ld:{pred:ldPred,proj:ldPred*DAYS,target4mo:T.limLdTotal||8000000},
      pos:{input:pt.input,output:pt.output,rows:pt.rows,
        balanced:Math.abs(pt.input-pt.output)<1},
      walls:contractorWallViolations()
    };
  }
  function renderRulesValidation(){
    const host=q('plan-rules-validation');
    if(!host)return;
    if(!_allocFrozen){host.innerHTML='';return;}
    const s=planRulesSummary();
    const yn=v=>v==null?'n/a':v?'YES':'NO';
    const mt=t=>(t/1e6).toFixed(2)+' Mt';
    const pre=
      'VALIDATION SUMMARY\n'
      +'==================\n'
      +'SAP target met:      '+yn(s.sap.met)+'  (target: '+fmt(Math.round(s.sap.tgt))
        +' t/day, actual: '+fmt(Math.round(s.sap.pred))+' t/day)\n'
      +'LIM-TOS target met:  '+yn(s.tos.met)+'  (day target: '+fmt(Math.round(s.tos.tgt))
        +' t/day, actual: '+fmt(Math.round(s.tos.pred))+' t/day · 4-mo projection '
        +mt(s.tos.proj)+' vs '+mt(s.tos.target4mo)+')\n'
      +'LIM-LD total:        '+mt(s.ld.proj)+' projected  (target: '+mt(s.ld.target4mo)+')  ['
        +(s.ld.proj>=s.ld.target4mo?'PASS':'FAIL')+']\n'
      +'POS transit balanced: '+(s.pos.rows.length?yn(s.pos.balanced):'n/a — no POS inflow')
        +(s.pos.rows.length?'  (input: '+fmt(Math.round(s.pos.input))
          +' t, output: '+fmt(Math.round(s.pos.output))+' t)':'')
      +((s.feniSap||[]).length
        ?'\nSAP to POS buffer (2,000 ±2,000): '+s.feniSap.map(x=>
          x.path.replace('>',' → ')+' '+fmt(Math.round(x.pred))+' t/day ['
          +(x.ok?'PASS':'FAIL')+']').join(' · ')
        :'');
    const posRows=s.pos.rows.length
      ?'<table style="margin-top:6px"><thead><tr><th>POS transit (IWIP)</th>'
        +'<th class="r">t/day</th><th class="r">trips/DT</th><th class="r">DT</th>'
        +'<th class="r">Loaders</th><th>basis</th></tr></thead><tbody>'
        +s.pos.rows.map(p=>'<tr><td>'+esc(p.key.replace('>',' → '))+'</td>'
          +'<td class="r">'+fmt(Math.round(p.tonnes))+'</td>'
          +'<td class="r">'+p.tripsPerDt.toFixed(2)+'</td>'
          +'<td class="r">'+p.dt+'</td>'
          +'<td class="r">'+(p.loaders||'—')+'</td>'
          +'<td class="muted">'+esc(p.src)+(p.calibrated?'':' · estimated')+'</td></tr>').join('')
        +'</tbody></table>'
        +'<div class="muted" style="font-size:11px;margin-top:4px">IWIP DT are the IWIP '
        +'fleet’s own trucks (rules §10.8) — not drawn from, or counted in, the '
        +'contractor fleet. Loaders on every row = DT ÷ historical trucks-per-loader '
        +'(route ratio; 15 when unmeasured, rules §10.9).</div>'
      :'';
    const walls=s.walls.length
      ?'<div style="color:#ef4444;margin-top:6px">⚠ contractor wall broken: '
        +s.walls.map(w=>esc(w.key)+' is '+esc(w.contractor)+' (must be '+esc(w.want)+')').join(' · ')
        +'</div>'
      :'';
    // the owner's "windows": trucks, flow vs official capacity and speed on
    // every chainage section this plan loads. Tag is GREEN / YELLOW / RED
    // on v/c at the live following distance (50 m from 2026-08-25).
    function _vcTag(vc){
      const v=+vc;
      if(!Number.isFinite(v)) return '';
      let cls='free', lab='GREEN';
      if(v>1){cls='overloaded';lab='RED';}
      else if(v>=0.7){cls='saturated';lab='YELLOW';}
      return '<span class="plan-cong-badge '+cls+'">'+lab+'</span>';
    }
    const secs=(_secPricing&&_secPricing.sections)||[];
    const capNote=(_secPricing&&_secPricing.basis&&_secPricing.basis.capacity_basis)
      || 'official speed-limit sheets: min bin speed ÷ following distance, one loaded lane';
    const winTable=secs.length
      ?'<table class="cong-pack-tbl" style="margin-top:8px"><thead><tr><th>Road window (section)</th>'
        +'<th class="r">km</th><th class="r">Trucks on it</th><th class="r">Flow/hr</th>'
        +'<th class="r">Cap/hr · loaded lane</th><th class="r">v/c</th><th>Tag</th><th class="r">Speed</th></tr></thead><tbody>'
        +secs.map(x=>{
          const t=_vcTag(x.vc);
          const cell=x.vc>1?'tone-bad':(x.vc>=0.7?'tone-warn':'tone-ok');
          return '<tr><td>'+esc(x.section)+'</td>'
            +'<td class="r">'+x.km+'</td><td class="r">'+x.trucks+'</td>'
            +'<td class="r">'+x.flow_hr+'</td><td class="r">'+x.cap_hr+'</td>'
            +'<td class="r '+cell+'">'+x.vc+'</td>'
            +'<td>'+t+'</td>'
            +'<td class="r">'+x.speed_free_kmh+(x.speed_cong_kmh?' → '+x.speed_cong_kmh:'')+' km/h</td></tr>';
        }).join('')
        +'</tbody></table>'
        +'<div class="muted" style="font-size:11px;margin-top:4px">Road windows are INFORMATION '
        +'only: pricing stays on the calibrated per-route curves. Cap/hr is ONE loaded lane — '
        +'the same trucks/hr as the Congestion packing card (speed × 1000 / 50 m gap). Empty '
        +'trucks use the other carriageway and are not in this cap. Plan Road crowding occupancy '
        +'is that loaded lane too, not 2×. GREEN = v/c &lt; 0.7, YELLOW = 0.7–1.0, '
        +'RED = over capacity. Speed is '
        +'the limit-implied free speed. A demonstrated peak is not a capacity and prices nothing.</div>'
      :'';
    const s4=planRulesS4Active()
      ?' <span class="plan-cong-badge saturated" title="Day-04 plan = Scenario 4: same as S3 '
        +'but leftover LD trucks split 50/50 HUAFEI/BSE vs '+String((((window.PLANNING_RULES||{}).limLd)||{}).splitDest||'POS 6')+'. Compare NEW PREDICTED '
        +'against the day-03 save to see the tonnage effect.">S4 · LD split 50/50</span>'
      :'';
    host.innerHTML=
      '<div class="plan-s2-label" style="margin-top:14px">Planning rules validation'+s4+' '
      +'<span class="muted">(<a href="/planning_rules.md" target="_blank" '
      +'style="color:inherit">planning_rules.md</a> §7 · projections at this day-rate)</span></div>'
      +'<pre style="font-size:11.5px;line-height:1.5;margin:6px 0 0;white-space:pre-wrap">'
      +esc(pre)+'</pre>'+posRows+winTable+walls;
  }

  const _origCompute=window.computePlan;
  if(typeof _origCompute==='function'){
    window.computePlan=function(){
      const r=_origCompute.apply(this,arguments);
      try{renderBoard();}catch(e){}
      if(_allocFrozen)lockHoldingPlan();
      return r;
    };
  }
  if(typeof window.planRenderEstimateColumn==='function'){
    const _origCap=window.planRenderEstimateColumn;
    window.planRenderEstimateColumn=function(){
      const r=_origCap.apply(this,arguments);
      try{renderBoard();}catch(e){}
      return r;
    };
  }

  // Frozen-plan edits used to be swallowed SILENTLY (only Add alerted): the
  // user deleted a row, saw nothing happen internally, and Allocate rebuilt
  // the untouched frozen baseline — "it's showing the old plan, this is
  // nonsense" (owner, 2026-08-21). An edit on a locked plan now offers to
  // unlock and apply in one step, so Check capacity always follows the plan
  // as built on top.
  function _frozenEditGate(what){
    if(!_allocFrozen)return true;
    if(!confirm('Original plan is locked after Allocate. Unlock and '+what
      +'? The New Allocation Plan will be cleared — run Check capacity again after editing.'))return false;
    unfreezeOriginal();
    if(typeof planSetScenarioBtn==='function')planSetScenarioBtn();
    return true;
  }
  if(typeof window.planSet==='function'){
    const _origSet=window.planSet;
    window.planSet=function(id){
      const row=draft()[id];
      const ten=row&&(typeof planIsTenantRow==='function'?planIsTenantRow(row,id):row._tenant);
      if(!ten&&!_frozenEditGate('change this DT'))return;
      return _origSet.apply(this,arguments);
    };
  }
  if(typeof window.planRemove==='function'){
    const _origRm=window.planRemove;
    window.planRemove=function(){
      if(!_frozenEditGate('remove this path'))return;
      return _origRm.apply(this,arguments);
    };
  }
  if(typeof window.planAddPath==='function'){
    const _origAddFrozen=window.planAddPath;
    window.planAddPath=function(){
      if(_allocFrozen){
        alert('Original plan is locked. Unlock to edit DT or add paths, then Check capacity again.');
        return;
      }
      return _origAddFrozen.apply(this,arguments);
    };
  }

  // Allocation prices the whole plan synchronously, so loaders (§10.9) and
  // hybrid curves must be ready BEFORE it runs — cold curves drop pricing
  // onto the clamped legacy path. Callers are fire-and-forget (button,
  // refreeze script), so going async here is safe.
  //
  // §10.9 is also CIRCULAR with allocation: loaders follow the allocated
  // fleet, pricing follows loaders. Without the second pass, rows were
  // sized on the saved plan's loaders and then repriced after Allocate —
  // measured 2026-09-04: the trimmed P2 row re-landed at 88% of target.
  // One relaxation pass closes it: allocate, set loaders from that
  // allocation's DT, allocate again on the loaders the plan will show.
  {
    const _allocCoreRun=window.planAllocatePriority;
    let _allocRunning=false;
    function planSetAllocFrontBusy(on){
      const overlay=q('plan-alloc-frontload');
      if(overlay)overlay.hidden=!on;
      const btn=q('plan-alloc-priority-btn');
      if(btn){
        btn.disabled=!!on;
        btn.setAttribute('aria-busy',on?'true':'false');
      }
      const wrap=q('plan-alloc-wrap');
      const panel=q('plan-scenario-panel');
      const busy=q('plan-alloc-busy');
      if(on){
        if(panel)panel.style.display='block';
        if(wrap)wrap.style.display='';
        if(busy)busy.classList.add('is-busy');
      }else if(busy){
        busy.classList.remove('is-busy');
      }
    }
    window.planAllocatePriority=async function(){
      if(_allocRunning)return;
      _allocRunning=true;
      planSetAllocFrontBusy(true);
      try{
        try{await window.planRulesPrepare();}catch(e){}
        const r1=_allocCoreRun.apply(this,arguments);
        try{
          // §5 IWIP POS-transit rows from pass 1 must be ON THE ROAD before
          // pass 2 runs: they load the POS weighbridges (wb 0.8 on KR>POS 12
          // measured 2026-08-21) and pass 2's Stage F re-verifies priorities
          // against exactly that traffic. Without this await pass 2 raced
          // the async sizing and judged targets on an empty bridge.
          try{await window._planPosTransitP;}catch(e){}
          await window.planRulesPrepare();   // applyLoaders reads _allocDt now
          let r2=_allocCoreRun.apply(this,arguments);
          try{await window._planPosTransitP;}catch(e){}
          // Steps done carefully (owner, 2026-08-21): pass 2's Stage F can
          // still be undone by traffic that lands AFTER it — the §5 IWIP
          // sizing is async AND its weighbridge shares resolve on a second
          // async fetch (annotatePathWb), so KR>POS 12 only shows wb 0.8
          // once both have landed. SETTLE FIRST (engine idle + a beat for
          // the bridge annotations), then judge the finished pass with the
          // same pricing the board uses; while any targeted P1/P2 row is
          // short, run another full pass with all traffic frozen in.
          // Three passes bound the loop.
          for(let extra=0;extra<3;extra++){
            if(typeof window.planWhenScenarioIdle==='function'){
              try{await window.planWhenScenarioIdle();}catch(e){}
            }
            await new Promise(res=>setTimeout(res,1500));
            const short=(typeof window.planAllocShortfalls==='function')
              ?window.planAllocShortfalls():[];
            if(!short.length)break;
            await window.planRulesPrepare();
            r2=_allocCoreRun.apply(this,arguments);
            try{await window._planPosTransitP;}catch(e){}
          }
          if(typeof window.planWhenScenarioIdle==='function'){
            await window.planWhenScenarioIdle();
          }
          return r2;
        }catch(e){return r1;}
      }finally{
        if(typeof window.planWhenScenarioIdle==='function'){
          try{await window.planWhenScenarioIdle();}catch(e){}
        }
        planSetAllocFrontBusy(false);
        _allocRunning=false;
      }
    };
  }

  // planning_rules.md §3 — pick the pit's contractor BEFORE the row is
  // created, so the draft slot id (contractor|key|material) is born correct
  // instead of renamed afterwards. Road-only rows are exempt: the walls
  // govern contractor haulage, not IWIP/Position traffic.
  if(typeof window.planAddPath==='function'){
    const _origAddWall=window.planAddPath;
    window.planAddPath=function(){
      try{
        const foreign=typeof planForeignOn==='function'&&planForeignOn();
        const src=canonSrc(((q('plan-src')||{}).value)||'');
        const want=(((window.PLANNING_RULES||{}).contractors)||{})[src];
        const sel=q('plan-contractor');
        if(!foreign&&want&&sel&&canonCo(sel.value)!==canonCo(want)){
          const opt=Array.prototype.find.call(sel.options||[],
            o=>canonCo(o.value)===canonCo(want));
          if(opt){
            sel.value=opt.value;
            sel.dispatchEvent(new Event('change',{bubbles:true}));
          }
        }
      }catch(e){}
      return _origAddWall.apply(this,arguments);
    };
  }

  loadYearlyTargets();
})();
