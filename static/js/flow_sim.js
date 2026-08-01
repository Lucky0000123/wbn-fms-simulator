// flow_sim.js — Flow simulator — scenario evaluation, particle motion, animation loop,
// and the non-WBN ("other traffic") corridor model.
// Extracted verbatim from templates/simulator.html (Phase 1 refactor; no logic changes).

function flowPlayLabel(){return '▶ Run';}
// Analytic point on a route's loaded/empty rectangle loop (source→dest @180, down, dest→source @210, up).
// Replaces per-particle SVG getPointAtLength() in the hot loop → far cheaper, so many more trucks stay smooth.
function flowPointAt(r,phase){
  const x1=r.sourceX,x2=r.destX,w=x2-x1,len=2*w+60,d=(((phase%1)+1)%1)*len;
  if(d<w) return {x:x1+d,y:180};
  if(d<w+30) return {x:x2,y:180+(d-w)};
  if(d<2*w+30) return {x:x2-(d-w-30),y:210};
  return {x:x1,y:210-(d-2*w-30)};
}
function stopFlowSimulator(){if(_flowSim&&_flowSim.raf)cancelAnimationFrame(_flowSim.raf);if(_flowSim){_flowSim.raf=null;_flowSim.running=false;}const b=q('c3-flow-play');if(b)b.textContent=flowPlayLabel();}
function updateFlowSimulator(){
  const s=_flowSim;if(!s)return;const clock=(FLOW_SHIFT_START*60+Math.round(s.hour*60))%(24*60);q('c3-flow-clock').textContent=String(Math.floor(clock/60)).padStart(2,'0')+':'+String(clock%60).padStart(2,'0');q('c3-flow-progress').style.width=(100*s.hour/FLOW_SHIFT_HOURS).toFixed(1)+'%';
  s.routes.forEach(r=>buildFlowMotion(r,s.inputs,s.liveCongestion||0));
  const shiftTrips=_flowMode==='plan'?s.achievedTrips:s.dbTrips,completed=shiftTrips*s.hour/FLOW_SHIFT_HOURS;
  const moving=[];s.routes.forEach((r,i)=>{for(let j=0;j<r.particles;j++){const id=i+'-'+j,el=q('flow-p-'+id),depart=r.departures[j]||0;if(!el)continue;if(s.hour<depart){el.setAttribute('visibility','hidden');continue;}const active=Math.max(0,Math.min(FLOW_SHIFT_HOURS,s.hour-depart)),cycleTime=(r.startTimes[j]+(active?r.achievedTr*active/FLOW_SHIFT_HOURS:0))%1,phase=flowMotionPhase(r,cycleTime),pt=flowPointAt(r,phase);el.setAttribute('visibility','visible');moving.push({id,el,x:pt.x,y:pt.y,minX:r.sourceX,maxX:r.destX,weight:r.particleWeight});}});
  // Non-WBN white trucks join the SAME convoy as WBN (one physical lane → nobody overtakes). Hidden off.
  if(s.otherRoutes)s.otherRoutes.forEach((r,i)=>{for(let j=0;j<r.particles;j++){const el=q('flow-op-'+i+'-'+j);if(!el)continue;if(!_otherInModel){el.setAttribute('visibility','hidden');continue;}const cycleTime=(r.startTimes[j]+r.achievedTr*s.hour/FLOW_SHIFT_HOURS)%1,pt=flowPointAt(r,flowMotionPhase(r,cycleTime));el.setAttribute('visibility','visible');moving.push({id:'o'+i+'-'+j,el,x:pt.x,y:pt.y,minX:r.sourceX,maxX:r.destX,weight:1});}});
  // Persistent one-lane convoy order. Existing members never get re-sorted, so a follower cannot
  // exchange identity/order with its leader. New arrivals merge by physical position; if there is
  // no safe room at their endpoint they remain hidden in that endpoint's release reservoir.
  const states=s.vehicleStates||(s.vehicleStates={}),orders=s.laneOrders||(s.laneOrders={loaded:[],empty:[]}),byId=new Map(moving.map(p=>[p.id,p])),laneOf=p=>Math.abs(p.y-180)<.8?'loaded':Math.abs(p.y-210)<.8?'empty':null;
  moving.forEach(p=>{const st=states[p.id]||(states[p.id]={lane:null,lastX:p.x}),lane=laneOf(p);if(st.lane!==lane){st.lane=lane;st.lastX=p.x;}});
  // One physical lane means one convoy order across ALL routes. A leader constrains a follower only
  // while their route intervals overlap, preventing overtaking without pulling a TF truck out of the
  // TF–KR leg merely because a KR-origin truck has already left that shared interval.
  ['loaded','empty'].forEach(lane=>{const current=moving.filter(p=>laneOf(p)===lane),ids=new Set(current.map(p=>p.id));orders[lane]=(orders[lane]||[]).filter(id=>ids.has(id));const known=new Set(orders[lane]),entrants=current.filter(p=>!known.has(p.id)).sort((a,b)=>lane==='loaded'?b.x-a.x:a.x-b.x);entrants.forEach(p=>{let at=orders[lane].findIndex(id=>{const qq=byId.get(id),x=qq?qq.x:(states[id]?states[id].lastX:p.x);return lane==='loaded'?x<p.x:x>p.x;});if(at<0)at=orders[lane].length;orders[lane].splice(at,0,p.id);});const gap=1.8,leaders=[];orders[lane].forEach(id=>{const p=byId.get(id),st=states[id];if(!p||!st)return;const overlapping=leaders.filter(x=>x>=p.minX&&x<=p.maxX);if(lane==='loaded'){const free=Math.max(p.x,st.lastX),leader=overlapping.length?Math.min(...overlapping):null;p.x=Math.min(free,leader==null?free:leader-gap);if(p.x<p.minX){p.x=p.minX;p.el.setAttribute('visibility','hidden');}}else{const free=Math.min(p.x,st.lastX),leader=overlapping.length?Math.max(...overlapping):null;p.x=Math.max(free,leader==null?free:leader+gap);if(p.x>p.maxX){p.x=p.maxX;p.el.setAttribute('visibility','hidden');}}st.lastX=p.x;leaders.push(p.x);});});
  moving.forEach(p=>{p.el.setAttribute('transform',`translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`);
    // Highlight a truck while it's crossing between the loaded and empty lanes (the dump/load turnaround)
    // so the state change is clearly visible instead of an instant lane-swap.
    const cross=Math.abs(p.y-180)>=.8&&Math.abs(p.y-210)>=.8;
    if(p.el._cross!==cross){const c=p.el._c||(p.el._c=p.el.querySelector('circle'));if(c){c.setAttribute('r',cross?'3':'1.2');c.setAttribute('opacity',cross?'1':'0.85');c.setAttribute('stroke',cross?'#fff':'none');c.setAttribute('stroke-width',cross?'0.6':'0');}p.el._cross=cross;}
  });
  const loadedNow=moving.filter(p=>Math.abs(p.y-180)<.8&&p.el.getAttribute('visibility')!=='hidden').length,emptyNow=moving.filter(p=>Math.abs(p.y-210)<.8&&p.el.getAttribute('visibility')!=='hidden').length,crossoverNow=moving.filter(p=>Math.abs(p.y-180)>=.8&&Math.abs(p.y-210)>=.8&&p.el.getAttribute('visibility')!=='hidden').length;
  q('c3-flow-meta').innerHTML=`<b>${escH(s.band)} observed load</b> · live constrained density ${fmt(s.liveDensity||0,2)} DT/km · ${fmt(s.corridorKm,1)} km corridor<br>${_flowMode==='plan'?'simulating':'replaying'} ${fmt(completed)} / ${fmt(shiftTrips)} trips per 12h shift · loaded ${loadedNow} · empty return ${emptyNow} · crossover ${crossoverNow}`;
  const ranges={1:[67.8,39],2:[39,27],3:[27,17],4:[17,0]},activeRanges=[..._gSelSec].map(id=>ranges[+id]).filter(Boolean),kmAt=x=>s.corridorKm-(x-s.roadLeft)/(s.roadRight-s.roadLeft)*s.corridorKm,densities=activeRanges.map(z=>{const weight=moving.reduce((n,p)=>{const km=kmAt(p.x),onLane=Math.abs(p.y-180)<.8||Math.abs(p.y-210)<.8;return n+(onLane&&km<=z[0]&&km>=z[1]?p.weight:0);},0);return weight/Math.max(.1,z[0]-z[1]);}),density=Math.max(0,...densities),pressure=Math.max(0,Math.min(1,(density-2)/4));s.liveCongestion=(s.liveCongestion||0)+.08*(pressure-(s.liveCongestion||0));s.liveDensity=density;
  // Project visible particles onto the GPS polyline map (chainage → lat/lng).
  flowMapSync(moving.filter(p=>p.el.getAttribute('visibility')!=='hidden').map(p=>{
    const c=p.el._c||p.el.querySelector('circle');
    return {id:p.id,km:kmAt(p.x),loaded:Math.abs(p.y-180)<.8,col:(c&&c.getAttribute('fill'))||'#38bdf8'};
  }));
}
function flowFrame(ts){const s=_flowSim;if(!s||!s.running)return;if(!s.last)s.last=ts;const dt=Math.min(.1,(ts-s.last)/1000);s.last=ts;s.hour=Math.min(FLOW_SHIFT_HOURS,s.hour+dt*FLOW_SHIFT_HOURS/24);updateFlowSimulator();if(s.hour>=FLOW_SHIFT_HOURS){stopFlowSimulator();return;}s.raf=requestAnimationFrame(flowFrame);}
function flowToggle(){const s=_flowSim;if(!s)return;if(s.running){stopFlowSimulator();return;}if(s.hour>=FLOW_SHIFT_HOURS){s.hour=0;s.liveCongestion=0;s.liveDensity=0;s.vehicleStates={};s.laneOrders={loaded:[],empty:[]};}if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches){s.hour=FLOW_SHIFT_HOURS;updateFlowSimulator();return;}s.running=true;s.last=0;q('c3-flow-play').textContent='Ⅱ Pause';s.raf=requestAnimationFrame(flowFrame);}
function flowReset(){stopFlowSimulator();if(_flowSim){_flowSim.hour=0;_flowSim.liveCongestion=0;_flowSim.liveDensity=0;_flowSim.vehicleStates={};_flowSim.laneOrders={loaded:[],empty:[]};updateFlowSimulator();}}
// When false (default), motion uses corridor.measuredSpeeds (GPS). Advanced km/h
// inputs are display/override only — touching them sets _flowSpeedOverride.
let _flowSpeedOverride=false;
function flowInputs(){
  const n=(id,d)=>{const e=q(id),v=e&&parseFloat(e.value);return Number.isFinite(v)?v:d;};
  return {start:(q('flow-start')||{}).value||'split',
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
function flowSeedGpsInputs(){
  // Reflect measured medians in the Advanced fields without enabling override.
  const bands=flowMeasuredBands();
  if(!bands.length) return;
  const L=bands.map(b=>b.loadedKmh).filter(Number.isFinite).sort((a,b)=>a-b);
  const E=bands.map(b=>b.emptyKmh).filter(Number.isFinite).sort((a,b)=>a-b);
  const med=a=>a[Math.floor(a.length/2)];
  if(L.length&&q('flow-loaded-speed')) q('flow-loaded-speed').value=med(L).toFixed(1);
  if(E.length&&q('flow-empty-speed')) q('flow-empty-speed').value=med(E).toFixed(1);
}
function flowUseMeasuredGps(){
  _flowSpeedOverride=false; _flowSpeedsInitialised=true;
  flowSeedGpsInputs();
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
  segments.forEach(x=>{time+=x.hours/total;if(x.cross==='dump')g=gDump;else if(x.cross==='load')g=1;else if(x.loaded){travelledLoaded+=x.km;g=gLoaded*travelledLoaded/dist;}else{travelledEmpty+=x.km;g=gDump+(gEmpty-gDump)*travelledEmpty/dist;}r.motion.push({t:time,g});});
  r.destTimeFraction=segments.filter(x=>x.loaded).reduce((s,x)=>s+x.hours,0)/total;
  r.startTimes=r.startTimes.map((_,j)=>p.start==='destination'?r.destTimeFraction:p.start==='split'&&j%2?r.destTimeFraction:0);
  return total;
}
function flowLaneCapacity(p){
  // Prefer measured peak segment-hour trucks (GPS congestion extract). Fall
  // back to assumed headway only when that extract is missing.
  const mc=((_D&&_D.corridor)||{}).measuredCapacity||{};
  const measured=Number(mc.trucksPerHour);
  if(Number.isFinite(measured)&&measured>5){
    return {laneCapacity:measured,capSource:'measured',
      equivHeadway:mc.equivHeadwaySec||Math.round(3600/measured),
      method:mc.method||'measured GPS peak trucks/h'};
  }
  const assumed=3600/Math.max(1,p.headway||90);
  return {laneCapacity:assumed,capSource:'assumed-headway',
    equivHeadway:p.headway||90,method:'assumed min headway'};
}
function evaluateFlowScenario(){
  const s=_flowSim;if(!s)return;const p=flowInputs(),cap=flowLaneCapacity(p),laneCapacity=cap.laneCapacity,demand=s.routes.reduce((n,r)=>n+r.dt*p.fleet*flowRouteTarget(r)/p.hours,0),vc=demand/laneCapacity,congestion=vc>1?1/vc:1;
  s.capSource=cap.capSource;s.laneCapacity=laneCapacity;
  // Trip KPIs stay from DB / path-response. Motion uses GPS — do NOT inflate speeds
  // so kinematics invent the trip rate (old sharedOpenFactor behaviour).
  p.sharedOpenFactor=1;
  let target=0,achieved=0,dbTrips=0,fleetTotal=0;s.routes.forEach(r=>{const trucks=r.dt*p.fleet;r.targetTr=flowRouteTarget(r);buildFlowMotion(r,p,Math.max(0,vc-.7));r.achievedTr=r.targetTr;r.targetTrips=trucks*r.targetTr;r.achievedTrips=r.targetTrips;dbTrips+=r.dbTrips;target+=r.targetTrips;achieved+=r.achievedTrips;fleetTotal+=trucks;});
  s.dbTrips=dbTrips;s.targetTrips=target;s.achievedTrips=achieved;s.vc=vc;s.queue=Math.max(0,Math.ceil((demand-laneCapacity)*p.hours));s.inputs=p;
  q('flow-attain').textContent=fmt(_flowMode==='plan'?achieved:dbTrips);q('flow-attain-label').textContent=_flowMode==='plan'?'Estimated trips / 12h shift':'Average DB trips / shift';q('flow-vc').textContent=fmt(vc,2);q('flow-queue').textContent=fmt(s.queue);
  const vcHint=q('flow-vc-hint');
  if(vcHint){
    vcHint.textContent=cap.capSource==='measured'
      ?(`measured · ~${fmt(laneCapacity,0)} tph · ≡${fmt(cap.equivHeadway)}s`)
      :(`assumed headway ${fmt(cap.equivHeadway)}s`);
  }
  // Est. production = trips × avg tonnes/trip (TF from the capability selection). Reflects the fleet plan.
  const _tf=(_D&&_D.kpi&&_D.kpi.tf)||0,_trips=(_flowMode==='plan'?achieved:dbTrips),_prod=_tf?_trips*_tf:0;
  const _prodBase=_tf?dbTrips*_tf:0,_dWMT=_prod-_prodBase;   // WMT vs the actual shift
  q('flow-prod').innerHTML=_prod?(fmtM(_prod)+(_flowMode==='plan'&&Math.abs(_dWMT)>=1?` <span style="font-size:11px;color:${_dWMT>=0?'#22c55e':'#ef4444'}">${_dWMT>=0?'+':'−'}${fmtM(Math.abs(_dWMT))}</span>`:'')):'—';
  q('flow-prod-label').textContent=(_flowMode==='plan'?'Est. WMT / shift vs actual':'Avg production / shift')+(_tf?' · TF '+fmt(_tf,1)+' t':'');
  updateFlowModeBadge();
  const sectionDefs=[{id:1,label:'TOFU–KR',from:67.8,to:39},{id:2,label:'KR–POS 12',from:39,to:27},{id:3,label:'POS 12–POS 10',from:27,to:17},{id:4,label:'POS 10–FENI',from:17,to:0}];
  s.hotspots=sectionDefs.map(z=>{const wbnTrips=s.routes.filter(r=>r.fromKm>=z.from&&r.toKm<=z.to).reduce((n,r)=>n+r.dt*p.fleet*flowRouteTarget(r),0),otherTrips=otherSectionTrips(z.label),trips=wbnTrips+otherTrips,hourly=trips/p.hours,ratio=hourly/laneCapacity,status=ratio>=1?'High':ratio>=.7?'Watch':'Open',colour=ratio>=1?'#ef4444':ratio>=.7?'#f59e0b':'#22c55e';return {...z,trips,wbnTrips,otherTrips,hourly,ratio,status,colour};});
  s.hotspots.forEach(z=>{const el=q('flow-risk-zone-'+z.id);if(el){el.setAttribute('fill',z.colour);el.setAttribute('opacity',z.ratio>=1?'.38':z.ratio>=.7?'.25':'.10');}});
  q('flow-hotspots').innerHTML=s.hotspots.map(z=>`<span class="flow-hotspot"><i style="background:${z.colour}"></i><b>${escH(z.label)}</b> ${z.status} · V/C ${fmt(z.ratio,2)}</span>`).join('');
  const worst=s.hotspots.reduce((a,b)=>b.ratio>a.ratio?b:a,s.hotspots[0]),picked=_flowPointScenario?`3D scenario: ${_flowPointScenario.date} · ${_flowPointScenario.label}. `:'',basis=s.shiftExplicit?'DB shift basis confirmed by NB_SHIFT. ':'Some source rows have no explicit NB_SHIFT; those values remain on their original basis. ',fleetGap=_flowMode==='plan'&&Number.isFinite(_flowFleetAvailable)?_flowFleetAvailable-fleetTotal:null,fleetWarning=fleetGap!=null&&fleetGap<0?` Fleet is over-allocated by ${fmt(-fleetGap,0)} DT.`:'';const bottleneck=worst.ratio>=1?`Highest congestion risk is ${worst.label} (V/C ${fmt(worst.ratio,2)}); demand exceeds the modelled lane capacity.`:worst.ratio>=.7?`Highest congestion risk is ${worst.label} (V/C ${fmt(worst.ratio,2)}); it is approaching saturation.`:`All mapped sections retain headway reserve; the highest load is ${worst.label} (V/C ${fmt(worst.ratio,2)}).`;q('flow-alert').textContent=picked+basis+bottleneck+fleetWarning;
  q('flow-routes').innerHTML=s.routes.map(r=>{const effChg=_flowMode==='plan'&&r.predEff&&Math.abs(r.targetTr-r.tr)>0.01,extrap=r.predEff&&r.dt>r.dtMax;
    const effTxt=effChg?`<b style="color:#fcd34d">${fmt(r.targetTr,2)} predicted Trips/DT</b> <span class="muted">(actual ${fmt(r.tr,2)}${extrap?', ⚠ beyond observed '+fmt(r.dtMax,0)+' DT':''})</span>`:`<b>${fmt(r.tr,2)} DB Trips/DT/shift</b>`;
    const rp=flowRainPct(r),rainTxt=(rp!==null&&rp<-3)?` · <span style="color:#60a5fa" title="Historically rain-sensitive: measured efficiency runs ~${fmt(-rp,0)}% lower on a wet (10 mm) day, fleet held constant. Daily rainfall is a rough proxy for road/mud state, so treat as context, not a precise predictor.">☔ rain-sensitive</span>`:'';
    const src=r.speedSource==='gps'?'GPS':(r.speedSource==='override'?'override':'est');
    const over=r.overLimitPct>1?` · <span style="color:#f87171" title="Share of route km where measured/override speed exceeds posted FMS limit">${fmt(r.overLimitPct,0)}% over posted limit</span>`:'';
    return `<div><span style="color:${r.col}">■</span> <b>${escH(r.label)}</b> · ${effTxt}${rainTxt} · ${_flowMode==='plan'?`${fmt(r.dbDt,0)} actual → <b>${fmt(r.dt,0)} scenario DT</b> · ${fmt(r.achievedTrips,0)} predicted trips/shift`:`${fmt(r.dbDt,1)} DB DT/shift · ${fmt(r.dbTrips)} DB trips/shift${r.shiftExplicit?'':' · shift count unavailable'}`} · ${r.particles} visual elements · ${src} loaded ${fmt(r.loadedSpeedRange[0],1)}–${fmt(r.loadedSpeedRange[1],1)} km/h · empty ${fmt(r.emptySpeedRange[0],1)}–${fmt(r.emptySpeedRange[1],1)} km/h${over}</div>`;}).join('');
  // Honesty caption under the map / stick.
  const win=((_D&&_D.corridor)||{}).measuredWindow||{};
  const note=q('flow-note');
  if(note){
    const gpsN=flowMeasuredBands().length, limN=flowPostedLimits().length;
    const winTxt=(win.from&&win.to)?`${win.from} → ${win.to}`:'(no GPS window)';
    const capTxt=cap.capSource==='measured'
      ?`V/C capacity = measured ${fmt(laneCapacity,0)} trucks/h (${cap.method})`
      :`V/C capacity = assumed ${fmt(cap.equivHeadway)}s headway (no measured peaks)`;
    note.textContent=`GPS corridor map · motion = measured GPS (${gpsN} bands, ${winTxt}) · posted FMS limits as overlay (${limN} zones) · trip counts from dispatch, not from road physics · ${capTxt}.`;
  }
  if(_combined3D){const rr=_combined3D.ranges,path=fleetTotal?_avg(s.routes,r=>r.dt*p.fleet):0,section=s.avgSection*p.fleet,tr=fleetTotal?achieved/fleetTotal:0,clamp=(v,r)=>Math.max(-1,Math.min(1,-1+2*(v-r.lo)/r.d)),selected=_flowPointScenario&&_combined3D.points[_flowPointScenario.pointIndex];_combined3D.scenario=selected?{...selected}: {path,section,tr,nx:clamp(path,rr.path),ny:clamp(section,rr.section),nz:clamp(tr,rr.tr)};renderCombined3D();}
  updateFlowSimulator();
}
function flowEstimateSpeeds(){
  // Optional override: back-solve corridor-average from trip rate (NOT GPS).
  if(!_flowSim)return;
  const p=flowInputs(),vals=[];
  _flowSim.routes.forEach(r=>{const cycle=p.hours/flowRouteTarget(r)-p.dwell/60,dist=Math.abs(r.fromKm-r.toKm);if(cycle>0&&dist>0)vals.push({v:dist*(1/.9+1/1.1)/cycle,w:r.dt});});
  if(!vals.length)return;
  const base=vals.reduce((s,x)=>s+x.v*x.w,0)/vals.reduce((s,x)=>s+x.w,0),clamp=v=>Math.max(5,Math.min(80,v));
  q('flow-loaded-speed').value=clamp(.9*base).toFixed(1);
  q('flow-empty-speed').value=clamp(1.1*base).toFixed(1);
  _flowSpeedOverride=true;_flowSpeedsInitialised=true;flowScenarioChanged(true);
}
// Mode is DERIVED, never toggled: any route whose planned DT differs from its actual → simulated scenario.
function flowDeriveMode(){
  if(!_flowSim)return;
  const changed=_flowSim.routes.some(r=>Number.isFinite(_flowPlanDraft[r.key])&&Math.round(_flowPlanDraft[r.key])!==Math.round(r.dbDt));
  _flowMode=changed?'plan':'replay';
}
function updateFlowModeBadge(){
  const el=q('flow-mode-badge');if(!el)return;
  const dt=_flowSim?Math.round(_flowSim.routes.reduce((n,r)=>n+r.dt,0)):0,actual=_flowSim?Math.round(_flowSim.routes.reduce((n,r)=>n+r.dbDt,0)):0;
  if(_flowMode==='plan'){ el.className='flow-mode-badge plan'; el.textContent='◆ SIMULATED SCENARIO · '+fmt(dt,0)+' DT (actual '+fmt(actual,0)+')'; }
  else { el.className='flow-mode-badge replay'; el.textContent='● ACTUAL AVERAGE SHIFT · '+fmt(dt,0)+' DT'; }
}
function renderFlowPlanner(){const box=q('flow-planner');if(!box||!_flowSim)return;box.style.display='block';_flowSim.routes.forEach(r=>{if(!Number.isFinite(_flowPlanDraft[r.key]))_flowPlanDraft[r.key]=Math.round(r.dbDt);});const current=Math.round(_flowSim.routes.reduce((n,r)=>n+r.dbDt,0));if(!Number.isFinite(_flowFleetAvailable))_flowFleetAvailable=current;const scenario=_flowSim.routes.reduce((n,r)=>n+(_flowPlanDraft[r.key]??r.dbDt),0),balance=_flowFleetAvailable-scenario,balanceClass=balance<0?'bad':balance===0?'':'warn',balanceText=balance<0?`Over-allocated by ${fmt(-balance,0)} DT`:balance>0?`${fmt(balance,0)} DT unallocated`:'Fleet fully allocated';box.innerHTML=`<div class="flow-plan-top"><span>Fleet Planner</span><label class="flow-fleet-total">Available fleet <input type="number" min="0" step="1" value="${Math.round(_flowFleetAvailable)}" onchange="flowFleetAvailableSet(this.value)"> DT</label></div><div class="flow-plan-grid">${_flowSim.routes.map(r=>`<div class="flow-plan-card"><b><span style="color:${r.col}">■</span> ${escH(r.label)}</b><div class="flow-plan-edit"><button onclick="flowPlanStep('${escH(r.key)}',-5)">−</button><input type="number" min="0" step="1" value="${Math.round(_flowPlanDraft[r.key])}" onchange="flowPlanSet('${escH(r.key)}',this.value)"><button onclick="flowPlanStep('${escH(r.key)}',5)">+</button><span>DT</span></div><div class="flow-plan-current">Actual: ${fmt(r.dbDt,0)} DT/shift · ${fmt(r.tr,2)} DB Trips/DT/shift</div></div>`).join('')}</div><div class="flow-fleet-balance ${balanceClass}"><b>Actual fleet:</b> ${fmt(current,0)} DT · <b>Allocated:</b> ${fmt(scenario,0)} DT · <b>${balanceText}</b></div><div style="margin-top:8px;font-size:11px"><a onclick="flowPlanReset()" style="cursor:pointer;color:#7eb8f7">↺ Reset fleet to actual</a> <span class="muted">· edit fleet above, then press Run Scenario ▲</span></div>${_flowOtherBlock()}`;}
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
function flowFleetAvailableSet(value){_flowFleetAvailable=Math.max(0,Math.round(+value||0));renderFlowPlanner();}
function flowPlanSet(key,value){_flowPlanDraft[key]=Math.max(0,Math.round(+value||0));flowApplyPlanLight();}
function flowPlanStep(key,delta){_flowPlanDraft[key]=Math.max(0,Math.round((_flowPlanDraft[key]||0)+delta));flowApplyPlanLight();}
function flowPlanReset(){if(!_flowSim)return;_flowSim.routes.forEach(r=>_flowPlanDraft[r.key]=Math.round(r.dbDt));_flowFleetAvailable=Math.round(_flowSim.routes.reduce((n,r)=>n+r.dbDt,0));renderFlowSimulator(_flowSource.P,_flowSource.colours,true);}
function runFlowPlan(){if(!_flowSource)return;stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);flowToggle();}
function flowScenarioChanged(speedTouched){if(!_flowSim||!_flowSource)return;if(speedTouched){_flowSpeedsInitialised=true;_flowSpeedOverride=true;}stopFlowSimulator();renderFlowSimulator(_flowSource.P,_flowSource.colours,true);}
// Editing a fleet input updates the CONGESTION ANALYSIS live (V/C, trips, production, queue) without the
// heavy particle rebuild — so as you add trucks you immediately see the predicted congestion respond.
function flowApplyPlanLight(){
  if(!_flowSim){renderFlowPlanner();return;}
  _flowSim.routes.forEach(r=>{if(Number.isFinite(_flowPlanDraft[r.key]))r.dt=_flowPlanDraft[r.key];});
  flowDeriveMode();renderFlowPlanner();evaluateFlowScenario();
}
// Single run/pause control: a fresh Run always re-renders the road for the current fleet, then plays.
function flowRunOrPause(){const s=_flowSim;if(s&&s.running){stopFlowSimulator();return;}runFlowPlan();}
function renderFlowSimulator(P,colours){
  const selectedDate=(_flowPointScenario&&_flowPointScenario.date)||'';
  if(selectedDate&&selectedDate!==_wbPosDate)loadWbPositions(0,selectedDate);
  if(selectedDate)loadShiftContext(selectedDate);
  stopFlowSimulator();_flowSource={P,colours};const svg=q('c3-flow-svg'),fallback={source:'WBN_DATABASE.dbo.HAUL_ROAD_STA',basis:'road chainage',lengthKm:67.8,nodes:[{id:'tf',label:'TF',km:67.8,aliases:['TF','TOFU']},{id:'kr',label:'KR',km:39,aliases:['KR','KRENE']},{id:'pos12',label:'POS 12',km:27,aliases:['POS 12','POS12']},{id:'pos10',label:'POS 10',km:17,aliases:['POS 10','POS10']},{id:'feni15',label:'FENI 15',km:15,aliases:['FENI KM15','FENI 15']},{id:'feni0',label:'FENI 0',km:0,aliases:['FENI KM0','FENI 0']} ]},corridor=(_D&&_D.corridor)||fallback,by={},scenarioP=_flowPointScenario?P.filter(p=>p.date===_flowPointScenario.date):P;
  scenarioP.forEach(p=>{const g=by[p.pathKey]||(by[p.pathKey]={key:p.pathKey,label:p.label,dt:0,tr:0,trips:0,n:0,shiftExplicit:true});g.dt+=p.path;g.tr+=Number.isFinite(p.shiftTr)?p.shiftTr:p.tr;g.trips+=Number.isFinite(p.shiftTrips)?p.shiftTrips:p.trips;g.shiftExplicit=g.shiftExplicit&&p.shiftExplicit!==false;g.n++;});
  const norm=x=>(x||'').trim().toUpperCase().replace(/\s+/g,' '),nodeFor=name=>corridor.nodes.find(n=>(n.aliases||[n.label]).some(a=>norm(a)===norm(name))),routeParts=k=>{const i=k.indexOf('>');return i<0?['','']:[k.slice(0,i),k.slice(i+1)];};
  let routes=Object.values(by).map(g=>{const [o,d]=routeParts(g.key),a=nodeFor(o),b=nodeFor(d),dbDt=g.dt/g.n,scenarioDt=Number.isFinite(_flowPlanDraft[g.key])?_flowPlanDraft[g.key]:dbDt;return {...g,origin:o,dest:d,fromKm:a&&a.km,toKm:b&&b.km,dbDt,dt:scenarioDt,tr:g.tr/g.n,dbTrips:g.trips/g.n,col:colours[g.key]};}).filter(r=>Number.isFinite(r.fromKm)&&Number.isFinite(r.toKm)&&r.fromKm>r.toKm).sort((a,b)=>b.dt-a.dt);
  if(!routes.length){svg.innerHTML='<text x="220" y="270" text-anchor="middle" fill="#94a3b8" font-size="12">Selected routes are not mapped to the TF–FENI corridor.</text>';_flowSim=null;return;}
  // Visual density scales with the SCENARIO fleet — ~1 particle per DT (capped for perf) so 1,000 DT
  // actually shows ~1,000 trucks, not a fixed 500-element budget. Advanced "Trace elements" can override.
  const fp=flowInputs(),fleet=fp.fleet,sumDt=routes.reduce((s,r)=>s+r.dt,0),allocationBase=Math.max(1,sumDt),
    _elBudget=fp.elementsTouched?fp.elements:Math.round(sumDt),
    totalElements=Math.max(routes.length,Math.min(1400,_elBudget||500)),remaining=totalElements-routes.length;
  routes=routes.map(r=>{const raw=remaining*r.dt/allocationBase,n=Math.floor(raw);return {...r,particles:1+n,_fraction:raw-n};});
  for(let leftN=totalElements-routes.reduce((s,r)=>s+r.particles,0);leftN>0;leftN--)routes.slice().sort((a,b)=>b._fraction-a._fraction)[(leftN-1)%routes.length].particles++;
  routes.forEach(r=>{r.particleWeight=r.dt*fleet/r.particles;r.departures=Array(r.particles).fill(0);r.startTimes=Array(r.particles).fill(0);});
  // One global release sequence prevents simultaneous source pulses. Paths are round-robin, but each
  // element is released at the source belonging to its own path. Weighted elements are spread over
  // the full 12-hour shift and never emitted as a batch.
  let releaseOrder=[],maxParticles=Math.max(...routes.map(r=>r.particles));for(let j=0;j<maxParticles;j++)routes.forEach(r=>{if(j<r.particles)releaseOrder.push({r,j});});let releaseSeconds=0;const shiftStep=FLOW_SHIFT_HOURS*3600/releaseOrder.length;releaseOrder.forEach(x=>{x.r.departures[x.j]=releaseSeconds/3600;releaseSeconds+=Math.max(shiftStep,Math.max(fp.headway,fp.stagger*60)*x.r.particleWeight);});
  const avgSection=_avg(scenarioP,p=>p.section),groups=c3LoadGroups(P),band=(groups.find(g=>avgSection>=g.min&&avgSection<=g.max)||groups.reduce((a,b)=>Math.abs(b.section-avgSection)<Math.abs(a.section-avgSection)?b:a,groups[0])).label,pipeCol=band==='Congested'?'#ef4444':'#22c55e',left=55,right=945,length=corridor.lengthKm||Math.max(...corridor.nodes.map(n=>n.km)),X=km=>left+(length-km)/length*(right-left);
  let out='<title>07:00 to 19:00 finite-truck road simulation</title><desc>Every particle represents one average selected DT for a 12-hour shift. Loaded and empty trucks share one no-overtaking left-hand-traffic road.</desc>';
  for(let km=0;km<=60;km+=10){const x=X(km);out+=`<line x1="${x.toFixed(1)}" y1="236" x2="${x.toFixed(1)}" y2="248" stroke="#334155"/><text x="${x.toFixed(1)}" y="260" fill="#64748b" font-size="9" text-anchor="middle">km ${km}</text>`;}
  const win=((corridor.measuredWindow)||{});
  const winLbl=(win.from&&win.to)?` · GPS ${win.from}→${win.to}`:'';
  out+=`<text x="20" y="24" fill="#64748b" font-size="9">DB road chainage · ${escH(corridor.source||'haul-road source')}${escH(winLbl)}</text><rect x="${left}" y="164" width="${right-left}" height="62" rx="14" fill="#17263e"/><rect x="${left}" y="172" width="${right-left}" height="46" rx="9" fill="#334155"/><line x1="${left}" y1="195" x2="${right}" y2="195" stroke="#94a3b8" stroke-width="1" stroke-dasharray="8 8" opacity=".45"/><text x="${left}" y="150" fill="#94a3b8" font-size="9">LOADED →</text><text x="${right}" y="248" fill="#94a3b8" font-size="9" text-anchor="end">← EMPTY RETURN</text>`;
  // Dual ribbon: posted FMS limits (top) vs measured GPS loaded speed (bottom).
  out+=`<text x="${left-4}" y="223" fill="#94a3b8" font-size="7" text-anchor="end">Posted</text>`;
  (corridor.speedLimits||[]).forEach(z=>{const x1=X(z.fromKm),x2=X(z.toKm),col=z.limit<=20?'#ef4444':z.limit<=30?'#f59e0b':'#22c55e';out+=`<rect x="${x1.toFixed(1)}" y="218" width="${Math.max(1,x2-x1).toFixed(1)}" height="6" fill="${col}" opacity=".85"><title>Posted ${escH(z.chainage||z.segment)} · ${fmt(z.limit)} km/h</title></rect><text x="${((x1+x2)/2).toFixed(1)}" y="223" fill="#0b1220" font-size="6" font-weight="700" text-anchor="middle">${fmt(z.limit)}</text>`;});
  out+=`<text x="${left-4}" y="233" fill="#94a3b8" font-size="7" text-anchor="end">GPS</text>`;
  const meas=corridor.measuredSpeeds||[];
  const gpsCol=v=>{if(!(v>0))return'#475569';if(v<12)return'#ef4444';if(v<18)return'#f59e0b';if(v<25)return'#38bdf8';return'#22c55e';};
  meas.forEach(z=>{const v=z.loadedKmh,x1=X(z.fromKm),x2=X(z.toKm);if(!Number.isFinite(v))return;
    out+=`<rect x="${x1.toFixed(1)}" y="227" width="${Math.max(1,x2-x1).toFixed(1)}" height="6" fill="${gpsCol(v)}" opacity=".9"><title>GPS loaded ${escH(z.seg)} · ${fmt(v,1)} km/h (empty ${fmt(z.emptyKmh,1)})</title></rect>`;});
  // Each named road section receives an independent risk overlay; selected constraints get an outline.
  const secRange={1:[67.8,39],2:[39,27],3:[27,17],4:[17,0]};Object.entries(secRange).forEach(([id,z])=>{const x1=X(z[0]),x2=X(z[1]);out+=`<rect id="flow-risk-zone-${id}" x="${x1.toFixed(1)}" y="164" width="${(x2-x1).toFixed(1)}" height="62" fill="#22c55e" opacity=".10"/>`;});[..._gSelSec].forEach(id=>{const z=secRange[+id];if(!z)return;const x1=X(z[0]),x2=X(z[1]);out+=`<rect x="${x1.toFixed(1)}" y="164" width="${(x2-x1).toFixed(1)}" height="62" fill="none" stroke="${pipeCol}" stroke-width="2" opacity=".9"/>`;});
  // Every logical path shares these same two travel lanes; colour belongs only to its trucks and
  // endpoint crossovers. The long vertical legs dominate each closed cycle.
  routes.forEach((r,i)=>{const x1=X(r.fromKm),x2=X(r.toKm),d=`M ${x1.toFixed(1)} 180 L ${x2.toFixed(1)} 180 L ${x2.toFixed(1)} 210 L ${x1.toFixed(1)} 210 Z`,gy=42+(i%10)*10;r.sourceX=x1;r.destX=x2;out+=`<path d="M ${x1.toFixed(1)} ${gy} L ${x2.toFixed(1)} ${gy}" stroke="${r.col}" stroke-width="1.5" opacity="0.7"/><circle cx="${x1.toFixed(1)}" cy="${gy}" r="2.8" fill="${r.col}"/><path d="M ${(x2-3).toFixed(1)} ${gy-3} L ${(x2+3).toFixed(1)} ${gy} L ${(x2-3).toFixed(1)} ${gy+3} Z" fill="${r.col}"/><text x="${((x1+x2)/2).toFixed(1)}" y="${gy-2}" fill="${r.col}" font-size="7.5" text-anchor="middle">${escH(r.origin)} → ${escH(r.dest)}</text><line x1="${x1.toFixed(1)}" y1="176" x2="${x1.toFixed(1)}" y2="214" stroke="${r.col}" stroke-width="2" opacity="0.65"/><line x1="${x2.toFixed(1)}" y1="176" x2="${x2.toFixed(1)}" y2="214" stroke="${r.col}" stroke-width="2" opacity="0.65"/><path id="flow-path-${i}" d="${d}" fill="none" stroke="none"/>`;for(let j=0;j<r.particles;j++){const staged=fp.start==='destination'||fp.start==='split'&&j%2?'destination':'source';out+=`<g id="flow-p-${i}-${j}" visibility="hidden"><title>Element ${j+1}/${r.particles} · staged at ${staged} · weight ${fmt(r.particleWeight,3)} DT · ${escH(r.origin)} → ${escH(r.dest)} · release +${fmt(r.departures[j]*60,1)} min</title><circle r="1.15" fill="${r.col}" opacity="0.88"/></g>`;}});
  // Non-WBN (IWIP / Position) trucks as WHITE particles on their own paths — congestion only, no WMT.
  let otherRoutes=[];
  if(_otherCtx&&_otherCtx.paths&&_otherCtx.paths.length){
    otherRoutes=_otherCtx.paths.map(p=>{const xo=X(p.oKm),xd=X(p.dKm),sourceX=Math.min(xo,xd),destX=Math.max(xo,xd),particles=Math.max(2,Math.min(22,Math.round(p.trips/70))),loops=Math.max(2,p.trucks?Math.round(p.trips/p.trucks):4);return {label:p.label,sourceX,destX,particles,achievedTr:loops,startTimes:Array.from({length:particles},(_,j)=>j/particles)};});
    otherRoutes.forEach((r,i)=>{for(let j=0;j<r.particles;j++){out+=`<g id="flow-op-${i}-${j}" visibility="hidden"><title>Other road user (IWIP / Position) · ${escH(r.label)}</title><circle r="1.35" fill="#f8fafc" opacity="0.92" stroke="#334155" stroke-width="0.35"/></g>`;}});
    // IWIP / Position paths shown as a clean white legend BELOW the corridor (mirrors the WBN top legend),
    // each a white span with an origin dot + arrowhead toward the destination.
    out+=`<text x="${left}" y="316" fill="#94a3b8" font-size="8.5">◻ IWIP / Position paths (white trucks share this road)</text>`;
    _otherCtx.paths.slice(0,6).forEach((p,i)=>{const xo=X(p.oKm),xd=X(p.dKm),lo=Math.min(xo,xd),hi=Math.max(xo,xd),gy=328+i*10,rt=xd>=xo;
      out+=`<line x1="${lo.toFixed(1)}" y1="${gy}" x2="${hi.toFixed(1)}" y2="${gy}" stroke="#e2e8f0" stroke-width="1.3" opacity=".7"/><circle cx="${xo.toFixed(1)}" cy="${gy}" r="2.1" fill="#e2e8f0" opacity=".85"/><path d="M ${(rt?xd-3:xd+3).toFixed(1)} ${(gy-3).toFixed(1)} L ${(rt?xd+2:xd-2).toFixed(1)} ${gy} L ${(rt?xd-3:xd+3).toFixed(1)} ${(gy+3).toFixed(1)} Z" fill="#e2e8f0" opacity=".85"/><text x="${((lo+hi)/2).toFixed(1)}" y="${(gy-2.5).toFixed(1)}" fill="#cbd5e1" font-size="7.5" text-anchor="middle">${escH(p.label)}</text>`;});
  }
  // Nodes remain at true proportional chainage; labels alternate sides to keep POS 10 / FENI 15 legible.
  corridor.nodes.forEach((n,i)=>{const x=X(n.km),above=i%2===0,y=above?130:286;out+=`<line x1="${x.toFixed(1)}" y1="${above?164:226}" x2="${x.toFixed(1)}" y2="${above?145:267}" stroke="#64748b"/><circle cx="${x.toFixed(1)}" cy="195" r="5" fill="#0b1220" stroke="#cbd5e1" stroke-width="1.5"/><text x="${x.toFixed(1)}" y="${y}" fill="#e2e8f0" font-size="10" font-weight="700" text-anchor="middle">${escH(n.label)}</text><text x="${x.toFixed(1)}" y="${y+12}" fill="#64748b" font-size="8.5" text-anchor="middle">${fmt(n.km,1)} km</text>`;});
  // Only weighbridges used on this shift are shown. Position is estimated by snapping each
  // geofence centre to its nearest HAUL_ROAD_STA corridor marker.
  // Weighbridges used on the selected shift: short colour-coded dots on the road (no overlapping text),
  // with the details spelled out in a neat legend below the SVG. Busiest bridge = red = congestion point.
  // Weighbridges used on the shift: colour-coded dots with a short "WB13" label above (busiest = red).
  // Labels are staggered in height where bridges sit close together, so they don't overlap.
  {const leg=q('wb-road-legend');if(leg)leg.innerHTML='';
    const used=_wbPos?_wbPos.filter(w=>w.usedOnShift&&w.km<=length&&w.km>=0).sort((a,b)=>b.trucks-a.trucks):[];
    const WBCOL=['#f59e0b','#22c55e','#a78bfa','#38bdf8','#ec4899','#2dd4bf','#fb923c','#eab308','#f43f5e','#84cc16'],
      wbCol=i=>i===0?'#ef4444':WBCOL[(i-1)%WBCOL.length],wbNm=w=>'WB'+(w.wbNum||(w.name||'').replace(/\D/g,'')||'?');
    // Uniform, aligned markers: same-size dots on one line (busiest = red by colour, not size); labels
    // stagger over just 2 heights where bridges sit close together.
    const order=used.map((w,i)=>({w,i,x:X(w.km)})).sort((a,b)=>a.x-b.x);
    let lastX=-99,lvl=0;order.forEach(o=>{lvl=(o.x-lastX<30)?(lvl+1)%2:0;lastX=o.x;o.lvl=lvl;});
    order.forEach(o=>{const w=o.w,col=wbCol(o.i),x=o.x,ly=166-o.lvl*9;
      out+=`<line x1="${x.toFixed(1)}" y1="173" x2="${x.toFixed(1)}" y2="${(ly+2).toFixed(1)}" stroke="${col}" stroke-width=".7" opacity=".45"/><circle cx="${x.toFixed(1)}" cy="176" r="3.4" fill="${col}" stroke="#0b1220" stroke-width="1"><title>${escH(wbNm(w))} (${escH(w.name)}) · ~${fmt(w.km,1)}km · ${fmt(w.trucks)} weigh events${o.i===0?' · busiest / likely congestion point':''}</title></circle><text x="${x.toFixed(1)}" y="${ly.toFixed(1)}" fill="${col}" font-size="8" font-weight="700" text-anchor="middle">${escH(wbNm(w))}</text>`;});}
  out+=`<text x="980" y="24" fill="${pipeCol}" font-size="9" text-anchor="end">selected constraint · ${escH(band)} load</text>`;svg.innerHTML=out;
  _flowSim={routes,otherRoutes,hour:0,running:false,raf:null,last:0,avgSection,band,dbTrips:0,targetTrips:0,achievedTrips:0,corridorKm:length,roadLeft:left,roadRight:right,liveCongestion:0,liveDensity:0,shiftExplicit:routes.every(r=>r.shiftExplicit)};flowDeriveMode();renderFlowPlanner();
  // Default: GPS motion. Do not auto-call flowEstimateSpeeds (that overrides GPS).
  if(!_flowSpeedOverride) flowSeedGpsInputs();
  _flowSpeedsInitialised=true;
  evaluateFlowScenario();
  flowMapEnsure();
}

/* ── GPS polyline map (Leaflet) — primary visual for Tab 1 flow ─────────── */
let _flowMap=null,_flowMapRoad=null,_flowMapTrucks=null,_flowGeom=null,_flowChain=null,_flowMapMarkers={};

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
  const el=q('c3-flow-map');
  if(!el)return;
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
  if(!_flowMap){
    _flowMap=L.map(el,{scrollWheelZoom:false,attributionControl:true,preferCanvas:true});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:18,attribution:'&copy; OpenStreetMap',
    }).addTo(_flowMap);
    _flowMapRoad=L.layerGroup().addTo(_flowMap);
    _flowMapTrucks=L.layerGroup().addTo(_flowMap);
  }
  _flowMapRoad.clearLayers();
  _flowMapMarkers={};
  _flowMapTrucks.clearLayers();
  const corridor=(_D&&_D.corridor)||(_flowGeom.corridor)||{};
  const measured=corridor.measuredSpeeds||[];
  const posted=corridor.speedLimits||[];
  const bounds=[];
  // Paint GPS-coloured segments along the centreline.
  for(let i=1;i<_flowChain.length;i++){
    const a=_flowChain[i-1],b=_flowChain[i],mid=(a.km+b.km)/2;
    const seg=measured.find(s=>mid<=s.fromKm&&mid>=s.toKm);
    const lim=posted.find(z=>mid<=z.fromKm&&mid>=z.toKm);
    const v=seg&&seg.loadedKmh;
    const colour=flowMapGpsColour(v);
    const line=L.polyline([[a.lat,a.lng],[b.lat,b.lng]],{
      color:colour,weight:seg?6:3,opacity:seg?0.95:0.45,
    });
    const tip=['KM '+mid.toFixed(1)];
    if(seg)tip.push('GPS loaded '+(v==null?'—':fmt(v,1)+' km/h'),
      'empty '+(seg.emptyKmh==null?'—':fmt(seg.emptyKmh,1)+' km/h'));
    if(lim)tip.push('posted '+fmt(lim.limit)+' km/h');
    line.bindPopup(tip.map(escH).join('<br>'));
    line.addTo(_flowMapRoad);
    bounds.push([a.lat,a.lng],[b.lat,b.lng]);
  }
  (corridor.nodes||[]).forEach(n=>{
    const ll=flowMapLatLngAt(n.km);if(!ll)return;
    L.circleMarker(ll,{radius:5,color:'#e2e8f0',weight:1.5,fillColor:'#0b1220',fillOpacity:1})
      .bindTooltip(escH(n.label)+' · '+fmt(n.km,1)+' km',{permanent:false})
      .addTo(_flowMapRoad);
    bounds.push(ll);
  });
  if(bounds.length){
    _flowMap.fitBounds(bounds,{padding:[18,18]});
    setTimeout(()=>{try{_flowMap.invalidateSize();}catch(e){}},80);
  }
}
function flowMapSync(particles){
  if(!_flowMap||!_flowMapTrucks||!_flowChain||!_flowChain.length)return;
  // Cap markers for canvas performance; sample evenly when dense.
  const maxShow=100;
  let list=particles||[];
  if(list.length>maxShow){
    const step=list.length/maxShow;
    const sampled=[];
    for(let i=0;i<maxShow;i++)sampled.push(list[Math.floor(i*step)]);
    list=sampled;
  }
  const seen=new Set();
  list.forEach(p=>{
    const ll=flowMapLatLngAt(p.km);if(!ll)return;
    seen.add(p.id);
    let m=_flowMapMarkers[p.id];
    if(!m){
      m=L.circleMarker(ll,{
        radius:p.loaded?3.2:2.6,
        color:p.loaded?'#0b1220':'#94a3b8',
        weight:1,
        fillColor:p.col||'#38bdf8',
        fillOpacity:0.9,
      }).addTo(_flowMapTrucks);
      _flowMapMarkers[p.id]=m;
    }else{
      m.setLatLng(ll);
      m.setStyle({fillColor:p.col||'#38bdf8',radius:p.loaded?3.2:2.6});
    }
  });
  Object.keys(_flowMapMarkers).forEach(id=>{
    if(seen.has(id))return;
    try{_flowMapTrucks.removeLayer(_flowMapMarkers[id]);}catch(e){}
    delete _flowMapMarkers[id];
  });
}
