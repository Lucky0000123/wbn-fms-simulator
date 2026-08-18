// ── Why "Achievable" can sit below "Predicted" (owner 2026-08-13) ────────────
// "if this achievable model is showing less than what we predicted ... when we
//  expect minimum is 94 how we can go for achievable as like 86 ... what is
//  the issue ... check for 1st september saved plan."
//
// Diagnosed on that exact plan (rain 0, no capacity warnings, every row OK):
//   • Predicted (path model) = dayRate × DT × payload × CONTRACTOR FACTOR.
//     dayRate is the mid-60% TRIMMED day-cluster rate — a NORMAL day, with
//     breakdown/disrupted days excluded by construction.
//   • Achievable (engine)   = shift/effective-cycle × DT × payload. The
//     effective cycle is the RAW average over ALL measured truck-shifts —
//     including breakdowns, part-shifts and bad days — and it carries NO
//     contractor factor.
//   Measured on 2026-09-01's eight routes: cluster rate ≈ raw rate × ~1.22.
//   So predicted ≈ engine × 1.22 × factor:
//     RIM (1.085×) → predicted ≈ 1.3 × engine  → achievable BELOW predicted
//     SMA (0.744×) → predicted ≈ 0.9 × engine  → achievable ABOVE predicted
//   The aggregate %-figure flips with the RIM/SMA mix — that is all the
//   102%-one-day / 92%-next-day movement is.
//
// Neither number is wrong; they answer different questions. When NO capacity
// warning binds, "achievable" is not a ceiling at all — it is the engine's
// all-days average. This module says so on the card, with live numbers.
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  const fmt=n=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:0});

  function note(){
    const frozen=typeof window.planAllocFrozen==='function'&&window.planAllocFrozen();
    const cap=frozen?(q('plan-alloc-holding')||q('plan-alloc-wrap')):q('plan-scenario-estimate');
    if(!cap)return;
    const slotId=frozen?'plan-alloc-basis-note':'plan-basis-note';
    let slot=q(slotId);
    const sim=(typeof _planLastSim!=='undefined')&&_planLastSim;
    const pred=(typeof planPredictTotals==='function')?planPredictTotals():null;
    if(!sim||!sim.summary||!pred||!(pred.wmt>0)){if(slot)slot.innerHTML='';return;}
    const warns=(sim.summary.capacity_warnings||[]).length;
    const achv=sim.summary.achievable_production_t||0;
    const ratio=achv/pred.wmt;
    // Only when the gap exists AND no physical ceiling explains it.
    if(warns>0||ratio>=0.995){if(slot)slot.innerHTML='';return;}
    const hz=typeof planHorizonFactor==='function'?planHorizonFactor():1;
    const block=cap.querySelector('.plan-cap-block')||cap;
    if(!slot||!cap.contains(slot)){
      slot=document.createElement('div');
      slot.id=slotId;
      block.appendChild(slot);
    }
    slot.innerHTML=
      '<div style="margin-top:10px;border:1px solid rgba(96,165,250,.3);border-radius:9px;padding:9px 12px;font-size:12px">'
      +'<b>Why Achievable ('+fmt(achv*hz)+' t) sits below Predicted ('+fmt(pred.wmt*hz)+' t) with every row OK:</b> '
      +'this is <b>not</b> a capacity limit — no loader or dump ceiling is binding. The two numbers use different bases. '
      +'<b>Predicted</b> = the normal-day cluster rate (disrupted days trimmed out) × your contractor\u2019s measured factor. '
      +'<b>Achievable</b> = the engine\u2019s raw average over ALL measured truck-shifts — breakdowns and part-shifts included — with no contractor factor. '
      +'On these routes the normal-day rate runs ~20% above the all-days average, so RIM rows (factor 1.085×) predict above the engine and SMA rows (0.744×) below it; '
      +'the total flips with the contractor mix. When rows are OK, <b>Predicted is the planning number</b>; Achievable here is the engine\u2019s conservative all-days average, not a ceiling.'
      +'</div>';
  }

  function wrap(){
    if(typeof window.planRenderEstimateColumn!=='function')return false;
    const orig=window.planRenderEstimateColumn;
    window.planRenderEstimateColumn=function(){
      const r=orig.apply(this,arguments);
      try{note();}catch(e){}
      return r;
    };
    return true;
  }
  if(!wrap())document.addEventListener('DOMContentLoaded',wrap);
})();
