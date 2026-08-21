/* plan_assessment.js — the plan assessment view (Sections 2–9 of the Production
 * Simulator tab; S1 = plan builder, S6 = production table in plan_simulator.js).
 * Charts are ECharts from CDN; there is no build step and no npm dependency.
 *
 * IT RENDERS FROM THE SAME /api/simulate RESPONSE the results table already
 * uses, so a number can never disagree between the table and a chart. The extra
 * fetches (options, congestion-model, capability) are cached for the session.
 *
 * THREE PLACES THE BRIEF ASKED FOR SOMETHING THE DATA CANNOT SUPPORT, and what
 * is drawn instead. Each is labelled in the UI, not just here:
 *
 *   1. "travel empty" as its own band in the trip-time bar.
 *      Weigh-to-weigh (predicted_cycle_time_min) spans load -> haul -> dump. The
 *      empty return is OUTSIDE it, sitting in the gap up to effective_cycle_min
 *      together with the shovel queue, refuelling, breaks and downtime. That gap
 *      is 277 of 355 min on BLB>FENI KM0. Calling it "travel empty" would assert
 *      a decomposition nothing measures, so it is drawn as one residual band and
 *      named for everything it contains.
 *
 *   2. [RESOLVED 2026-07-31] Loaded vs empty speed as two lines per section.
 *      This used to read "not available -- the endpoint aggregates over DIR".
 *      It now is available: the endpoint selects DIR and returns loadedSpeed /
 *      emptySpeed per segment. DIR is a CHAINAGE direction ('down' / 'up'), and
 *      that it means loaded / empty was verified against the tickets rather than
 *      inferred from the word -- 100.0% of loaded corridor hauls run
 *      down-chainage (298,340 trips, zero counter-examples), because every tip
 *      sits seaward of every load point. Empty is faster on 75 of 94 segments,
 *      median +11.5%, up to +101% on the steep TF sections.
 *
 *   3. Per-contractor fleet-sizing breakdown.
 *      /api/simulate returns roster per ROUTE, and availability is measured for
 *      trucks carrying only 30.3% of tonnage. There is no contractor dimension on
 *      the roster figure, so the table breaks down by route and shows each row's
 *      basis (measured vs fleet_prior) rather than inventing contractor rows.
 *
 * ECHARTS MAY BE ABSENT. This tool is demonstrated without VPN and sometimes
 * without internet, so a CDN failure must not take the page with it. Every chart
 * goes through paChart(), which degrades to a visible note; the tables carry the
 * numbers regardless and are built with plain DOM.
 */

let _paOptions = null, _paCongestion = null, _paCapability = null;
let _paLastSim = null, _paCharts = {}, _paRoad = null;
let _paAnalogues = null;
/* Section 9 map state. _paGeom is the corridor centreline; it is fetched once
 * and may legitimately be an "unavailable" payload, because site coordinates are
 * not committed to the public mirror. */
let _paGeom = null, _paMap = null, _paLayer = null, _paMapMetric = 'loadedSpeed';
let _paSegIndex = {};
/* 3D view state. Cesium is lazy-loaded on first use, so _paCesiumLoading
 * doubles as the once-only guard and the in-flight promise. */
let _paMapMode = '2d', _paViewer = null, _paCesiumLoading = null;

/* ---------- small helpers ---------- */

function paNum(n, d) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Number(n).toLocaleString(undefined, {minimumFractionDigits: d || 0,
                                              maximumFractionDigits: d || 0});
}

function paEsc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* Quartiles by linear interpolation on a sorted array. Used for the historical
 * box plot. Returns null below 4 points: a box drawn from 3 shifts implies a
 * distribution that is not there. */
function paQuartiles(sorted) {
  const n = sorted.length;
  if (n < 4) return null;
  const at = (p) => {
    const i = (n - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
    return lo === hi ? sorted[lo] : sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
  };
  return {min: sorted[0], q1: at(0.25), med: at(0.5), q3: at(0.75), max: sorted[n - 1]};
}

/* Chart colours, kept in one place so the sections read as one system and so
 * the trip-time band colours match their table columns. */
const PA_C = {
  load:  '#3fb950',   // loading dwell
  haul:  '#4a9eff',   // travel while loaded
  dump:  '#f0883e',   // dumping dwell
  resid: '#6e7681',   // queue + empty return + breaks (residual)
  meas:  '#4a9eff',
  free:  '#3fb950',
  bad:   '#e5534b',
  warn:  '#d29922',
  ok:    '#3fb950',
  axis:  '#8b98a5',
  grid:  'rgba(139,152,165,.16)',
  text:  '#c9d1d9',
};

/* Every chart funnels through here so the CDN-missing path is handled once. */
// emptyNote: what to tell the reader when ECharts is missing. Defaults to the
// assessment-view truth ("it is all in the tables"), which is FALSE for any
// chart-only section -- section B · Fleet sensitivity has no table behind it,
// so it passes its own sentence rather than promising numbers that are not there.
function paChart(id, option, emptyNote) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof echarts === 'undefined') {
    el.innerHTML = '<div class="muted" style="padding:14px;font-size:12px;'
      + 'border:1px dashed var(--line,#30363d);border-radius:8px">'
      + 'Chart library unavailable (ECharts is loaded from a CDN and this machine '
      + 'appears to be offline). '
      + (emptyNote || 'Every figure in this section is also in the '
        + 'tables, which do not need it.') + '</div>';
    return;
  }
  // Reuse the cached instance ONLY if it is still bound to the element that is
  // currently in the document. paGauges() rebuilds its container with innerHTML,
  // which detaches the old chart divs -- and a detached instance is NOT disposed,
  // so isDisposed() stays false and the chart happily renders into orphaned DOM.
  // That is what blanked every gauge from the second render onwards: 2 canvases,
  // then 1, then 0, while the wrapper divs were recreated each time and looked
  // fine to anything counting elements.
  let c = _paCharts[id];
  // No canvas under the root = the instance's inner DOM was wiped (innerHTML)
  // while the root stayed connected; getDom() checks alone cannot see that.
  if (c && (c.isDisposed() || c.getDom() !== el || !c.getDom().isConnected
      || !el.querySelector('canvas'))) {
    try { c.dispose(); } catch (e) {}
    c = null;
    delete _paCharts[id];
  }
  if (!c) { c = echarts.init(el); _paCharts[id] = c; }
  c.setOption(option, true);
}

function paResizeAll() {
  Object.values(_paCharts).forEach(c => { try { c.resize(); } catch (e) {} });
}
window.addEventListener('resize', paResizeAll);

/* ---------- data loading (cached per session) ---------- */

function paLoadRefs() {
  const jobs = [];
  if (!_paOptions) {
    jobs.push(fetch('/api/simulate/options').then(r => r.json())
      .then(d => { _paOptions = d; }).catch(() => { _paOptions = {}; }));
  }
  if (!_paCongestion) {
    jobs.push(fetch('/api/simulator/congestion-model').then(r => r.json())
      .then(d => { _paCongestion = d; }).catch(() => { _paCongestion = {}; }));
  }
  if (!_paCapability) {
    jobs.push(fetch('/api/simulator/capability').then(r => r.json())
      .then(d => { _paCapability = d; }).catch(() => { _paCapability = {}; }));
  }
  if (!_paGeom) {
    jobs.push(fetch('/api/simulator/corridor-geometry').then(r => r.json())
      .then(d => { _paGeom = d; })
      .catch(() => { _paGeom = {ok: false, roads: [],
                                reason: 'corridor geometry request failed'}; }));
  }
  return Promise.all(jobs);
}

/* Entry point. plan_simulator.js calls this with the /api/simulate response it
 * just rendered, so the assessment and the results table are the same numbers. */
function paRender(sim) {
  _paLastSim = sim;
  // Two wrappers, because sections 2–5 sit ABOVE the production table (section 6);
  // sections 7–9 sit below.
  // and 7-8 below it, so the page reads 1..8 top to bottom.
  const hosts = ['pa-sections-top', 'pa-sections-bot']
    .map(id => document.getElementById(id)).filter(Boolean);
  if (!hosts.length) return;
  const rows = ((sim || {}).results || []).filter(r => !r.error);
  hosts.forEach(h => { h.style.display = rows.length ? '' : 'none'; });
  if (!rows.length) return;
  paLoadRefs().then(() => {
    paBreakdown(rows);
    paSpeed();
    paGauges(sim, rows);
    paFleet(sim, rows);
    paMap();
    return paEnsureAnalogues(rows).then(() => {
      paCongestion(sim, rows);
      paHistory(rows);
    });
  });
}

function paAnaloguePlansFromRows(rows) {
  // Prefer Plan-tab draft (keeps contractor); else build from simulate rows.
  if (window._paAnaloguePlans && window._paAnaloguePlans.length) {
    return window._paAnaloguePlans;
  }
  return (rows || []).map(r => ({
    source: r.source, destination: r.destination,
    n_trucks: r.n_trucks, contractor: null,
  }));
}

function paEnsureAnalogues(rows) {
  if (window._paAnalogues && window._paAnalogues.ok) {
    _paAnalogues = window._paAnalogues;
    return Promise.resolve(_paAnalogues);
  }
  const plans = paAnaloguePlansFromRows(rows);
  if (!plans.length) {
    _paAnalogues = null;
    return Promise.resolve(null);
  }
  const rainEl = document.getElementById('plan-rain') || document.getElementById('ps-weather');
  let rain_mm = 0;
  if (rainEl && rainEl.id === 'ps-weather') {
    rain_mm = rainEl.value === 'wet' ? 2 : 0;
  } else if (rainEl) {
    rain_mm = Math.max(0, parseFloat(rainEl.value) || 0);
  }
  return fetch('/api/plan/analogues', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({plans, rain_mm, k: 8}),
  }).then(r => r.json()).then(data => {
    _paAnalogues = data;
    window._paAnalogues = data;
    return data;
  }).catch(() => {
    _paAnalogues = null;
    return null;
  });
}

function paRenderSharedRoad(sr) {
  const box = document.getElementById('pa-shared-road');
  const rowsEl = document.getElementById('pa-shared-road-rows');
  if (!box && !rowsEl) return;
  sr = sr || {};
  const risk = sr.risk || 'none';
  if (box) {
    box.innerHTML = '<p style="margin:0 0 4px"><span class="plan-risk-badge plan-risk-'
      + paEsc(risk) + '">' + paEsc(sr.risk_label || risk) + '</span></p>'
      + '<p class="muted" style="margin:0;font-size:12px">Shared road sections: <b>'
      + paEsc((sr.shared_sections || []).join(', ') || '—')
      + '</b> · planned ~ <b>' + paNum(sr.plan_dt_total) + ' DT</b>'
      + (sr.max_hist_section_dt != null
          ? ' · hist peak <b>' + paNum(sr.max_hist_section_dt) + ' DT</b>' : '')
      + (sr.trips_per_dt_collapse_pct != null
          ? ' · busy trips/DT <b>' + paNum(sr.trips_per_dt_collapse_pct, 1)
            + '%</b> below quiet days' : '')
      + '</p>';
  }
  const ev = sr.evidence || [];
  if (rowsEl) {
    rowsEl.innerHTML = ev.length ? ev.map(e => {
      const secBits = Object.keys(e.sections || {}).map(k => k + ': ' + paNum(e.sections[k])).join(', ');
      return '<tr><td><b>' + paEsc(e.date) + '</b></td>'
        + '<td class="r">' + paNum(e.section_dt, 1) + '</td>'
        + '<td class="r">' + paNum(e.trips_per_dt, 2) + '</td>'
        + '<td>' + paEsc(e.season || '') + '</td>'
        + '<td class="muted" style="font-size:10.5px">' + paEsc(secBits) + '</td></tr>';
    }).join('') : '<tr><td colspan="5" class="muted">'
      + paEsc(sr.note || 'No shared-road evidence.') + '</td></tr>';
  }
}

/* ---------- Section 2 · trip time breakdown ---------- */

function paBreakdown(rows) {
  const names = rows.map(r => r.route);
  const load = rows.map(r => r.predicted_load_time_min || 0);
  const haul = rows.map(r => r.implied_travel_time_min || 0);
  const dump = rows.map(r => r.predicted_dump_time_min || 0);
  // The residual is effective cycle minus weigh-to-weigh, floored at zero. It is
  // NOT "travel empty" -- see the header comment. Floored because a route whose
  // effective cycle is below its weigh-to-weigh interval would be a data problem,
  // and a negative bar would hide it; the note below the chart flags it instead.
  const resid = rows.map(r => Math.max(0, (r.effective_cycle_min || 0)
                                        - (r.predicted_cycle_time_min || 0)));
  const inverted = rows.filter(r => (r.effective_cycle_min || 0)
                                  < (r.predicted_cycle_time_min || 0));

  const bar = (name, data, color) => ({
    name, type: 'bar', stack: 'cycle', emphasis: {focus: 'series'},
    itemStyle: {color}, data,
  });

  paChart('pa-breakdown-chart', {
    backgroundColor: 'transparent',
    tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'},
              valueFormatter: v => paNum(v, 1) + ' min'},
    legend: {textStyle: {color: PA_C.text, fontSize: 11}, top: 0},
    grid: {left: 8, right: 16, bottom: 4, top: 34, containLabel: true},
    xAxis: {type: 'value', name: 'minutes', nameTextStyle: {color: PA_C.axis},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    yAxis: {type: 'category', data: names, axisLabel: {color: PA_C.text, fontSize: 11}},
    series: [
      bar('Loading (estimated split)', load, PA_C.load),
      bar('Travel, loaded', haul, PA_C.haul),
      bar('Dumping (estimated split)', dump, PA_C.dump),
      bar('Queue + empty return + breaks (residual)', resid, PA_C.resid),
    ],
  });

  const tb = rows.map(r => {
    const res = Math.max(0, (r.effective_cycle_min || 0) - (r.predicted_cycle_time_min || 0));
    const pct = r.effective_cycle_min ? 100 * res / r.effective_cycle_min : 0;
    return `<tr><td><b>${paEsc(r.route)}</b></td>
      <td class="r">${paNum(r.predicted_load_time_min, 1)}</td>
      <td class="r">${paNum(r.implied_travel_time_min, 1)}</td>
      <td class="r">${paNum(r.predicted_dump_time_min, 1)}</td>
      <td class="r"><b>${paNum(r.predicted_cycle_time_min, 1)}</b></td>
      <td class="r">${paNum(res, 1)}</td>
      <td class="r"><b>${paNum(r.effective_cycle_min, 1)}</b></td>
      <td class="r">${paNum(pct, 0)}%</td></tr>`;
  }).join('');
  document.getElementById('pa-breakdown-rows').innerHTML = tb;

  document.getElementById('pa-breakdown-note').innerHTML =
    'The first three bands sum to the <b>weigh-to-weigh</b> interval &mdash; the trip '
    + 'time a planner recognises. The fourth is everything between one trip and the '
    + 'next: the empty return, the shovel queue, refuelling, breaks and downtime. It '
    + 'is drawn as one band because the weighbridge cannot separate them &mdash; '
    + '<b>it is not "travel empty"</b>, and labelling it so would assert a split '
    + 'nothing measures. Trips per shift divide by the full effective cycle, which is '
    + 'why the residual matters more than the trip time. The load/dump split is '
    + 'itself an apportionment: load time is directly measured on only 24.8% of trips.'
    + (inverted.length
        ? '<br><span style="color:' + PA_C.bad + '">Check: ' + inverted.length
          + ' route(s) report an effective cycle below their weigh-to-weigh interval, '
          + 'which should not happen; the residual is floored at zero for those.</span>'
        : '');
}

/* ---------- Section 3 · speed per KM section ---------- */

/* Segment ids look like "CBB KM10-11" / "KR KM35-36": road prefix, then the km
 * span. Parsed rather than assumed -- anything that does not match is dropped
 * from the chart and counted in the note, so a vocabulary change shows up as a
 * shrinking sample instead of a silently wrong axis. */
function paParseSeg(seg) {
  const m = String(seg).match(/^(.+?)\s*KM\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$/i);
  if (!m) return null;
  return {road: m[1].trim(), from: parseFloat(m[2]), to: parseFloat(m[3])};
}

function paSpeed() {
  const segs = ((_paCongestion || {}).segments) || [];
  const parsed = [], unparsed = [];
  segs.forEach(s => {
    const p = paParseSeg(s.seg);
    if (p) parsed.push(Object.assign({}, s, p)); else unparsed.push(s.seg);
  });

  const byRoad = {};
  parsed.forEach(s => { (byRoad[s.road] = byRoad[s.road] || []).push(s); });
  const roads = Object.keys(byRoad).sort((a, b) => byRoad[b].length - byRoad[a].length);

  const sel = document.getElementById('pa-road');
  if (sel && sel.options.length !== roads.length) {
    sel.innerHTML = roads.map(r =>
      `<option value="${paEsc(r)}">${paEsc(r)} — ${byRoad[r].length} segments</option>`).join('');
  }
  if (!roads.length) {
    document.getElementById('pa-speed-note').innerHTML =
      '<span style="color:' + PA_C.warn + '">No segment speeds available. '
      + ((_paCongestion || {}).error ? paEsc(_paCongestion.error)
         : 'FMS_CONGESTION_SEG retains about two weeks, so this is empty without a '
           + 'recent extract.') + '</span>';
    paChart('pa-speed-chart', {});
    return;
  }
  if (!_paRoad || !byRoad[_paRoad]) _paRoad = roads[0];
  if (sel) sel.value = _paRoad;

  const list = byRoad[_paRoad].slice().sort((a, b) => a.from - b.from);
  // Nulls are dropped, not zeroed: a segment with no fixes in one direction has
  // no speed, and plotting 0 would draw a truck standing still.
  const pt = (s, k) => (s[k] === null || s[k] === undefined) ? null : [s.from, s[k]];
  const loaded = list.map(s => pt(s, 'loadedSpeed')).filter(Boolean);
  const empty = list.map(s => pt(s, 'emptySpeed')).filter(Boolean);
  const free = list.map(s => pt(s, 'freeFlow')).filter(Boolean);
  const haveDir = loaded.length > 0 || empty.length > 0;
  const meas = list.map(s => pt(s, 'avgSpeed')).filter(Boolean);

  paChart('pa-speed-chart', {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (ps) => {
        if (!ps || !ps.length) return '';
        const km = ps[0].value[0];
        const s = list.find(x => x.from === km) || {};
        const gap = (s.loadedSpeed && s.emptySpeed)
          ? `<br>empty vs loaded: <b>${paNum(100 * (s.emptySpeed - s.loadedSpeed) / s.loadedSpeed, 1)}%</b>`
          : '';
        return `<b>${paEsc(s.seg || '')}</b><br>`
          + ps.map(p => `${p.marker}${p.seriesName}: ${paNum(p.value[1], 1)} km/h`).join('<br>')
          + gap
          + `<br>GPS fixes loaded / empty: ${paNum(s.nLoaded)} / ${paNum(s.nEmpty)}`
          + `<br>segment-hours: ${paNum(s.n)}`
          + `<br>peak trucks on segment: ${paNum(s.peakTrucks)}`;
      },
    },
    legend: {textStyle: {color: PA_C.text, fontSize: 11}, top: 0},
    grid: {left: 8, right: 18, bottom: 4, top: 34, containLabel: true},
    xAxis: {type: 'value', name: 'KM chainage', nameLocation: 'middle', nameGap: 26,
            nameTextStyle: {color: PA_C.axis},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    yAxis: {type: 'value', name: 'km/h', min: 0, nameTextStyle: {color: PA_C.axis},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    // Loaded vs empty when DIR is present; otherwise fall back to the pooled
    // mean so an older fixture still renders something true rather than blank.
    series: haveDir ? [
      {name: 'Free-flow (p85 at low traffic)', type: 'line', data: free,
       lineStyle: {color: PA_C.axis, type: 'dotted', width: 1.5, opacity: .75},
       itemStyle: {color: PA_C.axis}, symbolSize: 0, z: 1},
      {name: 'Loaded (down-chainage, toward the tip)', type: 'line', data: loaded,
       lineStyle: {color: PA_C.meas, width: 2.5}, itemStyle: {color: PA_C.meas},
       symbolSize: 6, z: 3},
      {name: 'Empty (up-chainage, returning)', type: 'line', data: empty,
       lineStyle: {color: PA_C.free, type: 'dashed', width: 2.5},
       itemStyle: {color: PA_C.free}, symbolSize: 6, z: 2},
    ] : [
      {name: 'Free-flow (p85 at low traffic)', type: 'line', data: free,
       lineStyle: {color: PA_C.free, type: 'dashed', width: 2},
       itemStyle: {color: PA_C.free}, symbolSize: 5, z: 2},
      {name: 'Measured mean speed (no direction split available)', type: 'line',
       data: meas, lineStyle: {color: PA_C.meas, width: 2.5},
       itemStyle: {color: PA_C.meas}, symbolSize: 6, z: 3},
    ],
  });

  const totalObs = list.reduce((a, s) => a + (s.n || 0), 0);
  // Fixture-served data is labelled, never passed off as live. The server tags
  // the fallback because the VPN here drops every few minutes, so "cached" is
  // the normal case rather than an edge case.
  const cached = (_paCongestion || {}).servedFrom === 'fixture';
  // The server's reason is a raw driver error ("DB-Lib error message 20009...")
  // with embedded newlines. Useful on hover, unreadable in a sentence, so it
  // goes in the title and the visible text says the operational thing instead.
  const rawReason = (_paCongestion || {}).servedFromReason || '';
  const shortReason = /unreachable/i.test(rawReason)
    ? 'the site link or database is down'
    : 'no database is configured on this machine';
  const cachedBanner = cached
    ? '<b style="color:' + PA_C.warn + '" title="' + paEsc(rawReason) + '">'
      + 'Cached segment speeds.</b> Live segment data is unavailable because '
      + shortReason + ', so these are the last captured speeds shipped with the '
      + "app, not today's. The shape of the corridor and the relative "
      + 'differences between segments hold; absolute km/h may be stale. '
    : '';
  document.getElementById('pa-speed-note').innerHTML =
    cachedBanner
    + `Road <b>${paEsc(_paRoad)}</b>: ${list.length} segments, ${paNum(totalObs)} `
    + `segment-hours over ${paNum((_paCongestion || {}).days)} days of retention. `
    + (haveDir
        ? '<b>Loaded</b> is measured down-chainage (toward the tip), <b>empty</b> '
          + 'up-chainage (returning). That mapping is verified against the '
          + 'weighbridge tickets, not inferred from the words: <b>100.0% of '
          + 'loaded corridor hauls run down-chainage</b> (298,340 trips, zero '
          + 'counter-examples), because every tip sits seaward of every load '
          + 'point. Across the corridor empty is faster on <b>75 of 94 '
          + 'segments</b>, median <b>+11.5%</b>, and up to +101% on the steep TF '
          + 'sections. On the ~20% where loaded reads faster the two are usually '
          + 'within noise &mdash; check the fix counts in the tooltip before '
          + 'reading anything into a single segment. The dotted line is free-flow '
          + '(p85 of speeds in the bottom traffic quintile), pooled over both '
          + 'directions.'
        : 'Showing the pooled mean: this response carries no direction split.')
    + (unparsed.length ? ` ${unparsed.length} segment id(s) did not match the `
        + '"ROAD KMa-b" pattern and are excluded.' : '');
}

/* ---------- Section 4 · congestion impact ---------- */

function paCongestion(sim, rows) {
  const s = (sim || {}).summary || {};
  const sharedLoad = s.shared_loading_points || [];
  const sharedDump = s.shared_dumping_points || [];
  const segs = ((_paCongestion || {}).segments) || [];
  const fit = (_paCongestion || {}).densityFit || null;

  // Shared-point table: which plans collide, and on how many trucks. This is the
  // contention the engine actually models -- capacity at a point -- as distinct
  // from the road-speed effect below, which it deliberately does not model.
  const shareRows = [];
  rows.forEach(r => {
    (r.shared_with || []).forEach(o => shareRows.push({
      point: r.source, route: r.route, other: o, trucks: r.n_trucks}));
  });
  const shareHtml = (sharedLoad.length || sharedDump.length)
    ? [].concat(
        sharedLoad.map(x => `<tr><td>Loading</td><td><b>${paEsc(x)}</b></td></tr>`),
        sharedDump.map(x => `<tr><td>Dumping</td><td><b>${paEsc(x)}</b></td></tr>`)
      ).join('')
    : '<tr><td colspan="2" class="muted">No loading or dumping point is shared '
      + 'between the plans in this assessment.</td></tr>';
  document.getElementById('pa-shared-rows').innerHTML = shareHtml;

  // Shared-road advisory from analogue engine (separate from loader shared_with).
  paRenderSharedRoad((_paAnalogues && _paAnalogues.shared_road) || {
    risk: 'none',
    risk_label: 'Shared-road analogues not loaded',
    shared_sections: [],
    note: 'Open from Plan tab Run, or wait for /api/plan/analogues.',
  });

  // Segment speed-drop table + bar: measured free-flow vs measured mean, biggest
  // drops first. Sorted by drop so the worst sections lead, but n is shown on
  // every row because a large drop on 6 observations is not a finding.
  const drops = segs.map(x => {
    const ff = x.freeFlow || 0, av = x.avgSpeed || 0;
    return {seg: x.seg, ff, av, n: x.n, peak: x.peakTrucks,
            dropPct: ff > 0 ? 100 * (ff - av) / ff : 0};
  }).filter(d => d.n >= 20).sort((a, b) => b.dropPct - a.dropPct);
  const top = drops.slice(0, 12);

  document.getElementById('pa-drop-rows').innerHTML = top.length
    ? top.map(d => `<tr><td>${paEsc(d.seg)}</td>
        <td class="r">${paNum(d.ff, 1)}</td>
        <td class="r">${paNum(d.av, 1)}</td>
        <td class="r">${paNum(d.dropPct, 1)}%</td>
        <td class="r">${paNum(d.peak)}</td>
        <td class="r">${paNum(d.n)}</td></tr>`).join('')
    : '<tr><td colspan="6" class="muted">No segment has 20+ observations in the '
      + 'retained window.</td></tr>';

  paChart('pa-drop-chart', {
    backgroundColor: 'transparent',
    tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'},
              valueFormatter: v => paNum(v, 1) + '%'},
    grid: {left: 8, right: 18, bottom: 4, top: 12, containLabel: true},
    xAxis: {type: 'value', name: "% below that segment's own free-flow — NOT a congestion effect",
            nameLocation: 'middle', nameGap: 26, nameTextStyle: {color: PA_C.axis, fontSize: 10.5},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    yAxis: {type: 'category', data: top.map(d => d.seg).reverse(),
            axisLabel: {color: PA_C.text, fontSize: 10}},
    series: [{
      type: 'bar', data: top.map(d => d.dropPct).reverse(),
      itemStyle: {color: (p) => p.value > 20 ? PA_C.warn : PA_C.meas},
    }],
  });

  document.getElementById('pa-cong-note').innerHTML = fit
    ? '<b>Read the bars and the coefficient as two different things.</b> A bar shows '
      + "how far a segment's <i>mean</i> speed sits below its <i>own</i> free-flow "
      + 'across all conditions — gradient, bends, surface, loaded-vs-empty mix and '
      + 'traffic combined. A 50% bar is a permanently slow segment, not a congested '
      + 'one, and adding trucks would not change it much. The traffic-only part is '
      + 'the coefficient below, and it is small.<br><br>'
      + 'Site-wide, adding trucks to a segment <b>does</b> slow it, and the effect is '
      + `<b>negligible</b>: within-segment slope <b>${fit.within_cell_slope_kmh_per_truck} `
      + `km/h per extra truck</b> (t = ${fit.t_stat}, n = ${paNum(fit.rows_used)} of `
      + `${paNum(fit.rows_total)} segment-hours, ${fit.segments} segments, `
      + `${fit.window_days} days). Statistically significant, practically irrelevant: `
      + `R&sup2; within cells is <b>${fit.within_r2}</b>, so density explains ~`
      + `${paNum(100 * fit.within_r2, 1)}% of speed variation, and the full range from `
      + 'the emptiest to the busiest density decile is about &minus;4.8%. '
      + '<b>No congestion term is in the tonnage model</b>, and gate J53 keeps it out: '
      + 'at trip level the correlation flips sign (more trucks, shorter cycles) because '
      + 'dispatch sends trucks to routes that are running well. Contention is reported '
      + 'as measured capacity headroom in the next section instead. The per-segment '
      + 'drops above are observed differences, not a fitted congestion response.'
    : '<span class="muted">Speed-density fit unavailable '
      + '(reports/speed_density_fit.json not found), so no coefficient is claimed.</span>';
}

/* ---------- Section 5 · capacity at loading / dumping points ---------- */

function paGauges(sim, rows) {
  const opts = _paOptions || {};
  const cap = {};
  (opts.loading_points || []).forEach(p =>
    cap['L:' + String(p.point).toUpperCase()] = p);
  (opts.dumping_points || []).forEach(p =>
    cap['D:' + String(p.point).toUpperCase()] = p);

  // Demand is summed ACROSS plans, which is the whole point: two plans that load
  // from one point are one queue.
  const demand = {};
  rows.forEach(r => {
    const add = (kind, point) => {
      const k = kind + ':' + String(point).toUpperCase();
      demand[k] = demand[k] || {kind, point, trips: 0, trucks: 0, routes: []};
      demand[k].trips += r.total_trips || 0;
      demand[k].trucks += r.n_trucks || 0;
      demand[k].routes.push(r.route);
    };
    add('L', r.source); add('D', r.destination);
  });

  const items = Object.keys(demand).map(k => {
    const d = demand[k], c = cap[k];
    const ceiling = c ? c.capacity_trips_shift : null;
    return Object.assign({}, d, {
      ceiling,
      hours: c ? c.observed_hours : null,
      ratio: (ceiling && ceiling > 0) ? d.trips / ceiling : null,
    });
  }).sort((a, b) => (b.ratio || 0) - (a.ratio || 0));

  const host = document.getElementById('pa-gauges');
  if (!host) return;
  host.innerHTML = items.map((it, i) =>
    `<div style="flex:0 0 190px"><div id="pa-gauge-${i}" style="height:150px"></div>
     <div class="muted" style="font-size:10.5px;text-align:center;margin-top:-8px">
       ${it.kind === 'L' ? 'Loading' : 'Dumping'} · <b>${paEsc(it.point)}</b><br>
       ${paNum(it.trips)} of ${it.ceiling === null ? '—' : paNum(it.ceiling)} trips/shift
     </div></div>`).join('');

  items.forEach((it, i) => {
    if (it.ratio === null) {
      const el = document.getElementById('pa-gauge-' + i);
      if (el) el.innerHTML = '<div class="muted" style="font-size:11px;padding:20px 6px;'
        + 'text-align:center">no measured ceiling for this point</div>';
      return;
    }
    const pct = Math.min(150, 100 * it.ratio);
    const colour = it.ratio > 1 ? PA_C.bad : (it.ratio >= 0.8 ? PA_C.warn : PA_C.ok);
    paChart('pa-gauge-' + i, {
      backgroundColor: 'transparent',
      series: [{
        type: 'gauge', min: 0, max: 150, startAngle: 210, endAngle: -30,
        radius: '92%', center: ['50%', '58%'],
        progress: {show: true, width: 12, itemStyle: {color: colour}},
        axisLine: {lineStyle: {width: 12, color: [[1, 'rgba(139,152,165,.18)']]}},
        axisTick: {show: false}, splitLine: {show: false},
        axisLabel: {show: false}, pointer: {show: false},
        anchor: {show: false},
        title: {show: false},
        detail: {valueAnimation: false, offsetCenter: [0, 0], fontSize: 19,
                 color: colour, formatter: v => paNum(v, 0) + '%'},
        data: [{value: pct}],
      }],
    });
  });

  const breach = items.filter(it => it.ratio !== null && it.ratio > 1);
  document.getElementById('pa-gauge-note').innerHTML =
    'Utilisation is trips requested by this plan against the <b>p99 of hourly '
    + 'throughput actually observed</b> at that point, scaled to the shift &mdash; a '
    + 'demonstrated ceiling, not a design rating. p99 rather than max, because the '
    + 'max is a single freak hour. Green below 80%, amber 80&ndash;100%, red above. '
    + 'Points with fewer than 200 observed hours have no published ceiling and are '
    + 'shown without a gauge rather than with a guessed one. '
    + (breach.length
        ? '<span style="color:' + PA_C.bad + '"><b>' + breach.length + ' point(s) over '
          + 'ceiling:</b> ' + breach.map(b => paEsc(b.point)).join(', ')
          + '. Those trucks queue and the extra tonnes do not arrive.</span>'
        : 'No point in this plan is above its measured ceiling.');
}

/* ---------- Section 7 · historical reference ---------- */

function paHistory(rows) {
  // Top-k matched days from /api/plan/analogues (fleet-banded), then all-days boxplot.
  const ana = _paAnalogues;
  const ensEl = document.getElementById('pa-analogues-ensemble');
  const anaRows = document.getElementById('pa-analogues-rows');
  if (ensEl) {
    if (ana && ana.ok && ana.ensemble) {
      const e = ana.ensemble;
      ensEl.innerHTML =
        '<div class="effkpi"><div class="v">' + paNum(e.trips_med) + '</div><div class="l">history trips med</div></div>'
        + '<div class="effkpi"><div class="v">' + paNum(e.wmt_med) + ' t</div><div class="l">history WMT med</div></div>'
        + '<div class="effkpi"><div class="v">' + paNum(e.wmt_p25) + '–' + paNum(e.wmt_p75)
        + '</div><div class="l">history WMT P25–P75</div></div>'
        + '<div class="effkpi"><div class="v">' + paNum((ana.analogues || []).length)
        + '</div><div class="l">matched days</div></div>';
    } else {
      ensEl.innerHTML = '<p class="muted" style="margin:0;font-size:12px">Analogue ensemble unavailable.</p>';
    }
  }
  if (anaRows) {
    const list = (ana && ana.ok && ana.analogues) || [];
    anaRows.innerHTML = list.length ? list.map(a => {
      const spd = a.avg_speed_kmh != null ? paNum(a.avg_speed_kmh, 1) + ' km/h' : '—';
      const why = paEsc((a.why || '') + (a.location_note ? ' · ' + a.location_note : ''));
      return '<tr><td><b>' + paEsc(a.date) + '</b></td><td>' + paEsc(a.route || '') + '</td>'
        + '<td>' + paEsc(a.season || '') + '</td>'
        + '<td class="r">' + paNum(a.dt, 1) + '</td>'
        + '<td class="r">' + paNum(a.trips_per_dt, 2) + '</td>'
        + '<td class="r">' + paNum(a.wmt) + '</td>'
        + '<td class="r">' + spd + '</td>'
        + '<td class="muted" style="font-size:10.5px">' + why + '</td></tr>';
    }).join('') : '<tr><td colspan="8" class="muted">'
      + paEsc((ana && ana.error) || 'No matched days.') + '</td></tr>';
  }

  const daily = ((_paCapability || {}).dailyByPath) || [];
  // dailyByPath is per (path, DAY): srit = trips in the shift-normalised figure,
  // snb = average shift fleet. Trips per DT is srit/snb, which is the same
  // quantity the simulator predicts as trips_per_shift_per_truck.
  const byPath = {};
  daily.forEach(x => {
    const nb = Number(x.snb), rit = Number(x.srit);
    if (!(nb > 0) || !(rit >= 0)) return;
    const k = String(x.o).toUpperCase() + '>' + String(x.dd).toUpperCase();
    (byPath[k] = byPath[k] || []).push({v: rit / nb, nb, d: x.d});
  });

  const cats = [], boxes = [], preds = [], verdicts = [];
  rows.forEach(r => {
    const k = String(r.source).toUpperCase() + '>' + String(r.destination).toUpperCase();
    const hist = (byPath[k] || []).slice();
    const pred = r.trips_per_shift_per_truck;
    if (hist.length < 4) {
      verdicts.push({route: r.route, n: hist.length, pred, q: null,
                     verdict: 'no comparable history (' + hist.length + ' day(s))'});
      return;
    }
    const sorted = hist.map(h => h.v).sort((a, b) => a - b);
    const q = paQuartiles(sorted);
    cats.push(r.route);
    boxes.push([q.min, q.q1, q.med, q.q3, q.max]);
    preds.push(pred);
    let verdict;
    if (pred < q.min) verdict = 'BELOW every observed day';
    else if (pred > q.max) verdict = 'ABOVE every observed day';
    else if (pred >= q.q1 && pred <= q.q3) verdict = 'within the historical middle half';
    else verdict = 'inside the observed range, outside the middle half';
    verdicts.push({route: r.route, n: hist.length, pred, q, verdict});
  });

  if (cats.length) {
    paChart('pa-history-chart', {
      backgroundColor: 'transparent',
      tooltip: {trigger: 'item'},
      legend: {textStyle: {color: PA_C.text, fontSize: 11}, top: 0,
               data: ['Observed trips/DT per day', 'This plan']},
      grid: {left: 8, right: 18, bottom: 4, top: 34, containLabel: true},
      xAxis: {type: 'category', data: cats,
              axisLabel: {color: PA_C.text, fontSize: 10, interval: 0, rotate: cats.length > 3 ? 20 : 0}},
      yAxis: {type: 'value', name: 'trips / DT / shift', min: 0,
              nameTextStyle: {color: PA_C.axis}, axisLabel: {color: PA_C.axis},
              splitLine: {lineStyle: {color: PA_C.grid}}},
      series: [
        {name: 'Observed trips/DT per day', type: 'boxplot', data: boxes,
         itemStyle: {color: 'rgba(74,158,255,.18)', borderColor: PA_C.meas},
         boxWidth: [12, 42]},
        {name: 'This plan', type: 'scatter', symbolSize: 13,
         data: preds.map((p, i) => [i, p]),
         itemStyle: {color: PA_C.warn, borderColor: '#fff', borderWidth: 1.5}, z: 5},
      ],
    });
  } else {
    paChart('pa-history-chart', {});
  }

  document.getElementById('pa-history-rows').innerHTML = verdicts.map(v =>
    `<tr><td><b>${paEsc(v.route)}</b></td>
      <td class="r">${paNum(v.n)}</td>
      <td class="r">${v.q ? paNum(v.q.min, 2) : '—'}</td>
      <td class="r">${v.q ? paNum(v.q.med, 2) : '—'}</td>
      <td class="r">${v.q ? paNum(v.q.max, 2) : '—'}</td>
      <td class="r"><b>${paNum(v.pred, 2)}</b></td>
      <td>${paEsc(v.verdict)}</td></tr>`).join('')
    || '<tr><td colspan="7" class="muted">No plans to compare.</td></tr>';

  const corpusNote = (ana && ana.basis)
    ? (' Matched-day table uses <b>' + paEsc(ana.basis.corpus_source || '')
       + '</b> corpus (' + paNum(ana.basis.corpus_n) + ' path-days); GPS speeds only from '
       + paEsc(ana.basis.gps_haul_start || '2026-07-15') + ' onward.')
    : '';
  document.getElementById('pa-history-note').innerHTML =
    'The <b>matched days</b> table ranks historical path-days by fleet band (+ contractor / weather when available). '
    + 'The boxplot below is still all days for that OD — a wider sanity check. '
    + 'Neither feeds /api/simulate tonnes.' + corpusNote;
}

/* ---------- Section 8 · fleet sizing ---------- */

function paFleet(sim, rows) {
  const fs = ((sim || {}).summary || {}).fleet_sizing || {};
  const body = rows.map(r => {
    const measured = r.roster_basis === 'measured';
    const extra = (r.trucks_to_roster || 0) - (r.n_trucks || 0);
    return `<tr><td><b>${paEsc(r.route)}</b></td>
      <td class="r">${paNum(r.n_trucks)}</td>
      <td class="r"><b>${paNum(r.trucks_to_roster)}</b>${measured ? '' : '*'}</td>
      <td class="r">${extra > 0 ? '+' + paNum(extra) : paNum(extra)}</td>
      <td class="r">${paNum(r.roster_availability, 3)}</td>
      <td>${measured
            ? '<span style="color:' + PA_C.ok + '">measured</span>'
            : '<span style="color:' + PA_C.warn + '">fleet prior *</span>'}</td></tr>`;
  }).join('');
  document.getElementById('pa-fleet-rows').innerHTML = body
    || '<tr><td colspan="6" class="muted">No plans.</td></tr>';

  document.getElementById('pa-fleet-foot').innerHTML =
    `<tr><th>Total</th><th class="r">${paNum(fs.trucks_hauling)}</th>
     <th class="r">${paNum(fs.trucks_to_roster)}</th>
     <th class="r">${paNum((fs.trucks_to_roster || 0) - (fs.trucks_hauling || 0))}</th>
     <th class="r">${paNum(fs.measured_availability, 3)}</th>
     <th>${paEsc((fs.bases_used || []).join(' + '))}</th></tr>`;

  document.getElementById('pa-fleet-note').innerHTML =
    'This is what availability is <b>for</b>. It sizes the roster and it never scales '
    + 'the tonnage: the effective cycle already contains downtime, so an allowance on '
    + 'top double-counts it (measured bias: +5.5% with no factor, &minus;10.3% at '
    + '&times;0.85). ' + paEsc(fs.basis || '') + ' '
    + '<b>Read the mean carefully:</b> the distribution is bimodal &mdash; 75.4% of '
    + 'truck-shifts sit at exactly 1.0 and 19.8% at exactly 0.0 &mdash; so the honest '
    + 'phrasing is "~28% of haul-truck shifts are lost entirely", not "every truck '
    + 'runs at 72%". A starred roster figure means no availability is measured for '
    + "that route's own trucks and the site-wide prior was used; "
    + paEsc(fs.coverage_note || '') + '. '
    + '<b>Not broken down by contractor:</b> the roster is computed per route and '
    + 'there is no contractor dimension on it, so a per-contractor table would be '
    + 'apportionment presented as measurement.';
}

/* ---------- Section 9 · corridor map ---------- */

/* Colour a speed. Anchored on the MEASURED distribution rather than a pretty
 * gradient: median loaded speed on this corridor is 16.6 km/h and median empty
 * 18.3, so the mid-point sits at 17 and the scale saturates at 8 and 30. A
 * generic 0-100 scale would paint the whole road the same shade. */
function paSpeedColour(v) {
  if (v === null || v === undefined || !isFinite(v)) return '#4a5568';
  const t = Math.max(0, Math.min(1, (v - 8) / (30 - 8)));
  // red -> amber -> green
  const stops = [[0, 229, 83, 75], [0.5, 210, 153, 34], [1, 63, 185, 80]];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) { a = stops[i]; b = stops[i + 1]; }
  }
  const f = (b[0] - a[0]) ? (t - a[0]) / (b[0] - a[0]) : 0;
  const ch = (i) => Math.round(a[i] + (b[i] - a[i]) * f);
  return `rgb(${ch(1)},${ch(2)},${ch(3)})`;
}

/* Percentage-below-free-flow uses the opposite polarity: bigger is worse. */
function paDropColour(p) {
  if (p === null || p === undefined || !isFinite(p)) return '#4a5568';
  const t = Math.max(0, Math.min(1, p / 60));
  return `rgb(${Math.round(63 + (229 - 63) * t)},${Math.round(185 + (83 - 185) * t)},${Math.round(80 + (75 - 80) * t)})`;
}

function paMapMetric(v) { _paMapMetric = v; paMap(); }

/* Fill the side panel for one segment. Kept separate from the popup so the
 * figures stay on screen after the popup closes. */
function paMapDetail(s) {
  const el = document.getElementById('pa-map-detail');
  if (!el || !s) return;
  const gap = (s.loadedSpeed && s.emptySpeed)
    ? 100 * (s.emptySpeed - s.loadedSpeed) / s.loadedSpeed : null;
  const row = (k, v) => `<tr><td class="muted" style="padding-right:10px">${k}</td><td><b>${v}</b></td></tr>`;
  el.innerHTML = `<div style="border:1px solid var(--line,#30363d);border-radius:8px;padding:10px">
    <b style="font-size:13px">${paEsc(s.seg)}</b>
    <div class="muted" style="font-size:11px;margin-bottom:6px">KM ${paNum(s.from, 1)}&ndash;${paNum(s.to, 1)}</div>
    <table style="font-size:12px">
    ${row('Loaded (down)', s.loadedSpeed == null ? '—' : paNum(s.loadedSpeed, 1) + ' km/h')}
    ${row('Empty (up)', s.emptySpeed == null ? '—' : paNum(s.emptySpeed, 1) + ' km/h')}
    ${row('Empty vs loaded', gap == null ? '—' : paNum(gap, 1) + '%')}
    ${row('Free-flow', paNum(s.freeFlow, 1) + ' km/h')}
    ${row('Peak trucks', paNum(s.peakTrucks))}
    ${row('GPS fixes L/E', paNum(s.nLoaded) + ' / ' + paNum(s.nEmpty))}
    ${row('Segment-hours', paNum(s.n))}
    </table></div>`;
}

/* Clicking a row in the side table centres the map on that section. */
function paMapFocus(seg) {
  const s = (_paSegIndex || {})[seg];
  if (!s || !_paMap || !_paGeom) return;
  const alias = _paGeom.roadAlias || {};
  const road = (_paGeom.roads || []).find(r =>
    r.road.toUpperCase() === (alias[s.road] || s.road).toUpperCase());
  if (!road) return;
  const pts = road.points.filter(p => p.km >= s.from && p.km <= s.to);
  if (!pts.length) return;
  const b = L.latLngBounds(pts.map(p => [p.lat, p.lng]));
  _paMap.fitBounds(b, {padding: [60, 60], maxZoom: 15});
  paMapDetail(s);
}

function paMap() {
  const el = document.getElementById('pa-map');
  const note = document.getElementById('pa-map-note');
  if (!el) return;

  if (typeof L === 'undefined') {
    el.innerHTML = '<div class="muted" style="padding:20px;font-size:12px">'
      + 'Map library unavailable (Leaflet loads from a CDN and this machine '
      + 'appears to be offline). Every speed on this map is also in section 3 '
      + 'and its table.</div>';
    return;
  }
  const geo = _paGeom || {};
  if (!geo.ok || !(geo.roads || []).length) {
    el.innerHTML = '<div class="muted" style="padding:20px;font-size:12px">'
      + paEsc(geo.reason || 'corridor geometry unavailable') + '</div>';
    if (note) note.innerHTML = '';
    return;
  }

  // Index measured segments by road + km span so a polyline slice can find its
  // speeds. Segment ids name the Tofu road "TF"; chainage calls it "TOFU".
  const alias = geo.roadAlias || {};
  const segs = ((_paCongestion || {}).segments) || [];
  const byRoad = {};
  segs.forEach(s => {
    const p = paParseSeg(s.seg);
    if (!p) return;
    const road = (alias[p.road] || p.road).toUpperCase();
    (byRoad[road] = byRoad[road] || []).push(Object.assign({}, s, p));
  });

  if (!_paMap) {
    // preferCanvas, and not only for speed with ~370 polylines. The SVG
    // renderer sizes its overlay from the container at init; this map lives in
    // a tab that starts hidden, so the overlay was created 0px wide and every
    // polyline was drawn correctly into a zero-width viewport -- 376 <path>
    // elements present, correct stroke and geometry, nothing visible.
    // invalidateSize moves the map but does not rescue a stale SVG viewport.
    // The canvas renderer is resized from the map's current pixel bounds on
    // every redraw, so it cannot get stuck that way.
    _paMap = L.map(el, {scrollWheelZoom: false, attributionControl: true,
                        preferCanvas: true});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '&copy; OpenStreetMap',
    }).addTo(_paMap);
    _paLayer = L.layerGroup().addTo(_paMap);
  }
  _paLayer.clearLayers();

  const metric = _paMapMetric || 'loadedSpeed';
  const bounds = [];
  let coloured = 0, uncoloured = 0;

  geo.roads.forEach(r => {
    const pts = r.points;
    const measured = byRoad[r.road.toUpperCase()] || [];
    // Draw the road in slices between consecutive chainage points, so colour
    // changes at the segment boundary rather than the whole road taking one
    // shade. A slice with no measured segment is drawn grey, not guessed.
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i], mid = (a.km + b.km) / 2;
      const seg = measured.find(s => mid >= s.from && mid <= s.to);
      let val = null, colour = '#4a5568';
      if (seg) {
        if (metric === 'dropPct') {
          val = seg.freeFlow ? 100 * (seg.freeFlow - seg.avgSpeed) / seg.freeFlow : null;
          colour = paDropColour(val);
        } else {
          val = seg[metric];
          colour = paSpeedColour(val);
        }
      }
      if (val === null || val === undefined) uncoloured++; else coloured++;
      const line = L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
        color: colour, weight: seg ? 6 : 3, opacity: seg ? 0.95 : 0.45,
      });
      if (seg) {
        // Clicking a section fills the side panel too, so the numbers stay
        // readable after the popup is dismissed.
        line.on('click', () => paMapDetail(seg));
        line.bindPopup(
          `<b>${paEsc(seg.seg)}</b><br>`
          + `KM ${paNum(seg.from, 1)}&ndash;${paNum(seg.to, 1)}<br>`
          + `loaded (down): <b>${seg.loadedSpeed == null ? '—' : paNum(seg.loadedSpeed, 1) + ' km/h'}</b><br>`
          + `empty (up): <b>${seg.emptySpeed == null ? '—' : paNum(seg.emptySpeed, 1) + ' km/h'}</b><br>`
          + `free-flow: ${paNum(seg.freeFlow, 1)} km/h<br>`
          + `pooled mean: ${paNum(seg.avgSpeed, 1)} km/h<br>`
          + `peak trucks: ${paNum(seg.peakTrucks)}<br>`
          + `GPS fixes loaded/empty: ${paNum(seg.nLoaded)} / ${paNum(seg.nEmpty)}<br>`
          + `segment-hours: ${paNum(seg.n)}`);
      }
      line.addTo(_paLayer);
      bounds.push([a.lat, a.lng], [b.lat, b.lng]);
    }
  });

  // Corridor nodes, positioned by looking their chainage up on the road that
  // carries that km -- so the marker sits on the line, not at a guessed point.
  const nodes = ((geo.corridor || {}).nodes) || [];
  const ranges = ((geo.corridor || {}).roadRanges) || [];
  nodes.forEach(n => {
    const rr = ranges.find(x => n.km <= Math.max(x.fromKm, x.toKm)
                             && n.km >= Math.min(x.fromKm, x.toKm));
    const road = geo.roads.find(r => r.road.toUpperCase()
                                  === (alias[(rr || {}).label] || (rr || {}).label || '').toUpperCase());
    if (!road) return;
    let best = null, bd = 1e9;
    road.points.forEach(p => { const d = Math.abs(p.km - n.km); if (d < bd) { bd = d; best = p; } });
    if (!best || bd > 1.0) return;
    L.circleMarker([best.lat, best.lng], {
      radius: 6, color: '#fff', weight: 2, fillColor: PA_C.warn, fillOpacity: 1,
    }).bindPopup(`<b>${paEsc(n.label)}</b><br>chainage KM ${paNum(n.km, 1)}`)
      .addTo(_paLayer);
  });

  // invalidateSize BEFORE fitBounds, and fit again after the container has
  // settled. Leaflet computes the zoom from the container's CURRENT pixel size;
  // this section is inside a tab that starts hidden, so the first fit ran
  // against a stale (smaller) viewport and left the corridor as a hairline on a
  // map of the whole island. Fitting twice is cheap and removes the race.
  const fit = () => {
    try {
      _paMap.invalidateSize(false);
      if (bounds.length) _paMap.fitBounds(bounds, {padding: [24, 24]});
    } catch (e) { /* container not laid out yet */ }
  };
  fit();
  setTimeout(fit, 120);
  setTimeout(fit, 400);

  // --- side panel: legend, and the sections worth looking at ---
  const legend = document.getElementById('pa-map-legend');
  if (legend) {
    const swatch = (c, t) => `<span style="display:inline-flex;align-items:center;gap:5px;margin-right:10px">`
      + `<span style="width:16px;height:8px;border-radius:2px;background:${c};display:inline-block"></span>`
      + `<span class="muted" style="font-size:11px">${t}</span></span>`;
    legend.innerHTML = (metric === 'dropPct'
      ? swatch(paDropColour(0), '0%') + swatch(paDropColour(30), '30%') + swatch(paDropColour(60), '60%+')
      : swatch(paSpeedColour(8), '8 km/h') + swatch(paSpeedColour(17), '17') + swatch(paSpeedColour(30), '30+'))
      + swatch('#4a5568', 'no measurement');
  }

  const ranked = [].concat(...Object.values(byRoad))
    .filter(s => s.loadedSpeed != null && s.emptySpeed != null)
    .sort((a, b) => a.loadedSpeed - b.loadedSpeed).slice(0, 12);
  const rowsEl = document.getElementById('pa-map-rows');
  if (rowsEl) {
    rowsEl.innerHTML = ranked.map(s => {
      const gap = 100 * (s.emptySpeed - s.loadedSpeed) / s.loadedSpeed;
      return `<tr style="cursor:pointer" onclick="paMapFocus('${paEsc(s.seg).replace(/'/g, "")}')">
        <td>${paEsc(s.seg)}</td>
        <td class="r" style="color:${paSpeedColour(s.loadedSpeed)}">${paNum(s.loadedSpeed, 1)}</td>
        <td class="r" style="color:${paSpeedColour(s.emptySpeed)}">${paNum(s.emptySpeed, 1)}</td>
        <td class="r">${paNum(gap, 0)}%</td></tr>`;
    }).join('') || '<tr><td colspan="4" class="muted">no measured sections</td></tr>';
  }
  _paSegIndex = {};
  [].concat(...Object.values(byRoad)).forEach(s => { _paSegIndex[s.seg] = s; });
  if (!document.getElementById('pa-map-detail').innerHTML && ranked.length) {
    paMapDetail(ranked[0]);
  }

  const label = {loadedSpeed: 'loaded speed', emptySpeed: 'empty speed',
                 avgSpeed: 'pooled mean speed',
                 dropPct: '% below free-flow'}[metric] || metric;
  if (note) {
    note.innerHTML =
      `Centreline from <b>HAUL_ROAD_STA</b> (${paNum(geo.roads.reduce((a, r) => a + r.nRaw, 0))} `
      + `chainage markers, downsampled to ~0.25 km), coloured by <b>${label}</b>. `
      + `<b>${paNum(coloured)}</b> slices carry a measured segment; `
      + `<b>${paNum(uncoloured)}</b> are drawn thin and grey because no segment `
      + 'covers them &mdash; absence of measurement, not a slow road. '
      + (((_paCongestion || {}).servedFrom === 'fixture')
          ? '<b style="color:' + PA_C.warn + '">Speeds are cached, not live.</b> '
          : '')
      + 'Scale is anchored on the measured distribution (median loaded 16.6 km/h, '
      + 'empty 18.3), so it saturates at 8 and 30 km/h rather than 0 and 100 &mdash; '
      + 'a generic scale would paint the whole corridor one shade.';
  }
}

/* ---------- Section 9b · the 3D view ---------- */

/* CesiumJS, loaded ON DEMAND. It is ~4 MB and this tool is demonstrated on site
 * connections, so the default 2D path must not pay for a view most sessions
 * never open. No ion token is used or needed: OpenStreetMap imagery and the
 * plain ellipsoid are both token-free, and a token could not be committed to a
 * public mirror anyway. Verified working without one.
 */
const PA_CESIUM = 'https://cesium.com/downloads/cesiumjs/releases/1.114/Build/Cesium/';

function paLoadCesium() {
  if (_paCesiumLoading) return _paCesiumLoading;
  if (typeof Cesium !== 'undefined') { _paCesiumLoading = Promise.resolve(true); return _paCesiumLoading; }
  _paCesiumLoading = new Promise((resolve) => {
    // Cesium resolves its workers and assets relative to this.
    window.CESIUM_BASE_URL = PA_CESIUM;
    const css = document.createElement('link');
    css.rel = 'stylesheet'; css.href = PA_CESIUM + 'Widgets/widgets.css';
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = PA_CESIUM + 'Cesium.js';
    s.onload = () => resolve(typeof Cesium !== 'undefined');
    s.onerror = () => resolve(false);
    document.head.appendChild(s);
  });
  return _paCesiumLoading;
}

function paMapView(mode) {
  const m2 = document.getElementById('pa-map');
  const m3 = document.getElementById('pa-map3d');
  const b2 = document.getElementById('pa-view-2d');
  const b3 = document.getElementById('pa-view-3d');
  if (!m2 || !m3) return;
  _paMapMode = mode;
  const on3 = mode === '3d';
  m2.style.display = on3 ? 'none' : '';
  m3.style.display = on3 ? '' : 'none';
  if (b2) b2.classList.toggle('on', !on3);
  if (b3) b3.classList.toggle('on', on3);
  if (on3) {
    m3.innerHTML = '<div class="muted" style="padding:20px;font-size:12px">Loading 3D view…</div>';
    paLoadCesium().then((ok) => {
      if (!ok) {
        m3.innerHTML = '<div class="muted" style="padding:20px;font-size:12px;'
          + 'border:1px dashed var(--line,#30363d);border-radius:8px">'
          + '3D unavailable: CesiumJS loads from a CDN and this machine appears '
          + 'to be offline. The 2D map and every figure in section 3 still work.'
          + '</div>';
        return;
      }
      paMap3D();
    });
  } else {
    // Leaflet needs a nudge after being un-hidden, or it keeps the size it had
    // while display:none.
    setTimeout(() => { try { _paMap && _paMap.invalidateSize(); } catch (e) {} }, 60);
  }
}

function paMap3D() {
  const el = document.getElementById('pa-map3d');
  const geo = _paGeom || {};
  if (!el) return;
  if (!geo.ok || !(geo.roads || []).length) {
    el.innerHTML = '<div class="muted" style="padding:20px;font-size:12px">'
      + paEsc(geo.reason || 'corridor geometry unavailable') + '</div>';
    return;
  }
  el.innerHTML = '';

  const alias = geo.roadAlias || {};
  const segs = ((_paCongestion || {}).segments) || [];
  const byRoad = {};
  segs.forEach(s => {
    const p = paParseSeg(s.seg);
    if (!p) return;
    const road = (alias[p.road] || p.road).toUpperCase();
    (byRoad[road] = byRoad[road] || []).push(Object.assign({}, s, p));
  });

  if (_paViewer) { try { _paViewer.destroy(); } catch (e) {} _paViewer = null; }

  // OSM imagery + the plain ellipsoid: both work with NO ion token. Real terrain
  // would need one, and there is no elevation in this database to drape on it
  // anyway (ELEVATIONS is 100% NULL).
  //
  // The provider is passed as `baseLayer`, NOT the older `imageryProvider:`
  // constructor option. That option was removed around Cesium 1.107 and is
  // SILENTLY IGNORED in 1.114 -- no error, no warning, just a viewer with zero
  // imagery layers and the default blue globe. It looked like a tile-loading
  // problem; imageryLayers.length was 0.
  const osm = new Cesium.OpenStreetMapImageryProvider(
    {url: 'https://tile.openstreetmap.org/'});
  const opts = {
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    baseLayerPicker: false, geocoder: false, homeButton: false,
    sceneModePicker: false, navigationHelpButton: false, animation: false,
    timeline: false, infoBox: false, selectionIndicator: false,
    fullscreenButton: false, creditContainer: document.createElement('div'),
  };
  try {
    opts.baseLayer = new Cesium.ImageryLayer(osm);      // 1.104+
  } catch (e) { /* older build: added below instead */ }
  _paViewer = new Cesium.Viewer(el, opts);
  // Belt and braces across Cesium versions: if the viewer still has no imagery,
  // attach it directly rather than shipping a blue void.
  try {
    if (_paViewer.imageryLayers.length === 0) {
      _paViewer.imageryLayers.addImageryProvider(osm);
    }
  } catch (e) { /* nothing more to try */ }
  _paViewer.scene.globe.enableLighting = false;

  const metric = _paMapMetric || 'loadedSpeed';
  const val = (s) => (metric === 'dropPct'
    ? (s.freeFlow ? 100 * (s.freeFlow - s.avgSpeed) / s.freeFlow : null)
    : s[metric]);
  const col = (v) => (metric === 'dropPct' ? paDropColour(v) : paSpeedColour(v));

  // HEIGHT ENCODES SPEED, NOT ELEVATION. On a 3D globe a raised ribbon reads as
  // terrain unless it is said otherwise, and this database has no elevation at
  // all -- so the note below states it and the units are km/h, not metres.
  // Slower sections stand taller, because the planner is looking for the slow
  // ones.
  // Ribbon height at the slowest end. Tuned against the corridor, not picked:
  // the road runs ~37 km, so a 900 m wall is 2.4% of its length and reads as
  // flat from any useful camera angle. 2,600 m is legible while still
  // obviously a data encoding rather than a mountain.
  const H = 2600;
  let drawn = 0, blank = 0;

  geo.roads.forEach(r => {
    const pts = r.points;
    const measured = byRoad[r.road.toUpperCase()] || [];
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i], mid = (a.km + b.km) / 2;
      const seg = measured.find(s => mid >= s.from && mid <= s.to);
      const v = seg ? val(seg) : null;
      if (v === null || v === undefined) {
        blank++;
        _paViewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArray([a.lng, a.lat, b.lng, b.lat]),
            width: 2, material: Cesium.Color.fromCssColorString('#4a5568').withAlpha(0.6),
            clampToGround: true,
          },
        });
        continue;
      }
      drawn++;
      // Invert for speed metrics so SLOW is TALL; dropPct is already
      // "worse = bigger".
      const t = metric === 'dropPct'
        ? Math.max(0, Math.min(1, v / 60))
        : 1 - Math.max(0, Math.min(1, (v - 8) / (30 - 8)));
      const c = Cesium.Color.fromCssColorString(col(v));
      _paViewer.entities.add({
        name: seg.seg,
        paSeg: seg.seg,
        wall: {
          positions: Cesium.Cartesian3.fromDegreesArrayHeights(
            [a.lng, a.lat, 0, b.lng, b.lat, 0]),
          maximumHeights: [t * H + 40, t * H + 40],
          minimumHeights: [0, 0],
          material: c.withAlpha(0.82),
          outline: false,
        },
      });
    }
  });

  // Corridor nodes as labelled points, positioned on the line by chainage.
  const nodes = ((geo.corridor || {}).nodes) || [];
  const ranges = ((geo.corridor || {}).roadRanges) || [];
  nodes.forEach(n => {
    const rr = ranges.find(x => n.km <= Math.max(x.fromKm, x.toKm)
                             && n.km >= Math.min(x.fromKm, x.toKm));
    const road = geo.roads.find(r => r.road.toUpperCase()
                                  === (alias[(rr || {}).label] || (rr || {}).label || '').toUpperCase());
    if (!road) return;
    let best = null, bd = 1e9;
    road.points.forEach(p => { const d = Math.abs(p.km - n.km); if (d < bd) { bd = d; best = p; } });
    if (!best || bd > 1.0) return;
    _paViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(best.lng, best.lat, 60),
      point: {pixelSize: 10, color: Cesium.Color.fromCssColorString(PA_C.warn),
              outlineColor: Cesium.Color.WHITE, outlineWidth: 2},
      label: {text: n.label, font: '12px sans-serif',
              fillColor: Cesium.Color.WHITE,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              outlineWidth: 3, outlineColor: Cesium.Color.BLACK,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -12)},
    });
  });

  // Click a ribbon -> the same detail panel the 2D map fills.
  const handler = new Cesium.ScreenSpaceEventHandler(_paViewer.scene.canvas);
  handler.setInputAction((click) => {
    const picked = _paViewer.scene.pick(click.position);
    const id = picked && picked.id;
    const key = id && (id.paSeg || id.name);
    if (key && (_paSegIndex || {})[key]) paMapDetail(_paSegIndex[key]);
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  // Tilted view over the corridor, which runs roughly north-south.
  const lats = [], lngs = [];
  geo.roads.forEach(r => r.points.forEach(p => { lats.push(p.lat); lngs.push(p.lng); }));
  const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const midLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
  // Low and tilted, looking north up the corridor. A steeper pitch flattens the
  // ribbons back into the 2D view the toggle exists to escape.
  _paViewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(midLng, midLat - 0.34, 26000),
    orientation: {heading: Cesium.Math.toRadians(0),
                  pitch: Cesium.Math.toRadians(-28),
                  roll: 0},
  });

  const note = document.getElementById('pa-map-note');
  if (note) {
    note.innerHTML =
      '<b>3D view.</b> Ribbon <b>height encodes SPEED, not elevation</b> &mdash; '
      + 'slower sections stand taller. There is no terrain here on purpose: '
      + '<code>ELEVATIONS</code> is 100% NULL in this database, so a height that '
      + 'looked like ground would be invented. Imagery is OpenStreetMap and the '
      + 'globe is the plain ellipsoid, both of which need no Cesium ion token &mdash; '
      + 'a token could not be committed to a public mirror in any case. '
      + `<b>${paNum(drawn)}</b> sections drawn, <b>${paNum(blank)}</b> left flat `
      + 'and grey for want of a measurement. Drag to orbit, scroll to zoom, click '
      + 'a ribbon for its figures.';
  }
}

/* Road selector for Section 3. */
function paSetRoad(v) { _paRoad = v; paSpeed(); }

/* Explicit "Run assessment" entry point for the button. Re-runs the simulation
 * so the assessment can never render against a stale plan. */
function paRun() {
  if (typeof psRun === 'function') psRun();
  else if (_paLastSim) paRender(_paLastSim);
}
