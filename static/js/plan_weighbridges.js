// ── Fleet-plan ↔ weighbridge linkage ─────────────────────────────────────────
// Joins the Plan tab's free "Weighbridges open" number to the weighbridges that
// ACTUALLY serve the selected source→dest haul (measured from tickets via
// /api/simulator/weighbridge-by-path). When a route is picked, this anchors the
// count to the bridges measured on that route and lists them under the input;
// the user can still override.
//
// Wired entirely by event listeners so plan.js stays UNTOUCHED — merges from
// Rahul's mirror stay clean. Wrapped in an IIFE so nothing leaks to globals.
(function(){
  let _lastKey = '';

  function el(id){ return document.getElementById(id); }

  function escH(x){
    return String(x == null ? '' : x).replace(/[&<>"]/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  }

  function load(){
    const host = el('plan-wb-onpath');
    if (!host) return;
    const s = (el('plan-src') || {}).value || '';
    const d = (el('plan-dst') || {}).value || '';
    const key = s + '>' + d;
    if (!s || !d){ host.innerHTML = ''; _lastKey = ''; return; }
    if (key === _lastKey) return;                 // route unchanged — don't refetch
    _lastKey = key;
    host.innerHTML = '<span class="muted" style="font-size:10.5px">Checking weighbridges on this route…</span>';

    const qs = new URLSearchParams({ source: s, dest: d });
    const frm = (el('f-from') || {}).value, to = (el('f-to') || {}).value;
    if (frm) qs.set('from', frm);
    if (to)  qs.set('to', to);

    fetch('/api/simulator/weighbridge-by-path?' + qs.toString())
      .then(r => r.json())
      .then(res => { if (key === _lastKey) render(host, res, s, d); })
      .catch(() => { host.innerHTML = ''; });
  }

  function render(host, res, s, d){
    const bridges = (res && res.bridges) || [];
    if (!bridges.length){
      host.innerHTML = '<span class="muted" style="font-size:10.5px">No weighbridge tickets found for this route in the selected window.</span>';
      return;
    }
    const n = res.nBridges || bridges.length;
    // Anchor "Weighbridges open" to the bridges measured on THIS route, then let
    // plan.js's own computePlan()/planPreview() recompute off the new value.
    const wb = el('plan-wb');
    if (wb){
      wb.value = n;
      wb.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const top = bridges.slice(0, 5)
      .map(b => `${escH(b.wb)} <span class="muted">${b.sharePct == null ? '' : Math.round(b.sharePct) + '%'}</span>`)
      .join(' · ');
    const cached = res && res.servedFrom === 'fixture';
    host.innerHTML =
      `<div style="font-size:10.5px;line-height:1.55">`
      + `<b style="color:var(--txt)">${n}</b> weighbridge${n === 1 ? '' : 's'} measured on `
      + `<b>${escH(s)} → ${escH(d)}</b>`
      + (cached ? ' <span class="muted">(sample data)</span>' : '')
      + `<br><span class="muted">${top}</span>`
      + `<br><span class="muted">Set “Weighbridges open” to ${n} from this route — edit to override.</span>`
      + `</div>`;
  }

  function wire(){
    ['plan-src', 'plan-dst'].forEach(id => {
      const e = el(id);
      if (e && !e._wbOnPathWired){ e.addEventListener('change', load); e._wbOnPathWired = true; }
    });
    load();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
  // Re-check when the Plan tab is opened (selects may have just been populated).
  document.addEventListener('click', function(ev){
    if (ev.target && ev.target.id === 'tabbtn-plan') setTimeout(wire, 60);
  });
})();
