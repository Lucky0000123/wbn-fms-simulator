#!/usr/bin/env python3
"""Rewrite plan_weighbridges per-row UI: ONE assigned bridge per path with
utilization coloring; shared-bridge congestion visible; alternates collapsed."""
p = 'static/js/plan_weighbridges.js'
s = open(p, encoding='utf-8').read()

# 1. Default per-path assignment = the TOP bridge only (not all)
old = """    const id = name + '|' + s + '>' + d;
    if (typeof _planDraft !== 'undefined' && _planDraft[id] && _bridges.length){
      _pathWb[id] = { bridges: _bridges.map(b => ({ wb: b.wb, sharePct: b.sharePct })), sel: new Set(_sel) };
    }
  }"""
new = """    const id = name + '|' + s + '>' + d;
    if (typeof _planDraft !== 'undefined' && _planDraft[id] && _bridges.length){
      // ONE bridge per path by default — the route's historical top bridge.
      // The planner reassigns from the collapsed alternates; utilisation
      // colouring below shows when two paths pile onto the same bridge.
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

  // Per-bridge utilisation across the WHOLE holding plan: each path's trips go
  // to its assigned bridge(s) (split evenly when >1). Ceiling per bridge =
  // PLAN_WB_TRIPS_PER_HOUR x shift hours (same basis as the WB-load bar).
  function bridgeUtil(){
    const hours = Math.max(1, parseFloat((el('plan-hours') || {}).value) || 12);
    const perH = (typeof PLAN_WB_TRIPS_PER_HOUR !== 'undefined') ? PLAN_WB_TRIPS_PER_HOUR : 30;
    const cap = perH * hours;
    const byWb = {};   // wb -> {trips, paths:[label]}
    Object.keys(_pathWb).forEach(id => {
      const pw = _pathWb[id];
      if (!pw || !pw.sel.size) return;
      const t = pathTrips(id) / pw.sel.size;
      if (!(t > 0)) return;
      const label = id.split('|').slice(1).join('|').replace('>', ' \\u2192 ');
      pw.sel.forEach(wb => {
        const rec = byWb[wb] || (byWb[wb] = { trips: 0, paths: [] });
        rec.trips += t;
        rec.paths.push(label);
      });
    });
    return { byWb, cap };
  }"""
assert old in s, 'snapshot block missing'
s = s.replace(old, new)

# 2. Per-row renderer: assigned chip + util colour; alternates collapsed
old2 = """      const chips = pw.bridges.map(b => {
        const on = pw.sel.has(b.wb);
        return `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(b.wb)}"`
          + ` title="${on ? 'click to remove from this path' : 'click to add back'}"`
          + ` style="cursor:pointer;display:inline-block;margin:1px 3px 1px 0;padding:1px 7px;border-radius:11px;`
          + `border:1px solid ${on ? '#f59e0b' : 'var(--line)'};background:${on ? 'rgba(245,158,11,.16)' : 'transparent'};`
          + `color:${on ? 'var(--txt)' : 'var(--muted)'}">${escH(b.wb)} <span style="opacity:.7">${pct(b.sharePct)}</span> ${on ? '\\u2715' : '+'}</span>`;
      }).join('');
      const sub = document.createElement('tr');
      sub.className = 'pwb-row';
      sub.innerHTML = `<td></td><td colspan="8" style="font-size:10px;padding:0 0 7px">`
        + `<span class="muted">Weighbridges (${pw.sel.size} of ${pw.bridges.length}):</span> ${chips}</td>`;
      tr.parentNode.insertBefore(sub, tr.nextSibling);
    });
  }"""
new2 = """      const { byWb, cap } = _lastUtil || bridgeUtil();
      const colFor = u => u >= 1 ? '#ef4444' : u >= 0.7 ? '#f59e0b' : '#22c55e';
      const bgFor  = u => u >= 1 ? 'rgba(239,68,68,.16)' : u >= 0.7 ? 'rgba(245,158,11,.16)' : 'rgba(34,197,94,.14)';
      const assigned = [...pw.sel].map(wb => {
        const rec = byWb[wb] || { trips: 0, paths: [] };
        const u = cap ? rec.trips / cap : 0;
        const sharedWith = rec.paths.length > 1
          ? ` \\u00b7 SHARED with ${rec.paths.length - 1} other path(s) \\u2014 congested; pick another WB`
          : '';
        return `<span class="pwb-chip" data-pwid="${escH(mm[1])}" data-wb="${escH(wb)}"`
          + ` title="WB ${escH(wb)} \\u00b7 ${Math.round(100 * u)}% of its ${Math.round(cap)}-trip shift ceiling${sharedWith} \\u00b7 click to unassign"`
          + ` style="cursor:pointer;display:inline-block;margin:1px 4px 1px 0;padding:1px 8px;border-radius:11px;font-weight:600;`
          + `border:1px solid ${colFor(u)};background:${bgFor(u)};color:var(--txt)">`
          + `WB ${escH(wb)} <span style="opacity:.85">${Math.round(100 * u)}%</span>`
          + (rec.paths.length > 1 ? ' \\u26a0' : '') + `</span>`;
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
    _lastUtil = null;
  }
  let _lastUtil = null;"""
assert old2 in s, 'inject block missing'
s = s.replace(old2, new2)

# 3. Precompute util once per injectPathWb pass
old3 = """  function injectPathWb(){
    const tbody = el('plan-rows');
    if (!tbody) return;"""
new3 = """  function injectPathWb(){
    const tbody = el('plan-rows');
    if (!tbody) return;
    _lastUtil = bridgeUtil();"""
assert old3 in s
s = s.replace(old3, new3)

# 4. Click handling: assigned chip = unassign (keep >=1), alternate = assign, toggle = expand
old4 = """    const pchip = t && t.closest ? t.closest('.pwb-chip') : null;
    if (pchip){
      const id = pchip.getAttribute('data-pwid'), wb = pchip.getAttribute('data-wb');
      const pw = _pathWb[id];
      if (pw){ if (pw.sel.has(wb)) pw.sel.delete(wb); else pw.sel.add(wb); if (typeof computePlan === 'function') computePlan(); }
      return;
    }"""
new4 = """    const ptog = t && t.closest ? t.closest('.pwb-toggle') : null;
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
    }"""
assert old4 in s
s = s.replace(old4, new4)

open(p, 'w', encoding='utf-8').write(s)
print('patched 4 blocks')
