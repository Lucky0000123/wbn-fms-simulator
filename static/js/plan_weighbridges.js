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
    host.innerHTML = '<div class="plan-wb-path"><div class="plan-wb-path-h muted">Checking bridges…</div></div>';
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
      ? `Max ${_n} on this route — only ${_n} bridge${_n === 1 ? '' : 's'} in the data.`
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
      host.innerHTML = '<div class="plan-wb-path"><div class="plan-wb-path-h muted">No weighbridge tickets on this route in the window.</div></div>';
      return;
    }
    const chips = _bridges.map(b => {
      const on = _sel.has(b.wb);
      return `<button type="button" data-wb="${escH(b.wb)}" class="wb-chip${on ? ' on' : ''}"`
        + ` title="${escH(b.wb)} — ${pct(b.sharePct)} of this route's weighs · click to toggle">`
        + `${escH(b.wb)} <span class="wb-chip-pct">${pct(b.sharePct)}</span></button>`;
    }).join('');
    host.innerHTML =
      `<div class="plan-wb-path">`
      + `<div class="plan-wb-path-h">`
      + `<b>${escH(_route.s)} → ${escH(_route.d)}</b>`
      + `<span class="muted">${_sel.size}/${_n} bridges`
      + (_cached ? ' · sample' : '')
      + (_excluded > 0 ? ` · ${_excluded} incidental hidden` : '')
      + `</span></div>`
      + `<div class="plan-wb-chips">${chips}</div>`
      + (note ? `<div class="plan-wb-path-note">${note}</div>` : '')
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

  // ── Per-path weighbridges in the plan table (section 3) ───────────────────
  // When a path is added, snapshot the weighbridges chosen for it; show them as
  // editable chips under that path's row so the planner can see/remove per path.
  // plan.js stores no weighbridges per path, so we keep our own map keyed by the
  // same id it uses (contractor|src>dst) and wrap its two globals at runtime —
  // its source stays untouched.
  let _pathWb = {};

  function snapshotAddedPath(){
    const s = (el('plan-src') || {}).value || '', d = (el('plan-dst') || {}).value || '';
    if (!s || !d) return;
    let name = '—';
    try { if (typeof planContractor === 'function'){ const c = planContractor(); if (c && c.name) name = c.name; } } catch (e) {}
    const id = name + '|' + s + '>' + d;
    if (typeof _planDraft !== 'undefined' && _planDraft[id] && _bridges.length){
      // ONE bridge per path by default — the route's historical top bridge.
      // Reassign from the collapsed alternates; utilisation colouring shows
      // when two paths pile onto the same bridge.
      _pathWb[id] = { bridges: _bridges.map(b => ({ wb: b.wb, sharePct: b.sharePct })),
                      sel: new Set([_bridges[0].wb]), open: false };
    }
  }

  // Trips a path contributes this shift (mirrors plan.js maths).
  function pathTrips(id){
    try {
      const r = typeof _planDraft !== 'undefined' ? _planDraft[id] : null;
      if (!r || !(r.dt > 0)) return 0;
      if (r.foreign && Number.isFinite(r.measTrips)){
        const rate = r.measTrucks ? r.measTrips / r.measTrucks : 0;
        return r.dt * rate;
      }
      if (typeof planTripsPerDT === 'function'){
        const rain = Math.max(0, parseFloat((el('plan-rain') || {}).value) || 0);
        const c = typeof planContractor === 'function' ? planContractor(r.contractor) : null;
        const e = planTripsPerDT(r.key, r.dt, rain, c);
        if (e) return r.dt * e.shift;
      }
    } catch (e) {}
    return 0;
  }

  // Per-bridge utilisation across the whole holding plan: each path's trips go
  // to its assigned bridge(s) (split evenly when >1). Ceiling per bridge =
  // PLAN_WB_TRIPS_PER_HOUR x shift hours (same basis as the WB-load bar).
  function bridgeUtil(){
    const hours = Math.max(1, parseFloat((el('plan-hours') || {}).value) || 12);
    const perH = (typeof PLAN_WB_TRIPS_PER_HOUR !== 'undefined') ? PLAN_WB_TRIPS_PER_HOUR : 30;
    const cap = perH * hours;
    const byWb = {};
    Object.keys(_pathWb).forEach(id => {
      const pw = _pathWb[id];
      if (!pw || !pw.sel.size) return;
      const t = pathTrips(id) / pw.sel.size;
      if (!(t > 0)) return;
      const label = id.split('|').slice(1).join('|').replace('>', ' → ');
      pw.sel.forEach(wb => {
        const rec = byWb[wb] || (byWb[wb] = { trips: 0, paths: [] });
        rec.trips += t;
        rec.paths.push(label);
      });
    });
    return { byWb, cap };
  }

  function injectPathWb(){
    const tbody = el('plan-rows');
    if (!tbody) return;
    _lastUtil = bridgeUtil();
    if (typeof _planDraft !== 'undefined') Object.keys(_pathWb).forEach(id => { if (!_planDraft[id]) delete _pathWb[id]; });
    Array.prototype.forEach.call(tbody.querySelectorAll('tr'), tr => {
      if (tr.className === 'pwb-row') return;
      const a = tr.querySelector('a[onclick^="planRemove"]');
      if (!a) return;
      const mm = /planRemove\('([^']*)'\)/.exec(a.getAttribute('onclick') || '');
      if (!mm) return;
      const pw = _pathWb[mm[1]];
      if (!pw || !pw.bridges.length) return;
      const next = tr.nextSibling;
      if (next && next.className === 'pwb-row') return;   // already injected
      const { byWb, cap } = _lastUtil || bridgeUtil();
      const colFor = u => u >= 1 ? '#ef4444' : u >= 0.7 ? '#f59e0b' : '#22c55e';
      const bgFor  = u => u >= 1 ? 'rgba(239,68,68,.16)' : u >= 0.7 ? 'rgba(245,158,11,.16)' : 'rgba(34,197,94,.14)';
      const assigned = [...pw.sel].map(wb => {
        const rec = byWb[wb] || { trips: 0, paths: [] };
        const u = cap ? rec.trips / cap : 0;
        const sharedWith = rec.paths.length > 1
          ? ` · SHARED with ${rec.paths.length - 1} other path(s) — congested; pick another WB`
          : '';
        return `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(wb)}"`
          + ` title="WB ${escH(wb)} · ${Math.round(100 * u)}% of its ${Math.round(cap)}-trip shift ceiling${sharedWith} · click to unassign"`
          + ` style="cursor:pointer;display:inline-block;margin:1px 4px 1px 0;padding:1px 8px;border-radius:11px;font-weight:600;`
          + `border:1px solid ${colFor(u)};background:${bgFor(u)};color:var(--txt)">`
          + `WB ${escH(wb)} <span style="opacity:.85">${Math.round(100 * u)}%</span>`
          + (rec.paths.length > 1 ? ' ⚠' : '') + `</span>`;
      }).join('');
      const alternates = pw.open
        ? pw.bridges.filter(b => !pw.sel.has(b.wb)).map(b =>
            `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(b.wb)}"`
            + ` title="assign WB ${escH(b.wb)} (${pct(b.sharePct)} of this route's historical weighs)"`
            + ` style="cursor:pointer;display:inline-block;margin:1px 3px 1px 0;padding:1px 7px;border-radius:11px;`
            + `border:1px dashed var(--line);color:var(--muted)">+ ${escH(b.wb)} <span style="opacity:.6">${pct(b.sharePct)}</span></span>`
          ).join('')
        : '';
      const toggle = pw.bridges.length > pw.sel.size
        ? `<span class="pwb-toggle" data-pwid="${escH(mm[1])}"`
        + ` style="cursor:pointer;font-size:9.5px;color:var(--muted);text-decoration:underline dotted">`
        + (pw.open ? 'hide' : 'change WB') + `</span>`
        : '';
      const sub = document.createElement('tr');
      sub.className = 'pwb-row';
      sub.innerHTML = `<td></td><td colspan="8" style="font-size:10px;padding:0 0 7px">`
        + `<span class="muted">WB:</span> ${assigned} ${alternates} ${toggle}</td>`;
      tr.parentNode.insertBefore(sub, tr.nextSibling);
    });
  }
  let _lastUtil = null;

  // Wrap plan.js globals at runtime (source untouched). planAddPath already calls
  // computePlan() before we snapshot, so re-run it after snapshotting.
  if (typeof planAddPath === 'function'){
    const _origAdd = planAddPath;
    planAddPath = function(){
      const r = _origAdd.apply(this, arguments);
      try { snapshotAddedPath(); if (typeof computePlan === 'function') computePlan(); } catch (e) {}
      return r;
    };
  }
  if (typeof computePlan === 'function'){
    const _origCompute = computePlan;
    computePlan = function(){
      const r = _origCompute.apply(this, arguments);
      try { injectPathWb(); } catch (e) {}
      return r;
    };
  }

  // Delegated clicks: top-panel chips, per-path chips, and re-wire on tab open.
  document.addEventListener('click', function(ev){
    const t = ev.target;
    const ptog = t && t.closest ? t.closest('.pwb-toggle') : null;
    if (ptog){
      const pw = _pathWb[ptog.getAttribute('data-pwid')];
      if (pw){ pw.open = !pw.open; if (typeof computePlan === 'function') computePlan(); }
      return;
    }
    const pchip = t && t.closest ? t.closest('.pwb-chip') : null;
    if (pchip){
      const id = pchip.getAttribute('data-pwid'), wb = pchip.getAttribute('data-wb');
      const pw = _pathWb[id];
      if (pw){
        if (pw.sel.has(wb)){ if (pw.sel.size > 1) pw.sel.delete(wb); }
        else { pw.sel.add(wb); pw.open = false; }
        if (typeof computePlan === 'function') computePlan();
      }
      return;
    }
    const chip = t && t.closest ? t.closest('.wb-chip') : null;
    if (chip && chip.dataset && chip.dataset.wb){ toggleChip(chip.dataset.wb); return; }
    if (t && t.id === 'tabbtn-plan') setTimeout(wire, 60);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
