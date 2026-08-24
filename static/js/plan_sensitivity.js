// ── B · Fleet sensitivity — hybrid saturation curve vs fleet size ─────────────
// After Run scenario. Each line is THAT path's /api/congestion_curve
// (proportional loaders, rules §10.9) — the same curve the plan table prices
// with. Not the old path-response dayRate + day-ceiling divide.
(function(){
  const PALETTE=['#4e79a7','#f28e2b','#59a14f','#e15759','#b07aa1','#76b7b2','#edc948','#ff9da7'];
  let _sel=null;            // isolated plan id, or null = all
  let _hidden={};           // id → true (eye toggle)
  let _gran='day';          // hour | shift | day — follows Conditions (Day default)
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
  let _sensWarmT=null;

  const el=id=>document.getElementById(id);
  const esc=x=>String(x==null?'':x).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function granFactor(){
    // Stored curve values are PER DAY (hybrid saturation curve).
    if(_gran==='hour')return {f:1/24,unit:'/h'};
    if(_gran==='shift')return {f:0.5,unit:'/shift'};
    return {f:1,unit:'/day'};
  }

  function niceMax(x){
    const n=Math.max(40, Math.ceil(x||0));
    const steps=[40,50,60,80,100,120,150,180,200,250,300,350,400,500];
    for(let i=0;i<steps.length;i++)if(n<=steps[i])return steps[i];
    return Math.ceil(n/50)*50;
  }

  function axisMax(vis){
    if(!vis.length)return 80;
    if(_sel){
      const p=vis[0];
      return niceMax(Math.max(p.currentDt*1.35, p.kinkDt||0, 80));
    }
    const maxPlan=vis.reduce((m,p)=>Math.max(m,p.currentDt||0),0);
    return niceMax(Math.max(maxPlan*1.4, 60));
  }

  // planTripsPerDT tags every answer with the model that produced it:
  //   'hybrid_segment' — segment-based physics (the default since 2026-08-22)
  //   'hybrid'         — per-route physics curve
  //   'legacy_divide'  — the cold-start / failed-fetch fallback
  // Match the FAMILY, never a literal. This test read ==='hybrid' and went
  // silently false for every point the day segment pricing shipped; pinning
  // 'hybrid_segment' instead would just re-arm the same trap for the next tag.
  const isHybrid=v=>typeof v==='string'&&v.indexOf('hybrid')===0;

  // '' when the whole curve came from the hybrid family. Otherwise it names
  // what actually priced the line. A curve CAN be built entirely on the legacy
  // divide — cold start before /api/congestion_curve lands, or inside the 30 s
  // retry window after a failed fetch — and a caption that says "hybrid"
  // regardless is the densityFit / road-crowding caption defect a third time.
  function basisNote(p){
    const b=(p&&p.bases)||[];
    if(!b.length||b.every(isHybrid))return '';
    return 'Priced with '+b.join(' + ')+' — the hybrid saturation curve had not '
      +'landed for every fleet point when this line was drawn. It reprices itself '
      +'on the next refresh.';
  }

  function workingDt(r){
    const frozen=typeof planAllocFrozen==='function'&&planAllocFrozen();
    const n=(frozen&&r._allocDt!=null)?r._allocDt:r.dt;
    return Math.round(n||0);
  }

  // Build the curves from the live holding plan via the hybrid saturation curve.
  function buildCurves(){
    if(typeof planDraftEntries!=='function'||typeof planTripsPerDT!=='function')return [];
    const rain=Math.max(0,parseFloat((el('plan-rain')||{}).value)||0);
    const out=[];
    let colorI=0;
    planDraftEntries().forEach(r=>{
      if(r.foreign)return;
      const dtNow=workingDt(r);
      if(!(dtNow>0))return;
      const m=(typeof _pathResp!=='undefined'&&_pathResp[r.key])||{};
      const c=typeof planContractor==='function'?planContractor(r.contractor):null;
      const pay=typeof planPayload==='function'?planPayload(r.key,c):{tf:0};
      const envMax=typeof planDtEnvelope==='function'?planDtEnvelope(m):(Number.isFinite(m.dtMax)?Math.round(m.dtMax):null);
      const hyb=typeof planHybridCurveFor==='function'
        ?planHybridCurveFor(r.key,0,rain,{proportional:true}):null;
      const cap=Math.min(800, Math.max(120, Math.ceil(dtNow*1.35)));
      const step=cap<=80?2:(cap<=200?5:Math.max(5, Math.ceil(cap/50)));
      const ldNow=(typeof planNLoaders==='function'?planNLoaders(r):r.loaders)||2;
      const tpl=dtNow>0?dtNow/Math.max(1,ldNow):15;
      const curve=[];
      for(let dt=1;dt<=cap;dt+=step){
        const nLd=Math.max(1, Math.round(dt/Math.max(1,tpl)));
        const extra={solo:true, nLoaders:nLd};
        const e=planTripsPerDT(r.key,dt,rain,c,
          typeof planTripOpts==='function'?planTripOpts(r.id, extra)
            :Object.assign({selfId:r.id}, extra));
        if(!e||(!(e.daily>0)&&!(e.shift>0)))continue;
        const tpdDay=e.daily>0?e.daily:e.shift;
        const trips=dt*tpdDay, wmt=trips*(pay.tf||0);
        const free=curve.length?curve[0].tripsPerDt:tpdDay;
        const sat=free>0?Math.min(1, tpdDay/free):1;
        // eff/sat are this path's own rate at `dt` over its own rate at the
        // first swept fleet — both straight out of planTripsPerDT, nothing
        // re-derived here. It deliberately does NOT read e.satFactor: that
        // field is now a clean pooled-vs-priced ratio, where it used to carry
        // 1/cf for calibrated contractors (see the tombstone comment in
        // plan.js for the fleet-global factor deleted 2026-08-23), so
        // consuming it would have silently changed what this axis means.
        // A ratio to the path's own baseline is unaffected by that.
        // wb/rateF were the other two terms of the old
        // efficiency = rateFactor x satFactor x wbFactor decomposition. They
        // were hardcoded to 1, read by nothing, and asserted "no rate or
        // weighbridge derating applied" — which planTripsPerDT does not
        // promise. Dropped rather than left lying.
        curve.push({dt,tripsPerDt:+tpdDay.toFixed(3),trips:Math.round(trips),
          wmt:Math.round(wmt),eff:sat,sat,
          mv:e.modelVersion||null,hybrid:isHybrid(e.modelVersion)});
      }
      if(curve.length<3)return;
      const kink=curve.find(pt=>pt.sat!=null&&pt.sat<0.999)
        ||(hyb&&hyb.knee_dt?curve.find(pt=>pt.dt>=hyb.knee_dt):null);
      const opt=kink||curve[curve.length-1];
      const optNote=kink
        ?('Saturation curve knee near '+kink.dt+' DT · '+kink.tripsPerDt+' trips/DT/day')
        :'Hybrid saturation curve (proportional loaders) — same as the plan table.';
      out.push({id:r.id,label:r.key.replace('>',' → ')+' · '+(r.contractor||'—'),
        color:PALETTE[colorI++%PALETTE.length],curve,currentDt:dtNow,
        foreign:false,capDt:cap,tf:pay.tf||0,
        kinkDt:kink?kink.dt:null,
        dayCap:Number.isFinite(m.dayTripsCap)?m.dayTripsCap:null,
        opt,optNote,slopeFlat:false,dtMax:envMax,
        bases:Array.from(new Set(curve.map(pt=>pt.mv).filter(Boolean))),
        hybrid:curve.every(pt=>pt.hybrid)});
    });
    return out;
  }

  function renderCards(){
    const host=el('plan-sens-cards');if(!host)return;
    host.innerHTML=_curves.map(p=>{
      const isolated=_sel===p.id;
      const hidden=!!_hidden[p.id];
      const note=basisNote(p);
      return `<div class="plan-sens-card${isolated?' on':''}${hidden?' off':''}" data-id="${esc(p.id)}">
        <span class="plan-sens-dot" style="background:${p.color}"></span>
        <span class="plan-sens-lbl">${esc(p.label)}</span>
        <span class="plan-sens-dt muted">${p.currentDt} DT</span>
        ${note?`<span class="plan-sens-dt er" title="${esc(note)}">legacy</span>`:''}
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
    const {f,unit}=granFactor();
    const vis=visibleCurves();
    const xmax=axisMax(vis);
    const clip=pts=>pts.filter(pt=>pt.dt<=xmax+1);
    const series=[];const legend=[];
    const isEff=_metric==='efficiency';
    const isolated=!!_sel;
    // Titles below name the hybrid saturation curve as the basis. Say so only
    // while it IS the basis for every line drawn — otherwise name the fallback.
    const fellBack=vis.some(p=>basisNote(p));
    const basisTail=fellBack?' · some lines on the legacy divide fallback':'';
    if(isEff)vis.forEach(p=>{
      const pts=clip(p.curve.filter(pt=>pt.eff!=null));
      if(!pts.length)return;
      const name=p.label;
      legend.push(name);
      const marks=[];
      const at=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);
      if(at&&at.eff!=null){
        marks.push({coord:[at.dt,+(at.eff*100).toFixed(1)],name:'planned',symbol:'circle',
          symbolSize:8,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
      }
      series.push({name,type:'line',smooth:false,yAxisIndex:0,showSymbol:false,
        color:p.color,lineStyle:{width:2},
        data:pts.map(pt=>[pt.dt,+(pt.eff*100).toFixed(1)]),
        markPoint:marks.length?{data:marks}:undefined,
        markLine:(isolated&&p.kinkDt&&p.kinkDt<=xmax)?{silent:true,symbol:'none',
          lineStyle:{color:'#94a3b8',type:'dashed',width:1,opacity:.7},
          label:{show:true,formatter:'Knee · '+p.kinkDt+' DT',fontSize:10,color:'#94a3b8'},
          data:[{xAxis:p.kinkDt}]}:undefined,
        markArea:(isolated&&p.dtMax&&xmax>p.dtMax)?{
          silent:true,itemStyle:{color:'rgba(148,163,184,.06)'},
          label:{show:true,position:'insideTop',color:'#8b98a5',fontSize:10,
            formatter:'Beyond measured fleet (>'+p.dtMax+' DT)'},
          data:[[{xAxis:p.dtMax},{xAxis:xmax}]]}:undefined});
    });
    if(!isEff)vis.forEach(p=>{
      const name=p.label;
      legend.push(name);
      const pts=clip(p.curve.filter(pt=>pt.wmt!=null));
      const markData=[];
      const pt=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);
      if(pt&&pt.wmt!=null){
        markData.push({coord:[pt.dt,Math.round(pt.wmt*f)],name:'planned',
          symbol:'circle',symbolSize:8,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
      }
      if(isolated&&p.opt&&p.opt.wmt!=null&&p.opt.dt<=xmax){
        markData.push({coord:[p.opt.dt,Math.round(p.opt.wmt*f)],name:'day cap',
          symbol:'diamond',symbolSize:10,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},
          label:{show:false}});
      }
      series.push({name,type:'line',smooth:false,xAxisIndex:0,yAxisIndex:0,showSymbol:false,
        color:p.color,lineStyle:{width:2},
        data:pts.map(row=>[row.dt,Math.round(row.wmt*f)]),
        markPoint:markData.length?{data:markData}:undefined,
        markArea:(isolated&&p.dtMax&&xmax>p.dtMax)?{
          silent:true,itemStyle:{color:'rgba(148,163,184,.06)'},
          label:{show:true,position:'insideTop',color:'#8b98a5',fontSize:10,
            formatter:'Beyond measured fleet (>'+p.dtMax+' DT)'},
          data:[[{xAxis:p.dtMax},{xAxis:xmax}]]}:undefined});
      const marks2=[];
      if(pt)marks2.push({coord:[pt.dt,+(pt.tripsPerDt*f).toFixed(3)],name:'planned',symbol:'circle',
        symbolSize:8,itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},label:{show:false}});
      series.push({name,type:'line',smooth:false,xAxisIndex:1,yAxisIndex:1,showSymbol:false,
        color:p.color,lineStyle:{width:2},
        data:clip(p.curve).map(row=>[row.dt,+(row.tripsPerDt*f).toFixed(3)]),
        markPoint:marks2.length?{data:marks2}:undefined,
        markLine:(isolated&&p.kinkDt&&p.kinkDt<=xmax)?{silent:true,symbol:'none',
          lineStyle:{color:'#94a3b8',type:'dashed',width:1,opacity:.7},
          label:{show:false},
          data:[{xAxis:p.kinkDt}]}:undefined});
    });
    const axisCommon={type:'value',min:0,max:xmax,minInterval:1,
      axisLabel:{color:'#94a3b8',fontSize:10},
      splitLine:{lineStyle:{color:'rgba(148,163,184,.1)'}},
      axisLine:{lineStyle:{color:'rgba(148,163,184,.25)'}}};
    paChart('plan-sens-chart',{
      animationDuration:200,
      title:isEff
        ?{text:'Efficiency vs fleet size'+(_sel&&vis[0]?'  ·  '+vis[0].label:'')+basisTail,
          left:8,top:4,textStyle:{fontSize:13,fontWeight:600,color:'#e6edf3'}}
        :[{text:'Tonnage vs fleet size'+(_sel&&vis[0]?'  ·  '+vis[0].label:''),
           left:8,top:4,textStyle:{fontSize:13,fontWeight:600,color:'#e6edf3'}},
          {text:'Trips per DT  ·  hybrid saturation curve (proportional loaders)'+basisTail,
           left:8,top:'54%',textStyle:{fontSize:12,fontWeight:600,color:'#e6edf3'}}],
      legend:{type:'scroll',top:24,left:8,right:16,itemWidth:10,itemHeight:8,
        textStyle:{fontSize:10.5,color:'#94a3b8'}},
      grid:isEff
        ?{left:62,right:20,top:58,bottom:40}
        :[{left:62,right:20,top:56,height:'32%'},
          {left:62,right:20,top:'62%',height:'26%'}],
      axisPointer:{link:[{xAxisIndex:'all'}],lineStyle:{color:'#64748b'}},
      tooltip:{trigger:'axis',axisPointer:{type:'line'},
        backgroundColor:'rgba(15,18,24,.94)',borderColor:'rgba(148,163,184,.25)',
        textStyle:{color:'#e6edf3',fontSize:12},
        formatter:params=>{
          if(!params||!params.length)return '';
          const dt=params[0].value[0];
          planSensReadout(dt);
          if(isEff){
            let h='<b>'+dt+' DT</b>';
            params.forEach(s=>{
              const cv=_curves.find(p=>p.label===s.seriesName);
              if(!cv)return;
              const row=cv.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null);
              if(!row||row.eff==null)return;
              const pct=v=>Math.round(v*100);
              h+='<br><span style="color:'+s.color+'">●</span> '+esc(cv.label)
                +' · <b>'+pct(row.eff)+'%</b> of free rate'
                +' <span style="opacity:.75">('+(row.tripsPerDt*f).toFixed(3)+' trips/DT'
                +(row.wmt!=null?(' · '+Math.round(row.wmt*f).toLocaleString()+' t'+unit):'')+')</span>';
              if(row.sat!=null&&row.sat<0.999)h+='<br><span style="opacity:.6;font-size:10px">  curve knee'
                +(cv.kinkDt?(' near '+cv.kinkDt+' DT'):'')+' · '+(pct(row.sat))+'% of free rate</span>';
            });
            return h;
          }
          const seen={};
          let h='<b>'+dt+' DT</b>';
          params.forEach(s=>{
            const pl=s.seriesName;
            if(seen[pl])return;seen[pl]=1;
            const cv=_curves.find(p=>p.label===pl);
            const row=cv?cv.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null):null;
            if(!row)return;
            h+='<br><span style="color:'+s.color+'">●</span> '+esc(pl)
              +(row.wmt!=null?(' · <b>'+Math.round(row.wmt*f).toLocaleString()+' t'+unit+'</b>'):'')
              +' · '+(row.tripsPerDt*f).toFixed(3)+' trips/DT';
          });
          return h;
        }},
      xAxis:isEff
        ?Object.assign({},axisCommon,{name:'Dump trucks (DT)',nameGap:24,nameLocation:'middle',
          nameTextStyle:{color:'#8b98a5',fontSize:11}})
        :[
          Object.assign({},axisCommon,{gridIndex:0,axisLabel:{show:false},axisTick:{show:false}}),
          Object.assign({},axisCommon,{gridIndex:1,name:'Dump trucks (DT)',nameGap:24,nameLocation:'middle',
            nameTextStyle:{color:'#8b98a5',fontSize:11}}),
        ],
      yAxis:isEff?[
        {type:'value',name:'Share of free rate',min:0,
         max:Math.max(100,Math.ceil(vis.reduce((mx,p)=>Math.max(mx,
           p.curve.reduce((m2,pt)=>Math.max(m2,pt.eff!=null?pt.eff*100:0),0)),0))),
         axisLabel:{color:'#94a3b8',formatter:'{value}%',fontSize:10},
         nameTextStyle:{color:'#8b98a5',fontSize:11},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.1)'}}},
      ]:[
        {type:'value',gridIndex:0,name:'t'+unit,scale:true,
         axisLabel:{color:'#94a3b8',fontSize:10,formatter:v=>Math.round(v).toLocaleString()},
         nameTextStyle:{color:'#8b98a5',fontSize:11},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.1)'}}},
        {type:'value',gridIndex:1,name:'trips/DT',scale:true,min:0,
         axisLabel:{color:'#94a3b8',fontSize:10},
         nameTextStyle:{color:'#8b98a5',fontSize:11},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.08)'}}},
      ],
      series,
    },'This section is a chart only — there is no table behind it, so the '
      +'tonnage/trips-per-DT curves cannot be shown while the library is '
      +'unavailable. The plan table above still carries your current DT figures.');
    renderOptStrip();
  }

  function planSensReadout(dt){
    const host=el('plan-sens-readout');if(!host)return;
    const {f,unit}=granFactor();
    const vis=visibleCurves();
    host.innerHTML='<div class="plan-sens-side-h muted">At '+dt+' DT</div>'
      +vis.map(p=>{
        const pt=p.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null);
        if(!pt)return '';
        return '<div class="plan-sens-ro"><span class="plan-sens-dot" style="background:'+p.color+'"></span>'
          +'<span class="plan-sens-ro-v">'+(pt.wmt!=null?('<b>'+Math.round(pt.wmt*f).toLocaleString()+'</b> t'+unit):'')
          +' · '+(pt.tripsPerDt*f).toFixed(3)+' trips/DT</span></div>';
      }).join('');
  }

  function renderOptStrip(){
    const host=el('plan-sens-opt');if(!host)return;
    const vis=visibleCurves().filter(p=>p.opt);
    const {f,unit}=granFactor();
    host.innerHTML=vis.length
      ?vis.map(p=>{
          let note;
          if(p.kinkDt){
            const d=p.currentDt-p.kinkDt;
            note=d>4
              ?('Planned '+p.currentDt+' DT · curve knee near '+p.kinkDt+' DT')
              :d<-4
              ?('Planned '+p.currentDt+' DT · curve knee near '+p.kinkDt+' DT')
              :('Planned '+p.currentDt+' DT · at the saturation-curve knee');
          }else{
            note='Planned '+p.currentDt+' DT · hybrid saturation curve (proportional loaders)';
          }
          return '<div class="plan-sens-opt-row" title="'+esc(p.optNote)+'">'
            +'<span class="plan-sens-dot" style="background:'+p.color+'"></span>'
            +'<span>'+esc(p.label)+' · '+Math.round(p.opt.trips)+' trips'
            +(p.opt.wmt!=null?(' · '+Math.round(p.opt.wmt*f).toLocaleString()+' t'+unit):'')
            +' · '+esc(note)+'</span></div>';
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
    // Both captions name the hybrid curve as the basis. Only say so while it
    // IS the basis for every line on screen; otherwise name the fallback and
    // let the reader discount the shape. Same rule the road-crowding card
    // learned on 2026-08-22 — a hardcoded basis caption outlives its model.
    const fell=visibleCurves().filter(p=>basisNote(p));
    const fellTail=fell.length
      ? ' <span class="er">'+fell.length+' line'+(fell.length>1?'s':'')
        +' fell back to the legacy divide (marked “legacy”) and will reprice on refresh.</span>'
      : '';
    if(cap)cap.innerHTML=(_metric==='efficiency'
      ? 'Each line is that path’s own hybrid rate as a share of its free trips/DT. '
        +'Not a ranking: 100% on a slow haul still moves fewer trips than a lower % on a fast one. '
        +'Click a plan to see where the saturation-curve knee sits. ● = planned DT.'
      : 'Hybrid saturation curve from /api/congestion_curve (proportional loaders — same basis the plan table prices with). '
        +'Trips/DT is per day on the Per day scale. ● = planned DT.')+fellTail;
    renderChart();
  };
  /** Called after Run scenario resolves (planRunScenario paint). */
  window.planSensRefresh=function(){
    const sec=el('plan-s2-sensitivity');
    if(!sec)return;
    const rain=Math.max(0,parseFloat((el('plan-rain')||{}).value)||0);
    let pending=false;
    if(typeof planDraftEntries==='function'&&typeof planHybridCurveFor==='function'){
      planDraftEntries().forEach(r=>{
        if(!r||r.foreign||!(workingDt(r)>0))return;
        if(planHybridCurveFor(r.key,0,rain,{proportional:true})===undefined)pending=true;
      });
    }
    _curves=buildCurves();
    if(!_curves.length){sec.style.display='none';sec.open=false;return;}
    if(_sel&&!_curves.some(p=>p.id===_sel))_sel=null;
    Object.keys(_hidden).forEach(id=>{if(!_curves.some(p=>p.id===id))delete _hidden[id];});
    sec.style.display='';
    // Stay collapsed until the user opens the dropdown. Painting while closed
    // sizes ECharts to a zero-width box (same trap as the hidden-tab map).
    if(sec.open){renderCards();renderChart();}
    if(pending){
      if(_sensWarmT)clearTimeout(_sensWarmT);
      _sensWarmT=setTimeout(window.planSensRefresh, 280);
    }
  };

  const _sensHost=el('plan-s2-sensitivity');
  if(_sensHost){
    _sensHost.addEventListener('toggle',function(){
      if(!_sensHost.open)return;
      renderCards();renderChart();
      if(typeof paResizeAll==='function')paResizeAll();
    });
  }

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
