/* plan_assessment.js — the plan assessment view (Sections 2-8 of the Production
 * Simulator tab). Charts are ECharts from CDN; there is no build step and no npm
 * dependency.
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
 *   2. Loaded vs empty speed as two lines per section.
 *      FMS_CONGESTION_SEG has a DIR column, but /api/simulator/congestion-model
 *      aggregates over it -- the payload has no direction field. So the two lines
 *      are measured mean speed and the data-anchored free-flow speed (p85 at
 *      bottom-quintile traffic), which are both real, instead of a loaded/empty
 *      split that would have to be invented. Splitting by DIR is a server change,
 *      noted as follow-up.
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
function paChart(id, option) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof echarts === 'undefined') {
    el.innerHTML = '<div class="muted" style="padding:14px;font-size:12px;'
      + 'border:1px dashed var(--line,#30363d);border-radius:8px">'
      + 'Chart library unavailable (ECharts is loaded from a CDN and this machine '
      + 'appears to be offline). Every figure in this section is also in the '
      + 'tables, which do not need it.</div>';
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
  if (c && (c.isDisposed() || c.getDom() !== el || !c.getDom().isConnected)) {
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
  return Promise.all(jobs);
}

/* Entry point. plan_simulator.js calls this with the /api/simulate response it
 * just rendered, so the assessment and the results table are the same numbers. */
function paRender(sim) {
  _paLastSim = sim;
  // Two wrappers, because sections 2-5 sit ABOVE the production table (section 6)
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
    paCongestion(sim, rows);
    paGauges(sim, rows);
    paHistory(rows);
    paFleet(sim, rows);
  });
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
  const meas = list.map(s => [s.from, s.avgSpeed]);
  const free = list.map(s => [s.from, s.freeFlow]);

  paChart('pa-speed-chart', {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (ps) => {
        if (!ps || !ps.length) return '';
        const km = ps[0].value[0];
        const s = list.find(x => x.from === km) || {};
        return `<b>${paEsc(s.seg || '')}</b><br>`
          + ps.map(p => `${p.marker}${p.seriesName}: ${paNum(p.value[1], 1)} km/h`).join('<br>')
          + `<br>observations: ${paNum(s.n)}<br>peak trucks on segment: ${paNum(s.peakTrucks)}`;
      },
    },
    legend: {textStyle: {color: PA_C.text, fontSize: 11}, top: 0},
    grid: {left: 8, right: 18, bottom: 4, top: 34, containLabel: true},
    xAxis: {type: 'value', name: 'KM chainage', nameLocation: 'middle', nameGap: 26,
            nameTextStyle: {color: PA_C.axis},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    yAxis: {type: 'value', name: 'km/h', min: 0, nameTextStyle: {color: PA_C.axis},
            axisLabel: {color: PA_C.axis}, splitLine: {lineStyle: {color: PA_C.grid}}},
    series: [
      {name: 'Free-flow (p85 at low traffic)', type: 'line', data: free,
       lineStyle: {color: PA_C.free, type: 'dashed', width: 2},
       itemStyle: {color: PA_C.free}, symbolSize: 5, z: 2},
      {name: 'Measured mean speed', type: 'line', data: meas,
       lineStyle: {color: PA_C.meas, width: 2.5}, itemStyle: {color: PA_C.meas},
       symbolSize: 6, z: 3},
    ],
  });

  const totalObs = list.reduce((a, s) => a + (s.n || 0), 0);
  document.getElementById('pa-speed-note').innerHTML =
    `Road <b>${paEsc(_paRoad)}</b>: ${list.length} segments, ${paNum(totalObs)} `
    + `segment-hours over ${paNum((_paCongestion || {}).days)} days of retention. `
    + 'The two lines are <b>measured mean speed</b> and the <b>free-flow</b> speed '
    + 'anchored in the data (p85 of speeds in the bottom traffic quintile). '
    + '<b>They are not loaded vs empty.</b> FMS_CONGESTION_SEG carries a direction '
    + 'column but this endpoint aggregates over it, so a loaded/empty split is not '
    + 'available without a server change &mdash; drawing one would be invention.'
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

  document.getElementById('pa-history-note').innerHTML =
    'Each box is the distribution of <b>observed</b> trips per DT per shift for that '
    + 'exact origin&rarr;destination over its recorded days; the amber dot is this '
    + "plan's prediction. This is a sanity check on the prediction, not an input to "
    + 'it. <b>Two caveats.</b> The brief asked to match on shift and weather: '
    + 'dailyByPath is aggregated per day, not per shift, and carries no rainfall, so '
    + 'neither can be matched at this grain &mdash; the box is all days, not '
    + 'weather-matched days. And a box is only drawn where at least 4 days exist; '
    + 'routes with fewer are listed with their count instead of a distribution '
    + 'invented from 2 points.';
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

/* Road selector for Section 3. */
function paSetRoad(v) { _paRoad = v; paSpeed(); }

/* Explicit "Run assessment" entry point for the button. Re-runs the simulation
 * so the assessment can never render against a stale plan. */
function paRun() {
  if (typeof psRun === 'function') psRun();
  else if (_paLastSim) paRender(_paLastSim);
}
