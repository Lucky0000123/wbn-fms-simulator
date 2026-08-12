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
  let _chart=null;
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
      const cap=Math.min(150,Number.isFinite(m.dtMax)?Math.max(20,Math.round(m.dtMax*2)):100);
      const step=cap<=40?2:(cap<=100?4:6);
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
      out.push({id:r.id,label:r.key.replace('>',' → ')+' · '+(r.contractor||'—'),
        color:PALETTE[i%PALETTE.length],curve,currentDt:Math.round(r.dt),
        foreign:isForeign,capDt:cap,
        dtMax:Number.isFinite(m.dtMax)?Math.round(m.dtMax):null});
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
    if(!host||typeof echarts==='undefined')return;
    if(!_chart)_chart=echarts.init(host);
    const {f,unit}=granFactor();
    const vis=visibleCurves();
    const series=[];const legend=[];
    vis.forEach(p=>{
      if(!p.foreign){
        const name=p.label+' — tonnage';
        legend.push(name);
        series.push({name,type:'line',smooth:true,yAxisIndex:0,showSymbol:false,
          color:p.color,lineStyle:{width:2.2},
          data:p.curve.filter(pt=>pt.wmt!=null).map(pt=>[pt.dt,Math.round(pt.wmt*f)]),
          markPoint:(p.currentDt<=p.capDt)?{symbol:'circle',symbolSize:9,
            label:{show:false},itemStyle:{color:p.color,borderColor:'#fff',borderWidth:1.5},
            data:[{coord:[p.currentDt,(()=>{const pt=p.curve.reduce((a,b)=>Math.abs(b.dt-p.currentDt)<Math.abs((a?a.dt:1e9)-p.currentDt)?b:a,null);return pt&&pt.wmt!=null?Math.round(pt.wmt*f):0;})()],name:'your plan'}]}:undefined});
      }
      const name2=p.label+' — trips/DT';
      legend.push(name2);
      series.push({name:name2,type:'line',smooth:true,yAxisIndex:1,showSymbol:false,
        color:p.color,lineStyle:{width:1.6,type:'dashed'},
        data:p.curve.map(pt=>[pt.dt,pt.tripsPerDt])});
    });
    _chart.setOption({
      title:{text:_sel?('Fleet sensitivity — '+(vis[0]?vis[0].label:'')):'Fleet sensitivity — all plans',
        left:8,top:2,textStyle:{fontSize:12.5,color:'#cbd5e1'}},
      legend:{type:'scroll',top:24,textStyle:{fontSize:10,color:'#8b98a5'}},
      grid:{left:58,right:56,top:58,bottom:34},
      tooltip:{trigger:'axis',axisPointer:{type:'line'},
        formatter:params=>{
          if(!params||!params.length)return '';
          const dt=params[0].value[0];
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
    },true);
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
  window.addEventListener('resize',()=>{if(_chart)_chart.resize();});
})();
