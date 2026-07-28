// matrix.js — Constraint matrix — sections x paths, route identity, and the path/section filters.
// Extracted verbatim from templates/simulator.html (Phase 1 refactor; no logic changes).

function gsecPaths(){
  const selected=new Set([..._gSelSec].map(Number));
  return (_matrix.paths||[]).filter(p=>(p.sections||[]).some(s=>selected.has(Number(s))));
}
// paths available on the graph: scoped to the picked sections if any, else every path present in the data
function gPathOptions(){
  if(_gSelSec.size) return gsecPaths().map(p=>({key:pathKey(p.origin,p.dest),o:p.origin,d:p.dest}));
  const seen=new Set(), out=[];
  ((_D&&_D.dailyByPath)||[]).forEach(r=>{ const k=pathKey(r.o,r.dd); if(!seen.has(k)){seen.add(k); out.push({key:k,o:r.o,d:r.dd});} });
  if(!out.length) ((_D&&_D.routes)||[]).forEach(r=>{ const k=pathKey(r.origin,r.dest); if(!seen.has(k)){seen.add(k); out.push({key:k,o:r.origin,d:r.dest});} });
  return out.sort((a,b)=>(a.o+a.d).localeCompare(b.o+b.d));
}
// effective path-key set for the chart: explicit path picks → else paths through the picked sections → else all
function gPathKeys(){
  if(_gSelPath.size) return _gSelPath;
  if(_gSelSec.size) return new Set(gsecPaths().map(p=>pathKey(p.origin,p.dest)));
  return null;
}
function gsecRender(){
  const p=q('ms-gsec-panel'), secs=(_matrix.sections||[]);
  p.innerHTML=`<label class="all"><input type="checkbox" ${_gSelSec.size===0?'checked':''} onchange="gsecAll(this.checked)"> No constraint sections</label>`+
    (secs.length?secs.map(s=>`<label><input type="checkbox" ${_gSelSec.has(s.id)?'checked':''} onchange="gsecPick(${s.id},this.checked)"> ${escH(s.name)}</label>`).join('')
      :`<div class="muted" style="padding:6px;font-size:11px">No sections — use ⚙ Matrix to add.</div>`);
  q('ms-gsec-btn').textContent='Constraint sections: '+(_gSelSec.size===0?'none':_gSelSec.size+' selected')+' ▾';
}
function gPathRender(){
  const p=q('ms-gpath-panel'), opts=gPathOptions();
  p.innerHTML=`<label class="all"><input type="checkbox" ${_gSelPath.size===0?'checked':''} onchange="gPathAll(this.checked)"> All paths${_gSelSec.size?' in sections':''}</label>`+
    (opts.length?opts.map(o=>`<label><input type="checkbox" ${_gSelPath.has(o.key)?'checked':''} onchange="gPathPick('${o.key.replace(/'/g,"\\'")}',this.checked)"> ${escH(o.o)} → ${escH(o.d)}</label>`).join('')
      :`<div class="muted" style="padding:6px;font-size:11px">No paths.</div>`);
  q('ms-gpath-btn').textContent='Paths: '+(_gSelPath.size===0?'All':_gSelPath.size+' selected')+' ▾';
}
function gPathAll(on){ _gSelPath.clear(); gPathRender(); redrawScatter(); }
function gPathPick(k,on){ if(on)_gSelPath.add(k); else _gSelPath.delete(k); gPathRender(); redrawScatter(); }
function gsecAll(on){ _gSelSec.clear(); _gSelPath.clear(); gsecRender(); gPathRender(); redrawScatter(); }
function gsecPick(id,on){ if(on)_gSelSec.add(id); else _gSelSec.delete(id);
  const valid=new Set(gPathOptions().map(x=>x.key)); [..._gSelPath].forEach(k=>{if(!valid.has(k))_gSelPath.delete(k);});
  gsecRender(); gPathRender(); redrawScatter(); }
// Canonical route identity. Persisted matrix labels and dispatch data have historically used
// aliases such as TOFU/TF, KRENE/KR, POS12/POS 12 and FENI KM 15/FENI KM15. Treat them as the
// same route so a valid section selection can never produce an empty chart through spelling alone.
function routeName(v,isOrigin){
  let s=String(v==null?'':v).trim().toUpperCase().replace(/\s+/g,' ');
  if(isOrigin){
    if(s==='TOFU') s='TF';
    if(s==='KRENE'||s==='KRNE'||s==='KRE') s='KR';
  }
  s=s.replace(/^POS[ _]*(\d+)$/,'POS $1');
  s=s.replace(/^FENI(?:[ _]*KM)?[ _]*(\d+)$/,'FENI KM$1');
  return s;
}
function pathKey(o,d){ return routeName(o,true)+'>'+routeName(d,false); }
function setFilterMode(m){
  _filterMode=m;
  q('fm-sd').classList.toggle('on',m==='sd'); q('fm-path').classList.toggle('on',m==='path');
  q('fm-sd-ctrls').style.display=m==='sd'?'':'none'; q('fm-path-ctrls').style.display=m==='path'?'':'none';
  if(m==='path'){ pathRender(); }
}
// available paths for the top-bar Path picker = all actual routes (section-based scoping lives on the
// graph now, client-side — the top bar only picks whole paths and reloads the data window)
function availPaths(){
  const seen=new Set(), out=[];
  ((_D&&_D.routes)||[]).forEach(r=>{ const k=pathKey(r.origin,r.dest); if(!seen.has(k)){seen.add(k); out.push({key:k,o:r.origin,d:r.dest});} });
  return out.sort((a,b)=>(a.o+a.d).localeCompare(b.o+b.d));
}
function pathRender(){
  const p=q('ms-path-panel');
  p.innerHTML=`<div style="padding:4px 4px 6px"><input id="path-search" placeholder="🔍 search paths…" value="${escH(_pathSearch)}" oninput="_pathSearch=this.value; pathRenderList()" onclick="event.stopPropagation()" style="width:100%;box-sizing:border-box;background:#0d1524;border:1px solid var(--line);border-radius:6px;color:var(--txt);font-size:12px;padding:5px 7px"></div><div id="ms-path-list"></div>`;
  pathRenderList();
}
function pathRenderList(){
  const c=q('ms-path-list'); if(!c) return;
  const qv=(_pathSearch||'').toLowerCase();
  let opts=availPaths(); if(qv) opts=opts.filter(o=>(o.o+' → '+o.d).toLowerCase().includes(qv));
  c.innerHTML=`<label class="all"><input type="checkbox" ${_selPath.size===0?'checked':''} onchange="pathAll(this.checked)"> All paths</label>`+
    (opts.length?opts.map(o=>`<label><input type="checkbox" ${_selPath.has(o.key)?'checked':''} onchange="pathPick('${o.key.replace(/'/g,"\\'")}',this.checked)"> ${escH(o.o)} → ${escH(o.d)}</label>`).join('')
      :`<div class="muted" style="padding:6px;font-size:11px">No matching paths.</div>`);
  q('ms-path-btn').textContent='Paths: '+(_selPath.size===0?'All':_selPath.size+' selected')+' ▾';
}
function pathAll(on){ _selPath.clear(); pathRenderList(); }
function pathPick(k,on){ if(on)_selPath.add(k); else _selPath.delete(k); pathRenderList(); }
// the origin>dest set sent to the server in path mode: explicit picks → else all-through-sections → else none (all)
function effectivePaths(){
  const avail=availPaths().map(x=>x.key), aset=new Set(avail);
  const picked=[..._selPath].filter(k=>aset.has(k));
  return picked.length ? picked : [];
}
function filterParams(){
  const o={from:q('f-from').value,to:q('f-to').value};
  if(_selType.size) o.types=[..._selType].join(',');
  if(q('excl-iwip') && !q('excl-iwip').checked) o.inclIwip='1';   // checkbox checked = exclude (default)
  if(_filterMode==='path'){ const ep=effectivePaths(); if(ep.length) o.paths=ep.join('~'); }
  else { o.source=[..._selSrc].join(','); o.dest=[..._selDest].join(','); }
  return new URLSearchParams(o);
}
function _matNextId(){ let m=0; _matEdit.secs.forEach(s=>{if(s.id>m)m=s.id;}); return m+1; }
function openMatrix(){
  const secs=(_matrix.sections||[]).map(s=>({id:s.id,name:s.name}));
  const sel={}; (_matrix.paths||[]).forEach(p=>{ sel[pathKey(p.origin,p.dest)]={o:p.origin,d:p.dest,secs:new Set(p.sections||[])}; });
  // Keep the agreed mappings checked at the top, then offer every other route in the current data
  // window underneath as an unchecked candidate. Unchecked candidates are not persisted on Save.
  ((_D&&_D.routes)||[]).forEach(r=>{ const k=pathKey(r.origin,r.dest); if(!sel[k]) sel[k]={o:r.origin,d:r.dest,secs:new Set()}; });
  _matEdit={secs,sel}; q('mat-backdrop').style.display='flex'; renderMatrix();
  loadModelStatus();
}
function closeMatrix(){ q('mat-backdrop').style.display='none'; }

// ── Prediction-model status + retrain (admin) ───────────────────────────────
// R² alone flatters a model, so the status line always pairs it with the lift
// over a plain per-route lookup. If that lift is negligible the model is a
// lookup table wearing a hat, and the line says so.
function _modelLine(m){
  if(!m||!m.trained)return 'No trained model — predictions use the OLS fallback.';
  const lift=m.baseline_lift, has=Number.isFinite(lift);
  const when=m.trained_at?String(m.trained_at).slice(0,10):'unknown date';
  const rows=Number.isFinite(m.training_rows)?fmt(m.training_rows)+' rows · ':'';
  let s=`${escH(m.model_type||'model')} · trained ${escH(when)} · ${rows}R² ${fmt(m.r2,3)}`;
  if(has)s+=` · lift ${lift>=0?'+':''}${fmt(lift*100,1)}% over lookup`;
  if(has&&lift<0.01)s+=' ⚠ barely better than historical averages';
  // The cycle model is a second model on a second table. It was reachable only
  // by curl, which meant the operator could not tell whether it was trained,
  // how old it was, or that it misses its own R2 bar while beating the lookup
  // on MAE. Both halves of that verdict are shown, never one.
  const c=m.cycle_model;
  if(c&&c.cv_mae_min!=null){
    s+=`\nCycle model · ${fmt(c.rows)} rows${c.date_range?` to ${escH(String(c.date_range[1]))}`:''}`
      +` · ±${fmt(c.cv_mae_min,0)} min vs ±${fmt(c.baseline_cv_mae_min,0)} for a route average`;
    // 3 dp: the lift is 0.0085 and fmt() to fewer places renders it as a bare
    // "0", which reads as "no improvement at all" rather than "real but small".
    if(c.beats_baseline===false)s+=` · R² lift ${(c.lift_over_baseline??0).toFixed(3)} misses the ${(c.min_lift_required??0.05).toFixed(2)} bar`;
  }else{
    s+='\nCycle model · not trained (run python cycle_pipeline.py && python cycle_model.py)';
  }
  return s;
}
async function loadModelStatus(){
  const el=q('retrain-status'); if(!el)return;
  try{ const m=await(await fetch('/api/model-info',{cache:'no-store'})).json();
    el.textContent=_modelLine(m); }
  catch(e){ el.textContent='Model status unavailable.'; }
}
async function retrainModel(){
  const btn=q('retrain-btn'), el=q('retrain-status'); if(!btn)return;
  // Honest duration: retrain now rebuilds the cycle model too, which
  // re-extracts ~663k trip rows over the VPN. Promising 30-60s made a working
  // 5-minute job look hung.
  if(!confirm('This retrains the tonnage AND cycle models (~5 minutes over the VPN). Retrain now?'))return;
  const label=btn.textContent;
  btn.disabled=true; btn.textContent='⟳ Retraining…';
  if(el)el.textContent='Extracting data and training both models — this takes several minutes…';
  try{
    const r=await fetch('/api/retrain',{method:'POST'});
    const d=await r.json();
    if(!r.ok||!d.ok)throw new Error((d&&d.error)||('HTTP '+r.status));
    const lift=d.baseline_lift, has=Number.isFinite(lift);
    if(el)el.innerHTML=`<span class="${has&&lift<0.01?'ea':'eg'}">✓ Retrained in ${fmt(d.elapsed_s,1)}s — `
      +`${escH(d.model_type)} · R² ${fmt(d.r2,3)} · MAE ${fmt(d.mae,3)}`
      +(has?` · lift ${lift>=0?'+':''}${fmt(lift*100,1)}% over lookup`:'')
      +`</span><br><span class="muted">${fmt(d.training_rows)} training rows · ${escH(d.data_source||'')}`
      +(d.cycle_model?` · cycle model: ${escH(String(d.cycle_model))}`:'')+`</span>`;
    // The server hot-swaps its cached model, so the next estimate uses the new
    // one. Re-render the open Plan tab so the badge updates without a reload.
    if(typeof planPreview==='function')planPreview();
  }catch(e){
    if(el)el.innerHTML=`<span class="er">✗ Retrain failed: ${escH(e.message)}</span>`;
  }finally{
    btn.disabled=false; btn.textContent=label;
  }
}
function matAddSection(){ _matEdit.secs.push({id:_matNextId(),name:'New section'}); renderMatrix(); }
function matDelSection(id){ _matEdit.secs=_matEdit.secs.filter(s=>s.id!==id); Object.values(_matEdit.sel).forEach(v=>v.secs.delete(id)); renderMatrix(); }
function matRename(id,v){ const s=_matEdit.secs.find(x=>x.id===id); if(s)s.name=v; }
function matToggle(k,id,on){ const v=_matEdit.sel[k]; if(!v)return; if(on)v.secs.add(id); else v.secs.delete(id); }
function renderMatrix(){
  const secs=_matEdit.secs;
  // selected paths (any section ticked) first, then the rest — each alphabetical — so picks are easy to see
  const keys=Object.keys(_matEdit.sel).sort((a,b)=>{
    const ta=_matEdit.sel[a].secs.size>0, tb=_matEdit.sel[b].secs.size>0;
    if(ta!==tb) return ta?-1:1;
    return a.localeCompare(b);
  });
  let h='<div style="margin-bottom:14px"><div style="font-size:11px;color:var(--muted2);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Sections</div>';
  h+=secs.map(s=>`<span style="display:inline-flex;align-items:center;gap:3px;margin:0 6px 6px 0"><input value="${escH(s.name)}" oninput="matRename(${s.id},this.value)" style="background:#0d1524;border:1px solid var(--line);border-radius:6px;color:var(--txt);font-size:12px;padding:4px 7px;width:130px"><button onclick="matDelSection(${s.id})" title="Delete section" style="background:none;border:0;color:#f87171;cursor:pointer;font-size:15px">×</button></span>`).join('');
  h+=`<button class="ms-btn" style="min-width:0;cursor:pointer;font-size:12px" onclick="matAddSection()">+ section</button></div>`;
  h+='<div style="font-size:11px;color:var(--muted2);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Paths — tick the sections each path runs through</div>';
  h+='<table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr><th style="text-align:left;padding:5px 8px;color:var(--muted2)">Path</th>'+
    secs.map(s=>`<th style="padding:5px 6px;color:var(--muted2);white-space:nowrap">${escH(s.name)}</th>`).join('')+'</tr></thead><tbody>';
  h+=(keys.length?keys.map(k=>{ const v=_matEdit.sel[k];
    return `<tr style="border-top:1px solid var(--line)"><td style="padding:5px 8px;color:var(--txt);white-space:nowrap">${escH(v.o)} → ${escH(v.d)}</td>`+
      secs.map(s=>`<td style="text-align:center;padding:5px 6px"><input type="checkbox" ${v.secs.has(s.id)?'checked':''} onchange="matToggle('${k.replace(/'/g,"\\'")}',${s.id},this.checked)"></td>`).join('')+'</tr>';
  }).join(''):`<tr><td colspan="${secs.length+1}" style="padding:10px;color:var(--muted2)">Load data first (routes come from the current window).</td></tr>`);
  h+='</tbody></table>';
  q('mat-body').innerHTML=h;
}
