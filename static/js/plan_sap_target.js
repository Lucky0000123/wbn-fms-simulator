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
//   • The SAP targets board lives in A · Production & capacity (after Check
//     capacity), not under the holding-plan table — that duplicate is gone.
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
  // The same tick self-heals the CAP board: async re-renders (Check capacity,
  // simulate, analogues) rebuild the capacity card with innerHTML and can
  // detach #plan-sap-board-cap after we drew it.
  setInterval(function(){
    syncTargetVisibility();
    try{
      const cap=q('plan-scenario-estimate');
      const hasTargets=Object.keys(draft()).some(id=>draft()[id]&&draft()[id].targetWmt>0);
      if(cap&&hasTargets&&cap.querySelector('.plan-cap-block')&&!q('plan-sap-board-cap')){
        renderBoard();
      }
    }catch(e){}
  },900);

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
      const hasTarget=r.targetWmt>0;
      const existing=tag.parentNode.querySelector('.plan-sap-chip[data-sapid="'+CSS.escape(id)+'"]');
      // Owner 2026-08-14: LIM-TOS rows carry targets too (priority P2), so
      // EVERY production row gets a chip. SAP chips green (P1 fixed supply);
      // LIM chips blue (P2 TOS target; leave empty for buffer LD limonite).
      const label=hasTarget?('🎯 '+fmt(r.targetWmt)+' t'):'＋ target';
      const col=isSap?['rgba(34,197,94,.14)','#4ade80','rgba(34,197,94,.3)']
                     :['rgba(96,165,250,.14)','#93c5fd','rgba(96,165,250,.3)'];
      const tip=isSap?'SAP is fixed supply (P1) — click to set the t/day target'
                     :'LIM from TOS is priority 2 — set its t/day target here; leave empty if this row is LD buffer limonite';
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
      if(v>0)r.targetWmt=v;else delete r.targetWmt;
      if(typeof computePlan==='function')computePlan();   // re-render chip + board
    };
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();commit();}
      if(e.key==='Escape'){done=true;if(typeof computePlan==='function')computePlan();}});
    inp.addEventListener('blur',commit);
    ev.stopPropagation();
  });

  function renderBoard(){
    const rows=q('plan-rows');
    if(!rows)return;
    decorateRowTargets(rows);
    // Holding-plan table does not host the SAP board — Check capacity does
    // (`#plan-sap-board-cap`). Drop any leftover under-table host.
    const leftover=q('plan-sap-board');
    if(leftover)leftover.remove();
    const targets=Object.keys(draft()).map(id=>({id,r:draft()[id]}))
      .filter(x=>x.r&&x.r.targetWmt>0&&!x.r.foreign);
    renderCapBoard(targets);
  }

  function boardHtml(targets){
    const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
    const body=targets.map(({id,r})=>{
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,{selfId:id}):null;
      const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
      const predDay=e?r.dt*e.daily*pay.tf:null;
      const achvDay=achievableFor(r.key);
      let reqDt=requiredDt(r.key,r.targetWmt,c);
      const ceil=typeof planDtForWmt==='function'?planDtForWmt._lastCeiling:null;
      const unreachable=reqDt==null;
      // Target above the path's demonstrated ceiling (owner 2026-08-13,
      // October BLB>POS 14: 26,913 asked vs 24,674 max): don't give up with
      // a dash — still answer "how many DTs" by solving for the CEILING
      // itself (99.5% of it: the solver rejects targets at/above the peak).
      // The status then says both facts: trucks to reach the max, and the
      // shortfall that no truck count can close.
      let ceilDt=null;
      if(unreachable&&ceil&&ceil.maxT>0){
        ceilDt=requiredDt(r.key,ceil.maxT*2*0.995,c);
      }
      const met=predDay!=null&&predDay>=r.targetWmt*0.995;
      const status=unreachable
        ?(ceilDt!=null
          ?'<span style="color:#ef4444;font-weight:600">'
            +(ceilDt>r.dt?('add '+fmt(ceilDt-r.dt)+' DT → path max '):'at path max ')
            +fmt(ceil.maxT*2)+' t/day — short '+fmt(Math.max(0,r.targetWmt-ceil.maxT*2))
            +' t/day needs a 2nd path</span>'
          :'<span style="color:#ef4444;font-weight:600">target above path ceiling'+(ceil?(' ('+fmt(ceil.maxT*2)+' t/day max)'):'')+'</span>')
        :met?'<span style="color:#22c55e;font-weight:600">on target</span>'
        :'<span style="color:#f59e0b;font-weight:600">add '+fmt(Math.max(0,reqDt-r.dt))+' DT</span>';
      if(unreachable&&ceilDt!=null)reqDt=ceilDt;   // Required-DT column: trucks for the max
      const prio=(r.material==='SAP')?'P1':'P2';
      const dtDelta=r._preAlloc!=null&&r._preAlloc.dt!==r.dt
        ?' <span style="color:'+(r.dt>r._preAlloc.dt?'#4ade80':'#f59e0b')+'">('
          +(r.dt>r._preAlloc.dt?'+':'')+(r.dt-r._preAlloc.dt)+')</span>':'';
      return '<tr>'
        +'<td><span style="font-size:9px;padding:0 5px;border-radius:7px;margin-right:4px;'
        +(prio==='P1'?'background:rgba(34,197,94,.15);color:#4ade80':'background:rgba(96,165,250,.15);color:#93c5fd')
        +'">'+prio+'</span><b>'+esc(r.key.replace('>',' → '))+'</b> <span class="muted">'+esc(r.contractor)+'</span></td>'
        +'<td class="r">'+fmt(r.targetWmt)+'</td>'
        +'<td class="r">'+(predDay!=null?fmt(predDay):'—')+'</td>'
        +'<td class="r">'+(achvDay!=null?fmt(achvDay):'<span class="muted" title="run ▶ Run simulated scenario to fill">run sim</span>')+'</td>'
        +'<td class="r">'+fmt(r.dt)+dtDelta+'</td>'
        +'<td class="r">'+(reqDt!=null?fmt(reqDt):'—')+'</td>'
        +'<td>'+status+'</td></tr>';
    }).join('');
    // Allocation deltas ready? Show the 5-tonnage comparison strip.
    const hasAlloc=targets.some(({r})=>r._preAlloc!=null);
    let strip='';
    if(hasAlloc){
      let oP=0,nP=0,oA=0,nA=0,T=0;
      targets.forEach(({id,r})=>{
        const pre=r._preAlloc||{};
        T+=r.targetWmt||0;
        oP+=pre.pred||0; oA+=pre.achv||0;
        const c=typeof planContractor==='function'?planContractor(r.contractor):null;
        const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,0,c,{selfId:id}):null;
        const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
        nP+=e?r.dt*e.daily*pay.tf:0;
        nA+=achievableFor(r.key)||0;
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
        +'</div>';
    }
    return '<div style="margin-top:10px;border:1px solid rgba(34,197,94,.3);border-radius:9px;padding:9px 12px">'
      +'<b style="font-size:12px">Priority targets — P1 SAP (fixed supply) · P2 LIM from TOS</b> '
      +'<span class="muted" style="font-size:11px">(LD limonite = buffer, no target). '
      +'Goal: predicted = achievable = target. Required DT solved with the same path engine as the table.</span>'
      +strip
      +'<table style="width:100%;margin-top:6px;font-size:12px;border-collapse:collapse">'
      +'<tr style="color:var(--muted,#8b98a5);font-size:10.5px;text-transform:uppercase">'
      +'<th style="text-align:left">Path</th><th class="r">Target t/day</th><th class="r">Predicted</th>'
      +'<th class="r">Achievable</th><th class="r">Allocated DT</th><th class="r">Required DT</th><th style="text-align:left">Status</th></tr>'
      +body+'</table>'
      +'<div style="margin-top:8px">'
      +'<button type="button" class="ms-btn" onclick="planAllocatePriority()" '
      +'title="Fixed total fleet per contractor. Fills P1 SAP targets first, then P2 TOS-LIM targets, taking trucks from buffer (no-target) LIM rows of the same contractor. Then re-runs the scenario so new predicted AND new achievable appear next to the old ones.">'
      +'⚡ Allocate DT as per priority requirements</button>'
      +'<span class="muted" id="plan-alloc-status" style="font-size:11px;margin-left:9px"></span>'
      +'</div>'
      +(_allocMsg?('<div class="muted" style="font-size:11px;margin-top:5px">'+esc(_allocMsg)+'</div>'):'')
      +'</div>';
  }

  // Owner 2026-08-13 (screenshots): "this should be shown in this part after
  // calculations" — the same board inside A · Production & capacity, under the
  // Check-capacity route table, where Achievable is filled from the engine.
  function renderCapBoard(targets){
    const cap=q('plan-scenario-estimate');
    if(!cap)return;
    let slot=q('plan-sap-board-cap');
    if(!targets||!targets.length){if(slot)slot.innerHTML='';return;}
    if(!slot){
      const block=cap.querySelector('.plan-cap-block')||cap;
      slot=document.createElement('div');
      slot.id='plan-sap-board-cap';
      block.appendChild(slot);
    }else if(!slot.isConnected||!cap.contains(slot)){
      // capacity card re-rendered via innerHTML — reattach
      const block=cap.querySelector('.plan-cap-block')||cap;
      slot=document.createElement('div');
      slot.id='plan-sap-board-cap';
      block.appendChild(slot);
    }
    slot.innerHTML=boardHtml(targets);
  }

  // ── Allocate DT as per priority requirements (owner 2026-08-14) ────────────
  // "our model will see how to allocate DT from different plans to different
  //  priorities, and then come up with new plan ... it will recalculate the
  //  new predictions tonnage, new achievable tonnage as compared to targets."
  //
  // Rules (owner 2026-08-13/14): total fleet per CONTRACTOR is fixed. P1 =
  // SAP rows with targets, P2 = LIM rows with targets (TOS), buffer = rows
  // without targets (LD limonite). Donors: buffer rows of the same contractor,
  // same-origin rows first. Required DT solved with planDtForWmt (same engine
  // as everything else), capped at the path ceiling when the target is beyond
  // it. Old predicted/achievable are snapshotted per row BEFORE the move, then
  // the scenario re-runs so the new achievable comes from the same engine.
  let _allocMsg='';
  window.planAllocatePriority=function(){
    const d=draft();
    const st=q('plan-alloc-status');
    const rows=Object.keys(d).map(id=>({id,r:d[id]})).filter(x=>!x.r.foreign);
    if(!rows.length)return;
    // Snapshot OLD numbers per targeted row (and buffer donors) first.
    const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
    rows.forEach(({id,r})=>{
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const e=typeof planTripsPerDT==='function'?planTripsPerDT(r.key,r.dt,rain,c,{selfId:id}):null;
      const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:50};
      r._preAlloc={dt:r.dt,
        pred:e?r.dt*e.daily*pay.tf:0,
        achv:achievableFor(r.key)||0};
    });
    // Per contractor: needs of P1 then P2; donors = no-target rows.
    const byCont={};
    rows.forEach(x=>{(byCont[x.r.contractor]=byCont[x.r.contractor]||[]).push(x);});
    const movesTxt=[];
    Object.keys(byCont).forEach(cont=>{
      const crows=byCont[cont];
      const targeted=crows.filter(x=>x.r.targetWmt>0)
        .sort((a,b)=>((a.r.material==='SAP')?0:1)-((b.r.material==='SAP')?0:1)
          ||b.r.targetWmt-a.r.targetWmt);
      const buffer=crows.filter(x=>!(x.r.targetWmt>0));
      // Surplus donors: a TARGETED row holding more DT than its own target
      // needs (e.g. TF>HUAFEI RIM carries the LD buffer inside the same row:
      // 284 DT vs ~101 needed for the TOS target). Its surplus may donate
      // after true buffer rows are exhausted.
      const surplus=targeted.map(x=>{
        const c2=typeof planContractor==='function'?planContractor(x.r.contractor):null;
        let need2=requiredDt(x.r.key,x.r.targetWmt,c2);
        if(need2==null){
          const cl=planDtForWmt._lastCeiling;
          if(cl&&cl.maxT>0)need2=requiredDt(x.r.key,cl.maxT*2*0.995,c2);
        }
        return {x,spare:need2!=null?Math.max(0,x.r.dt-need2):0};
      }).filter(o=>o.spare>1);
      targeted.forEach(({id,r})=>{
        const c=typeof planContractor==='function'?planContractor(r.contractor):null;
        let need=requiredDt(r.key,r.targetWmt,c);
        if(need==null){
          const ceil=planDtForWmt._lastCeiling;
          if(ceil&&ceil.maxT>0)need=requiredDt(r.key,ceil.maxT*2*0.995,c);
        }
        if(need==null)return;
        let deficit=need-r.dt;
        if(deficit<=0)return;
        const origin=r.key.split('>')[0];
        // same-origin buffer donors first, then any buffer of this contractor
        const donorsOrdered=buffer.filter(x=>x.r.key.split('>')[0]===origin)
          .concat(buffer.filter(x=>x.r.key.split('>')[0]!==origin));
        for(const don of donorsOrdered){
          if(deficit<=0)break;
          const spare=don.r.dt-1;              // never strip a row to zero
          if(spare<=0)continue;
          const take=Math.min(deficit,spare);
          don.r.dt-=take;
          r.dt+=take;
          deficit-=take;
          movesTxt.push(cont+' '+take+' DT: '+don.r.key+' → '+r.key
            +(don.r.key.split('>')[0]===origin?' (same origin)':' (cross plan)'));
        }
        // Then surplus of other targeted rows (their own target stays covered).
        if(deficit>0)for(const o of surplus){
          if(deficit<=0)break;
          if(o.x.id===id||o.spare<=0)continue;
          const take=Math.min(deficit,o.spare);
          o.x.r.dt-=take;o.spare-=take;
          r.dt+=take;deficit-=take;
          movesTxt.push(cont+' '+Math.round(take)+' DT: '+o.x.r.key+' (surplus) → '+r.key);
        }
        if(deficit>0)movesTxt.push('⚠ '+cont+' short '+Math.ceil(deficit)+' DT for '+r.key
          +' — buffer exhausted');
      });
    });
    _allocMsg=movesTxt.length
      ?('Moved: '+movesTxt.join(' · ')+' — engine recalculating for new achievable…')
      :'No moves possible — every row of the contractor already carries a target (no buffer to draw from) or targets are covered.';
    if(typeof computePlan==='function')computePlan();
    // Re-run the scenario so NEW achievable comes from the engine.
    if(typeof planRunScenario==='function')planRunScenario({preserveFinalize:true});
  };

  // Re-render whenever the plan table re-renders.
  const _origCompute=window.computePlan;
  if(typeof _origCompute==='function'){
    window.computePlan=function(){
      const r=_origCompute.apply(this,arguments);
      try{renderBoard();}catch(e){}
      return r;
    };
  }

  // A · Production & capacity re-renders with its own innerHTML on Check
  // capacity / simulate — re-attach the board right after it paints.
  if(typeof window.planRenderEstimateColumn==='function'){
    const _origCap=window.planRenderEstimateColumn;
    window.planRenderEstimateColumn=function(){
      const r=_origCap.apply(this,arguments);
      try{renderBoard();}catch(e){}
      return r;
    };
  }
})();
