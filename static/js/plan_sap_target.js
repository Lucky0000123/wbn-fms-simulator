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
      Object.keys(snap.paths||{}).forEach(id=>{
        const r=draft()[id];
        if(!r)return;
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
      stampYearlyTargets();
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
    return e?r.dt*e.daily*pay.tf:null;
  }

  function decorateRowTargets(rows){
    const d=draft();
    Array.from(rows.querySelectorAll('.plan-mat-tag[data-matid]')).forEach(tag=>{
      const id=tag.getAttribute('data-matid');
      const r=d[id];
      if(!r||r.foreign)return;
      const isSap=(r.material||'')==='SAP';
      const p=prioOf(r);
      const hasTarget=r.targetWmt>0;
      const existing=tag.parentNode.querySelector('.plan-sap-chip[data-sapid="'+CSS.escape(id)+'"]');
      const label=hasTarget?('🎯 '+fmt(r.targetWmt)+' t'):'＋ target';
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
        +'style="font-size:9px;padding:1px 6px;border-radius:8px;cursor:pointer;vertical-align:middle;'
        +'background:'+col[0]+';color:'+col[1]
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
    inp.style.cssText='width:64px;font-size:9px;background:transparent;color:#4ade80;border:none;outline:none';
    chip.textContent='🎯 ';
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
    if(_allocFrozen)renderAllocView();
  }

  function boardHtml(targets){
    const rain=rainMm();
    const body=targets.map(({id,r})=>{
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const pred=predDayFor(id,r);
      const achv=achievableShare(r.key,r.dt);
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
      let oP=0,nP=0,oA=0,nA=0,T=0;
      targets.forEach(({id,r})=>{
        const pre=r._preAlloc||{};
        T+=r.targetWmt||0;
        oP+=pre.pred||0; oA+=pre.achv||0;
        nP+=predDayFor(id,r)||0;
        nA+=achievableShare(r.key,r.dt)||0;
      });
      const cell=(v,l,cls)=>'<div class="kpi" style="margin-right:18px;display:inline-block">'
        +'<div style="font-size:17px;font-weight:700;color:'+cls+'">'+fmt(v)+'</div>'
        +'<div style="font-size:10px;color:var(--muted,#8b98a5);text-transform:uppercase">'+l+'</div></div>';
      strip='<div style="margin:8px 0 2px">'
        +cell(T,'target · t/day','#e6edf3')
        +cell(nP,'new predicted','#4ade80')
        +cell(oP,'old predicted','#8b98a5')
        +cell(nA,'new achievable','#93c5fd')
        +cell(oA,'old achievable','#8b98a5')
        +'</div>'
        +'<div class="muted" style="font-size:10.5px;margin:0 0 6px">P1+P2 rows only. Predicted = path model · Achievable = this row\u2019s share of simulate. Same rain on old and new. Never averaged.</div>';
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
      +(_allocMsg?('<div class="muted" style="font-size:11px;margin-top:5px;white-space:pre-wrap">'+esc(_allocMsg)+'</div>'):'')
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
    ['plan-alloc-hero','plan-alloc-buckets','plan-alloc-holding','plan-alloc-moves','plan-alloc-estimate']
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
    return {dt:r.dt,pred:c.pred||0,achv:c.achv||0,achv_sim:c.sim||0};
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
      paintSavedAfter(_savedAlloc);
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
        .sort((a,b)=>{
          const pa=prioOf(a.r), pb=prioOf(b.r);
          const ra=pa===1?1:pa===2?2:pa===3?3:9;
          const rb=pb===1?1:pb===2?2:pb===3?3:9;
          return ra-rb||String(a.r.contractor||'').localeCompare(b.r.contractor||'')
            ||String(a.r.key||'').localeCompare(b.r.key||'');
        });
      const srcOf=r=>typeof planHoldSrc==='function'?planHoldSrc(r):(r.source||(r.key||'').split('>')[0]||'');
      const colOf=src=>typeof planSrcColour==='function'?planSrcColour(src):'#64748b';
      const body=ids.map(({id,r})=>{
        const dtNow=workingDt(r);
        if(!(dtNow>0))return '';
        const src=srcOf(r),col=colOf(src);
        const dtOld=r._preAlloc!=null?r._preAlloc.dt:r.dt;
        const clkNew=rowClocks(id,r,dtNow);
        const clkOld=rowClocks(id,r,dtOld);
        const tgt=r.targetWmt||0;
        const achv=clkNew.achv;
        const achvOld=r._preAlloc&&r._preAlloc.achv!=null?r._preAlloc.achv:clkOld.achv;
        const mat=String(r.material||'—')+(r.otype?' · '+r.otype:'')+(r.foreign?' · road':'');
        const p=prioOf(r);
        const prio=p===1?'P1':p===2?'P2':p===3?'P3':'';
        const prioHtml=prio
          ?'<span style="font-size:9px;padding:0 5px;border-radius:7px;margin-right:4px;'
            +(p===1?'background:rgba(34,197,94,.15);color:#4ade80'
             :p===2?'background:rgba(96,165,250,.15);color:#93c5fd'
             :'background:rgba(148,163,184,.15);color:#94a3b8')+'">'+prio+'</span>'
          :'';
        const rpOld=ratePair(clkOld.pred, clkOld.trips, dtOld);
        const rpNew=ratePair(clkNew.pred, clkNew.trips, dtNow);
        return '<tr class="plan-hold-src" style="--src:'+col+'" data-prio="'+(p||9)+'"'
          +' data-dt="'+(dtNow||0)+'" data-dt-old="'+(dtOld||0)+'" data-dt-new="'+(dtNow||0)+'"'
          +' data-trips="'+(clkNew.trips||0)+'" data-trips-old="'+(clkOld.trips||0)+'" data-trips-new="'+(clkNew.trips||0)+'"'
          +' data-pred="'+(clkNew.pred||0)+'" data-pred-old="'+(clkOld.pred||0)+'" data-pred-new="'+(clkNew.pred||0)+'"'
          +' data-achv="'+(achv||0)+'" data-achv-old="'+(achvOld||0)+'" data-achv-new="'+(achv||0)+'"'
          +' data-tgt="'+(tgt||0)+'">'
          +'<td class="plan-hold-path"><span class="plan-hold-dot" aria-hidden="true"></span>'
          +prioHtml+'<b>'+esc(r.key.replace('>',' → '))+'</b></td>'
          +'<td><span class="plan-hold-co">'+esc(r.contractor)+'</span></td>'
          +'<td class="plan-hold-mat"><span class="plan-mat-tag" title="'+esc(mat)+'">'+esc(mat)+'</span></td>'
          +allocMetricTds({
            tgt:tgt, dtOld:dtOld, dtNew:dtNow,
            tpdOld:rpOld.tpd, tpdNew:rpNew.tpd,
            wpdOld:rpOld.wpd, wpdNew:rpNew.wpd,
            predOld:clkOld.pred, predNew:clkNew.pred,
            achvOld:achvOld, achvNew:achv,
            valHtml:r.foreign?'':planRulesRowBadgeHtml(planRulesRowCheck(id,r,dtNow))
          })
          +'</tr>';
      }).join('');
      const nShow=ids.filter(x=>workingDt(x.r)>0).length;
      hold.setAttribute('data-hz', hzLab);
      hold.innerHTML=
        '<div class="plan-holding-head"><h3>New Allocation Plan</h3>'
        +allocPrioFilterBar()
        +'<div class="sub">'+nShow+' path'+(nShow===1?'':'s')+' · per '+esc(hzLab)
        +' · new on top · was = before Allocate</div></div>'
        +'<div class="plan-holding-table"><table>'
        +allocTableHead()
        +'<tbody>'+(body||'<tr><td colspan="9" class="muted">No paths</td></tr>')+'</tbody>'
        +allocTableFoot(hzLab, nShow)
        +'</table></div>';
      applyAllocPrioFilter();
    }
    const mv=q('plan-alloc-moves');
    if(mv)mv.textContent=_allocMsg||'';
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
      const dtNow=workingDt(r);
      const clk=rowClocks(id,r,dtNow);
      const pre=r._preAlloc||{};
      const clkOld=pre.dt!=null?rowClocks(id,r,pre.dt):clk;
      return {
        id:id, key:r.key, contractor:r.contractor||'',
        material:r.material||'', otype:r.otype||'', prio:prioOf(r),
        target:r.targetWmt||0, foreign:!!r.foreign,
        dt_before:pre.dt!=null?pre.dt:r.dt, dt_after:dtNow,
        pred_before:Math.round(pre.pred!=null?pre.pred:(clkOld.pred||0)),
        pred_after:Math.round(clk.pred||0),
        achv_before:Math.round(pre.achv||0),
        achv_after:Math.round(clk.achv||0),
        achv_sim:Number.isFinite(clk.sim)?Math.round(clk.sim):null,
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
    return {
      frozen:true,
      horizon:hzLab,
      old:_origTotals||{pred:null,achv:null,dt:filled.fleetWas},
      cap:'none',
      new:{pred:newPred, achv:newAchv,
        achv_sim:filled.simComplete?Math.round(filled.achvSimTotal):null,
        dt:filled.fleet, target:goals.total},
      calculation_status:filled.simComplete?'complete':'simulation_pending',
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
    const sorted=(rows||[]).slice().sort((a,b)=>{
      const pa=a.prio===1?1:a.prio===2?2:a.prio===3?3:9;
      const pb=b.prio===1?1:b.prio===2?2:b.prio===3?3:9;
      return pa-pb||String(a.contractor||'').localeCompare(b.contractor||'')
        ||String(a.key||'').localeCompare(b.key||'');
    });
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
      const mat=String(r.material||'—')+(r.otype?' · '+r.otype:'');
      return '<tr data-prio="'+(p||9)+'" data-dt="'+(dtNew||0)+'"'
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

  function paintSavedAfter(alloc){
    if(!alloc)return;
    const wrap=q('plan-alloc-wrap');
    if(wrap)wrap.style.display='';
    const hzLab=alloc.horizon||'day';
    const old=alloc.old||{};
    const neu=alloc.new||{};
    const fleet=alloc.fleet||{};
    const hero=q('plan-alloc-hero');
    const afterT=(function(){
      let pred=0,achv=0,tgt=0;
      (alloc.rows||[]).forEach(r=>{
        if(!(r.dt_after>0))return;
        pred+=r.pred_after||0; tgt+=r.target||0;
        achv+=(r.achv_sim!=null?r.achv_sim:r.achv_after)||0;
      });
      return {pred,achv,tgt};
    })();
    const beforeT=(function(){
      let pred=0,achv=0;
      (alloc.rows||[]).forEach(r=>{
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
      hold.innerHTML=
      '<div class="plan-holding-head"><h3>New Allocation Plan</h3>'
      +allocPrioFilterBar()
      +'<div class="sub">saved with this plan · per '+esc(hzLab)
      +' · new on top · was = before Allocate</div></div>'
      +savedRowsTable(alloc.rows||[], 'after', hzLab);
      applyAllocPrioFilter();
    }
    const mv=q('plan-alloc-moves');
    if(mv){
      const n=alloc.moved_total!=null?alloc.moved_total
        :(alloc.moves||[]).reduce((a,m)=>a+(m.trucks||0),0);
      mv.textContent=(n?n+' DT moved\n':'')+(alloc.notes||'');
    }
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
  };

  window.planAllocatePriority=function(){
    const d=draft();
    const rows=Object.keys(d).map(id=>({id,r:d[id]})).filter(x=>x.r&&!x.r.foreign);
    if(!rows.length)return;
    const rain=rainMm();
    const firstPass=!_allocFrozen;
    _allocMoves=[];
    _savedAlloc=null;
    rows.forEach(({id,r})=>{
      if(!r._preAlloc)r._preAlloc=snapshotRow(id,r);
      r.dt=r._preAlloc.dt;
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
        const split=(((window.PLANNING_RULES||{}).limLd)||{}).split;
        if(!split||!(split.pos12>0))return;
        const dd=draft();
        const destOf=x=>canonDest(String(x.r.key||'').split('>')[1]||'');
        const isPos12=x=>destOf(x)==='POS 12';
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
        const wantPos=Math.round(total*split.pos12);
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
        if(havePos()<wantPos&&!posRows.length)helper('TF>POS 12');
        if(havePos()>wantPos&&!hbRows.length)helper('TF>HUAFEI');
        let guard=0;
        while(havePos()<wantPos&&guard++<500){
          const don=hbRows.filter(x=>x.r.dt>0).sort((a,b)=>b.r.dt-a.r.dt)[0];
          const rec=posRows.slice().sort((a,b)=>a.r.dt-b.r.dt)[0];
          if(!don||!rec)break;
          if(transfer(don,rec,Math.min(wantPos-havePos(),don.r.dt),
            'P3 50/50 split — leftovers → POS 12 (planning rules §4)',true)<=0)break;
        }
        while(havePos()>wantPos&&guard++<500){
          const don=posRows.filter(x=>x.r.dt>0).sort((a,b)=>b.r.dt-a.r.dt)[0];
          const rec=hbRows.slice().sort((a,b)=>a.r.dt-b.r.dt)[0];
          if(!don||!rec)break;
          if(transfer(don,rec,Math.min(havePos()-wantPos,don.r.dt),
            'P3 50/50 rebalance — POS 12 → HUAFEI/BSE (planning rules §4)',true)<=0)break;
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
              const pos=lds.filter(x=>destOf(x)==='POS 12');
              const hb=lds.filter(x=>destOf(x)!=='POS 12');
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
    planRulesPosTransit();
  };

  // ── planning_rules.md §5 — POS transit: size IWIP trucks for POS→FeNi ────
  // POS is a transit stockpile: whatever the plan tips into POS 12/14/15/16
  // must leave again for the FeNi plants, moved by IWIP (not contractor)
  // trucks. Those trucks are real road traffic, so they enter the draft as
  // ROAD-ONLY rows (foreign:true — the exact mechanism the app already uses
  // for IWIP/Position traffic): counted by road crowding and shared-section
  // spans, never in production WMT, never touched by the allocator.
  function planRulesPosDumps(){return ['POS 12','POS 14','POS 15','POS 16'];}
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
    const rows=Object.keys(d).map(id=>d[id])
      .filter(r=>r&&r.key&&workingDt(r)>0);
    // planTripsPerDT prices each route at its COMBINED loaders (rows share
    // the road and its faces), so warm exactly those keys — per-row keys
    // would warm curves nothing asks for.
    const comb={};
    rows.forEach(r=>{
      if(!r.foreign)comb[r.key]=(comb[r.key]||0)+(r.loaders||2);
    });
    rows.forEach(r=>{if(comb[r.key]==null)comb[r.key]=r.loaders||2;});
    for(let i=0;i<60;i++){
      let pending=false;
      Object.keys(comb).forEach(key=>{
        if(planHybridCurveFor(key, comb[key], rain)===undefined)pending=true;
      });
      if(!pending)return;
      await new Promise(res=>setTimeout(res,250));
    }
  }
  // One call for "make the draft rules-clean and priced on warm curves":
  // loaders per §10.9, then hybrid curves resolved. Used by the allocate
  // flow and by scripted re-saves.
  window.planRulesPrepare=async function(){
    await planRulesApplyLoaders();
    await planRulesWarmCurves();
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
      const r=await fetch('/api/congestion_model?route='+encodeURIComponent(key)
        +'&n_trucks='+n+'&n_loaders='+planRulesLoadersFor(n,tpl),{cache:'no-store'});
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
    // IWIP trucks are on the road now: recompute so the plan table, road
    // crowding (▶ Run) and the validation summary all see them — and
    // RE-SIMULATE, because planRunScenario fetched the engine before these
    // rows existed and Achievable must carry their corridor drag too
    // (owner, 2026-08-21: every aspect follows the allocated division).
    try{if(typeof computePlan==='function')computePlan();}catch(e){}
    try{renderAllocView();}catch(e){}
    try{renderRulesValidation();}catch(e){}
    if(_posTransitInfo&&_posTransitInfo.rows.length&&typeof planRunScenario==='function'){
      try{planRunScenario({preserveFinalize:true,fromAlloc:true});}catch(e){}
    }
  }

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
    const V=((window.PLANNING_RULES||{}).validation)||{};
    const T=((window.PLANNING_RULES||{}).targets)||{};
    const rows=Object.keys(draft()).map(id=>({id,r:draft()[id]}))
      .filter(x=>x.r&&!x.r.foreign&&workingDt(x.r)>0);
    const ranges={BLB:[],TF:[]};
    let sapTgt=0,sapPred=0,tosTgt=0,tosPred=0,ldPred=0;
    rows.forEach(({id,r})=>{
      const dt=workingDt(r);
      const chk=planRulesRowCheck(id,r,dt);
      if(chk){
        const pit=canonSrc(String(r.key||'').split('>')[0]||'');
        if(ranges[pit])ranges[pit].push(chk);
      }
      const pred=predDayAt(id,r,dt)||0;
      const p=prioOf(r);
      if(p===1){sapTgt+=r.targetWmt||0;sapPred+=pred;}
      else if(p===2){tosTgt+=r.targetWmt||0;tosPred+=pred;}
      else if(p===3){ldPred+=pred;}
    });
    function rangeLine(pit){
      const l=ranges[pit];
      if(!l.length)return {txt:'no '+pit+' routes in plan',status:'—'};
      const mn=Math.min.apply(null,l.map(c=>c.tpd)),mx=Math.max.apply(null,l.map(c=>c.tpd));
      const st=l.some(c=>c.status==='FAIL')?'FAIL':l.some(c=>c.status==='WARN')?'WARN':'PASS';
      return {txt:mn.toFixed(2)+' - '+mx.toFixed(2),status:st};
    }
    // Sep-Dec 2026 = 122 days; the 4-month totals are PROJECTIONS at this
    // plan's day-rate, labelled as such — one day cannot measure a quarter.
    const DAYS=122;
    const pt=_posTransitInfo||{rows:[],input:0,output:0};
    return {
      blb:rangeLine('BLB'), tf:rangeLine('TF'),
      sap:{tgt:sapTgt,pred:sapPred,met:sapTgt>0?sapPred>=sapTgt*0.995:null},
      tos:{tgt:tosTgt,pred:tosPred,met:tosTgt>0?tosPred>=tosTgt*0.995:null,
        proj:tosPred*DAYS,target4mo:T.limTosTotal||4600000},
      ld:{pred:ldPred,proj:ldPred*DAYS,target4mo:T.limLdTotal||8000000},
      pos:{input:pt.input,output:pt.output,rows:pt.rows,
        balanced:Math.abs(pt.input-pt.output)<1},
      walls:contractorWallViolations()
    };
  }
  function renderRulesValidation(){
    const moves=q('plan-alloc-moves');
    if(!moves)return;
    let host=q('plan-rules-validation');
    if(!host){
      host=document.createElement('div');
      host.id='plan-rules-validation';
      moves.insertAdjacentElement('afterend',host);
    }
    if(!_allocFrozen){host.innerHTML='';return;}
    const s=planRulesSummary();
    const yn=v=>v==null?'n/a':v?'YES':'NO';
    const mt=t=>(t/1e6).toFixed(2)+' Mt';
    const pre=
      'VALIDATION SUMMARY\n'
      +'==================\n'
      +'BLB trips/DT range:  '+s.blb.txt+'  ['+s.blb.status+']\n'
      +'TF trips/DT range:   '+s.tf.txt+'  ['+s.tf.status+']\n'
      +'SAP target met:      '+yn(s.sap.met)+'  (target: '+fmt(Math.round(s.sap.tgt))
        +' t/day, actual: '+fmt(Math.round(s.sap.pred))+' t/day)\n'
      +'LIM-TOS target met:  '+yn(s.tos.met)+'  (day target: '+fmt(Math.round(s.tos.tgt))
        +' t/day, actual: '+fmt(Math.round(s.tos.pred))+' t/day · 4-mo projection '
        +mt(s.tos.proj)+' vs '+mt(s.tos.target4mo)+')\n'
      +'LIM-LD total:        '+mt(s.ld.proj)+' projected  (target: '+mt(s.ld.target4mo)+')  ['
        +(s.ld.proj>=s.ld.target4mo?'PASS':'FAIL')+']\n'
      +'POS transit balanced: '+(s.pos.rows.length?yn(s.pos.balanced):'n/a — no POS inflow')
        +(s.pos.rows.length?'  (input: '+fmt(Math.round(s.pos.input))
          +' t, output: '+fmt(Math.round(s.pos.output))+' t)':'');
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
    const s4=planRulesS4Active()
      ?' <span class="plan-cong-badge saturated" title="Day-04 plan = Scenario 4: same as S3 '
        +'but leftover LD trucks split 50/50 HUAFEI/BSE vs POS 12. Compare NEW PREDICTED '
        +'against the day-03 save to see the tonnage effect.">S4 · LD split 50/50</span>'
      :'';
    host.innerHTML=
      '<div class="plan-s2-label" style="margin-top:14px">Planning rules validation'+s4+' '
      +'<span class="muted">(<a href="/planning_rules.md" target="_blank" '
      +'style="color:inherit">planning_rules.md</a> §7 · projections at this day-rate)</span></div>'
      +'<pre style="font-size:11.5px;line-height:1.5;margin:6px 0 0;white-space:pre-wrap">'
      +esc(pre)+'</pre>'+posRows+walls;
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
    window.planSet=function(){
      if(!_frozenEditGate('change this DT'))return;
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
          await window.planRulesPrepare();   // applyLoaders reads _allocDt now
          const r2=_allocCoreRun.apply(this,arguments);
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
