// flow_sim.js — Flow simulator — scenario evaluation, particle motion, animation loop,
// and the non-WBN ("other traffic") corridor model.
// Dual host: Capability (historical replay, prefix '') and Plan Step 2 (illustration, prefix 'plan-').

let _flowIdPrefix='';
let _flowHost='capability'; // 'capability' | 'plan'
let _flowSimRatio=1;       // simulate achievable/planned — tints animation only (Phase C)
let _flowMapByHost={};     // prefix → {map,road,trucks,markers}
let _flowNeedLL=false;     // set per frame: does this host have a live map to feed?
// Cartoon clock only. 1× = 12 h shift in 24 s of wall time. Never trips/WMT.
let _flowPlaybackRate=1;

function flowQ(id){
  if(_flowIdPrefix){const el=document.getElementById(_flowIdPrefix+id);if(el)return el;}
  return document.getElementById(id);
}
function flowSetHost(host){
  if(_flowSim&&_flowSim.running)stopFlowSimulator();
  const next=host==='plan'?'plan':'capability';
  // Plan Step 2 seeds synthetic rows into the SHARED flow globals. Snapshot the
  // Capability replay state on the way out so returning to the Capability tab
  // restores its own scenario instead of re-rendering the plan's synthetic data
  // into the unprefixed DOM (cross-host state bleed).
  if(next==='plan'&&_flowHost==='capability'){
    _flowCapSaved={source:_flowSource,point:_flowPointScenario,draft:_flowPlanDraft,
      fleet:_flowFleetAvailable,speeds:_flowSpeedsInitialised,ratio:_flowSimRatio};
  }
  _flowHost=next;
  _flowIdPrefix=_flowHost==='plan'?'plan-':'';
}
let _flowCapSaved=null;
function flowEnsureCapabilityHost(){
  if(_flowHost==='capability')return;
  flowSetHost('capability');
  _flowSimRatio=1;
  if(_flowCapSaved){
    _flowSource=_flowCapSaved.source;
    _flowPointScenario=_flowCapSaved.point;
    _flowPlanDraft=_flowCapSaved.draft||{};
    _flowFleetAvailable=_flowCapSaved.fleet;
    _flowSpeedsInitialised=!!_flowCapSaved.speeds;
    _flowCapSaved=null;
  }else if(_flowPointScenario&&_flowPointScenario.date==='plan'){
    // No snapshot (page loaded straight into Plan): drop the synthetic plan
    // scenario rather than replaying it as capability history.
    _flowSource=null;_flowPointScenario=null;_flowPlanDraft={};
  }
  if(_flowSource)renderFlowSimulator(_flowSource.P,_flowSource.colours,true);
}
function flowPlayLabel(){return '▶ Run';}
// Analytic point on a route's loaded/empty loop. Rectangle fallback for
// corridor-only hauls; polyline loop when a spur (BLB / HUAFEI / POS CBB) is involved.
function flowKmFromStickX(x){
  const s=_flowSim;
  if(!s||!(s.roadRight>s.roadLeft)||!Number.isFinite(s.corridorKm)||!Number.isFinite(x))return null;
  return s.corridorKm-(x-s.roadLeft)/(s.roadRight-s.roadLeft)*s.corridorKm;
}
function flowPointAt(r,phase){
  if(r.loop&&r.loop.length>1)return flowInterpLoop(r.loop,phase);
  const x1=r.sourceX,x2=r.destX,w=x2-x1,len=2*Math.abs(w)+60,d=(((phase%1)+1)%1)*len;
  const lo=Math.min(x1,x2),hi=Math.max(x1,x2),span=hi-lo;
  let x,y;
  if(d<span){x=x1+(w>=0?d:-d);y=180;}
  else if(d<span+30){x=x2;y=180+(d-span);}
  else if(d<2*span+30){x=x2+(w>=0?-(d-span-30):(d-span-30));y=210;}
  else{x=x1;y=210-(d-2*span-30);}
  const km=flowKmFromStickX(x),ll=flowMapLatLngAt(km);
  return {x,y,km,road:'CORRIDOR',roadKm:km,lat:ll&&ll[0],lng:ll&&ll[1],spur:false};
}
function flowNormName(x){return (x||'').trim().toUpperCase().replace(/\s+/g,' ');}
// Spurs that hang off ANOTHER spur's road instead of the stick. EMPTY today:
// the 2026-08-24 override that hung HUAFEI on the BLB road was deleted on
// 2026-08-25, exactly as its own comment instructed, when the owner confirmed
// the survey ("go for survey"). Three sources now agree HUAFEI is its own
// branch off the stick at km 5.5: the survey polyline (HFC's first point
// 0.8 m from CRD km 5.500), the dispatch road book's literal "HFC KM5,5 -
// KM6,4" segment column (flagged on every HUAFEI.C01 haul), and that book's
// gross km reproducing |origin − 5.5| + 0.925. Gate J80 pins the geometry;
// the model side moved the same day (congestion NODE_KM 0.0 → 5.5).
const FLOW_SPUR_PARENTS={};
function flowJoins(){
  const a=(_flowGeom&&_flowGeom.joins)||[];
  const b=(((_D&&_D.corridor)||{}).joins)||[];
  // Survey fallback (haul_road_chainage_public.csv) so BLB paints before geometry fetch.
  const raw=a.length?a:b.length?b:[
    {id:'blb',road:'BLB',label:'BLB',aliases:['BLB'],joinKm:2.45,joinRoad:'CRD',joinLat:0.483061,joinLng:127.968764,spurJoinKm:2.45,endKm:19.825,endLat:0.540268,endLng:127.963169,lengthKm:17.375},
    {id:'hfc',road:'HFC',label:'HUAFEI',aliases:['HUAFEI','HUAFEI.B01','HUAFEI.C01'],joinKm:5.5,joinRoad:'CRD',joinLat:0.482365,joinLng:127.949115,spurJoinKm:5.525,endKm:6.425,endLat:0.48646,endLng:127.943539,lengthKm:0.9},
    {id:'cbb',road:'CBB',label:'POS CBB',aliases:['POS CBB','CBB','POSCBB'],joinKm:7.875,joinRoad:'KR',joinLat:0.47953,joinLng:127.936987,spurJoinKm:6.3,endKm:17.125,endLat:0.534598,endLng:127.955861,lengthKm:10.825}
  ];
  // HUAFEI is its own branch off the stick at km 5.5 (survey, confirmed by
  // the owner 2026-08-25 — see FLOW_SPUR_PARENTS above for the evidence).
  const list=raw.map(j=>({...j}));
  list.forEach(j=>{
    const o=FLOW_SPUR_PARENTS[j.road];
    if(!o)return;
    const p=list.find(q=>q.road===o.parentRoad);
    if(p){j.parent=p;j.parentAtKm=o.atKm;}
  });
  return list;
}
function flowLocate(name){
  const n=flowNormName(name);
  if(!n)return null;
  // BSE (the second HPAL plant, coastal cluster between Huafei and POS 14 —
  // owner's map, 2026-09-01) sits at the coast end of the stick, where
  // congestion/segments.py already puts it (NODE_KM 'BSE': 0.0). Without
  // this alias every 4.2/4.2.1 BSE route was filtered out of the animation
  // ("not mapped to the haul-road survey") and the stick showed a plan
  // missing ~1/3 of its LIM traffic. No survey polyline exists for the
  // BSE spur yet, so it rides the corridor to km 0; the tooltip says so.
  const extra=[{label:'POS 14',km:26.1,aliases:['POS 14','POS14']},{label:'POS 15',km:32.1,aliases:['POS 15','POS15']},{label:'POS 16',km:31.7,aliases:['POS 16','POS16']},
               {label:'BSE',km:0,aliases:['BSE','BSE-1','BSE1','BSE2','BSE5','BSE02','PT.BSE']}];
  const nodes=((((_D&&_D.corridor)||{}).nodes)||[]).concat(extra);
  const hit=nodes.find(nd=>(nd.aliases||[nd.label]).some(a=>flowNormName(a)===n));
  if(hit)return {kind:'corridor',label:hit.label,km:hit.km};
  const aliasHit=j=>{
    const aliases=j.aliases||[j.label];
    return aliases.some(a=>{
      const al=flowNormName(a);
      return n===al||n.startsWith(al+'.')||n.startsWith(al+' ');
    });
  };
  const join=flowJoins().find(aliasHit);
  if(!join)return null;
  return {
    kind:'spur',label:join.label,joinKm:join.joinKm,road:join.road,
    endKm:join.endKm,lat:join.endLat,lng:join.endLng,
    joinLat:join.joinLat,joinLng:join.joinLng,lengthKm:join.lengthKm,
    spurJoinKm:join.spurJoinKm,parent:join.parent||null,parentAtKm:join.parentAtKm
  };
}
function flowInterpLoop(loop,phase){
  if(!loop||loop.length<2)return {x:0,y:180,lat:null,lng:null,km:null};
  // Segment table is a property of the loop, not of the call: it was rebuilt
  // (hypot per vertex, ~150 vertices on a TF loop) for every particle on
  // every frame — 1,700 particles × 60 fps. Cached on the loop array itself
  // (renderFlowSimulator hands out a fresh array whenever geometry changes),
  // with cumulative lengths so the segment lookup is a binary search.
  let c=loop._segs;
  if(!c||c.n!==loop.length){
    const segs=[],cum=[0];let total=0;
    for(let i=1;i<loop.length;i++){
      const a=loop[i-1],b=loop[i];
      const len=Math.hypot((b.x-a.x),(b.y-a.y))||0.001;
      segs.push({a,b,len});total+=len;cum.push(total);
    }
    c=loop._segs={segs,cum,total,n:loop.length};
  }
  const {segs,cum,total}=c;
  let d=(((phase%1)+1)%1)*total;
  let lo=0,hi=segs.length-1;
  while(lo<hi){const mid=(lo+hi)>>1;if(cum[mid+1]<d)lo=mid+1;else hi=mid;}
  {
    const i=lo;d-=cum[i];
    const s=segs[i],t=Math.min(1,d/s.len);
    {
      const road=(s.a.road&&s.a.road===s.b.road)?s.a.road:s.a.road;
      const roadKm=(Number.isFinite(s.a.roadKm)&&Number.isFinite(s.b.roadKm)&&s.a.road===s.b.road)
        ?s.a.roadKm+(s.b.roadKm-s.a.roadKm)*t
        :(Number.isFinite(s.a.roadKm)?s.a.roadKm:s.a.km);
      // Map position is always a survey lookup at interpolated chainage — never a
      // lat/lng lerp between loop vertices (that draws chords across the island).
      // Only when a map is mounted for this host: the stick itself never
      // reads lat/lng, and the lookup is a linear scan of the survey chain
      // — the single largest per-particle cost when 1,700 trucks move.
      const ll=_flowNeedLL?flowLookupLL(road,roadKm):null;
      const km=(Number.isFinite(s.a.km)&&Number.isFinite(s.b.km))?s.a.km+(s.b.km-s.a.km)*t:s.a.km;
      return {x:s.a.x+(s.b.x-s.a.x)*t,y:s.a.y+(s.b.y-s.a.y)*t,
        lat:ll&&ll[0],lng:ll&&ll[1],km,road,roadKm,spur:!!(s.a.spur&&s.b.spur)};
    }
  }
}
function flowRoadPts(road){
  const alias={TF:'TOFU',KRENE:'KR',KR:'KR',TOFU:'TOFU'};
  const want=alias[(road||'').toUpperCase()]||(road||'').toUpperCase();
  const roads=(_flowGeom&&_flowGeom.roads)||[];
  const row=roads.find(x=>(x.road||'').toUpperCase()===want);
  return ((row&&row.points)||[]).slice().sort((a,b)=>a.km-b.km);
}
function flowLatLngOnRoad(road,km){
  if(!Number.isFinite(km))return null;
  const name=(road||'').toUpperCase();
  if(!name||name==='CORRIDOR'||name==='TOFU'||name==='KR'||name==='CRD'||name==='KRENE'||name==='TF'){
    return flowMapLatLngAt(km);
  }
  const pts=flowRoadPts(name);
  if(pts.length<2)return null;
  if(km<=pts[0].km)return[pts[0].lat,pts[0].lng];
  if(km>=pts[pts.length-1].km)return[pts[pts.length-1].lat,pts[pts.length-1].lng];
  for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i];
    if(km>=a.km&&km<=b.km){
      const t=(b.km===a.km)?0:(km-a.km)/(b.km-a.km);
      return[a.lat+(b.lat-a.lat)*t,a.lng+(b.lng-a.lng)*t];
    }
  }
  return[pts[0].lat,pts[0].lng];
}
function flowLookupLL(road,km){
  return flowLatLngOnRoad(road,km);
}
function flowSpurJoinKm(loc){
  return Number.isFinite(loc.spurJoinKm)?loc.spurJoinKm:loc.joinKm;
}
// Short branches used to be drawn as a horizontal "dock" laid ON the stick at
// their junction. That put HUAFEI's plant bulb on the main road at km 5.5,
// which the owner read as "it is on the road" (2026-09-03) — the survey has
// it as a 0.9 km branch NORTH of the corridor, beside the BLB branch at
// km 2.5. Every branch now hangs off the stick the same way (BLB long,
// HUAFEI short), so the drawing says what the geometry says. The stub path
// stays only as a switch, off by default.
function flowIsStickStub(loc){
  return false;
}
function flowStubLen(loc){
  return Math.max(56,(loc.lengthKm||1)*62);
}
// ONE spur height scale, shared by drawing and particle geometry (owner,
// 2026-08-24: make BLB a bit bigger — 13 px/km, cap 260).
function flowSpurH(loc){
  // Spur drop, px. Capped low (was 260): the BLB leg used to hang ~226px
  // under the road and the bottom half of the panel was dead space with two
  // bulbs in it (owner, 2026-08-25). 8 px/km keeps relative length readable
  // — BLB 17.4 km still draws ~3x CBB's span — without donating a third of
  // the canvas to empty background.
  // Floor raised 40 → 52 so a 0.9 km branch (HUAFEI) still has room for its
  // bulb + two label lines without touching the stick's km ruler.
  return Math.max(52,Math.min(140,(loc.lengthKm||8)*8));
}
function flowKmSamples(road,fromKm,toKm){
  const lo=Math.min(fromKm,toKm),hi=Math.max(fromKm,toKm);
  let kms=[];
  if(!road||road==='CORRIDOR'){
    kms=(_flowChain||[]).map(p=>p.km);
  }else{
    kms=flowRoadPts(road).map(p=>p.km);
  }
  kms=kms.filter(k=>Number.isFinite(k)&&k>=lo-1e-4&&k<=hi+1e-4);
  kms.push(fromKm,toKm);
  const uniq=[];
  kms.sort((a,b)=>fromKm<=toKm?a-b:b-a).forEach(k=>{
    if(!uniq.length||Math.abs(uniq[uniq.length-1]-k)>0.02)uniq.push(k);
  });
  if(uniq[0]!==fromKm)uniq.unshift(fromKm);
  if(uniq[uniq.length-1]!==toKm)uniq.push(toKm);
  return uniq;
}
// Road-graph walk: each spur may itself hang off another spur's road (HUAFEI
// sits on the road to BLB — FLOW_SPUR_PARENTS). flowUpChain climbs from a point
// on a road up to the stick, one leg per road crossed.
function flowUpChain(loc,fromKm){
  const legs=[];let cur=loc,km=fromKm;
  while(cur){
    legs.push({kind:'spur',loc:cur,fromKm:km,toKm:flowSpurJoinKm(cur)});
    if(!cur.parent)return {legs,stickKm:cur.joinKm};
    km=cur.parentAtKm;   // junction chainage in the PARENT road's own km
    cur=cur.parent;
  }
  return {legs,stickKm:km};
}
function flowLoadedLegs(r){
  const o=r.originLoc,d=r.destLoc;
  if(!o||!d)return [];
  const upO=o.kind==='spur'?flowUpChain(o,o.endKm):{legs:[],stickKm:o.km};
  const upD=d.kind==='spur'?flowUpChain(d,d.endKm):{legs:[],stickKm:d.km};
  const lo=upO.legs[upO.legs.length-1],ld=upD.legs[upD.legs.length-1];
  let legs;
  if(lo&&ld&&lo.loc.road===ld.loc.road&&(upO.legs.length>1||upD.legs.length>1)){
    // Both endpoints live on the same road (e.g. BLB→HUAFEI): cut at the
    // junction, no pointless round-trip down to the stick and back.
    legs=upO.legs.slice(0,-1);
    legs.push({kind:'spur',loc:lo.loc,fromKm:lo.fromKm,toKm:ld.fromKm});
    legs.push(...upD.legs.slice(0,-1).reverse().map(l=>({...l,fromKm:l.toKm,toKm:l.fromKm})));
  }else{
    legs=[...upO.legs];
    legs.push({kind:'corridor',fromKm:upO.stickKm,toKm:upD.stickKm});
    legs.push(...upD.legs.slice().reverse().map(l=>({...l,fromKm:l.toKm,toKm:l.fromKm})));
  }
  return legs.filter(leg=>Number.isFinite(leg.fromKm)&&Number.isFinite(leg.toKm));
}
function flowVerticesFromLegs(legs,X,y){
  const pts=[];
  legs.forEach((leg,li)=>{
    const road=leg.kind==='spur'?leg.loc.road:'CORRIDOR';
    const samples=flowKmSamples(road,leg.fromKm,leg.toKm);
    samples.forEach((km,si)=>{
      if(li>0&&si===0)return;
      if(leg.kind==='corridor'){
        const ll=flowMapLatLngAt(km);
        pts.push({x:X(km),y,km,road:'CORRIDOR',roadKm:km,lat:ll&&ll[0],lng:ll&&ll[1],spur:false});
      }else{
        const loc=leg.loc,ll=flowLatLngOnRoad(loc.road,km);
        const laneDx=y<200?-4.5:4.5;
        if(loc.parent){
          // Nested spur (HUAFEI on the road to BLB): a horizontal two-lane
          // branch leaving the parent's vertical road at the junction height.
          const p=loc.parent,pH=flowSpurH(p);
          const pJoin=flowSpurJoinKm(p),pPit=p.endKm;
          const pT=(pPit===pJoin)?0:Math.abs(loc.parentAtKm-pJoin)/Math.max(1e-6,Math.abs(pPit-pJoin));
          const yJ=226+pH*pT;
          const join=flowSpurJoinKm(loc),pit=loc.endKm;
          const t=(pit===join)?0:Math.abs(km-join)/Math.max(1e-6,Math.abs(pit-join));
          const len=Math.max(40,(loc.lengthKm||1)*44);
          pts.push({x:X(p.joinKm)-4.5-len*t,y:yJ+(y<200?-4.5:4.5),km:p.joinKm,road:loc.road,roadKm:km,
            lat:ll&&ll[0],lng:ll&&ll[1],spur:t>0.02});
        }else if(flowIsStickStub(loc)){
          const join=flowSpurJoinKm(loc),pit=loc.endKm;
          const t=(pit===join)?0:Math.abs(km-join)/Math.max(1e-6,Math.abs(pit-join));
          const len=flowStubLen(loc);
          pts.push({x:X(loc.joinKm)-len*t,y:y,km:loc.joinKm,road:loc.road,roadKm:km,
            lat:ll&&ll[0],lng:ll&&ll[1],spur:t>0.02});
        }else{
          // Top-level spur: two-lane vertical road hanging off the stick's
          // bottom edge (y=226); loaded (y=180) keeps left, empty (y=210) right.
          const h=flowSpurH(loc);
          const pit=loc.endKm,join=flowSpurJoinKm(loc);
          const t=(pit===join)?0:Math.abs(km-join)/Math.max(1e-6,Math.abs(pit-join));
          // Lane offset follows the drawn road width (26 px → ±4.5, 18 px → ±3).
          const dx=(loc.lengthKm||8)<4?(y<200?-3:3):laneDx;
          pts.push({x:X(loc.joinKm)+dx,y:226+h*t,km:loc.joinKm,road:loc.road,roadKm:km,
            lat:ll&&ll[0],lng:ll&&ll[1],spur:t>0.02});
        }
      }
    });
  });
  return pts;
}
function flowBuildRouteLoop(r,X){
  const legs=flowLoadedLegs(r);
  const L=flowVerticesFromLegs(legs,X,180);
  const rev=legs.slice().reverse().map(leg=>({...leg,fromKm:leg.toKm,toKm:leg.fromKm}));
  const E=flowVerticesFromLegs(rev,X,210);
  if(L.length<2||!E.length)return L;
  const dump={...L[L.length-1],y:E[0].y};
  const load={...E[E.length-1],y:L[0].y};
  return L.concat([dump],E.slice(1),[load]);
}
function stopFlowSimulator(){if(_flowSim&&_flowSim.raf)cancelAnimationFrame(_flowSim.raf);if(_flowSim){_flowSim.raf=null;_flowSim.running=false;}const b=flowQ('c3-flow-play');if(b)b.textContent=flowPlayLabel();}
function updateFlowSimulator(){
  const s=_flowSim;if(!s)return;
  {const mst=flowMapState();_flowNeedLL=!!(mst.map&&mst.trucks&&_flowChain&&_flowChain.length);}const clock=(FLOW_SHIFT_START*60+Math.round(s.hour*60))%(24*60);
  const clockEl=flowQ('c3-flow-clock');if(clockEl)clockEl.textContent=String(Math.floor(clock/60)).padStart(2,'0')+':'+String(clock%60).padStart(2,'0');
  const prog=flowQ('c3-flow-progress');if(prog)prog.style.width=(100*s.hour/FLOW_SHIFT_HOURS).toFixed(1)+'%';
  // Phase C: simulate shortfall only tints congestion feel — never invents trip KPIs.
  const tint=Math.max(0,Math.min(1,1-_flowSimRatio));
  s.routes.forEach(r=>buildFlowMotion(r,s.inputs,Math.max(s.liveCongestion||0,tint*0.85)));
  const shiftTrips=_flowMode==='plan'?s.achievedTrips:s.dbTrips,completed=shiftTrips*s.hour/FLOW_SHIFT_HOURS;
  // Element handles cached on the route (1,700 getElementById per frame
  // was ~2 ms); visibility written only on change.
  const setVis=(el,v)=>{if(el._vis!==v){el.setAttribute('visibility',v);el._vis=v;}};
  const moving=[];s.routes.forEach((r,i)=>{const els=r._els||(r._els=[]);for(let j=0;j<r.particles;j++){const id=i+'-'+j,el=els[j]||(els[j]=flowQ('flow-p-'+id)),depart=r.departures[j]||0;if(!el)continue;if(s.hour<depart){setVis(el,'hidden');continue;}const active=Math.max(0,Math.min(FLOW_SHIFT_HOURS,s.hour-depart)),cycleTime=(r.startTimes[j]+(active?r.achievedTr*active/FLOW_SHIFT_HOURS:0))%1,phase=flowMotionPhase(r,cycleTime),pt=flowPointAt(r,phase);setVis(el,'visible');moving.push({id,el,x:pt.x,y:pt.y,minX:r.corrX1!=null?r.corrX1:r.sourceX,maxX:r.corrX2!=null?r.corrX2:r.destX,weight:r.particleWeight,lat:pt.lat,lng:pt.lng,km:pt.km,road:pt.road,roadKm:pt.roadKm,spur:!!pt.spur});}});
  // Non-WBN white trucks join the SAME convoy as WBN (one physical lane → nobody overtakes). Hidden off.
  if(s.otherRoutes)s.otherRoutes.forEach((r,i)=>{for(let j=0;j<r.particles;j++){const el=flowQ('flow-op-'+i+'-'+j);if(!el)continue;if(!_otherInModel){el.setAttribute('visibility','hidden');continue;}const cycleTime=(r.startTimes[j]+r.achievedTr*s.hour/FLOW_SHIFT_HOURS)%1,pt=flowPointAt(r,flowMotionPhase(r,cycleTime));el.setAttribute('visibility','visible');moving.push({id:'o'+i+'-'+j,el,x:pt.x,y:pt.y,minX:r.sourceX,maxX:r.destX,weight:1});}});
  // ── ONE-LANE FOLLOW RULE ──────────────────────────────────────────────
  // (Rewritten 2026-09-03. Owner: "the movement of the dots, especially
  // going back to TOFU, is not real, it's not calculated.")
  //
  // Every truck has a FREE position from its own motion model: GPS
  // segment speeds, dump/load dwell, and the residual wait that makes the
  // measured trips/DT come out. That is the calculated part. The road is
  // one lane each way with no overtaking, so the only thing this pass may
  // do is HOLD a truck behind a slower one. It may never advance a truck
  // past its free position, never reverse it, and never let it pass.
  //
  // Per lane, in road order (furthest along in the direction of travel
  // first):   drawn = min_dir( free,  drawn_prev + step,  drawn_ahead - gap )
  //           drawn = max_dir( drawn, drawn_prev )
  // gap  = 1.2 px (~85 m at 72 m/px). The Nov plan has ~250 loaded TF>POS
  //        12 trucks on 569 px of road at once (701 DT x 2.7 h / 7.7 h
  //        cycle): 2.3 px each. A larger gap cannot fit the plan on the
  //        road and holds every truck behind its own motion (measured at
  //        2.4 px: all routes 150-560 px back).
  // step = 3x the fastest free speed, so a truck released from a queue
  //        closes on its motion visibly but never teleports.
  // Yard: a truck is off the lane (neither held nor a leader) while its
  //        free motion sits at its entry (loading/waiting) or it is drawn
  //        within one node radius of its exit (turning in).
  // Road order comes from last DRAWN x, so a truck held behind a slower
  // one cannot be re-sorted past it when its free x moves ahead.
  const states=s.vehicleStates||(s.vehicleStates={}),laneOf=p=>Math.abs(p.y-180)<.8?'loaded':Math.abs(p.y-210)<.8?'empty':null;
  moving.forEach(p=>{const st=states[p.id]||(states[p.id]={lane:null,drawnX:NaN}),lane=laneOf(p);if(st.lane!==lane){st.lane=lane;st.drawnX=NaN;}});
  ['loaded','empty'].forEach(lane=>{
    const fwd=lane==='loaded'?1:-1, gap=1.2, step=Math.max(8,13*flowPlaybackRate());
    const prevOf=p=>{const st=states[p.id];return (st&&st.lane===lane&&Number.isFinite(st.drawnX))?st.drawnX:null;};
    const inYard=p=>{const entryX=fwd>0?p.minX:p.maxX,exitX=fwd>0?p.maxX:p.minX;if(Math.abs(p.x-entryX)<.5)return true;const k=prevOf(p)??p.x;return Math.abs(k-exitX)<6;};
    const current=moving.filter(p=>laneOf(p)===lane);
    current.sort((a,b)=>{const ka=prevOf(a)??a.x,kb=prevOf(b)??b.x;return fwd*(kb-ka);});
    let leadX=null;
    current.forEach(p=>{
      const prev=prevOf(p);
      if(inYard(p)){if(prev!=null&&fwd*(p.x-prev)>step)p.x=prev+fwd*step;return;}
      let hi=prev!=null?prev+fwd*step:p.x;
      if(leadX!=null){const wall=leadX-fwd*gap;if(fwd*(wall-hi)<0)hi=wall;}
      if(prev!=null&&fwd*(hi-prev)<0)hi=prev;
      if(fwd*(p.x-hi)>0)p.x=hi;
      if(prev!=null&&fwd*(p.x-prev)<0)p.x=prev;
      if(p.x<p.minX-.01||p.x>p.maxX+.01){p.x=fwd>0?p.minX:p.maxX;setVis(p.el,'hidden');return;}
      const exitX=fwd>0?p.maxX:p.minX;
      if(Math.abs(p.x-exitX)>=6)leadX=p.x;
    });
    current.forEach(p=>{const st=states[p.id];if(st)st.drawnX=p.el._vis==='hidden'?NaN:p.x;});
  });
  moving.forEach(p=>{
    // Write the transform only when it changes: with 1,300 visible trucks
    // the DOM attribute set is the largest per-frame cost, and ~40% of
    // them are parked in a yard or held in a queue on any given frame.
    const tr=`translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`;
    if(p.el._tr!==tr){p.el.setAttribute('transform',tr);p.el._tr=tr;}
    // Highlight a truck while it's crossing between the loaded and empty lanes (the dump/load turnaround)
    // so the state change is clearly visible instead of an instant lane-swap.
    const cross=!p.spur&&Math.abs(p.y-180)>=.8&&Math.abs(p.y-210)>=.8;
    // Turnaround highlight eases in/out over ~6 frames instead of snapping
    // between two radii — the snap read as a flicker at the dump/load ends.
    const c=p.el._c||(p.el._c=p.el.querySelector('circle:not(.fp-halo)'));
    const h=p.el._h||(p.el._h=p.el.querySelector('.fp-halo'));
    let k=p.el._k==null?0:p.el._k;
    k+=cross?(1-k)*.35:(0-k)*.35;
    if(Math.abs(k-(p.el._k==null?0:p.el._k))>.004){
      if(c){c.setAttribute('r',(1.25+1.6*k).toFixed(2));c.setAttribute('stroke','#fff');c.setAttribute('stroke-width',(0.7*k).toFixed(2));c.setAttribute('opacity',(0.92+0.08*k).toFixed(2));}
      if(h){h.setAttribute('r',(2.6+2.4*k).toFixed(2));h.setAttribute('opacity',(0.16+0.22*k).toFixed(2));}
      p.el._k=k;
    }
  });
  const visNow=moving.filter(p=>p.el._vis!=='hidden');
  const loadedNow=visNow.filter(p=>Math.abs(p.y-180)<.8).length,emptyNow=visNow.filter(p=>Math.abs(p.y-210)<.8).length,crossoverNow=visNow.filter(p=>!p.spur&&Math.abs(p.y-180)>=.8&&Math.abs(p.y-210)>=.8).length;
  const onRoadEl=flowQ('flow-onroad');
  if(onRoadEl){
    const onLab=flowQ('flow-onroad-label');
    if(s.running){
      const onRoad=visNow.reduce((n,p)=>n+(Number(p.weight)||1),0);
      onRoadEl.textContent=fmt(onRoad,0);
      if(onLab)onLab.textContent='DT now · illustration';
    }else{
      const fleet=s.routes.reduce((n,r)=>n+(Number(r.dt)||0)*((s.inputs&&s.inputs.fleet)||1),0);
      onRoadEl.textContent=fmt(fleet,0);
      if(onLab)onLab.textContent='DT on corridor';
    }
  }
  const metaHost=flowQ('c3-flow-meta');
  if(metaHost){
    if(_flowHost==='plan'){
      metaHost.innerHTML=`<div class="flow-run-status flow-run-status-slim">
        <span class="flow-run-chip"><b>${fmt(flowPlaybackRate(),1)}×</b></span>
        <span class="flow-run-chip">On road <b>${loadedNow+emptyNow}</b></span>
      </div>`;
    }else{
    const tripSrc=_flowMode==='plan'?'Path-response':'Dispatch';
    const tintChip=_flowSimRatio<0.999?`<span class="flow-run-chip">Simulate tint <b>${fmt(100*_flowSimRatio,0)}%</b> <span class="muted">achievable</span></span>`:'';
    metaHost.innerHTML=`<div class="flow-run-status">
      <span class="flow-run-chip"><b>${escH(s.band)}</b> load</span>
      <span class="flow-run-chip">Density <b>${fmt(s.liveDensity||0,2)}</b> <span class="muted">DT/km</span></span>
      <span class="flow-run-chip">Corridor <b>${fmt(s.corridorKm,1)}</b> <span class="muted">km</span></span>
      <span class="flow-run-chip">${tripSrc} <b>${fmt(completed)}</b> <span class="muted">/ ${fmt(shiftTrips)} trips</span></span>
      <span class="flow-run-chip">Playback <b>${fmt(flowPlaybackRate(),1)}×</b> <span class="muted">cartoon clock</span></span>
      <span class="flow-run-chip">On screen <b>${loadedNow}</b> <span class="muted">loaded</span> · <b>${emptyNow}</b> <span class="muted">empty</span> · <b>${crossoverNow}</b> <span class="muted">turn</span></span>
      ${tintChip}
      <p class="flow-run-note">Linear progress clock — not an event simulator.</p>
    </div>`;
    }
  }
  const ranges={1:[67.8,39],2:[39,27],3:[27,17],4:[17,0]},activeRanges=[..._gSelSec].map(id=>ranges[+id]).filter(Boolean),kmAt=x=>s.corridorKm-(x-s.roadLeft)/(s.roadRight-s.roadLeft)*s.corridorKm,densities=activeRanges.map(z=>{const weight=moving.reduce((n,p)=>{if(p.spur)return n;const km=Number.isFinite(p.km)?p.km:kmAt(p.x),onLane=Math.abs(p.y-180)<.8||Math.abs(p.y-210)<.8;return n+(onLane&&km<=z[0]&&km>=z[1]?p.weight:0);},0);return weight/Math.max(.1,z[0]-z[1]);}),density=Math.max(0,...densities),pressure=Math.max(0,Math.min(1,(density-2)/4));s.liveCongestion=(s.liveCongestion||0)+.08*(pressure-(s.liveCongestion||0));s.liveDensity=density;
  // Project visible particles onto the GPS polyline map (chainage → lat/lng, or spur coords).
  flowMapSync(moving.filter(p=>p.el._vis!=='hidden').map(p=>{
    const c=p.el._c||p.el.querySelector('circle:not(.fp-halo)');
    return {id:p.id,km:p.km,road:p.road,roadKm:p.roadKm,lat:p.lat,lng:p.lng,loaded:Math.abs(p.y-180)<.8,col:(c&&c.getAttribute('fill'))||'#38bdf8'};
  }));
}
// Skip the PAINT when nobody can see it. The per-frame work moves every
// particle (~1 per DT — a December plan is ~1,270 of them), re-sorts both
// lanes and syncs Leaflet markers, and it kept doing all of that at full
// requestAnimationFrame rate while the card was scrolled away or the window
// sat behind another app — measured 2026-08-27 as a browser renderer pinned
// at ~50-60% CPU for the whole replay. The CLOCK still advances and the
// replay still completes (planOnIllustrationFinished must fire — the Plan
// flow stages off it); only the visual work is skipped, and the first
// visible frame repaints the current state in full.
let _flowStageOnScreen=true,_flowStageObserved=null,_flowStageHoldUntil=0;
const _flowStageIO=(typeof IntersectionObserver!=='undefined')
  ?new IntersectionObserver(es=>{es.forEach(e=>{
      if(e.isIntersecting||performance.now()<_flowStageHoldUntil)_flowStageOnScreen=true;
      else _flowStageOnScreen=false;
    });})
  :null;
function flowHoldStageVisible(ms){
  _flowStageOnScreen=true;
  _flowStageHoldUntil=performance.now()+(ms||1600);
}
function flowObserveStage(){
  if(!_flowStageIO)return;
  const el=flowQ('c3-flow-visuals')||flowQ('c3-flow-svg');
  if(!el||el===_flowStageObserved)return;
  if(_flowStageObserved)_flowStageIO.unobserve(_flowStageObserved);
  _flowStageIO.observe(el);
  _flowStageObserved=el;
  _flowStageOnScreen=true;   // assume visible until the observer reports
}
function flowPlaybackRate(){
  const r=Number(_flowPlaybackRate);
  return Number.isFinite(r)&&r>0?r:1;
}
function flowSetPlaybackRate(n){
  const r=Number(n);
  if(!(r>0))return;
  _flowPlaybackRate=r;
  document.querySelectorAll('[data-flow-rate]').forEach(b=>{
    b.classList.toggle('on', Number(b.getAttribute('data-flow-rate'))===r);
  });
}
function flowFrame(ts){const s=_flowSim;if(!s||!s.running)return;if(!s.last)s.last=ts;const dt=Math.min(.1,(ts-s.last)/1000);s.last=ts;s.hour=Math.min(FLOW_SHIFT_HOURS,s.hour+dt*FLOW_SHIFT_HOURS/24*flowPlaybackRate());
  if(!document.hidden&&_flowStageOnScreen)updateFlowSimulator();
  if(s.hour>=FLOW_SHIFT_HOURS){
  // One final full paint regardless of visibility, so the completed state is
  // what the user finds when they scroll back — a replay that "finished
  // blank" reads as a crash.
  updateFlowSimulator();
  stopFlowSimulator();
  // Plan host: the illustration finished its full clock — run the full
  // assessment (prediction) underneath. Staged: illustration → predict → results.
  if(_flowHost==='plan'&&typeof planOnIllustrationFinished==='function'){
    try{planOnIllustrationFinished();}catch(_){}
  }
  return;}s.raf=requestAnimationFrame(flowFrame);}
function flowToggle(){const s=_flowSim;if(!s)return;if(s.running){stopFlowSimulator();return;}if(s.hour>=FLOW_SHIFT_HOURS){s.hour=0;s.liveCongestion=0;s.liveDensity=0;s.vehicleStates={};s.laneOrders={loaded:[],empty:[]};}if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches){s.hour=FLOW_SHIFT_HOURS;updateFlowSimulator();
  if(_flowHost==='plan'&&typeof planOnIllustrationFinished==='function'){try{planOnIllustrationFinished();}catch(_){}}
  return;}s.running=true;s.last=0;flowObserveStage();flowHoldStageVisible(1600);const play=flowQ('c3-flow-play');if(play)play.textContent='Ⅱ Pause';s.raf=requestAnimationFrame(flowFrame);}
function flowReset(){stopFlowSimulator();if(_flowSim){_flowSim.hour=0;_flowSim.liveCongestion=0;_flowSim.liveDensity=0;_flowSim.vehicleStates={};_flowSim.laneOrders={loaded:[],empty:[]};updateFlowSimulator();}}
// When false (default), motion uses corridor.measuredSpeeds (GPS). Advanced km/h
// inputs are display/override only — touching them sets _flowSpeedOverride.
let _flowSpeedOverride=false;
function flowInputs(){
  const n=(id,d)=>{const e=flowQ(id),v=e&&parseFloat(e.value);return Number.isFinite(v)?v:d;};
  // Plan host: always stage at loading point (source). Capability may use Split /
  // destination for what-if cartoons — that made Plan look like trucks spawn at dump.
  const startDefault=_flowHost==='plan'?'source':((flowQ('flow-start')||{}).value||'split');
  return {start:startDefault,
    loaded:n('flow-loaded-speed',25),empty:n('flow-empty-speed',35),
    stagger:n('flow-stagger',0),headway:n('flow-headway',90),dwell:n('flow-dwell',12),
    hours:FLOW_SHIFT_HOURS,fleet:1,
    elements:Math.round(n('flow-elements',500)),
    elementsTouched:Math.round(n('flow-elements',500))!==500,
    speedOverride:_flowSpeedOverride};
}
function flowMeasuredBands(){return (((_D&&_D.corridor)||{}).measuredSpeeds)||[];}
function flowPostedLimits(){return ((((_D&&_D.corridor)||{}).speedLimits)||[]).filter(x=>x.limit>0);}
function gpsSpeedAt(km, loaded, fallback){
  const bands=flowMeasuredBands();
  let nearest=null, best=1e9;
  for(let i=0;i<bands.length;i++){
    const b=bands[i], lo=Math.min(b.fromKm,b.toKm), hi=Math.max(b.fromKm,b.toKm);
    const v=loaded?b.loadedKmh:b.emptyKmh;
    if(km<=hi+1e-6&&km>=lo-1e-6&&Number.isFinite(v)) return Math.max(1, v);
    const mid=(lo+hi)/2, d=Math.abs(km-mid);
    if(d<best&&Number.isFinite(v)){best=d; nearest=v;}
  }
  if(nearest!=null) return Math.max(1, nearest);
  const vals=bands.map(b=>loaded?b.loadedKmh:b.emptyKmh).filter(Number.isFinite).sort((a,b)=>a-b);
  if(vals.length) return Math.max(1, vals[Math.floor(vals.length/2)]);
  return fallback;
}
// 'gps' | 'trip-implied' | 'manual' — only affects map cartoon, never trips/WMT.
let _flowMotionMode='gps';
function flowSeedGpsInputs(){
  // Keep hidden override fields in sync with GPS medians (display only while GPS is on).
  const bands=flowMeasuredBands();
  if(!bands.length) return;
  const L=bands.map(b=>b.loadedKmh).filter(Number.isFinite).sort((a,b)=>a-b);
  const E=bands.map(b=>b.emptyKmh).filter(Number.isFinite).sort((a,b)=>a-b);
  const med=a=>a[Math.floor(a.length/2)];
  if(L.length&&flowQ('flow-loaded-speed')) flowQ('flow-loaded-speed').value=med(L).toFixed(1);
  if(E.length&&flowQ('flow-empty-speed')) flowQ('flow-empty-speed').value=med(E).toFixed(1);
}
function flowUpdateMotionModeUi(){
  const gps=!_flowSpeedOverride;
  const banner=q('flow-motion-banner'),label=q('flow-motion-mode-label'),detail=q('flow-motion-mode-detail');
  const manual=q('flow-speed-manual');
  const nBands=flowMeasuredBands().length;
  const win=(((_D&&_D.corridor)||{}).measuredWindow)||{};
  const winTxt=(win.from&&win.to)?`${win.from} → ${win.to}`:'GPS extract';
  if(banner){banner.className='flow-motion-banner '+(gps?'gps':'override');}
  if(label)label.textContent=gps?'● Measured GPS motion':'◆ Speed override (debug)';
  if(detail){
    const struggle=!!(win&&win.struggleSeasonExtract);
    detail.textContent=gps
      ?(struggle
        ?`Each DT moves on GPS segment speeds (${nBands} bands · ${winTxt}). Jul struggle extract only — Jan–May peak has no corridor GPS. Trips/tonnes still from predict/simulate.`
        :`Each DT moves on GPS segment speeds (${nBands} bands · ${winTxt}). No manual speed entry.`)
      :'Cartoon uses Loaded/Empty km/h below (typed or filled from trip rate). Same override mode — not a second engine. Trips/WMT unchanged.';
  }
  if(manual)manual.hidden=gps;
  const on=(id,yes)=>{const b=q(id);if(b)b.classList.toggle('on',!!yes);};
  on('flow-btn-gps',gps);
  on('flow-btn-override',!gps);
}
function flowUseMeasuredGps(){
  _flowSpeedOverride=false;_flowMotionMode='gps';_flowSpeedsInitialised=true;
  flowSeedGpsInputs();
  flowUpdateMotionModeUi();
  if(_flowSim&&_flowSource){stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);}
}
function flowShowManualSpeeds(){
  _flowSpeedOverride=true;_flowMotionMode='manual';_flowSpeedsInitialised=true;
  flowUpdateMotionModeUi();
  if(_flowSim&&_flowSource){stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);}
}
function otherPathMult(p){const d=_otherDraft&&_otherDraft[p.label];return p.trucks?((Number.isFinite(d)?d:p.trucks)/p.trucks):1;}
// non-WBN trips on a corridor section, from the (edited) per-path counts — 0 when the toggle is off
function otherSectionTrips(label){if(!_otherInModel||!_otherCtx||!_otherCtx.paths)return 0;const sec=OTHER_SECS.find(s=>s[0]===label);if(!sec)return 0;let t=0;_otherCtx.paths.forEach(p=>{const lo=Math.min(p.oKm,p.dKm),hi=Math.max(p.oKm,p.dKm);if(hi>sec[1]&&lo<sec[2])t+=p.trips*otherPathMult(p);});return t;}
// change in non-WBN trips (vs actual) on the shared POS→FENI corridor — drives the FENI-route effect
function otherFeniDelta(){if(!_otherInModel||!_otherCtx||!_otherCtx.paths)return 0;let d=0;_otherCtx.paths.forEach(p=>{if(Math.min(p.oKm,p.dKm)<17)d+=p.trips*(otherPathMult(p)-1);});return d;}
function flowRouteTarget(r){
  const m=_pathResp&&_pathResp[r.key];
  // Prefer the rain-controlled fleet coefficient (bAdj) — the pure fleet effect once weather is
  // removed — falling back to the simple slope. Only a measured decline is applied.
  const slope=m?(Number.isFinite(m.bAdj)&&m.bAdj<0?m.bAdj:m.b):0;
  let eff;
  if(m&&slope<0&&Number.isFinite(r.dbDt)){
    r.predEff=true;r.effR2=m.r2;r.dtMax=m.dtMax;r.effSlope=slope;
    eff=r.tr+slope*(r.dt-r.dbDt);                          // efficiency drops as fleet grows past actual
  }else{r.predEff=false;eff=r.tr;}
  // Non-WBN (IWIP/Position) congestion: only FENI-bound routes share the POS→FENI section they load.
  r.otherEff=0;
  if(_otherInModel&&_otherCtx&&r.toKm<17){
    const delta=otherFeniDelta();
    if(delta!==0){r.otherEff=OTHER_TRAFFIC_COEF*delta;eff+=r.otherEff;r.predEff=true;}
  }
  return Math.max(0.4*r.tr,eff);
}
// Rain sensitivity for a route (mm→trips-per-DT), expressed as % of mean eff on a typical 10 mm wet day.
function flowRainPct(r){const m=_pathResp&&_pathResp[r.key];if(!m||!Number.isFinite(m.cRain)||!m.avgTr)return null;return 100*m.cRain*10/m.avgTr;}
function flowMotionPhase(r,t){const m=r.motion||[{t:0,g:0},{t:1,g:1}];for(let i=1;i<m.length;i++)if(t<=m[i].t){const a=m[i-1],b=m[i],u=(t-a.t)/(b.t-a.t||1);return a.g+u*(b.g-a.g);}return 1;}
function buildFlowMotion(r,p,vc){
  const ranges={1:[67.8,39],2:[39,27],3:[27,17]},selected=[..._gSelSec].map(id=>ranges[+id]).filter(Boolean);
  const limits=flowPostedLimits(), maxDbLimit=limits.length?Math.max(...limits.map(x=>x.limit)):80;
  const inside=km=>selected.some(z=>km<=z[0]&&km>=z[1]);
  const limitAt=km=>{const matches=limits.filter(x=>km<=x.fromKm&&km>=x.toKm);return matches.length?Math.min(...matches.map(x=>x.limit)):maxDbLimit;};
  const dist=Math.abs(r.fromKm-r.toKm),cuts=[r.fromKm,r.toKm];
  selected.forEach(z=>{[z[0],z[1]].forEach(k=>{if(k<r.fromKm&&k>r.toKm)cuts.push(k);});});
  limits.forEach(z=>{[z.fromKm,z.toKm].forEach(k=>{if(k<r.fromKm&&k>r.toKm)cuts.push(k);});});
  flowMeasuredBands().forEach(z=>{[z.fromKm,z.toKm].forEach(k=>{if(k<r.fromKm&&k>r.toKm)cuts.push(k);});});
  cuts.sort((a,b)=>b-a);
  let congested=0;for(let i=1;i<cuts.length;i++){const d=cuts[i-1]-cuts[i],mid=(cuts[i-1]+cuts[i])/2;if(inside(mid))congested+=d;}
  const slow=Math.max(.3,Math.min(1,1-.7*Math.max(0,vc)));
  // GPS-first: never stretch speeds to match trip rate (sharedOpenFactor stays 1).
  const openFactor=1;
  const useGps=!p.speedOverride&&flowMeasuredBands().length>0;
  r.congestedFactor=slow;r.openFactor=openFactor;r.congestedKm=congested;r.speedSource=useGps?'gps':(p.speedOverride?'override':'fallback');
  const roadPx=Math.max(1,r.destX-r.sourceX),loopPx=2*roadPx+60,gLoaded=roadPx/loopPx,gDump=(roadPx+30)/loopPx,gEmpty=(2*roadPx+30)/loopPx,segments=[];
  const addTravel=(from,to,loaded)=>{
    const descending=from>to;
    const pts=cuts.filter(k=>k<=Math.max(from,to)&&k>=Math.min(from,to)).sort((a,b)=>descending?b-a:a-b);
    if(pts[0]!==from)pts.unshift(from);if(pts[pts.length-1]!==to)pts.push(to);
    for(let i=1;i<pts.length;i++){
      const d=Math.abs(pts[i]-pts[i-1]), mid=(pts[i]+pts[i-1])/2, limit=limitAt(mid);
      const requested=loaded?p.loaded:p.empty;
      const base=useGps?gpsSpeedAt(mid,loaded,requested):Math.max(1,requested);
      const speed=Math.max(1, base*(inside(mid)?slow:1));
      segments.push({hours:d/speed,km:d,loaded,speed,limit,overLimit:base>limit+0.5,congested:inside(mid),gps:useGps});
    }
  };
  addTravel(r.fromKm,r.toKm,true);segments.push({hours:p.dwell/120,cross:'dump'});
  addTravel(r.toKm,r.fromKm,false);segments.push({hours:p.dwell/120,cross:'load'});
  // The trip rate implies a LOOP time (shift hours / trips-per-shift) far longer
  // than the driving time: on TF>FENI the drive is ~1.5 h but the measured
  // effective cycle is ~11 h. Without representing that residual, the animation
  // stretched the drive over the whole loop — trucks crawled and never visibly
  // returned to the loading point, which read as "trips never finish". The
  // residual (shovel queue, refuelling, breaks, standby) is idle time AT the
  // loading point, so draw it as exactly that: park the particle there.
  {
    const drivingH=segments.reduce((s,x)=>s+x.hours,0);
    const tr=Number.isFinite(r.targetTr)&&r.targetTr>0.05?r.targetTr:0;
    const loopH=tr?p.hours/tr:0;
    const residH=loopH>drivingH?loopH-drivingH:0;
    if(residH>0.02)segments.push({hours:residH,cross:'wait'});
    r.residualWaitH=residH;
  }
  const travel=segments.filter(x=>x.speed),loadedTravel=travel.filter(x=>x.loaded),emptyTravel=travel.filter(x=>!x.loaded);
  const cL=loadedTravel.filter(x=>x.congested),cE=emptyTravel.filter(x=>x.congested);
  r.loadedSpeedRange=loadedTravel.length?[Math.min(...loadedTravel.map(x=>x.speed)),Math.max(...loadedTravel.map(x=>x.speed))]:[0,0];
  r.emptySpeedRange=emptyTravel.length?[Math.min(...emptyTravel.map(x=>x.speed)),Math.max(...emptyTravel.map(x=>x.speed))]:[0,0];
  r.congestedLoaded=cL.length?Math.min(...cL.map(x=>x.speed)):null;
  r.congestedEmpty=cE.length?Math.min(...cE.map(x=>x.speed)):null;
  r.maxOpen=travel.filter(x=>!x.congested).reduce((m,x)=>Math.max(m,x.speed),0);
  const overKm=travel.filter(x=>x.overLimit).reduce((s,x)=>s+x.km,0);
  r.overLimitPct=dist?100*overKm/dist:0;
  const total=segments.reduce((s,x)=>s+x.hours,0)||1;let time=0,g=0,travelledLoaded=0,travelledEmpty=0;r.motion=[{t:0,g:0}];
  segments.forEach(x=>{time+=x.hours/total;if(x.cross==='dump')g=gDump;else if(x.cross==='load')g=1;else if(x.cross==='wait')g=1;else if(x.loaded){travelledLoaded+=x.km;g=gLoaded*travelledLoaded/dist;}else{travelledEmpty+=x.km;g=gDump+(gEmpty-gDump)*travelledEmpty/dist;}r.motion.push({t:time,g});});
  r.destTimeFraction=segments.filter(x=>x.loaded).reduce((s,x)=>s+x.hours,0)/total;
  // Plan host keeps its per-truck cycle phases (set once at render).
  if(_flowHost!=='plan')r.startTimes=r.startTimes.map((_,j)=>p.start==='destination'?r.destTimeFraction:p.start==='split'&&j%2?r.destTimeFraction:0);
  return total;
}
// ── Official road geometry — the ONE capacity basis ─────────────────────────
// This readout used to divide by `_D.corridor.measuredCapacity` (~54 tph, the
// Jul GPS "struggle-season" extract). That is a DEMONSTRATED PEAK, not a
// capacity — the same "the most we ever did read as the most we can do" trap
// that sections.py (2026-08-23) and the BLB pricing capacity were already
// migrated off. Measured on the 2026-12-04 plan it put Peak V/C at 7.13 on the
// same screen where the crowding grid, Excel and the physics model all read
// under 1.0, because they divide by the official geometry and this did not.
//
// Capacity now comes from /api/road_segments (congestion/speed_limits.py:
// min bin speed x 1000 / FOLLOWING_DISTANCE_M, one loaded lane). The literals
// below are the OFFLINE FALLBACK only, matching congestion/segments.py at
// 50 m following — edit the Python, not this, and let the fetch hydrate.
const FLOW_SEG_FALLBACK=[
  {id:'S1',label:'TF–KR',      top_km:67.8,bottom_km:39.0,cap_hr:600},
  {id:'S2',label:'KR–POS 12',  top_km:39.0,bottom_km:27.0,cap_hr:600},
  {id:'S3',label:'POS 12–KM15',top_km:27.0,bottom_km:15.0,cap_hr:600},
  {id:'S4',label:'KM15–coast', top_km:15.0,bottom_km:0.0, cap_hr:400},
];
let _flowSegs=FLOW_SEG_FALLBACK.slice(),_flowSegMeta={source:'fallback',followingM:50};
function flowRoadSegments(){return _flowSegs;}

// Other tenants' trucks: a FLOW, never a truck count at our tempo.
// congestion/tenants.py owns the register and serves {segment_id: trucks/hr}
// on the loaded lane, each fleet clocked on ITS OWN cycle. The tenant plan
// rows are deliberately kept out of _flowSim.routes (see planDraftToFlowSeed),
// so this is where their road demand comes back in. Empty until fetched, so a
// cold page under-states the road rather than inventing traffic.
let _flowTenantFlow={};
function flowTenantSegmentFlow(segId){
  const v=Number(_flowTenantFlow[segId]);
  return Number.isFinite(v)&&v>0?v:0;
}
function flowHydrateSegments(d){
  const segs=d&&d.ok&&Array.isArray(d.segments)?d.segments:null;
  if(!segs||!segs.length)return;
  _flowSegs=segs.map(s=>({id:s.id,label:s.label,top_km:s.top_km,bottom_km:s.bottom_km,
    cap_hr:Number(s.cap_hr)||0})).filter(s=>s.cap_hr>0);
  _flowSegMeta={source:'api',followingM:((d.road||{}).following_distance_m)||50,
    basis:d.capacity_basis||null};
  if(typeof _flowSim!=='undefined'&&_flowSim&&typeof evaluateFlowScenario==='function')evaluateFlowScenario();
}
function flowLaneCapacity(){
  // Corridor-wide figure = the TIGHTEST official section, so the headline can
  // never claim more headroom than the binding kilometre allows.
  const segs=flowRoadSegments();
  const laneCapacity=segs.reduce((m,s)=>Math.min(m,s.cap_hr),Infinity);
  return {laneCapacity:Number.isFinite(laneCapacity)?laneCapacity:400,
    capSource:'official',
    equivHeadway:_flowSegMeta.followingM,
    method:_flowSegMeta.basis||'official speed limits ÷ following distance, one loaded lane',
    segSource:_flowSegMeta.source};
}
function flowSectionCapacity(cap,label){
  const row=flowRoadSegments().find(s=>s.label===label||s.id===label);
  return row&&row.cap_hr>0?row.cap_hr:cap.laneCapacity;
}
function evaluateFlowScenario(){
  const s=_flowSim;if(!s)return;const p=flowInputs(),cap=flowLaneCapacity(),laneCapacity=cap.laneCapacity;
  let demand=s.routes.reduce((n,r)=>n+r.dt*p.fleet*flowRouteTarget(r)/p.hours,0);
  // Plan host: non-plan (IWIP/Position) trucks share the same road. Their trips
  // come from the Step-1 "Other trips" input (measured last shift, editable).
  let otherPlanTph=0;
  if(_flowHost==='plan'&&typeof _planOtherTrips!=='undefined'&&_planOtherTrips>0){
    otherPlanTph=_planOtherTrips/p.hours;
    demand+=otherPlanTph;
  }
  const vc=demand/laneCapacity,congestion=vc>1?1/vc:1;
  s.otherPlanTph=otherPlanTph;
  s.capSource=cap.capSource;s.laneCapacity=laneCapacity;
  // Trip KPIs stay from DB / path-response. Motion uses GPS — do NOT inflate speeds
  // so kinematics invent the trip rate (old sharedOpenFactor behaviour).
  p.sharedOpenFactor=1;
  const motionVc=Math.max(0,vc-.7,Math.max(0,1-_flowSimRatio)*0.9);
  // PRODUCTION vs ROAD. Every route drives motion and takes road capacity, but
  // only OUR rows produce trips and tonnes for us. IWIP POS-transit rows are
  // real trucks with 0 WMT for us — planPredictTotals has filtered them since
  // 2026-08-21 and the engine payload marks them foreign, but this readout
  // summed them, so it quoted more trips than the page's own hero and priced
  // them at the TF payload. Road demand keeps every truck; production does not.
  let target=0,achieved=0,dbTrips=0,fleetTotal=0,foreignDt=0,foreignTrips=0;
  s.routes.forEach(r=>{
    const trucks=r.dt*p.fleet;
    r.targetTr=flowRouteTarget(r);
    buildFlowMotion(r,p,motionVc);
    r.achievedTr=r.targetTr;
    r.targetTrips=trucks*r.targetTr;
    r.achievedTrips=r.targetTrips;
    if(r.foreign&&_flowHost==='plan'){foreignDt+=trucks;foreignTrips+=r.targetTrips;return;}
    dbTrips+=r.dbTrips;target+=r.targetTrips;achieved+=r.achievedTrips;fleetTotal+=trucks;
  });
  s.foreignDt=foreignDt;s.foreignTrips=foreignTrips;
  s.dbTrips=dbTrips;s.targetTrips=target;s.achievedTrips=achieved;s.vc=vc;s.queue=Math.max(0,Math.ceil((demand-laneCapacity)*p.hours));s.inputs=p;
  const setTxt=(id,v)=>{const el=flowQ(id);if(el)el.textContent=v;};
  const setHtml=(id,v)=>{const el=flowQ(id);if(el)el.innerHTML=v;};
  const hzPlan=_flowHost==='plan'&&typeof planHorizonFactor==='function'?planHorizonFactor():1;
  const hzLab=_flowHost==='plan'&&typeof planHorizonLabel==='function'?planHorizonLabel():'shift';
  const hzUnit=hzPlan>1?'/ day (2 × 12h)':'/ 12h shift';
  setTxt('flow-attain',fmt(hzPlan*(_flowMode==='plan'?achieved:dbTrips)));
  // Plan readout kickers already say Predict/Simulate; keep unit lines short.
  // BUT: the corridor stick only carries TF–FENI-mapped routes. A holding plan
  // with off-corridor paths (e.g. BLB>BSE) has those DT silently excluded from
  // this trip figure — say so, or "73 trips from 134 DT" reads as a bug.
  let attainLabel='trips '+hzUnit;
  if(_flowHost==='plan'&&typeof _flowPlanDraft!=='undefined'){
    const draftKeys=Object.keys(_flowPlanDraft||{});
    const onStick=new Set(s.routes.map(r=>r.key));
    const excluded=draftKeys.filter(k=>!onStick.has(k));
    const exclDt=excluded.reduce((n,k)=>n+(Number.isFinite(_flowPlanDraft[k])?_flowPlanDraft[k]:0),0);
    // Name every fleet that is on the road but NOT in this trip figure, so a
    // smaller number than the fleet total never reads as a missing truck.
    const extra=[];
    if(foreignDt>0)extra.push(fmt(foreignDt,0)+' IWIP DT (road only, 0 WMT for us)');
    const tenTot=Object.keys(_flowTenantFlow||{}).length
      ?Object.values(_flowTenantFlow).reduce((a,b)=>a+(Number(b)||0),0):0;
    if(_flowHost==='plan'&&tenTot>0)extra.push('other tenants (flow only, own tempo)');
    if(excluded.length&&exclDt>0){
      extra.unshift(fmt(exclDt,0)+' DT off-corridor: '+excluded.map(k=>k.replace('>','→')).join(', '));
    }
    attainLabel='trips '+hzUnit+' · our '+fmt(fleetTotal,0)+' DT on corridor'
      +(extra.length?' — excludes '+extra.join('; '):'');
  }
  setTxt('flow-attain-label',_flowHost==='plan'
    ?attainLabel
    :(_flowMode==='plan'?'predict · trips / 12h shift':'dispatch · trips / shift'));
  setTxt('flow-vc',fmt(vc,2)+(otherPlanTph>0?' ⊕':''));
  const vcEl=flowQ('flow-vc');
  if(vcEl)vcEl.title=otherPlanTph>0
    ?('includes '+fmt(otherPlanTph*p.hours,0)+' non-plan (other) trips from Step 1 — remove them there to see plan-only V/C')
    :'plan trips only';
  setTxt('flow-queue',fmt(s.queue));
  setTxt('flow-onroad',fmt(fleetTotal,0));
  setTxt('flow-onroad-label','DT on corridor');
  const winMeta=(((_D&&_D.corridor)||{}).measuredWindow)||{};
  const gpsStruggle=!!winMeta.struggleSeasonExtract;
  // The V/C hint is written AFTER the hotspots exist (below): it names the
  // binding section, and s.hotspots is not built until then.
  // Production KPI: Cap what-if = predict WMT; Plan host after simulate = achievable tonnes.
  const _tf=(_D&&_D.kpi&&_D.kpi.tf)||0,_trips=(_flowMode==='plan'?achieved:dbTrips),_prod=_tf?_trips*_tf:0;
  const _prodBase=_tf?dbTrips*_tf:0,_dWMT=_prod-_prodBase;
  const simSum=(_flowHost==='plan'&&typeof _planLastSim!=='undefined'&&_planLastSim&&_planLastSim.summary)||null;
  const simAchv=simSum&&Number.isFinite(simSum.achievable_production_t)?simSum.achievable_production_t:null;
  if(_flowHost==='plan'&&simAchv!=null){
    setHtml('flow-prod',fmtM(simAchv*hzPlan));
    setTxt('flow-prod-label',simSum.planned_production_t!=null
      ?`${fmt(100*simAchv/Math.max(1,simSum.planned_production_t),0)}% of planned · ${hzLab}`
      :'achievable t / '+hzLab);
  }else{
    setHtml('flow-prod',_prod?(fmtM(_prod*hzPlan)+(_flowMode==='plan'&&Math.abs(_dWMT)>=1?` <span style="font-size:11px;color:${_dWMT>=0?'#22c55e':'#ef4444'}">${_dWMT>=0?'+':'−'}${fmtM(Math.abs(_dWMT)*hzPlan)}</span>`:'')):'—');
    setTxt('flow-prod-label',_flowHost==='plan'
      ?('WMT / '+hzLab+(_tf?' · TF '+fmt(_tf,1)+' t':''))
      :((_flowMode==='plan'?'predict · WMT / shift':'dispatch · WMT / shift')+(_tf?' · TF '+fmt(_tf,1)+' t':'')));
  }
  updateFlowModeBadge();
  // Sections are the OFFICIAL stick (congestion/segments.py via
  // /api/road_segments), not the legacy POS 10 split this file used to carry.
  // The old boundaries (POS 12–POS 10 27→17, POS 10–FENI 17→0) named a
  // bottleneck the crowding grid and Excel do not have, so the two panels
  // disagreed on WHICH section was worst as well as by how much.
  const sectionDefs=flowRoadSegments().map((s,i)=>(
    {id:i+1,segId:s.id,label:s.label,from:s.top_km,to:s.bottom_km}));
  s.hotspots=sectionDefs.map(z=>{
    const secCap=flowSectionCapacity(cap,z.label);
    const wbnTrips=s.routes.filter(r=>{
      const lo=Number.isFinite(r.corrLo)?r.corrLo:Math.min(r.fromKm,r.toKm);
      const hi=Number.isFinite(r.corrHi)?r.corrHi:Math.max(r.fromKm,r.toKm);
      const slo=Math.min(z.from,z.to),shi=Math.max(z.from,z.to);
      return hi>slo&&lo<shi;
    }).reduce((n,r)=>n+r.dt*p.fleet*flowRouteTarget(r),0),
      otherTrips=otherSectionTrips(z.label),trips=wbnTrips+otherTrips,
      // Tenants arrive as trucks/hr already — add to the HOURLY rate, not to
      // the shift trip count, because their clock is not ours.
      tenantHourly=_flowHost==='plan'?flowTenantSegmentFlow(z.segId):0,
      hourly=trips/p.hours+tenantHourly,
      ratio=hourly/secCap,status=ratio>=1?'High':ratio>=.7?'Watch':'Open',
      colour=ratio>=1?'#ef4444':ratio>=.7?'#f59e0b':'#22c55e';
    return {...z,trips,wbnTrips,otherTrips,tenantHourly,hourly,ratio,status,colour,secCap};
  });
  // Peak corridor V/C = worst section against its OFFICIAL capacity.
  let peakVc=s.hotspots.reduce((m,z)=>Math.max(m,z.ratio),0);
  // ONE OWNER on the Plan host (2026-08-25): quote the shared-flow engine's
  // flow ratio, not this replay's own arithmetic. The two disagreed on the
  // same plan (readout 424/hr vs engine 408/hr on KM15–coast) because the
  // replay prices IWIP transit rows at a fallback ~1 trip/DT while the
  // engine uses each leg's measured rate — the exact two-owners defect the
  // capacity card (J71) and the 0.85 availability already paid for. The
  // local hotspot model still colours the replay's own illustrations and is
  // the only voice on the Capability host, where no plan payload exists.
  let vcOwner=null;
  if(_flowHost==='plan'&&typeof _planSharedFlow!=='undefined'&&_planSharedFlow&&_planSharedFlow.ok){
    const secs=_planSharedFlow.sections||[];
    const wz=secs.length?secs.reduce((a,b)=>((b.ratio||0)>(a.ratio||0)?b:a),secs[0]):null;
    if(wz&&Number.isFinite(wz.ratio)){
      peakVc=wz.ratio;
      vcOwner={label:wz.section,hourly:wz.peak_flow_per_h,cap:wz.cap_flow_per_h,engine:true};
    }
  }
  s.vc=peakVc;setTxt('flow-vc',fmt(peakVc,2));
  {
    // Name the quantity. The crowding grid under this card ranks sections by
    // lane OCCUPANCY against the same geometry, and the two can name different
    // worst sections (measured 2026-08-25: flow peaks on KM15-coast, occupancy
    // on POS 12-KM15). Two real metrics, so each says which one it is.
    const vcHint=flowQ('flow-vc-hint');
    const wz=vcOwner||(s.hotspots.length?s.hotspots.reduce((a,b)=>b.ratio>a.ratio?b:a,s.hotspots[0]):null);
    if(vcHint)vcHint.textContent=wz
      ?`flow v/c · ${wz.label} ${fmt(wz.hourly,0)}/hr ÷ ${fmt(wz.secCap!=null?wz.secCap:wz.cap,0)}/hr official cap `
        +`(one loaded lane at ${fmt(cap.equivHeadway,0)} m)`
        +(wz.engine?' · shared-flow engine (same number as the crowding grid)':'')
      :`flow v/c · official caps, one loaded lane at ${fmt(cap.equivHeadway,0)} m`;
  }
  // The replay's own hotspot colours no longer paint anywhere: the segment
  // strip is owned by the plan's shared-flow v/c (same number as the crowding
  // grid and Excel, J79), and giving this illustration model a colour voice
  // beside it produced a strip that said RED over the text 'v/c 0.41'. The
  // hotspot RATIOS still feed the readouts below; only the paint is gone.
  s.hotspots.forEach(z=>{const el=flowQ('flow-risk-zone-'+z.id);if(el){el.setAttribute('fill',z.colour);el.setAttribute('opacity',z.ratio>=1?'.55':z.ratio>=.7?'.42':'.28');}});
  const hs=flowQ('flow-hotspots');
  if(hs)hs.innerHTML=s.hotspots.map(z=>`<span class="flow-hotspot"><i style="background:${z.colour}"></i><b>${escH(z.label)}</b> ${z.status} · V/C ${fmt(z.ratio,2)} <span class="muted">@ ${fmt(z.secCap,0)}/hr official${z.tenantHourly>0?` · incl. ${fmt(z.tenantHourly,0)}/hr other tenants`:''}</span></span>`).join('');
  const worst=s.hotspots.reduce((a,b)=>b.ratio>a.ratio?b:a,s.hotspots[0]),
    picked=_flowHost==='plan'
      ?((typeof planAllocFrozen==='function'&&planAllocFrozen())
        ?'ALLOCATED fleet illustration. ':'Holding plan illustration. ')
      :(_flowPointScenario?`3D scenario: ${_flowPointScenario.date} · ${_flowPointScenario.label}. `:''),
    // Say what these trips ARE. They are the path-response rate applied to the
    // fleet drawn here, which on a frozen plan is the ALLOCATED fleet — while
    // Step 2's Predicted headline prices the ORIGINAL plan on the segment
    // curves. Two different fleets on two different models, both legitimate,
    // so neither may sit unlabelled next to the other and be read as a check
    // on it. Production is owned by Step 2, never by this card.
    basis=_flowHost==='plan'
      ?'Trips are the path-response illustration rate on the fleet drawn here; '
       +'Step 2 Predicted (segment curves, original plan) and Achievable (simulate) own production. '
       +'Particles are illustration density from the Plan DT list. '
      :
      (s.shiftExplicit?'DB shift basis confirmed by NB_SHIFT. ':'Some source rows have no explicit NB_SHIFT; those values remain on their original basis. '),
    fleetGap=_flowMode==='plan'&&_flowHost!=='plan'&&Number.isFinite(_flowFleetAvailable)?_flowFleetAvailable-fleetTotal:null,
    fleetWarning=fleetGap!=null&&fleetGap<0?` Fleet is over-allocated by ${fmt(-fleetGap,0)} DT.`:'',
    bottleneck=worst.ratio>=1?`Highest congestion risk is ${worst.label} (V/C ${fmt(worst.ratio,2)}); demand exceeds the modelled lane capacity.`:worst.ratio>=.7?`Highest congestion risk is ${worst.label} (V/C ${fmt(worst.ratio,2)}); it is approaching saturation.`:`All mapped sections retain headway reserve; the highest load is ${worst.label} (V/C ${fmt(worst.ratio,2)}).`;
  const alert=flowQ('flow-alert');if(alert)alert.textContent=picked+basis+bottleneck+fleetWarning;
  const routesEl=flowQ('flow-routes');
  if(routesEl)routesEl.innerHTML=s.routes.map(r=>{const effChg=_flowMode==='plan'&&r.predEff&&Math.abs(r.targetTr-r.tr)>0.01,extrap=r.predEff&&r.dt>r.dtMax;
    const effTxt=effChg?`<b style="color:#fcd34d">${fmt(r.targetTr,2)} predicted Trips/DT</b> <span class="muted">(actual ${fmt(r.tr,2)}${extrap?', ⚠ beyond observed '+fmt(r.dtMax,0)+' DT':''})</span>`:`<b>${fmt(r.tr,2)} DB Trips/DT/shift</b>`;
    const rp=flowRainPct(r),rainTxt=(rp!==null&&rp<-3)?` · <span style="color:#60a5fa" title="Historically rain-sensitive: measured efficiency runs ~${fmt(-rp,0)}% lower on a wet (10 mm) day, fleet held constant. Daily rainfall is a rough proxy for road/mud state, so treat as context, not a precise predictor.">☔ rain-sensitive</span>`:'';
    const src=r.speedSource==='gps'?'GPS':(r.speedSource==='override'?'override':'est');
    const over=r.overLimitPct>1?` · <span style="color:#f87171" title="Share of route km where measured/override speed exceeds posted FMS limit">${fmt(r.overLimitPct,0)}% over posted limit</span>`:'';
    return `<div><span style="color:${r.col}">■</span> <b>${escH(r.label)}</b> · ${effTxt}${rainTxt} · ${_flowMode==='plan'?`${fmt(r.dbDt,0)} actual → <b>${fmt(r.dt,0)} scenario DT</b> · ${fmt(r.achievedTrips,0)} predicted trips/shift`:`${fmt(r.dbDt,1)} DB DT/shift · ${fmt(r.dbTrips)} DB trips/shift${r.shiftExplicit?'':' · shift count unavailable'}`} · ${r.particles} on-screen elements · ${src} loaded ${fmt(r.loadedSpeedRange[0],1)}–${fmt(r.loadedSpeedRange[1],1)} km/h · empty ${fmt(r.emptySpeedRange[0],1)}–${fmt(r.emptySpeedRange[1],1)} km/h${over}</div>`;}).join('');
  // Honesty caption under the map / stick.
  const win=winMeta;
  const note=flowQ('flow-note');
  if(note){
    const gpsN=flowMeasuredBands().length, limN=flowPostedLimits().length;
    const winTxt=(win.from&&win.to)?`${win.from} → ${win.to}`:'(no GPS window)';
    const peak=win.peakSeason||{};
    const peakTxt=(peak.from&&peak.to)?`${peak.from} → ${peak.to}`:'Jan–May peak';
    const secN=flowRoadSegments().length;
    // The capacity is GEOMETRY, not a GPS peak. Jul GPS still drives the
    // motion bands above; it no longer divides the V/C.
    const capTxt=`V/C = flow ÷ official capacity (${secN} sections · `
      +`${fmt(cap.equivHeadway,0)} m following, one loaded lane`
      +`${cap.segSource==='api'?'':' · offline fallback'})`
      +(gpsStruggle?` — GPS motion is the Jul struggle extract, not ${peakTxt}`:'');
    const eng=_flowHost==='plan'
      ?'Plan: trips = path-response illustration on the fleet drawn · tonnes = simulate when a run exists · particles = illustration only.'
      :'Capability: trips/WMT = dispatch (or path-response what-if) · particles = illustration.';
    note.textContent=`${eng} GPS motion ${gpsN} bands (${winTxt})${gpsStruggle?` · no segment GPS in ${peakTxt}`:''} · posted limits ${limN} · ${capTxt}.`;
  }
  if(_combined3D&&_flowHost!=='plan'){const rr=_combined3D.ranges,path=fleetTotal?_avg(s.routes,r=>r.dt*p.fleet):0,section=s.avgSection*p.fleet,tr=fleetTotal?achieved/fleetTotal:0,clamp=(v,r)=>Math.max(-1,Math.min(1,-1+2*(v-r.lo)/r.d)),selected=_flowPointScenario&&_combined3D.points[_flowPointScenario.pointIndex];_combined3D.scenario=selected?{...selected}: {path,section,tr,nx:clamp(path,rr.path),ny:clamp(section,rr.section),nz:clamp(tr,rr.tr)};renderCombined3D();}
  updateFlowSimulator();
}
function flowEstimateSpeeds(){
  // Optional override: back-solve corridor-average from trip rate (NOT GPS).
  if(!_flowSim)return;
  const p=flowInputs(),vals=[];
  _flowSim.routes.forEach(r=>{const cycle=p.hours/flowRouteTarget(r)-p.dwell/60,dist=Math.abs(r.fromKm-r.toKm);if(cycle>0&&dist>0)vals.push({v:dist*(1/.9+1/1.1)/cycle,w:r.dt});});
  if(!vals.length)return;
  const base=vals.reduce((s,x)=>s+x.v*x.w,0)/vals.reduce((s,x)=>s+x.w,0),clamp=v=>Math.max(5,Math.min(80,v));
  _flowSpeedOverride=true;_flowMotionMode='trip-implied';_flowSpeedsInitialised=true;
  flowUpdateMotionModeUi(); // reveal fields before writing values
  const ls=flowQ('flow-loaded-speed'),es=flowQ('flow-empty-speed');
  if(ls)ls.value=clamp(.9*base).toFixed(1);
  if(es)es.value=clamp(1.1*base).toFixed(1);
  flowScenarioChanged(true);
}
// Mode is DERIVED, never toggled: any route whose planned DT differs from its actual → simulated scenario.
function flowDeriveMode(){
  if(!_flowSim)return;
  if(_flowHost==='plan'){_flowMode='plan';return;}
  const changed=_flowSim.routes.some(r=>Number.isFinite(_flowPlanDraft[r.key])&&Math.round(_flowPlanDraft[r.key])!==Math.round(r.dbDt));
  _flowMode=changed?'plan':'replay';
}
function updateFlowModeBadge(){
  const el=flowQ('flow-mode-badge');if(!el)return;
  const dt=_flowSim?Math.round(_flowSim.routes.reduce((n,r)=>n+r.dt,0)):0,actual=_flowSim?Math.round(_flowSim.routes.reduce((n,r)=>n+r.dbDt,0)):0;
  if(_flowHost==='plan'){ el.className='flow-mode-badge plan'; el.textContent='◇ ILLUSTRATION · holding plan · '+fmt(dt,0)+' DT'; }
  else if(_flowMode==='plan'){ el.className='flow-mode-badge plan'; el.textContent='◆ WHAT-IF (illustration) · '+fmt(dt,0)+' DT (dispatch '+fmt(actual,0)+')'; }
  else { el.className='flow-mode-badge replay'; el.textContent='● HISTORICAL REPLAY · '+fmt(dt,0)+' DT'; }
}
function flowPlannerTotals(){
  const current=Math.round(_flowSim.routes.reduce((n,r)=>n+r.dbDt,0));
  if(!Number.isFinite(_flowFleetAvailable))_flowFleetAvailable=current;
  const scenario=_flowSim.routes.reduce((n,r)=>n+(_flowPlanDraft[r.key]??r.dbDt),0),balance=_flowFleetAvailable-scenario;
  return {current,scenario,balance,
    balanceClass:balance<0?'bad':balance===0?'':'warn',
    balanceText:balance<0?`Over-allocated by ${fmt(-balance,0)} DT`:balance>0?`${fmt(balance,0)} DT unallocated`:'Fleet fully allocated'};
}
/** Update balance / available field without rebuilding the panel (keeps <details> open + focus). */
function flowRefreshPlannerStats(){
  const box=flowQ('flow-planner');if(!box||!_flowSim)return;
  const t=flowPlannerTotals();
  const bal=box.querySelector('.flow-fleet-balance');
  if(bal){bal.className='flow-fleet-balance '+t.balanceClass;
    bal.innerHTML=`<b>Dispatch that day:</b> ${fmt(t.current,0)} DT · <b>What-if:</b> ${fmt(t.scenario,0)} DT · <b>${t.balanceText}</b>`;}
  const avail=box.querySelector('#flow-fleet-available');
  if(avail)avail.value=Math.round(_flowFleetAvailable);
  _flowSim.routes.forEach(r=>{
    const inp=box.querySelector(`input[data-flow-key="${CSS.escape(r.key)}"]`);
    if(inp&&document.activeElement!==inp&&Number.isFinite(_flowPlanDraft[r.key]))inp.value=Math.round(_flowPlanDraft[r.key]);
  });
}
function renderFlowPlanner(){
  const box=flowQ('flow-planner');
  if(!box||!_flowSim)return;
  // Plan-tab host: holding plan is the source of truth — no Capability fleet what-if.
  if(_flowHost==='plan'){box.style.display='none';box.innerHTML='';return;}
  box.style.display='block';
  _flowSim.routes.forEach(r=>{if(!Number.isFinite(_flowPlanDraft[r.key]))_flowPlanDraft[r.key]=Math.round(r.dbDt);});
  const t=flowPlannerTotals();
  // Preserve open/focus across rebuilds — full innerHTML was collapsing the panel on every edit.
  const prevDetails=box.querySelector('details.flow-whatif-secondary');
  const keepOpen=!prevDetails||prevDetails.open;
  const ae=document.activeElement;
  const focusKey=ae&&ae.getAttribute&&ae.getAttribute('data-flow-key');
  const focusId=ae&&ae.id;
  const focusSel=ae&&ae.selectionStart;
  box.innerHTML=`<details class="flow-whatif-secondary"${keepOpen?' open':''}>
    <summary>Optional what-if fleet edit <span class="muted">(illustration only — forward plans → Plan tab Step 2)</span></summary>
    <p class="muted" style="font-size:11px;margin:8px 0 6px">Set DT per route below — <b>Available fleet</b> is the sum of those boxes (starts at this day’s dispatch ${fmt(t.current,0)} DT). Shift outcomes / illustration follow that what-if total. Achievable tonnes → <b>Plan</b> tab Step 2.</p>
    <div class="flow-plan-top"><span>Fleet what-if</span><label class="flow-fleet-total">Available fleet (sum of routes) <input id="flow-fleet-available" type="number" min="0" step="1" value="${Math.round(_flowFleetAvailable)}" readonly title="Auto-updates from the route DT boxes below"> DT</label></div>
    <div class="flow-plan-grid">${_flowSim.routes.map(r=>`<div class="flow-plan-card"><b><span style="color:${r.col}">■</span> ${escH(r.label)}</b><div class="flow-plan-edit"><button type="button" onclick="flowPlanStep('${escH(r.key)}',-5)">−</button><input data-flow-key="${escH(r.key)}" type="number" min="0" step="1" value="${Math.round(_flowPlanDraft[r.key])}" onchange="flowPlanSet('${escH(r.key)}',this.value)" oninput="flowPlanLive('${escH(r.key)}',this.value)"><button type="button" onclick="flowPlanStep('${escH(r.key)}',5)">+</button><span>DT</span></div><div class="flow-plan-current">Dispatch: ${fmt(r.dbDt,0)} DT/shift · ${fmt(r.tr,2)} DB Trips/DT/shift</div></div>`).join('')}</div>
    <div class="flow-fleet-balance"><b>Dispatch that day:</b> ${fmt(t.current,0)} DT · <b>What-if fleet:</b> ${fmt(t.scenario,0)} DT</div>
    <div style="margin-top:8px;font-size:11px"><a onclick="flowPlanReset()" style="cursor:pointer;color:#7eb8f7">↺ Reset routes to dispatch</a></div>
    ${_flowOtherBlock()}
  </details>`;
  if(focusKey){const inp=box.querySelector(`input[data-flow-key="${CSS.escape(focusKey)}"]`);if(inp){inp.focus();if(Number.isFinite(focusSel))try{inp.setSelectionRange(focusSel,focusSel);}catch(e){}}}
  else if(focusId){const inp=box.querySelector('#'+CSS.escape(focusId));if(inp)inp.focus();}
}
function _flowOtherBlock(){
  const has=_otherCtx&&_otherCtx.paths&&_otherCtx.paths.length;
  if(!has)return `<div style="margin-top:10px;padding:9px 11px;border:1px solid #475569;border-radius:8px;background:rgba(100,116,139,.08)"><b><span style="color:#94a3b8">■</span> Other road users (IWIP / Position)</b> <span class="muted" style="font-size:10.5px">— no weigh data for this shift (pre-Dec 2025)</span></div>`;
  const cards=_otherCtx.paths.map((p,i)=>{const draft=Number.isFinite(_otherDraft[p.label])?_otherDraft[p.label]:p.trucks,mult=p.trucks?draft/p.trucks:1,feni=Math.min(p.oKm,p.dKm)<17;
    return `<div class="flow-plan-card"><b><span style="color:#94a3b8">■</span> ${escH(p.label)}${feni?' <span class="muted" style="font-weight:400">· shares FENI road</span>':''}</b><div class="flow-plan-edit"><button onclick="flowOtherStep(${i},-10)">−</button><input type="number" min="0" step="1" value="${Math.round(draft)}" onchange="flowOtherSet(${i},this.value)"><button onclick="flowOtherStep(${i},10)">+</button><span>trucks</span></div><div class="flow-plan-current">Actual: ${fmt(p.trucks)} trucks · ${fmt(p.trips*mult,0)} trips${mult!==1?` · ×${fmt(mult,2)}`:''}</div></div>`;}).join('');
  const feniEff=OTHER_TRAFFIC_COEF*otherFeniDelta();
  return `<div style="margin-top:10px;padding:9px 11px;border:1px solid #475569;border-radius:8px;background:rgba(100,116,139,.08)">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><b><span style="color:#94a3b8">■</span> Other road users (IWIP / Position)</b><span class="muted" style="font-size:10.5px">adds congestion · no WBN WMT / Trips</span><label class="muted" style="margin-left:auto;font-size:10.5px"><input type="checkbox" ${_otherInModel?'checked':''} onchange="flowOtherToggle(this.checked)" style="vertical-align:-1px"> count in section DT &amp; congestion</label></div>
    <div class="flow-plan-grid" style="margin-top:8px">${cards}</div>
    <div class="flow-plan-current" style="margin-top:5px">${fmt(_otherCtx.fleet)} trucks total on ${escH(_otherCtx.date)} · split by path above</div>
    ${_otherInModel&&Math.abs(feniEff)>=0.005?`<div style="font-size:10.5px;margin-top:4px;color:#fcd34d">→ Predicted effect on FENI-bound WBN routes: <b>${(feniEff>=0?'+':'')+fmt(feniEff,2)} trips/DT</b> <span class="muted">(measured, POS→FENI only)</span></div>`:''}
    ${!_otherInModel?`<div class="muted" style="font-size:10px;margin-top:4px">Excluded from the model — display only.</div>`:''}</div>`;
}
function flowOtherStep(i,d){const p=_otherCtx&&_otherCtx.paths[i];if(!p)return;_otherDraft[p.label]=Math.max(0,(Number.isFinite(_otherDraft[p.label])?_otherDraft[p.label]:p.trucks)+d);renderFlowPlanner();evaluateFlowScenario();}
function flowOtherSet(i,v){const p=_otherCtx&&_otherCtx.paths[i];if(!p)return;_otherDraft[p.label]=Math.max(0,parseFloat(v)||0);renderFlowPlanner();evaluateFlowScenario();}
function flowOtherToggle(on){_otherInModel=!!on;renderFlowPlanner();evaluateFlowScenario();if(_flowSim)updateFlowSimulator();}
function flowFleetAvailableLive(value){_flowFleetAvailable=Math.max(0,Math.round(+value||0));flowRefreshPlannerStats();}
function flowFleetAvailableSet(value){_flowFleetAvailable=Math.max(0,Math.round(+value||0));flowRefreshPlannerStats();}
function flowWhatIfTotal(){
  if(!_flowSim)return 0;
  return Math.round(_flowSim.routes.reduce((n,r)=>n+(_flowPlanDraft[r.key]??r.dbDt),0));
}
/** Available budget always follows the sum of route what-if DT boxes. */
function flowSyncAvailableToWhatIf(){_flowFleetAvailable=flowWhatIfTotal();}
function flowFleetMatchWhatIf(){flowSyncAvailableToWhatIf();flowRefreshPlannerStats();}
function flowPlanLive(key,value){
  // Ignore blank mid-keystroke so typing "40" does not briefly force 0.
  if(value===''||value==null)return;
  const n=Math.round(+value);if(!Number.isFinite(n))return;
  _flowPlanDraft[key]=Math.max(0,n);flowApplyPlanLight();
}
function flowPlanSet(key,value){
  _flowPlanDraft[key]=Math.max(0,Math.round(+value||0));flowApplyPlanLight(true);
}
function flowPlanStep(key,delta){_flowPlanDraft[key]=Math.max(0,Math.round((_flowPlanDraft[key]||0)+delta));flowApplyPlanLight(true);}
function flowPlanReset(){if(!_flowSim)return;_flowSim.routes.forEach(r=>_flowPlanDraft[r.key]=Math.round(r.dbDt));flowSyncAvailableToWhatIf();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);if(_combined3D)renderCombinedAnalysis(_combined3D.points);}
function runFlowPlan(){if(!_flowSource)return;stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);flowToggle();}
function flowScenarioChanged(speedTouched){
  if(!_flowSim||!_flowSource)return;
  if(speedTouched){_flowSpeedsInitialised=true;_flowSpeedOverride=true;if(_flowMotionMode==='gps')_flowMotionMode='manual';}
  stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);
  flowUpdateMotionModeUi();
}
let _flowPlanRebuildTimer=null;
// Editing a fleet input updates KPIs live; map dots rebuild on commit (blur / ±) so totals match.
function flowApplyPlanLight(rebuildDots){
  if(!_flowSim){renderFlowPlanner();return;}
  _flowSim.routes.forEach(r=>{if(Number.isFinite(_flowPlanDraft[r.key]))r.dt=_flowPlanDraft[r.key];});
  flowDeriveMode();
  // Budget = selected what-if DT (not frozen at the historical dispatch day total).
  flowSyncAvailableToWhatIf();
  flowRefreshPlannerStats();
  evaluateFlowScenario();
  if(_combined3D&&_flowHost!=='plan')renderCombinedAnalysis(_combined3D.points);
  if(rebuildDots&&_flowSource){
    clearTimeout(_flowPlanRebuildTimer);
    _flowPlanRebuildTimer=setTimeout(()=>{
      if(!_flowSource)return;
      const hour=_flowSim?_flowSim.hour:0,running=_flowSim&&_flowSim.running;
      stopFlowSimulator();
      renderFlowSimulator(_flowSource.P,_flowSource.colours,true);
      if(_flowSim){_flowSim.hour=hour;updateFlowSimulator();if(running)flowToggle();}
    },180);
  }
}
// Bring map + schematic stick into view so Run is watched on both visuals.
// Plan: scroll the GPS corridor block (map + chainage stick). Paint must not
// wait on IntersectionObserver — smooth-scroll is async and the observer
// otherwise reports off-screen for the first frames (blank cartoon).
function flowScrollVisualsIntoView(){
  const stage=_flowHost==='plan'
    ?(document.getElementById('plan-s2-corridor')||flowQ('c3-flow-visuals'))
    :(flowQ('c3-flow-visuals')||flowQ('c3-flow-map'));
  if(!stage||typeof stage.scrollIntoView!=='function')return;
  flowHoldStageVisible(1600);
  try{stage.scrollIntoView({behavior:'smooth',block:'nearest',inline:'nearest'});}
  catch(_){stage.scrollIntoView(true);}
}
// Single run/pause control: a fresh Run always re-renders the road for the current fleet, then plays.
function flowRunOrPause(){
  const s=_flowSim;
  if(s&&s.running){stopFlowSimulator();return;}
  flowScrollVisualsIntoView();
  // Plan host: reveal C · road illustration on first ▶ Run after a scenario.
  if(_flowHost==='plan'){
    // Guard: only animate the HOLDING PLAN. If the seed never ran (e.g. the
    // simulate fetch failed), _flowSource still holds Capability's historical
    // rows — re-seed from the plan draft instead of replaying those.
    if(!(_flowPointScenario&&_flowPointScenario.date==='plan')){
      if(!(typeof planSeedFlowAnimation==='function'&&planSeedFlowAnimation()))return;
    }
    if(typeof planOnCorridorRun==='function'){
      try{planOnCorridorRun();}catch(_){}
    }
  }
  runFlowPlan();
}
function renderFlowSimulator(P,colours){
  flowObserveStage();
  const selectedDate=(_flowPointScenario&&_flowPointScenario.date)||'';
  // Plan illustration: still snap weighbridges onto the stick (fixture/live positions).
  if(selectedDate==='plan'){if(!_wbPos)loadWbPositions(0,'');}
  else if(selectedDate&&selectedDate!==_wbPosDate)loadWbPositions(0,selectedDate);
  if(selectedDate&&selectedDate!=='plan')loadShiftContext(selectedDate);
  stopFlowSimulator();_flowSource={P,colours};const svg=flowQ('c3-flow-svg'),fallback={source:'WBN_DATABASE.dbo.HAUL_ROAD_STA',basis:'road chainage',lengthKm:67.8,nodes:[{id:'tf',label:'TF',km:67.8,aliases:['TF','TOFU']},{id:'kr',label:'KR',km:39,aliases:['KR','KRENE']},{id:'pos12',label:'POS 12',km:27,aliases:['POS 12','POS12']},{id:'pos10',label:'POS 10',km:17,aliases:['POS 10','POS10']},{id:'feni15',label:'FENI 15',km:15,aliases:['FENI KM15','FENI 15']},{id:'pos6',label:'POS 6',km:12,aliases:['POS 6','POS6','POS 06']},{id:'feni0',label:'FENI 0',km:0,aliases:['FENI KM0','FENI 0']} ]},corridor=(_D&&_D.corridor)||fallback,by={},scenarioP=_flowPointScenario?P.filter(p=>p.date===_flowPointScenario.date):P;
  if(!svg)return;
  scenarioP.forEach(p=>{const g=by[p.pathKey]||(by[p.pathKey]={key:p.pathKey,label:p.label,dt:0,tr:0,trips:0,n:0,shiftExplicit:true,foreign:!!p.foreign});g.dt+=p.path;g.tr+=Number.isFinite(p.shiftTr)?p.shiftTr:p.tr;g.trips+=Number.isFinite(p.shiftTrips)?p.shiftTrips:p.trips;g.shiftExplicit=g.shiftExplicit&&p.shiftExplicit!==false;if(!p.foreign)g.foreign=false;g.n++;});
  const routeParts=k=>{const i=k.indexOf('>');return i<0?['','']:[k.slice(0,i),k.slice(i+1)];};
  let routes=Object.values(by).map(g=>{
    const [o,d]=routeParts(g.key),ol=flowLocate(o),dl=flowLocate(d),dbDt=g.dt/g.n,scenarioDt=Number.isFinite(_flowPlanDraft[g.key])?_flowPlanDraft[g.key]:dbDt;
    const stickKmOf=loc=>!loc?null:loc.kind==='spur'?(loc.parent?loc.parent.joinKm:loc.joinKm):loc.km;
    const fromKm=stickKmOf(ol),toKm=stickKmOf(dl);
    return {...g,origin:o,dest:d,originLoc:ol,destLoc:dl,fromKm,toKm,dbDt,dt:scenarioDt,tr:g.tr/g.n,dbTrips:g.trips/g.n,col:colours[g.key]};
  }).filter(r=>r.originLoc&&r.destLoc&&Number.isFinite(r.fromKm)&&Number.isFinite(r.toKm)).sort((a,b)=>b.dt-a.dt);
  if(!routes.length){svg.innerHTML='<text x="220" y="270" text-anchor="middle" fill="#94a3b8" font-size="12">Selected routes are not mapped to the haul-road survey (TF–FENI + BLB/HUAFEI/CBB spurs).</text>';_flowSim=null;return;}
  // Plan: one particle per planned DT so the GPS map and the chainage stick
  // show the same trucks. Capability keeps the trace-element budget (illustration).
  const fp=flowInputs(),fleet=fp.fleet,sumDt=routes.reduce((s,r)=>s+r.dt,0),allocationBase=Math.max(1,sumDt);
  if(_flowHost==='plan'){
    routes.forEach(r=>{
      const n=Math.max(1, Math.round(r.dt*fleet));
      r.particles=n;
      r.particleWeight=(r.dt*fleet)/n;
      r.departures=Array(n).fill(0);
      r.startTimes=Array(n).fill(0);
    });
  }else{
    const _elBudget=fp.elementsTouched?fp.elements:Math.round(sumDt),
      totalElements=Math.max(routes.length,Math.min(1400,_elBudget||500)),remaining=totalElements-routes.length;
    routes=routes.map(r=>{const raw=remaining*r.dt/allocationBase,n=Math.floor(raw);return {...r,particles:1+n,_fraction:raw-n};});
    for(let leftN=totalElements-routes.reduce((s,r)=>s+r.particles,0);leftN>0;leftN--)routes.slice().sort((a,b)=>b._fraction-a._fraction)[(leftN-1)%routes.length].particles++;
    routes.forEach(r=>{r.particleWeight=r.dt*fleet/r.particles;r.departures=Array(r.particles).fill(0);r.startTimes=Array(r.particles).fill(0);});
  }
  // One global release sequence prevents simultaneous source pulses. Paths are round-robin, but each
  // element is released at the source belonging to its own path. Weighted elements are spread over
  // the full 12-hour shift and never emitted as a batch.
  let releaseOrder=[],maxParticles=Math.max(...routes.map(r=>r.particles));for(let j=0;j<maxParticles;j++)routes.forEach(r=>{if(j<r.particles)releaseOrder.push({r,j});});
  if(_flowHost==='plan'){
    // PLAN HOST: THE FLEET IS ALREADY AT WORK AT 07:00. The Capability
    // release below drips trucks out of the pit one at a time at a 90 s
    // headway; with 1,700 planned DT the last one left at hour 42 of a
    // 12-hour shift, so at 18:00 only 176 loaded trucks were on the road
    // and 14 empties between KR and TF - a trickle that read as a game,
    // not the plan (owner, 2026-09-03). A shift does not start with 1,280
    // parked trucks: the night shift hands over on the road. Each truck
    // starts at a phase of ITS OWN cycle - stratified (n trucks at n even
    // phases, shuffled) and seeded per route, so the picture is stable
    // and the cycle is covered uniformly. Nothing here invents a trip.
    routes.forEach(r=>{
      let seed=0;for(const ch of r.key)seed=(seed*31+ch.charCodeAt(0))>>>0;
      const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
      const n=r.particles,ph=Array.from({length:n},(_,k)=>(k+rnd())/n);
      for(let k=n-1;k>0;k--){const m=Math.floor(rnd()*(k+1));[ph[k],ph[m]]=[ph[m],ph[k]];}
      for(let j=0;j<n;j++){r.departures[j]=0;r.startTimes[j]=ph[j];}
    });
  }else{
    let releaseSeconds=0;const shiftStep=FLOW_SHIFT_HOURS*3600/releaseOrder.length;releaseOrder.forEach(x=>{x.r.departures[x.j]=releaseSeconds/3600;releaseSeconds+=Math.max(shiftStep,Math.max(fp.headway,fp.stagger*60)*x.r.particleWeight);});
  }
  const avgSection=_avg(scenarioP,p=>p.section),groups=c3LoadGroups(P),band=(groups.find(g=>avgSection>=g.min&&avgSection<=g.max)||groups.reduce((a,b)=>Math.abs(b.section-avgSection)<Math.abs(a.section-avgSection)?b:a,groups[0])).label,pipeCol=band==='Congested'?'#ef4444':'#22c55e',left=30,right=975,length=corridor.lengthKm||Math.max(...corridor.nodes.map(n=>n.km)),X=km=>left+(length-km)/length*(right-left);
  const usedSpurs=[];
  routes.forEach(r=>{
    r.loop=flowBuildRouteLoop(r,X);
    const xs=r.loop.filter(p=>!p.spur).map(p=>p.x);
    const loaded=flowVerticesFromLegs(flowLoadedLegs(r),X,180);
    r.sourceX=r.loop[0].x;r.destX=(loaded.length?loaded[loaded.length-1]:r.loop[r.loop.length-1]).x;
    r.corrX1=xs.length?Math.min(...xs):Math.min(r.sourceX,r.destX);
    r.corrX2=xs.length?Math.max(...xs):Math.max(r.sourceX,r.destX);
    r.corrLo=Math.min(r.fromKm,r.toKm);r.corrHi=Math.max(r.fromKm,r.toKm);
    [r.originLoc,r.destLoc].forEach(loc=>{
      if(!loc||loc.kind!=='spur')return;
      // A nested spur's parent road is part of the drive — draw it too.
      if(!usedSpurs.some(s=>s.road===loc.road))usedSpurs.push(loc);
      if(loc.parent&&!usedSpurs.some(s=>s.road===loc.parent.road))usedSpurs.push(loc.parent);
    });
  });
  const hangingSpurs=usedSpurs.filter(s=>!s.parent&&!flowIsStickStub(s));
  const stubSpurs=usedSpurs.filter(flowIsStickStub);
  const spurH=hangingSpurs.length?Math.max(...hangingSpurs.map(s=>flowSpurH(s))):0;
  const famOf=o=>o.startsWith('TF')||o.startsWith('TOFU')?0:o.startsWith('KR')?1:o.startsWith('BLB')?2:3;
  let baseH=300;
  if(_otherCtx&&_otherCtx.paths&&_otherCtx.paths.length&&_flowHost!=='plan')baseH=Math.max(baseH,330+14*Math.min(6,_otherCtx.paths.length)+8);
  // Canvas ends 44 px under the deepest branch bulb (bulb + two caption
  // lines), not a fixed 48 under the road: the old value left a dead band.
  const viewH=hangingSpurs.length?Math.max(baseH,Math.round(226+spurH+15+44)):baseH;
  // Legend is HTML above the SVG. Crop the unused ledger band on Plan so the
  // road fills the restored 560 px panel (crop + tiny CSS was the empty look).
  // Both hosts crop the old in-SVG legend band (the legend is HTML above
  // the SVG on both since 2026-08-25). Capability kept crop 0 and showed a
  // ~140 px dead band between the caption and the node labels.
  const cropTop=80;
  const capY=cropTop+16;
  svg.setAttribute('viewBox','0 '+cropTop+' 1000 '+(viewH-cropTop));
  let out='<title>07:00 to 19:00 finite-truck road simulation</title><desc>Every particle represents one average selected DT for a 12-hour shift. Loaded and empty trucks share one no-overtaking left-hand-traffic road. BLB (17.4 km) and HUAFEI (0.9 km) hang off the stick as branches at km 2.5 and km 5.5 (survey, J80).</desc>';
  // km ruler: skip any tick whose label would sit under a node's own km
  // caption (POS 10 @17, POS 6 @12 and the km 10/km 20 ticks collided) or
  // inside a hanging branch's road.
  {
    const nodeKm=(corridor.nodes||[]).map(n=>n.km);
    const spurKm=usedSpurs.filter(s=>!s.parent).map(s=>s.joinKm);
    for(let km=0;km<=60;km+=10){
      const x=X(km);
      const nearNode=nodeKm.some(k=>Math.abs(X(k)-x)<34);
      const nearSpur=spurKm.some(k=>Math.abs(X(k)-x)<22);
      out+=`<line x1="${x.toFixed(1)}" y1="236" x2="${x.toFixed(1)}" y2="${nearNode||nearSpur?242:248}" stroke="#334155"/>`;
      if(!nearNode&&!nearSpur)out+=`<text x="${x.toFixed(1)}" y="260" fill="#64748b" font-size="9" text-anchor="middle">km ${km}</text>`;
    }
  }
  const win=((corridor.measuredWindow)||{});
  const winLbl=(win.from&&win.to)?` · GPS ${win.from}→${win.to}`:'';
  // Lane captions: LOADED at the TF end of the loaded lane, EMPTY RETURN at
  // the TF end of the empty lane too — the FENI end is where the branch
  // junctions (BLB 2.5, HUAFEI 5.5) and the smelter node sit, so a caption
  // there overprinted the junction rings.
  out+=`<text x="20" y="${capY}" fill="#64748b" font-size="9">DB road chainage · ${escH(corridor.source||'haul-road source')}${escH(winLbl)}${usedSpurs.length?' · '+usedSpurs.map(s=>s.parent?s.label+' on '+s.parent.label+' road':s.label+' @'+fmt(s.joinKm,1)+' km').join(', '):''}</text><rect x="${left}" y="164" width="${right-left}" height="62" rx="14" fill="#17263e"/><rect x="${left}" y="172" width="${right-left}" height="46" rx="9" fill="#334155"/><line x1="${left}" y1="195" x2="${right}" y2="195" stroke="#94a3b8" stroke-width="1" stroke-dasharray="8 8" opacity=".45"/><text x="${left+14}" y="180" fill="#94a3b8" font-size="7.5" font-weight="700" letter-spacing=".1em" opacity=".9">LOADED →</text><text x="${left+14}" y="216" fill="#94a3b8" font-size="7.5" font-weight="700" letter-spacing=".1em" opacity=".9">← EMPTY</text>`;
  // ── S1–S4 segment blocks, tinted by the plan's own v/c (owner redesign,
  // 2026-08-25: "no segment demarcation ... the user must see which segment
  // is the bottleneck"). Colour source is _planSharedFlow — the SAME payload
  // the Road-crowding grid and the Excel corridor read (J79) — so this stick
  // can never name a different bottleneck than the grid. No payload (e.g. the
  // Capability tab before a plan run) → neutral boundaries only, no invented
  // colour. Thresholds mirror cbTone/crowdTone: .6 / .85 / 1.0.
  let stickAlert=null;
  {
    const SEGS=[{id:'S1',lab:'TF–KR',hi:67.8,lo:39,sec:'TF–KR'},
                {id:'S2',lab:'KR–POS 12',hi:39,lo:27,sec:'KR–POS 12'},
                {id:'S3',lab:'POS 12–KM15',hi:27,lo:15,sec:'POS 12–KM15'},
                {id:'S4',lab:'KM15–coast',hi:15,lo:0,sec:'KM15–coast'}];
    const sf=(typeof _planSharedFlow!=='undefined'&&_planSharedFlow&&_planSharedFlow.ok)?_planSharedFlow:null;
    const bySec={};(sf&&sf.sections||[]).forEach(s=>{bySec[s.section]=s;});
    let worst=null,worstOcc=null;
    SEGS.forEach(sg=>{
      const x1=X(sg.hi),x2=X(sg.lo);
      const sec=bySec[sg.sec];
      const vc=sec?sec.ratio:null;
      const stripFill=vc==null?'rgba(51,65,85,.55)':vc>=1?'rgba(220,38,38,.5)':vc>=.85?'rgba(239,68,68,.38)':vc>=.6?'rgba(249,115,22,.32)':'rgba(34,197,94,.22)';
      out+=`<rect x="${x1.toFixed(1)}" y="146" width="${(x2-x1).toFixed(1)}" height="17" rx="3" fill="${stripFill}" stroke="#0b1220" stroke-width="1"><title>${escH(sg.id+' · '+sg.lab)}${vc!=null?' · flow v/c '+vc.toFixed(2):''}</title></rect>`;
      const mid=(x1+x2)/2;
      const ink=vc==null?'#cbd5e1':vc>=.85?'#fecaca':vc>=.6?'#fed7aa':'#bbf7d0';
      const wide=(x2-x1)>110;
      const txt=wide?`${sg.id}  ${sg.lab}${vc!=null?'  ·  '+vc.toFixed(2):''}`:`${sg.id}${vc!=null?' '+vc.toFixed(2):''}`;
      out+=`<text x="${mid.toFixed(1)}" y="158" fill="${ink}" font-size="10" font-weight="700" letter-spacing=".05em" text-anchor="middle">${escH(txt)}</text>`;
      out+=`<line x1="${x2.toFixed(1)}" y1="146" x2="${x2.toFixed(1)}" y2="230" stroke="#64748b" stroke-width="1" opacity=".55"/>`;
      if(sec&&(!worst||(sec.ratio||0)>(worst.ratio||0)))worst={...sec,segId:sg.id};
      if(sec&&(!worstOcc||(sec.ratio_presence_lane||0)>(worstOcc.ratio_presence_lane||0)))
        worstOcc={...sec,segId:sg.id};
    });
    if(worst&&worst.ratio>=.6){
      const lab=worst.ratio>=1?'OVER CAPACITY':worst.ratio>=.85?'CONGESTED':'BUSIEST';
      stickAlert=worst.segId+' · '+lab+' · v/c '+worst.ratio.toFixed(2);
      // One typographic row for the verdict: 11px bold, right-aligned, no
      // dash-dressed sentence. Colour carries the severity; the strip below
      // shows which segment.
      const aCol=worst.ratio>=.85?'#fca5a5':'#fdba74';
      out+=`<text x="${right}" y="${capY}" fill="${aCol}" font-size="11" font-weight="800" letter-spacing=".02em" text-anchor="end">${escH(worst.segId)} ${escH(worst.section)} · ${lab} · v/c ${worst.ratio.toFixed(2)}</text>`;
      if(worstOcc&&worstOcc.section!==worst.section&&worstOcc.ratio_presence_lane>=.6){
        out+=`<text x="${right}" y="${capY+12}" fill="#94a3b8" font-size="8.5" font-weight="600" text-anchor="end">by occupancy: ${escH(worstOcc.segId)} ${escH(worstOcc.section)} · ${(100*worstOcc.ratio_presence_lane).toFixed(0)}% of one loaded lane</text>`;
      }
    }
    if(sf){
      out+=`<text x="${left}" y="141" fill="#64748b" font-size="8" font-weight="600" letter-spacing=".04em">SEGMENT v/c · busiest hour ÷ lane capacity</text>`;
    }
  }
  // Spurs are two-lane roads in the stick's own language: dark shoulder, asphalt,
  // dashed centreline. Roads first, nodes/labels last, so one spur's road never
  // paints over another's label.
  const spurCol=loc=>loc.road==='BLB'?'#a78bfa':loc.road==='HFC'?'#f472b6':'#2dd4bf';
  const spurJoinY=(parent,atKm)=>{
    const pH=flowSpurH(parent),pJoin=flowSpurJoinKm(parent),pPit=parent.endKm;
    const t=(pPit===pJoin)?0:Math.abs(atKm-pJoin)/Math.max(1e-6,Math.abs(pPit-pJoin));
    return 226+pH*t;
  };
  hangingSpurs.forEach(loc=>{
    // Road width follows the branch: the 17 km BLB haul road stays a full
    // two-lane 26 px; a sub-4 km plant spur (HUAFEI) is 18 px so it and BLB
    // (42 px apart on the stick) never touch.
    const x=X(loc.joinKm),h=flowSpurH(loc),y0=226,y2=226+h,rw=(loc.lengthKm||8)<4?18:26;
    const col=spurCol(loc);
    // Two-lane vertical road. The 8 px tuck under the stick (y0-8) merges the junction.
    out+=`<rect x="${(x-rw/2).toFixed(1)}" y="${y0-8}" width="${rw}" height="${h+8}" rx="${rw/2}" fill="#17263e"/>`;
    out+=`<rect x="${(x-rw/2+4).toFixed(1)}" y="${y0}" width="${rw-8}" height="${h}" rx="${(rw-8)/2}" fill="#334155"/>`;
    out+=`<line x1="${x.toFixed(1)}" y1="${y0+6}" x2="${x.toFixed(1)}" y2="${y2-4}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="6 7" opacity=".4"/>`;
    out+=`<line x1="${(x-rw/2+1).toFixed(1)}" y1="${y0}" x2="${(x-rw/2+1).toFixed(1)}" y2="${y2}" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<line x1="${(x+rw/2-1).toFixed(1)}" y1="${y0}" x2="${(x+rw/2-1).toFixed(1)}" y2="${y2}" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<circle cx="${x.toFixed(1)}" cy="214" r="3.4" fill="#0b1220" stroke="${col}" stroke-width="1.4"><title>${escH(loc.label)} spur joins the TF–FENI stick at ${fmt(loc.joinKm,1)} km</title></circle>`;
  });
  stubSpurs.forEach(loc=>{
    // Short dock on the stick (HUAFEI 0.9 km at km 5.5). Same two lanes as the
    // main road — not a second hanging extra beside BLB.
    const x=X(loc.joinKm),len=flowStubLen(loc),x0=x-len,col=spurCol(loc);
    out+=`<rect x="${(x0-4).toFixed(1)}" y="164" width="${(len+8).toFixed(1)}" height="62" rx="14" fill="#17263e"/>`;
    out+=`<rect x="${x0.toFixed(1)}" y="172" width="${len.toFixed(1)}" height="46" rx="9" fill="#334155"/>`;
    out+=`<line x1="${(x0+8).toFixed(1)}" y1="195" x2="${(x-6).toFixed(1)}" y2="195" stroke="#94a3b8" stroke-width="1" stroke-dasharray="8 8" opacity=".45"/>`;
    out+=`<line x1="${x0.toFixed(1)}" y1="172" x2="${x.toFixed(1)}" y2="172" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<line x1="${x0.toFixed(1)}" y1="218" x2="${x.toFixed(1)}" y2="218" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<circle cx="${x.toFixed(1)}" cy="214" r="3.4" fill="#0b1220" stroke="${col}" stroke-width="1.4"><title>${escH(loc.label)} dock on the TF–FENI stick at ${fmt(loc.joinKm,1)} km · ${fmt(loc.lengthKm,1)} km</title></circle>`;
  });
  usedSpurs.filter(l=>l.parent).forEach(loc=>{
    // Nested spur: horizontal two-lane branch off the parent's road at the
    // junction height, running west (HUAFEI lies west of the BLB road).
    const p=loc.parent,px=X(p.joinKm),yJ=spurJoinY(p,loc.parentAtKm),len=Math.max(40,(loc.lengthKm||1)*44),x1=px-4.5,x0=x1-len,col=spurCol(loc);
    out+=`<rect x="${(x0-2).toFixed(1)}" y="${(yJ-13).toFixed(1)}" width="${(px-x0+4).toFixed(1)}" height="26" rx="12" fill="#17263e"/>`;
    out+=`<rect x="${(x0+2).toFixed(1)}" y="${(yJ-9).toFixed(1)}" width="${(px-x0-2).toFixed(1)}" height="18" rx="8" fill="#334155"/>`;
    out+=`<line x1="${(x0+8).toFixed(1)}" y1="${yJ.toFixed(1)}" x2="${(px-8).toFixed(1)}" y2="${yJ.toFixed(1)}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="6 7" opacity=".4"/>`;
    out+=`<line x1="${x0.toFixed(1)}" y1="${(yJ-12).toFixed(1)}" x2="${px.toFixed(1)}" y2="${(yJ-12).toFixed(1)}" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<line x1="${x0.toFixed(1)}" y1="${(yJ+12).toFixed(1)}" x2="${px.toFixed(1)}" y2="${(yJ+12).toFixed(1)}" stroke="${col}" stroke-width="1.4" opacity=".55"/>`;
    out+=`<circle cx="${x1.toFixed(1)}" cy="${yJ.toFixed(1)}" r="3.2" fill="#0b1220" stroke="${col}" stroke-width="1.3"><title>${escH(loc.label)} leaves the ${escH(p.label)} road at ${fmt(loc.parentAtKm,1)} km</title></circle>`;
  });
  usedSpurs.forEach(loc=>{
    const col=spurCol(loc);
    if(loc.parent){
      const p=loc.parent,px=X(p.joinKm),yJ=spurJoinY(p,loc.parentAtKm),len=Math.max(40,(loc.lengthKm||1)*44),x0=px-4.5-len;
      out+=`<circle cx="${x0.toFixed(1)}" cy="${yJ.toFixed(1)}" r="11" fill="#17263e" stroke="${col}" stroke-width="1.6"/>`;
      out+=`<circle cx="${x0.toFixed(1)}" cy="${yJ.toFixed(1)}" r="6.5" fill="#334155"/>`;
      out+=`<circle cx="${x0.toFixed(1)}" cy="${yJ.toFixed(1)}" r="2.2" fill="${col}"/>`;
      out+=`<text x="${(x0-4).toFixed(1)}" y="${(yJ+24).toFixed(1)}" fill="#e2e8f0" font-size="10" font-weight="700" text-anchor="middle">${escH(loc.label)}</text>`;
      out+=`<text x="${(x0-4).toFixed(1)}" y="${(yJ+35).toFixed(1)}" fill="#94a3b8" font-size="8" text-anchor="middle">${fmt(loc.lengthKm,1)} km · on the ${escH(p.label)} road</text>`;
    }else if(flowIsStickStub(loc)){
      const x=X(loc.joinKm),len=flowStubLen(loc),x0=x-len;
      out+=`<circle cx="${x0.toFixed(1)}" cy="195" r="11" fill="#17263e" stroke="${col}" stroke-width="1.6"/>`;
      out+=`<circle cx="${x0.toFixed(1)}" cy="195" r="6.5" fill="#334155"/>`;
      out+=`<circle cx="${x0.toFixed(1)}" cy="195" r="2.2" fill="${col}"/>`;
      out+=`<text x="${x0.toFixed(1)}" y="248" fill="#e2e8f0" font-size="10" font-weight="700" text-anchor="middle">${escH(loc.label)}</text>`;
      out+=`<text x="${x0.toFixed(1)}" y="259" fill="#94a3b8" font-size="8" text-anchor="middle">${fmt(loc.lengthKm,1)} km dock</text>`;
    }else{
      const x=X(loc.joinKm),h=flowSpurH(loc),y2=226+h;
      // Bulb size follows branch length so a 0.9 km plant spur and the
      // 17 km BLB pit road read as different things at a glance. Captions:
      // the label + "x km" only; the junction km already sits on the stick
      // ruler and the caption line at the top, so "joins stick at 2.5 km"
      // was three copies of one number and the widest text on the canvas
      // (it collided with a neighbouring branch's caption).
      const long=h>=90,r1=long?15:11,r2=long?10:7,r3=long?2.8:2.2;
      out+=`<circle cx="${x.toFixed(1)}" cy="${y2}" r="${r1}" fill="#17263e" stroke="${col}" stroke-width="1.8"/>`;
      out+=`<circle cx="${x.toFixed(1)}" cy="${y2}" r="${r2}" fill="#334155"/>`;
      out+=`<circle cx="${x.toFixed(1)}" cy="${y2}" r="${r3}" fill="${col}"/>`;
      out+=`<text x="${x.toFixed(1)}" y="${(y2+r1+13).toFixed(1)}" fill="#e2e8f0" font-size="${long?11:10}" font-weight="700" text-anchor="middle">${escH(loc.label)}</text>`;
      out+=`<text x="${x.toFixed(1)}" y="${(y2+r1+24).toFixed(1)}" fill="#94a3b8" font-size="8" text-anchor="middle">${fmt(loc.lengthKm,1)} km branch</text>`;
    }
  });
  // Dual ribbon: posted FMS limits (top) vs measured GPS loaded speed (bottom).
  // ONE speed ribbon (owner, 2026-08-25): GPS measured where it exists, the
  // posted limit as the fallback where GPS has no bin. Two stacked ribbons of
  // 6px colour chips doubled the small-print at the bottom of the band and
  // said nearly the same thing twice; a reader who wants both numbers still
  // gets them — the tooltip carries "GPS x km/h · posted y".
  // Speed ribbon stays on Capability (historical replay). Plan already has
  // GPS colour on the map — a second rainbow under the stick is noise.
  {
    const meas=corridor.measuredSpeeds||[];
    const lims=corridor.speedLimits||[];
    const gpsCol=v=>{if(!(v>0))return'#475569';if(v<12)return'#ef4444';if(v<18)return'#f59e0b';if(v<25)return'#38bdf8';return'#22c55e';};
    const postedAt=km=>{const z=lims.find(l=>km>=Math.min(l.fromKm,l.toKm)&&km<=Math.max(l.fromKm,l.toKm));return z?z.limit:null;};
    out+=`<text x="${left-4}" y="228" fill="#94a3b8" font-size="7" text-anchor="end">Speed</text>`;
    meas.forEach(z=>{const v=z.loadedKmh;if(!Number.isFinite(v))return;const x1=X(z.fromKm),x2=X(z.toKm);
      const post=postedAt((z.fromKm+z.toKm)/2);
      out+=`<rect x="${Math.min(x1,x2).toFixed(1)}" y="222" width="${Math.max(1,Math.abs(x2-x1)).toFixed(1)}" height="7" fill="${gpsCol(v)}" opacity=".9"><title>GPS loaded ${escH(z.seg)} · ${fmt(v,1)} km/h (empty ${fmt(z.emptyKmh,1)})${post?' · posted '+fmt(post)+' km/h':''}</title></rect>`;});
    lims.forEach(z=>{const x1=X(z.fromKm),x2=X(z.toKm);
      const covered=meas.some(m=>Number.isFinite(m.loadedKmh)&&Math.min(m.fromKm,m.toKm)<=Math.min(z.fromKm,z.toKm)&&Math.max(m.fromKm,m.toKm)>=Math.max(z.fromKm,z.toKm));
      if(covered)return;
      const col=z.limit<=20?'#ef4444':z.limit<=30?'#f59e0b':'#22c55e';
      out+=`<rect x="${Math.min(x1,x2).toFixed(1)}" y="222" width="${Math.max(1,Math.abs(x2-x1)).toFixed(1)}" height="7" fill="${col}" opacity=".45"><title>No GPS bin · posted ${fmt(z.limit)} km/h</title></rect>`;});
  }
  // Each named road section receives an independent risk overlay; selected constraints get an outline.
  const pid=base=>_flowIdPrefix+base;
  // ONE colour layer (owner, 2026-08-25): the road band itself stays tarmac.
  // The live hotspot recolour (updateFlowSimulator) and the constraint
  // selection now target the SEGMENT STRIP cells drawn above the road, via
  // the same flow-risk-zone-N ids the animation already updates. The old
  // full-height wash + green selection boxes stacked two more colour fields
  // onto a band that already carried tint, ribbons and particles.
  const secRange={1:[67.8,39],2:[39,27],3:[27,17],4:[17,0]};
  [..._gSelSec].forEach(id=>{const z=secRange[+id];if(!z)return;const x1=X(z[0]),x2=X(z[1]);
    out+=`<rect x="${x1.toFixed(1)}" y="145" width="${(x2-x1).toFixed(1)}" height="19" rx="3" fill="none" stroke="${pipeCol}" stroke-width="2" opacity=".95"/>`;});
  // Every logical path shares these same two travel lanes; colour belongs only to its trucks and
  // endpoint crossovers. The long vertical legs dominate each closed cycle.
  const ledger=[];
  routes.forEach((r,i)=>{
    const loaded=flowVerticesFromLegs(flowLoadedLegs(r),X,180);
    if(loaded.length<2)return;
    r.sourceX=loaded[0].x;r.destX=loaded[loaded.length-1].x;
    const c1=X(r.fromKm),c2=X(r.toKm);
    const d=loaded.map((p,idx)=>(idx?'L':'M')+' '+p.x.toFixed(1)+' '+p.y.toFixed(1)).join(' ');
    const fam=famOf(r.origin);
    if(!ledger[fam])ledger[fam]=[];
    ledger[fam].push({i,r});
    out+=`<g id="${pid('flow-span-'+i)}" opacity="0" pointer-events="none">`
      +`<rect x="${Math.min(c1,c2).toFixed(1)}" y="168" width="${Math.abs(c2-c1).toFixed(1)}" height="54" fill="${r.col}" opacity=".14"/>`
      +`<line x1="${c1.toFixed(1)}" y1="168" x2="${c1.toFixed(1)}" y2="222" stroke="${r.col}" stroke-width="2.5"/>`
      +`<line x1="${c2.toFixed(1)}" y1="168" x2="${c2.toFixed(1)}" y2="222" stroke="${r.col}" stroke-width="2.5"/>`
      +`<path d="M ${(c2-5).toFixed(1)} 165 L ${(c2+1).toFixed(1)} 168 L ${(c2-5).toFixed(1)} 171 Z" fill="${r.col}"/>`
      +`<text x="${((c1+c2)/2).toFixed(1)}" y="140" fill="${r.col}" font-size="11" font-weight="700" text-anchor="middle">${escH(r.origin)} → ${escH(r.dest)} · ${fmt(r.dt,0)} DT</text>`
      +`</g><path id="${pid('flow-path-'+i)}" d="${d}" fill="none" stroke="none"/>`;
    for(let j=0;j<r.particles;j++){out+=`<g id="${pid('flow-p-'+i+'-'+j)}" visibility="hidden"><title>${escH(r.origin)} → ${escH(r.dest)} · DT ${j+1}/${r.particles}</title><circle class="fp-halo" r="2.6" fill="${r.col}" opacity="0.16"/><circle r="1.25" fill="${r.col}" opacity="0.92"/></g>`;}
  });
  {
    const famNames=['TF','KR','BLB','POS'];
    const legEl=flowQ('c3-flow-legend');
    if(legEl){
      let html='';
      ledger.forEach((rows,f)=>{
        if(!rows||!rows.length)return;
        html+=`<div class="flow-leg-group"><span class="flow-leg-fam">${famNames[f]}</span>`;
        rows.forEach(({i,r})=>{
          html+=`<button type="button" class="flow-leg-chip" data-span="${pid('flow-span-'+i)}" title="${escH(r.origin)} → ${escH(r.dest)} · ${fmt(r.dt,0)} DT"><i style="background:${r.col}"></i><span>${escH(r.origin)} → ${escH(r.dest)}</span><em>${fmt(r.dt,0)} DT</em></button>`;
        });
        html+='</div>';
      });
      if(stickAlert)html+=`<span class="flow-leg-alert">${escH(stickAlert)}</span>`;
      legEl.innerHTML=html;
    }
  }
  // Non-WBN (IWIP / Position) trucks as WHITE particles on their own paths — congestion only, no WMT.
  let otherRoutes=[];
  if(_otherCtx&&_otherCtx.paths&&_otherCtx.paths.length&&_flowHost!=='plan'){
    otherRoutes=_otherCtx.paths.map(p=>{const xo=X(p.oKm),xd=X(p.dKm),sourceX=Math.min(xo,xd),destX=Math.max(xo,xd),particles=Math.max(2,Math.min(22,Math.round(p.trips/70))),loops=Math.max(2,p.trucks?Math.round(p.trips/p.trucks):4);return {label:p.label,sourceX,destX,particles,achievedTr:loops,startTimes:Array.from({length:particles},(_,j)=>j/particles)};});
    otherRoutes.forEach((r,i)=>{for(let j=0;j<r.particles;j++){out+=`<g id="${pid('flow-op-'+i+'-'+j)}" visibility="hidden"><title>Other road user (IWIP / Position) · ${escH(r.label)}</title><circle r="1.35" fill="#f8fafc" opacity="0.92" stroke="#334155" stroke-width="0.35"/></g>`;}});
    // IWIP / Position paths shown as a clean white legend BELOW the corridor (mirrors the WBN top legend),
    // each a white span with an origin dot + arrowhead toward the destination.
    out+=`<text x="${left}" y="312" fill="#64748b" font-size="8" font-weight="600" letter-spacing=".04em">OTHER ROAD USERS · IWIP / Position (white trucks share this road)</text>`;
    _otherCtx.paths.slice(0,6).forEach((p,i)=>{const xo=X(p.oKm),xd=X(p.dKm),lo=Math.min(xo,xd),hi=Math.max(xo,xd),gy=330+i*14,rt=xd>=xo;
      out+=`<line x1="${lo.toFixed(1)}" y1="${gy}" x2="${hi.toFixed(1)}" y2="${gy}" stroke="#e2e8f0" stroke-width="1.3" opacity=".7"/><circle cx="${xo.toFixed(1)}" cy="${gy}" r="2.1" fill="#e2e8f0" opacity=".85"/><path d="M ${(rt?xd-3:xd+3).toFixed(1)} ${(gy-3).toFixed(1)} L ${(rt?xd+2:xd-2).toFixed(1)} ${gy} L ${(rt?xd-3:xd+3).toFixed(1)} ${(gy+3).toFixed(1)} Z" fill="#e2e8f0" opacity=".85"/><text x="${((lo+hi)/2).toFixed(1)}" y="${(gy-2.5).toFixed(1)}" fill="#cbd5e1" font-size="7.5" text-anchor="middle">${escH(p.label)}</text>`;});
  }
  // Nodes remain at true proportional chainage; labels alternate sides to keep POS 10 / FENI 15 legible.
  // DETERMINISTIC label tiers (owner, 2026-08-25). The old rule was "even
  // index above, odd below", so which side a node landed on depended on array
  // ORDER, and POS 12/POS 10/FENI 15 fell wherever they fell — that is the
  // pile-up in the owner's screenshot. Tiering is now by IMPORTANCE: majors
  // (pits + smelter ends) above in 13px, minors below in 10px, and both tiers
  // nudge horizontally when two labels would overlap. Same data, same km.
  {
    const MAJOR=new Set(['TF','KR','POS 12','FENI 15','FENI 0']);
    const placed={above:[],below:[]};
    corridor.nodes.forEach(n=>{
      const x=X(n.km);
      const isMaj=MAJOR.has((n.label||'').toUpperCase());
      const side=isMaj?'above':'below';
      const fs=isMaj?13:10;
      const halfW=(String(n.label).length*fs*0.62)/2+6;
      let lx=x;
      for(let guard=0;guard<8;guard++){
        const clash=placed[side].find(q=>Math.abs(q.x-lx)<q.halfW+halfW);
        if(!clash)break;
        lx=clash.x+(lx>=clash.x?1:-1)*(clash.halfW+halfW+2);
      }
      placed[side].push({x:lx,halfW});
      const ly=side==='above'?126:262;
      out+=`<line x1="${x.toFixed(1)}" y1="${side==='above'?164:226}" x2="${x.toFixed(1)}" y2="${side==='above'?138:250}" stroke="#64748b" opacity=".7"/>`
        +`<circle cx="${x.toFixed(1)}" cy="195" r="${isMaj?5:4}" fill="#0b1220" stroke="#cbd5e1" stroke-width="1.5"/>`
        +`<text x="${lx.toFixed(1)}" y="${ly}" fill="${isMaj?'#f1f5f9':'#cbd5e1'}" font-size="${fs}" font-weight="700" text-anchor="middle">${escH(n.label)}</text>`
        +`<text x="${lx.toFixed(1)}" y="${ly+12}" fill="#64748b" font-size="9" text-anchor="middle">${fmt(n.km,1)} km</text>`;
    });
  }
  const seenExtra=new Set();
  routes.forEach(r=>{
    [r.originLoc,r.destLoc].forEach(loc=>{
      if(!loc||loc.kind!=='corridor'||!Number.isFinite(loc.km))return;
      if(loc.label==='BSE'){
        // Shares km 0 with FENI 0 (no BSE survey polyline yet), so it would
        // vanish into that node. Name it once, below the coast end, in the
        // same amber as the other off-node stops.
        if(seenExtra.has('BSE'))return;seenExtra.add('BSE');
        const x=X(0);
        out+=`<line x1="${x.toFixed(1)}" y1="226" x2="${x.toFixed(1)}" y2="250" stroke="#f59e0b" opacity=".55"/><text x="${(x+4).toFixed(1)}" y="262" fill="#f59e0b" font-size="10" font-weight="700" text-anchor="end">BSE</text><text x="${(x+4).toFixed(1)}" y="274" fill="#64748b" font-size="9" text-anchor="end">coast · at FENI 0</text>`;
        return;
      }
      if(corridor.nodes.some(n=>Math.abs(n.km-loc.km)<0.35))return;
      const k=loc.km.toFixed(1);if(seenExtra.has(k))return;seenExtra.add(k);
      const x=X(loc.km);
      // Off-node stops (POS 14 @ 26.1 sits 0.9 km from POS 12) sit on the
      // BELOW tier with the minors, tinted amber, instead of a lone label
      // pinned to the top edge where it collided with the verdict row.
      out+=`<line x1="${x.toFixed(1)}" y1="226" x2="${x.toFixed(1)}" y2="250" stroke="#f59e0b" opacity=".55"/><circle cx="${x.toFixed(1)}" cy="195" r="4" fill="#0b1220" stroke="#f59e0b" stroke-width="1.4"/><text x="${x.toFixed(1)}" y="262" fill="#f59e0b" font-size="10" font-weight="700" text-anchor="middle">${escH(loc.label)}</text><text x="${x.toFixed(1)}" y="274" fill="#64748b" font-size="9" text-anchor="middle">${fmt(loc.km,1)} km</text>`;
    });
  });
  {const used=_wbPos?_wbPos.filter(w=>Number.isFinite(w.km)&&w.km<=length&&w.km>=0&&(_flowHost==='plan'||w.usedOnShift)).sort((a,b)=>(b.trucks||0)-(a.trucks||0)):[];
    const WBCOL=['#f59e0b','#22c55e','#a78bfa','#38bdf8','#ec4899','#2dd4bf','#fb923c','#eab308','#f43f5e','#84cc16'],
      wbCol=i=>i===0?'#ef4444':WBCOL[(i-1)%WBCOL.length],wbNm=w=>'WB'+(w.wbNum||(w.name||'').replace(/\D/g,'')||'?');
    const order=used.map((w,i)=>({w,i,x:X(w.km)})).sort((a,b)=>a.x-b.x);
    let lastX=-99,lvl=0;order.forEach(o=>{lvl=(o.x-lastX<30)?(lvl+1)%2:0;lastX=o.x;o.lvl=lvl;});
    order.forEach(o=>{const w=o.w,col=wbCol(o.i),x=o.x,ly=166-o.lvl*9;
      out+=`<line x1="${x.toFixed(1)}" y1="173" x2="${x.toFixed(1)}" y2="${(ly+2).toFixed(1)}" stroke="${col}" stroke-width=".7" opacity=".45"/><circle cx="${x.toFixed(1)}" cy="176" r="3.4" fill="${w.onCorridor===false?'none':col}" stroke="${col}" stroke-width="${w.onCorridor===false?1.4:1}"><title>${escH(wbNm(w))} (${escH(w.name)}) · stick ~${fmt(w.km,1)} km${w.offM!=null?' · '+fmt(w.offM,0)+' m off centreline':''}${w.trucks?(' · '+fmt(w.trucks)+' weigh events'):''}${o.i===0&&w.trucks?' · busiest':''}${w.onCorridor===false?' · off-corridor spur':''}</title></circle><text x="${x.toFixed(1)}" y="${ly.toFixed(1)}" fill="${col}" font-size="8" font-weight="700" text-anchor="middle">${escH(wbNm(w))}</text>`;});}
  out+=`<text x="${right}" y="${capY+(stickAlert?24:12)}" fill="${pipeCol}" font-size="8.5" font-weight="600" letter-spacing=".04em" text-anchor="end" opacity=".85">${escH(band).toUpperCase()} LOAD</text>`;
  svg.innerHTML=out;
  const legEl=flowQ('c3-flow-legend');
  if(legEl){
    const chips=[...legEl.querySelectorAll('.flow-leg-chip')];
    chips.forEach(b=>{
      const span=document.getElementById(b.getAttribute('data-span'));
      b.addEventListener('mouseenter',()=>{if(span)span.setAttribute('opacity','1');
        chips.forEach(o=>{if(o!==b)o.style.opacity='.35';});});
      b.addEventListener('mouseleave',()=>{if(span)span.setAttribute('opacity','0');
        chips.forEach(o=>o.style.opacity='');});
    });
  }
  _flowSim={routes,otherRoutes,hour:0,running:false,raf:null,last:0,avgSection,band,dbTrips:0,targetTrips:0,achievedTrips:0,corridorKm:length,roadLeft:left,roadRight:right,liveCongestion:0,liveDensity:0,shiftExplicit:routes.every(r=>r.shiftExplicit),X};flowDeriveMode();renderFlowPlanner();
  // Default: GPS motion. Do not auto-call flowEstimateSpeeds (that overrides GPS).
  if(!_flowSpeedOverride){_flowMotionMode='gps';flowSeedGpsInputs();}
  _flowSpeedsInitialised=true;
  evaluateFlowScenario();
  flowUpdateMotionModeUi();
  flowMapEnsure().then(()=>{
    if(!_flowSim||typeof _flowSim.X!=='function')return;
    _flowSim.routes.forEach(r=>{r.loop=flowBuildRouteLoop(r,_flowSim.X);});
    updateFlowSimulator();
  });
}

/* ── GPS polyline map (Leaflet) — primary visual for Tab 1 flow ─────────── */
let _flowGeom=null,_flowChain=null;
function flowMapState(){
  const k=_flowIdPrefix||'';
  return _flowMapByHost[k]||(_flowMapByHost[k]={map:null,road:null,trucks:null,markers:{}});
}

function flowMapGpsColour(v){
  if(!(v>0))return'#475569';
  if(v<12)return'#ef4444';
  if(v<18)return'#f59e0b';
  if(v<25)return'#38bdf8';
  return'#22c55e';
}
function flowMapBuildChain(geo){
  // Unified TF→FENI chainage index from TOFU / KR / CRD centreline points.
  const alias=(geo.roadAlias)||{TF:'TOFU'};
  const want=new Set(['TOFU','KR','CRD','KRENE']);
  const pts=[];
  (geo.roads||[]).forEach(r=>{
    const road=(r.road||'').toUpperCase();
    if(!want.has(road)&&!want.has(alias[road]||''))return;
    (r.points||[]).forEach(p=>pts.push({km:p.km,lat:p.lat,lng:p.lng,road}));
  });
  pts.sort((a,b)=>b.km-a.km); // TF (high km) → FENI (0)
  // Deduplicate near-identical km markers across road joins.
  const out=[];
  pts.forEach(p=>{
    if(!out.length||Math.abs(out[out.length-1].km-p.km)>0.05)out.push(p);
  });
  return out;
}
function flowMapLatLngAt(km){
  const chain=_flowChain||[];
  if(!chain.length||!Number.isFinite(km))return null;
  if(km>=chain[0].km)return[chain[0].lat,chain[0].lng];
  if(km<=chain[chain.length-1].km){
    const last=chain[chain.length-1];return[last.lat,last.lng];
  }
  for(let i=1;i<chain.length;i++){
    const a=chain[i-1],b=chain[i];
    if(km<=a.km&&km>=b.km){
      const t=(a.km===b.km)?0:(a.km-km)/(a.km-b.km);
      return[a.lat+(b.lat-a.lat)*t,a.lng+(b.lng-a.lng)*t];
    }
  }
  return[chain[0].lat,chain[0].lng];
}
async function flowMapEnsure(){
  const el=flowQ('c3-flow-map');
  if(!el)return;
  const st=flowMapState();
  if(typeof L==='undefined'){
    el.innerHTML='<div class="muted" style="padding:16px;font-size:12px">Map library unavailable (Leaflet CDN). Open the schematic stick below for the chainage view.</div>';
    return;
  }
  try{
    if(!_flowGeom){
      const d=await(await fetch('/api/simulator/corridor-geometry',{cache:'no-store'})).json();
      _flowGeom=d;
    }
  }catch(e){
    el.innerHTML='<div class="muted" style="padding:16px;font-size:12px">Corridor geometry unavailable.</div>';
    return;
  }
  if(!_flowGeom||!_flowGeom.ok||!(_flowGeom.roads||[]).length){
    el.innerHTML='<div class="muted" style="padding:16px;font-size:12px">'
      +escH((_flowGeom&&_flowGeom.reason)||'corridor geometry unavailable')+'</div>';
    return;
  }
  _flowChain=flowMapBuildChain(_flowGeom);
  if(!st.map){
    st.map=L.map(el,{scrollWheelZoom:false,attributionControl:true,preferCanvas:true});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:18,attribution:'&copy; OpenStreetMap',
    }).addTo(st.map);
    st.road=L.layerGroup().addTo(st.map);
    st.trucks=L.layerGroup().addTo(st.map);
  }
  st.road.clearLayers();
  st.markers={};
  st.trucks.clearLayers();
  const corridor=(_D&&_D.corridor)||(_flowGeom.corridor)||{};
  const measured=corridor.measuredSpeeds||[];
  const posted=corridor.speedLimits||[];
  const bounds=[];
  const spurCol={BLB:'#a78bfa',HFC:'#f472b6',CBB:'#2dd4bf',CBBB:'#94a3b8',CSW:'#22c55e'};
  const mainRoads=new Set(['TOFU','KR','CRD','KRENE']);
  // Spur polylines first (under), then GPS-coloured TF→FENI stick.
  (_flowGeom.roads||[]).forEach(road=>{
    const name=(road.road||'').toUpperCase();
    if(mainRoads.has(name))return;
    const pts=(road.points||[]).map(p=>[p.lat,p.lng]);
    if(pts.length<2)return;
    const col=spurCol[name]||'#64748b';
    L.polyline(pts,{color:col,weight:5,opacity:0.85}).bindPopup(escH(name)+' spur · survey chainage').addTo(st.road);
    pts.forEach(p=>bounds.push(p));
  });
  // Paint GPS-coloured segments along the centreline.
  for(let i=1;i<_flowChain.length;i++){
    const a=_flowChain[i-1],b=_flowChain[i],mid=(a.km+b.km)/2;
    const seg=measured.find(s=>mid<=s.fromKm&&mid>=s.toKm);
    const lim=posted.find(z=>mid<=z.fromKm&&mid>=z.toKm);
    const v=seg&&seg.loadedKmh;
    const colour=flowMapGpsColour(v);
    // Phase C: tint road colour toward congested when simulate ratio < 1.
    const tint=_flowHost==='plan'?Math.max(0,Math.min(1,1-_flowSimRatio)):0;
    const paint=tint>0.15?(tint>0.45?'#ef4444':tint>0.25?'#f59e0b':colour):colour;
    const line=L.polyline([[a.lat,a.lng],[b.lat,b.lng]],{
      color:paint,weight:seg?6:3,opacity:seg?0.95:0.45,
    });
    const tip=['KM '+mid.toFixed(1)];
    if(seg)tip.push('GPS loaded '+(v==null?'—':fmt(v,1)+' km/h'),
      'empty '+(seg.emptyKmh==null?'—':fmt(seg.emptyKmh,1)+' km/h'));
    if(lim)tip.push('posted '+fmt(lim.limit)+' km/h');
    if(tint>0.05)tip.push('simulate tint '+(100*_flowSimRatio).toFixed(0)+'% achievable (illustration)');
    line.bindPopup(tip.map(escH).join('<br>'));
    line.addTo(st.road);
    bounds.push([a.lat,a.lng],[b.lat,b.lng]);
  }
  (corridor.nodes||[]).forEach(n=>{
    const ll=flowMapLatLngAt(n.km);if(!ll)return;
    L.circleMarker(ll,{radius:5,color:'#e2e8f0',weight:1.5,fillColor:'#0b1220',fillOpacity:1})
      .bindTooltip(escH(n.label)+' · '+fmt(n.km,1)+' km',{permanent:false})
      .addTo(st.road);
    bounds.push(ll);
  });
  flowJoins().forEach(j=>{
    if(j.endLat==null)return;
    L.circleMarker([j.endLat,j.endLng],{radius:6,color:'#c4b5fd',weight:2,fillColor:'#0b1220',fillOpacity:1})
      .bindTooltip(escH(j.label)+' · '+fmt(j.lengthKm,1)+' km spur · joins stick at '+fmt(j.joinKm,1)+' km',{permanent:j.road==='BLB',direction:'right',opacity:0.92})
      .addTo(st.road);
    bounds.push([j.endLat,j.endLng]);
    if(j.joinLat!=null)bounds.push([j.joinLat,j.joinLng]);
  });
  (_wbPos||[]).forEach(w=>{
    if(w.onCorridor===false||!Number.isFinite(w.km))return;
    const ll=flowMapLatLngAt(w.km);if(!ll)return;
    const nm='WB'+(w.wbNum||(w.name||'').replace(/\D/g,'')||'?');
    L.circleMarker(ll,{radius:4,color:'#f59e0b',weight:1.4,fillColor:'#f59e0b',fillOpacity:0.9})
      .bindTooltip(escH(nm)+' · '+fmt(w.km,1)+' km'+(w.offM!=null?' · '+fmt(w.offM,0)+' m off':'') ,{permanent:false})
      .addTo(st.road);
    bounds.push(ll);
  });
  if(bounds.length){
    st.map.fitBounds(bounds,{padding:[18,18]});
    setTimeout(()=>{try{st.map.invalidateSize();}catch(e){}},80);
  }
}
function flowMapSync(particles){
  const st=flowMapState();
  if(!st.map||!st.trucks||!_flowChain||!_flowChain.length)return;
  // Same list the stick just moved — do not sample. preferCanvas is on so a
  // December plan (~1,270 DT) stays on one canvas, not 1,270 DOM markers.
  const list=particles||[];
  const rLoad=3.2, rEmpty=2.6;
  const seen=new Set();
  list.forEach(p=>{
    const ll=((p.lat!=null&&p.lng!=null)?[p.lat,p.lng]:null)||flowLookupLL(p.road,p.roadKm)||flowMapLatLngAt(p.km);if(!ll)return;
    seen.add(p.id);
    let m=st.markers[p.id];
    if(!m){
      m=L.circleMarker(ll,{
        radius:p.loaded?rLoad:rEmpty,
        color:p.loaded?'#0b1220':'#94a3b8',
        weight:1,
        fillColor:p.col||'#38bdf8',
        fillOpacity:0.9,
      }).addTo(st.trucks);
      st.markers[p.id]=m;
    }else{
      m.setLatLng(ll);
      m.setStyle({fillColor:p.col||'#38bdf8',radius:p.loaded?rLoad:rEmpty});
    }
  });
  Object.keys(st.markers).forEach(id=>{
    if(seen.has(id))return;
    try{st.trucks.removeLayer(st.markers[id]);}catch(e){}
    delete st.markers[id];
  });
}

// Hydrate the official road geometry once. The literals in FLOW_SEG_FALLBACK
// are the offline copy; this is what keeps them from going stale the way the
// hardcoded densityFit and the crowding caption did.
document.addEventListener('DOMContentLoaded',function(){
  fetch('/api/road_segments').then(function(r){return r.json();})
    .then(flowHydrateSegments).catch(function(){});
  fetch('/api/congestion_tenants').then(function(r){return r.json();}).then(function(d){
    if(!d||!d.ok||!d.segment_flow_hr)return;
    _flowTenantFlow=d.segment_flow_hr;
    if(typeof _flowSim!=='undefined'&&_flowSim)evaluateFlowScenario();
  }).catch(function(){});
});
