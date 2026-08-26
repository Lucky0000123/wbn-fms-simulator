// congestion_charts.js — Congestion Model extras (saturation, cycle, loader sweep).
// Backend endpoints may not exist yet (parallel rebuild). Charts fall back to the
// local planTripsPerDT ceiling-scale estimate, or a "backend not ready" note.

let _congChartReady=false;
let _congCurveSeq=0;

function _congChartEl(id, note){
  const el=document.getElementById(id);
  if(!el)return null;
  // innerHTML guts a live ECharts instance while its root (el) stays connected,
  // so reuse guards keyed on getDom() never notice. Dispose before wiping.
  if(typeof echarts!=='undefined'){
    const c=echarts.getInstanceByDom(el);
    if(c){try{c.dispose();}catch(e){}}
  }
  if(el._congChart){try{el._congChart.dispose();}catch(e){} el._congChart=null;}
  el.innerHTML='<div class="muted" style="padding:16px;font-size:12px;border:1px dashed var(--line);border-radius:8px">'
    +(note||'Loading…')+'</div>';
  return el;
}
function _congPaint(id, option, emptyNote){
  const el=document.getElementById(id);
  if(!el)return;
  if(typeof paChart==='function'){paChart(id, option, emptyNote);return;}
  if(typeof echarts==='undefined'){
    el.innerHTML='<div class="muted" style="padding:14px;font-size:12px;border:1px dashed var(--line);border-radius:8px">'
      +(emptyNote||'Chart library unavailable (ECharts is loaded from a CDN).')+'</div>';
    return;
  }
  let c=el._congChart;
  if(c&&(c.isDisposed()||c.getDom()!==el||!c.getDom().isConnected)){
    try{c.dispose();}catch(e){}
    c=null;
  }
  if(!c){c=echarts.init(el);el._congChart=c;}
  c.setOption(option,true);
}
function _congAxis(){
  return {
    axisLine:{lineStyle:{color:'#30363d'}},
    axisLabel:{color:'#8b98a5',fontSize:10},
    splitLine:{lineStyle:{color:'#16233c'}},
  };
}
function _congFillRoutes(){
  const sel=document.getElementById('cong-curve-route');
  if(!sel)return '';
  const prev=sel.value;
  const keys=Object.keys(typeof _pathResp!=='undefined'&&_pathResp?_pathResp:{}).sort();
  if(!keys.length){
    if(!sel.options.length)sel.innerHTML='<option value="">No routes loaded</option>';
    return sel.value||'';
  }
  if(!_congChartReady||sel.options.length!==keys.length){
    const prefer=prev&&keys.indexOf(prev)>=0?prev:(keys.indexOf('TF>FENI KM0')>=0?'TF>FENI KM0':keys[0]);
    sel.innerHTML=keys.map(k=>'<option value="'+k.replace(/"/g,'&quot;')+'">'+k.replace('>',' → ')+'</option>').join('');
    sel.value=prefer;
    _congChartReady=true;
  }
  return sel.value||keys[0];
}
function _congInputs(){
  const route=_congFillRoutes();
  const ldEl=document.getElementById('cong-curve-loaders');
  const dtEl=document.getElementById('cong-curve-dt');
  const nLoaders=Math.max(1,parseInt(ldEl&&ldEl.value,10)||2);
  const nTrucks=Math.max(1,parseInt(dtEl&&dtEl.value,10)||80);
  const lv=document.getElementById('cong-curve-loaders-v');
  const dv=document.getElementById('cong-curve-dt-v');
  if(lv)lv.textContent=String(nLoaders);
  if(dv)dv.textContent=String(nTrucks);
  return {route,nLoaders,nTrucks};
}
function _congLocalCurve(route, nLoaders, maxTrucks){
  const pts=[];
  if(typeof planTripsPerDT!=='function')return pts;
  const c=typeof planContractor==='function'?planContractor():null;
  const step=Math.max(1,Math.round((maxTrucks||600)/80));
  for(let dt=1;dt<=(maxTrucks||600);dt+=step){
    const e=planTripsPerDT(route,dt,0,c,{nLoaders:nLoaders});
    if(!e)continue;
    pts.push({n_trucks:dt,trips_per_dt:+e.daily.toFixed(4),satFactor:e.satFactor,
      bottleneck:e.bottleneck||'ok',legacy:true});
  }
  return pts;
}
function _congLocalSweep(route, nTrucks){
  const pts=[];
  if(typeof planTripsPerDT!=='function')return pts;
  const c=typeof planContractor==='function'?planContractor():null;
  for(let n=1;n<=12;n++){
    const e=planTripsPerDT(route,nTrucks,0,c,{nLoaders:n});
    if(!e)continue;
    pts.push({n_loaders:n,trips_per_dt:+e.daily.toFixed(4),bottleneck:e.bottleneck||'ok'});
  }
  return pts;
}
function _congUnavailable(d){
  return !d||d.unavailable||d.status===404||d.status===501||d.ok===false&&!d.points&&!d.curve&&!d.components;
}
function _congNote(id, text){
  const el=document.getElementById(id);
  if(el)el.textContent=text||'';
}

function renderCongCurve(){
  const inp=_congInputs();
  if(!inp.route){
    _congChartEl('cong-curve-chart','Load Capability first so route history is available.');
    _congChartEl('cong-wmtdt-chart','Load Capability first so route history is available.');
    _congChartEl('cong-wmtday-chart','Load Capability first so route history is available.');
    _congChartEl('cong-breakdown-chart','Load Capability first so route history is available.');
    _congChartEl('cong-loader-chart','Load Capability first so route history is available.');
    return;
  }
  const seq=++_congCurveSeq;
  const local=_congLocalCurve(inp.route,inp.nLoaders,600);
  const knee=local.find(p=>p.satFactor<0.999);
  const kneeEl=document.getElementById('cong-curve-knee');
  if(kneeEl)kneeEl.textContent=knee?('Ceiling binds near '+knee.n_trucks+' DT'):'Linear in this range';

  const axis=_congAxis();
  const localLine=local.map(p=>[p.n_trucks,p.trips_per_dt]);
  _congPaint('cong-curve-chart',{
    backgroundColor:'transparent',
    tooltip:{trigger:'axis'},
    legend:{data:['Local ceiling-scale','Hybrid model'],textStyle:{color:'#8b98a5',fontSize:11},top:0},
    grid:{left:48,right:16,top:28,bottom:36},
    xAxis:Object.assign({type:'value',name:'DT',nameLocation:'middle',nameGap:22},axis),
    yAxis:Object.assign({type:'value',name:'trips/DT/day',nameLocation:'middle',nameGap:36},axis),
    series:[
      {name:'Local ceiling-scale',type:'line',showSymbol:false,data:localLine,
        lineStyle:{type:'dashed',width:1.8,color:'#94a3b8'}},
    ],
  },'No local path-response for this route.');
  _congNote('cong-curve-note','Dashed line = local divide-at-ceiling estimate, scaled by loaders / historical loaders. Solid hybrid line appears when /api/congestion_curve is available.');

  renderCongBreakdown(inp.route,inp.nTrucks,inp.nLoaders);
  renderCongLoaderSweep(inp.route,inp.nTrucks);

  if(typeof loadCongestionCurve!=='function')return;
  loadCongestionCurve(inp.route,inp.nLoaders,600).then(d=>{
    if(seq!==_congCurveSeq)return;
    if(_congUnavailable(d)){
      _congNote('cong-curve-note','Backend not ready (/api/congestion_curve). Showing the local ceiling-scale estimate — trips/DT stays flat until the demonstrated day cap, then extra trucks share that cap. Loader count scales the cap.');
      _congChartEl('cong-wmtdt-chart','Backend not ready (/api/congestion_curve) — tonnage curves need the hybrid sweep.');
      _congChartEl('cong-wmtday-chart','Backend not ready (/api/congestion_curve) — tonnage curves need the hybrid sweep.');
      return;
    }
    const pts=d.points||d.curve||d.hybrid||[];
    const band=d.p10&&d.p90?d.points||[]:[];
    const hybrid=pts.map(p=>[p.n_trucks||p.dt,p.trips_per_dt||p.tripsPerDt||p.y]);
    const p10=(d.p10||band.map(p=>[p.n_trucks||p.dt,p.p10])).filter(Boolean);
    const p90=(d.p90||band.map(p=>[p.n_trucks||p.dt,p.p90])).filter(Boolean);
    const kneeX=d.knee_dt||d.knee||d.n_star||null;
    const series=[
      {name:'Local ceiling-scale',type:'line',showSymbol:false,data:localLine,
        lineStyle:{type:'dashed',width:1.6,color:'#94a3b8'}},
      {name:'Hybrid model',type:'line',showSymbol:false,data:hybrid,
        lineStyle:{width:2.4,color:'#38bdf8'}},
    ];
    if(p10.length&&p90.length){
      series.splice(1,0,{name:'P10–P90',type:'line',showSymbol:false,data:p90,
        lineStyle:{opacity:0},areaStyle:{color:'rgba(56,189,248,.12)'},stack:'band'},
        {name:'P10–P90',type:'line',showSymbol:false,data:p10,
          lineStyle:{opacity:0},areaStyle:{color:'rgba(56,189,248,.12)'},stack:'band'});
    }
    if(d.obs||d.observations){
      const obs=(d.obs||d.observations).map(o=>[o.n_trucks||o.dt,o.trips_per_dt||o.y]);
      series.push({name:'History',type:'scatter',data:obs,symbolSize:6,itemStyle:{color:'#93c5fd',opacity:.55}});
    }
    _congPaint('cong-curve-chart',{
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{data:['Local ceiling-scale','Hybrid model','History'],textStyle:{color:'#8b98a5',fontSize:11},top:0},
      grid:{left:48,right:16,top:28,bottom:36},
      xAxis:Object.assign({type:'value',name:'DT',nameLocation:'middle',nameGap:22},axis),
      yAxis:Object.assign({type:'value',name:'trips/DT/day',nameLocation:'middle',nameGap:36},axis),
      series:series.concat(kneeX?[{type:'line',markLine:{silent:true,symbol:'none',
        lineStyle:{type:'dashed',color:'#f59e0b'},label:{formatter:'knee',color:'#f59e0b',fontSize:10},
        data:[{xAxis:kneeX}]}}]:[]),
    });
    _congNote('cong-curve-note',d.note||'Solid = hybrid physics + queueing + BPR. Dashed = previous divide-at-ceiling model. Shaded = P10–P90 when the API sends it.');
    if(kneeEl&&kneeX)kneeEl.textContent='Knee at '+Math.round(kneeX)+' DT';
    renderCongWmtCurves();
  }).catch(()=>{
    if(seq!==_congCurveSeq)return;
    _congNote('cong-curve-note','Backend not ready. Showing the local ceiling-scale estimate.');
  });
}

// ── whole-plan WMT saturation curves (owner, 2026-08-26 v2) ──────────────────
// "Not per route — take the average of the history Jan–Jun as the threshold,
// and show how our model's whole-plan curve moves as DT are added."
// /api/plan_saturation sweeps TOTAL fleet DT, spreads it in the measured
// Jan–Jun route mix, prices every route under the shared segment fleet, and
// returns two curves plus the measured whole-fleet baseline:
//   wmt_per_dt_day  — model average tonnes per truck per day
//   wmt_day         — model total tonnes per day
// The dashed threshold = what the fleet ACTUALLY averaged Jan–Jun (189.3
// t/DT/day at ~609 DT/day). Fetched once and cached: the sweep does not
// depend on the per-route controls above.
let _planSatCache=null;
function renderCongWmtCurves(){
  if(_planSatCache){_paintPlanSat(_planSatCache);return;}
  _congChartEl('cong-wmtdt-chart','Computing whole-plan sweep…');
  _congChartEl('cong-wmtday-chart','Computing whole-plan sweep…');
  fetch('/api/plan_saturation?max_dt=2600').then(r=>r.json()).then(d=>{
    if(!d||d.ok===false||!(d.curve||[]).length){
      const why=(d&&d.error)||'Backend not ready (/api/plan_saturation).';
      _congChartEl('cong-wmtdt-chart',why);
      _congChartEl('cong-wmtday-chart',why);
      return;
    }
    _planSatCache=d;
    _paintPlanSat(d);
  }).catch(()=>{
    _congChartEl('cong-wmtdt-chart','Backend not ready (/api/plan_saturation).');
    _congChartEl('cong-wmtday-chart','Backend not ready (/api/plan_saturation).');
  });
}
function _paintPlanSat(d){
  const axis=_congAxis();
  const base=d.baseline||{};
  const perDt=d.curve.map(p=>[p.total_dt,p.wmt_per_dt_day]);
  const perDay=d.curve.map(p=>[p.total_dt,p.wmt_day]);
  const histDt=base.avg_fleet_dt||null;
  const histPerDt=base.wmt_per_dt_day||null;
  const histWmt=base.avg_wmt_day||null;
  const histMark=(y,label)=>({type:'line',markLine:{silent:true,symbol:'none',
    lineStyle:{type:'dashed',color:'#f59e0b',width:1.6},
    label:{formatter:label,color:'#f59e0b',fontSize:10,position:'insideEndTop'},
    data:[{yAxis:y}]}});
  const fleetMark=histDt?{type:'line',markLine:{silent:true,symbol:'none',
    lineStyle:{type:'dashed',color:'#64748b'},
    label:{formatter:'Jan–Jun avg fleet '+Math.round(histDt)+' DT',color:'#94a3b8',fontSize:10},
    data:[{xAxis:histDt}]}}:null;
  _congPaint('cong-wmtdt-chart',{
    backgroundColor:'transparent',
    tooltip:{trigger:'axis'},
    grid:{left:56,right:16,top:14,bottom:36},
    xAxis:Object.assign({type:'value',name:'total fleet DT',nameLocation:'middle',nameGap:22},axis),
    yAxis:Object.assign({type:'value',name:'WMT/day per DT',nameLocation:'middle',nameGap:44,
      min:v=>Math.floor(Math.min(v.min,histPerDt?histPerDt-10:v.min)),
      max:v=>Math.ceil(Math.max(v.max,histPerDt?histPerDt+5:v.max))},axis),
    series:[{name:'Model (whole plan)',type:'line',showSymbol:false,data:perDt,
      lineStyle:{width:2.4,color:'#34d399'},
      areaStyle:{color:'rgba(52,211,153,.07)'}}]
      .concat(histPerDt?[histMark(histPerDt,'Jan–Jun measured avg '+histPerDt+' t/DT')]:[])
      .concat(fleetMark?[fleetMark]:[]),
  });
  _congPaint('cong-wmtday-chart',{
    backgroundColor:'transparent',
    tooltip:{trigger:'axis'},
    grid:{left:72,right:16,top:14,bottom:36},
    xAxis:Object.assign({type:'value',name:'total fleet DT',nameLocation:'middle',nameGap:22},axis),
    yAxis:Object.assign({type:'value',name:'WMT/day (all routes)',nameLocation:'middle',nameGap:56},axis),
    series:[{name:'Model (whole plan)',type:'line',showSymbol:false,data:perDay,
      lineStyle:{width:2.4,color:'#818cf8'},
      areaStyle:{color:'rgba(129,140,248,.07)'}}]
      .concat(histWmt?[histMark(histWmt,'Jan–Jun measured avg '+Math.round(histWmt/1000)+' kt/day')]:[])
      .concat(fleetMark?[fleetMark]:[]),
  });
  const w=(base.window||[]).join(' → ');
  _congNote('cong-wmtdt-note','Model: total fleet spread in the measured Jan–Jun route mix ('
    +d.mix_routes+' routes, shared-road pricing, loaders at calibrated faces). Dashed = the fleet\'s '
    +'measured average over '+w+' ('+histPerDt+' t/DT/day at ~'+Math.round(histDt)+' DT). '
    +'The curve falls as added DT queue at the same loading faces and share the same road.');
  _congNote('cong-wmtday-note','Total daily tonnage as the whole fleet grows, same mix and pricing. '
    +'Dashed = measured Jan–Jun average ('+Math.round(histWmt/1000)+' kt/day). The flattening slope is the '
    +'marginal value of each added truck across the whole plan.');
}

function renderCongBreakdown(route, nTrucks, nLoaders){
  const empty='Backend not ready (/api/congestion_model). Cycle components (road, queue, load, dump) are not computed locally.';
  _congChartEl('cong-breakdown-chart',empty);
  if(typeof loadCongestionModel!=='function')return;
  loadCongestionModel(route,nTrucks,nLoaders).then(d=>{
    if(_congUnavailable(d)){
      _congChartEl('cong-breakdown-chart',empty);
      return;
    }
    const c=d.components||d.cycle||d;
    // /api/congestion_model sends t_free_road / bpr_penalty_minutes / … ;
    // the *_min names never shipped but are kept in case an older payload did.
    const parts=[
      {name:'Road (free flow)',v:c.t_free_road||c.road_min||c.travel_min},
      {name:'Road (BPR penalty)',v:c.bpr_penalty_minutes||c.bpr_min||c.bprMin},
      {name:'Loader queue',v:c.queue_wait_minutes||c.queue_min||c.queueMin||c.wait_min},
      {name:'Loading',v:c.t_load||c.load_min||c.loadMin||c.loading_min},
      {name:'Dump / spot',v:((c.t_dump||0)+(c.t_spot||0))||c.dump_min||c.dumpMin||c.spot_min},
      {name:'Bunching',v:c.bunching_penalty_minutes||c.bunching_min||c.bunchingMin},
      {name:'Overhead (breaks/dispatch, per trip)',v:c.overhead_per_trip_minutes},
    ].filter(p=>Number.isFinite(p.v)&&p.v>0);
    if(!parts.length){
      _congChartEl('cong-breakdown-chart',empty);
      return;
    }
    const axis=_congAxis();
    _congPaint('cong-breakdown-chart',{
      backgroundColor:'transparent',
      tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
      grid:{left:88,right:16,top:12,bottom:24},
      xAxis:Object.assign({type:'value',name:'min'},axis),
      yAxis:Object.assign({type:'category',data:[route.replace('>',' → ')]},axis),
      series:parts.map((p,i)=>({name:p.name,type:'bar',stack:'cycle',barWidth:28,
        data:[+Number(p.v).toFixed(1)],
        itemStyle:{color:['#38bdf8','#f59e0b','#22c55e','#a78bfa','#f472b6','#eab308','#64748b'][i%7]}})),
      legend:{data:parts.map(p=>p.name),textStyle:{color:'#8b98a5',fontSize:10},bottom:0},
    });
  }).catch(()=>_congChartEl('cong-breakdown-chart',empty));
}

function renderCongLoaderSweep(route, nTrucks){
  const local=_congLocalSweep(route,nTrucks);
  const axis=_congAxis();
  const paintLocal=function(note){
    _congPaint('cong-loader-chart',{
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      grid:{left:48,right:16,top:16,bottom:36},
      xAxis:Object.assign({type:'value',name:'Loaders',min:1,max:12,nameLocation:'middle',nameGap:22},axis),
      yAxis:Object.assign({type:'value',name:'trips/DT/day',nameLocation:'middle',nameGap:36},axis),
      series:[{name:'Local ceiling-scale',type:'line',showSymbol:true,symbolSize:7,
        data:local.map(p=>[p.n_loaders,p.trips_per_dt]),
        lineStyle:{type:'dashed',width:1.8,color:'#94a3b8'},itemStyle:{color:'#94a3b8'}}],
    },'No local path-response for this route.');
    _congNote('cong-loader-note',note);
  };
  paintLocal('Dashed = local cap × (loaders / historical loaders). If this stays flat after 2–3 loaders, the path-day ceiling — not the shovel — is binding.');

  if(typeof loadCongestionCompare!=='function')return;
  loadCongestionCompare(route,nTrucks).then(d=>{
    if(_congUnavailable(d)){
      _congNote('cong-loader-note','Backend not ready (/api/congestion_compare). '+
        'Dashed line is the local ceiling scaled by loader count.');
      return;
    }
    const pts=d.points||d.sweep||d.curve||[];
    const hybrid=pts.map(p=>[p.n_loaders||p.loaders,p.trips_per_dt||p.tripsPerDt||p.y]);
    _congPaint('cong-loader-chart',{
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{data:['Local ceiling-scale','Hybrid model'],textStyle:{color:'#8b98a5',fontSize:11},top:0},
      grid:{left:48,right:16,top:28,bottom:36},
      xAxis:Object.assign({type:'value',name:'Loaders',min:1,max:12,nameLocation:'middle',nameGap:22},axis),
      yAxis:Object.assign({type:'value',name:'trips/DT/day',nameLocation:'middle',nameGap:36},axis),
      series:[
        {name:'Local ceiling-scale',type:'line',showSymbol:true,symbolSize:6,
          data:local.map(p=>[p.n_loaders,p.trips_per_dt]),
          lineStyle:{type:'dashed',width:1.6,color:'#94a3b8'}},
        {name:'Hybrid model',type:'line',showSymbol:true,symbolSize:7,
          data:hybrid,lineStyle:{width:2.4,color:'#f59e0b'},itemStyle:{color:'#f59e0b'}},
      ],
    });
    const last=pts[pts.length-1], mid=pts[Math.max(0,pts.length-3)];
    const flat=last&&mid&&Number(last.trips_per_dt||last.y)>0
      && Math.abs(Number(last.trips_per_dt||last.y)-Number(mid.trips_per_dt||mid.y))/Number(mid.trips_per_dt||mid.y)<0.02;
    _congNote('cong-loader-note', flat
      ? 'Curve has flattened — bottleneck has shifted off the loader (road or path-day cap). Adding more loaders will not lift trips/DT; a second route is needed.'
      : (d.note||'If the curve flattens, the bottleneck has shifted from loader to road — adding more loaders will not help.'));
  }).catch(()=>{
    _congNote('cong-loader-note','Backend not ready. Dashed line is the local ceiling scaled by loader count.');
  });
}

window.addEventListener('resize',function(){
  ['cong-curve-chart','cong-breakdown-chart','cong-loader-chart'].forEach(id=>{
    const el=document.getElementById(id);
    if(el&&el._congChart){try{el._congChart.resize();}catch(e){}}
  });
});

// Section packing calculator (Congestion tab, after the model charts).
// Same geometry as congestion/speed_limits.py: trucks/hr = speed_kmh × 1000 / gap_m,
// one loaded lane. Live model following distance is FOLLOWING_DISTANCE_M (50 m
// from 2026-08-25); /api/road_segments hydrates so this table cannot drift.
let _CONG_FOLLOW_M=50;
const _CONG_PACK = {
  S1:{id:'S1',label:'S1 · TF–KR',span:'KM 67.8–39.0',km:28.8,postedKmh:30,postedCap:null,
      gpsKmh:16.0,gpsPeakKmh:15.3,gpsGapM:410,gpsFlow:66},
  S2:{id:'S2',label:'S2 · KR–POS 12',span:'KM 39.0–27.0',km:12.0,postedKmh:30,postedCap:null,
      gpsKmh:16.2,gpsPeakKmh:15.7,gpsGapM:240,gpsFlow:84},
  S3:{id:'S3',label:'S3 · POS 12–KM15',span:'KM 27.0–15.0',km:12.0,postedKmh:30,postedCap:null,
      gpsKmh:16.2,gpsPeakKmh:13.7,gpsGapM:340,gpsFlow:74},
  S4:{id:'S4',label:'S4 · KM15–coast',span:'KM 15.0–0.0',km:15.0,postedKmh:20,postedCap:null,
      gpsKmh:16.2,gpsPeakKmh:15.9,gpsGapM:340,gpsFlow:83},
};
function _congFollow(){return (_CONG_FOLLOW_M>0)?_CONG_FOLLOW_M:50;}
function _congPostedCap(s){
  if(Number.isFinite(s.postedCap)&&s.postedCap>0)return s.postedCap;
  return s.postedKmh*1000/_congFollow();
}
function _congVcTone(vc){
  if(!Number.isFinite(vc)||vc<0)return {cls:'',lab:'—',cell:''};
  // Official 50 m packing is v/c = 1 → YELLOW (at the limit).
  // RED is only OVER that packing — the "more congestion" the table exists to flag.
  if(vc>1)return {cls:'overloaded',lab:'RED',cell:'tone-bad'};
  if(vc>=0.7)return {cls:'saturated',lab:'YELLOW',cell:'tone-warn'};
  return {cls:'free',lab:'GREEN',cell:'tone-ok'};
}
function _congTag(vc){
  const t=_congVcTone(vc);
  if(!t.cls)return '—';
  return '<span class="plan-cong-badge '+t.cls+'">'+t.lab+'</span>';
}
function _congPackN(n,d){
  d=(d==null)?0:d;
  const x=Number(n);
  if(!Number.isFinite(x))return '—';
  return x.toLocaleString('en-GB',{maximumFractionDigits:d,minimumFractionDigits:d});
}
function _congPackSeg(){
  const sel=document.getElementById('cong-pack-seg');
  if(sel&&!sel.options.length){
    sel.innerHTML=Object.keys(_CONG_PACK).map(k=>{
      const s=_CONG_PACK[k];
      return '<option value="'+s.id+'">'+s.label+' · '+s.km+' km</option>';
    }).join('');
    sel.value='S3';
  }
  return _CONG_PACK[(sel&&sel.value)||'S3']||_CONG_PACK.S3;
}
function _congPackNums(s,spd,gap){
  const follow=_congFollow();
  const cap=_congPostedCap(s);
  const perKm=1000/gap;
  return {
    follow:follow,
    cap:cap,
    perKm:perKm,
    onSec:s.km*perKm,
    perHr:spd*1000/gap,
    postedPerKm:1000/follow,
    postedOnSec:s.km*(1000/follow),
    gpsPerKm:1000/s.gpsGapM,
    gpsOnSec:s.km*(1000/s.gpsGapM),
    gpsAtFollow:s.gpsKmh*1000/follow,
  };
}
function renderCongPack(){
  const root=document.getElementById('cong-pack');
  if(!root)return;
  const s=_congPackSeg();
  const spdEl=document.getElementById('cong-pack-spd');
  const gapEl=document.getElementById('cong-pack-gap');
  const follow=_congFollow();
  if(spdEl&&!spdEl.dataset.touched) spdEl.value=String(s.postedKmh);
  const liveTh=document.getElementById('cong-pack-live-th');
  if(liveTh) liveTh.textContent='Posted (live '+_congPackN(follow,0)+' m)';
  const spd=Math.max(1,Number(spdEl&&spdEl.value)||s.postedKmh);
  const gap=Math.max(5,Number(gapEl&&gapEl.value)||follow);
  const spdV=document.getElementById('cong-pack-spd-v');
  const gapV=document.getElementById('cong-pack-gap-v');
  if(spdV)spdV.textContent=_congPackN(spd,0);
  if(gapV)gapV.textContent=_congPackN(gap,0);
  const n=_congPackNums(s,spd,gap);
  const playVc=n.perHr/n.cap;
  const gpsVc=s.gpsFlow/n.cap;
  const playTone=_congVcTone(playVc);
  const gpsTone=_congVcTone(gpsVc);
  const kpis=document.getElementById('cong-pack-kpis');
  if(kpis)kpis.innerHTML=[
    ['Trucks in 1 km',_congPackN(n.perKm,1),'', 'gap '+_congPackN(gap,0)+' m'],
    ['Trucks on this section',_congPackN(n.onSec,0),'on '+s.id, s.span+' · '+s.km+' km · loaded lane'],
    ['Can pass per hour',_congPackN(n.perHr,0),'trucks/hr · one loaded lane', 'live '+_congPackN(n.cap,0)+'/hr at '+_congPackN(follow,0)+' m — not both sides'],
  ].map(c=>'<div class="effkpi"><div class="v">'+c[1]+(c[2]?' <span class="u">'+c[2]+'</span>':'')+'</div><div class="l">'+c[0]+' · '+c[3]+'</div></div>').join('');

  const kmEl=document.getElementById('cong-pack-km');
  if(kmEl){
    const W=640,H=72,pad=28,iw=W-pad*2;
    const count=Math.max(1,Math.round(n.perKm));
    const truckFill=playTone.cls==='overloaded'?'#ef4444':(playTone.cls==='saturated'?'#facc15':'#22c55e');
    let svg='<rect x="0" y="0" width="'+W+'" height="'+H+'" fill="transparent"/>';
    svg+='<line x1="'+pad+'" y1="36" x2="'+(W-pad)+'" y2="36" stroke="#30363d" stroke-width="10" stroke-linecap="round"/>';
    svg+='<text x="'+pad+'" y="18" fill="#8b98a5" font-size="10">0 km</text>';
    svg+='<text x="'+(W-pad)+'" y="18" fill="#8b98a5" font-size="10" text-anchor="end">1 km</text>';
    const drawN=Math.min(count,24);
    const step=iw/Math.max(1,drawN);
    for(let i=0;i<drawN;i++){
      const x=pad+step*(i+0.5);
      svg+='<rect x="'+(x-7)+'" y="28" width="14" height="16" rx="3" fill="'+truckFill+'" opacity="0.9"/>';
    }
    const more=count>24?(' · showing 24 of '+count):'';
    svg+='<text x="'+(W/2)+'" y="64" fill="#e6edf3" font-size="11" text-anchor="middle" font-weight="600">'
      +count+' trucks / km'+more+'</text>';
    kmEl.innerHTML=svg;
  }

  const flEl=document.getElementById('cong-pack-flow');
  if(flEl){
    const W=640,H=160,pl=46,pr=16,pt=14,pb=28,iw=W-pl-pr,ih=H-pt-pb;
    const g0=20,g1=400;
    const capY=n.cap;
    const maxY=Math.max(capY,n.perHr,n.gpsAtFollow)*1.15;
    const X=g=>pl+iw*(g-g0)/(g1-g0);
    const Y=v=>pt+ih*(1-v/maxY);
    let svg='';
    for(let i=0;i<=4;i++){
      const v=maxY*(1-i/4), yy=pt+ih*i/4;
      svg+='<line x1="'+pl+'" y1="'+yy.toFixed(1)+'" x2="'+(W-pr)+'" y2="'+yy.toFixed(1)+'" stroke="#16233c"/>';
      svg+='<text x="'+(pl-6)+'" y="'+(yy+3).toFixed(1)+'" fill="#64748b" font-size="10" text-anchor="end">'+_congPackN(v,0)+'</text>';
    }
    let pts=[];
    for(let g=g0;g<=g1;g+=4) pts.push(X(g).toFixed(1)+','+Y(spd*1000/g).toFixed(1));
    svg+='<polyline points="'+pts.join(' ')+'" fill="none" stroke="#f59e0b" stroke-width="2"/>';
    const xm=X(Math.min(g1,Math.max(g0,follow)));
    svg+='<line x1="'+xm.toFixed(1)+'" y1="'+pt+'" x2="'+xm.toFixed(1)+'" y2="'+(pt+ih)+'" stroke="#64748b" stroke-dasharray="3 3"/>';
    svg+='<text x="'+xm.toFixed(1)+'" y="'+(pt+10)+'" fill="#94a3b8" font-size="9" text-anchor="middle">'+_congPackN(follow,0)+' m</text>';
    svg+='<line x1="'+pl+'" y1="'+Y(capY).toFixed(1)+'" x2="'+(W-pr)+'" y2="'+Y(capY).toFixed(1)+'" stroke="#22c55e" stroke-dasharray="4 3" opacity="0.8"/>';
    svg+='<text x="'+(W-pr)+'" y="'+(Y(capY)-4).toFixed(1)+'" fill="#22c55e" font-size="9" text-anchor="end">live '+_congPackN(capY,0)+'/hr</text>';
    svg+='<circle cx="'+X(Math.min(g1,Math.max(g0,gap))).toFixed(1)+'" cy="'+Y(n.perHr).toFixed(1)+'" r="5" fill="#f59e0b" stroke="#111" stroke-width="1"/>';
    svg+='<text x="'+(W/2)+'" y="'+(H-6)+'" fill="#94a3b8" font-size="10" text-anchor="middle">following distance (m) →</text>';
    flEl.innerHTML=svg;
  }

  const tb=document.getElementById('cong-pack-tbl');
  if(tb){
    const rows=[
      {label:'Speed', posted:_congPackN(s.postedKmh,0)+' km/h', play:_congPackN(spd,1)+' km/h', gps:_congPackN(s.gpsPeakKmh,1)+' km/h', tag:''},
      {label:'Gap between trucks', posted:_congPackN(follow,0)+' m', play:_congPackN(gap,0)+' m', gps:_congPackN(s.gpsGapM,0)+' m', tag:''},
      {label:'Trucks in 1 km', posted:_congPackN(n.postedPerKm,1), play:_congPackN(n.perKm,1), gps:_congPackN(n.gpsPerKm,1), tag:''},
      {label:'Trucks on this section', posted:_congPackN(n.postedOnSec,0), play:_congPackN(n.onSec,0), gps:_congPackN(n.gpsOnSec,0), tag:''},
      {label:'Through the section / hour (one loaded lane)', posted:_congPackN(n.cap,0)+' (live '+_congPackN(follow,0)+' m)',
        play:_congPackN(n.perHr,0)+' (play)', gps:_congPackN(s.gpsFlow,0)+' (flow seen)',
        playCell:playTone.cell, gpsCell:gpsTone.cell,
        tag:_congTag(playVc)+' <span class="muted">play</span> · '+_congTag(gpsVc)+' <span class="muted">GPS</span>'},
    ];
    tb.innerHTML=rows.map(r=>'<tr><td>'+r.label+'</td>'
      +'<td class="r">'+r.posted+'</td>'
      +'<td class="r you '+(r.playCell||'')+'">'+r.play+'</td>'
      +'<td class="r '+(r.gpsCell||'')+'">'+r.gps+'</td>'
      +'<td>'+(r.tag||'')+'</td></tr>').join('');
  }
  const note=document.getElementById('cong-pack-note');
  if(note){
    let extra=' Live model uses '+_congPackN(follow,0)+' m between DTs on ONE loaded lane ('+_congPackN(n.cap,0)+' trucks/hr). Both carriageways would be ~2× and is not what Plan uses.';
    extra+=' GREEN = v/c &lt; 0.7 · YELLOW = 0.7–1.0 (at the '+_congPackN(follow,0)+' m packing) · RED = over capacity.';
    if(gap<follow) extra+=' Your play gap is tighter than the live '+_congPackN(follow,0)+' m, so throughput is higher and the tag moves toward RED.';
    note.innerHTML=s.label+' · '+s.span+' · ONE loaded lane (empty is the other carriageway) · formula trucks/hr = speed × 1000 / gap.'
      +' Play is '+_congPackN(100*playVc,0)+'% of live capacity.'
      +extra+' Plan Road crowding uses this same loaded-lane packing.';
  }
}
function _congPackHydrate(j){
  if(!j||!j.ok)return;
  const f=j.road&&j.road.following_distance_m;
  if(f>0)_CONG_FOLLOW_M=f;
  (j.segments||[]).forEach(seg=>{
    const s=_CONG_PACK[seg.id];
    if(!s)return;
    if(seg.cap_hr>0)s.postedCap=seg.cap_hr;
    const pmin=seg.speeds&&seg.speeds.loaded&&seg.speeds.loaded.min;
    if(pmin>0)s.postedKmh=pmin;
  });
  const gapEl=document.getElementById('cong-pack-gap');
  if(gapEl&&!gapEl.dataset.touched){
    gapEl.value=String(Math.round(_CONG_FOLLOW_M));
  }
  renderCongPack();
}
document.addEventListener('DOMContentLoaded',function(){
  if(!document.getElementById('cong-pack-seg'))return;
  const gapEl=document.getElementById('cong-pack-gap');
  if(gapEl)gapEl.addEventListener('input',function(){gapEl.dataset.touched='1';});
  const spdEl=document.getElementById('cong-pack-spd');
  if(spdEl)spdEl.addEventListener('input',function(){spdEl.dataset.touched='1';});
  renderCongPack();
  fetch('/api/road_segments').then(function(r){return r.json();}).then(_congPackHydrate).catch(function(){});
});
