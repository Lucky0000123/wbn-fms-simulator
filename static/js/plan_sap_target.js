// ── Priority targets in the plan (owner 2026-08-13 / 2026-08-14) ─────────────
// P1 = SAP (must-move). Predicted sits AT the target, never well above.
// P2 = LIM from TOS. Filled after SAP. MAY exceed its target when a
//      contractor still has leftover trucks (they have to live somewhere).
// P3 = LIM from LD (lowest priority; first donor; leftover trucks land here).
// Allocate: same contractor, same origin first.
//   1. SAP extra → SAP still short.
//   2. Remaining SAP shortfall from LIM-LD, then LIM-TOS, until Predicted
//      meets target. P2/P3 may go to 0 DT — a 1-truck leftover path is not
//      a real plan (it still needs a loader and a dump). requiredDt is not the stop.
//   3. LIM-TOS extra → LIM-TOS still short.
//   4. Remaining LIM-TOS shortfall from LIM-LD, then SAP extra.
//   5. Trim SAP to Predicted ≈ target. Leftover trucks → TOS short, then LD,
//      then any same-contractor P2 even if that P2 is already over.
//   6. P2 surplus is only dumped to other TOS shorts or LD — never back to SAP.
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

  let _allocFrozen=false;
  let _allocMsg='';
  let _allocMoves=[];
  let _origTotals=null;
  let _savedAlloc=null;
  let _yearlyRows=null;
  let _yearlyMonth=null;
  let _allocPrioFilter='';
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
      +'<td class="r">'+pairHtml(o.tpdOld, o.tpdNew, {fmt:fmt2})+'</td>'
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

  // P1 SAP, P2 LIM TOS, P3 LIM LD (and anything else that is not protected).
  // Origin type from the year matrix wins; a missing chip does not turn SAP
  // into a donor, and a typed target does not protect LD limonite.
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
  function isProtected(r){const p=prioOf(r);return p===1||p===2;}

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
        ?'LIM from LD — t/day target for this row. Allocate still treats LD as lowest priority.'
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
    const dt=planDtForWmt(key,perShift,rain,contractor,{selfId:selfId});
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
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rainMm(),c,{selfId:id}):null;
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
               :p===3?'LIM from LD — click to set the t/day target. Allocate still treats LD as lowest priority.'
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
      +'<button type="button" class="ms-btn" onclick="planAllocatePriority()" '
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
      el.title='Original plan is locked. Unlock to edit DT, then Check capacity again.';
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
    const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,n,rainMm(),c,{selfId:id}):null;
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
      sap:{key:'sap',label:'SAP · must-move',cls:'sap',target:0,pred:0,achv:0,achvSim:0,dt:0,n:0,dtWas:0,predWas:0,achvWas:0},
      tos:{key:'tos',label:'LIM-TOS · priority 2',cls:'tos',target:0,pred:0,achv:0,achvSim:0,dt:0,n:0,dtWas:0,predWas:0,achvWas:0},
      ld:{key:'ld',label:'Other LIM · LD buffer',cls:'ld',target:0,pred:0,achv:0,achvSim:0,dt:0,n:0,dtWas:0,predWas:0,achvWas:0}
    };
    let fleet=0,fleetWas=0,hasWas=false,predTotal=0,achvTotal=0,achvSimTotal=0;
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
      achvSimTotal+=clk.sim||0;
      const k=bucketOf(r);
      if(!k)return;
      const b=B[k];
      if(dtNow>0)b.n+=1;
      b.dt+=dtNow||0;
      b.target+=r.targetWmt>0?r.targetWmt:0;
      b.pred+=clk.pred||0;
      b.achv+=clk.achv||0;
      b.achvSim+=clk.sim||0;
      if(r._preAlloc){
        b.dtWas+=r._preAlloc.dt||0;
        b.predWas+=r._preAlloc.pred||0;
        b.achvWas+=r._preAlloc.achv||0;
      }else{
        b.dtWas+=r.dt||0;
      }
    });
    return {B:B,hzLab:hzLab,fleet:fleet,fleetWas:fleetWas,hasWas:hasWas,predTotal:predTotal,achvTotal:achvTotal,achvSimTotal:achvSimTotal};
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
            achvOld:achvOld, achvNew:achv
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
  }
  window.planRenderAllocView=renderAllocView;

  function packBucket(b){
    return {n:b.n, target:Math.round(b.target||0),
      dt_before:Math.round(b.dtWas||0), dt_after:Math.round(b.dt||0),
      pred_before:Math.round(b.predWas||0), pred_after:Math.round(b.pred||0),
      achv_before:Math.round(b.achvWas||0), achv_after:Math.round(b.achv||0),
      achv_sim:Math.round(b.achvSim||0)};
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
        achv_sim:Math.round(clk.sim||0),
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
      new:{pred:newPred, achv:newAchv, achv_sim:filled.achvSimTotal||null, dt:filled.fleet, target:goals.total},
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
      ld:{label:'Other LIM · LD buffer',cls:'ld'}
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
      function donorSpare(list, keep){
        const k=keep==null?0:keep;
        return list.reduce((a,x)=>a+Math.max(0,x.r.dt-k),0);
      }
      // Smallest DT that still meets ~target. Inverse of requiredDt is the
      // wrong surplus on a saturated path: extra trucks barely add tonnes so
      // the inverse still "needs" the whole fleet even when Predicted is
      // already thousands above target (TF→FENI KM15 16 kt vs 10 kt).
      function minDtForTarget(x){
        if(!(x.r.targetWmt>0)||x.r.dt<=1)return x.r.dt;
        const pred=predOf(x);
        if(pred==null||pred<x.r.targetWmt*0.995)return x.r.dt;
        const tgt=x.r.targetWmt*0.995;
        let lo=1, hi=Math.floor(x.r.dt), best=x.r.dt;
        while(lo<=hi){
          const mid=(lo+hi)>>1;
          const p=predAt(x, mid);
          if(p!=null&&p>=tgt){best=mid;hi=mid-1;}
          else lo=mid+1;
        }
        // The contractor clamp makes Predicted lumpy in DT, so the binary
        // search can stop early/late. Walk to the true boundary linearly.
        while(best>1){
          const p=predAt(x, best-1);
          if(p!=null&&p>=tgt)best--;
          else break;
        }
        return Math.max(1,best);
      }
      // Extra DT to push Predicted up to target. If the path cannot reach
      // target, take every remaining P2/P3 DT including the last truck —
      // SAP is must-move; a 1-DT leftover path is not a real plan.
      function extraDtForTarget(x, spare){
        if(!(x.r.targetWmt>0)||!(spare>0))return 0;
        const pred=predOf(x);
        if(pred!=null&&pred>=x.r.targetWmt*0.995)return 0;
        const tgt=x.r.targetWmt*0.995;
        const lo0=Math.floor(x.r.dt)+1;
        let lo=lo0, hi=Math.floor(x.r.dt)+spare, best=null;
        while(lo<=hi){
          const mid=(lo+hi)>>1;
          const p=predAt(x, mid);
          if(p!=null&&p>=tgt){best=mid;hi=mid-1;}
          else lo=mid+1;
        }
        // Lumpy prediction breaks binary-search monotonicity; walk down to
        // the true minimum so Predicted lands ~100%, not several % over.
        while(best!=null&&best>lo0){
          const p=predAt(x, best-1);
          if(p!=null&&p>=tgt)best--;
          else break;
        }
        return best!=null?best-x.r.dt:spare;
      }
      function belowNeed(x){
        if(!(x.r.targetWmt>0))return 0;
        const pred=predOf(x);
        if(pred!=null&&pred>=x.r.targetWmt*0.995)return 0;
        const p=prioOf(x.r);
        if(p===1)return extraDtForTarget(x, donorSpare(p3.concat(p2), 0));
        if(p===2)return extraDtForTarget(x, donorSpare(p3, 1));
        return 0;
      }
      function surplusOf(x){
        const p=prioOf(x.r);
        if(p===3)return Math.max(0,x.r.dt-1);
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
          dumpExtra(p1, (origin)=>
            orderDonors(tosShort(), origin)
              .concat(orderDonors(p3, origin)),
            'trim SAP to target → LD (extras haul LIM-LD)');
          dumpExtra(p2, (origin)=>
            orderDonors(tosShort(), origin).concat(orderDonors(p3, origin)),
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
      const after=crows.reduce((a,x)=>a+x.r.dt,0);
      if(Math.abs(after-before)>0.01)movesTxt.push('⚠ '+cont+' fleet drift '+Math.round(after-before)+' DT');
    });
    rows.forEach(({r})=>{
      r._allocDt=r.dt;
      if(r._preAlloc&&r._preAlloc.dt!=null)r.dt=r._preAlloc.dt;
    });
    _allocMsg=moved
      ?(movesTxt.join('\n')+'\nAllocator v2 · extras → LIM-LD only · P1/P2 trimmed to ~100% of target\nEngine recalculating for new achievable…')
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
  };

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

  if(typeof window.planSet==='function'){
    const _origSet=window.planSet;
    window.planSet=function(){
      if(_allocFrozen)return;
      return _origSet.apply(this,arguments);
    };
  }
  if(typeof window.planRemove==='function'){
    const _origRm=window.planRemove;
    window.planRemove=function(){
      if(_allocFrozen)return;
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

  loadYearlyTargets();
})();
