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
  // Owner 2026-08-26 (inverting the 2026-08-25 rule, which was a blunder):
  // ~2,000 t/day of each pit's SAP goes to POS as the BUFFER; the REST goes
  // DIRECT to FeNi, to the destination the mine-plan matrix itself names for
  // that pit (BLB→KM0, TF→KM15; KR's matrix has no FeNi SAP row, so its rest
  // follows its most-used direct haul, KM15 — 375 dispatch rows vs 214).
  fixedRoutes: [
    { path: 'BLB>POS 14', material: 'SAP', targetWmt: 2000, priority: 'P1', type: 'fixed' },
    { path: 'TF>POS 12', material: 'SAP', targetWmt: 2000, priority: 'P1', type: 'fixed' },
    { path: 'KR>POS 12', material: 'SAP', targetWmt: 2000, priority: 'P1', type: 'fixed' }
  ],
  // Remaining SAP → DIRECT FeNi per the plan's own destinations.
  overflowRoutes: [
    { path: 'BLB>FENI KM0', material: 'SAP', priority: 'P1', type: 'buffer', fillsRemaining: true },
    { path: 'TF>FENI KM15', material: 'SAP', priority: 'P1', type: 'buffer', fillsRemaining: true },
    { path: 'KR>FENI KM15', material: 'SAP', priority: 'P1', type: 'buffer', fillsRemaining: true }
  ],
  // FIXED buffer SAP row may land in [0, target+band] because trucks are integers.
  sapFeniBand: 2000,
  limTos: {
    primaryDestination: 'HUAFEI',
    blbTarget: 250000, // t/month
    // Owner 2026-08-27: 4,640,201 is the 3.1 total (WITH the ~1 Mt
    // addition); 3.0 runs at 3,650,201. planRulesLimTosTarget() picks by
    // the plan date's scenario day.
    totalTarget: 4640201,
    totalTarget30: 3650201,
    totalTarget31: 4640201,
    blbRoute: 'BLB>HUAFEI'
  },
  limLd: {
    origin: 'TF',
    // splitDest is the OTHER leg of the S4 50/50 split. POS 6 since
    // 2026-08-25 (owner; was POS 12) — the km 12.0 yard on the lower
    // mainline. Key name kept as `pos12` historically; renamed to
    // `splitShare` + `splitDest` so the destination is data, not a
    // second hardcode the engine has to agree with.
    split: { huafeiBse: 0.5, splitShare: 0.5 },
    splitDest: 'POS 6',
    // Planning team 2026-08-26: the x.x.2 half-split begins in October.
    // September day-04 plans behave like x.x.1 (all leftovers HUAFEI/BSE).
    splitStartMonth: 10,
    destinations: ['HUAFEI', 'BSE', 'POS 6']
  },
  posTransit: {
    enabled: true,
    truckType: 'IWIP',
    calculateFlow: true, // not fixed
    inputMustEqualOutput: true,
    routes: [
      'POS 12>FENI KM0', 'POS 12>FENI KM15',
      // Scenario 4.1 (owner + Huafei meeting, 2026-08-31): POS 6 is not
      // ready, so ALL LD goes TF>POS 12 and reclaims onward to HUAFEI.
      // The LD share of POS 12 inflow rides this leg; the SAP buffer share
      // keeps the FeNi legs above. Material-aware split in posTransit.
      'POS 12>HUAFEI',
      // Scenario 4.2 (commercial/client, 2026-09-01): POS reclaim feeds
      // BOTH plants, 2/3 Huafei : 1/3 BSE (LD via POS = 4.0 Mt HUA +
      // 2.0 Mt BSE). These legs are DAY-08 ONLY - plan_sap_target's
      // posTransit gates them so 3.x/4.1 saves keep their HUAFEI-only
      // reclaim. From Nov 1 LIM stops stocking POS 12 (POS 6 instead);
      // the POS 6 legs below then carry the same 2:1 split.
      'POS 12>BSE',
      'POS 6>BSE',
      'POS 14>FENI KM0', 'POS 15>FENI KM0', 'POS 16>FENI KM0',
      // POS 6 transit-out (owner 2026-08-25: it is a loading point too).
      // Destination is HUAFEI, not FeNi (owner, 2026-08-28: "the
      // reclaiming of POS 6 goes to Huafei, not FeNi"). POS 6 receives
      // LIM-LD off the TF split leg and that ore feeds Huafei/BSE. The
      // 2025 tickets do show POS 6>FENI legs (32.5k + 1.9k), but they are
      // not this plan's reclaim path and sent the whole POS 6 build — up
      // to 1.4 Mt/month on the .2 scenarios — down the wrong corridor.
      'POS 6>HUAFEI'
    ]
  },
  validation: {
    BLB: { minTrips: 6, maxTrips: 7, warnBelow: 6, failBelow: 5 },
    TF: { minTrips: 1.5, warnBelow: 1.5, failBelow: 1.0, routes: ['HUAFEI', 'BSE', 'POS 12'] }
  },
  targets: {
    // Planning team sales table 2026-08-26: Limonite LD 6,644,306 wmt
    // declared (was 8 Mt). Parsed from planning_rules.md §6.
    limLdTotal: 6644306,
    limTosTotal: 4640201, // 3.1 total; 3.0 = limTos.totalTarget30
    period: 'Sep-Dec 2026'
  },
  loaders: {
    // §10.9 — loaders per row = round(DT / trucks-per-loader). Per-route
    // measured ratios come from /api/congestion_model (trucks_per_loader);
    // this is the unmeasured-route fallback.
    trucksPerLoaderDefault: 15
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
  // §4 fixed routes: | BLB → POS 14 | SAP | 2,000 t/day | BUFFER |
  // (accepts FIXED too — the type word names the ROLE, the shape is the rule)
  const fixed=[];
  md.replace(/\|\s*([^|]+?)\s*\|\s*SAP\s*\|\s*([\d,]+)\s*t\/day\s*\|\s*(?:FIXED|BUFFER)\s*\|/g,
    function(_,route,t){
      fixed.push({path:planRulesRouteKey(route), material:'SAP',
        targetWmt:parseInt(t.replace(/,/g,''),10), priority:'P1', type:'fixed'});
      return _;
    });
  if(fixed.length){R.fixedRoutes=fixed;touched=true;}
  // §4 remaining → DIRECT FeNi: | BLB → FeNi KM0 | SAP | remaining | DIRECT |
  // (accepts the legacy BUFFER word too, so an old doc still parses)
  const overflow=[];
  md.replace(/\|\s*([^|]+?)\s*\|\s*SAP\s*\|\s*remaining\s*\|\s*(?:DIRECT|BUFFER)\s*\|/g,
    function(_,route){
      overflow.push({path:planRulesRouteKey(route), material:'SAP',
        priority:'P1', type:'buffer', fillsRemaining:true});
      return _;
    });
  if(overflow.length){R.overflowRoutes=overflow;touched=true;}
  const mBand=md.match(/0\s*[–-]\s*4,000\s*t\/day|2,000\s*[±]\s*2,000/);
  if(mBand){R.sapFeniBand=2000;touched=true;}
  // §4 P3 split: "50% of leftover DT → TF → HUAFEI / BSE" and "... POS <n>".
  // The destination is CAPTURED from the document, so editing
  // planning_rules.md is enough to retarget the split (owner moved it
  // POS 12 → POS 6 on 2026-08-25).
  const mSplit=md.match(/(\d+)%\s*of leftover DT[^\n]*HUAFEI[\s\S]{0,80}?(\d+)%\s*of leftover DT[^\n]*(POS\s*\d+)/);
  if(mSplit){
    const dest=mSplit[3].replace(/POS\s*/i,'POS ').trim();
    R.limLd.split={huafeiBse:parseInt(mSplit[1],10)/100, splitShare:parseInt(mSplit[2],10)/100};
    R.limLd.splitDest=dest;
    // "Split starts October (from month 10)" — captured as data so the
    // month is editable in the doc, like the destination.
    const mStart=md.match(/Split starts \w+\s*\(from month\s*(\d{1,2})\)/i);
    R.limLd.splitStartMonth=mStart?parseInt(mStart[1],10):null;
    if(R.limLd.destinations&&R.limLd.destinations.indexOf(dest)<0)R.limLd.destinations.push(dest);
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
  // §6 targets: "| Total LIM-LD | 6.644306 Mt |" / "| Total LIM-TOS (all pits) | 4.6 Mt |"
  const mLd=md.match(/Total LIM-LD\s*\|\s*([\d.]+)\s*Mt/);
  if(mLd){R.targets.limLdTotal=Math.round(parseFloat(mLd[1])*1e6);touched=true;}
  // §6 now carries BOTH scenario totals: "| 3.650201 Mt (3.0) / 4.640201 Mt (3.1) |"
  const mTos2=md.match(/([\d.]+)\s*Mt\s*\(3\.0\)\s*\/\s*([\d.]+)\s*Mt\s*\(3\.1\)/);
  if(mTos2){
    R.limTos.totalTarget30=Math.round(parseFloat(mTos2[1])*1e6);
    R.limTos.totalTarget31=Math.round(parseFloat(mTos2[2])*1e6);
    R.targets.limTosTotal=R.limTos.totalTarget=R.limTos.totalTarget31;
    touched=true;
  } else {
    const mTos=md.match(/Total LIM-TOS[^|]*\|\s*([\d.]+)\s*Mt/);
    if(mTos){R.targets.limTosTotal=R.limTos.totalTarget=Math.round(parseFloat(mTos[1])*1e6);touched=true;}
  }
  const mBlbTos=md.match(/([\d,]+)\s*t\/month/);
  if(mBlbTos){R.limTos.blbTarget=parseInt(mBlbTos[1].replace(/,/g,''),10);touched=true;}
  // §10.9 loader fallback: "15 trucks/loader when unmeasured"
  const mTpl=md.match(/(\d+(?:\.\d+)?)\s*trucks\/loader when unmeasured/);
  if(mTpl){R.loaders.trucksPerLoaderDefault=parseFloat(mTpl[1]);touched=true;}
  return touched&&/Status:.*ACTIVE/.test(md);
}

function planRulesBadge(){
  // Badge was removed from the sticky bar (owner request). Rules still
  // parse and enforce; this stays as a no-op so planRulesReady() is unchanged.
  const stale=document.getElementById('plan-rules-badge');
  if(stale&&stale.parentNode)stale.parentNode.removeChild(stale);
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
