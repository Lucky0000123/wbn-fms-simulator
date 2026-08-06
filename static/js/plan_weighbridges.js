// ── Fleet-plan ↔ weighbridge linkage (interactive) ───────────────────────────
// Joins the Plan tab's "Weighbridges open" number to the weighbridges that
// ACTUALLY serve the selected source→dest haul (measured from tickets via
// /api/simulator/weighbridge-by-path). Behaviour:
//   • lists the weighbridges historically used on the route as clickable chips
//     (multi-select), sorted by usage share;
//   • two-way link with the "Weighbridges open" count — typing a count selects
//     the top-N by usage; toggling chips sets the count to the selection size;
//   • caps at the historical max — asking for more than the route has ever used
//     clamps and tells the user the max.
// The count is what plan.js already feeds into its capacity check, so selecting
// bridges flows straight into the estimate.
//
// Wired by listeners so plan.js stays UNTOUCHED. IIFE — nothing leaks to globals.
(function(){
  let _bridges = [];            // [{wb, sharePct, trips}] used on the route, desc by trips
  let _n = 0;                   // historical max = distinct bridges that carried the route
  let _sel = new Set();         // currently selected wb ids
  let _route = { s: '', d: '' };
  let _cached = false;
  let _excluded = 0;            // incidental (<min share) bridges hidden by the server
  let _minShare = 1;
  let _lastKey = '';
  let _syncing = false;         // guard: programmatic #plan-wb writes must not re-trigger us

  const el = id => document.getElementById(id);
  const escH = x => String(x == null ? '' : x).replace(/[&<>"]/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const pct = v => (v == null ? '' : Math.round(v) + '%');

  function route(){
    const s = (el('plan-src') || {}).value || '';
    const d = (el('plan-dst') || {}).value || '';
    return { s, d, key: s + '>' + d };
  }

  function load(){
    const host = el('plan-wb-onpath');
    if (!host) return;
    const { s, d, key } = route();
    if (!s || !d){ host.innerHTML = ''; _lastKey = ''; _bridges = []; _n = 0; _sel.clear(); return; }
    if (key === _lastKey) return;
    _lastKey = key;
    host.innerHTML = '<span class="muted" style="font-size:10.5px">Checking weighbridges on this route…</span>';
    const qs = new URLSearchParams({ source: s, dest: d });
    const frm = (el('f-from') || {}).value, to = (el('f-to') || {}).value;
    if (frm) qs.set('from', frm);
    if (to)  qs.set('to', to);
    fetch('/api/simulator/weighbridge-by-path?' + qs.toString())
      .then(r => r.json())
      .then(res => { if (key === _lastKey) init(res, s, d); })
      .catch(() => { host.innerHTML = ''; });
  }

  function init(res, s, d){
    const all = (res && res.bridges) || [];
    _bridges = all.filter(b => b.trips > 0).sort((a, b) => b.trips - a.trips);
    _n = _bridges.length;
    _cached = !!(res && res.servedFrom === 'fixture');
    _excluded = (res && res.excludedMinorBridges) || 0;
    if (res && res.minSharePct != null) _minShare = res.minSharePct;
    _route = { s, d };
    _sel = new Set(_bridges.map(b => b.wb));   // default: all bridges used on the route
    const wb = el('plan-wb');
    if (wb) wb.max = _n || 1;                    // cap the stepper at the historical max
    setPlanWb(_sel.size);
    renderChips();
  }

  // Write the count into #plan-wb and let plan.js's own oninput=computePlan() run,
  // without re-entering our own input handler.
  function setPlanWb(v){
    const wb = el('plan-wb');
    if (!wb) return;
    _syncing = true;
    wb.value = v;
    wb.dispatchEvent(new Event('input', { bubbles: true }));
    _syncing = false;
  }

  // User asked for k bridges → select the top-k by usage, clamped to the max.
  function applyCount(k){
    let clamped = false;
    if (k > _n){ k = _n; clamped = true; }
    if (k < 1) k = 1;
    _sel = new Set(_bridges.slice(0, k).map(b => b.wb));
    setPlanWb(_sel.size);
    renderChips(clamped
      ? `Max on this route is ${_n} — only ${_n} weighbridge${_n === 1 ? '' : 's'} have carried ${escH(_route.s)} → ${escH(_route.d)} in the data.`
      : '');
  }

  function toggleChip(wb){
    if (_sel.has(wb)){
      if (_sel.size <= 1) return;               // keep at least one selected
      _sel.delete(wb);
    } else {
      _sel.add(wb);
    }
    setPlanWb(_sel.size);
    renderChips();
  }

  function renderChips(note){
    const host = el('plan-wb-onpath');
    if (!host) return;
    if (!_n){
      host.innerHTML = '<span class="muted" style="font-size:10.5px">No weighbridge tickets found for this route in the selected window.</span>';
      return;
    }
    const chips = _bridges.map(b => {
      const on = _sel.has(b.wb);
      return `<span data-wb="${escH(b.wb)}" class="wb-chip" title="${escH(b.wb)} — ${pct(b.sharePct)} of this route's weighs"`
        + ` style="cursor:pointer;display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;border-radius:12px;`
        + `border:1px solid ${on ? '#f59e0b' : 'var(--line)'};background:${on ? 'rgba(245,158,11,.16)' : 'transparent'};`
        + `color:${on ? 'var(--txt)' : 'var(--muted)'};font-size:10.5px">${escH(b.wb)} <span style="opacity:.7">${pct(b.sharePct)}</span></span>`;
    }).join('');
    host.innerHTML =
      `<div style="font-size:10.5px;line-height:1.5">`
      + `<b style="color:var(--txt)">${_n}</b> weighbridge${_n === 1 ? '' : 's'} used on <b>${escH(_route.s)} → ${escH(_route.d)}</b>`
      + (_cached ? ' <span class="muted">(sample data)</span>' : '')
      + ` <span class="muted">· click to choose — the count links to “Weighbridges open”</span>`
      + `<div style="margin-top:4px">${chips}</div>`
      + (note ? `<div style="margin-top:3px;color:#f59e0b">${note}</div>` : '')
      + `<div class="muted" style="margin-top:2px"><b>${_sel.size}</b> selected of ${_n} max on this route`
      + (_excluded > 0 ? ` · ${_excluded} incidental bridge${_excluded === 1 ? '' : 's'} (&lt;${_minShare}% of weighs) hidden` : '')
      + `</div>`
      + `</div>`;
  }

  function onWbInput(){
    if (_syncing) return;                        // our own programmatic write — ignore
    if (!_n) return;
    const wb = el('plan-wb');
    if (!wb) return;
    const k = parseInt(wb.value, 10);
    if (isNaN(k)) return;
    applyCount(k);
  }

  function wire(){
    ['plan-src', 'plan-dst'].forEach(id => {
      const e = el(id);
      if (e && !e._wbWired){ e.addEventListener('change', load); e._wbWired = true; }
    });
    const wb = el('plan-wb');
    if (wb && !wb._wbWired){ wb.addEventListener('input', onWbInput); wb._wbWired = true; }
    load();
  }

  // Delegated clicks: chip toggles, and re-wire when the Plan tab opens.
  document.addEventListener('click', function(ev){
    const chip = ev.target && ev.target.closest ? ev.target.closest('.wb-chip') : null;
    if (chip && chip.dataset && chip.dataset.wb){ toggleChip(chip.dataset.wb); return; }
    if (ev.target && ev.target.id === 'tabbtn-plan') setTimeout(wire, 60);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
