/* plan_simulator.js — UI for the production simulator tab (Task 4).
 *
 * Talks to POST /api/simulate. The engine deliberately does NOT scale cycle
 * time with truck count (that effect is not identifiable in weighbridge data),
 * so this UI must not imply that it does. Contention is shown where the
 * evidence actually is: measured capacity utilisation at shared loading points.
 *
 * Every number is rendered with its basis available on hover, so a planner can
 * tell a measured value from a derived one without reading the docs.
 */
let _psRoutes = [], _psPlans = [], _psReady = false;

function psInit() {
  if (_psReady) return;
  _psReady = true;
  fetch('/api/simulate/options').then(r => r.json()).then(d => {
    _psRoutes = d.routes || [];
    const sel = q('ps-route');
    if (!sel) return;
    sel.innerHTML = _psRoutes.map((r, i) =>
      `<option value="${i}">${r.route} — ${Math.round(r.median_cycle_min)} min typical · ${r.shifts_observed} shifts observed</option>`
    ).join('') || '<option>no route history — run simulator_model.py</option>';
  }).catch(() => {
    const sel = q('ps-route');
    if (sel) sel.innerHTML = '<option>could not load routes</option>';
  });
}

function psAddPlan() {
  const sel = q('ps-route'), n = parseInt(q('ps-trucks').value, 10);
  if (!sel || !_psRoutes.length || !(n > 0)) return;
  const r = _psRoutes[parseInt(sel.value, 10)];
  if (!r) return;
  // Adding the same haul twice means one bigger fleet, not two entries.
  const dup = _psPlans.find(p => p.route === r.route);
  if (dup) dup.n_trucks += n;
  else _psPlans.push({route: r.route, source: r.source,
                      destination: r.destination, n_trucks: n});
  psRun();
}

function psRemove(i) { _psPlans.splice(i, 1); psRun(); }
function psClear() { _psPlans = []; psRun(); }

function psRun() {
  const body = q('ps-rows');
  if (!body) return;
  if (!_psPlans.length) {
    body.innerHTML = '<tr><td colspan="12" class="muted">Add a haul above to run the simulator…</td></tr>';
    q('ps-foot').innerHTML = '';
    q('ps-warnings').innerHTML = '';
    q('ps-limits').innerHTML = '';
    ['trucks', 'planned', 'achv'].forEach(k => q('ps-kpi-' + k).textContent = '—');
    return;
  }
  body.innerHTML = '<tr><td colspan="12" class="muted">Simulating…</td></tr>';
  fetch('/api/simulate', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      plans: _psPlans,
      weather: q('ps-weather').value,
      shift_minutes: parseFloat(q('ps-shift').value) || 720,
      availability: parseFloat(q('ps-avail').value) || 0.85,
    }),
  }).then(r => r.json()).then(psRender)
    .catch(e => { body.innerHTML = '<tr><td colspan="12" class="muted">simulation failed: ' + e + '</td></tr>'; });
}

function psRender(d) {
  const rows = d.results || [], s = d.summary || {};
  const fmt = n => (n == null ? '—' : Math.round(n).toLocaleString());
  q('ps-rows').innerHTML = rows.map((r, i) => {
    if (r.error) return `<tr><td>${r.route}</td><td colspan="11" class="muted">${r.error}</td></tr>`;
    const over = r.capacity_ratio > 1;
    // Only colour the capacity cell, because capacity is the only column with
    // a measured constraint behind it. Colouring predictions would imply a
    // confidence the model does not have.
    const capCell = `<span style="color:${over ? 'var(--bad,#e5534b)' : 'var(--muted,#8b98a5)'}">`
      + `${r.capacity_note.split(':')[0]}${r.capacity_ratio != null ? ' · ' + Math.round(100 * r.capacity_ratio) + '%' : ''}</span>`;
    const tip = Object.entries(r.basis || {}).map(([k, v]) => k + ': ' + v).join('\n');
    return `<tr title="${tip.replace(/"/g, '&quot;')}">
      <td><b>${r.route}</b></td>
      <td class="r">${r.n_trucks}</td>
      <td class="r" title="Weigh-to-weigh trip time">${r.predicted_cycle_time_min} min</td>
      <td class="r" title="Shift-minutes per completed trip, measured per route. This is what trips/shift divides by; it includes the empty return, the queue and breaks.">${r.effective_cycle_min} min</td>
      <td class="r">${r.predicted_load_time_min}</td>
      <td class="r">${r.predicted_dump_time_min}</td>
      <td class="r">${r.implied_travel_time_min}</td>
      <td class="r">${r.trips_per_shift_per_truck}</td>
      <td class="r">${fmt(r.planned_production_t)}</td>
      <td class="r">${over ? '<b>' + fmt(r.achievable_production_t) + '</b>' : fmt(r.achievable_production_t)}</td>
      <td>${capCell}</td>
      <td><button class="mode-btn" onclick="psRemove(${i})" title="Remove this haul">×</button></td>
    </tr>`;
  }).join('');

  const shortfall = (s.planned_production_t || 0) - (s.achievable_production_t || 0);
  q('ps-foot').innerHTML = `<tr><th>Total</th><th class="r">${s.total_trucks}</th>
    <th colspan="6"></th><th class="r">${fmt(s.planned_production_t)}</th>
    <th class="r">${fmt(s.achievable_production_t)}</th>
    <th colspan="2">${shortfall > 1 ? '<span style="color:var(--bad,#e5534b)">' + fmt(shortfall) + ' t blocked by capacity</span>' : ''}</th></tr>`;

  q('ps-kpi-trucks').textContent = s.total_trucks ?? '—';
  q('ps-kpi-planned').textContent = fmt(s.planned_production_t);
  q('ps-kpi-achv').textContent = fmt(s.achievable_production_t);

  const w = (s.capacity_warnings || []);
  const shared = (s.shared_loading_points || []);
  q('ps-warnings').innerHTML =
    (w.length ? w.map(x => `<div style="font-size:12px;color:var(--bad,#e5534b);margin-bottom:6px">⚠ ${x}</div>`).join('') : '')
    + (shared.length ? `<div class="muted" style="font-size:12px">Shared loading points: ${shared.join('; ')}</div>` : '')
    + (!w.length && !shared.length ? '<div class="muted" style="font-size:12px">No shared loading points and no capacity breach in this plan.</div>' : '');

  const lim = d.model_limits || {};
  q('ps-limits').innerHTML = '<b>What this simulator does not claim.</b> '
    + Object.values(lim).map(v => '· ' + v).join('<br>');
}
