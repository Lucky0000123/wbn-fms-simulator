// ── Estimate ⇄ plan-row reconciliation (owner 2026-08-13) ────────────────────
// "as I was making plan, I see in the window my WMT shown something different
//  but when it enter in plan, it shows different. why? what is happening?"
//
// Two honest numbers, two different questions:
//   • The builder strip ("This path") may be answered by the trained model
//     (/api/predict, e.g. Random Forest) — a SINGLE-PATH estimate that knows
//     contractor/route/rain but nothing about the rest of the holding plan,
//     and carries its own payload estimate.
//   • The plan-table row prices the SAME path INSIDE the plan: shared-corridor
//     drag from other rows, the shared weighbridge ceiling, the shared
//     day-throughput cap, and the contractor's measured payload.
// When the path being built is already in the plan and the two figures part by
// more than 3%, this module appends one line under the estimate quoting the
// plan-row number and naming the causes, so nobody has to wonder which one is
// real. Wrapper file (not a plan.js edit): plan.js is mid-refactor elsewhere.
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmt=n=>Number(n||0).toLocaleString('en-GB',{maximumFractionDigits:0});

  function reconcile(v){
    try{
      const box=q('plan-preview');
      if(!box||v.foreign||v.swapped)return;
      if(v.model==='local')return;                 // still loading — skip flicker
      const key=v.src+'>'+v.dst;
      const draft=(typeof _planDraft!=='undefined')?_planDraft:{};
      const id=Object.keys(draft).find(k=>{
        const r=draft[k];
        if(!r||r.foreign||r.key!==key)return false;
        if((r.contractor||'')!==(v.contractor||''))return false;
        const mat=((q('plan-material')||{}).value||'').trim().toUpperCase();
        const ot=((q('plan-otype')||{}).value||'').trim().toUpperCase();
        if(mat&&String(r.material||'').toUpperCase()!==mat)return false;
        if(mat==='LIM'&&(ot==='TOS'||ot==='LD')&&String(r.otype||'').toUpperCase()!==ot)return false;
        return true;
      });
      if(!id)return;                               // path not in the plan yet
      const r=draft[id];
      const rain=Math.max(0,parseFloat((q('plan-rain')||{}).value)||0);
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const e=typeof planTripsPerDT==='function'?planTripsPerDT(key,r.dt,rain,c,typeof planTripOpts==='function'?planTripOpts(id):{selfId:id,nLoaders:r.loaders||2}):null;
      const pay=typeof planPayload==='function'?planPayload(key,c):null;
      if(!e||!pay)return;
      const hz=typeof planHorizonFactor==='function'?planHorizonFactor():1;
      const trips=Math.round(r.dt*e.shift*hz);
      const wmt=Math.round(r.dt*e.shift*hz*pay.tf);
      const shown=Math.round((v.wmt||0)*(typeof planHorizonFactor==='function'?planHorizonFactor():1));
      if(!(shown>0&&wmt>0))return;
      const delta=Math.abs(shown-wmt)/Math.max(shown,wmt);
      const old=box.querySelector('.est-plan-row-note');
      if(old)old.remove();
      if(delta<0.03)return;                        // agree within 3% — nothing to explain
      // Name the causes we can actually measure.
      const causes=[];
      if(e.wbFactor!=null&&e.wbFactor<0.995)causes.push('weighbridge shared with other paths');
      if(e.satFactor!=null&&e.satFactor<0.995)causes.push('route throughput ceiling shared across the plan');
      const secDrag=typeof planSectionDrag==='function'?planSectionDrag(key,r.dt):null;
      if(secDrag&&secDrag.delta<0)causes.push('shared road with your other paths');
      if(pay&&v.payload&&Math.abs(pay.tf-v.payload)/pay.tf>0.005)
        causes.push('measured payload '+pay.tf.toFixed(1)+' t vs model '+Number(v.payload).toFixed(1)+' t');
      if(!causes.length)causes.push('the estimate above is a single-path model; the plan row prices it inside your whole plan');
      const foot=box.querySelector('.est-foot');
      if(!foot)return;
      foot.insertAdjacentHTML('beforeend',
        '<div class="est-plan-row-note" style="margin-top:4px;font-size:10.5px;color:#93c5fd" '
        +'title="'+esc('The strip above answers "this path alone". The plan table answers "this path inside your plan". Causes: '+causes.join('; '))+'">'
        +'In your plan this row = <b>'+fmt(wmt)+' t · '+fmt(trips)+' trips</b> — '
        +esc(causes[0])+(causes.length>1?' +'+(causes.length-1)+' more':'')+'</div>');
    }catch(err){/* decorative only — never break the estimate */}
  }

  function wrap(){
    if(typeof window._planRenderEstimate!=='function')return false;
    const orig=window._planRenderEstimate;
    window._planRenderEstimate=function(v){
      const ret=orig.apply(this,arguments);
      reconcile(v||{});
      return ret;
    };
    return true;
  }
  if(!wrap()){
    document.addEventListener('DOMContentLoaded',wrap);
  }
})();
