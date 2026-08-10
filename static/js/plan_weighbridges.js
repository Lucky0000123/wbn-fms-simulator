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
    // SINGLE-SELECT: the planner picks the bridge NUMBER this path will use.
    // Default suggestion = the route's historical top bridge (or WB 1 when the
    // route has no ticket history) — but ANY bridge is selectable.
    _sel = new Set([_bridges.length ? _bridges[0].wb : '1']);
    syncWbCount();
    renderChips();
  }

  // #plan-wb is now a DERIVED count: distinct bridges assigned across the
  // holding plan (plus the picker's bridge for the path being built). It still
  // feeds plan.js's WB-ceiling maths, but nobody types a count any more.
  function syncWbCount(){
    const used = new Set(_sel);
    Object.keys(_pathWb).forEach(id => {
      const pw = _pathWb[id];
      if (pw && pw.sel) pw.sel.forEach(wb => used.add(wb));
    });
    setPlanWb(Math.max(1, used.size));
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

  // MULTI-select: a path may use two or more bridges (trucks take whichever
  // assigned bridge is free). Click toggles; at least one stays selected.
  function toggleChip(wb){
    if (_sel.has(wb)){ if (_sel.size > 1) _sel.delete(wb); }
    else _sel.add(wb);
    syncWbCount();
    renderChips();
  }

  // Every bridge number on site is selectable — the USER decides which bridge
  // this path uses; the system only calculates the consequences. History is
  // shown as a hint (share % on bridges that served this route), never as a
  // restriction.
  const ALL_WBS = ['1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18'];
  function renderChips(note){
    const host = el('plan-wb-onpath');
    if (!host) return;
    const byWb = {};
    _bridges.forEach(b => { byWb[b.wb] = b; });
    if (!_sel.size) _sel = new Set([ALL_WBS[0]]);
    const chips = ALL_WBS.map(wb => {
      const on = _sel.has(wb);
      const hist = byWb[wb];
      const hint = hist ? ` <span class="wb-chip-pct">${pct(hist.sharePct)}</span>` : '';
      const t = hist
        ? `${escH(wb)} — ${pct(hist.sharePct)} of this route's historical weighs · click to use this bridge`
        : `${escH(wb)} — no history on this route (fine — your choice) · click to use this bridge`;
      return `<button type="button" data-wb="${escH(wb)}" class="wb-chip${on ? ' on' : ''}${hist ? '' : ' wb-chip-nohist'}"`
        + ` title="${t}">${escH(wb)}${hint}</button>`;
    }).join('');
    host.innerHTML =
      `<div class="plan-wb-path">`
      + `<div class="plan-wb-path-h">`
      + `<b>${escH(_route.s)} → ${escH(_route.d)}</b>`
      + `<span class="muted">choose the weighbridge for this path · % = historical use on this route`
      + (_cached ? ' · sample' : '')
      + `</span></div>`
      + `<div class="plan-wb-chips">${chips}</div>`
      + (note ? `<div class="plan-wb-path-note">${note}</div>` : '')
      + `</div>`;
  }

  function onWbInput(){
    if (_syncing) return;                        // our own programmatic write — ignore
    // #plan-wb is derived (distinct bridges in use); a manual edit is
    // immediately re-derived so the ceiling maths can't drift from the
    // actual assignments.
    syncWbCount();
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
    if (typeof _planDraft !== 'undefined' && _planDraft[id]){
      // Carry the bridge NUMBER picked in the top panel for this path. The
      // alternates list is the FULL site grid, annotated with history where
      // it exists — reassignment is never limited to historical bridges.
      const byWb = {};
      _bridges.forEach(b => { byWb[b.wb] = b; });
      _pathWb[id] = {
        bridges: ALL_WBS.map(wb => ({ wb, sharePct: byWb[wb] ? byWb[wb].sharePct : null })),
        sel: new Set(_sel.size ? _sel : ['1']), open: false };
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

  // Per-bridge load across the whole holding plan.
  //
  // SPLIT: a path's trips divide across its assigned bridges by the route's
  // HISTORICAL share of those bridges (drivers already favour the bridges
  // that serve their route); even split when no history covers the selection.
  //
  // QUEUE MODEL (M/M/1): each bridge is a single server at rate mu =
  // PLAN_WB_TRIPS_PER_HOUR. With arrivals lambda, utilisation rho = lambda/mu
  // and steady-state queue wait W = s * rho / (1 - rho), s = 60/mu min. This
  // matches the measured flat-wait regime below ~70%% and the blow-up above:
  // rho .70 -> +5 min, .85 -> +11, .95 -> +38, >=1 -> unbounded (queue grows
  // all shift). The measured wait curve (11.7->12.1 min at 3.6->31 trucks/h)
  // is the flat part of exactly this curve.
  // Other (non-plan) traffic per bridge: the measured shift tells us WHERE the
  // IWIP/Position trucks actually weighed (plan.js exposes _planOtherWb shares
  // + _planOtherTrips count). They preload those bridges — the planner's paths
  // then stack on top. This is the SINGLE capacity model: your plan + their
  // traffic, per bridge number, nothing pooled.
  function otherPerBridge(){
    const trips = (typeof _planOtherTrips !== 'undefined' ? _planOtherTrips : 0) || 0;
    const shares = (typeof _planOtherWb !== 'undefined' ? _planOtherWb : []) || [];
    if (!(trips > 0) || !shares.length) return {};
    const typ = (typeof _planOtherTypical !== 'undefined') ? _planOtherTypical : null;
    const regime = (typeof _planOtherRegime !== 'undefined') ? _planOtherRegime : 'peak';
    const src = typ
      ? ((regime === 'peak' && typ.peak) ? ('best period ' + (typ.peak.window || '')) : '30d median')
      : ((typeof _planOtherSrc !== 'undefined' && _planOtherSrc) ? 'measured ' + _planOtherSrc.slice(5) : 'last shift');
    const out = {};
    shares.forEach(s => { out[s.wb] = { trips: trips * s.share, label: 'other traffic (' + src + ')' }; });
    return out;
  }

  function bridgeUtil(){
    const hours = Math.max(1, parseFloat((el('plan-hours') || {}).value) || 12);
    const perH = (typeof PLAN_WB_TRIPS_PER_HOUR !== 'undefined') ? PLAN_WB_TRIPS_PER_HOUR : 30;
    const cap = perH * hours;
    const byWb = {};
    Object.keys(_pathWb).forEach(id => {
      const pw = _pathWb[id];
      if (!pw || !pw.sel.size) return;
      const total = pathTrips(id);
      if (!(total > 0)) return;
      const label = id.split('|').slice(1).join('|').replace('>', ' → ');
      // History-weighted split over the selected bridges.
      const shares = {};
      let histSum = 0;
      pw.sel.forEach(wb => {
        const b = pw.bridges.find(x => x.wb === wb);
        const sh = b && b.sharePct != null ? Math.max(0, b.sharePct) : 0;
        shares[wb] = sh; histSum += sh;
      });
      pw.sel.forEach(wb => {
        const frac = histSum > 0 ? (shares[wb] / histSum) : (1 / pw.sel.size);
        const t = total * frac;
        const rec = byWb[wb] || (byWb[wb] = { trips: 0, paths: [] });
        rec.trips += t;
        rec.paths.push(label);
      });
    });
    // Other (non-plan) traffic stacks onto ITS measured bridges.
    const other = otherPerBridge();
    Object.keys(other).forEach(wb => {
      const rec = byWb[wb] || (byWb[wb] = { trips: 0, paths: [] });
      rec.trips += other[wb].trips;
      rec.otherTrips = (rec.otherTrips || 0) + other[wb].trips;
      rec.paths.push(other[wb].label);
    });
    // Queue-wait per bridge from the M/M/1 curve.
    const svc = 60 / perH;   // service minutes per weigh
    Object.keys(byWb).forEach(wb => {
      const rec = byWb[wb];
      const rho = cap ? rec.trips / cap : 0;
      rec.rho = rho;
      rec.waitMin = rho >= 1 ? Infinity : svc * rho / (1 - rho);
    });
    return { byWb, cap, svc };
  }

  // Dispatcher auto-balance: assign every path's trips across bridges so the
  // worst bridge is as lightly loaded as possible. Greedy: paths in trip order;
  // each path picks its best bridges (history first, then any free bridge)
  // until its trips fit under the amber line (70%%) where possible.
  function autoBalance(){
    const hours = Math.max(1, parseFloat((el('plan-hours') || {}).value) || 12);
    const perH = (typeof PLAN_WB_TRIPS_PER_HOUR !== 'undefined') ? PLAN_WB_TRIPS_PER_HOUR : 30;
    const cap = perH * hours, amber = 0.7 * cap;
    const load = {}; ALL_WBS.forEach(wb => load[wb] = 0);
    // Other traffic is immovable — it preloads its measured bridges, and the
    // balancer routes the plan's trucks around it.
    const other = otherPerBridge();
    Object.keys(other).forEach(wb => { if (load[wb] != null) load[wb] += other[wb].trips; });
    const entries = Object.keys(_pathWb)
      .map(id => ({ id, pw: _pathWb[id], trips: pathTrips(id) }))
      .filter(x => x.trips > 0)
      .sort((a, b) => b.trips - a.trips);
    entries.forEach(x => {
      // Candidate order: this route's historical bridges by share desc, then
      // the rest of the site by current load asc.
      const hist = x.pw.bridges.filter(b => b.sharePct != null)
        .sort((a, b) => b.sharePct - a.sharePct).map(b => b.wb);
      const rest = ALL_WBS.filter(wb => !hist.includes(wb));
      const order = hist.concat(rest).sort((a, b) => {
        const ha = hist.indexOf(a), hb = hist.indexOf(b);
        if (ha !== -1 && hb !== -1) return ha - hb;         // keep history order first
        if (ha !== -1) return -1;
        if (hb !== -1) return 1;
        return load[a] - load[b];
      });
      const chosen = [];
      let remaining = x.trips;
      for (const wb of order){
        if (remaining <= 0) break;
        const room = amber - load[wb];
        if (room <= 0) continue;
        const take = Math.min(remaining, room);
        load[wb] += take; remaining -= take;
        chosen.push(wb);
      }
      if (remaining > 0){
        // Site genuinely saturated at 70%%: spill onto the least-loaded bridge.
        const least = ALL_WBS.slice().sort((a, b) => load[a] - load[b])[0];
        load[least] += remaining;
        if (!chosen.includes(least)) chosen.push(least);
      }
      x.pw.sel = new Set(chosen.length ? chosen : [ALL_WBS[0]]);
      x.pw.open = false;
    });
    syncWbCount();
    if (typeof computePlan === 'function') computePlan();
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
        const rec = byWb[wb] || { trips: 0, paths: [], rho: 0, waitMin: 0 };
        const u = rec.rho || 0;
        const wait = rec.waitMin;
        const waitTxt = wait === Infinity ? 'queue grows all shift'
          : wait > 1 ? `~${Math.round(wait)} min queue` : 'no queue';
        const sharedWith = rec.paths.length > 1
          ? ` · shared by ${rec.paths.length} paths` : '';
        const advice = u >= 1 ? ' · OVERLOADED — add a second bridge or move trips'
          : u >= 0.7 ? ' · heavy — consider a second bridge' : '';
        return `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(wb)}"`
          + ` title="WB ${escH(wb)} · ${Math.round(rec.trips)} trips assigned (${Math.round(100 * u)}% of ${Math.round(cap)}) · ${waitTxt}${sharedWith}${advice} · click to unassign"`
          + ` style="cursor:pointer;display:inline-block;margin:1px 4px 1px 0;padding:1px 8px;border-radius:11px;font-weight:600;`
          + `border:1px solid ${colFor(u)};background:${bgFor(u)};color:var(--txt)">`
          + `WB ${escH(wb)} <span style="opacity:.85">${Math.round(100 * u)}%${wait > 5 && wait !== Infinity ? ' · ' + Math.round(wait) + "'" : wait === Infinity ? ' · ∞' : ''}</span>`
          + (u >= 1 ? ' ⛔' : u >= 0.7 || rec.paths.length > 1 ? ' ⚠' : '') + `</span>`;
      }).join('');
      const alternates = pw.open
        ? pw.bridges.filter(b => !pw.sel.has(b.wb)).map(b => {
            const hint = b.sharePct != null ? ` <span style="opacity:.6">${pct(b.sharePct)}</span>` : '';
            const t = b.sharePct != null
              ? `assign WB ${escH(b.wb)} (${pct(b.sharePct)} of this route's historical weighs)`
              : `assign WB ${escH(b.wb)} (no history on this route — your choice)`;
            return `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(b.wb)}"`
            + ` title="${t}"`
            + ` style="cursor:pointer;display:inline-block;margin:1px 3px 1px 0;padding:1px 7px;border-radius:11px;`
            + `border:1px dashed var(--line);color:var(--muted)">+ ${escH(b.wb)}${hint}</span>`;
          }).join('')
        : '';
      const toggle = pw.bridges.length > 1
        ? `<span class="pwb-toggle" data-pwid="${escH(mm[1])}"`
        + ` style="cursor:pointer;font-size:9.5px;color:var(--muted);text-decoration:underline dotted">`
        + (pw.open ? 'hide' : 'add / change WB') + `</span>`
        : '';
      const sub = document.createElement('tr');
      sub.className = 'pwb-row';
      sub.innerHTML = `<td></td><td colspan="8" style="font-size:10px;padding:0 0 7px">`
        + `<span class="muted">WB:</span> ${assigned} ${alternates} ${toggle}</td>`;
      tr.parentNode.insertBefore(sub, tr.nextSibling);
    });
    // One auto-balance strip under the table (once, not per row).
    const anyOver = Object.values((_lastUtil || {}).byWb || {}).some(r => (r.rho || 0) >= 0.7);
    let strip = document.getElementById('pwb-balance-strip');
    if (!strip){
      strip = document.createElement('tr');
      strip.id = 'pwb-balance-strip';
      tbody.appendChild(strip);
    } else if (strip.parentNode !== tbody){
      strip.parentNode.removeChild(strip); tbody.appendChild(strip);
    }
    strip.innerHTML = Object.keys(_pathWb).length
      ? `<td></td><td colspan="8" style="font-size:10px;padding:2px 0 8px">`
        + `<span class="pwb-autobalance" style="cursor:pointer;padding:2px 9px;border:1px solid ${anyOver ? '#f59e0b' : 'var(--line)'};border-radius:10px;${anyOver ? 'background:rgba(245,158,11,.14);font-weight:600' : 'color:var(--muted)'}">`
        + `⚖ Auto-balance trucks across bridges</span>`
        + (anyOver ? ` <span style="color:#f59e0b">⚠ a bridge is over 70% — balancing recommended</span>` : '')
        + `</td>`
      : '';
    renderStressBoard();
  }
  let _lastUtil = null;

  // ── Weighbridge stress board ──────────────────────────────────────────────
  // One glance: every bridge in use, its assigned trips, utilisation and
  // estimated queue — live DURING planning (re-renders on every plan edit),
  // and unchanged after Run scenario since it reads the same holding plan.
  function renderStressBoard(){
    const host = document.getElementById('plan-wb-stress');
    if (!host) return;
    const { byWb, cap, svc } = _lastUtil || bridgeUtil();
    const used = Object.keys(byWb).filter(wb => byWb[wb].trips > 0.5);
    if (!used.length){ host.innerHTML = ''; return; }
    used.sort((a, b) => byWb[b].rho - byWb[a].rho);
    const worst = byWb[used[0]];
    const rows = used.map(wb => {
      const r = byWb[wb];
      const u = r.rho || 0, pctN = Math.round(100 * u);
      const col = u >= 1 ? '#ef4444' : u >= 0.7 ? '#f59e0b' : '#22c55e';
      const wait = r.waitMin === Infinity ? '∞' : r.waitMin > 1 ? Math.round(r.waitMin) + "'" : '—';
      const paths = r.paths.join(', ');
      const oth = Math.round(r.otherTrips || 0);
      const mine = Math.round(r.trips) - oth;
      const tripsTxt = oth > 0
        ? (mine > 0 ? `${mine}+${oth}o tr` : `${oth}o tr`)
        : `${Math.round(r.trips)} tr`;
      return `<div class="wbs-row" title="WB ${escH(wb)} · ${Math.round(r.trips)} trips total${oth > 0 ? ` = ${mine} plan + ${oth} other traffic` : ''} (${pctN}% of ${Math.round(cap)}) · est queue ${r.waitMin === Infinity ? 'grows all shift' : Math.round(r.waitMin || 0) + ' min'} · ${escH(paths)}">`
        + `<span class="wbs-name">WB ${escH(wb)}</span>`
        + `<span class="wbs-bar"><i style="width:${Math.min(100, pctN)}%;background:${col}"></i></span>`
        + `<span class="wbs-pct" style="color:${col}">${pctN}%</span>`
        + `<span class="wbs-wait">${wait}</span>`
        + `<span class="wbs-trips">${tripsTxt} · ${r.paths.length}p</span>`
        + `</div>`;
    }).join('');
    const worstNote = worst.rho >= 1
      ? `<span style="color:#ef4444">⛔ WB ${escH(used[0])} overloaded — queue grows all shift</span>`
      : worst.rho >= 0.7
        ? `<span style="color:#f59e0b">⚠ WB ${escH(used[0])} heavy (${Math.round(100 * worst.rho)}% · ~${Math.round(worst.waitMin)} min queue)</span>`
        : `<span class="muted">all bridges comfortable</span>`;
    host.innerHTML =
      `<div class="wbs-head muted">Bridge stress <span title="Per-bridge M/M/1 queue model: utilisation = assigned trips ÷ (${Math.round(60 / svc)} weighs/h × shift h); queue = service × ρ/(1−ρ). Other (non-plan) traffic is stacked onto the bridges it actually used in the measured shift — 'o' marks its trips. Columns: utilisation · est queue · trips (plan+other) & users. Live during planning.">ⓘ</span> ${worstNote}</div>`
      + rows;
  }

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
        else { pw.sel.add(wb); }
        syncWbCount();
        if (typeof computePlan === 'function') computePlan();
      }
      return;
    }
    const bal = t && t.closest ? t.closest('.pwb-autobalance') : null;
    if (bal){ autoBalance(); return; }
    const chip = t && t.closest ? t.closest('.wb-chip') : null;
    if (chip && chip.dataset && chip.dataset.wb){ toggleChip(chip.dataset.wb); return; }
    if (t && t.id === 'tabbtn-plan') setTimeout(wire, 60);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
