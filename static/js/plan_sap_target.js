// ── SAP targets in the plan (owner 2026-08-13) ───────────────────────────────
// "add a target for SAP, whenever the material we enter SAP, you have to add
//  the target in front of that ... if it is going to buffer, it's limonite.
//  If it is not going to buffer, it's supply ... suggest us with allocated
//  DTs and the required DTs, so that target tonnage, predicted tonnage and
//  achievable tonnage will be there. Our predicted should equal achievable
//  equal target for SAP. Limonite - not an issue."
//
// Behaviour:
//   • The builder's SAP-target input appears only when Material = SAP.
//     SAP = fixed SUPPLY (has a target); LIM = BUFFER (no target needed).
//   • The target rides on the draft row (targetWmt, t/day) and through saved
//     plans (planDraftSnapshot wrapper).
//   • A "SAP targets" board under the plan table shows, per SAP row:
//     target vs predicted vs achievable, allocated DT vs REQUIRED DT (solved
//     through the same planTripsPerDT engine), and a one-word status.
// Separate module (like plan_material.js): plan.js is mid-refactor elsewhere.
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmt=n=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:0});

  function draft(){return (typeof _planDraft!=='undefined')?_planDraft:{};}
  function hz(){return typeof planHorizonFactor==='function'?planHorizonFactor():1;}

  // Show the target input only for SAP.
  function syncTargetVisibility(){
    const mat=q('plan-material'),f=q('plan-sap-target-field');
    if(!mat||!f)return;
    f.style.display=(mat.value==='SAP')?'':'none';
  }
  document.addEventListener('change',ev=>{
    if(ev.target&&ev.target.id==='plan-material')syncTargetVisibility();
  });
  // plan_material.js sets the route default PROGRAMMATICALLY (no change event
  // fires), so a one-shot init missed it — keep visibility synced on a light
  // interval instead (found in verification: SAP default left the field hidden).
  setInterval(syncTargetVisibility,900);

  // Stamp targetWmt on rows created by Add to plan (SAP only).
  const _origAdd=window.planAddPath;
  if(typeof _origAdd==='function'){
    window.planAddPath=function(){
      const before=new Set(Object.keys(draft()));
      const r=_origAdd.apply(this,arguments);
      const mat=(q('plan-material')||{}).value;
      const tgt=Math.max(0,parseFloat((q('plan-sap-target')||{}).value)||0);
      if(mat==='SAP'&&tgt>0){
        Object.keys(draft()).forEach(id=>{
          if(!before.has(id))draft()[id].targetWmt=tgt;   // t/day
        });
        const ti=q('plan-sap-target');if(ti)ti.value='';
      }
      renderBoard();
      return r;
    };
  }

  // Persist through saved plans.
  if(typeof window.planDraftSnapshot==='function'){
    const _origSnap=window.planDraftSnapshot;
    window.planDraftSnapshot=function(){
      const snap=_origSnap.apply(this,arguments);
      Object.keys(snap.paths||{}).forEach(id=>{
        const r=draft()[id];
        if(r&&r.targetWmt>0)snap.paths[id].targetWmt=r.targetWmt;
      });
      return snap;
    };
  }

  // Required DT for a target: same solver plan.js uses for its ⇄WMT mode,
  // so the suggestion can never disagree with the engine.
  function requiredDt(key,targetDay,contractor){
    if(typeof planDtForWmt!=='function')return null;
    const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
    const sf=typeof planShiftFactor==='function'?planShiftFactor():0.5;
    // planDtForWmt takes a PER-SHIFT target; targets here are per day.
    const perShift=targetDay*sf;
    const dt=planDtForWmt(key,perShift,rain,contractor);
    return dt?Math.ceil(dt):null;   // ceiling: never suggest under the need
  }

  function achievableFor(key){
    // Last simulate run, per route (per shift -> horizon).
    const sim=(typeof _planLastSim!=='undefined')&&_planLastSim;
    if(!sim||!sim.results)return null;
    const row=sim.results.find(x=>(x.route||'').trim()===key);
    return row&&row.achievable_production_t!=null?row.achievable_production_t*2:null; // per day
  }

  // ── Target directly on the plan-table row (owner 2026-08-13: "add option
  //    to add sap target in plan table as well so i can enter it directly").
  // Every SAP row gets a 🎯 chip after the material tag: shows the target if
  // set ("🎯 10,000 t"), or "＋ target" if not. Click → inline number input;
  // Enter/blur commits to the draft row, 0/empty clears the target.
  function decorateRowTargets(rows){
    const d=draft();
    Array.from(rows.querySelectorAll('.plan-mat-tag[data-matid]')).forEach(tag=>{
      const id=tag.getAttribute('data-matid');
      const r=d[id];
      if(!r||r.foreign)return;
      const isSap=(r.material||'')==='SAP';
      const existing=tag.parentNode.querySelector('.plan-sap-chip[data-sapid="'+CSS.escape(id)+'"]');
      if(!isSap){if(existing)existing.remove();return;}
      const label=r.targetWmt>0?('🎯 '+fmt(r.targetWmt)+' t'):'＋ target';
      if(existing){
        if(!existing.querySelector('input'))existing.innerHTML=label;
        return;
      }
      tag.insertAdjacentHTML('afterend',
        ' <span class="plan-sap-chip" data-sapid="'+esc(id)+'" title="SAP is fixed supply — click to set the t/day target for this path" '
        +'style="font-size:9px;padding:1px 6px;border-radius:8px;cursor:pointer;vertical-align:middle;'
        +'background:rgba(34,197,94,.14);color:#4ade80;border:1px solid rgba(34,197,94,.3)">'+label+'</span>');
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
      if(v>0)r.targetWmt=v;else delete r.targetWmt;
      if(typeof computePlan==='function')computePlan();   // re-render chip + board
    };
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();commit();}
      if(e.key==='Escape'){done=true;if(typeof computePlan==='function')computePlan();}});
    inp.addEventListener('blur',commit);
    ev.stopPropagation();
  });

  function renderBoard(){
    let host=q('plan-sap-board');
    const rows=q('plan-rows');
    if(!rows)return;
    decorateRowTargets(rows);
    const targets=Object.keys(draft()).map(id=>({id,r:draft()[id]}))
      .filter(x=>x.r&&x.r.targetWmt>0&&!x.r.foreign);
    if(!host){
      const table=rows.closest('table');
      if(!table)return;
      host=document.createElement('div');
      host.id='plan-sap-board';
      table.parentNode.insertBefore(host,table.nextSibling);
    }
    if(!targets.length){host.innerHTML='';return;}
    const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
    const body=targets.map(({id,r})=>{
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,{selfId:id}):null;
      const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
      const predDay=e?r.dt*e.daily*pay.tf:null;
      const achvDay=achievableFor(r.key);
      const reqDt=requiredDt(r.key,r.targetWmt,c);
      const ceil=typeof planDtForWmt==='function'?planDtForWmt._lastCeiling:null;
      const unreachable=reqDt==null;
      const met=predDay!=null&&predDay>=r.targetWmt*0.995;
      const status=unreachable
        ?'<span style="color:#ef4444;font-weight:600">target above path ceiling'+(ceil?(' ('+fmt(ceil.maxT*2)+' t/day max)'):'')+'</span>'
        :met?'<span style="color:#22c55e;font-weight:600">on target</span>'
        :'<span style="color:#f59e0b;font-weight:600">add '+fmt(Math.max(0,reqDt-r.dt))+' DT</span>';
      return '<tr>'
        +'<td><b>'+esc(r.key.replace('>',' → '))+'</b> <span class="muted">'+esc(r.contractor)+'</span></td>'
        +'<td class="r">'+fmt(r.targetWmt)+'</td>'
        +'<td class="r">'+(predDay!=null?fmt(predDay):'—')+'</td>'
        +'<td class="r">'+(achvDay!=null?fmt(achvDay):'<span class="muted" title="run ▶ Run simulated scenario to fill">run sim</span>')+'</td>'
        +'<td class="r">'+fmt(r.dt)+'</td>'
        +'<td class="r">'+(reqDt!=null?fmt(reqDt):'—')+'</td>'
        +'<td>'+status+'</td></tr>';
    }).join('');
    host.innerHTML=
      '<div style="margin-top:10px;border:1px solid rgba(34,197,94,.3);border-radius:9px;padding:9px 12px">'
      +'<b style="font-size:12px">SAP targets — fixed supply</b> '
      +'<span class="muted" style="font-size:11px">(LIM is buffer — no target needed). '
      +'Goal: predicted = achievable = target. Required DT solved with the same path engine as the table.</span>'
      +'<table style="width:100%;margin-top:6px;font-size:12px;border-collapse:collapse">'
      +'<tr style="color:var(--muted,#8b98a5);font-size:10.5px;text-transform:uppercase">'
      +'<th style="text-align:left">Path (SAP)</th><th class="r">Target t/day</th><th class="r">Predicted</th>'
      +'<th class="r">Achievable</th><th class="r">Allocated DT</th><th class="r">Required DT</th><th style="text-align:left">Status</th></tr>'
      +body+'</table></div>';
  }

  // Re-render whenever the plan table re-renders.
  const _origCompute=window.computePlan;
  if(typeof _origCompute==='function'){
    window.computePlan=function(){
      const r=_origCompute.apply(this,arguments);
      try{renderBoard();}catch(e){}
      return r;
    };
  }
})();
