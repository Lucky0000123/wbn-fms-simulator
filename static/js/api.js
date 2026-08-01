// api.js — API / data loading — every fetch() against the Flask endpoints.
// Falls back to the sample fixtures automatically (server-side).
// Extracted verbatim from templates/simulator.html (Phase 1 refactor; no logic changes).

async function loadMatrix(){
  try{ const d=await(await fetch('/api/simulator/constraints',{cache:'no-store'})).json();
    if(d&&d.ok&&(d.sections||[]).length) _matrix={sections:d.sections||[],paths:d.paths||[]}; }
  catch(e){ _matrix=matrixCopy(_MATRIX_DEFAULT); }
}
async function resetMatrix(){
  if(!confirm('Reset the matrix to the built-in default (8 paths)? This discards custom edits.')) return;
  try{ const d=await(await fetch('/api/simulator/constraints/reset',{method:'POST'})).json();
    if(d&&d.ok){ _matrix={sections:d.sections||[],paths:d.paths||[]}; _gSelSec.clear();
      openMatrix(); gsecRender(); gPathRender(); redrawScatter(); } }
  catch(e){ alert('Reset failed: '+e.message); }
}
async function saveMatrix(){
  const paths=[]; Object.values(_matEdit.sel).forEach(v=>{ if(v.secs.size) paths.push({origin:v.o,dest:v.d,sections:[...v.secs]}); });
  const body={sections:_matEdit.secs.map(s=>({id:s.id,name:(s.name||'').trim()||('Section '+s.id)})),paths};
  try{ const d=await(await fetch('/api/simulator/constraints',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(d&&d.ok){ _matrix={sections:d.sections||[],paths:d.paths||[]};
      const validSec=new Set(_matrix.sections.map(s=>s.id));
      [..._gSelSec].forEach(id=>{if(!validSec.has(id))_gSelSec.delete(id);});
      pathRender(); gsecRender(); gPathRender(); redrawScatter(); closeMatrix(); }
    else alert('Save failed: '+((d&&d.error)||'unknown')); }
  catch(e){ alert('Save failed: '+e.message); }
}
// Generation counter: a second Apply while the first is still in flight must not
// let the slower (stale) response overwrite the newer filter window.
let _loadGen=0;
async function load(){
  const gen=++_loadGen;
  const t0=performance.now();
  q('loading').style.display=''; q('loading').textContent='Loading capability…';
  q('content').style.display='none';
  const p=filterParams();
  let d; try{ d=await(await fetch('/api/simulator/capability?'+p,{cache:'no-store'})).json(); }
  catch(e){
    if(gen!==_loadGen) return;
    q('loading').textContent='Could not load — try again.';
    return;
  }
  if(gen!==_loadGen) return;          // superseded by a newer Apply
  if(!d||!d.ok){ q('loading').textContent=(d&&d.error)||'No data.'; return; }
  _D=d; q('loading').style.display='none'; q('content').style.display='';
  _initDone=true;
  typeRender();
  msRender('source'); msRender('dest');
  if(_filterMode==='path'){ pathRender(); }
  gsecRender(); gPathRender();
  render();
  loadTrucks();
  // Rain / path-response used to load once at init and ignore Apply. Re-fetch
  // with the same filter bar so the rainfall table tracks the date window.
  loadPathResp();
  // Surface the round-trip so a regression back to per-request SQL is visible
  // in the console without opening the network tab.
  console.info('[capability] %.0f ms  %s..%s  iwip=%s',
    performance.now()-t0, d.from||'', d.to||'', d.inclIwip?'incl':'excl');
}
async function loadTrucks(){
  const p=filterParams();
  q('trucks').innerHTML='<tr><td colspan="6" class="empty">Loading truck list…</td></tr>'; _trucks=null; _trucksServedFrom=null;
  try{ const d=await(await fetch('/api/simulator/trucks?'+p,{cache:'no-store'})).json();
    _trucks=(d&&d.ok)?d.trucks:[]; _trucksServedFrom=(d&&d.servedFrom)||null;
    if(!d||!d.ok){ q('trucks').innerHTML='<tr><td colspan="6" class="empty">'+((d&&d.error)||'Unavailable')+'</td></tr>'; return; }
  }catch(e){ q('trucks').innerHTML='<tr><td colspan="6" class="empty">Could not load trucks.</td></tr>'; return; }
  renderTrucks();
}
async function loadPathResp(){
  const body=q('cap-rain');
  if(body) body.innerHTML='<tr><td colspan="5" class="muted">Loading rainfall-matched route history…</td></tr>';
  const p=filterParams();
  try{
    const t0=performance.now();
    const d=await(await fetch('/api/simulator/path-response?'+p,{cache:'no-store'})).json();
    if(d&&d.ok){
      _pathResp=d.paths||{};
      renderRainContext();
      if(_flowSim)evaluateFlowScenario();
      if(q('tabbtn-plan')&&q('tabbtn-plan').classList.contains('on'))renderPlanBuilder();
      console.info('[path-response] %.0f ms  paths=%d  %s..%s',
        performance.now()-t0, Object.keys(_pathResp).length, d.from||'', d.to||'');
    }else renderRainContext(d&&d.error);
  }catch(e){renderRainContext('Rainfall history unavailable');}
}
async function loadCapabilityWeighbridge(){
  const status=q('cap-wb-status');
  try{
    const d=await(await fetch('/api/weighbridge-summary',{cache:'no-store'})).json();
    if(!d||!d.ok) throw new Error(d&&d.error||'Weighbridge activity unavailable');
    q('cap-wb-open').textContent=fmt(d.bridges);
    q('cap-wb-trucks').textContent=fmt(d.trucks);
    q('cap-wb-share').textContent=fmt(d.busiestShare,1)+'%';
    q('cap-wb-other').textContent=fmt(d.otherShare,1)+'%';
    const critical=d.busiestShare>40, watch=d.busiestShare>25;
    status.style.borderLeftColor=critical?'#ef4444':watch?'#f59e0b':'#22c55e';
    // Honesty: HAULAGE_IWIP_CLEAN ends mid-July 2026. Say the as-of date and
    // when the table is stale — do not imply a live feed.
    const age=(d.ageDays!=null)?(` · ${d.ageDays}d old`):'';
    const tag=d.servedFrom==='fixture'?' (fixture)'
      :(d.stale?` (stale — table ends ${d.date||'?'}${age})`:'');
    status.textContent=`${critical?'🔴':watch?'🟡':'🟢'} ${d.status} · ${d.perBridge} trucks/bridge · busiest ${d.busiest||'—'} · as of ${d.date||'latest'}${tag}`;
  }catch(e){status.style.borderLeftColor='#64748b';status.textContent=e.message;}
}
async function loadShiftContext(date){date=(date||'').slice(0,10);if(!date||date===_shiftCtxDate)return;_shiftCtxDate=date;
  try{const d=await(await fetch('/api/simulator/shift-context?date='+encodeURIComponent(date)+_shParam(),{cache:'no-store'})).json();if(d&&d.ok)renderShiftContext(d);}catch(e){}}
async function loadWbPositions(tries,date){tries=tries||0;date=(date||(_flowPointScenario&&_flowPointScenario.date)||'').slice(0,10);try{const d=await(await fetch('/api/simulator/weighbridge-positions'+(date?'?date='+encodeURIComponent(date)+_shParam():''),{cache:'no-store'})).json();
    if(d&&d.ok&&d.positions&&d.positions.length){_wbPos=d.positions;_wbPosDate=d.date||date||null;if(_flowSource&&_flowSim&&!_flowSim.running&&_flowSim.hour===0)renderFlowSimulator(_flowSource.P,_flowSource.colours,true);return;}
  }catch(e){}
  if(tries<4)setTimeout(()=>loadWbPositions(tries+1,date),1500);}
async function loadWeighbridge(){
  const note=q('wb-note');if(note)note.textContent='Loading measured weighbridge history…';
  try{const d=await(await fetch('/api/simulator/weighbridge',{cache:'no-store'})).json();
    if(!d||!d.ok){if(note)note.textContent=(d&&d.error)||'Weighbridge history unavailable.';return;}
    _wbData=d;renderWeighbridge();
  }catch(e){if(note)note.textContent='Could not load: '+e.message;}
}
async function loadCongModel(){
  const note=q('cong-note');if(note)note.textContent='Loading measured segment data…';
  try{const d=await(await fetch('/api/simulator/congestion-model',{cache:'no-store'})).json();
    if(!d||!d.ok){if(note)note.textContent=(d&&d.error)||'Congestion data unavailable.';return;}
    _congData=d;const sel=q('cong-seg');sel.innerHTML=(d.segments||[]).map(s=>`<option value="${escH(s.seg)}">${escH(s.seg)} — ${s.n} hrs</option>`).join('');
    renderCongModel();
  }catch(e){if(note)note.textContent='Could not load: '+e.message;}
}
