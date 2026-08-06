// ── WBN tab ────────────────────────────────────────────────────────────────
// WBN-owned view. Lives in its own file so pulling Rahul's updates
// (merge mirror/main) never conflicts here. Touch-points in his code are kept
// minimal and additive: a tab button + panel in templates/simulator.html and
// one 'wbn' entry in setSimTab(). Backend uses our own additive endpoint
// /api/simulator/weighbridge-by-path (see simulator_api.py).
//
// Section 1: WBN-branded capability summary (reuses the loaded /api/simulate _D).
// Section 2: path → weighbridge linkage — which weighbridges actually weighed a
//   selected source→dest haul, and the capacity ceiling from THOSE bridges,
//   instead of the Plan tab's free "weighbridges open" number that is tied to
//   neither which bridges nor the bridges on the path.

// Source/dest options mirror the constraint matrix (TF/KR × POS/FENI). Kept
// local so this tab renders offline; extend alongside the server area maps.
const WBN_SOURCES = ['TF', 'KR'];
const WBN_DESTS = ['FENI KM0', 'FENI KM15', 'POS 12', 'POS 10', 'CRUSHER'];

function wbnInit(){
  const el = document.getElementById('wbn-body');
  if (!el) return;

  const d = (typeof _D !== 'undefined') ? _D : null;
  const summary = (d && d.kpi) ? wbnSummaryHtml(d) :
    '<p class="muted" style="margin:8px 0">Loading capability data… open the '
    + '<b>Capability &amp; Scenario</b> tab first, then return here.</p>';

  el.innerHTML =
    `<section style="margin:6px 0 20px">${summary}</section>`
    + `<section style="border-top:1px solid var(--line);padding-top:16px">`
    + `  <h3 style="margin:0 0 4px;font-size:15px;color:var(--txt)">Weighbridges on the path</h3>`
    + `  <p class="muted" style="margin:0 0 12px;font-size:11.5px">`
    + `    Which weighbridges actually weighed this haul's trucks, measured from tickets — `
    + `    so fleet sizing is tied to the bridges that serve the path, not a free number.</p>`
    + `  <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin:0 0 14px">`
    + `    <label style="font-size:11px;color:var(--muted)">Source<br>`
    + `      <select id="wbn-src" style="margin-top:3px">`
    +        WBN_SOURCES.map(s => `<option value="${s}">${s}</option>`).join('')
    + `      </select></label>`
    + `    <label style="font-size:11px;color:var(--muted)">Destination<br>`
    + `      <select id="wbn-dst" style="margin-top:3px">`
    +        WBN_DESTS.map(s => `<option value="${s}">${s}</option>`).join('')
    + `      </select></label>`
    + `    <button id="wbn-go" class="btn" onclick="wbnLoadBridges()" style="padding:6px 16px">Show</button>`
    + `  </div>`
    + `  <div id="wbn-bridges"></div>`
    + `</section>`;

  wbnLoadBridges();
}

function wbnSummaryHtml(d){
  const k = d.kpi;
  const cards = [
    [fmtM(k.wmtPerDay), 't/day',   'WMT / day',            'plan ' + fmtM(k.planWmtPerDay)],
    [fmt(k.dtPerDay),   'DT/day',  'Dump trucks / day',    'plan ' + fmt(k.planDtPerDay)],
    [fmt(k.tripsPerDT, 2), 'trips/DT', 'Trips per truck',  k.tf != null ? ('TF ' + fmt(k.tf, 1) + ' t') : ''],
    [fmt(k.tPerDT),     't/DT',    'Productivity / truck', ''],
  ];
  const scope = `${d.from} → ${d.to} · ${k.days} operating days`
    + (d.source ? ` · ${d.source}` : '') + (d.dest ? ` → ${d.dest}` : '');
  return `<div class="muted" style="margin:0 0 10px;font-size:12px">${scope}</div>`
    + `<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">`
    + cards.map(c =>
        `<div class="kpi"><div class="v">${c[0]} <span class="u">${c[1]}</span></div>`
        + `<div class="l">${c[2]}</div>${c[3] ? `<div class="sub">${c[3]}</div>` : ''}</div>`
      ).join('')
    + `</div>`;
}

function wbnLoadBridges(){
  const host = document.getElementById('wbn-bridges');
  if (!host) return;
  const src = (document.getElementById('wbn-src') || {}).value || 'TF';
  const dst = (document.getElementById('wbn-dst') || {}).value || 'FENI KM0';
  // Reuse the page's date range if present so this matches the numbers above.
  const frm = (document.getElementById('f-from') || {}).value || '';
  const to  = (document.getElementById('f-to') || {}).value || '';
  host.innerHTML = '<p class="muted" style="margin:6px 0">Loading…</p>';

  const qs = new URLSearchParams({ source: src, dest: dst });
  if (frm) qs.set('from', frm);
  if (to)  qs.set('to', to);

  fetch('/api/simulator/weighbridge-by-path?' + qs.toString())
    .then(r => r.json())
    .then(res => wbnRenderBridges(host, res, src, dst))
    .catch(() => { host.innerHTML = '<p class="muted" style="margin:6px 0">Could not load weighbridge data.</p>'; });
}

function wbnRenderBridges(host, res, src, dst){
  const bridges = (res && res.bridges) || [];
  const cached = res && res.servedFrom === 'fixture';
  if (!bridges.length){
    host.innerHTML = `<p class="muted" style="margin:6px 0">No weighbridge tickets found for ${escH(src)} → ${escH(dst)} in this window.</p>`;
    return;
  }
  const n = res.nBridges || bridges.length;
  const rows = bridges.map(b => {
    const kmTxt = (b.km != null) ? (fmt(b.km, 1) + ' km') : '<span class="muted">—</span>';
    const bar = `<span style="display:inline-block;height:9px;width:${Math.max(2, b.sharePct || 0)}%;background:#f59e0b;border-radius:2px;vertical-align:middle"></span>`;
    const off = (b.onCorridor === false) ? ' <span class="muted" title="off the main corridor centreline">(spur)</span>' : '';
    return `<tr>`
      + `<td style="padding:4px 10px 4px 0;color:var(--txt);font-weight:600">${escH(b.wb)}${off}</td>`
      + `<td style="padding:4px 10px;color:var(--muted)">${kmTxt}</td>`
      + `<td style="padding:4px 10px;text-align:right">${fmt(b.trips)}</td>`
      + `<td style="padding:4px 10px;text-align:right">${fmt(b.sharePct, 1)}%</td>`
      + `<td style="padding:4px 0;width:120px">${bar}</td>`
      + `</tr>`;
  }).join('');

  host.innerHTML =
    `<p style="margin:0 0 8px;color:var(--txt);font-size:13px">`
    + `<b>${n}</b> weighbridge${n === 1 ? '' : 's'} serve <b>${escH(src)} → ${escH(dst)}</b>`
    + ` · <span class="muted">${fmt(res.totalTrips || 0)} tickets in window</span>`
    + (cached ? ` · <span class="muted" title="${escH(res.servedFromReason || 'sample data')}">sample data</span>` : '')
    + `</p>`
    + `<table style="border-collapse:collapse;font-size:12.5px;margin:0 0 12px">`
    + `<thead><tr style="color:var(--muted);font-size:10.5px;text-transform:uppercase">`
    + `<th style="text-align:left;padding:0 10px 4px 0">Weighbridge</th>`
    + `<th style="text-align:left;padding:0 10px 4px">Chainage</th>`
    + `<th style="text-align:right;padding:0 10px 4px">Tickets</th>`
    + `<th style="text-align:right;padding:0 10px 4px">Share</th>`
    + `<th style="padding:0 0 4px">&nbsp;</th></tr></thead>`
    + `<tbody>${rows}</tbody></table>`
    + `<div class="kpi" style="display:inline-block;min-width:220px">`
    + `  <div class="v">${fmt(res.capacityTripsPerShift || 0)} <span class="u">trips/shift</span></div>`
    + `  <div class="l">Capacity ceiling from on-path bridges</div>`
    + `  <div class="sub">${escH(res.capacityBasis || '')}</div>`
    + `</div>`
    + `<p class="muted" style="margin:12px 0 0;font-size:11px">`
    + `The Plan tab asks for a free "weighbridges open" count. This ceiling instead uses the `
    + `<b>${n}</b> bridge${n === 1 ? '' : 's'} measured to serve this path — sizing a fleet past it just grows the weigh queue.</p>`;
}
