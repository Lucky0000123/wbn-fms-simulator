// congestion_charts.js — Congestion Model PREVIEW extras (saturation, cycle, loader sweep).
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
  }).catch(()=>{
    if(seq!==_congCurveSeq)return;
    _congNote('cong-curve-note','Backend not ready. Showing the local ceiling-scale estimate.');
  });
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
