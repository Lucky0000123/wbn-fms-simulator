// ── Material quality label (owner 2026-08-12) ────────────────────────────────
// "I want to add the material quality in our plan ... check in the SQL database
//  and give the options what kind of quality is it. It doesn't matter like it
//  affect model in any ways."
//
// So: a LABEL, never a model input. The dropdown lists the codes actually in
// HAULAGE.MATERIAL (SAP/LIM/WCO/BOULDER/…); when a route is picked it defaults
// to the material most weighed on that route (measured share shown alongside).
// Each plan row remembers the material it was added with and shows it as a tag.
//
// Deliberately a separate file: it decorates plan.js via wrappers instead of
// editing it, so it ships independently of the in-flight refactor of plan.js.
(function(){
  'use strict';
  const q=id=>document.getElementById(id);
  const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  // Seeded with the codes measured in HAULAGE.MATERIAL (2026-08-12 census:
  // SAP 2.84M · LIM 490k · WCO 148k · rest <20k) so the dropdown still offers
  // the real options if the first fetch lands during a DB/VPN outage. A
  // successful fetch replaces this with the server's list.
  let _all=[
    {code:'SAP',name:'Saprolite'},{code:'LIM',name:'Limonite'},
    {code:'WCO',name:'Waste Conservation Ore'},{code:'BOULDER',name:'Boulder'},
    {code:'RS',name:'Road Spoil'},{code:'BASALT',name:'Basalt'},
    {code:'SLAG',name:'Slag'},{code:'RSAP',name:'Rehandled Saprolite'},
    {code:'SS',name:'Soft Spoil'},{code:'CS',name:'Crushed Stone'},
    {code:'QUARRY',name:'Quarry'},
  ];
  let _route=[];        // [{code,name,trips,sharePct}] for the current path
  let _manual=false;    // user picked a material by hand → stop auto-defaulting
  let _seq=0;

  function currentCode(){const s=q('plan-material');return s?s.value:'';}
  function labelFor(code){
    const m=_all.find(x=>x.code===code)||_route.find(x=>x.code===code);
    return m?m.name:code;
  }

  function renderSelect(){
    const s=q('plan-material');if(!s)return;
    const prev=s.value;
    const routeCodes=_route.map(r=>r.code);
    // Route materials first (with measured share), then the rest of the site list.
    const opts=[];
    _route.forEach(r=>opts.push(
      `<option value="${esc(r.code)}">${esc(r.name)} (${esc(r.code)}) · ${r.sharePct}% of route</option>`));
    _all.filter(m=>!routeCodes.includes(m.code)).forEach(m=>opts.push(
      `<option value="${esc(m.code)}">${esc(m.name)} (${esc(m.code)})</option>`));
    s.innerHTML=opts.join('');
    // Default = majority material on the route; keep a manual pick if still listed.
    const want=(_manual&&(routeCodes.includes(prev)||_all.some(m=>m.code===prev)))?prev
      :(_route.length?_route[0].code:prev);
    if(want)s.value=want;
  }

  function fetchMix(){
    const s=(q('plan-src')||{}).value,d=(q('plan-dst')||{}).value;
    if(!s||!d)return;
    const seq=++_seq;
    fetch('/api/plan/material-mix?src='+encodeURIComponent(s)+'&dst='+encodeURIComponent(d))
      .then(r=>r.json()).then(res=>{
        if(seq!==_seq)return;
        if(!res||!res.ok){
          // DB unreachable: DROP the old route's shares rather than keep them.
          // Caught live 2026-08-12: VPN fell over mid-session and a TF→POS 12
          // pick kept showing "Saprolite · 99.2% of route" measured on
          // TF→FENI KM0 — a stale label is worse than no label.
          _route=[];renderSelect();decorateRows();return;
        }
        _all=res.materials||[];
        _route=res.route||[];
        renderSelect();
        decorateRows();
      }).catch(()=>{
        if(seq!==_seq)return;
        _route=[];renderSelect();decorateRows();
      });
  }

  window.planMaterialManual=function(){_manual=true;};

  // Path change → refresh the measured mix (and the default, unless manual).
  const _origDst=window.planDstChange;
  window.planDstChange=function(){
    const r=_origDst.apply(this,arguments);
    fetchMix();
    return r;
  };

  // Add to plan → stamp the chosen material on the row(s) that just appeared.
  const _origAdd=window.planAddPath;
  window.planAddPath=function(){
    const before=new Set(Object.keys((typeof _planDraft!=="undefined"?_planDraft:{})));
    const r=_origAdd.apply(this,arguments);
    const code=currentCode();
    if(code)Object.keys((typeof _planDraft!=="undefined"?_planDraft:{})).forEach(id=>{
      if(!before.has(id))_planDraft[id].material=code;
    });
    decorateRows();
    return r;
  };

  // Saved plans → carry material through the snapshot (planDraftSnapshot copies
  // an explicit field list, which would drop it). Load needs nothing: the saved
  // paths object is assigned straight into _planDraft, material included.
  if(typeof window.planDraftSnapshot==='function'){
    const _origSnap=window.planDraftSnapshot;
    window.planDraftSnapshot=function(){
      const snap=_origSnap.apply(this,arguments);
      Object.keys(snap.paths||{}).forEach(id=>{
        const r=((typeof _planDraft!=="undefined"?_planDraft:{}))[id];
        if(r&&r.material)snap.paths[id].material=r.material;
      });
      return snap;
    };
  }

  // Plan table → small tag after the path name. computePlan rebuilds the rows
  // with innerHTML, so re-decorate after every run (rows are matched by the
  // path + contractor text, not index, because skipped rows shift positions).
  function decorateRows(){
    const rows=q('plan-rows');if(!rows)return;
    const draft=(typeof _planDraft!=="undefined"?_planDraft:{});
    Array.from(rows.querySelectorAll('tr')).forEach(tr=>{
      const tds=tr.querySelectorAll('td');
      if(tds.length<2||tr.querySelector('.plan-mat-tag'))return;
      const pathTxt=(tds[0].querySelector('b')||{}).textContent||'';
      const contTxt=(tds[1].textContent||'').trim();
      const hit=Object.keys(draft).find(id=>{
        const r=draft[id];
        return r&&r.material&&r.key===pathTxt.replace(' → ','>')&&(r.contractor||'')===contTxt;
      });
      if(!hit)return;
      const code=draft[hit].material;
      tds[0].insertAdjacentHTML('beforeend',
        ' <span class="plan-mat-tag" title="'+esc(labelFor(code))
        +' — label only, does not change the model" style="font-size:9px;padding:1px 5px;'
        +'border-radius:8px;background:rgba(96,165,250,.16);color:#93c5fd;'
        +'vertical-align:middle">'+esc(code)+'</span>');
    });
  }
  const _origCompute=window.computePlan;
  if(typeof _origCompute==='function'){
    window.computePlan=function(){
      const r=_origCompute.apply(this,arguments);
      decorateRows();
      return r;
    };
  }

  // First fill once the builder exists (Plan tab may already be open).
  document.addEventListener('DOMContentLoaded',fetchMix);
  if(document.readyState!=='loading')setTimeout(fetchMix,0);
})();
