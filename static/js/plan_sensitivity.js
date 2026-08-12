// ── B · Fleet sensitivity — nonlinear DT sweep per plan ──────────────────────
// Owner (2026-08-12): after Run scenario, a smooth ECharts line chart showing
// how tonnage (WMT) and trips/DT bend as the fleet grows, one colour per plan;
// a side panel lists the plans (click = isolate, eye = hide) and a granularity
// toggle rescales to per-hour / per-shift / per-day.
//
// ENGINE CONSISTENCY: every point is computed by the SAME planTripsPerDT()
// path model that prices the plan table and the estimate strip (measured
// decline, 30% floor, WB throughput ceiling at the CURRENT bridge
// assignments, rain, shared-section and other-traffic drags). No second
// model, no backend duplication — sweeping 1..cap in the browser is
// microseconds per point because the model is a closed formula.
//
// Sweep cap per plan: 2× the path's highest observed DT (the same envelope
// the guards use), max 150; no history → 100. Road-only rows have no WMT —
// they contribute a trips/DT curve only.
(function(){
  const PALETTE=['#4e79a7','#f28e2b','#59a14f','#e15759','#b07aa1','#76b7b2','#edc948','#ff9da7'];
  let _sel=null;            // isolated plan id, or null = all
  let _hidden={};           // id → true (eye toggle)
  let _gran='shift';        // hour | shift | day
  // Y-metric. 'output' = tonnage + trips/DT (the original dual axis).
  // 'efficiency' = what fraction of this path's own free rate each truck still
  // gets, 0-100%, all plans on ONE axis because the ratio is dimensionless.
  //
  // WHY A RATIO IS SAFE HERE ONLY IF THE RATE IS SHOWN WITH IT: efficiency is
  // measured against each path's OWN baseline, so it does not rank paths. KM15
  // at 41% still moves 1.06 trips/truck/day while KM0 at 100% moves 2.19. A
  // planner optimising the percentage would pick the wrong haul. Every place
  // efficiency is displayed also carries the absolute trips/DT -- see the
  // capacity-card defect in AGENTS.md for what happens when a ratio is left to
  // be read as a verdict.
  let _metric='output';     // output | efficiency
  // No local ECharts instance: paChart() owns the registry (_paCharts) and
  // paResizeAll() owns resize, so a second cache here could only drift from it.
  let _curves=[];           // [{id,label,color,curve:[{dt,tripsPerDt,trips,wmt}],currentDt,foreign,capDt}]

  const el=id=>document.getElementById(id);
  const esc=x=>String(x==null?'':x).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function granFactor(){
    const hours=Math.max(1,parseFloat((el('plan-hours')||{}).value)||12);
    if(_gran==='hour')return {f:1/hours,unit:'/h'};
    if(_gran==='day'){
      const shiftsPerDay=Math.max(1,Math.round(24/hours));
      return {f:shiftsPerDay,unit:'/day'};
    }
    return {f:1,unit:'/shift'};
  }

  // Build the curves from the live holding plan via the real path model.
  function buildCurves(){
    if(typeof planDraftEntries!=='function'||typeof planTripsPerDT!=='function')return [];
    const rain=Math.max(0,parseFloat((el('plan-rain')||{}).value)||0);
    const out=[];
    planDraftEntries().forEach((r,i)=>{
      const m=(typeof _pathResp!=='undefined'&&_pathResp[r.key])||{};
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
      const isForeign=!!r.foreign;
      // Sweep must COVER the assigned DT (owner: "not limited to 2× only") —
      // extend past the envelope so the planner sees where their fleet sits.
      const envMax=typeof planDtEnvelope==='function'?planDtEnvelope(m):(Number.isFinite(m.dtMax)?Math.round(m.dtMax):null);
      const histCap=envMax!=null?Math.max(20,Math.round(envMax*2)):100;
      const cap=Math.min(2000,Math.max(histCap,Math.ceil((r.dt||1)*1.25)));
      const step=cap<=40?2:(cap<=100?4:(cap<=300?8:Math.ceil(cap/40)));
      const curve=[];
      for(let dt=1;dt<=cap;dt+=step){
        let tpd=null,trips=null,wmt=null,eff=null,sat=null,wb=null,rateF=null,dg=null;
        if(isForeign&&Number.isFinite(r.measTrips)){
          const rate=r.measTrucks?r.measTrips/r.measTrucks:0;
          tpd=rate;trips=dt*rate;wmt=null;
          // Foreign rows are a flat measured rate, not the path model: there is
          // no free baseline to divide by, so they get no efficiency curve
          // rather than a fabricated 100%.
        }else{
          const e=planTripsPerDT(r.key,dt,rain,c,{selfId:r.id});
          if(!e)continue;
          tpd=e.shift;trips=dt*e.shift;wmt=trips*(pay.tf||0);
          // Efficiency = served rate / this path's UNCONSTRAINED rate, i.e. what
          // one truck would get with no ceiling and no drags. Every factor below
          // is returned by planTripsPerDT itself -- nothing is re-derived here.
          //   shiftFree = daily*sf (post-saturation, pre-weighbridge), so
          //   sf = shiftFree/daily recovers the day→shift factor without
          //   reaching into planShiftFactor() and risking a second convention.
          const sf=e.daily>0?e.shiftFree/e.daily:null;
          const rawRate=e.dayBasis?(e.m&&e.m.dayRate):(e.m&&e.m.avgTr);
          // The baseline must include the CONTRACTOR factor, because the served
          // rate does. Without it, RIM (factor 1.085) read 108.5% at every low
          // DT and the pinned 0-100 axis clipped the line flat against the top,
          // so the error was invisible rather than obvious. Efficiency answers
          // "how much of what THIS plan could do is it getting", so the
          // reference is this contractor on this path with no ceilings and no
          // drags -- not the path average.
          const cf=(typeof planContractorFactor==='function')?planContractorFactor(c):1;
          const base=(sf&&Number.isFinite(rawRate)&&rawRate>0)
            ?rawRate*sf*(Number.isFinite(cf)&&cf>0?cf:1):null;
          if(base>0){
            eff=e.shift/base;
            sat=Number.isFinite(e.satFactor)?e.satFactor:1;
            wb=Number.isFinite(e.wbFactor)?e.wbFactor:1;
            // Everything that is not a ceiling: rain, other/IWIP traffic,
            // shared-section coupling, contractor factor, measured slope.
            rateF=(sat>0&&wb>0)?eff/(sat*wb):null;
            dg={rain:e.rainDelta,other:e.otherDelta,sec:e.secDelta};
          }
        }
        curve.push({dt,tripsPerDt:+tpd.toFixed(3),trips:Math.round(trips),
          wmt:wmt==null?null:Math.round(wmt),
          eff,sat,wb,rateF,dg});
      }
      if(!curve.length)return;
      // OPTIMAL DT — calculated, not just historical. Objective: most TRIPS
      // for the fewest trucks that the DATA can defend. Search only inside the
      // measured envelope (≤ dtMax): beyond it the model is guarded/floored,
      // so any "optimum" out there would be invented. Marginal-trips rule —
      // stop where the next step of trucks adds <25% of what a truck adds at
      // the small-fleet end (queueing has eaten 3/4 of the marginal truck),
      // else take the in-envelope trips peak.
      let opt=null,optNote='';
      if(!isForeign){
        const env=curve.filter(pt=>envMax==null||pt.dt<=envMax);
        if(env.length>=3){
          const margEarly=(env[1].trips-env[0].trips)/(env[1].dt-env[0].dt);
          let peak=env[0],marg=null;
          for(let k=1;k<env.length;k++){
            if(env[k].trips>peak.trips)peak=env[k];
            const mg=(env[k].trips-env[k-1].trips)/(env[k].dt-env[k-1].dt);
            if(marg==null&&margEarly>0&&mg<0.25*margEarly)marg=env[k-1];
          }
          const slopeNeg=Number.isFinite(m.bAdj)?m.bAdj<0:(m.b!=null&&m.b<0);
          if(!slopeNeg){
            opt=env[env.length-1];
            optNote='No measured decline on this path (slope ≥ 0 up to '+(envMax!=null?envMax:'?')+' DT) — every observed fleet size kept its rate, so the data-backed best is the largest proven fleet. Beyond it is untested.';
          }else if(marg&&marg.dt<peak.dt){
            opt=marg;
            optNote='Diminishing-returns point: past ~'+marg.dt+' DT each added truck contributes under 25% of what a truck adds in a small fleet (measured decline '+(Number.isFinite(m.bAdj)?m.bAdj.toFixed(4):'')+'/DT). The trips peak is later ('+peak.dt+' DT) but the extra trucks mostly queue.';
          }else{
            opt=peak;
            optNote='In-envelope trips peak at '+peak.dt+' DT (measured decline applied).';
          }
        }
      }
      // Saturation kink: the first fleet size at which the demonstrated day
      // ceiling starts dividing a FIXED number of trips. Below it the next truck
      // adds a full path-rate of trips; above it it adds ~nothing, because
      // dayTripsCap does not move. That boundary is the actual decision, so it
      // is marked rather than smoothed -- and it is measured (no day has ever
      // produced more than dayTripsCap), not a modelled congestion threshold.
      const kink=curve.find(pt=>pt.sat!=null&&pt.sat<0.999);
      out.push({id:r.id,label:r.key.replace('>',' → ')+' · '+(r.contractor||'—'),
        color:PALETTE[i%PALETTE.length],curve,currentDt:Math.round(r.dt),
        foreign:isForeign,capDt:cap,tf:pay.tf||0,
        kinkDt:kink?kink.dt:null,
        dayCap:Number.isFinite(m.dayTripsCap)?m.dayTripsCap:null,
        opt,optNote,
        slopeFlat:!(Number.isFinite(m.bAdj)?m.bAdj<0:(m.b!=null&&m.b<0)),
        dtMax:envMax});
    });
    return out;
  }

  function renderCards(){
    const host=el('plan-sens-cards');if(!host)return;
    host.innerHTML=_curves.map(p=>{
      const isolated=_sel===p.id;
      const hidden=!!_hidden[p.id];
      return `<div class="plan-sens-card${isolated?' on':''}${hidden?' off':''}" data-id="${esc(p.id)}">
        <span class="plan-sens-dot" style="background:${p.color}"></span>
        <span class="plan-sens-lbl">${esc(p.label)}</span>
        <span class="plan-sens-dt muted">${p.currentDt} DT</span>
        <button type="button" class="plan-sens-eye" data-eye="${esc(p.id)}" title="${hidden?'show':'hide'} this plan">${hidden?'◌':'👁'}</button>
      </div>`;
    }).join('');
    const back=el('plan-sens-back');
    if(back)back.style.display=_sel?'':'none';
  }

  function visibleCurves(){
    if(_sel)return _curves.filter(p=>p.id===_sel);
    return _curves.filter(p=>!_hidden[p.id]);
  }

  function renderChart(){
    const host=el('plan-sens-chart');
    if(!host)return;
    // Goes through paChart() like every other chart here (AGENTS.md). Direct
    // echarts.init() used to return silently when the CDN was unreachable,
    // leaving this section as a heading, an empty 340px gap and a caption
    // describing solid/dashed lines that were never drawn -- and this tool is
    // demoed on site connections without internet. paChart() also owns the
    // stale-instance check (getDom()===el && isConnected) that blanked every
    // gauge, and registers in _paCharts so paResizeAll() handles resize.
    const {f,unit}=granFactor();
    const vis=visibleCurves();
    const series=[];const legend=[];
    const isEff=_metric==='efficiency';
    if(isEff)vis.forEach(p=>{
      const pts=p.curve.filter(pt=>pt.eff!=null);
      if(!pts.length)return;            // road-only rows: no baseline, no curve
      const name=p.label;
      legend.push(name);
      const marks=[];
      const at=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);
      if(at&&at.eff!=null){
        marks.push({coord:[at.dt,+(at.eff*100).toFixed(1)],name:'your plan',symbol:'circle',
          symbolSize:9,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
      }
      series.push({name,type:'line',smooth:false,yAxisIndex:0,showSymbol:false,
        color:p.color,lineStyle:{width:2.2},
        data:pts.map(pt=>[pt.dt,+(pt.eff*100).toFixed(1)]),
        markPoint:marks.length?{data:marks}:undefined,
        // The kink is a real boundary, not a rendering artifact: smooth:false so
        // it is not rounded away, and a vertical rule so it can be read off.
        markLine:p.kinkDt?{silent:true,symbol:'none',
          lineStyle:{color:p.color,type:'dotted',width:1.2,opacity:.75},
          label:{show:!!_sel,formatter:'ceiling binds\n'+p.kinkDt+' DT',fontSize:9,color:'#8b98a5'},
          data:[{xAxis:p.kinkDt}]}:undefined,
        markArea:(p.dtMax&&p.capDt>p.dtMax&&(!_sel||_sel===p.id))?{
          silent:true,itemStyle:{color:'rgba(239,68,68,.05)'},
          label:{show:!!_sel,position:'insideTop',color:'#8b98a5',fontSize:9,
            formatter:'beyond measured data (> '+p.dtMax+' DT)'},
          data:[[{xAxis:p.dtMax},{xAxis:p.capDt}]]}:undefined});
    });
    if(!isEff)vis.forEach(p=>{
      // TWO STACKED PANELS (owner 2026-08-12: "split tonnage and trips/DT into
      // two graphs aligned underneath each other — clearer for anyone").
      // grid 0 = tonnage, grid 1 = trips/DT, same x scale, linked cursor.
      // Both series carry the SAME name, so one legend chip toggles the pair.
      const name=p.label;
      legend.push(name);
      if(!p.foreign){
        const markData=[];
        // ● your plan
        if(p.currentDt<=p.capDt){
          const pt=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);
          if(pt&&pt.wmt!=null)markData.push({coord:[pt.dt,Math.round(pt.wmt*f)],name:'your plan',
            symbol:'circle',symbolSize:9,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
        }
        // ★ calculated optimal
        if(p.opt&&p.opt.wmt!=null){
          markData.push({coord:[p.opt.dt,Math.round(p.opt.wmt*f)],name:'optimal',
            symbol:'pin',symbolSize:26,itemStyle:{color:'#facc15'},
            label:{show:true,formatter:'★',fontSize:11,color:'#1a1d24'}});
        }
        series.push({name,type:'line',smooth:true,xAxisIndex:0,yAxisIndex:0,showSymbol:false,
          color:p.color,lineStyle:{width:2.2},
          data:p.curve.filter(pt=>pt.wmt!=null).map(pt=>[pt.dt,Math.round(pt.wmt*f)]),
          markPoint:markData.length?{data:markData}:undefined,
          // Shade beyond the measured envelope: model guarded out there.
          markArea:(p.dtMax&&p.capDt>p.dtMax&&(!_sel||_sel===p.id))?{
            silent:true,itemStyle:{color:'rgba(239,68,68,.05)'},
            label:{show:!!_sel,position:'insideTop',color:'#8b98a5',fontSize:9,
              formatter:'beyond measured data (> '+p.dtMax+' DT)'},
            data:[[{xAxis:p.dtMax},{xAxis:p.capDt}]]}:undefined});
      }
      // Bottom panel: trips/DT, solid, same colour/name (legend pairs them).
      const marks2=[];
      const at2=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);
      if(at2)marks2.push({coord:[at2.dt,at2.tripsPerDt],name:'your plan',symbol:'circle',
        symbolSize:8,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
      series.push({name,type:'line',smooth:true,xAxisIndex:1,yAxisIndex:1,showSymbol:false,
        color:p.color,lineStyle:{width:1.8},
        data:p.curve.map(pt=>[pt.dt,pt.tripsPerDt]),
        markPoint:marks2.length?{data:marks2}:undefined,
        markLine:p.kinkDt?{silent:true,symbol:'none',
          lineStyle:{color:p.color,type:'dotted',width:1.1,opacity:.7},
          label:{show:false},
          data:[{xAxis:p.kinkDt}]}:undefined});
    });
    paChart('plan-sens-chart',{
      title:isEff
        ?{text:'Fleet efficiency — '+(_sel?(vis[0]?vis[0].label:''):'all plans')
            +'  (share of this path’s own free rate)',
          left:8,top:2,textStyle:{fontSize:12.5,color:'#cbd5e1'}}
        :[{text:'Tonnage'+(_sel?(' — '+(vis[0]?vis[0].label:'')):' — all plans'),
           left:8,top:2,textStyle:{fontSize:12,color:'#cbd5e1'}},
          {text:'Trips per DT',left:8,top:'56%',
           textStyle:{fontSize:12,color:'#cbd5e1'}}],
      legend:{type:'scroll',top:isEff?24:22,left:120,right:20,
        textStyle:{fontSize:10,color:'#8b98a5'}},
      // Output mode: two aligned grids sharing the x scale (owner: clearer than
      // dual-axis). axisPointer link keeps one hover cursor across both panels.
      grid:isEff
        ?{left:58,right:56,top:58,bottom:34}
        :[{left:58,right:24,top:48,height:'34%'},
          {left:58,right:24,top:'62%',height:'27%'}],
      axisPointer:{link:[{xAxisIndex:'all'}]},
      tooltip:{trigger:'axis',axisPointer:{type:'line'},
        formatter:params=>{
          if(!params||!params.length)return '';
          const dt=params[0].value[0];
          planSensReadout(dt);                       // live side readout while hovering
          if(isEff){
            // Attribution, not just a number: efficiency is multiplicative
            // (rate drags x ceiling x weighbridge), so each term is reported as
            // the percentage points it costs. The absolute trips/DT rides along
            // because the ratio alone does not say whether a path is any good.
            let h='<b>'+dt+' trucks</b>';
            params.forEach(s=>{
              const cv=_curves.find(p=>p.label===s.seriesName);
              if(!cv)return;
              const pt=cv.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null);
              if(!pt||pt.eff==null)return;
              const pct=v=>Math.round(v*100);
              h+='<br><span style="color:'+s.color+'">■</span> '+esc(cv.label)
                +' · <b>'+pct(pt.eff)+'%</b>'
                +' <span style="opacity:.75">('+pt.tripsPerDt+' trips/DT'
                +(pt.wmt!=null?(' · '+Math.round(pt.wmt*f).toLocaleString()+' t'+unit):'')+')</span>';
              const lost=[];
              if(pt.sat!=null&&pt.sat<0.999)lost.push('day ceiling'
                +(cv.dayCap?(' ('+cv.dayCap+' trips)'):'')+' −'+(100-pct(pt.sat))+'%');
              if(pt.wb!=null&&pt.wb<0.999)lost.push('weighbridge −'+(100-pct(pt.wb))+'%');
              if(pt.rateF!=null&&pt.rateF<0.999)lost.push('rain / other traffic / shared section −'
                +(100-pct(pt.rateF))+'%');
              h+=lost.length
                ?('<br><span style="opacity:.6;font-size:10px">&nbsp;&nbsp;lost to: '+lost.join(' · ')+'</span>')
                :'<br><span style="opacity:.6;font-size:10px">&nbsp;&nbsp;no measured loss at this fleet</span>';
            });
            return h;
          }
          // Two stacked grids share series NAMES (one per plan) — dedupe by
          // plan and read both values from the curve itself.
          const seen={};
          let h='<b>'+dt+' trucks</b>';
          params.forEach(s=>{
            const pl=s.seriesName;
            if(seen[pl])return;seen[pl]=1;
            const cv=_curves.find(p=>p.label===pl);
            const pt=cv?cv.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null):null;
            if(!pt)return;
            h+='<br><span style="color:'+s.color+'">■</span> '+esc(pl)
              +(pt.wmt!=null?(' · <b>'+Math.round(pt.wmt*granFactor().f).toLocaleString()+' t'+granFactor().unit+'</b>'):' · road-only')
              +' · '+pt.tripsPerDt+' trips/DT'
              +' · '+Math.round(pt.trips*granFactor().f)+' trips'+granFactor().unit;
          });
          return h;
        }},
      xAxis:isEff
        ?{type:'value',name:'Trucks (DT)',nameGap:22,nameLocation:'middle',
          minInterval:1,axisLabel:{color:'#8b98a5'},splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}}
        :(()=>{
          // Both panels MUST share the exact x extent or the curves misalign:
          // the top grid drops road-only plans, so left to auto-scale the two
          // axes could span different DT ranges.
          const xmax=vis.reduce((m,p)=>Math.max(m,p.capDt||0,
            p.curve.length?p.curve[p.curve.length-1].dt:0),0)||10;
          return [
            // Top panel: labels hidden (the bottom axis carries them); same scale.
            {type:'value',gridIndex:0,min:0,max:xmax,minInterval:1,axisLabel:{show:false},
             axisTick:{show:false},splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
            {type:'value',gridIndex:1,min:0,max:xmax,name:'Trucks (DT)',nameGap:22,nameLocation:'middle',
             minInterval:1,axisLabel:{color:'#8b98a5'},
             splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
          ];
        })(),
      yAxis:isEff?[
        // Pinned to 0-100 so a 97-vs-99% difference does not look like a cliff,
        // but the max GROWS if any point exceeds 100. A hard max:100 silently
        // clipped a 108.5% curve flat against the ceiling on 2026-08-12 --
        // never let an axis hide an out-of-range value it was meant to bound.
        {type:'value',name:'Efficiency (%)',min:0,
         max:Math.max(100,Math.ceil(vis.reduce((mx,p)=>Math.max(mx,
           p.curve.reduce((m2,pt)=>Math.max(m2,pt.eff!=null?pt.eff*100:0),0)),0))),
         axisLabel:{color:'#8b98a5',formatter:'{value}%'},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
      ]:[
        {type:'value',gridIndex:0,name:'t'+unit,axisLabel:{color:'#8b98a5'},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
        {type:'value',gridIndex:1,name:'trips/DT',axisLabel:{color:'#8b98a5'},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.07)'}}},
      ],
      series,
    },'This section is a chart only — there is no table behind it, so the '
      +'tonnage/trips-per-DT curves cannot be shown while the library is '
      +'unavailable. The plan table above still carries your current DT figures.');
    renderOptStrip();
  }

  // Live readout under the plan cards while hovering the chart (owner: "when I
  // hover, show how the tonnage keeps changing on the side").
  function planSensReadout(dt){
    const host=el('plan-sens-readout');if(!host)return;
    const {f,unit}=granFactor();
    const vis=visibleCurves();
    host.innerHTML='<div class="plan-sens-side-h muted">At '+dt+' trucks</div>'
      +vis.map(p=>{
        const pt=p.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null);
        if(!pt)return '';
        return '<div class="plan-sens-ro"><span class="plan-sens-dot" style="background:'+p.color+'"></span>'
          +'<span class="plan-sens-ro-v">'+(pt.wmt!=null?('<b>'+Math.round(pt.wmt*f).toLocaleString()+'</b> t'+unit):'road-only')
          +' · '+pt.tripsPerDt+' /DT · '+Math.round(pt.trips*f)+' trips'+unit+'</span></div>';
      }).join('');
  }

  // Optimal-DT strip under the chart: the calculated answer, with its basis.
  function renderOptStrip(){
    const host=el('plan-sens-opt');if(!host)return;
    const vis=visibleCurves().filter(p=>p.opt);
    host.innerHTML=vis.length
      ?vis.map(p=>{
          const gain=p.currentDt&&p.opt.dt!==p.currentDt
            ?(p.currentDt>p.opt.dt
              ?(' — you planned '+p.currentDt+' DT: ~'+Math.max(0,p.currentDt-p.opt.dt)+' trucks mostly queue')
              :(' — you planned '+p.currentDt+' DT: room for +'+(p.opt.dt-p.currentDt)+' before returns die'))
            :' — your plan sits at the optimum';
          return '<div class="plan-sens-opt-row" title="'+esc(p.optNote)+'">'
            +'<span class="plan-sens-dot" style="background:'+p.color+'"></span>'
            +'<span>★ optimal ~<b>'+p.opt.dt+' DT</b> → '+Math.round(p.opt.trips)+' trips'
            +(p.opt.wmt!=null?(' · '+Math.round(p.opt.wmt).toLocaleString()+' t/shift'):'')
            +esc(gain)+'</span></div>';
        }).join('')
      :'';
  }

  // ── Public hooks ───────────────────────────────────────────────────────────
  window.planSensIsolate=function(id){
    _sel=id||null;
    renderCards();renderChart();
  };
  window.planSensGran=function(g){
    _gran=(g==='hour'||g==='day')?g:'shift';
    // Scoped to [data-g]: the metric group reuses .plan-sens-gran for styling,
    // and an unscoped selector would strip its .on class on every scale click.
    document.querySelectorAll('.plan-sens-gran button[data-g]').forEach(b=>{
      b.classList.toggle('on',b.getAttribute('data-g')===_gran);
    });
    renderChart();
  };
  window.planSensMetric=function(mm){
    _metric=(mm==='efficiency')?'efficiency':'output';
    document.querySelectorAll('.plan-sens-gran button[data-m]').forEach(b=>{
      b.classList.toggle('on',b.getAttribute('data-m')===_metric);
    });
    const cap=el('plan-sens-caption');
    if(cap)cap.innerHTML=_metric==='efficiency'
      ? 'Share of each path’s own free rate that a truck still gets — <b>not</b> a ranking between '
        +'paths: a path at 100% can still be the slower haul, so the trips/DT is in every tooltip. '
        +'Dotted rule = where the demonstrated day ceiling starts dividing a fixed number of trips; '
        +'below it the next truck adds a full rate, above it it adds almost nothing. ● marks your current DT.'
      : 'Top graph = tonnage, bottom graph = trips per truck, same fleet-size scale so they '
        +'read together. ● your current DT · ★ calculated optimal (most trips before diminishing '
        +'returns, within measured data) · dotted rule = where the day ceiling starts binding · '
        +'shaded = beyond measured data. Same path model as the plan table. '
        +'Road-only plans appear in the bottom graph only.';
    renderChart();
  };
  /** Called after Run scenario resolves (planRunScenario paint). */
  window.planSensRefresh=function(){
    const sec=el('plan-s2-sensitivity');
    if(!sec)return;
    _curves=buildCurves();
    if(!_curves.length){sec.style.display='none';return;}
    // Drop stale isolate/hide state for removed plans.
    if(_sel&&!_curves.some(p=>p.id===_sel))_sel=null;
    Object.keys(_hidden).forEach(id=>{if(!_curves.some(p=>p.id===id))delete _hidden[id];});
    sec.style.display='';
    renderCards();renderChart();
  };

  document.addEventListener('click',ev=>{
    const eye=ev.target&&ev.target.closest?ev.target.closest('.plan-sens-eye'):null;
    if(eye){
      const id=eye.getAttribute('data-eye');
      _hidden[id]=!_hidden[id];
      renderCards();renderChart();
      ev.stopPropagation();return;
    }
    const card=ev.target&&ev.target.closest?ev.target.closest('.plan-sens-card'):null;
    if(card){
      const id=card.getAttribute('data-id');
      window.planSensIsolate(_sel===id?null:id);
    }
  });
  // Resize is handled by paResizeAll() in plan_assessment.js, which iterates the
  // shared _paCharts registry this chart is now part of.
})();
