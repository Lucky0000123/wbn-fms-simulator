// planning_rules.js — the owner's mine-plan rules (planning_rules.md) as data.
// Loads right after api.js, BEFORE plan.js / plan_sap_target.js, so every plan
// script can read window.PLANNING_RULES at load time.
//
// The repo-root planning_rules.md is the single source of truth. On startup we
// fetch /planning_rules.md and re-read every number we enforce from it; the
// literals below are the offline fallback (fixture mode, file unreachable) and
// must be kept in step with the file. PLANNING_RULES.fileStatus says which one
// is live: 'active' (parsed from the file) or 'fallback' (built-ins).
//
// Consumers: plan_sap_target.js (contractor walls, P3 50/50 split, POS transit
// IWIP rows, validation summary). Keep this file logic-free apart from parsing:
// enforcement lives with the allocator so there is exactly one enforcement
// point per rule.

window.PLANNING_RULES = {
  contractors: {
    BLB: 'RIM',
    KR: 'SMA',
    TF: null // both allowed
  },
  priorities: {
    P1: { material: 'SAP', fillsBefore: null },
    P2: { material: 'LIM-TOS', fillsBefore: 'P1' },
    P3: { material: 'LIM-LD', fillsBefore: 'P2' }
  },
  fixedRoutes: [
    { path: 'BLB>FENI KM0', material: 'SAP', targetWmt: 10000, priority: 'P1', type: 'fixed' },
    { path: 'TF>FENI KM15', material: 'SAP', targetWmt: 10000, priority: 'P1', type: 'fixed' }
  ],
  overflowRoutes: [
    { path: 'BLB>FENI KM15', material: 'SAP', priority: 'P1', type: 'overflow', fillsRemaining: true },
    { path: 'TF>FENI KM0', material: 'SAP', priority: 'P1', type: 'overflow', fillsRemaining: true }
  ],
  limTos: {
    primaryDestination: 'HUAFEI',
    blbTarget: 250000, // t/month
    totalTarget: 4600000, // 4.6 Mt over 4 months
    blbRoute: 'BLB>HUAFEI'
  },
  limLd: {
    origin: 'TF',
    split: { huafeiBse: 0.5, pos12: 0.5 },
    destinations: ['HUAFEI', 'BSE', 'POS 12']
  },
  posTransit: {
    enabled: true,
    truckType: 'IWIP',
    calculateFlow: true, // not fixed
    inputMustEqualOutput: true,
    routes: [
      'POS 12>FENI KM0', 'POS 12>FENI KM15',
      'POS 14>FENI KM0', 'POS 15>FENI KM0', 'POS 16>FENI KM0'
    ]
  },
  validation: {
    BLB: { minTrips: 6, maxTrips: 7, warnBelow: 6, failBelow: 5 },
    TF: { minTrips: 1.5, warnBelow: 1.5, failBelow: 1.0, routes: ['HUAFEI', 'BSE', 'POS 12'] }
  },
  targets: {
    limLdTotal: 8000000, // 8 Mt
    limTosTotal: 4600000, // 4.6 Mt
    period: 'Sep-Dec 2026'
  },
  fileStatus: 'loading', // 'active' | 'fallback'
  sourceUrl: '/planning_rules.md'
};

// "BLB → FeNi KM0" (file spelling) → "BLB>FENI KM0" (app route key).
function planRulesRouteKey(s){
  return String(s||'').replace(/→/g,'>').replace(/\s*>\s*/g,'>')
    .trim().toUpperCase().replace(/\s+/g,' ');
}

// Re-read every enforced number from the .md text. Anything the parse cannot
// find keeps its built-in value — a half-edited file must not zero a wall.
function planRulesParseMd(md){
  const R=window.PLANNING_RULES;
  let touched=false;
  // §3 contractor table: | BLB | RIM | ...
  md.replace(/\|\s*(BLB|KR|TF)\s*\|\s*([A-Za-z]+)\s*\|/g, function(_,pit,who){
    who=who.toUpperCase();
    R.contractors[pit]=(who==='BOTH')?null:who;
    touched=true;
    return _;
  });
  // §4 fixed routes: | BLB → FeNi KM0 | SAP | 10,000 t/day | FIXED |
  const fixed=[];
  md.replace(/\|\s*([^|]+?)\s*\|\s*SAP\s*\|\s*([\d,]+)\s*t\/day\s*\|\s*FIXED\s*\|/g,
    function(_,route,t){
      fixed.push({path:planRulesRouteKey(route), material:'SAP',
        targetWmt:parseInt(t.replace(/,/g,''),10), priority:'P1', type:'fixed'});
      return _;
    });
  if(fixed.length){R.fixedRoutes=fixed;touched=true;}
  // §4 P3 split: "50% of leftover DT → TF → HUAFEI / BSE" and "... POS 12"
  const mSplit=md.match(/(\d+)%\s*of leftover DT[^\n]*HUAFEI[\s\S]{0,80}?(\d+)%\s*of leftover DT[^\n]*POS 12/);
  if(mSplit){
    R.limLd.split={huafeiBse:parseInt(mSplit[1],10)/100, pos12:parseInt(mSplit[2],10)/100};
    touched=true;
  }
  // §7 BLB band: "should be 6-7" / "Below 5 is a red flag"
  const mBlb=md.match(/BLB trips\/DT[^\n]*?(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)/);
  if(mBlb){
    R.validation.BLB.minTrips=R.validation.BLB.warnBelow=parseFloat(mBlb[1]);
    R.validation.BLB.maxTrips=parseFloat(mBlb[2]);
    touched=true;
  }
  const mBlbFail=md.match(/Below\s+(\d+(?:\.\d+)?)\s+is a red flag/);
  if(mBlbFail){R.validation.BLB.failBelow=parseFloat(mBlbFail[1]);touched=true;}
  // §7 TF band: "must not go below 1.5" / "Below 1.0 is impossible"
  const mTf=md.match(/TF trips\/DT must not go below\s+(\d+(?:\.\d+)?)/);
  if(mTf){R.validation.TF.minTrips=R.validation.TF.warnBelow=parseFloat(mTf[1]);touched=true;}
  const mTfFail=md.match(/Below\s+(\d+(?:\.\d+)?)\s+is impossible/);
  if(mTfFail){R.validation.TF.failBelow=parseFloat(mTfFail[1]);touched=true;}
  // §6 targets: "| Total LIM-LD | 8 Mt |" / "| Total LIM-TOS (all pits) | 4.6 Mt |"
  const mLd=md.match(/Total LIM-LD\s*\|\s*([\d.]+)\s*Mt/);
  if(mLd){R.targets.limLdTotal=Math.round(parseFloat(mLd[1])*1e6);touched=true;}
  const mTos=md.match(/Total LIM-TOS[^|]*\|\s*([\d.]+)\s*Mt/);
  if(mTos){R.targets.limTosTotal=R.limTos.totalTarget=Math.round(parseFloat(mTos[1])*1e6);touched=true;}
  const mBlbTos=md.match(/([\d,]+)\s*t\/month/);
  if(mBlbTos){R.limTos.blbTarget=parseInt(mBlbTos[1].replace(/,/g,''),10);touched=true;}
  return touched&&/Status:.*ACTIVE/.test(md);
}

function planRulesBadge(){
  const nav=document.getElementById('plan-navbar');
  if(!nav)return; // /monthly has no plan navbar — badge is a Plan-tab thing
  let b=document.getElementById('plan-rules-badge');
  if(!b){
    b=document.createElement('a');
    b.id='plan-rules-badge';
    b.href=window.PLANNING_RULES.sourceUrl;
    b.target='_blank';
    b.style.cssText='margin-left:10px;font-size:10.5px;font-weight:650;letter-spacing:.03em;'
      +'padding:2px 8px;border-radius:8px;text-decoration:none;white-space:nowrap;';
    nav.appendChild(b);
  }
  const active=window.PLANNING_RULES.fileStatus==='active';
  b.textContent='📋 Planning rules: '+(active?'ACTIVE':'built-in');
  b.style.background=active?'rgba(34,197,94,.15)':'rgba(148,163,184,.15)';
  b.style.color=active?'#4ade80':'#94a3b8';
  b.title=(active
    ?'planning_rules.md loaded — the plan builder enforces it. Click to read.'
    :'planning_rules.md not reachable — enforcing the built-in copy of the rules. Click to try the file.')
    +'\nEnforced: RIM-only on BLB · SMA-only on KR · P1 SAP → P2 LIM-TOS → P3 LIM-LD ·'
    +'\nP3 leftover split 50/50 HUAFEI/BSE vs POS 12 · POS transit IWIP rows · trips/DT validation bands';
}

// Resolves once the .md has been fetched (or given up on); plan code that
// wants file-fresh numbers can await it, everything else reads the defaults.
window.planRulesReady=(function(){
  return fetch(window.PLANNING_RULES.sourceUrl,{cache:'no-store'})
    .then(function(r){return r.ok?r.text():Promise.reject(new Error('HTTP '+r.status));})
    .then(function(md){
      window.PLANNING_RULES.fileStatus=planRulesParseMd(md)?'active':'fallback';
    })
    .catch(function(){window.PLANNING_RULES.fileStatus='fallback';})
    .then(function(){
      planRulesBadge();
      return window.PLANNING_RULES;
    });
})();
