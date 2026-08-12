// ── C · Fleet sensitivity — nonlinear DT sweep per plan ──────────────────────
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
        let tpd=null,trips=null,wmt=null;
        if(isForeign&&Number.isFinite(r.measTrips)){
          const rate=r.measTrucks?r.measTrips/r.measTrucks:0;
          tpd=rate;trips=dt*rate;wmt=null;
        }else{
          const e=planTripsPerDT(r.key,dt,rain,c);
          if(!e)continue;
          tpd=e.shift;trips=dt*e.shift;wmt=trips*(pay.tf||0);
        }
        curve.push({dt,tripsPerDt:+tpd.toFixed(3),trips:Math.round(trips),
          wmt:wmt==null?null:Math.round(wmt)});
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
      out.push({id:r.id,label:r.key.replace('>',' → ')+' · '+(r.contractor||'—'),
        color:PALETTE[i%PALETTE.length],curve,currentDt:Math.round(r.dt),
        foreign:isForeign,capDt:cap,tf:pay.tf||0,
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
    vis.forEach(p=>{
      if(!p.foreign){
        const name=p.label+' — tonnage';
        legend.push(name);
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
        series.push({name,type:'line',smooth:true,yAxisIndex:0,showSymbol:false,
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
      const name2=p.label+' — trips/DT';
      legend.push(name2);
      series.push({name:name2,type:'line',smooth:true,yAxisIndex:1,showSymbol:false,
        color:p.color,lineStyle:{width:1.6,type:'dashed'},
        data:p.curve.map(pt=>[pt.dt,pt.tripsPerDt])});
    });
    paChart('plan-sens-chart',{
      title:{text:_sel?('Fleet sensitivity — '+(vis[0]?vis[0].label:'')):'Fleet sensitivity — all plans',
        left:8,top:2,textStyle:{fontSize:12.5,color:'#cbd5e1'}},
      legend:{type:'scroll',top:24,textStyle:{fontSize:10,color:'#8b98a5'}},
      grid:{left:58,right:56,top:58,bottom:34},
      tooltip:{trigger:'axis',axisPointer:{type:'line'},
        formatter:params=>{
          if(!params||!params.length)return '';
          const dt=params[0].value[0];
          planSensReadout(dt);                       // live side readout while hovering
          const byPlan={};
          params.forEach(s=>{
            const plan=s.seriesName.replace(/ — (tonnage|trips\/DT)$/,'');
            (byPlan[plan]=byPlan[plan]||{}).c=s.color;
            if(/tonnage$/.test(s.seriesName))byPlan[plan].wmt=s.value[1];
            else byPlan[plan].tpd=s.value[1];
          });
          let h='<b>'+dt+' trucks</b>';
          Object.keys(byPlan).forEach(pl=>{
            const v=byPlan[pl];
            const cv=_curves.find(p=>p.label===pl);
            const pt=cv?cv.curve.reduce((a,b)=>Math.abs(b.dt-dt)<Math.abs((a?a.dt:1e9)-dt)?b:a,null):null;
            h+='<br><span style="color:'+v.c+'">■</span> '+esc(pl)
              +(v.wmt!=null?(' · <b>'+Number(v.wmt).toLocaleString()+' t'+granFactor().unit+'</b>'):' · road-only')
              +(v.tpd!=null?(' · '+v.tpd+' trips/DT'):'')
              +(pt?(' · '+Math.round(pt.trips*granFactor().f)+' trips'+granFactor().unit):'');
          });
          return h;
        }},
      xAxis:{type:'value',name:'Trucks (DT)',nameGap:22,nameLocation:'middle',
        minInterval:1,axisLabel:{color:'#8b98a5'},splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
      yAxis:[
        {type:'value',name:'Tonnage (t'+unit+')',axisLabel:{color:'#8b98a5'},
         splitLine:{lineStyle:{color:'rgba(148,163,184,.09)'}}},
        {type:'value',name:'Trips/DT',axisLabel:{color:'#8b98a5'},splitLine:{show:false}},
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
    document.querySelectorAll('.plan-sens-gran button').forEach(b=>{
      b.classList.toggle('on',b.getAttribute('data-g')===_gran);
    });
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
