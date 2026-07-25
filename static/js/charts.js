// charts.js — Chart rendering — scatter plots, SVG axes/series, hover chrome.
// Extracted verbatim from templates/simulator.html (Phase 1 refactor; no logic changes).

function effHover(e){
  if(!_ec) return; const svg=q('scatter'), g=q('xhair'), tip=q('eff-tip');
  const ctm=svg.getScreenCTM(); if(!ctm) return;
  const pt=svg.createSVGPoint(); pt.x=e.clientX; pt.y=e.clientY; const loc=pt.matrixTransform(ctm.inverse());
  const {bins,xr,X,YW,YE,MK,mLbl,mFmt,padL,padT,ih,iw,W,padR,maxW,peakT,peakE,useTrips,sectionMode}=_ec;
  if(loc.x<padL||loc.x>W-padR||loc.y<padT||loc.y>padT+ih){ g.innerHTML=''; tip.style.display='none'; return; }
  const dt=xr.lo+(loc.x-padL)/iw*(xr.hi-xr.lo);
  let b=bins[0]; bins.forEach(x=>{ if(Math.abs(x.dt-dt)<Math.abs(b.dt-dt)) b=x; });
  const cxp=X(b.dt);
  g.innerHTML=`<line x1="${cxp.toFixed(1)}" y1="${padT}" x2="${cxp.toFixed(1)}" y2="${padT+ih}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>`+
    (sectionMode?'':`<circle cx="${cxp.toFixed(1)}" cy="${YW(b.w).toFixed(1)}" r="4" fill="#3b82f6" stroke="#0b1220" stroke-width="1.5"/>`)+
    `<circle cx="${cxp.toFixed(1)}" cy="${YE(b[MK]).toFixed(1)}" r="4" fill="#eab308" stroke="#0b1220" stroke-width="1.5"/>`;
  const box=svg.getBoundingClientRect();
  tip.style.display='block';
  tip.style.left=Math.min(box.width-190, (e.clientX-box.left)+14)+'px';
  tip.style.top=Math.max(4, (e.clientY-box.top)-70)+'px';
  tip.innerHTML=sectionMode
    ?`<b>${fmt(Math.round(b.dt/10)*10)} DT/day on section</b> · ${b.n} days<br><span style="color:#eab308">Selected-path Trips/DT</span> <b>${fmt(b.tr,2)}</b> (${Math.round(b.tr/peakT*100)}% of observed peak)`+(b.margS!=null?`<br><span style="color:#f87171">Marginal Δ</span> <b>${b.margS>0?'+':''}${fmt(b.margS,2)} trips/DT</b> per +50 section DT`:'')
    :`<b>${fmt(Math.round(b.dt/10)*10)} DT/day</b> · ${b.n} days<br>`+
      `<span style="color:#3b82f6">WMT/day</span> <b>${fmtM(b.w)}</b> (${Math.round(b.w/maxW*100)}% of max)<br>`+
      `<span style="color:#eab308">Trips/DT</span> <b>${fmt(b.tr,2)}</b> (${Math.round(b.tr/peakT*100)}% of peak)<br>`+
      `<span style="color:#eab308">WMT/DT</span> <b>${fmt(b.e)}</b> (${Math.round(b.e/peakE*100)}% of peak)`+
      (b.marg!=null?`<br><span class="muted">marginal</span> +${useTrips?fmt(b.marg,1):fmt(Math.round(b.marg))} ${useTrips?'trips':'t/day'} per truck`:'');
}

function redrawScatter(){ if(_D) drawScatter(curDaily(), _mode==='plan'); }
function niceStep(x){ if(!(x>0)) return 1; const p=Math.pow(10,Math.floor(Math.log10(x))), f=x/p; return (f<1.5?1:f<3?2:f<7?5:10)*p; }
function niceRange(min,max,n){ n=n||4; const step=niceStep((max-min)/n)||1; const lo=Math.floor(min/step)*step, hi=Math.ceil(max/step)*step, t=[]; for(let v=lo;v<=hi+step*0.01;v+=step) t.push(v); return {lo,hi,step,ticks:t}; }
function drawSectionScatter(daily,plan){
  const svg=q('scatter'), kb=q('eff-kpis');
  const P=daily.map(d=>({x:plan?d.planDt:d.dt,tr:plan?d.planTripsPerDT:d.tripsPerDT})).filter(p=>p.x>0&&p.tr>0);
  if(P.length<6){ svg.innerHTML='<text x="20" y="40" fill="#64748b">Not enough '+(plan?'planned':'actual')+' section-DT data in range.</text>'; kb.innerHTML=''; q('eff-math').textContent=''; return; }
  const W=1000,H=340,padL=66,padR=108,padB=44,padT=42,iw=W-padL-padR,ih=H-padT-padB;
  const xs=P.map(p=>p.x).sort((a,b)=>a-b), minX=xs[0], maxX=xs[xs.length-1];
  const BW=50, bm={};
  P.forEach(p=>{ const k=Math.floor(p.x/BW)*BW; (bm[k]=bm[k]||[]).push(p); });
  const bins=Object.keys(bm).map(Number).sort((a,b)=>a-b).map(k=>({dt:k+BW/2,tr:_avg(bm[k],p=>p.tr),n:bm[k].length})).filter(b=>b.n>=3);
  if(bins.length<2){ svg.innerHTML='<text x="20" y="40" fill="#64748b">Not enough days per section-DT range.</text>'; kb.innerHTML=''; q('eff-math').textContent=''; return; }
  const xr=niceRange(minX,maxX,5), er=niceRange(Math.min(...P.map(p=>p.tr)),Math.max(...P.map(p=>p.tr)),4);
  const X=v=>padL+iw*(v-xr.lo)/(xr.hi-xr.lo||1), YE=v=>padT+ih*(1-(v-er.lo)/(er.hi-er.lo||1));
  // Efficiency slope only: change in selected-path Trips/DT for each +50 DT on the section.
  // Unlike the path-mode marginal production curve, this does not multiply by WMT or claim extra trips.
  bins.forEach((b,i)=>{b.marg=i?(b.tr-bins[i-1].tr)*50/((b.dt-bins[i-1].dt)||1):null;});
  bins.forEach((b,i)=>{const v=[bins[i-1]&&bins[i-1].marg,b.marg,bins[i+1]&&bins[i+1].marg].filter(x=>x!=null);b.margS=v.length?v.reduce((a,c)=>a+c,0)/v.length:null;});
  const mgVals=bins.map(b=>b.margS).filter(v=>v!=null), mr=niceRange(Math.min(0,...mgVals),Math.max(0,...mgVals),4);
  const YM=v=>padT+ih*(1-(v-mr.lo)/(mr.hi-mr.lo||1));
  const peakT=Math.max(...bins.map(b=>b.tr)), lowT=Math.min(...bins.map(b=>b.tr));
  const threshold=peakT-0.10*((peakT-lowT)||peakT||1);
  const band=bins.filter(b=>b.tr>=threshold);
  const peak=band.reduce((a,b)=>b.tr>a.tr?b:a,band[0]);
  let s='';
  band.forEach(b=>{const x1=X(Math.max(b.dt-BW/2,xr.lo)),x2=X(Math.min(b.dt+BW/2,xr.hi));if(x2>x1)s+=`<rect x="${x1.toFixed(1)}" y="${padT}" width="${(x2-x1).toFixed(1)}" height="${ih}" fill="rgba(34,197,94,.10)"/>`;});
  er.ticks.forEach(v=>{const y=YE(v);s+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="#16233c"/><text x="${W-padR+8}" y="${(y+3).toFixed(1)}" fill="#eab308" font-size="10">${fmt(v,2)}</text>`;});
  xr.ticks.forEach(v=>{s+=`<text x="${X(v).toFixed(1)}" y="${H-padB+16}" fill="#94a3b8" font-size="10" text-anchor="middle">${fmt(v)}</text>`;});
  s+=`<text x="${W-padR+8}" y="14" fill="#eab308" font-size="9">trips/DT</text><text x="${(padL+iw/2).toFixed(1)}" y="${H-6}" fill="#64748b" font-size="10" text-anchor="middle">${xAxisText()} →</text>`;
  P.forEach(p=>{s+=`<circle cx="${X(p.x).toFixed(1)}" cy="${YE(p.tr).toFixed(1)}" r="2.4" fill="#eab308" opacity="0.16"><title>${fmt(p.x)} DT/day on section · ${fmt(p.tr,2)} selected-path trips/DT</title></circle>`;});
  s+=`<polyline points="${bins.map(b=>X(b.dt).toFixed(1)+','+YE(b.tr).toFixed(1)).join(' ')}" fill="none" stroke="#eab308" stroke-width="3" stroke-linejoin="round"/>`;
  const mgPts=bins.filter(b=>b.margS!=null).map(b=>X(b.dt).toFixed(1)+','+YM(b.margS).toFixed(1)).join(' ');
  if(mgPts)s+=`<polyline points="${mgPts}" fill="none" stroke="#f87171" stroke-width="1.7" stroke-dasharray="5 5" stroke-linejoin="round" opacity="0.75"/>`;
  if(mr.lo<0&&mr.hi>0){const y0=YM(0);s+=`<line x1="${padL}" y1="${y0.toFixed(1)}" x2="${W-padR}" y2="${y0.toFixed(1)}" stroke="#f87171" stroke-width="0.7" stroke-dasharray="3 4" opacity="0.35"/>`;}
  mr.ticks.forEach(v=>{s+=`<text x="${W-6}" y="${(YM(v)+3).toFixed(1)}" fill="#f87171" font-size="9.5" text-anchor="end" opacity="0.8">${v>0?'+':''}${fmt(v,2)}</text>`;});
  s+=`<text x="${W-6}" y="28" fill="#f87171" font-size="9" text-anchor="end">Δtrips/DT per +50 DT</text>`;
  s+=`<line x1="${X(peak.dt).toFixed(1)}" y1="${padT}" x2="${X(peak.dt).toFixed(1)}" y2="${padT+ih}" stroke="#22c55e" stroke-width="1.8" stroke-dasharray="5 4"/><text x="${(X(peak.dt)-6).toFixed(1)}" y="${padT+12}" fill="#86efac" font-size="10.5" font-weight="700" text-anchor="end">Observed peak ${fmt(Math.round(peak.dt/10)*10)}</text>`;
  s+=`<text x="${X(peak.dt).toFixed(1)}" y="${padT+ih-6}" fill="#4ade80" font-size="9.5" text-anchor="middle" opacity="0.8">highest observed efficiency</text><g id="xhair"></g>`;
  svg.innerHTML=s;
  _ec={sectionMode:true,bins,xr,X,YW:()=>0,YE,MK:'tr',mLbl:'trips/DT',mFmt:v=>fmt(v,2),padL,padT,ih,iw,W,padR,maxW:1,peakT,peakE:1,useTrips:true};
  svg.onmousemove=effHover; svg.onmouseleave=()=>{const g=q('xhair');if(g)g.innerHTML='';q('eff-tip').style.display='none';};
  kb.innerHTML=[
    ['Section DT at observed efficiency peak',fmt(Math.round(peak.dt/10)*10),'DT/day','on mapped section paths'],
    ['Selected-path efficiency',fmt(peak.tr,2),'trips/DT','observed peak'],
    ['Marginal efficiency at peak',peak.margS==null?'—':((peak.margS>0?'+':'')+fmt(peak.margS,2)),'trips/DT','per +50 section DT']
  ].map(c=>`<div class="effkpi"><div class="v">${c[1]} <span class="u">${c[2]}</span></div><div class="l">${c[0]} · ${c[3]}</div></div>`).join('');
  const pathScope=_gSelPath.size?`${_gSelPath.size} selected path${_gSelPath.size===1?'':'s'}`:'all mapped paths in the selected section scope';
  q('eff-math').innerHTML=`Section traffic is the number of DT assigned to paths mapped to any selected section. The yellow series shows <b>Trips/DT for ${pathScope}</b>. The red dashed line is the marginal <b>change in Trips/DT per +50 section DT</b>; below zero means efficiency tended to fall as section DT increased. It does not use WMT and does not represent incremental trips. Green bins contain the highest observed efficiency, but are <b>not a fleet recommendation</b>: route mix and other operating conditions can also affect the relationship.`;
}

function combinedPathDays(plan){
  const secKeys=new Set(gsecPaths().map(p=>pathKey(p.origin,p.dest))),targetKeys=_gSelPath.size?_gSelPath:secKeys,secByDay={};
  (_D.dailyByPath||[]).forEach(r=>{const k=pathKey(r.o,r.dd);if(secKeys.has(k)){secByDay[r.d]=secByDay[r.d]||[0,0];secByDay[r.d][0]+=r.nb;secByDay[r.d][1]+=r.dtp;}});
  return (_D.dailyByPath||[]).filter(r=>targetKeys.has(pathKey(r.o,r.dd))&&secKeys.has(pathKey(r.o,r.dd))).map(r=>{
    const path=plan?r.dtp:r.nb,section=(secByDay[r.d]||[])[plan?1:0]||0,tr=plan?(r.dtp?r.ptr/r.dtp:0):(r.nb?r.rit/r.nb:0);
    return {date:r.d,pathKey:pathKey(r.o,r.dd),label:r.o+' → '+r.dd,path,section,tr,wmt:plan?r.pw:r.w,trips:plan?r.ptr:r.rit,
      shiftTr:plan?tr:(r.snb?r.srit/r.snb:tr),shiftTrips:plan?r.ptr:(Number.isFinite(r.srit)?r.srit:r.rit),
      shiftWmt:plan?r.pw:(Number.isFinite(r.sw)?r.sw:r.w),shiftExplicit:plan?false:!!r.sx,shiftCount:plan?null:(r.sc||null)};
  }).filter(p=>p.path>0&&p.section>0&&p.tr>0);
}

function projectCombinedPoint(p){
  const v=_combined3D,a=v.az,e=v.el,x=p.nx,y=p.ny,z=p.nz,ca=Math.cos(a),sa=Math.sin(a),ce=Math.cos(e),se=Math.sin(e);
  const side=ca*x-sa*y,forward=sa*x+ca*y;
  return {x:v.cx+v.scale*side,y:v.cy-v.scale*(ce*z-se*forward),depth:ce*forward+se*z};
}
function combinedOptimum(P,rx,ry){
  const xb=Math.max(1,niceStep(rx.d/7)),yb=Math.max(1,niceStep(ry.d/7)),gm={};
  P.forEach(p=>{const x=Math.floor(p.path/xb)*xb,y=Math.floor(p.section/yb)*yb,k=x+'|'+y;(gm[k]=gm[k]||{x,y,vals:[]}).vals.push(p.tr);});
  let cells=Object.values(gm).filter(c=>c.vals.length>=3).map(c=>({...c,tr:_avg(c.vals,v=>v),n:c.vals.length}));
  if(!cells.length)cells=Object.values(gm).filter(c=>c.vals.length>=2).map(c=>({...c,tr:_avg(c.vals,v=>v),n:c.vals.length}));
  if(!cells.length)return null;
  const best=cells.reduce((a,b)=>b.tr>a.tr?b:a,cells[0]);
  const path=Math.min(rx.hi,best.x+xb/2),section=Math.min(ry.hi,best.y+yb/2);
  return {path,section,tr:best.tr,n:best.n,xb,yb};
}
function renderCombined3D(){
  if(!_combined3D)return;const v=_combined3D,svg=q('scatter'),corners=[];
  for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1])corners.push({x,y,z,p:projectCombinedPoint({nx:x,ny:y,nz:z})});
  const corner=(x,y,z)=>corners.find(c=>c.x===x&&c.y===y&&c.z===z).p;let s='<title>Rotatable combined DT efficiency model</title><desc>Path DT, total section DT, and Trips per DT shown as a three-dimensional daily scatter. Drag to rotate.</desc>';
  const edges=[];for(const c of corners){if(c.x<1)edges.push([c.p,corner(1,c.y,c.z)]);if(c.y<1)edges.push([c.p,corner(c.x,1,c.z)]);if(c.z<1)edges.push([c.p,corner(c.x,c.y,1)]);}edges.forEach(([a,b])=>{s+=`<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#263b5e" stroke-width="1" opacity="0.65"/>`;});
  const pts=v.points.map((p,i)=>({...p,pi:i,sp:projectCombinedPoint(p)})).sort((a,b)=>a.sp.depth-b.sp.depth);
  pts.forEach(p=>{const col=v.colours[p.pathKey],selected=p.pi===v.selectedIndex,r=3.2+1.8*(p.sp.depth+2)/4,aria=escH(`${p.label} · ${p.date} · path ${fmt(p.path)} DT/day · section ${fmt(p.section)} DT/day · ${fmt(p.tr,2)} trips/DT · click to run scenario`);s+=`<circle class="c3-point" data-i="${p.pi}" cx="${p.sp.x.toFixed(1)}" cy="${p.sp.y.toFixed(1)}" r="${(r+(selected?2:0)).toFixed(1)}" fill="${col}" opacity="${selected?1:.64}" stroke="${selected?'#f8fafc':'#0b1220'}" stroke-width="${selected?2.2:.7}" role="button" aria-label="${aria}"/>`;});
  const o=corner(-1,-1,-1),r=v.ranges,cc=projectCombinedPoint({nx:0,ny:0,nz:0});
  const axis=(end,coord,range,label,col,dec)=>{const ep=corner(...end),dx=ep.x-o.x,dy=ep.y-o.y,l=Math.hypot(dx,dy)||1,mx=(o.x+ep.x)/2,my=(o.y+ep.y)/2;let nx=-dy/l,ny=dx/l;if(Math.hypot(mx+nx*18-cc.x,my+ny*18-cc.y)<Math.hypot(mx-nx*18-cc.x,my-ny*18-cc.y)){nx=-nx;ny=-ny;}let a='';for(let i=0;i<=4;i++){const t=-1+i/2,p=projectCombinedPoint(coord(t)),val=range.lo+(range.hi-range.lo)*i/4,anchor=nx>.25?'start':nx<-.25?'end':'middle';a+=`<line x1="${(p.x-nx*3).toFixed(1)}" y1="${(p.y-ny*3).toFixed(1)}" x2="${(p.x+nx*3).toFixed(1)}" y2="${(p.y+ny*3).toFixed(1)}" stroke="${col}" opacity="0.7"/><text x="${(p.x+nx*9).toFixed(1)}" y="${(p.y+ny*9+3).toFixed(1)}" fill="#94a3b8" font-size="9.5" text-anchor="${anchor}">${fmt(val,dec)}</text>`;}a+=`<text x="${(mx+nx*27).toFixed(1)}" y="${(my+ny*27+3).toFixed(1)}" fill="${col}" font-size="10" text-anchor="middle">${label}</text>`;return a;};
  s+=axis([1,-1,-1],t=>({nx:t,ny:-1,nz:-1}),r.path,'Path DT/day','#60a5fa',0)+axis([-1,1,-1],t=>({nx:-1,ny:t,nz:-1}),r.section,'Section DT/day','#a78bfa',0)+axis([-1,-1,1],t=>({nx:-1,ny:-1,nz:t}),r.tr,'Trips/DT','#eab308',2);
  if(v.optimum){const p=projectCombinedPoint(v.optimum),lbl=`Observed peak · ${fmt(v.optimum.path)} path DT · ${fmt(v.optimum.section)} section DT · ${fmt(v.optimum.tr,2)} trips/DT`;s+=`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="10" fill="none" stroke="#4ade80" stroke-width="2"/><path d="M ${p.x.toFixed(1)} ${(p.y-6).toFixed(1)} L ${(p.x+6).toFixed(1)} ${p.y.toFixed(1)} L ${p.x.toFixed(1)} ${(p.y+6).toFixed(1)} L ${(p.x-6).toFixed(1)} ${p.y.toFixed(1)} Z" fill="#4ade80" stroke="#0b1220"/><text x="${(p.x+12).toFixed(1)}" y="${(p.y-11).toFixed(1)}" fill="#86efac" font-size="9.5" font-weight="700">${lbl}</text>`;}
  if(v.scenario){const p=projectCombinedPoint(v.scenario),lbl=`Scenario · ${fmt(v.scenario.path)} path DT · ${fmt(v.scenario.section)} section DT · ${fmt(v.scenario.tr,2)} trips/DT`;s+=`<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="9" fill="#0b1220" stroke="#f8fafc" stroke-width="2.5"/><path d="M ${(p.x-5).toFixed(1)} ${p.y.toFixed(1)} L ${(p.x+5).toFixed(1)} ${p.y.toFixed(1)} M ${p.x.toFixed(1)} ${(p.y-5).toFixed(1)} L ${p.x.toFixed(1)} ${(p.y+5).toFixed(1)}" stroke="#f8fafc" stroke-width="2"/><text x="${(p.x+12).toFixed(1)}" y="${(p.y+15).toFixed(1)}" fill="#e2e8f0" font-size="9.5" font-weight="700">${lbl}</text>`;}
  s+='<g id="c3-laser" pointer-events="none"></g>';
  s+=`<text x="18" y="24" fill="#94a3b8" font-size="10">Drag to rotate · double-click to reset</text>`;
  let ly=45;Object.entries(v.colours).forEach(([k,col])=>{const label=v.labels[k];s+=`<circle cx="22" cy="${ly}" r="4" fill="${col}"/><text x="32" y="${ly+3}" fill="#94a3b8" font-size="9">${escH(label)}</text>`;ly+=15;});
  svg.innerHTML=s;
}
function hideCombinedHover(){const g=q('c3-laser'),tip=q('eff-tip');if(g)g.innerHTML='';if(tip)tip.style.display='none';}
function showCombinedHover(i){
  const v=_combined3D,svg=q('scatter'),tip=q('eff-tip'),p=v&&v.points[i];if(!p)return hideCombinedHover();
  const sp=projectCombinedPoint(p),base=projectCombinedPoint({nx:p.nx,ny:p.ny,nz:-1}),px=projectCombinedPoint({nx:p.nx,ny:-1,nz:-1}),py=projectCombinedPoint({nx:-1,ny:p.ny,nz:-1}),g=q('c3-laser');
  if(g)g.innerHTML=`<line x1="${sp.x.toFixed(1)}" y1="${sp.y.toFixed(1)}" x2="${base.x.toFixed(1)}" y2="${base.y.toFixed(1)}" stroke="#eab308" stroke-width="1.5" stroke-dasharray="4 3"/><line x1="${base.x.toFixed(1)}" y1="${base.y.toFixed(1)}" x2="${px.x.toFixed(1)}" y2="${px.y.toFixed(1)}" stroke="#60a5fa" stroke-width="1.5" stroke-dasharray="4 3"/><line x1="${base.x.toFixed(1)}" y1="${base.y.toFixed(1)}" x2="${py.x.toFixed(1)}" y2="${py.y.toFixed(1)}" stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="4 3"/><circle cx="${sp.x.toFixed(1)}" cy="${sp.y.toFixed(1)}" r="7" fill="none" stroke="#f8fafc" stroke-width="1.5"/><circle cx="${base.x.toFixed(1)}" cy="${base.y.toFixed(1)}" r="3" fill="#f8fafc"/>`;
  tip.innerHTML=`<b>${escH(p.label)}</b><br>${escH(p.date)}<br><span style="color:#60a5fa">Path DT/day</span> ${fmt(p.path)}<br><span style="color:#a78bfa">Section DT/day</span> ${fmt(p.section)}<br><span style="color:#eab308">Trips/DT</span> ${fmt(p.tr,2)}`;tip.style.display='block';
  const sr=svg.getBoundingClientRect(),cr=svg.parentElement.getBoundingClientRect(),vb=svg.viewBox.baseVal;let left=sr.left-cr.left+(sp.x-vb.x)*sr.width/vb.width+12,top=sr.top-cr.top+(sp.y-vb.y)*sr.height/vb.height+12;
  left=Math.max(8,Math.min(left,cr.width-tip.offsetWidth-8));top=Math.max(8,Math.min(top,cr.height-tip.offsetHeight-8));tip.style.left=left+'px';tip.style.top=top+'px';
}
function drawCombinedScatter(plan){
  const svg=q('scatter'),kb=q('eff-kpis'),tip=q('eff-tip'),P=combinedPathDays(plan);tip.style.display='none';_ec=null;_flowPointScenario=null;
  if(P.length<8){stopFlowSimulator();svg.innerHTML='<text x="500" y="155" fill="#94a3b8" font-size="14" text-anchor="middle">Not enough '+(plan?'planned':'actual')+' path-day observations for the combined view.</text>';kb.innerHTML='';q('eff-math').textContent='';q('c3-analysis').style.display='none';return;}
  const range=k=>{const a=P.map(p=>p[k]),lo=Math.min(...a),hi=Math.max(...a);return {lo,hi,d:(hi-lo)||1};},rx=range('path'),ry=range('section'),rz=range('tr');
  const keys=[...new Set(P.map(p=>p.pathKey))],colours={},labels={};keys.forEach((k,i)=>{colours[k]=`hsl(${Math.round(210+i*137.508)%360} 72% 64%)`;labels[k]=P.find(p=>p.pathKey===k).label;});
  const points=P.map(p=>({...p,nx:-1+2*(p.path-rx.lo)/rx.d,ny:-1+2*(p.section-ry.lo)/ry.d,nz:-1+2*(p.tr-rz.lo)/rz.d})),opt=combinedOptimum(P,rx,ry);
  q('c3-scenario-select').innerHTML='<option value="">Choose an observed scenario…</option>'+points.map((p,i)=>`<option value="${i}">${escH(p.date)} · ${escH(p.label)} · ${fmt(p.section)} section DT · ${fmt(p.tr,2)} trips/DT</option>`).join('');
  const optimum=opt?{path:opt.path,section:opt.section,tr:opt.tr,n:opt.n,nx:-1+2*(opt.path-rx.lo)/rx.d,ny:-1+2*(opt.section-ry.lo)/ry.d,nz:-1+2*(opt.tr-rz.lo)/rz.d}:null;
  _combined3D={points,colours,labels,ranges:{path:rx,section:ry,tr:rz},optimum,az:-0.72,el:0.46,cx:650,cy:275,scale:190,drag:null};renderCombined3D();
  svg.onpointerdown=e=>{e.preventDefault();hideCombinedHover();const t=e.target.closest&&e.target.closest('.c3-point');if(_c3Tool==='select'){_combined3D.drag={point:t?+t.dataset.i:null,moved:false,select:true};return;}_combined3D.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,point:t?+t.dataset.i:null,moved:false};svg.style.cursor='grabbing';svg.setPointerCapture(e.pointerId);};
  svg.onpointermove=e=>{if(!_combined3D)return;if(_combined3D.drag){const d=_combined3D.drag,total=Math.hypot(e.clientX-d.startX,e.clientY-d.startY);if(total>10)d.moved=true;if(d.moved){const dx=e.clientX-d.x,dy=e.clientY-d.y;_combined3D.az+=dx*.012;_combined3D.el=Math.max(-1.15,Math.min(1.15,_combined3D.el-dy*.009));d.x=e.clientX;d.y=e.clientY;renderCombined3D();}return;}const t=e.target.closest&&e.target.closest('.c3-point');if(t)showCombinedHover(+t.dataset.i);else hideCombinedHover();};
  svg.onpointerup=()=>{if(!_combined3D)return;const d=_combined3D.drag;_combined3D.drag=null;_combined3D.suppressClick=!!(d&&(d.moved||d.select));svg.style.cursor=_c3Tool==='select'?'crosshair':'grab';if(d&&d.select&&d.point!=null)runCombinedScenario(d.point);};svg.onclick=e=>{if(!_combined3D||_c3Tool!=='select')return;if(_combined3D.suppressClick){_combined3D.suppressClick=false;return;}const t=e.target.closest&&e.target.closest('.c3-point');if(t)runCombinedScenario(+t.dataset.i);};svg.onpointercancel=()=>{if(_combined3D)_combined3D.drag=null;svg.style.cursor=_c3Tool==='select'?'crosshair':'grab';};svg.onpointerleave=()=>{if(!_combined3D||!_combined3D.drag)hideCombinedHover();};
  svg.ondblclick=()=>{if(_combined3D){_combined3D.az=-.72;_combined3D.el=.46;renderCombined3D();}};
  const best=opt||P.reduce((a,b)=>b.tr>a.tr?b:a,P[0]);kb.innerHTML=[
    ['Paths shown',fmt(keys.length),'paths',fmt(P.length)+' path-days'],
    ['Observed peak',fmt(best.path),'path DT/day','section '+fmt(best.section)+' DT/day'],
    ['Efficiency at peak',fmt(best.tr,2),'trips/DT',opt?(fmt(opt.n)+' observations in cell'):'single best observation']
  ].map(c=>`<div class="effkpi"><div class="v">${c[1]} <span class="u">${c[2]}</span></div><div class="l">${c[0]} · ${c[3]}</div></div>`).join('');
  q('eff-math').innerHTML=`Each point is one <b>path-day</b>: path DT, total DT on the selected section, and that path's Trips/DT. <b>Click a point to load and run that observation in the road simulator below</b>; drag empty space or a point to rotate. The green marker is the highest repeated-observation efficiency cell and should be treated as an observed peak, not a causal fleet recommendation.`;
  renderFlowSimulator(P,colours);
  // Start with a real observed shift nearest the best repeated-observation cell. This gives the
  // crosshair, replay and assessment a valid current scenario instead of leaving the page blank.
  // Default to a 2026 shift so the weighbridge markers/panel have data (weigh history starts Dec 2025).
  const in2026=points.map((p,i)=>({p,i})).filter(x=>x.p.date>='2026-01-01'),pool=in2026.length?in2026:points.map((p,i)=>({p,i}));
  const autoIndex=opt?pool.reduce((b,x)=>{const d=((x.p.path-opt.path)/rx.d)**2+((x.p.section-opt.section)/ry.d)**2+((x.p.tr-opt.tr)/rz.d)**2;return d<b.d?{i:x.i,d}:b;},{i:pool[0].i,d:Infinity}).i:pool.reduce((b,x)=>x.p.tr>points[b.i].tr?{i:x.i}:b,{i:pool[0].i}).i;
  if(Number.isFinite(autoIndex))runCombinedScenario(autoIndex,false);else renderCombinedAnalysis(P);
  setC3Tool(_c3Tool);
}

function drawScatter(daily, plan){
  const svg=q('scatter'), kb=q('eff-kpis');
  const combined=_xAxis==='combined';
  q('eff-visual-wrap').classList.toggle('combined',combined&&_gSelSec.size>0);
  svg.setAttribute('viewBox',combined?'0 0 1100 620':'0 0 1000 340');svg.style.height=combined?'560px':'280px';
  svg.style.cursor=combined?'grab':'';svg.style.touchAction=combined?'none':'';svg.style.userSelect=combined?'none':'';svg.style.webkitUserSelect=combined?'none':'';svg.onselectstart=combined?()=>false:null;
  if(!combined){stopFlowSimulator();_combined3D=null;svg.onpointerdown=null;svg.onpointermove=null;svg.onpointerup=null;svg.onpointercancel=null;svg.onpointerleave=null;svg.ondblclick=null;}
  if((_xAxis==='section'||_xAxis==='combined')&&!_gSelSec.size){
    svg.innerHTML='<text x="500" y="145" fill="#94a3b8" font-size="14" text-anchor="middle">Select at least one constraint section to plot DT on section.</text><text x="500" y="168" fill="#64748b" font-size="11" text-anchor="middle">Use the “Constraint sections” control above the graph.</text>';
    stopFlowSimulator();kb.innerHTML=''; q('eff-math').textContent='';q('c3-analysis').style.display='none'; return;
  }
  if(_xAxis==='combined'){drawCombinedScatter(plan);return;}
  if(_xAxis==='section'){ drawSectionScatter(daily,plan); return; }
  // x=DT/day, w=WMT/day, e=WMT/DT, tr=trips/DT
  const P=daily.map(d=>({x:plan?d.planDt:d.dt, w:plan?d.planWmt:d.wmt, tr:plan?d.planTripsPerDT:d.tripsPerDT})).filter(p=>p.x>0&&p.w>0&&p.tr>0).map(p=>({...p,e:p.w/p.x}));
  if(P.length<6){ svg.innerHTML='<text x="20" y="40" fill="#64748b">Not enough '+(plan?'planned':'actual')+' data in range.</text>'; kb.innerHTML=''; q('eff-math').textContent=''; return; }
  const useTrips=_effMetric==='trips', MK=useTrips?'tr':'e', mLbl=useTrips?'trips/DT':'t/DT', mFmt=v=>useTrips?fmt(v,2):fmt(v);
  const W=1000,H=340,padL=66,padR=88,padB=44,padT=16, iw=W-padL-padR, ih=H-padT-padB;
  const xs=P.map(p=>p.x).slice().sort((a,b)=>a-b), minX=xs[0], maxX=xs[xs.length-1];
  const wr=niceRange(Math.min(...P.map(p=>p.w)),Math.max(...P.map(p=>p.w))), er=niceRange(Math.min(...P.map(p=>p[MK])),Math.max(...P.map(p=>p[MK]))), xr=niceRange(minX,maxX,5);
  const X=v=>padL+iw*(v-xr.lo)/(xr.hi-xr.lo||1), YW=v=>padT+ih*(1-(v-wr.lo)/(wr.hi-wr.lo||1)), YE=v=>padT+ih*(1-(v-er.lo)/(er.hi-er.lo||1));
  // ── 50-truck bins (min 3 obs) ──
  const BW=50, bm={}; P.forEach(p=>{const k=Math.floor(p.x/BW)*BW; (bm[k]=bm[k]||[]).push(p);});
  const bins=Object.keys(bm).map(Number).sort((a,b)=>a-b).map(k=>({dt:k+BW/2,w:_avg(bm[k],p=>p.w),e:_avg(bm[k],p=>p.e),tr:_avg(bm[k],p=>p.tr),n:bm[k].length})).filter(b=>b.n>=3);
  if(bins.length<2){ svg.innerHTML='<text x="20" y="40" fill="#64748b">Not enough days per fleet-size range.</text>'; kb.innerHTML=''; q('eff-math').textContent=''; return; }
  // Marginal follows the active efficiency metric: Trips/DT → extra TRIPS per +1 DT; WMT/DT → extra t/day.
  const _tot=b=>useTrips? b.dt*b.tr : b.w;   // active-metric total (Σ trips, or WMT/day)
  const mUnit=useTrips?'trips':'t/day';
  bins.forEach((b,i)=>{ b.marg=i? (_tot(b)-_tot(bins[i-1]))/((b.dt-bins[i-1].dt)||1):null; });
  // Marginal-product curve, 3-pt smoothed for a clean line. Where it bends down = diminishing returns
  // (each added truck buys fewer trips / less production as congestion builds).
  bins.forEach((b,i)=>{ const w=[bins[i-1]&&bins[i-1].marg,b.marg,bins[i+1]&&bins[i+1].marg].filter(v=>v!=null); b.margS=w.length?w.reduce((a,c)=>a+c,0)/w.length:null; });
  const mgVals=bins.map(b=>b.margS).filter(v=>v!=null);
  const mr=niceRange(Math.min(0,...mgVals),Math.max(...mgVals),4), YM=v=>padT+ih*(1-(v-mr.lo)/(mr.hi-mr.lo||1));
  const maxW=Math.max(...bins.map(b=>b.w)), peakE=Math.max(...bins.map(b=>b.e)), peakT=Math.max(...bins.map(b=>b.tr)), maxDT=Math.max(...bins.map(b=>b.dt));
  // ── OPTIMISER: score each bin per objective; recommend a RANGE (top-decile scores) ──
  const wt=k=>Math.max(0,parseFloat(q('w-'+k).value)||0);
  const nP=b=>b.w/maxW, nE=b=>b.e/peakE, nT=b=>b.tr/peakT, nF=b=>b.dt/maxDT;
  // Minimum production floor — applies to EVERY objective: only fleet sizes producing ≥ this are
  // considered, then the objective picks the best among them. If the floor is ABOVE anything any fleet
  // sustains, we can't meet it — so recommend the MAX-production fleet (closest we can get) and warn,
  // rather than ignoring the floor and snapping back to the efficiency peak.
  const minP=Math.max(0,parseFloat(q('opt-min-v').value)||0);
  let minWarn='', eligible=bins.slice(), forceMaxProd=false;
  if(minP>0){ const meet=bins.filter(b=>b.w>=minP);
    if(meet.length) eligible=meet;
    else { forceMaxProd=true; minWarn=`No fleet size sustains ${fmtM(minP)} t/day (best sustained ≈ ${fmtM(maxW)} at ${fmt(Math.round(maxDT/10)*10)} DT/day) — recommending the max-production fleet.`; } }
  let objLbl='', scoreFn;
  if(forceMaxProd){ objLbl='Max production (target '+fmtM(minP)+' t/day unreachable)'; scoreFn=b=> nP(b); }
  else if(_optObj==='max_trips'){ objLbl='Maximise efficiency (Trips/DT)'; scoreFn=b=> nT(b); }
  else if(_optObj==='balanced'){ objLbl='Balanced production & efficiency'; scoreFn=b=> nP(b)*nP(b)*nT(b); }
  else if(_optObj==='max_prod'){ objLbl='Max production'; scoreFn=b=> nP(b); }
  else if(_optObj==='min_fleet'){ objLbl='Minimum fleet'+(minP>0?(' for ≥'+fmtM(minP)+' t/day'):' (set a min production)'); scoreFn=b=> (1-nF(b)); }
  else { objLbl='Custom weights'; scoreFn=b=> wt('trip')*nT(b)+wt('prod')*nP(b)+wt('wmt')*nE(b)-wt('fleet')*nF(b); }
  if(minP>0 && !minWarn && _optObj!=='min_fleet') objLbl+=`, ≥${fmtM(minP)} t/day`;
  eligible.forEach(b=>b.score=scoreFn(b));
  const valid=eligible.length?eligible:bins.slice();
  const sMax=Math.max(...valid.map(b=>b.score)), sMin=Math.min(...valid.map(b=>b.score));
  const thr=sMax-0.10*((sMax-sMin)||Math.abs(sMax)||1);         // top-decile band = recommended range
  const band=valid.filter(b=>b.score>=thr).sort((a,b)=>a.dt-b.dt);
  const loDT=band[0].dt-BW/2, hiDT=band[band.length-1].dt+BW/2;
  // recommended point: unreachable floor → max-production fleet; min_fleet → fewest trucks meeting
  // target; else the PEAK of the objective
  const recBin= forceMaxProd ? valid.reduce((a,b)=>b.w>a.w?b:a,valid[0])
              : (_optObj==='min_fleet')? band[0]
              : valid.reduce((a,b)=>b.score>a.score?b:a,valid[0]);
  const recDT=recBin.dt, prodPct=Math.round(recBin.w/maxW*100), effPct=Math.round((useTrips?recBin.tr/peakT:recBin.e/peakE)*100), margAtRec=recBin.marg;
  let s='';
  // recommended range band (green) + over-fleet band (red beyond hiDT)
  const zone=(a,b,col)=>{const x1=X(Math.max(a,xr.lo)),x2=X(Math.min(b,xr.hi)); return x2>x1?`<rect x="${x1.toFixed(1)}" y="${padT}" width="${(x2-x1).toFixed(1)}" height="${ih}" fill="${col}"/>`:'';};
  s+=zone(loDT,hiDT,'rgba(34,197,94,.10)')+zone(hiDT,xr.hi,'rgba(239,68,68,.06)');
  wr.ticks.forEach(v=>{const y=YW(v);s+=`<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W-padR}" y2="${y.toFixed(1)}" stroke="#16233c"/><text x="${padL-8}" y="${(y+3).toFixed(1)}" fill="#3b82f6" font-size="10" text-anchor="end">${fmtM(v)}</text>`;});
  er.ticks.forEach(v=>{s+=`<text x="${W-padR+8}" y="${(YE(v)+3).toFixed(1)}" fill="#eab308" font-size="10">${mFmt(v)}</text>`;});
  xr.ticks.forEach(v=>{s+=`<text x="${X(v).toFixed(1)}" y="${H-padB+16}" fill="#94a3b8" font-size="10" text-anchor="middle">${fmt(v)}</text>`;});
  s+=`<text x="${padL-8}" y="${padT-5}" fill="#3b82f6" font-size="9" text-anchor="end">WMT/day</text><text x="${W-padR+8}" y="${padT-5}" fill="#eab308" font-size="9">${mLbl}</text><text x="${(padL+iw/2).toFixed(1)}" y="${H-6}" fill="#64748b" font-size="10" text-anchor="middle">${xAxisText()} →</text>`;
  P.forEach(p=>{s+=`<circle cx="${X(p.x).toFixed(1)}" cy="${YW(p.w).toFixed(1)}" r="2.4" fill="#3b82f6" opacity="0.15"><title>${fmt(p.x)} DT · ${fmtM(p.w)} t/day · ${fmt(p.e)} t/DT · ${fmt(p.tr,2)} trips/DT</title></circle>`;});
  P.forEach(p=>{s+=`<circle cx="${X(p.x).toFixed(1)}" cy="${YE(p[MK]).toFixed(1)}" r="2.4" fill="#eab308" opacity="0.15"><title>${fmt(p.x)} DT · ${mFmt(p[MK])} ${mLbl} · ${fmt(p.tr,2)} trips/DT</title></circle>`;});
  // recommended-range edges + point + historical max
  s+=`<line x1="${X(recDT).toFixed(1)}" y1="${padT}" x2="${X(recDT).toFixed(1)}" y2="${padT+ih}" stroke="#22c55e" stroke-width="1.8" stroke-dasharray="5 4"/><text x="${(X(recDT)-6).toFixed(1)}" y="${padT+12}" fill="#86efac" font-size="10.5" font-weight="700" text-anchor="end">Recommended ${fmt(Math.round(recDT/10)*10)}</text>`;
  s+=`<text x="${(X((loDT+hiDT)/2)).toFixed(1)}" y="${padT+ih-6}" fill="#4ade80" font-size="9.5" text-anchor="middle" opacity="0.8">range ${fmt(Math.round(loDT/10)*10)}–${fmt(Math.round(hiDT/10)*10)}</text>`;
  s+=`<line x1="${X(maxX).toFixed(1)}" y1="${padT}" x2="${X(maxX).toFixed(1)}" y2="${padT+ih}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 4" opacity="0.7"/><text x="${(X(maxX)-6).toFixed(1)}" y="${padT+27}" fill="#94a3b8" font-size="10" text-anchor="end">Historical max ${fmt(Math.round(maxX/10)*10)}</text>`;
  s+=`<polyline points="${bins.map(b=>X(b.dt).toFixed(1)+','+YW(b.w).toFixed(1)).join(' ')}" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linejoin="round"/>`;
  s+=`<polyline points="${bins.map(b=>X(b.dt).toFixed(1)+','+YE(b[MK]).toFixed(1)).join(' ')}" fill="none" stroke="#eab308" stroke-width="3" stroke-linejoin="round"/>`;
  // red marginal-product curve + its own far-right scale (t/day per +1 DT)
  const mgPts=bins.filter(b=>b.margS!=null).map(b=>X(b.dt).toFixed(1)+','+YM(b.margS).toFixed(1)).join(' ');
  if(mgPts){ s+=`<polyline points="${mgPts}" fill="none" stroke="#f87171" stroke-width="1.6" stroke-dasharray="5 5" stroke-linejoin="round" opacity="0.5"/>`; }
  if(mr.lo<0){ const y0=YM(0); s+=`<line x1="${padL}" y1="${y0.toFixed(1)}" x2="${W-padR}" y2="${y0.toFixed(1)}" stroke="#f87171" stroke-width="0.7" stroke-dasharray="3 4" opacity="0.35"/>`; }
  mr.ticks.forEach(v=>{ s+=`<text x="${W-6}" y="${(YM(v)+3).toFixed(1)}" fill="#f87171" font-size="9.5" text-anchor="end" opacity="0.7">${useTrips?fmt(v,1):fmtM(v)}</text>`; });
  s+=`<text x="${W-6}" y="${(padT-5).toFixed(1)}" fill="#f87171" font-size="9" text-anchor="end" opacity="0.7">${useTrips?'trips/+DT':'t/+DT'}</text>`;
  s+=`<g id="xhair"></g>`;
  svg.innerHTML=s;
  // crosshair: store state + hook mouse (nearest bin readout)
  _ec={bins,xr,X,YW,YE,MK,mLbl,mFmt,padL,padT,padB,ih,iw,W,H,padR,minX,maxX,maxW,peakT,peakE,useTrips};
  svg.onmousemove=effHover; svg.onmouseleave=()=>{const g=q('xhair');if(g)g.innerHTML='';q('eff-tip').style.display='none';};
  kb.innerHTML=[
    [_xAxis==='section'?'Recommended section load':'Recommended fleet', fmt(Math.round(recDT/10)*10), 'DT/day', 'range '+fmt(Math.round(loDT/10)*10)+'–'+fmt(Math.round(hiDT/10)*10)],
    ['Production at recommendation', fmtM(recBin.w), 't/day', prodPct+'% of maximum'],
    [useTrips?'Trips/DT at recommendation':'WMT/DT at recommendation', mFmt(recBin[MK]), useTrips?'trips/DT':'t/DT', effPct+'% of peak'],
  ].map(c=>`<div class="effkpi"><div class="v">${c[1]} <span class="u">${c[2]}</span></div><div class="l">${c[0]} · ${c[3]}</div></div>`).join('');
  q('eff-math').innerHTML=`Objective: <b>${objLbl}</b>. Recommended operating range <b>${fmt(Math.round(loDT/10)*10)}–${fmt(Math.round(hiDT/10)*10)} DT/day</b> on <b>${xAxisText()}</b> (top-decile of the objective score on 50-truck bins, min 3 days each). At the recommendation: <b>${prodPct}%</b> of max production, ${mLbl} at <b>${effPct}%</b> of peak${margAtRec!=null?`, marginal ≈ <b>+${useTrips?fmt(margAtRec,1):fmt(Math.round(margAtRec))} ${mUnit} per extra truck</b>`:''}.`+(minWarn?` <span style="color:#f59e0b">⚠ ${minWarn}</span>`:'');
}
function drawChart(months){
  const svg=q('chart'); if(!months||!months.length){svg.innerHTML='<text x="20" y="40" fill="#64748b">No data in range.</text>';return;}
  const W=1000,H=280,padL=58,padR=104,padB=32,padT=18, iw=W-padL-padR, ih=H-padT-padB;
  const mo=months.map(m=>({...m, tpdt:(m.dtPerDay? m.tPerDay/m.dtPerDay:0)}));
  const maxT=Math.max(...mo.map(m=>m.tPerDay),1), maxD=Math.max(...mo.map(m=>m.dtPerDay),1), maxP=Math.max(...mo.map(m=>m.tpdt),1);
  const cx=i=>padL+gap*i+gap/2, YT=v=>padT+ih*(1-v/maxT), YD=v=>padT+ih*(1-v/maxD), YP=v=>padT+ih*(1-v/maxP);
  const n=mo.length, bw=iw/n*0.6, gap=iw/n; let s='';
  // 3 axes: left WMT (blue), inner-right DT (amber), outer-right t/DT (green)
  for(let g=0;g<=3;g++){const y=padT+ih*(1-g/3);
    s+=`<line x1="${padL}" y1="${y}" x2="${W-padR}" y2="${y}" stroke="#16233c"/>`;
    s+=`<text x="${padL-8}" y="${y+3}" fill="#3b82f6" font-size="10" text-anchor="end">${fmtM(maxT*g/3)}</text>`;
    s+=`<text x="${W-padR+8}" y="${y+3}" fill="#eab308" font-size="10">${fmt(maxD*g/3)}</text>`;
    s+=`<text x="${W-6}" y="${y+3}" fill="#22c55e" font-size="10" text-anchor="end">${fmt(maxP*g/3)}</text>`;}
  s+=`<text x="${padL-8}" y="${padT-6}" fill="#3b82f6" font-size="9" text-anchor="end">t/day</text><text x="${W-padR+8}" y="${padT-6}" fill="#eab308" font-size="9">DT/day</text><text x="${W-6}" y="${padT-6}" fill="#22c55e" font-size="9" text-anchor="end">t/DT</text>`;
  mo.forEach((m,i)=>{const x=padL+gap*i+(gap-bw)/2, y=YT(m.tPerDay);
    s+=`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(padT+ih-y,0).toFixed(1)}" rx="2" fill="#3b82f6" opacity="0.8"><title>${ymLbl(m.ym)}: ${fmtM(m.tPerDay)} t/day · ${Math.round(m.dtPerDay)} DT/day · ${fmt(m.tpdt)} t/DT</title></rect>`;
    s+=`<text x="${(x+bw/2).toFixed(1)}" y="${H-padB+14}" fill="#94a3b8" font-size="10" text-anchor="middle">${ymLbl(m.ym)}</text>`;});
  // DT/day line (amber)
  s+=`<polyline points="${mo.map((m,i)=>cx(i).toFixed(1)+','+YD(m.dtPerDay).toFixed(1)).join(' ')}" fill="none" stroke="#eab308" stroke-width="2"/>`;
  mo.forEach((m,i)=>{s+=`<circle cx="${cx(i).toFixed(1)}" cy="${YD(m.dtPerDay).toFixed(1)}" r="2.4" fill="#eab308"><title>${ymLbl(m.ym)}: ${Math.round(m.dtPerDay)} DT/day</title></circle>`;});
  // WMT/DT productivity line (green)
  s+=`<polyline points="${mo.map((m,i)=>cx(i).toFixed(1)+','+YP(m.tpdt).toFixed(1)).join(' ')}" fill="none" stroke="#22c55e" stroke-width="2" stroke-dasharray="4 3"/>`;
  mo.forEach((m,i)=>{s+=`<circle cx="${cx(i).toFixed(1)}" cy="${YP(m.tpdt).toFixed(1)}" r="2.4" fill="#22c55e"><title>${ymLbl(m.ym)}: ${fmt(m.tpdt)} t/DT</title></circle>`;});
  svg.innerHTML=s;
}
